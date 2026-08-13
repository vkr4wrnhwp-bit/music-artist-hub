# Deploying the TRACE sync server

The sync server is a single dependency-free Node process. This guide covers
running it for real: TLS, process supervision, backups, and the account
lifecycle. Nothing here changes application code — it is all standard
self-hosting practice around `npm run server`.

## What you are deploying

- One process: `apps/server/src/main.ts` (via `tsx`), listening on `PORT`
  (default 8787).
- One directory: `TRACE_DATA_DIR`, containing everything the server knows:

```
trace-data/
  secret               HMAC token-signing key (created on first start)
  org-<orgId>.json     revisioned team database snapshot
  auth-<orgId>.json    scrypt password records (salt + hash, never plaintext)
  invites-<orgId>.json pending one-time invite codes (hashes only)
  telemetry/           binary telemetry chunks, <orgId>-<sessionId>.bin
```

Backing up the server IS backing up that directory. Copy it while the
process is stopped (or accept the small race of a live copy — writes are
whole-file). Restoring is putting the directory back.

## TLS is not optional

Auth tokens are bearer tokens: whoever holds one is that user until it
expires. Over plain HTTP on a shared network they can be read on the wire.
Run the server behind a TLS reverse proxy and never expose the plain port
beyond localhost.

Caddy (automatic certificates):

```
trace.example.com {
    reverse_proxy localhost:8787
}
```

nginx (certificates via certbot):

```
server {
    listen 443 ssl;
    server_name trace.example.com;
    ssl_certificate     /etc/letsencrypt/live/trace.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/trace.example.com/privkey.pem;
    client_max_body_size 64m;          # telemetry chunk uploads
    location / { proxy_pass http://localhost:8787; }
}
```

Then the URL teams enter in More → Team Sync is `https://trace.example.com`.

## Keeping it running (systemd)

```
[Unit]
Description=TRACE sync server
After=network.target

[Service]
User=trace
WorkingDirectory=/opt/mx-lab
Environment=PORT=8787
Environment=TRACE_DATA_DIR=/var/lib/trace
ExecStart=/usr/bin/npx tsx apps/server/src/main.ts
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

`systemctl enable --now trace` and it survives reboots.

## Account lifecycle (how trust works)

1. **Bootstrap.** A brand-new org (no database on the server yet) lets any
   listed team member sign in and set a password — someone has to be first.
   Do the bootstrap and the first Sync immediately, because…
2. **…the door closes on first push.** Once the team database is on the
   server, it is the authority: unknown users cannot sign in, roles come
   from the database (never from the client), and a new account's first
   sign-in requires a **one-time invite code** minted by an admin
   (More → Team & roles → Invite). Codes are stored hashed, shown exactly
   once, and die on use.
3. **Passwords** are scrypt-hashed with per-user salts and compared
   timing-safe. Users change their own via Team Sync → Change password
   (authenticated by the old password). A forgotten password is an admin
   deleting that user's entry from `auth-<orgId>.json` and minting a fresh
   invite.
4. **Remote tuners** never get accounts. They get grant tokens: minted
   in-app against a scoped, expiring, revocable grant, enforced server-side
   (redacted reads, no writes, export only if granted). Revoking the grant
   kills its tokens on their next request.
5. **SSO** (OIDC/IdP) replaces exactly one handler — `POST /auth/login` —
   and removes local passwords entirely. Everything behind it (token
   format, role authority, grant enforcement) is unchanged.

## Scaling honestly

Storage sits behind the `ServerStore` interface (four snapshot/chunk methods
plus auth/invite records). The file store is correct for a team's
self-hosted server — a race program's metadata measures in hundreds of
kilobytes. If hosting ever demands it, a document-database + object-store
adapter drops in without touching a route. Snapshot-level sync (the whole
org database per sync) is a deliberate simplicity trade documented in the
implementation report; per-collection deltas are the escape hatch if
snapshots ever grow past it.

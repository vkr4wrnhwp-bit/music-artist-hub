# Security model

---

## What we are protecting

1. **Provider credentials.** They spend money.
2. **The spend authorization itself.** A bug in routing must not be able to run
   up a bill.
3. **Likeness and consent.** Reference packs of real people.
4. **Unreleased footage.** Client work before it ships.
5. **The audit trail.** Who approved what, and what it cost.

## Who we are protecting against

| Actor | Capability assumed |
|---|---|
| Anonymous internet | can reach the public API surface and any webhook endpoint |
| Authenticated org member | can reach every project they are a member of |
| A provider (or anyone spoofing one) | can POST to our webhook endpoints |
| A malicious upload | controls filename, declared MIME, and file bytes |
| A malicious prompt | controls every string that reaches ffmpeg and the database |
| A compromised database backup | has every row, but not the process environment |

---

## Controls, and where they live

### Credentials

- Provider keys are read from the environment **server-side only**. No key is
  ever serialized to the browser; `/api/providers` returns a masked fingerprint
  (`abcd…yz (32 chars)`), never the key.
- `registerSecret()` records every live secret value at boot, and the logger
  passes every field through `redact()` — which scrubs both by **key name**
  (`authorization`, `api_key`, `token`, `secret`, …) and by **registered value**,
  so a key echoed back inside a provider error message is still scrubbed.
- Outbound URLs are logged with their query strings stripped, because signed
  provider URLs carry tokens there.
- `pnpm lint` fails the build on a committed AWS key id, Anthropic key,
  Google API key, private-key block, or literal bearer token, and on a
  `.gitignore` that does not ignore `.env`.

### Spending

- **Nothing reaches a provider's `submit()` except through the cost controller.**
  `RenderService.submitRender` is the only caller, and it cannot get there
  without an `authorize()` that returned `allowed`.
- Authorization runs **twice** — at plan time and again at submit time, because
  jobs wait in a queue while prices move and other jobs spend the budget.
- `MASTERCLIP_MODE=sandbox` (the default) refuses every billable submission
  outright, independent of budgets.
- `LIVE_SPEND_CAP_USD` is a global ceiling across every org and project, checked
  last and separately, precisely so a routing bug cannot spend at scale.
- Premium-tier renders and estimates above the project threshold require an
  explicit human approval flag; an agent cannot supply it —
  `assertCanApprovePremium` restricts that to the cost controller agent, and even
  that only produces a recommendation.
- `cost_ledger` and `audit_log` are append-only. Nothing in the codebase updates
  or deletes a row in either.

### Sessions and authorization

- Passwords: **scrypt** with a per-user salt, timing-safe comparison. Login runs
  the KDF even for an unknown email so response timing does not enumerate
  accounts.
- Sessions are opaque random tokens; only their **SHA-256** is stored. A database
  leak does not hand out live sessions.
- Cookies are `httpOnly`, `sameSite=lax`, and `secure` when
  `NODE_ENV=production`.
- Project access is checked on **every** project-scoped route via
  `requireProject`, which also verifies the project belongs to the caller's org.
  Roles ladder `viewer < editor < director < producer`; spending money and
  promoting masters require `director` or above.
- The first account bootstraps the org; after that `/api/auth/signup` refuses.

### Webhooks

Three independent defences, because provider webhook security ranges from signed
to nothing at all:

1. **Our own HMAC token in the callback URL**, bound to `(providerId, jobId)`, so
   a token minted for one job cannot authorize another.
2. **Per-provider signature verification** where the provider offers one
   (Replicate). Verification runs against the **raw request body** — the JSON
   content-type parser stashes the exact bytes, because re-serializing parsed
   JSON changes them and breaks every HMAC. A timestamp window rejects replays.
3. **A dedupe key** on a unique `(provider_id, dedupe_key)` index, so a
   redelivered webhook is acknowledged and ignored rather than driving a second
   ingest.

Even then, a webhook is treated as a **wake-up signal only**: authoritative state
is re-fetched from the provider before anything is recorded or spent. That is
what makes an unsigned MuAPI or fal callback safe to accept.

### Uploads

- Type is decided by **magic-byte sniffing**, not the declared `Content-Type` or
  the filename — both are attacker-controlled. Anything not on the allow-list is
  rejected.
- Filenames are stripped of directory separators, traversal, and leading dots.
- Object keys are **constructed** from `(projectId, kind, assetId, filename)`,
  never taken from input, and the local driver additionally resolves and rejects
  any key that escapes the storage root.
- Size limits: 512 MB per file, 8 files per request, 32 MB JSON bodies.
- Content-addressed dedupe by SHA-256 means the same upload is stored once.

### Serving media

The only route that returns bytes is `/api/assets/raw`, and it requires a valid
HMAC over `(key, expiry)` plus an unexpired deadline. A raw storage key is not
enough. Signature and expiry failures are indistinguishable in timing.

### Command execution

Every ffmpeg and ffprobe invocation goes through `run()` in
`packages/media-tools/src/runner.ts`, which uses **`execFile` with an argv
array** and `shell: false`. There is no string-command variant to reach for.
Prompts, character names, and filenames all flow through this layer and any of
them can contain quotes, semicolons, or backticks; an argv array makes shell
metacharacters inert by construction. `pnpm lint` fails the build if
`packages/media-tools` ever uses `exec()`.

The one place a path is written into a file rather than an argv slot is the
concat demuxer list, where paths are single-quoted with embedded quotes escaped,
and the list is written by us and deleted afterwards.

### SQL

Every query uses bound parameters. The only interpolated values are `LIMIT`
counts (passed through `Math.floor`) and table/column identifiers, which come
from literal strings in the code and are additionally validated against
`/^[a-z_][a-z0-9_]*$/i` by `assertIdent`. `pnpm lint` flags SQL that interpolates
anything else.

### Rights and consent

`requireAuthorizedForIdentity` refuses unless every reference in the pack is
explicitly `authorized`, has recorded consent, and has not expired. The failure
mode this prevents is generating a real person's likeness because someone dropped
a photo in a folder. Rights changes are written to the audit log.

---

## Known gaps in this release

Stated plainly rather than left to be discovered:

| Gap | Impact | Mitigation today |
|---|---|---|
| No rate limiting on the API | brute-force login, upload flooding | put it behind a reverse proxy that rate-limits |
| No CSRF token | `sameSite=lax` blocks cross-site POSTs from forms, but a token would be belt-and-braces | same-origin deployment; add tokens before exposing to untrusted networks |
| `SECRETS_ENCRYPTION_KEY` is defined but unused | the `provider_credentials` table exists for per-org keys; this release reads keys from the environment only | keys live in the environment, not the database |
| S3 driver unexercised against a live bucket | signing is unit-tested against AWS's published vector, but no end-to-end run | run `masterclip doctor` with `STORAGE_DRIVER=s3` before relying on it |
| No per-user MFA or invite flow | first account bootstraps, others are created by an owner | keep the deployment private |
| Session revocation is per-session | no "sign out everywhere" | delete rows from `sessions` |

## Reporting

Security issues in this codebase should go to the repository owner privately
rather than through a public issue.

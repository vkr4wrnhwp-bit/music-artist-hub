# Motion to Vault hand-off

Owner, 2026-09-19: "I thought we had discussed sending everything to Motion
and being able to pull it into basically your vault or your artist profile."

This is the smallest spec for that. Nothing in it is built on either side.
Street Banker (V1) carries one stub endpoint behind a flag that is off; Motion
carries nothing yet.

## What Motion exposes today (read 2026-09-19, masterclip-os `apps/api/src`)

Motion is the masterclip-os repo, live at motion.streetbankermusic.com. V1
opens it through `/suites/go/motion`, which sends the browser to Motion's
`GET /auth/street-banker?token=...` with a short-lived sb_suite_sso token.

- The sign-in landing reads **only `token`** and redirects to `/`. V1's
  `sb_suite_sso.handoff_url` already adds a `next` query value; Motion
  ignores it. So no rollout context can ride along today: the Motion link
  in V1 is a plain link.
- Finished media is reachable only from inside a Motion session, by
  cookie, on project-scoped routes:
  - `GET /api/shots/:shotId/outputs` returns signed URLs (1 hour) for each
    render's source, proxy, thumbnail and contact sheet.
  - `GET /api/assets/:assetId/url` returns a signed URL (1 hour) for one
    asset.
  - `GET /api/projects/:projectId/masters` lists masters with their
    deliverables; `POST /api/masters/:masterId/finish` renders deliverables
    (`social_h264`, `delivery_h264`, ProRes and so on); `POST
    /api/masters/:masterId/package` writes a package **to Motion's own disk**
    and returns a directory path, not a URL.
  - `GET /api/projects/:projectId/shots/export` exports shot specs as CSV or
    a bundle. That is the shot list, not the media.
- There is **no** share link, no API-key or service-to-service read of a
  finished file, no "send to" button, and no outbound call to any other app.
  The only outbound HTTP in Motion is provider webhooks coming **in**
  (`POST /api/webhooks/:providerId`).

So the honest V1 action is: open Motion in a new tab, make the file there,
download it, upload it to the Vault. Every Rollout page and the Cover Studio
now say exactly that.

## What Motion should expose (the spec)

Two pieces, in this order. The first is useful on its own.

### 1. A signed download URL per finished deliverable, for a named recipient

`POST /api/masters/:masterId/deliverables/:deliverableId/handoff`

Session-authenticated (the person is signed in to Motion through the
suite hand-off, so Motion already knows their Street Banker email).

Response:

```json
{
  "url": "https://motion.streetbankermusic.com/api/assets/raw?...signed...",
  "expires_at": "2026-09-19T21:00:00Z",
  "filename": "title-social-9x16.mp4",
  "content_type": "video/mp4",
  "bytes": 18234911,
  "sha256": "...",
  "email": "artist@example.com",
  "source": {"project_id": "...", "master_id": "...", "deliverable_id": "..."}
}
```

The URL must be fetchable **without a Motion cookie** (Motion already has
`verifySignedUrl` behind `/api/assets/raw` for local storage, and presigned
URLs for remote storage; this reuses whichever the deployment runs). Ten
minutes is enough; the receiver fetches it once.

### 2. A "Send to Street Banker Vault" button

On the Masters page, per deliverable. On click, Motion:

1. Calls step 1 to mint the URL.
2. Signs a hand-off call with the shared `SUITE_SSO_SECRET` the sign-in
   already uses (same shape as V1's `sb_suite_sso.verify_credit_call`:
   a short-lived token carrying `email`, `suite: "motion"` and the payload).
3. `POST {STREET_BANKER_URL}/api/vault/from-motion` with
   `{"token": "<signed>"}` where the signed payload is the step 1 response.
4. Shows the artist V1's answer: "Saved to your Vault as ..." or the error.

Motion stores nothing about the result beyond a log line. If V1 is down the
artist still has the download button.

## What V1 does with it (the receiving stub, flag OFF)

`POST /api/vault/from-motion` exists in `app.py` behind
`MOTION_HANDOFF_ENABLED` (name in `rollout_config.MOTION_HANDOFF_FLAG`).

- Flag unset: 404, like any address that does not exist.
- Flag set: 501 with a sentence pointing here. Nothing is fetched or stored.

When Motion has step 1 and 2, the endpoint becomes:

1. Verify the token with `sb_suite_sso.verify_credit_call` (same secret,
   same expiry, `suite == "motion"`). Unsigned or expired: 401.
2. Look the account up by the token's email. Unknown or shut: 404 / 403.
3. Refuse anything but `https://` on the Motion host from
   `sb_suite_sso.suite_base("motion")`. Refuse `bytes` over the app's
   upload ceiling (`MAX_CONTENT_LENGTH`) before fetching.
4. Fetch the URL once, stream to the Vault store the way `/vault/upload`
   writes (blob_store when configured, else the instance disk), check the
   `sha256` when given, and record the file with `source: motion` and the
   `source` ids so the Vault card can say where it came from.
5. Answer `{"ok": true, "file_id": ..., "path": ...}`; the Rollout plan's
   asset picker then lists it like any other Vault file.

No network calls in tests; the fetch is one injectable function.

## What this does not promise

- Nothing in V1 edits video or generates images. The Cover Studio makes
  square cover art (OpenAI's gpt-image-1 when OPENAI_API_KEY is set,
  Pollinations without it) and is labelled as cover art.
- Motion's per-account workspaces are not done (see the demo-account gate
  in `suite_go`), so the button in step 2 waits on that too.
- "Artist profile" placement is a Vault question: once a file is in the
  Vault it is attachable wherever the Vault is, and that is the whole of
  what "pull it into your artist profile" means today.

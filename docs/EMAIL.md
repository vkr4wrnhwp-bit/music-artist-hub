# Email — sending, replies, receiving

One mailer, `email_provider.py`, over Resend. Everything the app sends
goes through `send()`; the statement drop-box receives through the
`/webhooks/resend` route. This is the operating record: what is set, what
each email is for, and the rules that keep replies landing with a person.

## The sender

`EMAIL_FROM` — `Street Banker <advance@mail.artiswarrecords.com>` on
production since 2 September 2026, on a domain verified in the
team.summitarts Resend account with a Full-access key from the same
account. `using_shared_test_sender()` is the honesty check: while
`EMAIL_FROM` is unset the sender is `onboarding@resend.dev`, which only
delivers to the account owner, and every send-heavy surface (advances,
tour invites, critical tour alerts) refuses rather than pretend.

Two faults found the day the first real email went out, both fixed:

- The send call carried Python's default User-Agent and Cloudflare, in
  front of `api.resend.com`, refused it with `403 error code: 1010` before
  Resend saw it. Every send from this app had failed that way, silently.
  `_http()` now identifies itself.
- A failed send recorded nothing but "failed". `send()` keeps the vendor's
  response text (`last_send_error()`), and surfaces that record it.

## Replies go to a person

The From address is a machine's. Any email that a human might answer
carries `reply_to` set to the human behind it. The rule applied on 2
September, per call site:

| Email | Reply-to |
| --- | --- |
| Advance packet (single and bulk) | the sender's account email |
| Legacy hub advance (`POST /tour/<id>/send-advance`, kept for old forms; nothing links to it since the hub folded into TOUR) | the artist |
| Tour team invite | the person who invited |
| Street Banker team invite | the person who invited |
| Roster invite | the label account |
| Signature request (lockbox) | the person asking for the signature |
| Fan club access link and members-only drop | the artist |
| Release-day fan email | the artist who owns the campaign |
| Marketplace application to a collab request | the applicant's contact address |
| Team-Up Board reply notification | the person who replied |
| Press pitch | the account sending the pitch |

No reply-to, on purpose: password reset, demo access, drop-box self-test,
Team-Up renewal and watch alerts, critical tour-change alerts. Nobody
should answer those; the link in them is the action.

## Receiving: the statement drop-box

`RESEND_INBOUND_DOMAIN` + `RESEND_WEBHOOK_SECRET` switch it on. Each
account gets `<ingest token>@<inbound domain>`; a distributor statement
emailed there arrives as an `email.received` webhook, signature-checked
(Svix headers), the CSV attachments fetched through Resend's receiving
API with the same key, and parsed into Statements.

Rebuilt on the team.summitarts account, 2 September 2026. Resend gives
every account a managed receiving subdomain, so no DNS is needed: this
account's is **uldainelob.resend.app** (Resend → Emails → Receiving shows
it as `<anything>@uldainelob.resend.app`). Drop-box addresses are
therefore `<ingest token>@uldainelob.resend.app`.

Done:

1. Webhook created in Resend → Webhooks:
   `https://street-banker.onrender.com/webhooks/resend`, event
   `email.received`, status Enabled.
2. Render: `RESEND_INBOUND_DOMAIN=uldainelob.resend.app`, saved and
   deployed.

Still needed (the secret must be pasted by the account owner; nobody else
should handle it):

3. Resend → Webhooks → that endpoint → reveal the **signing secret**, and
   paste it into Render as `RESEND_WEBHOOK_SECRET`, replacing the value
   left over from the old account. Save, rebuild, deploy.
4. Prove it: Statements → drop-box self-test emails a sample CSV to your
   own drop-box address and it should appear as a statement within a
   minute. `/mail/diag` reports the shape if it does not.

A custom address (`statements@mail.artiswarrecords.com`) is possible by
adding the MX record Resend shows under a verified domain's Records tab,
but the managed subdomain needs no DNS and does not depend on a domain
being retired.

Drop-box addresses change with the domain; anyone who was emailing an
older address needs the new one from the Statements page.


## Object storage (R2), and how to see why it is off

`/storage/diag` (any signed-in account) writes, reads and deletes one tiny
object and, when that fails, names the variable that is wrong by SHAPE —
never by value. As of 2 September 2026 it reports a secret of 32
characters where R2 wants 64 hex, and a bucket holding a 32-hex id rather
than a name, so uploads stay on the Render disk.

To fix, in Cloudflare → R2:

1. **Manage R2 API Tokens → Create API token**, Object Read & Write. It
   shows an Access Key ID (32 hex) and a Secret Access Key (64 hex) once.
2. Note the **bucket name** as typed when it was created, and the
   **account id** (the 32 hex in the S3 endpoint
   `https://<account id>.r2.cloudflarestorage.com`).
3. In Render, set `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`
   and `R2_ACCOUNT_ID` to those four, save, rebuild and deploy.
4. Open `/storage/diag`; `"ok": true` means the round trip worked.

Until then nothing is lost: uploads fall back to the Render disk, which is
1 GB and shared with the database, which is why Studio caps upload size.

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
| Tour Hub advance (`/tour/<id>/send-advance`) | the artist |
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

As of the sending switch-over the inbound domain (`…resend.app`) and the
webhook secret still belong to the *other* Resend account, so deliveries
arrive but the attachment fetch fails with the new key. Rebuild on the
team.summitarts account:

1. Resend → Domains → `mail.artiswarrecords.com` → Enable Receiving; add
   the MX record it shows (`mail` → `inbound-smtp.us-east-1.amazonaws.com`)
   in Shopify DNS, where the domain is managed.
2. Resend → Webhooks → Add: `https://street-banker.onrender.com/webhooks/resend`,
   event `email.received`. Copy its signing secret.
3. Render: `RESEND_INBOUND_DOMAIN=mail.artiswarrecords.com`,
   `RESEND_WEBHOOK_SECRET=<the secret>`. Save, redeploy.
4. Prove it: Statements → drop-box self-test emails a sample CSV to your
   own address and it should appear as a statement within a minute.

Drop-box addresses change with the domain; anyone who was emailing the
old address needs the new one from the Statements page.

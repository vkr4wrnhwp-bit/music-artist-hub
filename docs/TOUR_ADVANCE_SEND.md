# TOUR — sending the advance

`/tours/<t>/shows/<s>?tab=send`. The tour module had the advance
checklist, the files, the share links and an inbox for the venue's reply.
It did not have the act itself: one email to the venue with the times, the
bill, what we bring, what we still need, the rider and the stage plot. This
is that.

## What the email is made of

Every line traces to a row. Nothing is typed twice and nothing is invented.

| Section | Source |
| --- | --- |
| Greeting | The name typed into the advance's *Venue contact* item, first word only |
| The show | `tour_shows` date, venue, city; the venue's address if attached; the lineup in running order with set times; capacity and ticket link if set |
| Times we are working to | `tour_schedule` rows for the show — call, load-in, soundcheck, doors, support, set, curfew, bus call. `approx` reads "about", `tbd` reads "TBD" |
| What we have confirmed | Advance items with status *complete* and a value, in the general / production / artist / business categories |
| What we still need | Advance items *incomplete* or *waiting* in those categories, each phrased as the question a tour manager asks (`tour_advance_mail.QUESTIONS`) |
| Guest list | `guest_allocation` and `guest_cutoff` when set |
| Attached | The names of what went with it |
| Links | The Tour Hub's public tech-rider page and a production-scope share link, both minted on first send and reused after |
| Sign-off | The sender's name, the tour manager's role and phone (phone only if not marked private), the account's email — which is also the reply-to |

**Money never.** Guarantee, backend, deposits, settlement — none of it is
read by the composer, and `test_the_email_confirms_what_it_has_and_asks_what_it_lacks`
holds the line. Travel and VIP items are ours, not the venue's, and are
never asked.

The text is editable before it goes. What is sent is what was in the box.

## Attachments

Ticked by default: the stage plot image, the generated input list, and any
file on the show or the tour in the *rider*, *tech pack* or *stage plot*
categories. Also offered: *production* files. Never offered: money files.

- **Stage plot (PNG)** — the designer at `/stage-plot` draws in the browser
  and this server has no renderer, so the page's new **Save for advances**
  button rasterises the SVG and posts it to `/stage-plot/image`
  (`plot_images.py`, one per artist, bucket or private directory). Until it
  is pressed once, the tab says so and offers the link.
- **Input list (text)** — from the saved plot, by `tour_advance_mail.channel_list()`,
  which mirrors `stageplot.js`'s catalogue; a test diffs the two.
- Files are read back from the bucket or the tour directory and sent inline
  (base64, Resend's attachment shape). Together they are capped at 18 MB;
  anything left out is named on the confirmation and is still reachable
  through the production link.

## Sending

`POST /tours/<t>/shows/<s>/advance/send`, scope *advance* or *edit*. Refuses
before sending when the To address is not an address (`fail=to`) or when
the deployment's sender is Resend's shared test address (`fail=sender`),
because that sender only delivers to the account owner — a "sent" that
nobody received is the one lie this must not tell. The button is disabled
with the reason on the tab in that state.

Each send, successful or not, is a `tour_advance_sends` row (to, cc,
subject, the body as sent, the attachment names, the links) and an
activity-log entry. The tab lists them.

## The loop

The venue replies to the sender's address. Paste the reply into the
**Advance inbox** tab; the extractor proposes entries and the checklist
fills in. Send again when something changes: the links are reused, the
email says what is confirmed now.

## What it needs on the deployment

`EMAIL_FROM` set to an address on a domain verified in Resend. As of 2
September 2026 production has `RESEND_API_KEY` but no `EMAIL_FROM`, so the
sender is `onboarding@resend.dev` and the tab reports that plainly. The
Resend key on the account is restricted to sending, so `/mail/diag` cannot
list the domain's DNS records; verify the domain in the Resend dashboard,
then set the variable.

## Files

| File | Role |
| --- | --- |
| `tour_advance_mail.py` | The composer, the questions, the recipient finder, the input-list mirror. No I/O. |
| `plot_images.py` | Keeps the rendered plot for attaching. |
| `tour_os.py` | `_send_context`, `_build_attachments`, the route, the tab. |
| `templates/tour/show/_send.html` | The tab. |
| `tests/test_tour_advance_send.py` | 11 tests. |

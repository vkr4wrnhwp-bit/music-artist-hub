# Room audit — feature by feature

Owner, 2026-09-18: *"if i ask you what every feature in a room does one at
a time can you audit it and check against yourself?"* and *"keep a note pad
of what we discuss right now on the changes you and i find"*.

This is that notepad. One entry per feature, written as it is checked.

**Why it exists.** On 2026-09-18 three things I had reported as done turned
out not to be: the Artist Twin's moving shadows (the section had no ghost
elements at all), the Rack photoreal rebuild (approved, plates gathered,
never started), and a mockup I published three times without ever being
able to see it. The correction is to verify each claim against the code
rather than assert it, and to write down what is found.

**What each entry records**

| Field | Meaning |
|---|---|
| Claims | The label, button or copy the page shows |
| Does | What the code actually does, with `file:line` |
| Data | Real / provider / sample / none |
| Reach | Which plans, and whether the route enforces it or only hides a button |
| Verdict | works · overclaims · empty · not built |

**Verdicts are about the claim, not the ambition.** A feature that does
less than its label says is an overclaim even when the code is good.

---

## Room: Fans

*"The people who follow you and what they get."* Six cards:
Fans, Fan CRM, Fan Club, Discover, Collab Marketplace, Apparel & Merch.

### 1. Fans — `/fans`

- **Claims:** "Your fans, your CRM, your club."
- **Does:** [app.py:10030](../app.py). Branches on who is asking. A demo
  session or a signed-out visitor gets `get_fan_dashboard_data()`, the
  showcase set, explicitly stamped `is_real = False`. A real account gets
  `fan_dashboard.fan_dashboard_for(user["id"])`, which reads
  `mls.list_fans(user_id)` — the fans captured by smart links — and builds
  segments from the intent scorer's own bands.
- **Data:** Real for a real account. Segments are the true distribution of
  `intent_level`, a band nobody is in is dropped rather than shown as 0
  ([fan_dashboard.py:107](../fan_dashboard.py)), averages are over real
  counters, and there is deliberately no money figure "because there is
  none". With no fans it returns a written empty state naming how fans
  arrive, not a zero.
- **Reach:** Signed-in. Owner-only extra: the Shopify customer import
  (`_shopify_import_allowed`).
- **Verdict:** **works for a real account, OVERCLAIMS in the demo.**
  The owner audited this signed in as the demo account with Label access —
  the account he shows partners — which takes the showcase branch.

  **F-1. The disclosure comes after the claim.** The showcase shows
  Superfans 1,240, Total Fans 50,840 and Avg. Fan LTV $9.40 in 2xl bold at
  the top; the line calling them invented ("Illustrative example figures,
  not anybody's fans") is at the BOTTOM of the page in the smallest type on
  it (`text-xs text-gray-300`). The subtitle under the heading is marketing
  copy, not a disclosure. A label that arrives after the number has been
  read is a footnote, not a label.

  **F-2. The demo advertises a metric the product refuses to produce.**
  The real branch of this same template carries the comment: "there is
  deliberately no lifetime value, spend, or leaderboard-by-amount: ml_fans
  has no spend column and the app has no purchase feed ... A fan-value
  number an artist might act on is not a thing to guess at." The showcase
  branch then shows **Avg. Fan LTV $9.40**. Anyone sold on that tile will
  never get it. This is the sharper of the two: F-1 is presentation, F-2 is
  a promise the product cannot keep.

  Mechanism note: `fans` is in `hubs.LIVE_KEYS`, so the sidebar never badges
  it "example data, not yours" — right for a real account, but it means the
  demo has no badge either and the footnote is the only signal.

  The 2026 fix that removed the invented figures was only half-applied: it
  cleaned the real-account path and left the demo path as it was.

**Method, from here on (the owner's, 2026-09-18):** *"I logged in through
this account acting like a customer seeing where the flaws are at."* He made
a real account, `demos.streetbankermusic@gmail.com`, and granted it Label.
It is NOT `demo@streetbanker.io`, so it takes the real branch everywhere and
shows genuine day-one empty states. This is the right way to audit and the
showcase accounts hide exactly this class of defect, because they are
pre-filled. Walk every room as a brand new paying customer.

### 2. Fan CRM — `/links/fans`

- **Day one:** an empty list, and an **Export CSV** button.
- **Verdict:** **works, but lopsided.** You can export nothing and cannot
  import anything (F-3). Export without import on an empty page is the
  asymmetry that makes the missing import obvious.

### 3. Fan Club — `/fan-club`

- **Day one:** the club editor itself — Your club, Members-Only Drops,
  **Save Club**, **Post Drop**.
- **Verdict:** **works.** The one page in this room a new customer can use
  on the first day without needing anything to exist first. Not badged
  live (`fan-club` is not in `LIVE_KEYS`) and does not need to be: what it
  shows is the account's own club.

### 4. Discover (Fans) — `/discover`

- **Claims:** "Find artists to follow and support."
- **Does:** [app.py:9819](../app.py) reads `get_discover_data()` from
  [discover_config.py](../discover_config.py), a hand-written `_TRACKS`
  list. Real iTunes search is wired in on top, but only when the visitor
  types a query.
- **Data:** **Invented, and unlabelled.** "Midnight Drive" by Nova Reign,
  5,200,000 plays. "Neon Dreams", 3,100,000. The module's own docstring
  says "play counts and cover gradients are illustrative". The template
  says nothing: `discover.html` has no match for sample, example,
  illustrative or demonstration.
- **Verdict:** **OVERCLAIMS — F-5.** And the badge mechanism points the
  wrong way: `discover` IS in `hubs.LIVE_KEYS`, so the sidebar deliberately
  does not badge it Sample, while Collab Marketplace — equally invented —
  is not in LIVE_KEYS and is badged Sample honestly. Two fake pages in one
  room, one labelled, one flagged live.
- This is the same defect that was already found and fixed on `/fans`,
  one page over.

### 5. Collab Marketplace — `/marketplace`

- **Day one:** Open Requests, filters by kind (For Bid / Royalty Split /
  For Fun), **Post request** works.
- **Verdict:** **honest.** Badged **Sample** in the nav because
  `marketplace` is not in `LIVE_KEYS`. The listings are illustrative and
  the product says so. This is the pattern Discover should follow.

### 6. Apparel & Merch — `/apparel`

*Parked: the owner is switching this card off in Settings > Pages until
the Artifacts suite has a page of its own. Audit it when it moves there.*

---

## Changes this audit found

| # | Where | Finding | Fix | State |
|---|---|---|---|---|
| F-1 | `/fans` showcase | "Illustrative example figures" sits last and smallest, under figures shown in 2xl bold | Move the disclosure ABOVE the tiles and make it a visible band, not 12px grey | proposed |
| F-2 | `/fans` showcase | Shows **Avg. Fan LTV $9.40**, a number the real product deliberately will not compute | Drop the LTV tile from the showcase, or replace it with a metric the product actually produces | proposed |
| F-3 | `/fans`, `/links/fans` | **No way to import fans.** `fan_list_import` is referenced NOWHERE in app.py - no route, no button, no import. Built, tested (12 tests), committed 2026-09-18, never wired. The only import control left is the Shopify one, now owner-only via `_shopify_import_allowed`, so every non-owner lost the capability entirely | Wire `fan_list_import` to a route and put the upload control on both pages | **confirmed, unfixed** |

| F-4 | `/links/fans` | **Export CSV** offered beside an empty list, with no way to import | Ships with F-3 | proposed |
| F-5 | `/discover` | Curated fake catalogue (Nova Reign, 5.2M plays) shown to paying customers with **no label anywhere**; `discover` is in `LIVE_KEYS` so the sidebar will not badge it Sample, while the equally-invented Marketplace is badged honestly | Either badge it Sample (take it out of `LIVE_KEYS`) or label the illustrative figures in the page, as `/fans` does | **confirmed, unfixed** |

**F-3 is the fourth instance today of the same failure**: engine built and
tested, control never connected. The others were the Artist Twin's ghosts,
the Rack rebuild, and the ElevenLabs plates. Before reporting anything as
delivered, check that a person can reach it from the UI - `grep` the module
name in app.py and the templates, not just its own test file.

**Correction logged 2026-09-18:** I told the owner he was looking at 1,240
superfans and $9.40 LTV, reading it off the code branch. He replied "i see
no fans". I asserted the contents of his screen instead of asking. F-1 and
F-2 are real as written in the template, but whether he was SEEING them is
unconfirmed, and if a Label demo account is taking the real branch instead
of the showcase that is a separate and larger bug.

Neither is applied. The full test suite was running when they were found,
and V1 is never edited mid-gate.


---

## Owner's directions from the Fans walk (2026-09-18)

Four calls, in his words, with what each actually needs.

### D-1. One screen for Fans, Fan CRM and Fan Club
*"i almost think everything in fans besides collab and discover can be in
one screen"*

The audit supports this. Three rooms hold one concept: the CRM is the list,
the dashboard is segments computed from that same list, and the club is
what you sell to the people on it. Two of the three are empty shells on day
one. Merging gives a new customer one page that says: here are your fans,
here is how they group, here is your club — and one obvious way to fill it.
Collab Marketplace and Discover stay separate: they are about other people,
not your audience.

### D-2. Discover: real artists, opted in
*"discover is all fake artists so this needs to be imported via soundcharts
or something then a toggle the artists can switch on to be discovered in
that area maybe??"*

Fixes F-5 properly rather than just labelling it. Two halves, and the
second is the important one: a provider import (Soundcharts is already
wired and authenticating — see [[street-banker-provider-wave]]), and an
artist-facing switch reading roughly "list me in Discover". Being listed
somewhere public is a consent decision, so it is off until the artist turns
it on, the same rule the fan import follows. Until real artists opt in the
page is thin, which is honest and is the point.

### D-3. Collab Marketplace: drop the Sample badge by making it real
*"collab marketplace is still marked sample this needs to be removed and
working"*

Note the order: the badge is honest TODAY because the listings are seeded.
Removing the badge without removing the seed data turns an honest page into
F-5. So: delete the seeded requests, let real posts populate it (Post
request already works), then take `marketplace` out of the sample set. It
will be empty until people post, which is the chicken-and-egg partner week
may solve.

### D-4. Fan import: authorize, upload, then work the list
*"the import fans data needs to have a i authorize button and a upload
button then show the fans. they should be sorted by region and allowed to
be mass clicked on in regions or select all for tour blasts i think??"*

The staged fix (F-3) already has the authorize checkbox, the upload button
and a result summary. What it does NOT have, and what he is asking for:

  show the fans after the import, on the same screen
  group them by region
  select a region, or select all, and act on the selection
  the action being a tour blast

**The open question is where region comes from.** A Mailchimp or Klaviyo
export may carry country/city columns; a bare email list carries nothing.
Region must be read from the file where it exists and left blank where it
does not — never inferred from an email domain or guessed. A fan whose
region is unknown belongs in an "Unknown" group that can still be selected,
not quietly dropped from every region.

**Suggested order:** D-4 completes F-3 and is the thing a paying customer
needs on day one. D-1 is the IA change that makes D-4's screen the obvious
home. D-3 is small once the decision is made. D-2 is the largest and needs
a provider budget conversation first.


---

## Outside review of the Fans section (owner-supplied, 2026-09-18)

A full product review arrived proposing a **Fan Operating System**: capture
-> understand -> segment -> activate -> monetize -> community -> measure.
Persistent nav (Overview, Audience, Segments, Journeys, Fan Club,
Community, Insights), Artist vs Label modes, a command centre in place of
the launcher, fan profiles, journeys, a guided Fan Club builder, a split of
Discover into artist and fan experiences, and a full Collab lifecycle.

**Where it agrees with this audit, independently:** merge Fans and Fan CRM;
empty states must offer a path; sample vs live must be unmistakable; the
Marketplace Sample label contradicts its real-requests language.

**Three code-level facts that change the plan.**

1. ~~**There is no messaging layer. At all.**~~ **WRONG, corrected
   2026-09-18 by the owner: "we have resend man" and "the tour section we
   literally have advance emails in it".** Both true, and both checkable in
   seconds, which is the lesson.

   What is actually there: `email_provider.py` IS Resend, imported as
   `emailer` at app.py:225 - my grep for `emailer.py` missed the alias. And
   the Tour advance packet is a REAL sending feature: `tour_advance_mail.py`
   composes it with no I/O, tour_os.py:2299 sends it with permissions,
   attachments and minted share tokens, through that same mailer. V1 emails
   people outside the building today.

   So the fan send is much smaller than I claimed. What is genuinely
   missing, and only this:

     batching and rate limiting      advance sends one email to one venue
     an unsubscribe link and header  REACH has the pattern (reach/compliance.py)
     bounce/complaint -> suppression REACH has it (reach/outcomes.py); the
                                     sink already exists here as
                                     links_store.suppress_fan

   The architecture to copy is the advance's: compose stays pure and
   testable, I/O and permissions live in the route. Do NOT extend
   tour_advance_mail itself - tour_hub_rules.py:6 says not to build new
   features on it.

2. **The Marketplace contradiction resolves the other way.** The review
   assumes the listings are sample and the language is wrong. In fact
   `collab_requests` is a real table written only by the Post request
   route; nothing seeds it; a fresh database has zero rows. The listings
   are real and the BADGE is wrong. Fix: add `marketplace` to
   `hubs.LIVE_KEYS`. One line.

3. **Lifetime value is in the fan-profile spec and the product refuses to
   compute it** (F-2). No spend column, no purchase feed. It needs a
   purchase-feed decision before it is a build item, or it becomes F-2
   again under a new name.

**Already built against this, 2026-09-18:** `fan_segments.py` + 15 tests -
regions (Unknown selectable, never dropped), tour overlap in both
directions (where to play, not only who to tell), consent-age buckets (an
unreadable date is unknown, not new), suppression keyed by reason, and
`first_send` (who has never been scored). That is the review's Segments
item, standing. `ml_fans` gained country, city, suppressed, suppressed_at;
`fan_list_import` now reads country/city columns where the export carries
them and leaves them blank where it does not.

**Sequencing view (mine, differs from the review's):** merge Fans + Fan CRM
into Audience FIRST - cheap, and everything else hangs off it. THEN a
sender. THEN Journeys. The review puts Journeys in "Next" alongside
segments; without a sender that ordering produces dead UI.

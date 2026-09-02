# TOUR — the date page (Phase 1)

`/tours/<t>/shows/<s>`. One date, one page. Built after the owner said:
"a lot of the tabs can be located inside the actual date and the event,
you can add a plus sign next to hotels and vip etc, they can add them if
they want to, these pages are overwhelming."

## The section model

Defined in `tour_os.py` next to `SHOW_TABS` (which is untouched: it is
still the deep-link vocabulary).

**Core — always on the page, in this order**

| Key | Title | Body |
| --- | --- | --- |
| `times` | Times | `tour/show/_schedule.html` (the bill + line checks, the timeline, the add form) |
| `advance` | Advance | `tour/date/_advance.html`: the meter, the six checklist categories as `<details>` (General open, the rest folded, each with its count), then three folded sub-disclosures — **Paste an advance email** (`_inbox.html`, id `inbox`), **Send advance** (`_send.html`, id `send`), **Production pack & files** (`_production.html`, id `production`). The header's primary **Send advance** button opens and scrolls to the send disclosure. |
| `venue` | Venue & contacts | `tour/date/_venue.html`: `_venue.html` + the people table (`_people.html`, id `people`) |
| `deal` | Deal | `tour/show/_money.html`: the Deal field group up front; Night-of, Settlement and the expense ledger inside a `<details id="settlement">` that is open only when the Settlement section is on. One form, every money field still posted. Financials scope only. |
| `notes` | Notes | `_notes.html` |
| `activity` | Activity | `_activity.html`, collapsed by default, last on the page |

**Optional — a `+` chip until added**

| Key | Chip | Readiness categories it owns | Add scope |
| --- | --- | --- | --- |
| `hotel` | + Hotel | hotel | hotel |
| `travel` | + Travel | travel, ground | travel |
| `guests` | + Guest list | guest_list | guests |
| `vip` | + VIP | vip | vip |
| `settlement` | + Settlement | settlement | financials |
| `merch` | + Merch counts | — | merch |
| `marketing` | + Marketing | marketing | marketing |
| `content` | + Content plan | content | content |
| `setlist` | + Set list | — | production |
| `files` | + Files | — | files |
| `tasks` | + Tasks | — | schedule |

`edit` may add any of them. Viewing a section needs the scope its old tab
needed (`TAB_SCOPE`, plus `deal`/`settlement` → financials); a viewer
without the scope sees neither the section nor its chip.

An optional section is **shown** when any of these holds:

1. it is in the show's opted list (`tour_show_ext.readiness_config`,
   a JSON list of section keys, written only by `/sections`);
2. it has rows on this date — lodging, travel legs (attached or on the
   date), guests, VIP records, any night-of/settlement field or a logged
   expense, any marketing value or ticket field, a content row that has
   been assigned/dated/filed/moved off `planned`, merch counts, set lists,
   files the viewer may see, tasks;
3. the request's `?tab=` names it — a deep link is intent, and looking
   is not adding (the opted list is not written).

Otherwise its chip sits in the **Add to this date** row, which comes after
the core sections and before Activity. Each chip is a tiny POST form.

An added-but-empty section is one line tall: its form sits inside a
`<details class="to-add">` ("Add a hotel", "Add a VIP package"…), opened
only when the section is the deep-link target or an edit is in progress.
Hotel and travel edit links from the date page go to
`?tab=hotel&edit=<id>` / `?tab=travel&edit=<id>`; the show route hands the
row to the shared `_hotel_form` / `_travel_form` partials the way
`/hotels?edit=` and `/travel?edit=` do, and Cancel returns to the date.

## The plus, and the minus

`POST /tours/<t>/shows/<s>/sections` with `key` and `action=add|remove`.
Needs `edit` or the section's own add scope, and the section's view
scope. `add` appends the key to `readiness_config`, logs a `sections`
change row on the show, and redirects to `?tab=<key>`. `remove` is
offered in the UI only when the section has no rows, and the route
refuses it (redirects, no change) when rows exist: the rows would keep
the section on the page anyway, and its categories would keep counting.

## The readiness translation

`tour_engine.show_readiness` is unchanged: it scores every category in
`config`, or all 17 when `config` is `None`. What changed is what
`tour_os._readiness_for` passes as `config`:

    effective = CORE_CATEGORIES
              + categories of every opted optional section
              + categories of every optional section that has rows

`CORE_CATEGORIES` = confirmation, contract, deposit, venue, promoter,
advance, production, catering, hospitality. So a fresh show is scored out
of 8 (deposit is not applicable until one is required), not 17; adding
Hotel makes it 9, an unmet hotel; one ground leg brings travel and ground
without anybody opting in. Existing shows with an empty
`readiness_config` behave as before *except* that optional categories
with no rows and no opt-in stop counting against them — that is the
point. The same translation feeds Tour Home, the shows list, the calendar
and Ask Tour, because they all call `_readiness_for`.

The page shows the score as "n of m applicable" with the next three gaps
as text; the full checklist is a `<details>`.

## The deep-link rule

`?tab=<key>` is accepted for every `SHOW_TABS` key and every section key.
The page always renders in full; `tab` names the element that gets
`open` (and its `<details>` ancestors), the `is-target` outline on its
section, and a scroll on load (`open_target` → a small inline script;
no JS still lands on an open section). Old tab keys map to their new
home through `TAB_SECTION`: `schedule`→times, `inbox`/`send`/
`production`→advance, `people`→venue, `money`→deal; every other key is
its own section id. The scope check is the old one (`TAB_SCOPE`, plus
`deal`/`settlement`→financials) and still answers 403. `?tab=overview`
and no tab are the page as designed. Prev/next keep `?tab=`. The service
worker (`sb-v166`) caches by full URL, query included, as before.

## Tests

`tests/test_tour_date_page.py`: the six core sections in order and the
eleven chips on a fresh show; add → section on, chip off, key stored,
change logged; deep links open un-added sections and old sub-tab ids;
remove refused while rows exist; readiness 8 → 9 → 11; a member without
financials sees no Deal and no Settlement chip, a viewer gets no chips;
all 21 old tab URLs answer 200 and land on their element; the asset
versions moved.

`tests/test_tour_advance_send.py` judges the invoice on the attachment
checklist rather than the whole page, because the owner's Files section
now lists it further down.

## Notes from the first render

- The disclosures are `.to-fold` (`-title`, `-note`, `-body`); `.to-sub`
  was already the muted paragraph with a 70ch reading measure, and reusing
  it squeezed every fold to 506px.
- `main:has(> .to) { min-width: 0 }` in `tour-os.css`: the shell's `<main>`
  is a flex item with `min-width: auto`, so the 24-link tour bar's
  min-content width pushed every tour page (the old tabs too) past the
  viewport. Phase 2 removes the cause; this removes the symptom.
- `.to-empty a.to-btn` keeps ink-on-gold: the empty-state link colour was
  painting the button label amber on amber.
- The Deal cards read `—` with "no merch gross entered" / "none entered"
  instead of `0` when the merch gross, the expense fields and the ledger
  are all blank (honesty rule: money never reads zero for nothing typed).
- The schedule's nine-field add form folds behind "Add an item", and
  "Copy from" only renders when there is another date to copy from — on
  a fresh date the first move is the standard day.

## Still owed

**Phase 2 — the tour bar.** `templates/tour/_shell.html` still renders
the 24-link tour bar above every page, including this one. Fold it the
same way: a few core destinations (Home, Dates, My Day, Team) and the rest
behind a `+`/More, with every `TOUR_TABS` path still answering.

**Phase 3 — Tour Hub fold-in.** Shipped; see "Phase 3: one product"
below.

Also open: the tour-level `/hotels` and `/travel` pages still carry their
own add forms (the date page reuses them, it does not replace them);
`_overview.html` is no longer rendered anywhere and can go once nothing
links to it; and the section status lines are computed in
`tour_os._section_status` — if they grow, they belong in `tour_engine`.


## Phase 2: the tour bar (shipped)

The tour-level bar in `templates/tour/_shell.html` now carries seven
entries: Home, Dates (the Shows page), Crew (the People page), Travel &
hotels, Money, Files, and More. `tour_os._tour_bar(viewer, nav)` builds it
from `PRIMARY_TABS`, `BAR_LABELS`, `BAR_GROUPS` and `MORE_ORDER`, filtered
by the same scopes as before. Hotels and Route sit under Travel & hotels
and get a sub-row (`.to-subnav`) on those three pages. Everything else (My
Day, Calendar, Schedule, Venues, Guests, Merch, Marketing, Content, Tasks,
What changed, Ask Tour, Import, Exports, Share links, Team, Settings) lives
in the More menu, a `<details>` that needs no script; when the active page
is in More, the button takes that page's label. `TOUR_TABS`, every route,
path and scope are unchanged; `tests/test_tour_bar.py` pins the bar.


## Phase 3: one product (shipped)

There is one tour product, TOUR at `/tours`. The Tour Hub at `/tour` is
folded into it; nothing a show carried was lost and nothing in the wild
broke.

**What moved.**

- The pipeline. The Dates page (`templates/tour/shows.html`) carries the
  hub's line above the table - "Every show, one pipeline: hold → confirmed
  → advanced → played → settled. Keep the status honest and nothing falls
  through the cracks on show day." - a status `<select>` on every row for
  anyone with `edit` or `advance` (posting to the existing
  `/tours/<t>/shows/<s>/ext`, which rejects anything outside the five;
  the select submits itself on change and the Update button stays as the
  no-script fallback), and the legend beneath the table, word for word:
  "Statuses, honestly: hold = penciled in, confirmed = date locked,
  advanced = venue has your plot and details, played = done, settled = you
  got paid." Everyone else reads the status as a chip.
- The statuses themselves. `tour_store.SHOW_STATUSES` is the one
  definition; `tour_os` (vocab, the `/ext` guard, the importer's
  forward-only order) and `app.py` (the legacy POST routes) read it.
- The Tour P&L. TOUR's Money page (`/tours/<t>/money`) already summed the
  money entered per show; it now carries a "Settled" line - the
  settlement amounts of shows marked settled, and how many - "straight
  sums of what you entered, nothing estimated". A settled show with no
  amount is not summed as zero. (`tour_engine.tour_finance` returns
  `settled_total` / `settled_count`.)
- The routing flags. The Route page (`/tours/<t>/map`) flagged
  back-to-back dates already; it now flags "same day" too. Dates alone,
  no drive time guessed.
- The Money Queue's "Settled tour income" reads TOUR first
  (`tour_store.settled_income`: every show of the account marked settled
  on TOUR with an amount) and adds the walk-away of any legacy hub
  settlement sheet on a show that has no TOUR settlement, so a sheet
  saved on the old hub still comes out as the figure it computed. Its
  link is "TOUR →".

**What redirects.** `GET /tour` (and `?view=board`) lands on the newest
tour's Dates page, or on `/tours` when the account owns no tour (the
index offers to bring unattached shows onto one). `GET /tour/<show_id>`
lands on the date page when the show is on a tour, on `/tours` when it is
not, and stays a 404 for anyone else's account - never a redirect that
confirms the id. Every hub POST route (`/tour/add`, `/tour/<id>/status`,
`/delete`, `/advance`, `/settlement`, `/share`, `/send-advance`) answers
exactly as it did, so old forms and bookmarks keep working. The public
`/showday/<token>` and `/rider/<token>` pages are untouched;
`tour_shows.share_token` keeps its meaning and TOUR's `_rider_url` still
reuses it. `templates/tour.html` and `templates/tour_show.html` are gone:
nothing rendered them after the redirects.

**Navigation.** One tour entry: `hubs.py`'s Live Stage Suite lists TOUR
only, `command_center.py` names `/tours`, the Light Studio rail lost the
hub icon, and the money tab's "Classic settlement sheet" link is retired
(the Settlement summary print view stays). `tests/test_tour_fold.py`
pins all of it; the seven `tests/test_app.py` hub tests were rewritten
to the folded behaviour rather than dropped.

**Still owed.** The hub's 15-field advance form (`touring.ADVANCE_FIELDS`)
and its rule-built email (`touring.advance_email`) are not surfaced
anywhere now; TOUR's Advance section and `tour_advance_mail` are the live
composer. `touring.py` stays for the Money Queue fallback and the public
pages. A 15-field core view of Advance on the date page is future work.

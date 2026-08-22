# TOUR — reading a real routing sheet

The TOUR module already handled shows, advance, travel, hotels, money and
day sheets. This document covers the pass built against an actual van
run (DEVORA on PRAYERS' *No Tengo Calma* 2026): the shapes a routing
sheet arrives in, the four things a van tour needs that had no home, and
sharing the run with the band.

## The importer had to meet the paperwork where it is

Three sources for one tour, in three different shapes, none of which the
importer could read:

| Shape | Example | What broke |
|---|---|---|
| Two-digit year | `10/14/26` | `_PASTE_RE` required four digits — every line failed "no date at the start" |
| Tab columns | `10/14/26⇥Iowa City, IA⇥Gabe's` | Split on pipes and dashes only, so the venue ended up inside the city |
| Month, no year | `October 14 - Wednesday - ...` | A routing email never writes the year |
| Ticket links | `Ticket Link: https://…` on its own line | Read as a row with no date |
| Deal sheet | TSV with a header row | `csv.DictReader` assumed commas — and a merch rate of `90/10, 100% CD/DVD, Artist Sells` is full of them |

All five now parse. Specifics worth keeping:

- **Two-digit years are windowed** 00–68 → 2000s, 69–99 → 1900s. A tour
  date is never in the 1900s in practice, but guessing forward would turn
  a typo into a booking a year out.
- **A hyphen only separates columns when it has spaces around it.**
  Otherwise `X-Ray Arcade` and `Sold-Out Room` get torn in half.
- **City and venue are told apart by the state suffix**, not by column
  order — because one sheet writes `City - Venue` and the next writes
  `Venue - City`, and both are correct.
- **A weekday beside the date is dropped**; it says nothing the date does
  not, and it was landing in the city field.
- **`Ticket Link:` lines attach to the row above.** `**waiting on link**`
  sets `ticket_pending` rather than storing a URL, and a second link on
  the same date (a separate VIP on-sale) is kept as an extra rather than
  overwriting the first.
- **`OFF`, `START` and `END` live in the CITY column** on a routing grid.
  Read as venue-less shows they became empty dates on the calendar.
- The CSV delimiter is **picked from the header line**, so old comma
  files keep working.

### A bug this pass introduced and the tests caught

The "no separator found" fallback re-split the *raw* line on commas —
which ran after the weekday filter and undid it. `October 20 - Tuesday -
OFF` came back whole and was read as a show at a venue called "OFF".
Every off day on the tour was landing as a phantom show. The fallback now
runs before the filter.

## The importer proposes; it never resolves

Three sources disagreed about the same dates. The importer does not pick
a winner — `source_note` on a show records where a value came from so
nobody re-litigates it later. Real examples from the run:

- One sheet said the city was Milwaukee, two said Cudahy. The venue is in
  Cudahy; Milwaukee is the market.
- Three shows were "2H Challenged" / "3H Challenged" / "1H" on the deal
  sheet while tickets were publicly on sale. The deal sheet was stale.
- One date existed only on the deal sheet and on neither announcement.

Each of those is a person's decision. Silently picking one and moving on
is how a tour manager ends up advancing a show that was cancelled.

## Fuel and mileage

The second-largest line on a van tour after guarantees, and the one
nobody has in a system. `eng.fuel_plan(tour, legs)` is arithmetic over
figures a person entered — no routing service, no distance API, no
guessed miles.

    miles / mpg = gallons
    gallons × price = fuel
    fuel × reserve% = reserve

Three refusals that matter more than the arithmetic:

**A stated estimate is never dressed up as a routed total.** `miles_source`
is `"estimate"` or `"routed"` and every screen says which. One is a number
somebody typed before any address existed; the other is the drive.

**A part-entered route stays an estimate.** If 12 of 35 drives have
mileage, the total is not 12 legs' worth presented as the tour — it keeps
showing the estimate and reports `12 of 35 entered`. A part-filled route
would read as a total and be short by every leg nobody filled in.

**The Route tab's straight-line distances are never used.** That page
computes crow-flight miles between venues with coordinates. A crow-flight
total understates a real drive by roughly a fifth, so fuel reads only
`miles` entered on a *ground* travel leg. The page says so in as many
words, because a fuel figure that quietly did that is worse than none.

A missing assumption comes back in `missing` and every dependent number
stays `None` — never a zero, never a NaN, never a division by zero on a
tour with no shows yet.

Verified against the tour's own document: 9,775 miles at 16 MPG and
$3.75/gal gives 611 gallons and $2,291, which is what the sheet the tour
manager already uses says. If those disagreed, one of them would be wrong
on the road.

## What else a van run needed

- **Support lineup per show** (`support`). A package tour's bill changes
  date to date, so it belongs on the show and not on the tour.
- **Buyout per person** — the number that gets argued about at settlement
  if nobody wrote it down. The label says "per person" for that reason.
- **A VIP advance block** — location, start time, capacity, early-entry
  path, host. A VIP package is sold to the public before anyone has
  confirmed where it happens or how those ticket holders get in early;
  each of these is a question somebody asks on the day otherwise.
- **Fuel stop, tolls, planned departure** on the travel advance, and
  `miles` / `tolls` on the travel leg itself.

### A trap in `list_shows`

That function names its ext columns one by one in the SELECT rather than
using `e.*`. That is a good rule — a column has to be added on purpose —
and it has a cost: a field added to `EXT_FIELDS` and to the table but
missed in the SELECT is **writable and permanently unreadable**.
`update_show_ext` writes it happily and every read returns `None`.

`support` did exactly that. `tests/test_tour_routing.py` now writes every
field in `EXT_FIELDS` and reads them all back, so the next one cannot.

## Sharing the run with the band

Every other share scope is one show handed to one person for one job.
`band` is the only tour-wide scope, because a band member's question is
never "what happens tonight" — it is "where am I on the 14th and what
time does the van leave on the 15th".

**It carries** every date in order, venue and address, the bill for that
night, set and load-in times, drives with departure and pickup, hotel
name and address, off days, and a marker on today.

**It does not carry** guarantees, settlement, merch splits, room
assignments, confirmation numbers, payment details, phone numbers, driver
details, or the guest list. The response is assembled field by field
rather than by stripping a full tour object, so a column added later
cannot quietly start travelling to everyone holding the link. The page
says what is missing and why, so nobody reads it as an oversight.

Revocable and password-protectable like every other share link. A test
asserts each private value is absent from the rendered HTML.

## Endpoints

`POST /tours/<id>/fuel` (mpg, price, reserve %, estimated miles, vehicle)
· the Route tab at `/tours/<id>/map` renders the plan · `band` is a scope
on the existing `POST /tours/<id>/share/new` and renders through
`/tour-share/<token>`.

## Testing note

Do not edit templates or modules while a suite is running. The test
process holds the Python it imported at collection time but reads
templates fresh at render time, so a half-applied change shows up as a
mystery failure — `'fuel' is undefined` on a route whose handler already
passed it, in a file that passes on its own.

And point verification scripts at a throwaway database. The dev DB at
`instance/streetbanker.db` is the one the suite uses.

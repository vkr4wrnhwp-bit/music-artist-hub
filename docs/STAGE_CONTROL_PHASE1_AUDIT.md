# Stage Control — Phase 1: repository and system audit

Answers the audit Phase 1 of [STAGE_CONTROL_BRIEF.md](STAGE_CONTROL_BRIEF.md)
asks for, and records the two findings that change what Phase 2 onward should
build. Written before any Stage Control code existed.

## Stack

| | |
| --- | --- |
| Server | Flask (app factory `create_app()` in `app.py`, ~440 KB, one file) |
| Templates | Jinja2, server-rendered. No SPA, no build step for JS. |
| Database | SQLite via `db.py` (`get_db()`), one file on a Render disk at `/var/data` |
| Client JS | Vanilla, hand-written, no bundler |
| CSS | Tailwind, **build frozen** — see Constraints |
| Deploy | Render, `gunicorn app:app --workers 2 --threads 4 --timeout 180` |
| Auth | Server session cookie; `current_user()` at `app.py:682` |
| Tenancy | `users.partner_id` + `partner_store.py` / `partner_os.py` |

## FINDING 1 — There is no realtime infrastructure, and the deployment cannot host one

`grep` for websocket / socketio / EventSource / `text/event-stream` across the
tree returns **nothing** outside vendored worktrees. The only "realtime" in the
product is `setInterval` polling (`hub_desk.html`, `lights_remote.html`,
`live/perform.html`, `network.html`, `lights.js`).

This is not merely a missing library. **`--workers 2 --threads 4` is 8
concurrent request slots for the whole application.** Server-Sent Events or
long-polling hold a thread for the life of the connection, so nine connected
performers would consume every slot and the site would stop answering — for
every user, not just this module. WebSockets need a different worker class
(gevent/eventlet) and a deploy change.

**Decision for Phase 4:** the Engineer Desk and performer interface use
**short-interval polling against a monotonic event cursor**, not sockets. That
still satisfies the brief's actual realtime requirements — server-generated
event IDs, ordered processing, idempotency, duplicate protection, heartbeats,
presence, explicit stale-state, server timestamps — because those are
properties of the event model, not of the transport. The brief's instruction
is "use the existing realtime infrastructure where suitable"; the honest
reading is that there is none, and inventing one would be a deploy-wide risk
taken for a module nobody is using yet.

Revisit only with a measured need and a worker-class change. Recorded so this
is a decision, not an omission.

## FINDING 2 — Most of "show advancement" already exists in TOUR

TOUR ships **27 tables** and already owns the entities Phase 3 of the brief
describes. Building a second show/venue/crew system would fragment the product
exactly the way Tour Hub did before it was folded into TOUR (Phases 1–4,
`b0737bc`…`03bee74`).

| Brief asks for | Already exists |
| --- | --- |
| Show, date, timezone | `tour_days` + `tour_show_ext` (`tz`, venue, promoter, capacity) |
| Load-in, soundcheck, doors, set, curfew | `SCHEDULE_CATEGORIES` in `tour_schedule` |
| Venue / room | `tour_venues` |
| Assigned crew | `tour_people` (`PEOPLE_CATEGORIES`) |
| Advance + questions | `tour_advance` + `ADVANCE_CATEGORIES` + `ADVANCE_STATUSES` |
| **QR / signed show access** | **`tour_share_links`** — `token` UNIQUE, `revoked`, `expires`, `scope`, `show_id`, `access_count`, `last_access`, `password_hash` |
| Set list | `tour_setlists` / `tour_setlist_items` |
| Stage plot | `stage_plots` / `stage_plot_images` in `db.py` (per user, JSON blob) |

`tour_share_links` already meets the brief's token requirements — opaque,
revocable, expiring, scoped to one show. **Reuse it; do not write a second
token table.**

**Decision:** Show Passport is a NEW module that *references* a TOUR show
rather than defining its own. Phase 3 ("Show Advancement") therefore becomes
mostly integration — attaching a passport version to an existing show — not a
new show system.

`SHOW_STATUSES` stays `hold / confirmed / advanced / played / settled`
verbatim. The brief suggests a different vocabulary (Draft/Invited/Reviewing…);
the owner has a standing instruction to keep the existing five statuses and
their legend, so passport/advance state is tracked on the passport, not by
renaming show status.

## What genuinely does not exist yet

The real work of this build:

* Show Passport as a versioned, immutable record
* Input list, output/monitor list, monitor mixes as structured rows
* Playback + timecode spec, backline, show cues
* Performer request model and its state machine
* Engineer Desk
* Console adapter contract, simulator, Stage Bridge, safety engine

## Constraints this build must respect

1. **The Tailwind build is frozen.** `tests/test_stylesheet.py` fails on new
   Tailwind utilities — they are not compiled. All new layout is hand-written
   prefixed CSS (the convention: `sbrl-*` Remix Lab, `sr-*` studio, `to-*`
   tour). Stage Control uses **`sc-*`**.
2. **Design lock.** `tests/test_design_system.py` bans raw hex outside an
   exempt list (use `var(--sb-*)` or `rgb(r g b / a)`), enforces a 12px font
   floor, and allows only `--sb-r-control` / `--sb-r-panel` / `--sb-r-pill`
   radii plus 0 and 50%.
3. **Internal-page cohesion.** Every in-app page opens with the shared
   `sb.plate` band from `templates/_sb.html`, never a landing hero. Richness
   goes in the body. (Owner feedback, 2026-09-02.)
4. **Service worker.** Bump `VERSION` in `static/js/sw.js` on any static
   change.
5. **Honesty doctrine.** Never present an unmeasured value as measured. This
   module inherits it with teeth: a requested change is never shown as applied
   without confirmation, and the simulator is labelled simulated everywhere.
6. **Login wall.** Every route is gated unless listed in `_PUBLIC_EXACT` /
   `_PUBLIC_PREFIXES` in `app.py`.

## Security risks noted during the audit

* `/uploads/<path:filename>` (`app.py:2097`) is in `_PUBLIC_PREFIXES` and does
  no ownership check. Filenames are `uuid4().hex + name`, so unguessable in
  practice, but there is no revocation. **Passport documents must not use this
  path** — the brief requires scanned, validated, access-controlled documents.
* There is no CSRF token on form posts anywhere in the app. Stage Control's
  destructive actions (lockout, revoke, apply) should not be the first place
  that matters, but it is recorded here as a platform-level gap.

## Reusable components

`templates/_sb.html` macros — `plate()`, `btn()`, `badge()`, `field()`;
`partner_os.require()` as the model for a server-side permission decorator;
`tour_store` token helpers; `segno` (already a dependency) for QR rendering.

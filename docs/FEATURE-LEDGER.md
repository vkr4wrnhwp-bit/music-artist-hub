# Feature ledger

Every feature in this repository, read from the code. Not from plans, not
from docs/, not from what a name suggests. Where a comment and the code
disagreed, the code won.

Built 2026-09-20 by ten inspectors, one per area, each followed by a
skeptic that had to prove every Live claim reached a real table and every
Dead code claim had no reference anywhere in .py, .html, .js or tests/.
Route, table and environment counts below are extracted mechanically, so
they are exact.

**Status means:**

- **Live** the route is reachable by an account of the right plan and it
  reads or writes that account's real data. A page whose table is usually
  empty is still Live.
- **Partial** part of what it promises works and part does not. The entry
  says which half.
- **Stubbed** it answers, but with fixed, sample, demo-only or hard-coded
  output, or it writes nowhere. A provider adapter with no key that
  refuses honestly is Stubbed.
- **Dead code** nothing reaches it. No route, nav entry, template, module
  or test.

**Rule:** this file is updated in the same commit as any feature added,
changed or removed. A status change counts.

## At a glance

| | Count |
| --- | ---: |
| Live | 390 |
| Partial | 85 |
| Stubbed | 63 |
| Dead code | 22 |
| **Features in total** | **560** |
| Routes | 747 across 19 files |
| Database tables | 230 |
| Environment variables | 95 |

## Contents

- [Money and rights](#money-and-rights)
- [Releases and catalog](#releases-and-catalog)
- [Studio and audio](#studio-and-audio)
- [Fans and audience](#fans-and-audience)
- [Collaboration](#collaboration)
- [Tour and live](#tour-and-live)
- [Command and intelligence](#command-and-intelligence)
- [Account, access and billing](#account-access-and-billing)
- [Press and partners](#press-and-partners)
- [Platform and plumbing](#platform-and-plumbing)
- [Integrations](#integrations)
- [Database tables](#database-tables)
- [Environment variables](#environment-variables)
- [Background jobs and webhooks](#background-jobs-and-webhooks)
- [Unverified](#unverified)

## Money and rights

51 features: 37 Live, 8 Partial, 5 Stubbed, 1 Dead code.

### Live

**The room plate (shared)**

Every room opens on a photographed hardware unit; only the readings are drawn on it.

- Because: room-kit.css owns the pattern - `.rk-pl` is the unit, `.rk-pl-win` a window positioned by `--x/--y/--w/--h`, `.rk-pl-n` a reading, `.rk-pl-sr` the name the photograph already silkscreens. The measurements are NOT in the stylesheet: each room's builder module holds them as `PLATE`, measured off the image with PIL, so a test can read them and a silent drift after a re-crop fails loudly instead of landing the overlays beside their glass.
- Both traps the Studio plate taught are encoded once here: the unit carries `container-type: inline-size`, without which every `cqw` size on a plate is invalid and the type falls back to page-sized and bursts out of the windows; and nothing is ever sized in `cqh`, which does not resolve against an inline-size container. tests/test_fan_room.py asserts both.
- Under 560px the photograph is hidden and the windows become an ordinary stacked list, with the silkscreened names becoming visible because nothing else is naming the figures. The readings are never hidden: a phone that dropped them would be showing a picture of an instrument instead of the artist's numbers.
- STANDBY, THE DISPLAY (owner, 2026-09-22, ruled three times in one afternoon). When a room has measured NOTHING, the plate explains itself. The first cut printed a caption in every window at ~11px — "your text is so small ... it's really cheap looking" — and was replaced by what he asked for, "slot machine-y": the big window SEQUENCES THE ROOM'S FEATURES (`.rk-cine`, one frame at a time at up to ~87px on a desktop plate, each cutting in hard and GLITCHING OUT to the next with a gold/ivory colour split), and the small windows each do a different thing and never carry a caption — icons rolling like a reel (`.rk-reel`), one hint at a time (`.rk-tip`), the feature names ticking through (`.rk-tick`). One voice across all of it: phosphor green with glow and scanlines, "an actual interface looking computerized thing" — the plate's own splash on the suite's gold; the face stays Archivo because he ruled out monospace on the 13th. NO DOOR ON THE PLATE ("remove the link to create a smart link"); the head band's gold pill is the way in. No drawing behind the words. Text in the small windows sits above geometric centre because the photographed glass has a highlight along its top edge. Each room's STANDBY_FRAMES name cards that exist in rooms.ROOMS for it, and the owner supplies the final text per room at the audit. A picture per frame (STANDBY_IMAGES, owner-generated, 2208×1056, no text) draws only when the file is on disk. THE RULE: words only — never a figure, not even an example one — and nothing that repeats what the plate silkscreens. Each room decides `idle` from its own tables; a genuine measured 0 is NOT idle, it prints. Under 560px the small windows go and the sequence becomes a card. The display lives once, in room-kit.css (`.rk-cine*`, `.rk-reel*`, `.rk-tip*`, `.rk-tick*`); per-window headline size comes in as `--cine-size` so a wide-short screen (Stage, Analytics) or a narrow-tall one (Marketing's story) sets its own. Studio, whose plate is bespoke, carries a PLATE dict for the standby's sake only, locked to its sheet by a test. THE READINGS SPEAK IN THE SAME VOICE (owner, same afternoon: "if we flip the data to whatever comes up in the room from uploads ... I would like it to show up in that same green computer text"): `--screen`/`--screen-dim`/`--screen-glow` live on `.rk-pl` and are repeated on the two bespoke units (`.bz-unit`, `.sd-unit`), and every reading, sub-line, plot line and needle readout takes its colour from them, so a plate never switches from green to gold when an account gets its first row. Direction is the arrow and the weight of the green, not red and amber. AND A WINDOW WITH NOTHING TO READ FILLS WITH ICONS, not words ("if it's a display that has no information, then we need to have some sort of icons in there or something to fill it"): `.rk-reel--fill` runs the room's own reel inside the reading window and the small line beneath still names what is missing, so "Not measured" is never the loudest thing on the glass. Business is on the flip like every other room — the display until a statement exists, the readings once one does.
- ON A PHONE the plate steps aside: below 560px the photograph is hidden, the container query is turned off (nothing left to scale a `cqw` against) and the readings become an ordinary stacked list, because a phone that kept the picture would show an instrument instead of this artist's numbers. The six shared plates get this from room-kit.css; the two bespoke units do it in their own sheets, and STUDIO'S WAS MISSING until the 2026-09-22 audit looked at it on a 375px screen - the plate stayed and "Record or upload a track, then measure your master here." was clipped mid-sentence. tests/test_room_kit.py::test_every_plate_steps_aside_on_a_phone holds all three.
- A SEAT SEES ONLY DOORS IT CAN OPEN. Each room takes a `can_open` and drops any tile, action or hero pill whose page the reader's team areas do not allow. `fan_room.build` had no such parameter until the 2026-09-22 audit, so a seat holding only the Fans room was offered that room's gold pill, "Launch fan campaign", and a "See your links" move - both `/links`, a Marketing page, which bounced it. Nothing leaked (the other seven rooms redirect such a seat home and every page held); it was a dead end. The seat is now offered "Open the fan list" and the account holder's own pill is unchanged. tests/test_team_rooms.py holds both halves.
- Studio and Business keep bespoke sheets. Studio's plate has needles, a bay and a waveform that do not generalise; Business's middle window is physically two panes.
- Routes: (library - no route of its own)
- Files: static/css/room-kit.css (.rk-pl*); PLATE in stage_room.py, analytics_room.py, publishing_room.py, releases_room.py, marketing_room.py; static/img/{stage,analytics,publishing,releases,marketing}-plate.webp. The Fans room left this plate for the rooms' shared three-window one on 2026-09-23 (its PLATE went; static/img/fans-plate.webp stays on disk, drawn by nothing).
- Access: whatever the room around it is.

**Business Room (/room/business)**

The Business room's opening screen: a photographed analyser with three windows that are never summed, the five-step path, where the money comes from, what is being chased, and eighteen closing tiles.

- Because: every figure is read off this account's own rows. THE RULE: reported, not collected and kept are three kinds of money and no code path adds them. recovery_engine.build returns a `total_at_stake` that sums the actual with the estimate (recovery_engine.py:238); the Recovery page refuses to print it and so does this room — the route deliberately reads only `actual_unattributed` and `estimated_gaps`, and the middle window shows them as TWO readings side by side, each named, with the plate silkscreening ACTUAL and ESTIMATE between them.
- One basis for the whole plate: business_room.periods() buckets the rows by period (statements_engine.analyze returns NO by_period — the first cut of the route read that key and the window silently showed the lifetime total while the note under it said "One period on file" on every account), reading() names the period it read, and costs_in() takes only the SAME period's expenses, so Kept really is Reported less costs rather than one period's income minus every cost the account ever logged. A period label period_key cannot read is kept out of the ordering entirely, and rows carrying no readable period are counted out loud in the provenance line.
- Nothing unmeasured reads as a nought: money(None) is the words "Not measured", a genuine £0 still prints, and Kept is NOT measured at all when no costs have ever been logged — printing Reported again under KEPT would claim this artist kept every penny, a statement about their finances drawn from missing data. recovery_engine's actual/estimate are read only when there are rows, because it returns 0 for both on an empty account.
- business_room.streams() folds the rows through royalty_types.classify rather than reading analysis["by_bucket"], a key analyze() has never returned — every stream read "—" on every account, telling an artist with a Spotify statement they had no measured streaming income. Money from an unclassifiable source gets its own Unclassified line rather than vanishing between the four named streams, and the table names its basis (every statement on file) because the windows above read one period.
- NO FIGURE FROM THE MISSING-MONEY QUEUE: artist_os._LANE_SHARE applies six hardcoded coefficients to the whole-account total once per track, so its estimate can exceed everything the catalogue has earned. Its tile carries a count and no money.
- Eighteen cards, eighteen doors, and no merges. Two pairs look like free ones and are not: Tax and Contracts are each a second VIEW of another card's handler (/statements?view=tax, /vault?view=contracts), but both templates switch on that argument — `{% if view == "tax" %}`, `{% if view == "contracts" %}` — so the bare page does not contain the other half. One handler, two pages; dropping either tile deletes its only door rather than tidying a page away. They were merged, tests/test_rooms.py caught it, and they were restored. Roster, Portal and Services keep their tiles for the same reason: nothing else in the rooms layout links to them. A real merge here means making /vault and /statements each show both halves on one page — a change to those pages, not to this tile list. tests/test_business_room.py asserts the templates still hide the second view and will say when that stops being true.
- THE PLATE since 2026-09-23 (owner: every room on the shorter three-window plate): the working room draws the rooms' shared plate, static/img/room-plate.webp, through partials/cc_rack.html - three screens, Reported / Not collected / Kept, each named on its screen (the plate prints no names), figures from business_room.rack_screens(); Not collected keeps its two readings apart: the actual unattributed figure is the screen's reading and the estimate is named as an estimate on the line under it, never summed. An absence (Kept with no costs logged) is the words Not measured, never a nought. The earlier business-plate.webp analyser is retired from the page (file kept).
- The photo-plate method: the hardware is ONE photograph, static/img/business-plate.webp (1672x757, 105KB, cropped from 1672x941 — the blank sub-panel below the seam at y=756 held nothing), and only the readings are drawn on it. Every region is a FRACTION measured off the file with PIL and recorded in static/css/business-room.css (windows top 19.95% height 56.94%; reported 6.70% wide 26.61%, the middle pair 35.94% wide 28.05% with a 1.49% gutter, kept 66.75% wide 26.61%; the bottom 7% of the middle panes left clear of the ACTUAL/ESTIMATE silkscreen). If the plate is regenerated those must be re-measured — the windows move and nothing in code will say so. The unit carries `container-type: inline-size` because every size on it is a cqw clamp; without it they are all invalid and the type bursts out of the windows (the Studio bug of the same day), and nothing is sized in cqh, which does not resolve against an inline-size container.
- No label in the markup is printed on screen: REPORTED / NOT COLLECTED / KEPT and ACTUAL / ESTIMATE are silkscreen on the photograph, so the names sit in the markup for screen readers alone — and become visible under 560px, where the plate steps aside and the three readings become an ordinary stacked list. The figures are never hidden: a phone that dropped them would show a picture of an instrument instead of this artist's money. The five-circle rail under the plate uses none of the plate's words (Statements / Matched / Chased / Recovered / Costs) after the first cut repeated Reported and Kept forty pixels below the windows printing them.
- The page from zero (owner's Business spec + mockup, 2026-09-23): an account with no statement, no row, no cost, no claim and no dispute meets an onboarding page rather than an empty analyser, in the spec's order - the header (subtitle "See what you earned, what you spent, and what still needs attention.", the account chip kept, primary "Upload your first statement" -> /statements?returnTo=/room/business&from=business-zero-state, exactly as the spec writes it), the Command Center's photographed three-screen plate drawn STATIC with PURPOSE / START HERE / GOOD TO KNOW (green is information, never a button; no rotation), "Start with your first statement" with the "Upload a statement" card ("Upload statement", "How statements work" -> the desk's intake) beside "What Business will organize" - the four categories, each a door by its own room card (Statements & royalties -> statements, Costs & profit -> revenue-os, Recovery & claims -> recovery, Contracts & people -> vault; words, not a door, for a seat that cannot open the page), the five-step workflow numbered 1-5 as the mockup numbers it with Upload lit and no percentage, "Your money picture will appear here" (one link, "Supported statements" -> the desk's intake; the spec's second link "Import history" would be the same door under a second name and an empty table besides, so it waits for an import) beside "No income is measured yet", help, and "More Business tools" - a drawer that starts OPEN (owner's ruling the same day) with every tool under the spec's four categories. No date range, no income total, no profit, no recovery estimate, no percentage, no nought. The room says "Your first statement was added. Business is organizing what it reports." only when a statement is really on file (business_room.done_line). The state is read from every count the spec names in ONE try (rows, statements, costs, claims, disputes); a failed read is templates/room_business_error.html at 503 ("We could not load Business", Try again / Open statements), never a fresh account - the old per-read fallbacks for costs, claims and disputes that turned a failure into empty values are gone. A seat without edit access gets the card without its door. One statement, cost, claim or dispute and the populated analyser returns untouched with its own three bands. The animated standby that ran on the analyser for an empty account is retired on this room; the fill reel stays for a populated analyser's empty windows. The owner's mark on a page they hid (page_switches) stays on the drawer's tile from zero - the "Hidden" pill in the room's own status classes - because rooms.build keeps that card for the owner alone; the seven rooms dropped the state on the way to their zero drawers until 2026-09-23 (the Marketing room had it from the start), and the populated Studio, Stage, Analytics, Business and Releases rooms, whose tile feet were empty, show the same pill from the same day.
- Routes: GET /room/business (dispatched from /room/<room_key>)
- Files: app.py room_screen() -> app.py _business_room() (+ _business_chasing); templates/room_business_error.html; templates/partials/cc_rack.html + static/css/command-zero.css + static/img/room-plate.webp (the owner's shorter three-window plate, 2026-09-23) (the page from zero); business_room.py new_account(), done_line(), zero_page(), STEPS, TILES, RENAMED, STREAMS, money(), change(), windows(), provenance(), path(), streams(), periods(), costs_in(), reading(), build(); templates/room_business.html; static/css/business-room.css; static/img/business-plate.webp; rooms.py ROOMS["business"]; reads db.get_statement_rows / get_statements / list_expenses / list_recovery_cases / list_disputes, statements_engine.analyze, recovery_engine.build, royalty_types.classify
- Access: Any signed-in account, as /room/<key>: no tier gate. Team seats need the "business" room ticked; a tile whose page the seat cannot open is dropped. Anonymous redirected to /login.

**Capital Readiness Score**

A 0-100 funding-readiness score from five verifiable factors, with an illustrative 0.8-1.5x advance band.

- Because: GET answered 200; capital_score reads real statement rows, catalog tracks, campaigns and the Trust Score, records the reading in score_history, and the band is None (so nothing is quoted) when annualised income is zero or non-finite.
- Routes: GET /capital-score
- Files: app.py:8614; capital_engine.py:22 capital_score; trust_score.py:40 calculate; statements_engine.annualize; db.record_score/score_trend; templates/capital_score.html
- Access: Artist tier and above ("/capital-score" in _PRO_PATHS). Team seats: "/capital-score" is in team_areas.EXTRA["business"].

**Catalog value rule**

The single 3/4/5 multiple band every surface that prints a catalog figure reads.

- Because: catalog_value.band is imported and called by valuation_engine, statements_engine.build_royalty_summary, the /catalog value card and royalty_data.CATALOG_VALUE_MULTIPLES; it guards against a stored inf by returning zeros. Reachable from four call sites, so not dead.
- Routes: (library — no route of its own)
- Files: catalog_value.py:32; valuation_engine.py:44; statements_engine.py:351; app.py:2695 (catalog card); royalty_data.py:517
- Access: n/a — library used by pages gated at Artist tier.

**Contract reader**

Pull renewal terms out of a filed contract's own text so a person can check them.

- Because: The route fetches the real bytes (blob_store.fetch for remote, a size-capped local read otherwise), runs contract_reader.extract_text + find_terms and persists the reading with store.set_document_reading; a file it cannot reach is recorded as status "unavailable" rather than as empty findings. Nothing reaches the contract's row until a person presses Save dates.
- Routes: POST /vault/documents/<doc_id>/read
- Files: app.py:10367; contract_reader.py extract_text/find_terms/summary; db.py set_document_reading/get_document_readings (table document_readings); templates/vault.html
- Access: Artist tier and above (reached from the contracts section). Team seats with the Studio or Business room as above, and edit access for the write.

**Contract renewal terms and reminders**

Type a renewal date and notice period on a contract, and get told at 60, 30, 7 and 1 days before the notice deadline, once a scheduler runs the daily reminders.

- Because: POST validates the date format and clamps notice_days to 0-365 before store.set_document_terms; contract_reminders.status() drives the row's state and contract_reminders.run() fires the milestones, writing document_reminders and sending email where the deployment can. Each milestone fires once and nothing fires for a renewal already in the past. The run only happens when something POSTs /reminders/run, and nothing in the repo does: the Render cron is the owner's to create. So the words are measured (2026-09-23): contract_reminders.scheduled() is true only when REMINDERS_CRON_TOKEN is set AND a scheduler completed a run with it in the last 48 hours. Until then the Contracts card reads "with renewal dates on file", each row says the 60, 30, 7 and 1 day reminders "are not switched on yet", the saved note drops "Reminders follow them" and the upload action asks to "Set the renewal dates"; once it is true the reminder wording comes back by itself (tests/test_reminders_cron.py).
- Routes: POST /vault/documents/<doc_id>/terms; POST /reminders/run
- Files: app.py document_terms, reminders_run, _reminders_on, _read_on_upload; contract_reminders.py MILESTONES/status/run/token_matches/record_run/scheduled; rooms.py catalogue (the Contracts card line); readiness.py "Contract renewal reminders" row; db.py document_terms, document_reminders tables, set_kv("reminders_last_run") and set_kv("reminders_last_scheduled_run"); templates/_vault_contracts.html
- Access: The terms form is Artist tier and above, behind the contracts gate. /reminders/run answers for itself outside the session wall (plan_gate lets the path through): a scheduler presents REMINDERS_CRON_TOKEN in the X-Reminders-Token header (hmac.compare_digest), or a signed-in owner runs it by hand. BACKUP_TOKEN no longer runs it. Anonymous without the token gets 401 JSON with the reason, never a redirect; a GET gets 405; a signed-in non-owner gets 404. Team seats never reach it: the route is owner-or-token.

**Contracts and licences (Documents)**

File a contract, licence, statement or registration against the account or one recording, and see per-track paperwork coverage.

- Because: GET /documents 302s to /vault?view=contracts (confirmed) and the section is rendered from documents_engine.build, which counts real store.list_documents against tracks gathered from the catalog, the Track Passports and the titles on uploaded statements. POST accepts both /documents and /vault/documents, validates the extension, stores through blob_store and writes store.add_document. Coverage is None rather than 0% when no track is named.
- Routes: GET/POST /documents; POST /vault/documents; POST /documents/<doc_id>/delete; POST /vault/documents/<doc_id>/delete; GET /vault?view=contracts
- Files: app.py:12405-12406 (documents), app.py:12441-12442 (delete), app.py:10281 (_render_vault); documents_engine.py:73 build / :44 known_tracks; db.py documents table; templates/vault.html
- Access: The section keeps the old page's gate: the handler re-checks plans.allowed(plan, plans.required_tier("/documents")) and renders upgrade.html 402 otherwise — so Artist tier and above, even though the vault around it is Artist too. Team seats: "/documents" is in team_areas.EXTRA["business"], and "contracts" is a Studio-room card pointing at /vault?view=contracts (rooms.py:106), so the two routes sit in different rooms.

**Deal Room**

A board of agreements — type, counterparty, terms, deadline, status — each able to carry a filed document.

- Because: GET answered 200; POST creates through store.create_deal and patches through store.update_deal against the deals table, and the document picker is the account's own store.list_documents. Deal types and statuses are validated against _DEAL_TYPES/_DEAL_STATUSES. trust_score reads signed split deals back, so the writes are consumed elsewhere.
- Routes: GET/POST /deal-room
- Files: app.py:9370; app.py:9153-9154 (_DEAL_TYPES/_DEAL_STATUSES); db.py deals table, list_deals/create_deal/update_deal; templates/deal_room.html
- Access: Artist tier and above ("/deal-room" in _PRO_PATHS). Team seats: "/deal-room" is in team_areas.EXTRA["business"]; it is also the Business room's "deals" card.

**Deal Room one-sheet**

The label-facing one-sheet, now folded into the press kit.

- Because: GET /deal-room/onesheet returned 301 to /epk (confirmed). What it used to print is rebuilt by _deal_facts() for the press kit's "For deals" section from real data — certification, statement rows and total, lanes, Pulse growth — and growth is omitted entirely unless two snapshots carry a follower count.
- Routes: GET /deal-room/onesheet (301 → /epk)
- Files: app.py:7166 (redirect), app.py:7177 (_deal_facts); artist_os.py certification/lane_grid/clean_release; epk templates
- Access: Artist tier and above ("/onesheet" and "/deal-room" are both in _PRO_PATHS; /epk itself is an exact-match artist gate).

**Disputes**

Log a conflict with a platform — type, amount, description — and track it open/submitted/resolved.

- Because: GET answered 200; the rows come from store.list_disputes and the three totals are summed from them. POST validates the type against _DISPUTE_TYPES and writes store.add_dispute into the disputes table; delete is user-scoped.
- Routes: GET /disputes; POST /disputes/new; POST /disputes/<dispute_id>/delete
- Files: app.py:13198, app.py:13217, app.py:13234; db.py disputes table, list_disputes/add_dispute; templates/disputes.html
- Access: Artist tier and above ("/disputes" in _PRO_PATHS and _SWEEP_MARK_PATHS). Team seats through the Business room ("disputes" card).

**Distributor letter**

A draft letter about one case, worded from what the store check actually found — carried, absent, or unchecked.

- Because: The handler pulls the case, the matching finding, the ISRC from the real rows and the stored gap check, and hands them to distributor_letter.draft; the three letter shapes are chosen from the check result, and an unchecked case gets the letter that says so. Nothing is sent — there is no send call in the route.
- Routes: GET /royalty-recovery/cases/<case_id>/letter; POST /royalty-recovery/cases/<case_id>/sent
- Files: app.py:9283 (letter), app.py:9321 (sent → store.record_case_evidence); distributor_letter.py; statements_desk.py slug(); templates/recovery_case_letter.html
- Access: Artist tier and above. Team seats with the Business room; marking it sent is a write and needs an edit seat.

**Income-by-type redirects (Publishing, Mechanicals, Neighbouring rights, Territories)**

The four old per-stream pages now land on the matching section of the Royalties page.

- Because: All four answered 302 to /royalties#streams (or #markets for /territories) on the test client. The sections they land on are computed by royalties_desk.streams()/markets() from real rows.
- Routes: GET /publishing → /royalties#streams; GET /neighboring-rights → /royalties#streams; GET /mechanicals → /royalties#streams; GET /territories → /royalties#markets
- Files: app.py:11347, app.py:11351, app.py:11362, app.py:11366; royalties_desk.py streams()/markets(); royalty_types.py:55 classify / :36 GUIDANCE
- Access: Artist tier and above — all four prefixes are in _PRO_PATHS. Team seats: "/mechanicals" and "/neighboring-rights" are in team_areas.EXTRA["business"], "/territories" is in EXTRA["analytics"], and "/publishing" is in EXTRA["publishing"], so the three land in different rooms.

**Insights**

Rule-based observations over the account's own numbers, including income concentration and which royalty streams show nothing.

- Because: GET answered 200; every insight cites a real query — statement sources for concentration, royalty_types.type_report per bucket for the missing streams, campaign event counts for the best converter, fan intent scores, Pulse deltas (only where two readings carry a number), and catalog ISRC gaps. With no statement rows it emits the "No income data yet" card rather than inventing money insights.
- Routes: GET /insights
- Files: app.py:11370; insights_engine.py:22 build_insights; royalty_types.py:64 type_report; templates/insights.html
- Access: Artist tier and above ("/insights" in _ARTIST_PATHS). Analytics room card "insights" (rooms.py:112).

**Lockbox signing page**

The page an outside approver opens from their emailed link to read the contract and sign off.

- Because: GET/POST /sign/<token> reads the token row and renders the real passport slot; /sign/<token>/document serves the attached file by token and aborts 404 unless the path is under /uploads/ and matches the lockbox uploader's own name shape, so an approver who is not signed in can read exactly the one file they were asked about and nothing else. Both routes answer by one rule, _sign_link (2026-09-23): the document is served only while the link is open. A used link (signed or declined), a link the artist has replaced by resending or asking the same person again, and a link whose track or slot is gone all get the same 404 as an unknown token. Until then the document route read none of this and served the contract after the link was used (tests/test_sign_link_document.py).
- Routes: GET/POST /sign/<token>; GET /sign/<token>/document
- Files: app.py _sign_link, sign_document, sign_document_file, _is_lockbox_upload, os_lockbox_update (approver/resend mint the token the approval carries); db.py get_sign_token/sign_tokens; templates/sign.html; tests/test_sign_link_document.py
- Access: Anonymous by design — "/sign/" is in _PUBLIC_PREFIXES (app.py:4817); the unguessable token is the authorisation and is checked on both routes.

**Money queue**

The prioritised list of money actions across the account's Track Passports, beside tour income already settled.

- Because: GET answered 200; the queue is artist_os.action_queue over store.list_os_tracks + _os_ctx, and the tour figure is tour_store.settled_income plus legacy Tour Hub settlement blobs parsed from store.list_tour_shows. Nothing seeded; an account with no passports gets an empty queue.
- Routes: GET /money-queue
- Files: app.py:7114; artist_os.py action_queue; tour_store.settled_income; touring.settlement_totals; templates/money_queue.html
- Access: Artist tier and above ("/money-queue" in _PRO_PATHS). Team seats: "/money-queue" is in team_areas.EXTRA["business"].

**Open a case from a finding**

Turn one Recovery finding into a case, once, keyed on the finding's own identity so a repeated sweep refreshes rather than duplicates it.

- Because: The form posts case_key (recovery_engine.finding_key) and store.open_case_for_finding keeps one live case per key, returning whether it was opened or refreshed; the page reports that back through ?opened=.
- Routes: POST /royalty-recovery/cases/from-finding
- Files: app.py:9338; recovery_engine.py:74 finding_key; db.py open_case_for_finding; templates/recovery.html, templates/recovery_cases.html
- Access: Artist tier and above. Team seats with the Business room and edit access.

**Qualification (Growth) Score**

A 0-100 score over twelve categories of real account data, including income on record, with unlock thresholds and named fixes.

- Because: GET answered 200; every category reads a real source — campaigns and destinations, rollout posts, fans, catalog ISRCs, EPK fields, Pulse snapshots, the Rack's track analysis, and statement rows for the money category, which quotes "upload a royalty statement" and scores 0 when there are none. The total is normalised over the category count and recorded in score_history inside a try/except.
- Routes: GET /qualification
- Files: app.py:9991; qualification.py:46 calculate; audio_readiness.readiness_points; db.record_score/score_trend; score_history.summarise; templates/qualification.html
- Access: Artist tier and above ("/qualification" in _ARTIST_PATHS). It is the Analytics room's "scores" card (rooms.py:48), so a team seat needs Analytics, not Business.

**Publishing Room (/room/publishing)**

The Publishing room's opening screen: three figures, the five-state song ladder, what each registry said per recording, where the records disagree, who owns the selected song, and five closing tiles.

- Because: every figure is a count over this account's own rows. Works on file is store.list_os_tracks. Share claimed and the uncollected count are artist_os.mlc_evidence, which reads the STORED registry answer (track_mlc_checks) and carries share_total and song_code - so the share is of the recordings a registry has answered about, not of the catalogue, and the sub-line says which. A recording nobody has asked about is "Not measured", never 0 and never green, and a value typed into a passport keeps its own "typed, unverified" state distinct from a registry's confirmation. The five-state rail is publishing_room.state_of: a song is counted at the FURTHEST rung it reached, not at every rung it satisfies, so the counts sum to the works on file and read as a funnel; a song collecting with no split sheet is counted as collecting and its missing sheet appears as a conflict instead. Collecting is a statement row whose source royalty_types.classify()es to publishing or mechanical (a Spotify line is the master's money, not the work's, and is excluded) matched on the normalised title, which UNDERCOUNTS when a society spells a title differently - the footnote says so rather than rounding up. The conflicts panel is rights_conflicts.for_account over the same tracks: identifier clashes, ownership disagreements, unresolved clearances and split gaps, each with its own fix link. The tiles carry only counts that were counted; Catalog has no figure and shows none.
- Substitute (owner's mockup could not be built as drawn): his "Splits, one song at a time" drew writer, role, society and percentage totalling 95%. There are no writer shares stored anywhere in this application - os_tracks.passport holds songwriters as one line of free text - so the panel is "Who owns it": the passport's own words for songwriters, producers, publishers, PRO and publishing administrator, plus the Rights Lockbox's split sheet and producer agreement states, under a line reading "Writer percentages are not recorded anywhere yet." His ruling, asked and answered 2026-09-22: show what is already there, and no "coming soon" badge, because nothing else in the app makes a promise.
- THE PLATE since 2026-09-23 (owner: every room on the shorter three-window plate): the working room draws the rooms' shared plate, static/img/room-plate.webp, through partials/cc_rack.html - three screens, Works on file / Uncollected / Share claimed, each named on its screen, from publishing_room.rack_screens(); an unanswered registry reads Not measured in words. The 2026-09-22 registry plate below is retired from the page (file kept).
- THE PLATE (2026-09-22): a photographed RIGHTS REGISTRY, static/img/publishing-plate.webp (1859x846), fractions in publishing_room.PLATE. Two equal halves carry WORKS ON FILE and UNCOLLECTED; the narrow ledger strip carries SHARE CLAIMED as a bar - the third headline figure, which has no window of its own. The bar is drawn ONLY when a registry has answered: an empty bar would read as "you have claimed nothing" when the truth is that nobody has asked. It is not the "Who owns it" table, which keeps its own panel and song picker.
- The page from zero (owner's Publishing spec + mockup, 2026-09-23): an account with no song meets an onboarding page rather than an empty plate, five zero-count states and blank conflict tables, in the spec's order - the header (subtitle "Keep every song's writers, splits, rights, and registration status in one trusted record.", the account chip kept, primary "Add your first song" -> /catalog/new?returnTo=/room/publishing&from=publishing-zero-state, the spec's suggested route, now a real GET that forwards to the catalog's passports view - the ONE shared add-song form Studio and the Command Center already use - carrying the way back), the Command Center's photographed three-screen plate drawn STATIC with PURPOSE / START HERE / GOOD TO KNOW, "Start with one song" with the "Create your first song record" card ("Add a song"; "What information do I need?" opens the spec's first-draft list in place: the title, the account, one known writer or "Writers not known yet") beside "What Publishing will organize" - the four categories, each a door by its own room card (Catalog & passports -> catalog, Writers & splits -> track-passports, Registrations & collection -> certified, Conflicts & clearances -> conflicts; words, not a door, for a seat that cannot open the page), the five-step workflow numbered 1-5 as the mockup numbers it with Add song lit and no percentage, "Your publishing catalog will appear here" (one link, "How song records work", into the workflow; the spec's "Import catalog" waits for a catalog import to exist) beside "Nothing has been verified yet", help, and "More Publishing tools" - a drawer that starts OPEN (owner's ruling the same day) with the tools under the spec's categories, Beats and Fingerprints inside it as the spec asks. The room says "Your first song was added. Publishing is ready for its writers." only when a song is really on file (publishing_room.done_line). The state is read in ONE try (songs and statement rows); a failed read is templates/room_publishing_error.html at 503 ("We could not load Publishing", Try again / Open catalog), never a fresh account - the statement rows' old fallback to nothing is gone. A seat without edit access gets the card without its door. One song and the populated plate returns untouched. The animated standby that ran on the plate for an empty account is retired on this room; the fill reel stays for a populated plate's empty windows. The owner's mark on a page they hid (page_switches) stays on the drawer's tile from zero - the "Hidden" pill in the room's own status classes - because rooms.build keeps that card for the owner alone; the seven rooms dropped the state on the way to their zero drawers until 2026-09-23 (the Marketing room had it from the start), and the populated Studio, Stage, Analytics, Business and Releases rooms, whose tile feet were empty, show the same pill from the same day.
- Routes: GET /room/publishing?song=<id> (dispatched from /room/<room_key>); GET /catalog/new (the shared add-song door, forwards to /catalog?view=passports with returnTo/from)
- Files: app.py room_screen() -> app.py _publishing_room(), catalog_new(); templates/room_publishing_error.html; templates/partials/cc_rack.html + static/css/command-zero.css + static/img/room-plate.webp (the owner's shorter three-window plate, 2026-09-23) (the page from zero); publishing_room.py new_account(), done_line(), zero_page(), showcase(), STATES, PUBLISHING_BUCKETS, collecting_titles(), state_of(), states(), uncollected(), headline(), splits(), build(); templates/room_publishing.html; static/css/publishing-room.css; rooms.py ROOMS["publishing"]; engines artist_os.py (mlc_evidence, lockbox_report), rights_conflicts.py, royalty_types.py; stores db.py (os_tracks, track_mlc_checks, statement_rows)
- Access: Any signed-in account, as /room/<key>: no tier gate. Team seats need the "publishing" room ticked; a tile whose page the seat cannot open is dropped. Anonymous redirected to /login.

**Recovery**
- THE SHOWCASE (owner's ruling: the demo account is the showcase, never the page from zero; fixed 2026-09-23, audit publishing-2): the three non-fan demo logins (demo@, demo-pro@, demo-artist@) carry seeded statements but no song records, so each met "Start with one song" under a "Sample data" lamp that marked nothing. _publishing_room now passes zero=(not showcase) and publishing_room.new_account(tracks) with showcase = _session_is_demo(), the Marketing room's pattern, and a showcase session's songs are publishing_room.showcase(): five songs with the demo statement's own titles, built in memory and never stored (nothing is written to os_tracks or track_mlc_checks), read by the same engines a real account's songs go through (state_of, uncollected, headline, rights_conflicts) - a full claim, a part claim, one with no work linked, a signed split sheet nobody has asked about, and a bare title, with one song carrying two writers and no split sheet so the conflicts panel has something true to say. The "Sample data" lamp is drawn only when that example is on screen, never on the page from zero. The example's rows link to no passport page and its conflicts to no fix page, "See all rights conflicts" is not drawn over it, the table's foot says its answers are part of the sample and nobody asked a registry, and the done line is never said for the example's songs. A shared read-only demo (users.demo_lock, whose saves demo_lock_gate refuses) is offered no write door on either page: can_add is "demo", the populated header's "Add a song" is not drawn and the card from zero says the demo is read only. The same header rule holds for a read seat, which had kept the populated "Add a song" after the page from zero took it away; it now gets the line "Songs are added by the account owner or a seat with edit access."

Findings computed from the account's own statement rows — unattributed revenue (actual) and cross-store coverage gaps (estimate) — with the case desk and the MLC panel alongside.

- Because: GET answered 200 and POST /scan/missing-royalties on the same account returned two findings computed from the uploaded CSV ($12.40 unattributed, $14.48 gap). recovery_engine.build returns has_data:False with zeroed figures when nothing is uploaded, so there is no seed fallback; recovery_desk.build lays it out with the stored gap checks and open cases.
- Routes: GET /recovery
- Files: app.py:3042; recovery_engine.py:89 build; recovery_desk.py:197 build; recovery_mlc.py state(); statements_engine.py:233 analyze; templates/recovery.html
- Access: Artist tier and above ("/recovery" in _PRO_PATHS, and in _SWEEP_MARK_PATHS). Team seats through the Business room.

**Recovery Cases**

Track a claim from open through submitted/waiting to won or lost, with an estimated amount, a deadline, notes and an evidence document.

- Because: GET answered 200; POST creates via store.create_recovery_case or patches via store.update_recovery_case, both user-scoped, and the pipeline and recovered totals are summed from the stored rows. A won case writes a notification.
- Routes: GET/POST /royalty-recovery/cases; POST /royalty-recovery/cases/<case_id>/delete
- Files: app.py:9158 (recovery_cases), app.py:9273 (delete), app.py:3030 (_strip_case); recovery_desk.py rail()/cases_view(); db.py recovery_cases table; templates/recovery_cases.html
- Access: Artist tier and above ("/royalty-recovery" in _PRO_PATHS and _SWEEP_MARK_PATHS). Team seats: "/royalty-recovery" is in team_areas.EXTRA["business"]; writes need an edit seat.

**Recovery findings CSV**

Download the unattributed-revenue and coverage-gap findings as a CSV, each row labelled Actual or Estimate.

- Because: GET returned 200; the rows come from statements_engine.build_royalty_summary over the account's own statement rows, and an account with none gets a header-only file rather than invented findings.
- Routes: GET /reports/recovery.csv
- Files: app.py:3148; statements_engine.py:351 build_royalty_summary
- Access: Any signed-in account by tier ("/reports" is in _PRO_PATHS so Artist and above), and the handler re-checks current_user(). Team seats: /reports is not in team_areas.EXTRA, so it follows room_for_path.

**Reports (real CSV exports)**

Seven report builders that produce a real CSV from the account's own statements, or refuse with a reason.

- Because: report_builder.build returns (None, None, reason) when a builder has no data, and app.py:14363 only files a history row after the build succeeds and under the name the builder gave it; the download route rebuilds from live data rather than serving a cache. /reports itself answered 200 and /reports/campaigns.csv, /reports/recovery.csv and /reports/executive are separate real exports.
- Routes: GET /reports; POST /reports/<report_id>/generate; GET /reports/<report_id>/download; GET /reports/campaigns.csv; GET /reports/recovery.csv; GET /reports/executive
- Files: app.py:3111 (reports), app.py:14363 (generate), app.py:14389 (download), app.py:3148 (recovery.csv); report_builder.py:218 build and the seven builders at :54-:218; royalty_data.py:1364 get_report_history / :1389 record_generated_report; templates/reports.html
- Access: Artist tier and above ("/reports" in _PRO_PATHS). Analytics room card "reports" (rooms.py:48). The scheduled-report list on the page is the demo account's only.

**Revenue OS (Profit & Loss)**

Log release expenses by category and set them against reported statement income to get a net.

- Because: GET answered 200; POST writes and deletes rows in revenue_expenses through store.add_expense/delete_expense, and income is statements_engine.build_royalty_summary over the real rows. With no statement it passes income=None, not 0, so the page cannot print "$0.00 Profitable" on a fresh account.
- Routes: GET/POST /revenue-os
- Files: app.py:9652; db.py list_expenses/add_expense/delete_expense (table revenue_expenses); statements_engine.py:351 build_royalty_summary; templates/revenue_os.html
- Access: Artist tier and above ("/revenue-os" in _PRO_PATHS). Team seats through the Business room ("revenue-os" card); writes need an edit seat.

**Rights Conflicts**

Where the account's own Track Passports disagree about who owns a song, plus the clearances it has answered no to.

- Because: GET answered 200; rights_conflicts.summary reads store.list_os_tracks only and computes four families — duplicate ISRC/UPC, ownership disagreements between two passports for one title, unresolved clearances and multi-writer songs with no signed split sheet. An empty catalogue returns an empty list and the page says nothing was checked, rather than calling it clean. The context is deliberately layered over build_dashboard_context so the old demo "conflicts" key cannot show through.
- Routes: GET /conflicts
- Files: app.py:12460; rights_conflicts.py:186 for_account / :199 summary; db.py list_os_tracks (table os_tracks); templates/conflicts.html
- Access: Artist tier and above ("/conflicts" in _PRO_PATHS). Team seats: "/conflicts" is in team_areas.EXTRA["business"]. Note a code disagreement: the page computes real data, but "conflicts" is absent from hubs._BASE_LIVE (hubs.py:155) and from hubs.live_keys(), so the sidebar still badges it Sample.

**Royalties desk**

One page over the uploaded rows: earnings with movement, the four royalty streams, the nine lanes per track, stores, tracks, markets and the roster of acts.

- Because: GET answered 200 with a statement on file; every panel is computed by royalties_desk.build from store.get_statement_rows + store.list_os_tracks, with the period control listing only the periods actually on file. Streams are classified by royalty_types.classify over the real source names; a stream with nothing on file renders "—" and "not on file" rather than a zero.
- Routes: GET /royalties (period via ?period=, act via ?artist=)
- Files: app.py:2550; royalties_desk.py (build at end of file), royalty_types.py:55 classify, statements_engine.py:233 analyze, artist_os.lane_grid; templates/royalties.html
- Access: Artist tier and above ("/royalties" in _PRO_PATHS; also carries the Royalty Sweep mark via _SWEEP_MARK_PATHS). Team seats through the Business room.

**Royalty goal**

Set, change or clear the yearly royalty target the money ring on the front door reads.

- Because: POST writes store.set_royalty_goal / clear_royalty_goal against the royalty_goals table and is read back by _front_money_context; the amount is validated finite, positive and under GOAL_MAX so "nan" and "1e400" are rejected rather than stored.
- Routes: POST /overview/goal
- Files: app.py:2520; db.py royalty_goals table, set_royalty_goal/get_royalty_goal/clear_royalty_goal; app.py:2472 (_front_money_context)
- Access: Any signed-in account — /overview is not in the tier lists, so required_tier is None; the handler requires current_user(). Team seats never reach it: "/overview" is in team_areas.WHOLE_ACCOUNT, so a seat without every room is bounced.

**Royalty Lanes**

The nine income lanes scored per track, now a section of the Royalties page.

- Because: /royalty-lanes is a 302 to /royalties#lanes (confirmed by test client); the matrix itself is royalties_desk.lanes() over artist_os.lane_grid for the account's own Track Passports, and the walk fix separates "claimed" (a statement row pays it) from "connected" (set up, no income yet) so an unsold sync pack no longer reads as paying.
- Routes: GET /royalty-lanes (302 → /royalties#lanes)
- Files: app.py:7108; royalties_desk.py lanes()/_lane_note; artist_os.py LANES, lane_grid, _LANE_SHARE; templates/royalties.html
- Access: Artist tier and above ("/royalty-lanes" in _PRO_PATHS). Team seats: "/royalty-lanes" is explicitly in team_areas.EXTRA["business"].

**Royalty Sweep method page**

A public explainer of what the sweep reads, how an estimate is arrived at and what happens to the data.

- Because: GET returned 200 signed out. It renders sweep_config.METHOD and SOURCES — fixed editorial copy by design, carrying no figures and no account data; it is a content page, not a computation, and nothing on it claims a scan has run.
- Routes: GET /royalty-sweep
- Files: app.py:14186; sweep_config.py METHOD/SOURCES; templates/sweep_method.html
- Access: Anonymous — "/royalty-sweep" is in _PUBLIC_EXACT (app.py:4865), so plan_gate lets it through with no session. Note the sidebar's "royalty-sweep" entry (hubs.py:327) points at /royalties, not here.

**Split agreement generator**

Turn two to four named parties and their percentages into a plain-text split-agreement template, filed in the vault and opened as a deal.

- Because: The route writes a real file into UPLOADS_DIR, records it with store.add_document as a "Split Agreement", and creates the matching deal; it refuses with a redirect when fewer than two parties are named. The output is explicitly labelled a template and "NOT LEGAL ADVICE".
- Routes: POST /deal-room/generate-split
- Files: app.py:9405; db.py add_document, create_deal; templates/deal_room.html
- Access: Artist tier and above. Team seats with the Business room and edit access.

**Statement delete**

Remove one uploaded statement and every row it brought in.

- Because: store.delete_statement is scoped to the user id and the handler aborts 404 when nothing was removed, so a guessed or another account's id changes nothing; the money pages re-read the remaining rows.
- Routes: POST /statements/<statement_id>/delete
- Files: app.py:1660; db.py delete_statement; templates/statements.html
- Access: Artist tier and above ("/statements" prefix). Team seats with the Business room and edit access; a read seat is bounced by team_seat_gate (app.py:5109).

**Statements**

Upload distributor/PRO/MLC royalty CSVs and read the parsed rows back as a desk of totals, store ladder, track table and coverage-gap cards.

- Because: GET/POST both answered 200 on a throwaway DB after a real CSV upload; the POST writes statements + statement_rows via store.save_statement and the page re-reads them through store.get_statement_rows, with the desk built by statements_desk.build over statements_engine.analyze. No seed path.
- Routes: GET/POST /statements
- Files: app.py:1578 (handler), app.py:1474 (_ingest_statement), app.py:1534 (_act_scope); templates/statements.html; statements_engine.py:180 parse_statement / :233 analyze; statements_desk.py:297 build; db.py save_statement/get_statement_rows/get_statements
- Access: Artist tier and above — plans.required_tier("/statements") returns "artist" via _PRO_PATHS; a fan plan gets upgrade.html 402 from plan_gate (app.py:4956). Anonymous is redirected to /login. Team seats reach it through the Business room (rooms.ROOMS "business" holds the "statements" card); not in _TEAM_BLOCKED. Not owner-only.

**Reporting lag: has each store reported?**

Per store on the uploaded statements, whether the period it owes has arrived and whether the wait so far is normal for THAT store. Overdue is called out; a store that is simply slow by nature is reassured about. Every verdict rests on a published industry figure and says so, because nothing here records when a distributor actually reported.

- Because: GET /statements and GET /royalties both render the section from statements_engine.reporting_lag over store.get_statement_rows; every verdict comes from royalty_lag.judge/expectation, which until this commit was imported by nothing. The wait is the only number and it is pure calendar: a period ended on a known day, today is a known day, and no row on file covers the period after it. Basis is named on the page in words, and is always either "a general figure for this platform, not yours" from royalty_lag.TYPICAL or "no figure for this platform, and none assumed", which keeps its row rather than reading as a pass. Never measured: nothing in this app records the day a distributor reported a period, and the only date on file is the day the ARTIST uploaded the CSV, so royalty_lag.observed_days is deliberately not called and tests/test_reporting_lag_wired.py fails if anything reaches it. An account with no statements renders the section saying it has no reading. Known limit: a period missing BETWEEN two reported ones is not flagged, because a quarterly payor would false-alarm.
- Routes: GET /statements (full, row per store); GET /royalties (compact, links to /statements#reporting)
- Files: royalty_lag.py judge/expectation/TYPICAL; statements_engine.py reporting_lag / _lag_summary / _period_end; app.py (statements handler), app.py (royalties handler); templates/_reporting_lag.html; static/css/reporting-lag.css; tests/test_reporting_lag_wired.py
- Access: Follows the two pages it sits on. Artist tier and above; team seats through the Business room.

**Store check on a coverage gap**

Ask the stores whether a silent store actually carries the recording, by ISRC, and keep the answer.

- Because: POST runs coverage_check.check_gap(isrc, missing_sources) and persists the result with store.save_gap_check into gap_checks; the gap cards and the distributor letter both read it back. Apple and Deezer are keyless public lookups so a real answer comes back with no credentials at all; Spotify and Songstats add to it when their keys are set, and anything unreached is returned as "unchecked" with a reason rather than as "absent". A row with no ISRC is refused with ?checked=no-isrc instead of being matched by title.
- Routes: POST /statements/gaps/check
- Files: app.py:1625; coverage_check.py:164 availability / :222 check_gap; music_apis.py apple_has_isrc, deezer_has_isrc; spotify_provider.py; db.py save_gap_check/get_gap_checks (table gap_checks)
- Access: Artist tier and above. Team seats with the Business room and edit access.

**Sync clearance packs**

Build a cleared, ready-to-send pack for a track — audio, instrumental, clean edit, master and publishing clearance status — with a private public link a supervisor can open and request a licence from.

- Because: GET answered 200; POST uploads real audio into UPLOADS_DIR, mints a slug unique across every account (retried with a suffix on collision) and writes store.create_sync_pack. The public /s/<slug> page reads the row and counts a view; /s/<slug>/request writes an inbox row and a notification to the pack's owner. Delete is user-scoped, returns None (→404) for another account's pack and unlinks only files named sync_*. trust_score reads cleared packs back.
- Routes: GET/POST /sync/clearance-packs; POST /sync/clearance-packs/<pack_id>/delete; GET /s/<slug>; POST /s/<slug>/request; GET /sync (302 → /sync/clearance-packs)
- Files: app.py:9463 (sync_packs), app.py:9515 (delete), app.py:9548 (public), app.py:9560 (request), app.py:11355 (/sync redirect), app.py:9447 (_sync_audio_upload); db.py sync_packs table, create/list/update/delete_sync_pack, get_sync_pack_by_slug; templates/sync_packs.html, templates/sync_pack_public.html
- Access: The workspace is Artist tier and above ("/sync" in _PRO_PATHS); it is the Releases room's "sync-packs" card and "/sync" is in team_areas.EXTRA["business"], so a seat needs the matching room. /s/<slug> and /s/<slug>/request are anonymous — "/s/" is in _PUBLIC_PREFIXES (app.py:4803); the slug is the authorisation and an archived pack 404s.

**Tax view of Statements**

The same uploaded rows filed by tax year and payor, with the $600-per-payor 1099 mark.

- Because: GET /statements?view=tax answered 200 and ctx["tax_years"] is built by _tax_years() from store.get_statement_rows, using statements_engine.period_year to read shapes like "JUN-26". The old /tax and /tax-center addresses 301 to it (confirmed by test client).
- Routes: GET /statements?view=tax; GET /tax, /tax-center, /tax/<path>, /tax-center/<path> (301 redirects)
- Files: app.py:1547 (_tax_years), app.py:1578 (statements handler), app.py:12751 (tax redirects); statements_engine.py:63 period_year; templates/statements.html
- Access: Same as Statements: Artist tier and above; the redirect routes themselves also sit under the "/tax" prefix in _PRO_PATHS. Team seats via the Business room.

**Track lockbox**

Attach the paperwork that proves who gets paid for one recording, mark a slot not-applicable, and ask a named person to sign it.

- Because: POST writes real files into UPLOADS_DIR and updates the passport's lockbox dict through store.update_os_track_lockbox; the approver flow mints a token with store.add_sign_token and emails a link when emailer.configured(), leaving the link visible on the page either way. The delete route is scoped by get_os_track (owner-scoped) and only unlinks names matching the uploader's own uuid4-hex + "-" shape. rights_conflicts reads the lockbox back.
- Routes: POST /tracks/<track_id>/lockbox/<doc_key>; POST /tracks/<track_id>/lockbox/<doc_key>/delete
- Files: app.py:7323, app.py:7371, app.py:7312 (_is_lockbox_upload); artist_os.py LOCKBOX_DOCS, lockbox_report; db.py update_os_track_lockbox, delete_os_track_lockbox_file, add_sign_token (tables os_tracks, sign_tokens)
- Access: Artist tier and above ("/tracks" in _ARTIST_PATHS). Team seats: "/tracks" is in team_areas.EXTRA["publishing"], so a seat needs the Publishing room; writes need edit access.

**Trust Score**

A partner-facing 0-100 score over eleven factors of business hygiene, including whether statements are connected and whether splits are signed.

- Because: GET answered 200; the factors read catalog tracks, deals (signed splits), store.get_statements, non-suppressed fans, campaign scores, cleared sync packs, EPK fields and Pulse snapshots. Factors with nothing to measure are listed in "unmeasured" with the reason rather than drawn as a 0/10 bar. Recorded in score_history. Read back by capital_engine and valuation_engine.
- Routes: GET /trust-score
- Files: app.py:9693; trust_score.py:40 calculate; db.record_score/score_trend; templates/trust_score.html
- Access: Artist tier and above ("/trust-score" in _ARTIST_PATHS). Analytics room card "trust-score" (rooms.py:111).

**Valuation**

Catalog value as a 3x/4x/5x band on the run rate the account's own statement months produce, with a worst/average/best forecast and named value drivers.

- Because: GET answered 200; valuation_engine.build reads store.get_statement_rows and returns has_data:False with a zero band when there are none. The multiples come from catalog_value.MULTIPLES, the one source of truth, and the page flags thin history (months<3) and no-period statements instead of annualising silently.
- Routes: GET /valuation
- Files: app.py:3097; valuation_engine.py:113 build / :56 _drivers; catalog_value.py:32 band; statements_engine.py annualize; score_history.summarise + db.score_trend; templates/valuation.html
- Access: Artist tier and above ("/valuation" in _PRO_PATHS). Team seats through the Business room ("valuation" card).

**Vault**

Every release asset the account holds — uploads, press assets, cover art, rollout assets, saved press kits — listed, downloadable singly or as a zip, and deletable.

- Because: GET answered 200; the listing is assembled from store.list_vault_files, store.get_epk_assets, the EPK photo, campaign covers and rollout assets — all account-scoped reads. Upload writes through blob_store.save (R2 when configured, /uploads on disk when not) and store.add_vault_file. Download and zip use the listing itself as the allowlist, so a guessed id or a path the account does not own serves nothing; delete only unlinks names matching vault_/doc_/presskit_.
- Routes: GET /vault; POST /vault/upload; POST /vault/<file_id>/delete; GET /vault/<file_id>/download; POST /vault/zip
- Files: app.py:10274 (asset_vault), app.py:10281 (_render_vault), app.py:10454 (upload), app.py:10483 (delete), app.py:10510 (download), app.py:10536 (zip); blob_store.py save/remove/fetch/safe_local_path/url_for; db.py vault_files table; templates/vault.html
- Access: Artist tier and above ("/vault" in _ARTIST_PATHS). It is the Studio room's "vault" card, so a team seat needs the Studio room, not Business. Not owner-only.

### Partial

**Advance eligibility and Funding**

An indicative advance range from the account's own statements, shown as three comparable offers with a "record interest" button.

- Because: The eligibility half is real: capital_engine.advance_eligibility returns real:False and quotes nothing when there is no income, otherwise a band computed from annualised statement income. The marketplace half is illustrative and says so: funding_config.get_funding_data builds three offers from fixed provider names, terms, factors and multipliers (1.6x, 0.5x) off that one figure, and POST /funding/request submits nothing to anybody — it only writes a notification with a reference string. The page is parked off the sidebar (tests/test_sidebar_fold.py PARKED lists /funding as "illustrative").
- Routes: GET /funding; POST /funding/request
- Files: app.py:12351 (funding), app.py:12365 (funding_request); capital_engine.py:118 advance_eligibility; funding_config.py:14 get_funding_data; db.notify; templates/funding.html
- Access: Artist tier and above ("/funding" in _PRO_PATHS). Team seats: "/funding" is in team_areas.EXTRA["business"].

**Catalog (identifiers and catalog value card)**

Every song the account owns with its ISRC/UPC/ISWC, its Track Passport, and a catalog-value card.

- Because: The route starts from catalog_config.get_catalog_data(), which is hardcoded (1,248 tracks, 87 releases, a 76 health score and sample issues), and then overwrites summary, health, issues, catalog_value, tracks, releases, songwriters, publishers, splits, release_filter_options and recently_added with real figures — but only for accounts whose email is not demo@streetbanker.io. So on the demo account the hardcoded catalogue is what renders, and on a real account any key of get_catalog_data() not in that override list is still the seed value. The value card itself is real: catalog_value.band over the account's own annualised rows.
- Routes: GET /catalog (?view=passports); POST /catalog/add; POST /catalog/remove/<track_id>; GET /identifiers (302 → /catalog#identifiers)
- Files: app.py:2584 (catalog_page), app.py:2927 (add), app.py:2954 (remove), app.py:12444 (identifiers redirect), app.py:2717 (_passport_section); catalog_config.py:177 get_catalog_data; catalog_value.py:32 band; db.py catalog_tracks, os_tracks, track_mlc_checks; templates/catalog.html
- Access: Artist tier and above ("/catalog" and "/identifiers" in _PRO_PATHS). Publishing room card "catalog" (rooms.py:57), so a team seat needs Publishing.

**Free catalog sweep (public lead form)**

Three questions from a visitor with no account, answered with what a sweep checks and what it cannot know yet.

- Because: The lead half is real: store.add_inbox("catalog_sweep", ...) files the submission, wrapped so a failed write never costs the visitor the page. The result half is hardcoded — the four "checks" and three "limits" are literals in the handler, no scan runs, and the code says so explicitly ("It does not claim a scan has run, because none has").
- Routes: GET/POST /catalog-sweep
- Files: app.py:14269; app.py _SWEEP_ROLES; db.py add_inbox (table inbox); templates/catalog_sweep.html
- Access: Anonymous — "/catalog-sweep" is in _PUBLIC_EXACT (app.py:4853).

**Missing-royalties scan API**

A JSON scan that returns the account's recovery findings.

- Because: For a signed-in, non-demo account it returns recovery_engine.build output — proved: it returned the two findings computed from the uploaded CSV. For the demo session (and for any path where _session_is_demo() is true) it falls through to royalty_data.get_missing_royalty_findings(get_platform_catalog()), which is the hardcoded platform list, so the same endpoint answers with seed findings there.
- Routes: POST /scan/missing-royalties
- Files: app.py:14336; recovery_engine.py:89 build; royalty_data.py:730 get_missing_royalty_findings, :152 get_platform_catalog
- Access: Not in _PRO_PATHS or _ARTIST_PATHS, so required_tier is None — any signed-in account; anonymous is redirected to /login by plan_gate.

**Royalty report CSV**

A flat CSV of every statement row — title, source, amount, period.

- Because: With rows on file it writes the account's real rows (confirmed 200 on the smoke account). With none it falls through to royalty_data.get_songs() and exports the five invented demo songs' platform earnings under a different header — so an account with nothing uploaded downloads a file of somebody else's numbers named royalty-report.csv. The route also does not require a signed-in user for the demo branch (it guards `if user` only when reading rows).
- Routes: GET /reports/royalty-report/download.csv
- Files: app.py:2151; royalty_data.py:375 get_songs, :92 Song.platform_earnings
- Access: Artist tier and above by path ("/reports" in _PRO_PATHS, enforced by plan_gate); anonymous is redirected to /login by plan_gate before the handler runs.

**Spend Optimizer**

A suggested split of a release budget across four channels.

- Because: The four channels, their base percentages (40/25/15/20) and the three "avoid" lines are hardcoded in capital_engine.spend_plan; what is real is the shift — fan count from mls.list_fans and the click-through ratio from mls.event_counts move weight between buckets, and the logged spend total comes from store.list_expenses. So the frame is fixed and the adjustment is computed.
- Routes: GET /spend-optimizer (?budget= clamped 50-100000)
- Files: app.py:8627; capital_engine.py:79 spend_plan; templates/spend_optimizer.html
- Access: Artist tier and above ("/spend-optimizer" in _PRO_PATHS). Team seats: in team_areas.EXTRA["business"].

**Statement email drop-box**

A per-account email address that turns CSVs emailed by a distributor into statement rows, plus a rotate button and a round-trip self-test.

- Because: The ingest half is real — /webhooks/resend verifies the Resend signature, resolves the account by the recipient local part (store.user_by_ingest_token) and calls the same _ingest_statement the upload uses. The other half is env-gated and inert without it: emailer.inbound_configured() requires RESEND_WEBHOOK_SECRET and RESEND_INBOUND_DOMAIN, and without them the webhook aborts 404, dropbox-test returns a 400 "Drop-box not configured", and ctx["drop_box"] is None so no address is shown.
- Routes: POST /webhooks/resend; POST /statements/dropbox-new; POST /statements/dropbox-test
- Files: app.py:1275 (resend_webhook), app.py:1499 (dropbox_new_address), app.py:1510 (dropbox_test), app.py:1474 (_ingest_statement); email_provider.py:150 inbound_configured / :155 inbound_address / verify_webhook; db.py ingest_tokens (get_or_create_ingest_token, rotate_ingest_token, user_by_ingest_token)
- Access: /webhooks/resend is anonymous by design ("/webhooks/" is in _PUBLIC_PREFIXES, app.py:4813); the signature is the authorisation. The two buttons need a signed-in account holder and are refused to anyone working as someone else (_working_as_someone) — so a team seat or a partner acting on the artist's behalf cannot see or rotate the address.

**The MLC registry sweep**

Check every Track Passport ISRC against The MLC's public database and keep the sweep, so unregistered or partly claimed works show as mechanical money nobody is collecting.

- Because: The sweep, its bounded batch (PER_SWEEP=25), the summary and the storage are real code that writes recovery_mlc_sweeps, and the Royalties streams ledger reads the result back. The provider half is inert without credentials: MLCAdapter declares env_keys ("MLC_USERNAME","MLC_PASSWORD") and env_flag MLC_ENABLED, and on this checkout POST /recovery/mlc returned 302 to /recovery?mlc=off#mlc and wrote nothing. A passport with no ISRC is listed as uncheckable rather than looked up by title.
- Routes: POST /recovery/mlc (redirects to /recovery#mlc, or ?mlc=off / ?mlc=none)
- Files: app.py:3082; recovery_mlc.py:35 candidates / :50 sweep / earnings_by_title; signal_providers.py:2884 MLCAdapter, :3497 mlc_adapter; db.py add_recovery_mlc_sweep (table recovery_mlc_sweeps); templates/recovery.html
- Access: Artist tier and above. Team seats with the Business room and edit access.

### Stubbed

**Capital hub (Fan Royalty Passes, crowdfunding, royalty futures, staking, Roll the Dice)**

A monetisation concept board of passes, crowdfunding, a futures marketplace, staking pools and a dice game.

- Because: Every figure comes from capital_config.get_capital_data, which hardcodes them (318 of 500 sold, $6,200 of $10,000, three futures with fixed asking prices and yields, fixed APYs); its own docstring says "every one of these is a SIMULATED DEMO". Titles are borrowed from royalty_data.get_songs (the five invented demo songs). Nothing is read from or written to the account. GET returned 200, so it is reachable, and tests/test_sidebar_fold.py lists it as PARKED "Simulated demo" — no live nav entry links to it (the only /capital hrefs outside app.py, plans.py and team_areas.py are in backups/).
- Routes: GET /capital
- Files: app.py:12270; capital_config.py:20 get_capital_data; royalty_data.py:375 get_songs; templates/capital.html
- Access: Any signed-in account — plans.required_tier("/capital") returns None because /capital is in neither _ARTIST_PATHS nor _PRO_PATHS (plans.py only names it in world_for_path, where it maps to the "fan" world). Anonymous is redirected to /login. Team seats: "/capital" is in team_areas.EXTRA["business"], so a seat with the Business room reaches it.

**Find my lane (public)**

One situation in, one suggested lane out, with all three lanes printed underneath.

- Because: GET returned 200 but the handler only matches ?situation= against lanes_config.SITUATIONS and picks the matching entry from lanes_config.LANES — both fixed lists in the config module. Nothing is read from an account and nothing is written. Distinct from /royalty-lanes, which is the real per-track matrix.
- Routes: GET /lanes (?situation=)
- Files: app.py:14244; lanes_config.py LANES/SITUATIONS; templates/lanes_public.html
- Access: Anonymous — "/lanes" is in _PUBLIC_EXACT (app.py:4863). Note "/lanes" is also listed in team_areas.EXTRA["business"], which would put this public page in a seat's Business room.

**royalty_data demo money module**

The original hardcoded money model — platform balances, earnings trend, payouts, leak alerts, claims, fixes queue, rights conflicts, recovery summary.

- Because: _DEFAULT_PLATFORMS and _SONGS are literal lists; every getter derives from them. It is gated behind _session_is_demo() in build_dashboard_context (app.py:447) and _front_money_context, so a real account gets [] and 0.0 instead — but three live call sites still reach it regardless of the demo flag: /reports/royalty-report/download.csv on an empty account (app.py:2163), POST /scan/missing-royalties in its fallback branch (app.py:14352), and capital_config/_titles() for the /capital board. get_rights_conflicts is imported at app.py:279 but /conflicts no longer calls it.
- Routes: (no route of its own; reached through /reports/royalty-report/download.csv, /scan/missing-royalties, /capital and the demo dashboard context)
- Files: royalty_data.py:121 _DEFAULT_PLATFORMS, :192 get_earnings_trend, :730 get_missing_royalty_findings, :1444 get_rights_conflicts, :1508 get_recovery_summary; app.py:256 (import block), app.py:447 (demo gate); demo_accounts.py, demo_seed.py
- Access: n/a — module-level seed, surfaced only on the demo showcase account plus the three call sites above.

**Sample statement CSV**

A downloadable example statement for the walkthrough.

- Because: The eight rows are literals in the handler, including two deliberately untitled rows so the recovery scan has unattributed revenue to find. Fixed output by design, reading nothing from the account.
- Routes: GET /walkthrough/sample-statement.csv
- Files: app.py:9975; templates/walkthrough.html
- Access: Any signed-in account — the path is in neither tier list so required_tier is None; anonymous is redirected to /login by plan_gate (it is not in _PUBLIC_EXACT).

**Sync Deal Simulator**

Score a sync offer against a market range and produce risk flags and a counteroffer paragraph.

- Because: GET/POST answered 200 but sync_simulator.simulate is pure arithmetic over hardcoded constants — seven media types with fixed (low, high) bands and fixed multipliers for territory, term, exclusivity and all-media. It reads nothing from the account and writes nothing anywhere; the result is rendered and discarded. Its own docstring calls the ranges "heuristic market ranges".
- Routes: GET/POST /sync/deal-simulator
- Files: app.py:9575; sync_simulator.py:27 simulate, MEDIA_TYPES/TERMS/TERRITORIES; templates/deal_simulator.html
- Access: Artist tier and above ("/sync" in _PRO_PATHS). Team seats: "/sync" is in team_areas.EXTRA["business"]; it is also the Business room's "deal-simulator" card.

### Dead code

**Reporting-lag explainer (royalty_lag)**

Whether a store is actually late or just reporting on its normal delay, measured from the account's own statement history with a published table as the fallback.

- Because: Nothing imports it outside its own test. grep for "royalty_lag" across every .py and .html in the repo returns only royalty_lag.py itself and tests/test_royalty_lag.py:14 — no route, no template, no other module, and no nav entry names it. The module is complete and tested; it is simply not wired to anything a user can reach.
- Routes: (none — no route, nav entry or template references it)
- Files: royalty_lag.py (TYPICAL table, measured/typical/unknown verdicts); tests/test_royalty_lag.py
- Access: n/a — unreachable from any route.

> Noted by the reviewer as not yet written up in this area: One-sheet share link (/sheet/<token>) — the whole feature, not just the 301. The inspector's "Deal Room one-sheet" entry stops at GET /deal-room/onesheet → 301 /epk, but POST /onesheet/share (app.py:7208) is live and writes a real token+PIN share through store.upsert_onesheet_share, with regenerate and disable actions, a banner and up to three audio files chosen only from the account's own store.list_vault_files. GET/POST /sheet/<token> (app.py:7257) serves the public page (templates/sheet_public.html), PIN-gated, and logs a view via store.log_onesheet_view; POST /sheet/<token>/pitch (app.py:7286) files a supervisor's approach through store.add_inbox with a honeypot drop. Tables: onesheet_shares, onesheet_views (db.py:2874-2923). Anonymous by design — "/sheet/" is in _PUBLIC_PREFIXES (app.py:4817) and "/sheet" is in team_areas.EXTRA["marketing"]; the signed-in half is Artist tier ("/onesheet" in _PRO_PATHS). I proved every step: share saved, /sheet/<token> 200 signed out, pitch 302 ?sent=1, view stats {'total': 1}.; Hours Desk and invoicing — a whole money page with no entry. It is the last card of the money hub group itself (hubs.py:80 "Royalty Sweep & Banking" → ("hours", "/hours", "Hours Desk", "Bill your time, take bookings, approve collaborators")), a Business-room card (rooms.ROOMS "business"), and "hours" is in hubs._BASE_LIVE. Routes: GET /hours (app.py:13017), POST /hours/invoice (13054, store.create_hours_invoice + hours_engine.next_invoice_number, files an inbox trail), POST /hours/invoice/<invoice_id>/paid (13076), POST /hours/rate (13084, with a _HOURS_STARTER rate card), POST /hours/entry/<entry_id>/delete (13042, refuses to delete an already-invoiced line), plus the block/booking routes. Tables: hours_invoices, hours_rates, hours_entries, hours_submissions, hours_blocks, hours_bookings. hours_engine.py's docstring states every total is summed from stored rows with no projections. GET /hours answered 200 on my throwaway account.; Per-track MLC registry check — POST /tracks/<track_id>/mlc (app.py:7035). The Catalog entry cites db.py track_mlc_checks but names no route for it, and the "MLC registry sweep" entry covers only the bulk /recovery/mlc sweep. This is the single-track version: it asks signal_providers.mlc_adapter() by ISRC (or by title+artist when there is no ISRC), writes store.add_track_mlc_check into track_mlc_checks, and carries a second action — action=fill copies the registry's writers and publishers into the passport's songwriters/publishers ONLY where those fields are still empty, and deliberately no longer writes mlc_status prose. Partial for the same reason as the sweep: adapter.configured() is false without MLC_USERNAME/MLC_PASSWORD/MLC_ENABLED, and the route then 302s to /tracks/<id>?mlc=off#mlc having written nothing. Artist tier ("/tracks" in _ARTIST_PATHS); team seats need the Publishing room (team_areas.EXTRA["publishing"]).; GET /overview — the money front door itself. The inspector lists only POST /overview/goal. /overview (app.py:2428) answers with command_center_page(), whose money band is _front_money_context() (app.py:2472) rendered through templates/_front_money.html and _real_royalty_band.html: the goal ring read back from royalty_goals, the monthly trend and the two month tiles (_month_tile_labels, app.py:2439, which refuses to call an April statement period "This month"), and the "Money Left on the Table" card. That card is the honesty seam worth recording — for a signed-in real account it renders recovery_view.total_at_stake from recovery_engine.build, or the words "Not scanned" when no statement is uploaded, and it falls back to royalty_data's seeded money_left only when recovery_view is None (the showcase). Artist tier ("/overview" in _PRO_PATHS); "/overview" is in team_areas.WHOLE_ACCOUNT, so a seat without every room is bounced.; GET /registration (app.py:12636) — a rights route in _PRO_PATHS with no entry. It is a deleted feature that still answers: 302 to /tracks, with the handler docstring recording why ("the wizard only ever ran over the demo songs, so a real account saw an empty page"; PRO/MLC/SoundExchange/Content ID status now lives on each Track Passport). "/registration" is also in team_areas.EXTRA["publishing"]. Worth a Live-redirect row so the ledger explains an address a label or an old link may still hit.; GET /connections (app.py:2961) — in _PRO_PATHS beside the money pages and an Account-row card (rooms.EXTRA "connections" → "Data and connections"), with no entry. It is the page that says which money sources are actually feeding the engine: the integration list is a hardcoded seven-row literal but every `on` flag is a real read (spotify.pulse_configured(), store.get_pulse_profile, emailer.configured(), tour_dates_feed.upcoming, and store.get_statements for the "Royalty statements" row, which counts the account's own uploads), plus a deliberately honest `unavailable` list naming distributor analytics and PRO/MLC registration status as not connectable. Partial. Flagging in case it was assigned to an integrations/settings area instead — it sits in the money tier gate, so it should be in exactly one ledger.; Vault write and read paths from other desks, and one stub. The Vault entry says the listing includes saved press kits but names no route that puts them there. POST /epk/vault-save (app.py:3377) renders the press kit as one self-contained page and files a new dated version in the Vault (Live). POST /epk/asset/<kind>/from-vault (app.py:3897) goes the other way, promoting a Vault image into an EPK asset slot, and refuses anything that is not a png/jpg/jpeg/webp already in the account's own listing (Live). POST /api/vault/from-motion (app.py:10948) is a documented Stubbed route: 404 unless MOTION_HANDOFF_ENABLED is set, and 501 "The Motion hand-off is specified, not built" when it is — it belongs in the ledger precisely because it looks like a working intake.

## Releases and catalog

47 features: 23 Live, 11 Partial, 11 Stubbed, 2 Dead code.

### Live

**Studio Room (/room/studio)**

The Studio room's opening screen: a photographed master bus analyser carrying the artist's last measured master, the five-step path, their cover art, and six closing tiles.

- Because: the room opens on ONE thing and every figure on it is the Rack's own. db.latest_track_analysis is the last run of the browser meter to ITU-R BS.1770 / EBU R128: `integrated` is the LUFS readout, `true_peak` the dBTP headroom, `duration`, `sample_rate` and `channels` the line under the title. Both readouts are NULLABLE and a null prints as "Not measured yet" in words - this matters more here than anywhere else in the app, because -0.0 dBTP would read as a master clipping the ceiling and 0.0 LUFS as an extraordinarily loud one, so a zero standing in for an absence would be alarming and wrong. A genuine 0.0 still prints. No bit depth appears anywhere: track_analysis has no bit-depth column, so the unit does not print one. The needles are studio_room.needle(), mapping -30..0 LUFS onto the dial and clamping at both ends - a picture of the figure printed above, never a substitute. The path counts os_tracks, the measurement's own date, release_ready_store.stored_masters (a master the account OWNS, not a job that was started), artwork_config.list_uploads, and artist_os.clean_release over the catalogue; "Ready" is None until something is checked, never a zero.
- The photo-plate method, as the homepage EQ uses it: the hardware is ONE photograph, static/img/studio-bus-plate.webp (1993x640, 103KB — cropped from 2000x667 and its white ground cleared to alpha), and only the moving parts are drawn on it - the cover into the bay, the title and waveform into the display, the two figures into the LCD windows, and the two needles. Every region is a FRACTION of the plate, measured off the file itself with PIL and recorded in static/css/studio-room.css (bay 8.08%/12.34%/17.51%/70.47%, display 29.00%/12.66%/47.22%/38.75%, LCDs at 84.6% wide 12.0% with tops at 12.50% and 36.88%, dial centres 46.74% and 58.00%, needle pivot 88%). If the plate is ever regenerated those must be re-measured: the windows move and nothing in code will say so. Nothing on this screen is a vector drawing of a machine - the Stage room was withdrawn the same day for exactly that.
- The page from zero (owner's Studio spec, 2026-09-22): an account with nothing tracked, measured or on file meets an onboarding page rather than an empty instrument, in the spec's order - the header (subtitle "Turn a song into a release-ready package.", primary "Add your first song"), the Command Center's photographed three-screen plate drawn STATIC with PURPOSE / START HERE / GOOD TO KNOW, "Create your first Studio project", "What Studio keeps together" (gold icons - the spec's ruling over the mockup's green ticks), the five-stage workflow as education with Song record highlighted and no progress claimed, "Your tracks will appear here" beside "Nothing to review yet", contextual help, and the tiles under "More Studio tools" - a drawer that starts OPEN (owner, 2026-09-23: "a lot of people won't read, they need to see it"), closable but never closed by default. No date filter, no nought anywhere. The one door is /tracks?returnTo=/room/studio&from=song and the room answers the way back with "Your first song was added. Its Studio workspace is ready." only when a saved track exists (studio_room.done_line). /tracks is the Publishing room's, so a seat without it gets the card without its button and a line saying who adds songs. One track, cover or reading and the populated room returns untouched. The animated standby that ran on the analyser for an empty account is retired on this room; the fill reel stays for a populated unit's empty LCDs. The owner's mark on a page they hid (page_switches) stays on the drawer's tile from zero - the "Hidden" pill in the room's own status classes - because rooms.build keeps that card for the owner alone; the seven rooms dropped the state on the way to their zero drawers until 2026-09-23 (the Marketing room had it from the start), and the populated Studio, Stage, Analytics, Business and Releases rooms, whose tile feet were empty, show the same pill from the same day.
- Two tiles, not one: Release-Ready and Mix Check both answer "is this master ready" and the owner's mockup drew one Master Check tile, but they are still two pages, and one door over two pages is a door that lies (owner, 2026-09-22). They become one tile when they become one page.
- Covers are read (audit studio-1, 2026-09-23): the room lists the artist's cover files from UPLOADS_DIR, the folder /artwork/upload and /artwork/save write, and studio_room.covers() takes each file's `path`. Before this the route called an _uploads_dir() that app.py never defined, the NameError fell into a silent except, and covers() read `url`, which artwork_config.list_uploads never returns: every account with covers read "No art yet" and a cover-only account met the page from zero. The bay carries the newest cover; the gallery labels each one by kind and date ("Uploaded cover, 23 Sep 2026"), never by its storage key.
- The demo account is the showcase (audit studio-7, 2026-09-23): showcase = _session_is_demo() and the route passes zero=(not showcase) and studio_room.new_account(...), as the Marketing room does. The demo seed carries statements only, so the demo met the page from zero, with an "Add your first song" door a locked demo cannot use, beside the "Sample data" lamp. studio_room.showcase() is generated (Midnight Drive, -9.4 LUFS, -1.1 dBTP, five tracks, one master, one song blocked, "Sample reading" in place of a date), the unit's foot says "Sample data. Every figure in this room is generated for the example.", and the lamp is lit only on it. It carries no form and no done line. A real account never sees it.
- Routes: GET /room/studio (dispatched from /room/<room_key>)
- Files: app.py room_screen() -> app.py _studio_room(); studio_room.py STEPS, clock(), decibels(), source_line(), title_of(), analyser(), needle(), covers(), path(), zero_page(), done_line(), showcase(), new_account(), build(); templates/room_studio.html; templates/partials/cc_rack.html (the page from zero); static/css/studio-room.css; static/css/command-zero.css (the plate's rules); static/img/studio-bus-plate.webp; static/img/room-plate.webp; rooms.py ROOMS["studio"]; stores db.py (track_analysis, os_tracks), release_ready_store.py, artwork_config.py
- Access: Any signed-in account, as /room/<key>: no tier gate. Team seats need the "studio" room ticked; a tile whose page the seat cannot open is dropped. Anonymous redirected to /login.

**Artwork upload, save and delete**

Bring your own cover into the designer, pull a generated image into uploads, and take either back off the disk.

- Because: All three write or remove real files; ownership is the filename prefix (artup_<user>_ / aiart_<user>_), so another account's name cannot be addressed and 404s rather than being refused. /artwork/save accepts only https://image.pollinations.ai/ URLs and caps the download at 8MB.
- Routes: /artwork/upload (POST), /artwork/save (POST), /artwork/upload/delete (POST)
- Files: app.py:4073 artwork_upload(), app.py:4090 artwork_save(), app.py:4113 artwork_upload_delete(); artwork_config.py owned_prefixes()/owns()/list_uploads()/take_upload(); blob_store.py remove(); music_apis.fetch_image_bytes()
- Access: Artist/Pro/Label; Fan 402; anonymous gets 401 JSON. Studio room; read-only team seat refused.

**Clean Release (legacy URL)**

Old Clean Release address that now forwards into the Autopilot desk with the campaign kept.

- Because: Verified 302 to /releases/autopilot#clean; the page was folded into Autopilot and only the redirect remains.
- Routes: /releases/clean-release
- Files: app.py:6230 clean_release()
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Releases room for team seats.

**Clean Release (per-track score)**

Sixteen rights-and-readiness checks per Track Passport producing a 0-100 score, with red critical rows blocking submission.

- Because: artist_os.clean_release reads the track's own passport and lockbox plus _os_ctx signals (statement rows, live links, fans, rollout assets) - all real account reads. Two invented rows were removed on 2026-09-20: the Spotify pitch reminder (no reminder exists) and the social-assets row now requires a file actually uploaded to a rollout.
- Routes: /releases/autopilot#clean; also rendered on /catalog?view=passports and /tracks/<id>
- Files: artist_os.py:223 clean_release(); app.py _os_ctx() (above app.py:6884); templates/release_autopilot.html lines 240-289, templates/_catalog_passports.html
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Publishing or Releases room depending on the page it is read from.

**Clean Release certificate**

A print-ready page recording a 100-score Clean Release, its lockbox state and the moment it was generated.

- Because: Recomputes the score server-side and redirects to /releases/autopilot#clean when blocked or below 100 (verified: 302 on a fresh track); renders clean_certificate.html only on a real 100.
- Routes: /tracks/<track_id>/certificate
- Files: app.py:6306 clean_release_certificate(); templates/clean_certificate.html; store db.get_os_track
- Access: Artist/Pro/Label (path /tracks -> artist tier); Fan 402; anonymous to /login. Publishing room for team seats. Owner-scoped by get_os_track, so another account's track 404s.

**Cover art on a smart-link campaign**

Clears a campaign's cover art and removes the file when the uploader owns it.

- Because: _ml_owned scopes the campaign to the account and 404s otherwise; mls.clear_campaign_cover writes and _ml_drop_cover_file removes. Listed here because it is the other half of cover art, but the campaign and its store belong to the Smart Links area.
- Routes: /links/<cid>/cover/delete (POST)
- Files: app.py ml_cover_delete() (in the /links block, ~app.py:4400); links_store.py clear_campaign_cover()
- Access: Artist/Pro/Label (path /links -> artist tier); Fan 402; anonymous to /login. Marketing room for team seats; read-only seat refused.

**Metadata Passport**

Per-track completeness across seven identifier and credit fields, with an overall percentage and a CSV export.

- Because: _passport_rows reads the account's own catalog rows and their meta; os_rows adds artist_os.passport_report over the account's own passports; rr_masters marks tracks with a stored Release-Ready master. Verified 200, and the CSV export returns 200 text/csv with the same real values.
- Routes: /metadata-passport, /metadata-passport/export.csv
- Files: app.py:6346 metadata_passport(), app.py:6363 metadata_passport_export(), app.py _PASSPORT_FIELDS/_passport_rows() above; templates/metadata_passport.html; release_ready_store.py:663 masters_by_track()
- Access: Artist/Pro/Label; Fan 402 (verified); anonymous to /login. Publishing room for team seats. Linked from the Command Center tile (command_center.py:110) and the Artist EQ (artist_eq_config.py:184); note the handler sets active_page='identifiers', which no longer names a live page.

**Passport pull into the catalog record**

Copies songwriters and publishers from a Track Passport onto the matching catalog row, one click at a time.

- Because: _passport_resolves diffs real passport values against real catalog meta and only lists fields that exist on one side and not the other; the POST recomputes the values server-side from the user's own records and writes through store.set_catalog_track_meta. ISRC, UPC and Label were removed from the map because db._META_TO_PASSPORT already reads them through the link.
- Routes: /clean-release/resolve (POST)
- Files: app.py _RESOLVE_MAP/_passport_resolves() (above app.py:6280), app.py:6280 clean_release_resolve(); db.py:1910 set_catalog_track_meta()
- Access: No tier gate on this exact path (plans.required_tier('/clean-release/resolve') is None), so any signed-in account; anonymous is redirected to /login by the handler itself. Releases room for team seats; a read-only seat is refused by team_seat_gate.

**Public document signing**

A tokenised page where an approver with no account reads a lockbox document and signs or declines it.

- Because: /sign/ is in _PUBLIC_PREFIXES so it answers without a session; a valid token renders the document, the POST writes the decision into the artist's lockbox, burns the token and files an in-app notification for the artist. An unknown token, a token whose track or slot is gone, and a token the artist has since replaced (the approval carries the newest request's token) render the invalid state, so an old link cannot flip a decision a newer one recorded. A used link shows the decision that was made (it read "Signed" for a declined link until 2026-09-23) and no document.
- Routes: /sign/<token> (GET, POST)
- Files: app.py _sign_link, sign_document(); templates/sign.html; db.py sign_tokens table (db.py:297), add_sign_token/get_sign_token/use_sign_token; tests/test_sign_link_document.py
- Access: Anonymous, by single-use token only - no plan gate, no session. _is_public_path allows the '/sign/' prefix. Only the newest link sent to an approver is live.

**Registration wizard**

Deleted page that now forwards to the track list.

- Because: Verified 302 to /tracks. The docstring says the wizard only ever ran over the demo songs so a real account saw an empty page; PRO/MLC/SoundExchange/Content ID status now live on each Track Passport, and the code is a bare redirect.
- Routes: /registration
- Files: app.py:12636 registration()
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Publishing room for team seats.

**Release Autopilot (the release desk)**

One page per smart-link campaign holding readiness, the release arc, the plan, the kit and the per-track Clean Release scores.

- Because: GET returns 200 for an artist/pro/label account (test client), the campaign picker reads the account's own ml_campaigns, and every panel is computed from that account's rows; the fan plan gets the 402 upgrade page.
- Routes: /releases/autopilot (views: autopilot | calendar | ready)
- Files: app.py:6093 release_autopilot(); template templates/release_autopilot.html; engines artist_os.py; stores links_store.py (as mls), rollout_store.py (as ros), db.py
- Access: required_tier('/catalog'-family) = artist, so Artist/Pro/Label; Fan gets 402 upgrade.html. Anonymous is redirected to /login by plan_gate (app.py:4732). Not owner-only. Team seats reach it through the Releases room (team_areas.room_for_path -> 'releases'); not in _TEAM_BLOCKED.

**Release calendar .ics feed**

One-way iCalendar export of the same derived release and milestone events.

- Because: Returns 200 with text/calendar built from _scheduler_events for the signed-in account; the docstring states plainly it is an export, not a two-way sync, and the code matches.
- Routes: /releases/calendar.ics
- Files: app.py:12608 releases_ics()
- Access: Artist/Pro/Label; Fan 402; anonymous to /login (so the feed cannot be subscribed to by an unauthenticated calendar client). Releases room for team seats.

**Release Calendar / Release Scheduler**

Every dated campaign and rollout post laid out as months, swimlanes and lead-time warnings, with milestone overlays from date presets.

- Because: _scheduler_events reads ml_campaigns and ro_posts for the signed-in user only; the presets are pure date maths over each campaign's own release_date and nothing is stored or predicted.
- Routes: /releases/autopilot?view=calendar; /releases (302 to that view, query kept)
- Files: app.py _scheduler_events()/_release_calendar() (just above app.py:12597), app.py:12597 releases(); templates/_release_calendar.html included by templates/release_autopilot.html
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Releases room for team seats.

**Release readiness checklist (12 checks)**

Twelve derived pass/fail checks on the selected campaign, grouped into five meters with a percentage.

- Because: _release_checks reads real destinations, settings, variants, catalog rows, EPK and rollout posts; nothing is seeded. As of 2026-09-20 the rollout lamp requires a dated, non-rejected post on a linked rollout and the ISRC row points at the track's own passport when one exists.
- Routes: /releases/autopilot (Readiness panel), /releases/autopilot?view=ready
- Files: app.py _release_checks() (immediately above app.py:6093), _check_groups(); template templates/release_autopilot.html lines 99-150
- Access: Same as Release Autopilot: Artist/Pro/Label, Fan 402, anonymous to /login; team seats via the Releases room.

**Releases Room (/room/releases)**

The Releases room's opening screen: three figures on the rooms' three-window plate, the plan under it, the five-stage arc, what needs attention with a due day, the release itself, what is scheduled, per-recording Clean Release, and three closing tiles.

- Because: every figure is a count or a date over this account's own rows. The checks figure is app.py _release_checks over the chosen campaign, shown as passed/total rather than a score, and the group meters are _CHECK_GROUPS counted from those same checks. Days left is the campaign's own release_date less today. Scheduled drops is every ro_posts row with a scheduled_date across ros.list_campaigns; an account with NO rollout at all cannot be counted, so it reads "Not measured" with "Nothing scheduled yet", while a rollout whose posts carry no dates has been counted and reads 0 - the distinction _release_drops exists for. The arc's stage is the TIGHTEST window still ahead of the release date (ten days out is the 14-day plan, not the 60-day one), and with no release date no step is marked now at all. A task's due day is its own window in releases_room.CHECK_WINDOW counted back from release day, so it is traceable in one step; a check with no window, or a release with no date, shows a dash. The per-recording panel is artist_os.clean_release over store.list_os_tracks and is labelled as a different measurement from the campaign checks. Nothing on the page says a release was delivered: the note panel says in as many words that delivery is the distributor's to confirm and we cannot see it.
- Merged: Releases, Release Calendar and Release check were three cards pointing at /releases/autopilot with a different query string - one page behind three doors, which is the "no double tabs" rule broken as literally as it can be. They are this screen now. Rollout Studio, Sync Packs and Distribution are separate pages and stay as tiles; a tile a team seat cannot open is dropped rather than drawn (team_areas.allows).
- THE PLATE (owner, 2026-09-23: every room's rack is the shorter three-window plate; Studio excepted): the working room draws static/img/room-plate.webp through templates/partials/cc_rack.html, the same unit as the page from zero, with command-zero.css linked on both states. Its three screens are releases_room.rack_screens(): CHECKS PASSED (passed / total, never a score; "Read from your own records"), DAYS TO RELEASE (the campaign's own date less today, under "A plan — not proof of delivery", the zero page's own words; release day reads "Today" and a date already past counts the other way as DAYS PAST RELEASE, never a negative) and OPEN TASKS (the checks still open, "Of 12 checks, listed below"; all passed is a measured 0 with "All 12 checks passed"). The plate prints no names, so every screen carries its label. Nothing measured is words set as an absence - "Not measured" with "No release chosen" or "No release date set" - never 0 / 0, never 0 open and never a countdown of 0. Every line is ONE line on the short glass: measured with headless Chrome in Archivo at 12px, the widest (the plan line, 168px) fits its screen at every rack width the plate is drawn at (881px up), and the first wording ("Planned Oct 17, 2026 · not proof of delivery") wrapped and was clipped at a 1280 window. THE PLAN - the old RELEASE CLOCK's ribbon window (static/img/releases-plate.webp, 1859x846, left on disk) - is its own panel directly under the plate and its line ("The plan", the next five dated rollout posts soonest first, each date, caption and platform, or "Nothing scheduled yet" in words), so nothing the old plate showed is lost; the scheduled-drops figure stays on the line under the plate, just above the plan it counts. The clock's PLATE fractions, box(), plate_windows(), the fill reel (standby(), STANDBY_FILL) and the .rl-pl*/.rl-ribbon rules are gone. Neither screen nor panel is the five-stage arc: that is the gold rail further down, and drawing it twice would be the screen folding onto itself. On a phone the three screens stack (the plate's own container query) and the task table scrolls inside its panel, as the passport does, so the page never scrolls sideways at 375px.
- The page from zero (owner's Releases spec + mockup, 2026-09-23): an account with no release and no rollout meets an onboarding page rather than an empty plate, the 60/30/14-day arc, twelve empty checks, an empty calendar, a countdown or a distribution status, in the spec's order - the header (subtitle "Build the release record, check what is ready, and plan what happens next.", the account field kept, primary "Create your first release" -> /links/new?type=release&returnTo=/room/releases&from=releases-zero-state), the Command Center's photographed three-screen plate drawn STATIC with PURPOSE / START HERE / GOOD TO KNOW, "Start with one release" with the "Create your first release plan" card ("Create a release"; "What do I need before I start?" opens the spec's first-save list in place: type, working title, account) beside "What Releases will organize" - the four areas, each a door by its own room card (Release record -> autopilot, Readiness checks -> release-check, Rollout & calendar -> release-calendar, Distribution & sync packs -> distribution; words, not a door, for a seat that cannot open the page), the five-step workflow numbered 1-5 as the mockup numbers it with Create lit and no percentage, "Your release plan will appear here" (links into the workflow and the first-save list, since no page has anything to show before a release exists) beside "Nothing is scheduled yet", help, and "More Release tools" - a drawer that starts OPEN (owner's ruling the same day) with the tools under the four areas. THE RELEASE RECORD, as the spec asked to be confirmed: a release IS a campaign row of type "release" in links_store (ml_campaigns) - the record the twelve checks, the arc, the calendar and the rollout all read - so the builder opened on that type creates the release record itself, not "only a smart link"; there is no second release entity. The room says "Your first release was created. Its twelve checks are ready to run." only when a release is really on file (releases_room.done_line). The state is read in ONE try (releases, the chosen release, rollouts); a failed read is templates/room_releases_error.html at 503 ("We could not load Releases", Try again / Open the release desk), never a fresh account - the rollouts' old fallback to none-at-all is gone (_release_drops takes the rollouts the room already read). A seat without edit access gets the card without its door. One release or one rollout and the working room returns, dated rollout posts included. The animated standby that ran on the plate for an empty account is retired on this room, and since 2026-09-23 so is the fill reel its empty windows ran: the working screens say an absence in words. The owner's mark on a page they hid (page_switches) stays on the drawer's tile from zero - the "Hidden" pill in the room's own status classes - because rooms.build keeps that card for the owner alone; the seven rooms dropped the state on the way to their zero drawers until 2026-09-23 (the Marketing room had it from the start), and the populated Studio, Stage, Analytics, Business and Releases rooms, whose tile feet were empty, show the same pill from the same day.
- The demo account is the showcase, never the page from zero (audit releases-5, 2026-09-23; the Marketing room's pattern): the route passes zero=(not showcase) and new_account(...). A showcase login with no release and no rollout of its own is shown releases_room.showcase() - one example single ("Night Drive") 24 days out, the twelve checks with eight passed, four dated rollout posts and one passport row, dated from today and built in memory, never written to the database - with the Sample data lamp; a release or rollout the demo really made is shown instead, unmarked, and a real account never sees the example or the lamp. Nothing in the example is a door into a record that does not exist: its tasks and passport row are words, there is no release chooser, and the header door is the real builder (Create a release). An account under the read-only demo lock is offered no write door on this room at all: the header has none, and from zero the card says "This account is read only, so releases cannot be created here." in place of the button.
- Routes: GET /room/releases?campaign=<id> (dispatched from /room/<room_key>)
- Files: app.py room_screen() -> app.py _releases_room(), _release_drops(); templates/room_releases_error.html; templates/partials/cc_rack.html + static/css/command-zero.css + static/img/room-plate.webp (the owner's shorter three-window plate, 2026-09-23) (the page from zero and the working room); releases_room.py new_account(), done_line(), zero_page(), STAGES, CHECK_WINDOW, stage_now(), arc(), due_on(), tasks(), rack_screens(), ribbon(), headline(), build(); templates/room_releases.html; static/css/releases-room.css; rooms.py ROOMS["releases"]; stores links_store.py (ml_campaigns), rollout_store.py (ro_campaigns, ro_posts), db.py (os_tracks)
- Access: Any signed-in account, as /room/<key>: no tier gate. Team seats need the "releases" room ticked; a seat without a tile's page is not shown that tile. Anonymous redirected to /login.

**Release-risk notification**

Files one in-app notification when a dated track inside 14 days still has Clean Release blockers or an incomplete score.

- Because: Written inside the /releases/autopilot GET handler via store.notify into the notifications table, deduped against the account's existing notification titles; it is a real write on a real read, not a scheduled job.
- Routes: fired by GET /releases/autopilot
- Files: app.py:6093 release_autopilot() (the 'known = {n["title"] ...}' block); db.py notify()
- Access: Artist/Pro/Label; Fan 402. Fires for whichever account is loading the page (a team seat loading it writes into the artist's notifications).

**Rights conflicts**

Reports what disagrees across the account's own track passports and lockboxes.

- Because: rights_conflicts.summary reads store.list_os_tracks for the signed-in account; the demo-song version was removed on 2026-09-20. Note: this route returned HTTP 500 during my first probe today ('render_template() got multiple values for keyword argument conflicts' - the dashboard context carries its own demo 'conflicts' key); a concurrent edit landed the fix (context.update(found)) and a re-probe returned 200. Listed here because it reads os_tracks; it may equally belong to the publishing area.
- Routes: /conflicts
- Files: app.py:12460 conflicts(); rights_conflicts.py:202 summary(); templates/conflicts.html
- Access: required_tier = artist (in _PRO_PATHS), so Artist/Pro/Label; Fan 402; anonymous to /login. team_areas maps it to the Business room, so a seat without 'Money and business' is bounced.

**Show Passport (passport_os blueprint)**

The technical record a live production carries - contacts, personnel, input list, monitor mixes, playback, backline and show cues - with immutable published versions.

- Because: Verified end to end on a throwaway DB: create 302s to the detail page, the detail page renders 200, adding an input row persists, publish writes a frozen JSON snapshot into passport_versions (1 row), and both the change log and the version page render 200. Every handler goes through require_passport, which asks the database for ownership and 404s (not 403s) for another account's id. This is the tour/stage-rider passport, not the release Metadata Passport, despite the module name.
- Routes: /passports, /passports/ , /passports/new, /passports/<id>, /passports/<id>/identity, /passports/<id>/<section>/add|<row_id>/save|<row_id>/delete, /passports/<id>/playback, /passports/<id>/inputs/import, /passports/<id>/publish, /passports/<id>/archive, /passports/<id>/versions, /passports/<id>/version/<vid>, /passports/<id>/version/<vid>/archive
- Files: passport_os.py (whole module; bp at passport_os.py:21, init at passport_os.py:269, registered from app.py ~14500); passport_store.py (schema at passport_store.py:81, publish at :565, compare at :675, gaps at :733); templates/passport/index.html, detail.html, versions.html, version.html
- Access: No tier gate (plans.required_tier('/passports') is None), but plans.path_suite maps it to the 'tour' suite, which SUITE_ACCESS opens at Pro. gates_on() is true wherever RENDER is set or SUITE_GATES=on, so on every deployed service an Artist plan gets 402 (verified: 200 with gates off, 402 with SUITE_GATES=on). Owner accounts bypass the suite gate. Anonymous is redirected to /login. Stage room for team seats.

**Show Passport readiness gaps**

A plain list of what is missing before a passport is worth sending to a venue.

- Because: passport_store.gaps reads the built snapshot and returns facts (no input list, unassigned mixes, no safe starting state, no emergency contact); it deliberately returns no percentage, and the code matches that stated rule.
- Routes: /passports/<id> (gaps panel)
- Files: passport_store.py:733 gaps(); passport_os.py:109 detail()
- Access: Same as Show Passport: Pro on a deployed service via the tour suite gate; Stage room for team seats.

**Song-table link migration**

Start-up pass that gives every Track Passport a catalog row and every catalog row a passport, so the two lists stay one list.

- Because: Called unconditionally from db init (db.py:1311) on every boot; matches by ISRC then title, opens a row where there is none, and deletes nothing. It is a no-op once everything is linked.
- Routes: none - runs at boot
- Files: db.py:1311 (call site), db.py:3944 link_song_tables(); exercised by tests/test_tier_c_folds.py:183,198
- Access: Not user-facing; runs as the process, for every account in the database.

**Stage Room (/room/stage)**

The Stage room's working screen: the rooms' shared three-window plate (Cues, Channels, Passport), the saved cue list in its own panel under it, the Stage Plot designer, and four closing tiles - or, on an empty account, the page from zero.

- Because: two saved JSON blobs per account, read back without a second copy of the editors' rules. The show is db.get_light_show -> {name, bars, chans, cues[], pos{}, rot{}, rigName, dmxUniverse, dmxStart, dmxAddr{}}; a cue is {t, group, color, intensity, fade, note, look, move}; the plot is db.get_stage_plot plus db.get_stage_plot_image. Channels are DERIVED - bars times their 3 or 4 channel width - never typed, and a bar's DMX address mirrors lights-engine.js fixtureAddress(): its own patch if it has one, else in order from the start address, clamped to 512. The stage preview is drawn server-side from the saved positions; "truss" or "floor" is the editor's own reading of a bar's height (lights.js: p[1] < 0.5), not a stored field. The input list is stage_plot_catalog.as_input_rows - the same catalogue the editor uses, already mirrored server-side and guarded by tests/test_stage_plot_catalog.py against the two drifting apart. The passport version is passport_store.current_version, and a passport that has never been published has NO version - drawn as "Never published", not version 0.
- The room edits nothing. Every control the mockup drew that would change something - Add fixture, Update cue, the transport - is a link into the editor that owns it, and tests/test_stage_room.py asserts the room's own markup contains no form at all. A button that looks like it programmes a cue and does not is the dead control the 2026-09-22 audit found in Publishing.
- Substitutes (the owner's mockup could not be built as drawn): "Fade in / Fade out" is ONE Fade row, because a saved cue has one fade and two rows would print one number twice. "Main Plot (v1)" is just the plot's name - there is one plot per account and no versions. "Front Truss / Back Truss / Floor" is All / Truss / Floor, because the editor knows truss from floor and nothing about front or back. No phantom-power column: stage_plot_catalog leaves what the editor does not know empty rather than guessing, and says so.
- The page from zero (owner's Stage spec + mockup, 2026-09-23): an account with no shows, no tours, no plot, no light show and no passport meets an onboarding page rather than the desk or the plot editor, in the spec's order - the header (subtitle "Turn show details into a plan everyone can use.", primary "Add your first show" jumping to the card), the Command Center's photographed three-screen plate drawn STATIC with PURPOSE / START HERE / GOOD TO KNOW, "Create your first Stage project" with the first-show form IN the card (name optional, date, venue or a stand-in label, city - nothing else, per the spec's first-save rule), "What Stage keeps together" (three rows, gold icons that explain capabilities and do not look completed), the five-stage workflow as education with Show details lit, "Your shows will appear here" beside "Nothing to advance yet", help with the five questions, and the tools under "More Stage tools" - a drawer that starts OPEN (owner's ruling later the same day). One Show record for every tool: the form posts to the Tour desk's own POST /tours/new one_off=1, which now takes the name and a same-site returnTo and answers /room/stage?from=show; the room says "Your first show was added. Its Stage workspace is ready. Next, draw the stage plot." only when a saved show exists (stage_room.done_line). The state is read from every count the spec names in ONE try (shows and tours minus the Tour desk's Mock Up Tour and its invented shows, the light show, the plot, passports); a failed read is templates/room_stage_error.html at 503 ("We could not load your Stage workspace"), never a fresh account. A seat without edit access or the Tour desk in its rooms, and a plan without Tour, get the card without the form and a line saying who adds shows. One show, plot, light show or passport and the populated room returns untouched. The animated standby that ran on the desk for an empty account is retired on this room, and since 2026-09-23 so is the fill reel a populated desk's empty windows showed: an absence on the working room's screens is words. The plot editor never appears before a show exists. The owner's mark on a page they hid (page_switches) stays on the drawer's tile from zero - the "Hidden" pill in the room's own status classes - because rooms.build keeps that card for the owner alone; the seven rooms dropped the state on the way to their zero drawers until 2026-09-23 (the Marketing room had it from the start), and the populated Studio, Stage, Analytics, Business and Releases rooms, whose tile feet were empty, show the same pill from the same day.
- The demo account is the showcase, never the page from zero (audit stage-1, blocker, 2026-09-23; the Marketing room's pattern): the route passes zero=(not showcase) and new_account(...), so no showcase login meets the first-show form. Where the demo has no light show or plot of its own, stage_room.showcase_show() ("Sample show": six bars, eight cues) and showcase_plot() (drums, bass, guitar, keys, two vocals, three wedges, drawn by the editor's own catalogue) stand in, in memory and never saved; the cue list and the plot panel each carry a Sample pill (the plot's replaces Saved) and the plate's line says anything marked Sample is the example. The Sample data lamp is drawn only when something on the page really is sample - it used to be lit for any demo login, over a page from zero that had no sample on it. What the demo really saved is shown instead, unmarked. An account under the read-only demo lock is offered no write door: from zero the card says "This account is read only, so shows cannot be added here." instead of the form (whose POST only bounced at the lock), and the working room's plot editor is drawn read only with a line saying so.
- Tour: absent from this screen entirely (owner, 2026-09-22). Tour is its own suite and the suite strip is its door. "tours" stays a CARD of this room so /tours keeps its room, its team-seat access (team_areas.room_for_path) and its way back - the same shape Marketing uses for links.
- THE PLATE (owner, 2026-09-23: every room's rack is the shorter three-window plate): the working room draws templates/partials/cc_rack.html (static/img/room-plate.webp, 1774x421, command-zero.css linked on both states) with stage_room.rack_screens() on its three screens - Cues (the saved light show's cue count, "In <show>"), Channels (bars times their channel width, "N fixtures · universe U"), Passport ("Version N", or "Never published" - a passport has no version until a first publish). The new plate prints no names, so each screen carries its label. A reading is a figure (cz-screen-v--fig); an absence is words (cz-screen-v--none), never a 0: "No light show saved" (the room can be open on a tour show or a plot alone, so it names the light show), "No cues yet", "Nothing patched". The Show Control desk it replaced (static/img/stage-plate.webp, 1859x846, left in the repo but drawn nowhere) had a fourth, wide window, THE STAGE, carrying the CUE LIST - never a picture of the plot, which has its own panel and that panel is the real designer. Nothing is lost: that window is now its own panel ("Cue list", .sg-cuebox) directly under the plate and its line, before the Stage plot panel - the first six cues in time order (time, look, group, intensity) with "N more in the Light Designer", or, with no cues, the blueprint invitation (an illustration, never a reading) that opens /lights. stage_room.PLATE/box()/plate_windows() and the standby fill reel went with the desk. Tour stays off the working page (no /tours).
- Routes: GET /room/stage (dispatched from /room/<room_key>)
- Files: app.py room_screen() -> app.py _stage_room(); stage_room.py STEPS, timecode(), rig(), address_of(), fixtures(), fixture_groups(), cue_name(), cues(), span(), plot(), figures(), rack_screens(), path(), new_account(), done_line(), zero_page(), build(); templates/room_stage_error.html; templates/partials/cc_rack.html + static/css/command-zero.css + static/img/room-plate.webp (the owner's shorter three-window plate, 2026-09-23) (the page from zero and the working room alike); tour_os.py create() (one_off: name, returnTo); templates/room_stage.html, templates/_sg_inputs.html; static/css/stage-room.css; rooms.py ROOMS["stage"]; engines stage_plot_catalog.py, passport_store.py; stores db.py (light_shows, stage_plots, stage_plot_images), passport_store.py (passports, passport_versions)
- Access: Any signed-in account, as /room/<key>: no tier gate. Team seats need the "stage" room ticked; a tile whose page the seat cannot open is dropped. Anonymous redirected to /login.

**Stage-plot import into the input list**

Seeds a passport's input list from the channel list derived from the artist's drawn stage plot.

- Because: passport_store.import_inputs_from_plot reads db.get_stage_plot (the stage_plots table, per user) through stage_plot_catalog and writes real passport_inputs rows, appending by default and leaving patch/stagebox/performer blank rather than inventing them. It catches OperationalError so a deployment without the stage-plot schema answers 'no plot' instead of 500.
- Routes: /passports/<id>/inputs/import (POST)
- Files: passport_store.py:458 get_stage_plot(), :481 import_inputs_from_plot(); passport_os.py:174 import_inputs(); db.py:2487 get_stage_plot(); stage_plot_catalog.py
- Access: Same as Show Passport. Read-only team seat refused on the POST.

**Track Passport CSV import**

Bulk-creates up to 200 passports from a CSV, mapping known columns straight into each new passport.

- Because: Reads the uploaded file, maps _CSV_PASSPORT columns and writes through store.add_os_track + update_os_track_passport; a decode or CSV error is swallowed and the user is returned to the passports page rather than shown a stack trace.
- Routes: /tracks/import (POST), /tracks/add (POST)
- Files: app.py:6922 os_tracks_import(), app.py:6958 os_tracks_add(), app.py _CSV_PASSPORT/_passports_home() above; db.py:3899 add_os_track()
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Publishing room; read-only team seat refused.

**Track Passport detail**

One recording's 25 metadata fields, notes, Clean Release, royalty lanes, rights lockbox, MLC panel and stored Release-Ready master.

- Because: Verified 200; get_os_track is owner-scoped and a foreign id 404s; POSTing the form persists (a written ISRC came back on the next read and propagated to the catalog row's meta via db._META_TO_PASSPORT).
- Routes: /tracks/<track_id> (GET), /tracks/<track_id>/passport (POST), /tracks/<track_id>/delete (POST)
- Files: app.py:6970 os_track_detail(), app.py:7090 os_track_passport(), app.py:7452 os_track_delete(); templates/os_track_detail.html; artist_os.py PASSPORT_FIELDS/PASSPORT_NOTES; db.py:4073 update_os_track_passport()
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Publishing room for team seats; a read-only seat is bounced with ?team=readonly on the POSTs.

**Track Passports (the song list inside Catalog)**

Each song once, carrying its passport completeness, Clean Release score, lockbox caps, ISRC, latest MLC check and certificate eligibility.

- Because: _passport_section joins catalog_tracks to os_tracks through passport_track_id, adds any passport with no catalog row so nothing is hidden, and computes every column from that account's own rows; verified 200 at /catalog?view=passports.
- Routes: /catalog?view=passports
- Files: app.py _passport_section() (just below app.py:2584); templates/_catalog_passports.html; db.py list_os_tracks()/get_catalog_tracks()
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Publishing room (rooms.py card 'track-passports').

### Partial

**Add a song to the catalog (with metadata enrichment)**

Saves a song to the catalog and best-effort fills ISRC/UPC/label from Deezer, then songwriters and publishers from The MLC by that ISRC.

- Because: The save and the Deezer lookup are real and keyless (music_apis.deezer_track_metadata, cached in api_cache); the MLC credits hop returns None on every deployment where MLC_ENABLED/MLC_USERNAME/MLC_PASSWORD are unset, so credits are absent rather than wrong. Duplicate title+artist returns 409.
- Routes: /catalog/add (POST, JSON), /catalog/remove/<track_id> (POST, JSON)
- Files: app.py:2927 catalog_add(), app.py:2954 catalog_remove(), app.py _mlc_credits() just above; db.py:1782 add_catalog_track(), db.py:1962 remove_catalog_track(); music_apis.py:182 deezer_track_metadata()
- Access: Artist/Pro/Label (path /catalog); Fan 402; anonymous gets 401 JSON {ok:false,error:'sign_in'}. Publishing room; a read-only team seat is refused with 403 JSON by team_seat_gate.

**AI cover generation**

Turns a text prompt into an album-cover image URL plus a suggested colourway and layout.

- Because: The image is real: the route builds a Pollinations.ai URL (no key, browser loads it directly) with a reusable seed for remixes. The 'suggestion' half is not a model - artwork_config.suggest_from_prompt is a hard-coded keyword-to-colourway table with a word-count rule for the layout, and its own note admits the seam.
- Routes: /artwork/generate (POST, JSON)
- Files: app.py:4050 artwork_generate(); artwork_config.py:86 suggest_from_prompt(), artwork_config.py MOOD_KEYWORDS
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Studio room; read-only team seat refused (POST).

**Catalog**

The account's own song list with identifiers, releases grouped by UPC, songwriter and publisher aggregates, and a health readout.

- Because: For a real account the route overwrites catalog_config.get_catalog_data()'s invented 1,248-track showcase with zeros and the account's own rows, and my_tracks/my_releases/my_writers/my_publishers are all real. The demo account (email demo@streetbanker.io) is deliberately exempted and still renders the fictional Synthwave Surfer catalogue, valuation and issue counts.
- Routes: /catalog (?view=catalog|passports)
- Files: app.py:2584 catalog_page(); templates/catalog.html, templates/_catalog_passports.html; catalog_config.py:177 get_catalog_data(); db.py:1934 get_catalog_tracks()
- Access: required_tier = artist, so Artist/Pro/Label; Fan gets 402 (verified). Anonymous to /login. Publishing room for team seats; not owner-only.

**Catalog sweep lead form (public)**

Asks a visitor three questions, files the answer as a lead, and says plainly what a sweep checks and what it cannot yet know.

- Because: The lead write is real (store.add_inbox into the platform inbox, wrapped so a failure never costs the visitor the page), but the four 'checks' and three 'limits' shown back are hard-coded copy; the page states explicitly that no scan has run because the engine reads uploaded statements and there are none. Verified 200 signed out. This sits at the boundary with the Royalty Sweep area.
- Routes: /catalog-sweep (GET, POST)
- Files: app.py:14269 catalog_sweep(); templates/catalog_sweep.html; db.py add_inbox()
- Access: Anonymous - _PUBLIC_EXACT. No plan gate, no room.

**Cover Studio (artwork designer)**

Compose cover art in the browser from colourways, layout templates, fonts and aspect presets, with the artist's own uploads listed beside it.

- Because: The designer is real client-side SVG and the uploads listing is the account's own files read off disk by prefix. The quick-fill title list is not: artwork_config.get_artwork_data pulls royalty_data.get_songs(), the invented Synthwave Surfer catalogue, for every account - the module docstring's claim that titles come from 'the live catalog' is contradicted by the code.
- Routes: /artwork
- Files: app.py:4039 artwork(); templates/artwork.html; artwork_config.py:73 get_artwork_data(), artwork_config.py list_uploads(); royalty_data.py:375 get_songs()
- Access: Artist/Pro/Label; Fan 402 (verified); anonymous to /login. Studio room for team seats (rooms.py 'artwork').

**Identifiers (ISRC / UPC / ISWC)**

A per-song table of ISRC, UPC, label, release date and ISWC with coverage counts, shown inside the Catalog page.

- Because: ISRC/UPC/label/release date come from the account's own catalog meta, which db.get_catalog_tracks reads through the passport link. The ISWC column is only ever filled from a stored MLC check's work code (artist_os.mlc_evidence), so with MLC_ENABLED unset it is empty for every row and ids_with_iswc is always 0.
- Routes: /catalog#identifiers; /identifiers (301-style 302 to /catalog#identifiers, verified)
- Files: app.py:2584 catalog_page() (ids_rows block), app.py:12453 identifiers(); templates/catalog.html
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Publishing room for team seats.

**ISRC store diagnostic**

Prints what Deezer, Spotify and Songstats each say about one ISRC, and what they could not say.

- Because: Deezer answers keylessly, so the deezer block is real on any deployment. The Spotify id needs SPOTIFY_CLIENT_ID/SPOTIFY_CLIENT_SECRET and the Songstats block needs SONGSTATS_API_KEY; without them both come back empty with a note rather than inventing coverage. No credential value appears in the reply.
- Routes: /isrc/diag (?isrc=&probe=1)
- Files: app.py:9225 isrc_diag(); coverage_check.py:78 _spotify_url_for_isrc(), :136 spotify_track_id_for(), :145 _songstats_links(); signal_providers.py:1235 SongstatsAdapter
- Access: Owner-only: _owner_or_404 (app.py ~10100) 404s for anybody whose email is not an owner hash or in OWNER_EMAILS, and for any request inside a team seat. No tier gate otherwise; anonymous is bounced to /login.

**Release kit text export**  *(status corrected on review)*

Downloads the kit and plan for one campaign as a single plain-text file.

- Because: The route (C:/Users/17049/OneDrive/Desktop/claude/music/mah-login/app.py:6192 autopilot_kit_export) is real and owner-scoped — mls.get_campaign is user-scoped and a foreign id aborts 404 — but every line of the file it writes comes from artist_os.release_kit (artist_os.py:488) and artist_os.campaign_plan (artist_os.py:520), which this same ledger grades Stubbed. I read both: they are fixed template strings and fixed window/task lists with [brackets] for the unknowns; the only account-derived values interpolated into the whole bundle are the campaign title, release date and smart-link slug. Grading the generator Stubbed and its export Live reads to a ledger user as though a real kit is exported. Same standard as the Release Kit entry -> Partial (plumbing real, payload hard-coded).
- Routes: /releases/autopilot/kit.txt?campaign=<id>&days=<n>
- Files: app.py:6191 autopilot_kit_export()
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Releases room for team seats.

**Rights & Split Lockbox**

Eight rights documents per track: upload a file, mark one not applicable, or email an approver a signature link.

- Because: Upload, not-applicable and detach all persist into os_tracks.lockbox and the uploads directory, and lockbox_report feeds the Clean Release blockers - all real. The approver email only goes out when emailer.configured() (RESEND_API_KEY); with it unset the token row is still written and the sign link stays visible on the page, so the invitation is never actually delivered.
- Routes: /tracks/<track_id>/lockbox/<doc_key> (POST), /tracks/<track_id>/lockbox/<doc_key>/delete (POST)
- Files: app.py:7323 os_lockbox_update(), app.py:7371 os_lockbox_file_delete(), app.py _is_lockbox_upload() above; artist_os.py:94 LOCKBOX_DOCS, artist_os.py:108 lockbox_report(); db.py:4080 update_os_track_lockbox(), db.py:4087 delete_os_track_lockbox_file(); blob_store.py remove()
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Publishing room; read-only team seat refused. get_os_track is owner-scoped so a foreign track and an unknown doc_key both 404.

**Rollout Engine (Rollout Studio)**

Generates a dated social rollout - phased posts, captions, hashtags and edit plans - with one tracked smart-link variant per post.

- Because: The campaign, assets, posts and per-post attribution are all real rows (ro_campaigns/ro_assets/ro_posts joined to ml_variants and ml_events), and generation is honest deterministic templating that never claims to have rendered a video. Once every post is out of draft the overview asks rollout_learning for a learned next step from this account's past rollouts (campaign["user_id"]). Until 2026-09-23 that expression read an undefined `user` and the page was a 500 at exactly that moment; fixed and held through the real pages by tests/test_rollout_overview_reviewed.py (approve every post, reject every post, and the learned line reaching the page).
- Routes: /rollout-studio, /rollout-studio/new, /rollout-studio/<cid>, /rollout-studio/<cid>/generate, /rollout-studio/<cid>/plan (?view=list|board|calendar), /rollout-studio/<cid>/performance, /rollout-studio/<cid>/socials, /rollout-studio/<cid>/delete; 301s: /posts, /storyboard, /calendar
- Files: app.py rollout_dashboard(), rollout_new(), rollout_generate(), rollout_overview(), rollout_plan(), rollout_performance(), rollout_socials(), rollout_delete(); rollout_engine.py, rollout_store.py, rollout_learning.py; templates/rollout_dashboard.html, rollout_new.html, rollout_overview.html, rollout_plan.html, rollout_performance.html, rollout_socials.html; tests/test_rollout_overview_reviewed.py
- Access: required_tier = artist, so Artist/Pro/Label; Fan 402 (verified); anonymous to /login. Marketing room for team seats; read-only seat refused on every POST.

**Track Passport list page (/tracks)**

Redirects into the Catalog's passports view for every plan that has the Catalog page.

- Because: The redirect half works (verified 302 to /catalog?view=passports for artist/pro/label). The other half - the render_template('os_tracks.html') fallback for a plan without /catalog - is unreachable: plans.required_tier('/tracks') is 'artist', so the only plan that would take that branch (fan) is stopped by plan_gate with a 402 first (verified: Fan gets 402 on /tracks). templates/os_tracks.html is referenced nowhere else (grepped across .py and .html).
- Routes: /tracks
- Files: app.py:6884 os_tracks(); dead branch at app.py:6905; dead template templates/os_tracks.html
- Access: Artist/Pro/Label (redirect); Fan 402; anonymous to /login. Publishing room for team seats.

### Stubbed

**Campaign Plan (14/30/60 day)**

A windowed rollout plan with tasks, a creator brief and ad concepts, flagged for windows the release date has already passed.

- Because: artist_os.campaign_plan returns fixed window/task lists chosen only by the day count; the one computed thing is the 'passed' flag, which is date maths against the campaign's real release_date.
- Routes: /releases/autopilot#plan (?days=14|30|60)
- Files: artist_os.py:512 campaign_plan(); app.py:6093; templates/release_autopilot.html lines 161-206
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Releases room for team seats.

**Discogs pressing lookup and attach**

Looks a song up on Discogs and attaches the chosen pressing, filling only passport fields that are still empty.

- Because: With DISCOGS_ENABLED/DISCOGS_TOKEN unset the adapter is not configured, /catalog runs no lookup at all, and the attach POST redirects to ...?discogs=off without writing (verified). The fill map deliberately excludes credits - a third-party database does not get to make a rights claim - and discogs_links records which fields it filled.
- Routes: /tracks/<track_id>/discogs (POST); lookup surfaced on /catalog?view=passports&discogs=<track_id>
- Files: app.py:2858 os_track_discogs(), app.py _DISCOGS_OFF/_DISCOGS_FILLS/_discogs_state() above app.py:2858; signal_providers.py:1773 DiscogsAdapter; db.py:4183 set_discogs_link()
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Publishing room; read-only team seat refused.

**Distribution guide (public)**

Explains who delivers releases, what a package needs and which parts are the partner's.

- Because: Renders entirely fixed copy from distro_config (GUIDE, WORKFLOW, CHECKLIST, INTEGRATIONS, PARTNER). There is no delivery code anywhere behind it: INTEGRATIONS lists every store row as 'Delivered through partner' and 'Direct platform connections from Street Banker' as 'Coming soon'. Verified 200 signed out.
- Routes: /distribution
- Files: app.py:14168 distribution_guide(); distro_config.py; templates/distribution_public.html; rooms.py:120 (the Releases room card)
- Access: Anonymous - _PUBLIC_EXACT. Also carried as a Releases room card for signed-in accounts; Releases room for team seats.

**Metadata Passport explainer (public)**

Sets out the seven metadata records, what a conflict looks like and what happens to the information.

- Because: Renders fixed passport_config data (CATEGORIES, CONNECTED, ISSUES, USE, STANDARDS); everything shown is a labelled example and nothing reads an account. Verified 200 signed out.
- Routes: /metadata
- Files: app.py:14153 passport_public(); passport_config.py; templates/passport_public.html
- Access: Anonymous - _PUBLIC_EXACT. Publishing room for team seats when signed in.

**MLC check on a track**

Asks The MLC about one recording by ISRC (or title+artist), stores the answer, and can fill empty songwriter/publisher fields from a stored match.

- Because: The adapter refuses honestly with no key: with MLC_ENABLED/MLC_USERNAME/MLC_PASSWORD unset the POST redirects to /tracks/<id>?mlc=off#mlc and writes nothing (verified). The store side (track_mlc_checks) and the fill rule - evidence never overwrites a typed value, and no status sentence is composed any more - are real code waiting on the key.
- Routes: /tracks/<track_id>/mlc (POST)
- Files: app.py:7035 os_track_mlc(), app.py _track_mlc_state() above; signal_providers.py:2884 MLCAdapter; artist_os.py:145 mlc_evidence(); db.py:4135 add_track_mlc_check()
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Publishing room; read-only team seat refused.

**Motion hand-off receiver**

The endpoint a Motion 'send to Street Banker Vault' button would post a finished render to.

- Because: 404s unless MOTION_HANDOFF_ENABLED is set; with it on it returns 501 with the message that the hand-off is specified, not built. It writes nowhere and Motion has no outbound call to make.
- Routes: /api/vault/from-motion (POST)
- Files: app.py:10948 vault_from_motion(); rollout_config.py:41 MOTION_HANDOFF_FLAG; spec at docs/MOTION_HANDOFF.md
- Access: No tier gate, so any signed-in account when the flag is on; anonymous to /login. Off by default on every deployment.

**Release check (public)**

A tickable pre-delivery checklist that counts how much of a release package is ready.

- Because: The checklist is the fixed distro_config.CHECKLIST; state lives only in the ?have= query string and nothing is stored against an account. It does validate ticks server-side against the real requirement slugs so a hand-edited URL cannot inflate the readout. Verified 200 signed out.
- Routes: /release-check; the Releases room's 'Release check' card points instead at /releases/autopilot?view=ready
- Files: app.py:14021 release_check(); distro_config.py CHECKLIST; templates/release_check.html; rooms.py:119
- Access: Anonymous - it is in _PUBLIC_EXACT (app.py ~4642). Open to every plan and to team seats (Releases room).

**Release Kit**

Captions, short-form ideas, an email, an SMS and a playlist pitch for the selected campaign.

- Because: artist_os.release_kit returns hard-coded template strings with only the campaign's title, release date and smart-link URL interpolated, and marks the rest with [brackets]; there is no model call anywhere in the path.
- Routes: /releases/autopilot#kit
- Files: artist_os.py:480 release_kit(); app.py:6093 (kit=...); templates/release_autopilot.html lines 206-240
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Releases room for team seats.

**Release Signal (public)**

Explains what a pre-release audio read would contain, and refuses to accept an upload.

- Because: Renders release_signal.get_release_signal_config() and takes no file; the docstring's reason - no analysis provider is connected, and returning an invented genre would be a fake scan - matches the code, which has no upload field or provider call. Verified 200 signed out.
- Routes: /release-signal
- Files: app.py:13872 release_signal_page(); release_signal.py; templates/release_signal.html
- Access: Anonymous - _PUBLIC_EXACT. Analytics room for team seats (team_areas EXTRA 'analytics').

**Rollout Engine explainer (public)**

Describes the rollout product before an account is asked for, with a labelled example campaign.

- Because: Fixed copy from rollout_config (TOUR_SECTIONS, WORKFLOW, SAMPLE, STATUSES, PLAN_LENGTHS); the sample is labelled as one and the page states plainly that nothing posts itself. Verified 200 signed out.
- Routes: /rollout
- Files: app.py:14199 rollout_public(); rollout_config.py; templates/rollout_public.html
- Access: Anonymous - _PUBLIC_EXACT. Marketing room for team seats when signed in.

**Rollout publishing routes**

Shows which social platforms a post could actually be published to.

- Because: social_providers.PROVIDERS marks only 'manual' as publishing; every other row is False and the module states in its own docstring that there is no upload code behind any platform. Present credentials report 'not connected' rather than 'configured', so the page cannot claim a route that does not exist.
- Routes: /rollout-studio/<cid>/socials
- Files: app.py:10939 rollout_socials(); social_providers.py:24 PROVIDERS, :49 provider_status(); templates/rollout_socials.html
- Access: Artist/Pro/Label; Fan 402; anonymous to /login. Marketing room for team seats.

### Dead code

**Cover store-spec check (artwork_check.py)** - Live

Measures a cover file against distributor requirements - square, 3000px, RGB, no alpha, size, sharpness, not blank - and lists the rules it cannot settle.

- Because: Wired 2026-09-21. POST /artwork/check (app.py:4106 artwork_cover_check) reads one uploaded file, measures it and returns the verdict as JSON; nothing is written to disk. The Cover Studio panel that calls it is templates/artwork.html:299-317 with its behaviour at :882. Verified in a browser against a real 3000px cover (clean) and a 1200px one (size named as the one thing a store would refuse).
- Verdicts: pass / review / fix, plus not-checked when the image library is missing. not-checked is its own state and is never reported as a pass, so a deployment without Pillow says the check did not run.
- Honesty: the rules no file inspection can settle always come back with the result, so a pass is never mistaken for a guarantee. SPEC figures are the ones distributors publish and move; DSP_NOTE says so on every result.
- Routes: POST /artwork/check (signed in; refuses a file over 24 MB)
- Files: artwork_check.py (check(), unavailable(), SPEC, UNCHECKED); app.py:4106; templates/artwork.html:299-317 and :882; requirements.txt (Pillow, added for this); tests/test_artwork_check.py (measurements) and tests/test_artwork_check_wired.py (the route)
- Access: any signed-in account. No plan gate.

**Show Passport documents**

A per-passport list of rider, stage-plot, patch-list and similar attachments.

- Because: The table, add_document, documents() and delete_document all exist in passport_store and the documents list is passed into detail.html, but grepping templates/passport/*.html for 'documents' returns nothing and passport_os registers no upload or delete route - so no document can ever be added or seen. build_snapshot and the version diff still carry the (always empty) section.
- Routes: none (the data is passed to /passports/<id> and never rendered)
- Files: passport_store.py:511 add_document(), :524 documents(), :531 delete_document(), passport_documents table at passport_store.py:229; passport_os.py:109 detail() passes documents=...
- Access: Unreachable by any account.

> Noted by the reviewer as not yet written up in this area: Street Banker Certified — /certified (C:/Users/17049/OneDrive/Desktop/claude/music/mah-login/app.py:7156 certified_page, helper _os_full at app.py:7150; artist_os.py:420 CERT_LEVELS and artist_os.py:424 certification(); templates/certified.html). Six-rung ladder (Unranked -> Upstream Ready) with the next requirement named, computed from _os_summary/_os_ctx over the account's own os_tracks, lockboxes, royalty lanes, fan rows and statement rows — no seeded data anywhere in the path. LIVE: verified 200 for an artist account and 402 for Fan on a throwaway DB. It is a sidebar entry (hubs.py:128 "Certified — Six rungs computed from your real record") and a Publishing-room card (rooms.py:57), sits beside 'catalog' and 'track-passports', and '/certified' is in plans._ARTIST_PATHS. The ledger uses artist_os.certification for passport_cert on /catalog?view=passports but never lists the page it belongs to.; Approver's document download — GET /sign/<token>/document (app.py:7443 sign_document_file). Public: '/sign/' is in _PUBLIC_PREFIXES, so an approver with no account fetches the lockbox contract file by token alone; verified 200 with the file bytes from an anonymous client. The 'Public document signing' entry lists only /sign/<token> (GET, POST). Worth its own line because it is the one path that hands a private rights document to an unauthenticated caller — and unlike the POST (gated on `not row["used"]`) this handler has no `used` check at all: verified 200 still returning the file after the token had been burned by a signature.; Rollout learning — rollout_learning.py, reached at app.py:10694 (suggested_platforms) and app.py:10776 (next_action_line) via the _rollout_learning helper at app.py:10648. Real, not templated: it reads ml_variants and ml_events conversion history (which survives clear_posts) and, when the artist ticks no platforms on /rollout-studio/new, picks the platforms their past rollouts actually converted on, falling back to the fixed list when traffic is too thin to say. The ledger names rollout_learning.py in the Rollout Engine entry's file list but describes generation as purely deterministic templating, so this measured-from-real-data behaviour has no entry. (Its other call site is the app.py:10777 NameError the ledger already documents — I reproduced that 500 on a throwaway DB.)

## Studio and audio

76 features: 49 Live, 7 Partial, 16 Stubbed, 4 Dead code.

### Live

**Approve and lock a version**

Marks a version approved (recording the audio's sha256) or locked.

- Because: studio.py:645 calls sstore.record_approval with the asset checksum then set_version_status; the lock is enforced in the store's WHERE clause, not in the view.
- Routes: POST /studio/session/<project_id>/version/<version_id>/status
- Files: studio.py:645 studio_version_status; studio_store.py:record_approval/set_version_status; table studio_approvals
- Access: Project owner only; same plan/suite gates.

**Ask the Room**

Answers a question about the project from its own stored state, with evidence and a confidence band.

- Because: studio.py:328 redirects the question back onto the session page and studio.py:443 calls studio_room.ask with the real measurements, findings, comments, versions, checklist and rail. studio_room.py is rule-based and deterministic; there is no LLM configured and the module says so.
- Routes: POST /studio/session/<project_id>/room
- Files: studio.py:328 studio_room_ask; studio_room.py:1
- Access: Owner or shared collaborator; same plan/suite gates.

**Audio job runner**

Records, dispatches, retries and settles every audio job, and writes the usage ledger.

- Because: audio_jobs.py:74 creates an audio_jobs row, dispatches through the adapter, treats ProviderRefusal as terminal and ProviderUnavailable as retryable up to MAX_ATTEMPTS=3, and records usage even for mock jobs with a null cost.
- Routes: POST /admin/audio/poll runs the pending sweep
- Files: audio_jobs.py:74 submit, :256 poll, :332 collect_outputs, :375 run_pending; audio_store.py tables audio_jobs, audio_usage
- Access: n/a (library); the manual sweep is owner-only.

**Audio operator desk (/admin/audio)**

Provider health per capability, every flag and whether it gates anything, secret presence, jobs, usage, webhooks, policy and overdue retention.

- Because: audio_admin.py:126 renders from ap.health_report(), audio_policy.FLAGS, astore.list_jobs/usage_summary/list_webhook_events and audio_retention.due_count(); audio_admin.py:105 reports presence of credentials only, never values. A probe as a non-owner returned 404. It does not list LYRIC_SHEET_ENABLED because that name is missing from audio_policy.FLAGS.
- Routes: GET /admin/audio, POST /admin/audio/sweep, POST /admin/audio/poll
- Files: audio_admin.py:126 audio_admin, :47 _provider_rows, :81 _flag_rows, :105 _secret_presence; templates/audio_admin.html
- Access: Owner only (_is_owner_email, hashed emails plus OWNER_EMAILS); 404 for everyone else, including a signed-in artist. No team seat (app.py _TEAM_BLOCKED includes "/admin").

**Audio probe (upload sniffing)**

Reads an uploaded file's own header to refuse the wrong format, length or sample rate before anything is stored or sent.

- Because: audio_probe.py parses RIFF/WAVE (including EXTENSIBLE and 24-bit) and FLAC STREAMINFO in pure Python, reads MP3 Xing/Info/VBRI, falls back to ffmpeg, and refuses an unknown length rather than guessing; release_ready.py:1674 _take_file calls it on every upload.
- Routes: part of POST /creative-studio/release-ready/upload
- Files: audio_probe.py:1; release_ready.py:1674 _take_file, :368 _probe_message
- Access: n/a (library).

**Audio readiness rulings**

Turns the Rack's and the Studio's measurements into platform rulings (true-peak ceiling, loudness targets, loudness range).

- Because: audio_readiness.py derives every ruling from a stored measurement and returns "not measured yet" where there is none; it is called from app.py:8349 (Rack analysis), studio.py:396 (session verdict) and studio_metrics/studio_score.
- Routes: none directly
- Files: audio_readiness.py:33 TRUE_PEAK_CEILING, :40 PLATFORM_TARGETS, assess()
- Access: n/a (library).

**Audio retention sweep**

Destroys audio whose retention date has passed, keeping the row as an audit record.

- Because: audio_retention.py:155 sweep() deletes the blob first and only marks deleted_at after the bytes are gone; a missing blob counts as deleted; dry_run is the default from the admin button.
- Routes: POST /admin/audio/sweep
- Files: audio_retention.py:155 sweep, :197 due_count; audio_admin.py:161 audio_sweep; audio_store.py:694 expired_assets, :704 mark_asset_deleted
- Access: Owner only (audio_admin.py:38 _guard via _is_owner_email); /admin is in app.py _TEAM_BLOCKED so no team seat reaches it. No scheduler calls it — a probe of the repo found sweep() called only from audio_admin.py.

**Audio Studio — outputs, source and downloads**

Serves a job's produced files, the source that went in, and a JSON manifest the Rack loads stems from.

- Because: audio_studio.py:546/578/667 each re-check item["user_id"] against the signed-in account, 410 when retention has destroyed the bytes, and audio_studio.py:603 _send_asset streams through the app when ?via=app so a script fetch is not defeated by the bucket's missing CORS headers. static/js/rackdsp.js:2122 consumes outputs.json.
- Routes: GET /audio-studio/<work_id>/outputs.json, GET /audio-studio/<work_id>/output/<asset_id>, GET /audio-studio/<work_id>/source
- Files: audio_studio.py:546 studio_outputs, :578 studio_output, :603 _send_asset, :667 studio_source; blob_store.py
- Access: Owner of the work item only; same tier/suite gates.

**Audio Studio — work item page**

One job's status, refusal reason, outputs, source and (for a lyric sheet) the timed words.

- Because: audio_studio.py:480 404s another account's item, calls works.settle_work for a queued/running job because there is no background worker, and templates/audio_studio_item.html:240 reloads itself every 20 seconds while it waits.
- Routes: GET /audio-studio/<work_id>
- Files: audio_studio.py:480 studio_item, audio_studio.py:509 _transcript; templates/audio_studio_item.html; audio_works.py:353 settle_work
- Access: Owner of the work item only (404 otherwise); same tier/suite gates.

**Beat audio**

Uploads, streams and deletes the audio attached to a beat, with tempo and key measured in the browser.

- Because: app.py:8814 enforces a size cap and a MIME allowlist, stores through blob_store, drops the orphaned old object on replace; app.py:8972 streams it to the owner and :8984 deletes it. The tempo/key numbers come from static/js/tempokey.js in the browser — nothing listens server-side.
- Routes: POST /beats/<beat_id>/audio, GET /beats/<beat_id>/stream, POST /beats/<beat_id>/audio/delete
- Files: app.py:8814 beat_audio_upload, :8972 beat_stream, :8984 beat_audio_delete; blob_store.py; static/js/tempokey.js; db.py table beat_audio
- Access: Owner of the beat (404 otherwise); same tier/suite gates.

**Beat detail, licences, cleared list and usage cases**

One beat's licences, cleared items, usage cases and fingerprint checks, all editable from one form.

- Because: app.py:8697 dispatches on an action field into db.add_beat_licence / add_beat_clearance / delete_beat_clearance / add_beat_use / update_beat_use / set_beat_licence_status, all scoped to the signed-in user, and renders real rows.
- Routes: GET+POST /beats/<beat_id>, POST /beats/<beat_id>/delete, GET /beats/<beat_id>/clearance.csv
- Files: app.py:8697 beat_detail, :9062 beat_delete, :9070 beat_clearance_csv; templates/beat_detail.html; producers.py; db.py tables beat_licences, beat_clearances, beat_uses
- Access: Same as /beats; the beat must belong to the account (404 otherwise).

**Beat share links**

A private link that lets one artist hear a beat without an account, with plays counted.

- Because: app.py:8998 mints a token row, :9013 lists them, :9023 revokes, :9032 renders a standalone one-beat page and :9049 streams it, counting a play only on a non-range request.
- Routes: POST /beats/<beat_id>/share, GET /beats/<beat_id>/shares, POST /beat-link/<token>/revoke, GET /beat/<token>, GET /beat/<token>/stream
- Files: app.py:8998-9061; templates/beat_share.html; static/js/beat-share.js; db.py table beat_shares
- Access: The producer's controls (/beats/... and /beat-link/<token>/revoke) need the account and the Rack-family gates. /beat/<token> and /beat/<token>/stream are ANONYMOUS — "/beat/" is in app.py _PUBLIC_PREFIXES and the token is the authorisation.

**Beats desk**

A producer's beat registry with tempo, key, tags and notes, plus the ACRCloud monitoring status card.

- Because: app.py:8658 reads and writes real rows through db.add_beat / producers.desk(user_id) / db.beat_audio_for(user_id) and renders templates/beats.html; GET /beats returned 200.
- Routes: GET+POST /beats, POST /beats/register
- Files: app.py:8658 beats, app.py:8683 beat_register; templates/beats.html; static/js/beats.js; producers.py; db.py tables beats, beat_audio
- Access: plans.required_tier("/beats") == "artist" AND path_suite == "the-room": with gates on, Label or credits > 0 (or owner email). Team seats need the "studio" room.

**Browser master render intake**

Accepts a WAV the browser mastered as a new version, never overwriting the source.

- Because: studio.py:577 refuses without rights_confirmed_at, checks the RIFF magic and the size cap, writes a new audio_assets row with parent_asset_id and creates a studio_versions row; the gain applied is recorded in change_summary.
- Routes: POST /studio/session/<project_id>/render
- Files: studio.py:577 studio_render; studio_store.py:create_studio_asset/create_version/attach_report; static/js/masterchain.js
- Access: Project owner only; same plan/suite gates; 403 until rights are confirmed.

**Creative Studio explainer**

A public page grouping what Creative Studio does today, what is guided, and what is not built.

- Because: app.py:14214 renders creative_config.CAPABILITIES/WORKFLOW into templates/creative_studio_public.html; "/creative-studio" is an exact entry in app.py _PUBLIC_EXACT.
- Routes: GET /creative-studio
- Files: app.py:14214 creative_studio_public; creative_config.py; templates/creative_studio_public.html
- Access: ANONYMOUS (exact match only; /creative-studio/release-ready is gated separately).

**Delete an Audio Studio job**

Destroys the uploaded source's bytes and removes the work row.

- Because: audio_studio.py:729 removes the blob via _destroy, marks the asset deleted and calls works.delete_work.
- Routes: POST /audio-studio/<work_id>/delete
- Files: audio_studio.py:729 studio_delete, :746 _destroy; audio_works.py:243 delete_work
- Access: Owner of the work item only; same tier/suite gates; refused to a read-only seat.

**Delivery checklist**

Shows, line by line, what the project still needs before a package can be built.

- Because: studio.py:674 renders sstore.delivery_checklist, which is computed from the project's own versions, approvals and metadata rather than stored ticks.
- Routes: GET /studio/session/<project_id>/deliver
- Files: studio.py:674 studio_deliver; templates/studio/deliver.html; studio_store.py:delivery_checklist/list_deliveries
- Access: Project owner only; same plan/suite gates.

**Delivery package**

Builds a zip of the locked audio, a manifest, a checksum manifest and provenance, or refuses and names the missing line.

- Because: studio.py:697 refuses with a 400 naming the first unmet required line, otherwise studio_store.py:904 build_package writes the zip and _record_package logs it into studio_deliveries (and into the bucket when R2 is configured).
- Routes: POST /studio/session/<project_id>/deliver/package
- Files: studio.py:697 studio_package, studio.py:727 _record_package, studio.py:775 _read_asset_bytes; studio_store.py:904 build_package; table studio_deliveries
- Access: Project owner only; same plan/suite gates.

**Live Lab (stage sets)**

Sets, scenes, stems and MIDI mappings for a stage rig, with the audio engine running entirely in the browser.

- Because: live.py:115/129/158/178/196 create, list, open, edit and archive real rows in live_sets; live.py:220-360 write scenes, stems and MIDI mappings; live.py:362 serves the one manifest the browser engine loads and :375 opens Performance Mode with static/js/livelab.js. GET /live returned 200. live.enabled() is on unless LIVE_LAB_ENABLED is set to 0/false/no/off.
- Routes: GET /live, POST /live/new, GET /live/<set_id>, POST /live/<set_id>/settings, POST /live/<set_id>/archive, POST /live/<set_id>/scene, POST /live/<set_id>/scene/<scene_id>/delete, POST /live/<set_id>/scene/<scene_id>/stem, GET /live/stem/<stem_id>, POST /live/stem/<stem_id>/set, POST /live/stem/<stem_id>/delete, POST /live/<set_id>/midi, POST /live/midi/<mapping_id>/delete, GET /live/<set_id>/manifest.json, GET /live/<set_id>/perform
- Files: live.py:115-388; live_store.py; templates/live/*.html; static/js/livelab.js
- Access: plans.required_tier("/live") == "artist" AND plans.path_suite("/live") == "tour", so with gates on it needs Pro or above (or the owner email). Team seats need the "stage" room, not "studio". Every query filters on partner_id + user_id.

**Live Lab readiness statement**

Says before soundcheck which browser capabilities the rig needs and where they are missing.

- Because: live.py:90 readiness() returns four fixed statements of fact about Web Audio, Web MIDI, offline caching and setSinkId (Chromium-only) and templates/live/home.html renders them. These are capability statements, not measurements of anything.
- Routes: inside GET /live
- Files: live.py:90 readiness; templates/live/home.html
- Access: Same as /live.

**Loudness meter (BS.1770-4)**

Integrated LUFS, true peak (4x oversampled), loudness range and a per-block loudness graph, measured in the tab.

- Because: static/js/loudness.js (381 lines) implements the gating and K-weighting and templates/rack.html:1041-1110 renders the readouts; no request is made to measure.
- Routes: inside GET /rack (and GET /studio/session/<id>/mix via templates/studio/_measure.html)
- Files: static/js/loudness.js; templates/rack.html:1041; audio_readiness.py:PLATFORM_TARGETS
- Access: Same as /rack.

**Master Station**

The master view: the same measurements judged against platform targets, plus the browser render control.

- Because: studio.py:509 renders studio/master.html through _room; templates/studio/_render.html loads loudness.js, wavwrite.js and masterchain.js and posts the result to /studio/session/<id>/render. No server provider is involved.
- Routes: GET /studio/session/<project_id>/master
- Files: studio.py:509 studio_master; templates/studio/master.html; templates/studio/_render.html; static/js/masterchain.js; static/js/wavwrite.js; static/js/loudness.js
- Access: Same as the session console.

**Mix Check (Studio home)**

Lists the artist's Studio projects and offers the newest one as "Continue working".

- Because: studio.py:133 reads sstore.list_projects + list_shared_projects for the signed-in account and renders studio/home.html; probe of GET /studio returned 200 for a fresh artist account.
- Routes: GET /studio
- Files: studio.py:122 studio_home; templates/studio/home.html; studio_store.py; studio_config.py:66 enabled(); hubs.py:419 _STUDIO_ITEM names it "Mix Check"
- Access: Any signed-in account by tier (plans.required_tier("/studio") is None) BUT plans.path_suite("/studio") == "the-room", so on any deployment where plans.gates_on() is true (RENDER set, or SUITE_GATES=on) it needs Label or a credit balance > 0, or the owner email (app.py:4957 plan_gate). Team seats need the "studio" room (team_areas.EXTRA/rooms.ROOMS). 404 for everyone if STUDIO_V1_ENABLED/STUDIO_ENABLED is set to 0/false/no/off.

**Mix Station**

The mix view of a session: measured loudness/peak/dynamics, findings, timed notes and a mix-readiness breakdown.

- Because: studio.py:503 calls the same _room builder against studio/mix.html; the numbers come from studio_analysis rows the browser posted, and audio_readiness.assess turns them into rulings server-side.
- Routes: GET /studio/session/<project_id>/mix
- Files: studio.py:503 studio_mix; templates/studio/mix.html; audio_readiness.py; studio_metrics.py:162 mix_metrics; studio_score.py:mix_readiness
- Access: Same as the session console.

**New Studio project**

Creates a project row from a name, artist name and one of seven project types.

- Because: studio.py:207 POSTs into sstore.create_project and redirects to the new session id; _TYPE_LABELS is a form vocabulary, not seeded data.
- Routes: GET+POST /studio/new
- Files: studio.py:207 studio_new; studio.py:187 _TYPE_LABELS; templates/studio/new.html; studio_store.py:create_project
- Access: Same as /studio.

**Open this project in the Rack**

Sends the artist into /rack carrying the project and source asset on the query string.

- Because: studio.py:558 redirects to /rack?project=<id>&asset=<id>; static/js/rackdsp.js:2163 fetches /studio/asset/<id> to load it.
- Routes: GET /studio/session/<project_id>/rack
- Files: studio.py:558 studio_rack; static/js/rackdsp.js:2163
- Access: Project owner only; same plan/suite gates.

**Public beat licence and cleared list**

A single-use link where a licensee reads and signs a beat licence, and a public page a label can check a use against.

- Because: app.py:9095 handles the signing link and app.py:9119 renders the cleared list from db.list_beat_clearances plus the licence status behind each row, deliberately omitting fee, terms text and licensee email; producers.clearance_for answers cleared / not cleared / no list yet.
- Routes: GET+POST /licence/<token>, GET /cleared/<beat_id>
- Files: app.py:9095 beat_licence_public, :9119 beat_cleared_public; templates/cleared_public.html; producers.py:clearance_for
- Access: ANONYMOUS — "/licence/" and "/cleared/" are both in app.py _PUBLIC_PREFIXES, on purpose: the people who check these have no account.

**Rack analysis persistence**

Saves what the Rack measured against the account so Release Readiness can speak about the record.

- Because: app.py:8349 rejects NaN/inf, refuses a report with neither integrated nor true_peak, writes db.save_track_analysis and returns audio_readiness.assess of the stored row.
- Routes: POST /rack/analysis
- Files: app.py:8349 rack_analysis; db.py table track_analysis; audio_readiness.py:assess
- Access: Any signed-in account at the route itself (401 otherwise); reached through /rack, so the Rack's gates apply.
- Song (audit, 2026-09-23): the report carries `track_id` from the Rack's "Measuring for" select (templates/rack.html #rk-track, the account's songs, preselected from ?track= or the only song, never guessed between several), and the route keeps only an id that is one of THIS account's songs (store.get_os_track) - an invented id or another account's song is stored as no song. A measurement that names a song is working audio on it: the Command Center's "Open the Rack" essential.

**Rack preset library**

Many named, noted rack chains per account, with a per-account cap.

- Because: app.py:8402/8410/8430/8440 list, save, fetch and delete rows in db.rack_library and return a 409 naming the cap when it is full; static/js/rackdsp.js:2371-2438 drives all four.
- Routes: GET /rack/library, POST /rack/library/save, GET /rack/library/<preset_id>, POST /rack/library/<preset_id>/delete
- Files: app.py:8402-8448; db.py table rack_library, MAX_RACK_PRESETS; static/js/rackdsp.js:2371
- Access: Same as /rack; every query is scoped to user_id.

**Rack saved chain**

Remembers the one rack that loads with the page.

- Because: app.py:8449 writes db.save_rack_preset for the user and app.py:8130 reads it back into the template; static/js/rackdsp.js:2289 posts to it.
- Routes: POST /rack/save
- Files: app.py:8449 rack_save; db.py table rack_presets; static/js/rackdsp.js:2289
- Access: Same as /rack.

**Release-Ready owner desk**

Credits this month against the budget, job counts, per-artist and per-organisation spend, retries, resume, manual run, a RoEx health check and an end-to-end bucket test.

- Because: release_ready.py:2356/2363 render admin_data(), which reads the real release_ready_jobs/payments tables and the app_kv counters; release_ready.py:2233 _owner_or_404 gives a 404 to anyone else, confirmed by a probe returning 404 for an artist account. The cost figures are the app's own estimates from RoEx's price list and the desk says so (release_ready_settings.py docstring).
- Routes: GET /admin/release-ready, GET /admin/release-ready.json, POST /admin/release-ready/settings, POST /admin/release-ready/jobs/<jid>/retry, POST /admin/release-ready/resume, POST /admin/release-ready/run, POST /admin/release-ready/health, POST /admin/release-ready/storage
- Files: release_ready.py:2233 _owner_or_404, :2242 admin_data, :2356 admin_page, :2369 admin_settings, :2379 admin_retry, :2462 admin_resume, :2470 admin_run, :2478 admin_health, admin_storage; blob_store.py round_trip; templates/release_ready_admin.html
- Honesty: the storage badge reads "set up", not "connected", because blob_store.configured() only checks that four environment variables are non-empty. "Test the bucket end to end" is the only thing on this desk that proves a download: blob_store.round_trip stores a few bytes, fetches them back through a presigned link with no Authorization header - RoEx's exact position - at both lifetimes this module hands out (an hour for an analysis, R2's seven-day maximum for a mastering task), then deletes the object. It reports HTTP statuses and R2's own error codes and no secret. It runs on a press, never on a page view, because it writes into the production bucket.
- Honesty: "Work that has not come back" (_provider_notes) lists jobs still in flight or given up on that have a stored reason. It exists because a preview RoEx will never produce and a slow one look identical from the app: retrieve_preview_master reads any answer without a download link as "pending", so roex_client now keeps that answer's field names and RoEx's own message, _preview_poll_result stores them on the job and logs them the first time they change, and the deadline failure keeps them instead of replacing them with a bare timeout. The artist's wording is chosen by error_kind and never quotes this, so a stored reason cannot leak into their page. A bare HTTP 202 with an empty body - what a real staging run hit for forty-five minutes - is returned by roex_client before it looks for a download link, so there is nothing to quote; the job records "RoEx keeps answering 202 and has sent no file, on N ask(s) so far" instead, and the ask count alone does not earn a second log line (_without_count). The bucket test's result is stored in app_kv (release_ready:storage_report) and the route redirects like every other button on this desk, because a POST that rendered its own page came back to the plain page with the answer lost.
- Honesty: _store_preview's three failure paths (RoexDownloadError, an empty body, a bucket that refuses the object) went back on the clock recording nothing, so a preview RoEx HAD produced and we could not keep was indistinguishable from one RoEx was still making, for forty-five minutes, and then failed as "RoEx didn't finish this preview within 45 minutes" - which was untrue. They now go through _preview_snag: the reason is kept, logged once per distinct reason, and the deadline fails as error_kind "not_kept" with its own artist sentence, never the timeout's or the handoff's (handoff is the other direction - us failing to hand a file TO RoEx). The likeliest reason is roex_client.MAX_PREVIEW_BYTES (20 MB): a full-length 48 kHz 24-bit WAV is far over it. The test harness's download seam now refuses a file over max_bytes, which it did not, so the cap was untestable.
- Access: Owner only (_is_owner_email, and not while acting as a seat or on behalf). 404 for everyone else. /admin is in app.py _TEAM_BLOCKED.

**Resolve a finding**

Closes one automatic finding on the source asset.

- Because: studio.py:548 writes through sstore.resolve_finding into studio_findings; open findings with a start time become transport markers.
- Routes: POST /studio/session/<project_id>/finding/<finding_id>/resolve
- Files: studio.py:548 studio_resolve_finding; studio_store.py:list_findings/resolve_finding
- Access: Project owner only; same plan/suite gates.

**Rights confirmation**

Records who confirmed they hold the rights to the recording, per project.

- Because: studio.py:891 writes sstore.confirm_rights; upload and render both 403/refuse until rights_confirmed_at is set.
- Routes: POST /studio/session/<project_id>/rights
- Files: studio.py:891 studio_rights; studio_store.py:confirm_rights
- Access: Project owner only; same plan/suite gates.

**Rough Split (browser stem split)**

Splits the loaded track into four rough lanes with classical DSP, in the tab.

- Because: static/js/roughsplit.js (343 lines) is loaded at templates/rack.html:1218 and drives the #rk-roughsplit button, progress bar and #rk-stems panel; nothing uploads.
- Routes: inside GET /rack
- Files: static/js/roughsplit.js; templates/rack.html:715-745
- Access: Same as /rack.

**Send outputs to the Asset Vault**

Records a job's outputs as vault files without copying the audio.

- Because: audio_studio.py:694 calls db.add_vault_file with the same storage_key the work item holds, tagging stems/master by kind; templates/audio_studio_item.html:195 posts to it and tests/test_studio_outputs.py:125 exercises it.
- Routes: POST /audio-studio/<work_id>/to-vault
- Files: audio_studio.py:694 studio_to_vault; db.py table vault_files
- Access: Owner of the work item only; same tier/suite gates; refused to a read-only seat.

**Send to Remix Lab**

Redirects from a Studio session to /remix-lab.

- Because: studio.py:246 is a bare redirect and templates/studio/session.html:289 links it.
- Routes: GET /studio/remix
- Files: studio.py:246 studio_remix; templates/studio/session.html:289
- Access: Any signed-in account inside the Studio gates; the destination has its own.

**Session console (Control Room)**

One project's source, measurements, findings, notes, versions, lifecycle rail and delivery checklist on one page.

- Because: studio.py:374 _room builds every panel from studio_store rows and studio_metrics/studio_score functions that read those rows; nothing in the view model is a literal (studio_metrics.py:1 docstring and code both derive from stored measurements).
- Routes: GET /studio/session/<project_id>
- Files: studio.py:231 studio_session, studio.py:374 _room; templates/studio/session.html; studio_metrics.py; studio_score.py; studio_store.py:project_summary/delivery_checklist/provenance
- Access: Same as /studio, plus per-project: owner, or a live collaborator bound to an accepted team seat (studio.py:109 _project_shared_or_404 re-checks membership every request).

**Session switcher**

Moves between the account's own Studio sessions from inside a room.

- Because: studio.py:158 checks the requested id against the account's own project ids and 404s otherwise; templates/studio/session.html:51 posts to it as a GET form.
- Routes: GET /studio/open?project_id=
- Files: studio.py:158 studio_open; templates/studio/session.html:51
- Access: Same as /studio; owner of the project only (a foreign id is 404).

**Studio asset streaming**

Serves the bytes of one Studio asset to its owner, re-checking ownership each request.

- Because: studio.py:861 looks the asset up scoped by owner_user_id and partner, falls back to an audio_store asset only after re-checking the project membership, then redirects to a signed R2 URL or sends the local file.
- Routes: GET /studio/asset/<asset_id>
- Files: studio.py:861 studio_asset; blob_store.py:url_for/is_remote; static/js/rackdsp.js:2163 fetches it
- Access: Owner, or a shared collaborator of the owning project; same plan/suite gates.

**Studio project team and credits**

Adds a collaborator bound to an accepted team seat, or a named credit with no login, and removes them.

- Because: studio.py:274 resolves the seat from db.list_team and writes sstore.add_member; studio.py:300 removes it. Both abort 403 when session["team_as"] is set, so a seat cannot hand the artist's projects to others.
- Routes: POST /studio/session/<project_id>/team, POST /studio/session/<project_id>/team/<member_id>/remove
- Files: studio.py:274 studio_team_add, studio.py:300 studio_team_remove; studio_store.py:add_member/remove_member; table studio_members
- Access: Account holder only (explicit 403 for a team seat); project owner only; same plan/suite gates.

**Studio projects list**

Every non-archived project the account owns, plus projects shared to it.

- Because: studio.py:175 queries the studio_projects table with limit=200 and renders real rows; GET /studio/projects returned 200.
- Routes: GET /studio/projects
- Files: studio.py:175 studio_projects; templates/studio/projects.html; studio_store.py:list_projects/list_shared_projects
- Access: Same as /studio.

**Studio readiness panel**

States, component by component, what this deployment can actually do: analysis, storage, processing, worker.

- Because: studio_config.py:139 readiness() reads blob_store.configured(), provider_configured() and release_ready_settings.available() at request time; a local probe returned analysis=True, storage=False, processing=False, worker=False with nothing configured.
- Routes: rendered inside /studio, /studio/session/<id>/* and /studio/session/<id>/deliver
- Files: studio_config.py:139 readiness; studio_metrics.py:244 system_notes; templates/studio/home.html
- Access: Same as the page it renders on.

**Studio source upload**

Takes the artist's WAV/AIFF/FLAC/MP3/M4A into the project as version 1, written once.

- Because: studio.py:792 enforces rights confirmation, extension, size cap and a sha256 duplicate check, stores through blob_store or a private studio/ folder (never the public uploads tree) and creates the asset plus a "Source" version.
- Routes: POST /studio/session/<project_id>/upload
- Files: studio.py:792 studio_upload, studio.py:64 _save; blob_store.py; studio_store.py:create_studio_asset/create_version
- Access: Project owner only; same plan/suite gates. Refuses files over 25 MB entirely when R2 is not configured (studio.py:832).

**Studio Split diagnostics**

Reports the shape of the StemSplit environment (name present, length, stray quotes), never the value.

- Because: app.py:8151 returns JSON describing os.environ["STEMSPLIT_API_KEY"] without printing it, and optionally probes the vendor; GET /rack/studio-split/diag returned 200 signed in. readiness.py:254 links it as a probe and tests/test_app.py:5659 exercises it.
- Routes: GET /rack/studio-split/diag
- Files: app.py:8151 studio_split_diag; readiness.py:254; stemsplit_provider.py:probe
- Access: Any signed-in account (401 otherwise) plus the Rack's tier/suite gates. Not owner-gated, which is worth knowing: it lists every env NAME containing STEM or SPLIT.

**Tempo and key detection**

Estimates BPM, first beat, grid confidence and musical key from the loaded file, in the tab.

- Because: static/js/tempokey.js (574 lines) is loaded by templates/rack.html:1220 and paints rk-tk-bpm / rk-tk-key / the chroma SVG; the same detector feeds beat uploads (app.py comment above /beats/<id>/audio).
- Routes: inside GET /rack
- Files: static/js/tempokey.js; templates/rack.html:955-1012
- Access: Same as /rack.

**The audio gate**

The single door every audio job passes: flags, entitlement, tenant policy, provider, budget, consent, rights, retention, health.

- Because: audio_policy.py:184 gate() runs ten ordered checks and returns a Decision with a code and a readable reason; audio_jobs.py:74 submit() is the only caller path and the adapters are imported nowhere else. The zero-retention rule refuses rather than downgrading (audio_policy.py:262).
- Routes: none directly — called by audio_jobs.submit
- Files: audio_policy.py:184 gate; audio_jobs.py:74 submit; audio_store.py:425 get_policy, :476 has_consent; table audio_policies, audio_consent
- Access: n/a (library). A partner seat below owner/admin/manager is refused all audio features (audio_policy.py:215).

**The Rack**

A browser mixing and mastering desk: valve stages, tube, SUB-1, EQ, compressor, cabinet/mic, delay, reverb and output trim, patched in any order.

- Because: app.py:8130 renders templates/rack.html with the account's saved chain from db.get_rack_preset and loads static/js/rackdsp.js (5,207 lines of Web Audio); GET /rack returned 200. All DSP runs in the tab — no server audio path exists.
- Routes: GET /rack
- Files: app.py:8130 rack; templates/rack.html; static/js/rackdsp.js; static/js/tubes.js; static/js/rack-ducker.js; db.py table rack_presets
- Access: plans.required_tier("/rack") == "artist", AND plans.path_suite == "the-room", so with gates on it needs Label or credits > 0 (or the owner email). Team seats need the "studio" room.

**Timed notes on a mix**

Adds and resolves comments pinned to a timestamp on an asset, optionally assigned to someone.

- Because: studio.py:515 and :537 write and resolve rows in studio_comments and the console renders them as transport markers (studio.py:424).
- Routes: POST /studio/session/<project_id>/comment, POST /studio/session/<project_id>/comment/<comment_id>/resolve
- Files: studio.py:515 studio_comment, studio.py:537 studio_resolve_comment; studio_store.py:add_comment/resolve_comment
- Access: Owner or a shared collaborator (studio.py:109); same plan/suite gates.

**Versions and provenance**

Every version of the project with its change summary and the event log behind it.

- Because: studio.py:253 reads studio_versions via project_summary and studio_provenance via provenance(50).
- Routes: GET /studio/session/<project_id>/versions
- Files: studio.py:253 studio_versions; templates/studio/versions.html; studio_store.py:provenance
- Access: Project owner only; same plan/suite gates.

### Partial

**Archive a Studio project**

Shelves a project so it disappears from the lists, the switcher and its own URL.

- Because: studio.py:312 sets archived_at and every reader filters on it, so the archive half works; there is no unarchive function in studio_store, so an archived project cannot be brought back from the UI and the code says so in the docstring.
- Routes: POST /studio/session/<project_id>/archive
- Files: studio.py:312 studio_archive; studio_store.py:archive_project
- Access: Project owner role only (403 for a shared collaborator); same plan/suite gates.

**Audio Studio**

One page with seven audio lanes (dub, voiceover, sound effects, stem separation, voice isolation, voice vault, lyric sheet) plus a "what runs here" panel and a recent-work rail.

- Because: The page, the work list and the honesty panel are real and read the account's own audio_works rows (audio_studio.py:353). Every lane is OFF unless AUDIO_INTELLIGENCE_ENABLED and the lane's own flag are set — a probe showed no flag set, so all seven render off. With flags on but no ElevenLabs key, audio_providers.get() falls back to the mock adapter and the lane is badged "demo" (audio_studio.py:206/216).
- Routes: GET /audio-studio
- Files: audio_studio.py:353 studio, audio_studio.py:51 LANES, audio_studio.py:238 _runs_here; templates/audio_studio.html; audio_works.py; audio_policy.py:46 FLAGS
- Access: plans.required_tier("/audio-studio") == "artist" AND path_suite == "the-room": with gates on, Label or credits > 0 (or owner email). The route itself only requires a signed-in account. Team seats need the "studio" room.

**Audio Studio — start a job**

Takes a lane, an optional recording, a brief and rights ticks and creates one work item per piece of work.

- Because: The validation, storage, rights record and item creation are real (audio_studio.py:385: extension and 200 MB checks, private storage, per-item works.confirm_rights, one item per dub language). Whether anything comes back depends on the adapter: with no ELEVENLABS_API_KEY the mock answers and returns no audio at all (audio_mock.py:214 dubbing, :264 stems, :281 isolation all return b"").
- Routes: POST /audio-studio/new
- Files: audio_studio.py:385 studio_new, audio_studio.py:764 _options; audio_works.py:147 create_work, :258 submit_work; audio_jobs.py:74 submit; audio_policy.py:184 gate
- Access: Signed-in; 404 if the lane's flags are off. Same tier/suite gates as /audio-studio; a read-only team seat is refused every POST by app.py team_seat_gate.

**Browser measurement intake**  *(status corrected on review)*

Stores the loudness/true-peak/LRA/tempo/key numbers the browser measured against an asset.

- Because: studio.py:341 studio_measure ends with `numeric["measured_at"] = payload.get("measured_at") or True` — a Python bool when the client omits the field. templates/studio/session.html:201 then evaluates `(analysis.measurements.measured_at or analysis.created_at or "")[:16]` and raises TypeError: 'bool' object is not subscriptable. Reproduced: POST /studio/session/<id>/measure with {asset_id, integrated:-6.2, true_peak:-0.2, lra:3.1, duration_seconds:2.0} returned 200 {"ok":true}, after which GET /studio/session/<id> returned 500 while /mix and /master (which lack that line) returned 200. The bundled browser path does send it (templates/studio/_measure.html:69 measured_at: new Date().toISOString()), and a later well-formed measurement self-heals the page because latest_analysis takes the newest row — so the route works for the shipped client but accepts input that takes the project's own console down.
- Routes: POST /studio/session/<project_id>/measure
- Files: studio.py:341 studio_measure; templates/studio/_measure.html; static/js/loudness.js; static/js/tempokey.js; studio_store.py:save_analysis
- Access: Project owner only (studio.py:100 _project_or_404); same plan/suite gates.

**Lyric sheet export**

Downloads the transcribed words as a timed plain-text file.

- Because: audio_studio.py:637 builds the [m:ss] text and the download from audio_transcripts/audio_transcript_segments and templates/audio_studio_item.html:93 posts to it — so the export half is real. The lane that fills those rows gates on LYRIC_SHEET_ENABLED, which audio_policy.FEATURES names (audio_policy.py:93) but audio_policy.FLAGS (line 46) does not list, so /admin/audio's flag table never shows it. With no transcript the route 404s.
- Routes: POST /audio-studio/<work_id>/lyrics.txt
- Files: audio_studio.py:637 studio_lyrics_txt, audio_studio.py:509 _transcript; audio_policy.py:93 lyric_sheet spec vs :46 FLAGS; audio_store.py:755 transcript_for_asset
- Access: Owner of the work item only; same tier/suite gates.

**Remix Lab**

A remix-brief builder: the artist's choices plus a likeness screen, with a worked example until the engine is switched on.

- Because: The page, the two rights confirmations and the client-side likeness screen are real and render for any signed-in account (app.py:13887; GET /remix-lab returned 200). The brief itself only exists when the engine is live: remix_lab_config.engine_live() needs AUDIO_INTELLIGENCE_ENABLED and REMIX_LAB_AUDIO_ENGINE_ENABLED (both unset by default, verified), and the template switches between the real form action="/remix-lab/brief" and a panel labelled EXAMPLE OUTPUT (templates/partials/remix_lab_body.html:136, :357).
- Routes: GET /remix-lab
- Files: app.py:13887 remix_lab; templates/remix_lab.html, templates/partials/remix_lab_body.html; remix_lab_config.py:166 engine_live; static/js/remix-lab.js
- Access: required_tier("/remix-lab") is None, but path_suite == "the-room": with gates on, Label or credits > 0 (or owner email). Signed-in only (public version removed). Team seats need the "studio" room.

**Server audio conversion**  *(status corrected on review)*

Encodes MP3, FLAC, AAC, ALAC, Opus and Vorbis on the server because a browser has no encoder for them.

- Because: available() is `bool(shutil.which("ffmpeg"))` evaluated per request (convert_engine.py:169-175), and app.py:8138 passes it to the template as server_convert, so the Rack hides the panel and app.py:8303 returns 503 where the binary is absent. Nothing in the repo installs it: render.yaml's buildCommand is only `pip install -r requirements.txt`, requirements.txt has no ffmpeg wheel (flask, gunicorn, pytest, segno, cryptography, tzdata, elevenlabs, pypdf, sentry-sdk), and there is no Dockerfile or apt.txt. convert_engine.py:9 only asserts "There is an ffmpeg on the server". The True the inspector measured is this Windows dev box (which ffmpeg -> WinGet Links). Whether the deployed Render service has one is UNVERIFIED from the repo; grading it Live on a laptop binary is the error.
- Routes: POST /rack/convert
- Files: app.py:8303 rack_convert; convert_engine.py:48 FORMATS, convert_engine.py:169 ffmpeg_path/available
- Access: Any signed-in account at the route (401 otherwise) plus the Rack's tier/suite gates.

### Stubbed

**Artist Voice Vault lane**

Would register a voice its owner verified with the vendor.

- Because: audio_studio.py:133 _CONSENT_FLOW_MISSING = {"voice_vault"} makes audio_studio.py:136 _on() return False for this lane whatever the flags say, so the lane is permanently rendered off and POST /audio-studio/new for it aborts 404. audio_studio.py:800 also hard-codes owner_verified=False, and both the mock (audio_mock.py:307) and the real adapter refuse without owner verification. Nothing can complete it.
- Routes: lane on GET /audio-studio; POST /audio-studio/new with lane=voice_vault (404)
- Files: audio_studio.py:133 _CONSENT_FLOW_MISSING, :136 _on, :800 _options; audio_mock.py:307; audio_elevenlabs.py:839 ElevenLabsVoiceIdentity
- Access: n/a — nobody can turn it on from configuration.

**Audio webhook receiver**

Takes a vendor's "your job moved" call, verifies the signature over the raw body, dedupes it and advances our own job.

- Because: audio_webhooks.py:58 answers 404 unless AUDIO_INTELLIGENCE_ENABLED is set, 404 again unless <PROVIDER>_WEBHOOK_SECRET exists, and 401 on a bad signature. With nothing configured (the local default) it can only ever 404. The plumbing is real — the tenant is taken from our own audio_jobs row, never from the payload, and duplicates are recognised across processes.
- Routes: POST /webhooks/audio/<provider>
- Files: audio_webhooks.py:58 audio_webhook, :104 _signing_adapter, :127 _apply; audio_store.py:600 store_webhook_event; audio_elevenlabs.py:810 verify_webhook; table audio_webhook_events
- Access: Anonymous by design — "/webhooks/" is in app.py _PUBLIC_PREFIXES; the HMAC signature is the only authorisation.

**Beat fingerprint identify (ACRCloud)**

Sends one sample of a beat, or a clip the producer found, to ACRCloud and records what came back.

- Because: Needs ACRCLOUD_HOST, ACRCLOUD_ACCESS_KEY and ACRCLOUD_ACCESS_SECRET. app.py:8924 redirects straight back when acr_provider.configured() is False, and acr_provider.py:167 raises "ACRCloud keys are not set". With the keys it is a real single call on a button press, and the result or the vendor's error is stored as a check row.
- Routes: POST /beats/<beat_id>/identify
- Files: app.py:8924 beat_identify; acr_provider.py:50 configured, :167 identify; db.py tables beat_fingerprint_checks, beat_fingerprint_matches
- Access: Owner of the beat; same tier/suite gates; refused to a read-only seat.

**ElevenLabs adapters**

Real transcription, speech, sound effects, isolation, music/composition plan, stems, dubbing, agent and voice-identity adapters.

- Because: Needs ELEVENLABS_ENABLED and ELEVENLABS_API_KEY. audio_elevenlabs.py:293 _measure_health() returns "unconfigured" without them and never claims ready on the strength of a key it has not used — health() makes a real models.list() call. audio_elevenlabs.py:877 register_all() only makes the vendor the default when both are set, so the mock serves every capability by default (probe confirmed all nine serving adapters are "mock"). Zero retention stays refused until ELEVENLABS_ZERO_RETENTION_VERIFIED is set.
- Routes: none directly
- Files: audio_elevenlabs.py:339 _Base, :374 Transcription, :498 Speech, :534 SoundEffects, :550 VoiceIsolation, :569 Music, :677 Stems, :703 Dubbing, :767 Agent, :839 VoiceIdentity, :877 register_all
- Access: n/a (adapter layer).

**Offline (mock) audio adapters**

Complete, deterministic, credential-free adapters so the app runs with no vendor.

- Because: By design: audio_mock.py returns is_mock=True on every result and produces NO audio for dubbing, stems or isolation (b"" with a note saying so), refuses music generation outright, and refuses a voice registration without owner verification. They are the default whenever ElevenLabs is not configured.
- Routes: none directly
- Files: audio_mock.py:57 onwards; audio_providers.py:256 get() falls back to "mock"
- Access: n/a (adapter layer).

**Release-Ready (RoEx)**

ONE photographed rack unit is the interface (owner-supplied black 2U plate, 2026-09-22): it is on the Release-Ready page the moment you open it and you load into it, and it carries the three takes as buttons. Not the browser's audio controls, and not one faceplate per preview - both were built and rejected. The faceplate is one photograph; the load slot, the display window, three take buttons, the transport, two thirteen-lens meter strips, the jewel and the knob are the only parts in code, each placed as a fraction of the 1658x509 crop measured with PIL.

- Because: static/css/rr-unit.css carries the measurements and tests/test_rr_unit.py asserts them against the same numbers the crop was taken with, so a nudged value fails rather than quietly putting a lit segment on the metal between two lenses. The meters are fed by a WebAudio analyser on the preview itself and the waveform is decoded from the same file, so both are showing this track; with no audio yet the window draws no waveform at all.
- Files: static/css/rr-unit.css, static/js/rr-unit.js, templates/_rr_unit.html, static/img/rr2-plate-{1120,1658}.webp, static/img/rr2-knob.png; included from templates/release_ready.html (load into it) and release_ready_source.html (play the takes)
- Honesty: the unit is shown in every state and unlit IS the waiting state - the plate was photographed with every lamp off for exactly that, so there is no second loading graphic to keep in step. The load slot does NOT upload: it hands the file to the page's own form and takes you to the rights and licence boxes, which are not ours to skip. Buy stays off the faceplate - a payment should not be a button you can knock. The skin is a skin: the <audio> element keeps its id and ARIA label, it is what plays, and below a 520px container the plain controls are what a reader gets.

Upload a mix, or a vocal and a beat, get a mix report and free 30-second previews, then buy the full master.

- Because: Needs ROEX_API_KEY, R2 storage and the owner's rr_open switch. release_ready.connection_state (release_ready.py:613) returned code "not_connected" on a probe, and release_ready_settings.available() was False; every write goes through _gate (release_ready.py:1643) which refuses with 409 while that is so. rr_open defaults to "0" (release_ready_settings.py:DEFAULTS) so even with RoEx connected it is owner-only until the owner opens it. The page itself renders (200) and states the reason.
- Routes: GET /creative-studio/release-ready, GET .../state.json, POST .../upload, GET .../sources/<sid>
- Files: release_ready.py:1576 page, :1584 page_state, :1594 source_page, :1691 upload, :613 connection_state, :1643 _gate; release_ready_settings.py:86 available; roex_client.py:206 configured; templates/release_ready.html, release_ready_source.html
- Access: plans.required_tier("/creative-studio/release-ready") == "artist" — no suite/credits gate (it is not in plans._ROOM_PATHS). A team seat inside the account can view (release_ready.py:560 _is_seat) but is refused buying (COPY["seat_buy"], 403) and a read-only seat is refused every write.

**Release-Ready consent record**  *(status corrected on review)*

Records, per file, who ticked which two boxes, when, against the file's sha256 and a hash of the exact wording.

- Because: That sentence is false. release_ready.py:1691 upload() calls `refused = _gate(user)` on its FIRST line and returns _refuse(*refused) before it ever looks at f.get("rights")/f.get("licence") (the boxes check is the next statement, line ~1697). _gate (release_ready.py:1639) returns connection_state(user)["message"] with 409 whenever state["open"] is false, and connection_state (release_ready.py:613) is false the moment roex.configured() is false. Probe on this worktree: roex_client.configured() -> False, release_ready_settings.available() -> False, is_open() -> False. So no row can ever be written to release_ready_consents on a deployment without ROEX_API_KEY + R2 + the owner's rr_open switch. The consent machinery is real code; it is not reachable.
- Routes: part of POST /creative-studio/release-ready/upload
- Files: release_ready.py:141, :146, :1691; release_ready_store.py table release_ready_consents
- Access: Same as Release-Ready.

**Release-Ready master delivery**

Stores the paid master privately, serves it to its owner, deletes it on request and attaches it to the song's Track Passport.

- Because: Reaching it needs a paid job, which needs RoEx and Stripe. The storage rule is real and strict: release_ready.py:707 _store_private returns None rather than falling back to the Render disk when R2 is not configured, and release_ready.py:1142 attach_master writes the Track Passport link.
- Routes: GET /creative-studio/release-ready/jobs/<jid>/master.wav, POST /creative-studio/release-ready/jobs/<jid>/master/delete
- Files: release_ready.py:2012 master_audio, :2024 delete_master, :1091 _store_master, :1142 attach_master, :707 _store_private
- Access: Owner of the job; same tier gate; a read-only seat is refused the delete.

**Release-Ready master purchase**

A one-time Stripe Checkout per master, claimed once by either the webhook or the success redirect.

- Because: Needs both RoEx and Stripe: release_ready.py:2067 refuses with COPY["no_payments"] when stripe_provider.configured() is False, and _gate refuses first when RoEx is not connected. The claim logic is real and defensive — release_ready.py:2104 claim_session checks the account, the amount against the price that session was opened at, freshness, and records "stale"/"mismatch"/"duplicate" with an owner alert instead of retrieving.
- Routes: POST /creative-studio/release-ready/jobs/<jid>/buy, GET /creative-studio/release-ready/jobs/<jid>/paid
- Files: release_ready.py:2049 buy, :2104 claim_session, :2164 paid_return; stripe_provider.py; release_ready_store.py tables release_ready_jobs, release_ready_payments
- Access: Same as Release-Ready, and explicitly NOT a team seat (release_ready.py:2057 returns 403 COPY["seat_buy"] for any seat or act-on-behalf).

**Release-Ready mix report**

RoEx's verdicts and figures on an uploaded mix, run under a monthly credit budget and a per-artist cap.

- Because: release_ready.py:766 _step_analysis calls roex.mix_analysis, which cannot leave without ROEX_API_KEY (roex_client.py:202 _key, :318 _http). The budget machinery around it is real and counts in app_kv (release_ready_settings.py rr_credits:<YYYY-MM>:auto and rr_reports:<YYYY-MM>:<user>), and release_ready.py:491 report_view renders "Not measured" rather than 0 for anything RoEx omitted — there is deliberately no score, because RoEx returns none.
- Routes: POST /creative-studio/release-ready/sources/<sid>/report
- Files: release_ready.py:1802 run_report, :766 _step_analysis, :491 report_view; roex_client.py:573 mix_analysis; release_ready_settings.py
- Access: Same as Release-Ready; a read-only seat is refused.

**Release-Ready previews**

Free 30-second mastering previews, capped per file and per artist per day.

- Because: Same RoEx key requirement. release_ready.py:1849 make_previews goes through _gate, and release_ready.py:858/890/916 submit, poll and store through roex_client.mastering_preview / retrieve_preview_master. The caps (rr_previews_per_file, rr_previews_per_day) are real settings read from app_kv.
- Routes: POST /creative-studio/release-ready/sources/<sid>/previews, GET /creative-studio/release-ready/jobs/<jid>/preview
- Files: release_ready.py:1849 make_previews, :2002 preview_audio, :916 _store_preview; roex_client.py:600 mastering_preview, :623 retrieve_preview_master
- Access: Same as Release-Ready; a read-only seat is refused.

**Release-Ready upload deletion**  *(status corrected on review)*

Removes an uploaded source, its objects and any open checkouts for it.

- Because: True of the handler, misleading as a status. delete_source (release_ready.py:1911) does skip _gate, but its first act is `src = store.source_for(user["id"], sid)` and it aborts 404 when that is None. The only writer of a release_ready source row is upload() (release_ready.py:1691), which IS gated by _gate. With roex.configured() False (probed) nothing is ever stored, so every id 404s. Nothing is deletable until RoEx has been connected.
- Routes: POST /creative-studio/release-ready/sources/<sid>/delete
- Files: release_ready.py:1911 delete_source, :1952 _close_checkouts, :1979 _delete_object
- Access: Owner of the source; same tier gate; a read-only seat is refused.

**Remix brief run**

Screens the references, takes the uploaded master and composes a brief from what a provider could measure.

- Because: app.py:13910 aborts 404 unless remix_lab_config.engine_live(), which is False by default. When on, it is real in structure — the server-side likeness screen runs first (audio_works.screen_reference), both rights ticks are required, the file is stored privately, a remix_plan work item is created and submitted — but with no vendor key the mock MusicProvider answers with a seeded composition plan (audio_mock.py:237 returns a fixed four-section structure and a checksum-derived BPM) and the page marks it is_mock.
- Routes: POST /remix-lab/brief
- Files: app.py:13910 remix_lab_brief; remix_lab_engine.py:compose_brief/brief_is_grounded; remix_lab_config.py:184 check_reference_text; audio_mock.py:237 composition_plan; templates/remix_lab_brief.html, templates/remix_lab_refused.html
- Access: Same as /remix-lab; refused to a read-only team seat.

**RoEx client**

The only module that talks to RoEx, with a path allowlist, a shared rate limiter and key scrubbing.

- Because: roex_client.py:202 reads ROEX_API_KEY and configured() is False without it (probe). Everything else is real and enforced: roex_client.py:290 allowed_path is an allowlist (separation endpoints deliberately excluded), :456 _rate_take takes a slot from a SQLite sliding window shared across workers, :267 _scrub removes the key and every query string, and _http never follows a redirect.
- Routes: none directly
- Files: roex_client.py:85 BASE, :202 _key, :206 configured, :290 allowed_path, :318 _http, :393 _download, :456 _rate_take, :573 mix_analysis, :600 mastering_preview, :643 retrieve_final_master, :675 recombine, :756 health; table roex_rate
- Access: n/a (library).

**RoEx webhook**  *(status corrected on review)*

RoEx's "this job moved" call, used only as a nudge to re-read the task.

- Because: release_ready.py:2191 roex_webhook aborts 404 unless store.get_job(jid) exists AND carries a non-empty webhook_token_hash. A job row only exists after a submission that passed the same _gate (RoEx + storage + rr_open), and release_ready.py:675 _webhook_for explicitly writes `store.update_job(job_id, webhook_token_hash=None)` and returns None unless PUBLIC_BASE_URL startswith "https://". Both preconditions are unmet here (roex.configured() False by probe; no PUBLIC_BASE_URL). The endpoint can only ever answer 404 — the inspector's own "because" clause states this and then grades it Live anyway.
- Routes: POST /webhooks/roex/<jid>/<token>
- Files: release_ready.py:2191 roex_webhook, :675 _webhook_for
- Access: ANONYMOUS — "/webhooks/" is in app.py _PUBLIC_PREFIXES; the per-job token is the only authorisation and it is stored hashed.

**Studio Split (StemSplit.io)**

Sends the loaded track to StemSplit.io for studio-quality separation and streams the stems back.

- Because: Needs STEMSPLIT_API_KEY. stemsplit_provider.configured() is False with it unset (verified by probe), the template hides the tier (app.py:8130 passes studio_split=stemsplit.configured()), and app.py:8221/8265/8277 all return 503 "isn't configured" without it. With the key it is a real three-call flow (park source, create job, proxy stems) — that path was not exercised here.
- Routes: POST /rack/studio-split, GET /rack/studio-split/<job_id>, GET /rack/studio-split/<job_id>/stem/<stem>, GET /stem-src/<token>
- Files: app.py:8221 studio_split_start, app.py:8256 stem_src, app.py:8265 studio_split_status, app.py:8277 studio_split_stem; stemsplit_provider.py
- Access: The three /rack/studio-split routes need a signed-in account (401 otherwise) plus the Rack's tier/suite gates. /stem-src/<token> is ANONYMOUS by design — "/stem-src/" is in app.py _PUBLIC_PREFIXES so StemSplit can fetch the file; the unguessable token is the only authorisation and the parked file is swept after 1 hour (stemsplit_provider.SRC_TTL).

### Dead code

**Song Lab**

Not present.

- Because: Absent from this repository entirely. Case-insensitive grep for "songlab", "song-lab" and "song lab" across *.py, *.html and *.js returns nothing; there is no module, route, template or static file. templates/ has no song-lab page and app.url_map carries no such rule.
- Routes: none
- Files: none in this worktree
- Access: n/a

**Studio external processing provider seam**

Would send renders to a configured mastering/mixing vendor.

- Because: STUDIO_PROCESSING_PROVIDER, STUDIO_PROVIDER_BASE_URL and STUDIO_PROVIDER_API_KEY are read only by studio_config.processing_provider()/provider_configured(), and those two are called only by studio_config.readiness() and tests/test_studio_foundation.py. grep across the repo finds no adapter, no HTTP call and no job that would use them — setting all three changes one sentence on the readiness panel and nothing else.
- Routes: none
- Files: studio_config.py:120 processing_provider, studio_config.py:127 provider_configured; no caller outside studio_config.py and tests
- Access: n/a

**Studio sub-flags (Mix Doctor, Master Station, Album mode, Delivery, retention)**

Per-room switches for the Studio.

- Because: studio_config.mix_doctor_enabled(), master_station_enabled(), album_mode_enabled(), delivery_enabled() and retention_days() are referenced nowhere in the app — grep finds mix_doctor_enabled/master_station_enabled only in tests/test_studio_foundation.py, and album_mode_enabled, delivery_enabled and studio_config.retention_days nowhere at all. The routes they name never consult them.
- Routes: none
- Files: studio_config.py:76-110
- Access: n/a

**Studio Visual Room**

Redirects to /artwork.

- Because: Nothing reaches it. grep for "studio_visual" and "/studio/visual" across *.py, *.html, *.js and *.md returns only its own definition at studio.py:237-238 — no template link, no nav entry, no command-palette key, no test.
- Routes: GET /studio/visual
- Files: studio.py:237 studio_visual
- Access: Would be the same as /studio if anything linked it.

> Noted by the reviewer as not yet written up in this area: Rack chain strip on the Studio session console — templates/studio/_rackmods.html (114 lines; macros knob/module/strip), imported at templates/studio/session.html:4 and rendered at session.html:240-244 as rackmods.strip(rack_chain, "/rack?project=...&asset=..."), fed by rack_chain=store.get_rack_preset(user["id"]) in studio.py _room. Server-computed needle angles and power LEDs off the account's real saved Rack preset, read-only, each module deep-linking to #sb01..#sb08 in /rack. Live, and it is the only Studio panel with no entry (the inspector's "Session console" entry lists source, measurements, findings, notes, versions, rail and checklist and omits this).; Playback translation (listening simulations) on the Studio console — templates/studio/session.html:426-430 (#sb-sims, labelled "Simulations, not measurements of any real device") driven by static/js/studioconsole.js:106-410, which builds a switchable filter chain (flat plus device simulations) on the monitor path via simIn/simNodes/setSim. Live, entirely in the tab, no entry.; Hook / snippet finder in the Rack (SB-11) — templates/rack.html:774-793 (#rk-hook-scan "Find hooks", #rk-hookmap, #rk-hooks) and static/js/rackdsp.js:2564-2800. A real energy scan, snapped to the tempo grid via window.SBTempoKey.beatGrid (rackdsp.js:2604-2648), preview through the loaded chain, WAV snippet export (rackdsp.js:2690) and a 720x1280 vertical WebM export through MediaRecorder (rackdsp.js:2696-2740). Its hook_15s/hook_30s are persisted server-side by POST /rack/analysis (app.py:8382). Live, browser-only. No entry.; Rack exports — "Export WAV" (templates/rack.html:468 #rk-export, rackdsp.js:3646, bounces the processed master or a stem mix offline) and "→ Vault" (templates/rack.html:1214 #rk-vault, rackdsp.js:3659-3682, renders the master then POSTs it to /vault/upload with kind=master and label). Live. The inspector's "The Rack" entry describes the DSP units and never mentions that the Rack can bounce a file at all, or that it writes into the Asset Vault.; Stem Deck — static/js/stemdeck.js (277 lines) with templates/rack.html:714-745 (#rk-stems, #rk-stems-file "Add stems") : a multi-lane stem player with per-lane gain/mute/solo feeding the same chain, plus the compressor sidechain key selectable from a loaded stem (templates/rack.html:303-304 #rk-comp-key). It is the panel Rough Split, Studio Split and the Audio Studio's outputs.json handoff (rackdsp.js:2122) all load into, so three entries reference its inputs and none names the deck itself. Live.; GET /creative-studio/release-ready/sources/<sid>.json — release_ready.py:1595-1597 (`as_json = sid.endswith(".json")`), consumed by templates/release_ready_source.html:34 data-rr-source-url and static/js/release_ready.js:172. This is the poll that advances RoEx work: source_page calls _kick(jobs) (release_ready.py:1203) which spawns advance() for every due, unleased job. With no background worker it is the artist's own open tab that moves a job forward. The inspector listed only the HTML `GET .../sources/<sid>` and gave no entry to the polling mechanism.; GET /creative-studio/release-ready/jobs/<jid>.json (release_ready.py:1621-1629 job_state) — DEAD CODE, and missed entirely. It re-kicks the job and returns public_job(). grep across *.py, *.html, *.js and tests/ for "job_state", "/jobs/" and "jobs/" finds only its own definition: no template attribute, nothing in static/js/release_ready.js (which uses only data-rr-source-url and data-rr-state-url), no test.; GET /creative-studio/release-ready/state.json (release_ready.py:1584 page_state) — listed inside the Release-Ready route line but given no status of its own; it is the list page's poller (templates/release_ready.html:29 data-rr-state-url, static/js/release_ready.js:212) and, unlike every write, it is NOT behind _gate, so it answers 200 with the refusal state on an unconfigured deployment (probed: 200).

## Fans and audience

54 features: 31 Live, 12 Partial, 9 Stubbed, 2 Dead code.

### Live

**Real music search on Discover**

Search the Apple/iTunes catalogue from the fan page, play a 30 second preview, open the full track. This is the whole of Discover for a real account.

- Because: app.py discover() calls music_apis.itunes_search(q) with the typed term and renders whatever comes back; music_apis.py:41 itunes_search hits https://itunes.apple.com/search live, caches by term in store.cache_get/cache_set, drops any result with no title or artwork and upscales artworkUrl100 to 300x300. Probed with a fresh fan account and a stubbed transport: the titles, artists, artwork and the preview button all came from the response, and nothing on the page came from discover_config. A network failure returns [] and the page says no tracks came back rather than inventing any.
- Routes: GET /discover?q=<term>
- Files: app.py discover(); music_apis.py:41 itunes_search(); templates/discover.html (the results grid and the shared preview player)
- Access: Any signed-in account, including the free Fan plan. Anonymous is bounced to /login by plan_gate. The "+ Catalog" button on each result is rendered only when the account's plan can reach /catalog/add (plans._PRO_PATHS contains "/catalog"), because a Fan plan was being offered a button that answered 402.

**/audience (retired)**

The old listener/follower/age/country page, now a permanent redirect to Artist Pulse.

- Because: app.py:12328 def audience() is three lines: a redirect to /pulse; probed, returns 302 /pulse. The docstring says the old splits were invented and were deleted, and no template for them remains.
- Routes: GET /audience
- Files: app.py:12327-12332
- Access: Artist tier or higher (plans._ARTIST_PATHS contains "/audience"); it belongs to the Fans room in team_areas.EXTRA.

**Audience (/fans)**

One screen of the account's own fan records: totals, map, funnel, list health, activity, segments and tour overlap.

- Because: fan_audience.for_account() reads ml_fans, ml_consents (consented_count), club_members, tour_shows and ml_events (via links_store.account_event_counts) for the signed-in user and every panel is computed from those rows; probed with the test client, a fresh account rendered the first-run screen and after one real capture rendered the full Audience screen. Two gaps are declared on the page rather than faked: the Deliverability health row is hard-coded score=None/"Not measured" (fan_audience.py build(), health list) because nothing is sent from here, and the third step of "The first send" says "Not available in this build".
- Routes: GET /fans
- Files: app.py:12206 (@app.route("/fans")), handler app.py:12207 def fans(); builder fan_audience.py:239 def build() and fan_audience.py:585 def for_account(); templates/fans.html, templates/partials/fans_head.html; stores links_store.py (list_fans, account_event_counts), fan_segments.py, db.py (list_club_members, list_tour_shows, get_fan_club)
- Access: Any signed-in account. plans.required_tier("/fans") returns None (verified by calling it), so a free Fan-plan account opens it too — confirmed by probe: fan plan got 200 on /fans while /links/fans, /fan-club and /links returned 402. Anonymous is bounced by app.py plan_gate (probe: 302 to /login?next=/fans), so the `user is None` showcase branch in the handler is unreachable — which contradicts fan_audience.py's module docstring ("the demo account and signed-out visitors"); the code wins. Team seats: team_areas.room_for_path("/fans") == "fans", so a seat with the Fans box ticked reaches it; not in app.py _TEAM_BLOCKED.

**Audience first run**

An account with nobody on file gets the list-import form as the whole page instead of empty panels.

- Because: app.py:12261 `if not showcase and not ctx["audience"]["total"]` renders fans_first_run.html with the real last list import (store.latest_fan_import), the real pending draft (store.get_fan_import_draft) and fan_list_import.MAX_ROWS; probe confirmed a brand-new account got this page and the Audience screen appeared only after the first fan.
- Routes: GET /fans (branch)
- Files: app.py:12261-12266; templates/fans_first_run.html; fan_list_import.py:167 MAX_ROWS; db.py:4281 latest_fan_import, db.py:4335 get_fan_import_draft
- Access: Same as /fans: any signed-in account; never shown to the demo/showcase session (`not showcase` guard).

**Connect Hypeddit panel**

Shows the account's own secret webhook address, what Hypeddit last sent (masked) and how many fans arrived.

- Because: app.py:11060 def _hypeddit_panel() mints or reads the token (hypeddit_ingest.get_or_create_token, app_kv) and reads the real delivery log and counter; probed — after one webhook POST, status() reported count 1, connected True and the last delivery's masked fields.
- Routes: GET /links/fans (#hypeddit section)
- Files: app.py:11060-11071; hypeddit_ingest.py:74 get_or_create_token(), :240 record(), :253 status(); templates/partials/hypeddit_connect.html; db.py app_kv
- Access: Artist tier or higher. Hidden from the demo session (_session_is_demo → panel is None) and hidden by the template from any team seat whose access is not "edit".

**Consent log**

One row per permission a fan gave, with the sentence they agreed to and where it came from.

- Because: ml_consents is written on every intake path — email_marketing/presave_notify at app.py:2114, spotify_presave at app.py:1926, hypeddit_gate at hypeddit_ingest.py:296, shopify_email_marketing at shopify_customers.py:323, list_import inside links_store.confirm_list_import, fan_club at app.py:6440 and app.py:5776 — and read back by fan_audience.consented_count() for the "Consent on file" health row. Deleting a fan deletes their consents too (links_store.delete_fan).
- Routes: surfaced on GET /fans (health) — no page lists the rows themselves
- Files: links_store.py:460 add_consent(), :407 find_consent(), :473 list_consents(); fan_audience.py:565 consented_count(); db.py ml_consents (db.py:684)
- Access: n/a for writes; the derived figure is on /fans (any signed-in account). Note links_store.list_consents() has only one caller, fan_dashboard.py:135, which is itself dead code.

**Destination click-through**

Sends the visitor to the chosen platform and records which service was clicked.

- Because: app.py:2084 ml_go() 404s a destination that does not belong to the campaign, writes a service_click ml_events row with the service_key and variant, and refuses any target that is not http(s) with a 400.
- Routes: GET /l/<slug>/go/<dest_id>
- Files: app.py:2083-2095; links_store.py:146 get_destination(), :153 track()
- Access: Anonymous (public prefix).

**Email capture on a smart link**

A fan gives their address on the public page and becomes a scored fan record with a consent row.

- Because: app.py:2108 ml_subscribe() validates the address, upserts the fan, writes an ml_consents row with the campaign's own consent text (presave_notify before release, email_marketing after), writes the matching ml_events row, bumps the counter, rescores intent and notifies the artist. Probed live: POST returned ok and the fan appeared in the CRM at Warm/25.
- Routes: POST /l/<slug>/subscribe
- Files: app.py:2107-2152; links_store.py:200 upsert_fan(), :460 add_consent(), :376 bump_fan(), :390 set_fan_intent(); links_engine.py:160 calculate_fan_intent(); db.py ml_fans/ml_consents/ml_events
- Access: Anonymous (public prefix); refused with 404 JSON unless the campaign status is "live".

**Fan Club setup**

Name, blurb, monthly price, perks and an on/off switch for a paid membership, with member and MRR counts.

- Because: app.py:6387 fan_club() writes through db.save_fan_club into the fan_clubs table and reads the real club_members and club_drops rows; MRR is computed from the active member count times the stored price, not invented. Probed: GET /fan-club returned 200 for an artist account.
- Routes: GET/POST /fan-club
- Files: app.py:6386-6417; db.py:2351 save_fan_club(), :2363 get_fan_club(), :2392 list_club_members(), :2430 list_club_drops(); templates/fan_club.html; db.py fan_clubs/club_members/club_drops (db.py:120, :129, :139)
- Access: Artist tier or higher — plans._ARTIST_PATHS contains "/fan-club" (probe: fan-plan got 402). Team seats reach it through the Fans room; read seats cannot POST.

**Fan CRM (/links/fans)**

The table of every fan on file with intent band, pre-saves, captures, first campaign and last activity.

- Because: app.py:11001 def ml_fans() calls links_store.list_fans(user_id, q) and renders real rows; probed end-to-end — a fan captured on a smart link and a fan filed by the Hypeddit webhook both appeared with their tags and scores.
- Routes: GET /links/fans
- Files: app.py:11000 (@app.route("/links/fans")), handler app.py:11001; templates/links_fans.html, templates/partials/fans_head.html, templates/partials/fan_list_import.html, templates/partials/hypeddit_connect.html; store links_store.py:466 def list_fans()
- Access: Artist tier or higher — plans.required_tier("/links/fans") == "artist" (it is under the "/links" prefix in plans._ARTIST_PATHS); probe confirmed 402 upgrade for a fan-plan account. Team seats reach it through the Fans room (team_areas.room_for_path == "fans"); a read seat can GET but every POST on the page is refused by app.py team_seat_gate.

**Fan CRM CSV export**

Downloads the fan list, contactable only by default, with a ?include=suppressed full export.

- Because: app.py:11295 def ml_fans_export() writes a real CSV from links_store.list_fans() and skips rows whose `suppressed` reason is set unless ?include=suppressed; probed, returned the header plus the account's real rows. Note the Visits and Clicks columns are always 0 (see "Fan engagement counters").
- Routes: GET /links/fans/export.csv, GET /links/fans/export.csv?include=suppressed
- Files: app.py:11294-11319; links_store.py:466 list_fans(); templates/links_fans.html (au-crm-export)
- Access: Artist tier or higher. For a demo session this exports the demo account's own (empty) ml_fans, not the showcase rows.

**Fan gate reward**

After a real capture, hands back a download link to a file the artist chose from their Vault.

- Because: app.py:2139-2151 resolves settings["gate_reward"] against store.list_vault_files(campaign owner) and returns the file's path only in the successful-capture response; app.py:3232 _vault_file_private() deliberately keeps a master that is a gate_reward publicly served, so the handed-out link keeps working — the two halves agree.
- Routes: POST /l/<slug>/subscribe (reward in the JSON response); file served by GET /uploads/<filename>
- Files: app.py:2139-2151; app.py:3205 uploaded_file(), app.py:3232 _vault_file_private(); db.py:2753 list_vault_files(); templates/links_builder.html (gate_reward picker)
- Access: Anonymous. The reward file itself is public by design once it is a gate reward (unguessable filename, no session check).

**Fan Room new-fans CSV**

Downloads the contactable fans who joined through a link in the chosen 7/30/90-day window.

- Because: app.py:4693 def fan_room_new_csv() calls fan_room.new_fans_csv(), which filters through new_fans() (imports and Shopify pulls are excluded by tag) and fan_segments.contactable(); probed, returned a real CSV of the two fans captured that day.
- Routes: GET /room/fans/new.csv?days=7|30|90
- Files: app.py:4692-4703; fan_room.py:285 def new_fans_csv(), :87 def new_fans(), :59 days_from(); fan_segments.py:212 contactable()
- Access: Any signed-in account — no tier gate (probe: fan-plan got 200). Anonymous redirected to /login.

**Fan segmentation library**

Groups a fan list by place, matches it against tour cities, buckets consent age and separates the suppressed.

- Because: fan_segments.py is pure logic with no writes, and it is really called — fan_audience.build() uses summary(), contactable(), place_key(), city_key(), canonical() and regions(), and fan_room uses contactable() and new_fans; the tour overlap on /fans is computed against the account's real tour_shows rows.
- Routes: none of its own; feeds /fans, /room/fans and the CSV exports
- Files: fan_segments.py:100 regions(), :138 tour_overlap(), :188 consent_ages(), :201 suppressed(), :212 contactable(), :221 first_send(), :245 summary(); callers fan_audience.py:239, fan_room.py:222
- Access: n/a

**Hypeddit webhook receiver**

Accepts a fan posted to the account's secret URL and files them into the Fan CRM.

- Because: app.py:1324 def hypeddit_webhook() resolves the token, answers 200 fast, and hypeddit_ingest.receive() applies the daily cap, detects Hypeddit's test record, extracts the address from JSON/form/query however it is spelled and calls file_fan(), which upserts, tags "hypeddit", writes one hypeddit_gate consent, bumps total_captures, scores intent and notifies. Probed live: POST with {"Email Address":...} created the fan with tags ["hypeddit"] and intent Warm/25; an unknown token returned 404.
- Routes: GET/POST /webhooks/hypeddit/<token>
- Files: app.py:1323-1348; hypeddit_ingest.py:287 file_fan(), :311 receive(), :140 extract(), :183 is_test(); links_store.py:200 upsert_fan(), :397 add_fan_tags(), :460 add_consent(); db.py app_kv (hypeddit_token/user/log/count/last/day keys)
- Access: Anonymous — "/webhooks/" is in app.py _PUBLIC_PREFIXES so plan_gate lets it through; the URL token is the only authorisation. No plan gate.

**Legacy quick links**

The older single-target short links, created by an API call and listed on /links with their click counts.

- Because: app.py:11320 links_create() writes a real row through db.create_db_link and /l/<slug> falls back to it with store.log_click(); app.py:4372 legacy_link_delete() removes one, scoped to the account. It also inserts into the in-process links_config._smart_links list, which is per-process demo state and not what /links renders for a real account.
- Routes: POST /links/create, GET /l/<slug> (fallback), POST /links/legacy/<slug>/delete
- Files: app.py:11319 def links_create(), app.py:2076-2082 (fallback), app.py:4371 def legacy_link_delete(); links_config.py:49 create_smart_link(); db.py smart_links + link_clicks (db.py:90, db.py:98), get_db_links/get_db_link/delete_db_link
- Access: POST /links/create only checks current_user() for attribution, but /links is artist-gated so plan_gate refuses a lower plan first. Delete requires a signed-in account and is scoped by user_id.

**List import — cancel**

Throws the parked draft away without writing anything.

- Because: app.py:11257 def fans_import_cancel() calls db.drop_fan_import_draft(user_id, draft_id) (scoped to the user) and returns the artist to whichever page the draft's origin names, via the _IMPORT_ORIGINS allow-list so an arbitrary redirect cannot be injected.
- Routes: POST /fans/import/cancel
- Files: app.py:11256-11268; db.py:4367 drop_fan_import_draft(); app.py:11125 _IMPORT_ORIGINS
- Access: Any signed-in account; demo session redirected to /fans.

**List import — confirm**

Files exactly the rows the preview showed, once, in one transaction.

- Because: links_store.confirm_list_import() does the draft DELETE as the claim and the INSERTs on the same connection, tags new fans "imported", writes one list_import consent each, fills only a MISSING country/city on fans already here, and records the corrected summary into fan_imports; probed — 2 fans added, fan_imports row written with adds_up True.
- Routes: POST /fans/import/confirm
- Files: app.py:11233-11255; links_store.py:252 def confirm_list_import(); db.py fan_import_drafts + fan_imports tables (db.py:506, db.py:525)
- Access: Any signed-in account; demo session redirected to /fans; read team seats refused.

**List import — preview**

Reads a pasted or uploaded CSV, parks it as a draft and writes no fan.

- Because: app.py:11141 def ml_fans_import_list() parses with fan_list_import.parse(), counts with preview(), builds draft_rows() and stores them with db.put_fan_import_draft(); no INSERT into ml_fans happens here. Probed: a 2-row CSV redirected to /fans/import and ml_fans was still unchanged until confirm.
- Routes: POST /fans/import/preview, POST /links/fans/import/list (same handler)
- Files: app.py:11139-11201; fan_list_import.py:171 parse(), :243 preview(), :271 draft_rows(); db.py:4316 put_fan_import_draft(); templates/partials/fan_list_import.html, templates/fans_first_run.html
- Access: Any signed-in account (plans.required_tier("/fans/import") is None) — probe confirmed a fan-plan account completed the whole preview→confirm cycle and wrote 2 real ml_fans rows. Refused for the demo session (redirects to /fans). Read team seats are refused by team_seat_gate.

**List import — preview page**

Shows the counts, the skip reasons and a masked sample before anything is written.

- Because: app.py:11204 def fans_import_preview() reads the stored draft and renders fan_list_import.sample() (addresses masked by mask_email) plus the exact consent sentence confirm will write (_import_consent_line dates it from the draft, not from now); probed and the draft_id field was present.
- Routes: GET /fans/import
- Files: app.py:11203-11231, app.py:11223 def _import_consent_line(); fan_list_import.py:290 sample(), :299 mask_email — note mask_email is defined at fan_list_import.py:281; consent_note at fan_list_import.py:299; templates/fans_import_preview.html; db.py:4335 get_fan_import_draft()
- Access: Any signed-in account; demo session redirected to /fans.

**Public smart link page and redirector (/l/<slug>)**

The public campaign page (or a plain redirect for an older quick link), counting every view.

- Because: app.py:2043 smart_link_redirect() resolves the campaign, 410s an archived one, 404s a draft for anyone but its owner (owner_preview writes no events), writes a page_view ml_events row and renders link_campaign.html with the real destinations; a slug that is not a campaign falls back to db.get_db_link + store.log_click. Probed indirectly: subscribing through a published slug worked and the events landed.
- Routes: GET /l/<slug>
- Files: app.py:2042-2082; links_store.py:100 get_campaign_by_slug(), :153 track(), :137 get_destinations(); db.py:1799 get_db_link(), log_click(); templates/link_campaign.html, templates/link_landing.html, templates/link_campaign_unavailable.html
- Access: Anonymous — "/l/" is in app.py _PUBLIC_PREFIXES. A draft campaign is visible only to its own signed-in owner.

**Publish / unpublish / archive / duplicate a smart link**

Flips a campaign live or back to draft, archives it or copies it with its destinations.

- Because: All four call links_store.update_campaign or duplicate_campaign with real column writes; publish also writes a notification and the public page starts answering (probed: after publish, POST /l/<slug>/subscribe returned ok). Archive makes /l/<slug> answer 410 via link_campaign_unavailable.html.
- Routes: POST /links/<cid>/publish, POST /links/<cid>/unpublish, POST /links/<cid>/archive, POST /links/<cid>/duplicate
- Files: app.py:4348, :4362, :4380 (archive), :4395 (duplicate); links_store.py:34 update_campaign(), :113 duplicate_campaign(); db.py:5038 notify(); templates/link_campaign_unavailable.html
- Access: Artist tier or higher, own campaign only (_ml_owned). Read team seats refused.

**Region selection export ("Use this selection")**

Downloads the contactable fans in the ticked places as a CSV.

- Because: app.py:12230-12247 reads ?export=csv&region=... , calls fan_audience.selection_rows() which filters through fan_segments.contactable() so a suppressed fan can never be in it, and streams a real CSV; probed, returns text/csv with Email,Name,City,Country.
- Routes: GET /fans?export=csv&region=<key>
- Files: app.py:12230 (inside def fans()); fan_audience.py:493 def selection_rows(); fan_segments.py:212 def contactable(), fan_segments.py:88 def place_key(); templates/fans.html (form#au-sel)
- Access: Any signed-in account (no tier gate on /fans). Anonymous is bounced by plan_gate before the handler's own login_required_redirect() is reached.

**Remove a fan**

Deletes one fan record plus their consent log and their link events.

- Because: app.py:11284 def ml_fan_delete() calls links_store.delete_fan(), whose DELETE is scoped `WHERE id = ? AND user_id = ?` and then clears ml_consents and ml_events for that fan; the confirm text in templates/links_fans.html matches what the code does (it does not block the address).
- Routes: POST /links/fans/<fan_id>/delete
- Files: app.py:11283-11293; links_store.py:441 def delete_fan(); templates/links_fans.html (the per-row form)
- Access: Artist tier or higher. A read team seat is refused by app.py team_seat_gate (non-GET + access != "edit").

**Rotate the Hypeddit address**

Mints a new webhook token and kills the old one immediately.

- Because: app.py:11073 def ml_fans_hypeddit_rotate() calls hypeddit_ingest.rotate_token(), which writes the new token, points the reverse key at it and deletes the old reverse key, so user_for_token() stops resolving the old address.
- Routes: POST /links/fans/hypeddit/rotate
- Files: app.py:11072-11083; hypeddit_ingest.py:85 rotate_token(), :98 user_for_token(); templates/partials/hypeddit_connect.html
- Access: Artist tier or higher; abort(404) for the demo session; read team seats refused by team_seat_gate.

**Smart Link analytics**

Per-campaign visits, clicks, CTR, top services, referrers, UTM sources, a timeline and variant splits.

- Because: app.py:4404 ml_analytics() reads links_store.event_counts / breakdown / timeline / variant_stats, all of which are GROUP BY queries over the real ml_events rows written by /l/<slug> and /l/<slug>/go/<dest_id>.
- Routes: GET /links/<cid>/analytics
- Files: app.py:4404-4429; links_store.py:161 event_counts(), :168 breakdown(), :185 timeline(), :505 variant_stats(); templates/links_analytics.html; db.py ml_events (db.py:653)
- Access: Artist tier or higher, own campaign only.

**Smart Link autofill (Odesli)**

Paste one track URL and every platform destination plus the artwork fills itself in.

- Because: app.py:4232 ml_autofill() calls music_apis.odesli_lookup(), a real HTTP GET to api.song.link cached in api_cache, and maps the result through links_engine.ODESLI_TO_SERVICE; no key is needed. Not exercised live from here (no network calls made during this audit).
- Routes: GET /links/autofill?url=...
- Files: app.py:4232-4250; music_apis.py:72 odesli_lookup(); links_engine.py:34 ODESLI_TO_SERVICE; db.py api_cache (db.py:877)
- Access: Any signed-in account at the route itself (it only checks current_user()), but it is only reachable from the builder, which is artist-gated; anonymous gets 401 JSON — and plan_gate would bounce them first since /links is artist-tier.

**Smart Link builder**

Creates and edits a campaign: title, cover, release date, destinations, email-capture and consent settings.

- Because: app.py:4275 ml_new() and app.py:4308 ml_edit() write through links_store.create_campaign/update_campaign/set_destinations into ml_campaigns and ml_destinations; probed — POST /links/new created a campaign and redirected to its edit page. The cover-clear path (links_store.clear_campaign_cover) also unlinks only files this uploader wrote (mlcover_ prefix).
- Routes: GET/POST /links/new, GET/POST /links/<cid>/edit, POST /links/<cid>/cover/delete
- Files: app.py:4275, app.py:4308, app.py:4332 (ml_cover_delete); links_store.py:20 create_campaign(), :34 update_campaign(), :60 clear_campaign_cover(), :127 set_destinations(); links_engine.py:101 calculate_street_banker_score(); templates/links_builder.html
- Access: Artist tier or higher; _ml_owned() 404s a campaign that is not this account's. Read team seats cannot POST.

**Smart Link QR code**

Serves an SVG QR for the campaign's public link; scans of it are counted separately.

- Because: app.py:4446 ml_qr() renders an SVG, and the public page at app.py:2056 writes a qr_scan ml_events row whenever the link carries ?src=qr, so the count has a real source.
- Routes: GET /links/<cid>/qr.svg
- Files: app.py:4446 def ml_qr(); app.py:2055-2057 (qr_scan tracking); links_store.py:153 track()
- Access: Artist tier or higher, own campaign only.

**Smart Link variants**

Named per-channel variants of one link, each attributed separately in the event log.

- Because: app.py:4430 ml_variants() writes through links_store.create_variant into ml_variants, and app.py:2036 _ml_variant_id() resolves ?v=<slug> on the public page so mls.track() stores variant_id on the ml_events row.
- Routes: GET/POST /links/<cid>/variants
- Files: app.py:4430-4446, app.py:2036 _ml_variant_id(); links_store.py:487 create_variant(), :494 get_variant_by_slug(), :505 variant_stats(); templates/links_variants.html; db.py ml_variants (db.py:692)
- Access: Artist tier or higher, own campaign only.

**Smart Links manager (/links)**

Lists the account's campaigns and older quick links with their real counts.

- Because: app.py:4170 def links() renders store.get_db_links(user_id) and mls.list_campaigns(user_id); the seeded demo links from links_config are only included when get_links_data(demo=True), i.e. for a demo email (app.py:4173), so a real artist's totals are their own.
- Routes: GET /links
- Files: app.py:4169-4183; links_config.py:84 get_links_data(); links_store.py:105 list_campaigns(); db.py:1770 get_db_links(); templates/links.html
- Access: Artist tier or higher (plans._ARTIST_PATHS contains "/links"); probe: fan-plan got 402. Team seats: team_areas.room_for_path("/links") == "marketing", so it needs the Marketing box, not Fans.

### Partial

**Fan Club drops**

Posts a members-only update and emails every active member a sign-in link to it.

- Because: The write is real and unconditional — app.py:6536 fan_club_drop_post() calls db.add_club_drop, and the delete at app.py:6585 is scoped to the artist. The notification half only runs when RESEND_API_KEY is set (otherwise it redirects ?email_off=1, which is honest), it is capped at the first 200 members, and the redirect carries the real notified/failed counts. The sends were not exercised here.
- Routes: POST /fan-club/drops, POST /fan-club/drops/<drop_id>/delete
- Files: app.py:6535-6589; db.py:2420 add_club_drop(), :2438 delete_club_drop(); email_provider.py; templates/fan_club.html
- Access: Artist tier or higher (/fan-club prefix); read team seats cannot POST.

**Fan Club members area**

A paying member reads the artist's members-only drops after a magic link puts them in the session.

- Because: The gate is real — app.py:6483 club_members_area() checks a signed itsdangerous token (7 days, salt "club-member") against db.get_active_club_member and renders the real club_drops rows. The way in depends on email: app.py:6512 club_members_link() only sends when emailer.configured(), and when the send fails it honestly redirects with ?email_error=1 rather than claiming an inbox. With no RESEND_API_KEY a member who lost their session cannot get back in.
- Routes: GET /club/<slug>/members, GET /club/<slug>/members?token=..., POST /club/<slug>/members/link
- Files: app.py:6482-6534, serializer app.py:6474 _club_serializer(); db.py:2411 get_active_club_member(), :2430 list_club_drops(); email_provider.py:28 configured(); templates/club_members.html
- Access: Anonymous (public prefix); the signed token or an existing session key "club_member_<artist_id>" is the authorisation.

**Fan Club public page and paid join**

The public membership page for an artist's slug and the Stripe Checkout that joins a fan.

- Because: The page is real (app.py:6420 resolves the artist by their EPK slug and 404s when the club is off) and the claim path is real (app.py:6455 club_join creates a Stripe subscription Checkout; the return at app.py:6427 trusts only what Stripe says about the session, and app.py:5766 handles the same event from the webhook so it is claimed once). But joining is shut twice over: it needs STRIPE_SECRET_KEY (stripe_billing.configured()) AND the owner's switch, sales_switch.is_on(), which reads app_kv "online_sales" and defaults to off — with either off the form is replaced by sales_switch.CLOSED ("email … for details") and club_join redirects straight back. Neither half could be exercised here.
- Routes: GET /club/<slug>, POST /club/<slug>/join
- Files: app.py:6419-6480; stripe_provider.py:552 create_club_checkout(), :678 get_checkout_session(); sales_switch.py:22 is_on(); db.py:2373 add_club_member(); templates/club_public.html
- Access: Anonymous — "/club/" is in _PUBLIC_PREFIXES. The owner flips the sales switch at app.py:13404 (owner-only).

**Fan Club Stripe webhook**

Adds a member on a paid checkout and cancels them when the subscription ends.

- Because: Both branches are real code — app.py:5766 handles checkout.session.completed with metadata kind "fan_club" (adds the member, upserts the fan, writes a fan_club consent, notifies, and only on a genuinely new row so replays do not re-notify), and app.py:5859 calls db.cancel_club_member_by_subscription on the deletion event. The receiver 404s unless stripe_billing.webhook_accepts() (STRIPE_WEBHOOK_SECRET or a stored secret) and verifies the signature, neither of which is configured here, so nothing could be exercised.
- Routes: POST /webhooks/stripe
- Files: app.py:5755 def stripe_webhook(), :5766-5779 (fan club branch), :5859 (cancel); stripe_provider.py:110 webhook_accepts(), :767 verify_webhook(); db.py:2373 add_club_member(), :2400 cancel_club_member_by_subscription()
- Access: Anonymous ("/webhooks/" is public); the Stripe signature is the authorisation.

**Fan CRM filters (missing email / top intent)**

Narrows the CRM to fans with no email address, or to the Hot and Superfan bands.

- Because: ?intent=top works — it filters on intent_level against fan_room.TOP_BANDS and those bands are really written by links_engine.calculate_fan_intent. ?missing=email cannot match anything: every write path requires a valid address (links_store.upsert_fan is only ever called with a checked address — app.py:2113 ml_subscribe validates "@", hypeddit_ingest.py:294 file_fan only after valid_email(), shopify_customers.py:310 skips rows with no email, links_store.confirm_list_import skips `if not email`), so the Fan Room move "Find N missing emails" that links here can never fire either.
- Routes: GET /links/fans?missing=email, GET /links/fans?intent=top
- Files: app.py:11021-11029; fan_room.py:127 (the move that links to ?missing=email) and fan_room.py:145 (?intent=top); links_engine.py:160 calculate_fan_intent; templates/links_fans.html
- Access: Artist tier or higher (same gate as /links/fans).

**Fan intent scoring**

Turns a fan's tracked behaviour into a 0-100 score and a band.

- Because: links_engine.py:160 calculate_fan_intent() weights four counters, and the captures and pre-saves halves are really fed (bump_fan is called with total_presaves at app.py:2005 and app.py:2115 and with total_captures at app.py:2115 and hypeddit_ingest.py:301). The visits and clicks halves — worth 30 of the 100 points — are never incremented by any production code path: grep for bump_fan found only those three call sites plus tests/test_fan_dashboard.py:50. The band "Cool" that fan_audience.INTENT_ORDER and INTENT_COPY describe is never produced by this function either; only the showcase generator writes it.
- Routes: none of its own; called from /l/<slug>/subscribe, /presave/callback and the Hypeddit receiver
- Files: links_engine.py:160 calculate_fan_intent(), :180 INTENT_TONES; links_store.py:373 _FAN_COUNTERS, :376 bump_fan(), :390 set_fan_intent(); fan_audience.py:169 INTENT_ORDER/INTENT_COPY
- Access: n/a (server-side, runs for whichever account owns the campaign).

**Fan Room (/room/fans)**

The Fans room's opening screen: owned audience, new-in-window, reachable share, next best moves, a city constellation and the room's tool tiles.

- Because: Every figure but one is real — fan_room.build() reads the same rows the Audience screen reads (links_store.list_fans + fan_audience.for_account), the tile statuses are true counts (fan-crm reads audience total, fan-club reads active club_members, marketplace counts open collab_requests), and the "Get their emails" move hands over a real CSV. The "fan lifecycle" rail is fixed decorative copy: fan_room.py:47 LIFECYCLE is five hard-coded (key, name, line) tuples rendered by templates/room_fans.html:99 with no count attached to any stage. The "Find N missing emails" move can never appear (no write path produces an empty-email fan).
- THE RACK AND THE MAP (owner, 2026-09-23: every room's rack is the shorter three-window plate). The working room draws the rooms' shared plate, static/img/room-plate.webp through templates/partials/cc_rack.html, with its three readings on the three screens: ON FILE (fans on file), REACHABLE (the contactable share, "can be emailed") and NEW (smart-link arrivals in the window), from fan_room.windows() via fan_room.rack_screens(). The new plate prints no names, so each screen carries its own label. A reading is set as a figure; an absence as words - REACHABLE says "None yet" with nobody on file, while a real 0% (every fan suppressed or without an address) is a reading and is set as one. The old Audience Monitor plate's big window, the city constellation, is its own panel directly under the rack (AUDIENCE PULSE / Reachable fans by city, .fr-map-panel), nothing lost: dots sized by fans, the biggest four named, lines to nearest neighbours, and "No fan cities yet" in words when fans exist but no city can be plotted. The names are SVG <text> inside the viewBox (13/12 units), set larger at each narrower container step (fan-room.css frmap steps = fan_room.LABEL_STEPS) so they read at 13px/12px or more from a 240px map up; fan_room._place_labels() turns a name to the side that keeps it clear and, at a step where it would still run into a bigger city's name, leaves it out there (is-off-N) rather than draw two names over each other - New York and Chicago did, at 1280 and at 375, until 2026-09-23. The drawing carries an aria-label naming the cities it labels. The foot line under the map keeps the Live/Sample mark, which is what stops a demo account's generated audience reading as real (it read "Live8 cities" with no space until the same day). fan_room.PLATE, box(), standby() and the STANDBY_* reel/tip/ticker/frame copy went with the old plate (nothing else read them); static/img/fans-plate.webp stays on disk, drawn by nothing, in case the owner wants it back. REACHABLE is a strict figure: fan_segments.contactable() requires an email address as well as an unsuppressed row, because you cannot email somebody who has no address.
- Routes: GET /room/fans (dispatched from /room/<room_key>)
- Files: app.py:4636 def room_screen() → app.py:4664 def _fan_room(); fan_room.py build(), windows(), rack_screens(), moves(), pulse() with _place_labels() and LABEL_STEPS, tile_status(); templates/room_fans.html; templates/partials/cc_rack.html; static/css/fan-room.css (.fr-map*), static/css/command-zero.css (.cz-rack, .cz-screen*); rooms.py:23 ROOMS["fans"]; stores links_store.py, fan_audience.py, db.py (get_fan_club, list_club_members, collab_requests query at app.py:4676)
- Access: Any signed-in account — plans.required_tier("/room/fans") is None (verified); probe confirmed a fan-plan account got 200. rooms.get_room() takes the plan, so Label-only cards are filtered out. Team seats: app.py team_seat_gate → team_areas.allows() permits /room/<key> only when that room key is ticked. Anonymous redirected to /login.

- THE PAGE FROM ZERO (Fans spec + mockup, owner, 2026-09-22; built 2026-09-23). An account with no fans gets an onboarding page, not an empty dashboard, in the spec's order. THE RACK IS STATIC on this room now (owner: "static on zero-state pages"; the animated standby stays on the other seven). Since 2026-09-23 it is the rooms' shared three-window plate (partials/cc_rack.html, fan_room.zero_page()["screens"]) with one module on each screen; the .fr-z-mod* / .fr-z-win* rules of the first cut are gone. As first built, the big window of the Audience Monitor plate carried the three modules SIDE BY SIDE with a rule between - PURPOSE "Own the listener relationship" / START HERE "Choose how to add your first fans" / GOOD TO KNOW "Nothing is added until you review and confirm" - the owner's one-wide-screen mockup, in the screen's green, list semantics, icons above. The three small windows were photographed for a figure and a word and the spec's sentences did not fit them at any width tried (62px tall at 1300px), so they stay UNLIT until there is data to read (STATUS / NEXT ACTION per the spec's return state). Below: CHOOSE YOUR STARTING POINT, two EQUAL cards (capture -> /links/new?type=bio, import -> /fans, both carrying returnTo=/room/fans; the capture button filled and the import outlined only so the eye has an order, neither smaller or lower); HOW THE FAN WORKFLOW WORKS, the spec's five stages (Capture highlighted, Confirm consent, Organize, Activate, Measure) as education - nothing complete, in progress or blocked, no percentage; the populated room keeps its own LIFECYCLE rail; YOUR FANS WILL APPEAR HERE beside YOU STAY IN CONTROL (three checks, in words); NOT SURE WHERE TO BEGIN? with the pill and Ask; the tool tiles under MORE FAN TOOLS (<details>, OPEN by default since 2026-09-23 - owner: "a lot of people won't read, they need to see it"; closable, never closed to start). Forbidden things absent: no table, no "0 fans" (the import move's reach is gone), no 0%, no charts, no placeholders. A SEAT sees only doors it can open: the capture card, the help pill and "How fan capture works" read fr.can_capture, the hero pill's gate - the seat probe found the first cut offering a Fans-only seat /links/new and /links, the defect the morning fixed on the old page. The populated room is untouched (locked by test). fan-room.css carries the rules under .fr-z-* / .fr-start* / .fr-fold; nothing kit-owned is redeclared. ZERO_RACK / STARTS / WORKFLOW / CONTROL / HELP_QUESTIONS and zero_page() in fan_room.py. The owner's mark on a page they hid (page_switches) stays on the drawer's tile from zero - the "Hidden" pill in the room's own status classes - because rooms.build keeps that card for the owner alone; the seven rooms dropped the state on the way to their zero drawers until 2026-09-23 (the Marketing room had it from the start), and the populated Studio, Stage, Analytics, Business and Releases rooms, whose tile feet were empty, show the same pill from the same day.
**Marketing Room (/room/marketing)**

The Marketing room's opening screen: a windowed hero of link traffic, a five-stage rail from Written to Heard, recommended actions, media contacts by city and three closing tiles.

- Because: every figure is a COUNT over this account's own rows. The hero's visits, clicks and pre-saves are ml_events page_view / service_click / presave_notify joined to ml_campaigns on user_id and filtered on e.created, so the range chooser governs all three and the line under the controls says so; the ml_fans counter columns total_visits and total_clicks are never read (nothing in the app increments them). The rail counts the whole record: press_releases status='ready', press_pitches with sent_at, SUM(press_recipients.open_count), press_coverage, and all-time page_view. Each action row is its own EXISTS query and a row whose count is zero is dropped rather than drawn. The map is a constellation, not a basemap: contacts are grouped by city AND country, through board_taxonomy's alias table so six spellings of one metro (new york, nyc, brooklyn) are one row under the metro's own name, and a city is placed only where the metro's own country agrees with the record's, so London CA is not plotted in England; anything the table cannot place is left off and counted in the footnote. Two names are kept apart by the boxes they will really occupy at marketing_room.MIN_LABEL_PANEL, and below that panel width the stylesheet's @container rule draws the first name only. The press kit tile says Live only when epk_profiles holds saved data, because _ensure_epk_slug mints the public address on a plain page view. An action row whose destination this reader would be bounced at is dropped, the way a zero row is: a Marketing-only team seat is not shown the rollout row, which leads into the Releases room. The hero's large figure is a link to /links, the page it counts, and the room's only door to Smart Links in the rooms layout. The demo account alone is handed marketing_room.showcase(), an in-memory literal that is never written to the database.
- Substitutes (owner's design could not be built as drawn): his fifth action row "Release with no smart link" is a rollout with no link connected (ro_campaigns.ml_campaign_id is the only stored join to a smart link), worded to his ruling of 2026-09-21. It states the consequence, offers ours and never says another service is disallowed. His map sub-heading "Media contacts around the world" is "The cities your media contacts work in", because there is no world basemap in the repository. His "Sample" pill shows only on the demo; a real account's panel carries the Live mark instead.
- THE RACK (owner, 2026-09-23: every room but Studio on the shorter three-window plate): the working room draws the rooms' shared plate, templates/partials/cc_rack.html over static/img/room-plate.webp, as the page from zero does, with the three screens the owner approved - READY (press_releases status='ready'), SENT (press_pitches with sent_at) and COVERAGE (press_coverage), built by marketing_room.rack_screens(). The plate prints no names, so each screen says what it is; a count with nothing in it is the words "None yet", never a 0; no screen is a door. The old BROADCAST plate (static/img/marketing-plate.webp, 1859x846, left on disk, drawn by nothing) had five windows, and nothing it showed is lost: VIEWS (SUM(press_recipients.open_count)) has no screen and rides on Sent's line ("Pitches Street Banker sent · N views", "no views yet" when none), and THE STORY - the newest announcement on file, headline falling back to title, with its status lamp, or "No announcement yet" - is its own panel (.mk-story) directly under the rack and its caption line, above the stage rail. marketing_room.PLATE, PLATE_ORDER, box() and plate_windows() and the sheet's .mk-pl rules are gone. TWO WORDS THE AUDIT CHOSE BEFORE THE OLD PLATE WAS RENDERED, and the rack keeps both: Sent is what Street Banker sent, and its line says so, because press_pitches.sent_at is written only by the platform's own send loop, so a pitch posted from the artist's own inbox never lands in it; and VIEWS rather than opens, because press_store.mark_opened fires when a journalist LOADS the announcement page and a figure called opens would be read as an email open every time. The caption line under the rack says both ("Sent counts pitches Street Banker sent ... A view is a journalist opening your announcement page"). The band above the rack is smart-link data and does not overlap it; the gold rail below covers the same concepts in words (its Opened stage still says "N opens logged"), which is an open question for the owner. Measured with headless Chrome on 2026-09-23: every screen's name, figure and line inside its glass at 1280 and 1920; at 375 the screens stack and nothing widens the page.
- The page from zero (owner's Marketing spec + mockup, 2026-09-23): an account with no campaign, no link event, no press activity and no contact meets an onboarding page rather than a 30-day filter, empty figures, a press funnel, a contact-city report or a recommendation, in the spec's order - the header (subtitle "Plan the message, reach the right people, and know what to do next.", the account chip kept, NO date chooser, primary "Plan your first campaign" -> /links/new?returnTo=/room/marketing&from=marketing-zero-state, the campaign builder whose first question is the goal), the Command Center's photographed three-screen plate drawn STATIC with PURPOSE / START HERE / GOOD TO KNOW, "Start with one goal" with the "Choose your first marketing goal" card ("Start planning"; "Compare campaign goals" opens the spec's five goals and their smallest toolsets in place) beside "What Marketing will organize" - the four areas as doors (Campaign plans -> /links/new, Press & media -> the press-desk card, Smart links & fan capture -> the links card, Content & rollout -> /rollout-studio; words, not a door, for a seat that cannot open the page - a Marketing-only seat is refused at the Rollout Engine), the five-step workflow numbered 1-5 as the mockup numbers it with Choose goal lit and no percentage, "Your campaign plan will appear here" ("How campaigns work" into the workflow; "Marketing checklist" opens the spec's pre-activation list in place: one message, one call to action, a consented audience, a channel, confirmation) beside "No results are measured yet", help, and "More Marketing tools" - a drawer that starts OPEN (owner's ruling the same day) with Press Desk and the Press Kit, Smart Links, and Referrals under their own headings as the spec places them. The room says "Your first campaign is planned. Marketing will show its results once something is sent or published." only when a campaign is really on file (marketing_room.done_line). The state is read in ONE try (campaigns and every figure the room counts); a failed read is templates/room_marketing_error.html at 503 ("We could not load Marketing", Try again / Open Smart Links), never a fresh account. The demo account is never from zero: it is the showcase. A seat without edit access gets the card without its door. One campaign, event, announcement, contact or rollout and the populated room returns untouched. The animated standby that ran on the plate for an empty account is retired on this room.
- Routes: GET /room/marketing?days=7|30|90 (dispatched from /room/<room_key>)
- Files: app.py room_screen() → app.py _marketing_room(); templates/room_marketing_error.html; templates/partials/cc_rack.html + static/css/command-zero.css + static/img/room-plate.webp (the owner's shorter three-window plate, 2026-09-23) (the page from zero and the working room); marketing_room.py new_account(), done_line(), zero_page(), rack_screens(), story(), build(), for_account(), stages(), actions(), constellation(), group_cities(), metro_for(), country_code(), _label_box(), tile_status(), showcase(); templates/room_marketing.html; static/css/marketing-room.css; rooms.py ROOMS["marketing"]; stores db.py (ml_events, ml_campaigns, ro_campaigns), press_store.py (press_contacts, press_releases, press_pitches, press_recipients, press_coverage), board_taxonomy.METROS
- Access: Any signed-in account, as /room/<key>: no tier gate. rooms.get_room() takes the plan and the page switches, so a hidden card leaves the tile grid for everybody but an owner. Team seats need the "marketing" room ticked. Anonymous redirected to /login.

**Marketing room card list and the press tab strip**

The Marketing room holds four cards (links, press-desk, epk, referrals); the press pages draw their own tab strip in both layouts again.

- Because: the room's screen closes with the three tiles the owner drew, so rooms.py collapsed the four press cards into press-desk, moved rollout to the Releases room and dropped reach (hubs.tool_suites() already carries REACH on the suites strip at the same address). links stays a card so /links keeps its way back to the room, but the screen shows it as the hero figures and the rollout action rather than as a tile. press-contacts, press-announcements and press-coverage are now in no room, so the `{% if not rooms_nav %}` guard came off templates/press/_shell.html and templates/epk.html: without it those three pages would have no door in the rooms layout. They keep their live flag and their page switch through rooms.parent_of() == "press-desk".
- Routes: unchanged (GET /press-desk, /press-desk/contacts, /press-desk/announcements, /press-desk/coverage, /epk, /rollout-studio)
- Rooms for team seats: /rollout-studio and /rollout belong to Releases alone. team_areas.EXTRA["marketing"] listed /rollout-studio as well, so two rooms claimed one prefix and room_for_path() answered "releases" only because rooms.ROOMS names Releases first (honesty review, 2026-09-21).
- Files: rooms.py ROOMS["marketing"], ROOMS["releases"], EXTRA; team_areas.py EXTRA, room_for_path(); templates/press/_shell.html; templates/epk.html; tests/test_rooms.py; tests/test_team_rooms.py
- Access: unchanged.

**Release-day email to captured fans**

The first page view after release day emails every consented fan of that campaign the listen link.

- Because: app.py:1679 _send_release_emails() is real — it claims a release_email_sent flag in the campaign settings before sending, builds the HTML and calls emailer.send() per fan — but it only runs when RESEND_API_KEY is set (emailer.configured()), and the recipient list is links_store.campaign_fans(), whose query joins ml_consents with no `suppressed` filter, so a suppressed fan would still be mailed. Not exercised here (no key).
- Routes: triggered inside GET /l/<slug> (no route of its own)
- Files: app.py:1679-1703, called from app.py:1708 _process_due_presaves(); links_store.py:452 campaign_fans(); email_provider.py:28 configured(), release_email_html()
- Access: No user-facing gate — it fires on a public page view of a released campaign. Nothing in the UI triggers it directly.

**Seeded example smart links**  *(status corrected on review)*

Three invented links with invented click totals, shown on /links to the demo account only.

- Because: The list is not fixed at three and is not demo-created-only. `links_config.create_smart_link()` ends with `_smart_links.insert(0, link)` (links_config.py:64), and `POST /links/create` (app.py:11321, reachable from the quick-link modal in templates/links.html:271 via fetch) calls it for every signed-in account, so the module-level list grows with REAL accounts' quick links for the life of the worker process. Probed in one process: a fresh artist account created "Legacy One" through /links/create; `links_config._smart_links` then held ['lnk-4','lnk-1','lnk-2','lnk-3'], and the demo login (demo@streetbanker.io) rendered "Legacy One" on its own /links page, where `_links_totals` (app.py:4186) counts it into the demo's Active Links and Total Clicks tiles. The demo-only guard in `get_links_data(demo=...)` protects a real artist from the seeds, as the entry says; nothing stops a real artist's link title and slug reaching the shared demo login in the other direction.
- Routes: GET /links (demo session only)
- Files: links_config.py:15 _smart_links, :84 get_links_data(); app.py:4172-4174; templates/links.html
- Access: Demo email only.

**Shopify customer import**

Reads the connected store's customers and files the email-subscribed ones as fans.

- Because: The write half is real and verifiable in code: shopify_customers.import_fans() upserts through links_store, tags "shopify" (+"customer" when orders > 0), skips unsubscribed and no-email rows and counts both, and app.py records every run into fan_imports including the vendor's error text. The read half could not be exercised from here — no SHOPIFY_* is set, so shopify_customers.configured() is False, the panel is not drawn and the route redirects ?imp=off. It is also unreachable for every non-owner account: app.py:10967 _shopify_import_allowed() is `_is_owner_email(user["email"])` and the route abort(404)s otherwise, so no artist can ever run it.
- Routes: POST /links/fans/import/shopify
- Files: app.py:11084-11123, gate app.py:10967 def _shopify_import_allowed(); shopify_customers.py:281 fetch_customers(), :304 import_fans(), :212 status(); db.py:4271 add_fan_import(); templates/links_fans.html (#shopify-import)
- Access: Owner only (_is_owner_email, hashes at app.py:100 plus OWNER_EMAILS); 404 to everyone else. Also requires the artist tier gate on /links/fans to see the page at all.

**Shopify reconnect**  *(status corrected on review)*

Forgets the cached Admin and Storefront tokens so the next call mints fresh ones.

- Because: app.py:11269-11282: the entire body is `if shopify_customers.uses_grant(): forget_grant(); token()` followed by `redirect("/links/fans?imp=reconnected#import")`. The entry's because omits that guard. `uses_grant()` (shopify_customers.py:68) is `bool(client_id() and client_secret())` — SHOPIFY_CLIENT_ID **and** SHOPIFY_CLIENT_SECRET — so on a service holding only a legacy SHOPIFY_ADMIN_TOKEN, or holding nothing (probed on this checkout: `shopify_customers.configured()` is False), the route writes nothing at all and only redirects. It is additionally 404 to every non-owner (probed with a fresh artist account: POST /links/fans/shopify/reconnect -> 404), and "reconnected" appears in neither `_IMPORT_ERRORS`/`_import_result` (app.py:11127-11137) nor the `imp_note` map passed to links_fans.html, so pressing it says nothing back. The forget_grant() writes themselves are real (shopify_customers.py:131-137 blanks GRANT_KEY, GRANT_ERROR_KEY, shopify:storefront-token and shopify:storefront-token-error), but they are unreachable as configured.
- Routes: POST /links/fans/shopify/reconnect
- Files: app.py:11269-11282; shopify_customers.py:130 forget_grant(), :86 granted_token(), :205 token(); db.py app_kv table (db.py:959)
- Access: Owner only (_shopify_import_allowed → abort(404)).

**Spotify pre-save**

A fan authorises Spotify on a pre-release link and the track is saved to their library on release day.

- Because: The whole flow exists in code and writes real rows — app.py:1980 presave_start() mints a nonce and redirects to Spotify, app.py:1989 presave_callback() checks the nonce, exchanges the code, stores an encrypted refresh token in spotify_presaves, upserts the fan with a spotify_presave consent and scores them; delivery runs lazily in app.py:1705 _process_due_presaves() on the next page view. It is inert without SPOTIFY_CLIENT_ID/SPOTIFY_CLIENT_SECRET/SPOTIFY_REDIRECT_URI (spotify.configured() gates both the start route and delivery), and none of that could be exercised here — no keys, no network.
- Routes: GET /presave/<slug>/start, GET /presave/callback, POST /presave/retry-reset, GET /presave/diag
- Files: app.py:1979, :1988, :1965, :1861; spotify_provider.py:29 configured(); links_store.py:200 upsert_fan/:460 add_consent/:376 bump_fan; db.py spotify_presaves (db.py:864), pending_spotify_presaves/resolve_spotify_presave
- Access: /presave/ is in _PUBLIC_PREFIXES, so start and callback are anonymous (the state nonce is the guard). /presave/retry-reset needs any signed-in account and only touches its own campaigns. /presave/diag is plan=="label" only, otherwise 404.

### Stubbed

**Discover sample feed**

Twelve invented tracks with invented artists and invented play counts, browsable by genre and mood, shown to the showcase logins only and labelled on the page as made up.

- Because: discover_config._TRACKS is a hand-written list ("Nova Reign", "Midnight Drive", plays 5200000); get_discover_data() returns it only when called with showcase=True and otherwise returns _nothing_to_show(), every list empty. app.py discover() passes showcase=_session_is_demo(), the same gate the Audience showcase uses. Probed both ways on 2026-09-21: demo-fan@streetbanker.io got the twelve tracks under a "Sample feed" banner reading "Every artist, title, cover and play count below is made up"; a freshly signed-up fan account got none of the twelve names, titles or figures on the unfiltered page, on any of the nine genre filters, on any of the six mood filters, or with a search running. The nine artist_ids link to /network/<id> profiles and all nine were checked against network_config._PROFILES and exist (this closes the open question logged under Unverified).
- Routes: GET /discover (the browse sections), GET /discover?genre=&mood= (showcase session only)
- Files: discover_config.py (_TRACKS, GENRES, MOODS, get_discover_data, _nothing_to_show); app.py discover(); templates/discover.html (everything inside `{% if d.showcase %}`); static/css/discover-feed.css (.dc-sample banner)
- Access: Showcase session only (_session_is_demo, i.e. the four seeded addresses in demo_accounts.ACCOUNTS). Until 2026-09-21 it was served unlabelled to every visitor including real fan accounts, which is the honesty defect this entry records as fixed. Note the sidebar still stamps Discover with the "Sample" badge from hubs.py for every account; that now understates a real account's page, which shows real search results and an honest empty state.

**Discover likes and follows**

A heart on a sample track and a Follow button on a sample artist, saved in the browser session and attached to nothing.

- Because: like_track/follow_artist mutate the set the caller hands them and discover_config keeps no module state (locked by tests/test_shared_state.py); app.py _discover_state()/_keep_discover_state() read and write session["discover_likes"]/["discover_follows"], so they last as long as the cookie and reach no table. Both routes run _discover_sample_only() first, which answers 404 for any session that is not a showcase one, because a follow handed to a real account is a relationship that does not exist. follow_artist now also refuses an id the feed does not carry: it previously accepted any string, so POST /discover/follow/beyonce answered {"following": true}. Probed: a real fan got 404 with nothing written to the session; the demo fan toggled tr-1 and nova-reign and got 404 on beyonce.
- Routes: POST /discover/like/<track_id>, POST /discover/follow/<artist_id>
- Files: app.py _discover_state(), _keep_discover_state(), _discover_sample_only(), discover_like_route(), discover_follow_route(); discover_config.py like_track(), follow_artist(), sample_artist_ids(); the inline script in templates/discover.html
- Access: Showcase session only. Anonymous is bounced to /login by plan_gate.

**Discover empty state**

What a real account sees on the fan page: what the feed will be, where it will come from, and four real searches to start with.

- Because: templates/discover.html renders it when `not d.showcase and not real_query`, and the copy states plainly that the feed "is not built yet", that it "fills from a music data source once one is connected, and from Street Banker artists who choose to be listed", and that the alternative was "a wall of acts that do not exist". It writes nothing and reads nothing; it is Stubbed because the feature it stands in for does not exist yet. Probed with a fresh fan account.
- Routes: GET /discover (branch)
- Files: templates/discover.html; static/css/discover-feed.css (.dc-empty)
- Access: Any signed-in non-showcase account, artist or fan.

**Audience showcase**

Roughly 14,400 generated fan rows built through the same builder, shown to the demo login and labelled.

- Because: fan_audience.py:520 SHOWCASE_REGIONS and :534 showcase_rows() generate the rows from fixed city/count tuples, and :547 showcase() caches one build per day per process; app.py:12227 hands it over only when _session_is_demo(). Probed with demo@streetbanker.io: /fans and /links/fans carried "Showcase.", /room/fans carried "Sample data.", and a real account never reached any of them.
- Routes: GET /fans, GET /links/fans, GET /room/fans (demo session only)
- Files: fan_audience.py:517-564; app.py:12227, app.py:10982, app.py:4654 _fan_room_rows(); templates/fans.html:46, templates/room_fans.html:90
- Access: Demo session only (_session_is_demo).

**Fan CRM demo rows**

The demo login sees 200 of the Audience showcase's generated rows in the CRM table instead of an empty list.

- Because: app.py:10982 def _showcase_crm_rows() returns fan_audience.showcase_rows() (generated in fan_audience.py:534 showcase_rows, emails showcase-N@example.com), capped at _SHOWCASE_CRM_ROWS = 200, with id="" so nothing can be removed and no score; probe with demo@streetbanker.io found exactly 200 showcase-N@example.com rows and the "Showcase." label, and the Hypeddit and import panels suppressed.
- Routes: GET /links/fans (demo session only)
- Files: app.py:10978-10996; fan_audience.py:520 SHOWCASE_REGIONS / fan_audience.py:534 showcase_rows(); templates/links_fans.html
- Access: Only the showcase session (app.py _session_is_demo()). A real account can never reach it — the branch is `if showcase:`.

**Fan engagement counters (visits and clicks)**

Per-fan visit and click totals shown in the CRM export and the segment averages.

- Because: ml_fans.total_visits and total_clicks exist (db.py:674-675) and are exported (app.py:11317) but nothing writes them: bump_fan is only ever called with total_presaves or total_captures in production code, so both columns stay 0 for every real fan. fan_audience._clicked() (fan_audience.py:184), which reads total_clicks, has no caller at all.
- Routes: surfaced in GET /links/fans/export.csv
- Files: db.py:666-683 ml_fans; links_store.py:373-382; app.py:11313-11318; dead helper fan_audience.py:184 def _clicked()
- Access: n/a

**Fan Label**

A fan-funded label page with a raise total, backers, milestones and demo voting.

- Because: app.py:12192 fan_label() renders community_config.get_fan_label_data(), which returns is_sample True with a hard-coded raised/goal, backers 342 and a fixed demo list; the votes at app.py:12197 are kept in the visitor's own session (session["fan_label_votes"]) and never persisted. docs/PARKED_PAGES.md:16 lists it as parked for exactly this reason.
- Routes: GET /fan-label, POST /fan-label/vote/<demo_id>
- Files: app.py:12191-12204; community_config.py (get_fan_label_data, vote_demo); templates/fan_label.html; docs/PARKED_PAGES.md:16
- Access: Any signed-in account (no tier gate). team_areas.EXTRA puts it in the Fans room.

**Suppression (do-not-contact)**

Marks a fan as not to be emailed, with the reason, and keeps them out of sends and the default export.

- Because: The read half is everywhere — links_fans.html:84 shows the reason, fans.html:94 and :262 count the suppressed per region, fan_segments.contactable() is the single door used by every export and the Fan Room CSV. The write half has no caller: grep for suppress_fan and unsuppress_fan across the repo found only their definitions at links_store.py:352 and :366 plus tests/test_fans_audience.py:66-67 and tests/test_collab_marketplace.py:290. There is no route, form, unsubscribe link or bounce/complaint webhook that sets ml_fans.suppressed, so on a real account the column can only ever be empty.
- Routes: none — no route writes it
- Files: links_store.py:352 def suppress_fan(), :366 def unsuppress_fan(); db.py:1075-1083 (the ALTER that adds suppressed/suppressed_at); readers fan_segments.py:201/:212, fan_audience.py:284, app.py:11310, fan_room.py:285; templates/links_fans.html, templates/fans.html
- Access: n/a — unreachable from the product.

**Voice of Fan**

A page that states the feature is in preview and lists what it would do.

- Because: There is no handler for it in app.py; the route is registered in a loop at app.py:8651-8653 for every command_center.MODULES entry whose status is "preview", rendering the generic module_preview.html with the four bullet strings from command_center.PREVIEW_FEATURES. No fan data is read.
- Routes: GET /voice-of-fan
- Files: app.py:8641-8653 (_module_preview + the registration loop); command_center.py:116 (the MODULES row), :199 (PREVIEW_FEATURES); templates/module_preview.html
- Access: Any signed-in account (no tier gate). team_areas.EXTRA puts it in the Fans room for team seats.

### Dead code

**community_config.get_fan_dashboard_data**

The old invented fan panel: 1,240 superfans, 41,000 casual listeners and a spend leaderboard.

- Because: It is imported into app.py at line 209 and never called — grep for "get_fan_dashboard_data" in app.py returns only that import line. No template references it. It is the data fan_dashboard.py's docstring says was removed from /fans; the function body still contains the fabricated segments, LTVs and handle leaderboard.
- Routes: none
- Files: community_config.py:140 def get_fan_dashboard_data(); unused import at app.py:209
- Access: n/a

**fan_dashboard.py**

An honest fan-dashboard builder that reads the account's real fans, segments, sources and consent gap.

- Because: No route, template or non-test module calls it. Grepped the whole repo for "fan_dashboard" and "fan_dashboard_for": the only hits outside the module itself are tests/test_fan_dashboard.py and tests/test_fan_tiles.py. The Audience redesign (fan_audience.py) replaced it and /fans renders fan_audience instead. It also carries a latent bug the live code does not: its summary reads events.get("presave"), but links_store.track() only ever writes the event type "presave_notify", so that figure would always be 0.
- Routes: none
- Files: fan_dashboard.py:87 def fan_dashboard_for(); exercised only by tests/test_fan_dashboard.py:86 and tests/test_fan_tiles.py:41
- Access: n/a

> Noted by the reviewer as not yet written up in this area: Product tour: Smart Link + Fan Intelligence example page — Stubbed. A public, labelled example of a smart link and a "fan intelligence workspace", with no real data behind it. Routes: GET /product-tour/smart-link. Files: app.py:14110 @app.route, handler app.py:14111 def product_tour_smart_link(); product_tour_config.py:149 SMART_LINK, :174 FAN_PANEL (hard-coded tuples; every row carries a capability_status key — sms_capture=coming-soon, release_emails/geographic_response/conversion_events/streaming_destinations=integration-ready, email_capture/qr_codes/smart_links=live); templates/product_tour_smart_link.html. Access: anonymous — the exact path is in app.py _PUBLIC_EXACT (probed: 200 for a signed-out client, renders "Example smart link" and the fan-intelligence rows).; Campaign status derivation / pre-save auto-conversion — Live. One campaign URL stays alive across release day: the status shown is derived from the release date, not flipped by hand (Archived / Draft / "Pre-save live" / "Released" / "Live"). Files: links_engine.py:75 def effective_status(), :90 is_prerelease(), :95 STATUS_TONES; read by the builder (app.py:4326 ml_edit), the analytics page (app.py:4435), the public page (app.py:2043 smart_link_redirect) and the executive report (app.py:3191). It is also what decides whether /l/<slug>/subscribe writes a presave_notify or an email_marketing consent (app.py:2118-2124) and whether _send_release_emails fires. Access: no gate of its own; follows whichever page calls it.; Street Banker release-readiness score — Live. A 0-100 score with named warnings over destinations, cover art, release date, email capture, consent copy, announcement text and publish state. Files: links_engine.py:101 def calculate_street_banker_score(), :68 _CORE_SERVICES; shown on the builder (app.py:4326 ml_edit, templates/links_builder.html) and the analytics page (app.py:4435, templates/links_analytics.html), and averaged into the Command Center's links_score (command_center.py:335). Referenced only as a filename in the builder entry, never named as a feature. Access: artist tier or higher, own campaign only.; Artist Hub (/@<slug>) — Live. The public link-in-bio page, which carries the account's ACTIVE Fan Club, its live non-archived smart-link campaigns and its upcoming confirmed/advanced shows to an anonymous visitor; besides /club/<slug> it is the only public door to the fan club. Routes: GET /@<slug>. Files: app.py:6821 @app.route("/@<slug>"), handler app.py:6822 def artist_hub(); templates/artist_hub.html; reads store.get_epk_by_slug, store.get_fan_club, mls.list_campaigns, store.list_tour_shows. Access: anonymous — "/@" is in app.py _PUBLIC_PREFIXES; 404 when no EPK slug matches, and the club block is dropped unless club["active"].; Universal quick-link landing page — Live. When an older quick link was created from a pasted track URL, /l/<slug> does NOT plain-redirect: it renders a branded all-platform page from the Odesli metadata cached on the row. The redirector entry lists templates/link_landing.html among its files but describes that path as "a plain redirect for an older quick link". Routes: GET /l/<slug> (fallback branch). Files: app.py:2076-2081 (store.get_db_link -> store.log_click -> if meta and meta["links"] render link_landing.html, else redirect(link["target"])); templates/link_landing.html; ordered_platform_links(); meta written by app.py:11321 links_create via music_apis.odesli_lookup. Access: anonymous ("/l/" is a public prefix).

## Collaboration

44 features: 37 Live, 2 Partial, 2 Stubbed, 3 Dead code.

### Live

**Active Projects tab and tile**

Open briefs of yours that drew applications, closed briefs awaiting a rating, and open briefs you were chosen for.

- Because: active_count is len(projects)+len(to_rate)+len(chosen_for), each built from collab_replies.chosen and collab_ratings; a finished brief you were chosen for is listed separately and deliberately not counted
- Routes: GET /marketplace?tab=projects
- Files: app.py:11409 (to_rate / chosen_all / active_count block); db.py:3248 rated_pairs_by, :3256 list_collab_chosen_for; templates/partials/collab_pipeline.html
- Access: Any signed-in account (own rows only).

**Applications tab**

Every application this account sent, with the brief's current state and when it was sent.

- Because: a single JOIN over collab_replies/collab_requests/users keyed on r.user_id = the viewer; probe returned 200
- Routes: GET /marketplace?tab=applications
- Files: app.py:11409 (the `sent` query); templates/marketplace.html
- Access: Any signed-in account (own applications only).

**Apply to a Brief**

Sends an application (message, contact email, proposal, reference link) to the brief's poster.

- Because: probe POST wrote a collab_replies row and redirected with applied=1; refuses when the brief is closed, missing, your own, the message is empty or the contact has no '@'
- Routes: POST /marketplace/<req_id>/apply
- Files: app.py:11695 marketplace_apply(); db.py:3020 add_collab_reply, db.py:5038 notify; collab_market.py:220 safe_back, :234 with_flag
- Access: Any signed-in account other than the brief's poster; demo logins refused by _demo_not_a_member. Team seat needs the Fans room.

**Board activity stats strip**

Open listings, posts and replies in the last 30 days, and listings matched on the board.

- Because: four COUNT queries over tour_board, board_messages and board_events; each figure is hidden when it is zero rather than printed as 0
- Routes: GET /tour-board (header strip)
- Files: board_store.py:719 stats(); templates/board/index.html:13-17
- Access: Anyone who can open the board.

**Board encoding repair and legacy migrations**

Un-mangles text that arrived as mojibake and backfills structured columns and threads for rows posted before they existed.

- Because: init_board() runs repair_all_text(), migrate_legacy_listings() and migrate_legacy_replies() at app start (board.init, app.py:14505); repair_text is idempotent and migrate_legacy_listings measures expiry from the migration so an old row is not born expired
- Routes: no route; runs at startup, plus the CLI tools/repair_board_encoding.py (--apply, dry run by default)
- Files: board_store.py:42 init_board, :117 repair_text, :150 repair_all_text, :192 migrate_legacy_listings, :217 migrate_legacy_replies; tools/repair_board_encoding.py
- Access: Startup code and a local CLI; no route, no user-facing gate.

**Board Inbox**

Every thread you are in, newest activity first, with your own unread count on each.

- Because: bs.inbox() is one query over board_threads joined to tour_board and users, keyed on poster_id or replier_id; probe returned 200 and bs.unread_total reported 1 for each side
- Routes: GET /tour-board/inbox
- Files: board.py:160 inbox() -> templates/board/inbox.html; board_store.py:595 inbox, :617 unread_total
- Access: Any account past the Pro/Label Tour gate; own threads only.

**Board taxonomy and free-text parsers**

Stable codes for 16 regions and 50+ metros plus genre codes, and conservative parsers for region, date window, genres and draw.

- Because: the vocabularies are reference data, not fake records, and the parsers return None rather than guess; probe confirmed 'Nashville, TN' resolved to metro-nashville and 'draw 200' to draw_min 200
- Routes: no route of its own; used by /tour-board and its API
- Files: board_taxonomy.py:13 REGIONS, :32 METROS, :106 GENRES, :179 parse_region, :246 parse_window, :329 parse_genres, :351 parse_draw, :380 regions_related
- Access: n/a (library). Note: region_distance_km (board_taxonomy.py:370) has no caller in app code - only tests/test_team_up_board.py:74 exercises it.

**Choose an applicant**

The poster marks an application as chosen, which is what makes a rating possible.

- Because: probe POST set collab_replies.chosen=1; the UPDATE is scoped to briefs the caller posted, and unchoosing deletes the poster's rating of that person on that brief (db.py:3157)
- Routes: POST /marketplace/<req_id>/choose/<reply_id>
- Files: app.py:11931 marketplace_choose(); db.py:3157 set_collab_reply_chosen
- Access: The brief's poster only (view checks req['user_id'] == user['id'] and the SQL re-checks); demo logins refused.

**Close / Delete your Brief**

The poster closes a brief so it leaves the board, or deletes it with its applications and ratings.

- Because: probe POST flipped status to 'closed'; delete_collab_request also removes collab_replies and the poster's collab_ratings for that brief (db.py:3004-3018), both scoped by user_id in SQL
- Routes: POST /marketplace/<req_id>/close, POST /marketplace/<req_id>/delete
- Files: app.py:11748 marketplace_close(), app.py:11756 marketplace_delete(); db.py:2998 close_collab_request, :3004 delete_collab_request
- Access: Poster only (enforced by `AND user_id = ?` in SQL, not by a check in the view). Unlike post/apply/save/report/choose/rate, these two carry NO _demo_not_a_member guard as of md5 0499507e; they only act on rows the caller owns. Team seat needs the Fans room.

**Collab Marketplace (Discover)**

One screen of every open collaboration brief from every account, with tiles, filters and recommendations.

- Because: handler queries collab_requests/collab_replies/collab_saves for the signed-in account and renders real rows; probe with the Flask test client returned 200 and the tiles/board reflected rows a second account had just written
- Routes: GET /marketplace (also ?tab=discover|briefs|applications|projects, ?kind/role/genre/loc/budget/q/saved/brief)
- Files: app.py:11409 marketplace() -> templates/marketplace.html; collab_market.py (whole module); db.py:2942-3055 (add/list/get/close/delete collab requests, replies, saves)
- Access: Any signed-in account. plans.required_tier('/marketplace') is None (not in _ARTIST_PATHS/_PRO_PATHS) and plans.path_suite('/marketplace') is None; probed fan/artist/pro/label with SUITE_GATES=on -> all 200. Anonymous is redirected to /login by plan_gate (app.py:11956). Team seat: team_areas.room_for_path('/marketplace') == 'fans', so a seat needs the Fans room ticked. Not owner-only.

**Collaborator public profile**

One listed member's card with their match reasons, their ratings, their open briefs and their trust factors.

- Because: get_listed_collab_profile filters on listed=1 plus not-locked/not-ended/not-demo in SQL; probe returned 200 for a listed member, and requesting your own id redirects to /marketplace/profile rather than 404ing
- Routes: GET /marketplace/people/<member_id>
- Files: app.py:11893 marketplace_person() -> templates/collab_person.html; db.py:3144 get_listed_collab_profile, :3239 list_collab_ratings_for, :3223 collab_rating_summary; trust_score.py:40 calculate
- Access: Any signed-in account. An unlisted, locked, expired or demo member 404s. A demo login sees nobody but itself.

**Collaborator ratings**

One to five stars and a note, once per brief and person, only on a closed brief of yours where you chose them.

- Because: probe POST produced a collab_ratings row and collab_rating_summary returned count 1, mean 5.0, clients 1; can_rate_collab requires a closed brief the rater posted plus a chosen reply from someone other than the rater, and the read side re-checks that basis (_RATING_BASIS, db.py:3217)
- Routes: POST /marketplace/<req_id>/rate/<ratee_id>
- Files: app.py:11948 marketplace_rate(); db.py:3177 can_rate_collab, :3190 add_collab_rating, :3223 collab_rating_summary, :3248 rated_pairs_by; collab_market.py:597 rating_line; templates/partials/collab_rate_form.html
- Access: The brief's poster only, and only after closing it; demo logins refused.

**Collaborators directory**

Every member who opted in, best match first, filterable by role.

- Because: _people_cards reads the same listed-only store call and sorts by match percent; probe returned 200 and showed the other account's name
- Routes: GET /marketplace/people (?role=)
- Files: app.py:11876 marketplace_people(), app.py:11858 _people_cards -> templates/collab_people.html; db.py:3126 list_listed_collab_profiles
- Access: Any signed-in account. A demo login gets an empty list with a message saying members listed themselves for members only.

**Edit a listing**

The poster rewrites the headline, region, window, genres, draw and details.

- Because: probe POST changed the stored title; update_listing returns (False, []) unless the row's user_id matches and the UPDATE is scoped by user_id as well
- Routes: GET/POST /tour-board/<listing_id>/edit
- Files: board.py:275 edit() -> templates/board/edit.html; board_store.py:399 update_listing
- Access: Poster only (404 otherwise), behind the Pro/Label Tour gate; Stage room for a team seat.

**Expiry and one-click renewal**

A listing expires after 60 days; three days out its owner gets one renewal notice with a single-use link.

- Because: bs.expiring_soon() selects open listings inside the window with renew_notice_at empty and the caller marks them so the notice is sent once; probe hit /board-renew/<id>?t=<token> signed out and got the renewed page, and a token cannot resurrect a listing the owner closed or filled (board_store.py:491)
- Routes: GET /board-renew/<listing_id>?t=<token>
- Files: board.py:68 _sweep_renewals(), board.py:326 renew_by_token() -> templates/board/renewed.html; board_store.py:511 expiring_soon, :521 mark_renew_notice, :476 renew; app.py:4851 _PUBLIC_PREFIXES includes '/board-renew/'
- Access: Anonymous is allowed: '/board-renew/' is a public prefix and the single-use token is the authorisation. The in-app POST /tour-board/<id>/renew stays behind the Pro/Label Tour gate.

**Listing lifecycle: close, reopen, mark filled, renew, delete**

The poster closes, reopens, marks a listing filled against a thread, renews it for 60 days or deletes it with its threads.

- Because: probe exercised all five: status went open -> filled (with matched True) -> open, renew reset expires_at, and delete removed the listing, its legacy replies, its threads and their messages; marking filled notifies the chosen replier
- Routes: POST /tour-board/<id>/close, /reopen, /fill, /renew, /delete
- Files: board.py:291 close(), :300 reopen(), :309 fill(), :340 renew(), :349 delete(); board_store.py:464 set_status, :476 renew, :501 delete_listing, :714 event
- Access: Poster only (every statement is scoped by user_id in SQL), behind the Pro/Label Tour gate; Stage room for a team seat.

**Match scoring**

Scores a listed profile against the viewer's open briefs, or against the viewer's own profile when there is no brief.

- Because: match_brief weights role 40 / genre 25 / location 15 / availability 10 / budget 10 and counts only rules the brief states; every reason is carried to the card's 'Why' list, and no role and no genre in common returns None so no % is shown
- Routes: used by GET /marketplace, /marketplace/people, /marketplace/people/<id>
- Files: collab_market.py:517 match_brief, :560 match_self, :451 _score, :468 _location_rule, :497 _budget_rule, :432 _available_for
- Access: Runs for any signed-in viewer; no separate gate.

**Money field parsing**

Reads a typed amount (300, $1,500, 2k) or refuses it with a message instead of keeping its digits.

- Because: read_money returns (None, False) for anything the regex rejects and the post route saves nothing when it does; '150-400' is refused, not read as 150400 (tests/test_collab_profiles.py:578)
- Routes: used by POST /marketplace/post and POST /marketplace/profile
- Files: collab_market.py:284 read_money, :304 parse_money, :315 read_money_pair, :329 money_range, :281 MONEY_PATTERN
- Access: No gate of its own. Note: parse_money (collab_market.py:304) has no caller in app code - only tests use it; read_money/read_money_pair are what the routes call.

**My Briefs tab**

The account's own briefs with applicant counts, state labels and the applicant list.

- Because: reads store.list_own_collab_requests(uid) plus store.list_collab_replies per brief; probe returned 200 with the just-posted brief and its one application
- Routes: GET /marketplace?tab=briefs
- Files: app.py:11409 (own/replies_by_req block); db.py:2990 list_own_collab_requests, :3029 list_collab_replies; templates/marketplace.html
- Access: Any signed-in account (own rows only).

**New Matches tile**

Counts listed profiles scoring 60%+ against one of your open briefs that are new or changed since you last opened Discover.

- Because: compares collab_profiles.updated (microsecond stamps) against the collab_seen row written on each Discover view; the tile is omitted entirely when you have no open brief, so it never shows a zero it did not measure
- Routes: GET /marketplace (tile), written on GET /marketplace?tab=discover
- Files: app.py:11409 (new_matches block); db.py:3268 get_collab_seen, :3279 set_collab_seen, :3275 _now_fine; collab_market.py:265 MATCH_THRESHOLD
- Access: Any signed-in account; the seen stamp is not written while acting through a team seat (`if tab == 'discover' and not session.get('team_as')`).

**One listing page**

A listing with its poster's verified chips and either its reply threads (yours) or your own thread (someone else's).

- Because: reads bs.get_listing and bs.threads_for_listing; probe returned 200 and the reply button, thread list and reply counts came from board_threads/board_messages
- Routes: GET /tour-board/<listing_id>
- Files: board.py:198 listing() -> templates/board/listing.html; board_store.py:416 get_listing, :582 threads_for_listing, :625 reply_counts
- Access: Any account that passes the Pro/Label Tour gate; a 404 only when the listing does not exist.

**Open opportunities table (filters and search)**

Filters the live board by role, genre, deal type, location, budget band, free text and saved-only.

- Because: every filter is applied over rows read from collab_requests; collab_market.location_options() builds the location list only from places live briefs actually state, and budget_filter/location_filter are pure functions over stored columns
- Routes: GET /marketplace?role=&genre=&kind=&loc=&budget=&q=&saved=1#opps
- Files: app.py:11409 (filter block), collab_market.py:642 location_options, :655 location_filter, :666 budget_filter, :217 TABLE_ROWS=100; templates/marketplace.html:209-265
- Access: Same as /marketplace: any signed-in account.

**Outreach Pipeline**

A private pitch tracker: who you pitched, their role, notes and a stage from saved to accepted or passed.

- Because: probe added, re-staged and deleted an entry and each write landed in outreach_items keyed by user_id; the six stages are a fixed vocabulary (db.py:2901) but every row is the member's own, and the page starts empty on purpose
- Routes: GET /tour-board/outreach; POST /network/outreach/add, POST /network/outreach/<item_id>/stage, POST /network/outreach/<item_id>/delete
- Files: board.py:168 outreach() -> templates/board/outreach.html + templates/partials/outreach_pipeline.html; app.py:12062 outreach_add(), :12075 outreach_stage(), :12084 outreach_delete(), :12055 _outreach_back; db.py:2901 OUTREACH_STAGES, :2904 add_outreach, :2916 list_outreach, :2925 set_outreach_stage, :2934 delete_outreach
- Access: The page is behind the Pro/Label Tour suite gate ('/tour-board/outreach' matches the '/tour-board' prefix; probed fan 402, artist 402, pro 200, label 200). The three POST routes live under /network/ and are NOT suite-gated, but every statement is scoped by user_id. Team seat: both the page and /network/outreach/* map to the Stage room (team_areas.EXTRA['stage'] lists '/network/outreach'). Note a cross-gate: the marketplace's 'Network' tab (collab_market.py:76) links to /tour-board/outreach, so a Fan or Artist account clicking it from the fan-open /marketplace meets the 402 upgrade card.

**Post a Brief**

Writes a collaboration brief (role, genre, deal type, budget range, location, closing date) to the shared board.

- Because: probe POST persisted a row in collab_requests with budget_min=500 and city='Atlanta'; a malformed amount is refused with a message and nothing is saved (redirect carries post_error)
- Routes: POST /marketplace/post
- Files: app.py:11662 marketplace_post(); collab_market.py:315 read_money_pair, :276 _MONEY_RE; db.py:2942 add_collab_request; templates/marketplace.html (#post form)
- Access: Any signed-in account, except a seeded demo login: _demo_not_a_member (app.py:11650) bounces demo_accounts.EMAILS with ?demo=member. Team seat needs the Fans room.

**Post a Team-Up listing**

Posts an artist or venue listing with a structured region, date window, genres and draw range.

- Because: probe POST persisted a tour_board row with an expires_at 60 days out and a renew token; a listing with no headline is refused with coaching, and the coaching messages are nudges written back to the session, never blockers
- Routes: POST /tour-board/post (GET redirects to /tour-board?new=1)
- Files: board.py:119 post(); board_store.py:376 add_listing, :309 _clean_fields; board_taxonomy.py parse_region/parse_window/parse_genres/parse_draw
- Access: Same Pro/Label suite gate as /tour-board; Stage room for a team seat. No demo-account guard on this route.

**Profile photo**

Uploads the member's photo, stored as their one EPK photo.

- Because: posts through the shared _store_epk_photo (app.py:3954), which writes the file under UPLOADS_DIR and calls store.save_epk_photo; the card falls back to initials when there is none, never a stock face
- Routes: POST /marketplace/profile/photo
- Files: app.py:11846 marketplace_profile_photo(), app.py:3954 _store_epk_photo; db.py save_epk_photo; templates/collab_profile.html (#photo)
- Access: Any signed-in account, own photo only.

**Recommended briefs**

Up to three open briefs by other members that match a role you applied as or a genre you post in.

- Because: collab_market.recommendations() filters the live board against the viewer's own sent applications and posted genres and returns the stated basis; with no basis the template prints an honest empty state instead of filler
- Routes: GET /marketplace#recs
- Files: collab_market.py:189 recommendations(); app.py:11409 (recs/rec_basis); templates/marketplace.html:141-206
- Access: Any signed-in account.

**Recommended collaborators**

Up to three listed members, best match first, each with the rules that produced its percentage.

- Because: reads store.list_listed_collab_profiles(exclude_user_id=uid) and scores with collab_market.best_match; probe confirmed a second account's opted-in profile appeared with a % and reasons, and unlisted profiles never leave SQL (db.py:3108 _listable_sql)
- Routes: GET /marketplace#recs, GET /marketplace/people
- Files: collab_market.py:579 best_match, :606 person_card; app.py:11409 (listed/scored/row), app.py:11858 _people_cards; db.py:3126 list_listed_collab_profiles; templates/partials/collab_person_card.html
- Access: Any signed-in account; a seeded demo login is handed an empty list (`listed = [] if demo`) and sees the labelled showcase instead.

**Region typeahead API**

Returns up to 25 matching regions and metros for the board's region pickers.

- Because: returns rows built from board_taxonomy.region_options() plus a parse_region() best guess; probe GET /tour-board/api/regions?q=nash returned 200, and it answers 401 JSON without a session
- Routes: GET /tour-board/api/regions?q=
- Files: board.py:179 api_regions(); board_taxonomy.py:160 region_options, :179 parse_region, :141 region_label; static/js/board.js
- Access: Signed in only (401 JSON otherwise), and behind the Pro/Label Tour gate like the rest of /tour-board.

**Reply in Street Banker (threads)**

Starts or continues an in-app message thread on a listing; no email address is shown to anyone.

- Because: probe reply created a board_threads row and a board_messages row and redirected to the thread; the second message from the poster landed in the same thread and unread counters moved on both sides
- Routes: POST /tour-board/<listing_id>/reply, GET/POST /tour-board/thread/<thread_id>
- Files: board.py:222 reply(), board.py:249 thread() -> templates/board/thread.html; board_store.py:528 start_or_get_thread, :540 add_message, :557 get_thread, :566 thread_messages, :576 mark_read
- Access: Either side of the thread only (`user['id'] not in (poster_id, replier_id)` -> 404); replying to your own listing or a non-open one is refused. Behind the Pro/Label Tour gate. A team seat reading the artist's thread does not mark it read (`if not session.get('team_as')`).

**Report a post**

Flags someone else's brief; the first report per member notifies every owner account.

- Because: probe POST wrote the app_kv key collab_report:<req>:<user> and a repeat press is ignored; the notify loop walks store.list_users() and files under kind 'report' for addresses _is_owner_email accepts
- Routes: POST /marketplace/<req_id>/report
- Files: app.py:11767 marketplace_report(), app.py:11763 _collab_report_key, app.py:107 _is_owner_email; db.py:2033 get_kv / :2041 set_kv, :5038 notify; templates/marketplace.html:120-129
- Access: Any signed-in account except the post's own author; demo logins refused. The notification lands only on owner accounts (OWNER_EMAILS or a hashed address in _OWNER_EMAIL_HASHES).

**Save a Brief**

Toggles a brief onto the account's saved list, which the Saved filter reads.

- Because: probe POST produced a collab_saves row and store.list_collab_saves returned it; the redirect target is validated by safe_back so only a /marketplace path is accepted
- Routes: POST /marketplace/<req_id>/save
- Files: app.py:11734 marketplace_save(); db.py:3038 toggle_collab_save, :3050 list_collab_saves; collab_market.py:220 safe_back
- Access: Any signed-in account; demo logins refused. Team seat needs the Fans room.

**Saved searches (watches)**

Saves a board search and alerts you by notification and email when a matching listing is posted.

- Because: probe POST wrote a board_watches row with region_code metro-nashville and label 'artists - Nashville, TN - Hip-Hop'; bs.matching_watches() re-checks kind, region relationship, genre overlap and window on each new listing and board._alert_watchers notifies and touches each hit
- Routes: POST /tour-board/watch, POST /tour-board/watch/<watch_id>/delete
- Files: board.py:359 watch(), :373 watch_delete(), :143 _alert_watchers; board_store.py:646 add_watch, :655 list_watches, :667 watch_label, :680 delete_watch, :685 matching_watches, :707 touch_watch
- Access: Any account past the Pro/Label Tour gate; own watches only (delete is scoped by user_id).

**Team-Up Board**

Artists seeking tour partners and venues seeking acts, filtered by who, region, genre and date window.

- Because: board.index reads bs.list_listings() and bs.list_own() from tour_board and renders real rows; probe posted a listing and it came back with region_code metro-nashville, genres ['hiphop'] and draw_min 200; the stats strip is four COUNT queries (bs.stats)
- Routes: GET /tour-board (?kind, ?region, ?genre, ?from, ?to, ?sort)
- Files: board.py:89 index() -> templates/board/index.html, templates/board/_macros.html; board_store.py:423 list_listings, :457 list_own, :719 stats; db.py:267 tour_board
- Access: Pro or Label when plans.gates_on() (RENDER set, or SUITE_GATES=on): '/tour-board' is in plans._TOUR_PATHS so path_suite returns 'tour' and SUITE_ACCESS['tour']=='pro'. Probed with SUITE_GATES=on: fan 402, artist 402, pro 200, label 200. Owner accounts bypass (_is_owner_email in plan_gate). Team seat needs the Stage room (team_areas.room_for_path -> 'stage'). Anonymous redirected to /login.

**Verified chips**

Facts drawn from the poster's own TOUR records (shows played, home market, confirmed dates ahead) shown beside their name.

- Because: bs.verified_chips reads tour_shows and epk_profiles for that user and labels each chip with its source; a poster with no shows gets an empty list (probe returned {'chips': [], 'slug': ''}) rather than an invented badge, and self-reported draw is rendered separately and marked as such
- Routes: shown on GET /tour-board and GET /tour-board/<id>
- Files: board_store.py:731 verified_chips; templates/board/_macros.html:30 chips(), :47 (slug -> /@<slug>)
- Access: Displayed to anyone who can open the board.

**Your collaborator profile**

The member's own opt-in profile: roles, genres, location, rate, availability, credits, links, bio.

- Because: probe POST persisted every field to collab_profiles including rate_max=2000 parsed from '2k'; nothing is listed until `listed` is ticked, and listing with no role is refused with a message
- Routes: GET/POST /marketplace/profile
- Files: app.py:11808 marketplace_profile(), app.py:11799 _own_card -> templates/collab_profile.html; collab_market.py:370 clean_profile; db.py:3077 get_collab_profile, :3085 save_collab_profile
- Access: Any signed-in account, own record only. A seeded demo login may fill every field but `listed` is forced to 0 with an explanation (app.py:11808 `if demo and fields['listed']`). Team seat needs the Fans room.

**Your trust signals (on the marketplace)**

The account's own Trust Score factors, the number shown beside its name on every brief it posts.

- Because: trust_score.calculate reads the account's own catalog, deals, statements, fans, campaigns, sync packs and EPK; a factor that was never measured scores 0 and is labelled unmeasured, and collab_market.trust_label prints 'Trust not scored' rather than 'Trust 0' when nothing is on record
- Routes: GET /marketplace (trust card), GET /marketplace/people/<id>
- Files: collab_market.py:141 trust_label, :53 TRUST_ICONS; trust_score.py:40 calculate; app.py:11409 (_with_trust, trust_rows); templates/marketplace.html:283-304
- Access: Any signed-in account; a poster's score is computed only for rows on screen.

### Partial

**Network (parked directory)**

An industry directory with playlists, shows and moments, carrying the real outreach tracker at the bottom.

- Because: the directory, playlists, shows and moments come from network_config._PROFILES/_PLAYLISTS - hard-coded people with invented follower counts - and connections, pitches, submissions and claims live in the session, not a table; the Outreach Pipeline on the same page is the real outreach_items rows for the account. docs/PARKED_PAGES.md:17 names it parked
- Routes: GET /network (?tab=directory|playlists|shows|moments|my)
- Files: app.py:12041 network() -> templates/network.html; network_config.py:32 _PROFILES, :277 get_network_data; app.py:11(_network_state, session-backed); db.py:2916 list_outreach
- Access: Any signed-in account - no tier gate and no suite gate (required_tier None, path_suite None; probed 200 on fan/artist/pro/label). It is in no room, so a team seat sees the tracker only if it has the Stage room (app.py:12041 checks team_areas.allows(seat['areas'], '/tour-board/outreach') and blanks the rows otherwise). Not in any nav: grep of hubs.py, hub_defs.py and rooms.py finds no 'network' key.

**Project Pipeline**

Six stages for one of your briefs, three tracked here and three that say they are not.

- Because: Brief / Applications / Closing carry real dates and counts from the brief and its replies; Agreement, Production and Delivery are hard-coded steps with state 'todo' and the notes 'In the Deal Room' and 'Not tracked here' (collab_market.py:170-182) - the board records nothing for them
- Routes: GET /marketplace (Project Pipeline card), GET /marketplace?tab=projects
- Files: collab_market.py:159 pipeline(); app.py:11409 (projects/latest); templates/marketplace.html:270-279, templates/partials/collab_pipeline.html
- Access: Any signed-in account (own briefs only).

### Stubbed

**Demo showcase collaborators**

Three invented example collaborators shown to the seeded demo login when it has nothing real to show.

- Because: collab_market.SHOWCASE is a hard-coded list of three dicts (Maya Chen, Darius Cole, Nia Brooks) with fixed match percentages and rates; it is passed only when _session_is_demo() and there are no recs and no rec_people, and the card is labelled 'Showcase ... They are not members'
- Routes: GET /marketplace (Recommended card, demo session only)
- Files: collab_market.py:81 SHOWCASE; app.py:11409 (showcase= kwarg); templates/marketplace.html:148-177; demo_accounts.py EMAILS
- Access: Only the four seeded addresses in demo_accounts.ACCOUNTS. tests/test_collab_marketplace.py:155 locks that a real account never sees it.

**Network profile / playlist / moment pages and their actions**

A sample contact's page with connect, pitch and booking-enquiry buttons, plus playlist submission and moment claiming.

- Because: every target is an entry in network_config's hard-coded lists and every action writes to the Flask session, not a table - app.py's own comment calls the people 'invented' and says the state is the session 'because the people being connected to are invented'
- Routes: GET /network/<profile_id>, POST /network/<profile_id>/connect, /pitch, /enquire; GET /network/playlist/<id>, POST /network/playlist/<id>/submit; GET /network/moment/<id>, POST /network/moment/<id>/claim
- Files: app.py:12091-12179; network_config.py (_PROFILES, _PLAYLISTS, _SHOWS, _MOMENTS); templates/network_profile.html, network_playlist.html, network_moment.html
- Access: Any signed-in account. Reachable in-app only from templates/discover.html (which links /network/<artist_id>) and from inside the network family itself; no nav entry. As of 2026-09-21 those Discover links are drawn only for a showcase session, so a real account now has no in-app route to these pages at all; the addresses still answer if typed.

### Dead code

**db.list_collab_requests**

An unfiltered read of open collaboration briefs with the poster's name.

- Because: grepped every .py and .html for list_collab_requests - the only hits are the definition at db.py:2961 and a passing mention in a test docstring (tests/test_collab_marketplace.py:40). The /marketplace view builds its own SQL inline instead, precisely so the 200-row cap this function carries cannot truncate the board
- Routes: none
- Files: db.py:2961 list_collab_requests
- Access: n/a - unreachable.

**Legacy board store helpers in db.py**

An older, pre-blueprint set of tour_board read/write helpers superseded by board_store.py.

- Because: grepped every .py and .html for list_board_listings, get_board_listing, close_board_listing, delete_board_listing, list_own_board_listings, add_board_reply and db.list_board_replies - no caller outside db.py and no test (the tests call bs.list_board_replies from board_store). db.add_board_listing is the one exception: it is still used by tests/test_team_up_board.py to seed legacy rows
- Routes: none
- Files: db.py:3332 list_board_listings, :3346 get_board_listing, :3355 close_board_listing, :3362 delete_board_listing, :3372 list_own_board_listings, :3380 add_board_reply, :3390 list_board_replies
- Access: n/a - unreachable.

**Listing view's non-open guard**

An intended check that would hide a closed or expired listing from people with no thread on it.

- Because: board.py:207 reads `if A and B and not bs.get_thread_for(...) if hasattr(bs, 'get_thread_for') else False:` - grep for get_thread_for across every .py finds only this line, so hasattr is False, the whole conditional expression evaluates to False, and the body is `pass` in any case. A closed, filled or expired listing is therefore visible to anyone signed in who has its URL
- Routes: GET /tour-board/<listing_id>
- Files: board.py:207-208; board_store.py has no get_thread_for (whole file read)
- Access: n/a - the branch never runs.

> Noted by the reviewer as not yet written up in this area: Legacy "Feature Marketplace" in community_config.py — DEAD CODE the inspector did not list at all. community_config.py:20-68 holds a seeded board of three invented requests (_seed_requests: Nova Reign / Kilo Byte / Lila Rose), plus post_request(), get_marketplace_data(), reset_marketplace_state(), DEAL_TONE and DEAL_TYPES. app.py:205-206 still imports get_marketplace_data, but grep across every .py, .html and .js finds no call site, no route and no template reading `summary.open_requests` or `deal_tone`. It predates collab_market.py and is unreachable.; Fans room "Collab" tile — a live count of open briefs outside /marketplace. app.py:4676-4681 runs its own COUNT over collab_requests (status='open' and closing date not passed) and passes it as open_briefs to fan_room.build; fan_room.py:217 turns it into the tile status ("N open briefs", green only when non-zero) and fan_room.py:48 labels the card "Collab / Artists, creators & brands". Route GET /room/fans, template room_fans.html. This is the only read of the collab tables from outside the marketplace family.; Prefilled Team-Up post form (deep link) — board.py:59 _prefill() reads ?new/kind/title/region/from/to/genre/details, runs the region through tx.parse_region, and opens the post <details> already filled (templates/board/index.html:27 `{% if prefill %}open data-open="1"{% endif %}`); GET /tour-board/post (board.py:124-129) exists only to redirect old bookmarks to /tour-board?new=1 carrying the query string. Its one in-app producer is templates/tour/calendar.html:48, "Post this open date to the Team-Up Board, prefilled".; board_store.list_board_replies (board_store.py:636) — a second piece of dead code, separate from the db.py family the inspector listed. It is a compat shim reading board_messages joined to board_threads; grep finds callers only in tests/test_app.py:3988, :4009 and tests/test_team_up_board.py:172. No route, no template, no app module calls it.; Outbound email for this area (email_provider / Resend) — three send sites with no entry: app.py:11719-11729 emails the brief's poster when an application arrives, with reply_to set to the applicant's typed contact; board.py:236-245 emails the listing's poster on a first reply, with reply_to set to the replier's account email; board.py:148-157 emails a watcher when a matching listing is posted. Each is wrapped so a mail failure never fails the write, and each has an in-app notification as the fallback. Note this qualifies the Threads entry's "no email address is shown to anyone": the in-app board hides it, but the notification email hands the poster's mail client the replier's address as Reply-To.; Start-over and account-delete rules for this area — db.py RESET_EXTRA_KEYS names ('tour_board_replies','from_user_id'), ('board_threads','poster_id') and ('board_messages','from_user_id') so board rows the generic user_id sweep would miss are cleared; db.py DELETE_ONLY_KEYS names ('collab_ratings','ratee_id'), which is what stops a rated member wiping other people's ratings of them with "Start over" while keeping the login. This is the write side of the _RATING_BASIS rule the ratings entry only mentions on the read side.; The single-brief focus panel, /marketplace?brief=<id>#brief (templates/marketplace.html:85-133, app.py focus/focus_reported block) — the brief detail card that actually carries the Save, Apply and Report forms, the terms/budget/location/details body, the reference-track link and the "Reported. The Street Banker team will look at it." confirmation. Every board row, recommendation and the owner's report notification link here; the inspector lists ?brief only as a query parameter of Discover and attributes the forms to the routes they post to.; Navigation and Command Center registration — hubs.py:70 ("tour-board", /tour-board, "Team-Up Board") and hubs.py:113 ("marketplace", /marketplace, "Collab Marketplace"), both also in the hubs.py:168/175 groups; rooms.py:25 puts "marketplace" in the Fans room and rooms.py:40 puts "tour-board" in the Stage room (which is what makes team_areas.room_for_path resolve them to 'fans' and 'stage'); command_center.py:122 lists /tour-board with status "live"; templates/lights.html:20 carries a rail button to /tour-board.; Progressive-enhancement scripts — static/js/collab-market.js (12 lines: the filter <select>s submit on change and the no-JavaScript "Filter" button is hidden) and static/js/board.js (58 lines: region typeahead against /tour-board/api/regions, genre chips, auto-opening the post form when ?new=1). Both are additive; every filter and form works server-side without them, which is the reason the API entry exists at all.

## Tour and live

81 features: 68 Live, 5 Partial, 3 Stubbed, 5 Dead code.

### Live

**Advance checklist**

The per-show advance items by category with status, value, owner and due date, set one at a time or in bulk.

- Because: tour_os.py:2318/2336 call ts.ensure_advance_items and ts.set_advance_item against tour_advance (tour_store.py:320); the item vocabulary is a fixed template (ADVANCE_CATEGORIES) but every value is the account's own.
- Routes: POST .../shows/<show_id>/advance/<item_key>; POST .../shows/<show_id>/advance-bulk
- Files: tour_os.py:2318 advance_set(), :2336 advance_bulk(); tour_store.py:56 ADVANCE_CATEGORIES; templates/tour/show/_advance.html
- Access: require_tour("advance", "edit").

**Ask Tour**

Answers plain questions about times, hotels, travel, guests, money and what changed from the rows the asker may see.

- Because: tour_engine.ask() (tour_engine.py:445) is rule-based with no model behind it — the module docstring says so and there is no provider call — and _ask_context (tour_os.py:4174) passes only permission-filtered rows, so it answers from data or says the row is not entered.
- Routes: GET and POST /tours/<tour_id>/ask
- Files: tour_os.py:4204 ask(), :4174 _ask_context(); tour_engine.py:445 ask(); templates/tour/ask.html
- Access: require_tour("view"); money questions and examples appear only with financials.

**Calendar and day rows**

A month grid of the tour's days, with add and edit for non-show days (off, travel, press, festival).

- Because: tour_os.py:1524 builds cells from ts.list_days and scores the month's shows; day_add/day_edit write tour_days or create a show, both logged.
- Routes: GET /tours/<tour_id>/calendar; POST /tours/<tour_id>/days/add; POST /tours/<tour_id>/days/<day_id>/edit
- Files: tour_os.py:1524 calendar(), :1571 day_add(), :1593 day_edit(), _calendar_month :1491; templates/tour/calendar.html, _calendar_grid.html
- Access: view to read; require_tour("edit", "schedule") to add or edit a day. A day carrying a show cannot be deleted here (tour_os.py:1598).

**Content plan**

A per-date shot list with assignee, due time, status and an optional uploaded file.

- Because: tour_os.py:3777 calls ts.ensure_content_plan, which seeds rows from the fixed CONTENT_DEFAULTS list (tour_store.py:121) into tour_content for that account; everything after that — assignee, status, file — is the account's own and persists.
- Routes: GET /tours/<tour_id>/content; POST .../content/<content_id>; POST .../shows/<show_id>/content/bulk
- Files: tour_os.py:3777 content(), :3793 content_set(), :3807 content_bulk(); tour_store.py:595 tour_content; templates/tour/content.html, show/_content.html
- Access: require_tour("content"); attaching a file also needs the files scope (tour_os.py:3796).

**Crew on this date and call times**

Ticks who is on one date and stores a call time per person for it.

- Because: tour_os.py:2096 writes tour_people.shows and tour_show_calls via ts.set_show_calls, and refuses an untick that would empty a list (which would silently mean every date).
- Routes: POST /tours/<tour_id>/shows/<show_id>/crew
- Files: tour_os.py:2096 show_crew(); tour_store.py:2906 tour_show_calls; templates/tour/show/_crew.html
- Access: require_tour("edit").

**Date page (day of show)**

One date as one page: event header, then one grid of every feature the show can carry, folded when on and a + row when not.

- Because: tour_os.py:1669 show() and :1842 _date_page() build the grid from real rows (_date_rows :1057, _has_data :1092) and render tour/show.html plus templates/tour/show/*; probed 200.
- Routes: GET /tours/<tour_id>/shows/<show_id> (tab= deep links); POST .../sections; POST .../ext; POST .../notes; POST .../crew; POST .../delete
- Files: tour_os.py:1669 show(), :1842 _date_page(), :1996 show_sections(), :2054 show_ext(), :2086 show_notes(), :2096 show_crew(), :2144 show_delete(); templates/tour/show.html + templates/tour/show/
- Access: require_tour("view"); each section re-checks SECTION_VIEW_SCOPE (tour_os.py:143) so money sections need financials and guests need guests. edit for notes and crew; admin for delete, which also demands the venue name typed back.

**Exports (calendar, itinerary, CSVs, day sheet)**

The run as an .ics feed, a printable itinerary, CSVs for the itinerary, personnel, travel and money, and a printable day sheet per date.

- Because: each route builds from the viewer's own filtered rows and returns real bytes; probed all seven and got 200 with non-empty bodies.
- Routes: GET /tours/<tour_id>/exports; /tours/<tour_id>/calendar.ics; /tours/<tour_id>/itinerary; /tours/<tour_id>/itinerary.csv; /tours/<tour_id>/people.csv; /tours/<tour_id>/travel.csv; /tours/<tour_id>/money.csv; /tours/<tour_id>/shows/<show_id>/day-sheet
- Files: tour_os.py:4490 exports(), :4498 calendar_ics(), :4507 itinerary_csv(), :4522 itinerary_print(), :4541 people_csv(), :4550 travel_csv(), :4579 day_sheet(), _day_sheet_data :4585; tour_engine.py:1226 csv_text(), :1235 ics_text(); templates/tour/exports.html, print_itinerary.html, print_day_sheet.html
- Access: view for the ics, itinerary and day sheet; people for people.csv; travel for travel.csv; financials for money.csv.

**Guest list**

Guest requests per date against an allocation, with approve/deny, credentials, check-in and a CSV for the door.

- Because: tour_os.py:3211/3226/3252 write tour_guests and ts.guest_summary counts against the show's allocation; an approval over the remaining allocation is downgraded to pending rather than silently over-approved (tour_os.py:3244).
- Routes: GET /tours/<tour_id>/guests; POST .../shows/<show_id>/guests/add; POST .../shows/<show_id>/guests/<guest_id>; GET .../shows/<show_id>/guests.csv
- Files: tour_os.py:3211 guests_all(), :3226 guest_add(), :3252 guest_update(), :3277 guests_csv(); templates/tour/guests.html, show/_guests.html
- Access: require_tour("guests") throughout. The guests scope alone may set the allocation and cutoff via .../ext (tour_os.py:2064).

**Hotels and rooming**

Lodging per date with rooms assigned to people, and a printable rooming list.

- Because: tour_os.py:2755/2774/2785/2803 write tour_lodging and tour_rooms; :4564 prints or exports the room list as CSV; private rooms and payment fields are redacted (_redact_lodging :433, _redact_rooms :425).
- Routes: GET /tours/<tour_id>/hotels; POST .../hotels/add; POST .../hotels/<lodging_id>/edit; POST .../hotels/<lodging_id>/rooms; GET .../hotels/<lodging_id>/rooming
- Files: tour_os.py:2755 hotels(), :2774 hotel_add(), :2785 hotel_edit(), :2803 rooms(), :4564 rooming_print(); templates/tour/hotels.html, print_rooming.html
- Access: view to read (redacted); require_tour("hotel") to write and to print the rooming list.

**Import dates**

Imports a deal sheet, CSV or ICS as shows and days, with a preview, duplicate detection and fill-what-is-missing on a re-sent sheet.

- Because: tour_os.py:4396 parses with tour_engine.parse_csv_rows / parse_ics / parse_pasted, dedupes against existing rows, and on confirm writes real shows, days, ext fields and statuses; each run is recorded in tour_imports.
- Routes: GET and POST /tours/<tour_id>/import
- Files: tour_os.py:4396 import_dates(), _fill_existing_show :4305, _import_ext :4337, _import_status :4371; tour_engine.py:881/938/1003/1112; templates/tour/import.html
- Access: require_tour("edit").

**Join a tour by invite**

Attaches whoever opens a crew invite token to that tour and links their person record by email.

- Because: tour_os.py:1386 join() calls ts.accept_invite, links the tour_people row and notifies the owner; the token comes from tour_members.invite_token written by team_invite.
- Routes: GET /tours/join/<token>
- Files: tour_os.py:1386 join(); templates/tour/join.html; tour_store.get_invite / accept_invite / link_member_person
- Access: Signed in as the person themselves, any plan (a crew member on a free account keeps their day sheet). Refused inside a team seat: app.py:5045 _TEAM_BLOCKED lists /tours/join and tour_os.py:1393 aborts 403.

**Light rigs**

Saved rig layouts — bar count, channel mode, positions, rotations and DMX addresses — optionally bound to a venue.

- Because: app.py:7777 clamps and whitelists every field before storing (bars 2-10, DMX 1-512, at most ten entries per map) and writes light_rigs; :7770 and :7837 list and delete for the caller only.
- Routes: GET /lights/rigs; POST /lights/rigs/save; POST /lights/rigs/<rig_id>/delete
- Files: app.py:7770 lights_rigs(), :7777 lights_rigs_save(), :7837 lights_rigs_delete(); lights_store.py:39 light_rigs, venue_key()
- Access: Same as Light Studio.

**Light setlists**

An ordered run of light shows with a gap colour, for playing a set end to end.

- Because: app.py:7743 writes light_setlists and light_setlist_items and lights_store drops items pointing at another account's show; probed GET /lights/setlists 200.
- Routes: GET /lights/setlists; GET /lights/setlists/<setlist_id>; POST /lights/setlists/save; POST /lights/setlists/<setlist_id>/delete
- Files: app.py:7726 lights_setlists(), :7733 lights_setlist_get(), :7743 lights_setlist_save(), :7758 lights_setlist_delete(); lights_store.py:64/:73
- Access: Same as Light Studio.

**Light show attached to a track**

Binds a light show to a catalog track so it travels with the song.

- Because: app.py:7697 calls lights_store.attach_to_track after the track is confirmed to be the caller's, and :7714 reads it back; the Light Studio page loads tracks_with_shows on render.
- Routes: POST /lights/track/<track_id>/attach; GET /lights/track/<track_id>/show
- Files: app.py:7697 lights_track_attach(), :7714 lights_track_show(); lights_store.attach_to_track / show_on_track / tracks_with_shows
- Access: Same as Light Studio; only the caller's own tracks.

**Light show library and versions**

Named shows saved per account, each explicit save taking a version snapshot that can be restored.

- Because: app.py:7400 writes light_show_library and, unless autosave, a light_show_versions row; track and tour-date links are validated against the caller's own rows and dropped otherwise (:7409-7414); restore and delete answer against the caller's id only.
- Routes: GET /lights/library; POST /lights/library/save; GET /lights/library/<show_id>; GET /lights/library/<show_id>/versions; POST /lights/library/<show_id>/restore; POST /lights/library/<show_id>/delete
- Files: app.py:7393 lights_library(), :7400 lights_library_save(), :7423 lights_library_get(), :7433 lights_library_versions(), :7442 lights_library_restore(), :7453 lights_library_delete(); lights_store.py:21 light_show_library, :31 light_show_versions
- Access: Same as Light Studio; every query is scoped to the signed-in account's user_id.

**Light Studio**

Programs a light show against a track — cues, looks, rig layout and DMX patch — and sends it out over ENTTEC USB, Art-Net or sACN.

- Because: app.py:7351 renders templates/lights.html with the account's own library, rigs, setlists and tour dates; static/js/lights-engine.js frames real DMX, Art-Net and sACN packets (:262, :315, :338) and templates/lights.html:150 downloads static/tools/lx-bridge.py, the local UDP forwarder the browser cannot be; probed GET /lights 200.
- Routes: GET /lights; POST /lights/save
- Files: app.py:7351 lights(), :7378 lights_save(); static/js/lights-engine.js, static/js/lights.js; static/tools/lx-bridge.py; db.py:187 light_shows (the working copy); templates/lights.html
- Access: Signed in; required_tier("/lights") is artist, and plans._TOUR_PATHS puts it behind the Tour suite (Pro) wherever plans.gates_on(). Team seat: the Stage room.

**Light Studio phone remote**

A second operator drives looks and blackout from a phone by scanning a QR; the laptop drains the button presses.

- Because: app.py:7628 mints a code into light_remotes, :7671 pushes real commands into light_remote_cmds, :7645 drains them for the owner, and :7679 draws a QR with segno for a live code of that account only.
- Routes: POST /lights/remote/start; POST /lights/remote/end; GET /lights/remote/poll; GET /lights/remote/<code>; POST /lights/remote/<code>/cmd; GET /lights/remote/<code>/qr.svg
- Files: app.py:7628 lights_remote_start(), :7637 lights_remote_end(), :7645 lights_remote_poll(), :7658 lights_remote_page(), :7671 lights_remote_cmd(), :7679 lights_remote_qr(), _LIGHT_REMOTE_LOOKS :7706; lights_store.py:48 light_remotes, :55 light_remote_cmds; templates/lights_remote.html
- Access: The phone page and its cmd endpoint are anonymous (app.py:4828 lists /lights/remote/ public); start, end, poll and the QR need the signed-in account. A team seat gets an empty queue and no code (app.py:7652).

**Live — manifest and Performance Mode**

Hands the browser the whole set in one document and opens the dark, chrome-free stage screen that plays it.

- Because: live.py:363 returns live_store.set_manifest as JSON and :376 renders templates/live/perform.html outside the app shell; the scheduling, MIDI and offline cache run in static/js/livelab.js (290 KB, present in the repo) because Web Audio timing cannot be done server-side.
- Routes: GET /live/<set_id>/manifest.json; GET /live/<set_id>/perform
- Files: live.py:363 live_manifest(), :376 live_perform(); live_store.set_manifest(); static/js/livelab.js; templates/live/perform.html
- Access: Same as Live sets.

**Live — MIDI mappings**

Maps a physical control to a scene or transport target, refusing an unknown target and a duplicate control.

- Because: live.py:327 checks live_store.find_duplicate before writing live_midi_maps and the targets come from live_store.MIDI_TARGETS; the docstring states this is the server half of rules the browser's Learn already enforces.
- Routes: POST /live/<set_id>/midi; POST /live/midi/<mapping_id>/delete
- Files: live.py:327 live_add_mapping(), :353 live_delete_mapping(); live_store.py:141 live_midi_maps, MIDI_TARGETS
- Access: Same as Live sets.

**Live — scenes and stems**

Scenes with bar counts, follow actions and launch quantisation, holding stems pointed at Vault files with gain, pan, mute, solo and output bus.

- Because: live.py:221/247/299 write live_scenes and live_stems; a stem is a pointer to an existing vault_files row, never a copy (live.py:246), and :270 re-checks ownership on every byte served rather than minting a durable URL.
- Routes: POST /live/<set_id>/scene; POST /live/<set_id>/scene/<scene_id>/delete; POST /live/<set_id>/scene/<scene_id>/stem; GET /live/stem/<stem_id>; POST /live/stem/<stem_id>/set; POST /live/stem/<stem_id>/delete
- Files: live.py:221 live_add_scene(), :236 live_delete_scene(), :247 live_add_stem(), :270 live_stem(), :299 live_set_stem(), :317 live_delete_stem(); live_store.py:99 live_scenes, :120 live_stems; blob_store.py
- Access: Same as Live sets; every store call is scoped to partner key plus user id.

**Live — sets**

A stage rig's set: name, venue, tempo, time signature and click, with archive and restore.

- Because: live.py:116/130/179/197 read and write live_sets scoped by partner key and user id; probed GET /live 200. Note the code and a comment disagree: hubs.py:452 says "LIVE_LAB_ENABLED is off by default and every /live route 404s", but live.enabled() (live.py:54) returns True unless LIVE_LAB_ENABLED is explicitly 0/false/no/off — the code wins, Live is on by default.
- Routes: GET /live; POST /live/new; GET /live/<set_id>; POST /live/<set_id>/settings; POST /live/<set_id>/archive
- Files: live.py:116 live_home(), :130 live_new(), :159 live_set(), :179 live_settings(), :197 live_archive(), :54 enabled(); live_store.py:80 live_sets; templates/live/home.html, set.html
- Access: Signed in; required_tier("/live") is artist and plans._TOUR_PATHS puts it behind the Tour suite (Pro) wherever plans.gates_on(). live.enabled() gates every route with a 404 when LIVE_LAB_ENABLED is off. Team seat: the Stage room.

**Marketing and tickets**

Per-date announce/presale/onsale plan, ticket link and the sold-against-capacity figure with where the number came from.

- Because: tour_os.py:3737/3753 read and write tour_show_ext.marketing; _ticket_progress :2028 will not present a typed count as a measured one and flips ticket_source to "typed" the moment somebody edits the number by hand (:3771).
- Routes: GET /tours/<tour_id>/marketing; POST .../shows/<show_id>/marketing
- Files: tour_os.py:3737 marketing(), :3753 show_marketing(), :2028 _ticket_progress(); templates/tour/marketing.html, show/_marketing.html
- Access: require_tour("marketing").

**Merch counts**

Products for the run and per-date opening/closing counts with venue cut, taxes, fees and settled flag.

- Because: tour_os.py:3670/3702/3709 write tour_merch_products and tour_merch_counts and derive sold and gross when only one side is entered; the total is written back to the show's merch_gross only for a viewer with financials.
- Routes: GET /tours/<tour_id>/merch; POST .../merch/products/add; POST .../shows/<show_id>/merch
- Files: tour_os.py:3670 merch(), :3702 product_add(), :3709 merch_counts(); templates/tour/merch.html, show/_merch.html; tour_store.py:567/:578
- Access: require_tour("merch").

**My Day**

One person's day on the run: their times, their travel, their hotel and the next thing that happens.

- Because: tour_os.py:1461 filters the real schedule/travel/lodging rows through tour_engine.my_day and personal(); probed 200.
- Routes: GET /tours/<tour_id>/my-day
- Files: tour_os.py:1461 my_day(); tour_engine.py:379 my_day(), :349 personal(); templates/tour/my_day.html
- Access: require_tour("view"); rows are filtered by tour_engine.visible_to against the viewer's scopes and person record.

**New tour / one-off show**

Creates a tour, or a one-date tour whose single show is made immediately.

- Because: tour_os.py:1317 create() calls ts.create_tour and store.add_tour_show, logs the change and redirects; test client created a tour and a show.
- Routes: POST /tours/new
- Files: tour_os.py:1317 create(); tour_store.create_tour / attach_show; db.add_tour_show
- Access: Signed in; refuses below tier with upgrade.html 402 (artist, or Pro when plans.gates_on()). A read-only team seat is refused 403 (tour_os.py:1322).

**Openers and set times (the bill)**

Pastes the running order as one box, saves every act's line-check and set times in one submit, and can push them onto the day sheet.

- Because: tour_os.py:2233/2252/2287 write tour_lineup (tour_store.py:2781) and ts.lineup_schedule_items skips acts with no time rather than inventing one.
- Routes: POST .../shows/<show_id>/lineup; POST .../lineup/times; POST .../lineup/schedule
- Files: tour_os.py:2233 lineup_set(), :2252 lineup_times(), :2287 lineup_to_schedule(); templates/tour/show/_lineup.html; tour_store.set_lineup / list_lineup
- Access: require_tour("schedule", "edit").

**Outreach tracker**

A private pitch tracker of contacts and stages, shown under the Team-Up Board.

- Because: board.py:169 renders store.list_outreach with store.OUTREACH_STAGES, and the three POST routes in app.py write outreach_items; probed GET /tour-board/outreach 200.
- Routes: GET /tour-board/outreach; POST /network/outreach/add; POST /network/outreach/<item_id>/stage; POST /network/outreach/<item_id>/delete
- Files: board.py:169 outreach(); app.py:12061 outreach_add(), :12074 outreach_stage(), :12083 outreach_delete(); db.py:229 outreach_items; templates/board/outreach.html
- Access: Signed in and the owner of the rows; team_areas.EXTRA puts /network/outreach in the Stage room so a seat's forms follow the board.

**Passport on a date (advance attachment)**

Attaches one published passport version to a date, or detaches it while the advance is still open.

- Because: tour_os.py:1820 show_stage() calls advance_store.attach/detach, which stores the version id (not the passport pointer) so publishing later leaves the date where it was (advance_store.py:106), and refuses a passport with nothing published.
- Routes: POST /tours/<tour_id>/shows/<show_id>/stage
- Files: tour_os.py:1820 show_stage(), _stage_ctx :1791; advance_store.py:106 attach(), :156 detach(), :183 snapshot_for(), :198 newer_version_available(); advance_store.py:58 show_passports
- Access: require_tour("edit", "production").

**People (crew directory)**

Everyone on the run by category with role, company, phone and emergency contact, optionally pulled from the Press Desk media list.

- Because: tour_os.py:3154/3177 read and write tour_people; private phones are removed from the dicts before render (_redact_people :408), not hidden by template.
- Routes: GET /tours/<tour_id>/people; POST /tours/<tour_id>/people/save; GET /tours/<tour_id>/people.csv
- Files: tour_os.py:3154 people(), :3177 person_save(), :4541 people_csv(); press_store.list_contacts; templates/tour/people.html, _person_form.html
- Access: view to read (redacted); require_tour("people") to write and to export. Press Desk contacts show only to the owner and only when a team seat holds the Marketing room (tour_os.py:380 _press_contacts_open).

**Planning / Live mode**

Forces the tour header into planning or live view, or lets the dates decide.

- Because: tour_os.py:1551 writes tours.mode_override and logs it; the docstring records that this route was missing and the header button 404'd until it was added.
- Routes: POST /tours/<tour_id>/mode
- Files: tour_os.py:1551 tour_mode_set(); tour_engine.py:114 tour_mode(); tours.mode_override
- Access: require_tour("edit").

**Public share pages**

The pages a share token opens: day sheet, photographer brief, guest check-in, venue guest list, driver sheet, set list, production pack, VIP check-in, rooming list, band itinerary, Stage Control.

- Because: tour_os.py:4712 shared() resolves the link, enforces password and expiry, counts the access, and renders the scope's own template from real rows; the band scope is built field by field so a column added later cannot start travelling (:4743); guest and VIP check-in POST real status changes back.
- Routes: GET and POST /tour-share/<token>; GET /tour-share/<token>/file/<file_id>
- Files: tour_os.py:4712 shared(), :4840 shared_file(), :4699 _share_link_or_404(); templates/tour/share_*.html, print_day_sheet.html; stage_os.py:583 guest_page() for scope "stage"
- Access: Anonymous — app.py:4848 lists /tour-share/ public; the token plus any password is the authorisation. A production file download re-checks visibility=all, category and that the file belongs to the linked show (tour_os.py:4846).

**Public show day page**

The public page a show's share token opens for local crew: schedule, advance facts and the stage plot.

- Because: app.py:7312 resolves the token with db.get_show_by_share_token and renders templates/showday.html from the show's real advance dict and the owner's saved plot.
- Routes: GET /showday/<token>
- Files: app.py:7312 showday(); templates/showday.html; db.get_show_by_share_token, db.get_stage_plot
- Access: Anonymous — app.py:4813 lists /showday/ public; the token is the authorisation.

**Public tech rider**

The public rider a venue reads: stage plot, input list, schedule, backline and the lighting rig summary.

- Because: app.py:7327 renders templates/rider.html from the show's advance, the account's stage plot and db.get_light_show; tour_os mints the token on first advance send (_rider_url :2451).
- Routes: GET /rider/<token>
- Files: app.py:7327 tech_rider(); templates/rider.html; db.get_stage_plot / get_light_show
- Access: Anonymous — app.py:4817 lists /rider/ public.

**Schedule (the day's times)**

Timed items per day with category, precision, audience and visibility, plus a standard-day template and copy-from-another-date.

- Because: tour_os.py:2168/2183/2201 read and write tour_schedule and log each change; copy_standard_day and copy_schedule build from real rows.
- Routes: GET /tours/<tour_id>/schedule; POST /tours/<tour_id>/schedule/add; POST /tours/<tour_id>/schedule/<item_id>/edit; POST .../shows/<show_id>/standard-day; POST .../shows/<show_id>/copy-schedule
- Files: tour_os.py:2168 schedule_all(), :2183 schedule_add(), :2201 schedule_edit(), :2222 standard_day(), :2304 copy_schedule(); templates/tour/schedule.html; tour_store.py:265
- Access: view to read (rows filtered by tour_engine.visible_to); require_tour("schedule","edit") to write.

**Send the advance**

Composes one email per show from its own rows, attaches the plot, input list, rider files and a Vault press kit, sends it and records the send.

- Because: tour_os.py:2616 _deliver_advance composes through tour_advance_mail, attaches real bytes and calls email_provider.send, then writes tour_advance_sends with sent/failed; :2648 refuses to report "sent" when the mailer is unconfigured or on Resend's shared test sender.
- Routes: POST /tours/<tour_id>/shows/<show_id>/advance/send; POST /tours/<tour_id>/advance/send-all
- Files: tour_os.py:2641 advance_send(), :2669 advance_send_all(), _send_context :2498, _build_attachments :2553; tour_advance_mail.py; email_provider.py; tour_store.py:533 tour_advance_sends
- Access: require_tour("advance", "edit"). A team seat composes and sends but is given no public rider or production link — tour_os.py:2513 links_held blanks both.

**Set lists**

Set lists per date and per tour, parsed one song per line with durations and Encore/Alt sections, linked to catalog tracks, printable.

- Because: tour_os.py:3822 _setlist_items parses the box and matches titles against store.list_os_tracks; :3846 and :3886 write tour_setlists / tour_setlist_items; :3929 prints.
- Routes: POST .../shows/<show_id>/setlist; GET and POST /tours/<tour_id>/setlists; GET /tours/<tour_id>/setlists/<setlist_id>/print
- Files: tour_os.py:3846 setlist(), :3873 setlists(), :3886 setlists_edit(), :3929 setlist_print(); templates/tour/setlists.html, print_setlist.html
- Access: view to read and print; require_tour("edit", "production") to create, copy, save or delete.

**Settlement**

The night-of numbers on a date — ticket gross, expenses, settlement amount, collected — and a printable settlement summary.

- Because: SETTLEMENT_FIELDS (tour_os.py:172) post through show_money into tour_show_ext, and :3657 renders print_settlement.html from tour_engine.show_money plus the date's expenses and merch counts; probed 200.
- Routes: POST .../shows/<show_id>/money (settlement keys); GET .../shows/<show_id>/settlement-summary
- Files: tour_os.py:3596 show_money(), :3657 settlement_summary(); tour_engine.py:1151 show_money(); templates/tour/print_settlement.html, show/_settlement.html
- Access: require_tour("financials"); same team-seat Money-room rule as Tour money.

**Share a light show for notes**

Sends one light show to a reviewer by link and collects their comments against it.

- Because: app.py:7489 mints a light_shares token and :7525 renders templates/lights_share.html for anyone holding it; _share_payload :7473 assembles a field whitelist so account-internal ids never travel, and comments write light_comments from both sides.
- Routes: POST /lights/library/<show_id>/share; GET /lights/library/<show_id>/shares; POST /lights/share/<token>/revoke; GET /lights/show/<token>; GET /lights/show/<token>/comments; POST /lights/show/<token>/comment; GET /lights/library/<show_id>/comments; POST /lights/library/<show_id>/comment; POST /lights/comments/<comment_id>/resolve; POST /lights/comments/<comment_id>/delete
- Files: app.py:7489 lights_share_create(), :7504 lights_share_list(), :7516 lights_share_revoke(), :7525 lights_share_page(), :7537/:7544/:7560/:7569/:7584/:7594; lights_store.py:82 light_shares, :91 light_comments; templates/lights_share.html; static/js/lights-share.js
- Access: The owner's routes need the signed-in account; /lights/show/<token> and its comment routes are anonymous (app.py:4832 lists /lights/show/ public).

**Share links**

Unguessable, optionally password-protected and expiring links that hand one thing to one outsider — eleven scopes including the whole-run band itinerary and Stage Control.

- Because: tour_os.py:4654 writes tour_share_links with a salted SHA-256 password hash (:4611) and an expiry, :4683 draws a QR only for a live link, and :4712 serves each scope by assembling fields explicitly rather than stripping a row.
- Routes: GET /tours/<tour_id>/share; POST .../share/new; POST .../share/<link_id>/revoke; GET .../share/<link_id>/qr.svg
- Files: tour_os.py:4625 share(), :4654 share_new(), :4676 share_revoke(), :4683 share_qr(); SHARE_SCOPE_LABELS :4638; tour_store.py:136 SHARE_SCOPES, :655 tour_share_links; templates/tour/share.html
- Access: require_tour("admin"). Shut to a team seat two ways: app.py:5057 _team_blocked_inside and tour_os.py:266 _SEAT_SHUT — a link outlives the seat that saw it.

**Show list and attach**

Every date as a row with readiness and advance recipients, plus attaching an old Tour Hub show onto the tour.

- Because: tour_os.py:1617 renders real rows and ts.advance_send_map; :1637 attaches by ts.attach_show after checking the show belongs to the account.
- Routes: GET /tours/<tour_id>/shows; POST /tours/<tour_id>/shows/attach
- Files: tour_os.py:1617 shows_list(), :1637 shows_attach(); templates/tour/shows.html
- Access: view to read; require_tour("admin") to attach.

**Show Passports**

The act's technical document — contacts, personnel, input list, monitor mixes, backline, cues — published as immutable versions.

- Because: passport_os.py:76-257 read and write the ten passport_* tables through passport_store, and publish() freezes a version row that later attachments point at by id.
- Routes: GET /passports; POST /passports/new; GET /passports/<id>; POST /passports/<id>/identity; POST /passports/<id>/<section>/add|<row_id>/save|<row_id>/delete; POST /passports/<id>/playback; POST /passports/<id>/inputs/import; POST /passports/<id>/publish; POST /passports/<id>/archive; GET /passports/<id>/versions; GET /passports/<id>/version/<version_id>; POST /passports/<id>/version/<version_id>/archive
- Files: passport_os.py:76 index(), :97 create(), :111 detail(), :189 publish(), :233 versions(); passport_store.py:84-245; templates/passports/
- Access: Signed in and the passport's owner — require_passport 404s on anybody else's id (passport_os.py:46). required_tier is None, but plans._TOUR_PATHS puts /passports behind the Tour suite (Pro) wherever plans.gates_on(). Team seat: the Stage room.

**Stage Control — device API**

The four endpoints a Stage Bridge daemon calls out to: heartbeat, pull, ack, reconcile.

- Because: stage_os.py:420-457 authenticate by bearer device token (stage_bridge.authenticate) and answer 401 without one; stage_bridge signs commands with HMAC-SHA256 over a canonical body with a nonce and expiry, and refuses a nonce already settled; tools/stage_bridge_daemon.py is the matching client.
- Routes: POST /bridge/heartbeat; POST /bridge/pull; POST /bridge/ack; POST /bridge/reconcile
- Files: stage_os.py:413 _device_from_request(), :420 device_heartbeat(), :437 device_pull(), :446 device_ack(), :457 device_reconcile(); stage_bridge.py; tools/stage_bridge_daemon.py
- Access: No session — app.py:4808 lists /bridge/ public and every route 401s without a valid device token.

**Stage Control — Engineer Desk**

The front-of-house screen: open requests against the frozen passport's mixes, the decision buttons, history and the mode banner.

- Because: stage_os.py:157 desk() reads real stage_requests/stage_events rows through stage_store and the attached version's mixes through advance_store.snapshot_for; :208 act() drives the whitelisted state machine (stage_store.TRANSITIONS) and writes events; probed GET /stage/<show_id> 200.
- Routes: GET /stage/<show_id>; POST /stage/<show_id>/request/<request_id>/<action>; POST /stage/<show_id>/lock
- Files: stage_os.py:157 desk(), :208 act(), :467 lock(); stage_store.py:126 stage_requests, :158 stage_events, :188 stage_locks; templates/stage/desk.html
- Access: require_show("stage_review"): the account that owns the show's passport attachment, or a partner seat whose role carries the permission (partner_store.PERMS), with every such act written to partner_audit; anybody else is 404 (stage_os.py:54 _resolve). "send" and a revert of an applied change also need stage_operate. /stage is not tier-gated or suite-gated; team seats reach it under the Stage room (team_areas EXTRA).

**Stage Control — event poll**

The realtime transport: returns everything after a cursor plus the counters, on a timer rather than a socket.

- Because: stage_os.py:186 events() returns stage_store.events_since / cursor / summary and stage_bridge.mode as JSON; the module docstring records that the deployment has eight request slots so SSE is deliberately not used; probed 200.
- Routes: GET /stage/<show_id>/events; GET /stage/guest/<token>/events
- Files: stage_os.py:186 events(), :618 guest_events(); stage_store.py cursor()/events_since(); stage_events.seq AUTOINCREMENT
- Access: Same as the desk for /stage/<show_id>/events; the guest poll is anonymous behind a valid "stage" share token and answers 401 if the link carries a password not yet entered.

**Stage Control — guest phone by share link**

The same performer page for someone with no account, opened from a TOUR share link of scope "stage".

- Because: stage_os.py:563 _guest_link checks the link the way TOUR does and additionally that scope == "stage"; :583 guest_page is what tour_os.shared() calls for that scope, and the guest POSTs write the same stage_requests rows.
- Routes: GET /stage/guest/<token>; POST /stage/guest/<token>/ask; POST /stage/guest/<token>/cancel/<request_id>; GET /stage/guest/<token>/events; also reached via GET /tour-share/<token>
- Files: stage_os.py:563 _guest_link(), :583 guest_page(), :591 guest(), :602 guest_ask(), :610 guest_cancel(); templates/stage/_guest_shell.html; tour_os.py:4730 dispatch
- Access: Anonymous — app.py:4811 lists /stage/guest/ public; the token is the authorisation and a password-protected link bounces to TOUR's password form first.

**Stage Control — performer's phone**

The big dark page a performer holds mid-song to ask for more, less, mute or to report a problem on their own mix.

- Because: stage_os.py:481 _performer_page renders from the frozen version and stage_store.for_performer, and _ask :510 recomputes which mixes are the performer's on the server rather than trusting the form; submissions become real stage_requests rows.
- Routes: GET /stage/<show_id>/me; POST /stage/<show_id>/ask; POST /stage/<show_id>/cancel/<request_id>
- Files: stage_os.py:542 performer(), :551 ask(), :557 cancel(), :481 _performer_page(); templates/stage/performer.html
- Access: require_show("stage_review") — the owner's own session.

**Stage Control — Stage Bridge and safety**

Registers the venue device, patches mixes and channels, arms, locks out, rotates and revokes credentials, and sets the per-show safety policy.

- Because: stage_os.py:320 bridge_act drives stage_bridge register/rotate/revoke/arm/lockout against stage_devices with a hashed token and a signing key, and stage_safety.set_policy refuses out-of-bounds values by name (stage_safety.py:28 POLICY_DEFAULTS); credentials are handed to the page once through the session, never a URL (stage_os.py:34).
- Routes: GET /stage/<show_id>/bridge; POST /stage/<show_id>/bridge/<action>; GET /stage/<show_id>/bridge/diagnostics.json
- Files: stage_os.py:274 bridge(), :320 bridge_act(), :302 bridge_diagnostics(); stage_bridge.py:64 stage_devices, :87 stage_commands; stage_safety.py:51 stage_policies; stage_rack.py; templates/stage/bridge.html
- Access: require_show("stage_configure") for the page; the POST route is require_show("stage_lockout") and then re-checks stage_configure for everything except the emergency lockout (stage_os.py:324). register and rotate are refused inside a team seat with 403 (stage_os.py:327).

**Stage plot editor**

Draws the act's stage plot in the browser and keeps a rendered PNG so the advance email can attach it.

- Because: app.py:8206 renders templates/stage_plot.html with the saved plot JSON, :8217 saves it to stage_plots, and :8226 accepts a browser-rasterised PNG (checked for the PNG magic bytes and a 4 MB cap) into plot_images; tour_os._build_attachments:2568 attaches that PNG to advances.
- Routes: GET /stage-plot; POST /stage-plot/save; POST /stage-plot/image; GET /stage-plot/image.png
- Files: app.py:8206 stage_plot(), :8217 stage_plot_save(), :8226 stage_plot_image_save(), :8244 stage_plot_image_get(); plot_images.py; static/js/stageplot.js; db.py:157 stage_plots, :164 stage_plot_images
- Access: Signed in; required_tier("/stage-plot") is artist, and plans._TOUR_PATHS puts it behind the Tour suite (Pro) wherever plans.gates_on(). Team seat: the Stage room.

**Stage plot inside the tour**

Shows the account's stage plot inside the tour frame, editable only by the tour owner.

- Because: tour_os.py:4121 reads db.get_stage_plot for the tour owner and passes editable=viewer.is_owner; the drawing itself is the one at /stage-plot.
- Routes: GET /tours/<tour_id>/stage-plot
- Files: tour_os.py:4121 stage_plot(); templates/tour/stage_plot.html; db.py:157 stage_plots
- Access: require_tour("view") to see; only the tour owner may change it.

**Team-Up Board**

Artists and venues posting what they are looking for, filtered by kind, region, genre and date window.

- Because: board.py:90 lists real tour_board rows through board_store with structured region/window/genre columns and verified chips; :120 posts with coaching when a field is weak; probed GET /tour-board 200.
- Routes: GET /tour-board; GET and POST /tour-board/post; GET /tour-board/<listing_id>; GET and POST /tour-board/<listing_id>/edit; POST /tour-board/<listing_id>/close; /reopen; /fill; /renew; /delete; GET /tour-board/api/regions
- Files: board.py:90 index(), :120 post(), :199 listing(), :276 edit(), :292 close(), :301 reopen(), :310 fill(), :341 renew(), :350 delete(), :180 api_regions(); board_store.py; board_taxonomy.py; db.py:267 tour_board; templates/board/
- Access: Signed in; required_tier is None but plans._TOUR_PATHS puts /tour-board behind the Tour suite (Pro) wherever plans.gates_on(). Team seat: the Stage room; the seat posts and reads as the artist (board.py:26).

**Team-Up Board expiry and renewal**

Listings expire, get one renewal email with a one-click link, and can be renewed or reopened.

- Because: board.py:68 _sweep_renewals runs on every GET /tour-board, notifies and emails through board_store.expiring_soon / mark_renew_notice, and :327 renews on a single-use token without a session.
- Routes: GET /board-renew/<listing_id>?t=<token>; POST /tour-board/<listing_id>/renew
- Files: board.py:68 _sweep_renewals(), :327 renew_by_token(), :341 renew(); board_store.py renew()/expiring_soon(); templates/board/renewed.html
- Access: /board-renew/ is anonymous (app.py:4850 lists it public); the single-use token is the authorisation. The POST renew needs the signed-in owner.

**Team-Up Board saved searches**

Watches a kind, region, genre and date window and alerts the watcher when a matching listing is posted.

- Because: board.py:361 writes board_watches and :143 _alert_watchers walks board_store.matching_watches on every new listing, notifying in-app and by email.
- Routes: POST /tour-board/watch; POST /tour-board/watch/<watch_id>/delete
- Files: board.py:143 _alert_watchers(), :361 watch(), watch_delete(); board_store.py:76 board_watches
- Access: Same as the board.

**Team-Up Board threads and inbox**

In-platform reply threads between a poster and a replier, with an unread count and email notification.

- Because: board.py:223 starts or reuses a board_threads row and writes board_messages, notifies through db.notify and emails when the mailer is configured; :250 refuses anyone who is not one of the two parties with 404, and a team seat leaves messages unread for the artist (:262).
- Routes: POST /tour-board/<listing_id>/reply; GET and POST /tour-board/thread/<thread_id>; GET /tour-board/inbox
- Files: board.py:161 inbox(), :223 reply(), :250 thread(); board_store.py:56 board_threads, :68 board_messages; templates/board/inbox.html, thread.html
- Access: Same as the board; each thread is visible only to its poster and replier.

**Tour crew and scopes (Team)**

Invites people by email with a role preset and a scope list, links them to a person record, changes or removes them.

- Because: tour_os.py:4870 writes tour_members with an invite token, notifies an existing account and emails the join link when the mailer is live; only the owner may hand out admin (:4877, :4915).
- Routes: GET /tours/<tour_id>/team; POST .../team/invite; POST .../team/<member_id>
- Files: tour_os.py:4858 team(), :4870 team_invite(), :4900 team_member(); tour_store.py:145 SCOPES, :149 ROLE_PRESETS, :200 tour_members; templates/tour/team.html
- Access: require_tour("admin"), and refused to a team seat (app.py:5057, tour_os.py:266).

**Tour files**

Uploads against the tour, a date, an expense or a content row, with category, visibility and download.

- Because: tour_os.py:4005 _store_upload writes to the object store or a private directory beside the database and records tour_files; :4078 re-checks visibility before serving and 404s on a record the viewer may not see.
- Routes: GET /tours/<tour_id>/files; POST .../files/upload; GET .../files/<file_id>/download; POST .../files/<file_id>/delete
- Files: tour_os.py:4038 files(), :4055 file_upload(), :4078 file_download(), :4101 file_delete(), :3979 _tour_dir(); blob_store.py; tour_store.py:518; templates/tour/files.html, too_large.html
- Access: require_tour("files") to list, upload and delete; view to download (filtered by _files_for :500). Money categories (invoice, tax, settlement, contract) are downgraded to "other" without financials (tour_os.py:4068). Deleting needs owner, admin or being the uploader. 25 MB cap, allowed extensions at tour_os.py:66.

**Tour home (Dates)**

The tour's list of dates with a readiness figure each, and the fetch buttons for photos, coordinates and ticket counts.

- Because: tour_os.py:1418 home() reads ts.list_shows/list_people, scores each date from rows, and renders tour/home.html; probed 200.
- Routes: GET /tours/<tour_id>
- Files: tour_os.py:1418 home(); _readiness_for :1154; templates/tour/home.html; tour_store.py, tour_engine.show_readiness
- Access: require_tour("view") — owner, or a tour member whose scopes include view/admin. Money fields are stripped for anyone without financials (tour_os.py:396).

**Tour Hub legacy forms**

The old Hub's POST endpoints that still write a show's status, advance fields, settlement and public rider token.

- Because: app.py:7204-7290 still write through db.add_tour_show / update_tour_show_status / save_show_advance / save_show_settlement / set_show_share_token against the same tour_shows rows TOUR reads.
- Routes: POST /tour/add; /tour/<show_id>/status; /tour/<show_id>/delete; /tour/<show_id>/advance; /tour/<show_id>/settlement; /tour/<show_id>/share; /tour/<show_id>/send-advance
- Files: app.py:7204 tour_add(), :7217 tour_status(), :7227 tour_delete(), :7254 tour_show_advance(), :7264 tour_show_settlement(), :7282 tour_show_share(), :7290 tour_send_advance(); touring.py; db.py:148 tour_shows
- Access: Signed in, artist tier. Settlement additionally needs the Money and business room on a team seat (app.py:7268). /tour/<id>/share and /tour/<id>/send-advance are shut to any team seat (app.py:5059).

**Tour Hub legacy redirects**

Keeps old /tour and /tour/<show_id> links working by adopting the show onto a tour and redirecting into TOUR.

- Because: app.py:7196 and :7235 redirect through tour_store.adopt_orphan_shows into /tours/<id>/shows/<id>; probed GET /tour returned 302.
- Routes: GET /tour; GET /tour/<show_id>
- Files: app.py:7196 tour_hub(), :7235 tour_show_detail(), _tour_dates_url :7186; tour_store.adopt_orphan_shows
- Access: Signed in; required_tier("/tour") is artist (plans.py _ARTIST_PATHS). Team seat: the Stage room (team_areas.EXTRA "stage").

**Tour money**

Deal, backend, merch and VIP per date rolled into earned, outstanding and net, with expenses and a CSV.

- Because: tour_os.py:3581 builds from tour_engine.tour_finance over real show fields and tour_expenses rows; money_csv :3639 exports the same numbers.
- Routes: GET /tours/<tour_id>/money; POST .../shows/<show_id>/money; POST .../expenses/add; POST .../expenses/<expense_id>/delete; GET /tours/<tour_id>/money.csv
- Files: tour_os.py:3581 money(), :3596 show_money(), :3608 expense_add(), :3632 expense_delete(), :3639 money_csv(); tour_engine.py:1188 tour_finance(); tour_store.py:551 tour_expenses
- Access: require_tour("financials") on every route. A team seat also needs the Money and business room: tour_os.py:311 _seat_money_open consults team_areas.money_open, so can(viewer,"financials") is false without it.

**Tour search**

Searches the tour's shows, people, venues, schedule, hotels, travel, files and guests in one box.

- Because: tour_os.py:4951 queries each store list and folds the results, applying the same redactions and scope checks as the pages; probed 200.
- Routes: GET /tours/<tour_id>/search
- Files: tour_os.py:4951 search(); templates/tour/search.html
- Access: require_tour("view"); file hits need files, guest hits need guests.

**Tour settings**

Renames the tour, sets artist name, dates, home time zone, currency and status, and deletes the tour.

- Because: tour_os.py:4922 writes the tours row, validates the time zone and logs a status change; deletion needs the tour name typed back and the owner, and ts.delete_tour clears the child tables (tour_store.py:885).
- Routes: GET and POST /tours/<tour_id>/settings
- Files: tour_os.py:4922 settings(); tour_store.delete_tour; templates/tour/settings.html
- Access: require_tour("admin"); deletion additionally requires viewer.is_owner and is refused to a team seat (tour_os.py:4929).

**Tour tasks**

Tasks against the tour or one date, kept in the account's Command Center action list.

- Because: tour_os.py:3951 calls command_center.create_action with entity_type tour/tour_show, and :3941 filters the account's actions back down to this tour (_tour_tasks :1654); rows live in street_actions.
- Routes: GET /tours/<tour_id>/tasks; POST .../tasks/add; POST .../tasks/<action_id>/status
- Files: tour_os.py:3941 tasks(), :3951 task_add(), :3970 task_status(); command_center.py:43 create_action(); templates/tour/tasks.html
- Access: view to read; require_tour("edit","schedule","advance","production") to add or change status.

**Tours (index)**

Lists the tours the account owns and the tours it was invited onto, plus one month-grid across all of them.

- Because: tour_os.py:1234 reads tour_store.list_tours / tours_shared_with and renders tour/index.html; probed GET /tours returned 200 for a real account.
- Routes: GET /tours
- Files: tour_os.py:1234 index(); _all_tours_month() tour_os.py:1271; templates/tour/index.html; store tour_store.py
- Access: Any signed-in account (no required_tier for /tours, not suite-path-gated). Owning a tour needs the artist tier, or Pro where plans.gates_on() (tour_os.py:1225 _artist_tier). Team seat: the Stage room (team_areas.py EXTRA/rooms.ROOMS); a seat sees only the artist's own tours, never tours the artist was invited onto (tour_os.py:282 _seat_viewer).

**Travel**

Flights, ground and bus legs per day with travellers, confirmation numbers and status.

- Because: tour_os.py:2703/2715/2731 read and write tour_travel (tour_store.py:336); confirmation numbers and driver phones are stripped for viewers without the travel scope (_redact_travel :447).
- Routes: GET /tours/<tour_id>/travel; POST /tours/<tour_id>/travel/add; POST /tours/<tour_id>/travel/<travel_id>/edit
- Files: tour_os.py:2703 travel_all(), :2715 travel_add(), :2731 travel_edit(); templates/tour/travel.html, _travel_form.html
- Access: view to read (redacted); require_tour("travel") to write. A delete notifies the other members (tour_os.py:2742).

**Venue book**

The account's saved rooms with address, capacity, production notes and a photo, linkable to a date.

- Because: tour_os.py:2826/2849/2867 read and write tour_venues (tour_store.py:288) keyed to the tour owner, and the page names its own gaps (dates with no record, records with no photo).
- Routes: GET /tours/<tour_id>/venues; POST .../venues/link; POST .../venues/save; POST .../venues/<venue_id>/photo; POST .../shows/<show_id>/venue/from-advance
- Files: tour_os.py:2826 venues(), :2849 venue_link(), :2867 venue_save(), :2914 venue_photo_save(), :3125 venue_from_advance(); templates/tour/venues.html, _venue_form.html
- Access: view to read; require_tour("edit", "advance") to link, save, upload a photo or promote advance facts onto a record.

**Venue photo fetch (Google Places)**

Asks Google Places for a photo of every room on the tour that has none and reports what it got.

- Because: tour_os.py:2948 calls venue_photos.ensure/search which makes a real Places (New) searchText + media call (venue_photos.py:27); with no GOOGLE_MAPS_API_KEY configured() is False and the page says so rather than fetching.
- Routes: POST /tours/<tour_id>/venues/fetch-photos; GET /tours/<tour_id>/venues/<venue_id>/photo
- Files: tour_os.py:2948 venue_fetch_photos(), :2894 venue_photo(); venue_photos.py; blob_store.py; tour_venues.photo
- Access: require_tour("edit", "advance") for the fetch; require_tour("view") to read a photo.

**VIP at the door**

VIP packages sold offline, recorded per date, with check-in, no-show and merch-fulfilled states.

- Because: tour_os.py:3291/3304 write tour_vip (tour_store.py:451) and :3914 rolls the run up from ts.vip_summary; probed /tours/<id>/vip 200.
- Routes: POST .../shows/<show_id>/vip/add; POST .../shows/<show_id>/vip/<vip_id>; GET /tours/<tour_id>/vip
- Files: tour_os.py:3291 vip_add(), :3304 vip_update(), :3914 vip(); templates/tour/vip.html, show/_vip.html
- Access: require_tour("vip").

**What changed (activity log)**

The tour's change log by severity, marked seen automatically and acknowledged by hand for critical entries.

- Because: every write path in tour_os calls ts.log_change into tour_changes; :4136 reads them filtered by the viewer (_changes_for :462) and writes tour_acks; a team seat marks nothing seen and cannot acknowledge (:4152, :4165).
- Routes: GET /tours/<tour_id>/changes; POST /tours/<tour_id>/changes/<change_id>/ack
- Files: tour_os.py:4136 changes(), :4163 change_ack(), _log :1198; tour_store.py:629 tour_changes / :645 tour_acks; templates/tour/changes.html
- Access: require_tour("view"); the acknowledgement roster for critical changes needs admin.

### Partial

**Advance inbox (extractor)**

Pastes a venue's advance email, proposes times and facts with the line each came from, and writes only what is ticked.

- Because: tour_engine.extract() is real pattern matching with no model behind it (tour_engine.py:14) and the apply step writes schedule rows and advance items, but a PDF upload is refused outright — tour_os.py:2380 returns "PDF text extraction is not installed on this deployment".
- Routes: POST /tours/<tour_id>/shows/<show_id>/inbox
- Files: tour_os.py:2367 inbox(); tour_engine.py:691 extract(); tour_store.record_import; templates/tour/show/_inbox.html
- Access: require_tour("advance", "edit").

**Route map and fuel**

The run as legs between rooms with distance, a measured drive time where one exists, an overnight-gap warning, and a fuel plan.

- Because: tour_os.py:4233 prints a measured Google drive only when one is cached (leg_drive :789) and otherwise the app's own haversine labelled a straight line; the overnight flag needs both a measured duration and two entered times (overnight_gap :832); fuel is computed only from driven miles somebody entered on a ground leg, never from crow-flight totals (:4275).
- Routes: GET /tours/<tour_id>/map; POST /tours/<tour_id>/fuel
- Files: tour_os.py:4233 route_map(), :4288 fuel_save(), _haversine_km :4218; tour_engine.py:801 fuel_plan(); venue_geo.py; templates/tour/map.html
- Access: view to read; require_tour("travel") to save the fuel settings.

**Ticket sync (Eventbrite + Ticketmaster)**

Matches each date to a listing and fills the link, on-sale word and — from Eventbrite only — the sold count.

- Because: tour_tickets.sync() calls both providers for real, but Ticketmaster publishes no sold count at all (tour_tickets.py:1) and ticketmaster_provider.enabled() is off on every deployed service unless TICKETMASTER_ENABLED=on; with no token the page names the missing key instead of a button.
- Routes: POST /tours/<tour_id>/tickets/sync; POST /tours/<tour_id>/shows/<show_id>/tickets/link
- Files: tour_os.py:3082 tickets_sync(), :3101 tickets_link(), _ticket_progress :2028; tour_tickets.py; eventbrite_provider.py; ticketmaster_provider.py
- Access: require_tour("edit", "advance").

**Venue coordinates, time zones and drives**

Geocodes each room, fills a date's time zone from its room, and measures the drives between consecutive dates.

- Because: tour_os.py:3009 uses venue_geo Geocoding and Time Zone (both live on the key per venue_geo.py:1), but Routes v2 latches off on the first refusal (venue_geo.routes_available :106) and the map then prints only the straight line this app computes itself.
- Routes: POST /tours/<tour_id>/venues/fetch-coordinates
- Files: tour_os.py:3009 venue_fetch_coordinates(), measure_leg :804, leg_drive :789; venue_geo.py; drives cached in app_kv under geo_leg:*
- Access: require_tour("edit", "advance").

**VIP sold online (Stripe)**

One public purchase link per date: a fan picks a package, pays Stripe, and the sale is recorded once with the platform fee split out.

- Because: the whole path is real — stripe_provider.create_vip_checkout posts to /v1/checkout/sessions, claim_vip_session (tour_os.py:3443) records only a session Stripe says is paid and is idempotent across the webhook and the redirect — but sales_switch.is_on() defaults to off (sales_switch.py:22) so /vip/<token>/buy redirects with err=closed, and payouts are not automatic: the pages say Street Banker settles outside the app (templates/tour/vip.html:28).
- Routes: GET /vip/<token>; POST /vip/<token>/buy; POST .../shows/<show_id>/vip/offers/add; POST .../shows/<show_id>/vip/offers/<offer_id>; POST .../shows/<show_id>/vip/dayof; POST /webhooks/stripe
- Files: tour_os.py:3484 vip_public(), :3508 vip_buy(), :3537 vip_offer_add(), :3552 vip_offer_update(), :3562 vip_dayof(), :3443 claim_vip_session(); app.py:5781 webhook branch; stripe_provider.py:579; sales_switch.py; tour_store.py:474 tour_vip_offers / :492 tour_vip_sales / :512 tour_vip_links; templates/tour/vip_public.html
- Access: /vip/<token> and /vip/<token>/buy are anonymous (app.py:4816 lists /vip/ public). Offers, day-of mail and the ledger need require_tour("vip"); a team seat is shown no purchase link and mints none (tour_os.py:3387). Fee from VIP_PLATFORM_FEE_PCT, clamped 0-50, default 15 (tour_os.py:3348).

### Stubbed

**Example tour (seed demo)**

Loads a fictional four-show tour into the demo showcase account.

- Because: tour_seed.py is all invented venues, people and numbers, and tour_os.py:1372 404s for any account demo_accounts.is_demo_email() does not name.
- Routes: POST /tours/seed-demo
- Files: tour_os.py:1372 seed_demo(); tour_seed.py:18 seed(); demo_accounts.py
- Access: The four seeded showcase logins only (demo_accounts.EMAILS); any other account gets 404.

**Mock Up Tour**

Seeds each empty Tour account with a 44-day invented routing so the product opens on something clickable.

- Because: tour_mockup.py holds a hard-coded tab-separated SHEET of invented venues on 2027 dates; it is run for any account with no tours (tour_os.py:1249) and only when enabled() is true, which is RENDER or MOCK_UP_TOUR=on.
- Routes: no route of its own; runs inside GET /tours
- Files: tour_mockup.py:24 enabled(), SHEET at :39, ensure_for(); called tour_os.py:1249; parsed through tour_engine.parse_csv_rows
- Access: Any signed-in account at the artist/Pro tier reaching /tours with no tours; never on a team seat's visit (tour_os.py:1244).

**Stage Control — console adapters**

The only thing in the system that touches a desk, and the vocabulary that bounds what can be asked of one.

- Because: stage_adapters.py:234 ADAPTERS = {"simulator": SimulatorAdapter} and nothing else ships; the X32 adapter is a bench entry reachable only with STAGE_BENCH_ADAPTERS=1, with tested_model "UNTESTED - not yet bench-tested on any X32" and verified False (stage_x32.py:184). stage_bridge.run_local refuses to drive anything not simulated, so on a real deployment "Send to console" moves a simulator.
- Routes: no routes of its own; reached from POST /stage/<show_id>/request/<id>/send and the bridge page
- Files: stage_adapters.py:234 ADAPTERS, :239 _bench_adapters(), :247 bench_enabled(), NEVER list :35; stage_x32.py:184 SPEC; stage_bridge.run_local; tools/x32_bench.py
- Access: n/a — reached through the desk's stage_operate permission.

### Dead code

**Advance conversation (questions, conflicts, approval, lock)**

The state machine that would carry a venue's questions, the conflicts between passport and room, and the approval that locks the advance.

- Because: advance_store defines ask, answer, questions, raise_conflict, resolve_conflict, conflicts, blockers, can_approve, approve and set_state, and a grep for `adv.<fn>(` / `advance_store.<fn>(` across the repo outside advance_store.py and tests returns zero for every one of them; no route, template or other module calls any. Attachments are written at state 'draft' (advance_store.py:138) and nothing ever moves them, so show_questions and show_conflicts are never written.
- Routes: none
- Files: advance_store.py:224 ask(), :243 answer(), :255 questions(), :270 raise_conflict(), :284 resolve_conflict(), :296 conflicts(), :311 blockers(), :335 can_approve(), :341 approve(), :167 set_state(); tables advance_store.py:73 show_questions, :88 show_conflicts
- Access: n/a — unreachable.

**Legacy board helpers in db.py**

An older set of tour_board query functions superseded by board_store.

- Because: a whole-repo grep across .py/.html/.js finds list_board_listings, get_board_listing, close_board_listing, delete_board_listing, list_own_board_listings and add_board_reply only at their own def lines in db.py — no caller anywhere, tests included; add_board_listing survives only in tests/test_team_up_board.py. board.py imports board_store, not these.
- Routes: none
- Files: db.py:3298 list_board_listings(), :3312 get_board_listing(), :3321 close_board_listing(), :3328 delete_board_listing(), :3338 list_own_board_listings(), :3346 add_board_reply(); superseded by board_store.py:388 onward
- Access: n/a — unreachable.

**Stage Control — presence panel**

Who is on the show's stage pages right now, shown on the Engineer Desk.

- Because: stage_os.py:194 passes st.presence(show_id) to the desk, but stage_store.touch_presence (stage_store.py:266) is the only writer of stage_presence and a whole-repo grep outside stage_store.py and tests finds no caller; the panel can only ever be empty.
- Routes: read inside GET /stage/<show_id>
- Files: stage_store.py:177 stage_presence, :266 touch_presence(), :275 presence(); stage_os.py:194; templates/stage/desk.html
- Access: n/a — nothing writes it.

**Tour fan captures**

A counter on Settings for email/phone captured at shows.

- Because: tour_store.add_fan_capture (tour_store.py:2743) is the only writer of tour_fan_captures and a whole-repo grep for "add_fan_capture" across .py/.html/.js finds no caller anywhere, tests included; the count on templates/tour/settings.html:21 can only ever be zero.
- Routes: none; read inside GET /tours/<tour_id>/settings
- Files: tour_store.py:679 tour_fan_captures, :2743 add_fan_capture(), :2755 fan_capture_summary(); templates/tour/settings.html:21
- Access: n/a — nothing writes it.

**Unused store helpers in the area**

Store functions with no caller outside their own module and the test suite.

- Because: a whole-repo scan of .py/.html/.js excluding tests returns zero references for each: tour_store.show_tour_id, tour_store.delete_vip_offer, tour_engine.tour_readiness, lights_store.rig_for_venue, live_store.manifest_json (live.py:363 calls set_manifest instead).
- Routes: none
- Files: tour_store.py show_tour_id() / delete_vip_offer(); tour_engine.py:295 tour_readiness(); lights_store.py rig_for_venue(); live_store.py manifest_json()
- Access: n/a — unreachable.

> Noted by the reviewer as not yet written up in this area: Automatic venue photo on every write path (_photo_quietly, tour_os.py:644) — a best-effort Google Places lookup that fires when a show is created (tour_os.py:1365), when a day/show is added (:1602), when a venue is promoted from the advance (:2890) and for every row of an import (:4489, with a per-request deadline). The ledger describes only the manual 'fetch photos' button, so it reads as if nothing calls Places unless the owner presses it. Live (same configured() gate).; Stage room landing — GET /room/<room_key> for room_key='stage' (app.py:4635 room_screen, rooms.py:39-40), the card screen that is the door to tours, stage-plot, lights, live, tour-board, passports and tour-suite. Cross-cutting nav, but it is this area's front page and has no entry. Live (rooms.get_room gates by plan/owner/demo-lock; renders templates/room.html).; Team-Up Board activity log — board_events table (board_store.py:87) plus board_store.event() (:714), written on four real paths: listing_posted (:395), listing_<status> (:472), listing_renewed (:497) and message_sent (:553). Nothing ever reads it — a whole-repo grep for 'board_events' across .py/.html/.js, tests included, returns only the CREATE TABLE and the INSERT. Dead code (write-only data collection), and it belongs beside the other Dead-code entries.; EPK Tour Dates block (app.py:3272-3282, used at :3318, :3770, :3860) — the kit prints the account's own confirmed TOUR dates and falls back to bandsintown_provider.upcoming_events / artist_info, labelling which source it used (templates/epk_public.html:236, templates/_epk_document.html:97/:113). A live consumer of this area's data with its own external provider; arguably Press/EPK's entry, but no ledger entry anywhere names it. Live where BANDSINTOWN is configured, TOUR-sourced otherwise.; Money Queue legacy settlement fallback (app.py:7141) — tour income is folded into the money page via tour_hub_rules.settlement_totals(st)['walk'] on legacy Tour Hub settlement rows. A tour-money seam into the Money area that neither the 'Tour money' nor the 'Settlement' entry mentions. Live.

## Command and intelligence

43 features: 28 Live, 10 Partial, 4 Stubbed, 1 Dead code.

### Live

**Action Center**

Work that belongs somewhere (owner's mockup + crawl, 2026-09-23): each action carries an owning room, an action type, a priority, a due date, an assignee from the team, the record it is about (a release, campaign, song, tour, show or document, with an Open door to it), and where it came from with the way back; the board counts dismissed work apart from unfinished work and uses one name per state everywhere (Not started, In progress, Complete, Dismissed).

- Because: street_actions gained room, assignee_id, source, source_href and created_by (additive ALTERs in db.py, empty = unknown, never guessed) plus an index on user_id; actions_center.py turns a row into what a person reads (room, record, source, due words, assignee, next step) and app.py reads the account's records once per page to resolve them. The ten crawl findings are each pinned in tests/test_actions_center.py: dismissed work leaves the completion figure and is reported as "N dismissed, not counted"; any open action reaches the Command Center (the page from zero's attention panel shows the most pressing one and any open action beats "Nothing needs attention yet"; the full page's Today's Priorities fills its spare slots with actions that need attention, with an Open action button, never Fix now; the compass names the top open action when there is no alert; Open Actions rows are links with room and due date); the assignee is a real person (the account holder and confirmed members inside the plan's seat count; a team seat is shown only itself and the account holder, anyone else reads "a teammate"); priority, room, type, due date and assignee are on every row and Needs attention (open and high priority, overdue, or due within three days) is a filter with counts; /actions/<id> shows everything and edits every field; an action typed in by hand (source manual or tour_task) can be deleted after a confirm step, one a check, an alert or a contract reading raised is dismissed instead and the page says why; the list and board share state names and the board has a Dismissed column and Dismiss on every open card; the create button reads Create action and the board confirms "Action created." with View action, Return to source (when there is one) and Add another, said by the saved row, never the param; the form starts at No room, General, Medium and me, and keeps the last choices after a create. The header chip names the account and plan. A read-only seat sees the board and is offered no change.
- Routes: /actions (GET, POST; ?status=all|attention|new|in_progress|complete|dismissed, ?view=board, ?created=<id>), /actions/<id> (GET, POST), /actions/<id>/delete (POST)
- Files: app.py:6879 actions_page, :6953 action_detail, :6991 action_delete (and _actions_context, _action_fields); actions_center.py (FILTERS, BOARD, RECORD_KINDS, due, assignees, records, related, row, brief, pick, source_for_path); command_center.py:116 create_action, :139 get_action, :152 update_action, :196 delete_action, :307 set_action_status, :319 list_actions, :231 board_summary, :250 rank_open, :332 open_actions; account_state.py attention(campaigns, actions), compass(..., actions); templates/actions.html, templates/action_detail.html, templates/command_center.html, templates/command_center_zero.html; static/css/actions.css; db.py street_actions
- Access: plans.required_tier("/actions") = "artist" (in _ARTIST_PATHS); a fan plan gets 402. /actions is in team_areas.WHOLE_ACCOUNT, so a partial-room seat is bounced; a read seat sees the board without a form or buttons (team_seat_gate refuses its writes). Another account's action is a 404 on /actions/<id> and its status or delete does nothing. Not owner-only.

**Artist Signal Profile card**

Shows the homepage EQ mix the artist saved, as a curve plus their lane, priorities and recommended modules.

- Because: the API persists a validated profile to artist_signal_profiles and the Command Center reads it back with store.get_artist_signal_profile, drawing the polyline from the saved channel values; the card renders only when a profile exists
- Routes: /api/artist-signal-profile (GET, POST JSON); the card renders on /command-center
- Files: app.py:1261 artist_signal_profile_api; app.py:5906-5920 (curve build); templates/partials/signal_profile_card.html; artist_eq_config.py; db.py:110 artist_signal_profiles
- Access: Any signed-in account for the API (401 when signed out). /api/artist-signal-profile is in team_areas.WHOLE_ACCOUNT, so a partial-room seat is blocked. The "Not now" dismissal of the stale banner is localStorage only, per-browser.

**Command Center**

One screen holding the account's scores, money band, derived alerts, open actions and the module board.

- Because: handler renders templates/command_center.html with cc.get_summary/build_alerts/open_actions, all of which query the account's own tables; probed 200 for an artist/label plan, 402 for a fan plan
- Routes: /command-center (GET); /overview (GET, alias calling the same function); /dashboard (GET, 302 -> /overview)
- Files: app.py:5903 command_center_page; app.py:2429 overview; app.py:2547 dashboard; command_center.py:329 get_summary; templates/command_center.html; store: db.py (users, statements, statement_rows, catalog_tracks, os_tracks, ml_* tables)
- Access: plans.required_tier("/command-center") = "artist" via plans._ARTIST_PATHS, so Artist/Pro/Label; a fan plan gets upgrade.html 402 (verified). /overview is artist via _PRO_PATHS. Team seats: /command-center, /overview and /dashboard are all in team_areas.WHOLE_ACCOUNT, so a seat with fewer than all eight rooms is redirected to team_areas.home(). Not owner-only. Anonymous is redirected to /login by app.py:4957 plan_gate.

- ACCOUNT STATE, DECIDED ONCE (owner's zero-state spec, 2026-09-22, Pass 1). account_state.py answers `new / setup / operational / error` from saved records, server-side, and the route branches on it. The rule: a failed read is `error` and renders templates/command_center_error.html (503, "We could not load your Command Center", Try again + Browse all tools) - NEVER a fresh account. Before this, _firstrun_panel and _tutor_panel wrapped every query in `except Exception: return None`, so one bad read deleted the setup panel and the account looked finished. The audit that found it also found the page telling a brand-new account four untrue things, all gone: "1 / 5 done" for a name typed at signup (identity is artist or label details SAVED - EPK data or the pulse profile's artist name); a 1m/3m/6m date filter over a chart with nothing in it (the select is inside the `months` guard now, and _front_scripts.html null-checks it); "every live campaign is capturing fans" with no campaigns (reads "Nothing needs attention yet" unless summary.campaign_count); "What Changed Since Your Last Visit" on the first visit ever (since_engine's first_visit is honoured).
- THE FIVE ESSENTIALS replace firstrun's five in the Start-here panel: identity, song, asset (a Release-Ready master or a Studio measurement attached to a track - a rack PRESET is a setting, not an asset), smart link, fan capture (a campaign with email_capture AND consent_text). "Set what you charge" is gone. Two kinds of dependency, from the spec: LOCKED_BY (the smart link is shown on a fresh account but its button is disabled until a song exists, with the reason beside it) and REVEAL_AFTER (the Rack card is not on the board until a song exists; capture not until a link). Only three cards compete at once. Progress is a saved record or it is nothing - opening a task does not count, which firstrun already held and account_state keeps. firstrun.py stays for the tutor's stage names; app.py no longer reads it.
- /all-tools (GET, artist tier): the complete 33-window directory, grouped like the sidebar, with an in-page search - moved out of the Command Center per the spec ("do not place the full directory back inside"). The Command Center still draws its board until Pass 2 replaces it with "Explore at your own pace -> Browse all tools".
- tests/test_account_state.py holds the pure rules (reveal, lock, three-at-once, state_of, error-never-new), the facts against a real store (signup name is not identity; capture needs both halves; a preset is not an asset), and the route (503 error page with no zero values; the fresh account is not lied to; All Tools is the directory).

- THE PAGE FROM ZERO (Pass 2, same day). A `new` or `setup` account gets templates/command_center_zero.html + static/css/command-zero.css - the owner's mockup, in the spec's order: header (eyebrow, one H1, "Start with the essentials. Street Banker will guide the next move.", account chip with "New label" fallback, and CONTINUE SETUP, which opens the FIRST INCOMPLETE MILESTONE and never a generic settings page); the rack - THREE STATIC SCREENS, no rotation (owner: "static on zero-state pages", the animated standby stays on the rooms) reading WELCOME / START HERE (the next actual step, "Complete your artist or label profile." on a fresh account) / PROGRESS ("N of 5 essentials complete.", the one figure on the page and the only measurement); YOUR FIRST STEPS, the three revealed cards with filled gold for the next task, gold outline for another available one, a muted disabled control for a locked one with the reason beside it; HOW STREET BANKER FITS TOGETHER, four neutral stages with no marks and no percentage; NOTHING NEEDS ATTENTION YET beside YOU CAN EXPLORE AT YOUR OWN PACE -> /all-tools; and NEED HELP CHOOSING YOUR FIRST STEP? which focuses the corner Ask box (Contact with scripts off). Nothing forbidden renders: no royalties, recovery, release metrics, empty tables, charts or since-your-last-visit. The rack is drawn in CSS (brushed metal, brass frames, screws, ears, inset CRTs with scanlines) to the room plates' proportions until the owner's photographed plate for this room lands; the markup does not change when it does. Under 560px the drawn plate goes and the three screens stack, the same rule as the room plates. The wrapper carries data-no-collapse so the shell's section-fold does not decorate the headings with chevrons.
- state_of: an account with REAL RECORDS (statements, fans) is OPERATIONAL even mid-setup - its money is never hidden behind an onboarding page - and the essentials panel rides along on the operational page until all five are done (the spec's gradual transition), then goes for good.
- CRT GREEN IS A TOKEN: `--sb-crt: #5DFF8F` / `--sb-crt-dim: #34C96A` in tools/tailwind-input.css and tailwind.config.js (stylesheet rebuilt), and room-kit.css, business-room.css, studio-room.css read `var(--sb-crt)` where they carried the literal. With the drawn rack's colours as tokens too, stage-room.css's stage floor and studio-room.css's needle mapped, and room-stage.js's fallback gel colour marked `sb-keep` (it is a light designer's data, not chrome), tests/test_design_system.py::test_no_raw_hex_outside_the_token_set is GREEN - one of the twelve pre-existing reds cleared.
- "All tools" is in both sidebars: rooms.ACCOUNT_KEYS (first) and hubs.ACCOUNT_GROUP (first).
- Two width-percentage traps on the way: `.cz-screens` first used padding to sit inside the plate, and 22% of the WIDTH pushed all three screens out of the bottom of the plate and over the heading below - top/bottom offsets resolve against the containing block's height, padding does not; and `sb.icons()` knows twelve names and silently draws a grid for any other, so the page draws from the sprite (`<use href="#sb-i-…">`) with an explicit box. tests/test_account_state.py holds the page: the exact copy, the order, the forbidden list, three cards with the lock explained, Continue setup's target moving with the first incomplete milestone, real records -> operational, All tools in the sidebar, the token.

- THE WAY BACK, AND WHAT YOU ARE TOLD (Pass 4, same day). Every setup door on the page from zero and on the operational Start-here panel carries `?returnTo=/command-center&from=<key>`. THE SHELL honours a same-site `returnTo` on ANY page: base.html's back-link reads it through `safe_return()` (a Jinja global over app.py's _safe_next - same-site paths only, never `//host`, never a line break) and prefers it to the rooms rule, so the fix is made once and every task page gets a way back - including the one the Fans audit caught, where leaving Fans for /links/new offered "Back to Marketing". /tracks's pro-plan redirect to /catalog?view=passports carries the two params through, or the song door's way back was lost. ON RETURN the Command Center re-reads the state and, ONLY if the milestone named by `from` is now real, says so in a role=status band: `account_state.done_line()` - past tense, the count, the next step ("Your first song was added. Setup is now 2 of 5 complete. Next, add the working audio in the Rack."). The param names the door; the saved record decides the sentence; `?from=song` with no song saved says nothing, and a plain visit says nothing. tests/test_account_state.py holds all of it: the sentence from state not param, every door carrying the way back, a hostile returnTo dropped, the redirect carrying the query, and the return through a door before and after the thing exists.
- The rack is the owner's photographed three-window plate (static/img/room-plate.webp since 2026-09-23, the shorter plate he sent - "they are too tall"; the Command Center and all eight rooms' pages from zero, Fans included, draw it through partials/cc_rack.html; under an 880px rack the three screens stack as boxes so no sentence is cut; tests/test_room_plate.py). STILL TO COME on this page: the gradual transition rules after the first asset / link / fan / statement (Pass 5); onboarding analytics events; the sidebar regroup, which the owner's own spec holds until the state machinery has settled.

- THE COMPASS, AND THE GRADUAL TRANSITION (Pass 5, same day). The rack is on the OPERATIONAL page too (partials/cc_rack.html, the same photographed plate and measured screens), and there it reads RESUME / NEXT ACTION / BLOCKER from `account_state.compass()`: while setup is incomplete, RESUME carries the count and NEXT ACTION the next essential (with its returnTo door); once done, RESUME is the last campaign touched (or Statements, or "Nothing in progress."), NEXT ACTION the top ranked alert and BLOCKER the top HIGH alert (or "Nothing on fire." / "Nothing blocking."). This is the owner's anti-lost mechanism, pulled forward from the spec's last pass on his agreement: every visit, not only the first, the first screen says where you were, what to do and what is in the way. It is also the spec's "collapse setup into a compact completed state" - the rack says it, so no permanent congratulation panel. Priorities are capped at three (`cc_alerts=alerts[:3]`, ranked). On the page from zero, after the first song an IN PROGRESS panel lists each song with the next thing it is missing (`in_progress()`: no working audio -> Open the Rack; no link -> Create smart link; else Ready to publish), and after the first smart link "Nothing needs attention yet" becomes a real priority (`attention()`: publish the draft, else turn capture on; None when there is nothing real to say - an archived campaign says nothing). After the first fan or statement the account is operational by state_of and the operational page's own honesty devices carry source and freshness; "changes since last visit" already distinguishes first_visit and quiet, which is the spec's "meaningful comparison". tests/test_account_state.py holds the compass in both phases, in_progress per song, attention real-or-nothing, the page from zero transitioning after a song and a link, and the operational page carrying the compass with three priorities at most.

**Command palette (Ctrl+K)**
- THE BLOCKERS OF THE 2026-09-23 AUDIT. (1) THE RACK CAN CLOSE "OPEN THE RACK": the step counts a measurement only when it names a song, and the Rack never named one, so an account with the other four essentials stayed at 4 of 5 on the page from zero with every door sending it to a Rack that could not close the step (only a paid Release-Ready master could). /rack now takes ?track=<id> and carries a "Measuring for" select of the account's songs; rackdsp.js reportAnalysis sends the chosen song as track_id (and sends the same reading again when the song is chosen after measuring); /rack/analysis keeps only the account's own song ids. The In progress row's door is /rack?track=<id>&returnTo=/command-center&from=asset, so the Rack arrives attached to the song with no audio yet. (2) THE DEMO IS THE SHOWCASE, NEVER THE PAGE FROM ZERO: _account_state answers operational for a demo login by who it is (_session_is_demo / demo_accounts.is_demo_email), not by its rows - Start over empties the seeded statements until the next boot re-seeds them, and the Command Center used to fall to "0 of 5 essentials complete" while every room still showed its showcase. tests/test_account_state.py: test_the_rack_completes_its_own_step, test_a_measurement_filed_against_a_song_that_is_not_yours_counts_for_nothing, test_the_rack_picks_the_only_song_and_guesses_nothing_between_several, test_the_demo_is_the_showcase_even_after_start_over.

A keyboard jump list of every destination the account's sidebar offers.

- Because: hubs.command_index() derives the flat list from the same HUBS/LABEL/COMMUNITY/ACCOUNT definitions, and inject_hub_context filters it by page_switches, the demo lock, the team seat's rooms and the fan shell before handing it to base.html
- Routes: rendered into every signed-in page (no route)
- Files: hubs.py:369 command_index; hubs.py:362 PALETTE_WORDS; app.py:4495 _palette_for; app.py:4554 inject_hub_context; templates/base.html:873
- Access: Any signed-in account. A fan plan is cut down to COMMUNITY_GROUP plus hubs.FAN_ACCOUNT_KEYS.

**Create action from an alert**

Turns a Command Center alert, a release check, a catalog, score or royalty finding, or a preview page's reminder into a high-priority action that remembers where it came from, and confirms it on the page you were on.

- Because: the handler writes through cc.create_action into street_actions with the source the form names (alert, release_check, catalog_check, growth_score, trust_score, royalty_check, module) or, failing that, the one actions_center.source_for_path reads off the page it sits on; the room the form names, else the page's room, else the action type's room; the page as the way back; the release or campaign the release check names, kept only when it is this account's; and the person who pressed as the assignee. It redirects back to the referrer with ?action=<title>&action_id=<id>; partials/action_created.html adds "View action" only when that id is this account's saved action. An empty title is refused before any write (locked by tests/test_walk_command-tools_2026_09_20.py and tests/test_actions_center.py)
- Routes: /actions/from-alert (POST)
- Files: app.py:7005 action_from_alert; command_center.py:116 create_action; actions_center.py source_for_path; templates/command_center.html, templates/release_autopilot.html, templates/catalog.html, templates/qualification.html, templates/trust_score.html, templates/_real_royalty_band.html, templates/module_preview.html (the forms); templates/partials/action_created.html
- Access: /actions/from-alert shares the /actions prefix, so plans and team_areas treat it as /actions: artist tier, whole-account seats only (a partial-room seat pressing Create action on its own room's page is bounced; open question for the owner).

**Fan Room screen**

The Fans room opens on a dedicated screen of real fan counts, club members and open collab briefs instead of a plain card grid.

- Because: _fan_room reads the account's own mls.list_fans, store.get_fan_club/list_club_members and a live COUNT over collab_requests; the showcase account is branched to fan_audience.showcase_rows() and is labelled as such
- Routes: /room/fans (GET), /room/fans/new.csv (GET)
- Files: app.py:4664 _fan_room, app.py:4693 fan_room_new_csv, app.py:4655 _fan_room_rows; fan_room.py; fan_audience.py; templates/room_fans.html; db.py ml_fans, fan_clubs, club_members, collab_requests
- Access: As /room/<key>: no tier gate; a team seat needs the "fans" room. The banner image is a stand-in per the module.

**Growth Score (Qualification)**

Ten categories scored out of ten from the account's own campaigns, rollouts, fans, catalog, EPK and link traffic.

- Because: qualification.calculate reads links_store, rollout_store, db catalog/EPK/pulse tables and records the day's reading itself; score_history.summarise then draws the trend from score_history rows
- Routes: /qualification (GET)
- Files: app.py:9992 qualification_page; qualification.py:1; score_history.py:26 KINDS; db.py record_score/score_trend; templates/qualification.html; db.py:424 score_history
- Access: artist tier (in plans._ARTIST_PATHS as /qualification); a fan plan got 402. Team seats need the "analytics" room (team_areas maps /qualification to analytics). Sidebar key is "scores".

**Hub sidebar and hub desk landings**

Five hubs (Command, Studio & Assets, Launch Engine, Live Stage Suite, Royalty Sweep & Banking) each with a landing page of live micro-dashboards.

- Because: hubs.nav_hubs() is the single definition the sidebar, the rooms, the palette and /desk/<hub> all read; the Command desk's tiles call qualification.calculate, trust_score.calculate, cc.open_actions and insights_engine.build_insights on the signed-in account; probed /desk/command and /desk/studio at 200
- Routes: /desk/<hub_key> (GET); the sidebar renders on every signed-in page
- Files: app.py:4729 hub_desk; app.py:4554 inject_hub_context; hubs.py:9 HUBS, :194 live_keys, :429 nav_hubs, :406 get_hub; templates/hub_desk.html; templates/base.html
- Access: Any signed-in account — /desk/<hub> has no tier gate and is not in team_areas.WHOLE_ACCOUNT, so a fan-plan account opened /desk/command at 200 in the probe and got its Growth and Trust scores computed. An unknown hub key aborts 404.

**Insights**

Rule-based observations over the account's money, promo, fans, growth, catalog hygiene and link click split.

- Because: insights_engine.build_insights is pure rules over store.get_statement_rows, royalty_types.type_report, mls.list_campaigns/event_counts/breakdown/list_fans, store.list_pulse_snapshots and get_catalog_tracks; nothing is generated and an account with no data gets the single "No income data yet" starter insight
- Routes: /insights (GET); the top two also appear on /desk/command
- Files: app.py:11371 insights; insights_engine.py:21 build_insights; templates/insights.html
- Access: artist tier (/insights is in plans._ARTIST_PATHS); a fan plan got 402. Team seats need the "analytics" room.

**Notification preferences**

Ticks which kinds of notification the account wants; an unticked kind is dropped before it is written.

- Because: the POST stores the unticked kinds in notification_mutes via store.set_muted_kinds, and db.notify checks that table and returns before inserting
- Routes: /settings/notifications (POST); the form is on /settings
- Files: app.py:13287 settings_notifications; db.py:5022 muted_kinds, :5031 set_muted_kinds, :5038 notify; db.py:767 notification_mutes; templates/settings.html
- Access: Any signed-in account. /settings is in _TEAM_BLOCKED, so a team seat cannot reach the form.

**Notifications**

The account's own notification feed, with per-item dismiss and a clear-all.

- Because: store.list_notifications/mark_notifications_read/delete_notification/clear_notifications all work on the notifications table scoped by user_id, the DELETE is scoped in SQL so a guessed id removes nothing, and ~55 non-test call sites write into it (app.py, tour_os.py, board.py, press_desk.py, release_ready.py, hypeddit_ingest.py, contract_reminders.py)
- Routes: /notifications (GET), /notifications/<int:id>/dismiss (POST), /notifications/clear (POST)
- Files: app.py:12714 notifications, :12733 notification_dismiss, :12744 notifications_clear; db.py:5038 notify, :5049 list_notifications, :5065 mark_notifications_read; templates/notifications_real.html; db.py:772 notifications
- Access: No tier gate — a fan plan opened it at 200. /notifications is in team_areas.WHOLE_ACCOUNT, so a partial-room seat is bounced; a seat also does not clear the unread badge (the mark-read is skipped when session team_as is set).

**Operator Desk Files page**  *(status corrected on review)*

The old files index; it now sends an old bookmark to the dashboard.

- Because: The orphan template claim holds (grep for desk/files.html across .py/.html/.js finds only the file itself), but the ROUTE is not dead. url_for("desk.files") is called from three live code paths in C:/Users/17049/OneDrive/Desktop/claude/music/mah-login/operator_desk.py — :461 (file_upload bails on an empty upload), :478 (file_upload success fallback when there is no lead_id), :499 (file_delete fallback when the form carries no `back`). Deleting the route would raise a BuildError in each. It is also pinned by two tests: tests/test_operator_desk.py:139-143 (RETIRED_PAGES = ["/files","/meetings","/agents"], asserting 302 to the dashboard) and tests/test_no_way_out_round_two.py:101-102. Correct status is Live — a retired-page redirect that live handlers target; only templates/desk/files.html is genuinely dead.
- Routes: /operator-desk/files (GET, 302)
- Files: operator_desk.py:444 files; templates/desk/files.html (orphan); desk_store.py desk_files table
- Access: Desk seat with view (the decorator still runs before the redirect).

**Push an artist to the Operator Desk**

Creates or finds a Desk lead for a Signal artist, attaches the score snapshot, writes a first note and a follow-up task and starts watching.

- Because: the handler imports desk_store and writes a real lead plus note and task, records the link in signal_desk_links and adds the artist to a watchlist; when the person holds no Desk seat it still does the Signal-side work and sends them back to the artist page instead of to a 403
- Routes: /signal/artist/<id>/operator-desk (POST)
- Files: signal_hub.py:548 to_desk, :638 _has_desk_seat; signal_store.py signal_desk_links, :1098 list_desk_links; desk_store.py create_lead/add_note/add_task
- Access: Signal seat with "push_to_desk": owner, admin, anr, scout.

**Rooms (the eight-room layout)**

Eight room screens — Fans, Studio, Stage, Analytics, Business, Publishing, Releases, Marketing — each a grid of feature cards.

- Because: rooms.build composes cards from the same hubs definitions the sidebar uses and applies page_switches, the demo lock and LABEL_ONLY; /room/analytics probed 200 and an unknown key aborts 404
- Routes: /room/<room_key> (GET)
- Files: app.py:4636 room_screen; rooms.py:23 ROOMS, :241 build, :296 get_room; templates/room.html; hubs.py (card definitions); page_switches.py
- Access: No tier gate — plans.required_tier("/room/analytics") is None, and a fan-plan account opened /room/analytics and /room/fans at 200 in the probe even though every card behind them answers 402. Label-only cards (services, roster, submit, apparel) need plan == "label". A team seat may open only /room/<key> for a room it was ticked (team_areas.allows). The sidebar only draws rooms when rooms.enabled() (owner's nav_layout kv, or NAV_ROOMS); the routes answer either way.

**Royalty goal**

Saves the account's royalty target so the ring on the money band reads a number the artist set.

- Because: POST writes store.set_royalty_goal / clear_royalty_goal into royalty_goals, and _front_money_context reads it back for non-showcase accounts; finite/positive/<=1e9 validation is in the handler
- Routes: /overview/goal (POST)
- Files: app.py:2521 overview_goal; db.py royalty_goals table (db.py:760); templates/_front_money.html
- Access: Any signed-in account whose plan clears the /overview artist gate; whole-account for team seats (/overview is in WHOLE_ACCOUNT).

**Score history and trend**

One row per score per day so Growth, Trust, Capital Readiness and the catalog valuation can show a direction.

- Because: db.record_score upserts on (user_id, kind, day) into score_history and score_history.summarise computes the delta only when two readings exist; the Command Center also writes the valuation reading from build_alerts inside a try/except so a history write can never break the page
- Routes: no route of its own; read by /qualification, /trust-score and /capital-score
- Files: score_history.py:26 KINDS, summarise; db.py record_score/score_trend; command_center.py:255 (valuation write); db.py:424 score_history
- Access: Follows whichever page reads it.

**Sidebar layout switch (rooms vs hubs)**

The owner flips the whole deployment's sidebar between the eight rooms and the five hubs.

- Because: the POST writes rooms.set_layout into the app_kv key nav_layout and rooms.enabled() reads it before falling back to NAV_ROOMS; guarded by _owner_or_404
- Routes: /admin/nav-layout (POST)
- Files: app.py:4707 admin_nav_layout; rooms.py:131 enabled, :144 set_layout; db.py app_kv; templates/settings.html
- Access: Owner only — _owner_or_404 (app.py:10126) 404s anybody whose email is not in _OWNER_EMAIL_HASHES or OWNER_EMAILS, and also 404s a team seat. /admin is in _TEAM_BLOCKED.

**Signal alerts**

Threshold rules over watched artists that raise in-app alerts, evaluated on the dashboard sweep and when the page is opened.

- Because: create/delete_alert_rule persist to signal_alert_rules and ingest.evaluate_alerts reads this org's rules against this org's watch items and writes signal_alerts; opening the page marks them read and the dashboard shows the unread count
- Routes: /signal/alerts (GET), /signal/alerts/rules (POST), /signal/alerts/rules/<id>/delete (POST)
- Files: signal_hub.py:750 alerts, :761 alert_rule_add, :771 alert_rule_delete; signal_ingest.py:258 evaluate_alerts; signal_store.py signal_alert_rules, signal_alerts, :1035 unread_alert_count; templates/signal/alerts.html
- Access: Reading needs "view"; rule writes need "alert_edit" — owner, admin, anr. The rule form carries a channel field but only in_app alerts are written; no email or webhook path exists in this module.

**Signal board CSV export**

Exports the board being read, with its filters and the score version, as a CSV.

- Because: the handler re-applies BOARD_RULES and _board_filter from the same table the page uses and only falls back to the whole universe when no board is named; probed /signal/export/board.csv?board=breaking at 200
- Routes: /signal/export/board.csv (GET, ?board=&mandate=)
- Files: signal_hub.py:1054 export_board, :234 _board_rows, :246 _board_filter; signal_scoring.SCORE_VERSION
- Access: Signal seat with "view" (any role) — export is not restricted the way the Operator Desk's CSV is.

**Signal data sources admin**

Adapter health, per-vendor probe, usage and failure history, freshness, artist lookup, manual add, force refresh and retire-the-demo.

- Because: the page reads registry().health(), signal_store.provider_usage/provider_failures/data_freshness (all built from real signal_provider_runs rows), and the probe button makes one real vendor call distinct from the environment read; retire-demo is refused while no real artist exists rather than emptying the product
- Routes: /signal/admin/data-sources (GET), /signal/admin/probe/<key> (POST JSON), /signal/admin/refresh (POST), /signal/admin/find (GET), /signal/admin/add (POST), /signal/admin/retire-demo (POST)
- Files: signal_hub.py:817 _render_data_sources, :841 data_sources, :847 admin_probe, :865 admin_refresh, :872 admin_find, :904 admin_add, :916 admin_retire_demo, :780 _own_act_names; signal_providers.py:3448 ProviderRegistry; signal_store.py:1114 record_provider_run, :1134 provider_usage, :1151 provider_failures, :1184 data_freshness; soundcharts_budget.py:85 summary; templates/signal/data_sources.html
- Access: Signal seat with "provider_admin": owner and admin only.

**Signal mandates**

Named search criteria (genre, listener ceiling, momentum and gap floors) that filter the Deal Ready board and get their own match/miss page.

- Because: create/update/delete_mandate persist to signal_mandates keyed by id, _mandate_match evaluates the stored criteria against board rows and returns reasons and misses, and pausing uses the same row rather than delete-and-recreate so referencing links survive
- Routes: /signal/mandates (GET, POST), /signal/mandates/<id> (GET), /signal/mandates/<id>/edit (POST), /signal/mandates/<id>/active (POST), /signal/mandates/<id>/delete (POST)
- Files: signal_hub.py:384 _mandate_match, :654 _mandate_criteria, :673 mandates, :687 mandate_edit, :706 mandate_active, :723 mandate_delete, :730 mandate_detail; signal_store.py signal_mandates; templates/signal/mandates.html, mandate.html
- Access: Reading needs "view"; every write needs "mandate_edit" — owner, admin, anr only (the GET/POST page re-checks with can() and aborts 403).

**Signal team roster**

Add, re-role and remove Signal seats, mirroring the Operator Desk roster on every view.

- Because: upsert_member/set_member_role/remove_member write signal_members and sync_desk_roster mirrors desk_users into the default org on each GET; the POST re-checks manage_members and aborts 403
- Routes: /signal/team (GET, POST)
- Files: signal_hub.py:929 team; signal_store.py:36 ROLES, :48 PERMS, :60 DESK_ROLE_MAP, :457 sync_desk_roster, :480 can; templates/signal/team.html
- Access: "view" to read; "manage_members" (owner role only) to write.

**Signal watchlists**

Put an artist on a named watchlist with the momentum score as it stood, and take them off.

- Because: ensure_watchlist/add_to_watchlist/remove_watch_item write signal_watchlists and signal_watch_items scoped to the org, and the stored score and version are what makes the later "was Signal right" question answerable
- Routes: /signal/watchlists (GET), /signal/artist/<id>/watch (POST), /signal/watchlists/<item_id>/remove (POST)
- Files: signal_hub.py:518 watch, :533 watchlists, :541 watch_remove; signal_store.py signal_watchlists, signal_watch_items; templates/signal/watchlists.html
- Access: Signal seat with "watch": owner, admin, anr, scout, analyst. Viewer and deal roles are refused.

**Start-here checklist (first run)**

A five-step checklist on the Command Center that is ticked from what the account actually holds, and retires itself.

- Because: _firstrun_panel builds every flag from a real query (get_epk, list_os_tracks, statement_titles, get_db_links, list_campaigns, get_rack_preset, list_hours_rates) and firstrun.build drops any step this plan cannot open; no dismissed-onboarding bit exists anywhere
- Routes: rendered inside /command-center (no route of its own)
- Files: app.py:2383 _firstrun_panel; firstrun.py:30 STEPS, :62 build; templates/command_center.html:104
- Access: Rendered for any signed-in non-fan account on the Command Center; it is suppressed when tutor mode is on. Steps are filtered by plans.allowed and plans.suite_open so it never points at a locked door.

**Today's Priorities (derived health alerts)**

Alerts computed live from campaigns, statements and catalog gaps, each with a destination and a create-action button.

- Because: command_center.build_alerts reads links_store.list_campaigns/get_destinations, statements_engine.build_royalty_summary over real statement rows and store.get_catalog_tracks; no seeded list anywhere in the function
- Routes: /command-center, /overview
- Files: command_center.py:212 build_alerts; command_center.py:300 mls_catalog_tracks; statements_engine.build_royalty_summary; templates/command_center.html:267
- Access: As the Command Center (artist tier; whole-account for team seats).

**Trust Score**

One partner-facing readiness number from ten factors, each naming its fix when it is a blocker.

- Because: trust_score.calculate reads catalog tracks, signed split deals, statements, unsuppressed consented fans, campaigns and pulse snapshots, records itself into score_history, and returns 0 rather than raising for a factor that was never measured
- Routes: /trust-score (GET)
- Files: app.py:9694 trust_score_page; trust_score.py:1; score_history.py; templates/trust_score.html; db.py:424 score_history
- Access: artist tier (/trust-score is in plans._ARTIST_PATHS); a fan plan got 402. Team seats need the "analytics" room.

**Tutor mode**

An opt-in four-stage walkthrough of the whole desk that replaces the start-here checklist while it is on.

- Because: the toggle sets a year-long sb_tutor cookie and _tutor_panel derives every step from real queries; tutor.build filters steps by plans.allowed; a back value that is not a single-slash local path is replaced with /command-center
- Routes: /tutor/toggle (POST); the panel renders on /command-center
- Files: app.py:2315 _tutor_panel, app.py:2363 tutor_toggle; tutor.py:40 STAGES, tutor.build; templates/command_center.html:12
- Access: Any signed-in account that can open the Command Center. The choice lives in a cookie, not on the account, so it does not follow the person to another browser. /tutor is listed in team_areas.WHOLE_ACCOUNT but no /tutor route exists — only /tutor/toggle.

**What changed since your last visit**

Counts only the rows created since the previous visit stamp, and says so when there is no window yet.

- Because: since_engine.build runs one real query per kind against the account's tables and db.roll_seen/get_prev_seen stamp the visit; the module header records that the old version was five constants in royalty_data
- Routes: /command-center, /overview (inside _front_money_context)
- Files: app.py:2472 _front_money_context; since_engine.py:34 build; db.py roll_seen/get_prev_seen; templates/_front_money.html
- Access: As the Command Center. Skipped entirely for the showcase account and for a session with team_as set (the visit stamp is not rolled for a seat).

### Partial

**Analytics Room (/room/analytics)**

The Analytics room's opening screen: three figures, the five-step measurement path, the instrument readings with their providers and dates, the line over time, the observations, and three closing tiles.

- Because: nothing on this screen is read live from a provider - it shows what is ON FILE and says how old it is, because a room door is opened constantly and /pulse already spends and caches the provider calls (tests/test_analytics_room.py asserts spotify_provider.artist_pulse is never called). Every figure is a local read: link visits are links_store.account_event_counts (ml_events page_view joined to this account's ml_campaigns), followers are the newest NON-NULL reading in pulse_snapshots, the path counts pulse_snapshots, pulse_peers and insights_engine observations, and the observations are insights_engine.build_insights, the one feature in this room with no demo branch and no hardcoded figure. A null reading is skipped rather than read as 0 throughout - analytics_room.latest(), chart() - because the snapshot columns were made nullable precisely to stop a provider's "0 for a field it stopped counting" standing in as a following of nobody. A figure nobody measured reads "Not measured" in words AND names the provider that would supply it; a 0 is printed as a measurement, because somebody counted. A reading older than a day says how old instead of passing as current. The line refuses to draw until two readings exist on DIFFERENT days, so one afternoon's two snapshots are one day of history.
- Room shape: six cards became three tiles. Pulse opens the room and Insights is the right-hand panel, so neither is a card any more; trust-score folded into the scores tile because rooms.py already gives both the same parent and they are two tabs of one page. All four keep their own addresses. Income is deliberately absent (owner, 2026-09-22: "let analytics stay about measurements") - royalties live in the Business room and a panel here would put the same figures in a second room.
- THE PLATE (owner, 2026-09-23: every room on the shorter three-window plate): the working page draws the rooms' shared plate, templates/partials/cc_rack.html on static/img/room-plate.webp, the same one as the page from zero. Its three screens are analytics_room.rack_screens() over figures(), in RACK_ORDER: Link visits, Followers, Monthly listeners. The shared plate prints no names, so each screen carries its label; a reading is set as a figure (cz-screen-v--fig), an absence stays the words "Not measured" (cz-screen-v--none), never a 0, and the line under each is what the old window printed there - its source ("From your smart links", "From the connected provider") or, unmeasured, what would fill it ("No smart links tracked yet", "Spotify stopped returning this", "Needs a metrics provider"). No change arrow: the room keeps no prior period for these three and does not invent one. THE TREND, which had the old analyser's long upper screen, is its own panel directly under the plate and its foot line (section.rk-panel.an-trend, styled in analytics-room.css): the polyline over every reading on file on the MEASURED range, with the axis printed (analytics_room.chart()'s "axis": highest and lowest reading, first and last day), "Read by Spotify" said only over a drawn line, and with one reading - or two from one afternoon - the glass gives the reason in words instead. The old four-window TREND ANALYSER (static/img/analytics-plate.webp, 1859x846, analytics_room.PLATE/box()/plate_windows()) is retired from the page and the module; the image stays on disk. The standby reel that filled an unmeasured window (standby(), STANDBY_FILL) went with it. LINK VISITS now sums BOTH event spellings - page_view and the legacy pageview - because counting one made this room disagree with Artist Pulse, the page its own head band sends you to, about the same number.
- The page from zero (owner's Analytics spec + mockup, 2026-09-23): an account with nothing connected (no pinned artist), nothing synced (no snapshot), no link event and no peer meets an onboarding page rather than an empty analyser, in the spec's order - the header (subtitle "Turn connected data into clear next moves.", primary "Connect your first source" -> /connections with returnTo=/room/analytics?from=connect), the Command Center's photographed three-screen plate drawn STATIC with PURPOSE / START HERE / GOOD TO KNOW (green is information, never a button; no rotation), "Start with a trusted source" with the "Connect your first data source" card ("View connections") beside "What Analytics will organize" - the four lenses, each a door to the room that owns the next step (Audience signals -> Fans, Release performance -> Releases, Live results -> Stage, Revenue insights -> Business; words, not a door, for a seat that cannot open that room), the five-step workflow as education with Connect lit and no percentage, "Your insights will appear here" (links: coverage explained by the language panel on the page; supported sources = Connections) beside "Nothing is measured yet", help, and the tools under "More Analytics tools" - a drawer that starts OPEN (owner's ruling the same day). No chart frame, no date filter, no comparison, no export, no nought. The room says "Your first source is connected. Analytics will show what it measures once the first sync has finished." only when a source is really on file (analytics_room.done_line). The state is read from every count the spec names in ONE try (profile, snapshots, peers, link event counts); a failed read is templates/room_analytics_error.html at 503 ("We could not load Analytics", Try again / Review connections), never a fresh account - the old per-read fallbacks that turned a failure into empty values are gone; the observations keep their own fallback because one section's failure must not block the room. A seat without edit access gets the card without its door and a line saying who connects sources. One source, reading or visit and the populated analyser returns untouched. The animated standby that ran on the analyser for an empty account is retired on this room, and since 2026-09-23 the fill reel is too: an unmeasured screen on the working page says so in words. The owner's mark on a page they hid (page_switches) stays on the drawer's tile from zero - the "Hidden" pill in the room's own status classes - because rooms.build keeps that card for the owner alone; the seven rooms dropped the state on the way to their zero drawers until 2026-09-23 (the Marketing room had it from the start), and the populated Studio, Stage, Analytics, Business and Releases rooms, whose tile feet were empty, show the same pill from the same day.
- THE SHOWCASE (owner's ruling: the demo account is the showcase, never the page from zero; audit analytics-2, 2026-09-23): every demo login (demo_accounts.ACCOUNTS, read by _session_is_demo()) gets analytics_room.showcase() - an in-memory example, nothing written to the database, the route alone deciding who is shown it, as marketing_room.showcase() does - and zero=(not showcase) and new_account(...), so a demo login is never the page from zero. Before this no demo login had a pin, a reading or a peer, and all of them met "Start with a trusted source" under a "Sample data" lamp with no sample on the page. The example: 12,480 link visits (the Marketing example's figure), fourteen daily readings of followers and monthly listeners credited to "Sample provider" (analytics_room.SHOWCASE_SOURCE: never a real vendor's name beside an invented figure), three peers; Spotify's own snapshots stay empty, as they are for real accounts. The observations are still the demo account's own insights_engine reading. The "Sample data" lamp is drawn only over the example's readings, never on the page from zero, and the example's header offers "Open Artist Pulse" instead of Change artist / Pin your artist: the example's artist is not the demo's pin, so a shared demo is offered no write door. build() takes those readings as `metrics` ({label, followers, monthly_listeners, as_of, snapshots}); each reading it supplies is credited to its label with its own day, the path counts its snapshots, and the trend draws its followers when Spotify's snapshots carry none. The done line is still decided by the account's own saved source, never by the example.
- Routes: GET /room/analytics (dispatched from /room/<room_key>)
- Files: app.py room_screen() -> app.py _analytics_room(); analytics_room.py STEPS, RACK_ORDER, SHOWCASE_SOURCE, showcase(), days_measured(), latest(), reading(), figures(), rack_screens(), path(), chart(), new_account(), done_line(), zero_page(), build(); templates/room_analytics_error.html; templates/partials/cc_rack.html + static/css/command-zero.css + static/img/room-plate.webp (the owner's shorter three-window plate, 2026-09-23) (the page from zero AND the working page); templates/room_analytics.html; static/css/analytics-room.css; rooms.py ROOMS["analytics"]; engines insights_engine.py; stores db.py (pulse_snapshots, pulse_profiles, pulse_peers), links_store.py (ml_events, ml_campaigns)
- Access: Any signed-in account, as /room/<key>: no tier gate. Team seats need the "analytics" room ticked; a tile whose page the seat cannot open is dropped. Anonymous redirected to /login.

**Artist Pulse**

Live Spotify followers and popularity, Deezer fans, monthly listeners, a YouTube panel, peers and the account's own link engagement.

- Because: the owned-engagement tile and the stored snapshot history are real with no key at all (counted from the account's own ml_events, summing both the page_view/service_click and the older pageview/click spellings), but the Spotify, Deezer, monthly-listener, "everything" and YouTube panels only carry numbers when SPOTIFY_CLIENT_ID/SECRET, a CAP_METRICS provider and YOUTUBE_API_KEY are set — otherwise they render "Not measured" rather than 0
- Routes: /pulse (GET); /stats (GET, 301-style redirect to /pulse#engagement)
- Files: app.py:9707 pulse_page; app.py:12341 stats; pulse_signals.py:1 build; pulse_everything.py:1 build; spotify_provider.py:133 pulse_configured; music_apis.py:225 deezer_artist_fans; templates/pulse.html, templates/_pulse_everything.html; db.py pulse_profiles, pulse_snapshots, pulse_peers, pulse_peer_snapshots
- Access: artist tier (/pulse is in plans._ARTIST_PATHS); a fan plan got 402. Team seats need the "analytics" room. Changing the pinned artist once one is set additionally needs Pro/Label or an owner email (_pulse_change_allowed, app.py:9876), which answers 402 otherwise.

**Ask Signal**

A natural-language box that parses a query into visible filters and lists what it could not support.

- Because: the parser is deterministic regex with no model call and applies only filters Signal can really apply, and the eight unsupported phrases (tiktok, shazam, ticketing, merch, playlist, manager, producer, songwriter) are listed rather than silently dropped — but the rows it filters are whatever is in the universe, which is the mock's fiction until a real provider is configured
- Routes: /signal/ask (GET, ?q=)
- Files: signal_hub.py:954 ask, :983 _parse_ask, :1031 _ask_match; templates/signal/ask.html
- Access: Signal seat with "view" (any role).

**Global search**

Finds pages by name, and the account's own statement tracks, sources and disputes.

- Because: page_hits and the track/source/dispute searches read this account's real pages and statement_rows/disputes, but when the signed-in email is a demo email search_config._demo_search adds royalty_data._SONGS, the hard-coded platform catalog, get_claims() and disputes_config seeds as if they were records
- Routes: /search (GET, ?q=)
- Files: app.py:12703 search_route; app.py:12650 _search_pages; app.py:12646 _PAGE_ALIASES; search_config.py:24 page_hits, :59 _demo_search, :106 search; templates/search.html
- Access: No tier gate (required_tier returns None) but the handler has no login check of its own — plan_gate sends an anonymous request to /login first. A fan plan opened it at 200. /search is in team_areas.WHOLE_ACCOUNT, so a partial-room seat is bounced.

**Money band on the Command Center (the old Overview)**

Total collected, monthly trend, goal ring, money-left-on-the-table and the recovery view, at the top of the Command Center.

- Because: for a real account every figure comes from that account's statement_rows (_real_royalty, recovery_engine.build, store.get_royalty_goal); when _session_is_demo() is true the same band is fed royalty_data's hard-coded get_platform_balances()/get_earnings_trend() and the $25,000 goal instead
- Routes: /command-center, /overview (rendered by _front_money_context)
- Files: app.py:2472 _front_money_context; app.py:2302 _real_royalty; app.py:361 _session_is_demo; templates/_front_money.html; since_engine.py; recovery_engine.py; royalty_data.py (showcase seed)
- Access: Same as the Command Center: artist tier and above, whole-account for team seats.

**Operator Desk**

The internal A&R workspace: leads, notes, tasks, follow-ups, shows and meetings, deals, team and an audit log.

- Because: every page reads and writes its own desk_* tables and probed 200 for an owner, but desk_store.seed_if_empty() plants five clearly-labelled "(sample)" leads and three team names into an empty database on every boot, so a fresh deployment's Leads board and dashboard counts are seeded rather than empty
- Routes: /operator-desk (GET), /operator-desk/leads(+/new, /<id>, /<id>/edit, /<id>/stage, /<id>/follow-up, /<id>/delete, /<id>/notes, /<id>/deals, /<id>/files), /operator-desk/notes/<id>/pin, /operator-desk/tasks(+/<id>/status), /operator-desk/follow-ups, /operator-desk/events, /operator-desk/deals(+/<id>/status), /operator-desk/team, /operator-desk/activity, /operator-desk/export/leads.csv, /operator-desk/files/upload, /files/<id>/download, /files/<id>/delete, /admin (alias)
- Files: operator_desk.py:48 bp, :95 require, :184 dashboard, :200 leads, :331 tasks, :368 follow_ups, :378 events, :408 deals, :444 files, :524 team, :581 activity, :588 export_leads, :612 init; desk_store.py (tables at :145-:240, :850 dashboard_counts, :902 warnings, :936 seed_if_empty); templates/desk/*; registered from app.py:14425
- Access: Not plan-gated at all. Access is a row in desk_users with status active, or an owner email (_is_owner_email auto-provisions an owner seat on first visit). A signed-in account with no seat gets desk/denied.html and 403 (verified). Roles owner/admin/member/viewer with operator_desk.PERMS; delete, export, audit and manage_users are owner-only; a member may edit only leads assigned to their name. /operator-desk and /admin are both in app.py _TEAM_BLOCKED, so a team seat is redirected. /admin 404s a signed-in login with no desk seat (verified).

**Pulse artist picker**

Search Spotify for the artist to track, pin one, or clear the pin.

- Because: /pulse/select and /pulse/clear write and delete pulse_profiles for real with no external call, but /pulse/search needs SPOTIFY_CLIENT_ID/SECRET and returns an honest refusal without them
- Routes: /pulse/search (GET), /pulse/select (POST JSON), /pulse/clear (POST)
- Files: app.py:9858 pulse_search, :9881 pulse_select, :9949 pulse_clear; spotify_provider.py; db.py pulse_profiles
- Access: Signed in (401 JSON otherwise). Re-pinning a different artist needs Pro/Label or owner (402 with _PULSE_LOCKED).

**Pulse peers**

Pin other artists and snapshot their public Spotify numbers alongside your own.

- Because: the peer list and its snapshot history are real rows in pulse_peers/pulse_peer_snapshots, but every live reading comes from spotify.artist_pulse and is left None when pulse_configured() is false
- Routes: /pulse/peer/add (POST), /pulse/peer/<artist_id>/remove (POST)
- Files: app.py:9828 pulse_peer_add, :9850 pulse_peer_remove; app.py:9749-9770 (peer block in pulse_page); db.py pulse_peers, pulse_peer_snapshots
- Access: As /pulse (artist tier; analytics room for a seat).

**Signal Audio Briefs**  *(status corrected on review)*

Spoken weekly briefs from the org's alerts; retired from the menu on 2026-09-19.

- Because: The two orphan templates are real (no render_template for signal/briefs.html or signal/brief.html anywhere), and /signal/briefs and /signal/briefs/<id> are bare redirects. But the rest is live, referenced code: C:/Users/17049/OneDrive/Desktop/claude/music/mah-login/audio_signal.py:100 and :147 call url_for("signal.brief_detail") and :196 calls url_for("signal.briefs_index"), so both "retired" endpoints are live url_for targets. tests/test_audio_briefs.py exercises the whole pipeline end to end — :111 POSTs /signal/briefs/new and asserts the real alert text lands in the script, :138-141 asserts /speak then /audio returns a well-formed RIFF/WAV, :161-168 asserts a second render is not dispatched, :180-188 asserts tenancy refusals, :194 asserts 404 when SIGNAL_AUDIO_BRIEFS_ENABLED is unset. Working, test-covered code with no rendered door is Partial, not Dead code.
- Routes: /signal/briefs (GET, 302), /signal/briefs/<id> (GET, 302), /signal/briefs/new (POST), /signal/briefs/<id>/speak (POST), /signal/briefs/<id>/audio (GET), /signal/briefs/<id>/delete (POST)
- Files: audio_signal.py:58 register, :70 briefs_index, :75 brief_new, :102 brief_detail, :108 brief_speak, :149 brief_audio, :176 brief_delete; audio_briefs.py; templates/signal/briefs.html, brief.html (orphans)
- Access: Signal seat with "view", plus the audio policy gate (_audio_on) which 404s when audio is off. Belongs to the audio area; listed here because the routes live on the Signal blueprint.

**Signal provider adapters**

The pluggable sources Signal (and Pulse) read artists, metrics, releases, cities, events and rights from.

- Because: MusicBrainz, Discogs, YouTube, Soundcharts, Songstats, MLC, Bandsintown and the first-party TourDates adapter all carry real HTTP or first-party implementations, but ChartmetricAdapter (signal_providers.py:1592), SoundExchangeAdapter (:3107) and SpotifyMetadataAdapter (:3115) declare capabilities and env keys and implement no methods at all, so if they were ever configured every call would raise the base class's NotImplementedError
- Routes: no routes of their own; read by /signal/*, /pulse and /fingerprints-adjacent pages
- Files: signal_providers.py:95 MusicIntelligenceProvider, :178 _EnvProvider, :289 SoundchartsAdapter, :1217 SongstatsAdapter, :1592 ChartmetricAdapter, :1601 MusicBrainzAdapter, :1773 DiscogsAdapter, :2246 YouTubeAdapter, :2736 BandsintownAdapter, :2790 TourDatesAdapter, :2884 MLCAdapter, :3107 SoundExchangeAdapter, :3115 SpotifyMetadataAdapter, :3123 PublicWebResearchAdapter, :3134 InternalStreetBankerAdapter, :3180 MockMusicIntelligenceAdapter, :3448 ProviderRegistry
- Access: Server-side only; reached through /signal/admin/data-sources (provider_admin) and indirectly by /pulse.

**The Operating System board (module registry)**

A board of 33 windows for the app's modules, grouped by the hub each one sits in, each lamped live or preview.

- Because: 28 of the 33 rows point at real pages and are lamped live, but 5 are lamped preview and their routes are generated stub pages (see next entry); the list itself is a hand-maintained literal, so the lamp is a claim in command_center.py rather than a measurement of the page
- Routes: rendered inside /command-center and /overview
- Files: command_center.py:96 MODULES; command_center.py:147 module_groups; command_center.py:132 MODULE_BY_ROUTE; templates/command_center.html:343; hubs.py HUBS (group order)
- Access: As the Command Center. Note the board does not filter by plan or by page_switches, so an artist sees a window for /roster (Label-only) and for the preview routes.

### Stubbed

**ACRCloud Fingerprints desk**

Register the account's masters into an ACRCloud bucket and scan a long recording for them.

- Because: the page, the registration list and the scan list all read real acr_* rows scoped by user_id, but every action first checks acr_console.configured() — which needs ACRCLOUD_CONSOLE_TOKEN and refuses while sandbox.active() — and without it register, scan and refresh each write nothing and set a one-shot session notice saying so; _console_state also keeps a failed bucket call apart from an empty bucket list. With the token present it is a real vendor integration (buckets, upload_audio, scan_file, scan_results)
- Routes: /fingerprints/ (GET), /fingerprints/register (POST), /fingerprints/scans (POST), /fingerprints/scans/<scan_id> (GET), /fingerprints/scans/<scan_id>/refresh (POST)
- Files: acr_desk.py:55 bp, :144 _console_state, :168 index, :188 register, :256 new_scan, :297 scan, :320 refresh, :351 init; acr_console.py:143 configured, :312 buckets, :352 upload_audio, :398 containers, :422 scan_file, :484 scan_results; acr_store.py:39 init_acr (tables at :48, :72, :93); templates/acr/index.html, acr/scan.html; registered from app.py:14515
- Access: plans.required_tier("/fingerprints") = "artist" (it sits in plans._PRO_PATHS, which maps to artist) — a fan plan got 402, an artist plan 200. Within the account: a login with no partner seat is its own owner and may act; a login holding a partner seat may only press buttons when its role carries partner_store "act_as_artist", enforced by acr_desk._require_act (403), not just hidden in the template. Team seats need the "publishing" room (team_areas maps /fingerprints there). There is no scheduler — every call happens because somebody pressed a button.

**Preview module pages**

Five addresses that answer with a generic "this module is in preview" page listing what it will do.

- Because: app.py:8641 _module_preview builds one view per MODULES row whose status is "preview" and renders module_preview.html with a hard-coded bullet list from command_center.PREVIEW_FEATURES; probed all five at 200 and the body is the stub, with no account data read
- Routes: /royalty-recovery/mlc, /fraud-sentinel, /ai-rights, /opportunities, /voice-of-fan (all GET)
- Files: app.py:8641 _module_preview and the add_url_rule loop at app.py:8651; command_center.py:185 PREVIEW_FEATURES; templates/module_preview.html
- Access: Any signed-in account (no tier gate on these paths; required_tier returns None for all five). /opportunities is in team_areas.WHOLE_ACCOUNT so it is shut to a partial-room seat; the other four are not.

**Pulse YouTube panel**

Subscriber and view counts for a channel the account owner names by handle or URL.

- Because: every path first asks _youtube_adapter().configured(), which is the signal_providers YouTubeAdapter needing YOUTUBE_ENABLED and YOUTUBE_API_KEY; without them the search returns an error string and the save redirects with ?yt=unconfigured, and the panel renders "Not measured". It never derives a channel from the artist name
- Routes: /pulse/youtube (POST), /pulse/youtube/search (GET)
- Files: app.py:9898 pulse_youtube_search, :9918 pulse_youtube, :3545 _youtube_adapter, :3559 _youtube_pulse; signal_providers.py:2246 YouTubeAdapter; db.py save_pulse_youtube_channel
- Access: As /pulse.

**Signal**

The internal A&R discovery engine: boards of artists scored for momentum, distribution gap, rights health and deal readiness.

- Because: with no real adapter configured ProviderRegistry.is_demo() is true and signal_ingest.ensure_universe seeds 25 deterministic fictional artists from MockMusicIntelligenceAdapter (signal_providers.py:3180) — that is what a fresh deployment shows, labelled by the demo_mode/demo_universe banners. The moment any real adapter is configured the mock stands down for every capability and uncovered capabilities become "not measured" rather than invented, at which point the boards are Live
- Routes: /signal, /signal/ (GET); /signal/breaking, /signal/early, /signal/cities, /signal/undervalued, /signal/deal-ready (GET); /signal/artist/<id> (GET); /signal/artist/<id>/score/<key> (GET)
- Files: signal_hub.py:36 bp, :76 require, :289 dashboard, :308 breaking, :319 early, :332 cities, :355 undervalued, :366 deal_ready, :413 artist, :498 score_detail, :1099 init; signal_ingest.py:193 refresh_universe, :234 ensure_universe, :242 sweep; signal_scoring.py; signal_store.py (tables at :146-:330); signal_providers.py:3448 ProviderRegistry; templates/signal/*; registered from app.py:14448
- Access: Not plan-gated — signal_hub's own header states /signal is in neither plans._ARTIST_PATHS nor _PRO_PATHS, and required_tier("/signal") returns None. Access is a row in signal_members for the default org, seeded from the Operator Desk roster (DESK_ROLE_MAP) or auto-enrolled for an owner email; everyone else gets signal/denied.html 403 (verified with a Label-plan non-owner). Roles owner/admin/anr/scout/analyst/deal/viewer via signal_store.PERMS. /signal is in _TEAM_BLOCKED. It is deliberately a card in no room and in no palette entry (locked by tests/test_signal_is_internal.py); the only door is _internal_tools() in app.py:383 and the Operator Desk sidebar link.

### Dead code

**rooms.image_for**

Helper meant to return the owner's drawn picture for one room card.

- Because: grepped image_for across every .py and .html in the repo and across tests/ and found only its definition at rooms.py:229; the room screen is handed rooms.images() as room_images and templates/room.html:33 does room_images.get(key) itself
- Routes: none
- Files: rooms.py:229 image_for (rooms.py:213 images is the live one)
- Access: n/a

> Noted by the reviewer as not yet written up in this area: Operator Desk Meeting Intelligence — upload a recording, transcribe it, review extracted lead candidates, delete. Routes /operator-desk/meetings (GET, 302 to the dashboard), /meetings/upload (POST), /meetings/<id> (GET, 302), /meetings/<id>/transcribe (POST), /meetings/<id>/delete (POST), /meetings/candidates/<id>/decide (POST). Files: audio_desk.py:90-120 meetings_index and meeting_upload, :157 transcribe, :200 detail, :209 candidate decide, :334 delete; audio_meetings.py; registered from operator_desk.py:625-628. templates/desk/meetings.html and desk/meeting.html are orphans (no render_template anywhere). Same retirement family as the Files page the inspector did list: index and detail are redirects, the write routes still work behind _audio_on(), a 200 MB cap and a consent box. Desk seat, file_upload permission.; Operator Desk Voice Agent — create, activate, suspend and delete a public-facing voice agent profile, and read/escalate its sessions. Routes /operator-desk/agents (GET, 302), /agents/new (POST), /agents/<id>/activate, /suspend, /delete (POST), /agents/sessions/<id> (GET, 302), /agents/sessions/<id>/escalate (POST). Files: audio_desk.py:261-311; audio_agent.py (GuardrailRefusal checks against known person names); templates/desk/agents.html and desk/agent_session.html are orphans. Writes need manage_users, delete needs delete — both owner-only on the desk.; Internal tools door — the only mechanism that puts the internal desks in the sidebar, and the thing the Signal entry refers to in passing but never lists as a feature. app.py:382 _internal_tools() checks the real rosters (desk_store.get_user_by_email for the Operator Desk, signal_store.get_member for Signal) so it never offers a link that would 403, and adds five owner-only entries on top: /admin/audio, /admin/review, /admin/readiness, /resellers, /admin/release-ready, plus an away-link to the Core builder. Returns [] for a team seat acting inside an artist's account.; Deployment readiness board — /admin/readiness (GET), owner only (404 otherwise). One page reporting which of the deployment's ~73 environment variables are set and, per row, whether that is a key check or a real capability probe; it prints variable NAMES only, never values. Files: readiness.py:323-337 init/admin_readiness, readiness.report(); templates/admin_readiness.html. Locked by tests/test_readiness.py:107-113 (stranger 404, owner 200, link absent from a stranger's /overview).; Artist accounts review queue — /admin/review (GET), owner only via _owner_or_404. A cross-tenant roster of every non-fan account on the deployment with name, email, plan and a live qualification.calculate() score per account. app.py:10588-10610. The header records that this was previously behind a buyable Label tier and leaked every customer's email until 2026-09-10 — an intelligence surface with a real privilege story and no ledger entry.; Soundcharts budget control — /admin/soundcharts-budget (POST), owner only. Sets the month's Soundcharts call allowance that the Signal data-sources page reads back via soundcharts_budget.summary(). app.py:13389-13399; soundcharts_budget.py:85. The inspector cites soundcharts_budget.summary inside the Signal data sources admin entry but never lists the control that sets the number.; Demo walkthrough — /walkthrough (GET) and /walkthrough/sample-statement.csv (GET). A guided first-run tour whose step one uploads a sample statement; app.py:9960-9987 redirects any non-demo email to /command-center, because on a real account the sample produced real-looking income ($1,504.68, a $36,112 valuation — the 2026-09-18 launch check). Belongs beside the tutor/first-run entries: it is the showcase account's version of them, Live for a demo email and closed to everyone else.

## Account, access and billing

69 features: 54 Live, 4 Partial, 10 Stubbed, 1 Dead code.

### Live

**Accept a roster invite**

The invited artist joins a label's roster, creating an account only when sign-up is open.

- Because: app.py:6745 calls store.accept_roster_invite and signs the artist in; the same _join_existing_ok password check applies, the label's plan is re-checked at redemption (so a downgrade kills pending invitations), and a shut door returns _MEMBER_LINK_SHUT with 403.
- Routes: GET/POST /roster/join/<token>
- Files: app.py:6745 roster_join(); templates/roster_join.html; db.py get_roster_invite/accept_roster_invite
- Access: anonymous — /roster/join/ is in _PUBLIC_PREFIXES; note plans.required_tier (plans.py:59) deliberately leaves /roster/join/ open while the rest of /roster needs Label

**Accept a team invite**

The invited address joins the team, creating an account only when sign-up is open.

- Because: app.py:12890 calls store.accept_team_invite and signs the member in; a probe joined and then opened the account through /portal. _join_existing_ok (app.py:6693) requires the existing account's own password or an already-signed-in match, and with the door shut a new account is refused with _MEMBER_LINK_SHUT.
- Routes: GET/POST /team/join/<token>
- Files: app.py:12890 team_join(), app.py:6693 _join_existing_ok(); templates/team_join.html; db.py get_team_invite/accept_team_invite
- Access: anonymous — /team/join/ is in _PUBLIC_PREFIXES; the token plus the account's own password is the authorisation. Blocked for team seats (_TEAM_BLOCKED '/team').

**Accounts panel (owner)**

Lists every account with plan, arrival, last seen, shut state, owner/demo/partner marks and per-plan counts.

- Because: _accounts_panel (app.py:13560) reads db.py list_accounts (db.py:1482), which selects real users columns and joins active club_members for has_paid; it returns empty dicts for a non-owner.
- Routes: GET /settings#accounts
- Files: app.py:13560 _accounts_panel(); templates/settings.html:409; db.py:1482 list_accounts
- Access: owner only — the panel data is blank for everyone else

**Billing page**

Shows the plan, the wallet and its history, the plan cards, and the Stripe buttons.

- Because: app.py:12762 renders the real wallet, credit_history and plans.PLANS plus stripe_billing.configured()/webhook state; a probe returned 200 for artist, fan and label accounts.
- Routes: GET /billing
- Files: app.py:12762 billing(); templates/billing.html; plans.py:14 PLANS; db.py credit_balances/credit_history
- Access: any signed-in account. Closed to team seats and to partner staff acting as an artist only for the POST actions — the page itself renders.

**Bulk clear of self-registered Fan accounts**

Deletes the Fan accounts that signed themselves up, holding back owner, demo, partner-owned and paying ones.

- Because: app.py:13473 requires the typed word DELETE and calls store.delete_user_everything per row; _clearable_fan_accounts (app.py:13540) does the hold-back and db.py delete_user_everything (db.py:5268) deletes in one transaction with the users row last.
- Routes: POST /admin/accounts/clear
- Files: app.py:13473 admin_accounts_clear(), app.py:13540 _clearable_fan_accounts(); templates/settings.html:468; db.py:5268
- Access: owner only (_owner_or_404)

**Card-free plan switch**

Switches tier instantly, for the demo logins and for an off-Render laptop with no Stripe.

- Because: app.py:5298 writes store.set_user_plan when _demo_switching(user) holds; a probe off RENDER with no Stripe switched artist -> label and the users row changed. _demo_switching (app.py:5290) is false on any deployed service, so a service missing its Stripe key cannot give tiers away.
- Routes: POST /plan/switch
- Files: app.py:5298 plan_switch(), app.py:5290 _demo_switching(); templates/billing.html:238
- Access: any signed-in account, but refused for a partner-seated artist (user['partner_id']) and for anyone holding a live stripe_subscription_id; blocked for team seats (_TEAM_BLOCKED)

**Create an account**

Makes an artist or fan account from name, email and a 6+ character password, honouring an invitation or a referral code.

- Because: app.py:986 calls store.create_user with generate_password_hash and redirects to /command-center; a probe signup created the row and set plan 'artist'.
- Routes: GET/POST /signup (?invite=, ?ref=, ?as=fan)
- Files: app.py:986 signup(); templates/signup.html; db.py create_user/set_user_plan/use_signup_invite/set_referred_by
- Access: anonymous; a signed-in GET is redirected away

**Credit wallet**

One balance per account of monthly Label credits that lapse and bought credits that do not.

- Because: db.py:4599 _credits creates credit_ledger with a unique ref index; _wallet (app.py:925) grants LABEL_MONTHLY_CREDITS once per calendar month keyed by ref; a probe on a Label account read monthly=1000 with a real expiry and the spend moved it to 990.
- Routes: read on GET /billing, GET /suites/go/<key>, POST /api/suites/credits
- Files: app.py:925 _wallet(); plans.py:100 LABEL_MONTHLY_CREDITS; db.py:4599 _credits, :4608 credit_balances, :4633 add_credits, :4649 spend_credits, :4687 credit_history; templates/billing.html
- Access: any signed-in account holds a wallet; only Label is granted monthly credits. The shared demo logins get a 100,000 standing balance on sign-in (app.py:1133).

**Delete the account**

Removes the account and every row that names it, permanently.

- Because: app.py:13627 requires the email typed back and refuses an owner account or one with a live stripe_subscription_id, then calls store.delete_user_everything (db.py:5268), clears the session and deletes blob objects after the rows commit. It also writes a _ref_spent_key hash so deleting and re-signing-up cannot earn the referral twice.
- Routes: POST /account/delete
- Files: app.py:13627 account_delete(); db.py:5268 delete_user_everything; templates/settings.html:537
- Access: the account holder; blocked for team seats ('/account')

**Demo walkthrough**

The demo's guided tour page, plus a sample statement CSV to upload during it.

- Because: app.py:9959 renders walkthrough.html and redirects any non-demo account to /command-center; app.py:9975 returns a hard-coded CSV as a download.
- Routes: GET /walkthrough, GET /walkthrough/sample-statement.csv
- Files: app.py:9959 walkthrough(), app.py:9975 walkthrough_sample_csv(); templates/walkthrough.html
- Access: signed-in demo accounts only; everyone else is bounced to /command-center

**Demo workspace sign-in**

Opens one of the four seeded showcase logins with the shared demo password and lands on the walkthrough.

- Because: app.py:1062 refuses any address not in demo_accounts.EMAILS, checks the password hash, then redirects /walkthrough (or /discover for the fan demo); a probe returned 302 /walkthrough and a non-demo address returned 302 /login.
- Routes: POST /demo-open
- Files: app.py:1062 demo_open(); templates/partials/login_demo_tour.html:58; demo_accounts.py:28 is_demo_email
- Access: anonymous, password-gated; the four exact addresses only

**First-run checklist**

A five-step start-here panel on the Command Center, derived from what the account actually has.

- Because: _firstrun_panel (app.py:2383) runs a real query per step and firstrun.build (firstrun.py:63) drops any step the account cannot reach and retires the panel at RETIRE_AT; it reads no 'seen onboarding' flag, so deleting the thing brings the step back.
- Routes: rendered inside GET /command-center
- Files: firstrun.py; app.py:2383 _firstrun_panel(), app.py:5938; templates/command_center.html
- Access: any signed-in account except a fan plan (app.py:2392); stands aside when the tutor panel is on

**Grant a plan by address**

The owner puts any account on any tier without a card, and the grant then holds against Stripe changes.

- Because: app.py:13516 calls store.set_user_plan then store.set_kv(plan_grant:<id>), which _plan_held (app.py:5358) reads so webhook and checkout paths skip that account; it notifies in-app and reports honestly whether the email went.
- Routes: POST /admin/plan
- Files: app.py:13516 admin_plan(), app.py:13563 _grant_plan_email_html(), app.py:13590 _grant_plan_notify(); templates/settings.html:494; db.py set_user_plan/set_kv
- Access: owner only (_owner_or_404)

**Guest pass (72-hour access)**

An invitation marked guest sets access_ends 72 hours from redemption, after which the account is shut off but not deleted.

- Because: app.py:1036 sets store.set_access_ends(now + guest_hours); db.py account_shut returns 'ended' past that time and current_user (app.py:803) clears the session; a probe confirmed access_ends was written.
- Routes: POST /admin/invite (guest=1); enforced in every request via current_user/login
- Files: app.py:1036, app.py:803, app.py:1101; db.py:1463 set_access_ends, db.py:1470 account_shut
- Access: owner mints it; the guest is any plan the invitation names

**Invitation-only sign-up door**

On a deployed service the sign-up form still renders but creates nothing unless an owner invitation token is present.

- Because: _signup_open (app.py:966) returns False whenever RENDER is set and SIGNUP_MODE is not 'open'; with RENDER set a probe POST /signup returned 403 with the invite-only sentence, and the same POST with ?invite=<token> returned 302 /command-center.
- Routes: GET/POST /signup
- Files: app.py:966 _signup_open(), app.py:1005-1014; db.py get_signup_invite
- Access: anonymous; governed by env SIGNUP_MODE and RENDER, not by plan

**Membership plan cards**

The four tier cards (Fan free, Artist $29, Pro $79, Label $199) shown on Billing and on every upgrade wall.

- Because: plans.PLANS (plans.py:14) is passed to templates/billing.html as plan_cards and to templates/upgrade.html as plans_list from plan_gate, suite_go and the grant email; the prices match stripe_provider.PRICES (2900/7900/19900). Note the public route /plan (app.py:13824) is the Artist EQ plan page, not a membership page.
- Routes: rendered on GET /billing and on any 402 upgrade wall
- Files: plans.py:14 PLANS, plans.py:33 PLAN_NAMES; stripe_provider.py:23 PRICES; templates/billing.html:233, templates/upgrade.html
- Access: any signed-in account

**Owner invitation link (Settings > Invite someone)**

The owner mints a one-address, one-plan, one-use sign-up link, optionally as a 72-hour guest pass.

- Because: app.py:13411 writes a signup_invites row via db.py add_signup_invite (db.py:4692); a probe as an owner produced the row with plan='label', guest_hours=72 and the link redeemed once.
- Routes: POST /admin/invite; the link is /signup?invite=<token>
- Files: app.py:13411 admin_invite(); templates/settings.html:384; db.py:4587 _signup_invites / add_signup_invite / get_signup_invite / use_signup_invite / list_signup_invites
- Access: owner only (_owner_or_404, app.py:10126); a non-owner POST returned 404 in a probe

**Owner's door on an account (lock / unlock / extend / make permanent)**

The owner locks or unlocks any account, adds 72 more guest hours, or removes the end date.

- Because: app.py:13492 branches on the action and calls set_account_locked / set_access_ends; a probe locked an account and its next sign-in was refused with the locked sentence.
- Routes: POST /admin/account
- Files: app.py:13492 admin_account(); templates/settings.html:446; db.py:1458 set_account_locked, db.py:1463 set_access_ends
- Access: owner only (_owner_or_404); owner accounts themselves are refused as targets

**Partner act-on-behalf**

Partner staff open an artist's workspace as the artist, with every change on the partner's audit trail.

- Because: partner_os.py:261 writes an audit row then sets session['acting_as']; current_user (app.py:761) re-resolves it through acting_context on EVERY request and drops it the moment the seat, the permission or the ownership goes; the acting_as_change_note/_acting_as_change_write pair (app.py:5165, 5185) records each write.
- Routes: POST /partner/act/<user_id>, POST /partner/act/stop
- Files: partner_os.py:231 acting_context(), :261 act_as(), :279 act_stop(); app.py:761 current_user(), :5165, :5185; partner_store.py audit
- Access: a seat with act_as_artist over an owned artist. act/stop is deliberately not behind @require so a seat that just lost the permission can still leave.

**Partner console (white-label reseller)**

A reseller's own home, roster, branding and audit trail inside Street Banker.

- Because: partner_os.py:26 registers a /partner blueprint whose every handler sits behind @require(permission) (partner_os.py:48), which resolves the tenant, 404s a request with no seat and 403s a seat without the permission; a probe with no seat got 404 on /partner/.
- Routes: GET /partner/, GET/POST /partner/branding, GET /partner/roster, GET /partner/audit
- Files: partner_os.py:94 home(), :132 branding(), :180 roster(), :223 audit(); app.py:4893 resolve_partner(); partner_store.py:132 init_partners; templates/partner/*.html
- Access: a partner_members seat at an active partner, with the named permission. Blocked for team seats (_TEAM_BLOCKED '/partner'). Tenant resolution is by host (domain or <slug>.PARTNER_ROOT_DOMAIN) then by seat.

**Partner grants an artist's tier**

The reseller sets one of its artists onto fan/artist/pro/label and carries the cost.

- Because: partner_os.py:195 goes through owned_user_or_404 then pstore.grant_plan and writes an audit line with the old and new tier; the matching refusal is in app.py:5312, where /plan/switch returns early for any user with partner_id.
- Routes: POST /partner/roster/<user_id>/plan
- Files: partner_os.py:195 set_artist_plan(); partner_store.py grant_plan/owns_user; app.py:5312
- Access: a partner seat with entitlement_grant; the artist themselves cannot switch and cannot check out (_billing_hands_off, app.py:5340)

**Plan tiers and the tier gate**

Four tiers (Fan/Artist/Pro/Label) with a path-prefix wall that answers 402 and an upgrade card above an account's tier.

- Because: plans.required_tier + plans.allowed are enforced in the plan_gate before_request (app.py:4957); a probe on a fan account got 402 on /links and /overview and 200 after switching to artist.
- Routes: every non-public path; the wall is a before_request
- Files: plans.py:12 TIER_RANK, plans.py:14 PLANS, plans.py:56-96 required_tier; app.py:4957 plan_gate(); templates/upgrade.html
- Access: anonymous is redirected to /login first; _PUBLIC_EXACT/_PUBLIC_PREFIXES (app.py:4802) stay open

**Portal (accounts you hold a seat in)**

Lists the accounts this person is on the team of and opens one to work inside it.

- Because: app.py:8546 reads store.list_portal_memberships; /portal/<id>/open re-resolves the seat through _team_seat and sets session['team_as'], landing on team_areas.home; a probe opened a seat and landed on /room/fans.
- Routes: GET /portal, POST /portal/<owner_id>/open, POST /portal/leave, GET /portal/<owner_id>
- Files: app.py:8546 portal(), :8555 portal_open(), :8571 portal_leave(), :8577 portal_view(); app.py:810 _team_seat(); templates/portal.html, templates/portal_view.html
- Access: any signed-in account that holds a seat. /portal is blocked for a seat already inside another account (_TEAM_BLOCKED) except /portal/leave. A seat is refused while acting_as is set, and never opens the owner's account or a demo login (app.py:825).

**Portal summary card**

A per-account summary of money or promo figures for the role, following the rooms the artist opened.

- Because: app.py:8577 sums real statement rows (store.get_statement_rows) and real campaign counts (mls.list_campaigns/event_counts) and only when the matching room is in team_areas.parse(membership['areas']).
- Routes: GET /portal/<owner_id>
- Files: app.py:8577 portal_view(); templates/portal_view.html; team_areas.py:100 parse
- Access: the seat holder; 404 when no membership row exists

**Read-only demo lock**

The owner marks an account read-only so anyone can browse it and nothing they do is saved.

- Because: app.py:5240 writes users.demo_lock via store.set_demo_lock, and the demo_lock_gate before_request (app.py:5044) refuses every non-GET; a probe locked the artist demo and POST /settings/profile came back 302 /command-center?demo=readonly.
- Routes: POST /admin/demo-lock; enforced app-wide by demo_lock_gate
- Files: app.py:5240 admin_demo_lock(), app.py:5044 demo_lock_gate(), app.py:4992 _demo_locked_account(); templates/settings.html:261; db.py:1503 set_demo_lock, db.py:1515 list_demo_locked
- Access: owner only to set it; the lock itself applies to whoever signs into that account. Owner accounts cannot be locked.

**Referral link and stats**

Gives each account a /signup?ref=<code> link and counts sign-ups and conversions from it.

- Because: app.py:5622 calls store.ensure_ref_code (db.py:3399) and store.referral_stats (db.py:3456), which are real COUNT(*) queries over users.referred_by / ref_credited; a probe returned 200 and the signup path writes referred_by (app.py:1046).
- Routes: GET /referrals; GET /signup?ref=<code>
- Files: app.py:5622 referrals(), app.py:1043-1050; templates/referrals.html; db.py:3399 ensure_ref_code, :3411 user_by_ref_code, :3419 set_referred_by, :3456 referral_stats
- Access: any signed-in account; blocked for team seats (_TEAM_BLOCKED '/referrals')

**Remember this device**

A ticked box makes the session permanent (31 days) instead of a browser-session cookie.

- Because: app.py:1127 sets session.permanent = bool(request.form.get('remember')); the checkbox is name="remember" in templates/partials/login_session_recall.html:52.
- Routes: POST /login
- Files: app.py:1127; templates/partials/login_session_recall.html:51
- Access: anonymous

**Remove a team member**

Takes the seat away and rotates the account's statement drop-box address.

- Because: app.py:12937 calls store.remove_team_member and, on success, store.rotate_ingest_token so an address the departing member saw stops working.
- Routes: POST /team/<member_id>/remove
- Files: app.py:12937 team_remove(); db.py remove_team_member, rotate_ingest_token
- Access: the account holder only; returns JSON

**Reseller back office**

The owner creates resellers, sets seat caps, adds staff seats and attaches or detaches artists.

- Because: app.py:10150 onward is behind _owner_or_404 and writes real partner_store rows; refusals are specific (taken slug/domain, seat cap reached, account already on another roster) and attaching never invents an account.
- Routes: GET/POST /resellers, POST /resellers/<pid>/seats, POST /resellers/<pid>/members, POST /resellers/<pid>/artists, POST /resellers/<pid>/artists/<uid>/remove, POST /resellers/<pid>/status
- Files: app.py:10150-10260; partner_store.py:132 init_partners, create_partner/add_member/attach_user/detach_user/set_seat_limit; templates/partners_admin.html
- Access: owner only (_owner_or_404); a probe as a non-owner got 404

**Reset password**

A valid, unused link sets a new password hash and signs the person in.

- Because: app.py:1401 verifies the signature with max_age=3600, compares _reset_stamp (a hash of the current password_hash, app.py:1356) so a used link stops working, then calls store.set_user_password and sets session['user_id'].
- Routes: GET/POST /reset/<token>
- Files: app.py:1401 reset_password(), app.py:1356 _reset_stamp(); templates/reset.html; db.py set_user_password
- Access: anonymous — /reset/ is in _PUBLIC_PREFIXES (app.py:4812); the token is the authorisation

**Roster invite (Label seats an artist)**  *(status corrected on review)*

A Label invites an artist onto its roster by email.

- Because: The 404 is unreachable. plans.required_tier() (plans.py:77-79) returns "label" for /roster and every /roster/... path except /roster/join/, so the plan_gate before_request (app.py:4972) answers 402 with upgrade.html before roster_invite() ever runs. Probe on a throwaway DB: artist account POST /roster/invite -> 402, pro -> 402, label -> 302 /roster with the roster_invites row written; GET /roster is 402 for artist and pro, so a non-Label account cannot even see the button. Every plan that clears the gate (label, or the owner) satisfies _may_seat(user,"roster") (app.py:6664-6677), so `return redirect("/upgrade?why=roster")` at app.py:6728 can never execute. The invite itself is Live end to end: probe POST /roster/invite then GET+POST /roster/join/<token> -> 302 /command-center with the row moving invited->active and artist_user_id set. app.py:6728 is dead code inside a live handler and should be noted as such, but it does not make the feature Partial.
- Routes: POST /roster/invite
- Files: app.py:6722 roster_invite(); app.py:6728 the dead redirect; db.py add_roster_invite; templates/upgrade.html exists but is only ever rendered inline by the gates
- Access: Label plan only (_may_seat kind='roster', app.py:6664); owner always. Blocked for team seats via '/roster/join', and roster writes need can_roster on an edit seat.

**Settings > display name**

Saves the account's display name server-side.

- Because: app.py:13602 calls store.set_user_name and redirects with ?saved=1; the docstring records that this replaced a localStorage form that saved nothing. Email and plan are deliberately read-only here.
- Routes: POST /settings/profile
- Files: app.py:13602 settings_profile(); templates/settings.html:71; db.py set_user_name
- Access: any signed-in account

**Settings > home page layout**

The owner switches the front page between the long homepage and the split app door.

- Because: app.py:4716 is behind _owner_or_404 and calls split_home.set_layout; split_home.enabled() is also read into the settings context (app.py:13301).
- Routes: POST /admin/home-layout
- Files: app.py:4716 admin_home_layout(); split_home.py; templates/settings.html:216
- Access: owner only; env SPLIT_HOME can also turn it on

**Settings > notification preferences**

Ticks which kinds of notification the account wants; unticked kinds are dropped before they are written.

- Because: app.py:13286 computes the complement of the posted kinds against store.NOTIFICATION_KINDS and calls store.set_muted_kinds, which notify() reads.
- Routes: POST /settings/notifications
- Files: app.py:13286 settings_notifications(); templates/settings.html:99; db.py NOTIFICATION_KINDS, notification_mutes, set_muted_kinds/muted_kinds
- Access: any signed-in account

**Settings > online sales switch**

The owner turns paid fan-club joins and online VIP packages on or off platform-wide.

- Because: app.py:13401 is behind _owner_or_404 and calls sales_switch.set_on, which writes app_kv (sales_switch.py:22); default is off.
- Routes: POST /admin/online-sales
- Files: app.py:13401 admin_online_sales(); sales_switch.py; templates/settings.html:372
- Access: owner only

**Settings > page switchboard**

The owner switches any sidebar page off for everybody but themselves, and since 2026-09-23 any room card that is not a sidebar entry too (Fan Club, Fan CRM, Tax, Contracts, Trust score, Insights, Deal Simulator, Track Passports, Release Calendar, Release check, Distribution): page_switches.entries() lists each unfolded page (rooms.EXTRA) after the entry it unfolded from, under that hub, so the board shows it, known_keys() accepts it and set_hidden() keeps it. Before that day set_hidden dropped those keys silently and hiding "fan-club" hid nothing.

- Because: app.py:5223 is behind _owner_or_404 and writes page_switches.set_hidden; the page_switch_gate before_request (app.py:5210) bounces non-owners to /command-center?off=<label>.
- Routes: POST /admin/pages; enforced by page_switch_gate
- Files: app.py:5223 admin_pages(), app.py:5210 page_switch_gate(); page_switches.py; templates/settings.html:229
- Access: owner only to set; the effect applies to everyone else

**Settings > sidebar layout (rooms or hubs)**

The owner picks which sidebar everybody gets on the next request.

- Because: app.py:4706 is behind _owner_or_404 and calls rooms.set_layout.
- Routes: POST /admin/nav-layout
- Files: app.py:4706 admin_nav_layout(); rooms.py set_layout; templates/settings.html:205
- Access: owner only

**Settings > tutor mode**

Turns the guided tutor panel on or off for this browser.

- Because: app.py:2362 sets a one-year cookie; it persists per browser, not per account, and the posted back link is validated to a single leading slash before it is used.
- Routes: POST /tutor/toggle
- Files: app.py:2362 tutor_toggle(); templates/settings.html:45
- Access: any signed-in account

**Settings page**

One page carrying the account's profile, notifications, tutor mode, backup and — for an owner — every operator panel.

- Because: app.py:13298 renders settings.html with real state (muted kinds, backup state, signup_open, the invite list, demo-locked accounts) and every owner-only value is gated on _is_owner_email at the point it is computed; a probe returned 200 for an ordinary artist and the owner blocks were empty.
- Routes: GET /settings
- Files: app.py:13298 settings(); templates/settings.html
- Access: any signed-in account; owner sections are computed as empty for everyone else. Blocked for team seats (_TEAM_BLOCKED '/settings').

**Showcase demo accounts and their seeding**

Four fixed logins (Label, Pro, Artist, Fan) are created at boot and the three non-fan ones get a real parsed statement.

- Because: create_app (app.py:737-753) creates any missing address, forces its plan, rewrites the password from DEMO_PASSWORD when set, and calls demo_seed.seed_statements, which runs a real CSV through parse_statement into the statements tables (demo_seed.py:1).
- Routes: none — runs at import of app.py
- Files: app.py:737-753; demo_accounts.py:17 ACCOUNTS; demo_seed.py
- Access: not user-facing; the set is exact (demo_accounts.py:28), so a lookalike address gets no showcase treatment

**Sidebar tier and credit tags**

Marks a sidebar entry the account cannot open with 'Pro' or 'Credits' instead of hiding it.

- Because: plans.nav_lock (plans.py:134) is injected as a template callable at app.py:4611 and rendered at templates/base.html:238 and :274; it returns '' for the owner and for anything already open.
- Routes: every page that renders the sidebar
- Files: plans.py:134 nav_lock(), :157 suite_tag(); app.py:4611-4618; templates/base.html:238,274
- Access: cosmetic; the real refusals are plan_gate and suite_go

**Sign in**

Email and password sign-in that starts the session and routes fan / demo / artist accounts to different homes.

- Because: app.py:1096 checks check_password_hash against the users row, sets session['user_id'], and a probe POST returned 302; account_shut (db.py:1470) blocks a locked or expired account with a reason.
- Routes: GET/POST /login
- Files: app.py:1096 login(); templates/login.html + templates/partials/login_session_recall.html; db.py get_user_by_email/account_shut
- Access: anonymous; already signed-in GET redirects to _signed_in_home (app.py:1084)

**Sign out**

Clears the session keys for the account, the team seat and the seat name.

- Because: app.py:1464 pops user_id/signed_in/team_as/team_as_name and redirects to /login; probe POST returned 302.
- Routes: POST /logout
- Files: app.py:1464 logout()
- Access: any signed-in account; also in _DEMO_LOCK_ALLOWED and _TEAM_ALLOWED so a locked demo and a team seat can always leave

**Start over (empty the account, keep the login)**

Deletes every row the account owns while keeping the login, plan, seats and drop-box address.

- Because: app.py:13355 requires the account's own email typed back, refuses while any fan is paying it through Stripe (store.fan_club_subscriptions, db.py:5248), then calls store.reset_user_data in one transaction (db.py:5260) and deletes the blob keys afterwards, best effort.
- Routes: POST /account/reset
- Files: app.py:13355 account_reset(); db.py:5133 RESET_KEEPS, :5260 reset_user_data, :5107 stored_keys_for_user; templates/settings.html:517
- Access: the account holder; '/account' is in _TEAM_BLOCKED so no team seat can reach it

**Suite credit call (server to server)**

A suite asks Street Banker for an account's credit balance or spends some of it.

- Because: app.py:932 verifies a token signed under a separate CREDIT_SALT, refuses a shut account 403 and an unsigned body 401, and calls store.spend_credits; a probe got balance 1000 then 990 after a spend of 10, and 401 for garbage.
- Routes: POST /api/suites/credits
- Files: app.py:932 suite_credits_call(); sb_suite_sso.py:66 issue_credit_call/verify_credit_call; db.py:4649 spend_credits
- Access: no session — the signed token is the authorisation. Listed in _PUBLIC_EXACT (app.py:4869) and blocked for team seats (_TEAM_BLOCKED '/api/suites').

**Suite doors**

Hands a signed-in artist across to The Room, REACH, Noise Lab, Tour or Motion.

- Because: app.py:875 checks the key against suite_sso.SUITES, grants Label monthly credits via _wallet, enforces plans.suite_open, and redirects; a probe as Label got 302 to the suite, as Artist got 402, and /suites/go/bogus 404s.
- Routes: GET /suites/go/<key>
- Files: app.py:875 suite_go(), app.py:925 _wallet(); sb_suite_sso.py:36 SUITES; hubs.py:315 SUITES_SOON; templates/upgrade.html, templates/suite_soon.html
- Access: signed in; SUITE_ACCESS (plans.py:105) decides — artist for royalty-sweep/artifacts, pro for reach/tour/company, credits for the-room/noise-lab/motion/masterclip. Owner opens all. Blocked for team seats (_TEAM_BLOCKED). noise-lab is in SUITES_SOON so everyone but the owner gets suite_soon.html; motion is closed to demo logins.

**Suite gates on in-app pages**

Pages that are really The Room or Tour under another name open the way those suites do — credits or Pro.

- Because: plans.path_suite maps /rack,/remix-lab,/audio-studio,/beats,/studio to the-room and /passports,/stage-plot,/lights,/tour-board,/live to tour, and plan_gate (app.py:4980) returns upgrade.html with 402 when suite_open is false; gates_on() only returns True on RENDER or SUITE_GATES=on, so a laptop run is ungated.
- Routes: the paths in plans._ROOM_PATHS and plans._TOUR_PATHS
- Files: plans.py:113 gates_on(), plans.py:121 path_suite(), plans.py:167 suite_open(); app.py:4979-4989
- Access: Label or a non-zero credit balance for the-room; Pro for tour; the owner's own account bypasses both

**Team change audit**

Records every write an editing seat makes, under their own name, on the artist's Team page.

- Because: g._team_audit is set in the gate and written by the _team_audit_write after_request (app.py:5157) only when a URL rule matched and the status is under 400, into the team_audit table (db.py:982).
- Routes: after_request; shown on GET /team
- Files: app.py:5152-5162; db.py:982 team_audit, add_team_audit/list_team_audit
- Access: written for seats; read by the account holder on /team

**Team invite**

Invites someone by email into a role with read or edit access and a set of ticked rooms.

- Because: app.py:12835 writes a team_members row through store.add_team_invite and returns the join link as JSON; a probe got {"ok":true,"link":...} and the link worked. Seat limits, edit rights (plans.team_can_edit) and roster rights (plans.team_can_roster) are all checked server-side.
- Routes: POST /team/invite
- Files: app.py:12835 team_invite(); team_areas.py:118 from_form; plans.py:196 TEAM_SEATS/team_can_edit/team_can_roster; db.py add_team_invite; templates/team.html
- Access: any paid plan (_may_seat, app.py:6664 — artist/pro/label, not fan); edit only on Pro or Label; roster rights only on Label; owner always. Blocked for team seats.

**Team page**

Lists team seats with their role, access, rooms and seat count, plus a change audit.

- Because: app.py:12787 reads store.list_team, store.count_team_seats and store.list_team_audit and labels each row with team_areas.describe; a probe returned 200.
- Routes: GET /team (?older=N)
- Files: app.py:12787 team(); templates/team.html; team_areas.py:180 describe; db.py team_members / team_audit
- Access: any signed-in account; seats per plan come from plans.TEAM_SEATS (artist 2, pro 5, label unlimited) and the owner has no limit. Blocked for team seats (_TEAM_BLOCKED '/team').

**Team room checkboxes**

Which of the eight rooms a seat may open, and the page-level enforcement of that choice.

- Because: team_areas.allows/hidden_page_keys drive the team_seat_gate (app.py:5110); a probe seat granted only fans+marketing landed on /room/fans, got 200 there and on /press, and was bounced with ?team=room from /command-center and /room/stage.
- Routes: POST /team/invite, POST /team/<member_id>/access; enforced on every request by team_seat_gate
- Files: team_areas.py (LABELS, EXTRA, WHOLE_ACCOUNT, allows, home, hidden_page_keys); app.py:5110 team_seat_gate(); templates/team.html
- Access: set by the account holder; applies to the seat holder

**Team seat access change**

Change a seat between read and edit, grant roster rights, and re-tick its rooms.

- Because: app.py:12815 downgrades an edit request to read unless the plan allows it, refuses an empty room set with ?rooms=none, and writes through store.set_team_access.
- Routes: POST /team/<member_id>/access
- Files: app.py:12815 team_member_access(); db.py set_team_access; team_areas.py:118 from_form
- Access: the account holder only; blocked for team seats

**Team seat gate**

Keeps a seat out of the account holder's billing, settings, team, suites and invitation doors, and makes a read seat read-only.

- Because: app.py:5110 checks _TEAM_BLOCKED (app.py:5084) and _team_blocked_inside, then team_areas.allows, then the read/edit rule; a probe seat got 302 ...?team=blocked on /billing, /settings and /team. HEAD with a body is refused 400 because Flask answers HEAD with the GET view.
- Routes: before_request on every path while session['team_as'] is set
- Files: app.py:5084 _TEAM_BLOCKED, app.py:5090 _team_blocked_inside(), app.py:5110 team_seat_gate()
- Access: applies to team seats only; /portal/leave and /logout stay open (_TEAM_ALLOWED)

**Upgrade wall page**  *(status corrected on review)*

The 402 page that names the tier or credits needed and lists the plans.

- Because: The missing route is real (signed-in GET /upgrade -> 404; grep for '\"/upgrade' and "'/upgrade" across all .py finds only the _TEAM_BLOCKED string at app.py:5086 and the redirect at app.py:6728; add_url_rule at app.py:8653 only registers cc.MODULES preview routes, and "upgrade" does not appear in command_center.py). But the only cited defect is that one redirect, and it is unreachable (see the Roster invite correction), so nothing in the product reaches the 404. Every real path into templates/upgrade.html was probed and works at 402: plan_gate tier wall (fan GET /links -> 402, GET /overview -> 402), the suite gate on in-app pages with SUITE_GATES=on (artist GET /rack, /beats, /audio-studio, /remix-lab, /lights, /stage-plot, /passports, /tour-board -> all 402), and suite_go (artist GET /suites/go/the-room, /suites/go/tour, /suites/go/reach -> 402).
- Routes: rendered inline with 402; /upgrade itself is not a route
- Files: templates/upgrade.html; app.py:4949, :4985, :911; the broken link is app.py:6728
- Access: any signed-in account that hits a wall

### Partial

**Demo password request**

A visitor leaves an email, the lead is filed in the owner's inbox and the demo password is mailed if the mailer is live.

- Because: the lead is really stored (store.add_inbox, app.py:1197) and a 90-day sb_demo_lead cookie is set — a probe returned 302 /login?demo=pending with the cookie — but the email half only runs when emailer.configured(), so without RESEND_API_KEY nobody is sent a password and the page says 'pending'.
- Routes: POST /demo-access
- Files: app.py:1157 demo_access(); templates/partials/login_demo_tour.html:37; email_provider.py; db.py add_inbox
- Access: anonymous; honeypot field 'company' and an in-process 30s-per-IP throttle (app.py:1154 _demo_access_seen)

**Forgot password**

Emails a one-hour signed reset link to an address that has an account, saying nothing about whether it does.

- Because: the token mint and the same-response-either-way behaviour are real (app.py:1368, itsdangerous over SECRET_KEY, link pinned to PUBLIC_BASE_URL not the Host header), but the form refuses outright when emailer.configured() is False, so with RESEND_API_KEY unset no link can be obtained at all.
- Routes: GET/POST /forgot
- Files: app.py:1368 forgot_password(); templates/forgot.html; email_provider.py:22 configured/send
- Access: anonymous; a signed-in GET is redirected to _signed_in_home

**Settings > full-database backup**

Downloads a consistent zip of the database and uploads, or triggers the off-box push.

- Because: the download is real — _snapshot_zip (app.py:13664) uses SQLite's backup API and walks UPLOADS_DIR — but /backup/run returns an honest error unless backup_store.configured(), which needs off-box target env vars that are not set here; the run record is written to app_kv either way.
- Routes: GET /backup, POST /backup/run
- Files: app.py:13756 backup_download(), :13767 backup_run(), :13664 _snapshot_zip(), :13262 _backup_allowed_for(); backup_store.py; templates/settings.html:168
- Access: owner only (_is_owner_email, or the legacy singular OWNER_EMAIL), and never while acting_as or team_as is set; or a scheduler presenting BACKUP_TOKEN, which _valid_backup_token (app.py:4884) lets past the login wall for this path alone

**Suite sign-in hand-off (SSO)**

Mints a 2-minute signed token naming the account and one suite so nobody signs in twice.

- Because: issue/handoff_url work and a probe with SUITE_SSO_SECRET set produced a real token URL, but sb_suite_sso.configured() is False without that secret and app.py:917 then falls back to a plain link with no identity at all; whether the suite services accept the token could not be checked from this repo.
- Routes: GET /suites/go/<key> issues it; the suites receive it at /auth/street-banker
- Files: sb_suite_sso.py:100 issue(), :110 handoff_url(), :132 verify(); app.py:915-918
- Access: same as the suite door above

### Stubbed

**Credit packs**

Buy 500 / 2,000 / 5,000 credits as a one-off Stripe payment.

- Because: plans.CREDIT_PACKS_ON_SALE is False (plans.py:107) so app.py:5481 returns to /billing#credits before doing anything — a probe POST came back 302 /billing#credits. The Stripe session builder and the _claim_credit_pack path exist behind the switch but nothing can reach them.
- Routes: POST /billing/credits; claimed on GET /billing?credits=1&session_id= and in the webhook
- Files: app.py:5481 billing_credits(), app.py:5500 _claim_credit_pack(); plans.py:106 CREDIT_PACKS; stripe_provider.py:612 create_credit_pack_checkout
- Access: any signed-in account when the switch is on; refused for a demo-locked account

**Onboarding wizard**

A 'Connect your sources' screen listing eight platforms with tick boxes.

- Because: app.py:12949 hard-codes connected=False for all eight and there is no POST route and no form action in templates/onboarding.html — the ticks persist nowhere. Nothing links to it either: grepping '/onboarding' across templates/ and every .py returns only the route and a comment saying signup now redirects to /command-center instead. Two tests in tests/test_app.py (976, 5606) still GET it, so it is not unreachable by the letter of the dead-code rule.
- Routes: GET /onboarding
- Files: app.py:12949 onboarding(); templates/onboarding.html
- Access: any signed-in account (behind the login wall only)

**Partner seat billing statement**

Works out what a reseller owes: a flat platform fee plus each artist seat at 40% off list.

- Because: partner_billing.py:36 statement() is arithmetic over the roster and stripe_provider.PRICES only — nothing charges, invoices or records anything, and the module says so in its own docstring; partner/home.html:10 renders the figure as a read-out.
- Routes: rendered on GET /partner/
- Files: partner_billing.py:36 statement(), :26 seat_price_cents(); templates/partner/home.html:10
- Access: a partner seat with 'view'

**Referral credit settlement**

Credits a referrer half their own billed month on a Stripe balance once the friend actually pays.

- Because: every path into it runs through Stripe — ensure_referral_coupon, apply_credit, find_credit, subscription_state — and stripe_provider.configured() is False without STRIPE_SECRET_KEY. The bookkeeping around it is real: claim_ref_credit/release_ref_credit in the database (db.py:3430), an idempotency key per referred id, a cap at what the friend paid, and a _ref_spent_key so deleting and re-signing-up cannot earn it twice.
- Routes: driven by POST /webhooks/stripe (invoice.paid), POST /billing/sync, POST /billing/checkout
- Files: app.py:5560 _credit_referrer(), app.py:5591 _referral_cents(), app.py:5599 _settle_referrals(), app.py:121 _ref_spent_key(); stripe_provider.py:161 referrer_credit_cents, :167 ensure_referral_coupon, :187 apply_credit, :217 find_credit
- Access: not user-facing; the referrals page tells the member plainly when stripe_live is false (templates/referrals.html:38)

**Sample billing block (invoices, renewal date, usage tiles)**

A demonstration plan card with three invented paid invoices and a literal renewal date.

- Because: billing_config.get_billing_data hard-codes INV-2026-06/05/04, renews_on '2026-08-01' and reads royalty_data's seed catalogue, not the account; templates/billing.html:27 wraps the whole block in {% if is_demo_account %}. A probe confirmed a demo account sees INV-2026-06 and the plan-name match against its own PLANS list (Free/Pro Plan/Label) does not line up with plans.PLAN_NAMES, so it falls through to 'Pro Plan' for anything but Label.
- Routes: rendered inside GET /billing
- Files: billing_config.py:1 (module docstring says so in as many words); templates/billing.html:9-70; app.py:12768
- Access: the four demo logins only

**Stripe billing portal**

Sends the member to Stripe's own portal to change the card, see invoices or cancel.

- Because: app.py:5650 needs both stripe_billing.configured() and a stored stripe_customer_id and otherwise redirects to /billing; neither exists without STRIPE_SECRET_KEY. The forgotten-customer cleanup (customer_exists is False -> clear the ids) is real code.
- Routes: POST /billing/portal
- Files: app.py:5650 billing_portal(); stripe_provider.py:701 create_portal_session, :266 customer_exists
- Access: any signed-in account with a customer id; refused while working in someone else's account (_working_as_someone, app.py:5346)

**Stripe subscription checkout**

Starts or changes a paid membership through a Stripe-hosted checkout.

- Because: the handler is thorough — it revalidates the customer id, moves an existing subscription with change_subscription_plan rather than opening a second one, settles an already-open session, and applies a referral coupon — but stripe_provider.configured() (stripe_provider.py:30) is False without STRIPE_SECRET_KEY and app.py:5379 then redirects straight back to /billing, which is the state in this checkout. Whether a real charge completes was not testable here.
- Routes: POST /billing/checkout; success_url /billing?upgraded=1
- Files: app.py:5373 billing_checkout(), app.py:5677 _claim_plan_session(); stripe_provider.py:230 create_checkout_session, :395 change_subscription_plan, :455 active_subscription_for_customer, :476 close_open_checkout
- Access: any signed-in account. Refused when _billing_hands_off (app.py:5340): a partner-seated artist, act-on-behalf, or a team seat.

**Stripe webhook receiver**

Takes Stripe's events and moves plans, credits, referrals, fan-club and VIP state accordingly.

- Because: app.py:5755 aborts 404 when stripe_billing.webhook_accepts() is false — a probe POST returned 404 — and verifies the signature otherwise. The handlers behind it are real and detailed (checkout.session.completed, async_payment_succeeded, invoice.paid, invoice.payment_failed, customer.subscription.updated/deleted, charge.refunded, charge.dispute.created), including 503 'retry' answers when Stripe cannot be read.
- Routes: POST /webhooks/stripe
- Files: app.py:5755 stripe_webhook(); stripe_provider.py:36 WEBHOOK_EVENTS, :764 verify_webhook
- Access: no session — Stripe's signature is the authorisation; /webhooks/ is in _PUBLIC_PREFIXES

**Stripe webhook self-setup**

Creates the platform's Stripe webhook endpoint from inside the app and stores its signing secret.

- Because: app.py:5635 gates on _owner_or_404 and calls stripe_provider.setup_webhook_endpoint (stripe_provider.py:718), which needs STRIPE_SECRET_KEY; the secret is kept per Stripe mode in app_kv (stripe_provider.py:60 _kv_key).
- Routes: POST /billing/webhook-setup
- Files: app.py:5635 billing_webhook_setup(); stripe_provider.py:718 setup_webhook_endpoint, :118 webhook_events_current; templates/billing.html:265
- Access: owner only — the card is hidden unless viewer_is_owner (app.py:5286) and the handler 404s otherwise

**Webhook-less Stripe sync**

A button that finds an active subscription by the account's email and puts the plan back in step.

- Because: app.py:5514 returns to /billing immediately unless stripe_billing.configured(); with a key it calls active_subscription_for_email and does persist the plan, ids and a notification, and settles referrals.
- Routes: POST /billing/sync
- Files: app.py:5514 billing_sync(); stripe_provider.py:518 active_subscription_for_email; db.py set_stripe_ids/set_user_plan
- Access: any signed-in account; refused by _billing_hands_off

### Dead code

**Sign-up bot guard** - Live

A honeypot field, a signed form clock, a per-IP rate limit and a throwaway-domain list for the sign-up form.

- Because: Wired 2026-09-21. templates/signup.html:16-20 carries the signed stamp and the hidden field; POST /signup calls signup_guard.judge before it creates anything (app.py, inside signup()), and a caught submission returns 429 having created no account. The helper that mints the stamp is _signup_stamp beside the route.
- Honesty and safety: the reason a submission was caught goes to app.logger and is never rendered, because naming the check tells a script how to pass it. The person sees one sentence (signup_guard.REFUSAL) and a way to reach a human.
- Not judged: an invitation. The owner made that link for one address, so an invited guest on a shared connection is never rate-limited out. The shut door still renders the stamp, so reopening sign-up needs no second change.
- On or off: signup_guard.enabled() is on wherever RENDER is set, off on a laptop and in the tests unless SIGNUP_GUARD=on.
- Caveat, unchanged: _seen is a per-process table and the Procfile runs gunicorn with 2 workers, so the per-IP window is per worker.
- Routes: POST /signup
- Files: signup_guard.py (whole module); app.py (import, _signup_stamp, the judge call in signup(), and the three signup.html renders that pass guard_stamp); templates/signup.html:16-20; tests/test_signup_guard.py (the judgement) and tests/test_signup_guard_wired.py (the door)
- Access: the public sign-up form.
- Companion: the refusal tells the person to write to us, and until 2026-09-21 the door pages offered nowhere to write. partials/support_ask.html is now included by templates/auth_base.html as well as base.html, so sign-in, create account, forgot and reset all carry it. The partial is self-contained, with its own styles and script.

> Noted by the reviewer as not yet written up in this area: Label roster desk — GET /roster (app.py:6607 roster(); templates/roster.html). Per-artist statement revenue, fans, live links, upcoming shows, OS summary and certification for every active roster member, plus a 10-item upcoming-release calendar, all summed from real rows via store.list_roster + _artist_snapshot + mls.list_campaigns. Live; Label tier (plans.required_tier). Probe: label GET /roster -> 200, artist/pro -> 402.; Roster CSV export — GET /roster/export.csv (app.py:6639 roster_export()). An 11-column report row per active roster artist (revenue, fans, links, shows, tracks, passport avg, clean-release avg, red rights issues, certification) streamed as text/csv. Live; Label. Probe -> 200.; Roster artist view — GET /roster/artist/<artist_id> (app.py:6795 roster_artist(); templates/roster_artist.html). One roster member's detail page. Live; Label. Probe -> 200.; Remove an artist from the roster — POST /roster/<member_id>/remove (app.py:6812 roster_remove()). Live; Label, and blocked for a team seat without can_roster by team_seat_gate's '/roster' rule (app.py:5144).; Settings > Soundcharts monthly budget — POST /admin/soundcharts-budget (app.py:13389 admin_soundcharts_budget(); form at templates/settings.html:298; read back into the page as soundcharts_budget.summary() at app.py:13332). Owner-only via _owner_or_404. Live. Probe as owner -> 302 /settings?soundcharts=saved.; Settings > Release-Ready owner card — POST /admin/release-ready/settings (release_ready blueprint; form at templates/settings.html:331; state at app.py:13335 as rr_month = release_ready_settings.summary() plus roex.configured() and storage_ready()). An owner-only Settings panel that sets the per-master price and the monthly credit budget. No entry at all.; Owner auto-plan grant — _grant_owner_plan (app.py:126). Any address in OWNER_EMAILS or the built-in _OWNER_EMAIL_HASHES is moved to OWNER_PLAN with no card and no Settings action: at boot for every existing row (create_app walks store.list_users(), app.py:757), on every /login (app.py:1127), and right after /signup (app.py:1041). Probe: a fresh signup on an OWNER_EMAILS address came out plan 'label'. Live. It is also what makes the owner bypass plan_gate, the suite gates, suite_go, the demo lock as a target, and _plan_held against Stripe.; Standing demo credit grant — app.py:1131-1136 inside login(). A sign-in adds 100,000 'bought' credits once per account (ref demo-standing:<id>) and lands on /walkthrough. Two things the Credit wallet entry states are not what the code does: (1) it fires only on POST /login, NOT on POST /demo-open, which is the door the login page's demo form actually posts to — probe: after /demo-open the demo-artist wallet was {total: 0}; after /login it was {bought: 100000}; so on a service with SUITE_GATES on, a demo opened by the tour form is refused /rack; (2) the test is the wildcard `email == "demo@streetbanker.io" or email.startswith("demo-") and email.endswith("@streetbanker.io")`, not demo_accounts.is_demo_email — probe: demo-evil@streetbanker.io (is_demo_email False) signed in, got the 100,000 credits and the /walkthrough landing, which is exactly the wildcard demo_accounts.py's docstring says was closed as an open door.; Public memberships band — templates/partials/memberships_band.html, included by templates/landing_split.html:96. The three engraved membership plates and the credit wallet shown on the split home door to anonymous visitors; tests/test_split_home.py asserts every engraved price still matches plans.PLANS. The ledger has the in-app plan cards (Billing / upgrade wall) but nothing for the public pricing surface.; Sandbox mode — sandbox.py (env SANDBOX, SANDBOX_NAME). active() makes stripe_provider.configured() (stripe_provider.py:31) and email_provider.configured() (email_provider.py:24) return False whatever key is set, and adds a fixed banner. It is the switch that decides whether any billing or transactional email in this area does anything, and it is upstream of the 'Stubbed' verdict on every Stripe entry, but it has no entry.

## Press and partners

43 features: 32 Live, 8 Partial, 2 Stubbed, 1 Dead code.

### Live

**Act as an artist (partner impersonation)**

A reseller's staff member opens an artist's workspace and every change is filed under their own name.

- Because: act_as runs owned_user_or_404, audits before the session changes and sets session["acting_as"]; app.py current_user returns the ARTIST for the rest of the request while session["user_id"] keeps the staff id; partner_os.acting_context re-checks seat, permission and ownership on every request, so detaching, suspending or unseating ends it at the next click; acting_as_change_note/_acting_as_change_write add an "act_as.change" audit row for every non-GET that succeeds; base.html:588 shows an undismissable banner with the way out. Probe: act-as redirected to /overview, /overview rendered 200, act_as.start and the stop were both audited, and /partner/act/stop returned to /partner/roster.
- Routes: POST /partner/act/<user_id>; POST /partner/act/stop
- Files: partner_os.py:259 (act_as), 278 (act_stop), 231 (acting_context), app.py:761 (current_user), 5168-5192 (change auditing), templates/base.html:588-603, tests/test_partner_act_as.py
- Access: /partner/act/<id>: a seat holding "act_as_artist" — owner, admin, support. /partner/act/stop is deliberately outside @require so a seat that just lost the permission can still leave. A Street Banker account with no partner_id can never be acted as; acting as yourself is refused. Team seats blocked from /partner, and /partner/act/stop is on app.py's _DEMO_LOCK_ALLOWED list.

**Announcements**

Write a press release (headline, subhead, dateline, body, quote, boilerplate, embargo) and keep the list of them.

- Because: press_desk.releases/release_new/release_edit/release_delete read and write press_releases via press_store.create_release/update_release/delete_release (deleting a release also deletes its pitches and recipients). Probe: POST created a row, GET /press-desk/announcements/<id> returned 200. NOTE: the working tree is mid-rebuild by a concurrent session — release_new/release_edit now render templates/press/announcement_desk.html (announcement + pitch rail on one page) instead of press/release_form.html, and release_form.html is still on disk unused by any handler.
- Routes: GET /press-desk/announcements; GET+POST /press-desk/announcements/new; GET+POST /press-desk/announcements/<release_id>; POST /press-desk/announcements/<release_id>/delete
- Files: press_desk.py:391,398,413,433, press_store.py create_release/update_release/get_release/list_releases/delete_release/embargo_active, templates/press/releases.html, templates/press/announcement_desk.html (new, uncommitted), templates/press/release_form.html (now unreferenced by any handler)
- Access: Any signed-in account. Team seat: Marketing room, edit access to write. Partner act-as writes the artist's rows.

**Artist hub (link-in-bio) on the EPK slug**

A public hub page at /@<slug> keyed on the same press-kit slug, showing the fan club, live links and upcoming shows.

- Because: app.py artist_hub resolves store.get_epk_by_slug and renders artist_hub.html from real rows (fan club, live non-archived ml_campaigns, confirmed/advanced upcoming tour_shows) and links back to /epk/<slug>. Included here because it depends on epk_profiles.slug; its body belongs to the links/fan area.
- Routes: GET /@<slug>
- Files: app.py:6816 (artist_hub), db.py get_epk_by_slug, templates/artist_hub.html:109,113
- Access: Anonymous.

**Console seat claiming**

A seat invited by email binds to the real account the first time that person is seen.

- Because: resolve_partner calls partner_store.claim_seats(user_id, email) on every request where no host matched, and claim_seats fills partner_members.user_id for rows where it is NULL — the module documents this as the fix for Signal's orphaning seats, and tests/test_partner_os.py:123 pins it. Probe: a member added by email before signup reached /partner/ after signing up.
- Routes: before_request (app.py _resolve_partner) and POST /resellers/<pid>/members
- Files: partner_store.py:341 (claim_seats), app.py:4926-4930, tests/test_partner_os.py:123
- Access: Automatic for any signed-in account; no plan involved.

**Contact CSV import**

Paste a CSV of contacts; each unusable row is named with its line number instead of being dropped.

- Because: press_desk.contacts_import calls press_store.import_contacts_csv, which parses with csv.DictReader, de-duplicates against existing emails and returns (added, skipped, problems) rendered by press/import.html; the skip reasons are real strings built per line.
- Routes: GET+POST /press-desk/contacts/import
- Files: press_desk.py:372, press_store.py import_contacts_csv, templates/press/import.html
- Access: Any signed-in account. Team seat: Marketing room, edit access for the POST.

**Coverage log**

Record what ran — outlet, headline, kind, date, quote — and list it.

- Because: press_desk.coverage POST calls press_store.add_coverage (writes press_coverage) and the GET lists it joined to press_releases; desk_stats counts it. Probe: a coverage row written through the form came back from list_coverage. Code-vs-copy disagreement worth recording: press_config.py's workflow says the coverage log is "the material your press kit is allowed to reuse", and no code path moves a press_coverage row into the EPK — grep shows press_coverage is read only by press_desk.desk, press_desk.coverage and desk_stats; the kit's press quotes come from the Google News finder or are typed by hand.
- Routes: GET+POST /press-desk/coverage; POST /press-desk/coverage/<coverage_id>/delete
- Files: press_desk.py:581,594, press_store.py add_coverage/list_coverage/delete_coverage, templates/press/coverage.html
- Access: Any signed-in account. Team seat: Marketing room, edit access for the POSTs.

**Deal Room one-sheet and artist profile redirects**

The two retired label-facing pages now land on the press kit.

- Because: app.py deal_onesheet and artist_profile both return redirect("/epk", code=301) and their templates are gone; probe: GET /deal-room/onesheet returned 301 to /epk.
- Routes: GET /deal-room/onesheet; GET /artist-profile
- Files: app.py:7166 (deal_onesheet), app.py:10006 (artist_profile)
- Access: Signed-in; /deal-room and /onesheet are under plans._PRO_PATHS so they resolve to artist tier, and /artist-profile carries no gate of its own.

**Delete the whole press kit**

Take the kit down: profile, assets, share link and its open log, plus the files this app wrote.

- Because: db.delete_epk removes epk_profiles and epk_assets rows, deletes the epk_shares row and its epk_share_events by token, and returns the stored paths; app.py epk_delete unlinks only basenames matching epk_<user>. or epkasset_<user>_ so a Vault-shared image is left alone. tests/test_epk_delete.py exercises it.
- Routes: POST /epk/delete
- Files: app.py:3996 (epk_delete), db.py:2155 (delete_epk), templates/epk.html:357, tests/test_epk_delete.py
- Access: Any signed-in account (ungated sub-path). Team seat: Marketing room, edit access.

**For deals section of the press kit**

The label-facing figures the old Deal Room one-sheet carried, off by default and never shown on the public or pitch pages.

- Because: _deal_facts builds from the account's own rows (artist_os tracks, clean_release scores, statement rows/total, fans, claimed lanes, upcoming campaigns and Pulse snapshots, counting only readings that carry a number); epk_config._SECTIONS marks "deals" on=False, private=True, and _epk_kit_context passes ctx["deal"] only to the editor and the saved copy — epk_public and epk_pitch never receive it.
- Routes: GET /epk (editor), POST /epk/vault-save (saved copy)
- Files: app.py:7175 (_deal_facts), 3299 (_epk_kit_context), epk_config.py:84 (_SECTIONS "deals"), templates/epk.html, templates/epk_saved.html
- Access: Artist tier or higher on /epk. Team seat: Marketing room. The figures come from the account the request works in.

**Grant an artist's plan (partner entitlement)**

A reseller sets the tier of an artist it owns, and the change is written to the audit trail.

- Because: set_artist_plan runs owned_user_or_404 (ownership asked of the database), rejects a tier outside PARTNER_TIERS with 400, and partner_store.grant_plan re-checks owns_user and writes users.plan scoped by partner_id before pstore.audit records the old and new tier. Probe: POST /partner/roster/<uid>/plan set the artist to pro and "entitlement.grant" appeared in the trail. A seated artist cannot buy their own plan — app.py refuses /plan/switch when user.partner_id is set (probe: 302 to /billing).
- Routes: POST /partner/roster/<user_id>/plan
- Files: partner_os.py:193 (set_artist_plan), 80 (owned_user_or_404), partner_store.py grant_plan/owns_user/audit, app.py:5311 (self-serve refusal), tests/test_partner_seats.py
- Access: A seat holding "entitlement_grant" — owner and admin only (partner_store.PERMS); manager/support/viewer get 403. An artist another partner owns is a 404. Team seats blocked.

**Label Roster**

A label's artists on one desk with revenue, fans, live links, upcoming shows and each artist's Artist OS score and certification.

- Because: app.py roster() lists store.list_roster(user_id) and computes _artist_snapshot per active member from that artist's own statement rows, fans, campaigns and shows, plus _os_full for the score — no constants. Probe: a Label plan got 200; an Artist plan got HTTP 402.
- Routes: GET /roster
- Files: app.py:6606 (roster), 6594 (_artist_snapshot), db.py:4424 (list_roster), roster_members table, templates/roster.html
- Access: Label plan only — plans.required_tier("/roster") returns "label" (probe: artist and fan both 402). The sidebar card is also in rooms.LABEL_ONLY. Team seats: /roster maps to the Business room AND app.py team_seat_gate additionally requires seat["can_roster"] for any write under /roster (plans.team_can_roster is Label-only). Not owner-only.

**Legacy public one-sheet**

The old tokenised one-sheet page that links already sent still open, with a PIN gate and a pitch-back form.

- Because: sheet_public reads onesheet_shares by token, enforces the PIN (403 on a wrong one), builds from the owner's real artist_os tracks, certification and campaigns via _sheet_context, logs a view to onesheet_views for anyone who is not the owner, and sheet_pitch writes a real inbox row (kind onesheet_pitch) plus a notification, with a honeypot field dropping bots. tests/test_app.py:4834 exercises the whole path.
- Routes: GET+POST /sheet/<token>; POST /sheet/<token>/pitch
- Files: app.py:7257 (sheet_public), 7286 (sheet_pitch), 7244 (_sheet_context), db.py:2874-2930 (onesheet share/view helpers), templates/sheet_public.html, db.py add_inbox/notify
- Access: Anonymous (PIN only if the owner set one); unknown token is 404.

**Media list (press contacts)**

Add, edit, search, filter, re-status and delete the writers, editors and curators the artist pitches.

- Because: press_desk.contacts/contact_new/contact_edit/contact_status/contact_delete write press_contacts through press_store; every SELECT/UPDATE/DELETE carries "WHERE ... user_id = ?" (press_store.list_contacts/get_contact/update_contact) — probe: a contact created through the form came back from press_store.list_contacts for that user only.
- Routes: GET /press-desk/contacts; GET+POST /press-desk/contacts/new; GET+POST /press-desk/contacts/<contact_id>/edit; POST /press-desk/contacts/<contact_id>/status; POST /press-desk/contacts/<contact_id>/delete
- Files: press_desk.py:314,328,343,357,365, press_store.py add_contact/update_contact/set_contact_status/delete_contact/list_contacts, templates/press/contacts.html, templates/press/contact_form.html
- Access: Any signed-in account (no tier gate on /press-desk/*). Team seats with the Marketing room; a read-only seat gets the 403/readonly redirect on the POSTs. Partner act-as works in the artist's account.

**Partner audit trail**

Every act-on-behalf, entitlement grant and branding edit at this reseller, with the actor.

- Because: partner_store.audit writes partner_audit with the actor's id and lowercased email, and audit_trail is filtered by partner_id (optionally by subject) — tests/test_partner_os.py:231 pins the scoping. Probe: the trail held entitlement.grant and act_as.start after those actions.
- Routes: GET /partner/audit
- Files: partner_os.py:221 (audit view), partner_store.py audit/audit_trail, templates/partner/audit.html
- Access: A seat holding "view" (every role). No seat = 404. Team seats blocked.

**Partner permissions table**

One table mapping each permission to the roles that hold it, read by the decorator, the templates and Stage Control.

- Because: partner_store.PERMS is consumed by partner_os.require via can(), by every partner template through the injected can() lambda, and by stage_os.py:118,175,188-190,258,292 for stage_review/stage_operate/stage_configure/stage_lockout; can() fails closed for an unknown permission, unknown role, missing member or suspended partner (tests/test_partner_os.py:94,106,112).
- Routes: n/a — consumed by /partner/* and the Stage Control desk
- Files: partner_store.py:56 (PERMS), 362 (can), partner_os.py:48 (require), stage_os.py:118, tests/test_partner_os.py, tests/test_stage_partner_roles.py
- Access: n/a. The four stage_* permissions are exercised by the Stage Control area, outside this area.

**Partner roster and seat cap**

The reseller's artists with what is in each account, against its seat cap.

- Because: partner_os.roster renders partner_store.roster_detail (per-artist songs and ml_campaigns counts, never_signed_in flag, and None rather than 0 for a table a deployment has not created), plus seats_used/seats_left/seat_limit where seats_left returns None for an uncapped partner rather than a fake ceiling. Probe: 200 for a seated owner; tests/test_partner_seats.py pins the cap behaviour.
- Routes: GET /partner/roster
- Files: partner_os.py:178, partner_store.py roster_detail/seats_used/seats_left/seat_limit/_count, templates/partner/roster.html, tests/test_partner_seats.py
- Access: A seat holding "roster_view" (all five roles). No seat = 404. Team seats blocked.

**Pitch builder**

Pick one announcement and a set of contacts; the desk personalises and saves one message and one tracked link per recipient.

- Because: press_store.create_pitch writes press_pitches and one press_recipients row per contact with a unique 20-hex token, substituting only {name}{outlet}{artist}{title}{link}{kit}; do-not-contact, bounced, no-email and the 100-per-pitch cap are enforced in the store and reported as `skipped`. Probe: a pitch came back status=prepared with a personalised subject "Probe Artist2 - Head".
- Routes: GET+POST /press-desk/pitch/new; GET /press-desk/pitch/<pitch_id>; POST /press-desk/pitch/<pitch_id>/delete
- Files: press_desk.py:449 (pitch_new), 480 (pitch), 559 (pitch_delete), press_store.py create_pitch/personalise/pitch_recipients/MAX_RECIPIENTS, templates/press/pitch_form.html, templates/press/pitch.html
- Access: Any signed-in account. Team seat: Marketing room, edit access for the POSTs. Defect seen in code: the POST validation-error branch (press_desk.py:456-461) re-renders pitch_form.html without `kits`, and Jinja iterates the undefined as empty, so a failed submit silently shows "No press kit yet" even when saved kits exist.

**Press Desk**

Landing page for the artist's press work: counts, recent pitches, follow-ups due, recent coverage and announcements.

- Because: press_desk.desk renders press/desk.html from six COUNT queries over this artist's own rows (press_store.desk_stats) plus list_pitches/needs_follow_up/list_coverage/list_releases; no seeded rows anywhere in press_store — probe: signed-in account returns 200 and an empty desk renders empty.
- Routes: GET /press-desk
- Files: press_desk.py:299 (desk), press_store.py desk_stats/needs_follow_up, templates/press/desk.html, templates/press/_shell.html
- Access: Any signed-in account — plans.required_tier("/press-desk") is None, so a Fan plan reaches it (probe: fan GET /press-desk = 200). Team seats: Marketing room (team_areas.room_for_path("/press-desk") == "marketing"); a read seat is refused writes by app.py team_seat_gate. A partner seat acting-as works in the artist's account (press_desk.init is given app.py current_user). Not owner-only. Anonymous is bounced by the global login wall.

**Press Desk public explainer**

The signed-out page describing what the Press Desk does, does not do, and whether this deployment can send.

- Because: app.py press_public renders press_public.html from press_config.get_press_config(), and the sending panel calls the Jinja global cap('press_sending'), which is capability_status._press_sending probing RESEND_API_KEY and EMAIL_FROM at request time — so the page demotes its own claim. Probe: anonymous GET /press = 200.
- Routes: GET /press
- Files: app.py:14227 (press_public), press_config.py get_press_config, capability_status.py:81,145, templates/press_public.html
- Access: Anonymous — /press is a public path.

**Press finder (coverage search for quotes)**

Search live news for the artist and drop a headline into a press-quote slot.

- Because: app.py epk_press_search calls music_apis.press_mentions, which fetches Google News RSS with no key, parses items with ElementTree, strips the trailing " - Publication" and caches for 24h in api_cache; the editor calls it from templates/epk.html:691. Probe: GET /epk/press/search?q=test returned 200 JSON.
- Routes: GET /epk/press/search
- Files: app.py:3421, music_apis.py:252 (press_mentions), templates/epk.html:226,685-696
- Access: Any signed-in account (401 JSON when signed out); ungated sub-path, so a Fan plan reaches it (probe: 200).

**Press Kit editor (EPK)**

Build the artist's press kit: bio, genres, socials, contact, quotes, sections, colour, video, merch, tour dates and the measured stats strip.

- Because: app.py epk() renders epk.html from _epk_kit_context, which merges the saved epk_profiles row over an EMPTY base for a real account (epk_config._EMPTY_PROFILE; the invented _EPK_PROFILE is reached only when _is_demo_email is true) and passes stats_override from the artist's own statements/catalog/metrics. Probe: a fresh account's public kit rendered "Not measured" in every stat slot.
- Routes: GET /epk
- Files: app.py:3336 (epk), 3299 (_epk_kit_context), 3250 (_ensure_epk_slug), 3714 (_epk_real_stats), 3700 (_epk_real_tracks), epk_config.py get_epk_data/real_stats/not_measured_stats, templates/epk.html, templates/_epk_document.html, db.py get_epk/save_epk
- Access: Artist tier or higher — plans.required_tier("/epk") returns "artist" (exact match only). Probe: a Fan plan gets HTTP 402 on GET /epk. Team seats: Marketing room. Partner act-as edits the artist's kit.

**Press kit ZIP download**

Download the public kit's image assets as one zip.

- Because: app.py epk_kit_zip streams public-only epk_assets from the object store or the uploads dir into a zipfile and aborts 404 when nothing was added. Probe: a kit with no assets returned 404; the route is linked from epk_public.html:300.
- Routes: GET /epk/<slug>/kit.zip
- Files: app.py:3914, blob_store.py fetch/is_remote, templates/epk_public.html:300
- Access: Anonymous.

**Private pitch link (EPK share)**

A tokenised, optionally PIN-protected, optionally expiring copy of the kit with up to three Vault audio files, and a first-open-today notification.

- Because: app.py epk_share_save writes epk_shares (token, pin>=4 digits or blank, expires, audio resolved through the artist's own vault listing); epk_pitch enforces expiry (410), the PIN gate (403 on a wrong PIN) and logs view events to epk_share_events, notifying once a day. Probe: POST /epk/share created a share and GET /pitch/<token> returned 200; /pitch/nosuch is 404.
- Routes: POST /epk/share; GET+POST /pitch/<token>; POST /pitch/<token>/play
- Files: app.py:3791 (epk_share_save), 3822 (epk_pitch), 3886 (epk_pitch_play), db.py:2798-2874 (get/upsert/delete_epk_share, log_epk_event, epk_share_stats, epk_viewed_today), templates/epk_public.html (play beacon at line 376), templates/sheet_public.html (PIN gate)
- Access: POST /epk/share: any signed-in account (ungated sub-path — verified on a Fan plan). GET /pitch/<token>: anonymous, PIN only if the artist set one. Team seat: Marketing room, edit access.

**Public partner network page**

The signed-out page naming which distribution partnership exists today.

- Because: app.py partners_page renders public_page.html from public_pages_config.get_partners() — static editorial copy, no partners table read. Distinct from Partner OS despite the name.
- Routes: GET /partners
- Files: app.py:14078 (partners_page), public_pages_config.get_partners, templates/public_page.html
- Access: Anonymous.

**Public press kit page**

The artist's kit at its own slug, with public-only assets and honest stats.

- Because: app.py epk_public reads store.get_epk_by_slug, passes public_only=True assets, and forces stats_override to the artist's real stats or epk_config.not_measured_stats() unless the owner is a demo email — so a real account's public page never carries the seeded catalogue's totals. The slug is minted once by _ensure_epk_slug and never re-minted. Probe: GET /epk/<slug> = 200 containing "Not measured"; an unknown slug is 404.
- Routes: GET /epk/<slug>
- Files: app.py:3754 (epk_public), 3250 (_ensure_epk_slug), db.py get_epk_by_slug (resolves the act's name through artist_identity), templates/epk_public.html
- Access: Anonymous. No tier gate — required_tier("/epk/<slug>") is None by design.

**Recipient status log**

Mark one recipient replied, covered, passed or back to sent, with a note.

- Because: press_desk.recipient_status resolves the row with get_recipient(user_id, id) before writing and press_store.set_recipient_status rejects any status outside RECIPIENT_STATUSES, writing press_recipients scoped by user_id.
- Routes: POST /press-desk/recipients/<recipient_id>/status
- Files: press_desk.py:566, press_store.py set_recipient_status/get_recipient, templates/press/pitch.html
- Access: Any signed-in account (404 on another account's recipient). Team seat: Marketing room, edit access.

**Reseller back office**

The owner's console to create resellers, set seat caps, seat console staff, attach or detach artists and suspend a tenant.

- Because: All six handlers run _owner_or_404 (404, not 403, so the address is not discoverable) and call partner_store directly; create names a taken slug or domain rather than failing silently, attach refuses an account already owned elsewhere and refuses at the seat cap, detach leaves the account and its work intact, and status is a suspend rather than a delete. Probe: an ordinary artist got 404 on /resellers; tests/test_partner_back_office.py covers each write.
- Routes: GET /resellers; POST /resellers; POST /resellers/<pid>/seats; POST /resellers/<pid>/members; POST /resellers/<pid>/artists; POST /resellers/<pid>/artists/<uid>/remove; POST /resellers/<pid>/status
- Files: app.py:10126 (_owner_or_404), 10136 (_partners_view), 10150,10157,10178,10188,10210,10246,10258, partner_store.py create_partner/set_seat_limit/add_member/attach_user/detach_user/set_partner_status, templates/partners_admin.html, tests/test_partner_back_office.py
- Access: Owner accounts only (_is_owner_email, seeded from hashed constants plus the OWNER_EMAILS name); everybody else 404, anonymous redirected to login, and a team seat is refused explicitly because _owner_or_404 aborts when session["team_as"] is set.

**Roster artist detail and removal**

One roster artist's snapshot plus their Release-Ready status rows, and taking them off the roster.

- Because: roster_artist resolves store.get_roster_member(user_id, artist_id) and 404s when the label does not hold that member, then renders the real snapshot and release_ready_store.status_rows (status only — no audio, downloads or buying); roster_remove calls store.remove_roster_member scoped to the label.
- Routes: GET /roster/artist/<artist_id>; POST /roster/<member_id>/remove
- Files: app.py:6794, 6811, db.py get_roster_member/remove_roster_member, release_ready_store.status_rows, templates/roster_artist.html
- Access: Label plan (path gate). Team seat needs the Business room and can_roster for the POST.

**Roster invite and join**

Invite an artist by email to a label's roster and let them accept, signing up or proving an existing account's password.

- Because: roster_invite checks _may_seat(user, "roster") (Label plan, or the owner) and writes store.add_roster_invite, then best-effort emails the join link only when emailer.configured(); roster_join re-checks the label still may seat, requires the existing account's password via _join_existing_ok (the token alone is not proof of who opened it), respects _signup_open() for a new account, then accepts the invite and notifies the label. Probe: invite created a roster_members row and the anonymous join page returned 200.
- Routes: POST /roster/invite; GET+POST /roster/join/<token>
- Files: app.py:6722 (roster_invite), 6745 (roster_join), 6664 (_may_seat), 6690 (_join_existing_ok), db.py:4389 add_roster_invite/get_roster_invite/accept_roster_invite, templates/roster_join.html
- Access: /roster/invite: Label plan or the owner (_may_seat), and Label tier by path gate; a non-Label account is redirected to /upgrade?why=roster. /roster/join/<token>: anonymous and untiered by design (plans.required_tier excludes /roster/join/). Team seats are blocked from /roster/join outright (app.py _TEAM_BLOCKED).

**Roster report export**

CSV of the roster with revenue, fans, links, shows, passport and clean-release averages, rights reds and certification.

- Because: app.py roster_export writes one row per active member from the same _artist_snapshot and _os_full calls the page uses and returns text/csv with a Content-Disposition. Probe: Label plan 200, artist plan 402.
- Routes: GET /roster/export.csv
- Files: app.py:6638, templates/roster.html
- Access: Label plan (402 below it).

**Save press kit to the Vault**

File a dated, self-contained HTML copy of the kit in the artist's Vault.

- Because: app.py epk_vault_save renders epk_saved.html from the same _epk_kit_context the editor uses, inlines the photo and logo as data URIs, embeds the built tailwind.css, writes through blob_store.save and records a vault_files row of kind press_kit. Probe: one press_kit row existed in the Vault afterwards. The page states plainly that this server has no PDF engine (nothing in requirements.txt renders one) and that the copy prints to PDF from a browser.
- Routes: POST /epk/vault-save
- Files: app.py:3377 (epk_vault_save), 3293 (_saved_press_kits), templates/epk_saved.html, templates/_epk_document.html, blob_store.py save, db.py add_vault_file/list_vault_files
- Access: Any signed-in account (ungated sub-path — succeeded on a Fan plan). Team seat: Marketing room, edit access.

**The page a journalist opens (per-recipient announcement)**

One announcement at one recipient's own token URL, with the embargo shown and the first open notified to the artist.

- Because: press_desk.press_page resolves the token to a recipient, reads the pitch and the release owner-blind (get_release_any — the token is the authorisation), renders press_release_public.html and calls mark_opened, which increments open_count and returns the row only on the FIRST open so store.notify fires once. A team seat or an acting partner viewing it is excluded from counting as an open (session team_as / acting_as check). Probe: anonymous GET returned 200 and moved the recipient from prepared to opened with open_count 1.
- Routes: GET /press/<token>
- Files: press_desk.py:603 (press_page), press_store.py get_recipient_by_token/mark_opened/embargo_active, templates/press_release_public.html, db.py notify
- Access: Anonymous — no account, no PIN. An unknown token is a 404 (probe: /press/nosuchtoken = 404).

### Partial

**EPK save / photo / assets**

Persist the editor's fields, the artist photo and the four asset slots (press photo, logo, cover art, live photo), including picking an image from the Vault.

- Because: Every write works and persists — normalize_epk_overrides validates and store.save_epk/save_epk_photo/save_epk_asset/set_epk_asset_public/delete_epk_asset write epk_profiles and epk_assets, and the delete routes unlink only files this uploader wrote (epk_<user>.<ext>, epkasset_<user>_<kind>.<ext>). The gate does not hold: required_tier matches "/epk" exactly, so every sub-path is ungated — probe on a Fan account: POST /epk/save returned {"ok": true} and the tagline was stored, POST /epk/share and POST /epk/vault-save both succeeded (302), while GET /epk was 402. A Fan can build and publish a kit it cannot open the editor for.
- Routes: POST /epk/save; POST /epk/photo; POST /epk/photo/delete; POST /epk/asset/<kind>; POST /epk/asset/<kind>/visibility; POST /epk/asset/<kind>/delete; POST /epk/asset/<kind>/from-vault
- Files: app.py:3945 (epk_save), 3969 (epk_photo), 3979 (epk_photo_delete), 3430 (epk_asset_upload), 3449 (epk_asset_visibility), 3457 (epk_asset_delete), 3897 (epk_asset_from_vault), epk_config.py normalize_epk_overrides, db.py:2070-2155, templates/epk.html (fetch calls at lines 456,516,545,583,602,622,633)
- Access: Any signed-in account including Fan (see above). Team seat: Marketing room, edit access. Anonymous gets 401 JSON from each.

**Merch / store embed on a press kit**

A Shopify Buy Button block under the kit's Merch heading.

- Because: app.py _epk_store returns shopify_buy.context() ONLY when the kit owner is the owner email or a demo email, and None for everybody else — the comment records that the embed is the server's own store and used to appear on every artist's kit. Other artists get the store_url and merch items they typed into the editor (epk_config.normalize_epk_overrides store_url/merch), which are plain links, not an embed.
- Routes: GET /epk/<slug>; GET /pitch/<token>
- Files: app.py:3739 (_epk_store), shopify_buy.py context (reads SHOPIFY_DOMAIN, SHOPIFY_STOREFRONT_TOKEN, SHOPIFY_COLLECTION_ID), epk_config.py normalize_epk_overrides, templates/epk_public.html
- Access: Anonymous readers of the public/pitch pages; the embed itself is owner/demo-only.

**One-sheet share settings**

Create, regenerate or disable the /sheet/<token> link and pick its banner and audio.

- Because: The endpoint works server-side — it writes onesheet_shares through store.upsert_onesheet_share, resolves banner and audio through the artist's own vault listing, and tests/test_app.py:4858 posts to it — but no page in the app posts to it any more: grep for "onesheet" across templates/ returns zero matches, and the page that held the form now 301s to /epk. An artist cannot create or disable a one-sheet share from the UI; the replacement is the EPK's own /epk/share.
- Routes: POST /onesheet/share
- Files: app.py:7208 (onesheet_share_save), db.py upsert_onesheet_share/delete_onesheet_share; no template posts to it
- Access: Artist tier or higher (plans._PRO_PATHS contains "/onesheet" — probe: a Fan plan got HTTP 402). Team seat: not in any room's path map, so a seat with fewer than all rooms is refused.

**Partner branding (white-label identity)**

The name, logo, tagline and accent colour a reseller's artists see instead of Street Banker's.

- Because: All four save and render. The accent is validated with brand_contrast.check_accent against the real token sheet (tools/tailwind-input.css) before pstore.set_branding writes it, and every save is audited. The LOGO became settable 2026-09-21: partners.logo_path had existed since Partner OS shipped and base.html and auth_base.html had always rendered brand.logo, but nothing had ever written it, so every tenant showed a name where their mark should have been. partner_os._save_logo now takes a PNG, JPG or WebP up to 2 MB (white_label.LOGO_EXTENSIONS / LOGO_MAX_BYTES), verifies it with Pillow when Pillow is installed, writes it to the same uploads directory as every other upload in this app under a name the uploader does not choose (partnerlogo_<partner_id>_<unix>.<ext>), and stores "/uploads/<name>". A remove_logo checkbox clears the row and unlinks the file; a replacement unlinks the one it replaced; a refused save writes nothing and deletes the file it had just written. SVG is refused on purpose and the screen says why: an SVG is a document, it is served same-origin with every artist's session from /uploads, and opened directly its script runs.
- Because (the accent's reach): It used to reach the wordmark and stop. brand_style (app.py inject_brand -> white_label.accent_vars) now declares --sb-brand-accent on :root for a tenant and nothing at all for the platform, and static/css/white-label.css spends it on the focus ring (--sb-focus), .sb-label-gold, .sb-eyebrow, .sb-plate-eyebrow, .sb-btn-secondary/.sb-btn-ghost hover edges and .sb-subnav-a.is-active. Filled buttons (.sb-btn-primary) take it only when --sb-brand-fill is also declared, which white_label.accent_fill_ok grants only when the better of two inks on the accent clears AA for body text — the save-time gate proves the accent is readable AS INK on a dark sidebar and proves nothing about text sitting ON it. When it is refused the branding screen says so in words rather than quietly using gold. Tailwind's amber/gold utilities do NOT move: the build compiles them to literal colours.
- Routes: GET+POST /partner/branding (multipart)
- Files: partner_os.py branding(), _save_logo(), _forget_logo(), _uploads_dir(), _brand_surfaces(); white_label.py LOGO_EXTENSIONS/LOGO_MAX_BYTES/accent_ink/accent_fill_ok/accent_vars; partner_store.py set_branding/branding; brand_contrast.py check_accent; static/css/white-label.css; templates/partner/branding.html; app.py config["UPLOADS_DIR"]; tests/test_white_label_titles.py
- Access: A seat holding "branding_edit" — owner and admin only. No seat = 404. Team seats blocked. The upload is inside the same @require("branding_edit") guard, so a tenant's artist posting to it gets 404.
- Not done: the installed app's ICONS still come from static/img/icon-192.png and icon-512.png on every tenant. A tenant logo is any aspect ratio; a maskable 192 and 512 PNG is a separate artefact that would have to be generated from it.

**Partner console home and monthly statement**

A reseller's own overview: how many accounts it owns and what it will be invoiced this month.

- Because: The roster count and the arithmetic are real — partner_store.roster(partner_id) is tenant-scoped and partner_billing.statement() prices each seat from stripe_provider.PRICES at a 40% discount plus a flat platform fee. Nothing charges: partner_billing's own docstring says the owner invoices by hand, and templates/partner/home.html prints "nothing is charged from this page". No Stripe call is made anywhere in this path. Probe: a seated owner-role member got 200.
- Routes: GET /partner/
- Files: partner_os.py:94 (home), partner_billing.py statement/seat_price_cents, partner_store.py roster, templates/partner/home.html, templates/partner/_shell.html
- Access: A partner seat holding "view" (every role). No seat is a 404, not a 403 (partner_os.require). Anonymous is redirected to /login. Team seats can never reach it — "/partner" is in app.py _TEAM_BLOCKED. Plan tier is irrelevant; the seat is the gate.

**Press kit attached to a pitch**

Choose the public kit's link or a Vault-saved copy to fill {kit}, and attach the saved copy on a platform send.

- Because: The link half is real: _kit_choices builds from store.get_epk slug and store.list_vault_files of kind press_kit, and create_pitch substitutes it into every message (verified in code and by the saved-kit row a probe created). The attachment half never runs on this deployment: _kit_bytes → base64 is only reached inside pitch_send after send_state()["platform"] is true, which needs both RESEND_API_KEY and EMAIL_FROM.
- Routes: POST /press-desk/pitch/new (kit field); POST /press-desk/pitch/<pitch_id>/send
- Files: press_desk.py:110 (_kit_choices), 129 (_kit_bytes), 498 (pitch_send), press_store.py create_pitch kit_link/kit_file_id, press_store.py init_press adds press_pitches.kit_file_id
- Access: Any signed-in account (the kit list reads the same account the request works in). Team seat: Marketing room, edit access.

**Tour dates on the press kit**

Upcoming shows on the kit, from the artist's own TOUR first and Bandsintown only as a fallback.

- Because: app.py _epk_tour_dates returns tour_dates_feed.epk_rows(user_id) whenever TOUR holds confirmed/advanced upcoming dates, and the page is told the source. The Bandsintown fallback is dormant: bandsintown_provider.configured() requires BANDSINTOWN_APP_ID, which is unset here, so upcoming_events()/artist_info() return nothing.
- Routes: GET /epk; GET /epk/<slug>; GET /pitch/<token>
- Files: app.py:3272 (_epk_tour_dates), bandsintown_provider.py:27,59,83, epk_config.py get_epk_data tour_dates/tour_source
- Access: Follows the page it is on: /epk artist-tier, the public pages anonymous.

**White-label tenant resolution and branded shell**

Deciding which reseller's front door a request is at, and painting its name through every page.

- Because: Host resolution works: resolve_partner matches partners.domain exactly, then a <slug>.<PARTNER_ROOT_DOMAIN> subdomain, and inject_brand hands `brand`, `product_name` and `brand_style` to every template. Probe on a partner domain: the login page and the signed-in shell both rendered "Foxglove Music" with no streetbanker-logo. The seat fallback is staff-only: when no host matches it reads partner_store.member_for_user (partner_members), never users.partner_id — so a reseller's ARTIST reaching the plain address gets Street Banker's brand (probe: seated artist, plain host, GET /overview = 200 with no tenant name). /terms and /privacy deliberately stay Street Banker's: neither template reads `brand` and probe on the partner domain showed "Street Banker" and no "Foxglove".
- Because (the tab): fixed 2026-09-21. base.html printed a literal `Royalty Sweep by Street Banker` with no substitution at all, and 151 leaf templates overrode that block with the product name baked into their own title, so a reseller's artist read Street Banker in the browser tab on nearly every page. The four frames that own a <title> (base.html, auth_base.html, public_base.html, tour/_public.html) now capture the page's own block and compose `<page> - {{ product_name }}`; 164 leaves name only the page. 18 more templates carry their own <title> and extend no frame at all (epk_public, sheet_public, sign, team_join, roster_join, link_campaign, sync_pack_public, report_executive, clean_certificate, release_check, release_signal, artist_twin_start, onboarding, landing_split, public_page, product_tour_smart_link, link_campaign_unavailable, board/renewed) and each reads product_name directly. white_label.product_name returns the tenant, else "Royalty Sweep" on plans._SWEEP_MARK_PATHS and "Street Banker" everywhere else — the rule the sidebar wordmark has followed since 2026-09-14, so the tab and the wordmark now agree where nineteen pages used to contradict each other.
- Because (the install card): fixed 2026-09-21. static/manifest.json is a fixed file naming Street Banker, so an artist installing a tenant's app to a home screen got the platform's name under the icon. GET /manifest.webmanifest renders it per tenant (name, short_name, description from the tagline) with Vary: Host, and base.html points a tenant at it. Street Banker's own pages keep the static file: it is the name static/js/sw.js precaches and it is cacheable at the edge. The path is in _PUBLIC_EXACT because a browser fetches a manifest with no cookie.
- Because (the mail): fixed 2026-09-21. email_provider.sender() had swapped the display name since 2026-09-10, but the words inside four messages still named the platform: the password reset (subject AND body), the team invite (subject AND body), the roster invite ("runs their label on Street Banker") and the plan grant (subject AND "your Street Banker account"). All four read white_label.product_name and escape it. email_provider._tenant_display_name now delegates to white_label.tenant_name, so the sender's name and the message body cannot disagree.
- Routes: before_request on every route (app.py _resolve_partner); context processor on every template; GET /manifest.webmanifest
- Files: app.py resolve_partner(), _resolve_partner(), inject_brand(), tenant_manifest(), _PARTNER_ROOT, _PUBLIC_EXACT; white_label.py product_name/page_title/tenant_name/accent_vars; partner_store.py partner_by_domain/partner_by_slug/member_for_user/branding; templates/base.html head, public_base.html, tour/_public.html, auth_base.html; static/css/white-label.css; email_provider.py sender/_tenant_display_name; tests/test_partner_os.py, tests/test_white_label_brand.py, tests/test_white_label_titles.py
- Access: Applies to everyone including anonymous visitors; a suspended partner resolves to nothing (status must be 'active'), and any exception falls back to no tenant.
- Because (the page band): found by walking the product as a tenant's artist, not by reading. Every internal page opens with the shared plate band and its eyebrow read "STREET BANKER", directly above the reseller's own name in the sidebar. templates/_sb.html's plate() macro and templates/partials/plate.html now pass the eyebrow through brand_text(). That is registered as a Jinja GLOBAL (app.py, white_label.brand_text) and not handed over by the context processor, because templates/_sb.html is pulled in with {% import %}, which is context-free: a first attempt that read `brand` inside the macro compiled, rendered, and silently changed nothing on every page. With no tenant brand_text returns its argument untouched, so the platform's own eyebrow is byte-identical.
- The two exceptions, in the tab as well as the body: /terms and /privacy kept naming Street Banker in their plate and their sections, but after the sweep their TAB read the reseller like every other page. templates/legal.html sets title_product = "Street Banker", which base.html and public_base.html prefer over product_name. It is the only use of that variable and the only page that should have one.
- Locked: tests/test_white_label_titles.py::test_no_page_bakes_the_product_name_into_its_own_title reads every template in templates/ and fails on any title naming the product, so a page that does not exist yet cannot reintroduce the leak. Six templates are exempt and named there: the four frames, which compose the brand once, and desk/layout.html + desk/denied.html + signal/_shell.html + signal/denied.html, which are Street Banker's own staff tools behind operator_desk.require / signal_hub.require and are not part of what a reseller sells.
- Still Street Banker's on a tenant's domain, and deliberately left so: page BODY copy. The tab, the shell, the page band, the mail and the manifest are swapped; sentences inside pages are not. Counted on one screen (Command Center, signed in as a tenant's artist): the page eyebrow in templates/command_center.html, the "Royalty Sweep & Banking" nav hub and heading from hubs.py, a "Street Banker Certified" module card, the "Ask Street Banker" assistant title, and "Your Street Banker sign-in opens them" in the suites band. Also templates/sweep_method.html and templates/certified.html throughout; app.py's invite-only and locked-account messages ("Contact Street Banker"); the demo-tour fine print on the sign-in door (templates/partials/login_demo_tour.html: "so we can follow up about Street Banker"), which is a true statement about who keeps the address and would become false if swapped; and the "Powered by Street Banker" mark on the public share pages (epk_public, link_campaign, club_public, club_members, artist_hub, rider, showday, cleared_public, roster_join). Each is a copy or attribution decision rather than a substitution, and each is the owner's call.

### Stubbed

**Press kit PDF export**

Names a PDF file for the press kit.

- Because: app.py epk_export builds get_epk_data, derives a filename and returns jsonify({"ok": True, "filename": "...-press-kit-YYYYMMDD.pdf"}) — no PDF is rendered, nothing is written and nothing is returned to download. Probe: POST /epk/export returned {'filename': 'probe-artist2-press-kit-20260920.pdf', 'ok': True} with no file created. No template or script calls it: grep for "epk/export" across templates/, static/ and *.py finds only this handler and tests/test_app.py:667.
- Routes: POST /epk/export
- Files: app.py:4028 (epk_export), tests/test_app.py:667
- Access: No sign-in check in the handler at all — it calls current_user() but tolerates None; the global login wall is what stops an anonymous POST. Ungated sub-path, so any plan.

**Send pitches from Street Banker**

Email every prepared message in a pitch, one address at a time, and mark each recipient from its own result.

- Because: press_desk.send_state() refuses unless emailer.configured() (RESEND_API_KEY) AND not using_shared_test_sender() (EMAIL_FROM); with neither set the route renders press/blocked.html with HTTP 409 and sends nothing — probe: POST /press-desk/pitch/<id>/send returned 409 and no recipient changed state. The send loop, per-recipient mark_sent, last_contacted write and mark_pitch_sent are real code that only runs once both env names are set; nothing was executed against Resend here.
- Routes: POST /press-desk/pitch/<pitch_id>/send
- Files: press_desk.py:82 (send_state), 498 (pitch_send), 547 (_as_html), press_store.py mark_sent/mark_pitch_sent, email_provider.py configured/using_shared_test_sender/send, templates/press/blocked.html
- Access: Any signed-in account. Team seat: Marketing room, edit access. The refusal is deployment-wide, not per plan.

### Dead code

**Pitch send result / missing-kit notice**

The counts of sent and failed messages, and the warning that a saved kit could not be attached.

- Because: press_desk.py writes session["press_send_result"] (line 527) and session["press_kit_missing"] (line 512) and nothing ever reads them: grep for both names across templates/, static/ and every *.py returns only those two write sites. The pitch page after a send shows no count and no warning.
- Routes: POST /press-desk/pitch/<pitch_id>/send (writer); no reader
- Files: press_desk.py:512, press_desk.py:527; templates/press/pitch.html (reads only `skipped`)
- Access: n/a — the values never reach a page.

## Platform and plumbing

54 features: 33 Live, 18 Partial, 1 Stubbed, 2 Dead code.

### Live

**Acting-on-behalf audit**

Records every change a partner staff member makes while acting as one of their artists.

- Because: app.py:5193 reads the actor before the view can end the act-on-behalf and app.py:5188 writes partner_store.audit(...) after, again only on url_rule is not None and status < 400. GET/OPTIONS/HEAD, /partner/*, /logout and /static/ are skipped.
- Routes: every state-changing request while session['acting_as'] is set
- Files: app.py:5192-5212; partner_store.py audit()
- Access: n/a

**Backup state panel on Settings**

Shows whether an off-box target is configured, where it points, and what the last run did.

- Because: app.py:13736-13754 _backup_state() reads the stored backup_last_run record out of app_kv and backup_store.target() (backup_store.py:44, which never includes credentials); passed into templates/settings.html at app.py:13305-13306. Probed /settings as a signed-in account: 200.
- Routes: GET /settings
- Files: app.py:13736-13754, app.py:13305-13306; templates/settings.html
- Access: Any signed-in account sees the page; can_backup (and therefore the download button) is owner-only

**Bucket-object manifest inside the backup**

Writes OBJECTS.csv naming every stored object and whether it made it into the archive.

- Because: app.py:13700-13731 calls blob_inventory.stored_keys(db) (blob_inventory.py:35, a generic sqlite_master + text-column sweep for "r2:" values), fetches each, writes it under objects/ while under BACKUP_BLOB_BUDGET and records key,bytes,in_this_archive either way. With R2 unconfigured the manifest says so rather than being omitted. tests/test_backup_objects.py (5 tests) holds it.
- Routes: part of GET /backup and POST /backup/run
- Files: app.py:13700-13733; blob_inventory.py
- Access: Same as /backup

**Core schema + additive migrations**

init_db() creates ~94 tables and runs guarded ALTER TABLE / table-rebuild migrations on every boot.

- Because: db.py:56 init_db() executescript of the CREATE TABLE block, then ~30 try/except ALTER blocks (db.py:968-1310) and two full table rebuilds for pulse_snapshots / pulse_peer_snapshots; called unconditionally at app.py:734 inside create_app().
- Routes: none
- Files: db.py:56-1314 (init_db), db.py:1316 _migrate_collab_profiles, db.py link_song_tables()/link_document_store() called at end of init_db
- Access: n/a — runs at process start

**Database path fallback**

If DATABASE_PATH's directory cannot be created the app silently drops to instance/streetbanker.db and prints a warning.

- Because: db.py:33-46 catches OSError around os.makedirs and reassigns path; the same fallback is repeated for uploads at app.py:3194-3203. Data written after a fallback is ephemeral and nothing on any page says so.
- Routes: none
- Files: db.py:32-52; app.py:3194-3203
- Access: n/a

**Deployment readiness page**

One owner page saying which of the deployment's capabilities are actually configured, by variable name only.

- Because: readiness.py:318 init registers GET /admin/readiness (readiness.py:323); it redirects an anonymous visitor to login and abort(404)s a non-owner (probed: 404 for a plain account, 200 for an owner). Rows are built by _try/_call wrappers (readiness.py:34-56) so a raising provider is reported rather than 500ing the page, and the module docstring states the rule it holds: a key is a presence check, not a capability. 15 tests in tests/test_readiness.py.
- Routes: GET /admin/readiness
- Files: readiness.py:1-400; templates/admin_readiness.html; registered at app.py:14483
- Access: Owner only (_is_owner_email), 404 to everyone else; blocked for team seats by the /admin prefix in _TEAM_BLOCKED

**Design system tokens and Tailwind build**

One gold ramp, one ink ramp, a fixed type and radius scale, spelled as CSS custom properties and as Tailwind theme keys.

- Because: tools/tailwind-input.css (23 KB) defines the --sb-* custom properties the 44 hand-written sheets in static/css read, and tools/tailwind.config.js redefines the stock amber/green/gray families onto the brand ramps so `text-amber-500` cannot be Tailwind's colour any more. static/css/tailwind.css (86 KB) is the committed build output. tests/test_design_system.py (16 tests) fails on any colour literal outside the token set, any font-size under 12px, any radius outside {0, 6px, 10px, 50%, 999px}, and measures ink-2/ink-3 contrast on every surface; tests/test_stylesheet.py (7 tests) fails when the committed sheet is missing a class the templates use or when a template still pulls cdn.tailwindcss.com.
- Routes: served as /static/css/*.css
- Files: tools/tailwind-input.css, tools/tailwind.config.js, static/css/tailwind.css + 44 sheets; brand_contrast.py (the WCAG maths the test imports)
- Access: Anonymous (static)

**Downloadable DMX bridge**

A 152-line localhost UDP forwarder the Light Studio hands the operator, because a browser cannot open a socket.

- Because: It is a real served asset with a real door: templates/lights.html:150 offers <a href="/static/tools/lx-bridge.py" download>, line 149 has a "Check bridge" button and line 153 prints the command to run it; tests/test_light_studio.py:46 asserts those control ids are on the page.
- Routes: GET /static/tools/lx-bridge.py
- Files: static/tools/lx-bridge.py; templates/lights.html:148-153
- Access: Anonymous to download (under /static/); the Light Studio page itself is artist-tier and Tour-suite gated

**Full-database backup download**

Zips a consistent SQLite copy plus the uploads directory plus bucket objects and hands it over as a file.

- Because: app.py:13757 builds the zip via app.py:13672 _snapshot_zip(), which uses sqlite3's backup API (not a file copy), walks UPLOADS_DIR, and then fetches every r2: key the database references. Probed as an owner: 200, application/zip, Content-Disposition streetbanker-backup-<date>.zip. Probed as a plain signed-in account: 404.
- Routes: GET /backup
- Files: app.py:13756-13765 (route), app.py:13672-13734 (_snapshot_zip), app.py:13257-13285 (_backup_allowed / _backup_allowed_for), app.py:168 BACKUP_BLOB_BUDGET
- Access: Owner only — _is_owner_email (app.py:105) or the legacy OWNER_EMAIL address; never a demo login; never while a team seat or a partner is acting (app.py:13257). Plan is irrelevant. Blocked for team seats by _TEAM_BLOCKED (app.py:5085).

**Hypeddit webhook receiver**

One per-account address that files Hypeddit download-gate signups into the Fan CRM.

- Because: app.py:1324 resolves the token to an account (hypeddit_ingest.user_for_token), 404s an unknown one (probed: GET /webhooks/hypeddit/zzz → 404), answers GET with {"ok": true, "listening": true} for tools that ping first, and always answers 200 on POST so a delivery is never retried into a duplicate. Held by tests/test_hypeddit_webhook.py (15 tests).
- Routes: GET|POST /webhooks/hypeddit/<token>; rotate at POST /links/fans/hypeddit/rotate
- Files: app.py:1323-1350; hypeddit_ingest.py:114 (address builder)
- Access: Anonymous; the token in the URL is the authorisation

**Key-value store (app_kv)**

A plain server-side string store used for owner settings, the last backup record and the stored Stripe webhook secret.

- Because: db.py:2033 get_kv / 2041 set_kv / 2049 delete_kv / 2055 kv_incr all read and write the real app_kv table. Keys actually written (grepped set_kv literals): backup_last_run, reminders_last_run, reminders_last_scheduled_run, home_layout, nav_layout, page_switches, shopify:storefront, stripe_webhook_secret, stripe_ref_coupon_50, stripe_open_checkout:*, stripe_cs_done:*, rr_* (six Release-Ready settings). Note: a live Stripe webhook signing secret is stored here in plaintext (stripe_provider.py:86) and therefore lands in every /backup zip.
- Routes: none (library)
- Files: db.py:960-964 (CREATE TABLE app_kv), db.py:2033-2066; stripe_provider.py:86-106; page_switches.py:20
- Access: n/a — callers gate

**Login wall and plan gate**

One before_request that bounces anonymous requests, enforces the path tier gate and the suite doors.

- Because: app.py:4957 plan_gate(): public paths and a valid backup token pass; /backup/run POST gets the explicit 403; everything else anonymous redirects to /login?next=. Then plans.required_tier(request.path) renders upgrade.html with 402 for an under-tier plan, and plans.path_suite / suite_open gates The Room and Tour behind credits or Pro. Probed: anonymous /nonexistent-page → 302, /storage/diag → 302; signed-in artist /backup → 404.
- Routes: every request
- Files: app.py:4956-4991; plans.py (TIER_RANK, PLANS, required_tier:78, SUITE_ACCESS:95, gates_on:128, path_suite:139, suite_open:166, allowed:196)
- Access: n/a — it is the gate. Suite gates are on wherever RENDER is set or SUITE_GATES=on (plans.py:128), off on a laptop and in tests.

**Mail diagnostic**

Reports the shape of the mail setup and, on request, Resend's view of the account's domains.

- Because: app.py:1744 returns configured/sender/using_shared_test_sender/email_from_set/inbound_domain/webhook_secret_set as booleans and names, never values. Same unreachable-401 note as /storage/diag: anonymous is redirected by plan_gate.
- Routes: GET /mail/diag (and ?domains=1)
- Files: app.py:1743-1763
- Access: Any signed-in account — no owner gate, although it reports deployment configuration

**Object-storage round-trip diagnostic**

Writes, signs, reads back and deletes one tiny object, and names which R2 variable has the wrong shape.

- Because: app.py:1819 calls app.py:1765 _r2_check() (a real put/presigned get/delete) and blob_store.py:269 diagnose(), which reports lengths, hex-ness and whether two variables hold the same string — never a value — and does a TLS-SNI handshake to tell a wrong account id from a wrong credential. Probed unconfigured: 200 {"configured": false, "next": "Set R2_ACCOUNT_ID, ..."}. 3 tests in tests/test_storage_diag.py.
- Routes: GET /storage/diag
- Files: app.py:1765-1817 (_r2_check), app.py:1818-1859 (route); blob_store.py:269-370 diagnose()
- Access: Any signed-in account. The handler's own 401 for user is None is unreachable — plan_gate redirects anonymous callers to /login first (probed: 302), so the docstring and the behaviour disagree.

**Offline fallback page**

Shown after a navigation fails twice, and it words itself from navigator.onLine rather than asserting the reader is offline.

- Because: static/offline.html is precached by the worker (static/js/sw.js:19 PRECACHE) and served by retryThenFallback (sw.js:35-44) only on the second failure; the page's own script re-words the heading and retries on a 3/6/12/30s backoff. tests/test_offline_fallback.py (5 tests) reads both files and asserts the retry and the wording.
- Routes: served by the service worker, not a Flask route (also reachable as GET /static/offline.html)
- Files: static/offline.html; static/js/sw.js:35-44
- Access: Anonymous

**Page switchboard**

The owner turns any sidebar page live or hidden from Settings, without a deploy - and, from 2026-09-23, any room card that is not a sidebar entry (rooms.EXTRA: Fan Club, Tax, Contracts, Track Passports, the two release views, Distribution...), each a switch of its own after its parent's row. A VIEW page (/statements?view=tax is Tax) bounces only when the request asks for that view: hidden_for_path() takes request.args, matches a querystring entry first, and falls back to the longest plain prefix, so hiding Tax leaves /statements open and hiding Statements still takes the tax view with it. A page in no room (Signal, the three folded press pages, Connections) is not a switch and follows its parent through rooms.hidden_keys(). 8 tests in tests/test_page_switches.py.

- Because: page_switches.py reads one app_kv override on top of the shipped sidebar (hubs.py) — hidden_keys() returns an empty set on a missing or corrupt value, PROTECTED pins command-center and settings. app.py:5206 page_switch_gate redirects a non-owner off a hidden page to /command-center?off=<label> using the longest-prefix match (page_switches.py:74 hidden_for_path). Saved by POST /admin/pages (app.py:5224), owner-only. (see above)
- Routes: every request; POST /admin/pages
- Files: page_switches.py (3.5 KB, whole file); app.py:5199-5232
- Access: Owners see hidden pages badged and are the only ones who can save; everyone else is bounced

**Per-module schema bootstraps**

Five feature modules create their own tables when create_app() runs, outside db.init_db.

- Because: app.py:14450 lights_store.init_lights(), 14455 partner_store.init_partners(), 14460 audio_store.init_audio(), 14466 studio_store.init_studio(), 14471 live_store.init_live() — all unconditional. Other stores (board_store, press_store, signal_store, tour_store, desk_store, passport_store, release_ready_store, acr_store, stage_store) create tables lazily on first use rather than here.
- Routes: none
- Files: app.py:14450-14471; lights_store.py, partner_store.py, audio_store.py, studio_store.py, live_store.py
- Access: n/a

**Read-only demo lock**

A locked demo account can read everything and change nothing; a form is bounced, a fetch gets 403 JSON.

- Because: app.py:5044 demo_lock_gate() returns early on GET/OPTIONS (explicitly counting HEAD as a write, since Flask answers HEAD with the GET view), allows only five paths (app.py:5075), and branches on _wants_json (app.py:5030, which reads Accept, Sec-Fetch-Mode and Sec-Fetch-Dest). The lock is a real users.demo_lock column (db.py migration ~1105) set by POST /admin/demo-lock (app.py:5288), owner only, and an owner account cannot be locked. 6 tests in tests/test_demo_lock.py.
- Routes: every state-changing request; POST /admin/demo-lock
- Files: app.py:4993-5041 (_demo_locked_account, _DEMO_LOCK_ALLOWED, _wants_json), app.py:5043-5071, app.py:5284-5305; db.py:1503 set_demo_lock, :1509 is_demo_locked, :1515 list_demo_locked
- Access: Lock/unlock is owner only (404 otherwise). The lock itself applies to the locked account and to anyone acting as it.

**Release-Ready background worker threads**

Runs one job step off-request on a daemon thread, at most four per process.

- Because: release_ready.py:633 _SEM = threading.BoundedSemaphore(4); release_ready.py:636 _spawn acquires non-blocking, starts a daemon Thread named "release-ready", releases in finally, and returns False when full so the job simply stays due. This is the only background thread the running app starts — grepped threading.Thread across all .py: acr_console.py and stage_adapters.py use only locks/thread-locals, audio_elevenlabs.py only a Lock, and tools/stage_bridge_daemon.py is a separate program.
- Routes: none; triggered by the RoEx webhook and by run_due()
- Files: release_ready.py:61, :633-652
- Access: n/a — server-side

**Request body ceiling and the "file too large" page**

Caps every request at 210 MB and answers an oversize one with an explanatory page instead of Werkzeug's bare error.

- Because: app.py:628 sets MAX_CONTENT_LENGTH = 210*1024*1024 (probed: 220200960); app.py:630-645 errorhandler(413) renders templates/too_large.html or JSON. Probed a 211 MB multipart POST to /vault/upload: 413 with the HTML page. tests/test_upload_limits.py asserts every advertised cap in the codebase is <= this number.
- Routes: any POST; error page only
- Files: app.py:628-645; templates/too_large.html
- Access: Whoever reached the route

**Reseller tenant resolution**

Resolves which white-label partner a request's hostname belongs to, before the login wall runs.

- Because: app.py:4899 resolve_partner() matches a custom domain first, then a <slug>.<PARTNER_ROOT_DOMAIN> subdomain, then a partner seat on the session; it is read-only, sets g.partner / g.partner_member and returns nothing, and the whole body is wrapped so a missing or mid-migration partner table cannot take a page down. Registered before plan_gate at app.py:4948.
- Routes: every request
- Files: app.py:4899-4954; app.py:84 _PARTNER_ROOT; partner_store.py
- Access: n/a

**robots.txt**

Disallows the share-link prefixes and the auth pages so a crawler cannot index a tokenised private link.

- Because: app.py:8478 builds the body from the _NO_CRAWL tuple at app.py:8469-8475 and returns text/plain. Probed: 200. Locked by tests/test_static_caching.py.
- Routes: GET /robots.txt
- Files: app.py:8469-8489
- Access: Anonymous

**RoEx webhook receiver**

A per-job callback that marks a Release-Ready job due now; the body is never read for a status.

- Because: release_ready.py:2191 compares sha256(token) against the job's stored webhook_token_hash with hmac.compare_digest and 404s both an unknown job and a wrong token; on a match it touches the job and spawns a step. The address is only minted when PUBLIC_BASE_URL starts https:// (release_ready.py:675-688), and only the hash is kept. Held by tests/test_roex_release_ready.py (100 tests).
- Routes: POST /webhooks/roex/<jid>/<token>
- Files: release_ready.py:2191-2213; release_ready.py:675-688 _webhook_for; registered via release_ready.init at app.py:14489
- Access: Anonymous; the per-job token is the authorisation

**Runtime colour check for reseller accents**

Checks a partner's chosen accent against WCAG AA at the moment it is saved, because the design lock cannot see a database value.

- Because: brand_contrast.py implements WCAG 2.1 luminance and contrast ratio with AA_NORMAL=4.5 / AA_LARGE=3.0, and tests/test_design_system.py imports it rather than keeping a second copy. Used at the partner branding save path.
- Routes: partner branding save (partner_os.py)
- Files: brand_contrast.py (3.4 KB); tests/test_design_system.py
- Access: Partner owner

**Sandbox marking**

Stamps a red strip and a [SANDBOX] tab title on every HTML page of a throwaway deployment, and switches email, Stripe and R2 off.

- Because: sandbox.py:35 active() reads SANDBOX; sandbox.py:66 mark() injects the bar before </body> and rewrites <title>. The after_request at app.py:14405 is registered unconditionally but returns the response untouched when not active, and skips direct_passthrough and non-HTML. The three providers each consult it in their own configured(): email_provider.py:24, blob_store.py:67, and stripe_provider. 8 tests in tests/test_sandbox.py.
- Routes: every HTML response
- Files: sandbox.py (whole file); app.py:14404-14422
- Access: n/a — inert unless SANDBOX is set

**Service worker**

Caches /static/ cache-first, keeps pages network-first, and caches three TOUR pages for a venue with no signal.

- Because: app.py:8457 serves static/js/sw.js from the root with Cache-Control: no-cache (probed: 200, no-cache). Registered from templates/base.html:7, landing.html:25 and landing_split.html:53. static/js/sw.js VERSION = "sb-v270"; TOUR_PAGE regex at line 22 matches /tours/<32hex>(/my-day|/shows/<32hex>).
- Routes: GET /sw.js
- Files: app.py:8456-8462; static/js/sw.js (76 lines); templates/base.html:7
- Access: Anonymous

**Shared component macros (sb.*)**

27 Jinja macros — button, badge, kpi, plate, meter, lamp, subnav, instrument and the rest — that every page is built from.

- Because: templates/_sb.html defines 27 macros (grepped ^{% macro); the not-found page (templates/not_found.html:12) and every internal page open with sb.plate, which the internal-page cohesion rule requires. tests/test_instruments.py (16), tests/test_meters.py (9), tests/test_landmarks.py (8) and the fold/lamp tests hold their shape.
- Routes: n/a (template library)
- Files: templates/_sb.html (macros at lines 24, 48, 61, 95, 124, 145, 175, 199, 232, 236, 247, 264, 275, 283, 306, 341, 365, 375, 383, 398, 410, 423, 441, 458, 514, 533, 544); meters.py (geometry); brand_contrast.py
- Access: n/a

**Sign-up bot guard**

Four cheap checks — hidden field, signed clock, one-per-address, throwaway domains — before an account is made.

- Because: signup_guard.py:124 judge() runs all four and returns a reason string that is logged and never shown; the person sees one sentence (signup_guard.py:160 REFUSAL). The clock is an itsdangerous-signed stamp so it cannot be back-dated. 14 tests in tests/test_signup_guard.py. Caveat above about the per-process rate table.
- Routes: POST /signup
- Files: signup_guard.py (6.9 KB, whole file); app.py:969-975 (_signup_open / SIGNUP_MODE); the wiring itself is in signup(), templates/signup.html:16-20 and tests/test_signup_guard_wired.py
- Note: this route was listed here before anything called the module. It became true on 2026-09-21. The fuller entry for this feature is "Sign-up bot guard" in the accounts area.
- Access: Anonymous — and the door itself is shut on a deployed service unless SIGNUP_MODE=open (app.py:969-971)

**SQLite persistence layer**

Opens a per-request sqlite3 connection against DATABASE_PATH and commits on exit.

- Because: db.py:32 get_db() connects, yields, commits; every store module imports it and the whole test suite runs against it (tests/conftest.py points DATABASE_PATH at a temp file). Probed: app boots and writes users on a throwaway DB.
- Routes: none (library)
- Files: db.py:22 db_path(), db.py:32 get_db(); 6157 lines total
- Access: n/a — server-side

**Static asset cache headers (WSGI middleware)**

Strips Vary: Cookie from /static/ responses and sets a one-year or one-day Cache-Control.

- Because: app.py:538 StaticCacheHeaders wraps app.wsgi_app last (app.py:14519). Probed: /static/css/tailwind.css → "public, max-age=86400" + "Vary: Accept-Encoding", while /robots.txt still carries "Vary: Cookie". Only 200/304 are rewritten (app.py:551-560). tests/test_static_caching.py holds it with 10 tests.
- Routes: everything under /static/
- Files: app.py:537-586 (class), app.py:14519 (wrap)
- Access: Anonymous

**Team seat gate and audit trail**

A team seat inside the artist's account is held to its rooms and its read/edit access, and every change it makes is recorded.

- Because: app.py:5110 team_seat_gate(): _TEAM_BLOCKED (app.py:5085-5090) shuts /billing, /settings, /team, /admin, /partner, /account, /backup, /signal, /operator-desk, /tours/join and eleven more by prefix; _team_blocked_inside (app.py:5096) covers the id-mid-path cases; team_areas.allows() enforces the ticked rooms; a read seat's write gets 403 JSON or a redirect. The audit row is written after the fact in an after_request (app.py:5186-5191) and only when request.url_rule is not None and the status is < 400. Backed by team_audit (db.py:982). 18 tests in tests/test_team_rooms.py, 13 in tests/test_team_access.py, 24 in tests/test_team_tour.py.
- Routes: every request while session['team_as'] is set
- Files: app.py:5084-5191; team_areas.py (whole file: LABELS, EXTRA, WHOLE_ACCOUNT, allows:150, home:172, hidden_page_keys:181); plans.py:189 TEAM_SEATS
- Access: n/a — it is the gate on seats

**Test suite**

300 pytest files holding 3,761 test functions plus 13 Node harnesses for the browser modules.

- Because: Counted by parsing every tests/test_*.py with ast: 300 files, 3,761 functions named test_*. Ran a platform subset (test_observability, test_blob_store, test_static_caching, test_offline_fallback, test_backup_objects, test_backup_access, test_backup_run_refusal, test_storage_diag): 60 passed. tests/conftest.py points DATABASE_PATH at a temp file before any app import and restores the Signal provider registry per module and per test. The largest files are test_app.py (227 tests), test_roex_release_ready.py (100), test_royalty_data.py (99), test_rack.py (63), test_audio_readiness.py (45). What it locks structurally: the design system (test_design_system 16, test_stylesheet 7), accessibility/landmarks (test_landmarks 8, test_a11y_batch 4, test_stage_a11y 8, test_centred_layout 4), the zero rule (test_zero_rule 8, test_pulse_not_measured 6, test_unmeasured_pulse_sweep 3), demo boundaries (test_demo_boundaries 7, test_demo_data_guard 6, test_demo_lock 6, test_sandbox 8), tenancy (test_tenant_isolation 3, test_shared_state 10, test_no_object_leaks 3, test_launch_leaks 6), script integrity (test_inline_scripts 6, test_rendered_scripts 2, test_template_markup 1), navigation honesty (test_navigation_honesty 10, test_nav_rail 7, test_sidebar_fold 11, test_folded_tabs_are_views 4), and seven 2026-09-20 page-walk files pinning that walk's findings.
- Routes: n/a
- Files: tests/ (300 test_*.py + conftest.py + __init__.py); tests/js/ (13 check_*.js harnesses + artist_eq_harness.js)
- Access: n/a

**Web app manifest / installable PWA**

Names the app, its icons and its standalone display for an installed home-screen copy.

- Because: static/manifest.json is a real file with two icon entries and is linked from the page head (seen in every rendered page probe: <link rel="manifest" href="/static/manifest.json">); it is also precached by the service worker. Probed: 200.
- Routes: GET /static/manifest.json
- Files: static/manifest.json; templates/base.html head
- Access: Anonymous

### Partial

**Cross-site request forgery protection**

What stops a third-party page from making a state-changing request with the user's cookie.

- Because: There is no CSRF token anywhere: grepped csrf/CSRF across all .py outside tests — one hit, and it is a header name in observability.py:87's scrub list. No flask-wtf, no Flask-SeaSurf in requirements.txt. What does exist is SESSION_COOKIE_SAMESITE="Lax" (app.py:610), which blocks cross-site POSTs in current browsers, and no form carries a token. Every webhook receiver verifies its own signature separately.
- Routes: every POST
- Files: app.py:610; requirements.txt (no CSRF package); observability.py:87
- Access: n/a

**Daily reminders run**

One POST fires the contract renewal reminders and moves the Release-Ready queue.

- Because: The work is real: contract_reminders.run(...) then release_ready.run_due(), with the result stored under reminders_last_run (and a scheduler's run also under reminders_last_scheduled_run, with when and by whom). Fixed 2026-09-23: it had answered an unsigned POST with a 302 to /login, the false green /backup/run was fixed for. It now has its own REMINDERS_CRON_TOKEN in the X-Reminders-Token header and answers 401 JSON with the reason when the token is missing or wrong, 200 JSON when it ran, and 500 JSON (recorded) when the run raised. Nothing calls it yet: the daily Render cron is an owner step.
- Routes: POST /reminders/run
- Files: app.py reminders_run, plan_gate; contract_reminders.py run/token_matches/record_run/scheduled; release_ready.py run_due; tests/test_reminders_cron.py, tests/test_contract_reminders.py
- Access: REMINDERS_CRON_TOKEN holder (X-Reminders-Token header only), or a signed-in owner (_is_owner_email). Anonymous otherwise: 401 JSON. A signed-in non-owner gets 404.

**Error reporting (Sentry)**

Starts the Sentry SDK when SENTRY_DSN is set and scrubs credentials off every event before it leaves.

- Because: observability.py:98 init(app) is called first thing in create_app (app.py:599-601). With no DSN it returns False without importing the SDK, and with no sentry-sdk installed it returns False too — so on an unconfigured checkout nothing reports. When it does run it is errors-only (traces_sample_rate 0), send_default_pii False, and before_send (observability.py:70) drops request cookies, the Authorization/Cookie/X-CSRF-Token headers and any key containing token/secret/password/api_key/apikey/dsn at any depth. A malformed DSN is caught and logged by variable NAME only. 8 tests in tests/test_observability.py, run and passing.
- Routes: none; reported as a row on /admin/readiness
- Files: observability.py (4.6 KB, whole file); app.py:598-601; requirements.txt sentry-sdk[flask]==2.69.2
- Access: n/a

**In-app 404 page**

A mistyped or stale address gets the app shell with two ways out, or a JSON body for API callers.

- Because: app.py:647-676 errorhandler(404) works for a signed-in account (probed /definitely-not-a-real-page → 404, 116 KB, renders "Page not found") and for JSON (/api/nope.json → {"ok": false, "error": "Not found"}). Anonymous visitors never see it: plan_gate (app.py:4957) redirects any unknown non-public path to /login first — probed, 302. No test references not_found.html (grepped tests/*.py for not_found / "Back to the Command Center": zero hits).
- Routes: error handler, all paths
- Files: app.py:647-676; templates/not_found.html
- Access: Signed-in accounts see the page; anonymous gets a redirect to /login

**Object storage (Cloudflare R2) adapter**

Stores uploaded bytes in an S3-compatible bucket with hand-rolled SigV4, falling back to the local disk.

- Because: The disk half is Live and persists: blob_store.py:186 save() writes through open() and returns "/uploads/<name>". The bucket half is inert on any deployment without the four R2 vars — configured() (blob_store.py:65) requires R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and sandbox.active() forces it False. Probed /storage/diag on a clean checkout: {"configured": false}. A 4xx from R2 is logged and the write still lands on disk (blob_store.py:200-222), so a misconfigured bucket never surfaces to the artist.
- Routes: none directly; consumed by every upload route (e.g. /vault/upload app.py:10454)
- Files: blob_store.py (18.4 KB): 65 configured, 136 presigned_get, 165 put, 173 delete, 186 save, 250 url_for, 372 fetch, 394 remove, 412 safe_local_path; registered as the Jinja global/filter media_url at app.py:695-696
- Access: n/a — the calling route gates

**Off-box backup push**

Takes the same snapshot and PUTs it to an S3-compatible bucket, recording the outcome including failures.

- Because: The snapshot, the recorded run (store.set_kv("backup_last_run")) and the owner alert on failure are all real code paths (app.py:13792-13815). The upload leg is inert without credentials: backup_store.configured() (backup_store.py:38) needs BACKUP_S3_ENDPOINT, BACKUP_S3_BUCKET, BACKUP_S3_KEY, BACKUP_S3_SECRET, and the route returns 503 with the variable names before calling it. Probed with no token and no config: 403 with "BACKUP_TOKEN is not configured on the server".
- Routes: POST /backup/run
- Files: app.py:13767-13815; backup_store.py:63 put(), backup_store.py:134 object_name(); app.py:4885 _valid_backup_token()
- Access: A scheduler presenting X-Backup-Token or form token matching BACKUP_TOKEN (hmac.compare_digest), or an account that passes _backup_allowed (owner). Everyone else gets 403 — deliberately not a redirect, so a cron log cannot read a 302 as success (tests/test_backup_run_refusal.py).

**Provider response cache (api_cache)**

TTL-checked JSON cache in front of the outside music APIs.

- Because: Reads and writes are real (db.py:2013 cache_get checks age against max_age_seconds, db.py:2024 cache_set upserts) and bandsintown_provider.py / music_apis.py use it — but nothing ever deletes a row: grepped "DELETE FROM api_cache" across all .py, zero hits. Expired entries are skipped on read and kept forever on disk.
- Routes: none (library)
- Files: db.py:878-882 (CREATE TABLE), db.py:2013-2031; callers in music_apis.py, bandsintown_provider.py
- Access: n/a

**Request rate limiting**

Where a flood is actually slowed down.

- Because: Two in-process throttles and nothing else. signup_guard.py:105 _rate_ok keeps a module-level dict _seen (one address per 60 s, pruned past 4096 entries), and app.py:5xxx _demo_access_seen does the same for /demo-access. Both are per-process, and the Procfile runs gunicorn --workers 2, so each worker has its own table. signup_guard is off unless RENDER is set or SIGNUP_GUARD=on (signup_guard.py:71). /login, /forgot, /webhooks/*, /uploads/ and every /api/ route have no throttle and no lockout — grepped rate_limit/ratelimit across .py: the only other hits are stage_store.py:373 (Request Mode's open-request cap), roex_client.py:434 (RoEx's own quota) and provider modules reporting a vendor's limit.
- Routes: POST /signup, POST /demo-access
- Files: signup_guard.py:62 _seen, :105 _rate_ok, :124 judge, :71 enabled; app.py (_demo_access_seen, ~line 1155); Procfile
- Access: n/a

**Resend domain status reader**

Read-only list of every domain on the Resend account with the exact DNS records each still needs.

- Because: email_provider.py:226 domain_status() makes two real GETs per domain via _api_get and returns the records; it is reachable only behind a query flag (app.py:1762, request.args.get("domains") == "1") and only when emailer.configured(). With no key it never runs and _api_get returns (None, "RESEND_API_KEY not set").
- Routes: GET /mail/diag?domains=1
- Files: email_provider.py:205-253; app.py:1761-1762
- Access: Any signed-in account

**Response security headers**

What the app puts on a response beyond content type and caching.

- Because: Only the static-cache headers exist. Grepped Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Strict-Transport-Security, Referrer-Policy and Permissions-Policy across every .py and .html in the repo: zero hits. Probed a live GET /: the response carries Content-Type, Content-Length and Vary: Cookie and nothing else. The app renders user-supplied strings into inline <script> blocks (the js_json filter, app.py:700-731, exists precisely because of that), so there is no CSP behind that escaping.
- Routes: every response
- Files: app.py:537-586 (the only header middleware); app.py:698-732 (_js_json, the escaping that stands in for a CSP)
- Access: n/a

**Session cookie configuration**

Signs sessions with SECRET_KEY, SameSite=Lax, Secure only where TLS is actually served.

- Because: app.py:604-614 sets SECRET_KEY from the environment with a hardcoded fallback "royalty-sweep-demo-session", SESSION_COOKIE_SAMESITE="Lax" and SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")). Probed on a bare checkout: SECRET_KEY is the fallback, SECURE False, HTTPONLY True (Flask's default), SAMESITE Lax. render.yaml generates a SECRET_KEY, so the fallback is a local-only risk — but a deployment on a host that does not set RENDER would serve the session cookie without Secure and nothing would say so. "remember this device" sets session.permanent at login (app.py:1121).
- Routes: every request
- Files: app.py:604-614; app.py:1119-1122; render.yaml (SECRET_KEY generateValue)
- Access: n/a

**Spotify/config presence diagnostic**

A JSON dump of which credentials the running process can see, plus the R2 round trip and Spotify probes.

- Because: app.py:1861 returns presence booleans and never values, which is what its comment promises — but the comment says "Owner-only config check" and the code gates on (user.get("plan") or "artist") != "label" (app.py:1865). That is a plan, not an identity, and /plan/switch sets a plan directly whenever Stripe is unconfigured (app.py:5316 _demo_switching) — the same shape as the leak tests/test_backup_access.py exists to stop for /backup. Probed as a plain artist: 404.
- Routes: GET /presave/diag
- Files: app.py:1861-1900
- Access: Any account on the label plan (the comment claims owner-only; the code does not)

**Statement drop-box (inbound email)**

Resend receives mail at a per-account address and the CSV attachments are parsed into statements.

- Because: app.py:1276 verifies the svix-style signature over the raw body (email_provider.py:147 verify_webhook) before anything is parsed, resolves the account from the recipient local part via ingest_tokens, downloads each CSV attachment and calls _ingest_statement(via="email"). It is 404 unless BOTH RESEND_WEBHOOK_SECRET and RESEND_INBOUND_DOMAIN are set (email_provider.py:143 inbound_configured) — probed on a clean checkout: POST /webhooks/resend → 404. Only tests/test_app.py references the route.
- Routes: POST /webhooks/resend; address minted at POST /statements/dropbox-new, tested at POST /statements/dropbox-test
- Files: app.py:1275-1320; email_provider.py:143-190; db.py:538 ingest_tokens, db.py:4482-4508
- Access: Anonymous but signature-gated (/webhooks/ is in _PUBLIC_PREFIXES, app.py:4811). The address itself is per-account and rotatable by its owner (app.py:1499-1520).

**Stripe webhook receiver**

Verifies Stripe's signature and claims fan-club, VIP, credit-pack, Release-Ready and plan checkouts.

- Because: app.py:5756 is 404 unless stripe_provider.webhook_accepts() finds a secret (probed with none: 404), then verifies the signature over the raw body before parsing. It dispatches on event type and returns 503 on transient failures so Stripe retries. Partial because the signing secret it verifies against may be a value stored in app_kv rather than the environment (stripe_provider.py:86-106), which means a rotated secret and the backup zip both carry it.
- Routes: POST /webhooks/stripe; setup at POST /billing/webhook-setup
- Files: app.py:5755-5850+; stripe_provider.py:85-120, :724-752
- Access: Anonymous but signature-gated

**Suite sign-in hand-off**

Mints a two-minute signed token so a signed-in artist reaches another Street Banker service without a second password.

- Because: sb_suite_sso.py implements issue/verify on an itsdangerous URLSafeTimedSerializer with MAX_AGE_SECONDS=120 and a per-suite key check; configured() (sb_suite_sso.py:49) requires SUITE_SSO_SECRET, and with it unset the caller falls back to a plain link. The suite addresses are hardcoded onrender.com defaults overridable by SUITE_URL_* (sb_suite_sso.py:36-42). 9 tests in tests/test_suite_sso.py.
- Routes: GET /suites/go/<key> (app.py:875)
- Files: sb_suite_sso.py (6.8 KB); app.py:875
- Access: Signed-in; the suite door itself is gated by plans.suite_open (Pro for Tour/REACH, Label-or-credits for The Room/Noise Lab/Motion). Blocked for team seats (/suites/go in _TEAM_BLOCKED).

**Transactional email (Resend)**

Sends one HTML email through api.resend.com, with the reseller's display name in front of the verified address.

- Because: The send path is complete and exercised through the _http seam (email_provider.py:76 _http, :86 send) — attachments, reply_to, cc, text, a User-Agent header added because Cloudflare 403s Python's default, and the vendor's own error kept in last_send_error(). With no RESEND_API_KEY, configured() returns False and send() returns False without pretending (email_provider.py:20-27); sandbox.active() forces the same. The known half-truth is using_shared_test_sender() (email_provider.py:196): with EMAIL_FROM unset every send "succeeds" to onboarding@resend.dev and reaches only the Resend account owner — callers in contract_reminders.py:128, press_desk.py:94 and tour_os.py:1179 check it, others do not.
- Routes: none (library); diagnostics at GET /mail/diag
- Files: email_provider.py (11.3 KB): 20 configured, 30 sender, 86 send, 140 last_send_error, 196 using_shared_test_sender, 226 domain_status; app.py:1743-1763 /mail/diag
- Access: /mail/diag: any signed-in account (no owner gate, despite reporting the mail setup)

**Untested platform surfaces**

The platform pieces with no test of their own.

- Because: Grepped tests/*.py for each. No test references templates/not_found.html or the 404 handler (grepped not_found, "Back to the Command Center": zero hits) — the 413 handler is covered by test_upload_limits.py:75,88 but the 404 page is not. No test names the absent security headers or CSRF, because there is nothing to name. email_provider.py has no dedicated file (it is monkeypatched from test_app, test_contract_reminders, test_distributor_letter, test_fans_audience, test_owner_rulings and others). /webhooks/resend is referenced only by tests/test_app.py. /mail/diag, /presave/diag and /admin/pages' interaction with team seats have no named file. db.py itself has no test_db.py — its migrations are exercised only as a side effect of every other file importing the app.
- Routes: n/a
- Files: tests/ (absence); app.py:647-676; email_provider.py; db.py
- Access: n/a

**Uploaded-file serving (/uploads)**

Serves files from the uploads directory, with an ownership check on the private kinds only.

- Because: app.py:3206 send_from_directory always answers; the gate at app.py:3216-3230 only fires for names starting doc_, for vault_ files whose row kind is master/stems and that are not shared (app.py:3233 _vault_file_private), and for lockbox uploads. Everything else under /uploads — press photos, cover art, link images, sync audio, tour files — is served to anyone with the address, by design, and /uploads/ is in _PUBLIC_PREFIXES (app.py:4811) so plan_gate never sees it. Probed: /uploads/nope.txt returns 404 anonymously.
- Routes: GET /uploads/<path:filename>
- Files: app.py:3205-3230 (handler), app.py:3194-3203 (UPLOADS_DIR), blob_store.py:412 safe_local_path; store helpers db.document_path_owned / vault_path_owned / lockbox_path_owned
- Access: Anonymous for public kinds; signed-in owner only for doc_*, private vault_*, lockbox files (404 to anyone else)

### Stubbed

**Audio Intelligence webhook receiver**

Takes a vendor's job-finished callback, verifies it, dedupes it and advances the job it names.

- Because: audio_webhooks.py:58 answers 404 unless AUDIO_INTELLIGENCE_ENABLED is on AND the provider is a registered adapter AND a <PROVIDER>_WEBHOOK_SECRET exists — probed POST /webhooks/audio/mock on a clean checkout: 404. The logic underneath is complete and correct (signature over the raw body first, dedupe on (provider, external_event_id), tenant taken from our own audio_jobs row and never from the payload, always 200 after a good signature), and 12 tests in tests/test_audio_webhooks.py exercise it — but on an unconfigured deployment it accepts nothing.
- Routes: POST /webhooks/audio/<provider>
- Files: audio_webhooks.py:58-110 (route), :112 _signing_adapter, :140 _apply, :160 init; registered at app.py:14474
- Access: Anonymous, but shut unless the flag and a per-provider secret are both set

### Dead code

**Checked-in homepage backups**

122 files under backups/ holding six earlier homepage versions with their configs, templates, images and RESTORE notes.

- Because: Nothing imports or renders them: grepped "from backups"/"import backups" across .py and .html — zero hits; the only occurrences of the word in app.py are prose in a comment. They ship in the repo and in every source checkout, and backups/homepage-2026-08-05/config/rollout_config.py is a stale copy of a live module.
- Routes: none
- Files: backups/homepage-2026-07-26, -07-29, -08-05, -08-14, backups/homepage-editorial-2026-07-26, backups/section07-2026-08-14 (122 files)
- Access: n/a

**tools/ maintenance and build scripts**

Nineteen hand-run Python scripts for the design-system sweeps, homepage photo derivatives, local preview servers and the X32 bench.

- Because: Nothing in the running app reaches them: grepped "import tools", "from tools" and "tools." across every .py and .html outside tools/ itself — zero hits, and tools/ has no __init__.py. They are invoked by hand (each docstring gives the command line). Three are consumed indirectly: tools/tailwind.config.js and tools/tailwind-input.css are the stylesheet build inputs that tests/test_stylesheet.py and tests/test_design_system.py check the output of, and tools/stage_bridge_daemon.py is exercised end-to-end by tests/test_stage_bridge_daemon.py (14 tests).
- Routes: none
- Files: tools/: adopt_components.py, adopt_controls.py, adopt_module_headings.py, build_departments_image.py, build_photo.py, clean_distribution_photo.py, clean_rollout_photo.py, clean_sweep_photo.py, clean_twin_photo.py, dev_preview.py, dev_preview_studio.py, gold_discipline.py, normalise_type.py, repair_board_encoding.py, restore_hook_classes.py, stage_bridge_daemon.py, sweep_colours.py, v1_preview_signed.py, visible_words.py, x32_bench.py + tailwind-input.css, tailwind.config.js
- Access: Developer machine only
## Integrations

Every external service the code calls, gathered from the ten area
inspections. A service whose key is unset refuses in its own words; none
of them invents a figure to fill the gap.

- ACRCloud (acr_provider.py, called from app.py:8924 /beats/<id>/identify) — audio fingerprint identification for a producer's beat or a found clip. KEY REQUIRED: ACRCLOUD_HOST, ACRCLOUD_ACCESS_KEY, ACRCLOUD_ACCESS_SECRET; without them the route redirects back without calling and the provider raises "keys are not set".
- ACRCloud Console API — acr_console.py (buckets, upload_audio, containers, scan_file, scan_results), called from acr_desk.py. KEY REQUIRED: ACRCLOUD_CONSOLE_TOKEN; refuses while sandbox.active().
- ACRCloud Identify API — acr_provider.py (identify, status). KEY REQUIRED: ACRCLOUD_HOST + ACRCLOUD_ACCESS_KEY + ACRCLOUD_ACCESS_SECRET. Used by the producers/beats desk; acr_console.default_region() reads ACRCLOUD_HOST to pick the console region.
- Apple Music / iTunes Search — music_apis.apple_has_isrc, called by coverage_check.availability. NO KEY.
- Art-Net (UDP 6454) and sACN / E1.31 (UDP 5568) — DMX output from Light Studio, framed in static/js/lights-engine.js:315/:338 and forwarded by a locally-run helper the page offers for download, static/tools/lx-bridge.py on 127.0.0.1:7070. No key.
- Audio Intelligence vendors (inbound webhook receiver) — audio_webhooks.py /webhooks/audio/<provider>; requires AUDIO_INTELLIGENCE_ENABLED plus a per-provider <PROVIDER>_WEBHOOK_SECRET, otherwise 404.
- Bandsintown Events API — bandsintown_provider.py, keyed on BANDSINTOWN_APP_ID. Reached only from the EPK path (app.py:3281), not from tour_os; tour_dates.py:1 records that the platform was declined an app_id and that TOUR's own dates feed the kit instead.
- Bandsintown — bandsintown_provider.py upcoming_events/artist_info, called by app.py _epk_tour_dates as the fallback when TOUR has no upcoming dates. Key REQUIRED: BANDSINTOWN_APP_ID; unset here, so configured() is false and the fallback returns nothing.
- Bandsintown — signal_providers.py:2736 BandsintownAdapter, delegating to bandsintown_provider.py, for the Signal artist Events tab. KEY REQUIRED: BANDSINTOWN_APP_ID (named in the adapter's health_check message).
- Behringer/Midas X32 over OSC UDP 10023 — stage_x32.py. BENCH ONLY: reachable only with STAGE_BENCH_ADAPTERS=1, spec tested_model is "UNTESTED" and verified is False (stage_x32.py:184); stage_adapters.ADAPTERS ships the simulator alone.
- Chartmetric — signal_providers.py:1592 ChartmetricAdapter. KEY REQUIRED: CHARTMETRIC_ENABLED + CHARTMETRIC_REFRESH_TOKEN. Declaration only, no methods implemented.
- Cloudflare R2 (object storage) - blob_store.py, called from app.py:7371 (lockbox file delete) and app.py:4113 (artwork delete) to remove stored objects. Keys REQUIRED (R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY); unconfigured it falls back to local /uploads paths.
- Cloudflare R2 (S3-compatible object storage) — blob_store.py, hand-rolled SigV4; key required (R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY). Unconfigured it silently uses the local disk. Optional public CDN base via R2_PUBLIC_BASE_URL.
- Cloudflare R2 (S3-compatible) — blob_store.py, used for vault uploads, filed contracts and generated split agreements. KEYS REQUIRED: R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY (+ optional R2_PUBLIC_BASE_URL); unconfigured, blob_store.save falls back to the local uploads directory and the same code path works.
- Cloudflare R2 / blob storage — blob_store.py, called from this area only to delete objects after an account reset (app.py:13381) or delete (app.py:13653); keys required (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET), and a failure there is swallowed so it cannot resurrect the account.
- Cloudflare R2 / blob storage — blob_store.py, used by operator_desk.py:168 _save_desk_file (desk/ prefix) and audio_signal.py (briefs/ prefix), with a local directory fallback. KEY REQUIRED for the bucket path (blob_store's own env, outside this area).
- Cloudflare R2 object storage (blob_store.py) — private storage for Studio sources and masters, Audio Studio sources and outputs, beat audio and Release-Ready masters, served by short-lived signed URLs. KEYS REQUIRED: R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY. Without them the Studio refuses uploads over 25 MB and Release-Ready refuses to store a master at all (release_ready.py:707 never falls back to disk).
- Cloudflare R2 object store — blob_store.py save/fetch/url_for/remove, used to store the saved press kit written by /epk/vault-save and EPK assets. Keys REQUIRED for remote storage: R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY; without them it falls back to the local uploads directory.
- Deezer API — music_apis.deezer_artist_fans / deezer_has_isrc, called by coverage_check.availability. NO KEY.
- Deezer public API - music_apis.py:182 deezer_track_metadata(), called from app.py:2927 /catalog/add for ISRC/UPC/label/release date. NO key required; responses cached in the api_cache table (DEEZER_TTL).
- Deezer public API — music_apis.py:225 deezer_artist_fans, called from app.py:9707 pulse_page. NO KEY.
- Discogs - signal_providers.py:1773 DiscogsAdapter, called from app.py _discogs_state() (catalog page) and app.py:2858 /tracks/<id>/discogs. Key REQUIRED (DISCOGS_ENABLED + DISCOGS_TOKEN); unconfigured, no lookup runs at all.
- Discogs — signal_providers.py:1773 DiscogsAdapter. KEY REQUIRED: DISCOGS_ENABLED + DISCOGS_TOKEN.
- ElevenLabs (audio_elevenlabs.py, via the elevenlabs SDK) — transcription, speech, sound effects, voice isolation, music/composition plan, stem separation, dubbing, conversational agent, voice identity. KEY REQUIRED: ELEVENLABS_ENABLED plus ELEVENLABS_API_KEY; without both, health() reports "unconfigured", register_all() does not make it the default, and the offline mock adapter answers every capability instead (verified by probe).
- ENTTEC USB DMX over Web Serial — direct output from the browser; static/js/lights-engine.js OUTPUTS at :390. No key; Chromium desktop only.
- Eventbrite Events API — the only source of a measured sold count and capacity; eventbrite_provider.py via tour_tickets.py:211 sync(). KEY REQUIRED (EVENTBRITE_TOKEN).
- ffmpeg (local binary, convert_engine.py and audio_probe.py) — server-side MP3/FLAC/AAC/ALAC/Opus/Vorbis encoding for the Rack, and MP3 duration when there is no Xing header. NO KEY; convert_engine.available() checks shutil.which and POST /rack/convert answers 503 when it is missing.
- Google Geocoding API — venue coordinates; venue_geo.py. KEY REQUIRED (GOOGLE_MAPS_API_KEY, same key).
- Google Maps directions deep links — tour_os.py:4278 builds https://www.google.com/maps/dir/?api=1 URLs for each leg. No key; a link, not an API call.
- Google News RSS (press mentions) — music_apis.py:252 press_mentions, called by app.py /epk/press/search for the EPK's press-quote finder. NO key required; results cached 24h in api_cache. Verified reachable as a route; the outbound fetch itself was not exercised.
- Google Places API (New) — venue photos; venue_photos.py:27 searchText + media. KEY REQUIRED (GOOGLE_MAPS_API_KEY). configured() is false under sandbox even with a key; the photo credit is printed because Google's terms require it.
- Google Routes API v2 — measured drive distance and duration between dates; venue_geo.drive(), cached by tour_os.measure_leg (tour_os.py:804) into app_kv. KEY REQUIRED (GOOGLE_MAPS_API_KEY). venue_geo.py:1 records that Routes is NOT enabled on the owner's key; routes_available() latches off after the first refusal and the map falls back to a labelled straight line.
- Google Time Zone API — a date's time zone from its room; venue_geo.py, called from tour_os.fill_show_tz (tour_os.py:764). KEY REQUIRED (GOOGLE_MAPS_API_KEY).
- Hypeddit (inbound automation webhook) — app.py /webhooks/hypeddit/<token> → hypeddit_ingest.receive; no vendor key, the per-account token in the URL is the authorisation.
- Hypeddit (inbound only, relayed through a Make/Zapier scenario) — receiver app.py:1324 hypeddit_webhook + hypeddit_ingest.py; NO KEY: the per-account token in the URL is the authorisation. Hypeddit's own Automation field only accepts Zapier/IFTTT/Make addresses, so the documented setup is a Make relay (templates/partials/hypeddit_connect.html).
- Metrics provider through the Signal registry (Soundcharts today) — signal_providers CAP_METRICS, read by app.py _epk_real_stats via _provider_metrics(..., fetch=False) so a stranger opening a pitch link never spends the artist's quota; the mock is explicitly rejected (app.py _metrics_provider), so with no real provider the kit says "Not measured". Key REQUIRED for the provider.
- MusicBrainz — signal_providers.py:1601 MusicBrainzAdapter (artist, releases, label only; measures nothing). NO ACCOUNT, but MUSICBRAINZ_ENABLED + MUSICBRAINZ_CONTACT are required for the User-Agent their policy demands.
- No other external service is called from this area. trust_score.py (used by /marketplace and /marketplace/people/<id>) reads only local tables - catalog, deals, statements, fans, campaigns, sync packs, EPK and stored Spotify pulse snapshots - and makes no network call of its own.
- Object storage (R2/S3-compatible) via blob_store.py — tour file uploads (tour_os.py:4005), venue photos (tour_os.py:545), the stage-plot PNG (plot_images.py) and Live stems (live.py:270). Falls back to a private directory beside the database when not configured.
- Odesli / song.link (platform link resolution for the smart-link builder) — music_apis.py:72 odesli_lookup, called from app.py:4232 ml_autofill and app.py:11320 links_create; NO KEY; responses cached in the api_cache table.
- Odesli / song.link — music_apis.odesli_lookup (music_apis.py:72). NO KEY. Named in coverage_check's docstring as the route; the live availability() path uses Songstats + Apple + Deezer, so the docstring and the code disagree.
- Off-box backup target — backup_store.py, reached from the Settings backup panel and POST /backup/run; credentials required, and the run refuses honestly with the missing variable names when unconfigured.
- Pollinations.ai image model - app.py:4050 /artwork/generate builds the image URL, app.py:4090 /artwork/save downloads it via music_apis.fetch_image_bytes(). NO key required; the browser loads the generation URL directly.
- Render (hosting) — render.yaml defines one web service (starter plan, gunicorn, 2 workers / 4 threads / 180 s timeout) with a 1 GB disk at /var/data; RENDER, RENDER_SERVICE_NAME and RENDER_GIT_COMMIT are read as signals (cookie Secure, Sentry environment/release, suite-gate and signup-guard defaults). No cron or worker service is defined in the repo.
- Resend (domain/DNS status, read-only) — email_provider.py domain_status() → GET /domains and /domains/<id>; key required (RESEND_API_KEY).
- Resend (email) - email_provider.py, called from app.py:7323 os_lockbox_update() to send a lockbox signature request. Key REQUIRED (RESEND_API_KEY); unconfigured, the token is still minted and the sign link stays on the page but no mail goes out.
- Resend (email) — email_provider.py; used by tour_os._deliver_advance (tour_os.py:2616), VIP confirmation and day-of mail (tour_os.py:3402/3408), crew invitations (tour_os.py:4884), Team-Up Board reply/watch/renew mail (board.py:150/:236/:76). KEY REQUIRED (RESEND_API_KEY, EMAIL_FROM). tour_os refuses to report an advance as sent when configured() is false or using_shared_test_sender() is true.
- Resend (inbound email receiving) — email_provider.py verify_webhook/list_received_attachments/download_attachment → https://api.resend.com/emails/receiving/<id>/attachments; requires RESEND_WEBHOOK_SECRET and RESEND_INBOUND_DOMAIN (plus RESEND_API_KEY to fetch the attachment) or POST /webhooks/resend is 404.
- Resend (outbound transactional email) — email_provider.py send() → POST https://api.resend.com/emails; key required (RESEND_API_KEY). Without EMAIL_FROM it sends as onboarding@resend.dev, which only reaches the Resend account owner.
- Resend (transactional email) via email_provider.py - emailer.configured() is bool(RESEND_API_KEY), so with no key every call site silently skips the send and the in-app notification is the fallback. Key REQUIRED. Called from: app.py:11695 marketplace_apply (application email to the brief's poster, reply_to = the applicant's contact); board.py:143 _alert_watchers (saved-search alert); board.py:222 reply (new-reply email to the listing's owner); board.py:68 _sweep_renewals (one renewal email with the one-click /board-renew link).
- Resend (transactional email) — email_provider.py send/configured/using_shared_test_sender; called by press_desk.pitch_send for press pitches and by app.py roster_invite for roster invitations. Key REQUIRED: press sending needs RESEND_API_KEY *and* EMAIL_FROM (press_desk.send_state refuses with 409 while EMAIL_FROM is unset, because the shared onboarding sender delivers only to the account owner's inbox); roster invites only need RESEND_API_KEY and are best-effort. Neither is set in this environment, so no real delivery was exercised.
- Resend email — email_provider.py (as emailer); used by this area for the password-reset link (app.py:1381), team invites (app.py:12862), roster invites (app.py:6736), the plan-grant email (app.py:13590) and the demo password (app.py:1185). Key required: RESEND_API_KEY; EMAIL_FROM decides whether it is the shared test sender (email_provider.py:196).
- Resend email — email_provider.py:28 configured / send, used for release-day emails (app.py:1679), fan club drop notifications (app.py:6536) and fan club magic links (app.py:6512); KEY REQUIRED: RESEND_API_KEY (EMAIL_FROM optional).
- Resend — email_provider.py. Inbound: the statement drop-box webhook receiver (POST /webhooks/resend) plus list_received_attachments/download_attachment. Outbound: lockbox signature requests and contract renewal reminders. KEYS REQUIRED: RESEND_API_KEY for sending; RESEND_WEBHOOK_SECRET + RESEND_INBOUND_DOMAIN for the drop-box (inbound_configured()).
- RoEx (per-job callback receiver) — release_ready.py /webhooks/roex/<jid>/<token>; no vendor signature (deliveries are unsigned), authorised by a per-job token whose sha256 we store. Requires PUBLIC_BASE_URL on https for the address to be minted at all.
- RoEx (via Release-Ready) - not called from this area, but release_ready_store.masters_by_track() is READ on app.py:6346 /metadata-passport and app.py:6970 /tracks/<id> to mark tracks with a stored master. The provider call and its webhook (/webhooks/roex/<jid>/<token>) belong to the Creative Studio area.
- RoEx Tonn (roex_client.py, https://tonn.roexaudio.com) — mix analysis, mastering previews, vocal+beat recombine, final master. KEY REQUIRED: ROEX_API_KEY, sent as X-API-Key only, never as ?key=. Without it configured() is False and Release-Ready reports "not connected" and refuses every write.
- S3-compatible backup bucket (R2 / B2 / Wasabi / S3) — backup_store.py, hand-rolled SigV4 PUT; key required (BACKUP_S3_ENDPOINT, BACKUP_S3_BUCKET, BACKUP_S3_KEY, BACKUP_S3_SECRET, optional BACKUP_S3_REGION). Returns (False, "not configured") without them and the route 503s first.
- segno (QR code generation) — tour share-link QR codes (tour_os.py:4692) and the Light Studio remote QR (app.py:7686). A library, not a service.
- Sentry (error reporting) — observability.py via sentry-sdk[flask]==2.69.2; key required (SENTRY_DSN). Optional at runtime: with the DSN unset the SDK is never imported.
- Shopify Admin GraphQL API (customers) — shopify_customers.py:281 fetch_customers / :86 granted_token; KEY REQUIRED: SHOPIFY_DOMAIN plus either SHOPIFY_ADMIN_TOKEN or SHOPIFY_CLIENT_ID+SHOPIFY_CLIENT_SECRET (client-credentials grant, 24h token cached in app_kv). Not configured in this checkout, so the panel reports 'Shopify is not connected' and the import route redirects ?imp=off.
- Shopify Buy Button — shopify_buy.py context(), called by app.py _epk_store for the Merch block, and only for the owner's own kit and the demo showcase. Keys REQUIRED: SHOPIFY_DOMAIN, SHOPIFY_STOREFRONT_TOKEN, SHOPIFY_COLLECTION_ID.
- Social publishing platforms (Meta, TikTok, YouTube, X, Threads, LinkedIn, Snapchat) - social_providers.py, read only by app.py:10939 /rollout-studio/<cid>/socials. NOTHING publishes: every provider row has publishes=False and there is no upload code behind any of them; present credentials report 'not connected'.
- Songstats - signal_providers.py:1235 SongstatsAdapter, reached only from app.py:9225 /isrc/diag. Key REQUIRED (SONGSTATS_API_KEY).
- Songstats API — coverage_check._songstats_links (coverage_check.py:145) and signal_providers.SongstatsAdapter. KEY REQUIRED: SONGSTATS_API_KEY.
- Songstats — signal_providers.py:1217 SongstatsAdapter. KEY REQUIRED: SONGSTATS_ENABLED + SONGSTATS_API_KEY.
- Soundcharts — signal_providers.py:289 SoundchartsAdapter (artist, metrics, releases, cities, playlists, social). KEY REQUIRED: SOUNDCHARTS_ENABLED plus a ready-made SOUNDCHARTS_ACCESS_TOKEN or the legacy SOUNDCHARTS_APP_ID/SOUNDCHARTS_API_KEY pair. Spend is counted and capped by soundcharts_budget.py.
- SoundExchange — signal_providers.py:3107 SoundExchangeAdapter. KEY REQUIRED: SOUNDEXCHANGE_ENABLED + SOUNDEXCHANGE_API_KEY. Declaration only, no methods implemented.
- Spotify metadata (as a Signal provider) — signal_providers.py:3115 SpotifyMetadataAdapter. KEY REQUIRED: SPOTIFY_METADATA_ENABLED + SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET. Declaration only, no methods implemented.
- Spotify Web API (Artist Pulse) — spotify_provider.py:133 pulse_configured / artist_pulse, called from app.py:9707 pulse_page. KEY REQUIRED: SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET (the OAuth flow additionally needs SPOTIFY_REDIRECT_URI).
- Spotify Web API (catalogue search by ISRC) — spotify_provider.py via coverage_check._spotify_url_for_isrc, used by the gap store check. KEY REQUIRED: SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET; without them the store is reported as "unchecked" with a reason, never "absent".
- Spotify Web API (OAuth + library save for pre-saves) — spotify_provider.py, used by app.py:1980 presave_start, :1989 presave_callback and :1705 _process_due_presaves; KEY REQUIRED: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI.
- Spotify Web API - coverage_check.py:78 via spotify provider, reached only from app.py:9225 /isrc/diag. Key REQUIRED (SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET).
- Stage Bridge daemon — tools/stage_bridge_daemon.py, an out-of-process client on the venue network that calls /bridge/heartbeat|pull|ack|reconcile with a device token and HMAC-SHA256 signature verification. No third-party service.
- StemSplit.io (stemsplit_provider.py, called from app.py:8221/8265/8277) — studio-quality stem separation for the Rack's Stem Deck. KEY REQUIRED: STEMSPLIT_API_KEY; without it configured() is False, the tier is hidden on /rack and the three endpoints answer 503. The flow lends StemSplit a public /stem-src/<token> URL to fetch the source from.
- Street Banker's own TOUR, as a Signal events provider — signal_providers.py:2790 TourDatesAdapter reading tour_dates.py. NO KEY; "configured" only for a signed-in owner holding a confirmed upcoming date.
- Stripe (subscriptions, checkout, customer portal, balance credits, coupons, webhook endpoint creation) — stripe_provider.py, imported into app.py as stripe_billing; key required: STRIPE_SECRET_KEY, plus a webhook signing secret from STRIPE_WEBHOOK_SECRET or the app_kv key stripe_<mode>_webhook_secret. configured() also returns False whenever sandbox.active(), so a SANDBOX deployment never charges.
- Stripe (webhook receiver only, from this area's point of view) — app.py:5755 /webhooks/stripe, verified by stripe_provider.verify_webhook; signing secret required, read from STRIPE_WEBHOOK_SECRET or from the app_kv row stripe_webhook_secret.
- Stripe Checkout (fan club subscriptions) — stripe_provider.py:552 create_club_checkout, :678 get_checkout_session, called from app.py:6455; KEY REQUIRED: STRIPE_SECRET_KEY. Also gated by the owner's sales_switch (app_kv 'online_sales', default off).
- Stripe Checkout (stripe_provider.py, used by release_ready.py:2049 buy / :2104 claim_session) — one-time payment per master. KEY REQUIRED: STRIPE_SECRET_KEY (and STRIPE_WEBHOOK_SECRET for the webhook); without it buy() returns 409 "no payments".
- Stripe Checkout — online VIP package sales; stripe_provider.py:579 create_vip_checkout() posts to /v1/checkout/sessions and get_checkout_session() reads a session back; the webhook branch is app.py:5781 -> tour_os.claim_vip_session (tour_os.py:3443). KEY REQUIRED (STRIPE_SECRET_KEY; STRIPE_WEBHOOK_SECRET for the receiver). Also gated by an owner switch in app_kv (sales_switch.py, default off).
- Stripe price table — stripe_provider.PRICES, read by partner_billing.seat_price_cents/statement for the reseller's monthly figure. NO API call is made; this is the local price constant only. Nothing in Partner OS charges anybody.
- Stripe webhooks (fan club member add / cancel) — app.py:5755 stripe_webhook, branches at :5766 and :5859; KEY REQUIRED: STRIPE_WEBHOOK_SECRET (or a secret stored in app_kv); the receiver 404s without one.
- Suite services (SSO hand-off) — sb_suite_sso.py issues a 120-second signed token to street-banker-v2-workflows.onrender.com, street-banker-tour-open-preview-3.onrender.com and masterclip.onrender.com (overridable by SUITE_URL_*); shared secret required (SUITE_SSO_SECRET).
- Suite services — The Room, REACH, Noise Lab (street-banker-v2-workflows.onrender.com), Tour (street-banker-tour-open-preview-3.onrender.com) and Motion (masterclip.onrender.com) — sb_suite_sso.py. Shared secret SUITE_SSO_SECRET required for the signed hand-off; without it app.py:917 falls back to a plain unauthenticated link. The same secret, under a separate salt, authenticates the suites' inbound credit calls to /api/suites/credits.
- Symphonic Distribution via SummitArts - named on /distribution as the delivery partner. NO code integration exists: distro_config.INTEGRATIONS lists every store row as 'Delivered through partner' and direct platform connections as 'Coming soon'.
- The built-in mock universe — signal_providers.py:3180 MockMusicIntelligenceAdapter. NO KEY; it is always configured() and answers only while no real adapter is.
- The MLC - signal_providers.py:2884 MLCAdapter, called from app.py:7035 /tracks/<id>/mlc and from app.py _mlc_credits() on /catalog/add. Key REQUIRED (MLC_ENABLED + MLC_USERNAME + MLC_PASSWORD); unconfigured it refuses honestly and writes nothing.
- The MLC Public Search API — signal_providers.MLCAdapter (signal_providers.py:2884), called by recovery_mlc.sweep from POST /recovery/mlc. KEY REQUIRED: env_keys MLC_USERNAME + MLC_PASSWORD, env_flag MLC_ENABLED; unconfigured it refuses and the route redirects to /recovery?mlc=off (verified on this checkout).
- The MLC Public Search API — signal_providers.py:2884 MLCAdapter (rights evidence; OAuth token exchange). KEY REQUIRED: MLC_ENABLED + MLC_USERNAME + MLC_PASSWORD.
- Ticketmaster Discovery API — listing link and on-sale word only, no counts; ticketmaster_provider.py via tour_tickets.py. KEY REQUIRED (TICKETMASTER_API_KEY) AND the switch: enabled() is false on every deployed service unless TICKETMASTER_ENABLED=on (ticketmaster_provider.py:83).
- YouTube Data API — signal_providers.py:2246 YouTubeAdapter, reached from app.py:3545 _youtube_adapter for the Pulse YouTube panel. KEY REQUIRED: YOUTUBE_ENABLED + YOUTUBE_API_KEY.

## Database tables

230 tables, extracted from every CREATE TABLE statement in the
repository. This list is mechanical, so it is complete.

`acr_registrations`, `acr_scan_hits`, `acr_scans`, `agent_profiles`
`agent_sessions`, `api_cache`, `app_kv`, `artist_signal_profiles`
`audio_assets`, `audio_consent`, `audio_jobs`, `audio_policies`
`audio_transcript_segments`, `audio_transcript_speakers`, `audio_transcripts`, `audio_usage`
`audio_webhook_events`, `audio_works`, `beat_audio`, `beat_clearances`
`beat_fingerprint_checks`, `beat_fingerprint_matches`, `beat_licences`, `beat_shares`
`beat_uses`, `beats`, `board_events`, `board_messages`
`board_threads`, `board_watches`, `catalog_tracks`, `club_drops`
`club_members`, `collab_profiles`, `collab_ratings`, `collab_replies`
`collab_requests`, `collab_saves`, `collab_seen`, `credit_ledger`
`deals`, `desk_activity`, `desk_deals`, `desk_events`
`desk_files`, `desk_leads`, `desk_meeting_candidates`, `desk_meetings`
`desk_notes`, `desk_tasks`, `desk_users`, `discogs_links`
`disputes`, `document_readings`, `document_reminders`, `document_terms`
`documents`, `does`, `epk_assets`, `epk_profiles`
`epk_share_events`, `epk_shares`, `fan_clubs`, `fan_import_drafts`
`fan_imports`, `gap_checks`, `hours_blocks`, `hours_bookings`
`hours_entries`, `hours_invoices`, `hours_rates`, `hours_submissions`
`inbox`, `ingest_tokens`, `is`, `light_comments`
`light_remote_cmds`, `light_remotes`, `light_rigs`, `light_setlist_items`
`light_setlists`, `light_shares`, `light_show_library`, `light_show_versions`
`light_shows`, `link_clicks`, `live_midi_maps`, `live_scenes`
`live_sets`, `live_stems`, `ml_campaigns`, `ml_consents`
`ml_destinations`, `ml_events`, `ml_fans`, `ml_variants`
`notification_mutes`, `notifications`, `on`, `onesheet_shares`
`onesheet_views`, `os_tracks`, `outreach_items`, `partner_audit`
`partner_members`, `partners`, `passport_contacts`, `passport_cues`
`passport_documents`, `passport_equipment`, `passport_inputs`, `passport_outputs`
`passport_personnel`, `passport_playback`, `passport_versions`, `passports`
`press_contacts`, `press_coverage`, `press_pitches`, `press_recipients`
`press_releases`, `pulse_peer_snapshots`, `pulse_peers`, `pulse_profiles`
`pulse_snapshots`, `rack_library`, `rack_presets`, `recovery_cases`
`recovery_mlc_sweeps`, `release_ready_consents`, `release_ready_jobs`, `release_ready_payments`
`release_ready_sources`, `revenue_expenses`, `ro_assets`, `ro_campaigns`
`ro_posts`, `roex_rate`, `roster_members`, `royalty_goals`
`score_history`, `show_conflicts`, `show_passports`, `show_questions`
`sign_tokens`, `signal_alert_rules`, `signal_alerts`, `signal_artist_ids`
`signal_artists`, `signal_briefs`, `signal_city_metrics`, `signal_desk_links`
`signal_evidence`, `signal_mandates`, `signal_members`, `signal_metrics`
`signal_orgs`, `signal_provider_runs`, `signal_releases`, `signal_scores`
`signal_watch_items`, `signal_watchlists`, `signup_invites`, `smart_links`
`spotify_presaves`, `stage_commands`, `stage_devices`, `stage_events`
`stage_locks`, `stage_plot_images`, `stage_plots`, `stage_policies`
`stage_presence`, `stage_requests`, `statement_rows`, `statements`
`street_actions`, `studio_analysis`, `studio_approvals`, `studio_comments`
`studio_deliveries`, `studio_findings`, `studio_members`, `studio_projects`
`studio_provenance`, `studio_versions`, `sync_packs`, `team_audit`
`team_members`, `tour_acks`, `tour_advance`, `tour_advance_sends`
`tour_board`, `tour_board_replies`, `tour_changes`, `tour_content`
`tour_days`, `tour_expenses`, `tour_fan_captures`, `tour_files`
`tour_guests`, `tour_imports`, `tour_lineup`, `tour_lodging`
`tour_members`, `tour_merch_counts`, `tour_merch_products`, `tour_people`
`tour_rooms`, `tour_schedule`, `tour_setlist_items`, `tour_setlists`
`tour_share_links`, `tour_show_calls`, `tour_show_ext`, `tour_shows`
`tour_travel`, `tour_venues`, `tour_vip`, `tour_vip_links`
`tour_vip_offers`, `tour_vip_sales`, `tours`, `track_analysis`
`track_mlc_checks`, `twin_generations`, `twin_settings`, `users`
`vault_files`, `will`

## Environment variables

96 names, extracted mechanically. **Names only. No values appear in this
file and none should ever be added to it.** A value belongs in the
service's own environment settings and nowhere else.

`ACRCLOUD_ACCESS_KEY`, `ACRCLOUD_ACCESS_SECRET`, `ACRCLOUD_CONSOLE_TOKEN`
`ACRCLOUD_HOST`, `AUDIO_INTELLIGENCE_ENABLED`, `AUDIO_OPERATOR_ENABLED`
`BACKUP_S3_BUCKET`, `BACKUP_S3_ENDPOINT`, `BACKUP_S3_KEY`
`BACKUP_S3_REGION`, `BACKUP_S3_SECRET`, `BACKUP_TOKEN`
`BANDSINTOWN_APP_ID`, `CHARTMETRIC_RIGHTS_CONFIRMED`, `CHARTMETRIC_TOKEN`
`CORE_BUILDER_URL`, `DATABASE_PATH`, `DEMO_PASSWORD`
`DISCOGS_CACHE_S`, `DISCOGS_TOKEN`, `ELEVENLABS_API_KEY`
`ELEVENLABS_DEFAULT_VOICE_ID`, `ELEVENLABS_OUTPUT_FORMAT`, `ELEVENLABS_STT_MODEL`
`ELEVENLABS_TTS_MODEL`, `EMAIL_FROM`, `EVENTBRITE_TOKEN`
`GOOGLE_MAPS_API_KEY`, `LIVE_LAB_ENABLED`, `MEETING_INTELLIGENCE_ENABLED`
`MLC_PASSWORD`, `MLC_USERNAME`, `MOCK_UP_TOUR`
`MUSICBRAINZ_CONTACT`, `NAV_ROOMS`, `OWNER_EMAIL`
`OWNER_EMAILS`, `PARTNER_PLATFORM_FEE_CENTS`, `PARTNER_ROOT_DOMAIN`
`PATH_INFO`, `PORT`, `PUBLIC_BASE_URL`
`QUERY_STRING`, `R2_ACCESS_KEY_ID`, `R2_ACCOUNT_ID`
`R2_BUCKET`, `R2_PUBLIC_BASE_URL`, `R2_SECRET_ACCESS_KEY`
`REMINDERS_CRON_TOKEN`, `REMIX_LAB_AUDIO_ENGINE_ENABLED`, `RENDER`, `RENDER_GIT_COMMIT`
`RESEND_API_KEY`, `RESEND_INBOUND_DOMAIN`, `RESEND_WEBHOOK_SECRET`
`ROEX_API_KEY`, `SANDBOX`, `SANDBOX_NAME`
`SB_NODE_BIN`, `SB_REQUIRE_JS_TESTS`, `SECRET_KEY`
`SHOPIFY_ADMIN_TOKEN`, `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`
`SHOPIFY_COLLECTION_ID`, `SHOPIFY_DOMAIN`, `SHOPIFY_STOREFRONT_TOKEN`
`SIGNAL_AUDIO_BRIEFS_ENABLED`, `SIGNUP_BLOCKED_DOMAINS`, `SIGNUP_GUARD`
`SIGNUP_MODE`, `SONGSTATS_API_KEY`, `SOUNDCHARTS_CACHE_S`
`SOUNDCHARTS_SANDBOX_LIVE`, `SPLIT_HOME`, `SPOTIFY_CLIENT_ID`
`SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`, `STAGE_BENCH_ADAPTERS`
`STEMSPLIT_API_KEY`, `STEMSPLIT_JOBS_PATH`, `STRIPE_SECRET_KEY`
`STRIPE_WEBHOOK_SECRET`, `STUDIO_DEFAULT_RETENTION_DAYS`, `STUDIO_MAX_UPLOAD_BYTES`
`STUDIO_PROCESSING_PROVIDER`, `STUDIO_PROVIDER_API_KEY`, `STUDIO_PROVIDER_BASE_URL`
`STUDIO_V1_ENABLED`, `SUITE_GATES`, `SUITE_SSO_SECRET`
`TICKETMASTER_API_KEY`, `TICKETMASTER_ENABLED`, `VIP_PLATFORM_FEE_PCT`
`YOUTUBE_API_KEY`, `YOUTUBE_CACHE_S`

## Background jobs and webhooks

### Webhook receivers

Six addresses the outside world posts to. Each authenticates its caller
in its own way, listed in its feature entry above.

- `/webhooks/resend` (POST) app.py:1212
- `/webhooks/hypeddit/<token>` (GET/POST) app.py:1260
- `/billing/webhook-setup` (POST) app.py:5396
- `/webhooks/stripe` (POST) app.py:5516
- `/webhooks/audio/<provider>` (POST) audio_webhooks.py:58
- `/webhooks/roex/<jid>/<token>` (POST) release_ready.py:2191

### Jobs and schedulers

- _alert_watchers() - board.py:143, runs inline after a listing is posted; notifies and emails every other member whose saved search matches.
- _sweep_renewals() - board.py:68, called inline at the top of every GET /tour-board (board.py:94). Not a scheduler, not a thread, no cron entry: the expiry notice is sent by whoever happens to load the board next. It notifies and emails each listing within RENEW_NOTICE_DAYS (3) of expiry that has not had a notice, then sets renew_notice_at so it fires once.
- acr_console._refusals = threading.local() (acr_console.py:129) — per-thread storage for the last 401/403/429 message, not a background thread.
- acr_desk.refresh(scan_id) — a manual poll: the person presses Refresh and the handler asks ACRCloud where the job is. Deliberately not a timer, so an unattended page cannot spend the account's quota.
- Audio job poller: audio_jobs.run_pending(partner_id, limit=25) (audio_jobs.py:375), reachable only from POST /admin/audio/poll (owner only). No scheduler calls it.
- Audio retention sweep: audio_retention.sweep(now, limit=500, dry_run) (audio_retention.py:155), reachable only from POST /admin/audio/sweep (owner only, dry run by default). grep finds no cron or scheduler caller in this repo — the module docstring says it is meant for the backup/cron path, and the code does not have that wiring.
- Background threads: release_ready.py:651 starts a daemon thread named 'release-ready' per job step, bounded to four per process by release_ready.py:633 BoundedSemaphore(4). This is the only thread the running app starts. acr_console.py uses threading.local, audio_elevenlabs.py and stage_adapters.py use Locks only.
- before_request chain touching this area, in order: _resolve_partner (app.py:4871), plan_gate (app.py:4957), demo_lock_gate (app.py:5044), team_seat_gate (app.py:5110), acting_as_change_note (app.py:5165), page_switch_gate (app.py:5210). after_request: _team_audit_write (app.py:5157), _acting_as_change_write (app.py:5185).
- board_store.init_board() - board_store.py:42, run once at app start via board.init (app.py:14505). Performs ALTER TABLE migrations, then repair_all_text(), migrate_legacy_listings() and migrate_legacy_replies(). All idempotent.
- Boot sweep — tour_os.init() (tour_os.py:4999) calls tour_store.adopt_all_orphans() so a Tour Hub show sitting on no tour joins one at process start; wrapped in try/except so a boot never fails on it.
- Boot-time work inside create_app: the demo-account seeding loop (app.py:737-753) creates the four showcase logins, forces their plans, rewrites their passwords from DEMO_PASSWORD and calls demo_seed.seed_statements; then app.py:758 iterates every user and calls _grant_owner_plan. Both run on every process start, once per gunicorn worker.
- Client-driven polling transports (no server thread): GET /stage/<show_id>/events, GET /stage/guest/<token>/events (cursor over stage_events.seq) and GET /lights/remote/poll (drains light_remote_cmds).
- db.roll_seen(user_id) — fired once per session on the first Command Center/Overview render to stamp the visit for since_engine; skipped for a team seat.
- Device API polled from outside the app — POST /bridge/heartbeat, /bridge/pull, /bridge/ack, /bridge/reconcile (stage_os.py:420-457), driven by tools/stage_bridge_daemon.py on the venue network with a device token.
- In-process simulator drive — stage_os._drive_if_simulated (stage_os.py:261) calls stage_bridge.run_local for one cycle after a send; stage_bridge.run_local refuses any adapter whose spec is not simulated.
- In-process state, not shared across gunicorn workers: app.py:1154 _demo_access_seen (30s per-IP throttle on the demo lead form) and signup_guard._seen (reached on every public sign-up since 2026-09-21). No threads, schedulers or timers are started anywhere in this area.
- In-request opportunistic work rather than a job: app.py:1707 completes a small batch of pending Spotify pre-saves on a page hit, with the comment 'No cron needed'.
- Lazy expiry, not a scheduler: fan_import_drafts older than 24h are deleted by whichever draft read or write comes next (db.py:4316 put_fan_import_draft, :4335 get_fan_import_draft, :4367 drop_fan_import_draft, and links_store.py:252 confirm_list_import).
- Lazy on-request work, not a scheduler: app.py:1705 _process_due_presaves() runs on every public view of a released smart link and (a) sends the one-time release email via app.py:1679 _send_release_emails() and (b) completes pending Spotify pre-saves in a batch. Its own docstring says 'No cron needed'.
- Lazy settling instead of a worker: audio_studio.py:480 calls audio_works.settle_work for a queued/running item when its owner opens the page, and templates/audio_studio_item.html:240 reloads the page every 20 seconds while it waits.
- No background worker for statement parsing, the MLC sweep or the store check — all three run inline on the request that triggers them (the MLC sweep is bounded to 25 ISRCs per press by recovery_mlc.PER_SWEEP).
- No cron entry, scheduled task or background thread exists anywhere in this area — grepped the fan modules for Thread/schedule/cron and found none.
- No cron entry, scheduler or background thread exists for this area: render.yaml declares only the gunicorn web service, and the only threading in these modules is stage_adapters' per-device instance lock (stage_adapters.py:165, :261).
- No cron entry, scheduler, thread or background worker exists in this area. The RoEx webhook (/webhooks/roex/<jid>/<token>) belongs to the Creative Studio / Release-Ready area, though its results are displayed on /metadata-passport and /tracks/<id>.
- No scheduler is defined in the repository: render.yaml declares one web service and a disk, and no cron job or worker. Procfile declares only the web process.
- No scheduler, cron entry, background thread or webhook receiver exists anywhere in this area — grep for Thread, schedule, cron and webhook across press_desk.py, press_store.py, partner_os.py, partner_store.py, partner_billing.py, epk_config.py and press_config.py returns no matches.
- No scheduler, cron entry, thread or timer for either job exists inside this repo: render.yaml declares only the web service (no cron job), and none of statements_engine, recovery_engine, recovery_mlc, valuation_engine, capital_engine, documents_engine, rights_conflicts, qualification, trust_score, insights_engine, sync_simulator, report_builder or contract_reminders imports threading or a scheduler.
- NO scheduler, worker, queue or cron entry exists in this area. signal_ingest.py:3 states it outright, acr_desk.py:33 states it for the Fingerprints desk, and render.yaml defines a single gunicorn web service with no cron job.
- NO webhook receiver in this area. The app's webhook routes (/webhooks/resend, /webhooks/hypeddit/<token>, /webhooks/stripe, audio_webhooks) all belong to other areas.
- Out-of-process DMX forwarder — static/tools/lx-bridge.py, downloaded from templates/lights.html:150 and run on the operator's own machine; listens on 127.0.0.1:7070 and forwards to UDP 6454 (Art-Net) / 5568 (sACN).
- Per-process daily cache, not a job: fan_audience._SHOWCASE_CACHE rebuilds the ~14,400 generated showcase rows once per calendar day per worker (fan_audience.py:547 def showcase()).
- POST /admin/audio/poll (audio_admin.py:176) — audio_jobs.run_pending(). audio_jobs.py:376's docstring says 'Called by the route and by cron'; grepped run_pending — the only caller is this owner-only route. No cron calls it.
- POST /admin/audio/sweep (audio_admin.py:161) — audio retention destruction. audio_retention.py:28's docstring says sweep() 'is called by the backup/cron path'; grepped audio_retention.sweep across the repo — the only caller is this owner-only route. No cron calls it.
- POST /api/suites/credits (app.py:932) — server-to-server receiver for the suites; no session, a token signed under sb_suite_sso.CREDIT_SALT is the authorisation
- POST /backup/run (app.py:13767) — meant for an external scheduler presenting BACKUP_TOKEN via the X-Backup-Token header or a token form field; _valid_backup_token (app.py:4884) lets it past the login wall for this path only. No cron entry for it exists in this repo's render.yaml.
- POST /backup/run (app.py:13767) — the off-box backup. Intended for an external scheduler presenting BACKUP_TOKEN; app.py:4963 gives an anonymous POST an explicit 403 rather than a redirect so a cron log cannot read it as green. Records every outcome, success or failure, under app_kv 'backup_last_run', and notifies the OWNER_EMAIL account on failure.
- POST /reminders/run — contract renewal reminders plus release_ready.run_due(). REMINDERS_CRON_TOKEN in the X-Reminders-Token header, or a signed-in owner. Result stored under app_kv 'reminders_last_run' (a scheduler's run also under 'reminders_last_scheduled_run'). Since 2026-09-23 a token-less or wrong-token POST gets 401 JSON with the reason, not the 302 to /login a cron log reads as success.
- POST /reminders/run — scheduled job endpoint. Runs contract_reminders.run(), which fires the 60/30/7/1-day renewal milestones, writes document_reminders and emails where configured; then records the run and also calls release_ready.run_due() in a try/except. No scheduler calls it yet. The owner's Render cron, daily at 09:00 UTC, would run: code=$(curl -sS -o /dev/stderr -w '%{http_code}' -X POST -H "X-Reminders-Token: $REMINDERS_CRON_TOKEN" https://app.streetbankermusic.com/reminders/run); echo "HTTP $code"; [ "$code" = 200 ]
- POST /webhooks/resend (app.py:1275) — webhook receiver. Resend inbound email → signature verified with RESEND_WEBHOOK_SECRET → recipient local part resolved to an account via ingest_tokens → CSV attachments run through the same _ingest_statement the upload uses, writing statements/statement_rows and a recovery or statement notification. Aborts 404 when emailer.inbound_configured() is false. Anonymous by design ("/webhooks/" prefix is public).
- POST /webhooks/stripe (app.py:5755) — Stripe webhook receiver; 404 unless a signing secret exists, signature-verified, answers 503 'retry' when Stripe cannot be read so the event is redelivered
- Press pitch sending is synchronous and inside the request: press_desk.pitch_send loops the recipients and calls email_provider.send once per address before redirecting (press_desk.py:498).
- Release-Ready background steps: release_ready.advance(job_id) runs one step at a time under a database lease in a Python thread, capped at four per process by a BoundedSemaphore (release_ready.py:636 _spawn). There is no worker process — a job that cannot get a slot stays due for the next poll.
- Release-Ready queue sweep: release_ready.run_due(limit=20) (release_ready.py:1168), called from POST /reminders/run (authorised by REMINDERS_CRON_TOKEN or the owner since 2026-09-23; no scheduler calls it yet) and from POST /admin/release-ready/run. It moves reports paused on the budget, polls that came due, and raises an alert for a paid master not stored after 30 minutes. It can never start a paid RoEx retrieval that was not paid for.
- Request-time expiry on the Stage desk and every poll — stage_bridge.expire_stale(show_id, user_id) (stage_os.py:162 and :197): the poll is the clock, so a dead command cannot sit at 'sent' forever.
- Request-time sweep on GET /tour-board — board._sweep_renewals() (board.py:68, called at :94) notifies and emails the owner of every listing at or past expiry, then marks the notice so it is sent once.
- Request-time sweep on GET /tours — tour_store.adopt_orphan_shows(user_id) (tour_os.py:1244) and tour_mockup.ensure_for(user) (tour_os.py:1252). Skipped entirely on a team seat's visit.
- RoEx rate limiter: roex_client._rate_take (roex_client.py:456) takes a slot from a sliding window kept in the SQLite roex_rate table so both gunicorn workers and every thread share one count.
- Roster invitation email is synchronous and best-effort inside the POST: app.py roster_invite sends only when emailer.configured() and the join link stays visible on the roster either way (app.py:6722).
- Schema creation on boot: passport_os.init() (passport_os.py:269) calls passport_store.init_passports(), advance_store.init_advance() and stage_store.init_stage() at app-factory time, so the Show Passport and Stage Control tables exist before any route needs them.
- Schema creation runs once at startup: press_store.init_press() and partner_store.init_partners() are called from create_app (app.py:14435 and 14455).
- signal_ingest.ensure_universe() — request-triggered, runs on every /signal dashboard and board view; fills an empty universe once (up to 25 artists) and then does nothing.
- signal_ingest.evaluate_alerts(org_id) — also runs on every GET of /signal/alerts.
- signal_ingest.refresh_universe(force=True) — manual, from the POST /signal/admin/refresh button.
- signal_ingest.sweep(org_id) — request-triggered on the /signal dashboard; refreshes at most SWEEP_ARTIST_BUDGET = 3 stale artists (staleness REFRESH_AFTER_HOURS = 12) then evaluates that org's alert rules.
- Standalone daemon (not part of the web process): tools/stage_bridge_daemon.py — runs on a venue network, heartbeat → pull → verify → apply → ack against the /bridge/ routes. 14 tests in tests/test_stage_bridge_daemon.py.
- Start-up migration: db.link_song_tables() runs from db init on every boot (call site db.py:1311, body db.py:3944). It gives every Track Passport a catalog row and every catalog row a passport, matching by ISRC then title; it opens rows and deletes nothing, and is a no-op once everything is linked.
- StemSplit temp-file cleanup: stemsplit_provider.sweep() drops parked sources older than an hour — not scheduled; it is called inline from park_source() on each new upload (stemsplit_provider.py:142/154).
- store.set_collab_seen(uid) - written on every GET /marketplace?tab=discover (app.py:11409), skipped while acting through a team seat.
- Tenant resolution runs as a before_request on every request (app.py _resolve_partner, registered before plan_gate; it sets g and can never bounce a request), and partner act-as change auditing runs as a before_request/after_request pair (app.py:5168, 5188).
- tools/repair_board_encoding.py - a manual CLI (dry run by default, --apply to write). No cron entry references it.
- Webhook receiver — POST /webhooks/stripe (app.py:5755); the checkout.session.completed / async_payment_succeeded branch with metadata kind 'tour_vip' calls tour_os.claim_vip_session (app.py:5781-5786), which is idempotent against the success redirect.
- Webhook receiver: /api/vault/from-motion (app.py:10948) - 404 unless MOTION_HANDOFF_ENABLED, and 501 with an explanatory message when it is on. Writes nothing.
- Webhook receiver: POST /webhooks/audio/<provider> (audio_webhooks.py:58) — signature verified over the raw body before parsing, deduped on (provider, external_event_id), always 200 once the signature is good so the vendor does not retry forever.
- Webhook receiver: POST /webhooks/roex/<jid>/<token> (release_ready.py:2191) — unsigned by RoEx, so a valid per-job token only marks the job due and the next step re-reads RoEx itself.
- Webhook receiver: POST /webhooks/stripe (app.py:5755) — the fan-club branches add a member on checkout.session.completed and cancel one on the subscription-deleted event.
- Webhook receiver: POST/GET /webhooks/hypeddit/<token> (app.py:1323) — one address per account, always answers 200 to a known token so Hypeddit never retries into a duplicate; unknown token 404. Per-account daily cap of 2000 deliveries enforced by an app_kv counter (hypeddit_ingest.py:47 DAILY_CAP, :283 _over_cap).
- Webhook receivers in this area: none. /board-renew/<id>?t=<token> is a public GET link from an email, not a webhook; email_provider's inbound webhook (RESEND_WEBHOOK_SECRET / RESEND_INBOUND_DOMAIN) is not used by anything in this area.
- Webhook receivers, all five: POST /webhooks/resend (app.py:1275, svix signature), POST /webhooks/hypeddit/<token> (app.py:1323, URL token), POST /webhooks/stripe (app.py:5755, Stripe-Signature), POST /webhooks/audio/<provider> (audio_webhooks.py:58, per-provider secret over the raw body), POST /webhooks/roex/<jid>/<token> (release_ready.py:2191, per-job token hash). All sit under the public /webhooks/ prefix (app.py:4811) and each carries its own authorisation.
- Write-on-read side effect (not a scheduled job): GET /releases/autopilot (app.py:6093) files a 'Release risk' notification for any dated track inside 14 days with Clean Release blockers, deduped against existing notification titles.

## Unverified

What the inspection could not confirm from code, and why. This list is
as much a part of the ledger as the rest: a gap named is a gap somebody
can close, and nothing here was guessed to fill it.

**Platform and plumbing (db, storage, uploads, email, observability, PWA, static/design system, gating middleware, webhooks, backup/cron, tools, tests)**

- Whether the live and staging Render services actually set RESEND_API_KEY, EMAIL_FROM, SENTRY_DSN, the four R2_* vars, the four BACKUP_S3_* vars or BACKUP_TOKEN. Nothing in the repo records a value and I did not touch Render. Every one of these decides Live vs Stubbed for its feature at runtime, so each of those statuses is conditional.
- Whether a nightly backup cron actually exists. The endpoint and its token check are in code; render.yaml defines no cron service and no schedule file exists anywhere in the repo. The schedule, if there is one, lives outside this repository.
- Whether R2 is reachable from the running deployment. /storage/diag performs a real put/get/delete round trip, but I only ran it against an unconfigured checkout ({"configured": false}) and did not call it against a live service.
- Whether the object store or the disk holds today's uploads on production. blob_store.save writes to R2 OR disk and never both, so which one a given stored path points at can only be read from the live database.
- Whether any Sentry event has ever been delivered. observability.configured() is a presence check by design and observability.py:98 returns True as soon as sentry_sdk.init does not raise.
- Whether SESSION_COOKIE_SECURE is True in production. It keys off os.environ.get("RENDER"), which Render sets, but I could not confirm the running environment.
- Which value SECRET_KEY holds on the live service. render.yaml generates one; the code falls back to a hardcoded string if it is unset, and nothing on any page or diagnostic reports which is in use.
- Whether the DATABASE_PATH / UPLOADS_DIR fallback has ever fired in production. Both print a warning to stdout and nothing else — there is no row, no notification and no readiness signal, so a deployment silently running on ephemeral storage would look identical to a healthy one.
- How large the api_cache table has grown. Nothing evicts it, so this is a disk question I can only answer from a live database.
- Whether static assets are in fact being cached by Cloudflare. The middleware sets the headers correctly under the test client, but what the edge does with them is not observable from code.
- Whether the committed static/css/tailwind.css is current. tests/test_stylesheet.py samples template classes against it and passed on the subset I ran, but I did not run that file or rebuild the sheet to compare byte for byte.
- Whether the JS harnesses under tests/js run in CI. They are gated on SB_NODE_BIN / SB_REQUIRE_JS_TESTS and I did not run them; there is no CI configuration file in the repository to read.
- Whether email_provider.release_email_html renders correctly in a mail client. It emits border-radius:var(--sb-r-panel) three times (email_provider.py:257-271) and mail clients do not resolve CSS custom properties, so those corners will be square — I could not confirm this in a client, only read it in the source.

**Press and partners — Press Desk (announcements, contacts, pitches, coverage, public token pages), the EPK / press kit and its public and private share surfaces, the legacy one-sheet, the Label roster, Partner OS (reseller console, act-as, branding), white-label tenant resolution and the owner's reseller back office**

- press_desk.py and press_store.py were BEING REWRITTEN by a concurrent session during this pass. git status shows both modified against HEAD (+251/-10 lines); press_desk.py grew from 525 to 643 lines between two reads, and templates/press/announcement_desk.html did not exist at one probe and did at the next. The line numbers cited for those two files, and the new combined announcement+pitch desk (count_line, send_button, _desk_context, compose_dateline/compose_embargo/split_dateline/split_embargo, embargo_label), are uncommitted working-tree state, not HEAD. Re-read both files before trusting those references.
- Whether templates/press/release_form.html is now dead. The handlers were switched to announcement_desk.html mid-pass, leaving release_form.html on disk with no handler rendering it — but that switch is uncommitted, so I cannot say whether it is the intended end state.
- Real email delivery. With RESEND_API_KEY and EMAIL_FROM unset, everything past email_provider.send() — the actual Resend call, the per-recipient sent/failed marking, last_contacted, mark_pitch_sent, and the base64 press-kit attachment built by _kit_bytes — was never executed. Only the 409 refusal path was exercised.
- The partner logo. partners.logo_path exists, partner_store.branding returns it and base.html/auth_base.html render brand.logo, but no route writes it and templates/partner/branding.html has no logo field, so I could not confirm the rendering path end to end.
- Whether a reseller's artist ever reaches the app on the reseller's own host in production. The branded shell only appears when the Host matches partners.domain or <slug>.PARTNER_ROOT_DOMAIN; whether DNS and the hosting service are wired for that is outside the repo.
- EPK metrics figures. No CAP_METRICS provider is configured in this environment, so _epk_real_stats returned nothing and the kit showed "Not measured" — the Monthly Listeners / Followers branch of epk_config.real_stats was never exercised with data.
- Bandsintown tour-date fallback on the press kit — BANDSINTOWN_APP_ID is unset, so bandsintown_provider.configured() is false and the fallback returned empty; the parsing of real events was not exercised.
- Shopify merch embed on the owner's and the demo kit — SHOPIFY_* names are unset, so shopify_buy.context() was never exercised from _epk_store.
- The audio play beacon on the private pitch link (POST /pitch/<token>/play writing an epk_share_events 'play' row) was not exercised; only the view event was.
- brand_contrast.check_accent rejecting a low-contrast accent. I saved a passing colour (#ffcc55) and saw it stored; I did not submit a failing colour, so the refusal path on /partner/branding is unconfirmed by execution.
- Whether the /epk tier asymmetry is intentional. plans.required_tier matches "/epk" exactly, so the editor is Artist-gated (Fan gets 402) while every write sub-path is open to any signed-in account — a Fan account successfully saved an EPK, created a share link and saved a kit to the Vault in a probe. I can prove the behaviour from code and probe; I cannot tell from code whether it was intended.

**account-billing**

- Whether STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET are actually set on any deployment — I read no env values and made no network calls, so every Stripe feature above is marked Stubbed on the evidence of this checkout, not of production. A deployment with the key set would move checkout, portal, sync, webhook and referral settlement toward Live.
- Whether a real Stripe checkout, subscription change, portal session, coupon or balance credit succeeds. stripe_provider._http is the only wire and it was never called; all probes ran with Stripe unconfigured.
- Whether the suite services (The Room, REACH, Noise Lab, Tour, Motion) accept the SSO token or call back to /api/suites/credits. Their code is not in this repository; only the minting side is verifiable here.
- Whether any email is actually delivered (password reset, team invite, roster invite, plan-grant notice, demo password). RESEND_API_KEY was unset, so every send path returned its honest 'not configured' branch.
- Whether the off-box backup upload and the R2 object deletes on account reset/delete succeed. backup_store and blob_store were unconfigured; the delete loops swallow exceptions by design so a failure would be invisible from the route.
- Whether a real Stripe plan purchase is ever claimed without a webhook. Reading app.py:12762, GET /billing claims a credit-pack session by session_id but not a membership session, so a plan checkout is claimed only by the webhook, POST /billing/sync, or the member pressing Subscribe again. I could not test the redirect path with Stripe live.
- billing_config.get_billing_data matches the account's plan name against its own PLANS list (Free / Pro Plan / Label) while the app supplies plans.PLAN_NAMES (Fan / Artist / Pro / Label), so only 'Label' matches and everything else falls through to plans[1]. It is demo-only, so the practical effect is limited, but I did not confirm every demo login's rendering.
- POST /admin/release-ready/settings is a Settings panel (templates/settings.html:331) whose handler lives in release_ready.py:2369, outside this area. I verified the route exists but not its behaviour.
- POST /admin/soundcharts-budget (app.py:13388) is an owner Settings panel in this page but its budget semantics belong to the Signal/data-sources area; I confirmed only the owner gate and the redirect.
- Whether team_areas.room_paths() covers every page in practice. It is built from rooms.catalogue() at first use (team_areas.py:151) plus a hand-written EXTRA map, so a page in neither is treated as room-less and allowed through to any seat. I confirmed the gate works for the rooms I probed, not for all eight.

**collab-marketplace**

- app.py was being edited by another session throughout this pass: its md5 changed four times and the marketplace block moved from line 11072 to 11408, gaining a new _demo_not_a_member guard on post/apply/save/report/choose/rate mid-pass (a change whose comment cites 'the walk of 2026-09-20'). All app.py line numbers above are as of md5 0499507e3e6b5ecbd2f181131abcd841 and will drift; the route decorators and function names are the stable anchors. board.py and db.py also changed during the pass (board.py gained a `counts=` kwarg on the listing view).
- Email delivery end to end. emailer.configured() is False without RESEND_API_KEY, so none of the four send sites in this area was exercised against Resend. What the code proves is that the in-app notification always fires and the email is attempted only when a key is present, each inside try/except.
- Whether the demo showcase (collab_market.SHOWCASE) renders in production. It needs a session signed in as one of the four seeded addresses in demo_accounts.ACCOUNTS, which I could not do without their passwords. The gating expression and the 'Showcase ... not members' label were read in code and tests/test_collab_marketplace.py:155 locks that a real account never sees it.
- Whether PUBLIC_BASE_URL is set on the deployed services. It is what board.py:72 and board.py:155 put into the renewal and watch-alert links, so an unset value would ship relative-looking links in email; the default at app.py:77 was not traced.
- ~~Whether the artist ids that templates/discover.html links as /network/<artist_id> actually exist in network_config._PROFILES.~~ CHECKED 2026-09-21: all nine (cass-oram, dj-codec, grid-runner, kilo-byte, lila-rose, marco-velocity, milo-tran, nova-reign, sable-wynn) are ids in network_config._PROFILES, so none of those links 404. They are now drawn for a showcase session only; see "Discover sample feed" under Fans and audience.
- Whether any deployed service currently has SUITE_GATES or RENDER set, which is what decides whether the /tour-board Pro gate is on at all. plans.gates_on() reads the environment; I probed both states locally but cannot see the deployment's variables.
- board_store.stats()['matched'] counts rows still at status='filled'. A listing marked filled and then reopened keeps its filled_via but leaves that count - observed in my probe (matched went to 0 after reopen), not asserted by any test I found, so whether that is intended is unverified.
- Whether the marketplace 'Network' tab pointing at the Pro-gated /tour-board/outreach from the fan-open /marketplace is known. The gate mismatch is confirmed in code and by probe (fan and artist get 402); the intent behind it is not stated anywhere I read.
- I did not sign in through an actual team seat. The team-seat access claims above come from reading app.py's team_seat_gate (blocked prefixes, team_areas.allows) and from calling team_areas.room_for_path/allows directly on each path, not from an end-to-end seat session.

**command-signal**

- Whether any provider key is actually set on the live or staging deployment. Every judgement about Signal, Pulse and the Fingerprints desk being Stubbed is from code plus an empty local environment; render.yaml declares only SECRET_KEY, DEMO_PASSWORD, ROEX_API_KEY, SENTRY_DSN and DATABASE_PATH, and the rest are set in the Render dashboard, which I did not and must not read.
- Whether the real vendor endpoints answer. I did not make a single outbound call — no Soundcharts, MusicBrainz, Discogs, YouTube, MLC, Bandsintown, Spotify, Deezer or ACRCloud request. Adapter "Live" claims mean the HTTP code exists and is wired, not that the vendor responded.
- Whether ChartmetricAdapter, SoundExchangeAdapter and SpotifyMetadataAdapter would really raise NotImplementedError in production. The classes implement no methods and inherit the base class's raises, but I could not configure them to prove it without credentials.
- The exact behaviour of /signal and /operator-desk for a non-owner who IS on the roster. I proved the owner path (200 everywhere) and the no-seat path (403), but I could not create a genuine desk_users/signal_members row for a second account without writing to a database, so the per-role refusals in PERMS are read from code only.
- Whether the showcase branch in _front_money_context and search_config._demo_search fires for any account other than demo@streetbanker.io. It keys on demo_accounts.is_demo_email, whose full list I did not enumerate.
- Whether the rooms layout is on for the live deployment. rooms.enabled() reads the app_kv key "nav_layout" first and NAV_ROOMS second; on a fresh local database neither is set, so the hub sidebar is what I saw. Which one the live and staging services use is a runtime fact.
- Whether desk_store.seed_if_empty()'s five sample leads are still present on the live Operator Desk. The code plants them into any empty desk_leads table on every boot; whether the owner has since deleted them is a data question, not a code question.
- Whether signal_store.sync_desk_roster has already mirrored real Operator Desk seats into signal_members on the deployment, and therefore who can currently open Signal.
- The Pulse "everything" panel (pulse_everything.build) and the instrument strip (pulse_signals.build) beyond their honesty contract. I read both modules and confirmed they return None/"not measured" rather than zeros, but I could not render either with a live metrics provider to see which of the six sections actually fill.
- Whether templates/desk/files.html, templates/signal/briefs.html and templates/signal/brief.html are referenced from any non-Python, non-HTML source (a JS bundle, for instance). I grepped .py and .html only; within those two file types nothing renders or links them.
- Whether the fan-plan gap on /room/<key> and /desk/<hub_key> is intentional. A fan-plan account opened /room/analytics, /room/fans and /desk/command at 200 in my probe while every card behind them answers 402, and /desk/command computed that fan's Growth and Trust scores. I found no code comment and no test either way, so I am reporting the behaviour rather than calling it a defect.
- Whether the alert rule "channel" field was ever meant to do more than in_app. signal_store.create_alert_rule stores it and the form offers it, but nothing in this area reads it back to send anything; I did not search the whole repo for a consumer outside Signal.

**fans**

- app.py was being rewritten by another session DURING this audit — it went from ~13,800 to 14,100+ lines mid-read (an import statement even parsed as a SyntaxError on one read), and its mtime is 2026-09-20 17:03:08. All app.py line numbers above are from that 752,338-byte revision; fan_room.py and templates/links_fans.html were touched at 16:59 the same day. Line numbers may have moved again since.
- Shopify: no SHOPIFY_* is set here, so fetch_customers(), granted_token() and the client-credentials grant were never called against the real API. Only the local write path (import_fans → links_store) and the status() copy were read; whether the store actually returns customers, and whether the app's released version really carries read_customers, is unverified.
- Stripe: no STRIPE_SECRET_KEY or STRIPE_WEBHOOK_SECRET here, so the fan-club Checkout, the ?joined= return verification and both webhook branches were never exercised. Whether a real join produces a club_members row end to end is unverified.
- Resend: no RESEND_API_KEY here, so the release-day email, the fan-club drop notifications and the members-area magic link were never sent. Whether emailer.send() succeeds against a verified domain is unverified.
- Spotify: no SPOTIFY_* here, so /presave/<slug>/start, /presave/callback and the library-save delivery were never exercised. Whether a pre-save actually lands in a fan's library is unverified.
- Odesli: no network calls were made, so /links/autofill was never exercised against api.song.link.
- Hypeddit's own field names are undocumented (hypeddit_ingest.py module docstring says so). I verified the receiver files a fan from {"Email Address", "Name"}, but whether Hypeddit's real payload (or a Make relay's) carries a shape extract() recognises is unverified from code alone.
- Owner identity: _is_owner_email compares SHA-256 hashes (app.py:100) plus whatever OWNER_EMAILS holds, so I could not determine which accounts are owners. Everything marked 'owner only' is owner-only by construction, not by a verified account.
- sales_switch: app_kv 'online_sales' was not set in any database I touched, so the switch was read as off. Its state on the deployed services is unknown (I did not and could not read Render).
- Whether the demo account demo@streetbanker.io exists with that password on deployed services — I only confirmed it on a locally seeded throwaway database.
- fan_audience.US_CITIES claims to hold real public coordinates; I did not check the 100-odd latitude/longitude pairs or the Albers affine fit against an external source.
- Client-side behaviour of static/js/fans-audience.js (the region select-all, the tag chips, the 'How these are measured' toggle) was not executed — only the server-rendered HTML was checked.
- The Fan Room's Collab open-brief count joins collab_requests, which belongs to another area; I confirmed the query runs but not that the collab board's own semantics match what the tile claims.

**money**

- Whether MLC_USERNAME/MLC_PASSWORD/MLC_ENABLED, SONGSTATS_API_KEY, SPOTIFY_CLIENT_ID/SECRET, RESEND_* or R2_* are actually set on any deployed service. This was a read-only local checkout, I did not read .env or .env.example values, and render.yaml declares only SECRET_KEY, DEMO_PASSWORD, ROEX_API_KEY, SENTRY_DSN and DATABASE_PATH. So the MLC sweep and the statement drop-box are Partial on the evidence here; they may be fully live in production.
- Whether anything actually calls POST /backup/run on a schedule: render.yaml in this repo contains no cron service (the nightly backup cron lives in the Render dashboard). POST /reminders/run: nothing calls it as of 2026-09-23, and the pages say so until a scheduler run is on record (contract_reminders.scheduled).
- advance_store.py — named in the brief for this area, but the code is not about money. It is the Stage/Tour show-advance store (show_passports, show_questions, show_conflicts), imported by passport_os.py, stage_os.py, stage_bridge.py and tour_os.py. Nothing in it touches royalties, capital or a cash advance. The brief's file list and the code disagree; the code wins.
- statements_engine.py is the real name of what the brief called "statements_engine (find its real name)" — it exists under that exact name and is imported at app.py:141. There is also a separate statements_desk.py (page layout) and statements are surfaced through royalties_desk.py and recovery_desk.py.
- /conflicts computes real data but is badged Sample: "conflicts" is absent from hubs._BASE_LIVE (hubs.py:155) and from hubs.live_keys(). I verified the absence by grep; I did not open the sidebar template to confirm exactly what badge renders as a result.
- I did not open templates/capital.html, templates/funding.html or templates/sync_pack_public.html, so I cannot say what disclaimer text those pages actually print next to their simulated figures — only that the data handed to them is hardcoded (capital_config, funding_config) or real (sync_packs).
- The exact behaviour of the Royalties page when an account has statement rows but the chosen period filters them all away: royalties_desk.build returns None for empty `rows` and the template branch on desk=None was not read.
- royalty_types.territory_report is reached only from report_builder.py:196 (the investor snapshot). I confirmed the call site but did not exercise that report builder.
- Whether /capital is reachable from any rendered page rather than only by typing the URL: the only live references are the route itself, plans.world_for_path, team_areas.EXTRA and a command_center.html icon-picking expression (`"/capital" in route`). tests/test_sidebar_fold.py lists it as PARKED. I did not render every template to prove no link exists.
- I did not verify the per-plan behaviour by signing in as a fan-tier account; the 402 upgrade path is read from plan_gate (app.py:4972-4976) rather than exercised. My smoke run used a label-plan account.
- Partner-tenant behaviour (g.partner / partner_member acting on an artist's behalf) on the money pages: resolve_partner sets the context but I did not trace which money routes change behaviour under it, beyond _working_as_someone() hiding the statement drop-box address.

**releases**

- app.py was being edited by another session throughout this pass (mtime moved 16:14 -> 17:03 while I read it, and line numbers shifted by ~370). All app.py line numbers above are from a final sweep at 17:03 against a 14,527-line file and WILL drift. Two behaviours I observed changed mid-pass: _release_checks gained the dated-post rollout rule and the passport-aware ISRC hint, and /conflicts went from HTTP 500 to 200. Re-verify every app.py file:line before relying on it.
- /rollout-studio/<cid> NameError: fixed 2026-09-23 (rollout_overview reads campaign["user_id"]); tests/test_rollout_overview_reviewed.py reproduces the old 500 through the plan page and the overview.
- artwork_check.py: was uncalled when this ledger was written. Wired 2026-09-21 to POST /artwork/check and the Cover Studio panel; see its entry above.
- templates/os_tracks.html dead branch: proved unreachable by the plan matrix (artist/pro/label redirect, fan blocked 402) and by a live probe of both cases. Not verified for a hypothetical account whose plan string is absent or unknown - plans.allowed defaults such a plan to artist rank 1, which also redirects, but I did not construct that account.
- Demo-account catalog: app.py:2584 exempts email demo@streetbanker.io from the zeroing block, so that one account still renders the invented 1,248-track showcase. I did not sign in as it to confirm what the page looks like.
- Lockbox signature email: emailer.configured() is false on this checkout (no RESEND_API_KEY), so I confirmed the no-send path by reading the code, not by observing a delivery.
- MLC, Discogs, Songstats and Spotify: all confirmed to refuse honestly with no key (verified redirects ?mlc=off and ?discogs=off). Their behaviour WITH a key - response shapes, fill correctness, rate limits - is unverified from here; the /isrc/diag docstring itself says the Songstats response shape has never been confirmed.
- Pollinations.ai: no outbound request was made, so I verified the URL construction and the https://image.pollinations.ai/ save allowlist by reading, not by fetching an image.
- Team-seat behaviour: derived from plans.py, team_areas.py and app.py:4852 _TEAM_BLOCKED by reading, plus the path->room mapping run through team_areas.room_for_path. I did not create a seat and walk these pages as one.
- /passports suite gate: verified 402 with SUITE_GATES=on and 200 with gates off. The owner-bypass branch (_is_owner_email in plan_gate) was read, not exercised.
- The /catalog 'catalog_value' block is hard-zeroed for real accounts ({estimated_value: 0, trend all zeros}); whether the template hides or prints those zeros I did not check in templates/catalog.html.
- I did not run the repository's test suite. Test files named in this report (tests/test_release_desk.py, test_rollout.py, test_passport_routes.py, test_discogs.py, test_track_mlc.py, test_walk_release-studio_2026_09_20.py and others) were read for intent only - I have not confirmed they currently pass.

**studio-audio**

- app.py is being edited by another session while I read it — its size grew from 731,321 to 752,338 bytes and its mtime moved to 17:03 mid-task. Every app.py line number I cite was re-read at 17:03 and may drift again; the handler function names are stable.
- What the deployed services actually set. Every flag and key in my area was unset on this machine (probe: no AUDIO_* flag on, all nine adapters serving "mock", roex/blob/stemsplit unconfigured). Whether production sets AUDIO_INTELLIGENCE_ENABLED, ELEVENLABS_*, ROEX_API_KEY, STEMSPLIT_API_KEY, ACRCLOUD_*, R2_* or STRIPE_* is not knowable from code, and I did not read any environment I was not told to.
- The rr_open switch. release_ready_settings defaults it to "0" in code, but the live value lives in the app_kv table on the deployed database, which I did not read. So whether Release-Ready is open to artists today is not answerable from the repository.
- Whether ffmpeg exists on the Render box. convert_engine.available() returned True on this Windows machine; the deployment's PATH is not in code. If it is absent, POST /rack/convert is a 503 and the Rack's compressed-format panel is hidden.
- The real ElevenLabs, RoEx, StemSplit, ACRCloud and Stripe call paths were never executed — no key, and I was told not to sign in or spend anything. I read the request shapes and refusal paths, not live responses. StemSplit's probe_output_types() in particular makes live calls I did not run, so which separation modes the account holds is unknown.
- The webhook secret env name is built at runtime as "%s_WEBHOOK_SECRET" % provider.upper() (audio_webhooks.py:52). Only "elevenlabs" and "mock" adapters register, so ELEVENLABS_WEBHOOK_SECRET is the real one; MOCK_WEBHOOK_SECRET would also be accepted by that code, which I could not tell was intended.
- The credits wallet that decides suite_open for "the-room" comes from db.credit_balances (app.py:4752). The credit ledger is outside my area, so I state the gate but not what typically satisfies it.
- /suites/go/masterclip is a card in the Studio room (rooms.py:37) but MASTERCLIP runs on another service; I did not inspect it and it is not in my area.
- audio_desk.py, audio_signal.py, audio_meetings.py, audio_briefs.py and audio_agent.py share the audio_* prefix and the same gate and job runner, but belong to the Operator Desk / Signal area, not this one. I read audio_policy, audio_jobs, audio_store and audio_retention because the Studio lanes run on them; I did not audit those five surfaces.
- stage_rack.py is Stage Control's status surface for a venue edge device, not part of The Rack (/rack). The name collides; the code is unrelated. Out of my area.
- I did not verify what the Studio's delivery zip contains end to end by building one — I read studio_store.build_package (line 904) rather than running it, because doing so needs a project with locked versions and stored audio.

**tour-live**

- Whether GOOGLE_MAPS_API_KEY, EVENTBRITE_TOKEN, TICKETMASTER_API_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET and RESEND_API_KEY are actually set on the live deployment. The code reads them at request time and every provider degrades honestly without one; no value is in the repository and I did not read any environment.
- Whether Google has Routes API v2 enabled on the deployment's key. venue_geo.py:1 states it is not, and routes_available() latches off after a refusal — but that is a comment plus a runtime latch, not something the code can prove offline.
- Whether the online-sales switch is on in production. sales_switch.is_on() reads app_kv key 'online_sales' and defaults to off (sales_switch.py:22); its value lives in the live database, not in code.
- Whether TICKETMASTER_ENABLED is set. enabled() (ticketmaster_provider.py:83) returns false on any service with RENDER set unless the variable says 'on'.
- Whether the ENTTEC / Art-Net / sACN output has ever driven a real fixture. static/js/lights-engine.js frames correct packets and static/tools/lx-bridge.py forwards them, but nothing in the repository records a hardware test.
- Whether the X32 adapter works at all. stage_x32.py exists and speaks OSC, but its own spec says tested_model 'UNTESTED', verified is False, and tools/x32_bench.py has no recorded pass in the repo.
- Whether a Stage Bridge has ever run against a real console in a venue. tools/stage_bridge_daemon.py implements the full protocol; there is no deployment record either way.
- Whether the Stage Rack appliance exists. stage_rack.py:23 states plainly that it does not and that only the status surface is built; I could not verify the hardware claim beyond that comment.
- Whether venue photos, coordinates or ticket counts have ever been fetched on the live service. The report dictionaries are written into the Flask session per run (tour_os.py:2985, :3057, :3096) and nothing persists a history.
- How many tours, shows or VIP sales exist in production. I ran the test client only against a throwaway database under the scratchpad and never touched the live data.
- Whether /stage/<show_id> is reachable by a partner seat in practice. stage_os._resolve (stage_os.py:54) routes through partner_store.member_for_user / owns_user / can / audit; partner_store is outside this area and I did not verify its contents.
- Whether the tour suite gate is on. plans.gates_on() is true when RENDER is set or SUITE_GATES=on; I could not confirm the deployed environment, so every 'Pro where gates are on' note above is conditional.
- One code-vs-comment disagreement I could not resolve in the comment's favour: hubs.py:452 says 'LIVE_LAB_ENABLED is off by default and every /live route 404s while it is', while live.enabled() (live.py:54) returns True unless the variable is explicitly falsey. The code wins — Live is on by default — and the comment is stale.

**Memberships rack (app home)**

The memberships band on the app home as the photographed three-screen rack: CRT static on each screen at rest, and the tier renders when it is pointed at.

- Because: owner, 2026-09-23 - "make it when you hover over it they render". The plate is the Command Center's former plate (static/img/command-plate.webp; the rooms moved to the shorter room-plate.webp on 2026-09-23 and this rack kept the taller one) at the same measured screen fractions (split_home.RACK_SCREENS; a test holds them equal to partials/cc_rack.html). Prices are READ from plans.PLANS at render (the figure and the plan's own line), never typed into a template or cut into a photograph - the metal passes' one weakness, that a price change needed a new picture, and the owner's own render of this band had the prices baked in. At rest the glass is the photograph's own dark screen and NOTHING is laid over it at any point - no snow, no drift, no particle layer, no sweep (owner, 2026-09-23, three rulings in a row: TV snow "looks weird, it's cheesy"; a resting drift the same; a particle layer "turns into a square ... no static, nothing"). Hover or keyboard focus CUTS THE TIER IN the way the room racks' displays do (room-kit.css rk-frame / rk-split): slices thrown sideways, the name through the colour-split glitch, then the price, /month, the plan's line and the coming-soon line (hubs.suites_pending()) each in turn, about a second and a half in all; on the way out (.is-out, set by the script for the animation's length on mouseleave / blur / a tap elsewhere) the number breaks into slices and goes and the glass is dark again. Hard cuts, never a crossfade; prefers-reduced-motion makes both an instant swap. On touch the first tap renders the screen and the second opens it (static/js/memberships-rack.js, the band's one script; without it a tap is still a door). No media query decides who gets the static: the owner's own touchscreen laptop reports no hover and no fine pointer at all in Chrome, so a (hover) or (any-hover) gate showed him resolved screens and no static - found on 2026-09-23 and removed the same hour. Under 760px the plate steps aside and the screens stack, resolved; prefers-reduced-motion stops the jitter. Each screen is the door to /billing, one per tier as the passes were, and the link's name carries the whole reading so the tier is readable without pointing at anything. Fan is free and has no screen. The engraved passes are one switch away: Settings > Home page > Memberships band (owner-only POST /admin/membership-band, kv membership_band) or MEMBERSHIP_BAND=passes; nothing set means the rack.
- Routes: GET / (the split home renders it); POST /admin/membership-band (owner only)
- Files: templates/partials/memberships_band.html (the section, heading and credits; draws the rack or the passes); templates/partials/memberships_rack.html (the rack's tiers); templates/landing_split.html; split_home.py band(), set_band(), BANDS, RACK_SCREENS, get_split_home_config(); static/css/split-home.css (.sbrk-*); static/js/memberships-rack.js; static/img/command-plate.webp; app.py admin_membership_band(), settings(); templates/settings.html
- Access: public - the split home's anonymous visitors. The switch is owner-only, 404 to anyone else signed in.


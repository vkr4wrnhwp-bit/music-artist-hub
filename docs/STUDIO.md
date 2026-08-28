# Street Banker Studio

Status: **phase 0 shipped.** Schema, feature flag and documentation are in.
There is no Studio screen yet, and `studio_v1` is off by default, so this
release changes nothing an artist can see.

---

## 1. What the application is

Measured against the working tree, not assumed.

| Concern | What is there |
|---|---|
| Backend | Flask. One large `app.py` plus ~30 sibling modules; blueprints for newer areas (`tour_os`, `audio_studio`, `audio_desk`, `partner_os`) |
| Frontend | Jinja2, server-rendered, vanilla JS. No React, no build step for app code |
| CSS | Tailwind, **compiled and committed** to `static/css/tailwind.css`. `tests/test_stylesheet.py` fails on any NEW arbitrary/bracket class |
| Database | SQLite, raw `sqlite3`, **no ORM**. 75 tables in `db.py`, plus `audio_store` (9), `tour_store` (26), `partner_store` (3) |
| Migrations | Guarded `ALTER TABLE` inside an `init_*()`; `audio_store._migrate()` returns the steps it applied. **No framework, no down-migrations** |
| Auth | Session cookie, `current_user()`, an `@app.before_request` login wall plus `plan_gate` |
| Tenancy | `partner_id` (NULL = Street Banker itself) plus `user_id`. There is **no general organization model** — `partners`/`partner_members` is Partner OS reseller scoping |
| Object storage | `blob_store.py` — Cloudflare R2, hand-rolled SigV4, private bucket, short-lived presigned GETs. Falls back to local disk when unconfigured |
| Queue / worker | **None.** `audio_jobs.py` submits and polls inside the web request |
| Feature flags | Environment variables read at call time |
| Billing | Stripe; `plans.py` tiers, `billing.html` |
| Design system | `templates/_sb.html` macros, `sb-*` tokens. `tests/test_design_system.py` locks raw-hex, a 12px type floor and three radii |
| Nav | `hubs.py` — single source of truth for the sidebar, `/desk/<hub>` and the Ctrl-K palette |
| Deployment | Render, **one** web service: `gunicorn app:app --workers 2 --threads 4 --timeout 180`, Starter, **1 GB disk shared with the SQLite database** |
| Tests | pytest, ~1500 tests, ~28 min. Node checks under `tests/js/` |

## 2. What the Rack does today

- Route `app.py` `@app.route("/rack")` renders `rack.html` with the user's saved preset.
- Persistence: `rack_library` (saved chains) and `rack_presets` (current state per user). **Both hold work people did and must survive every migration.**
- Engine `static/js/rackdsp.js`: EQ-12, SUB-1, TS-1 tube, VLV-6, CAB-3 cab/mic, DYN-1 compressor, FX, bus, output. `buildChain()` is shared by live playback and offline WAV export.
- Mastering `static/js/loudness.js`: real ITU-R BS.1770-4 — K-weighting derived for the file's own sample rate, both gates, the −0.691 offset, EBU 3342 LRA, true peak by 4× polyphase FIR. Verified by `node tests/js/check_loudness.js` against the published EBU Tech 3341 cases. `audio_readiness.py` turns measurements into platform rulings.
- `templates/rack.html` and `static/js/rackdsp.js` are **exempt** from the design-system lock. Carry that forward.

**Reusable:** the DSP chain, the loudness engine, `audio_readiness.py`, the A/B and normalise-to-platform logic, `blob_store`, `audio_store`'s asset table, `audio_policy`'s rights and consent gating.

**Must be preserved:** `rack_library` / `rack_presets` rows; the `/rack` URL **and its `?stems=<work_id>` parameter**, which `rackdsp.js:loadStemsFromStudio` reads and the Audio Studio's "Open the stems in the Rack" button produces.

**Untouched:** the `audio_studio` blueprint, Remix Lab, the frozen Tailwind build, `hubs.py` ordering.

## 3. Four constraints that decide what "functional" can mean

Not objections — facts about the deployment.

1. **There is no background worker.** One web service, 180-second request timeout. Every job the design calls for (`audio_analyze`, `mix_render`, `master_render`, `stem_separate`, `delivery_package`) needs one. Adding a Render worker service is a paid change **only the account owner can make**. Until then: work that fits in a request runs inline; work that does not is queued and **reported queued**, never reported finished.

2. **`blob_store` has no multipart or resumable upload.** `put(key, data)` takes the whole body in memory. Presigned multipart against R2 is buildable, but it is new work, not configuration.

3. **R2 may not be configured.** Unset, audio lands on the 1 GB Render disk *shared with the SQLite database* — the failure `blob_store.py`'s own header warns about: "a handful of masters fills it and takes the database down with it." Studio limits upload size on the disk fallback rather than filling it politely.

4. **No external mastering or mixing provider is wired up.** The honest posture, and the one taken: ship the provider-neutral seam with a clearly labelled local/demo adapter and **disabled** production actions. `audio_providers.py` already does this for stems and dubbing; Studio follows it rather than inventing a second pattern.

`studio_config.readiness()` reports these four separately. A single "Studio: on" would repeat the Audio Studio's mistake of naming six flags and omitting the one that gated them all.

## 4. Data model — extend, do not duplicate

Most of the entities already exist under other names. Parallel tables would mean two answers to "where is this artist's audio", two retention policies, and two places to fix the next tenancy bug.

| Concept | Existing | Action |
|---|---|---|
| Audio asset | `audio_assets` | **Extended** — see §5 |
| Processing job | `audio_jobs` | Reuse; extend when a worker exists |
| Consent | `audio_consent` | Reuse |
| Rack chain / preset | `rack_library`, `rack_presets` | Reuse; add project linkage later |
| Project, version, analysis, finding, comment, approval, provenance | — | **New**, this release |
| Connector account | none | **Defer** — do not create a parallel credential store |
| Organization | `partners` / `partner_members` | Tenant key stays `partner_id` + `user_id` |

## 5. Migration, and how to roll it back

`studio_store.init_studio()` runs from the app factory, unconditionally — schema lands ahead of surface so the surface can ship in a later release against an already-migrated database. It returns the list of steps it applied, which is empty on a database that is already current.

**Created:** `studio_projects`, `studio_versions`, `studio_analysis`, `studio_findings`, `studio_comments`, `studio_approvals`, `studio_provenance`.

**Altered:** `audio_assets` gains `parent_asset_id`, `asset_role`, `version_label`, `sha256`, `proxy_storage_key`, `waveform_storage_key`, `sample_rate`, `channels`, `bit_depth`, `lossless`.

**Rollback: deploy the previous revision. Nothing else is required.** Every step is an additive `ALTER TABLE ADD COLUMN` with a default, plus `CREATE TABLE IF NOT EXISTS`. Nothing is dropped, renamed or retyped, so an older build reading this database simply ignores the new columns and tables. There is deliberately no down-migration: dropping columns in SQLite means rebuilding the table, and a rebuild of `audio_assets` to undo a reversible addition is a far larger risk than the addition.

If the tables must genuinely be removed (they hold no data until Studio ships a screen):

```sql
DROP TABLE IF EXISTS studio_provenance;
DROP TABLE IF EXISTS studio_approvals;
DROP TABLE IF EXISTS studio_comments;
DROP TABLE IF EXISTS studio_findings;
DROP TABLE IF EXISTS studio_analysis;
DROP TABLE IF EXISTS studio_versions;
DROP TABLE IF EXISTS studio_projects;
```

Leave the `audio_assets` columns. They are harmless, and removing them means a full table rebuild.

## 6. Environment variables

Names only — **never commit values.**

```
STUDIO_V1_ENABLED              the studio_v1 flag (STUDIO_ENABLED also accepted)
STUDIO_MIX_DOCTOR_ENABLED      requires STUDIO_V1_ENABLED as well
STUDIO_MASTER_STATION_ENABLED  requires STUDIO_V1_ENABLED as well
STUDIO_ALBUM_MASTER_ENABLED    requires STUDIO_V1_ENABLED as well
STUDIO_DELIVERY_ENABLED        requires STUDIO_V1_ENABLED as well
STUDIO_MAX_UPLOAD_BYTES        clamped to 200 MB; must stay under MAX_CONTENT_LENGTH
STUDIO_DEFAULT_RETENTION_DAYS  0 or unset = keep until deleted
STUDIO_PROCESSING_PROVIDER     empty = no provider; renders stay disabled
STUDIO_PROVIDER_BASE_URL       required before a provider counts as configured
STUDIO_PROVIDER_API_KEY        required before a provider counts as configured
STUDIO_WEBHOOK_SECRET          provider callbacks are rejected without it
STUDIO_HUMAN_REVIEW_EMAIL      where a human-review request is routed
```

Storage reuses the existing R2 variables (`R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`) rather than adding a second set. There is one object store; a `STUDIO_STORAGE_*` family would be a second credential path to leak.

## 7. Traps this codebase has already sprung once

- A blueprint registration landing between `@app.before_request` and `plan_gate` **disabled the login wall**. Placement in `app.py` is load-bearing.
- `CREATE TABLE IF NOT EXISTS` is not a migration. It does nothing to a table that exists.
- SQLite treats NULLs as distinct in UNIQUE/PRIMARY KEY. Use `''`, never NULL, for a tenant key. A whole-column UNIQUE over a `DEFAULT ''` column collides — use a partial index.
- A test watching `rootpage` to detect a rebuild **passes while the schema is rebuilt on every boot**; SQLite reuses freed pages. Assert on reported migration steps instead.
- `sb.btn`'s `extra` is appended to the *class* attribute. Pass `id=` as a real parameter.
- Static JS edits need the template's `?v=N` **and** `static/js/sw.js` `VERSION` bumped.
- New arbitrary Tailwind classes fail `tests/test_stylesheet.py` against the frozen build.
- An advertised upload cap above `MAX_CONTENT_LENGTH` is never enforced — Werkzeug refuses the body before routing. Shipped once as a 250 MB Remix Lab against a 25 MB ceiling.

## 8. What phase 0 shipped

- `studio_store.py` — schema, tenancy, projects, versions, provenance.
- `studio_config.py` — the `studio_v1` flag, room sub-flags, and `readiness()`.
- `studio_store.init_studio()` wired into the app factory.
- `tests/test_studio_foundation.py` — 23 tests: migration idempotency asserted on reported steps, cross-account read *and* write refusal, version numbering derived rather than supplied, the lock proven red against its own removal, rights recorded with who and when, provenance scoped, the flag off by default, a room flag inert without its parent, the upload cap held under the request ceiling, `readiness()` reporting components separately — and four tests that the Rack still works, keeps `?stems=`, stays in the nav, and that saved chains survive the migration.

## 9. What phase 0 did **not** ship

No `/studio` route, no screen, no upload, no analysis, no mix or master station, no delivery. `studio_v1` is off. The next slice is one vertical workflow — create project → upload → waveform → analyse → findings → comment → approve — not twenty empty screens.

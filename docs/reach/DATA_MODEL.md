# REACH — Data Model

SQLite through the Python standard library, in `reach/db.py`. Eight numbered
migrations, applied on first connection, tracked in `schema_migrations`.
Foreign keys are enforced (`PRAGMA foreign_keys = ON`); WAL is used for file
databases.

Configure the path with `REACH_DB_PATH` (default `reach.db` beside `app.py`).

## Why a database at all

The host app keeps its catalog in memory. Phase One requires campaign state to
survive a restart and every metric to be a count of persisted rows, so REACH
needs durable storage. SQLite gives that with no new runtime dependency. REACH
does **not** duplicate the host catalog: `recording.host_song_id` references
`royalty_data`'s own song id, and `royalty_data` stays the source of truth for
titles, ISRCs, splits, registrations and earnings.

## Entity groups

### Tenancy, identity and audit

| Table | Purpose |
| --- | --- |
| `tenant` | One per account. Every scoped table carries `tenant_id` |
| `principal` | Acting user with a role from `rbac.ROLES` |
| `audit_event` | Append-only, hash-chained (`prev_hash` → `hash`), per-tenant `seq` |

### Providers

| Table | Purpose |
| --- | --- |
| `provider_policy` | The machine-readable `ProviderPolicy` record as JSON, plus `kill_switch_enabled` and review dates |
| `provider_connection` | Per-tenant connection state, quota counters, last success/error |
| `provider_request_log` | One row per external call: operation, cost units, HTTP status, outcome |
| `kill_switch` | Global emergency stop and outreach send stop |

### Music identity

| Table | Purpose |
| --- | --- |
| `artist` | Mirrored from the host catalog's `master_owner` |
| `release` | Release-level identity (UPC, MusicBrainz release id) |
| `recording` | The canonical recording. Unique on `(tenant, host_song_id, version_type, mix_name, edit_name)` so a remix, radio edit, instrumental and clean version are **separate entities** |
| `platform_asset` | Per-provider external ids and URLs for a recording |
| `rights_attestation` | Scope, statement, who attested, when. Required before a campaign |

`recording` carries: internal ids, ISRC, ISWC, UPC, MusicBrainz recording id,
version type, mix name, edit name, explicit flag, duration, master-version flag,
release territory and release date. An ISRC identifies a recording; the
attestation — not the ISRC — is what establishes the right to promote it.

### Track intelligence

| Table | Purpose |
| --- | --- |
| `track_profile` | One versioned profile per recording |
| `track_profile_field` | One row per field: `value_json`, `confidence`, `source`, `extractor_version`, `generated_at`, `human_override`. A field with no row **is** UNKNOWN |

A human override is never silently replaced by a later derived value.

### Discovery

| Table | Purpose |
| --- | --- |
| `source_document` | One row per retrieval attempt, successful or refused. Stores a bounded excerpt (≤2000 chars), a content hash, the robots decision and the block reason. Never a full page copy |
| `evidence_packet` | The `EvidencePacket` contract: entity, field, extracted value, source URL and domain, source type, excerpt, confidence, retrieved/verified/stale timestamps, extractor version |
| `organization` | The entity that controls one or more outlets |
| `outlet` | Kind-discriminated (`PLAYLIST`, `CURATOR`, `RADIO`, `BLOG`, `PUBLICATION`, `PODCAST`, `DJ`, `DJ_POOL`, `CREATOR`) with `canonical_id` for merges |
| `submission_route` | Method, destination, login/CAPTCHA flags, cost model and amount, published instructions, supporting evidence, active flag |
| `entity_merge` | Winner, loser, rule, merged-at, undone-at — merges are reversible |

`follower_count` is always paired with `follower_count_source`; a count without
a source is not used by scoring.

### Contacts

| Table | Purpose |
| --- | --- |
| `professional_contact` | A person or role at an organization |
| `contact_method` | `value_ciphertext` (Fernet), `value_hash` (keyed HMAC), `value_preview` (redacted), category, role-based flag, `spotify_only` flag, independent-source count, verification and MX timestamps |
| `contact_evidence` | Join table: which evidence packets support this method |
| `suppression_record` | Keyed hash, `GLOBAL` or `TENANT` scope, reason, source. Never deleted |
| `relationship` | Per outlet/contact: last contact, next eligible date, accepted/declined/placement counts |
| `relationship_note` | Tenant-private notes |

A plaintext address exists only transiently inside `contacts.reveal`, which is
audited on every call.

### Campaign operations

| Table | Purpose |
| --- | --- |
| `campaign` | Mode, status, territories, channels, languages, budgets, daily send limit, rights attestation |
| `campaign_target` | Status from the 24-value CRM vocabulary, dedup key, consolidated related outlets, owner, tags, rejection reason. Unique on `(campaign, outlet)` |
| `opportunity_score` | Score, per-component values, generated reasons, version, override flag and reason |
| `risk_assessment` | Score, band, signals, version |
| `compliance_decision` | Decision plus the full `ComplianceDecisionRecord` JSON and policy version |
| `outreach_draft` | Recipient hash and preview, subject, body, links, attachments, language, translation flag, per-sentence fact basis, generator version, **payload hash** |
| `approval` | Bound to a payload hash, with invalidation timestamp and reason |
| `submission` | Method, provider message id, payload hash, status, cost, sent-at |
| `response` | Kind, sentiment, excerpt, received-at, who recorded it |
| `follow_up` | Sequence, due date, status |
| `placement` | **`evidence_id` is NOT NULL** — a placement cannot exist without evidence. Plus URL, program, added/verified/removed dates, position, confidence, cost |
| `analytics_snapshot` | Baseline and outcome measurements with an explicit `attribution` label |
| `human_action_task` | Provider, action, reason automation is unavailable, deadline, eligibility, copy-ready fields, assets, effort, cost, risk band, status |
| `sender_identity` | From address, domain, postal address, the full check set, ready/disabled status |
| `job_run` | Kind, payload, unique idempotency key, status, attempts, progress, error kind, result, cost, cancellation flag, next attempt time |
| `campaign_budget` | Searches, pages, model tokens, emails, spend, per-domain counts |

## Modelling choices

**One `outlet` table, not nine.** The brief lists Playlist, Channel, Station,
Blog, Publication, Podcast, DJProfile, DJPool and CreatorProfile separately.
In Phase One their attributes are identical, so they are one table discriminated
by `kind` with kind-specific extras in `profile_json`. Organization, route,
contact and contact method stay separate — those genuinely differ in shape.

**Deduplication keys the inbox, not the name.** `entities.dedup_key` returns
`contact:<keyed-hash>` when a contact method exists, otherwise
`domain:<registrable-domain>`. Resolution always collapses onto the earliest
target holding that key.

**Merge, split and undo.** `entities.merge` sets `canonical_id` on the loser and
re-parents its evidence; `undo_merge` reverses it. Fuzzy matches are only ever
returned by `suggest_merges` for a human to confirm.

**Forward compatibility.** Identity fields are deliberately flat and
standards-shaped (ISRC, ISWC, UPC, MusicBrainz ids, version type, territory,
release date) so a DDEX RIN import can map onto them without remapping the
database.

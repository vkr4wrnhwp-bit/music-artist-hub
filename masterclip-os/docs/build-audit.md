# Build audit

**First production-capable release. Audited 2026-08-17.**

Status vocabulary, used strictly:

| | |
|---|---|
| **REAL** | implemented, tested, and verified running |
| **DEV-LABELED** | functional and spec-correct, but not validated against the live third party |
| **PARTIAL** | legitimately started, incomplete, and described as such |
| **NOT BUILT** | absent, and never represented as working |

---

## The one thing to read first

**No live provider API call has ever been made from this build.** Every vendor
host — MuAPI, Google, fal, Runway, Luma, Replicate — was blocked by the
development environment's egress policy (403 at the CONNECT tunnel, an
organization policy denial). The adapters were therefore written against each
vendor's **own client library or machine-readable spec**, not from memory, and
are correct as far as those sources go. They have not touched the wire.

**Total live spend: $0.00.** Not "under the cap" — zero, because no billable call
was reachable. The `$2` cap was never approached.

Everything else below is genuinely exercised: the pipeline runs end to end
against the mock provider, which renders real MP4s with ffmpeg.

---

## Verification performed

| Check | Result |
|---|---|
| `pnpm typecheck` | **27/27 projects clean** |
| `pnpm lint` | **clean** — secret scan, shell-exec guard, SQL-interpolation guard, typecheck |
| `pnpm test` | **165 passed / 165**, 12 files |
| `pnpm test:e2e` | **10 passed / 10** (Playwright, Chromium, against the production web build) |
| `pnpm build` | **succeeds** — `dist/api.js`, `dist/worker.js`, `dist/masterclip.js`, `apps/web/dist` |
| bundled artifacts run | `node dist/masterclip.js doctor` → all required checks pass; `node dist/api.js` → serves `/api/health` |
| PostgreSQL parity | same migrations and same SQL verified against live PostgreSQL 16 |
| full pipeline | plan → authorize → submit → poll → download → verify → QC → derivatives → review → promote → finish → package, with real media |

130 source files, ~24,800 lines, 27 workspace packages, 14 test files.

---

## Feature audit

### Foundation

| Feature | Status | Files | Verification |
|---|---|---|---|
| Monorepo, 27 packages, strict TS | **REAL** | `pnpm-workspace.yaml`, `scripts/scaffold.mjs` | typecheck 27/27 |
| Micro-USD money | **REAL** | `packages/shared/src/money.ts` | 3 tests incl. a 500-clip exactness check |
| Error taxonomy + retry classification | **REAL** | `packages/shared/src/{errors,retry}.ts` | 5 tests |
| Secret redaction (by key *and* by value) | **REAL** | `packages/shared/src/redact.ts` | 3 tests |
| Structured JSON logging | **REAL** | `packages/shared/src/logger.ts` | used throughout; redaction tested |
| Database: SQLite + PostgreSQL, one SQL | **REAL** | `packages/database/` | 10 tests; verified on live PG 16 |
| Migrations, forward-only, transactional | **REAL** | `packages/database/src/migrations.ts` | idempotency + all-tables tests |
| Durable queue: leases, backoff+jitter, dead-letter, stalled recovery, dedupe, replay | **REAL** | `packages/queue/` | 13 tests |
| Local object storage + signed URLs | **REAL** | `packages/asset-storage/src/local.ts` | 6 tests incl. path-escape and expiry |
| S3 storage driver | **DEV-LABELED** | `packages/asset-storage/src/s3.ts` | SigV4 verified against AWS's published test vector; **never run against a live bucket** |
| Auth: scrypt, hashed sessions, project roles | **REAL** | `packages/auth/` | exercised by every API test + e2e |

### Canonical shot system

| Feature | Status | Files | Verification |
|---|---|---|---|
| Canonical shot schema (47 fields) | **REAL** | `packages/shot-schema/src/shot.ts` | 3 tests |
| JSON Schema generated from the same source | **REAL** | `packages/shot-schema/src/index.ts` | test asserts >40 properties |
| Semantic validation beyond the schema | **REAL** | `packages/shot-schema/src/validate.ts` | 6 tests |
| Derived requirements for routing | **REAL** | `packages/shot-schema/src/requirements.ts` | 5 tests |
| Locked-fact extraction | **REAL** | same | 1 test |
| Character + World bibles, versioned | **REAL** | `packages/shot-schema/src/bible.ts`, `packages/domain/src/bibles.ts` | pipeline test resolves both |
| CSV + JSON import/export, lossless round trip | **REAL** | `packages/shot-schema/src/io.ts` | 5 tests incl. RFC 4180 and prototype-pollution refusal |
| Shot versioning; renders bind to an immutable version | **REAL** | `packages/domain/src/projects.ts` | pipeline provenance test |

### Providers

| Feature | Status | Files | Verification |
|---|---|---|---|
| `VideoProvider` contract + capability matcher | **REAL** | `packages/provider-core/` | 17 tests |
| Contract test battery | **REAL** | `packages/provider-core/src/contract.ts` | runs green against mock incl. submit→poll→download |
| Mock provider rendering real, defective-on-purpose MP4s | **REAL** | `packages/provider-mock/` | 8 tests |
| MuAPI adapter | **DEV-LABELED** | `packages/provider-muapi/` | built from MuAPI's official CLI source; **no live call** |
| Google (Veo 3.1 family) adapter | **DEV-LABELED** | `packages/provider-google/` | built from Google's v1beta discovery doc + official SDK; **no live call** |
| fal adapter | **DEV-LABELED** | `packages/provider-fal/` | built from `fal-js`/`fal` official clients; **no live call** |
| Runway adapter | **DEV-LABELED** | `packages/provider-runway/` | built from the official OpenAPI spec + `sdk-node`; **no live call** |
| Luma adapter | **DEV-LABELED** | `packages/provider-luma/` | built from the official OpenAPI spec; **no live call** |
| Replicate adapter (schema-driven) | **DEV-LABELED** | `packages/provider-replicate/` | built from `replicate/client.py`; **no live call** |
| Self-hosted ComfyUI adapter | **DEV-LABELED** | `packages/provider-selfhosted/` | endpoints verified against ComfyUI's routes; **no live instance** |
| Webhook verification (HMAC, replay window, callback tokens) | **REAL** | `packages/provider-core/src/webhook.ts` | 3 tests |
| Webhook ingest with dedupe | **REAL** | `apps/api/src/routes/ops.ts` | unique-index dedupe; **not exercised by a real provider callback** |

### Render factory

| Feature | Status | Files | Verification |
|---|---|---|---|
| Batch matrix builder with pruning and stop-loss | **REAL** | `packages/domain/src/matrix.ts` | used by API + UI; priced before submit |
| Plan → quote → authorize → queue | **REAL** | `packages/runtime/src/render.ts` | pipeline tests |
| Submit → poll → download → verify | **REAL** | same | pipeline tests, real files |
| Idempotency (duplicate cells collapse) | **REAL** | `packages/domain/src/renders.ts` | dedicated test |
| Worker survives death mid-flight | **REAL** | `packages/queue` + worker | dedicated test |
| Provider health monitoring | **REAL** | `packages/provider-core/src/registry.ts` | doctor + UI |
| Four-level budgets, caps, attempt ceilings | **REAL** | `packages/cost-engine/src/budget.ts` | 15 tests |
| Batch-aware authorization | **REAL** | `packages/cost-engine/src/controller.ts` | dedicated test (found and fixed a real over-spend bug) |
| Global live-spend cap | **REAL** | same | dedicated test |
| Append-only cost ledger + variance | **REAL** | `packages/cost-engine/src/ledger.ts` | 3 tests |

### QC and review

| Feature | Status | Files | Verification |
|---|---|---|---|
| Technical QC (integrity, black, freeze, duration, bitrate, duplicates, decode) | **REAL** | `packages/qc-engine/src/technical.ts` | **10 tests against real defective media** |
| Frame extraction, contact sheets, proxies, thumbnails | **REAL** | `packages/media-tools/src/transform.ts` | pipeline test asserts all three derivatives |
| QC decision rules | **REAL** | `packages/qc-engine/src/decide.ts` | 7 tests |
| Visual QC via Claude vision | **DEV-LABELED** | `packages/qc-engine/src/visual.ts`, `packages/agents/src/vision.ts` | wired end to end and cost-metered; **never run against the live Anthropic API from this build** |
| Honest fallback with no vision model | **REAL** | `HeuristicVisionClient` | test asserts it reports 0 scores, 0.05 confidence, and routes to human review |
| Rejection taxonomy feeding routing | **REAL** | `packages/cost-engine/src/metrics.ts` | dedicated test |
| Review grid: sync playback, frame step, compare, rank | **REAL** | `apps/web/src/views/ReviewGrid.tsx` | e2e test |
| Master promotion requires a human approval | **REAL** | `packages/runtime/src/masters.ts` | test asserts promotion is refused without one |

### Routing and learning

| Feature | Status | Files | Verification |
|---|---|---|---|
| 8 routing profiles | **REAL** | `packages/model-router/src/profiles.ts` | consistency test over all 8 |
| Expected-approved-cost ranking | **REAL** | `packages/model-router/src/index.ts` | test proves the pricier, more-accepted model wins |
| Conservative priors + reported confidence | **REAL** | same | 3 tests |
| Acceptance history per model per shot category | **REAL** | `packages/cost-engine/src/metrics.ts` | dedicated test |
| Draft-vs-premium strategy simulator | **REAL** | `compareStrategies` + Cost Lab | 2 tests incl. the case where drafting *loses* |
| Prompt compiler with locked-fact verification | **REAL** | `packages/prompt-compiler/` | 14 tests incl. "fails loudly rather than truncating" |
| A/B testing | **PARTIAL** | matrix + acceptance stats | the mechanism exists (multi-model, multi-seed, multi-variation batches with per-model acceptance) but there is no dedicated experiment object with significance reporting |

### Finishing and delivery

| Feature | Status | Files | Verification |
|---|---|---|---|
| Delivery transcodes (H.264/H.265/ProRes/social) | **REAL** | `packages/media-tools/src/transform.ts` | pipeline test renders one |
| Reframing with a required explicit crop/pad choice | **REAL** | `packages/runtime/src/masters.ts` | refuses without `reframeMode` |
| Delivery package in the documented layout | **REAL** | same | pipeline test asserts files + manifest |
| Provenance sidecar + cost CSV | **REAL** | same | test asserts provider, prompt, shot version, cost, disclaimers |
| EDL + FCPXML | **REAL** | `packages/media-tools/src/edl.ts` | generated and shape-checked |
| Archive to tar | **DEV-LABELED** | `MasterService.archive` | shells out to `tar`; not covered by a test |
| Audio replace / normalize / extract | **REAL** | `packages/media-tools/src/transform.ts` | implemented; **not covered by a test** |

### Interfaces

| Feature | Status | Files | Verification |
|---|---|---|---|
| Web: dashboard, project, shot builder, queue, review, masters, cost lab, providers | **REAL** | `apps/web/src/views/` | 10 e2e tests + screenshots |
| REST API | **REAL** | `apps/api/` | exercised by e2e and pipeline tests |
| CLI, 20 commands, `--json`, exit codes | **REAL** | `apps/cli/src/main.ts` | `doctor`, `render submit`, `queue work`, `costs report` all run |
| `masterclip doctor` | **REAL** | same | verified against the production bundle |

### Claude agent layer

| Feature | Status | Files | Verification |
|---|---|---|---|
| Messages API client with prompt caching + exact cost metering | **REAL (code)** / **DEV-LABELED (live)** | `packages/agents/src/client.ts` | pricing table and cost maths are code-verified; **no live API call** |
| 7 producer agents with permissions | **REAL (definitions)** | `packages/agents/src/agents.ts` | system prompts, permission model, and forced-JSON schemas are defined and wired |
| Agent-run persistence + ledger integration | **REAL** | `agent_runs` table, `entryType: 'agent'` | schema present; QC path writes to the ledger |
| Agents driving the pipeline end to end | **PARTIAL** | — | the QC vision path is wired into the worker. The Creative Director, Shot Designer, Continuity Supervisor, and Cost Controller are defined with schemas and permissions but are **not yet invoked from an API route or the UI** |
| Claude Agent SDK (`@anthropic-ai/claude-agent-sdk`) subprocess orchestration | **NOT BUILT** | — | the Messages API was used directly instead: the worker needs a small, pinned bundle and per-call cost attribution into the same ledger as video spend, which the subprocess model does not give |

### Not built

| Feature | Why |
|---|---|
| Gemini Omni Flash adapter | A different API entirely (Interactions, stateful, token-metered). Needs its own adapter, not a flag. See `docs/model-capabilities.md` |
| Cloud-GPU benchmark harness | The self-hosted adapter refuses to quote without measured numbers, which is the honest posture; the harness that *produces* those numbers is not written |
| Scene-level and org-level budget **UI** | Both scopes are enforced in the cost engine; only the project scope has an editor |
| OpenTelemetry export | Logs carry trace-shaped fields (`trace_id`, `job_id`, `provider`) but there is no OTLP exporter |
| API rate limiting | Documented as a gap; deploy behind a rate-limiting proxy |
| Per-org encrypted provider credentials | `provider_credentials` table and `SECRETS_ENCRYPTION_KEY` exist; this release reads keys from the environment only |

---

## Bugs this build's own tests found and fixed

Worth recording, because they are the argument for the tests existing:

1. **Out-of-range durations were silently snapped.** The provider contract battery
   caught `validate()` accepting a 999-second request and coercing it to 10s.
   Snapping now only chooses between legal values.
2. **Freezes running to end-of-file were scored as zero frozen seconds.** ffmpeg
   emits `freeze_start` with no `freeze_end` in exactly the worst case — a still
   image padded to length. It now closes the interval at the clip duration.
3. **A batch could collectively blow a per-shot cap.** Every candidate was
   authorized against the same starting balance. Authorization now carries the
   batch's running commitment.
4. **Vertical video was silently low-resolution.** `frameSize` treated the
   resolution label as the height, making "1080p" vertical 608×1080 instead of
   1080×1920.
5. **Form labels were not associated with their controls.** Found by Playwright,
   fixed by rendering controls inside their `<label>` — an accessibility fix, not
   a test workaround.

---

## Exact commands to run it

```bash
cd masterclip-os
pnpm install
pnpm seed                    # demo project + credentials, printed to stdout
pnpm dev                     # web :4311 · api :4310 · worker
pnpm masterclip doctor       # verify ffmpeg, db, queue, storage, providers, spend
pnpm test && pnpm test:e2e && pnpm typecheck && pnpm lint && pnpm build
```

Requires Node ≥22.5 and ffmpeg/ffprobe on `PATH`.

## Credentials still needed

| For | Variable |
|---|---|
| MuAPI | `MUAPI_API_KEY` (a sandbox/test key first) |
| Google Veo | `GOOGLE_API_KEY` |
| fal | `FAL_KEY` |
| Runway / Luma / Replicate | `RUNWAY_API_KEY` / `LUMA_API_KEY` / `REPLICATE_API_TOKEN` |
| Visual QC + producer agents | `ANTHROPIC_API_KEY` |
| Provider callbacks | `PUBLIC_BASE_URL` + `WEBHOOK_SECRET` |
| Production deployment | `ASSET_SIGNING_SECRET`, `SESSION_SECRET` |

## Security warnings

1. No API rate limiting — put a rate-limiting proxy in front before exposing it.
2. No CSRF token; `sameSite=lax` is the only cross-site protection today.
3. The S3 driver has never touched a live bucket.
4. `ASSET_SIGNING_SECRET` **must** be set in production — the code refuses to
   start with the development fallback when `NODE_ENV=production`, but check it.

## Cost-saving recommendations

1. **Resolve the Google "per 1 count" unit against a real invoice before routing
   volume there.** It is an 8× ambiguity and it is risk #1.
2. Draft on Wan 2.2 turbo / LTX-2.3 Fast (≈$0.04–0.08/s), finish on Veo 3.1 Fast
   or Lite. Let the router's measured acceptance rates take over from the priors
   after ~20 reviewed candidates per model.
3. Keep visual QC triage on Haiku 4.5 and escalate only uncertain or HERO clips —
   roughly an order of magnitude per frame.
4. Set `PUBLIC_BASE_URL` + `WEBHOOK_SECRET` in any real deployment so providers
   call back instead of being polled.
5. Do not self-host until the measured cost per **accepted** second beats the API.

## Recommended next milestone

**Prove one live provider end to end.** Obtain a MuAPI sandbox key, run
`pnpm masterclip providers contract --provider muapi --submit`, then a single
live render with `MASTERCLIP_MODE=live LIVE_SPEND_CAP_USD=2`, and confirm the
charge the ledger records matches the provider's own reported cost. That single
run converts six adapters from DEV-LABELED toward REAL faster than any amount of
further building, and it is the only way to close risk #3.

# MX LAB Phase 1 — Implementation Report

Status: Phase 1 MVP delivered. The Definition-of-Done scenario (spec §30) was
executed end-to-end by an automated browser walkthrough — all 30 steps pass
with zero console errors, and 34 domain unit tests are green.

Everything below is stated exactly: nothing simulated is claimed as real
hardware integration.

## COMPLETED (real, working software)

- **Monorepo** — TypeScript workspaces (`packages/domain`, `apps/web`), strict
  typechecking, Vitest, Vite single-file offline build (~322 KB, runs from disk).
- **Domain engine layer** (pure, unit-tested):
  - Permission matrix for 11 roles; riders can never approve maps, edit ECU
    definitions, confirm transfers, or define envelopes.
  - Readiness gates — overall status is the worst unresolved critical gate;
    computed from confirmed records only.
  - Compatibility gates — exact key (manufacturer/model/model-year/ECU
    definition/firmware/engine build/fuel/exhaust/rev limit); blocking
    verdicts prevent transfers.
  - Map workflow — DRAFT → TUNER REVIEW → APPROVED FOR TEST → EXPORTED →
    TRANSFER CONFIRMED → TESTED → ACCEPTED/REJECTED/REVISED → TEAM BASELINE /
    RETIRED, role-gated, every transition audited.
  - Validated tuning envelopes — a draft exceeding the tuner-defined per-cell
    step (or lacking an envelope entirely) cannot be approved.
  - Append-only audit log (no update/delete API).
  - Provenance labels on records (MEASURED / RIDER REPORTED / TUNER ENTERED /
    … / AI INFERENCE / SIMULATION) rendered as badges; AI INFERENCE and
    SIMULATION are visually distinct.
  - Offline merge policy — conflicts preserve both versions and require human
    review; approvals/decisions are never silently overwritten (tested).
- **AI Race Engineer** — rule-based pipeline per spec §13.4: data-quality
  check → telemetry-window correlation (computed from the trace, not
  asserted) → ranked causes incl. non-map causes → non-map checks → proposed
  controlled A/B bounded by the envelope → confidence (capped ≤55 % on
  degraded data, never 100 %) → human decision required. It cannot mutate map
  state (tested).
- **Start Lab analytics** — rankings (fastest / most consistent / least
  wheelspin / RPM control / confidence / second phase) and an insight engine
  that recommends clutch/gate-prep work instead of map changes when variance
  analysis points there (tested on the seeded data).
- **A/B comparison** — lap stats, slip, consistency, thermal; explicit
  “telemetry supports/challenges rider preference”; engine-hours and
  engine-build comparability warnings.
- **Web application** — Team Garage, bike registration (Phase 0 inventory) and
  profile (identity/setup/trims/maintenance/map history/sessions/audit), ECU
  profile with verification ladder, map library + slots, map workspace
  (data-driven grids, diff heatmap, change summary, lineage, compatibility
  panel, CSV/JSON export), companion transfer worksheet with printable change
  sheet + second-person verification, 8-step session wizard (readiness-gated),
  session telemetry explorer with crosshair charts and channel quality,
  track view with section comparison, marker review (“What happened at
  Marker 3?”), rapid rider feedback (10 questions + 10 sliders, preferred vs
  previous preserved separately), AI recommendation review, Start Lab,
  hardware module, CNC part registry, reports (print + JSON/CSV + full team
  archive export/import), audit browser, Tutor mode, light/dark themes,
  offline-first (single file, localStorage).
- **Documentation** — architecture/data-flow/storage/sync, safety boundary,
  Vortex integration boundary, Phase 4 plan, hardware adapter spec, MX Node
  brief, competition-mode doc, CNC briefs (enclosure, YZ250F mount, YZ450F
  mount, pit dock, MARK button + sensor mounts, bench fixture), known
  unknowns requiring physical verification.

## SIMULATED (working software over explicitly fake data)

- **Telemetry** — deterministic seeded generator (10 Hz, 13 channels, laps,
  GPS position, marker-anomaly injection). No fake samples are stored as
  “measured”; traces regenerate from the seed. Every screen carries
  `SIMULATED DEMONSTRATION DATA — NOT A VALID TUNE`.
- **MX Node devices** — `SimulatedMxNodeAdapter` behind the read-only
  `TelemetryHardwareAdapter` interface; devices are labeled SIMULATED
  HARDWARE and self-report a SIMULATED transport.
- **Vortex ECU definitions** — two fictional definitions
  (`SIM-DEMO-250/450`, “exact model pending verification”) with per-capability
  verification statuses; the 10-slot layout is labeled a configurable example.
- **External transfer confirmations** — the companion workflow records that a
  person performed the change in the official Vortex software; in the demo
  these confirmations are marked `simulated: true`.
- **Authentication** — demo account picker; production auth is an adapter
  boundary documented in the architecture doc.
- **Seed dataset** — 2 bikes, 2 riders, 2 ECU definitions, 2 tracks, 3 engine
  builds, 4+ map revisions, 6 sessions, 12 start attempts, markers, feedback,
  one accepted A/B → team baseline, one rejected recommendation, one open
  degraded-data recommendation, one sensor failure, one compatibility
  failure, one maintenance warning.

## DISABLED (present by design, cannot run)

- **Direct ECU writing** — no write path exists. All write-adjacent UI renders
  `DIRECT ECU WRITE DISABLED — AUTHORIZED VORTEX INTEGRATION NOT YET VALIDATED`.
- **FutureFlashJob** — schema slot only, `status: 'DISABLED'`; execution
  always throws `AUTHORIZED DIRECT ECU INTEGRATION HAS NOT BEEN IMPLEMENTED`
  (unit-tested).
- **Competition live telemetry** — competition mode is local-logging only,
  with radio-disable confirmation and the sanctioning-body notice.

## FUTURE (documented, not built)

- Phase 2: passive read-only MX Node hardware (bench work per
  docs/hardware/, verification backlog in docs/testing/known-unknowns.md).
- Phase 3: companion workflow against real Vortex software (the software side
  ships now; the “SIMULATED” labels come off only after Phase 0 inventory of
  real units).
- Phase 4: authorized direct integration — gate checklist in
  docs/vortex/future-direct-integration-plan.md.
- Production backend (Firebase Auth, Firestore metadata, object-storage
  telemetry chunks) behind the existing `StoragePort`; background sync using
  the tested conflict policy.
- Voice notes (marker field reserved), video markers, 3D surface view,
  multi-org marketplace/consumer tiers, additional vehicle platforms via new
  ECU definitions + adapters.

## Known limitations

- localStorage persistence is per-browser; team sharing is via archive
  export/import until the backend lands.
- Charts downsample to ~700 points for display; full-resolution data is used
  for analysis.
- The AI cause-ranking is a transparent heuristic pipeline — appropriate for
  Phase 1; it should be re-validated against real telemetry in Phase 2 before
  any confidence figure is trusted.

---

# Expansion addendum — Race Intelligence & Team Operations

## COMPLETED (real logic, tested)
- Unified confidence model; TRACE Compare (WHAT CHANGED / WHAT HAPPENED /
  WHAT PROBABLY CAUSED IT with intended/uncontrolled marking); WHAT CHANGED
  auto-diff on every session vs its baseline with hold-constant violations;
  Test Planner (A/B/C, blind, start, section, durability) with
  controlled-variable detection and plan→session linking; Team Decision Log;
  race-day Timeline derived from the audit log; dynamic Between-Moto
  Checklists (real gates + component life + manual physical checks); Crew
  assignments; Live Pit Board; Morning Brief and Debrief composed from live
  records with human edit/approval; universal search; private map library
  tags + privacy levels; Digital Twin component registry with service
  history; reliability factors where a failed critical gate overrides the
  score. 25 new domain tests (59 total).

## SIMULATED
- All session data, telemetry-derived metrics, and hardware remain
  simulated and labeled. Remote tuner access grants (scoped, expiring,
  revocable, audited) are functional in-app but enforcement is local-demo
  until the backend ships.

## DEVELOPMENT-LABELED
- Setup Intelligence rankings and TRACE Predict (starting point only,
  requires human confirmation, citations + sample size always shown);
  Rider DNA (measured/preference/inference separated); Rider Coaching;
  Fatigue estimate (mandatory NOT-MEDICAL disclaimer); component life
  estimates; Ask TRACE / Knowledge answers (structured-record retrieval,
  keyword intents — composes only from real records, admits gaps).

## SHELL / FUTURE
- Marketplace: listing schema + screen with validation levels and
  disclaimers; nothing publishable or buyable.

## DISABLED
- Direct ECU write: unchanged, verbatim label everywhere.

## Known limitation
- Seeded narrative text (e.g. the historical A/B conclusion) is authored
  demo fiction, while Compare recomputes metrics live from the simulated
  traces — the two can disagree in places. Real data removes this class of
  mismatch; everything on screen is banner-labeled SIMULATED.

---

# Backend addendum — Production persistence (self-hosted sync server)

## COMPLETED (real, working software)
- **Sync engine** (`packages/domain/src/syncEngine.ts`): `fullMerge` unions
  every append-only collection by id (nothing is ever lost in a merge);
  protected records — map revisions, decision records, debriefs, TRACE
  Focus — are never overwritten silently. Divergent copies are preserved on
  both sides and surfaced as conflicts for a human to resolve.
  `redactDbForGrant` scopes a database to a remote-tuner grant: bikes in
  scope only, sessions only with `readTelemetry`, revisions only with
  `readMaps`; decisions, debriefs, plans, crew, audit, users, and focus are
  stripped entirely.
- **Sync server** (`apps/server`): dependency-free `node:http` service.
  Revisioned org snapshots + binary telemetry chunk files on disk behind a
  swappable `ServerStore` interface. HMAC-SHA256 bearer tokens with expiry
  (timing-safe compare). Optimistic concurrency: `PUT` with a stale
  `If-Match` returns **409 plus the server copy** — the *client* merges and
  retries; the server never merges silently. Grant tokens are minted only
  for grants that are active *in the stored database* (revocation kills
  tokens immediately) and are enforced server-side: reads are redacted,
  writes are 403, telemetry export requires `exportAllowed` plus bike scope.
- **Web client** (`apps/web/src/syncClient.ts` + More → Team Sync): sign in,
  pull → `fullMerge` → push with one 409 retry, conflict queue with
  Keep-local / Take-remote resolution (audited), optional debounced
  auto-sync after every change, telemetry archive upload, footer sync state,
  graceful offline degradation. The app never requires the server.
- **Tests**: 6 sync-engine tests + 9 server integration tests over real
  HTTP (76 total). Browser E2E: two isolated browser profiles synced
  through a live server — divergent TRACE Focus surfaced and resolved,
  union merge kept all sessions, telemetry chunk archived, offline grace.

## DEMO-LABELED (real code, placeholder trust)
- Identity issuance: `POST /auth/login` signs a token for any known org
  user with **no password** — labeled DEMO in the UI. Production swaps this
  one endpoint for a real IdP (OIDC); everything behind it (token format,
  role claims, grant enforcement) is already real.

## FUTURE (documented swap points, not built)
- Hosted storage adapters (document DB for snapshots, object store for
  telemetry chunks) behind `ServerStore`; TLS/reverse-proxy deployment
  guide; per-collection delta sync if snapshot sizes ever warrant it.

## Known limitations
- Snapshot-level sync: the whole org database travels on each sync
  (fine at this scale; measured well under a megabyte).
- Tokens are bearer tokens over HTTP in local demo use — deploy behind TLS.

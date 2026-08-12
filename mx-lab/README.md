# MX LAB — Phase 1

Vortex-first motocross mapping, telemetry, and AI race-engineering platform for
Yamaha YZ250F / YZ450F test programs. **Phase 1 is a simulation-only software
intelligence platform: it never writes to an ECU, and every simulated element
is labeled as such.**

Banner shown on every screen: `SIMULATED DEMONSTRATION DATA — NOT A VALID TUNE`

## Run it

```bash
cd mx-lab
npm install
npm run dev        # dev server
npm test           # 34 domain unit tests (vitest)
npm run typecheck  # strict TS across both packages
npm run build      # single-file offline build → apps/web/dist/index.html
```

The production build is **one self-contained HTML file** — open it from disk,
no server or connection needed. All data persists in the browser
(localStorage); use Reports → “Export full archive” to move a team database
between machines.

## Layout

```
packages/domain    typed models + pure engines (permissions, readiness,
                   compatibility, map workflow, audit, provenance, simulator,
                   AI race engineer, Start Lab, sync policy, hardware adapters)
apps/web           React PWA (Vite) — all modules, offline-first
docs/architecture  system + data-flow + storage + sync strategy
docs/safety        safety boundary (passive-only, AI-never list)
docs/vortex        integration boundary + Phase 4 direct-integration plan
docs/hardware      adapter spec, MX Node brief, competition-mode doc
docs/cnc           enclosure, YZ250F/YZ450F mounts, pit dock, MARK button,
                   sensor mounts, bench fixture briefs
docs/testing       known unknowns requiring physical verification
docs/IMPLEMENTATION-REPORT.md   COMPLETED / SIMULATED / DISABLED / FUTURE
```

## Demo accounts

Sign-in is simulated (production maps to real auth behind the same permission
matrix). Twelve fictional users cover all eleven roles — tuner Jules Ortiz,
mechanic Casey Trần, and rider Blake Harmon walk the full workflow.

## Safety invariants (enforced in code and tests)

- No ECU write path exists anywhere in the codebase; the Phase 4 schema slot
  is `status: 'DISABLED'` and throws
  `AUTHORIZED DIRECT ECU INTEGRATION HAS NOT BEEN IMPLEMENTED` if executed.
- All ECU-write controls render
  `DIRECT ECU WRITE DISABLED — AUTHORIZED VORTEX INTEGRATION NOT YET VALIDATED`.
- The AI Race Engineer creates recommendations only in
  `AWAITING_TUNER_REVIEW`; only humans with the right role can decide them,
  confidence is capped under degraded data quality, and readiness gates can
  never be satisfied by inference.
- A map revision is authored against an exact compatibility key; blocking
  mismatches (ECU, firmware, model year, engine build, fuel) prevent transfer
  confirmation.
- Audit history is append-only — no update or delete API exists.

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
npm test           # 76 tests: domain units + sync engine + server integration
npm run typecheck  # strict TS across all three packages
npm run build      # single-file offline build → apps/web/dist/index.html
npm run server     # optional self-hosted team sync server (default :8787)
```

The production build is **one self-contained HTML file** — open it from disk,
no server or connection needed. All data persists in the browser
(localStorage); use Reports → “Export full archive” to move a team database
between machines.

## Team sync server (optional, self-hosted)

The app is local-first and never requires a connection. `npm run server`
starts the persistence backend: a dependency-free Node server that stores
each org's database as a revisioned snapshot plus binary telemetry chunks on
disk, behind HMAC-signed bearer tokens. Devices connect from **More → Team
Sync**; sync is pull → merge → push with optimistic concurrency, and the
server never merges silently — divergent approvals, decisions, debriefs, and
TRACE Focus land in an on-screen conflict queue for a person to resolve.
Remote-tuner grant tokens are enforced server-side: the server redacts the
database down to the grant's bike scope and permissions before it ever
leaves the machine. Managers mint access tokens from the Remote Tuner
Access screen; external tuners consume them at `#/grantview` — a read-only
view with no team account, where export needs the grant's permission and
revocation kills tokens instantly. Identity issuance is real password auth
(scrypt, timing-safe compare) with a **first-sign-in-sets-password**
bootstrap; once the org database is on the server, roles come from it,
never from the client. Deploy behind TLS; an IdP for SSO swaps in at
`POST /auth/login`. Storage sits behind a swappable `ServerStore` interface
(file-backed today; a hosted document/blob store drops in without touching
routes).

## Layout

```
packages/domain    typed models + pure engines (permissions, readiness,
                   compatibility, map workflow, audit, provenance, simulator,
                   AI race engineer, Start Lab, sync policy, hardware adapters)
apps/web           React PWA (Vite) — all modules, offline-first
apps/server        self-hosted sync server (auth, snapshots, telemetry chunks,
                   grant-scoped redaction) — zero runtime dependencies
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

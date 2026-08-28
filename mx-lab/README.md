# MX LAB — Phase 1

Vortex-first motocross mapping, telemetry, and AI race-engineering platform for
Yamaha YZ250F / YZ450F test programs. **Phase 1 is a simulation-only software
intelligence platform: it never writes to an ECU, and every simulated element
is labeled as such.**

Banner shown on every screen: `SIMULATED DEMONSTRATION DATA — NOT A VALID TUNE`

## Map editing

Fuel and ignition tables are edited in **Tune → a revision**. The grid is
driven by the bike's verified ECU definition — its own axis breakpoints, its
own allowed range and precision — and cells are only writable while the
revision is a `DRAFT` and your role holds `map.editDraft`.

- **Select** — click, drag to paint a region, shift for a rectangle from the
  anchor, ctrl/⌘-click to add a single cell. Arrow keys move; `+` and `−`
  nudge the selection; `0` zeroes it; ctrl/⌘-Z and ctrl/⌘-shift-Z undo and redo.
- **Shape** — step buttons, set, % change, zero, **smooth** (each selected cell
  becomes the mean of its 3×3 neighbourhood) and **interpolate** (fill a region
  bilinearly from its four corners).
- **Condition presets** — starting shapes for hardpack, sand, mud, altitude and
  cold air. They are resampled onto *this* ECU definition's axes by breakpoint
  value, not by index, so "richer just off the bottom" lands at the throttle
  position it names on any bike. They only apply to `offset` tables, and they
  are labelled as simulated starting points every time they are offered.
- **Air density** — elevation, temperature, humidity and altimeter setting give
  density altitude, density ratio and a suggested trim. Suggested, never
  applied: like everything advisory here it is offered next to a plug reading,
  not written into a table.

This is where the **Holeshot Tuner** and **Trackside** worksheets went. They
were two separate implementations of the same RPM × throttle grid, drifting
apart from each other and from this one, and neither had revisions, approval
gates or real ECU axes. The editing tools came here; the worksheets are gone.
The operations themselves are pure functions in
`packages/domain/src/mapEditing.ts`, `air.ts` and `mapPresets.ts`, tested
independently of the screen.

## Run it

```bash
cd mx-lab
npm install
npm run dev        # dev server
npm test           # 122 tests: domain units + map editing + sync engine + server integration
npm run typecheck  # strict TS across all three packages
npm run build      # single-file offline build → apps/web/dist/index.html
npm run server     # optional self-hosted team sync server (default :8787)
npm run demo       # one command: build + app on :8080 + sync server on :8787
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
The Live Pit Board goes genuinely live when connected: it polls a
lightweight revision probe and pulls within seconds of any teammate's sync.
Hosting: the repo's `render.yaml` deploys app + server as one Render web
service with automatic TLS — see `docs/architecture/deployment.md`.
Remote-tuner grant tokens are enforced server-side: the server redacts the
database down to the grant's bike scope and permissions before it ever
leaves the machine. Managers mint access tokens from the Remote Tuner
Access screen; external tuners consume them at `#/grantview` — a read-only
view with no team account, where export needs the grant's permission and
revocation kills tokens instantly. Identity issuance is real password auth
(scrypt, timing-safe compare): the very first account bootstraps the org,
and from the first sync onward new accounts need a **one-time invite code**
minted by an admin (More → Team & roles), roles come from the synced
database (never from the client), and passwords are changed self-service.
Deploy behind TLS — see `docs/architecture/deployment.md` for the reverse
proxy, systemd, and backup guide. An IdP for SSO swaps in at
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

## Signing in

The front door depends on where TRACE is running:

- **Hosted** (a real URL, with the sync server behind it): a real sign-in —
  pick who you are, enter your password, and the app claims-or-joins the
  organization and pulls the team database in one step. The first sign-in sets
  that account's password and claims the org; every account after it needs a
  one-time invite code from an admin. Visitors without an account can press
  **Explore the demo**, which runs the seeded simulation in their browser and
  never reaches the server — the app says DEMO MODE while it is on.
- **Offline** (the single-file build opened from disk, or local dev): there is
  no server to ask, so the twelve seeded users are pickable directly.

Twelve fictional users cover all eleven roles — tuner Jules Ortiz, mechanic
Casey Trần, and rider Blake Harmon walk the full workflow.

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

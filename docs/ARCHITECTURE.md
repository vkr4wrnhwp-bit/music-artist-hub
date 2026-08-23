# CANVAS — Architecture

CANVAS is the beginning of an AI manufacturing operating system. Phase 1's wedge
is 3-axis CNC milling in a real job shop, but every structural decision below is
made so that CNC is *one process among many* rather than the thing the system is
built around.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | Next.js 16 (App Router, Turbopack) | Server components keep manufacturing data and AI keys server-side by default |
| Language | TypeScript, strict | The domain is full of numbers that must not be confused with each other |
| UI | React 19 + Tailwind v4 | Design tokens live in CSS custom properties (`src/app/globals.css`) |
| 3D | Three.js via React Three Fiber + drei | Viewport is a client island; nothing else ships to the browser |
| ORM | Prisma 7 with driver adapters | Adapter swap moves dev SQLite → production PostgreSQL with no schema change |
| DB (dev) | SQLite | The app runs with zero external services |
| DB (prod) | PostgreSQL | Same schema; see "Database" below |
| Auth | Cookie sessions, bcrypt | No third-party identity dependency in the core |
| Storage | Driver interface (`src/lib/storage.ts`) | Local FS in dev, S3/GCS in production behind the same three methods |

## Layout

```
src/
  app/
    (auth)/            sign-in, sign-up
    (app)/             the application shell — every route reads the session
    api/               intake, assets, measurements, copilot
  components/          design system, nav, viewport, workspace, reverse-engineering
  lib/
    domain/            the vocabulary: part intent, features, shop resources
    engines/           the reasoning: workholding, nominal, CAM, readiness, cost,
                       process advisor, network fingerprint
    ai/                provider abstraction — deterministic and Anthropic
    manufacturing/     the turning side: geometry, operations, analyses,
                       readiness, post, cost, sim, soft jaws, NC parse/optimize,
                       package.ts (the lathe's own composition point)
    nc/                uploaded-program analysis: parse, time, load, protect,
                       audit gates, feed-only optimization
    step/              STEP import: Part 21 parser + feature recognizer
    scan/              STL scan import: mesh parser + honest inspection
    guide/             the guided workflows: pure engine + authored flows
    sim/  metrology/  export/   stock-removal replay, instrument vocabulary,
                       gated NC export minting
    package.ts         composition point: assembles the manufacturing package
    provenance.ts      where every value's source and confidence lives
    auth.ts db.ts audit.ts data.ts storage.ts
prisma/                schema, migrations, demo seed
```

## The three layers, and why they are separate

**Domain** (`lib/domain`) is vocabulary and shape. It has no I/O and no
opinions — a `Feature` is a `Feature` whether it came from a drawing, a
measurement session or a model.

**Engines** (`lib/engines`) are pure functions over domain objects. They are
deterministic, individually testable, and none of them touch the database or
the network. This is deliberate: the workholding assessment, the CAM engine and
the cost model are the parts of CANVAS a shop's money and safety depend on, and
they must be reviewable in isolation.

**Application** (`app/`, `lib/package.ts`, `lib/data.ts`) loads records, calls
engines, and renders. `buildPackage()` is the single composition point where
geometry, shop resources and every engine meet — deliberately one function,
because readiness depends on workholding, which depends on the roughing
operation, whose cycle time drives cost. Computing those in separate places is
how a UI ends up showing a cost that does not match the program beside it.

## Data flow: description → NC

```
prompt ──> AiProvider.interpretPartPrompt ──> PartIntentExtraction (zod-validated)
       ──> PartIntent (every field Provenanced, AI_INFERENCE, unconfirmed)
       ──> human confirms fields + answers the Responsibility interview
       ──> Features (parametric, only after a human accepts proposals)
       ──> Setups + Operations (validated against machine + crib)
       ──> DETERMINISTIC toolpath engine  ← no model involvement, ever
       ──> machine constraint validation
       ──> workholding validation
       ──> simulation (visualisation only in Phase 1)
       ──> post processor (modular, development-only)
       ──> NC verification (linter)
       ──> pre-flight gate + human approval
       ──> export
```

Every arrow after "Features" is arithmetic. See `docs/CAM_ENGINE.md`.

## Database

The schema (`prisma/schema.prisma`) is written to move to PostgreSQL without
restructuring:

- No SQLite-specific column types.
- Enumerated values are stored as strings and validated in `lib/domain`, which
  keeps one source of truth for the vocabulary instead of splitting it between
  a Prisma enum and a TypeScript union.
- JSON documents are used only where shredding into columns would destroy
  meaning — the Part Intent Model in particular, where every field carries a
  `{value, source, confidence, confirmedByUser}` tuple that columns would lose.

To move to Postgres: change `provider` in the datasource block, swap
`PrismaBetterSqlite3` for `PrismaPg` in `src/lib/db.ts`, point `DATABASE_URL`
at the cluster, re-run migrations. Nothing else changes.

### Multi-tenancy

Every manufacturing table is organisation-scoped. `lib/data.ts` takes
`organizationId` as the first argument of every accessor, and that id always
comes from the session — never from a request parameter. A crafted part id
returns 404, indistinguishable from "does not exist".

## Extension seams

These exist so the hard parts can be replaced without a rewrite:

| Seam | Replace with |
|---|---|
| `generateToolpath(request, feature, ctx, stock)` | A production CAM kernel |
| `AiProvider` | Any model vendor; add a class, no callers change |
| `StorageDriver` | S3, GCS, Azure Blob |
| `PostDefinition.emit` | A validated per-controller post |
| `evaluateReadiness` gates | Additional gates; the aggregate is worst-of, not average |
| `buildFingerprint` | Richer matching, same privacy contract |

## Environment

```
DATABASE_URL          file:./prisma/dev.db  (dev)
CANVAS_AI_PROVIDER    deterministic | anthropic
ANTHROPIC_API_KEY     server-side only, never exposed to the client
CANVAS_AI_MODEL       optional model override
CANVAS_STORAGE_DIR    optional local storage root
```

`src/lib/ai/anthropic.ts`, `db.ts`, `auth.ts`, `audit.ts` and `storage.ts` all
import `server-only`, so a client-side import is a build error rather than a
credential leak.

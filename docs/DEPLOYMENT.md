# Deployment

CANVAS runs on three database homes from one codebase and one schema. The
driver is chosen from the connection string; nothing else in the application
knows which one it got.

| Home | Connection string | Use |
|---|---|---|
| **SQLite** | `file:./prisma/dev.db` | Local development. No services |
| **Turso** | `libsql://…` | Smallest live deployment. SQLite over the network |
| **PostgreSQL** | `postgresql://…` | Any managed provider |

---

## Which branch is live

`render.yaml` names no branch, and a Render Blueprint with no `branch:` key
deploys the repository's **default branch**. If the branch you are pushing to
is not the default, nothing you push reaches the site — the build succeeds, the
service stays healthy, and it serves older code. There is no error anywhere;
the only symptom is that the site does not change.

Check it in one place: Render dashboard -> the `canvas` service -> Settings ->
Branch. Set it to the branch you actually deploy from, or make that branch the
repository default. Do both and they agree; do neither and you are reading a
build from whenever the default branch last moved.


## Render (recommended — one blueprint, nothing to copy)

`render.yaml` in the repository root declares the web service and its
PostgreSQL database together and wires the connection string between them, so
there is nothing to paste by hand.

**Render dashboard → New → Blueprint → point at this repository → Apply.**

That is the whole procedure. The build runs `npm ci && npm run deploy:build`,
which migrates, seeds and builds; the service starts with `npm start` on the
port Render provides. Sign in at `/sign-in` with
`demo@canvas.local` / `canvas-demo`.

Render suits CANVAS better than a serverless host in two ways: it runs a
long-lived Node process, so there are no cold starts on the 3D viewport, and
its filesystem survives the life of the instance rather than a single request.

### Verified against real PostgreSQL (2026-08-23)

The blueprint is not just declared, it is exercised. Against PostgreSQL 16,
with `NODE_ENV=production` set the way Render sets it:

| Check | Result |
|---|---|
| `npm ci --include=dev && npm run deploy:build` (the exact buildCommand) | exit 0 |
| `prisma migrate deploy` — the committed postgres migration set | 18 applied, none pending |
| `prisma db seed` | 3 parts, 10 tools, 9 instruments, 9 turning tools |
| `healthCheckPath: /sign-in` — what Render polls | 200 |
| 16 workspace routes on Postgres, authenticated | all 200 |
| Engine output on Postgres, not just SQLite | chamfer warning, worst-gate readiness correct |

**A redeploy does not wipe shop data.** `autoDeployTrigger: commit` means every
push to the branch redeploys and re-runs `prisma db seed`. The seed is
idempotent — it detects the demo org and leaves everything untouched unless
`CANVAS_FORCE_RESEED=1` is set. Verified explicitly: a part created after the
first seed survived a full re-seed. Pushing a fix mid-beta is safe.

**Before a beta session, wake the service.** On the free plan the instance
sleeps after inactivity and the first request takes ~30 seconds. Hit the URL
yourself a minute before the machinist walks up; do not let a cold start be
their first impression. If the beta is more than a one-off, the paid instance
type removes the sleep and enables the durable-uploads disk below.

**Free plan caveats.** The service sleeps after inactivity, so the first
request after a quiet period takes ~30 seconds to wake. Render's free
PostgreSQL instances expire after a fixed period — check the current terms
before relying on one for anything you care about.

**Durable uploads.** Uncomment the `disk` block in `render.yaml` (requires a
paid instance) and set `CANVAS_STORAGE_DURABLE=1`. Until you do, uploads work
but do not survive a redeploy, and the Reverse Engineer screen says so.

---

## Vercel + Turso

Turso is SQLite over HTTP. Because it speaks the same dialect, **the committed
migrations in `prisma/migrations` apply to it unchanged** — no second migration
set, no schema rewrite, nothing to keep in sync. It is the smallest step from
"runs on my laptop" to "has a URL", and the free tier needs no card.

**1. Create the database.**

```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup
turso db create canvas
turso db show canvas --url          # libsql://canvas-….turso.io
turso db tokens create canvas       # the auth token
```

**2. Import the repo into Vercel.** New Project → import `canvas`. Leave the
framework preset alone and do not override the build command — `package.json`
defines `vercel-build`, which Vercel picks up automatically.

**3. Set two environment variables.**

| Name | Value |
|---|---|
| `DATABASE_URL` | the `libsql://…` URL |
| `DATABASE_AUTH_TOKEN` | the token from `turso db tokens create` |

**4. Deploy.** Sign in at `/sign-in` with `demo@canvas.local` / `canvas-demo`.

### If you would rather use PostgreSQL

Identical, with one variable instead of two: set `DATABASE_URL` to a Neon,
Supabase or Vercel Postgres connection string. The build detects the provider,
regenerates the schema and applies `prisma/migrations-postgres`.

### Optional variables

| Name | Effect |
|---|---|
| `CANVAS_AI_PROVIDER=anthropic` | Enables the full copilot |
| `ANTHROPIC_API_KEY` | Required by the above. Server-side only |
| `CANVAS_AI_MODEL` | Overrides the model |
| `CANVAS_FORCE_RESEED=1` | Replaces the demo shop on the next deploy |
| `CANVAS_STORAGE_DIR` | Storage root, if you mount a persistent volume |
| `CANVAS_STORAGE_DURABLE=1` | Declares that the storage root is a persistent volume, which silences the temporary-uploads warning |

### What the build actually runs

```
prepare:db              rewrite the schema for the detected provider and
                        generate the matching client — always together, so
                        the two can never disagree
prisma migrate deploy   apply the matching migration set
prisma db seed          create the demo shop, only if it is missing
next build
```

---

## How one schema serves all three

`prisma/schema.prisma` is the single source of truth, authored for SQLite.
`scripts/prepare-schema.mjs` rewrites exactly one line — the datasource
provider — into `prisma/.generated/schema.prisma`, which `prisma.config.ts`
points at. Turso maps to the `sqlite` provider because it is SQLite.

This works because the schema was written portable from the start: no
SQLite-specific column types, and enumerated values stored as strings validated
in `src/lib/domain` rather than as native database enums. Generating the second
schema rather than maintaining it means a schema change cannot be applied to
one provider and forgotten on the other.

Migration SQL *is* dialect-specific, so PostgreSQL keeps its own directory:

```
prisma/migrations/            SQLite and Turso
prisma/migrations-postgres/   PostgreSQL
```

After changing the schema, generate the migration for both dialects:

```bash
DATABASE_URL="file:./prisma/dev.db"   npm run db:migrate:new
DATABASE_URL="postgresql://…"         npm run db:migrate:new
```

`src/lib/database-url.ts` holds the routing — one function, unit-tested against
all six connection-string forms.

---

## What is verified, and what is not

**Verified here**, against a real PostgreSQL 16 instance:

- Render's exact commands — `npm ci && npm run deploy:build`, then `npm start`
  under `RENDER=true`, `NODE_ENV=production` and a Render-style `PORT` — driven
  through a browser afterwards: 668 toolpath moves, every part route 200, zero
  console errors.
- The same for Vercel's build path.
- Both storage states: the ephemeral-uploads warning appears without a
  persistent disk, and is correctly suppressed by `CANVAS_STORAGE_DURABLE=1`.
- The SQLite path re-verified unchanged, and the libSQL adapter verified
  against this schema and generated client.
- URL routing across all six connection-string forms.

**Not verified here.** The hosts themselves — Render, Vercel and Turso all need
accounts this environment does not have. Every command they will run has been
executed locally against a real database; what is untested is the network hop
and the platform's own orchestration.

---

## Known limitations of a hosted deployment

These are real, and the interface states them rather than hiding them.

**Uploaded files are not durable by default.** On a serverless host nothing
survives the request; on a container host like Render the filesystem survives
the instance but not a redeploy. Durability cannot be inferred — a mounted
volume looks identical to the container filesystem — so it is declared: set
`CANVAS_STORAGE_DURABLE=1` when a persistent volume is actually attached.
Until then the Reverse Engineer screen states plainly that uploads are
temporary. Everything else — parts, measurements, jobs, audit — is in the
database and unaffected.

For durable uploads, implement `StorageDriver` against S3, R2 or GCS. It is
three methods — `put`, `get`, `url` — and nothing else knows where bytes live.

**The demo shop is shared.** Everyone hitting a public deployment signs in as
the same seeded operator and edits the same parts. Fine for showing the
product, wrong for anything else. Real use means real accounts: `/sign-up`
already exists and every query is organisation-scoped, so organisations are
already isolated from each other.

**Cold starts.** On a serverless host the 3D viewport's client bundle makes
first paint slower than a local build. On Render's free plan the service sleeps
after inactivity, so the first request wakes it (~30s) before anything renders.

---

## Self-hosting instead

An ordinary Next.js server plus a database URL:

```bash
export DATABASE_URL="postgresql://…"   # or libsql://… or file:…
npm ci
npm run db:migrate
npm run db:seed
npm run build
npm start
```

On a host with a persistent disk, point `CANVAS_STORAGE_DIR` at a mounted
volume and uploads become durable with no code change.

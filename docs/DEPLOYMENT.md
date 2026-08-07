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

## The easiest live deployment: Vercel + Turso

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

### What the build actually runs

```
prepare:schema          rewrite the schema for the detected provider
prisma generate         generate the client for that provider
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

**Verified here.** The PostgreSQL path end to end against a real PostgreSQL 16
instance: clean install, `vercel-build`, migrate, seed, production build, then
driven through a browser — same 668 toolpath moves and zero console errors as
the SQLite build. The SQLite path re-verified unchanged. The libSQL adapter
verified against this schema and the generated client. The URL routing tested
across all six forms.

**Not verified here.** Turso over the network, and Vercel itself — both need
accounts this environment does not have. The adapter, the dialect and the
routing are all confirmed; what is untested is the network hop.

---

## Known limitations of a serverless deployment

These are real, and the interface states them rather than hiding them.

**Uploaded files do not persist.** A serverless filesystem is read-only apart
from a per-instance temp directory that is cleared between invocations.
`src/lib/storage.ts` detects this, writes to `/tmp`, and exports
`storageIsEphemeral`; the Reverse Engineer screen shows a warning when it is
set. Photographs uploaded during a session work, and will not be there
tomorrow. Everything else — parts, measurements, jobs, audit — is in the
database and unaffected.

For durable uploads, implement `StorageDriver` against S3, R2 or GCS. It is
three methods — `put`, `get`, `url` — and nothing else knows where bytes live.

**The demo shop is shared.** Everyone hitting a public deployment signs in as
the same seeded operator and edits the same parts. Fine for showing the
product, wrong for anything else. Real use means real accounts: `/sign-up`
already exists and every query is organisation-scoped, so organisations are
already isolated from each other.

**Cold starts.** The 3D viewport is a client bundle, so first paint on a cold
function is slower than a local build.

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

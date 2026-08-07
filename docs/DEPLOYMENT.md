# Deployment

CANVAS runs on SQLite locally and PostgreSQL in a deployment, from the same
codebase and the same schema. Nothing about the application changes between
them — only the driver adapter.

Both paths are verified: the application was built, migrated, seeded and driven
through a browser against a real PostgreSQL 16 instance, producing the same 668
toolpath moves and the same zero console errors as the SQLite build.

---

## Vercel + Neon (about five minutes)

**1. Create a Postgres database.** Neon, Supabase, Vercel Postgres or any
managed Postgres works. Copy the connection string — it looks like
`postgresql://user:password@host/dbname?sslmode=require`.

**2. Import the repository into Vercel.** New Project → import your `canvas`
repo. Leave the framework preset on Next.js; do not override the build command,
because `package.json` already defines `vercel-build`, which Vercel prefers
automatically.

**3. Set one environment variable.**

| Name | Value |
|---|---|
| `DATABASE_URL` | your Postgres connection string |

That is the only required variable. The provider is detected from the string —
there is nothing else to configure.

**4. Deploy.** The build runs:

```
prepare:schema     rewrite the schema for postgresql
prisma generate    generate the client for that provider
prisma migrate deploy   apply prisma/migrations-postgres
prisma db seed     create the demo shop, only if it is missing
next build
```

Sign in at `/sign-in` with `demo@canvas.local` / `canvas-demo`.

### Optional variables

| Name | Effect |
|---|---|
| `CANVAS_AI_PROVIDER=anthropic` | Enables the full copilot |
| `ANTHROPIC_API_KEY` | Required by the above. Server-side only |
| `CANVAS_AI_MODEL` | Overrides the model |
| `CANVAS_FORCE_RESEED=1` | Replaces the demo shop on the next deploy |
| `CANVAS_STORAGE_DIR` | Storage root, if you mount a persistent volume |

---

## How the two providers share one schema

`prisma/schema.prisma` is the single source of truth, authored for SQLite.
`scripts/prepare-schema.mjs` rewrites exactly one line — the datasource
provider — into `prisma/.generated/schema.prisma`, which `prisma.config.ts`
points at.

This works because the schema was deliberately written to be portable: no
SQLite-specific column types, and enumerated values stored as strings validated
in `src/lib/domain` rather than as native database enums. Generating the second
schema rather than maintaining it means a schema change cannot be applied to
one provider and forgotten on the other.

Migration SQL *is* dialect-specific, so each provider keeps its own directory:

```
prisma/migrations/            SQLite
prisma/migrations-postgres/   PostgreSQL
```

When you change the schema, generate the migration for both:

```bash
DATABASE_URL="file:./prisma/dev.db"        npm run db:migrate:new
DATABASE_URL="postgresql://…"              npm run db:migrate:new
```

---

## Known limitations of a serverless deployment

These are real and the interface states them rather than hiding them.

**Uploaded files do not persist.** A serverless filesystem is read-only except
for the OS temp directory, which is per-instance and cleared between
invocations. `src/lib/storage.ts` detects this, writes to `/tmp`, and exports
`storageIsEphemeral` so the UI can say so. Photographs uploaded during a
session work; they will not be there tomorrow.

For durable uploads, implement `StorageDriver` against S3, R2 or GCS. It is
three methods — `put`, `get`, `url` — and nothing else in the application knows
where bytes live.

**The demo shop is shared.** Everyone hitting a public deployment signs in as
the same seeded operator and edits the same parts. That is fine for showing the
product and wrong for anything else. Real use means real accounts — sign-up
already exists at `/sign-up`, and every query is organisation-scoped, so
separate organisations are already isolated from each other.

**Cold starts.** The 3D viewport and its dependencies are a client bundle, so
first paint on a cold function is slower than the local build.

---

## Self-hosting instead

The application is an ordinary Next.js server with a Postgres connection, so
anything that runs Node 20+ will host it:

```bash
export DATABASE_URL="postgresql://…"
npm ci
npm run db:migrate
npm run db:seed
npm run build
npm start
```

On a host with a persistent disk, set `CANVAS_STORAGE_DIR` to a mounted volume
and uploads become durable with no code change.

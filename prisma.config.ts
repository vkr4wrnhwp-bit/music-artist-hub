import path from "node:path";
import { existsSync } from "node:fs";
import { defineConfig } from "prisma/config";

/**
 * Prisma 7 moves the datasource URL out of the schema file.
 *
 * The schema itself is generated per provider by `scripts/prepare-schema.mjs`
 * — SQLite for local development, PostgreSQL for a deployment — from the one
 * canonical `prisma/schema.prisma`. If the generated file has not been
 * produced yet (a bare `npx prisma …` before install), fall back to the
 * source schema so the CLI still has something valid to read.
 */

const generated = path.join("prisma", ".generated", "schema.prisma");
const schema = existsSync(generated) ? generated : path.join("prisma", "schema.prisma");

const url = process.env.DATABASE_URL ?? "file:./prisma/dev.db";
// Turso reuses the SQLite migration set — same dialect, so the committed
// migrations apply to it unchanged.
const isPostgres = url.startsWith("postgres://") || url.startsWith("postgresql://");

export default defineConfig({
  schema,
  migrations: {
    // Migration SQL is dialect-specific, so each provider keeps its own set.
    path: path.join("prisma", isPostgres ? "migrations-postgres" : "migrations"),
    seed: "tsx prisma/seed.ts",
  },
  datasource: { url },
});

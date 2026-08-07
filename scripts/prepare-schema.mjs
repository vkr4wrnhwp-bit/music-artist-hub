#!/usr/bin/env node
/**
 * Emits the Prisma schema for the target database provider.
 *
 * `prisma/schema.prisma` is the single source of truth and is authored for
 * SQLite, which is what local development uses. Production runs PostgreSQL.
 * The two schemas differ by exactly one line — the datasource provider —
 * because the schema was deliberately written without SQLite-specific column
 * types and stores enumerated values as strings validated in `lib/domain`.
 *
 * Rather than maintain two files that will drift, this rewrites that one line
 * into `prisma/.generated/schema.prisma`, which `prisma.config.ts` points at.
 * Keeping it generated means a schema change can never be applied to one
 * provider and forgotten on the other.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const PROVIDERS = { sqlite: "sqlite", postgresql: "postgresql", postgres: "postgresql" };

const requested = (process.env.DATABASE_PROVIDER ?? inferFromUrl() ?? "sqlite").toLowerCase();
const provider = PROVIDERS[requested];

if (!provider) {
  console.error(
    `[canvas] Unknown DATABASE_PROVIDER "${requested}". Supported: ${Object.keys(PROVIDERS).join(", ")}`,
  );
  process.exit(1);
}

/** A Postgres connection string is unambiguous, so honour it without ceremony. */
function inferFromUrl() {
  const url = process.env.DATABASE_URL ?? "";
  if (url.startsWith("postgres://") || url.startsWith("postgresql://")) return "postgresql";
  if (url.startsWith("file:")) return "sqlite";
  return null;
}

const root = path.join(import.meta.dirname, "..");
const source = path.join(root, "prisma", "schema.prisma");
const outDir = path.join(root, "prisma", ".generated");
const outFile = path.join(outDir, "schema.prisma");

const original = readFileSync(source, "utf8");

// Match only the provider inside the datasource block, never the generator's.
const datasource = /datasource\s+db\s*\{[^}]*\}/m.exec(original);
if (!datasource) {
  console.error("[canvas] Could not find the `datasource db` block in prisma/schema.prisma");
  process.exit(1);
}

let rewritten = original.replace(
  datasource[0],
  datasource[0].replace(/provider\s*=\s*"[^"]*"/, `provider = "${provider}"`),
);

/**
 * Generator output paths are resolved relative to the schema file. The
 * generated schema lives one directory deeper than the source, so a relative
 * output would land the client in `prisma/src/generated` instead of
 * `src/generated`. Re-anchor it to the project root.
 */
rewritten = rewritten.replace(
  /(generator\s+client\s*\{[^}]*output\s*=\s*")([^"]*)(")/m,
  (_match, head, target, tail) => {
    const absolute = path.resolve(path.dirname(source), target);
    const fromGenerated = path.relative(outDir, absolute).split(path.sep).join("/");
    return head + fromGenerated + tail;
  },
);

if (rewritten === original && provider !== "sqlite") {
  console.error("[canvas] Provider rewrite produced no change — check the datasource block format.");
  process.exit(1);
}

const banner = `// GENERATED FILE — do not edit.
// Produced by scripts/prepare-schema.mjs from prisma/schema.prisma
// for the "${provider}" provider. Edit the source schema instead.

`;

mkdirSync(outDir, { recursive: true });
writeFileSync(outFile, banner + rewritten);

console.log(`[canvas] Prisma schema prepared for ${provider}`);

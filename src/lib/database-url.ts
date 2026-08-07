/**
 * Chooses the database driver from the connection string alone.
 *
 * Three homes are supported, and the application is identical on all of them:
 *
 *   file:…            SQLite on local disk — development, zero services
 *   libsql:… / wss:…  Turso — SQLite over the network, works on serverless
 *   postgres…         PostgreSQL — any managed provider
 *
 * Turso matters because it speaks the SQLite dialect: the schema and the
 * migrations in prisma/migrations apply to it unchanged, so a deployment needs
 * no second migration set and no schema rewrite. It is the smallest possible
 * step from "runs on my laptop" to "has a URL".
 *
 * Shared by the application, the seed and the schema generator so all three
 * can never disagree about which database they are talking to.
 */

export type DatabaseKind = "sqlite" | "libsql" | "postgresql";

export function databaseKind(url: string): DatabaseKind {
  if (url.startsWith("postgres://") || url.startsWith("postgresql://")) return "postgresql";
  if (url.startsWith("libsql://") || url.startsWith("wss://") || url.startsWith("ws://")) return "libsql";
  if (url.startsWith("http://") || url.startsWith("https://")) return "libsql";
  return "sqlite";
}

/** The Prisma datasource provider. libSQL is SQLite as far as the schema is concerned. */
export function prismaProvider(kind: DatabaseKind): "sqlite" | "postgresql" {
  return kind === "postgresql" ? "postgresql" : "sqlite";
}

/** Migration SQL is dialect-specific; libSQL reuses the SQLite set. */
export function migrationsDir(kind: DatabaseKind): string {
  return kind === "postgresql" ? "migrations-postgres" : "migrations";
}

export function resolveDatabaseUrl(): string {
  return process.env.DATABASE_URL ?? "file:./prisma/dev.db";
}

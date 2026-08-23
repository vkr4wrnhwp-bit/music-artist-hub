import { test } from "node:test";
import assert from "node:assert/strict";
import { databaseKind, prismaProvider, migrationsDir } from "@/lib/database-url";

/**
 * The database switch. Wrong answers here are not subtle: the postgres
 * migration set applied to SQLite, or vice versa, is the app down at
 * boot. Shared by the application, the seed and the schema generator so
 * the three cannot disagree — which is only true while this file is.
 */

test("connection strings resolve to the driver that actually speaks them", () => {
  assert.equal(databaseKind("file:./prisma/dev.db"), "sqlite");
  assert.equal(databaseKind("postgres://u:p@host/db"), "postgresql");
  assert.equal(databaseKind("postgresql://u:p@host/db"), "postgresql");
  assert.equal(databaseKind("libsql://db-org.turso.io"), "libsql");
  assert.equal(databaseKind("wss://db-org.turso.io"), "libsql");
  assert.equal(databaseKind("https://db-org.turso.io"), "libsql");
});

test("libSQL is SQLite as far as the schema and migrations are concerned", () => {
  // Turso's whole value here: one migration set, no schema rewrite.
  assert.equal(prismaProvider("libsql"), "sqlite");
  assert.equal(migrationsDir("libsql"), "migrations");
  assert.equal(prismaProvider("postgresql"), "postgresql");
  assert.equal(migrationsDir("postgresql"), "migrations-postgres");
  assert.equal(prismaProvider("sqlite"), "sqlite");
});

import "server-only";
import { PrismaClient } from "@/generated/prisma";

/**
 * Development runs on a local SQLite file so CANVAS starts with no external
 * services. Production runs PostgreSQL. The provider is chosen from the
 * connection string, and the adapter is the only thing that differs — the
 * schema and every query are identical, which is what `scripts/prepare-schema.mjs`
 * exists to guarantee.
 */

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

const url = process.env.DATABASE_URL ?? "file:./prisma/dev.db";
export const isPostgres = url.startsWith("postgres://") || url.startsWith("postgresql://");

function createClient(): PrismaClient {
  if (isPostgres) {
    // Required at call time rather than imported at module scope so a SQLite
    // deployment never has to resolve the Postgres driver, and vice versa.
    const { PrismaPg } = require("@prisma/adapter-pg") as typeof import("@prisma/adapter-pg");
    return new PrismaClient({ adapter: new PrismaPg({ connectionString: url }) });
  }
  const { PrismaBetterSqlite3 } = require("@prisma/adapter-better-sqlite3") as typeof import("@prisma/adapter-better-sqlite3");
  return new PrismaClient({ adapter: new PrismaBetterSqlite3({ url }) });
}

export const db = globalForPrisma.prisma ?? createClient();

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = db;

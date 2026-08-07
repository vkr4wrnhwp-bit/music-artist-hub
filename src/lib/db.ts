import "server-only";
import { PrismaClient } from "@/generated/prisma";
import { databaseKind, resolveDatabaseUrl } from "./database-url";

/**
 * One codebase, three database homes — local SQLite, Turso, or PostgreSQL.
 * The driver is chosen from the connection string and nothing else in the
 * application knows or cares which one it got. See docs/DEPLOYMENT.md.
 */

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

const url = resolveDatabaseUrl();
export const kind = databaseKind(url);

function createClient(): PrismaClient {
  // Adapters are required lazily so a deployment never has to load — or, in
  // the case of the native better-sqlite3 binding, even resolve — a driver it
  // does not use.
  switch (kind) {
    case "postgresql": {
      const { PrismaPg } = require("@prisma/adapter-pg") as typeof import("@prisma/adapter-pg");
      return new PrismaClient({ adapter: new PrismaPg({ connectionString: url }) });
    }
    case "libsql": {
      const { PrismaLibSql } = require("@prisma/adapter-libsql") as typeof import("@prisma/adapter-libsql");
      // Turso issues a token alongside the URL; a local libsql file needs none.
      return new PrismaClient({
        adapter: new PrismaLibSql({ url, authToken: process.env.DATABASE_AUTH_TOKEN }),
      });
    }
    default: {
      const { PrismaBetterSqlite3 } =
        require("@prisma/adapter-better-sqlite3") as typeof import("@prisma/adapter-better-sqlite3");
      return new PrismaClient({ adapter: new PrismaBetterSqlite3({ url }) });
    }
  }
}

export const db = globalForPrisma.prisma ?? createClient();

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = db;

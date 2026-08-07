import path from "node:path";
import { defineConfig } from "prisma/config";

/**
 * Prisma 7 moves the datasource URL out of the schema. Development uses a
 * local SQLite file so CANVAS runs with no external services; production
 * swaps the adapter for PostgreSQL without schema changes.
 */
export default defineConfig({
  schema: path.join("prisma", "schema.prisma"),
  migrations: {
    path: path.join("prisma", "migrations"),
    seed: "tsx prisma/seed.ts",
  },
  datasource: {
    url: process.env.DATABASE_URL ?? "file:./prisma/dev.db",
  },
});

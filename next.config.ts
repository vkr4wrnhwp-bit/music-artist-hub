import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /**
   * Both database adapters are resolved at runtime rather than bundled.
   * `better-sqlite3` is a native module, so bundling it into a serverless
   * function breaks the build on a Postgres deployment that never uses it —
   * and `src/lib/db.ts` only ever requires the one matching the connection
   * string, so the unused driver is never loaded either way.
   */
  serverExternalPackages: [
    "@prisma/adapter-better-sqlite3",
    "better-sqlite3",
    "@prisma/adapter-pg",
    "@prisma/adapter-libsql",
    "@libsql/client",
    "pg",
  ],
};

export default nextConfig;

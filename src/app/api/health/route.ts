import { NextResponse } from "next/server";
import { db, kind } from "@/lib/db";

/**
 * Unauthenticated health and diagnostics.
 *
 * A deployment that half-works is opaque from the outside: the page renders,
 * sign-in fails, and the reason is buried in a build log. This endpoint answers
 * the three questions that actually matter — can the app reach its database,
 * do the tables exist, and has anything been seeded — in a form that can be
 * read at a glance or pasted into a bug report.
 *
 * It deliberately exposes no connection string, no credentials and no
 * organisation data. Counts and booleans only.
 */

export const dynamic = "force-dynamic";

export async function GET() {
  const started = Date.now();

  const report: Record<string, unknown> = {
    status: "unknown",
    databaseKind: kind,
    // Confirms which provider the client was generated for, which is the
    // single most common deployment mismatch.
    node: process.version,
    environment: process.env.NODE_ENV ?? "unknown",
    aiProvider: process.env.CANVAS_AI_PROVIDER ?? "deterministic",
  };

  try {
    const [users, organizations, parts, features] = await Promise.all([
      db.user.count(),
      db.organization.count(),
      db.part.count(),
      db.feature.count(),
    ]);

    report.status = users > 0 ? "ok" : "no-accounts";
    report.database = "connected";
    report.counts = { users, organizations, parts, features };
    report.seeded = organizations > 0;
    report.demoAccountPresent = Boolean(
      await db.user.findUnique({ where: { email: "demo@canvas.local" }, select: { id: true } }),
    );
    if (users === 0) {
      report.hint =
        "The database is reachable and migrated, but nothing has been seeded. Open /sign-in and use \"Create the demo shop\", or sign up for a new account.";
    }
  } catch (error) {
    report.status = "error";
    report.database = "unreachable-or-unmigrated";
    // The message is useful (missing table, auth failure, host unreachable);
    // the stack is not. Prisma's first line is often blank, so collapse
    // whitespace and take the first substantive text rather than line one.
    report.error = describeError(error);
    report.hint =
      "Either DATABASE_URL is wrong, or migrations have not been applied. Check the deploy log for `prisma migrate deploy`.";
  }

  report.responseMs = Date.now() - started;

  return NextResponse.json(report, {
    status: report.status === "error" ? 503 : 200,
    headers: { "cache-control": "no-store" },
  });
}

/**
 * Prisma errors are multi-line and frequently start with a blank line, so
 * naively taking the first line yields an empty string — useless in exactly
 * the situation this endpoint exists for. Collapse whitespace, prefer the
 * error code when there is one, and cap the length so no connection string
 * can ride along in a long message.
 */
function describeError(error: unknown): string {
  if (!(error instanceof Error)) return "Unknown error";
  const code = (error as { code?: string }).code;
  const text = error.message.replace(/\s+/g, " ").trim();
  const body = text.length > 0 ? text : error.name;
  return (code ? `${code}: ${body}` : body).slice(0, 300);
}

import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { randomBytes, timingSafeEqual } from "node:crypto";
import bcrypt from "bcryptjs";
import { db } from "./db";
import { roleCanWrite, roleCanApprove } from "./roles";

/**
 * Session authentication with organisation scoping.
 *
 * The organisation boundary is the most important security property in
 * CANVAS: one shop's proprietary geometry must never be reachable from
 * another shop's session. Every data accessor in the app takes the
 * organisation id from the session — never from a request parameter — so a
 * crafted URL cannot cross the boundary.
 */

const COOKIE = "canvas_session";
const SESSION_DAYS = 14;

export interface SessionUser {
  id: string;
  email: string;
  name: string;
  role: string;
  organizationId: string;
  organizationName: string;
  organizationSlug: string;
  onboardingDone: boolean;
}

export async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, 12);
}

export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash);
}

export async function createSession(userId: string, userAgent?: string): Promise<string> {
  const token = randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + SESSION_DAYS * 864e5);
  await db.session.create({ data: { token, userId, expiresAt, userAgent } });

  const jar = await cookies();
  jar.set(COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires: expiresAt,
  });
  return token;
}

export async function destroySession(): Promise<void> {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  if (token) await db.session.deleteMany({ where: { token } });
  jar.delete(COOKIE);
}

export async function getSessionUser(): Promise<SessionUser | null> {
  const jar = await cookies();
  const token = jar.get(COOKIE)?.value;
  if (!token) return null;

  const session = await db.session.findUnique({
    where: { token },
    include: { user: { include: { organization: true } } },
  });

  if (!session || session.expiresAt < new Date()) {
    if (session) await db.session.delete({ where: { id: session.id } }).catch(() => {});
    return null;
  }

  const { user } = session;
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    organizationId: user.organizationId,
    organizationName: user.organization.name,
    organizationSlug: user.organization.slug,
    onboardingDone: user.organization.onboardingDone,
  };
}

/** Use in every server component and action that touches organisation data. */
export async function requireUser(): Promise<SessionUser> {
  const user = await getSessionUser();
  // redirect() throws, so control never returns past this point.
  if (!user) redirect("/sign-in");
  return user;
}

/**
 * Both are enforced.
 *
 * canApprove is checked inside the two server actions that use it, against a
 * freshly read session rather than a rendered prop — a disabled button is not
 * a gate.
 *
 * canWrite was exported and called by nothing until every mutating action was
 * wired to requireWrite() or requireWriteApi(): thirty-six server actions and
 * seven route handlers. Before that, each of them checked that a user was
 * signed in and never what they were allowed to do.
 *
 * The change is a no-op for every account that exists today, because every
 * account this application creates is an OWNER — sign-up and the demo seed
 * both hardcode it, and there is no invite flow. It is not a fix for a live
 * hole; it makes a declared control real before there is a role that could
 * fall through it. tests/engines/tenancy.test.ts fails if a new mutating
 * action ships without one.
 */
export const canWrite = (user: SessionUser) => roleCanWrite(user.role);
export const canApprove = (user: SessionUser) => roleCanApprove(user.role);

/**
 * Signed in AND permitted to change something. Use in a mutating server
 * action in place of requireUser().
 */
export async function requireWrite(): Promise<SessionUser> {
  const user = await requireUser();
  if (!canWrite(user)) redirect("/");
  return user;
}

/**
 * Signed in, answered as a status.
 *
 * Some route handlers must not apply the write-role check — a viewer's own
 * guide progress, their own viewport preferences, a question they asked the
 * copilot, an analysis that writes nothing. They still must not REDIRECT: a
 * fetch() follows the 307 to /sign-in and parses a page of HTML as JSON, so
 * the caller is told nothing and the work is lost. `requireUser()` belongs in
 * a page, never in a route handler that a fetch() is waiting on.
 *
 * Returns the user, or the Response to return.
 */
export async function requireSessionApi(): Promise<{ user: SessionUser } | { denied: Response }> {
  const user = await getSessionUser();
  if (!user) {
    return {
      denied: new Response(JSON.stringify({ error: "Not signed in." }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    };
  }
  return { user };
}

/**
 * The same check for a route handler, which must answer with a status rather
 * than a redirect — a fetch() following a 307 to the dashboard and parsing
 * HTML as JSON is a worse failure than a plain 403.
 *
 * Returns the user, or the Response to return.
 */
export async function requireWriteApi(): Promise<{ user: SessionUser } | { denied: Response }> {
  const user = await getSessionUser();
  if (!user) {
    return { denied: new Response(JSON.stringify({ error: "Not signed in." }), { status: 401, headers: { "content-type": "application/json" } }) };
  }
  if (!canWrite(user)) {
    return {
      denied: new Response(JSON.stringify({ error: "Your role does not permit changing manufacturing data." }), {
        status: 403,
        headers: { "content-type": "application/json" },
      }),
    };
  }
  return { user };
}

/** Constant-time compare for any token comparison outside the DB lookup. */
export function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  return ab.length === bb.length && timingSafeEqual(ab, bb);
}

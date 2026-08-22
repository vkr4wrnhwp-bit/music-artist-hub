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
 * NOT YET ENFORCED — canWrite is exported and called by nothing.
 *
 * canApprove IS enforced, inside the two server actions that use it, against
 * a freshly read session rather than a rendered prop. canWrite has no such
 * caller: every mutating server action in the app checks that a user is
 * signed in and does not check what they may do. A VIEWER could change a
 * machine, a tool, a material or a sharing level.
 *
 * Nothing can exploit that today. Every user this application creates is an
 * OWNER — sign-up and the demo seed both hardcode it — and there is no invite
 * flow or role-assignment UI, so no VIEWER, MACHINIST or ENGINEER account can
 * exist. The hazard is a future one and it is specific: somebody adds user
 * invitations, sees an exported canWrite, and reasonably assumes writes are
 * already gated.
 *
 * requireWrite() below is the one line each action needs. Wiring it through
 * roughly thirty actions is a deliberate change with no non-OWNER account to
 * test the negative path against, so it is called out here rather than done
 * quietly.
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

/** Constant-time compare for any token comparison outside the DB lookup. */
export function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  return ab.length === bb.length && timingSafeEqual(ab, bb);
}

/**
 * WHO MAY DO WHAT
 *
 * Split out of auth.ts, which is server-only because it reads cookies and the
 * database. Deciding what a role may do is neither, and keeping it here means
 * the rule can be exercised.
 */

/** The roles the schema declares on User.role. */
export const ROLES = ["OWNER", "ENGINEER", "MACHINIST", "VIEWER"] as const;
export type Role = (typeof ROLES)[number];

/** Roles that may change manufacturing parameters. */
const WRITE_ROLES = new Set<string>(["OWNER", "ENGINEER", "MACHINIST"]);

/** Roles that may approve a package for export. */
const APPROVE_ROLES = new Set<string>(["OWNER", "ENGINEER"]);

/**
 * A role CANVAS does not recognise gets nothing.
 *
 * The alternative — treating an unknown role as a full one — would mean a
 * typo in a seed script or a role added to the schema and not to this file
 * silently granted permissions rather than withholding them.
 */
export const roleCanWrite = (role: string): boolean => WRITE_ROLES.has(role);
export const roleCanApprove = (role: string): boolean => APPROVE_ROLES.has(role);

import { createHash } from "node:crypto";

/**
 * APPROVING A TURNED PART, AND LOSING THAT APPROVAL
 *
 * `RotationalPart.humanApproved` had readers in three places and no writer
 * anywhere in `src/`. The turn readiness gate reports "Human approval —
 * Awaiting a named human. NOT ATTEMPTED", counts NOT_ATTEMPTED as blocking,
 * and `mintTurnExport` refuses while anything blocks — so lathe NC export was
 * unreachable for every rotational part in the system, and the card inviting
 * the operator to "REVIEW AND APPROVE" led nowhere.
 *
 * WHY A BOOLEAN WAS NOT ENOUGH
 *
 * On the milling side an `Approval` row is bound to a `partRevisionId`, so
 * changing the part means a new revision and the approval does not follow it.
 * A rotational part has no revision: profile, plan, lathe, workholding, grip,
 * stickout, clamp force and RPM clamp all sit on the one mutable row. Setting
 * a boolean there would mean an operator could approve a package, someone
 * could halve the grip length, and the approval would still read PASS over
 * geometry nobody approved.
 *
 * So an approval is bound to a digest of the state it was given. Change any of
 * those fields and the digest changes, the approval reads STALE, and the gate
 * is open again. This is the same rule review findings use: the acknowledgement
 * was of a specific condition, not of a title.
 */

/** The fields an approval is an approval OF. */
export interface ApprovableTurnState {
  /** RotationalProfile — the geometry itself. */
  profileJson: string;
  /** TurnOperation[] — the plan that will cut it. */
  planJson: string;
  latheMachineId: string | null;
  workholdingId: string | null;
  gripLength: number | null;
  stickout: number | null;
  clampForceLbf: number | null;
  tailstockActive: boolean;
  maxRpmClamp: number | null;
}

/**
 * A stable fingerprint of everything an operator was looking at.
 *
 * Field order is fixed here rather than taken from `Object.keys`, so a schema
 * reordering cannot silently invalidate every approval in the database — and
 * adding a field to `ApprovableTurnState` is a type error until it is listed,
 * which is the point: a new input that changes how the part is cut must
 * invalidate approvals of the old one.
 */
export function turnApprovalDigest(s: ApprovableTurnState): string {
  const canonical = [
    s.profileJson,
    s.planJson,
    s.latheMachineId ?? "",
    s.workholdingId ?? "",
    s.gripLength ?? "",
    s.stickout ?? "",
    s.clampForceLbf ?? "",
    s.tailstockActive ? "1" : "0",
    s.maxRpmClamp ?? "",
  ].join(" ");
  return createHash("sha256").update(canonical).digest("hex").slice(0, 32);
}

export type TurnApprovalState = "NONE" | "APPROVED" | "STALE";

export interface TurnApprovalRecord {
  humanApproved: boolean;
  approvedAt: Date | null;
  approvedDigest: string | null;
}

/**
 * Whether a recorded approval still applies to the part as it stands.
 *
 * An approval with no digest is treated as STALE rather than APPROVED. Rows
 * predating this column were approved by nothing — the flag has no writer in
 * the application's history — but even if one existed, an approval whose
 * subject cannot be identified is not evidence that this package was reviewed.
 */
export function turnApprovalState(record: TurnApprovalRecord, current: ApprovableTurnState): TurnApprovalState {
  if (!record.humanApproved) return "NONE";
  if (!record.approvedDigest) return "STALE";
  return record.approvedDigest === turnApprovalDigest(current) ? "APPROVED" : "STALE";
}

/** What the operator is putting their name to. Stored with the approval. */
export const TURN_APPROVAL_STATEMENT =
  "I have reviewed the profile, the turning plan, the lathe, the workholding and the grip for this part and accept responsibility for running it.";

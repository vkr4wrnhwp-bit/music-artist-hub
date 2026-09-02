import { createHash } from "node:crypto";
import type { ActorType } from "@/lib/audit";
import type { FindingEvidence, Severity } from "@/lib/engines/review";

/**
 * REVIEW FINDING PERSISTENCE
 *
 * The review engine is deterministic and is re-run on every visit. That is
 * deliberate — a finding has to reflect the setup as it is now. So nothing
 * here serves a stored finding in place of running the engine.
 *
 * What is stored is everything the engine cannot know on its own:
 *
 * - when a finding was first raised, and when it stopped being raised;
 * - what a human concluded about it, and against which evidence.
 *
 * The second half is the one that matters. A recorded response is bound to
 * the evidence digest it was recorded against. Change the stickout, re-run,
 * and the digest changes: the response does not silently carry over onto a
 * different engineering condition, it reads as stale and the finding is open
 * again. That is principle 2 surviving the trip through a database — the
 * acknowledgement was of a specific condition, not of a title.
 *
 * And per principle 11 a resolution clears nothing. It does not remove the
 * finding, does not lower its severity and does not touch a readiness gate.
 * It records that somebody looked.
 */

export const RESOLUTION_STATUSES = ["ACKNOWLEDGED", "ACTIONED", "DISPUTED"] as const;
export type ResolutionStatus = (typeof RESOLUTION_STATUSES)[number];

export const RESOLUTION_LABEL: Record<ResolutionStatus, string> = {
  ACKNOWLEDGED: "Seen, not yet actioned",
  ACTIONED: "Changed — re-run the review",
  DISPUTED: "Disagreed with",
};

/**
 * The digest is over the evidence and the severity, not the prose. A reworded
 * title is the same engineering condition; a changed number is not.
 */
export function evidenceDigest(severity: Severity, evidence: FindingEvidence[]): string {
  const canonical = JSON.stringify([severity, evidence.map((e) => [e.label, e.value])]);
  return createHash("sha256").update(canonical).digest("hex").slice(0, 32);
}

export interface FindingRecord {
  findingKey: string;
  firstSeenAt: Date;
  lastSeenAt: Date;
  clearedAt: Date | null;
  /** The most recent human response, if any. */
  resolution: {
    status: ResolutionStatus;
    note: string;
    actorType: ActorType;
    actorName: string;
    recordedAt: Date;
    /** False when the evidence has moved since the response was recorded. */
    current: boolean;
  } | null;
  /** Every response, newest first — the record of what was thought when. */
  history: { status: ResolutionStatus; note: string; actorName: string; actorType: ActorType; recordedAt: Date }[];
}


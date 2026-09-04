import { createHash } from "node:crypto";

/**
 * HAS THIS PROGRAM EVER CUT A GOOD PART?
 *
 * It is the most important property an NC program has and nothing recorded it.
 * A program proven on the VF-2 last Tuesday and the same program never run were
 * indistinguishable in this system — and no machinist treats them the same. The
 * first one gets loaded and run. The second one gets single-blocked with a hand
 * on the feed hold, and it should.
 *
 * This gate does NOT block. A program that has never cut a part is the normal
 * state of every new program, and a system that refused to release one would
 * make first articles impossible — which is to say it would be routed around
 * within a week. What it does is make the distinction visible, attributable and
 * auditable, so that "we ran this last month" is a record rather than a memory.
 *
 * THE DIGEST IS WHAT STOPS THE RECORD OUTLIVING THE PROGRAM
 *
 * A proof is about specific bytes. Regenerate the toolpath, re-post, and the
 * text is not the text anybody watched cut — so the proof goes STALE rather
 * than going on vouching for a program nobody has run. This is the same
 * construction as the turning side's approval digest, and for the same reason:
 * an approval that survives the thing it approved is worse than no approval,
 * because somebody relies on it.
 */

export type ProofState = "NEVER_RUN" | "PROVEN" | "STALE";

export interface ProofRecord {
  provenAt: Date | null;
  provenByName: string | null;
  provenMachineId: string | null;
  provenNote: string | null;
  provenDigest: string | null;
}

export interface ProofVerdict {
  state: ProofState;
  /** The sentence a machinist reads. */
  detail: string;
  provenAt: Date | null;
  provenByName: string | null;
  provenNote: string | null;
}

/** SHA-256 of the program text, hex. The same digest the export mint computes. */
export function programDigest(code: string): string {
  return createHash("sha256").update(Buffer.from(code, "utf8")).digest("hex");
}

export function proofState(record: ProofRecord, code: string, machineLabel: string | null): ProofVerdict {
  const base = { provenAt: record.provenAt, provenByName: record.provenByName, provenNote: record.provenNote };

  // Nobody has recorded a run. Not a failure — the state every program starts in.
  if (!record.provenAt || !record.provenDigest) {
    return {
      ...base,
      state: "NEVER_RUN",
      detail: "This program has never cut a part. Prove it out: single block, dry run above the part, hand on the feed hold.",
    };
  }

  if (record.provenDigest !== programDigest(code)) {
    return {
      ...base,
      state: "STALE",
      detail: `The program has changed since it was proven on ${record.provenAt.toISOString().slice(0, 10)}${
        record.provenByName ? ` by ${record.provenByName}` : ""
      }. What is here now has not been run. Prove it again.`,
    };
  }

  const where = machineLabel ? ` on the ${machineLabel}` : "";
  return {
    ...base,
    state: "PROVEN",
    detail: `Proven${where} on ${record.provenAt.toISOString().slice(0, 10)}${
      record.provenByName ? ` by ${record.provenByName}` : ""
    }${record.provenNote ? ` — ${record.provenNote}` : ""}.`,
  };
}

/**
 * IS THIS POST PROVEN ON THIS MACHINE?
 *
 * `PostDefinition.certified` is typed as the literal `false` — the same trick
 * as `clearableByConfirmation`, so no caller can argue with it — and that was
 * correct and also a dead end. There was no path OUT: no record of a post
 * having been validated, against which machine and which control software, by
 * whom, with what evidence. Every post was permanently DEVELOPMENT, which is
 * honest right up until it becomes the label nobody reads.
 *
 * Certification is not a property of the code. It is a property of a post
 * having been run on a specific machine, against a specific control software
 * version, by a named person who watched what happened. So it lives in a record
 * beside the machine, not in a flag beside the emitter.
 *
 * SCOPED, AND SUPERSEDED RATHER THAN INHERITED
 *
 * A post proven on the VF-2 says nothing about the VF-4 next to it: different
 * travels, different changer, possibly different control generation. And a
 * control software update can change how a canned cycle retracts or how
 * look-ahead handles short blocks — which is exactly the class of thing a post
 * validation is about. So the control version is part of the identity of what
 * was proven, and a different one reads SUPERSEDED rather than quietly
 * inheriting the old proof.
 *
 * This is the same shape as every other evidence record here. It does not make
 * the post certified in the abstract; it records that somebody proved this
 * combination, and the gate reads the record rather than a boolean.
 */

export interface PostValidationRecord {
  postId: string;
  machineId: string;
  controlVersion: string;
  validatedByName: string;
  validatedAt: Date;
  evidence: string;
  revokedAt: Date | null;
}

export type PostValidationState = "VALIDATED" | "SUPERSEDED" | "NONE";

export interface PostValidationVerdict {
  state: PostValidationState;
  detail: string;
  /** The record that decided it, when there is one. */
  record: PostValidationRecord | null;
  /**
   * True when the program did not come from a CANVAS post at all. The check
   * abstains rather than failing: it would be asking for evidence about the
   * wrong artifact.
   */
  foreign?: boolean;
}

/**
 * A program CANVAS did not write.
 *
 * An uploaded program came out of somebody else's CAM, and CANVAS's post
 * validation says nothing whatever about it: proving the Haas post here does
 * not vouch for a file Mastercam wrote. A gate that claimed otherwise would be
 * asking for evidence about the wrong artifact — and it would be the kind of
 * gate that gets cleared to make it go away.
 *
 * The program still carries every other check on the list. This one abstains,
 * by name.
 */
export function foreignProgram(labels: { machine: string | null }): PostValidationVerdict {
  return {
    state: "NONE",
    record: null,
    foreign: true,
    detail: `This program was not written by a CANVAS post, so validating a CANVAS post on ${
      labels.machine ?? "this machine"
    } says nothing about it. Whoever produced it is who vouches for the dialect.`,
  };
}

export function postValidationState(
  records: PostValidationRecord[],
  postId: string | null,
  machineId: string | null,
  controlVersion: string | null,
  labels: { post: string | null; machine: string | null },
): PostValidationVerdict {
  if (!postId || !machineId) {
    return {
      state: "NONE",
      record: null,
      detail: !postId
        ? "No post processor is selected, so there is nothing to have validated."
        : "No machine is assigned, and a post is only ever proven on a named machine.",
    };
  }

  const live = records
    .filter((r) => r.postId === postId && r.machineId === machineId && !r.revokedAt)
    .sort((a, b) => b.validatedAt.getTime() - a.validatedAt.getTime());

  if (live.length === 0) {
    return {
      state: "NONE",
      record: null,
      detail: `${labels.post ?? postId} has never been validated on ${
        labels.machine ?? "this machine"
      }. Executable NC from an unproven post is a program nobody has watched run.`,
    };
  }

  /*
   * A control version nobody recorded cannot be compared to one nobody
   * recorded. Treating "unknown equals unknown" as a match would let a proof
   * taken before a software update stand after it, which is the single case
   * this field exists to catch — so an absent version on either side is
   * SUPERSEDED, and the message says which half is missing.
   */
  const current = (controlVersion ?? "").trim();
  const matching = current === "" ? null : live.find((r) => r.controlVersion.trim() === current) ?? null;

  if (matching) {
    return {
      state: "VALIDATED",
      record: matching,
      detail: `${labels.post ?? postId} validated on ${labels.machine ?? "this machine"} at control ${
        matching.controlVersion
      } on ${matching.validatedAt.toISOString().slice(0, 10)} by ${matching.validatedByName} — ${matching.evidence}`,
    };
  }

  const newest = live[0];
  return {
    state: "SUPERSEDED",
    record: newest,
    detail:
      current === ""
        ? `${labels.post ?? postId} was validated on ${labels.machine ?? "this machine"} at control ${
            newest.controlVersion
          }, and this machine has no control version recorded — so nothing here can say the proof still applies.`
        : `${labels.post ?? postId} was validated at control ${newest.controlVersion} and this machine is now running ${current}. A control update can change how a canned cycle retracts or how look-ahead handles short blocks, which is what a post validation is about. Prove it again.`,
  };
}

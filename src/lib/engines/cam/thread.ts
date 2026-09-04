/**
 * THREADS: WHAT THE DESIGNATION SAYS, AND WHAT IT TAKES TO CUT IT.
 *
 * A tapped hole was SPOTTED and DRILLED and never threaded. The planner had no
 * TAP branch at all — the engine has had `tapToolpath` since Phase 1, the
 * operation type has always existed, and nothing ever emitted one. Four
 * "1/4-20 mounting hole" features on the seeded part came out as four plain
 * ⌀0.201 holes, and the coverage gate passed them because the feature HAS
 * operations. A part with no threads in it, and a plan that reads complete.
 *
 * MATCHING A TAP TO A THREAD IS NOT MATCHING A DIAMETER
 *
 * A 1/4-20 tap and a 1/4-28 tap are both ⌀0.250. Picking one by diameter puts
 * a 28-pitch tap into a hole drilled for 20 and snaps it off in the part, which
 * is the single most expensive thing that happens to a small hole. So the tool
 * carries its own designation and the match is on the thread, not the size —
 * the same rule as the chamfer mill's point angle.
 */

export interface Thread {
  /** As written, for messages. */
  designation: string;
  /** Nominal major diameter, inches. */
  major: number;
  /** Distance between crests, inches. */
  pitch: number;
}

/** Pitch in inches, from a designation. Null when it cannot be read. */
export function parseThreadPitch(thread: string): number | null {
  const metric = /M\s*\d+(?:\.\d+)?\s*[x×]\s*(\d+(?:\.\d+)?)/i.exec(thread);
  if (metric) {
    const mm = parseFloat(metric[1]);
    return mm > 0 ? mm / 25.4 : null;
  }
  const imperial = /(?:\d+\/\d+|#?\d+)\s*-\s*(\d+(?:\.\d+)?)/.exec(thread);
  if (imperial) {
    const tpi = parseFloat(imperial[1]);
    return tpi > 0 ? 1 / tpi : null;
  }
  return null;
}

/** Nominal major diameter in inches, where the designation states one. */
export function parseThreadMajor(thread: string): number | null {
  const metric = /M\s*(\d+(?:\.\d+)?)/i.exec(thread);
  if (metric) return parseFloat(metric[1]) / 25.4;
  const fraction = /^(\d+)\/(\d+)/.exec(thread.trim());
  if (fraction) return parseInt(fraction[1], 10) / parseInt(fraction[2], 10);
  const numbered = /^#(\d+)/.exec(thread.trim());
  if (numbered) return 0.06 + 0.013 * parseInt(numbered[1], 10);
  return null;
}

/** Both halves, or null when either cannot be read. */
export function parseThread(thread: string | null | undefined): Thread | null {
  if (!thread) return null;
  const major = parseThreadMajor(thread);
  const pitch = parseThreadPitch(thread);
  if (major === null || pitch === null || !(major > 0) || !(pitch > 0)) return null;
  return { designation: thread.trim(), major, pitch };
}

/**
 * Two designations describing the same thread.
 *
 * Compared on the numbers rather than the text, so "1/4-20 UNC" and "1/4-20"
 * are the same tap and "M6x1.0" and "M6 x 1" are the same tap. The series
 * suffix is deliberately not compared: UNC and UNF are already distinguished by
 * their pitch, and a shop that writes "1/4-20" on the tool and "1/4-20 UNC" on
 * the drawing is describing one thread.
 */
export function sameThread(a: string | null | undefined, b: string | null | undefined): boolean {
  const x = parseThread(a);
  const y = parseThread(b);
  if (!x || !y) return false;
  return Math.abs(x.major - y.major) < 0.001 && Math.abs(x.pitch - y.pitch) < 1e-6;
}

/**
 * THE HOLE A TAP NEEDS.
 *
 * `major − pitch` is the standard rule and it lands at about 77% thread
 * engagement, which is what a shop drills unless a print says otherwise: 1/4-20
 * gives 0.200 and the shop reaches for the #7 at 0.201. Deeper engagement buys
 * very little strength and costs tap life steeply — 100% engagement is where
 * taps break.
 *
 * This is used to CHECK a recorded hole, never to replace one. A drawing that
 * calls a different drill is the drawing's business; a hole recorded at the
 * thread's major diameter has no material left to cut a thread in, and that is
 * worth saying out loud before somebody runs it.
 */
export function tapDrill(thread: Thread): number {
  return thread.major - thread.pitch;
}

/**
 * How much of the thread form a hole of this size leaves, as a percentage.
 *
 * The usual approximation for UN and metric forms: engagement is the shortfall
 * from the major diameter measured against the full thread height, which is
 * 0.6495 × pitch for a 60° form on both.
 */
export function threadEngagement(thread: Thread, holeDiameter: number): number {
  const fullHeight = 2 * 0.6495 * thread.pitch;
  if (fullHeight <= 0) return 0;
  return ((thread.major - holeDiameter) / fullHeight) * 100;
}

/** Minor diameter of an internal thread — the hole the crest sits at. */
export const threadMinor = (thread: Thread): number => thread.major - 2 * 0.6495 * thread.pitch;

/**
 * HOW FAR PAST THE FULL THREAD A TAP HAS TO GO.
 *
 * A tap does not cut a full thread to the end of its travel: the lead chamfer
 * is still forming when it stops. A drawing calling a 0.500" thread depth wants
 * 0.500" of FULL FORM, so the tap's tip finishes a lead below that.
 *
 * In a THROUGH hole the hole is open and running past costs nothing, so a tool
 * that records no lead gets `PLUG_LEAD_THREADS` — a stated process allowance
 * printed in the operation's own rationale, not a number hidden in a Z.
 *
 * In a BLIND hole it costs everything: the tap has to reach the called-out
 * depth plus its lead and the drilled hole has to be deeper still, and a lead
 * assumed too short bottoms the tap and snaps it off. That case refuses.
 */
export const PLUG_LEAD_THREADS = 5;

/** Chips have to go somewhere at the bottom of a blind tapped hole. */
export const BLIND_TAP_CHIP_CLEARANCE_THREADS = 2;

export interface TapDepth {
  /** Z the tap's tip reaches, positive, below the top of the thread. */
  tip: number;
  /** How much of that is the lead rather than full thread. */
  lead: number;
  /** How deep the hole under it has to be drilled. */
  hole: number;
  /** True when the lead was the stated allowance rather than the tool's own. */
  assumed: boolean;
}

export function tapDepth(
  thread: Thread,
  threadDepth: number,
  through: boolean,
  leadThreads: number | null | undefined,
): TapDepth | { error: { reason: string; recommendations: string[] } } {
  if (leadThreads == null && !through) {
    return {
      error: {
        reason: `This is a blind ${thread.designation} and the tap records no lead chamfer. A tap has to reach the called-out depth plus its own lead, and the hole has to be deeper still — assume too short a lead and the tap bottoms and snaps off in the part.`,
        recommendations: [
          "Record the lead on the tap in threads: taper 7-10, plug 3-5, bottoming 1-1.5",
          "The catalogue page states it, and so does the box",
        ],
      },
    };
  }
  const threads = leadThreads ?? PLUG_LEAD_THREADS;
  const lead = threads * thread.pitch;
  return {
    tip: threadDepth + lead,
    lead,
    hole: through ? threadDepth : threadDepth + lead + BLIND_TAP_CHIP_CLEARANCE_THREADS * thread.pitch,
    assumed: leadThreads == null,
  };
}

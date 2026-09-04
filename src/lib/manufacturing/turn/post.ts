import type { TurnToolpath } from "./operations";

/**
 * DEVELOPMENT LATHE POST — generic Haas/Fanuc-style 2-axis turning.
 *
 * G18 plane, G20 inches, T0101-style calls, G96/G97 with a G50 clamp when
 * CSS is used. Feeds emit G99 (per-rev). No canned cycles, no threading
 * cycles (thread passes emit as G32-style feed-synchronous moves), no nose
 * radius compensation. The header says DEVELOPMENT — NOT FOR PRODUCTION USE
 * because that is what it is; the honest label is the feature.
 */

/**
 * The lathe posts that exist. One, and it is a development post.
 *
 * A machine row carries the post its control expects; if a shop records a
 * lathe whose control is not this, the readiness gate has to fail. The set is
 * here rather than in the package builder so adding a post and forgetting the
 * gate is not possible.
 */
export const LATHE_POSTS = new Set(["lathe-fanuc-dev"]);

export interface LathePostContext {
  programNumber: string;
  partName: string;
  machine: string;
  workOffset: string;
  /** G50 spindle clamp, RPM — REQUIRED when any operation runs CSS. */
  maxRpmClamp: number | null;
  generatedAtIso: string;
  /**
   * Where the turret retracts between operations, on diameter and in Z.
   *
   * This was `G0 X6.0 Z2.0`, hardcoded — a number that fits some lathes and
   * some parts and was derived from neither. On a machine with less X travel
   * it is outside the envelope; on a part longer than the Z guess it is
   * inside the work. Null refuses the program rather than guessing, which is
   * the same rule the deterministic engines follow everywhere else.
   */
  clearX: number | null;
  clearZ: number | null;
}

export interface LatheOpForPost {
  toolpath: TurnToolpath;
  station: string; // "0101"
  description: string;
  cssEnabled: boolean;
  surfaceSpeed: number | null;
  rpm: number;
  coolant: boolean;
}

export function emitLatheProgram(ops: LatheOpForPost[], ctx: LathePostContext): { code: string; refusals: string[] } {
  const refusals: string[] = [];
  const cssUsed = ops.some((o) => o.cssEnabled);
  if (cssUsed && ctx.maxRpmClamp === null) {
    refusals.push("CSS is programmed and no G50 maximum-RPM clamp was provided. An unclamped G96 winds the spindle to its limit as X approaches zero. Refusing to emit.");
    return { code: "", refusals };
  }

  /*
   * THREADING UNDER CSS IS A SCRAPPED PART, AND IT WAS ONLY A CONVENTION.
   *
   * A thread's lead comes from feed-per-rev against a CONSTANT spindle speed.
   * Under G96 the RPM changes as X changes, so the lead changes down the
   * thread and the second pass does not follow the first. The planner sets
   * cssEnabled false for threading and the comment in operations.ts says CSS
   * is never used for threading — but nothing stopped a caller handing this
   * emitter a threading operation with CSS on, and the post would have
   * written G96 followed by G32 without a word.
   *
   * The rule belongs here, beside the G50 check, for the same reason the mill
   * post refuses G41 D0 rather than trusting whoever built the toolpath.
   */
  for (const op of ops) {
    if (!op.cssEnabled) continue;
    if (op.toolpath.moves.some((m) => m.kind === "THREAD_PASS")) {
      refusals.push(
        `${op.description}: threading is programmed with CSS on. A thread's lead is feed-per-rev against a FIXED spindle speed — under G96 the RPM changes with X and the lead changes with it, so each pass cuts a different helix. Refusing to emit.`,
      );
    }
  }
  if (refusals.length > 0) return { code: "", refusals };

  if (ctx.clearX === null || ctx.clearZ === null) {
    refusals.push(
      "No retract position. The clear point has to come from the machine's travels and the part's own length; this post will not guess one, because a guess that is inside the work is a crash on the first tool change.",
    );
    return { code: "", refusals };
  }
  const clear = `G0 X${ctx.clearX.toFixed(4)} Z${ctx.clearZ.toFixed(4)} (CLEAR)`;

  const L: string[] = [];
  L.push("%");
  L.push(`O${ctx.programNumber}`);
  L.push(`(${ctx.partName.toUpperCase().slice(0, 30)})`);
  L.push(`(CANVAS DEVELOPMENT LATHE POST - NOT FOR PRODUCTION USE)`);
  L.push(`(MACHINE: ${ctx.machine})`);
  L.push(`(GENERATED ${ctx.generatedAtIso})`);
  L.push("(VERIFY EVERY LINE. DRY RUN. CONFIRM OFFSETS AT THE MACHINE.)");
  L.push("G18 G20 G40 G80 G99");
  L.push(`${ctx.workOffset}`);
  if (ctx.maxRpmClamp !== null) L.push(`G50 S${Math.round(ctx.maxRpmClamp)}`);

  for (const op of ops) {
    L.push(`(${op.description.toUpperCase().slice(0, 40)})`);
    /*
     * Index at the machine's own reference position, not wherever the last
     * operation happened to finish. A Haas lathe rotates the turret in place:
     * a long boring bar indexed near the chuck sweeps through it. G28 U0 W0
     * goes to reference incrementally with no intermediate point, so it is
     * defined by the machine rather than by a number this post invented.
     */
    L.push("G28 U0 W0");
    L.push(`T${op.station}`);

    /*
     * Rigid tapping is a canned cycle, not a sequence of feed moves. The
     * cycle (M29 arms it, G84 runs it, G80 closes it) owns the spindle —
     * it starts, synchronises, reverses at depth and backs out itself,
     * which is why there is no M3 here: a spindle already turning when
     * G84 takes over is a crashed tap. The engine's stand-in moves exist
     * for simulation and timing; emitting them as G1 would strip the
     * thread on the way out.
     */
    if (op.toolpath.rigidTapCycle) {
      const plunge = op.toolpath.moves.find((m) => m.kind === "CUT");
      const retractZ = op.toolpath.moves[0]?.z;
      if (!plunge || plunge.feedPerRev === null || retractZ === undefined) {
        refusals.push(`${op.description}: rigid tap cycle carries no synchronised plunge. Refusing to emit.`);
        continue;
      }
      L.push(`G0 X0. Z${retractZ.toFixed(4)}`);
      if (op.coolant) L.push("M8");
      L.push(`M29 S${Math.round(op.toolpath.spindleRpmOverride ?? op.rpm)}`);
      L.push(`G84 Z${plunge.z.toFixed(4)} F${plunge.feedPerRev.toFixed(4)}`);
      L.push("G80");
      if (op.coolant) L.push("M9");
      L.push(clear);
      continue;
    }

    if (op.cssEnabled && op.surfaceSpeed !== null) {
      L.push(`G96 S${Math.round(op.surfaceSpeed)} M3`);
    } else {
      L.push(`G97 S${Math.round(op.rpm)} M3`);
    }
    if (op.coolant) L.push("M8");
    for (const m of op.toolpath.moves) {
      const x = `X${m.x.toFixed(4)}`;
      const z = `Z${m.z.toFixed(4)}`;
      if (m.kind === "RAPID") L.push(`G0 ${x} ${z}`);
      else if (m.kind === "THREAD_PASS") L.push(`G32 ${x} ${z} F${m.feedPerRev!.toFixed(4)}`);
      else L.push(`G1 ${x} ${z} F${m.feedPerRev!.toFixed(4)}`);
    }
    if (op.coolant) L.push("M9");
    L.push(clear);
    L.push("M5");
  }
  L.push("G28 U0 W0");
  L.push("M30");
  L.push("%");
  return { code: L.join("\n"), refusals };
}

import type { Toolpath } from "@/lib/engines/cam/types";
import { flattenArcs } from "@/lib/engines/cam/arc";
import { parseNC, type NCSegment } from "./parse";

/**
 * DOES THE PROGRAM CUT THE PATH THE ENGINE PLANNED?
 *
 * Everything upstream verifies the TOOLPATH. The workholding assessment, the
 * holding margin, the height-field simulation, the cycle time, the collision
 * checks — all of them read `Toolpath.moves`. The post sits downstream of every
 * one of those proofs, and nothing read what came out of it.
 *
 * So a whole class of failure was invisible by construction: a dropped retract,
 * a modal feed carried into a rapid, an arc emitted with the wrong direction or
 * the wrong I/J sign, a canned cycle whose R plane does not match the moves it
 * replaced, an operation the post skipped. Each one produces a program that
 * looks like the plan and does not cut like it, and the simulation would have
 * gone on proving the plan.
 *
 * WHY THIS RATHER THAN A SECOND SIMULATOR
 *
 * The obvious move is to simulate the posted text as well — parse it, sweep the
 * height field again, compare the two results. This does something stronger and
 * cheaper: it proves the two paths are the SAME path, to a stated tolerance. If
 * the emitted program traces the moves the simulator already swept, then every
 * proof already run against those moves covers the program too, and there is no
 * second material-removal model to keep in step with the first. Two simulators
 * that disagree is a worse problem than the one being solved.
 *
 * WHAT IT DOES NOT COVER, STATED
 *
 * Geometry, not machine state. It says the tool goes where the plan says. It
 * says nothing about whether the work offset is set, whether the length offsets
 * are right, whether the spindle is running the right way, or whether the post
 * chose a coolant the machine has — `verifyNc` and the pre-flight cover parts of
 * that, and the setup sheet carries the rest to the machine.
 *
 * And where the parser refuses — a macro, a subprogram, an unknown G-word
 * carrying coordinates — this reports UNVERIFIED rather than clean. A dialect
 * that was not read must never come back verified, because verified is what an
 * operator reads as safe.
 */

/**
 * Position tolerance, inches.
 *
 * Two sources of honest disagreement remain after the planned side is flattened
 * as finely as it is below: the NC parser's own arc tessellation (0.001 chord)
 * and the post's rounding of Z to three places (0.0005). Measured worst case on
 * a real eight-tool part is 0.00102″ — the NC parser's arc chord tolerance exactly, with
 * everything else below rounding.
 *
 * Four thou, not two, and the margin is the point. A check that passes at
 * exactly its limit flips on the next arc, and a reconciliation that cries wolf
 * gets switched off. It is still one to two orders of magnitude tighter than any
 * error worth catching here: a reversed arc, a dropped pass, a wrong work offset
 * and a missing operation are all measured in tenths of an inch or worse.
 */
export const POSITION_TOLERANCE = 0.004;

/**
 * How finely the PLANNED path is flattened for comparison.
 *
 * Much tighter than the tolerance the engine emits at, and deliberately so:
 * this side of the comparison should contribute nothing to the error budget.
 * What is left is the NC parser's own arc tessellation (0.001) and the post's
 * rounding (0.0005), which leaves real margin under POSITION_TOLERANCE instead
 * of landing on it — a check that passes at exactly its limit is a check that
 * will flip on the next arc.
 */
const COMPARISON_CHORD = 0.0001;

/** Cutting-distance tolerance, as a fraction. */
export const DISTANCE_TOLERANCE = 0.02;

export interface ReconcileFinding {
  severity: "ERROR" | "WARNING";
  message: string;
  /** Program line, when the finding has one. */
  line?: number;
}

export interface ToolComparison {
  toolNumber: number;
  plannedCutting: number;
  postedCutting: number;
  /** Worst distance from a posted cutting point to the planned path. */
  maxDeviation: number;
}

export interface ReconcileResult {
  /** True only when the program was fully read AND matches the plan. */
  verified: boolean;
  findings: ReconcileFinding[];
  tools: ToolComparison[];
  /** Sentence for a gate, a pre-flight item or an export refusal. */
  detail: string;
}

interface Seg {
  x0: number; y0: number; z0: number;
  x1: number; y1: number; z1: number;
}

const len = (s: Seg) => Math.hypot(s.x1 - s.x0, s.y1 - s.y0, s.z1 - s.z0);

/** Distance from a point to a segment, in 3D. */
function pointToSegment(px: number, py: number, pz: number, s: Seg): number {
  const dx = s.x1 - s.x0;
  const dy = s.y1 - s.y0;
  const dz = s.z1 - s.z0;
  const l2 = dx * dx + dy * dy + dz * dz;
  if (l2 === 0) return Math.hypot(px - s.x0, py - s.y0, pz - s.z0);
  let t = ((px - s.x0) * dx + (py - s.y0) * dy + (pz - s.z0) * dz) / l2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (s.x0 + t * dx), py - (s.y0 + t * dy), pz - (s.z0 + t * dz));
}

/**
 * Sample points along a segment list, capped.
 *
 * The cap is what keeps this from being quadratic on a long program. It is a
 * cap on the CHECK, not on the program, so it is stated in the result rather
 * than left as a silent truncation — a check that quietly stopped looking is
 * the thing this module exists to prevent.
 */
const MAX_SAMPLES = 600;

function samplePoints(segs: Seg[]): { x: number; y: number; z: number }[] {
  const total = segs.reduce((s, g) => s + len(g), 0);
  if (total === 0) return [];
  const step = Math.max(total / MAX_SAMPLES, 1e-6);
  const out: { x: number; y: number; z: number }[] = [];
  let carry = 0;
  for (const g of segs) {
    const l = len(g);
    if (l === 0) continue;
    for (let d = step - carry; d < l; d += step) {
      const t = d / l;
      out.push({ x: g.x0 + (g.x1 - g.x0) * t, y: g.y0 + (g.y1 - g.y0) * t, z: g.z0 + (g.z1 - g.z0) * t });
    }
    carry = (carry + l) % step;
  }
  // The endpoints matter most — a dropped final move shows up there first.
  const last = segs[segs.length - 1];
  out.push({ x: last.x1, y: last.y1, z: last.z1 });
  return out;
}

/**
 * The path the PROGRAM carries, which is not always the cutter centre.
 *
 * Where cutter compensation is active the program holds the part boundary and
 * the control offsets it. Comparing the posted text against the cutter centre
 * there would report every compensated contour as being exactly one tool radius
 * wrong — a false alarm on the one operation a machinist most needs to trust.
 */
const programmedPath = (moves: Toolpath["moves"]) =>
  moves.map((m) =>
    m.program
      ? { ...m, x: m.program.x, y: m.program.y, ...(m.program.i !== undefined ? { i: m.program.i, j: m.program.j } : {}) }
      : m,
  );

function plannedSegments(tp: Toolpath): Seg[] {
  const moves = flattenArcs(programmedPath(tp.moves), COMPARISON_CHORD);
  const out: Seg[] = [];
  for (let i = 1; i < moves.length; i++) {
    const a = moves[i - 1];
    const b = moves[i];
    // Cutting moves only. A rapid's exact route is the control's business —
    // it is checked for gouging by the simulator, not for shape by this.
    if (b.feed === null) continue;
    out.push({ x0: a.x, y0: a.y, z0: a.z, x1: b.x, y1: b.y, z1: b.z });
  }
  return out;
}

const postedSegments = (segs: NCSegment[]): Seg[] =>
  segs
    .filter((s) => s.kind === "CUT" || s.kind === "ARC")
    .map((s) => ({ x0: s.x0, y0: s.y0, z0: s.z0, x1: s.x1, y1: s.y1, z1: s.z1 }));

/**
 * Dialects this cannot read.
 *
 * The NC parser is a Fanuc/Haas-family interpreter and says so. Run against a
 * Heidenhain conversational program or an 840D one it does not fail loudly — it
 * reads almost nothing, attributes what is left to tool zero, and produces a
 * page of confident nonsense: every planned tool reported as never cutting, and
 * one phantom tool reported as unplanned. Eight false alarms and nothing true.
 *
 * `verifyNc` already learned this lesson on Heidenhain. The rule is the same
 * here and it is the rule for the whole system: a dialect that was not read
 * must not come back verified, because verified is what an operator reads as
 * safe. Refusing by name is the honest answer, and it is also the one that puts
 * the pressure where it belongs — either the parser learns the dialect or the
 * post does not ship.
 */
const FOREIGN_DIALECTS: { test: RegExp; name: string; why: string }[] = [
  {
    test: /^\s*BEGIN PGM\b/m,
    name: "Heidenhain conversational",
    why: "L and C blocks rather than G1 and G2",
  },
  {
    test: /\bT\s*=\s*"/,
    name: "Siemens 840D",
    why: 'T="T1" tool calls and X= axis addressing',
  },
  {
    test: /^\s*G\d+\s+X=/m,
    name: "Siemens 840D",
    why: "X= axis addressing rather than X",
  },
];

export function reconcilePostedProgram(nc: string, toolpaths: Toolpath[]): ReconcileResult {
  const findings: ReconcileFinding[] = [];

  const foreign = FOREIGN_DIALECTS.find((d) => d.test.test(nc));
  if (foreign) {
    const message = `This is a ${foreign.name} program — ${foreign.why} — and CANVAS's NC reader is a Fanuc-family interpreter. The program has NOT been checked against the toolpath it came from, and nothing here says it cuts the planned shape.`;
    return {
      verified: false,
      findings: [{ severity: "ERROR", message }],
      tools: [],
      detail: message,
    };
  }

  const parsed = parseNC(nc);

  for (const r of parsed.refusals) {
    findings.push({
      severity: "ERROR",
      line: r.line,
      message: `The program could not be read past line ${r.line}: ${r.reason}. Everything after that point is unverified.`,
    });
  }

  const real = toolpaths.filter((t) => !t.isPlaceholder);
  const tools: ToolComparison[] = [];

  /*
   * A program with no tool change in it cannot be compared tool by tool.
   *
   * GRBL is the honest case: no changer, so the post writes M0 and a message
   * to the operator and there is no T word anywhere. Every segment then belongs
   * to tool zero, and comparing per tool would report every planned tool as
   * missing and one phantom tool as unplanned — eight false alarms and nothing
   * true. The geometry can still be checked as a whole, so it is, and the
   * result says which of the two checks actually ran.
   */
  const perTool = parsed.toolChanges.length > 0;
  if (!perTool && real.length > 0) {
    findings.push({
      severity: "WARNING",
      message:
        "This program contains no tool change, so motion cannot be attributed to a tool. The whole path is compared against the whole plan instead — a tool cutting another tool's path would not be caught.",
    });
  }

  const key = (n: number) => (perTool ? n : 0);
  const plannedByTool = new Map<number, Seg[]>();
  for (const tp of real) {
    const k = key(tp.toolNumber);
    plannedByTool.set(k, [...(plannedByTool.get(k) ?? []), ...plannedSegments(tp)]);
  }
  const postedByTool = new Map<number, Seg[]>();
  for (const s of parsed.segments) {
    if (s.kind !== "CUT" && s.kind !== "ARC") continue;
    const k = key(s.toolNumber);
    postedByTool.set(k, [...(postedByTool.get(k) ?? []), { x0: s.x0, y0: s.y0, z0: s.z0, x1: s.x1, y1: s.y1, z1: s.z1 }]);
  }

  const name = (n: number) => (perTool ? `T${n}` : "The program");
  for (const [toolNumber, planned] of plannedByTool) {
    const posted = postedByTool.get(toolNumber) ?? [];
    const plannedCutting = planned.reduce((a, g) => a + len(g), 0);
    const postedCutting = posted.reduce((a, g) => a + len(g), 0);

    if (posted.length === 0) {
      findings.push({
        severity: "ERROR",
        message: `${name(toolNumber)} cuts ${plannedCutting.toFixed(2)}" in the plan and does not cut at all in the program. The program runs to completion without that operation.`,
      });
      tools.push({ toolNumber, plannedCutting, postedCutting: 0, maxDeviation: Infinity });
      continue;
    }

    /*
     * Both directions, and no early exit.
     *
     * Both directions because a program that cuts a perfect SUBSET of the plan
     * would pass a one-way check while quietly dropping a pass.
     *
     * No early exit because this number is reported. Stopping the search as
     * soon as a point was inside tolerance made `maxDeviation` mean "the
     * largest distance found before the search gave up", which tracked the
     * tolerance rather than the program — raise the tolerance and the reported
     * worst case rose with it. A number on a screen in this system has to be
     * the number it claims to be.
     */
    const worstAgainst = (points: { x: number; y: number; z: number }[], against: Seg[]) => {
      let worst = 0;
      for (const p of points) {
        let best = Infinity;
        for (const g of against) {
          const d = pointToSegment(p.x, p.y, p.z, g);
          if (d < best) best = d;
        }
        if (best > worst) worst = best;
      }
      return worst;
    };
    const maxDeviation = Math.max(worstAgainst(samplePoints(posted), planned), worstAgainst(samplePoints(planned), posted));

    if (maxDeviation > POSITION_TOLERANCE) {
      findings.push({
        severity: "ERROR",
        message: `${name(toolNumber)} departs from the planned path by up to ${maxDeviation.toFixed(4)}", against a ${POSITION_TOLERANCE}" tolerance. The program does not cut the shape that was simulated and approved.`,
      });
    }

    const drift = plannedCutting === 0 ? 0 : Math.abs(postedCutting - plannedCutting) / plannedCutting;
    if (drift > DISTANCE_TOLERANCE) {
      findings.push({
        severity: "ERROR",
        message: `${name(toolNumber)} cuts ${postedCutting.toFixed(2)}" in the program against ${plannedCutting.toFixed(2)}" in the plan, ${(drift * 100).toFixed(0)}% apart. Something was added or dropped between the toolpath and the post.`,
      });
    }

    tools.push({ toolNumber, plannedCutting, postedCutting, maxDeviation });
  }

  for (const [toolNumber, posted] of postedByTool) {
    if (plannedByTool.has(toolNumber)) continue;
    findings.push({
      severity: "ERROR",
      message: `T${toolNumber} cuts ${posted.reduce((a, g) => a + len(g), 0).toFixed(2)}" in the program and appears nowhere in the plan. Nothing has assessed that motion for reach, holding or collision.`,
    });
  }

  if (real.length === 0) {
    findings.push({ severity: "ERROR", message: "There is no toolpath to compare the program against." });
  }

  for (const w of parsed.warnings) findings.push({ severity: "WARNING", message: w });

  const errors = findings.filter((f) => f.severity === "ERROR");
  const verified = errors.length === 0;

  const worst = tools.reduce((m, t) => Math.max(m, Number.isFinite(t.maxDeviation) ? t.maxDeviation : 0), 0);
  const detail = verified
    ? perTool
      ? `The program traces the planned toolpath for all ${tools.length} tools, worst departure ${worst.toFixed(4)}″ against a ${POSITION_TOLERANCE}″ tolerance.`
      : `The program traces the planned toolpath, worst departure ${worst.toFixed(4)}″ against a ${POSITION_TOLERANCE}″ tolerance. Not checked tool by tool — this program has no tool change.`
    : errors[0].message;

  return { verified, findings, tools, detail };
}

import type { Feature, Stock } from "@/lib/domain/features";
import { maximumDepth, minimumInternalRadius } from "@/lib/domain/features";
import type { MachineProfile, Tool, WorkholdingDevice } from "@/lib/domain/shop";
import { canReach, fitsInternalCorner } from "@/lib/domain/shop";
import type { OperationType } from "./cam/types";
import { chamferGeometry } from "./cam/chamfer";
import { PLUG_LEAD_THREADS, parseThread, sameThread, tapDepth, tapDrill, threadEngagement, threadMinor } from "./cam/thread";
import { annulusOf, footprintOf, overlaps } from "./cam/island";
import { BREAKOUT_CLEARANCE, drillPoint } from "./cam/drill-point";

/**
 * THE AI MACHINIST
 *
 * Ask two machinists to plan the same part and you get two different plans.
 * One packs everything into a single setup and accepts a long tool. One takes
 * the extra flip because they do not trust the grip. Both are defensible; they
 * are optimising different things, and which is right depends on the shop, the
 * quantity and what the part is for.
 *
 * So this does not produce "the plan". It produces several complete plans from
 * named priorities — thought patterns — and lets the deterministic engines
 * score them on cycle time, risk, setups, tool changes and cost. The machinist
 * proposes; arithmetic compares; a human approves. Nothing here writes to a
 * part.
 *
 * Deliberately rule-based, not a model. A plan a shop owner is going to sign
 * their name to has to be inspectable — you can read why this planner chose a
 * 3/8" tool and disagree with it. A model that emitted the same plan could not
 * offer that, and could not be argued with. The AI layer's role is to explain
 * an approach in prose, never to author it.
 */

export const THOUGHT_PATTERNS = [
  "MINIMUM_SETUPS",
  "LOWEST_RISK",
  "FASTEST_CYCLE",
  "BEST_FINISH",
  "MINIMUM_TOOLING",
] as const;
export type ThoughtPattern = (typeof THOUGHT_PATTERNS)[number];

export interface Philosophy {
  id: ThoughtPattern;
  name: string;
  /** How this machinist thinks, in their own words. */
  stance: string;
  /** What they will trade away to get it. */
  tradeoff: string;
  /** When a shop owner should pick this one. */
  suitedTo: string;
}

export const PHILOSOPHIES: Record<ThoughtPattern, Philosophy> = {
  MINIMUM_SETUPS: {
    id: "MINIMUM_SETUPS",
    name: "Fewest setups",
    stance:
      "Every flip is a re-datum, a new work offset and another chance to stack error. Do everything reachable from one orientation, even if that means a longer tool and a lighter cut.",
    tradeoff: "Longer tools deflect more, and cycle time goes up to compensate.",
    suitedTo: "Tight tolerances between features, low quantities, or an operator you do not want re-fixturing.",
  },
  LOWEST_RISK: {
    id: "LOWEST_RISK",
    name: "Lowest risk",
    stance:
      "The expensive failure is not a slow cycle, it is a part that moves in the vise at 80% through the last operation. Grip hard, cut light, machine soft jaws before you need them.",
    tradeoff: "More setups and more cycle time than strictly necessary.",
    suitedTo: "Expensive material, long cycles, unattended running, or a part you have already scrapped once.",
  },
  FASTEST_CYCLE: {
    id: "FASTEST_CYCLE",
    name: "Fastest cycle",
    stance:
      "Biggest tool that fits the smallest corner, heaviest engagement the setup will take, fewest tool changes. Spindle time is the product.",
    tradeoff: "Higher cutting loads, so the workholding has to be genuinely good.",
    suitedTo: "Production quantities where cycle time dominates the unit cost.",
  },
  BEST_FINISH: {
    id: "BEST_FINISH",
    name: "Best finish",
    stance:
      "Rough and finish are different jobs. Leave stock, change tools, take a light spring pass on anything with a tolerance or a surface callout.",
    tradeoff: "The slowest of the approaches, and it uses the most tools.",
    suitedTo: "Bearing seats, seal surfaces, cosmetic parts, or anything a customer will run a fingernail over.",
  },
  MINIMUM_TOOLING: {
    id: "MINIMUM_TOOLING",
    name: "Fewest tools",
    stance:
      "Use the smallest set of tools that can produce the part. Fewer tool changes, fewer offsets to set, fewer things to break at 2am.",
    tradeoff: "One tool doing several jobs does none of them optimally.",
    suitedTo: "A shop running lean on tooling, a machine with a small changer, or a job that has to run tonight.",
  },
};

/* ------------------------------------------------------------------ */
/* Plan shape                                                          */
/* ------------------------------------------------------------------ */

export interface PlannedOperation {
  sequence: number;
  type: OperationType;
  label: string;
  featureId: string | null;
  toolId: string | null;
  toolNumber: number | null;
  topZ: number;
  finalZ: number;
  /** Radial engagement as a fraction of tool diameter. */
  stepover: number;
  /** Left for a later finishing pass. */
  stockToLeave: number;
  /**
   * ROUGH | FINISH. A finish pass takes finishing chipload and runs the full
   * depth in one go where the flute allows, so the wall has no witness line at
   * every depth step. Absent means ROUGH.
   */
  pass?: "ROUGH" | "FINISH";
  /** Why this machinist chose this tool and these numbers. */
  rationale: string;
}

export interface PlannedSetup {
  sequence: number;
  name: string;
  orientation: "TOP" | "BOTTOM";
  /**
   * Which axis the part is turned over about to reach this orientation.
   *
   * "BOTTOM" on its own cannot say: rolled about X mirrors every Y, pitched
   * about Y mirrors every X, and both put the same face up. A plan that does
   * not say produces a setup nothing can generate motion for, which is the
   * honest outcome and not a useful one — so the planner states its intent and
   * the datum note says why it chose that way.
   */
  flipAxis: "X" | "Y" | null;
  workOffset: string;
  datumNote: string;
  gripDepth: number;
  gripLength: number;
  stockProjection: number;
  requiresSoftJaws: boolean;
  operations: PlannedOperation[];
  rationale: string;
}

export interface MachinistPlan {
  pattern: ThoughtPattern;
  philosophy: Philosophy;
  setups: PlannedSetup[];
  /** Distinct tools the plan needs. */
  toolNumbers: number[];
  /** Things this machinist wants the human to know before approving. */
  concerns: string[];
  /** Inputs the planner needed and did not have. */
  assumptions: string[];
}

export interface PlanInput {
  stock: Stock;
  features: Feature[];
  machine: MachineProfile;
  tools: Tool[];
  workholding: WorkholdingDevice | null;
  /** Finished part height, used to work out what grip is available. */
  finishedHeight: number;
}

/* ------------------------------------------------------------------ */
/* Tool selection — the heart of the difference between approaches     */
/* ------------------------------------------------------------------ */

const MILL_CLASSES = ["FLAT_END_MILL", "BULL_NOSE"];

/**
 * Picks a milling cutter for a feature. The ordering is what varies between
 * thought patterns: the fast machinist takes the largest tool that fits the
 * corner, the finish machinist takes a smaller one to leave a better wall.
 */
function selectMill(
  tools: Tool[],
  cornerRadius: number | null,
  depth: number,
  prefer: "LARGEST" | "SMALLEST" | "MIDDLE",
): { tool: Tool | null; reason: string } {
  const candidates = tools
    .filter((t) => MILL_CLASSES.includes(t.toolClass))
    .filter((t) => (cornerRadius === null ? true : fitsInternalCorner(t, cornerRadius)))
    .filter((t) => canReach(t, depth))
    .sort((a, b) => a.diameter - b.diameter);

  if (candidates.length === 0) {
    const blockedByCorner = tools
      .filter((t) => MILL_CLASSES.includes(t.toolClass))
      .filter((t) => cornerRadius !== null && !fitsInternalCorner(t, cornerRadius));
    return {
      tool: null,
      reason:
        blockedByCorner.length > 0 && cornerRadius !== null
          ? `No mill in the crib fits an R${cornerRadius.toFixed(4)} corner and reaches ${depth.toFixed(3)}".`
          : `No mill in the crib reaches ${depth.toFixed(3)}".`,
    };
  }

  if (prefer === "LARGEST") {
    const t = candidates[candidates.length - 1];
    return {
      tool: t,
      reason: `Largest tool that clears the corner and reaches depth — ⌀${t.diameter.toFixed(4)} removes material fastest.`,
    };
  }
  if (prefer === "SMALLEST") {
    const t = candidates[0];
    return {
      tool: t,
      reason: `⌀${t.diameter.toFixed(4)} deflects less than a larger cutter, which holds the wall straighter.`,
    };
  }
  const t = candidates[Math.floor((candidates.length - 1) / 2)];
  return { tool: t, reason: `⌀${t.diameter.toFixed(4)} balances removal rate against deflection.` };
}

function findTool(tools: Tool[], toolClass: string): Tool | null {
  return tools.find((t) => t.toolClass === toolClass) ?? null;
}

/**
 * The largest fraction of a bore diameter a mill may be and still interpolate
 * it. A cutter the same size as the bore cannot circle inside it — it can
 * only plunge — and one close to the same size leaves no room to ramp in.
 *
 * This is a planning convention rather than a physical limit, which is why it
 * is named here and repeated in the rationale: a machinist who wants to run
 * closer than this can see the number they are arguing with.
 */
const BORE_MILL_FRACTION = 0.7;

/**
 * Picks a mill to interpolate a bore.
 *
 * selectMill was being called with cornerRadius = diameter / 2, and
 * fitsInternalCorner only asks that tool radius <= corner radius — which for
 * a bore reduces to tool diameter <= bore diameter, satisfied by equality. On
 * FASTEST_CYCLE, which takes the largest candidate, a 0.5" bore with a 0.5"
 * end mill in the crib selected that end mill and planned a POCKET_2D at 60%
 * stepover. That toolpath cannot exist.
 */
function selectBoreMill(
  tools: Tool[],
  boreDiameter: number,
  depth: number,
  prefer: "LARGEST" | "SMALLEST" | "MIDDLE",
): { tool: Tool | null; reason: string } {
  const ceiling = boreDiameter * BORE_MILL_FRACTION;
  const usable = tools.filter((t) => MILL_CLASSES.includes(t.toolClass) && t.diameter <= ceiling);

  if (usable.length === 0) {
    const tooBig = tools.filter((t) => MILL_CLASSES.includes(t.toolClass) && t.diameter <= boreDiameter);
    return {
      tool: null,
      reason:
        tooBig.length > 0
          ? `No mill in the crib is small enough to interpolate a ⌀${boreDiameter.toFixed(4)} bore. The smallest that fits inside it at all is ⌀${Math.min(...tooBig.map((t) => t.diameter)).toFixed(4)}, which leaves nothing to ramp into — a cutter has to be under ⌀${ceiling.toFixed(4)} to circle this bore rather than plunge it.`
          : `No mill in the crib fits inside a ⌀${boreDiameter.toFixed(4)} bore.`,
    };
  }

  const picked = selectMill(usable, null, depth, prefer);
  if (!picked.tool) return picked;
  return {
    tool: picked.tool,
    reason: `${picked.reason} Held under ${(BORE_MILL_FRACTION * 100).toFixed(0)}% of the ⌀${boreDiameter.toFixed(4)} bore so it can ramp in rather than plunge.`,
  };
}

/* ------------------------------------------------------------------ */
/* Feature classification                                              */
/* ------------------------------------------------------------------ */

interface Classified {
  faces: Feature[];
  pockets: Feature[];
  /** Their own bucket: a slot is a centreline and a width, not a rectangle. */
  slots: Feature[];
  holes: Feature[];
  /** Holes that also carry a head to cut once the pilot exists. */
  heads: Feature[];
  bores: Feature[];
  /** Features that have to be LEFT STANDING when everything round them goes. */
  bosses: Feature[];
  contours: Feature[];
  chamfers: Feature[];
  engravings: Feature[];
}

/**
 * WHAT THE PLANNER SEES, AND WHAT IT USED TO MISS.
 *
 * SLOT sat in the pocket bucket, so every slot got a POCKET_2D operation the
 * pocket engine then refused — a plan that reads complete and cannot run.
 * COUNTERBORE and COUNTERSINK sat in no bucket at all: no operation, no
 * concern, total silence on a feature whose whole point is that a screw head
 * has to sit in it, caught only by the coverage gate at export.
 *
 * A head is BOTH a hole and a head: the pilot is drilled like any other hole
 * and the head is cut after it, which is why those kinds appear twice here.
 */
function classify(features: Feature[]): Classified {
  const headed = (f: Feature) => f.kind === "COUNTERBORE" || f.kind === "COUNTERSINK";
  return {
    faces: features.filter((f) => f.kind === "FACE"),
    pockets: features.filter((f) => f.kind === "RECT_POCKET"),
    slots: features.filter((f) => f.kind === "SLOT"),
    holes: features.filter((f) => f.kind === "DRILLED_HOLE" || f.kind === "TAPPED_HOLE" || headed(f)),
    heads: features.filter(headed),
    bores: features.filter((f) => f.kind === "BORE" || f.kind === "CIRC_POCKET"),
    bosses: features.filter((f) => f.kind === "BOSS"),
    contours: features.filter((f) => f.kind === "OUTSIDE_CONTOUR"),
    chamfers: features.filter((f) => f.kind === "CHAMFER"),
    engravings: features.filter((f) => f.kind === "ENGRAVING"),
  };
}

/**
 * Returns null rather than 0 when the feature does not say how deep it is.
 *
 * It used to fall through to 0, which produced a real planned operation with
 * finalZ: 0 — a pass that travels the whole toolpath at the top of the stock
 * and removes nothing. The plan then counted it in cycle time and tool
 * changes, and the operator read a pocket in the list that would not be cut.
 * A depth nobody recorded is a missing input, and the planner says so.
 */
/** Whether a feature is called out as going right through the part. */
const isThrough = (f: Feature): boolean => "through" in f && f.through === true;

const depthOf = (f: Feature, stock: Stock): number | null => {
  if ("through" in f && f.through) return stock.z;
  if ("depth" in f && typeof f.depth === "number") return f.depth;
  return null;
};

/* ------------------------------------------------------------------ */
/* The planner                                                         */
/* ------------------------------------------------------------------ */

export function planApproach(pattern: ThoughtPattern, input: PlanInput): MachinistPlan {
  const philosophy = PHILOSOPHIES[pattern];
  const { stock, features, tools } = input;
  const c = classify(features);
  const concerns: string[] = [];
  const assumptions: string[] = [];

  if (!input.workholding) {
    assumptions.push("No vise is defined, so grip and jaw engagement are assumed from a 6\" vise.");
  }

  const jawWidth = input.workholding?.jawWidth ?? 6;

  // How each pattern picks tools and loads them.
  const prefer: "LARGEST" | "SMALLEST" | "MIDDLE" =
    pattern === "FASTEST_CYCLE" || pattern === "MINIMUM_TOOLING"
      ? "LARGEST"
      : pattern === "BEST_FINISH"
        ? "SMALLEST"
        : "MIDDLE";

  const stepover =
    pattern === "FASTEST_CYCLE" ? 0.6 : pattern === "LOWEST_RISK" ? 0.3 : pattern === "BEST_FINISH" ? 0.35 : 0.45;

  // Finish passes are a separate operation only when the approach cares.
  const separateFinish = pattern === "BEST_FINISH";
  const stockToLeave = separateFinish ? 0.015 : pattern === "FASTEST_CYCLE" ? 0 : 0.01;

  /* ---- Setup strategy ---- */

  // Everything except the bottom face and the outside profile is reachable
  // from the top. The question each approach answers differently is whether
  // to take a second setup at all, and how hard to grip when it does.
  const needsSecondSetup = c.contours.length > 0 || pattern !== "MINIMUM_SETUPS";

  // Be honest when the part refuses to cooperate with the approach's whole
  // premise: an outside profile cannot be cut from the face you are gripping,
  // so "fewest setups" still means two here. Claiming otherwise, or quietly
  // planning two setups under a heading that promises one, would be worse
  // than saying so.
  if (pattern === "MINIMUM_SETUPS" && c.contours.length > 0) {
    concerns.push(
      "This part cannot be done in one setup. The outside profile is the surface being gripped, so it needs a flip regardless of approach — what this approach still buys you is everything else finished in Setup 1.",
    );
  }

  const facingAllowance = Math.max(0, stock.z - input.finishedHeight);
  const availableGrip = Math.max(0.05, stock.z - facingAllowance / 2);

  const gripPolicy: Record<ThoughtPattern, number> = {
    // Grip as much as the stock allows, because everything happens here.
    MINIMUM_SETUPS: Math.min(availableGrip * 0.6, 0.5),
    // Deliberately generous, and soft jaws rather than a marginal hold.
    LOWEST_RISK: Math.min(availableGrip * 0.75, 0.6),
    FASTEST_CYCLE: Math.min(availableGrip * 0.55, 0.45),
    BEST_FINISH: Math.min(availableGrip * 0.6, 0.5),
    MINIMUM_TOOLING: Math.min(availableGrip * 0.6, 0.5),
  };

  const setup1Grip = Number(gripPolicy[pattern].toFixed(3));

  /* ---- Setup 1: everything reachable from the top ---- */

  const ops1: PlannedOperation[] = [];
  let seq = 1;

  const faceMill = findTool(tools, "FACE_MILL") ?? findTool(tools, "SHELL_MILL");
  if (c.faces.length > 0 && faceMill) {
    ops1.push({
      sequence: seq++,
      type: "FACE",
      label: "Face top",
      featureId: c.faces[0].id,
      toolId: faceMill.id,
      toolNumber: faceMill.toolNumber,
      topZ: facingAllowance / 2,
      finalZ: 0,
      stepover: 0.7,
      stockToLeave: 0,
      rationale: `⌀${faceMill.diameter.toFixed(2)} face mill establishes Datum A in one pass across the ${stock.x.toFixed(2)}" width.`,
    });
  }

  // Pockets
  for (const f of c.pockets) {
    const cr = "cornerRadius" in f ? f.cornerRadius : null;
    const d = depthOf(f, stock);
    if (d === null) {
      concerns.push(`${f.label}: no depth recorded, so it cannot be planned. A pocket of unknown depth is a missing dimension, not a shallow one.`);
      continue;
    }
    /*
     * A pocket with something standing in it that is not a concentric round
     * island is an operation the engine refuses. Planning it anyway produces a
     * plan that reads complete and cannot run, which the boss's own concern
     * above has already explained.
     */
    const blocked = c.bosses.some(
      (b) =>
        footprintOf(f) !== null &&
        footprintOf(b) !== null &&
        overlaps(footprintOf(f)!, footprintOf(b)!) &&
        annulusOf(f, b) === null,
    );
    if (blocked) continue;
    const { tool, reason } = selectMill(tools, cr, d, prefer);
    if (!tool) {
      concerns.push(`${f.label}: ${reason}`);
      continue;
    }
    ops1.push({
      sequence: seq++,
      type: "POCKET_2D",
      label: `${separateFinish ? "Rough " : ""}${f.label}`,
      featureId: f.id,
      toolId: tool.id,
      toolNumber: tool.toolNumber,
      topZ: 0,
      finalZ: -d,
      stepover,
      stockToLeave,
      rationale: reason,
    });
    if (separateFinish) {
      const finish = selectMill(tools, cr, d, "SMALLEST");
      if (finish.tool) {
        ops1.push({
          sequence: seq++,
          type: "POCKET_2D",
          label: `Finish ${f.label}`,
          featureId: f.id,
          toolId: finish.tool.id,
          toolNumber: finish.tool.toolNumber,
          topZ: 0,
          finalZ: -d,
          stepover: 0.1,
          stockToLeave: 0,
          rationale: "Separate finish pass at light engagement so the wall is cut, not pushed.",
        });
      }
    }
  }

  /*
   * BOSSES.
   *
   * A boss was in no bucket at all: no operation, no concern, and the pocket
   * around it machined it away without a word. Cutting the material round a
   * boss IS island avoidance, so there is no separate boss operation to plan —
   * what there is, is the truth about it, said once per boss.
   *
   * The pocket that contains one refuses in the engine and names it, and the
   * coverage gate holds the part until somebody says how the boss is made.
   */
  for (const f of c.bosses) {
    const inPocket = [...c.pockets, ...c.bores].find(
      (pk) => footprintOf(pk) !== null && footprintOf(f) !== null && overlaps(footprintOf(pk)!, footprintOf(f)!),
    );
    concerns.push(
      inPocket
        ? `${f.label} stands inside ${inPocket.label}. Cutting the material round an island is island avoidance and this engine does not have it — the only case it can cut is a round island concentric in a round pocket.`
        : `${f.label} is left standing while the material round it goes, which is island avoidance and this engine does not have it. Nothing here will produce it.`,
    );
  }

  /*
   * SLOTS.
   *
   * A slot used to fall into the pocket bucket, so it got a POCKET_2D
   * operation that the pocket engine refused — a plan that reads complete,
   * produces an operation and cannot run.
   *
   * The tool has to FIT the slot, which is the opposite constraint to a
   * pocket: a pocket wants the biggest cutter that clears its corners, a slot
   * wants the biggest that is not wider than the slot itself. Full width is
   * the heaviest cut there is, so where the crib has something narrower the
   * plan takes it and leaves the walls to a finishing lap.
   */
  for (const f of c.slots) {
    if (f.kind !== "SLOT") continue;
    const d = depthOf(f, stock);
    if (d === null) {
      concerns.push(`${f.label}: no depth recorded, so it cannot be planned. A slot of unknown depth is a missing dimension, not a shallow one.`);
      continue;
    }
    const fits = tools
      .filter((t) => MILL_CLASSES.includes(t.toolClass) && t.diameter <= f.width + 1e-9 && canReach(t, d))
      .sort((a, b) => b.diameter - a.diameter);
    // The biggest that still leaves a wall to finish; failing that the biggest
    // that fits at all, which is a full-width cut and the engine says so.
    // Both are choices over a list this decision built, not a fallback to
    // whatever is first in the crib.
    const leavesWall = fits.filter((t) => t.diameter < f.width - 1e-9);
    const tool = (leavesWall.length > 0 ? leavesWall : fits)[0] ?? null;
    if (!tool) {
      const narrowest = tools
        .filter((t) => MILL_CLASSES.includes(t.toolClass))
        .sort((a, b) => a.diameter - b.diameter)[0];
      concerns.push(
        narrowest
          ? `${f.label} is ${f.width.toFixed(4)}" wide and ${d.toFixed(3)}" deep. The narrowest mill in the crib that reaches is not a fit — ⌀${narrowest.diameter.toFixed(4)} is the smallest there is.`
          : `${f.label}: no mill in the crib, so it cannot be produced.`,
      );
      continue;
    }
    ops1.push({
      sequence: seq++,
      type: "SLOT_MILL",
      label: f.label,
      featureId: f.id,
      toolId: tool.id,
      toolNumber: tool.toolNumber,
      topZ: 0,
      finalZ: -d,
      stepover: 0,
      stockToLeave: 0,
      rationale:
        tool.diameter < f.width - 1e-9
          ? `⌀${tool.diameter.toFixed(4)} in a ${f.width.toFixed(4)}" slot leaves ${((f.width - tool.diameter) / 2).toFixed(4)}" a side for a finishing lap, and the cutter is never more than half engaged.`
          : `⌀${tool.diameter.toFixed(4)} is the full width of the slot, so it runs 180° engaged. Nothing narrower in the crib reaches ${d.toFixed(3)}".`,
    });
  }

  // Holes — spot then drill, unless the approach is minimising tool changes.
  const spot = findTool(tools, "SPOT_DRILL") ?? findTool(tools, "CENTER_DRILL");
  const drills = tools.filter((t) => t.toolClass === "DRILL").sort((a, b) => a.diameter - b.diameter);
  if (c.holes.length > 0) {
    const spotWorthIt = pattern !== "MINIMUM_TOOLING" && pattern !== "FASTEST_CYCLE";

    // One drill per hole diameter.
    //
    // This used to take findTool(tools, "DRILL") — the first drill in the
    // crib, whatever it happened to be — and plan a single operation for
    // every hole in the part at the DEEPEST hole's depth. A part with a
    // 0.201 hole and a 0.500 hole came back as one op: drill both with the
    // ⌀0.201, 0.900" deep. The 0.500 hole was never produced, the small one
    // was drilled through the bottom of the part, and nothing was flagged.
    // Paired with the hole each one makes, so the spot operation beside it can
    // be built from the feature rather than by editing the drill's own label.
    const drillOps: { op: PlannedOperation; hole: Feature }[] = [];
    const byDiameter = new Map<number, Feature[]>();
    for (const h of c.holes) {
      const dia = "diameter" in h && typeof h.diameter === "number" ? h.diameter : null;
      if (dia === null) {
        concerns.push(`${h.label}: no diameter recorded, so no drill can be selected for it.`);
        continue;
      }
      byDiameter.set(dia, [...(byDiameter.get(dia) ?? []), h]);
    }

    for (const [dia, holes] of [...byDiameter.entries()].sort((a, b) => a[0] - b[0])) {
      const depths = holes.map((h) => depthOf(h, stock)).filter((v): v is number => v !== null);
      if (depths.length !== holes.length) {
        concerns.push(`⌀${dia.toFixed(4)} holes: not every one records a depth, so the group cannot be planned as one operation.`);
        continue;
      }
      const d = Math.max(...depths);

      // A drill is sized to the hole, not to whatever is first in the crib.
      const match = drills.find((t) => Math.abs(t.diameter - dia) < 0.0005) ?? null;
      if (!match) {
        const nearest = drills.length > 0
          ? drills.reduce((a, b) => (Math.abs(a.diameter - dia) < Math.abs(b.diameter - dia) ? a : b))
          : null;
        concerns.push(
          nearest
            ? `⌀${dia.toFixed(4)} ${holes.length === 1 ? "hole" : "holes"}: no drill of that size in the crib. The nearest is ⌀${nearest.diameter.toFixed(4)}, which is not the same hole.`
            : `⌀${dia.toFixed(4)} ${holes.length === 1 ? "hole" : "holes"}: no drill in the crib — they cannot be produced.`,
        );
        continue;
      }

      /*
       * ONE OPERATION PER HOLE.
       *
       * This used to emit a single operation labelled "Drill 6 × ⌀0.2010"
       * pointed at `holes[0].id`, and the toolpath engine drilled that one
       * hole. Five holes were never produced, no error was raised, the
       * operation reported real motion, and the pre-flight said every
       * operation had produced motion. The operator read a label promising six
       * holes, ran it, and took a part with one out of the machine.
       *
       * Per hole is also what the rest of the system is built on: coverage,
       * inspection method, measurement and tolerance are all per feature. The
       * program does not get longer for it — the post merges consecutive
       * cycles that share a tool and a depth into one G81 with a position
       * under it, which is what a real post writes anyway.
       */
      for (const hole of holes) {
        // Depth and the peck decision are the HOLE's, not the group's. The
        // group's deepest hole set both, so a 0.1" hole beside a 1.0" one was
        // drilled to 1.0" — through the bottom of the part and into the vise.
        const holeDepth = depthOf(hole, stock) ?? d;

        /*
         * A THROUGH HOLE IS DRILLED PAST THE MATERIAL BY THE DRILL'S POINT.
         *
         * The full diameter is reached a point-length behind the tip, so a
         * hole drilled to exactly the stock thickness comes off the machine
         * with a cone of material still in the bottom of it. It looks finished
         * everywhere in the system and fails on the first part.
         *
         * The point angle is required rather than assumed: 118° and 135°
         * differ by a quarter of the point length on the same drill, and there
         * is no safe direction to guess in — too shallow leaves the cone, too
         * deep drills the parallels.
         */
        const through = "through" in hole && hole.through === true;
        let tipZ = -holeDepth;
        let breakthroughNote = "";

        /*
         * A BLIND TAPPED HOLE IS DRILLED DEEPER THAN ITS THREAD.
         *
         * The drawing's depth on a tapped hole is the FULL-FORM thread depth.
         * The tap has to reach that plus its own lead chamfer, and the chips
         * have to go somewhere below that — so the drill goes deeper than
         * either. Drilling to the thread depth and then tapping to it is how a
         * tap bottoms out and snaps off in the part.
         *
         * A through hole needs none of this: the breakthrough below already
         * opens the far side.
         */
        let tapNote = "";
        if (!through && hole.kind === "TAPPED_HOLE") {
          const th = parseThread(hole.thread);
          const tapForThis = th
            ? tools.find((t) => t.toolClass === "TAP" && sameThread(t.threadDesignation, hole.thread))
            : null;
          if (th && tapForThis) {
            const dep = tapDepth(th, holeDepth, false, tapForThis.tapLeadThreads);
            if (!("error" in dep)) {
              tipZ = -dep.hole;
              tapNote = ` Drilled to ${dep.hole.toFixed(4)}" rather than the ${holeDepth.toFixed(3)}" thread depth: the tap reaches full form at ${holeDepth.toFixed(3)}" only if its ${dep.lead.toFixed(4)}" lead has somewhere to go, and the chips below that.`;
            }
          }
        }
        if (through) {
          const point = drillPoint(match);
          if ("error" in point) {
            concerns.push(`${hole.label}: ${point.error.reason}`);
            continue;
          }
          tipZ = -(holeDepth + point.breakthrough);
          breakthroughNote = ` Through hole: the tip runs to Z${tipZ.toFixed(4)}, which is the ${holeDepth.toFixed(3)}" of material plus the drill's ${point.pointLength.toFixed(4)}" point and ${BREAKOUT_CLEARANCE.toFixed(3)}" to break the burr clean. The part needs that much clearance under it.`;
        }

        /*
         * The peck decision is the MATERIAL, not the drilled depth. What packs
         * a flute is how much hole the chips have to climb; the point-length
         * overrun is mostly the point leaving the far side.
         */
        const ratio = holeDepth / match.diameter;
        drillOps.push({
          hole,
          op: {
            sequence: 0, // assigned below, once it is known whether spotting precedes them
            type: ratio > 4 ? "PECK_DRILL" : "DRILL",
            label: `Drill ${hole.label}`,
            featureId: hole.id,
            toolId: match.id,
            toolNumber: match.toolNumber,
            topZ: 0,
            finalZ: tipZ,
            stepover: 0,
            stockToLeave: 0,
            rationale:
              (ratio > 4
                ? `${ratio.toFixed(1)}:1 depth to diameter — pecking to clear chips rather than packing the flutes.`
                : `${ratio.toFixed(1)}:1 depth to diameter drills straight through without pecking.`) +
              breakthroughNote +
              tapNote,
          },
        });
      }
    }

    // Spot only if something is actually going to be drilled.
    //
    // The spot operation used to be emitted whenever the crib held a spot
    // drill and the part held any hole at all, before it was known whether
    // any of those holes had a drill to match. A part whose only hole was a
    // ⌀0.500 with no ⌀0.500 drill in the crib came back with one operation:
    // spot it. Centre-drilling holes nobody can then drill is a tool change
    // and a cycle spent on nothing, and it reads as though the holes are
    // handled.
    // One spot per hole, for the same reason as the drills — and the count no
    // longer comes from a regex over the drill operation's own label, which
    // was reading a number back out of a sentence the planner had just written.
    if (spot && spotWorthIt && drillOps.length > 0) {
      for (const { hole } of drillOps) {
        ops1.push({
          sequence: seq++,
          type: "DRILL",
          label: `Spot ${hole.label}`,
          featureId: hole.id,
          toolId: spot.id,
          toolNumber: spot.toolNumber,
          topZ: 0,
          finalZ: -0.08,
          stepover: 0,
          stockToLeave: 0,
          rationale: "Spotting first stops the drill walking on entry, which is where hole position is won or lost.",
        });
      }
    }
    for (const { op } of drillOps) ops1.push({ ...op, sequence: seq++ });
  }

  /*
   * THE HEAD ON A HOLE.
   *
   * COUNTERBORE and COUNTERSINK were in no bucket at all: no operation, no
   * concern, total silence on a feature whose whole point is that a screw head
   * has to sit in it. Only the coverage gate caught them, at export, three
   * pages away from the plan a machinist reads.
   *
   * The pilot is drilled above with every other hole; this is the head, and it
   * only goes in the plan if the pilot did — cutting a counterbore over a hole
   * nobody could drill is a tool change spent on nothing, and it reads as
   * though the feature is handled.
   */
  const drilled = new Set(ops1.filter((o) => o.type === "DRILL" || o.type === "PECK_DRILL").map((o) => o.featureId));
  for (const f of c.heads) {
    if (f.kind !== "COUNTERBORE" && f.kind !== "COUNTERSINK") continue;
    if (!drilled.has(f.id)) {
      concerns.push(`${f.label}: its own hole is not being drilled, so there is nothing to put a head on.`);
      continue;
    }
    const head = f.headDiameter;
    if (head == null || !(head > 0)) {
      concerns.push(
        `${f.label}: no head diameter recorded, and the head is the whole of what the operation cuts. The fastener standard gives it.`,
      );
      continue;
    }

    if (f.kind === "COUNTERSINK") {
      const want = f.countersinkAngle ?? 82;
      const sinks = tools.filter(
        (t) => (t.toolClass === "COUNTERSINK" || t.toolClass === "CHAMFER_MILL" || t.toolClass === "SPOT_DRILL") && t.pointAngle != null,
      );
      const tool = sinks.find((t) => Math.abs(t.pointAngle! - want) <= 0.5) ?? null;
      if (!tool) {
        const near = sinks.sort((a, b) => Math.abs(a.pointAngle! - want) - Math.abs(b.pointAngle! - want))[0];
        concerns.push(
          near
            ? `${f.label} is a ${want}° countersink and the nearest cone in the crib is ${near.description} at ${near.pointAngle}°. The angle of a countersink is the angle of the cone that cuts it — no depth makes a ${near.pointAngle}° tool cut ${want}°.`
            : `${f.label} is a ${want}° countersink and no tool in the crib records a point angle, so nothing here can be said to cut one.`,
        );
        continue;
      }
      ops1.push({
        sequence: seq++,
        type: "COUNTERSINK",
        label: `Countersink ${f.label}`,
        featureId: f.id,
        toolId: tool.id,
        toolNumber: tool.toolNumber,
        topZ: 0,
        // The engine derives the depth from the cone and the head diameter;
        // this is the same arithmetic, so the plan and the program agree.
        finalZ: -(head / 2 - (tool.tipDiameter ?? 0) / 2) / Math.tan(((tool.pointAngle! / 2) * Math.PI) / 180),
        stepover: 0,
        stockToLeave: 0,
        rationale: `⌀${head.toFixed(4)} at ${want}° comes off the ${tool.pointAngle}° cone at one depth — the diameter and the depth are one number, not two.`,
      });
      continue;
    }

    const depth = f.headDepth;
    if (depth == null || !(depth > 0)) {
      concerns.push(
        `${f.label}: no counterbore depth recorded. A head that sits proud is the failure this feature exists to prevent, and a depth nobody wrote down is not a shallow one.`,
      );
      continue;
    }
    // Mills only. A piloted counterbore of the finished size is a real tool
    // and the crib has no class for one; interpolating with an end mill holds
    // the size at the control instead, which is the answer a shop without the
    // exact piloted cutter reaches for anyway.
    const fits = tools
      .filter((t) => MILL_CLASSES.includes(t.toolClass) && t.diameter <= head + 1e-9 && canReach(t, depth))
      .sort((a, b) => b.diameter - a.diameter);
    const tool = fits[0] ?? null;
    if (!tool) {
      concerns.push(`${f.label}: no cutter in the crib fits a ⌀${head.toFixed(4)} counterbore ${depth.toFixed(3)}" deep.`);
      continue;
    }
    ops1.push({
      sequence: seq++,
      type: "COUNTERBORE",
      label: `Counterbore ${f.label}`,
      featureId: f.id,
      toolId: tool.id,
      toolNumber: tool.toolNumber,
      topZ: 0,
      finalZ: -depth,
      stepover: 0.4,
      stockToLeave: 0,
      rationale:
        Math.abs(tool.diameter - head) < 1e-9
          ? `⌀${tool.diameter.toFixed(4)} is the finished size, so it plunges down the pilot and cuts the bore in one.`
          : `⌀${tool.diameter.toFixed(4)} interpolates the ⌀${head.toFixed(4)} bore, which holds the size at the control rather than at the tool crib.`,
    });
  }

  /*
   * THREADS.
   *
   * There was no branch here at all. `tapToolpath` has existed since Phase 1,
   * the TAP operation type has always existed, the seeded crib holds a 1/4-20
   * tap — and nothing ever emitted the operation. Every TAPPED_HOLE was spotted
   * and drilled and came out as a plain hole, and the coverage gate passed it
   * because the feature HAS operations. A part with no threads in it, and a
   * plan that reads complete.
   *
   * The match is on the THREAD, not the diameter. A 1/4-20 tap and a 1/4-28 tap
   * are both ⌀0.250, and picking one by size puts a 28-pitch tap into a hole
   * drilled for 20 and snaps it off in the part.
   */
  for (const f of c.holes) {
    if (f.kind !== "TAPPED_HOLE") continue;
    const thread = parseThread(f.thread);
    if (!thread) {
      concerns.push(
        f.thread
          ? `${f.label}: the thread "${f.thread}" cannot be read for a pitch and a major diameter, and both are needed to cut it.`
          : `${f.label}: no thread designation recorded, so nothing here can say what thread to cut.`,
      );
      continue;
    }

    /*
     * The hole has to have material left in it to thread. `major − pitch` is
     * the standard tap drill and lands at about 77% engagement; a hole recorded
     * at the thread's own major diameter has nothing to cut. This checks the
     * recorded hole rather than replacing it — a drawing that calls a different
     * drill is the drawing's business.
     */
    const engagement = threadEngagement(thread, f.diameter);
    if (engagement < 40) {
      concerns.push(
        `${f.label} is recorded as a ⌀${f.diameter.toFixed(4)} hole for ${thread.designation}, which leaves ${engagement.toFixed(0)}% of the thread form. The tap drill is ⌀${tapDrill(thread).toFixed(4)} — check which diameter the drawing means.`,
      );
    } else if (engagement > 85) {
      concerns.push(
        `${f.label} at ⌀${f.diameter.toFixed(4)} puts ${engagement.toFixed(0)}% of the thread form on the tap. Past about 80% the strength barely moves and tap life falls off a cliff; ⌀${tapDrill(thread).toFixed(4)} is the usual drill.`,
      );
    }

    /*
     * The engagement check comes BEFORE the drilled check on purpose. A hole
     * recorded at the thread's own major diameter usually has no drill in the
     * crib either, and "its own hole is not being drilled" is the symptom
     * while the recorded diameter is the cause.
     */
    if (!drilled.has(f.id)) {
      concerns.push(`${f.label}: its own hole is not being drilled, so there is nothing to thread.`);
      continue;
    }

    const tap = tools.find((t) => t.toolClass === "TAP" && sameThread(t.threadDesignation, f.thread));
    const mill = tools.find(
      (t) => t.toolClass === "THREAD_MILL" && sameThread(t.threadDesignation, f.thread) && t.diameter < threadMinor(thread),
    );
    const depth = depthOf(f, stock) ?? 0;
    // A thread mill only cuts the whole thread in one turn where its form
    // covers it, so a shallow-form mill is not a substitute for a tap here.
    const millFits = mill && mill.fluteLength >= depth;

    if (tap && !(pattern === "BEST_FINISH" && millFits)) {
      /*
       * The tap goes PAST the called-out depth by its own lead chamfer, because
       * the chamfer is still forming when it stops. A drawing asking for 0.500"
       * of thread wants 0.500" of full form, and a tap that stops there leaves
       * the last threads incomplete.
       */
      const dep = tapDepth(thread, depth, isThrough(f), tap.tapLeadThreads);
      if ("error" in dep) {
        concerns.push(`${f.label}: ${dep.error.reason}`);
        continue;
      }
      ops1.push({
        sequence: seq++,
        type: "TAP",
        label: `Tap ${f.label}`,
        featureId: f.id,
        toolId: tap.id,
        toolNumber: tap.toolNumber,
        topZ: 0,
        finalZ: -dep.tip,
        stepover: 0,
        stockToLeave: 0,
        rationale:
          `${thread.designation} rigid tapped. The feed is the thread — ${thread.pitch.toFixed(4)}" per revolution — not a number anybody chose. ` +
          `The tip runs to ${dep.tip.toFixed(4)}" so full form reaches the called-out ${depth.toFixed(3)}": the last ${dep.lead.toFixed(4)}" is the tap's lead chamfer, still cutting.` +
          (dep.assumed
            ? ` ${tap.description} records no lead, so ${PLUG_LEAD_THREADS} threads is assumed — free in a through hole, and recorded on the tool it would not be an assumption.`
            : ""),
      });
      continue;
    }
    if (millFits && mill) {
      ops1.push({
        sequence: seq++,
        type: "THREAD_MILL",
        label: `Thread mill ${f.label}`,
        featureId: f.id,
        toolId: mill.id,
        toolNumber: mill.toolNumber,
        topZ: 0,
        finalZ: -depth,
        stepover: 0,
        stockToLeave: 0,
        rationale: tap
          ? `${thread.designation} milled rather than tapped: the size comes off the D offset, which is how a class-3 fit is held and how the first article is corrected without a new tool.`
          : `No ${thread.designation} tap in the crib. A full-form mill cuts it in one turn, and a broken mill comes out of the hole where a broken tap does not.`,
      });
      continue;
    }

    const nearMill = tools.find((t) => t.toolClass === "THREAD_MILL" && sameThread(t.threadDesignation, f.thread));
    concerns.push(
      nearMill
        ? `${f.label}: ${nearMill.description} carries ${nearMill.fluteLength.toFixed(3)}" of form against a ${depth.toFixed(3)}" thread, so one turn would leave the bottom of it uncut, and there is no ${thread.designation} tap in the crib.`
        : `${f.label}: nothing in the crib cuts ${thread.designation}. It needs a tap or a full-form thread mill of that pitch — the hole will be drilled and left unthreaded otherwise.`,
    );
  }

  // Bores — the feature most likely to carry a real tolerance.
  for (const f of c.bores) {
    const d = depthOf(f, stock);
    const diameter = "diameter" in f ? f.diameter : null;
    if (d === null || diameter === null) {
      concerns.push(
        `${f.label}: ${d === null ? "no depth" : "no diameter"} recorded, so it cannot be planned.`,
      );
      continue;
    }
    const { tool, reason } = selectBoreMill(tools, diameter, d, prefer);
    if (!tool) {
      concerns.push(`${f.label}: ${reason}`);
      continue;
    }
    ops1.push({
      sequence: seq++,
      type: "POCKET_2D",
      label: `${f.critical ? "Rough " : ""}${f.label}`,
      featureId: f.id,
      toolId: tool.id,
      toolNumber: tool.toolNumber,
      topZ: 0,
      finalZ: -d,
      stepover,
      stockToLeave: f.critical ? 0.02 : stockToLeave,
      rationale: f.critical
        ? `${reason} Leaving 0.020" for a finishing operation because this bore carries a tolerance.`
        : reason,
    });

    if (f.critical) {
      const boring = findTool(tools, "BORING_TOOL");
      if (boring) {
        ops1.push({
          sequence: seq++,
          type: "BORE",
          label: `Finish ${f.label}`,
          featureId: f.id,
          toolId: boring.id,
          toolNumber: boring.toolNumber,
          topZ: 0,
          finalZ: -d,
          stepover: 0,
          stockToLeave: 0,
          rationale: "A boring head holds size and roundness in a way an interpolated end mill does not.",
        });
      } else {
        concerns.push(
          `${f.label} carries a tolerance but there is no boring tool in the crib — interpolating with an end mill will struggle to hold it.`,
        );
      }
    }
  }

  // Engraving
  const engraver = findTool(tools, "ENGRAVER");
  for (const f of c.engravings) {
    if (!engraver) {
      concerns.push(`${f.label}: no engraving tool in the crib.`);
      continue;
    }
    ops1.push({
      sequence: seq++,
      type: "ENGRAVE",
      label: f.label,
      featureId: f.id,
      toolId: engraver.id,
      toolNumber: engraver.toolNumber,
      topZ: 0,
      finalZ: -("depth" in f ? f.depth : 0.01),
      stepover: 0,
      stockToLeave: 0,
      rationale: "Engraved last on this face so a later roughing pass cannot damage it.",
    });
  }

  /*
   * Chamfer — one per chamfer feature, at the depth the geometry gives.
   *
   * "Chamfer top edges" pointed at `chamfers[0]` was the same defect as the
   * drills: every other chamfer on the part went uncut, and the label did not
   * say which one it meant. `finalZ` was a hard-coded −0.03 regardless of the
   * chamfer's width or the tool's angle, which is a number that produces the
   * drawn chamfer only by coincidence.
   *
   * The depth comes from `chamferGeometry`, which is the same function the
   * toolpath engine calls — so the plan, the setup sheet and the program all
   * carry one number rather than three that can drift. Where the tool cannot
   * cut the chamfer at all, the plan says which tool would rather than
   * planning an operation the engine will refuse.
   */
  const chamfer = findTool(tools, "CHAMFER_MILL");
  if (c.chamfers.length > 0 && !chamfer) {
    concerns.push(
      `${c.chamfers.length === 1 ? "The chamfer" : `${c.chamfers.length} chamfers`} on this part cannot be cut: there is no chamfer mill in the crib. Break the edges by hand or add one.`,
    );
  }
  if (chamfer) {
    for (const f of c.chamfers) {
      if (f.kind !== "CHAMFER") continue;
      const geo = chamferGeometry(f, chamfer);
      if ("error" in geo) {
        concerns.push(`${f.label}: ${geo.error.reason}`);
        continue;
      }
      ops1.push({
        sequence: seq++,
        type: "CHAMFER",
        label: `Chamfer ${f.label}`,
        featureId: f.id,
        toolId: chamfer.id,
        toolNumber: chamfer.toolNumber,
        topZ: 0,
        finalZ: geo.z,
        stepover: 0,
        stockToLeave: 0,
        rationale: `${f.width.toFixed(4)} × ${f.angle}° comes off the ${chamfer.pointAngle}° cone at Z${geo.z.toFixed(4)} — the depth and the width are one number, not two. Breaking edges on the machine is cheaper than a deburring bench and far more consistent.`,
      });
    }
  }

  const setups: PlannedSetup[] = [
    {
      sequence: 1,
      name: "SETUP 1 — Top face and features",
      orientation: "TOP",
      flipAxis: null,
      workOffset: "G54",
      datumNote:
        "Datum A is the machined top face. X0Y0 at the part centre, established by probing the stock rather than trusting the saw cut.",
      gripDepth: setup1Grip,
      gripLength: Math.min(stock.x, jawWidth),
      stockProjection: Number((stock.z - setup1Grip).toFixed(3)),
      requiresSoftJaws: false,
      operations: ops1,
      rationale:
        pattern === "MINIMUM_SETUPS"
          ? "Everything reachable from above happens here, including features a second setup would otherwise pick up."
          : "Standard first operation on saw-cut stock, gripping the as-supplied outside.",
    },
  ];

  /* ---- Setup 2 ---- */

  if (needsSecondSetup) {
    const ops2: PlannedOperation[] = [];
    let s2 = 1;

    if (faceMill) {
      ops2.push({
        sequence: s2++,
        type: "FACE",
        label: "Face bottom to thickness",
        // Not c.faces[0] — that is the TOP face, machined in Setup 1. Naming
        // it here pointed SHOW ME at the wrong surface and attributed two
        // operations on opposite sides of the part to one feature.
        featureId: c.faces[1]?.id ?? null,
        toolId: faceMill.id,
        toolNumber: faceMill.toolNumber,
        topZ: facingAllowance / 2,
        finalZ: 0,
        stepover: 0.7,
        stockToLeave: 0,
        rationale: "Bringing the part to final thickness against the datum established in Setup 1.",
      });
    }

    for (const f of c.contours) {
      const cr = "cornerRadius" in f ? f.cornerRadius : null;
      const d = depthOf(f, stock) ?? stock.z; // a profile with no depth runs the full stock height
      const { tool, reason } = selectMill(tools, cr, d, prefer);
      if (!tool) {
        concerns.push(`${f.label}: ${reason}`);
        continue;
      }
      /*
       * A WALL THAT MATTERS GETS ITS OWN PASS.
       *
       * This used to depend on the approach: only BEST_FINISH split rough from
       * finish, so a toleranced profile planned under any other heading got
       * roughing feeds on its final wall and a witness line at every depth
       * step. The approach decides how hard to push, not whether a toleranced
       * surface is finished — that is a property of the feature.
       *
       * FASTEST_CYCLE still gets one pass when the profile carries no
       * tolerance and is not critical, because there the wall is a wall.
       */
      const needsFinish = separateFinish || f.critical || Boolean(f.tolerance);
      ops2.push({
        sequence: s2++,
        type: "CONTOUR_2D",
        label: `${needsFinish ? "Rough " : "Finish "}${f.label}`,
        featureId: f.id,
        toolId: tool.id,
        toolNumber: tool.toolNumber,
        topZ: 0,
        finalZ: -d,
        stepover,
        stockToLeave: needsFinish ? Math.max(stockToLeave, 0.015) : stockToLeave,
        pass: "ROUGH",
        rationale: reason,
      });
      if (needsFinish) {
        const finish = selectMill(tools, cr, d, "SMALLEST");
        if (finish.tool) {
          ops2.push({
            sequence: s2++,
            type: "CONTOUR_2D",
            label: `Finish ${f.label}`,
            featureId: f.id,
            toolId: finish.tool.id,
            toolNumber: finish.tool.toolNumber,
            topZ: 0,
            finalZ: -d,
            stepover: 0.08,
            stockToLeave: 0,
            pass: "FINISH",
            rationale:
              finish.tool.fluteLength >= d
                ? "Full-depth finishing pass: one continuous wall, no witness line at a depth step."
                : `Finishing pass. ${finish.tool.description} has ${finish.tool.fluteLength.toFixed(3)}" of flute against a ${d.toFixed(3)}" wall, so it steps down and will show a line at each step.`,
          });
        } else {
          concerns.push(
            `${f.label} is toleranced and no tool in the crib can finish it in a separate pass — the roughing pass is the wall.`,
          );
        }
      }
    }

    // The second setup is where grip gets hard: the outside is now finished
    // geometry, and there is much less material to hold.
    const remaining = Math.max(0.05, input.finishedHeight);
    const wantedGrip =
      pattern === "LOWEST_RISK" ? 0.2 : pattern === "FASTEST_CYCLE" ? 0.1 : 0.15;
    const grip = Number(Math.min(wantedGrip, remaining * 0.35).toFixed(3));

    // Soft jaws are how a second operation gets a repeatable hold. The risk-
    // averse machinist always cuts them; the fast one only when forced.
    const softJaws =
      pattern === "LOWEST_RISK" ||
      pattern === "BEST_FINISH" ||
      grip < 0.14 ||
      c.contours.length > 0;

    // A flip that does no work is not a plan, it is an instruction to take
    // the part out of the vise and put it back. It used to be pushed
    // unconditionally whenever the pattern was not MINIMUM_SETUPS, so a part
    // with no outside profile and no face mill in the crib produced a second
    // setup with zero operations — counted against the plan in setups and in
    // cycle time, and carrying a soft-jaw concern about gripping for a
    // operation that did not exist.
    if (ops2.length === 0) {
      concerns.push(
        "Nothing in this part needs a second setup: there is no outside profile to cut, and no face mill in the crib to bring the bottom to thickness. The plan stays in one setup, which leaves the bottom face and the outside as supplied.",
      );
    } else {

    // Raised here rather than alongside the grip calculation, so a setup that
    // gets dropped does not leave a concern behind warning about how hard it
    // grips.
    if (softJaws) {
      concerns.push(
        `Setup 2 grips ${grip.toFixed(3)}" on finished geometry. Soft jaws with a machined seat are the difference between repeatable and hopeful.`,
      );
    }

    setups.push({
      sequence: 2,
      name: "SETUP 2 — Flip, thickness and profile",
      orientation: "BOTTOM",
      /*
       * Rolled front to back, about X.
       *
       * The jaws hold the two faces perpendicular to X. Turning the part over
       * about that same axis keeps both of them in the jaws AND keeps the one
       * that was against the fixed jaw against it, which is what makes the
       * second setup's X repeat off the first. Turning it about Y would swap
       * them and hand the datum to the moving jaw.
       *
       * Every Y in the model mirrors as a result, and the program says so.
       */
      flipAxis: "X",
      workOffset: "G55",
      datumNote:
        "Located on the machined top face from Setup 1, seated on the soft jaw step. Rolled front to back about X, so the face that was against the fixed jaw stays against it — every Y on the model is mirrored in this setup.",
      gripDepth: grip,
      gripLength: Math.min(stock.x, jawWidth),
      stockProjection: Number((remaining - grip).toFixed(3)),
      requiresSoftJaws: softJaws,
      operations: ops2,
      rationale:
        pattern === "LOWEST_RISK"
          ? "Cutting soft jaws before this operation rather than discovering mid-cut that the grip was not enough."
          : "Second operation brings the part to thickness and cuts the finished profile.",
    });
    }
  } else {
    concerns.push(
      "Single setup leaves the bottom face and the outside profile as supplied. That is only acceptable if the stock is already to size and square.",
    );
  }

  /* ---- Global checks ---- */

  const minR = minimumInternalRadius(features);
  const smallest = tools.filter((t) => MILL_CLASSES.includes(t.toolClass)).sort((a, b) => a.diameter - b.diameter)[0];
  if (minR !== null && smallest && !fitsInternalCorner(smallest, minR)) {
    concerns.push(
      `The smallest mill in the crib is ⌀${smallest.diameter.toFixed(4)} but the part has an R${minR.toFixed(4)} internal corner. Either buy a ⌀${(minR * 2).toFixed(4)} cutter or open the corner.`,
    );
  }

  const deepest = maximumDepth(features, stock);
  if (pattern === "MINIMUM_SETUPS" && deepest > stock.z * 0.7) {
    concerns.push(
      `Reaching ${deepest.toFixed(3)}" from one side needs a long tool. Expect deflection on the wall and take the finish pass light.`,
    );
  }

  const toolNumbers = [...new Set(setups.flatMap((s) => s.operations.map((o) => o.toolNumber)).filter((n): n is number => n !== null))].sort(
    (a, b) => a - b,
  );

  return { pattern, philosophy, setups, toolNumbers, concerns, assumptions };
}

export function planAllApproaches(input: PlanInput): MachinistPlan[] {
  return THOUGHT_PATTERNS.map((p) => planApproach(p, input));
}

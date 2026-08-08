import type { Feature, Stock } from "@/lib/domain/features";
import { maximumDepth, minimumInternalRadius } from "@/lib/domain/features";
import type { MachineProfile, Tool, WorkholdingDevice } from "@/lib/domain/shop";
import { canReach, fitsInternalCorner } from "@/lib/domain/shop";
import type { OperationType } from "./cam/types";

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
  /** Why this machinist chose this tool and these numbers. */
  rationale: string;
}

export interface PlannedSetup {
  sequence: number;
  name: string;
  orientation: "TOP" | "BOTTOM";
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

/* ------------------------------------------------------------------ */
/* Feature classification                                              */
/* ------------------------------------------------------------------ */

interface Classified {
  faces: Feature[];
  pockets: Feature[];
  holes: Feature[];
  bores: Feature[];
  contours: Feature[];
  chamfers: Feature[];
  engravings: Feature[];
}

function classify(features: Feature[]): Classified {
  return {
    faces: features.filter((f) => f.kind === "FACE"),
    pockets: features.filter((f) => f.kind === "RECT_POCKET" || f.kind === "SLOT"),
    holes: features.filter((f) => f.kind === "DRILLED_HOLE" || f.kind === "TAPPED_HOLE"),
    bores: features.filter((f) => f.kind === "BORE" || f.kind === "CIRC_POCKET"),
    contours: features.filter((f) => f.kind === "OUTSIDE_CONTOUR"),
    chamfers: features.filter((f) => f.kind === "CHAMFER"),
    engravings: features.filter((f) => f.kind === "ENGRAVING"),
  };
}

const depthOf = (f: Feature, stock: Stock): number => {
  if ("through" in f && f.through) return stock.z;
  if ("depth" in f && typeof f.depth === "number") return f.depth;
  return 0;
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

  // Holes — spot then drill, unless the approach is minimising tool changes.
  const spot = findTool(tools, "SPOT_DRILL") ?? findTool(tools, "CENTER_DRILL");
  const drill = findTool(tools, "DRILL");
  if (c.holes.length > 0) {
    const spotWorthIt = pattern !== "MINIMUM_TOOLING" && pattern !== "FASTEST_CYCLE";
    if (spot && spotWorthIt) {
      ops1.push({
        sequence: seq++,
        type: "DRILL",
        label: `Spot ${c.holes.length} holes`,
        featureId: c.holes[0].id,
        toolId: spot.id,
        toolNumber: spot.toolNumber,
        topZ: 0,
        finalZ: -0.08,
        stepover: 0,
        stockToLeave: 0,
        rationale: "Spotting first stops the drill walking on entry, which is where hole position is won or lost.",
      });
    }
    if (drill) {
      const d = Math.max(...c.holes.map((h) => depthOf(h, stock)));
      const ratio = d / drill.diameter;
      ops1.push({
        sequence: seq++,
        type: ratio > 4 ? "PECK_DRILL" : "DRILL",
        label: `Drill ${c.holes.length} holes`,
        featureId: c.holes[0].id,
        toolId: drill.id,
        toolNumber: drill.toolNumber,
        topZ: 0,
        finalZ: -d,
        stepover: 0,
        stockToLeave: 0,
        rationale:
          ratio > 4
            ? `${ratio.toFixed(1)}:1 depth to diameter — pecking to clear chips rather than packing the flutes.`
            : `${ratio.toFixed(1)}:1 depth to diameter drills straight through without pecking.`,
      });
    } else {
      concerns.push("No drill in the crib — the holes cannot be produced.");
    }
  }

  // Bores — the feature most likely to carry a real tolerance.
  for (const f of c.bores) {
    const d = depthOf(f, stock);
    const diameter = "diameter" in f ? f.diameter : 0;
    const { tool, reason } = selectMill(tools, diameter / 2, d, prefer);
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

  // Chamfer
  const chamfer = findTool(tools, "CHAMFER_MILL");
  if (c.chamfers.length > 0 && chamfer) {
    ops1.push({
      sequence: seq++,
      type: "CHAMFER",
      label: "Chamfer top edges",
      featureId: c.chamfers[0].id,
      toolId: chamfer.id,
      toolNumber: chamfer.toolNumber,
      topZ: 0,
      finalZ: -0.03,
      stepover: 0,
      stockToLeave: 0,
      rationale: "Breaking edges on the machine is cheaper than a deburring bench and far more consistent.",
    });
  }

  const setups: PlannedSetup[] = [
    {
      sequence: 1,
      name: "SETUP 1 — Top face and features",
      orientation: "TOP",
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
        featureId: c.faces[0]?.id ?? null,
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
      const d = "depth" in f ? f.depth : stock.z;
      const { tool, reason } = selectMill(tools, cr, d, prefer);
      if (!tool) {
        concerns.push(`${f.label}: ${reason}`);
        continue;
      }
      ops2.push({
        sequence: s2++,
        type: "CONTOUR_2D",
        label: `${separateFinish ? "Rough " : "Finish "}${f.label}`,
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
            rationale: "Spring pass at full depth for a consistent wall finish.",
          });
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

    if (softJaws) {
      concerns.push(
        `Setup 2 grips ${grip.toFixed(3)}" on finished geometry. Soft jaws with a machined seat are the difference between repeatable and hopeful.`,
      );
    }

    setups.push({
      sequence: 2,
      name: "SETUP 2 — Flip, thickness and profile",
      orientation: "BOTTOM",
      workOffset: "G55",
      datumNote: "Located on the machined top face from Setup 1, seated on the soft jaw step.",
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

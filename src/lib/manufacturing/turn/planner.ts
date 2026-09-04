import { intersectSfm } from "@/lib/engines/cam/engine";
import { parseThreadPitch } from "@/lib/engines/cam/engine";
import type { ProfileSegment, RotationalProfile } from "./geometry";
import type { TurnCutParams, TurnOperation, TurnOperationType } from "./operations";

/**
 * THE TURNING PLANNER — operations derived from a profile, or a refusal.
 *
 * `RotationalPart.planJson` was written by `prisma/seed.ts` and by nothing
 * else. Every rotational part created through the reverse-engineering flow —
 * the one path a shop actually uses to get a turned part into CANVAS — had an
 * empty plan, so it had no toolpaths, no cycle time, no cost, and a Tooling
 * gate that could never pass.
 *
 * WHAT THIS IS NOT
 *
 * It is not a CAM system and it is not a model. There are no model calls here
 * and there must never be any: this file generates machine motion's inputs,
 * and principle 6 puts that on the far side of a line an LLM does not cross.
 * It is arithmetic over the profile and the crib.
 *
 * IT REFUSES RATHER THAN GUESSING
 *
 * Speeds and feeds come from the intersection of the tool's rated window and
 * the material's, through `intersectSfm` — the same function the mill uses, so
 * the two cannot drift apart on how fast to run. With no material on file
 * there are no speeds and no plan, which is the rule `generateToolpath`
 * already applies to milling: a carbide-in-steel window applied to whatever is
 * in the chuck reads as a plausible S-number and is six times too fast for
 * Inconel.
 *
 * Every operation it cannot plan is named with the reason. A plan that quietly
 * skipped the bore it could not reach would be worse than no plan, because the
 * cycle time and the cost would both look complete.
 */

/** A crib tool, in the shape the planner needs. */
export interface PlannerTool {
  station: string;
  toolClass: string;
  description: string;
  surfaceSpeedMin: number | null;
  surfaceSpeedMax: number | null;
  feedPerRevMin: number | null;
  feedPerRevMax: number | null;
  maxDepthOfCut: number | null;
  grooveWidth: number | null;
  minBoreDiameter: number | null;
  noseRadius: number | null;
}

export interface TurnPlanInput {
  profile: RotationalProfile;
  tools: PlannerTool[];
  /** Material surface-speed window, carbide. Null when nothing is on file. */
  materialSfmMin: number | null;
  materialSfmMax: number | null;
  materialName: string | null;
  /** The chuck's RPM ceiling, when one is recorded. */
  chuckMaxRpm: number | null;
}

export interface TurnPlanResult {
  operations: TurnOperation[];
  /** Geometry the planner would not plan, and why. */
  refusals: string[];
  /** Choices a machinist should look at before running it. */
  assumptions: string[];
}

/**
 * Stock left on the diameter for the finishing pass, inches.
 *
 * A planning convention, not a measurement — it is stated in the plan's own
 * assumptions so a machinist can change it. Nothing downstream treats it as
 * an engineering fact about the part.
 */
export const FINISH_ALLOWANCE = 0.02;

/** Roughing depth of cut when the crib records no ceiling for the tool. */
export const FALLBACK_ROUGH_DOC = 0.05;

const TOOL_FOR: Record<string, string> = {
  FACE: "FACING",
  OD_ROUGH: "OD_ROUGHING",
  OD_FINISH: "OD_FINISHING",
  ID_BORE_ROUGH: "BORING_BAR",
  ID_BORE_FINISH: "BORING_BAR",
  GROOVE_OD: "GROOVING",
  THREAD_OD: "THREADING",
  PART_OFF: "PARTING",
};

/**
 * Speeds and feeds for one cut, or null with the reason.
 *
 * The RPM is computed at the diameter the cut actually happens on, which is
 * what constant surface speed means on a lathe — the same 400 SFM is 764 rpm
 * on a 2" bar and 1528 on a 1" one.
 */
function paramsFor(
  tool: PlannerTool,
  input: TurnPlanInput,
  diameter: number,
  finishing: boolean,
): { params: TurnCutParams; outsideToolWindow: boolean } | { refusal: string } {
  if (input.materialSfmMin === null || input.materialSfmMax === null) {
    return {
      refusal: `No surface speed window on file for ${input.materialName || "this material"}. Speeds and feeds are not derivable without it, and CANVAS will not substitute another material's numbers.`,
    };
  }
  if (tool.surfaceSpeedMin === null || tool.surfaceSpeedMax === null) {
    return { refusal: `${tool.description} (T${tool.station}) has no surface speed recorded in the crib.` };
  }
  if (tool.feedPerRevMin === null || tool.feedPerRevMax === null) {
    return { refusal: `${tool.description} (T${tool.station}) has no feed per revolution recorded in the crib.` };
  }
  if (!(diameter > 0)) {
    return { refusal: `A cut at ⌀${diameter} has no surface speed — the diameter must be positive.` };
  }

  /*
   * Where the tool's rated window and the material's do not overlap, the
   * MATERIAL wins on a lathe. Surface speed in turning is a property of the
   * workpiece: an insert rated 500-1100 SFM is rated across the materials it
   * might see, and in 4140 you run at 4140's speed. Running the insert at its
   * own rating burns it.
   *
   * This is the opposite of what the mill does with the same non-overlap, and
   * deliberately so — see `intersectSfm`. Taking the milling fallback here ran
   * a finishing insert at 800 SFM in a steel quoted 250-450.
   */
  const overlap = intersectSfm(tool.surfaceSpeedMin, tool.surfaceSpeedMax, input.materialSfmMin, input.materialSfmMax);
  const sfm = overlap ?? (input.materialSfmMin + input.materialSfmMax) / 2;
  const rawRpm = (sfm * 12) / (Math.PI * diameter);
  // The chuck's ceiling is a real limit and the G50 clamp is what enforces it.
  // Without one recorded there is no ceiling to apply, and the analysis says so
  // separately rather than this inventing one.
  const rpm = Math.round(input.chuckMaxRpm != null ? Math.min(rawRpm, input.chuckMaxRpm) : rawRpm);

  // Roughing takes the top of the recorded feed range and finishing the
  // bottom: the range is the shop's own, and which end suits which cut is not
  // a judgement about this part.
  const feedPerRev = finishing ? tool.feedPerRevMin : tool.feedPerRevMax;

  return {
    outsideToolWindow: overlap === null,
    params: {
      feedPerRev,
      surfaceSpeed: sfm,
      rpm,
      cssEnabled: true,
      doc: finishing ? FINISH_ALLOWANCE : (tool.maxDepthOfCut ?? FALLBACK_ROUGH_DOC),
      finishAllowance: finishing ? 0 : FINISH_ALLOWANCE,
      springPasses: finishing ? 1 : 0,
      coolant: "FLOOD",
    },
  };
}

const externalCuts = (p: RotationalProfile) =>
  p.segments.filter((s) => !s.internal && s.kind !== "GROOVE" && s.kind !== "THREAD" && s.kind !== "CUTOFF");

/**
 * Plan a turned part.
 *
 * The sequence is the ordinary one for chucked bar work: face the front, rough
 * the whole OD envelope, open and finish any bore while the part is stiff and
 * fully supported, finish the OD, then the features that cut into a finished
 * surface — grooves, then threads — and part off last.
 *
 * Bores come before the OD finish because a boring bar pushing outward will
 * mark an OD that is already on size, and because the part is at its stiffest
 * before material comes off the outside. A machinist who orders it differently
 * is not wrong; the plan is a starting point and the workspace supports
 * disagreeing with it.
 */
export function planTurning(input: TurnPlanInput): TurnPlanResult {
  const { profile, tools } = input;
  const operations: TurnOperation[] = [];
  const refusals: string[] = [];
  const assumptions: string[] = [
    `Roughing leaves ${FINISH_ALLOWANCE.toFixed(3)}" on the diameter for the finishing pass. That is a planning convention, not a measurement.`,
    "Surface speed is the overlap of the tool's rated window and the material's, at the diameter each cut runs on. Feed is the top of the tool's recorded range for roughing and the bottom for finishing.",
    "The sequence is chucked bar work: face, rough OD, bore, finish OD, groove, thread, part off. Bores are cut before the OD is finished so a boring bar cannot mark a diameter already on size.",
  ];

  const toolFor = (opType: TurnOperationType): PlannerTool | null =>
    tools.find((t) => t.toolClass === TOOL_FOR[opType]) ?? null;

  let n = 0;
  const nextNumber = () => (n += 10);

  /** Tools being run outside their own rated window because the material governs. */
  const outsideWindow = new Set<string>();

  /** Adds an operation, or records why it could not be planned. */
  const emit = (
    type: TurnOperationType,
    label: string,
    seg: ProfileSegment | null,
    geom: { startZ: number; endZ: number; startDiameter: number; endDiameter: number },
    speedDiameter: number,
    finishing: boolean,
  ) => {
    const tool = toolFor(type);
    if (!tool) {
      refusals.push(`${label}: the crib records no ${(TOOL_FOR[type] ?? type).replace(/_/g, " ").toLowerCase()} tool.`);
      return;
    }
    const p = paramsFor(tool, input, speedDiameter, finishing);
    if ("refusal" in p) {
      refusals.push(`${label}: ${p.refusal}`);
      return;
    }
    if (p.outsideToolWindow) outsideWindow.add(`${tool.description} (T${tool.station})`);
    operations.push({
      operationNumber: nextNumber(),
      type,
      label,
      toolStation: tool.station,
      targetSegmentId: seg?.id ?? null,
      ...geom,
      params: p.params,
    });
  };

  const cuts = externalCuts(profile);
  if (cuts.length === 0 && profile.segments.length === 0) {
    return {
      operations: [],
      refusals: ["The profile has no segments, so there is nothing to plan."],
      assumptions: [],
    };
  }

  const finishedLength = cuts.length > 0 ? Math.max(...cuts.map((s) => s.zEnd)) : 0;
  const largestOd = cuts.length > 0 ? Math.max(...cuts.map((s) => Math.max(s.diameterStart, s.diameterEnd))) : 0;

  if (largestOd > profile.stockDiameter) {
    refusals.push(
      `The profile's largest diameter is ⌀${largestOd.toFixed(4)} and the stock is ⌀${profile.stockDiameter.toFixed(4)}. There is nothing to cut this from.`,
    );
    return { operations: [], refusals, assumptions: [] };
  }

  /* ---- Face the front ---- */
  emit(
    "FACE",
    "Face front",
    null,
    { startZ: 0.05, endZ: 0, startDiameter: profile.stockDiameter, endDiameter: 0 },
    profile.stockDiameter,
    false,
  );

  /* ---- Rough the OD envelope ---- */
  if (cuts.length > 0) {
    emit(
      "OD_ROUGH",
      `Rough OD to ⌀${(largestOd + FINISH_ALLOWANCE).toFixed(4)} envelope`,
      null,
      {
        startZ: 0,
        endZ: finishedLength,
        startDiameter: profile.stockDiameter,
        endDiameter: largestOd + FINISH_ALLOWANCE,
      },
      profile.stockDiameter,
      false,
    );
  }

  /* ---- Bores, while the part is stiff ---- */
  const bores = profile.segments.filter((s) => s.internal && s.kind !== "GROOVE" && s.kind !== "THREAD");
  for (const b of bores) {
    const bore = Math.min(b.diameterStart, b.diameterEnd);
    const bar = tools.find((t) => t.toolClass === "BORING_BAR");
    if (bar && bar.minBoreDiameter != null && bore < bar.minBoreDiameter) {
      refusals.push(
        `${b.label}: ⌀${bore.toFixed(4)} is smaller than the ⌀${bar.minBoreDiameter.toFixed(3)} minimum bore of ${bar.description} (T${bar.station}). The bar will not fit the hole.`,
      );
      continue;
    }
    emit(
      "ID_BORE_ROUGH",
      `Rough bore ${b.label}`,
      b,
      { startZ: b.zStart, endZ: b.zEnd, startDiameter: bore - FINISH_ALLOWANCE, endDiameter: bore - FINISH_ALLOWANCE },
      bore,
      false,
    );
    emit(
      "ID_BORE_FINISH",
      `Finish bore ${b.label}`,
      b,
      { startZ: b.zStart, endZ: b.zEnd, startDiameter: b.diameterStart, endDiameter: b.diameterEnd },
      bore,
      true,
    );
  }

  /* ---- Finish the OD, one pass per segment ---- */
  for (const s of cuts) {
    emit(
      "OD_FINISH",
      `Finish ${s.label}`,
      s,
      { startZ: s.zStart, endZ: s.zEnd, startDiameter: s.diameterStart, endDiameter: s.diameterEnd },
      Math.max(s.diameterStart, s.diameterEnd),
      true,
    );
  }

  /* ---- Grooves ---- */
  for (const g of profile.segments.filter((s) => s.kind === "GROOVE")) {
    const width = Math.abs(g.zEnd - g.zStart);
    const grooveTool = tools.find((t) => t.toolClass === "GROOVING");
    if (grooveTool && grooveTool.grooveWidth != null && width < grooveTool.grooveWidth - 1e-9) {
      refusals.push(
        `${g.label}: the groove is ${width.toFixed(4)}" wide and the narrowest grooving tool on file is ${grooveTool.grooveWidth.toFixed(4)}". It will not fit.`,
      );
      continue;
    }
    emit(
      g.internal ? "GROOVE_ID" : "GROOVE_OD",
      `Groove ${g.label}`,
      g,
      { startZ: g.zStart, endZ: g.zEnd, startDiameter: g.diameterStart, endDiameter: g.diameterEnd },
      Math.max(g.diameterStart, g.diameterEnd),
      true,
    );
  }

  /* ---- Threads ---- */
  for (const t of profile.segments.filter((s) => s.kind === "THREAD")) {
    if (!t.thread) {
      refusals.push(`${t.label}: the segment is a thread but carries no designation, so there is no pitch to cut.`);
      continue;
    }
    const pitch = parseThreadPitch(t.thread);
    if (pitch === null) {
      refusals.push(`${t.label}: "${t.thread}" is not a designation CANVAS can read a pitch from.`);
      continue;
    }
    const tool = toolFor("THREAD_OD");
    if (!tool) {
      refusals.push(`${t.label}: the crib records no threading tool.`);
      continue;
    }
    const p = paramsFor(tool, input, Math.max(t.diameterStart, t.diameterEnd), true);
    if ("refusal" in p) {
      refusals.push(`${t.label}: ${p.refusal}`);
      continue;
    }
    operations.push({
      operationNumber: nextNumber(),
      type: t.internal ? "THREAD_ID" : "THREAD_OD",
      label: `Thread ${t.thread}`,
      toolStation: tool.station,
      targetSegmentId: t.id,
      startZ: t.zStart,
      endZ: t.zEnd,
      startDiameter: t.diameterStart,
      endDiameter: t.diameterEnd,
      // On a thread the feed per revolution IS the pitch. Taking it from the
      // tool's finishing range would cut a thread of the wrong lead.
      params: { ...p.params, feedPerRev: pitch, cssEnabled: false, surfaceSpeed: null },
    });
  }

  /* ---- Part off ---- */
  if (profile.barStock && cuts.length > 0) {
    emit(
      "PART_OFF",
      `Part off at Z${finishedLength.toFixed(3)}`,
      profile.segments.find((s) => s.kind === "CUTOFF") ?? null,
      { startZ: finishedLength, endZ: finishedLength, startDiameter: largestOd, endDiameter: 0 },
      largestOd,
      true,
    );
  } else if (!profile.barStock) {
    assumptions.push(
      "The stock is not bar, so no part-off is planned — the back end comes off in a second operation nobody has planned yet.",
    );
  }

  if (outsideWindow.size > 0) {
    assumptions.push(
      `${[...outsideWindow].join(", ")} ${outsideWindow.size === 1 ? "is" : "are"} run at the material's surface speed rather than the tool's own rated window — the two do not overlap, and on a lathe the workpiece governs. Check the insert grade suits ${input.materialName ?? "this material"}.`,
    );
  }

  return { operations, refusals, assumptions };
}

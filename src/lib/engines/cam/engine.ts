import type { Feature, Stock } from "@/lib/domain/features";
import { canReach, fitsInternalCorner } from "@/lib/domain/shop";
import type {
  CannedCycle,
  CuttingParameters,
  MachiningContext,
  Move,
  OperationRequest,
  Toolpath,
  ToolpathError,
  ToolpathResult,
} from "./types";
import { IMPLEMENTED_OPERATIONS, PLACEHOLDER_OPERATIONS } from "./types";
import { arcGeometry, arcMove, arcSegments } from "./arc";
import { chainLength, chainMoves, offsetChain, rectangleChain, type Chain } from "./chain";
import { chamferEdge, chamferGeometry } from "./chamfer";
import { annulusOf, islandsIn } from "./island";
import { parseThread, parseThreadMajor, parseThreadPitch, sameThread, threadMinor } from "./thread";

/**
 * DETERMINISTIC TOOLPATH ENGINE — Phase 1
 *
 * Every move in here is arithmetic on the parametric feature model. There is
 * no inference, no sampling, and no model call anywhere in this file, by
 * design. It is a prototype engine covering the 2.5D envelope; it is not a
 * production CAM kernel, and everything it emits is labelled
 * DEVELOPMENT / SIMULATION ONLY until a verified kernel replaces it.
 *
 * The public surface — `generateToolpath(request, feature, context, stock)` —
 * is the seam a production kernel drops into.
 */

/* ------------------------------------------------------------------ */
/* Speeds and feeds                                                    */
/* ------------------------------------------------------------------ */

/** A context whose material window is known. See generateToolpath's refusal. */
export type CuttableContext = MachiningContext & { materialSfmMin: number; materialSfmMax: number };

export function deriveCuttingParameters(
  ctx: CuttableContext,
  overrides: Partial<CuttingParameters> = {},
  finishing = false,
): CuttingParameters {
  const { tool } = ctx;

  /*
   * The intersection of the tool's rated window and the material's.
   *
   * Where they overlap — which generateToolpath requires of a milling
   * cutter — the midpoint of the intersection is the answer, and the old
   * clamp to the union was a no-op on it.
   *
   * Where they do NOT overlap, the old expression was not: `max(toolMin,
   * matMin)` and `min(toolMax, matMax)` cross over, and their average is a
   * number strictly between the two windows and inside neither. A ⌀0.25 tap
   * rated 30-60 SFM, in aluminium quoted 600-1000, came out at 330 SFM —
   * eleven thousand rpm before the tapping cap caught it. Those are the
   * tools whose speed is not set by the material's milling window at all,
   * so the tool's own rating wins: it is the rating that belongs to the
   * thing doing the cutting.
   */
  // No overlap: the tool's own rating wins. `max(toolMin, matMin)` and
  // `min(toolMax, matMax)` cross over there, and their average is a number
  // strictly between the two windows and inside neither — a ⌀0.25 tap rated
  // 30-60 SFM, in aluminium quoted 600-1000, came out at 330 SFM.
  const sfm =
    intersectSfm(tool.sfmMin, tool.sfmMax, ctx.materialSfmMin, ctx.materialSfmMax) ??
    clamp((tool.sfmMin + tool.sfmMax) / 2, tool.sfmMin, tool.sfmMax);

  const rawRpm = (sfm * 12) / (Math.PI * tool.diameter);
  const rpm = Math.round(clamp(rawRpm, 100, Math.min(tool.maxRPM, ctx.maxSpindleRPM)));

  const chipload = finishing
    ? tool.chiploadMin
    : (tool.chiploadMin + tool.chiploadMax) / 2;

  const feed = Math.round(clamp(rpm * tool.flutes * chipload, 1, ctx.maxFeed));

  return {
    rpm,
    feed,
    plungeFeed: Math.round(feed * 0.35),
    stepdown: finishing ? tool.diameter * 0.5 : tool.diameter * 0.5,
    stepover: finishing ? 0.1 : 0.45,
    sfm: Number(sfm.toFixed(0)),
    chipload: Number(chipload.toFixed(4)),
    coolant: "FLOOD",
    stockToLeave: finishing ? 0 : 0.01,
    ...overrides,
  };
}

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

/**
 * Surface speed where the tool's rated window and the material's overlap, or
 * NULL when they do not.
 *
 * Exported because the turning planner needs the intersection and a second
 * copy of it would eventually disagree with the mill about how fast to run.
 *
 * WHAT IS DELIBERATELY NOT SHARED is what to do when the windows miss each
 * other, because that is not one rule. Milling falls back to the tool's own
 * rating: the tools that land here are taps and the like, whose speed is set
 * by the operation rather than by the material's milling window. Turning does
 * the opposite and falls back to the material, because surface speed in
 * turning is a property of the workpiece — an insert "rated 500-1100 SFM" is
 * rated across the materials it might see, and in 4140 you run at 4140's
 * speed. Applying the milling fallback to a turning finish pass ran a carbide
 * insert at 800 SFM in a steel quoted 250-450, which burns the insert.
 *
 * Returning null makes each caller state its own answer instead of inheriting
 * one written for the other machine.
 */
export function intersectSfm(toolMin: number, toolMax: number, materialMin: number, materialMax: number): number | null {
  const lo = Math.max(toolMin, materialMin);
  const hi = Math.min(toolMax, materialMax);
  return lo <= hi ? (lo + hi) / 2 : null;
}

/* ------------------------------------------------------------------ */
/* Entry point                                                         */
/* ------------------------------------------------------------------ */

export function generateToolpath(
  req: OperationRequest,
  feature: Feature | null,
  ctx: MachiningContext,
  stock: Stock,
): ToolpathResult {
  /*
   * No material record, no speeds and feeds.
   *
   * Surface speed is what sets the spindle, and the window used to default
   * to 300-800 SFM when the shop had no record of the material — a carbide
   * -in-steel window applied to whatever was in the vise. Inconel 718 cuts
   * at roughly 60-100 SFM with carbide; the default is six times that, and
   * the operator would have read a plausible S-number in the program.
   */
  if (ctx.materialSfmMin === null || ctx.materialSfmMax === null) {
    return {
      ok: false,
      error: {
        operationId: req.id,
        reason: `No surface speed window on file for ${ctx.materialName || "this material"}. Speeds and feeds are not derivable without it, and CANVAS will not substitute another material's numbers.`,
        recommendations: [
          `Add ${ctx.materialName || "the material"} to the material library with its carbide SFM window`,
          "Check the material named on the part matches a library record",
        ],
      },
    };
  }
  const cuttable = ctx as CuttableContext;

  /*
   * The tool's rated window and the material's must actually overlap.
   *
   * Scoped to the peripheral-milling classes on purpose: the material record's
   * SFM window is a MILLING window. A tap runs at a fraction of it by design
   * (this engine caps rigid tapping at 800 rpm and locks the feed to the
   * thread), and a drill's rated speed is a property of the drill. Applying
   * the overlap test to those would refuse operations that are correct.
   *
   * Where the windows genuinely do not overlap for a milling cutter, this
   * tool is not rated for this material — and averaging the two windows'
   * endpoints produced a surface speed belonging to neither.
   */
  const SURFACE_SPEED_MILLING = ["FACE_MILL", "FLAT_END_MILL", "BALL_END_MILL", "BULL_NOSE", "SHELL_MILL", "CHAMFER_MILL"];
  if (
    SURFACE_SPEED_MILLING.includes(ctx.tool.toolClass) &&
    (ctx.tool.sfmMin > cuttable.materialSfmMax || ctx.tool.sfmMax < cuttable.materialSfmMin)
  ) {
    return {
      ok: false,
      error: {
        operationId: req.id,
        reason: `${ctx.tool.description} is rated ${ctx.tool.sfmMin}-${ctx.tool.sfmMax} SFM and ${ctx.materialName} cuts at ${cuttable.materialSfmMin}-${cuttable.materialSfmMax} SFM. The windows do not overlap — this tool is not rated for this material.`,
        recommendations: [
          `Select a tool rated at or below ${cuttable.materialSfmMax} SFM`,
          "Confirm the material record against the supplier's data",
        ],
      },
    };
  }

  /*
   * Finishing is a property of the OPERATION, not a guess from its type.
   *
   * This used to be `type === "CHAMFER" || type === "ENGRAVE"` — so an
   * operation the planner labelled "Finish outside profile" got roughing
   * parameters: mid-range chipload, roughing stepdown, a depth ladder that
   * leaves a witness line at every step. The label said finish and the numbers
   * said rough.
   */
  const finishing = req.pass === "FINISH" || req.type === "CHAMFER" || req.type === "ENGRAVE";
  const params = deriveCuttingParameters(cuttable, req.overrides, finishing);
  const warnings: string[] = [];

  /* ---- Hard validation before any motion is produced ---- */
  const depth = Math.abs(req.finalZ - req.topZ);
  if (!canReach(ctx.tool, depth)) {
    return {
      ok: false,
      error: {
        operationId: req.id,
        reason: `${ctx.tool.description} has ${ctx.tool.stickout.toFixed(3)}" of stickout and cannot reach the ${depth.toFixed(3)}" depth of ${req.label}.`,
        recommendations: [
          "Increase tool stickout in the holder",
          "Select a longer-reach tool",
          "Split the operation across two setups",
        ],
      },
    };
  }

  if (feature && feature.kind === "RECT_POCKET") {
    // Corner radius vs tool radius is the classic un-machinable condition.
    const cr = feature.cornerRadius;
    if (cr > 0 && !fitsInternalCorner(ctx.tool, cr)) {
      return {
        ok: false,
        error: {
          operationId: req.id,
          reason: `Selected ${ctx.tool.diameter.toFixed(4)}" end mill cannot produce the R${cr.toFixed(4)} internal corner in ${feature.label}.`,
          recommendations: [
            `Use a tool ⌀${(cr * 2).toFixed(4)}" or smaller`,
            `Increase the corner radius to R${(ctx.tool.diameter / 2).toFixed(4)} or larger`,
            "Add a corner relief to the geometry",
          ],
        },
      };
    }
  }

  if (PLACEHOLDER_OPERATIONS.includes(req.type)) {
    return {
      ok: true,
      toolpath: {
        operationId: req.id,
        setupId: req.setupId,
        type: req.type,
        toolId: req.toolId,
        toolNumber: ctx.tool.toolNumber,
        moves: [],
        parameters: params,
        cycleTimeMinutes: 0,
        materialRemoved: 0,
        cuttingDistance: 0,
        warnings: [
          `${req.type} has an interface defined but no toolpath engine in Phase 1. No motion has been generated.`,
        ],
        isPlaceholder: true,
      },
    };
  }

  if (!IMPLEMENTED_OPERATIONS.includes(req.type)) {
    return {
      ok: false,
      error: {
        operationId: req.id,
        reason: `Operation type ${req.type} is not supported by the Phase 1 toolpath engine.`,
        recommendations: ["Select a supported operation type"],
      },
    };
  }

  let moves: Move[] = [];
  let removed = 0;
  let cannedCycle: CannedCycle | undefined;

  switch (req.type) {
    case "FACE": {
      const r = faceToolpath(req, ctx, stock, params);
      moves = r.moves;
      removed = r.removed;
      break;
    }
    case "POCKET_2D":
    case "SOFT_JAW_POCKET": {
      if (!feature) return missingFeature(req);
      const r = pocketToolpath(req, feature, ctx, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      break;
    }
    case "ADAPTIVE_2D": {
      if (!feature) return missingFeature(req);
      const r = adaptiveToolpath(req, feature, ctx, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      break;
    }
    case "DRILL":
    case "PECK_DRILL": {
      if (!feature) return missingFeature(req);
      const r = drillToolpath(req, feature, ctx, params, req.type === "PECK_DRILL");
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      cannedCycle = r.cycle;
      break;
    }
    case "BORE": {
      if (!feature) return missingFeature(req);
      const r = boreToolpath(req, feature, ctx, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      break;
    }
    case "TAP": {
      if (!feature) return missingFeature(req);
      const r = tapToolpath(req, feature, ctx, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      cannedCycle = r.cycle;
      break;
    }
    case "CONTOUR_2D": {
      if (!feature) return missingFeature(req);
      const r = contourToolpath(req, feature, ctx, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      break;
    }
    case "THREAD_MILL": {
      if (!feature) return missingFeature(req);
      const r = threadMillToolpath(req, feature, ctx, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      break;
    }
    case "STEP_MILL": {
      if (!feature) return missingFeature(req);
      const r = stepToolpath(req, feature, ctx, stock, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      break;
    }
    case "SLOT_MILL": {
      if (!feature) return missingFeature(req);
      const r = slotToolpath(req, feature, ctx, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      break;
    }
    case "COUNTERBORE":
    case "COUNTERSINK": {
      if (!feature) return missingFeature(req);
      const r = headToolpath(req, feature, ctx, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      break;
    }
    case "CHAMFER": {
      if (!feature) return missingFeature(req);
      const r = chamferToolpath(req, feature, ctx, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      warnings.push(...r.warnings);
      break;
    }
    case "ENGRAVE": {
      if (!feature) return missingFeature(req);
      const r = engraveToolpath(req, feature, ctx, params);
      moves = r.moves;
      removed = r.removed;
      break;
    }
  }

  const { minutes, cuttingDistance } = cycleTime(moves, ctx.rapidRate);

  if (params.rpm >= ctx.maxSpindleRPM) {
    warnings.push(
      `Speed is clamped at the machine limit of ${ctx.maxSpindleRPM} RPM. Surface speed is below the ideal window for this tool and material.`,
    );
  }
  if (minutes > 30) {
    warnings.push(`Estimated ${minutes.toFixed(1)} min cycle for a single operation — review stepover and stepdown.`);
  }

  return {
    ok: true,
    toolpath: {
      operationId: req.id,
      setupId: req.setupId,
      type: req.type,
      toolId: req.toolId,
      toolNumber: ctx.tool.toolNumber,
      moves,
      parameters: params,
      cycleTimeMinutes: minutes,
      materialRemoved: Number(removed.toFixed(4)),
      cuttingDistance: Number(cuttingDistance.toFixed(2)),
      warnings,
      isPlaceholder: false,
      ...(cannedCycle ? { cannedCycle } : {}),
    },
  };
}

const missingFeature = (req: OperationRequest): ToolpathResult => ({
  ok: false,
  error: {
    operationId: req.id,
    reason: `${req.label} is not linked to a geometry feature, so no toolpath can be generated.`,
    recommendations: ["Link the operation to a feature in the feature tree"],
  },
});

/* ------------------------------------------------------------------ */
/* FACE — zig-zag across the stock                                     */
/* ------------------------------------------------------------------ */

function faceToolpath(
  req: OperationRequest,
  ctx: MachiningContext,
  stock: Stock,
  p: CuttingParameters,
): { moves: Move[]; removed: number } {
  const moves: Move[] = [];
  const d = ctx.tool.diameter;
  const stepover = d * 0.7; // face mills run heavier stepover than end mills
  const halfX = stock.x / 2;
  const halfY = stock.y / 2;
  const lead = d * 0.6; // roll on and off the material

  const totalDepth = req.topZ - req.finalZ;
  const passes = Math.max(1, Math.ceil(totalDepth / p.stepdown));

  moves.push({ type: "RAPID", x: -halfX - lead, y: -halfY + d / 2, z: req.clearanceZ, feed: null });

  let prevZ = req.topZ;
  for (let pass = 1; pass <= passes; pass++) {
    const z = req.topZ - (totalDepth * pass) / passes;
    let y = -halfY + d / 2;
    let dir = 1;
    moves.push({ type: "RAPID", x: -halfX - lead, y, z: req.clearanceZ, feed: null });
    moves.push({ type: "PLUNGE", x: -halfX - lead, y, z, feed: p.plungeFeed });

    while (y <= halfY - d / 2 + 1e-6) {
      const xStart = dir > 0 ? -halfX - lead : halfX + lead;
      const xEnd = dir > 0 ? halfX + lead : -halfX - lead;
      moves.push({ type: "CUT", x: xStart, y, z, feed: p.feed });
      moves.push({ type: "CUT", x: xEnd, y, z, feed: p.feed });
      y += stepover;
      dir *= -1;
      if (y <= halfY - d / 2 + 1e-6) {
        moves.push({ type: "CUT", x: xEnd, y, z, feed: p.feed });
      }
    }
    moves.push({ type: "RETRACT", x: moves[moves.length - 1].x, y: moves[moves.length - 1].y, z: req.retractZ, feed: null });
  }

  return { moves, removed: stock.x * stock.y * totalDepth };
}

/* ------------------------------------------------------------------ */
/* 2D POCKET — offset-inward roughing plus a finish wall pass          */
/* ------------------------------------------------------------------ */

function pocketToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
  const warnings: string[] = [];
  const d = ctx.tool.diameter;
  const r = d / 2;
  const moves: Move[] = [];

  let cx = 0,
    cy = 0,
    width = 0,
    length = 0,
    cornerR = 0,
    circular = false,
    diameter = 0;

  if (feature.kind === "RECT_POCKET") {
    cx = feature.centerX;
    cy = feature.centerY;
    width = feature.width;
    length = feature.length;
    cornerR = feature.cornerRadius;
  } else if (feature.kind === "CIRC_POCKET" || feature.kind === "BORE") {
    circular = true;
    cx = feature.centerX;
    cy = feature.centerY;
    diameter = feature.diameter;
  } else {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind} and cannot be machined with a 2D pocket operation.`,
        recommendations: ["Select a pocket or bore feature", "Change the operation type"],
      },
    };
  }

  /*
   * ANYTHING STANDING IN THIS POCKET.
   *
   * A pocket toolpath sweeps its whole area, so a boss inside one is machined
   * away — on a 3.000 × 2.000 pocket with a ⌀0.750 boss at its centre, a third
   * of the moves were inside the boss and the helical entry started at the
   * boss's own centre. Nothing said a word.
   *
   * A circular island concentric in a circular pocket is an annulus and needs
   * no clipping at all. Every other arrangement needs island avoidance, which
   * this engine does not have, and it is refused by name.
   */
  const islands = islandsIn(feature, ctx.partFeatures);
  let inner = 0;
  if (islands.length > 1) {
    return {
      error: {
        reason: `${feature.label} has ${islands.length} features standing in it — ${islands.map((f) => f.label).join(", ")}. A pocket toolpath sweeps its whole area, so it would machine all of them away. Cutting around more than one island needs island avoidance, which this engine does not have.`,
        recommendations: [
          "Machine this pocket as separate pockets between the islands",
          "Record the islands as not made by this program if another operation produces them",
        ],
      },
    };
  }
  if (islands.length === 1) {
    const ring = annulusOf(feature, islands[0]);
    if (!ring) {
      return {
        error: {
          reason: `${islands[0].label} stands inside ${feature.label}, and a pocket toolpath sweeps its whole area — this path would machine it away. Only a round island concentric in a round pocket can be cut without island avoidance, which this engine does not have.`,
          recommendations: [
            `Make ${feature.label} a round pocket concentric with ${islands[0].label}, if that is what the part is`,
            "Machine the area around the island as separate pockets",
            `Record ${islands[0].label} as not made by this program if another operation produces it`,
          ],
        },
      };
    }
    inner = ring.innerDiameter;
  }

  if (circular && diameter <= d) {
    return {
      error: {
        reason: `⌀${diameter.toFixed(4)} pocket is not larger than the ⌀${d.toFixed(4)} tool — there is no room to move.`,
        recommendations: [`Use a tool smaller than ⌀${diameter.toFixed(4)}`, "Drill and bore this feature instead"],
      },
    };
  }
  if (!circular && (width <= d || length <= d)) {
    return {
      error: {
        reason: `${width.toFixed(3)} × ${length.toFixed(3)} pocket is too small for the ⌀${d.toFixed(4)} tool.`,
        recommendations: [`Use a tool smaller than ⌀${Math.min(width, length).toFixed(4)}`, "Machine as a slot"],
      },
    };
  }

  const totalDepth = req.topZ - req.finalZ;
  const passes = Math.max(1, Math.ceil(totalDepth / p.stepdown));
  const stepover = d * p.stepover;
  const leave = p.stockToLeave;

  moves.push({ type: "RAPID", x: cx, y: cy, z: req.clearanceZ, feed: null });

  // Each pass helixes down from the previous depth, not from the top: the
  // material above it is already gone.
  let prevZ = req.topZ;
  for (let pass = 1; pass <= passes; pass++) {
    const z = req.topZ - (totalDepth * pass) / passes;

    if (circular) {
      // Helical entry at centre, then concentric rings outward. The helix
      // must fit inside the finished wall, less the tool radius.
      /*
       * With an island there is material at the centre, so the helix goes in
       * the band on the mid-radius rather than on the axis — and the band has
       * to be wider than the tool for one to fit at all.
       */
      if (inner > 0) {
        const band = (diameter - inner) / 2 - leave;
        if (band <= d) {
          return {
            error: {
              reason: `${feature.label} leaves a ${band.toFixed(4)}" band around ${islands[0].label} and the tool is ⌀${d.toFixed(4)}. There is no room to get in, let alone move.`,
              recommendations: [`Use a tool under ⌀${band.toFixed(4)}`, "Open the pocket or reduce the island"],
            },
          };
        }
        const mid = (diameter / 2 + inner / 2) / 2;
        const entry = helicalEntry(cx + mid, cy, d, pass === 1 ? req.topZ : prevZ, z, req.clearanceZ, p.plungeFeed, band / 2 - r);
        if (!entry) return helixRefusal(d, `${band.toFixed(4)}" band around ${islands[0].label}`);
        moves.push(...entry);
      } else {
        const entry = helicalEntry(cx, cy, d, pass === 1 ? req.topZ : prevZ, z, req.clearanceZ, p.plungeFeed, diameter / 2 - r - leave);
        if (!entry) return helixRefusal(d, `⌀${diameter.toFixed(4)} pocket`);
        moves.push(...entry);
      }
      const maxRadius = diameter / 2 - r - leave;
      // An island leaves an annulus: the rings start clear of it rather than
      // at the centre, and the last one stops a tool radius off its wall.
      const minRadius = inner > 0 ? inner / 2 + r + leave : 0;
      for (let rad = Math.max(stepover, minRadius); rad <= maxRadius + 1e-6; rad += stepover) {
        ringMoves(moves, cx, cy, Math.min(rad, maxRadius), z, p.feed);
      }
      // Finish wall pass, full depth, no stock left.
      if (pass === passes) {
        moves.push({ type: "LEAD_IN", x: cx + diameter / 2 - r - leave, y: cy, z, feed: p.feed });
        ringMoves(moves, cx, cy, diameter / 2 - r, z, Math.round(p.feed * 0.7));
        // The island gets a finish pass too: it is a wall of the part, and the
        // one the boss's own size is measured on.
        if (inner > 0) {
          moves.push({ type: "LEAD_IN", x: cx + inner / 2 + r, y: cy, z, feed: p.feed });
          ringMoves(moves, cx, cy, inner / 2 + r, z, Math.round(p.feed * 0.7));
        }
      }
    } else {
      const innerW = width - d - 2 * leave;
      const innerL = length - d - 2 * leave;
      const rings = Math.max(1, Math.ceil(Math.min(innerW, innerL) / 2 / stepover));
      const entry = helicalEntry(cx, cy, d, pass === 1 ? req.topZ : prevZ, z, req.clearanceZ, p.plungeFeed, Math.min(innerW, innerL) / 2);
      if (!entry) return helixRefusal(d, `${width.toFixed(3)} × ${length.toFixed(3)} pocket`);
      moves.push(...entry);
      for (let i = rings; i >= 1; i--) {
        const w = (innerW * i) / rings;
        const l = (innerL * i) / rings;
        rectMoves(moves, cx, cy, w, l, Math.max(0, cornerR - r), z, p.feed);
      }
      if (pass === passes) {
        rectMoves(moves, cx, cy, width - d, length - d, Math.max(0, cornerR - r), z, Math.round(p.feed * 0.7));
      }
    }
    moves.push({ type: "RETRACT", x: cx, y: cy, z: req.retractZ, feed: null });
    prevZ = z;
  }

  if (leave > 0 && passes > 1) {
    warnings.push(`${leave.toFixed(3)}" left on the walls for the finish pass.`);
  }

  const area = (circular ? Math.PI * (diameter / 2) ** 2 : width * length) - Math.PI * (inner / 2) ** 2;
  return { moves, removed: Math.max(0, area) * totalDepth, warnings };
}

/**
 * HELICAL ENTRY — the only way an end mill gets into solid material.
 *
 * A standard end mill has no cutting edge at its centre: the flutes stop
 * short of the axis. Plunged straight down it does not cut, it rubs — the
 * centre heats, the flutes load up, and the tool snaps. Only a
 * centre-cutting mill (a 2-flute, or a 3+ flute with the special grind) can
 * plunge, and CANVAS has no record of which tools those are, so it does not
 * gamble on it.
 *
 * A helix sidesteps the question entirely: every point on the path is a
 * peripheral cut, which any end mill can make. The adaptive engine already
 * did this — "full depth means no straight plunge" — while the pocket
 * routine beside it plunged straight down at the pocket centre, under a
 * comment claiming a helical entry it did not perform.
 *
 * Returns null when the pocket is too tight to turn a helix in. That is a
 * refusal, not a fallback to plunging: the caller says so by name.
 */
const MIN_HELIX_RADIUS = 0.015;

/**
 * A pocket too tight to turn a helix in. Entering it needs a straight
 * plunge, which needs a centre-cutting mill — and CANVAS holds no record of
 * which tools are centre-cutting, so it refuses rather than assuming.
 */
function helixRefusal(toolDiameter: number, what: string): { error: Omit<ToolpathError, "operationId"> } {
  return {
    error: {
      reason: `The ${what} leaves no room to helix a ⌀${toolDiameter.toFixed(4)} end mill in, and entering it straight down needs a centre-cutting mill. CANVAS does not record which tools cut on centre, so it will not plunge one on the assumption.`,
      recommendations: [
        "Use a smaller end mill so the helix fits",
        "Drill a start hole at the entry point and pocket from there",
        "Plunge-mill or ramp in manually, with a tool you know cuts on centre",
      ],
    },
  };
}

function helicalEntry(
  cx: number,
  cy: number,
  toolDiameter: number,
  fromZ: number,
  toZ: number,
  clearanceZ: number,
  plungeFeed: number,
  /** Largest radius the helix may swing, from the pocket's own geometry. */
  maxRadius: number,
): Move[] | null {
  const radius = Math.min(toolDiameter * 0.4, 0.4, maxRadius);
  if (radius < MIN_HELIX_RADIUS) return null;
  const depth = fromZ - toZ;
  if (depth <= 0) return [];
  const pitch = Math.max(0.02, toolDiameter * 0.05);
  const revs = Math.max(1, Math.ceil(depth / pitch));
  // Two helical half-turns per revolution. Each one is a real G2/G3 with a Z,
  // which is what a control ramps smoothly; the twenty-four chords per turn
  // this used to emit were the ramp entry a look-ahead buffer chokes on.
  const halves = revs * 2;
  const out: Move[] = [{ type: "RAPID", x: cx + radius, y: cy, z: clearanceZ, feed: null }];
  let from = { x: cx + radius, y: cy, z: fromZ };
  for (let i = 1; i <= halves; i++) {
    const a = i * Math.PI;
    const to = {
      x: cx + radius * Math.cos(a),
      y: cy + radius * Math.sin(a),
      z: Math.max(toZ, fromZ - (depth * i) / halves),
    };
    out.push(arcMove("PLUNGE", from, cx, cy, to, false, plungeFeed));
    from = to;
  }
  // Close to centre at depth so the clearing pattern starts where it expects.
  out.push({ type: "CUT", x: cx, y: cy, z: toZ, feed: plungeFeed });
  return out;
}

/**
 * A full circle, as two 180° arcs.
 *
 * This used to walk `max(24, radius * 60)` straight chords, which left a
 * Ø1.000" bore 0.0027" out of round at the chord midpoints — see arc.ts. Two
 * halves rather than one full-circle block because a G2 with I/J and no
 * endpoint means "full circle" on Haas and Fanuc and means something else or
 * nothing elsewhere; two semicircles are unambiguous on every control and cost
 * one extra block.
 *
 * Counter-clockwise, which is climb milling on an internal circular pocket
 * with a right-hand cutter — the same direction the chorded version walked.
 */
function ringMoves(moves: Move[], cx: number, cy: number, radius: number, z: number, feed: number) {
  if (radius <= 0) return;
  const start = { x: cx + radius, y: cy };
  const far = { x: cx - radius, y: cy, z };
  moves.push({ type: "CUT", x: start.x, y: start.y, z, feed });
  moves.push(arcMove("ARC", start, cx, cy, far, false, feed));
  moves.push(arcMove("ARC", far, cx, cy, { ...start, z }, false, feed));
}

function rectMoves(
  moves: Move[],
  cx: number,
  cy: number,
  w: number,
  l: number,
  cr: number,
  z: number,
  feed: number,
) {
  const hx = w / 2;
  const hy = l / 2;
  const rr = Math.min(cr, hx, hy);
  // Each corner is one 90° arc about the corner's centre, counter-clockwise.
  // It was eight chords, which put a flat on every corner of every profile.
  //
  // The arc's I/J are measured from where the tool already is, and every corner
  // here is preceded by the straight run that lands exactly on its start point.
  // Emitting that point again produced a zero-length block before every corner
  // — legal, and four wasted blocks per pass that a machinist single-blocking
  // through has to step past.
  const corner = (x: number, y: number, sx: number, sy: number) => {
    if (rr <= 0) {
      moves.push({ type: "CUT", x, y, z, feed });
      return;
    }
    const startAngle = Math.atan2(sy, sx);
    const from = { x: x + rr * Math.cos(startAngle), y: y + rr * Math.sin(startAngle) };
    const endAngle = startAngle + Math.PI / 2;
    moves.push(
      arcMove("ARC", from, x, y, { x: x + rr * Math.cos(endAngle), y: y + rr * Math.sin(endAngle), z }, false, feed),
    );
  };
  moves.push({ type: "CUT", x: cx - hx + rr, y: cy - hy, z, feed });
  moves.push({ type: "CUT", x: cx + hx - rr, y: cy - hy, z, feed });
  corner(cx + hx - rr, cy - hy + rr, 0, -1);
  moves.push({ type: "CUT", x: cx + hx, y: cy + hy - rr, z, feed });
  corner(cx + hx - rr, cy + hy - rr, 1, 0);
  moves.push({ type: "CUT", x: cx - hx + rr, y: cy + hy, z, feed });
  corner(cx - hx + rr, cy + hy - rr, 0, 1);
  moves.push({ type: "CUT", x: cx - hx, y: cy - hy + rr, z, feed });
  corner(cx - hx + rr, cy - hy + rr, -1, 0);
}

/* ------------------------------------------------------------------ */
/* DRILL / PECK                                                        */
/* ------------------------------------------------------------------ */

function drillToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
  peck: boolean,
): { moves: Move[]; removed: number; warnings: string[]; cycle: CannedCycle } | { error: { reason: string; recommendations: string[] } } {
  if (
    feature.kind !== "DRILLED_HOLE" &&
    feature.kind !== "TAPPED_HOLE" &&
    feature.kind !== "COUNTERBORE" &&
    feature.kind !== "COUNTERSINK"
  ) {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind} and cannot be drilled.`,
        recommendations: ["Select a hole feature"],
      },
    };
  }

  const warnings: string[] = [];
  const moves: Move[] = [];
  const depth = req.topZ - req.finalZ;
  const ratio = depth / ctx.tool.diameter;

  if (ratio > 4 && !peck) {
    warnings.push(
      `Depth-to-diameter ratio is ${ratio.toFixed(1)}:1. Use a peck cycle to clear chips above 4:1.`,
    );
  }

  // Drill feed is chipload per revolution, not per tooth.
  const drillFeed = Math.round(p.rpm * ctx.tool.chiploadMax * 2);

  // The R plane. The moves rapid to it, the cycle retracts to it between
  // pecks, and both are this number — the peck retract used to be
  // topZ + 0.05 while the rapid came down to clearanceZ, which meant the
  // simulated path and the cycle would have been two different paths.
  const rPlane = req.clearanceZ;
  const peckDepth = ctx.tool.diameter * 0.75;

  moves.push({ type: "RAPID", x: feature.centerX, y: feature.centerY, z: rPlane, feed: null });
  if (peck) {
    /*
     * The peck ladder starts at the R PLANE, not at the top of the stock.
     *
     * That is what the control does: G83's Q is the increment measured from R,
     * so the depths are R−Q, R−2Q … and the first peck spends the air gap
     * between R and the surface. Starting the ladder at topZ instead produced a
     * move list whose peck depths were every one of them Q off from the cycle
     * the post emits — 13% more cutting distance in the program than in the
     * plan, on a path the simulator had already approved.
     *
     * Found by reconcile.ts on its first run against a real part, which is the
     * entire reason that module exists.
     */
    let z = rPlane;
    while (z > req.finalZ + 1e-6) {
      z = Math.max(req.finalZ, z - peckDepth);
      moves.push({ type: "PLUNGE", x: feature.centerX, y: feature.centerY, z, feed: drillFeed });
      moves.push({ type: "RETRACT", x: feature.centerX, y: feature.centerY, z: rPlane, feed: null });
    }
  } else {
    moves.push({ type: "PLUNGE", x: feature.centerX, y: feature.centerY, z: req.finalZ, feed: drillFeed });
  }
  moves.push({ type: "RETRACT", x: feature.centerX, y: feature.centerY, z: req.retractZ, feed: null });

  const removed = Math.PI * (ctx.tool.diameter / 2) ** 2 * depth;
  return {
    moves,
    removed,
    warnings,
    cycle: {
      code: peck ? "G83" : "G81",
      x: feature.centerX,
      y: feature.centerY,
      z: req.finalZ,
      r: rPlane,
      ...(peck ? { q: Number(peckDepth.toFixed(4)) } : {}),
      feed: drillFeed,
      rpm: p.rpm,
    },
  };
}

/* ------------------------------------------------------------------ */
/* ADAPTIVE 2D — bounded-engagement clearing at full depth             */
/* ------------------------------------------------------------------ */

/**
 * Adaptive clearing, the deterministic version. What makes roughing
 * "adaptive" is the engagement contract: SMALL radial engagement at FULL
 * axial depth, so the whole flute works and the load never spikes the way a
 * slotting corner does. This engine delivers that contract by construction
 * rather than by feedback: the radial step between consecutive passes is
 * the engagement bound, so the tool can never take more than it was
 * promised to.
 *
 * Two path families:
 * - Circular pockets/bores: an Archimedean spiral from the helical entry
 *   outward. Loop spacing = engagement, exactly, everywhere.
 * - Rectangular pockets: a morphed spiral — successive inward offsets of
 *   the rounded-rect boundary interpolated toward the centre. Loop count is
 *   set by the LARGER half-dimension, so spacing never exceeds the bound on
 *   either axis (and is tighter than needed on the short one, which errs
 *   toward lighter cuts).
 *
 * Feed carries radial chip-thinning compensation: at engagements below half
 * the diameter the actual chip is thinner than the programmed chipload, and
 * the standard geometric correction restores it — capped by the machine.
 * The formula is stated in the warning it emits.
 *
 * Refusals, not adaptations: a depth beyond the flute length is refused
 * (full-depth is the premise, and cutting on the shank is not a strategy),
 * and non-pocket features are refused as everywhere else.
 */
const ADAPTIVE_ENGAGEMENT_FRACTION = 0.15;

function adaptiveToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
  const d = ctx.tool.diameter;
  const r = d / 2;

  if (feature.kind !== "RECT_POCKET" && feature.kind !== "CIRC_POCKET" && feature.kind !== "BORE") {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind}; adaptive clearing requires a pocket or bore feature.`,
        recommendations: ["Select a pocket feature", "Change the operation type"],
      },
    };
  }
  if (
    ctx.tool.toolClass !== "FLAT_END_MILL" &&
    ctx.tool.toolClass !== "BULL_NOSE"
  ) {
    return {
      error: {
        reason: `${ctx.tool.description} is a ${ctx.tool.toolClass}. Adaptive clearing loads the full flute; it needs an end mill.`,
        recommendations: ["Assign a flat or bull-nose end mill"],
      },
    };
  }

  const totalDepth = req.topZ - req.finalZ;
  if (totalDepth > ctx.tool.fluteLength + 1e-9) {
    return {
      error: {
        reason: `Adaptive clearing cuts the full ${totalDepth.toFixed(3)}" in one pass, but the tool has ${ctx.tool.fluteLength.toFixed(3)}" of flute. Cutting on the shank is not a strategy.`,
        recommendations: [
          "Use a longer-flute tool",
          "Split the depth across two adaptive operations",
          "Use conventional 2D pocketing, which steps down",
        ],
      },
    };
  }

  const ae = d * ADAPTIVE_ENGAGEMENT_FRACTION;
  // Radial chip thinning: h = fz·√(1−(1−2·ae/D)²)⁻¹ restores programmed
  // chipload at partial engagement. Bounded by the machine's feed ceiling.
  const ctf = 1 / Math.sqrt(1 - (1 - (2 * ae) / d) ** 2);
  const feed = Math.round(Math.min(p.feed * ctf, ctx.maxFeed));
  const z = req.finalZ;
  const moves: Move[] = [];
  const warnings: string[] = [
    `Adaptive contract: ${(ADAPTIVE_ENGAGEMENT_FRACTION * 100).toFixed(0)}% radial engagement (${ae.toFixed(4)}") at full ${totalDepth.toFixed(3)}" depth, feed ×${ctf.toFixed(2)} chip-thinning compensation (capped by the machine at ${ctx.maxFeed} ipm).`,
  ];

  let cx: number, cy: number, removed: number;

  if (feature.kind === "RECT_POCKET") {
    cx = feature.centerX;
    cy = feature.centerY;
    const innerW = feature.width - d;
    const innerL = feature.length - d;
    if (innerW <= 0 || innerL <= 0) {
      return {
        error: {
          reason: `${feature.width.toFixed(3)} × ${feature.length.toFixed(3)} pocket is too small for the ⌀${d.toFixed(4)} tool.`,
          recommendations: [`Use a tool smaller than ⌀${Math.min(feature.width, feature.length).toFixed(4)}`],
        },
      };
    }
    if (feature.cornerRadius > 0 && !fitsInternalCorner(ctx.tool, feature.cornerRadius)) {
      return {
        error: {
          reason: `Selected ⌀${d.toFixed(4)}" end mill cannot produce the R${feature.cornerRadius.toFixed(4)} internal corner in ${feature.label}.`,
          recommendations: [`Use a tool ⌀${(feature.cornerRadius * 2).toFixed(4)}" or smaller`],
        },
      };
    }
    const crInner = Math.max(0, feature.cornerRadius - r);
    // Loop count from the LARGER half-dimension keeps spacing ≤ ae on both
    // axes; the short axis just gets lighter cuts, which is the safe side.
    const loops = Math.max(2, Math.ceil(Math.max(innerW, innerL) / 2 / ae));
    removed = feature.width * feature.length * totalDepth;
    for (let k = 1; k <= loops; k++) {
      const t = k / loops;
      rectMoves(moves, cx, cy, innerW * t, innerL * t, crInner * t, z, feed);
    }
  } else {
    cx = feature.centerX;
    cy = feature.centerY;
    const maxR = feature.diameter / 2 - r;
    if (maxR <= 0) {
      return {
        error: {
          reason: `⌀${feature.diameter.toFixed(4)} pocket is not larger than the ⌀${d.toFixed(4)} tool.`,
          recommendations: [`Use a tool smaller than ⌀${feature.diameter.toFixed(4)}`],
        },
      };
    }
    /*
     * Archimedean spiral: radius grows by exactly ae per revolution.
     *
     * This one stays tessellated, and that is not an oversight. An arc has a
     * constant radius by definition and a spiral does not have one — G2/G3
     * cannot express this path, and every CAM system on the market walks it in
     * chords too. What changed is the chord count: a fixed 48 per revolution
     * was a tolerance that got worse as the pocket got bigger, and the count
     * now comes from the same chord tolerance every other flattening in the
     * system uses, computed at the largest radius the spiral reaches.
     */
    const revs = Math.max(1, Math.ceil(maxR / ae));
    const segsPerRev = arcSegments(maxR, 2 * Math.PI);
    for (let i = 1; i <= revs * segsPerRev; i++) {
      const a = (i / segsPerRev) * Math.PI * 2;
      const rad = Math.min(maxR, (a / (Math.PI * 2)) * ae);
      moves.push({ type: "CUT", x: cx + rad * Math.cos(a), y: cy + rad * Math.sin(a), z, feed });
    }
    // Closing ring at the wall.
    ringMoves(moves, cx, cy, maxR, z, feed);
    removed = Math.PI * (feature.diameter / 2) ** 2 * totalDepth;
  }

  // Helical entry ahead of everything: full depth means no straight plunge.
  const entry: Move[] = [];
  const he = Math.min(d * 0.4, 0.4);
  const pitch = Math.max(0.02, d * 0.05);
  const entryRevs = Math.max(1, Math.ceil(totalDepth / pitch));
  entry.push({ type: "RAPID", x: cx + he, y: cy, z: req.clearanceZ, feed: null });
  // Two helical half-turns per revolution, the same construction the pocket
  // engine ramps in on. Twenty-four chords a turn was a ramp the control's
  // look-ahead had to stumble through before the cut even started.
  {
    const halves = entryRevs * 2;
    let from = { x: cx + he, y: cy, z: req.topZ };
    for (let i = 1; i <= halves; i++) {
      const a = i * Math.PI;
      const to = {
        x: cx + he * Math.cos(a),
        y: cy + he * Math.sin(a),
        z: Math.max(z, req.topZ - (totalDepth * i) / halves),
      };
      entry.push(arcMove("PLUNGE", from, cx, cy, to, false, p.plungeFeed));
      from = to;
    }
  }
  entry.push({ type: "CUT", x: cx, y: cy, z, feed });

  moves.unshift(...entry);
  moves.push({ type: "RETRACT", x: moves[moves.length - 1].x, y: moves[moves.length - 1].y, z: req.retractZ, feed: null });

  return { moves, removed, warnings };
}

/* ------------------------------------------------------------------ */
/* BORE — finish an existing hole to size                              */
/* ------------------------------------------------------------------ */

/**
 * Two honest ways to finish a bore on a 3-axis mill, selected by the tool the
 * plan assigned:
 *
 * BORING_TOOL — a single-point head cuts at the diameter it is physically set
 * to. The motion is a feed pass down and a feed pass back out (G85-style, the
 * feed-out is what leaves the finish). The engine cannot know what the head is
 * set to; it requires the tool's recorded diameter to match the feature and
 * says out loud that the operator must set the head to that diameter.
 *
 * End mill — helical interpolation: spiral down the finished wall, one full
 * cleanup ring at depth, lead out. The tool must be smaller than the bore.
 *
 * Anything else — a drill, a tap, a chamfer mill — is refused, not adapted.
 */
function boreToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
  if (feature.kind !== "BORE" && feature.kind !== "CIRC_POCKET") {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind}; a bore operation requires a bore or circular pocket feature.`,
        recommendations: ["Select the bore feature", "Change the operation type"],
      },
    };
  }

  const warnings: string[] = [];
  const moves: Move[] = [];
  const cx = feature.centerX;
  const cy = feature.centerY;
  const bore = feature.diameter;
  const depth = req.topZ - req.finalZ;

  // What the roughing pass left on the wall. The pocket engine leaves its
  // stockToLeave (0.010" radial by default); the removal figure below assumes
  // that allowance and says so, because CANVAS did not measure the roughed
  // bore.
  const assumedAllowance = 0.01;

  if (ctx.tool.toolClass === "BORING_TOOL") {
    if (Math.abs(ctx.tool.diameter - bore) > 0.001) {
      return {
        error: {
          reason: `The boring head is recorded at ⌀${ctx.tool.diameter.toFixed(4)}" but ${feature.label} is ⌀${bore.toFixed(4)}". A single-point head cuts at the diameter it is set to — CANVAS cannot adjust it.`,
          recommendations: [
            `Set the boring head to ⌀${bore.toFixed(4)} and record that diameter on the tool`,
            "Assign an end mill smaller than the bore for helical interpolation",
          ],
        },
      };
    }
    // Single-point: feed per revolution, one cutting edge.
    const boringFeed = Math.max(1, Math.round(p.rpm * (ctx.tool.chiploadMin + ctx.tool.chiploadMax) / 2));
    p.feed = boringFeed;
    p.plungeFeed = boringFeed;
    p.stepover = 0;
    p.stockToLeave = 0;

    moves.push({ type: "RAPID", x: cx, y: cy, z: req.clearanceZ, feed: null });
    moves.push({ type: "PLUNGE", x: cx, y: cy, z: req.finalZ, feed: boringFeed });
    // Feed out, not rapid out — the spring pass is what leaves the finish.
    moves.push({ type: "RETRACT", x: cx, y: cy, z: req.topZ + 0.05, feed: boringFeed });
    moves.push({ type: "RETRACT", x: cx, y: cy, z: req.retractZ, feed: null });

    warnings.push(
      `Single-point bore: set the head to ⌀${bore.toFixed(4)} before running. The program cannot verify the head setting.`,
    );
  } else if (
    ctx.tool.toolClass === "FLAT_END_MILL" ||
    ctx.tool.toolClass === "BULL_NOSE" ||
    ctx.tool.toolClass === "SHELL_MILL"
  ) {
    const d = ctx.tool.diameter;
    if (d >= bore) {
      return {
        error: {
          reason: `⌀${d.toFixed(4)}" end mill cannot helically interpolate a ⌀${bore.toFixed(4)}" bore — the tool is not smaller than the hole.`,
          recommendations: [`Use an end mill smaller than ⌀${bore.toFixed(4)}`, "Use a boring head set to size"],
        },
      };
    }
    const pathR = bore / 2 - d / 2;
    // Helix pitch per revolution: shallow enough to stay a finishing cut.
    const pitch = Math.min(p.stepdown, d * 0.1);
    const revs = Math.max(1, Math.ceil(depth / pitch));
    const helixFeed = Math.round(p.feed * 0.65);

    moves.push({ type: "RAPID", x: cx, y: cy, z: req.clearanceZ, feed: null });
    moves.push({ type: "PLUNGE", x: cx, y: cy, z: req.topZ + 0.02, feed: p.plungeFeed });
    moves.push({ type: "LEAD_IN", x: cx + pathR, y: cy, z: req.topZ + 0.02, feed: helixFeed });
    /*
     * Helical interpolation, two half-turn arcs per revolution.
     *
     * This is the operation where chording hurt most: boring is what produces
     * a bearing seat, and the bore was being cut as a polygon of up to
     * `max(24, pathR * 60)` sides. On a Ø1.000" bore that is 0.0027" of form
     * error — five times a ±0.0005" band, and not something an offset can fix.
     */
    let from = { x: cx + pathR, y: cy, z: req.topZ + 0.02 };
    for (let rev = 0; rev < revs; rev++) {
      const zStart = req.topZ - (depth * rev) / revs;
      const zEnd = req.topZ - (depth * (rev + 1)) / revs;
      for (let half = 1; half <= 2; half++) {
        const a = half * Math.PI;
        const to = {
          x: cx + pathR * Math.cos(a),
          y: cy + pathR * Math.sin(a),
          z: Math.max(req.finalZ, zStart + ((zEnd - zStart) * half) / 2),
        };
        moves.push(arcMove("CUT", from, cx, cy, to, false, helixFeed));
        from = to;
      }
    }
    // Full flat ring at depth cleans up the helix exit ramp.
    ringMoves(moves, cx, cy, pathR, req.finalZ, Math.round(p.feed * 0.7));
    moves.push({ type: "LEAD_OUT", x: cx, y: cy, z: req.finalZ, feed: helixFeed });
    moves.push({ type: "RETRACT", x: cx, y: cy, z: req.retractZ, feed: null });
  } else {
    return {
      error: {
        reason: `${ctx.tool.description} is a ${ctx.tool.toolClass} and cannot finish a bore.`,
        recommendations: ["Assign a boring head set to size", "Assign an end mill smaller than the bore"],
      },
    };
  }

  const outerR = bore / 2;
  const innerR = Math.max(0, outerR - assumedAllowance);
  const removed = Math.PI * (outerR ** 2 - innerR ** 2) * depth;
  warnings.push(
    `Material-removed figure assumes the roughing pass left ${assumedAllowance.toFixed(3)}" radial. CANVAS has not measured the roughed bore.`,
  );

  return { moves, removed, warnings };
}

/* ------------------------------------------------------------------ */
/* TAP — rigid tap, feed locked to pitch × rpm                         */
/* ------------------------------------------------------------------ */

/**
 * Parse a pitch, in inches per revolution, out of a thread designation.
 *
 * Deterministic and deliberately narrow: imperial "1/4-20", "#10-32",
 * "5/16-18 UNC" (pitch = 1 / TPI) and metric "M6x1.0" / "M6×1.0" (pitch in
 * mm). Anything else returns null — a tap fed at an invented pitch breaks,
 * so no pitch is ever guessed. See CLAUDE.md principle 12.
 */
/* ------------------------------------------------------------------ */
/* THREAD MILL — one helical turn, cutting the form                    */
/* ------------------------------------------------------------------ */

/**
 * THREAD MILLING.
 *
 * Tapping was the only thread strategy this system had, and the planner never
 * even emitted one. Thread milling is how a shop makes a 3/4-10 in 17-4, how it
 * saves a part with a broken tap still in the hole, and how it holds a class-3
 * fit — and it is the same helical arc machinery the bore already uses.
 *
 * A FULL-FORM mill carries the whole thread profile on its flutes, so one
 * 360° helical turn rising a single pitch cuts the entire thread. That is the
 * cycle here. A SINGLE-POINT mill carries one tooth and needs a pass per
 * thread; this engine does not implement that and refuses rather than emitting
 * one turn and calling it a thread.
 *
 * The tool circles at (major − toolDiameter) / 2, because an internal thread's
 * MAJOR diameter is its root — the deepest the cutter has to reach. It runs
 * bottom-up and counter-clockwise, which climb mills a right-hand internal
 * thread and puts the cutting pressure into the material rather than pulling
 * the tool into the wall.
 *
 * Lead-in and lead-out are tangential arcs on the same helix, half a turn and
 * half a pitch each, so the cutter enters and leaves the form on the thread
 * rather than crashing into the wall radially and leaving a witness at the
 * entry.
 */
function threadMillToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
  if (feature.kind !== "TAPPED_HOLE") {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind}; a thread mill operation requires a tapped hole feature.`,
        recommendations: ["Select a tapped hole feature"],
      },
    };
  }
  if (ctx.tool.toolClass !== "THREAD_MILL") {
    return {
      error: {
        reason: `${ctx.tool.description} is a ${ctx.tool.toolClass}, not a thread mill. The helix that cuts a thread is the tool's own form, and no other cutter carries it.`,
        recommendations: ["Assign a thread mill", "Tap this hole instead"],
      },
    };
  }
  const thread = parseThread(feature.thread);
  if (!thread) {
    return {
      error: {
        reason: feature.thread
          ? `Thread designation "${feature.thread}" could not be read for a pitch and a major diameter, and the helix is both of them. CANVAS will not invent either.`
          : `${feature.label} has no thread designation, so there is no helix to cut. CANVAS will not invent one.`,
        recommendations: ['Record the thread on the feature (e.g. "1/4-20 UNC" or "M6x1.0")'],
      },
    };
  }
  if (!sameThread(ctx.tool.threadDesignation, feature.thread)) {
    return {
      error: {
        reason: ctx.tool.threadDesignation
          ? `${ctx.tool.description} cuts ${ctx.tool.threadDesignation} and ${feature.label} is ${feature.thread}. A full-form mill carries one pitch on its flutes; run at another it cuts a thread of the wrong form.`
          : `${ctx.tool.description} records no thread, and a full-form mill's pitch is ground into it. Matching on diameter alone puts a 28-pitch form in a hole cut for 20.`,
        recommendations: [
          `Record the thread on the tool, or assign a ${feature.thread} thread mill`,
          "A single-point thread mill cuts any pitch, and this engine does not implement one",
        ],
      },
    };
  }

  const minor = threadMinor(thread);
  const d = ctx.tool.diameter;
  if (d >= minor) {
    return {
      error: {
        reason: `${ctx.tool.description} is ⌀${d.toFixed(4)} and ${feature.thread} has a ⌀${minor.toFixed(4)} minor diameter. The tool does not go in the hole.`,
        recommendations: [`Use a thread mill under ⌀${minor.toFixed(4)}`, "Tap this hole instead"],
      },
    };
  }

  const depth = req.topZ - req.finalZ;
  const warnings: string[] = [];
  /*
   * A full-form mill cuts the whole thread in one turn ONLY where its form
   * covers the thread. Past the flute length the top of the thread is cut and
   * the bottom is not, and the hole gauges as a partial thread — which a plug
   * gauge finds and a tapped hole never would.
   */
  if (ctx.tool.fluteLength < depth - 1e-9) {
    return {
      error: {
        reason: `${feature.label} is threaded ${depth.toFixed(3)}" deep and ${ctx.tool.description} carries ${ctx.tool.fluteLength.toFixed(3)}" of form. One turn would cut the top of the thread and leave the bottom of it uncut.`,
        recommendations: [
          `Use a thread mill with at least ${depth.toFixed(3)}" of form`,
          "Reduce the threaded depth if the print allows it",
          "Tap this hole instead",
        ],
      },
    };
  }

  const moves: Move[] = [];
  const r = (thread.major - d) / 2;
  const cx = feature.centerX;
  const cy = feature.centerY;
  const feed = Math.round(p.feed * 0.6); // the form is a full-width cut
  const bottom = req.finalZ;

  moves.push({ type: "RAPID", x: cx, y: cy, z: req.clearanceZ, feed: null });
  // Down the middle of a hole that already exists — the same case as a
  // counterbore, and the reason the drill precedes this in the stage table.
  moves.push({ type: "PLUNGE", x: cx, y: cy, z: bottom, feed: p.plungeFeed });

  // Lead in: half a turn out to the thread radius, rising half a pitch, so the
  // cutter arrives tangent to the helix rather than into the wall.
  moves.push(
    arcMove("LEAD_IN", { x: cx, y: cy }, cx + r / 2, cy, { x: cx + r, y: cy, z: bottom + thread.pitch / 2 }, false, feed),
  );
  // The thread: one full turn, rising one pitch, as two halves because a G2/G3
  // with I/J and no end point means "full circle" on a Haas and means something
  // else or nothing elsewhere.
  moves.push(
    arcMove("CUT", { x: cx + r, y: cy }, cx, cy, { x: cx - r, y: cy, z: bottom + thread.pitch }, false, feed),
  );
  moves.push(
    arcMove("CUT", { x: cx - r, y: cy }, cx, cy, { x: cx + r, y: cy, z: bottom + 1.5 * thread.pitch }, false, feed),
  );
  // Lead out: back to the centre on the same helix, clear of the form.
  moves.push(
    arcMove("LEAD_OUT", { x: cx + r, y: cy }, cx + r / 2, cy, { x: cx, y: cy, z: bottom + 2 * thread.pitch }, false, feed),
  );
  moves.push({ type: "RETRACT", x: cx, y: cy, z: req.retractZ, feed: null });

  warnings.push(
    `Thread milled full form: one turn at ⌀${(2 * r).toFixed(4)} centre path cuts the whole ${thread.designation}. Check the class of fit on the first part — the size comes off the D offset, which is the point of milling it.`,
  );

  // The thread form removed from the wall of the hole, over its depth.
  const removed = Math.PI * ((thread.major / 2) ** 2 - (minor / 2) ** 2) * depth * 0.5;
  return { moves, removed: Math.max(0, removed), warnings };
}

function tapToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[]; cycle: CannedCycle } | { error: { reason: string; recommendations: string[] } } {
  if (feature.kind !== "TAPPED_HOLE") {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind}; a tap operation requires a tapped hole feature.`,
        recommendations: ["Select a tapped hole feature"],
      },
    };
  }
  if (ctx.tool.toolClass !== "TAP") {
    return {
      error: {
        reason: `${ctx.tool.description} is a ${ctx.tool.toolClass}, not a tap. Feed-per-rev synchronisation only holds for the tool the thread was designed for.`,
        recommendations: ["Assign a tap matching the thread designation", "Thread mill this hole instead"],
      },
    };
  }
  if (!feature.thread) {
    return {
      error: {
        reason: `${feature.label} has no thread designation, so the pitch is unknown. A tap fed at a guessed pitch breaks — CANVAS will not invent one.`,
        recommendations: ['Record the thread on the feature (e.g. "1/4-20 UNC" or "M6x1.0")'],
      },
    };
  }
  const pitch = parseThreadPitch(feature.thread);
  if (pitch === null) {
    return {
      error: {
        reason: `Thread designation "${feature.thread}" could not be parsed for a pitch. CANVAS will not invent one.`,
        recommendations: ['Use the form "1/4-20 UNC", "#10-32" or "M6x1.0"'],
      },
    };
  }

  const warnings: string[] = [];
  const major = parseThreadMajor(feature.thread);
  if (major !== null && Math.abs(ctx.tool.diameter - major) > 0.02) {
    warnings.push(
      `Assigned tap is ⌀${ctx.tool.diameter.toFixed(3)}" but ${feature.thread} has a ${major.toFixed(3)}" major diameter — confirm the right tap is loaded.`,
    );
  }

  // Rigid tapping: the feed is not chosen, it is the thread. Cap the spindle
  // well below the machine's rapid-tap comfort zone rather than at the
  // milling rpm the generic derivation produced.
  const rpm = Math.min(p.rpm, 800);
  const feed = Number((rpm * pitch).toFixed(2));
  p.rpm = rpm;
  p.feed = feed;
  p.plungeFeed = feed;
  p.stepover = 0;
  p.stockToLeave = 0;
  p.coolant = "FLOOD";

  const moves: Move[] = [];
  moves.push({ type: "RAPID", x: feature.centerX, y: feature.centerY, z: req.clearanceZ, feed: null });
  // Down and back out at the synchronised feed — the reversal is a feed move.
  moves.push({ type: "PLUNGE", x: feature.centerX, y: feature.centerY, z: req.finalZ, feed });
  moves.push({ type: "RETRACT", x: feature.centerX, y: feature.centerY, z: req.topZ + 0.1, feed });
  moves.push({ type: "RETRACT", x: feature.centerX, y: feature.centerY, z: req.retractZ, feed: null });

  warnings.push(
    "Rigid tap: the post emits a canned tapping cycle. Posts for controllers without rigid tapping refuse the operation rather than emitting unsynchronised moves.",
  );

  // A tap displaces more than it removes; the removal figure is the thread
  // relief over the drilled hole, small and honest enough at zero.
  //
  // The cycle carries the feed the engine locked, not a feed the post derives.
  // G84 owns the spindle, and a feed that is not exactly pitch x rpm breaks the
  // tap in the hole.
  return {
    moves,
    removed: 0,
    warnings,
    cycle: {
      code: "G84",
      x: feature.centerX,
      y: feature.centerY,
      z: req.finalZ,
      r: req.clearanceZ,
      feed,
      rpm,
    },
  };
}

/* ------------------------------------------------------------------ */
/* 2D CONTOUR — outside profile with tangential lead in/out            */
/* ------------------------------------------------------------------ */

/**
 * 2D CONTOUR, WITH THE CONTROL DOING THE OFFSETTING.
 *
 * The offset used to be baked into the path — `feature.width + tool.diameter`
 * — and no G41/G42/D ever reached the control. That takes away the machinist's
 * only recourse for holding size. A cutter a thou and a half under nominal, a
 * regrind, a hair of runout, spring on a deep wall: the answer to all of them
 * is to nudge the D offset and re-run the finish pass. A program whose offset
 * is baked in cannot be adjusted at the machine at all, and the only fix is to
 * walk back to the computer and re-post, which nobody does at 11pm.
 *
 * So the PROGRAM now carries the part boundary and the control offsets it. The
 * move list still carries the cutter centre, because that is what the simulator
 * sweeps and what every collision check reasons about — the two paths are built
 * side by side here and zipped together, from the same generator, so they
 * cannot drift.
 *
 * COMP SIDE
 *
 * The contour runs counter-clockwise, so at the bottom edge travel is +X with
 * the part at +Y. The cutter must stay outside the part, which is to the RIGHT
 * of the direction of travel: G42. With a right-hand cutter that is
 * conventional milling; climbing an outside profile means reversing to
 * clockwise with G41, which belongs with real finish passes (A6) rather than
 * here, where it would be a second change hiding inside this one.
 *
 * THE LEAD MOVES ARE THE COMP RULES
 *
 * Compensation is activated on a straight move, in free air, at least a tool
 * radius long, and cancelled the same way on a move AWAY from the part. Never
 * inside a corner and never on an arc — controls fault on that or ramp the
 * offset through the cut.
 *
 * Fixed here at the same time: the lead-in used to end on the LEFT edge while
 * the contour started on the BOTTOM edge, so the first cutting move was a
 * straight chord across the bottom-left corner — a gouge of 0.293 × the corner
 * radius, nearly a tenth of an inch on an ordinary part. The lead now lands
 * exactly on the point the contour starts from.
 */
function contourToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
  if (feature.kind !== "OUTSIDE_CONTOUR") {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind}; 2D contour requires an outside contour feature.`,
        recommendations: ["Select the outside contour feature"],
      },
    };
  }

  const moves: Move[] = [];
  const d = ctx.tool.diameter;
  const r = d / 2;
  const totalDepth = req.topZ - req.finalZ;

  /*
   * A FINISH pass runs the full depth in one go.
   *
   * Every depth step in a finishing pass leaves a witness line on the wall —
   * a visible band where the cutter re-entered, and a place the wall is a
   * fraction of a thou proud or shy depending on how the tool deflected on
   * each step. A wall cut in one pass has none of them.
   *
   * The limit is the flute, not the ambition: past the flute length the shank
   * is rubbing the wall, which is not a finishing strategy. There the pass
   * steps down like a roughing pass and SAYS SO, because a machinist who
   * ordered a finish pass and got a stepped one needs to know which he has.
   */
  const finishing = req.pass === "FINISH";
  const oneShot = finishing && totalDepth <= ctx.tool.fluteLength + 1e-9;
  const passes = oneShot ? 1 : Math.max(1, Math.ceil(totalDepth / p.stepdown));
  const warnings: string[] = [];
  if (finishing && !oneShot) {
    warnings.push(
      `Finish pass on ${feature.label} is ${totalDepth.toFixed(3)}" deep against ${ctx.tool.fluteLength.toFixed(3)}" of flute, so it steps down in ${passes} passes and will show a witness line at each step. A longer-flute tool would cut this wall in one.`,
    );
  }

  /*
   * THE BOUNDARY.
   *
   * A chain when the feature carries one, and otherwise the rounded rectangle
   * its width, length and corner radius describe — which is what most plate
   * work actually is, and what this engine used to assume of everything.
   *
   * The PROGRAM carries this boundary; the control offsets it. The offset
   * computed here is the cutter centre, for the simulator and the collision
   * checks. See chain.ts for what it refuses and why.
   */
  const boundary: Chain =
    feature.chain && feature.chainStart
      ? { start: feature.chainStart, segments: feature.chain }
      : rectangleChain(feature.width, feature.length, feature.cornerRadius);

  const centreChain = offsetChain(boundary, r);
  if ("error" in centreChain) {
    return { error: { reason: `${feature.label}: ${centreChain.error.reason}`, recommendations: centreChain.error.recommendations } };
  }

  // Where the contour opens, on both paths.
  const startProgram = boundary.start;
  const startCentre = centreChain.start;
  const lead = Math.max(2 * r, 0.2);
  const leadFeed = Math.round(p.feed * 0.6);

  /*
   * The lead comes in along the first segment's own direction, so compensation
   * ramps on over a straight move that is already pointing where the cut goes.
   * A lead that arrives from any other angle either gouges as the offset comes
   * on or leaves a witness mark where it meets the wall.
   */
  const firstSeg = boundary.segments[0];
  const dir =
    firstSeg.kind === "LINE"
      ? {
          x: firstSeg.to.x - startProgram.x,
          y: firstSeg.to.y - startProgram.y,
        }
      : { x: 0, y: 0 };
  const dirMag = Math.hypot(dir.x, dir.y);
  if (dirMag < 1e-9) {
    return {
      error: {
        reason: `${feature.label} starts on an arc, and compensation cannot be brought on over one — a control either faults or ramps the offset through the cut.`,
        recommendations: ["Start the profile on a straight segment", "Add a short straight lead-in to the geometry"],
      },
    };
  }
  const unit = { x: dir.x / dirMag, y: dir.y / dirMag };
  const approach = { x: startProgram.x - unit.x * lead, y: startProgram.y - unit.y * lead };
  // Away from the part, perpendicular to the first segment on the cutter side.
  const away = { x: startProgram.x + unit.y * lead, y: startProgram.y - unit.x * lead };

  for (let pass = 1; pass <= passes; pass++) {
    const z = req.topZ - (totalDepth * pass) / passes;

    // Comp is off for the approach and the plunge, so program and centre agree.
    moves.push({ type: "RAPID", x: approach.x, y: approach.y, z: req.clearanceZ, feed: null });
    moves.push({ type: "PLUNGE", x: approach.x, y: approach.y, z, feed: p.plungeFeed });

    // Comp comes on over the lead-in. The centre ends one radius to the right
    // of the programmed point, which is exactly where the contour starts.
    moves.push({
      type: "LEAD_IN",
      x: startCentre.x,
      y: startCentre.y,
      z,
      feed: leadFeed,
      program: { x: startProgram.x, y: startProgram.y, side: "RIGHT", activate: true },
    });

    /*
     * Both chains, zipped. The offset chain can carry MORE segments than the
     * boundary — a sharp convex corner gains a pivot arc that has no
     * counterpart in the boundary — so they are matched by walking the
     * boundary and taking each offset segment that belongs to it. A pivot arc
     * is programmed at the corner it pivots about, which is where the control
     * puts the tool anyway with compensation on.
     */
    const centreMoves = chainMoves(centreChain, z, p.feed);
    const boundaryMoves = chainMoves(boundary, z, p.feed);
    /*
     * The offset says which of its segments it INSERTED, rather than the zip
     * inferring it. Inferring it was wrong: `b` advanced once per centre move
     * including the pivots, so from the first sharp corner onward every
     * boundary point landed on the wrong centre move — a straight edge went
     * out as an impossible arc, and once `b` ran past the end it clamped to
     * the closing point and emitted full circles there. A 4 x 2 plate posted
     * three of its four sides and cut four 360 degree circles into one corner,
     * and it did that for every profiled part in the system.
     *
     * A pivot carries no program block at all: with compensation active the
     * control pivots the tool round the corner itself. The move stays, because
     * the simulator and the collision checks need the motion.
     */
    const pivots = new Set(centreChain.pivots ?? []);
    let b = 0;
    for (let k = 0; k < centreMoves.length; k++) {
      if (pivots.has(k)) {
        moves.push({ ...centreMoves[k], program: { x: centreMoves[k].x, y: centreMoves[k].y, side: "RIGHT", pivot: true } });
        continue;
      }
      const bm = boundaryMoves[b];
      if (!bm) break;
      moves.push({
        ...centreMoves[k],
        program: {
          x: bm.x,
          y: bm.y,
          ...(bm.i !== undefined ? { i: bm.i, j: bm.j } : {}),
          side: "RIGHT",
        },
      });
      b++;
    }

    /*
     * Comp off on the way out, moving away from the part rather than back
     * along the wall that was just cut.
     *
     * The cutter centre ends AT the programmed point, because that is what
     * G40 means: the offset is gone by the end of the move. Carrying the
     * offset through the cancel — which the chain rework briefly did — puts
     * the simulated tool a radius from where the machine leaves it, and the
     * reconciler cannot see it because the reconciler reads the programmed
     * path, which was right.
     */
    moves.push({
      type: "LEAD_OUT",
      x: away.x,
      y: away.y,
      z,
      feed: leadFeed,
      program: { x: away.x, y: away.y, side: "RIGHT", deactivate: true },
    });
    moves.push({ type: "RETRACT", x: away.x, y: away.y, z: req.retractZ, feed: null });
  }

  // Perimeter from the chain itself, arcs along the arc — not 2(w + l), which
  // described the bounding box rather than the profile.
  const perimeter = chainLength(boundary);
  return { moves, removed: perimeter * ctx.tool.diameter * totalDepth * 0.5, warnings };
}

/* ------------------------------------------------------------------ */
/* STEP — a facing cut over a strip along one edge                     */
/* ------------------------------------------------------------------ */

/**
 * A STEP HAD NO ENGINE AND NO PLAN.
 *
 * `STEP` was in the feature vocabulary, on the entry form, and in no bucket the
 * planner reads — so a step recorded on a part produced no operation, no
 * concern, and only the coverage gate three pages later saying a feature was
 * not cut. It was the last kind in the list that nothing looked at.
 *
 * A step is not a pocket. It is open on one side — the side it runs along — so
 * ringing a closed boundary round it would air-cut the open edge and leave the
 * cutter buried at the closed one. It is a FACING cut over a strip: zig-zag
 * across it, entering and leaving off the end of the part where there is no
 * material, which is what makes it need no ramp and no helix.
 */
function stepToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  stock: Stock,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
  if (feature.kind !== "STEP") {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind} and is not a step.`,
        recommendations: ["Point the operation at a step feature", "Change the operation type"],
      },
    };
  }
  const d = ctx.tool.diameter;
  const along = feature.side === "XMIN" || feature.side === "XMAX";
  const across = along ? stock.y : stock.x;
  if (feature.width <= 0) {
    return {
      error: {
        reason: `${feature.label} records a ${feature.width} step, which takes nothing off the edge.`,
        recommendations: ["Record how far in from the edge the step runs"],
      },
    };
  }

  const warnings: string[] = [];
  const moves: Move[] = [];
  const lead = d * 0.6; // roll on and off past the end of the part
  const stepover = d * 0.7;
  const totalDepth = req.topZ - req.finalZ;
  const passes = Math.max(1, Math.ceil(totalDepth / p.stepdown));

  /*
   * The strip, in part coordinates. `width` is measured in from the named edge,
   * and the cutter centre runs half a tool inside the far boundary so the edge
   * of the cut lands on the step's wall rather than a radius past it.
   */
  const edge = feature.side === "XMIN" ? -stock.x / 2 : feature.side === "XMAX" ? stock.x / 2 : feature.side === "YMIN" ? -stock.y / 2 : stock.y / 2;
  const inward = feature.side === "XMIN" || feature.side === "YMIN" ? 1 : -1;
  const wallAt = edge + inward * feature.width;
  // First pass hangs off the edge; the last one stops a tool radius short of
  // the wall so the wall is cut to size and not through.
  const first = edge - inward * (d / 2);
  const last = wallAt - inward * (d / 2);
  const span = Math.abs(last - first);
  const lanes = Math.max(1, Math.ceil(span / stepover));

  if (feature.width < d / 2) {
    warnings.push(
      `${feature.label} is ${feature.width.toFixed(4)}" wide and the tool is ⌀${d.toFixed(4)}, so a single pass overhangs the edge by more than half the cutter. It cuts, and the far side of the tool is doing nothing.`,
    );
  }

  const at = (lane: number, end: number, z: number, type: Move["type"], feed: number | null): Move => {
    const pos = first + inward * (lanes === 0 ? 0 : (span * lane) / lanes);
    const cross = end * (across / 2 + lead);
    return along ? { type, x: pos, y: cross, z, feed } : { type, x: cross, y: pos, z, feed };
  };

  moves.push(at(0, -1, req.clearanceZ, "RAPID", null));
  for (let pass = 1; pass <= passes; pass++) {
    const z = req.topZ - (totalDepth * pass) / passes;
    let dir = 1;
    moves.push(at(0, -dir, req.clearanceZ, "RAPID", null));
    moves.push(at(0, -dir, z, "PLUNGE", p.plungeFeed));
    for (let lane = 0; lane <= lanes; lane++) {
      moves.push(at(lane, -dir, z, "CUT", p.feed));
      moves.push(at(lane, dir, z, "CUT", p.feed));
      dir *= -1;
      if (lane < lanes) moves.push(at(lane + 1, -dir, z, "CUT", p.feed));
    }
    moves.push({ ...moves[moves.length - 1], type: "RETRACT", z: req.retractZ, feed: null });
  }

  return { moves, removed: feature.width * across * totalDepth, warnings };
}

/* ------------------------------------------------------------------ */
/* SLOT — ramped, along its own centreline                             */
/* ------------------------------------------------------------------ */

/**
 * The steepest a mill is fed into its own cut along a straight line.
 *
 * A slot cannot be helixed into: at full width there is no room to swing, and
 * `helicalEntry` refuses rather than plunging a tool nobody recorded as
 * centre-cutting. Ramping along the slot's own length is what a machinist does
 * instead, and 3° is the conservative end of what a plain end mill takes.
 */
const SLOT_RAMP_DEGREES = 3;

/**
 * A SLOT IS NOT A POCKET.
 *
 * `classify` put SLOT in the pocket bucket, so the planner emitted a POCKET_2D
 * operation for every slot on the part and the pocket engine then refused it —
 * "is a SLOT and cannot be machined with a 2D pocket operation". A plan that
 * reads complete, produces an operation, and cannot run. The machinist reads
 * the plan; the refusal only appears at export.
 *
 * A slot is a centreline and a width: a stadium, two parallel edges closed by
 * a half-round at each end. The cutter runs the centreline, and where it is
 * narrower than the slot it takes a finishing lap round the stadium the
 * boundary offsets to — the same shape, narrower by the tool.
 */
function slotToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
  if (feature.kind !== "SLOT") {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind} and is not a slot.`,
        recommendations: ["Point the operation at a slot feature", "Change the operation type"],
      },
    };
  }

  const d = ctx.tool.diameter;
  const r = d / 2;
  const w = feature.width;

  if (w < d - 1e-9) {
    return {
      error: {
        reason: `${feature.label} is ${w.toFixed(4)}" wide and the tool is ⌀${d.toFixed(4)}. It does not fit.`,
        recommendations: [`Use a tool ⌀${w.toFixed(4)} or smaller`, "Open the slot on the drawing"],
      },
    };
  }

  const dx = feature.endX - feature.startX;
  const dy = feature.endY - feature.startY;
  const len = Math.hypot(dx, dy);
  if (len < 1e-6) {
    return {
      error: {
        reason: `${feature.label} starts and ends at the same point, so it has no length to cut along.`,
        recommendations: ["Record the slot's two end points", "A slot of zero length is a hole — record it as one"],
      },
    };
  }
  const ux = dx / len;
  const uy = dy / len;

  /*
   * HOW FAR THE CUTTER CENTRE ACTUALLY TRAVELS.
   *
   * The cutter's EDGE makes the round end of the slot, so its centre stops a
   * radius short at each end. A slot no longer than the tool leaves the centre
   * nowhere to go — the two ends collapse onto one point and the "ramp" becomes
   * a vertical feed at a single XY, which is the plunge this whole approach
   * exists to avoid. That is a round-ended pocket, not a slot, and it is
   * refused rather than plunged.
   */
  const travel = len - d;
  if (travel <= 1e-6) {
    return {
      error: {
        reason: `${feature.label} is ${len.toFixed(4)}" long and the tool is ⌀${d.toFixed(4)}, so the cutter centre has nowhere to travel and nothing to ramp along. Feeding it straight down at one point needs a centre-cutting mill, and CANVAS does not record which tools cut on centre.`,
        recommendations: [
          `Use a tool under ⌀${len.toFixed(4)} so the cutter has room to move`,
          "A slot no longer than the cutter is a round-ended pocket — record it as one",
        ],
      },
    };
  }

  const warnings: string[] = [];
  const moves: Move[] = [];
  const totalDepth = req.topZ - req.finalZ;

  /*
   * The step is whatever the ramp can reach over the travel available, and
   * never more than the parameters ask for. A short slot ramps less per pass
   * and takes more passes; forcing the parameter's stepdown would steepen the
   * ramp past what a plain end mill takes, on the tool the ramp exists for.
   */
  const rampReach = travel * Math.tan((SLOT_RAMP_DEGREES * Math.PI) / 180);
  const step = Math.min(p.stepdown, rampReach);
  const passes = Math.max(1, Math.ceil(totalDepth / step));
  if (rampReach < p.stepdown) {
    warnings.push(
      `${feature.label} leaves the cutter ${travel.toFixed(4)}" of travel, so a ${SLOT_RAMP_DEGREES}° ramp only reaches ${rampReach.toFixed(4)}" per pass against the ${p.stepdown.toFixed(4)}" stepdown. Cutting it in ${passes} passes rather than steepening the ramp.`,
    );
  }

  // Full width is a full slot: 180° of engagement, the heaviest cut there is.
  if (w - d < 1e-9) {
    warnings.push(
      `The tool is the full width of the slot, so it is 180° engaged for the whole cut — chips have nowhere to go and the cutter is loaded on both sides. A smaller tool taking two passes is easier on the spindle and on the wall.`,
    );
  }

  const at = (t: number, z: number, type: Move["type"], feed: number | null): Move => ({
    type,
    x: feature.startX + ux * t,
    y: feature.startY + uy * t,
    z,
    feed,
  });
  // The centreline is shortened by the tool radius at each end: the cutter's
  // edge, not its centre, makes the round end of the slot.
  const a = r;
  const b = len - r;

  moves.push({ type: "RAPID", x: feature.startX + ux * a, y: feature.startY + uy * a, z: req.clearanceZ, feed: null });
  moves.push(at(a, req.topZ, "PLUNGE", p.plungeFeed));

  let z = req.topZ;
  for (let pass = 1; pass <= passes; pass++) {
    const target = req.topZ - (totalDepth * pass) / passes;
    // Down the slot while descending, back along it flat. Every pass ends
    // where the next one starts, so nothing rapids through the cut.
    moves.push(at(b, target, "CUT", p.plungeFeed));
    moves.push(at(a, target, "CUT", p.feed));
    z = target;
  }

  /*
   * The finishing lap, when the tool is narrower than the slot: round the
   * stadium the boundary offsets to, which is the same centreline with a
   * half-round of (w − d)/2 at each end.
   */
  const offR = (w - d) / 2;
  if (offR > 1e-6) {
    const nx = -uy;
    const ny = ux;
    const finishFeed = Math.round(p.feed * 0.7);
    const pt = (t: number, side: number) => ({
      x: feature.startX + ux * t + nx * offR * side,
      y: feature.startY + uy * t + ny * offR * side,
    });
    const s1 = pt(a, 1);
    const e1 = pt(b, 1);
    const e2 = pt(b, -1);
    const s2 = pt(a, -1);
    moves.push({ type: "LEAD_IN", x: s1.x, y: s1.y, z, feed: finishFeed });
    moves.push({ type: "CUT", x: e1.x, y: e1.y, z, feed: finishFeed });
    moves.push(arcMove("CUT", e1, feature.startX + ux * b, feature.startY + uy * b, { ...e2, z }, true, finishFeed));
    moves.push({ type: "CUT", x: s2.x, y: s2.y, z, feed: finishFeed });
    moves.push(arcMove("CUT", s2, feature.startX + ux * a, feature.startY + uy * a, { ...s1, z }, true, finishFeed));
  }

  moves.push({ type: "RETRACT", x: moves[moves.length - 1].x, y: moves[moves.length - 1].y, z: req.retractZ, feed: null });

  // A stadium: a rectangle of length (len − w) by w, plus a circle of ⌀w.
  const area = Math.max(0, len - w) * w + Math.PI * (w / 2) ** 2;
  return { moves, removed: area * totalDepth, warnings };
}

/* ------------------------------------------------------------------ */
/* COUNTERBORE and COUNTERSINK — the head on a hole                    */
/* ------------------------------------------------------------------ */

/**
 * THE HEAD ON A HOLE.
 *
 * COUNTERBORE and COUNTERSINK were in no `classify` bucket at all. The planner
 * emitted no operation and raised no concern: total silence, on a feature whose
 * whole point is that a screw head has to sit in it. Only the coverage gate
 * caught them, at export, three pages away from the plan a machinist reads.
 *
 * A counterbore is a flat-bottomed circle at the head diameter, interpolated
 * with an end mill. A countersink is a cone, and it is the same arithmetic as a
 * chamfer: the tool's own included angle is the angle of the cone, and the
 * depth is where that cone reaches the head diameter. Both need the pilot hole
 * to exist first, which is what the sequencing table's stage says.
 */
function headToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
  if (feature.kind !== "COUNTERBORE" && feature.kind !== "COUNTERSINK") {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind}, which has no head to cut.`,
        recommendations: ["Point the operation at a counterbore or countersink feature"],
      },
    };
  }
  const head = feature.headDiameter;
  if (head == null || !(head > 0)) {
    return {
      error: {
        reason: `${feature.label} records no head diameter, and the head is the whole of what this operation cuts.`,
        recommendations: [
          "Record the head diameter from the drawing or the fastener standard",
          "A 1/4-20 socket head takes a ⌀0.400 counterbore; the standard gives the rest",
        ],
      },
    };
  }
  if (head <= feature.diameter) {
    return {
      error: {
        reason: `${feature.label} records a ⌀${head.toFixed(4)} head on a ⌀${feature.diameter.toFixed(4)} hole. A head no larger than its own hole is not a head.`,
        recommendations: ["Check which of the two diameters is the head"],
      },
    };
  }

  const warnings: string[] = [];
  const moves: Move[] = [];
  const d = ctx.tool.diameter;

  if (feature.kind === "COUNTERSINK") {
    /*
     * A cone, cut by a cone. The tool's own included angle IS the angle of the
     * countersink — no depth or offset changes it — so a tool ground at the
     * wrong angle is refused rather than plunged deeper to make the diameter.
     */
    const want = feature.countersinkAngle ?? 82;
    if (ctx.tool.pointAngle == null) {
      return {
        error: {
          reason: `${ctx.tool.description} has no point angle recorded, and a countersink is cut by the tool's cone. Without it there is no way to know what angle this tool cuts.`,
          recommendations: [
            "Record the point angle on the tool — 82° is the inch standard, 90° the metric one",
            "The included angle is the full angle at the point",
          ],
        },
      };
    }
    if (Math.abs(ctx.tool.pointAngle - want) > 0.5) {
      return {
        error: {
          reason: `${feature.label} is a ${want}° countersink and ${ctx.tool.description} is ground at ${ctx.tool.pointAngle}°. The angle of a countersink is the angle of the cone that cuts it.`,
          recommendations: [`Use a ${want}° countersink`, `Change the drawing to ${ctx.tool.pointAngle}° if the angle is not functional`],
        },
      };
    }
    const tip = (ctx.tool.tipDiameter ?? 0) / 2;
    if (tip >= feature.diameter / 2) {
      return {
        error: {
          reason: `${ctx.tool.description} has a ${(tip * 2).toFixed(4)}" flat on its end and ${feature.label} is a ⌀${feature.diameter.toFixed(4)} hole. The tip will not enter it.`,
          recommendations: [`Use a countersink with a tip under ⌀${feature.diameter.toFixed(4)}`],
        },
      };
    }
    // Depth: where the cone's radius reaches the head. The flank stands off
    // the axis at half the included angle, so it gains tan(half) per unit down.
    const half = ((ctx.tool.pointAngle / 2) * Math.PI) / 180;
    const z = req.topZ - (head / 2 - tip) / Math.tan(half);
    moves.push({ type: "RAPID", x: feature.centerX, y: feature.centerY, z: req.clearanceZ, feed: null });
    moves.push({ type: "PLUNGE", x: feature.centerX, y: feature.centerY, z, feed: p.plungeFeed });
    moves.push({ type: "RETRACT", x: feature.centerX, y: feature.centerY, z: req.retractZ, feed: null });
    // A truncated cone from the hole to the head, over the depth it takes.
    const drop = req.topZ - z;
    const removed = (Math.PI * drop) / 3 * ((head / 2) ** 2 + (head / 2) * (feature.diameter / 2) + (feature.diameter / 2) ** 2);
    return { moves, removed: Math.max(0, removed), warnings };
  }

  /* ---- Counterbore: a flat-bottomed circle at the head diameter ---- */

  const depth = feature.headDepth;
  if (depth == null || !(depth > 0)) {
    return {
      error: {
        reason: `${feature.label} records no counterbore depth. A head that sits proud is the failure this feature exists to prevent, and a depth nobody wrote down is not a shallow one.`,
        recommendations: ["Record the counterbore depth from the drawing", "Flush usually means the head height plus a few thou"],
      },
    };
  }
  if (d > head) {
    return {
      error: {
        reason: `${feature.label} is a ⌀${head.toFixed(4)} counterbore and the tool is ⌀${d.toFixed(4)}. It does not fit.`,
        recommendations: [`Use a tool ⌀${head.toFixed(4)} or smaller`, "Use a piloted counterbore of the finished size"],
      },
    };
  }

  /*
   * The DEPTH is the counterbore's, not the operation's `finalZ` — the pilot
   * beneath it goes right through the part, and a head cut to the pilot's Z
   * would take the whole thickness out at the head diameter.
   */
  const passes = Math.max(1, Math.ceil(depth / p.stepdown));
  const stepover = d * p.stepover;
  const maxRadius = head / 2 - d / 2;

  moves.push({ type: "RAPID", x: feature.centerX, y: feature.centerY, z: req.clearanceZ, feed: null });

  /*
   * STRAIGHT DOWN THE PILOT.
   *
   * Everywhere else in this engine an end mill helixes into solid material,
   * because a standard mill has no cutting edge at its centre and plunging one
   * rubs rather than cuts. A counterbore is the case where that does not apply:
   * the tool is concentric with a hole that already exists, so its axis is over
   * open air and the cutting happens on the annulus outside the pilot. It is
   * what every machinist does, and it is why the sequencing table puts the head
   * after the drill rather than beside it.
   *
   * A ⌀0.400 counterbore with a ⌀0.375 mill leaves 0.0125" of radius to move
   * in, which no helix fits — and needs none.
   */
  moves.push({ type: "PLUNGE", x: feature.centerX, y: feature.centerY, z: req.topZ, feed: p.plungeFeed });

  for (let pass = 1; pass <= passes; pass++) {
    const z = req.topZ - (depth * pass) / passes;
    moves.push({ type: "PLUNGE", x: feature.centerX, y: feature.centerY, z, feed: p.plungeFeed });
    for (let rad = stepover; rad <= maxRadius + 1e-6; rad += stepover) {
      ringMoves(moves, feature.centerX, feature.centerY, Math.min(rad, maxRadius), z, p.feed);
    }
    if (pass === passes && maxRadius > 1e-6) {
      ringMoves(moves, feature.centerX, feature.centerY, maxRadius, z, Math.round(p.feed * 0.7));
    }
  }
  moves.push({ type: "RETRACT", x: feature.centerX, y: feature.centerY, z: req.retractZ, feed: null });

  if (Math.abs(d - head) < 1e-9) {
    warnings.push(
      `The cutter is the finished size of the counterbore, so the bore is whatever the tool measures and there is nothing to adjust at the control. A smaller mill interpolating it holds size on a D offset instead.`,
    );
  }

  const removed = Math.PI * ((head / 2) ** 2 - (feature.diameter / 2) ** 2) * depth;
  return { moves, removed: Math.max(0, removed), warnings };
}

/* ------------------------------------------------------------------ */
/* CHAMFER                                                             */
/* ------------------------------------------------------------------ */

function chamferToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
  if (feature.kind !== "CHAMFER") {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind} and is not a chamfer.`,
        recommendations: ["Point the operation at the chamfer feature"],
      },
    };
  }

  const geo = chamferGeometry(feature, ctx.tool);
  if ("error" in geo) return geo;
  const edge = chamferEdge(feature, ctx.partFeatures);
  if ("error" in edge) return edge;

  const moves: Move[] = [];
  const warnings: string[] = [];
  // A chamfer is a light finishing cut taken with the flank of a cone. It runs
  // at the finishing chipload, not the roughing one the operation inherited.
  const feed = Math.round(p.feed * 0.8);
  const z = geo.z;

  /*
   * The Z here is the ENGINE's, derived from the chamfer width and the tool's
   * own cone, not the operation's `finalZ`. A depth typed into a plan cannot
   * produce a chamfer of a stated width except by coincidence — the two are
   * locked together by the geometry — and the plan carries the same number
   * because the planner asks this same function for it.
   */
  if (Math.abs(req.finalZ - z) > 1e-6) {
    warnings.push(
      `Cutting at Z${z.toFixed(4)} rather than the planned Z${req.finalZ.toFixed(4)}: the depth of a chamfer is set by its width and the tool's angle, not chosen.`,
    );
  }

  if (edge.kind === "HOLES") {
    let cut = 0;
    for (const hole of edge.holes) {
      const rTool = hole.diameter / 2 - geo.offset;
      if (geo.tipRadius >= hole.diameter / 2) {
        return {
          error: {
            reason: `${ctx.tool.description} has a ${(geo.tipRadius * 2).toFixed(4)}" flat on its end and ${hole.label} is ⌀${hole.diameter.toFixed(4)}. The tip will not enter the hole, so it cannot break that edge.`,
            recommendations: [
              `Use a chamfer mill with a tip under ⌀${hole.diameter.toFixed(4)}`,
              "Spot the chamfer with a spotting drill of the same included angle",
            ],
          },
        };
      }
      moves.push({ type: "RAPID", x: hole.x, y: hole.y, z: req.clearanceZ, feed: null });
      if (rTool > MIN_CHAMFER_ARC) {
        /*
         * Big enough to interpolate: down the middle, out to the circle, round
         * it, back to the middle. Two 180° arcs, because a G2 with I/J and no
         * end point means "full circle" on a Haas and means something else or
         * nothing elsewhere.
         */
        moves.push({ type: "PLUNGE", x: hole.x, y: hole.y, z, feed: p.plungeFeed });
        moves.push({ type: "CUT", x: hole.x + rTool, y: hole.y, z, feed });
        moves.push(arcMove("CUT", { x: hole.x + rTool, y: hole.y }, hole.x, hole.y, { x: hole.x - rTool, y: hole.y, z }, false, feed));
        moves.push(arcMove("CUT", { x: hole.x - rTool, y: hole.y }, hole.x, hole.y, { x: hole.x + rTool, y: hole.y, z }, false, feed));
        moves.push({ type: "CUT", x: hole.x, y: hole.y, z, feed });
      } else {
        /*
         * Too small to circle in — the cone forms the whole chamfer on the way
         * down, which is how a small hole gets chamfered and is what a
         * spotting drill does. The depth is different: the chamfer's top edge
         * is where the cone's radius reaches half the hole plus the width, so
         * that is what sets Z rather than the flank-on-the-line construction.
         */
        const plungeZ = -(hole.diameter / 2 + feature.width - geo.tipRadius) * geo.tanAngle;
        moves.push({ type: "PLUNGE", x: hole.x, y: hole.y, z: plungeZ, feed: p.plungeFeed });
        moves.push({ type: "RETRACT", x: hole.x, y: hole.y, z: req.clearanceZ, feed: null });
        cut += Math.PI * hole.diameter * feature.width * geo.drop * 0.5;
        continue;
      }
      moves.push({ type: "RETRACT", x: hole.x, y: hole.y, z: req.clearanceZ, feed: null });
      cut += Math.PI * hole.diameter * feature.width * geo.drop * 0.5;
    }
    moves.push({ type: "RETRACT", x: moves[moves.length - 1].x, y: moves[moves.length - 1].y, z: req.retractZ, feed: null });
    return { moves, removed: cut, warnings };
  }

  /* ---- A closed boundary: the outside profile, or a pocket ---- */

  let path: Chain;
  if (edge.kind === "POCKET") {
    // Inward, so the boundary shrinks by the offset on every side. A corner
    // the offset cannot fit inside is a corner this tool cannot get into, and
    // that is the same refusal the pocket itself makes.
    const pk = edge.pocket;
    if (pk.cornerRadius - geo.offset <= 0 || pk.width - 2 * geo.offset <= 0 || pk.length - 2 * geo.offset <= 0) {
      return {
        error: {
          reason: `Breaking the edge of ${pk.label} puts the cutter centre ${geo.offset.toFixed(4)}" inside the wall, and the pocket's R${pk.cornerRadius.toFixed(4)} corner has no room for it.`,
          recommendations: [
            "Use a chamfer mill with a smaller tip",
            "Open the pocket's corner radius",
            "Break this edge by hand",
          ],
        },
      };
    }
    const shrunk = rectangleChain(pk.width - 2 * geo.offset, pk.length - 2 * geo.offset, pk.cornerRadius - geo.offset);
    path = {
      start: { x: shrunk.start.x + pk.centerX, y: shrunk.start.y + pk.centerY },
      segments: shrunk.segments.map((seg) =>
        seg.kind === "LINE"
          ? { kind: "LINE" as const, to: { x: seg.to.x + pk.centerX, y: seg.to.y + pk.centerY } }
          : {
              kind: "ARC" as const,
              to: { x: seg.to.x + pk.centerX, y: seg.to.y + pk.centerY },
              center: { x: seg.center.x + pk.centerX, y: seg.center.y + pk.centerY },
              cw: seg.cw,
            },
      ),
    };
  } else {
    const outer = offsetChain(edge.chain, geo.offset);
    if ("error" in outer) return outer;
    path = outer;
  }

  moves.push({ type: "RAPID", x: path.start.x, y: path.start.y, z: req.clearanceZ, feed: null });
  moves.push({ type: "PLUNGE", x: path.start.x, y: path.start.y, z, feed: p.plungeFeed });
  moves.push(...chainMoves(path, z, feed));
  moves.push({ type: "RETRACT", x: path.start.x, y: path.start.y, z: req.retractZ, feed: null });

  // The chamfer is a triangular prism along the edge: half the width by the
  // drop, run round the perimeter.
  return { moves, removed: chainLength(path) * feature.width * geo.drop * 0.5, warnings };
}

/** Below this the tool cannot usefully circle a hole, so it plunges instead. */
const MIN_CHAMFER_ARC = 0.005;

/* ------------------------------------------------------------------ */
/* ENGRAVE                                                             */
/* ------------------------------------------------------------------ */

function engraveToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number } {
  const moves: Move[] = [];
  if (feature.kind !== "ENGRAVING") return { moves, removed: 0 };

  // Phase 1 engraves a single-stroke box per glyph cell. Real single-line font
  // vectorisation is a Phase 2 item — see /docs/CANVAS_ROADMAP.md.
  const chars = feature.text.length;
  const cellW = feature.height * 0.62;
  const totalW = chars * cellW;
  const startX = feature.centerX - totalW / 2;
  const feed = Math.round(p.feed * 0.5);

  for (let i = 0; i < chars; i++) {
    if (feature.text[i] === " ") continue;
    const x0 = startX + i * cellW + cellW * 0.1;
    const x1 = startX + (i + 1) * cellW - cellW * 0.1;
    const y0 = feature.centerY - feature.height / 2;
    const y1 = feature.centerY + feature.height / 2;
    moves.push({ type: "RAPID", x: x0, y: y0, z: req.clearanceZ, feed: null });
    moves.push({ type: "PLUNGE", x: x0, y: y0, z: req.finalZ, feed: p.plungeFeed });
    moves.push({ type: "CUT", x: x1, y: y0, z: req.finalZ, feed });
    moves.push({ type: "CUT", x: x1, y: y1, z: req.finalZ, feed });
    moves.push({ type: "CUT", x: x0, y: y1, z: req.finalZ, feed });
    moves.push({ type: "CUT", x: x0, y: y0, z: req.finalZ, feed });
    moves.push({ type: "RETRACT", x: x0, y: y0, z: req.retractZ, feed: null });
  }

  return { moves, removed: chars * cellW * feature.height * feature.depth * 0.1 };
}

/* ------------------------------------------------------------------ */
/* Cycle time — measured from the actual moves                         */
/* ------------------------------------------------------------------ */

/**
 * Cycle time from the moves themselves.
 *
 * An arc is measured along the arc, not across its chord. Once circles became
 * real arcs, a straight-line measure would have read a full bore ring as its
 * diameter — every circular cut in the program shorter than it is, and the
 * quoted cycle time short with it.
 */
export function cycleTime(moves: Move[], rapidRate: number): { minutes: number; cuttingDistance: number } {
  let minutes = 0;
  let cuttingDistance = 0;
  for (let i = 1; i < moves.length; i++) {
    const a = moves[i - 1];
    const b = moves[i];
    const geo = arcGeometry(a, b);
    const dist = geo ? geo.length : Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
    if (dist === 0) continue;
    const rate = b.feed ?? rapidRate;
    minutes += dist / Math.max(rate, 1);
    if (b.feed !== null) cuttingDistance += dist;
  }
  return { minutes: Number(minutes.toFixed(3)), cuttingDistance };
}

export function totalCycleTime(toolpaths: Toolpath[], toolChangeSeconds = 8): number {
  const cut = toolpaths.reduce((s, t) => s + t.cycleTimeMinutes, 0);
  const changes = new Set(toolpaths.map((t) => t.toolNumber)).size;
  return Number((cut + (changes * toolChangeSeconds) / 60).toFixed(2));
}

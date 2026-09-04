import type { Feature, Stock } from "@/lib/domain/features";
import { canReach, fitsInternalCorner } from "@/lib/domain/shop";
import type {
  CuttingParameters,
  MachiningContext,
  Move,
  OperationRequest,
  Toolpath,
  ToolpathError,
  ToolpathResult,
} from "./types";
import { IMPLEMENTED_OPERATIONS, PLACEHOLDER_OPERATIONS } from "./types";

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

  const params = deriveCuttingParameters(cuttable, req.overrides, req.type === "CHAMFER" || req.type === "ENGRAVE");
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
      break;
    }
    case "CONTOUR_2D": {
      if (!feature) return missingFeature(req);
      const r = contourToolpath(req, feature, ctx, params);
      if ("error" in r) return { ok: false, error: { operationId: req.id, ...r.error } };
      moves = r.moves;
      removed = r.removed;
      break;
    }
    case "CHAMFER": {
      if (!feature) return missingFeature(req);
      const r = chamferToolpath(req, feature, ctx, params, stock);
      moves = r.moves;
      removed = r.removed;
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
      const entry = helicalEntry(cx, cy, d, pass === 1 ? req.topZ : prevZ, z, req.clearanceZ, p.plungeFeed, diameter / 2 - r - leave);
      if (!entry) return helixRefusal(d, `⌀${diameter.toFixed(4)} pocket`);
      moves.push(...entry);
      const maxRadius = diameter / 2 - r - leave;
      for (let rad = stepover; rad <= maxRadius + 1e-6; rad += stepover) {
        ringMoves(moves, cx, cy, Math.min(rad, maxRadius), z, p.feed);
      }
      // Finish wall pass, full depth, no stock left.
      if (pass === passes) {
        moves.push({ type: "LEAD_IN", x: cx + diameter / 2 - r - leave, y: cy, z, feed: p.feed });
        ringMoves(moves, cx, cy, diameter / 2 - r, z, Math.round(p.feed * 0.7));
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

  const area = circular ? Math.PI * (diameter / 2) ** 2 : width * length;
  return { moves, removed: area * totalDepth, warnings };
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
  const steps = revs * 24;
  const out: Move[] = [{ type: "RAPID", x: cx + radius, y: cy, z: clearanceZ, feed: null }];
  for (let i = 1; i <= steps; i++) {
    const a = (i / 24) * Math.PI * 2;
    out.push({
      type: "PLUNGE",
      x: cx + radius * Math.cos(a),
      y: cy + radius * Math.sin(a),
      z: Math.max(toZ, fromZ - (depth * i) / steps),
      feed: plungeFeed,
    });
  }
  // Close to centre at depth so the clearing pattern starts where it expects.
  out.push({ type: "CUT", x: cx, y: cy, z: toZ, feed: plungeFeed });
  return out;
}

function ringMoves(moves: Move[], cx: number, cy: number, radius: number, z: number, feed: number) {
  if (radius <= 0) return;
  const segments = Math.max(24, Math.round(radius * 60));
  moves.push({ type: "CUT", x: cx + radius, y: cy, z, feed });
  for (let i = 1; i <= segments; i++) {
    const a = (i / segments) * Math.PI * 2;
    moves.push({ type: "CUT", x: cx + radius * Math.cos(a), y: cy + radius * Math.sin(a), z, feed });
  }
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
  const corner = (x: number, y: number, sx: number, sy: number) => {
    if (rr <= 0) {
      moves.push({ type: "CUT", x, y, z, feed });
      return;
    }
    const steps = 8;
    const startAngle = Math.atan2(sy, sx);
    for (let i = 0; i <= steps; i++) {
      const a = startAngle + (i / steps) * (Math.PI / 2);
      moves.push({ type: "CUT", x: x + rr * Math.cos(a), y: y + rr * Math.sin(a), z, feed });
    }
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
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
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

  moves.push({ type: "RAPID", x: feature.centerX, y: feature.centerY, z: req.clearanceZ, feed: null });
  if (peck) {
    const peckDepth = ctx.tool.diameter * 0.75;
    let z = req.topZ;
    while (z > req.finalZ + 1e-6) {
      z = Math.max(req.finalZ, z - peckDepth);
      moves.push({ type: "PLUNGE", x: feature.centerX, y: feature.centerY, z, feed: drillFeed });
      moves.push({ type: "RETRACT", x: feature.centerX, y: feature.centerY, z: req.topZ + 0.05, feed: null });
    }
  } else {
    moves.push({ type: "PLUNGE", x: feature.centerX, y: feature.centerY, z: req.finalZ, feed: drillFeed });
  }
  moves.push({ type: "RETRACT", x: feature.centerX, y: feature.centerY, z: req.retractZ, feed: null });

  const removed = Math.PI * (ctx.tool.diameter / 2) ** 2 * depth;
  return { moves, removed, warnings };
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
    // Archimedean spiral: radius grows by exactly ae per revolution.
    const revs = Math.max(1, Math.ceil(maxR / ae));
    const segsPerRev = 48;
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
  for (let i = 1; i <= entryRevs * 24; i++) {
    const a = (i / 24) * Math.PI * 2;
    const zz = Math.max(z, req.topZ - (totalDepth * i) / (entryRevs * 24));
    entry.push({ type: "PLUNGE", x: cx + he * Math.cos(a), y: cy + he * Math.sin(a), z: zz, feed: p.plungeFeed });
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
    const segments = Math.max(24, Math.round(pathR * 60));
    const helixFeed = Math.round(p.feed * 0.65);

    moves.push({ type: "RAPID", x: cx, y: cy, z: req.clearanceZ, feed: null });
    moves.push({ type: "PLUNGE", x: cx, y: cy, z: req.topZ + 0.02, feed: p.plungeFeed });
    moves.push({ type: "LEAD_IN", x: cx + pathR, y: cy, z: req.topZ + 0.02, feed: helixFeed });
    for (let rev = 0; rev < revs; rev++) {
      const zStart = req.topZ - (depth * rev) / revs;
      const zEnd = req.topZ - (depth * (rev + 1)) / revs;
      for (let i = 1; i <= segments; i++) {
        const a = (i / segments) * Math.PI * 2;
        moves.push({
          type: "CUT",
          x: cx + pathR * Math.cos(a),
          y: cy + pathR * Math.sin(a),
          z: Math.max(req.finalZ, zStart + ((zEnd - zStart) * i) / segments),
          feed: helixFeed,
        });
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

function tapToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number; warnings: string[] } | { error: { reason: string; recommendations: string[] } } {
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
  return { moves, removed: 0, warnings };
}

/* ------------------------------------------------------------------ */
/* 2D CONTOUR — outside profile with tangential lead in/out            */
/* ------------------------------------------------------------------ */

function contourToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
): { moves: Move[]; removed: number } | { error: { reason: string; recommendations: string[] } } {
  if (feature.kind !== "OUTSIDE_CONTOUR") {
    return {
      error: {
        reason: `${feature.label} is a ${feature.kind}; 2D contour requires an outside contour feature.`,
        recommendations: ["Select the outside contour feature"],
      },
    };
  }

  const moves: Move[] = [];
  const r = ctx.tool.diameter / 2;
  const totalDepth = req.topZ - req.finalZ;
  const passes = Math.max(1, Math.ceil(totalDepth / p.stepdown));

  // Cutter compensation applied in the path: offset outward by tool radius.
  const w = feature.width + ctx.tool.diameter;
  const l = feature.length + ctx.tool.diameter;
  const cr = feature.cornerRadius + r;
  const leadRadius = Math.max(r, 0.1);

  for (let pass = 1; pass <= passes; pass++) {
    const z = req.topZ - (totalDepth * pass) / passes;
    moves.push({ type: "RAPID", x: -w / 2 - leadRadius * 2, y: -l / 2 + cr, z: req.clearanceZ, feed: null });
    moves.push({ type: "PLUNGE", x: -w / 2 - leadRadius * 2, y: -l / 2 + cr, z, feed: p.plungeFeed });
    moves.push({ type: "LEAD_IN", x: -w / 2, y: -l / 2 + cr, z, feed: Math.round(p.feed * 0.6) });
    rectMoves(moves, 0, 0, w, l, cr, z, p.feed);
    moves.push({ type: "LEAD_OUT", x: -w / 2 - leadRadius * 2, y: -l / 2 + cr, z, feed: Math.round(p.feed * 0.6) });
    moves.push({ type: "RETRACT", x: -w / 2 - leadRadius * 2, y: -l / 2 + cr, z: req.retractZ, feed: null });
  }

  const perimeter = 2 * (feature.width + feature.length);
  return { moves, removed: perimeter * ctx.tool.diameter * totalDepth * 0.5 };
}

/* ------------------------------------------------------------------ */
/* CHAMFER                                                             */
/* ------------------------------------------------------------------ */

function chamferToolpath(
  req: OperationRequest,
  feature: Feature,
  ctx: MachiningContext,
  p: CuttingParameters,
  stock: Stock,
): { moves: Move[]; removed: number } {
  const moves: Move[] = [];
  const z = req.finalZ;
  const feed = Math.round(p.feed * 0.8);

  if (feature.kind === "CHAMFER" && feature.applyTo === "HOLES") {
    // Chamfer pass at each hole is emitted by the caller as separate ops in a
    // full implementation; Phase 1 rings the outside profile.
    moves.push({ type: "RAPID", x: 0, y: 0, z: req.clearanceZ, feed: null });
    moves.push({ type: "PLUNGE", x: 0, y: 0, z, feed: p.plungeFeed });
    moves.push({ type: "RETRACT", x: 0, y: 0, z: req.retractZ, feed: null });
    return { moves, removed: 0.001 };
  }

  const w = stock.x + ctx.tool.diameter * 0.25;
  const l = stock.y + ctx.tool.diameter * 0.25;
  moves.push({ type: "RAPID", x: -w / 2, y: -l / 2, z: req.clearanceZ, feed: null });
  moves.push({ type: "PLUNGE", x: -w / 2, y: -l / 2, z, feed: p.plungeFeed });
  rectMoves(moves, 0, 0, w, l, 0.1, z, feed);
  moves.push({ type: "RETRACT", x: -w / 2, y: -l / 2, z: req.retractZ, feed: null });

  return { moves, removed: 2 * (stock.x + stock.y) * 0.01 * 0.01 };
}

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

export function cycleTime(moves: Move[], rapidRate: number): { minutes: number; cuttingDistance: number } {
  let minutes = 0;
  let cuttingDistance = 0;
  for (let i = 1; i < moves.length; i++) {
    const a = moves[i - 1];
    const b = moves[i];
    const dist = Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
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

import type { Feature, Stock } from "@/lib/domain/features";
import { canReach, fitsInternalCorner } from "@/lib/domain/shop";
import type {
  CuttingParameters,
  MachiningContext,
  Move,
  OperationRequest,
  Toolpath,
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

export function deriveCuttingParameters(
  ctx: MachiningContext,
  overrides: Partial<CuttingParameters> = {},
  finishing = false,
): CuttingParameters {
  const { tool } = ctx;

  // Use the intersection of the tool's rated window and the material's window.
  const sfm = clamp(
    (Math.max(tool.sfmMin, ctx.materialSfmMin) + Math.min(tool.sfmMax, ctx.materialSfmMax)) / 2,
    Math.min(tool.sfmMin, ctx.materialSfmMin),
    Math.max(tool.sfmMax, ctx.materialSfmMax),
  );

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

/* ------------------------------------------------------------------ */
/* Entry point                                                         */
/* ------------------------------------------------------------------ */

export function generateToolpath(
  req: OperationRequest,
  feature: Feature | null,
  ctx: MachiningContext,
  stock: Stock,
): ToolpathResult {
  const params = deriveCuttingParameters(ctx, req.overrides, req.type === "CHAMFER" || req.type === "ENGRAVE");
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

  for (let pass = 1; pass <= passes; pass++) {
    const z = req.topZ - (totalDepth * pass) / passes;

    if (circular) {
      // Helical entry at centre, then concentric rings outward.
      moves.push({ type: "RAPID", x: cx, y: cy, z: req.clearanceZ, feed: null });
      moves.push({ type: "PLUNGE", x: cx, y: cy, z, feed: p.plungeFeed });
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
      moves.push({ type: "RAPID", x: cx, y: cy, z: req.clearanceZ, feed: null });
      moves.push({ type: "PLUNGE", x: cx, y: cy, z, feed: p.plungeFeed });
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
  }

  if (leave > 0 && passes > 1) {
    warnings.push(`${leave.toFixed(3)}" left on the walls for the finish pass.`);
  }

  const area = circular ? Math.PI * (diameter / 2) ** 2 : width * length;
  return { moves, removed: area * totalDepth, warnings };
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

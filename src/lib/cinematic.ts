/**
 * CINEMATIC TOOLPATH — prompt and storyboard generation
 *
 * Builds an AI-video prompt from structured CANVAS state: real operations,
 * real tools, real cycle-time proportions. It is a COMMUNICATION artifact —
 * customer explainer, training clip, investor demo — and it says so on
 * every output: CINEMATIC PREVIEW — NOT NC VERIFICATION. Nothing here reads
 * or writes a gate, and nothing here verifies anything.
 *
 * Two rules:
 * 1. No hallucination. A value CANVAS does not hold is written "unspecified"
 *    or omitted — the prompt never invents a material, a dimension or a
 *    machine to look complete.
 * 2. Customer-safe mode strips identity and dimensions by construction:
 *    part/program numbers dropped, feature labels replaced by generic
 *    process nouns, material reduced to its family. The un-safe prompt is
 *    never emitted when the mode is on.
 */

export interface CinematicOp {
  id: string;
  label: string;
  type: string;
  toolDescription: string | null;
  cycleMinutes: number | null;
}

export interface CinematicInput {
  partName: string;
  partNumber: string | null;
  material: string | null;
  /** Which process family the shots should speak. Defaults to MILL. */
  process?: "MILL" | "TURN";
  stock: { x: number; y: number; z: number } | null;
  /** Turning stock — a bar, spoken as ⌀ × length. Used when process is TURN. */
  barStock?: { diameter: number; length: number } | null;
  setupName: string | null;
  workholding: string | null;
  hasSoftJaws: boolean;
  readiness: string | null;
  operations: CinematicOp[];
}

export interface CinematicSettings {
  durationSeconds: 10 | 15 | 30;
  style:
    | "PREMIUM_PRODUCT_RENDER"
    | "SHOP_FLOOR_REALISM"
    | "CUSTOMER_EXPLAINER"
    | "OPERATOR_TRAINING"
    | "INVESTOR_DEMO"
    | "TECHNICAL_MINIMAL";
  include: {
    softJaws: boolean;
    stock: boolean;
    toolAndHolder: boolean;
    toolpathTrace: boolean;
    materialRemoval: boolean;
    datumLabels: boolean;
    measurementOverlays: boolean;
    operationLabels: boolean;
    coolantChips: boolean;
    finalReveal: boolean;
  };
  customerSafe: boolean;
}

export interface Shot {
  start: number;
  end: number;
  operation: string;
  visual: string;
  camera: string;
  overlays: string[];
}

export interface CinematicResult {
  title: string;
  prompt: string;
  shortPrompt: string;
  shots: Shot[];
  constraints: string[];
  disclaimer: string;
  storyboard: {
    title: string;
    part: string;
    material: string;
    durationSeconds: number;
    style: string;
    selectedOperations: string[];
    shots: Shot[];
    disclaimer: string;
  };
}

export const DISCLAIMER = "Cinematic preview only. Not NC verification.";

export const STYLE_LABEL: Record<CinematicSettings["style"], string> = {
  PREMIUM_PRODUCT_RENDER: "Premium Product Render",
  SHOP_FLOOR_REALISM: "Shop Floor Realism",
  CUSTOMER_EXPLAINER: "Customer Explainer",
  OPERATOR_TRAINING: "Operator Training",
  INVESTOR_DEMO: "Investor Demo",
  TECHNICAL_MINIMAL: "Technical Minimal",
};

const STYLE_DIRECTION: Record<CinematicSettings["style"], string> = {
  PREMIUM_PRODUCT_RENDER:
    "Premium product film: clean white-to-graphite studio, soft key light, long lens, shallow depth of field, Apple/Leica restraint.",
  SHOP_FLOOR_REALISM:
    "Documentary shop-floor realism: machine enclosure interior, work lamp warmth, coolant sheen on surfaces, honest wear on the fixtures.",
  CUSTOMER_EXPLAINER:
    "Calm explanatory pacing: one idea per shot, generous hold times, annotations fade in and out, nothing rushed.",
  OPERATOR_TRAINING:
    "Instructional clarity: locked-off camera angles an operator would stand at, every motion legible, overlays name what matters before it happens.",
  INVESTOR_DEMO:
    "Confident product storytelling: decisive cuts, the part is the hero, end on the finished component under premium light.",
  TECHNICAL_MINIMAL:
    "Technical minimalism: neutral ground, no camera drift, precise orthographic-leaning angles, annotation over atmosphere.",
};

/** §6 — operation type → what the camera sees. Generic verbs, real nouns. */
function shotVisual(op: CinematicOp, include: CinematicSettings["include"], safe: boolean, process: "MILL" | "TURN" = "MILL"): string {
  const tool = !safe && op.toolDescription ? ` (${op.toolDescription})` : "";
  const trace = include.toolpathTrace ? " following a precision-blue toolpath trace" : "";
  const removal = include.materialRemoval ? ", material peeling away pass by pass" : "";
  switch (op.type) {
    case "FACE":
      return process === "TURN"
        ? `Facing insert${tool} sweeps from the spinning bar's edge to center${trace}; a clean true face appears in one pass${removal}.`
        : `Face mill${tool} sweeps across the top face${trace}; a fresh machined surface appears behind it${removal}.`;
    case "POCKET_2D":
    case "ADAPTIVE_2D":
      return `End mill${tool} spirals through the pocket${trace}${removal}; walls and floor emerge crisp.`;
    case "DRILL":
    case "PECK_DRILL":
      return `Drill${tool} descends; the hole appears with a clean entry${include.measurementOverlays ? ", depth callout fading in" : ""}.`;
    case "BORE":
      return `Boring tool${tool} enters along the bore axis; the wall comes to final size${include.measurementOverlays ? " with a diameter callout" : ""}.`;
    case "TAP":
      return `Tap${tool} feeds in synchronised rotation; threads catch the light on retract.`;
    case "CONTOUR_2D":
      return `End mill${tool} traces the outside profile${trace}; the finished silhouette separates from the stock${removal}.`;
    case "CHAMFER":
      return `Chamfer tool${tool} breaks the edges; a bright, even chamfer line follows it around the part.`;
    case "ENGRAVE":
      return `Engraver${tool} inscribes the marking; fine chips lift from the surface.`;
    /* ---- turning: the bar spins, the tool is still ---- */
    case "OD_ROUGH":
      return `Roughing insert${tool} strips the spinning bar down pass by pass${trace}; a ribbon of chip clears the cut${removal}.`;
    case "OD_FINISH":
      return `Finishing insert${tool} takes one continuous light pass along the spinning journal${trace}; the surface comes up to a mirror-fine turn${include.measurementOverlays ? ", diameter callout fading in" : ""}.`;
    case "GROOVE_OD":
      return `Grooving insert${tool} plunges square into the spinning diameter; the groove walls appear in one decisive motion.`;
    case "THREAD_OD":
      return `Threading insert${tool} traces the helix in repeated synchronised passes${trace}; the thread form deepens visibly each pass, never in one.`;
    case "PART_OFF":
      return `Parting blade${tool} feeds steadily toward center; the finished part separates and is caught cleanly.`;
    case "CENTER_DRILL":
      return `Center drill${tool} kisses the spinning face on the axis of rotation; a precise conical seat appears.`;
    case "ID_DRILL":
      return `Drill${tool} advances along the spindle centerline into the spinning bar; chips evacuate up the flutes.`;
    case "ID_BORE_ROUGH":
    case "ID_BORE_FINISH":
      return `Boring bar${tool} reaches inside the spinning bore${trace}; the internal wall comes to size${include.measurementOverlays ? " with a bore callout" : ""}.`;
    default:
      return `${op.label}: the tool${tool} performs the operation${trace}.`;
  }
}

const CONSTRAINTS: string[] = [
  "Photorealistic machining; physically believable tool motion and speeds.",
  "Real metal behaviour — chips, not sparks, unless the process genuinely sparks.",
  "Correct scale throughout; the part is the size the dimensions imply.",
  "No cartoon look, no fantasy effects, no sci-fi glow, no generic AI aesthetic.",
  "No machines, tools or text overlays other than those described.",
  "Precision-blue annotations only; clean white/graphite environment; aerospace-metrology restraint.",
];

const safeNoun = (op: CinematicOp): string => {
  switch (op.type) {
    case "FACE": return "Facing pass";
    case "POCKET_2D": case "ADAPTIVE_2D": return "Pocket milling";
    case "DRILL": case "PECK_DRILL": return "Drilling";
    case "BORE": return "Precision boring";
    case "TAP": return "Thread tapping";
    case "CONTOUR_2D": return "Profile finishing";
    case "CHAMFER": return "Edge chamfering";
    case "ENGRAVE": return "Marking";
    case "OD_ROUGH": return "Rough turning";
    case "OD_FINISH": return "Finish turning";
    case "GROOVE_OD": return "Grooving";
    case "THREAD_OD": return "Thread turning";
    case "PART_OFF": return "Parting off";
    case "CENTER_DRILL": return "Center drilling";
    case "ID_DRILL": return "Drilling";
    case "ID_BORE_ROUGH": case "ID_BORE_FINISH": return "Precision boring";
    default: return "Machining operation";
  }
};

/** Material family only — "Aluminum 6061 · T6511" → "Aluminum". */
const materialFamily = (m: string | null): string | null => (m ? m.split(/[\s·]/)[0] : null);

export function generateCinematic(input: CinematicInput, settings: CinematicSettings): CinematicResult {
  const safe = settings.customerSafe;
  const process = input.process ?? "MILL";
  const ops = input.operations;
  const D = settings.durationSeconds;

  const partLabel = safe ? "Precision machined component" : input.partName + (input.partNumber ? ` (${input.partNumber})` : "");
  const material = safe ? materialFamily(input.material) : input.material;
  const opName = (o: CinematicOp) => (safe ? safeNoun(o) : o.label);

  /* ---- shot timing: intro + per-op (weighted by real cycle time) + reveal ---- */
  const intro = Math.max(1, Math.round(D * 0.15));
  const outro = settings.include.finalReveal ? Math.max(1, Math.round(D * 0.12)) : 0;
  const opWindow = D - intro - outro;
  const weights = ops.map((o) => Math.max(0.2, o.cycleMinutes ?? 0.5));
  const wSum = weights.reduce((a, b) => a + b, 0);

  const shots: Shot[] = [];
  const introBits = [
    settings.include.stock && process === "TURN" && input.barStock
      ? safe
        ? "a raw bar gripped in the chuck, beginning to spin"
        : `raw ${material ?? "metal"} bar, ⌀${input.barStock.diameter} × ${input.barStock.length} in, gripped in the chuck and coming up to speed`
      : settings.include.stock && input.stock
        ? safe
          ? "raw stock clamped and ready"
          : `raw ${material ?? "metal"} stock, ${input.stock.x} × ${input.stock.y} × ${input.stock.z} in`
        : "the setup, ready to cut",
    settings.include.softJaws && input.hasSoftJaws ? "machined soft jaws seating the part, contact faces highlighted" : null,
    input.workholding && !safe ? `held in the ${input.workholding}` : null,
  ].filter(Boolean);
  shots.push({
    start: 0,
    end: intro,
    operation: "Setup",
    visual: `Establishing shot: ${introBits.join("; ")}.`,
    camera: "Slow push-in from a three-quarter high angle.",
    overlays: [
      ...(settings.include.datumLabels ? ["datum origin marker"] : []),
      ...(settings.include.operationLabels ? ["setup title"] : []),
    ],
  });

  let t = intro;
  ops.forEach((o, i) => {
    const dur = i === ops.length - 1 ? D - outro - t : Math.max(1, Math.round((opWindow * weights[i]) / wSum));
    const end = Math.min(D - outro, t + dur);
    shots.push({
      start: t,
      end,
      operation: opName(o),
      visual: shotVisual(o, settings.include, safe, process),
      camera:
        process === "TURN"
          ? o.type === "PART_OFF" || o.type === "CENTER_DRILL" || o.type === "ID_DRILL"
            ? "Locked on the spindle axis, the rotation is the motion."
            : "Fixed cross-slide angle, long lens — the bar spins, the camera holds."
          : o.type === "DRILL" || o.type === "PECK_DRILL" || o.type === "TAP" || o.type === "BORE"
            ? "Low orbit locked to the spindle axis."
            : "Tracking shot following the cutter, long lens.",
      overlays: [
        ...(settings.include.operationLabels ? [opName(o)] : []),
        ...(settings.include.measurementOverlays && !safe ? ["dimension callout"] : []),
      ],
    });
    t = end;
  });

  if (outro > 0) {
    shots.push({
      start: t,
      end: D,
      operation: "Reveal",
      visual: "The finished component, deburred and clean, rotating slowly under premium product light.",
      camera: "Hero orbit, settling to a three-quarter beauty angle.",
      overlays: input.readiness && input.readiness !== "READY_TO_RUN" && settings.include.operationLabels ? ["Review Required marker"] : [],
    });
  }

  /* ---- prose prompt ---- */
  const lines: string[] = [];
  lines.push(`${STYLE_DIRECTION[settings.style]}`);
  lines.push(
    `A ${D}-second film of CNC machining: ${partLabel}${material ? `, ${material}` : ""}${
      !safe && input.setupName ? `, ${input.setupName.toLowerCase()}` : ""
    }.`,
  );
  if (settings.include.coolantChips) lines.push("Coolant mist and real chip formation where the tool cuts — restrained, never theatrical.");
  shots.forEach((s) => lines.push(`${s.start}–${s.end}s — ${s.operation}: ${s.visual} Camera: ${s.camera}${s.overlays.length ? ` Overlays: ${s.overlays.join(", ")}.` : ""}`));
  lines.push(`Constraints: ${CONSTRAINTS.join(" ")}`);

  const title = `Cinematic Toolpath — ${partLabel}`;
  const selectedOperations = ops.map(opName);

  return {
    title,
    prompt: lines.join("\n"),
    shortPrompt:
      `${D}s photorealistic CNC machining film, ${STYLE_LABEL[settings.style].toLowerCase()}: ${partLabel}` +
      `${material ? ` in ${material}` : ""} — ${selectedOperations.join(", ")}. Precision-blue toolpath accents, ` +
      `clean studio, real metal physics, no sparks, no sci-fi glow.`,
    shots,
    constraints: CONSTRAINTS,
    disclaimer: DISCLAIMER,
    storyboard: {
      title,
      part: partLabel,
      material: material ?? "unspecified",
      durationSeconds: D,
      style: STYLE_LABEL[settings.style],
      selectedOperations,
      shots,
      disclaimer: DISCLAIMER,
    },
  };
}

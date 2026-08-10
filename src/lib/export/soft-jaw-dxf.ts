import type { JawGeometry } from "@/lib/engines/workholding";
import { createDxf } from "./dxf";

/**
 * SOFT JAW DRAWING — DXF export
 *
 * Two views of one jaw, dimensioned enough to machine from:
 *
 *   FRONT — the jaw face as it sits in the vise. Blank outline, the seat
 *           opening from the top of the jaw down to the step, corner reliefs
 *           drawn as real arcs, and the stop edge where one exists.
 *   PLAN  — looking down. Blank width × thickness with the seat pocket depth
 *           into the face.
 *
 * The geometry is the generator's `JawGeometry`, verbatim — this file draws,
 * it does not re-derive. Layers: OUTLINE for the blank, CUT for machined
 * edges, NOTES for text. All dimensions inches.
 *
 * Honesty carried in the file itself: the 999 header and the NOTES layer say
 * DEVELOPMENT and say what is not modelled (bolt holes — the blank's pattern
 * is drilled already; thread reliefs). A drawing that leaves the shop must
 * carry its own caveats, because the file outlives the screen it came from.
 */

export function softJawDxf(
  geom: JawGeometry,
  meta: { partName: string; partNumber: string | null; setupName: string; generatedAtIso: string },
): string {
  const d = createDxf();
  const W = geom.blankWidth;
  const H = geom.blankHeight;
  const T = geom.blankThickness;
  const seatW = geom.seatWidth;
  const step = geom.stepDepth;
  const r = geom.seatCornerRadius;

  d.comment("CANVAS SOFT JAW — DEVELOPMENT. VERIFY BEFORE MACHINING.");
  d.comment(`JAW ${geom.side} — ${meta.partName}${meta.partNumber ? ` (${meta.partNumber})` : ""} — ${meta.setupName}`);
  d.comment(`GENERATED ${meta.generatedAtIso}. UNITS INCHES.`);
  d.comment("BOLT HOLES NOT DRAWN — USE THE BLANK'S EXISTING PATTERN.");

  /* ---------------- FRONT view, origin at blank bottom-left ---------------- */

  // Blank outline.
  rect(d, "OUTLINE", 0, 0, W, H);

  // Seat opening: from the top edge down `step`, centred, with corner
  // reliefs at the bottom corners drawn as quarter arcs.
  const x0 = W / 2 - seatW / 2;
  const x1 = W / 2 + seatW / 2;
  const yStep = H - step;
  // Vertical walls stop where the relief arcs begin.
  d.line("CUT", x0, H, x0, yStep + r);
  d.line("CUT", x1, H, x1, yStep + r);
  // Step floor between the arcs.
  d.line("CUT", x0 + r, yStep, x1 - r, yStep);
  // Reliefs: left corner sweeps 180°→270°, right corner 270°→360°.
  d.arc("CUT", x0 + r, yStep + r, r, 180, 270);
  d.arc("CUT", x1 - r, yStep + r, r, 270, 360);

  // Stop edge, where this jaw carries one. stopLocation is measured from the
  // seat centre; drawn as a vertical edge across the step band.
  if (geom.stopLocation !== null) {
    const xs = W / 2 + geom.stopLocation;
    d.line("CUT", xs, H, xs, yStep);
    d.text("NOTES", xs + 0.06, H - step / 2, 0.08, "STOP");
  }

  // Dimensions as text — plain, unambiguous, no dimension-entity dialects.
  d.text("NOTES", W / 2 - 0.9, H + 0.15, 0.1, `SEAT ${seatW.toFixed(3)} WIDE x ${step.toFixed(3)} STEP`);
  d.text("NOTES", x1 + 0.1, yStep + r, 0.08, `R${r.toFixed(3)} RELIEF (2)`);
  d.text("NOTES", 0, -0.25, 0.1, `FRONT — BLANK ${W.toFixed(2)} x ${H.toFixed(2)} x ${T.toFixed(2)}`);

  /* ---------------- PLAN view, offset below the front view ---------------- */

  const oy = -1.0 - T;
  rect(d, "OUTLINE", 0, oy, W, T);
  // Seat pocket depth into the face (the face the part touches is y = oy + T).
  const yPocket = oy + T - geom.seatDepth;
  d.line("CUT", x0, oy + T, x0, yPocket);
  d.line("CUT", x1, oy + T, x1, yPocket);
  d.line("CUT", x0, yPocket, x1, yPocket);
  d.text("NOTES", x1 + 0.1, yPocket, 0.08, `SEAT ${geom.seatDepth.toFixed(3)} DEEP`);
  d.text("NOTES", 0, oy - 0.25, 0.1, "PLAN — PART FACE AT TOP OF VIEW");

  d.text("NOTES", 0, oy - 0.55, 0.09, "CANVAS DEVELOPMENT DRAWING — VERIFY BEFORE MACHINING. INCHES.");

  return d.build();
}

function rect(d: ReturnType<typeof createDxf>, layer: string, x: number, y: number, w: number, h: number): void {
  d.line(layer, x, y, x + w, y);
  d.line(layer, x + w, y, x + w, y + h);
  d.line(layer, x + w, y + h, x, y + h);
  d.line(layer, x, y + h, x, y);
}

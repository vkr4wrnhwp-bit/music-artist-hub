import type { ManufacturingPackage } from "@/lib/package";
import type { FeatureKind } from "@/lib/domain/features";
import { GOVERNING_DIMENSION } from "@/lib/engines/inspection-plan";
import { assessCoverage } from "@/lib/engines/coverage";
import { PROGRAM_ORIGIN } from "@/lib/program-origin";
import { frameSentence } from "./engines/cam/setup-frame";

/**
 * THE SETUP SHEET
 *
 * CANVAS knew the stock, the vise, the jaw axis, the grip depth, the parallel
 * height, the orientation, the work offset, the tool list with stickout and
 * holder, the operation order, the predicted cycle time, the critical
 * dimensions and how each one is to be inspected — and printed none of it.
 * Which means that until now the program could not leave the office: you
 * cannot hand a second-shift machinist a program and nothing else.
 *
 * WHAT THIS IS NOT
 *
 * It is not an approval and it does not clear anything. It prints the gate
 * state as it stands, including the blocking gates, precisely so that a sheet
 * in somebody's hand is never mistaken for clearance to cut.
 *
 * ABSENCE IS PRINTED, NOT OMITTED
 *
 * The dangerous setup sheet is the one that leaves a field blank. A blank grip
 * depth reads as "no grip depth needed"; a missing parallel height reads as
 * "sits on the floor of the vise". So every unknown this sheet carries is
 * collected into `unknowns` and printed as a list a machinist has to resolve
 * at the machine — the same reason the engines return null and name what is
 * missing rather than substituting a default.
 *
 * The one number that is deliberately NOT restated here is the holding margin
 * verdict's arithmetic. The sheet says which geometry it was computed from —
 * PLANNED (what the approach generator intended) or MEASURED (what somebody
 * actually set) — because a margin computed from a planned grip describes a
 * setup nobody has built yet, and a machinist reading it at the vise needs to
 * know which of the two he is looking at.
 */

export interface SheetField {
  label: string;
  value: string | null;
}

export interface SheetTool {
  toolNumber: number;
  description: string;
  diameter: number;
  stickout: number;
  holder: string;
  /**
   * H and D registers. Both equal the tool number under the current post.
   *
   * D matters now that contours are cut with the control doing the offsetting:
   * it holds the cutter radius, and nudging it is how a machinist takes a thou
   * off a wall without re-posting. It has to reach the machine, which is why it
   * is on this sheet.
   */
  lengthOffset: number;
  pocket: number | null;
  operationLabels: string[];
}

export interface SheetOperation {
  sequence: number;
  label: string;
  type: string;
  /** ROUGH or FINISH. A machinist treats the two differently at the control. */
  pass: string;
  toolNumber: number | null;
  featureLabel: string | null;
  topZ: number;
  finalZ: number;
  rpm: number | null;
  feed: number | null;
  cycleMinutes: number | null;
  /** True when the toolpath engine produced no motion for this operation. */
  noMotion: boolean;
}

export interface SheetCharacteristic {
  label: string;
  nominal: string | null;
  tolerance: string | null;
  method: string | null;
}

export interface SetupSheet {
  part: { name: string; number: string | null; revision: string; material: string | null; condition: string | null };
  setup: { sequence: number; name: string; orientation: string; workOffset: string; machine: string | null };
  /**
   * `turned` is its own line because it is its own fact. A machinist reading
   * "BOTTOM" knows which face is up and not which way it got there, and the
   * two answers mirror different coordinates.
   */
  origin: { xy: string; z: string; turned: string | null; prose: string; datumNote: string | null };
  stock: SheetField[];
  workholding: SheetField[];
  /** PLANNED | MEASURED | null — what the grip numbers above actually describe. */
  geometrySource: string | null;
  holding: { level: string; margin: string | null } | null;
  tools: SheetTool[];
  operations: SheetOperation[];
  cycleMinutes: number | null;
  characteristics: SheetCharacteristic[];
  /** Features a person has said this program does not make. Instructions to somebody. */
  notMadeHere: { label: string; reason: string; by: string | null }[];
  /** Everything this sheet cannot tell the machinist, stated rather than left blank. */
  unknowns: string[];
  gateState: { overall: string; blocking: { label: string; detail: string }[] };
  /** Never absent. The post is a development post and the sheet says so. */
  developmentNotice: string;
}

const dim = (v: number | null | undefined, places = 3, unit = "″"): string | null =>
  v == null || !Number.isFinite(v) ? null : `${v.toFixed(places)}${unit}`;

const words = (s: string) => s.replace(/_/g, " ").toLowerCase();

export function buildSetupSheet(pkg: ManufacturingPackage, setupId: string): SetupSheet | null {
  const setup = pkg.setups.find((s) => s.id === setupId);
  if (!setup) return null;

  const unknowns: string[] = [];
  const note = (missing: string | null | undefined, sentence: string) => {
    if (missing == null || missing === "") unknowns.push(sentence);
  };

  /* ---------------- Stock ---------------- */

  const st = pkg.revision.stock;
  const stock: SheetField[] = st
    ? [
        { label: "Size", value: `${st.x.toFixed(3)} × ${st.y.toFixed(3)} × ${st.z.toFixed(3)}″` },
        { label: "Material", value: st.material },
        { label: "Condition", value: st.condition ?? null },
      ]
    : [{ label: "Stock", value: null }];
  if (!st) {
    unknowns.push("Stock is not defined. Every coordinate in this program is measured from the stock, so nothing below can be set up without it.");
  } else if (!st.condition) {
    unknowns.push("Stock condition is not recorded. Confirm the temper against the certificate before cutting — the speeds and feeds were derived from the material record, not from this bar.");
  }

  /* ---------------- Where zero is, for THIS setup ---------------- */

  /*
   * The sheet used to print one system-wide sentence for every setup, because
   * there was one convention. A setup that is turned over is a different frame
   * under a different work offset, and the sheet is the document that stands
   * between a machinist and picking up the wrong edge.
   */
  const frame = pkg.framesBySetup[setup.id] ?? null;
  const frameError = pkg.frameErrorsBySetup[setup.id] ?? null;
  const originText = frame
    ? frameSentence(frame, st)
    : { xy: PROGRAM_ORIGIN.xy, z: PROGRAM_ORIGIN.z, sentence: PROGRAM_ORIGIN.sentence, prose: PROGRAM_ORIGIN.prose };
  if (frameError) {
    unknowns.push(`Where zero is cannot be stated for this setup. ${frameError.reason}`);
  }

  /* ---------------- Workholding ---------------- */

  const wh = setup.workholding;
  const assessment = pkg.workholdingBySetup[setup.id] ?? null;

  const workholding: SheetField[] = [
    { label: "Device", value: wh ? `${wh.manufacturer} ${wh.model}` : null },
    { label: "Jaw type", value: setup.jawSurface ? words(setup.jawSurface) : null },
    { label: "Jaws close on", value: setup.jawAxis ? `${setup.jawAxis} axis` : null },
    { label: "Grip depth", value: dim(setup.gripDepth) },
    { label: "Grip length", value: dim(setup.gripLength) },
    { label: "Parallel height", value: dim(setup.parallelHeight) },
    { label: "Stock projection", value: dim(setup.stockProjection) },
    { label: "Positive stop", value: setup.hasPositiveStop ? "yes" : "no" },
  ];

  /*
   * HOW MUCH AIR THE PART NEEDS UNDER IT.
   *
   * A through hole is drilled past the material by the drill's own point plus
   * a break allowance, so the tip finishes below the bottom of the stock. On
   * the sheet that reads as a Z deeper than the part is thick, and a machinist
   * who cannot see why will shorten it at the control — or set the part flat on
   * the parallels and drill them.
   *
   * The number is the deepest any operation in this setup goes past the bottom
   * of the stock, which is exactly the gap the part has to stand off whatever
   * is under it.
   */
  const below = st
    ? Math.max(0, ...setup.operations.map((o) => -o.finalZ - st.z))
    : 0;
  if (below > 1e-6) {
    workholding.push({
      label: "Clearance under part",
      value: `${below.toFixed(3)}″ — the deepest cut finishes below the bottom of the stock. Set the part off the parallels by at least that, or run it on a sacrificial plate.`,
    });
  }

  if (!wh) unknowns.push("No workholding device is recorded for this setup. Nothing below has been checked against a fixture.");
  note(setup.jawAxis, "Which axis the jaws close on is not recorded, so the fixture is not modelled and the clearance checks that need it did not run.");
  note(setup.gripDepth == null ? null : "x", "Grip depth is not recorded. Set it at the vise and record what you set — the holding margin cannot be computed without it.");
  note(setup.parallelHeight == null ? null : "x", "Parallel height is not recorded. The Z the program works from assumes the stock top; check it against the parallels you use.");
  note(setup.geometrySource, "Nobody has recorded whether the grip numbers above are planned or measured.");

  if (setup.geometrySource === "PLANNED") {
    unknowns.push("The grip numbers above are the plan's intent, not a measurement. The holding margin describes a setup nobody has built yet — measure what you actually set and record it.");
  }

  /* ---------------- Tools ---------------- */

  const opsForTool = new Map<string, string[]>();
  for (const op of setup.operations) {
    if (!op.toolId) continue;
    const list = opsForTool.get(op.toolId) ?? [];
    list.push(op.label);
    opsForTool.set(op.toolId, list);
  }

  const tools: SheetTool[] = [];
  for (const op of setup.operations) {
    const row = op.tool;
    if (!row || tools.some((x) => x.toolNumber === row.toolNumber)) continue;
    // The domain tool carries the holder description and the measured
    // stickout; the row carries the pocket it physically sits in. Both are
    // needed and neither has the other.
    const t = pkg.assignedTools.find((x) => x.id === row.id) ?? null;
    tools.push({
      toolNumber: row.toolNumber,
      description: row.description,
      diameter: row.diameter,
      // Stickout as actually set wins over the catalogue figure: that is the
      // number that decides reach and the number that goes on the presetter.
      stickout: t?.actualStickout ?? row.stickout,
      holder: t?.holder ?? "not recorded",
      lengthOffset: row.toolNumber,
      pocket: row.pocket ?? null,
      operationLabels: opsForTool.get(row.id) ?? [],
    });
  }
  tools.sort((a, b) => a.toolNumber - b.toolNumber);

  const unpocketed = tools.filter((t) => t.pocket == null);
  if (unpocketed.length > 0) {
    unknowns.push(
      `${unpocketed.map((t) => `T${t.toolNumber}`).join(", ")} ${unpocketed.length === 1 ? "is" : "are"} not assigned to a pocket in this machine's changer. Load ${unpocketed.length === 1 ? "it" : "them"} and set the length offsets before running.`,
    );
  }
  if (tools.length > 0) {
    unknowns.push(
      "Tool length offsets are set at the machine, not by CANVAS. H equals the tool number in this post; confirm every one on the offset page before the first cut.",
    );
    unknowns.push(
      "Set the D register for each cutter to its radius. Contours are cut with the control compensating, so D is what holds the size — and D is where you take a thou off a wall without re-posting.",
    );
  }

  /* ---------------- Operations ---------------- */

  const byOp = new Map(pkg.toolpaths.map((tp) => [tp.operationId, tp]));
  const operations: SheetOperation[] = setup.operations.map((op) => {
    const tp = byOp.get(op.id);
    return {
      sequence: op.sequence,
      label: op.label,
      type: words(op.type),
      pass: op.pass === "FINISH" ? "FINISH" : "ROUGH",
      toolNumber: op.tool?.toolNumber ?? null,
      featureLabel: op.feature?.label ?? null,
      topZ: op.topZ,
      finalZ: op.finalZ,
      rpm: tp?.parameters.rpm ?? null,
      feed: tp?.parameters.feed ?? null,
      cycleMinutes: tp?.cycleTimeMinutes ?? null,
      // An operation with no toolpath is written into the program as a comment
      // and skipped. On a sheet that has to be stated, not omitted.
      noMotion: !tp || tp.isPlaceholder,
    };
  });

  const skipped = operations.filter((o) => o.noMotion);
  if (skipped.length > 0) {
    unknowns.push(
      `${skipped.length} operation${skipped.length === 1 ? "" : "s"} produced no toolpath and ${skipped.length === 1 ? "is" : "are"} written into the program as a skipped comment: ${skipped.map((o) => o.label).join(", ")}. The program runs to completion without cutting ${skipped.length === 1 ? "it" : "them"}.`,
    );
  }

  const cycle = operations.reduce<number | null>(
    (sum, o) => (sum === null || o.cycleMinutes === null ? null : sum + o.cycleMinutes),
    0,
  );

  /* ---------------- What has to be inspected ---------------- */

  const characteristics: SheetCharacteristic[] = pkg.revision.features
    .filter((f) => f.critical || f.tolerance)
    .map((f) => {
      const governing = GOVERNING_DIMENSION[f.kind as FeatureKind];
      const raw = governing ? (f as unknown as Record<string, number | undefined>)[governing] : undefined;
      return {
        label: f.label,
        // A feature with several dimensions any of which the tolerance could be
        // about gets no nominal rather than a confident wrong one. Same rule
        // the inspection plan derives under.
        nominal: governing && typeof raw === "number" ? `${raw.toFixed(4)}″ ${governing}` : null,
        tolerance: f.tolerance
          ? f.tolerance.plus === f.tolerance.minus
            ? `±${f.tolerance.plus.toFixed(4)}`
            : `+${f.tolerance.plus.toFixed(4)} / −${f.tolerance.minus.toFixed(4)}`
          : null,
        method: f.inspectionMethod ?? null,
      };
    });

  const unmethodded = characteristics.filter((c) => !c.method);
  if (unmethodded.length > 0) {
    unknowns.push(
      `${unmethodded.length} toleranced feature${unmethodded.length === 1 ? "" : "s"} ${unmethodded.length === 1 ? "has" : "have"} no inspection method assigned: ${unmethodded.map((c) => c.label).join(", ")}.`,
    );
  }

  /* ---------------- Not made by this program ---------------- */

  const coverage = assessCoverage(
    pkg.revision.features,
    pkg.setups.flatMap((s) => s.operations.map((o) => ({ id: o.id, label: o.label, featureId: o.featureId }))),
  );
  const rows = new Map(pkg.revision.features.map((f) => [f.id, f]));
  const notMadeHere = coverage.accountedFor.map((e) => ({
    label: e.label,
    reason: e.reason ?? "",
    by: (rows.get(e.featureId) as { notMachinedBy?: string } | undefined)?.notMachinedBy ?? null,
  }));

  if (coverage.uncut.length > 0) {
    unknowns.push(
      `${coverage.uncut.length} feature${coverage.uncut.length === 1 ? "" : "s"} on this part ${coverage.uncut.length === 1 ? "is" : "are"} cut by no operation anywhere in the plan: ${coverage.uncut.map((e) => e.label).join(", ")}.`,
    );
  }

  /* ---------------- Gate state, printed rather than implied ---------------- */

  const blocking = pkg.readiness.gates
    .filter((g) => g.blocking && g.status !== "PASS")
    .map((g) => ({ label: g.label, detail: g.detail }));

  return {
    part: {
      name: pkg.revision.partName,
      number: pkg.revision.partNumber ?? null,
      revision: pkg.revision.revision,
      material: pkg.revision.intent.material.value ?? null,
      condition: pkg.revision.intent.materialCondition.value ?? null,
    },
    setup: {
      sequence: setup.sequence,
      name: setup.name,
      orientation: words(setup.orientation),
      workOffset: setup.workOffset,
      machine: setup.machine ? `${setup.machine.manufacturer} ${setup.machine.model}` : null,
    },
    origin: {
      xy: originText.xy,
      z: originText.z,
      turned:
        frame && frame.flipAxis
          ? `About ${frame.flipAxis} — every ${frame.flipAxis === "Y" ? "X" : "Y"} on the model is mirrored${
              frame.quarterTurns ? `, then indexed ${frame.quarterTurns * 90}° CCW` : ""
            }`
          : frame && frame.quarterTurns
            ? `Indexed ${frame.quarterTurns * 90}° CCW from the model`
            : null,
      prose: originText.prose,
      datumNote: setup.datumNote ?? null,
    },
    stock,
    workholding,
    geometrySource: setup.geometrySource ?? null,
    holding: assessment
      ? {
          level: assessment.level,
          margin: assessment.holdingMargin?.margin != null ? `${assessment.holdingMargin.margin.toFixed(2)}×` : null,
        }
      : null,
    tools,
    operations,
    cycleMinutes: cycle,
    characteristics,
    notMadeHere,
    unknowns,
    gateState: { overall: pkg.readiness.overall, blocking },
    developmentNotice:
      "The program this sheet accompanies comes from a DEVELOPMENT post that has not been validated on this machine. Verify every line, dry run above the part, and keep a hand on the feed hold.",
  };
}

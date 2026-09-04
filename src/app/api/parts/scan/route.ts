import { NextResponse } from "next/server";
import { requireWriteApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { parseStl } from "@/lib/scan/mesh";
import { inspectMesh, type MeshUnits } from "@/lib/scan/inspect";
import { sliceMesh } from "@/lib/scan/slice";
import { fitChain } from "@/lib/geometry/fit";
import { assembleLoops, splitProfile } from "@/lib/geometry/loop";
import { recognizeGeometry } from "@/lib/geometry/recognize";
import { isScanningInstrument } from "@/lib/domain/shop";
import { emptyPartIntent, type PartIntent } from "@/lib/domain/part-intent";
import { measured, unknown as unknownField, value } from "@/lib/provenance";

/**
 * SCAN IMPORT — a scanner is an instrument, and this treats it as one.
 *
 * The difference between this and the STEP import is the difference between
 * a drawing and a part. A STEP file is the design authority; a scan is one
 * worn example measured by one instrument. So:
 *
 *   - The scan is attributed to a METROLOGY DEVICE the shop actually owns,
 *     and the envelope carries that device's recorded uncertainty. No
 *     scanner on file, no import — the same refusal the CAM engine makes
 *     for a material with no surface-speed window.
 *   - UNITS ARE DECLARED, never sniffed. An STL file contains no units at
 *     all, and the difference between the two readings is a factor of 25.4.
 *   - It lands in the reverse-engineering flow as a measurement session with
 *     PENDING readings, not as a finished model. A human rules on them,
 *     exactly as they would on a reading taken at the bench.
 *
 * There is no model call in this pipeline. Reading triangles is arithmetic.
 */

const MAX_BYTES = 100 * 1024 * 1024;

export async function POST(request: Request) {
  const gate = await requireWriteApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;

  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  const declaredUnits = String(form?.get("units") ?? "");
  const deviceId = String(form?.get("deviceId") ?? "");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Attach an .stl scan file." }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json({ error: "File exceeds the 100 MB import limit." }, { status: 400 });
  }

  /*
   * Units first, because every number downstream is wrong by 25.4x if this
   * is wrong, and the file cannot settle it.
   */
  if (declaredUnits !== "IN" && declaredUnits !== "MM") {
    return NextResponse.json(
      {
        error:
          "Declare the units the scan was exported in. An STL file records none, and the same file is a 1\" part in millimetres or a 25.4\" part in inches — CANVAS will not pick for you.",
      },
      { status: 400 },
    );
  }
  const units = declaredUnits as MeshUnits;

  /*
   * The instrument. A scan's accuracy is the scanner's accuracy; without a
   * record of which scanner, there is no uncertainty to attach to any
   * number this produces, and an unqualified dimension off a mesh is
   * exactly the thing reverse engineering exists to avoid.
   */
  if (!deviceId) {
    return NextResponse.json(
      { error: "Name the scanner this came off. The uncertainty on every dimension is the instrument's, and CANVAS does not assume one." },
      { status: 400 },
    );
  }
  const device = await db.metrologyDevice.findFirst({
    where: { id: deviceId, organizationId: user.organizationId },
  });
  if (!device) {
    return NextResponse.json({ error: "That scanner is not in this shop's metrology library." }, { status: 404 });
  }
  if (!isScanningInstrument(device.deviceType)) {
    return NextResponse.json(
      { error: `${device.description} is not a scanning instrument. A scan is attributed to the device that produced it.` },
      { status: 400 },
    );
  }

  const parsed = parseStl(new Uint8Array(await file.arrayBuffer()));
  if (!parsed.ok) {
    return NextResponse.json({ error: parsed.error.reason, recommendations: parsed.error.recommendations }, { status: 422 });
  }
  const inspection = inspectMesh(parsed.mesh, units);

  const name = parsed.mesh.name?.trim() || file.name.replace(/\.stl$/i, "");
  const intent: PartIntent = emptyPartIntent(name);
  intent.description = value(
    `Imported from 3D scan ${file.name}, measured on ${device.description}`,
    "MEASURED",
    "HIGH",
    { note: `±${device.uncertainty.toFixed(4)}" instrument uncertainty`, confirmedByUser: false },
  );
  intent.units = measured("IN", `Scan declared in ${units === "MM" ? "millimetres" : "inches"} at import; stored in inches`);
  /*
   * The envelope is MEASURED — by a named instrument, to a stated
   * uncertainty — and it is still not the finished size. A scan measures a
   * worn example, and if the mesh is open it may not even bound the part.
   */
  intent.finishedEnvelope = inspection.integrity.watertight
    ? value({ x: inspection.envelope.x, y: inspection.envelope.y, z: inspection.envelope.z }, "MEASURED", "MEDIUM", {
        note: `Scanned envelope on ${device.description}, ±${device.uncertainty.toFixed(4)}". This is one worn example, not the drawing.`,
      })
    : unknownField(
        `The scan is not a closed surface — ${inspection.integrity.openEdges.toLocaleString()} open edges. The envelope bounds what the scanner SAW, which is smaller than the part.`,
      );
  intent.stock = unknownField("Size stock from the finished envelope — the import adds no allowance");
  intent.loadBearing = unknownField("Requires the Part Responsibility interview");
  intent.safetyCritical = unknownField("Requires the Part Responsibility interview");
  intent.failureConsequence = unknownField("Requires the Part Responsibility interview");
  intent.notes = value(
    [
      `Scan import: ${inspection.triangles.toLocaleString()} triangles, ${parsed.mesh.format} STL.`,
      `${inspection.planarFaces.length} planar regions found — candidate faces, not datums.`,
      ...inspection.missingInputs,
      `Not established by this scan: ${inspection.notAttempted.join(" ")}`,
    ].join(" "),
    "MEASURED",
    "MEDIUM",
    { note: "Scan inspection report" },
  );

  const part = await db.part.create({
    data: {
      organizationId: user.organizationId,
      name,
      description: `Imported from 3D scan ${file.name}`,
      sharing: "PRIVATE",
      revisions: {
        create: {
          revision: "A",
          status: "DRAFT",
          units: "IN",
          intentJson: JSON.stringify(intent),
          stockJson: null,
          responsibility: { create: {} },
        },
      },
    },
    include: { revisions: true },
  });
  const revision = part.revisions[0];

  /*
   * The readings land in a measurement session, PENDING, attributed to the
   * scanner — the same shape as a reading taken at the bench, because that
   * is what they are. The reverse-engineering flow rules on them.
   */
  const session = await db.measurementSession.create({
    data: {
      partRevisionId: revision.id,
      name: `3D scan — ${device.description}`,
      mode: "REVERSE_ENGINEER",
      status: "IN_PROGRESS",
      notes: `${parsed.mesh.format} STL, ${inspection.triangles.toLocaleString()} triangles, declared in ${units}.`,
    },
  });
  const axes: [string, number][] = [
    ["Scanned overall X", inspection.envelope.x],
    ["Scanned overall Y", inspection.envelope.y],
    ["Scanned overall Z", inspection.envelope.z],
  ];
  await db.measurement.createMany({
    data: axes.map(([label, measuredValue]) => ({
      sessionId: session.id,
      deviceId: device.id,
      label,
      measuredValue,
      units: "IN",
      uncertainty: device.uncertainty,
      context: "GENERAL",
      resolution: "PENDING",
    })),
  });

  /*
   * THE OUTSIDE PROFILE, FROM THE SCAN.
   *
   * A part a 3-axis mill makes is 2.5D, so its outline IS the cross-section of
   * the mesh — and slicing one is exact arithmetic, not inference. This is the
   * piece that was missing: reverse engineering produced an envelope and a list
   * of things to go and measure, and the shape of the part came from nowhere.
   *
   * THE FIT TOLERANCE IS THE SCANNER'S OWN UNCERTAINTY.
   *
   * Fitting is deciding that points which are not on a line are close enough to
   * be treated as though they were, and a fit TIGHTER than the measurement is a
   * claim about the part the measurement cannot support — it would turn this
   * instrument's noise into geometry. So the tolerance comes from the
   * metrology record, and the proposal says which instrument set it.
   *
   * It is a proposal. A scan is one worn example measured on one day, and what
   * the part is SUPPOSED to be is a human's call against the print.
   */
  const slice = sliceMesh(parsed.mesh, units);
  const outer = splitProfile(assembleLoops(slice.segments).loops).profile;
  if (outer) {
    const fit = fitChain(outer.chain, { tolerance: Math.max(device.uncertainty, 1e-4) });
    const rec = recognizeGeometry(
      fit.chain.segments.map((seg, i) => {
        const from = i === 0 ? fit.chain.start : fit.chain.segments[i - 1].to;
        return seg.kind === "ARC"
          ? { kind: "ARC" as const, a: from, b: seg.to, center: seg.center, cw: seg.cw }
          : { kind: "LINE" as const, a: from, b: seg.to };
      }),
      { label: "Outside profile (scanned)" },
    );
    if (rec.profile) {
      await db.aIRecommendation.create({
        data: {
          partRevisionId: revision.id,
          kind: "FEATURE",
          summary:
            `Outside profile sliced from the scan at Z ${slice.z.toFixed(4)}": ` +
            `${fit.from} chords fitted to ${fit.to} segments (${fit.lines} lines, ${fit.arcs} arcs) ` +
            `within ${Math.max(device.uncertainty, 1e-4).toFixed(4)}" — the uncertainty of ${device.description}, ` +
            `because a fit tighter than the measurement is a claim the measurement cannot support. ` +
            `Worst deviation ${fit.maxDeviation.toFixed(5)}". ` +
            `${slice.assumptions.join(" ")} ` +
            `This is one worn example measured on one day: check every dimension against the print before accepting.`,
          payloadJson: JSON.stringify([rec.profile]),
          providerId: "scan-slice",
          confidence: 1,
          status: "PROPOSED",
        },
      });
    }
  }

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Part",
    entityId: part.id,
    action: "CREATE",
    actorType: "HUMAN",
    reason: `Scan import: ${file.name}`,
    newValue: name,
  });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "PartRevision",
    entityId: revision.id,
    action: "GENERATE",
    // Reading triangles is arithmetic. No model was involved.
    actorType: "SYSTEM",
    reason: `Scan inspection on ${device.description} (±${device.uncertainty.toFixed(4)}"), units declared ${units}`,
    newValue: JSON.stringify({
      triangles: inspection.triangles,
      format: parsed.mesh.format,
      watertight: inspection.integrity.watertight,
      openEdges: inspection.integrity.openEdges,
      planarFaces: inspection.planarFaces.length,
      envelope: inspection.envelope,
    }),
  });

  return NextResponse.json({
    partId: part.id,
    sessionId: session.id,
    inspection,
    instrument: { description: device.description, uncertainty: device.uncertainty, calibrated: device.calibrated },
  });
}

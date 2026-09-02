import { NextResponse } from "next/server";
import { requireWriteApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { recognizeStep } from "@/lib/step/recognize";
import { emptyPartIntent, type PartIntent } from "@/lib/domain/part-intent";
import { calculated, unknown as unknownField } from "@/lib/provenance";

/**
 * STEP IMPORT — deterministic intake
 *
 * A STEP file is the design authority, and reading it is arithmetic: the
 * recognizer is a parser plus geometry, with no model call anywhere in the
 * pipeline. Extracted values therefore carry CALCULATED provenance — not
 * AI_INFERENCE — but they are still proposals: features go through the same
 * acceptance flow as every other suggestion, because the recognizer's
 * hole-vs-bore classification is a heuristic even when its coordinates are
 * exact. Zero-click ingest, never zero-click geometry.
 */

const MAX_BYTES = 25 * 1024 * 1024;

export async function POST(request: Request) {
  const gate = await requireWriteApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;

  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Attach a .step / .stp file." }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json({ error: "File exceeds the 25 MB import limit." }, { status: 400 });
  }
  const text = await file.text();

  const recognition = recognizeStep(text);
  if (recognition.envelope.x === 0 && recognition.envelope.y === 0) {
    return NextResponse.json(
      { error: recognition.warnings.join(" ") || "No recognizable geometry in the file." },
      { status: 422 },
    );
  }

  const name = recognition.partName ?? file.name.replace(/\.(stp|step)$/i, "");
  const intent: PartIntent = emptyPartIntent(name);
  intent.description = calculated(`Imported from STEP file ${file.name}`, "Deterministic geometry import");
  intent.units = calculated("IN", `Drawing units ${recognition.units}; converted to inches`);
  intent.finishedEnvelope = calculated(recognition.envelope, "Bounding envelope of the STEP geometry");
  // The envelope is the finished size. Stock needs an allowance, and choosing
  // one is a machining decision, not a parsing result.
  intent.stock = unknownField("Size stock from the finished envelope — the import adds no allowance");
  intent.loadBearing = unknownField("Requires the Part Responsibility interview");
  intent.safetyCritical = unknownField("Requires the Part Responsibility interview");
  intent.failureConsequence = unknownField("Requires the Part Responsibility interview");
  intent.notes = calculated(
    [
      `STEP import: ${recognition.surfaces.recognized} of ${recognition.surfaces.total} surfaces recognized.`,
      ...recognition.unrecognized.map((u) => `${u.count} × ${u.type} not recognized — model these features by hand.`),
      ...recognition.warnings,
    ].join(" "),
    "Recognition report",
  );

  const part = await db.part.create({
    data: {
      organizationId: user.organizationId,
      name,
      description: `Imported from ${file.name}`,
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

  if (recognition.suggestions.length > 0) {
    await db.aIRecommendation.create({
      data: {
        partRevisionId: revision.id,
        kind: "FEATURE",
        summary:
          `${recognition.suggestions.length} features recognized from STEP geometry ` +
          `(${recognition.surfaces.recognized}/${recognition.surfaces.total} surfaces). ` +
          `Deterministic recognizer — coordinates are exact, classifications are heuristic.`,
        payloadJson: JSON.stringify(recognition.suggestions),
        providerId: "step-recognizer",
        confidence: 0.9,
        status: "PROPOSED",
      },
    });
  }

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Part",
    entityId: part.id,
    action: "CREATE",
    actorType: "HUMAN",
    reason: `STEP import: ${file.name}`,
    newValue: name,
  });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "PartRevision",
    entityId: revision.id,
    action: "GENERATE",
    // The recognizer is deterministic arithmetic, not a model.
    actorType: "SYSTEM",
    reason: "STEP geometry recognition",
    newValue: JSON.stringify({
      surfaces: recognition.surfaces,
      suggestions: recognition.suggestions.length,
      unrecognized: recognition.unrecognized,
      warnings: recognition.warnings.length,
    }),
  });

  return NextResponse.json({
    partId: part.id,
    suggestions: recognition.suggestions.length,
    surfaces: recognition.surfaces,
    unrecognized: recognition.unrecognized,
    warnings: recognition.warnings,
  });
}

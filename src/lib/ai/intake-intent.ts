import { emptyPartIntent, type PartIntent, type PartIntentExtraction } from "@/lib/domain/part-intent";
import type { Stock } from "@/lib/domain/features";
import { inferred, userValue, unknown as unknownField } from "@/lib/provenance";

/**
 * INTAKE → PART INTENT
 *
 * Turns whatever the model extracted from a description into a Part Intent
 * Model. Extracted separately from the route so it can be tested: the route
 * around it is a database write and an audit entry, and this is where the
 * provenance rules actually live.
 *
 * The rule is locked principle 3 — an AI inference stays inferred until a
 * human confirms it. Every field the model produced is tagged AI_INFERENCE
 * and unconfirmed, and nothing here is engineering-grade on arrival.
 */

export interface IntakeResult {
  intent: PartIntent;
  /**
   * Stock, only when the extraction actually carried dimensions. Null rather
   * than a zero-filled record — see below.
   */
  stock: Stock | null;
}

/**
 * Builds a stock record from an extraction, or returns null.
 *
 * The route used to write `x: extraction.stock.x ?? 0` for every axis. Two
 * things went wrong with that. A model that named a form and no dimensions
 * produced a 0 x 0 x 0 block, and a zero-sized stock is not a missing stock
 * downstream — it is a stock that satisfies "thin" in the flatness test, sits
 * inside every machine envelope, and weighs nothing in the cost model. And a
 * ROUND bar carries diameter and length rather than x/y/z, so a round
 * extraction was written as a rectangular record of zeros with the diameter
 * discarded entirely.
 */
export function stockFromExtraction(extraction: PartIntentExtraction): Stock | null {
  const s = extraction.stock;
  if (!s) return null;

  const material = extraction.material ?? "Unspecified";
  const common = { form: s.form, material, condition: extraction.materialCondition } as const;

  if (s.form === "ROUND" || s.form === "TUBE") {
    if (s.diameter == null || s.length == null) return null;
    return {
      ...common,
      diameter: s.diameter,
      // A round bar's bounding box is the diameter across and the length along.
      x: s.diameter,
      y: s.diameter,
      z: s.length,
    } as Stock;
  }

  if (s.x == null || s.y == null || s.z == null) return null;
  return { ...common, x: s.x, y: s.y, z: s.z } as Stock;
}

export function buildIntakeIntent(prompt: string, extraction: PartIntentExtraction): IntakeResult {
  const intent: PartIntent = emptyPartIntent(extraction.partName ?? "New Part");
  const score = extraction.confidence;

  // The description is the operator's own sentence, so it is a USER value.
  // It was tagged AI_INFERENCE with a confidence of 1, which asked someone to
  // confirm the words they had just typed. Over-marking is the safe direction
  // to be wrong in, but provenance is first-class data and a wrong source is
  // a wrong answer whichever way it leans.
  intent.description = userValue(prompt);

  // Units were tagged userValue — source USER, confidence VERIFIED,
  // confirmedByUser true — so isEngineeringGrade() passed on them the instant
  // the model returned. Every other extracted field was correctly marked
  // AI_INFERENCE. Units decide whether every dimension on the part is inches
  // or millimetres, which makes it the worst single field to have been the
  // exception.
  if (extraction.units) intent.units = inferred(extraction.units, score, "Read from the intake description");

  if (extraction.material) intent.material = inferred(extraction.material, score, "Recognised from the description");
  if (extraction.materialCondition) intent.materialCondition = inferred(extraction.materialCondition, score);
  if (extraction.stock) {
    intent.stock = inferred(extraction.stock, score, "Stock sized from the finished envelope with a facing allowance");
  }
  if (extraction.finishedEnvelope) intent.finishedEnvelope = inferred(extraction.finishedEnvelope, score);
  if (extraction.quantity) intent.quantity = inferred(extraction.quantity, score);
  if (extraction.generalTolerance) intent.generalTolerance = inferred(extraction.generalTolerance, score);
  if (extraction.surfaceFinish) intent.surfaceFinish = inferred(extraction.surfaceFinish, score);
  if (extraction.features?.length) intent.features = inferred(extraction.features, score);
  if (extraction.notes) intent.notes = inferred(extraction.notes, score);

  // Responsibility is never inferred. It is asked.
  intent.loadBearing = unknownField("Requires the Part Responsibility interview");
  intent.safetyCritical = unknownField("Requires the Part Responsibility interview");
  intent.failureConsequence = unknownField("Requires the Part Responsibility interview");

  intent.unknowns = extraction.unknowns;
  intent.confidence = extraction.confidence;

  return { intent, stock: stockFromExtraction(extraction) };
}

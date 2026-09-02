import { NextResponse } from "next/server";
import { z } from "zod";
import { requireWriteApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { DEVICE_UNCERTAINTY, type MetrologyDeviceType } from "@/lib/domain/shop";
import { bestNominalSuggestion, findNominalCandidates } from "@/lib/engines/nominal";

/**
 * Records a measurement and runs nominal reasoning against it.
 *
 * The suggestion is stored alongside the measurement, never instead of it.
 * `measuredValue` is what the instrument said and never changes; `resolution`
 * records what the human decided to do about the suggestion.
 */

const createSchema = z.object({
  sessionId: z.string().min(1),
  label: z.string().min(1).max(160),
  measuredValue: z.number().finite(),
  deviceId: z.string().optional().nullable(),
  featureId: z.string().optional().nullable(),
  datumId: z.string().optional().nullable(),
  context: z.enum(["BORE", "SHAFT", "HOLE", "THREAD", "THICKNESS", "GENERAL"]).default("GENERAL"),
  repeatCount: z.number().int().min(1).max(20).default(1),
  wearExpected: z.boolean().default(false),
});

export async function POST(request: Request) {
  const gate = await requireWriteApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;
  const parsed = createSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message ?? "Invalid" }, { status: 400 });

  const input = parsed.data;

  // Session must belong to this organisation.
  const session = await db.measurementSession.findFirst({
    where: { id: input.sessionId, partRevision: { part: { organizationId: user.organizationId } } },
  });
  if (!session) return NextResponse.json({ error: "Session not found" }, { status: 404 });

  const device = input.deviceId
    ? await db.metrologyDevice.findFirst({ where: { id: input.deviceId, organizationId: user.organizationId } })
    : null;

  /**
   * What this dimension was measured FROM.
   *
   * The schema has carried this field, and the sentence explaining why it
   * matters, since it was written: a number without it is not reproducible,
   * because the next person measures from a different edge and gets a
   * different answer that is equally defensible. Nothing ever wrote it. Every
   * measurement in the system is an isolated number.
   *
   * It must be an ESTABLISHED datum on this session's own revision. Accepting
   * a datum is a human act; measuring from a proposal CANVAS has not had
   * agreed records a reference that does not exist yet. Resolved against the
   * revision rather than trusted, so a request cannot name another part's
   * datum — or another shop's.
   */
  const datum = input.datumId
    ? await db.datum.findFirst({
        where: { id: input.datumId, partRevisionId: session.partRevisionId, acceptedByUser: true },
      })
    : null;
  if (input.datumId && !datum) {
    return NextResponse.json(
      { error: "That datum is not an established datum on this revision." },
      { status: 400 },
    );
  }

  // Uncertainty comes from the instrument actually used. Repeated readings
  // reduce random error but never below the instrument's own resolution.
  const base = device?.uncertainty ?? DEVICE_UNCERTAINTY[(device?.deviceType as MetrologyDeviceType) ?? "DIGITAL_CALIPER"] ?? 0.002;
  const uncertainty = Math.max(base / Math.sqrt(input.repeatCount), device?.resolution ?? base);

  const suggestion = bestNominalSuggestion({
    measured: input.measuredValue,
    uncertainty,
    context: input.context,
    wearExpected: input.wearExpected,
  });

  const measurement = await db.measurement.create({
    data: {
      sessionId: input.sessionId,
      featureId: input.featureId ?? null,
      deviceId: device?.id ?? null,
      datumId: datum?.id ?? null,
      label: input.label,
      measuredValue: input.measuredValue,
      units: "IN",
      uncertainty,
      repeatCount: input.repeatCount,
      context: input.context,
      suggestedNominal: suggestion?.nominalInches ?? null,
      suggestedNominalLabel: suggestion?.label ?? null,
      suggestedFamily: suggestion?.family ?? null,
      suggestionConfidence: suggestion?.confidence ?? null,
      suggestionBasis: suggestion?.basis ?? null,
      resolution: "PENDING",
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Measurement",
    entityId: measurement.id,
    action: "CREATE",
    actorType: "HUMAN",
    newValue: String(input.measuredValue),
    reason: `${input.label} measured with ${device?.description ?? "unspecified instrument"}`,
  });

  const candidates = findNominalCandidates({
    measured: input.measuredValue,
    uncertainty,
    context: input.context,
    wearExpected: input.wearExpected,
  });

  return NextResponse.json({ measurement, suggestion, candidates });
}

/* ------------------------------------------------------------------ */
/* Resolution — accept the nominal, keep the measured value, or dig in */
/* ------------------------------------------------------------------ */

const resolveSchema = z.object({
  measurementId: z.string().min(1),
  resolution: z.enum(["ACCEPTED_NOMINAL", "KEPT_MEASURED", "INVESTIGATING"]),
});

export async function PATCH(request: Request) {
  const gate = await requireWriteApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;
  const parsed = resolveSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "Invalid request" }, { status: 400 });

  const { measurementId, resolution } = parsed.data;

  const measurement = await db.measurement.findFirst({
    where: { id: measurementId, session: { partRevision: { part: { organizationId: user.organizationId } } } },
  });
  if (!measurement) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const resolvedValue =
    resolution === "ACCEPTED_NOMINAL" ? measurement.suggestedNominal ?? measurement.measuredValue : measurement.measuredValue;

  const updated = await db.measurement.update({
    where: { id: measurementId },
    data: { resolution, resolvedValue, resolvedBy: user.id, resolvedAt: new Date() },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Measurement",
    entityId: measurementId,
    action: resolution === "ACCEPTED_NOMINAL" ? "ACCEPT_SUGGESTION" : "UPDATE",
    actorType: "HUMAN",
    field: "resolvedValue",
    oldValue: String(measurement.measuredValue),
    newValue: String(resolvedValue),
    reason:
      resolution === "ACCEPTED_NOMINAL"
        ? `Accepted nominal ${measurement.suggestedNominalLabel}`
        : resolution === "KEPT_MEASURED"
          ? "Kept the measured value"
          : "Marked for investigation",
  });

  // If this measurement is bound to a feature, the resolved value updates the
  // model — but only on an explicit human decision, never automatically.
  if (measurement.featureId && resolution !== "INVESTIGATING") {
    const feature = await db.feature.findUnique({ where: { id: measurement.featureId } });
    if (feature) {
      const params = JSON.parse(feature.parametersJson) as Record<string, unknown>;
      if (measurement.context === "BORE" || measurement.context === "HOLE") params.diameter = resolvedValue;
      else if (measurement.context === "THICKNESS") params.depth = resolvedValue;
      await db.feature.update({ where: { id: feature.id }, data: { parametersJson: JSON.stringify(params) } });

      await audit({
        organizationId: user.organizationId,
        userId: user.id,
        entityType: "Feature",
        entityId: feature.id,
        action: "UPDATE",
        actorType: "HUMAN",
        field: measurement.context === "THICKNESS" ? "depth" : "diameter",
        oldValue: JSON.stringify(JSON.parse(feature.parametersJson)),
        newValue: String(resolvedValue),
        reason: "Updated from a resolved measurement",
      });
    }
  }

  return NextResponse.json({ measurement: updated });
}

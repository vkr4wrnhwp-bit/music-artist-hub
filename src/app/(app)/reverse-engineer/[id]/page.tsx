import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { getMetrology } from "@/lib/data";
import { METROLOGY_LABELS } from "@/lib/domain/shop";
import { inchesToMm } from "@/lib/engines/nominal";
import { TopBar } from "@/components/nav";
import { revalidatePath } from "next/cache";
import { audit } from "@/lib/audit";
import { buildReconstructionPlan } from "@/lib/engines/reconstruction";
import { loadRevision } from "@/lib/data";
import { ReconstructionPlanPanel } from "@/components/reverse/reconstruction-plan";
import { GuidedMeasurement } from "@/components/reverse/guided-measurement";
import { PhotoSetUploader } from "@/components/reverse/photo-set";
import { LinkButton, Notice, Panel, SectionHeading, StatusChip } from "@/components/ui";
import { GuideCard } from "@/components/guide/guide-card";
import type { GuideContext } from "@/lib/guide/engine";

export default async function SessionPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();

  const session = await db.measurementSession.findFirst({
    where: { id, partRevision: { part: { organizationId: user.organizationId } } },
    include: {
      partRevision: { include: { part: true, features: { orderBy: { orderIndex: "asc" } } } },
      measurements: { orderBy: { createdAt: "asc" }, include: { device: true, feature: true } },
    },
  });
  if (!session) notFound();

  const [devices, photos, datums] = await Promise.all([
    getMetrology(user.organizationId),
    db.uploadedAsset.findMany({
      where: { organizationId: user.organizationId, partId: session.partRevision.partId, kind: "PHOTO" },
      orderBy: { createdAt: "asc" },
    }),
    db.datum.findMany({ where: { partRevisionId: session.partRevisionId }, orderBy: { letter: "asc" } }),
  ]);

  /* ---------------- Reconstruction plan ---------------- */

  // The plan reads the hydrated, validated feature models rather than the raw
  // rows, so the tasks it proposes are about geometry the rest of CANVAS also
  // agrees exists.
  const revision = await loadRevision(user.organizationId, session.partRevision.partId);

  const plan = buildReconstructionPlan({
    features: revision?.features ?? [],
    uploadedViews: photos.map((p) => p.viewLabel ?? "").filter(Boolean),
    establishedDatums: datums
      .filter((d) => d.acceptedByUser)
      .map((d) => ({ system: d.system, letter: d.letter })),
    completedLabels: session.measurements.map((m) => m.label),
    inferredAwaitingReview: session.measurements.filter(
      (m) => m.resolution === "PENDING" && m.suggestedNominal != null,
    ).length,
  });

  const establishedKeys = new Set(
    datums.filter((d) => d.acceptedByUser).map((d) => `${d.system}:${d.letter}`),
  );

  /**
   * Establishing a datum is a human act. CANVAS proposes the frame and says
   * why; it does not get to decide what the part is referenced to, because the
   * person holding the component knows which face actually seats in service
   * and the feature list does not.
   */
  async function establishDatum(formData: FormData) {
    "use server";
    const currentUser = await requireUser();
    const owned = await db.measurementSession.findFirst({
      where: { id, partRevision: { part: { organizationId: currentUser.organizationId } } },
    });
    if (!owned) notFound();

    const letter = String(formData.get("letter") ?? "").trim();
    const system = String(formData.get("system") ?? "DESIGN");
    const featureId = String(formData.get("featureId") ?? "").trim() || null;
    if (!letter) redirect(`/reverse-engineer/${id}`);

    await db.datum.upsert({
      where: { partRevisionId_system_letter: { partRevisionId: owned.partRevisionId, system, letter } },
      create: {
        partRevisionId: owned.partRevisionId,
        letter,
        system,
        featureId,
        description: String(formData.get("description") ?? ""),
        geometryType: String(formData.get("geometryType") ?? "PLANE"),
        proposedReason: String(formData.get("reason") ?? ""),
        acceptedByUser: true,
        acceptedAt: new Date(),
        source: "USER",
      },
      update: { acceptedByUser: true, acceptedAt: new Date(), source: "USER", featureId },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "Datum",
      entityId: `${owned.partRevisionId}:${system}:${letter}`,
      action: "CREATE",
      actorType: "HUMAN",
      field: `${system} datum ${letter}`,
      newValue: String(formData.get("description") ?? ""),
      reason: "Datum accepted by operator",
    });

    revalidatePath(`/reverse-engineer/${id}`);
    redirect(`/reverse-engineer/${id}`);
  }

  const pending = session.measurements.filter((m) => m.resolution === "PENDING" && m.suggestedNominal);

  // Guide snapshot — the same reconstruction plan the page renders, so the
  // REVERSE_A_PART steps complete from the truth, never a checklist copy.
  const guideCtx: GuideContext = {
    partId: session.partRevision.partId,
    hasStock: false,
    hasMachine: true,
    hasMaterial: true,
    featureCount: revision?.features.length ?? 0,
    pendingProposals: 0,
    setupCount: 0,
    workholdingAssessed: false,
    toolpathCount: 0,
    simulationRecorded: false,
    approvalExists: false,
    ncProgramExists: false,
    blockingGates: [],
    nextAction: null,
    training: false,
    re: {
      sessionId: session.id,
      photosOnFile: plan.photosOnFile,
      missingViews: plan.missingViews.length,
      datumsEstablished: plan.datumsEstablished,
      datumsRequired: plan.datumsRequired,
      measurementsComplete: plan.measurementsComplete,
      measurementsRequired: plan.measurementsRequired,
      inferredAwaitingReview: plan.inferredAwaitingReview,
    },
  };

  return (
    <>
      <TopBar>
        <Link href="/reverse-engineer" className="tech-label hover:text-platinum">
          Reverse engineer
        </Link>
        <span className="text-muted">/</span>
        <span className="text-[13px] text-white">{session.partRevision.part.name}</span>
        <StatusChip tone={session.status === "COMPLETE" ? "pass" : "precision"}>{session.status}</StatusChip>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          <div className="flex items-start justify-between gap-6">
            <SectionHeading sub="CANVAS asks for measurements in the order that constrains the model fastest: datums first, then everything referenced to them. Each request names the instrument to use and what the result is worth.">
              Guided measurement
            </SectionHeading>
            <LinkButton href={`/parts/${session.partRevision.partId}`} size="sm">
              Open part workspace
            </LinkButton>
          </div>

          {pending.length > 0 && (
            <Notice tone="precision" title={`${pending.length} measurement${pending.length === 1 ? "" : "s"} awaiting your decision`}>
              CANVAS has matched these readings against published standards. It will not change a dimension for you.
            </Notice>
          )}

          <ReconstructionPlanPanel
            plan={plan}
            establishDatum={establishDatum}
            establishedKeys={establishedKeys}
          />

          <GuidedMeasurement
            sessionId={session.id}
            devices={devices.map((d) => ({
              id: d.id,
              label: `${METROLOGY_LABELS[d.deviceType]} — ${d.description}`,
              uncertainty: d.uncertainty,
              deviceType: d.deviceType,
            }))}
            features={session.partRevision.features.map((f) => ({ id: f.id, label: f.label, kind: f.kind }))}
            photos={photos.map((p) => ({ id: p.id, url: `/api/assets/${encodeURIComponent(p.storageKey)}`, view: p.viewLabel ?? "—", filename: p.filename }))}
            measurements={session.measurements.map((m) => ({
              id: m.id,
              label: m.label,
              measuredValue: m.measuredValue,
              measuredMm: Number(inchesToMm(m.measuredValue).toFixed(4)),
              uncertainty: m.uncertainty,
              device: m.device?.description ?? null,
              context: m.context,
              suggestedNominal: m.suggestedNominal,
              suggestedNominalLabel: m.suggestedNominalLabel,
              suggestedFamily: m.suggestedFamily,
              suggestionConfidence: m.suggestionConfidence,
              suggestionBasis: m.suggestionBasis,
              resolution: m.resolution,
              resolvedValue: m.resolvedValue,
              feature: m.feature?.label ?? null,
            }))}
          />

          <Panel title="Photo set">
            <PhotoSetUploader partId={session.partRevision.partId} />
            {photos.length > 0 && (
              <div className="mt-4 grid grid-cols-2 gap-px bg-line sm:grid-cols-4">
                {photos.map((p) => (
                  // eslint-disable-next-line @next/next/no-img-element
                  <figure key={p.id} className="bg-surface p-2">
                    <img
                      src={`/api/assets/${encodeURIComponent(p.storageKey)}`}
                      alt={p.viewLabel ?? p.filename}
                      className="aspect-square w-full object-cover"
                    />
                    <figcaption className="tech-label mt-1.5 truncate">{p.viewLabel ?? p.filename}</figcaption>
                  </figure>
                ))}
              </div>
            )}
          </Panel>

          <Notice tone="review" title="Measurement dependency">
            Measurements after the first are referenced to the datum established by the first. If you re-measure a
            datum, everything downstream of it needs re-checking — CANVAS records the dependency but does not
            invalidate readings for you.
          </Notice>
        </div>
      </main>
      <GuideCard ctx={guideCtx} flowId="REVERSE_A_PART" />
    </>
  );
}

export const dynamic = "force-dynamic";

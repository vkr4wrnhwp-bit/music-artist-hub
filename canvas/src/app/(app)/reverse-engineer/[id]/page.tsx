import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { getMetrology } from "@/lib/data";
import { METROLOGY_LABELS } from "@/lib/domain/shop";
import { inchesToMm } from "@/lib/engines/nominal";
import { TopBar } from "@/components/nav";
import { GuidedMeasurement } from "@/components/reverse/guided-measurement";
import { PhotoSetUploader } from "@/components/reverse/photo-set";
import { LinkButton, Notice, Panel, SectionHeading, StatusChip } from "@/components/ui";

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

  const [devices, photos] = await Promise.all([
    getMetrology(user.organizationId),
    db.uploadedAsset.findMany({
      where: { organizationId: user.organizationId, partId: session.partRevision.partId, kind: "PHOTO" },
      orderBy: { createdAt: "asc" },
    }),
  ]);

  const pending = session.measurements.filter((m) => m.resolution === "PENDING" && m.suggestedNominal);

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

      <main className="flex-1 overflow-y-auto p-6">
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
    </>
  );
}

export const dynamic = "force-dynamic";

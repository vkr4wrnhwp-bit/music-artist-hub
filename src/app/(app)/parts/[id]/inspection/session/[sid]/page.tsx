import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { loadRevision } from "@/lib/data";
import { assessConformance } from "@/lib/engines/fair";
import { featureSummary, fmtTol, type Feature } from "@/lib/domain/features";
import { TopBar } from "@/components/nav";
import { Button, Field, Notice, Panel, SectionHeading, StatusChip, inputClass } from "@/components/ui";

/**
 * FIRST-ARTICLE MEASUREMENT SESSION
 *
 * Records inspection measurements against the finished article. Every reading
 * requires an instrument from the shop's metrology inventory — a number
 * without an instrument has no uncertainty, and a number without an
 * uncertainty cannot carry a conformance decision. The uncertainty is copied
 * from the instrument record, never typed in.
 *
 * The verdict shown next to each reading is `assessConformance` — the same
 * function the FAIR report runs. This screen cannot say CONFORMS where the
 * report would say UNDETERMINED.
 */

export default async function InspectionSessionPage(props: {
  params: Promise<{ id: string; sid: string }>;
}) {
  const { id, sid } = await props.params;
  const user = await requireUser();
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) notFound();

  const session = await db.measurementSession.findFirst({
    where: { id: sid, partRevisionId: revision.revisionId, mode: "INSPECTION" },
    include: { measurements: { include: { device: true }, orderBy: { createdAt: "desc" } } },
  });
  if (!session) notFound();

  const devices = await db.metrologyDevice.findMany({
    where: { organizationId: user.organizationId },
    orderBy: { description: "asc" },
  });

  const open = session.status === "IN_PROGRESS";
  const characteristics = revision.features.filter((f) => f.tolerance || f.critical || f.inspectionMethod);

  /* ---------------- actions ---------------- */

  async function record(formData: FormData) {
    "use server";
    const currentUser = await requireUser();
    const rev = await loadRevision(currentUser.organizationId, id);
    if (!rev) notFound();
    const s = await db.measurementSession.findFirst({
      where: { id: sid, partRevisionId: rev.revisionId, mode: "INSPECTION", status: "IN_PROGRESS" },
    });
    if (!s) redirect(`/parts/${id}/inspection/session/${sid}`);

    const featureId = String(formData.get("featureId"));
    const feature = rev.features.find((f) => f.id === featureId);
    const deviceId = String(formData.get("deviceId") || "");
    const device = deviceId
      ? await db.metrologyDevice.findFirst({ where: { id: deviceId, organizationId: currentUser.organizationId } })
      : null;
    const value = Number(formData.get("value"));
    // No instrument, no reading. The uncertainty comes from the instrument
    // record; there is nothing honest to write in its place.
    if (!feature || !device || !Number.isFinite(value)) redirect(`/parts/${id}/inspection/session/${sid}`);

    const measurement = await db.measurement.create({
      data: {
        sessionId: s.id,
        featureId: feature.id,
        deviceId: device.id,
        label: `${feature.label} — first article`,
        measuredValue: value,
        units: rev.units,
        uncertainty: device.uncertainty,
        repeatCount: Math.max(1, Number(formData.get("repeatCount")) || 1),
        context: contextOf(feature),
        // An inspection reading is a statement about the article, not a
        // nominal to be reasoned about. It is kept as measured.
        resolution: "KEPT_MEASURED",
        resolvedValue: value,
        resolvedBy: currentUser.id,
        resolvedAt: new Date(),
      },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "Measurement",
      entityId: measurement.id,
      action: "CREATE",
      actorType: "HUMAN",
      reason: "First-article inspection reading",
      newValue: `${feature.label}: ${value.toFixed(4)} ±${device.uncertainty.toFixed(4)} (${device.description})`,
    });

    redirect(`/parts/${id}/inspection/session/${sid}`);
  }

  async function complete() {
    "use server";
    const currentUser = await requireUser();
    const rev = await loadRevision(currentUser.organizationId, id);
    if (!rev) notFound();
    await db.measurementSession.updateMany({
      where: { id: sid, partRevisionId: rev.revisionId, mode: "INSPECTION", status: "IN_PROGRESS" },
      data: { status: "COMPLETED", completedAt: new Date() },
    });
    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "MeasurementSession",
      entityId: sid,
      action: "UPDATE",
      actorType: "HUMAN",
      reason: "First-article session completed",
    });
    redirect(`/parts/${id}/fair`);
  }

  /* ---------------- render ---------------- */

  const uncalibrated = devices.filter((d) => !d.calibrated);

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <Link href={`/parts/${id}/inspection`} className="tech-label hover:text-platinum">
          Inspection
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">{session.name}</span>
        <StatusChip tone={open ? "precision" : "neutral"}>{open ? "In progress" : "Completed"}</StatusChip>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="Every reading requires an instrument from the metrology inventory. The uncertainty on the reading is the instrument's, never typed in, and the verdict beside each reading is the same rule the FAIR report runs.">
            {session.name}
          </SectionHeading>

          {uncalibrated.length > 0 && (
            <Notice tone="review" title={`${uncalibrated.length} instrument${uncalibrated.length === 1 ? " is" : "s are"} not calibrated`}>
              Readings taken with an uncalibrated instrument are recorded like any other, but their uncertainty
              cannot be defended at audit. Calibrate before the first article if this report matters.
            </Notice>
          )}

          {characteristics.map((f) => {
            const readings = session.measurements.filter((m) => m.featureId === f.id);
            const latest = readings[0];
            const verdict = assessConformance(
              f,
              latest ? { value: latest.resolvedValue ?? latest.measuredValue, uncertainty: latest.uncertainty } : undefined,
            );
            return (
              <Panel
                key={f.id}
                title={f.label}
                meta={
                  <span className="flex items-center gap-2">
                    {f.critical && <StatusChip tone="review">Crit</StatusChip>}
                    <VerdictChip verdict={verdict} measured={Boolean(latest)} />
                  </span>
                }
                dense
              >
                <div className="space-y-3 px-4 py-3">
                  <p className="font-mono text-[12px] text-platinum-dim tabular-nums">
                    {featureSummary(f)}
                    {f.tolerance && <span className="ml-3 text-muted">{fmtTol(f.tolerance)}</span>}
                    {f.inspectionMethod && <span className="ml-3 text-muted">· {f.inspectionMethod}</span>}
                  </p>

                  {readings.length > 0 && (
                    <ul className="space-y-1">
                      {readings.map((m) => (
                        <li key={m.id} className="flex flex-wrap items-baseline gap-x-3 font-mono text-[11.5px] tabular-nums">
                          <span className="text-platinum">{(m.resolvedValue ?? m.measuredValue).toFixed(4)}″</span>
                          <span className="text-muted">±{m.uncertainty.toFixed(4)}″</span>
                          <span className="text-muted">n={m.repeatCount}</span>
                          <span className="text-muted">{m.device?.description ?? "instrument not recorded"}</span>
                          <span className="text-muted">{m.createdAt.toISOString().slice(0, 16).replace("T", " ")}</span>
                        </li>
                      ))}
                    </ul>
                  )}

                  {verdict.verdict === "CANNOT_DETERMINE" && latest && (
                    <p className="text-[11.5px] leading-relaxed text-review">{verdict.reason}</p>
                  )}
                  {verdict.verdict === "NONCONFORMS" && (
                    <p className="text-[11.5px] leading-relaxed text-risk">
                      {verdict.departure > 0 ? "+" : ""}
                      {verdict.departure.toFixed(4)}″ beyond the limit. Documented, not dispositioned.
                    </p>
                  )}

                  {open && (
                    <form action={record} className="flex flex-wrap items-end gap-3">
                      <input type="hidden" name="featureId" value={f.id} />
                      <div className="w-36">
                        <Field label="Measured value">
                          <input name="value" type="number" step="0.0001" required className={inputClass} placeholder="0.0000" />
                        </Field>
                      </div>
                      <div className="w-64">
                        <Field label="Instrument">
                          <select name="deviceId" required className={inputClass} defaultValue="">
                            <option value="" disabled>
                              Select — required
                            </option>
                            {devices.map((d) => (
                              <option key={d.id} value={d.id}>
                                {d.description} (±{d.uncertainty.toFixed(4)}″{d.calibrated ? "" : " · UNCALIBRATED"})
                              </option>
                            ))}
                          </select>
                        </Field>
                      </div>
                      <div className="w-24">
                        <Field label="Repeats">
                          <input name="repeatCount" type="number" min={1} defaultValue={3} className={inputClass} />
                        </Field>
                      </div>
                      <Button type="submit">Record</Button>
                    </form>
                  )}
                </div>
              </Panel>
            );
          })}

          {open && (
            <form action={complete} className="flex items-center justify-between gap-4 border border-line bg-surface px-4 py-3">
              <p className="text-[12px] leading-relaxed text-muted">
                Completing the session locks it. {session.measurements.length} reading
                {session.measurements.length === 1 ? "" : "s"} recorded; characteristics without one stay
                UNDETERMINED on the FAIR — completing does not fill them in.
              </p>
              <Button type="submit" variant="primary">
                Complete session
              </Button>
            </form>
          )}
        </div>
      </main>
    </>
  );
}

function VerdictChip({ verdict, measured }: { verdict: ReturnType<typeof assessConformance>; measured: boolean }) {
  if (!measured) return <StatusChip tone="unknown">Not measured</StatusChip>;
  if (verdict.verdict === "CONFORMS") return <StatusChip tone="pass">Conforms</StatusChip>;
  if (verdict.verdict === "NONCONFORMS") return <StatusChip tone="risk">Nonconforms</StatusChip>;
  return <StatusChip tone="review">Undetermined</StatusChip>;
}

function contextOf(f: Feature): string {
  switch (f.kind) {
    case "BORE":
    case "CIRC_POCKET":
      return "BORE";
    case "DRILLED_HOLE":
    case "COUNTERBORE":
    case "COUNTERSINK":
      return "HOLE";
    case "TAPPED_HOLE":
      return "THREAD";
    case "FACE":
      return "THICKNESS";
    default:
      return "GENERAL";
  }
}

export const dynamic = "force-dynamic";

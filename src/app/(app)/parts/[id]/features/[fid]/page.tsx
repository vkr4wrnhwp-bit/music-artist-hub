import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { revalidatePath } from "next/cache";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import { getMetrology } from "@/lib/data";
import { fmtTol } from "@/lib/domain/features";
import {
  analyseMating,
  MATING_COMPONENTS,
  MATING_LABEL,
  type MatingComponent,
  type InterfaceSide,
} from "@/lib/engines/mating";
import { assessCapability, measurementGeometry } from "@/lib/engines/inspection-capability";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { Button, DataRow, Notice, Panel, SectionHeading, StatusChip, inputClass } from "@/components/ui";
import { comparableJobs } from "@/lib/disagreement";
import { Disagree } from "@/components/disagree";
import { MatingDesignationField } from "@/components/mating-designation";
import { recordPartDisagreement } from "../../disagree-actions";

/**
 * FEATURE DETAIL — FUNCTION BEFORE DIMENSION
 *
 * The question this page exists to ask is not "how big is it". It is "what
 * does it have to do", because that is the question with an answer that has a
 * tolerance on it.
 *
 * A measured 1.5744" is a number somebody wrote down. ⌀40 mm H7 because a 6203
 * goes in it is an engineering decision, and the difference between the two is
 * everything downstream: which tool, which finishing pass, which instrument
 * has to verify it, and whether the part can be accepted at all.
 *
 * Nothing here is applied automatically. A dimension from a standards table
 * and a dimension from an instrument are different kinds of fact.
 */

export default async function FeatureDetailPage(props: {
  params: Promise<{ id: string; fid: string }>;
  searchParams: Promise<{ saved?: string }>;
}) {
  const { id, fid } = await props.params;
  const { saved } = await props.searchParams;
  const user = await requireUser();
  const jobs = await comparableJobs(user.organizationId);

  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  const feature = pkg.revision.features.find((f) => f.id === fid);
  if (!feature) notFound();

  const row = await db.feature.findFirst({
    where: { id: fid, partRevision: { part: { organizationId: user.organizationId } } },
  });
  if (!row) notFound();

  const metrology = await getMetrology(user.organizationId);

  const diameter = "diameter" in feature ? feature.diameter : null;
  const band = feature.tolerance ? feature.tolerance.plus + feature.tolerance.minus : null;

  /* ---- What can measure this, and how well ---- */

  // Which instruments can reach this is the engine's decision, not this page's.
  // A local list here disagreed with the readiness gate on dowel and mounting
  // holes, which the engine classifies POSITION rather than INTERNAL.
  const capability = assessCapability(
    {
      featureId: feature.id,
      featureLabel: feature.label,
      geometry: measurementGeometry(feature),
      nominal: diameter,
      toleranceBand: band,
      critical: feature.critical,
    },
    metrology.map((d) => ({
      id: d.id,
      deviceType: d.deviceType as string,
      description: d.description,
      resolution: d.resolution,
      uncertainty: d.uncertainty,
      rangeMin: d.rangeMin ?? null,
      rangeMax: d.rangeMax ?? null,
      calibrated: d.calibrated,
    })),
  );

  /* ---- Reasoning from the interface ---- */

  // Which side of the fit this feature is — a hole is the housing, everything
  // else is the shaft. Separate question from which instrument can reach it.
  const isHole = ["DRILLED_HOLE", "TAPPED_HOLE", "BORE", "CIRC_POCKET", "RECT_POCKET", "SLOT"].includes(feature.kind);
  const component = (row.matingComponent as MatingComponent | null) ?? "UNKNOWN";
  const side = (row.interfaceSide as InterfaceSide | null) ?? (isHole ? "HOUSING" : "SHAFT");

  const analysis =
    diameter != null
      ? analyseMating({
          measured: diameter,
          component,
          side,
          designation: row.matingDesignation,
          rotatingUnderLoad: row.rotatingUnderLoad,
          // The instrument that produced the measurement bounds what any
          // comparison against a standard can possibly conclude.
          measurementUncertainty: capability.bestInstrument?.uncertainty ?? null,
        })
      : null;

  /* ---- Recording the interface ---- */

  async function saveInterface(formData: FormData) {
    "use server";
    const currentUser = await requireWrite();
    const owned = await db.feature.findFirst({
      where: { id: fid, partRevision: { part: { organizationId: currentUser.organizationId } } },
    });
    if (!owned) notFound();

    const nextComponent = String(formData.get("matingComponent") ?? "UNKNOWN");
    const nextSide = String(formData.get("interfaceSide") ?? "HOUSING");
    const designation = String(formData.get("matingDesignation") ?? "").trim() || null;
    /*
     * Where the designation came from. PHOTO_CONFIRMED means a model read it
     * off a photograph AND a human accepted it against the bearing — it stays
     * an inference somebody confirmed, never a reading believed on its own.
     *
     * The evidence link is only kept when there is a designation to attach it
     * to and a photograph that belongs to this organisation. A photo id posted
     * without a value, or one that is not this shop's, is dropped.
     */
    const sourceRaw = String(formData.get("matingDesignationSource") ?? "");
    const photoRaw = String(formData.get("matingDesignationPhotoId") ?? "");
    const designationSource =
      designation === null ? null : sourceRaw === "PHOTO_CONFIRMED" ? "PHOTO_CONFIRMED" : "USER";
    const photoId =
      designation !== null && designationSource === "PHOTO_CONFIRMED" && photoRaw !== ""
        ? (await db.uploadedAsset.findFirst({
            where: { id: photoRaw, organizationId: currentUser.organizationId },
            select: { id: true },
          }))?.id ?? null
        : null;
    const rotating = formData.get("rotatingUnderLoad") === "on";

    await db.feature.update({
      where: { id: fid },
      data: {
        matingComponent: nextComponent,
        interfaceSide: nextSide,
        matingDesignation: designation,
        matingDesignationSource: designationSource,
        matingDesignationPhotoId: photoId,
        rotatingUnderLoad: rotating,
      },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "Feature",
      entityId: fid,
      action: "UPDATE",
      // A human said what this interfaces with. That is exactly the kind of
      // fact that must never be recorded as anything else.
      actorType: "HUMAN",
      field: "matingComponent",
      oldValue: owned.matingComponent,
      newValue: nextComponent,
      reason: "Mating component recorded",
    });

    revalidatePath(`/parts/${id}/features/${fid}`);
    redirect(`/parts/${id}/features/${fid}?saved=1`);
  }

  /**
   * Accepting a suggested nominal is a separate, explicit act from recording
   * what the feature mates with. Recording the interface is a statement about
   * function; accepting the nominal changes the geometry the whole plan is
   * built on, and it is written with USER provenance because a human chose it.
   */
  async function acceptNominal(formData: FormData) {
    "use server";
    const currentUser = await requireWrite();
    const owned = await db.feature.findFirst({
      where: { id: fid, partRevision: { part: { organizationId: currentUser.organizationId } } },
    });
    if (!owned) notFound();

    const fitClass = String(formData.get("fitClass") ?? "").trim() || null;
    const plus = Number(formData.get("tolerancePlus"));
    const minus = Number(formData.get("toleranceMinus"));

    await db.feature.update({
      where: { id: fid },
      data: {
        fitClass,
        tolerancePlus: Number.isFinite(plus) ? plus : owned.tolerancePlus,
        toleranceMinus: Number.isFinite(minus) ? minus : owned.toleranceMinus,
      },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "Feature",
      entityId: fid,
      action: "UPDATE",
      actorType: "HUMAN",
      field: "fitClass",
      oldValue: owned.fitClass,
      newValue: fitClass,
      reason: "Fit class accepted from the standard mounting recommendation",
    });

    revalidatePath(`/parts/${id}`);
    redirect(`/parts/${id}/features/${fid}?saved=2`);
  }

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">{feature.label}</span>
        <PartStatusChip readiness={pkg.readiness} />
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div>
            <SectionHeading sub="A dimension on its own is a number somebody wrote down. What it has to interface with is the thing that decides what tolerance belongs on it, which tool cuts it, and what has to measure it.">
              {feature.label}
            </SectionHeading>
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
              {diameter != null && (
                <span className="font-mono text-[34px] leading-none tracking-tight text-platinum tabular-nums">
                  ⌀{diameter.toFixed(4)}
                  <span className="ml-1 text-[16px] text-muted">in</span>
                </span>
              )}
              {feature.tolerance && (
                <span className="font-mono text-[15px] text-muted tabular-nums">{fmtTol(feature.tolerance)}</span>
              )}
              {feature.critical && <StatusChip tone="review">Critical</StatusChip>}
              <StatusChip tone="neutral">{feature.kind.replace(/_/g, " ").toLowerCase()}</StatusChip>
            </div>
          </div>

          {saved === "1" && (
            <Notice tone="pass" title="Interface recorded">
              What this feature mates with is stored against the feature. The nominal below is still a suggestion — it
              has not been applied to the geometry.
            </Notice>
          )}
          {saved === "2" && (
            <Notice tone="pass" title="Fit class accepted">
              The tolerance now comes from the standard mounting recommendation rather than from the measured value.
              Downstream readiness, tooling and inspection have been re-evaluated against it.
            </Notice>
          )}

          {/* ---------------- What mates with this ---------------- */}
          <Panel title="What mates with this feature?">
            <form action={saveInterface} className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {MATING_COMPONENTS.map((c) => (
                  <label
                    key={c}
                    className="flex cursor-pointer items-center gap-1.5 border border-line-strong px-2.5 py-1.5 text-[12px] text-platinum-dim has-checked:border-precision has-checked:text-precision"
                  >
                    <input
                      type="radio"
                      name="matingComponent"
                      value={c}
                      defaultChecked={component === c}
                      className="accent-[color:var(--c-blue)]"
                    />
                    {MATING_LABEL[c]}
                  </label>
                ))}
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="interfaceSide" className="tech-label mb-1 block">
                    This feature is the
                  </label>
                  <select id="interfaceSide" name="interfaceSide" defaultValue={side} className={inputClass}>
                    <option value="HOUSING">Housing — the component goes into it</option>
                    <option value="SHAFT">Journal — the component goes onto it</option>
                  </select>
                </div>

                <MatingDesignationField
                  featureId={fid}
                  initial={row.matingDesignation ?? ""}
                  showPhoto={component === "BEARING"}
                />
              </div>

              <label className="flex items-center gap-2 text-[12.5px] text-platinum-dim">
                <input
                  type="checkbox"
                  name="rotatingUnderLoad"
                  defaultChecked={row.rotatingUnderLoad}
                  className="accent-[color:var(--c-blue)]"
                />
                This ring turns relative to the load
              </label>
              <p className="max-w-2xl text-[12px] leading-relaxed text-muted">
                Which ring rotates decides the fit, and it is the one thing a dimension cannot tell you. A ring that
                turns under load has to be an interference fit or it creeps and frets its seat; the stationary one is
                left loose enough to assemble and to grow with heat.
              </p>

              <Button type="submit" variant="primary">
                Record interface
              </Button>
            </form>
          </Panel>

          {/* ---------------- What CANVAS makes of it ---------------- */}
          {analysis && (
            <Panel
              title="Why CANVAS thinks this"
              meta={
                analysis.suggestedNominal.value != null ? (
                  <span className="tech-label">
                    {analysis.suggestedNominal.source.toLowerCase()} · {analysis.suggestedNominal.confidence.toLowerCase()}
                  </span>
                ) : null
              }
            >
              <p className="max-w-2xl text-[13px] leading-relaxed text-platinum">{analysis.reasoning}</p>

              {analysis.needs.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {analysis.needs.map((n) => (
                    <li key={n} className="text-[12px] leading-relaxed text-review">
                      Needs — {n}
                    </li>
                  ))}
                </ul>
              )}

              {analysis.best && (
                <>
                  <div className="mt-4 grid gap-x-8 sm:grid-cols-2">
                    <DataRow label="Measured" value={`${diameter?.toFixed(4)}″`} />
                    <DataRow
                      label="Suggested nominal"
                      value={
                        analysis.suggestedNominal.value != null
                          ? `${analysis.best.nominalMm} mm (${analysis.suggestedNominal.value.toFixed(5)}″)`
                          : "—"
                      }
                    />
                    <DataRow label="Difference" value={`${Math.abs(analysis.best.differenceIn).toFixed(5)}″`} />
                    <DataRow
                      label="Bearing"
                      value={`${analysis.best.bearing.designation} — ${analysis.best.bearing.bore} × ${analysis.best.bearing.outer} × ${analysis.best.bearing.width} mm`}
                    />
                  </div>

                  {analysis.candidates.length > 1 && (
                    <div className="mt-4">
                      <p className="tech-label mb-1.5">Others within reach</p>
                      <p className="text-[12px] leading-relaxed text-muted">
                        {analysis.candidates
                          .slice(1)
                          .map(
                            (c) =>
                              `${c.bearing.designation} (${c.bearing.bore}×${c.bearing.outer}×${c.bearing.width})`,
                          )
                          .join(" · ")}
                      </p>
                    </div>
                  )}
                </>
              )}

              {/* Accepting the standard's tolerance is an explicit human act */}
              {analysis.best?.fit && (
                <form action={acceptNominal} className="mt-5 border-t border-line pt-5">
                  <p className="tech-label mb-2">Standard mounting fit</p>
                  <div className="grid gap-x-8 sm:grid-cols-2">
                    <DataRow label="Fit class" value={analysis.best.fit.fitClass} />
                    <DataRow
                      label="Limits"
                      value={`${analysis.best.fit.minIn.toFixed(4)}–${analysis.best.fit.maxIn.toFixed(4)}″`}
                    />
                    <DataRow label="Band" value={`${analysis.best.fit.bandIn.toFixed(5)}″`} />
                    <DataRow
                      label="Measured falls"
                      value={analysis.best.withinFit === null ? "—" : analysis.best.withinFit ? "inside" : "outside"}
                      tone={analysis.best.withinFit === false ? "review" : undefined}
                    />
                  </div>
                  <p className="mt-2 max-w-2xl text-[12.5px] leading-relaxed text-muted">
                    {analysis.best.fit.rationale}
                  </p>

                  <input type="hidden" name="fitClass" value={analysis.best.fit.fitClass} />
                  <input type="hidden" name="tolerancePlus" value={analysis.best.fit.upperIn} />
                  <input type="hidden" name="toleranceMinus" value={Math.abs(analysis.best.fit.lowerIn)} />

                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <Button type="submit" variant="primary">
                      Accept {analysis.best.fit.fitClass} on this feature
                    </Button>
                    <span className="text-[11.5px] text-muted">
                      Nothing is applied until you accept it. The measured value stays as measured.
                    </span>
                  </div>
                </form>
              )}
              {/* Accept it, or say why not. A suggested nominal is CANVAS
                  reading a measurement against a fit table; the machinist may
                  know what this bore actually mates with. */}
              {analysis?.best?.fit && (
                <div className="mt-4 border-t border-line pt-3">
                  <Disagree
                    action={recordPartDisagreement}
                    partId={id}
                    surface="part"
                    subjectType="NOMINAL"
                    subjectId={fid}
                    canvasPosition={`${feature.label} — ${analysis.best.bearing.designation}, suggested ${analysis.best.fit.fitClass} against a ${analysis.best.nominalMm} mm nominal (${analysis.best.differenceIn >= 0 ? "+" : ""}${analysis.best.differenceIn.toFixed(4)}" from measured).`}
                    jobs={jobs}
                  />
                </div>
              )}
            </Panel>
          )}

          {/* ---------------- Can it be verified ---------------- */}
          <Panel title="Can this be verified?">
            <p className="max-w-2xl text-[13px] leading-relaxed text-platinum">{capability.reason}</p>
            {capability.bestInstrument && (
              <div className="mt-3 grid gap-x-8 sm:grid-cols-2">
                <DataRow label="Best instrument on hand" value={capability.bestInstrument.description} />
                <DataRow label="Its uncertainty" value={`±${capability.bestInstrument.uncertainty.toFixed(4)}″`} />
                <DataRow
                  label="Tolerance band"
                  value={capability.toleranceBand != null ? `${capability.toleranceBand.toFixed(4)}″` : "none specified"}
                />
                <DataRow
                  label="Consumed by the instrument"
                  value={capability.consumedFraction != null ? `${(capability.consumedFraction * 100).toFixed(0)}%` : "—"}
                  tone={capability.verdict === "CAPABLE" ? "pass" : capability.verdict === "MARGINAL" ? "review" : "risk"}
                />
              </div>
            )}
            {capability.recommendations.length > 0 && (
              <ul className="mt-3 space-y-1">
                {capability.recommendations.map((r) => (
                  <li key={r} className="flex gap-2 text-[12px] leading-relaxed text-muted">
                    <span className="text-precision">—</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

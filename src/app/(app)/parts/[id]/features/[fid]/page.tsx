import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { revalidatePath } from "next/cache";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import { getMetrology } from "@/lib/data";
import { fmtTol, FUNCTIONAL_ROLES } from "@/lib/domain/features";
import {
  analyseMating,
  MATING_COMPONENTS,
  MATING_LABEL,
  type MatingComponent,
  type InterfaceSide,
} from "@/lib/engines/mating";
import { assessCapability, measurementGeometry } from "@/lib/engines/inspection-capability";
import { methodOptions, geometryPhrase } from "@/lib/engines/inspection-method";
import { assignInspectionMethod } from "../inspection-method-actions";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { Button, DataRow, Notice, Panel, SectionHeading, StatusChip, inputClass } from "@/components/ui";
import { comparableJobs } from "@/lib/disagreement";
import { Disagree } from "@/components/disagree";
import { MatingDesignationField } from "@/components/mating-designation";
import { recordPartDisagreement } from "../../disagree-actions";
import { recordFeatureResponsibility } from "../responsibility-actions";
import { FeatureSpecimen } from "@/components/feature-specimen";
import {
  SPECIMEN_TABS,
  SPECIMEN_TAB_LABEL,
  deviationIsResolvable,
  specimenDimensions,
  viewsFor,
  type MeasuredValue,
  type SpecimenTab,
  type SpecimenView,
} from "@/lib/engines/specimen";

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
  searchParams: Promise<{ saved?: string; tab?: string; view?: string }>;
}) {
  const { id, fid } = await props.params;
  const { saved, tab: tabRaw, view: viewRaw } = await props.searchParams;
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

  // Every method this shop could honestly assign, each carrying the verdict it
  // would produce. Computed by the capability engine, not ranked here.

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
      // Once a method is assigned, this gate judges the method. See
      // engines/inspection-method.ts.
      chosenDeviceType: row.inspectionDeviceType,
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

  const instrumentList = metrology.map((d) => ({
    id: d.id,
    deviceType: d.deviceType as string,
    description: d.description,
    resolution: d.resolution,
    uncertainty: d.uncertainty,
    rangeMin: d.rangeMin ?? null,
    rangeMax: d.rangeMax ?? null,
    calibrated: d.calibrated,
  }));
  const options = methodOptions(feature, instrumentList);
  const assignMethod = assignInspectionMethod.bind(null, id);
  const responsibilityAction = recordFeatureResponsibility.bind(null, id);

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

  /* ---------------- The specimen ---------------- */

  /*
   * Readings taken against THIS feature, matched to the dimension they are a
   * reading of by the measurement context. A bore reading is a diameter; a
   * thickness reading is a depth. A reading whose context does not name a
   * dimension this feature carries is left out rather than attached to
   * whichever one happens to be first.
   */
  const CONTEXT_FIELD: Record<string, string> = {
    BORE: "diameter",
    SHAFT: "diameter",
    HOLE: "diameter",
    THREAD: "diameter",
    THICKNESS: "depth",
  };
  const measurementRows = await db.measurement.findMany({
    where: { featureId: fid },
    orderBy: { createdAt: "desc" },
  });
  const measured: MeasuredValue[] = measurementRows
    .map((m) => ({
      field: CONTEXT_FIELD[m.context] ?? "",
      value: m.resolution === "ACCEPTED_NOMINAL" && m.resolvedValue != null ? m.resolvedValue : m.measuredValue,
      uncertainty: m.uncertainty,
      at: m.createdAt,
    }))
    .filter((m) => m.field !== "");

  const dimensions = specimenDimensions(feature, feature.tolerance ?? null, measured);
  const views = viewsFor(feature.kind);
  const view: SpecimenView = views.includes(viewRaw as SpecimenView) ? (viewRaw as SpecimenView) : views[0];
  const tab: SpecimenTab = (SPECIMEN_TABS as readonly string[]).includes(tabRaw ?? "")
    ? (tabRaw as SpecimenTab)
    : "GEOMETRY";
  const href = (t: SpecimenTab, v: SpecimenView = view) => `/parts/${id}/features/${fid}?tab=${t}&view=${v}`;

  // Operations planned to cut this feature, and the audit trail behind it.
  const operations = pkg.setups.flatMap((sx) =>
    sx.operations.filter((o) => o.featureId === fid).map((o) => ({ setup: sx.name, op: o })),
  );
  const history = await db.auditLog.findMany({
    where: { organizationId: user.organizationId, entityType: "Feature", entityId: fid },
    orderBy: { createdAt: "desc" },
    take: 40,
    include: { user: { select: { name: true, email: true } } },
  });

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

          {/* ---------------- The specimen, isolated and enlarged ---------------- */}
          <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
            <div>
              <div className="border border-line" style={{ height: 300 }}>
                <FeatureSpecimen feature={feature} view={view} dimensions={dimensions} />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {views.map((v) => (
                  <Link
                    key={v}
                    href={href(tab, v)}
                    aria-current={v === view ? "true" : undefined}
                    className={`border px-2 py-1 text-[10.5px] font-semibold uppercase tracking-[0.12em] ${
                      v === view ? "border-precision text-precision" : "border-line-strong text-muted hover:text-platinum-dim"
                    }`}
                  >
                    {v.toLowerCase()}
                  </Link>
                ))}
                <span className="text-[11px] text-muted">
                  {views.length === 1
                    ? "One view — a section of this feature is the same drawing as the plan."
                    : "Two orthographic views. Free 3D rotation of the isolated feature is not built; this is a drawing, and it says which view it is."}
                </span>
              </div>
            </div>

            {/* Nominal against measured, for every dimension the feature carries. */}
            <div>
              <p className="tech-label mb-1.5">Nominal against measured</p>
              <table className="w-full border-collapse text-[12px]">
                <thead>
                  <tr className="border-b border-line text-left">
                    <th className="py-1 font-normal text-muted">Dimension</th>
                    <th className="py-1 font-normal text-muted">Nominal</th>
                    <th className="py-1 font-normal text-muted">Measured</th>
                    <th className="py-1 font-normal text-muted">Deviation</th>
                  </tr>
                </thead>
                <tbody>
                  {dimensions.map((d) => {
                    const resolvable = deviationIsResolvable(d.deviation, d.uncertainty);
                    return (
                      <tr key={d.label} className="border-b border-line/50">
                        <td className="py-1 text-platinum-dim">{d.label}</td>
                        <td className="py-1 font-mono tabular-nums text-platinum">
                          {d.nominal != null ? d.nominal.toFixed(4) : "not recorded"}
                        </td>
                        <td className="py-1 font-mono tabular-nums text-platinum">
                          {d.measured != null ? d.measured.toFixed(4) : <span className="text-muted">not measured</span>}
                        </td>
                        <td
                          className={`py-1 font-mono tabular-nums ${
                            d.verdict === "OUT_OF_TOLERANCE" ? "text-risk" : d.verdict === "IN_TOLERANCE" ? "text-pass" : "text-muted"
                          }`}
                        >
                          {d.deviation == null
                            ? "—"
                            : `${d.deviation >= 0 ? "+" : ""}${d.deviation.toFixed(4)}`}
                          {resolvable === false && (
                            <span className="ml-1 text-[10.5px] text-review">within the instrument</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {dimensions.every((d) => d.measured == null) && (
                <p className="mt-2 text-[11.5px] leading-relaxed text-muted">
                  Nothing has been measured against this feature yet. The measured column stays empty rather than
                  repeating the nominal — a comparison with one side missing is not a comparison.
                </p>
              )}
            </div>
          </div>

          {/* ---------------- Tabs ---------------- */}
          <div className="flex flex-wrap gap-1 border-b border-line pb-2">
            {SPECIMEN_TABS.map((t) => (
              <Link
                key={t}
                href={href(t)}
                aria-current={t === tab ? "page" : undefined}
                className={`px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                  t === tab ? "border-b-2 border-b-precision text-platinum" : "text-muted hover:text-platinum-dim"
                }`}
              >
                {SPECIMEN_TAB_LABEL[t]}
              </Link>
            ))}
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

          {/* ---------------- FUNCTION ---------------- */}
          {tab === "FUNCTION" && (
          <Panel title="What this feature is for">
            <p className="max-w-2xl text-[12.5px] leading-relaxed text-muted">
              Set when the feature was entered, and correctable here. It was not: a machinist who realised the top face
              was the datum had to delete the feature and enter it again, losing its measurements and its inspection
              method along with the mistake.
            </p>

            <form action={responsibilityAction} className="mt-4 space-y-4">
              <input type="hidden" name="featureId" value={feature.id} />

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="label" className="tech-label mb-1 block">
                    Name
                  </label>
                  <input id="label" name="label" defaultValue={row.label} className={inputClass} />
                </div>
                <div>
                  <label htmlFor="functionalRole" className="tech-label mb-1 block">
                    What it does
                  </label>
                  <select id="functionalRole" name="functionalRole" defaultValue={row.functionalRole} className={inputClass}>
                    {FUNCTIONAL_ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r.replace(/_/g, " ").toLowerCase()}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-[10.5px] leading-relaxed text-muted">
                    A datum face is what the workholding assessment looks for when it says none is designated.
                  </p>
                </div>
                <div>
                  <label htmlFor="surfaceFinish" className="tech-label mb-1 block">
                    Surface finish, Ra µin
                  </label>
                  <input
                    id="surfaceFinish"
                    name="surfaceFinish"
                    inputMode="decimal"
                    defaultValue={row.surfaceFinish ?? ""}
                    placeholder="none stated"
                    className={inputClass}
                  />
                </div>
              </div>

              <label className="flex items-start gap-2 text-[12.5px] text-platinum-dim">
                <input type="checkbox" name="critical" defaultChecked={row.critical} className="mt-0.5 accent-[color:var(--c-blue)]" />
                <span>
                  This feature is critical
                  <span className="mt-0.5 block text-[11px] leading-relaxed text-muted">
                    {row.critical
                      ? "Turning this off closes the critical tolerance strategy gate for this feature and drops it from a derived inspection plan. Any inspection method already assigned is kept — it is still a decision somebody made."
                      : "Turning this on opens the critical tolerance strategy gate for this feature until a method is assigned to it, and puts it in a derived inspection plan."}
                  </span>
                </span>
              </label>

              <Button type="submit" variant="primary" size="sm">
                Record what it is for
              </Button>
            </form>
          </Panel>
          )}

          {tab === "FUNCTION" && (
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

          )}

          {/* ---------------- MEASURE ---------------- */}
          {tab === "MEASURE" && !analysis && (
            <Panel title="Nothing to reason about yet">
              <p className="max-w-2xl text-[12.5px] leading-relaxed text-muted">
                Nominal reasoning runs on a measured diameter, and this feature has none — either it carries no
                diameter, or nothing has been measured against it. The table above stays empty rather than repeating
                the nominal, and a suggestion would be reasoning about a number nobody took.
              </p>
            </Panel>
          )}
          {tab === "MEASURE" && analysis && (
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

          {/* ---------------- INSPECT ---------------- */}
          {tab === "INSPECT" && (
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

            {/* ---- How this feature will be verified ---- */}
            <div className="mt-6 border-t border-line pt-5">
              <SectionHeading>How this one will be checked</SectionHeading>

              {row.inspectionMethod ? (
                <div className="mt-3 grid gap-x-8 sm:grid-cols-2">
                  <DataRow label="Method" value={row.inspectionMethod} />
                  <DataRow
                    label="Decided by"
                    value={
                      row.inspectionMethodBy
                        ? `${row.inspectionMethodBy}${row.inspectionMethodAt ? ` · ${row.inspectionMethodAt.toISOString().slice(0, 10)}` : ""}`
                        : "not recorded"
                    }
                  />
                </div>
              ) : (
                <p className="mt-2 max-w-2xl text-[12.5px] leading-relaxed text-platinum">
                  No method is assigned.{" "}
                  {feature.critical
                    ? "This feature is flagged critical, so the critical tolerance strategy gate stays open until one is."
                    : "Assigning one is optional for a feature that is not critical."}
                </p>
              )}

              <p className="mt-3 max-w-2xl text-[12px] leading-relaxed text-muted">
                Only instruments this shop owns that can physically reach a {geometryPhrase(measurementGeometry(feature))}{" "}
                feature of this size are listed. Once a method is assigned it is the method — not the best instrument in
                the drawer — that the inspection capability gate judges, so choosing a coarser one makes this part read
                worse rather than better.
              </p>

              {options.length === 0 ? (
                <Notice tone="review" title="No instrument in this shop can reach this feature">
                  Nothing on the metrology list can measure a {geometryPhrase(measurementGeometry(feature))} feature of
                  this size, so there is no method to assign. Add a suitable instrument on the metrology page.
                </Notice>
              ) : (
                <form action={assignMethod} className="mt-4 space-y-3">
                  <input type="hidden" name="featureId" value={feature.id} />
                  <div className="space-y-1.5">
                    {options.map((o) => (
                      <label
                        key={o.deviceType}
                        className="flex cursor-pointer items-start gap-3 border border-line bg-surface px-3 py-2.5 hover:border-precision"
                      >
                        <input
                          type="radio"
                          name="deviceType"
                          value={o.deviceType}
                          defaultChecked={row.inspectionDeviceType === o.deviceType}
                          className="mt-1 accent-[var(--canvas-precision)]"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="text-[13px] text-platinum">{o.label}</span>
                            <StatusChip
                              tone={o.verdict === "CAPABLE" ? "pass" : o.verdict === "MARGINAL" ? "review" : "risk"}
                            >
                              {o.verdict.replace(/_/g, " ")}
                            </StatusChip>
                            {o.consumedFraction != null && (
                              <span className="tech-label text-muted">
                                {(o.consumedFraction * 100).toFixed(0)}% of band
                              </span>
                            )}
                          </span>
                          <span className="mt-0.5 block text-[12px] leading-relaxed text-muted">{o.reason}</span>
                          <span className="mt-0.5 block text-[11.5px] leading-relaxed text-muted">
                            {o.instruments.map((d) => d.description).join(", ")}
                          </span>
                        </span>
                      </label>
                    ))}
                    {row.inspectionDeviceType && (
                      <label className="flex cursor-pointer items-center gap-3 border border-line bg-surface px-3 py-2.5 hover:border-precision">
                        <input type="radio" name="deviceType" value="" className="accent-[var(--canvas-precision)]" />
                        <span className="text-[13px] text-platinum">
                          Clear the method
                          <span className="ml-2 text-[12px] text-muted">— reopens the critical tolerance strategy gate</span>
                        </span>
                      </label>
                    )}
                  </div>
                  <Button type="submit" variant="primary" size="sm">
                    Record method
                  </Button>
                </form>
              )}
            </div>
          </Panel>
          )}

          {/* ---------------- GEOMETRY ---------------- */}
          {tab === "GEOMETRY" && (
            <Panel title="Geometry">
              <div className="grid gap-x-8 sm:grid-cols-2">
                {dimensions.map((d) => (
                  <DataRow
                    key={d.label}
                    label={d.unit ? `${d.label}, ${d.unit}` : d.label}
                    value={d.nominal != null ? d.nominal.toFixed(4) : "not recorded"}
                  />
                ))}
                <DataRow label="Kind" value={feature.kind.replace(/_/g, " ").toLowerCase()} />
                <DataRow label="Tolerance" value={feature.tolerance ? fmtTol(feature.tolerance) : "none stated"} />
                <DataRow label="Surface finish" value={feature.surfaceFinish != null ? `Ra ${feature.surfaceFinish} µin` : "none stated"} />
                <DataRow label="Critical" value={feature.critical ? "Yes" : "No"} />
              </div>
              <p className="mt-3 max-w-2xl text-[12px] leading-relaxed text-muted">
                The dimensions listed are the ones this kind of feature carries, from the same field description the
                entry form and the proposal path validate against — so this cannot show a dimension the feature does
                not have, or miss one it does.
              </p>
            </Panel>
          )}

          {/* ---------------- MACHINE ---------------- */}
          {tab === "MACHINE" && (
            <Panel title={`How it gets cut — ${operations.length} operation${operations.length === 1 ? "" : "s"}`} dense>
              {operations.length === 0 ? (
                <p className="p-4 text-[12px] leading-relaxed text-muted">
                  No operation is planned against this feature yet. Choosing a machining approach on the Machinist page
                  creates them.
                </p>
              ) : (
                <ul>
                  {operations.map(({ setup, op }) => (
                    <li key={op.id} className="border-b border-line/60 px-4 py-3 last:border-0">
                      <div className="flex flex-wrap items-baseline justify-between gap-3">
                        <span className="font-mono text-[12.5px] text-platinum">{op.label}</span>
                        <span className="tech-label">{setup}</span>
                      </div>
                      <p className="tech-label mt-1">
                        {op.type.replace(/_/g, " ").toLowerCase()} · from Z{op.topZ.toFixed(3)} to Z{op.finalZ.toFixed(3)}
                        {op.tool ? ` · T${op.tool.toolNumber} ${op.tool.description}` : " · no tool assigned"}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}

          {/* ---------------- HISTORY ---------------- */}
          {tab === "HISTORY" && (
            <Panel title={`What has happened to this feature — ${history.length}`} dense>
              {history.length === 0 ? (
                <p className="p-4 text-[12px] leading-relaxed text-muted">
                  Nothing is on record for this feature. Every entry here is read from the audit log, so an empty list
                  means nothing was done to it rather than that nothing was kept.
                </p>
              ) : (
                <ul>
                  {history.map((h) => (
                    <li key={h.id} className="border-b border-line/60 px-4 py-3 last:border-0">
                      <div className="flex flex-wrap items-baseline justify-between gap-3">
                        <span className="font-mono text-[12.5px] text-platinum">
                          {h.reason ?? `${h.action.toLowerCase()}${h.field ? ` — ${h.field}` : ""}`}
                        </span>
                        <span className="tech-label">{h.createdAt.toISOString().slice(0, 16).replace("T", " ")}</span>
                      </div>
                      <p className="tech-label mt-1">
                        {h.user?.name ?? h.user?.email ?? "actor not recorded"} · {h.actorType}
                        {h.oldValue || h.newValue ? ` · ${h.oldValue ?? "—"} → ${h.newValue ?? "—"}` : ""}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

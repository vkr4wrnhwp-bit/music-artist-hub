import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import { getMetrology } from "@/lib/data";
import { fmt, fmtTol } from "@/lib/domain/features";
import type { Feature } from "@/lib/domain/features";
import { isCriticalApplication, missingEngineeringInput } from "@/lib/domain/part-intent";
import { money } from "@/lib/engines/cost";
import { RISK_LABEL } from "@/lib/engines/workholding";
import {
  assessCapability,
  CAPABILITY_LABEL,
  measurementGeometry,
  type CapabilityVerdict,
} from "@/lib/engines/inspection-capability";
import { TopBar, BarMeta, PartShellInfoBridge } from "@/components/nav";
import { PartStatusSummary } from "@/components/part-status";
import { nextActions } from "@/lib/engines/next-action";
import { Workspace } from "@/components/workspace/workspace";
import type {
  DatumInfo,
  FeatureDetail,
  NextActionInfo,
  RunwayData,
  RunwayOperation,
} from "@/components/workspace/panel-data";
import {
  DataRow,
  DevLabel,
  Dot,
  LinkButton,
  Notice,
  ProvenanceBadge,
  StatusChip,
  ValueRow,
  type Tone,
} from "@/components/ui";

/**
 * THE PART WORKSPACE
 *
 * Three zones and a command bar. Everything that used to sit in a stack of
 * horizontal strips between the bar and the viewport has moved: the part's
 * identity and metadata into the command bar, the next action into the
 * operation runway, and the data panels behind the feature panel's tabs. What
 * is left above the workspace is one row — the readiness gates and the routes
 * out of here — because the component is meant to be the thing you look at.
 *
 * Every value handed to the workspace below is loaded or computed here, on the
 * server, from a column that exists. Where a value does not exist — no datum
 * rows, no NC program, no inspection results — the absence travels with it and
 * the client renders the absence.
 */

/* The geometry classifier lives in inspection-capability.ts and is imported
   above. A local copy lived here and disagreed with the gate — it returned
   INTERNAL for dowel and mounting holes the engine classifies POSITION, so the
   panel printed NOT CAPABLE on two features the readiness gate counted as
   verifiable. There is one classifier now. */

const nominalOf = (f: Feature): number | null =>
  "diameter" in f && typeof f.diameter === "number" ? f.diameter : null;

export default async function PartWorkspace(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ intake?: string }>;
}) {
  const { id } = await props.params;
  const { intake } = await props.searchParams;
  const user = await requireUser();

  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  const { revision, readiness } = pkg;
  const critical = isCriticalApplication(revision.intent);
  const gaps = missingEngineeringInput(revision.intent);

  const [proposals, audits, metrology, datumRows, measurementRows, inspectionPlan, ncProgram, latestSession] =
    await Promise.all([
      db.aIRecommendation.findMany({
        where: { partRevisionId: revision.revisionId, status: "PROPOSED" },
        orderBy: { createdAt: "desc" },
      }),
      db.auditLog.findMany({
        where: { entityType: { in: ["Part", "PartRevision", "Feature", "Setup"] }, organizationId: user.organizationId },
        orderBy: { createdAt: "desc" },
        take: 20,
      }),
      getMetrology(user.organizationId),
      db.datum.findMany({
        where: { partRevisionId: revision.revisionId },
        orderBy: [{ system: "asc" }, { letter: "asc" }],
      }),
      db.measurement.findMany({
        where: { session: { partRevisionId: revision.revisionId } },
        orderBy: { createdAt: "desc" },
        include: { device: true, session: true, datum: true },
      }),
      db.inspectionPlan.findFirst({
        where: { partRevisionId: revision.revisionId },
        include: { items: true, _count: { select: { results: true } } },
      }),
      db.nCProgram.findFirst({ where: { partRevisionId: revision.revisionId }, orderBy: { createdAt: "desc" } }),
      db.measurementSession.findFirst({
        where: { partRevisionId: revision.revisionId },
        orderBy: { startedAt: "desc" },
      }),
    ]);

  const moves = pkg.toolpaths.flatMap((tp) => tp.moves);

  // Structured operations for the CUT stock-removal simulation: per-op moves
  // with the real tool geometry and speeds, in plan order. Placeholders have
  // no motion and are excluded — simulating them would be showing nothing and
  // calling it something.
  const allOps = pkg.setups.flatMap((s) => s.operations);
  const simOps = pkg.toolpaths
    .filter((tp) => !tp.isPlaceholder && tp.moves.length > 1)
    .map((tp) => {
      const op = allOps.find((o) => o.id === tp.operationId);
      const tool = pkg.assignedTools.find((t) => t.toolNumber === tp.toolNumber);
      return {
        operationId: tp.operationId,
        label: op?.label ?? tp.type,
        toolNumber: tp.toolNumber,
        toolDiameter: tool?.diameter ?? 0.25,
        fluteLength: tool?.fluteLength ?? 0,
        rpm: tp.parameters.rpm,
        moves: tp.moves,
      };
    });

  async function recordSimulation(payload: { removedVolume: number; totalTime: number; collisions: number }) {
    "use server";
    const currentUser = await requireUser();
    const fresh = await buildPackage(currentUser.organizationId, id);
    if (!fresh) notFound();
    // One row per setup: the simulation covered the whole plan. The flags are
    // true in the geometric sense only — stock removal and clearance were
    // simulated; forces were not, and the result says so.
    for (const s of fresh.setups) {
      await db.simulation.create({
        data: {
          setupId: s.id,
          kind: "VISUALIZATION",
          status: "COMPLETE",
          verifiedStockRemoval: true,
          collisionChecked: true,
          resultJson: JSON.stringify({
            scope: "GEOMETRIC — material removal and clearance only, no forces modelled",
            removedVolume: payload.removedVolume,
            totalTimeMinutes: payload.totalTime,
            collisions: payload.collisions,
          }),
        },
      });
    }
    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "PartRevision",
      entityId: fresh.revision.revisionId,
      action: "GENERATE",
      actorType: "HUMAN",
      reason: "Stock-removal simulation watched to completion and recorded",
      newValue: `${payload.removedVolume.toFixed(3)} in³ removed, ${payload.collisions} collision(s), ${payload.totalTime.toFixed(2)} min`,
    });
  }

  const primarySetup = pkg.setups[0];
  // HOLD draws the setup, so it needs what the holding model concluded about
  // it — not a second opinion computed here. Every field below is either a
  // recorded setup value or an output of assessHoldingMargin, so the callouts
  // in the viewport and the margin on /setups cannot disagree.
  const primaryAssessment = primarySetup ? pkg.workholdingBySetup[primarySetup.id] ?? null : null;
  const primaryMargin = primaryAssessment?.holdingMargin ?? null;

  const fixture = pkg.primaryWorkholding
    ? {
        jawWidth: pkg.primaryWorkholding.jawWidth,
        jawHeight: pkg.primaryWorkholding.jawHeight,
        gripDepth: primarySetup?.gripDepth ?? null,
        gripLength: primarySetup?.gripLength ?? null,
        stockProjection: primarySetup?.stockProjection ?? null,
        contactArea: primaryMargin?.contactArea ?? null,
        contactPressure: primaryMargin?.contactPressure ?? null,
        margin: primaryMargin?.margin ?? null,
        verdict: primaryMargin?.verdict ?? null,
        governingMode: primaryMargin?.governingMode ?? null,
        jawSurface: primarySetup?.jawSurface ?? null,
      }
    : null;

  /* ---------------- Per-feature evidence for the feature panel ---------------- */

  // The capability engine wants the instruments the shop owns, not a promise
  // about instruments it could buy. This is the same instrument list AND the
  // same geometry classifier the readiness gate is evaluated against — both
  // halves matter, because the gate is the authority on whether the evidence
  // can be obtained and the primary screen must not contradict it.
  const instruments = metrology.map((d) => ({
    id: d.id,
    deviceType: d.deviceType as string,
    description: d.description,
    resolution: d.resolution,
    uncertainty: d.uncertainty,
    rangeMin: d.rangeMin ?? null,
    rangeMax: d.rangeMax ?? null,
    calibrated: d.calibrated,
  }));

  const featureDetails: Record<string, FeatureDetail> = {};
  for (const f of revision.features) {
    const band = f.tolerance ? f.tolerance.plus + f.tolerance.minus : null;
    const capability = assessCapability(
      {
        featureId: f.id,
        featureLabel: f.label,
        geometry: measurementGeometry(f),
        nominal: nominalOf(f),
        toleranceBand: band,
        critical: f.critical,
      },
      instruments,
    );

    const device = capability.bestInstrument
      ? metrology.find((d) => d.id === capability.bestInstrument!.id) ?? null
      : null;

    const item = inspectionPlan?.items.find((i) => i.featureId === f.id) ?? null;

    featureDetails[f.id] = {
      capability: {
        verdict: capability.verdict,
        label: CAPABILITY_LABEL[capability.verdict as CapabilityVerdict],
        reason: capability.reason,
        toleranceBand: capability.toleranceBand,
        consumedFraction: capability.consumedFraction,
        requiredUncertainty: capability.requiredUncertainty,
        bestInstrument: capability.bestInstrument
          ? {
              description: capability.bestInstrument.description,
              deviceType: capability.bestInstrument.deviceType,
              rangeMin: capability.bestInstrument.rangeMin,
              rangeMax: capability.bestInstrument.rangeMax,
              resolution: capability.bestInstrument.resolution,
              uncertainty: capability.bestInstrument.uncertainty,
              calibrated: capability.bestInstrument.calibrated,
              // `calibrationDue` is genuinely null on the seeded devices. A
              // calibration claim with no certificate date is thin evidence and
              // the panel says so rather than implying a date exists.
              calibrationDue: device?.calibrationDue ?? null,
            }
          : null,
      },
      measurements: measurementRows
        .filter((m) => m.featureId === f.id)
        .map((m) => ({
          id: m.id,
          label: m.label,
          value: m.measuredValue,
          units: m.units,
          uncertainty: m.uncertainty,
          repeatCount: m.repeatCount,
          resolution: m.resolution,
          instrument: m.device?.description ?? null,
          operator: m.session.operator ?? null,
          sessionId: m.sessionId,
          sessionName: m.session.name,
          recordedAt: m.createdAt.toISOString().slice(0, 16).replace("T", " "),
          datumLetter: m.datum?.letter ?? null,
        })),
      inspectionItem: item
        ? {
            label: item.label,
            nominal: item.nominal,
            plusTol: item.plusTol,
            minusTol: item.minusTol,
            method: item.method,
            deviceType: item.deviceType,
          }
        : null,
    };
  }

  const datums: DatumInfo[] = datumRows.map((d) => ({
    letter: d.letter,
    system: d.system,
    description: d.description,
    geometryType: d.geometryType,
    accepted: d.acceptedByUser,
    featureId: d.featureId,
  }));

  /* ---------------- The operation runway ---------------- */

  // Sequence, tool, feature and toolpath are real. Execution state is not, and
  // there is no field on this object that could carry it.
  const runwayOperations: RunwayOperation[] = pkg.setups.flatMap((s) =>
    s.operations.map((o): RunwayOperation => {
      const tp = pkg.toolpaths.find((t) => t.operationId === o.id);
      const err = pkg.toolpathErrors.find((e) => e.operationId === o.id);
      return {
        id: o.id,
        setupId: s.id,
        sequence: o.sequence,
        label: o.label,
        type: o.type,
        toolNumber: o.tool?.toolNumber ?? null,
        toolDescription: o.tool?.description ?? null,
        featureId: o.featureId,
        featureLabel: o.feature?.label ?? null,
        cycleMinutes: tp && !tp.isPlaceholder ? tp.cycleTimeMinutes : null,
        moveCount: tp && !tp.isPlaceholder ? tp.moves.length : null,
        isPlaceholder: Boolean(tp?.isPlaceholder),
        error: err?.reason ?? null,
        warnings: tp?.warnings ?? [],
      };
    }),
  );

  const worstSetupId = Object.entries(pkg.workholdingBySetup).sort(
    (a, b) => riskRank(b[1].level) - riskRank(a[1].level),
  )[0]?.[0];
  const worst = worstSetupId ? pkg.workholdingBySetup[worstSetupId] : null;

  const stock = revision.stock;

  const runway: RunwayData = {
    setups: pkg.setups.map((s) => {
      const a = pkg.workholdingBySetup[s.id];
      return {
        id: s.id,
        name: s.name,
        sequence: s.sequence,
        machine: s.machine ? `${s.machine.manufacturer} ${s.machine.model}` : null,
        workholding: s.workholding?.description ?? null,
        riskLevel: a?.level ?? null,
        riskLabel: a ? RISK_LABEL[a.level] : null,
        gripDepth: s.gripDepth,
        hasPositiveStop: s.hasPositiveStop || s.jaws.length > 0,
      };
    }),
    operations: runwayOperations,
    cycleMinutes: pkg.cycleMinutes,
    placeholderCount: runwayOperations.filter((o) => o.isPlaceholder).length,
    workholding: {
      worstLevel: worst?.level ?? null,
      worstLabel: worst ? RISK_LABEL[worst.level] : null,
      device: pkg.primaryWorkholding?.description ?? null,
      gripDepth: primarySetup?.gripDepth ?? null,
      hasPositiveStop: Boolean(primarySetup?.hasPositiveStop || (primarySetup?.jaws.length ?? 0) > 0),
      // holding-margin.ts carries a non-optional developmentAnalysis flag for
      // exactly this reason: the model has never been validated against a
      // pull-off test.
      developmentAnalysis: Boolean(worst?.holdingMargin),
    },
    inspection: {
      hasPlan: pkg.hasInspectionPlan,
      itemCount: inspectionPlan?.items.length ?? 0,
      resultCount: inspectionPlan?._count.results ?? 0,
      measurementCount: measurementRows.length,
      pendingResolutionCount: measurementRows.filter((m) => m.resolution === "PENDING").length,
      criticalFeatureCount: revision.features.filter((f) => f.critical).length,
    },
    material: {
      name: revision.intent.material.value,
      condition: revision.intent.materialCondition.value,
      stockForm: stock?.form ?? null,
      stockSize: stock ? `${fmt(stock.x, 3)} × ${fmt(stock.y, 3)} × ${fmt(stock.z, 3)} in` : null,
      stockCondition: stock?.condition ?? null,
    },
  };

  // The whole ordered queue travels to the runway, not just its head. The
  // instruction is what matters on arrival; the reasoning and the rest of the
  // queue matter the moment it is questioned, and principle 12 says a
  // consequential value has to be openable rather than hover-only.
  const actions: NextActionInfo[] = nextActions(
    readiness,
    id,
    pkg.workholdingBySetup[pkg.setups[0]?.id ?? ""] ?? null,
  ).map((a) => ({
    action: a.action,
    reason: a.reason,
    href: a.href,
    linkLabel: a.linkLabel,
    severity: a.severity,
  }));

  // Blue means active state. The NC route is promoted to the primary treatment
  // only when the gate list that governs export has nothing blocking —
  // `blockingCount` is the readiness engine's own figure, not a second copy of
  // it. The NC page then runs its own pre-flight on top and still refuses to
  // export until that passes; nothing here weakens that.
  const ncExportUnblocked = readiness.blockingCount === 0;

  /* ---------------- Data panels, behind the feature panel's Data tab ---------------- */

  const panels: Record<string, React.ReactNode> = {
    part: (
      <div className="space-y-4">
        {critical && (
          <Notice tone="risk" title="Critical application">
            This component is load bearing or safety critical. CANVAS may assist with manufacturing planning but does
            not certify component safety. Professional engineering validation, material certification, process
            controls and inspection may be required.
          </Notice>
        )}

        {gaps.length > 0 && (
          <Notice tone="review" title="Engineering input required">
            <ul className="mt-1 space-y-0.5">
              {gaps.map((g) => (
                <li key={g}>— {g}</li>
              ))}
            </ul>
            <Link href={`/parts/${id}/responsibility`} className="mt-2 inline-block text-precision hover:underline">
              Answer the responsibility interview
            </Link>
          </Notice>
        )}

        <div>
          <p className="instrument-label mb-1.5">Part intent model</p>
          <ValueRow label="Name" field={revision.intent.partName} />
          <ValueRow label="Material" field={revision.intent.material} />
          <ValueRow label="Condition" field={revision.intent.materialCondition} />
          <ValueRow
            label="Envelope"
            field={revision.intent.finishedEnvelope}
            render={(v) => {
              const e = v as { x: number; y: number; z: number };
              return `${fmt(e.x, 3)} × ${fmt(e.y, 3)} × ${fmt(e.z, 3)}`;
            }}
          />
          <ValueRow label="Quantity" field={revision.intent.quantity} />
          <ValueRow label="General tol" field={revision.intent.generalTolerance} render={(v) => `±${Number(v).toFixed(4)}`} />
          <ValueRow label="Surface finish" field={revision.intent.surfaceFinish} />
          <ValueRow label="Production intent" field={revision.intent.productionIntent} />
          <ValueRow label="Load bearing" field={revision.intent.loadBearing} render={(v) => (v ? "Yes" : "No")} />
          <ValueRow label="Safety critical" field={revision.intent.safetyCritical} render={(v) => (v ? "Yes" : "No")} />
          <ValueRow label="Failure consequence" field={revision.intent.failureConsequence} />
          <ValueRow label="Annual volume" field={revision.intent.annualVolume} />
        </div>

        {proposals.length > 0 && (
          <Notice tone="precision" title={`${proposals.length} AI proposal${proposals.length === 1 ? "" : "s"} pending`}>
            Feature suggestions from the intake are stored as proposals. They are not geometry until you accept them.
            <Link href={`/parts/${id}/proposals`} className="mt-2 block text-precision hover:underline">
              Review proposals
            </Link>
          </Notice>
        )}
      </div>
    ),

    stock: (
      <div className="space-y-3">
        {revision.stock ? (
          <>
            <DataRow label="Form" value={revision.stock.form} />
            <DataRow label="X" value={`${fmt(revision.stock.x, 3)}″`} />
            <DataRow label="Y" value={`${fmt(revision.stock.y, 3)}″`} />
            <DataRow label="Z" value={`${fmt(revision.stock.z, 3)}″`} />
            <DataRow label="Material" value={revision.stock.material} />
            <DataRow label="Condition" value={revision.stock.condition ?? "—"} />
            <DataRow
              label="Volume"
              value={`${(revision.stock.x * revision.stock.y * revision.stock.z).toFixed(2)} in³`}
            />
          </>
        ) : (
          <p className="text-[12px] text-muted">Stock is not defined for this revision.</p>
        )}
      </div>
    ),

    setups: (
      <div className="space-y-4">
        {pkg.setups.length === 0 ? (
          <p className="text-[12px] text-muted">No setups defined.</p>
        ) : (
          pkg.setups.map((s) => {
            const a = pkg.workholdingBySetup[s.id];
            const tone: Tone =
              a?.level === "SAFE" || a?.level === "LIKELY_SAFE" ? "pass" : a?.level === "REVIEW" ? "review" : a?.level === "HIGH_RISK" ? "risk" : "unknown";
            const setupOps = s.operations;
            const setupMinutes = pkg.toolpaths
              .filter((tp) => setupOps.some((o) => o.id === tp.operationId))
              .reduce((sum, tp) => sum + tp.cycleTimeMinutes, 0);
            return (
              <div key={s.id} className="border border-line">
                <div className="flex items-center justify-between border-b border-line px-2.5 py-1.5">
                  <span className="font-mono text-[11px] text-platinum">{s.name}</span>
                  <StatusChip tone={tone}>{a ? RISK_LABEL[a.level] : "—"}</StatusChip>
                </div>
                <div className="px-2.5 py-2">
                  <DataRow label="Orientation" value={s.orientation} />
                  <DataRow label="Work offset" value={s.workOffset} />
                  <DataRow label="Machine" value={s.machine ? `${s.machine.manufacturer} ${s.machine.model}` : "—"} />
                  <DataRow label="Workholding" value={s.workholding?.description ?? "Not defined"} />
                  <DataRow label="Grip depth" value={s.gripDepth != null ? `${fmt(s.gripDepth, 3)}″` : "—"} tone={tone === "risk" ? "risk" : undefined} />
                  <DataRow label="Positive stop" value={s.hasPositiveStop || s.jaws.length > 0 ? "Yes" : "None"} />
                  <DataRow label="Operations" value={String(setupOps.length)} />
                  <DataRow label="Cycle" value={setupMinutes > 0 ? `${setupMinutes.toFixed(2)} min` : "—"} />
                  {s.datumNote && <p className="mt-2 text-[11px] leading-relaxed text-muted">{s.datumNote}</p>}
                </div>
              </div>
            );
          })
        )}
        <LinkButton href={`/parts/${id}/setups`} size="sm">
          Setup planning
        </LinkButton>
      </div>
    ),

    workholding: (
      <div className="space-y-4">
        {pkg.setups.map((s) => {
          const a = pkg.workholdingBySetup[s.id];
          if (!a) return null;
          return (
            <div key={s.id}>
              <p className="instrument-label mb-1.5">{s.name}</p>
              {a.missingInputs.length > 0 && (
                <div className="mb-2 border border-unknown/30 px-2 py-1.5">
                  <p className="instrument-label text-unknown">Missing inputs</p>
                  {a.missingInputs.map((m) => (
                    <p key={m} className="text-[11.5px] text-muted">
                      — {m}
                    </p>
                  ))}
                </div>
              )}
              {a.estimatedCuttingForce != null && (
                <DataRow label="Est. cutting load" value={`${a.estimatedCuttingForce} lbf`} />
              )}
              <div className="mt-2 space-y-2">
                {a.factors.map((f) => {
                  const tone: Tone =
                    f.level === "SAFE" || f.level === "LIKELY_SAFE" ? "pass" : f.level === "REVIEW" ? "review" : f.level === "HIGH_RISK" ? "risk" : "unknown";
                  return (
                    <div key={f.id} className="border border-line px-2.5 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="flex items-center gap-1.5">
                          <Dot tone={tone} />
                          <span className="font-mono text-[11px] text-platinum">{f.label}</span>
                        </span>
                        <StatusChip tone={tone}>{RISK_LABEL[f.level]}</StatusChip>
                      </div>
                      <p className="tech-label mt-1">{f.observed}</p>
                      {f.expected && <p className="tech-label text-precision/80">Expected {f.expected}</p>}
                      <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">{f.reason}</p>
                      {f.suggestions.length > 0 && (
                        <ul className="mt-1.5 space-y-0.5">
                          {f.suggestions.map((sg) => (
                            <li key={sg} className="text-[11.5px] text-platinum-dim">
                              — {sg}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
        <LinkButton href={`/parts/${id}/soft-jaws`} size="sm" variant="primary">
          Generate soft jaws
        </LinkButton>
      </div>
    ),

    tools: (
      <div className="space-y-2">
        {pkg.assignedTools.length === 0 ? (
          <p className="text-[12px] text-muted">No tools assigned to this part.</p>
        ) : (
          pkg.assignedTools.map((t) => (
            <div key={t.id} className="border border-line px-2.5 py-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[11px] text-platinum">T{t.toolNumber}</span>
                <span className="instrument-label">{t.toolClass.replace(/_/g, " ").toLowerCase()}</span>
              </div>
              <p className="mt-0.5 text-[12px] text-platinum-dim">{t.description}</p>
              <p className="tech-label mt-1">
                ⌀{fmt(t.diameter, 4)} · {t.flutes} fl · {t.stickout.toFixed(2)}″ stickout · {t.maxRPM} rpm max
              </p>
            </div>
          ))
        )}
      </div>
    ),

    operations: (
      <div className="space-y-2">
        {pkg.toolpathErrors.length > 0 && (
          <Notice tone="risk" title="Toolpath cannot be generated">
            {pkg.toolpathErrors.map((e) => (
              <div key={e.operationId} className="mt-1.5">
                <p className="text-platinum-dim">{e.reason}</p>
                <ul className="mt-1">
                  {e.recommendations.map((r) => (
                    <li key={r}>— {r}</li>
                  ))}
                </ul>
              </div>
            ))}
          </Notice>
        )}
        {pkg.setups.flatMap((s) =>
          s.operations.map((o) => {
            const tp = pkg.toolpaths.find((t) => t.operationId === o.id);
            return (
              <div key={o.id} className="border border-line px-2.5 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-[11px] text-platinum">{o.label}</span>
                  {tp?.isPlaceholder ? <DevLabel>No engine</DevLabel> : null}
                </div>
                <p className="tech-label mt-0.5">
                  {o.type} · T{o.tool?.toolNumber ?? "—"} · {o.feature?.label ?? "no feature"}
                </p>
                {tp && !tp.isPlaceholder && (
                  <p className="tech-label mt-1">
                    {tp.parameters.rpm} rpm · {tp.parameters.feed} ipm · {tp.moves.length} moves ·{" "}
                    {tp.cycleTimeMinutes.toFixed(2)} min
                  </p>
                )}
                {tp?.warnings.map((w) => (
                  <p key={w} className="mt-1 text-[11px] leading-relaxed text-review">
                    {w}
                  </p>
                ))}
              </div>
            );
          }),
        )}
        <DataRow label="Total cycle" value={`${pkg.cycleMinutes.toFixed(2)} min`} />
      </div>
    ),

    inspection: (
      <div className="space-y-3">
        {pkg.hasInspectionPlan ? (
          <LinkButton href={`/parts/${id}/inspection`} size="sm">
            Open inspection plan
          </LinkButton>
        ) : (
          <p className="text-[12px] leading-relaxed text-muted">
            No inspection plan exists for this revision. Critical dimensions without a measurement method are
            dimensions nobody is going to check.
          </p>
        )}
        <div>
          <p className="instrument-label mb-1.5">Critical features</p>
          {revision.features.filter((f) => f.critical).length === 0 ? (
            <p className="text-[12px] text-muted">None flagged critical.</p>
          ) : (
            revision.features
              .filter((f) => f.critical)
              .map((f) => (
                <div key={f.id} className="border-b border-line/60 py-1.5">
                  <p className="font-mono text-[11.5px] text-platinum">{f.label}</p>
                  <p className="tech-label">
                    {fmtTol(f.tolerance)} · {f.inspectionMethod ?? "no method assigned"}
                  </p>
                </div>
              ))
          )}
        </div>
      </div>
    ),

    cost: (
      <div className="space-y-3">
        <DataRow label={`Unit cost @ ${pkg.cost.quantity}`} value={money(pkg.cost.unitCost)} />
        <DataRow label="Unit price" value={money(pkg.cost.unitPrice)} />
        <DataRow label="Lot price" value={money(pkg.cost.lotPrice)} />
        <div className="mt-3">
          <p className="instrument-label mb-1.5">Quantity breaks</p>
          {pkg.breaks.map((b) => (
            <DataRow key={b.quantity} label={String(b.quantity)} value={money(b.unitPrice)} />
          ))}
        </div>
        <LinkButton href={`/parts/${id}/cost`} size="sm">
          Cost & make vs buy
        </LinkButton>
      </div>
    ),

    history: (
      <div className="space-y-2">
        {audits.length === 0 ? (
          <p className="text-[12px] text-muted">No changes recorded.</p>
        ) : (
          audits.map((a) => (
            <div key={a.id} className="border-b border-line/60 py-1.5">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-[11px] text-platinum">{a.action}</span>
                <StatusChip tone={a.actorType === "AI" ? "review" : "neutral"}>{a.actorType}</StatusChip>
              </div>
              <p className="tech-label">
                {a.entityType}
                {a.field ? ` · ${a.field}` : ""} · {a.createdAt.toISOString().slice(0, 16).replace("T", " ")}
              </p>
              {a.reason && <p className="text-[11px] text-muted">{a.reason}</p>}
            </div>
          ))
        )}
      </div>
    ),
  };

  return (
    <>
      {/* The job command bar. Every value in it is stored; where one is not
          stored the bar says what is missing rather than filling the slot. */}
      <TopBar
        title={revision.partName}
        chips={
          <>
            <StatusChip tone="neutral">Rev {revision.revision}</StatusChip>
            <StatusChip tone={revision.status === "RELEASED" ? "pass" : "unknown"}>{revision.status}</StatusChip>
            {critical && <StatusChip tone="risk">Critical application</StatusChip>}
          </>
        }
        meta={
          <>
            <BarMeta label="Material">
              <span className="flex items-center gap-1.5">
                {revision.intent.material.value ?? "not defined"}
                {revision.intent.materialCondition.value ? ` · ${revision.intent.materialCondition.value}` : ""}
                <ProvenanceBadge
                  source={revision.intent.material.source}
                  confidence={revision.intent.material.confidence}
                  confirmed={revision.intent.material.confirmedByUser}
                  compact
                />
              </span>
            </BarMeta>
            <BarMeta label="Stock">
              {/* With the unit. Every other dimensional readout in the app
                  carries one, and this app's own demo feature is a 40 mm bore
                  in an inch part — an unlabelled triple at the top of the
                  screen is an avoidable ambiguity. */}
              {stock ? `${fmt(stock.x, 3)} × ${fmt(stock.y, 3)} × ${fmt(stock.z, 3)} in` : "not defined"}
            </BarMeta>
            <BarMeta label="Machine">
              {pkg.primaryMachine
                ? `${pkg.primaryMachine.manufacturer} ${pkg.primaryMachine.model}`
                : "not assigned"}
            </BarMeta>
            {/* NC is gated. Until a program exists there is no number, and a
                header that invents one is a header that gets the wrong program
                run. */}
            <BarMeta label="Program">{ncProgram?.programNumber ?? "not generated"}</BarMeta>
          </>
        }
        status={<PartStatusSummary readiness={readiness} />}
      >
        <Link href="/parts" className="instrument-label hover:text-platinum">
          Parts
        </Link>
        <span className="text-muted">/</span>
        <span className="instrument-label">{revision.partNumber ?? revision.partName}</span>
      </TopBar>

      {intake === "1" && (
        <div className="border-b border-line bg-raised px-5 py-2.5">
          <p className="text-[12px] leading-relaxed text-platinum-dim">
            Part created from your description. Every extracted field is marked as an AI suggestion and unconfirmed —
            confirm each one before CANVAS will plan manufacturing against it.
          </p>
        </div>
      )}

      {/* One chrome row. Gates on demand, and the routes out of here.

          The two halves each take a full line below `xl`. They used to share
          one: the gate strip was the only flexible item between two shrink-0
          siblings, so it absorbed the whole squeeze and measured zero width at
          1024 and 768 — four unresolved gates silently dropped — while the
          "All gates" toggle painted over the action group beside it. The
          action group is itself wider than a phone viewport, so it scrolls
          rather than holding its intrinsic width off the edge of a clipped
          shell.

          The bottom rule is `--canvas-border-strong`, matching the centre/right
          and centre/footer seams: this is the work canvas's top edge and the
          same kind of edge gets the same rule. The ground is the footer grey,
          so the three light chrome regions read as one family. */}
      <div
        className="flex flex-col gap-y-2 bg-footer px-4 py-1.5 xl:flex-row xl:items-center xl:gap-x-5"
        style={{ borderBottom: "1px solid var(--canvas-border-strong)" }}
      >
        {/* Fourteen labels across the top of every screen is noise the eye
            learns to skip, which is the opposite of what a readiness system is
            for. Dots only, no aggregate, no score. */}
        <details className="group min-w-0 xl:flex-1">
          <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1">
            <span className="instrument-label shrink-0">Readiness</span>
            {/* Wraps, never scrolls. A horizontal scroller with no scrollbar
                cut "OPERATOR APPROVAL" mid-word against the toggle beside it,
                which is how an unresolved gate silently disappears. */}
            <span className="flex min-w-[8rem] flex-1 basis-[16rem] flex-wrap items-center gap-x-2.5 gap-y-1">
              {readiness.gates
                .filter((g) => g.status !== "PASS" && g.status !== "NOT_ATTEMPTED")
                .slice(0, 4)
                .map((g) => (
                  <span key={g.id} className="flex shrink-0 items-center gap-1.5">
                    <Dot tone={g.status === "REVIEW" ? "review" : "risk"} />
                    <span className="instrument-label">{g.label}</span>
                  </span>
                ))}
              {readiness.gates.every((g) => g.status === "PASS" || g.status === "NOT_ATTEMPTED") && (
                <span className="instrument-label text-pass">All gates pass</span>
              )}
            </span>
            <span className="instrument-label shrink-0 text-precision-dim">
              <span className="group-open:hidden">All gates</span>
              <span className="hidden group-open:inline">Hide</span>
            </span>
          </summary>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-2.5">
            {readiness.gates.map((g) => {
              const tone: Tone =
                g.status === "PASS" ? "pass" : g.status === "REVIEW" ? "review" : g.status === "NOT_ATTEMPTED" ? "unknown" : "risk";
              return (
                <span key={g.id} className="flex shrink-0 items-center gap-1.5" title={g.detail}>
                  <Dot tone={tone} />
                  <span className="instrument-label">{g.label}</span>
                </span>
              );
            })}
          </div>
        </details>

        {/* Wraps at phone width. This group is 564px wide and used to be
            `shrink-0`, so on a 390px screen it ran 190px past the edge of a
            shell that clips: "Full readiness" was cut in half and NC output —
            the gated export route — was entirely unreachable. */}
        <div className="flex min-w-0 flex-wrap items-center gap-2 xl:shrink-0 xl:flex-nowrap">
          <LinkButton href={`/parts/${id}/review`} size="sm" variant="ghost" className="shrink-0">
            Run it past CANVAS
          </LinkButton>
          <LinkButton href={`/parts/${id}/machinist`} size="sm" variant="ghost" className="shrink-0">
            Machinist
          </LinkButton>
          <LinkButton href={`/parts/${id}/tooling`} size="sm" variant="ghost" className="shrink-0">
            Tooling
          </LinkButton>
          <LinkButton href={`/parts/${id}/readiness`} size="sm" variant="ghost" className="shrink-0">
            Full readiness
          </LinkButton>
          {/* NC output is neutral while the part cannot use it. Blue in this
              system means active state, and framing a gated, development-grade
              export route as the primary action — beside a status module that
              reads NOT READY with blocking gates — is blue as decoration.
              When the gates that block export pass, it is promoted, and then
              the colour is reporting state. */}
          <LinkButton
            href={`/parts/${id}/nc`}
            size="sm"
            variant={ncExportUnblocked ? "primary" : "ghost"}
            className="shrink-0"
          >
            NC output
          </LinkButton>
          <DevLabel>Dev</DevLabel>
        </div>
      </div>

      <Workspace
        partId={id}
        partName={revision.partName}
        stock={revision.stock}
        features={revision.features}
        moves={moves}
        fixture={fixture}
        copilotContext={{}}
        panels={panels}
        featureDetails={featureDetails}
        datums={datums}
        runway={runway}
        nextActions={actions}
        hasInspectionPlan={pkg.hasInspectionPlan}
        measurementSessionId={latestSession?.id ?? null}
        simOps={simOps}
        recordSimulation={recordSimulation}
        simulationRecorded={pkg.simulationRun}
      />

      {/* Publishes this page's own values to the shell drawer. Renders
          nothing. Both values are already on this screen. */}
      <PartShellInfoBridge
        partId={id}
        name={revision.partName}
        number={revision.partNumber ?? null}
        revision={revision.revision ?? null}
        nextAction={
          actions[0]
            ? {
                action: actions[0].action,
                href: actions[0].href,
                linkLabel: actions[0].linkLabel,
                severity: actions[0].severity,
              }
            : null
        }
      />
    </>
  );
}

const riskRank = (level: string) => ({ SAFE: 0, LIKELY_SAFE: 1, REVIEW: 2, HIGH_RISK: 3, UNKNOWN: 4 })[level] ?? 0;

import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { buildPackage } from "@/lib/package";
import { fmt, fmtTol } from "@/lib/domain/features";
import { isCriticalApplication, missingEngineeringInput } from "@/lib/domain/part-intent";
import { money } from "@/lib/engines/cost";
import { RISK_LABEL } from "@/lib/engines/workholding";
import { GATE_LABEL } from "@/lib/engines/readiness";
import { TopBar } from "@/components/nav";
import { Workspace } from "@/components/workspace/workspace";
import { DataRow, DevLabel, Dot, LinkButton, Notice, StatusChip, ValueRow, type Tone } from "@/components/ui";

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

  const [proposals, audits] = await Promise.all([
    db.aIRecommendation.findMany({
      where: { partRevisionId: revision.revisionId, status: "PROPOSED" },
      orderBy: { createdAt: "desc" },
    }),
    db.auditLog.findMany({
      where: { entityType: { in: ["Part", "PartRevision", "Feature", "Setup"] }, organizationId: user.organizationId },
      orderBy: { createdAt: "desc" },
      take: 20,
    }),
  ]);

  const readinessTone: Tone =
    readiness.overall === "READY_TO_RUN" ? "pass" : readiness.overall === "REVIEW_REQUIRED" ? "review" : "risk";

  const moves = pkg.toolpaths.flatMap((tp) => tp.moves);

  const primarySetup = pkg.setups[0];
  const fixture = pkg.primaryWorkholding
    ? {
        jawWidth: pkg.primaryWorkholding.jawWidth,
        jawHeight: pkg.primaryWorkholding.jawHeight,
        gripDepth: primarySetup?.gripDepth ?? null,
      }
    : null;

  /* ---------------- Left navigator panels ---------------- */

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
          <p className="tech-label mb-1.5">Part intent model</p>
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
                  <DataRow label="Operations" value={String(setupOps.length)} />
                  <DataRow label="Cycle" value={setupMinutes > 0 ? `${setupMinutes.toFixed(2)} min` : "—"} />
                  {s.datumNote && <p className="tech-label mt-2 leading-relaxed">{s.datumNote}</p>}
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
              <p className="tech-label mb-1.5">{s.name}</p>
              {a.missingInputs.length > 0 && (
                <div className="mb-2 border border-unknown/30 px-2 py-1.5">
                  <p className="tech-label text-unknown">Missing inputs</p>
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
                <span className="tech-label">{t.toolClass.replace(/_/g, " ").toLowerCase()}</span>
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
          <p className="tech-label mb-1.5">Critical features</p>
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
          <p className="tech-label mb-1.5">Quantity breaks</p>
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
      <TopBar>
        <Link href="/parts" className="tech-label hover:text-platinum">
          Parts
        </Link>
        <span className="text-muted">/</span>
        <span className="text-[13px] text-white">{revision.partName}</span>
        <StatusChip tone="neutral">Rev {revision.revision}</StatusChip>
        <StatusChip tone={readinessTone}>{readiness.overall.replace(/_/g, " ")}</StatusChip>
        {critical && <StatusChip tone="risk">Critical application</StatusChip>}
      </TopBar>

      {intake === "1" && (
        <div className="border-b border-line bg-raised px-5 py-2.5">
          <p className="text-[12px] leading-relaxed text-platinum-dim">
            Part created from your description. Every extracted field is marked as an AI suggestion and unconfirmed —
            confirm each one before CANVAS will plan manufacturing against it.
          </p>
        </div>
      )}

      <div className="flex items-center gap-4 border-b border-line bg-surface px-5 py-2">
        <span className="tech-label">Readiness</span>
        <div className="flex flex-wrap items-center gap-3">
          {readiness.gates.map((g) => {
            const tone: Tone =
              g.status === "PASS" ? "pass" : g.status === "REVIEW" ? "review" : g.status === "NOT_ATTEMPTED" ? "unknown" : "risk";
            return (
              <span key={g.id} className="group relative flex items-center gap-1.5" title={g.detail}>
                <Dot tone={tone} />
                <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted group-hover:text-platinum">
                  {g.label}
                </span>
              </span>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <LinkButton href={`/parts/${id}/readiness`} size="sm" variant="ghost">
            Full readiness
          </LinkButton>
          <LinkButton href={`/parts/${id}/nc`} size="sm" variant="primary">
            NC output
          </LinkButton>
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
        readinessTone={readinessTone}
        readinessLabel={GATE_LABEL.PASS}
      />
    </>
  );
}

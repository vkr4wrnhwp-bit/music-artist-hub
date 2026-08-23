import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { TopBar } from "@/components/nav";
import { TurnProfileView } from "@/components/turn/profile-view";
import { LatheSimView } from "@/components/turn/lathe-3d";
import { TurnViews } from "@/components/turn/turn-views";
import { TurnAnalysisNarrative } from "@/components/turn/analysis-narrative";
import { CinematicTurnButton } from "@/components/turn/cinematic-turn";
import { NcExportPanel } from "@/components/nc/export-panel";
import { mintTurnExport, recordTurnExport } from "./nc/actions";
import { GuideCard } from "@/components/guide/guide-card";
import type { GuideContext } from "@/lib/guide/engine";
import { Button, DevLabel, Dot, LimitsDisclosure, Notice, Panel, StatusChip, inputClass, type Tone } from "@/components/ui";
import type { RotationalProfile } from "@/lib/manufacturing/turn/geometry";
import { buildTurnPackage } from "@/lib/manufacturing/turn/package";
import { bestNominalSuggestion } from "@/lib/engines/nominal";

/**
 * THE TURNING WORKSPACE — PROFILE view, plan, hold intelligence, gates.
 *
 * Everything on this page is deterministic arithmetic over the rotational
 * model: toolpaths from the turn engines, verdicts from the turn analyses,
 * readiness from worst-gate aggregation. The 3D lathe view is DEVELOPMENT
 * and is labelled as absent rather than mocked. The NC preview comes from
 * the development post and is withheld while gates fail — the same law as
 * the mill.
 */

export default async function LathePartPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ op?: string }>;
}) {
  const { id } = await props.params;
  const { op: opParam } = await props.searchParams;
  const user = await requireUser();

  /*
   * ONE ASSEMBLY. This page used to rebuild the toolpaths, hold analyses,
   * inspection check and readiness itself, from its own copy of the same
   * arithmetic — and the copies had already drifted: the workspace handed
   * the material gate a literal `true` (a PASS/FAIL gate that could not
   * fail) and assessed boring-bar reach against a fabricated 0.625" x 3"
   * steel bar when the crib held none. The export mint, meanwhile, gated on
   * buildTurnPackage. A workspace showing a different readiness than the
   * gate is exactly what "the rendered button is not the gate" means.
   */
  const pkg = await buildTurnPackage(user.organizationId, id);
  if (!pkg) notFound();
  const { part, rot, profile, plan, results, totalMinutes, lathe, holding, tools, readiness, blocking, program } = pkg;
  const { grip, stickout, partOff } = pkg.analyses;

  // A reverse-engineering part with no readings yet has no geometry to show —
  // the bench flow is the workspace until the first step is recorded.
  if (profile.segments.length === 0) redirect(`/lathe/${id}/reverse`);

  const selectedOpNum = opParam ? Number(opParam) : plan[0]?.operationNumber ?? null;
  const selected = results.find((r) => r.op.operationNumber === selectedOpNum) ?? null;
  const selSeg = selected?.op.targetSegmentId
    ? profile.segments.find((s) => s.id === selected.op.targetSegmentId) ?? null
    : null;

  /* ---------------- Nominal reasoning (never auto-applied) ------------ */
  const journal = profile.segments.find((s) => s.functionalRole === "BEARING_JOURNAL");
  const nominal =
    journal && !journal.confirmedByUser
      ? bestNominalSuggestion({ measured: journal.diameterStart, uncertainty: 0.0002, context: "SHAFT" })
      : null;

  /* ---------------- Actions ---------------- */

  async function acceptNominal() {
    "use server";
    const u = await requireWrite();
    const fresh = await db.rotationalPart.findFirst({ where: { id: rot!.id, organizationId: u.organizationId } });
    if (!fresh) notFound();
    const prof = JSON.parse(fresh.profileJson) as RotationalProfile;
    const j = prof.segments.find((s) => s.functionalRole === "BEARING_JOURNAL");
    if (!j || j.confirmedByUser) redirect(`/lathe/${id}`);
    const sug = bestNominalSuggestion({ measured: j.diameterStart, uncertainty: 0.0002, context: "SHAFT" });
    if (!sug) redirect(`/lathe/${id}`);
    const before = j.diameterStart;
    j.diameterStart = sug.nominalInches;
    j.diameterEnd = sug.nominalInches;
    j.source = "USER";
    j.confirmedByUser = true;
    await db.rotationalPart.update({ where: { id: fresh.id }, data: { profileJson: JSON.stringify(prof) } });
    await audit({
      organizationId: u.organizationId,
      userId: u.id,
      entityType: "RotationalPart",
      entityId: fresh.id,
      action: "UPDATE",
      actorType: "HUMAN",
      field: "bearing-journal nominal",
      oldValue: `${before.toFixed(4)} in MEASURED`,
      newValue: `${sug.nominalInches.toFixed(5)} in (${sug.label}) USER-CONFIRMED`,
      reason: "Nominal accepted by a human — AI suggestion alone never changes geometry.",
    });
    revalidatePath(`/lathe/${id}`);
  }

  async function keepMeasured() {
    "use server";
    const u = await requireWrite();
    const fresh = await db.rotationalPart.findFirst({ where: { id: rot!.id, organizationId: u.organizationId } });
    if (!fresh) notFound();
    const prof = JSON.parse(fresh.profileJson) as RotationalProfile;
    const j = prof.segments.find((s) => s.functionalRole === "BEARING_JOURNAL");
    if (!j) redirect(`/lathe/${id}`);
    j.confirmedByUser = true; // measured value, human-confirmed as intentional
    await db.rotationalPart.update({ where: { id: fresh.id }, data: { profileJson: JSON.stringify(prof) } });
    await audit({
      organizationId: u.organizationId, userId: u.id, entityType: "RotationalPart", entityId: fresh.id,
      action: "UPDATE", actorType: "HUMAN", field: "bearing-journal nominal",
      newValue: `${j.diameterStart.toFixed(4)} in kept as measured`,
      reason: "Measured value kept deliberately over the metric nominal suggestion.",
    });
    revalidatePath(`/lathe/${id}`);
  }

  async function toggleTailstock() {
    "use server";
    const u = await requireWrite();
    const fresh = await db.rotationalPart.findFirst({ where: { id: rot!.id, organizationId: u.organizationId } });
    if (!fresh) notFound();
    await db.rotationalPart.update({ where: { id: fresh.id }, data: { tailstockActive: !fresh.tailstockActive } });
    await audit({
      organizationId: u.organizationId, userId: u.id, entityType: "RotationalPart", entityId: fresh.id,
      action: "UPDATE", actorType: "HUMAN", field: "tailstockActive",
      oldValue: String(fresh.tailstockActive), newValue: String(!fresh.tailstockActive),
      reason: "Tailstock toggled on the turning workspace.",
    });
    revalidatePath(`/lathe/${id}`);
  }

  async function recordClampForce(formData: FormData) {
    "use server";
    const u = await requireWrite();
    const v = Number(String(formData.get("clampForce") ?? "").trim());
    if (!Number.isFinite(v) || v <= 0) redirect(`/lathe/${id}`);
    const fresh = await db.rotationalPart.findFirst({ where: { id: rot!.id, organizationId: u.organizationId } });
    if (!fresh) notFound();
    await db.rotationalPart.update({ where: { id: fresh.id }, data: { clampForceLbf: v } });
    await audit({
      organizationId: u.organizationId, userId: u.id, entityType: "RotationalPart", entityId: fresh.id,
      action: "UPDATE", actorType: "HUMAN", field: "clampForceLbf", newValue: `${v} lbf`,
      reason: "Clamp force recorded from the machine's hydraulic setting.",
    });
    revalidatePath(`/lathe/${id}`);
  }

  const tone = (v: string): Tone => (v === "PASS" ? "pass" : v === "REVIEW" ? "review" : v === "UNKNOWN" ? "unknown" : "risk");

  // Cinematic input: real operations, real cycle proportions, turning voice.
  const partMaterial = pkg.materialFromIntent;
  const cinematicInput = {
    partName: part.name,
    partNumber: part.partNumber,
    material: partMaterial,
    process: "TURN" as const,
    stock: null,
    barStock: { diameter: profile.stockDiameter, length: profile.stockLength },
    setupName: "Chuck setup",
    workholding: holding?.description ?? null,
    hasSoftJaws: holding?.type === "SOFT_JAWS",
    readiness: readiness.overall,
    operations: plan.map((o) => ({
      id: String(o.operationNumber),
      label: o.label,
      type: o.type,
      toolDescription: tools.find((t) => t.station === o.toolStation)?.description ?? null,
      cycleMinutes: (() => {
        const r = results.find((x) => x.op.operationNumber === o.operationNumber);
        return r?.result.ok ? r.result.toolpath.estimatedMinutes : null;
      })(),
    })),
  };

  // Guide snapshot — real turning state mapped into the shared context, so
  // TURN_A_SHAFT steps complete from the truth, never a checklist copy.
  const guideCtx: GuideContext = {
    partId: id,
    hasStock: profile.stockDiameter > 0 && profile.stockLength > 0,
    hasMachine: Boolean(lathe),
    hasMaterial: partMaterial !== null,
    featureCount: profile.segments.length,
    pendingProposals: 0,
    setupCount: holding ? 1 : 0,
    workholdingAssessed: grip.verdict === "PASS" || grip.verdict === "REVIEW",
    toolpathCount: results.filter((r) => r.result.ok).length,
    simulationRecorded: false,
    approvalExists: rot.humanApproved,
    ncProgramExists: program.refusals.length === 0 && program.code.trim().length > 0,
    blockingGates: blocking.map((g) => ({ id: g.id, label: g.label, detail: g.detail })),
    readinessHref: `/lathe/${id}`,
    nextAction: null,
    training: false,
  };

  return (
    <>
      <TopBar>
        <Link href="/lathe" className="tech-label hover:text-platinum">Turning</Link>
        <span className="text-muted">/</span>
        <span className="tech-label">{part.name}</span>
        <DevLabel>TURN_2_AXIS</DevLabel>
        <StatusChip tone={readiness.overall === "READY_TO_RUN" ? "pass" : readiness.overall === "REVIEW_REQUIRED" ? "review" : "risk"}>
          {readiness.overall.replace(/_/g, " ")}
        </StatusChip>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-6xl space-y-5">
          {blocking.length > 0 && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-risk/40 bg-risk/10 px-3 py-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-risk">
                {blocking.length} blocking — action required
              </span>
              <span className="min-w-0 flex-1 truncate text-[11.5px] text-platinum-dim">{blocking[0].detail}</span>
            </div>
          )}

          {/* ---------------- The part — PROFILE / 3D / BOTH ---------------- */}
          <Panel
            title="The part"
            meta={<DevLabel>3D is a kinematic replay, not a collision check</DevLabel>}
          >
            <TurnViews
              profile={
                <>
                  <TurnProfileView
                    profile={profile}
                    selectedSegmentId={selected?.op.targetSegmentId ?? null}
                    moves={selected?.result.ok ? selected.result.toolpath.moves : null}
                  />
                  {selected && !selected.result.ok && (
                    <p className="mt-2 text-[12px] text-risk">
                      Op {selected.op.operationNumber}: {selected.result.reason}
                    </p>
                  )}
                  {/*
                    * The toolpath's own narrative, where the operation is
                    * examined. Every engine writes warnings (a chamfer's
                    * uncompensated nose radius, a tap's feed override) and
                    * assumptions (ESTIMATED, chord tolerance) for a human —
                    * and until this block, no page rendered either. The
                    * fourth instance of exactly that defect, this time on
                    * engines written the same week as the rule.
                    */}
                  {selected?.result.ok && selected.result.toolpath.warnings.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {selected.result.toolpath.warnings.map((w) => (
                        <li key={w} className="flex gap-2 text-[11.5px] leading-relaxed text-review">
                          <Dot tone="review" /> {w}
                        </li>
                      ))}
                    </ul>
                  )}
                  {selected?.result.ok && selected.result.toolpath.assumptions.length > 0 && (
                    <p className="mt-1.5 border-t border-line/60 pt-1.5 text-[10.5px] leading-relaxed text-muted">
                      <span className="tech-label mr-1.5">Assumed</span>
                      {selected.result.toolpath.assumptions.join(" · ")}
                    </p>
                  )}
                </>
              }
              sim={
                <LatheSimView
                  profile={profile}
                  ops={results.filter((r) => r.result.ok).map((r) => ({ op: r.op, moves: r.result.ok ? r.result.toolpath.moves : [] }))}
                />
              }
            />
          </Panel>

          {/* ---------------- Operation runway ---------------- */}
          {/* Compact strip is the default interaction: selecting an op updates
              the profile highlight, the toolpath overlay and the lens below.
              The full technical table survives behind VIEW TABLE. */}
          <div className="flex flex-wrap items-center gap-1.5">
            {results.map(({ op, result }) => {
              const isSel = selectedOpNum === op.operationNumber;
              const refused = !result.ok;
              return (
                <Link
                  key={op.operationNumber}
                  href={`/lathe/${id}?op=${op.operationNumber}`}
                  aria-current={isSel ? "true" : undefined}
                  className={`border px-2.5 py-1.5 font-mono text-[10.5px] uppercase tracking-[0.08em] transition-colors ${
                    isSel
                      ? "border-precision bg-precision/10 text-precision"
                      : refused
                        ? "border-review/60 text-review hover:border-review"
                        : "border-line-strong text-muted hover:border-line-strong hover:text-platinum"
                  }`}
                >
                  <span className="font-semibold">{op.operationNumber}</span> {op.type.replace(/_/g, " ")}
                </Link>
              );
            })}
            <span className="ml-auto flex items-center gap-3">
              <span className="font-mono text-[10.5px] text-muted tabular-nums">est {totalMinutes.toFixed(2)} min · ESTIMATED</span>
              <Link href={`/lathe/${id}/cost`} className="font-mono text-[10.5px] text-precision-dim hover:text-precision">Cost →</Link>
              <CinematicTurnButton input={cinematicInput} />
            </span>
          </div>

          {/* ---------------- Feature lens ---------------- */}
          {selSeg && (
            <Panel
              title={selSeg.label}
              meta={
                <span className="flex items-center gap-2">
                  {selSeg.critical && <StatusChip tone="precision">CRITICAL</StatusChip>}
                  <StatusChip tone={selSeg.confirmedByUser ? "pass" : "review"}>
                    {selSeg.confirmedByUser ? "CONFIRMED" : "REVIEW"}
                  </StatusChip>
                </span>
              }
            >
              <p className="font-mono text-[22px] text-platinum tabular-nums">⌀{selSeg.diameterEnd.toFixed(4)}″</p>
              <div className="mt-2 grid gap-x-8 gap-y-2 sm:grid-cols-3 lg:grid-cols-6">
                <p className="text-[11px] text-muted"><span className="tech-label block">Function</span>{selSeg.functionalRole.replace(/_/g, " ").toLowerCase()}</p>
                <p className="text-[11px] text-muted"><span className="tech-label block">Tolerance</span>{selSeg.tolerancePlus != null ? `+${selSeg.tolerancePlus.toFixed(4)} / −${(selSeg.toleranceMinus ?? 0).toFixed(4)}` : "not stated"}</p>
                <p className="text-[11px] text-muted"><span className="tech-label block">Surface</span>{selSeg.surfaceFinish != null ? `${selSeg.surfaceFinish} Ra` : "not stated"}</p>
                <p className="text-[11px] text-muted"><span className="tech-label block">Datum</span>Z {selSeg.zStart.toFixed(3)}–{selSeg.zEnd.toFixed(3)} from {profile.zZeroReference}</p>
                <p className="text-[11px] text-muted"><span className="tech-label block">Operation</span>{selected!.op.operationNumber} {selected!.op.label}</p>
                <p className="text-[11px] text-muted"><span className="tech-label block">Tool</span>T{selected!.op.toolStation}{(() => { const t = tools.find((x) => x.station === selected!.op.toolStation); return t ? ` — ${t.description}` : ""; })()}</p>
              </div>
              {selSeg.matingComponent && (
                <p className="mt-2 text-[11.5px] text-platinum-dim">Mates with: {selSeg.matingComponent}</p>
              )}
              <div className="mt-3 flex gap-4 border-t border-line/60 pt-2.5">
                <Link href={`/lathe/${id}/reverse`} className="text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:text-precision">Measure</Link>
                <Link href={`/lathe/${id}/nc-review`} className="text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:text-precision">Verify NC</Link>
                <Link href={`/lathe/${id}/cost`} className="text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:text-precision">Cost</Link>
              </div>
            </Panel>
          )}

          {/* ---------------- Nominal reasoning ---------------- */}
          {nominal && journal && (
            <Panel title="Possible nominal feature" meta={<StatusChip tone="review">AI inferred — awaiting a human</StatusChip>}>
              <div className="grid gap-x-8 gap-y-1 px-1 sm:grid-cols-4">
                <p className="text-[12px] text-muted">Measured<br /><span className="font-mono text-[15px] text-platinum">{journal.diameterStart.toFixed(4)} in</span></p>
                <p className="text-[12px] text-muted">Likely nominal<br /><span className="font-mono text-[15px] text-precision-dim">{nominal.label}</span></p>
                <p className="text-[12px] text-muted">Equivalent<br /><span className="font-mono text-[15px] text-platinum">{nominal.nominalInches.toFixed(5)} in</span></p>
                <p className="text-[12px] text-muted">Difference<br /><span className="font-mono text-[15px] text-platinum">{Math.abs(nominal.nominalInches - journal.diameterStart).toFixed(5)} in</span></p>
              </div>
              <p className="mt-2 text-[12px] leading-relaxed text-muted">
                {journal.label} measures like a metric bearing seat. Accepting rewrites the nominal as USER-CONFIRMED
                and audits the change; the suggestion alone changes nothing.
              </p>
              <div className="mt-2 flex gap-2">
                <form action={acceptNominal}><Button type="submit" variant="primary">Accept {nominal.label}</Button></form>
                <form action={keepMeasured}><Button type="submit">Keep measured</Button></form>
                <Link href={`/lathe/${id}?op=30`} className="self-center text-[11px] uppercase tracking-[0.1em] text-muted hover:text-platinum">Investigate</Link>
              </div>
            </Panel>
          )}

          {/* ---------------- Full technical table, on demand ---------------- */}
          <details className="border border-line bg-surface">
            <summary className="cursor-pointer px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted hover:text-platinum">
              View table — {plan.length} ops · est {totalMinutes.toFixed(2)} min (ESTIMATED — assumptions per op)
            </summary>
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-line">
                  {["Op", "Type", "Description", "Station", "Passes", "Est", ""].map((h, i) => (
                    <th key={i} className="instrument-label px-3 py-1.5 text-left font-normal">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.map(({ op, result }) => (
                  <tr key={op.operationNumber} className={`border-b border-line/60 ${selectedOpNum === op.operationNumber ? "bg-card shadow-[inset_2px_0_0_var(--c-blue)]" : ""}`}>
                    <td className="px-3 py-1.5 font-mono text-[12px] text-platinum-dim tabular-nums">{op.operationNumber}</td>
                    <td className="px-3 py-1.5 text-[9.5px] font-semibold uppercase tracking-[0.1em] text-muted">{op.type.replace(/_/g, " ")}</td>
                    <td className="px-3 py-1.5 text-[12px] text-platinum">{op.label}</td>
                    <td className="px-3 py-1.5 font-mono text-[11px] text-muted">T{op.toolStation}</td>
                    <td className="px-3 py-1.5 font-mono text-[11px] text-muted tabular-nums">{result.ok ? result.toolpath.passes : "—"}</td>
                    <td className="px-3 py-1.5 font-mono text-[11px] text-muted tabular-nums">{result.ok ? `${result.toolpath.estimatedMinutes.toFixed(2)} min` : <span className="text-risk">refused</span>}</td>
                    <td className="px-3 py-1.5"><Link href={`/lathe/${id}?op=${op.operationNumber}`} className="text-[10px] font-semibold uppercase tracking-[0.1em] text-precision-dim hover:text-precision">Show</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>

          {/* ---------------- Hold intelligence ---------------- */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Hold — chuck grip" meta={<span className="flex gap-2"><DevLabel>Dev</DevLabel><StatusChip tone={tone(grip.verdict)}>{grip.verdict}</StatusChip></span>}>
              <p className="text-[12.5px] leading-relaxed text-platinum-dim">{grip.detail}</p>
              <TurnAnalysisNarrative analysis={grip} />
              {rot.clampForceLbf === null && (
                <form action={recordClampForce} className="mt-2 flex items-end gap-2">
                  <label className="block">
                    <span className="tech-label mb-0.5 block">Clamp force (lbf)</span>
                    <input name="clampForce" inputMode="decimal" className={inputClass} />
                  </label>
                  <Button type="submit">Record</Button>
                </form>
              )}
              <p className="mt-2 border-t border-line/60 pt-2">
                <Link href={`/lathe/${id}/soft-jaws`} className="font-mono text-[11px] text-precision-dim hover:text-precision">
                  Soft jaws — drawer search + bore recipe →
                </Link>
              </p>
            </Panel>
            <Panel title="Hold — stickout" meta={<span className="flex gap-2"><DevLabel>Dev</DevLabel><StatusChip tone={tone(stickout.verdict)}>{stickout.verdict}</StatusChip></span>}>
              <p className="font-mono text-[15px] text-platinum tabular-nums">L/D {("ldRatio" in stickout ? stickout.ldRatio : 0).toFixed(1)}:1</p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-platinum-dim">{stickout.detail}</p>
              <TurnAnalysisNarrative analysis={stickout} />
              <form action={toggleTailstock} className="mt-2">
                <Button type="submit">{rot.tailstockActive ? "Retract tailstock" : "Engage tailstock"}</Button>
              </form>
              <p className="mt-1.5 text-[10.5px] text-muted">
                Tailstock needs the center-drilled tail end (op 50) actually cut before it supports anything real.
              </p>
            </Panel>
          </div>
          {partOff && (
            <Panel title="Part-off stability" meta={<span className="flex gap-2"><DevLabel>Dev</DevLabel><StatusChip tone={tone(partOff.verdict)}>{partOff.verdict}</StatusChip></span>}>
              <p className="text-[12.5px] leading-relaxed text-platinum-dim">{partOff.detail}</p>
              <TurnAnalysisNarrative analysis={partOff} />
            </Panel>
          )}

          {/* ---------------- Readiness ---------------- */}
          <Panel title="Turning readiness — worst gate decides" dense>
            <ul>
              {readiness.gates.map((g) => (
                <li key={g.id} className="flex items-start justify-between gap-4 border-b border-line/60 px-4 py-2 last:border-0">
                  <span className="flex items-start gap-2.5">
                    <span className="mt-1"><Dot tone={g.status === "PASS" ? "pass" : g.status === "REVIEW" ? "review" : g.status === "NOT_ATTEMPTED" ? "unknown" : "risk"} /></span>
                    <span>
                      <span className="block text-[12.5px] text-platinum">{g.label}</span>
                      <span className="block text-[11.5px] leading-relaxed text-muted">{g.detail}</span>
                    </span>
                  </span>
                  <StatusChip tone={g.status === "PASS" ? "pass" : g.status === "REVIEW" ? "review" : g.status === "NOT_ATTEMPTED" ? "unknown" : "risk"}>{g.status.replace(/_/g, " ")}</StatusChip>
                </li>
              ))}
            </ul>
          </Panel>

          {/* ---------------- NC preview ---------------- */}
          <Panel
            title="NC preview — development lathe post"
            meta={
              <span className="flex items-center gap-3">
                <Link href={`/lathe/${id}/nc-review`} className="text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:text-precision">
                  Run NC past CANVAS →
                </Link>
                <DevLabel>NOT FOR PRODUCTION USE</DevLabel>
              </span>
            }
          >
            <div className="mb-2">
              <LimitsDisclosure label="What this post is and is not">
                Generic Fanuc-style 2-axis: G18/G20/G99, T-station calls, G96/G97 with a mandatory G50 clamp when CSS
                is used, thread passes as G32-style moves. No canned cycles, no threading cycles, no nose-radius
                compensation. The preview below is withheld while blocking gates fail, and export uses the same
                single-use authorization mint as the mill — re-running the turning readiness gate server-side at both
                mint and record time. The exported file keeps this NOT FOR PRODUCTION USE header: an authorization is
                permission to take bytes out of CANVAS, not a certification of the post processor.
              </LimitsDisclosure>
            </div>
            {program.refusals.length > 0 ? (
              <Notice tone="risk" title="Post refused">
                {program.refusals.join(" ")}
              </Notice>
            ) : blocking.length > 0 ? (
              <p className="text-[12px] leading-relaxed text-platinum-dim">
                A program can be generated ({program.code.split("\n").length} lines), but {blocking.length} blocking
                gate{blocking.length === 1 ? "" : "s"} fail{blocking.length === 1 ? "s" : ""}, so the text is withheld
                until they pass. The failing items are listed above.
              </p>
            ) : (
              <>
                <pre className="max-h-[400px] overflow-auto bg-void px-4 py-3 font-mono text-[11.5px] leading-relaxed text-platinum-dim">{program.code}</pre>
                <div className="mt-3 border-t border-line/60 pt-3">
                  <NcExportPanel partId={id} mint={mintTurnExport} record={recordTurnExport} />
                </div>
              </>
            )}
          </Panel>
        </div>
      </main>
      <GuideCard ctx={guideCtx} flowId="TURN_A_SHAFT" />
    </>
  );
}

export const dynamic = "force-dynamic";

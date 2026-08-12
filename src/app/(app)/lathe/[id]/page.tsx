import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { TopBar } from "@/components/nav";
import { TurnProfileView } from "@/components/turn/profile-view";
import { LatheSimView } from "@/components/turn/lathe-3d";
import { CinematicTurnButton } from "@/components/turn/cinematic-turn";
import { Button, DevLabel, Dot, LimitsDisclosure, Notice, Panel, SectionHeading, StatusChip, inputClass, type Tone } from "@/components/ui";
import type { RotationalProfile } from "@/lib/manufacturing/turn/geometry";
import { generateTurnToolpath, type TurnOperation } from "@/lib/manufacturing/turn/operations";
import { assessChuckGrip, assessStickout, assessBoringBar, assessPartOff } from "@/lib/manufacturing/turn/analysis";
import { evaluateTurnReadiness } from "@/lib/manufacturing/turn/readiness";
import { emitLatheProgram } from "@/lib/manufacturing/turn/post";
import { bestNominalSuggestion } from "@/lib/engines/nominal";
import { parseThreadPitch } from "@/lib/engines/cam/engine";

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

  const part = await db.part.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!part) notFound();
  const revision = await db.partRevision.findFirst({ where: { partId: part.id }, orderBy: { createdAt: "desc" } });
  if (!revision) notFound();
  const rot = await db.rotationalPart.findFirst({
    where: { partRevisionId: revision.id, organizationId: user.organizationId },
  });
  if (!rot) notFound();

  const [lathe, holding, tools, metrology] = await Promise.all([
    rot.latheMachineId ? db.latheMachine.findFirst({ where: { id: rot.latheMachineId, organizationId: user.organizationId } }) : null,
    rot.workholdingId ? db.latheWorkholding.findFirst({ where: { id: rot.workholdingId, organizationId: user.organizationId } }) : null,
    db.turningTool.findMany({ where: { organizationId: user.organizationId } }),
    db.metrologyDevice.findMany({ where: { organizationId: user.organizationId } }),
  ]);

  const profile = JSON.parse(rot.profileJson) as RotationalProfile;
  // A reverse-engineering part with no readings yet has no geometry to show —
  // the bench flow is the workspace until the first step is recorded.
  if (profile.segments.length === 0) redirect(`/lathe/${id}/reverse`);
  const plan = JSON.parse(rot.planJson) as TurnOperation[];

  /* ---------------- Toolpaths, deterministic ---------------- */
  const toolWidthFor = (station: string) => tools.find((t) => t.station === station)?.grooveWidth ?? null;
  const results = plan.map((op) => {
    const seg = op.targetSegmentId ? profile.segments.find((s) => s.id === op.targetSegmentId) : null;
    const pitch = seg?.thread ? parseThreadPitch(seg.thread) : null;
    return { op, result: generateTurnToolpath(op, profile, toolWidthFor(op.toolStation), pitch) };
  });
  const totalMinutes = results.reduce((t, r) => t + (r.result.ok ? r.result.toolpath.estimatedMinutes : 0), 0);
  const selectedOpNum = opParam ? Number(opParam) : plan[0]?.operationNumber ?? null;
  const selected = results.find((r) => r.op.operationNumber === selectedOpNum) ?? null;

  /* ---------------- Analyses ---------------- */
  const gripDiameter = profile.stockDiameter;
  const grip = assessChuckGrip({
    gripDiameter,
    gripLength: rot.gripLength ?? 0,
    jawMaterial: (holding?.jawMaterial as "HARD" | "SOFT_MACHINED" | null) ?? null,
    serrated: holding?.serrated ?? null,
    clampForceLbf: rot.clampForceLbf,
    stickout: rot.stickout ?? 0,
    chuckMaxRpm: holding?.maxRPM ?? null,
    programmedMaxRpm: rot.maxRpmClamp,
  });
  const stickout = assessStickout({
    unsupportedLength: rot.stickout ?? 0,
    diameter: profile.stockDiameter,
    tailstock: rot.tailstockActive,
  });
  const boringOps = plan.filter((o) => o.type.startsWith("ID_BORE"));
  const boringBar = boringOps.length
    ? assessBoringBar({
        barDiameter: tools.find((t) => t.toolClass === "BORING_BAR")?.barDiameter ?? 0.625,
        stickout: tools.find((t) => t.toolClass === "BORING_BAR")?.stickout ?? 3,
        boreDepth: Math.max(...boringOps.map((o) => Math.abs(o.endZ - o.startZ))),
        barMaterial: "STEEL",
      })
    : null;
  const cutoff = plan.find((o) => o.type === "PART_OFF");
  const partOff = cutoff
    ? assessPartOff({
        cutoffZ: cutoff.startZ,
        cutoffDiameter: cutoff.startDiameter,
        distanceFromChuck: cutoff.startZ - (rot.gripLength ?? 0) + (rot.stickout ?? 0) - (profile.stockLength - (rot.gripLength ?? 0)),
        toolWidth: toolWidthFor(cutoff.toolStation),
        hasPartsCatcher: lathe?.hasPartsCatcher ?? false,
        hasSubSpindle: lathe?.hasSubSpindle ?? false,
        tailstockActive: rot.tailstockActive,
      })
    : null;

  /* ---------------- Inspection capability, simplest honest form ------- */
  // The critical journal is ±0.0005: a micrometer at ≤0.0001 uncertainty
  // covers it; calipers do not. Reuses the instrument library directly.
  const criticalTol = Math.min(
    ...profile.segments.filter((s) => s.critical && s.toleranceMinus != null).map((s) => (s.tolerancePlus ?? 0) + (s.toleranceMinus ?? 0)),
    Infinity,
  );
  const bestInstrument = metrology
    .filter((m) => m.deviceType === "MICROMETER" || m.deviceType === "BORE_GAUGE" || m.deviceType === "CMM")
    .sort((a, b) => a.uncertainty - b.uncertainty)[0];
  const inspectionCapable =
    criticalTol === Infinity ? true : bestInstrument ? bestInstrument.uncertainty * 4 <= criticalTol : false;

  /* ---------------- Readiness, worst-gate ---------------- */
  const cssUsed = plan.some((o) => o.params.cssEnabled);
  const readiness = evaluateTurnReadiness({
    profile,
    materialKnown: true,
    latheSelected: Boolean(lathe),
    workholdingSelected: Boolean(holding),
    grip,
    stickout,
    boringBar,
    partOff,
    toolsAssigned: plan.filter((o) => tools.some((t) => t.station === o.toolStation)).length,
    toolsRequired: plan.length,
    chuckRpmKnown: holding?.maxRPM != null,
    cssUsed,
    inspectionCapable,
    postSelected: true,
    humanApproved: rot.humanApproved,
  });
  const blocking = readiness.gates.filter((g) => g.blocking && (g.status === "FAIL" || g.status === "NOT_ATTEMPTED"));

  /* ---------------- Nominal reasoning (never auto-applied) ------------ */
  const journal = profile.segments.find((s) => s.functionalRole === "BEARING_JOURNAL");
  const nominal =
    journal && !journal.confirmedByUser
      ? bestNominalSuggestion({ measured: journal.diameterStart, uncertainty: 0.0002, context: "SHAFT" })
      : null;

  /* ---------------- NC preview (development post) ---------------- */
  const postOps = results
    .filter((r) => r.result.ok)
    .map((r) => ({
      toolpath: (r.result as { ok: true; toolpath: never }).toolpath,
      station: r.op.toolStation,
      description: r.op.label,
      cssEnabled: r.op.params.cssEnabled,
      surfaceSpeed: r.op.params.surfaceSpeed,
      rpm: r.op.params.rpm,
      coolant: r.op.params.coolant === "FLOOD",
    }));
  const program = emitLatheProgram(postOps, {
    programNumber: "2001",
    partName: part.name,
    machine: lathe ? `${lathe.manufacturer} ${lathe.model}` : "No lathe",
    workOffset: "G54",
    maxRpmClamp: rot.maxRpmClamp,
    generatedAtIso: new Date().toISOString().slice(0, 10),
  });

  /* ---------------- Actions ---------------- */

  async function acceptNominal() {
    "use server";
    const u = await requireUser();
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
    const u = await requireUser();
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
    const u = await requireUser();
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
    const u = await requireUser();
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
  const intentDoc = JSON.parse(revision.intentJson ?? "{}") as { material?: { value?: string } };
  const cinematicInput = {
    partName: part.name,
    partNumber: part.partNumber,
    material: intentDoc.material?.value ?? null,
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

          {/* ---------------- PROFILE view ---------------- */}
          <Panel
            title="Profile — X/Z"
            meta={<StatusChip tone="neutral">PROFILE</StatusChip>}
          >
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
          </Panel>

          {/* ---------------- 3D playback ---------------- */}
          <Panel title="3D — stock removal playback" meta={<DevLabel>DEVELOPMENT — kinematic replay, not a collision check</DevLabel>}>
            <LatheSimView
              profile={profile}
              ops={results.filter((r) => r.result.ok).map((r) => ({ op: r.op, moves: r.result.ok ? r.result.toolpath.moves : [] }))}
            />
          </Panel>

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

          {/* ---------------- Operation plan ---------------- */}
          <Panel title="Operation plan" meta={<span className="flex items-center gap-3"><span className="font-mono text-[10.5px] text-muted tabular-nums">{plan.length} ops · est {totalMinutes.toFixed(2)} min (ESTIMATED — assumptions per op)</span><Link href={`/lathe/${id}/cost`} className="font-mono text-[10.5px] text-precision-dim hover:text-precision">Cost →</Link><CinematicTurnButton input={cinematicInput} /></span>} dense>
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
          </Panel>

          {/* ---------------- Hold intelligence ---------------- */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Hold — chuck grip" meta={<span className="flex gap-2"><DevLabel>Dev</DevLabel><StatusChip tone={tone(grip.verdict)}>{grip.verdict}</StatusChip></span>}>
              <p className="text-[12.5px] leading-relaxed text-platinum-dim">{grip.detail}</p>
              {grip.missingInputs.length > 0 && (
                <ul className="mt-1.5 space-y-1">
                  {grip.missingInputs.map((m, i) => (
                    <li key={i} className="flex gap-2 text-[11.5px] text-review"><Dot tone="review" /> {m}</li>
                  ))}
                </ul>
              )}
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
              {stickout.recommendations.length > 0 && (
                <p className="mt-1 text-[11.5px] text-muted">{stickout.recommendations.join(" · ")}</p>
              )}
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
              {partOff.recommendations.length > 0 && <p className="mt-1 text-[11.5px] text-muted">{partOff.recommendations.join(" · ")}</p>}
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
                compensation. There is no production export path for turning yet — the preview below is withheld while
                blocking gates fail, and export machinery arrives with verification, human approval and the same mint
                pattern the mill uses.
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
              <pre className="max-h-[400px] overflow-auto bg-void px-4 py-3 font-mono text-[11.5px] leading-relaxed text-platinum-dim">{program.code}</pre>
            )}
          </Panel>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

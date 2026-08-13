import Link from "next/link";
import { redirect } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { SUBJECT_LABEL, promoteToShopKnowledge, type DisagreementSubject } from "@/lib/disagreement";
import { TopBar } from "@/components/nav";
import { Button, EmptyState, Field, Notice, Panel, SectionHeading, StatusChip, inputClass, type Tone } from "@/components/ui";

/**
 * SHOP KNOWLEDGE
 *
 * What this shop has learned, kept separate from what is generally true.
 *
 * The distinction is the entire point. "1018 cuts at 300–600 SFM with carbide"
 * is published data. "That 1/2" three-flute chatters above 0.450 depth on VF-2
 * number two" is this shop's knowledge about this shop's machine, and it is
 * worth more here and nothing at all somewhere else. Collapsing the two into a
 * single confidence score would destroy both.
 *
 * This page is also the review queue: an open disagreement is promoted into
 * scoped knowledge, or declined with a reason, by a named human. Neither
 * outcome touches a gate.
 */

const CATEGORY_LABEL: Record<string, string> = {
  TOOL_BEHAVIOUR: "Tool behaviour",
  FIXTURE_BEHAVIOUR: "Fixture behaviour",
  MACHINE_BEHAVIOUR: "Machine behaviour",
  MATERIAL_BEHAVIOUR: "Material behaviour",
  INSPECTION_OUTCOME: "Inspection outcome",
  OPERATOR_CORRECTION: "Operator correction",
};

const STATUS_TONE: Record<string, Tone> = {
  OPEN: "review",
  EVIDENCE_REQUESTED: "unknown",
  ACCEPTED_AS_KNOWLEDGE: "pass",
  DECLINED: "neutral",
  SUPERSEDED: "neutral",
};

export default async function KnowledgePage(props: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await props.searchParams;
  const user = await requireUser();

  // Guide friction: where the shop's people go back or skip. Product
  // telemetry about the guide, shown here because "where we struggle" is
  // shop knowledge too — it never feeds a gate and carries no part data.
  const guideEvents = await db.guideEvent.findMany({
    where: { organizationId: user.organizationId, action: { in: ["BACK", "SKIP", "FLOW_COMPLETE", "START"] } },
    orderBy: { createdAt: "desc" },
    take: 2000,
  });
  const friction = new Map<string, { flowId: string; stepId: string; backs: number; skips: number }>();
  let starts = 0;
  let completes = 0;
  for (const e of guideEvents) {
    if (e.action === "START") starts++;
    if (e.action === "FLOW_COMPLETE") completes++;
    if ((e.action === "BACK" || e.action === "SKIP") && e.stepId) {
      const key = `${e.flowId}:${e.stepId}`;
      const row = friction.get(key) ?? { flowId: e.flowId, stepId: e.stepId, backs: 0, skips: 0 };
      if (e.action === "BACK") row.backs++;
      else row.skips++;
      friction.set(key, row);
    }
  }
  const frictionRows = [...friction.values()].sort((a, b) => b.backs + b.skips - (a.backs + a.skips)).slice(0, 8);

  const betaRuns = await db.betaRunRecord.findMany({
    where: { organizationId: user.organizationId },
    orderBy: { createdAt: "desc" },
    take: 50,
  });
  const verdictTally = { YES: 0, PARTLY: 0, NO: 0 } as Record<string, number>;
  const wrongTally = new Map<string, number>();
  for (const b of betaRuns) {
    verdictTally[b.verdict] = (verdictTally[b.verdict] ?? 0) + 1;
    try {
      for (const c of JSON.parse(b.wrongCategoriesJson) as string[]) wrongTally.set(c, (wrongTally.get(c) ?? 0) + 1);
    } catch {
      /* unreadable categories stay uncounted */
    }
  }

  const [knowledge, disagreements, machines, tools, materials] = await Promise.all([
    db.shopKnowledge.findMany({
      where: { organizationId: user.organizationId, active: true },
      include: { machine: true, tool: true, material: true, recordedBy: true },
      orderBy: [{ jobCount: "desc" }, { lastObservedAt: "desc" }],
    }),
    db.disagreement.findMany({
      where: { organizationId: user.organizationId },
      include: { user: true, partRevision: { include: { part: true } } },
      orderBy: { createdAt: "desc" },
      take: 25,
    }),
    db.machine.findMany({ where: { organizationId: user.organizationId }, orderBy: { model: "asc" } }),
    db.tool.findMany({ where: { organizationId: user.organizationId }, orderBy: { toolNumber: "asc" } }),
    db.material.findMany({ where: { organizationId: user.organizationId }, orderBy: { name: "asc" } }),
  ]);

  /* ---------------- Review actions ---------------- */

  async function promote(formData: FormData) {
    "use server";
    // Organisation comes from the session; the form supplies only the ids the
    // library call re-checks against that organisation.
    const currentUser = await requireUser();
    const disagreementId = String(formData.get("disagreementId"));
    const category = String(formData.get("category"));
    const observation = String(formData.get("observation") ?? "").trim();
    if (!observation) redirect("/knowledge?error=observation");

    // A threshold is all-or-nothing: a number without its parameter, unit and
    // direction is not a threshold, it is a stray value.
    const parameter = String(formData.get("parameter") ?? "").trim() || null;
    const rawValue = String(formData.get("thresholdValue") ?? "").trim();
    const thresholdValue = rawValue === "" ? null : Number(rawValue);
    const thresholdUnit = String(formData.get("thresholdUnit") ?? "").trim() || null;
    const direction = (String(formData.get("direction") ?? "") || null) as "ABOVE" | "BELOW" | null;
    const thresholdFields = [parameter, thresholdValue, thresholdUnit, direction];
    const provided = thresholdFields.filter((v) => v !== null).length;
    if (provided !== 0 && provided !== 4) redirect("/knowledge?error=threshold");
    if (thresholdValue !== null && !Number.isFinite(thresholdValue)) redirect("/knowledge?error=threshold");

    const result = await promoteToShopKnowledge({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      disagreementId,
      category,
      observation,
      machineId: String(formData.get("machineId") ?? "") || null,
      toolId: String(formData.get("toolId") ?? "") || null,
      materialId: String(formData.get("materialId") ?? "") || null,
      parameter,
      thresholdValue,
      thresholdUnit,
      direction,
    });
    if (!result) redirect("/knowledge?error=notfound");
    redirect("/knowledge");
  }

  async function decline(formData: FormData) {
    "use server";
    const currentUser = await requireUser();
    const disagreementId = String(formData.get("disagreementId"));
    const reason = String(formData.get("reason") ?? "").trim();
    if (!reason) redirect("/knowledge?error=reason");

    const row = await db.disagreement.findFirst({
      where: { id: disagreementId, organizationId: currentUser.organizationId },
    });
    if (!row) redirect("/knowledge?error=notfound");

    await db.disagreement.update({
      where: { id: row.id },
      data: { status: "DECLINED", resolution: reason, gateCleared: false },
    });
    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "Disagreement",
      entityId: row.id,
      action: "UPDATE",
      actorType: "HUMAN",
      field: "status",
      oldValue: row.status,
      newValue: "DECLINED",
      reason,
    });
    redirect("/knowledge");
  }

  /** WAS CANVAS RIGHT? — beta run evidence. Stored, audited, read by no engine. */
  async function recordBetaRun(formData: FormData) {
    "use server";
    const currentUser = await requireUser();
    const verdict = String(formData.get("verdict") ?? "");
    if (!["YES", "PARTLY", "NO"].includes(verdict)) redirect("/knowledge?error=verdict");
    const wrong = formData.getAll("wrong").map(String).filter(Boolean);
    if (verdict !== "YES" && wrong.length === 0) redirect("/knowledge?error=categories");
    const num = (name: string) => {
      const v = String(formData.get(name) ?? "").trim();
      if (v === "") return null;
      const n = Number(v);
      return Number.isFinite(n) && n > 0 ? n : null;
    };
    const txt = (name: string) => String(formData.get(name) ?? "").trim() || null;
    const row = await db.betaRunRecord.create({
      data: {
        organizationId: currentUser.organizationId,
        createdById: currentUser.id,
        machineLabel: txt("machineLabel"),
        materialName: txt("materialName"),
        toolNotes: txt("toolNotes"),
        holderNotes: txt("holderNotes"),
        workholdingNotes: txt("workholdingNotes"),
        predictedCycleMinutes: num("predictedCycle"),
        actualCycleMinutes: num("actualCycle"),
        predictedLoadNote: txt("predictedLoadNote"),
        actualLoadNote: txt("actualLoadNote"),
        canvasRecommendation: txt("canvasRecommendation"),
        verdict,
        wrongCategoriesJson: JSON.stringify(wrong),
        whatWasWrong: verdict === "YES" ? null : txt("whatWasWrong"),
        measuredResultsNote: txt("measuredResultsNote"),
        toolWearNote: txt("toolWearNote"),
        chatter: formData.get("chatter") === "on" ? true : null,
        scrapOrFailure: formData.get("scrap") === "on",
        correctiveAction: txt("correctiveAction"),
      },
    });
    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "BetaRunRecord",
      entityId: row.id,
      action: "CREATE",
      actorType: "HUMAN",
      field: "verdict",
      newValue: verdict + (wrong.length ? ` — ${wrong.join(", ")}` : ""),
      reason: "Beta run evidence recorded — was CANVAS right?",
    });
    redirect("/knowledge");
  }

  const reviewable = new Set(["OPEN", "EVIDENCE_REQUESTED"]);

  return (
    <>
      <TopBar>
        <span className="tech-label">Shop intelligence</span>
        <span className="text-muted">/</span>
        <span className="tech-label">Shop knowledge</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="What this shop has learned on this equipment, kept deliberately separate from what is generally true. Published cutting data belongs to everyone; that a particular cutter chatters above a particular depth on a particular machine belongs here.">
            Shop knowledge
          </SectionHeading>

          {error && (
            <Notice tone="risk" title="Not recorded">
              {error === "observation" && "The observation text is required — knowledge with no content is not knowledge."}
              {error === "threshold" && "A threshold needs all four of parameter, value, unit and direction, or none of them. A number without its context is a stray value."}
              {error === "reason" && "Declining a disagreement requires a reason. The person who recorded it deserves to know why."}
              {error === "notfound" && "That disagreement was not found in this organisation."}
              {error === "verdict" && "Pick YES, PARTLY or NO — the verdict is the machinist's call and cannot default."}
              {error === "categories" && "PARTLY or NO needs at least one category — evidence that something was wrong without saying what teaches nothing."}
            </Notice>
          )}

          <Notice tone="precision" title="Shop knowledge is not universal knowledge">
            Everything on this page is scoped to the equipment it was observed on. CANVAS will surface it when planning
            against that machine, that tool or that material, and will not offer it as evidence about anything else. It
            is also never promoted into an engineering fact — an observation across seventeen jobs is strong evidence
            about this shop and still not a published material property.
          </Notice>

          {/* ---------------- WAS CANVAS RIGHT? — beta evidence -------- */}
          <Panel
            title="Was CANVAS right?"
            meta={
              <span className="flex items-center gap-2">
                <span className="font-mono text-[10.5px] text-muted tabular-nums">
                  {betaRuns.length === 0
                    ? "no runs reported"
                    : `${verdictTally.YES} yes · ${verdictTally.PARTLY} partly · ${verdictTally.NO} no`}
                </span>
                <StatusChip tone="review">BETA EVIDENCE</StatusChip>
              </span>
            }
          >
            <p className="mb-3 text-[11.5px] leading-relaxed text-muted">
              One record per real run: what CANVAS predicted, what the machine actually did, and your call. This is
              shop-scoped evidence for development — no engine reads it to change a calculation, and it never becomes
              universal model truth.
            </p>

            {wrongTally.size > 0 && (
              <div className="mb-3 flex flex-wrap gap-2">
                {[...wrongTally.entries()].sort((a, b) => b[1] - a[1]).map(([c, n]) => (
                  <span key={c} className="border border-review/40 px-2 py-0.5 font-mono text-[10.5px] text-review tabular-nums">
                    {c.replace(/_/g, " ").toLowerCase()} × {n}
                  </span>
                ))}
              </div>
            )}

            <form action={recordBetaRun} className="space-y-3">
              <fieldset>
                <legend className="tech-label mb-1.5">The machinist&apos;s call — never inferred</legend>
                <div className="flex gap-2">
                  {(["YES", "PARTLY", "NO"] as const).map((v) => (
                    <label key={v} className="flex cursor-pointer items-center gap-1.5 border border-line-strong px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-platinum-dim has-[:checked]:border-precision/60 has-[:checked]:text-precision">
                      <input type="radio" name="verdict" value={v} required className="accent-[color:var(--c-blue)]" />
                      {v}
                    </label>
                  ))}
                </div>
              </fieldset>
              <fieldset>
                <legend className="tech-label mb-1.5">If partly or no — what was wrong?</legend>
                <div className="flex flex-wrap gap-1.5">
                  {["CYCLE_ESTIMATE", "TOOL_LOAD", "WORKHOLDING", "FEED_RECOMMENDATION", "TOOL_SELECTION", "INSPECTION", "GEOMETRY", "OTHER"].map((c) => (
                    <label key={c} className="flex cursor-pointer items-center gap-1.5 border border-line px-2 py-1 text-[10px] uppercase tracking-[0.1em] text-muted has-[:checked]:border-review/60 has-[:checked]:text-review">
                      <input type="checkbox" name="wrong" value={c} className="accent-[color:var(--c-amber,#b86a0a)]" />
                      {c.replace(/_/g, " ").toLowerCase()}
                    </label>
                  ))}
                </div>
              </fieldset>
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="block">
                  <span className="tech-label mb-0.5 block">Machine</span>
                  <input name="machineLabel" placeholder="VF-2 #2" className={inputClass} />
                </label>
                <label className="block">
                  <span className="tech-label mb-0.5 block">Material</span>
                  <input name="materialName" placeholder="6061-T6" className={inputClass} />
                </label>
                <label className="block">
                  <span className="tech-label mb-0.5 block">Tool / holder</span>
                  <input name="toolNotes" placeholder="T3 1/2″ 3F carbide" className={inputClass} />
                </label>
                <label className="block">
                  <span className="tech-label mb-0.5 block">Predicted cycle (min)</span>
                  <input name="predictedCycle" inputMode="decimal" className={inputClass} />
                </label>
                <label className="block">
                  <span className="tech-label mb-0.5 block">Actual cycle (min)</span>
                  <input name="actualCycle" inputMode="decimal" className={inputClass} />
                </label>
                <label className="block">
                  <span className="tech-label mb-0.5 block">Workholding</span>
                  <input name="workholdingNotes" placeholder="6″ vise, 0.6 grip" className={inputClass} />
                </label>
              </div>
              <label className="block">
                <span className="tech-label mb-0.5 block">What was wrong / what happened</span>
                <textarea name="whatWasWrong" rows={2} className={`${inputClass} w-full`} placeholder="Cycle came in 40s over the estimate; corner at op 3 chattered until feed dropped to F28…" />
              </label>
              <details>
                <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-[0.14em] text-muted hover:text-platinum">
                  Full record — load, results, wear, corrective action
                </summary>
                <div className="mt-2 grid gap-3 sm:grid-cols-2">
                  <label className="block">
                    <span className="tech-label mb-0.5 block">CANVAS predicted load</span>
                    <input name="predictedLoadNote" placeholder="TARGET band, brief HIGH at corner" className={inputClass} />
                  </label>
                  <label className="block">
                    <span className="tech-label mb-0.5 block">Actual spindle load (if observed)</span>
                    <input name="actualLoadNote" placeholder="peaked 62% at the corner" className={inputClass} />
                  </label>
                  <label className="block">
                    <span className="tech-label mb-0.5 block">CANVAS recommendation under test</span>
                    <input name="canvasRecommendation" placeholder="raise F32→F41 on L120–160" className={inputClass} />
                  </label>
                  <label className="block">
                    <span className="tech-label mb-0.5 block">Measured part results</span>
                    <input name="measuredResultsNote" placeholder="bore +0.0002, all in tolerance" className={inputClass} />
                  </label>
                  <label className="block">
                    <span className="tech-label mb-0.5 block">Tool wear notes</span>
                    <input name="toolWearNote" className={inputClass} />
                  </label>
                  <label className="block">
                    <span className="tech-label mb-0.5 block">Corrective action taken</span>
                    <input name="correctiveAction" className={inputClass} />
                  </label>
                </div>
                <div className="mt-2 flex gap-4">
                  <label className="flex items-center gap-1.5 text-[11.5px] text-platinum-dim">
                    <input type="checkbox" name="chatter" className="accent-[color:var(--c-blue)]" /> Chatter observed
                  </label>
                  <label className="flex items-center gap-1.5 text-[11.5px] text-platinum-dim">
                    <input type="checkbox" name="scrap" className="accent-[color:var(--c-blue)]" /> Scrap / failure
                  </label>
                </div>
              </details>
              <Button type="submit" variant="primary">Record run evidence</Button>
            </form>

            {betaRuns.length > 0 && (
              <ul className="mt-4 border-t border-line pt-1">
                {betaRuns.slice(0, 10).map((b) => {
                  let cats: string[] = [];
                  try { cats = JSON.parse(b.wrongCategoriesJson) as string[]; } catch { /* shown without categories */ }
                  return (
                    <li key={b.id} className="border-b border-line/60 py-2 last:border-0">
                      <div className="flex flex-wrap items-baseline gap-x-3">
                        <StatusChip tone={b.verdict === "YES" ? "pass" : b.verdict === "PARTLY" ? "review" : "risk"}>{b.verdict}</StatusChip>
                        <span className="font-mono text-[11px] text-muted">{b.createdAt.toISOString().slice(0, 10)}</span>
                        {b.machineLabel && <span className="font-mono text-[11px] text-platinum-dim">{b.machineLabel}</span>}
                        {b.materialName && <span className="font-mono text-[11px] text-muted">{b.materialName}</span>}
                        {b.predictedCycleMinutes !== null && b.actualCycleMinutes !== null && (
                          <span className="font-mono text-[11px] text-platinum-dim tabular-nums">
                            est {b.predictedCycleMinutes.toFixed(1)} → ran {b.actualCycleMinutes.toFixed(1)} min
                          </span>
                        )}
                        {b.scrapOrFailure && <StatusChip tone="risk">SCRAP</StatusChip>}
                        {cats.map((c) => (
                          <span key={c} className="text-[10px] uppercase tracking-[0.1em] text-review">{c.replace(/_/g, " ").toLowerCase()}</span>
                        ))}
                      </div>
                      {b.whatWasWrong && <p className="mt-0.5 text-[12px] leading-relaxed text-platinum-dim">{b.whatWasWrong}</p>}
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>

          {frictionRows.length > 0 && (
            <Panel title="Guide friction" meta={<span className="tech-label">{starts} flow starts · {completes} completions</span>}>
              <p className="mb-2 text-[11.5px] leading-relaxed text-muted">
                Steps the shop&apos;s people back out of or skip most. Telemetry about the guide, not about parts — it feeds no gate. A step everyone skips is a lesson worth rewriting, or a control worth moving.
              </p>
              <ul>
                {frictionRows.map((r) => (
                  <li key={`${r.flowId}:${r.stepId}`} className="flex items-center gap-3 border-b border-line/60 py-1.5 last:border-0">
                    <span className="font-mono text-[11px] text-muted">{r.flowId}</span>
                    <span className="min-w-0 flex-1 font-mono text-[12px] text-platinum">{r.stepId}</span>
                    {r.backs > 0 && <span className="font-mono text-[11px] text-review tabular-nums">{r.backs} back</span>}
                    {r.skips > 0 && <span className="font-mono text-[11px] text-muted tabular-nums">{r.skips} skipped</span>}
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          <Panel title="Recorded observations" meta={<span className="tech-label">{knowledge.length}</span>}>
            {knowledge.length === 0 ? (
              <EmptyState
                title="Nothing recorded yet"
                body="Shop knowledge accumulates from disagreements you record, from jobs that ran, and from jobs that did not. It is the part of CANVAS that only your shop can fill in."
                action={{ label: "Part library", href: "/parts" }}
              />
            ) : (
              <ul className="space-y-3">
                {knowledge.map((k) => (
                  <li key={k.id} className="border border-line px-3 py-2.5">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="tech-label">{CATEGORY_LABEL[k.category] ?? k.category}</span>
                      <span className="tech-label">
                        {k.jobCount} {k.jobCount === 1 ? "job" : "jobs"} · confidence {k.confidence.toLowerCase()}
                      </span>
                    </div>
                    <p className="mt-1.5 text-[13px] leading-relaxed text-platinum">{k.observation}</p>
                    {k.parameter && k.thresholdValue != null && (
                      <p className="mt-1 font-mono text-[12px] text-precision">
                        {k.parameter} {k.direction === "ABOVE" ? "≥" : "≤"} {k.thresholdValue}
                        {k.thresholdUnit ?? ""}
                      </p>
                    )}
                    <p className="tech-label mt-1.5">
                      Scope:{" "}
                      {[
                        k.machine ? `${k.machine.manufacturer} ${k.machine.model}` : null,
                        k.tool ? `T${k.tool.toolNumber} ${k.tool.description}` : null,
                        k.material?.name ?? null,
                      ]
                        .filter(Boolean)
                        .join(" · ") || "Shop-wide"}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Recorded disagreements" meta={<span className="tech-label">{disagreements.length}</span>}>
            {disagreements.length === 0 ? (
              <EmptyState
                title="No disagreements recorded"
                body="When CANVAS says something you know to be wrong, say so. Recording it does not clear the gate — it captures what you know so it can be evaluated, and so the same argument does not have to happen twice."
                action={{ label: "Part library", href: "/parts" }}
              />
            ) : (
              <ul className="space-y-3">
                {disagreements.map((d) => (
                  <li key={d.id} className="border border-line px-3 py-2.5">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="tech-label">
                        {SUBJECT_LABEL[d.subjectType as DisagreementSubject] ?? d.subjectType}
                        {d.subjectId ? ` · ${d.subjectId}` : ""}
                      </span>
                      <span className="flex items-center gap-2">
                        {d.hasRunComparable && <StatusChip tone="pass">Comparable job run</StatusChip>}
                        <StatusChip tone={STATUS_TONE[d.status] ?? "neutral"}>
                          {d.status.replace(/_/g, " ").toLowerCase()}
                        </StatusChip>
                      </span>
                    </div>

                    <p className="tech-label mt-2">CANVAS said</p>
                    <p className="text-[12px] leading-relaxed text-muted">{d.canvasPosition}</p>

                    <p className="tech-label mt-2">
                      {d.user?.name ?? "Operator"} said
                    </p>
                    <p className="text-[12.5px] leading-relaxed text-platinum">{d.reasoning}</p>

                    {d.proposedValue && (
                      <p className="mt-1.5 font-mono text-[12px] text-precision">Proposed: {d.proposedValue}</p>
                    )}

                    {d.resolution && (
                      <>
                        <p className="tech-label mt-2">Resolution</p>
                        <p className="text-[12px] leading-relaxed text-muted">{d.resolution}</p>
                      </>
                    )}

                    <p className="tech-label mt-2">
                      Gate cleared by this: no
                      {d.partRevision?.part ? " · " : ""}
                      {d.partRevision?.part && (
                        <Link href={`/parts/${d.partRevision.part.id}/readiness`} className="hover:text-platinum">
                          {d.partRevision.part.name}
                        </Link>
                      )}
                    </p>

                    {reviewable.has(d.status) && (
                      <details className="mt-2.5 border-t border-line pt-2.5">
                        <summary className="tech-label cursor-pointer select-none hover:text-platinum">
                          Review — promote to shop knowledge or decline
                        </summary>

                        <form action={promote} className="mt-3 space-y-3">
                          <input type="hidden" name="disagreementId" value={d.id} />
                          <div className="grid gap-3 sm:grid-cols-2">
                            <Field label="Category">
                              <select name="category" className={inputClass} defaultValue="OPERATOR_CORRECTION">
                                {Object.entries(CATEGORY_LABEL).map(([v, l]) => (
                                  <option key={v} value={v}>{l}</option>
                                ))}
                              </select>
                            </Field>
                            <Field label="Machine scope (optional)">
                              <select name="machineId" className={inputClass} defaultValue="">
                                <option value="">Shop-wide</option>
                                {machines.map((m) => (
                                  <option key={m.id} value={m.id}>{m.manufacturer} {m.model}</option>
                                ))}
                              </select>
                            </Field>
                            <Field label="Tool scope (optional)">
                              <select name="toolId" className={inputClass} defaultValue="">
                                <option value="">Any tool</option>
                                {tools.map((t) => (
                                  <option key={t.id} value={t.id}>T{t.toolNumber} {t.description}</option>
                                ))}
                              </select>
                            </Field>
                            <Field label="Material scope (optional)">
                              <select name="materialId" className={inputClass} defaultValue="">
                                <option value="">Any material</option>
                                {materials.map((m) => (
                                  <option key={m.id} value={m.id}>{m.name}</option>
                                ))}
                              </select>
                            </Field>
                          </div>
                          <Field label="Observation, as it should be surfaced during planning">
                            <textarea
                              name="observation"
                              rows={2}
                              defaultValue={d.reasoning}
                              className={inputClass}
                            />
                          </Field>
                          <div className="grid gap-3 sm:grid-cols-4">
                            <Field label="Parameter (optional)">
                              <input name="parameter" placeholder="e.g. depth of cut" className={inputClass} />
                            </Field>
                            <Field label="Threshold value">
                              <input name="thresholdValue" inputMode="decimal" className={inputClass} />
                            </Field>
                            <Field label="Unit">
                              <input name="thresholdUnit" placeholder={'e.g. "'} className={inputClass} />
                            </Field>
                            <Field label="Direction">
                              <select name="direction" className={inputClass} defaultValue="">
                                <option value="">—</option>
                                <option value="ABOVE">Above</option>
                                <option value="BELOW">Below</option>
                              </select>
                            </Field>
                          </div>
                          <p className="text-[11.5px] leading-relaxed text-muted">
                            Promotion records this as scoped shop knowledge at{" "}
                            {d.hasRunComparable ? "LOW confidence (one comparable job)" : "UNKNOWN confidence (no comparable job)"}.
                            It does not clear any gate, and it is never offered as evidence outside its scope.
                          </p>
                          <Button type="submit" variant="primary">Promote to shop knowledge</Button>
                        </form>

                        <form action={decline} className="mt-3 flex items-end gap-3 border-t border-line pt-3">
                          <input type="hidden" name="disagreementId" value={d.id} />
                          <div className="flex-1">
                            <Field label="Decline with a reason">
                              <input name="reason" placeholder="Why this is not being recorded as knowledge" className={inputClass} />
                            </Field>
                          </div>
                          <Button type="submit">Decline</Button>
                        </form>
                      </details>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Notice tone="review" title="Promotion never clears a gate">
            Promoting a disagreement records what the machinist knows as scoped shop knowledge — it does not change any
            readiness gate, and declining one requires saying why. The gate moves when the evidence moves.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

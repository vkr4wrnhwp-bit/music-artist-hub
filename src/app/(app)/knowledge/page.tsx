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
            </Notice>
          )}

          <Notice tone="precision" title="Shop knowledge is not universal knowledge">
            Everything on this page is scoped to the equipment it was observed on. CANVAS will surface it when planning
            against that machine, that tool or that material, and will not offer it as evidence about anything else. It
            is also never promoted into an engineering fact — an observation across seventeen jobs is strong evidence
            about this shop and still not a published material property.
          </Notice>

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

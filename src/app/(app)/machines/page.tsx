import Link from "next/link";
import { redirect } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { getMachines } from "@/lib/data";
import { summarizeCalibration } from "@/lib/engines/calibration";
import { TELEMETRY_SOURCES } from "@/lib/telemetry";
import { TopBar } from "@/components/nav";
import { MachineEnvelope } from "@/components/machine-envelope";
import { Button, EmptyState, inputClass, LinkButton, Panel, SectionHeading, StatusChip } from "@/components/ui";
import { revalidatePath } from "next/cache";

export default async function MachinesPage() {
  const user = await requireUser();
  const machines = await getMachines(user.organizationId);
  const [calRecords, referenceCuts, tools, pocketCounts] = await Promise.all([
    db.machineCalibrationRecord.findMany({ where: { organizationId: user.organizationId }, orderBy: { createdAt: "desc" } }),
    db.referenceCut.findMany({ where: { organizationId: user.organizationId }, orderBy: { createdAt: "desc" }, take: 20 }),
    db.tool.findMany({ where: { organizationId: user.organizationId }, orderBy: { toolNumber: "asc" } }),
    // Carousel occupancy per machine. Counted, not inferred — a tool is in a
    // pocket because somebody recorded putting it there.
    db.tool.groupBy({
      by: ["machineId"],
      where: { organizationId: user.organizationId, machineId: { not: null }, pocket: { not: null } },
      _count: { _all: true },
    }),
  ]);
  const loadedByMachine = new Map(pocketCounts.map((r) => [r.machineId as string, r._count._all]));

  async function recordCycle(formData: FormData) {
    "use server";
    const u = await requireUser();
    const machineId = String(formData.get("machineId") ?? "");
    const programLabel = String(formData.get("programLabel") ?? "").trim();
    const est = Number(String(formData.get("estimated") ?? "").trim());
    const act = Number(String(formData.get("actual") ?? "").trim());
    const machine = await db.machine.findFirst({ where: { id: machineId, organizationId: u.organizationId } });
    if (!machine || !programLabel || !Number.isFinite(est) || est <= 0 || !Number.isFinite(act) || act <= 0) redirect("/machines");
    const row = await db.machineCalibrationRecord.create({
      data: { organizationId: u.organizationId, machineId, programLabel, estimatedMinutes: est, actualMinutes: act, createdById: u.id },
    });
    await audit({
      organizationId: u.organizationId, userId: u.id, entityType: "MachineCalibrationRecord", entityId: row.id,
      action: "CREATE", actorType: "HUMAN", field: "observed cycle",
      newValue: `${programLabel}: est ${est.toFixed(2)} min, actual ${act.toFixed(2)} min`,
      reason: "Actual machine cycle recorded against the CANVAS estimate.",
    });
    revalidatePath("/machines");
  }

  async function recordReferenceCut(formData: FormData) {
    "use server";
    const u = await requireUser();
    const get = (k: string) => String(formData.get(k) ?? "").trim();
    const num = (k: string) => Number(get(k));
    const machineId = get("machineId") || null;
    const toolId = get("toolId") || null;
    if (!get("materialName") || !get("operation") || !Number.isFinite(num("doc")) || !Number.isFinite(num("woc")) || !Number.isFinite(num("feed")) || !Number.isFinite(num("rpm"))) redirect("/machines");
    const row = await db.referenceCut.create({
      data: {
        organizationId: u.organizationId,
        machineId, toolId,
        materialName: get("materialName"),
        operation: get("operation"),
        docInches: num("doc"), wocInches: num("woc"), feedIpm: num("feed"), rpm: Math.round(num("rpm")),
        result: ["RUNS_CLEAN", "ACCEPTABLE", "MARGINAL"].includes(get("result")) ? get("result") : "ACCEPTABLE",
        notes: get("notes") || null,
        createdById: u.id,
      },
    });
    await audit({
      organizationId: u.organizationId, userId: u.id, entityType: "ReferenceCut", entityId: row.id,
      action: "CREATE", actorType: "HUMAN", field: "reference cut",
      newValue: `${get("operation")} · ${get("materialName")} · DOC ${get("doc")} WOC ${get("woc")} F${get("feed")} S${get("rpm")}`,
      reason: "Machinist marked a proven cutting region as shop evidence.",
    });
    revalidatePath("/machines");
  }

  return (
    <>
      <TopBar>
        <span className="tech-label">Machines</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <SectionHeading sub="Machine profiles are hard constraints. CANVAS validates travel, spindle limits, tool capacity and post-processor against these values — it never assumes a capability that is not recorded here.">
            Machines
          </SectionHeading>
          <div className="shrink-0 pt-1">
            <LinkButton href="/machines/new" size="sm" variant="primary">
              Add machine
            </LinkButton>
          </div>
        </div>

        {machines.length === 0 ? (
          <EmptyState
            title="No machine selected"
            body="Add a machine before CANVAS can validate travel, spindle limits or post-processing."
            action={{ label: "Add machine", href: "/machines/new" }}
          />
        ) : (
          <div className="space-y-6">
            {machines.map((m) => {
              const recs = calRecords.filter((r) => r.machineId === m.id);
              const summary = summarizeCalibration(recs);
              return (
              <Panel
                key={m.id}
                title={`${m.manufacturer} ${m.model}`}
                meta={
                  <span className="flex gap-2">
                    <StatusChip tone="neutral">{m.machineType.replace(/_/g, " ")}</StatusChip>
                    <StatusChip tone="neutral">{m.controller.replace(/_/g, " ")}</StatusChip>
                    {m.isReferenceProfile && <StatusChip tone="review">Reference profile</StatusChip>}
                    <Link
                      href={`/machines/${m.id}/carousel`}
                      className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted hover:text-precision"
                    >
                      Carousel
                    </Link>
                    <Link
                      href={`/machines/${m.id}/edit`}
                      className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted hover:text-precision"
                    >
                      Edit
                    </Link>
                  </span>
                }
                dense
              >
                {/* The machine is the object: its working volume drawn from
                    the profile values, the timing truth beside it. */}
                <div className="grid gap-4 p-4 lg:grid-cols-[300px_1fr]">
                  <div className="h-[190px]">
                    <MachineEnvelope
                      travelsX={m.travelsX}
                      travelsY={m.travelsY}
                      travelsZ={m.travelsZ}
                      tableX={m.tableX}
                      tableY={m.tableY}
                    />
                  </div>
                  <div>
                    <p className="font-mono text-[22px] text-white tabular-nums">
                      {m.maxSpindleRPM.toLocaleString()} <span className="text-[12px] text-muted">RPM</span>
                      <span className="ml-4">{m.maxSpindlePower} <span className="text-[12px] text-muted">hp</span></span>
                      <span className="ml-4">{m.maxRapid} <span className="text-[12px] text-muted">ipm rapid</span></span>
                    </p>
                    <p className="mt-2 text-[12px] leading-relaxed text-platinum-dim">{summary.statement}</p>
                    {summary.medianVariancePct !== null ? (
                      <p className="mt-1 font-mono text-[13px] text-platinum tabular-nums">
                        cycle estimates run {summary.medianVariancePct >= 0 ? "+" : ""}{summary.medianVariancePct}% vs this machine · spread {summary.spreadPct}% · shown beside estimates, never silently applied
                      </p>
                    ) : (
                      <p className="mt-1">
                        <StatusChip tone="unknown">INSUFFICIENT CALIBRATION DATA</StatusChip>
                      </p>
                    )}
                    {summary.status === "CALIBRATED" && (
                      <p className="mt-1">
                        <StatusChip tone="pass">CALIBRATED FROM {summary.samples} CYCLES</StatusChip>
                      </p>
                    )}
                  </div>
                </div>
                <div className="grid gap-px border-t border-line bg-line md:grid-cols-3">
                  <Spec
                    label="Travels"
                    rows={[
                      ["X", `${m.travelsX}″`],
                      ["Y", `${m.travelsY}″`],
                      ["Z", `${m.travelsZ}″`],
                      ["Table", `${m.tableX}″ × ${m.tableY}″`],
                    ]}
                  />
                  <Spec
                    label="Spindle & feed"
                    rows={[
                      ["Max RPM", String(m.maxSpindleRPM)],
                      ["Power", `${m.maxSpindlePower} hp`],
                      ["Torque", `${m.maxSpindleTorque} lb-ft`],
                      ["Max feed", `${m.maxFeed} ipm`],
                      ["Rapid", `${m.maxRapid} ipm`],
                    ]}
                  />
                  <Spec
                    label="Tooling & options"
                    rows={[
                      // Capacity is a spec; occupancy is a fact about this
                      // shop. Both, so "20 pockets" stops reading as though
                      // CANVAS knows what is in them.
                      [
                        "Changer",
                        `${loadedByMachine.get(m.id) ?? 0} of ${m.toolChangerCapacity} pockets loaded`,
                      ],
                      ["Max tool ⌀", `${m.maxToolDiameter}″`],
                      ["Max tool length", `${m.maxToolLength}″`],
                      ["Probe", m.probe ? "Yes" : "No"],
                      ["Tool setter", m.toolSetter ? "Yes" : "No"],
                      ["Through coolant", m.throughSpindleCoolant ? "Yes" : "No"],
                      ["Post", m.supportedPostProcessor],
                    ]}
                  />
                </div>
                {m.notes && (
                  <p className="border-t border-line px-4 py-3 text-[12px] leading-relaxed text-muted">{m.notes}</p>
                )}

                {/* Timing truth — recorded cycles and the record form,
                    on the machine they belong to. */}
                <details className="border-t border-line">
                  <summary className="cursor-pointer px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted hover:text-platinum">
                    Recorded cycles — {recs.length} · record another
                  </summary>
                  <div className="px-4 pb-3">
                    {recs.length > 0 && (
                      <ul className="pt-1">
                        {recs.slice(0, 5).map((r) => (
                          <li key={r.id} className="flex gap-4 py-1 font-mono text-[11px] text-muted tabular-nums">
                            <span className="min-w-0 flex-1 truncate text-platinum-dim">{r.programLabel}</span>
                            <span>est {r.estimatedMinutes.toFixed(2)}</span>
                            <span>actual {r.actualMinutes.toFixed(2)}</span>
                            <span className={r.actualMinutes > r.estimatedMinutes ? "text-review" : "text-pass"}>
                              {r.actualMinutes >= r.estimatedMinutes ? "+" : ""}{((r.actualMinutes - r.estimatedMinutes) * 60).toFixed(0)}s
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                    <form action={recordCycle} className="mt-2 flex flex-wrap items-end gap-3 border-t border-line/60 pt-3">
                      <input type="hidden" name="machineId" value={m.id} />
                      <label className="block">
                        <span className="tech-label mb-1 block">Program</span>
                        <input name="programLabel" placeholder="O2507" className={`${inputClass} w-28 font-mono`} />
                      </label>
                      <label className="block">
                        <span className="tech-label mb-1 block">Estimated (min)</span>
                        <input name="estimated" inputMode="decimal" className={`${inputClass} w-24 font-mono`} />
                      </label>
                      <label className="block">
                        <span className="tech-label mb-1 block">Actual (min)</span>
                        <input name="actual" inputMode="decimal" className={`${inputClass} w-24 font-mono`} />
                      </label>
                      <Button type="submit">Record cycle</Button>
                    </form>
                  </div>
                </details>
              </Panel>
            );})}
          </div>
        )}

        <div className="mt-6 space-y-6">
          {/* ---------------- Reference cuts ---------------- */}
          <Panel title={`Reference cuts — ${referenceCuts.length}`} meta={<span className="font-mono text-[10.5px] text-muted">SHOP_KNOWLEDGE · scoped, never universal</span>}>
            <p className="mb-2 text-[11.5px] leading-relaxed text-muted">
              A cutting region a machinist has personally proven on this machine, tool and material. Scoped evidence: it informs comparison against comparable contexts and is never generalized beyond them, and it clears no gate.
            </p>
            {referenceCuts.length > 0 && (
              <ul className="mb-3">
                {referenceCuts.map((rc) => (
                  <li key={rc.id} className="flex flex-wrap items-baseline gap-x-3 border-b border-line/60 py-1.5 font-mono text-[11.5px] tabular-nums last:border-0">
                    <StatusChip tone={rc.result === "RUNS_CLEAN" ? "pass" : rc.result === "MARGINAL" ? "review" : "neutral"}>{rc.result.replace(/_/g, " ")}</StatusChip>
                    <span className="text-platinum">{rc.operation}</span>
                    <span className="text-muted">{rc.materialName}</span>
                    <span className="text-muted">DOC {rc.docInches}″ · WOC {rc.wocInches}″ · F{rc.feedIpm} · S{rc.rpm}</span>
                    {rc.notes && <span className="min-w-0 flex-1 truncate text-muted">{rc.notes}</span>}
                  </li>
                ))}
              </ul>
            )}
            <form action={recordReferenceCut} className="flex flex-wrap items-end gap-3 border-t border-line/60 pt-3">
              <label className="block">
                <span className="tech-label mb-1 block">Machine</span>
                <select name="machineId" className={inputClass} defaultValue={machines[0]?.id ?? ""}>
                  {machines.map((m) => <option key={m.id} value={m.id}>{m.manufacturer} {m.model}</option>)}
                  <option value="">—</option>
                </select>
              </label>
              <label className="block">
                <span className="tech-label mb-1 block">Tool</span>
                <select name="toolId" className={inputClass} defaultValue="">
                  <option value="">—</option>
                  {tools.map((t) => <option key={t.id} value={t.id}>T{t.toolNumber} {t.description.slice(0, 24)}</option>)}
                </select>
              </label>
              <label className="block">
                <span className="tech-label mb-1 block">Material</span>
                <input name="materialName" placeholder="6061-T6" className={`${inputClass} w-28`} />
              </label>
              <label className="block">
                <span className="tech-label mb-1 block">Operation</span>
                <input name="operation" placeholder="Adaptive rough" className={`${inputClass} w-36`} />
              </label>
              <label className="block"><span className="tech-label mb-1 block">DOC ″</span><input name="doc" inputMode="decimal" className={`${inputClass} w-20 font-mono`} /></label>
              <label className="block"><span className="tech-label mb-1 block">WOC ″</span><input name="woc" inputMode="decimal" className={`${inputClass} w-20 font-mono`} /></label>
              <label className="block"><span className="tech-label mb-1 block">Feed ipm</span><input name="feed" inputMode="decimal" className={`${inputClass} w-20 font-mono`} /></label>
              <label className="block"><span className="tech-label mb-1 block">RPM</span><input name="rpm" inputMode="numeric" className={`${inputClass} w-20 font-mono`} /></label>
              <label className="block">
                <span className="tech-label mb-1 block">Result</span>
                <select name="result" className={inputClass} defaultValue="RUNS_CLEAN">
                  <option value="RUNS_CLEAN">Runs clean</option>
                  <option value="ACCEPTABLE">Acceptable</option>
                  <option value="MARGINAL">Marginal</option>
                </select>
              </label>
              <label className="block"><span className="tech-label mb-1 block">Notes</span><input name="notes" className={`${inputClass} w-40`} /></label>
              <Button type="submit">Mark reference cut</Button>
            </form>
          </Panel>

          {/* ---------------- Telemetry — NOT CONNECTED ---------------- */}
          <Panel title="Machine telemetry" meta={<StatusChip tone="unknown">NOT CONNECTED</StatusChip>} dense>
            <ul>
              {TELEMETRY_SOURCES.map((src) => (
                <li key={src.protocol} className="flex items-center gap-3 border-b border-line/60 px-4 py-2 last:border-0">
                  <StatusChip tone="unknown">NOT CONNECTED</StatusChip>
                  <span className="text-[12px] text-platinum">{src.label}</span>
                </li>
              ))}
            </ul>
            <p className="border-t border-line/60 px-4 py-2.5 text-[11px] leading-relaxed text-muted">
              The interfaces exist (spindle load, actual feed, cycle samples, tool life) so a real source can plug in — but no adapter is built, and nothing in CANVAS claims live machine data until one is. The long-term objective: calibrate estimated load and time against what these machines actually did.
            </p>
          </Panel>
        </div>
      </main>
    </>
  );
}

function Spec({ label, rows }: { label: string; rows: [string, string][] }) {
  return (
    <div className="bg-surface p-4">
      <p className="tech-label mb-2">{label}</p>
      <table className="w-full">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td className="py-1 pr-4 font-mono text-[11px] text-muted">{k}</td>
              <td className="py-1 text-right font-mono text-[12px] text-platinum">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const dynamic = "force-dynamic";

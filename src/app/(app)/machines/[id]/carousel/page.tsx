import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { TopBar } from "@/components/nav";
import { Button, EmptyState, Notice, Panel, SectionHeading, inputClass } from "@/components/ui";

/**
 * THE TOOL CAROUSEL — what is actually loaded in this machine's changer.
 *
 * Before this existed, `Machine.toolChangerCapacity` was an integer and the
 * machines page printed "20 pockets" as a specification. Nothing anywhere
 * recorded that T3 is in pocket 3 of the VF-2, so "is the tooling for this
 * job actually in the machine" was a question CANVAS could not answer and
 * did not admit it could not answer.
 *
 * What this deliberately does NOT do, yet: change the TOOL AVAILABILITY
 * gate. `readiness.ts` passes that gate when a part has tools assigned from
 * the crib, and it still does. Making the gate ask whether those tools are
 * loaded in the assigned machine is the obviously correct next step, and it
 * would start failing parts that pass today — which is a decision about how
 * a shop works, not a detail to slip in behind a schema change. The
 * occupancy is recorded first; the gate follows separately.
 *
 * A pocket is empty until a human says otherwise. There is no inference
 * here, no "probably still loaded from last time", and no default fill from
 * the operation plan — a carousel map that guesses is worse than none,
 * because a machinist would walk to the machine expecting to find a tool.
 */
export default async function CarouselPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ problem?: string }>;
}) {
  const { id } = await props.params;
  const { problem } = await props.searchParams;
  const user = await requireUser();

  const machine = await db.machine.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!machine) notFound();

  const [loaded, unassigned] = await Promise.all([
    db.tool.findMany({ where: { machineId: id }, orderBy: { pocket: "asc" } }),
    db.tool.findMany({
      where: { organizationId: user.organizationId, machineId: null },
      orderBy: { toolNumber: "asc" },
    }),
  ]);

  const byPocket = new Map(loaded.filter((t) => t.pocket !== null).map((t) => [t.pocket as number, t]));
  const pockets = Array.from({ length: machine.toolChangerCapacity }, (_, i) => i + 1);

  // Tools recorded as in this machine but with no pocket number. Not
  // possible through this page, but a data import could produce it and
  // silently dropping them from the view would hide a real record.
  const inMachineNoPocket = loaded.filter((t) => t.pocket === null);

  async function loadTool(formData: FormData): Promise<void> {
    "use server";
    const u = await requireWrite();
    const machineId = String(formData.get("machineId") ?? "");
    const toolId = String(formData.get("toolId") ?? "");
    const pocket = Number(String(formData.get("pocket") ?? ""));

    const m = await db.machine.findFirst({ where: { id: machineId, organizationId: u.organizationId } });
    const t = await db.tool.findFirst({ where: { id: toolId, organizationId: u.organizationId } });
    const back = `/machines/${machineId}/carousel`;
    if (!m || !t) redirect("/machines");

    if (!Number.isInteger(pocket) || pocket < 1 || pocket > m.toolChangerCapacity) {
      redirect(
        `${back}?problem=${encodeURIComponent(
          `Pocket ${pocket} is outside this changer — it has ${m.toolChangerCapacity} pockets.`,
        )}`,
      );
    }

    // The tool must physically fit the changer. This is the machine's own
    // recorded limit against the tool's own recorded geometry — no estimate.
    const problems: string[] = [];
    if (t.diameter > m.maxToolDiameter)
      problems.push(`⌀${t.diameter} exceeds the changer's ${m.maxToolDiameter} maximum tool diameter`);
    if (t.overallLength > m.maxToolLength)
      problems.push(`overall length ${t.overallLength} exceeds the changer's ${m.maxToolLength} maximum`);
    if (problems.length > 0) {
      redirect(`${back}?problem=${encodeURIComponent(`T${t.toolNumber} will not fit: ${problems.join("; ")}.`)}`);
    }

    const occupant = await db.tool.findFirst({ where: { machineId, pocket } });
    if (occupant && occupant.id !== toolId) {
      redirect(
        `${back}?problem=${encodeURIComponent(
          `Pocket ${pocket} already holds T${occupant.toolNumber}. Unload it first.`,
        )}`,
      );
    }

    await db.tool.update({ where: { id: toolId }, data: { machineId, pocket } });
    await audit({
      organizationId: u.organizationId,
      userId: u.id,
      entityType: "Tool",
      entityId: toolId,
      action: "UPDATE",
      actorType: "HUMAN",
      field: "carousel pocket",
      oldValue: t.machineId ? `machine ${t.machineId} pocket ${t.pocket ?? "—"}` : "crib",
      newValue: `${m.manufacturer} ${m.model} pocket ${pocket}`,
      reason: "Tool loaded into the changer.",
    });
    revalidatePath(back);
    revalidatePath("/tools");
    redirect(back);
  }

  async function unloadTool(formData: FormData): Promise<void> {
    "use server";
    const u = await requireWrite();
    const toolId = String(formData.get("toolId") ?? "");
    const machineId = String(formData.get("machineId") ?? "");
    const t = await db.tool.findFirst({ where: { id: toolId, organizationId: u.organizationId } });
    if (!t) redirect("/machines");

    await db.tool.update({ where: { id: toolId }, data: { machineId: null, pocket: null } });
    await audit({
      organizationId: u.organizationId,
      userId: u.id,
      entityType: "Tool",
      entityId: toolId,
      action: "UPDATE",
      actorType: "HUMAN",
      field: "carousel pocket",
      oldValue: `pocket ${t.pocket ?? "—"}`,
      newValue: "crib",
      reason: "Tool removed from the changer.",
    });
    revalidatePath(`/machines/${machineId}/carousel`);
    revalidatePath("/tools");
    redirect(`/machines/${machineId}/carousel`);
  }

  const occupied = byPocket.size;

  return (
    <>
      <TopBar>
        <Link href="/machines" className="tech-label hover:text-platinum">
          Machines
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">
          {machine.manufacturer} {machine.model}
        </span>
        <span className="text-muted">/</span>
        <span className="tech-label">Carousel</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          <SectionHeading sub="What is physically in the changer, recorded by the people who put it there. A pocket is empty until somebody says otherwise — CANVAS does not infer occupancy from the operation plan, because a machinist would walk to the machine expecting to find the tool.">
            {machine.manufacturer} {machine.model} — tool changer
          </SectionHeading>

          <p className="font-mono text-[12px] text-muted">
            <span className="text-[20px] text-white tabular-nums">{occupied}</span>
            <span className="mx-1.5">/</span>
            <span className="tabular-nums">{machine.toolChangerCapacity}</span>
            <span className="ml-2">pockets loaded</span>
          </p>

          {problem && (
            <Notice tone="risk" title="Not changed">
              {problem}
            </Notice>
          )}

          {machine.toolChangerCapacity === 0 ? (
            <EmptyState
              title="No tool changer recorded"
              body="This machine's changer capacity is zero, so there are no pockets to map. Set the capacity on the machine record first."
            />
          ) : (
            <Panel title="Pockets" dense>
              {/* Cell borders rather than a gap over a coloured container:
                  a short final row would otherwise leave the container's own
                  colour showing as a phantom highlighted pocket that does not
                  exist on the machine. */}
              <div className="grid sm:grid-cols-2 lg:grid-cols-3">
                {pockets.map((p) => {
                  const t = byPocket.get(p);
                  return (
                    <div key={p} className="border-b border-line px-3 py-2.5 sm:border-r">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-mono text-[11px] tracking-[0.12em] text-precision tabular-nums">
                          P{String(p).padStart(2, "0")}
                        </span>
                        {t && (
                          <span className="font-mono text-[11px] text-platinum-dim tabular-nums">T{t.toolNumber}</span>
                        )}
                      </div>

                      {t ? (
                        <>
                          <p className="mt-1 text-[12px] leading-snug text-platinum">{t.description}</p>
                          <p className="mt-0.5 font-mono text-[10.5px] text-muted tabular-nums">
                            ⌀{t.diameter} · {t.flutes}FL · stickout {t.stickout.toFixed(3)}
                          </p>
                          <form action={unloadTool} className="mt-1.5">
                            <input type="hidden" name="toolId" value={t.id} />
                            <input type="hidden" name="machineId" value={machine.id} />
                            <Button type="submit" size="sm" variant="ghost">
                              Unload
                            </Button>
                          </form>
                        </>
                      ) : (
                        <form action={loadTool} className="mt-1.5 flex items-center gap-1.5">
                          <input type="hidden" name="machineId" value={machine.id} />
                          <input type="hidden" name="pocket" value={p} />
                          <select name="toolId" required className={`${inputClass} py-1 text-[11px]`} defaultValue="">
                            <option value="" disabled>
                              Empty
                            </option>
                            {unassigned.map((u) => (
                              <option key={u.id} value={u.id}>
                                T{u.toolNumber} — {u.description}
                              </option>
                            ))}
                          </select>
                          <Button type="submit" size="sm">
                            Load
                          </Button>
                        </form>
                      )}
                    </div>
                  );
                })}
              </div>
            </Panel>
          )}

          {inMachineNoPocket.length > 0 && (
            <Notice tone="review" title={`${inMachineNoPocket.length} tools assigned to this machine with no pocket`}>
              {inMachineNoPocket.map((t) => `T${t.toolNumber}`).join(", ")} are recorded as being in this machine
              without a pocket number. They are shown here rather than hidden — give them a pocket, or unload them.
            </Notice>
          )}

          <Notice tone="review" title="This does not yet gate readiness">
            TOOL AVAILABILITY currently passes when a part has tools assigned from the crib, and it still does — this
            page records where the tools are, it does not yet decide whether a job can run. Making the gate require the
            tooling to be loaded in the assigned machine would start failing parts that pass today, which is a decision
            about how your shop works rather than one to slip in behind a schema change.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

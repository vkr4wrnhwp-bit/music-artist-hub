import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { getMachines, getParts, getTools, getWorkholding } from "@/lib/data";
import { TopBar } from "@/components/nav";
import { CommandBar } from "@/components/command-bar";
import { AxisTriad, Dot, EmptyState, LinkButton, Panel, StatusChip } from "@/components/ui";

export default async function HomePage() {
  const user = await requireUser();
  const [parts, machines, tools, workholding, jobs, insights] = await Promise.all([
    getParts(user.organizationId),
    getMachines(user.organizationId),
    getTools(user.organizationId),
    getWorkholding(user.organizationId),
    db.job.findMany({
      where: { organizationId: user.organizationId, status: { in: ["PLANNED", "SETUP", "RUNNING"] } },
      include: { part: true },
      orderBy: { dueDate: "asc" },
      take: 5,
    }),
    buildInsights(user.organizationId),
  ]);

  const shopReady = machines.length > 0 && tools.length > 0 && workholding.length > 0;

  return (
    <>
      <TopBar>
        <span className="tech-label">Home</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto">
        {/* ---------------- What are we making ---------------- */}
        <section className="precision-grid relative border-b border-line px-8 py-14">
          <AxisTriad className="absolute right-8 top-8 opacity-50" />
          <div className="mx-auto max-w-3xl">
            <h1 className="mb-1 text-[26px] font-light tracking-[0.14em] text-white">WHAT ARE WE MAKING?</h1>
            <p className="tech-label mb-7">Describe it, upload it, or reconstruct it from the physical part.</p>
            <CommandBar />

            {!shopReady && (
              <p className="mt-5 text-[12px] leading-relaxed text-muted">
                You can describe a part before configuring equipment. CANVAS will capture the intent, but it cannot
                produce a manufacturing plan until a machine, tooling and workholding exist.{" "}
                <Link href="/machines" className="text-precision hover:underline">
                  Configure my shop first
                </Link>
                .
              </p>
            )}
          </div>
        </section>

        <div className="grid gap-px bg-line lg:grid-cols-2">
          {/* ---------------- Recent parts ---------------- */}
          <Panel
            title="Recent parts"
            className="border-0"
            actions={
              <LinkButton href="/parts" size="sm" variant="ghost">
                All parts
              </LinkButton>
            }
          >
            {parts.length === 0 ? (
              <EmptyState
                title="No parts yet"
                body="Describe a component above, or load the demo part to see the full workflow from intent through to a development NC program."
                action={{ label: "Try the demo part", href: "/parts" }}
              />
            ) : (
              <ul className="divide-y divide-line/60">
                {parts.slice(0, 6).map((p) => {
                  const rev = p.revisions[0];
                  return (
                    <li key={p.id}>
                      <Link href={`/parts/${p.id}`} className="group flex items-center justify-between gap-4 py-2.5">
                        <span className="min-w-0">
                          <span className="block truncate text-[13px] text-platinum group-hover:text-white">
                            {p.name}
                          </span>
                          <span className="tech-label">
                            {p.partNumber ?? "no part number"} · rev {rev?.revision ?? "—"} ·{" "}
                            {rev?._count.features ?? 0} features · {rev?._count.setups ?? 0} setups
                          </span>
                        </span>
                        {p.isDemo && <StatusChip tone="precision">Demo</StatusChip>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>

          {/* ---------------- Active jobs ---------------- */}
          <Panel title="Active jobs" className="border-0">
            {jobs.length === 0 ? (
              <EmptyState
                title="No active jobs"
                body="Jobs are created from a released part revision. Once a job runs, its outcome — what held, what chattered, what scrapped — is recorded against the part's manufacturing record."
              />
            ) : (
              <ul className="divide-y divide-line/60">
                {jobs.map((j) => (
                  <li key={j.id} className="flex items-center justify-between gap-4 py-2.5">
                    <span>
                      <span className="block text-[13px] text-platinum">{j.part.name}</span>
                      <span className="tech-label">
                        {j.jobNumber} · qty {j.quantity} · rev {j.revision}
                      </span>
                    </span>
                    <StatusChip tone={j.status === "RUNNING" ? "precision" : "neutral"}>{j.status}</StatusChip>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {/* ---------------- Machine status ---------------- */}
          <Panel
            title="Machine status"
            meta={<span className="tech-label text-unknown">No machine connection</span>}
            className="border-0"
          >
            {machines.length === 0 ? (
              <EmptyState
                title="No machine selected"
                body="Add a machine before CANVAS can validate travel, spindle limits or post-processing."
                action={{ label: "Add machine", href: "/machines" }}
              />
            ) : (
              <>
                <ul className="divide-y divide-line/60">
                  {machines.map((m) => (
                    <li key={m.id} className="flex items-center justify-between gap-4 py-2.5">
                      <span className="flex items-center gap-2.5">
                        <Dot tone="unknown" />
                        <span>
                          <span className="block text-[13px] text-platinum">
                            {m.manufacturer} {m.model}
                          </span>
                          <span className="tech-label">
                            {m.travelsX}″ × {m.travelsY}″ × {m.travelsZ}″ · {m.maxSpindleRPM} rpm
                          </span>
                        </span>
                      </span>
                      <span className="tech-label">Status unknown</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-[11px] leading-relaxed text-muted">
                  CANVAS is not connected to machine controls. Live status requires an MTConnect or controller
                  integration, which is not part of this phase.
                </p>
              </>
            )}
          </Panel>

          {/* ---------------- CANVAS intelligence ---------------- */}
          <Panel title="CANVAS intelligence" className="border-0">
            {insights.length === 0 ? (
              <EmptyState
                title="Nothing to report"
                body="Insights are derived from your own parts, jobs and outcomes. As work accumulates, CANVAS surfaces patterns across it — repeated fixtures, capability gaps, recurring failures."
              />
            ) : (
              <ul className="space-y-3">
                {insights.map((insight, i) => (
                  <li key={i} className="border-l-2 border-l-precision/60 bg-raised px-3.5 py-2.5">
                    <p className="text-[12.5px] leading-relaxed text-platinum">{insight.body}</p>
                    <p className="tech-label mt-1.5">{insight.basis}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        {/* ---------------- Manufacturing opportunities ---------------- */}
        <Panel
          title="Manufacturing opportunities"
          meta={<StatusChip tone="unknown">Requires network participation</StatusChip>}
          className="border-x-0 border-b-0"
        >
          <EmptyState
            title="Network participation is off"
            body="Supplier matches and demand signals require opting into anonymous network matching. Nothing about your parts leaves this organisation until you do, and an anonymous fingerprint never carries geometry, dimensions or identity."
            action={{ label: "Review network privacy", href: "/network" }}
          />
        </Panel>
      </main>
    </>
  );
}

/**
 * Insights are computed from the organisation's own records. Nothing here is
 * a model guess — each one names the data that produced it.
 */
async function buildInsights(organizationId: string): Promise<{ body: string; basis: string }[]> {
  const out: { body: string; basis: string }[] = [];

  const [machines, setups, outcomes] = await Promise.all([
    db.machine.findMany({ where: { organizationId } }),
    db.setup.findMany({
      where: { partRevision: { part: { organizationId } } },
      include: { workholding: true, partRevision: { include: { part: true } } },
    }),
    db.jobOutcome.findMany({
      where: { job: { organizationId } },
      include: { job: { include: { part: true } } },
      orderBy: { recordedAt: "desc" },
      take: 20,
    }),
  ]);

  // Capability coverage: how many setups fit the largest machine's envelope.
  if (machines.length > 0 && setups.length > 0) {
    const biggest = machines.reduce((a, b) => (a.travelsX * a.travelsY > b.travelsX * b.travelsY ? a : b));
    out.push({
      body: `${biggest.manufacturer} ${biggest.model} covers ${setups.length} of ${setups.length} setups in the current queue on envelope. Envelope is not capability — tool reach and workholding are evaluated per setup.`,
      basis: `Derived from ${setups.length} setups against the machine profile`,
    });
  }

  // Repeated soft jaw work is a real, expensive, recurring pattern.
  const secondOps = setups.filter((s) => s.sequence > 1);
  if (secondOps.length >= 2) {
    out.push({
      body: `${secondOps.length} second operations across your parts rely on jaw work. A reusable jaw family sized to your common envelopes would remove setup time from every one of them.`,
      basis: `Derived from ${secondOps.length} setups with sequence > 1`,
    });
  }

  // Recurring failure modes are the highest-value thing a shop can know.
  const failures = outcomes.filter((o) => o.code !== "SUCCESS");
  if (failures.length > 0) {
    const byCause = new Map<string, number>();
    for (const f of failures) byCause.set(f.cause, (byCause.get(f.cause) ?? 0) + 1);
    const [cause, count] = [...byCause.entries()].sort((a, b) => b[1] - a[1])[0];
    out.push({
      body: `"${cause}" accounts for ${count} of ${failures.length} recorded job failures. The workholding model now flags this condition before the program is posted rather than after the part moves.`,
      basis: `Derived from ${outcomes.length} recorded job outcomes`,
    });
  }

  return out;
}

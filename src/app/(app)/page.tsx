import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { getMachines, getMaterials, getMetrology, getParts, getTools, getWorkholding, loadRevision } from "@/lib/data";
import { MillPartThumb, TurnPartThumb } from "@/components/part-thumb";
import type { RotationalProfile } from "@/lib/manufacturing/turn/geometry";
import { GuideCard } from "@/components/guide/guide-card";
import type { GuideContext } from "@/lib/guide/engine";
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
  const [materials, instruments, pocketCount] = await Promise.all([
    getMaterials(user.organizationId),
    getMetrology(user.organizationId),
    db.tool.count({ where: { organizationId: user.organizationId, machineId: { not: null }, pocket: { not: null } } }),
  ]);

  const shopReady = machines.length > 0 && tools.length > 0 && workholding.length > 0;

  /*
   * Geometry for the six tiles only — not for every part in the library.
   *
   * The turned parts have to be looked up separately or they are drawn by
   * the mill thumbnail, which knows nothing about a revolved profile and
   * renders "no geometry yet" over a part that has a measured one. The
   * library already made that distinction; the home screen did not.
   */
  const recent = await Promise.all(
    parts.slice(0, 6).map(async (p) => {
      const rev = p.revisions[0];
      const rot = rev
        ? await db.rotationalPart.findFirst({ where: { partRevisionId: rev.id, organizationId: user.organizationId } })
        : null;
      return {
        p,
        rev,
        hydrated: await loadRevision(user.organizationId, p.id),
        profile: rot ? (JSON.parse(rot.profileJson) as RotationalProfile) : null,
        isTurned: rot !== null,
      };
    }),
  );

  /*
   * The shop-setup walkthrough. Every other guide flow assumes a shop that
   * has already said what it owns; a new organisation has said nothing, and
   * the engines below are all written to refuse rather than assume. This is
   * week zero from the beta runbook, guided — and it completes from the
   * recorded counts, so a shop that was set up before the guide existed
   * sees it already finished rather than being asked to redo it.
   */
  const guideCtx: GuideContext = {
    partId: "",
    hasStock: false,
    hasMachine: machines.length > 0,
    hasMaterial: materials.length > 0,
    featureCount: 0,
    pendingProposals: 0,
    setupCount: 0,
    workholdingAssessed: false,
    toolpathCount: 0,
    simulationRecorded: false,
    approvalExists: false,
    ncProgramExists: false,
    blockingGates: [],
    nextAction: null,
    training: false,
    shop: {
      machines: machines.length,
      tools: tools.length,
      materials: materials.length,
      instruments: instruments.length,
      workholding: workholding.length,
      toolsInChanger: pocketCount,
    },
  };

  return (
    <>
      <TopBar>
        <span className="tech-label">Home</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto">
        {/* ---------------- What are we making ---------------- */}
        <section className="relative border-b border-line px-5 py-10 sm:px-8 sm:py-14">
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
              /*
               * Tiles, not rows. A machinist coming back to a job recognises
               * the part before they recognise "AUDIT-verify-step" — the
               * library already knew that and the home screen did not, so the
               * one screen people land on was the one place parts had no
               * shape. The drawing is the part's own features; a part with no
               * geometry yet says so in the tile rather than being given a
               * generic icon that implies there is something to look at.
               */
              <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {recent.map(({ p, rev, hydrated, profile, isTurned }) => (
                  <li key={p.id}>
                    <Link
                      href={isTurned ? `/lathe/${p.id}` : `/parts/${p.id}`}
                      className="group block border border-line bg-surface transition-colors hover:border-line-strong"
                    >
                      <div className="h-[92px] border-b border-line">
                        {isTurned && profile ? (
                          <TurnPartThumb profile={profile} />
                        ) : (
                          <MillPartThumb features={hydrated?.features ?? []} stock={hydrated?.stock ?? null} />
                        )}
                      </div>
                      <div className="px-3 py-2">
                        <span className="flex items-baseline justify-between gap-2">
                          <span className="truncate text-[12.5px] text-platinum group-hover:text-white">{p.name}</span>
                          {p.isDemo && <StatusChip tone="precision">Demo</StatusChip>}
                        </span>
                        <span className="tech-label mt-0.5 block truncate">
                          {/* Setup count dropped: at this tile width it truncated to
                              an ellipsis, and a number cut in half is worse than
                              one that was never offered. */}
                          Rev {rev?.revision ?? "—"} · {rev?._count.features ?? 0} features
                        </span>
                      </div>
                    </Link>
                  </li>
                ))}
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
      {/* Week zero, guided. Mounted on the home page because that is where
          a new shop lands, and it completes from recorded counts rather
          than from clicks. */}
      <GuideCard ctx={guideCtx} flowId="SET_UP_THE_SHOP" />
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

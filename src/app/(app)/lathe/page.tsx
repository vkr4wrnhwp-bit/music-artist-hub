import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { DevLabel, EmptyState, Panel, SectionHeading, StatusChip } from "@/components/ui";
import { PROCESS_SUPPORT } from "@/lib/manufacturing/process";

/** TURNING — the lathe library: rotational parts, machines, workholding, tools. */
export default async function LathePage() {
  const user = await requireUser();
  const [rotational, lathes, holding, tools] = await Promise.all([
    db.rotationalPart.findMany({ where: { organizationId: user.organizationId }, orderBy: { createdAt: "desc" } }),
    db.latheMachine.findMany({ where: { organizationId: user.organizationId } }),
    db.latheWorkholding.findMany({ where: { organizationId: user.organizationId } }),
    db.turningTool.findMany({ where: { organizationId: user.organizationId }, orderBy: { station: "asc" } }),
  ]);
  const revisions = await db.partRevision.findMany({
    where: { id: { in: rotational.map((r) => r.partRevisionId) } },
    include: { part: true },
  });

  return (
    <>
      <TopBar>
        <span className="tech-label">Turning</span>
        <DevLabel>TURN_2_AXIS</DevLabel>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          <SectionHeading sub="2-axis turning is a first-class CANVAS process: rotational X/Z geometry, chuck and collet workholding, deterministic turning toolpaths, worst-gate readiness and a development lathe post. Live tooling and mill-turn exist as architecture only and say DEVELOPMENT wherever they appear.">
            Turning
          </SectionHeading>

          <Panel title="Rotational parts" dense>
            {rotational.length === 0 ? (
              <EmptyState title="No turned parts" body="The demo shaft appears here after seeding." />
            ) : (
              <ul>
                {rotational.map((r) => {
                  const rev = revisions.find((x) => x.id === r.partRevisionId);
                  return (
                    <li key={r.id} className="border-b border-line/60 last:border-0">
                      <Link href={`/lathe/${rev?.part.id}`} className="flex items-center justify-between px-4 py-2.5 hover:bg-raised">
                        <span className="text-[13px] text-platinum">{rev?.part.name ?? "Part"}</span>
                        <span className="font-mono text-[11px] text-muted">{rev?.part.partNumber ?? ""}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>

          <div className="grid gap-4 lg:grid-cols-3">
            <Panel title={`Lathes — ${lathes.length}`} dense>
              <ul>
                {lathes.map((m) => (
                  <li key={m.id} className="border-b border-line/60 px-4 py-2 last:border-0">
                    <p className="text-[12.5px] text-platinum">{m.manufacturer} {m.model}</p>
                    <p className="font-mono text-[10.5px] text-muted tabular-nums">
                      ⌀{m.maxTurningDiameter}×{m.maxTurningLength} · {m.maxRPM} RPM · {m.turretStations} stations
                    </p>
                    {m.isReferenceProfile && <DevLabel>Reference</DevLabel>}
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title={`Workholding — ${holding.length}`} dense>
              <ul>
                {holding.map((w) => (
                  <li key={w.id} className="border-b border-line/60 px-4 py-2 last:border-0">
                    <p className="text-[12.5px] text-platinum">{w.description}</p>
                    <p className="font-mono text-[10.5px] text-muted">
                      {w.maxRPM ? `${w.maxRPM} RPM limit` : "RPM limit not recorded"}
                      {w.maxClampForceLbf == null && w.type.includes("CHUCK") ? " · clamp force not recorded" : ""}
                    </p>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title={`Turning tools — ${tools.length}`} dense>
              <ul>
                {tools.map((t) => (
                  <li key={t.id} className="flex items-baseline gap-2 border-b border-line/60 px-4 py-2 last:border-0">
                    <span className="font-mono text-[11px] text-precision-dim">T{t.station}</span>
                    <span className="min-w-0 flex-1 truncate text-[12px] text-platinum-dim">{t.description}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>

          <Panel title="Process support" dense>
            <ul>
              {(["TURN_2_AXIS", "TURN_LIVE_TOOLING", "MILL_TURN", "SWISS"] as const).map((proc) => (
                <li key={proc} className="flex items-center justify-between border-b border-line/60 px-4 py-2 last:border-0">
                  <span className="font-mono text-[12px] text-platinum-dim">{proc}</span>
                  <StatusChip tone={PROCESS_SUPPORT[proc] === "REAL" ? "pass" : PROCESS_SUPPORT[proc] === "DEVELOPMENT" ? "review" : "neutral"}>
                    {PROCESS_SUPPORT[proc]}
                  </StatusChip>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

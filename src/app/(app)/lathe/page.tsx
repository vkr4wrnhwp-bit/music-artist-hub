import Link from "next/link";
import { redirect } from "next/navigation";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { TopBar } from "@/components/nav";
import { Button, DevLabel, EmptyState, Panel, SectionHeading, StatusChip, inputClass } from "@/components/ui";
import { PROCESS_SUPPORT } from "@/lib/manufacturing/process";
import { TurnPartThumb } from "@/components/part-thumb";
import { LibraryView } from "@/components/library-view";
import type { RotationalProfile } from "@/lib/manufacturing/turn/geometry";

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

  async function startReverse(formData: FormData) {
    "use server";
    const u = await requireWrite();
    const name = String(formData.get("name") ?? "").trim();
    if (!name) redirect("/lathe");
    const part = await db.part.create({
      data: {
        organizationId: u.organizationId,
        name,
        description: "Reverse engineered from bench measurement",
        revisions: {
          create: {
            revision: "A",
            status: "DRAFT",
            units: "IN",
            intentJson: JSON.stringify({
              partName: { value: name, source: "USER", confidence: "VERIFIED", confirmedByUser: true },
              unknowns: ["Reconstructed from measurement — every dimension requires confirmation"],
              confidence: 0.1,
            }),
            responsibility: { create: {} },
          },
        },
      },
      include: { revisions: true },
    });
    const rot = await db.rotationalPart.create({
      data: {
        partRevisionId: part.revisions[0].id,
        organizationId: u.organizationId,
        profileJson: JSON.stringify({ units: "IN", zZeroReference: "measured datum face", stockDiameter: 0, stockLength: 0, barStock: true, segments: [] }),
      },
    });
    await audit({
      organizationId: u.organizationId, userId: u.id, entityType: "RotationalPart", entityId: rot.id,
      action: "CREATE", actorType: "HUMAN", field: "reverse engineering",
      newValue: name, reason: "Rotational part started from bench measurement.",
    });
    redirect(`/lathe/${part.id}/reverse`);
  }

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

          {rotational.length === 0 ? (
            <EmptyState title="No turned parts" body="The demo shaft appears here after seeding." />
          ) : (
            <LibraryView
              storageKey="canvas.latheView"
              grid={
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {rotational.map((r) => {
                    const rev = revisions.find((x) => x.id === r.partRevisionId);
                    let profile: RotationalProfile | null = null;
                    try {
                      profile = JSON.parse(r.profileJson) as RotationalProfile;
                    } catch {
                      profile = null;
                    }
                    const next =
                      !profile || profile.segments.length === 0
                        ? "Measure the profile"
                        : r.clampForceLbf === null
                          ? "Record clamp force"
                          : r.humanApproved
                            ? "Open workspace"
                            : "Review and approve";
                    return (
                      <Link
                        key={r.id}
                        href={`/lathe/${rev?.part.id}`}
                        className="group block border border-line bg-surface transition-colors hover:border-line-strong"
                      >
                        <div className="h-[120px] border-b border-line">
                          {profile ? (
                            <TurnPartThumb profile={profile} />
                          ) : (
                            <div className="flex h-full items-center justify-center text-[10px] uppercase tracking-[0.14em] text-muted">no profile yet</div>
                          )}
                        </div>
                        <div className="px-3.5 py-2.5">
                          <p className="truncate text-[13px] text-platinum group-hover:text-white">{rev?.part.name ?? "Part"}</p>
                          <p className="tech-label mt-0.5">{rev?.part.partNumber ?? "—"}{profile ? ` · ⌀${profile.stockDiameter.toFixed(2)} × ${profile.stockLength.toFixed(1)}″ bar` : ""}</p>
                          <div className="mt-2 flex items-center justify-between gap-2">
                            <StatusChip tone={r.humanApproved ? "pass" : "review"}>{r.humanApproved ? "APPROVED" : "REVIEW REQUIRED"}</StatusChip>
                            <span className="tech-label truncate text-right">{next}</span>
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              }
              table={
                <Panel title="Rotational parts" dense>
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
                </Panel>
              }
            />
          )}

          <Panel title="Reverse engineer a shaft" meta={<span className="font-mono text-[10.5px] text-muted">GUIDED</span>}>
            <p className="mb-2 text-[11.5px] leading-relaxed text-muted">
              Measure a turned part on the bench, front to back, with the instrument named per reading. CANVAS assembles the profile with MEASURED provenance and suggests standard nominals; it never rounds a reading for you.
            </p>
            <form action={startReverse} className="flex items-end gap-3">
              <label className="block">
                <span className="tech-label mb-1 block">Part name</span>
                <input name="name" placeholder="e.g. Idler shaft (worn)" className={`${inputClass} w-64`} />
              </label>
              <Button type="submit">Start measuring</Button>
            </form>
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

import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { getParts, loadRevision } from "@/lib/data";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { MillPartThumb, TurnPartThumb } from "@/components/part-thumb";
import { LibraryView } from "@/components/library-view";
import { EmptyState, LinkButton, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";
import type { RotationalProfile } from "@/lib/manufacturing/turn/geometry";

/**
 * PART LIBRARY — visual by default. Tiles carry real geometry (top-view
 * drawing from the part's own features; profile silhouette for turned
 * parts), a compact status, and a concise next action. The table survives
 * for power users, one toggle away, preference persisted.
 */

export default async function PartLibraryPage() {
  const user = await requireUser();
  const parts = await getParts(user.organizationId);

  // Tile data: hydrated features + stock per part, and the rotational
  // profile where one exists. Parts are few; this stays cheap.
  const tiles = await Promise.all(
    parts.map(async (p) => {
      const rev = p.revisions[0];
      const hydrated = await loadRevision(user.organizationId, p.id);
      const rot = rev
        ? await db.rotationalPart.findFirst({ where: { partRevisionId: rev.id, organizationId: user.organizationId } })
        : null;
      const profile = rot ? (JSON.parse(rot.profileJson) as RotationalProfile) : null;
      const material = hydrated?.intent.material.value ?? null;
      const next =
        rot !== null
          ? profile && profile.segments.length > 0
            ? "Open the turning workspace"
            : "Measure the profile"
          : !hydrated || hydrated.features.length === 0
            ? "Add geometry"
            : !hydrated.stock
              ? "Define stock"
              : (rev?._count.setups ?? 0) === 0
                ? "Pick an approach"
                : "Open workspace";
      return { p, rev, hydrated, profile, isTurned: rot !== null, material, next };
    }),
  );

  const grid = (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {tiles.map(({ p, rev, hydrated, profile, isTurned, material, next }) => (
        <Link
          key={p.id}
          href={isTurned ? `/lathe/${p.id}` : `/parts/${p.id}`}
          className="group block border border-line bg-surface transition-colors hover:border-line-strong"
        >
          <div className="h-[120px] border-b border-line">
            {isTurned && profile ? (
              <TurnPartThumb profile={profile} />
            ) : (
              <MillPartThumb features={hydrated?.features ?? []} stock={hydrated?.stock ?? null} />
            )}
          </div>
          <div className="px-3.5 py-2.5">
            <p className="truncate text-[13px] text-platinum group-hover:text-white">{p.name}</p>
            <p className="tech-label mt-0.5">
              {p.partNumber ?? "—"} · Rev {rev?.revision ?? "—"}
              {material ? ` · ${material}` : ""}
            </p>
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5">
                {p.training ? (
                  <StatusChip tone="precision">TRAINING</StatusChip>
                ) : (
                  <StatusChip tone={rev?.status === "RELEASED" ? "pass" : "neutral"}>{rev?.status ?? "DRAFT"}</StatusChip>
                )}
                {isTurned && <StatusChip tone="neutral">TURNED</StatusChip>}
              </span>
              <span className="tech-label truncate text-right">{next}</span>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );

  const table = (
    <Panel title={`${parts.length} parts`} dense>
      <Table head={["Part", "Number", "Rev", "Status", "Features", "Setups", "Sharing", "Updated"]}>
        {parts.map((p) => {
          const rev = p.revisions[0];
          return (
            <tr key={p.id} className="hover:bg-raised">
              <Td>
                <Link href={`/parts/${p.id}`} className="text-platinum hover:text-white">
                  {p.name}
                </Link>
                {p.isDemo && <span className="ml-2 text-[10px] uppercase tracking-[0.12em] text-precision">demo</span>}
              </Td>
              <Td muted>{p.partNumber ?? "—"}</Td>
              <Td>{rev?.revision ?? "—"}</Td>
              <Td muted>{rev?.status ?? "—"}</Td>
              <Td>{rev?._count.features ?? 0}</Td>
              <Td>{rev?._count.setups ?? 0}</Td>
              <Td>
                <StatusChip tone={p.sharing === "PRIVATE" ? "neutral" : "review"}>{p.sharing}</StatusChip>
              </Td>
              <Td muted>{p.updatedAt.toISOString().slice(0, 10)}</Td>
            </tr>
          );
        })}
      </Table>
    </Panel>
  );

  return (
    <>
      <TopBar>
        <span className="tech-label">Part library</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="flex items-start justify-between gap-6">
          <SectionHeading sub="Every part is revision-controlled. A revision carries its own intent model, geometry, setups, inspection plan and cost estimate, so a change to Rev B never rewrites what Rev A was actually built to.">
            Part library
          </SectionHeading>
          <LinkButton href="/parts/new" variant="primary" size="sm">
            New part
          </LinkButton>
        </div>

        {parts.length === 0 ? (
          <EmptyState
            title="No parts"
            body="Describe a component from the home screen, import a drawing, or start from the physical part in Reverse Engineer."
            action={{ label: "Describe a part", href: "/parts/new" }}
          />
        ) : (
          <LibraryView storageKey="canvas.partsView" grid={grid} table={table} />
        )}
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

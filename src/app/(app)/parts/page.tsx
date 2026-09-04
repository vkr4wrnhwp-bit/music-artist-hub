import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { getPartPhotos, getParts, loadRevision } from "@/lib/data";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { MillPartThumb, PartPhotoThumb, PartThumbEmpty, TurnPartThumb } from "@/components/part-thumb";
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
  const photos = await getPartPhotos(user.organizationId, parts.map((p) => p.id));
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
      /*
       * Which of the four pictures this tile gets. Decided once, here,
       * because the caption below the tile has to know: an empty tile
       * already carries the next action in 9px caps across its middle, and
       * repeating it in the corner is the same sentence twice.
       */
      const photo = photos.get(p.id) ?? null;
      const art =
        rot !== null && profile && profile.segments.length > 0
          ? "profile"
          : (hydrated?.features.length ?? 0) > 0
            ? "drawing"
            : photo
              ? "photo"
              : "action";
      /*
       * THREE WEIGHTS, NOT TWELVE EQUAL CARDS.
       *
       * The grid gave a released part and an empty stub the same border, the
       * same size and the same everything, with status as the quietest
       * element on the card — and finding the released ones is the one thing
       * a shop scans this page for.
       *
       * The stage is derived from what is already loaded. It is NOT a
       * readiness verdict: readiness is gate-based and costs a package build
       * per part, and a green stripe that had not actually run the gates
       * would be the worst thing this grid could show. RELEASED means a human
       * approved the revision, which is a fact the row already holds.
       */
      const stage =
        rev?.status === "RELEASED" ? "released" : (hydrated?.features.length ?? 0) > 0 || rot !== null ? "working" : "stub";
      return { p, rev, hydrated, profile, isTurned: rot !== null, material, next, photo, art, stage };
    }),
  );

  const grid = (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {tiles.map(({ p, rev, hydrated, profile, isTurned, material, next, photo, art, stage }) => (
        <Link
          key={p.id}
          href={isTurned ? `/lathe/${p.id}` : `/parts/${p.id}`}
          className={`group block border bg-surface transition-colors hover:border-line-strong ${
            stage === "released"
              ? "border-line border-l-2 border-l-pass"
              : stage === "stub"
                ? "border-line/60"
                : "border-line"
          }`}
        >
          <div className="h-[120px] border-b border-line">
            {/*
              Geometry first, then a photograph of the real part labelled as
              one, then the action that would fill the slot — `next` is
              already computed above, so an empty tile says the same thing
              the row under it says.
            */}
            {art === "profile" && profile ? (
              <TurnPartThumb profile={profile} />
            ) : art === "drawing" ? (
              <MillPartThumb features={hydrated?.features ?? []} stock={hydrated?.stock ?? null} />
            ) : art === "photo" && photo ? (
              <PartPhotoThumb src={`/api/assets/${encodeURIComponent(photo)}`} alt={`Photograph of ${p.name}`} />
            ) : (
              <PartThumbEmpty stock={hydrated?.stock ?? null} action={next} />
            )}
          </div>
          <div className="px-3.5 py-2.5">
            {/* A stub's name recedes: it is a placeholder for a part, not a part. */}
            <p
              className={`truncate text-[13px] group-hover:text-white ${
                stage === "stub" ? "text-muted" : "text-platinum"
              }`}
            >
              {p.name}
            </p>
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
              {art !== "action" && <span className="tech-label truncate text-right">{next}</span>}
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

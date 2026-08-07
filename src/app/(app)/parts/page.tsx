import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { getParts } from "@/lib/data";
import { TopBar } from "@/components/nav";
import { EmptyState, LinkButton, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

export default async function PartLibraryPage() {
  const user = await requireUser();
  const parts = await getParts(user.organizationId);

  return (
    <>
      <TopBar>
        <span className="tech-label">Part library</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-6">
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
        )}
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

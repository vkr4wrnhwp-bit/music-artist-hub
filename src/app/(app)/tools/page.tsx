import { requireUser } from "@/lib/auth";
import { getTools } from "@/lib/data";
import { fmt } from "@/lib/domain/features";
import { TopBar } from "@/components/nav";
import Link from "next/link";
import { EmptyState, LinkButton, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

export default async function ToolCribPage() {
  const user = await requireUser();
  const tools = await getTools(user.organizationId);

  return (
    <>
      <TopBar>
        <span className="tech-label">Tool crib</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <SectionHeading sub="Tool geometry drives what CANVAS will and will not plan. Corner radius decides whether an internal corner is machinable at all; stickout decides whether a depth is reachable. A tool that is not in the crib does not exist to the planner.">
            Tool crib
          </SectionHeading>
          <div className="shrink-0 pt-1">
            <LinkButton href="/tools/new" size="sm" variant="primary">
              Add tool
            </LinkButton>
          </div>
        </div>

        {tools.length === 0 ? (
          <EmptyState
            title="Tool crib is empty"
            body="CANVAS cannot select tooling, derive speeds and feeds, or validate feature access until tools are defined."
            action={{ label: "Add tool", href: "/tools/new" }}
          />
        ) : (
          <div data-guide-target="tool-crib">
          <Panel title={`${tools.length} tools`} dense>
            <Table head={["T#", "Class", "Description", "⌀", "Flutes", "Reach", "Chipload", "SFM", "Holder", "Life", ""]}>
              {tools.map((t) => (
                <tr key={t.id} className="hover:bg-raised">
                  <Td className="text-precision">T{t.toolNumber}</Td>
                  <Td muted>{t.toolClass.replace(/_/g, " ").toLowerCase()}</Td>
                  <Td>{t.description}</Td>
                  <Td>{fmt(t.diameter, 4)}</Td>
                  <Td>{t.flutes}</Td>
                  <Td>{t.stickout.toFixed(2)}″</Td>
                  <Td muted>
                    {t.chiploadMin.toFixed(4)}–{t.chiploadMax.toFixed(4)}
                  </Td>
                  <Td muted>
                    {t.sfmMin}–{t.sfmMax}
                  </Td>
                  <Td muted>{t.holder}</Td>
                  <Td>
                    <StatusChip tone={t.lifeRemaining > 0.4 ? "pass" : t.lifeRemaining > 0.15 ? "review" : "risk"}>
                      {(t.lifeRemaining * 100).toFixed(0)}%
                    </StatusChip>
                  </Td>
                  <Td>
                    <Link
                      href={`/tools/${t.id}/edit`}
                      className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted hover:text-precision"
                    >
                      Edit
                    </Link>
                  </Td>
                </tr>
              ))}
            </Table>
          </Panel>
          </div>
        )}
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

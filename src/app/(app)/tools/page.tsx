import { requireUser } from "@/lib/auth";
import { getTools } from "@/lib/data";
import { toolLife, formatMinutes, type ToolLife, type ToolLifeState } from "@/lib/engines/tool-life";
import { db } from "@/lib/db";
import { fmt } from "@/lib/domain/features";
import { TopBar } from "@/components/nav";
import Link from "next/link";
import { EmptyState, LinkButton, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

/*
 * UNTRACKED is not a warning. A tool with no expected life recorded is a
 * missing input, not a worn cutter, and colouring it as risk would be the
 * same lie in the other direction.
 */
const LIFE_TONE: Record<ToolLifeState, "pass" | "review" | "risk" | "unknown"> = {
  UNTRACKED: "unknown",
  FRESH: "pass",
  IN_USE: "pass",
  NEAR_END: "review",
  PAST_EXPECTED: "risk",
};

/*
 * A tool charged a real fraction of a minute must not read 0% — "0% used" and
 * "unused" are the same sentence to a machinist glancing down a column, and one
 * of them is false. Anything counted but below a whole percent reads as such.
 */
const LIFE_LABEL = (l: ToolLife): string => {
  if (l.state === "UNTRACKED") return l.minutesUsed > 0 ? `${formatMinutes(l.minutesUsed)} min` : "Not counted";
  if (l.state === "FRESH") return "Unused";
  const pct = l.fractionUsed! * 100;
  return pct < 1 ? "under 1% used" : `${pct.toFixed(0)}% used`;
};

export default async function ToolCribPage() {
  const user = await requireUser();
  const tools = await getTools(user.organizationId);

  // Where each tool physically is. Queried separately rather than widened
  // into the domain Tool type — location is a fact about this shop's
  // machines, not a property of the cutter.
  const placements = await db.tool.findMany({
    where: { organizationId: user.organizationId },
    select: { id: true, pocket: true, machine: { select: { manufacturer: true, model: true } } },
  });
  const locationOf = new Map(
    placements.map((p) => [
      p.id,
      p.machine && p.pocket !== null ? `${p.machine.manufacturer} ${p.machine.model} · P${String(p.pocket).padStart(2, "0")}` : null,
    ]),
  );

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
            <Table head={["T#", "Class", "Description", "⌀", "Flutes", "Reach", "Chipload", "SFM", "Holder", "Loaded in", "Used", ""]}>
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
                  {/* "In the crib" is a real location, not a blank. */}
                  <Td muted={locationOf.get(t.id) == null}>{locationOf.get(t.id) ?? "Crib"}</Td>
                  {/*
                    What the tool has DONE, not a number somebody typed.
                    A 0-1 float nothing ever updated was shown here as a
                    colour-coded percentage, and green at 100% is what a
                    machinist reads as "plenty left".
                  */}
                  <Td>
                    {(() => {
                      const life = toolLife({
                        description: t.description,
                        minutesUsed: t.minutesUsed,
                        partsCut: t.partsCut,
                        expectedLifeMinutes: t.expectedLifeMinutes,
                        lifeCountedFrom: t.lifeCountedFrom ?? null,
                        regrindCount: t.regrindCount,
                      });
                      return (
                        <span title={`${life.summary} ${life.caveat}`}>
                          <StatusChip tone={LIFE_TONE[life.state]}>{LIFE_LABEL(life)}</StatusChip>
                        </span>
                      );
                    })()}
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

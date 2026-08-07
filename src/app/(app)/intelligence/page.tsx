import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { getMachines, getMaterials, getTools, getWorkholding } from "@/lib/data";
import { TopBar } from "@/components/nav";
import { DevLabel, EmptyState, Notice, Panel, SectionHeading, Table, Td } from "@/components/ui";

/**
 * SHOP INTELLIGENCE — shell.
 *
 * What is real here is the capability inventory, computed from the shop's own
 * records. What is not real is opportunity discovery, and the page says so
 * rather than filling the space with plausible-looking suggestions.
 */
export default async function IntelligencePage() {
  const user = await requireUser();
  const [machines, tools, workholding, materials, org, dna] = await Promise.all([
    getMachines(user.organizationId),
    getTools(user.organizationId),
    getWorkholding(user.organizationId),
    getMaterials(user.organizationId),
    db.organization.findUnique({ where: { id: user.organizationId } }),
    db.manufacturingDNA.findMany({
      where: { part: { organizationId: user.organizationId } },
      include: { part: true },
      orderBy: { recordedAt: "desc" },
      take: 10,
    }),
  ]);

  const maxEnvelope = machines.length
    ? machines.reduce((a, b) => (a.travelsX * a.travelsY > b.travelsX * b.travelsY ? a : b))
    : null;
  const smallestTool = tools.length ? tools.reduce((a, b) => (a.diameter < b.diameter ? a : b)) : null;
  const deepestReach = tools.length ? tools.reduce((a, b) => (a.stickout > b.stickout ? a : b)) : null;

  return (
    <>
      <TopBar>
        <span className="tech-label">Shop intelligence</span>
        <DevLabel>Capability inventory real · opportunity discovery not implemented</DevLabel>
      </TopBar>

      <main className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="What your shop can physically make, derived from your machines, tooling, workholding and materials. This is the substrate the opportunity engine will eventually run on — the inventory is real today, the discovery is not.">
            Shop intelligence
          </SectionHeading>

          <Panel title="Capability envelope">
            {machines.length === 0 ? (
              <EmptyState
                title="No machines recorded"
                body="Capability is computed from machine profiles. Add a machine to see what your shop can physically produce."
                action={{ label: "Add machine", href: "/machines" }}
              />
            ) : (
              <div className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
                <Row label="Largest work envelope" value={maxEnvelope ? `${maxEnvelope.travelsX}″ × ${maxEnvelope.travelsY}″ × ${maxEnvelope.travelsZ}″` : "—"} />
                <Row label="Machines" value={`${machines.length}`} />
                <Row label="Max spindle speed" value={`${Math.max(...machines.map((m) => m.maxSpindleRPM))} rpm`} />
                <Row label="Probing" value={machines.some((m) => m.probe) ? "Available" : "None"} />
                <Row label="Smallest internal corner" value={smallestTool ? `R${(smallestTool.diameter / 2).toFixed(4)}` : "—"} />
                <Row label="Deepest tool reach" value={deepestReach ? `${deepestReach.stickout.toFixed(2)}″` : "—"} />
                <Row label="Workholding devices" value={`${workholding.length}`} />
                <Row label="Materials on file" value={`${materials.length}`} />
                <Row label="Typical tolerance" value={org?.typicalTolerance ? `±${org.typicalTolerance}″` : "Not stated"} />
                <Row label="Tools in crib" value={`${tools.length}`} />
              </div>
            )}
          </Panel>

          <Panel title="Manufacturing DNA" dense>
            {dna.length === 0 ? (
              <div className="p-4">
                <p className="text-[12px] leading-relaxed text-muted">
                  No completed jobs have been recorded into the manufacturing record yet. Each completed job writes an
                  immutable snapshot — geometry, setups, tooling, feeds, workholding, measured results, cycle time,
                  scrap and cost — which becomes the shop's institutional memory of how a part was actually made.
                </p>
              </div>
            ) : (
              <Table head={["Part", "Rev", "Actual cost", "Recorded"]}>
                {dna.map((d) => (
                  <tr key={d.id} className="hover:bg-raised">
                    <Td className="text-platinum">{d.part.name}</Td>
                    <Td muted>{d.revision}</Td>
                    <Td>{d.costActual ? `$${d.costActual.toFixed(2)}` : "—"}</Td>
                    <Td muted>{d.recordedAt.toISOString().slice(0, 10)}</Td>
                  </tr>
                ))}
              </Table>
            )}
          </Panel>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Find opportunities" meta={<DevLabel>Not implemented</DevLabel>}>
              <EmptyState
                title="Opportunity discovery is not built"
                body="Evaluating what else your shop could make — internal components to bring in-house, adjacent product categories, network RFQs matched to your capability — requires the network layer and a demand corpus that do not exist in this phase."
              />
            </Panel>

            <Panel title="Company research" meta={<DevLabel>Not implemented</DevLabel>}>
              <EmptyState
                title="No web analysis"
                body="Analysing a company's public information to identify product families and make/buy opportunities requires web tooling that is deliberately not wired up here. Uncontrolled scraping is not something to add quietly."
              />
            </Panel>
          </div>

          <Notice tone="review" title="Why this page is mostly empty">
            Everything above that shows a number computed it from your own records. Everything that shows nothing is
            honest about not being built. A dashboard full of confident-looking suggestions with no data behind them is
            worse than an empty one.
          </Notice>
        </div>
      </main>
    </>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-line/60 py-1.5">
      <span className="tech-label">{label}</span>
      <span className="font-mono text-[12px] text-platinum">{value}</span>
    </div>
  );
}

export const dynamic = "force-dynamic";

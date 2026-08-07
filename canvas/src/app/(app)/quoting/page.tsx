import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { money } from "@/lib/engines/cost";
import { TopBar } from "@/components/nav";
import { EmptyState, Notice, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

export default async function QuotingPage() {
  const user = await requireUser();
  const [quotes, estimates] = await Promise.all([
    db.quote.findMany({
      where: { organizationId: user.organizationId },
      include: { part: true, estimates: true },
      orderBy: { createdAt: "desc" },
    }),
    db.costEstimate.findMany({
      where: { partRevision: { part: { organizationId: user.organizationId } } },
      include: { partRevision: { include: { part: true } } },
      orderBy: { createdAt: "desc" },
      take: 20,
    }),
  ]);

  return (
    <>
      <TopBar>
        <span className="tech-label">Quoting</span>
      </TopBar>
      <main className="flex-1 space-y-6 overflow-y-auto p-6">
        <SectionHeading sub="Quotes carry their assumption set. Machine rate, cycle time, material utilisation, scrap allowance and margin are all stored with the estimate, so a quote can be defended, re-run against changed rates, or compared against what the job actually cost.">
          Quoting
        </SectionHeading>

        {quotes.length === 0 && estimates.length === 0 ? (
          <EmptyState
            title="No quotes"
            body="Cost estimates are generated per part revision from the cost engine. Open a part's Cost panel to produce one, then attach it to a quote."
            action={{ label: "Part library", href: "/parts" }}
          />
        ) : (
          <>
            {quotes.length > 0 && (
              <Panel title="Quotes" dense>
                <Table head={["Quote", "Part", "Customer", "Status", "Estimates", "Created"]}>
                  {quotes.map((q) => (
                    <tr key={q.id} className="hover:bg-raised">
                      <Td className="text-precision">{q.quoteNumber}</Td>
                      <Td>{q.part.name}</Td>
                      <Td muted>{q.customer ?? "—"}</Td>
                      <Td>
                        <StatusChip tone="neutral">{q.status}</StatusChip>
                      </Td>
                      <Td>{q.estimates.length}</Td>
                      <Td muted>{q.createdAt.toISOString().slice(0, 10)}</Td>
                    </tr>
                  ))}
                </Table>
              </Panel>
            )}

            {estimates.length > 0 && (
              <Panel title="Stored estimates" dense>
                <Table head={["Part", "Quantity", "Unit cost", "Unit price", "Lot price", "Created"]}>
                  {estimates.map((e) => (
                    <tr key={e.id} className="hover:bg-raised">
                      <Td>
                        <Link href={`/parts/${e.partRevision.partId}/cost`} className="text-platinum hover:text-white">
                          {e.partRevision.part.name}
                        </Link>
                      </Td>
                      <Td>{e.quantity}</Td>
                      <Td>{money(e.unitCost)}</Td>
                      <Td>{money(e.unitPrice)}</Td>
                      <Td muted>{money(e.lotPrice)}</Td>
                      <Td muted>{e.createdAt.toISOString().slice(0, 10)}</Td>
                    </tr>
                  ))}
                </Table>
              </Panel>
            )}
          </>
        )}

        <Notice tone="review" title="CANVAS will not guess a supplier price">
          Make vs buy compares your cost model against quotes you have actually received. It does not estimate what an
          outside shop would charge — a fabricated comparison is worse than an empty one, because somebody will make a
          sourcing decision on it.
        </Notice>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { money } from "@/lib/engines/cost";
import { TopBar } from "@/components/nav";
import { EmptyState, Notice, Panel, SectionHeading, StatusChip, Table, Td, type Tone } from "@/components/ui";
import { QUOTE_STATUS_LABEL, type QuoteStatus } from "@/lib/engines/quoting";
import { RaiseQuoteForm } from "@/components/quoting/raise-quote";
import { createQuote } from "./actions";

const TONE: Record<QuoteStatus, Tone> = {
  DRAFT: "unknown",
  SENT: "precision",
  WON: "pass",
  LOST: "risk",
  EXPIRED: "review",
};

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

  const parts = await db.part.findMany({
    where: { organizationId: user.organizationId },
    orderBy: { name: "asc" },
    select: { id: true, name: true },
  });

  return (
    <>
      <TopBar>
        <span className="tech-label">Quoting</span>
      </TopBar>
      <main className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-6">
        <SectionHeading sub="Quotes carry their assumption set. Machine rate, cycle time, material utilisation, scrap allowance and margin are all stored with the estimate, so a quote can be defended, re-run against changed rates, or compared against what the job actually cost.">
          Quoting
        </SectionHeading>

        <RaiseQuoteForm parts={parts} action={createQuote} />

        {quotes.length === 0 && estimates.length === 0 ? (
          <EmptyState
            title="Nothing quoted yet"
            body="An estimate is frozen from a part's Cost page — machine rate, cycle time, material utilisation, scrap allowance and margin stored with the price so it can be defended later. Attach one to a quote above."
            action={{ label: "Open a part's cost", href: "/parts" }}
          />
        ) : (
          <>
            {quotes.length > 0 && (
              <Panel title="Quotes" dense>
                <Table head={["Quote", "Part", "Customer", "Status", "Estimates", "Created"]}>
                  {quotes.map((q) => (
                    <tr key={q.id} className="hover:bg-raised">
                      <Td className="text-precision">
                        <Link href={`/quoting/${q.id}`} className="underline decoration-dotted hover:text-precision-dim">
                          {q.quoteNumber}
                        </Link>
                      </Td>
                      <Td>{q.part.name}</Td>
                      <Td muted>{q.customer ?? "—"}</Td>
                      <Td>
                        <StatusChip tone={TONE[q.status as QuoteStatus] ?? "neutral"}>
                          {QUOTE_STATUS_LABEL[q.status as QuoteStatus] ?? q.status}
                        </StatusChip>
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

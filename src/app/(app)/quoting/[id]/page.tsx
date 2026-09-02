import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { buildPackage } from "@/lib/package";
import { computeCost, money, type CostAssumptions, type CostLine } from "@/lib/engines/cost";
import {
  assumptionDrift,
  canSend,
  compareQuoteToActual,
  NEXT_QUOTE_STATUS,
  QUOTE_STATUS_LABEL,
  type QuoteStatus,
} from "@/lib/engines/quoting";
import { TopBar } from "@/components/nav";
import { DataRow, LinkButton, Notice, Panel, SectionHeading, StatusChip, Table, Td, type Tone } from "@/components/ui";
import { QuoteTransport, AttachEstimate } from "@/components/quoting/quote-forms";
import { advanceQuote, attachEstimate } from "../actions";

/**
 * ONE QUOTE
 *
 * The page the Quoting subtitle always described: the assumption set travels
 * with the estimate, so the quote can be defended, checked against today's
 * rates, and compared against what the job actually cost.
 *
 * Nothing here recomputes the quote and shows the new number as the quote. A
 * stored estimate is a record of a promise made at particular rates; when the
 * rates move, what is shown is WHICH ones moved.
 */

const TONE: Record<QuoteStatus, Tone> = {
  DRAFT: "unknown",
  SENT: "precision",
  WON: "pass",
  LOST: "risk",
  EXPIRED: "review",
};

export default async function QuotePage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();

  const quote = await db.quote.findFirst({
    where: { id, organizationId: user.organizationId },
    include: {
      part: true,
      estimates: { orderBy: { createdAt: "desc" }, include: { partRevision: { select: { revision: true } } } },
    },
  });
  if (!quote) notFound();

  const pkg = await buildPackage(user.organizationId, quote.partId);
  const unattached = await db.costEstimate.findMany({
    where: { quoteId: null, partRevision: { partId: quote.partId, part: { organizationId: user.organizationId } } },
    orderBy: { createdAt: "desc" },
    include: { partRevision: { select: { revision: true } } },
  });

  const status = quote.status as QuoteStatus;
  const primary = quote.estimates[0] ?? null;
  const quotedAssumptions = primary ? (JSON.parse(primary.assumptionsJson) as CostAssumptions) : null;
  const storedLines = primary
    ? (JSON.parse(primary.linesJson) as { lines: CostLine[]; warnings: string[] })
    : null;

  const drift =
    quotedAssumptions && pkg ? assumptionDrift(quotedAssumptions, pkg.costAssumptions) : [];

  /*
   * What the job actually cost. Rebuilt with the SAME engine and the quote's
   * own assumptions, substituting only what a job actually recorded — so the
   * difference is attributable to the run rather than to a second model.
   */
  const job = await db.job.findFirst({
    where: { organizationId: user.organizationId, partId: quote.partId, status: "COMPLETE" },
    orderBy: { completedAt: "desc" },
  });
  const actual =
    primary && quotedAssumptions && job
      ? compareQuoteToActual(
          computeCost(primary.quantity, quotedAssumptions),
          quotedAssumptions,
          {
            actualCycleMinutes: job.actualCycleMinutes,
            actualSetupHours: job.actualSetupHours,
            scrapCount: job.scrapCount,
            quantityRun: job.quantity,
          },
          (a, q) => computeCost(q, a),
        )
      : null;

  return (
    <>
      <TopBar>
        <Link href="/quoting" className="tech-label hover:text-platinum">Quoting</Link>
        <span className="text-muted">/</span>
        <span className="tech-label">{quote.quoteNumber}</span>
        <StatusChip tone={TONE[status]}>{QUOTE_STATUS_LABEL[status]}</StatusChip>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub={`${quote.part.name}${quote.customer ? ` for ${quote.customer}` : ""}. The assumption set travels with the price, so this can be defended, checked against today's rates, and compared against what the job actually cost.`}>
            {quote.quoteNumber}
          </SectionHeading>

          <Panel title="Quote" meta={<StatusChip tone={TONE[status]}>{QUOTE_STATUS_LABEL[status]}</StatusChip>}>
            <div className="grid gap-x-8 sm:grid-cols-2">
              <DataRow label="Part" value={quote.part.name} />
              <DataRow label="Customer" value={quote.customer ?? "Not recorded"} />
              <DataRow label="Raised" value={quote.createdAt.toISOString().slice(0, 10)} />
              <DataRow label="Valid until" value={quote.validUntil ? quote.validUntil.toISOString().slice(0, 10) : "Not set"} />
            </div>
            {NEXT_QUOTE_STATUS[status].length > 0 ? (
              <QuoteTransport
                next={NEXT_QUOTE_STATUS[status]}
                canSend={canSend(quote.estimates.length)}
                action={advanceQuote.bind(null, quote.id)}
              />
            ) : (
              <p className="tech-label mt-3">
                {status === "WON" || status === "LOST" || status === "EXPIRED"
                  ? "Closed. The number the customer holds does not change when the shop changes its mind — a revised price is a new quote."
                  : ""}
              </p>
            )}
          </Panel>

          {/* ---------------- The price, as it was stored ---------------- */}
          {primary && storedLines ? (
            <Panel
              title="Priced at"
              meta={<StatusChip tone="neutral">Quantity {primary.quantity}</StatusChip>}
            >
              <p>
                <span className="font-mono text-[26px] text-white tabular-nums">{money(primary.unitPrice)}</span>
                <span className="ml-2 text-[12px] text-muted">
                  per part · {money(primary.unitCost)} cost · {money(primary.lotPrice)} for the lot · stored{" "}
                  {primary.createdAt.toISOString().slice(0, 10)}
                  {primary.createdBy ? ` by ${primary.createdBy}` : ""}
                </span>
              </p>
              {storedLines.warnings.length > 0 && (
                <div className="mt-3 border border-review/40 bg-review/5 p-3">
                  <p className="tech-label text-review">Assumptions this quote does not stand on</p>
                  <ul className="mt-1 space-y-1">
                    {storedLines.warnings.map((w) => (
                      <li key={w} className="text-[12px] leading-relaxed text-platinum">{w}</li>
                    ))}
                  </ul>
                </div>
              )}
              <Table head={["Line", "Per part", "Basis"]}>
                {storedLines.lines.map((l) => (
                  <tr key={l.label}>
                    <Td>{l.label}</Td>
                    <Td>{money(l.perPart)}</Td>
                    <Td muted>{l.basis}</Td>
                  </tr>
                ))}
              </Table>
            </Panel>
          ) : (
            <Notice tone="review" title="This quote prices nothing yet">
              A quote needs a stored estimate before it can be sent. Estimates are frozen from a part&rsquo;s Cost
              page, where the assumption set is computed.
            </Notice>
          )}

          {/* ---------------- Has anything moved since ---------------- */}
          {primary && (
            <Panel
              title="Against today's rates"
              meta={<StatusChip tone={drift.length === 0 ? "pass" : "review"}>{drift.length === 0 ? "Unchanged" : `${drift.length} moved`}</StatusChip>}
            >
              {!pkg ? (
                <p className="text-[12.5px] text-review">The part could not be loaded, so nothing can be compared.</p>
              ) : drift.length === 0 ? (
                <p className="text-[12.5px] leading-relaxed text-muted">
                  Every assumption behind this price still matches the shop&rsquo;s current figures.
                </p>
              ) : (
                <>
                  <p className="max-w-2xl text-[12.5px] leading-relaxed text-muted">
                    These inputs have changed since the estimate was stored. The quote is not wrong — it is a record of
                    a promise made at these numbers. Nothing here has been recomputed into the price above.
                  </p>
                  <Table head={["Assumption", "Quoted at", "Now"]}>
                    {drift.map((d) => (
                      <tr key={String(d.key)}>
                        <Td>{d.label}</Td>
                        <Td>{d.quoted.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}</Td>
                        <Td className="text-review">{d.now.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}</Td>
                      </tr>
                    ))}
                  </Table>
                </>
              )}
            </Panel>
          )}

          {/* ---------------- What it actually cost ---------------- */}
          {primary && (
            <Panel title="Against what the job cost">
              {actual ? (
                <>
                  <p>
                    <span className="font-mono text-[26px] text-white tabular-nums">{actual.ratio.toFixed(2)}×</span>
                    <span className="ml-2 text-[12px] text-muted">
                      quoted {money(actual.quotedUnitCost)} cost, actual {money(actual.actualUnitCost)} ·{" "}
                      {actual.deltaPerPart >= 0 ? "+" : ""}
                      {money(actual.deltaPerPart)} per part
                    </span>
                  </p>
                  <p className="mt-2 max-w-2xl text-[12px] leading-relaxed text-muted">
                    Rebuilt with the same cost engine and this quote&rsquo;s own assumptions, substituting only what the
                    job recorded: {actual.usedActuals.join(", ")}.
                    {actual.assumedFromQuote.length > 0 && (
                      <>
                        {" "}
                        <span className="text-review">
                          {actual.assumedFromQuote.join(" and ")} {actual.assumedFromQuote.length === 1 ? "was" : "were"}{" "}
                          not recorded on the job, so {actual.assumedFromQuote.length === 1 ? "it is" : "they are"} still
                          the quoted assumption — that part of this comparison is the quote against itself.
                        </span>
                      </>
                    )}
                  </p>
                </>
              ) : (
                <p className="text-[12.5px] leading-relaxed text-review">
                  {job
                    ? "The completed job recorded no actual cycle time, setup hours or scrap, so there is nothing to rebuild the cost from. A comparison against the quote's own numbers would return exactly 1.00× and call it agreement."
                    : "No completed job for this part yet. A quote is compared against what a run actually cost, not against a second estimate."}
                </p>
              )}
            </Panel>
          )}

          {/* ---------------- Attach ---------------- */}
          {status === "DRAFT" && (
            <AttachEstimate
              estimates={unattached.map((e) => ({
                id: e.id,
                label: `Rev ${e.partRevision.revision} · qty ${e.quantity} · ${money(e.unitPrice)}/part · ${e.createdAt.toISOString().slice(0, 10)}`,
              }))}
              action={attachEstimate.bind(null, quote.id)}
            />
          )}

          <LinkButton href={`/parts/${quote.partId}/cost`} size="sm">
            Open the part&rsquo;s cost
          </LinkButton>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

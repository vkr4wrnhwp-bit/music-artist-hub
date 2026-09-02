import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { buildPackage } from "@/lib/package";
import { compareMakeVsBuy, money } from "@/lib/engines/cost";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { Notice, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";
import { comparableJobs } from "@/lib/disagreement";
import { Disagree } from "@/components/disagree";
import { recordPartDisagreement } from "../disagree-actions";
import { StoreEstimate } from "@/components/quoting/store-estimate";
import { storeEstimate } from "@/app/(app)/quoting/actions";

export default async function CostPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const jobs = await comparableJobs(user.organizationId);
  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  // External quotes are entered by the user, never estimated. With none
  // recorded, BUY genuinely cannot be evaluated and CANVAS says so.
  const suppliers = await db.supplier.findMany({ where: { organizationId: user.organizationId } });
  const comparison = compareMakeVsBuy(pkg.cost.quantity, pkg.cost, [], null);

  // Estimates already frozen against this revision, and whether each is on a
  // quote yet. Read here so the panel can show what storing actually did.
  const stored = await db.costEstimate.findMany({
    where: { partRevisionId: pkg.revision.revisionId },
    orderBy: { createdAt: "desc" },
    take: 10,
    include: { quote: { select: { quoteNumber: true } } },
  });

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Cost</span>
              <PartStatusChip readiness={pkg.readiness} />
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="Every number here traces to a stored assumption. A quote you cannot defend in a customer meeting is worthless, so the assumption set travels with the estimate rather than living in someone's head.">
            Cost & make vs buy
          </SectionHeading>

          {pkg.cost.warnings.length > 0 && (
            <div className="border border-review/40 bg-review/5 p-4">
              <p className="tech-label mb-2 text-review">Assumptions this quote cannot stand on</p>
              <ul className="space-y-1.5">
                {pkg.cost.warnings.map((w) => (
                  <li key={w} className="text-[12.5px] leading-relaxed text-platinum">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <StoreEstimate
            quantity={pkg.cost.quantity}
            unitPrice={money(pkg.cost.unitPrice)}
            warnings={pkg.cost.warnings}
            stored={stored.map((e) => ({
              id: e.id,
              quantity: e.quantity,
              unitPrice: money(e.unitPrice),
              createdAt: e.createdAt,
              quoteNumber: e.quote?.quoteNumber ?? null,
            }))}
            action={storeEstimate.bind(null, id)}
          />

          <div className="grid gap-px bg-line sm:grid-cols-3">
            <Metric label="Unit cost" value={money(pkg.cost.unitCost)} sub={`at quantity ${pkg.cost.quantity}`} />
            <Metric label="Unit price" value={money(pkg.cost.unitPrice)} sub={`${(pkg.costAssumptions.marginRate * 100).toFixed(0)}% margin`} />
            <Metric label="Cycle time" value={`${pkg.cycleMinutes.toFixed(2)} min`} sub="from generated toolpaths" />
          </div>

          <Panel title="Cost breakdown" dense>
            <Table head={["Line", "Per part", "Per lot", "Basis"]}>
              {pkg.cost.lines.map((l) => (
                <tr key={l.label} className="hover:bg-raised">
                  <Td className="text-platinum">{l.label}</Td>
                  <Td>{money(l.perPart)}</Td>
                  <Td muted>{money(l.perLot)}</Td>
                  <Td muted className="text-[11px]">
                    {l.basis}
                  </Td>
                </tr>
              ))}
              <tr className="bg-raised">
                <Td className="text-white">Unit cost</Td>
                <Td className="text-white">{money(pkg.cost.unitCost)}</Td>
                <Td className="text-white">{money(pkg.cost.unitCost * pkg.cost.quantity)}</Td>
                <Td muted>Sum of all lines</Td>
              </tr>
            </Table>
          </Panel>

          <Panel title="Quantity breaks" dense>
            <Table head={["Quantity", "Unit cost", "Unit price", "Lot price", "Setup per part"]}>
              {pkg.breaks.map((b) => (
                <tr key={b.quantity} className={b.quantity === pkg.cost.quantity ? "bg-raised" : "hover:bg-raised"}>
                  <Td className={b.quantity === pkg.cost.quantity ? "text-precision" : "text-platinum"}>{b.quantity}</Td>
                  <Td>{money(b.unitCost)}</Td>
                  <Td>{money(b.unitPrice)}</Td>
                  <Td muted>{money(b.lotPrice)}</Td>
                  <Td muted>{money(b.setupCostPerPart)}</Td>
                </tr>
              ))}
            </Table>
            <p className="border-t border-line px-4 py-3 text-[12px] leading-relaxed text-muted">
              Setup amortisation is what moves this curve. At quantity 1 the setup is the part; by 100 it is noise. If
              the curve does not flatten, the cycle time is the problem, not the batch size.
            </p>
          </Panel>

          <Panel title="Make vs buy">
            <div className="space-y-3">
              {comparison.options.map((o) => (
                <div key={o.id} className="border border-line px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-[12px] text-platinum">{o.label}</span>
                    <span className="flex items-center gap-2">
                      <StatusChip tone={o.grounded ? "pass" : "unknown"}>{o.grounded ? "Grounded" : "No data"}</StatusChip>
                      <span className="font-mono text-[13px] text-white">
                        {o.unitCost !== null ? money(o.unitCost) : "—"}
                      </span>
                    </span>
                  </div>
                  <p className="mt-1 text-[12px] text-muted">{o.notes}</p>
                </div>
              ))}
            </div>

            {comparison.recommendation ? (
              <>
                <p className="mt-4 text-[13px] text-platinum">{comparison.recommendation}</p>
                {/* Only where there IS a recommendation. With no external
                    quotes there is no CANVAS position to disagree with, and
                    a form offering to argue with nothing is a dead control. */}
                <div className="mt-3">
                  <Disagree
                    action={recordPartDisagreement}
                    partId={id}
                    surface="cost"
                    subjectType="COST"
                    subjectId={pkg.revision.revisionId}
                    canvasPosition={comparison.recommendation}
                    jobs={jobs}
                  />
                </div>
              </>
            ) : (
              <Notice tone="unknown" title="Buy cannot be evaluated">
                No external quotes have been entered for this part. CANVAS will not estimate a supplier price it has no
                basis for — a fabricated comparison is worse than an empty one, because someone will act on it.
              </Notice>
            )}

            {comparison.caveats.length > 0 && (
              <ul className="mt-4 space-y-1">
                {comparison.caveats.map((c) => (
                  <li key={c} className="text-[11.5px] leading-relaxed text-muted">
                    — {c}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Assumptions">
            <div className="grid gap-x-8 gap-y-1 sm:grid-cols-2">
              {Object.entries(pkg.costAssumptions).map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-line/60 py-1.5">
                  <span className="tech-label">{k.replace(/([A-Z])/g, " $1").toLowerCase()}</span>
                  <span className="font-mono text-[12px] text-platinum">
                    {typeof v === "number" ? (v < 1 && v > 0 ? v.toFixed(3) : v.toFixed(2)) : String(v)}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-4 text-[12px] leading-relaxed text-muted">
              Rates come from your shop settings. Cycle time comes from the generated toolpaths, not an estimate. Tool
              cost is consumed life — minutes in cut divided by expected tool life, times tool price.
            </p>
          </Panel>
        </div>
      </main>
    </>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="bg-surface px-5 py-4">
      <p className="tech-label">{label}</p>
      <p className="mt-1 font-mono text-[24px] font-light text-white">{value}</p>
      <p className="tech-label mt-0.5">{sub}</p>
    </div>
  );
}

export const dynamic = "force-dynamic";

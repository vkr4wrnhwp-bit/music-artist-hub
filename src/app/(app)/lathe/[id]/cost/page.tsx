import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { Notice, Panel, SectionHeading, Table, Td } from "@/components/ui";
import { buildTurnPackage } from "@/lib/manufacturing/turn/package";
import { deriveTurnCostAssumptions } from "@/lib/manufacturing/turn/cost";
import { computeCost, quantityBreaks, compareMakeVsBuy, money } from "@/lib/engines/cost";
import { findReusableLatheJaws } from "@/lib/manufacturing/turn/soft-jaws";

/**
 * TURNING COST — bar economics + the generic cost engine.
 *
 * Cycle time from the generated toolpaths, kerf from the recorded parting
 * tool, remnant from the recorded grip, utilization computed from
 * parts-per-bar. Where a recorded input is missing the derived figure is
 * absent and named, not defaulted silently. BUY stays unevaluated until a
 * real quote exists.
 */

export default async function LatheCostPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();

  /*
   * One assembly, same as the workspace. This page used to rebuild the
   * toolpaths itself, so it also had to know how to resolve a groove insert
   * and a thread pitch — and when boring learned to ask for the bar at its
   * station, this copy would have quietly costed every bore at zero minutes.
   */
  const pkg = await buildTurnPackage(user.organizationId, id);
  if (!pkg) notFound();
  const { part, rot, profile, results, totalMinutes: cycleMinutes, tools } = pkg;
  const jawSets = await db.latheWorkholding.findMany({ where: { organizationId: user.organizationId, type: "SOFT_JAWS" } });
  const refused = results.filter((r) => !r.result.ok);

  const partingTool = tools.find((t) => t.toolClass === "PARTING");
  const gripDia = profile.stockDiameter;
  const jawMatches =
    rot.gripLength && jawSets.length > 0
      ? findReusableLatheJaws(gripDia, rot.gripLength, jawSets.map((j) => ({ id: j.id, description: j.description, boredDiameter: j.boredDiameter, boredDepth: j.boredDepth })))
      : [];
  const softJawsNeedBoring = jawMatches.length > 0 && jawMatches[0].kind !== "DIRECT";

  const quantity = pkg.quantity;

  const derived = deriveTurnCostAssumptions({
    profile,
    cycleMinutes,
    partOffKerf: partingTool?.grooveWidth ?? null,
    gripLength: rot.gripLength,
    softJawsNeedBoring,
    tailstock: rot.tailstockActive,
  });
  const cost = computeCost(quantity, derived.assumptions);
  const breaks = quantityBreaks(derived.assumptions);
  const comparison = compareMakeVsBuy(quantity, cost, [], null);

  return (
    <>
      <TopBar>
        <Link href="/lathe" className="tech-label hover:text-platinum">Turning</Link>
        <span className="text-muted">/</span>
        <Link href={`/lathe/${id}`} className="tech-label hover:text-platinum">{part.name}</Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Cost</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="Bar economics derived from the rotational model: kerf from the recorded parting tool, remnant from the recorded grip, utilization computed from parts-per-bar, cycle from the generated toolpaths. Missing inputs are named, never defaulted silently.">
            Cost & make vs buy — turning
          </SectionHeading>

          {cost.warnings.length > 0 && (
            <div className="border border-review/40 bg-review/5 p-4">
              <p className="tech-label mb-2 text-review">Assumptions this quote cannot stand on</p>
              <ul className="space-y-1.5">
                {cost.warnings.map((w) => (
                  <li key={w} className="text-[12.5px] leading-relaxed text-platinum">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid gap-px bg-line sm:grid-cols-3">
            <Metric label="Unit cost" value={money(cost.unitCost)} sub={`at quantity ${quantity}`} />
            <Metric label="Unit price" value={money(cost.unitPrice)} sub={`${(derived.assumptions.marginRate * 100).toFixed(0)}% margin`} />
            <Metric label="Cycle time" value={`${cycleMinutes.toFixed(2)} min`} sub="from turning toolpaths" />
          </div>

          {/*
            * A refused operation contributes zero minutes, so the cycle time
            * above — and every figure derived from it — is for a job that
            * does not include it. Quoting that as the cycle is quoting the
            * part short.
            */}
          {refused.length > 0 && (
            <Notice tone="risk" title={`Cycle time excludes ${refused.length} operation(s) the engine could not plan`}>
              <ul className="mt-1 space-y-1">
                {refused.map(({ op, result }) => (
                  <li key={op.operationNumber}>
                    — Op {op.operationNumber} {op.label}: {result.ok ? "" : result.reason}
                  </li>
                ))}
              </ul>
              <p className="mt-2">
                The quote below is for the operations that could be planned. It is not the cost of this part.
              </p>
            </Notice>
          )}

          <Panel title="Bar economics" dense>
            <div className="grid gap-px bg-line sm:grid-cols-4">
              <Metric label="Bar" value={`${derived.bar.barLengthIn / 12} ft`} sub="standard, stated" />
              <Metric label="Part + kerf" value={derived.bar.partLengthWithKerf !== null ? `${derived.bar.partLengthWithKerf.toFixed(2)}"` : "—"} sub={derived.bar.partLengthWithKerf !== null ? "consumed per part" : "kerf unrecorded"} />
              <Metric label="Parts per bar" value={derived.bar.partsPerBar !== null ? String(derived.bar.partsPerBar) : "—"} sub={derived.bar.partsPerBar !== null ? `remnant ${derived.bar.remnant?.toFixed(2)}"` : "not computable"} />
              <Metric label="Bar utilization" value={derived.bar.utilization !== null ? `${(derived.bar.utilization * 100).toFixed(1)}%` : "—"} sub={derived.bar.utilization !== null ? "computed" : "fallback assumed"} />
            </div>
            <ul className="space-y-1 px-4 py-3">
              {derived.bar.notes.map((n, i) => (
                <li key={i} className="text-[11.5px] leading-relaxed text-muted">{n}</li>
              ))}
            </ul>
            {derived.bar.missingInputs.length > 0 && (
              <ul className="space-y-1 border-t border-line/60 px-4 py-3">
                {derived.bar.missingInputs.map((m, i) => (
                  <li key={i} className="text-[11.5px] leading-relaxed text-review">{m}</li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Cost breakdown" dense>
            <Table head={["Line", "Per part", "Per lot", "Basis"]}>
              {cost.lines.map((l) => (
                <tr key={l.label} className="hover:bg-raised">
                  <Td className="text-platinum">{l.label}</Td>
                  <Td>{money(l.perPart)}</Td>
                  <Td muted>{money(l.perLot)}</Td>
                  <Td muted className="text-[11px]">{l.basis}</Td>
                </tr>
              ))}
              <tr className="bg-raised">
                <Td className="text-white">Unit cost</Td>
                <Td className="text-white">{money(cost.unitCost)}</Td>
                <Td className="text-white">{money(cost.unitCost != null ? cost.unitCost * cost.quantity : null)}</Td>
                <Td muted>Sum of all lines</Td>
              </tr>
            </Table>
          </Panel>

          <Panel title="Quantity breaks" dense>
            <Table head={["Quantity", "Unit cost", "Unit price", "Lot price", "Setup per part"]}>
              {breaks.map((b) => (
                <tr key={b.quantity} className={b.quantity === quantity ? "bg-raised" : "hover:bg-raised"}>
                  <Td className={b.quantity === quantity ? "text-precision" : "text-platinum"}>{b.quantity}</Td>
                  <Td>{money(b.unitCost)}</Td>
                  <Td>{money(b.unitPrice)}</Td>
                  <Td muted>{money(b.lotPrice)}</Td>
                  <Td muted>{money(b.setupCostPerPart)}</Td>
                </tr>
              ))}
            </Table>
            <p className="border-t border-line px-4 py-3 text-[12px] leading-relaxed text-muted">
              Bar work flattens faster than mill work: setup amortises AND the remnant spreads across more parts. If the curve stays steep past 25, the cycle is the problem, not the batch.
            </p>
          </Panel>

          <Panel title="Make vs buy">
            {comparison.options.map((o) => (
              <div key={o.id} className="border border-line px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-[12px] text-platinum">{o.label}</span>
                  <span className="font-mono text-[13px] text-white">{o.unitCost !== null ? money(o.unitCost) : "—"}</span>
                </div>
                <p className="mt-1 text-[12px] text-muted">{o.notes}</p>
              </div>
            ))}
            <Notice tone="unknown" title="Buy cannot be evaluated">
              No external quotes have been entered for this part. CANVAS will not estimate a supplier price it has no basis for.
            </Notice>
            {comparison.caveats.length > 0 && (
              <ul className="mt-3 space-y-1">
                {comparison.caveats.map((c) => (
                  <li key={c} className="text-[11.5px] leading-relaxed text-muted">— {c}</li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Where the turning assumptions came from">
            <ul className="space-y-1">
              {derived.basis.map((b, i) => (
                <li key={i} className="text-[12px] leading-relaxed text-platinum-dim">{b}</li>
              ))}
            </ul>
            <p className="mt-3 text-[12px] leading-relaxed text-muted">
              Rates, scrap, margin and tooling consumption remain shop-level assumptions from the generic cost model — visible in every line&apos;s basis above, never hidden.
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
      <p className="mt-1 font-mono text-[20px] font-light text-white">{value}</p>
      <p className="tech-label mt-0.5">{sub}</p>
    </div>
  );
}

export const dynamic = "force-dynamic";

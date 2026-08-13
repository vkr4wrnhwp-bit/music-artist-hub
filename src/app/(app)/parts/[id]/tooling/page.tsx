import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { buildPackage } from "@/lib/package";
import { getShopSettings } from "@/lib/data";
import { planHole } from "@/lib/engines/tool-substitution";
import { findExistingJaws, proposeFamily, jawEconomics, type JawSet, type JawProfile } from "@/lib/engines/jaw-family";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { DataRow, EmptyState, Notice, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

/**
 * WORKING WITH WHAT YOU HAVE
 *
 * Two questions a machinist answers constantly and software usually ignores:
 * "I do not own that drill — what do I own?" and "do I really have to cut jaws
 * for this, or is there something in the drawer?"
 */

export default async function ToolingPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();

  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  const [jawRows, shop] = await Promise.all([
    db.jawSet.findMany({ where: { organizationId: user.organizationId }, orderBy: { nominalSize: "asc" } }),
    getShopSettings(user.organizationId),
  ]);

  const inventory: JawSet[] = jawRows.map((j) => ({
    id: j.id,
    name: j.name,
    profile: j.profile as JawProfile,
    nominalSize: j.nominalSize,
    nominalLength: j.nominalLength ?? undefined,
    stepDepth: j.stepDepth,
    jawHeight: j.jawHeight,
    material: j.material,
    viseDescription: j.viseDescription,
    timesUsed: j.timesUsed,
    minutesToCut: j.minutesToCut,
    notes: j.notes ?? undefined,
  }));

  /* ---------------- Every hole in the part, planned against the crib ---------------- */

  const holes = pkg.revision.features.filter(
    (f) => f.kind === "DRILLED_HOLE" || f.kind === "TAPPED_HOLE" || f.kind === "BORE" || f.kind === "CIRC_POCKET",
  );

  const holePlans = holes.map((f) => {
    const diameter = "diameter" in f ? f.diameter : 0;
    const through = "through" in f ? f.through : false;
    const depth = through ? (pkg.revision.stock?.z ?? 1) : "depth" in f ? f.depth : 0.5;
    return {
      feature: f,
      diameter,
      plan: planHole({
        targetDiameter: diameter,
        depth,
        precision: f.critical || Boolean(f.tolerance && f.tolerance.plus + f.tolerance.minus <= 0.002),
        tools: pkg.tools,
      }),
    };
  });

  /* ---------------- Jaws: is there something in the drawer? ---------------- */

  const stock = pkg.revision.stock;
  const contour = pkg.revision.features.find((f) => f.kind === "OUTSIDE_CONTOUR");
  const partWidth = contour && "width" in contour ? contour.width : (stock?.x ?? 0);
  const partLength = contour && "length" in contour ? contour.length : (stock?.y ?? 0);
  const secondSetup = pkg.setups.find((s) => s.sequence > 1);
  const requiredStep = secondSetup?.gripDepth ?? 0.15;

  const jawRequest = { profile: "RECTANGULAR" as JawProfile, size: partWidth, length: partLength, requiredStep };
  const matches = stock ? findExistingJaws(jawRequest, inventory) : [];
  const family = stock ? proposeFamily(jawRequest, inventory) : null;

  const economics = family
    ? jawEconomics({
        minutesToCut: family.minutesToCut,
        shopRatePerHour: shop.machineRate + shop.operatorRate,
        blankCost: 45,
        quantity: pkg.revision.intent.quantity.value ?? 1,
        expectedUses: 4,
        reuseSetupMinutes: matches[0]?.setupMinutes ?? null,
      })
    : null;

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Working with what you have</span>
              <PartStatusChip readiness={pkg.readiness} />
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="Two questions that decide whether a job is cheap or expensive, and that most CAM software answers by assuming you own everything: what do I do without the exact drill, and do I actually need to cut jaws for this?">
            Working with what you have
          </SectionHeading>

          {/* ---------------- Tool substitution ---------------- */}
          {/* Coach-mark anchor: readiness SHOW ME for tool gates lands here. */}
          <div data-guide-target="tool-assignment">
          <Panel title="Holes, against the crib you actually own">
            {holePlans.length === 0 ? (
              <p className="text-[12.5px] text-muted">This part has no holes or bores.</p>
            ) : (
              <div className="space-y-4">
                {holePlans.map(({ feature, diameter, plan }) => (
                  <div key={feature.id} className="border border-line px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-[12.5px] text-platinum">
                        {feature.label} — ⌀{diameter.toFixed(4)}
                      </span>
                      <span className="flex gap-2">
                        {feature.critical && <StatusChip tone="review">Tolerance</StatusChip>}
                        <StatusChip tone={plan.blocked ? "risk" : plan.exact ? "pass" : "precision"}>
                          {plan.blocked ? "Cannot produce" : plan.exact ? "Exact tool" : "Substitution"}
                        </StatusChip>
                      </span>
                    </div>

                    {plan.blocked ? (
                      <>
                        <p className="mt-2 text-[12.5px] leading-relaxed text-risk">{plan.blocked}</p>
                        {plan.suggestedPurchase && (
                          <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
                            <span className="tech-label">Buy</span> {plan.suggestedPurchase}
                          </p>
                        )}
                      </>
                    ) : (
                      <ol className="mt-3 space-y-2">
                        {plan.steps.map((s) => (
                          <li key={s.order} className="flex gap-3">
                            <span className="font-mono text-[11px] text-precision">
                              {String(s.order).padStart(2, "0")}
                            </span>
                            <span className="min-w-0">
                              <span className="block font-mono text-[12px] text-platinum">{s.action}</span>
                              <span className="tech-label block">
                                T{s.toolNumber ?? "—"} {s.toolDescription}
                                {s.remainingPerSide > 0
                                  ? ` · leaves ${s.remainingPerSide.toFixed(4)}″ per side`
                                  : " · to size"}
                              </span>
                              <span className="mt-0.5 block text-[12px] leading-relaxed text-muted">{s.rationale}</span>
                            </span>
                          </li>
                        ))}
                      </ol>
                    )}

                    {plan.warnings.map((w) => (
                      <p key={w} className="mt-2 text-[11.5px] leading-relaxed text-review">
                        {w}
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </Panel>
          </div>

          {/* ---------------- Jaw drawer ---------------- */}
          <Panel title="The jaw drawer" meta={<span className="tech-label">{inventory.length} sets on hand</span>}>
            {inventory.length === 0 ? (
              <EmptyState
                title="No jaw sets recorded"
                body="Soft jaws only stop being an expense once you know what is already in the drawer. Record the sets you have and CANVAS will look there before it proposes cutting anything."
                action={{ label: "Workholding", href: "/workholding" }}
              />
            ) : (
              <Table head={["Set", "Profile", "Size", "Step", "Times used", "Notes"]}>
                {inventory.map((j) => (
                  <tr key={j.id} className="hover:bg-raised">
                    <Td className="text-platinum">{j.name}</Td>
                    <Td muted>{j.profile.toLowerCase()}</Td>
                    <Td>
                      {j.nominalSize.toFixed(3)}
                      {j.nominalLength ? ` × ${j.nominalLength.toFixed(3)}` : ""}
                    </Td>
                    <Td>{j.stepDepth.toFixed(3)}″</Td>
                    <Td>{j.timesUsed}</Td>
                    <Td muted className="text-[11px]">
                      {j.notes ?? "—"}
                    </Td>
                  </tr>
                ))}
              </Table>
            )}
          </Panel>

          {/* ---------------- Reuse or cut ---------------- */}
          {stock && (
            <Panel title="Do you need to cut jaws for this?">
              {matches.length > 0 ? (
                <>
                  <Notice tone="pass" title="Something in the drawer already fits">
                    {matches[0].reason}
                  </Notice>
                  <div className="mt-4 space-y-3">
                    {matches.map((m) => (
                      <div key={m.jawSet.id} className="border border-line px-4 py-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-mono text-[12.5px] text-platinum">{m.jawSet.name}</span>
                          <StatusChip tone={m.direct ? "pass" : "precision"}>
                            {m.direct ? "Drops straight in" : "Shim to fit"}
                          </StatusChip>
                        </div>
                        {m.shim && (
                          <>
                            <p className="tech-label mt-2">Shim stack, per side</p>
                            <p className="mt-0.5 font-mono text-[13px] text-precision">
                              {m.shim.stack.map((s) => s.toFixed(3)).join(" + ")}″
                            </p>
                            <p className="mt-1 text-[12px] leading-relaxed text-muted">{m.shim.note}</p>
                          </>
                        )}
                        <p className="tech-label mt-2">
                          ~{m.setupMinutes} min to fit and prove, against {family?.minutesToCut ?? 35} min to cut new
                        </p>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <Notice tone="review" title="Nothing in the drawer fits this part">
                  Every set on hand is either the wrong profile, too small, or has too shallow a step for the grip this
                  setup needs.
                </Notice>
              )}

              {family && (
                <div className="mt-5 border-t border-line pt-5">
                  <p className="tech-label mb-2">If you do cut new jaws</p>
                  <p className="max-w-2xl text-[13px] leading-relaxed text-platinum">{family.rationale}</p>
                  <p className="mt-2 max-w-2xl text-[12.5px] leading-relaxed text-muted">{family.versusBespoke}</p>
                  <div className="mt-3 grid gap-x-8 sm:grid-cols-2">
                    <DataRow label="Cut at" value={`${family.cutAt.toFixed(3)}″`} />
                    <DataRow label="This part needs" value={`${family.partSize.toFixed(3)}″`} />
                    <DataRow label="Covers" value={`${family.coversFrom.toFixed(3)}–${family.coversTo.toFixed(3)}″`} />
                    <DataRow
                      label="Shim for this part"
                      value={family.shim ? `${family.shim.stack.map((s) => s.toFixed(3)).join(" + ")}″` : "none"}
                    />
                  </div>
                </div>
              )}

              {economics && (
                <div className="mt-5 border-t border-line pt-5">
                  <p className="tech-label mb-2">What it costs</p>
                  <div className="grid gap-x-8 sm:grid-cols-2">
                    <DataRow label="Cutting the jaws" value={`$${economics.cutCost.toFixed(2)}`} />
                    <DataRow label="Charged to this job alone" value={`$${economics.costIfBespoke.toFixed(2)}/part`} />
                    <DataRow
                      label={`Spread over ${economics.expectedUses} jobs`}
                      value={`$${economics.costAmortised.toFixed(2)}/part`}
                    />
                    <DataRow
                      label="Reusing what you have"
                      value={economics.costIfReused !== null ? `$${economics.costIfReused.toFixed(2)}/part` : "—"}
                    />
                  </div>
                  <p className="mt-3 max-w-2xl text-[12.5px] leading-relaxed text-platinum">{economics.verdict}</p>
                </div>
              )}
            </Panel>
          )}

          <Notice tone="precision" title="Why soft jaws look expensive and are not">
            The cost of cutting jaws gets charged once, to one job, and then the jaws go in a drawer and eventually get
            scrapped for the blanks. That is a bookkeeping failure rather than a manufacturing one. Cut at a size that
            heads a family, keep the shim schedule with them, and the second job that uses them costs two shims and a
            setup.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

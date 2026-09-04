import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TECHNOLOGY_LABEL, type PrintTechnology } from "@/lib/engines/additive";
import { TopBar } from "@/components/nav";
import { EmptyState, LinkButton, Notice, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

/**
 * ADDITIVE INVENTORY
 *
 * The print-vs-cut advisor answers from these rows and refuses without them.
 * The two columns worth reading are "holds" on a printer and "through Z" on a
 * material: both are allowed to be blank, and blank changes the advisor's
 * answer from a verdict to a named gap rather than to a guess.
 */

const tech = (t: string) => TECHNOLOGY_LABEL[t as PrintTechnology] ?? t;

export default async function PrintingPage() {
  const user = await requireUser();
  const [printers, materials] = await Promise.all([
    db.printer.findMany({ where: { organizationId: user.organizationId }, orderBy: [{ manufacturer: "asc" }, { model: "asc" }] }),
    db.printMaterial.findMany({ where: { organizationId: user.organizationId }, orderBy: { name: "asc" } }),
  ]);

  const unmeasured = printers.filter((p) => p.achievableTolerance == null);
  const noZ = materials.filter((m) => m.tensileXY != null && m.tensileZ == null);

  return (
    <>
      <TopBar>
        <span className="tech-label">Additive</span>
      </TopBar>
      <main className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <SectionHeading sub="CANVAS answers 'should this be printed' against the machines and materials you actually own. A printer that is not on this list is not considered, and what a machine holds is a property of that machine — not of its datasheet.">
            Additive
          </SectionHeading>
          <div className="shrink-0 pt-1">
            <LinkButton href="/printing/new" size="sm" variant="primary">
              Add printer
            </LinkButton>
          </div>
        </div>

        {printers.length === 0 ? (
          <EmptyState
            title="No printer recorded"
            body="The manufacturing method advisor cannot say anything about printing this part until it knows what you would print it on. Add the machine, then the materials you run on it."
            action={{ label: "Add printer", href: "/printing/new" }}
          />
        ) : (
          <Panel title={`${printers.length} printer${printers.length === 1 ? "" : "s"}`} dense>
            <Table head={["Machine", "Technology", "Build volume", "Holds", "Finish", ""]}>
              {printers.map((p) => (
                <tr key={p.id} className="hover:bg-raised">
                  <Td className="text-platinum">
                    {p.manufacturer} {p.model}
                  </Td>
                  <Td muted>{tech(p.technology)}</Td>
                  <Td muted>
                    {p.buildX.toFixed(1)} × {p.buildY.toFixed(1)} × {p.buildZ.toFixed(1)}″
                  </Td>
                  <Td>
                    {p.achievableTolerance != null ? (
                      <span className="font-mono tabular-nums text-platinum">±{p.achievableTolerance.toFixed(4)}″</span>
                    ) : (
                      <StatusChip tone="review">NOT MEASURED</StatusChip>
                    )}
                  </Td>
                  <Td muted>{p.achievableRa != null ? `Ra ${p.achievableRa.toFixed(0)} µin` : "—"}</Td>
                  <Td>
                    <Link
                      href={`/printing/${p.id}/edit`}
                      className="text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:text-precision"
                    >
                      Edit
                    </Link>
                  </Td>
                </tr>
              ))}
            </Table>
          </Panel>
        )}

        {unmeasured.length > 0 && (
          <Notice tone="review" title={`${unmeasured.length} printer${unmeasured.length === 1 ? "" : "s"} with no measured tolerance`}>
            {unmeasured.map((p) => `${p.manufacturer} ${p.model}`).join(", ")}. The advisor will not judge a tolerance
            band against a machine nobody has measured, and will not substitute the datasheet figure. Print a coupon,
            measure it, and record what you got.
          </Notice>
        )}

        <div className="flex items-start justify-between gap-4 pt-2">
          <SectionHeading sub="Strength in the build plane and through the layers. The second figure is the one that governs wherever a part is loaded across the layers, and leaving it blank is better than copying the first.">
            Print materials
          </SectionHeading>
          <div className="shrink-0 pt-1">
            <LinkButton href="/printing/materials/new" size="sm">
              Add material
            </LinkButton>
          </div>
        </div>

        {materials.length === 0 ? (
          <EmptyState
            title="No print material recorded"
            body="Without a material the advisor can check whether a part fits the bed and whether the machine holds the tolerance, and nothing about whether the part will survive being loaded."
            action={{ label: "Add material", href: "/printing/materials/new" }}
          />
        ) : (
          <Panel title={`${materials.length} material${materials.length === 1 ? "" : "s"}`} dense>
            <Table head={["Material", "Technology", "In plane", "Through Z", "Retained", "Max temp", "Creep", ""]}>
              {materials.map((m) => {
                const retained = m.tensileXY != null && m.tensileZ != null ? m.tensileZ / m.tensileXY : null;
                return (
                  <tr key={m.id} className="hover:bg-raised">
                    <Td className="text-platinum">{m.name}</Td>
                    <Td muted>{tech(m.technology)}</Td>
                    <Td muted>{m.tensileXY != null ? `${m.tensileXY.toFixed(0)} psi` : "—"}</Td>
                    <Td>
                      {m.tensileZ != null ? (
                        <span className="font-mono tabular-nums text-platinum">{m.tensileZ.toFixed(0)} psi</span>
                      ) : (
                        <StatusChip tone="review">NOT MEASURED</StatusChip>
                      )}
                    </Td>
                    <Td>
                      {retained != null ? (
                        <StatusChip tone={retained >= 0.7 ? "pass" : "risk"}>{`${(retained * 100).toFixed(0)}%`}</StatusChip>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </Td>
                    <Td muted>{m.maxServiceTempF != null ? `${m.maxServiceTempF.toFixed(0)}°F` : "—"}</Td>
                    <Td muted>{m.creepDataOnFile ? "on file" : "none"}</Td>
                    <Td>
                      <Link
                        href={`/printing/materials/${m.id}/edit`}
                        className="text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:text-precision"
                      >
                        Edit
                      </Link>
                    </Td>
                  </tr>
                );
              })}
            </Table>
          </Panel>
        )}

        {noZ.length > 0 && (
          <Notice tone="review" title={`${noZ.length} material${noZ.length === 1 ? "" : "s"} with no through-layer figure`}>
            {noZ.map((m) => m.name).join(", ")}. A printed part is bonded between layers rather than continuous through
            them, so a part loaded across them is a different part from the one the in-plane figure describes. The
            advisor reports the gap rather than assuming the two are equal, which is the assumption that breaks a
            printed part.
          </Notice>
        )}

        <Notice tone="review" title="What this inventory does not do">
          CANVAS does not slice, does not generate printer motion and does not estimate print time. It answers whether
          a part <em>should</em> be printed on what you own, and hands the decision back. The machine that makes the
          part is still the one that makes the part.
        </Notice>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

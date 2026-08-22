import { requireUser } from "@/lib/auth";
import { getMaterials } from "@/lib/data";
import { TopBar } from "@/components/nav";
import { EmptyState, LinkButton, Panel, SectionHeading, Table, Td } from "@/components/ui";

export default async function MaterialsPage() {
  const user = await requireUser();
  const materials = await getMaterials(user.organizationId);

  return (
    <>
      <TopBar>
        <span className="tech-label">Materials</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <SectionHeading sub="Material drives speeds, feeds, the cutting-force model and the material line of every quote. Specific cutting energy is what turns a depth of cut into an estimated load on the workholding.">
            Materials
          </SectionHeading>
          <div className="shrink-0 pt-1">
            <LinkButton href="/materials/new" size="sm" variant="primary">
              Add material
            </LinkButton>
          </div>
        </div>

        {materials.length === 0 ? (
          <EmptyState
            title="No materials defined"
            body="Without a material, CANVAS cannot derive surface speed, estimate cutting load, or cost a part."
            action={{ label: "Add material", href: "/materials/new" }}
          />
        ) : (
          <Panel title={`${materials.length} materials`} dense>
            <Table head={["Material", "Condition", "Family", "Density", "Machinability", "SFM (carbide)", "Spec. energy", "$/lb", "Castable"]}>
              {materials.map((m) => (
                <tr key={m.id} className="hover:bg-raised">
                  <Td className="text-platinum">{m.name}</Td>
                  <Td muted>{m.condition}</Td>
                  <Td muted>{m.family}</Td>
                  <Td>{m.density.toFixed(3)}</Td>
                  <Td>{m.machinabilityRating}%</Td>
                  <Td muted>
                    {m.sfmCarbideMin}–{m.sfmCarbideMax}
                  </Td>
                  <Td>{m.specificEnergy.toFixed(2)}</Td>
                  <Td>${m.costPerPound.toFixed(2)}</Td>
                  <Td muted>{m.castable ? "Yes" : "No"}</Td>
                </tr>
              ))}
            </Table>
          </Panel>
        )}
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

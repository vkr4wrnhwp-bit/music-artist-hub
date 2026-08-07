import { requireUser } from "@/lib/auth";
import { getWorkholding } from "@/lib/data";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { EmptyState, Notice, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

export default async function WorkholdingPage() {
  const user = await requireUser();
  const [devices, blanks] = await Promise.all([
    getWorkholding(user.organizationId),
    db.jawBlank.findMany({ where: { organizationId: user.organizationId } }),
  ]);

  return (
    <>
      <TopBar>
        <span className="tech-label">Workholding</span>
      </TopBar>
      <main className="flex-1 space-y-6 overflow-y-auto p-6">
        <SectionHeading sub="Workholding is where most real machining failures start. CANVAS reasons about grip depth, jaw engagement, projection and cutting load per setup — but only against devices recorded here with real dimensions.">
          Workholding
        </SectionHeading>

        {devices.length === 0 ? (
          <EmptyState
            title="Workholding not defined"
            body="CANVAS can generate toolpaths, but cannot evaluate setup stability or fixture collisions until workholding is defined."
            action={{ label: "Define workholding", href: "/workholding/new" }}
          />
        ) : (
          <Panel title="Devices" dense>
            <Table head={["Type", "Description", "Jaw width", "Jaw height", "Max opening", "Clamp force", "Fixture height", "CAD"]}>
              {devices.map((d) => (
                <tr key={d.id} className="hover:bg-raised">
                  <Td className="text-precision">{d.type.replace(/_/g, " ")}</Td>
                  <Td>{d.description}</Td>
                  <Td>{d.jawWidth.toFixed(2)}″</Td>
                  <Td>{d.jawHeight.toFixed(2)}″</Td>
                  <Td>{d.maxOpening.toFixed(2)}″</Td>
                  <Td muted>{d.clampForce ? `${d.clampForce} lbf` : "—"}</Td>
                  <Td>{d.fixtureHeight.toFixed(2)}″</Td>
                  <Td>
                    <StatusChip tone={d.hasCadRepresentation ? "pass" : "unknown"}>
                      {d.hasCadRepresentation ? "Yes" : "None"}
                    </StatusChip>
                  </Td>
                </tr>
              ))}
            </Table>
          </Panel>
        )}

        <Panel title="Jaw blanks" dense>
          {blanks.length === 0 ? (
            <div className="p-4">
              <p className="text-[12px] text-muted">
                No jaw blanks on hand. The soft jaw generator needs a blank size to work from.
              </p>
            </div>
          ) : (
            <Table head={["Material", "Width", "Height", "Thickness", "Bolt pattern", "On hand"]}>
              {blanks.map((b) => (
                <tr key={b.id} className="hover:bg-raised">
                  <Td>{b.material.replace(/_/g, " ")}</Td>
                  <Td>{b.width.toFixed(2)}″</Td>
                  <Td>{b.height.toFixed(2)}″</Td>
                  <Td>{b.thickness.toFixed(2)}″</Td>
                  <Td muted>{b.boltPattern}</Td>
                  <Td>{b.quantityOnHand}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Panel>

        <Notice tone="precision" title="Fixture collision checking">
          CANVAS evaluates grip, engagement, projection and holder reach analytically. It does not perform swept-volume
          collision detection against fixture CAD — no device here has a CAD representation, and CANVAS will not imply a
          check it has not run.
        </Notice>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

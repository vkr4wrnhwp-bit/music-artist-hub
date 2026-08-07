import { requireUser } from "@/lib/auth";
import { getMachines } from "@/lib/data";
import { TopBar } from "@/components/nav";
import { EmptyState, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

export default async function MachinesPage() {
  const user = await requireUser();
  const machines = await getMachines(user.organizationId);

  return (
    <>
      <TopBar>
        <span className="tech-label">Machines</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-6">
        <SectionHeading sub="Machine profiles are hard constraints. CANVAS validates travel, spindle limits, tool capacity and post-processor against these values — it never assumes a capability that is not recorded here.">
          Machines
        </SectionHeading>

        {machines.length === 0 ? (
          <EmptyState
            title="No machine selected"
            body="Add a machine before CANVAS can validate travel, spindle limits or post-processing."
            action={{ label: "Add machine", href: "/machines/new" }}
          />
        ) : (
          <div className="space-y-6">
            {machines.map((m) => (
              <Panel
                key={m.id}
                title={`${m.manufacturer} ${m.model}`}
                meta={
                  <span className="flex gap-2">
                    <StatusChip tone="neutral">{m.machineType.replace(/_/g, " ")}</StatusChip>
                    <StatusChip tone="neutral">{m.controller.replace(/_/g, " ")}</StatusChip>
                    {m.isReferenceProfile && <StatusChip tone="review">Reference profile</StatusChip>}
                  </span>
                }
                dense
              >
                <div className="grid gap-px bg-line md:grid-cols-3">
                  <Spec
                    label="Travels"
                    rows={[
                      ["X", `${m.travelsX}″`],
                      ["Y", `${m.travelsY}″`],
                      ["Z", `${m.travelsZ}″`],
                      ["Table", `${m.tableX}″ × ${m.tableY}″`],
                    ]}
                  />
                  <Spec
                    label="Spindle & feed"
                    rows={[
                      ["Max RPM", String(m.maxSpindleRPM)],
                      ["Power", `${m.maxSpindlePower} hp`],
                      ["Torque", `${m.maxSpindleTorque} lb-ft`],
                      ["Max feed", `${m.maxFeed} ipm`],
                      ["Rapid", `${m.maxRapid} ipm`],
                    ]}
                  />
                  <Spec
                    label="Tooling & options"
                    rows={[
                      ["Changer", `${m.toolChangerCapacity} pockets`],
                      ["Max tool ⌀", `${m.maxToolDiameter}″`],
                      ["Max tool length", `${m.maxToolLength}″`],
                      ["Probe", m.probe ? "Yes" : "No"],
                      ["Tool setter", m.toolSetter ? "Yes" : "No"],
                      ["Through coolant", m.throughSpindleCoolant ? "Yes" : "No"],
                      ["Post", m.supportedPostProcessor],
                    ]}
                  />
                </div>
                {m.notes && (
                  <p className="border-t border-line px-4 py-3 text-[12px] leading-relaxed text-muted">{m.notes}</p>
                )}
              </Panel>
            ))}
          </div>
        )}
      </main>
    </>
  );
}

function Spec({ label, rows }: { label: string; rows: [string, string][] }) {
  return (
    <div className="bg-surface p-4">
      <p className="tech-label mb-2">{label}</p>
      <table className="w-full">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td className="py-1 pr-4 font-mono text-[11px] text-muted">{k}</td>
              <td className="py-1 text-right font-mono text-[12px] text-platinum">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const dynamic = "force-dynamic";

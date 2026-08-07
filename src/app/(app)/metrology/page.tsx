import { requireUser } from "@/lib/auth";
import { getMetrology } from "@/lib/data";
import { METROLOGY_LABELS } from "@/lib/domain/shop";
import { TopBar } from "@/components/nav";
import { EmptyState, Notice, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

export default async function MetrologyPage() {
  const user = await requireUser();
  const devices = await getMetrology(user.organizationId);

  return (
    <>
      <TopBar>
        <span className="tech-label">Metrology</span>
      </TopBar>
      <main className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-6">
        <SectionHeading sub="CANVAS designs measurement instructions around the instruments you actually own. Instrument uncertainty also sets how confidently a measurement can be matched to a standard nominal value — a caliper reading cannot resolve a 40 mm bearing seat the way a bore gauge can.">
          Metrology
        </SectionHeading>

        {devices.length === 0 ? (
          <EmptyState
            title="No inspection equipment recorded"
            body="Guided measurement and inspection planning both depend on knowing what you can measure with. Add your instruments before starting a reverse engineering session."
            action={{ label: "Add instrument", href: "/metrology/new" }}
          />
        ) : (
          <Panel title={`${devices.length} instruments`} dense>
            <Table head={["Instrument", "Range", "Resolution", "Uncertainty", "Calibration"]}>
              {devices.map((d) => (
                <tr key={d.id} className="hover:bg-raised">
                  <Td className="text-platinum">{d.description}</Td>
                  <Td muted>
                    {d.rangeMin != null && d.rangeMax != null ? `${d.rangeMin}–${d.rangeMax}″` : "—"}
                  </Td>
                  <Td>{d.resolution.toFixed(5)}″</Td>
                  <Td className="text-precision">±{d.uncertainty.toFixed(5)}″</Td>
                  <Td>
                    <StatusChip tone={d.calibrated ? "pass" : "review"}>
                      {d.calibrated ? "Calibrated" : "Not calibrated"}
                    </StatusChip>
                  </Td>
                </tr>
              ))}
            </Table>
          </Panel>
        )}

        <Notice tone="precision" title="Why uncertainty matters here">
          Nominal reasoning compares a measurement against published bearing, thread, dowel and stock tables. The
          confidence it reports is derived from the deviation relative to the instrument&apos;s uncertainty — so the same
          reading taken with calipers and with a bore gauge produce genuinely different conclusions.
        </Notice>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

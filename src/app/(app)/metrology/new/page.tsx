import Link from "next/link";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { METROLOGY_DEVICES, METROLOGY_LABELS, DEVICE_UNCERTAINTY } from "@/lib/domain/shop";
import { FormReader, rejectionQuery } from "@/lib/shop-form";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";

/**
 * Add an instrument.
 *
 * Uncertainty is the field that matters here and the one a shop is most
 * tempted to skip, so it is required and it is not pre-filled. It is the
 * number `assessCapability` divides the tolerance band by; get it wrong and
 * every inspection-capability verdict in the shop is wrong with it. The
 * hint names the typical figure for the chosen class of instrument as a
 * sanity check, but typing it is the operator's decision — CANVAS will not
 * fill in an uncertainty it did not observe.
 */
export default async function NewInstrumentPage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  await requireUser();

  async function createInstrument(formData: FormData): Promise<void> {
    "use server";
    const user = await requireUser();
    const f = new FormReader(formData);

    const rangeMin = f.optionalNumber("rangeMin", "Range min", { min: 0 });
    const rangeMax = f.optionalNumber("rangeMax", "Range max", { min: 0 });
    const data = {
      deviceType: f.choice("deviceType", "Instrument", METROLOGY_DEVICES),
      description: f.text("description", "Description"),
      rangeMin,
      rangeMax,
      resolution: f.number("resolution", "Resolution", { min: 0 }),
      uncertainty: f.number("uncertainty", "Uncertainty", { min: 0 }),
      calibrated: f.boolean("calibrated"),
      calibrationDue: null as Date | null,
    };
    const due = f.optionalText("calibrationDue");
    if (due) {
      const d = new Date(due);
      if (Number.isNaN(d.getTime())) f.optionalNumber("__bad", "Calibration due date");
      else data.calibrationDue = d;
    }
    f.requireOrder(rangeMin, rangeMax, "Range");

    try {
      f.done();
    } catch (err) {
      redirect(`/metrology/new${rejectionQuery(err)}`);
    }

    const row = await db.metrologyDevice.create({ data: { ...data, organizationId: user.organizationId } });
    await audit({
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "MetrologyDevice",
      entityId: row.id,
      action: "CREATE",
      actorType: "HUMAN",
      field: "instrument",
      newValue: `${data.description} · ±${data.uncertainty} · ${data.calibrated ? "calibrated" : "not calibrated"}`,
      reason: "Instrument added to the shop's metrology list.",
    });
    revalidatePath("/metrology");
    redirect("/metrology");
  }

  return (
    <>
      <TopBar>
        <Link href="/metrology" className="tech-label hover:text-platinum">
          Metrology
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New instrument</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="CANVAS designs measurement instructions around the instruments you actually own, and decides whether a tolerance can be verified at all by dividing its band by this instrument's uncertainty. An instrument that is not on this list cannot be recommended.">
            Add an instrument
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm
            action={createInstrument}
            submitLabel="Add instrument"
            cancelHref="/metrology"
            sections={[
              {
                title: "Instrument",
                fields: [
                  {
                    name: "deviceType",
                    label: "Type",
                    kind: "select",
                    required: true,
                    half: true,
                    options: METROLOGY_DEVICES.map((d) => ({ value: d, label: METROLOGY_LABELS[d] })),
                    defaultValue: "DIGITAL_CALIPER",
                  },
                  {
                    name: "description",
                    label: "Description",
                    kind: "text",
                    required: true,
                    half: true,
                    placeholder: '0–6" digital calipers',
                  },
                  { name: "rangeMin", label: "Range min", unit: "in", kind: "number", min: "0", half: true, hint: "Leave blank for an instrument with no stated range, such as a surface plate." },
                  { name: "rangeMax", label: "Range max", unit: "in", kind: "number", min: "0", half: true },
                ],
              },
              {
                title: "What it can actually resolve",
                note: "Resolution is the smallest division it displays. Uncertainty is how much the reading could be wrong in shop conditions — a larger number, and the one the capability verdict is computed from.",
                fields: [
                  { name: "resolution", label: "Resolution", unit: "in", kind: "number", required: true, min: "0", half: true, placeholder: "0.0005" },
                  {
                    name: "uncertainty",
                    label: "Expanded uncertainty",
                    unit: "± in",
                    kind: "number",
                    required: true,
                    min: "0",
                    half: true,
                    hint: `Typical figures by class, for a sanity check only: ${METROLOGY_DEVICES.slice(0, 6)
                      .map((d) => `${METROLOGY_LABELS[d]} ±${DEVICE_UNCERTAINTY[d]}`)
                      .join(", ")}. Enter what this instrument achieves, not what the class usually does.`,
                  },
                ],
              },
              {
                title: "Calibration",
                note: "An instrument that is out of calibration still measures — it just cannot be evidence. CANVAS shows the state rather than hiding the instrument.",
                fields: [
                  { name: "calibrated", label: "Calibration certificate is current", kind: "checkbox", half: true },
                  { name: "calibrationDue", label: "Calibration due", kind: "text", half: true, placeholder: "2027-03-01", hint: "ISO date. Blank means no certificate date is recorded." },
                ],
              },
            ]}
          />

          <Notice tone="review" title="Uncertainty is not a formality">
            It is the denominator in every inspection-capability verdict this shop will see. A caliper entered at
            ±0.0002 will be called capable of a bore it cannot verify, and the gate that exists to catch that will
            pass. Enter the figure you can defend.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

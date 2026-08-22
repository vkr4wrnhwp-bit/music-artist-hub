import Link from "next/link";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { WORKHOLDING_TYPES } from "@/lib/domain/shop";
import { FormReader, rejectionQuery } from "@/lib/shop-form";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";

const title = (s: string) => s.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());

/**
 * Add a workholding device.
 *
 * Clamp force is optional here and that is deliberate. Most shops do not
 * know what their vise actually applies, and `assessHoldingMargin` handles
 * that honestly: no clamp force means the margin comes back INDETERMINATE
 * with "clamp force not recorded" named as the missing input. Requiring the
 * field would push people to type a catalogue number they have not measured,
 * which converts an honest INDETERMINATE into a confident wrong answer.
 */
export default async function NewWorkholdingPage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  await requireUser();

  async function createDevice(formData: FormData): Promise<void> {
    "use server";
    const user = await requireUser();
    const f = new FormReader(formData);

    const data = {
      type: f.choice("type", "Type", WORKHOLDING_TYPES),
      manufacturer: f.optionalText("manufacturer"),
      model: f.optionalText("model"),
      description: f.text("description", "Description"),
      jawWidth: f.number("jawWidth", "Jaw width", { min: 0 }),
      jawHeight: f.number("jawHeight", "Jaw height", { min: 0 }),
      maxOpening: f.number("maxOpening", "Maximum opening", { min: 0 }),
      clampForce: f.optionalNumber("clampForce", "Clamp force", { min: 0 }),
      fixtureHeight: f.number("fixtureHeight", "Fixture height", { min: 0 }),
      mountingGeometry: f.optionalText("mountingGeometry"),
      notes: f.optionalText("notes"),
    };

    try {
      f.done();
    } catch (err) {
      redirect(`/workholding/new${rejectionQuery(err)}`);
    }

    const row = await db.workholdingDevice.create({ data: { ...data, organizationId: user.organizationId } });
    await audit({
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "WorkholdingDevice",
      entityId: row.id,
      action: "CREATE",
      actorType: "HUMAN",
      field: "workholding device",
      newValue: `${title(data.type)} · ${data.description} · jaw ${data.jawWidth}×${data.jawHeight}`,
      reason: "Workholding device added to the shop.",
    });
    revalidatePath("/workholding");
    redirect("/workholding");
  }

  return (
    <>
      <TopBar>
        <Link href="/workholding" className="tech-label hover:text-platinum">
          Workholding
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New device</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="Jaw geometry sets how much of the part can be gripped and how much has to stand proud of the jaws. Both feed the holding margin, and neither can be inferred from the part.">
            Add a workholding device
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm
            action={createDevice}
            submitLabel="Add device"
            cancelHref="/workholding"
            sections={[
              {
                title: "Identity",
                fields: [
                  {
                    name: "type",
                    label: "Type",
                    kind: "select",
                    required: true,
                    half: true,
                    options: WORKHOLDING_TYPES.map((t) => ({ value: t, label: title(t) })),
                    defaultValue: "VISE",
                  },
                  { name: "description", label: "Description", kind: "text", required: true, half: true, placeholder: '6" precision milling vise' },
                  { name: "manufacturer", label: "Manufacturer", kind: "text", half: true },
                  { name: "model", label: "Model", kind: "text", half: true },
                ],
              },
              {
                title: "Geometry",
                note: "Grip depth and stock projection are checked against jaw height. A part standing proud of the jaws is the lever arm that rolls it out of the vise.",
                fields: [
                  { name: "jawWidth", label: "Jaw width", unit: "in", kind: "number", required: true, min: "0", half: true },
                  { name: "jawHeight", label: "Jaw height", unit: "in", kind: "number", required: true, min: "0", half: true },
                  { name: "maxOpening", label: "Maximum opening", unit: "in", kind: "number", required: true, min: "0", half: true },
                  { name: "fixtureHeight", label: "Fixture height", unit: "in", kind: "number", required: true, min: "0", half: true, hint: "Base to the top of the jaws. Checked against Z travel." },
                  { name: "mountingGeometry", label: "Mounting", kind: "text", half: true, placeholder: "Table T-slots, 4 bolts" },
                ],
              },
              {
                title: "Clamping",
                note: "Left blank, the holding margin comes back INDETERMINATE and names clamp force as the input it wanted. That is the correct answer for a vise nobody has measured — better than a catalogue figure entered as though it were observed.",
                fields: [
                  { name: "clampForce", label: "Clamp force", unit: "lbf", kind: "number", min: "0", half: true, hint: "Measured or from a torque-to-force chart for the handle torque actually used." },
                  { name: "notes", label: "Notes", kind: "textarea" },
                ],
              },
            ]}
          />
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

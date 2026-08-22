import Link from "next/link";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { FormReader, rejectionQuery } from "@/lib/shop-form";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";

const FAMILIES = [
  "ALUMINUM",
  "STEEL",
  "STAINLESS",
  "TOOL_STEEL",
  "TITANIUM",
  "BRASS",
  "BRONZE",
  "COPPER",
  "CAST_IRON",
  "PLASTIC",
  "COMPOSITE",
  "OTHER",
] as const;

const title = (s: string) => s.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());

/**
 * Add a material.
 *
 * Strength properties are optional and stay that way. `process-advisor.ts`
 * and the load reasoning read yield and tensile strength, and where they are
 * missing they say which figure they needed rather than substituting one for
 * "6061-ish". A material record with a blank yield strength is a material
 * CANVAS will not size a load against — which is the correct behaviour, and
 * strictly better than one it will size against a number nobody sourced.
 *
 * Specific cutting energy is required, because the cutting force model
 * divides by it on every operation and there is no sane fallback: aluminium
 * is about 0.3 hp/in³/min and steel about 1.0, a factor of three that lands
 * directly in the spindle load estimate.
 */
export default async function NewMaterialPage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  await requireUser();

  async function createMaterial(formData: FormData): Promise<void> {
    "use server";
    const user = await requireUser();
    const f = new FormReader(formData);

    const sfmMin = f.number("sfmCarbideMin", "Carbide surface speed min", { min: 0 });
    const sfmMax = f.number("sfmCarbideMax", "Carbide surface speed max", { min: 0 });
    const data = {
      name: f.text("name", "Name"),
      family: f.choice("family", "Family", FAMILIES),
      condition: f.text("condition", "Condition"),
      density: f.number("density", "Density", { min: 0 }),
      hardness: f.optionalNumber("hardness", "Hardness", { min: 0 }),
      yieldStrength: f.optionalNumber("yieldStrength", "Yield strength", { min: 0 }),
      tensileStrength: f.optionalNumber("tensileStrength", "Tensile strength", { min: 0 }),
      machinabilityRating: f.number("machinabilityRating", "Machinability rating", { min: 0 }),
      sfmCarbideMin: sfmMin,
      sfmCarbideMax: sfmMax,
      specificEnergy: f.number("specificEnergy", "Specific cutting energy", { min: 0 }),
      costPerPound: f.number("costPerPound", "Cost per pound", { min: 0 }),
      weldable: f.boolean("weldable"),
      castable: f.boolean("castable"),
      notes: f.optionalText("notes"),
    };
    f.requireOrder(sfmMin, sfmMax, "Carbide surface speed");

    try {
      f.done();
    } catch (err) {
      redirect(`/materials/new${rejectionQuery(err)}`);
    }

    const row = await db.material.create({ data: { ...data, organizationId: user.organizationId } });
    await audit({
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "Material",
      entityId: row.id,
      action: "CREATE",
      actorType: "HUMAN",
      field: "material",
      newValue: `${data.name} (${title(data.family)}, ${data.condition}) · ${data.specificEnergy} hp/in³/min`,
      reason: "Material added to the shop's list.",
    });
    revalidatePath("/materials");
    redirect("/materials");
  }

  return (
    <>
      <TopBar>
        <Link href="/materials" className="tech-label hover:text-platinum">
          Materials
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New material</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="Condition matters as much as alloy. 6061-T6 and 6061-O are the same alloy and do not cut, hold or load the same way, so the condition is a field rather than part of the name.">
            Add a material
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm
            action={createMaterial}
            submitLabel="Add material"
            cancelHref="/materials"
            sections={[
              {
                title: "Identity",
                fields: [
                  { name: "name", label: "Name", kind: "text", required: true, half: true, placeholder: "Aluminum 6061" },
                  {
                    name: "family",
                    label: "Family",
                    kind: "select",
                    required: true,
                    half: true,
                    options: FAMILIES.map((x) => ({ value: x, label: title(x) })),
                    defaultValue: "ALUMINUM",
                  },
                  { name: "condition", label: "Condition / temper", kind: "text", required: true, half: true, placeholder: "T6" },
                  { name: "density", label: "Density", unit: "lb/in³", kind: "number", required: true, min: "0", half: true, placeholder: "0.098" },
                ],
              },
              {
                title: "Cutting behaviour",
                note: "Specific cutting energy is what the force model divides by on every operation — aluminium is about 0.3 hp/in³/min and steel about 1.0. There is no safe default across that range, so it is required.",
                fields: [
                  { name: "specificEnergy", label: "Specific cutting energy", unit: "hp/in³/min", kind: "number", required: true, min: "0", half: true, placeholder: "0.3" },
                  { name: "machinabilityRating", label: "Machinability rating", unit: "% of B1112", kind: "number", required: true, min: "0", half: true, placeholder: "190" },
                  { name: "sfmCarbideMin", label: "Carbide surface speed min", unit: "sfm", kind: "number", required: true, min: "0", half: true },
                  { name: "sfmCarbideMax", label: "Carbide surface speed max", unit: "sfm", kind: "number", required: true, min: "0", half: true },
                ],
              },
              {
                title: "Strength",
                note: "Optional, and left blank means not recorded. CANVAS will then decline to size a load against this material and name the figure it wanted, rather than borrowing one from a similar alloy.",
                fields: [
                  { name: "hardness", label: "Hardness", unit: "HB", kind: "number", min: "0", half: true },
                  { name: "yieldStrength", label: "Yield strength", unit: "psi", kind: "number", min: "0", half: true },
                  { name: "tensileStrength", label: "Tensile strength", unit: "psi", kind: "number", min: "0", half: true },
                  { name: "costPerPound", label: "Cost per pound", unit: "currency", kind: "number", required: true, min: "0", half: true },
                ],
              },
              {
                title: "Process compatibility",
                note: "Read by process recommendation. CANVAS does not assume CNC machining is the answer, and these decide which alternatives it is allowed to raise at all.",
                fields: [
                  { name: "weldable", label: "Weldable", kind: "checkbox", half: true },
                  { name: "castable", label: "Castable", kind: "checkbox", half: true },
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

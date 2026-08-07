import { redirect } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { TopBar } from "@/components/nav";
import { Button, Field, Notice, Panel, SectionHeading, inputClass } from "@/components/ui";

const BUSINESS_TYPES = [
  "JOB_SHOP",
  "AEROSPACE",
  "AUTOMOTIVE",
  "MOTORSPORTS",
  "MEDICAL",
  "ROBOTICS",
  "DEFENSE",
  "MARINE",
  "OIL_AND_GAS",
  "INDUSTRIAL",
  "CONSUMER",
  "R_AND_D",
  "OTHER",
];

/**
 * Onboarding exists to make CANVAS useful on day one, not to collect a
 * profile. Every question here changes what the system can validate: without
 * typical tolerance it cannot flag an unusual callout, without bottlenecks it
 * cannot know what is worth optimising.
 */
export default async function OnboardingPage() {
  const user = await requireUser();
  const org = await db.organization.findUnique({ where: { id: user.organizationId } });
  if (!org) redirect("/");

  async function save(formData: FormData) {
    "use server";
    const currentUser = await requireUser();

    const list = (k: string) =>
      String(formData.get(k) ?? "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

    await db.organization.update({
      where: { id: currentUser.organizationId },
      data: {
        businessType: String(formData.get("businessType") || "OTHER"),
        industry: String(formData.get("businessType") || "OTHER"),
        website: String(formData.get("website") || "") || null,
        typicalTolerance: formData.get("typicalTolerance") ? Number(formData.get("typicalTolerance")) : null,
        typicalQuantity: String(formData.get("typicalQuantity") || "") || null,
        outsourced: JSON.stringify(list("outsourced")),
        bottlenecks: JSON.stringify(list("bottlenecks")),
        onboardingDone: true,
      },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "Organization",
      entityId: currentUser.organizationId,
      action: "UPDATE",
      actorType: "HUMAN",
      reason: "Onboarding completed",
    });

    redirect("/machines");
  }

  return (
    <>
      <TopBar>
        <span className="tech-label">Shop setup</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-6">
          <SectionHeading sub="Six questions. Each one changes what CANVAS can validate, so skipping them means the system is quieter rather than smarter.">
            Tell CANVAS about your shop
          </SectionHeading>

          <form action={save} className="space-y-6">
            <Panel title="Business">
              <div className="space-y-4">
                <Field label="What kind of business do you run?">
                  <select name="businessType" defaultValue={org.businessType ?? "JOB_SHOP"} className={inputClass}>
                    {BUSINESS_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Company website" hint="Stored only. CANVAS does not analyse it — company research is not implemented.">
                  <input name="website" type="url" defaultValue={org.website ?? ""} className={inputClass} />
                </Field>
              </div>
            </Panel>

            <Panel title="Work">
              <div className="space-y-4">
                <Field label="Typical tolerance (in)" hint="CANVAS uses this to flag callouts well outside your normal working band.">
                  <input name="typicalTolerance" type="number" step="0.0001" defaultValue={org.typicalTolerance ?? 0.005} className={inputClass} />
                </Field>
                <Field label="Typical quantities">
                  <select name="typicalQuantity" defaultValue={org.typicalQuantity ?? "1-25"} className={inputClass}>
                    {["1", "1-25", "25-100", "100-1000", "1000+"].map((q) => (
                      <option key={q}>{q}</option>
                    ))}
                  </select>
                </Field>
                <Field label="What do you outsource?" hint="Comma separated. e.g. Anodising, heat treat, grinding.">
                  <input name="outsourced" defaultValue={JSON.parse(org.outsourced ?? "[]").join(", ")} className={inputClass} />
                </Field>
                <Field label="What causes bottlenecks?" hint="Comma separated. This is what CANVAS will look for opportunities to remove.">
                  <input name="bottlenecks" defaultValue={JSON.parse(org.bottlenecks ?? "[]").join(", ")} className={inputClass} />
                </Field>
              </div>
            </Panel>

            <Notice tone="precision" title="Next: your equipment">
              Machines, tooling, workholding and metrology are the hard constraints CANVAS validates against. Nothing is
              assumed — a capability you do not record does not exist to the planner.
            </Notice>

            <Button type="submit" variant="primary">
              Save and add equipment
            </Button>
          </form>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

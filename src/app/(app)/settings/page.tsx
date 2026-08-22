import { redirect } from "next/navigation";
import { requireUser, destroySession } from "@/lib/auth";
import { db } from "@/lib/db";
import { auditChanges } from "@/lib/audit";
import { getShopSettings } from "@/lib/data";
import { getAiProvider } from "@/lib/ai/provider";
import { TopBar } from "@/components/nav";
import { Button, DataRow, Field, Notice, Panel, SectionHeading, StatusChip, inputClass } from "@/components/ui";
import { DensityToggle } from "@/components/density";

export default async function SettingsPage() {
  const user = await requireUser();
  const [shop, org, ai, auditCount] = await Promise.all([
    getShopSettings(user.organizationId),
    db.organization.findUnique({ where: { id: user.organizationId } }),
    getAiProvider(),
    db.auditLog.count({ where: { organizationId: user.organizationId } }),
  ]);

  async function saveRates(formData: FormData) {
    "use server";
    const currentUser = await requireUser();
    const existing = await db.shop.findFirst({ where: { organizationId: currentUser.organizationId } });

    const data = {
      machineRate: Number(formData.get("machineRate")),
      operatorRate: Number(formData.get("operatorRate")),
      inspectionRate: Number(formData.get("inspectionRate")),
      overheadRate: Number(formData.get("overheadRate")) / 100,
      marginRate: Number(formData.get("marginRate")) / 100,
      shiftHours: Number(formData.get("shiftHours")),
    };

    if (existing) {
      await db.shop.update({ where: { id: existing.id }, data });
    } else {
      await db.shop.create({ data: { organizationId: currentUser.organizationId, name: "Main floor", ...data } });
    }

    await auditChanges(
      {
        organizationId: currentUser.organizationId,
        userId: currentUser.id,
        entityType: "Shop",
        entityId: existing?.id ?? "new",
        actorType: "HUMAN",
        reason: "Shop rates updated",
      },
      (existing ?? {}) as Record<string, unknown>,
      data as Record<string, unknown>,
    );

    redirect("/settings");
  }

  async function signOut() {
    "use server";
    await destroySession();
    redirect("/sign-in");
  }

  return (
    <>
      <TopBar>
        <span className="tech-label">Settings</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="Rates here drive every cost estimate and quote in the system. They are stored with each estimate, so changing them does not silently rewrite quotes you have already sent.">
            Settings
          </SectionHeading>
          <Panel title="Display density">
            <p className="mb-2 text-[11.5px] leading-relaxed text-muted">
              COMPACT tightens panel chrome, data rows and table cells for smaller screens and denser review work. Type hierarchy and color are untouched — density is spacing, not a different design. Stored on this device.
            </p>
            <DensityToggle />
          </Panel>


          <Panel title="Organisation">
            <DataRow label="Name" value={org?.name ?? "—"} />
            <DataRow label="Business type" value={org?.businessType ?? "Not stated"} />
            <DataRow label="Network participation" value={org?.defaultSharing ?? "PRIVATE"} />
            <DataRow label="Signed in as" value={`${user.name} · ${user.role}`} />
            <DataRow label="Audit entries" value={String(auditCount)} />
          </Panel>

          <Panel title="Shop rates">
            <form action={saveRates} className="grid gap-4 sm:grid-cols-2">
              <Field label="Machine rate ($/hr)" hint="Burdened rate including the machine, floor space and power.">
                <input name="machineRate" type="number" step="0.5" defaultValue={shop.machineRate} className={inputClass} />
              </Field>
              <Field label="Operator rate ($/hr)">
                <input name="operatorRate" type="number" step="0.5" defaultValue={shop.operatorRate} className={inputClass} />
              </Field>
              <Field label="Inspection rate ($/hr)">
                <input name="inspectionRate" type="number" step="0.5" defaultValue={shop.inspectionRate} className={inputClass} />
              </Field>
              <Field label="Shift hours">
                <input name="shiftHours" type="number" step="0.5" defaultValue={shop.shiftHours} className={inputClass} />
              </Field>
              <Field label="Overhead (%)">
                <input name="overheadRate" type="number" min="0" max="500" defaultValue={(shop.overheadRate * 100).toFixed(1)} className={inputClass} />
              </Field>
              <Field
                label="Target margin (%)"
                hint="Applied to price, not marked up on cost — so it cannot reach 100%. A 100% markup is a 50% margin."
              >
                <input name="marginRate" type="number" min="0" max="95" defaultValue={(shop.marginRate * 100).toFixed(1)} className={inputClass} />
              </Field>
              <div className="sm:col-span-2">
                <Button type="submit" variant="primary">
                  Save rates
                </Button>
              </div>
            </form>
          </Panel>

          <Panel title="AI provider">
            <DataRow label="Active provider" value={ai.label} />
            <DataRow
              label="Remote model"
              value={ai.usesRemoteModel ? "Yes — requests leave this server" : "No — fully local"}
            />
            <p className="mt-3 text-[12px] leading-relaxed text-muted">
              CANVAS runs on a deterministic parser by default: no API key, no network, and manufacturing intake still
              works. Set <span className="font-mono text-platinum-dim">CANVAS_AI_PROVIDER=anthropic</span> and{" "}
              <span className="font-mono text-platinum-dim">ANTHROPIC_API_KEY</span> server-side to enable the full
              copilot. Keys are read from the environment and never reach the browser.
            </p>
          </Panel>

          <Notice tone="review" title="What the AI layer is never allowed to do">
            It never emits machine motion, never invents a machine or tool you do not own, and never satisfies a
            manufacturing gate on its own. Every suggestion is recorded as a proposal with an explicit accept or reject
            by a named human.
          </Notice>

          <form action={signOut}>
            <Button type="submit" variant="danger">
              Sign out
            </Button>
          </form>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

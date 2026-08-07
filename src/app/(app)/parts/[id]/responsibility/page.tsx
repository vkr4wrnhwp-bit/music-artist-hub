import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { auditChanges } from "@/lib/audit";
import { loadRevision } from "@/lib/data";
import { ENVIRONMENTS, FAILURE_CONSEQUENCE, LOADING_TYPES, PRODUCTION_INTENT } from "@/lib/domain/part-intent";
import { userValue } from "@/lib/provenance";
import { TopBar } from "@/components/nav";
import { Button, Field, Notice, Panel, SectionHeading, inputClass } from "@/components/ui";

const LOADING_LABEL: Record<string, string> = {
  STATIC: "Static load",
  CYCLIC: "Cyclic / fatigue",
  SHOCK: "Shock",
  IMPACT: "Impact",
  VIBRATION: "Vibration",
  TORSION: "Torsion",
  BENDING: "Bending",
  PRESSURE: "Pressure containment",
  THERMAL_CYCLING: "Thermal cycling",
};

const ENV_LABEL: Record<string, string> = {
  INDOOR_DRY: "Indoor, dry",
  OUTDOOR: "Outdoor",
  MARINE: "Marine",
  HIGH_TEMP: "High temperature",
  CRYOGENIC: "Cryogenic",
  CHEMICAL: "Chemical exposure",
  FOOD_CONTACT: "Food contact",
  VACUUM: "Vacuum",
  ABRASIVE: "Abrasive",
};

const CONSEQUENCE_DESC: Record<string, string> = {
  LOW: "Cosmetic or inconvenience only",
  MEDIUM: "Equipment downtime or product damage",
  HIGH: "Major equipment damage",
  CRITICAL: "Potential injury, life safety, flight, automotive safety or pressure containment",
};

export default async function ResponsibilityPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) notFound();

  const profile = await db.partResponsibilityProfile.findUnique({
    where: { partRevisionId: revision.revisionId },
  });

  async function save(formData: FormData) {
    "use server";
    const currentUser = await requireUser();
    const rev = await loadRevision(currentUser.organizationId, id);
    if (!rev) notFound();

    const bool = (k: string) => {
      const v = formData.get(k);
      return v === "yes" ? true : v === "no" ? false : null;
    };
    const num = (k: string) => {
      const v = formData.get(k);
      return v ? Number(v) : null;
    };
    const list = (k: string) => formData.getAll(k).map(String);

    const loadBearing = bool("loadBearing");
    const safetyCritical = bool("safetyCritical");
    const failureConsequence = (formData.get("failureConsequence") as string) || null;

    const before = await db.partResponsibilityProfile.findUnique({ where: { partRevisionId: rev.revisionId } });

    const data = {
      loadBearing,
      safetyCritical,
      failureConsequence,
      loadingTypes: JSON.stringify(list("loadingTypes")),
      environments: JSON.stringify(list("environments")),
      temperatureMin: num("temperatureMin"),
      temperatureMax: num("temperatureMax"),
      serviceLifeYears: num("serviceLifeYears"),
      productionIntent: (formData.get("productionIntent") as string) || null,
      annualVolume: num("annualVolume") ? Math.round(num("annualVolume")!) : null,
      regulatory: JSON.stringify(
        String(formData.get("regulatory") ?? "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      ),
      materialCertRequired: bool("materialCertRequired"),
      traceabilityRequired: bool("traceabilityRequired"),
      answeredBy: currentUser.id,
      answeredAt: new Date(),
    };

    await db.partResponsibilityProfile.upsert({
      where: { partRevisionId: rev.revisionId },
      create: { partRevisionId: rev.revisionId, ...data },
      update: data,
    });

    // The intent model mirrors the answers, marked USER-confirmed — these are
    // stated facts from a human, not inference, and the process advisor
    // depends on that distinction.
    const intent = { ...rev.intent };
    if (loadBearing !== null) intent.loadBearing = userValue(loadBearing);
    if (safetyCritical !== null) intent.safetyCritical = userValue(safetyCritical);
    if (failureConsequence) intent.failureConsequence = userValue(failureConsequence as never);
    if (list("loadingTypes").length) intent.loadingType = userValue(list("loadingTypes") as never);
    if (list("environments").length) intent.environment = userValue(list("environments") as never);
    if (data.productionIntent) intent.productionIntent = userValue(data.productionIntent as never);
    if (data.annualVolume) intent.annualVolume = userValue(data.annualVolume);
    if (data.temperatureMin !== null && data.temperatureMax !== null) {
      intent.temperatureRange = userValue({ min: data.temperatureMin, max: data.temperatureMax });
    }
    intent.unknowns = intent.unknowns.filter(
      (u) => !u.toLowerCase().includes("responsibility") && !u.toLowerCase().includes("functional"),
    );

    await db.partRevision.update({
      where: { id: rev.revisionId },
      data: { intentJson: JSON.stringify(intent) },
    });

    await auditChanges(
      {
        organizationId: currentUser.organizationId,
        userId: currentUser.id,
        entityType: "PartResponsibilityProfile",
        entityId: rev.revisionId,
        actorType: "HUMAN",
        reason: "Responsibility interview answered",
      },
      (before ?? {}) as Record<string, unknown>,
      data as Record<string, unknown>,
    );

    redirect(`/parts/${id}`);
  }

  const loadingTypes: string[] = JSON.parse(profile?.loadingTypes ?? "[]");
  const environments: string[] = JSON.parse(profile?.environments ?? "[]");

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Responsibility</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-2xl">
          <SectionHeading sub="CANVAS will not recommend an alternative manufacturing method without understanding what the part is responsible for. Switching a fatigue-loaded billet part to a casting is a materials decision, not a cost decision, and it needs these answers first.">
            Part responsibility profile
          </SectionHeading>

          <form action={save} className="space-y-6">
            <Panel title="Function">
              <div className="space-y-4">
                <YesNo name="loadBearing" label="Is this part load bearing?" value={profile?.loadBearing} />
                <YesNo
                  name="safetyCritical"
                  label="Is this part safety critical?"
                  hint="A failure could injure someone, or the part is in a flight, automotive safety, medical or pressure-containing application."
                  value={profile?.safetyCritical}
                />
                <Field label="What loading does it experience?" hint="Select every case that applies.">
                  <div className="grid grid-cols-2 gap-1.5">
                    {LOADING_TYPES.map((t) => (
                      <Check key={t} name="loadingTypes" value={t} label={LOADING_LABEL[t]} checked={loadingTypes.includes(t)} />
                    ))}
                  </div>
                </Field>
              </div>
            </Panel>

            <Panel title="Consequence of failure">
              <div className="space-y-2">
                {FAILURE_CONSEQUENCE.map((c) => (
                  <label key={c} className="flex cursor-pointer items-start gap-2.5 border border-line px-3 py-2 hover:border-line-strong">
                    <input
                      type="radio"
                      name="failureConsequence"
                      value={c}
                      defaultChecked={profile?.failureConsequence === c}
                      className="mt-0.5 accent-[color:var(--c-blue)]"
                    />
                    <span>
                      <span className={`block font-mono text-[11px] uppercase tracking-[0.14em] ${c === "CRITICAL" ? "text-risk" : c === "HIGH" ? "text-review" : "text-platinum"}`}>
                        {c}
                      </span>
                      <span className="text-[12px] text-muted">{CONSEQUENCE_DESC[c]}</span>
                    </span>
                  </label>
                ))}
              </div>
            </Panel>

            <Panel title="Service environment">
              <div className="space-y-4">
                <Field label="Environment">
                  <div className="grid grid-cols-2 gap-1.5">
                    {ENVIRONMENTS.map((e) => (
                      <Check key={e} name="environments" value={e} label={ENV_LABEL[e]} checked={environments.includes(e)} />
                    ))}
                  </div>
                </Field>
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Min temperature (°F)">
                    <input name="temperatureMin" type="number" className={inputClass} defaultValue={profile?.temperatureMin ?? ""} />
                  </Field>
                  <Field label="Max temperature (°F)">
                    <input name="temperatureMax" type="number" className={inputClass} defaultValue={profile?.temperatureMax ?? ""} />
                  </Field>
                </div>
                <Field label="Expected service life (years)">
                  <input name="serviceLifeYears" type="number" step="0.1" className={inputClass} defaultValue={profile?.serviceLifeYears ?? ""} />
                </Field>
              </div>
            </Panel>

            <Panel title="Production">
              <div className="space-y-4">
                <Field label="Production intent">
                  <select name="productionIntent" defaultValue={profile?.productionIntent ?? ""} className={inputClass}>
                    <option value="">Not stated</option>
                    {PRODUCTION_INTENT.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Annual volume" hint="This is the single biggest input into whether machining is the right process at all.">
                  <input name="annualVolume" type="number" className={inputClass} defaultValue={profile?.annualVolume ?? ""} />
                </Field>
                <Field label="Regulatory requirements" hint="Comma separated. e.g. AS9100, ITAR, FDA, PED.">
                  <input name="regulatory" className={inputClass} defaultValue={JSON.parse(profile?.regulatory ?? "[]").join(", ")} />
                </Field>
                <YesNo name="materialCertRequired" label="Material certification required?" value={profile?.materialCertRequired} />
                <YesNo name="traceabilityRequired" label="Lot traceability required?" value={profile?.traceabilityRequired} />
              </div>
            </Panel>

            <Notice tone="review" title="Why CANVAS asks">
              These answers gate the manufacturing method advisor and raise the required input set for critical
              components. If you answer &quot;unknown&quot;, CANVAS keeps machining as the working assumption and says so
              — it does not fill the gap with an average.
            </Notice>

            <div className="flex gap-2">
              <Button type="submit" variant="primary">
                Save profile
              </Button>
              <Link href={`/parts/${id}`} className="tech-label self-center hover:text-platinum">
                Cancel
              </Link>
            </div>
          </form>
        </div>
      </main>
    </>
  );
}

function YesNo({ name, label, hint, value }: { name: string; label: string; hint?: string; value?: boolean | null }) {
  return (
    <Field label={label} hint={hint}>
      <div className="flex gap-2">
        {[
          { v: "yes", l: "Yes" },
          { v: "no", l: "No" },
          { v: "", l: "Unknown" },
        ].map((o) => (
          <label key={o.l} className="flex cursor-pointer items-center gap-1.5 border border-line px-2.5 py-1 text-[11px] text-platinum-dim hover:border-line-strong">
            <input
              type="radio"
              name={name}
              value={o.v}
              defaultChecked={value === true ? o.v === "yes" : value === false ? o.v === "no" : o.v === ""}
              className="accent-[color:var(--c-blue)]"
            />
            {o.l}
          </label>
        ))}
      </div>
    </Field>
  );
}

function Check({ name, value, label, checked }: { name: string; value: string; label: string; checked: boolean }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 border border-line px-2 py-1 text-[11.5px] text-platinum-dim hover:border-line-strong">
      <input type="checkbox" name={name} value={value} defaultChecked={checked} className="accent-[color:var(--c-blue)]" />
      {label}
    </label>
  );
}

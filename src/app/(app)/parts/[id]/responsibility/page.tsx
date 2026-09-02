import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { auditChanges } from "@/lib/audit";
import { loadRevision } from "@/lib/data";
import { ENVIRONMENTS, FAILURE_CONSEQUENCE, LOADING_TYPES, PRODUCTION_INTENT } from "@/lib/domain/part-intent";
import { confirmedBy } from "@/lib/provenance";
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
    const currentUser = await requireWrite();
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
    // One stamp for the whole submission, so every answer carries the same
    // moment rather than a scatter of times a few milliseconds apart.
    const answeredAt = new Date();


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
      answeredAt,
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
    if (loadBearing !== null) intent.loadBearing = confirmedBy(loadBearing, currentUser.name, answeredAt, "Part responsibility interview");
    if (safetyCritical !== null) intent.safetyCritical = confirmedBy(safetyCritical, currentUser.name, answeredAt, "Part responsibility interview");
    if (failureConsequence) intent.failureConsequence = confirmedBy(failureConsequence as never, currentUser.name, answeredAt, "Part responsibility interview");
    if (list("loadingTypes").length) intent.loadingType = confirmedBy(list("loadingTypes") as never, currentUser.name, answeredAt, "Part responsibility interview");
    if (list("environments").length) intent.environment = confirmedBy(list("environments") as never, currentUser.name, answeredAt, "Part responsibility interview");
    if (data.productionIntent) intent.productionIntent = confirmedBy(data.productionIntent as never, currentUser.name, answeredAt, "Part responsibility interview");
    if (data.annualVolume) intent.annualVolume = confirmedBy(data.annualVolume, currentUser.name, answeredAt, "Part responsibility interview");
    if (data.temperatureMin !== null && data.temperatureMax !== null) {
      intent.temperatureRange = confirmedBy({ min: data.temperatureMin, max: data.temperatureMax }, currentUser.name, answeredAt, "Part responsibility interview");
    }
    // The critical-part intake fields the Engineering-input gate checks.
    // These were previously unreachable from any form, so "Complete the
    // Part Responsibility Profile" could never actually complete.
    // Baseline inputs. Each is recorded only when actually given: an empty
    // field must leave the gate open, never write a zero that reads as an
    // answer.
    const quantityRaw = String(formData.get("quantity") ?? "").trim();
    const quantity = quantityRaw ? Number(quantityRaw) : null;
    if (quantity !== null && Number.isFinite(quantity) && quantity >= 1) {
      intent.quantity = confirmedBy(Math.round(quantity), currentUser.name, answeredAt, "Part responsibility interview");
    }
    const toleranceRaw = String(formData.get("generalTolerance") ?? "").trim();
    const generalTolerance = toleranceRaw ? Number(toleranceRaw) : null;
    // A zero general tolerance is not a tolerance. Refused rather than stored.
    if (generalTolerance !== null && Number.isFinite(generalTolerance) && generalTolerance > 0) {
      intent.generalTolerance = confirmedBy(generalTolerance, currentUser.name, answeredAt, "Part responsibility interview");
    }

    const envelope = (["X", "Y", "Z"] as const).map((axis) => {
      const raw = String(formData.get(`envelope${axis}`) ?? "").trim();
      return raw ? Number(raw) : null;
    });
    // All three or none. Two axes of a finished envelope is not a smaller
    // envelope, it is an unanswered question.
    if (envelope.every((n) => n !== null && Number.isFinite(n) && n > 0)) {
      intent.finishedEnvelope = confirmedBy({ x: envelope[0]!, y: envelope[1]!, z: envelope[2]! }, currentUser.name, answeredAt, "Part responsibility interview");
    }

    const materialCondition = String(formData.get("materialCondition") ?? "").trim();
    if (materialCondition) intent.materialCondition = confirmedBy(materialCondition, currentUser.name, answeredAt, "Part responsibility interview");
    const surfaceFinish = String(formData.get("surfaceFinish") ?? "").trim();
    if (surfaceFinish) intent.surfaceFinish = confirmedBy(surfaceFinish, currentUser.name, answeredAt, "Part responsibility interview");
    const inspectionReqs = String(formData.get("inspectionRequirements") ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (inspectionReqs.length) intent.inspectionRequirements = confirmedBy(inspectionReqs, currentUser.name, answeredAt, "Part responsibility interview");

    intent.unknowns = intent.unknowns.filter(
      (u) => !u.toLowerCase().includes("responsibility") && !u.toLowerCase().includes("functional"),
    );
    // Explicitly resolved unknowns — a named human checking "resolved" is a
    // USER statement, and each one is audited below. Nothing auto-clears.
    const resolved = formData.getAll("resolveUnknown").map(String);
    if (resolved.length) {
      intent.unknowns = intent.unknowns.filter((u) => !resolved.includes(u));
    }

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
      {
        ...data,
        ...(materialCondition ? { intentMaterialCondition: materialCondition } : {}),
        ...(surfaceFinish ? { intentSurfaceFinish: surfaceFinish } : {}),
        ...(inspectionReqs.length ? { intentInspectionRequirements: inspectionReqs.join(", ") } : {}),
        ...(resolved.length ? { unknownsResolved: resolved.join(" | ") } : {}),
      } as Record<string, unknown>,
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

            {/* The baseline the gate demands of EVERY part, critical or not.
                None of it was askable anywhere in the app: material and stock
                were written once at intake and quantity, general tolerance and
                the finished envelope had no editor at all. So the gate
                reported them missing, recommended "Complete the Part
                Responsibility Profile", and the profile did not ask — fill it
                out, nothing clears, round again. That loop was reported and
                this is the half of it that was still open. */}
            <Panel title="Baseline engineering inputs">
              <p className="mb-3 text-[11.5px] leading-relaxed text-muted">
                The Engineering-input gate requires these of every part. Material and stock come from the stock you
                define on the part page; the rest are stated by you here. A blank leaves the gate open — nothing is
                averaged or assumed.
              </p>
              <div className="space-y-4">
                <Field label="Quantity" hint="How many of this part are being made in this run.">
                  <input
                    name="quantity"
                    type="number"
                    min="1"
                    step="1"
                    className={inputClass}
                    defaultValue={(revision.intent.quantity.value as number | null) ?? ""}
                  />
                </Field>
                <Field
                  label="General tolerance, inches"
                  hint="The drawing's title-block tolerance as a ± value. e.g. 0.005 for ±0.005."
                >
                  <input
                    name="generalTolerance"
                    type="number"
                    step="0.0001"
                    min="0"
                    className={inputClass}
                    defaultValue={(revision.intent.generalTolerance.value as number | null) ?? ""}
                  />
                </Field>
                <Field label="Finished envelope, inches" hint="X × Y × Z of the finished part. Stock smaller than this is refused.">
                  <div className="flex items-center gap-2">
                    {(["x", "y", "z"] as const).map((axis) => (
                      <input
                        key={axis}
                        name={`envelope${axis.toUpperCase()}`}
                        type="number"
                        step="0.0001"
                        min="0"
                        aria-label={`Finished envelope ${axis.toUpperCase()}`}
                        placeholder={axis.toUpperCase()}
                        className={inputClass}
                        defaultValue={
                          ((revision.intent.finishedEnvelope.value as { x: number; y: number; z: number } | null)?.[
                            axis
                          ] ?? "") as number | ""
                        }
                      />
                    ))}
                  </div>
                </Field>
              </div>
            </Panel>

            <Panel title="Required engineering inputs">
              <p className="mb-3 text-[11.5px] leading-relaxed text-muted">
                For a critical part, the Engineering-input gate also requires these. They are stated facts from you,
                recorded USER-confirmed — leaving one blank leaves the gate open, it does not fill in an average.
              </p>
              <div className="space-y-4">
                <Field label="Material condition / temper" hint="e.g. T6511, annealed, 4140 HT 28-32 HRC.">
                  <input name="materialCondition" className={inputClass} defaultValue={revision.intent.materialCondition.value ?? ""} />
                </Field>
                <Field label="Surface finish requirement" hint="e.g. 32 Ra general, 16 Ra on the bearing bore.">
                  <input name="surfaceFinish" className={inputClass} defaultValue={revision.intent.surfaceFinish.value ?? ""} />
                </Field>
                <Field label="Inspection requirements" hint="Comma separated. e.g. FAIR to AS9102, 100% on criticals, CMM report.">
                  <input
                    name="inspectionRequirements"
                    className={inputClass}
                    defaultValue={(revision.intent.inspectionRequirements.value ?? []).join(", ")}
                  />
                </Field>
              </div>
            </Panel>

            {revision.intent.unknowns.length > 0 && (
              <Panel title={`Open unknowns — ${revision.intent.unknowns.length}`}>
                <p className="mb-2 text-[11.5px] leading-relaxed text-muted">
                  Each unknown counts as an outstanding engineering input until a named human resolves it. Checking one
                  states that you have the answer or have decided it does not apply — the resolution is audited.
                </p>
                <ul className="space-y-1.5">
                  {revision.intent.unknowns.map((u) => (
                    <li key={u}>
                      <label className="flex cursor-pointer items-start gap-2.5 border border-line px-3 py-2 text-[12px] leading-relaxed text-platinum-dim hover:border-line-strong">
                        <input type="checkbox" name="resolveUnknown" value={u} className="mt-0.5 accent-[color:var(--c-blue)]" />
                        {u}
                      </label>
                    </li>
                  ))}
                </ul>
              </Panel>
            )}

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

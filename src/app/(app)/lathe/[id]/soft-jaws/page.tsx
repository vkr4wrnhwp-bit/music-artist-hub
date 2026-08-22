import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { TopBar } from "@/components/nav";
import { Button, DevLabel, Notice, Panel, SectionHeading, StatusChip, inputClass, type Tone } from "@/components/ui";
import type { RotationalProfile } from "@/lib/manufacturing/turn/geometry";
import { planSoftJawBore, findReusableLatheJaws, type JawReuseKind } from "@/lib/manufacturing/turn/soft-jaws";

/**
 * LATHE SOFT JAWS — the drawer search and the bore-in-place recipe.
 *
 * Lathe rules, not mill rules: a chuck jaw bored at a diameter holds that
 * diameter, and can only ever be RE-BORED LARGER. No shim fiction. The
 * recipe bores under preload; where the chuck's jaw stroke is unrecorded
 * the preload ring is not sized and the missing input is named. Recording
 * a completed bore is a HUMAN act and is audited.
 */

const KIND_TONE: Record<JawReuseKind, Tone> = { DIRECT: "pass", REBORE: "review", BLANK: "neutral", UNUSABLE: "risk" };

export default async function LatheSoftJawsPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();

  const part = await db.part.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!part) notFound();
  const revision = await db.partRevision.findFirst({ where: { partId: part.id }, orderBy: { createdAt: "desc" } });
  if (!revision) notFound();
  const rot = await db.rotationalPart.findFirst({ where: { partRevisionId: revision.id, organizationId: user.organizationId } });
  if (!rot) notFound();

  const profile = JSON.parse(rot.profileJson) as RotationalProfile;
  const gripDiameter = profile.stockDiameter;
  const gripLength = rot.gripLength;

  const [chuck, jawSets, boringBars] = await Promise.all([
    rot.workholdingId ? db.latheWorkholding.findFirst({ where: { id: rot.workholdingId, organizationId: user.organizationId } }) : null,
    db.latheWorkholding.findMany({ where: { organizationId: user.organizationId, type: "SOFT_JAWS" } }),
    db.turningTool.findMany({ where: { organizationId: user.organizationId, toolClass: "BORING_BAR" } }),
  ]);
  const bar = boringBars[0] ?? null;

  const plan = planSoftJawBore({
    gripDiameter,
    gripLength,
    chuck: chuck
      ? { description: chuck.description, jawStroke: chuck.jawStroke, chuckDiameter: chuck.chuckDiameter, maxRPM: chuck.maxRPM }
      : null,
    boringTool: bar
      ? {
          station: bar.station,
          description: bar.description,
          barDiameter: bar.barDiameter,
          minBoreDiameter: bar.minBoreDiameter,
          surfaceSpeedMin: bar.surfaceSpeedMin,
          surfaceSpeedMax: bar.surfaceSpeedMax,
          feedPerRevMin: bar.feedPerRevMin,
          feedPerRevMax: bar.feedPerRevMax,
        }
      : null,
  });

  const matches =
    gripLength !== null && gripLength > 0
      ? findReusableLatheJaws(gripDiameter, gripLength, jawSets.map((j) => ({ id: j.id, description: j.description, boredDiameter: j.boredDiameter, boredDepth: j.boredDepth })))
      : [];

  async function recordBore(formData: FormData) {
    "use server";
    const u = await requireWrite();
    const jawId = String(formData.get("jawId") ?? "");
    const dia = Number(String(formData.get("boredDiameter") ?? "").trim());
    const depth = Number(String(formData.get("boredDepth") ?? "").trim());
    if (!jawId || !Number.isFinite(dia) || dia <= 0 || !Number.isFinite(depth) || depth <= 0) redirect(`/lathe/${id}/soft-jaws`);
    const jaw = await db.latheWorkholding.findFirst({ where: { id: jawId, organizationId: u.organizationId, type: "SOFT_JAWS" } });
    if (!jaw) notFound();
    // A bored jaw only ever grows — refuse a record that shrinks it.
    if (jaw.boredDiameter !== null && dia < jaw.boredDiameter - 0.0005) redirect(`/lathe/${id}/soft-jaws`);
    await db.latheWorkholding.update({ where: { id: jaw.id }, data: { boredDiameter: dia, boredDepth: depth } });
    await audit({
      organizationId: u.organizationId, userId: u.id, entityType: "LatheWorkholding", entityId: jaw.id,
      action: "UPDATE", actorType: "HUMAN", field: "boredDiameter",
      oldValue: jaw.boredDiameter === null ? "blank" : `⌀${jaw.boredDiameter.toFixed(4)}`,
      newValue: `⌀${dia.toFixed(4)} × ${depth.toFixed(3)} deep`,
      reason: "Soft jaw bore completed and recorded at the machine.",
    });
    revalidatePath(`/lathe/${id}/soft-jaws`);
  }

  return (
    <>
      <TopBar>
        <Link href="/lathe" className="tech-label hover:text-platinum">Turning</Link>
        <span className="text-muted">/</span>
        <Link href={`/lathe/${id}`} className="tech-label hover:text-platinum">{part.name}</Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Soft jaws</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-5xl space-y-5">
          <SectionHeading sub={`Grip ⌀${gripDiameter.toFixed(4)}${gripLength !== null ? ` × ${gripLength.toFixed(3)}" long` : " — grip length not recorded"}. A chuck soft jaw is bored in place, under preload, at the diameter it will grip — and it only ever grows. CANVAS searches the drawer before it asks you to cut anything.`}>
            Soft jaws — {part.name}
          </SectionHeading>

          <Panel title="The drawer" dense>
            {matches.length === 0 ? (
              <p className="px-4 py-2 text-[12px] text-muted">
                {gripLength === null || gripLength <= 0
                  ? "Grip length is not recorded on the setup — record it on the holding panel before the drawer search means anything."
                  : "No soft jaw sets in the workholding library."}
              </p>
            ) : (
              <ul>
                {matches.map((m) => (
                  <li key={m.jawSet.id} className="flex items-start gap-3 border-b border-line/60 px-4 py-2 last:border-0">
                    <StatusChip tone={KIND_TONE[m.kind] ?? "neutral"}>{m.kind}</StatusChip>
                    <span className="min-w-0 flex-1 text-[12px] leading-relaxed text-platinum-dim">{m.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {!plan.ok ? (
            <Notice tone="risk" title="CANVAS will not write this recipe yet">
              <ul className="space-y-1">
                {plan.refusals.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </Notice>
          ) : (
            <>
              <Panel
                title="Bore recipe"
                meta={<DevLabel>DEVELOPMENT ANALYSIS</DevLabel>}
              >
                <div className="mb-3 grid grid-cols-2 gap-x-8 gap-y-1 sm:grid-cols-4">
                  <Fact label="Bore" value={`⌀${plan.boreDiameter.toFixed(4)}`} />
                  <Fact label="Depth" value={`${plan.boreDepth.toFixed(3)}"`} />
                  <Fact label="Preload ring" value={plan.preloadRingDiameter !== null ? `⌀${plan.preloadRingDiameter.toFixed(3)}` : "not sized"} />
                  <Fact
                    label="Boring"
                    value={
                      plan.boringRpm !== null && plan.boringFeedPerRev !== null
                        ? `${plan.boringRpm} RPM · F${plan.boringFeedPerRev.toFixed(4)}`
                        : "no cutting data"
                    }
                  />
                </div>
                <ol className="space-y-2">
                  {plan.steps.map((st) => (
                    <li key={st.order} className="flex gap-3">
                      <span className="font-mono text-[11px] text-precision-dim">{st.order}</span>
                      <span className="min-w-0 flex-1 text-[12px] leading-relaxed text-platinum-dim">
                        {st.text}
                        {st.missingInputs.length > 0 && (
                          <span className="mt-0.5 block text-[10.5px] text-review">Missing: {st.missingInputs.join("; ")}</span>
                        )}
                      </span>
                    </li>
                  ))}
                </ol>
                {plan.missingInputs.length > 0 && (
                  <ul className="mt-3 space-y-0.5 border-t border-line/60 pt-2">
                    {plan.missingInputs.map((m, i) => (
                      <li key={i} className="text-[11px] leading-relaxed text-review">{m}</li>
                    ))}
                  </ul>
                )}
                <ul className="mt-2 space-y-0.5">
                  {plan.assumptions.map((a, i) => (
                    <li key={i} className="text-[10.5px] leading-relaxed text-muted">{a}</li>
                  ))}
                </ul>
              </Panel>

              <Panel title="Jaw cross-section">
                <JawSection bore={plan.boreDiameter} depth={plan.boreDepth} />
              </Panel>
            </>
          )}

          {jawSets.length > 0 && (
            <Panel title="Record a completed bore" meta={<span className="font-mono text-[10.5px] text-muted">HUMAN · audited</span>}>
              <p className="mb-2 text-[11.5px] leading-relaxed text-muted">
                Record what was actually bored, measured at the machine. A record smaller than the jaws&apos; current bore is refused — a chuck jaw cannot shrink.
              </p>
              <form action={recordBore} className="flex flex-wrap items-end gap-3">
                <label className="block">
                  <span className="tech-label mb-1 block">Jaw set</span>
                  <select name="jawId" className={inputClass} defaultValue={jawSets[0].id}>
                    {jawSets.map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.description}
                        {j.boredDiameter !== null ? ` (⌀${j.boredDiameter.toFixed(4)})` : " (blank)"}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="tech-label mb-1 block">Bored ⌀</span>
                  <input name="boredDiameter" inputMode="decimal" placeholder={plan.ok ? plan.boreDiameter.toFixed(4) : ""} className={`${inputClass} w-28 font-mono`} />
                </label>
                <label className="block">
                  <span className="tech-label mb-1 block">Depth</span>
                  <input name="boredDepth" inputMode="decimal" placeholder={plan.ok ? plan.boreDepth.toFixed(3) : ""} className={`${inputClass} w-24 font-mono`} />
                </label>
                <Button type="submit">Record bore</Button>
              </form>
            </Panel>
          )}
        </div>
      </main>
    </>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <span className="block">
      <span className="tech-label block">{label}</span>
      <span className="font-mono text-[13px] text-platinum tabular-nums">{value}</span>
    </span>
  );
}

/** Front cross-section of one jaw pair on light paper: bore, step land, part circle. */
function JawSection({ bore, depth }: { bore: number; depth: number }) {
  const W = 620, H = 260, pad = 30;
  const scale = (H - 2 * pad) / (bore * 1.9);
  const cy = H / 2;
  const cxAxis = pad + 40;
  const r = (bore / 2) * scale;
  const jawH = r * 1.7;
  const stepW = Math.max(24, depth * scale);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ background: "#fafaf8" }} className="w-full border border-line" role="img" aria-label="Soft jaw cross-section">
      <line x1={pad - 8} y1={cy} x2={W - pad} y2={cy} stroke="#0b72ff" strokeWidth={1} strokeDasharray="14 4 3 4" opacity={0.6} />
      {/* Jaw bodies above and below the bore */}
      <rect x={cxAxis} y={cy - jawH} width={stepW + 70} height={jawH - r} fill="none" stroke="#14181c" strokeWidth={1.6} />
      <rect x={cxAxis} y={cy + r} width={stepW + 70} height={jawH - r} fill="none" stroke="#14181c" strokeWidth={1.6} />
      {/* Step land */}
      <line x1={cxAxis + stepW} y1={cy - r} x2={cxAxis + stepW} y2={cy - r * 0.55} stroke="#14181c" strokeWidth={1.6} />
      <line x1={cxAxis + stepW} y1={cy + r} x2={cxAxis + stepW} y2={cy + r * 0.55} stroke="#14181c" strokeWidth={1.6} />
      <line x1={cxAxis + stepW} y1={cy - r * 0.55} x2={cxAxis + stepW + 70} y2={cy - r * 0.55} stroke="#14181c" strokeWidth={1.6} />
      <line x1={cxAxis + stepW} y1={cy + r * 0.55} x2={cxAxis + stepW + 70} y2={cy + r * 0.55} stroke="#14181c" strokeWidth={1.6} />
      {/* Part in the bore */}
      <circle cx={cxAxis + stepW / 2} cy={cy} r={r} fill="#0b72ff" opacity={0.1} />
      <line x1={cxAxis} y1={cy - r} x2={cxAxis + stepW} y2={cy - r} stroke="#0b72ff" strokeWidth={2} />
      <line x1={cxAxis} y1={cy + r} x2={cxAxis + stepW} y2={cy + r} stroke="#0b72ff" strokeWidth={2} />
      <text x={cxAxis + stepW / 2} y={cy - jawH - 8} fontSize={11} fill="#0b72ff" fontFamily="monospace" textAnchor="middle">⌀{bore.toFixed(4)}</text>
      <text x={cxAxis + stepW / 2} y={cy + r + 18} fontSize={9} fill="#5a616b" fontFamily="monospace" textAnchor="middle">{depth.toFixed(3)}" deep</text>
      <text x={W - pad} y={H - 10} fontSize={9} fill="#5a616b" fontFamily="monospace" textAnchor="end">blue = bored grip surface · part seats on the step face</text>
    </svg>
  );
}

export const dynamic = "force-dynamic";

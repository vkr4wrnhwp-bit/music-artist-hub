import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { TopBar } from "@/components/nav";
import { TurnProfileView } from "@/components/turn/profile-view";
import { Button, DevLabel, Notice, Panel, SectionHeading, StatusChip, inputClass } from "@/components/ui";
import { assembleMeasuredProfile, nextTurnTask, type TurnReading } from "@/lib/manufacturing/turn/reverse";
import { findNominalCandidates } from "@/lib/engines/nominal";

/** Write readings + the profile assembled from them in one place. */
async function persistReadings(rotId: string, next: TurnReading[]) {
  const a = assembleMeasuredProfile(next);
  await db.rotationalPart.update({
    where: { id: rotId },
    data: {
      reReadingsJson: JSON.stringify(next),
      ...(a.profile ? { profileJson: JSON.stringify(a.profile) } : {}),
    },
  });
}

/**
 * TURNING REVERSE ENGINEERING — guided bench measurement of a shaft.
 *
 * The flow the engine dictates: datum face first, then steps front to
 * back, each with the instrument named so the uncertainty is real. Every
 * reading is audited MEASURED; the nominal engine SUGGESTS standard
 * values and a human accepts or keeps the measurement — nothing is
 * rounded silently. The stock is a labelled suggestion until confirmed.
 */

export default async function LatheReversePage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();

  const part = await db.part.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!part) notFound();
  const revision = await db.partRevision.findFirst({ where: { partId: part.id }, orderBy: { createdAt: "desc" } });
  if (!revision) notFound();
  const rot = await db.rotationalPart.findFirst({ where: { partRevisionId: revision.id, organizationId: user.organizationId } });
  if (!rot) notFound();

  const devices = await db.metrologyDevice.findMany({ where: { organizationId: user.organizationId }, orderBy: { uncertainty: "asc" } });

  const readings = JSON.parse(rot.reReadingsJson) as TurnReading[];
  const task = nextTurnTask(readings);
  const assembled = assembleMeasuredProfile(readings);

  // Bench flow: the operator is explicitly asking for standard-value matches
  // on a possibly worn part, so the candidate list (wear window open) is the
  // right tool — with confidence shown, not hidden behind an interrupt bar.
  const suggestions = readings.map((r) =>
    r.resolution == null && !r.thread
      ? findNominalCandidates({ measured: r.diameter, uncertainty: r.uncertainty ?? 0.005, context: r.internal ? "BORE" : "SHAFT", wearExpected: true })[0] ?? null
      : null,
  );

  async function addReading(formData: FormData) {
    "use server";
    const u = await requireWrite();
    const owned = await db.rotationalPart.findFirst({ where: { id: rot!.id, organizationId: u.organizationId } });
    if (!owned) notFound();
    const diameter = Number(String(formData.get("diameter") ?? "").trim());
    const length = Number(String(formData.get("length") ?? "").trim());
    const deviceId = String(formData.get("deviceId") ?? "");
    const thread = String(formData.get("thread") ?? "").trim() || null;
    const internal = formData.get("internal") === "on";
    if (!Number.isFinite(diameter) || diameter <= 0 || !Number.isFinite(length) || length <= 0) redirect(`/lathe/${id}/reverse`);
    const device = deviceId ? await db.metrologyDevice.findFirst({ where: { id: deviceId, organizationId: u.organizationId } }) : null;

    const current = JSON.parse(owned.reReadingsJson) as TurnReading[];
    const next = [...current, { diameter, length, uncertainty: device?.uncertainty ?? null, instrument: device?.description ?? null, thread, internal }];
    await persistReadings(owned.id, next);
    await audit({
      organizationId: u.organizationId, userId: u.id, entityType: "RotationalPart", entityId: owned.id,
      action: "UPDATE", actorType: "HUMAN", field: `RE step ${next.length}`,
      newValue: `⌀${diameter.toFixed(4)} × ${length.toFixed(3)}${thread ? ` (${thread})` : ""}`,
      reason: device ? `Measured with ${device.description} (±${device.uncertainty}").` : "Measured with an unrecorded instrument — uncertainty unknown.",
    });
    revalidatePath(`/lathe/${id}/reverse`);
  }

  async function removeLast() {
    "use server";
    const u = await requireWrite();
    const owned = await db.rotationalPart.findFirst({ where: { id: rot!.id, organizationId: u.organizationId } });
    if (!owned) notFound();
    const current = JSON.parse(owned.reReadingsJson) as TurnReading[];
    if (current.length === 0) redirect(`/lathe/${id}/reverse`);
    const removed = current[current.length - 1];
    await persistReadings(owned.id, current.slice(0, -1));
    await audit({
      organizationId: u.organizationId, userId: u.id, entityType: "RotationalPart", entityId: owned.id,
      action: "UPDATE", actorType: "HUMAN", field: `RE step ${current.length}`,
      oldValue: `⌀${removed.diameter.toFixed(4)} × ${removed.length.toFixed(3)}`, newValue: "removed",
      reason: "Reading withdrawn at the bench.",
    });
    revalidatePath(`/lathe/${id}/reverse`);
  }

  async function resolve(formData: FormData) {
    "use server";
    const u = await requireWrite();
    const owned = await db.rotationalPart.findFirst({ where: { id: rot!.id, organizationId: u.organizationId } });
    if (!owned) notFound();
    const index = Number(String(formData.get("index") ?? ""));
    const mode = String(formData.get("mode") ?? "");
    const nominal = Number(String(formData.get("nominal") ?? ""));
    const current = JSON.parse(owned.reReadingsJson) as TurnReading[];
    const r = current[index];
    if (!r || (mode !== "NOMINAL" && mode !== "MEASURED")) redirect(`/lathe/${id}/reverse`);
    if (mode === "NOMINAL" && !Number.isFinite(nominal)) redirect(`/lathe/${id}/reverse`);
    current[index] = { ...r, resolution: mode as "NOMINAL" | "MEASURED", resolvedDiameter: mode === "NOMINAL" ? nominal : null };
    await persistReadings(owned.id, current);
    await audit({
      organizationId: u.organizationId, userId: u.id, entityType: "RotationalPart", entityId: owned.id,
      action: "UPDATE", actorType: "HUMAN", field: `RE step ${index + 1} diameter`,
      oldValue: `⌀${r.diameter.toFixed(4)} (measured)`,
      newValue: mode === "NOMINAL" ? `⌀${nominal.toFixed(4)} (accepted nominal)` : `⌀${r.diameter.toFixed(4)} (measured value kept)`,
      reason: mode === "NOMINAL" ? "Standard nominal accepted by operator against the measurement." : "Operator ruled the measured value stands.",
    });
    revalidatePath(`/lathe/${id}/reverse`);
  }

  return (
    <>
      <TopBar>
        <Link href="/lathe" className="tech-label hover:text-platinum">Turning</Link>
        <span className="text-muted">/</span>
        <Link href={`/lathe/${id}`} className="tech-label hover:text-platinum">{part.name}</Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Reverse engineer</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-5xl space-y-5">
          <SectionHeading sub="Set the part datum-face-down and read it front to back: a diameter and a length per step, with the instrument named so the uncertainty is real. CANVAS suggests standard nominals; it never applies one for you.">
            Reverse engineer — {part.name}
          </SectionHeading>

          <Panel title={`Next — step ${task.step}`} meta={<span className="font-mono text-[10.5px] text-muted">GUIDED</span>}>
            <p className="text-[12.5px] leading-relaxed text-platinum-dim">{task.instruction}</p>
            <p className="mt-1 text-[11px] text-precision-dim">{task.instrumentHint}</p>
            <p className="mt-1 text-[11px] text-muted">{task.why}</p>
            <form action={addReading} className="mt-3 flex flex-wrap items-end gap-3">
              <label className="block">
                <span className="tech-label mb-1 block">Diameter ⌀</span>
                <input name="diameter" inputMode="decimal" className={`${inputClass} w-28 font-mono`} />
              </label>
              <label className="block">
                <span className="tech-label mb-1 block">Length</span>
                <input name="length" inputMode="decimal" className={`${inputClass} w-24 font-mono`} />
              </label>
              <label className="block">
                <span className="tech-label mb-1 block">Instrument</span>
                <select name="deviceId" className={inputClass} defaultValue={devices[0]?.id ?? ""}>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>{d.description} (±{d.uncertainty}&quot;)</option>
                  ))}
                  <option value="">Unrecorded instrument</option>
                </select>
              </label>
              <label className="block">
                <span className="tech-label mb-1 block">Thread (as gauged)</span>
                <input name="thread" placeholder="e.g. 3/4-16 UNF" className={`${inputClass} w-36 font-mono`} />
              </label>
              <label className="flex items-center gap-1.5 pb-2">
                <input type="checkbox" name="internal" />
                <span className="text-[11px] text-platinum-dim">Internal (bore)</span>
              </label>
              <Button type="submit">Record</Button>
            </form>
          </Panel>

          {readings.length > 0 && (
            <Panel title={`Readings — ${readings.length}`} dense>
              <ul>
                {readings.map((r, i) => (
                  <li key={i} className="border-b border-line/60 px-4 py-2 last:border-0">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-[11px] text-muted">step {i + 1}</span>
                      <span className="font-mono text-[12px] text-platinum tabular-nums">
                        ⌀{r.diameter.toFixed(4)} × {r.length.toFixed(3)}
                        {r.thread && <span className="ml-2 text-precision-dim">{r.thread}</span>}
                        {r.internal && <span className="ml-2 text-muted">bore</span>}
                      </span>
                      <span className="text-[10.5px] text-muted">{r.instrument ?? "instrument unrecorded"}</span>
                      {r.resolution === "NOMINAL" && <StatusChip tone="pass">⌀{r.resolvedDiameter?.toFixed(4)} accepted</StatusChip>}
                      {r.resolution === "MEASURED" && <StatusChip tone="neutral">measured kept</StatusChip>}
                    </div>
                    {suggestions[i] && (
                      <div className="mt-1.5 flex flex-wrap items-center gap-3 border-l-2 border-precision/40 pl-3">
                        <span className="text-[11.5px] leading-relaxed text-platinum-dim">
                          Reads like <span className="font-mono text-precision-dim">{suggestions[i]!.label}</span> ({suggestions[i]!.interpretation.toLowerCase()}) — off by {(suggestions[i]!.deviation >= 0 ? "+" : "")}{suggestions[i]!.deviation.toFixed(4)}&quot; · confidence {(suggestions[i]!.confidence * 100).toFixed(0)}%. {suggestions[i]!.basis}
                        </span>
                        <form action={resolve} className="flex gap-2">
                          <input type="hidden" name="index" value={i} />
                          <input type="hidden" name="nominal" value={suggestions[i]!.nominalInches} />
                          <button name="mode" value="NOMINAL" className="border border-precision/50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-precision-dim hover:bg-precision/10">
                            Accept {suggestions[i]!.label}
                          </button>
                          <button name="mode" value="MEASURED" className="border border-line-strong px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-platinum-dim hover:bg-panel">
                            Keep measured
                          </button>
                        </form>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
              <form action={removeLast} className="border-t border-line/60 px-4 py-2">
                <button className="text-[10.5px] font-semibold uppercase tracking-wide text-muted hover:text-risk">Withdraw last reading</button>
              </form>
            </Panel>
          )}

          {assembled.profile && (
            <>
              <Panel title="Profile so far" meta={<DevLabel>MEASURED — unconfirmed until ruled on</DevLabel>}>
                <TurnProfileView profile={assembled.profile} />
              </Panel>
              {assembled.stockNote && (
                <Notice tone="review" title="Stock suggestion">
                  {assembled.stockNote}
                </Notice>
              )}
              <p>
                <Link href={`/lathe/${id}`} className="font-mono text-[11px] text-precision-dim hover:text-precision">
                  Open in the turning workspace →
                </Link>
              </p>
            </>
          )}
          {assembled.issues.length > 0 && (
            <Notice tone="review" title="Measurement notes">
              <ul className="space-y-1">
                {assembled.issues.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </Notice>
          )}

          <Notice tone="review" title="Measurement dependency">
            Every Z position is referenced to the datum face chosen at step 1. Re-measure that face and every reading after it needs re-checking — CANVAS records the order but does not invalidate readings for you.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

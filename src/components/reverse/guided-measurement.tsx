"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Button, Field, Panel, StatusChip, buttonClass, inputClass } from "@/components/ui";

/**
 * The measurement interview.
 *
 * This is the part of CANVAS that should feel like an experienced machinist
 * standing next to you: it names the instrument, tells you what the reading is
 * worth, and — critically — when a reading lands on a standard value it shows
 * you the case and lets you decide. It never rewrites the number.
 */

interface Device {
  id: string;
  label: string;
  uncertainty: number;
  deviceType: string;
}

interface FeatureRef {
  id: string;
  label: string;
  kind: string;
}

interface Photo {
  id: string;
  url: string;
  view: string;
  filename: string;
}

interface MeasurementRow {
  id: string;
  label: string;
  measuredValue: number;
  measuredMm: number;
  uncertainty: number;
  device: string | null;
  context: string;
  suggestedNominal: number | null;
  suggestedNominalLabel: string | null;
  suggestedFamily: string | null;
  suggestionConfidence: number | null;
  suggestionBasis: string | null;
  resolution: string;
  resolvedValue: number | null;
  feature: string | null;
}

const CONTEXTS = [
  { id: "BORE", label: "Bore / internal diameter", instrument: "BORE_GAUGE" },
  { id: "SHAFT", label: "Shaft / external diameter", instrument: "MICROMETER" },
  { id: "HOLE", label: "Drilled hole", instrument: "PIN_GAUGE" },
  { id: "THREAD", label: "Thread major diameter", instrument: "MICROMETER" },
  { id: "THICKNESS", label: "Thickness / height", instrument: "MICROMETER" },
  { id: "GENERAL", label: "General dimension", instrument: "DIGITAL_CALIPER" },
];

export function GuidedMeasurement({
  sessionId,
  devices,
  features,
  photos,
  measurements,
}: {
  sessionId: string;
  devices: Device[];
  features: FeatureRef[];
  photos: Photo[];
  measurements: MeasurementRow[];
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [context, setContext] = useState("BORE");
  const [error, setError] = useState<string | null>(null);

  const recommended = recommendDevice(context, devices);
  const alternative = devices.find((d) => d.id !== recommended?.id && d.deviceType === "DIGITAL_CALIPER");

  const record = (formData: FormData) => {
    setError(null);
    start(async () => {
      const res = await fetch("/api/measurements", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          sessionId,
          label: String(formData.get("label")),
          measuredValue: Number(formData.get("value")),
          deviceId: String(formData.get("deviceId")) || null,
          featureId: String(formData.get("featureId")) || null,
          context,
          repeatCount: Number(formData.get("repeatCount") || 1),
          wearExpected: formData.get("wear") === "on",
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.error ?? "Measurement could not be recorded.");
        return;
      }
      router.refresh();
    });
  };

  const resolve = (measurementId: string, resolution: string) => {
    start(async () => {
      await fetch("/api/measurements", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ measurementId, resolution }),
      });
      router.refresh();
    });
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        {/* ---------------- Record ---------------- */}
        <Panel title="Record a measurement">
          <form action={record} className="space-y-4">
            <Field label="What are you measuring?">
              <div className="grid grid-cols-2 gap-1.5">
                {CONTEXTS.map((c) => (
                  <button
                    type="button"
                    key={c.id}
                    onClick={() => setContext(c.id)}
                    className={`border px-2 py-1.5 text-left text-[11.5px] transition-colors ${
                      context === c.id
                        ? "border-precision/60 text-precision"
                        : "border-line text-platinum-dim hover:border-line-strong"
                    }`}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </Field>

            <div className="border-l-2 border-l-precision/50 bg-raised px-3 py-2.5">
              <p className="tech-label">Recommended instrument</p>
              <p className="mt-0.5 font-mono text-[12px] text-platinum">
                {recommended ? recommended.label : "No suitable instrument in your metrology profile"}
              </p>
              {recommended && (
                <p className="tech-label mt-0.5 text-precision">±{recommended.uncertainty.toFixed(4)}″ uncertainty</p>
              )}
              {alternative && recommended && alternative.id !== recommended.id && (
                <p className="tech-label mt-1">
                  Alternative: {alternative.label} — lower confidence (±{alternative.uncertainty.toFixed(4)}″)
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Label" required>
                <input name="label" required placeholder="e.g. Bearing bore diameter" className={inputClass} />
              </Field>
              <Field label="Measured value (in)" required>
                <input name="value" type="number" step="0.0001" required placeholder="1.5744" className={inputClass} />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Instrument used">
                <select name="deviceId" defaultValue={recommended?.id ?? ""} className={inputClass}>
                  <option value="">Not specified</option>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Readings taken" hint="Repeat readings reduce random error, never below instrument resolution.">
                <input name="repeatCount" type="number" min={1} max={20} defaultValue={3} className={inputClass} />
              </Field>
            </div>

            <Field label="Link to feature">
              <select name="featureId" defaultValue="" className={inputClass}>
                <option value="">Not linked</option>
                {features.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.label}
                  </option>
                ))}
              </select>
            </Field>

            <label className="flex items-center gap-2 text-[12px] text-platinum-dim">
              <input type="checkbox" name="wear" className="accent-[color:var(--c-blue)]" />
              Surface is worn — widen the nominal search window
            </label>

            {error && <p className="text-[12px] text-risk">{error}</p>}

            <Button type="submit" variant="primary" disabled={pending}>
              {pending ? "Recording…" : "Record measurement"}
            </Button>
          </form>
        </Panel>

        {/* ---------------- Reference photo ---------------- */}
        <Panel title="Reference">
          {photos.length === 0 ? (
            <p className="text-[12px] leading-relaxed text-muted">
              No photographs uploaded. CANVAS uses them to show you which feature it is asking about — it does not
              measure them.
            </p>
          ) : (
            <div className="space-y-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={photos[0].url} alt={photos[0].view} className="w-full border border-line object-cover" />
              <p className="tech-label">{photos[0].view} view</p>
            </div>
          )}
        </Panel>
      </div>

      {/* ---------------- Recorded measurements ---------------- */}
      <Panel title={`Measurements — ${measurements.length}`} dense>
        {measurements.length === 0 ? (
          <p className="p-4 text-[12px] text-muted">No measurements recorded yet.</p>
        ) : (
          <ul>
            {measurements.map((m) => (
              <li key={m.id} className="border-b border-line/60 px-4 py-3 last:border-0">
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <div>
                    <p className="font-mono text-[12.5px] text-platinum">{m.label}</p>
                    <p className="tech-label">
                      {m.context.toLowerCase()} · {m.device ?? "instrument not specified"} · ±{m.uncertainty.toFixed(4)}″
                      {m.feature && ` · ${m.feature}`}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-[15px] text-white">{m.measuredValue.toFixed(4)}″</p>
                    <p className="tech-label">{m.measuredMm} mm</p>
                  </div>
                </div>

                {/* ---- Nominal reasoning ---- */}
                {m.suggestedNominal && m.resolution === "PENDING" && (
                  <div className="mt-3 border border-precision/40 bg-precision/[0.04] px-3.5 py-3">
                    <p className="tech-label text-precision">Possible nominal feature</p>
                    <div className="mt-2 grid gap-x-8 gap-y-1 sm:grid-cols-3">
                      <Readout label="Measured" value={`${m.measuredValue.toFixed(4)}″`} />
                      <Readout label="Likely engineering intent" value={m.suggestedNominalLabel ?? "—"} highlight />
                      <Readout
                        label="Confidence"
                        value={m.suggestionConfidence ? `${(m.suggestionConfidence * 100).toFixed(0)}%` : "—"}
                      />
                    </div>
                    <div className="mt-2 grid gap-x-8 gap-y-1 sm:grid-cols-3">
                      <Readout label="Nominal" value={`${m.suggestedNominal.toFixed(4)}″`} />
                      <Readout label="Deviation" value={`${((m.measuredValue - m.suggestedNominal) * 1000).toFixed(1)} thou`} />
                      <Readout label="Family" value={(m.suggestedFamily ?? "").replace(/_/g, " ").toLowerCase()} />
                    </div>
                    {m.suggestionBasis && (
                      <p className="mt-2 text-[12px] leading-relaxed text-muted">{m.suggestionBasis}</p>
                    )}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button onClick={() => resolve(m.id, "ACCEPTED_NOMINAL")} className={buttonClass("primary", "sm")}>
                        Accept {m.suggestedNominalLabel}
                      </button>
                      <button onClick={() => resolve(m.id, "KEPT_MEASURED")} className={buttonClass("default", "sm")}>
                        Keep measured value
                      </button>
                      <button onClick={() => resolve(m.id, "INVESTIGATING")} className={buttonClass("ghost", "sm")}>
                        Investigate
                      </button>
                    </div>
                  </div>
                )}

                {m.resolution !== "PENDING" && (
                  <div className="mt-2 flex items-center gap-3">
                    <StatusChip tone={m.resolution === "ACCEPTED_NOMINAL" ? "precision" : m.resolution === "KEPT_MEASURED" ? "pass" : "review"}>
                      {m.resolution.replace(/_/g, " ")}
                    </StatusChip>
                    {m.resolvedValue !== null && (
                      <span className="font-mono text-[12px] text-platinum">
                        Model value {m.resolvedValue.toFixed(4)}″
                      </span>
                    )}
                  </div>
                )}

                {!m.suggestedNominal && m.resolution === "PENDING" && (
                  <p className="mt-2 text-[11.5px] text-muted">
                    No standard value matches this reading strongly enough to suggest engineering intent. Treated as a
                    custom dimension.
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function Readout({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div>
      <p className="tech-label">{label}</p>
      <p className={`font-mono text-[13px] ${highlight ? "text-precision" : "text-platinum"}`}>{value}</p>
    </div>
  );
}

/**
 * Instrument selection is by capability, not preference: a bore is measured
 * with a bore gauge if one exists, and CANVAS says plainly when the best
 * available instrument is not good enough for the feature.
 */
function recommendDevice(context: string, devices: Device[]): Device | null {
  const preference: Record<string, string[]> = {
    BORE: ["BORE_GAUGE", "TELESCOPING_GAUGE", "CMM", "DIGITAL_CALIPER"],
    SHAFT: ["MICROMETER", "CMM", "DIGITAL_CALIPER"],
    HOLE: ["PIN_GAUGE", "BORE_GAUGE", "DIGITAL_CALIPER"],
    THREAD: ["MICROMETER", "OPTICAL_COMPARATOR", "DIGITAL_CALIPER"],
    THICKNESS: ["MICROMETER", "HEIGHT_GAUGE", "DIGITAL_CALIPER"],
    GENERAL: ["DIGITAL_CALIPER", "HEIGHT_GAUGE", "TAPE_RULE"],
  };
  for (const type of preference[context] ?? preference.GENERAL) {
    const found = devices.find((d) => d.deviceType === type);
    if (found) return found;
  }
  return devices[0] ?? null;
}

"use client";

import { useState, useTransition } from "react";
import { Button, Field, inputClass } from "@/components/ui";
import { PhotoGuide } from "./photo-guide";
import type { GuidedPlan, GuidedStep } from "@/lib/engines/photo-plan";

/**
 * UPLOAD A PHOTOGRAPH; GET AN ORDER OF WORK ON IT.
 *
 * The whole point of reverse engineering for a shop with a part and no drawing.
 * The picture goes up, a model says what it can see and where, and the machinist
 * gets numbered pins on their own photograph: measure this, then this.
 *
 * Every reading they take goes into the measurement session attributed to the
 * instrument that took it. Nothing the model said becomes a dimension, because
 * the model was never asked for one and has nowhere to put one.
 */
export function PhotoMeasure({
  partId,
  sessionId,
  photos,
  devices,
}: {
  partId: string;
  /** Readings land in this session, like every other reading in the flow. */
  sessionId: string;
  /** Photographs already on file for this part. */
  photos: { id: string; url: string; label: string }[];
  devices: { id: string; label: string }[];
}) {
  const [selected, setSelected] = useState<string | null>(photos[0]?.id ?? null);
  /*
   * The photograph that was just handed over, held in the browser.
   *
   * The pins have to go on THAT picture. Falling back to whatever is already
   * stored against the part would mark up a different view — the machinist
   * uploads a photo of the back face, and gets pins on the front. And a first
   * photograph, before anything is stored, produced a plan with nowhere to
   * draw it at all.
   */
  const [uploaded, setUploaded] = useState<string | null>(null);
  const [plan, setPlan] = useState<GuidedPlan | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const [recording, setRecording] = useState(false);

  const stored = photos.find((p) => p.id === selected) ?? null;
  const canvasUrl = uploaded ?? stored?.url ?? null;

  const readPhoto = async (file: File) => {
    setProblem(null);
    const fd = new FormData();
    fd.set("file", file);
    fd.set("partId", partId);
    fd.set("views", String(photos.length || 1));
    const res = await fetch("/api/parts/photo-plan", { method: "POST", body: fd });
    const body = (await res.json()) as { error?: string; connected?: boolean; plan?: GuidedPlan };
    if (!res.ok || !body.plan) {
      setProblem(body.error ?? "The photograph could not be read.");
      return;
    }
    // Revoked when it is replaced, so a long session does not accumulate
    // object URLs for every photograph that has been through here.
    setUploaded((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
    setPlan(body.plan);
  };

  return (
    <div className="space-y-4">
      <div className="border border-line bg-raised px-4 py-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">Measure from a photograph</p>
        <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
          Photograph the part and CANVAS marks up what to measure and in what order, on the picture itself. It reads no
          dimensions from the photograph and cannot — every number below is one you take with an instrument.
        </p>
        <form
          className="mt-3 flex flex-wrap items-end gap-3"
          action={(fd) => {
            const f = fd.get("file");
            if (f instanceof File && f.size > 0) start(() => readPhoto(f));
          }}
        >
          <div className="min-w-[16rem] flex-1">
            <Field label="Photograph" required hint="JPEG, PNG or WebP — what a phone takes.">
              <input type="file" name="file" accept="image/jpeg,image/png,image/webp" className={inputClass} required />
            </Field>
          </div>
          <Button type="submit" variant="primary" size="sm" disabled={pending}>
            {pending ? "Reading the photograph…" : "What should I measure?"}
          </Button>
        </form>
        {problem && (
          <p className="mt-3 border border-line border-l-2 border-l-risk bg-void px-3 py-2 text-[12px] text-platinum">
            {problem}
          </p>
        )}
      </div>

      {photos.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {photos.map((p) => (
            <Button
              key={p.id}
              type="button"
              size="sm"
              variant={p.id === selected ? "primary" : "default"}
              onClick={() => setSelected(p.id)}
            >
              {p.label}
            </Button>
          ))}
        </div>
      )}

      {plan && canvasUrl && (
        <PhotoGuide
          imageUrl={canvasUrl}
          plan={plan}
          devices={devices}
          recording={recording}
          onRecord={(step: GuidedStep, reading: string, deviceId: string) => {
            /*
             * Straight into the session, through the same endpoint a reading
             * taken at the bench goes through — because that is what it is. The
             * uncertainty comes from the instrument, and the nominal engine
             * resolves the number afterwards with a human ruling on it.
             */
            setRecording(true);
            void fetch("/api/measurements", {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({
                sessionId,
                deviceId,
                label: `${step.label} — ${step.whatToMeasure}`,
                measuredValue: Number(reading),
                context: step.kind === "BORE" ? "BORE" : step.kind.includes("HOLE") ? "HOLE" : "GENERAL",
                repeatCount: 1,
                wearExpected: false,
              }),
            })
              .then(async (r) => {
                setRecording(false);
                if (!r.ok) setProblem(((await r.json()) as { error?: string }).error ?? "The reading was not recorded.");
              })
              .catch(() => {
                setRecording(false);
                setProblem("The reading was not recorded.");
              });
          }}
        />
      )}

      {plan && !canvasUrl && (
        <p className="border border-line bg-raised px-4 py-3 text-[12px] leading-relaxed text-muted">
          The plan was read but there is no picture to put it on. Attach the photograph above.
        </p>
      )}
    </div>
  );
}

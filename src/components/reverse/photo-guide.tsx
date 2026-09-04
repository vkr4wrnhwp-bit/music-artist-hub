"use client";

import { useState } from "react";
import { Button, Field, StatusChip, inputClass } from "@/components/ui";
import type { GuidedPlan, GuidedStep } from "@/lib/engines/photo-plan";

/**
 * THE PHOTOGRAPH, WITH THE WORK ON IT.
 *
 * "I have the part and a phone. Where do I start?" — the plan knew the answer
 * and could not point, so a machinist read a list of labels and had to work out
 * which lump of metal each one meant.
 *
 * Here the list is ON the part. One pin per step, the current one lit and the
 * rest dimmed, and under it what to measure, what to reach for out of this
 * shop's own drawer, and why this one now. Record the reading and it moves to
 * the next.
 *
 * WHAT IS NOT ON THIS SCREEN
 *
 * Any number the model produced, because it produced none. It said what it
 * could see and where; every dimension here is one somebody takes with an
 * instrument. The caveats say so at the top rather than the bottom — a
 * machinist who reads this as a description of the part will measure the five
 * things listed and miss the sixth, on the face nobody photographed.
 */
export function PhotoGuide({
  imageUrl,
  plan,
  devices,
  onRecord,
  recording,
}: {
  imageUrl: string;
  plan: GuidedPlan;
  /** This shop's instruments. A reading with no instrument has no uncertainty. */
  devices: { id: string; label: string }[];
  onRecord: (step: GuidedStep, reading: string, deviceId: string) => void;
  recording: boolean;
}) {
  const [done, setDone] = useState<number[]>([]);
  const [reading, setReading] = useState("");
  const [deviceId, setDeviceId] = useState(devices[0]?.id ?? "");
  const current = plan.steps.find((s) => !done.includes(s.order)) ?? null;

  if (plan.steps.length === 0) {
    return (
      <div className="border border-line bg-raised px-4 py-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">Nothing to measure yet</p>
        <p className="mt-1.5 text-[12px] leading-relaxed text-muted">{plan.headline}</p>
        {plan.caveats.map((c) => (
          <p key={c} className="mt-1 text-[11px] leading-relaxed text-muted">
            {c}
          </p>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="border border-line bg-raised px-4 py-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">{plan.headline}</p>
        {/*
          At the top, not the bottom. What the model did and did not do is the
          first thing a machinist needs, not a footnote under the list.
        */}
        {plan.caveats.map((c) => (
          <p key={c} className="mt-1.5 text-[11px] leading-relaxed text-muted">
            {c}
          </p>
        ))}
      </div>

      <div className="relative inline-block max-w-full border border-line bg-void">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={imageUrl} alt="The part, with each measurement pinned to it" className="block max-h-[520px] w-auto max-w-full" />
        {plan.steps.map((s) => {
          const isDone = done.includes(s.order);
          const isCurrent = current?.order === s.order;
          return (
            <span
              key={s.order}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${s.x * 100}%`, top: `${s.y * 100}%` }}
              title={`${s.label} — ${s.whatToMeasure}`}
            >
              <span
                className={[
                  "flex h-6 w-6 items-center justify-center border font-mono text-[11px]",
                  isCurrent
                    ? "border-precision bg-precision text-void"
                    : isDone
                      ? "border-line-strong bg-void text-muted line-through"
                      : "border-line-strong bg-void/80 text-muted",
                ].join(" ")}
              >
                {s.order}
              </span>
            </span>
          );
        })}
      </div>

      {current ? (
        <div className="border border-line border-l-2 border-l-precision bg-raised px-4 py-3">
          <div className="flex flex-wrap items-baseline gap-3">
            <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-precision">Step {current.order}</span>
            <span className="font-mono text-[13px] text-platinum">{current.label}</span>
            {current.blocking && <StatusChip tone="review">Do this first</StatusChip>}
          </div>
          <p className="mt-2 text-[12.5px] leading-relaxed text-platinum">Measure: {current.whatToMeasure}</p>
          <p className="mt-1 text-[12px] leading-relaxed text-muted">
            {current.instrument ? (
              <>With: {current.instrument}</>
            ) : (
              <>
                Nothing in this shop&apos;s metrology library can take this one. It is on the list anyway — an unmeasured
                dimension you know about beats one that was quietly dropped.
              </>
            )}
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-muted">{current.why}</p>
          {current.caution && (
            <p className="mt-1 text-[11px] leading-relaxed text-review">From the photograph: {current.caution}</p>
          )}

          <div className="mt-3 flex flex-wrap items-end gap-3">
            <div className="w-40">
              <Field label="Reading" hint="inches">
                <input
                  className={inputClass}
                  value={reading}
                  onChange={(e) => setReading(e.target.value)}
                  inputMode="decimal"
                  placeholder="1.5748"
                />
              </Field>
            </div>
            {/*
              WHICH INSTRUMENT ACTUALLY TOOK IT.
              The step recommends one; what was reached for is a different
              question, and it is the one that sets the uncertainty on this
              number. A reading with no instrument behind it is a figure with
              no error bar, and the nominal engine would resolve it as though
              it were exact.
            */}
            <div className="w-64">
              <Field label="Measured with" required>
                <select className={inputClass} value={deviceId} onChange={(e) => setDeviceId(e.target.value)}>
                  {devices.length === 0 && <option value="">Nothing in the metrology library</option>}
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={recording || !(Number(reading) > 0) || deviceId === ""}
              onClick={() => {
                onRecord(current, reading, deviceId);
                setDone((d) => [...d, current.order]);
                setReading("");
              }}
            >
              {recording ? "Recording…" : "Record and go on"}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setDone((d) => [...d, current.order])}>
              Skip for now
            </Button>
          </div>
        </div>
      ) : (
        <div className="border border-line bg-raised px-4 py-3">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">Every step has been visited</p>
          <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
            That is this photograph finished, which is not the same as the part being described. Anything on a face this
            view does not show is still unmeasured — photograph it and read it again.
          </p>
        </div>
      )}

      <ol className="border border-line bg-raised">
        {plan.steps.map((s) => (
          <li
            key={s.order}
            className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-line/60 px-4 py-2 last:border-0"
          >
            <span className="w-5 font-mono text-[11px] text-muted">{s.order}</span>
            <span className={`font-mono text-[12px] ${done.includes(s.order) ? "text-muted line-through" : "text-platinum"}`}>
              {s.label}
            </span>
            <span className="text-[11px] text-muted">{s.whatToMeasure}</span>
            {s.instrument ? (
              <span className="ml-auto text-[11px] text-muted">{s.instrument}</span>
            ) : (
              <span className="ml-auto text-[11px] text-review">No instrument for this</span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

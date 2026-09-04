"use client";

import { useState, useTransition } from "react";
import { Button, Field, inputClass } from "@/components/ui";
import { PATTERN_KINDS, type PatternKind } from "@/lib/domain/pattern";

/**
 * PLACING A FEATURE AS A PATTERN.
 *
 * Every hole in a bolt circle had to be typed in by hand with its coordinates
 * worked out off the machine. Six holes on a 3.000" circle is twelve numbers to
 * compute and twelve to mistype, on the most common thing there is on a plate.
 *
 * The refusals are the reason this is a client form rather than a bare action:
 * "4 of 6 would sit off the 6.000 × 4.000 stock — the first at X3.5000" is the
 * message that catches a transposed diameter, and it has to reach the person
 * typing it rather than disappearing into a redirect.
 */

const LABEL: Record<PatternKind, string> = {
  BOLT_CIRCLE: "Bolt circle",
  GRID: "Grid",
  LINEAR: "Line",
};

export function PatternForm({
  featureId,
  action,
}: {
  featureId: string;
  action: (formData: FormData) => Promise<{ error?: string; ok?: true; created?: number } | void>;
}) {
  const [kind, setKind] = useState<PatternKind>("BOLT_CIRCLE");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  return (
    <form
      action={(fd) => {
        setError(null);
        start(async () => {
          const r = await action(fd);
          if (r && "error" in r && r.error) setError(r.error);
        });
      }}
      className="mt-4 space-y-3"
    >
      <input type="hidden" name="featureId" value={featureId} />
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Pattern">
          <select
            name="patternKind"
            value={kind}
            onChange={(e) => { setKind(e.target.value as PatternKind); setError(null); }}
            className={inputClass}
          >
            {PATTERN_KINDS.map((k) => (
              <option key={k} value={k}>{LABEL[k]}</option>
            ))}
          </select>
        </Field>

        {/* Only the fields this pattern actually uses. A form that asks for a
            bolt circle diameter on a grid invites a number that is then
            ignored, which is worse than not asking. */}
        {kind === "BOLT_CIRCLE" && (
          <>
            <Field label="How many">
              <input name="count" type="number" step="1" min={2} defaultValue={6} required className={inputClass} />
            </Field>
            <Field label="Bolt circle ⌀, in" hint="The circle the hole CENTRES sit on, not the holes.">
              <input name="diameter" type="number" step="0.0001" min={0} required className={inputClass} />
            </Field>
            <Field label="First hole at, °" hint="Counter-clockwise from +X.">
              <input name="startAngle" type="number" step="0.01" defaultValue={0} required className={inputClass} />
            </Field>
            <Field label="Centre X, in">
              <input name="centerX" type="number" step="0.0001" defaultValue={0} required className={inputClass} />
            </Field>
            <Field label="Centre Y, in">
              <input name="centerY" type="number" step="0.0001" defaultValue={0} required className={inputClass} />
            </Field>
          </>
        )}

        {kind === "GRID" && (
          <>
            <Field label="Columns">
              <input name="columns" type="number" step="1" min={1} defaultValue={3} required className={inputClass} />
            </Field>
            <Field label="Rows">
              <input name="rows" type="number" step="1" min={1} defaultValue={2} required className={inputClass} />
            </Field>
            <Field label="Pitch X, in">
              <input name="pitchX" type="number" step="0.0001" min={0} required className={inputClass} />
            </Field>
            <Field label="Pitch Y, in">
              <input name="pitchY" type="number" step="0.0001" min={0} required className={inputClass} />
            </Field>
            <Field label="First one at X, in">
              <input name="originX" type="number" step="0.0001" defaultValue={0} required className={inputClass} />
            </Field>
            <Field label="First one at Y, in">
              <input name="originY" type="number" step="0.0001" defaultValue={0} required className={inputClass} />
            </Field>
          </>
        )}

        {kind === "LINEAR" && (
          <>
            <Field label="How many">
              <input name="count" type="number" step="1" min={2} defaultValue={4} required className={inputClass} />
            </Field>
            <Field label="Pitch, in" hint="Centre to centre.">
              <input name="pitch" type="number" step="0.0001" min={0} required className={inputClass} />
            </Field>
            <Field label="Along, °" hint="Counter-clockwise from +X.">
              <input name="angle" type="number" step="0.01" defaultValue={0} required className={inputClass} />
            </Field>
            <Field label="First one at X, in">
              <input name="originX" type="number" step="0.0001" defaultValue={0} required className={inputClass} />
            </Field>
            <Field label="First one at Y, in">
              <input name="originY" type="number" step="0.0001" defaultValue={0} required className={inputClass} />
            </Field>
          </>
        )}
      </div>

      {error && <p className="max-w-2xl text-[12px] leading-relaxed text-risk">{error}</p>}

      <Button type="submit" variant="primary" size="sm" disabled={pending}>
        {pending ? "Placing…" : "Place the pattern"}
      </Button>
    </form>
  );
}

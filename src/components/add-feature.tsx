"use client";

import { useState, useTransition } from "react";
import { Button, Field, Panel, inputClass } from "@/components/ui";
import { FEATURE_FIELDS } from "@/lib/domain/feature-input";
import { FEATURE_KINDS, FUNCTIONAL_ROLES, type FeatureKind } from "@/lib/domain/features";

/**
 * ADDING A FEATURE BY HAND
 *
 * The only route into a part's geometry was accepting an AI proposal. This is
 * the other door — a machinist typing in the 40 mm bore they are looking at.
 *
 * The fields come from the kind's own spec, so the form cannot drift from what
 * the engines read, and nothing is prefilled with a plausible number. An empty
 * field is refused by name rather than defaulted: a zero-depth pocket removes
 * no material and every engine downstream would treat it as real.
 */

const KIND_LABEL: Record<FeatureKind, string> = {
  FACE: "Face",
  RECT_POCKET: "Rectangular pocket",
  CIRC_POCKET: "Circular pocket",
  BORE: "Bore",
  SLOT: "Slot",
  DRILLED_HOLE: "Drilled hole",
  TAPPED_HOLE: "Tapped hole",
  COUNTERBORE: "Counterbore",
  COUNTERSINK: "Countersink",
  CHAMFER: "Chamfer",
  FILLET: "Fillet",
  OUTSIDE_CONTOUR: "Outside contour",
  ENGRAVING: "Engraving",
  BOSS: "Boss",
  STEP: "Step",
};

const ROLE_LABEL = (r: string) => r.toLowerCase().replace(/_/g, " ");

export function AddFeature({ action }: { action: (formData: FormData) => Promise<{ error?: string; ok?: true } | void> }) {
  const [kind, setKind] = useState<FeatureKind>("BORE");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const fields = FEATURE_FIELDS[kind];

  return (
    <Panel title="Add a feature">
      <p className="mb-3 max-w-2xl text-[12.5px] leading-relaxed text-muted">
        What the part has, as you would describe it at the machine. Geometry only — what the feature is for, and what
        it has to hold, is asked on the feature itself, because a dimension without its responsibility is just a
        number.
      </p>
      <form
        action={(fd) => {
          setError(null);
          start(async () => {
            const r = await action(fd);
            if (r && "error" in r && r.error) setError(r.error);
          });
        }}
        className="space-y-3"
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Kind">
            <select
              name="kind"
              value={kind}
              onChange={(e) => { setKind(e.target.value as FeatureKind); setError(null); }}
              className={inputClass}
            >
              {FEATURE_KINDS.map((k) => (
                <option key={k} value={k}>{KIND_LABEL[k]}</option>
              ))}
            </select>
          </Field>
          <Field label="Name" hint="What a machinist would call it.">
            <input name="label" required maxLength={120} placeholder="40 mm bearing bore" className={inputClass} />
          </Field>
          <Field label="Function" hint="What it is for. Drives the tolerance the standard asks for.">
            <select name="functionalRole" defaultValue="NONE" className={inputClass}>
              {FUNCTIONAL_ROLES.map((r) => (
                <option key={r} value={r}>{ROLE_LABEL(r)}</option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid gap-3 sm:grid-cols-4" key={kind}>
          {fields.map((f) =>
            f.type === "boolean" ? (
              <label key={f.name} className="flex items-center gap-2 self-end pb-2 text-[12px] text-platinum-dim">
                <input type="checkbox" name={f.name} className="accent-[color:var(--c-blue)]" />
                {f.label}
              </label>
            ) : (
              <Field key={f.name} label={f.unit ? `${f.label}, ${f.unit}` : f.label} hint={f.hint}>
                {f.type === "choice" ? (
                  <select name={f.name} className={inputClass}>
                    {f.choices?.map((c) => (
                      <option key={c} value={c}>{ROLE_LABEL(c)}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    name={f.name}
                    type={f.type === "number" ? "number" : "text"}
                    step={f.type === "number" ? "0.0001" : undefined}
                    required={f.required}
                    placeholder={f.required ? "" : "optional"}
                    className={inputClass}
                  />
                )}
              </Field>
            ),
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-4">
          <Field label="Tolerance +, in" hint="Leave blank for no stated tolerance.">
            <input name="tolerancePlus" type="number" step="0.0001" placeholder="none" className={inputClass} />
          </Field>
          <Field label="Tolerance −, in">
            <input name="toleranceMinus" type="number" step="0.0001" placeholder="none" className={inputClass} />
          </Field>
          <Field label="Surface finish, Ra µin">
            <input name="surfaceFinish" type="number" step="1" placeholder="none" className={inputClass} />
          </Field>
          <label className="flex items-center gap-2 self-end pb-2 text-[12px] text-platinum-dim">
            <input type="checkbox" name="critical" className="accent-[color:var(--c-blue)]" />
            Critical
          </label>
        </div>

        <Field label="Notes">
          <input name="notes" maxLength={1000} className={inputClass} />
        </Field>

        {error && <p className="text-[12px] leading-relaxed text-risk">{error}</p>}

        <Button type="submit" variant="primary" disabled={pending}>
          {pending ? "Adding…" : "Add feature"}
        </Button>
      </form>
    </Panel>
  );
}

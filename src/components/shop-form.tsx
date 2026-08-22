import type { ReactNode } from "react";
import { Field, inputClass, Button, LinkButton } from "@/components/ui";

/**
 * SHOP RECORD FORM — the shared shape for creating and editing the records
 * that describe what a shop actually owns: tools, machines, workholding,
 * instruments, materials.
 *
 * Why this exists at all: every "Add tool" / "Add instrument" / "Add machine"
 * button in the app pointed at a route that did not exist. A button that
 * appears to add and 404s is the same class of lie as a button that appears
 * to optimise and does nothing — principle 5 — and it was worse here than
 * elsewhere, because those empty states are the first thing a new shop sees.
 *
 * Two decisions worth stating.
 *
 * NO CLIENT JAVASCRIPT. These are plain `<form action={serverAction}>`
 * posts. A shop-floor terminal on a slow connection can fill in a tool
 * record and it will submit; there is no hydration to wait for and nothing
 * to lose if a bundle fails. Validation is server-side, where it has to be
 * anyway — a client check is a convenience, never the guard.
 *
 * REQUIRED MEANS THE ENGINES NEED IT. A field is marked required when a
 * deterministic engine reads it and returns null without it, not to make the
 * record look complete. Diameter, flutes and stickout decide whether a
 * feature is machinable at all; a nullable field stays nullable, and the
 * form says what is missing rather than filling a default in.
 */

export type ShopFieldKind = "text" | "number" | "select" | "checkbox" | "textarea";

export interface ShopField {
  name: string;
  label: string;
  kind: ShopFieldKind;
  required?: boolean;
  hint?: string;
  placeholder?: string;
  /** Unit suffix shown against the label, e.g. `in` or `lbf`. Display only. */
  unit?: string;
  /**
   * number inputs.
   *
   * `step` defaults to "any" and should almost always stay there. HTML
   * validates a number against `min + n * step`, so `step="100"` with
   * `min="1"` makes 12000 RPM invalid and tells the machinist "the two
   * nearest valid values are 11901 and 12001" — which is nonsense about a
   * spindle speed, and it blocks the submit before the server sees it.
   * Step is not a precision hint here and must not be used as one; real
   * bounds go in `min`/`max`, and everything else is checked server-side
   * where it has to be checked anyway.
   */
  step?: string;
  min?: string;
  max?: string;
  /** select inputs */
  options?: { value: string; label: string }[];
  /** Current value when editing. */
  defaultValue?: string | number | boolean | null;
  /** Half-width on wide screens. Most numeric fields want this. */
  half?: boolean;
}

export interface ShopSection {
  title: string;
  /** Why these fields matter — machinist voice, not form-filling copy. */
  note?: string;
  fields: ShopField[];
}

function Input({ field }: { field: ShopField }) {
  const common = {
    name: field.name,
    id: field.name,
    required: field.required,
    className: inputClass,
  };

  if (field.kind === "select") {
    return (
      <select {...common} defaultValue={field.defaultValue == null ? "" : String(field.defaultValue)}>
        {!field.required && <option value="">—</option>}
        {(field.options ?? []).map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    );
  }

  if (field.kind === "checkbox") {
    return (
      <input
        type="checkbox"
        name={field.name}
        id={field.name}
        defaultChecked={Boolean(field.defaultValue)}
        className="h-3.5 w-3.5 accent-[color:var(--c-blue)]"
      />
    );
  }

  if (field.kind === "textarea") {
    return (
      <textarea
        {...common}
        rows={3}
        placeholder={field.placeholder}
        defaultValue={field.defaultValue == null ? "" : String(field.defaultValue)}
      />
    );
  }

  return (
    <input
      {...common}
      type={field.kind === "number" ? "number" : "text"}
      inputMode={field.kind === "number" ? "decimal" : undefined}
      step={field.step ?? (field.kind === "number" ? "any" : undefined)}
      min={field.min}
      max={field.max}
      placeholder={field.placeholder}
      defaultValue={field.defaultValue == null ? "" : String(field.defaultValue)}
    />
  );
}

/**
 * A checkbox reads badly inside `Field`, which puts its label above the
 * control — for a boolean the label belongs beside it.
 */
function Row({ field }: { field: ShopField }) {
  if (field.kind === "checkbox") {
    return (
      <div className={field.half ? "sm:col-span-1" : "sm:col-span-2"}>
        <label className="flex items-center gap-2">
          <Input field={field} />
          <span className="tech-label">{field.label}</span>
        </label>
        {field.hint && <p className="mt-1 text-[11px] leading-relaxed text-muted">{field.hint}</p>}
      </div>
    );
  }

  return (
    <div className={field.half ? "sm:col-span-1" : "sm:col-span-2"}>
      <Field
        label={field.unit ? `${field.label} (${field.unit})` : field.label}
        hint={field.hint}
        required={field.required}
      >
        <Input field={field} />
      </Field>
    </div>
  );
}

export function ShopForm({
  action,
  sections,
  submitLabel,
  cancelHref,
  children,
}: {
  action: (formData: FormData) => void | Promise<void>;
  sections: ShopSection[];
  submitLabel: string;
  cancelHref: string;
  /** Extra content between the last section and the buttons. */
  children?: ReactNode;
}) {
  return (
    <form action={action} className="space-y-6">
      {sections.map((s) => (
        <section key={s.title} className="border border-line bg-card">
          <div className="border-b border-line px-4 py-2.5">
            <p className="instrument-label">{s.title}</p>
            {s.note && <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{s.note}</p>}
          </div>
          <div className="grid gap-x-6 gap-y-4 px-4 py-4 sm:grid-cols-2">
            {s.fields.map((f) => (
              <Row key={f.name} field={f} />
            ))}
          </div>
        </section>
      ))}

      {children}

      <div className="flex items-center gap-2">
        <Button type="submit" variant="primary" size="sm">
          {submitLabel}
        </Button>
        <LinkButton href={cancelHref} size="sm">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}

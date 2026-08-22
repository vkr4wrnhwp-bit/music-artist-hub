import { WORKHOLDING_TYPES } from "@/lib/domain/shop";
import type { ShopSection } from "@/components/shop-form";

/**
 * The workholding device record, as a form.
 *
 * Clamp force is optional and stays that way. Most shops do not know what
 * their vise actually applies, and `assessHoldingMargin` handles that
 * honestly: no clamp force means the margin comes back INDETERMINATE with
 * "clamp force not recorded" named as the missing input. Requiring the field
 * would push people to type a catalogue number they have never measured,
 * which converts an honest INDETERMINATE into a confident wrong answer.
 */

export const title = (s: string) => s.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());

export interface DeviceFormValues {
  type?: string;
  manufacturer?: string | null;
  model?: string | null;
  description?: string;
  jawWidth?: number;
  jawHeight?: number;
  maxOpening?: number;
  clampForce?: number | null;
  fixtureHeight?: number;
  mountingGeometry?: string | null;
  notes?: string | null;
}

export function deviceSections(v: DeviceFormValues): ShopSection[] {
  return [
    {
      title: "Identity",
      fields: [
        {
          name: "type",
          label: "Type",
          kind: "select",
          required: true,
          half: true,
          options: WORKHOLDING_TYPES.map((t) => ({ value: t, label: title(t) })),
          defaultValue: v.type ?? "VISE",
        },
        {
          name: "description",
          label: "Description",
          kind: "text",
          required: true,
          half: true,
          placeholder: '6" precision milling vise',
          defaultValue: v.description ?? null,
        },
        { name: "manufacturer", label: "Manufacturer", kind: "text", half: true, defaultValue: v.manufacturer ?? null },
        { name: "model", label: "Model", kind: "text", half: true, defaultValue: v.model ?? null },
      ],
    },
    {
      title: "Geometry",
      note: "Grip depth and stock projection are checked against jaw height. A part standing proud of the jaws is the lever arm that rolls it out of the vise.",
      fields: [
        { name: "jawWidth", label: "Jaw width", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.jawWidth ?? null },
        { name: "jawHeight", label: "Jaw height", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.jawHeight ?? null },
        { name: "maxOpening", label: "Maximum opening", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.maxOpening ?? null },
        {
          name: "fixtureHeight",
          label: "Fixture height",
          unit: "in",
          kind: "number",
          required: true,
          min: "0",
          half: true,
          hint: "Base to the top of the jaws. Checked against Z travel.",
          defaultValue: v.fixtureHeight ?? null,
        },
        {
          name: "mountingGeometry",
          label: "Mounting",
          kind: "text",
          half: true,
          placeholder: "Table T-slots, 4 bolts",
          defaultValue: v.mountingGeometry ?? null,
        },
      ],
    },
    {
      title: "Clamping",
      note: "Left blank, the holding margin comes back INDETERMINATE and names clamp force as the input it wanted. That is the correct answer for a vise nobody has measured — better than a catalogue figure entered as though it were observed.",
      fields: [
        {
          name: "clampForce",
          label: "Clamp force",
          unit: "lbf",
          kind: "number",
          min: "0",
          half: true,
          hint: "Measured, or from a torque-to-force chart for the handle torque actually used.",
          defaultValue: v.clampForce ?? null,
        },
        { name: "notes", label: "Notes", kind: "textarea", defaultValue: v.notes ?? null },
      ],
    },
  ];
}

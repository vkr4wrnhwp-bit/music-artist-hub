import { PRINT_TECHNOLOGIES, TECHNOLOGY_LABEL, type PrintTechnology } from "@/lib/engines/additive";
import type { ShopSection } from "@/components/shop-form";

/**
 * The printer record, as a form.
 *
 * `achievableTolerance` is the field that matters and it is deliberately NOT
 * required and never pre-filled. It is what the shop measured on a printed
 * coupon, and it is the number the additive advisor divides a tolerance band
 * by — so a machine entered at the manufacturer's figure will be called
 * capable of a bore it cannot hold.
 *
 * Blank is a real answer here, and a better one than a guess: the advisor
 * reports "nobody has measured what this machine holds — print a coupon"
 * rather than passing or failing on a number nobody stands behind.
 */

export interface PrinterFormValues {
  manufacturer?: string;
  model?: string;
  technology?: string;
  buildX?: number;
  buildY?: number;
  buildZ?: number;
  achievableTolerance?: number | null;
  achievableRa?: number | null;
  minLayerHeight?: number | null;
  nozzleDiameter?: number | null;
  notes?: string | null;
}

export function printerSections(v: PrinterFormValues): ShopSection[] {
  return [
    {
      title: "Machine",
      fields: [
        {
          name: "manufacturer",
          label: "Manufacturer",
          kind: "text",
          required: true,
          half: true,
          placeholder: "Prusa",
          defaultValue: v.manufacturer ?? null,
        },
        {
          name: "model",
          label: "Model",
          kind: "text",
          required: true,
          half: true,
          placeholder: "MK4",
          defaultValue: v.model ?? null,
        },
        {
          name: "technology",
          label: "Technology",
          kind: "select",
          required: true,
          half: true,
          options: PRINT_TECHNOLOGIES.map((t) => ({ value: t, label: TECHNOLOGY_LABEL[t as PrintTechnology] })),
          defaultValue: v.technology ?? "FDM",
          hint: "Decides which of your print materials this machine can run.",
        },
      ],
    },
    {
      title: "Build volume",
      note: "Inches. A part is checked against these in any orientation, because it can be turned on the bed — so the order they are entered in does not matter.",
      fields: [
        { name: "buildX", label: "X", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.buildX ?? null },
        { name: "buildY", label: "Y", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.buildY ?? null },
        { name: "buildZ", label: "Z", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.buildZ ?? null },
      ],
    },
    {
      title: "What it actually holds",
      note: "Measured on a printed coupon, not taken from the datasheet. Leave blank if nobody has measured it — the advisor will say so and tell you to print one, which is more use than a number nobody stands behind.",
      fields: [
        {
          name: "achievableTolerance",
          label: "Achievable tolerance",
          unit: "± in",
          kind: "number",
          min: "0",
          half: true,
          placeholder: "0.008",
          hint: "The advisor divides the part's tightest tolerance band by this. A machine entered optimistically will be called capable of a feature it cannot hold.",
          defaultValue: v.achievableTolerance ?? null,
        },
        {
          name: "achievableRa",
          label: "Surface finish",
          unit: "Ra µin",
          kind: "number",
          min: "0",
          half: true,
          placeholder: "500",
          defaultValue: v.achievableRa ?? null,
        },
        {
          name: "minLayerHeight",
          label: "Minimum layer height",
          unit: "in",
          kind: "number",
          min: "0",
          half: true,
          defaultValue: v.minLayerHeight ?? null,
        },
        {
          name: "nozzleDiameter",
          label: "Nozzle diameter",
          unit: "in",
          kind: "number",
          min: "0",
          half: true,
          hint: "FDM only. Leave blank for resin and powder machines.",
          defaultValue: v.nozzleDiameter ?? null,
        },
      ],
    },
    {
      title: "Notes",
      fields: [
        {
          name: "notes",
          label: "Notes",
          kind: "textarea",
          placeholder: "How the tolerance figure was measured, which profile it applies to, anything the next person needs.",
          defaultValue: v.notes ?? null,
        },
      ],
    },
  ];
}

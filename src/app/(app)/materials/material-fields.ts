import type { ShopSection } from "@/components/shop-form";

/**
 * The material record, as a form.
 *
 * Strength properties are optional and stay that way. The load reasoning
 * reads yield and tensile strength, and where they are missing it says which
 * figure it needed rather than substituting one for "6061-ish". A material
 * with a blank yield strength is a material CANVAS will not size a load
 * against — correct behaviour, and strictly better than one it will size
 * against a number nobody sourced.
 *
 * Specific cutting energy is required, because the cutting force model
 * divides by it on every operation and there is no sane fallback across the
 * range: aluminium is about 0.3 hp/in³/min and steel about 1.0, a factor of
 * three that lands directly in the spindle load estimate.
 */

export const FAMILIES = [
  "ALUMINUM",
  "STEEL",
  "STAINLESS",
  "TOOL_STEEL",
  "TITANIUM",
  "BRASS",
  "BRONZE",
  "COPPER",
  "CAST_IRON",
  "PLASTIC",
  "COMPOSITE",
  "OTHER",
] as const;

export const title = (s: string) => s.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());

export interface MaterialFormValues {
  name?: string;
  family?: string;
  condition?: string;
  density?: number;
  hardness?: number | null;
  yieldStrength?: number | null;
  tensileStrength?: number | null;
  machinabilityRating?: number;
  sfmCarbideMin?: number;
  sfmCarbideMax?: number;
  specificEnergy?: number;
  costPerPound?: number;
  weldable?: boolean;
  castable?: boolean;
  notes?: string | null;
}

export function materialSections(v: MaterialFormValues): ShopSection[] {
  return [
    {
      title: "Identity",
      fields: [
        { name: "name", label: "Name", kind: "text", required: true, half: true, placeholder: "Aluminum 6061", defaultValue: v.name ?? null },
        {
          name: "family",
          label: "Family",
          kind: "select",
          required: true,
          half: true,
          options: FAMILIES.map((x) => ({ value: x, label: title(x) })),
          defaultValue: v.family ?? "ALUMINUM",
        },
        { name: "condition", label: "Condition / temper", kind: "text", required: true, half: true, placeholder: "T6", defaultValue: v.condition ?? null },
        { name: "density", label: "Density", unit: "lb/in³", kind: "number", required: true, min: "0", half: true, placeholder: "0.098", defaultValue: v.density ?? null },
      ],
    },
    {
      title: "Cutting behaviour",
      note: "Specific cutting energy is what the force model divides by on every operation — aluminium is about 0.3 hp/in³/min and steel about 1.0. There is no safe default across that range, so it is required.",
      fields: [
        { name: "specificEnergy", label: "Specific cutting energy", unit: "hp/in³/min", kind: "number", required: true, min: "0", half: true, placeholder: "0.3", defaultValue: v.specificEnergy ?? null },
        { name: "machinabilityRating", label: "Machinability rating", unit: "% of B1112", kind: "number", required: true, min: "0", half: true, placeholder: "190", defaultValue: v.machinabilityRating ?? null },
        { name: "sfmCarbideMin", label: "Carbide surface speed min", unit: "sfm", kind: "number", required: true, min: "0", half: true, defaultValue: v.sfmCarbideMin ?? null },
        { name: "sfmCarbideMax", label: "Carbide surface speed max", unit: "sfm", kind: "number", required: true, min: "0", half: true, defaultValue: v.sfmCarbideMax ?? null },
      ],
    },
    {
      title: "Strength",
      note: "Optional, and left blank means not recorded. CANVAS will then decline to size a load against this material and name the figure it wanted, rather than borrowing one from a similar alloy.",
      fields: [
        { name: "hardness", label: "Hardness", unit: "HB", kind: "number", min: "0", half: true, defaultValue: v.hardness ?? null },
        { name: "yieldStrength", label: "Yield strength", unit: "psi", kind: "number", min: "0", half: true, defaultValue: v.yieldStrength ?? null },
        { name: "tensileStrength", label: "Tensile strength", unit: "psi", kind: "number", min: "0", half: true, defaultValue: v.tensileStrength ?? null },
        { name: "costPerPound", label: "Cost per pound", unit: "currency", kind: "number", required: true, min: "0", half: true, defaultValue: v.costPerPound ?? null },
      ],
    },
    {
      title: "Process compatibility",
      note: "Read by process recommendation. CANVAS does not assume CNC machining is the answer, and these decide which alternatives it is allowed to raise at all.",
      fields: [
        { name: "weldable", label: "Weldable", kind: "checkbox", half: true, defaultValue: v.weldable ?? false },
        { name: "castable", label: "Castable", kind: "checkbox", half: true, defaultValue: v.castable ?? false },
        { name: "notes", label: "Notes", kind: "textarea", defaultValue: v.notes ?? null },
      ],
    },
  ];
}

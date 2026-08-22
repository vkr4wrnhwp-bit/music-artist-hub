import { TOOL_CLASSES } from "@/lib/domain/shop";
import type { ShopSection } from "@/components/shop-form";

/**
 * The tool crib record, as a form.
 *
 * Which fields are REQUIRED is not a style choice — it is the set a
 * deterministic engine reads and returns null without:
 *
 *   diameter, cornerRadius → feature access. Corner radius decides whether
 *     an internal corner is machinable at all.
 *   flutes, chipload, sfm  → feed and speed. cutting-force.ts computes
 *     nothing without them.
 *   stickout, fluteLength  → reach. Whether a depth is cuttable.
 *   maxRPM                 → machine validation against spindle limits.
 *
 * Everything genuinely optional stays nullable and is stored as null, which
 * every engine already handles by naming it as a missing input. Nothing here
 * gets a plausible default to make the record look finished.
 */

const CONDITIONS = ["NEW", "GOOD", "WORN", "REGRIND", "UNKNOWN"] as const;
const COOLANTS = ["FLOOD", "MIST", "THROUGH_TOOL", "AIR_BLAST", "DRY"] as const;

export const TOOL_CONDITIONS = CONDITIONS;
export const TOOL_COOLANTS = COOLANTS;

const title = (s: string) => s.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());

/** Existing values when editing; everything undefined when creating. */
export interface ToolFormValues {
  toolNumber?: number;
  toolClass?: string;
  description?: string;
  manufacturer?: string | null;
  product?: string | null;
  diameter?: number;
  cornerRadius?: number;
  flutes?: number;
  material?: string;
  coating?: string | null;
  fluteLength?: number;
  overallLength?: number;
  stickout?: number;
  holderId?: string | null;
  maxRPM?: number;
  recommendedMaterials?: string;
  chiploadMin?: number;
  chiploadMax?: number;
  sfmMin?: number;
  sfmMax?: number;
  coolant?: string;
  lifeRemaining?: number;
  costPerTool?: number;
  expectedLifeMinutes?: number;
  condition?: string;
  actualStickout?: number | null;
  measuredRunout?: number | null;
  helixAngle?: number | null;
  notes?: string | null;
  shopNotes?: string | null;
}

/** Parses the stored JSON array back into the comma list the form shows. */
function materialList(json: string | undefined): string {
  if (!json) return "";
  try {
    const v = JSON.parse(json) as unknown;
    return Array.isArray(v) ? v.join(", ") : "";
  } catch {
    return "";
  }
}

export function toolSections(
  v: ToolFormValues,
  holders: { id: string; description: string; taper: string }[],
): ShopSection[] {
  return [
    {
      title: "Identity",
      note: "The tool number is how the post, the setup sheet and the operator all refer to this tool. It has to be unique in the crib.",
      fields: [
        { name: "toolNumber", label: "Tool number", kind: "number", required: true, min: "1", half: true, defaultValue: v.toolNumber ?? null },
        {
          name: "toolClass",
          label: "Class",
          kind: "select",
          required: true,
          half: true,
          options: TOOL_CLASSES.map((c) => ({ value: c, label: title(c) })),
          defaultValue: v.toolClass ?? "FLAT_END_MILL",
        },
        { name: "description", label: "Description", kind: "text", required: true, placeholder: '1/2" 3-flute carbide end mill', defaultValue: v.description ?? null },
        { name: "manufacturer", label: "Manufacturer", kind: "text", half: true, defaultValue: v.manufacturer ?? null },
        { name: "product", label: "Product code", kind: "text", half: true, defaultValue: v.product ?? null },
      ],
    },
    {
      title: "Geometry",
      note: "Corner radius decides whether an internal corner is machinable at all. Stickout decides whether a depth is reachable. Neither has a safe default.",
      fields: [
        { name: "diameter", label: "Diameter", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.diameter ?? null },
        { name: "cornerRadius", label: "Corner radius", unit: "in", kind: "number", required: true, min: "0", half: true, hint: "Zero for a square end mill.", defaultValue: v.cornerRadius ?? 0 },
        { name: "flutes", label: "Flutes", kind: "number", required: true, min: "1", half: true, defaultValue: v.flutes ?? null },
        { name: "helixAngle", label: "Helix angle", unit: "deg", kind: "number", min: "0", max: "90", half: true, hint: "Optional. Raises the cutting model's accuracy when recorded.", defaultValue: v.helixAngle ?? null },
        { name: "fluteLength", label: "Flute length", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.fluteLength ?? null },
        { name: "overallLength", label: "Overall length", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.overallLength ?? null },
        { name: "stickout", label: "Stickout", unit: "in", kind: "number", required: true, min: "0", half: true, hint: "Nominal, as the tool is normally set.", defaultValue: v.stickout ?? null },
        {
          name: "holderId",
          label: "Holder",
          kind: "select",
          half: true,
          options: holders.map((h) => ({ value: h.id, label: `${h.taper} — ${h.description}` })),
          defaultValue: v.holderId ?? null,
        },
      ],
    },
    {
      title: "Cutting data",
      note: "Chipload and surface speed are what the feed and speed calculation actually reads. Without them CANVAS will not propose a feed rate — it will say the tool has no cutting data.",
      fields: [
        { name: "material", label: "Tool material", kind: "text", required: true, half: true, placeholder: "Carbide", defaultValue: v.material ?? null },
        { name: "coating", label: "Coating", kind: "text", half: true, placeholder: "AlTiN", defaultValue: v.coating ?? null },
        { name: "chiploadMin", label: "Chipload min", unit: "in/tooth", kind: "number", required: true, min: "0", half: true, defaultValue: v.chiploadMin ?? null },
        { name: "chiploadMax", label: "Chipload max", unit: "in/tooth", kind: "number", required: true, min: "0", half: true, defaultValue: v.chiploadMax ?? null },
        { name: "sfmMin", label: "Surface speed min", unit: "sfm", kind: "number", required: true, min: "0", half: true, defaultValue: v.sfmMin ?? null },
        { name: "sfmMax", label: "Surface speed max", unit: "sfm", kind: "number", required: true, min: "0", half: true, defaultValue: v.sfmMax ?? null },
        { name: "maxRPM", label: "Maximum RPM", kind: "number", required: true, min: "1", half: true, defaultValue: v.maxRPM ?? null },
        {
          name: "coolant",
          label: "Coolant",
          kind: "select",
          required: true,
          half: true,
          options: COOLANTS.map((c) => ({ value: c, label: title(c) })),
          defaultValue: v.coolant ?? "FLOOD",
        },
        {
          name: "recommendedMaterials",
          label: "Recommended materials",
          kind: "text",
          hint: "Comma separated, e.g. Aluminum, Brass, Plastic. Used to flag a tool being pointed at a material it was not chosen for.",
          defaultValue: materialList(v.recommendedMaterials),
        },
      ],
    },
    {
      title: "Tool reality",
      note: "What is actually in the holder, as opposed to what the catalogue page said. A worn edge ploughs rather than cuts and raises specific cutting force, so the cutting model reads condition directly.",
      fields: [
        {
          name: "condition",
          label: "Condition",
          kind: "select",
          required: true,
          half: true,
          options: CONDITIONS.map((c) => ({ value: c, label: title(c) })),
          defaultValue: v.condition ?? "UNKNOWN",
        },
        { name: "lifeRemaining", label: "Life remaining", unit: "0–1", kind: "number", required: true, min: "0", max: "1", half: true, defaultValue: v.lifeRemaining ?? 1 },
        { name: "actualStickout", label: "Measured stickout", unit: "in", kind: "number", min: "0", half: true, hint: "Left blank means not measured — not that it matches nominal.", defaultValue: v.actualStickout ?? null },
        { name: "measuredRunout", label: "Measured runout", unit: "in", kind: "number", min: "0", half: true, defaultValue: v.measuredRunout ?? null },
        { name: "expectedLifeMinutes", label: "Expected life", unit: "min", kind: "number", required: true, min: "0", half: true, defaultValue: v.expectedLifeMinutes ?? 120 },
        { name: "costPerTool", label: "Cost per tool", unit: "currency", kind: "number", required: true, min: "0", half: true, defaultValue: v.costPerTool ?? 0 },
        { name: "notes", label: "Notes", kind: "textarea", defaultValue: v.notes ?? null },
        { name: "shopNotes", label: "Shop notes", kind: "textarea", hint: "What this shop has learned about this tool. Scoped to this shop — never promoted into a published engineering fact.", defaultValue: v.shopNotes ?? null },
      ],
    },
  ];
}

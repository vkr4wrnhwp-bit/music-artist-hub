import { PRINT_TECHNOLOGIES, TECHNOLOGY_LABEL, type PrintTechnology } from "@/lib/engines/additive";
import type { ShopSection } from "@/components/shop-form";

/**
 * A printable material, as a form.
 *
 * The pair that matters is the two tensile figures. A printed part is
 * continuous within a layer and BONDED between layers, so its strength through
 * Z is a fraction of its strength in plane — commonly half for FDM, much
 * closer to parity for SLS and resin.
 *
 * The Z figure is optional and blank is honest. Most shops have not measured
 * it, and the advisor treats a missing Z as a reason it cannot judge a load
 * across the layers, rather than assuming it equals the in-plane number. That
 * assumption is the one that breaks a printed part.
 */

export interface PrintMaterialFormValues {
  name?: string;
  technology?: string;
  tensileXY?: number | null;
  tensileZ?: number | null;
  maxServiceTempF?: number | null;
  creepDataOnFile?: boolean;
  densityLbIn3?: number | null;
  costPerPound?: number | null;
  notes?: string | null;
}

export function printMaterialSections(v: PrintMaterialFormValues): ShopSection[] {
  return [
    {
      title: "Material",
      fields: [
        {
          name: "name",
          label: "Name",
          kind: "text",
          required: true,
          half: true,
          placeholder: "PETG — Prusament",
          defaultValue: v.name ?? null,
        },
        {
          name: "technology",
          label: "Technology",
          kind: "select",
          required: true,
          half: true,
          options: PRINT_TECHNOLOGIES.map((t) => ({ value: t, label: TECHNOLOGY_LABEL[t as PrintTechnology] })),
          defaultValue: v.technology ?? "FDM",
          hint: "Only machines of this technology are judged against this material.",
        },
      ],
    },
    {
      title: "Strength, in plane and through the layers",
      note: "A printed part is bonded between layers rather than continuous through them. Where a part is loaded across the layers, the Z figure is the one that governs — and leaving it blank is better than copying the in-plane number, because assuming they are equal is the assumption that breaks the part.",
      fields: [
        {
          name: "tensileXY",
          label: "Tensile strength, in plane",
          unit: "psi",
          kind: "number",
          min: "0",
          half: true,
          placeholder: "7100",
          defaultValue: v.tensileXY ?? null,
        },
        {
          name: "tensileZ",
          label: "Tensile strength, through Z",
          unit: "psi",
          kind: "number",
          min: "0",
          half: true,
          placeholder: "3250",
          hint: "Measured on a coupon printed upright and pulled apart. Blank if nobody has measured it.",
          defaultValue: v.tensileZ ?? null,
        },
      ],
    },
    {
      title: "Service conditions",
      note: "Above its deflection temperature a polymer is not a structural material. A sustained load is a creep question that a tensile figure does not answer.",
      fields: [
        {
          name: "maxServiceTempF",
          label: "Maximum service temperature",
          unit: "°F",
          kind: "number",
          half: true,
          placeholder: "160",
          defaultValue: v.maxServiceTempF ?? null,
        },
        {
          name: "creepDataOnFile",
          label: "A creep figure is on file for this material",
          kind: "checkbox",
          half: true,
          hint: "Leave unchecked unless you actually hold one. The advisor names the gap for parts under sustained load.",
          defaultValue: v.creepDataOnFile ?? false,
        },
      ],
    },
    {
      title: "Cost and density",
      fields: [
        {
          name: "densityLbIn3",
          label: "Density",
          unit: "lb/in³",
          kind: "number",
          min: "0",
          half: true,
          placeholder: "0.0459",
          defaultValue: v.densityLbIn3 ?? null,
        },
        {
          name: "costPerPound",
          label: "Cost",
          unit: "$/lb",
          kind: "number",
          min: "0",
          half: true,
          defaultValue: v.costPerPound ?? null,
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
          placeholder: "Where the figures came from, which print profile they apply to.",
          defaultValue: v.notes ?? null,
        },
      ],
    },
  ];
}

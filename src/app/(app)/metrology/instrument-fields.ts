import { METROLOGY_DEVICES, METROLOGY_LABELS, DEVICE_UNCERTAINTY } from "@/lib/domain/shop";
import type { ShopSection } from "@/components/shop-form";

/**
 * The instrument record, as a form.
 *
 * Uncertainty is required and is never pre-filled. It is the number
 * `assessCapability` divides the tolerance band by, so it decides every
 * inspection-capability verdict the shop will ever see. The hint lists
 * typical figures by class as a sanity check, but typing one is the
 * operator's decision — CANVAS will not fill in an uncertainty it did not
 * observe, because a caliper entered at ±0.0002 will be called capable of a
 * bore it cannot verify and the gate that exists to catch that will pass.
 */

export interface InstrumentFormValues {
  deviceType?: string;
  description?: string;
  rangeMin?: number | null;
  rangeMax?: number | null;
  resolution?: number;
  uncertainty?: number;
  calibrated?: boolean;
  calibrationDue?: Date | string | null;
}

function isoDate(v: Date | string | null | undefined): string | null {
  if (!v) return null;
  const d = v instanceof Date ? v : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d.toISOString().slice(0, 10);
}

/** A handful of typical figures, for a sanity check only. */
const TYPICAL = (["DIGITAL_CALIPER", "MICROMETER", "BORE_GAUGE", "HEIGHT_GAUGE", "CMM"] as const)
  .map((d) => `${METROLOGY_LABELS[d]} ±${DEVICE_UNCERTAINTY[d]}`)
  .join(", ");

export function instrumentSections(v: InstrumentFormValues): ShopSection[] {
  return [
    {
      title: "Instrument",
      fields: [
        {
          name: "deviceType",
          label: "Type",
          kind: "select",
          required: true,
          half: true,
          options: METROLOGY_DEVICES.map((d) => ({ value: d, label: METROLOGY_LABELS[d] })),
          defaultValue: v.deviceType ?? "DIGITAL_CALIPER",
        },
        {
          name: "description",
          label: "Description",
          kind: "text",
          required: true,
          half: true,
          placeholder: '0–6" digital calipers',
          defaultValue: v.description ?? null,
        },
        {
          name: "rangeMin",
          label: "Range min",
          unit: "in",
          kind: "number",
          min: "0",
          half: true,
          hint: "Leave blank for an instrument with no stated range, such as a surface plate.",
          defaultValue: v.rangeMin ?? null,
        },
        { name: "rangeMax", label: "Range max", unit: "in", kind: "number", min: "0", half: true, defaultValue: v.rangeMax ?? null },
      ],
    },
    {
      title: "What it can actually resolve",
      note: "Resolution is the smallest division it displays. Uncertainty is how much the reading could be wrong in shop conditions — a larger number, and the one the capability verdict is computed from.",
      fields: [
        {
          name: "resolution",
          label: "Resolution",
          unit: "in",
          kind: "number",
          required: true,
          min: "0",
          half: true,
          placeholder: "0.0005",
          defaultValue: v.resolution ?? null,
        },
        {
          name: "uncertainty",
          label: "Expanded uncertainty",
          unit: "± in",
          kind: "number",
          required: true,
          min: "0",
          half: true,
          hint: `Typical figures by class, for a sanity check only: ${TYPICAL}. Enter what this instrument achieves, not what the class usually does.`,
          defaultValue: v.uncertainty ?? null,
        },
      ],
    },
    {
      title: "Calibration",
      note: "An instrument that is out of calibration still measures — it just cannot be evidence. CANVAS shows the state rather than hiding the instrument.",
      fields: [
        { name: "calibrated", label: "Calibration certificate is current", kind: "checkbox", half: true, defaultValue: v.calibrated ?? false },
        {
          name: "calibrationDue",
          label: "Calibration due",
          kind: "text",
          half: true,
          placeholder: "2027-03-01",
          hint: "ISO date. Blank means no certificate date is recorded.",
          defaultValue: isoDate(v.calibrationDue),
        },
      ],
    },
  ];
}

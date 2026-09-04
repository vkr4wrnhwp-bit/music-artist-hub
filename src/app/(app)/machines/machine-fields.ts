import { MACHINE_TYPES, CONTROLLERS } from "@/lib/domain/shop";
import { POSTS } from "@/lib/engines/cam/post";
import type { ShopSection } from "@/components/shop-form";

/**
 * The machine record, as a form.
 *
 * Travels and table size are required because machine validation is a real
 * gate: a part whose envelope exceeds the machine fails MACHINE ENVELOPE and
 * says by how much. A machine recorded without travels cannot fail that gate,
 * which means it cannot pass it honestly either.
 *
 * Axis acceleration is optional on purpose, and the schema comment says why:
 * left null, cycle time estimates stay distance-over-feed and state that they
 * ignore acceleration, rather than assuming a figure and reporting a cycle
 * time that looks measured.
 */

export const title = (s: string) => s.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());

export interface MachineFormValues {
  manufacturer?: string;
  model?: string;
  controller?: string;
  machineType?: string;
  axisCount?: number;
  travelsX?: number;
  travelsY?: number;
  travelsZ?: number;
  tableX?: number;
  tableY?: number;
  maxSpindleRPM?: number;
  maxSpindlePower?: number;
  maxSpindleTorque?: number;
  maxFeed?: number;
  maxRapid?: number;
  axisAccel?: number | null;
  toolChangerCapacity?: number;
  maxToolDiameter?: number;
  maxToolLength?: number;
  maxToolWeight?: number;
  coolantTypes?: string;
  throughSpindleCoolant?: boolean;
  probe?: boolean;
  toolSetter?: boolean;
  fourthAxis?: boolean;
  fifthAxis?: boolean;
  supportedPostProcessor?: string;
  controlVersion?: string | null;
  notes?: string | null;
}

/** The stored JSON array, back to the comma list the form shows. */
function coolantList(json: string | undefined): string {
  if (!json) return "";
  try {
    const v = JSON.parse(json) as unknown;
    return Array.isArray(v) ? v.join(", ") : "";
  } catch {
    return "";
  }
}

export function machineSections(v: MachineFormValues): ShopSection[] {
  return [
    {
      title: "Identity",
      fields: [
        { name: "manufacturer", label: "Manufacturer", kind: "text", required: true, half: true, placeholder: "Haas", defaultValue: v.manufacturer ?? null },
        { name: "model", label: "Model", kind: "text", required: true, half: true, placeholder: "VF-2", defaultValue: v.model ?? null },
        {
          name: "machineType",
          label: "Type",
          kind: "select",
          required: true,
          half: true,
          options: MACHINE_TYPES.map((t) => ({ value: t, label: title(t) })),
          defaultValue: v.machineType ?? "VMC_3AXIS",
        },
        { name: "axisCount", label: "Axis count", kind: "number", required: true, min: "2", max: "9", half: true, defaultValue: v.axisCount ?? 3 },
        {
          name: "controller",
          label: "Controller",
          kind: "select",
          required: true,
          half: true,
          options: CONTROLLERS.map((c) => ({ value: c, label: title(c) })),
          defaultValue: v.controller ?? "HAAS_NGC",
        },
        {
          name: "supportedPostProcessor",
          label: "Post processor",
          kind: "select",
          half: true,
          options: POSTS.map((p) => ({ value: p.id, label: p.name })),
          hint: "Every post in the registry is a development post — none is certified against a machine. Blank picks the default for the controller.",
          defaultValue: v.supportedPostProcessor ?? null,
        },
        {
          name: "controlVersion",
          label: "Control software version",
          kind: "text",
          half: true,
          placeholder: "100.22.000.1130",
          hint: "As it reads on the machine. A post validation is scoped to it, because a control update can change how a canned cycle retracts or how look-ahead handles short blocks. Blank means nobody has recorded it, and a proof cannot be matched against a version nobody wrote down.",
          defaultValue: v.controlVersion ?? null,
        },
      ],
    },
    {
      title: "Envelope",
      note: "Checked directly against the part's bounding box and the setup's fixture height. Both the travel and the table matter — a part can fit the travels and not fit the table.",
      fields: [
        { name: "travelsX", label: "X travel", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.travelsX ?? null },
        { name: "travelsY", label: "Y travel", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.travelsY ?? null },
        { name: "travelsZ", label: "Z travel", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.travelsZ ?? null },
        { name: "tableX", label: "Table X", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.tableX ?? null },
        { name: "tableY", label: "Table Y", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.tableY ?? null },
      ],
    },
    {
      title: "Spindle and motion",
      note: "Spindle power bounds what the cutting model is allowed to propose. Axis acceleration is optional — left blank, cycle estimates stay distance over feed and say that they ignore acceleration rather than assuming a figure.",
      fields: [
        { name: "maxSpindleRPM", label: "Maximum spindle RPM", kind: "number", required: true, min: "1", half: true, defaultValue: v.maxSpindleRPM ?? null },
        { name: "maxSpindlePower", label: "Spindle power", unit: "hp", kind: "number", required: true, min: "0", half: true, defaultValue: v.maxSpindlePower ?? null },
        { name: "maxSpindleTorque", label: "Spindle torque", unit: "ft-lbf", kind: "number", required: true, min: "0", half: true, defaultValue: v.maxSpindleTorque ?? null },
        { name: "maxFeed", label: "Maximum feed", unit: "ipm", kind: "number", required: true, min: "0", half: true, defaultValue: v.maxFeed ?? null },
        { name: "maxRapid", label: "Maximum rapid", unit: "ipm", kind: "number", required: true, min: "0", half: true, defaultValue: v.maxRapid ?? null },
        { name: "axisAccel", label: "Axis acceleration", unit: "in/s²", kind: "number", min: "0", half: true, defaultValue: v.axisAccel ?? null },
      ],
    },
    {
      title: "Tooling limits",
      note: "The changer's own limits. Loading a tool into a pocket is checked against these, so a cutter that will not fit is refused with both figures named rather than recorded and discovered at the machine.",
      fields: [
        { name: "toolChangerCapacity", label: "Tool changer pockets", kind: "number", required: true, min: "0", half: true, defaultValue: v.toolChangerCapacity ?? null },
        { name: "maxToolDiameter", label: "Maximum tool diameter", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.maxToolDiameter ?? null },
        { name: "maxToolLength", label: "Maximum tool length", unit: "in", kind: "number", required: true, min: "0", half: true, defaultValue: v.maxToolLength ?? null },
        { name: "maxToolWeight", label: "Maximum tool weight", unit: "lb", kind: "number", required: true, min: "0", half: true, defaultValue: v.maxToolWeight ?? null },
      ],
    },
    {
      title: "Equipment",
      note: "A probe the machine does not have is a measurement plan that cannot run. These are checked before a probing routine is proposed.",
      fields: [
        { name: "coolantTypes", label: "Coolant types", kind: "text", half: true, placeholder: "Flood, Mist", hint: "Comma separated.", defaultValue: coolantList(v.coolantTypes) },
        { name: "throughSpindleCoolant", label: "Through-spindle coolant", kind: "checkbox", half: true, defaultValue: v.throughSpindleCoolant ?? false },
        { name: "probe", label: "Spindle probe", kind: "checkbox", half: true, defaultValue: v.probe ?? false },
        { name: "toolSetter", label: "Tool setter", kind: "checkbox", half: true, defaultValue: v.toolSetter ?? false },
        { name: "fourthAxis", label: "Fourth axis", kind: "checkbox", half: true, defaultValue: v.fourthAxis ?? false },
        { name: "fifthAxis", label: "Fifth axis", kind: "checkbox", half: true, defaultValue: v.fifthAxis ?? false },
        { name: "notes", label: "Notes", kind: "textarea", defaultValue: v.notes ?? null },
      ],
    },
  ];
}

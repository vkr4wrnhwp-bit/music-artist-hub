import Link from "next/link";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { MACHINE_TYPES, CONTROLLERS } from "@/lib/domain/shop";
import { POSTS, defaultPostForController } from "@/lib/engines/cam/post";
import { FormReader, rejectionQuery } from "@/lib/shop-form";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";

const title = (s: string) => s.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase());

/**
 * Add a machine.
 *
 * Travels and table size are required because machine validation is a real
 * gate: a part whose envelope exceeds the machine fails MACHINE ENVELOPE and
 * says by how much. A machine recorded without travels cannot fail that gate
 * and so cannot pass it honestly either.
 *
 * Axis acceleration is optional on purpose, and the schema comment says why:
 * left null, cycle time estimates stay distance-over-feed and state that
 * they ignore acceleration, rather than assuming a figure and reporting a
 * cycle time that looks measured.
 *
 * Every post processor in the registry is marked `certified: false`. The
 * form says so rather than presenting a picker that implies otherwise.
 */
export default async function NewMachinePage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  await requireUser();

  async function createMachine(formData: FormData): Promise<void> {
    "use server";
    const user = await requireUser();
    const f = new FormReader(formData);

    const controller = f.choice("controller", "Controller", CONTROLLERS);
    const chosenPost = f.optionalText("supportedPostProcessor");
    const data = {
      manufacturer: f.text("manufacturer", "Manufacturer"),
      model: f.text("model", "Model"),
      controller,
      machineType: f.choice("machineType", "Machine type", MACHINE_TYPES),
      axisCount: f.integer("axisCount", "Axis count", { min: 2, max: 9 }),

      travelsX: f.number("travelsX", "X travel", { min: 0 }),
      travelsY: f.number("travelsY", "Y travel", { min: 0 }),
      travelsZ: f.number("travelsZ", "Z travel", { min: 0 }),
      tableX: f.number("tableX", "Table X", { min: 0 }),
      tableY: f.number("tableY", "Table Y", { min: 0 }),

      maxSpindleRPM: f.integer("maxSpindleRPM", "Maximum spindle RPM", { min: 1 }),
      maxSpindlePower: f.number("maxSpindlePower", "Spindle power", { min: 0 }),
      maxSpindleTorque: f.number("maxSpindleTorque", "Spindle torque", { min: 0 }),
      maxFeed: f.number("maxFeed", "Maximum feed", { min: 0 }),
      maxRapid: f.number("maxRapid", "Maximum rapid", { min: 0 }),
      axisAccel: f.optionalNumber("axisAccel", "Axis acceleration", { min: 0 }),

      toolChangerCapacity: f.integer("toolChangerCapacity", "Tool changer capacity", { min: 0 }),
      maxToolDiameter: f.number("maxToolDiameter", "Maximum tool diameter", { min: 0 }),
      maxToolLength: f.number("maxToolLength", "Maximum tool length", { min: 0 }),
      maxToolWeight: f.number("maxToolWeight", "Maximum tool weight", { min: 0 }),

      coolantTypes: f.jsonList("coolantTypes"),
      throughSpindleCoolant: f.boolean("throughSpindleCoolant"),
      probe: f.boolean("probe"),
      toolSetter: f.boolean("toolSetter"),
      fourthAxis: f.boolean("fourthAxis"),
      fifthAxis: f.boolean("fifthAxis"),
      supportedPostProcessor:
        chosenPost && POSTS.some((p) => p.id === chosenPost) ? chosenPost : defaultPostForController(controller).id,
      // A machine a shop entered is a machine the shop owns. Reference
      // profiles are seeded example data and are never created from here.
      isReferenceProfile: false,
      notes: f.optionalText("notes"),
    };

    try {
      f.done();
    } catch (err) {
      redirect(`/machines/new${rejectionQuery(err)}`);
    }

    const row = await db.machine.create({ data: { ...data, organizationId: user.organizationId } });
    await audit({
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "Machine",
      entityId: row.id,
      action: "CREATE",
      actorType: "HUMAN",
      field: "machine",
      newValue: `${data.manufacturer} ${data.model} · ${data.travelsX}×${data.travelsY}×${data.travelsZ} · ${data.maxSpindleRPM} rpm`,
      reason: "Machine added to the shop.",
    });
    revalidatePath("/machines");
    redirect("/machines");
  }

  return (
    <>
      <TopBar>
        <Link href="/machines" className="tech-label hover:text-platinum">
          Machines
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New machine</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="Travels, spindle and changer limits are what the machine envelope gate is checked against. A machine recorded without them cannot fail that gate, which means it cannot pass it honestly either.">
            Add a machine
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm
            action={createMachine}
            submitLabel="Add machine"
            cancelHref="/machines"
            sections={[
              {
                title: "Identity",
                fields: [
                  { name: "manufacturer", label: "Manufacturer", kind: "text", required: true, half: true, placeholder: "Haas" },
                  { name: "model", label: "Model", kind: "text", required: true, half: true, placeholder: "VF-2" },
                  {
                    name: "machineType",
                    label: "Type",
                    kind: "select",
                    required: true,
                    half: true,
                    options: MACHINE_TYPES.map((t) => ({ value: t, label: title(t) })),
                    defaultValue: "VMC_3AXIS",
                  },
                  { name: "axisCount", label: "Axis count", kind: "number", required: true, min: "2", max: "9", half: true, defaultValue: 3 },
                  {
                    name: "controller",
                    label: "Controller",
                    kind: "select",
                    required: true,
                    half: true,
                    options: CONTROLLERS.map((c) => ({ value: c, label: title(c) })),
                    defaultValue: "HAAS_NGC",
                  },
                  {
                    name: "supportedPostProcessor",
                    label: "Post processor",
                    kind: "select",
                    half: true,
                    options: POSTS.map((p) => ({ value: p.id, label: p.name })),
                    hint: "Every post in the registry is a development post — none is certified against a machine. Blank picks the default for the controller.",
                  },
                ],
              },
              {
                title: "Envelope",
                note: "Checked directly against the part's bounding box and the setup's fixture height. Both the travel and the table matter — a part can fit the travels and not fit the table.",
                fields: [
                  { name: "travelsX", label: "X travel", unit: "in", kind: "number", required: true, min: "0", half: true },
                  { name: "travelsY", label: "Y travel", unit: "in", kind: "number", required: true, min: "0", half: true },
                  { name: "travelsZ", label: "Z travel", unit: "in", kind: "number", required: true, min: "0", half: true },
                  { name: "tableX", label: "Table X", unit: "in", kind: "number", required: true, min: "0", half: true },
                  { name: "tableY", label: "Table Y", unit: "in", kind: "number", required: true, min: "0", half: true },
                ],
              },
              {
                title: "Spindle and motion",
                note: "Spindle power bounds what the cutting model is allowed to propose. Axis acceleration is optional — left blank, cycle estimates stay distance over feed and say that they ignore acceleration rather than assuming a figure.",
                fields: [
                  { name: "maxSpindleRPM", label: "Maximum spindle RPM", kind: "number", required: true, min: "1", half: true },
                  { name: "maxSpindlePower", label: "Spindle power", unit: "hp", kind: "number", required: true, min: "0", half: true },
                  { name: "maxSpindleTorque", label: "Spindle torque", unit: "ft-lbf", kind: "number", required: true, min: "0", half: true },
                  { name: "maxFeed", label: "Maximum feed", unit: "ipm", kind: "number", required: true, min: "0", half: true },
                  { name: "maxRapid", label: "Maximum rapid", unit: "ipm", kind: "number", required: true, min: "0", half: true },
                  { name: "axisAccel", label: "Axis acceleration", unit: "in/s²", kind: "number", min: "0", half: true },
                ],
              },
              {
                title: "Tooling limits",
                fields: [
                  { name: "toolChangerCapacity", label: "Tool changer pockets", kind: "number", required: true, min: "0", half: true },
                  { name: "maxToolDiameter", label: "Maximum tool diameter", unit: "in", kind: "number", required: true, min: "0", half: true },
                  { name: "maxToolLength", label: "Maximum tool length", unit: "in", kind: "number", required: true, min: "0", half: true },
                  { name: "maxToolWeight", label: "Maximum tool weight", unit: "lb", kind: "number", required: true, min: "0", half: true },
                ],
              },
              {
                title: "Equipment",
                note: "A probe the machine does not have is a measurement plan that cannot run. These are checked before a probing routine is proposed.",
                fields: [
                  { name: "coolantTypes", label: "Coolant types", kind: "text", half: true, placeholder: "Flood, Mist", hint: "Comma separated." },
                  { name: "throughSpindleCoolant", label: "Through-spindle coolant", kind: "checkbox", half: true },
                  { name: "probe", label: "Spindle probe", kind: "checkbox", half: true },
                  { name: "toolSetter", label: "Tool setter", kind: "checkbox", half: true },
                  { name: "fourthAxis", label: "Fourth axis", kind: "checkbox", half: true },
                  { name: "fifthAxis", label: "Fifth axis", kind: "checkbox", half: true },
                  { name: "notes", label: "Notes", kind: "textarea" },
                ],
              },
            ]}
          />

          <Notice tone="review" title="Posts are development posts">
            No post processor in CANVAS has been certified against a physical machine. Whichever you pick, output is
            labelled as development and NC export stays behind the readiness gates. Prove any program on the machine
            before you trust it.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

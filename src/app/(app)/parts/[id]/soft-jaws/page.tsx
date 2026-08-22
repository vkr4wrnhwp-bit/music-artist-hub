import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import { generateSoftJaws } from "@/lib/engines/workholding";
import { assembleSoftJawRequest } from "@/lib/soft-jaw-request";
import type { JawBlank } from "@/lib/domain/shop";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { Button, DataRow, EmptyState, Field, Notice, Panel, SectionHeading, StatusChip, inputClass } from "@/components/ui";
import { selectWorkholdingDevice } from "@/lib/package-selectors";

/**
 * SOFT JAW GENERATOR
 *
 * Phase 1 generates a parametric rectangular seat with corner relief and the
 * process to cut it. The geometry is simplified; the data model is not, so a
 * full profile generator can replace `generateSoftJaws` without changing this
 * page or the stored records.
 */

export default async function SoftJawsPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ setup?: string; grip?: string; allowance?: string; clearance?: string; dir?: string; stop?: string }>;
}) {
  const { id } = await props.params;
  const sp = await props.searchParams;
  const user = await requireUser();

  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  const blanks = await db.jawBlank.findMany({ where: { organizationId: user.organizationId } });
  const setup = pkg.setups.find((s) => s.id === sp.setup) ?? pkg.setups.find((s) => s.sequence > 1) ?? pkg.setups[0];
  const device = selectWorkholdingDevice(pkg.workholdingDevices, setup);
  // Enumerated values are stored as strings in the DB and validated here at
  // the boundary, matching the schema's single-source-of-truth approach.
  const blank = blanks[0] ? { ...blanks[0], material: blanks[0].material as JawBlank["material"] } : undefined;

  if (!setup || !device || !blank || !pkg.revision.stock) {
    return (
      <>
        <TopBar>
          <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
            {pkg.revision.partName}
          </Link>
          <span className="text-muted">/</span>
          <span className="tech-label">Soft jaws</span>
                <PartStatusChip readiness={pkg.readiness} />
      </TopBar>
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          <div className="mx-auto max-w-2xl">
            <EmptyState
              title="Cannot generate soft jaws"
              body={
                !setup
                  ? "This part has no setups. Soft jaws are generated for a specific setup orientation."
                  : !device
                    ? "No vise is defined. The jaw design is derived from the vise's jaw width, height and opening."
                    : !blank
                      ? "No jaw blanks are on hand. Add a blank size in Workholding before generating."
                      : "Stock is not defined, so there is no part envelope to seat."
              }
              action={{ label: "Workholding", href: "/workholding" }}
            />
          </div>
        </main>
      </>
    );
  }

  // One assembler, shared with the save action and the DXF export, so the
  // drawing a machinist downloads cannot disagree with the page.
  const assembled = assembleSoftJawRequest(pkg, blank, {
    setupId: setup.id,
    grip: sp.grip != null ? Number(sp.grip) : null,
    allowance: sp.allowance != null ? Number(sp.allowance) : null,
    clearance: sp.clearance != null ? Number(sp.clearance) : null,
    includeStop: sp.stop != null ? sp.stop !== "0" : null,
    dir: sp.dir ?? null,
  })!; // the guard above already established setup, device, blank and stock
  const request = assembled.request;

  const result = generateSoftJaws(request);
  const assessment = pkg.workholdingBySetup[setup.id];

  async function saveJaws(formData: FormData) {
    "use server";
    const currentUser = await requireWrite();
    const fresh = await buildPackage(currentUser.organizationId, id);
    if (!fresh) notFound();

    const setupId = String(formData.get("setupId"));
    const grip = Number(formData.get("grip"));
    const freshSetup = fresh.setups.find((s) => s.id === setupId);
    const freshDevice = selectWorkholdingDevice(fresh.workholdingDevices, freshSetup);
    const blankRow = await db.jawBlank.findFirst({ where: { organizationId: currentUser.organizationId } });
    const freshBlank = blankRow ? { ...blankRow, material: blankRow.material as JawBlank["material"] } : null;
    if (!freshSetup || !freshDevice || !freshBlank || !fresh.revision.stock) notFound();

    const freshAssembled = assembleSoftJawRequest(fresh, freshBlank, {
      setupId,
      grip,
      allowance: Number(formData.get("allowance")),
      clearance: Number(formData.get("clearance")),
      includeStop: formData.get("stop") === "on",
      dir: String(formData.get("dir")),
    });
    if (!freshAssembled) notFound();
    const req = freshAssembled.request;

    const generated = generateSoftJaws(req);
    if (!generated.ok || !generated.left || !generated.right) redirect(`/parts/${id}/soft-jaws?setup=${setupId}`);

    await db.jaw.deleteMany({ where: { setupId } });
    for (const geom of [generated.left!, generated.right!]) {
      await db.jaw.create({
        data: {
          setupId,
          deviceId: freshDevice.id,
          blankId: freshBlank.id,
          side: geom.side,
          stepDepth: geom.stepDepth,
          stepHeight: geom.stepHeight,
          seatWidth: geom.seatWidth,
          seatDepth: geom.seatDepth,
          seatCornerRadius: geom.seatCornerRadius,
          stopLocation: geom.stopLocation,
          reliefRadius: geom.reliefRadius,
          clampingDirection: req.clampingDirection,
          processJson: JSON.stringify({ process: generated.process, operations: generated.jawOperations }),
        },
      });
    }

    // The jaws change the grip, so the setup's grip depth moves with them.
    await db.setup.update({ where: { id: setupId }, data: { gripDepth: generated.achievedGrip } });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "Setup",
      entityId: setupId,
      action: "GENERATE",
      actorType: "SYSTEM",
      field: "gripDepth",
      oldValue: String(freshSetup.gripDepth ?? ""),
      newValue: String(generated.achievedGrip),
      reason: "Soft jaws generated",
    });

    redirect(`/parts/${id}/soft-jaws?setup=${setupId}&grip=${grip}`);
  }

  const existingJaws = setup.jaws;

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Soft jaws</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub={`Generating for ${setup.name}. The jaw seat is what turns a marginal second-operation grip into a repeatable one — and it is the single most common thing a job shop re-does by hand for every new part.`}>
            Soft jaw generator
          </SectionHeading>

          {assessment && assessment.level === "HIGH_RISK" && (
            <Notice tone="risk" title="Current grip is high risk">
              {assessment.factors.find((f) => f.id === "grip-depth")?.reason}
            </Notice>
          )}

          <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
            <Panel title="Inputs">
              <form action={saveJaws} className="space-y-4">
                <input type="hidden" name="setupId" value={setup.id} />
                <Field label="Setup">
                  <p className="font-mono text-[12px] text-platinum">{setup.name}</p>
                </Field>
                <Field label="Vise">
                  <p className="font-mono text-[12px] text-platinum">{device.description}</p>
                  <p className="tech-label mt-0.5">
                    {device.jawWidth}″ jaw · {device.maxOpening}″ opening
                  </p>
                </Field>
                <Field label="Jaw blank">
                  <p className="font-mono text-[12px] text-platinum">
                    {blank.width}″ × {blank.height}″ × {blank.thickness}″
                  </p>
                  <p className="tech-label mt-0.5">{blank.material.replace(/_/g, " ").toLowerCase()}</p>
                </Field>
                <Field label="Desired grip (in)" hint="Depth of the machined step the part sits on.">
                  <input name="grip" type="number" step="0.005" defaultValue={request.desiredGrip} className={inputClass} />
                </Field>
                <Field label="Jaw allowance (in)" hint="Material left around the part profile, per side.">
                  <input name="allowance" type="number" step="0.005" defaultValue={request.jawAllowance} className={inputClass} />
                </Field>
                <Field label="Clearance (in)" hint="Gap below the part so it seats on the step, not the pocket floor.">
                  <input name="clearance" type="number" step="0.005" defaultValue={request.clearance} className={inputClass} />
                </Field>
                <Field label="Clamping direction">
                  <select name="dir" defaultValue={request.clampingDirection} className={inputClass}>
                    <option value="X">X — jaws close across X</option>
                    <option value="Y">Y — jaws close across Y</option>
                  </select>
                </Field>
                <label className="flex items-center gap-2 text-[12px] text-platinum-dim">
                  <input type="checkbox" name="stop" defaultChecked={request.includeStop} className="accent-[color:var(--c-blue)]" />
                  Machine a fixed stop for repeatability
                </label>
                <Button type="submit" variant="primary" className="w-full">
                  Generate & save jaws
                </Button>
              </form>
            </Panel>

            <div className="space-y-6">
              {result.errors.length > 0 && (
                <Notice tone="risk" title="Jaws cannot be generated">
                  <ul className="mt-1 space-y-0.5">
                    {result.errors.map((e) => (
                      <li key={e}>— {e}</li>
                    ))}
                  </ul>
                </Notice>
              )}

              {result.warnings.length > 0 && (
                <Notice tone="review" title="Warnings">
                  <ul className="mt-1 space-y-0.5">
                    {result.warnings.map((w) => (
                      <li key={w}>— {w}</li>
                    ))}
                  </ul>
                </Notice>
              )}

              {result.ok && result.left && result.right && (
                <>
                  <div className="grid gap-px bg-line sm:grid-cols-2">
                    {[result.left, result.right].map((j) => (
                      <div key={j.side} className="bg-surface p-4">
                        <div className="mb-2 flex items-center justify-between">
                          <span className="tech-label text-platinum-dim">{j.side} jaw</span>
                          <StatusChip tone="precision">Generated</StatusChip>
                        </div>
                        <DataRow label="Blank" value={`${j.blankWidth}″ × ${j.blankHeight}″ × ${j.blankThickness}″`} />
                        <DataRow label="Step depth" value={`${j.stepDepth.toFixed(3)}″`} />
                        <DataRow label="Step height" value={`${j.stepHeight.toFixed(3)}″`} />
                        <DataRow label="Seat width" value={`${j.seatWidth.toFixed(3)}″`} />
                        <DataRow label="Seat depth" value={`${j.seatDepth.toFixed(3)}″`} />
                        <DataRow label="Corner relief" value={`R${j.reliefRadius.toFixed(3)}`} />
                        <DataRow label="Stop" value={j.stopLocation !== null ? `${j.stopLocation.toFixed(3)}″` : "None"} />
                        <a
                          href={`/api/parts/${id}/soft-jaws/dxf?side=${j.side}&setup=${setup.id}&grip=${request.desiredGrip}&allowance=${request.jawAllowance}&clearance=${request.clearance}&stop=${request.includeStop ? "1" : "0"}&dir=${request.clampingDirection}`}
                          download
                          className="mt-3 block border border-precision/50 px-2.5 py-1.5 text-center text-[10px] font-semibold uppercase tracking-[0.14em] text-precision-dim hover:bg-precision/10"
                        >
                          Download DXF — {j.side.toLowerCase()} jaw
                        </a>
                        <p className="mt-1.5 text-[10.5px] leading-relaxed text-muted">
                          Front and plan views, real arcs, inches. Development drawing — verify before machining; bolt
                          holes use the blank&apos;s existing pattern.
                        </p>
                      </div>
                    ))}
                  </div>

                  <Panel title="Machine jaws" meta={<span className="tech-label">Process</span>}>
                    <ol className="space-y-2.5">
                      {result.process.map((s) => (
                        <li key={s.index} className="flex gap-3">
                          <span className="font-mono text-[11px] text-precision">
                            {String(s.index).padStart(2, "0")}
                          </span>
                          <span>
                            <span className="block font-mono text-[12px] text-platinum">{s.title}</span>
                            <span className="block text-[12px] leading-relaxed text-muted">{s.detail}</span>
                          </span>
                        </li>
                      ))}
                    </ol>
                  </Panel>

                  <Panel title="Jaw machining operations" dense>
                    <table className="w-full">
                      <tbody>
                        {result.jawOperations.map((o, i) => (
                          <tr key={i} className="border-b border-line/60 last:border-0">
                            <td className="px-4 py-2 font-mono text-[12px] text-platinum">{o.operation}</td>
                            <td className="px-4 py-2 font-mono text-[11.5px] text-platinum-dim">{o.tool}</td>
                            <td className="px-4 py-2 text-[11.5px] text-muted">{o.note}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </Panel>

                  {existingJaws.length > 0 && (
                    <Notice tone="pass" title={`${existingJaws.length} jaws saved to this setup`}>
                      The setup&apos;s grip depth has been updated to {result.achievedGrip.toFixed(3)}″, which
                      re-runs the workholding assessment on the part workspace.
                    </Notice>
                  )}

                  <Notice tone="review" title="Geometry is conceptual in this phase">
                    The seat is generated as a rectangular pocket with corner relief, not as an offset of the part
                    profile. For a part with a non-rectangular footprint, treat this as the setup plan and cut the
                    profile from the part model.
                  </Notice>
                </>
              )}
            </div>
          </div>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

import Link from "next/link";
import { redirect } from "next/navigation";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { getMetrology } from "@/lib/data";
import { METROLOGY_LABELS, isScanningInstrument } from "@/lib/domain/shop";
import { TopBar } from "@/components/nav";
import { PhotoSetUploader } from "@/components/reverse/photo-set";
import { ScanImport } from "@/components/reverse/scan-import";
import { storageIsEphemeral } from "@/lib/storage";
import { AxisTriad, Button, EmptyState, Field, LinkButton, Notice, Panel, SectionHeading, StatusChip, Table, Td, inputClass } from "@/components/ui";

/**
 * REVERSE ENGINEERING
 *
 * The flagship workflow. Everything here is built on one rule: CANVAS never
 * claims dimensional reconstruction from an uncalibrated photograph. Photos
 * organise and locate; measurements dimension. The interview between the two
 * is where the product's value actually is.
 */

export default async function ReverseEngineerPage() {
  const user = await requireUser();
  const [sessions, devices] = await Promise.all([
    db.measurementSession.findMany({
      where: { partRevision: { part: { organizationId: user.organizationId } }, mode: "REVERSE_ENGINEER" },
      orderBy: { startedAt: "desc" },
      include: { partRevision: { include: { part: true } }, _count: { select: { measurements: true } } },
      take: 20,
    }),
    getMetrology(user.organizationId),
  ]);

  // A scan's uncertainty is the scanner's. Only instruments that actually
  // produce a mesh can be attributed one — from the one list, so the picker
  // and the route that validates against it cannot disagree.
  const scanners = devices
    .filter((d) => isScanningInstrument(d.deviceType))
    .map((d) => ({ id: d.id, description: d.description, uncertainty: d.uncertainty, calibrated: d.calibrated }));

  async function startSession(formData: FormData) {
    "use server";
    const currentUser = await requireWrite();
    const name = String(formData.get("name") || "Untitled component");

    // A reverse engineering session always creates a part to hang the
    // reconstructed model on — measurements without a model are just numbers.
    const part = await db.part.create({
      data: {
        organizationId: currentUser.organizationId,
        name,
        description: "Reconstructed from a physical component.",
        sharing: "PRIVATE",
        revisions: {
          create: {
            revision: "A",
            status: "DRAFT",
            units: "IN",
            intentJson: JSON.stringify({
              partName: { value: name, source: "USER", confidence: "VERIFIED", confirmedByUser: true },
              unknowns: ["Reconstructed from measurement — every dimension requires confirmation"],
              confidence: 0.1,
            }),
            responsibility: { create: {} },
          },
        },
      },
      include: { revisions: true },
    });

    const session = await db.measurementSession.create({
      data: {
        partRevisionId: part.revisions[0].id,
        name: `Reverse engineering — ${name}`,
        mode: "REVERSE_ENGINEER",
        operator: currentUser.name,
        status: "IN_PROGRESS",
      },
    });

    redirect(`/reverse-engineer/${session.id}`);
  }

  return (
    <>
      <TopBar>
        <span className="tech-label">Reverse engineer</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto">
        <section className="relative border-b border-line px-5 py-10 sm:px-8 sm:py-12">
          <AxisTriad className="absolute right-8 top-8 opacity-50" />
          <div className="mx-auto max-w-3xl">
            <h1 className="mb-2 text-[24px] font-light tracking-[0.1em] text-white">HAVE THE PART. NEED ANOTHER ONE?</h1>
            <p className="mb-7 max-w-xl text-[13px] leading-relaxed text-muted">
              Upload photographs and CANVAS will guide you through reconstructing the component — asking for the minimum
              set of measurements that constrains the model, using the instruments you actually own.
            </p>

            <form action={startSession} className="flex flex-wrap items-end gap-3">
              <div className="w-72">
                <Field label="What is the component?">
                  <input name="name" required placeholder="e.g. Pump bearing housing" className={inputClass} />
                </Field>
              </div>
              <Button type="submit" variant="primary">
                Start guided measurement
              </Button>
            </form>

            <div className="mt-4 flex flex-wrap gap-2">
              <StatusChip tone="neutral">Upload photos</StatusChip>
              <StatusChip tone="neutral">Guided measurement</StatusChip>
              <StatusChip tone="neutral">Import scan</StatusChip>
            </div>
          </div>
        </section>

        <div className="mx-auto max-w-4xl space-y-6 p-5 sm:p-8">
          {storageIsEphemeral && (
            <Notice tone="risk" title="Uploads on this deployment are temporary">
              This instance has no persistent disk, so photographs are held only for the life of the
              server instance and will disappear. Measurements, parts and every other record are
              stored in the database and are unaffected. Configure object storage for durable uploads
              — see docs/DEPLOYMENT.md.
            </Notice>
          )}

          <Notice tone="review" title="What a photograph can and cannot do">
            An uncalibrated photograph establishes what features exist, roughly where they are, and what to measure
            next. It does not establish dimensions. CANVAS will not report a diameter it derived from pixels, with or
            without a scale reference in frame — a ruler in the photo bounds the error, it does not eliminate the
            perspective, lens and placement error underneath it.
          </Notice>

          <Panel
            title="Import a 3D scan"
            meta={<span className="tech-label">Measured, by a named instrument</span>}
          >
            <p className="mb-3 text-[12.5px] leading-relaxed text-muted">
              A scan is a measurement, not a drawing: it records one worn example to the accuracy of the scanner that
              read it. CANVAS attaches that instrument&apos;s uncertainty to every dimension and rules on none of them
              — the readings arrive PENDING in the same flow as anything measured at the bench.
            </p>
            <ScanImport scanners={scanners} />
          </Panel>

          <Panel title="Your metrology" meta={<span className="tech-label">{devices.length} instruments</span>}>
            {devices.length === 0 ? (
              <EmptyState
                title="No inspection equipment recorded"
                body="Guided measurement designs its instructions around what you own. Without a metrology profile, CANVAS cannot tell you which instrument to reach for or how much to trust the result."
                action={{ label: "Add instruments", href: "/metrology" }}
              />
            ) : (
              <div className="flex flex-wrap gap-2">
                {devices.map((d) => (
                  <span key={d.id} className="border border-line px-2 py-1 font-mono text-[11px] text-platinum-dim">
                    {METROLOGY_LABELS[d.deviceType]}
                    <span className="ml-1.5 text-precision">±{d.uncertainty.toFixed(4)}″</span>
                  </span>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Sessions" dense>
            {sessions.length === 0 ? (
              <div className="p-4">
                <p className="text-[12px] text-muted">No reverse engineering sessions yet.</p>
              </div>
            ) : (
              <Table head={["Component", "Session", "Measurements", "Status", "Started"]}>
                {sessions.map((s) => (
                  <tr key={s.id} className="hover:bg-raised">
                    <Td>
                      <Link href={`/reverse-engineer/${s.id}`} className="text-platinum hover:text-white">
                        {s.partRevision.part.name}
                      </Link>
                    </Td>
                    <Td muted>{s.name}</Td>
                    <Td>{s._count.measurements}</Td>
                    <Td>
                      <StatusChip tone={s.status === "COMPLETE" ? "pass" : "precision"}>{s.status}</StatusChip>
                    </Td>
                    <Td muted>{s.startedAt.toISOString().slice(0, 10)}</Td>
                  </tr>
                ))}
              </Table>
            )}
          </Panel>

          <Panel title="Recommended photo set">
            <p className="mb-4 max-w-2xl text-[12.5px] leading-relaxed text-muted">
              Six orthogonal views plus an isometric give CANVAS enough to enumerate features and plan the measurement
              order. Add close-ups of anything with a functional surface — bearing seats, seal grooves, threads.
            </p>
            <PhotoSetUploader />
          </Panel>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

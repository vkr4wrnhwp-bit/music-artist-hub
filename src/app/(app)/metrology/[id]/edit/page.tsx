import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { Button, Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { InstrumentGlyph } from "@/components/workspace/instrument-glyph";
import { instrumentSections } from "../../instrument-fields";
import { updateInstrument, deleteInstrument } from "../../actions";

export default async function EditInstrumentPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ problem?: string }>;
}) {
  const { id } = await props.params;
  const { problem } = await props.searchParams;
  const user = await requireUser();

  const device = await db.metrologyDevice.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!device) notFound();

  const citedBy = await db.measurement.count({ where: { deviceId: id } });

  return (
    <>
      <TopBar>
        <Link href="/metrology" className="tech-label hover:text-platinum">
          Metrology
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Edit instrument</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <div className="flex items-start gap-4">
            <InstrumentGlyph deviceType={device.deviceType} className="mt-1 w-[84px] shrink-0" />
            <SectionHeading sub={device.description}>Edit instrument</SectionHeading>
          </div>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          {citedBy > 0 && (
            <Notice tone="review" title={`Cited by ${citedBy} recorded measurement${citedBy === 1 ? "" : "s"}`}>
              Changing the uncertainty here changes what those readings can verify. It does not re-open a closed
              inspection or alter a recorded value — but the capability verdicts computed against this instrument will
              be recomputed the next time they are read, and a tolerance that was verifiable may stop being so.
            </Notice>
          )}

          <ShopForm
            action={updateInstrument}
            sections={instrumentSections(device)}
            submitLabel="Save changes"
            cancelHref="/metrology"
          >
            <input type="hidden" name="id" value={device.id} />
          </ShopForm>

          <form action={deleteInstrument} className="border border-line border-l-2 border-l-risk bg-raised px-4 py-3">
            <input type="hidden" name="id" value={device.id} />
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">Remove instrument</p>
            <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
              {citedBy > 0
                ? `${citedBy} recorded measurement${citedBy === 1 ? "" : "s"} cite this instrument. Deleting it would leave ${
                    citedBy === 1 ? "that reading" : "those readings"
                  } with nothing recorded about what took ${citedBy === 1 ? "it" : "them"} — a measured value whose instrument is gone is no longer evidence. It cannot be removed.`
                : "No recorded measurement cites this instrument. The record is deleted and the removal is logged."}
            </p>
            <div className="mt-2.5">
              <Button type="submit" variant="danger" size="sm" disabled={citedBy > 0}>
                Remove instrument
              </Button>
            </div>
          </form>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { instrumentSections } from "../instrument-fields";
import { createInstrument } from "../actions";

export default async function NewInstrumentPage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  await requireUser();

  return (
    <>
      <TopBar>
        <Link href="/metrology" className="tech-label hover:text-platinum">
          Metrology
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New instrument</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="CANVAS designs measurement instructions around the instruments you actually own, and decides whether a tolerance can be verified at all by dividing its band by this instrument's uncertainty. An instrument that is not on this list cannot be recommended.">
            Add an instrument
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm
            action={createInstrument}
            sections={instrumentSections({})}
            submitLabel="Add instrument"
            cancelHref="/metrology"
          />

          <Notice tone="review" title="Uncertainty is not a formality">
            It is the denominator in every inspection-capability verdict this shop will see. A caliper entered at
            ±0.0002 will be called capable of a bore it cannot verify, and the gate that exists to catch that will
            pass. Enter the figure you can defend.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

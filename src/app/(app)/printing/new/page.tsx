import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { printerSections } from "../printer-fields";
import { createPrinter } from "../actions";

export default async function NewPrinterPage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  await requireUser();

  return (
    <>
      <TopBar>
        <Link href="/printing" className="tech-label hover:text-platinum">
          Additive
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New printer</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="The manufacturing method advisor judges printing against the machines you own. A machine that is not on this list is not considered at all.">
            Add a printer
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm action={createPrinter} sections={printerSections({})} submitLabel="Add printer" cancelHref="/printing" />

          <Notice tone="review" title="Leave the tolerance blank if nobody has measured it">
            It is the number the advisor divides a part&rsquo;s tightest tolerance band by. A machine entered at its
            datasheet figure will be called capable of a feature it cannot hold, and the check that exists to catch
            that will pass. Blank is a real answer: the advisor then says to print a coupon and measure it.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

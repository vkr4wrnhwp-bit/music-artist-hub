import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TECHNOLOGY_LABEL, type PrintTechnology } from "@/lib/engines/additive";
import { TopBar } from "@/components/nav";
import { Button, Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { printerSections } from "../../printer-fields";
import { updatePrinter, deletePrinter } from "../../actions";

export default async function EditPrinterPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ problem?: string }>;
}) {
  const { id } = await props.params;
  const { problem } = await props.searchParams;
  const user = await requireUser();

  const printer = await db.printer.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!printer) notFound();

  const others = await db.printer.count({ where: { organizationId: user.organizationId, id: { not: id } } });

  return (
    <>
      <TopBar>
        <Link href="/printing" className="tech-label hover:text-platinum">
          Additive
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Edit printer</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub={`${printer.manufacturer} ${printer.model} · ${TECHNOLOGY_LABEL[printer.technology as PrintTechnology] ?? printer.technology}`}>
            Edit printer
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <Notice tone="review" title="Changing the tolerance changes every additive verdict">
            The advisor divides each part&rsquo;s tightest tolerance band by this figure. Loosening it will move parts
            from printable to not, and tightening it will do the opposite — on parts nobody has looked at since. Enter
            what a coupon measured, not what would be convenient.
          </Notice>

          <ShopForm action={updatePrinter} sections={printerSections(printer)} submitLabel="Save changes" cancelHref="/printing">
            <input type="hidden" name="id" value={printer.id} />
          </ShopForm>

          <form action={deletePrinter} className="border border-line border-l-2 border-l-risk bg-raised px-4 py-3">
            <input type="hidden" name="id" value={printer.id} />
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">Remove printer</p>
            <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
              {others === 0
                ? "This is the only printer on file. Removing it means the advisor stops assessing additive entirely and says there is no machine to judge against — it does not mean printing is unsuitable."
                : `Additive verdicts are recomputed from the ${others} remaining printer${others === 1 ? "" : "s"} the next time they are read. Nothing recorded against this machine is rewritten.`}
            </p>
            <div className="mt-2.5">
              <Button type="submit" size="sm">
                Remove printer
              </Button>
            </div>
          </form>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

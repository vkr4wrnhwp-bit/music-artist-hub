import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TECHNOLOGY_LABEL, type PrintTechnology } from "@/lib/engines/additive";
import { TopBar } from "@/components/nav";
import { Button, Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { printMaterialSections } from "../../../material-fields";
import { updatePrintMaterial, deletePrintMaterial } from "../../../actions";

export default async function EditPrintMaterialPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ problem?: string }>;
}) {
  const { id } = await props.params;
  const { problem } = await props.searchParams;
  const user = await requireUser();

  const material = await db.printMaterial.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!material) notFound();

  const retained =
    material.tensileXY != null && material.tensileZ != null ? material.tensileZ / material.tensileXY : null;

  return (
    <>
      <TopBar>
        <Link href="/printing" className="tech-label hover:text-platinum">
          Additive
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Edit material</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub={`${material.name} · ${TECHNOLOGY_LABEL[material.technology as PrintTechnology] ?? material.technology}`}>
            Edit print material
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          {retained != null && (
            <Notice tone={retained >= 0.7 ? "review" : "risk"} title={`Keeps ${(retained * 100).toFixed(0)}% of its strength through the layers`}>
              {material.tensileZ!.toFixed(0)} psi through Z against {material.tensileXY!.toFixed(0)} psi in plane. Any
              part loaded across the layers is judged on the smaller figure.
            </Notice>
          )}

          <ShopForm
            action={updatePrintMaterial}
            sections={printMaterialSections(material)}
            submitLabel="Save changes"
            cancelHref="/printing"
          >
            <input type="hidden" name="id" value={material.id} />
          </ShopForm>

          <form action={deletePrintMaterial} className="border border-line border-l-2 border-l-risk bg-raised px-4 py-3">
            <input type="hidden" name="id" value={material.id} />
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">Remove material</p>
            <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
              Additive verdicts are recomputed without it. A part judged against this material will be judged against
              whatever else runs on the same technology, or reported as having nothing to judge against.
            </p>
            <div className="mt-2.5">
              <Button type="submit" size="sm">
                Remove material
              </Button>
            </div>
          </form>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { Button, Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { materialSections } from "../../material-fields";
import { updateMaterial, deleteMaterial } from "../../actions";

export default async function EditMaterialPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ problem?: string }>;
}) {
  const { id } = await props.params;
  const { problem } = await props.searchParams;
  const user = await requireUser();

  const material = await db.material.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!material) notFound();

  const observations = await db.shopKnowledge.count({ where: { materialId: id } });

  return (
    <>
      <TopBar>
        <Link href="/materials" className="tech-label hover:text-platinum">
          Materials
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">{material.name}</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub={`${material.name} · ${material.condition}`}>Edit material</SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          {observations > 0 && (
            <Notice tone="review" title={`${observations} shop knowledge entr${observations === 1 ? "y" : "ies"} recorded against this material`}>
              Those observations stay scoped to this shop, this machine and this tool. Editing the material here does
              not rewrite them, and nothing recorded there is promoted into a published engineering fact.
            </Notice>
          )}

          <ShopForm
            action={updateMaterial}
            sections={materialSections(material)}
            submitLabel="Save changes"
            cancelHref="/materials"
          >
            <input type="hidden" name="id" value={material.id} />
          </ShopForm>

          <form action={deleteMaterial} className="border border-line border-l-2 border-l-risk bg-raised px-4 py-3">
            <input type="hidden" name="id" value={material.id} />
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">Remove material</p>
            <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
              {observations > 0
                ? `${observations} shop knowledge entr${observations === 1 ? "y was" : "ies were"} recorded against this material. Removing it would leave ${
                    observations === 1 ? "that observation" : "those observations"
                  } with no subject — a note saying a material runs hot with nothing to say which material. It cannot be removed.`
                : "Nothing references this material. The record is deleted and the removal is logged."}
            </p>
            <div className="mt-2.5">
              <Button type="submit" variant="danger" size="sm" disabled={observations > 0}>
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

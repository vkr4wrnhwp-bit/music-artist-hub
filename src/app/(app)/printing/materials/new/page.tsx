import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { printMaterialSections } from "../../material-fields";
import { createPrintMaterial } from "../../actions";

export default async function NewPrintMaterialPage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  await requireUser();

  return (
    <>
      <TopBar>
        <Link href="/printing" className="tech-label hover:text-platinum">
          Additive
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New material</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="What the part is made of decides whether it survives being loaded. Only machines of the same technology are judged against a material.">
            Add a print material
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm
            action={createPrintMaterial}
            sections={printMaterialSections({})}
            submitLabel="Add material"
            cancelHref="/printing"
          />

          <Notice tone="review" title="The through-layer figure is the one that matters">
            A printed part is continuous within a layer and bonded between them, so a part loaded across the layers is
            a different part from the one the in-plane number describes. Leaving it blank is better than copying the
            in-plane figure — the advisor reports the gap, and assuming the two are equal is the assumption that breaks
            a printed part.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

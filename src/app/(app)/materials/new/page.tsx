import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { materialSections } from "../material-fields";
import { createMaterial } from "../actions";

export default async function NewMaterialPage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  await requireUser();

  return (
    <>
      <TopBar>
        <Link href="/materials" className="tech-label hover:text-platinum">
          Materials
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New material</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="Condition matters as much as alloy. 6061-T6 and 6061-O are the same alloy and do not cut, hold or load the same way, so the condition is a field rather than part of the name.">
            Add a material
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm
            action={createMaterial}
            sections={materialSections({})}
            submitLabel="Add material"
            cancelHref="/materials"
          />
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

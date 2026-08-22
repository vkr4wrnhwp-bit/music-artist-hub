import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { deviceSections } from "../device-fields";
import { createDevice } from "../actions";

export default async function NewWorkholdingPage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  await requireUser();

  return (
    <>
      <TopBar>
        <Link href="/workholding" className="tech-label hover:text-platinum">
          Workholding
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New device</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="Jaw geometry sets how much of the part can be gripped and how much has to stand proud of the jaws. Both feed the holding margin, and neither can be inferred from the part.">
            Add a workholding device
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm
            action={createDevice}
            sections={deviceSections({})}
            submitLabel="Add device"
            cancelHref="/workholding"
          />
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { machineSections } from "../machine-fields";
import { createMachine } from "../machine-actions";

export default async function NewMachinePage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  await requireUser();

  return (
    <>
      <TopBar>
        <Link href="/machines" className="tech-label hover:text-platinum">
          Machines
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New machine</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="Travels, spindle and changer limits are what the machine envelope gate is checked against. A machine recorded without them cannot fail that gate, which means it cannot pass it honestly either.">
            Add a machine
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm
            action={createMachine}
            sections={machineSections({})}
            submitLabel="Add machine"
            cancelHref="/machines"
          />

          <Notice tone="review" title="Posts are development posts">
            No post processor in CANVAS has been certified against a physical machine. Whichever you pick, output is
            labelled as development and NC export stays behind the readiness gates. Prove any program on the machine
            before you trust it.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { Notice, SectionHeading } from "@/components/ui";
import { ShopForm } from "@/components/shop-form";
import { toolSections } from "../tool-fields";
import { createTool } from "../actions";
import Link from "next/link";

export default async function NewToolPage(props: { searchParams: Promise<{ problem?: string }> }) {
  const { problem } = await props.searchParams;
  const user = await requireUser();
  const holders = await db.toolHolder.findMany({ orderBy: { taper: "asc" } });
  void user;

  return (
    <>
      <TopBar>
        <Link href="/tools" className="tech-label hover:text-platinum">
          Tool crib
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">New tool</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="A tool that is not in the crib does not exist to the planner. What you record here decides which features CANVAS will call machinable, what feed and speed it will propose, and which depths it will call reachable.">
            Add a tool
          </SectionHeading>

          {problem && (
            <Notice tone="risk" title="Not saved">
              {problem}
            </Notice>
          )}

          <ShopForm action={createTool} sections={toolSections({}, holders)} submitLabel="Add to crib" cancelHref="/tools" />

          <Notice tone="review" title="Blank is not zero">
            Optional numbers left blank are stored as not recorded, and the engines that need them will say so by name.
            They are never filled in with a plausible default — a guessed stickout produces a reach check computed
            against a fiction that looks like a measurement.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

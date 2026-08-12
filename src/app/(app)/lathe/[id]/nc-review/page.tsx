import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { LatheNcReview } from "@/components/turn/nc-review";
import { DevLabel, SectionHeading } from "@/components/ui";

/** Run It Past CANVAS — lathe edition. Review-only analysis of 2-axis NC. */
export default async function LatheNcReviewPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const part = await db.part.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!part) notFound();

  return (
    <>
      <TopBar>
        <Link href="/lathe" className="tech-label hover:text-platinum">Turning</Link>
        <span className="text-muted">/</span>
        <Link href={`/lathe/${id}`} className="tech-label hover:text-platinum">{part.name}</Link>
        <span className="text-muted">/</span>
        <span className="tech-label">NC review</span>
        <DevLabel>Analysis only</DevLabel>
      </TopBar>
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-5xl space-y-5">
          <SectionHeading sub="Paste a 2-axis lathe program and CANVAS reads what it honestly can: motion, tool calls, CSS regions, the unclamped-G96 hazard, fixed-RPM-across-changing-OD review, and an ESTIMATED cycle with its assumptions stated. Canned cycles, threading cycles, macros and nose-radius compensation are refused by line, never silently assumed safe.">
            Run it past CANVAS — lathe
          </SectionHeading>
          <LatheNcReview partId={id} />
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

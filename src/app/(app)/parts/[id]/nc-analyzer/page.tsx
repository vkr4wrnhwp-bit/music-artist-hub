import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { loadRevision } from "@/lib/data";
import { GuideCard } from "@/components/guide/guide-card";
import type { GuideContext } from "@/lib/guide/engine";
import { TopBar } from "@/components/nav";
import { DevLabel, Notice, SectionHeading } from "@/components/ui";
import { NcAnalyzer } from "@/components/nc-analyzer";

/**
 * NC ANALYZER — load-aware optimizer, Phases 4A/4B.
 *
 * Upload an existing program; CANVAS parses it, backplots it, breaks down
 * cycle time and finds replay-proven air cutting against this part's stock
 * and tools. Analysis only: proposals, load maps and optimized output are
 * later phases and nothing on this screen pretends otherwise.
 */

export default async function NcAnalyzerPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) notFound();

  // Guide snapshot: database facts only — stored uploads and stored
  // optimized revisions. The card clears nothing; the gates hold their own.
  const [uploads, optimized, machines] = await Promise.all([
    db.nCProgram.count({ where: { partRevisionId: revision.revisionId, origin: "UPLOADED" } }),
    db.nCProgram.count({ where: { partRevisionId: revision.revisionId, origin: "OPTIMIZED" } }),
    db.machine.count({ where: { organizationId: user.organizationId } }),
  ]);
  const guideCtx: GuideContext = {
    partId: id,
    hasStock: Boolean(revision.stock),
    hasMachine: machines > 0,
    hasMaterial: Boolean(revision.intent.material.value),
    featureCount: revision.features.length,
    pendingProposals: 0,
    setupCount: 0,
    workholdingAssessed: false,
    toolpathCount: 0,
    simulationRecorded: false,
    approvalExists: false,
    ncProgramExists: optimized > 0,
    blockingGates: [],
    nextAction: null,
    training: false,
    nca: { uploads, optimized },
  };

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">NC analyzer</span>
        <DevLabel>Phase 4A/4B — analysis only</DevLabel>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="Upload an existing program. CANVAS parses it, backplots the motion, breaks down cycle time, and proves air cutting by replaying the motion against this part's stock and the shop's tool table. Findings are analysis, not changes — optimization proposals are a later phase, and this program is never modified or exported from here.">
            NC analyzer
          </SectionHeading>

          <Notice tone="review" title="Analysis, not verification">
            Times are distance over feed with no acceleration model, and the replay assumes the program's Z0 is the
            stock top with XY zero at the stock centre. A finding is a place to look, not a change to make.
          </Notice>

          <NcAnalyzer partId={id} />
        </div>
      </main>
      <GuideCard ctx={guideCtx} flowId="RUN_IT_PAST" />
    </>
  );
}

export const dynamic = "force-dynamic";

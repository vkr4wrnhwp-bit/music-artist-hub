import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { buildPackage } from "@/lib/package";
import { db } from "@/lib/db";
import { parseNC } from "@/lib/nc/parse";
import { analyzeNC } from "@/lib/nc/analyze";
import { reviewPackage, type Severity } from "@/lib/engines/review";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { DataRow, LinkButton, Notice, Panel, SectionHeading, StatusChip, type Tone } from "@/components/ui";
import { findingShowMeHref } from "@/lib/guide/show-me";
import { clearedFindings, syncFindings } from "@/lib/review-findings-store";
import { FindingResponse } from "@/components/review/finding-response";
import { recordFindingResolution } from "./finding-actions";

/**
 * RUN IT PAST CANVAS
 *
 * A shop that already trusts its CAM is not going to abandon it, and asking
 * them to is how this product gets ignored. What they will do is run a job
 * past a second opinion before pressing Cycle Start — the same way they would
 * ask the other machinist to look at a setup.
 *
 * The page is careful about one thing above all: a clean review is not a
 * safety claim. It means the checks CANVAS knows how to make found nothing,
 * and what CANVAS cannot check is listed with equal prominence.
 */

const TONE: Record<Severity, Tone> = { HIGH: "risk", MEDIUM: "review", LOW: "unknown" };

export default async function ReviewPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  const movesByOperation: Record<string, typeof pkg.toolpaths[number]["moves"]> = {};
  for (const tp of pkg.toolpaths) movesByOperation[tp.operationId] = tp.moves;

  /*
   * The shop's own program, if they have handed one over. This is the only
   * piece of the Phase 3B job-package import that actually exists: NC bytes
   * arrive through the analyzer and are stored immutably with their digest.
   *
   * The most recent upload is the one reviewed, because that is the one a
   * machinist just put in front of CANVAS. Reviewing an older upload silently
   * would answer a question nobody asked.
   */
  const uploaded = await db.nCProgram.findFirst({
    where: { partRevisionId: pkg.revision.revisionId, origin: "UPLOADED" },
    orderBy: { createdAt: "desc" },
  });

  const primarySetup = pkg.setups[0] ?? null;
  const toolDiameters: Record<number, number> = {};
  const toolGeometry: Record<number, { description: string; fluteLength: number; stickout: number; source: "CRIB" }> = {};
  for (const t of pkg.tools) {
    toolDiameters[t.toolNumber] = t.diameter;
    toolGeometry[t.toolNumber] = {
      description: t.description,
      fluteLength: t.fluteLength,
      stickout: t.stickout,
      source: "CRIB",
    };
  }

  const uploadedProgram = uploaded
    ? {
        filename: uploaded.sourceFilename ?? `Program ${uploaded.programNumber}`,
        // The stored digest is of the original bytes. Where an older row
        // predates digesting, the row id stands in — it is still stable and
        // still distinguishes one program from another.
        digest: uploaded.sourceDigest ?? uploaded.id,
        analysis: analyzeNC(parseNC(uploaded.code), {
          stock: pkg.revision.stock ? { x: pkg.revision.stock.x, y: pkg.revision.stock.y, z: pkg.revision.stock.z } : null,
          toolDiameters,
          toolGeometry,
          workholding: primarySetup
            ? { jawAxis: primarySetup.jawAxis, hasPositiveStop: primarySetup.hasPositiveStop, deviceDescription: null }
            : undefined,
          rapidRate: pkg.primaryMachine?.maxRapid ?? null,
          axisAccel: pkg.primaryMachine?.axisAccel ?? null,
        }),
      }
    : null;

  const review = reviewPackage({
    setups: pkg.setups.map((s) => ({
      id: s.id,
      name: s.name,
      sequence: s.sequence,
      gripDepth: s.gripDepth,
      stockProjection: s.stockProjection,
      jawAxis: s.jawAxis,
      operations: s.operations.map((o) => ({
        id: o.id,
        label: o.label,
        toolId: o.toolId,
        finalZ: o.finalZ,
        type: o.type,
      })),
    })),
    workholdingBySetup: pkg.workholdingBySetup,
    device: pkg.primaryWorkholding,
    machine: pkg.primaryMachine,
    tools: pkg.tools,
    movesByOperation,
    capability: pkg.readiness.capability,
    stockZ: pkg.revision.stock?.z ?? null,
    stockX: pkg.revision.stock?.x ?? null,
    stockY: pkg.revision.stock?.y ?? null,
    uploadedProgram,
  });

  /*
   * The findings are computed above and are the only thing displayed. This
   * reconciles them against the record so each one can carry its history and
   * whatever a machinist concluded about it — it never serves a stored
   * finding in place of a computed one.
   */
  const records = await syncFindings(user.organizationId, pkg.revision.revisionId, review.findings);
  const cleared = await clearedFindings(pkg.revision.revisionId);

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Run it past CANVAS</span>
        <PartStatusChip readiness={pkg.readiness} />
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="A second opinion before Cycle Start. This does not replace your CAM and does not verify your program — it runs the checks CANVAS knows how to make against the setups, the tooling and the actual toolpath moves, and tells you what it found and what it could not look at.">
            Run it past CANVAS
          </SectionHeading>

          {/* ---------------- Headline ---------------- */}
          <Panel
            title={review.findings.length === 0 ? "Nothing found" : "Review required"}
            meta={
              review.findings.length > 0 ? (
                <span className="flex gap-2">
                  {review.highCount > 0 && <StatusChip tone="risk">{review.highCount} high</StatusChip>}
                  {review.mediumCount > 0 && <StatusChip tone="review">{review.mediumCount} medium</StatusChip>}
                  {review.lowCount > 0 && <StatusChip tone="unknown">{review.lowCount} low</StatusChip>}
                </span>
              ) : null
            }
          >
            <p className="max-w-2xl text-[14px] leading-relaxed text-platinum">{review.headline}</p>
          </Panel>

          {/* ---------------- Findings ---------------- */}
          {review.findings.map((f, i) => (
            <Panel
              key={f.key}
              title={`${String(i + 1).padStart(2, "0")} — ${f.title}`}
              meta={<StatusChip tone={TONE[f.severity]}>{f.severity}</StatusChip>}
            >
              <p className="max-w-2xl text-[13px] leading-relaxed text-platinum">{f.detail}</p>

              <p className="mt-3 max-w-2xl text-[12.5px] leading-relaxed text-muted">
                <span className="tech-label">Do this</span> {f.recommendation}
              </p>

              <div className="mt-4 grid gap-x-8 sm:grid-cols-2">
                {f.evidence.map((e) => (
                  <DataRow key={e.label} label={e.label} value={e.value} />
                ))}
              </div>

              <p className="tech-label mt-3">Method — {f.method}</p>

              {/* SHOW ME. The context each finding is best understood in is
                  carried on the finding itself, so this deep-links to the
                  right view rather than dropping the user on the workspace. */}
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <LinkButton
                  href={findingShowMeHref(id, f.location, pkg.setups[0]?.id ?? null)}
                  size="sm"
                  variant="primary"
                >
                  Show me
                </LinkButton>
                <span className="tech-label">
                  {f.location.context}
                  {f.location.point &&
                    ` · X${f.location.point.x.toFixed(2)} Y${f.location.point.y.toFixed(2)} Z${f.location.point.z.toFixed(3)}`}
                </span>
              </div>

              <FindingResponse
                record={records[f.key]}
                findingKey={f.key}
                action={recordFindingResolution.bind(null, id)}
              />
            </Panel>
          ))}

          {/* ---------------- Findings that stopped being raised ---------------- */}
          {cleared.length > 0 && (
            <Panel title="No longer raised" meta={<StatusChip tone="pass">{cleared.length}</StatusChip>}>
              <p className="mb-3 max-w-2xl text-[12.5px] leading-relaxed text-muted">
                These were raised against this revision and the checks no longer raise them. Nobody dismissed them —
                the evidence changed. They are kept so a setup that quietly went from bad to good, or was reviewed and
                then re-planned, leaves a trace.
              </p>
              <ul className="space-y-1">
                {cleared.map((c) => (
                  <li key={c.findingKey} className="text-[12.5px] leading-relaxed text-platinum-dim">
                    <span className="tech-label">{c.severity}</span> {c.title}
                    <span className="block pl-4 text-muted">
                      Raised {new Date(c.firstSeenAt).toISOString().slice(0, 10)}, last raised{" "}
                      {new Date(c.clearedAt!).toISOString().slice(0, 10)}.
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {/* ---------------- What was checked ---------------- */}
          <Panel title="What CANVAS checked">
            <ul className="space-y-1">
              {review.checksRun.map((c) => (
                <li key={c} className="flex gap-2 text-[12.5px] leading-relaxed text-platinum-dim">
                  <span className="text-pass">✓</span>
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="What CANVAS did not check">
            <p className="mb-3 max-w-2xl text-[12.5px] leading-relaxed text-muted">
              This list matters as much as the findings. A clean review means these checks found nothing — not that the
              program is safe.
            </p>
            <ul className="space-y-2">
              {review.checksSkipped.map((c) => (
                <li key={c.check} className="text-[12.5px] leading-relaxed">
                  <span className="text-review">— {c.check}</span>
                  <span className="block pl-4 text-muted">{c.reason}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Notice tone="risk" title="This is not NC verification">
            There is no stock-removal simulation and no collision engine behind this review. It cannot tell you a
            program is safe. Dry run above the part, confirm work offsets and tool length offsets at the machine, and
            treat this as a second pair of eyes rather than a sign-off.
          </Notice>

          <Notice tone="review" title="Only part of a job package can be imported">
            Phase 3B describes handing CANVAS a whole job from whatever CAM the shop already runs — STEP model, NC
            program, tool list and setup file. Two of the four arrive:{" "}
            {uploadedProgram ? (
              <>
                the NC program is uploaded ({uploadedProgram.filename}) and its reach and cut-direction findings are in
                the list above,
              </>
            ) : (
              <>an NC program can be uploaded in the analyzer and its findings then appear in the list above,</>
            )}{" "}
            and a tool list can be attached alongside it. STEP and setup files cannot: STEP needs a geometry kernel, and
            no setup-file parser exists. Nothing here re-derives operations from posted code — the toolpath, workholding
            and inspection checks still run against the package CANVAS itself holds.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

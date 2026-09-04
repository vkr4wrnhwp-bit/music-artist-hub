import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import {
  POSTS,
  defaultPostForController,
  getPost,
  ncVerificationBlockers,
  preflightPassed,
  verifyNc,
  type NcVerificationIssue,
  type PostContext,
} from "@/lib/engines/cam/post";
import { buildPreflight } from "@/lib/engines/cam/preflight";
import { POSITION_TOLERANCE, reconcilePostedProgram } from "@/lib/nc/reconcile";
import { proofState } from "@/lib/nc/proof";
import { recordProofOut } from "./actions";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { NcExportPanel } from "@/components/nc/export-panel";
import { Button, DevLabel, Dot, Field, LimitsDisclosure, Notice, Panel, SectionHeading, StatusChip, Table, Td, inputClass } from "@/components/ui";
import { frameSentence } from "@/lib/engines/cam/setup-frame";

/**
 * NC OUTPUT
 *
 * The export button is disabled until every required pre-flight item passes.
 * That is the point of the screen: the program is trivially easy to generate
 * and deliberately hard to walk away with.
 */

export default async function NcPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ post?: string; generated?: string }>;
}) {
  const { id } = await props.params;
  const { post: postParam, generated } = await props.searchParams;
  const user = await requireUser();

  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  const partRow = await db.part.findFirst({ where: { id, organizationId: user.organizationId }, select: { training: true } });
  const isTraining = partRow?.training ?? false;

  const machine = pkg.primaryMachine;
  const selectedPost = postParam
    ? getPost(postParam)
    : machine
      ? defaultPostForController(machine.controller)
      : POSTS[0];

  const existing = await db.nCProgram.findFirst({
    where: { partRevisionId: pkg.revision.revisionId },
    orderBy: { createdAt: "desc" },
  });

  /* ---------------- Pre-flight ---------------- */

  // One gate, shared with the generate action and the export mint. If the
  // gate logic exists in two places, it does not exist.
  const preflight = buildPreflight(pkg, selectedPost);

  const issues: NcVerificationIssue[] = existing?.verificationIssuesJson
    ? (JSON.parse(existing.verificationIssuesJson) as NcVerificationIssue[])
    : [];
  // NC VERIFY is a step in the chain, not a report beside it. Errors stop the
  // program leaving; the mint re-checks, because a disabled button is not a
  // gate.
  const verifyBlockers = ncVerificationBlockers(issues);

  /*
   * RECONCILIATION — does the emitted program cut the path that was approved?
   *
   * Recomputed from the stored program text on every render rather than stored
   * with the program, because it is a comparison between two things that both
   * move: regenerate the toolpath and the answer changes, and a stored verdict
   * would go on describing a program that no longer matches.
   */
  const reconciled = existing ? reconcilePostedProgram(existing.code, pkg.toolpaths) : null;
  const proof = existing
    ? proofState(existing, existing.code, machine ? `${machine.manufacturer} ${machine.model}` : null)
    : { state: "NEVER_RUN" as const, detail: "", provenAt: null, provenByName: null, provenNote: null };
  const proofAction = recordProofOut.bind(null, id);
  const canExport =
    preflightPassed(preflight) &&
    Boolean(selectedPost) &&
    Boolean(machine) &&
    verifyBlockers.length === 0 &&
    Boolean(reconciled?.verified);

  /* ---------------- Generate ---------------- */

  async function generate(formData: FormData) {
    "use server";
    const currentUser = await requireWrite();
    const fresh = await buildPackage(currentUser.organizationId, id);
    if (!fresh || !fresh.primaryMachine) notFound();

    const postId = String(formData.get("postId"));
    const post = getPost(postId);
    if (!post) redirect(`/parts/${id}/nc`);

    // The disabled button is not the gate. A server action is a POST endpoint
    // reachable regardless of rendered button state, so the gate is re-run
    // here, against a package built fresh for this request.
    const gate = buildPreflight(fresh, post);
    if (!preflightPassed(gate)) redirect(`/parts/${id}/nc?post=${post.id}`);

    const programNumber = String(formData.get("programNumber") || "1001");
    const workOffset = String(formData.get("workOffset") || "G54");

    const ctx: PostContext = {
      programNumber,
      programName: fresh.revision.partName.slice(0, 24),
      machine: fresh.primaryMachine,
      workOffset,
      units: fresh.revision.units,
      // The registers as the crib recorded them. Null is not a hole to be
      // filled here — the post decides what an unrecorded register means and
      // says so in the header. See engines/cam/offsets.ts.
      toolTable: fresh.assignedTools.map((t) => ({
        toolNumber: t.toolNumber,
        description: t.description,
        lengthOffset: t.lengthOffset ?? null,
        diameterOffset: t.diameterOffset ?? null,
        diameter: t.diameter,
      })),
      safeZ: 1,
      partName: fresh.revision.partName,
      revision: fresh.revision.revision,
      generatedAtIso: new Date().toISOString(),
      /*
       * Where zero is, per work offset, in the setups' own words.
       *
       * A part that gets flipped runs under more than one offset and the frames
       * are not the same sentence. An operator who picks up an edge under the
       * wrong reading cuts a mirrored part, and nothing in the program is wrong
       * enough for a gate to catch it — so the header carries one line each.
       */
      origins: fresh.setups
        .filter((s) => fresh.framesBySetup[s.id])
        .map((s) => ({
          workOffset: s.workOffset,
          sentence: frameSentence(fresh.framesBySetup[s.id], fresh.revision.stock).sentence,
        })),
    };

    const code = post.emit(fresh.toolpaths, ctx);
    const issues = verifyNc(code, fresh.primaryMachine);

    const program = await db.nCProgram.create({
      data: {
        partRevisionId: fresh.revision.revisionId,
        machineId: fresh.primaryMachine.id,
        postId: post.id,
        programNumber,
        workOffset,
        units: fresh.revision.units,
        code,
        certified: false,
        verificationIssuesJson: JSON.stringify(issues),
        // The gate state this program was generated under travels with it.
        preflightJson: JSON.stringify(gate),
        generatedBy: currentUser.id,
      },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "NCProgram",
      entityId: program.id,
      action: "GENERATE",
      actorType: "SYSTEM",
      reason: `Development post ${post.name}`,
      newValue: `${code.split("\n").length} lines, ${issues.length} verification issues`,
    });

    redirect(`/parts/${id}/nc?post=${post.id}&generated=1`);
  }

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">NC output</span>
        <DevLabel>Development / simulation post</DevLabel>
              <PartStatusChip readiness={pkg.readiness} />
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          {/* COMMAND CENTER HEADER — one dominant status, the rail below it.
              The gate itself is unchanged; buildPreflight rules as before. */}
          <section className="border border-line bg-surface">
            <div className="flex flex-wrap items-stretch gap-px bg-line">
              <div className="min-w-[160px] flex-1 bg-surface px-5 py-4">
                <p className="tech-label">Program</p>
                <p className="mt-1 font-mono text-[24px] font-light text-white">O{existing?.programNumber ?? "—"}</p>
              </div>
              <div className="min-w-[160px] flex-1 bg-surface px-5 py-4">
                <p className="tech-label">Status</p>
                <p className={`mt-1 font-mono text-[24px] font-light ${canExport ? "text-pass" : "text-risk"}`}>
                  {canExport ? "READY" : "NOT READY"}
                </p>
              </div>
              <div className="min-w-[160px] flex-1 bg-surface px-5 py-4">
                <p className="tech-label">Controller</p>
                <p className="mt-1 font-mono text-[15px] text-platinum">{machine?.controller.replace(/_/g, " ") ?? "—"}</p>
                <p className="tech-label mt-1">{machine ? `${machine.manufacturer} ${machine.model}` : "no machine"}</p>
              </div>
              <div className="min-w-[200px] flex-1 bg-surface px-5 py-4">
                <p className="tech-label">Post</p>
                <p className="mt-1 font-mono text-[13px] text-platinum">{selectedPost?.name ?? "—"}</p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-review">
                  Development — not certified for production
                </p>
              </div>
            </div>
            {/* Beta loop: after a real run, report what actually happened —
                program, machine and the predicted cycle travel with the link. */}
            {existing && (
              <div className="border-t border-line px-5 py-2">
                <Link
                  href={`/knowledge?report=1&program=O${existing.programNumber}&machine=${encodeURIComponent(machine ? `${machine.manufacturer} ${machine.model}` : "")}&predicted=${pkg.cycleMinutes.toFixed(2)}&material=${encodeURIComponent(pkg.revision.intent.material.value ?? "")}`}
                  className="text-[10px] font-semibold uppercase tracking-[0.14em] text-precision-dim hover:text-precision"
                >
                  Ran this program? Report the run — was CANVAS right? →
                </Link>
              </div>
            )}
            {/* Pre-flight rail: every item one chip; the first unresolved one
                becomes the dominant card below the rail. */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-line px-5 py-2.5">
              {preflight.map((p) => (
                <span key={p.id} className="flex items-center gap-1.5 font-mono text-[10.5px] uppercase tracking-[0.08em]">
                  <Dot tone={p.status === "PASS" ? "pass" : p.status === "PENDING" ? "unknown" : "risk"} />
                  <span className={p.status === "PASS" ? "text-muted" : "text-platinum"}>{p.label}</span>
                  <span className={p.status === "PASS" ? "text-pass" : p.status === "PENDING" ? "text-unknown" : "text-risk"} aria-hidden>
                    {p.status === "PASS" ? "✓" : p.status === "PENDING" ? "—" : "✕"}
                  </span>
                </span>
              ))}
            </div>
            {(() => {
              const first = preflight.find((p) => p.status !== "PASS");
              if (!first) return null;
              return (
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-risk/40 bg-risk/5 px-5 py-3">
                  <div className="min-w-0">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-risk">First unresolved — {first.label}</p>
                    <p className="mt-0.5 text-[12.5px] leading-relaxed text-platinum-dim">{first.detail}</p>
                  </div>
                  <Link
                    href={`/parts/${id}/readiness`}
                    className="shrink-0 border border-precision/60 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-precision hover:bg-precision/10"
                  >
                    Show blocker
                  </Link>
                </div>
              );
            })()}
            <div className="border-t border-line px-5 py-2">
              <LimitsDisclosure label="Why this post is not certified">
                Verify every line before running. Dry run above the part. Confirm work offsets and tool length offsets
                at the machine. CANVAS has not verified stock removal, holder clearance or fixture collisions — the
                program header carries the same warning.
              </LimitsDisclosure>
            </div>
          </section>

          {isTraining && (
            <Notice tone="review" title="Training project — no production NC export">
              This part exists to practise on. Everything works — planning, simulation, gates, program preview —
              except walking away with the program: the export mint refuses training projects server-side.
            </Notice>
          )}

          <Panel title="Generate">
            <form action={generate} className="flex flex-wrap items-end gap-4">
              <div className="w-64">
                <Field label="Post processor">
                  <select name="postId" defaultValue={selectedPost?.id} className={inputClass}>
                    {POSTS.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <div className="w-40">
                <Field label="Program number">
                  <input name="programNumber" defaultValue={existing?.programNumber ?? "1001"} className={inputClass} />
                </Field>
              </div>
              <div className="w-32">
                <Field label="Work offset">
                  <select name="workOffset" defaultValue={existing?.workOffset ?? "G54"} className={inputClass}>
                    {["G54", "G55", "G56", "G57", "G58", "G59"].map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                </Field>
              </div>
              <Button type="submit" variant="primary" disabled={!canExport}>
                Generate program
              </Button>
            </form>
            {!canExport && (
              <p className="mt-3 text-[12px] text-review">
                {verifyBlockers.length > 0
                  ? `Export is disabled: NC verification reports ${verifyBlockers.length} error${
                      verifyBlockers.length === 1 ? "" : "s"
                    } in this program. Fix the program and generate again — there is no acknowledgement that clears this.`
                  : "Export is disabled until every required pre-flight item passes. This is deliberate."}
              </p>
            )}
          </Panel>

          {existing && (
            <>
              {existing && (
                <Panel
                  title="Proven on the machine"
                  meta={
                    <StatusChip
                      tone={proof.state === "PROVEN" ? "pass" : proof.state === "STALE" ? "risk" : "review"}
                    >
                      {proof.state.replace(/_/g, " ")}
                    </StatusChip>
                  }
                >
                  <p className="mb-3 text-[12px] leading-relaxed text-platinum-dim">{proof.detail}</p>
                  <p className="mb-3 text-[11.5px] leading-relaxed text-muted">
                    Whether a program has ever cut a good part is the first thing anybody wants to know about it, and
                    it is the one thing CANVAS could not tell you. This does not clear a gate and does not block one —
                    a program that has never been run is the normal state of a new program. It records which it is,
                    and who says so. Re-posting moves it back to stale by itself: a proof is about specific bytes.
                  </p>
                  <form action={proofAction} className="flex flex-wrap items-end gap-2">
                    <label className="min-w-[260px] flex-1">
                      <span className="tech-label mb-1 block">What happened at the machine</span>
                      <input
                        name="note"
                        maxLength={240}
                        defaultValue={existing.provenNote ?? ""}
                        placeholder="first article passed, 0.0002 over on the bore, took a thou off D2"
                        className={inputClass}
                      />
                    </label>
                    <Button type="submit" size="sm">
                      {proof.state === "PROVEN" ? "Update" : "Record the run"}
                    </Button>
                  </form>
                </Panel>
              )}

              {reconciled && (
                <Panel
                  title="Program against plan"
                  meta={
                    <StatusChip tone={reconciled.verified ? "pass" : "risk"}>
                      {reconciled.verified ? "TRACES THE PLAN" : "DOES NOT MATCH"}
                    </StatusChip>
                  }
                >
                  <div className="mb-3">
                    <LimitsDisclosure label="What this proves and what it does not">
                      Every other check on this page verifies the TOOLPATH — workholding, holding margin, simulation,
                      collision, cycle time. The post sits downstream of all of them. This reads the emitted program
                      back and checks it traces the same path, within {POSITION_TOLERANCE}″, so the proofs already run
                      against the toolpath carry over to the file. It is geometry only: it says nothing about whether
                      the work offset is set, the length offsets are right or the spindle turns the right way.
                    </LimitsDisclosure>
                  </div>
                  <p className="mb-3 text-[12px] leading-relaxed text-platinum-dim">{reconciled.detail}</p>
                  {reconciled.tools.length > 0 && (
                    <Table head={["Tool", "Planned cut", "In the program", "Worst departure"]}>
                      {reconciled.tools.map((t) => (
                        <tr key={t.toolNumber} className="hover:bg-raised">
                          <Td className="font-mono text-platinum">T{t.toolNumber}</Td>
                          <Td muted>{t.plannedCutting.toFixed(2)}″</Td>
                          <Td muted>{t.postedCutting.toFixed(2)}″</Td>
                          <Td>
                            <span
                              className={
                                Number.isFinite(t.maxDeviation) && t.maxDeviation <= POSITION_TOLERANCE
                                  ? "font-mono tabular-nums text-platinum"
                                  : "font-mono tabular-nums text-risk"
                              }
                            >
                              {Number.isFinite(t.maxDeviation) ? `${t.maxDeviation.toFixed(4)}″` : "not in the program"}
                            </span>
                          </Td>
                        </tr>
                      ))}
                    </Table>
                  )}
                  {reconciled.findings.length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {reconciled.findings.map((f, i) => (
                        <li key={i} className="flex gap-3 text-[11.5px] leading-relaxed">
                          <span className={f.severity === "ERROR" ? "font-mono text-risk" : "font-mono text-review"}>
                            {f.severity}
                          </span>
                          <span className="text-platinum-dim">{f.message}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Panel>
              )}

              {issues.length > 0 && (
                <Panel title={`NC verification — ${issues.length} issues`} meta={<DevLabel>Linter, not a verifier</DevLabel>}>
                  <div className="mb-3">
                    <LimitsDisclosure label="What this pass does and does not catch">
                      This pass catches what is cheap to catch in text: travel envelope violations, speeds above the
                      spindle maximum, motion below Z0 with the spindle off, missing units. It does not verify
                      collisions or material removal.
                    </LimitsDisclosure>
                  </div>
                  <ul className="space-y-1">
                    {issues.map((iss, i) => (
                      <li key={i} className="flex gap-3 font-mono text-[11.5px]">
                        <span className={iss.severity === "ERROR" ? "text-risk" : "text-review"}>{iss.severity}</span>
                        <span className="text-muted">line {iss.line}</span>
                        <span className="text-platinum-dim">{iss.message}</span>
                      </li>
                    ))}
                  </ul>
                </Panel>
              )}

              <Panel
                title={`Program O${existing.programNumber}`}
                meta={
                  <span className="flex gap-2">
                    {existing.origin !== "GENERATED" && <StatusChip tone="review">{existing.origin}</StatusChip>}
                    <StatusChip tone="neutral">{existing.postId}</StatusChip>
                    <StatusChip tone="risk">Not certified</StatusChip>
                  </span>
                }
                dense
              >
                {existing.optimizationAuditJson && (
                  <div className="border-b border-line px-4 py-2.5">
                    <p className="instrument-label mb-1">Optimization audit</p>
                    {(() => {
                      const a = JSON.parse(existing.optimizationAuditJson!) as {
                        scope: string; preset: string; savedSeconds: number;
                        originalMinutes: number; optimizedMinutes: number;
                        applied: { lines: [number, number]; originalFeed: number; proposedFeed: number }[];
                        originalDigest: string; optimizedDigest: string;
                      };
                      return (
                        <>
                          <p className="text-[12px] leading-relaxed text-platinum-dim">
                            {a.scope}. {a.preset} preset · {a.originalMinutes.toFixed(2)} → {a.optimizedMinutes.toFixed(2)} min
                            (~{a.savedSeconds}s estimated, no acceleration model).
                          </p>
                          <ul className="mt-1 font-mono text-[11px] text-muted tabular-nums">
                            {a.applied.map((p, i) => (
                              <li key={i}>
                                L{p.lines[0]}–{p.lines[1]}: F{p.originalFeed} → F{p.proposedFeed}
                              </li>
                            ))}
                          </ul>
                          <p className="mt-1 font-mono text-[10px] text-muted">
                            src {a.originalDigest.slice(0, 12)}… → opt {a.optimizedDigest.slice(0, 12)}…
                          </p>
                        </>
                      );
                    })()}
                  </div>
                )}
                {/* The program body renders only while the gate currently
                    passes. A program generated under a passing gate does not
                    stay copy-pasteable after a tool change, a revoked
                    approval or a downgraded workholding assessment has
                    invalidated it. */}
                {canExport ? (
                  <pre className="max-h-[520px] overflow-auto bg-void px-4 py-3 font-mono text-[11.5px] leading-relaxed text-platinum-dim">
                    {existing.code}
                  </pre>
                ) : (
                  <div className="px-4 py-3">
                    <p className="text-[12px] leading-relaxed text-platinum-dim">
                      A program exists for this revision ({existing.code.split("\n").length} lines, generated{" "}
                      {existing.createdAt.toISOString().slice(0, 10)}), but the pre-flight no longer passes, so the
                      program text and export are withheld until it does. The failing items are listed above.
                    </p>
                  </div>
                )}
              </Panel>

              {canExport && !isTraining && <NcExportPanel partId={id} />}
            </>
          )}

          {generated === "1" && !existing && (
            <Notice tone="review" title="No program stored">Generation completed but nothing was persisted.</Notice>
          )}
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";

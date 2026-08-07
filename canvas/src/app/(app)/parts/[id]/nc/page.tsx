import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import { POSTS, defaultPostForController, getPost, preflightPassed, verifyNc, type PostContext, type PreflightItem } from "@/lib/engines/cam/post";
import { TopBar } from "@/components/nav";
import { Button, DevLabel, Dot, Field, Notice, Panel, SectionHeading, StatusChip, inputClass, type Tone } from "@/components/ui";

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

  const realToolpaths = pkg.toolpaths.filter((t) => !t.isPlaceholder);
  const preflight: PreflightItem[] = [
    item("machine", "Machine selected", Boolean(machine), machine ? `${machine.manufacturer} ${machine.model}` : "No machine on this setup", true),
    item("post", "Post processor selected", Boolean(selectedPost), selectedPost ? selectedPost.name : "None", true),
    item("units", "Units confirmed", pkg.revision.units === "IN" || pkg.revision.units === "MM", `Program in ${pkg.revision.units === "IN" ? "inches (G20)" : "millimetres (G21)"}`, true),
    item("stock", "Stock verified", Boolean(pkg.revision.stock), pkg.revision.stock ? `${pkg.revision.stock.x} × ${pkg.revision.stock.y} × ${pkg.revision.stock.z}` : "Stock not defined", true),
    item(
      "workholding",
      "Workholding verified",
      Object.values(pkg.workholdingBySetup).every((a) => a.level === "SAFE" || a.level === "LIKELY_SAFE"),
      workholdingSummary(pkg),
      true,
    ),
    item("tools", "Tools verified", pkg.assignedTools.length > 0, `${pkg.assignedTools.length} tools assigned`, true),
    item(
      "toollengths",
      "Tool lengths verified",
      pkg.assignedTools.every((t) => t.stickout > 0),
      "Stickout recorded for every assigned tool. Length offsets must still be set at the machine.",
      true,
    ),
    item("toolpaths", "Toolpaths generated", realToolpaths.length > 0, `${realToolpaths.length} operations with motion, ${pkg.toolpaths.length - realToolpaths.length} without an engine`, true),
    item("errors", "No toolpath errors", pkg.toolpathErrors.length === 0, pkg.toolpathErrors.length === 0 ? "All operations produced a path" : `${pkg.toolpathErrors.length} operations failed`, true),
    item(
      "criticaldims",
      "Critical dimensions reviewed",
      pkg.revision.features.filter((f) => f.critical).every((f) => Boolean(f.inspectionMethod)),
      "Every critical feature has an inspection method",
      true,
    ),
    item("simulation", "Simulation completed", pkg.simulationRun, pkg.simulationRun ? "Development visualisation run" : "Not run", true),
    item("approval", "Operator approval", pkg.approved, pkg.approved ? "Package approved" : "No approval recorded", true),
  ];

  const canExport = preflightPassed(preflight) && Boolean(selectedPost) && Boolean(machine);

  /* ---------------- Generate ---------------- */

  async function generate(formData: FormData) {
    "use server";
    const currentUser = await requireUser();
    const fresh = await buildPackage(currentUser.organizationId, id);
    if (!fresh || !fresh.primaryMachine) notFound();

    const postId = String(formData.get("postId"));
    const post = getPost(postId);
    if (!post) redirect(`/parts/${id}/nc`);

    const programNumber = String(formData.get("programNumber") || "1001");
    const workOffset = String(formData.get("workOffset") || "G54");

    const ctx: PostContext = {
      programNumber,
      programName: fresh.revision.partName.slice(0, 24),
      machine: fresh.primaryMachine,
      workOffset,
      units: fresh.revision.units,
      toolTable: fresh.assignedTools.map((t) => ({
        toolNumber: t.toolNumber,
        description: t.description,
        lengthOffset: t.toolNumber,
        diameter: t.diameter,
      })),
      safeZ: 1,
      partName: fresh.revision.partName,
      revision: fresh.revision.revision,
      generatedAtIso: new Date().toISOString(),
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

  const issues: { severity: string; line: number; message: string }[] = existing?.verificationIssuesJson
    ? JSON.parse(existing.verificationIssuesJson)
    : [];

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">NC output</span>
        <DevLabel>Development / simulation post</DevLabel>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          <SectionHeading sub="An LLM never produces machine motion in CANVAS. This program came from the deterministic toolpath engine through a modular post processor. It is a development post, it is not certified for production, and it says so in its own header.">
            NC output
          </SectionHeading>

          <Notice tone="risk" title="Not certified for production">
            Verify every line before running. Dry run above the part. Confirm work offsets and tool length offsets at
            the machine. CANVAS has not verified stock removal, holder clearance or fixture collisions.
          </Notice>

          <Panel title="Pre-flight check" dense>
            <ul>
              {preflight.map((p) => (
                <li key={p.id} className="flex items-start justify-between gap-4 border-b border-line/60 px-4 py-2.5 last:border-0">
                  <span className="flex items-start gap-2.5">
                    <span className="mt-1.5">
                      <Dot tone={p.status === "PASS" ? "pass" : p.status === "PENDING" ? "unknown" : "risk"} />
                    </span>
                    <span>
                      <span className="block font-mono text-[12px] text-platinum">{p.label}</span>
                      <span className="block text-[12px] text-muted">{p.detail}</span>
                    </span>
                  </span>
                  <StatusChip tone={p.status === "PASS" ? "pass" : p.status === "PENDING" ? "unknown" : "risk"}>
                    {p.status}
                  </StatusChip>
                </li>
              ))}
            </ul>
          </Panel>

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
                Export is disabled until every required pre-flight item passes. This is deliberate.
              </p>
            )}
          </Panel>

          {existing && (
            <>
              {issues.length > 0 && (
                <Panel title={`NC verification — ${issues.length} issues`} meta={<DevLabel>Linter, not a verifier</DevLabel>}>
                  <p className="mb-3 text-[12px] leading-relaxed text-muted">
                    This pass catches what is cheap to catch in text: travel envelope violations, speeds above the
                    spindle maximum, motion below Z0 with the spindle off, missing units. It does not verify collisions
                    or material removal.
                  </p>
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
                    <StatusChip tone="neutral">{existing.postId}</StatusChip>
                    <StatusChip tone="risk">Not certified</StatusChip>
                  </span>
                }
                dense
              >
                <pre className="max-h-[520px] overflow-auto bg-void px-4 py-3 font-mono text-[11.5px] leading-relaxed text-platinum-dim">
                  {existing.code}
                </pre>
              </Panel>
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

function item(id: string, label: string, pass: boolean, detail: string, required: boolean): PreflightItem {
  return { id, label, status: pass ? "PASS" : "FAIL", detail, required };
}

function workholdingSummary(pkg: Awaited<ReturnType<typeof buildPackage>>): string {
  if (!pkg) return "";
  const levels = Object.values(pkg.workholdingBySetup).map((a) => a.level);
  if (levels.length === 0) return "No setups to evaluate";
  const bad = levels.filter((l) => l !== "SAFE" && l !== "LIKELY_SAFE");
  return bad.length === 0 ? "All setups assessed safe or likely safe" : `${bad.length} setup(s) at ${bad.join(", ")}`;
}

export const dynamic = "force-dynamic";

import { NextResponse } from "next/server";
import { createHash } from "node:crypto";
import { requireWriteApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { loadRevision, getTools, getMachines, getMaterials, getSetups } from "@/lib/data";
import { selectPrimaryMachine } from "@/lib/package-selectors";
import { parseNC } from "@/lib/nc/parse";
import { analyzeNC } from "@/lib/nc/analyze";
import { analyzeLoad, type LoadContext } from "@/lib/nc/load";
import { buildProtectedRegions } from "@/lib/nc/protection";
import { emitOptimized } from "@/lib/nc/emit";
import { verifyNc } from "@/lib/engines/cam/post";

/**
 * OPTIMIZED NC — Phases 4E/4F endpoint
 *
 * The client sends the STORED original's id and digest, the strategy
 * preset, and which proposals the operator accepted — identified by line
 * range and feeds, not by trusted content. The original text is read from
 * the immutable UPLOADED row in the database, never from bytes the client
 * re-sends, and the digest must match — a swapped or stale subject is
 * refused. The server then RE-DERIVES the proposals from scratch and
 * applies only the accepted ones that still match exactly.
 *
 * The optimized text must round-trip: it is re-parsed (zero refusals),
 * re-analyzed for the before/after comparison, linted by verifyNc, and the
 * masked geometry diff must be clean. Only then is it stored as an
 * NCProgram row with origin OPTIMIZED and the full audit — where it renders
 * behind the same pre-flight and exports through the same mint as any other
 * program, or not at all.
 */

export async function POST(request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const gate = await requireWriteApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) return NextResponse.json({ error: "Part not found" }, { status: 404 });

  const form = await request.formData().catch(() => null);
  const uploadedProgramId = String(form?.get("uploadedProgramId") ?? "");
  const claimedDigest = String(form?.get("digest") ?? "");
  const acceptedRaw = form?.get("accepted");
  const preset = String(form?.get("preset") ?? "BALANCED") as LoadContext["preset"];
  if (!uploadedProgramId || typeof acceptedRaw !== "string") {
    return NextResponse.json({ error: "Stored program id and accepted proposals are required. Analyze first." }, { status: 400 });
  }
  const accepted = JSON.parse(acceptedRaw) as { lines: [number, number]; originalFeed: number; proposedFeed: number }[];
  if (accepted.length === 0) return NextResponse.json({ error: "No proposals accepted." }, { status: 400 });

  const [tools, machines, materials] = await Promise.all([
    getTools(user.organizationId), getMachines(user.organizationId), getMaterials(user.organizationId),
  ]);
  const loadTools: LoadContext["tools"] = {};
  for (const t of tools) loadTools[t.toolNumber] = { diameter: t.diameter, flutes: t.flutes, chiploadMin: t.chiploadMin, chiploadMax: t.chiploadMax };
  const materialName = revision.intent.material.value ?? "";
  const material = materials.find((m) => materialName.toLowerCase().includes(m.name.toLowerCase().split(" ")[0]));
  const stock = revision.stock ? { x: revision.stock.x, y: revision.stock.y, z: revision.stock.z } : null;
  /*
   * The machine THIS part's setups name — not machines[0]. The audit gate
   * "Machine profile" is written to report INSUFFICIENT_DATA when no
   * machine is bound ("rapid rate and feed ceiling are defaults, not this
   * machine"), and the first-machine fallback defeated it: any shop owning
   * one machine record read as machine-known for every part, and the feed
   * ceiling that caps every raise proposal came from a machine that may
   * not be the one running the program.
   */
  const machine = selectPrimaryMachine(await getSetups(revision.revisionId), machines);

  // The immutable original, from the database — reachable only through the
  // session's own revision. The digest check refuses a swapped subject.
  const original = await db.nCProgram.findFirst({
    where: { id: uploadedProgramId, partRevisionId: revision.revisionId, origin: "UPLOADED" },
  });
  if (!original) return NextResponse.json({ error: "Stored original not found for this revision. Analyze first." }, { status: 404 });
  // The header claims a swapped or stale subject is refused. An optional
  // check is not a check: omitting the field must not skip it.
  if (!claimedDigest) {
    return NextResponse.json({ error: "The stored original's digest is required — it is what ties this optimization to the program you analyzed." }, { status: 400 });
  }
  if (original.sourceDigest !== claimedDigest) {
    return NextResponse.json({ error: "Digest mismatch — the stored original is not the program you analyzed. Re-analyze." }, { status: 409 });
  }
  const originalText = original.code;
  const parsed = parseNC(originalText);
  if (parsed.refusals.length > 0) {
    return NextResponse.json({ error: `Program refused at line ${parsed.refusals[0].line}: ${parsed.refusals[0].reason}` }, { status: 422 });
  }

  // Re-derive server-side; accept only exact matches.
  const derived = analyzeLoad(parsed, {
    stock, tools: loadTools, specificEnergy: material?.specificEnergy ?? null,
    machineMaxFeed: machine?.maxFeed ?? null,
    preset: ["CONSERVATIVE", "BALANCED", "AGGRESSIVE", "LIGHTS_OUT"].includes(preset) ? preset : "BALANCED",
    protectedRegions: buildProtectedRegions(revision.features),
  });
  const matched = derived.proposals.filter((p) =>
    accepted.some((a) => a.lines[0] === p.lines[0] && a.lines[1] === p.lines[1] && a.originalFeed === p.originalFeed && a.proposedFeed === p.proposedFeed),
  );
  if (matched.length !== accepted.length) {
    return NextResponse.json(
      { error: `${accepted.length - matched.length} accepted proposal(s) no longer match the server's derivation — context changed. Re-analyze and accept again.` },
      { status: 409 },
    );
  }

  const emitted = emitOptimized(originalText, matched);
  if (!emitted.ok) {
    return NextResponse.json({ error: "Emission failed the geometry diff — nothing was stored.", violations: emitted.geometryViolations.slice(0, 5) }, { status: 500 });
  }

  // Round-trip verification: the optimized text must parse identically in
  // structure and pass the same lint the generator's output does.
  const reparsed = parseNC(emitted.text);
  if (reparsed.refusals.length > 0 || reparsed.segments.length !== parsed.segments.length) {
    return NextResponse.json({ error: "Optimized text failed re-parsing — nothing was stored." }, { status: 500 });
  }
  const before = analyzeNC(parsed, { stock, toolDiameters: Object.fromEntries(tools.map((t) => [t.toolNumber, t.diameter])), rapidRate: machine?.maxRapid ?? null, axisAccel: machine?.axisAccel ?? null });
  const after = analyzeNC(reparsed, { stock, toolDiameters: Object.fromEntries(tools.map((t) => [t.toolNumber, t.diameter])), rapidRate: machine?.maxRapid ?? null, axisAccel: machine?.axisAccel ?? null });
  const lint = machine ? verifyNc(emitted.text, machine) : [];

  const auditPayload = {
    scope: "FEED-ONLY OPTIMIZATION — geometry verified identical by masked diff",
    preset,
    applied: emitted.applied,
    unapplied: emitted.unapplied,
    originalDigest: sha(originalText),
    optimizedDigest: sha(emitted.text),
    originalMinutes: before.totalMinutes,
    optimizedMinutes: after.totalMinutes,
    savedSeconds: Number(((before.totalMinutes - after.totalMinutes) * 60).toFixed(1)),
    caveats: ["No acceleration model — savings overstate on short segments.", ...after.assumptions],
  };

  const program = await db.nCProgram.create({
    data: {
      partRevisionId: revision.revisionId,
      machineId: machine?.id ?? null,
      postId: "optimizer-4e",
      programNumber: /O(\d+)/.exec(originalText)?.[1] ?? "0000",
      units: parsed.units,
      code: emitted.text,
      certified: false,
      origin: "OPTIMIZED",
      sourceProgramId: original.id,
      optimizationAuditJson: JSON.stringify(auditPayload),
      verificationIssuesJson: JSON.stringify(lint),
      generatedBy: user.id,
    },
  });

  // One HUMAN row per applied proposal — the acceptance is the act — plus a
  // SYSTEM row for the mechanical diff.
  for (const a of emitted.applied) {
    await audit({
      organizationId: user.organizationId, userId: user.id,
      entityType: "NCProgram", entityId: program.id, action: "UPDATE", actorType: "HUMAN",
      reason: "Feed proposal accepted",
      newValue: `L${a.lines[0]}-${a.lines[1]}: F${a.originalFeed} -> F${a.proposedFeed}`,
    });
  }
  await audit({
    organizationId: user.organizationId, userId: user.id,
    entityType: "NCProgram", entityId: program.id, action: "GENERATE", actorType: "SYSTEM",
    reason: "Optimized emission — masked geometry diff clean, round-trip parse identical",
    newValue: `${emitted.applied.length} applied, ${emitted.unapplied.length} unapplied, ~${auditPayload.savedSeconds}s estimated`,
  });

  return NextResponse.json({
    programId: program.id,
    applied: emitted.applied.length,
    unapplied: emitted.unapplied,
    savedSeconds: auditPayload.savedSeconds,
    originalMinutes: before.totalMinutes,
    optimizedMinutes: after.totalMinutes,
    lintErrors: lint.filter((i) => i.severity === "ERROR").length,
  });
}

const sha = (s: string) => createHash("sha256").update(s, "utf8").digest("hex");

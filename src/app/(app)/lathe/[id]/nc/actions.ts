"use server";

import { createHash, randomBytes } from "node:crypto";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildTurnPackage } from "@/lib/manufacturing/turn/package";
import type { MintGrant, MintRefusal, ExportOutcome, RecordResult } from "@/app/(app)/parts/[id]/nc/actions";

/**
 * TURNING NC EXPORT — the same authorization law as the mill, gated by
 * the TURNING readiness (worst-gate), re-run at mint time and again at
 * record time via buildTurnPackage — the same function the workspace
 * renders from, so the button and the gate cannot drift apart.
 *
 * The emitted file keeps the development post's NOT FOR PRODUCTION USE
 * header — an export authorization is permission to take bytes out of
 * CANVAS, not a certification of the post processor. Training parts are
 * refused at the mint, organisation always from the session, tokens are
 * single-use with a 5-minute TTL, and every outcome is audited with the
 * actor typed.
 */

const AUTHORIZATION_TTL_MS = 5 * 60 * 1000;
const LATHE_POST_ID = "canvas-lathe-dev";
const LATHE_PROGRAM_NUMBER = "2001";

export async function mintTurnExport(partId: string): Promise<MintGrant | MintRefusal> {
  const user = await requireWrite();
  const pkg = await buildTurnPackage(user.organizationId, partId);
  if (!pkg) return { ok: false, refused: [{ id: "part", label: "Part", detail: "Not found in this organisation" }] };

  if (pkg.part.training) {
    return {
      ok: false,
      refused: [{ id: "training", label: "Training project", detail: "Training projects cannot export production NC. Practise everything else freely." }],
    };
  }

  // The gate IS the turning readiness — worst unresolved required gate.
  if (pkg.blocking.length > 0 || pkg.readiness.overall === "NOT_READY_TO_RUN") {
    return {
      ok: false,
      refused: pkg.blocking.map((g) => ({ id: g.id, label: g.label, detail: g.detail })),
    };
  }
  if (pkg.program.refusals.length > 0) {
    return {
      ok: false,
      refused: pkg.program.refusals.map((r, i) => ({ id: `post-${i}`, label: "Post refusal", detail: r })),
    };
  }
  if (!pkg.program.code.trim()) {
    return { ok: false, refused: [{ id: "program", label: "Program", detail: "The post emitted no program for this plan." }] };
  }

  // Store the emitted program so the authorization has a durable subject.
  const program = await db.nCProgram.create({
    data: {
      partRevisionId: pkg.revisionId,
      postId: LATHE_POST_ID,
      programNumber: LATHE_PROGRAM_NUMBER,
      workOffset: "G54",
      units: "IN",
      code: pkg.program.code,
      certified: false,
      origin: "GENERATED",
      generatedBy: "SYSTEM",
    },
  });

  const bytes = Buffer.from(program.code, "utf8");
  const digest = createHash("sha256").update(bytes).digest("hex");
  const filename = `O${program.programNumber}.NC`;
  const expiresAt = new Date(Date.now() + AUTHORIZATION_TTL_MS);

  const auth = await db.nCExportAuthorization.create({
    data: {
      token: randomBytes(32).toString("hex"),
      organizationId: user.organizationId,
      ncProgramId: program.id,
      partRevisionId: program.partRevisionId,
      filename,
      byteLength: bytes.byteLength,
      digest,
      issuedToUserId: user.id,
      expiresAt,
    },
  });

  return {
    ok: true,
    token: auth.token,
    filename,
    byteLength: bytes.byteLength,
    digest,
    code: program.code,
    programNumber: program.programNumber,
    postName: "CANVAS development lathe post (NOT FOR PRODUCTION USE)",
    expiresAtIso: expiresAt.toISOString(),
  };
}

export async function recordTurnExport(input: {
  token: string;
  outcome: ExportOutcome;
  destinationName?: string;
  writtenFilename?: string;
  clientDigest?: string;
  failureDetail?: string;
}): Promise<RecordResult> {
  const user = await requireWrite();

  const auth = await db.nCExportAuthorization.findUnique({ where: { token: input.token } });
  if (!auth || auth.organizationId !== user.organizationId || auth.issuedToUserId !== user.id) {
    return { ok: false, error: "Authorisation not found" };
  }
  if (auth.consumedAt) return { ok: false, error: "Authorisation already spent" };
  if (auth.expiresAt.getTime() < Date.now()) return { ok: false, error: "Authorisation expired" };

  const consumed = await db.nCExportAuthorization.updateMany({
    where: { id: auth.id, consumedAt: null },
    data: {
      consumedAt: new Date(),
      outcome: input.outcome,
      destinationName: input.destinationName ?? null,
      writtenFilename: input.writtenFilename ?? null,
      clientDigest: input.clientDigest ?? null,
    },
  });
  if (consumed.count === 0) return { ok: false, error: "Authorisation already spent" };

  // Re-check the TURNING gate at record time. The write already happened
  // client-side; if the package changed between mint and record, the audit
  // trail says the authorisation lapsed rather than quietly looking normal.
  const rev = await db.partRevision.findUnique({ where: { id: auth.partRevisionId }, select: { partId: true } });
  const pkg = rev ? await buildTurnPackage(user.organizationId, rev.partId) : null;
  const gateHolds = Boolean(pkg && pkg.blocking.length === 0 && pkg.readiness.overall !== "NOT_READY_TO_RUN" && pkg.program.refusals.length === 0);

  const verifiedByClient = input.outcome === "WRITTEN_VERIFIED" && input.clientDigest === auth.digest;

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "NCProgram",
    entityId: auth.ncProgramId,
    action: "EXPORT",
    actorType: "HUMAN",
    reason: reasonFor(input.outcome, gateHolds),
    newValue: `${auth.filename} · ${auth.byteLength} bytes · destination "${input.destinationName ?? "not reported"}"`,
  });
  if (input.outcome === "WRITTEN_VERIFIED" || input.outcome === "WRITTEN_MISMATCH") {
    await audit({
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "NCProgram",
      entityId: auth.ncProgramId,
      action: "EXPORT",
      actorType: "SYSTEM",
      field: "read-back-compare",
      reason: "Read back through the same file handle in the export island (client-side), compared to the digest minted server-side.",
      newValue: verifiedByClient
        ? `sha256 ${auth.digest} — matches`
        : `sha256 expected ${auth.digest}, read back ${input.clientDigest ?? "none"} — MISMATCH`,
    });
  }

  return { ok: true, gateLapsed: !gateHolds };
}

function reasonFor(outcome: ExportOutcome, gateHolds: boolean): string {
  const base =
    outcome === "WRITTEN_VERIFIED"
      ? "Turning export, write verified by read-back"
      : outcome === "WRITTEN_MISMATCH"
        ? "Turning export, read-back DID NOT MATCH"
        : outcome === "DOWNLOAD_OFFERED"
          ? "Offered for download — destination and write not verifiable in this browser"
          : "Write attempted, nothing written";
  return gateHolds ? base : `${base}. Turning readiness no longer passed at record time — authorisation lapsed between mint and record.`;
}

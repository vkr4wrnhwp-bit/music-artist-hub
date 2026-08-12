"use server";

import { createHash, randomBytes } from "node:crypto";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import { buildPreflight } from "@/lib/engines/cam/preflight";
import { getPost, preflightPassed } from "@/lib/engines/cam/post";

/**
 * NC EXPORT — mint and record.
 *
 * The only server surface that emits NC bytes is `mintExport`, and it re-runs
 * the pre-flight gate every time it is called. There is no route that answers
 * "give me the program with this id"; the client can only spend a token it was
 * issued seconds ago, for bytes it was handed at the same moment.
 *
 * The 5-minute TTL is what stops an authorisation minted this morning being
 * spent this afternoon after the workholding changed. The single-use consume
 * is atomic, so a replayed record call is a no-op.
 *
 * Tenancy: organisation id comes from the session on both calls, never from
 * the payload. NCProgram has no organizationId column — it hangs off
 * partRevisionId — so it is only ever reached through buildPackage, which is
 * scoped to the session's organisation. See CLAUDE.md principle 13.
 */

const AUTHORIZATION_TTL_MS = 5 * 60 * 1000;

export interface MintRefusal {
  ok: false;
  refused: { id: string; label: string; detail: string }[];
}

export interface MintGrant {
  ok: true;
  token: string;
  filename: string;
  byteLength: number;
  /** SHA-256 of the program text, hex, computed server-side. */
  digest: string;
  code: string;
  programNumber: string;
  postName: string;
  expiresAtIso: string;
}

export async function mintExport(partId: string): Promise<MintGrant | MintRefusal> {
  const user = await requireUser();
  const pkg = await buildPackage(user.organizationId, partId);
  if (!pkg) return { ok: false, refused: [{ id: "part", label: "Part", detail: "Not found in this organisation" }] };

  // Training projects never export production NC — that is the isolation
  // that makes the Training Shop safe to practise in. Checked here at the
  // mint, not only in the UI, because a server action is a POST endpoint.
  const partRow = await db.part.findFirst({ where: { id: partId, organizationId: user.organizationId }, select: { training: true } });
  if (partRow?.training) {
    return {
      ok: false,
      refused: [{ id: "training", label: "Training project", detail: "Training projects cannot export production NC. Practise everything else freely." }],
    };
  }

  const program = await db.nCProgram.findFirst({
    where: { partRevisionId: pkg.revision.revisionId },
    orderBy: { createdAt: "desc" },
  });
  if (!program) {
    return { ok: false, refused: [{ id: "program", label: "Program generated", detail: "No NC program stored for this revision" }] };
  }

  const post = getPost(program.postId);
  const gate = buildPreflight(pkg, post);
  if (!preflightPassed(gate)) {
    return {
      ok: false,
      refused: gate
        .filter((i) => i.required && i.status !== "PASS")
        .map((i) => ({ id: i.id, label: i.label, detail: i.detail })),
    };
  }

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
    postName: post?.name ?? program.postId,
    expiresAtIso: expiresAt.toISOString(),
  };
}

export type ExportOutcome = "WRITTEN_VERIFIED" | "WRITTEN_MISMATCH" | "DOWNLOAD_OFFERED" | "WRITE_FAILED";

export interface RecordResult {
  ok: boolean;
  /** Set when the gate no longer held at record time. The bytes may already be
   * on the drive; pretending otherwise would be worse than saying so. */
  gateLapsed?: boolean;
  error?: string;
}

export async function recordExport(input: {
  token: string;
  outcome: ExportOutcome;
  /** Leaf name of what the operator chose. Media type is unknowable here. */
  destinationName?: string;
  writtenFilename?: string;
  /** SHA-256 the export island computed from the read-back, hex. */
  clientDigest?: string;
  failureDetail?: string;
}): Promise<RecordResult> {
  const user = await requireUser();

  const auth = await db.nCExportAuthorization.findUnique({ where: { token: input.token } });
  if (!auth || auth.organizationId !== user.organizationId || auth.issuedToUserId !== user.id) {
    return { ok: false, error: "Authorisation not found" };
  }
  if (auth.consumedAt) return { ok: false, error: "Authorisation already spent" };
  if (auth.expiresAt.getTime() < Date.now()) return { ok: false, error: "Authorisation expired" };

  // Atomic consume: a replay finds consumedAt set and updates nothing.
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

  // Re-check the gate. The write has already happened client-side — this does
  // not undo it, but if the package changed between mint and record, the audit
  // trail must say the authorisation lapsed rather than quietly look normal.
  const part = await db.partRevision.findUnique({ where: { id: auth.partRevisionId }, select: { partId: true } });
  const pkg = part ? await buildPackage(user.organizationId, part.partId) : null;
  const program = await db.nCProgram.findUnique({ where: { id: auth.ncProgramId } });
  const gateHolds = Boolean(
    pkg && program && preflightPassed(buildPreflight(pkg, getPost(program.postId))),
  );

  const verifiedByClient = input.outcome === "WRITTEN_VERIFIED" && input.clientDigest === auth.digest;

  // Two rows, actor typed explicitly. The operator chose the destination and
  // completed the write: HUMAN. The read-back comparison ran in the export
  // island against the server-issued digest: SYSTEM, and the method says
  // where it ran — the server cannot see the drive and does not claim to.
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "NCProgram",
    entityId: auth.ncProgramId,
    action: "EXPORT",
    actorType: "HUMAN",
    reason: gateLapsedReason(input.outcome, gateHolds),
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

function gateLapsedReason(outcome: ExportOutcome, gateHolds: boolean): string {
  const base =
    outcome === "WRITTEN_VERIFIED"
      ? "Operator export, write verified by read-back"
      : outcome === "WRITTEN_MISMATCH"
        ? "Operator export, read-back DID NOT MATCH"
        : outcome === "DOWNLOAD_OFFERED"
          ? "Offered for download — destination and write not verifiable in this browser"
          : "Write attempted, nothing written";
  return gateHolds ? base : `${base}. Pre-flight no longer passed at record time — authorisation lapsed between mint and record.`;
}

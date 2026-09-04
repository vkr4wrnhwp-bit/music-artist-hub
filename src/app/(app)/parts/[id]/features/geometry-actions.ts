"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { loadRevision } from "@/lib/data";
import { audit } from "@/lib/audit";
import { readDxf } from "@/lib/dxf/parse";
import { recognizeGeometry } from "@/lib/geometry/recognize";
import { rawSegmentSchema, type RawSegment } from "@/lib/geometry/loop";

/**
 * GETTING A REAL OUTLINE INTO A PART.
 *
 * `Feature.chain` was read by the contour engine and the chamfer engine, typed
 * in the domain, and written by nothing. Every profile CANVAS posted was
 * `rectangleChain(width, length, cornerRadius)` — a rounded rectangle from
 * three numbers, whatever shape the part actually was. An L-bracket came out a
 * rectangle and nothing said so.
 *
 * Two ways in, one path through. A DXF is what a shop already has, exported
 * from whatever CAD it owns; a sketch drawn here is what a shop does when the
 * drawing is a napkin. Both become the same unordered bag of lines and arcs,
 * both go through the same assembly, the same winding rule and the same
 * refusals, and both land as a PROPOSAL a human accepts before it is geometry.
 *
 * The units question is asked, never assumed. A millimetre drawing read as
 * inches is a part 25.4 times too big, and every number in it is
 * self-consistent, so nothing downstream would catch it.
 */

const MAX_BYTES = 10 * 1024 * 1024;
/** Enough for any 2D profile; past this a file is a 3D export or a drawing set. */
const MAX_SEGMENTS = 20000;

type Result = { error: string } | { ok: true; proposalId: string; summary: string };

/**
 * HOW DEEP THE PROFILE IS CUT.
 *
 * Not in a 2D drawing, and not guessable from one. It is asked here because
 * the person importing knows how thick the part is and CANVAS does not — and
 * without it the feature is refused downstream for a missing depth, which
 * turned an import into an accept that silently wrote nothing.
 */
function readDepth(formData: FormData): number | { error: string } {
  const raw = String(formData.get("depth") ?? "").trim();
  if (raw === "") return { error: "Say how deep the profile is cut. A 2D drawing does not say, and CANVAS will not pick one." };
  const d = Number(raw);
  if (!Number.isFinite(d) || d <= 0) return { error: "Profile depth has to be a positive number of inches." };
  return d;
}

async function propose(
  partId: string,
  segments: RawSegment[],
  depth: number,
  source: { label: string; providerId: string; reason: string },
): Promise<Result> {
  const user = await requireWrite();
  const revision = await loadRevision(user.organizationId, partId);
  if (!revision) return { error: "Part not found." };

  if (segments.length === 0) return { error: "No lines or arcs to read." };
  if (segments.length > MAX_SEGMENTS) {
    return { error: `${segments.length} entities is past the ${MAX_SEGMENTS} this reads. Export the profile layer on its own.` };
  }

  const rec = recognizeGeometry(segments, { label: source.label, depth });

  if (!rec.profile) {
    /*
     * A refusal is not an error message to bury. The drawing has a specific
     * problem at specific coordinates, and that is what the shop needs in
     * order to fix it in CAD and try again.
     */
    return {
      error:
        rec.refusals.length > 0
          ? `${rec.refusals[0].reason} ${rec.refusals[0].recommendations.join(". ")}.`
          : "Nothing in this closed into an outline.",
    };
  }

  const row = await db.aIRecommendation.create({
    data: {
      partRevisionId: revision.revisionId,
      kind: "FEATURE",
      summary:
        `Outside profile from ${source.reason}: ${rec.profile.chain!.length} segments, ` +
        `${rec.profileSize!.width.toFixed(4)}" × ${rec.profileSize!.length.toFixed(4)}". ` +
        (rec.interior.length > 0
          ? `${rec.interior.length} interior ${rec.interior.length === 1 ? "loop" : "loops"} found and NOT imported — ` +
            `${rec.interior
              .map((i) => (i.diameter ? `⌀${i.diameter.toFixed(4)} at ${i.x.toFixed(3)}, ${i.y.toFixed(3)}` : `${i.label} at ${i.x.toFixed(3)}, ${i.y.toFixed(3)}`))
              .join("; ")}. A drawing does not say whether a circle is drilled, bored or milled, so add those as features yourself. `
          : "") +
        [...rec.warnings, ...rec.refusals.map((r) => r.reason)].join(" "),
      payloadJson: JSON.stringify([rec.profile]),
      providerId: source.providerId,
      /*
       * Not a model score. This is deterministic geometry — a parser and
       * arithmetic — and the number exists because the column does. What makes
       * it safe is the human acceptance, not a confidence.
       */
      confidence: 1,
      status: "PROPOSED",
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "PartRevision",
    entityId: revision.revisionId,
    action: "GENERATE",
    // A parser and arithmetic, not a model.
    actorType: "SYSTEM",
    reason: source.reason,
    newValue: `Outside profile proposed: ${rec.profile.chain!.length} segments, ${rec.interior.length} interior loops not imported`,
  });

  revalidatePath(`/parts/${partId}`, "layout");
  return { ok: true, proposalId: row.id, summary: `${rec.profile.chain!.length} segments` };
}

/** A DXF exported from whatever CAD the shop owns. */
export async function importDxfProfile(partId: string, formData: FormData): Promise<Result> {
  const file = formData.get("file");
  if (!(file instanceof File)) return { error: "Attach a .dxf file." };
  if (file.size > MAX_BYTES) return { error: "File is over the 10 MB import limit." };

  const depth = readDepth(formData);
  if (typeof depth === "object") return depth;

  const read = readDxf(await file.text());
  if (read.segments.length === 0) {
    return { error: read.warnings.join(" ") || "No lines or arcs in this file." };
  }

  /*
   * Units are the one thing that must not be guessed. $INSUNITS says what the
   * numbers mean; a file that does not say gets asked rather than assumed,
   * because a millimetre drawing read as inches is a part 25.4 times too big
   * and every check in this system would pass it.
   */
  const stated = String(formData.get("units") ?? "");
  const units = read.units ?? (stated === "IN" || stated === "MM" ? stated : null);
  if (!units) {
    return {
      error:
        "This DXF does not record its units, so CANVAS will not assume them — a millimetre drawing read as inches is a part 25.4 times too big. Say which the drawing is and import again.",
    };
  }

  const k = units === "MM" ? 1 / 25.4 : 1;
  const segments: RawSegment[] =
    k === 1
      ? read.segments
      : read.segments.map((s) =>
          s.kind === "LINE"
            ? { kind: "LINE", a: { x: s.a.x * k, y: s.a.y * k }, b: { x: s.b.x * k, y: s.b.y * k } }
            : {
                kind: "ARC",
                a: { x: s.a.x * k, y: s.a.y * k },
                b: { x: s.b.x * k, y: s.b.y * k },
                center: { x: s.center.x * k, y: s.center.y * k },
                cw: s.cw,
              },
        );

  const result = await propose(partId, segments, depth, {
    label: "Outside profile",
    providerId: "dxf-import",
    reason: `DXF import: ${file.name}${read.units ? "" : ` (units stated as ${units} — the file does not say)`}`,
  });

  if ("error" in result) return result;
  return { ...result, summary: `${result.summary} from ${file.name}` };
}

/** A profile drawn in CANVAS, arriving as the same lines and arcs. */
export async function saveDrawnProfile(partId: string, formData: FormData): Promise<Result> {
  const depth = readDepth(formData);
  if (typeof depth === "object") return depth;

  const raw = String(formData.get("segments") ?? "");
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { error: "The drawing did not arrive intact. Try saving it again." };
  }

  // Same validator the schema uses on the way into a feature: a coordinate
  // that is not a finite number is not a place on the part.
  const check = rawSegmentSchema.array().safeParse(parsed);
  if (!check.success) return { error: "The drawing contains a point that is not a real coordinate." };

  return propose(partId, check.data, depth, {
    label: "Outside profile",
    providerId: "canvas-sketch",
    reason: "Profile drawn in CANVAS",
  });
}

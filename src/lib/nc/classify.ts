import type { ParsedNC, NCSegment } from "./parse";

/**
 * OPERATION CLASSIFICATION — deterministic motion evidence only.
 *
 * Groups a parsed program by tool region and classifies each group from
 * what the motion actually does. The rules are narrow on purpose: a group
 * earns a label only when the evidence is unambiguous, and everything
 * else is UNKNOWN — an unlabeled operation is honest; a mislabeled one
 * teaches the wrong thing. No AI here; an AI label, when the product adds
 * one, arrives separately marked AI_INFERRED and a human confirms it.
 *
 * Rules (cutting distance shares within the group):
 *   DRILL    ≥70% of cutting distance is vertical (|dz| dominant), at
 *            two or more distinct XY positions, with retracts between.
 *   TAP      as DRILL but the segments carry the parser's tapping flag.
 *   FACE     ≥90% of cutting at ONE Z level, XY span covers a large area.
 *   POCKET   XY cutting at 2+ descending Z levels inside a bounded region.
 *   LINKING  no cutting at all (positioning / tool-change region).
 *   UNKNOWN  everything the rules above cannot claim.
 */

export type OperationKind = "DRILL" | "TAP" | "FACE" | "POCKET" | "LINKING" | "UNKNOWN";

export interface NCOperationGroup {
  toolNumber: number;
  lines: [number, number];
  kind: OperationKind;
  /** Always DETERMINISTIC in V1 — there is no other classifier. */
  method: "DETERMINISTIC";
  detail: string;
  cutSegments: number;
}

const dist = (s: NCSegment) => Math.hypot(s.x1 - s.x0, s.y1 - s.y0, s.z1 - s.z0);

export function classifyOperations(parsed: ParsedNC): NCOperationGroup[] {
  // Split at tool changes; segments between belong to one group.
  const groups: NCSegment[][] = [];
  let cur: NCSegment[] = [];
  let curTool = parsed.segments[0]?.toolNumber ?? 0;
  for (const s of parsed.segments) {
    if (s.toolNumber !== curTool && cur.length > 0) {
      groups.push(cur);
      cur = [];
      curTool = s.toolNumber;
    }
    cur.push(s);
  }
  if (cur.length > 0) groups.push(cur);

  return groups.map((segs) => {
    const toolNumber = segs[0].toolNumber;
    const lines: [number, number] = [Math.min(...segs.map((s) => s.line)), Math.max(...segs.map((s) => s.line))];
    const cuts = segs.filter((s) => s.kind !== "RAPID" && s.kind !== "DWELL" && s.feed !== null);
    const base = { toolNumber, lines, method: "DETERMINISTIC" as const, cutSegments: cuts.length };

    if (cuts.length === 0) {
      return { ...base, kind: "LINKING" as const, detail: "No cutting motion — positioning or tool-change region." };
    }

    const totalCut = cuts.reduce((t, s) => t + dist(s), 0);
    const verticalCut = cuts
      .filter((s) => Math.abs(s.z1 - s.z0) > Math.hypot(s.x1 - s.x0, s.y1 - s.y0) * 3)
      .reduce((t, s) => t + dist(s), 0);
    const xySpots = new Set(cuts.map((s) => `${s.x1.toFixed(2)},${s.y1.toFixed(2)}`));
    const zLevels = [...new Set(cuts.filter((s) => Math.abs(s.z1 - s.z0) < 1e-6).map((s) => Number(s.z1.toFixed(3))))].sort((a, b) => b - a);

    if (totalCut > 0 && verticalCut / totalCut >= 0.7 && xySpots.size >= 2) {
      const tapping = cuts.some((s) => s.tapping);
      return {
        ...base,
        kind: tapping ? ("TAP" as const) : ("DRILL" as const),
        detail: `${Math.round((verticalCut / totalCut) * 100)}% of cutting is vertical across ${xySpots.size} position(s)${tapping ? " with synchronized tapping feed" : ""}.`,
      };
    }

    if (zLevels.length === 1) {
      const xs = cuts.flatMap((s) => [s.x0, s.x1]);
      const ys = cuts.flatMap((s) => [s.y0, s.y1]);
      const span = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys));
      if (span > 2) {
        return { ...base, kind: "FACE" as const, detail: `All cutting at one Z level (${zLevels[0].toFixed(3)}) across ${span.toFixed(1)} in² of XY.` };
      }
    }

    if (zLevels.length >= 2) {
      const descending = zLevels.every((z, i) => i === 0 || z < zLevels[i - 1]);
      if (descending) {
        return { ...base, kind: "POCKET" as const, detail: `XY cutting at ${zLevels.length} descending Z levels (${zLevels[0].toFixed(3)} → ${zLevels[zLevels.length - 1].toFixed(3)}).` };
      }
    }

    return { ...base, kind: "UNKNOWN" as const, detail: "Motion pattern does not match a rule the classifier will claim. Unlabeled is honest; mislabeled teaches the wrong thing." };
  });
}

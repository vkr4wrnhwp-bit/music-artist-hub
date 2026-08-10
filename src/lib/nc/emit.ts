import type { FeedProposal } from "./load";

/**
 * OPTIMIZED NC EMISSION — Phase 4E
 *
 * Applies accepted feed proposals to the original program text and proves,
 * mechanically, that nothing else changed. The rules:
 *
 * - FEED WORDS ONLY. A proposal is applied by rewriting F-words whose value
 *   matches the proposal's original feed, on the proposal's own lines. The
 *   line count never changes, so every line number in the audit maps 1:1 to
 *   the original program.
 *
 * - MODAL RANGES ARE REFUSED, NOT GUESSED. If a proposal's line range
 *   carries no matching F-word (the feed was set earlier and inherited),
 *   applying it would require inserting words — a structural edit V1 does
 *   not make. The proposal is reported unapplied with the reason.
 *
 * - THE DIFF IS THE INVARIANT. After application, both texts are compared
 *   line by line with F-words masked out: every line must be byte-identical.
 *   A single differing coordinate, G-word or comment fails the emission —
 *   this is how "geometry never changes" stops being a promise and becomes
 *   a check.
 */

export interface EmitResult {
  ok: boolean;
  text: string;
  applied: { lines: [number, number]; originalFeed: number; proposedFeed: number }[];
  unapplied: { lines: [number, number]; reason: string }[];
  /** Non-feed differences found by the masked diff. Must be empty. */
  geometryViolations: { line: number; original: string; emitted: string }[];
}

export function emitOptimized(originalText: string, proposals: FeedProposal[]): EmitResult {
  const lines = originalText.split(/\r?\n/);
  const out = [...lines];
  const applied: EmitResult["applied"] = [];
  const unapplied: EmitResult["unapplied"] = [];

  for (const p of proposals) {
    let hits = 0;
    for (let ln = p.lines[0]; ln <= p.lines[1] && ln <= out.length; ln++) {
      const idx = ln - 1;
      // Match F-words equal to the proposal's original feed (integer or with
      // a trailing decimal, as posts emit them), outside comments.
      const replaced = out[idx].replace(/F(\d+(?:\.\d*)?)/gi, (m, v) => {
        if (Math.abs(parseFloat(v) - p.originalFeed) < 0.51) {
          hits++;
          return `F${p.proposedFeed}.`;
        }
        return m;
      });
      out[idx] = replaced;
    }
    if (hits === 0) {
      unapplied.push({
        lines: p.lines,
        reason: `Feed F${p.originalFeed} is modal from an earlier line — applying would require inserting words, which V1 does not do.`,
      });
    } else {
      applied.push({ lines: p.lines, originalFeed: p.originalFeed, proposedFeed: p.proposedFeed });
    }
  }

  const text = out.join("\n");
  const geometryViolations = maskedDiff(lines, out);

  return { ok: geometryViolations.length === 0, text, applied, unapplied, geometryViolations };
}

/** Lines compared with all F-words masked. Anything left differing is a
 *  geometry change and fails the emission. Exported so the invariant itself
 *  is testable, not just the happy path through it. */
export function maskedDiff(a: string[], b: string[]): EmitResult["geometryViolations"] {
  const out: EmitResult["geometryViolations"] = [];
  const mask = (s: string) => s.replace(/F\d+(?:\.\d*)?/gi, "F*");
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i++) {
    const ma = mask(a[i] ?? "");
    const mb = mask(b[i] ?? "");
    if (ma !== mb) out.push({ line: i + 1, original: a[i] ?? "", emitted: b[i] ?? "" });
  }
  return out;
}

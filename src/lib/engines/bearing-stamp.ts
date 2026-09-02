import { BEARINGS, findBearing, type Bearing } from "./mating";

/**
 * READING A BEARING STAMP FROM A PHOTOGRAPH
 *
 * The mating panel offered a free-text "Designation, if known" field and
 * UNKNOWN. A machinist holding a worn bearing whose stamp is easier to
 * photograph than to read had no path in.
 *
 * What makes this dangerous rather than convenient: a designation is not a
 * label, it is dimensions. `findBearing` turns 6203 into a 17 mm bore and 6208
 * into a 40 mm one, and the mating analysis then reasons about the fit from
 * that. A misread stamp does not produce a wrong caption, it produces the
 * wrong bore.
 *
 * So this file does the deterministic half, and only the deterministic half:
 *
 *   - A model may READ characters off a photograph. That is an AI inference
 *     and stays one — principle 3 — so what comes back is candidates, never a
 *     stored value.
 *   - Every candidate is resolved against the catalogue here, in code. A
 *     designation the catalogue does not carry is reported as unknown rather
 *     than given invented dimensions.
 *   - The dimensions a machinist checks against the bearing in their hand come
 *     from the catalogue, not from the model. The model never states a bore.
 */

export interface StampCandidate {
  /** Exactly what was read, before anything was done to it. */
  readAs: string;
  /** The model's own confidence in the characters. Not a confidence in the fit. */
  confidence: number;
  /** The catalogue entry it resolves to, or null when it is not one CANVAS holds. */
  bearing: Bearing | null;
  /** Why it resolves the way it does, in a sentence a machinist can check. */
  note: string;
}

/** Characters an OCR pass confuses, and what they are confused with. */
const CONFUSABLE: [RegExp, string][] = [
  [/O/g, "0"],
  [/o/g, "0"],
  [/I/g, "1"],
  [/l/g, "1"],
  [/S/g, "5"],
  [/B/g, "8"],
];

/**
 * Normalises what was read into something the catalogue can be asked about.
 *
 * A stamp is dirty, worn, curved and photographed at an angle, so the reading
 * is expected to be imperfect. This is deliberately conservative: it strips
 * whitespace and separators and nothing else. It does NOT substitute
 * confusable characters — see `confusableAlternatives`, which offers them as
 * separate candidates for a human to choose between rather than silently
 * picking one.
 */
export function normaliseStamp(raw: string): string {
  return raw.trim().toUpperCase().replace(/[\s\-_.]/g, "");
}

/**
 * Other designations the same characters could be, given the substitutions an
 * OCR pass gets wrong.
 *
 * Offered rather than applied. "62O3" could be 6203; silently correcting it
 * would hide the fact that the reading was ambiguous, and the whole point is
 * that the machinist is looking at the bearing while they decide.
 */
export function confusableAlternatives(raw: string): string[] {
  const base = normaliseStamp(raw);
  const out = new Set<string>();
  for (const [from, to] of CONFUSABLE) {
    if (from.test(base)) out.add(base.replace(new RegExp(from.source, "g"), to));
    from.lastIndex = 0;
  }
  out.delete(base);
  return [...out].filter((c) => findBearing(c) !== null);
}

/**
 * Turns raw readings into candidates, resolved against the catalogue.
 *
 * Ordered by the model's confidence, highest first, and then by whether the
 * catalogue recognises them — a recognised designation the model was less sure
 * about is more useful than an unrecognised one it was certain of.
 */
export function resolveStampReadings(readings: { text: string; confidence: number }[]): StampCandidate[] {
  const seen = new Set<string>();
  const out: StampCandidate[] = [];

  for (const r of readings) {
    const key = normaliseStamp(r.text);
    if (key === "" || seen.has(key)) continue;
    seen.add(key);

    const bearing = findBearing(key);
    out.push({
      readAs: r.text.trim(),
      confidence: Number.isFinite(r.confidence) ? Math.min(1, Math.max(0, r.confidence)) : 0,
      bearing,
      note: bearing
        ? `${bearing.designation}: ${bearing.bore} mm bore, ${bearing.outer} mm outside, ${bearing.width} mm wide. Measure the bearing to confirm.`
        : "Not a designation CANVAS holds dimensions for. Recording it stores the number and nothing is derived from it.",
    });

    // Alternatives are separate candidates, never a silent correction.
    for (const alt of confusableAlternatives(r.text)) {
      if (seen.has(alt)) continue;
      seen.add(alt);
      const b = findBearing(alt)!;
      out.push({
        readAs: alt,
        // An alternative is a guess about a guess. It is offered lower than
        // whatever it came from and never above it.
        confidence: Math.max(0, (Number.isFinite(r.confidence) ? r.confidence : 0) - 0.2),
        bearing: b,
        note: `Could be this if the stamp reads "${r.text.trim()}" — ${b.bore} mm bore, ${b.outer} mm outside. Check the characters against the bearing.`,
      });
    }
  }

  return out.sort(
    (a, b) => b.confidence - a.confidence || Number(b.bearing !== null) - Number(a.bearing !== null),
  );
}

/**
 * Whether a designation may be stored at all.
 *
 * A designation the catalogue does not hold is storable — a shop knows
 * bearings CANVAS does not — but nothing is derived from it, and the caller
 * must say so. What is refused is a designation that reads as one CANVAS
 * knows and is not: the mating analysis would then reason about the wrong
 * dimensions.
 */
export function catalogueCoverage(): { count: number; series: string[] } {
  return { count: BEARINGS.length, series: [...new Set(BEARINGS.map((b) => b.series))].sort() };
}

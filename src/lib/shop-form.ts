/**
 * SHOP RECORD FORM — server-side parsing.
 *
 * These helpers exist so that "the field was left blank" and "the field was
 * filled in with something that is not a number" never collapse into the
 * same outcome. A blank optional field becomes null, which the engines
 * already handle by naming it as a missing input. A blank *required* field,
 * or garbage in a numeric field, is a rejected submission — never a
 * substituted default.
 *
 * That distinction is principle 12 applied at the front door. If a tool's
 * stickout arrives as an empty string and we store 0, every reach check
 * downstream is computed against a fiction that looks like a measurement.
 */

export class FormRejected extends Error {
  constructor(readonly problems: string[]) {
    super(problems.join("; "));
    this.name = "FormRejected";
  }
}

export class FormReader {
  private problems: string[] = [];

  constructor(private readonly data: FormData) {}

  /** Trimmed string, or null when blank. */
  optionalText(name: string): string | null {
    const raw = this.data.get(name);
    const v = typeof raw === "string" ? raw.trim() : "";
    return v === "" ? null : v;
  }

  text(name: string, label: string): string {
    const v = this.optionalText(name);
    if (v === null) this.problems.push(`${label} is required`);
    return v ?? "";
  }

  /**
   * A number, or null when the field was left blank. A non-blank field that
   * does not parse is a problem, not a null — the difference between "not
   * recorded" and "recorded as nonsense" matters to every engine downstream.
   */
  optionalNumber(name: string, label: string, opts: { min?: number; max?: number } = {}): number | null {
    const v = this.optionalText(name);
    if (v === null) return null;
    const n = Number(v);
    if (!Number.isFinite(n)) {
      this.problems.push(`${label} is not a number`);
      return null;
    }
    if (opts.min !== undefined && n < opts.min) {
      this.problems.push(`${label} must be at least ${opts.min}`);
      return null;
    }
    if (opts.max !== undefined && n > opts.max) {
      this.problems.push(`${label} must be at most ${opts.max}`);
      return null;
    }
    return n;
  }

  number(name: string, label: string, opts: { min?: number; max?: number } = {}): number {
    const n = this.optionalNumber(name, label, opts);
    if (n === null) {
      if (this.optionalText(name) === null) this.problems.push(`${label} is required`);
      return 0;
    }
    return n;
  }

  integer(name: string, label: string, opts: { min?: number; max?: number } = {}): number {
    const n = this.number(name, label, opts);
    if (!Number.isInteger(n)) this.problems.push(`${label} must be a whole number`);
    return Math.round(n);
  }

  optionalInteger(name: string, label: string, opts: { min?: number; max?: number } = {}): number | null {
    const n = this.optionalNumber(name, label, opts);
    if (n === null) return null;
    if (!Number.isInteger(n)) {
      this.problems.push(`${label} must be a whole number`);
      return null;
    }
    return n;
  }

  /** One of a fixed vocabulary. Anything else is rejected, never coerced. */
  choice<T extends string>(name: string, label: string, allowed: readonly T[]): T {
    const v = this.optionalText(name);
    if (v === null) {
      this.problems.push(`${label} is required`);
      return allowed[0];
    }
    if (!(allowed as readonly string[]).includes(v)) {
      this.problems.push(`${label} is not one of the recognised values`);
      return allowed[0];
    }
    return v as T;
  }

  optionalChoice<T extends string>(name: string, label: string, allowed: readonly T[]): T | null {
    const v = this.optionalText(name);
    if (v === null) return null;
    if (!(allowed as readonly string[]).includes(v)) {
      this.problems.push(`${label} is not one of the recognised values`);
      return null;
    }
    return v as T;
  }

  boolean(name: string): boolean {
    return this.data.get(name) !== null;
  }

  /** A comma-separated list, stored as a JSON array string. */
  jsonList(name: string): string {
    const v = this.optionalText(name);
    if (v === null) return "[]";
    return JSON.stringify(
      v
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    );
  }

  /** Ordering check between two fields that describe a range. */
  requireOrder(lo: number | null, hi: number | null, label: string): void {
    if (lo !== null && hi !== null && lo > hi) this.problems.push(`${label}: minimum is above maximum`);
  }

  /** Throws if anything was wrong. Call once, after reading every field. */
  /**
   * A problem that is not about one field being absent or malformed.
   *
   * Cross-field rules — an uncertainty below the instrument's own resolution,
   * a printed material stronger across its layers than within them — were
   * being recorded by calling `text()` with a fake field name and the message
   * as the label. That works, because `text()` pushes a problem for a field
   * that is not there, but it formats it as "<label> is required": the
   * operator was told "Uncertainty ±0.0001 is below half the 0.001
   * resolution, which no instrument achieves is required".
   */
  problem(message: string): void {
    this.problems.push(message);
  }

  done(): void {
    if (this.problems.length > 0) throw new FormRejected(this.problems);
  }
}

/**
 * Collect problems into a query string so the form can state them without a
 * client-side state machine. Kept short — these are field-level messages,
 * not a stack trace.
 */
export function rejectionQuery(err: unknown): string {
  const problems = err instanceof FormRejected ? err.problems : ["The record could not be saved."];
  return `?problem=${encodeURIComponent(problems.slice(0, 6).join(" · "))}`;
}

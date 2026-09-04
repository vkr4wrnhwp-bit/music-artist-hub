/**
 * WHERE PROGRAM ZERO IS.
 *
 * This convention already governed the whole system and lived in two source
 * comments in two different files — the NC analyzer's assumption list and the
 * stock-removal simulator's height field — and reached the operator in neither.
 * The post header carried part, machine, date, a tool list and a warning, and
 * not the one sentence that decides whether the part is cut in the right place.
 *
 * A machinist who picks up an edge at the corner instead of the centre will run
 * a program that is dimensionally perfect and half of it in air, and the other
 * half through the vise. There is no gate that catches it, because it is not
 * wrong in the program — it is wrong in the assumption the program was written
 * under, and an assumption nobody printed is one nobody can check.
 *
 * So it lives here, once, and every surface that has to state it — the setup
 * sheet, the post header, the analyzer's assumption list — says it in the same
 * words. When a Setup grows a real origin and orientation of its own (see
 * PATH_TO_METAL B3), this becomes the default that a setup may override, and
 * the sentence becomes a property of the setup rather than of the system.
 */

export const PROGRAM_ORIGIN = {
  /** Where X0 Y0 is. */
  xy: "Centre of the stock",
  /** Where Z0 is. */
  z: "Top of the stock",
  /** One sentence, for a program header or a sheet a machinist reads. */
  sentence:
    "PROGRAM ZERO: X0 Y0 AT THE CENTRE OF THE STOCK, Z0 AT THE TOP OF THE STOCK AS IT SITS IN THE VISE.",
  /** The same fact in prose, for a screen rather than a control. */
  prose:
    "Program zero is the centre of the stock in X and Y, with Z0 at the top of the stock as it sits in the vise. Every coordinate in the program is measured from there.",
} as const;

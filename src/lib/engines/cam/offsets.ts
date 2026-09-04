/**
 * THE OFFSET REGISTERS THE PROGRAM CALLS FOR.
 *
 * `G43 H6` tells the control to apply the length in row 6 of the offset table.
 * `G41 D6` tells it to apply the radius in row 6. Those two numbers decide
 * where the tool goes in Z and how much material it leaves on every wall, and
 * a wrong H is the single most consequential wrong number in a program: the
 * tool goes to the wrong Z, which is a crash into the fixture or a cut in air.
 *
 * CANVAS wrote `lengthOffset: t.toolNumber` in three places. H and D were the
 * tool number, everywhere, with no shop record behind them — and the program
 * header and the setup sheet printed the result as though CANVAS knew what was
 * loaded in that control's offset table.
 *
 * It usually IS the tool number. That is the common convention on a Haas or a
 * Fanuc, where H and D index the same row and a presetter writes the length
 * into the row matching the pocket. It is not universal: a shop running sister
 * tools, or one that keeps diameter offsets in a separate block so a length can
 * never be typed into a radius, breaks it. The difference between those shops
 * is not something to infer from a tool number.
 *
 * So the register is recorded on the tool where a shop has recorded it, and
 * where nobody has, the number is still the tool number — a program has to call
 * SOMETHING — but it goes out labelled ASSUMED, in the header, on the setup
 * sheet, and in the pre-flight. A number stated as an assumption is one a
 * machinist can check against the control in ten seconds. A number stated as a
 * fact is one they will not think to check.
 */

export interface OffsetInput {
  toolNumber: number;
  lengthOffset: number | null;
  diameterOffset: number | null;
}

export interface OffsetRegisters {
  /** The H word: which row of the offset table holds this tool's length. */
  h: number;
  /** The D word: which row holds its radius. */
  d: number;
  /**
   * RECORDED — this shop said so. ASSUMED — nobody did, and the tool number is
   * standing in for what the control actually holds.
   */
  source: "RECORDED" | "PARTLY_RECORDED" | "ASSUMED";
  /**
   * Per word, because they are recorded per word. A row-level flag marks a
   * recorded H as assumed the moment somebody fills in one and not the other,
   * which is a true number labelled as a guess — the mirror of the defect this
   * engine exists to fix.
   */
  hRecorded: boolean;
  dRecorded: boolean;
}

export function offsetRegisters(t: OffsetInput): OffsetRegisters {
  const hasH = Number.isInteger(t.lengthOffset) && (t.lengthOffset as number) > 0;
  const hasD = Number.isInteger(t.diameterOffset) && (t.diameterOffset as number) > 0;
  return {
    h: hasH ? (t.lengthOffset as number) : t.toolNumber,
    d: hasD ? (t.diameterOffset as number) : t.toolNumber,
    source: hasH && hasD ? "RECORDED" : hasH || hasD ? "PARTLY_RECORDED" : "ASSUMED",
    hRecorded: hasH,
    dRecorded: hasD,
  };
}

/**
 * The one line the program carries when any register was assumed.
 *
 * Named tools, not a count: the operator is standing at the control with the
 * offset page open, and "T5, T6" is something they can check. "3 tools" is not.
 */
export function assumedOffsetsNote(tools: OffsetInput[]): string | null {
  const assumed = tools.filter((t) => offsetRegisters(t).source !== "RECORDED");
  if (assumed.length === 0) return null;
  const names = assumed.map((t) => `T${t.toolNumber}`).join(", ");
  return `OFFSET REGISTERS ASSUMED EQUAL TO THE TOOL NUMBER FOR ${names} — NOT RECORDED IN THE CRIB. CHECK H AND D AGAINST THE CONTROL'S OFFSET TABLE BEFORE RUNNING.`;
}

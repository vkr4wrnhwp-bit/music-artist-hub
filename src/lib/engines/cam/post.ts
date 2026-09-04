import type { Move, Toolpath } from "./types";
import { CHORD_TOLERANCE, arcGeometry, flattenArcs, isArc } from "./arc";
import { PROGRAM_ORIGIN } from "@/lib/program-origin";
import type { MachineProfile } from "@/lib/domain/shop";

/**
 * POST PROCESSOR ARCHITECTURE
 *
 * Posts are modular and data-driven so a controller family can be added
 * without touching the toolpath engine. Everything produced here is a
 * DEVELOPMENT / SIMULATION post. It is not certified for production use, it
 * carries that statement in the program header, and the UI never implies
 * otherwise. See /docs/CAM_ENGINE.md.
 */

export interface PostContext {
  programNumber: string;
  programName: string;
  machine: MachineProfile;
  workOffset: string; // G54..G59
  units: "IN" | "MM";
  toolTable: { toolNumber: number; description: string; lengthOffset: number; diameter: number }[];
  safeZ: number;
  partName: string;
  revision: string;
  generatedAtIso: string;
}

export interface PostDefinition {
  id: string;
  name: string;
  controllerFamily: string;
  /** Development-only until a post is validated on real iron. */
  certified: false;
  emit(toolpaths: Toolpath[], ctx: PostContext): string;
}

const n = (v: number, places = 4) => v.toFixed(places).replace(/^-0(\.0+)?$/, "0");

function header(ctx: PostContext, lines: string[], comment: (s: string) => string) {
  lines.push(comment("CANVAS — DEVELOPMENT / SIMULATION POST. NOT CERTIFIED FOR PRODUCTION."));
  lines.push(comment(`PART ${ctx.partName} REV ${ctx.revision}`));
  lines.push(comment(`MACHINE ${ctx.machine.manufacturer} ${ctx.machine.model}`));
  lines.push(comment(`GENERATED ${ctx.generatedAtIso}`));
  /*
   * The one sentence that decides whether the part is cut in the right place.
   *
   * It governed the whole system and lived in two source comments, reaching the
   * operator in neither. A machinist who picks up an edge at the corner instead
   * of the centre runs a program that is dimensionally perfect and half of it in
   * air, the other half through the vise — and no gate catches it, because
   * nothing is wrong in the program. It is wrong in the assumption the program
   * was written under, and an assumption nobody printed is one nobody can check.
   */
  lines.push(comment(PROGRAM_ORIGIN.sentence));
  lines.push(comment("VERIFY EVERY LINE BEFORE RUNNING. DRY RUN ABOVE THE PART."));
  for (const t of ctx.toolTable) {
    lines.push(comment(`T${t.toolNumber} ${t.description} D${n(t.diameter, 4)} H${t.lengthOffset}`));
  }
}

/* ------------------------------------------------------------------ */
/* Fanuc-family (Haas NGC, Fanuc, PathPilot share this dialect)        */
/* ------------------------------------------------------------------ */

function emitFanucFamily(dialect: "HAAS" | "FANUC" | "PATHPILOT") {
  return (toolpaths: Toolpath[], ctx: PostContext): string => {
    const lines: string[] = [];
    const c = (s: string) => `(${s})`;

    lines.push(`%`);
    lines.push(`O${ctx.programNumber} (${ctx.programName.toUpperCase()})`);
    header(ctx, lines, c);

    lines.push(ctx.units === "IN" ? "G20" : "G21");
    lines.push("G17 G40 G49 G80 G90");
    lines.push("G53 G0 Z0.");

    let currentTool = -1;
    let currentFeed = -1;

    for (const tp of toolpaths) {
      if (tp.isPlaceholder) {
        lines.push(c(`OPERATION ${tp.type} HAS NO TOOLPATH ENGINE — SKIPPED`));
        continue;
      }
      const entry = ctx.toolTable.find((t) => t.toolNumber === tp.toolNumber);
      lines.push("");
      lines.push(c(`${tp.type} — T${tp.toolNumber} ${entry?.description ?? ""}`));

      if (tp.toolNumber !== currentTool) {
        lines.push(`T${tp.toolNumber} M6`);
        currentTool = tp.toolNumber;
      }

      /*
       * HOLE-MAKING GOES OUT AS THE CONTROL'S OWN CYCLE.
       *
       * G81 to drill, G83 to peck, G84 to rigid tap. The numbers come from the
       * descriptor the engine built beside the move list, never from reading
       * the moves back — this used to derive the tap's Z and R with a
       * `Math.min` over the move list, which is pattern-matching a program out
       * of a path and gets the wrong answer the day the path changes shape.
       *
       * G84 owns the spindle: no M3, and the feed is pitch × rpm exactly as the
       * engine locked it. G98 so the tool returns to the initial level rather
       * than to R, which is what clears a clamp on the way to the next hole.
       */
      if (tp.cannedCycle) {
        const cy = tp.cannedCycle;
        const tap = cy.code === "G84";
        lines.push(
          c(
            tap
              ? `RIGID TAP — F ${cy.feed.toFixed(2)} = ${cy.rpm} RPM x pitch`
              : `${cy.code === "G83" ? "PECK DRILL" : "DRILL"} — Z${n(cy.z, 3)} R${n(cy.r, 3)}${cy.q ? ` Q${n(cy.q, 4)}` : ""}`,
          ),
        );
        lines.push(`${ctx.workOffset} G0 X${n(cy.x)} Y${n(cy.y)}`);
        lines.push(`G43 H${entry?.lengthOffset ?? tp.toolNumber} Z${n(ctx.safeZ, 3)}`);
        if (tp.parameters.coolant !== "OFF") lines.push("M8");
        lines.push(tap ? `S${cy.rpm}` : `S${cy.rpm} M3`);
        lines.push(
          `G98 ${cy.code} X${n(cy.x)} Y${n(cy.y)} Z${n(cy.z, 3)} R${n(cy.r, 3)}${cy.q ? ` Q${n(cy.q, 4)}` : ""} F${cy.feed.toFixed(2)}`,
        );
        lines.push("G80");
        lines.push("M9");
        lines.push("G53 G0 Z0.");
        // M5 after the tap too. G80 has cancelled the cycle by here, so the
        // spindle is back under normal control — and the old special-cased tap
        // branch was the one path out of this post that left it turning.
        lines.push("M5");
        continue;
      }

      lines.push(`S${tp.parameters.rpm} M3`);
      lines.push(`${ctx.workOffset} G0 X${n(tp.moves[0]?.x ?? 0)} Y${n(tp.moves[0]?.y ?? 0)}`);
      lines.push(`G43 H${entry?.lengthOffset ?? tp.toolNumber} Z${n(ctx.safeZ, 3)}`);
      if (tp.parameters.coolant !== "OFF") {
        lines.push(dialect === "HAAS" && tp.parameters.coolant === "THROUGH_SPINDLE" ? "M88" : "M8");
      }
      currentFeed = -1;

      for (let i = 0; i < tp.moves.length; i++) {
        lines.push(
          moveLine(
            tp.moves[i],
            currentFeed,
            (f) => (currentFeed = f),
            i > 0 ? tp.moves[i - 1] : null,
            // D and H are the same register number under this post. The setup
            // sheet prints it, and it is what the machinist adjusts to hold size.
            entry?.lengthOffset ?? tp.toolNumber,
          ),
        );
      }
      // A tool must never leave with compensation still active. If the engine
      // produced a path that opens comp and does not close it, the program says
      // so rather than the control finding out on the next rapid.
      if (tp.moves.some((m) => m.program?.activate) && !tp.moves.some((m) => m.program?.deactivate)) {
        lines.push(c("COMPENSATION LEFT ACTIVE BY THE TOOLPATH — CANCELLED HERE"));
        lines.push("G40");
      }

      lines.push("M9");
      lines.push("G53 G0 Z0.");
      lines.push("M5");
    }

    lines.push("");
    lines.push("G53 G0 Z0.");
    lines.push(dialect === "HAAS" ? "G53 G0 Y0." : "G53 G0 X0. Y0.");
    lines.push("M30");
    lines.push("%");
    return lines.join("\n");
  };
}

/**
 * One move, in Fanuc-family words.
 *
 * `prev` is needed because an arc's I and J are measured from where the tool
 * already is — that is the incremental convention this engine stores them in,
 * so they go out as they are held. A control reads I/J as the vector to the
 * centre; getting the sign wrong here would put the arc on the other side of
 * the part, which is why the value is never recomputed on the way out.
 *
 * G2 is clockwise seen from +Z, which is what `cw` means.
 */
function moveLine(
  mv: Move,
  currentFeed: number,
  setFeed: (f: number) => void,
  prev: Move | null,
  dOffset?: number,
): string {
  /*
   * CUTTER COMPENSATION
   *
   * When a move carries a programmed point, the PROGRAM gets the boundary and
   * the control offsets it by the D register. `x`/`y` on the move stay the
   * cutter centre for everything upstream; only these two words change.
   *
   * G41 is left of the path, G42 right, G40 cancels. The engine puts activate
   * on a straight lead-in and deactivate on a straight lead-out away from the
   * part — this only writes what it is told, because a comp code on the wrong
   * block is a fault at best and a gouge at worst.
   */
  const pg = mv.program;
  const px = pg ? pg.x : mv.x;
  const py = pg ? pg.y : mv.y;
  const coords = `X${n(px)} Y${n(py)} Z${n(mv.z, 3)}`;
  if (mv.feed === null) return `G0 ${coords}`;

  const feedWord = mv.feed !== currentFeed ? ` F${mv.feed}.` : "";
  if (mv.feed !== currentFeed) setFeed(mv.feed);

  const compOn = pg?.activate ? `${pg.side === "LEFT" ? "G41" : "G42"} D${dOffset ?? 0} ` : "";
  const compOff = pg?.deactivate ? "G40 " : "";

  if (prev && isArc(mv)) {
    // Helical when the Z changes: same G2/G3 block with a Z word, which every
    // control in this family interpolates. Arc I/J come from the programmed
    // path too — an arc's centre offset is measured from where the PROGRAM
    // says the tool is, not from where the cutter centre is.
    const ai = pg?.i ?? mv.i!;
    const aj = pg?.j ?? mv.j!;
    return `${mv.cw ? "G2" : "G3"} ${coords} I${n(ai)} J${n(aj)}${feedWord}`;
  }
  return `${compOn}${compOff}G1 ${coords}${feedWord}`;
}

/* ------------------------------------------------------------------ */
/* GRBL — no tool changer, no work offsets beyond G54, no G43          */
/* ------------------------------------------------------------------ */

const emitGrbl = (toolpaths: Toolpath[], ctx: PostContext): string => {
  const lines: string[] = [];
  const c = (s: string) => `; ${s}`;
  header(ctx, lines, c);
  lines.push(ctx.units === "IN" ? "G20" : "G21");
  lines.push("G17 G90 G94");
  lines.push("G54");

  for (const tp of toolpaths) {
    if (tp.isPlaceholder) {
      lines.push(c(`OPERATION ${tp.type} HAS NO TOOLPATH ENGINE — SKIPPED`));
      continue;
    }
    if (tp.type === "TAP") {
      // GRBL has no rigid tapping. Emitting the tap moves as feed lines would
      // strip the spindle synchronisation and break the tap in the hole.
      lines.push(c(`TAP NOT EMITTED — GRBL CANNOT RIGID TAP. TAP THIS HOLE BY HAND.`));
      continue;
    }
    // GRBL has no canned cycles either — G81 and G83 are not in its vocabulary
    // and it faults on them. Drilling therefore goes out as the long-hand
    // moves, which is the same motion in more blocks.
    if (tp.cannedCycle) {
      lines.push(c(`${tp.cannedCycle.code} NOT AVAILABLE ON GRBL — DRILLED AS FEED MOVES`));
    }
    lines.push("");
    lines.push(c(`${tp.type} — T${tp.toolNumber}`));
    lines.push("M5");
    lines.push(c("MANUAL TOOL CHANGE REQUIRED — GRBL HAS NO ATC"));
    lines.push("M0");
    lines.push(`S${tp.parameters.rpm} M3`);
    // GRBL speaks the same G2/G3 with I/J, including helical.
    // GRBL supports G41/G42 with a D word in recent builds but not on every
    // firmware in the field, and it has no offset table to hold the value. The
    // program carries the CUTTER CENTRE here instead — correct motion with no
    // adjustment available at the machine — and says so, because a machinist
    // who expects to dial a D offset needs to know there is not one.
    if (tp.moves.some((m) => m.program)) {
      lines.push(c("NO CUTTER COMPENSATION ON GRBL — PATH IS THE CUTTER CENTRE, SIZE IS NOT ADJUSTABLE AT THE MACHINE"));
    }
    let feed = -1;
    for (let i = 0; i < tp.moves.length; i++) {
      const raw = tp.moves[i];
      const centreOnly = raw.program ? { ...raw, program: undefined } : raw;
      lines.push(moveLine(centreOnly, feed, (f) => (feed = f), i > 0 ? tp.moves[i - 1] : null));
    }
  }
  lines.push("");
  lines.push("M5");
  lines.push("M30");
  return lines.join("\n");
};

/* ------------------------------------------------------------------ */
/* Heidenhain conversational — structurally different, so its own post */
/* ------------------------------------------------------------------ */

const emitHeidenhain = (toolpaths: Toolpath[], ctx: PostContext): string => {
  const lines: string[] = [];
  lines.push(`BEGIN PGM ${ctx.programNumber} ${ctx.units === "IN" ? "INCH" : "MM"}`);
  lines.push(`; CANVAS DEVELOPMENT / SIMULATION POST — NOT CERTIFIED FOR PRODUCTION`);
  lines.push(`; PART ${ctx.partName} REV ${ctx.revision}`);
  lines.push(`; ${PROGRAM_ORIGIN.sentence}`);
  let block = 1;
  const push = (s: string) => lines.push(`${block++} ${s}`);
  for (const tp of toolpaths) {
    if (tp.isPlaceholder) continue;
    if (tp.type === "TAP") {
      // Rigid tapping on TNC is cycle 207, which this development post does
      // not implement. Unsynchronised feed lines would break the tap.
      lines.push(`; TAP NOT EMITTED — TAPPING CYCLE 207 NOT IMPLEMENTED IN THIS DEVELOPMENT POST`);
      continue;
    }
    // Drilling on a TNC is CYCL DEF 200/203, not implemented here. The moves
    // cut the same hole in more blocks, which is the honest trade.
    if (tp.cannedCycle) {
      lines.push(`; DRILLING CYCLE 200/203 NOT IMPLEMENTED — DRILLED AS FEED MOVES`);
    }
    // R0 throughout: no cutter compensation in this development post, so the
    // coordinates are the cutter centre and size is not adjustable at the
    // control. Cycle 200-series comp is a separate piece of work.
    if (tp.moves.some((m) => m.program)) {
      lines.push("; NO CUTTER COMPENSATION — PATH IS THE CUTTER CENTRE, SIZE NOT ADJUSTABLE AT THE MACHINE");
    }
    push(`TOOL CALL ${tp.toolNumber} Z S${tp.parameters.rpm}`);
    push(`L Z+${n(ctx.safeZ, 3)} R0 FMAX M3`);
    /*
     * A planar arc is CC (circle centre, absolute) followed by C (move to the
     * end point) with DR- clockwise or DR+ counter-clockwise. A HELICAL arc on
     * a TNC is a different construction again, and this development post does
     * not implement it — so those are flattened to straight moves at a stated
     * chord tolerance rather than guessed at. Flattening a helix is a longer
     * program that cuts the right shape; guessing the syntax is a program that
     * does not.
     */
    const moves = tp.moves;
    for (let i = 0; i < moves.length; i++) {
      const mv = moves[i];
      const prev = i > 0 ? moves[i - 1] : null;
      const geo = prev && isArc(mv) ? arcGeometry(prev, mv) : null;
      if (geo && prev && Math.abs(mv.z - prev.z) < 1e-9) {
        push(`CC X${n(geo.centerX, 3)} Y${n(geo.centerY, 3)}`);
        push(`C X${n(mv.x, 3)} Y${n(mv.y, 3)} ${mv.cw ? "DR-" : "DR+"} R0 F${mv.feed}`);
        continue;
      }
      if (geo && prev) {
        lines.push(`; HELICAL ARC FLATTENED TO ${CHORD_TOLERANCE}IN CHORD — TNC HELIX SYNTAX NOT IMPLEMENTED`);
        for (const seg of flattenArcs([prev, mv]).slice(1)) {
          push(`L X${n(seg.x, 3)} Y${n(seg.y, 3)} Z${n(seg.z, 3)} R0 F${seg.feed}`);
        }
        continue;
      }
      const coords = `X${n(mv.x, 3)} Y${n(mv.y, 3)} Z${n(mv.z, 3)}`;
      push(mv.feed === null ? `L ${coords} R0 FMAX` : `L ${coords} R0 F${mv.feed}`);
    }
    push(`L Z+${n(ctx.safeZ, 3)} R0 FMAX M9`);
  }
  push("M30");
  lines.push(`END PGM ${ctx.programNumber} ${ctx.units === "IN" ? "INCH" : "MM"}`);
  return lines.join("\n");
};

/* ------------------------------------------------------------------ */
/* Siemens 840D                                                        */
/* ------------------------------------------------------------------ */

const emitSiemens = (toolpaths: Toolpath[], ctx: PostContext): string => {
  const lines: string[] = [];
  const c = (s: string) => `; ${s}`;
  header(ctx, lines, c);
  lines.push(ctx.units === "IN" ? "G70" : "G71");
  lines.push("G17 G90 G54");
  for (const tp of toolpaths) {
    if (tp.isPlaceholder) continue;
    if (tp.type === "TAP") {
      // Rigid tapping on 840D is CYCLE84, which this development post does
      // not implement. Unsynchronised feed lines would break the tap.
      lines.push(c("TAP NOT EMITTED — CYCLE84 NOT IMPLEMENTED IN THIS DEVELOPMENT POST"));
      continue;
    }
    // Drilling on 840D is CYCLE81/83, not implemented here.
    if (tp.cannedCycle) {
      lines.push(c("DRILLING CYCLE81/83 NOT IMPLEMENTED — DRILLED AS FEED MOVES"));
    }
    lines.push("");
    lines.push(c(`${tp.type}`));
    lines.push(`T="T${tp.toolNumber}" M6`);
    lines.push(`S${tp.parameters.rpm} M3`);
    lines.push("D1");
    /*
     * 840D takes G2/G3 with incremental I/J for a planar arc, which is the
     * same convention the engine stores. A helix needs TURN= and a full-turn
     * count, and this development post does not implement it — flattened to a
     * stated chord tolerance instead, and the program says so where it happens.
     */
    if (tp.moves.some((m) => m.program)) {
      lines.push(c("NO CUTTER COMPENSATION — PATH IS THE CUTTER CENTRE, SIZE NOT ADJUSTABLE AT THE MACHINE"));
    }
    let feed = -1;
    const moves = tp.moves;
    for (let i = 0; i < moves.length; i++) {
      const mv = moves[i];
      const prev = i > 0 ? moves[i - 1] : null;
      const coords = `X=${n(mv.x)} Y=${n(mv.y)} Z=${n(mv.z, 3)}`;
      const helical = prev && isArc(mv) && Math.abs(mv.z - prev.z) > 1e-9;

      if (prev && isArc(mv) && !helical) {
        const word = mv.feed !== feed ? ` F=${mv.feed}` : "";
        if (mv.feed !== null) feed = mv.feed;
        lines.push(`${mv.cw ? "G2" : "G3"} ${coords} I=${n(mv.i!)} J=${n(mv.j!)}${word}`);
        continue;
      }
      if (prev && helical) {
        lines.push(c(`HELICAL ARC FLATTENED TO ${CHORD_TOLERANCE}IN CHORD — TURN= HELIX NOT IMPLEMENTED`));
        for (const seg of flattenArcs([prev, mv]).slice(1)) {
          const w = seg.feed !== feed ? ` F=${seg.feed}` : "";
          if (seg.feed !== null) feed = seg.feed;
          lines.push(`G1 X=${n(seg.x)} Y=${n(seg.y)} Z=${n(seg.z, 3)}${w}`);
        }
        continue;
      }
      if (mv.feed === null) lines.push(`G0 ${coords}`);
      else if (mv.feed !== feed) {
        feed = mv.feed;
        lines.push(`G1 ${coords} F=${mv.feed}`);
      } else lines.push(`G1 ${coords}`);
    }
    lines.push("M5");
  }
  lines.push("M30");
  return lines.join("\n");
};

/* ------------------------------------------------------------------ */
/* Registry                                                            */
/* ------------------------------------------------------------------ */

export const POSTS: PostDefinition[] = [
  { id: "haas-ngc-dev", name: "Haas NGC (development)", controllerFamily: "HAAS", certified: false, emit: emitFanucFamily("HAAS") },
  { id: "fanuc-dev", name: "Fanuc 0i/30i (development)", controllerFamily: "FANUC", certified: false, emit: emitFanucFamily("FANUC") },
  { id: "pathpilot-dev", name: "Tormach PathPilot (development)", controllerFamily: "PATHPILOT", certified: false, emit: emitFanucFamily("PATHPILOT") },
  { id: "siemens-840d-dev", name: "Siemens 840D (development)", controllerFamily: "SIEMENS", certified: false, emit: emitSiemens },
  { id: "heidenhain-dev", name: "Heidenhain TNC (development)", controllerFamily: "HEIDENHAIN", certified: false, emit: emitHeidenhain },
  { id: "grbl-dev", name: "GRBL (development)", controllerFamily: "GRBL", certified: false, emit: emitGrbl },
];

export function getPost(id: string): PostDefinition | undefined {
  return POSTS.find((p) => p.id === id);
}

export function defaultPostForController(controller: string): PostDefinition {
  const map: Record<string, string> = {
    HAAS_NGC: "haas-ngc-dev",
    HAAS_CLASSIC: "haas-ngc-dev",
    FANUC: "fanuc-dev",
    PATHPILOT: "pathpilot-dev",
    SIEMENS_840D: "siemens-840d-dev",
    HEIDENHAIN_TNC: "heidenhain-dev",
    GRBL: "grbl-dev",
  };
  return getPost(map[controller] ?? "fanuc-dev")!;
}

/* ------------------------------------------------------------------ */
/* NC verification — a cheap sanity pass over emitted code             */
/* ------------------------------------------------------------------ */

export interface NcVerificationIssue {
  severity: "ERROR" | "WARNING";
  line: number;
  message: string;
}

/**
 * This is a linter, not a verifier. It catches the categories of mistake that
 * are cheap to catch in text — missing units, motion below the part with no
 * spindle, travel outside the machine envelope. It does NOT verify collisions
 * or material removal, and the UI says so.
 */
/**
 * The verification issues that stop a program leaving CANVAS.
 *
 * NC VERIFICATION is a step in the export chain, not a report printed beside
 * it. It was the second: `verifyNc` ran at generation, the issues were stored
 * and displayed, and both the export button and the authorisation that
 * actually mints the file ignored them — so a program the checker had called
 * an ERROR on could be written to a stick and run.
 *
 * ERROR blocks. WARNING does not: the linter's warnings are judgement calls a
 * machinist is better placed to make than it is, and refusing on them would
 * teach people to route around the gate. An ERROR is a statement that the
 * program text is wrong — no units word, motion below the part with no feed,
 * a dialect this checker cannot read — and none of those are opinions.
 *
 * There is no confirmation that clears this. The evidence that clears it is a
 * program that verifies, which means fixing the program.
 */
export function ncVerificationBlockers(issues: NcVerificationIssue[]): NcVerificationIssue[] {
  return issues.filter((i) => i.severity === "ERROR");
}

export function verifyNc(nc: string, machine: MachineProfile): NcVerificationIssue[] {
  const issues: NcVerificationIssue[] = [];
  const lines = nc.split("\n");

  // This checker reads G-code. Heidenhain conversational is a different
  // language — BEGIN PGM ... INCH rather than G20, L X.. R0 F.. rather than
  // G1 X.. F.. — and every rule below misreads it. Run against a valid TNC
  // program it reported "No units word (G20/G21)" as an ERROR and, once the
  // feed checks were added, a second error saying no feed was ever commanded
  // when every L block carried one. Two false errors on a correct program.
  //
  // Saying so is the only defensible answer. A dialect this cannot parse must
  // not come back clean either, because clean is what an operator reads as
  // verified.
  if (/^\s*BEGIN PGM\b/m.test(nc)) {
    return [
      {
        severity: "WARNING",
        line: 1,
        message:
          "This is a Heidenhain conversational program. CANVAS's NC verification reads G-code and cannot check this dialect — travel envelope, spindle state and feed limits are all unverified here.",
      },
    ];
  }

  /*
   * Siemens 840D, for exactly the same reason.
   *
   * It looks like G-code and is not: axes are addressed `X=1.0` and tools are
   * called `T="T1"`. Every coordinate regex below misses `X=`, so the checker
   * saw no motion at all in an 840D program and returned CLEAN — verified,
   * having read nothing. That is the failure this file's header names, and it
   * survived because nothing exercised the honest-refusal path on the second
   * dialect that needs it.
   */
  if (/\bT\s*=\s*"/.test(nc) || /^\s*G\d+\s+X=/m.test(nc)) {
    return [
      {
        severity: "WARNING",
        line: 1,
        message:
          "This is a Siemens 840D program. CANVAS's NC verification reads Fanuc-family G-code and cannot check X= addressing — travel envelope, spindle state and feed limits are all unverified here.",
      },
    ];
  }

  let unitsSet = false;
  let spindleOn = false;
  let sawMotion = false;
  let sawFeedMotion = false;
  let spindleOnAtEnd = false;
  let feedEverSet = false;

  lines.forEach((raw, i) => {
    /*
     * Comments are stripped before anything is read out of a line.
     *
     * The header carries "PROGRAM ZERO: X0 Y0 AT THE CENTRE OF THE STOCK",
     * and the coordinate regexes below happily found an X and a Y in it — a
     * comment read as a motion block. On its own that is only noise; combined
     * with the feed check it turned a correct program into one reported as
     * "motion but no feed moves", which is an operator being told a cutting
     * pass runs at rapid.
     */
    const line = raw.replace(/\([^)]*\)/g, "").replace(/;.*$/, "").trim().toUpperCase();
    const ln = i + 1;
    if (/\bG20\b|\bG21\b|\bG70\b|\bG71\b/.test(line)) unitsSet = true;
    if (/\bM3\b|\bM4\b/.test(line)) { spindleOn = true; spindleOnAtEnd = true; }
    if (/\bM5\b/.test(line)) { spindleOn = false; spindleOnAtEnd = false; }

    const x = /X(-?\d+\.?\d*)/.exec(line);
    const y = /Y(-?\d+\.?\d*)/.exec(line);
    const z = /Z(-?\d+\.?\d*)/.exec(line);

    if (x || y || z) {
      sawMotion = true;
      // A cutting move is one with a feed rate. G0 is the machine moving as
      // fast as it can, and it does that in air.
      const cutting = /\bG0?1\b|\bG0?2\b|\bG0?3\b/.test(line);
      if (cutting || /\bF\d/.test(line)) sawFeedMotion = true;

      // An F word that is not a number reaches the control as a malformed
      // block. Depending on the control it is a fault or, worse, silently
      // ignored so the move runs at whatever feed was last modal. Either way
      // it is not the feed the CAM engine computed.
      const fWord = /\bF([^\s]*)/.exec(line);
      if (cutting && fWord && !/^\d+\.?\d*$/.test(fWord[1])) {
        issues.push({
          severity: "ERROR",
          line: ln,
          message: `Cutting move carries a malformed feed word "F${fWord[1]}". The control will either fault or fall back to the last modal feed.`,
        });
      }
      if (cutting) feedEverSet ||= Boolean(fWord) || feedEverSet;
      if (x && Math.abs(parseFloat(x[1])) > machine.travelsX / 2) {
        issues.push({ severity: "ERROR", line: ln, message: `X${x[1]} is outside the ±${(machine.travelsX / 2).toFixed(1)}" travel envelope` });
      }
      if (y && Math.abs(parseFloat(y[1])) > machine.travelsY / 2) {
        issues.push({ severity: "ERROR", line: ln, message: `Y${y[1]} is outside the ±${(machine.travelsY / 2).toFixed(1)}" travel envelope` });
      }
      if (z && parseFloat(z[1]) < -machine.travelsZ) {
        issues.push({ severity: "ERROR", line: ln, message: `Z${z[1]} exceeds ${machine.travelsZ}" of Z travel` });
      }
      if (z && parseFloat(z[1]) < 0 && !spindleOn && /G1|G2|G3/.test(line)) {
        issues.push({ severity: "ERROR", line: ln, message: "Cutting move below Z0 with the spindle off" });
      }
    }

    const f = /F(\d+\.?\d*)/.exec(line);
    if (f && parseFloat(f[1]) > machine.maxFeed) {
      issues.push({ severity: "WARNING", line: ln, message: `F${f[1]} exceeds the machine's ${machine.maxFeed} in/min maximum feed` });
    }
    const s = /\bS(\d+)/.exec(line);
    if (s && parseInt(s[1], 10) > machine.maxSpindleRPM) {
      issues.push({ severity: "ERROR", line: ln, message: `S${s[1]} exceeds the ${machine.maxSpindleRPM} RPM spindle maximum` });
    }
  });

  if (!unitsSet) issues.push({ severity: "ERROR", line: 1, message: "No units word (G20/G21) in the program" });
  if (!sawMotion) issues.push({ severity: "WARNING", line: 1, message: "Program contains no motion" });

  // A program that moves and never feeds is not cutting anything. Either it
  // does nothing, or — the reason this check exists — every cutting move has
  // been emitted as a rapid, which is the machine driving into the material
  // at full traverse. Nothing caught that: a post mutated to emit G0 for every
  // cutting move produced a program verifyNc passed with no errors at all.
  if (sawMotion && !sawFeedMotion) {
    issues.push({
      severity: "ERROR",
      line: 1,
      message:
        "Program contains motion but no feed moves — every move is a rapid. A cutting pass emitted as G0 drives into the material at traverse speed.",
    });
  }

  // Cutter compensation and a canned cycle left active by the PREVIOUS
  // program are still active when this one starts. The safe line cancels them.
  if (sawMotion && !/\bG40\b/.test(nc.toUpperCase())) {
    issues.push({
      severity: "WARNING",
      line: 1,
      message: "No G40 in the program — cutter compensation left on by whatever ran before this is still active.",
    });
  }
  if (sawFeedMotion && !feedEverSet) {
    issues.push({
      severity: "ERROR",
      line: 1,
      message: "Cutting moves are present but no feed rate is ever commanded — every pass would run at whatever feed the control had left over.",
    });
  }
  if (spindleOnAtEnd) {
    issues.push({ severity: "WARNING", line: lines.length, message: "Program ends with the spindle still commanded on." });
  }
  if (!/M30|M2\b/.test(nc.toUpperCase())) {
    issues.push({ severity: "WARNING", line: lines.length, message: "Program has no end-of-program code" });
  }

  return issues;
}

/* ------------------------------------------------------------------ */
/* Pre-flight gate                                                     */
/* ------------------------------------------------------------------ */

export interface PreflightItem {
  id: string;
  label: string;
  status: "PASS" | "FAIL" | "PENDING";
  detail: string;
  /** A failing required item disables export outright. */
  required: boolean;
}

export function preflightPassed(items: PreflightItem[]): boolean {
  return items.filter((i) => i.required).every((i) => i.status === "PASS");
}

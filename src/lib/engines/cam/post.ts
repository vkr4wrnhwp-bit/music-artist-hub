import type { Move, Toolpath } from "./types";
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

      if (tp.type === "TAP") {
        // Rigid tap as a canned cycle. G84 owns the spindle — no M3, and the
        // feed is pitch × rpm exactly as the engine locked it. Emitting these
        // moves as G1 lines instead would strip the spindle synchronisation
        // and break the tap, which is why the generic path is not used here.
        const finalZ = Math.min(...tp.moves.map((m) => m.z));
        const rPlane = tp.moves[0]?.z ?? ctx.safeZ;
        lines.push(c(`RIGID TAP — F ${tp.parameters.feed.toFixed(2)} = ${tp.parameters.rpm} RPM x pitch`));
        lines.push(`${ctx.workOffset} G0 X${n(tp.moves[0]?.x ?? 0)} Y${n(tp.moves[0]?.y ?? 0)}`);
        lines.push(`G43 H${entry?.lengthOffset ?? tp.toolNumber} Z${n(ctx.safeZ, 3)}`);
        if (tp.parameters.coolant !== "OFF") lines.push("M8");
        lines.push(`S${tp.parameters.rpm}`);
        lines.push(`G84 Z${n(finalZ, 3)} R${n(rPlane, 3)} F${tp.parameters.feed.toFixed(2)}`);
        lines.push("G80");
        lines.push("M9");
        lines.push("G53 G0 Z0.");
        continue;
      }

      lines.push(`S${tp.parameters.rpm} M3`);
      lines.push(`${ctx.workOffset} G0 X${n(tp.moves[0]?.x ?? 0)} Y${n(tp.moves[0]?.y ?? 0)}`);
      lines.push(`G43 H${entry?.lengthOffset ?? tp.toolNumber} Z${n(ctx.safeZ, 3)}`);
      if (tp.parameters.coolant !== "OFF") {
        lines.push(dialect === "HAAS" && tp.parameters.coolant === "THROUGH_SPINDLE" ? "M88" : "M8");
      }
      currentFeed = -1;

      for (const mv of tp.moves) {
        lines.push(moveLine(mv, currentFeed, (f) => (currentFeed = f)));
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

function moveLine(mv: Move, currentFeed: number, setFeed: (f: number) => void): string {
  const coords = `X${n(mv.x)} Y${n(mv.y)} Z${n(mv.z, 3)}`;
  if (mv.feed === null) return `G0 ${coords}`;
  if (mv.feed !== currentFeed) {
    setFeed(mv.feed);
    return `G1 ${coords} F${mv.feed}.`;
  }
  return `G1 ${coords}`;
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
    lines.push("");
    lines.push(c(`${tp.type} — T${tp.toolNumber}`));
    lines.push("M5");
    lines.push(c("MANUAL TOOL CHANGE REQUIRED — GRBL HAS NO ATC"));
    lines.push("M0");
    lines.push(`S${tp.parameters.rpm} M3`);
    let feed = -1;
    for (const mv of tp.moves) lines.push(moveLine(mv, feed, (f) => (feed = f)));
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
    push(`TOOL CALL ${tp.toolNumber} Z S${tp.parameters.rpm}`);
    push(`L Z+${n(ctx.safeZ, 3)} R0 FMAX M3`);
    for (const mv of tp.moves) {
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
    lines.push("");
    lines.push(c(`${tp.type}`));
    lines.push(`T="T${tp.toolNumber}" M6`);
    lines.push(`S${tp.parameters.rpm} M3`);
    lines.push("D1");
    let feed = -1;
    for (const mv of tp.moves) {
      const coords = `X=${n(mv.x)} Y=${n(mv.y)} Z=${n(mv.z, 3)}`;
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

  let unitsSet = false;
  let spindleOn = false;
  let sawMotion = false;
  let sawFeedMotion = false;
  let spindleOnAtEnd = false;
  let feedEverSet = false;

  lines.forEach((raw, i) => {
    const line = raw.trim().toUpperCase();
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

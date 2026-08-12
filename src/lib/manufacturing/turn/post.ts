import type { TurnToolpath } from "./operations";

/**
 * DEVELOPMENT LATHE POST — generic Haas/Fanuc-style 2-axis turning.
 *
 * G18 plane, G20 inches, T0101-style calls, G96/G97 with a G50 clamp when
 * CSS is used. Feeds emit G99 (per-rev). No canned cycles, no threading
 * cycles (thread passes emit as G32-style feed-synchronous moves), no nose
 * radius compensation. The header says DEVELOPMENT — NOT FOR PRODUCTION USE
 * because that is what it is; the honest label is the feature.
 */

export interface LathePostContext {
  programNumber: string;
  partName: string;
  machine: string;
  workOffset: string;
  /** G50 spindle clamp, RPM — REQUIRED when any operation runs CSS. */
  maxRpmClamp: number | null;
  generatedAtIso: string;
}

export interface LatheOpForPost {
  toolpath: TurnToolpath;
  station: string; // "0101"
  description: string;
  cssEnabled: boolean;
  surfaceSpeed: number | null;
  rpm: number;
  coolant: boolean;
}

export function emitLatheProgram(ops: LatheOpForPost[], ctx: LathePostContext): { code: string; refusals: string[] } {
  const refusals: string[] = [];
  const cssUsed = ops.some((o) => o.cssEnabled);
  if (cssUsed && ctx.maxRpmClamp === null) {
    refusals.push("CSS is programmed and no G50 maximum-RPM clamp was provided. An unclamped G96 winds the spindle to its limit as X approaches zero. Refusing to emit.");
    return { code: "", refusals };
  }

  const L: string[] = [];
  L.push("%");
  L.push(`O${ctx.programNumber}`);
  L.push(`(${ctx.partName.toUpperCase().slice(0, 30)})`);
  L.push(`(CANVAS DEVELOPMENT LATHE POST - NOT FOR PRODUCTION USE)`);
  L.push(`(MACHINE: ${ctx.machine})`);
  L.push(`(GENERATED ${ctx.generatedAtIso})`);
  L.push("(VERIFY EVERY LINE. DRY RUN. CONFIRM OFFSETS AT THE MACHINE.)");
  L.push("G18 G20 G40 G80 G99");
  L.push(`${ctx.workOffset}`);
  if (ctx.maxRpmClamp !== null) L.push(`G50 S${Math.round(ctx.maxRpmClamp)}`);

  for (const op of ops) {
    L.push(`(${op.description.toUpperCase().slice(0, 40)})`);
    L.push(`T${op.station}`);
    if (op.cssEnabled && op.surfaceSpeed !== null) {
      L.push(`G96 S${Math.round(op.surfaceSpeed)} M3`);
    } else {
      L.push(`G97 S${Math.round(op.rpm)} M3`);
    }
    if (op.coolant) L.push("M8");
    for (const m of op.toolpath.moves) {
      const x = `X${m.x.toFixed(4)}`;
      const z = `Z${m.z.toFixed(4)}`;
      if (m.kind === "RAPID") L.push(`G0 ${x} ${z}`);
      else if (m.kind === "THREAD_PASS") L.push(`G32 ${x} ${z} F${m.feedPerRev!.toFixed(4)}`);
      else L.push(`G1 ${x} ${z} F${m.feedPerRev!.toFixed(4)}`);
    }
    if (op.coolant) L.push("M9");
    L.push("G0 X6.0 Z2.0 (CLEAR)");
    L.push("M5");
  }
  L.push("M30");
  L.push("%");
  return { code: L.join("\n"), refusals };
}

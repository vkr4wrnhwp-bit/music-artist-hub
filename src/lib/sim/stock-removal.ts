import type { Move } from "@/lib/engines/cam/types";

/**
 * STOCK REMOVAL SIMULATION — deterministic geometric core
 *
 * Every CANVAS toolpath is 2.5D: the tool enters from +Z and the machined
 * state of any XY point is fully described by one number, the surviving top
 * height. So the stock is a height field — exact for this geometry class,
 * not an approximation of it — and removal is `h = min(h, toolTipZ)` under
 * the tool's footprint. No voxel soup, no CSG library, and nothing here
 * imports three.js or react: this file is arithmetic, and it is tested.
 *
 * What this is: GEOMETRIC simulation. Material disappears where the tool
 * sweeps; rapids that would enter surviving material are flagged; a cut
 * deeper than the flute length flags holder/shank contact. All of it is
 * geometry against the real Move[] data.
 *
 * What this is NOT, and never claims: physics. No cutting forces, no
 * deflection, no chatter, no thermal anything. The UI labels it
 * MATERIAL REMOVAL — GEOMETRIC SIMULATION for exactly this reason, and the
 * Simulation record it produces sets verifiedStockRemoval/collisionChecked
 * true only in the geometric sense defined here.
 *
 * Known geometric approximations, stated:
 * - Every cutter is treated as flat-bottomed at its nominal diameter. A
 *   drill's point and a chamfer mill's cone remove slightly less than the
 *   cylinder assumed here, so removal errs on the side of over-removal.
 * - The fixture is not modelled in the CUT view yet; collision checks cover
 *   stock and holder-vs-stock only. Vise collision belongs to the HOLD
 *   geometry integration and is listed as unchecked in the result.
 */

export interface SimOperation {
  operationId: string;
  label: string;
  toolNumber: number;
  /** Nominal cutter diameter, inches. */
  toolDiameter: number;
  /** Flute length — cutting depth available before the shank/holder rubs. */
  fluteLength: number;
  rpm: number;
  moves: Move[];
}

export interface SimSegment {
  opIndex: number;
  x0: number; y0: number; z0: number;
  x1: number; y1: number; z1: number;
  /** in/min. Rapids use the machine rapid rate. */
  feed: number;
  rapid: boolean;
  /** Cumulative time at segment start/end, minutes. */
  t0: number;
  t1: number;
}

export interface CollisionEvent {
  time: number;
  opIndex: number;
  x: number; y: number; z: number;
  kind: "RAPID_INTO_STOCK" | "HOLDER_CONTACT";
  detail: string;
}

export interface SimMetrics {
  time: number;
  totalTime: number;
  opIndex: number;
  position: { x: number; y: number; z: number };
  feed: number;
  rapid: boolean;
  rpm: number;
  toolNumber: number;
  removedVolume: number;
  totalRemovedVolume: number;
}

export interface StockDims { x: number; y: number; z: number }

/* ------------------------------------------------------------------ */
/* Height field                                                        */
/* ------------------------------------------------------------------ */

export class HeightField {
  readonly nx: number;
  readonly ny: number;
  readonly cell: number;
  /** Surviving top height per cell, from z=0 at the stock bottom. */
  readonly data: Float32Array;
  removedVolume = 0;

  constructor(readonly stock: StockDims, targetCells = 200) {
    this.cell = Math.max(stock.x, stock.y) / targetCells;
    this.nx = Math.max(2, Math.round(stock.x / this.cell));
    this.ny = Math.max(2, Math.round(stock.y / this.cell));
    this.data = new Float32Array(this.nx * this.ny).fill(stock.z);
  }

  /** Stock height at part-frame coordinates (origin at stock centre). */
  heightAt(x: number, y: number): number {
    const i = Math.floor((x + this.stock.x / 2) / this.cell);
    const j = Math.floor((y + this.stock.y / 2) / this.cell);
    if (i < 0 || j < 0 || i >= this.nx || j >= this.ny) return 0;
    return this.data[j * this.nx + i];
  }

  /** Flat-bottom cut: clamp heights under the tool footprint to tipZ. */
  cut(x: number, y: number, tipZ: number, radius: number): void {
    const zClamped = Math.max(0, tipZ);
    const i0 = Math.max(0, Math.floor((x - radius + this.stock.x / 2) / this.cell));
    const i1 = Math.min(this.nx - 1, Math.ceil((x + radius + this.stock.x / 2) / this.cell));
    const j0 = Math.max(0, Math.floor((y - radius + this.stock.y / 2) / this.cell));
    const j1 = Math.min(this.ny - 1, Math.ceil((y + radius + this.stock.y / 2) / this.cell));
    const r2 = radius * radius;
    const cellArea = this.cell * this.cell;
    for (let j = j0; j <= j1; j++) {
      const cy = (j + 0.5) * this.cell - this.stock.y / 2;
      for (let i = i0; i <= i1; i++) {
        const cx = (i + 0.5) * this.cell - this.stock.x / 2;
        const dx = cx - x;
        const dy = cy - y;
        if (dx * dx + dy * dy > r2) continue;
        const idx = j * this.nx + i;
        const h = this.data[idx];
        if (h > zClamped) {
          this.removedVolume += (h - zClamped) * cellArea;
          this.data[idx] = zClamped;
        }
      }
    }
  }

  snapshot(): { data: Float32Array; removedVolume: number } {
    return { data: this.data.slice(), removedVolume: this.removedVolume };
  }

  restore(s: { data: Float32Array; removedVolume: number }): void {
    this.data.set(s.data);
    this.removedVolume = s.removedVolume;
  }
}

/* ------------------------------------------------------------------ */
/* Timeline                                                            */
/* ------------------------------------------------------------------ */

export function buildTimeline(ops: SimOperation[], rapidRate: number): { segments: SimSegment[]; opStartTimes: number[]; totalTime: number } {
  const segments: SimSegment[] = [];
  const opStartTimes: number[] = [];
  let t = 0;
  ops.forEach((op, opIndex) => {
    opStartTimes.push(t);
    for (let i = 1; i < op.moves.length; i++) {
      const a = op.moves[i - 1];
      const b = op.moves[i];
      const dist = Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
      if (dist === 0) continue;
      const rapid = b.feed === null;
      const feed = rapid ? rapidRate : Math.max(1, b.feed!);
      const dt = dist / feed;
      segments.push({ opIndex, x0: a.x, y0: a.y, z0: a.z, x1: b.x, y1: b.y, z1: b.z, feed, rapid, t0: t, t1: t + dt });
      t += dt;
    }
  });
  return { segments, opStartTimes, totalTime: t };
}

/* ------------------------------------------------------------------ */
/* Simulator                                                           */
/* ------------------------------------------------------------------ */

export class StockRemovalSimulator {
  readonly field: HeightField;
  readonly segments: SimSegment[];
  readonly opStartTimes: number[];
  readonly totalTime: number;
  /** All collisions, discovered by the construction-time full pass, so the
   *  timeline can mark them before playback ever reaches them. */
  readonly collisions: CollisionEvent[] = [];
  readonly totalRemovedVolume: number;

  private time = 0;
  private segCursor = 0;
  private opSnapshots: ({ data: Float32Array; removedVolume: number } | null)[];

  constructor(
    readonly stock: StockDims,
    readonly ops: SimOperation[],
    rapidRate = 600,
    targetCells = 200,
  ) {
    this.field = new HeightField(stock, targetCells);
    const tl = buildTimeline(ops, rapidRate);
    this.segments = tl.segments;
    this.opStartTimes = tl.opStartTimes;
    this.totalTime = tl.totalTime;
    this.opSnapshots = ops.map(() => null);

    // Full deterministic pass: records every collision, every op-start
    // snapshot, and the total removed volume. Scrubbing then never has to
    // guess — seeking restores the nearest earlier snapshot and re-runs
    // forward, which reproduces this pass exactly.
    this.opSnapshots[0] = this.field.snapshot();
    this.runSegments(0, this.segments.length, true);
    this.totalRemovedVolume = this.field.removedVolume;
    // Reset to t=0 for playback.
    this.field.restore(this.opSnapshots[0]!);
    this.time = 0;
    this.segCursor = 0;
  }

  /** Advance or scrub to absolute time t (minutes). Deterministic. */
  seek(t: number): void {
    const target = Math.min(Math.max(0, t), this.totalTime);
    if (target < this.time) {
      // Backward: restore the latest op snapshot at or before the target.
      let opIdx = 0;
      for (let i = 0; i < this.opStartTimes.length; i++) {
        if (this.opStartTimes[i] <= target && this.opSnapshots[i]) opIdx = i;
      }
      this.field.restore(this.opSnapshots[opIdx]!);
      this.time = this.opStartTimes[opIdx];
      this.segCursor = this.segments.findIndex((s) => s.t1 > this.time + 1e-12);
      if (this.segCursor < 0) this.segCursor = this.segments.length;
    }
    this.advanceTo(target);
  }

  private advanceTo(target: number): void {
    while (this.segCursor < this.segments.length && this.segments[this.segCursor].t0 < target) {
      const seg = this.segments[this.segCursor];
      const end = Math.min(seg.t1, target);
      this.applySegment(seg, this.time > seg.t0 ? this.time : seg.t0, end, false);
      this.time = end;
      if (end >= seg.t1 - 1e-12) this.segCursor++;
      else break;
    }
    this.time = target;
  }

  private recordedRapidSegments = new Set<number>();
  private recordedHolderOps = new Set<number>();

  private runSegments(from: number, to: number, recording: boolean): void {
    for (let s = from; s < to; s++) {
      const seg = this.segments[s];
      // Snapshot at each operation boundary during the recording pass.
      if (recording) {
        const opStart = this.opStartTimes[seg.opIndex];
        if (Math.abs(seg.t0 - opStart) < 1e-12 && !this.opSnapshots[seg.opIndex]) {
          this.opSnapshots[seg.opIndex] = this.field.snapshot();
        }
      }
      this.applySegment(seg, seg.t0, seg.t1, recording, s);
    }
  }

  private applySegment(seg: SimSegment, tFrom: number, tTo: number, recording: boolean, segIndex = -1): void {
    const op = this.ops[seg.opIndex];
    const radius = op.toolDiameter / 2;
    const dt = seg.t1 - seg.t0;
    if (dt <= 0) return;
    const f0 = (tFrom - seg.t0) / dt;
    const f1 = (tTo - seg.t0) / dt;
    const len = Math.hypot(seg.x1 - seg.x0, seg.y1 - seg.y0, seg.z1 - seg.z0);
    const steps = Math.max(1, Math.ceil((len * (f1 - f0)) / (this.field.cell * 0.5)));

    for (let k = 0; k <= steps; k++) {
      const f = f0 + ((f1 - f0) * k) / steps;
      const x = seg.x0 + (seg.x1 - seg.x0) * f;
      const y = seg.y0 + (seg.y1 - seg.y0) * f;
      const z = seg.z0 + (seg.z1 - seg.z0) * f;
      // Part frame: moves use z=0 at the part top; the field measures from
      // the stock bottom.
      const tipH = z + this.stock.z;

      if (seg.rapid) {
        // A rapid never cuts. If it would pass through surviving material,
        // that is a crash, and it is recorded — once per segment.
        if (recording && !this.recordedRapidSegments.has(segIndex) && this.field.heightAt(x, y) > tipH + 1e-6) {
          this.recordedRapidSegments.add(segIndex);
          this.collisions.push({
            time: seg.t0 + (seg.t1 - seg.t0) * f,
            opIndex: seg.opIndex,
            x, y, z,
            kind: "RAPID_INTO_STOCK",
            detail: `Rapid at Z${z.toFixed(3)} passes through material standing ${(this.field.heightAt(x, y) - this.stock.z - z).toFixed(3)}" above it in ${op.label}.`,
          });
        }
        continue;
      }

      // Holder/shank check: the wall that rubs is the standing material just
      // OUTSIDE the cut radius — the centre has already been cut to the tip.
      // Sample a ring one cell beyond the cutter edge.
      if (recording && op.fluteLength > 0 && !this.recordedHolderOps.has(seg.opIndex)) {
        const ringR = radius + this.field.cell;
        let wall = 0;
        for (let a = 0; a < 8; a++) {
          const ang = (a / 8) * Math.PI * 2;
          wall = Math.max(wall, this.field.heightAt(x + ringR * Math.cos(ang), y + ringR * Math.sin(ang)));
        }
        if (wall - tipH > op.fluteLength + 1e-6) {
          this.recordedHolderOps.add(seg.opIndex);
          this.collisions.push({
            time: seg.t0 + (seg.t1 - seg.t0) * f,
            opIndex: seg.opIndex,
            x, y, z,
            kind: "HOLDER_CONTACT",
            detail: `The wall beside the cut stands ${(wall - tipH).toFixed(3)}" above the tip against a ${op.fluteLength.toFixed(3)}" flute length in ${op.label} — the shank or holder contacts it.`,
          });
        }
      }

      this.field.cut(x, y, tipH, radius);
    }
  }

  metricsAt(t: number): SimMetrics {
    const seg =
      this.segments.find((s) => t >= s.t0 && t < s.t1) ??
      this.segments[this.segments.length - 1] ?? null;
    const opIndex = seg?.opIndex ?? 0;
    const op = this.ops[opIndex];
    let position = { x: 0, y: 0, z: 0 };
    let feed = 0;
    let rapid = false;
    if (seg) {
      const f = seg.t1 > seg.t0 ? Math.min(1, Math.max(0, (t - seg.t0) / (seg.t1 - seg.t0))) : 1;
      position = {
        x: seg.x0 + (seg.x1 - seg.x0) * f,
        y: seg.y0 + (seg.y1 - seg.y0) * f,
        z: seg.z0 + (seg.z1 - seg.z0) * f,
      };
      feed = seg.feed;
      rapid = seg.rapid;
    }
    return {
      time: t,
      totalTime: this.totalTime,
      opIndex,
      position,
      feed,
      rapid,
      rpm: op?.rpm ?? 0,
      toolNumber: op?.toolNumber ?? 0,
      removedVolume: this.field.removedVolume,
      totalRemovedVolume: this.totalRemovedVolume,
    };
  }

  get currentTime(): number {
    return this.time;
  }
}

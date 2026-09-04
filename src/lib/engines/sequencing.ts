/**
 * OPERATION SEQUENCING — fewer tool changes, without reordering anything that
 * must not move.
 *
 * The setups page carried a "Reduce tool changes" button labelled Not
 * implemented. This is the engine behind it. There is no model call anywhere
 * in this file and there must not be one: reordering machine operations is
 * exactly the kind of decision principle 6 keeps away from an LLM.
 *
 * WHAT IT WILL AND WILL NOT MOVE
 *
 * A tool change costs a few seconds and a small risk each time, and a setup
 * that alternates tools for no reason is worth fixing. But an operation
 * order is not a list to be sorted — it is a sequence with real dependencies,
 * and a "helpful" reorder that puts a finish pass before roughing, or taps a
 * hole nobody drilled, is worse than the wasted seconds by every measure.
 *
 * So the rules below are deliberately conservative. Two operations may swap
 * only when nothing in the model says they must not, and where the model is
 * silent about a genuine machining concern, the engine does not move them and
 * says which concern it could not reason about.
 *
 * WHAT IT DOES NOT KNOW
 *
 * Thermal growth across a long cycle, thin-wall deflection as material comes
 * off, chip evacuation, and whether a mid-setup order change alters how the
 * part is supported. None of that is in the model. The proposal names these
 * as limitations rather than implying they were considered.
 *
 * And the search is greedy, not exhaustive. Minimising tool changes over a
 * precedence DAG is NP-hard in general; this takes the obvious pass and
 * reports what it found. It never claims to have found the minimum.
 */

import type { OperationType } from "./cam/types";

export interface SequencedOperation {
  id: string;
  sequence: number;
  type: string;
  label: string;
  featureId: string | null;
  featureLabel: string | null;
  /** Null when no tool is assigned — such an operation is never moved. */
  toolNumber: number | null;
}

export interface PrecedenceEdge {
  beforeId: string;
  afterId: string;
  /** Machinist-readable reason this ordering is fixed. */
  rule: string;
}

export interface SequenceProposal {
  currentOrder: string[];
  proposedOrder: string[];
  currentToolChanges: number;
  proposedToolChanges: number;
  /** Tool changes removed. Zero when nothing can be improved. */
  saved: number;
  edges: PrecedenceEdge[];
  /**
   * Precedence rules the CURRENT order already breaks.
   *
   * This engine was built to save tool changes, and the first thing it did
   * on real data was compute a full precedence graph and then say nothing
   * when the existing plan violated it. An engine that knows a setup
   * profiles the part before it pockets it, and stays quiet because there
   * were no seconds to save, is withholding the more serious finding.
   *
   * A violation is always worth reporting, and always worth reordering for,
   * even when the tool-change count does not move.
   */
  violations: PrecedenceEdge[];
  /** Present when `saved` is 0 — why no reduction is available. */
  reason: string | null;
  method: string;
  limitations: string[];
}

/**
 * Order of operations on ONE feature. A hole is spotted, then drilled, then
 * bored or tapped; a pocket is roughed before it is bored; edges are broken
 * last. Lower runs first, and two operations at the same rank keep the order
 * the planner already gave them.
 */
export const FEATURE_STAGE: Record<OperationType, number> = {
  // Cutting the soft jaws happens before the part is in them, so it precedes
  // everything. It was absent from this table and fell through to the `?? 1`
  // default, which sequenced jaw-cutting alongside part roughing. Typing the
  // table by OperationType means the compiler asks for a stage the day an
  // operation type is added — this was found by sweeping for the same
  // hand-kept-table pattern that had bitten next-action.ts.
  SOFT_JAW_POCKET: -1,
  FACE: 0,
  POCKET_2D: 1,
  ADAPTIVE_2D: 1,
  SLOT_MILL: 1,
  DRILL: 2,
  PECK_DRILL: 3,
  // A head goes on a hole that already exists and before it is threaded: a
  // counterbore cut after tapping cuts the top of the thread off, and a
  // countersink after it raises a burr into the finished form.
  COUNTERBORE: 4,
  COUNTERSINK: 4,
  BORE: 4,
  // A thread is cut at the same stage however it is cut: after the hole and
  // the head, before the edges are broken.
  TAP: 5,
  THREAD_MILL: 5,
  ENGRAVE: 6,
  CHAMFER: 7,
  CONTOUR_2D: 8,
};

const stage = (type: string): number =>
  type in FEATURE_STAGE ? FEATURE_STAGE[type as OperationType] : 1;

export const SEQUENCING_METHOD =
  "Precedence graph over the setup's operations, then a greedy topological pass that keeps the tool in the spindle wherever the graph allows it.";

export const SEQUENCING_LIMITATIONS = [
  "Greedy, not exhaustive. Minimising tool changes over a precedence graph is NP-hard; this reports what one pass found, never a proven minimum.",
  "Thermal growth over a long cycle is not modelled.",
  "Thin-wall deflection as material comes off is not modelled — if a wall gets thin partway through, order matters and CANVAS cannot see it.",
  "Chip evacuation and coolant reach are not modelled.",
  "Toolpaths are not regenerated. The cutting is identical; only the order changes, so the posted program must be re-verified before it runs.",
];

/** Tool changes in a given order. A null tool never counts as a change. */
export function countToolChanges(order: SequencedOperation[]): number {
  let changes = 0;
  let inSpindle: number | null = null;
  let started = false;
  for (const op of order) {
    if (op.toolNumber === null) continue;
    if (started && op.toolNumber !== inSpindle) changes += 1;
    inSpindle = op.toolNumber;
    started = true;
  }
  return changes;
}

/**
 * The constraints that fix an order. Every edge carries the reason, so the
 * UI can show why an operation would not move rather than asserting it.
 */
export function precedenceEdges(ops: SequencedOperation[]): PrecedenceEdge[] {
  const edges: PrecedenceEdge[] = [];
  const byIndex = [...ops].sort((a, b) => a.sequence - b.sequence);

  const faces = byIndex.filter((o) => o.type === "FACE");
  const contours = byIndex.filter((o) => o.type === "CONTOUR_2D");
  const jawCuts = byIndex.filter((o) => o.type === "SOFT_JAW_POCKET");

  for (const op of byIndex) {
    // Cutting the soft jaws comes before everything, including facing.
    //
    // The facing rule below said nothing moves ahead of the datum cut, and
    // that is right for every operation on the PART — but a soft jaw pocket
    // is cut into the jaws, not the part. The part cannot be faced until it
    // is held, and it is held by the jaws that have not been cut yet. The
    // sequencer was ordering face, rough, then cut the jaws.
    for (const j of jawCuts) {
      if (j.id !== op.id) {
        edges.push({
          beforeId: j.id,
          afterId: op.id,
          rule: "The soft jaws are cut before the part is held in them",
        });
      }
    }
    // Facing establishes the Z datum every later depth is cut to. Nothing on
    // the part moves ahead of it.
    if (op.type !== "SOFT_JAW_POCKET") {
      for (const f of faces) {
        if (f.id !== op.id) {
          edges.push({ beforeId: f.id, afterId: op.id, rule: "Facing sets the Z datum every later depth is cut from" });
        }
      }
    }
    // The part is held by its own stock until the profile is cut. Profiling
    // early changes what is holding the part for everything after it.
    for (const c of contours) {
      if (c.id !== op.id && op.type !== "SOFT_JAW_POCKET") {
        edges.push({
          beforeId: op.id,
          afterId: c.id,
          rule: "The part is held by its stock until the outside profile is cut",
        });
      }
    }
    // An operation with no tool assigned is not something to reason about
    // moving — pin it where the planner put it.
    if (op.toolNumber === null) {
      for (const other of byIndex) {
        if (other.id === op.id) continue;
        if (other.sequence < op.sequence) edges.push({ beforeId: other.id, afterId: op.id, rule: "No tool is assigned to this operation, so it is left where the plan put it" });
        else edges.push({ beforeId: op.id, afterId: other.id, rule: "No tool is assigned to this operation, so it is left where the plan put it" });
      }
    }
  }

  // Same feature: stage order, and ties keep their planned order.
  for (const a of byIndex) {
    for (const b of byIndex) {
      if (a.id === b.id) continue;
      if (!a.featureId || a.featureId !== b.featureId) continue;
      const sa = stage(a.type);
      const sb = stage(b.type);
      if (sa < sb) {
        edges.push({
          beforeId: a.id,
          afterId: b.id,
          rule: `On one feature, ${a.type.replace(/_/g, " ").toLowerCase()} comes before ${b.type.replace(/_/g, " ").toLowerCase()}`,
        });
      } else if (sa === sb && a.sequence < b.sequence) {
        edges.push({ beforeId: a.id, afterId: b.id, rule: "Same feature and same stage — the planned order is kept" });
      }
    }
  }

  // De-duplicate; the same pair can be constrained by more than one rule and
  // the first reason is the one worth showing.
  const seen = new Set<string>();
  return edges.filter((e) => {
    if (e.beforeId === e.afterId) return false;
    const k = `${e.beforeId}>${e.afterId}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

/**
 * Greedy topological order: among the operations whose prerequisites are all
 * placed, prefer one already using the tool in the spindle; otherwise take
 * the earliest in the planned order so the result stays recognisable.
 */
function greedyOrder(ops: SequencedOperation[], edges: PrecedenceEdge[]): SequencedOperation[] {
  const byId = new Map(ops.map((o) => [o.id, o]));
  const indegree = new Map(ops.map((o) => [o.id, 0]));
  const after = new Map<string, string[]>();
  for (const e of edges) {
    if (!byId.has(e.beforeId) || !byId.has(e.afterId)) continue;
    indegree.set(e.afterId, (indegree.get(e.afterId) ?? 0) + 1);
    after.set(e.beforeId, [...(after.get(e.beforeId) ?? []), e.afterId]);
  }

  const out: SequencedOperation[] = [];
  const remaining = new Set(ops.map((o) => o.id));
  let inSpindle: number | null = null;

  while (remaining.size > 0) {
    const ready = [...remaining]
      .filter((id) => (indegree.get(id) ?? 0) === 0)
      .map((id) => byId.get(id)!)
      .sort((a, b) => a.sequence - b.sequence);

    // A cycle would mean the rules contradict each other. Rather than loop
    // for ever or silently drop work, fall back to the planned order — a
    // proposal that loses an operation is far worse than no proposal.
    if (ready.length === 0) return [...ops].sort((a, b) => a.sequence - b.sequence);

    const keepsTool: SequencedOperation | undefined =
      inSpindle === null ? undefined : ready.find((o) => o.toolNumber === inSpindle);
    const next: SequencedOperation = keepsTool ?? ready[0];

    out.push(next);
    remaining.delete(next.id);
    if (next.toolNumber !== null) inSpindle = next.toolNumber;
    for (const id of after.get(next.id) ?? []) indegree.set(id, (indegree.get(id) ?? 1) - 1);
  }

  return out;
}

export function proposeSequence(operations: SequencedOperation[]): SequenceProposal {
  const current = [...operations].sort((a, b) => a.sequence - b.sequence);
  const edges = precedenceEdges(current);
  const proposed = greedyOrder(current, edges);

  const currentToolChanges = countToolChanges(current);
  const proposedToolChanges = countToolChanges(proposed);
  const saved = Math.max(0, currentToolChanges - proposedToolChanges);

  // Rules the plan as written already breaks. Reported whether or not there
  // are any seconds to save — cutting something before the operation it
  // depends on is a bigger problem than a tool change.
  const position = new Map(current.map((o, i) => [o.id, i]));
  const violations = edges.filter((e) => {
    const a = position.get(e.beforeId);
    const b = position.get(e.afterId);
    return a !== undefined && b !== undefined && a > b;
  });

  // Never hand back an order that is not an improvement. A shuffle that saves
  // nothing is churn presented as advice — unless it fixes a violation, which
  // is a reason to reorder on its own.
  const keepCurrent = saved === 0 && violations.length === 0;

  let reason: string | null = null;
  if (keepCurrent) {
    const withTools = current.filter((o) => o.toolNumber !== null);
    const distinct = new Set(withTools.map((o) => o.toolNumber)).size;
    if (withTools.length === 0) {
      reason = "No operation in this setup has a tool assigned, so there are no tool changes to count.";
    } else if (distinct === withTools.length) {
      reason = `Every operation in this setup uses a different tool (${distinct} operations, ${distinct} tools), so ${currentToolChanges} ${currentToolChanges === 1 ? "change is" : "changes are"} already the minimum. Fewer changes would need fewer operations or a tool that does two jobs.`;
    } else if (currentToolChanges === distinct - 1) {
      reason = `The setup already groups its ${distinct} tools into ${distinct} runs, which is the fewest changes ${distinct} tools can be used in.`;
    } else {
      reason = "The precedence between these operations fixes their order — nothing can be regrouped without cutting something before the operation it depends on.";
    }
  }

  return {
    currentOrder: current.map((o) => o.id),
    proposedOrder: (keepCurrent ? current : proposed).map((o) => o.id),
    currentToolChanges,
    proposedToolChanges: keepCurrent ? currentToolChanges : proposedToolChanges,
    saved,
    edges,
    violations,
    reason,
    method: SEQUENCING_METHOD,
    limitations: SEQUENCING_LIMITATIONS,
  };
}

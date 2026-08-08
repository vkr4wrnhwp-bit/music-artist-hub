/**
 * RUN IT PAST CANVAS — pre-flight review
 *
 * The adoption story. A shop that already has CAM it trusts is not going to
 * throw it away, and asking them to is how this product gets ignored. What
 * they will do is run a job past a second opinion before pressing Cycle Start,
 * the same way they would ask the other machinist to look at a setup.
 *
 * So this produces a short, ranked list of things to check — each one tied to
 * a specific setup and operation, each one carrying the evidence behind it,
 * and each one pointing at geometry the viewport can show.
 *
 * WHAT THIS IS NOT
 *
 * It is not NC verification. There is no stock-removal simulation and no
 * collision engine behind it, so it cannot tell you the program is safe — only
 * that these particular things look wrong. A clean review means the checks
 * CANVAS knows how to make found nothing, which is a much smaller claim, and
 * the UI states it in those words.
 *
 * Every finding here comes from a deterministic engine or from arithmetic over
 * real toolpath moves. None of it is inferred by a model.
 */

import type { Move } from "./cam/types";
import type { MachineProfile, Tool, WorkholdingDevice } from "@/lib/domain/shop";
import { canReach } from "@/lib/domain/shop";
import type { WorkholdingAssessment } from "./workholding";
import type { CapabilityResult } from "./inspection-capability";

export const SEVERITIES = ["HIGH", "MEDIUM", "LOW"] as const;
export type Severity = (typeof SEVERITIES)[number];

const SEVERITY_ORDER: Record<Severity, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };

export interface FindingEvidence {
  label: string;
  value: string;
}

/** Where in the scene the finding is, so SHOW ME has something to point at. */
export interface FindingLocation {
  setupId: string | null;
  operationId: string | null;
  featureId: string | null;
  /** Point in part coordinates the camera should frame, when there is one. */
  point: { x: number; y: number; z: number } | null;
  /** Which view best explains it. */
  context: "PART" | "HOLD" | "CUT" | "VERIFY";
}

export interface ReviewFinding {
  id: string;
  severity: Severity;
  title: string;
  /** What is wrong, in a machinist's terms. */
  detail: string;
  /** What to do about it. */
  recommendation: string;
  location: FindingLocation;
  evidence: FindingEvidence[];
  /** Which engine produced it, so the finding can be argued with. */
  method: string;
}

export interface ReviewResult {
  findings: ReviewFinding[];
  highCount: number;
  mediumCount: number;
  lowCount: number;
  /** What CANVAS actually checked, so the absence of findings can be read correctly. */
  checksRun: string[];
  /** Checks it could not run, and why. */
  checksSkipped: { check: string; reason: string }[];
  headline: string;
}

export interface ReviewInput {
  setups: {
    id: string;
    name: string;
    sequence: number;
    gripDepth: number | null;
    stockProjection: number | null;
    operations: { id: string; label: string; toolId: string | null; finalZ: number; type: string }[];
  }[];
  workholdingBySetup: Record<string, WorkholdingAssessment>;
  device: WorkholdingDevice | null;
  machine: MachineProfile | null;
  tools: Tool[];
  /** Toolpath moves keyed by operation. */
  movesByOperation: Record<string, Move[]>;
  capability: CapabilityResult[];
  stockZ: number | null;
}

export function reviewPackage(input: ReviewInput): ReviewResult {
  const findings: ReviewFinding[] = [];
  const checksRun: string[] = [];
  const checksSkipped: { check: string; reason: string }[] = [];

  let n = 0;
  const id = () => `finding-${++n}`;

  /* ---------------- Holding margin ---------------- */

  checksRun.push("Holding margin against peak cutting load, per setup");
  for (const setup of input.setups) {
    const margin = input.workholdingBySetup[setup.id]?.holdingMargin;
    if (!margin) continue;
    if (margin.verdict === "ADEQUATE") continue;

    findings.push({
      id: id(),
      severity: margin.verdict === "INSUFFICIENT" ? "HIGH" : "MEDIUM",
      title: `Grip margin ${margin.verdict.toLowerCase()} in ${setup.name}`,
      detail:
        margin.primaryRisk ??
        `The setup does not reach the target holding margin of 2.00×; it comes out at ${margin.margin?.toFixed(2)}×.`,
      recommendation: margin.recommendations[0] ?? "Review the workholding for this setup.",
      location: {
        setupId: setup.id,
        operationId: null,
        featureId: null,
        point: null,
        context: "HOLD",
      },
      evidence: [
        { label: "Margin", value: `${margin.margin?.toFixed(2)}× against 2.00× target` },
        { label: "Governing mode", value: margin.governingMode === "TIPPING" ? "Rolling out of the jaws" : "Sliding in the jaws" },
        { label: "Applied at peak", value: `${margin.appliedLoad} lbf` },
        { label: "Resisting", value: `${margin.resistingForce} lbf` },
      ],
      method: margin.method,
    });
  }

  /* ---------------- Rapid clearance near the jaws ---------------- */

  // The classic way to wreck a vise: a rapid across the part at a Z that is
  // above the stock but below the top of the jaws. It clears the workpiece and
  // takes the jaw off. This is arithmetic over real toolpath moves, not a
  // simulation — it checks Z against the jaw height and nothing else.
  if (input.device && input.stockZ != null) {
    checksRun.push("Rapid moves below the top of the jaws");
    const jawTop = input.device.jawHeight;

    for (const setup of input.setups) {
      const grip = setup.gripDepth ?? 0;
      // Height of the jaw top above the bottom of the part.
      const jawTopInPart = jawTop - (jawTop - grip);
      for (const op of setup.operations) {
        const moves = input.movesByOperation[op.id] ?? [];

        // Only LATERAL rapids matter. Every drilling and plunging operation
        // rapids straight down to just above the feature it is about to cut —
        // that move is below the jaw top by design and is not dangerous,
        // because it is directly over the hole. What wrecks a vise is a rapid
        // that travels in XY while still down at jaw height. Flagging the
        // plunges as well produces a page of findings a machinist would
        // dismiss in ten seconds, which is worse than making no check at all.
        const LATERAL = 0.05;
        const offending = moves.filter((m, i) => {
          if (m.feed !== null || m.z >= jawTopInPart || m.z <= 0) return false;
          const prev = moves[i - 1];
          if (!prev) return false;
          return Math.hypot(m.x - prev.x, m.y - prev.y) > LATERAL;
        });
        if (offending.length === 0) continue;

        const lowest = offending.reduce((a, b) => (a.z < b.z ? a : b));
        findings.push({
          id: id(),
          severity: "HIGH",
          title: `Rapid clearance near vise jaw in ${setup.name}`,
          detail: `${offending.length} rapid ${offending.length === 1 ? "move travels" : "moves travel"} sideways below the top of the jaws during ${op.label}. A lateral rapid at that height clears the workpiece and does not clear the vise. Plunges straight down over a feature are excluded — those are normal.`,
          recommendation:
            "Raise the clearance plane above the jaw height, or confirm the rapid path stays outside the jaw footprint in XY.",
          location: {
            setupId: setup.id,
            operationId: op.id,
            featureId: null,
            point: { x: lowest.x, y: lowest.y, z: lowest.z },
            context: "CUT",
          },
          evidence: [
            { label: "Lowest rapid Z", value: `${lowest.z.toFixed(3)}"` },
            { label: "Jaw top", value: `${jawTopInPart.toFixed(3)}"` },
            { label: "Lateral rapids below jaw top", value: String(offending.length) },
          ],
          method: "Toolpath move inspection — lateral rapids below jaw height, no jaw footprint check",
        });
      }
    }
    checksSkipped.push({
      check: "Whether a flagged lateral rapid actually crosses the jaw",
      reason:
        "Needs the jaw footprint as geometry. A lateral rapid below jaw height is reported wherever it happens, so a move well clear of the vise will still be flagged.",
    });
  } else {
    checksSkipped.push({
      check: "Rapid clearance near the jaws",
      reason: "No workholding device assigned, so there is no jaw height to check against.",
    });
  }

  /* ---------------- Tool reach and holder collision ---------------- */

  checksRun.push("Tool reach and holder clearance at depth");
  for (const setup of input.setups) {
    for (const op of setup.operations) {
      const tool = input.tools.find((t) => t.id === op.toolId);
      if (!tool) continue;

      const depth = Math.abs(op.finalZ);
      if (depth <= 0) continue;

      if (!canReach(tool, depth)) {
        findings.push({
          id: id(),
          severity: "HIGH",
          title: `Tool cannot reach depth in ${op.label}`,
          detail: `T${tool.toolNumber} ${tool.description} has ${tool.fluteLength.toFixed(3)}" of flute and ${tool.stickout.toFixed(3)}" of stickout, against a ${depth.toFixed(3)}" cut depth.`,
          recommendation: "Use a longer-reach or necked tool, increase stickout, or split the cut across setups.",
          location: { setupId: setup.id, operationId: op.id, featureId: null, point: null, context: "CUT" },
          evidence: [
            { label: "Cut depth", value: `${depth.toFixed(3)}"` },
            { label: "Flute length", value: `${tool.fluteLength.toFixed(3)}"` },
            { label: "Stickout", value: `${tool.stickout.toFixed(3)}"` },
          ],
          method: "Tool geometry against operation depth",
        });
        continue;
      }

      // Holder clearance: the holder body arrives before the tool does if the
      // stickout is not longer than the depth it has to reach into.
      const clearance = tool.stickout - depth;
      if (clearance < 0.1 && clearance >= 0) {
        findings.push({
          id: id(),
          severity: "MEDIUM",
          title: `Tool reach close to holder collision in ${op.label}`,
          detail: `T${tool.toolNumber} leaves only ${clearance.toFixed(3)}" between the holder nose and the top of the cut. Any variation in stickout or work offset closes that.`,
          recommendation: `Set stickout to at least ${(depth + 0.15).toFixed(3)}" and re-measure the tool length offset.`,
          location: { setupId: setup.id, operationId: op.id, featureId: null, point: null, context: "CUT" },
          evidence: [
            { label: "Stickout", value: `${tool.stickout.toFixed(3)}"` },
            { label: "Depth reached", value: `${depth.toFixed(3)}"` },
            { label: "Clearance", value: `${clearance.toFixed(3)}"` },
            { label: "Holder nose ⌀", value: `${tool.holderNoseDiameter.toFixed(3)}"` },
          ],
          method: "Stickout against depth — holder body is not modelled as geometry",
        });
      }
    }
  }

  /* ---------------- Spindle power ---------------- */

  if (input.machine) {
    checksRun.push("Spindle power against the machine");
    for (const setup of input.setups) {
      const force = input.workholdingBySetup[setup.id]?.forceEstimate;
      if (!force?.ok || force.spindlePower == null) continue;
      const ratio = force.spindlePower / Math.max(input.machine.maxSpindlePower, 0.1);
      if (ratio < 0.8) continue;

      findings.push({
        id: id(),
        severity: ratio >= 1 ? "HIGH" : "MEDIUM",
        title: `Roughing pass draws ${(ratio * 100).toFixed(0)}% of spindle power in ${setup.name}`,
        detail:
          ratio >= 1
            ? `The estimated cut needs ${force.spindlePower} hp against ${input.machine.maxSpindlePower} hp available. The machine will bog or trip before it finishes the pass.`
            : `The estimated cut needs ${force.spindlePower} hp against ${input.machine.maxSpindlePower} hp available, leaving little headroom for a dull tool or a hard spot.`,
        recommendation: "Reduce radial engagement or axial depth on the roughing pass, or step the feed back.",
        location: { setupId: setup.id, operationId: null, featureId: null, point: null, context: "CUT" },
        evidence: [
          { label: "Estimated power", value: `${force.spindlePower} hp` },
          { label: "Machine rating", value: `${input.machine.maxSpindlePower} hp` },
          { label: "Uncertainty", value: `±${force.uncertaintyPercent}%` },
        ],
        method: force.method,
      });
    }
  } else {
    checksSkipped.push({ check: "Spindle power", reason: "No machine assigned to the setups." });
  }

  /* ---------------- Inspection capability ---------------- */

  checksRun.push("Whether every toleranced feature can be measured");
  for (const cap of input.capability) {
    if (cap.verdict !== "NOT_CAPABLE" && cap.verdict !== "NO_INSTRUMENT") continue;
    findings.push({
      id: id(),
      severity: "HIGH",
      title: `${cap.featureLabel} cannot be verified with the instruments on hand`,
      detail: cap.reason,
      recommendation: cap.recommendations[0] ?? "Acquire a more capable instrument or outsource the inspection.",
      location: { setupId: null, operationId: null, featureId: cap.featureId, point: null, context: "VERIFY" },
      evidence: [
        { label: "Tolerance band", value: cap.toleranceBand != null ? `${cap.toleranceBand.toFixed(4)}"` : "—" },
        {
          label: "Best instrument",
          value: cap.bestInstrument ? `${cap.bestInstrument.description} ±${cap.bestInstrument.uncertainty.toFixed(4)}"` : "none",
        },
        {
          label: "Band consumed",
          value: cap.consumedFraction != null ? `${(cap.consumedFraction * 100).toFixed(0)}%` : "—",
        },
      ],
      method: "Gauge maker's rule — ASME B89.7.3.1 decision-rule framing",
    });
  }

  /* ---------------- Things CANVAS cannot check ---------------- */

  checksSkipped.push(
    { check: "Stock removal and gouge detection", reason: "No material-removal simulation exists." },
    { check: "Fixture and clamp collision in XY", reason: "The fixture is a parametric approximation, not geometry." },
    { check: "Program syntax against the specific control", reason: "The post is a development post and is not certified." },
  );

  findings.sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);

  const high = findings.filter((f) => f.severity === "HIGH").length;
  const medium = findings.filter((f) => f.severity === "MEDIUM").length;
  const low = findings.filter((f) => f.severity === "LOW").length;

  const headline =
    findings.length === 0
      ? `Nothing found by the ${checksRun.length} checks CANVAS knows how to make. That is not the same as the program being safe — see what was not checked.`
      : `${findings.length} thing${findings.length === 1 ? "" : "s"} to check before cycle start.`;

  return { findings, highCount: high, mediumCount: medium, lowCount: low, checksRun, checksSkipped, headline };
}

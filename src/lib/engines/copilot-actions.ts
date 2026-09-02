import { CONTEXTS } from "@/lib/workspace-contexts";
import { validateFeatureParameters } from "@/lib/domain/feature-input";

/**
 * WHAT THE COPILOT IS ALLOWED TO DO BESIDES TALK
 *
 * The reply contract was `{reply, references, needs}` — text plus two string
 * lists — and the client rendered `references` as a comma-joined line. There
 * was no way for the copilot to select geometry, change what the workspace is
 * showing, or put a change in front of somebody.
 *
 * Two channels, split by what happens if the model is wrong:
 *
 *   SCENE ACTIONS change what is on screen and nothing else. Selecting a
 *   feature, switching context, focusing an operation — a wrong one wastes a
 *   click. These take effect immediately.
 *
 *   PROPOSALS change the part, so they do not take effect at all. They go into
 *   the AIRecommendation queue at PROPOSED and are accepted by a human on
 *   /proposals, which is the path AI suggestions already take. The copilot
 *   gets no second, softer route to the same data — principle 3: the model may
 *   suggest, and may not certify.
 *
 * Everything here is validated against the package the SERVER built. A model
 * can name any id it likes; an id that is not on this part is dropped rather
 * than handed to the client as something to click. That matters more once a
 * reference is actionable than it did when it was a caption.
 */

export const SCENE_ACTION_KINDS = ["SELECT_FEATURE", "SET_CONTEXT", "FOCUS_OPERATION"] as const;
export type SceneActionKind = (typeof SCENE_ACTION_KINDS)[number];

export interface SceneAction {
  kind: SceneActionKind;
  /** A feature id, an operation id, or a context name. */
  targetId: string;
  label: string;
}

/** What the copilot may propose. The same kinds /proposals already accepts. */
export const PROPOSAL_KINDS = ["FEATURE", "MEASUREMENT", "PROCESS", "WORKHOLDING", "NOMINAL"] as const;
export type ProposalKind = (typeof PROPOSAL_KINDS)[number];

export interface CopilotProposal {
  kind: ProposalKind;
  summary: string;
  payload: unknown;
}

export interface WorkspaceTargets {
  featureIds: string[];
  operationIds: string[];
}

export interface ValidatedActions {
  actions: SceneAction[];
  /** Actions dropped, and why — surfaced so a silent drop is not invisible. */
  rejected: { kind: string; targetId: string; reason: string }[];
}

/**
 * Keeps the scene actions that point at something real on this part.
 *
 * The label is the model's; the target is not taken on trust. A SELECT_FEATURE
 * naming a feature from another part, or one that was deleted between the
 * question and the answer, is dropped.
 */
export function validateSceneActions(raw: unknown[], targets: WorkspaceTargets): ValidatedActions {
  const actions: SceneAction[] = [];
  const rejected: ValidatedActions["rejected"] = [];
  const seen = new Set<string>();

  for (const item of raw) {
    if (item === null || typeof item !== "object") continue;
    const a = item as Record<string, unknown>;
    const kind = String(a.kind ?? "");
    const targetId = String(a.targetId ?? "");
    const label = String(a.label ?? "").trim().slice(0, 120);

    if (!(SCENE_ACTION_KINDS as readonly string[]).includes(kind)) {
      rejected.push({ kind, targetId, reason: "not an action the workspace has" });
      continue;
    }
    if (label === "") {
      rejected.push({ kind, targetId, reason: "no label, so nothing could be shown to press" });
      continue;
    }

    const ok =
      kind === "SELECT_FEATURE"
        ? targets.featureIds.includes(targetId)
        : kind === "FOCUS_OPERATION"
          ? targets.operationIds.includes(targetId)
          : (CONTEXTS as readonly string[]).includes(targetId);
    if (!ok) {
      rejected.push({
        kind,
        targetId,
        reason:
          kind === "SET_CONTEXT"
            ? "not a context the workspace has"
            : "not on this part — a model can name any id, and this one does not exist here",
      });
      continue;
    }

    const key = `${kind}:${targetId}`;
    if (seen.has(key)) continue;
    seen.add(key);
    actions.push({ kind: kind as SceneActionKind, targetId, label });
  }

  // A wall of buttons is not help. The copilot is answering a question, not
  // building a menu.
  return { actions: actions.slice(0, 6), rejected };
}

export interface ValidatedProposals {
  proposals: CopilotProposal[];
  rejected: { kind: string; summary: string; reason: string }[];
}

/**
 * Keeps the proposals that describe something CANVAS could actually act on.
 *
 * A FEATURE proposal is held to the same field spec the hand-entry form and
 * the accept-a-proposal path use, so the copilot cannot introduce a feature
 * through a third door in a shape the engines cannot read.
 */
export function validateProposals(raw: unknown[]): ValidatedProposals {
  const proposals: CopilotProposal[] = [];
  const rejected: ValidatedProposals["rejected"] = [];

  for (const item of raw) {
    if (item === null || typeof item !== "object") continue;
    const p = item as Record<string, unknown>;
    const kind = String(p.kind ?? "");
    const summary = String(p.summary ?? "").trim().slice(0, 300);

    if (!(PROPOSAL_KINDS as readonly string[]).includes(kind)) {
      rejected.push({ kind, summary, reason: "not a kind /proposals knows how to accept" });
      continue;
    }
    if (summary.length < 10) {
      rejected.push({ kind, summary, reason: "no summary a person could decide on" });
      continue;
    }

    if (kind === "FEATURE") {
      const payload = p.payload;
      const asFeature =
        payload !== null && typeof payload === "object" ? (payload as Record<string, unknown>) : null;
      const params =
        asFeature && typeof asFeature.parameters === "object" && asFeature.parameters !== null
          ? (asFeature.parameters as Record<string, unknown>)
          : null;
      if (!asFeature || params === null) {
        rejected.push({ kind, summary, reason: "a feature proposal with no parameters describes nothing buildable" });
        continue;
      }
      const refusals = validateFeatureParameters(String(asFeature.kind ?? ""), params);
      if (refusals.length > 0) {
        rejected.push({ kind, summary, reason: refusals.map((r) => r.reason).join(" ") });
        continue;
      }
    }

    proposals.push({ kind: kind as ProposalKind, summary, payload: p.payload ?? null });
  }

  return { proposals: proposals.slice(0, 5), rejected };
}

/**
 * Turning audit rows into something a machinist reads.
 *
 * The part history rendered `entityType` and `field` straight out of the row,
 * so a machinist looking at what changed on their part saw
 * "PartResponsibilityProfile · matingComponent" and "LatheWorkholding ·
 * clampForceLbf". Those are Prisma model names and column names. They are the
 * schema talking to itself in front of the operator.
 *
 * Not a lookup table of 26 models — that rots the moment somebody adds one.
 * Splitting the identifier does the right thing for most of them
 * (`PartRevision` → "Part revision", `boredDiameter` → "Bored diameter"), so
 * the maps below carry only the cases where the split is wrong or the plain
 * words would lose something.
 *
 * What must survive translation, and is the reason this file is not just
 * cosmetic: `AIRecommendation` stays "AI recommendation" and never
 * "Recommendation", because an operator has to see that a model was the
 * actor. `Disagreement` stays "Disagreement". Renaming is one keystroke from
 * laundering.
 */

/** Where splitting the identifier gives the wrong words. */
const ENTITY_OVERRIDES: Record<string, string> = {
  AIRecommendation: "AI recommendation",
  NCProgram: "NC program",
  LatheWorkholding: "Turning workholding",
  RotationalPart: "Turned part",
  BetaRunRecord: "Beta run",
  MachineCalibrationRecord: "Machine calibration",
  UploadedAsset: "Uploaded file",
  MetrologyDevice: "Instrument",
  WorkholdingDevice: "Workholding",
};

const FIELD_OVERRIDES: Record<string, string> = {
  clampForceLbf: "Clamp force",
  tailstockActive: "Tailstock",
  defaultSharing: "Network sharing default",
  fitClass: "Fit class",
  manufacturingApproach: "Manufacturing approach",
  matingComponent: "Mating component",
  resolvedValue: "Resolved value",
};

/** What the actor did, in the words a shop would use. */
export const ACTION_LABEL: Record<string, string> = {
  CREATE: "Created",
  UPDATE: "Changed",
  DELETE: "Deleted",
  APPROVE: "Approved",
  GENERATE: "Generated",
  EXPORT: "Exported",
  ACCEPT_SUGGESTION: "Suggestion accepted",
  REJECT_SUGGESTION: "Suggestion rejected",
};

/**
 * `PartRevision` → `Part revision`, `boredDiameter` → `Bored diameter`.
 * Runs of capitals are kept together so `NCProgram` does not become
 * "N C Program".
 */
function splitIdentifier(id: string): string {
  const words = id
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
    .trim();
  return words.charAt(0).toUpperCase() + words.slice(1).toLowerCase();
}

export function entityLabel(entityType: string): string {
  return ENTITY_OVERRIDES[entityType] ?? splitIdentifier(entityType);
}

/**
 * Field names arrive both as column identifiers and as phrases the call site
 * already wrote ("MANUFACTURING datum A", "RE step 2"). A value that already
 * contains a space is prose and is left alone.
 */
export function fieldLabel(field: string): string {
  if (FIELD_OVERRIDES[field]) return FIELD_OVERRIDES[field];
  if (field.includes(" ")) return field;
  return splitIdentifier(field);
}

export function actionLabel(action: string): string {
  return ACTION_LABEL[action] ?? splitIdentifier(action);
}

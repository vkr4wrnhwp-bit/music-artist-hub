import "server-only";
import { z } from "zod";
import { partIntentExtractionSchema, type PartIntentExtraction } from "@/lib/domain/part-intent";
import { featureSuggestionSchema, type FeatureSuggestion } from "@/lib/domain/features";

/**
 * AI SERVICE LAYER
 *
 * CANVAS is not wired to a single provider. Every model interaction goes
 * through this interface, returns a schema-validated structure, and is tagged
 * AI_INFERENCE provenance downstream. Two rules are absolute:
 *
 *   1. No API key ever reaches the client. These functions run server-side —
 *      enforced by the server-only import above rather than by this comment.
 *      anthropic.ts carries its own guard, but it is reached through a dynamic
 *      import, which resolves at runtime and so cannot fail a client build.
 *      Without a guard here, a client import of getAiProvider would have built
 *      cleanly and silently fallen back to the deterministic provider.
 *   2. The model never produces machine motion, and never produces a value
 *      that bypasses a manufacturing gate. It proposes; engines dispose.
 */

export const riskSummarySchema = z.object({
  summary: z.string(),
  concerns: z.array(z.object({ label: z.string(), detail: z.string(), severity: z.enum(["LOW", "MEDIUM", "HIGH"]) })),
  questions: z.array(z.string()),
});
export type RiskSummary = z.infer<typeof riskSummarySchema>;

export const measurementPlanSchema = z.object({
  measurements: z.array(
    z.object({
      id: z.string(),
      label: z.string(),
      featureHint: z.string(),
      recommendedDevice: z.string(),
      alternativeDevice: z.string().optional(),
      /** Other measurement ids this one depends on. */
      dependsOn: z.array(z.string()).default([]),
      rationale: z.string(),
    }),
  ),
  rationale: z.string(),
});
export type MeasurementPlan = z.infer<typeof measurementPlanSchema>;

export const copilotReplySchema = z.object({
  reply: z.string(),
  /** Structured references into project data the answer relied on. */
  references: z.array(z.object({ kind: z.string(), id: z.string(), label: z.string() })).default([]),
  /** Things the copilot needs before it can answer properly. */
  needs: z.array(z.string()).default([]),
  /**
   * Things to look at. These change what is on screen and nothing else, so a
   * wrong one wastes a click — they are validated against the part
   * server-side and then take effect immediately.
   */
  sceneActions: z
    .array(z.object({ kind: z.string(), targetId: z.string(), label: z.string() }))
    .default([]),
  /**
   * Changes to the part. These do NOT take effect: they go into the
   * AIRecommendation queue at PROPOSED and are accepted by a human on
   * /proposals, the same path every other AI suggestion takes. The copilot
   * gets no softer second route to the same data.
   */
  proposals: z
    .array(z.object({ kind: z.string(), summary: z.string(), payload: z.unknown().optional() }))
    .default([]),
});
export type CopilotReply = z.infer<typeof copilotReplySchema>;

export interface CopilotContext {
  partName?: string;
  material?: string | null;
  stock?: string | null;
  machine?: string | null;
  tools?: string[];
  workholding?: string | null;
  features?: string[];
  readiness?: string;
  openQuestions?: string[];
}

export interface AiProvider {
  readonly id: string;
  readonly label: string;
  /** False for the built-in deterministic provider. */
  readonly usesRemoteModel: boolean;

  interpretPartPrompt(prompt: string): Promise<PartIntentExtraction>;
  suggestFeatures(prompt: string, extraction: PartIntentExtraction): Promise<FeatureSuggestion[]>;
  analyzePartImage(description: string): Promise<{ observations: string[]; cautions: string[] }>;
  extractDrawingIntent(text: string): Promise<PartIntentExtraction>;
  recommendMissingMeasurements(context: { features: string[]; availableDevices: string[] }): Promise<MeasurementPlan>;
  summarizeRisk(context: CopilotContext): Promise<RiskSummary>;
  answerCopilot(question: string, context: CopilotContext): Promise<CopilotReply>;
  /**
   * Reads the characters stamped on a bearing from a photograph.
   *
   * Returns readings, not a designation: a designation is dimensions, and
   * 6203 against 6208 is a 17 mm bore against a 40 mm one. What comes back is
   * resolved against the catalogue in `bearing-stamp.ts` and confirmed by a
   * human before anything is stored — principle 3, an inference stays
   * inferred.
   *
   * `connected` is false for any provider that cannot actually look at an
   * image, and then `readings` is empty. It never returns a plausible guess.
   */
  readBearingStamp(image: { mediaType: string; base64: string }): Promise<BearingStampReading>;
}

export interface BearingStampReading {
  connected: boolean;
  readings: { text: string; confidence: number }[];
  /** Why there is nothing, when there is nothing. */
  note: string;
}

/* ------------------------------------------------------------------ */
/* Provider selection                                                  */
/* ------------------------------------------------------------------ */

let cached: AiProvider | null = null;

export async function getAiProvider(): Promise<AiProvider> {
  if (cached) return cached;
  const configured = process.env.CANVAS_AI_PROVIDER ?? "deterministic";

  if (configured === "anthropic" && process.env.ANTHROPIC_API_KEY) {
    const { AnthropicProvider } = await import("./anthropic");
    cached = new AnthropicProvider(process.env.ANTHROPIC_API_KEY, process.env.CANVAS_AI_MODEL);
  } else {
    const { DeterministicProvider } = await import("./deterministic");
    cached = new DeterministicProvider();
  }
  return cached;
}

/** Shared schema registry so both providers validate identically. */
export const SCHEMAS = {
  partIntent: partIntentExtractionSchema,
  features: z.object({ features: z.array(featureSuggestionSchema) }),
  measurementPlan: measurementPlanSchema,
  risk: riskSummarySchema,
  copilot: copilotReplySchema,
};

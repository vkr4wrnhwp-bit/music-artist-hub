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
 *   1. No API key ever reaches the client. These functions run server-side.
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

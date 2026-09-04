import "server-only";
import type { ZodType } from "zod";
import type { PartIntentExtraction } from "@/lib/domain/part-intent";
import { FEATURE_KINDS, type FeatureSuggestion } from "@/lib/domain/features";
import { validSighting, type PhotoRead } from "@/lib/engines/photo-plan";
import { DeterministicProvider } from "./deterministic";
import { z } from "zod";
import { SCHEMAS, type AiProvider, type BearingStampReading, type CopilotContext, type CopilotReply, type MeasurementPlan, type RiskSummary } from "./provider";

/** What a vision read may return. Characters and legibility — never dimensions. */
const photoReadSchema = z.object({
  sightings: z.array(
    z.object({
      label: z.string(),
      kind: z.string(),
      x: z.number(),
      y: z.number(),
      whatToMeasure: z.string(),
      note: z.string().optional(),
    }),
  ),
  note: z.string(),
});

const stampReadingSchema = z.object({
  readings: z.array(z.object({ text: z.string(), confidence: z.number() })),
  note: z.string(),
});

/**
 * ANTHROPIC PROVIDER
 *
 * Server-only. The key is read from the environment and never crosses to the
 * client — this module imports `server-only` so a client import is a build
 * error rather than a leak.
 *
 * Every call is structured-output: the model is given a JSON schema and its
 * response is validated before it enters the system. A response that fails
 * validation falls back to the deterministic provider rather than being
 * partially trusted, because a half-parsed manufacturing intake is worse than
 * a conservative one.
 */

const API_URL = "https://api.anthropic.com/v1/messages";
const DEFAULT_MODEL = "claude-sonnet-4-5";

const SYSTEM_PROMPT = `You are the reasoning layer inside CANVAS, a precision manufacturing platform.

You speak as an experienced manufacturing engineer and machinist would: concise, specific, willing to disagree. You explain why. You never pad an answer with enthusiasm.

Hard rules:
- You never emit G-code, machine motion, or any executable machine instruction. A deterministic engine does that.
- You never invent machine specifications, tooling, workholding, or material properties. If it is not in the supplied context, it does not exist.
- You never state a dimension, load, tolerance, or material substitution as fact when you are inferring it. Put it in "unknowns" instead.
- When information required for a safe recommendation is missing, say so plainly and name what is needed.
- You do not certify component safety. You assist with manufacturing planning.
- No emoji. No marketing language.

Respond only with JSON matching the supplied schema.`;

export class AnthropicProvider implements AiProvider {
  readonly id = "anthropic";
  readonly label = "Anthropic";
  readonly usesRemoteModel = true;

  private fallback = new DeterministicProvider();

  constructor(
    private apiKey: string,
    private model: string = process.env.CANVAS_AI_MODEL ?? DEFAULT_MODEL,
  ) {}

  /** The same structured call, with an image in the message. */
  private async structuredWithImage<T>(
    schema: ZodType<T>,
    jsonSchema: object,
    userPrompt: string,
    image: { mediaType: string; base64: string },
  ): Promise<T | null> {
    return this.structuredRequest(schema, jsonSchema, [
      { type: "image", source: { type: "base64", media_type: image.mediaType, data: image.base64 } },
      { type: "text", text: userPrompt },
    ]);
  }

  private async structured<T>(schema: ZodType<T>, jsonSchema: object, userPrompt: string): Promise<T | null> {
    return this.structuredRequest(schema, jsonSchema, userPrompt);
  }

  private async structuredRequest<T>(schema: ZodType<T>, jsonSchema: object, content: unknown): Promise<T | null> {
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": this.apiKey,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: this.model,
          max_tokens: 4096,
          system: SYSTEM_PROMPT,
          tools: [
            {
              name: "respond",
              description: "Return the structured response.",
              input_schema: jsonSchema,
            },
          ],
          tool_choice: { type: "tool", name: "respond" },
          messages: [{ role: "user", content }],
        }),
      });

      if (!res.ok) {
        console.error("[canvas.ai] Anthropic request failed", res.status, await res.text());
        return null;
      }

      const body = (await res.json()) as { content: { type: string; input?: unknown }[] };
      const toolUse = body.content.find((c) => c.type === "tool_use");
      if (!toolUse?.input) return null;

      const parsed = schema.safeParse(toolUse.input);
      if (!parsed.success) {
        console.error("[canvas.ai] Model output failed schema validation", parsed.error.issues);
        return null;
      }
      return parsed.data;
    } catch (err) {
      console.error("[canvas.ai] Anthropic request threw", err);
      return null;
    }
  }

  async interpretPartPrompt(prompt: string): Promise<PartIntentExtraction> {
    const result = await this.structured(
      SCHEMAS.partIntent,
      PART_INTENT_JSON_SCHEMA,
      `Extract a manufacturing part intent from this request. Units are inches unless the request says otherwise. Put anything you are not certain of into "unknowns" rather than guessing.\n\n${prompt}`,
    );
    return result ?? this.fallback.interpretPartPrompt(prompt);
  }

  async suggestFeatures(prompt: string, extraction: PartIntentExtraction): Promise<FeatureSuggestion[]> {
    const result = await this.structured(
      SCHEMAS.features,
      { type: "object", properties: { features: { type: "array", items: FEATURE_JSON_SCHEMA } }, required: ["features"] },
      `Propose parametric 2.5D features for this part. Every parameter must be a number in inches. Do not invent dimensions that were not stated or implied — omit the feature instead.\n\nRequest: ${prompt}\n\nExtracted intent: ${JSON.stringify(extraction)}`,
    );
    return result?.features ?? this.fallback.suggestFeatures(prompt, extraction);
  }

  async analyzePartImage(): Promise<{ observations: string[]; cautions: string[] }> {
    // Vision intake is a Phase 2 item — see /docs/REVERSE_ENGINEERING.md.
    return this.fallback.analyzePartImage();
  }

  async extractDrawingIntent(text: string): Promise<PartIntentExtraction> {
    return this.interpretPartPrompt(text);
  }

  async recommendMissingMeasurements(context: { features: string[]; availableDevices: string[] }): Promise<MeasurementPlan> {
    const result = await this.structured(
      SCHEMAS.measurementPlan,
      MEASUREMENT_PLAN_JSON_SCHEMA,
      `Plan the minimum set of measurements needed to constrain this part's model. Only recommend instruments from the available list. Order them so datums are established first.\n\nFeatures: ${context.features.join(", ")}\nAvailable instruments: ${context.availableDevices.join(", ")}`,
    );
    return result ?? this.fallback.recommendMissingMeasurements(context);
  }

  async summarizeRisk(context: CopilotContext): Promise<RiskSummary> {
    const result = await this.structured(
      SCHEMAS.risk,
      RISK_JSON_SCHEMA,
      `Summarise the outstanding manufacturing risks for this part from the supplied context only.\n\n${JSON.stringify(context, null, 2)}`,
    );
    return result ?? this.fallback.summarizeRisk(context);
  }

  /**
   * Reads the characters stamped on a bearing.
   *
   * The prompt asks for CHARACTERS, not for a bearing. The model is not asked
   * what size it is and its answer is not trusted for dimensions: the reading
   * is resolved against CANVAS's own catalogue afterwards, and a human
   * confirms it against the bearing in their hand before anything is stored.
   *
   * An unreadable stamp comes back empty. A model that will not say it cannot
   * read something is worse than no model here, because the value it invents
   * decides a bore diameter.
   */
  /**
   * WHAT IS ON THIS PART AND WHERE, NOT HOW BIG.
   *
   * The tool schema has no field a dimension could go in. That is the point:
   * a model asked to describe a part will happily volunteer "approximately
   * 40 mm", and a plausible diameter is the most dangerous output this
   * application could produce because it looks exactly like a measured one.
   * Recognising that there IS a bore, and where, is pattern recognition —
   * which is the thing a model is genuinely good at, and which no amount of
   * being right about makes it a measurement.
   *
   * The coordinates are for pointing at the photograph the machinist is
   * holding, and nothing else reads them. They never become part coordinates:
   * a picture has perspective, and a pixel is not a position on the part.
   */
  async readPartPhoto(image: { mediaType: string; base64: string }): Promise<PhotoRead> {
    const result = await this.structuredWithImage(
      photoReadSchema,
      {
        type: "object",
        properties: {
          sightings: {
            type: "array",
            description: "Each distinct machined feature you can actually see. Do not list a feature you are inferring from symmetry on a face that is not visible.",
            items: {
              type: "object",
              properties: {
                label: { type: "string", description: "What it is, as a machinist would say it. e.g. 'large central bore', 'four corner mounting holes'." },
                kind: { type: "string", description: `One of: ${FEATURE_KINDS.join(", ")}.` },
                x: { type: "number", description: "Horizontal position in the image, 0 at the left edge to 1 at the right." },
                y: { type: "number", description: "Vertical position in the image, 0 at the top edge to 1 at the bottom." },
                whatToMeasure: { type: "string", description: "The dimension a machinist must go and take. e.g. 'inside diameter and depth', 'thickness'." },
                note: { type: "string", description: "Anything about this view that makes the feature hard to be sure of." },
              },
              required: ["label", "kind", "x", "y", "whatToMeasure"],
            },
          },
          note: { type: "string", description: "What you could not see: faces out of view, occlusion, focus, lighting." },
        },
        required: ["sightings", "note"],
      },
      "This is a photograph of a machined part. A machinist is holding it and needs to know what to measure. " +
        "List the machined features you can see and where each one is in the image. " +
        "DO NOT state or estimate any dimension, size, diameter, depth or thread — not even approximately, not even as a range. " +
        "You cannot measure from a photograph and the machinist is going to measure every one of these themselves. " +
        "If a face is out of view, say so in the note rather than guessing what is on it.",
      image,
    );
    if (!result) {
      return { connected: true, sightings: [], note: "The vision request failed. Nothing was read from the photograph." };
    }
    /*
     * A kind outside the vocabulary, or a point off the image, is dropped
     * rather than coerced. A pin in the wrong place points at the wrong lump
     * of metal, which is worse than one pin fewer.
     */
    const sightings = result.sightings.filter(validSighting);
    const dropped = result.sightings.length - sightings.length;
    return {
      connected: true,
      sightings,
      note: dropped > 0 ? `${result.note} ${dropped} reading(s) did not name a feature kind CANVAS knows or fell outside the image, and were dropped.`.trim() : result.note,
    };
  }

  async readBearingStamp(image: { mediaType: string; base64: string }): Promise<BearingStampReading> {
    const result = await this.structuredWithImage(
      stampReadingSchema,
      {
        type: "object",
        properties: {
          readings: {
            type: "array",
            items: {
              type: "object",
              properties: {
                text: { type: "string", description: "The characters as stamped, exactly. Do not correct or expand them." },
                confidence: { type: "number", description: "0 to 1, how legible those characters actually were." },
              },
              required: ["text", "confidence"],
            },
          },
          note: { type: "string", description: "What made it hard to read, if anything." },
        },
        required: ["readings", "note"],
      },
      "Read the designation stamped on this bearing. Report the characters exactly as they appear, including any suffix. If the stamp is illegible or no stamp is visible, return an empty list and say so — do not guess a common bearing number. Do not state the bearing's dimensions.",
      image,
    );
    if (!result) {
      return { connected: true, readings: [], note: "The vision request failed. Nothing was read from the photograph." };
    }
    return { connected: true, readings: result.readings, note: result.note };
  }

  async answerCopilot(question: string, context: CopilotContext): Promise<CopilotReply> {
    const result = await this.structured(
      SCHEMAS.copilot,
      COPILOT_JSON_SCHEMA,
      `Answer the machinist's question using only the project context supplied. If the context does not contain what you need, say so and list it in "needs".\n\nQuestion: ${question}\n\nProject context:\n${JSON.stringify(context, null, 2)}`,
    );
    return result ?? this.fallback.answerCopilot(question, context);
  }
}

/* ------------------------------------------------------------------ */
/* JSON schemas handed to the model                                    */
/* ------------------------------------------------------------------ */

const PART_INTENT_JSON_SCHEMA = {
  type: "object",
  properties: {
    partName: { type: "string" },
    description: { type: "string" },
    units: { type: "string", enum: ["IN", "MM"] },
    material: { type: "string" },
    materialCondition: { type: "string" },
    stock: {
      type: "object",
      properties: {
        form: { type: "string", enum: ["RECTANGULAR", "ROUND", "TUBE", "NEAR_NET", "CASTING", "FORGING"] },
        x: { type: "number" },
        y: { type: "number" },
        z: { type: "number" },
        diameter: { type: "number" },
        length: { type: "number" },
      },
      required: ["form"],
    },
    finishedEnvelope: {
      type: "object",
      properties: { x: { type: "number" }, y: { type: "number" }, z: { type: "number" } },
      required: ["x", "y", "z"],
    },
    quantity: { type: "integer" },
    generalTolerance: { type: "number" },
    surfaceFinish: { type: "string" },
    features: { type: "array", items: { type: "string" } },
    notes: { type: "string" },
    unknowns: { type: "array", items: { type: "string" } },
    confidence: { type: "number" },
  },
  required: ["unknowns", "confidence"],
};

const FEATURE_JSON_SCHEMA = {
  type: "object",
  properties: {
    kind: { type: "string" },
    label: { type: "string" },
    functionalRole: { type: "string" },
    critical: { type: "boolean" },
    parameters: { type: "object" },
    rationale: { type: "string" },
  },
  required: ["kind", "label", "parameters"],
};

const MEASUREMENT_PLAN_JSON_SCHEMA = {
  type: "object",
  properties: {
    measurements: {
      type: "array",
      items: {
        type: "object",
        properties: {
          id: { type: "string" },
          label: { type: "string" },
          featureHint: { type: "string" },
          recommendedDevice: { type: "string" },
          alternativeDevice: { type: "string" },
          dependsOn: { type: "array", items: { type: "string" } },
          rationale: { type: "string" },
        },
        required: ["id", "label", "featureHint", "recommendedDevice", "rationale"],
      },
    },
    rationale: { type: "string" },
  },
  required: ["measurements", "rationale"],
};

const RISK_JSON_SCHEMA = {
  type: "object",
  properties: {
    summary: { type: "string" },
    concerns: {
      type: "array",
      items: {
        type: "object",
        properties: {
          label: { type: "string" },
          detail: { type: "string" },
          severity: { type: "string", enum: ["LOW", "MEDIUM", "HIGH"] },
        },
        required: ["label", "detail", "severity"],
      },
    },
    questions: { type: "array", items: { type: "string" } },
  },
  required: ["summary", "concerns", "questions"],
};

const COPILOT_JSON_SCHEMA = {
  type: "object",
  properties: {
    reply: { type: "string" },
    references: {
      type: "array",
      items: {
        type: "object",
        properties: { kind: { type: "string" }, id: { type: "string" }, label: { type: "string" } },
        required: ["kind", "id", "label"],
      },
    },
    needs: { type: "array", items: { type: "string" } },
  },
  required: ["reply"],
};

import type { PartIntentExtraction } from "@/lib/domain/part-intent";
import type { FeatureSuggestion } from "@/lib/domain/features";
import type { AiProvider, CopilotContext, CopilotReply, MeasurementPlan, RiskSummary } from "./provider";

/**
 * DETERMINISTIC PROVIDER
 *
 * The default provider. It is a real grammar-based intake parser, not a stub —
 * it handles the dimensional, material and feature vocabulary that machinists
 * actually type, so CANVAS is fully usable with no API key and no network.
 *
 * It is deliberately conservative: anything it does not confidently recognise
 * becomes an entry in `unknowns` rather than a guess. That is the correct
 * behaviour for a manufacturing intake regardless of which provider is active.
 */

const FRACTION = String.raw`\d+(?:\s+\d+/\d+)?|\d*\.\d+|\d+/\d+`;

const MATERIALS: { pattern: RegExp; name: string; condition?: string }[] = [
  { pattern: /\b6061[- ]?t6511\b/i, name: "Aluminum 6061", condition: "T6511" },
  { pattern: /\b6061[- ]?t6\b/i, name: "Aluminum 6061", condition: "T6" },
  { pattern: /\b6061\b/i, name: "Aluminum 6061", condition: "T6" },
  { pattern: /\b7075[- ]?t6(51)?\b/i, name: "Aluminum 7075", condition: "T651" },
  { pattern: /\b2024\b/i, name: "Aluminum 2024", condition: "T351" },
  { pattern: /\bmic[- ]?6\b/i, name: "MIC-6 cast aluminum plate", condition: "As cast" },
  { pattern: /\b304\s*(?:l)?\s*stainless\b|\b304\b/i, name: "Stainless 304", condition: "Annealed" },
  { pattern: /\b316\s*(?:l)?\b/i, name: "Stainless 316", condition: "Annealed" },
  { pattern: /\b17[- ]?4\s*(?:ph)?\b/i, name: "Stainless 17-4 PH", condition: "H900" },
  { pattern: /\b4140\b/i, name: "Steel 4140", condition: "Pre-hard 28-32 HRC" },
  { pattern: /\b1018\b/i, name: "Steel 1018", condition: "Cold rolled" },
  { pattern: /\b12l14\b/i, name: "Steel 12L14", condition: "Cold rolled" },
  { pattern: /\ba36\b/i, name: "Steel A36", condition: "Hot rolled" },
  { pattern: /\bti(?:tanium)?[- ]?6al[- ]?4v\b|\bgrade\s*5\s*ti/i, name: "Titanium 6Al-4V", condition: "Annealed" },
  { pattern: /\bbrass\b|\b360\s*brass\b/i, name: "Brass 360", condition: "Half hard" },
  { pattern: /\bdelrin\b|\bacetal\b/i, name: "Acetal (Delrin)", condition: "Extruded" },
  { pattern: /\buhmw\b/i, name: "UHMW-PE", condition: "Extruded" },
  { pattern: /\bpeek\b/i, name: "PEEK", condition: "Extruded" },
  { pattern: /\baluminum\b|\baluminium\b|\balum\b/i, name: "Aluminum 6061", condition: "T6" },
  { pattern: /\bstainless\b/i, name: "Stainless 304", condition: "Annealed" },
  { pattern: /\bsteel\b/i, name: "Steel 1018", condition: "Cold rolled" },
];

const NUMBER_WORDS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8,
  nine: 9, ten: 10, eleven: 11, twelve: 12, sixteen: 16, twenty: 20,
};

function parseNum(raw: string): number {
  const s = raw.trim();
  const mixed = /^(\d+)\s+(\d+)\/(\d+)$/.exec(s);
  if (mixed) return Number(mixed[1]) + Number(mixed[2]) / Number(mixed[3]);
  const frac = /^(\d+)\/(\d+)$/.exec(s);
  if (frac) return Number(frac[1]) / Number(frac[2]);
  return Number(s);
}

export class DeterministicProvider implements AiProvider {
  readonly id = "deterministic";
  readonly label = "CANVAS deterministic parser";
  readonly usesRemoteModel = false;

  async interpretPartPrompt(prompt: string): Promise<PartIntentExtraction> {
    const text = prompt.trim();
    const unknowns: string[] = [];
    const out: PartIntentExtraction = { unknowns, confidence: 0.5 };

    /* ---- Units ---- */
    const metric = /\bmm\b|\bmillimet(?:er|re)s?\b/i.test(text);
    out.units = metric ? "MM" : "IN";

    /* ---- Material ---- */
    const mat = MATERIALS.find((m) => m.pattern.test(text));
    if (mat) {
      out.material = mat.name;
      out.materialCondition = mat.condition;
    } else {
      unknowns.push("Material not stated");
    }

    /* ---- Envelope: "6 x 4 x .500" ---- */
    const envRe = new RegExp(
      String.raw`(${FRACTION})\s*(?:in|")?\s*[x×]\s*(${FRACTION})\s*(?:in|")?\s*[x×]\s*(${FRACTION})`,
      "i",
    );
    const env = envRe.exec(text);
    if (env) {
      const [x, y, z] = [parseNum(env[1]), parseNum(env[2]), parseNum(env[3])];
      out.finishedEnvelope = { x, y, z };
      // Stock gets a conventional facing and profile allowance.
      out.stock = {
        form: "RECTANGULAR",
        x: Number((x + 0.125).toFixed(3)),
        y: Number((y + 0.125).toFixed(3)),
        z: Number((z + 0.125).toFixed(3)),
      };
    } else {
      unknowns.push("Finished envelope not stated");
    }

    /* ---- Quantity ---- */
    const qty = /\b(?:qty|quantity|make|need|run)\s*(?:of\s*)?(\d{1,6})\b/i.exec(text) ?? /\b(\d{1,6})\s*(?:pcs?|pieces|parts|off)\b/i.exec(text);
    if (qty) out.quantity = Number(qty[1]);
    else unknowns.push("Quantity not stated");

    /* ---- Tolerance ---- */
    const tol = /(?:±|\+\/-|plus\/minus)\s*(\.\d+|\d*\.\d+|\d+)/i.exec(text);
    if (tol) out.generalTolerance = parseNum(tol[1]);
    else unknowns.push("General tolerance not stated");

    /* ---- Surface finish ---- */
    const finish = /(\d{2,3})\s*(?:ra|µin|microinch)/i.exec(text);
    if (finish) out.surfaceFinish = `${finish[1]} Ra`;
    const anodize = /\banodiz(?:e|ed|ing)\b/i.exec(text);
    if (anodize) out.notes = (out.notes ? out.notes + " " : "") + "Anodising called out — treat as an outside process.";

    /* ---- Features (text summary) ---- */
    out.features = this.describeFeatures(text);
    if (out.features.length === 0) unknowns.push("No recognisable features in the description");

    out.partName = this.deriveName(text, out);
    out.description = text;

    // Completeness, not correctness. Never presented as a safety number.
    const filled = [out.material, out.finishedEnvelope, out.quantity, out.generalTolerance, out.features?.length].filter(Boolean).length;
    out.confidence = Number((filled / 5).toFixed(2));

    unknowns.push("Functional responsibility not stated — load, environment and failure consequence required before process advice");

    return out;
  }

  private deriveName(text: string, out: PartIntentExtraction): string {
    if (/\bplate\b/i.test(text)) return "Plate";
    if (/\bbracket\b/i.test(text)) return "Bracket";
    if (/\bhousing\b/i.test(text)) return "Housing";
    if (/\bmount\b/i.test(text)) return "Mount";
    if (/\bspacer\b/i.test(text)) return "Spacer";
    if (/\bflange\b/i.test(text)) return "Flange";
    if (/\badapter\b/i.test(text)) return "Adapter";
    if (/\bbearing\b/i.test(text)) return "Bearing Support";
    return out.material ? `${out.material} Component` : "New Part";
  }

  private describeFeatures(text: string): string[] {
    const found: string[] = [];

    // "four 1/4-20 holes", "4x M6 tapped holes"
    const tapRe = new RegExp(
      String.raw`\b(\d+|${Object.keys(NUMBER_WORDS).join("|")})\s*(?:x\s*)?(?:off\s*)?((?:\d+/\d+|#\d+|M\d+)[- ]?\d*(?:\s*(?:unc|unf|x\s*[\d.]+))?)\s*(?:tapped\s*)?holes?`,
      "gi",
    );
    for (const m of text.matchAll(tapRe)) {
      const count = NUMBER_WORDS[m[1].toLowerCase()] ?? Number(m[1]);
      found.push(`${count} × ${m[2].toUpperCase()} tapped holes`);
    }

    // "four .266 thru holes"
    const holeRe = new RegExp(
      String.raw`\b(\d+|${Object.keys(NUMBER_WORDS).join("|")})\s*(?:x\s*)?(?:⌀|dia\.?\s*)?(${FRACTION})\s*(?:in|")?\s*(?:thru|through)?\s*holes?`,
      "gi",
    );
    for (const m of text.matchAll(holeRe)) {
      const count = NUMBER_WORDS[m[1].toLowerCase()] ?? Number(m[1]);
      const d = parseNum(m[2]);
      if (d > 0 && d < 6) found.push(`${count} × ⌀${d.toFixed(4)} holes`);
    }

    // pockets
    const pocketRe = new RegExp(String.raw`(${FRACTION})\s*(?:in|")?\s*deep\s*(?:center\s*)?pocket`, "gi");
    for (const m of text.matchAll(pocketRe)) found.push(`Pocket ${parseNum(m[1]).toFixed(4)} deep`);
    if (found.every((f) => !f.includes("Pocket")) && /\bpocket\b/i.test(text)) found.push("Pocket (depth not stated)");

    // bore
    const boreRe = new RegExp(String.raw`(${FRACTION})\s*(?:in|"|mm)?\s*(?:dia\.?\s*)?bore`, "gi");
    for (const m of text.matchAll(boreRe)) found.push(`⌀${parseNum(m[1]).toFixed(4)} bore`);
    if (found.every((f) => !f.includes("bore")) && /\bbore\b/i.test(text)) found.push("Bore (diameter not stated)");

    // corners / chamfers / engraving
    const radRe = new RegExp(String.raw`(?:r|radius\s*)(${FRACTION})\s*(?:in|")?\s*(?:corners?|rounded)`, "gi");
    for (const m of text.matchAll(radRe)) found.push(`R${parseNum(m[1]).toFixed(3)} corners`);
    if (/rounded corners/i.test(text) && !found.some((f) => f.startsWith("R"))) found.push("Rounded corners (radius not stated)");

    const chamRe = new RegExp(String.raw`(${FRACTION})\s*(?:in|")?\s*(?:x\s*45\s*°?|chamfer)`, "gi");
    for (const m of text.matchAll(chamRe)) found.push(`${parseNum(m[1]).toFixed(3)} × 45° chamfer`);
    if (/\bchamfer\b/i.test(text) && !found.some((f) => f.includes("chamfer"))) {
      found.push("Chamfer (size not stated)");
    }

    if (/\bengrav/i.test(text)) {
      const quoted = /["“']([^"”']{1,40})["”']/.exec(text);
      found.push(quoted ? `Engraving "${quoted[1]}"` : "Engraved text (content not stated)");
    }
    if (/\bslot\b/i.test(text)) found.push("Slot");
    if (/\bcounterbore|c'bore\b/i.test(text)) found.push("Counterbore");
    if (/\bcountersink|csk\b/i.test(text)) found.push("Countersink");
    if (/\bfac(?:e|ing)\b/i.test(text)) found.push("Face");

    return [...new Set(found)];
  }

  async suggestFeatures(prompt: string, extraction: PartIntentExtraction): Promise<FeatureSuggestion[]> {
    const out: FeatureSuggestion[] = [];
    const env = extraction.finishedEnvelope;
    if (!env) return out;

    out.push({
      kind: "FACE",
      label: "Face top",
      functionalRole: "DATUM_FACE",
      critical: false,
      parameters: { depth: 0.0625 },
      rationale: "Stock was sized with facing allowance on both faces.",
    });
    out.push({
      kind: "OUTSIDE_CONTOUR",
      label: "Outside profile",
      functionalRole: "NONE",
      critical: false,
      parameters: { width: env.x, length: env.y, cornerRadius: 0.25, depth: env.z },
      rationale: "Derived from the stated finished envelope.",
    });

    for (const f of extraction.features ?? []) {
      const tapped = /^(\d+) × (.+) tapped holes$/.exec(f);
      if (tapped) {
        const count = Number(tapped[1]);
        const positions = cornerPositions(count, env.x, env.y, 0.5);
        positions.forEach((p, i) => {
          out.push({
            kind: "TAPPED_HOLE",
            label: `${tapped[2]} tapped hole ${i + 1}`,
            functionalRole: "MOUNTING_HOLE",
            critical: false,
            parameters: { centerX: p.x, centerY: p.y, diameter: 0.201, depth: env.z, through: true, thread: tapped[2] },
            rationale: "Positioned on a symmetric corner pattern — confirm the actual bolt circle.",
          });
        });
      }
      const pocket = /^Pocket ([\d.]+) deep$/.exec(f);
      if (pocket) {
        out.push({
          kind: "RECT_POCKET",
          label: "Center pocket",
          functionalRole: "NONE",
          critical: false,
          parameters: {
            centerX: 0,
            centerY: 0,
            width: Number((env.x * 0.5).toFixed(3)),
            length: Number((env.y * 0.5).toFixed(3)),
            depth: Number(pocket[1]),
            cornerRadius: 0.25,
            bottomRadius: 0,
            top: 0,
          },
          rationale: "Size inferred as half the envelope — confirm the actual pocket dimensions.",
        });
      }
      const engrave = /^Engraving "(.+)"$/.exec(f);
      if (engrave) {
        out.push({
          kind: "ENGRAVING",
          label: "Engraved text",
          functionalRole: "COSMETIC",
          critical: false,
          parameters: { text: engrave[1], centerX: 0, centerY: -env.y / 3, height: 0.2, depth: 0.01, top: 0 },
          rationale: "Placed below centre by convention — confirm location.",
        });
      }
    }
    return out;
  }

  async analyzePartImage(): Promise<{ observations: string[]; cautions: string[] }> {
    return {
      observations: [],
      cautions: [
        "No vision model is configured. CANVAS will not describe geometry it has not analysed.",
        "Photographs are stored and available for guided measurement, which does not require a vision model.",
      ],
    };
  }

  async extractDrawingIntent(text: string): Promise<PartIntentExtraction> {
    return this.interpretPartPrompt(text);
  }

  async recommendMissingMeasurements(context: {
    features: string[];
    availableDevices: string[];
  }): Promise<MeasurementPlan> {
    const measurements = context.features.map((f, i) => ({
      id: `m${i + 1}`,
      label: `Measure ${f}`,
      featureHint: f,
      recommendedDevice: pickDevice(f, context.availableDevices),
      alternativeDevice: context.availableDevices.includes("DIGITAL_CALIPER") ? "Digital calipers — lower confidence" : undefined,
      dependsOn: i === 0 ? [] : ["m1"],
      rationale: "Every dimension after the first is referenced to the primary datum established by measurement m1.",
    }));
    return {
      measurements,
      rationale:
        "Measurements are ordered so the datum is established first; every subsequent dimension is then referenced to it rather than measured part-to-part.",
    };
  }

  async summarizeRisk(context: CopilotContext): Promise<RiskSummary> {
    const concerns: RiskSummary["concerns"] = [];
    if (!context.machine) concerns.push({ label: "No machine selected", detail: "Travel, spindle and post-processor limits cannot be validated.", severity: "HIGH" });
    if (!context.workholding) concerns.push({ label: "Workholding undefined", detail: "Setup stability and fixture clearance cannot be evaluated.", severity: "HIGH" });
    if (!context.material) concerns.push({ label: "Material unspecified", detail: "Speeds, feeds and cost are all downstream of material.", severity: "MEDIUM" });
    return {
      summary: concerns.length === 0 ? "No outstanding structural gaps in the manufacturing package." : `${concerns.length} unresolved manufacturing conditions.`,
      concerns,
      questions: context.openQuestions ?? [],
    };
  }

  async answerCopilot(question: string, context: CopilotContext): Promise<CopilotReply> {
    const q = question.toLowerCase();
    const needs: string[] = [];
    const references: CopilotReply["references"] = [];

    const say = (reply: string) => ({ reply, references, needs });

    if (!context.machine && /(machine|cycle|post|g-?code|spindle|travel)/.test(q)) {
      needs.push("Machine selection");
      return say("No machine is selected for this part, so I can't answer that. Travel limits, spindle capability and the post-processor all come from the machine profile, and I won't assume one.");
    }

    if (/how should i hold|workhold|fixture|vise|jaw/.test(q)) {
      if (!context.workholding) {
        needs.push("Workholding definition");
        return say("Workholding isn't defined yet. Once you select a vise and set the stock position I can evaluate grip depth, jaw engagement and projection against the roughing load — until then anything I said about holding it would be invented.");
      }
      return say(`Current setup uses ${context.workholding}. The Workholding panel carries the grip and engagement assessment along with the factors behind it — that's the authoritative answer, not this chat.`);
    }

    if (/cheaper|cost|reduce cost|price/.test(q)) {
      return say("Cost is computed from the assumption set in the Cost panel, not estimated here. The three levers with real leverage on a part like this are setup count, roughing strategy and material utilisation. Open Cost to see which line dominates, then change that assumption and watch the quantity breaks move.");
    }

    if (/cast|forge|additive|3d print|should i machine|make it another way/.test(q)) {
      return say("Process comparison lives in the Manufacturing Method Advisor. It won't recommend a change until the part responsibility profile is filled in — load case, environment and failure consequence. Substituting a process without knowing what the part does is how a part fails in service.");
    }

    if (/why.*tool|which tool|what tool/.test(q)) {
      return say(
        context.tools?.length
          ? `Tools currently assigned: ${context.tools.join(", ")}. Tool selection is driven by the smallest internal radius in the geometry and the depth each feature needs to reach — both are shown in the Readiness panel.`
          : "No tools are assigned yet, so there's nothing to justify.",
      );
    }

    if (/metric|mm|nominal|bearing/.test(q)) {
      return say("Nominal reasoning runs on the measurement, not on this conversation. Record the measurement in a metrology session and CANVAS will compare it against bearing, thread, dowel and stock tables and show you the candidates with their deviations. It won't change a critical dimension without you accepting it.");
    }

    if (/missing|what do i need|what dimensions/.test(q)) {
      return say(
        context.openQuestions?.length
          ? `Outstanding: ${context.openQuestions.join("; ")}.`
          : "Nothing is flagged outstanding on the intake right now. That is not the same as the part being ready to run — check the Readiness gates.",
      );
    }

    return say(
      "I answer from the structured project data — geometry, machine, tooling, workholding, cost assumptions and measurement records. I don't have a model configured to reason beyond that in this deployment. Set CANVAS_AI_PROVIDER and ANTHROPIC_API_KEY server-side to enable the full copilot.",
    );
  }
}

function cornerPositions(count: number, x: number, y: number, inset: number) {
  if (count === 4) {
    return [
      { x: -x / 2 + inset, y: -y / 2 + inset },
      { x: x / 2 - inset, y: -y / 2 + inset },
      { x: x / 2 - inset, y: y / 2 - inset },
      { x: -x / 2 + inset, y: y / 2 - inset },
    ];
  }
  return Array.from({ length: count }, (_, i) => {
    const a = (i / count) * Math.PI * 2;
    const r = Math.min(x, y) / 2 - inset;
    return { x: Number((r * Math.cos(a)).toFixed(3)), y: Number((r * Math.sin(a)).toFixed(3)) };
  });
}

function pickDevice(featureHint: string, available: string[]): string {
  const h = featureHint.toLowerCase();
  if (h.includes("bore") && available.includes("BORE_GAUGE")) return "Bore gauge + micrometer";
  if (h.includes("bore") && available.includes("TELESCOPING_GAUGE")) return "Telescoping gauge + micrometer";
  if ((h.includes("thickness") || h.includes("height")) && available.includes("MICROMETER")) return "Micrometer";
  if (h.includes("depth") && available.includes("DEPTH_MICROMETER")) return "Depth micrometer";
  if (h.includes("center") && available.includes("HEIGHT_GAUGE")) return "Height gauge on a surface plate";
  return available.includes("DIGITAL_CALIPER") ? "Digital calipers" : "Best available instrument";
}

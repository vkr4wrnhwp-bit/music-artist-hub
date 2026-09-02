import { test } from "node:test";
import assert from "node:assert/strict";
import {
  CONFIDENCE,
  SOURCES,
  isEngineeringGrade,
  inferred,
  value,
  unknown,
  userValue,
  measured,
  manufacturerSpec,
  calculated,
  confirmedBy,
  provenanceDetail,
  type Provenanced,
  type Source,
} from "@/lib/provenance";
import { readFileSync } from "node:fs";

/**
 * Locked principle 3: "AI inference never satisfies a required gate. The
 * model may suggest, identify patterns, recommend, question, compare and
 * explain. It may not silently certify."
 *
 * CLAUDE.md names isEngineeringGrade as the one place that rule lives. It
 * had no tests, and — until the material gate was wired through it — no
 * callers either: the gate that was meant to enforce it had reimplemented a
 * narrower version inline. A rule enforced by a copy is a rule with nothing
 * keeping the copies together.
 */

test("AI inference is never engineering grade, at any score or confidence", () => {
  // The score is the model's own opinion of itself. It is not evidence.
  for (const score of [0, 0.5, 0.85, 0.99, 1]) {
    assert.equal(isEngineeringGrade(inferred("6061-T6", score)), false, `score ${score}`);
  }
  // Nor does dressing the record up in a stronger confidence get past it —
  // the source is checked before the confidence is.
  for (const confidence of CONFIDENCE) {
    assert.equal(
      isEngineeringGrade(value("6061-T6", "AI_INFERENCE", confidence)),
      false,
      `AI_INFERENCE at ${confidence}`,
    );
  }
});

test("a human confirming an inference is the one thing that promotes it", () => {
  // Principle 11: the confirmation is a recorded human act, not a click that
  // clears a gate on the model's behalf — the value stays AI_INFERENCE.
  const confirmed = value("6061-T6", "AI_INFERENCE", "LOW", { confirmedByUser: true });
  assert.equal(isEngineeringGrade(confirmed), true);
  assert.equal(confirmed.source, "AI_INFERENCE");
});

test("a null value is never engineering grade, whatever it claims about itself", () => {
  for (const source of SOURCES) {
    assert.equal(
      isEngineeringGrade(value(null, source, "VERIFIED", { confirmedByUser: true })),
      false,
      `null from ${source}`,
    );
  }
  assert.equal(isEngineeringGrade(unknown()), false);
});

test("sources verifiable outside CANVAS pass without a human, weak ones do not", () => {
  assert.equal(isEngineeringGrade(userValue("6061-T6")), true);
  assert.equal(isEngineeringGrade(measured(1.5748)), true);
  assert.equal(isEngineeringGrade(manufacturerSpec(8100)), true);
  // A published standard is checkable against the standard.
  assert.equal(isEngineeringGrade(value(40, "STANDARD", "VERIFIED")), true);
  // A deterministic calculation is not itself evidence about the world, and
  // a system default is nobody's decision yet.
  assert.equal(isEngineeringGrade(calculated(1200)), false);
  assert.equal(isEngineeringGrade(value("6061", "DEFAULT", "LOW")), false);
  // A simulation result is not a measurement.
  assert.equal(isEngineeringGrade(value(true, "SIMULATION", "MEDIUM")), false);
});

test("every source is decided, not left to fall through", () => {
  // A new source added to the vocabulary must have an answer here rather
  // than inheriting whatever the last branch happens to do.
  const decided: Record<Source, boolean> = {
    USER: true,
    MEASURED: true,
    MANUFACTURER: true,
    STANDARD: true,
    CALCULATED: false,
    SIMULATION: false,
    AI_INFERENCE: false,
    DEFAULT: false,
  };
  for (const source of SOURCES) {
    // At the STRONGEST confidence the vocabulary has, deliberately: the
    // question is whether the source decides, so handing each one only the
    // confidence it realistically carries would make this vacuous — the
    // weak ones would fail on confidence and prove nothing about source.
    assert.equal(
      isEngineeringGrade(value("x", source, "VERIFIED")),
      decided[source],
      `${source} at VERIFIED — the source decides, not the label attached to it`,
    );
  }
});

/* ---- the provenance panel ---- */

/**
 * The badge was a `<span>` whose `title=` repeated what it already said in
 * text. Two fields the engines fill were rendered nowhere: `note` — the
 * reason a value is what it is — and `score`, the model's own confidence.
 * provenance.ts documented note as "shown in the provenance popover" and
 * there was no popover.
 */

test("every value gets the same rows, so none can be quietly dropped", () => {
  // Fixed length is the point. "Instrument — not recorded" is a fact a
  // machinist can act on; a missing row is one they will not notice.
  const labels = (p: Provenanced<unknown>) => provenanceDetail(p).map((r) => r.label);
  const reference = labels(value("x", "USER", "VERIFIED"));
  for (const source of SOURCES) {
    for (const confidence of CONFIDENCE) {
      assert.deepEqual(labels(value("x", source, confidence)), reference, `${source}/${confidence} returns other rows`);
    }
  }
  assert.deepEqual(labels(unknown()), reference, "an unknown value returns fewer rows");
});

test("nothing recorded reads as not recorded, never as undefined", () => {
  const rows = provenanceDetail(value(null, "DEFAULT", "UNKNOWN"));
  for (const r of rows) {
    if (r.value === null) continue;
    assert.ok(!/undefined|null|NaN/.test(r.value), `${r.label} rendered "${r.value}"`);
  }
  // And the empty ones are explicitly null rather than an empty string, so
  // the UI can tell "not recorded" from "recorded as blank".
  const basis = rows.find((r) => r.label === "Basis");
  assert.equal(basis?.value, null);
});

test("the gate answer comes from isEngineeringGrade, not from a second copy of the rule", () => {
  // CLAUDE.md names provenance.ts as the one home of this rule. A plausible
  // re-derivation — "confirmed, or a high-confidence source" — differs from
  // the real one, and this is where that would show up.
  const cases: Provenanced<unknown>[] = [];
  for (const source of SOURCES) {
    for (const confidence of CONFIDENCE) {
      for (const confirmedByUser of [true, false]) {
        cases.push(value("x", source, confidence, { confirmedByUser }));
      }
    }
  }
  cases.push(value(null, "USER", "VERIFIED", { confirmedByUser: true }));
  for (const p of cases) {
    const row = provenanceDetail(p).find((r) => r.label === "Can satisfy a required gate");
    assert.equal(
      row?.value,
      isEngineeringGrade(p) ? "Yes" : "No",
      `${p.source}/${p.confidence}/confirmed=${p.confirmedByUser} disagrees with isEngineeringGrade`,
    );
  }
});

test("an AI inference says so, at every confidence", () => {
  for (const confidence of CONFIDENCE) {
    const p = value("x", "AI_INFERENCE", confidence);
    const row = provenanceDetail(p).find((r) => r.label === "Can satisfy a required gate");
    assert.equal(row?.value, "No", `AI_INFERENCE at ${confidence} claims it can satisfy a gate`);
  }
  // Unless a human has explicitly confirmed it — which is the one exception
  // isEngineeringGrade allows and the panel must reflect.
  const confirmed = value("x", "AI_INFERENCE", "LOW", { confirmedByUser: true });
  assert.equal(
    provenanceDetail(confirmed).find((r) => r.label === "Can satisfy a required gate")?.value,
    "Yes",
  );
});

test("a model score is shown for a model's output and nowhere else", () => {
  const ai = provenanceDetail(value("x", "AI_INFERENCE", "MEDIUM", { score: 0.62 }));
  assert.equal(ai.find((r) => r.label === "Model score")?.value, "0.62");
  // A score on a measured value would be a number with nothing behind it.
  const measuredWithScore = provenanceDetail(value("x", "MEASURED", "HIGH", { score: 0.62 }));
  assert.equal(measuredWithScore.find((r) => r.label === "Model score")?.value, null);
});

test("a chain of custody survives being stored as JSON", () => {
  // This is literally the persistence path: intent is stored whole as
  // intentJson and spread back over an empty intent on the way out.
  const p = confirmedBy("Aluminum 6061", "Demo Operator", new Date("2026-09-02T10:00:00Z"), "Part responsibility interview");
  const round = JSON.parse(JSON.stringify(p)) as Provenanced<string>;
  assert.deepEqual(provenanceDetail(round), provenanceDetail(p));
  const rows = provenanceDetail(round);
  assert.equal(rows.find((r) => r.label === "Recorded by")?.value, "Demo Operator");
  assert.equal(rows.find((r) => r.label === "Method")?.value, "Part responsibility interview");
  assert.match(rows.find((r) => r.label === "Recorded")?.value ?? "", /^2026-09-02T10:00:00/);
});

test("value() carries every field a write site passes, not just two of them", () => {
  // It used to pick `note` and `score` out of `extra` and drop the rest, so a
  // caller that recorded a method or a timestamp had it discarded on the way
  // in — the field would exist in the type and never reach storage.
  const p = value("x", "CALCULATED", "MEDIUM", {
    note: "n",
    method: "m",
    recordedAt: "2026-01-01T00:00:00.000Z",
    recordedBy: "r",
    instrument: "i",
    uncertainty: 0.0005,
    calculationVersion: "v1",
  });
  for (const [k, v] of Object.entries({ note: "n", method: "m", recordedBy: "r", instrument: "i", calculationVersion: "v1" })) {
    assert.equal((p as unknown as Record<string, unknown>)[k], v, `value() dropped ${k}`);
  }
  assert.equal(p.uncertainty, 0.0005);
});

/* ---- and it reaches the interface ---- */

test("the badge opens a panel instead of hiding the chain in a tooltip", () => {
  const ui = readFileSync("src/components/ui.tsx", "utf8");
  const badge = /export function ProvenanceBadge[\s\S]{0,3000}?\n}/.exec(ui);
  assert.ok(badge, "ProvenanceBadge moved — this test cannot check it any more");
  assert.ok(/<details/.test(badge![0]), "the badge is not an expandable element");
  assert.ok(!/title=/.test(badge![0]), "the chain of custody is back in a tooltip");
  assert.ok(/provenanceDetail\(/.test(badge![0]), "the badge does not render the detail rows");
});

test("the panel stays read-only", () => {
  // A confirm control here would let a click inside a disclosure promote an
  // AI inference to engineering grade — the precise thing principle 2 forbids.
  const ui = readFileSync("src/components/ui.tsx", "utf8");
  const badge = /export function ProvenanceBadge[\s\S]{0,3000}?\n}/.exec(ui)![0];
  for (const control of ["<button", "onClick", "<form", "<input"]) {
    assert.ok(!badge.includes(control), `the provenance panel gained ${control}`);
  }
});

test("the fields the engines write actually reach the reader", () => {
  // The defect this whole item is: a field written for a human that the page
  // drops. note was documented as appearing in a popover that did not exist.
  const lib = readFileSync("src/lib/provenance.ts", "utf8");
  for (const field of ["note", "method", "recordedAt", "recordedBy", "instrument", "uncertainty"]) {
    assert.ok(new RegExp(`${field}\\??:`).test(lib), `Provenanced no longer declares ${field}`);
    assert.ok(new RegExp(`p\\.${field}`).test(lib), `provenanceDetail never reads ${field}`);
  }
});

test("a badge is never nested inside a span it cannot legally sit in", () => {
  // <details> is flow content. Inside a <span> the markup is invalid and
  // browsers reparent it, which moves the panel out of its row.
  for (const file of ["src/components/ui.tsx", "src/app/(app)/parts/[id]/page.tsx"]) {
    const src = readFileSync(file, "utf8");
    assert.ok(
      !/<span[^>]*>(?:(?!<\/span>)[\s\S]){0,400}?<ProvenanceBadge/.test(src),
      `${file} wraps a ProvenanceBadge in a span`,
    );
  }
});

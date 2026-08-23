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
  type Source,
} from "@/lib/provenance";

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

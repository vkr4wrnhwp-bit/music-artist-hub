import { test } from "node:test";
import assert from "node:assert/strict";
import { evaluateAuditGates, type AuditGateInput } from "@/lib/nc/audit-gates";
import { parseNC } from "@/lib/nc/parse";

/**
 * Run It Past CANVAS audit gates: worst-gate stages, tool mapping refuses
 * to be averaged away, unsupported context fails the parser gate, and the
 * stored-original requirement is a hard gate — not decoration.
 */

const CLEAN = ["%", "O100", "G20 G90 G17 G54", "T1 M6", "S8000 M3", "G0 X0 Y0 Z0.1", "G1 Z-0.1 F20.", "G1 X2.0 F40.", "M30", "%"].join("\n");

function input(over: Partial<AuditGateInput> = {}): AuditGateInput {
  return {
    parsed: parseNC(CLEAN),
    originalStored: true,
    digest: "a".repeat(64),
    toolsInProgram: [1],
    toolsMapped: [1],
    machineKnown: true,
    axisAccelKnown: true,
    stockBound: true,
    materialMatched: true,
    compedSegments: 0,
    tappingSegments: 0,
    ...over,
  };
}

test("a fully-contexted clean program: audit PASS, optimization REVIEW (alignment is always an assumption)", () => {
  const r = evaluateAuditGates(input());
  assert.equal(r.stages.audit, "PASS");
  // Stock alignment is REVIEW by construction — CANVAS cannot see the vise.
  assert.equal(r.stages.optimization, "REVIEW");
  assert.ok(r.gates.find((g) => g.id === "stock-alignment")!.detail.includes("cannot see the vise"));
});

test("an unstored original is a FAIL, and the worst gate rules every stage", () => {
  const r = evaluateAuditGates(input({ originalStored: false, digest: null }));
  assert.equal(r.gates.find((g) => g.id === "file-integrity")!.status, "FAIL");
  assert.equal(r.stages.audit, "FAIL");
  assert.equal(r.stages.optimization, "FAIL");
  assert.equal(r.stages.exportPrereqs, "FAIL");
});

test("a parser refusal fails fidelity and names the line", () => {
  const bad = parseNC(["%", "G20 G90", "#100 = 5", "G1 X1 F10", "%"].join("\n"));
  const r = evaluateAuditGates(input({ parsed: bad }));
  const gate = r.gates.find((g) => g.id === "parser-fidelity")!;
  assert.equal(gate.status, "FAIL");
  assert.ok(gate.detail.includes("line 3"));
});

test("unmapped tools are INSUFFICIENT_DATA, named individually — never averaged into a pass", () => {
  const r = evaluateAuditGates(input({ toolsInProgram: [1, 3, 7], toolsMapped: [1] }));
  const gate = r.gates.find((g) => g.id === "tool-mapping")!;
  assert.equal(gate.status, "INSUFFICIENT_DATA");
  assert.ok(gate.detail.includes("T3, T7"));
  assert.equal(r.stages.optimization, "INSUFFICIENT_DATA");
  // The audit stage does not depend on tool mapping.
  assert.equal(r.stages.audit, "PASS");
});

test("assumed units downgrade the audit stage to REVIEW", () => {
  const noUnits = parseNC(["%", "G90 G17", "T1 M6", "S5000 M3", "G1 X1 F10", "%"].join("\n"));
  assert.equal(noUnits.unitsExplicit, false);
  const r = evaluateAuditGates(input({ parsed: noUnits }));
  assert.equal(r.gates.find((g) => g.id === "units")!.status, "REVIEW");
});

test("no stock means engagement is INSUFFICIENT_DATA — bands are never claimed from nothing", () => {
  const r = evaluateAuditGates(input({ stockBound: false }));
  assert.equal(r.gates.find((g) => g.id === "engagement-model")!.status, "INSUFFICIENT_DATA");
  assert.equal(r.gates.find((g) => g.id === "stock-alignment")!.status, "INSUFFICIENT_DATA");
  assert.equal(r.stages.optimization, "INSUFFICIENT_DATA");
});

test("comped and tapping segments are declared excluded from scope, not hidden", () => {
  const r = evaluateAuditGates(input({ compedSegments: 4, tappingSegments: 2 }));
  const gate = r.gates.find((g) => g.id === "optimization-scope")!;
  assert.ok(gate.detail.includes("4 comped"));
  assert.ok(gate.detail.includes("never retimed"));
});

/* ---- what arrived decides what the audit can claim ---- */

/**
 * The parser reads Fanuc-style word address. Run against Heidenhain
 * conversational it produces motion that means nothing — and every gate below
 * parser-fidelity reasons over that motion. Before the file's dialect was
 * recorded, a Heidenhain program came back REVIEW.
 */

const source = (over: Partial<NonNullable<AuditGateInput["source"]>> = {}) => ({
  encoding: "US_ASCII" as const,
  lineEnding: "LF" as const,
  controllerFamily: null,
  ...over,
});

test("a dialect this parser does not read fails, it does not warn", () => {
  for (const family of ["HEIDENHAIN", "SIEMENS"] as const) {
    const r = evaluateAuditGates(input({ source: source({ controllerFamily: family }) }));
    const fidelity = r.gates.find((g) => g.id === "parser-fidelity");
    assert.equal(fidelity?.status, "FAIL", `a ${family} program is not a note, it is unreadable`);
    assert.equal(r.stages.audit, "FAIL", `a ${family} program still lets the audit stage pass`);
  }
});

test("word address, which is what it does read, is not penalised", () => {
  const r = evaluateAuditGates(input({ source: source({ controllerFamily: "FANUC_STYLE" }) }));
  assert.notEqual(r.gates.find((g) => g.id === "parser-fidelity")?.status, "FAIL");
});

test("a file with no determinable dialect is not treated as foreign", () => {
  // Null is "the file does not say", never "wrong controller".
  const r = evaluateAuditGates(input({ source: source({ controllerFamily: null }) }));
  assert.notEqual(r.gates.find((g) => g.id === "parser-fidelity")?.status, "FAIL");
});

test("mixed line endings are reported rather than silently normalised", () => {
  const r = evaluateAuditGates(input({ source: source({ lineEnding: "MIXED" }) }));
  const fidelity = r.gates.find((g) => g.id === "parser-fidelity");
  assert.equal(fidelity?.status, "REVIEW");
  assert.match(fidelity!.detail, /mixes line endings/);
});

test("bytes with no declared codepage drop file integrity to review", () => {
  const r = evaluateAuditGates(input({ source: source({ encoding: "EIGHT_BIT_UNKNOWN" }) }));
  const integrity = r.gates.find((g) => g.id === "file-integrity");
  assert.equal(integrity?.status, "REVIEW");
  assert.match(integrity!.detail, /may not be what was typed/);
});

test("the encoding and line ending are stated on the integrity gate", () => {
  const r = evaluateAuditGates(input({ source: source({ encoding: "US_ASCII", lineEnding: "CRLF" }) }));
  const integrity = r.gates.find((g) => g.id === "file-integrity");
  assert.equal(integrity?.status, "PASS");
  assert.match(integrity!.detail, /US-ASCII/);
  assert.match(integrity!.detail, /CRLF/);
});

test("a generated program with nothing to inspect is not penalised for it", () => {
  // No upload, no source facts. The gates say nothing rather than assume.
  const r = evaluateAuditGates(input({}));
  assert.notEqual(r.gates.find((g) => g.id === "parser-fidelity")?.status, "FAIL");
  assert.equal(r.gates.find((g) => g.id === "file-integrity")?.status, "PASS");
});

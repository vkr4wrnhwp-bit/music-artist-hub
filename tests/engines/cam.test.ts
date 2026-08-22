import { test } from "node:test";
import assert from "node:assert/strict";
import { generateToolpath, parseThreadPitch, parseThreadMajor } from "@/lib/engines/cam/engine";
import { getPost, verifyNc, preflightPassed, type PreflightItem } from "@/lib/engines/cam/post";
import type { MachiningContext, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Tool, MachineProfile } from "@/lib/domain/shop";

/**
 * The CAM engine emits executable machine motion. These tests pin the rules
 * that make that safe: refusals stay refusals, tapping feed stays locked to
 * the thread, and the pre-flight aggregate stays worst-case.
 */

const stock: Stock = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" };

const boringHead = {
  id: "t9", toolNumber: 9, toolClass: "BORING_TOOL", description: "boring head", diameter: 1.5748,
  cornerRadius: 0, flutes: 1, material: "CARBIDE", fluteLength: 0.75, overallLength: 4, stickout: 2.2,
  holder: "CAT40", holderNoseDiameter: 1.75, maxRPM: 2000, recommendedMaterials: [],
  chiploadMin: 0.001, chiploadMax: 0.003, sfmMin: 400, sfmMax: 700, coolant: "FLOOD", lifeRemaining: 1,
  condition: "GOOD", regrindCount: 0,
} as unknown as Tool;
const endmill = { ...boringHead, id: "t2", toolClass: "FLAT_END_MILL", diameter: 0.5, flutes: 3, maxRPM: 8100 } as Tool;
const tap = { ...boringHead, id: "t10", toolNumber: 10, toolClass: "TAP", diameter: 0.25, maxRPM: 4000, sfmMin: 30, sfmMax: 60 } as Tool;

const ctx = (tool: Tool): MachiningContext => ({
  tool, materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
});

const bore = {
  id: "f1", kind: "BORE", label: "40 mm bearing bore", functionalRole: "BEARING_SEAT", critical: true,
  centerX: 0, centerY: 0, diameter: 1.5748, depth: 0.7, through: true, top: 0,
} as unknown as Feature;
const tapped = {
  id: "f2", kind: "TAPPED_HOLE", label: "1/4-20 hole", functionalRole: "MOUNTING_HOLE", critical: false,
  centerX: -2.25, centerY: -1.375, diameter: 0.201, depth: 0.625, through: true, top: 0, thread: "1/4-20 UNC",
} as unknown as Feature;

const req = (type: OperationRequest["type"]): OperationRequest => ({
  id: "op", type, label: "op", featureId: "f", toolId: "t", setupId: "s",
  topZ: 0, finalZ: -0.7, clearanceZ: 0.1, retractZ: 1,
});

/* ---- thread parsing: deterministic, refuses to guess ---- */

test("parseThreadPitch reads UNC, numbered and metric forms", () => {
  assert.equal(parseThreadPitch("1/4-20 UNC"), 1 / 20);
  assert.equal(parseThreadPitch("#10-32"), 1 / 32);
  assert.equal(parseThreadPitch("5/16-18"), 1 / 18);
  assert.equal(parseThreadPitch("M6x1.0"), 1.0 / 25.4);
  assert.equal(parseThreadPitch("M8×1.25"), 1.25 / 25.4);
});

test("parseThreadPitch returns null rather than inventing a pitch", () => {
  assert.equal(parseThreadPitch("smooth bore"), null);
  assert.equal(parseThreadPitch(""), null);
});

test("parseThreadMajor reads fraction, numbered and metric majors", () => {
  assert.equal(parseThreadMajor("1/4-20 UNC"), 0.25);
  assert.ok(Math.abs(parseThreadMajor("#10-32")! - 0.19) < 1e-9);
  assert.ok(Math.abs(parseThreadMajor("M6x1.0")! - 6 / 25.4) < 1e-9);
});

/* ---- BORE ---- */

test("boring head at size produces plunge + feed-out spring pass", () => {
  const r = generateToolpath(req("BORE"), bore, ctx(boringHead), stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.ok(!r.toolpath.isPlaceholder);
  assert.equal(Math.min(...r.toolpath.moves.map((m) => m.z)), -0.7);
  assert.ok(r.toolpath.moves.some((m) => m.type === "RETRACT" && m.feed !== null), "feed-out retract missing");
});

test("boring head set to the wrong diameter is refused, not adjusted", () => {
  const wrong = { ...boringHead, diameter: 1.25 } as Tool;
  const r = generateToolpath(req("BORE"), bore, ctx(wrong), stock);
  assert.ok(!r.ok);
});

test("helical bore stays on the wall radius and never climbs", () => {
  const r = generateToolpath(req("BORE"), bore, ctx(endmill), stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  const cuts = r.toolpath.moves.filter((m) => m.type === "CUT");
  const pathR = 1.5748 / 2 - 0.25;
  for (const m of cuts) assert.ok(Math.abs(Math.hypot(m.x, m.y) - pathR) < 1e-6);
  let last = Infinity;
  for (const m of cuts) {
    assert.ok(m.z <= last + 1e-9, "helix z climbed");
    last = m.z;
  }
});

test("bore refuses a drill, and an end mill not smaller than the hole", () => {
  const drill = { ...boringHead, toolClass: "DRILL", diameter: 0.201 } as Tool;
  assert.ok(!generateToolpath(req("BORE"), bore, ctx(drill), stock).ok);
  const big = { ...endmill, diameter: 1.75 } as Tool;
  assert.ok(!generateToolpath(req("BORE"), bore, ctx(big), stock).ok);
});

/* ---- TAP ---- */

test("tap locks feed to rpm × pitch and caps rpm", () => {
  const r = generateToolpath(req("TAP"), tapped, ctx(tap), stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  const p = r.toolpath.parameters;
  assert.ok(p.rpm <= 800);
  assert.equal(p.feed, Number((p.rpm * 0.05).toFixed(2)));
  assert.ok(r.toolpath.moves.some((m) => m.type === "RETRACT" && m.feed === p.feed), "reversal must be a feed move");
});

test("tap refuses a non-tap tool, a missing thread, and an unparseable thread", () => {
  assert.ok(!generateToolpath(req("TAP"), tapped, ctx(endmill), stock).ok);
  const noThread = { ...(tapped as object), thread: undefined } as Feature;
  assert.ok(!generateToolpath(req("TAP"), noThread, ctx(tap), stock).ok);
  const bad = { ...(tapped as object), thread: "quarter twenty" } as Feature;
  assert.ok(!generateToolpath(req("TAP"), bad, ctx(tap), stock).ok);
});

/* ---- posts ---- */

const machine = {
  id: "m", manufacturer: "Haas", model: "VF-2", controller: "HAAS_NGC",
  travelsX: 30, travelsY: 16, travelsZ: 20, maxSpindleRPM: 8100, spindleTaper: "CAT40",
  maxFeed: 500, rapidRate: 1000, toolCapacity: 20, hasToolChanger: true, accuracy: 0.0002,
} as unknown as MachineProfile;

const postCtx = {
  programNumber: "2507", programName: "test", machine, workOffset: "G54", units: "IN" as const,
  toolTable: [
    { toolNumber: 9, description: "boring head", lengthOffset: 9, diameter: 1.5748 },
    { toolNumber: 10, description: "1/4-20 tap", lengthOffset: 10, diameter: 0.25 },
  ],
  safeZ: 1, partName: "test", revision: "A", generatedAtIso: "2026-08-10T00:00:00Z",
};

test("Haas post emits a G84 canned cycle with no M3, closed by G80, and lints clean", () => {
  const rb = generateToolpath(req("BORE"), bore, ctx(boringHead), stock);
  const rt = generateToolpath(req("TAP"), tapped, ctx(tap), stock);
  assert.ok(rb.ok && rt.ok);
  if (!rb.ok || !rt.ok) return;
  const nc = getPost("haas-ngc-dev")!.emit([rb.toolpath, rt.toolpath], postCtx);
  assert.match(nc, /G84 Z-0\.700 R0\.100 F\d+\.\d\d/);
  assert.ok(nc.includes("G80"));
  const tapBlock = nc.slice(nc.indexOf("RIGID TAP"), nc.indexOf("G80"));
  assert.ok(!/\bM3\b/.test(tapBlock), "G84 owns the spindle; no M3 in the tap block");
  assert.equal(verifyNc(nc, machine).filter((i) => i.severity === "ERROR").length, 0);
});

test("GRBL post refuses the tap instead of emitting unsynchronised moves", () => {
  const rt = generateToolpath(req("TAP"), tapped, ctx(tap), stock);
  assert.ok(rt.ok);
  if (!rt.ok) return;
  const nc = getPost("grbl-dev")!.emit([rt.toolpath], postCtx);
  assert.ok(nc.includes("GRBL CANNOT RIGID TAP"));
  assert.ok(!/G1 .*Z-0\.7/.test(nc));
});

/* ---- pre-flight aggregate ---- */

const item = (status: PreflightItem["status"], required: boolean): PreflightItem => ({
  id: "x", label: "x", detail: "", status, required,
});

test("preflightPassed is worst-case: one failing required item fails the list", () => {
  assert.equal(preflightPassed([item("PASS", true), item("PASS", true)]), true);
  assert.equal(preflightPassed([item("PASS", true), item("FAIL", true)]), false);
  assert.equal(preflightPassed([item("PASS", true), item("PENDING", true)]), false);
  // A non-required failure does not block. That is what "required" means.
  assert.equal(preflightPassed([item("PASS", true), item("FAIL", false)]), true);
});

/* ---- what verifyNc has to catch before a program reaches a machine ---- */

test("a program whose every move is a rapid is an ERROR, not a clean program", () => {
  // Inverting one line of the post so every CUTTING move came out as G0 —
  // the machine driving into the material at traverse — passed all twelve
  // tests here and produced zero errors from verifyNc. This is the NC
  // VERIFICATION stage of the pipeline; it has to notice that.
  const allRapid = ["G20", "G17 G40 G49 G80 G90", "M3 S5000", "G0 X0. Y0. Z-0.500", "G0 X1. Y0. Z-0.500", "M5", "M30"].join("\n");
  const errors = verifyNc(allRapid, machine).filter((i) => i.severity === "ERROR");
  assert.ok(errors.some((e) => /no feed moves|every move is a rapid/i.test(e.message)), `got [${errors.map((e) => e.message).join(" | ")}]`);
});

test("a cutting move with a malformed feed word is an ERROR", () => {
  // "Fnull" reaches the control as a bad block: it faults, or it silently
  // runs the move at whatever feed was last modal. Either way it is not the
  // feed the CAM engine computed.
  const bad = ["G20", "G17 G40 G49 G80 G90", "M3 S5000", "G1 X1. Y0. Z-0.100 Fnull.", "M5", "M30"].join("\n");
  const errors = verifyNc(bad, machine).filter((i) => i.severity === "ERROR");
  assert.ok(errors.some((e) => /malformed feed/i.test(e.message)), `got [${errors.map((e) => e.message).join(" | ")}]`);
});

test("cutting with no feed rate ever commanded is an ERROR", () => {
  const noFeed = ["G20", "G17 G40 G49 G80 G90", "M3 S5000", "G1 X1. Y0. Z-0.100", "M5", "M30"].join("\n");
  const errors = verifyNc(noFeed, machine).filter((i) => i.severity === "ERROR");
  assert.ok(errors.some((e) => /no feed rate is ever commanded/i.test(e.message)));
});

test("a program with no G40 is flagged — the last program's cutter comp is still live", () => {
  const noG40 = ["G20", "G17 G90", "M3 S5000", "G1 X1. Y0. Z-0.100 F20.", "M5", "M30"].join("\n");
  assert.ok(verifyNc(noG40, machine).some((i) => /G40/.test(i.message)));
});

test("a program that ends with the spindle running is flagged", () => {
  const spinning = ["G20", "G17 G40 G49 G80 G90", "M3 S5000", "G1 X1. Y0. Z-0.100 F20.", "M30"].join("\n");
  assert.ok(verifyNc(spinning, machine).some((i) => /spindle still commanded on/i.test(i.message)));
});

test("every shipped post emits a program that passes its own verifier", () => {
  // Six posts, one assertion: whatever dialect, the emitted program has to
  // survive the stage that stands between it and a machine.
  const rb = generateToolpath(req("BORE"), bore, ctx(boringHead), stock);
  assert.ok(rb.ok);
  if (!rb.ok) return;
  for (const id of ["haas-ngc-dev", "fanuc-dev", "pathpilot-dev", "siemens-840d-dev", "heidenhain-dev", "grbl-dev"]) {
    const post = getPost(id);
    assert.ok(post, `${id} is not registered`);
    const nc = post.emit([rb.toolpath], postCtx);
    const errors = verifyNc(nc, machine).filter((i) => i.severity === "ERROR");
    assert.deepEqual(errors.map((e) => e.message), [], `${id} emitted a program with errors`);
  }
});

test("no shipped post is marked certified", () => {
  // Principle 5: an unimplemented or unvalidated capability stays labelled.
  // These are development posts and the UI says so; the registry must not
  // quietly disagree with it.
  for (const id of ["haas-ngc-dev", "fanuc-dev", "pathpilot-dev", "siemens-840d-dev", "heidenhain-dev", "grbl-dev"]) {
    assert.equal(getPost(id)!.certified, false, `${id} claims to be certified`);
  }
});

test("a dialect the verifier cannot read is declared unverified, not clean", () => {
  // Heidenhain conversational is a different language, and every G-code rule
  // misread it: a valid TNC program came back with "No units word (G20/G21)"
  // as an ERROR. Coming back clean instead would be worse — clean is what an
  // operator reads as verified.
  const rb = generateToolpath(req("BORE"), bore, ctx(boringHead), stock);
  assert.ok(rb.ok);
  if (!rb.ok) return;
  const nc = getPost("heidenhain-dev")!.emit([rb.toolpath], postCtx);
  const issues = verifyNc(nc, machine);
  assert.equal(issues.filter((i) => i.severity === "ERROR").length, 0, "no invented errors");
  assert.ok(issues.some((i) => /cannot check this dialect/i.test(i.message)), "and it says it did not verify");
});

import { test } from "node:test";
import assert from "node:assert/strict";
import { generateToolpath } from "@/lib/engines/cam/engine";
import { parseThreadPitch, parseThreadMajor } from "@/lib/engines/cam/thread";
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
  tool, partFeatures: [], materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
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
    { toolNumber: 9, description: "boring head", lengthOffset: 9, diameterOffset: 9, diameter: 1.5748 },
    { toolNumber: 10, description: "1/4-20 tap", lengthOffset: 10, diameterOffset: 10, diameter: 0.25 },
  ],
  safeZ: 1, partName: "test", revision: "A", generatedAtIso: "2026-08-10T00:00:00Z",
};

test("Haas post emits a G84 canned cycle with no M3, closed by G80, and lints clean", () => {
  const rb = generateToolpath(req("BORE"), bore, ctx(boringHead), stock);
  const rt = generateToolpath(req("TAP"), tapped, ctx(tap), stock);
  assert.ok(rb.ok && rt.ok);
  if (!rb.ok || !rt.ok) return;
  const nc = getPost("haas-ngc-dev")!.emit([rb.toolpath, rt.toolpath], postCtx);
  // X and Y are on the cycle block itself, not left to the positioning move
  // before it. A cycle block with no axis word relies on "drills at the
  // current position", which is true on some controls and not others; naming
  // the point is unambiguous everywhere and costs two words.
  assert.match(nc, /G98 G84 X-?\d+\.\d+ Y-?\d+\.\d+ Z-0\.700 R0\.100 F\d+\.\d\d/);
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

/* ------------------------------------------------------------------ */
/* Surface speed: the material window, or no motion                    */
/* ------------------------------------------------------------------ */

test("no material record means no toolpath — a default SFM window is another material's numbers", () => {
  // This defaulted to 300-800 SFM, a carbide-in-steel window, for whatever
  // was in the vise. Inconel 718 cuts at roughly 60-100 SFM with carbide:
  // the default is six times that, and the operator reads a plausible
  // S-number in the program.
  const r = generateToolpath(req("BORE"), bore, { ...ctx(boringHead), materialSfmMin: null, materialSfmMax: null, materialName: "Inconel 718" }, stock);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && /no surface speed window on file/i.test(r.error.reason), r.ok ? "" : r.error.reason);
  assert.ok(!r.ok && /Inconel 718/.test(r.error.reason));
  assert.ok(!r.ok && r.error.recommendations.length > 0);
  // Half a window is not a window.
  assert.equal(generateToolpath(req("BORE"), bore, { ...ctx(boringHead), materialSfmMax: null }, stock).ok, false);
  assert.equal(generateToolpath(req("BORE"), bore, { ...ctx(boringHead), materialSfmMin: null }, stock).ok, false);
});

test("a milling cutter not rated for the material is refused, not averaged into a middle number", () => {
  // Tool rated 400-700, material cutting at 60-100: no overlap. Averaging
  // the two windows' endpoints yields a surface speed belonging to neither.
  const slow = { ...ctx(endmill), materialSfmMin: 60, materialSfmMax: 100, materialName: "Inconel 718" };
  const r = generateToolpath(req("BORE"), bore, slow, stock);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && /do not overlap/i.test(r.error.reason), r.ok ? "" : r.error.reason);
});

test("the overlap rule is a milling rule — a tap is not refused by it", () => {
  // The material record's SFM window is a MILLING window. A tap runs at a
  // fraction of it by design; refusing it here would refuse a correct
  // operation. The tap is rated 30-60 against aluminium's 600-1000.
  const r = generateToolpath({ ...req("TAP"), finalZ: -0.625 }, tapped, ctx(tap), stock);
  assert.equal(r.ok, true, r.ok ? "" : r.error.reason);
});

test("surface speed lands inside both windows where they overlap", () => {
  // The clamp used to widen to min/max of the two — the union, not the
  // intersection — so the midpoint could be pulled outside both.
  const c = { ...ctx(endmill), materialSfmMin: 650, materialSfmMax: 900 }; // tool 400-700
  const r = generateToolpath(req("BORE"), bore, c, stock);
  assert.equal(r.ok, true, r.ok ? "" : r.error.reason);
  if (!r.ok) return;
  const sfm = r.toolpath.parameters.sfm;
  assert.ok(sfm >= 650 && sfm <= 700, `SFM ${sfm} is outside the 650-700 intersection`);
});

test("where the windows do not overlap the tool's own rating wins, not a number between them", () => {
  // The tap is rated 30-60 SFM; aluminium is quoted 600-1000 for milling.
  // The old expression averaged max(30,600)=600 with min(60,1000)=60 to get
  // 330 SFM — strictly between the two windows and inside neither, which on
  // a ⌀0.25 tap is over eleven thousand rpm before the tapping cap catches
  // it. A tap runs at the tap's rating.
  const r = generateToolpath({ ...req("TAP"), finalZ: -0.625 }, tapped, ctx(tap), stock);
  assert.equal(r.ok, true, r.ok ? "" : r.error.reason);
  if (!r.ok) return;
  const sfm = r.toolpath.parameters.sfm;
  assert.ok(sfm >= 30 && sfm <= 60, `SFM ${sfm} is outside the tap's own 30-60 rating`);
  // And the emitted spindle speed follows from it rather than from the cap.
  assert.ok(r.toolpath.parameters.rpm < 800, `rpm ${r.toolpath.parameters.rpm} is the tapping cap, not the tap's rating`);
});

/* ------------------------------------------------------------------ */
/* Pocket entry — no end mill is plunged into solid material           */
/* ------------------------------------------------------------------ */

const rectPocket = {
  id: "fp", kind: "RECT_POCKET", label: "pocket", functionalRole: "CLEARANCE", critical: false,
  centerX: 0, centerY: 0, width: 2.0, length: 1.5, depth: 0.5, cornerRadius: 0.25, top: 0,
} as unknown as Feature;

const roundPocket = {
  id: "fc", kind: "CIRC_POCKET", label: "round pocket", functionalRole: "CLEARANCE", critical: false,
  centerX: 0, centerY: 0, diameter: 1.5, depth: 0.5, top: 0,
} as unknown as Feature;

/** Straight-down moves: same X and Y as the move before, going deeper. */
const straightPlunges = (moves: { type: string; x: number; y: number; z: number }[]) =>
  moves.filter((m, i) => i > 0 && m.type === "PLUNGE" && m.x === moves[i - 1].x && m.y === moves[i - 1].y && m.z < moves[i - 1].z);

test("a pocket is entered by helix, never plunged straight into solid material", () => {
  // A standard end mill has no cutting edge at its centre — the flutes stop
  // short of the axis. Plunged straight down it rubs rather than cuts, the
  // centre heats, and the tool snaps. The adaptive engine already knew this
  // ("full depth means no straight plunge"); the pocket routine beside it
  // plunged at the pocket centre under a comment claiming a helix it did
  // not perform.
  for (const [name, feature] of [["rect", rectPocket], ["circular", roundPocket]] as const) {
    const r = generateToolpath(req("POCKET_2D"), feature, ctx(endmill), stock);
    assert.equal(r.ok, true, r.ok ? "" : r.error.reason);
    if (!r.ok) return;
    assert.deepEqual(
      straightPlunges(r.toolpath.moves),
      [],
      `${name} pocket plunges straight down — that is a broken end mill`,
    );
    // And the entry is a real helix: plunge moves that change X/Y while
    // descending, around the pocket centre.
    const helical = r.toolpath.moves.filter(
      (m, i) => i > 0 && m.type === "PLUNGE" && (m.x !== r.toolpath.moves[i - 1].x || m.y !== r.toolpath.moves[i - 1].y),
    );
    assert.ok(helical.length > 10, `${name} pocket has no helical entry (${helical.length} moves)`);
  }
});

test("adaptive clearing keeps the rule it already had", () => {
  const r = generateToolpath(req("ADAPTIVE_2D"), rectPocket, ctx(endmill), stock);
  assert.equal(r.ok, true, r.ok ? "" : r.error.reason);
  if (!r.ok) return;
  assert.deepEqual(straightPlunges(r.toolpath.moves), []);
});

test("a pocket too tight to helix is refused, not plunged on an assumption", () => {
  // CANVAS records no centre-cutting flag, so entering straight down is a
  // gamble on the tool. It says that rather than taking it.
  // 0.530 leaves a 0.005" swing for a 0.5" mill — under the 0.015" floor.
  // (0.560 was the first guess and still helixes fine at 0.020".)
  const tight = { ...(rectPocket as unknown as Record<string, unknown>), width: 0.53, length: 0.53 } as unknown as Feature;
  const r = generateToolpath(req("POCKET_2D"), tight, ctx(endmill), stock);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && /centre-cutting/i.test(r.error.reason), r.ok ? "" : r.error.reason);
  assert.ok(!r.ok && r.error.recommendations.some((x) => /start hole/i.test(x)));
});

test("the helix descends only from the depth already cleared", () => {
  // Each pass helixes from the previous pass's floor, not from the top of
  // the stock — re-cutting air is slow, and re-entering at full depth is
  // the straight plunge this fix exists to prevent.
  const r = generateToolpath({ ...req("POCKET_2D"), finalZ: -0.5 }, rectPocket, ctx(endmill), stock);
  assert.equal(r.ok, true);
  if (!r.ok) return;
  const deepest = Math.min(...r.toolpath.moves.map((m) => m.z));
  assert.ok(deepest >= -0.5 - 1e-9, `cut past the requested depth to ${deepest}`);
});

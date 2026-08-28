/* The Live engine, checked against a manifest this repository actually emits.
 *
 * static/js/livelab.js is bundled out of the TypeScript packages Live Lab was
 * written in. Python never runs it, so nothing in the pytest suite can tell
 * whether live_store.set_manifest() still produces something the engine will
 * accept - and the engine validates the project with zod, so a field this
 * repository renames is not a cosmetic problem. It is a set that refuses to
 * open, discovered at a venue.
 *
 * This is the contract test between the two halves. The manifest below is the
 * shape live_store.set_manifest() builds; tests/test_live.py asserts that the
 * real function still matches it, and this file asserts the engine still
 * accepts it. Either half moving on its own fails one of them.
 *
 *     node tests/js/check_livelab.js
 */
"use strict";

const fs = require("fs");
const path = require("path");

const bundle = path.join(__dirname, "..", "..", "static", "js", "livelab.js");
const source = fs.readFileSync(bundle, "utf8");

/* The bundle is a classic script that hangs itself off a global. Handing it
   empty stand-ins for the browser globals is enough to load it: nothing here
   touches an AudioContext until TestAudioBackend is asked to. */
const scope = {};
const SB = new Function(
  "globalThis", "window", "self", "navigator", "document",
  source + "; return globalThis.SBLive;"
)(scope, scope, scope, {}, {});

let passed = 0;
let failed = 0;

function check(label, fn) {
  try {
    fn();
    console.log("PASS  " + label);
    passed++;
  } catch (err) {
    console.log("FAIL  " + label + "  -> " + String(err.message).split("\n")[0]);
    failed++;
  }
}

// --- the bundle itself -------------------------------------------------------

check("the bundle exposes the four engine namespaces", () => {
  for (const name of ["engine", "midi", "cache", "project"]) {
    if (!SB || !SB[name]) throw new Error("missing " + name);
  }
});

// --- MIDI, against the published wire protocol -------------------------------
// These are not self-consistency checks: MIDI 1.0 says what these bytes mean.

check("0x90 is note on, channel 0", () => {
  const m = SB.midi.parseMidiMessage([0x90, 60, 100]);
  if (m.type !== "note_on" || m.channel !== 0) throw new Error(JSON.stringify(m));
});

check("0x81 is note off, channel 1", () => {
  const m = SB.midi.parseMidiMessage([0x81, 60, 0]);
  if (m.type !== "note_off" || m.channel !== 1) throw new Error(JSON.stringify(m));
});

check("0xB2 is a control change on channel 2", () => {
  const m = SB.midi.parseMidiMessage([0xB2, 7, 64]);
  if (m.type !== "cc" || m.channel !== 2 || m.noteOrController !== 7) {
    throw new Error(JSON.stringify(m));
  }
});

check("note on with velocity 0 is a note off", () => {
  const m = SB.midi.parseMidiMessage([0x90, 60, 0]);
  if (m.type !== "note_off") throw new Error(m.type);
});

check("the parsed field is noteOrController, not data1", () => {
  const m = SB.midi.parseMidiMessage([0x90, 62, 100]);
  if (m.noteOrController !== 62) throw new Error(JSON.stringify(m));
  if ("data1" in m) throw new Error("data1 exists again - perform.html reads noteOrController");
});

check("WebMidiSource is created through its factory, not new", () => {
  if (typeof SB.midi.WebMidiSource.create !== "function") {
    throw new Error("no static create()");
  }
});

// --- the manifest contract ---------------------------------------------------

function manifest() {
  const org = "street-banker";
  const setId = "set-1";
  const itemId = "item-scene-1";
  return {
    projectId: setId,
    masterTempo: 128,
    timeSignature: "4/4",
    items: [{
      id: itemId, organizationId: org, liveProjectId: setId, sortOrder: 0,
      type: "song", title: "Intro", sourceReleaseId: null, sourceTrackId: null,
      bpm: 128, key: null, durationMs: null, notes: "",
    }],
    scenes: [{
      id: "scene-1", organizationId: org, liveProjectId: setId,
      liveSetItemId: itemId, name: "Intro", sceneType: "custom", sortOrder: 0,
      color: "", bpm: null, key: null, bars: null, quantization: "1bar",
      loopEnabled: false, followAction: "next_scene", followTargetSceneId: null,
    }],
    clips: [{
      id: "clip-stem-1", organizationId: org, liveProjectId: setId,
      liveSceneId: "scene-1", name: "Vocal", sourceAssetId: "stem-1",
      startMs: 0, endMs: null, loopStartMs: null, loopEndMs: null,
    }],
    stems: [{
      id: "stem-1", organizationId: org, liveProjectId: setId,
      liveSetItemId: itemId, stemType: "vocal", label: "Vocal",
      sourceAssetId: "stem-1", gain: 1, pan: 0, muted: false, solo: false,
      outputId: "master",
    }],
    padMap: SB.project.defaultPadMap(),
  };
}

const backend = new SB.engine.TestAudioBackend();
const engine = new SB.engine.LiveAudioEngine(backend);

check("the engine accepts a manifest of the shape live_store emits", () => {
  engine.loadProject(manifest());
});

check("a song from that manifest can be started", () => {
  engine.startSong("item-scene-1");
});

check("beatNow reports a number", () => {
  if (typeof engine.beatNow() !== "number") throw new Error("not a number");
});

check("a scene launch returns a launch beat rather than firing instantly", () => {
  const res = engine.triggerScene("scene-1");
  if (!res || typeof res.launchBeat !== "number") {
    throw new Error("no launch beat: " + JSON.stringify(res));
  }
});

check("tick does not throw", () => { engine.tick(); });

check("stem mute and solo are addressable by the ids live_store issues", () => {
  if (engine.setStemMuted("stem-1", true) !== true) throw new Error("mute refused");
  if (engine.setStemSolo("stem-1", true) !== true) throw new Error("solo refused");
});

check("stopAll does not throw", () => { engine.stopAll(); });

check("pad 15 is STOP, where it must always be", () => {
  const pads = SB.project.defaultPadMap();
  if (pads[15].mode !== "stop") throw new Error(pads[15].mode);
});

// --- the vocabulary both halves share ----------------------------------------

check("the enums live_store copies still say what it thinks", () => {
  const expected = {
    FOLLOW_ACTIONS: ["stop", "loop", "next_scene", "target"],
    QUANTIZATIONS: ["none", "1/4", "1/2", "1bar", "2bars", "4bars", "scene_end"],
    STEM_TYPES: ["vocal", "drums", "bass", "music", "fx", "click", "custom"],
  };
  for (const [name, want] of Object.entries(expected)) {
    const got = SB.project[name];
    if (!got) throw new Error(name + " is gone from the engine");
    if (JSON.stringify([...got]) !== JSON.stringify(want)) {
      throw new Error(name + " changed: " + JSON.stringify([...got]));
    }
  }
});

console.log("");
console.log(passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);

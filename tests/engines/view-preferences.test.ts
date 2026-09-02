import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  DEFAULT_ENVIRONMENT,
  VIEW_PRESETS,
  ANNOTATION_SCALE,
  lightRig,
  parseHexColor,
  preferLocalEnvironment,
  sectionStroke,
  semanticConflicts,
} from "@/lib/view-environment";

/**
 * The picker chain, from the field a machinist types in to the row that comes
 * back on the next load. Every defect pinned here presented the same way —
 * "I changed the colour and nothing happened" — for a different reason.
 */

/* ---- which copy survives a reload ---- */

test("a change made after the server row was written wins", () => {
  assert.equal(preferLocalEnvironment("2026-09-02T10:00:01Z", "2026-09-02T10:00:00Z"), true);
});

test("a stale local copy yields to a newer server row", () => {
  assert.equal(preferLocalEnvironment("2026-09-01T10:00:00Z", "2026-09-02T10:00:00Z"), false);
});

test("with no server row the browser's copy stands", () => {
  assert.equal(preferLocalEnvironment("2026-09-02T10:00:00Z", null), true);
  assert.equal(preferLocalEnvironment(null, null), true);
});

test("a browser that has never saved yields to the server", () => {
  assert.equal(preferLocalEnvironment(null, "2026-09-02T10:00:00Z"), false);
});

test("an unreadable stamp keeps what is on screen rather than replacing it", () => {
  // The failure to avoid is silently discarding a colour the machinist can
  // see. Keeping it costs a stale preference; discarding it costs their work.
  assert.equal(preferLocalEnvironment("not a date", "2026-09-02T10:00:00Z"), true);
  assert.equal(preferLocalEnvironment("2026-09-02T10:00:00Z", "not a date"), true);
});

test("identical stamps are not treated as a local change", () => {
  const t = "2026-09-02T10:00:00Z";
  assert.equal(preferLocalEnvironment(t, t), false);
});

/* ---- the hex field ---- */

test("a hex colour is accepted with or without the hash, and normalised", () => {
  assert.equal(parseHexColor("#1B2530"), "#1b2530");
  assert.equal(parseHexColor("1b2530"), "#1b2530");
  assert.equal(parseHexColor("  #1b2530 "), "#1b2530");
});

test("a half-typed colour is refused rather than persisted", () => {
  for (const partial of ["#", "#0", "#0b", "#0b7", "#0b72", "#0b72f", ""]) {
    assert.equal(parseHexColor(partial), null, `${partial} must not read as a colour`);
  }
});

test("three-digit and named colours are refused — the contrast maths cannot read them", () => {
  // This is the real danger: an unparseable ground returns null from every
  // check, so it passes the semantic-conflict test by never being tested.
  assert.equal(parseHexColor("#fff"), null);
  assert.equal(parseHexColor("red"), null);
  assert.equal(parseHexColor("#gggggg"), null);
  assert.equal(semanticConflicts("#fff").length, 0, "an unreadable ground reports no conflicts — hence the refusal upstream");
});

test("the drawer never writes an unparsed value into the environment", () => {
  const src = readFileSync("src/components/workspace/view-environment-drawer.tsx", "utf8");
  // The swatch is exempt: `input type="color"` yields `#rrggbb` by spec. It
  // is the free-text field that could hand over "#0b".
  assert.ok(
    !/aria-label=\{`\$\{name\} hex`\}[\s\S]{0,200}?e\.target\.value/.test(src),
    "the hex text field writes raw input straight into the environment",
  );
  assert.ok(/<HexField/.test(src), "the hex field is not going through the parser");
  assert.ok(/parseHexColor\(/.test(src), "the drawer commits colours without parsing them");
});

/* ---- the floor belongs to the preset, not to the renderer ---- */

test("a preset that wants no floor says so itself", () => {
  assert.equal(VIEW_PRESETS.STUDIO_WHITE.env.floorVisible, false);
  assert.equal(DEFAULT_ENVIRONMENT.floorVisible, false);
  // Every other preset keeps its floor, so the control is live on all of them.
  for (const [id, p] of Object.entries(VIEW_PRESETS)) {
    if (id === "STUDIO_WHITE") continue;
    assert.equal(p.env.floorVisible, true, `${id} lost its floor`);
  }
});

test("the renderer draws the floor from the flag, not from the preset's name", () => {
  const src = readFileSync("src/components/viewport/scene.tsx", "utf8");
  assert.ok(
    !/preset !== "STUDIO_WHITE"/.test(src),
    "the scene decides the floor by preset name — the floor controls go dead on that preset and a floor appears the moment it becomes CUSTOM",
  );
});

/* ---- the preset chip tells the truth ---- */

test("any change that is not a preset choice leaves the preset", () => {
  const src = readFileSync("src/components/workspace/view-environment-drawer.tsx", "utf8");
  assert.ok(
    /"preset" in patch/.test(src),
    "the drawer keeps the preset lit for changes it does not enumerate — clicking that chip then discards them",
  );
  assert.ok(
    !/"background" in patch \|\| "floorColor" in patch \|\| "gridColor" in patch/.test(src),
    "only three keys count as customisation; every other control lies about the preset",
  );
});

/* ---- the write actually leaves the browser ---- */

test("a pending preference write is flushed on the way out of the page", () => {
  const src = readFileSync("src/lib/view-environment.ts", "utf8");
  assert.ok(/addEventListener\("pagehide"/.test(src), "the debounced write is lost if the page closes inside the window");
  // The PUT itself must carry it — a `keepalive` that only names a parameter
  // does not stop the browser cancelling the request with the document.
  assert.ok(
    /method: "PUT",[\s\S]{0,240}?\bkeepalive\b/.test(src),
    "the preference PUT does not set keepalive, so a flush on the way out is cancelled with the document",
  );
});

test("the preferences route answers with a status, not a redirect", () => {
  const src = readFileSync("src/app/api/view-preferences/route.ts", "utf8");
  // Match the call, not the comment that explains why it is not used.
  assert.ok(
    !/await requireUser\(\)/.test(src),
    "requireUser redirects; a fetch follows the 307 and parses HTML as JSON, so the write is lost silently",
  );
  // The 401 lives in requireSessionApi now — one guard for every route
  // handler that must not apply the write-role check but must still answer
  // with a status. tenancy.test.ts pins that no route handler does it a third
  // way.
  assert.ok(/requireSessionApi\(\)/.test(src), "the route does not use the session guard");
  assert.ok(/"denied" in gate/.test(src), "the route ignores the guard's denial");
  assert.ok(
    !/requireWriteApi/.test(src),
    "display preferences are not manufacturing data — the write-role gate would deny a viewer their own background",
  );
});

/* ---- the light rig ---- */

/**
 * A machinist reads material and finish off the render before reading any
 * label. One rig tuned for a bright studio ground cannot serve a dark one: on
 * Dark Machine Bay a light aluminium part was lit exactly as on Studio White,
 * because all five light intensities were literals in the scene.
 *
 * The failure these pin is a slider that moves and changes nothing.
 */

test("the default environment reproduces the rig the scene used to hard-code", () => {
  // A new control must not silently restyle every part already looked at.
  assert.deepEqual(lightRig(DEFAULT_ENVIRONMENT), {
    ambient: 0.25,
    hemisphere: 1,
    key: 1.5,
    fill: 0.55,
    rim: 0.4,
  });
});

test("both sliders actually move the lights they name", () => {
  const dim = lightRig({ ...DEFAULT_ENVIRONMENT, ambientLevel: 0, highlightLevel: 0 });
  const bright = lightRig({ ...DEFAULT_ENVIRONMENT, ambientLevel: 1, highlightLevel: 1 });
  assert.ok(bright.ambient > dim.ambient, "Ambient does not move the ambient light");
  assert.ok(bright.hemisphere > dim.hemisphere, "Ambient does not move the hemisphere light");
  assert.ok(bright.key > dim.key, "Highlight does not move the key light");
  assert.ok(bright.fill > dim.fill, "Highlight does not move the fill light");
  assert.ok(bright.rim > dim.rim, "Highlight does not move the rim light");
});

test("each slider moves only its own axis", () => {
  const base = lightRig(DEFAULT_ENVIRONMENT);
  const ambientOnly = lightRig({ ...DEFAULT_ENVIRONMENT, ambientLevel: 1 });
  const keyOnly = lightRig({ ...DEFAULT_ENVIRONMENT, highlightLevel: 1 });
  assert.equal(ambientOnly.key, base.key, "Ambient is reaching the key light");
  assert.equal(keyOnly.ambient, base.ambient, "Highlight is reaching the ambient light");
});

test("at zero the part is dim but not black", () => {
  // A control that can produce a black viewport is a control a machinist will
  // report as a broken renderer.
  const dark = lightRig({ ...DEFAULT_ENVIRONMENT, ambientLevel: 0, highlightLevel: 0 });
  for (const [name, v] of Object.entries(dark)) {
    assert.ok(v > 0, `${name} falls to zero — the form stops reading entirely`);
  }
});

test("every preset states its own lighting, and the dark ones differ", () => {
  for (const [id, p] of Object.entries(VIEW_PRESETS)) {
    assert.equal(typeof p.env.ambientLevel, "number", `${id} does not state an ambient level`);
    assert.equal(typeof p.env.highlightLevel, "number", `${id} does not state a highlight level`);
  }
  // The audit's specific complaint: Studio White, Dark Machine Bay and High
  // Contrast rendered under identical lights.
  const studio = VIEW_PRESETS.STUDIO_WHITE.env;
  for (const id of ["DARK_MACHINE_BAY", "HIGH_CONTRAST", "GRAPHITE", "INSPECTION_GRAY"] as const) {
    const p = VIEW_PRESETS[id].env;
    assert.ok(
      p.ambientLevel !== studio.ambientLevel || p.highlightLevel !== studio.highlightLevel,
      `${id} is lit exactly like Studio White — the preset does not control its own lighting`,
    );
  }
});

test("the scene takes its intensities from the rig, not from literals", () => {
  const src = readFileSync("src/components/viewport/scene.tsx", "utf8");
  assert.ok(/lightRig\(/.test(src), "the scene does not consult the light rig");
  for (const dead of ["intensity={0.25}", "intensity={1.5}", "intensity={0.55}", "intensity={0.4}"]) {
    assert.ok(!src.includes(dead), `a light is still hard-coded at ${dead}`);
  }
  // `args` is a constructor argument: three-fiber re-creates the object rather
  // than updating it, so an intensity passed that way looks live and is not.
  assert.ok(
    !/hemisphereLight args=/.test(src),
    "the hemisphere light takes its intensity as a constructor arg — it will not follow the slider",
  );
});

/* ---- the section drawing and the on-model annotations ---- */

/**
 * `sectionFillColor` and `sectionLineMode` were declared, defaulted, written
 * to localStorage and pushed to the server on every change — and read by
 * nothing at all. Settings a machinist's account carried that did nothing.
 */

test("the section stroke reproduces the drawing as it already was", () => {
  // Wiring a control must not restyle a drawing anyone has looked at. MEDIUM
  // is the default and 1.25 is the width the sketch hard-coded.
  assert.deepEqual(sectionStroke("MEDIUM"), { width: 1.25, opacity: 1 });
  assert.equal(DEFAULT_ENVIRONMENT.sectionLineMode, "MEDIUM");
});

test("OFF drops the cut boundary rather than making it faint", () => {
  // The same answer edgeMode OFF gives for part edges. A floor here would
  // make OFF mean "dim", which is not what was asked for.
  assert.equal(sectionStroke("OFF").opacity, 0);
});

test("the section line mode actually moves the line", () => {
  assert.ok(sectionStroke("STRONG").width > sectionStroke("LIGHT").width);
  assert.ok(sectionStroke("STRONG").opacity >= sectionStroke("LIGHT").opacity);
});

test("the two section fields have a consumer outside their own declaration", () => {
  // This is the whole item: they were dead.
  const sketch = readFileSync("src/components/workspace/section-sketch.tsx", "utf8");
  // BOTH renderers — SectionSketch and FaceSection each draw their own hatch
  // and their own cut boundary, so wiring one and not the other leaves a
  // control that works on bores and does nothing on faces.
  const hatches = (sketch.match(/patternUnits="userSpaceOnUse"/g) ?? []).length;
  assert.ok(hatches >= 2, `expected both section renderers, found ${hatches} hatch patterns`);
  assert.equal(
    (sketch.match(/env\.sectionFillColor/g) ?? []).length,
    hatches,
    "a hatch is still a hard-coded constant in one of the two section renderers",
  );
  assert.equal(
    (sketch.match(/sectionStroke\(env\.sectionLineMode\)/g) ?? []).length,
    hatches,
    "a cut boundary still ignores the section line mode in one of the two renderers",
  );
  assert.ok(!/const HATCH =/.test(sketch), "the old constant is still there and will be used again");
  assert.ok(!/strokeWidth="1\.25"/.test(sketch), "a cut boundary is still a literal width");
});

test("the section fill cannot repaint the locked datum and dimension blue", () => {
  // The centreline and the dimension lines are measurement blue and are not
  // repaintable from a colour picker.
  const sketch = readFileSync("src/components/workspace/section-sketch.tsx", "utf8");
  assert.ok(/const DIM = "var\(--c-blue\)"/.test(sketch), "the dimension colour became settable");
});

test("annotations have an off state, and it is a boolean not a zero scale", () => {
  assert.equal(DEFAULT_ENVIRONMENT.annotationsVisible, true);
  // ANNOTATION_SCALE.OFF = 0 would be a sentinel that silently collapses any
  // consumer that forgets to check it.
  assert.ok(!("OFF" in ANNOTATION_SCALE), "annotation size gained an OFF that scales to zero");
});

test("both on-model annotations respect the toggle, not just one", () => {
  const scene = readFileSync("src/components/viewport/scene.tsx", "utf8");
  // Half-wiring it — letters vanish, balloons stay — is exactly the kind of
  // control this cluster exists to stop.
  assert.ok(/annotationsVisible && \(/.test(scene), "the datum letters ignore the toggle");
  assert.ok(/if \(!env\.annotationsVisible\) return null;/.test(scene), "the measurement balloons ignore the toggle");
});

test("turning annotations off never hides evidence or geometry", () => {
  const scene = readFileSync("src/components/viewport/scene.tsx", "utf8");
  // The work offset origin and the toolpath are geometry, not lettering.
  const datumIndicator = /function DatumIndicator[\s\S]{0,1200}?\n}/.exec(scene);
  assert.ok(datumIndicator, "DatumIndicator moved — this test cannot check it any more");
  assert.ok(
    !/annotationsVisible/.test(datumIndicator![0]),
    "the work offset origin hides with annotations — it is geometry, not a label",
  );
  const toolpath = /function Toolpath\([\s\S]{0,1600}?\n}/.exec(scene);
  assert.ok(toolpath && !/annotationsVisible/.test(toolpath[0]), "the toolpath hides with annotations");
});

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  DEFAULT_ENVIRONMENT,
  VIEW_PRESETS,
  parseHexColor,
  preferLocalEnvironment,
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

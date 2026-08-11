import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { SEMANTIC_COLORS, contrastRatio } from "@/lib/view-environment";

/**
 * THE CONTRAST AUDIT, MADE PERMANENT
 *
 * The dark-canvas flip was done against measured WCAG ratios; this test is
 * the audit that keeps them measured. It reads the actual tokens out of
 * globals.css — not a copy of them — so a palette edit that drops muted
 * type below 4.5:1 on the card ground fails CI instead of shipping as
 * unreadable 10px labels under fluorescent light.
 */

const css = readFileSync("src/app/globals.css", "utf8");

function token(name: string): string {
  const m = css.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
  assert.ok(m, `token ${name} not found as a hex literal in globals.css`);
  return m![1];
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a: string, b: string): number {
  const [la, lb] = [luminance(a), luminance(b)];
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

// The dark grounds text is actually read on. Card is the LIGHTEST dark
// surface, so it is the worst case for light-on-dark type.
const grounds = {
  shell: token("--canvas-bg-shell"),
  page: token("--canvas-page-bg"),
  panel: token("--canvas-panel-bg"),
  footer: token("--canvas-footer-bg"),
  card: token("--canvas-card-bg"),
};

test("primary and dim reading colours clear 4.5:1 on every dark ground", () => {
  const textColors = { text: token("--canvas-text"), dim: token("--canvas-shell-fg-dim") };
  for (const [gName, g] of Object.entries(grounds)) {
    for (const [tName, t] of Object.entries(textColors)) {
      const r = ratio(t, g);
      assert.ok(r >= 4.5, `${tName} on ${gName}: ${r.toFixed(2)}:1 — below 4.5:1`);
    }
  }
});

test("muted and the four status colours clear 4.5:1 on the lightest dark ground", () => {
  // Small labels (8.5–11px) render in these; the card ground is the worst case.
  const smalls = {
    muted: token("--canvas-muted"),
    green: token("--canvas-green"),
    orange: token("--canvas-orange"),
    red: token("--canvas-red"),
    blue: token("--canvas-blue"),
  };
  for (const [name, c] of Object.entries(smalls)) {
    const r = ratio(c, grounds.card);
    assert.ok(r >= 4.5, `${name} on card: ${r.toFixed(2)}:1 — below 4.5:1 at label sizes`);
  }
});

test("the viewport's locked semantic colours stay legible on the default work window", () => {
  // The 3D work window is the one light region; semanticConflicts() enforces
  // 2.5:1 for coloured indicators against a custom background. The DEFAULT
  // background must itself pass the same floor for all four locked colours.
  const workWindow = token("--canvas-work-window");
  for (const [name, color] of Object.entries(SEMANTIC_COLORS)) {
    const r = contrastRatio(workWindow, color);
    assert.ok(r !== null && r >= 2.5, `${name} on the default work window: ${r?.toFixed(2)}:1 — below the 2.5:1 indicator floor`);
  }
});

test("the region hierarchy survives: shell darker than page, page darker than panel, panel darker than card", () => {
  const l = (h: string) => luminance(h);
  assert.ok(l(grounds.shell) < l(grounds.page), "shell must sit below the page ground");
  assert.ok(l(grounds.page) < l(grounds.panel), "page must sit below the panel");
  assert.ok(l(grounds.panel) < l(grounds.card), "panel must sit below the card");
});

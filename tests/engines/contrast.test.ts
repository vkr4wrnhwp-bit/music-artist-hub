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

/**
 * Every dark ground that carries text, not a sample of them.
 *
 * The comment here used to say card was the lightest and therefore the worst
 * case. It is not: `--canvas-shell-raised` #0b2436 is lighter, and two others
 * were missing entirely, so a token could fail on a real surface while the
 * audit reported green.
 */
const grounds = {
  shell: token("--canvas-bg-shell"),
  shell2: token("--canvas-bg-shell-2"),
  shellRaised: token("--canvas-shell-raised"),
  page: token("--canvas-page-bg"),
  panel: token("--canvas-panel-bg"),
  footer: token("--canvas-footer-bg"),
  card: token("--canvas-card-bg"),
  cardQuiet: token("--canvas-card-quiet"),
};

/** WCAG AAA for normal-size text. These labels are 8.5–11px. */
const AAA = 7;

/**
 * Inks that do NOT reach AAA, each with the reason, so CI states the
 * shortfall instead of hiding it.
 *
 * This table is the honest part of the audit. Raising the floor to 7 over a
 * palette that does not reach 7, and quietly keeping the failures on a
 * silent allowlist, would be a green AAA report over a palette that is not
 * AAA — the same lie as a button that appears to do something.
 *
 * Red is not a tuning choice: at its relative luminance its ceiling is
 * 6.10:1 against PURE BLACK, so no ground can get it there. Reaching 7:1
 * means giving up the saturation that makes red read as red, which is a
 * change to the locked colour vocabulary and not one to make silently.
 */
const AA_ONLY: Record<string, { worst: number; why: string }> = {
  "--canvas-red": {
    worst: 4.62,
    why: "cannot reach 7:1 against any ground — ceiling is 6.10:1 on pure black. Lifting it costs the saturation that makes red read as blocking.",
  },
  "--canvas-blue": {
    worst: 5.44,
    why: "would need a ground below #020407 to clear 7:1. Lifting it further moves it out of the restrained precision blue the vocabulary locks.",
  },
};

test("primary and dim reading colours clear AAA on every dark ground", () => {
  const textColors = { text: token("--canvas-text"), dim: token("--canvas-shell-fg-dim") };
  for (const [gName, g] of Object.entries(grounds)) {
    for (const [tName, t] of Object.entries(textColors)) {
      const r = ratio(t, g);
      assert.ok(r >= AAA, `${tName} on ${gName}: ${r.toFixed(2)}:1 — below ${AAA}:1`);
    }
  }
});

/** The worst ratio an ink achieves across every ground text is read on. */
function worstAcrossGrounds(hex: string): { ratio: number; ground: string } {
  let worst = { ratio: Infinity, ground: "" };
  for (const [gName, g] of Object.entries(grounds)) {
    const r = ratio(hex, g);
    if (r < worst.ratio) worst = { ratio: r, ground: gName };
  }
  return worst;
}

const SMALL_INKS = [
  "--canvas-muted",
  "--canvas-shell-muted",
  "--canvas-green",
  "--canvas-shell-green",
  "--canvas-orange",
  "--canvas-red",
  "--canvas-blue",
] as const;

test("every label ink clears AAA on every ground, or is a stated exception", () => {
  for (const name of SMALL_INKS) {
    const { ratio: r, ground } = worstAcrossGrounds(token(name));
    if (AA_ONLY[name]) continue;
    assert.ok(r >= AAA, `${name} on ${ground}: ${r.toFixed(2)}:1 — below ${AAA}:1 at label sizes`);
  }
});

test("the exceptions still clear AA, and are still exceptions", () => {
  // Two ways this table could rot: an ink drifts further down while the entry
  // makes it look accounted for, or it quietly reaches AAA and nobody
  // promotes it. Both fail here.
  for (const [name, entry] of Object.entries(AA_ONLY)) {
    const { ratio: r, ground } = worstAcrossGrounds(token(name));
    assert.ok(r >= 4.5, `${name} on ${ground}: ${r.toFixed(2)}:1 — a stated AAA exception is not a licence to fail AA`);
    assert.ok(
      Math.abs(r - entry.worst) < 0.05,
      `${name} measures ${r.toFixed(2)}:1 on ${ground}, the table records ${entry.worst} — the exception has drifted`,
    );
    assert.ok(r < AAA, `${name} now measures ${r.toFixed(2)}:1 — it clears AAA and should leave the exception table`);
    assert.ok(entry.why.length > 40, `${name}'s exception gives no reason`);
  }
});

test("the app's standard blue ink is one token, not two", () => {
  // `--c-blue-dim` was #0b72ff on :root and var(--canvas-blue) inside
  // `.canvas-shell`, so the same ink measured 6.51:1 in the nav and 3.69:1 on
  // every page — below AA, at 65 call sites, at 9–12px. The audit never saw
  // it because it read only --canvas-* names and this was a raw literal.
  assert.ok(
    /--c-blue-dim:\s*var\(--canvas-blue\)/.test(css),
    "--c-blue-dim is a literal again — it will drift from the shell's value and no ground test will notice",
  );
  assert.ok(
    !/--c-blue-dim:\s*#/.test(css),
    "--c-blue-dim is declared as a hex somewhere — one ink, one definition",
  );
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

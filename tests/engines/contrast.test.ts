import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { SEMANTIC_COLORS, contrastRatio } from "@/lib/view-environment";

/**
 * THE CONTRAST AUDIT, MADE PERMANENT
 *
 * Both palette flips — dark-canvas in August, Studio White in September —
 * were done against measured WCAG ratios; this test is the audit that keeps
 * them measured. It reads the actual tokens out of globals.css — not a copy
 * of them — so a palette edit that drops muted type below 4.5:1 on any real
 * ground fails CI instead of shipping as unreadable 10px labels under
 * fluorescent light.
 *
 * Nothing here assumes which way round the palette is. The grounds are read
 * by name, the worst case is found by measurement rather than asserted in a
 * comment, and `contrastRatio` is symmetric. That is deliberate: an earlier
 * version of this file named the worst-case ground in prose, and the prose
 * was wrong.
 *
 * TWO REGIONS, MEASURED SEPARATELY
 *
 * The app has a graphite chrome and a paper work surface. An ink belongs to
 * one of them, and measuring every ink against every ground would demand a
 * colour legible on both #171C21 and #FFFFFF — which is a mid-grey, which is
 * illegible on both. So the grounds are split, the inks are split, and each
 * pair is measured against its own region. The one thing checked ACROSS the
 * regions is that neither hardcodes the other's blue.
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
 * Every ground that carries text, split by the region it belongs to.
 *
 * Which member of a family is the worst case depends on the palette — the
 * darkest on paper, the lightest on graphite — so none is left out and none
 * is singled out in prose. `worstAcrossGrounds` measures it.
 */
const chromeGrounds = {
  shell: token("--canvas-bg-shell"),
  shell2: token("--canvas-bg-shell-2"),
  shellRaised: token("--canvas-shell-raised"),
};

const workGrounds = {
  page: token("--canvas-page-bg"),
  panel: token("--canvas-panel-bg"),
  footer: token("--canvas-footer-bg"),
  card: token("--canvas-card-bg"),
  cardQuiet: token("--canvas-card-quiet"),
};

/** Only for the hierarchy assertion, which spans both regions by design. */
const grounds = { ...chromeGrounds, ...workGrounds };

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
 * The same two hues fail in BOTH regions, which is not a coincidence: at a
 * saturation where blue still reads as the datum colour and red still reads
 * as blocking, neither clears 7:1 against a near-white or a near-black. That
 * is a property of the hues, not of the grounds, and it is stated here rather
 * than tuned away.
 */
const AA_ONLY: Record<string, { worst: number; why: string }> = {
  "--canvas-red": {
    worst: 5.87,
    why: "cannot reach 7:1 on a white work surface — its ceiling is 6.60:1 against pure white. Darkening it costs the saturation that makes red read as blocking.",
  },
  "--canvas-blue": {
    worst: 5.25,
    why: "ceiling is 5.90:1 against pure white, so no work ground gets it to 7:1. Darkening it further moves it out of the restrained precision blue the vocabulary locks.",
  },
  "--canvas-shell-red": {
    worst: 6.21,
    why: "the same hue problem on graphite: lifting it to 7:1 washes it toward pink, and a pink blocking state does not read as blocking on a machine screen.",
  },
  "--canvas-shell-blue": {
    worst: 6.6,
    why: "lifting the chrome blue to 7:1 turns it pale, and pale blue on graphite stops reading as an active datum. It clears AA comfortably and is used for state, not for prose.",
  },
};

test("primary and dim reading colours clear AAA, each on its own region", () => {
  const pairs: [string, Record<string, string>, Record<string, string>][] = [
    ["work", { text: token("--canvas-text") }, workGrounds],
    ["chrome", { fg: token("--canvas-shell-fg"), dim: token("--canvas-shell-fg-dim") }, chromeGrounds],
  ];
  for (const [region, inks, gs] of pairs) {
    for (const [gName, g] of Object.entries(gs)) {
      for (const [tName, t] of Object.entries(inks)) {
        const r = ratio(t, g);
        assert.ok(r >= AAA, `${region}: ${tName} on ${gName}: ${r.toFixed(2)}:1 — below ${AAA}:1`);
      }
    }
  }
});

/** The worst ratio an ink achieves across the grounds of its own region. */
function worstAcrossGrounds(hex: string, gs: Record<string, string> = workGrounds): { ratio: number; ground: string } {
  let worst = { ratio: Infinity, ground: "" };
  for (const [gName, g] of Object.entries(gs)) {
    const r = ratio(hex, g);
    if (r < worst.ratio) worst = { ratio: r, ground: gName };
  }
  return worst;
}

const WORK_INKS = ["--canvas-muted", "--canvas-green", "--canvas-orange", "--canvas-red", "--canvas-blue"] as const;
const CHROME_INKS = [
  "--canvas-shell-muted",
  "--canvas-shell-green",
  "--canvas-shell-orange",
  "--canvas-shell-red",
  "--canvas-shell-blue",
] as const;

/** Where each ink is measured. Adding an ink without an entry fails below. */
function regionOf(name: string): Record<string, string> {
  return name.startsWith("--canvas-shell-") ? chromeGrounds : workGrounds;
}

test("every label ink clears AAA on its own region, or is a stated exception", () => {
  for (const name of [...WORK_INKS, ...CHROME_INKS]) {
    if (AA_ONLY[name]) continue;
    const { ratio: r, ground } = worstAcrossGrounds(token(name), regionOf(name));
    assert.ok(r >= AAA, `${name} on ${ground}: ${r.toFixed(2)}:1 — below ${AAA}:1 at label sizes`);
  }
});

test("both regions carry the same states, so neither can quietly drop one", () => {
  // The chrome and the work surface are one vocabulary in two inks. A state
  // that exists on paper and not on graphite would silently render as body
  // text inside the nav — legible, and meaningless.
  const suffixes = (xs: readonly string[], p: string) => xs.map((x) => x.slice(p.length)).sort();
  assert.deepEqual(
    suffixes(CHROME_INKS, "--canvas-shell-"),
    suffixes(WORK_INKS, "--canvas-"),
    "the chrome and work ink sets name different states",
  );
});

test("the exceptions still clear AA, and are still exceptions", () => {
  // Two ways this table could rot: an ink drifts further down while the entry
  // makes it look accounted for, or it quietly reaches AAA and nobody
  // promotes it. Both fail here.
  for (const [name, entry] of Object.entries(AA_ONLY)) {
    const { ratio: r, ground } = worstAcrossGrounds(token(name), regionOf(name));
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
  /*
   * Region-aware, because "references a blue token" is not the invariant.
   * The chrome declaring `var(--canvas-blue)` passes that weaker check and
   * measures 2.46:1 on graphite — the original defect, inverted. Each region
   * must name ITS OWN blue: `:root` the work blue, `.canvas-shell` the
   * chrome blue, and neither a literal.
   */
  const shellStart = css.indexOf(".canvas-shell {");
  assert.ok(shellStart > 0, ".canvas-shell block not found");
  const shellBlock = css.slice(shellStart, css.indexOf("}", shellStart));
  const rootBlock = css.slice(0, shellStart);

  for (const [region, block, want] of [
    ["work surface (:root)", rootBlock, "--canvas-blue"],
    [".canvas-shell", shellBlock, "--canvas-shell-blue"],
  ] as const) {
    const decls = [...block.matchAll(/--c-blue(?:-dim)?:\s*([^;]+);/g)].map((m) => m[1].trim());
    assert.equal(decls.length, 2, `${region} must declare both --c-blue and --c-blue-dim, found ${decls.length}`);
    for (const d of decls) {
      assert.equal(
        d,
        `var(${want})`,
        `${region} declares blue as \`${d}\` — it must be var(${want}), so the ink follows the ground it lands on`,
      );
    }
  }
});

test("the viewport's locked semantic colours stay legible on the default work window", () => {
  // semanticConflicts() enforces 2.5:1 for coloured indicators against a
  // user-chosen viewport background. The DEFAULT one must itself pass the
  // same floor for all four locked colours — a preset that ships failing the
  // rule it enforces on everyone else is not a default, it is an exemption.
  const workWindow = token("--canvas-work-window");
  for (const [name, color] of Object.entries(SEMANTIC_COLORS)) {
    const r = contrastRatio(workWindow, color);
    assert.ok(r !== null && r >= 2.5, `${name} on the default work window: ${r?.toFixed(2)}:1 — below the 2.5:1 indicator floor`);
  }
});

test("the region hierarchy survives: chrome, then page, then panel, then card", () => {
  // The chrome sits below the page, the page below the panel, the panel below
  // the card. With graphite chrome the first step is now a large one and the
  // last three are small — which is the point: two regions, and three
  // elevations inside the lit one.
  const l = (h: string) => luminance(h);
  assert.ok(l(grounds.shell) < l(grounds.page), "the chrome must sit one step from the page ground");
  assert.ok(l(grounds.page) < l(grounds.panel), "the page must sit one step from the panel");
  assert.ok(l(grounds.panel) < l(grounds.card), "the panel must sit one step from the card");
});

test("the brass edge stays a seam and never becomes a state", () => {
  // Two ways this rots. Brass spreads to something that carries meaning, and
  // then a warm line reads as "needs a look" where nothing does; or brass is
  // set as a text colour, where it has never been measured against a ground.
  const brass = token("--canvas-brass");
  const uses = [...css.matchAll(/var\(--canvas-brass\)/g)].length;
  assert.ok(uses <= 2, `--canvas-brass is used ${uses} times — the seam is two edges, the rail and the header`);
  assert.ok(
    !/(?:^|[^-])color:\s*var\(--canvas-brass\)/m.test(css),
    "brass is set as a text colour — it is a hairline, and it has no measured ratio at label sizes",
  );
  // It is not the review ink wearing a different name. If they converge, one
  // of them is redundant and the seam has quietly become a status light.
  assert.notEqual(brass.toLowerCase(), token("--canvas-orange").toLowerCase());
  assert.notEqual(brass.toLowerCase(), token("--canvas-shell-orange").toLowerCase());
});

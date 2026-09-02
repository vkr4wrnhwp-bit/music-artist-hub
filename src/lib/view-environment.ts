/**
 * VIEW ENVIRONMENT — viewport visibility settings
 *
 * A machinist tunes the viewport the way they tune a surface plate lamp: for
 * the material in the vise, the light on the floor, and their own eyes. These
 * settings change how the scene is DRAWN — background, floor, grid, shadows,
 * line weight, text size. They change nothing about what the scene SHOWS:
 * no gate, no measurement, no provenance is touched from here, and changing
 * a colour improves visibility, never accuracy.
 *
 * Two rules with teeth:
 *
 * 1. Semantic colours are locked. Blue = selected/measurement, green = pass,
 *    orange = review, red = blocking. Custom viewport colours may not repaint
 *    them, and a custom background that drowns them triggers a visible
 *    warning (`semanticConflicts`) rather than a silent bad choice.
 *
 * 2. Persistence is per user. The server-side ViewPreference row is the
 *    source of truth and follows the user across devices; localStorage is a
 *    fast local cache so the viewport does not flash defaults while the
 *    fetch is in flight. On conflict the server copy wins.
 */

export type LineMode = "OFF" | "LIGHT" | "MEDIUM" | "STRONG";
export type LineWeight = "THIN" | "MEDIUM" | "HEAVY";
export type AnnotationSize = "COMPACT" | "STANDARD" | "LARGE";
export type ViewMode = "PROGRAMMING" | "INSPECTION" | "PRESENTATION" | "SHOP_FLOOR";

export interface ViewEnvironment {
  /** Preset id, or "CUSTOM". */
  preset: string;
  /**
   * The 3D WORK WINDOW's ground. This is the light region the part sits in —
   * it is NOT the application chrome around it. See `shellBackground`.
   */
  background: string;
  /**
   * Draw the background as a soft radial gradient derived from `background`
   * rather than as a flat fill. A studio ground falls off toward the frame
   * edge; a flat fill is a paint chip. Off for High Contrast, where an even
   * ground is the whole point.
   */
  backgroundGradient: boolean;
  floorColor: string;
  gridColor: string;
  /**
   * The APPLICATION CHROME's ground — the rail, the header, the panels
   * around the work window. Null keeps the approved near-black shell.
   *
   * This exists because "background" above only ever repainted the 3D
   * window, and a colour picked there left the rest of the screen exactly
   * as it was. The design is deliberately dark-shell/light-window, but the
   * shell being FIXED was never the decision — it was just the only thing
   * wired up.
   */
  shellBackground: string | null;
  /** Custom accent for selected-feature geometry. Defaults to precision blue. */
  selectedFeatureColor: string;
  sectionFillColor: string;
  gridVisible: boolean;
  /** 0–1. */
  gridIntensity: number;
  /** 0–1. Environment/reflection intensity on metal surfaces. */
  reflectionStrength: number;
  /**
   * The two axes of the direct light rig, 0-1, midpoint = the reference.
   *
   * Separate from `reflectionStrength`, which drives the softbox environment
   * and stays the room/reflection axis. These drive only the direct lights, so
   * the two do not double up on the same surface.
   *
   * A machinist reads material and finish off the render before reading any
   * label, and one rig tuned for a bright studio ground cannot serve a dark
   * one: on Dark Machine Bay a light aluminium part was lit exactly as on
   * Studio White. Ambient is the fill — how much light reaches surfaces facing
   * away from the key. Highlight is the key — the rig that puts the specular
   * on the top machined face, where the cutter marks are.
   */
  ambientLevel: number;
  highlightLevel: number;
  /** 0–1. Contact shadow opacity. */
  shadowStrength: number;
  /** 0–1. Floor plane visibility; 0 hides the plane entirely. */
  floorVisible: boolean;
  floorReflectivity: number;
  edgeMode: LineMode;
  datumLineMode: LineMode;
  measurementLineWeight: LineWeight;
  toolpathLineWeight: LineWeight;
  featureRingHighContrast: boolean;
  sectionLineMode: LineMode;
  /**
   * Whether the on-model annotations — datum letters and measurement balloons
   * — are drawn. A boolean rather than an OFF member on AnnotationSize,
   * because a scale of 0 is a sentinel that silently collapses anything that
   * forgets to check it. Pairs with annotationSize the way gridVisible pairs
   * with gridIntensity.
   */
  annotationsVisible: boolean;
  annotationSize: AnnotationSize;
  viewMode: ViewMode;
}

/* ------------------------------------------------------------------ */
/* Presets                                                             */
/* ------------------------------------------------------------------ */

const base: Omit<ViewEnvironment, "preset" | "background" | "floorColor" | "gridColor"> = {
  // Presets tune the WORK WINDOW. None of them repaints the chrome — a
  // machinist who picks "Dark Machine Bay" for the part is not asking for a
  // different application. Setting it is a separate, explicit act.
  shellBackground: null,
  selectedFeatureColor: "#0b72ff",
  // The resolved value of --c-line-strong, which section-sketch.tsx already
  // hard-coded as its hatch. Anchoring the default here means wiring the
  // field changes nothing about the drawing as it stands.
  sectionFillColor: "#22415a",
  backgroundGradient: true,
  /**
   * Off by default. The grid is ground decoration, not a reference: the work
   * offset is drawn on the part by `DatumIndicator`, datum letters by
   * `DatumFlags`, and size by the dimension card — none of them need it. On a
   * light ground it competes with the component for attention, which is the
   * opposite of what the workspace is for. The presets that switch it back on
   * are the ones where a ruled ground earns its place: a drawing-room review,
   * an inspection ground, a dark bay, and High Contrast.
   */
  gridVisible: false,
  gridIntensity: 0.5,
  reflectionStrength: 0.5,
  ambientLevel: 0.5,
  highlightLevel: 0.5,
  shadowStrength: 0.45,
  floorVisible: true,
  floorReflectivity: 0.2,
  edgeMode: "MEDIUM",
  datumLineMode: "MEDIUM",
  measurementLineWeight: "MEDIUM",
  toolpathLineWeight: "MEDIUM",
  featureRingHighContrast: false,
  sectionLineMode: "MEDIUM",
  annotationsVisible: true,
  annotationSize: "STANDARD",
  viewMode: "PROGRAMMING",
};

export const VIEW_PRESETS: Record<string, { label: string; note: string; env: ViewEnvironment }> = {
  STUDIO_WHITE: {
    label: "Studio White",
    note: "The default. Graduated neutral ground, soft contact shadow, no grid.",
    // No floor: a graduated white ground reads as a studio sweep, and a
    // floor plane in it is a horizon line the part does not need. Declared
    // here rather than special-cased by name in the renderer — the renderer
    // knowing which preset is which is what made the floor controls dead on
    // the default and put a floor up uninvited the moment a colour was
    // picked and the preset became CUSTOM.
    env: { ...base, preset: "STUDIO_WHITE", background: "#f6f6f4", floorColor: "#eceded", gridColor: "#14181c", floorVisible: false, ambientLevel: 0.5, highlightLevel: 0.5 },
  },
  GRAPHITE: {
    label: "Graphite",
    note: "Mid grey. Calms glare from polished surfaces — key down, fill up.",
    env: { ...base, preset: "GRAPHITE", background: "#8b8f93", floorColor: "#7e8286", gridColor: "#2a2e33", shadowStrength: 0.35, ambientLevel: 0.6, highlightLevel: 0.38 },
  },
  INSPECTION_GRAY: {
    label: "Inspection Gray",
    note: "Flat low-glare light on bright aluminum and stainless; the edges carry the read.",
    env: { ...base, preset: "INSPECTION_GRAY", background: "#b9bcbe", floorColor: "#aeb1b3", gridColor: "#3c4045", edgeMode: "STRONG", reflectionStrength: 0.3, gridVisible: true, ambientLevel: 0.65, highlightLevel: 0.35 },
  },
  BLUEPRINT_BLUE: {
    label: "Blueprint Blue",
    note: "Drawing-room ground for review sessions.",
    env: { ...base, preset: "BLUEPRINT_BLUE", background: "#1d3a5f", floorColor: "#193353", gridColor: "#7da4cc", gridIntensity: 0.7, shadowStrength: 0.25, gridVisible: true, ambientLevel: 0.6, highlightLevel: 0.45 },
  },
  WARM_SHOP_FLOOR: {
    label: "Warm Shop Floor",
    note: "Warm tone for sodium-lit floors.",
    env: { ...base, preset: "WARM_SHOP_FLOOR", background: "#e8e2d6", floorColor: "#ddd5c5", gridColor: "#4a443a", ambientLevel: 0.5, highlightLevel: 0.5 },
  },
  DARK_MACHINE_BAY: {
    label: "Dark Machine Bay",
    note: "Dark ground for bright toolpaths. Fill dropped so a light part separates from it.",
    env: { ...base, preset: "DARK_MACHINE_BAY", background: "#14181d", floorColor: "#1b2026", gridColor: "#4b5560", gridIntensity: 0.6, shadowStrength: 0.6, edgeMode: "STRONG", gridVisible: true, ambientLevel: 0.3, highlightLevel: 0.62 },
  },
  HIGH_CONTRAST: {
    label: "High Contrast",
    note: "Maximum readability: strong edges, heavy lines, large text.",
    env: {
      ...base, preset: "HIGH_CONTRAST", background: "#ffffff", floorColor: "#f2f2f2", gridColor: "#000000",
      edgeMode: "STRONG", datumLineMode: "STRONG", measurementLineWeight: "HEAVY", toolpathLineWeight: "HEAVY",
      featureRingHighContrast: true, annotationSize: "LARGE", gridIntensity: 0.8, ambientLevel: 0.28, highlightLevel: 0.75,
      gridVisible: true, backgroundGradient: false,
    },
  },
};

export const DEFAULT_ENVIRONMENT: ViewEnvironment = VIEW_PRESETS.STUDIO_WHITE.env;

/* ------------------------------------------------------------------ */
/* Semantic colour lock                                                */
/* ------------------------------------------------------------------ */

/**
 * The locked status colours. Custom viewport colours never repaint these.
 *
 * These are TEXT inks — they colour the digits in the operation balloons and
 * the letters in the datum chips, both of which sit on opaque white. Measured
 * on white they are 7.01–7.06:1, where the previous values were 4.32–5.76:1
 * and the balloons were semi-transparent, so what a number was read against
 * was whatever ground the machinist had picked.
 *
 * They are still 6.49–6.52:1 against the default work window — well clear of
 * the 2.5:1 floor `semanticConflicts` holds a custom background to, so
 * darkening them did not weaken that check.
 */
export const SEMANTIC_COLORS = {
  selected: "#0854bb",
  pass: "#146544",
  review: "#824c0b",
  blocking: "#aa251a",
} as const;

/**
 * A six-digit hex colour, normalised, or null if it is not one yet.
 *
 * Exported because the drawer needs the same answer the contrast checks do.
 * A half-typed "#0b7" written straight through to the environment used to
 * persist as the colour, and every check downstream skipped it silently: a
 * ground nothing could evaluate passed the semantic-conflict test by never
 * being tested.
 */
export function parseHexColor(input: string): string | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(input.trim());
  return m ? `#${m[1].toLowerCase()}` : null;
}

function luminance(hex: string): number | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const [r, g, b] = [0, 2, 4].map((i) => {
    const c = parseInt(m[1].slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a: string, b: string): number | null {
  const la = luminance(a);
  const lb = luminance(b);
  if (la === null || lb === null) return null;
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Which locked status colours a custom background would drown. 2.5:1 is the
 * floor for a coloured indicator against its ground — below that a red
 * blocking marker stops reading as red, which is exactly the failure this
 * check exists to name.
 */
export function semanticConflicts(background: string): string[] {
  const out: string[] = [];
  for (const [name, color] of Object.entries(SEMANTIC_COLORS)) {
    const ratio = contrastRatio(background, color);
    if (ratio !== null && ratio < 2.5) out.push(name);
  }
  return out;
}

/**
 * What a chosen SHELL colour would break.
 *
 * Two different failures, and both matter. The chrome carries running text
 * — labels, values, gate details — in a near-white foreground, so a light
 * shell erases the interface rather than restyling it; 4.5:1 is the WCAG AA
 * floor for body text and it is not negotiable on a screen someone reads
 * dimensions off. The status colours are the second: the same 2.5:1 rule
 * the work window already applies, because a red blocking marker that stops
 * reading as red is the one failure this whole vocabulary exists to prevent.
 *
 * Returns problems in the order they matter. Empty means the colour is fine.
 */
/** WCAG AAA for normal-size text. The labels are 9–11px, so the floor matters. */
const AAA_TEXT = 7;
const SHELL_TEXT = "#f2f6fa";
const SHELL_MUTED = "#a0b0bf";

export function shellLegibilityProblems(background: string): string[] {
  const problems: string[] = [];
  // Two inks, because the bright one is not what fails first. The small
  // uppercase labels are `--canvas-shell-muted`, and they go unreadable on a
  // ground the 15:1 body text is still comfortable on.
  const text = contrastRatio(background, SHELL_TEXT);
  if (text !== null && text < AAA_TEXT) {
    problems.push(
      `Chrome text sits at ${text.toFixed(1)}:1 against this ground — below the ${AAA_TEXT}:1 floor CANVAS holds itself to for reading dimensions off a screen.`,
    );
  }
  const labels = contrastRatio(background, SHELL_MUTED);
  if (labels !== null && labels < AAA_TEXT) {
    problems.push(
      `Labels sit at ${labels.toFixed(1)}:1 against this ground — the small uppercase type goes first, and it is what names every value.`,
    );
  }
  const drowned = semanticConflicts(background);
  if (drowned.length > 0) {
    problems.push(
      `Drowns the locked ${drowned.join(", ")} status colour${drowned.length === 1 ? "" : "s"} — markers stop reading at a glance.`,
    );
  }
  return problems;
}

/* ------------------------------------------------------------------ */
/* Material-aware recommendation                                       */
/* ------------------------------------------------------------------ */

/** A recommendation, never an auto-change. Visibility, not accuracy. */
export function recommendPresetFor(material: string | null): { preset: string; reason: string } | null {
  if (!material) return null;
  const m = material.toUpperCase();
  if (/ANODIZ|DELRIN|ACETAL|BLACK|PLASTIC/.test(m))
    return { preset: "STUDIO_WHITE", reason: "A light ground improves edge visibility on dark materials." };
  if (/STAINLESS|POLISH/.test(m))
    return { preset: "INSPECTION_GRAY", reason: "A mid-grey ground calms glare and improves edge visibility on stainless." };
  if (/ALUMIN/.test(m))
    return { preset: "INSPECTION_GRAY", reason: "Inspection Gray improves edge visibility on bright aluminum." };
  if (/CAST/.test(m))
    return { preset: "STUDIO_WHITE", reason: "A light ground improves visibility of as-cast surface detail." };
  if (/TITAN|STEEL|BRASS/.test(m)) return null; // read fine on the default
  return null;
}

/* ------------------------------------------------------------------ */
/* View modes                                                          */
/* ------------------------------------------------------------------ */

/**
 * A view mode changes visibility emphasis, not data. Returns the scene-flag
 * overrides and environment nudges the mode implies; the caller applies them
 * as overridable defaults, never as removals.
 */
export function viewModeDefaults(mode: ViewMode): {
  flags: { showToolpath?: boolean; showTool?: boolean; showFixture?: boolean };
  env: Partial<ViewEnvironment>;
} {
  switch (mode) {
    case "PROGRAMMING":
      return { flags: { showToolpath: true, showTool: true }, env: {} };
    case "INSPECTION":
      return { flags: { showToolpath: false, showTool: false }, env: { datumLineMode: "STRONG", measurementLineWeight: "HEAVY", edgeMode: "STRONG" } };
    case "PRESENTATION":
      return { flags: { showToolpath: false, showTool: false, showFixture: false }, env: { gridVisible: false, edgeMode: "LIGHT", shadowStrength: 0.55, reflectionStrength: 0.7 } };
    case "SHOP_FLOOR":
      return { flags: {}, env: { annotationSize: "LARGE", edgeMode: "STRONG", measurementLineWeight: "HEAVY", featureRingHighContrast: true } };
  }
}

/* ------------------------------------------------------------------ */
/* Persistence — server per user, localStorage as cache                */
/* ------------------------------------------------------------------ */

const STORAGE_KEY = "canvas.viewEnvironment.v1";
const SAVED_KEY = "canvas.viewEnvironment.saved.v1";
/** When this browser last changed the environment, for reconciling with the server. */
const STAMP_KEY = "canvas.viewEnvironment.savedAt.v1";

export function loadEnvironment(): ViewEnvironment {
  if (typeof window === "undefined") return DEFAULT_ENVIRONMENT;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_ENVIRONMENT;
    return { ...DEFAULT_ENVIRONMENT, ...(JSON.parse(raw) as Partial<ViewEnvironment>) };
  } catch {
    return DEFAULT_ENVIRONMENT;
  }
}

export function saveEnvironment(env: ViewEnvironment): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(env));
    window.localStorage.setItem(STAMP_KEY, new Date().toISOString());
  } catch {
    /* storage full or blocked — the session still works, it just forgets */
  }
}

/** When this browser last wrote the environment, or null if it never has. */
export function localEnvironmentStamp(): string | null {
  try {
    return window.localStorage.getItem(STAMP_KEY);
  } catch {
    return null;
  }
}

/**
 * Which copy to believe when the browser and the server disagree.
 *
 * The server used to win unconditionally, which loses every change made in
 * the 800ms before a reload — the push had not fired yet, so the stale row
 * came back AND overwrote the local cache on the way past. From the chair
 * that is a colour picker that does not work.
 *
 * No server row, or an unreadable stamp on either side: the browser's copy
 * stands, because it is the one the machinist can see.
 */
export function preferLocalEnvironment(localStamp: string | null, serverStamp: string | null): boolean {
  if (serverStamp === null) return true;
  if (localStamp === null) return false;
  const l = Date.parse(localStamp);
  const s = Date.parse(serverStamp);
  if (Number.isNaN(l) || Number.isNaN(s)) return true;
  return l > s;
}

export interface SavedPreset {
  name: string;
  env: ViewEnvironment;
  savedAtIso: string;
}

export function loadSavedPresets(): SavedPreset[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(SAVED_KEY) ?? "[]") as SavedPreset[];
  } catch {
    return [];
  }
}

export function saveNamedPreset(name: string, env: ViewEnvironment): SavedPreset[] {
  const list = loadSavedPresets().filter((p) => p.name !== name);
  list.push({ name, env, savedAtIso: new Date().toISOString() });
  try {
    window.localStorage.setItem(SAVED_KEY, JSON.stringify(list));
  } catch {
    /* same policy as above */
  }
  return list;
}

export function deleteNamedPreset(name: string): SavedPreset[] {
  const list = loadSavedPresets().filter((p) => p.name !== name);
  try {
    window.localStorage.setItem(SAVED_KEY, JSON.stringify(list));
  } catch {
    /* same policy as above */
  }
  return list;
}

/* ------------------------------------------------------------------ */
/* Render mappings                                                     */
/* ------------------------------------------------------------------ */

/**
 * Server copy of the user's preferences. `env: null` means the user has no
 * server row yet — the caller keeps whatever it has rather than resetting.
 */
export async function fetchServerPreferences(): Promise<{
  env: ViewEnvironment | null;
  saved: SavedPreset[];
  updatedAtIso: string | null;
}> {
  try {
    const res = await fetch("/api/view-preferences");
    if (!res.ok) return { env: null, saved: [], updatedAtIso: null };
    return (await res.json()) as { env: ViewEnvironment | null; saved: SavedPreset[]; updatedAtIso: string | null };
  } catch {
    return { env: null, saved: [], updatedAtIso: null };
  }
}

let pushTimer: ReturnType<typeof setTimeout> | null = null;
let pendingPush: { env?: ViewEnvironment; saved?: SavedPreset[] } = {};

function sendPush(keepalive: boolean): void {
  if (pushTimer) {
    clearTimeout(pushTimer);
    pushTimer = null;
  }
  if (pendingPush.env === undefined && pendingPush.saved === undefined) return;
  const body = JSON.stringify(pendingPush);
  pendingPush = {};
  void fetch("/api/view-preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive,
  }).catch(() => {});
}

/**
 * Fire-and-forget, debounced. Display preferences are the one category of
 * data in CANVAS where losing a write is acceptable — the viewport still
 * works, it just forgets — so a failed push is silent by design.
 *
 * Silent is not the same as lost, though. The debounce used to end at the
 * page: pick a colour, reload within 800ms, and the write never left the
 * browser while the stale server row came back and overwrote the local copy
 * as well. The pending write is flushed on the way out now, and
 * `preferLocalEnvironment` decides the rest.
 */
export function pushServerPreferences(update: { env?: ViewEnvironment; saved?: SavedPreset[] }): void {
  pendingPush = { ...pendingPush, ...update };
  if (pushTimer) clearTimeout(pushTimer);
  pushTimer = setTimeout(() => sendPush(false), 800);
  armFlush();
}

let flushArmed = false;
function armFlush(): void {
  if (flushArmed) return;
  try {
    // pagehide fires on navigation, tab close and bfcache; visibilitychange
    // covers the phone being locked, which never fires pagehide on iOS.
    window.addEventListener("pagehide", () => sendPush(true));
    window.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") sendPush(true);
    });
    flushArmed = true;
  } catch {
    /* no window (SSR): the caller is a client component, so this cannot
       happen in practice, and forgetting a colour is not worth a throw */
  }
}

/**
 * The five direct-light intensities a viewport should use.
 *
 * Affine maps with floors, in the same shape as the grid and environment maps
 * below. Two properties matter and both are pinned by tests:
 *
 *   - At the default 0.5/0.5 this returns exactly the intensities the scene
 *     used to hard-code. A new control must not silently restyle every part
 *     that has already been looked at.
 *   - The floors are non-zero. At both sliders at zero the part is dim but its
 *     form still reads, so the control cannot produce a black viewport that a
 *     machinist would reasonably report as a broken renderer.
 */
export function lightRig(env: ViewEnvironment): {
  ambient: number;
  hemisphere: number;
  key: number;
  fill: number;
  rim: number;
} {
  return {
    ambient: 0.06 + env.ambientLevel * 0.38,
    hemisphere: 0.25 + env.ambientLevel * 1.5,
    key: 0.35 + env.highlightLevel * 2.3,
    fill: 0.15 + env.highlightLevel * 0.8,
    rim: 0.1 + env.highlightLevel * 0.6,
  };
}

/**
 * The cut boundary in the section drawing, from the section line mode.
 *
 * `sectionFillColor` and `sectionLineMode` were declared on ViewEnvironment,
 * given defaults, written to localStorage and pushed to the server on every
 * change — and read by nothing at all. Settings a machinist's account carried
 * that did nothing.
 *
 * Anchored so MEDIUM reproduces the widths the drawing already used, for the
 * same reason the light rig is: wiring a control must not restyle a drawing
 * anyone has already looked at.
 */
export function sectionStroke(mode: LineMode): { width: number; opacity: number } {
  const strength = LINE_MODE_OPACITY[mode];
  // OFF drops the boundary entirely, the same way edgeMode OFF drops part
  // edges. A floor here would make OFF mean "faint", which is a different
  // answer from the one the machinist asked for.
  return { width: 0.55 + strength, opacity: strength === 0 ? 0 : Math.min(1, 0.3 + strength) };
}

export const LINE_MODE_OPACITY: Record<LineMode, number> = { OFF: 0, LIGHT: 0.35, MEDIUM: 0.7, STRONG: 1 };
export const LINE_WEIGHT_PX: Record<LineWeight, number> = { THIN: 1, MEDIUM: 2, HEAVY: 3.5 };
export const ANNOTATION_SCALE: Record<AnnotationSize, number> = { COMPACT: 0.85, STANDARD: 1, LARGE: 1.3 };

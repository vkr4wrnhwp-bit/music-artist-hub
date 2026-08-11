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
  background: string;
  floorColor: string;
  gridColor: string;
  /** Custom accent for selected-feature geometry. Defaults to precision blue. */
  selectedFeatureColor: string;
  sectionFillColor: string;
  gridVisible: boolean;
  /** 0–1. */
  gridIntensity: number;
  /** 0–1. Environment/reflection intensity on metal surfaces. */
  reflectionStrength: number;
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
  annotationSize: AnnotationSize;
  viewMode: ViewMode;
}

/* ------------------------------------------------------------------ */
/* Presets                                                             */
/* ------------------------------------------------------------------ */

const base: Omit<ViewEnvironment, "preset" | "background" | "floorColor" | "gridColor"> = {
  selectedFeatureColor: "#0b72ff",
  sectionFillColor: "#dce4ec",
  gridVisible: true,
  gridIntensity: 0.5,
  reflectionStrength: 0.5,
  shadowStrength: 0.45,
  floorVisible: true,
  floorReflectivity: 0.2,
  edgeMode: "MEDIUM",
  datumLineMode: "MEDIUM",
  measurementLineWeight: "MEDIUM",
  toolpathLineWeight: "MEDIUM",
  featureRingHighContrast: false,
  sectionLineMode: "MEDIUM",
  annotationSize: "STANDARD",
  viewMode: "PROGRAMMING",
};

export const VIEW_PRESETS: Record<string, { label: string; note: string; env: ViewEnvironment }> = {
  STUDIO_WHITE: {
    label: "Studio White",
    note: "The default. Neutral ground, soft shadow.",
    env: { ...base, preset: "STUDIO_WHITE", background: "#f6f6f4", floorColor: "#eceded", gridColor: "#14181c" },
  },
  GRAPHITE: {
    label: "Graphite",
    note: "Mid grey. Calms glare from polished surfaces.",
    env: { ...base, preset: "GRAPHITE", background: "#8b8f93", floorColor: "#7e8286", gridColor: "#2a2e33", shadowStrength: 0.35 },
  },
  INSPECTION_GRAY: {
    label: "Inspection Gray",
    note: "Improves edge visibility on bright aluminum and stainless.",
    env: { ...base, preset: "INSPECTION_GRAY", background: "#b9bcbe", floorColor: "#aeb1b3", gridColor: "#3c4045", edgeMode: "STRONG", reflectionStrength: 0.3 },
  },
  BLUEPRINT_BLUE: {
    label: "Blueprint Blue",
    note: "Drawing-room ground for review sessions.",
    env: { ...base, preset: "BLUEPRINT_BLUE", background: "#1d3a5f", floorColor: "#193353", gridColor: "#7da4cc", gridIntensity: 0.7, shadowStrength: 0.25 },
  },
  WARM_SHOP_FLOOR: {
    label: "Warm Shop Floor",
    note: "Warm tone for sodium-lit floors.",
    env: { ...base, preset: "WARM_SHOP_FLOOR", background: "#e8e2d6", floorColor: "#ddd5c5", gridColor: "#4a443a" },
  },
  DARK_MACHINE_BAY: {
    label: "Dark Machine Bay",
    note: "Dark ground for bright toolpaths and light materials.",
    env: { ...base, preset: "DARK_MACHINE_BAY", background: "#14181d", floorColor: "#1b2026", gridColor: "#4b5560", gridIntensity: 0.6, shadowStrength: 0.6, edgeMode: "STRONG" },
  },
  HIGH_CONTRAST: {
    label: "High Contrast",
    note: "Maximum readability: strong edges, heavy lines, large text.",
    env: {
      ...base, preset: "HIGH_CONTRAST", background: "#ffffff", floorColor: "#f2f2f2", gridColor: "#000000",
      edgeMode: "STRONG", datumLineMode: "STRONG", measurementLineWeight: "HEAVY", toolpathLineWeight: "HEAVY",
      featureRingHighContrast: true, annotationSize: "LARGE", gridIntensity: 0.8,
    },
  },
};

export const DEFAULT_ENVIRONMENT: ViewEnvironment = VIEW_PRESETS.STUDIO_WHITE.env;

/* ------------------------------------------------------------------ */
/* Semantic colour lock                                                */
/* ------------------------------------------------------------------ */

/** The locked status colours. Custom viewport colours never repaint these. */
export const SEMANTIC_COLORS = {
  selected: "#0b72ff",
  pass: "#17754e",
  review: "#96570d",
  blocking: "#c22a1e",
} as const;

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
  } catch {
    /* storage full or blocked — the session still works, it just forgets */
  }
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
export async function fetchServerPreferences(): Promise<{ env: ViewEnvironment | null; saved: SavedPreset[] }> {
  try {
    const res = await fetch("/api/view-preferences");
    if (!res.ok) return { env: null, saved: [] };
    return (await res.json()) as { env: ViewEnvironment | null; saved: SavedPreset[] };
  } catch {
    return { env: null, saved: [] };
  }
}

let pushTimer: ReturnType<typeof setTimeout> | null = null;
let pendingPush: { env?: ViewEnvironment; saved?: SavedPreset[] } = {};

/**
 * Fire-and-forget, debounced. Display preferences are the one category of
 * data in CANVAS where losing a write is acceptable — the viewport still
 * works, it just forgets — so a failed push is silent by design.
 */
export function pushServerPreferences(update: { env?: ViewEnvironment; saved?: SavedPreset[] }): void {
  pendingPush = { ...pendingPush, ...update };
  if (pushTimer) clearTimeout(pushTimer);
  pushTimer = setTimeout(() => {
    const body = JSON.stringify(pendingPush);
    pendingPush = {};
    pushTimer = null;
    void fetch("/api/view-preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body,
    }).catch(() => {});
  }, 800);
}

export const LINE_MODE_OPACITY: Record<LineMode, number> = { OFF: 0, LIGHT: 0.35, MEDIUM: 0.7, STRONG: 1 };
export const LINE_WEIGHT_PX: Record<LineWeight, number> = { THIN: 1, MEDIUM: 2, HEAVY: 3.5 };
export const ANNOTATION_SCALE: Record<AnnotationSize, number> = { COMPACT: 0.85, STANDARD: 1, LARGE: 1.3 };

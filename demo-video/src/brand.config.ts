/**
 * PRODUCT CONFIGURATION — the reuse seam.
 *
 * Everything specific to one application lives here. To make a demo film for a
 * different product you change this file, the shot list (scripts/shots.*.mjs)
 * and the scene copy (src/script.ts). The components, motion, timing engine and
 * render pipeline stay untouched.
 */

export interface BrandConfig {
  productName: string;
  tagline: string;
  /** shown in the closing card; keep it honest */
  disclosure: string;
  callToAction: string;
  colors: {
    ground: string;      // deepest background
    surface: string;     // panels
    ink: string;         // primary text
    ink2: string;        // secondary text
    muted: string;       // tertiary text
    accent: string;      // single brand accent — used sparingly
    good: string;
    warning: string;
    critical: string;
  };
  fonts: {
    display: string;     // headlines
    body: string;        // explanatory copy
    mono: string;        // data, labels, eyebrows
  };
  /** frames per second for every deliverable */
  fps: number;
}

export const brand: BrandConfig = {
  productName: 'TRACE',
  tagline: 'Telemetry & Tuning Platform',
  disclosure:
    'Phase 1 runs on simulated telemetry, labeled on every screen. No ECU write path exists in this build.',
  callToAction: 'trace-4qya.onrender.com',
  colors: {
    ground: '#0B0D10',
    surface: '#14181D',
    ink: '#F4F5F6',
    ink2: '#A8ADB5',
    muted: '#717781',
    accent: '#FF6A00',
    good: '#4BD08B',
    warning: '#E0A84E',
    critical: '#E4705E',
  },
  fonts: {
    display: 'Archivo',
    body: 'IBM Plex Sans',
    mono: 'IBM Plex Mono',
  },
  fps: 30,
};

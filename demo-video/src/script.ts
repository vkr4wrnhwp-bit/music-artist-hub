/**
 * SCENE SCRIPT — product-specific copy and timing.
 *
 * Each scene answers at least one of: what is happening, why is the system
 * doing it, why should the customer care. `shot` names a capture in
 * public/recordings. `focus` drives the push-in: a normalized rect of the
 * captured frame the camera settles on.
 */

export interface Scene {
  id: string;
  /** seconds */
  seconds: number;
  shot?: string;
  /** mono eyebrow — what the system is doing */
  label?: string;
  /** display headline — 2-7 words */
  headline?: string;
  /** body — why it matters, 6-18 words */
  why?: string;
  /** normalized {x,y,w,h} of the capture to settle on; omit for full frame */
  focus?: { x: number; y: number; w: number; h: number };
  /**
   * Same, for the portrait capture the vertical cut uses. The application
   * reflows at that viewport, so the wide rect does not transfer.
   */
  focusTall?: { x: number; y: number; w: number; h: number };
  /** where the copy block sits so it never covers the subject */
  copyAt?: 'left' | 'right' | 'bottom';
  kind?: 'title' | 'statement' | 'screen' | 'end';
}

export const scenes: Scene[] = [
  { id: 'open', seconds: 4.5, kind: 'title' },

  {
    id: 'problem', seconds: 4.5, kind: 'statement',
    headline: 'A rider says it hit too hard on the exit.',
    why: 'Then what?',
  },

  {
    id: 'today', seconds: 7, kind: 'screen', shot: 'today', copyAt: 'right',
    label: 'THE DAY HAS ONE QUESTION',
    headline: 'One objective, one team',
    why: 'Every role opens to the same test objective — not twelve competing dashboards.',
  },

  {
    id: 'marker', seconds: 8, kind: 'screen', shot: 'markers', copyAt: 'right',
    focus: { x: 0.02, y: 0.16, w: 0.72, h: 0.66 },
    label: 'RIDER MARKS THE MOMENT',
    headline: 'Anchored to the track, not memory',
    why: 'The report is pinned to a corner and a lap, so it can be found in the data.',
  },

  {
    id: 'telemetry', seconds: 10, kind: 'screen', shot: 'telemetry', copyAt: 'bottom',
    // framed so the whole trace and its time axis clear the copy band; a
    // harder push magnifies the raster without resolving any more detail
    focus: { x: 0.06, y: 0.25, w: 0.88, h: 0.50 },
    label: 'THE TRACE IS READ, NOT ASSUMED',
    headline: 'Every lap at that corner',
    why: 'Throttle, slip and RPM are correlated across the whole session — not one lucky lap.',
  },

  {
    id: 'engineer', seconds: 11, kind: 'screen', shot: 'engineer', copyAt: 'bottom',
    focus: { x: 0.27, y: 0.36, w: 0.70, h: 0.44 },
    label: 'RANKED CAUSES, COMPUTED CONFIDENCE',
    headline: 'It shows its work',
    why: 'Confidence comes from the data — capped when a channel is degraded, never certain.',
  },

  {
    id: 'authority', seconds: 5, kind: 'statement',
    headline: 'The engineer recommends. It never decides.',
    why: 'Only a person with the right role can approve a change.',
  },

  {
    id: 'envelope', seconds: 8, kind: 'screen', shot: 'map', copyAt: 'right',
    focus: { x: 0.0, y: 0.18, w: 0.8, h: 0.7 },
    label: 'A BOUNDED CHANGE',
    headline: 'Inside the validated envelope',
    why: 'Revision B moves one region within tuner-set limits. Everything else is held constant.',
  },

  {
    id: 'boundary', seconds: 8, kind: 'screen', shot: 'transfer', copyAt: 'right',
    // frame the disabled-write banner and the two-person change sheet; the
    // empty cell-diff table below it says nothing and dilutes the beat
    focus: { x: 0.0, y: 0.03, w: 0.72, h: 0.65 },
    label: 'NO PATH TO THE ECU',
    headline: 'The bike stays protected',
    why: 'TRACE never writes to an ECU. It issues a change sheet a person performs in the manufacturer\'s own software.',
  },

  {
    id: 'compare', seconds: 11, kind: 'screen', shot: 'compare', copyAt: 'bottom',
    focus: { x: 0.06, y: 0.29, w: 0.88, h: 0.25 },
    // portrait: full width so no metric column is cut, banded to the chain
    focusTall: { x: 0, y: 0, w: 1, h: 0.76 },
    label: 'WHAT CHANGED · WHAT HAPPENED · WHAT CAUSED IT',
    headline: 'The rider preferred it. The data disagreed.',
    why: 'Confidence rose 3 points while best lap fell 1.79s — and the uncontrolled variable is flagged.',
  },

  {
    id: 'baseline', seconds: 7, kind: 'screen', shot: 'library', copyAt: 'right',
    // sized so the revision table's columns end where the copy band begins —
    // a half-covered NOTES column reads as clipping, not as depth
    focus: { x: 0.04, y: 0.22, w: 0.645, h: 0.40 },
    label: 'THE DECISION IS RECORDED',
    headline: 'A feeling never becomes the baseline',
    why: 'Every revision keeps its status, its evidence and its lineage — so next season knows why.',
  },

  {
    id: 'verdict', seconds: 5.5, kind: 'statement',
    headline: 'Most tools would have shipped that change.',
    why: 'The rider liked it. TRACE showed the lap times anyway.',
  },

  { id: 'end', seconds: 6.5, kind: 'end' },
];

/** the 30s sales cutdown keeps problem, differentiator and outcome */
export const salesSceneIds = ['open', 'problem', 'engineer', 'compare', 'verdict', 'end'];
/** the 15s teaser: hook, one proof, close */
export const socialSceneIds = ['problem', 'compare', 'verdict', 'end'];

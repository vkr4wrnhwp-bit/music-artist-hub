/**
 * SHOT LIST — product-specific capture plan.
 *
 * Each shot names a route and an optional prep step. Selectors are role- or
 * text-based, never coordinates. `settle` gives charts and transitions time to
 * finish so no frame is captured mid-animation. `scrollTo` frames a specific
 * element instead of the top of the page.
 */
export const APP = 'http://localhost:8899/index.html';

/**
 * Capture variants. The vertical film is recomposed, not cropped: a second
 * pass drives the same routes at a portrait-ish viewport, where the
 * application's own responsive layout reflows to fewer columns and the type
 * is proportionally larger. Cropping the wide capture to 9:16 would slice
 * every metric label in half instead.
 */
export const variants = [
  { dir: 'wide', viewport: { width: 1440, height: 900 } },
  { dir: 'tall', viewport: { width: 1080, height: 1080 } },
];

/** who the film follows: the tuner making the call */
export const PERSONA = 'u-tuner';

export const shots = [
  { name: 'today',     route: '#/garage',                 settle: 1400 },
  { name: 'markers',   route: '#/session/sess-4/markers', settle: 1400 },
  {
    // The default framing puts the trace below the fold and the whole 720s
    // session reads as a hairball. Scroll the chart panel up so it fills the
    // frame; the film then pushes into one window of it, where the individual
    // throttle, slip and RPM traces are actually resolvable.
    name: 'telemetry', route: '#/session/sess-4/telemetry', settle: 2200,
    scrollTo: 'text=TRACE — 720S AT 10 HZ',
  },
  { name: 'engineer',  route: '#/engineer/rec-open',      settle: 1600 },
  { name: 'map',       route: '#/maps/rev-250-r07',       settle: 1800 },
  { name: 'transfer',  route: '#/transfer/rev-250-r07',   settle: 1600 },
  {
    // The whole causal chain — what changed, what happened, what caused it —
    // sits below the fold by default, which pushes the decisive numbers into
    // the film's copy band. Frame from the test plan line down.
    name: 'compare', route: '#/compare/sess-4/sess-5', settle: 2200,
    scrollTo: 'text=Linked test plan',
  },
  { name: 'library',   route: '#/tune',                   settle: 1400 },
  { name: 'analyze',   route: '#/analyze',                settle: 1600 },
  { name: 'pitboard',  route: '#/pitboard',               settle: 1400 },
];

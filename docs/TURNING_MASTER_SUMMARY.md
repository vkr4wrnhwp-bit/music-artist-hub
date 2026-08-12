# Turning — master summary (2026-08-12 pass)

TURN_2_AXIS is a first-class process. The support map
(`src/lib/manufacturing/process.ts`) is the single truth: TURN_2_AXIS
REAL, TURN_LIVE_TOOLING / MILL_TURN DEVELOPMENT, SWISS and the rest
FUTURE.

## Working, deterministic, tested (116-test suite, 13 turning tests)
- Rotational X/Z geometry: segments, validation (stock-can't-make-part,
  zero-length rules), polyline derivation. Diameters are diameters.
- Turning toolpath engines: FACE, OD_ROUGH (bounded passes + finish
  allowance), OD_FINISH (+spring passes), GROOVE_OD (refuses a groove
  narrower than the insert), THREAD_OD (feed = pitch, never retimed;
  constant-area infeed; G97 always), PART_OFF (drop warning),
  CENTER_DRILL/ID_DRILL. Unbuilt types refuse by name.
- CSS: G96 rpm from surface speed at diameter, clamped by G50; fixed
  RPM otherwise. Cycle time is ESTIMATED with assumptions on every op.
- Analyses (all DEVELOPMENT ANALYSIS, all refuse to invent inputs):
  chuck grip (UNKNOWN when clamp force unrecorded; FAIL when programmed
  RPM exceeds the chuck), stickout L/D (4:1/8:1 guidelines, tailstock
  aware), boring-bar reach (4×D steel / 6×D carbide), part-off
  stability (tailstock-pinch FAIL, overhang, drop management).
- Turning readiness: worst-gate aggregation, CSS-without-chuck-limit
  REVIEW, inspection capability from the real instrument library.
- Development lathe post: G18/G20/G99, T-station calls, G96/G97,
  REFUSES CSS without a G50 clamp, header says NOT FOR PRODUCTION USE.
- Nominal reasoning: 1.5744" journal → "40 mm" suggestion via the
  existing nominal engine; ACCEPT (USER-CONFIRMED + audit) / KEEP
  MEASURED (audited) / never auto-applied.
- Workspace: /lathe library + /lathe/[id] — PROFILE X/Z view (light
  paper SVG: stock envelope, centerline, Z0, selected segment with
  diameter/Z callouts, per-op toolpath), operation table, hold panels
  with record-clamp-force and tailstock toggle (audited), worst-gate
  readiness, NC preview withheld while gates fail.
- Demo data: reference 2-axis lathe, 8" chuck (clamp force deliberately
  unrecorded), soft jaws, 5C collets, T0101–T0909, CANVAS Demo Shaft.

## Partial
- Inspection capability is a single-tolerance check against the best
  instrument, not the full per-feature mill engine.
- The profile SVG closes gaps between non-adjacent segments with
  straight lines; a segment-complete demo profile would draw cleaner.

## Shell / development / absent (stated, not faked)
- 3D lathe view (labelled DEVELOPMENT in the workspace), lathe soft-jaw
  generator, turning reverse-engineering flow, guided turning
  measurements, lathe NC parser/backplot/optimizer, turning cost
  engine and make-vs-buy, cinematic turning, USB export for turning
  (no production export path exists at all — preview only), live
  tooling (capability flags only), mill-turn, Swiss (documented only).

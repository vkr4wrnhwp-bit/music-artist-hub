import type { MeasurementGeometry } from "@/lib/engines/inspection-capability";

/**
 * MEASUREMENT TECHNIQUE — how to take the reading with the instrument you have.
 *
 * The capability engine already answers "can this instrument verify this
 * tolerance". It does not answer "how do I actually take the reading", and
 * that is the question a machinist standing at the surface plate has. This
 * closes it.
 *
 * FOUR RULES THIS FILE HOLDS TO.
 *
 * 1. IT IS A LOOKUP, NOT A GENERATOR. Technique is selected deterministically
 *    by the instrument's real `deviceType` and the feature's measurement
 *    geometry. No model call, no per-part text. Two features measured the
 *    same way with the same gauge get the same words, because the technique
 *    is a property of the instrument and the geometry, not of the part.
 *
 * 2. IT IS STANDARD PRACTICE, NOT ENGINEERING ADVICE. Everything here is
 *    ordinary shop metrology — rock a bore gauge to the reversal point, use
 *    the ratchet on a micrometer, watch cosine error on a lever indicator.
 *    None of it is derived, none of it is specific to a part, and none of it
 *    tells anybody what a dimension should be. Where a figure appears it is
 *    a published material property used as an illustration of magnitude,
 *    with its inputs shown.
 *
 * 3. IT VERIFIES NOTHING. Reading this clears no gate and changes no verdict.
 *    Following good technique makes a reading trustworthy; it does not make
 *    an instrument capable of a tolerance it cannot resolve, and the
 *    capability verdict above it is unaffected by anything here.
 *
 * 4. NO ENTRY MEANS NO TEXT. An instrument type without technique on file
 *    renders nothing, the same refusal every drawing in this codebase makes.
 *    Inventing plausible-sounding procedure for an instrument nobody wrote
 *    up would be the worst possible version of this feature.
 */

export interface Technique {
  /** Before the reading — setting, zeroing, referencing. */
  setup: string[];
  /** Taking it. */
  taking: string[];
  /** What most often goes wrong with this instrument specifically. */
  pitfalls: string[];
}

/**
 * True for every measurement, so it is stated once rather than repeated into
 * every entry. The reference temperature is the ISO 1 standard 20 °C / 68 °F;
 * the aluminium figure is a published coefficient used to show the size of
 * the effect, not a correction to apply.
 */
export const UNIVERSAL_CAUTIONS = [
  "Dimensional standards are referenced to 20 °C (68 °F). A part straight off the machine is warm and reads large — 6061 moves about 13 µin per inch per °F, so a 6\" part 20 °F above reference is out by roughly 0.0016\". Let a tight part normalise before you accept a reading.",
  "Wipe the part and the instrument. A chip or a burr under a contact face is the most common wrong reading in any shop.",
  "One reading is a sample, not a size. Where the tolerance is tight enough to argue about, take several and record what you actually did.",
];

const T = (setup: string[], taking: string[], pitfalls: string[]): Technique => ({ setup, taking, pitfalls });

/**
 * Keyed by deviceType. Where geometry changes the technique materially, the
 * entry is a function of it; where it does not, it is fixed.
 */
const TECHNIQUE: Record<string, Technique | ((g: MeasurementGeometry | null) => Technique)> = {
  MICROMETER: T(
    ["Wipe the anvils and zero — on the faces for a 0–1\", on the supplied standard for anything larger.", "Check zero again at the end. A mic that has drifted invalidates everything measured since."],
    ["Use the ratchet or friction thimble on every reading. Thumb pressure on the thimble is the single largest source of operator-to-operator variation on a micrometer.", "Take three readings, rotating the part between them."],
    ["A micrometer reads across two small contacts. A lobed or out-of-round part gives a different answer at every angle, and a single reading hides that entirely."],
  ),

  DIGITAL_CALIPER: (g) =>
    T(
      ["Close the jaws and zero. Open and close again to confirm it returns to zero."],
      g === "INTERNAL_ROUND" || g === "INTERNAL_FLAT"
        ? ["Use the inside jaws square to the bore and rock gently for the largest reading — for an inside measurement the maximum is the true one.", "Read near the base of the jaws, not at the tips."]
        : ["Hold the jaws square to the surface. A caliper rocked off square reads large on an outside measurement.", "Use the faces near the beam rather than the tips, where jaw flex is worst."],
      ["Whatever the display shows, calipers are a thousandth instrument in practice. The fourth digit is resolution, not accuracy.", "The inside jaws are less accurate than the outside faces — treat an inside caliper reading as indicative."],
    ),

  VERNIER_CALIPER: T(
    ["Close and check the zero lines coincide."],
    ["Read square-on to the vernier scale to avoid parallax — from an angle, the coinciding line appears to shift.", "Hold the jaws square to the work, using the faces near the beam."],
    ["Same limits as a digital caliper, plus reading error. Two people will not always read the same vernier the same way."],
  ),

  INSIDE_MICROMETER: T(
    ["Set and check against a ring gauge or a micrometer over gauge blocks at the part's temperature."],
    ["Rock through the bore axis and take the MINIMUM reading. The reversal point is the true diameter; anything else is a chord across the bore and reads large."],
    ["Read at three angular positions 120° apart and at two depths. Out-of-round and taper show up as spread between readings, never in one number."],
  ),

  BORE_GAUGE: T(
    ["Set the gauge to nominal against a ring gauge, or against a micrometer held over gauge blocks. Set it at the temperature the part is at, not the temperature the gauge was stored at."],
    ["Rock the gauge through the bore axis and take the MINIMUM reading — the reversal point. Any other position measures a chord and reads large."],
    ["Take three angular positions 120° apart and two depths. A bore gauge tells you a diameter at one place; out-of-round and taper only appear as spread between places.", "The gauge is only as good as what it was set against — the setting standard's error is in every reading."],
  ),

  TELESCOPING_GAUGE: T(
    ["Wipe the bore. Insert with the plunger locked slightly under size."],
    ["Release, let it expand, rock through the axis, and lock at the reversal point.", "Withdraw without disturbing it and measure the gauge over a micrometer."],
    ["This transfers through two instruments, so both errors are in the answer. Treat it as a thousandth-class measurement, not a tenths one, whatever the micrometer displays.", "Over-tightening the lock springs the legs and reads small."],
  ),

  DEPTH_MICROMETER: T(
    ["Zero the base on a surface plate or a known flat reference."],
    ["Hold the base flat and firmly against the reference face and let the rod find the floor. Use the ratchet.", "Take readings at more than one point on the floor — a depth is only a single number if the floor is flat."],
    ["The base must bridge the opening on solid material. Bridging on a chamfer or a radius reads shallow, and it does so consistently, so it looks repeatable."],
  ),

  PIN_GAUGE: T(
    ["Wipe both the pin and the bore. Use them at the same temperature."],
    ["This is a limit check, not a measurement. The GO pin enters, the NO-GO pin does not.", "Enter straight and without force. A pin pushed in tells you nothing except that it was pushed."],
    ["Report GO/NO-GO, not a dimension. A pin that enters proves the bore is at least that size — it does not say what size it is.", "Pin gauges check size, not form. An oval bore can pass a GO pin."],
  ),

  GAUGE_BLOCK: T(
    ["Clean and lightly oil the faces. Wring blocks together with a sliding twist until they hold — a stack that does not wring is a stack with a gap in it."],
    ["Build the stack from the fewest blocks that reach the size. Every joint is a potential error.", "Use them as a reference to set or check another instrument, not as a way to measure a part."],
    ["Blocks are the standard everything else is set against. Handle by the edges; body heat is the fastest way to put a stack out."],
  ),

  HEIGHT_GAUGE: T(
    ["Wipe the plate and the part. Seat the part on the datum surface the print actually calls out.", "Zero on that datum, not on a convenient face."],
    ["Use an indicator on the arm rather than the scriber for anything tight — a scribed line is found by eye.", "Approach each reading from the same direction with the same contact feel."],
    ["A height gauge measures from the plate. It reports position relative to the datum you physically set, which is the print's datum only if you set the print's datum."],
  ),

  SURFACE_PLATE: T(
    ["Wipe the plate. Let the part sit long enough to reach the plate's temperature."],
    ["The plate is the reference the reading is taken from, not the instrument that takes it. Pair it with an indicator, a height gauge or blocks."],
    ["A plate wears in the middle, where everybody works. Its grade is a calibration property, and an uncalibrated plate quietly puts error into everything set on it."],
  ),

  DIAL_INDICATOR: T(
    ["Mount rigidly. A dial indicator on a flexible stand measures the stand.", "Preload the plunger to mid-range so it has travel in both directions."],
    ["Approach from the same direction every time and let the needle settle.", "Sweep the surface rather than taking one point — an indicator's strength is showing variation."],
    ["It reads variation from where you zeroed it, not absolute size. Turning the bezel to zero does not make the part nominal.", "Plungers have hysteresis; approaching from opposite directions gives two different answers."],
  ),

  TEST_INDICATOR: T(
    ["Mount rigidly and set the lever as close to parallel with the surface as the access allows."],
    ["Sweep across the feature and read the swing, not a single point."],
    ["Cosine error is the trap. A lever at 30° to the surface reads about 13% low, and nothing about the display suggests anything is wrong. Keep it under about 15° or correct for it.", "Like any indicator, it reads variation from your zero, not size."],
  ),

  SINE_BAR: T(
    ["Wring a gauge block stack under one roll. The angle is set by the stack height over the bar's roll centre distance — sin θ = stack ÷ length.", "Work on a surface plate; the bar and the plate are one instrument together."],
    ["Indicate along the top face and adjust until it sweeps flat. Flat means the part's angle matches the stack."],
    ["Accuracy falls off as the angle grows — above roughly 45° a small stack error becomes a large angular one. Set the complement and measure from the other face instead."],
  ),

  OPTICAL_COMPARATOR: T(
    ["Clean the part; edges are what the machine sees. Check the magnification against a stage standard before relying on a reading.", "Use the overlay chart or the digital readout the comparator was calibrated with."],
    ["Focus carefully — an out-of-focus edge is a fat edge, and it biases every measurement the same way.", "Good for form, profile, radii and angles that contact instruments cannot reach."],
    ["It measures a shadow. Surface finish, edge break and lighting all change where the edge appears to be."],
  ),

  CMM: T(
    ["Build the datum reference frame from the datums the print calls out, not from whichever surfaces are convenient to probe.", "Qualify the stylus before the run, and re-qualify after changing it."],
    ["Point count decides what form you can see. Four points on a bore give you a circle whether or not the bore is round.", "Let the part reach the room's temperature before probing anything tight."],
    ["A CMM reports exactly what you asked it to. A wrong datum frame produces confident, repeatable, wrong numbers — and they look like the best data in the shop."],
  ),

  PORTABLE_CMM: T(
    ["Set up so the work is reachable without extending the arm to its limit.", "Re-qualify the probe after any knock, and check against a reference artefact."],
    ["Take the same feature from more than one arm position and compare — agreement is your evidence the setup is sound."],
    ["Volumetric accuracy varies across the arm's envelope and is worst fully extended. The stated figure is a whole-volume number, not a promise at every position."],
  ),

  MACHINE_PROBE: T(
    ["Calibrate the probe against a ring or a reference sphere in the machine, at the work offset you will probe from."],
    ["Probe at the feed the calibration used — probing faster than you calibrated shifts the trigger point.", "Let the spindle and the part settle; a machine that has been cutting is not at the temperature it was calibrated at."],
    ["A spindle probe measures where the MACHINE thinks it is. Probing a part on the machine that cut it cannot see that machine's own systematic error — the error is in the cutting and in the probing equally.", "It is a process check, not independent verification. Where a dimension has to be proven, prove it off the machine."],
  ),

  LASER_SCANNER: T(
    ["Check the working standoff for the head; accuracy falls off outside it.", "Scan a reference artefact first if the result has to be defended."],
    ["Overlap passes and watch the alignment error between them — that number is your real uncertainty, not the sensor's spec."],
    ["Strong for form, deviation maps and free-form surfaces. Weak for a single tight dimension: a point cloud fitted to a feature carries the fit's error as well as the sensor's.", "Shiny, dark and translucent surfaces return badly. Spray changes the size of the part you are measuring."],
  ),

  STRUCTURED_LIGHT_SCANNER: T(
    ["Calibrate for the volume you are about to scan. Calibration is per volume, not once per machine.", "Control the ambient light — the projected pattern is the measurement."],
    ["Use targets or geometry for alignment and record the alignment residual with the result."],
    ["Same class of use as a laser scanner: excellent for form and deviation, poor for one tight dimension.", "Shiny and dark surfaces defeat the pattern, and spraying them changes what you are measuring."],
  ),

  TAPE_RULE: T(
    ["Check the hook floats by its own thickness — that movement is deliberate and makes inside and outside readings agree."],
    ["For stock sizing and layout only."],
    ["Not a precision instrument. If a tolerance is being verified, this is the wrong tool and CANVAS will say so."],
  ),
};

/**
 * Technique for this instrument and geometry, or null when nothing is on
 * file. Null renders nothing — see rule 4 above.
 */
export function techniqueFor(deviceType: string, geometry: MeasurementGeometry | null): Technique | null {
  const entry = TECHNIQUE[deviceType];
  if (!entry) return null;
  return typeof entry === "function" ? entry(geometry) : entry;
}

/** Device types with technique on file, for tests and coverage checks. */
export function techniqueCoverage(): string[] {
  return Object.keys(TECHNIQUE);
}

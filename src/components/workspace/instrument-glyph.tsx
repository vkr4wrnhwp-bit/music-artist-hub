/**
 * INSTRUMENT GLYPH — a schematic of the instrument the capability verdict
 * was computed against.
 *
 * The approved reference draws a micrometer beside the metrology readout.
 * CANVAS names the instrument in text, which is correct but slow to read: a
 * machinist recognises the shape of a bore gauge across a shop floor faster
 * than they read the words "1–2\" dial bore gauge". The drawing is a second
 * channel on the same fact, not a decoration.
 *
 * Three rules it holds to.
 *
 * 1. THE DRAWING FOLLOWS THE DATA. It is selected by `deviceType` off the
 *    real `MetrologyDevice` record, never by guesswork. Drawing a micrometer
 *    when `assessCapability` picked a CMM would be a picture that lies, which
 *    is worse than a number that lies because nobody thinks to check it. An
 *    unrecognised deviceType draws NOTHING and the text stands alone — the
 *    house pattern from `HoldScene` and `MillPartThumb`, which refuse to draw
 *    a default part rather than draw a wrong one.
 *
 * 2. NO READING IS IMPLIED. No needle on a dial, no digits in a display, no
 *    deflection, no jaw opened to a size. There is no probe feed and no live
 *    instrument connection anywhere in CANVAS, and a pointer resting at a
 *    graduation would suggest one. Dials are drawn as bezel, graduations and
 *    hub; the digital caliper's display is an empty bezel. What the shape
 *    says is "this class of instrument", nothing more.
 *
 * 3. IT IS NOT A METER. No arc fill, no coloured sector, no progress ring.
 *    The band-consumption bar below it is a physical ratio with a stated
 *    denominator; a gauge face that appears to read one would be the
 *    percentage pattern principle 1 forbids, wearing a costume.
 *
 * IDIOM: this sits inside the dark Feature Detail panel, so it is drawn in
 * theme tokens (the `section-sketch.tsx` idiom), not in the fixed paper inks
 * that `hold-scene.tsx` and the turning views use on their light grounds.
 * Blue is the measuring axis and the contact faces only — the one place the
 * locked semantic (blue = measurement) is literally what is being drawn.
 */

const OUTLINE = "var(--c-platinum-dim)";
const DETAIL = "var(--c-line-strong)";
const MEASURE = "var(--c-blue)";

const W = 96;
const H = 48;

/** Human-readable name for the device type, for the caption and the label. */
export const DEVICE_TYPE_LABEL: Record<string, string> = {
  MICROMETER: "Outside micrometer",
  INSIDE_MICROMETER: "Inside micrometer",
  DEPTH_MICROMETER: "Depth micrometer",
  DIGITAL_CALIPER: "Digital caliper",
  BORE_GAUGE: "Dial bore gauge",
  TELESCOPING_GAUGE: "Telescoping gauge",
  PIN_GAUGE: "Pin gauge",
  HEIGHT_GAUGE: "Height gauge",
  DIAL_INDICATOR: "Dial indicator",
  SURFACE_PLATE: "Surface plate",
  OPTICAL_COMPARATOR: "Optical comparator",
  CMM: "Coordinate measuring machine",
  MACHINE_PROBE: "Spindle probe",
};

/* ------------------------------------------------------------------ */
/* The drawings                                                        */
/* ------------------------------------------------------------------ */

/* Every glyph is authored in the same 96 x 48 box so the column beside the
   description does not jump between features. Stroke weights are constant:
   1.1 for the instrument body, 0.9 for knurling and graduations, 1.3 for the
   surfaces that actually touch the part. */

const body = { fill: "none", stroke: OUTLINE, strokeWidth: 1.1 } as const;
const detail = { fill: "none", stroke: DETAIL, strokeWidth: 0.9 } as const;
const contact = { fill: "none", stroke: MEASURE, strokeWidth: 1.3 } as const;

/** Knurl hatching on a thimble or barrel — evenly spaced verticals. */
function knurl(x: number, y: number, w: number, h: number, step = 3) {
  const lines = [];
  for (let i = x + step; i < x + w; i += step) lines.push(<line key={i} x1={i} y1={y} x2={i} y2={y + h} />);
  return <g {...detail}>{lines}</g>;
}

/** Graduation ticks around a dial face, no pointer. */
function graduations(cx: number, cy: number, r: number, count = 12) {
  const ticks = [];
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2 - Math.PI / 2;
    const inner = r - (i % 3 === 0 ? 4 : 2.5);
    ticks.push(
      <line
        key={i}
        x1={cx + Math.cos(a) * inner}
        y1={cy + Math.sin(a) * inner}
        x2={cx + Math.cos(a) * r}
        y2={cy + Math.sin(a) * r}
      />,
    );
  }
  return <g {...detail}>{ticks}</g>;
}

const GLYPHS: Record<string, React.ReactNode> = {
  /* Anvil and spindle share one axis; the frame is the C that swings BELOW
     that axis to join them. Drawn the other way round — frame around the
     gap — it reads as a closed capsule, which is not a micrometer. The two
     measuring faces are the blue pair; the gap between them carries no
     dimension line, because an annotated opening would imply a reading. */
  MICROMETER: (
    <>
      <path {...body} d="M26 27 C14 29 11 40 24 44 H50 C60 44 62 34 58 30" />
      <path {...body} d="M20 16 H28 V28 H20 Z" />
      <line {...contact} x1="28" y1="17" x2="28" y2="27" />
      <path {...body} d="M40 20 H56 V24 H40 Z" />
      <line {...contact} x1="40" y1="17" x2="40" y2="27" />
      <path {...body} d="M56 15 H70 V29 H56 Z" />
      <path {...body} d="M70 13 H86 V31 H70 Z" />
      {knurl(70, 13, 16, 18)}
      <path {...body} d="M86 18 H92 V26 H86 Z" />
    </>
  ),

  /* Tubular body with contact tips at both ends — measures across a bore. */
  INSIDE_MICROMETER: (
    <>
      <path {...body} d="M18 20 H78 V28 H18 Z" />
      <path {...body} d="M46 16 H70 V32 H46 Z" />
      {knurl(46, 16, 24, 16)}
      <line {...contact} x1="14" y1="17" x2="14" y2="31" />
      <line {...contact} x1="82" y1="17" x2="82" y2="31" />
      <path {...body} d="M14 20 H18" />
      <path {...body} d="M78 20 H82" />
    </>
  ),

  /* Base bridges the mouth of the pocket; the rod drops to the floor. */
  DEPTH_MICROMETER: (
    <>
      <path {...body} d="M22 30 H74 V36 H22 Z" />
      <line {...contact} x1="22" y1="36" x2="74" y2="36" />
      <path {...body} d="M42 6 H54 V30 H42 Z" />
      {knurl(42, 8, 12, 18)}
      <line {...body} x1="48" y1="36" x2="48" y2="44" />
      <line {...contact} x1="44" y1="44" x2="52" y2="44" />
    </>
  ),

  /* Beam, fixed and sliding jaws, an empty display bezel, depth rod. */
  DIGITAL_CALIPER: (
    <>
      <path {...body} d="M12 22 H84 V28 H12 Z" />
      <path {...body} d="M16 8 V22" />
      <path {...body} d="M16 28 V40" />
      <line {...contact} x1="16" y1="8" x2="16" y2="20" />
      <line {...contact} x1="16" y1="30" x2="16" y2="40" />
      <path {...body} d="M40 10 V22" />
      <path {...body} d="M40 28 V38" />
      <line {...contact} x1="40" y1="10" x2="40" y2="20" />
      <line {...contact} x1="40" y1="30" x2="40" y2="38" />
      <path {...body} d="M44 10 H70 V22 H44 Z" />
      {/* Display bezel only. Digits would read as a measurement. */}
      <path {...detail} d="M48 13 H66 V19 H48 Z" />
      <path {...body} d="M84 24 H92 V26 H84 Z" />
    </>
  ),

  /* Dial head, stem, and the two opposed contacts that span the bore. */
  BORE_GAUGE: (
    <>
      <circle {...body} cx="48" cy="13" r="11" />
      {graduations(48, 13, 11)}
      <circle {...detail} cx="48" cy="13" r="1.6" />
      <path {...body} d="M45 24 H51 V34 H45 Z" />
      <path {...body} d="M40 34 H56 V42 H40 Z" />
      <line {...contact} x1="36" y1="36" x2="36" y2="42" />
      <line {...contact} x1="60" y1="36" x2="60" y2="42" />
      <path {...body} d="M36 38 H40" />
      <path {...body} d="M56 38 H60" />
    </>
  ),

  /* T-handle, crossbar, spring-loaded plungers. Read with a micrometer. */
  TELESCOPING_GAUGE: (
    <>
      <path {...body} d="M45 18 H51 V44 H45 Z" />
      {knurl(45, 26, 6, 14, 3)}
      <path {...body} d="M28 14 H68 V20 H28 Z" />
      <line {...contact} x1="24" y1="11" x2="24" y2="23" />
      <line {...contact} x1="72" y1="11" x2="72" y2="23" />
      <path {...body} d="M24 14 H28" />
      <path {...body} d="M68 14 H72" />
    </>
  ),

  /* A ground cylinder in a collar. The pin itself is the standard. */
  PIN_GAUGE: (
    <>
      <path {...body} d="M20 20 H62 V28 H20 Z" />
      <line {...contact} x1="20" y1="20" x2="20" y2="28" />
      <path {...body} d="M62 16 H74 V32 H62 Z" />
      {knurl(62, 16, 12, 16)}
      <path {...detail} d="M78 18 V30" />
    </>
  ),

  /* Granite base, scaled column, carriage, scriber. */
  HEIGHT_GAUGE: (
    <>
      <path {...body} d="M18 38 H74 V44 H18 Z" />
      <line {...contact} x1="18" y1="44" x2="74" y2="44" />
      <path {...body} d="M40 6 H48 V38 H40 Z" />
      <g {...detail}>
        {[10, 14, 18, 22, 26, 30, 34].map((y) => (
          <line key={y} x1="48" y1={y} x2={y % 8 === 2 ? 53 : 51} y2={y} />
        ))}
      </g>
      <path {...body} d="M32 16 H40 V26 H32 Z" />
      <path {...body} d="M20 20 H32 V23 H20 Z" />
      <line {...contact} x1="14" y1="21.5" x2="20" y2="21.5" />
    </>
  ),

  /* Bezel, graduations, hub, stem, contact ball. No pointer, by rule. */
  DIAL_INDICATOR: (
    <>
      <circle {...body} cx="48" cy="17" r="14" />
      {graduations(48, 17, 14)}
      <circle {...detail} cx="48" cy="17" r="1.8" />
      <path {...body} d="M45 31 H51 V40 H45 Z" />
      <circle {...contact} cx="48" cy="43" r="2.6" />
    </>
  ),

  /* A lapped reference plane. The datum, not an instrument that reads. */
  SURFACE_PLATE: (
    <>
      <path {...body} d="M18 20 L60 12 L86 20 L44 28 Z" />
      <path {...body} d="M18 20 V30 L44 38 V28" />
      <path {...body} d="M44 38 L86 30 V20" />
      <line {...contact} x1="18" y1="20" x2="60" y2="12" />
      <g {...detail}>
        <line x1="30" y1="22" x2="66" y2="15" />
        <line x1="38" y1="25" x2="74" y2="18" />
      </g>
    </>
  ),

  /* Screen, projected profile, stage and lamp path. */
  OPTICAL_COMPARATOR: (
    <>
      <circle {...body} cx="62" cy="22" r="16" />
      <path {...detail} d="M56 14 V30 H68" />
      <path {...body} d="M10 18 H20 V26 H10 Z" />
      <g {...detail}>
        <line x1="20" y1="22" x2="34" y2="22" />
        <line x1="38" y1="22" x2="46" y2="22" />
      </g>
      <line {...contact} x1="35" y1="14" x2="35" y2="30" />
      <path {...body} d="M28 34 H42 V38 H28 Z" />
    </>
  ),

  /* Bridge, ram, probe. The one instrument here that is a machine. */
  CMM: (
    <>
      <path {...body} d="M12 40 H84 V45 H12 Z" />
      <path {...body} d="M20 12 V40" />
      <path {...body} d="M76 12 V40" />
      <path {...body} d="M20 12 H76 V18 H20 Z" />
      <path {...body} d="M44 18 H52 V30 H44 Z" />
      <path {...body} d="M47 30 V34" />
      <circle {...contact} cx="48" cy="36" r="2.6" />
      <g {...detail}>
        <line x1="26" y1="45" x2="26" y2="40" />
        <line x1="70" y1="45" x2="70" y2="40" />
      </g>
    </>
  ),

  /* Taper, body, stylus, ruby ball — measuring in the fixture, on the machine. */
  MACHINE_PROBE: (
    <>
      <path {...body} d="M38 6 H58 L54 16 H42 Z" />
      <path {...body} d="M40 16 H56 V30 H40 Z" />
      {knurl(40, 18, 16, 10)}
      <path {...body} d="M47 30 V38" />
      <circle {...contact} cx="48" cy="41" r="3" />
      <g {...detail}>
        <line x1="30" y1="41" x2="42" y2="41" />
        <line x1="54" y1="41" x2="66" y2="41" />
      </g>
    </>
  ),
};

/* ------------------------------------------------------------------ */

/**
 * Renders the schematic for `deviceType`, or null when there is no drawing
 * for it. Null is the correct answer for an unknown type — a generic outline
 * would say "some instrument", which the text already says better.
 */
export function InstrumentGlyph({ deviceType, className = "" }: { deviceType: string; className?: string }) {
  const drawing = GLYPHS[deviceType];
  if (!drawing) return null;
  const name = DEVICE_TYPE_LABEL[deviceType] ?? deviceType.replace(/_/g, " ").toLowerCase();

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={`block ${className}`}
      role="img"
      aria-label={`${name}, schematic. Instrument type only — no reading is shown.`}
      strokeLinecap="square"
      strokeLinejoin="miter"
    >
      {drawing}
    </svg>
  );
}

/** True when a drawing exists, so callers can lay out without rendering twice. */
export function hasInstrumentGlyph(deviceType: string): boolean {
  return deviceType in GLYPHS;
}

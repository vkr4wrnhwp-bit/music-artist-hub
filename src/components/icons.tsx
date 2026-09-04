/**
 * THE MARKS.
 *
 * These were ten glyphs inlined in `nav.tsx`, which meant the navigation had
 * an icon vocabulary and nothing else in the app could reach it. Every other
 * surface — feature lists, gate rows, operation tables, provenance badges —
 * rendered the same concepts as text, so a bore, a tapped hole and a datum
 * had marks that only the rail could draw.
 *
 * DRAWING RULES, AND WHY THEY ARE RULES
 *
 * 20 x 20 grid, safe area 1.8 to 18.2. Stroke 1.25, butt caps, mitre joins,
 * no fill, no corner rounding. Every stroke is `currentColor`, so a mark
 * takes the state of the text beside it and there is no coloured variant to
 * keep in sync — a red icon next to grey text is a thing that cannot be
 * built here.
 *
 * Each mark is the object a machinist would recognise on the bench, or the
 * section they would see on a print: a drilled hole carries its point, a
 * tapped hole carries thread, a slot carries its centreline, a contour
 * carries the offset path outside it. Nothing is a metaphor for a metaphor.
 *
 * The single filled shape in the set is the datum triangle, because on a
 * drawing it is filled.
 *
 * WHAT IS NOT HERE
 *
 * No emoji. No robot, no sparkle, no brain — a model that pointed at a bore
 * is not a character. No duotone, no rounded caps, nothing an operator has
 * to interpret twice while holding a part in one hand.
 *
 * Eight of these were redrawn after being read at 20px rather than admired
 * as path data: bore was a speck, drilled and tapped were the same shield,
 * chamfer read as a document, face read as export, flip read as a comma, and
 * slot and pocket were the same rectangle.
 */

const P: Record<string, string> = {
  /* ---- Sections ---- */
  home: "M2.5 9 L10 3 L17.5 9|M4.5 8.2 V16.5 H15.5 V8.2|M8.2 16.5 V11.8 H11.8 V16.5",
  part: "M10 2.6 L17 6.3 V13.7 L10 17.4 L3 13.7 V6.3 Z|M3 6.3 L10 10 L17 6.3|M10 10 V17.4",
  machine: "M2.5 16.8 H17.5|M6.4 16.8 V13.2 H13.6 V16.8|M8.4 2.8 H11.6 V8 H8.4 Z|M10 8 V13.2|M4 2.8 V8",
  tool: "M7.8 2.6 H12.2 V9.4 H7.8 Z|M7.8 9.4 V15.4 L10 17.6 L12.2 15.4 V9.4|M7.8 12 L12.2 10.4|M7.8 14.6 L12.2 13",
  workholding: "M1.8 6.6 H5.2 V13.4 H1.8 Z|M14.8 6.6 H18.2 V13.4 H14.8 Z|M7 4.8 H13 V15.2 H7 Z|M5.2 10 H7|M13 10 H14.8",
  metrology: "M2 6.6 H18|M2 6.6 V10.4|M5.2 6.6 V13.6 H7.4|M12.6 6.6 V13.6 H10.4|M8.4 3.4 H16 V6.6|M15 6.6 V9",
  additive: "M2.6 16.4 H17.4|M6 14.2 H14|M6.6 11.8 H13.4|M7.2 9.4 H12.8|M10 2.6 V6.4|M8.6 6.4 H11.4 L10 8.2 Z",
  jobs: "M4 2.8 H16 V17.2 H4 Z|M6.4 6.6 H8|M9.6 6.6 H13.6|M6.4 10 H8|M9.6 10 H13.6|M6.4 13.4 H8|M9.6 13.4 H13.6",
  knowledge: "M10 5.4 V17|M2.6 3.4 H8.4 L10 5.4 L11.6 3.4 H17.4|M2.6 3.4 V15 H8.4 L10 17 L11.6 15 H17.4 V3.4",
  settings: "M2.6 5.4 H17.4|M2.6 10 H17.4|M2.6 14.6 H17.4|M7 3.6 V7.2|M13 8.2 V11.8|M8.6 12.8 V16.4",

  /* ---- Feature kinds, as they appear in section ---- */
  bore: "M10 1.8 V6|M10 14 V18.2|M1.8 10 H6|M14 10 H18.2",
  drilledHole: "M2.5 3.4 H17.5|M5.6 3.4 V11.4 L10 15.6 L14.4 11.4 V3.4",
  tappedHole:
    "M2.5 3.4 H17.5|M5.6 3.4 V11.4 L10 15.6 L14.4 11.4 V3.4|M5.6 5.8 H8|M12 5.8 H14.4|M5.6 8.2 H8|M12 8.2 H14.4|M5.6 10.6 H8|M12 10.6 H14.4",
  chamfer: "M2.8 16.8 V6.6 L6.4 3 H17.2 V16.8 Z",
  face: "M2.4 14.2 H17.6|M7 3 H13 V11 H7 Z|M10 3 V11",

  /* ---- Work ---- */
  datum: "M10 9.2 V13.2",
  measurement: "M4.4 4.6 V15.4|M15.6 4.6 V15.4|M4.4 10 H15.6|M6.2 8.4 L4.4 10 L6.2 11.6|M13.8 8.4 L15.6 10 L13.8 11.6",
  ncProgram: "M4.6 2.8 H12.2 L15.4 6 V17.2 H4.6 Z|M12.2 2.8 V6 H15.4|M7 9.6 H13|M7 12 H13|M7 14.4 H10.6",
  approval: "M6.8 10.2 L9.1 12.6 L13.4 7.8",
  export: "M3.4 12.4 V16.6 H16.6 V12.4|M10 3 V12.4|M6.8 6.2 L10 3 L13.2 6.2",
  setupFlip: "M4.6 12.4 A6 6 0 0 1 12.4 4.6|M9.6 4 L12.7 4.6 L11.9 7.7|M15.4 7.6 A6 6 0 0 1 7.6 15.4|M10.4 16 L7.3 15.4 L8.1 12.3",
  photograph: "M3 6.4 H6.4 L7.8 4.4 H12.2 L13.6 6.4 H17 V15.6 H3 Z",
};

/**
 * Marks that need a primitive a path cannot express cleanly. Kept beside the
 * paths rather than folded into them so the geometry stays readable and a
 * circle stays a circle rather than four arc segments nobody can edit.
 */
const EXTRA: Record<string, React.ReactNode> = {
  bore: <circle cx="10" cy="10" r="6" />,
  drilledHole: null,
  simulation: (
    <>
      <rect x="2.8" y="4.4" width="14.4" height="11.2" />
      <path d="M8.4 7.2 L13.4 10 L8.4 12.8 Z" />
    </>
  ),
  rectPocket: (
    <>
      <rect x="2.6" y="4.2" width="14.8" height="11.6" />
      <rect x="5.8" y="7.2" width="8.4" height="5.6" rx="1.2" />
    </>
  ),
  slot: (
    <>
      <rect x="2.6" y="4.2" width="14.8" height="11.6" />
      <rect x="4.6" y="7.6" width="10.8" height="4.8" rx="2.4" />
      <path d="M7.2 10 H12.8" strokeDasharray="1.4 1.2" />
    </>
  ),
  contour: (
    <>
      <rect x="5" y="6" width="10" height="8" rx="1.4" />
      <rect x="2.6" y="3.6" width="14.8" height="12.8" rx="2.2" strokeDasharray="2 1.6" />
    </>
  ),
  chamfer: <path d="M2.8 6.6 H6.4 V3" strokeDasharray="1.6 1.4" />,
  face: <path d="M2.4 11 H17.6" strokeDasharray="1.8 1.4" />,
  // The one filled shape in the set, because a datum triangle is filled on a
  // drawing. `fill` is set on the path, not on the <svg>, so every other mark
  // in the set stays unfillable by construction.
  datum: (
    <>
      <rect x="6.8" y="2.8" width="6.4" height="6.4" />
      <path d="M10 13.2 L7.8 17 H12.2 Z" fill="currentColor" />
    </>
  ),
  approval: <circle cx="10" cy="10" r="6.4" />,
  photograph: <circle cx="10" cy="10.8" r="2.9" />,
};

export type IconName =
  | "home" | "part" | "machine" | "tool" | "workholding" | "metrology" | "additive" | "jobs" | "knowledge" | "settings"
  | "bore" | "drilledHole" | "tappedHole" | "rectPocket" | "slot" | "contour" | "chamfer" | "face"
  | "datum" | "measurement" | "simulation" | "ncProgram" | "approval" | "export" | "setupFlip" | "photograph";

/**
 * `size` is 16 inline, 20 in the rail, 28 in an empty state. The viewBox
 * scales; the stroke is not re-drawn per size, which is the point of one
 * grid and one weight.
 *
 * `title` is what a screen reader gets. Omit it for a mark that only repeats
 * an adjacent label — announcing "bore, bore" is worse than silence.
 */
export function Icon({ name, size = 20, title, className }: { name: IconName; size?: number; title?: string; className?: string }) {
  const d = P[name];
  const extra = EXTRA[name];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.25}
      className={className}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
    >
      {title && <title>{title}</title>}
      {extra}
      {d?.split("|").map((p) => <path key={p} d={p} />)}
    </svg>
  );
}

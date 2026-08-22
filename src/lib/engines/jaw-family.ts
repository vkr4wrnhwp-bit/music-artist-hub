/**
 * SOFT JAW FAMILIES
 *
 * Soft jaws are always the safest way to hold a part and almost never the
 * cheapest — because the cost is counted once, against one job, and then the
 * jaws go in a drawer and get scrapped when someone needs the blanks.
 *
 * That is a bookkeeping failure, not a manufacturing one. A jaw bored ⌀6.000
 * does not hold a ⌀6.000 part; it holds everything from ⌀6.000 down to
 * whatever the shim stack allows. Cut it once at a size chosen to head a
 * family, keep a shim schedule with it, and the second job that uses it costs
 * the price of two shims and five minutes.
 *
 * So this engine does three things:
 *   - looks in the drawer before it cuts anything
 *   - when it must cut, picks a size that heads a family rather than the size
 *     this one part happens to need
 *   - amortises the cutting cost across the parts that will reuse it, which is
 *     what actually changes the make/buy arithmetic
 */

export type JawProfile = "ROUND" | "RECTANGULAR";

/** A machined jaw set sitting in the drawer, described by what it can hold. */
export interface JawSet {
  id: string;
  name: string;
  profile: JawProfile;
  /** Bore diameter for ROUND, jaw opening across the part for RECTANGULAR. */
  nominalSize: number;
  /** Second dimension for RECTANGULAR; ignored for ROUND. */
  nominalLength?: number;
  /** Depth of the machined step the part seats on. */
  stepDepth: number;
  jawHeight: number;
  material: string;
  viseDescription: string;
  /** How many parts have already been held in it. Drives amortisation. */
  timesUsed: number;
  /** Minutes it took to cut, recorded when it was made. */
  minutesToCut: number;
  notes?: string;
}

/** Shim stock actually kept on the shelf, in inches. */
export const STANDARD_SHIMS = [0.015, 0.031, 0.062, 0.125, 0.25, 0.375, 0.5];

/**
 * Shimming is not unlimited. Past roughly three quarters of an inch per side
 * the stack starts to act like a spring and the repeatability the jaws existed
 * to provide goes away.
 */
const MAX_SHIM_PER_SIDE = 0.75;
const MIN_USEFUL_SHIM = 0.01;

export interface ShimSolution {
  /** Total required per side. */
  perSide: number;
  /** Individual shims stacked to reach it, largest first. */
  stack: number[];
  /** How far the stack misses the ideal, per side. */
  error: number;
  exact: boolean;
  note: string;
}

/**
 * Greedy stack from the shim stock on the shelf. Greedy is correct here rather
 * than optimal: a machinist builds the stack from the biggest piece down, and
 * a solution they would not assemble by hand is not a solution.
 */
export function solveShim(perSide: number): ShimSolution | null {
  if (perSide < MIN_USEFUL_SHIM) return null;
  if (perSide > MAX_SHIM_PER_SIDE) return null;

  const stack: number[] = [];
  let remaining = perSide;
  const sizes = [...STANDARD_SHIMS].sort((a, b) => b - a);

  for (const s of sizes) {
    while (remaining >= s - 0.0005 && stack.length < 6) {
      stack.push(s);
      remaining -= s;
    }
  }

  const total = stack.reduce((a, b) => a + b, 0);
  const error = Number((perSide - total).toFixed(4));
  const exact = Math.abs(error) <= 0.002;

  // A gap between MIN_USEFUL_SHIM and the thinnest shim on the shelf produces
  // an empty stack, and the note then rendered as ` = 0.000" per side` — an
  // empty join with nothing in front of it. Worse than looking broken, it was
  // returned as a shim solution, so the caller told the machinist to "shim it
  // down 0.012 per side" and listed no shims to do it with.
  if (stack.length === 0) {
    return {
      perSide: Number(perSide.toFixed(4)),
      stack: [],
      error,
      exact: false,
      note: `Nothing on the shelf is that thin — the smallest shim stocked is ${Math.min(...STANDARD_SHIMS).toFixed(3)}" and this gap is ${perSide.toFixed(4)}". Face a shim to suit, or run the part as it sits and probe it.`,
    };
  }

  return {
    perSide: Number(perSide.toFixed(4)),
    stack,
    error,
    exact,
    note: exact
      ? `${stack.map((s) => s.toFixed(3)).join(" + ")} = ${total.toFixed(3)}" per side.`
      : `${stack.map((s) => s.toFixed(3)).join(" + ")} = ${total.toFixed(3)}" per side, ${Math.abs(error).toFixed(4)}" ${error > 0 ? "under" : "over"}. Face a shim to suit or accept the offset and probe the part.`,
  };
}

/**
 * A round jaw is bored to a diameter; a rectangular one is cut to an opening
 * across the part. Writing ⌀ on a rectangular set reads as a mistake on the
 * shop floor, so size is always spoken in the right units for the profile.
 */
function sizeLabel(profile: JawProfile, size: number): string {
  return profile === "ROUND" ? `⌀${size.toFixed(3)}` : `${size.toFixed(3)}" across`;
}

/* ------------------------------------------------------------------ */
/* Matching what is already in the drawer                              */
/* ------------------------------------------------------------------ */

export interface JawMatch {
  jawSet: JawSet;
  shim: ShimSolution | null;
  /** True when the jaw fits the part with no shimming at all. */
  direct: boolean;
  /** Minutes to put this jaw set on the machine and prove it. */
  setupMinutes: number;
  /**
   * True when the request gave a length and the jaw set has none recorded, so
   * whether the part fits along the jaw could not be checked.
   */
  lengthUnverified: boolean;
  reason: string;
}

export interface JawRequest {
  profile: JawProfile;
  /** Diameter for ROUND, width across the clamped axis for RECTANGULAR. */
  size: number;
  length?: number;
  /** Grip the setup needs. */
  requiredStep: number;
}

export function findExistingJaws(request: JawRequest, inventory: JawSet[]): JawMatch[] {
  const matches: JawMatch[] = [];

  for (const jaw of inventory) {
    if (jaw.profile !== request.profile) continue;
    // A jaw can only ever hold something at or below its own size — shims go
    // inward, never outward.
    if (jaw.nominalSize < request.size - 0.0005) continue;
    if (jaw.stepDepth < request.requiredStep - 0.002) continue;

    // The second dimension was never checked. A rectangular set cut 4.000
    // across and 2.000 long was offered for a 4.000 × 6.000 part with the
    // words "this part drops straight in" — a third of the part hanging out
    // of a jaw that cannot reach it.
    let lengthUnverified = false;
    if (request.profile === "RECTANGULAR" && request.length != null) {
      if (jaw.nominalLength == null) {
        lengthUnverified = true;
      } else if (jaw.nominalLength < request.length - 0.0005) {
        continue;
      }
    }

    const unverifiedNote = lengthUnverified
      ? ` No length is recorded for this set, so whether the part fits along the jaw has not been checked — measure it before you rely on it.`
      : "";

    const perSide = (jaw.nominalSize - request.size) / 2;

    if (perSide < MIN_USEFUL_SHIM) {
      matches.push({
        jawSet: jaw,
        shim: null,
        direct: true,
        setupMinutes: 10,
        lengthUnverified,
        reason: `${jaw.name} is already at ${sizeLabel(jaw.profile, jaw.nominalSize)} — this part drops straight in with no shims.${unverifiedNote}`,
      });
      continue;
    }

    const shim = solveShim(perSide);
    if (!shim) continue;

    matches.push({
      jawSet: jaw,
      shim,
      direct: false,
      setupMinutes: 15,
      lengthUnverified,
      reason: `${jaw.name} is cut ${sizeLabel(jaw.profile, jaw.nominalSize)}. Shim it down ${perSide.toFixed(3)}" per side and it holds this part — no jaw cutting at all.${unverifiedNote}`,
    });
  }

  // Least shimming first: a smaller stack is stiffer and quicker to build.
  return matches.sort((a, b) => (a.shim?.perSide ?? 0) - (b.shim?.perSide ?? 0));
}

/* ------------------------------------------------------------------ */
/* Choosing a size that heads a family                                 */
/* ------------------------------------------------------------------ */

/**
 * Sizes worth cutting a jaw at. Round numbers and common stock diameters,
 * because the next part through the door is far more likely to be 4.000 or
 * 5.000 than 4.317 — and a jaw is only an asset if something else fits it.
 */
const FAMILY_SIZES = [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 8];

export interface FamilyProposal {
  /** Size to actually cut the jaws at. */
  cutAt: number;
  /** What this part needs. */
  partSize: number;
  /** Shim needed for this part, once the jaw is cut at the family size. */
  shim: ShimSolution | null;
  /** The span this jaw will cover once it exists. */
  coversFrom: number;
  coversTo: number;
  minutesToCut: number;
  rationale: string;
  /** Why not simply cut it at the part size. */
  versusBespoke: string;
}

export function proposeFamily(request: JawRequest, inventory: JawSet[]): FamilyProposal {
  const existingSizes = new Set(
    inventory.filter((j) => j.profile === request.profile).map((j) => Number(j.nominalSize.toFixed(3))),
  );

  // Smallest family size that covers this part and does not duplicate a jaw
  // already in the drawer.
  const candidate =
    FAMILY_SIZES.find((s) => s >= request.size - 0.0005 && !existingSizes.has(Number(s.toFixed(3)))) ??
    Number((Math.ceil(request.size * 2) / 2).toFixed(3));

  const perSide = (candidate - request.size) / 2;
  const shim = perSide < MIN_USEFUL_SHIM ? null : solveShim(perSide);

  // Cutting bigger costs nothing extra in time; the jaw is the same operation.
  const minutesToCut = 35;

  // A jaw cannot close past nothing. This was candidate - 2 * MAX_SHIM_PER_SIDE
  // unclamped, so a ⌀1.000 jaw was advertised as covering "-0.500–⌀1.000".
  const coversFrom = Number(Math.max(0, candidate - 2 * MAX_SHIM_PER_SIDE).toFixed(3));

  return {
    cutAt: candidate,
    partSize: request.size,
    shim,
    coversFrom,
    coversTo: candidate,
    minutesToCut,
    rationale:
      shim === null
        ? `Cut the jaws at ${sizeLabel(request.profile, candidate)}, which is what this part needs anyway and a size the next job is likely to want.`
        : `Cut the jaws at ${sizeLabel(request.profile, candidate)} rather than ${sizeLabel(request.profile, request.size)}. This part then runs on ${shim.stack.map((s) => s.toFixed(3)).join(" + ")}" of shim per side, and the jaws are left at a standard size the next job can use.`,
    versusBespoke:
      `Cut bespoke at ${sizeLabel(request.profile, request.size)} and the jaws hold exactly one part. Cut at ${sizeLabel(request.profile, candidate)} and they cover ${coversFrom.toFixed(3)}–${sizeLabel(request.profile, candidate)} with shims. Same ${minutesToCut} minutes either way.`,
  };
}

/* ------------------------------------------------------------------ */
/* What it actually costs, which is the whole argument                 */
/* ------------------------------------------------------------------ */

export interface JawEconomics {
  /** Cost of cutting the jaws, charged once. */
  cutCost: number;
  /** Charged to this job if the cost falls entirely on it. */
  costIfBespoke: number;
  /** Charged to this job when spread over expected reuse. */
  costAmortised: number;
  expectedUses: number;
  /** Cost of this job when an existing jaw is reused instead. */
  costIfReused: number | null;
  verdict: string;
  /** False when an input was missing and every figure above is NaN. */
  computable: boolean;
}

export function jawEconomics(input: {
  minutesToCut: number;
  shopRatePerHour: number;
  blankCost: number;
  quantity: number;
  expectedUses: number;
  reuseSetupMinutes: number | null;
}): JawEconomics {
  // Without this, a missing shop rate produced "the jaws add $NaN a part" —
  // a cost figure a shop owner is being asked to make a make/buy decision on.
  // There is no rate to guess: the arithmetic simply cannot be done.
  const inputsUsable =
    Number.isFinite(input.minutesToCut) &&
    Number.isFinite(input.shopRatePerHour) &&
    Number.isFinite(input.blankCost) &&
    input.shopRatePerHour > 0;

  if (!inputsUsable) {
    return {
      cutCost: Number.NaN,
      costIfBespoke: Number.NaN,
      costAmortised: Number.NaN,
      expectedUses: Math.max(1, input.expectedUses),
      costIfReused: null,
      verdict:
        "The cost of cutting these jaws cannot be worked out — the shop rate, the blank cost or the time to cut is missing. Soft jaws are a make/buy argument and it needs those three numbers to have.",
      computable: false,
    };
  }

  const cutCost = (input.minutesToCut / 60) * input.shopRatePerHour + input.blankCost;
  const qty = Math.max(1, input.quantity);
  const uses = Math.max(1, input.expectedUses);

  const costIfReused =
    input.reuseSetupMinutes === null ? null : (input.reuseSetupMinutes / 60) * input.shopRatePerHour / qty;

  const costIfBespoke = cutCost / qty;
  const costAmortised = cutCost / uses / qty;

  const verdict =
    costIfReused !== null
      ? `Reusing what is in the drawer costs ${money(costIfReused)} a part against ${money(costIfBespoke)} to cut new. The jaws already exist; use them.`
      : uses > 1
        ? `Charged to this job alone the jaws add ${money(costIfBespoke)} a part. Spread over ${uses} expected jobs they add ${money(costAmortised)} — which is the difference between soft jaws being an expense and being tooling.`
        : `No reuse expected, so the full ${money(cutCost)} lands on this job — ${money(costIfBespoke)} a part at quantity ${qty}.`;

  return {
    cutCost,
    costIfBespoke,
    costAmortised,
    expectedUses: uses,
    costIfReused,
    verdict,
    computable: true,
  };
}

const money = (v: number) => `$${v.toFixed(2)}`;

/**
 * LATHE SOFT JAW GENERATOR — bore-in-place recipe + reuse matching.
 *
 * Chuck soft jaws are the opposite economy from mill vise jaws. A vise jaw
 * cut at 5.000" holds smaller parts with shims; a chuck jaw bored ⌀1.500
 * holds exactly ⌀1.500 — but it can always be RE-BORED LARGER. So:
 *
 * - the drawer search looks for jaw sets bored AT the grip diameter
 *   (drop straight on) or BELOW it (one cleanup re-bore, no new blanks);
 * - a jaw set bored larger than the grip is honestly useless for this
 *   part, and the engine says so instead of proposing shim fiction.
 *
 * The recipe itself is the part machinists get wrong most often stated
 * plainly: soft jaws are bored IN PLACE, UNDER PRELOAD, at the diameter
 * they will grip. Boring unloaded jaws hands you the jaw-stroke scatter
 * as runout. The preload ring sizing needs the chuck's jaw stroke; where
 * that is not recorded the step is emitted with the input named missing,
 * not with an invented number.
 *
 * Nothing here claims a TIR. Concentricity of a bore-in-place jaw is
 * real but it is a measurement, not a promise — the recipe ends with
 * "indicate a ground pin in the finished bore and record what you read".
 */

export interface LatheJawChuck {
  description: string;
  jawStroke: number | null;
  chuckDiameter: number | null;
  maxRPM: number | null;
}

export interface LatheJawBoringTool {
  station: string;
  description: string;
  barDiameter: number | null;
  minBoreDiameter: number | null;
  surfaceSpeedMin: number | null;
  surfaceSpeedMax: number | null;
  feedPerRevMin: number | null;
  feedPerRevMax: number | null;
}

export interface SoftJawBoreSpec {
  /** Diameter the jaws must grip — the part's stock or a finished journal. */
  gripDiameter: number | null;
  /** Axial length of the grip. */
  gripLength: number | null;
  chuck: LatheJawChuck | null;
  boringTool: LatheJawBoringTool | null;
}

export interface SoftJawBoreStep {
  order: number;
  text: string;
  /** Inputs this step needed and did not have — the step still prints, honestly incomplete. */
  missingInputs: string[];
}

export interface SoftJawBorePlan {
  ok: true;
  boreDiameter: number;
  boreDepth: number;
  /** Ring/plug the jaws clamp on while being bored. Null when the stroke is unrecorded. */
  preloadRingDiameter: number | null;
  boringRpm: number | null;
  boringFeedPerRev: number | null;
  steps: SoftJawBoreStep[];
  missingInputs: string[];
  assumptions: string[];
  developmentAnalysis: true;
}

export interface SoftJawBoreRefusal {
  ok: false;
  refusals: string[];
}

/** Depth clearance past the grip so the part never bottoms in the bore. */
const DEPTH_CLEARANCE = 0.05;

export function planSoftJawBore(spec: SoftJawBoreSpec): SoftJawBorePlan | SoftJawBoreRefusal {
  const refusals: string[] = [];
  if (spec.gripDiameter === null || spec.gripDiameter <= 0) {
    refusals.push("Grip diameter is not defined. CANVAS will not pick a bore size for you — the bore IS the grip diameter, and that comes from the part.");
  }
  if (spec.gripLength === null || spec.gripLength <= 0) {
    refusals.push("Grip length is not recorded on the setup. Record it on the holding panel; the bore depth follows from it.");
  }
  if (
    spec.boringTool?.minBoreDiameter != null &&
    spec.gripDiameter !== null &&
    spec.gripDiameter < spec.boringTool.minBoreDiameter
  ) {
    refusals.push(
      `T${spec.boringTool.station} cannot enter a ⌀${spec.gripDiameter.toFixed(3)} bore (its minimum is ⌀${spec.boringTool.minBoreDiameter.toFixed(3)}). Grip this diameter in a collet, or bore with a smaller bar.`,
    );
  }
  if (refusals.length > 0) return { ok: false, refusals };

  const grip = spec.gripDiameter!;
  const depth = spec.gripLength! + DEPTH_CLEARANCE;
  const missingInputs: string[] = [];
  const assumptions: string[] = [
    `Bore depth = grip length + ${DEPTH_CLEARANCE.toFixed(2)}" clearance so the part seats on the step face, never the bore bottom.`,
  ];

  // Preload ring: clamp the jaws on a ring at the back of the step while
  // boring, sized so the jaws sit near mid-stroke at the grip diameter.
  let ring: number | null = null;
  if (spec.chuck?.jawStroke != null) {
    ring = Number((grip + spec.chuck.jawStroke / 2).toFixed(3));
    assumptions.push(`Preload ring ⌀${ring.toFixed(3)} puts the jaws near mid-stroke when closed on ⌀${grip.toFixed(3)} — half the recorded ${spec.chuck.jawStroke.toFixed(3)}" stroke.`);
  } else {
    missingInputs.push("Chuck jaw stroke is not recorded — the preload ring cannot be sized. Record the stroke on the chuck's workholding entry.");
  }

  // Boring speed/feed from the tool record only — no invented cutting data.
  let rpm: number | null = null;
  let feed: number | null = null;
  if (spec.boringTool) {
    if (spec.boringTool.surfaceSpeedMin != null && spec.boringTool.surfaceSpeedMax != null) {
      // Aluminum jaw stock cuts easily; run the insert's rated ceiling, capped by the chuck.
      const sfm = spec.boringTool.surfaceSpeedMax;
      rpm = Math.round((sfm * 12) / (Math.PI * grip));
      if (spec.chuck?.maxRPM != null && rpm > spec.chuck.maxRPM) rpm = spec.chuck.maxRPM;
      assumptions.push(`Boring RPM from T${spec.boringTool.station}'s rated ${Math.round(sfm)} SFM at ⌀${grip.toFixed(3)}${spec.chuck?.maxRPM != null ? `, capped by the chuck's ${spec.chuck.maxRPM} RPM limit` : ""}.`);
    } else {
      missingInputs.push(`T${spec.boringTool.station} has no recorded surface-speed window — no boring RPM is suggested.`);
    }
    if (spec.boringTool.feedPerRevMin != null && spec.boringTool.feedPerRevMax != null) {
      feed = Number(((spec.boringTool.feedPerRevMin + spec.boringTool.feedPerRevMax) / 2).toFixed(4));
    } else {
      missingInputs.push(`T${spec.boringTool.station} has no recorded feed/rev window — no boring feed is suggested.`);
    }
  } else {
    missingInputs.push("No boring bar in the tool library — speeds and feeds are not suggested.");
  }

  const s = (order: number, text: string, missing: string[] = []): SoftJawBoreStep => ({ order, text, missingInputs: missing });
  const steps: SoftJawBoreStep[] = [
    s(1, "Mount the soft jaw blanks and number each jaw to its master jaw slot. Jaws are bored as a set, in the slots they will run in — swapping them afterwards throws the bore away."),
    s(
      2,
      ring !== null
        ? `Clamp the jaws on the ⌀${ring.toFixed(3)} preload ring at the BACK of the jaw faces (behind where the bore will be), at normal working pressure. The jaws must be under load while bored — an unloaded bore hands you the jaw-stroke scatter as runout.`
        : "Clamp the jaws on a preload ring at the BACK of the jaw faces at normal working pressure. Ring size not computed — the chuck's jaw stroke is unrecorded.",
      ring === null ? ["chuck jaw stroke"] : [],
    ),
    s(3, `Face the jaw fronts true, then bore ⌀${grip.toFixed(4)} (+0.0000 / −0.0005) to ${depth.toFixed(3)}" deep. Bore, do not drill — the bore must be concentric with the spindle, and it is only that if the spindle cuts it in place.`),
    s(4, `Face the step land square at ${depth.toFixed(3)}" depth. The part locates on this face in Z; a ragged step is a Z-datum error on every part that follows.`),
    s(5, "Remove the ring, deburr, and close the jaws on nothing to confirm none touch before the bore does."),
    s(6, "Indicate a ground pin held in the finished bore and RECORD the runout you read. Concentricity of a bored-in-place jaw is real, but it is a measurement, not a promise — CANVAS does not state a TIR it has not seen."),
  ];

  return {
    ok: true,
    boreDiameter: Number(grip.toFixed(4)),
    boreDepth: Number(depth.toFixed(3)),
    preloadRingDiameter: ring,
    boringRpm: rpm,
    boringFeedPerRev: feed,
    steps,
    missingInputs,
    assumptions,
    developmentAnalysis: true,
  };
}

/* ------------------------------------------------------------------ */
/* Reuse: the drawer search, lathe rules                                */
/* ------------------------------------------------------------------ */

export interface LatheJawSet {
  id: string;
  description: string;
  boredDiameter: number | null;
  boredDepth: number | null;
}

export type JawReuseKind = "DIRECT" | "REBORE" | "UNUSABLE" | "BLANK";

export interface LatheJawMatch {
  jawSet: LatheJawSet;
  kind: JawReuseKind;
  reason: string;
}

/** Re-boring below this cleanup allowance would be chasing a spring cut. */
const MIN_REBORE = 0.01;
/** Past this the jaws run out of meat; a full re-cut is a new blank set. */
const MAX_REBORE_TOTAL = 0.5;

export function findReusableLatheJaws(gripDiameter: number, gripLength: number, inventory: LatheJawSet[]): LatheJawMatch[] {
  const matches: LatheJawMatch[] = inventory.map((jaw) => {
    if (jaw.boredDiameter === null) {
      return { jawSet: jaw, kind: "BLANK" as const, reason: `${jaw.description} is still blank — bore it with the recipe below.` };
    }
    const growth = gripDiameter - jaw.boredDiameter;
    const depthOk = jaw.boredDepth === null || jaw.boredDepth >= gripLength - 0.002;
    if (Math.abs(growth) <= 0.0005 && depthOk) {
      return { jawSet: jaw, kind: "DIRECT" as const, reason: `${jaw.description} is already bored ⌀${jaw.boredDiameter.toFixed(4)} — this part drops straight in. Indicate before trusting it.` };
    }
    if (growth >= MIN_REBORE && growth <= MAX_REBORE_TOTAL) {
      return {
        jawSet: jaw,
        kind: "REBORE" as const,
        reason: `${jaw.description} is bored ⌀${jaw.boredDiameter.toFixed(4)} — re-bore ${growth.toFixed(4)}" up to ⌀${gripDiameter.toFixed(4)}. A bored jaw only ever grows; this costs one cleanup pass, not a blank set.`,
      };
    }
    if (growth < 0) {
      return {
        jawSet: jaw,
        kind: "UNUSABLE" as const,
        reason: `${jaw.description} is bored ⌀${jaw.boredDiameter.toFixed(4)} — larger than this ⌀${gripDiameter.toFixed(4)} grip. A chuck jaw cannot shrink; these jaws cannot hold this part.`,
      };
    }
    if (!depthOk) {
      return {
        jawSet: jaw,
        kind: "REBORE" as const,
        reason: `${jaw.description} matches on diameter but its ${jaw.boredDepth!.toFixed(3)}" step is shallower than the ${gripLength.toFixed(3)}" grip — deepen the bore before use.`,
      };
    }
    return {
      jawSet: jaw,
      kind: "UNUSABLE" as const,
      reason: `${jaw.description} would need ${growth.toFixed(3)}" of re-bore — past the ${MAX_REBORE_TOTAL.toFixed(1)}" the jaw section can give. Treat it as a new blank set.`,
    };
  });

  const rank: Record<JawReuseKind, number> = { DIRECT: 0, REBORE: 1, BLANK: 2, UNUSABLE: 3 };
  return matches.sort((a, b) => rank[a.kind] - rank[b.kind]);
}

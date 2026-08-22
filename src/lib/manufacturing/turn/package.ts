import { db } from "@/lib/db";
import type { RotationalProfile } from "./geometry";
import { generateTurnToolpath, type TurnOperation, type TurnToolpathResult } from "./operations";
import { assessChuckGrip, assessStickout, assessBoringBar, assessPartOff } from "./analysis";
import { evaluateTurnReadiness } from "./readiness";
import { emitLatheProgram } from "./post";
import { parseThreadPitch } from "@/lib/engines/cam/engine";

/**
 * THE TURNING PACKAGE — one assembly of the rotational model, its
 * deterministic toolpaths, the hold analyses, worst-gate readiness and
 * the development post output.
 *
 * This exists because the export mint MUST re-run the same gate the
 * workspace shows — "the rendered button is not the gate". One function,
 * called by both the page and the mint, so they can never drift apart.
 * Organisation id is a parameter that always comes from the session.
 */

export interface TurnPackage {
  part: { id: string; name: string; partNumber: string | null; training: boolean };
  revisionId: string;
  rot: NonNullable<Awaited<ReturnType<typeof db.rotationalPart.findFirst>>>;
  profile: RotationalProfile;
  plan: TurnOperation[];
  results: { op: TurnOperation; result: TurnToolpathResult }[];
  totalMinutes: number;
  lathe: Awaited<ReturnType<typeof db.latheMachine.findFirst>>;
  holding: Awaited<ReturnType<typeof db.latheWorkholding.findFirst>>;
  tools: Awaited<ReturnType<typeof db.turningTool.findMany>>;
  metrology: Awaited<ReturnType<typeof db.metrologyDevice.findMany>>;
  analyses: {
    grip: ReturnType<typeof assessChuckGrip>;
    stickout: ReturnType<typeof assessStickout>;
    boringBar: ReturnType<typeof assessBoringBar> | null;
    partOff: ReturnType<typeof assessPartOff> | null;
  };
  readiness: ReturnType<typeof evaluateTurnReadiness>;
  blocking: ReturnType<typeof evaluateTurnReadiness>["gates"];
  program: { code: string; refusals: string[] };
}

export async function buildTurnPackage(organizationId: string, partId: string): Promise<TurnPackage | null> {
  const part = await db.part.findFirst({ where: { id: partId, organizationId } });
  if (!part) return null;
  const revision = await db.partRevision.findFirst({ where: { partId: part.id }, orderBy: { createdAt: "desc" } });
  if (!revision) return null;
  const rot = await db.rotationalPart.findFirst({ where: { partRevisionId: revision.id, organizationId } });
  if (!rot) return null;

  const [lathe, holding, tools, metrology] = await Promise.all([
    rot.latheMachineId ? db.latheMachine.findFirst({ where: { id: rot.latheMachineId, organizationId } }) : null,
    rot.workholdingId ? db.latheWorkholding.findFirst({ where: { id: rot.workholdingId, organizationId } }) : null,
    db.turningTool.findMany({ where: { organizationId } }),
    db.metrologyDevice.findMany({ where: { organizationId } }),
  ]);

  const profile = JSON.parse(rot.profileJson) as RotationalProfile;
  const plan = JSON.parse(rot.planJson) as TurnOperation[];

  /* ---- toolpaths, deterministic ---- */
  const toolWidthFor = (station: string) => tools.find((t) => t.station === station)?.grooveWidth ?? null;
  const results = plan.map((op) => {
    const seg = op.targetSegmentId ? profile.segments.find((s) => s.id === op.targetSegmentId) : null;
    const pitch = seg?.thread ? parseThreadPitch(seg.thread) : null;
    return { op, result: generateTurnToolpath(op, profile, toolWidthFor(op.toolStation), pitch) };
  });
  const totalMinutes = results.reduce((t, r) => t + (r.result.ok ? r.result.toolpath.estimatedMinutes : 0), 0);

  /* ---- hold analyses ---- */
  const grip = assessChuckGrip({
    gripDiameter: profile.stockDiameter,
    gripLength: rot.gripLength ?? 0,
    jawMaterial: (holding?.jawMaterial as "HARD" | "SOFT_MACHINED" | null) ?? null,
    serrated: holding?.serrated ?? null,
    clampForceLbf: rot.clampForceLbf,
    stickout: rot.stickout ?? 0,
    chuckMaxRpm: holding?.maxRPM ?? null,
    programmedMaxRpm: rot.maxRpmClamp,
  });
  const stickout = assessStickout({
    unsupportedLength: rot.stickout ?? 0,
    diameter: profile.stockDiameter,
    tailstock: rot.tailstockActive,
  });
  /*
   * Boring bar reach.
   *
   * The bar's diameter and stickout used to fall back to 0.625" and 3" when
   * the crib held no boring bar, and its material was passed as "STEEL"
   * unconditionally — there is no column recording it. So a shop with no bar
   * on file got a confident length-to-diameter verdict computed from a bar
   * that does not exist, and assessBoringBar's own message for an unrecorded
   * material ("steel guideline 4xD assumed, carbide reaches 6xD") could never
   * fire, because it was never told the material was unknown.
   *
   * Now the assessment runs only against a bar the shop actually recorded,
   * and a plan that bores with no bar on file is reported as an unassessed
   * gate rather than as a silent absence — boringBar: null already means
   * "this plan does not bore", and those are different facts.
   */
  const boringOps = plan.filter((o) => o.type.startsWith("ID_BORE"));
  const bar = tools.find((t) => t.toolClass === "BORING_BAR") ?? null;
  const barUsable = bar && bar.barDiameter != null && bar.stickout != null;
  const boringBar =
    boringOps.length && barUsable
      ? assessBoringBar({
          barDiameter: bar.barDiameter!,
          stickout: bar.stickout!,
          boreDepth: Math.max(...boringOps.map((o) => Math.abs(o.endZ - o.startZ))),
          // No column records this. assessBoringBar says so in its own words.
          barMaterial: null,
        })
      : null;
  const boringBarUnrecorded = boringOps.length > 0 && !barUsable;
  const cutoff = plan.find((o) => o.type === "PART_OFF");
  const partOff = cutoff
    ? assessPartOff({
        cutoffZ: cutoff.startZ,
        cutoffDiameter: cutoff.startDiameter,
        distanceFromChuck: cutoff.startZ - (rot.gripLength ?? 0) + (rot.stickout ?? 0) - (profile.stockLength - (rot.gripLength ?? 0)),
        toolWidth: toolWidthFor(cutoff.toolStation),
        hasPartsCatcher: lathe?.hasPartsCatcher ?? false,
        hasSubSpindle: lathe?.hasSubSpindle ?? false,
        tailstockActive: rot.tailstockActive,
      })
    : null;

  /* ---- inspection capability, simplest honest form ---- */
  const criticalTol = Math.min(
    ...profile.segments.filter((s) => s.critical && s.toleranceMinus != null).map((s) => (s.tolerancePlus ?? 0) + (s.toleranceMinus ?? 0)),
    Infinity,
  );
  const bestInstrument = metrology
    .filter((m) => m.deviceType === "MICROMETER" || m.deviceType === "BORE_GAUGE" || m.deviceType === "CMM")
    .sort((a, b) => a.uncertainty - b.uncertainty)[0];
  const inspectionCapable =
    criticalTol === Infinity ? true : bestInstrument ? bestInstrument.uncertainty * 4 <= criticalTol : false;

  /* ---- readiness, worst-gate ---- */
  const cssUsed = plan.some((o) => o.params.cssEnabled);
  /*
   * The material gate used to be handed a literal `true`, and it is a
   * PASS/FAIL gate — so the material gate on every turned part could not
   * fail. It reads the part's own intent now, exactly as the milling side
   * does.
   */
  const intentMaterial = (() => {
    try {
      const intent = JSON.parse(revision.intentJson ?? "{}") as { material?: { value?: unknown } };
      const v = intent.material?.value;
      return typeof v === "string" && v.trim() !== "" ? v : null;
    } catch {
      return null;
    }
  })();

  const readiness = evaluateTurnReadiness({
    profile,
    materialKnown: intentMaterial !== null,
    boringBarUnrecorded,
    latheSelected: Boolean(lathe),
    workholdingSelected: Boolean(holding),
    grip,
    stickout,
    boringBar,
    partOff,
    toolsAssigned: plan.filter((o) => tools.some((t) => t.station === o.toolStation)).length,
    toolsRequired: plan.length,
    chuckRpmKnown: holding?.maxRPM != null,
    cssUsed,
    inspectionCapable,
    postSelected: true,
    humanApproved: rot.humanApproved,
  });
  const blocking = readiness.gates.filter((g) => g.blocking && (g.status === "FAIL" || g.status === "NOT_ATTEMPTED"));

  /* ---- development post ---- */
  const postOps = results
    .filter((r) => r.result.ok)
    .map((r) => ({
      toolpath: (r.result as { ok: true; toolpath: never }).toolpath,
      station: r.op.toolStation,
      description: r.op.label,
      cssEnabled: r.op.params.cssEnabled,
      surfaceSpeed: r.op.params.surfaceSpeed,
      rpm: r.op.params.rpm,
      coolant: r.op.params.coolant === "FLOOD",
    }));
  const program = emitLatheProgram(postOps, {
    programNumber: "2001",
    partName: part.name,
    machine: lathe ? `${lathe.manufacturer} ${lathe.model}` : "No lathe",
    workOffset: "G54",
    maxRpmClamp: rot.maxRpmClamp,
    generatedAtIso: new Date().toISOString().slice(0, 10),
  });

  return {
    part: { id: part.id, name: part.name, partNumber: part.partNumber, training: part.training },
    revisionId: revision.id,
    rot,
    profile,
    plan,
    results,
    totalMinutes,
    lathe,
    holding,
    tools,
    metrology,
    analyses: { grip, stickout, boringBar, partOff },
    readiness,
    blocking,
    program,
  };
}

import type { ManufacturingPackage } from "@/lib/package";
import type { PostDefinition, PreflightItem } from "./post";

/**
 * The NC pre-flight gate, in one place.
 *
 * This used to live inline in the NC page's render body, which meant the gate
 * existed exactly once — until the export path needed it too, at which point
 * "the page checks it" would have quietly become "the page checks it and the
 * server actions trust the page". A disabled button is not a gate: server
 * actions are POST endpoints reachable regardless of rendered button state.
 *
 * Every consumer — page render, program generation, export mint, export
 * record — calls this function against a package freshly built from the
 * session's organisation. If the gate logic exists in two places, it does not
 * exist.
 *
 * `preflightPassed()` stays worst-case by construction: every required item
 * must be PASS. No arithmetic, no averaging. See CLAUDE.md principle 1.
 *
 * This module carried a server-only import and every one of its own imports
 * is a type, erased at build. The guard protected nothing and stopped the
 * export gate being exercised at all — which for a gate is the worse trade.
 */
export function buildPreflight(
  pkg: ManufacturingPackage,
  post: PostDefinition | null | undefined,
): PreflightItem[] {
  const machine = pkg.primaryMachine;
  const realToolpaths = pkg.toolpaths.filter((t) => !t.isPlaceholder);

  return [
    item("machine", "Machine selected", Boolean(machine), machine ? `${machine.manufacturer} ${machine.model}` : "No machine on this setup", true),
    item("post", "Post processor selected", Boolean(post), post ? post.name : "None", true),
    item("units", "Units confirmed", pkg.revision.units === "IN" || pkg.revision.units === "MM", `Program in ${pkg.revision.units === "IN" ? "inches (G20)" : "millimetres (G21)"}`, true),
    item("stock", "Stock verified", Boolean(pkg.revision.stock), pkg.revision.stock ? `${pkg.revision.stock.x} × ${pkg.revision.stock.y} × ${pkg.revision.stock.z}` : "Stock not defined", true),
    item(
      "workholding",
      "Workholding verified",
      // `.every()` on an empty object is true, so a package with no setups
      // passed "Workholding verified" with the detail "No setups to
      // evaluate". Nothing has been verified there.
      //
      // The toolpath item below was fixed for this exact reason and states
      // the rule: zero is a FAIL rather than a vacuous pass. In practice the
      // toolpath item currently masks this one — no setups means no
      // operations means no toolpaths — but an item on this list has to state
      // its own fact. Relying on a neighbour to catch it is the reasoning
      // this file was written to remove.
      Object.keys(pkg.workholdingBySetup).length > 0 &&
        Object.values(pkg.workholdingBySetup).every((a) => a.level === "SAFE" || a.level === "LIKELY_SAFE"),
      workholdingSummary(pkg),
      true,
    ),
    item("tools", "Tools verified", pkg.assignedTools.length > 0, `${pkg.assignedTools.length} tools assigned`, true),
    item(
      "toollengths",
      "Tool lengths verified",
      // Same rule: no tools is not "every tool has a stickout recorded".
      pkg.assignedTools.length > 0 && pkg.assignedTools.every((t) => t.stickout > 0),
      "Stickout recorded for every assigned tool. Length offsets must still be set at the machine.",
      true,
    ),
    item(
      "toolpaths",
      "Toolpaths generated",
      pkg.toolpaths.length > 0 && realToolpaths.length === pkg.toolpaths.length,
      toolpathDetail(pkg.toolpaths.length, realToolpaths.length),
      true,
    ),
    item("errors", "No toolpath errors", pkg.toolpathErrors.length === 0, pkg.toolpathErrors.length === 0 ? "All operations produced a path" : `${pkg.toolpathErrors.length} operations failed`, true),
    item(
      "criticaldims",
      "Critical dimensions reviewed",
      pkg.revision.features.filter((f) => f.critical).every((f) => Boolean(f.inspectionMethod)),
      "Every critical feature has an inspection method",
      true,
    ),
    item("simulation", "Simulation completed", pkg.simulationRun, pkg.simulationRun ? "Development visualisation run" : "Not run", true),
    item("approval", "Operator approval", pkg.approved, pkg.approved ? "Package approved" : "No approval recorded", true),
  ];
}

function item(id: string, label: string, pass: boolean, detail: string, required: boolean): PreflightItem {
  return { id, label, status: pass ? "PASS" : "FAIL", detail, required };
}

/**
 * The toolpath pre-flight item, stated as the worst fact rather than the best.
 *
 * This used to pass on `realToolpaths.length > 0` — one operation with motion
 * out of any number — while its own detail line read "3 operations with
 * motion, 6 without an engine". A green PASS next to a sentence describing six
 * missing operations, on the list `preflightPassed()` uses to decide whether
 * executable NC may leave the building.
 *
 * The consequence is not cosmetic. An operation with no engine is not omitted
 * from the program; the post writes it in as a comment and moves on. The
 * program is syntactically complete, runs start to finish, and simply never
 * cuts those features — and the operations that reach that path are BORE, TAP
 * and ADAPTIVE_2D, which is to say the bearing seats and the threads. An
 * operator who trusts the PASS gets a part that looks machined and is missing
 * the features nobody would think to check for absence.
 *
 * So the gate passes only when every operation produced motion. Zero
 * operations is a FAIL rather than a vacuous pass, for the same reason.
 */
function toolpathDetail(total: number, real: number): string {
  if (total === 0) return "No operations to post";
  const missing = total - real;
  if (missing === 0) return `All ${total} operations produced motion`;
  return `${missing} of ${total} operations have no toolpath engine. The post writes each one into the program as a skipped comment, so the program would run to completion without cutting them.`;
}

function workholdingSummary(pkg: ManufacturingPackage): string {
  const levels = Object.values(pkg.workholdingBySetup).map((a) => a.level);
  if (levels.length === 0) return "No setups to evaluate — nothing has been assessed";
  const bad = levels.filter((l) => l !== "SAFE" && l !== "LIKELY_SAFE");
  return bad.length === 0 ? "All setups assessed safe or likely safe" : `${bad.length} setup(s) at ${bad.join(", ")}`;
}

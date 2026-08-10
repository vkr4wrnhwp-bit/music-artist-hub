# CANVAS — Workspace Refactor & Capability Specification

Status: **PLANNED — design work deferred by owner decision (2026-08-10).**
This document is the reference for when it starts. Nothing here overrides the
locked principles in CLAUDE.md; where the brief conflicted with them, the
conflict is recorded, not silently resolved.

Reference layout: the approved mockup (dark shell, banner under header,
maximised viewport, docked feature panel, tabular operation timeline).

---

## 0. Triage — every requested item, honestly

| Item | Verdict | Why |
|---|---|---|
| Dark work canvas, realistic metal render | **OWNER DECISION REQUIRED** | Reverses the approved dark-shell / light-work-canvas design implemented this phase. The mockup shows the reversal working; it is a legitimate direction, but it is a reversal, not a refinement. Decide once, then commit. |
| Consolidated navigation (kill sidebar/sub-tab duplication) | **SHIP** | The duplication is real: the part sidebar and the top strip both list Setups/Tooling/Inspection/etc. One slim global rail + one contextual part dock. |
| Viewport ≥75%, dockable feature panel | **SHIP** | Aligns with the existing workspace direction. Panel becomes collapsible; state lives in `interaction.tsx`, nowhere else. |
| Remove floating callouts from the viewport | **SHIP WITH CHANGES** | HOLD callouts carry real computed values (grip depth, contact area, holding margin) — that was the point of the HOLD view. They move to a docked measurement strip anchored to the viewport edge with leader lines, not deleted. Values never disappear into tooltips. |
| Global action banner + Fix Now drawer | **SHIP WITH CHANGES** | The banner is the existing `NextActionPanel` promoted to full width — worst gate first, count of blocking items (the allowed count shape). The drawer routes to the evidence screen that clears each gate. **It must never contain a control that clears a gate in place** — principle 2. "Fix Now" means "take me to the evidence", not "mark resolved". |
| Vertical / expandable operation timeline | **SHIP** | The mockup's table (Op#, type, description, tool, cycle time, moves, per-setup SAFE/HIGH RISK rail) is better than the horizontal cards. Risk levels come from `workholding.ts` `RiskLevel`, never restyled ad hoc. |
| Purge "1 without an engine" | **ALREADY DONE** | BORE and TAP have real engines as of `9f6c1c4`; the string no longer occurs. ADAPTIVE_2D remains labelled — because it remains true. |
| Purge "WHAT THIS PANEL IS NOT" | **SHIP WITH CHANGES** | The placement can change (footer → an `ⓘ` disclosure per panel). The statements cannot be deleted while they are true — principle 5. Honesty copy moves; it does not vanish. |
| WCAG AAA contrast, label/data typography split | **SHIP** | Audit `--c-muted` on light surfaces; enforce label = grotesk caps / data = mono via the existing `.instrument-label` / `tabular-nums` conventions. |
| Machinist tablet mode | **SHIP (spec §3)** | Buildable now from existing data. Sign-offs are HUMAN-typed audit entries; a sign-off clears no gate that requires evidence. |
| Live metrology sync (BLE calipers, MTConnect) | **PHASE — bridge required** | Web Bluetooth reaches BLE calipers/mics in Chromium only; it is a legitimate v1 (reading lands as `MEASURED` provenance with instrument id). MTConnect/CMM require the local Bridge agent (same agent as verified NC export). UI shows NOT CONNECTED until a device is genuinely paired. |
| In-browser stock removal simulator | **SHIP AS WHAT IT IS** | Deterministic voxel/dexel removal from real `Move[]` data is buildable and useful (retract clearance, fixture collision against the HOLD geometry). It is geometry, not physics. Label: MATERIAL REMOVAL — GEOMETRIC SIMULATION. The word "physics-backed" does not appear until forces are actually modelled. |
| Generative soft jaw creator | **PARTIAL EXISTS** | `workholding.ts` already computes `SoftJawResult`/`JawGeometry`; `part-solid.ts` builds the part negative. Remaining work: subtract negative from blank, export STEP/DXF, machinable-check via the jaw-family engine. |
| AS9102 FAIR generator | **SHIP** | Genuinely one of the highest-value cheap items: Form 1/2/3 assemble from `Feature`, tolerances, `Measurement` rows and instrument records. Fields CANVAS cannot source (material certs, special processes) render as REQUIRED — NOT ON FILE, never blank-but-pretty. |
| Voice operator | **PILOT ONLY** | Web Speech API accuracy on a shop floor (coolant pumps, air guns) is unproven; a misheard dimension is worse than no dimension. Pilot = read-back-and-confirm loop, never direct commit. |
| Closed-loop adaptive machining (auto G10) | **PHASE — bridge + hard bounds** | See §5. Deterministic offset correction from probe results is standard practice, but CANVAS writes nothing to a control until the Bridge exists, and then only within a human-pre-approved correction band per feature. Out-of-band drift stops the loop and pages a human. Never an LLM in this loop. |
| AR shop floor overlays | **NOT NOW** | WebXR on shop hardware is not there; projecting torque specs onto an enclosure via tablet passthrough is a demo, not a tool. Revisit when the Bridge + fixed camera calibration exist. |
| Physics-informed AI feeds/speeds | **PHASE — telemetry first** | Requires spindle-load + acoustic telemetry that does not exist yet (`MachineTelemetry` below is the contract, born NOT CONNECTED). Adjustment models are control-theory, bounded, and never emit motion — they propose parameter deltas that pass the same gates. |
| Autonomous CAD→part pipeline | **PHASE — STEP first** | The brief's framing ("shift human effort to gate approvals") is exactly CANVAS's north star and is compatible. The blocker is real: there is no STEP/B-rep importer. Order: STEP import → deterministic feature recognition (2.5D taxonomy already exists) → auto-proposal of datums/workholding/ops as `AI_INFERENCE`/`CALCULATED` provenance → human clears gates. Zero-click ingest, never zero-click export. |

---

## 1. Component architecture

### 1.1 Layout grid

```
┌──────────────────────────────────────────────────────────────┐
│ header  (part identity · rev · worst-gate status chip)        │ 48px
├──────────────────────────────────────────────────────────────┤
│ action-banner (worst blocking gate · n blocking · Fix Now)    │ 40px, absent when clear
├────┬────────────────────────────────────────────┬────────────┤
│nav │            viewport (3D)                   │ feature    │
│rail│  ≥75% width when panel docked/collapsed    │ panel      │
│56px│  context rail (PART·HOLD·CUT·VERIFY·$) top │ 360px dock │
│    │  measurement strip docked bottom-left      │ collapsible│
├────┴────────────────────────────────────────────┴────────────┤
│ operation timeline (table rows, per-setup risk rail)          │ 280px, collapsible
└──────────────────────────────────────────────────────────────┘
```

CSS Grid, no magic margins:

```css
.workspace {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) auto; /* auto = 360px | 0 */
  grid-template-rows: 48px auto minmax(0, 1fr) auto;
  grid-template-areas:
    "nav header  header"
    "nav banner  banner"
    "nav viewport panel"
    "nav timeline timeline";
}
```

### 1.2 Component tree

```
<PartWorkspace>                          // server: buildPackage() once
 ├─ <GlobalNavRail/>                     // HOME PARTS MACHINES TOOLING METROLOGY JOBS KNOWLEDGE SETTINGS
 ├─ <WorkspaceHeader>
 │   └─ <PartStatusSummary/>             // existing — worst gate, never a %
 ├─ <ActionBanner>                       // NextActionPanel, promoted
 │   └─ <ResolutionDrawer/>              // routes to evidence; clears nothing
 ├─ <InteractionProvider>                // existing single state store
 │   ├─ <ContextRail/>                   // existing PART·HOLD·CUT·VERIFY·$
 │   ├─ <Viewport>                       // existing scene.tsx
 │   │   ├─ <MeasurementStrip/>          // NEW: docked values + leader lines (replaces floating callouts)
 │   │   └─ <ViewCube/> <DisplayModes/>
 │   ├─ <FeaturePanel docked|collapsed/> // existing, gains dock state in interaction.tsx
 │   └─ <OperationTimeline>              // replaces operation-runway cards
 │       ├─ <SetupRail/>                 // SETUP 01 · SAFE / SETUP 02 · HIGH RISK (RiskLevel verbatim)
 │       └─ <OperationRow/>*             // op# · type glyph · desc · tool · cycle · moves · SELECTED
 └─ <MachinistModeGate/>                 // §3 role toggle
```

Rules: every visual state derives from `interaction.tsx` or engine output.
No component computes a classification the engines already compute
(the `measurementGeometry` lesson is codified: one classifier, one home).

### 1.3 Theme tokens

Extend `globals.css`; do not fork a second token set. If the dark-canvas
decision is taken, it is executed by re-pointing the `--c-*` indirection
(exactly how `.canvas-shell` already works), not by touching components.
Metallic accents are gradients on *chrome* (rails, rules, chips) only —
never on data surfaces, where they cost contrast.

---

## 2. TypeScript contracts

The rule for all four: **extend the engine types, never re-declare them.**
A UI-local copy of a gate type is how a screen ends up disagreeing with the
gate that blocks NC export.

```ts
import type { ReadinessGate, GateStatus } from "@/lib/engines/readiness";
import type { RiskLevel } from "@/lib/engines/workholding";
import type { Source, Confidence, Provenanced } from "@/lib/provenance";
import type { OperationType } from "@/lib/engines/cam/types";

/** UI projection of a gate. `gate` is the engine object, untranslated. */
export interface PartReadinessGate {
  gate: ReadinessGate;                    // status/blocking come from here only
  /** Where the evidence that could change this gate is recorded. */
  evidenceHref: string | null;
  /** Typed false for gates no confirmation can clear (inspection capability). */
  clearableByConfirmation: false | boolean;
}

export interface FeatureInspection {
  featureId: string;
  method: string | null;                  // null = not assigned, rendered as such
  instrumentId: string | null;
  /** Engine verdict — CAPABLE | MARGINAL | NOT_CAPABLE | NOT_REQUIRED. */
  capability: string;
  measurements: {
    value: Provenanced<number>;           // {value, source, confidence, confirmedByUser}
    uncertainty: number;
    instrumentId: string | null;
    at: string;
    by: { actor: "HUMAN" | "SYSTEM"; userId: string | null }; // never inferred
  }[];
  /** Live-sync state. Absent hardware renders NOT CONNECTED, never a spinner. */
  liveSource: { kind: "BLE" | "MTCONNECT" | "NONE"; deviceId: string | null };
}

export interface SetupOperation {
  id: string;
  sequence: number;
  type: OperationType;
  label: string;
  toolNumber: number | null;
  toolDescription: string | null;
  /** Nulls, not zeros, when no engine result exists. */
  cycleMinutes: number | null;
  moveCount: number | null;
  isPlaceholder: boolean;                 // ADAPTIVE_2D only, labelled in UI
  setupRisk: RiskLevel;                   // verbatim from workholding.ts
  warnings: string[];
}

/** Born disconnected. Every field is Provenanced or explicitly absent. */
export interface MachineTelemetry {
  machineId: string;
  connection: { state: "NOT_CONNECTED" | "BRIDGE" | "MTCONNECT"; lastSeen: string | null };
  spindleLoadPct: Provenanced<number> | null;   // null until a real stream exists
  spindleRPM: Provenanced<number> | null;
  feedOverridePct: Provenanced<number> | null;
  alarms: { code: string; text: string; at: string }[];
  /** Wear-offset ledger — §5. Read-only in the web app, forever. */
  offsetLedger: {
    register: string;                     // e.g. "G10 L12 P4"
    delta: number;
    appliedBy: "BRIDGE";                  // the web client never writes offsets
    withinApprovedBand: boolean;
    probeMeasurementId: string;
    at: string;
  }[];
}
```

---

## 3. Machinist tablet view

**Toggle:** a role switch in the header — ENGINEERING / MACHINIST — persisted
per user. Machinist mode is a *projection* of the same package: it hides
depth, it does not hold different truth. One store (`interaction.tsx` +
server package), two renderings.

**Layout (≥1024px touch, high contrast, 48px minimum targets):**

```
┌────────────────────────────────────────────────┐
│ CNV-001 · SETUP 01 OF 02 · [NOT READY — 4]     │
├────────────────────────────────────────────────┤
│ 1. SETUP    photo/diagram · vise · jaw set ·   │
│             stock orientation · torque value    │
│ 2. TOOLS    T# · description · stickout ·      │
│             projection check [MEASURED ✓ by me] │
│ 3. PROBE    probing routine steps · expected    │
│             values ± band                       │
│ 4. RUN      per-op card: op# · tool · cycle ·  │
│             the one warning that matters        │
│ 5. SIGN-OFF "Setup complete as documented"      │
└────────────────────────────────────────────────┘
```

**State logic:** the five sections are a checklist state machine
(`PENDING → DONE(by, at)`), stored as HUMAN-typed audit entries.
A sign-off is testimony, recorded as such. It clears **no** readiness gate
that requires evidence; if every gate is already clear, it is the operator
approval the NC pre-flight looks for. If gates are failing, the sign-off
control is replaced by the failing-gate list — the tablet never offers a
signature over a red gate.

Voice, when piloted, lives here: push-to-talk → transcript → **read-back
confirmation on screen** → then commit as a measurement. Never direct commit.

---

## 4. Micro-copy standard

- Labels: grotesk caps (`.instrument-label`). Data: mono, `tabular-nums`,
  units always (`3.0000 in`, never `3`).
- Counts follow the outstanding-work shape (`4 BLOCKING`, `2 REVIEW`) —
  never `n of m passed`, never a percentage of readiness.
- Limits copy moves into per-panel `ⓘ` disclosures but keeps its content.
  A capability that does not exist is labelled where the user would look
  for it, in caps: NOT CONNECTED, GEOMETRIC SIMULATION, DEVELOPMENT.
- Tooltips explain; they never contain the only statement of a limit that
  changes what an operator would do.

---

## 5. Closed-loop adaptive machining — the honest architecture

The loop is legitimate manufacturing practice; the constraint is *where it
runs and what bounds it*.

1. **Probe result** lands as a `MEASURED` measurement (Bridge, MTConnect, or
   manual entry) tied to feature + offset register.
2. **Correction engine** (deterministic, `engines/`): proposed delta =
   f(departure, gauge R&R, last n results). Emits `CALCULATED` provenance
   with the full method open (`show-calculation` pattern).
3. **Human arms the loop once per feature**: approves a correction *band*
   (e.g. ±0.0008" total, max 0.0002" per adjustment) — an audited approval.
4. **Bridge applies** G10 writes only inside the armed band. The web client
   has no code path that writes to a control — the `offsetLedger` above is
   read-only by type.
5. **Out-of-band → stop.** Drift beyond the band, oscillation, or a stale
   probe halts the loop and raises a blocking action. The loop corrects
   drift; it never chases a broken process.
6. No LLM anywhere in 1–5. An LLM may *summarise* the ledger; it may not
   touch it.

Prerequisite for all of it: the local Bridge agent (already specified as the
NC-export phase-2 consumer — same mint/authorisation pattern, same server-side
gate checks).

---

## 6. Sequencing

1. **Now (no design dependency):** AS9102 FAIR generator · soft-jaw geometry
   export · STEP importer spike · engine unit tests.
2. **Design phase (this spec):** layout consolidation → banner/drawer →
   operation timeline → dockable panel → measurement strip → contrast audit.
   Dark-canvas decision taken explicitly at the start.
3. **Machinist mode** after the design phase (it inherits the new tokens).
4. **Bridge agent** unlocks: live metrology (MTConnect/CMM), telemetry,
   adaptive machining, verified-eject NC export.
5. **Autonomy ladder:** STEP import → feature recognition → auto-proposals →
   (much later) adaptive feeds from telemetry.

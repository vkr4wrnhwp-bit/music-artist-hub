# MX LAB — Competition Mode

Purpose: Define the behavior, hardware state, and approval tracking required when MX Node hardware is present on a bike in sanctioned competition.

Status: Phase 2+ target — design brief, pending physical verification and per-sanctioning-body approval. Nothing in this document makes competition use legal.

---

COMPETITION USE REQUIRES APPROVAL FROM THE APPLICABLE SANCTIONING BODY. SOFTWARE CONFIGURATION DOES NOT ESTABLISH LEGALITY.

## 1. Boundary

The MX Node is strictly passive: it must never control fueling, ignition, throttle, map slots, or any engine behavior, and its failure must not affect the motorcycle. Competition mode adds restrictions on top of that baseline; it never adds capability.

**No traction-control-like intervention, ever.** The node cannot intervene by design — there is no actuator, no bus transmit path, and no control output in the hardware. Competition mode does not "turn intervention off"; intervention does not exist to turn off. This is verifiable by inspection of the hardware.

## 2. Competition-mode behavior

| Requirement | Specification |
|---|---|
| Local logging only | All data is recorded to the node's local storage. Nothing is transmitted during operation. |
| Radio physically disabled | The radio is disabled by a physical mechanism (module removed, keyed plug, or hardware switch with visible state) — not by software setting. The node records and displays a confirmation status (`RADIO DISABLED` on the status LED pattern and in diagnostics), and the disable state is logged in the session manifest with actor and timestamp. |
| Approved sensors only | Only sensors on the approved list for the applicable sanctioning body may be connected. The bike profile enforces the list; connecting an unapproved channel flags the session as non-compliant for that body. |
| No live pit telemetry | None, unless the specific sanctioning body has explicitly authorized it in writing; that authorization is recorded in the approval tracker before the mode permits it. |
| Post-session download | Data leaves the node only after the session, via dock or service cable (`docs/cnc/pit-dock-brief.md`). |
| Inspectable hardware state | Radio-disable state is visible externally; enclosure seals and the absence of any control output are inspectable. The team can demonstrate the passive architecture to an official on request. |

## 3. Per-sanctioning-body approval tracking

Rules differ by series and change by season. MX LAB tracks approval per body, per series, per season — never globally.

```ts
interface SanctioningApprovalRecord {
  body: string;                  // e.g. national or regional sanctioning organization
  series: string;
  season: string;
  status: "NotSubmitted" | "Inquiry" | "Submitted" | "Approved" | "Denied" | "ConditionsApply";
  approvedSensors: string[];     // channel names permitted by this body
  liveTelemetryAuthorized: boolean;   // false unless explicit written authorization
  conditions?: string;           // verbatim conditions from the body
  evidence: EvidenceRef[];       // correspondence, rulebook citations
  reviewedBy: string;            // named human
  reviewedAt: string;
}
```

- A bike profile entering a session in competition mode must reference a current `SanctioningApprovalRecord` for that series/season; without one, the UI marks the configuration **NOT ESTABLISHED AS LEGAL** and records the gap.
- Approval records are evidence-backed and audited like all other approvals; they are never satisfied by AI inference (see `docs/safety/safety-boundary.md`).
- Rulebook questions per series are tracked in `docs/testing/known-unknowns.md` with "how to verify: sanctioning-body inquiry."

## 4. Pre-race checklist (per event)

- [ ] Sanctioning approval record current for this body/series/season
- [ ] Radio physically disabled; confirmation status verified and logged
- [ ] Connected sensors match the approved list for this body
- [ ] Enclosure seals intact; hardware state inspectable
- [ ] Node battery and storage health pass dock check
- [ ] Session manifest tagged `competitionMode: true` with the approval record reference

COMPETITION USE REQUIRES APPROVAL FROM THE APPLICABLE SANCTIONING BODY. SOFTWARE CONFIGURATION DOES NOT ESTABLISH LEGALITY.

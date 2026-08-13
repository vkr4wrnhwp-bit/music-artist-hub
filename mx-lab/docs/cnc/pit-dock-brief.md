# MX LAB — Pit Docking Station Design Brief

Purpose: Design brief for the pit dock: the between-session touchpoint that identifies a node, downloads its sessions, charges it, and health-checks it with minimal handling time.

Status: Phase 2 target — design brief, pending physical verification. No hardware exists.

---

## 1. Boundary

The dock interacts with the **MX Node only — never with the motorcycle**. The MX Node itself is strictly passive: it must never control fueling, ignition, throttle, map slots, or any engine behavior, and its failure must not affect the motorcycle. The dock inherits and cannot widen that boundary: docking a node grants no path to any bike system, and a dock fault can at worst damage a node or lose a download, never affect a bike.

## 2. Functional requirements

| Function | Specification |
|---|---|
| Node identification | On docking, the dock reads the node identity (serial, firmware label) via `identify()` (`docs/hardware/adapter-spec.md`) and resolves it to the inventoried node record. Unknown nodes are flagged, not silently adopted. |
| Auto-open bike profile | The node's inventory record binds it to a specific bike (model + model year + ECUDefinition). Docking auto-opens that bike's profile in MX LAB. A node bound to no bike, or to a bike with a stale binding, prompts for human confirmation — never guesses. |
| Session download | Chunked, resumable download of all completed sessions; checksums verified per chunk; sessions marked transferred only after verification. Interrupted downloads resume, never duplicate. |
| Charging | Charges the node battery; charge state and battery-health trend reported to the app. Charging circuit fused and current-limited. |
| Firmware check | Reads node firmware label and compares against the team-approved version list. The dock reports mismatches; firmware updates are a deliberate human action with release notes, never automatic on dock. |
| Sensor-health check | Runs node diagnostics (`getDiagnostics()`): storage health/wear, battery health, GPS receiver status, RTC drift, per-channel last-known quality. Results are recorded against the bike profile and surfaced as readiness-gate evidence. |
| Radio-disable status | Reports the node's physical radio-disable state (relevant to competition mode, `docs/hardware/competition-mode.md`). |

## 3. Connector

- **Protected blind-mate connector — candidate approach**: node drops into a keyed nest; alignment features engage before contacts; contacts recessed and sealed against pit dust and moisture; rated for high mating-cycle count as a service item.
- Candidate families: ruggedized blind-mate/pogo-style docking contacts, or a sealed automotive family (Deutsch DTM/ASX as candidates) with a guided receptacle. Final selection after node connector selection; contact ratings sized to charge current with margin.
- Wrong-orientation insertion must be mechanically impossible (keying), and a mis-docked node must result in no connection rather than a partial one.

## 4. Fast turnaround workflow (target)

Between motos, the entire node touchpoint should be one action: **drop node in dock**.

1. Drop node in nest → identification + bike profile opens automatically.
2. Download starts immediately; charging starts simultaneously.
3. Diagnostics run during download; results appear on the bike profile.
4. Dock signals a clear state: DOWNLOADING → VERIFYING → READY (or ATTENTION with reason).
5. Node lifted out at READY; readiness gates for the next session update from the recorded health check.

Targets (to validate against real hardware): download of a full session day and a meaningful recharge within a typical between-moto window. No workflow step may require menu navigation for the routine case.

## 5. Physical design notes

- Bench/pit-cart mountable; stable under cable tug; mud-tolerant nest geometry (draining, cleanable).
- Dock powered from pit power (mains or 12 V pit battery — candidates); input protection and fusing sized at design time.
- Status indication visible across a pit space: large-area indicator or light bar (states above).
- All dimensions TBD pending node enclosure release (`docs/cnc/enclosure-brief.md`); the nest is a slave geometry to the enclosure revision and carries the enclosure revision compatibility in its own revision block.

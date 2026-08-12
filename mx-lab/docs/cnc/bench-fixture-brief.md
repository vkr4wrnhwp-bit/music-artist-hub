# MX LAB — Bench Development Fixture Design Brief

Purpose: Design brief for the bench fixture that hosts a Vortex ECU and harness for safe, engine-off characterization and verification work.

Status: Phase 2 prerequisite — design brief, pending physical verification. The fixture is where "requires physical verification" items get verified before anything touches a bike.

---

## 1. Boundary and role

All MX LAB hardware is strictly passive: the MX Node must never control fueling, ignition, throttle, map slots, or any engine behavior, and its failure must not affect the motorcycle. The bench fixture exists to keep it that way: every claim about Vortex data outputs, tap passivity, and fault behavior is proven here, on the bench, with no engine and no bike, before any on-bike installation. The fixture itself never connects to a motorcycle.

What runs on the fixture: a Vortex ECU (inventoried unit, exact model/firmware recorded — capabilities never assumed, see `docs/vortex/integration-boundary.md`) with its harness or a representative harness section. What is verified here: connector identification, data-output existence and characteristics, MX Node tap passivity, fault-injection results, and — only if Phase 4 gates are ever pursued — the bench validation protocol of `docs/vortex/future-direct-integration-plan.md`.

## 2. Power

| Requirement | Specification |
|---|---|
| Supply | Current-limited bench supply; limit set to the minimum that operates the ECU (value TBD — establish from Vortex documentation request or cautious bench measurement) |
| Fusing | Inline fuse in addition to supply limiting; sized below harness wire ratings |
| Reverse-polarity protection | At the fixture power input |
| Emergency disconnect | Prominently placed, single-action physical disconnect (mushroom switch or equivalent) cutting all fixture power; reachable without leaning over the ECU |
| Metering | Continuous current display; unexpected draw is a stop condition |

Powering an ECU outside the bike involves unknowns (required loads, sensor presence expectations) — treat initial power-up as an experiment: minimum viable connections, current limit low, one variable at a time, log everything.

## 3. Connector breakouts and signal access

- Breakout panel between ECU and harness: every conductor accessible at labeled, protected test points. Test points shrouded/recessed so a slipped probe cannot short adjacent pins.
- Series protection (resistive or buffered probes) on any observation connection, so instrumentation faults cannot drive ECU pins.
- Pinouts are **not assumed**: the breakout is built pin-by-pin from physical inspection and, where obtainable, Vortex documentation. Every label carries its verification status (Unverified / Physically Inspected / Documentation Verified per the ladder in `docs/vortex/integration-boundary.md`).
- No connector part numbers are asserted in advance; mating connectors are identified from the physical units on hand and recorded in inventory. Do not invent or guess part numbers for Vortex or Yamaha components.

## 4. Communication testing without a live engine

- Purpose: determine whether, and in what form, the ECU exposes data (CAN vs proprietary stream vs none — an open question per `docs/testing/known-unknowns.md`) and characterize it passively.
- Instrumentation: oscilloscope and passive bus analyzers first; **listen-only** configurations for any bus interface (transmit disabled in hardware) until documentation-verified procedures exist.
- MX Node input front-end validation: connect the node's protected input to the fixture, then fault-inject on the node side (short, reverse polarity, node power loss) and demonstrate no disturbance on the ECU-side signals — this is the evidence behind the no-back-feed requirement in `docs/hardware/mx-node-brief.md`.
- The ECU may behave differently without engine sensors present; bench observations are labeled Bench Verified at most, never Bike Verified.

## 5. Labeling and discipline

- Every wire, test point, fuse, and connector labeled; labels carry ID + verification status.
- Fixture logbook (in MX LAB, audited): date, operator, ECU identity (model/firmware labels as read), configuration, procedure, observations, anomalies. No undocumented experiments.
- One change at a time; photograph configuration before and after changes.
- A visible placard on the fixture states the standing rule: **this fixture never connects to a motorcycle, and no result from it authorizes an on-bike install without the per-model-year verification steps.**

## 6. Build checklist

- [ ] Current-limited supply + inline fusing + reverse-polarity protection installed
- [ ] Emergency disconnect fitted and tested
- [ ] Breakout panel built with shrouded test points, all labels placed
- [ ] Listen-only instrumentation configuration verified (no transmit path)
- [ ] Logbook procedure in place
- [ ] Spare inventoried ECU policy defined before any experimental work

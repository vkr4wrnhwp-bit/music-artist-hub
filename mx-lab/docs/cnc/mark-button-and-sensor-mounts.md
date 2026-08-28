# MX LAB — Rider MARK Button and Sensor Mount Briefs

Purpose: Design briefs for the rider MARK button housing and the sensor mounting hardware (wheel speed, clutch position, suspension travel, GPS antenna, IMU fixture).

Status: Phase 2 target — design briefs, pending physical verification. All dimensions TBD — measure on bike, per model year.

---

## 1. Boundary

Everything in this document is instrumentation for a strictly passive system. The MX Node must never control fueling, ignition, throttle, map slots, or any engine behavior, and its failure must not affect the motorcycle. Accordingly: the MARK button is an event-annotation input to the logger only — it commands nothing on the bike; and every sensor is additive observation, never inserted in series with, or loading, any OEM control or signal circuit. Failure or loss of any item here degrades data only.

## 2. Rider MARK button

A handlebar-area button the rider presses to timestamp an event ("bike did X here") into the session log.

| Requirement | Specification |
|---|---|
| Actuation | Oversized target, operable with a motocross glove without looking; positive tactile detent so the rider feels the press over bike vibration |
| Sealing | Sealed switch and housing; target IP67, pressure-wash survivable; replaceable seal |
| Function | Logger annotation only. Electrically connected to the MX Node MARK input exclusively; no connection to any bike circuit |
| Placement | Must not interfere with clutch, front brake, throttle, kill switch, or map/start buttons in reach or in a crash; position surveyed per rider and per model year cockpit |
| Wiring | Protected routing along the bar and OEM harness path; strain relief at both ends; breakaway-tolerant (a ripped cable opens the circuit cleanly — MARK channel goes Missing, nothing else) |
| Switch | Replaceable switch element as a service item; housing (6061-T6 or glass-filled polymer — candidates) outlives the switch |
| Confirmation indicator | Optional small LED acknowledging capture — fitted only if it can be placed without rider distraction or glare; omit if in doubt |
| Crash behavior | Housing may sacrifice itself; no sharp fracture edges toward the rider; bar-clamp mount must not rotate into control cables |

## 3. Sensor mount briefs

Common requirements for all sensor mounts:

- **Repeatable**: doweled, keyed, or shouldered location so re-installation reproduces position/orientation without re-calibration where feasible; where not feasible, the mount design documents the required recalibration step.
- **Removable and non-invasive**: existing hardpoints only; no drilling, no permanent modification; return-to-stock on removal.
- **Alignment-controlled**: alignment features machined in, not eyeballed; alignment spec recorded per mount revision.
- **Model-year-specific**: YZ250F and YZ450F are separate designs, and each model year of each gets its own surveyed revision (`docs/cnc/mount-yz250f.md`, `docs/cnc/mount-yz450f.md` pattern applies). Interchangeability is never assumed.
- All dimensions TBD — measure on bike, per model year.

| Mount | Brief |
|---|---|
| Front wheel speed | Sensor bracket at fork lug/caliper-region existing bolt bosses (candidate); trigger target on wheel (bolt-on tone feature — candidate, no rotor modification); air gap set by machined shoulder; survey wheel/spoke/rotor geometry per model year |
| Rear wheel speed | Bracket near caliper carrier or swingarm existing features (candidate); same air-gap and target discipline; survey chain/roost exposure — shielding likely required |
| Clutch position | Non-contact or lever-follower sensor observing lever or actuation travel (candidates); must add no perceptible lever load and no restriction to full travel; failure detaches cleanly from the control path; requires calibration record (see `docs/hardware/adapter-spec.md`, Uncalibrated state) |
| Fork travel | Linear potentiometer or equivalent (candidate) parallel to fork leg; clamp-on collars at existing geometry; full-travel clearance verified at bottom-out; zero/full-scale calibration procedure defined per install |
| Shock travel | Linkage-area or direct shock-parallel sensor (candidate — packaging is tight; survey per model year); full-travel and mud-pack clearance verified; calibration as above |
| GPS antenna | Highest practical sky-view location with short cable run (steering-stem area or rear fender area — candidates to survey); ground-plane requirement per chosen antenna; away from rider contact |
| IMU orientation fixture | The IMU mounts inside the MX Node; the node's bracket therefore doubles as the IMU orientation fixture: machined datum faces define pitch/roll/yaw alignment to the bike, recorded per model-year mount revision so orientation is identical across reinstalls; any bracket revision re-validates orientation |

## 4. Verification checklist (per mount, per model year)

- [ ] Survey complete: geometry, exposure, clearance at full travel/lock
- [ ] Interference check: rider ergonomics, controls, suspension, wheel/chain clearance
- [ ] Alignment/calibration procedure written and tested
- [ ] Removal test: return-to-stock confirmed, reinstall repeatability measured
- [ ] Crash-failure behavior reviewed (clean detach, no control entanglement)
- [ ] Revision block: part ID, bike model, model year, rev, survey ref, approver

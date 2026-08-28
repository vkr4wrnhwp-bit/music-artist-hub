# MX Node — Billet Enclosure Design Brief

Purpose: CNC design brief for the MX Node enclosure: sealed, serviceable, crash- and pressure-wash-survivable housing for a strictly passive logger.

Status: Phase 2 target — design brief, pending physical verification. All dimensions TBD pending mount survey per bike model and model year.

---

## 1. Boundary

The enclosed device (MX Node) is strictly passive: it must never control fueling, ignition, throttle, map slots, or any engine behavior, and its failure — including total enclosure failure, water ingress, or crash destruction — must not affect the motorcycle. The enclosure has no feature that could interact with bike controls or systems.

## 2. Material and construction

| Item | Specification | Class |
|---|---|---|
| Body material | 6061-T6 aluminum, machined billet | Candidate |
| Surface finish | Hard anodize (Type III) target for abrasion (roost, boot contact); color TBD | Target |
| Lid | Separate machined lid, fastened (captive stainless fasteners target), fully serviceable with hand tools | Target |
| Sealing | O-ring in machined groove; groove per standard o-ring gland design practice (proper squeeze/fill for the chosen cross-section); seals are stocked, replaceable service items | Practice — safe general guidance |
| Ingress target | IP67 target; must additionally survive direct pressure-washing (motocross wash-bay reality exceeds static immersion assumptions) | Target |
| Thermal | Survey heat exposure at candidate mount locations per model year (exhaust proximity, engine radiation); internal temperature rating drives location eligibility, not vice versa | TBD — measure on bike, per model year |
| Media resistance | Seals and finish resistant to fuel splash, chain lube, mud acids, wash chemicals | Requirement |

## 3. Functional requirements

- **Status-light visibility**: single sealed light pipe carrying the status LED to the exterior; light pipe sealed to the same ingress target as the body; visible with the node mounted (viewing angle confirmed during mount survey).
- **Protected connectors**: all connectors recessed below surrounding body surfaces, strain-relieved, and oriented to shed mud and water; sealed connector families such as Deutsch DTM/ASX are candidates. Mating faces protected from direct roost line where possible (mount survey input).
- **Radio-disable access**: the physical radio-disable mechanism (see `docs/hardware/mx-node-brief.md`) must be operable and its state visible without opening the sealed lid, while preserving the ingress target.
- **Vibration-isolated internal mounting**: PCB and battery mounted on elastomer isolators inside the enclosure; no component relies on potting for retention (serviceability requirement). Isolator durometer TBD after vibration survey.
- **No sharp edges**: all external edges and corners radiused/chamfered; rider-contact and rope/tie-down snag review required. Nothing on the enclosure may present a laceration hazard in a crash.
- **Weight target**: minimize; target under a few hundred grams for the housing — final target TBD once internal component volume is fixed. Pocket internal ribs; do not chase weight at the cost of sealing or crash survival.
- **Drainage/standoff**: mounting face design must not trap mud/water against the bike (standoffs or drain relief).

## 4. Mounting

- Mounts to **existing bike hardpoints only — no frame drilling, no permanent modification** of any YZ250F/YZ450F component. Removal restores the bike to stock.
- The enclosure provides a standardized mounting boss pattern; model-year-specific brackets adapt it to each bike (see `docs/cnc/mount-yz250f.md` and `docs/cnc/mount-yz450f.md`). YZ250F and YZ450F mounts are separate designs; never assume interchangeability across model or model year.
- All enclosure-to-bracket interfaces use secondary retention (safety-wire provision or thread-locked fasteners with witness marks).

## 5. Dimensions

All external and internal dimensions: **TBD — measure on bike, per model year.** No dimension in this brief may be released to CNC until the mount survey for the target model year is complete and internal component selection is frozen. No unvalidated production G-code: toolpaths are generated only from a released, revision-controlled model, and first articles are inspected before fitment.

## 6. Verification before release

- [ ] Mount survey complete for target model + model year (locations, envelope, heat map)
- [ ] Internal component stack frozen (drives cavity size)
- [ ] Seal design reviewed against chosen o-ring cross-section per standard gland practice
- [ ] Ingress test plan defined (IP67 target + pressure-wash test)
- [ ] Vibration/shock test plan defined
- [ ] Crash-sled or drop test plan defined
- [ ] Revision block present on drawing (part rev, model year applicability, date, approver)

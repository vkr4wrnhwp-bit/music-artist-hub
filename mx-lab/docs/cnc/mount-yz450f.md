# MX Node Mount — Yamaha YZ450F (Model-Year-Specific)

Purpose: Mounting design brief for the MX Node on the Yamaha YZ450F. This document covers the YZ450F only.

Status: Phase 2 target — design brief, pending physical verification. All dimensions TBD — measure on bike, per model year. No mount exists.

---

## 1. Boundary

The mounted device (MX Node) is strictly passive: it must never control fueling, ignition, throttle, map slots, or any engine behavior, and its failure — including mount failure — must not affect the motorcycle. The mount must not compromise any bike system: no frame drilling, no permanent modification, attachment to existing hardpoints only, full return-to-stock on removal.

**YZ450F and YZ250F mounts are separate designs.** Nothing in this brief applies to the YZ250F (`docs/cnc/mount-yz250f.md`), and no YZ250F survey data may be reused here. Within the YZ450F, each model year gets its own surveyed, revision-controlled design — the YZ450F's packaging (including its intake and tank architecture) has changed significantly across generations, so cross-year assumptions are prohibited; every location claim below is a survey question, not a fact.

## 2. Candidate locations — to be surveyed per model year

| Candidate | Rationale | Survey questions |
|---|---|---|
| Airbox area | Potentially protected volume near ECU region | Actual airbox position and free volume for this model year? Flow impact? Filter-service access? TBD — measure on bike, per model year |
| Under seat | Roost-protected, accessible | Seat-base clearance under rider load? Local temperatures? TBD — measure on bike, per model year |
| Steering-stem area | Short GPS antenna run, rigid structure | Full-lock clearance, ergonomics, vibration? TBD — measure on bike, per model year |

Survey each candidate for: hardpoints, envelope, temperature under sustained load, mud/water exposure, vibration, cable reach. Note that the 450's thermal environment must be surveyed independently — do not assume it matches the 250F at equivalent locations.

## 3. Heat and mud exposure mapping

Per model year, before location selection:

- Temperature: instrumented ride, peak and sustained, at each candidate; exhaust and header routing for this model year noted. TBD — measure on bike, per model year.
- Mud/water: post-ride and post-wash inspection; roost lines; pressure-wash spray paths.
- Fuel/chemical: tank vent/overflow routing, chain-lube fling.

## 4. Cable routing

- Follow existing OEM harness paths; removable ties to existing anchors only.
- Surveyed clearance at full suspension travel and full steering lock; no unprotected routing near hot surfaces.
- Service loops, strain relief at every entry, abrasion sleeving at contact-prone spans.
- Routing documented with photos in the revision record, per model year.

## 5. Service access

- Node removable within a pit-compatible time target.
- No standard maintenance task (air filter, seat, shock, plug access) may get harder; verify during fit check.

## 6. Retention method candidates

| Candidate | Notes |
|---|---|
| Machined bracket to existing bolt bosses | Preferred; 6061-T6 candidate; correct-length replacement fasteners at OEM locations |
| Elastomer-isolated cradle + machined clamp | Mount-level vibration isolation |
| Strap-plus-keyed-seat interfaces | Secondary retention only |

Primary fasteners thread-locked or safety-wired with witness marks. Crash behavior requirement: retain the node or fail benignly.

## 7. Interference checks (required per model year)

- [ ] Rider ergonomics: seated/standing/gripping, boot and knee sweep
- [ ] Suspension travel: full stroke front and rear with node and cables fitted
- [ ] Steering: full lock both directions, cables included
- [ ] Airbox flow: no intake restriction; filter service unimpeded
- [ ] Seat/tank removal unaffected
- [ ] Heat clearance verified against this model year's exposure map

## 8. Part-revision tracking

| Field | Example |
|---|---|
| Part ID | MXN-MNT-450F-<year>-<seq> |
| Bike model | YZ450F |
| Model year applicability | Single model year unless fit re-verified and recorded per additional year |
| Revision | Rev letter + date |
| Survey record ref | Photos, measurements, exposure map |
| Fit-check record | Interference checklist results, checker identity |
| Approver | Named human |

A new model year always opens a new survey and a new part revision. Reusing a YZ250F design, or a prior-year YZ450F design without recorded re-verification, is prohibited.

# MX Node Mount — Yamaha YZ250F (Model-Year-Specific)

Purpose: Mounting design brief for the MX Node on the Yamaha YZ250F. This document covers the YZ250F only.

Status: Phase 2 target — design brief, pending physical verification. All dimensions TBD — measure on bike, per model year. No mount exists.

---

## 1. Boundary

The mounted device (MX Node) is strictly passive: it must never control fueling, ignition, throttle, map slots, or any engine behavior, and its failure — including mount failure — must not affect the motorcycle. The mount itself must not compromise any bike system: no frame drilling, no permanent modification, attachment to existing hardpoints only, full return-to-stock on removal.

**YZ250F and YZ450F mounts are separate designs.** Nothing in this brief applies to the YZ450F (`docs/cnc/mount-yz450f.md`). Within the YZ250F, each model year gets its own surveyed, revision-controlled design; airbox, subframe, and seat architecture change between years and interchangeability is never assumed.

## 2. Candidate locations — to be surveyed per model year

| Candidate | Rationale | Survey questions |
|---|---|---|
| Airbox area | Protected volume, moderate temperature, often near ECU region | Available volume without restricting airbox flow? Filter-service access preserved? TBD — measure on bike, per model year |
| Under seat | Protected from roost, accessible at seat removal | Clearance to seat base under rider load? Heat from under-seat components? TBD — measure on bike, per model year |
| Steering-stem area | Short GPS antenna run, rigid structure | Bar/trees full-lock clearance? Rider ergonomics? Vibration environment? TBD — measure on bike, per model year |

Survey each candidate for: mounting hardpoints, envelope, temperature (probe under sustained load), mud/water exposure, vibration, cable reach.

## 3. Heat and mud exposure mapping

Per model year, produce an exposure map before location selection:

- Temperature: instrumented ride at each candidate location (peak and sustained); exhaust routing and engine radiation noted. TBD — measure on bike, per model year.
- Mud/water: post-ride and post-wash inspection at each candidate; direct roost lines identified; pressure-wash spray paths noted.
- Fuel/chemical: proximity to fuel tank vents, overflow routing, chain-lube fling.

## 4. Cable routing

- Follow existing OEM harness paths; secure with removable ties to existing anchors only.
- No routing across suspension-travel paths, steering sweep, or hot surfaces without surveyed clearance at full travel/full lock.
- Service loops at connectors; strain relief at every entry; abrasion sleeving where routed near contact points.
- Routing plan is model-year-specific and documented with photos in the revision record.

## 5. Service access

- Node removable for dock download (if not using on-bike service connector) within a pit-stop-compatible time target.
- No standard maintenance task (air filter, seat removal, shock access, plug access) may get harder; verify each during fit check.

## 6. Retention method candidates

| Candidate | Notes |
|---|---|
| Machined bracket to existing bolt bosses | Preferred; 6061-T6 candidate; reuse OEM fastener locations with correct-length replacements |
| Elastomer-isolated cradle + machined clamp | Adds vibration isolation at the mount level |
| Strap-plus-keyed-seat interfaces | Secondary retention only, never primary |

All primary fasteners thread-locked or safety-wired with witness marks. Mount must retain the node through crash loads or fail without creating a hazard (no sharp fracture faces into rider space).

## 7. Interference checks (required per model year)

- [ ] Rider ergonomics: no contact in seated/standing/gripping positions; boot and knee sweep checked
- [ ] Suspension travel: full stroke front and rear with node and cables fitted (zip-tie travel indicators)
- [ ] Steering: full lock both directions, cables included
- [ ] Airbox flow: no intake-tract restriction; filter service unimpeded
- [ ] Seat/tank removal unaffected
- [ ] Heat clearance verified against exposure map

## 8. Part-revision tracking

Every released mount design carries:

| Field | Example |
|---|---|
| Part ID | MXN-MNT-250F-<year>-<seq> |
| Bike model | YZ250F |
| Model year applicability | Single model year unless fit is re-verified and recorded per additional year |
| Revision | Rev letter + date |
| Survey record ref | Photos, measurements, exposure map |
| Fit-check record | Interference checklist results, checker identity |
| Approver | Named human |

A new model year always opens a new survey and a new part revision. Carrying a mount across model years without a recorded fit re-verification is prohibited.

# 3D lathe view + playback + stock states — BUILT (DEVELOPMENT)

`src/lib/manufacturing/turn/sim.ts` (pure engine) +
`src/components/turn/lathe-3d.tsx` (R3F view), embedded in the turning
workspace under "3D — stock removal playback".

## The model

A turned part is axisymmetric, so the whole stock state is one curve:
radius as a function of Z (400 cells). The sim replays the deterministic
turn toolpaths against it — each cut clamps the envelope down over its
swept span, partially-elapsed moves carve only the swept portion, and
the radius never grows. Timing uses the same per-rev arithmetic as the
cycle estimates; rapids at a stated 800 in/min assumption.

## The view

Live-revolved envelope (nz × 64 mesh rewritten in place), raw bar vs
machined surface in different colours, translucent chuck context, tool
point riding the clock (grey rapid / blue cut). Transport: play/pause,
scrub, 1–30× speed, and STOCK STATES — one button per operation
boundary jumping the clock to "After op N". Light work-window ground,
same philosophy as the mill viewport.

## Honest limits, printed on screen

- Kinematic replay only — NOT a collision or gouge check.
- The tool is its programmed point, not real insert geometry.
- Internal (centerline/ID) operations advance the clock but do not
  carve the OD envelope — internal stock state is not modelled, stated
  in the notes rather than faked.
- Tapered sweeps clamp to their minimum radius across the swept span —
  a development-resolution approximation.

Pinned by 4 tests (raw→final envelope, monotonic shrink at every op
boundary, mid-cut partial sweep, internal ops leave the OD untouched).

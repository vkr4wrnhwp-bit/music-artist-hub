# Finish-pass protection — BUILT (rule-based, absolute in V1)

`src/lib/nc/protection.ts` builds ProtectedRegions deterministically
from the part's own features — no AI, no comment parsing. A feature
earns protection when it is marked critical, its tolerance band is
≤0.001", its finish is ≤32 Ra, its functional role is a finish surface
(bearing/seal/thread/dowel/locating), or it is a tapped hole. The
region is the feature footprint + 0.15" tool allowance over the
feature's own Z span.

`load.ts` tests each cutting segment against the regions using
SEGMENT-to-center distance (a pass crossing straight through a bore is
protected — endpoints alone are not the test; that hole was found live
and pinned by regression). Protected segments receive NO automatic
proposal in either direction; hits are reported as FINISH PASSES
PROTECTED with the reason. Protection is absolute in V1 — the audited
human override is not built, and the UI says so.

Derivation is shared by the analyze and optimize routes, so an
accepted proposal can never sneak into a protected region at apply
time.

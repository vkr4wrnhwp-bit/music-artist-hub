# Turning readiness

`turn/readiness.ts`: 12–14 gates (geometry, material, machine,
workholding, grip, stickout, boring-bar reach*, part-off*, tooling,
RPM/CSS, inspection capability, post, human approval; * only when the
plan contains those ops). Aggregation is worst-case by construction —
if arithmetic appears in it, stop. UNKNOWN analyses gate as FAIL:
missing evidence blocks, it does not average away. CSS with an
unrecorded chuck RPM limit is REVIEW by rule.

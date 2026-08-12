# Turning architecture

Modular per-process layout: `src/lib/manufacturing/{process.ts, turn/*}`.
Shared systems (materials, provenance, audit, readiness philosophy,
nominal reasoning, shop knowledge) are reused, not duplicated — the
nominal engine and instrument library serve both processes. Turning
never stuffs lathe cases into mill classes: LatheMachine,
LatheWorkholding, TurningTool and RotationalPart are their own tables;
the mill's Machine/Tool/Setup are untouched. X0 = centerline, Z0 =
machining datum face, diameters are diameters. JSON-shaped profile and
plan (domain layer owns the vocabulary — the intentJson pattern).

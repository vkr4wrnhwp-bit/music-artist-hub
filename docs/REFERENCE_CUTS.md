# Reference cuts — BUILT

ReferenceCut table + the "Mark reference cut" form on /machines. A
machinist records a cutting region they have personally proven:
machine, tool, material, operation, DOC, WOC, feed, RPM, coolant,
result (RUNS_CLEAN / ACCEPTABLE / MARGINAL), notes, user, timestamp —
audited HUMAN on creation.

Scope discipline: a reference cut is SHOP_KNOWLEDGE — scoped to the
context it was proven in, never generalized beyond comparable contexts
without qualification, and never a gate input. Future optimizer use
(normalizing relative load against a proven baseline) compares only
within compatible machine/tool/material context.

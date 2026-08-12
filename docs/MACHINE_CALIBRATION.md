# Machine calibration — BUILT (display-only)

MachineCalibrationRecord table + per-machine calibration panels on
/machines. The user records actual machine cycles against the CANVAS
estimate (program label, estimated min, actual min); each record is an
audited HUMAN act.

Methodology, stated on screen: calibration is claimed only from 5+
recorded cycles, and the factor is the MEDIAN of actual/estimated
ratios — one interrupted cycle (door open, chip nest, lunch) cannot
poison the model, pinned by test. Below the threshold the panel says
INSUFFICIENT CALIBRATION DATA and that one sample is an anecdote.

The factor is DISPLAY-ONLY in this phase: "shown beside estimates,
never silently applied." Applying it automatically comes only when the
sample base and spread justify it. Calibration is per machine —
SHOP_KNOWLEDGE, never another machine's truth.

# CANVAS Training Shop

Training projects are real parts flagged `Part.training = true`,
isolated from production by one hard rule: the NC export mint refuses
them server-side (`mintExport`), and the NC page says so. Everything
else — planning, workholding, toolpaths, simulation, gates — works
exactly as production, because practising on a fake would teach the
wrong lessons.

Seeded project: **Training — Basic Plate** (TRAIN-001): face, pocket,
two holes, chamfer; arrives with geometry and deliberately no stock,
no setups, no plan. Skills: stock, setup, zero, workholding, toolpaths,
simulate, gates. The BEARING SUPPORT skills are covered by the demo
part; a reverse-engineering training project is future work alongside
its guided flow. No points, no badges.

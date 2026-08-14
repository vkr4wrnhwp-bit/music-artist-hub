# Responsive workspace — measured matrix (2026-08-11)

Method: real browser (chromium), fresh storage per size, demo part
workspace, raw canvas pixels ÷ raw screen pixels. "Attention share" is
higher than the raw number since the header, banner and timeline header
are part of working the part.

| Size | Canvas | % of screen | hScroll | Readiness visible | Next action visible |
|---|---|---|---|---|---|
| 1366×768 | 1234×512 | 60% | no | yes | yes |
| 1440×900 | 1122×386 | 33% | no | yes | yes |
| 1920×1080 | 1602×596 | 46% | no | yes | yes |
| 2560×1440 | 2242×956 | 58% | no | yes | yes |
| 1024×768 | 892×471 | 53% | no | yes | yes |
| 1366×768 FOCUS | — | 60% | no | yes (chip) | yes (chip) |

Defaults: below 1440px width the context drawer and timeline start
collapsed; the feature panel starts collapsed at every width until a
feature is selected. Explicit user choices always win over defaults.

No horizontal scrollbar at any tested size. The canvas resizes through
R3F's own resize handling — panels collapse without remounting the
scene, and selection/camera survive layout changes (verified).

Honest gaps: 1440×900 keeps the drawer and timeline open by default
(it is above the collapse threshold) and reads 33% raw; collapsing
either raises it to the 1366 numbers. Mobile still uses the two-pane
Model/Panel switcher rather than a bottom-sheet — the bottom-sheet
pass remains open work.

## Consolidation pass — measured matrix (2026-08-14)

Production build, Bearing Support workspace, default states per size:

| Size | Header | Canvas share | Drawer | H-scroll | Page scroll | Focus share |
|---|---|---|---|---|---|---|
| 1366×768 | 86px (meta wraps) | 62% | collapsed | 0 | 0 | 66% |
| 1440×900 | 86px | 37% (drawer+panel open) | open | 0 | 0 | 70% |
| 1920×1080 | 64px | 49% | open | 0 | 0 | 77% |
| 1024×768 | 64px | 58% | collapsed | 0 | 0 | — |

Readiness status, blocker count and next action remain visible in
every state, including Focus (compact critical chip with EXIT FOCUS).

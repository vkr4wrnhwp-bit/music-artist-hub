# Guided workflow — status

Implemented: engine + sessions with visited-history, BACK ONE STEP,
OFF/ASSIST/TEACH persisted server-side, first-run experience profile,
Guide Card (floating, collapsible to a tab, 344px, G/Shift+G/Alt+←/Esc
shortcuts, never fires while typing), coach marks on stable
`data-guide-target` ids (define-stock, approve-approach, context-*),
MAKE_A_PART flow with branching and blocker teaching, Next Required
Action integration (ASSIST renders the real queue head; TEACH surfaces
gates as blockers), Training Shop with server-side export refusal,
8 engine safety tests.

Coach marks auto-reveal: when a mark's target is missing after layout
settles (~500ms), it broadcasts canvas:reveal-guide-target once; the
collapse owners — context drawer, feature panel, focus mode — listen
and expand. A highlight on a hidden control teaches nothing, and
revealing UI is non-destructive. Remaining partial: a target behind an
inactive tab inside the panel is revealed to the panel level only —
tab switching on reveal is not wired. Geometry targeting uses
routes + the existing selection system rather than per-face 3D
highlighting. ASSIST recommendations are the real nextActions() queue,
not yet per-parameter structured proposals.

TURN_A_SHAFT (added once turning landed): the same backbone in the
lathe's voice — profile, bar stock, lathe, hold-with-evidence (the
clamp-force step surfaces the grip gate as its blocker), turning
toolpaths, 3D playback as a teaching step, instrument capability,
worst-gate clearing, delivery through the turning export mint. Mounted
on the turning workspace; GuideCard now takes a flowId and persists
sessions per flow without clobbering other flows' progress.

Not implemented, not faked: DRAW_FROM_SCRATCH (no sketching exists),
the mill guided reverse-engineering flow (the turning bench flow
guides itself), (and see below for analytics).

Guide analytics: append-only GuideEvent rows (START / ADVANCE / BACK /
SKIP / RESET / MODE_CHANGE / FLOW_COMPLETE), written fire-and-forget
from the card through /api/guide/events — user and organisation from
the session, payload capped, actions whitelisted. The knowledge page
shows GUIDE FRICTION: the steps people back out of or skip most, with
flow start/completion counts. Telemetry about the guide, never about
parts — it feeds no gate and carries no engineering data.

The card is a true bottom sheet below lg: full width, docked to the
bottom edge, max 70dvh with internal scroll, a grab bar that collapses
it back to the Guide tab. At lg+ it stays the 344px floating card,
grab bar hidden.

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

Partial: coach marks target visible controls; a target inside a
collapsed panel is not auto-expanded yet. Geometry targeting uses
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
guides itself), guide analytics events, tablet/mobile sheets for the
card (it is responsive but not a bottom sheet).

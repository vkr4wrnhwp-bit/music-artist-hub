# Workspace layout — the part is the primary interface (2026-08-11)

## Zones

- 72px icon rail (global sections)
- 210px context drawer → collapses to a 24px edge tab; part routes
  grouped by mode (PART / HOLD / CUT / VERIFY / DELIVER)
- command bar (job identity, gate-based status)
- compact blocking banner: "N BLOCKING — ACTION REQUIRED · <worst> ·
  FIX →", expandable to per-blocker pills, each routing to its evidence
  screen; nothing in it clears a gate in place
- centre viewport (the part) with floating VIEW and FOCUS buttons —
  the view-control stack costs width only while open
- right feature panel: docked away by default, opens when a feature is
  selected, collapsible to a labelled rail
- bottom operation timeline: collapsible; minimized state keeps a
  one-line summary of the selected operation (a selection, never an
  execution state)

## Focus workspace (F)

Collapses the context drawer, feature panel, control stack, drawers and
the timeline body in one keystroke, and keeps a compact critical-status
chip over the viewport: blocking count (click-through to evidence) and
the next required action. Focus simplifies the interface; it never
conceals risk. Measured at 1366×768: the canvas goes from ~18% of raw
screen pixels (everything open) to ~60%.

## Shortcuts

F focus · V view environment · 1–5 context (PART/HOLD/CUT/VERIFY/$) ·
Esc clear selection. Never while typing in an input.

## Persistence

localStorage per browser: context drawer, feature panel, timeline,
view-control stack. View environment and saved presets persist
per user on the server (ViewPreference). Focus is transient by design.


## Resizable panels (added)

The context drawer (180-340px, default 210) and the feature panel
(280-560px, default 356) resize by dragging their canvas-edge handle;
double-click resets. Widths persist per user in localStorage
(canvas.drawerWidth / canvas.panelWidth), rAF-throttled during drag,
clamped so neither panel can vanish or eat the work window. Mobile
layout untouched (handles are lg-only; widths ride a CSS variable).


## Density modes (added)

COMFORTABLE (default) and COMPACT, toggled on Settings, stored per
device (canvas.density) and applied as a root data attribute by a
layout-mounted applier. COMPACT overrides only the shared primitives'
density hooks (d-panel-header, d-panel-body, d-row, d-td) in
globals.css — panel chrome, data rows and table cells tighten; type
hierarchy, color and page structure are untouched. Measured: panel
header 36→24px, data row 31→27px.

## Consolidation pass (workspace-parity brief)

- Command bar is ONE row (min 64px): identity, chips, trail (fading
  scroll), metadata (xl+), status, user. The inferred page heading
  renders only when a page brings no trail — the duplicate-title
  stack is gone shell-wide.
- Shell height is 100dvh; nothing outside a page's own main scrolls.
- Keyboard: F focus · V view environment · 1–5 contexts · Esc close
  · G guide — all guarded against typing targets.
- RESET VIEW (default camera/orientation/scene via OrbitControls
  reset + Studio White) and RESET WORKSPACE (clears layout keys,
  restores approved defaults) live in the View environment drawer.
  Neither touches manufacturing data.
- Already in place from prior phases and verified again: two-layer
  left side (72px rail + collapsible/resizable context drawer,
  auto-collapsed under 1440px), routes grouped under
  PART/HOLD/CUT/VERIFY/DELIVER, floating VIEW menu, functional view
  environment with live background, panel persistence, focus mode
  with the critical-status chip.

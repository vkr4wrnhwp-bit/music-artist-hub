# Holeshot Tuner — EFI trim-map tool for MX bikes

A self-contained fuel-mapping tool for fuel-injected motocross bikes, in the
style of handheld tuners (Yamaha Power Tuner, GET, Vortex): you edit **offsets**
on top of the ECU's stock map, not absolute injector values.

**Completely standalone** — one HTML file, no build step, no dependencies, no
network access. It does not touch or depend on anything else in this
repository.

## Run it

Open `index.html` in any modern browser. That's it.

## What it does

- **Fuel trim map** — 10 RPM rows × 9 throttle-position columns, ±20% in 0.5%
  steps, with finer throttle resolution below 40% where response tuning
  actually happens.
- **Ignition offset map** — same grid, ±6° in 0.5° steps.
- **Heatmap coloring** — blue = richer / advance, red = leaner / retard,
  neutral at stock. Lean is red on purpose: lean runs hot.
- **Editing** — click, drag-select regions, shift/ctrl selection, keyboard
  navigation, `+`/`−` stepping, type-to-set, smooth, and bilinear interpolate
  across a selection. Full undo/redo.
- **Base setting presets** — crisp bottom-end, smooth & tractable, sand/loam,
  mud protection, supercross hard-pack.
- **Air-density calculator** — elevation, temperature, and humidity produce a
  relative-air-density figure (ISA pressure + Magnus vapor pressure) and a
  suggested global fuel offset you can apply in one click.
- **Saved setups** — named setups persist in the browser's localStorage;
  JSON export/import moves them between devices, CSV export for spreadsheets.

## Disclaimer

Reference tool for closed-course competition use. Trims are suggestions —
verify changes with an AFR gauge, plug readings, or a dyno. Lean mixtures
raise engine temperature; when in doubt, stay slightly rich.

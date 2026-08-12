# View Environment

The viewport's inspection lamp: how the scene is **drawn**, never what it
**shows**. Nothing here touches a gate, a measurement, or provenance, and
the copy holds to "improves visibility / contrast" — a view setting never
certifies anything.

Opened from the viewport control stack: **Scene → View env**.

## Presets

| Preset | Intent |
|---|---|
| Studio White | Default. Neutral ground, soft shadow. |
| Graphite | Mid grey; calms glare on polished surfaces. |
| Inspection Gray | Edge visibility on bright aluminum / stainless. |
| Blueprint Blue | Drawing-room ground for review sessions. |
| Warm Shop Floor | Warm tone for sodium-lit floors. |
| Dark Machine Bay | Dark ground for bright toolpaths and light materials. |
| High Contrast | Strong edges, heavy lines, large text. |
| Custom | Any colour edit moves the preset to Custom. |

Each preset sets: background, floor colour/visibility/reflectivity, grid
visibility/intensity, shadow strength, reflection strength, edge mode, and
(High Contrast) line weights and text size.

## Custom colours and the semantic lock

Background, floor, grid and the selected-feature accent are customisable.
The **semantic status colours are not**: blue = selected/measurement,
green = pass, orange = review, red = blocking, everywhere in the product.

A custom background is contrast-checked against all four
(`semanticConflicts()` in `src/lib/view-environment.ts`, 2.5:1 floor). A
conflicting choice shows a visible warning naming the colours it drowns —
it is never silently accepted and never auto-corrected behind the user's
back.

## View detail

Edges and datum lines: Off / Light / Medium / Strong. Measurement and
toolpath lines: Thin / Medium / Heavy. Feature ring: Normal / High
contrast. Annotation text: Compact / Standard / Large. These exist for
shop-floor lighting, tablets and older eyes — accessibility, stated as
such.

## Material-aware recommendation

`recommendPresetFor(material)` suggests a preset for dark plastics,
anodize, bright aluminum, stainless and castings. It is a suggestion with
an APPLY button — the view is never changed without the user acting.

## View modes

Programming / Inspection / Presentation / Shop Floor change visibility
emphasis (scene flags + environment nudges). Nothing is removed; every
toggle remains individually reachable.

## Persistence

Per-user server row (`ViewPreference`: userId unique, envJson +
savedPresetsJson) storing the `ViewEnvironment` shape from
`src/lib/view-environment.ts` verbatim as JSON — display tuning does not
require a migration. The server copy is the source of truth and follows
the user across devices; `localStorage` (`canvas.viewEnvironment.v1`,
saved presets under `canvas.viewEnvironment.saved.v1`) is a fast cache so
the viewport does not flash defaults while the fetch is in flight. Writes
go to both, debounced to the server, fire-and-forget: display preferences
are the one category of data where losing a write is acceptable. User and
organisation come from the session, never from the request
(`/api/view-preferences`).

## Export view

Screenshot (PNG of the WebGL canvas) is real. Annotated image, setup
sheet, inspection view and customer-safe view are listed as DEVELOPMENT
and do nothing yet — listed so the architecture is visible, labelled so
nobody mistakes them for capability.

## Consolidation pass status (2026-08-11)

All eight presets (Studio White, Graphite, Inspection Gray, Blueprint
Blue, Warm Shop Floor, Dark Machine Bay, High Contrast, Custom) apply
to the real rendered scene — background, floor, grid, reflection,
shadow, edge/datum/measurement/toolpath weights, annotation size —
via the EnvCtx the scene consumes. Custom colors are contrast-checked
against the locked semantic colors (semanticConflicts, 2.5:1 floor)
and warn visibly instead of silently drowning a blocking red. The
drawer opens from the floating VIEW button or the V key.

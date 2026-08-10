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

`localStorage` per browser (`canvas.viewEnvironment.v1`, saved presets
under `canvas.viewEnvironment.saved.v1`), and the drawer says so. When a
server-side ViewPreferences model exists it adopts the `ViewEnvironment`
shape in `src/lib/view-environment.ts` verbatim (plus userId /
organizationId).

## Export view

Screenshot (PNG of the WebGL canvas) is real. Annotated image, setup
sheet, inspection view and customer-safe view are listed as DEVELOPMENT
and do nothing yet — listed so the architecture is visible, labelled so
nobody mistakes them for capability.

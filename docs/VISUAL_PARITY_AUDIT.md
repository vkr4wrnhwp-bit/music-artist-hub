# VISUAL PARITY AUDIT — live build vs the approved reference

Brief §30 and §45. Measured from the running production build on the
Bearing Support workspace, default state, at each required resolution.
Pixel values are sampled from the captured PNGs, not estimated by eye.

## Measured matrix

| Size | Header | Canvas | Share | Drawer | Feature panel | View env | Runway | H-scroll | Page scroll | Readiness | Next action | Part visible |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1366×768 | 86px | 1234×528 | 62% | collapsed | collapsed | closed | minimized | 0 | 0 | yes | yes | yes |
| 1440×900 | 86px | 1308×660 | 67% | collapsed | collapsed | closed | minimized | 0 | 0 | yes | yes | yes |
| 1920×1080 | 64px | 1788×862 | 74% | collapsed | collapsed | closed | minimized | 0 | 0 | yes | yes | yes |
| 1024×768 | 64px | 892×509 | 58% | collapsed | collapsed | closed | minimized | 0 | 0 | yes | yes | yes |

Header is 64px at one row and wraps to 86px where metadata meets the
1366/1440 content box. Nav rail is 72px at every size.

Sampled viewport ground at 1366×768: `rgb(243,243,241)` — Studio White
as designed. (An earlier capture in this session read dark because
testing had written a Dark Machine Bay preference to the user's stored
view preferences; that was test residue, cleared before this audit.)

## What matches the reference

- Deep navy/black shell, graphite panels, restrained precision blue,
  locked semantic colours (green pass / amber review / red blocking).
- 72px collapsed icon rail with labels, visually distinct from the
  context drawer beside it.
- One compact command bar carrying identity, revision, material, stock,
  machine, program and the readiness verdict.
- PART / HOLD / CUT / VERIFY / $ mode tabs across the top of the object.
- Light work-window viewport with the part dominant and a view cube.
- Feature Detail structured as the reference structures it: identity and
  chips, geometry, metrology (instrument, capability, nominal /
  measured / deviation / limits, status), then actions.
- View Environment with all eight presets, custom colours, surface and
  visibility controls, and save-as-preset.
- Zero border radius, thin structural rules, no card soup.

## Differences, honestly

### Deliberate — will not be changed to match

1. **Operation status column.** The reference's operation table carries
   COMPLETE / SELECTED / PENDING. CANVAS has no execution state:
   `Operation` has no status column, `OperationState` has no write
   sites, and there is no machine connection. Rendering COMPLETE would
   be a fabricated capability (locked principle 5). Ours shows sequence,
   tool, cycle and whether a toolpath exists — all real.

2. **SEND TO MACHINE.** The reference's bottom bar has it. Nothing in
   CANVAS can send a program to a machine. A button that appears to do
   it is exactly the lie principle 5 forbids.

3. **Blocker banner.** The reference shows all four blockers as pills.
   Ours shows the highest-priority blocker with FIX and ALL 3 — which
   is what brief §9 asked for ("show only the highest-priority blocker
   by default", expandable). The reference image is the expanded state
   of the same control.

4. **The reference's own metrology numbers.** Its panel reads DEVIATION
   +0.0006 against TOLERANCE ±0.0100 with STATUS **FAIL**. +0.0006 is
   comfortably inside ±0.0100. Ours renders that layout but lets
   `assessConformance` decide the verdict, so the status agrees with the
   numbers beside it.

### Real gaps — candidates for future work

5. **Part rendering fidelity.** The reference is photoreal machined
   aluminum: brushed finish, specular breakup across the top face, soft
   studio gradient and a contact shadow. Ours is a clean matte solid
   over a perspective grid. This is the largest remaining visual gap.

   **Partly closed.** The metals now sit at real conductor values
   (aluminium 0.62 → 0.9) and the environment is bright enough to light
   them. Measured on the seeded plate by sampling the captured PNG:

   | | top face | top face centre | side wall |
   |---|---|---|---|
   | before | rgb(148,150,153) | rgb(169,172,174) | rgb(119,122,125) |
   | after | rgb(128,131,134) | rgb(152,156,159) | rgb(96,100,102) |

   Slightly darker, and with a real gradient across both surfaces where
   there was a near-flat fill before — it reads as a machined plate
   rather than a matte solid. Material differentiation was checked at
   the same time and is genuine: cast iron rgb(175,176,174) matte,
   brass rgb(124,107,71) gold, aluminium rgb(128,131,134) cool neutral.

   **The lever was `environmentIntensity`, and an earlier entry here got
   that wrong.** A first pass raised metalness alone and produced a top
   face clipped to rgb(254,254,254) over side walls crushed to
   rgb(0,0,0); adding four enclosing Lightformer panels changed nothing,
   even at `intensity={20}`, and this document briefly recorded that the
   `<Environment>` rig "is not reaching the material". That was wrong. A
   probe inside the scene showed `scene.environment` populated and ACES
   tone mapping active, and forcing `environmentIntensity` 0.5 → 3.0
   moved every sampled pixel. The environment was arriving; there was
   simply not enough of it to light a surface with no diffuse response.

   **Anisotropy now works, and the fix was upstream of the material.**
   Milled faces smear their highlight along the cutter marks, and
   MeshPhysicalMaterial's `anisotropy` draws that analytically — but it
   needs a tangent frame, and `mergeGeometries` in part-solid.ts
   concatenates position and normal only, dropping the ExtrudeGeometry
   UVs. With no UVs there is nothing for three's `computeTangents()` to
   derive from, so the shader ran on a degenerate frame: measured, the
   top face clipped to rgb(255,255,255) over side walls at rgb(0,0,0),
   at every anisotropy value tried.

   `computeMachiningTangents()` now builds the frame directly, by
   projecting one world direction onto each vertex's surface plane
   (with the standard fallback axis where the normal is parallel to it).
   Measured with anisotropy 0.3 restored: rgb(134,136,139) top face,
   rgb(156,159,162) centre, rgb(92,95,98) wall — in range, no clipping,
   with a directional sheen across the top face.

   What it claims is deliberately modest: ONE consistent direction, not
   a per-operation cut direction. The solid is merged slabs with no
   per-operation channel, so a tangent field pretending to follow each
   operation's real feed would be invented. Cast iron and plastic carry
   anisotropy 0 — an as-cast face has no cutter marks to smear.

6. **Ground treatment.** The reference has a gradient ground and no
   grid; ours draws a visible grid by default. The grid is already a
   toggle in View Environment — the question is the default.

7. **Header chrome.** The reference carries a notification bell with a
   count, an analytics icon, and a circular avatar with the operator's
   name and role. Ours has the datum mark and the operator's name as
   text. Notifications and an analytics surface do not exist yet.

8. **Persistent bottom action bar.** The reference keeps READINESS
   GATES + four gate chips + EXPORT NC visible along the bottom. Ours
   puts the gate strip at the top and NC OUTPUT in it. (EXPORT NC is
   reachable and gated; only its placement differs.)

9. **Next-action card.** The reference has a dedicated bottom-right card
   with the action, the instrument, VIEW INSTRUCTIONS and WHY THIS
   MATTERS. Ours states the next action in the context drawer and the
   Guide card, and the CANVAS Guide occupies that corner.

10. **Setup cards in the left column.** The reference lists SETUP 01 /
    SETUP 02 with SAFE / HIGH RISK beside the viewport. Ours has them
    on the setups page with the hold scene.

11. **Orientation controls.** The reference has a bottom-centre
    segmented orientation control and bottom-right viewport tool icons.
    Ours has the view cube plus orientation inside the VIEW menu.

12. **Instrument illustration.** The reference draws the micrometer in
    the metrology block. Ours names the instrument in text.

13. **ANALYTICS nav item.** Present in the reference rail; no such route
    exists here.

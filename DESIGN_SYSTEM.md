# Design System

Read out of the templates, not invented for this document. Tailwind is
loaded from the CDN with no build step, so these values live as arbitrary
classes and in per-page `<style>` blocks.

## Palette

Counted from the templates and stylesheets. Usage counts as of
2026-07-31: `#c9a24a` 792, `#e8c667` 481, `#d8b25a` 178, `#e5c878` 51,
`#141209` 88. The rack instrument tokens are lower-volume by design —
they appear once per unit rather than across the app.

### Street Banker — the platform
| Token | Use |
|---|---|
| `#c9a24a` | brass — primary accent, borders, CTA fills |
| `#e8c667` | lit brass — active values, meter readouts, highlights |
| `#d8b25a` | badge fill |
| `#e5c878` | press-kit gold — the outward-facing variant |
| `#1c1302` | text on brass |
| `#0a0a0a` / `#0d0d0f` / `#111113` | page, sidebar, surface |
| `#141209` | warm panel — anything money- or signal-related |

### The Rack — instrument surfaces
| Token | Use |
|---|---|
| `#e8c667` | lit value, arc, pointer |
| `#c9bd9c` | engraved legend on dark |
| `#8a7c5d` | secondary legend |
| `#4c4536` / `#2e2920` | chassis dark / silver-unit text |
| `#e07a3c` | cut — negative EQ gain, and the bass instrument band. Lives in `rackdsp.js`, not CSS |

Amber is warmth and brass is structure. **Red is reserved for genuine
failure** and appears nowhere decoratively.

### Royalty Sweep
Shares the platform palette rather than forking it. It is a module of
Street Banker, not a separate fintech product, and a second accent system
would say otherwise. Money and recovery surfaces use the warm panel
(`#141209`) with brass borders.

## Rules that came from being wrong

**No black boxes on black with dim grey text.** A standing correction.
Use ivory bands, gold accents, amber borders and near-white copy.

**Small type is engraving, not body copy.** The 8–10px sizes on the Rack
and the EQ are scale markings on an instrument — frequency labels, dB
ticks. They are correct at that size. A blanket "raise all small text"
sweep would cost the hardware look and fix nothing. Body copy, labels and
anything a decision depends on must not be that small.

**Disclosure travels with the number it describes.** The public press kit
carried a "Sample metrics" line in a section the artist could switch off
independently of the figures. A disclosure that can be hidden separately
from the thing it discloses is not a disclosure. Sample warnings now
render against the numbers themselves.

**Never two badges that contradict.** A green "Catalog verified" sat
directly above "Sample metrics shown". The verified badge now only
appears when the figures are genuinely from uploaded statements.

## Touch

Keyed on `(pointer: coarse)` where the control is physical, and on width
where the layout is. A touch laptop at 1400px needs the same targets a
phone does; a narrow desktop window does not.

- **44px minimum** on anything tappable. Enforced on rack module
  switches, format pickers, Hours decision buttons, EPK controls and the
  two header buttons.
- **Hover-only is missing on touch.** Anything revealed by
  `group-hover:` needs an `@media (hover: none)` fallback. Removing a
  catalog track was impossible on a phone because of this.
- **Keyboard focus must be visible**, and shaped like its control — the
  rack knobs carry a round ring, because a square outline on a round knob
  reads as a rendering fault.

## Motion

For loading, completion, progression, validation and status changes.
Not for decoration. `prefers-reduced-motion` is honoured.

## Components worth reusing

`.u` / `.u-dark` / `.u-silver` (rack units), `.plate`, `.pick` +
`.cap` (segmented pickers), `.sw` (switch/button), `.fader`, `.lamp`,
`.lane`, `.note`, `.sk` (engraved label), `.chip`, `.rk-knob`.

## Known debt

- Tailwind arbitrary values are duplicated rather than tokenised. A real
  token layer wants a build step, which is a bigger decision than a
  stylesheet.
- `loudness.js` and `audio_readiness.py` each keep their own copy of the
  platform loudness targets. A test forbids them disagreeing, but they
  are still two copies.
- ~10 painful and ~12 cosmetic mobile findings remain, plus 48 rack
  `title=` tooltips carrying the only explanation of what a control does
  — invisible on touch, and a content decision rather than a layout one.

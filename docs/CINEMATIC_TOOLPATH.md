# Cinematic Toolpath

A film prompt generator, not a verification. From the CUT workspace
(viewport stack → Scene → Cinematic) the user selects operations and gets a
deterministic AI-video prompt, shot list and JSON storyboard built from
structured CANVAS state. Every output carries
**CINEMATIC PREVIEW — NOT NC VERIFICATION**.

## Purpose / non-purpose

For customer communication, training, demos, product storytelling. NOT for
NC verification, collision validation, proving manufacturability, or
clearing any gate — the drawer only writes text, and the technical
playback, simulator, readiness and export paths are untouched by it.

## Generation logic

`src/lib/cinematic.ts`, pure and deterministic — no model call. Shots map
from real operation types (FACE sweep, pocket spiral, drill descent, bore
axis, synchronised tap, chamfer pass); timing distributes the chosen
duration across the selected operations **weighted by their real cycle
times**, with an establishing shot and optional reveal. Style presets set
the photographic direction; a fixed constraint block demands photorealism
and bans sparks, sci-fi glow and the generic AI aesthetic. Values CANVAS
does not hold are written "unspecified" or omitted — never invented.

## Customer-safe mode

Strips by construction, and is tested: part name and number gone, feature
labels replaced with generic process nouns ("Precision boring"), tool
descriptions dropped, material reduced to its family, stock dimensions
generalized. The unsafe text is never emitted while the mode is on.

## Privacy

A prompt full of part geometry is proprietary data the moment it leaves.
The drawer says so above the external-send control, which is a
DEVELOPMENT-labelled disabled stub — no external video service is
integrated, and nothing is ever sent automatically. Copy and download are
local.

## Future integration path

The JSON storyboard (`storyboard` in `generateCinematic`'s result) is the
contract: shots with start/end, operation, visual, camera, overlays. An
external video API or an internal renderer consumes that object; the
privacy notice becomes a real consent step at that point, and customer-safe
becomes enforceable server-side.

## Turning mappings (added)

`CinematicInput.process: "TURN"` + `barStock {diameter, length}` switch
the shots to the lathe voice: the bar spins, the tool holds. Op-type
mappings for FACE (facing insert, edge to center), OD_ROUGH/OD_FINISH,
GROOVE_OD, THREAD_OD (deepens visibly each pass — never one plunge),
PART_OFF (part caught cleanly), CENTER_DRILL/ID_DRILL/ID_BORE.
Customer-safe nouns: Rough/Finish turning, Grooving, Thread turning,
Parting off. Turning cameras: fixed cross-slide angle — the rotation is
the motion. Mill wording untouched (pinned by test). Entry point:
CINEMATIC button on the turning workspace operation plan; same shared
drawer, same NOT-NC-VERIFICATION disclaimer on every output.

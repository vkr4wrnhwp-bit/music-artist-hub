# Scan import

The third route into reverse engineering, alongside photographs and guided
measurement. It was a chip reading "Import scan — not implemented" for as
long as the page existed.

## What a scan is, in CANVAS terms

A STEP file is the design authority. A scan is **one worn example, measured
by one instrument**. That difference decides the whole design:

| | STEP import | Scan import |
|---|---|---|
| Provenance of extracted values | `CALCULATED` | `MEASURED`, attributed to a device |
| Uncertainty | none needed — it is the drawing | the scanner's recorded uncertainty |
| Units | declared in the file | **not in the file at all** |
| Lands as | a part with recognized features | a measurement session with PENDING readings |

## The two refusals

Both are refusals rather than defaults, for the same reason the CAM engine
refuses a material with no surface-speed window.

**No declared units, no import.** An STL file records no units. None. A cube
25.4 units on a side is a 1" cube or a 25.4" cube and the file cannot settle
it — every scanner writes whatever its own setting was. The importer takes
the units as a declaration by the person importing and records them as such.
Guessing here is wrong by a factor of 25.4.

**No scanner on file, no import.** A scan's accuracy is the scanner's
accuracy. Without a metrology record there is no uncertainty to attach to any
dimension that comes out, and an unqualified dimension off a mesh is the
exact thing reverse engineering exists to avoid. The instrument is chosen
from the shop's own metrology library, filtered by `SCANNING_INSTRUMENTS`.

## What the mesh is allowed to claim

Derived, deterministically, from the triangles:

- **Envelope** — arithmetic over every vertex.
- **Mesh integrity** — every edge of a closed surface is shared by exactly
  two triangles. An open mesh means the scanner did not see the whole part,
  so the envelope bounds *what was seen*, which is a lower bound on the part.
  This demotes the envelope to `unknown` in the part intent rather than
  recording a confident number.
- **Planar regions** — coplanar facets grouped within 1° of a shared normal,
  above a 0.05 in² noise floor. Candidate faces. **Not datums** — which face
  seats in service is a human's knowledge.

Listed as not attempted, in the output, every time:

- Bores, holes and radii — finding them needs surface fitting this does not do
- Threads — a scanned helix is not a thread designation
- Tolerances and fits — a scan measures a worn example, not the drawing
- Datums — a human's knowledge, not the mesh's
- Functional roles — what a part does cannot be read off its shape

## Format detection

By arithmetic, not by the leading keyword. Plenty of binary exporters write
`solid` into their 80-byte header, so sniffing the keyword misreads those
files as ASCII. The triangle count at offset 80 either accounts for the
file's exact length or it does not.

## Normals

Many exporters write `(0,0,0)` and expect the reader to derive the normal.
A zero normal is not a direction, and face grouping is done on normals, so
accepting one would put every such facet into a single bucket. Non-unit and
zero normals are recomputed from the vertex winding and **counted** — the
count appears in the assumptions, because it is a fact about the exporter
worth knowing. A genuinely degenerate (zero-area) triangle has no normal and
is counted separately rather than given one.

## No model call

Reading triangles is arithmetic. The audit entry for the inspection is
`actorType: SYSTEM`, and `tests/engines/locked-principles.test.ts` keeps the
pipeline free of the AI layer.

## Scope not built

- **Cylinder and bore fitting.** Real work, and the honest v1 says it did not
  do it rather than shipping a fit nobody validated.
- **Mesh repair.** CANVAS reports open edges; it does not close them.
- **Alignment to a datum frame.** The scan lands in its own coordinates.
- **PLY, OBJ, 3MF.** STL is what scanners export by default.
- **Storing the mesh as an asset.** The inspection is stored; the file is not.

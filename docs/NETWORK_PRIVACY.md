# Network privacy

The network layer is the long-term reason CANVAS is valuable and the single
easiest thing to get catastrophically wrong. A shop's part geometry is its
livelihood. So the privacy model was built first, and the matching is built on
top of it — never the other way round.

**Phase 1 ships the privacy model and the fingerprint. It ships no matching.**

## Defaults

`PRIVATE`, at both organisation and part level. Nothing leaves. The default is
never raised automatically, never raised by an update, and never raised as a
side effect of any other action.

## Levels

| Level | What it permits |
|---|---|
| `PRIVATE` | Nothing leaves the organisation. Default. |
| `ANONYMOUS_LEARNING` | Anonymised manufacturing *outcomes* — what held, what chattered, what scrapped — contribute to CANVAS's models. No geometry, no dimensions, no identity. |
| `NETWORK_MATCH` | An anonymous fingerprint may be compared against other opted-in shops. Identity revealed only if the user accepts an introduction. |
| `MARKETPLACE` | The part may be listed for quoting. Explicit per-part opt-in. |

Every change writes a `NetworkPermission` row and an audit entry naming the
human who made it.

## The fingerprint

`buildFingerprint()` is lossy by construction. It emits bands, families and
classes — never numbers.

**Present:** geometry family, process family, material family, envelope band
(XS–XL), feature type list, bearing interface count, fastener interface count,
tolerance class, surface finish class, quantity band, machine class, complexity
band, workholding class, operation sequence, setup count.

**Deliberately absent:** part name, part number, customer, organisation
identity, any dimension, any tolerance value, any feature label, any note, any
free text, any file, any geometry.

`describeFingerprintDisclosure()` enumerates every field with its
re-identification risk, and the Network page renders that table built from a
*real* part — so a user sees exactly what would leave, and a reviewer can spot
a field that should never have been added.

## Matching (designed, not built)

Supplier match and the revenue-opportunity engine are the same comparison run
in opposite directions. Both are gated behind `NETWORK_MATCH`, both operate on
fingerprints only, and neither reveals identity without an explicit
per-request consent step.

The Network page says "not implemented" rather than showing a mock match.

## Collective intelligence

`JobOutcome` captures structured outcomes — `SUCCESS`, `PART_MOVED`, `CHATTER`,
`TOOL_BREAK`, `POOR_FINISH`, `OUT_OF_TOLERANCE`, `WORKHOLDING_FAILURE`,
`WARPED`, `COLLISION` — with a cause chosen from a per-outcome list rather than
typed free-form, so the data stays analysable and carries no incidental
proprietary detail.

Under `ANONYMOUS_LEARNING` these outcomes teach the workholding and process
models. The outcome record contains no geometry.

## Manufacturing DNA

Per-part, per-revision, immutable, and **always private**. It records what was
actually made and what happened: geometry revision, material, process, machine,
setup, workholding, tooling, feeds, speeds, toolpaths, inspection, measured
results, cycle time, tool wear, scrap, failures, corrective actions, cost,
supplier. This is the shop's institutional memory and is never a network input
at any sharing level.

## Tenancy

The organisation boundary is enforced in `lib/data.ts`: every accessor takes
`organizationId` from the session, never from a request parameter. Asset reads
verify the asset row belongs to the caller's organisation before a single byte
is served — the storage key alone is never sufficient.

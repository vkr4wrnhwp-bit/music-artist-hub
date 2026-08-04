# Capability status

One vocabulary for what is real, used on the homepage, the public product
tour and the example workspaces. Six labels and nothing else. The list is
enforced by `tests/test_closing.py::test_status_vocabulary_is_the_agreed_six`,
and the labels live in `tour_config.STATUS_LABELS`.

| Label | Means | Colour |
| --- | --- | --- |
| **Live** | Working in the product today. | green |
| **Example** | A worked example. Not any artist's data. | brass |
| **Partner delivered** | Carried out through a distribution partner, not by Street Banker directly. | blue |
| **Integration ready** | Built here; the outside connection is not live. | tan |
| **Coming soon** | Not built yet. Named so nobody assumes it is. | grey |
| **Requires verification** | A finding a person must check before it is acted on. | orange |

Colour is never the only signal. Every chip carries its own word, so the
meaning survives greyscale and colour-blindness.

## Where each label is used

### Live
Artist EQ and the plan it produces · Metadata Passport record and
conflict detection · Creative Studio brief → directions → revision →
approval → adaptation · cover, merch, poster, social, story, thumbnail
and press-kit output · Smart Link pages, email capture and consent
recording · campaign-source, device, return-visitor and signup readings ·
Rights & Ownership splits and documents · the lanes · the starting plan.

### Example
Every Artist Twin reading shown publicly · the example passport · the
example recovery opportunity · the example smart link · the example fan
intelligence rows · the 21-day rollout example.

### Partner delivered
Delivery to stores and platforms. Street Banker assembles and validates
the release package; delivery goes out through the distribution
partnership (SummitArts on Symphonic Distribution), not a direct line
from this application.

### Integration ready
Rollout Engine publishing — the campaign is prepared here and posted by a
person · smart-link streaming destinations · geographic response ·
conversion events.

### Coming soon
SMS capture · QR codes for a printed run · motion and video assets ·
print-ready separations.

### Requires verification
Every Royalty Sweep finding, without exception. A finding is a question
with evidence attached. It is never submitted anywhere on the strength of
the match alone, and any figure attached to it is arithmetic on the
artist's own statements rather than a prediction.

## Rules for adding a capability

1. If it is not built, it is **Coming soon**. There is no label meaning
   "nearly".
2. If the interface exists and the outside connection does not, it is
   **Integration ready** — never Live.
3. If somebody else performs it, it is **Partner delivered**, and the
   partner is named.
4. If the data on screen is invented, the label is **Example** and the
   surrounding copy says so in words as well.
5. Nothing on any public surface carries a figure that was not computed
   from a real input. No recovery totals, stream counts, artist counts,
   country counts, earnings or accuracy percentages appear anywhere.

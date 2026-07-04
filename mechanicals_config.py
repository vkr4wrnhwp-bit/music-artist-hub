"""Config-driven data for the Mechanical Royalties (MLC) page.

Mechanical royalties are owed for every reproduction/stream of a
composition in the US, collected by The MLC. Works that aren't
registered/matched with the MLC have their mechanicals held in the MLC's
"black box" of unmatched royalties until claimed. This page tracks
matched vs. unmatched mechanicals per work.

The mechanical figure uses the same basis as the Publishing page
(a share of each work's total earnings) so the two stay consistent;
it's an estimate, since the app doesn't line-item mechanicals.
"""

from royalty_data import get_songs

# Matches publishing_config's _MECHANICAL_SHARE so both pages agree.
_MECHANICAL_SHARE = 0.12


def get_mechanicals_data():
    works = []
    for s in get_songs():
        mechanical_total = round(s.total_earned * _MECHANICAL_SHARE, 2)
        matched = bool(s.registrations.get("mlc"))
        works.append({
            "id": s.id,
            "title": s.title,
            "streams": s.streams,
            "mlc_matched": matched,
            "mechanical_total": mechanical_total,
            "matched_amount": mechanical_total if matched else 0.0,
            "blackbox_amount": 0.0 if matched else mechanical_total,
        })

    matched_total = round(sum(w["matched_amount"] for w in works), 2)
    blackbox_total = round(sum(w["blackbox_amount"] for w in works), 2)
    # Reconcile the headline total from its parts so matched + black box
    # always equals it exactly (no separate-rounding drift).
    mechanical_total = round(matched_total + blackbox_total, 2)
    matched_works = sum(1 for w in works if w["mlc_matched"])
    total = len(works) or 1

    return {
        "summary": {
            "total_works": len(works),
            "matched_works": matched_works,
            "match_rate": round(matched_works / total * 100),
            "mechanical_total": mechanical_total,
            "matched_total": matched_total,
            "blackbox_total": blackbox_total,
        },
        "works": works,
    }

"""Config-driven data for the Neighboring Rights page.

Neighboring (or "related") rights are royalties owed to the performer
and master owner when a recording is played publicly — collected in the
US by SoundExchange and abroad by societies like PPL (UK) and GVL
(Germany). Independent artists routinely leave the international side
uncollected because they never register with foreign societies.

SoundExchange registration status and any SoundExchange earnings are
real (from the catalog). International collection is not tracked by the
app, so foreign-society coverage and the uncollected estimate are
clearly marked illustrative.
"""

from royalty_data import get_songs

# US collection is real; the foreign societies are illustrative gaps to
# show the recovery opportunity. registered=False means money is likely
# sitting uncollected in that territory.
_FOREIGN_SOCIETIES = [
    {"name": "PPL", "territory": "United Kingdom", "registered": False},
    {"name": "GVL", "territory": "Germany", "registered": False},
    {"name": "SCAPR network", "territory": "International (45+ territories)", "registered": False},
]

# Share of a recording's earnings estimated to be recoverable neighboring
# rights income when a channel isn't being collected. Illustrative only.
_US_UNCOLLECTED_SHARE = 0.08
_INTL_UNCOLLECTED_SHARE = 0.06


def _recording(song):
    se_registered = bool(song.registrations.get("soundexchange"))
    collected_us = round((song.platform_earnings or {}).get("SoundExchange", 0.0), 2)

    uncollected = 0.0
    if not se_registered:
        uncollected += round(song.total_earned * _US_UNCOLLECTED_SHARE, 2)
    # No foreign societies registered -> the international share is uncollected.
    uncollected += round(song.total_earned * _INTL_UNCOLLECTED_SHARE, 2)

    return {
        "id": song.id,
        "title": song.title,
        "master_owner": song.master_owner,
        "streams": song.streams,
        "soundexchange_registered": se_registered,
        "collected_us": collected_us,
        "uncollected": round(uncollected, 2),
    }


def get_neighboring_rights_data():
    songs = get_songs()
    recordings = [_recording(s) for s in songs]

    se_registered = sum(1 for r in recordings if r["soundexchange_registered"])
    collected_total = round(sum(r["collected_us"] for r in recordings), 2)
    uncollected_total = round(sum(r["uncollected"] for r in recordings), 2)

    # Artist-level US registration: treat SoundExchange as "registered"
    # when the catalog is majority-registered (derived from real status).
    total = len(recordings) or 1
    us_registered = se_registered >= (total / 2)
    us_collected = collected_total

    societies = [
        {
            "name": "SoundExchange",
            "territory": "United States",
            "registered": us_registered,
            "collected": us_collected,
        }
    ] + [dict(s, collected=0.0) for s in _FOREIGN_SOCIETIES]

    territories_covered = sum(1 for s in societies if s["registered"])

    return {
        "summary": {
            "recordings": len(recordings),
            "se_registered": se_registered,
            "se_pct": round(se_registered / total * 100),
            "collected_total": collected_total,
            "uncollected_total": uncollected_total,
            "territories_covered": territories_covered,
            "territories_total": len(societies),
        },
        "recordings": recordings,
        "societies": societies,
    }

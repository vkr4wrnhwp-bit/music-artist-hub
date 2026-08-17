"""Bridge between REACH and the host application's royalty data.

Everything REACH knows about a track's real-world performance comes from here,
and it is all first-party data the tenant already owns — which is why it is the
only source permitted into pitch copy.

Note what this module does *not* do: it does not invent musical attributes. The
host catalog models rights and royalty metadata (ISRC, splits, registrations,
earnings), not BPM, key or genre. So :func:`derived_profile_hints` returns only
what is genuinely present, and the campaign wizard asks the artist for the rest
rather than guessing. This function is also the seam where a distributor feed,
a DDEX RIN import or local audio analysis would attach later.
"""

import royalty_data

AUDIO_ANALYSIS_STATE = "NO_AUDIO_SOURCE_CONFIGURED"


def derived_profile_hints(song):
    """{field: (value, confidence)} for fields the host catalog really contains."""
    hints = {}
    # The host catalog has no musical attributes to derive. Anything added here
    # must come from a real field on the Song record, never from its title or
    # the artist's name.
    if song is None:
        return hints
    if getattr(song, "alternate_titles", None):
        # Alternate titles are a genuine catalog field and are useful when a
        # curator's guidelines ask which version is being submitted.
        hints["release_narrative"] = (
            f"Also catalogued as: {', '.join(song.alternate_titles)}",
            0.5,
        )
    return hints


def performance_baseline(song):
    """First-party performance facts. Safe to quote in outreach."""
    if song is None:
        return {}
    trend = list(song.monthly_trend or [])
    growth = None
    if len(trend) >= 2 and trend[0] > 0:
        growth = round((trend[-1] - trend[0]) / trend[0] * 100)
    return {
        "streams": song.streams,
        "total_earned": round(song.total_earned, 2),
        "monthly_trend": trend,
        "trend_growth_pct": growth,
        "platforms_with_earnings": sorted(song.platform_earnings.keys()),
        "writers": list(song.writers or []),
        "producers": list(song.producers or []),
        "publisher": song.publisher,
        "isrc": song.isrc,
    }


def catalog_platform_status(platform_name):
    """Connection status of a platform in the host app, by display name."""
    for entry in royalty_data.get_platform_catalog():
        if entry.platform.lower() == (platform_name or "").lower():
            return entry.status
    return None


def audio_analysis_state():
    """Local deterministic audio analysis is unavailable until audio files are
    attached to the catalog. Reported honestly rather than simulated."""
    return {
        "state": AUDIO_ANALYSIS_STATE,
        "detail": "The host catalog stores no audio file references, so BPM, key and "
                  "energy cannot be computed locally. These stay user-supplied.",
    }

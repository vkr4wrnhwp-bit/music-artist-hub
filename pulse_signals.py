"""The growth-signal instruments on Artist Pulse, built from what is on file.

One dict per signal, in the shape templates/_sb.html's `instrument`
macro draws. Each carries the reading, where it came from and when, and
whether it moved - and each is honest about what it does not have:

  * a reading nobody took is None and reads "Not measured", never 0
  * a series with gaps keeps the gaps; a run of unmeasured days at the
    end is drawn dashed so a stale figure looks stale
  * YouTube has no history, so its instrument has no line and says so
  * TikTok has no public artist-stats API; its instrument is built so
    nobody thinks it was forgotten. The page does not draw an instrument
    with no reading at all (state "none"); it names it, with this
    detail, under the bridge instead (owner notes, 2026-09-19)
"""
from datetime import date, timedelta

import meters

WINDOW_DAYS = 28


def _series(snaps, key):
    """(day, value) oldest first, from the stored snapshots."""
    return [(s.get("day") or "", s.get(key)) for s in (snaps or [])]


def _value_days_back(series, days, today):
    """The nearest measured value at or before `days` ago, else None."""
    cutoff = (today - timedelta(days=days)).isoformat()
    candidates = [v for d, v in series if d and d <= cutoff and v is not None]
    return candidates[-1] if candidates else None


def _last_measured(series):
    for _d, v in reversed(series):
        if v is not None:
            return v
    return None


def _days_old(day, today):
    try:
        return (today - date.fromisoformat(str(day)[:10])).days
    except (TypeError, ValueError):
        return None


def instrument(key, label, value, series, provider, as_of, today, *,
               scale="", detail="", history=True, fmt=None, stale=False):
    """One instrument. `value` None means not measured."""
    fmt = fmt or (lambda v: "{:,}".format(int(round(v))))
    series = [(d, v) for d, v in (series or []) if d]
    last = value if value is not None else _last_measured(series)
    spark = meters.sparkline(series) if history else None
    measured_vals = [v for _d, v in series if v is not None]
    low = min(measured_vals + ([value] if value is not None else [])) if (measured_vals or value is not None) else None
    high = max(measured_vals + ([value] if value is not None else [])) if (measured_vals or value is not None) else None
    d7 = meters.pct_change(_value_days_back(series, 7, today), last)
    d28 = meters.pct_change(_value_days_back(series, WINDOW_DAYS, today), last)
    age = _days_old(as_of, today) if as_of else None
    if value is None and last is None:
        state = "none"
    elif stale or (age is not None and age > 1):
        state = "stale"
    else:
        state = "fresh"
    if state == "none":
        lamp = "not measured"
    elif state == "stale":
        lamp = ("%d days old" % age) if age is not None and age > 1 else "last figures on file"
    else:
        lamp = "fresh"
    return {
        "source": ("provider" if key in ("listeners", "followers_provider") else "platform"),
        "key": key, "label": label,
        "value": last, "shown": (fmt(last) if last is not None else None), "scale": scale,
        "delta7": d7, "delta28": d28,
        "spark": spark,
        "spark_first": meters.short(spark["first"]) if spark else "",
        "spark_last": meters.short(spark["last"]) if spark else "",
        "low": low, "high": high,
        "low_short": meters.short(low), "high_short": meters.short(high),
        "rail_pos": meters.rail(low, high, last),
        "provider": provider, "as_of": (str(as_of)[:10] if as_of else ""),
        "state": state, "lamp": lamp, "detail": detail, "history": history,
        "missing_days": ((spark["total"] - spark["measured"]) if spark else 0),
    }


# Why Deezer fans read "Not measured", by what actually happened. Deezer is
# looked up by the name Spotify returns, so without Spotify it is never
# asked, and "no match" is only true after a search that came back empty.
DEEZER_WHY = {
    "no_spotify": ("Deezer is looked up by the Spotify artist name, and Spotify "
                   "is not connected on this service, so Deezer was not asked."),
    "spotify_failed": ("Deezer is looked up by the Spotify artist name, and "
                       "Spotify did not answer just now, so Deezer was not asked."),
    "no_answer": "Deezer did not answer just now.",
    "no_match": "No Deezer match found for this name.",
}


def build(pulse, metrics, youtube, deezer, snaps, today=None, deezer_state=None):
    """The bridge, in display order. Every argument may be None.

    `deezer_state` says why Deezer fans may be missing: "no_spotify",
    "spotify_failed", "no_answer" or "no_match" (DEEZER_WHY). None, from a
    caller that did not say, never claims a search came back empty."""
    today = today or date.today()
    out = []

    if metrics:
        prov_snaps = metrics.get("snapshots") or []
        out.append(instrument(
            "listeners", "Monthly listeners", metrics.get("monthly_listeners"),
            _series(prov_snaps, "monthly_listeners"), metrics.get("label") or "provider",
            metrics.get("as_of"), today, stale=bool(metrics.get("stale")),
            detail=metrics.get("note") or ""))
        if metrics.get("followers") is not None:
            # The provider's own follower reading, beside Spotify's live one
            # below: two sources, two instruments, each named. Merging them
            # would put one vendor's figure under another vendor's name.
            out.append(instrument(
                "followers_provider", "Followers", metrics.get("followers"),
                _series(prov_snaps, "followers"), metrics.get("label") or "provider",
                metrics.get("as_of"), today, stale=bool(metrics.get("stale")),
                detail="As measured by %s." % (metrics.get("label") or "the provider")))

    spotify_snaps = snaps or []
    # Spotify retired followers, popularity and genres for apps like this
    # one (2026-09-15). A 0 on file for either came from the days it sent
    # 0 for a field it had stopped counting, and is not a measurement:
    # it must never stand in for a figure as "fresh 0" (owner, live).
    def _spotify_series(key):
        return [(d, (None if v == 0 else v)) for d, v in _series(spotify_snaps, key)]

    followers = (pulse or {}).get("followers") if pulse else None
    followers_series = _spotify_series("followers")
    out.append(instrument(
        "followers", "Spotify followers", followers,
        followers_series, "Spotify",
        today.isoformat() if followers is not None else
        (spotify_snaps[-1].get("day") if spotify_snaps else None), today,
        detail=("" if followers is not None else
                "Spotify no longer sends a follower count to apps like this one; "
                "the followers figure above comes from the provider where one is connected.")))

    popularity = (pulse or {}).get("popularity") if pulse else None
    out.append(instrument(
        "popularity", "Popularity", popularity,
        _spotify_series("popularity"), "Spotify",
        today.isoformat() if popularity is not None else
        (spotify_snaps[-1].get("day") if spotify_snaps else None), today,
        scale="/100", fmt=lambda v: "%d" % int(round(v)),
        detail=("Spotify's own 0-100 signal, based on recent plays." if popularity is not None
                else "Spotify no longer sends a popularity figure to apps like this one.")))

    fans = (deezer or {}).get("fans") if deezer else None
    out.append(instrument(
        "deezer", "Deezer fans", fans,
        _series(spotify_snaps, "deezer_fans"), "Deezer",
        today.isoformat() if fans is not None else
        (spotify_snaps[-1].get("day") if spotify_snaps else None), today,
        detail=("" if fans is not None else
                DEEZER_WHY.get(deezer_state or "", "Deezer was not read for this artist."))))

    if youtube is not None:
        subs = youtube.get("subscribers")
        out.append(instrument(
            "youtube", "YouTube subscribers", subs, [], "YouTube",
            today.isoformat() if subs is not None else None, today, history=False,
            detail=("Current total only; no history is available." if subs is not None
                    else (youtube.get("note") or "Not measured"))))

    out.append(instrument(
        "tiktok", "TikTok", None, [], "TikTok", None, today, history=False,
        detail="No data available from this platform."))
    return out

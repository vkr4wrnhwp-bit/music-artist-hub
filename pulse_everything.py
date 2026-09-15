"""Everything the metrics provider holds on the Pulse artist.

Owner, 2026-09-14: "i want everything it can pull on the artist pulse,
we need as much information as we can find". The instrument row above
this carries the growth figures; this builds the rest, one section per
question the provider answers: who the artist is, the audience on every
platform, playlists by platform, the three audience reports, radio, the
YouTube daily views. (Related artists, the platform pages and the song
list were on the page for one day and came off, owner, 2026-09-15.)

Each section is its own call and its own failure. A section the plan
refuses reads "not in the plan"; one the provider holds nothing for
reads "nothing on file"; one that did not answer says so. Nothing is
estimated to fill a gap, and every count names who measured it.
"""
from datetime import date, datetime, timedelta, timezone

WINDOW_DAYS = 28

PLATFORM_NAMES = {
    "spotify": "Spotify", "deezer": "Deezer", "soundcloud": "SoundCloud",
    "youtube": "YouTube", "instagram": "Instagram", "tiktok": "TikTok",
    "facebook": "Facebook", "twitter": "X (Twitter)", "apple-music": "Apple Music",
    "amazon": "Amazon Music",
}

# Related artists, the platform pages and the song list came off the page
# (owner, 2026-09-15) and are not asked for.
SECTIONS = ("profile", "audience", "playlists", "reports", "radio", "youtube_views")


def platform_name(code):
    return PLATFORM_NAMES.get(code, (code or "").replace("-", " ").title())


def _sparkline(points, width=200, height=40):
    """SVG polyline points for a daily series, or "" for fewer than two."""
    vals = [p["views"] for p in points if p.get("views") is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = float(hi - lo) or 1.0
    step = float(width) / (len(vals) - 1)
    return " ".join("%.1f,%.1f" % (i * step, height - 2 - (v - lo) / span * (height - 4))
                    for i, v in enumerate(vals))


def build(prov, provider_artist_id, today=None):
    """The whole view, or None when the provider does not offer this."""
    if prov is None or not provider_artist_id or not hasattr(prov, "get_audience_all"):
        return None
    end = today or datetime.now(timezone.utc).date()
    start = end - timedelta(days=WINDOW_DAYS)
    out = {"label": getattr(prov, "label", "the provider"), "provider_artist_id": provider_artist_id,
           "window_days": WINDOW_DAYS, "refused": [], "failed": [], "empty": []}
    calls = {
        "profile": lambda: prov.get_profile(provider_artist_id),
        "audience": lambda: prov.get_audience_all(provider_artist_id, start, end),
        "playlists": lambda: prov.get_playlists_all(provider_artist_id),
        "reports": lambda: prov.get_audience_reports(provider_artist_id),
        "radio": lambda: prov.get_radio(provider_artist_id, start, end),
        "youtube_views": lambda: prov.get_youtube_views(provider_artist_id, start, end),
    }
    for key in SECTIONS:
        try:
            value = calls[key]()
        except Exception as e:                                  # noqa: BLE001
            text = str(e)
            out[key] = None
            (out["refused"] if "403" in text else out["failed"]).append(key)
            continue
        out[key] = value
        if not value:
            out["empty"].append(key)
    # Shapes the template reads directly.
    out["audience_rows"] = []
    for code, reading in (out.get("audience") or {}).items():
        row = dict(reading)
        row["platform"] = code
        row["name"] = platform_name(code)
        out["audience_rows"].append(row)
    out["playlist_rows"] = []
    for code, got in (out.get("playlists") or {}).items():
        row = dict(got)
        row["platform"] = code
        row["name"] = platform_name(code)
        out["playlist_rows"].append(row)
    out["report_rows"] = []
    for code, rep in (out.get("reports") or {}).items():
        row = dict(rep)
        row["platform"] = code
        row["name"] = platform_name(code)
        row.setdefault("state", "measured")
        out["report_rows"].append(row)
    yt = out.get("youtube_views") or []
    out["youtube_line"] = {
        "points": _sparkline(yt),
        "latest": yt[-1] if yt else None,
        "total": sum(p["views"] for p in yt) if yt else None,
        "days": len(yt),
    }
    return out

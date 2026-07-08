"""Config-driven data for the EPK / Press Kit builder.

Composes an artist press kit from live catalog data (streams, earnings,
catalog value, top tracks) plus an editable artist profile block. The
derived stats stay in sync with the rest of the app; the profile fields
(bio, genres, socials, contact, press) are artist-supplied and live here
so they can be edited without touching the template.
"""

from royalty_data import get_songs

# Artist-supplied profile. Not derivable from royalty data, so it lives
# here as editable config rather than being hard-coded in the template.
# The display name is intentionally omitted -- it comes from the shared
# account config so the EPK, sidebar chip, and settings stay consistent.
_EPK_PROFILE = {
    "tagline": "Synthwave-driven pop for late-night drives.",
    "bio": (
        "An independent artist blending analog synths with modern pop "
        "production. Self-released and self-owned, with a catalog that has "
        "quietly crossed the multi-million-stream mark across every major "
        "platform."
    ),
    "genres": ["Synthwave", "Electronic Pop", "Alternative"],
    "location": "Los Angeles, CA",
    "socials": [
        {"label": "Instagram", "handle": "@artiswar", "logo": "other"},
        {"label": "TikTok", "handle": "@artiswar", "logo": "tiktok"},
        {"label": "YouTube", "handle": "Art Is War", "logo": "youtube"},
        {"label": "Spotify", "handle": "Art Is War", "logo": "spotify"},
    ],
    "contact": {
        "booking": "booking@streetbanker.co",
        "management": "Street Banker Management",
        "press": "press@streetbanker.co",
    },
    # Editable pull quotes for the press strip.
    "press": [
        {"quote": "A gleaming, confident record that sounds bigger than its budget.", "source": "Indie Wave"},
        {"quote": "One of the most consistent independent catalogs we've heard this year.", "source": "Nightdrive Mag"},
    ],
}

# Which sections the artist can toggle into the shareable kit.
_SECTIONS = [
    {"key": "bio", "label": "Artist Bio", "on": True},
    {"key": "stats", "label": "Career Stats", "on": True},
    {"key": "tracks", "label": "Top Tracks", "on": True},
    {"key": "press", "label": "Press Quotes", "on": True},
    {"key": "contact", "label": "Contact", "on": True},
]


def _fmt_compact(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(int(n))


_SOCIAL_KEYS = [("instagram", "Instagram", "other"), ("tiktok", "TikTok", "tiktok"),
                ("youtube", "YouTube", "youtube"), ("spotify", "Spotify", "spotify")]


def normalize_epk_overrides(payload):
    """Validate + shape a saved editor payload into profile overrides."""
    p = payload or {}
    out = {}
    for key, cap in (("tagline", 120), ("bio", 1200), ("location", 80)):
        val = (p.get(key) or "").strip()
        if val:
            out[key] = val[:cap]
    genres = [g.strip() for g in (p.get("genres") or "").split(",") if g.strip()][:6]
    if genres:
        out["genres"] = genres
    socials = []
    for key, label, logo in _SOCIAL_KEYS:
        handle = ((p.get("socials") or {}).get(key) or "").strip()
        if handle:
            socials.append({"label": label, "handle": handle[:60], "logo": logo})
    if socials:
        out["socials"] = socials
    contact = {k: ((p.get("contact") or {}).get(k) or "").strip()[:120]
               for k in ("booking", "press", "management")}
    if any(contact.values()):
        out["contact"] = contact
    press = [{"quote": (q.get("quote") or "").strip()[:220], "source": (q.get("source") or "").strip()[:60]}
             for q in (p.get("press") or []) if (q.get("quote") or "").strip()][:3]
    if press:
        out["press"] = press
    if "show_sweep" in p:
        out["show_sweep"] = bool(p.get("show_sweep"))
    return out


def get_epk_data(account, catalog_value, overrides=None, photo=None):
    songs = get_songs()
    total_streams = sum(s.streams for s in songs)
    total_earned = sum(s.total_earned for s in songs)

    # Aggregate platform earnings to name the artist's biggest platform.
    platform_totals = {}
    for s in songs:
        for platform, amount in (s.platform_earnings or {}).items():
            platform_totals[platform] = platform_totals.get(platform, 0) + amount
    top_platform = max(platform_totals, key=platform_totals.get) if platform_totals else "Spotify"

    top_tracks = sorted(songs, key=lambda s: s.streams, reverse=True)[:5]
    top_tracks = [
        {
            "title": s.title,
            "streams": s.streams,
            "streams_compact": _fmt_compact(s.streams),
            "earned": round(s.total_earned, 2),
            "owner": s.master_owner,
        }
        for s in top_tracks
    ]

    stats = [
        {"label": "Total Streams", "value": _fmt_compact(total_streams), "sub": "All platforms, all time"},
        {"label": "Catalog Earnings", "value": "${:,.0f}".format(total_earned), "sub": "Collected to date"},
        {"label": "Est. Catalog Value", "value": "${:,.0f}".format(catalog_value["mid"]), "sub": "Mid valuation"},
        {"label": "Releases", "value": str(len(songs)), "sub": "In active catalog"},
    ]

    # Merge the artist's saved edits over the demo defaults.
    profile = {k: (v.copy() if isinstance(v, (dict, list)) else v) for k, v in _EPK_PROFILE.items()}
    o = overrides or {}
    for key in ("tagline", "bio", "location", "genres", "socials", "press"):
        if o.get(key):
            profile[key] = o[key]
    if o.get("contact"):
        profile["contact"] = {**profile["contact"],
                              **{k: v for k, v in o["contact"].items() if v}}

    # Editor prefill: flat handle map for the fixed social rows.
    social_handles = {key: "" for key, _, _ in _SOCIAL_KEYS}
    for s in profile["socials"]:
        for key, label, _ in _SOCIAL_KEYS:
            if s["label"] == label:
                social_handles[key] = s["handle"]

    return {
        "name": account["name"],
        "initials": account["initials"],
        "profile": profile,
        "social_handles": social_handles,
        "photo": photo,
        "customized": bool(o),
        "show_sweep": bool(o.get("show_sweep")),
        "top_platform": top_platform,
        "stats": stats,
        "top_tracks": top_tracks,
        "sections": _SECTIONS,
    }

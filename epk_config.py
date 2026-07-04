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


def get_epk_data(account, catalog_value):
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

    return {
        "name": account["name"],
        "initials": account["initials"],
        "profile": _EPK_PROFILE,
        "top_platform": top_platform,
        "stats": stats,
        "top_tracks": top_tracks,
        "sections": _SECTIONS,
    }

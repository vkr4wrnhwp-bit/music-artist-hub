"""
The sample browse feed behind the fan-facing Discover section.

Every name, title and play count in _TRACKS below is invented. Nobody
called Nova Reign recorded Midnight Drive and nobody played it 5,200,000
times. The list is showcase content and nothing else: it exists so the
seeded demo logins have a feed to walk a partner through, and the owner
keeps it for that.

So it is handed out only when the caller says the session is a showcase
one. get_discover_data(showcase=False) is the default, because the
fail-safe answer to "may this account be shown invented data" is no; it
returns the same shape with every list empty, and templates/discover.html
draws the real iTunes search and an honest empty state instead. A real
fan account is never served a name, a cover or a figure from this file.

The old docstring here said the tracks "reference real network artists
and catalog titles". They do not. They reference network_config, which
is itself a parked directory of invented people (docs/PARKED_PAGES.md),
and a fan signing up read the whole page as a music service.

Likes and follows belong to the caller's session and are passed in; this
module keeps no state of its own.
"""

import os

from royalty_data import get_songs

GENRES = ["Synthwave", "Electronic", "House", "Techno", "Pop",
          "Hip-Hop", "R&B", "Indie", "Ambient"]

# Mood tiles (name + gradient art).
MOODS = [
    {"id": "late-night", "name": "Late Night", "from": "#1e1b4b", "to": "#0f172a"},
    {"id": "energetic", "name": "Energetic", "from": "#7f1d1d", "to": "#b45309"},
    {"id": "chill", "name": "Chill", "from": "#0e7490", "to": "#0f172a"},
    {"id": "focus", "name": "Focus", "from": "#064e3b", "to": "#0c0a09"},
    {"id": "feel-good", "name": "Feel Good", "from": "#a16207", "to": "#b91c1c"},
    {"id": "heartbreak", "name": "Heartbreak", "from": "#831843", "to": "#1e3a8a"},
]

# The sample feed. INVENTED, every row: artist, title and play count.
# Shown only to a showcase session (see the module docstring). artist_id
# names a /network profile, which is a parked directory of invented
# people - all nine ids below were checked against network_config._PROFILES
# on 2026-09-21 and all nine exist, so the links resolve rather than 404.
_TRACKS = [
    {"id": "tr-1", "art": "/static/img/discover/tr-1.jpg", "title": "Midnight Drive", "artist": "Nova Reign", "artist_id": "nova-reign", "genre": "Synthwave", "mood": "late-night", "plays": 5200000, "from": "#1e1b4b", "to": "#0f172a", "new": False},
    {"id": "tr-2", "art": "/static/img/discover/tr-2.jpg", "title": "Neon Dreams", "artist": "Nova Reign", "artist_id": "nova-reign", "genre": "Synthwave", "mood": "late-night", "plays": 3100000, "from": "#312e81", "to": "#0f172a", "new": True},
    {"id": "tr-3", "art": "/static/img/discover/tr-3.jpg", "title": "Afterglow", "artist": "Sable Wynn", "artist_id": "sable-wynn", "genre": "R&B", "mood": "heartbreak", "plays": 980000, "from": "#831843", "to": "#1e3a8a", "new": True},
    {"id": "tr-4", "art": "/static/img/discover/tr-4.jpg", "title": "Warehouse Set", "artist": "DJ Codec", "artist_id": "dj-codec", "genre": "Techno", "mood": "energetic", "plays": 640000, "from": "#7f1d1d", "to": "#18181b", "new": False},
    {"id": "tr-5", "art": "/static/img/discover/tr-5.jpg", "title": "Chrome Hearts", "artist": "Kilo Byte", "artist_id": "kilo-byte", "genre": "Electronic", "mood": "energetic", "plays": 410000, "from": "#0e7490", "to": "#0f172a", "new": True},
    {"id": "tr-6", "art": "/static/img/discover/tr-6.jpg", "title": "Glass Horizon", "artist": "Grid Runner", "artist_id": "grid-runner", "genre": "Synthwave", "mood": "focus", "plays": 220000, "from": "#064e3b", "to": "#0c0a09", "new": True},
    {"id": "tr-7", "art": "/static/img/discover/tr-7.jpg", "title": "Velvet Static", "artist": "Sable Wynn", "artist_id": "sable-wynn", "genre": "R&B", "mood": "chill", "plays": 175000, "from": "#3b0764", "to": "#111827", "new": False},
    {"id": "tr-8", "art": "/static/img/discover/tr-8.jpg", "title": "City Lights", "artist": "Nova Reign", "artist_id": "nova-reign", "genre": "Pop", "mood": "feel-good", "plays": 1250000, "from": "#a16207", "to": "#7c2d12", "new": False},
    {"id": "tr-9", "art": "/static/img/discover/tr-9.jpg", "title": "Deep Current", "artist": "Marco Velocity", "artist_id": "marco-velocity", "genre": "House", "mood": "chill", "plays": 320000, "from": "#155e75", "to": "#0f172a", "new": True},
    {"id": "tr-10", "title": "Paper Planes", "artist": "Lila Rose", "artist_id": "lila-rose", "genre": "Pop", "mood": "feel-good", "plays": 88000, "from": "#b45309", "to": "#7c2d12", "new": True},
    {"id": "tr-11", "title": "Low Tide", "artist": "Cass Oram", "artist_id": "cass-oram", "genre": "Ambient", "mood": "focus", "plays": 54000, "from": "#0f766e", "to": "#0c0a09", "new": False},
    {"id": "tr-12", "title": "Backstreet Gold", "artist": "Milo Tran", "artist_id": "milo-tran", "genre": "Hip-Hop", "mood": "energetic", "plays": 210000, "from": "#7c2d12", "to": "#18181b", "new": True},
]

# Likes and follows are NOT held here.
#
# They were: two module-level sets, `_likes` and `_follows`, with no user
# key. One process serves every account, so one visitor's like rendered
# as everybody's - account A liked tr-1 and account B's page drew the
# heart filled. The page has always said "Likes & follows save for your
# session"; the caller now passes the session's own sets in, which makes
# that sentence true instead of aspirational.
#
# The functions below mutate the set they are handed and never reach for
# state of their own. That is the whole guard: there is nothing module
# level left to share.


def like_track(track_id, likes):
    if not any(t["id"] == track_id for t in _TRACKS):
        return None
    if track_id in likes:
        likes.discard(track_id)
        return {"liked": False, "count": len(likes)}
    likes.add(track_id)
    return {"liked": True, "count": len(likes)}


def sample_artist_ids():
    """The artist ids the sample feed can offer a follow button for."""
    return {t["artist_id"] for t in _TRACKS}


def follow_artist(artist_id, follows):
    # like_track has always refused an id it does not know; this one took
    # any string at all, so POST /discover/follow/beyonce answered
    # {"following": true} and the caller had been told a relationship
    # existed. It refuses the same way now, and the route above it
    # refuses every account that is not a showcase session.
    if artist_id not in sample_artist_ids():
        return None
    if artist_id in follows:
        follows.discard(artist_id)
        return {"following": False, "count": len(follows)}
    follows.add(artist_id)
    return {"following": True, "count": len(follows)}


def _fmt_plays(n):
    if n >= 1_000_000:
        return ("%.1fM" % (n / 1_000_000)).replace(".0M", "M")
    if n >= 1_000:
        return "%dK" % (n / 1_000)
    return str(n)


def _decorate_track(t, likes):
    return {**t, "liked": t["id"] in likes, "plays_fmt": _fmt_plays(t["plays"])}


def _nothing_to_show():
    """The same shape, carrying nothing.

    The caller keys off `showcase`; every list is empty so a template
    that forgets the flag still cannot print an invented name. Returned
    by default, which is the point: a new caller that says nothing about
    the session gets the honest answer, not the showcase one.
    """
    return {
        "showcase": False,
        "genres": [],
        "moods": [],
        "tracks": [],
        "new_releases": [],
        "spotlights": [],
        "filters": {"genre": "All", "mood": "All"},
        "summary": {"tracks": 0, "genres": 0, "new": 0, "likes": 0, "follows": 0},
        "result_count": 0,
    }


def get_discover_data(args=None, likes=None, follows=None, showcase=False):
    """The browse feed. Invented, so showcase sessions only.

    THE SEAM FOR A REAL FEED, since this is where it lands.

    Nothing here is started and nothing here is half-built; the owner has
    not made the calls it needs. When he does, the shape is already cut:

      * A real source fills `tracks`, `new_releases` and `spotlights`
        with the same keys these rows use (id, title, artist, artist_id,
        genre, mood, plays, art). Soundcharts is the named candidate;
        signal_providers.py already holds the client and
        soundcharts_budget.py the call cap, and data-source policy lives
        in docs/DATA_SOURCES.md. Whatever it returns must carry its own
        provenance, because `plays` is printed as a headline figure and
        the product does not print a figure it cannot source.
      * Street Banker's own artists appear only behind an opt-in. There
        is no such toggle today; it is a per-account setting plus a
        listing read, the same consent shape collab_profiles uses for
        "members who chose to be found".
      * `showcase` then stops meaning "may see invented rows" and starts
        meaning "has no real rows yet", and the guard in app.py
        discover() becomes the /links/fans two-clause form: demo AND
        nothing real to show.
      * Likes and follows move out of the session to a table keyed by
        user_id (app.py _discover_state says the same). Persisting a
        follow against an invented id is what this guard exists to
        prevent, so that move and the real feed are one change, not two.

    Until all of that, showcase=False is the honest answer and the
    default.
    """
    if not showcase:
        return _nothing_to_show()
    args = args or {}
    likes = likes if likes is not None else set()
    follows = follows if follows is not None else set()
    genre = args.get("genre") or "All"
    mood = args.get("mood") or "All"

    tracks = [_decorate_track(t, likes) for t in _TRACKS]
    filtered = tracks
    if genre != "All":
        filtered = [t for t in filtered if t["genre"] == genre]
    if mood != "All":
        filtered = [t for t in filtered if t["mood"] == mood]
    filtered.sort(key=lambda t: t["plays"], reverse=True)

    genre_counts = [{"name": g, "count": sum(1 for t in _TRACKS if t["genre"] == g)} for g in GENRES]
    genre_counts = [g for g in genre_counts if g["count"]]

    new_releases = sorted([t for t in tracks if t["new"]], key=lambda t: t["plays"], reverse=True)

    # Artist spotlights: unique artists in the feed, with follow state.
    seen, spotlights = set(), []
    for t in sorted(tracks, key=lambda t: t["plays"], reverse=True):
        if t["artist_id"] in seen:
            continue
        seen.add(t["artist_id"])
        spotlights.append({"id": t["artist_id"], "name": t["artist"], "genre": t["genre"],
                           "avatar": "/static/img/discover/av-%s.jpg" % t["artist_id"]
                           if os.path.exists(os.path.join("static", "img", "discover",
                                                          "av-%s.jpg" % t["artist_id"])) else None,
                           "following": t["artist_id"] in follows,
                           "initials": "".join(p[0] for p in t["artist"].split()[:2]).upper()})
    spotlights = spotlights[:6]

    return {
        "showcase": True,
        "genres": genre_counts,
        "moods": MOODS,
        "tracks": filtered,
        "new_releases": new_releases[:6],
        "spotlights": spotlights,
        "filters": {"genre": genre, "mood": mood},
        "summary": {
            "tracks": len(_TRACKS),
            "genres": len(genre_counts),
            "new": len(new_releases),
            "likes": len(likes),
            "follows": len(follows),
        },
        "result_count": len(filtered),
    }

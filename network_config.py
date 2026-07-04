"""Config-driven data for the Network hub.

A directory of industry contacts (artists, producers, songwriters, labels,
managers, A&R, engineers, sync supervisors, playlist curators) plus a
Playlists area where curators list playlists that accept track
submissions. Search / role / genre filters and sorting are applied
server-side. Connections, pitches, and submissions are held in
module-level session state (reset on restart) -- illustrative demo data.
"""

ROLES = ["Artist", "Producer", "Songwriter", "Label", "Manager",
         "A&R", "Engineer", "Sync Supervisor", "Playlist Curator"]

GENRES = ["Synthwave", "Electronic", "House", "Techno", "Pop",
          "Hip-Hop", "R&B", "Indie", "Ambient"]

SORTS = [
    {"id": "followers", "label": "Most followers"},
    {"id": "name", "label": "Name (A–Z)"},
    {"id": "available", "label": "Available first"},
]


def _initials(name):
    parts = [p for p in name.replace("&", " ").split() if p]
    return ("".join(p[0] for p in parts[:2]) or "?").upper()


# --- Directory ---------------------------------------------------------------
_PROFILES = [
    {"id": "nova-reign", "name": "Nova Reign", "role": "Artist", "genres": ["Synthwave", "Pop"],
     "location": "Los Angeles, CA", "followers": 128000, "verified": True, "available": True,
     "tagline": "Synth-pop for night drives.", "credits": ["'Midnight Tape' (2M streams)", "Toured with Lumen"],
     "rate": None, "links": [{"label": "Spotify", "url": "https://spotify.com"}]},
    {"id": "kilo-byte", "name": "Kilo Byte", "role": "Producer", "genres": ["Electronic", "House"],
     "location": "Berlin, DE", "followers": 54000, "verified": True, "available": True,
     "tagline": "Punchy mixes, fast turnarounds.", "credits": ["Mixed 40+ indie EPs", "Grammy-considered 2024"],
     "rate": "$500 / track", "links": []},
    {"id": "marco-velocity", "name": "Marco Velocity", "role": "Producer", "genres": ["House", "Techno"],
     "location": "Miami, FL", "followers": 89000, "verified": False, "available": False,
     "tagline": "Club-ready productions.", "credits": ["Resident, Vault Miami"], "rate": "$750 / track", "links": []},
    {"id": "lila-rose", "name": "Lila Rose", "role": "Songwriter", "genres": ["Pop", "R&B"],
     "location": "Nashville, TN", "followers": 32000, "verified": True, "available": True,
     "tagline": "Toplines & co-writes.", "credits": ["12 cuts placed", "ASCAP member"], "rate": "Split-based", "links": []},
    {"id": "nightdrive-records", "name": "Nightdrive Records", "role": "Label", "genres": ["Synthwave", "Indie"],
     "location": "London, UK", "followers": 410000, "verified": True, "available": True,
     "tagline": "Independent synth & indie label.", "credits": ["30-artist roster", "Distributed worldwide"],
     "rate": None, "links": [{"label": "Site", "url": "https://example.com"}]},
    {"id": "dj-codec", "name": "DJ Codec", "role": "Artist", "genres": ["Techno"],
     "location": "Detroit, MI", "followers": 76000, "verified": False, "available": True,
     "tagline": "Warehouse techno.", "credits": ["Boiler Room set"], "rate": None, "links": []},
    {"id": "sasha-quill", "name": "Sasha Quill", "role": "Manager", "genres": ["Pop", "Electronic"],
     "location": "Los Angeles, CA", "followers": 21000, "verified": True, "available": True,
     "tagline": "Artist manager & strategist.", "credits": ["Managed 2 gold records"], "rate": "Commission", "links": []},
    {"id": "reed-mensah", "name": "Reed Mensah", "role": "A&R", "genres": ["Hip-Hop", "R&B"],
     "location": "Atlanta, GA", "followers": 44000, "verified": True, "available": True,
     "tagline": "Scouting the next wave.", "credits": ["Signed 6 breakout acts"], "rate": None, "links": []},
    {"id": "vera-sound", "name": "Vera Sound", "role": "Engineer", "genres": ["Pop", "Indie"],
     "location": "New York, NY", "followers": 18000, "verified": False, "available": True,
     "tagline": "Mastering & mix engineer.", "credits": ["Mastered 200+ releases"], "rate": "$120 / master", "links": []},
    {"id": "atlas-sync", "name": "Atlas Sync", "role": "Sync Supervisor", "genres": ["Electronic", "Ambient"],
     "location": "Los Angeles, CA", "followers": 15000, "verified": True, "available": True,
     "tagline": "Placing music in film, TV & ads.", "credits": ["Placements on 3 networks"], "rate": None, "links": []},
    {"id": "echo-lin", "name": "Echo Lin", "role": "Playlist Curator", "genres": ["Synthwave", "Electronic"],
     "location": "Toronto, CA", "followers": 240000, "verified": True, "available": True,
     "tagline": "Curator — late-night electronic.", "credits": ["3 flagship playlists"], "rate": None,
     "links": [], "playlists": ["late-night-synth", "neon-circuit"]},
    {"id": "harper-vale", "name": "Harper Vale", "role": "Playlist Curator", "genres": ["Indie", "Pop"],
     "location": "London, UK", "followers": 180000, "verified": True, "available": True,
     "tagline": "Indie discovery weekly.", "credits": ["Editorial contributor"], "rate": None,
     "links": [], "playlists": ["indie-rising", "chill-drive"]},
    {"id": "milo-tran", "name": "Milo Tran", "role": "Producer", "genres": ["Hip-Hop"],
     "location": "Toronto, CA", "followers": 61000, "verified": False, "available": True,
     "tagline": "Boom-bap & trap beats.", "credits": ["Placed with indie rappers"], "rate": "$400 / beat", "links": []},
    {"id": "jade-okoro", "name": "Jade Okoro", "role": "Songwriter", "genres": ["R&B", "Pop"],
     "location": "Atlanta, GA", "followers": 27000, "verified": True, "available": False,
     "tagline": "Soulful toplines.", "credits": ["8 cuts placed"], "rate": "Split-based", "links": []},
    {"id": "prism-collective", "name": "Prism Collective", "role": "Label", "genres": ["House", "Techno"],
     "location": "Berlin, DE", "followers": 320000, "verified": True, "available": True,
     "tagline": "Electronic label & agency.", "credits": ["20-artist roster"], "rate": None, "links": []},
    {"id": "theo-park", "name": "Theo Park", "role": "Manager", "genres": ["Hip-Hop", "R&B"],
     "location": "New York, NY", "followers": 19000, "verified": False, "available": True,
     "tagline": "Day-to-day artist management.", "credits": ["Booked 40+ shows"], "rate": "Commission", "links": []},
    {"id": "sable-wynn", "name": "Sable Wynn", "role": "Artist", "genres": ["R&B", "Indie"],
     "location": "Los Angeles, CA", "followers": 95000, "verified": True, "available": True,
     "tagline": "Alt-R&B singer-songwriter.", "credits": ["Sync in 2 ad campaigns"], "rate": None, "links": []},
    {"id": "grid-runner", "name": "Grid Runner", "role": "Artist", "genres": ["Synthwave"],
     "location": "Berlin, DE", "followers": 52000, "verified": False, "available": True,
     "tagline": "Retro-futurist producer/artist.", "credits": ["2 self-released albums"], "rate": None, "links": []},
    {"id": "cass-oram", "name": "Cass Oram", "role": "Engineer", "genres": ["Ambient", "Electronic"],
     "location": "London, UK", "followers": 12000, "verified": False, "available": True,
     "tagline": "Atmospheric mixing & sound design.", "credits": ["Film score work"], "rate": "$140 / mix", "links": []},
    {"id": "juno-fields", "name": "Juno Fields", "role": "Playlist Curator", "genres": ["Ambient", "Indie"],
     "location": "Portland, OR", "followers": 88000, "verified": False, "available": True,
     "tagline": "Focus & ambient sounds.", "credits": ["Fast-growing curator"], "rate": None,
     "links": [], "playlists": ["deep-focus"]},
    {"id": "rico-santana", "name": "Rico Santana", "role": "A&R", "genres": ["Hip-Hop"],
     "location": "Miami, FL", "followers": 33000, "verified": True, "available": False,
     "tagline": "Label A&R, Latin & hip-hop.", "credits": ["Signed 4 acts"], "rate": None, "links": []},
    {"id": "wren-adler", "name": "Wren Adler", "role": "Sync Supervisor", "genres": ["Indie", "Pop"],
     "location": "New York, NY", "followers": 9000, "verified": False, "available": True,
     "tagline": "Ad & trailer music supervisor.", "credits": ["Trailer placements"], "rate": None, "links": []},
]

# --- Playlists (accept submissions) -----------------------------------------
_PLAYLISTS = [
    {"id": "late-night-synth", "name": "Late Night Synth", "curator_id": "echo-lin",
     "followers": 842000, "genres": ["Synthwave", "Electronic"], "mood": "Nocturnal · Driving",
     "accepting": True, "description": "Dark, cinematic synth for after-hours."},
    {"id": "neon-circuit", "name": "Neon Circuit", "curator_id": "echo-lin",
     "followers": 305000, "genres": ["Electronic", "House"], "mood": "Energetic · Bright",
     "accepting": True, "description": "Upbeat electronic and future-pop."},
    {"id": "indie-rising", "name": "Indie Rising", "curator_id": "harper-vale",
     "followers": 512000, "genres": ["Indie", "Pop"], "mood": "Fresh · Melodic",
     "accepting": True, "description": "New indie discovery, updated weekly."},
    {"id": "chill-drive", "name": "Chill Drive", "curator_id": "harper-vale",
     "followers": 96000, "genres": ["Indie", "Synthwave"], "mood": "Mellow · Warm",
     "accepting": False, "description": "Laid-back tracks for the open road."},
    {"id": "deep-focus", "name": "Deep Focus", "curator_id": "juno-fields",
     "followers": 431000, "genres": ["Ambient", "Electronic"], "mood": "Calm · Minimal",
     "accepting": True, "description": "Ambient beds for work and study."},
]

# --- Session state (resets on restart) --------------------------------------
_connections = {}   # profile_id -> status ("Pending" | "Connected")
_pitches = []       # {profile_id, message, song}
_submissions = []   # {playlist_id, song, message, status}


def reset_network_state():
    _connections.clear()
    _pitches.clear()
    _submissions.clear()


def _decorate(p):
    return {**p, "initials": _initials(p["name"]),
            "connection": _connections.get(p["id"]),
            "playlist_count": len(p.get("playlists", []))}


def get_profile(profile_id):
    p = next((x for x in _PROFILES if x["id"] == profile_id), None)
    if p is None:
        return None
    prof = _decorate(p)
    prof["playlists_full"] = [_decorate_playlist(pl) for pl in _PLAYLISTS if pl["curator_id"] == p["id"]]
    return prof


def _decorate_playlist(pl):
    curator = next((x for x in _PROFILES if x["id"] == pl["curator_id"]), None)
    submitted = any(s["playlist_id"] == pl["id"] for s in _submissions)
    return {**pl, "curator_name": curator["name"] if curator else "—", "submitted": submitted}


def get_playlist(playlist_id):
    pl = next((x for x in _PLAYLISTS if x["id"] == playlist_id), None)
    return _decorate_playlist(pl) if pl else None


def connect(profile_id):
    if not any(x["id"] == profile_id for x in _PROFILES):
        return None
    _connections[profile_id] = "Pending"
    return _connections[profile_id]


def pitch(profile_id, message, song):
    if not any(x["id"] == profile_id for x in _PROFILES):
        return None
    entry = {"profile_id": profile_id, "message": (message or "").strip(), "song": (song or "").strip()}
    _pitches.append(entry)
    return entry


def submit_to_playlist(playlist_id, song, message):
    pl = next((x for x in _PLAYLISTS if x["id"] == playlist_id), None)
    if pl is None or not pl["accepting"] or not (song or "").strip():
        return None
    entry = {"playlist_id": playlist_id, "song": song.strip(),
             "message": (message or "").strip(), "status": "Submitted"}
    _submissions.append(entry)
    return entry


def get_network_data(args=None):
    args = args or {}
    q = (args.get("q") or "").strip().lower()
    role = args.get("role") or "All"
    genre = args.get("genre") or "All"
    sort = args.get("sort") or "followers"
    tab = args.get("tab") or "directory"

    people = [_decorate(p) for p in _PROFILES]
    if role != "All":
        people = [p for p in people if p["role"] == role]
    if genre != "All":
        people = [p for p in people if genre in p["genres"]]
    if q:
        people = [p for p in people if q in " ".join(
            [p["name"], p["role"], p["location"], p["tagline"], " ".join(p["genres"])]).lower()]

    if sort == "name":
        people.sort(key=lambda p: p["name"].lower())
    elif sort == "available":
        people.sort(key=lambda p: (not p["available"], -p["followers"]))
    else:
        people.sort(key=lambda p: p["followers"], reverse=True)

    connected_ids = set(_connections)
    my_connections = [_decorate(p) for p in _PROFILES if p["id"] in connected_ids]

    return {
        "summary": {
            "total": len(_PROFILES),
            "roles": len({p["role"] for p in _PROFILES}),
            "playlists": len(_PLAYLISTS),
            "accepting": sum(1 for pl in _PLAYLISTS if pl["accepting"]),
            "connections": len(_connections),
        },
        "tab": tab,
        "people": people,
        "playlists": [_decorate_playlist(pl) for pl in _PLAYLISTS],
        "my_connections": my_connections,
        "pitches": [{**pt, "name": next((x["name"] for x in _PROFILES if x["id"] == pt["profile_id"]), pt["profile_id"])} for pt in _pitches],
        "submissions": [{**s, "playlist_name": next((x["name"] for x in _PLAYLISTS if x["id"] == s["playlist_id"]), s["playlist_id"])} for s in _submissions],
        "roles": ["All"] + ROLES,
        "genres": ["All"] + GENRES,
        "sorts": SORTS,
        "filters": {"q": args.get("q") or "", "role": role, "genre": genre, "sort": sort},
        "result_count": len(people),
    }

"""Config-driven data for the community / artist-interaction cluster:
Feature Marketplace, Network directory, Fan Label, and Fan Dashboard.

All of this is illustrative demo data — the app has no real social graph
or fan payments. The Fan Label is a community voting/visualisation demo:
no real money is contributed or moved.
"""

from royalty_data import get_songs

# ---- Feature Marketplace ----------------------------------------------------

DEAL_TONE = {
    "For Bid": "border-amber-500/20 bg-amber-500/10 text-amber-400",
    "Royalty Split": "border-blue-500/20 bg-blue-500/10 text-blue-400",
    "For Fun": "border-green-500/20 bg-green-500/10 text-green-400",
}
DEAL_TYPES = ["For Bid", "Royalty Split", "For Fun"]

_marketplace_seeded = False
_requests = []
_req_seq = 0


def _seed_requests():
    return [
        {"id": "mkt-1", "artist": "Nova Reign", "need": "Vocalist", "genre": "Synthwave",
         "deal_type": "Royalty Split", "detail": "Looking for an airy topline for a late-night driver."},
        {"id": "mkt-2", "artist": "Kilo Byte", "need": "Producer", "genre": "Electronic",
         "deal_type": "For Bid", "detail": "Need a punchy mix + master for a 3-track EP."},
        {"id": "mkt-3", "artist": "Lila Rose", "need": "Songwriter", "genre": "Pop",
         "deal_type": "For Fun", "detail": "Co-write session, just vibes — no strings."},
    ]


def _ensure_marketplace():
    global _requests, _req_seq, _marketplace_seeded
    if not _marketplace_seeded:
        _requests = _seed_requests()
        _req_seq = len(_requests)
        _marketplace_seeded = True


def reset_marketplace_state():
    global _marketplace_seeded
    _marketplace_seeded = False
    _ensure_marketplace()


def post_request(artist, need, genre, deal_type, detail):
    _ensure_marketplace()
    global _req_seq
    if not artist or not need or deal_type not in DEAL_TYPES:
        return None
    _req_seq += 1
    req = {"id": "mkt-%d" % _req_seq, "artist": artist.strip(), "need": need.strip(),
           "genre": (genre or "").strip() or "Any", "deal_type": deal_type, "detail": (detail or "").strip()}
    _requests.insert(0, req)
    return {**req, "deal_tone": DEAL_TONE.get(deal_type, "")}


def get_marketplace_data():
    _ensure_marketplace()
    reqs = [{**r, "deal_tone": DEAL_TONE.get(r["deal_type"], "")} for r in _requests]
    return {
        "summary": {"open_requests": len(reqs), "deal_types": len(DEAL_TYPES)},
        "requests": reqs,
        "deal_types": DEAL_TYPES,
    }


# ---- Network moved to network_config.py (rich directory + playlists) --------


# ---- Fan Label --------------------------------------------------------------

# The three demos and their placeholder vote counts. A constant: `_demos`
# was a module-level list whose counts were incremented in place, so one
# visitor's vote raised the number every other account saw, and the
# tally drifted away from the seed for the life of the process.
#
# The counts are invented (docs/PARKED_PAGES.md says so, and the page
# says so twice), which is exactly why they must not accumulate: a made
# up number that moves looks like a measured one.
_DEMOS = (
    {"id": "demo-1", "art": "/static/img/fanlabel/midnight-tape.jpg", "title": "Midnight Tape", "artist": "Nova Reign", "votes": 214},
    {"id": "demo-2", "art": "/static/img/fanlabel/chrome-hearts.jpg", "title": "Chrome Hearts", "artist": "Kilo Byte", "votes": 158},
    {"id": "demo-3", "art": "/static/img/fanlabel/afterglow.jpg", "title": "Afterglow", "artist": "Lila Rose", "votes": 97},
)


def vote_demo(demo_id, voted):
    """Record this visitor's vote and return the count they now see.

    Idempotent: a second press is still one vote, rather than a counter
    somebody can run up. `voted` is the caller's own set of demo ids.
    """
    d = next((x for x in _DEMOS if x["id"] == demo_id), None)
    if d is None:
        return None
    voted.add(demo_id)
    return d["votes"] + 1


def get_fan_label_data(voted=None):
    """Fan Label demonstration data.

    There is no fan-fund table behind this yet - no campaign to create,
    no backer to record, no money that moves. Every figure below is
    invented, so the page must say so. `is_sample` is what makes it say
    so; do not drop it when the real fund lands, flip it to False only
    once these numbers come from actual backers.
    """
    voted = voted if voted is not None else set()
    raised = 18400
    goal = 25000
    milestones = [
        {"label": "Studio session funded", "amount": 5000, "unlocked": True},
        {"label": "Vinyl pressing", "amount": 12000, "unlocked": True},
        {"label": "Showcase event", "amount": 20000, "unlocked": False},
        {"label": "Tour support", "amount": 25000, "unlocked": False},
    ]
    demos = sorted(
        ({**d, "votes": d["votes"] + (1 if d["id"] in voted else 0),
          "voted": d["id"] in voted} for d in _DEMOS),
        key=lambda d: d["votes"], reverse=True)
    return {
        "is_sample": True,
        "raised": raised,
        "goal": goal,
        "pct": round(raised / goal * 100),
        "backers": 342,
        "milestones": milestones,
        "demos": demos,
    }


# ---- Fan Dashboard ----------------------------------------------------------

def get_fan_dashboard_data():
    segments = [
        {"segment": "Superfans", "count": 1240, "ltv": 84.0, "merch": 55, "tickets": 30, "digital": 15},
        {"segment": "Engaged", "count": 8600, "ltv": 22.0, "merch": 35, "tickets": 20, "digital": 45},
        {"segment": "Casual", "count": 41000, "ltv": 4.5, "merch": 15, "tickets": 5, "digital": 80},
    ]
    leaderboard = [
        {"fan": "vinylhoarder", "spend": 412.0, "tier": "Superfan"},
        {"fan": "synthkid_92", "spend": 288.5, "tier": "Superfan"},
        {"fan": "nightdriver", "spend": 190.0, "tier": "Engaged"},
        {"fan": "mixtape_mary", "spend": 145.0, "tier": "Engaged"},
        {"fan": "echo_and_i", "spend": 98.0, "tier": "Engaged"},
    ]
    total_fans = sum(s["count"] for s in segments)
    return {
        "summary": {
            "superfans": segments[0]["count"],
            "total_fans": total_fans,
            "follower_growth": 230,
            "avg_ltv": round(sum(s["ltv"] * s["count"] for s in segments) / total_fans, 2),
        },
        "segments": segments,
        "leaderboard": leaderboard,
    }

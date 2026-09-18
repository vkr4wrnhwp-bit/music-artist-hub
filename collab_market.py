"""The Collab Marketplace screen, read into one shape for the template.

Approved design: static/_mock_collab.html (owner, 2026-09-18). The page
is the owner's layout; everything on it comes from the collab tables for
the signed-in account:

  * tiles        - four real counts (open briefs, my briefs, applications
                   I sent, saved briefs still open). The mock's "New
                   Matches" tile is dropped: there is no matching engine,
                   and a tile with no source is an invented number.
  * recommended  - open briefs from other members that ask for a role you
                   have applied as, or sit in a genre you post in. Both
                   rules are stated on the card. No basis, no cards.
  * pipeline     - the stages this board actually records (posted,
                   applications, closed). Agreement, production and
                   delivery are not tracked here and say so.
  * trust        - the account's own Trust Score factors, the number that
                   sits beside its name on every brief it posts.

The demo account alone may see a showcase of example collaborators, each
card labelled as one. A real account never does.
"""
from datetime import date

# Decoration for a brief card: the ROLE the brief asks for, never the
# person who posted it. Named here, not built from a loop variable in the
# template (tests/test_image_slots.py).
ROLE_PHOTOS = {
    "Vocalist": "/static/img/collab-role-vocalist.webp",
    "Producer": "/static/img/collab-role-producer.webp",
    "Songwriter": "/static/img/collab-role-songwriter.webp",
    "Mixing / Mastering": "/static/img/collab-role-mixing.webp",
    "Instrumentalist": "/static/img/collab-role-instrumentalist.webp",
    "Visuals / Cover Art": "/static/img/collab-role-visuals.webp",
}
DEFAULT_PHOTO = "/static/img/collab-role-producer.webp"

KIND_LABELS = {"bid": "Paid", "split": "Royalty split", "fun": "For fun"}
# Each deal type keeps its own chip, as in the mock: Paid is gold, a
# royalty split is the amber warn chip, For fun is the neutral chip.
KIND_CHIPS = {"bid": "gold", "split": "warn", "fun": ""}

# One decorative icon per trust factor (the mock's .hl svg). Pure
# decoration, no data claim; SVG path data only, drawn in ink-3.
TRUST_ICONS = {
    "Metadata coverage": '<path d="M4 5h12M4 10h12M4 15h8"/>',
    "Splits documented": '<path d="M5 3h7l3 3v11H5z"/><path d="M12 3v3h3"/>',
    "Statements connected": '<rect x="4" y="3" width="12" height="14" rx="2"/><path d="M7 7.5h6M7 10.5h6M7 13.5h3"/>',
    "Fan data consented": '<circle cx="7.8" cy="6.8" r="2.7"/><path d="M3 16.2c0-2.7 2.1-4.5 4.8-4.5s4.8 1.8 4.8 4.5"/>',
    "Release readiness": '<path d="M4 10.5l4 4 8-9"/>',
    "Sync clearance": '<path d="M10 2.6l6 2.4v4.2c0 4.3-6 8.2-6 8.2s-6-3.9-6-8.2V5z"/>',
    "Press kit complete": '<rect x="3" y="4.4" width="14" height="12.6" rx="2"/><path d="M3 8.4h14"/>',
    "Deal hygiene": '<path d="M10 3v14M13.2 6.2H8.4a2.1 2.1 0 000 4.2h3.2a2.1 2.1 0 010 4.2H6.4"/>',
    "Promo attribution": '<path d="M4 8v4h3l5 3V5L7 8H4z"/>',
    "Catalog depth": '<path d="M7 15V4l9-1.6V14"/><circle cx="5" cy="15.5" r="2.3"/><circle cx="14" cy="14" r="2.3"/>',
    "Verified platform presence": '<circle cx="10" cy="10" r="7.2"/><path d="M2.9 10h14.2M10 2.9c3.6 3.8 3.6 10.4 0 14.2-3.6-3.8-3.6-10.4 0-14.2z"/>',
}
DEFAULT_TRUST_ICON = '<circle cx="10" cy="10" r="7.2"/>'

TABS = [
    ("discover", "Discover", "/marketplace"),
    ("briefs", "My Briefs", "/marketplace?tab=briefs"),
    ("applications", "Applications", "/marketplace?tab=applications"),
    ("projects", "Active Projects", "/marketplace?tab=projects"),
    # Network is the account's real outreach pipeline. /network itself is
    # PARKED (sample directory profiles, docs/PARKED_PAGES.md) and nothing
    # may link to it; its real tracker moved to /tour-board/outreach.
    ("network", "Network", "/tour-board/outreach"),
]

# Demo account only. Example collaborators from the approved mock, shown
# under a Showcase label. Never rendered for a real account.
SHOWCASE = [
    {"name": "Maya Chen", "role": "Mix Engineer", "where": "Los Angeles, CA",
     "tags": ["Hip Hop", "R&B", "Pop"], "credits": "100+ releases",
     "rate": "$150-$400", "per": "per track", "avail": "Next 2 weeks",
     "match": "92% match", "photo": "/static/img/collab-role-mixing.webp"},
    {"name": "Darius Cole", "role": "Producer", "where": "Atlanta, GA",
     "tags": ["Hip Hop", "Trap", "R&B"], "credits": "60+ placements",
     "rate": "$500-$2,500", "per": "per track", "avail": "This month",
     "match": "88% match", "photo": "/static/img/collab-role-producer.webp"},
    {"name": "Nia Brooks", "role": "Visual Director", "where": "New York, NY",
     "tags": ["Music Video", "Photography"], "credits": "40+ videos",
     "rate": "$1,000-$5,000", "per": "per project", "avail": "Next month",
     "match": "84% match", "photo": "/static/img/collab-role-visuals.webp"},
]


def initials(name):
    parts = [p for p in (name or "").replace(".", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
          "Oct", "Nov", "Dec")


def short_date(iso, today):
    """'Oct 2' for a date this year, 'Oct 2, 2027' otherwise; '' if none."""
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return iso[:10]
    label = "%s %d" % (MONTHS[d.month - 1], d.day)
    return label if d.year == today.year else "%s, %d" % (label, d.year)


def brief_state(brief, today):
    """One effective status for a brief, used everywhere it is labelled.

    'closed' when its poster closed it; 'expired' when it is still open in
    the table but its closing date has passed (the board and the tiles
    already leave those out); otherwise 'open'.
    """
    if brief.get("status") == "closed":
        return "closed"
    closes = (brief.get("closes") or "")[:10]
    if closes and closes < today.isoformat():
        return "expired"
    return "open"


STATE_LABELS = {"open": "Open", "expired": "Closing date passed",
                "closed": "Closed"}


def trust_label(total, measured):
    """What sits beside a poster's name: the score, or that there is none.

    A total of 0 with nothing on record is not a measurement.
    """
    return "Trust %d" % total if measured else "Trust not scored"


def days_left(closes, today):
    """Whole days until a closing date, or None when there is none."""
    if not closes:
        return None
    try:
        return (date.fromisoformat(closes[:10]) - today).days
    except ValueError:
        return None


def pipeline(brief, replies, today):
    """The stages of one of the account's own briefs.

    Only what the board records is marked done. The rest are real stages
    of a collaboration that this page does not track, and each says so
    rather than drawing a progress bar nobody measured.
    """
    posted = short_date(brief.get("created"), today)
    first = short_date(replies[0]["created"], today) if replies else ""
    state = brief_state(brief, today)
    ended = state != "open"
    steps = [
        {"name": "Brief", "state": "done", "note": posted},
        {"name": "Applications",
         "state": "done" if replies else "now",
         "note": ("%d received" % len(replies)) if replies else "Waiting for the first"},
        {"name": "Closing",
         "state": "done" if ended else ("now" if replies else "todo"),
         "note": STATE_LABELS[state] if ended else "Still open"},
        {"name": "Agreement", "state": "todo", "note": "In the Deal Room",
         "href": "/deal-room"},
        {"name": "Production", "state": "todo", "note": "Not tracked here"},
        {"name": "Delivery", "state": "todo", "note": "Not tracked here"},
    ]
    return {"brief": brief, "steps": steps, "applications": len(replies),
            "photo": ROLE_PHOTOS.get(brief.get("role"), DEFAULT_PHOTO),
            "state": state, "state_label": STATE_LABELS[state],
            "first_application": first}


def recommendations(board, user_id, own, sent):
    """Open briefs by other members that match something the account did.

    Two rules, both explainable on the card:
      role  - the brief asks for a role this account has applied as;
      genre - the brief is in a genre this account has posted in.
    Returns (cards, basis) where basis lists what the account's record
    offered to match on; an empty basis means there is nothing to go on.
    """
    roles = {a["role"] for a in sent if a.get("role")}
    genres = {(b.get("genre") or "").strip().lower() for b in own}
    genres.discard("")
    applied_to = {a["request_id"] for a in sent}
    cards = []
    for r in board:
        if r["user_id"] == user_id or r["id"] in applied_to:
            continue
        why = []
        if r["role"] in roles:
            why.append("You have applied as a %s" % r["role"])
        if (r.get("genre") or "").strip().lower() in genres:
            why.append("You post %s briefs" % r["genre"])
        if why:
            cards.append(dict(r, why=why))
    basis = sorted(roles) + sorted(g.title() for g in genres)
    return cards[:3], basis


TABLE_ROWS = 100


def safe_back(value, default="/marketplace"):
    """Where a save or apply form returns to: the view it was sent from.

    Only a path on this screen is accepted (as _outreach_back does for the
    outreach forms); anything else, including another host, falls back.
    """
    v = (value or "").strip()
    if (v.startswith("/marketplace") and not v.startswith("//")
            and not any(ch in v for ch in ("\\", "\r", "\n"))
            and (len(v) == len("/marketplace") or v[len("/marketplace")] in "?#/")):
        return v
    return default


def with_flag(url, flag):
    """Add a query flag (e.g. applied=1) ahead of any #fragment."""
    base, _, frag = url.partition("#")
    base += ("&" if "?" in base else "?") + flag
    return base + ("#" + frag if frag else "")

"""The Collab Marketplace screen, read into one shape for the template.

Approved design: static/_mock_collab.html (owner, 2026-09-18). The page
is the owner's layout; everything on it comes from the collab tables for
the signed-in account:

  * tiles        - real counts (open briefs, my briefs, applications I
                   sent, saved briefs still open), plus "New Matches" and
                   "Active Projects" from collaborator profiles
                   (PROFILES-SPEC.md). Each of those two is shown only
                   when its source exists for this account.
  * recommended  - listed collaborators, best match first, each match %
                   with the rules that produced it; when nobody is listed
                   yet, open briefs on a stated basis (a role you applied
                   as, a genre you post in); when neither, an honest empty
                   state that invites the viewer to list themselves.
  * pipeline     - the stages this board actually records (posted,
                   applications, closed). Agreement, production and
                   delivery are not tracked here and say so.
  * trust        - the account's own Trust Score factors, the number that
                   sits beside its name on every brief it posts.

Opt-in is the privacy line: a member who has not switched "List me in the
marketplace" on is never shown, matched, counted or listed. db.py hands
out a profile to anyone but its owner only through the listed = 1 reads.

The demo account alone may see a showcase of example collaborators, each
card labelled as one. A real account never does.
"""
import re
from datetime import date, timedelta

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


# --- Collaborator profiles (PROFILES-SPEC.md, owner-approved 2026-09-18) -------

# The one role vocabulary: briefs ask for these, profiles offer these.
ROLES = ["Vocalist", "Producer", "Songwriter", "Mixing / Mastering",
         "Instrumentalist", "Visuals / Cover Art"]
RATE_UNITS = {"per track": "per track", "per project": "per project",
              "per hour": "per hour"}
CURRENCIES = {"USD": "$", "GBP": "£", "EUR": "€", "CAD": "CA$"}
AVAILABILITY = {"available": "Available now", "from": "Available from",
                "booked": "Booked"}
MAX_GENRES = 6
MAX_LINKS = 3

# Match weights, out of what the BRIEF states. The brief sets the rules: a
# rule the brief does not state (no genre, no place, no budget) is left out
# of the sum. A rule the brief states and the profile leaves unanswered is
# counted and not earned, so saying less never scores more (review of
# 2026-09-18: a bare profile used to score 100% and outrank a full one).
# Availability is always asked: every brief wants someone free to do it.
MATCH_WEIGHTS = {"role": 40, "genre": 25, "location": 15,
                 "availability": 10, "budget": 10}
SELF_WEIGHTS = {"genre": 60, "location": 20, "availability": 20}
# "New Matches" counts listed profiles at or above this against one of the
# viewer's open briefs. Stated on the tile.
MATCH_THRESHOLD = 60

BUDGET_BANDS = (("u500", "Under $500", 0, 499),
                ("500-2000", "$500 to $2,000", 500, 2000),
                ("2000up", "$2,000 and up", 2000, None))


# What a money field accepts: an optional currency sign, a whole amount
# (plain digits or with thousands commas), optional cents, and an optional
# "k" for thousands. Anything else is refused with a message, never
# reduced to its digits: "150-400" is not 150,400 and "2k" is not 2.
_MONEY_RE = re.compile(
    r"^\s*[$£€]?\s*(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?\s*([kK])?\s*$")
MONEY_MAX = 10000000
# The same rule for the browser, so a typo is caught before the form is sent
# and nothing typed is lost (the server checks again either way).
MONEY_PATTERN = r"\s*[$£€]?\s*(\d{1,3}(,\d{3})+|\d+)(\.\d{1,2})?\s*[kK]?\s*"


def read_money(value):
    """(amount, ok) from what someone typed. ("", True) reads as
    (None, True): left blank is unstated, not an error. A value the rule
    above does not accept is (None, False)."""
    v = (value or "").strip()
    if not v:
        return None, True
    m = _MONEY_RE.match(v)
    if not m:
        return None, False
    whole, cents, k = m.group(1), m.group(2) or "", m.group(3)
    amount = float(whole.replace(",", "") + cents)
    if k:
        amount *= 1000
    n = int(round(amount))
    if n > MONEY_MAX:
        return None, False
    return n, True


def parse_money(value):
    """A whole-number amount from what someone typed ("$1,500" -> 1500,
    "2k" -> 2000); None when blank or not a plain amount. Never a
    default, never the digits of something else."""
    return read_money(value)[0]


MONEY_HELP = ('Type a plain amount such as 300, $1,500 or 2k. A range goes '
              'in the two boxes, one number in each.')


def read_money_pair(lo_raw, hi_raw, label):
    """Both ends of a range, in order. Returns (lo, hi, errors)."""
    lo, ok_lo = read_money(lo_raw)
    hi, ok_hi = read_money(hi_raw)
    errors = []
    for ok, raw, end in ((ok_lo, lo_raw, "from"), (ok_hi, hi_raw, "up to")):
        if not ok:
            errors.append('%s %s: "%s" is not an amount. %s' % (
                label, end, (raw or "").strip()[:30], MONEY_HELP))
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return lo, hi, errors


def money_range(lo, hi, currency="USD"):
    """"$150–$400" (an en dash, as in the mock), "From $150",
    "Up to $400", or "" when unstated."""
    sym = CURRENCIES.get(currency or "USD", "")
    code = "" if sym else " " + (currency or "")

    def one(n):
        return "%s%s%s" % (sym, "{:,}".format(n), code)
    if lo is not None and hi is not None:
        return one(lo) if lo == hi else "%s–%s" % (one(lo), one(hi))
    if lo is not None:
        return "From " + one(lo)
    if hi is not None:
        return "Up to " + one(hi)
    return ""


def _span(lo, hi):
    """A stated range as (low, high); None when neither end is stated.
    One-sided ranges stay open: "From $150" is (150, infinity) and
    "Up to $500" is (0, 500), never the single point they name."""
    if lo is None and hi is None:
        return None
    return (lo if lo is not None else 0,
            hi if hi is not None else float("inf"))


def _money_words(lo, hi, currency="USD"):
    """money_range for the middle of a sentence ("from $150")."""
    text = money_range(lo, hi, currency)
    return text[0].lower() + text[1:] if text[:4] in ("From", "Up t") else text


def _overlaps(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def place_label(city, country):
    return ", ".join(p for p in ((city or "").strip(), (country or "").strip()) if p)


def clean_profile(form):
    """The edit form, cleaned into the record's fields. Returns
    (fields, errors). Nothing unstated is filled in."""
    errors = []
    roles = [r for r in form.getlist("roles") if r in ROLES]
    seen, genres = set(), []
    for g in (form.get("genres") or "").split(","):
        g = g.strip()[:40]
        if g and g.lower() not in seen:
            seen.add(g.lower())
            genres.append(g)
    genres = genres[:MAX_GENRES]
    lo, hi, money_errors = read_money_pair(form.get("rate_min"),
                                           form.get("rate_max"), "Rate")
    errors.extend(money_errors)
    unit = form.get("rate_unit") if form.get("rate_unit") in RATE_UNITS else ""
    currency = form.get("currency") if form.get("currency") in CURRENCIES else "USD"
    avail = form.get("availability") if form.get("availability") in AVAILABILITY else ""
    avail_from = ""
    if avail == "from":
        try:
            avail_from = date.fromisoformat((form.get("available_from") or "")[:10]).isoformat()
        except ValueError:
            errors.append("Give the date you are available from, or pick another option.")
            avail = ""
    links = []
    for link in form.getlist("links"):
        link = (link or "").strip()[:300]
        if not link:
            continue
        if re.match(r"^https?://[^\s/]+\.[^\s]+$", link):
            links.append(link)
        else:
            errors.append("A link must start with http:// or https:// (%s)." % link[:60])
    listed = form.get("listed") == "1"
    if listed and not roles:
        errors.append("Pick at least one role before listing yourself: the "
                      "marketplace matches people on the role a brief asks for.")
        listed = False
    return {
        "listed": 1 if listed else 0, "roles": roles, "genres": genres,
        "city": (form.get("city") or "").strip()[:60],
        "country": (form.get("country") or "").strip()[:60],
        "remote_ok": 1 if form.get("remote_ok") == "1" else 0,
        "rate_min": lo, "rate_max": hi, "rate_unit": unit, "currency": currency,
        "availability": avail, "available_from": avail_from,
        "credits": (form.get("credits") or "").strip()[:160],
        "links": links[:MAX_LINKS], "bio": (form.get("bio") or "").strip()[:600],
    }, errors


def availability_label(profile, today):
    a = profile.get("availability") or ""
    if a == "from" and profile.get("available_from"):
        if profile["available_from"] <= today.isoformat():
            return "Available now"
        return "From " + short_date(profile["available_from"], today)
    if a in ("available", "booked"):
        return AVAILABILITY[a]
    return "Not stated"


def _available_for(profile, brief, today):
    """(counted, hit, text) for the availability rule. Always counted:
    unstated is not earned."""
    a = profile.get("availability") or ""
    if a == "available":
        return True, True, "Availability: available now"
    if a == "booked":
        return True, False, "Availability: booked"
    if a == "from" and profile.get("available_from"):
        start = profile["available_from"]
        by = ((brief or {}).get("closes") or "")[:10] or (
            today + timedelta(days=30)).isoformat()
        label = short_date(start, today)
        if start <= by:
            return True, True, "Availability: from %s" % label
        return True, False, "Availability: not until %s" % label
    return True, False, "Availability: they have not said, not earned"


def _score(parts, weights):
    """parts: (rule, counted, hit, text). Counted rules make the sum; the
    reasons keep every rule, so the card can say what was left out and
    why."""
    total = sum(weights[k] for k, counted, _h, _t in parts if counted)
    earned = sum(weights[k] for k, counted, hit, _t in parts if counted and hit)
    pct = int(round(100.0 * earned / total)) if total else 0
    reasons = [{"rule": k, "text": t, "hit": bool(counted and hit),
                "counted": bool(counted), "weight": weights[k]}
               for k, counted, hit, t in parts]
    return pct, reasons


def _same(a, b):
    return bool(a and b and a.strip().lower() == b.strip().lower())


def _location_rule(want_place, want_remote, want_city, want_country,
                   profile, whose):
    """(counted, hit, text) for location, judged from the side that asks
    (`whose` is "your brief" or "your profile")."""
    if not (want_remote or want_place):
        return False, False, "Location: %s states none, not counted" % whose
    p_place = place_label(profile.get("city"), profile.get("country"))
    if want_remote and profile.get("remote_ok"):
        return True, True, "Location: both open to remote"
    if _same(want_city, profile.get("city")):
        return True, True, "Location: both in %s" % profile["city"]
    if _same(want_country, profile.get("country")):
        return True, True, "Location: both in %s" % profile["country"]
    if not (p_place or profile.get("remote_ok")):
        return (True, False,
                "Location: they have not said where they work, not earned")
    if want_place and want_remote:
        ask = "%s says %s, or remote" % (whose, want_place)
    elif want_place:
        ask = "%s says %s" % (whose, want_place)
    else:
        ask = "%s is open to remote" % whose
    if p_place and not profile.get("remote_ok"):
        return (True, False, "Location: %s; they are in %s and have not said "
                "they work remotely" % (ask, p_place))
    return True, False, "Location: %s; they are in %s" % (
        ask, p_place or "a place not stated")


def _budget_rule(profile, brief):
    """(counted, hit, text) for budget. Each case says what is true."""
    b_lo, b_hi = brief.get("budget_min"), brief.get("budget_max")
    b_span = _span(b_lo, b_hi)
    if b_span is None:
        return False, False, "Budget: your brief states none, not counted"
    r_lo, r_hi = profile.get("rate_min"), profile.get("rate_max")
    r_span = _span(r_lo, r_hi)
    if r_span is None:
        return True, False, "Budget: they have not stated a rate, not earned"
    currency = profile.get("currency") or "USD"
    if currency != "USD":
        return (False, False, "Budget: their rate is in %s and only USD is "
                "compared, not counted" % currency)
    fit = _overlaps(b_span, r_span)
    return True, fit, "Budget: their rate %s %s your budget %s" % (
        _money_words(r_lo, r_hi), "fits" if fit else "is outside",
        _money_words(b_lo, b_hi))


def match_brief(profile, brief, today):
    """How well a listed profile fits one of the viewer's open briefs.

    Rule-based and stated: role (40), genre (25), location (15),
    availability (10), budget (10). The brief decides which rules count:
    role and availability always; genre, location and budget when the
    brief states them. A counted rule the profile does not answer is not
    earned. No role and no genre in common means no match at all.
    Returns {"pct", "reasons", "brief_title", "basis"} or None.
    """
    roles = profile.get("roles") or []
    genres = [g.lower() for g in profile.get("genres") or []]
    parts = []
    role = brief.get("role") or ""
    role_hit = role in roles
    parts.append(("role", True, role_hit,
                  "Role: %s matches your brief" % role if role_hit else
                  "Role: your brief asks for a %s" % role))
    bg = (brief.get("genre") or "").strip()
    genre_hit = bool(bg) and bg.lower() in genres
    if not bg:
        parts.append(("genre", False, False,
                      "Genre: your brief states none, not counted"))
    elif genre_hit:
        parts.append(("genre", True, True, "Genre: %s" % bg))
    elif not genres:
        parts.append(("genre", True, False,
                      "Genre: they list no genres, not earned"))
    else:
        parts.append(("genre", True, False, "Genre: they do not list %s" % bg))
    if not (role_hit or genre_hit):
        return None
    parts.append(("location",) + _location_rule(
        place_label(brief.get("city"), brief.get("country")),
        brief.get("remote_ok"), brief.get("city"), brief.get("country"),
        profile, "your brief"))
    parts.append(("availability",) + _available_for(profile, brief, today))
    parts.append(("budget",) + _budget_rule(profile, brief))
    pct, reasons = _score(parts, MATCH_WEIGHTS)
    return {"pct": pct, "reasons": reasons, "brief_title": brief.get("title") or "",
            "basis": "brief"}


def match_self(profile, me, today):
    """No open brief to match on: compare with the viewer's OWN profile,
    which plays the brief's part. A genre in common is required (60);
    location (20) counts when the viewer states one; availability (20)
    always counts. Unanswered on their side is not earned. No genres of
    your own means no % at all."""
    mine = {g.lower() for g in (me or {}).get("genres") or []}
    shared = [g for g in profile.get("genres") or [] if g.lower() in mine]
    if not shared:
        return None
    parts = [("genre", True, True, "Genre: you both list %s" % ", ".join(shared[:3]))]
    parts.append(("location",) + _location_rule(
        place_label(me.get("city"), me.get("country")), me.get("remote_ok"),
        me.get("city"), me.get("country"), profile, "your profile"))
    parts.append(("availability",) + _available_for(profile, None, today))
    pct, reasons = _score(parts, SELF_WEIGHTS)
    return {"pct": pct, "reasons": reasons, "brief_title": "", "basis": "profile"}


def best_match(profile, open_briefs, me, today):
    """The best score across the viewer's open briefs; with none, against
    the viewer's own profile; with neither, None (no % is shown)."""
    if open_briefs:
        scored = [m for m in (match_brief(profile, b, today) for b in open_briefs) if m]
        return max(scored, key=lambda m: m["pct"]) if scored else None
    return match_self(profile, me, today) if me else None


def why_line(match):
    """The rules that scored, in one line, for the card."""
    hits = [r["text"] for r in match["reasons"] if r["hit"]]
    line = "; ".join(hits)
    if match.get("brief_title"):
        line += " (your brief “%s”)" % match["brief_title"]
    return line


def rating_line(summary):
    """("Trusted by 3 clients", "4.7", 5) or ("No ratings yet", None, 0)."""
    if not summary or not summary.get("count"):
        return "No ratings yet", None, 0
    n = summary["clients"]
    return ("Trusted by %d client%s" % (n, "" if n == 1 else "s"),
            "%.1f" % summary["mean"], summary["count"])


def person_card(profile, today, match=None, summary=None):
    """One listed collaborator, shaped for the people card. Every field is
    the member's own entry or says it is not stated."""
    trusted, mean, count = rating_line(summary)
    return {
        "user_id": profile["user_id"], "name": profile.get("name") or "Member",
        "initials": initials(profile.get("name")),
        "photo": profile.get("photo") or "",
        "roles": profile.get("roles") or [],
        "role_line": " / ".join(profile.get("roles") or []) or "Role not stated",
        "where": place_label(profile.get("city"), profile.get("country")),
        "remote": bool(profile.get("remote_ok")),
        "genres": (profile.get("genres") or [])[:4],
        # Cut to four on the card; the rest are counted, not hidden.
        "genres_more": max(0, len(profile.get("genres") or []) - 4),
        "credits": profile.get("credits") or "",
        "rate": money_range(profile.get("rate_min"), profile.get("rate_max"),
                            profile.get("currency")),
        "unit": RATE_UNITS.get(profile.get("rate_unit") or "", ""),
        "avail": availability_label(profile, today),
        "trusted": trusted, "mean": mean, "count": count,
        "match": match, "why": why_line(match) if match else "",
        "links": profile.get("links") or [], "bio": profile.get("bio") or "",
        "listed": bool(profile.get("listed")),
    }


def brief_place(brief):
    """The Location cell for a brief: its own words, or unstated."""
    return place_label(brief.get("city"), brief.get("country"))


def brief_budget(brief):
    return money_range(brief.get("budget_min"), brief.get("budget_max"))


def location_options(board):
    """The Location filter: Anywhere, Remote OK, each place a live brief
    states, and Not stated. No place is offered that no brief names."""
    places = {}
    for b in board:
        p = brief_place(b)
        if p:
            places.setdefault(p.lower(), p)
    return ([("", "Anywhere"), ("remote", "Remote OK")]
            + sorted(places.items(), key=lambda kv: kv[1].lower())
            + [("unstated", "Not stated")])


def location_filter(brief, value):
    if not value:
        return True
    stated = bool(brief_place(brief) or brief.get("remote_ok"))
    if value == "unstated":
        return not stated
    if value == "remote":
        return bool(brief.get("remote_ok"))
    return brief_place(brief).lower() == value


def budget_filter(brief, value):
    """A band matches only a brief that states a budget overlapping it;
    "unstated" is the briefs that do not say."""
    if not value:
        return True
    span = _span(brief.get("budget_min"), brief.get("budget_max"))
    if value == "unstated":
        return span is None
    band = next((b for b in BUDGET_BANDS if b[0] == value), None)
    if band is None or span is None:
        return False
    hi = band[3] if band[3] is not None else 10 ** 12
    return _overlaps(span, (band[2], hi))

"""The Audience screen (/fans): the owner's approved design, filled only
with what the account's own records can say.

Owner, 2026-09-18: "everything in fans besides collab and discover can be
in one screen", with the Audience mockup as the design. The mockup is a
picture of a full list; this module is what decides which parts of that
picture an account has earned.

THE RULES IT KEEPS
------------------
* Every number is counted from ml_fans, ml_consents, club_members and
  tour_shows for the signed-in account. Nothing is modelled.
* A thing that was never measured says so, with why. It is never 0:
  deliverability is not measured because nothing has been sent from here,
  and that is a different statement from "0% delivered".
* A trend appears only where stored history can compute it. The one
  history ml_fans keeps is `created`, so "Owned fans" can say how many
  gave their email on a smart link in the last 30 days against those who
  did before. Imports are not growth and are in neither side. The intent
  bands keep no history of who moved between them, so the segments card
  has no growth column rather than an invented one.
* The funnel is the owner's rows, each from a record type that exists
  (owner, 2026-09-18: "do your recommendations"):
    Link visits  ml_events page views on the account's own smart links.
                 Views, not people - the app keeps no visitor identity - so
                 the row says "views", and it is drawn only when views
                 outnumber the fans on file.
    On file      every fan record.
    Engaged      any visit, click, pre-save or capture; with Pre-saved, not
    Pre-saved    measured until somebody has clicked a smart link.
    Buyer        fans tagged "customer" by the Shopify import; drawn only
                 once a Shopify import has run, so an account with no store
                 is not told it has no buyers.
    Member       fans whose address is an active Fan Club member; drawn only
                 when the account has a Fan Club.
  "Advocate" from the mockup has nothing behind it and is not drawn. Rows
  are ordered by commitment, not sorted by size, so a later row can be
  bigger than the one above it; the counts stay true.
* The map plots a city only when it is in US_CITIES below - real
  coordinates, the same public figures any atlas prints - and the fan's
  country is the US or blank. A city without coordinates still counts in
  the Top list; it just gets no dot.
* The showcase (the demo account and signed-out visitors) runs through
  the SAME builder with generated rows, and is labelled. A real account
  can never reach it: the route decides, and tests lock that.

Nothing here writes, and nothing here calls a network service.
"""

import json
import math
from datetime import date, datetime, timedelta, timezone

import fan_segments

# --- the map ---------------------------------------------------------------
# Real city coordinates (latitude, longitude), rounded to 4 places. Names
# that are also famous cities abroad (Paris, London, Birmingham,
# Manchester, Cambridge) are left out on purpose: a fan in "Paris" with no
# country is far more likely French than Texan, and a guessed dot is
# worse than none.
US_CITIES = {
    "new york": (40.7128, -74.0060), "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298), "houston": (29.7604, -95.3698),
    "phoenix": (33.4484, -112.0740), "philadelphia": (39.9526, -75.1652),
    "san antonio": (29.4241, -98.4936), "san diego": (32.7157, -117.1611),
    "dallas": (32.7767, -96.7970), "san jose": (37.3382, -121.8863),
    "austin": (30.2672, -97.7431), "jacksonville": (30.3322, -81.6557),
    "fort worth": (32.7555, -97.3308), "columbus": (39.9612, -82.9988),
    "charlotte": (35.2271, -80.8431), "san francisco": (37.7749, -122.4194),
    "indianapolis": (39.7684, -86.1581), "seattle": (47.6062, -122.3321),
    "denver": (39.7392, -104.9903), "washington": (38.9072, -77.0369),
    "boston": (42.3601, -71.0589), "el paso": (31.7619, -106.4850),
    "nashville": (36.1627, -86.7816), "detroit": (42.3314, -83.0458),
    "oklahoma city": (35.4676, -97.5164), "portland": (45.5152, -122.6784),
    "las vegas": (36.1699, -115.1398), "memphis": (35.1495, -90.0490),
    "louisville": (38.2527, -85.7585), "baltimore": (39.2904, -76.6122),
    "milwaukee": (43.0389, -87.9065), "albuquerque": (35.0844, -106.6504),
    "tucson": (32.2226, -110.9747), "fresno": (36.7378, -119.7871),
    "sacramento": (38.5816, -121.4944), "kansas city": (39.0997, -94.5786),
    "atlanta": (33.7490, -84.3880), "miami": (25.7617, -80.1918),
    "raleigh": (35.7796, -78.6382), "omaha": (41.2565, -95.9345),
    "minneapolis": (44.9778, -93.2650), "tulsa": (36.1540, -95.9928),
    "cleveland": (41.4993, -81.6944), "new orleans": (29.9511, -90.0715),
    "tampa": (27.9506, -82.4572), "orlando": (28.5383, -81.3792),
    "pittsburgh": (40.4406, -79.9959), "cincinnati": (39.1031, -84.5120),
    "st. louis": (38.6270, -90.1994), "st louis": (38.6270, -90.1994),
    "salt lake city": (40.7608, -111.8910), "richmond": (37.5407, -77.4360),
    "buffalo": (42.8864, -78.8784), "oakland": (37.8044, -122.2712),
    "long beach": (33.7701, -118.1937), "virginia beach": (36.8529, -75.9780),
    "honolulu": (21.3069, -157.8583), "anchorage": (61.2181, -149.9003),
    "charleston": (32.7765, -79.9311),
    "savannah": (32.0809, -81.0912), "durham": (35.9940, -78.8986),
    "greensboro": (36.0726, -79.7920), "baton rouge": (30.4515, -91.1871),
    "jackson": (32.2988, -90.1848), "little rock": (34.7465, -92.2896),
    "boise": (43.6150, -116.2023), "spokane": (47.6588, -117.4260),
    "reno": (39.5296, -119.8138), "madison": (43.0731, -89.4012),
    "des moines": (41.5868, -93.6250), "providence": (41.8240, -71.4128),
    "hartford": (41.7658, -72.6734), "newark": (40.7357, -74.1724),
    "brooklyn": (40.6782, -73.9442), "queens": (40.7282, -73.7949),
    "bronx": (40.8448, -73.8648), "harlem": (40.8116, -73.9465),
    "fort lauderdale": (26.1224, -80.1373), "st. petersburg": (27.7676, -82.6403),
    "tallahassee": (30.4383, -84.2807), "knoxville": (35.9606, -83.9207),
    "chattanooga": (35.0456, -85.3097), "lexington": (38.0406, -84.5037),
    "norfolk": (36.8508, -76.2859), "columbia": (34.0007, -81.0348),
    "asheville": (35.5951, -82.5515),
    "macon": (32.8407, -83.6324), "augusta": (33.4735, -82.0105),
    "shreveport": (32.5252, -93.7502), "mobile": (30.6954, -88.0399),
    "san bernardino": (34.1083, -117.2898), "riverside": (33.9533, -117.3962),
    "santa ana": (33.7455, -117.8677), "anaheim": (33.8366, -117.9143),
    "bakersfield": (35.3733, -119.0187), "stockton": (37.9577, -121.2908),
}
CITY_ALIASES = {"nyc": "new york", "new york city": "new york", "la": "los angeles",
                "washington dc": "washington", "washington, dc": "washington",
                "washington d.c.": "washington", "d.c.": "washington", "dc": "washington",
                "sf": "san francisco", "philly": "philadelphia", "atl": "atlanta",
                "nola": "new orleans", "vegas": "las vegas"}
US_NAMES = {"us", "usa", "u.s.", "u.s.a.", "united states", "united states of america", "america"}

# The owner's map is an Albers equal-area conic of the lower 48
# (standard parallels 29.5 and 45.5, centred 37.5N 96W), drawn into a
# 604 x 306 viewBox. These six numbers are that projection's placement,
# fitted to the six cities the mockup drew; the fit is exact to 0.1px, so
# a real Atlanta lands where the owner's Atlanta was.
_AFFINE = (583.3515, -0.08794, 242.9069, -0.09022, -583.1708, 158.8131)
MAP_W, MAP_H = 604, 306


def _albers(lat, lon, lat1=29.5, lat2=45.5, lat0=37.5, lon0=-96.0):
    r = math.radians
    n = (math.sin(r(lat1)) + math.sin(r(lat2))) / 2
    c = math.cos(r(lat1)) ** 2 + 2 * n * math.sin(r(lat1))
    rho0 = math.sqrt(c - 2 * n * math.sin(r(lat0))) / n
    rho = math.sqrt(c - 2 * n * math.sin(r(lat))) / n
    theta = n * r(lon - lon0)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


def project(lat, lon):
    """(x, y) in the map's viewBox, or None when the point falls off it
    (Alaska, Hawaii: the owner's map is the lower 48)."""
    px, py = _albers(lat, lon)
    a, b, c, d, e, f = _AFFINE
    x, y = a * px + b * py + c, d * px + e * py + f
    if not (0 <= x <= MAP_W and 0 <= y <= MAP_H):
        return None
    return round(x, 1), round(y, 1)


def coords_for(city, country):
    """Real coordinates for a fan's city, or None. US or blank country only."""
    ctry = (country or "").strip().lower()
    if ctry and ctry not in US_NAMES:
        return None
    key = (city or "").strip().lower()
    key = CITY_ALIASES.get(key, key)
    return US_CITIES.get(key)


# --- helpers ---------------------------------------------------------------

INTENT_ORDER = ["Superfan", "Hot", "Warm", "Cool", "Cold"]
INTENT_COPY = {
    "Superfan": ("star", "The scorer's top band: repeat visits, clicks and pre-saves"),
    "Hot": ("star", "Scored hot: clicked and came back"),
    "Warm": ("note", "Scored warm: visited and clicked"),
    "Cool": ("pulse", "Scored cool: one visit or so"),
    "Cold": ("dot", "No activity scored yet, which is every fresh import"),
}


def _tags(fan):
    try:
        return json.loads(fan.get("tags") or "[]")
    except (ValueError, TypeError):
        return []


def _engaged(fan):
    return sum(int(fan.get(k) or 0) for k in
               ("total_visits", "total_clicks", "total_presaves", "total_captures")) > 0


def _clicked(fan):
    return int(fan.get("total_clicks") or 0) > 0 or int(fan.get("total_presaves") or 0) > 0


def _day(stamp):
    try:
        return date.fromisoformat(str(stamp)[:10])
    except (ValueError, TypeError):
        return None


def _when(stamp, now):
    try:
        then = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        d = _day(stamp)
        if d is None:
            return ""
        then = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    secs = max(0, int((now - then).total_seconds()))
    if secs < 3600:
        return "%dm ago" % max(1, secs // 60)
    if secs < 86400:
        return "%dh ago" % (secs // 3600)
    if secs < 86400 * 30:
        return "%dd ago" % (secs // 86400)
    return then.strftime("%b %d, %Y")


def _short_name(name, email):
    parts = (name or "").split()
    if len(parts) >= 2:
        return "%s %s." % (parts[0], parts[-1][0].upper())
    if parts:
        return parts[0]
    return email or "A fan"


def _initials(label):
    letters = [p[0] for p in label.replace("@", " ").replace(".", " ").split() if p[:1].isalpha()]
    return ("".join(letters[:2]) or "?").upper()


# The trend chip needs a base worth dividing by: 3 new against 1 before is
# not "up 300%", it is four people.
GROWTH_MIN_BASE = 20


def _pct(part, whole):
    return round(100.0 * part / whole) if whole else None


# --- the builder -----------------------------------------------------------

def build(fans, consented=0, club_members=(), shows=(), campaigns=(),
          now=None, showcase=False, resend_configured=False,
          link_visits=0, club_on=False):
    """Everything the Audience screen shows, from rows the caller read.

    fans           ml_fans rows (dicts) for one account
    consented      how many of them have at least one consent record
    club_members   club_members rows, for the activity feed
    shows          tour_shows rows, already filtered to upcoming
    campaigns      ml_campaigns rows, to name the link a fan came from
    """
    now = now or datetime.now(timezone.utc)
    today = now.date()
    fans = list(fans or ())
    show_cities = [(s.get("city") or "").strip() for s in shows if (s.get("city") or "").strip()]
    seg = fan_segments.summary(fans, show_cities, today=today)
    total = seg["total"]
    live = fan_segments.contactable(fans)
    contactable = seg["contactable"]

    # Owned fans, and the one trend the records can support: people who
    # gave their email on a smart link in the last 30 days, against those
    # who did before. A list import or a Shopify pull is the artist moving
    # a list they already had, not the audience growing, so those rows are
    # in neither side. A percentage needs a base worth dividing by.
    growth = None
    cutoff = today - timedelta(days=30)
    captured = [f for f in fans if not ({"imported", "shopify"} & set(_tags(f)))]
    recent = sum(1 for f in captured if (_day(f.get("created")) or today) > cutoff)
    before = len(captured) - recent
    if before >= GROWTH_MIN_BASE and recent > 0:
        growth = {"pct": round(100.0 * recent / before, 1), "recent": recent, "before": before}

    # Located is counted over the contactable, the same people "Where they
    # are" lists, so "the rest are Unknown, and still selectable" is true.
    nowhere = fan_segments.place_key({})
    located = sum(1 for f in live if fan_segments.place_key(f) != nowhere)

    # Where they are: contactable per region, and the suppressed in each.
    sup_by_region = {}
    for f in seg["suppressed"]["fans"]:
        k = fan_segments.place_key(f)
        sup_by_region[k] = sup_by_region.get(k, 0) + 1
    top = max([g["count"] for g in seg["regions"]] or [0])
    regions = []
    for g in seg["regions"]:
        regions.append({
            "key": g["region"], "count": g["count"], "unknown": g["unknown"],
            "suppressed": sup_by_region.get(g["key"], 0),
            "bar": max(2, round(100.0 * g["count"] / top)) if top else 0,
        })

    # The map: contactable fans by city, the same people the rows count,
    # keyed exactly as regions and tour matching key them.
    by_city = {}
    for f in live:
        k = fan_segments.city_key(f.get("city"))
        if not k:
            continue
        e = by_city.setdefault(k, {"count": 0, "_sp": {}, "_ct": {}})
        e["count"] += 1
        sp = " ".join((f.get("city") or "").split())
        e["_sp"][sp] = e["_sp"].get(sp, 0) + 1
        ct = " ".join((f.get("country") or "").split())
        if ct:
            e["_ct"][ct] = e["_ct"].get(ct, 0) + 1
    for e in by_city.values():
        e["city"] = fan_segments.canonical(e.pop("_sp"))
        e["country"] = fan_segments.canonical(e.pop("_ct"))
    cities = sorted(by_city.values(), key=lambda e: (-e["count"], e["city"]))
    plotted = []
    for e in cities:
        ll = coords_for(e["city"], e["country"])
        xy = project(*ll) if ll else None
        if xy:
            plotted.append(dict(e, x=xy[0], y=xy[1]))
    plotted = plotted[:12]
    geo = {"top": cities[:5], "dots": [], "labels": [], "unplotted": 0,
           "key_min": None, "key_max": None, "cities": len(cities)}
    if plotted:
        lo = min(p["count"] for p in plotted)
        hi = max(p["count"] for p in plotted)
        for i, p in enumerate(sorted(plotted, key=lambda p: p["count"])):
            core = 8.0 if hi == lo else 5.5 + 5.5 * (p["count"] - lo) / float(hi - lo)
            geo["dots"].append(dict(p, core=round(core, 1), halo=round(core + 3, 1),
                                    ring_a=round(core * 2.35, 1), ring_b=round(core * 4, 1),
                                    spec=core >= 7.5,
                                    sx=round(p["x"] - core * .3, 1), sy=round(p["y"] - core * .38, 1),
                                    sr=round(core * .26, 1)))
        for p in plotted[:2]:
            core = 8.0 if hi == lo else 5.5 + 5.5 * (p["count"] - lo) / float(hi - lo)
            geo["labels"].append({"city": p["city"], "count": p["count"], "x": p["x"],
                                  "x1": round(p["x"] + core + 1, 1), "x2": round(p["x"] + core + 11.5, 1),
                                  "tx": round(p["x"] + core + 16, 1), "y": p["y"],
                                  "lx": round(100.0 * (p["x"] + core + 16) / MAP_W, 2),
                                  "ly": round(100.0 * p["y"] / MAP_H, 2)})
        geo["key_min"], geo["key_max"] = lo, hi
    geo["unplotted"] = len(cities) - len(plotted)

    # The funnel. Engaged and Pre-saved read smart-link behaviour; until
    # anybody has clicked they are not measured and are drawn as empty
    # outlines, the same statement List health makes about Engagement.
    # Link visits, Buyer and Member have their own sources and appear only
    # where that source exists.
    engaged = [f for f in fans if _engaged(f)]
    presaved = [f for f in fans if int(f.get("total_presaves") or 0) > 0]

    def pct(n):
        return ("%.1f%%" % (100.0 * n / total)).replace(".0%", "%") if total else ""

    funnel = []
    if total and int(link_visits or 0) >= total:
        funnel.append({"name": "Link visits", "count": int(link_visits),
                       "measured": True, "pct": "views"})
    funnel.append({"name": "On file", "count": total if total else None,
                   "measured": bool(total), "pct": pct(total)})
    clicks = bool(total) and bool(engaged)
    for name, rows in (("Engaged", engaged), ("Pre-saved", presaved)):
        funnel.append({"name": name, "count": len(rows) if clicks else None,
                       "measured": clicks, "pct": pct(len(rows)) if clicks else ""})
    if total and any("shopify" in _tags(f) for f in fans):
        buyers = sum(1 for f in fans if "customer" in _tags(f))
        funnel.append({"name": "Buyer", "count": buyers, "measured": True, "pct": pct(buyers)})
    if total and club_on:
        joined = {(m.get("member_email") or "").strip().lower() for m in club_members or ()
                  if (m.get("status") or "active") == "active"}
        members = sum(1 for f in fans if (f.get("email") or "").strip().lower() in joined)
        funnel.append({"name": "Member", "count": members, "measured": True, "pct": pct(members)})
    # The footer runs from On file to the deepest measured row after it.
    tail = [st for st in funnel if st["measured"] and st["name"] not in ("Link visits", "On file")]
    funnel_foot_key = "On file to " + (tail[-1]["name"].lower() if tail else "pre-saved")
    funnel_foot = None
    if tail:
        n = tail[-1]["count"]
        funnel_foot = "1 in {:,}".format(max(1, round(total / float(n)))) if n else "None yet"

    # List health.
    in_app = [f for f in fans if not ({"imported", "shopify"} & set(_tags(f)))]
    fresh = 0
    for f in in_app:
        d = _day(f.get("created"))
        if d and (today - d).days <= fan_segments.FRESH_DAYS:
            fresh += 1
    health = [
        {"label": "Consent on file", "icon": "shield", "score": _pct(consented, total),
         "absent": "No fans on file", "whole": total},
        {"label": "Consent freshness", "icon": "clock",
         "score": _pct(fresh, len(in_app)) if in_app else None,
         "absent": "Not measured" if total else "No fans on file", "whole": len(in_app)},
        {"label": "Deliverability", "icon": "mail", "score": None, "absent": "Not measured",
         "whole": 0},
        {"label": "Location coverage", "icon": "pin", "score": _pct(located, contactable),
         "absent": "Nobody contactable" if total else "No fans on file",
         "whole": contactable},
        {"label": "Engagement", "icon": "pulse",
         "score": _pct(len(engaged), total) if engaged else None,
         "absent": "Not measured yet", "whole": total},
    ]
    for h in health:
        # Green means healthy, and a score only says that about the list
        # when it was measured over most of it. A score over a sliver
        # (freshness reads smart-link captures only) stays gold and names
        # its base.
        broad = bool(total) and h["whole"] * 2 >= total
        h["tone"] = "good" if (h["score"] or 0) >= 80 and broad else "mid"
        h["basis"] = ("of {:,}".format(h["whole"])
                      if h["score"] is not None and h["whole"] != total else "")

    # Recent activity: fans joining the list, and fan club joins.
    titles = {c["id"]: (c.get("title") or "a smart link") for c in campaigns or ()}
    by_email = {(f.get("email") or "").lower(): f for f in fans}
    events = []
    for f in fans:
        tags = _tags(f)
        if "imported" in tags:
            act = "Added from a list you imported"
        elif "shopify" in tags:
            act = "Added from your Shopify customers"
        elif f.get("first_campaign_id") in titles:
            act = "Gave you their email on %s" % titles[f["first_campaign_id"]]
        else:
            act = "Added to your list"
        events.append((str(f.get("created") or ""), f.get("name"), f.get("email"), act))
    for m in club_members or ():
        email = (m.get("member_email") or "").lower()
        fan = by_email.get(email) or {}
        events.append((str(m.get("created") or ""), fan.get("name"), email, "Joined your Fan Club"))
    events.sort(key=lambda e: e[0], reverse=True)
    activity = []
    for stamp, name, email, act in events[:5]:
        label = _short_name(name, email)
        activity.append({"name": label, "initials": _initials(label), "action": act,
                         "when": _when(stamp, now)})

    # Segments: the scorer's bands, no growth column (no history of them).
    counts = {}
    for f in fans:
        lvl = (f.get("intent_level") or "Cold").strip() or "Cold"
        counts[lvl] = counts.get(lvl, 0) + 1
    order = [l for l in INTENT_ORDER if l in counts] + sorted(l for l in counts if l not in INTENT_ORDER)
    segments = [{"name": l, "count": counts[l],
                 "icon": INTENT_COPY.get(l, ("pin", ""))[0],
                 "desc": INTENT_COPY.get(l, ("", "A band the scorer wrote"))[1]} for l in order]

    # Tour demand.
    first_date = {}
    for s in sorted(shows, key=lambda s: str(s.get("date") or "")):
        c = fan_segments.city_key(s.get("city"))
        if c and c not in first_date:
            d = _day(s.get("date"))
            first_date[c] = {"date": d.strftime("%b %d") if d else "",
                             "hold": (s.get("status") or "") == "hold"}
    tour = {"has_shows": bool(shows), "shows": len(shows),
            "covered": [dict(c, **first_date.get(c["key"], {"date": "", "hold": False}))
                        for c in seg["tour"]["covered"]][:6],
            "uncovered": seg["tour"]["uncovered"][:6],
            "unmatched": seg["tour"]["unmatched_shows"][:6]}

    return {
        "showcase": showcase,
        "resend_configured": bool(resend_configured),
        "total": total,
        "contactable": contactable,
        "contactable_pct": _pct(contactable, total),
        "suppressed": seg["suppressed"]["count"],
        "suppressed_reasons": seg["suppressed"]["reasons"],
        "adds_up": seg["adds_up"],
        "growth": growth,
        "never_engaged": seg["never_engaged"],
        "located": located,
        "located_pct": _pct(located, contactable),
        "regions": regions,
        "geo": geo,
        "funnel": funnel,
        "funnel_measured": bool(engaged),
        "funnel_foot": funnel_foot,
        "funnel_foot_key": funnel_foot_key,
        "health": health,
        "activity": activity,
        "segments": segments,
        "tour": tour,
    }


def selection_rows(fans, keys):
    """The contactable fans in the chosen regions, for the CSV. Suppressed
    fans are never in it: contactable() is the only door."""
    live = fan_segments.contactable(fans)
    labels = {g["region"]: g["key"] for g in fan_segments.regions(live)}
    wanted = {labels[k] for k in (keys or ()) if k in labels}
    return [f for f in live if fan_segments.place_key(f) in wanted]


# --- the showcase ----------------------------------------------------------
# Generated rows in the mockup's shape, for the demo account and signed-out
# visitors only. Labelled on the page; the route never hands them to a
# real account.

SHOWCASE_REGIONS = [("Atlanta", "US", 2837, 118), ("New York", "US", 2310, 96),
                    ("Los Angeles", "US", 1420, 54), ("London", "GB", 1204, 61),
                    ("Miami", "US", 1200, 40), ("Chicago", "US", 980, 30),
                    ("Seattle", "US", 610, 12), ("", "", 3216, 239)]
SHOWCASE_PEOPLE = [("Jasmine Reed", "Joined your Fan Club", 2), ("Marcus Tate", "Joined your Fan Club", 4),
                   ("Talia Moss", "Gave you their email on Midnight Drive", 6)]


def showcase_rows(now=None):
    now = now or datetime.now(timezone.utc)
    fans, i = [], 0
    for city, country, n, sup in SHOWCASE_REGIONS:
        for j in range(n + sup):
            i += 1
            recent = i % 9 == 0
            created = (now - timedelta(days=(5 if recent else 200 + i % 300))).isoformat()
            level = ("Hot" if i % 10 == 0 else "Warm" if i % 6 == 0 else "Cool" if i % 5 == 0 else "Cold")
            eng = level != "Cold"
            fans.append({"email": "showcase-%d@example.com" % i, "name": "", "city": city,
                         "country": country, "suppressed": "bounced" if j < sup else "",
                         "total_visits": 2 if eng else 0, "total_clicks": 1 if level in ("Hot", "Warm") else 0,
                         "total_presaves": 1 if level == "Hot" and i % 20 == 0 else 0,
                         "total_captures": 0, "intent_level": level, "tags": '["imported"]' if not eng else "[]",
                         "created": created})
    for k, (name, act, hours) in enumerate(SHOWCASE_PEOPLE):
        fans.append({"email": "showcase-p%d@example.com" % k, "name": name, "city": "Atlanta",
                     "country": "US", "suppressed": "", "total_visits": 3, "total_clicks": 2,
                     "total_presaves": 1, "total_captures": 1, "intent_level": "Hot", "tags": "[]",
                     "created": (now - timedelta(hours=hours)).isoformat()})
    return fans


_SHOWCASE_CACHE = {}


def showcase(now=None):
    """The labelled example. Built once a day per process: it is fourteen
    thousand generated rows and never changes within a day."""
    now = now or datetime.now(timezone.utc)
    key = now.date().isoformat()
    if key not in _SHOWCASE_CACHE:
        _SHOWCASE_CACHE.clear()
        _SHOWCASE_CACHE[key] = _showcase(now)
    return _SHOWCASE_CACHE[key]


def _showcase(now):
    fans = showcase_rows(now)
    shows = [{"city": "New York", "date": (now + timedelta(days=30)).date().isoformat(), "status": "confirmed"},
             {"city": "Miami", "date": (now + timedelta(days=36)).date().isoformat(), "status": "confirmed"},
             {"city": "Chicago", "date": (now + timedelta(days=44)).date().isoformat(), "status": "hold"}]
    ctx = build(fans, consented=round(len(fans) * .94), shows=shows, now=now, showcase=True)
    ctx["activity"] = [{"name": _short_name(n, ""), "initials": _initials(_short_name(n, "")),
                        "action": a, "when": "%dh ago" % h} for n, a, h in SHOWCASE_PEOPLE]
    return ctx


def upcoming(shows, today=None):
    today = (today or date.today()).isoformat()
    return [s for s in shows or () if str(s.get("date") or "")[:10] >= today]


# --- reading one account ---------------------------------------------------

def consented_count(user_id):
    """Fans on this account with at least one consent record. One query
    rather than one per fan: a list import can bring thousands."""
    from db import get_db
    with get_db() as db:
        row = db.execute(
            "SELECT COUNT(DISTINCT c.fan_id) AS n FROM ml_consents c "
            "JOIN ml_fans f ON f.id = c.fan_id WHERE f.user_id = ?", (user_id,)).fetchone()
    return int(row["n"] or 0) if row else 0


def _visits(user_id):
    """Page views on the account's own smart links. Views, not people."""
    import links_store as mls
    try:
        return int((mls.account_event_counts(user_id) or {}).get("page_view") or 0)
    except Exception:
        return 0


def for_account(user_id, resend_configured=False, now=None):
    """The screen for one real account, from its own rows only."""
    import db as store
    import links_store as mls
    now = now or datetime.now(timezone.utc)
    fans = mls.list_fans(user_id)
    return build(fans,
                 consented=consented_count(user_id) if fans else 0,
                 club_members=store.list_club_members(user_id),
                 shows=upcoming(store.list_tour_shows(user_id), now.date()),
                 campaigns=mls.list_campaigns(user_id),
                 now=now, resend_configured=resend_configured,
                 link_visits=_visits(user_id),
                 club_on=bool(store.get_fan_club(user_id)))

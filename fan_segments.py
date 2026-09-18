"""What to do with a list once it is in: group it, and know who not to email.

Owner, 2026-09-18, after seeing that an imported list could only be blasted:
"they should be sorted by region and allowed to be mass clicked on in
regions or select all for tour blasts i think??", then "do d-4 with the
smart link first flow and all your ideas above implemented as well".

The problem an imported list has is that it is UNSCORED. Everything this
app is good at - the Hot/Warm/Cold ladder, segments, intent - is computed
from behaviour: clicks on smart links, visits, consent events. An imported
fan has produced none of it. They are a row with an address on it.

So the first thing you send an imported list is not a campaign, it is a
smart link. One link, one thing worth clicking, and the scorer that
already exists turns a flat list into a real audience the same day.
`first_send` below is that idea as data: who has never been scored, and
therefore who the first link is for.

Four groupings, in the order they are worth having:

  regions       what he asked for. Read from the file, never inferred. A
                fan with no location is Unknown, and Unknown is selectable,
                because a group that quietly vanishes from every send is
                how a list loses a third of itself without anyone noticing.

  tour overlap  the reverse of a tour blast, and the more valuable
                direction. Blasting a region when a show is booked is
                useful; knowing you have 400 fans in a city you are not
                playing is booking intelligence. Cities are matched by
                name, lowercased and stripped - nothing cleverer, and the
                match is reported rather than assumed.

  consent age   who is safe to contact, which is a better first filter than
                who is nearby. A list gathered in 2019 is a different legal
                and practical object from one gathered last month.

  suppression   who NOT to email. The import already counts every skipped
                row under a reason; carrying that forward is what stops a
                list being burned.

Nothing here writes. It reads fans and returns groupings, so it can be
tested without a database and cannot corrupt one.
"""

from datetime import date, datetime, timezone

UNKNOWN = "Unknown"

# How old a consent record is before it is worth a second look. Not a legal
# threshold - this app is not a lawyer - but the point at which "when did
# they agree to this" stops being obvious.
FRESH_DAYS = 365
STALE_DAYS = 365 * 2


def _place(fan):
    """The group a fan belongs to. City first where there is one, because
    an artist routes a tour through cities, not countries."""
    city = (fan.get("city") or "").strip()
    country = (fan.get("country") or "").strip()
    if city and country:
        return "%s, %s" % (city, country)
    return city or country or UNKNOWN


def regions(fans):
    """[{region, count, emails, unknown}], biggest first, Unknown last.

    Unknown is last rather than absent: it is usually the largest group on
    a freshly imported list, and hiding it would mean every "select all in
    a region" quietly missed most of the list.
    """
    groups = {}
    for fan in fans or ():
        key = _place(fan)
        g = groups.setdefault(key, {"region": key, "count": 0, "emails": []})
        g["count"] += 1
        if fan.get("email"):
            g["emails"].append(fan["email"])
    known = [g for k, g in groups.items() if k != UNKNOWN]
    known.sort(key=lambda g: (-g["count"], g["region"]))
    out = known + [groups[UNKNOWN]] if UNKNOWN in groups else known
    for g in out:
        g["unknown"] = g["region"] == UNKNOWN
    return out


def tour_overlap(fans, show_cities):
    """Where the audience is against where the tour goes.

    Returns {"covered", "uncovered", "unmatched_shows"}:
      covered         cities with fans AND a show, biggest first
      uncovered       cities with fans and NO show - the booking argument
      unmatched_shows shows in cities with no fans on file, which is not a
                      criticism of the show, only a statement that this
                      list cannot speak for it
    """
    booked = {(c or "").strip().lower() for c in (show_cities or ()) if (c or "").strip()}
    by_city = {}
    for fan in fans or ():
        city = (fan.get("city") or "").strip()
        if not city:
            continue
        by_city.setdefault(city.lower(), {"city": city, "count": 0})["count"] += 1

    covered = [v for k, v in by_city.items() if k in booked]
    uncovered = [v for k, v in by_city.items() if k not in booked]
    covered.sort(key=lambda v: -v["count"])
    uncovered.sort(key=lambda v: -v["count"])
    unmatched = sorted({c for c in (show_cities or ())
                        if (c or "").strip() and (c or "").strip().lower() not in by_city})
    return {"covered": covered, "uncovered": uncovered, "unmatched_shows": unmatched}


def _age_days(stamp, today=None):
    """Days since an ISO stamp, or None when it cannot be read. None is not
    zero: an unreadable date is unknown, not new."""
    if not stamp:
        return None
    text = str(stamp)[:10]
    try:
        then = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
    return ((today or datetime.now(timezone.utc).date()) - then).days


def consent_ages(fans, today=None):
    """Fans bucketed by how long ago they agreed.

    Buckets are fresh / ageing / stale / unknown, and unknown is its own
    bucket rather than being folded into the oldest one, because "we do not
    know when they agreed" and "they agreed a long time ago" are different
    problems with different answers.
    """
    out = {"fresh": [], "ageing": [], "stale": [], "unknown": []}
    for fan in fans or ():
        days = _age_days(fan.get("consented_at") or fan.get("created"), today)
        if days is None:
            out["unknown"].append(fan)
        elif days <= FRESH_DAYS:
            out["fresh"].append(fan)
        elif days <= STALE_DAYS:
            out["ageing"].append(fan)
        else:
            out["stale"].append(fan)
    return out


def suppressed(fans):
    """Who is not being contacted, and why, most common reason first."""
    rows = [f for f in (fans or ()) if (f.get("suppressed") or "").strip()]
    reasons = {}
    for f in rows:
        why = f["suppressed"].strip()
        reasons[why] = reasons.get(why, 0) + 1
    return {"fans": rows,
            "count": len(rows),
            "reasons": sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))}


def contactable(fans):
    """Everyone a send may go to. One definition, used everywhere, so a
    suppressed fan cannot come back through a different door."""
    return [f for f in (fans or ()) if not (f.get("suppressed") or "").strip()]


def first_send(fans):
    """Who has never done anything, and is therefore who the first smart
    link is for.

    This is the smart-link-first idea as data. An imported fan has no
    clicks, no visits, no score - so a campaign aimed at them is a guess.
    A link is not: whoever clicks gets scored by machinery that already
    exists, and the list stops being flat.
    """
    never = []
    for fan in contactable(fans):
        moved = (int(fan.get("total_visits") or 0) + int(fan.get("total_clicks") or 0)
                 + int(fan.get("total_presaves") or 0) + int(fan.get("total_captures") or 0))
        if moved == 0:
            never.append(fan)
    return never


def summary(fans, show_cities=(), today=None):
    """Everything the screen needs, in one pass, with counts that add up."""
    fans = list(fans or ())
    live = contactable(fans)
    sup = suppressed(fans)
    ages = consent_ages(live, today)
    return {
        "total": len(fans),
        "contactable": len(live),
        "suppressed": sup,
        "regions": regions(live),
        "tour": tour_overlap(live, show_cities),
        "consent": {k: len(v) for k, v in ages.items()},
        "never_engaged": len(first_send(fans)),
        # The one invariant worth asserting out loud: everybody is either
        # contactable or suppressed, and nobody is both or neither.
        "adds_up": len(live) + sup["count"] == len(fans),
    }

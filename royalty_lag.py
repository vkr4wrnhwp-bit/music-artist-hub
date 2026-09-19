"""Is this platform late, or is this just how long it takes?

The single most useful thing nobody was saying. A coverage gap on its own
means almost nothing, because store reporting runs months behind and every
store runs behind by a different amount. An artist looking at a platform
that has not reported for ninety days cannot tell whether that is normal
for it or whether something is wrong, so either they worry about nothing or
they ignore a real problem. Both distributor conversations named this as
their clients' pain, and the outside audit named it too.

The answer is built the honest way round. It prefers what THIS account has
actually seen, because a figure measured from your own statements is
evidence and a figure from an industry table is a guess. TYPICAL is only
the fallback, and every answer says which one it used.

  measured   how long this source has really taken to report for this
             account, from its own statement history. Needs enough periods
             to mean anything; below that it is not offered.
  typical    the published order-of-magnitude for that platform. Labelled
             as a general figure, never as this account's.
  unknown    a source with no history and no published figure. Says so,
             and offers no verdict at all. This is the common case early
             on and must not be dressed up as a pass.
"""

import datetime
import statistics

# Published, order-of-magnitude reporting lags in days, from the time a
# period ends to the time it appears on a statement. These move, they vary
# by distributor and territory, and they are NEVER presented as this
# account's own figures. They exist so a brand new account is not left with
# no frame at all.
TYPICAL = {
    "spotify": 45,
    "apple music": 45,
    "apple": 45,
    "itunes": 45,
    "amazon": 60,
    "amazon music": 60,
    "youtube": 60,
    "youtube music": 60,
    "deezer": 60,
    "tidal": 60,
    "pandora": 75,
    "soundcloud": 60,
    "tiktok": 90,
    "facebook": 90,
    "instagram": 90,
    "meta": 90,
    "beatport": 60,
    "bandcamp": 15,
    "napster": 75,
    "iheartradio": 90,
    "audiomack": 60,
}

# Below this many observed periods the account's own history is a
# coincidence rather than a pattern.
MIN_OBSERVATIONS = 3
# How far past the expected date counts as merely slow rather than overdue.
SLOW_GRACE_DAYS = 21
# Past this multiple of the expected wait, something is wrong.
OVERDUE_FACTOR = 2.0


def _key(source):
    return (source or "").strip().lower()


def typical_days(source):
    """The published figure for a platform, or None when there is not one."""
    k = _key(source)
    if k in TYPICAL:
        return TYPICAL[k]
    # "Spotify (US)" and "Apple Music - UK" are the same platform.
    for name, days in TYPICAL.items():
        if k.startswith(name + " ") or k.startswith(name + " (") or k.startswith(name + " -"):
            return days
    return None


def observed_days(history):
    """What this account has actually waited, per source, from its own
    statements.

    `history` is an iterable of (source, period_end, reported_on) as dates
    or ISO strings. Returns {source: {"days", "periods"}} for the sources
    with enough history to mean something. Sources below the floor are left
    out entirely rather than reported with a shaky number.
    """
    waits = {}
    for source, period_end, reported_on in history or ():
        end, seen = _as_date(period_end), _as_date(reported_on)
        if end is None or seen is None:
            continue
        gap = (seen - end).days
        if gap < 0:
            continue                      # reported before the period ended
        waits.setdefault(_key(source), []).append(gap)
    out = {}
    for source, gaps in waits.items():
        if len(gaps) >= MIN_OBSERVATIONS:
            out[source] = {"days": int(round(statistics.median(gaps))),
                           "periods": len(gaps)}
    return out


def _as_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def expectation(source, observed=None):
    """How long this source is expected to take, and where that came from.

    Returns {"days", "basis", "detail"}. basis is "measured", "typical" or
    "unknown", and days is None when it is unknown.
    """
    seen = (observed or {}).get(_key(source))
    if seen:
        return {"days": seen["days"], "basis": "measured",
                "detail": ("Measured from your own statements: %s has taken about "
                           "%d days over %d periods."
                           % (source, seen["days"], seen["periods"]))}
    published = typical_days(source)
    if published is not None:
        return {"days": published, "basis": "typical",
                "detail": ("A general figure for %s, about %d days. Not measured "
                           "from your account; once you have a few periods of "
                           "your own this uses those instead."
                           % (source, published))}
    return {"days": None, "basis": "unknown",
            "detail": ("Nothing is known about how long %s takes to report, and "
                       "nothing has been assumed." % source)}


def judge(source, period_end, today, observed=None, reported_on=None):
    """Is this source late for this period, or is this how long it takes?

    Returns {"state", "headline", "detail", "waited", "expected", "basis"}.
    state is one of:
      reported  it arrived, with how long it took
      normal    still inside the wait this source usually needs
      slow      past it, but not by enough to mean anything on its own
      overdue   far enough past that it is worth chasing
      unknown   no basis to judge. No verdict is offered.
    """
    end, now = _as_date(period_end), _as_date(today)
    if end is None or now is None:
        return {"state": "unknown", "headline": "No dates to compare",
                "detail": "This period has no usable dates.",
                "waited": None, "expected": None, "basis": "unknown"}

    exp = expectation(source, observed)
    arrived = _as_date(reported_on)
    if arrived is not None:
        waited = (arrived - end).days
        return {"state": "reported", "waited": waited, "expected": exp["days"],
                "basis": exp["basis"],
                "headline": "Reported after %d days" % waited,
                "detail": exp["detail"]}

    waited = (now - end).days
    if exp["days"] is None:
        return {"state": "unknown", "waited": waited, "expected": None,
                "basis": "unknown",
                "headline": "%d days, and no way to say whether that is late" % waited,
                "detail": exp["detail"]}

    expected = exp["days"]
    if waited <= expected:
        return {"state": "normal", "waited": waited, "expected": expected,
                "basis": exp["basis"],
                "headline": "%d days, which is normal for %s" % (waited, source),
                "detail": exp["detail"]}
    if waited <= expected + SLOW_GRACE_DAYS and waited < expected * OVERDUE_FACTOR:
        return {"state": "slow", "waited": waited, "expected": expected,
                "basis": exp["basis"],
                "headline": "%d days, a little past the usual %d" % (waited, expected),
                "detail": exp["detail"] + " A few weeks over is common and is not "
                                          "on its own a sign of a problem."}
    return {"state": "overdue", "waited": waited, "expected": expected,
            "basis": exp["basis"],
            "headline": "%d days, against a usual %d" % (waited, expected),
            "detail": exp["detail"] + " This one is far enough past that it is "
                                      "worth asking about."}


# Only these are worth anybody's attention. The rest are the platform
# taking as long as the platform takes.
WORTH_CHASING = ("overdue",)


def rank(findings):
    """Put the findings worth acting on in front, and drop the ones that are
    only a platform being a platform.

    Each finding is a dict carrying at least a "judgement" from judge() and,
    where it is known, an "estimate" in money. Returns the same dicts with a
    "priority" added, most worth chasing first. A finding with no estimate
    is not pushed to the bottom: unknown is not small.
    """
    out = []
    for f in findings or ():
        j = f.get("judgement") or {}
        if j.get("state") not in WORTH_CHASING:
            continue
        estimate = f.get("estimate")
        # How far past its own norm, so a source that is 300 days late
        # against a 45 day norm outranks one 100 days late against 90.
        expected = j.get("expected") or 1
        overdueness = max(0.0, (j.get("waited") or 0) - expected) / float(expected)
        # Measured beats typical: a verdict from this account's own history
        # is evidence, and evidence should outrank a table.
        confidence = 1.0 if j.get("basis") == "measured" else 0.6
        weight = (float(estimate) if estimate else 0.0) * confidence
        out.append(dict(f, priority={
            "weight": round(weight, 2),
            "overdue_by": round(overdueness, 2),
            "confidence": confidence,
            "estimated": estimate is not None,
        }))
    # Ones with money attached first, by size; then the unestimated by how
    # far past they are. An unknown amount is not a small amount, so it sits
    # above nothing rather than below everything.
    out.sort(key=lambda f: (-(f["priority"]["weight"]),
                            -(f["priority"]["overdue_by"])))
    return out

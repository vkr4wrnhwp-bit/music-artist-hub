"""Geometry and formatting for the growth-signal instruments.

The owner approved the "meter bridge" mockup on 2026-09-13: one flat
instrument per signal - reading, movement, a sparkline with its start
and end values written on it, a range rail showing where today sits
between the 28-day low and high, and a provenance line - plus a
half-dial for SB Momentum whose lit track is only as long as the share
of the score that could be measured.

Everything here is arithmetic on plain values so the templates stay
declarative and the numbers can be tested without a browser. Nothing
invents a reading: a None stays a gap, and an instrument with no series
draws no line.
"""
import math


def short(n):
    """45,300 -> 45.3k, 1,350,000 -> 1.35M, 812 -> 812. None -> "".

    For the ends of a sparkline, where a full figure would not fit; the
    instrument's own readout carries the exact number.
    """
    if n is None:
        return ""
    n = float(n)
    if abs(n) >= 1_000_000:
        return ("%.2f" % (n / 1_000_000)).rstrip("0").rstrip(".") + "M"
    if abs(n) >= 1_000:
        return ("%.1f" % (n / 1_000)).rstrip("0").rstrip(".") + "k"
    return "%d" % round(n)


def pct_change(old, new):
    """Percent change, or None when either side is unmeasured or the old
    value is zero (a change from nothing is not a percentage)."""
    if old is None or new is None or not old:
        return None
    return round((float(new) - float(old)) / float(old) * 100.0, 1)


def sparkline(series, width=200, height=44, pad=3):
    """A path for a dated series with gaps.

    `series` is a list of (label, value) oldest first; value may be None.
    Returns None when fewer than two measured points exist - one point
    is not a line. Otherwise:
      {"line": "M.. L..", "area": "M.. Z", "end": (x, y),
       "gap_tail": "M.. L.." or "", "measured": k, "total": n,
       "first": v0, "last": v1, "low": min, "high": max}
    Measured points are joined; unmeasured days are skipped, and a run of
    unmeasured days at the END is drawn as a dashed tail so a stale
    reading looks stale rather than current.
    """
    pts = [(i, v) for i, (_label, v) in enumerate(series)]
    measured = [(i, v) for i, v in pts if v is not None]
    n = len(pts)
    if n < 2 or len(measured) < 2:
        return None
    vals = [v for _i, v in measured]
    lo, hi = min(vals), max(vals)
    span = float(hi - lo) or 1.0
    usable_h = height - 2 * pad

    def x(i):
        return round(pad + i * (width - 2 * pad) / float(max(n - 1, 1)), 1)

    def y(v):
        return round(height - pad - (float(v) - lo) / span * usable_h, 1)

    line = " ".join(("M" if k == 0 else "L") + "%s,%s" % (x(i), y(v))
                    for k, (i, v) in enumerate(measured))
    last_i, last_v = measured[-1]
    first_i, _first_v = measured[0]
    area = line + " L%s,%s L%s,%s Z" % (x(last_i), height, x(first_i), height)
    gap_tail = ""
    if last_i < n - 1:
        gap_tail = "M%s,%s L%s,%s" % (x(last_i), y(last_v), x(n - 1), y(last_v))
    return {"line": line, "area": area, "end": (x(last_i), y(last_v)),
            "gap_tail": gap_tail, "measured": len(measured), "total": n,
            "first": vals[0], "last": last_v, "low": lo, "high": hi,
            "width": width, "height": height}


def rail(low, high, current):
    """Where `current` sits between low and high, as a percentage."""
    if low is None or high is None or current is None:
        return None
    if high == low:
        return 50
    pos = (float(current) - float(low)) / (float(high) - float(low)) * 100.0
    return int(round(max(0.0, min(100.0, pos))))


# --- the momentum half-dial ----------------------------------------------

DIAL = {"cx": 150.0, "cy": 160.0, "r": 120.0}


def _point(value):
    """0..100 along a half dial from left (180 deg) to right (0 deg)."""
    angle = math.pi * (1.0 - max(0.0, min(100.0, float(value))) / 100.0)
    return (round(DIAL["cx"] + DIAL["r"] * math.cos(angle), 1),
            round(DIAL["cy"] - DIAL["r"] * math.sin(angle), 1))


def arc(start, end):
    """SVG arc from `start` to `end` (0..100) along the dial. "" if empty."""
    if end <= start:
        return ""
    x0, y0 = _point(start)
    x1, y1 = _point(end)
    large = 1 if (end - start) > 50 else 0
    return "M%s,%s A%s,%s 0 %d 1 %s,%s" % (x0, y0, DIAL["r"], DIAL["r"], large, x1, y1)


def gauge(score, coverage=1.0, base=None):
    """Paths for the dial.

    score     - the value shown (0..100)
    coverage  - share of the score's weight that was measured (0..1); the
                lit track stops there and the rest is a dashed tail
    base      - the value before any penalty; the segment from score to
                base is drawn in the critical colour when base > score
    """
    score = max(0.0, min(100.0, float(score or 0)))
    cov = max(0.0, min(1.0, float(coverage if coverage is not None else 1.0))) * 100.0
    base = None if base is None else max(0.0, min(100.0, float(base)))
    return {
        "track": arc(0, 100),
        "measurable": arc(0, cov),
        "tail": arc(cov, 100),
        "value": arc(0, score),
        "penalty": arc(score, base) if base is not None and base > score else "",
        "end": _point(score),
        "ticks": [(_point(0), "0"), (_point(50), "50"), (_point(100), "100")],
    }

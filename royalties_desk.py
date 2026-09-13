"""The Royalties page, as approved from the numbered mockup of 2026-09-13.

One page where there were three: Royalties, Royalty Lanes and Income by
type (publishing, mechanicals, neighboring rights, by market) read the
same statement rows and are laid out here together. Revenue OS is not
part of it; that stays the profit-and-loss page.

Everything is computed from the rows on file, scoped to the period the
reader chose. A stream with nothing on file is a statement nobody has
uploaded, never money that does not exist, and the row says which. The
lane estimates are a share of the artist's own earnings and say so.
"""
import re

import artist_os
import royalty_types
import statements_desk
import statements_engine
import store_identity


_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun",
           "jul", "aug", "sep", "oct", "nov", "dec")


def period_key(label):
    """(year, month) for ordering, for the ways distributors write a
    period: "2026-05", "MAY-26", "May 2026", "2026/05". Unknown shapes
    sort last, in the order they were written."""
    text = (label or "").strip().lower()
    m = re.match(r"^(\d{4})[-/](\d{1,2})", text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    for i, mon in enumerate(_MONTHS, 1):
        if text.startswith(mon):
            year = re.search(r"(\d{4}|\d{2})\b", text[3:])
            if year:
                y = int(year.group(1))
                return (y if y > 99 else 2000 + y, i)
    return (9999, 0)


def order_periods(labels):
    return sorted(set(labels), key=lambda p: (period_key(p), p))


def _fmt_list(names):
    names = list(names)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def money(n):
    return statements_desk.money(n)


# --- 1 · the period and the scan --------------------------------------------

def scan(rows, uploads, analysis, periods):
    span = ""
    if periods:
        span = periods[0] if len(periods) == 1 else "%s – %s" % (periods[0], periods[-1])
    return [
        "%d statement%s" % (len(uploads), "" if len(uploads) == 1 else "s"),
        "%s row%s" % ("{:,}".format(len(rows)), "" if len(rows) == 1 else "s"),
        "%d track%s" % (analysis["track_count"], "" if analysis["track_count"] == 1 else "s"),
        "%d store%s" % (analysis["store_count"], "" if analysis["store_count"] == 1 else "s"),
        "%d period%s%s" % (len(periods), "" if len(periods) == 1 else "s", (" · " + span) if span else ""),
    ]


# --- 2 · the instruments -----------------------------------------------------

def earnings(analysis, trend):
    """Reported earnings with the movement between the last two periods.
    `trend` is [(period, total)] over every period on file, in order."""
    import meters
    spark = meters.sparkline(trend) if len(trend) >= 2 else None
    delta = meters.pct_change(trend[-2][1], trend[-1][1]) if len(trend) >= 2 else None
    if delta is not None:
        delta_text = "%+.1f%% · %s vs %s" % (delta, trend[-1][0], trend[-2][0])
        tone = "up" if delta > 0.05 else ("down" if delta < -0.05 else "flat")
    else:
        delta_text, tone = "Not measured · one period", "flat"
    return {
        "shown": money(analysis["total"]), "delta_text": delta_text, "delta_tone": tone,
        "spark": spark,
        "spark_first": "%s $%s" % (trend[0][0], meters.short(round(trend[0][1]))) if spark else "",
        "spark_last": "%s $%s" % (trend[-1][0], meters.short(round(trend[-1][1]))) if spark else "",
        "note": "" if spark else "Upload a second period and the change between them appears here.",
        "prov": ["%d period%s on file" % (len(trend), "" if len(trend) == 1 else "s"),
                 "a third makes a trend" if len(trend) == 2 else ""],
    }


STREAMS = (
    ("recording", "Recording / streaming", "Paid by your distributor from the stores"),
    ("neighboring", "Neighboring rights", "SoundExchange, for the performer and the master owner"),
    ("publishing", "Performance / publishing", "A PRO: ASCAP, BMI, SESAC, or a publishing admin"),
    ("mechanical", "Mechanical", "The MLC, for the songwriter, on every stream"),
)
_ACTION = {
    "recording": ("Upload a statement", "/statements"),
    "neighboring": ("Upload a SoundExchange statement", "/statements"),
    "publishing": ("Upload a PRO statement", "/statements"),
    "mechanical": ("Open Recovery", "/recovery#mlc"),
}


def streams(analysis, mlc=None):
    """The four streams as columns and as ledger rows, classified from the
    source name on each row the way Income by type did it."""
    by_bucket = {}
    for s in analysis["by_source"]:
        b = royalty_types.classify(s["source"])
        entry = by_bucket.setdefault(b, {"amount": 0.0, "lines": 0, "sources": []})
        entry["amount"] += s["amount"]
        entry["lines"] += 1
        entry["sources"].append(s["source"])
    top = max((e["amount"] for e in by_bucket.values()), default=0)
    cols, ledger = [], []
    for key, label, who in STREAMS:
        e = by_bucket.get(key)
        amount = round(e["amount"], 2) if e else 0.0
        on_file = bool(e and e["amount"] > 0)
        col = {"key": key, "label": label, "amount": amount, "on_file": on_file,
               "shown": money(amount) if on_file else "—",
               "sub": ("%d line%s" % (e["lines"], "" if e["lines"] == 1 else "s")
                       + (" · " + e["sources"][0] if e["lines"] == 1 else "")) if on_file
                      else {"publishing": "no PRO statement", "mechanical": "no MLC statement",
                            "neighboring": "no SoundExchange line", "recording": "no distributor statement"}[key],
               "height": max(4, round(100.0 * amount / top)) if on_file and top else 0}
        cols.append(col)
        stores = sorted(set(store_identity.store_of(s) for s in e["sources"])) if e else []
        if on_file:
            what = ("%s%s. " % (_fmt_list(stores[:8]), (" and %d more" % (len(stores) - 8)) if len(stores) > 8 else ""))
            if key == "recording":
                what += "Distributor statements carry this stream, so it is most of what is on file."
            elif key == "neighboring":
                what += ("A SoundExchange line reached the statement through the distributor. A direct "
                         "SoundExchange registration pays the performer's share as well; nothing on file "
                         "says whether that is registered.")
            lamp, tone = "on file", "good"
        else:
            what = royalty_types.GUIDANCE.get(key, "")
            lamp, tone = "not on file", "none"
        action, href = _ACTION[key]
        mlc_note = ""
        if key == "mechanical" and mlc and mlc.get("latest"):
            gone = mlc["latest"]["summary"].get("unmatched") or 0
            part = mlc["latest"]["summary"].get("partial") or 0
            if gone or part:
                lamp, tone = ("%d work%s unregistered" % (gone, "" if gone == 1 else "s")
                              if gone else "%d partly claimed" % part), "crit" if gone else "warn"
                mlc_note = (" The MLC check on Recovery found %s, which is mechanical money nobody is collecting."
                            % _fmt_list([x for x in (
                                ("%d work%s with no registration" % (gone, "" if gone == 1 else "s")) if gone else "",
                                ("%d partly claimed" % part) if part else "") if x]))
            else:
                mlc_note = " The MLC check on Recovery found every checked work fully claimed."
        ledger.append({"key": key, "label": label, "who": who, "what": what + mlc_note,
                       "amount": amount, "on_file": on_file, "lines": e["lines"] if e else 0,
                       "lamp": lamp, "tone": tone, "action": action, "href": href})
    other = by_bucket.get("other")
    if other and other["amount"] > 0:
        ledger.append({"key": "other", "label": "Unclassified", "who": "Lines the classifier does not know",
                       "what": "%s. Money on file that none of the four streams claims; tell us the source and it will be filed."
                               % _fmt_list(sorted(set(store_identity.store_of(s) for s in other["sources"]))[:8]),
                       "amount": round(other["amount"], 2), "on_file": True, "lines": other["lines"],
                       "lamp": "on file", "tone": "good", "action": "", "href": ""})
    return {"cols": cols, "ledger": ledger,
            "on_file": sum(1 for c in cols if c["on_file"]),
            "other": round(other["amount"], 2) if other else 0.0}


LANE_DOT = {
    "claimed": ("paying", "claimed"), "connected": ("connected", "claimed"),
    "needs action": ("needs action", "action"), "in review": ("in review", "review"),
    "not eligible": ("not eligible", "na"),
}
REGISTRATION_LANES = {"mechanicals", "pro", "soundexchange", "neighboring", "content_id", "ugc"}


def lanes(tracks, ctx):
    """Every track against the nine lanes, and the count of lanes paying."""
    rows = []
    paying = set()
    per_lane = {key: {"key": key, "label": label, "estimate": 0.0, "count": 0}
                for key, label in artist_os.LANES}
    for t in tracks:
        cells = []
        for lane in artist_os.lane_grid(t, ctx):
            state = lane["state"]
            if state in ("claimed", "connected"):
                paying.add(lane["key"])
            if state == "missing":
                word, dot = (("needs a registration", "action") if lane["key"] in REGISTRATION_LANES
                             else ("no evidence", "missing"))
            else:
                word, dot = LANE_DOT.get(state, (state, "missing"))
            cells.append({"key": lane["key"], "state": state, "word": word, "dot": dot,
                          "estimate": lane.get("estimate")})
            if lane.get("estimate"):
                # lane_grid prices a lane as a share of the WHOLE catalogue's
                # earnings, on every track. Summed across tracks that
                # multiplies one estimate by the track count - the old
                # Royalty Lanes page did exactly that. The footer carries the
                # catalogue figure once.
                per_lane[lane["key"]]["estimate"] = lane["estimate"]
                per_lane[lane["key"]]["count"] += 1
        rows.append({"id": t.get("id"), "title": t.get("title") or "Untitled", "cells": cells})
    for key, entry in per_lane.items():
        entry["estimate"] = round(entry["estimate"], 2)
        share = artist_os._LANE_SHARE.get(key)
        entry["share"] = ("%d%% share" % round(share * 100)) if share else ""
    lane_keys = [k for k, _ in artist_os.LANES]
    return {
        "rows": rows, "labels": [(k, l) for k, l in artist_os.LANES],
        "paying": len(paying), "of": len(lane_keys),
        "cells": [k in paying for k in lane_keys],
        "footer": [per_lane[k] for k in lane_keys],
        "missing_est": round(sum(e["estimate"] for e in per_lane.values()), 2),
        "paying_names": [l for k, l in artist_os.LANES if k in paying],
        "note": (("%s are paying." % _fmt_list([l.split(" /")[0] for k, l in artist_os.LANES if k in paying]))
                 if paying else "No lane shows money yet.") if tracks
                else "No Track Passports yet, so there is nothing to read the lanes against.",
    }


# --- 6 · by store, 7 · by track, period against period ------------------------

def movement(rows, periods, key_fn, limit=5, chosen=""):
    """Amounts per key for two periods, with the change: the chosen period
    against the one before it, or the last two on file. The amount shown
    is the chosen period's when one is chosen - the whole page follows the
    period - and the two-period total otherwise."""
    if chosen and chosen in periods and periods.index(chosen) > 0:
        a, b = periods[periods.index(chosen) - 1], chosen
    elif len(periods) < 2 or (chosen and chosen in periods):
        return {"rows": [], "tail": None, "a": periods[0] if periods else "", "b": "", "top": 0, "enough": False}
    else:
        a, b = periods[-2], periods[-1]
    totals = {}
    for r in rows:
        p = (r.get("period") or "").strip()
        if p not in (a, b):
            continue
        k = key_fn(r)
        if not k:
            continue
        entry = totals.setdefault(k, {"key": k, "a": 0.0, "b": 0.0})
        entry["a" if p == a else "b"] += r.get("amount") or 0
    import meters
    out = []
    for e in totals.values():
        e["a"], e["b"] = round(e["a"], 2), round(e["b"], 2)
        e["total"] = round(e["a"] + e["b"], 2)
        e["amount"] = e["b"] if chosen else e["total"]
        # "new" and "gone" are states, not percentages: a store that paid
        # nothing before is not up by infinity, and one that stopped is
        # not down 100% - it is gone, which is the thing to notice.
        if e["b"] and not e["a"]:
            e["delta"], e["tone"], e["delta_text"] = None, "up", "new"
        elif e["a"] and not e["b"]:
            e["delta"], e["tone"], e["delta_text"] = None, "down", "gone"
        else:
            e["delta"] = meters.pct_change(e["a"], e["b"])
            e["tone"] = ("flat" if e["delta"] is None else
                         "up" if e["delta"] > 0.05 else "down" if e["delta"] < -0.05 else "flat")
            e["delta_text"] = ("%+.1f%%" % e["delta"]) if e["delta"] is not None else "—"
        out.append(e)
    out.sort(key=lambda e: (-e["total"], e["key"]))
    top = max((max(e["a"], e["b"]) for e in out), default=0)
    shown, rest = out[:limit], out[limit:]
    tail = None
    if rest:
        ta, tb = round(sum(e["a"] for e in rest), 2), round(sum(e["b"] for e in rest), 2)
        d = meters.pct_change(ta, tb)
        tail = {"count": len(rest), "a": ta, "b": tb, "total": round(ta + tb, 2), "delta": d,
                "amount": tb if chosen else round(ta + tb, 2),
                "delta_text": ("%+.1f%%" % d) if d is not None else "—",
                "tone": "flat" if d is None else "up" if d > 0.05 else "down" if d < -0.05 else "flat",
                "rows": rest}
    return {"rows": shown, "tail": tail, "a": a, "b": b, "top": top, "enough": True}


# --- 8 · markets and the catalogue signal --------------------------------------

def markets(rows, limit=5):
    with_t = [r for r in rows if (r.get("territory") or "").strip()]
    totals = {}
    for r in with_t:
        t = r["territory"].strip().upper()
        totals[t] = totals.get(t, 0.0) + (r.get("amount") or 0)
    ordered = sorted(totals.items(), key=lambda x: -x[1])
    top = ordered[0][1] if ordered else 0
    return {
        "rows": [{"code": c, "amount": round(a, 2)} for c, a in ordered[:limit]],
        "tail": {"count": len(ordered) - limit, "amount": round(sum(a for _, a in ordered[limit:]), 2)}
                if len(ordered) > limit else None,
        "top": top, "covered": len(with_t), "total_rows": len(rows),
        "total": round(sum(a for _, a in ordered), 2),
    }


def signal(summary):
    if not summary:
        return None
    band = summary.get("valuation") or {}
    return {"annualized": summary.get("annualized") or 0,
            "low": band.get("low"), "high": band.get("high"), "mid": band.get("mid"),
            "months": len(summary.get("monthly_trend") or []) or 1}


# --- the whole desk ---------------------------------------------------------------

def build(rows_all, rows, uploads, chosen, os_tracks, os_ctx, mlc=None):
    """rows_all: every statement row on file; rows: the rows in scope
    (one period, or all). chosen: the period label or ""."""
    if not rows:
        return None
    analysis = statements_engine.analyze(rows)
    summary = statements_engine.build_royalty_summary(rows)
    periods = order_periods((r.get("period") or "").strip() for r in rows_all if r.get("period"))
    monthly = {}
    for r in rows_all:
        p = (r.get("period") or "").strip()
        if p:
            monthly[p] = monthly.get(p, 0.0) + (r.get("amount") or 0)
    trend = [(p, round(monthly[p], 2)) for p in periods]
    in_scope = [chosen] if chosen else periods
    return {
        "chosen": chosen, "periods": periods, "analysis": analysis,
        "facts": scan(rows, uploads, analysis, in_scope),
        "earnings": earnings(analysis, trend),
        "streams": streams(analysis, mlc),
        "lanes": lanes(os_tracks, os_ctx),
        "stores": movement(rows_all, periods, lambda r: store_identity.store_of(r.get("source")), chosen=chosen),
        "tracks": movement(rows_all, periods, lambda r: (r.get("title") or "").strip(), chosen=chosen),
        "markets": markets(rows),
        "signal": signal(summary),
    }

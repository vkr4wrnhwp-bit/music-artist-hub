"""The Statements page, as approved from the numbered mockup of 2026-09-13.

Everything here is a view over `statements_engine.analyze()` and the
recovery findings; nothing is measured twice and nothing is invented. The
page's four readings are instruments in the same language as Artist
Pulse, and each one is tagged with what it is:

  actual    computed from the rows the artist uploaded
  estimate  a priority order, weighted by what each silent store paid
  derived   a count read off the rows (stores, payee lines)

The store ladder groups payee lines under the store they belong to, so
YouTube is one bar with its four lines folded under it rather than five
bars, and a society or a licensing deal is marked as not a store at all.

Each coverage gap shows its silent stores as chips in one of three
states - carries it, not listed, could not be checked - read from the
last store check the artist ran. A store nobody asked stays dashed and
is never read as missing.
"""
import math
import re

import coverage_check
import meters
import store_identity


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def slug(text):
    return "".join(c if c.isalnum() else "-" for c in str(text).lower()).strip("-")


def money(n):
    return "$%s" % "{:,.2f}".format(n or 0)


def period_label(period):
    """'2026-05' -> 'May 2026'; anything else is shown as written."""
    m = re.match(r"^(\d{4})-(\d{1,2})$", (period or "").strip())
    if m and 1 <= int(m.group(2)) <= 12:
        return "%s %s" % (_MONTHS[int(m.group(2)) - 1], m.group(1))
    return (period or "").strip()


def _whole(value):
    """round() for a sparkline end; a stored inf (an upload from before
    the parser refused one) cannot be rounded and reads as nothing."""
    return round(value) if math.isfinite(value) else None


def _fmt_list(names):
    names = list(names)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _line_names(store, lines):
    """The payee lines under a store, minus the store's own name."""
    out = []
    low = store.lower()
    for line in lines:
        name = line.strip()
        if name.lower().startswith(low):
            name = name[len(store):].strip(" :-·")
        if name and name.lower() != low:
            out.append(name)
    return out


def ladder(analysis, limit=11):
    """Stores, biggest first, each with its payee lines folded under it."""
    by_source = analysis["by_source"]
    amount = {s["source"]: s["amount"] for s in by_source}
    rows = []
    for store, lines in store_identity.group(list(amount)).items():
        total = round(sum(amount[l] for l in lines), 2)
        rows.append({
            "store": store,
            "amount": total,
            "line_count": len(lines),
            "line_names": _line_names(store, lines) if len(lines) > 1 else [],
            "deliverable": store_identity.is_deliverable(store),
        })
    rows.sort(key=lambda r: (-r["amount"], r["store"]))
    top = rows[0]["amount"] if rows else 0
    shown, tail = rows[:limit], rows[limit:]
    total = sum(r["amount"] for r in rows) or 0
    top3 = rows[:3]
    # A stored inf (an upload from before the parser refused one) makes
    # inf / inf, which is nan and cannot be rounded; the share is unread.
    top3_share = (round(100.0 * sum(r["amount"] for r in top3) / total)
                  if total and math.isfinite(total) else 0)
    return {
        "rows": shown,
        "top": top,
        "tail": tail,
        "tail_amount": round(sum(r["amount"] for r in tail), 2),
        "tail_names": [r["store"] for r in tail],
        "tail_lines": sum(r["line_count"] for r in tail),
        "store_count": len(rows),
        "society_count": sum(1 for r in rows if not r["deliverable"]),
        "top3_note": ("%s paid %d%% of it" % (_fmt_list(r["store"] for r in top3), top3_share)
                      if len(rows) >= 3 and total else ""),
        "cells": [{"lit": r["deliverable"]} for r in rows],
    }


def instruments(analysis, uploads, trend, unmatched_rows, ladder_view):
    """The four readings on the money bridge."""
    a = analysis
    out = []

    # Reported earnings - actual, with movement between the last two periods.
    spark = meters.sparkline(trend) if len(trend) >= 2 else None
    delta = meters.pct_change(trend[-2][1], trend[-1][1]) if len(trend) >= 2 else None
    if delta is not None:
        delta_text = "%+.1f%% · %s vs %s" % (delta, period_label(trend[-1][0]),
                                             period_label(trend[-2][0]))
        tone = "up" if delta > 0.05 else ("down" if delta < -0.05 else "flat")
    elif len(trend) == 1:
        delta_text, tone = "one period: %s" % period_label(trend[0][0]), "flat"
    else:
        delta_text, tone = "no period on the rows", "flat"
    out.append({
        "key": "earnings", "label": "Reported earnings",
        "tag": "actual", "tag_text": "actual", "est": False,
        "shown": money(a["total"]), "delta_text": delta_text, "delta_tone": tone,
        "spark": spark,
        "spark_first": ("%s $%s" % (period_label(trend[0][0]), meters.short(_whole(trend[0][1])))
                        if spark else ""),
        "spark_last": ("%s $%s" % (period_label(trend[-1][0]), meters.short(_whole(trend[-1][1])))
                       if spark else ""),
        "note": "" if spark else "One statement period so far; a second one draws the line.",
        "cells": [],
        "prov": ["%d statement%s" % (len(uploads), "" if len(uploads) == 1 else "s"),
                 "%s rows" % "{:,}".format(a["row_count"]),
                 "%d period%s" % (a["period_count"], "" if a["period_count"] == 1 else "s")],
    })

    # Stores that paid - a count read off the rows.
    out.append({
        "key": "stores", "label": "Stores that paid",
        "tag": "derived", "tag_text": "counted", "est": False,
        "shown": "%d" % a["store_count"],
        "delta_text": "across %d payee line%s" % (a["source_count"], "" if a["source_count"] == 1 else "s"),
        "delta_tone": "flat", "spark": None, "spark_first": "", "spark_last": "",
        "note": ladder_view["top3_note"],
        "cells": ladder_view["cells"],
        "prov": ["Store names", "one store, however many lines it reports under"]
                + (["%d %s licensing, not a store" % (ladder_view["society_count"],
                                                       "is" if ladder_view["society_count"] == 1 else "are")]
                   if ladder_view["society_count"] else []),
    })

    # Coverage gaps - an estimate, and it looks like one.
    gaps = a["coverage_gaps"]
    share = (100.0 * a["gap_estimate_total"] / a["total"]) if a["total"] else 0.0
    out.append({
        "key": "gaps", "label": "Coverage gaps",
        "tag": "estimate", "tag_text": "estimate", "est": bool(gaps),
        "shown": money(a["gap_estimate_total"]),
        "delta_text": "%d track%s" % (len(gaps), "" if len(gaps) == 1 else "s"),
        "delta_tone": "flat", "spark": None, "spark_first": "", "spark_last": "",
        "note": ("Tracks paid by some stores and not others. Weighted by what each silent "
                 "store actually paid you, not a flat average per store."
                 if gaps else
                 "No track is silent on a store where the rest of your catalogue earns."),
        "cells": [],
        "prov": (["%.1f%% of reported" % share, "a priority order, not a promise"]
                 if gaps else ["Nothing to chase here"]),
    })

    # Unmatched revenue - actual: money that arrived without a track name.
    out.append({
        "key": "unmatched", "label": "Unmatched revenue",
        "tag": "actual", "tag_text": "actual", "est": False,
        "shown": money(a["unmatched_revenue"]),
        "delta_text": "%d row%s" % (unmatched_rows, "" if unmatched_rows == 1 else "s"),
        "delta_tone": "down" if a["unmatched_revenue"] > 0 else "flat",
        "spark": None, "spark_first": "", "spark_last": "",
        "note": ("Rows with no track title. Money that arrived without a name is money "
                 "you cannot claim against a song."),
        "cells": [],
        "prov": (["On your statement", "ask the distributor to name the track"]
                 if a["unmatched_revenue"] > 0 else ["Nothing to chase here"]),
    })
    return out


def tracks(analysis, gap_by_title, dots=10):
    """Each track with what it earned and how many of the stores it reached."""
    of = analysis["store_count"]
    out = []
    for i, t in enumerate(analysis["by_track"], 1):
        filled = round(dots * t["stores"] / of) if of else 0
        filled = min(dots, max(1 if t["stores"] else 0, filled))
        gap = gap_by_title.get(t["title"])
        out.append({
            "rank": i, "title": t["title"], "untitled": t["title"] == "(no title)",
            "amount": t["amount"], "stores": t["stores"], "of": of,
            "dots": [True] * filled + [False] * (dots - filled),
            "gap": gap, "slug": slug(t["title"]) if gap is not None else "",
        })
    return out


def _checkable():
    """The platforms a store check can ask by ISRC: Deezer and Spotify
    directly, and every store Songstats reports on when it is configured.
    Read at call time, not import time, so a key set on the deployment
    widens the list without a restart of anything here."""
    platforms = set(coverage_check.CHECKABLE)
    try:
        import signal_providers as sp
        if sp.SongstatsAdapter().configured():
            platforms |= set(coverage_check.SONGSTATS_ALIASES.values())
    except Exception:                                          # noqa: BLE001
        pass
    return platforms


def _check_note(chips, check, isrc, askable):
    if not isrc:
        return ("No ISRC on this track's rows, so no store can be asked about the "
                "recording. Upload a statement with an ISRC column to check.")
    if check is None:
        if askable:
            return ("Not checked yet. %s answer%s by ISRC; the rest have no public "
                    "catalogue lookup here." % (_fmt_list(askable), "s" if len(askable) == 1 else ""))
        return "Not checked yet. None of these stores can be asked by ISRC here."
    when = (check.get("checked") or "")[:10]
    result = check.get("result") or {}
    if not result.get("ok"):
        return "Checked %s: %s." % (when, result.get("why") or "no store could be asked")
    answered = [c["source"] for c in chips if c["state"] != "unchecked"]
    if answered:
        return ("Checked %s. %s answered by ISRC; the rest could not be asked."
                % (when, _fmt_list(answered)))
    return "Checked %s. No store on this list could be asked." % when


def gap_cards(findings, analysis, checks, cases, isrc_by_title, floor=1.0):
    """One card per coverage gap, with its silent stores sorted into states."""
    stores_by_title = {t["title"]: t["stores"] for t in analysis["by_track"]}
    case_by_key = {c.get("finding_key"): c["id"] for c in cases
                   if c.get("finding_key") and not c.get("closed_at")}
    cards = []
    for f in findings:
        if f.get("kind") != "coverage_gap":
            continue
        title = f["track"]
        key = slug(title)
        check = checks.get(key)
        result = (check or {}).get("result") or {}
        carried = {c["source"] for c in result.get("carried", [])}
        absent = set(result.get("absent", []))
        missing = list(f.get("missing") or [])
        chips = [{"source": s,
                  "state": "carried" if s in carried else ("absent" if s in absent else "unchecked"),
                  "url": next((c["url"] for c in result.get("carried", []) if c["source"] == s), "")}
                 for s in missing]
        chips.sort(key=lambda c: ({"carried": 0, "absent": 1, "unchecked": 2}[c["state"]], c["source"]))
        isrc = isrc_by_title.get(title, "")
        askable = sorted({store_identity.store_of(s) for s in missing
                          if coverage_check.platform_for(s) in _checkable()})
        case_id = case_by_key.get(f.get("case_key"))
        cards.append({
            "slug": key, "title": title, "amount": f["amount"],
            "confidence": f.get("confidence", ""),
            "earns_on": stores_by_title.get(title, 0), "silent": len(missing),
            "chips": chips, "isrc": isrc, "checked": (check or {}).get("checked", "")[:10],
            "check_note": _check_note(chips, check, isrc, askable),
            "askable": askable,
            "carried_count": len(carried), "absent_count": len(absent),
            "case_key": f.get("case_key", ""), "case_title": f.get("case_title", ""),
            "case_category": f.get("case_category", ""), "detail": f.get("detail", ""),
            "action": f.get("action", ""), "has_case": bool(case_id),
            "case_id": case_id or "",
            "letter_href": ("/royalty-recovery/cases/%s/letter" % case_id) if case_id else "",
        })
    featured_n = max(2, sum(1 for c in cards if c["amount"] >= floor))
    featured, tail = cards[:featured_n], cards[featured_n:]
    return {
        "featured": featured, "tail": tail,
        "tail_under_floor": bool(tail) and all(c["amount"] < floor for c in tail),
        "count": len(cards),
    }


def build(analysis, rows, uploads, findings, checks, cases):
    """Everything statements.html reads, from one pass over the rows."""
    if analysis is None:
        return None
    monthly = {}
    unmatched_rows = 0
    isrc_by_title = {}
    for r in rows:
        if r.get("period"):
            monthly[r["period"]] = monthly.get(r["period"], 0) + (r.get("amount") or 0)
        title = (r.get("title") or "").strip()
        if not title:
            unmatched_rows += 1
        elif r.get("isrc") and title not in isrc_by_title:
            isrc_by_title[title] = r["isrc"]
    trend = [(p, round(v, 2)) for p, v in sorted(monthly.items())][-12:]
    ladder_view = ladder(analysis)
    gap_by_title = {g["title"]: g["estimated_value"] for g in analysis["coverage_gaps"]}
    return {
        "instruments": instruments(analysis, uploads, trend, unmatched_rows, ladder_view),
        "ladder": ladder_view,
        "tracks": tracks(analysis, gap_by_title),
        "gaps": gap_cards(findings, analysis, checks, cases, isrc_by_title),
        "last_received": next((u for u in uploads if u.get("via") == "email"), None),
    }

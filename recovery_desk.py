"""The Recovery page, as approved from the numbered mockup of 2026-09-13.

A view over recovery_engine.build(), recovery_mlc.state() and the gap
checks the artist ran. Nothing is measured here; the numbers are read
once from those and laid out so their basis is never lost:

  actual    unattributed rows - money on the statement with no track named
  estimate  coverage gaps - weighted by what each silent store paid
  registry  what The MLC said about each ISRC, in money the title has
            already earned; at risk, never owed

The three are stood side by side as columns and never added into one
headline, because an actual dollar and an estimated one are not the
same dollar. Each finding carries its state and one next step; a case
is the action, edited in a strip in the page's own flow.
"""
import statements_desk
import store_identity


def _label(period):
    return statements_desk.period_label(period)


def _period_span(rows):
    # Calendar order, not name order: sorted() put "JUN-26" before "MAY-26"
    # and the live scan strip read "JUN-26 – MAY-26" (walk of 2026-09-14).
    import royalties_desk
    periods = royalties_desk.order_periods((r.get("period") or "").strip() for r in rows if r.get("period"))
    if not periods:
        return ""
    if len(periods) == 1:
        return _label(periods[0])
    return "%s – %s" % (_label(periods[0]), _label(periods[-1]))


def scan(rv, analysis, rows, uploads, mlc, checks):
    """What the page read before it said anything, and when the two
    on-demand checks last ran."""
    facts = ["%d statement%s" % (len(uploads), "" if len(uploads) == 1 else "s"),
             "%s statement row%s" % ("{:,}".format(rv["row_count"]), "" if rv["row_count"] == 1 else "s")]
    if analysis:
        facts.append("%d store%s" % (analysis["store_count"], "" if analysis["store_count"] == 1 else "s"))
        span = _period_span(rows)
        facts.append("%d period%s%s" % (rv["period_count"], "" if rv["period_count"] == 1 else "s",
                                        (" · " + span) if span else ""))
    ready = len((mlc or {}).get("ready") or [])
    facts.append("%d Track Passport%s with an ISRC" % (ready, "" if ready == 1 else "s"))
    last_check = max((c.get("checked") or "" for c in checks.values()), default="")
    latest = (mlc or {}).get("latest")
    when = []
    when.append("Stores last asked %s" % last_check[:10] if last_check else "Stores not asked yet")
    if mlc and mlc.get("on"):
        when.append("The MLC last checked %s" % latest["created"][:10] if latest else "The MLC not checked yet")
    else:
        when.append("The MLC is not connected")
    return {"facts": facts, "when": " · ".join(when)}


def registry_at_risk(mlc):
    """Money the titles have already earned whose work The MLC has no
    claim on, summed over the latest sweep's gap rows. None when no
    sweep has run - not zero."""
    latest = (mlc or {}).get("latest")
    if not latest:
        return None
    rows = [r for r in latest.get("rows", []) if r.get("gap")]
    return {"amount": round(sum(r.get("case_amount") or 0 for r in rows), 2),
            "works": len(rows), "checked": latest["created"][:10]}


def stake(rv, registry, gap_count):
    """The three bases as columns. Heights are shares of the largest."""
    cols = [
        {"key": "actual", "label": "Unattributed", "tag": "actual", "tag_text": "actual",
         "amount": rv["actual_unattributed"], "est": False,
         "sub": "%d row%s" % (rv["_unattributed_rows"], "" if rv["_unattributed_rows"] == 1 else "s"),
         "note": "Paid with no track named. On the statement."},
        {"key": "estimate", "label": "Coverage gaps", "tag": "estimate", "tag_text": "estimate",
         "amount": rv["estimated_gaps"], "est": True,
         "sub": "%d track%s" % (gap_count, "" if gap_count == 1 else "s"),
         "note": "Weighted by what each silent store paid. A priority order."},
        {"key": "registry", "label": "At The MLC", "tag": "registry", "tag_text": "registry",
         "amount": registry["amount"] if registry else None, "est": False,
         "sub": ("%d work%s" % (registry["works"], "" if registry["works"] == 1 else "s")
                 if registry else "no check run yet"),
         "note": "Already earned, work unregistered. At risk, not owed."},
    ]
    top = max((c["amount"] or 0 for c in cols), default=0)
    for c in cols:
        if c["amount"] is None:
            c["state"], c["height"] = "unchecked", 0
        elif c["amount"] <= 0:
            c["state"], c["height"] = "zero", 0
        else:
            c["state"] = "value"
            c["height"] = max(4, round(100.0 * c["amount"] / top)) if top else 0
        # A real zero prints $0.00. A column nobody has checked used to print
        # a dash, while the legend below it said a dashed column WAS a real
        # zero, so one glyph carried two opposite meanings. Nothing checked
        # says so in words.
        c["shown"] = (statements_desk.money(c["amount"])
                      if c["amount"] is not None else "Not checked")
    return cols


def checked(gaps, checks):
    """How many gaps have been put to the stores, one cell per gap."""
    cells = [bool(checks.get(statements_desk.slug(g["title"]))) for g in gaps]
    n = sum(cells)
    return {"n": n, "of": len(cells), "cells": cells,
            "note": ("%d gap%s not asked yet. Deezer, Spotify and Apple Music answer by ISRC."
                     % (len(cells) - n, "" if len(cells) - n == 1 else "s")
                     if len(cells) > n else
                     ("Every gap has been put to the stores." if cells else "No gaps to ask about."))}


RAIL = ("Opened", "Sent", "Waiting", "Answered")


def rail(case):
    """How far a case has travelled, lit only as far as the record goes."""
    status = case.get("status") or "open"
    sent = bool(case.get("evidence_at")) or status in ("submitted", "waiting", "won", "lost")
    waiting = status in ("waiting", "won", "lost")
    answered = status in ("won", "lost")
    lit = [True, sent, waiting, answered]
    now = max(i for i, on in enumerate(lit) if on)
    return [{"label": RAIL[i], "on": on, "now": i == now} for i, on in enumerate(lit)]


def cases_view(cases):
    open_cases = [c for c in cases if c["status"] in ("open", "submitted", "waiting")]
    won = [c for c in cases if c["status"] == "won"]
    for c in open_cases:
        c["rail"] = rail(c)
    return {
        "open": open_cases, "open_count": len(open_cases), "won_count": len(won),
        "pipeline": round(sum(c["estimated_amount"] or 0 for c in open_cases), 2),
        "recovered": round(sum(c.get("payout_result") or 0 for c in won), 2),
        "newest": open_cases[0] if open_cases else None,
    }


def gap_rows(cards):
    """The ledger's estimate rows: the statements-desk gap cards with their
    silent stores folded into one strip and counted in words."""
    out = []
    for g in cards:
        states = [c["state"] for c in g["chips"]]
        carried, absent = states.count("carried"), states.count("absent")
        unchecked = states.count("unchecked")
        cap = []
        if carried:
            cap.append(("carried", "%d carr%s it, paid nothing" % (carried, "ies" if carried == 1 else "y")))
        if absent:
            cap.append(("absent", "%d not listed" % absent))
        if unchecked:
            cap.append(("unchecked", "%d not asked" % unchecked))
        if carried:
            lamp, lamp_tone, step = "Carried, unpaid", "warn", "letter"
        elif g["checked"]:
            lamp, lamp_tone, step = "Checked", "good", "case"
        else:
            lamp, lamp_tone, step = "Not checked", "none", "check"
        if g["has_case"]:
            lamp, lamp_tone = "Case open", "good"
        g.update({"strip": states, "caption": cap, "lamp": lamp, "lamp_tone": lamp_tone, "step": step})
        out.append(g)
    return out


def registry_rows(mlc):
    """The MLC's gap rows for the ledger, and every row as a claim meter."""
    latest = (mlc or {}).get("latest")
    if not latest:
        return {"gaps": [], "all": [], "claimed": []}
    rows = latest.get("rows", [])
    for r in rows:
        if r.get("result") == "match":
            r["claimed_pct"] = max(0.0, min(100.0, float(r.get("share_total") or 0)))
            r["meter"] = "full" if r["claimed_pct"] >= 99.5 else "partial"
        elif r.get("result") == "none":
            r["claimed_pct"], r["meter"] = 0.0, "none"
        else:
            r["claimed_pct"], r["meter"] = 0.0, "error"
    gaps = [r for r in rows if r.get("gap")]
    claimed = [r for r in rows if not r.get("gap") and r.get("meter") == "full"]
    return {"gaps": gaps, "all": rows, "claimed": claimed}


def sits(rv):
    """Unattributed money under the source that paid it, a gap under the
    silent store: one bar each, the actual part drawn in its own tone."""
    rows = rv.get("by_source") or []
    top = rows[0]["amount"] if rows else 0
    return {"rows": rows, "top": top,
            "any_actual": any(r.get("actual") for r in rows),
            "any_estimated": any(r.get("estimated") for r in rows)}


def build(rv, analysis, rows, uploads, mlc, checks, cases, isrc_by_title):
    if not rv or not rv.get("has_data"):
        return None
    rv["_unattributed_rows"] = sum(1 for r in rows if not (r.get("title") or "").strip()
                                   and (r.get("amount") or 0) > 0)
    gaps = analysis["coverage_gaps"] if analysis else []
    cards = statements_desk.gap_cards(rv["findings"], analysis, checks, cases, isrc_by_title)
    registry = registry_at_risk(mlc)
    # The case behind an unattributed finding, so its row can open the
    # strip rather than offer a second case.
    case_by_key = {c.get("finding_key"): c["id"] for c in cases
                   if c.get("finding_key") and not c.get("closed_at")}
    for f in rv["findings"]:
        if f["kind"] == "unattributed":
            f["case_id"] = case_by_key.get(f.get("case_key"), "")
            f["has_case"] = f["has_case"] or bool(f["case_id"])
    return {
        "scan": scan(rv, analysis, rows, uploads, mlc, checks),
        "stake": stake(rv, registry, len(gaps)),
        "registry": registry,
        "checked": checked(gaps, checks),
        "cases": cases_view(cases),
        "actual": [f for f in rv["findings"] if f["kind"] == "unattributed"],
        "gaps": {"featured": gap_rows(cards["featured"]), "tail": gap_rows(cards["tail"]),
                 "tail_under_floor": cards["tail_under_floor"], "count": cards["count"]},
        "mlc_rows": registry_rows(mlc),
        "sits": sits(rv),
    }

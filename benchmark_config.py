"""Config-driven data for the Benchmarking page.

Compares the signed-in account's own catalog metrics against illustrative
peer averages, so each metric shows whether they are ahead of or behind
the pack. The peer column is invented and says so. The "you" column must
therefore be the account's own or the page is worthless: a comparison is
only as honest as its left-hand side.

It was not. Four of the five "you" values came from royalty_data.get_songs(),
the five-song demo catalogue - so a brand-new account with nothing
uploaded rendered "Total streams - You: 11,990,000", which is
sum(s.streams for s in get_songs()) and belongs to nobody. The page
asserted the opposite in three places: the parked banner, the footnote
under the table, and docs/PARKED_PAGES.md, which parks it for the peer
half only.

Statements carry earnings, titles and periods. They do not carry stream
counts, and nothing else here does either, so Total streams is reported
as not measured rather than borrowed. An unmeasured metric is not
compared: there is no percentage, no ahead/behind badge and no bar,
because all three would be claims about a number nobody has.
"""

import statements_engine
from royalty_data import estimate_catalog_value, get_earnings_trend


def _pct_diff(you, peer):
    if not peer:
        return 0.0
    return round((you - peer) / peer * 100, 1)


def get_benchmark_data(statement_rows=None):
    """`statement_rows` are the signed-in account's own uploaded rows.

    With none, every "you" value is None and the page says so. That is
    the honest reading for an account that has uploaded nothing, and it
    is what a new artist sees: a peer column, an empty own column, and a
    sentence explaining what to upload.
    """
    summary = statements_engine.build_royalty_summary(statement_rows or []) or {}
    by_track = summary.get("by_track") or []

    total_earned = summary.get("total")
    catalog_size = len(by_track) or None
    avg_per_track = (round(total_earned / len(by_track), 2)
                     if total_earned is not None and by_track else None)

    # Est. catalog value: the same figure /valuation and the press kit
    # show, computed by the same rule, so nothing in the app disagrees.
    # The illustrative fallback is gone - it was the trend of a catalogue
    # that is not this account's.
    catalog_value = (summary.get("valuation") or {}).get("mid")

    metrics = [
        # Statements record money, not plays. Nothing in this app measures
        # an artist's stream count, so this row stays empty rather than
        # reporting somebody else's.
        {"label": "Total streams", "you": None, "peer": 9_500_000, "fmt": "int",
         "why_absent": "Statements record earnings, not plays."},
        {"label": "Catalog earnings", "you": total_earned, "peer": 14_500, "fmt": "money",
         "why_absent": "Upload a statement."},
        {"label": "Avg. earnings / track", "you": avg_per_track, "peer": 2_400, "fmt": "money",
         "why_absent": "Upload a statement."},
        {"label": "Est. catalog value", "you": catalog_value, "peer": 240_000, "fmt": "money",
         "why_absent": "Needs statement history to value."},
        {"label": "Catalog size", "you": catalog_size, "peer": 8, "fmt": "int",
         "why_absent": "Counted from titles on your statements."},
    ]
    for m in metrics:
        m["measured"] = m["you"] is not None
        if m["measured"]:
            m["you"] = round(m["you"], 2) if m["fmt"] == "money" else m["you"]
            m["diff_pct"] = _pct_diff(m["you"], m["peer"])
            m["ahead"] = m["you"] >= m["peer"]
        else:
            # No comparison exists, so none is offered. A 0% or a "behind"
            # badge here would both be statements about a missing number.
            m["diff_pct"] = None
            m["ahead"] = None

    measured = [m for m in metrics if m["measured"]]
    ahead = sum(1 for m in measured if m["ahead"])
    return {
        "summary": {
            "metrics": len(metrics),
            "measured": len(measured),
            "ahead": ahead,
            "behind": len(measured) - ahead,
            "peer_group": "Independent · Electronic/Synth-pop",
        },
        "metrics": metrics,
    }

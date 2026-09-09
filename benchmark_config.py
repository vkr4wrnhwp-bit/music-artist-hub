"""Config-driven data for the Benchmarking page.

Compares the artist's real catalog metrics against illustrative peer
averages for artists at a similar stage, so each metric shows whether
you're ahead of or behind the pack. Your own numbers are real; the peer
averages are illustrative reference points.
"""

import statements_engine
from royalty_data import get_songs, estimate_catalog_value, get_earnings_trend


def _pct_diff(you, peer):
    if not peer:
        return 0.0
    return round((you - peer) / peer * 100, 1)


def get_benchmark_data(statement_rows=None):
    """`statement_rows` are the signed-in account's own uploaded rows.

    Est. catalog value is the one metric here a label would quote back,
    and it used to be 12x an illustrative trend while /valuation and the
    press kit showed 4x the artist's real run rate. When the account has
    statements the figure is now the same one those pages show, computed
    by the same rule (catalog_value, via statements_engine). With no
    statements it falls back to the illustrative trend the rest of this
    parked page already uses - at the same multiple, so nothing on the
    page disagrees with anything else in the app.
    """
    songs = get_songs()
    total_streams = sum(s.streams for s in songs)
    total_earned = sum(s.total_earned for s in songs)
    avg_per_track = round(total_earned / len(songs), 2) if songs else 0.0
    summary = statements_engine.build_royalty_summary(statement_rows or []) or {}
    catalog_value = ((summary.get("valuation") or {}).get("mid")
                     or estimate_catalog_value(get_earnings_trend())["mid"])

    # Illustrative peer averages for a similar-stage independent artist.
    metrics = [
        {"label": "Total streams", "you": total_streams, "peer": 9_500_000, "fmt": "int"},
        {"label": "Catalog earnings", "you": round(total_earned, 2), "peer": 14_500, "fmt": "money"},
        {"label": "Avg. earnings / track", "you": avg_per_track, "peer": 2_400, "fmt": "money"},
        {"label": "Est. catalog value", "you": round(catalog_value, 2), "peer": 240_000, "fmt": "money"},
        {"label": "Catalog size", "you": len(songs), "peer": 8, "fmt": "int"},
    ]
    for m in metrics:
        m["diff_pct"] = _pct_diff(m["you"], m["peer"])
        m["ahead"] = m["you"] >= m["peer"]

    ahead = sum(1 for m in metrics if m["ahead"])
    return {
        "summary": {
            "metrics": len(metrics),
            "ahead": ahead,
            "behind": len(metrics) - ahead,
            "peer_group": "Independent · Electronic/Synth-pop",
        },
        "metrics": metrics,
    }

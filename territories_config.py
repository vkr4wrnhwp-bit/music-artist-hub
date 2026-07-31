"""ILLUSTRATIVE territory data. Wired to nothing, and it must stay that way.

These are hardcoded percentages, not an artist's money. The real
per-country income is parsed out of uploaded statements and lives in
statement_rows.territory; royalty_types.territory_report reads it and
/territories renders that. Use those.

This module previously fed insights_config, which built a ranked list of
"money you are not collecting" - gap_countries and uncollected_total -
entirely from the figures below, and imported itself into app.py. It was
never called, so nothing fabricated ever reached a user. But wiring it to
a page would have been one line, and the line would have looked
reasonable. insights_config has been deleted for that reason.

If you are about to import this into a route: the number you want is
already in the database.
"""
from royalty_data import get_songs

# Illustrative streaming distribution by territory (shares sum to ~1.0).
# collecting=True means we're set up to collect everything owed there;
# False means public-performance / neighboring income is going uncollected.
_TERRITORY_SHARES = [
    {"country": "United States", "flag": "US", "share": 0.42, "collecting": True},
    {"country": "United Kingdom", "flag": "GB", "share": 0.14, "collecting": False},
    {"country": "Germany", "flag": "DE", "share": 0.11, "collecting": False},
    {"country": "Canada", "flag": "CA", "share": 0.08, "collecting": True},
    {"country": "Australia", "flag": "AU", "share": 0.07, "collecting": False},
    {"country": "Netherlands", "flag": "NL", "share": 0.06, "collecting": False},
    {"country": "France", "flag": "FR", "share": 0.06, "collecting": False},
    {"country": "Brazil", "flag": "BR", "share": 0.06, "collecting": False},
]

# Illustrative share of a territory's earnings recoverable when we're not
# set up to collect public-performance / neighboring income there.
_UNCOLLECTED_SHARE = 0.14


def get_territories_data():
    total_earned = sum(s.total_earned for s in get_songs())

    territories = []
    for t in _TERRITORY_SHARES:
        earnings = round(total_earned * t["share"], 2)
        uncollected = 0.0 if t["collecting"] else round(earnings * _UNCOLLECTED_SHARE, 2)
        if t["collecting"]:
            status = "Collecting"
        elif uncollected > 0:
            status = "Gap"
        else:
            status = "Uncollected"
        territories.append({
            "country": t["country"],
            "flag": t["flag"],
            "earnings": earnings,
            "uncollected": uncollected,
            "share_pct": round(t["share"] * 100, 1),
            "collecting": t["collecting"],
            "status": status,
        })

    territories.sort(key=lambda x: x["earnings"], reverse=True)
    collected_total = round(sum(t["earnings"] for t in territories), 2)
    uncollected_total = round(sum(t["uncollected"] for t in territories), 2)
    gap_countries = sum(1 for t in territories if not t["collecting"])

    return {
        "summary": {
            "countries": len(territories),
            "collected_total": collected_total,
            "uncollected_total": uncollected_total,
            "gap_countries": gap_countries,
            "collecting_countries": len(territories) - gap_countries,
        },
        "territories": territories,
        "max_earnings": max((t["earnings"] for t in territories), default=0),
    }

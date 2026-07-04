"""Config-driven data for the Territories / Global royalties page.

Shows where earnings come from by country and — more importantly — where
money is being left uncollected because the artist isn't set up to
collect in that territory. The app doesn't track per-country earnings,
so the geographic split is illustrative, but it's scaled off the real
total catalog earnings so the numbers stay consistent with the rest of
the app. Collection status mirrors the neighboring-rights gaps.
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

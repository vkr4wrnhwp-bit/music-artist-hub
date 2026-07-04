"""Config-driven data for the Tax Center.

Pulls together the year-end tax picture: earnings YTD (real, from the
catalog), a recommended set-aside, tax forms (1099s), withholding, and
the taxpayer forms on file (W-9 / W-8BEN). The set-aside percentage and
withholding figures are illustrative, not tax advice; earnings totals
are real.
"""

from datetime import date

from royalty_data import get_songs

# Illustrative self-employment set-aside rate. Not tax advice.
_SET_ASIDE_RATE = 0.25


def get_tax_data():
    tax_year = date.today().year - 1
    ytd_earnings = round(sum(s.total_earned for s in get_songs()), 2)
    set_aside = round(ytd_earnings * _SET_ASIDE_RATE, 2)

    forms = [
        {"name": "1099-NEC", "issuer": "DistroKid (distribution)", "year": tax_year, "status": "Available", "amount": round(ytd_earnings * 0.55, 2)},
        {"name": "1099-MISC", "issuer": "ASCAP (performance)", "year": tax_year, "status": "Available", "amount": round(ytd_earnings * 0.18, 2)},
        {"name": "1099-K", "issuer": "Merch / direct sales", "year": tax_year, "status": "Pending", "amount": 0.0},
    ]
    forms_available = sum(1 for f in forms if f["status"] == "Available")

    withholding = [
        {"label": "US backup withholding", "amount": 0.0, "note": "None — W-9 on file"},
        {"label": "Foreign withholding (intl royalties)", "amount": round(ytd_earnings * 0.03, 2), "note": "Reclaimable via tax treaty"},
    ]
    withheld_total = round(sum(w["amount"] for w in withholding), 2)

    tax_profile = [
        {"form": "W-9", "purpose": "US taxpayer identification", "on_file": True},
        {"form": "W-8BEN", "purpose": "Foreign society treaty benefits", "on_file": False},
    ]

    return {
        "summary": {
            "tax_year": tax_year,
            "ytd_earnings": ytd_earnings,
            "set_aside": set_aside,
            "set_aside_rate": int(_SET_ASIDE_RATE * 100),
            "forms_available": forms_available,
            "forms_total": len(forms),
            "withheld_total": withheld_total,
        },
        "forms": forms,
        "withholding": withholding,
        "tax_profile": tax_profile,
    }

"""Config-driven data for the Billing / subscription page.

Shows the current plan (from the shared account config), usage this
period derived from real catalog/connection counts, past invoices, and
the available plans to compare. Invoices and prices are illustrative;
this is a demo — no payment method is ever entered or charged.
"""

from royalty_data import get_songs, get_platform_catalog


PLANS = [
    {"id": "free", "name": "Free", "price": 0, "blurb": "Track your catalog and see what you're owed.",
     "features": ["Up to 10 songs", "1 connected source", "Basic recovery scan"]},
    {"id": "pro", "name": "Pro Plan", "price": 19, "blurb": "Full recovery, valuation, and publishing tools.",
     "features": ["Unlimited songs", "All source connections", "Recovery + claims", "Valuation & advances", "Publishing admin"]},
    {"id": "label", "name": "Label", "price": 49, "blurb": "For teams managing multiple artists.",
     "features": ["Everything in Pro", "Multi-artist roster", "Team permissions", "Priority support", "API access"]},
]


def get_billing_data(account):
    current_plan_name = account.get("plan", "Pro Plan")
    songs = get_songs()
    catalog = get_platform_catalog()
    connected = sum(1 for p in catalog if p.status == "connected")

    plans = [dict(p, current=(p["name"] == current_plan_name)) for p in PLANS]
    current = next((p for p in plans if p["current"]), plans[1])

    invoices = [
        {"id": "INV-2026-06", "date": "2026-06-01", "amount": current["price"], "status": "Paid"},
        {"id": "INV-2026-05", "date": "2026-05-01", "amount": current["price"], "status": "Paid"},
        {"id": "INV-2026-04", "date": "2026-04-01", "amount": current["price"], "status": "Paid"},
    ]

    return {
        "current_plan": current,
        "renews_on": "2026-08-01",
        "usage": [
            {"label": "Songs tracked", "value": len(songs)},
            {"label": "Sources connected", "value": connected},
            {"label": "Plan seats used", "value": 1},
        ],
        "plans": plans,
        "invoices": invoices,
    }

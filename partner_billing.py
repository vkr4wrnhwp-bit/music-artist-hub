"""What a white-label partner owes Street Banker each month.

Owner, 2026-09-17: per seat, not a share of revenue. A flat platform fee,
then every artist seat at a wholesale discount off the public price of the
membership the partner put it on. The partner charges its own artists
whatever it likes; that is its margin and none of our business.

This module only does the arithmetic and says how it got there. Nothing here
charges anybody: the owner invoices from the figure until partner billing is
wired to Stripe, and the screens that show it say so.
"""
import os

import stripe_provider

PLATFORM_FEE_CENTS = 49900      # a month, whatever the roster size
SEAT_DISCOUNT_PCT = 40          # off the public price of the seat's membership


def _platform_fee():
    try:
        return int(os.environ.get("PARTNER_PLATFORM_FEE_CENTS") or PLATFORM_FEE_CENTS)
    except ValueError:
        return PLATFORM_FEE_CENTS


def seat_price_cents(plan):
    """The wholesale monthly price of one seat on `plan`. A free Fan seat
    costs nothing, which is what lets a partner park an account."""
    listed = stripe_provider.PRICES.get(plan)
    if not listed:
        return 0
    return round(listed[0] * (100 - SEAT_DISCOUNT_PCT) / 100)


def statement(roster):
    """The month at today's roster: {"platform", "lines", "seats", "total"},
    all in cents. `roster` is partner_store.roster() rows. One line per
    membership in use, so the partner can check the count against its list."""
    counts = {}
    for row in roster:
        plan = row.get("plan") or "artist"
        counts[plan] = counts.get(plan, 0) + 1
    lines = []
    for plan, (listed, _name) in stripe_provider.PRICES.items():
        n = counts.get(plan, 0)
        if n:
            each = seat_price_cents(plan)
            lines.append({"plan": plan, "seats": n, "list": listed, "each": each, "cents": n * each})
    seats = sum(line["cents"] for line in lines)
    fee = _platform_fee()
    return {"platform": fee, "lines": lines, "seats": seats, "total": fee + seats,
            "free_seats": counts.get("fan", 0), "discount_pct": SEAT_DISCOUNT_PCT}

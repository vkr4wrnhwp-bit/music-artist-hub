"""The owner's Soundcharts allowance: counted, capped, split two ways.

Found by the 2026-09-18 check: nothing counted or limited Soundcharts
calls. Pulse (every customer) and Signal (the owner's team) spend one
monthly allowance, and a customer switching Pulse artists could spend it
without a stop. Soundcharts' own plans cap it (owner, 2026-09-19: "call cap
on free is 1000 on paid lowest is 10000").

What holds now:
  - every call that leaves for Soundcharts is counted, by month, as
    "customers" or "team" (Signal and the Operator Desk, and anything run
    outside a page, such as a scheduled job)
  - the owner sets the monthly budget in Settings; nothing set means
    DEFAULT_BUDGET
  - customers stop at CUSTOMER_SHARE of it, so the team always keeps the
    rest; the team stops at the budget itself
  - a stopped call is never a zero: the adapter serves the last answer it
    measured, and a page says fresh numbers are paused until next month
"""
from datetime import datetime, timezone

import db

BUDGET_KEY = "soundcharts_monthly_budget"
DEFAULT_BUDGET = 10000          # Soundcharts' lowest paid plan
CUSTOMER_SHARE = 0.8
# The owner's Providers page checks Soundcharts on the team's share too
# (its checks run off the request thread, which already counts as the
# team's; the path is named so a check made in-request is not a customer's).
TEAM_PATHS = ("/signal", "/operator-desk", "/admin/providers")


def month(now=None):
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


def _count_key(kind, mon=None):
    return "soundcharts_calls:%s:%s" % (mon or month(), kind)


def budget():
    try:
        return max(0, int(db.get_kv(BUDGET_KEY) or DEFAULT_BUDGET))
    except (TypeError, ValueError):
        return DEFAULT_BUDGET


def set_budget(n):
    db.set_kv(BUDGET_KEY, str(max(0, int(n))))


def who():
    """Whose call this is: the team's when it comes from Signal or the
    Operator Desk, or from outside any page; a customer's otherwise."""
    try:
        from flask import has_request_context, request
        if not has_request_context():
            return "team"
        return "team" if request.path.startswith(TEAM_PATHS) else "customers"
    except Exception:
        return "team"


def counts(mon=None):
    c = int(db.get_kv(_count_key("customers", mon)) or 0)
    t = int(db.get_kv(_count_key("team", mon)) or 0)
    return {"customers": c, "team": t, "total": c + t}


def customer_ceiling():
    return int(budget() * CUSTOMER_SHARE)


def allowed(kind=None):
    kind = kind or who()
    total = counts()["total"]
    return total < (customer_ceiling() if kind == "customers" else budget())


def customers_paused():
    return not allowed("customers")


def record(kind=None):
    db.kv_incr(_count_key(kind or who()))


def summary():
    """Everything a page needs to show the month."""
    c = counts()
    return dict(c, month=month(), budget=budget(), customer_ceiling=customer_ceiling(),
                customers_paused=customers_paused(), team_paused=not allowed("team"))

"""The showcase accounts, named once.

Four seeded logins tour what each plan buys. They are the ONLY addresses
that get showcase treatment anywhere in the product: the sample press
kit profile, the seeded links and reports, the instant plan switch on
Billing. Everything else is an ordinary account, whatever it is called.

The rule used to be "demo@streetbanker.io, or anything demo-*@ that
domain", stated three times in three files. The wildcard was an open
door: /signup accepts any address, so demo-anything@streetbanker.io
registered itself and took the Label plan free while Stripe was live
(scout of 2026-09-14). The set below is exact, and there is one copy.
"""

# (email, display name, plan)
ACCOUNTS = (
    ("demo@streetbanker.io", "Synthwave Surfer", "label"),
    ("demo-pro@streetbanker.io", "Synthwave Surfer (Pro)", "pro"),
    ("demo-artist@streetbanker.io", "Synthwave Surfer (Artist)", "artist"),
    ("demo-fan@streetbanker.io", "Demo Fan", "fan"),
)

EMAILS = frozenset(email for email, _name, _plan in ACCOUNTS)


def is_demo_email(email):
    """True only for the seeded showcase logins - exact addresses, never a
    pattern, so nobody can register their way into showcase treatment."""
    return (email or "").strip().lower() in EMAILS

"""The owner's switch for money that artists take from their fans online.

Owner, 2026-09-18, on VIP packages and paid fan clubs: "in a on off that i
control (they need to email for details)". Both take a stranger's fan's
money into the platform's Stripe account, settled with the artist by hand
and with no payout rail yet, so until the owner says so they are off. Off
is not hidden: the artist can still build the club or the packages, and a
fan who opens the page is told plainly to email for details rather than
shown a form that cannot be used.

One switch, stored in app_kv so the owner flips it in Settings with no
deploy. Nothing set means off.
"""
import db

KEY = "online_sales"
CONTACT = "hello@streetbankermusic.com"
CLOSED = "Online sales are by arrangement for now. Email %s for details." % CONTACT


def is_on():
    return (db.get_kv(KEY) or "off") == "on"


def set_on(on):
    db.set_kv(KEY, "on" if on else "off")

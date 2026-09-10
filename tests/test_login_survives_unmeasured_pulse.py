"""Logging in returned 500 because a score read a number that wasn't there.

Reported live, 2026-09-10: "this happens when i log in — Internal Server
Error". Login lands on the Command Center, the Command Center asks for
the qualification score, and the score read Spotify popularity as:

    snaps[-1].get("popularity", 0)

The `.get` default never fires, because the key IS present — holding
None, which is how a snapshot records "Spotify did not send a number".
`10 * None` raised, and every login on that account failed.

The lesson is the trap, not the line: `.get(key, default)` does nothing
for a key that exists with a null value.
"""
import uuid
from datetime import date, timedelta

import pytest

import app as appmod
import db as store
import qualification

PASSWORD = "login-null-123"


@pytest.fixture
def account():
    c = appmod.app.test_client()
    email = "login-%s@example.net" % uuid.uuid4().hex[:10]
    c.post("/signup", data={"name": "Owner", "email": email, "password": PASSWORD})
    with appmod.app.app_context():
        uid = store.get_user_by_email(email)["id"]
    return c, email, uid


def _snap(uid, followers, popularity, days_back):
    with appmod.app.app_context():
        store.record_pulse_snapshot(
            uid, followers, popularity, 9000,
            day=(date.today() - timedelta(days=days_back)).isoformat())


def test_logging_in_survives_a_history_of_unmeasured_snapshots(account):
    c, email, uid = account
    with appmod.app.app_context():
        store.save_pulse_profile(uid, "king810", "King 810")
    for back in (3, 2, 1):
        _snap(uid, None, None, back)
    r = c.post("/login", data={"email": email, "password": PASSWORD},
               follow_redirects=True)
    assert r.status_code == 200, "a number Spotify withheld must not block the door"


def test_an_unmeasured_popularity_scores_nothing_rather_than_raising(account):
    _c, _email, uid = account
    with appmod.app.app_context():
        store.save_pulse_profile(uid, "king810", "King 810")
    _snap(uid, None, None, 1)
    assert qualification._pulse_momentum(uid) == 0
    assert qualification._pts(None, 60) == 0, "not measured earns nothing, quietly"


def test_the_score_reads_the_newest_measurement_not_the_oldest(account):
    """Snapshots come oldest first — the current reading is the last one."""
    _c, _email, uid = account
    with appmod.app.app_context():
        store.save_pulse_profile(uid, "king810", "King 810")
    _snap(uid, 90000, 12, 30)     # old and low
    _snap(uid, 100500, 48, 5)     # current
    _snap(uid, None, None, 1)     # today, withheld
    # 48/60 -> 8, not 12/60 -> 2.
    assert qualification._pulse_momentum(uid) == 8

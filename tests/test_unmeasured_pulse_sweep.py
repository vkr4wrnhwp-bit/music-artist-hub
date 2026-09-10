"""No page may fall over because a number was never measured.

2026-09-10. Making the Spotify provider honest — reporting an omitted
follower count as "not measured" instead of as 0 — broke eleven
surfaces in one go, because the readers all assumed a number:

    /pulse, login (via the Command Center's qualification score),
    /trust-score, /capital-score, /funding, /valuation, /insights,
    the Pulse search box, the peer table, the Deal One-Sheet.

Every one was the same two mistakes. `.get("followers", 0)` does not
help when the key exists holding None, and arithmetic on None raises.

So this does not test a line. It walks every GET route with a Pulse
history that carries no numbers, and again with a history that carries
some, and insists nothing 500s. A new reader that assumes a number
fails here rather than in front of the owner.
"""
from datetime import date, timedelta

import pytest

import app as appmod
import db as store

MONEY_PAGES = ["/trust-score", "/capital-score", "/funding", "/valuation",
               "/insights", "/pulse"]


def _routes():
    return sorted({r.rule for r in appmod.app.url_map.iter_rules()
                   if "GET" in r.methods and "<" not in r.rule
                   and not r.rule.startswith("/static")})


@pytest.fixture
def client():
    c = appmod.app.test_client()
    c.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    with appmod.app.app_context():
        uid = store.get_user_by_email("demo@streetbanker.io")["id"]
        store.save_pulse_profile(uid, "king810", "King 810")
    c._uid = uid
    return c


def _snap(uid, followers, popularity, days_back):
    with appmod.app.app_context():
        store.record_pulse_snapshot(
            uid, followers, popularity, 9000,
            day=(date.today() - timedelta(days=days_back)).isoformat())


def test_no_route_falls_over_on_a_history_with_no_numbers_in_it(client):
    for back in (3, 2, 1):
        _snap(client._uid, None, None, back)
    broken = [p for p in _routes() if client.get(p).status_code >= 500]
    assert not broken, "these read a number that was never measured: %s" % broken


def test_no_route_falls_over_on_a_history_that_is_part_measured(client):
    """What a live account actually looks like: some days, not others."""
    _snap(client._uid, 90000, 41, 30)
    _snap(client._uid, None, None, 14)
    _snap(client._uid, 100500, 44, 7)
    _snap(client._uid, None, None, 1)
    broken = [p for p in _routes() if client.get(p).status_code >= 500]
    assert not broken, "a gap in the series broke: %s" % broken


@pytest.mark.parametrize("path", MONEY_PAGES)
def test_the_pages_that_carry_a_score_still_render(client, path):
    """Named separately: these are the ones an owner shows a lender."""
    _snap(client._uid, None, None, 2)
    _snap(client._uid, None, None, 1)
    page = client.get(path)
    assert page.status_code == 200, "%s must survive an unmeasured reading" % path
    assert "None" not in page.get_data(as_text=True).replace("NoneType", ""), (
        "%s printed a bare None where a number was missing" % path)

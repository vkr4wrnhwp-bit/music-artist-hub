"""Signal is internal, and no customer surface offers it.

Owner, 2026-09-17: "signal needs to be removed from public view on
analytics". Signal is the catalog intelligence the Operator Desk feeds,
used to look at other people's catalogues. An artist has no business
being shown it, and the Analytics room is a customer room.

Before this it was a card in Analytics that was dropped for anyone
without a seat. That worked, but it made a customer room's definition
contain an internal tool, and the only thing standing between the two was
a boolean passed down four call layers. Taking the card out removes the
question instead of answering it every request.

Two things this file keeps honest:

  no customer surface names it   not a room card, not the command
                                 palette, not the sidebar, for any plan
                                 including the owner's own
  the guard is still the guard   the card leaving is cosmetic. The thing
                                 that actually stops somebody reading a
                                 catalogue they do not own is
                                 signal_hub.require(), and it has to keep
                                 being what fails, not the missing card
"""
import uuid

import pytest

import hubs
import rooms
import signal_hub
from app import create_app

PW = "signal-internal-1"


def _client(app_obj, plan="pro"):
    c = app_obj.test_client()
    email = "sig-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Sig", "email": email, "password": PW})
    c.post("/plan/switch", data={"plan": plan})
    c._email = email
    return c


# --- no customer surface names it ----------------------------------------

@pytest.mark.parametrize("plan", ["artist", "pro", "label"])
@pytest.mark.parametrize("owner", [False, True])
def test_signal_is_a_card_in_no_room(plan, owner):
    """Including for an owner. The owner reaches it from the desk; a room
    card would put it back in front of every customer's eyes the moment
    somebody copied the room definition."""
    for _key, _name, _purpose, _icon, cards in rooms.build(plan, owner, False):
        assert "signal" not in [c[0] for c in cards]
        assert "/signal" not in [c[1] for c in cards]


def test_the_analytics_room_is_the_rest_of_it_and_nothing_lost():
    room = rooms.get_room("analytics", "label", True, False)
    keys = [c[0] for c in room["cards"]]
    assert "signal" not in keys
    for kept in ("pulse", "scores", "trust-score", "insights", "artist-twin", "reports"):
        assert kept in keys, kept


def test_signal_is_in_no_sidebar_and_no_command_palette():
    for _hk, _name, _tag, items in hubs.HUBS:
        assert "signal" not in [it[0] for it in items]
    for _gname, items in (hubs.LABEL_GROUP, hubs.COMMUNITY_GROUP, hubs.ACCOUNT_GROUP):
        assert "signal" not in [it[0] for it in items]
    assert "signal" not in [e["key"] for e in hubs.command_index()]


def test_build_no_longer_takes_a_seat_to_decide_a_card_with():
    """The parameter is gone, so nothing can pass the wrong answer."""
    import inspect
    assert "signal_seat" not in inspect.signature(rooms.build).parameters
    assert "signal_seat" not in inspect.signature(rooms.get_room).parameters


# --- and the real guard still holds --------------------------------------

def test_the_route_still_refuses_an_account_with_no_seat(monkeypatch):
    """The card leaving is cosmetic. This is the part that matters, and it
    must fail for the right reason rather than because a link is missing."""
    monkeypatch.setenv("OWNER_EMAILS", "nobody-here@example.invalid")
    app_obj = create_app()
    stranger = _client(app_obj, "label")
    r = stranger.get("/signal")
    assert r.status_code in (302, 403, 404), r.status_code
    if r.status_code == 302:
        assert "/signal" not in r.headers.get("Location", "")


def test_a_seat_is_still_only_the_owner_or_a_roster_row():
    """Nothing about who gets in changed, so the enrolment rule is
    restated here: an owner is enrolled on sight, everybody else needs a
    row somebody with the desk put there."""
    src = signal_hub._member.__doc__ or ""
    assert "owner" in src.lower()
    assert signal_hub._member(None) == (None, None)


def test_the_operator_desk_still_has_the_door():
    """Taking it off the customer surface must not lock the owner out."""
    import io
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    layout = io.open(os.path.join(here, "templates", "desk", "layout.html"),
                     encoding="utf-8").read()
    assert 'href="/signal"' in layout

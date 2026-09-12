"""Notification Preferences on Settings switched nothing.

The panel offered "weekly summary email", "payout received" and "new
song detected" - things the app does not do - and saved the toggles to
localStorage, which nothing server-side has ever read. It lists the
kinds the app actually raises now, saved on the account, and a kind
that is unticked is dropped by notify() before it is written.
"""
import uuid

import pytest

import db as store
from app import create_app

PW = "prefs-pass-12345"


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "prefs-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "P", "email": email, "password": PW})
    client._app = app_obj
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
    return client


def _titles(client):
    with client._app.app_context():
        return [n["title"] for n in store.list_notifications(client._uid)]


def test_the_panel_names_real_kinds_and_saves_on_the_account(artist):
    body = artist.get("/settings").get_data(as_text=True)
    assert 'action="/settings/notifications"' in body
    for gone in ("weekly_summary", "payout_received", "new_song_detected",
                 "royaltySweep.notifications"):
        assert gone not in body, gone
    panel = body[body.index('id="notification-preferences"'):body.index('action="/settings/notifications"')]
    assert "Saved on this device" not in panel, "Tutor Mode may be per-device; these are the account's"
    assert 'name="kind" value="fan"' in body and 'name="kind" value="recovery"' in body


def test_an_unticked_kind_is_dropped_before_it_is_written(artist):
    every = [k for k, _l, _d in store.NOTIFICATION_KINDS if k != "fan"]
    artist.post("/settings/notifications", data={"kind": every})
    with artist._app.app_context():
        store.notify(artist._uid, "fan", "A fan", "", "/fans")
        store.notify(artist._uid, "recovery", "A finding", "", "/recovery")
    assert _titles(artist) == ["A finding"]
    body = artist.get("/settings").get_data(as_text=True)
    assert 'value="fan" class="h-4 w-4 shrink-0 accent-[var(--sb-gold-bright)]">' in body, "fan reads unticked"


def test_ticking_it_again_lets_it_through(artist):
    artist.post("/settings/notifications", data={"kind": ["statement"]})
    artist.post("/settings/notifications",
                data={"kind": [k for k, _l, _d in store.NOTIFICATION_KINDS]})
    with artist._app.app_context():
        store.notify(artist._uid, "fan", "Back", "", "/fans")
    assert "Back" in _titles(artist)


def test_anonymous_cannot_set_anybody_s_preferences(artist):
    anon = create_app().test_client()
    r = anon.post("/settings/notifications", data={"kind": []})
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    with artist._app.app_context():
        assert store.muted_kinds(artist._uid) == set()

"""In-app pages follow the suite they belong to, and the sidebar says so.

Owner, 2026-09-17: the audio pages (Rack, Remix Lab, Audio Studio, Beats,
Studio) are "part of the room", so they open with Label or with credits in
the wallet. The live pages are Tour, so they open with Pro. The gates are
enforced on every deployed service and wherever SUITE_GATES=on.
"""
import uuid

import pytest

import app as appmod
import db as store
import plans

PW = "suite-gates-pass-1"


@pytest.fixture
def gated(monkeypatch):
    monkeypatch.setenv("SUITE_GATES", "on")
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _client(plan):
    email = "gate-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "G", "email": email, "password": PW})
    user = store.get_user_by_email(email)
    store.set_user_plan(user["id"], plan)
    return c, user


def test_the_gates_are_off_on_a_laptop_and_on_when_deployed(monkeypatch):
    monkeypatch.delenv("SUITE_GATES", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert not plans.gates_on() and plans.path_suite("/rack") is None
    monkeypatch.setenv("RENDER", "true")
    assert plans.gates_on() and plans.path_suite("/rack") == "the-room"
    monkeypatch.setenv("SUITE_GATES", "off")
    assert not plans.gates_on()


def test_the_audio_pages_open_the_way_the_room_does(gated):
    artist, user = _client("artist")
    for path in ("/rack", "/beats", "/audio-studio", "/remix-lab"):
        r = artist.get(path)
        assert r.status_code == 402 and "The Room runs on credits" in r.get_data(as_text=True), path
    assert artist.get("/links").status_code == 200, "Street Banker itself stays open"
    store.add_credits(user["id"], 25, "pack", ref="g:" + user["id"])
    assert artist.get("/rack").status_code == 200
    label, _ = _client("label")
    assert label.get("/rack").status_code == 200


def test_the_live_pages_open_with_pro_and_a_public_link_stays_public(gated):
    artist, _ = _client("artist")
    r = artist.get("/stage-plot")
    assert r.status_code == 402 and "Tour opens with Pro" in r.get_data(as_text=True)
    pro, _ = _client("pro")
    assert pro.get("/stage-plot").status_code == 200
    # /tours is never path-gated: crew on any membership open what they were invited to.
    assert artist.get("/tours").status_code == 200
    assert plans.path_suite("/tours") is None and plans.path_suite("/tours", nav=True) == "tour"


def test_the_sidebar_tags_what_the_membership_cannot_open(gated):
    assert plans.nav_lock("artist", "/rack") == "Credits"
    assert plans.nav_lock("artist", "/rack", credits=5) == ""
    assert plans.nav_lock("artist", "/tours") == plans.nav_lock("artist", "/suites/go/reach") == "Pro"
    assert plans.nav_lock("pro", "/suites/go/motion") == "Credits"
    assert plans.nav_lock("label", "/suites/go/motion") == plans.nav_lock("artist", "/royalties") == ""
    artist, _ = _client("artist")
    page = artist.get("/links").get_data(as_text=True)
    assert 'title="Opens with credits or the Label membership">Credits</span>' in page
    assert 'title="Opens with the Pro membership">Pro</span>' in page
    label, _ = _client("label")
    assert ">Credits</span>" not in label.get("/links").get_data(as_text=True)


def test_the_shared_demo_login_keeps_the_rack_open(gated):
    """Owner, 2026-09-17: "let them use the rack". The demo logins are given a
    standing balance when they sign in, once."""
    from app import create_app
    c = create_app().test_client()
    c.post("/login", data={"email": "demo-artist@streetbanker.io", "password": "sweep"})
    c.post("/login", data={"email": "demo-artist@streetbanker.io", "password": "sweep"})
    user = store.get_user_by_email("demo-artist@streetbanker.io")
    assert store.credit_balances(user["id"])["bought"] == 100000
    assert c.get("/rack").status_code == 200

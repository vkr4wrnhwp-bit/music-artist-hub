"""Mechanicals, with the registry beside the income.

The page shows the latest MLC sweep (the same one Recovery keeps), each
row crossed with what that title earned in the mechanical stream, and a
button that runs the sweep and comes back here. Without the login it
says so and nothing on the page is a registration status.
"""
import io
import uuid

import pytest

import db as store
import signal_providers as providers
from app import create_app
from tests.test_signal_mlc import Fake

PASSWORD = "mech-pass-123"


def _artist(app_obj, with_statement=True):
    email = "mech-%s@example.net" % uuid.uuid4().hex[:8]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Ava", "email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})
    if with_statement:
        csv = ("title,source,amount,period,territory\n"
               "Night Drive,The MLC,45,2026-02,\n"
               "Night Drive,Spotify,500,2026-02,US\n"
               "Ghost,The MLC,12.5,2026-02,\n")
        client.post("/statements", data={"statement": (io.BytesIO(csv.encode()), "m.csv")},
                    content_type="multipart/form-data")
    return client, store.get_user_by_email(email)


def _track(client, user, title, **passport):
    client.post("/tracks/add", data={"title": title})
    track = [t for t in store.list_os_tracks(user["id"]) if t["title"] == title][0]
    if passport:
        p = track["passport"]
        p.update(passport)
        store.update_os_track_passport(user["id"], track["id"], p)
    return track


def _connect(monkeypatch, fake=None):
    monkeypatch.setenv("MLC_ENABLED", "1")
    monkeypatch.setenv("MLC_USERNAME", "api-user@example.net")
    monkeypatch.setenv("MLC_PASSWORD", "right")
    adapter = providers.MLCAdapter(transport=fake or Fake())
    monkeypatch.setattr(providers, "mlc_adapter", lambda: adapter)


def test_without_the_login_the_page_says_so_on_both_income_branches(monkeypatch):
    for k in ("MLC_ENABLED", "MLC_USERNAME", "MLC_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(providers, "mlc_adapter", lambda: providers.MLCAdapter(
        transport=lambda *a: pytest.fail("must not call out")))
    app_obj = create_app()
    for with_statement in (True, False):
        client, user = _artist(app_obj, with_statement)
        page = client.get("/mechanicals").get_data(as_text=True)
        assert 'id="mlc"' in page and "Registration at The MLC" in page and "Not connected" in page
        assert "at The MLC</button>" not in page
    # Publishing and neighbouring rights do not carry it: it is a mechanical question.
    assert 'id="mlc"' not in client.get("/publishing").get_data(as_text=True)
    assert 'id="mlc"' not in client.get("/neighboring-rights").get_data(as_text=True)


def test_the_sweep_runs_from_here_comes_back_here_and_shows_the_earnings(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    night = _track(client, user, "Night Drive", isrc="USAIW2600123")
    ghost = _track(client, user, "Ghost", isrc="USXXX9999999")
    _track(client, user, "Static", isrc="USAIW2600777")
    page = client.get("/mechanicals").get_data(as_text=True)
    assert "Check 3 ISRCs at The MLC" in page and 'name="next" value="/mechanicals"' in page
    assert "No check run yet" in page

    r = client.post("/recovery/mlc", data={"next": "/mechanicals"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/mechanicals#mlc")
    page = client.get("/mechanicals").get_data(as_text=True)
    assert "1 fully claimed" in page and "1 partly claimed" in page and "1 no work linked" in page
    assert "earning $45.00 here" in page and "earning $12.50 here" in page
    assert page.count("earning $") == 2, "Static earns nothing in this stream and says nothing"
    assert 'href="/tracks/%s#mlc"' % ghost["id"] in page and 'href="/tracks/%s#mlc"' % night["id"] in page
    assert 'value="Unmatched at The MLC: Ghost (USXXX9999999)"' in page
    assert "The same sweep on Recovery" in page
    # It is the same sweep Recovery shows.
    assert "1 no work linked" in client.get("/recovery").get_data(as_text=True)


def test_the_return_path_only_knows_the_two_pages(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj, with_statement=False)
    r = client.post("/recovery/mlc", data={"next": "https://evil.example/phish"})
    assert r.headers["Location"].endswith("/recovery?mlc=none#mlc")
    r = client.post("/recovery/mlc", data={"next": "/mechanicals"})
    assert r.headers["Location"].endswith("/mechanicals?mlc=none#mlc")
    assert "nothing to ask about" in client.get("/mechanicals?mlc=none").get_data(as_text=True)

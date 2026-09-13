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


def test_the_income_branches_fold_into_royalties_and_the_registry_stays_on_recovery(monkeypatch):
    """Mechanicals, Publishing and Neighboring rights are one Royalties
    page now (owner, 2026-09-13); the MLC section lives on Recovery, and
    without the login it says so and nothing on it is a registration
    status."""
    for k in ("MLC_ENABLED", "MLC_USERNAME", "MLC_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(providers, "mlc_adapter", lambda: providers.MLCAdapter(
        transport=lambda *a: pytest.fail("must not call out")))
    app_obj = create_app()
    for with_statement in (True, False):
        client, user = _artist(app_obj, with_statement)
        for old in ("/mechanicals", "/publishing", "/neighboring-rights"):
            r = client.get(old)
            assert r.status_code == 302 and r.headers["Location"].endswith("/royalties#streams"), old
        page = client.get("/recovery").get_data(as_text=True)
        assert 'id="mlc"' in page and "Not connected" in page
        assert "at The MLC</button>" not in page


def test_the_sweep_runs_on_recovery_and_the_mechanical_row_on_royalties_reads_it(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    night = _track(client, user, "Night Drive", isrc="USAIW2600123")
    ghost = _track(client, user, "Ghost", isrc="USXXX9999999")
    _track(client, user, "Static", isrc="USAIW2600777")
    body = client.get("/royalties").get_data(as_text=True)
    mech = body.split('data-stream-row="mechanical"')[1].split('data-stream-row=')[0]
    assert "$57.50" in mech and "The MLC" in mech, "45 + 12.50 of mechanical income on file"
    assert 'href="/recovery#mlc"' in mech

    r = client.post("/recovery/mlc", data={"next": "/mechanicals"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/recovery#mlc")
    page = client.get("/recovery").get_data(as_text=True)
    assert "1 fully claimed" in page and "1 partly claimed" in page and "1 no work linked" in page
    assert 'href="/tracks/%s#mlc"' % ghost["id"] in page and 'href="/tracks/%s#mlc"' % night["id"] in page
    assert 'value="Unmatched at The MLC: Ghost (USXXX9999999)"' in page
    # The stream row on Royalties reads the same sweep.
    body = client.get("/royalties").get_data(as_text=True)
    mech = body.split('data-stream-row="mechanical"')[1].split('data-stream-row=')[0]
    assert "1 work unregistered" in mech and "1 partly claimed" in mech


def test_the_return_path_only_knows_recovery(monkeypatch):
    """Mechanicals folded into Royalties (2026-09-13), so the sweep has one home."""
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj, with_statement=False)
    r = client.post("/recovery/mlc", data={"next": "https://evil.example/phish"})
    assert r.headers["Location"].endswith("/recovery?mlc=none#mlc")
    r = client.post("/recovery/mlc", data={"next": "/mechanicals"})
    assert r.headers["Location"].endswith("/recovery?mlc=none#mlc")
    assert "nothing to ask about" in client.get("/recovery?mlc=none").get_data(as_text=True)

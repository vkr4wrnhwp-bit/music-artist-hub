"""Track Passport, asked about The MLC.

A button, not a crawl: the artist presses it, the registry answers about
the ISRC (or, without one, the title and artist name), and every answer
is kept - a match with writers, publishers and the claimed share; "no
work linked", which for a released ISRC is money nobody is collecting;
or the vendor's error. A match can fill EMPTY passport fields; a name
the artist typed is never overwritten, and the MLC registration field
is filled only from a match by ISRC.
"""
import uuid

import pytest

import db as store
import signal_providers as providers
from app import create_app
from tests.test_signal_mlc import Fake

PASSWORD = "passport-pass-123"


def _artist(app_obj):
    email = "mlc-%s@example.net" % uuid.uuid4().hex[:8]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Ava", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client, store.get_user_by_email(email)


def _track(client, user, title="Night Drive", **passport):
    client.post("/tracks/add", data={"title": title, "release_title": "Midnight EP"})
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
    return adapter


def test_without_the_login_the_page_says_not_connected_and_the_button_is_absent(monkeypatch):
    for k in ("MLC_ENABLED", "MLC_USERNAME", "MLC_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(providers, "mlc_adapter", lambda: providers.MLCAdapter(
        transport=lambda *a: pytest.fail("must not call out")))
    app_obj = create_app()
    client, user = _artist(app_obj)
    track = _track(client, user, isrc="USAIW2600123")
    page = client.get("/tracks/" + track["id"]).get_data(as_text=True)
    assert 'id="mlc"' in page and "Not connected" in page
    assert "Check ISRC" not in page and "Fill empty passport fields" not in page
    r = client.post("/tracks/%s/mlc" % track["id"], data={"action": "check"})
    assert r.status_code == 302 and "mlc=off" in r.headers["Location"]
    assert store.list_track_mlc_checks(user["id"], track["id"]) == []
    assert "not connected on this service" in client.get("/tracks/%s?mlc=off" % track["id"]).get_data(as_text=True)


def test_an_isrc_check_names_the_work_and_fills_only_what_is_empty(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    track = _track(client, user, isrc="usaiw2600123", songwriters="Ava Kane (typed)")
    page = client.get("/tracks/" + track["id"]).get_data(as_text=True)
    assert "Check ISRC USAIW2600123" in page and "No check run yet" in page

    r = client.post("/tracks/%s/mlc" % track["id"], data={"action": "check"})
    assert r.status_code == 302 and r.headers["Location"].endswith("#mlc")
    checks = store.list_track_mlc_checks(user["id"], track["id"])
    assert len(checks) == 1 and checks[0]["result"] == "match" and checks[0]["asked"] == "ISRC USAIW2600123"
    work = checks[0]["works"][0]
    assert work["song_code"] == "BA1234" and work["share_total"] == 100.0

    page = client.get("/tracks/" + track["id"]).get_data(as_text=True)
    assert "NIGHT DRIVE" in page and "song code BA1234" in page and "ISWC T-123.456.789-0" in page
    assert "Ava Kane (IPI 00123456789)" in page and "J. Ro (IPI 00987654321)" in page
    assert "100.0% claimed" in page and "Kobalt Music Publishing" in page
    assert "Fill empty passport fields from this" in page

    client.post("/tracks/%s/mlc" % track["id"], data={"action": "fill", "check_id": checks[0]["id"]})
    passport = store.get_os_track(user["id"], track["id"])["passport"]
    assert passport["songwriters"] == "Ava Kane (typed)", "what the artist typed stands"
    assert passport["publishers"] == "Art Is War Publishing, Ro Songs"
    assert passport["mlc_status"].startswith("registered - matched at The MLC, song code BA1234, 100% claimed")
    page = client.get("/tracks/" + track["id"]).get_data(as_text=True)
    assert "matched at The MLC" in page


def test_a_title_match_shows_the_claim_gap_and_does_not_claim_registration(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    track = _track(client, user, title="Paper Lines", artist_name="Ava Kane")
    page = client.get("/tracks/" + track["id"]).get_data(as_text=True)
    assert "Check by title and artist" in page
    client.post("/tracks/%s/mlc" % track["id"], data={"action": "check"})
    check = store.list_track_mlc_checks(user["id"], track["id"])[0]
    assert check["asked"] == "Paper Lines by Ava Kane" and check["result"] == "match"
    page = client.get("/tracks/" + track["id"]).get_data(as_text=True)
    assert "50.0% claimed" in page and "Ava Kane (no IPI)" in page
    assert 'sb-lamp sb-lamp--warn">50.0% claimed' in page
    client.post("/tracks/%s/mlc" % track["id"], data={"action": "fill", "check_id": check["id"]})
    passport = store.get_os_track(user["id"], track["id"])["passport"]
    assert passport["songwriters"] == "Ava Kane" and passport["publishers"] == "Art Is War Publishing"
    assert not passport.get("mlc_status"), "a work of that name exists; that is not this recording's registration"


def test_no_work_is_a_gap_with_the_next_step_and_an_error_is_kept(monkeypatch):
    fake = Fake()
    _connect(monkeypatch, fake)
    app_obj = create_app()
    client, user = _artist(app_obj)
    track = _track(client, user, isrc="USXXX9999999")
    client.post("/tracks/%s/mlc" % track["id"], data={"action": "check"})
    page = client.get("/tracks/" + track["id"]).get_data(as_text=True)
    assert "no work linked" in page and "register the work, then check again" in page
    assert "Fill empty passport fields" not in page
    fake.password = "changed-on-their-side"
    monkeypatch.setattr(providers, "mlc_adapter", lambda: providers.MLCAdapter(transport=fake))
    client.post("/tracks/%s/mlc" % track["id"], data={"action": "check"})
    checks = store.list_track_mlc_checks(user["id"], track["id"])
    assert [c["result"] for c in checks] == ["error", "none"], "newest first"
    assert "Wrong email or password" in client.get("/tracks/" + track["id"]).get_data(as_text=True)


def test_nothing_to_ask_with_is_a_note_not_a_check(monkeypatch):
    _connect(monkeypatch, Fake())
    app_obj = create_app()
    client, user = _artist(app_obj)
    track = _track(client, user, title="Untitled")
    page = client.get("/tracks/" + track["id"]).get_data(as_text=True)
    assert "disabled" in page.split('id="mlc"')[1].split("</form>")[0]
    r = client.post("/tracks/%s/mlc" % track["id"], data={"action": "check"})
    assert "mlc=need" in r.headers["Location"]
    assert "at least an artist name" in client.get("/tracks/%s?mlc=need" % track["id"]).get_data(as_text=True)
    assert store.list_track_mlc_checks(user["id"], track["id"]) == []


def test_another_accounts_check_cannot_fill_your_passport_and_deletion_cleans_up(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    a, ua = _artist(app_obj)
    ta = _track(a, ua, isrc="USAIW2600123")
    a.post("/tracks/%s/mlc" % ta["id"], data={"action": "check"})
    check = store.list_track_mlc_checks(ua["id"], ta["id"])[0]
    b, ub = _artist(app_obj)
    tb = _track(b, ub, title="Mine")
    b.post("/tracks/%s/mlc" % tb["id"], data={"action": "fill", "check_id": check["id"]})
    assert not store.get_os_track(ub["id"], tb["id"])["passport"].get("publishers")
    a.post("/tracks/%s/delete" % ta["id"])
    assert store.list_track_mlc_checks(ua["id"], ta["id"]) == []
    assert store.get_track_mlc_check(ua["id"], check["id"]) is None

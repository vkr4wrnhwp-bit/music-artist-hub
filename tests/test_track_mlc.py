"""Track Passport, asked about The MLC.

A button, not a crawl: the artist presses it, the registry answers about
the ISRC (or, without one, the title and artist name), and every answer
is kept - a match with writers, publishers and the claimed share; "no
work linked", which for a released ISRC is money nobody is collecting;
or the vendor's error. A match can fill EMPTY passport fields; a name
the artist typed is never overwritten, and the MLC registration field
is never filled from a check at all: the check IS the registration
record, and the engines read it rather than a sentence about it.
"""
import uuid

import pytest

import artist_os
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
    assert not passport.get("mlc_status"), (
        "the registration is the check, not a sentence written into a text box")
    page = client.get("/tracks/" + track["id"]).get_data(as_text=True)
    assert "The MLC holds song code BA1234 with 100% of the collection share claimed." in page


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


# --- the check is the evidence; the text box is a claim -------------------------
#
# Clean Release and the mechanicals lane used to grade the free-text
# `mlc_status` box, so "registered" typed into it scored exactly as high
# as a matched work with a full claim. artist_os.mlc_evidence reads the
# stored check instead, and a typed field is labelled as one.


def _check(result="match", asked="ISRC USAIW2600123", works=()):
    return {"result": result, "asked": asked, "works": list(works)}


def _work(share, code="BA1234", iswc="T-123.456.789-0"):
    return {"song_code": code, "iswc": iswc, "share_total": share,
            "writers": [], "publishers": [{"name": "Art Is War Publishing",
                                           "share": share}]}


def test_a_full_claim_is_done_and_a_short_one_names_the_gap():
    full = artist_os.mlc_evidence(
        {"passport": {}, "mlc_check": _check(works=[_work(100.0)])})
    assert full["source"] == "check" and full["state"] == "green"
    assert full["label"] == "claimed" and full["lane"] == "claimed"
    assert "song code BA1234" in full["detail"] and "100% of the collection share" in full["detail"]

    short = artist_os.mlc_evidence(
        {"passport": {}, "mlc_check": _check(works=[_work(50.0)])})
    assert short["state"] == "yellow" and short["lane"] == "needs action"
    assert short["label"] == "50% claimed"
    assert "50% is going uncollected" in short["detail"]

    # 99.5 is the floor, so rounding noise is not a gap.
    assert artist_os.mlc_evidence(
        {"passport": {}, "mlc_check": _check(works=[_work(99.5)])})["state"] == "green"
    assert artist_os.mlc_evidence(
        {"passport": {}, "mlc_check": _check(works=[_work(99.4)])})["state"] == "yellow"


def test_no_work_for_an_isrc_is_a_finding_and_a_title_miss_is_silence():
    """An ISRC The MLC has no work for is uncollected money. A title with
    no recording is not: album titles are not works."""
    gap = artist_os.mlc_evidence({"passport": {}, "mlc_check": _check("none")})
    assert gap["state"] == "red" and gap["lane"] == "missing"
    assert gap["label"] == "not registered at The MLC"

    silence = artist_os.mlc_evidence(
        {"passport": {"mlc_status": "registered"},
         "mlc_check": _check("none", asked="Paper Lines by Ava Kane")})
    assert silence["source"] == "typed", "a title miss says nothing about this recording"


def test_a_typed_status_never_reads_as_evidence():
    typed = artist_os.mlc_evidence({"passport": {"mlc_status": "Registered"}})
    assert typed["source"] == "typed" and typed["label"] == "typed, unverified"
    assert typed["state"] == "yellow", "the word registered is not a finding"
    assert "Nobody has asked The MLC" in typed["detail"]
    bad = artist_os.mlc_evidence({"passport": {"mlc_status": "blocked"}})
    assert bad["state"] == "red"
    blank = artist_os.mlc_evidence({"passport": {}})
    assert blank["source"] == "none" and blank["label"] == "not checked"


def test_a_failed_check_is_not_evidence_either():
    """The vendor being down says nothing about the registration."""
    ev = artist_os.mlc_evidence(
        {"passport": {"mlc_status": "Registered"},
         "mlc_check": _check("error", works=[])})
    assert ev["source"] == "typed" and ev["label"] == "typed, unverified"


def test_clean_release_and_the_lane_both_read_the_check(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    track = _track(client, user, isrc="usaiw2600123", mlc_status="Registered")
    ctx = {"statement_rows": 0, "statement_total": 0, "lanes_with_data": set(),
           "live_links": 0, "fans": 0, "club_members": 0, "sync_active": False,
           "release_scheduled": False, "rollout_assets": False}

    before = store.get_os_track(user["id"], track["id"])
    assert before["mlc_check"] is None
    row = [i for i in artist_os.clean_release(before, ctx)["items"]
           if i["label"].startswith("Mechanical collection")][0]
    assert row["label"].endswith("typed, unverified") and row["state"] == "yellow"
    grid = {l["key"]: l for l in artist_os.lane_grid(before, ctx)}
    assert grid["mechanicals"]["state"] == "needs action"

    client.post("/tracks/%s/mlc" % track["id"], data={"action": "check"})
    after = store.get_os_track(user["id"], track["id"])
    assert after["mlc_check"]["result"] == "match"
    row = [i for i in artist_os.clean_release(after, ctx)["items"]
           if i["label"].startswith("Mechanical collection")][0]
    assert row["label"].endswith("claimed") and row["state"] == "green"
    assert {l["key"]: l for l in artist_os.lane_grid(after, ctx)}["mechanicals"]["state"] == "claimed"


def test_the_passport_page_shows_the_finding_beside_the_button(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    track = _track(client, user, title="Paper Lines", artist_name="Ava Kane",
                   mlc_status="Registered")
    page = client.get("/tracks/" + track["id"]).get_data(as_text=True)
    section = page.split('id="mlc"')[1].split("</section>")[0]
    assert "typed, unverified" in section
    assert "Nobody has asked The MLC about this recording" in section

    client.post("/tracks/%s/mlc" % track["id"], data={"action": "check"})
    section = client.get("/tracks/" + track["id"]).get_data(as_text=True) \
        .split('id="mlc"')[1].split("</section>")[0]
    assert "typed, unverified" not in section
    assert "only 50% of the collection share is claimed" in section


def test_the_newest_check_is_the_one_that_counts(monkeypatch):
    """A later answer replaces an earlier one; the history stays on file."""
    fake = Fake()
    _connect(monkeypatch, fake)
    app_obj = create_app()
    client, user = _artist(app_obj)
    track = _track(client, user, isrc="USXXX9999999")
    client.post("/tracks/%s/mlc" % track["id"], data={"action": "check"})
    assert artist_os.mlc_evidence(store.get_os_track(user["id"], track["id"]))["state"] == "red"
    p = store.get_os_track(user["id"], track["id"])["passport"]
    p["isrc"] = "USAIW2600123"
    store.update_os_track_passport(user["id"], track["id"], p)
    client.post("/tracks/%s/mlc" % track["id"], data={"action": "check"})
    assert len(store.list_track_mlc_checks(user["id"], track["id"])) == 2
    assert artist_os.mlc_evidence(store.get_os_track(user["id"], track["id"]))["label"] == "claimed"

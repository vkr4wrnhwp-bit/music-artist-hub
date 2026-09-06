"""Recovery, asked of The MLC: every passport ISRC, one sweep, on request.

The sweep is bounded, kept whole, and honest about what it did not ask:
passports without an ISRC are listed as unable to be checked, never
matched by title. Every gap - no work linked, or a work only partly
claimed - is offered as a case; a fully claimed work is not.
"""
import uuid

import pytest

import db as store
import recovery_mlc
import signal_providers as providers
from app import create_app
from tests.test_signal_mlc import Fake

PASSWORD = "recovery-pass-123"


def _artist(app_obj):
    email = "rmlc-%s@example.net" % uuid.uuid4().hex[:8]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Ava", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})      # Recovery is a Pro page
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
    return adapter


def _catalogue(client, user):
    full = _track(client, user, "Night Drive", isrc="us-aiw-26-00123")
    bare = _track(client, user, "Static", isrc="USAIW2600777")
    gone = _track(client, user, "Ghost", isrc="USXXX9999999")
    _track(client, user, "Night Drive (Radio Edit)", isrc="USAIW2600123")   # a duplicate ISRC
    no_isrc = _track(client, user, "Untitled Demo", artist_name="Ava Kane")
    return full, bare, gone, no_isrc


def test_candidates_are_isrcs_deduped_and_the_rest_are_named(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    full, bare, gone, no_isrc = _catalogue(client, user)
    ready, missing = recovery_mlc.candidates(user["id"])
    assert sorted(r["isrc"] for r in ready) == ["USAIW2600123", "USAIW2600777", "USXXX9999999"]
    assert [m["track_id"] for m in missing] == [no_isrc["id"]]


def test_without_the_login_the_page_says_so_and_the_sweep_refuses(monkeypatch):
    for k in ("MLC_ENABLED", "MLC_USERNAME", "MLC_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(providers, "mlc_adapter", lambda: providers.MLCAdapter(
        transport=lambda *a: pytest.fail("must not call out")))
    app_obj = create_app()
    client, user = _artist(app_obj)
    _catalogue(client, user)
    page = client.get("/recovery").get_data(as_text=True)
    assert 'id="mlc"' in page and "Not connected" in page and "at The MLC</button>" not in page
    r = client.post("/recovery/mlc")
    assert "mlc=off" in r.headers["Location"]
    assert store.latest_recovery_mlc_sweep(user["id"]) is None
    assert "not connected on this service" in client.get("/recovery?mlc=off").get_data(as_text=True)


def test_a_sweep_sorts_the_catalogue_into_claimed_partial_and_gone(monkeypatch):
    fake = Fake()
    _connect(monkeypatch, fake)
    app_obj = create_app()
    client, user = _artist(app_obj)
    full, bare, gone, no_isrc = _catalogue(client, user)
    page = client.get("/recovery").get_data(as_text=True)
    assert "Check 3 ISRCs at The MLC" in page and "No check run yet" in page
    assert "carries no ISRC and cannot be checked" in page and "Untitled Demo" in page

    r = client.post("/recovery/mlc")
    assert r.status_code == 302 and r.headers["Location"].endswith("/recovery#mlc")
    sweep = store.latest_recovery_mlc_sweep(user["id"])
    assert sweep["summary"] == {"checked": 3, "matched": 1, "partial": 1, "unmatched": 1, "errors": 0, "skipped": 0}
    by_isrc = {row["isrc"]: row for row in sweep["rows"]}
    assert by_isrc["USAIW2600123"]["result"] == "match" and by_isrc["USAIW2600123"]["share_total"] == 100.0
    assert by_isrc["USAIW2600777"]["result"] == "match" and by_isrc["USAIW2600777"]["publishers"] == 0
    assert by_isrc["USXXX9999999"]["result"] == "none"
    asked = [c[3]["isrc"] for c in fake.calls if c[1].endswith("/search/recordings")]
    assert sorted(asked) == ["USAIW2600123", "USAIW2600777", "USXXX9999999"], "each ISRC once, nothing by title"

    page = client.get("/recovery").get_data(as_text=True)
    assert "1 fully claimed" in page and "1 partly claimed" in page and "1 no work linked" in page
    assert "100.0% claimed" in page and "0.0% claimed" in page and "no work linked" in page
    assert 'href="/tracks/%s#mlc"' % gone["id"] in page
    # A case is offered on each gap and on nothing else.
    assert page.count('name="category" value="mechanical"') == 2
    assert 'value="Unmatched at The MLC: Ghost (USXXX9999999)"' in page
    assert 'value="Partly claimed at The MLC: Static (USAIW2600777)"' in page
    assert "Night Drive (USAIW2600123)" not in page


def test_a_case_opened_from_a_gap_is_shown_as_open_next_time(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    _catalogue(client, user)
    client.post("/recovery/mlc")
    client.post("/royalty-recovery/cases/from-finding", data={
        "title": "Unmatched at The MLC: Ghost (USXXX9999999)", "category": "mechanical",
        "amount": "0", "notes": "The MLC has no work linked to ISRC USXXX9999999."})
    cases = store.list_recovery_cases(user["id"])
    assert len(cases) == 1 and cases[0]["category"] == "mechanical"
    page = client.get("/recovery").get_data(as_text=True)
    assert page.count("Case open →") == 1 and page.count('name="category" value="mechanical"') == 1


def test_errors_are_counted_and_shown_and_an_empty_catalogue_is_a_note(monkeypatch):
    fake = Fake()
    _connect(monkeypatch, fake)
    app_obj = create_app()
    client, user = _artist(app_obj)
    r = client.post("/recovery/mlc")
    assert "mlc=none" in r.headers["Location"]
    assert "nothing to ask about" in client.get("/recovery?mlc=none").get_data(as_text=True)
    _track(client, user, "Night Drive", isrc="USAIW2600123")
    fake.password = "rotated"
    client.post("/recovery/mlc")
    sweep = store.latest_recovery_mlc_sweep(user["id"])
    assert sweep["summary"]["errors"] == 1 and sweep["rows"][0]["result"] == "error"
    page = client.get("/recovery").get_data(as_text=True)
    assert "1 error" in page and "Wrong email or password" in page
    assert 'name="category" value="mechanical"' not in page, "an error is not a gap"


def test_the_sweep_is_bounded_and_says_what_it_skipped(monkeypatch):
    _connect(monkeypatch)
    monkeypatch.setattr(recovery_mlc, "PER_SWEEP", 2)
    app_obj = create_app()
    client, user = _artist(app_obj)
    _catalogue(client, user)
    client.post("/recovery/mlc")
    sweep = store.latest_recovery_mlc_sweep(user["id"])
    assert sweep["summary"]["checked"] == 2 and sweep["summary"]["skipped"] == 1
    assert "1 more not checked this run" in client.get("/recovery").get_data(as_text=True)

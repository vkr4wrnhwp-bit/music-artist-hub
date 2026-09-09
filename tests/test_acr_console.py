"""ACRCloud's console API: registering the catalog, and scanning a set.

`tests/test_acr.py` guards the identify half - a check the producer runs on a
clip. This file guards the other half, which can WRITE to the owner's paid
ACRCloud account, and the things worth guarding follow from that:

  * nothing is claimed that did not happen. A refusal keeps ACRCloud's own
    message and writes no registration row, because a list of registrations
    containing things that were never registered is worse than a short list.
  * nothing is sent twice. The same master pressed twice is one upload and one
    row, enforced by a UNIQUE constraint rather than by a check somebody has
    to remember.
  * nothing is sent at all without a token, and never from a sandbox.
  * the scan tells the truth about offsets and confidence, and the lamp on a
    hit is computed from this account's own registrations rather than from
    anything the vendor said about ownership.
  * a seat that may not spend the account's quota reads the page and gets no
    buttons - checked in the route, not only in the template.

Every call is canned through the module's one `_http` seam, so the multipart
body it would have sent is exercised without a byte leaving the machine.
"""
import io
import json
import os
import uuid

import pytest

import acr_console as console
import acr_desk
import acr_store as astore
import db as store
import partner_store as pstore

PASSWORD = "acr-console-pass-123"
TOKEN = "console-token-test"

BUCKETS = {"data": [{"id": 4711, "name": "Street Banker masters", "type": "File",
                     "region": "us-west-2", "state": 1, "num": 3, "size": 900}],
           "meta": {"current_page": 1, "total": 1, "last_page": 1}}

CONTAINERS = {"data": [{"id": 88, "name": "Sets and streams", "region": "us-west-2",
                        "state": 1, "audio_type": "recorded"}],
              "meta": {"current_page": 1, "total": 1, "last_page": 1}}

UPLOADED = {"data": {"id": 90210, "acr_id": "acr-mine-1", "state": 1,
                     "title": "Night Drive", "duration": 213,
                     "bucket_id": 4711, "user_defined": {}}}

SCAN_STARTED = {"data": {"id": 5150, "state": 0, "name": "warehouse-set.mp3"}}

# One of the owner's records and one stranger's, in a two-hour set.
SCAN_READY = {"data": {"id": 5150, "state": 1, "name": "warehouse-set.mp3", "results": {"music": [
    {"offset": 132, "played_duration": 214, "type": "delay", "result": {
        "acrid": "acr-theirs-9", "title": "Somebody Else's Record",
        "artists": [{"name": "Other Act"}], "album": {"name": "Not Mine"},
        "external_ids": {"isrc": "GBAAA2500001"},
        "db_begin_time_offset_ms": 0, "db_end_time_offset_ms": 214000, "score": 88}},
    {"offset": 4360, "played_duration": 180, "type": "delay", "result": {
        "acrid": "acr-mine-1", "title": "Night Drive",
        "artists": [{"name": "Ava Kane"}], "album": {"name": "After Hours"},
        "external_ids": {"isrc": "USAIW2600123"},
        "db_begin_time_offset_ms": 12000, "db_end_time_offset_ms": 192000, "score": 96}},
]}}}


# --- harness -------------------------------------------------------------------

@pytest.fixture(scope="module")
def flask_app():
    import app as appmod
    app = appmod.create_app()
    pstore.init_partners()
    astore.init_acr()
    return app


@pytest.fixture(autouse=True)
def _connected(monkeypatch):
    """A token by default, and never a sandbox. Tests that want the other
    states switch them off themselves."""
    monkeypatch.setenv("ACRCLOUD_CONSOLE_TOKEN", TOKEN)
    monkeypatch.setenv("ACRCLOUD_HOST", "identify-us-west-2.acrcloud.com")
    monkeypatch.delenv("SANDBOX", raising=False)


def _account(flask_app, label="Producer"):
    email = "acrc-%s@example.net" % uuid.uuid4().hex[:10]
    client = flask_app.test_client()
    client.post("/signup", data={"name": label, "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    # Recovery cases are a Pro page, and the case button posts to one.
    client.post("/plan/switch", data={"plan": "pro"})
    return client, store.get_user_by_email(email)


def _wav(seconds=1, rate=8000):
    n = seconds * rate
    head = (b"RIFF" + (36 + n * 2).to_bytes(4, "little") + b"WAVEfmt " +
            (16).to_bytes(4, "little") + (1).to_bytes(2, "little") +
            (1).to_bytes(2, "little") + rate.to_bytes(4, "little") +
            (rate * 2).to_bytes(4, "little") + (2).to_bytes(2, "little") +
            (16).to_bytes(2, "little") + b"data" + (n * 2).to_bytes(4, "little"))
    return head + b"\x00\x00" * n


def _vault_master(flask_app, user, label="Night Drive", name="night-drive.wav"):
    """A real vault row with a real file behind it, put there the way the app
    puts one there."""
    uploads = os.path.join(os.path.dirname(store.db_path()), "uploads")
    os.makedirs(uploads, exist_ok=True)
    key = "acrtest-%s-%s" % (uuid.uuid4().hex[:8], name)
    with io.open(os.path.join(uploads, key), "wb") as handle:
        handle.write(_wav())
    return store.add_vault_file(user["id"], "/uploads/" + key, label, "master")


class Canned(object):
    """A scripted `_http`. Records every call so the request itself - method,
    URL, headers, body - can be asserted on."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, method, url, headers=None, body=None, timeout=None):
        self.calls.append({"method": method, "url": url,
                           "headers": headers or {}, "body": body or b""})
        if not self.answers:
            raise AssertionError("unscripted call: %s %s" % (method, url))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _patch(monkeypatch, canned):
    monkeypatch.setattr(console, "_http", canned)
    return canned


# --- the wire ------------------------------------------------------------------

def test_the_bucket_call_is_the_documented_one(monkeypatch):
    """Host, path and the bearer header, pinned. Nobody can test ACRCloud from
    here, so the test pins what the docs said on 2026-09-09."""
    canned = _patch(monkeypatch, Canned((200, BUCKETS)))
    rows = console.buckets()
    call = canned.calls[0]
    assert call["method"] == "GET"
    assert call["url"].startswith("https://api-v2.acrcloud.com/api/buckets?")
    assert "per_page=100" in call["url"] and "type=File" in call["url"]
    assert call["headers"]["Authorization"] == "Bearer " + TOKEN
    assert call["headers"]["Accept"] == "application/json"
    assert rows[0]["id"] == "4711" and rows[0]["name"] == "Street Banker masters"


def test_pagination_is_bounded_and_stops_on_a_short_page(monkeypatch):
    """A `meta` that says there are a thousand pages must not become a
    thousand requests inside one web request."""
    page = {"data": [{"id": i, "name": "b%d" % i, "region": "us-west-2"}
                     for i in range(console.PAGE_SIZE)],
            "meta": {"last_page": 9999}}
    last = {"data": [{"id": 1, "name": "tail", "region": "us-west-2"}],
            "meta": {"last_page": 9999}}
    canned = _patch(monkeypatch, Canned(*([(200, page)] * 2 + [(200, last)])))
    console.buckets(max_pages=3)
    assert len(canned.calls) == 3
    canned = _patch(monkeypatch, Canned((200, page), (200, last)))
    console.buckets(max_pages=10)
    assert len(canned.calls) == 2      # the short page ended it, not the meta


def test_the_upload_is_multipart_with_their_field_names(monkeypatch):
    canned = _patch(monkeypatch, Canned((200, UPLOADED)))
    answer = console.upload_audio("4711", "night-drive.wav", _wav(), "Night Drive",
                                  custom={"street_banker_vault_id": "v1"})
    call = canned.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api-us-west-2.acrcloud.com/api/buckets/4711/files"
    assert call["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    body = call["body"]
    assert b'name="data_type"' in body and b"audio" in body
    assert b'name="title"' in body and b"Night Drive" in body
    assert b'name="user_defined"' in body and b"street_banker_vault_id" in body
    assert b'name="file"; filename="night-drive.wav"' in body
    assert answer["audio_id"] == "90210" and answer["acr_id"] == "acr-mine-1"
    assert answer["state_word"] == "ready"


def test_a_scan_reads_state_and_results_from_the_one_documented_call(monkeypatch):
    """Their API has no separate results endpoint. Inventing one would have
    been a guess, so both functions read the same GET."""
    canned = _patch(monkeypatch, Canned((200, SCAN_READY), (200, SCAN_READY)))
    state = console.scan_state("88:5150")
    results = console.scan_results("88:5150")
    assert {c["url"] for c in canned.calls} == {
        "https://api-us-west-2.acrcloud.com/api/fs-containers/88/files/5150"}
    assert state["state_word"] == "ready"
    # offset and played_duration are seconds; everything downstream is ms.
    first, second = results["hits"][0], results["hits"][1]
    assert first["start_ms"] == 132000 and first["end_ms"] == 346000
    assert second["start_ms"] == 4360000 and second["score"] == 96
    assert second["isrc"] == "USAIW2600123"
    assert console.clock(4360000) == "1:12:40"


def test_a_refusal_keeps_acrclouds_own_words(monkeypatch):
    _patch(monkeypatch, Canned((403, {"message": "The token is missing the scope write-audios"})))
    with pytest.raises(console.AcrConsoleError) as caught:
        console.upload_audio("4711", "x.wav", _wav(), "X")
    assert caught.value.status == 403
    assert caught.value.msg == "The token is missing the scope write-audios"
    assert console.last_refusal()["message"] == "The token is missing the scope write-audios"


def test_a_rate_limit_is_remembered_too(monkeypatch):
    _patch(monkeypatch, Canned((429, {"message": "Too many requests"})))
    with pytest.raises(console.AcrConsoleError):
        console.buckets()
    assert console.last_refusal() == {"status": 429, "message": "Too many requests"}


def test_no_token_means_no_call_and_a_named_variable(monkeypatch):
    monkeypatch.delenv("ACRCLOUD_CONSOLE_TOKEN", raising=False)
    canned = _patch(monkeypatch, Canned())
    assert console.configured() is False
    assert console.missing_env() == ["ACRCLOUD_CONSOLE_TOKEN"]
    with pytest.raises(console.AcrConsoleError):
        console.buckets()
    assert canned.calls == []


def test_the_sandbox_makes_no_call_even_with_a_token(monkeypatch):
    """This token writes into a paid account. A throwaway deployment must not
    be able to put test audio in it."""
    monkeypatch.setenv("SANDBOX", "1")
    canned = _patch(monkeypatch, Canned())
    assert console.configured() is False
    with pytest.raises(console.AcrConsoleError):
        console.upload_audio("4711", "x.wav", _wav(), "X")
    assert canned.calls == []


# --- registering the catalog ------------------------------------------------------

def test_registering_a_master_writes_one_row_and_never_a_second(flask_app, monkeypatch):
    client, user = _account(flask_app)
    vault_id = _vault_master(flask_app, user)
    canned = _patch(monkeypatch, Canned((200, BUCKETS), (200, UPLOADED)))

    client.post("/fingerprints/register",
                data={"vault_id": vault_id, "bucket_id": "4711"})
    rows = astore.list_registrations(user["id"])
    assert len(rows) == 1
    assert rows[0]["acr_audio_id"] == "90210" and rows[0]["acr_id"] == "acr-mine-1"
    assert rows[0]["bucket_name"] == "Street Banker masters"
    assert rows[0]["bytes_sent"] > 0
    uploads = [c for c in canned.calls if c["method"] == "POST"]
    assert len(uploads) == 1

    # Press it again: no upload happens at all, and there is still one row.
    canned = _patch(monkeypatch, Canned((200, BUCKETS)))
    client.post("/fingerprints/register",
                data={"vault_id": vault_id, "bucket_id": "4711"})
    assert len(astore.list_registrations(user["id"])) == 1
    assert [c for c in canned.calls if c["method"] == "POST"] == []


def test_a_refusal_writes_nothing_and_shows_the_vendors_message(flask_app, monkeypatch):
    client, user = _account(flask_app)
    vault_id = _vault_master(flask_app, user, label="Refused Master")
    _patch(monkeypatch, Canned(
        (200, BUCKETS),
        (403, {"message": "Your plan does not allow custom bucket uploads"})))
    client.post("/fingerprints/register",
                data={"vault_id": vault_id, "bucket_id": "4711"}, follow_redirects=False)
    assert astore.list_registrations(user["id"]) == []
    _patch(monkeypatch, Canned((200, BUCKETS), (200, CONTAINERS)))
    page = client.get("/fingerprints/").get_data(as_text=True)
    assert "Your plan does not allow custom bucket uploads" in page
    # and the file is still offered, because nothing was registered
    assert "Refused Master" in page


def test_only_masters_and_stems_are_offered(flask_app, monkeypatch):
    client, user = _account(flask_app)
    store.add_vault_file(user["id"], "/uploads/contract.pdf", "Signed licence", "document")
    store.add_vault_file(user["id"], "/uploads/cover.png", "Cover art", "art")
    _vault_master(flask_app, user, label="A Real Master")
    _patch(monkeypatch, Canned((200, BUCKETS), (200, CONTAINERS)))
    page = client.get("/fingerprints/").get_data(as_text=True)
    assert "A Real Master" in page
    assert "Signed licence" not in page and "Cover art" not in page


def test_the_page_names_the_missing_variable(flask_app, monkeypatch):
    monkeypatch.delenv("ACRCLOUD_CONSOLE_TOKEN", raising=False)
    client, _user = _account(flask_app)
    canned = _patch(monkeypatch, Canned())
    page = client.get("/fingerprints/").get_data(as_text=True)
    assert "ACRCLOUD_CONSOLE_TOKEN" in page
    assert "Not connected" in page
    assert canned.calls == []


def test_no_bucket_says_what_to_make_and_creates_nothing(flask_app, monkeypatch):
    client, _user = _account(flask_app)
    canned = _patch(monkeypatch, Canned((200, {"data": [], "meta": {"last_page": 1}}),
                                        (200, {"data": [], "meta": {"last_page": 1}})))
    page = client.get("/fingerprints/").get_data(as_text=True)
    assert "create a bucket of type" in page and "File" in page
    assert [c for c in canned.calls if c["method"] == "POST"] == []


# --- file scanning ------------------------------------------------------------------

def _scan_with_hits(flask_app, monkeypatch, register=True):
    client, user = _account(flask_app)
    if register:
        vault_id = _vault_master(flask_app, user)
        _patch(monkeypatch, Canned((200, BUCKETS), (200, UPLOADED)))
        client.post("/fingerprints/register",
                    data={"vault_id": vault_id, "bucket_id": "4711"})
    _patch(monkeypatch, Canned((200, SCAN_STARTED)))
    response = client.post("/fingerprints/scans",
                           data={"container_id": "88", "url": "https://example.com/warehouse-set.mp3"})
    scan_id = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
    _patch(monkeypatch, Canned((200, SCAN_READY)))
    client.post("/fingerprints/scans/%s/refresh" % scan_id)
    return client, user, scan_id


def test_a_scans_hits_render_with_offsets_and_confidence(flask_app, monkeypatch):
    client, user, scan_id = _scan_with_hits(flask_app, monkeypatch)
    hits = astore.list_hits(user["id"], scan_id)
    assert len(hits) == 2
    page = client.get("/fingerprints/scans/%s" % scan_id).get_data(as_text=True)
    assert "Somebody Else&#39;s Record" in page or "Somebody Else's Record" in page
    assert "0:02:12" in page and "1:12:40" in page       # both starts, as a clock
    assert "96" in page and "88" in page                 # both confidences
    assert "GBAAA2500001" in page and "USAIW2600123" in page


def test_the_owners_own_master_lights_the_lamp_and_offers_a_case(flask_app, monkeypatch):
    client, user, scan_id = _scan_with_hits(flask_app, monkeypatch)
    page = client.get("/fingerprints/scans/%s" % scan_id).get_data(as_text=True)
    assert "Yours" in page and "Theirs" in page
    assert "Open a usage case" in page
    assert '/royalty-recovery/cases/from-finding' in page
    # the evidence, not just a title
    assert "1:12:40" in page
    hits = astore.list_hits(user["id"], scan_id)
    mine = [h for h in hits if h["mine"]]
    assert len(mine) == 1 and mine[0]["acrid"] == "acr-mine-1"
    title, note = astore.case_fields(astore.get_scan(user["id"], scan_id), mine[0])
    assert "Night Drive" in title
    assert "warehouse-set.mp3" in note and "1:12:40" in note
    assert "96 out of 100" in note and "USAIW2600123" in note


def test_the_case_button_opens_a_real_case_carrying_the_evidence(flask_app, monkeypatch):
    client, user, scan_id = _scan_with_hits(flask_app, monkeypatch)
    scan = astore.get_scan(user["id"], scan_id)
    mine = [h for h in astore.list_hits(user["id"], scan_id) if h["mine"]][0]
    title, note = astore.case_fields(scan, mine)
    client.post("/royalty-recovery/cases/from-finding",
                data={"title": title, "category": "other", "amount": "0", "notes": note})
    cases = store.list_recovery_cases(user["id"])
    assert any(c["title"] == title and "warehouse-set.mp3" in (c["notes"] or "")
               for c in cases)


def test_nothing_is_mine_until_it_is_registered(flask_app, monkeypatch):
    """The lamp is computed from this account's registrations, not from
    anything the vendor said about ownership."""
    client, user, scan_id = _scan_with_hits(flask_app, monkeypatch, register=False)
    hits = astore.list_hits(user["id"], scan_id)
    assert [h["mine"] for h in hits] == [False, False]
    page = client.get("/fingerprints/scans/%s" % scan_id).get_data(as_text=True)
    assert "Open a usage case" not in page


def test_a_refresh_replaces_hits_rather_than_doubling_them(flask_app, monkeypatch):
    client, user, scan_id = _scan_with_hits(flask_app, monkeypatch)
    _patch(monkeypatch, Canned((200, SCAN_READY)))
    client.post("/fingerprints/scans/%s/refresh" % scan_id)
    assert len(astore.list_hits(user["id"], scan_id)) == 2


def test_a_scan_still_running_says_so_and_shows_no_hits(flask_app, monkeypatch):
    client, _user = _account(flask_app)
    _patch(monkeypatch, Canned((200, SCAN_STARTED)))
    response = client.post("/fingerprints/scans",
                           data={"container_id": "88", "url": "https://example.com/set.mp3"})
    scan_id = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
    _patch(monkeypatch, Canned((200, {"data": {"id": 5150, "state": 0, "name": "set.mp3"}})))
    client.post("/fingerprints/scans/%s/refresh" % scan_id)
    page = client.get("/fingerprints/scans/%s" % scan_id).get_data(as_text=True)
    assert "still working through it" in page
    assert "Open a usage case" not in page


# --- access ---------------------------------------------------------------------------

def test_a_seat_without_the_scope_reads_the_list_and_gets_no_buttons(flask_app, monkeypatch):
    client, user, scan_id = _scan_with_hits(flask_app, monkeypatch)
    partner = pstore.get_partner(pstore.create_partner("Read Only %s" % uuid.uuid4().hex[:6]))
    pstore.add_member(partner["id"], user["email"], name="Viewer", role="viewer",
                      user_id=user["id"])
    assert pstore.can(pstore.member_for_user(user["id"]), "act_as_artist") is False

    _patch(monkeypatch, Canned((200, BUCKETS), (200, CONTAINERS)))
    page = client.get("/fingerprints/").get_data(as_text=True)
    assert "Street Banker masters" in page          # the list is readable
    assert "Register with ACRCloud" not in page     # and nothing is pressable

    scan_page = client.get("/fingerprints/scans/%s" % scan_id).get_data(as_text=True)
    assert "Night Drive" in scan_page
    assert "Open a usage case" not in scan_page

    # And the route refuses, so a hand-built POST does not get through either.
    canned = _patch(monkeypatch, Canned())
    assert client.post("/fingerprints/register",
                       data={"vault_id": "x", "bucket_id": "4711"}).status_code == 403
    assert client.post("/fingerprints/scans",
                       data={"container_id": "88", "url": "https://e.com/a.mp3"}).status_code == 403
    assert client.post("/fingerprints/scans/%s/refresh" % scan_id).status_code == 403
    assert canned.calls == []


def test_a_signed_out_visitor_gets_the_login_wall(flask_app):
    anon = flask_app.test_client()
    for path in ("/fingerprints/", "/fingerprints/scans/whatever"):
        assert anon.get(path).status_code in (301, 302)


def test_one_account_cannot_read_anothers_scan(flask_app, monkeypatch):
    _client, _user, scan_id = _scan_with_hits(flask_app, monkeypatch)
    stranger, _other = _account(flask_app, label="Stranger")
    assert stranger.get("/fingerprints/scans/%s" % scan_id).status_code == 404

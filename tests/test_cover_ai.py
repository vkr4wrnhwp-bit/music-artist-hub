"""Cover art renders: OpenAI's gpt-image-1 and the monthly allowance.

Owner, 2026-09-23: "open ai and we allow x amount of renders a month".
Every render spends the owner's money, so what is held here:

  - the request is the one OpenAI documents, and the key never leaves it
  - a render is reserved before the call, so a double click or a second
    tab cannot take more covers than the month has
  - a failed, refused or timed-out render never uses a cover up
  - the showcase logins never spend one, and a seat spends its holder's
  - with no key, the free Pollinations path is exactly what it was

No test reaches OpenAI: cover_ai._transport is replaced in every one.
"""
import base64
import json
import os
import socket
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app as appmod
import cover_ai
import db as store
import team_areas

PW = "cover-renders-1"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OWNER_EMAILS", raising=False)
    cover_ai.init_db()
    yield
    for plan in cover_ai.DEFAULT_ALLOWANCE:
        store.delete_kv("cover_renders:%s" % plan)


class FakeOpenAI:
    """Stands in for the network. Records every call it is given."""

    def __init__(self, status=200, payload=None, raises=None):
        self.calls = []
        self.status = status
        self.payload = payload if payload is not None else {
            "created": 1, "data": [{"b64_json": base64.b64encode(JPEG).decode()}],
            "usage": {"total_tokens": 1}}
        self.raises = raises

    def __call__(self, url, body, headers, timeout):
        self.calls.append({"url": url, "body": json.loads(body.decode()),
                           "headers": headers, "timeout": timeout})
        if self.raises is not None:
            raise self.raises
        return self.status, json.dumps(self.payload).encode()


@pytest.fixture
def openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    fake = FakeOpenAI()
    monkeypatch.setattr(cover_ai, "_transport", fake)
    return fake


def _account(plan="artist", name="Artist"):
    email = "%s-%s@example.net" % (name.lower(), uuid.uuid4().hex[:8])
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    c._email, c._id = email, uid
    return c


def _gen(client, **body):
    return client.post("/artwork/generate", data=json.dumps(body),
                       content_type="application/json")


def _rows(account_id):
    with store.get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM cover_renders WHERE account_id = ? ORDER BY created_at",
            (str(account_id),))]


# --- the request -----------------------------------------------------------------

def test_the_request_is_the_one_openai_documents(openai):
    data = cover_ai.render("neon city, album cover art")
    assert data == JPEG
    (call,) = openai.calls
    assert call["url"] == "https://api.openai.com/v1/images/generations"
    assert call["body"]["model"] == "gpt-image-1"
    assert call["body"]["size"] == "1024x1024"
    assert call["body"]["quality"] == "medium"
    assert call["body"]["n"] == 1
    assert call["body"]["prompt"] == "neon city, album cover art"
    assert call["headers"]["Authorization"] == "Bearer sk-test-not-a-real-key"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["timeout"] == 120


def test_no_key_means_not_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    assert not cover_ai.configured()
    monkeypatch.delenv("OPENAI_API_KEY")
    assert not cover_ai.configured()


def test_a_content_policy_refusal_is_named_as_one(openai):
    openai.status = 400
    openai.payload = {"error": {"message": "Your request was rejected by the safety system.",
                                "type": "image_generation_user_error",
                                "code": "moderation_blocked"}}
    with pytest.raises(cover_ai.RenderError) as e:
        cover_ai.render("x")
    assert e.value.kind == "refused"
    assert "content rules refused" in e.value.message
    assert "not used one of your covers" in e.value.message


def test_a_timeout_is_a_timeout(openai):
    openai.raises = socket.timeout("timed out")
    with pytest.raises(cover_ai.RenderError) as e:
        cover_ai.render("x")
    assert e.value.kind == "timeout"


@pytest.mark.parametrize("status,payload", [
    (500, {"error": {"message": "server error", "code": None}}),
    (401, {"error": {"message": "Incorrect API key provided: sk-...", "code": "invalid_api_key"}}),
    (200, {"data": []}),
    (200, {"data": [{"b64_json": "not base64 at all!!"}]}),
    (200, {"data": [{"b64_json": base64.b64encode(b"<html>nope</html>").decode()}]}),
])
def test_anything_else_is_a_failure_and_never_echoes_openai(openai, status, payload):
    openai.status, openai.payload = status, payload
    with pytest.raises(cover_ai.RenderError) as e:
        cover_ai.render("x")
    assert e.value.kind == "failed"
    assert "sk-" not in e.value.message and "server error" not in e.value.message


# --- the allowance -----------------------------------------------------------------

def test_the_defaults_per_plan():
    assert cover_ai.DEFAULT_ALLOWANCE == {"fan": 0, "artist": 10, "pro": 30, "label": 100}
    assert cover_ai.allowances() == cover_ai.DEFAULT_ALLOWANCE


def test_the_owner_changes_each_number_and_junk_is_refused():
    refused = cover_ai.save_allowances({"covers_artist": "12", "covers_pro": "-3",
                                        "covers_label": "lots", "covers_fan": "0"})
    assert sorted(refused) == ["label", "pro"]
    assert cover_ai.allowance("artist") == 12
    assert cover_ai.allowance("pro") == 30 and cover_ai.allowance("label") == 100


@pytest.mark.parametrize("now,expected", [
    (datetime(2026, 9, 23, 12, tzinfo=timezone.utc), "1 October"),
    (datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc), "1 January"),
    (datetime(2027, 1, 31, tzinfo=timezone.utc), "1 February"),
])
def test_the_reset_date_is_the_first_of_next_month(now, expected):
    assert cover_ai.reset_date(now) == expected


def test_a_reservation_holds_a_cover_and_a_failure_gives_it_back():
    acct = "acct-" + uuid.uuid4().hex[:8]
    a = cover_ai.reserve(acct, acct, 2)
    b = cover_ai.reserve(acct, acct, 2)
    assert a and b
    assert cover_ai.reserve(acct, acct, 2) is None, "two held, the third is refused"
    cover_ai.finish(a, "failed")
    c = cover_ai.reserve(acct, acct, 2)
    assert c, "a failed render gave its cover back"
    for status in ("refused", "timeout"):
        cover_ai.finish(c, status)
        c = cover_ai.reserve(acct, acct, 2)
        assert c, "a %s render gave its cover back" % status
    cover_ai.finish(b, "done")
    cover_ai.finish(c, "done")
    assert cover_ai.used(acct) == 2
    assert cover_ai.reserve(acct, acct, 2) is None


def test_a_pending_row_from_a_dead_worker_stops_counting():
    acct = "acct-" + uuid.uuid4().hex[:8]
    rid = cover_ai.reserve(acct, acct, 1)
    assert cover_ai.reserve(acct, acct, 1) is None
    old = (datetime.now(timezone.utc) - timedelta(minutes=cover_ai.PENDING_STALE_MINUTES + 1))
    with store.get_db() as conn:
        conn.execute("UPDATE cover_renders SET created_at = ? WHERE id = ?",
                     (old.isoformat(timespec="seconds"), rid))
    assert cover_ai.reserve(acct, acct, 1)


def test_two_tabs_at_once_cannot_take_more_than_the_month_has():
    acct = "acct-" + uuid.uuid4().hex[:8]
    got, start = [], threading.Barrier(12)

    def go():
        start.wait()
        got.append(cover_ai.reserve(acct, acct, 3))

    threads = [threading.Thread(target=go) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len([g for g in got if g]) == 3
    assert cover_ai.used(acct) == 3


def test_unlimited_is_recorded_and_counts_against_nobody():
    acct = "acct-" + uuid.uuid4().hex[:8]
    for _ in range(3):
        cover_ai.finish(cover_ai.reserve(acct, "owner", None), "done")
    assert cover_ai.used(acct) == 0
    assert cover_ai.reserve(acct, acct, 1), "the account's own allowance is untouched"


# --- the route, no key: exactly what it was -------------------------------------

def test_without_a_key_the_free_model_is_used_and_nothing_is_counted(monkeypatch):
    called = []
    monkeypatch.setattr(cover_ai, "_transport", lambda *a: called.append(a))
    c = _account()
    got = _gen(c, prompt="neon city", look=["photo"]).get_json()
    assert got["ok"] and got["engine"] == "pollinations"
    assert got["image_url"].startswith("https://image.pollinations.ai/prompt/")
    assert "seed=%d" % got["seed"] in got["image_url"]
    assert not called and not _rows(c._id)
    page = c.get("/artwork").get_data(as_text=True)
    assert "Pollinations.ai" in page
    assert 'id="cover-allowance"' not in page and 'id="generate-btn"' in page


def test_signed_out_nothing_is_made(openai):
    anon = appmod.app.test_client()
    r = _gen(anon, prompt="neon city")
    assert r.status_code in (302, 401)
    assert not openai.calls


# --- the route, with a key ----------------------------------------------------------

def test_a_render_is_saved_to_the_uploads_and_counted(openai):
    c = _account("artist")
    r = _gen(c, prompt="neon city", look=["photo", "moody"])
    got = r.get_json()
    assert r.status_code == 200 and got["ok"] and got["engine"] == "openai"
    assert got["saved"] and got["path"].startswith("/uploads/aiart_%s_" % c._id)
    assert got["image_url"] == got["path"]
    assert c.get(got["path"]).data == JPEG
    assert "shot on film" in openai.calls[0]["body"]["prompt"]
    assert got["allowance"]["left"] == 9 and got["allowance"]["limit"] == 10
    (row,) = _rows(c._id)
    assert row["status"] == "done" and row["path"] == got["path"]
    # The Cover Studio lists it with its other files.
    page = c.get("/artwork").get_data(as_text=True)
    assert os.path.basename(got["path"]) in page
    assert "9 of 10 covers left this month. Resets %s." % cover_ai.reset_date() in page
    assert "Made by OpenAI" in page


def test_at_zero_the_button_is_replaced_by_a_line(openai):
    cover_ai.save_allowances({"covers_artist": "2"})
    c = _account("artist")
    assert _gen(c, prompt="one").get_json()["ok"]
    assert _gen(c, prompt="two").get_json()["ok"]
    r = _gen(c, prompt="three")
    got = r.get_json()
    assert r.status_code == 429 and got["used_up"] and not got["ok"]
    assert "covers are used" in got["error"] and cover_ai.reset_date() in got["error"]
    assert len(openai.calls) == 2, "the third was refused before OpenAI was asked"
    page = c.get("/artwork").get_data(as_text=True)
    assert 'id="generate-btn"' not in page and 'id="generate4-btn"' not in page
    assert "This month&#39;s 2 covers are used. More on %s." % cover_ai.reset_date() in page \
        or "This month's 2 covers are used. More on %s." % cover_ai.reset_date() in page


def test_a_refused_prompt_says_so_and_is_not_counted(openai):
    openai.status = 400
    openai.payload = {"error": {"code": "moderation_blocked", "message": "rejected"}}
    c = _account("artist")
    r = _gen(c, prompt="something the filter refuses")
    got = r.get_json()
    assert r.status_code == 422 and got["kind"] == "refused"
    assert "content rules refused" in got["error"]
    assert got["allowance"]["left"] == 10
    assert [x["status"] for x in _rows(c._id)] == ["refused"]


@pytest.mark.parametrize("raises,status,kind", [
    (socket.timeout("timed out"), 504, "timeout"),
    (OSError("connection reset"), 502, "failed"),
])
def test_a_failed_render_never_uses_a_cover(openai, raises, status, kind):
    openai.raises = raises
    c = _account("artist")
    r = _gen(c, prompt="neon city")
    assert r.status_code == status and r.get_json()["kind"] == kind
    assert r.get_json()["allowance"]["left"] == 10
    assert cover_ai.used(c._id) == 0


def test_a_remix_is_a_new_render_and_counts(openai):
    c = _account("artist")
    _gen(c, prompt="neon city")
    got = _gen(c, prompt="neon city, make it red", seed=1234).get_json()
    assert got["ok"] and got["seed"] is None
    assert "make it red" in openai.calls[1]["body"]["prompt"]
    assert "seed" not in openai.calls[1]["body"]
    assert got["allowance"]["left"] == 8
    page = c.get("/artwork").get_data(as_text=True)
    assert "uses one of your covers" in page


def test_an_empty_description_spends_nothing(openai):
    c = _account("artist")
    got = _gen(c, prompt="  ").get_json()
    assert got["ok"] and got["image_url"] is None
    assert not openai.calls and not _rows(c._id)


def test_the_demo_never_spends_a_render(openai):
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    r = _gen(demo, prompt="neon city")
    assert r.status_code == 403 and r.get_json()["demo"]
    assert "isn't part of the demo" in r.get_json()["error"]
    assert not openai.calls
    page = demo.get("/artwork").get_data(as_text=True)
    assert "Cover generation isn&#39;t part of the demo" in page \
        or "Cover generation isn't part of the demo" in page
    assert 'id="generate-btn"' not in page


def test_an_owner_login_is_unlimited(openai, monkeypatch):
    cover_ai.save_allowances({"covers_label": "0"})
    c = _account("label", "Owner")
    monkeypatch.setenv("OWNER_EMAILS", c._email)
    for _ in range(2):
        got = _gen(c, prompt="neon city").get_json()
        assert got["ok"] and got["allowance"]["unlimited"]
    assert [r["counts"] for r in _rows(c._id)] == [0, 0]
    assert "Owner login: unlimited covers." in c.get("/artwork").get_data(as_text=True)


def _seat(owner, member, access="edit"):
    data = {"email": member._email, "role": "manager", "access": access, "areas_sent": "1",
            "areas": list(team_areas.keys())}
    assert owner.post("/team/invite", data=data).get_json().get("ok")
    token = [m for m in store.list_team(owner._id)
             if m["email"] == member._email][0]["invite_token"]
    assert member.post("/team/join/" + token, data={}).status_code == 302
    assert member.post("/portal/%s/open" % owner._id).status_code in (302, 200)


def test_a_team_seat_draws_on_the_account_holders_covers(openai):
    cover_ai.save_allowances({"covers_pro": "1"})
    holder, member = _account("pro", "Holder"), _account("artist", "Member")
    _seat(holder, member, access="edit")
    got = _gen(member, prompt="neon city").get_json()
    assert got["ok"], got
    assert got["path"].startswith("/uploads/aiart_%s_" % holder._id)
    (row,) = _rows(holder._id)
    assert row["actor_id"] == str(member._id)
    assert not _rows(member._id)
    # The holder's one cover is gone, whoever used it.
    assert _gen(holder, prompt="again").status_code == 429


def test_a_read_only_seat_cannot_render(openai):
    holder, member = _account("pro", "Holder"), _account("artist", "Reader")
    _seat(holder, member, access="read")
    r = _gen(member, prompt="neon city")
    assert r.status_code == 403 and not openai.calls


# --- the owner's card -------------------------------------------------------------

def test_the_owner_sees_the_months_renders_and_sets_the_numbers(openai, monkeypatch):
    before = cover_ai.month_summary()["done"]
    artist = _account("artist")
    _gen(artist, prompt="neon city")
    owner = _account("label", "Owner")
    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    page = owner.get("/settings").get_data(as_text=True)
    assert 'id="cover-renders"' in page
    assert "Cover art renders" in page and "OpenAI key: set" in page
    summary = cover_ai.month_summary()
    assert summary["done"] == before + 1
    assert "$0.042 a cover" in page and "23 September 2026" in page
    r = owner.post("/admin/cover-renders", data={"covers_artist": "7", "covers_pro": "30",
                                                 "covers_label": "100", "covers_fan": "0"})
    assert r.status_code == 302 and "covers=saved" in r.headers["Location"]
    assert cover_ai.allowance("artist") == 7


def test_nobody_else_sees_or_sets_them(openai):
    artist = _account("label")
    assert 'id="cover-renders"' not in artist.get("/settings").get_data(as_text=True)
    assert artist.post("/admin/cover-renders", data={"covers_artist": "999"}).status_code == 404
    assert cover_ai.allowance("artist") == 10


# --- what the rest of the app says about it ---------------------------------------

def test_the_capability_note_names_the_generator_in_use(monkeypatch):
    import capability_status
    got = capability_status.resolve("artwork_generator")
    assert got["status"] == capability_status.LIVE and "Pollinations" in got["note"]
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    got = capability_status.resolve("artwork_generator")
    assert got["status"] == capability_status.LIVE and "gpt-image-1" in got["note"]


def test_the_readiness_page_names_the_key(monkeypatch):
    import readiness
    row = [r for g in readiness.report() for r in g["rows"] if r["name"] == "OpenAI images"][0]
    assert row["env"] == ["OPENAI_API_KEY"] and not row["on"]
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    row = [r for g in readiness.report() for r in g["rows"] if r["name"] == "OpenAI images"][0]
    assert row["on"]


def test_the_tour_does_not_promise_a_remix_keeps_the_picture():
    """OpenAI has no seed: a remix is a new render, not an edit."""
    import product_tour_config
    revision = dict(product_tour_config.CREATIVE_STEPS)["Revision"]
    assert "keeping the concept" not in revision
    assert "made again" in revision

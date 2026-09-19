"""Hypeddit into the Fan CRM (owner, 2026-09-19).

Hypeddit's Automation page takes one webhook URL and posts each fan who
finishes a gate to it, after a test record when the URL is saved. The
field names are not published, so the receiver reads the address from
wherever it sits, files a real fan the way the smart-link subscribe route
does, logs the test without filing it, keeps the raw shape of the last
deliveries (addresses masked) for the artist to check, and always answers
200 for a known address so nothing is retried into a duplicate.
"""
import json
import uuid

import pytest

import app as appmod
import db as store
import hypeddit_ingest as hi
import links_store as mls
import team_areas

PW = "hypeddit-pass-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("RENDER", raising=False)


def _account(name="Artist", plan="pro"):
    email = "%s-%s@example.net" % (name.lower(), uuid.uuid4().hex[:8])
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    c._email, c._id = email, uid
    return c


def _anon():
    return appmod.app.test_client()


def _consents(user_id, email):
    fan = mls.fan_by_email(user_id, email)
    return [c for c in mls.list_consents(fan["id"]) if c["consent_type"] == hi.CONSENT_TYPE] if fan else []


# --- the address -----------------------------------------------------------------

def test_an_unknown_address_is_404_and_files_nothing():
    r = _anon().post("/webhooks/hypeddit/not-a-real-token", json={"email": "x@y.net"})
    assert r.status_code == 404 and r.get_json()["ok"] is False


def test_get_answers_listening_and_files_nothing():
    a = _account()
    token = hi.get_or_create_token(a._id)
    assert token == hi.get_or_create_token(a._id), "minted once"
    r = _anon().get("/webhooks/hypeddit/" + token)
    assert r.status_code == 200 and r.get_json() == {"ok": True, "listening": True}
    assert mls.list_fans(a._id) == [] and hi.status(a._id)["connected"] is False


def test_a_json_delivery_files_one_fan_once():
    a = _account()
    token = hi.get_or_create_token(a._id)
    body = {"email": "Ada@Example.NET", "name": "Ada Lovelace", "link": "Summer Single"}
    r = _anon().post("/webhooks/hypeddit/" + token, json=body)
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    fan = mls.fan_by_email(a._id, "ada@example.net")
    assert fan and fan["name"] == "Ada Lovelace" and fan["total_captures"] == 1
    assert "hypeddit" in json.loads(fan["tags"]) and fan["intent_level"]
    consents = _consents(a._id, "ada@example.net")
    assert len(consents) == 1 and consents[0]["campaign_id"] is None
    assert consents[0]["consent_text"].startswith(
        "Gave their email address on the artist's Hypeddit gate, pre-save or smart link (received ")
    st = hi.status(a._id)
    assert st["count"] == 1 and st["connected"] and st["last_delivery"]["kind"] == "fan"
    notes = [n for n in store.list_notifications(a._id) if "Hypeddit" in n["title"]]
    assert notes and "ada@example.net" in notes[0]["title"]
    # The same fan finishing a second gate: refreshed, not doubled.
    r = _anon().post("/webhooks/hypeddit/" + token, json=body)
    assert r.status_code == 200
    assert len(_consents(a._id, "ada@example.net")) == 1
    assert len([f for f in mls.list_fans(a._id) if f["email"] == "ada@example.net"]) == 1
    assert hi.status(a._id)["count"] == 1
    assert mls.fan_by_email(a._id, "ada@example.net")["total_captures"] == 2


def test_a_form_encoded_delivery_works():
    a = _account()
    token = hi.get_or_create_token(a._id)
    r = _anon().post("/webhooks/hypeddit/" + token,
                     data={"fan_email": "bo@example.net", "first_name": "Bo", "last_name": "Diddley"})
    assert r.status_code == 200
    fan = mls.fan_by_email(a._id, "bo@example.net")
    assert fan and fan["name"] == "Bo Diddley" and "hypeddit" in json.loads(fan["tags"])


def test_zapier_spelled_keys_work():
    a = _account()
    token = hi.get_or_create_token(a._id)
    r = _anon().post("/webhooks/hypeddit/" + token,
                     json={"Email Address": "cy@example.net", "Name": "Cy Ro", "Gate": "Pre-save"})
    assert r.status_code == 200
    fan = mls.fan_by_email(a._id, "cy@example.net")
    assert fan and fan["name"] == "Cy Ro"


def test_hypeddits_test_record_is_logged_and_not_filed():
    a = _account()
    token = hi.get_or_create_token(a._id)
    r = _anon().post("/webhooks/hypeddit/" + token, json={"email": "test@example.com", "name": "Test"})
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    assert mls.list_fans(a._id) == []
    st = hi.status(a._id)
    assert st["connected"] and st["count"] == 0 and st["last_delivery"]["kind"] == "test"


def test_a_delivery_with_no_email_is_logged_unusable():
    a = _account()
    token = hi.get_or_create_token(a._id)
    _anon().post("/webhooks/hypeddit/" + token, json={"email": "di@example.net"})
    r = _anon().post("/webhooks/hypeddit/" + token, json={"name": "Nobody", "gate": "Link Gate"})
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    st = hi.status(a._id)
    assert st["last_delivery"]["kind"] == "unusable" and "No email" in st["last_delivery"]["note"]
    assert st["count"] == 1 and len(mls.list_fans(a._id)) == 1


def test_the_log_masks_the_address_and_cuts_long_values():
    a = _account()
    token = hi.get_or_create_token(a._id)
    _anon().post("/webhooks/hypeddit/" + token,
                 json={"email": "ev@example.net", "note": "x" * 500, "also": "mail ev@example.net here"})
    fields = {f["key"]: f["value"] for f in hi.status(a._id)["last_delivery"]["fields"]}
    assert fields["email"] == "e***@example.net"
    assert "ev@example.net" not in json.dumps(fields)
    assert len(fields["note"]) == hi.VALUE_CUT
    assert fields["also"] == "mail e***@example.net here"
    assert "ev@example.net" not in (store.get_kv(hi.KEY_LOG % a._id) or "")


def test_the_daily_cap_drops_and_logs(monkeypatch):
    a = _account()
    token = hi.get_or_create_token(a._id)
    monkeypatch.setattr(hi, "DAILY_CAP", 1)
    _anon().post("/webhooks/hypeddit/" + token, json={"email": "fa@example.net"})
    r = _anon().post("/webhooks/hypeddit/" + token, json={"email": "fb@example.net"})
    assert r.status_code == 200 and r.get_json() == {"ok": True}
    assert mls.fan_by_email(a._id, "fb@example.net") is None
    assert hi.status(a._id)["last_delivery"]["kind"] == "dropped"


def test_rotating_makes_the_old_address_404():
    a = _account()
    old = hi.get_or_create_token(a._id)
    r = a.post("/links/fans/hypeddit/rotate")
    assert r.status_code == 302 and r.headers["Location"].endswith("/links/fans#hypeddit")
    new = hi.get_or_create_token(a._id)
    assert new != old
    assert _anon().post("/webhooks/hypeddit/" + old, json={"email": "g@example.net"}).status_code == 404
    assert _anon().post("/webhooks/hypeddit/" + new, json={"email": "g@example.net"}).status_code == 200
    assert mls.fan_by_email(a._id, "g@example.net")
    assert store.get_kv(hi.KEY_USER % old) is None


# --- the panel -------------------------------------------------------------------

def test_the_fan_crm_page_shows_the_owner_their_address():
    a = _account()
    body = a.get("/links/fans").get_data(as_text=True)
    token = hi.get_or_create_token(a._id)
    assert "Connect Hypeddit" in body
    assert "https://localhost/webhooks/hypeddit/" + token in body
    assert "Waiting for Hypeddit" in body and "/links/fans/hypeddit/rotate" in body
    _anon().post("/webhooks/hypeddit/" + token, json={"Email Address": "h@example.net"})
    body = a.get("/links/fans").get_data(as_text=True)
    assert "Connected: 1 fan has come in" in body and "What Hypeddit sent" in body
    # The fans table above shows the address in full, as it should; the
    # raw delivery in the panel does not.
    panel = body.split('id="hypeddit"', 1)[1].split("</section>", 1)[0]
    assert "Email Address" in panel and "h***@example.net" in panel and "h@example.net" not in panel


def test_a_read_seat_is_not_shown_the_address():
    owner, member = _account("Owner"), _account("Member", plan="artist")
    data = {"email": member._email, "role": "manager", "access": "read", "areas_sent": "1",
            "areas": team_areas.keys()}
    assert owner.post("/team/invite", data=data).get_json().get("ok")
    token = [m for m in store.list_team(owner._id) if m["email"] == member._email][0]["invite_token"]
    assert member.post("/team/join/" + token, data={}).status_code == 302
    assert member.post("/portal/%s/open" % owner._id).status_code == 302
    r = member.get("/links/fans")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Connect Hypeddit" not in body and "/webhooks/hypeddit/" not in body
    assert member.post("/links/fans/hypeddit/rotate").status_code in (302, 403)
    assert store.get_kv(hi.KEY_TOKEN % owner._id) in (None, hi.get_or_create_token(owner._id))


def test_the_showcase_account_has_no_panel():
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    r = demo.get("/links/fans")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Connect Hypeddit" not in body and "/webhooks/hypeddit/" not in body
    assert demo.post("/links/fans/hypeddit/rotate").status_code in (302, 403, 404)


# --- the reader on its own ---------------------------------------------------------

def test_extract_reads_the_address_wherever_it_sits():
    assert hi.extract({"E-Mail": "A@B.co", "Name": "Ab"}) == {"email": "a@b.co", "name": "Ab", "link": "", "extra": {}}
    assert hi.extract({"data": {"fan": {"emailAddress": "n@m.io", "firstName": "N", "lastName": "M"}}})["name"] == "N M"
    assert hi.extract({"email": "not an address", "contact": "real@one.net"})["email"] == "real@one.net"
    assert hi.extract({"name": "Nobody"})["email"] == ""
    assert hi.extract("junk")["email"] == "" and hi.extract(None)["email"] == ""


def test_is_test_knows_a_placeholder_from_a_fan():
    assert hi.is_test({"email": "test@example.com"})
    assert hi.is_test({"email": "someone@hypeddit.com"})
    assert hi.is_test({"email": "sample@gmail.com"})
    assert hi.is_test({"email": "real@gmail.com", "test": True})
    assert not hi.is_test({"email": "real@gmail.com", "name": "Real"})
    assert not hi.is_test({"name": "Nobody"}), "no address is unusable, not a test"
    assert hi.mask_email("ada@example.net") == "a***@example.net"

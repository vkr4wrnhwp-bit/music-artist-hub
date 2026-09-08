"""Stage Control phase 7: the security review, as tests.

Each finding the review looked for is a test that would have caught it. The
things that were wrong when this file was written are fixed in the same
commit and named in docs/STAGE_CONTROL_PHASE7.md: the device token used to
travel in a redirect URL, and neither the server nor the daemon checked the
command name against the vocabulary before handing a signed body to the
adapter.

What is held here:

  * every /bridge/* endpoint is Bearer-only, answers 401 to a missing, wrong
    or revoked token with the SAME body, and ignores a session cookie;
  * the signature covers the canonical body and a one-byte change anywhere
    in it, or in the signature, is refused - on the server and in the daemon;
  * a nonce cannot be reused: the column is UNIQUE, a settled command is
    refused as replayed, the daemon keeps what it has seen;
  * expiry is honoured wherever a command is handled;
  * the command allowlist is checked on both sides of the wire;
  * the request rate limit counts what is still open;
  * a guest token is re-checked on every guest route;
  * no page and no JSON echoes a token, a signing key or an HMAC, and the
    diagnostic export is checked column by column;
  * CSRF: the app has no CSRF token anywhere (phase 1 audit); its posture is
    SameSite=Lax session cookies plus the login wall, and the device door
    does not use cookies at all. Stage Control matches that and this test
    records it so a later CSRF rollout knows where to look.
"""
from datetime import datetime, timedelta, timezone
import json
import os
import re
import sqlite3
import sys
import uuid

import pytest

import advance_store as adv
import app as appmod
import db as store
import passport_store as ps
import stage_adapters as sa
import stage_bridge as sb
import stage_rack as rack
import stage_store as st
import tour_store as ts

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))
import stage_bridge_daemon as daemon  # noqa: E402

PASSWORD = "secure-rooms-123"
DEVICE_PATHS = ("/bridge/heartbeat", "/bridge/pull", "/bridge/ack", "/bridge/reconcile")


@pytest.fixture(scope="module")
def application():
    return appmod.app


def _account(application, label="sec"):
    email = "%s-%s@example.net" % (label, uuid.uuid4().hex[:10])
    client = application.test_client()
    client.post("/signup", data={"name": label.title(), "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        user = store.get_user_by_email(email)
    return client, user


@pytest.fixture
def show(application):
    client, user = _account(application)
    with application.app_context():
        pid = ps.create_passport(user["id"], artist_name="Prayers")
        ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
        ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", safe_start="-20 dB", sort=1)
        ps.publish(pid, user["id"])
        sid = "show-" + uuid.uuid4().hex[:10]
        adv.attach(sid, user["id"], pid)
        dev, token = sb.register(user["id"], sid, "Rack A")
        sb.arm(dev["id"], user["id"])
        sb.heartbeat(sb.get_device(dev["id"]), {"ok": True})
    return {"client": client, "user": user, "show": sid, "device": sb.get_device(dev["id"]),
            "token": token}


def _approved(show):
    with show["client"].application.app_context():
        uid = show["user"]["id"]
        rid = st.submit(show["show"], uid, "Leafar", "Mix 1", "more", source="Lead Vox", step_db=2,
                        allowed_mixes=["Mix 1"], allowed_sources=["Lead Vox"])
        st.approve(rid, uid, actor="eng")
        cmd, d = sb.issue(rid, uid, actor="eng")
    assert d.allowed
    return rid, cmd


# --- the device door -------------------------------------------------------------

@pytest.mark.parametrize("path", DEVICE_PATHS)
def test_every_device_endpoint_rejects_missing_wrong_and_revoked_tokens_alike(show, application, path):
    anon = application.test_client()
    with application.app_context():
        _dev, doomed = sb.register(show["user"]["id"], "show-" + uuid.uuid4().hex[:8], "Doomed")
        sb.revoke(_dev["id"], show["user"]["id"])
    answers = []
    for headers in ({}, {"Authorization": "Bearer " + "x" * 43},
                    {"Authorization": "Bearer " + doomed},
                    {"Authorization": "Basic abc"}, {"Authorization": "Bearer "}):
        r = anon.post(path, json={}, headers=headers)
        assert r.status_code == 401, (path, headers)
        answers.append(r.get_data(as_text=True))
    assert len(set(answers)) == 1, "a wrong token and a revoked one must read the same"
    assert "device" not in answers[0].lower() or "unauthorised" in answers[0]
    assert application.test_client().get(path).status_code in (401, 405)


def test_a_session_cookie_is_not_a_device_credential(show):
    """The owner's own browser session opens nothing on /bridge/*: the door
    is Bearer-only, which is also why it is immune to CSRF."""
    for path in DEVICE_PATHS:
        assert show["client"].post(path, json={}).status_code == 401, path


# --- signatures -----------------------------------------------------------------------

def test_a_one_byte_change_anywhere_in_the_body_or_signature_is_refused(show):
    rid, cmd = _approved(show)
    with show["client"].application.app_context():
        dev = sb.device_for_show(show["show"], show["user"]["id"])
        sb.pull(dev)
        cmd = sb.get_command(cmd["id"])
        assert sb.verify_for_device(cmd, dev).allowed
        for field in sb.BODY_FIELDS:
            bent = dict(cmd)
            v = bent[field]
            if isinstance(v, int) and not isinstance(v, bool) and v is not None:
                bent[field] = v + 1
            elif v is None:
                bent[field] = 1
            else:
                bent[field] = (str(v) + "x") if not str(v) else (chr(ord(str(v)[0]) ^ 1) + str(v)[1:])
            d = sb.verify_for_device(bent, dev)
            assert not d.allowed, field
            assert d.code in ("bad_signature", "wrong_device", "not_allowed"), (field, d.code)
        sig = cmd["signature"]
        flipped = ("1" if sig[0] != "1" else "2") + sig[1:]
        assert sb.verify_for_device(dict(cmd, signature=flipped), dev).code == "bad_signature"
        assert sb.verify_for_device(dict(cmd, signature=""), dev).code == "bad_signature"
        # The daemon makes the same refusal with its own copy of the check.
        body = sb.wire(cmd)
        assert daemon.verify(body, dev["signing_key"], set())[0]
        assert daemon.verify(dict(body, step_db=3), dev["signing_key"], set())[1] == "bad_signature"
        assert daemon.verify(dict(body, signature=flipped), dev["signing_key"], set())[1] == "bad_signature"


def test_the_signature_is_over_the_canonical_body_only(show):
    """Extra keys do not change the signature; a bridge cannot be fed a
    body that verifies but carries a smuggled field the adapter would read."""
    _rid, cmd = _approved(show)
    with show["client"].application.app_context():
        dev = sb.device_for_show(show["show"], show["user"]["id"])
    assert sb.sign(dict(cmd, extra="ignored"), dev["signing_key"]) == cmd["signature"]
    assert set(json.loads(sb.canonical(cmd))) == set(sb.BODY_FIELDS)
    assert daemon.BODY_FIELDS == sb.BODY_FIELDS


# --- nonces and expiry ------------------------------------------------------------------

def test_a_nonce_cannot_be_reused(show):
    _rid, cmd = _approved(show)
    with show["client"].application.app_context():
        dev = sb.device_for_show(show["show"], show["user"]["id"])
        with pytest.raises(sqlite3.IntegrityError):
            with store.get_db() as db:
                db.execute(
                    "INSERT INTO stage_commands (id, device_id, show_id, user_id, request_id, command, "
                    "nonce, issued, expires, signature, created, updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("dup", dev["id"], show["show"], show["user"]["id"], "r", "mute_state",
                     cmd["nonce"], cmd["issued"], cmd["expires"], "s", cmd["created"], cmd["created"]))
        sb.pull(dev)
        sb.acknowledge(dev, cmd["id"], cmd["nonce"], {"ok": True, "confirmed": True})
        assert sb.acknowledge(dev, cmd["id"], cmd["nonce"], {"ok": False})[1].code == "replayed"
        assert sb.reconcile(dev, [{"command_id": cmd["id"], "nonce": cmd["nonce"],
                                   "result": {"ok": True}}])[0]["code"] == "replayed"
    body = sb.wire(cmd)
    seen = set()
    assert daemon.verify(body, dev["signing_key"], seen)[0]
    seen.add(body["nonce"])
    assert daemon.verify(body, dev["signing_key"], seen)[1] == "replayed"


def test_expiry_is_honoured_at_pull_verify_ack_and_the_desk_poll(show):
    _rid, cmd = _approved(show)
    late = datetime.now(timezone.utc) + timedelta(seconds=300)
    with show["client"].application.app_context():
        dev = sb.device_for_show(show["show"], show["user"]["id"])
        assert sb.pull(dev, now=late) == []
        assert sb.get_command(cmd["id"])["state"] == "expired"
        _rid2, cmd2 = _approved(show)
        sb.pull(dev)
        assert sb.verify_for_device(sb.get_command(cmd2["id"]), dev, now=late).code == "expired"
        assert sb.acknowledge(dev, cmd2["id"], cmd2["nonce"], {"ok": True, "confirmed": True},
                              now=late)[1].code == "expired"
        _rid3, cmd3 = _approved(show)
        sb.pull(dev)
        assert sb.expire_stale(show["show"], show["user"]["id"], now=late) == 1
    assert daemon.verify(sb.wire(cmd3), dev["signing_key"], set(),
                         now=late.timestamp())[1] == "expired"


# --- the allowlist ----------------------------------------------------------------------

def test_the_command_allowlist_is_checked_on_both_sides_of_the_wire(show):
    _rid, cmd = _approved(show)
    with show["client"].application.app_context():
        dev = sb.device_for_show(show["show"], show["user"]["id"])
        sb.pull(dev)
        cmd = sb.get_command(cmd["id"])
        for bad in sa.NEVER + ("read_send_level", "", None, "SEND_LEVEL_DELTA"):
            forged = dict(cmd, command=bad)
            forged["signature"] = sb.sign(forged, dev["signing_key"])
            assert sb.verify_for_device(forged, dev).code == "not_allowed", bad
            body = sb.wire(forged)
            assert daemon.verify(body, dev["signing_key"], set())[1] == "not_allowed", bad
    assert set(daemon.ALLOWED_COMMANDS) == set(sa.WRITES)
    sim = sa.SimulatorAdapter()
    assert daemon.apply(sim, dict(sb.wire(cmd), command="preamp_gain"))["ok"] is False
    assert sim.writes == 0


# --- rate limit -------------------------------------------------------------------------

def test_the_request_rate_limit_counts_open_requests(show):
    with show["client"].application.app_context():
        uid = show["user"]["id"]
        for _ in range(6):
            st.submit(show["show"], uid, "Leafar", "Mix 1", "more", source="Lead Vox", step_db=1,
                      allowed_mixes=["Mix 1"], allowed_sources=["Lead Vox"])
        with pytest.raises(st.Refused):
            st.submit(show["show"], uid, "Leafar", "Mix 1", "more", source="Lead Vox", step_db=1,
                      allowed_mixes=["Mix 1"], allowed_sources=["Lead Vox"])
        assert len(st.for_performer(show["show"], "Leafar", open_only=True)) == 6
        assert len(st.for_performer(show["show"], "Javon", open_only=True)) == 0


# --- guests -------------------------------------------------------------------------------

@pytest.fixture
def guest(application):
    client, user = _account(application, "gsec")
    r = client.post("/tours/new", data={
        "name": "Sec Run", "artist_name": "Prayers", "start_date": "2030-05-01",
        "end_date": "2030-05-10", "home_tz": "America/New_York", "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = client.post("/tours/%s/days/add" % tid, data={
        "date": "2030-05-02", "kind": "show", "venue": "Room", "city": "Nashville, TN",
        "tz": "America/Chicago"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    with application.app_context():
        pid = ps.create_passport(user["id"], artist_name="Prayers")
        ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
        ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", sort=1)
        ps.publish(pid, user["id"])
        adv.attach(sid, user["id"], pid)

    def link(**extra):
        data = {"scope": "stage", "show_id": sid}
        data.update(extra)
        with application.app_context():
            before = {l["id"] for l in ts.list_share_links(tid)}
        client.post("/tours/%s/share/new" % tid, data=data)
        with application.app_context():
            rows = [l for l in ts.list_share_links(tid) if l["id"] not in before]
        return rows[0]

    return {"client": client, "user": user, "tour": tid, "show": sid, "link": link}


def _guest_routes(token, rid="r"):
    return (("get", "/stage/guest/%s" % token), ("get", "/stage/guest/%s?as=Leafar" % token),
            ("post", "/stage/guest/%s/ask" % token), ("post", "/stage/guest/%s/cancel/%s" % (token, rid)),
            ("get", "/stage/guest/%s/events?since=0" % token))


def test_the_guest_token_is_rechecked_on_every_guest_route(guest, application):
    phone = application.test_client()
    live = guest["link"]()
    for method, path in _guest_routes(live["token"]):
        r = getattr(phone, method)(path, data={})
        assert r.status_code in (200, 302, 404), (path, r.status_code)   # cancel of a bad id is 404
    guest["client"].post("/tours/%s/share/%s/revoke" % (guest["tour"], live["id"]))
    for method, path in _guest_routes(live["token"]):
        assert getattr(phone, method)(path, data={}).status_code == 404, ("revoked", path)
    old = guest["link"](expires="2001-01-01")
    for method, path in _guest_routes(old["token"]):
        assert getattr(phone, method)(path, data={}).status_code == 410, ("expired", path)
    locked = guest["link"](password="encore")
    for method, path in _guest_routes(locked["token"]):
        r = getattr(phone, method)(path, data={})
        if path.endswith("/events?since=0"):
            assert r.status_code == 401, path
        else:
            assert r.status_code in (302, 303) and "/tour-share/" in r.headers["Location"], path
    other = guest["link"](scope="setlist")
    for method, path in _guest_routes(other["token"]):
        assert getattr(phone, method)(path, data={}).status_code == 404, ("scope", path)
    assert phone.get("/stage/guest/%s" % ("z" * 32)).status_code == 404


# --- nothing echoes a secret ------------------------------------------------------------------

def _secrets(show):
    with show["client"].application.app_context():
        dev = sb.get_device(show["device"]["id"])
        cmds = sb.commands_for_show(show["show"], show["user"]["id"], limit=100)
    out = {"token": show["token"], "signing_key": dev["signing_key"], "token_hash": dev["token_hash"]}
    for c in cmds:
        out["signature:" + c["id"][:6]] = c["signature"]
    return out


def test_no_page_or_json_echoes_a_token_a_signing_key_or_an_hmac(show, application):
    _approved(show)
    _approved(show)
    c, sid = show["client"], show["show"]
    secrets = _secrets(show)
    bodies = {
        "desk": c.get("/stage/%s" % sid).get_data(as_text=True),
        "bridge": c.get("/stage/%s/bridge" % sid).get_data(as_text=True),
        "events": c.get("/stage/%s/events?since=0" % sid).get_data(as_text=True),
        "diagnostics": c.get("/stage/%s/bridge/diagnostics.json" % sid).get_data(as_text=True),
        "performer": c.get("/stage/%s/me?as=Leafar" % sid).get_data(as_text=True),
    }
    dev = application.test_client()
    auth = {"Authorization": "Bearer " + show["token"]}
    bodies["pull"] = dev.post("/bridge/pull", json={}, headers=auth).get_data(as_text=True)
    bodies["heartbeat"] = dev.post("/bridge/heartbeat", json={}, headers=auth).get_data(as_text=True)
    for name, body in bodies.items():
        for label, value in secrets.items():
            if name == "pull" and label.startswith("signature:"):
                continue   # the device is handed its own signatures; that is the protocol
            assert value not in body, "%s echoes %s" % (name, label)
        assert "signing_key" not in body, name
        assert "token_hash" not in body, name
    # The one place the token is shown is the page right after registration,
    # and it never went through the address bar.
    with application.app_context():
        sb.revoke(show["device"]["id"], show["user"]["id"])
    r = c.post("/stage/%s/bridge/register" % sid, data={"name": "Rack B", "adapter": "simulator"})
    assert "token" not in r.headers["Location"].replace("credentials=once", "")
    once = c.get(r.headers["Location"]).get_data(as_text=True)
    shown = re.search(r'<p class="sc-token">([^<]+)</p>', once).group(1)
    with application.app_context():
        assert sb.authenticate(shown)["name"] == "Rack B"
    assert shown not in c.get(r.headers["Location"]).get_data(as_text=True)
    assert shown not in c.get("/stage/%s/bridge" % sid).get_data(as_text=True)


def test_the_diagnostic_export_is_redacted_column_by_column(show):
    _approved(show)
    with show["client"].application.app_context():
        body = rack.diagnostics(show["show"], show["user"]["id"])
        dev = sb.get_device(show["device"]["id"])
    text = json.dumps(body)
    assert show["token"] not in text and dev["signing_key"] not in text and dev["token_hash"] not in text
    for c in body["commands"]:
        assert "signature" not in c and "signing_key" not in c
        assert "nonce" in c, "the nonce is not a secret; it is what the audit joins on"
    assert body["device"]["fingerprint"] == dev["token_hash"][:8]
    assert len(body["device"]["fingerprint"]) == 8
    for col in rack.SECRET_COLUMNS:
        assert col not in text or col == "signature" and '"signature"' not in text
    r = show["client"].get("/stage/%s/bridge/diagnostics.json" % show["show"])
    assert r.status_code == 200 and r.mimetype == "application/json"
    assert r.headers.get("Cache-Control") == "no-store"


# --- CSRF posture -------------------------------------------------------------------------------

def test_csrf_posture_matches_the_rest_of_the_app(show, application):
    """There is no CSRF token anywhere in the app (phase 1 audit). Its
    posture is the SameSite=Lax session cookie and the login wall, and
    Stage Control matches it: every state-changing route needs the session,
    an anonymous POST is sent to the login and changes nothing, and the
    device door uses no cookie at all. Recorded here, not hidden."""
    assert application.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert application.config["SESSION_COOKIE_HTTPONLY"] is not False
    src = open(os.path.join(HERE, "app.py"), encoding="utf-8").read()
    assert "csrf" not in src.lower(), "a CSRF token exists now; wire Stage Control's forms to it"
    anon = application.test_client()
    sid = show["show"]
    with application.app_context():
        rid = st.submit(sid, show["user"]["id"], "Leafar", "Mix 1", "more", source="Lead Vox",
                        step_db=1, allowed_mixes=["Mix 1"], allowed_sources=["Lead Vox"])
    for path in ("/stage/%s/request/%s/approve" % (sid, rid), "/stage/%s/bridge/lockout" % sid,
                 "/stage/%s/bridge/revoke" % sid, "/stage/%s/lock" % sid, "/stage/%s/ask" % sid):
        r = anon.post(path, data={"scope": "show"})
        assert r.status_code in (302, 401), path
        if r.status_code == 302:
            assert "/login" in r.headers["Location"], path
    with application.app_context():
        assert st.get(rid, show["user"]["id"])["state"] == "pending"
        dev = sb.get_device(show["device"]["id"])
    assert dev["lockout"] == 0 and dev["revoked_at"] == ""

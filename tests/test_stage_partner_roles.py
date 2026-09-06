"""Partner roles for the stage rooms.

The brief lists the stage permissions and says enforce them server-side.
The rooms were owner-only; now a seat at the partner that owns the show's
account opens them with what its role carries, every act by a seat is
audited, a seat without the permission is a 403, and anybody else is a
404 - a stranger must not learn a show exists from the shape of the
refusal.
"""
import uuid

import pytest

import advance_store as adv
import app as appmod
import db as store
import partner_store as pstore
import passport_store as ps
import stage_bridge as sb
import stage_store as st

PASSWORD = "roles-rooms-123"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _account(flask_app, label):
    email = "%s-%s@example.net" % (label, uuid.uuid4().hex[:8])
    client = flask_app.test_client()
    client.post("/signup", data={"name": label.title(), "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client, store.get_user_by_email(email)


@pytest.fixture
def stage(flask_app):
    """An artist owned by a partner, with a show advanced against a published
    passport and an armed simulator; seats at the partner in every role; and
    a seat at a different partner."""
    owner_client, owner = _account(flask_app, "artist")
    partner_id = pstore.create_partner("Roles %s" % uuid.uuid4().hex[:6])
    assert pstore.attach_user(partner_id, owner["id"])
    pid = ps.create_passport(owner["id"], artist_name="Prayers")
    ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", safe_start="-20 dB", sort=1)
    ps.publish(pid, owner["id"])
    show = "show-" + uuid.uuid4().hex[:10]
    adv.attach(show, owner["id"], pid)
    dev, _t = sb.register(owner["id"], show, "Rack A")
    sb.arm(dev["id"], owner["id"])
    sb.heartbeat(sb.get_device(dev["id"]), {"ok": True})

    seats = {}
    for role in ("admin", "manager", "support", "viewer"):
        client, user = _account(flask_app, role)
        pstore.add_member(partner_id, user["email"], name=user["name"], role=role, user_id=user["id"])
        seats[role] = client
    other_client, other = _account(flask_app, "elsewhere")
    other_partner = pstore.create_partner("Other %s" % uuid.uuid4().hex[:6])
    pstore.add_member(other_partner, other["email"], name=other["name"], role="owner", user_id=other["id"])
    return {"owner": owner_client, "owner_user": owner, "partner": partner_id, "show": show,
            "seats": seats, "stranger": other_client, "device": dev}


def _ask(stage):
    return st.submit(stage["show"], stage["owner_user"]["id"], "Leafar", "Mix 1", "more",
                     source="Lead Vox", step_db=2, allowed_mixes=["Mix 1"], allowed_sources=["Lead Vox"])


# --- who gets in --------------------------------------------------------------------

def test_a_stranger_gets_a_404_not_a_403(stage):
    assert stage["stranger"].get("/stage/%s" % stage["show"]).status_code == 404
    assert stage["stranger"].get("/stage/%s/bridge" % stage["show"]).status_code == 404
    assert stage["stranger"].post("/stage/%s/bridge/lockout" % stage["show"]).status_code == 404


def test_every_seat_with_review_opens_the_desk_and_a_viewer_does_not(stage):
    for role in ("admin", "manager", "support"):
        r = stage["seats"][role].get("/stage/%s" % stage["show"])
        assert r.status_code == 200, role
        assert "Connected Control" in r.get_data(as_text=True)
    assert stage["seats"]["viewer"].get("/stage/%s" % stage["show"]).status_code == 403


def test_a_seat_decides_on_a_request_in_the_owners_queue_and_is_named(stage):
    rid = _ask(stage)
    r = stage["seats"]["support"].post("/stage/%s/request/%s/acknowledge" % (stage["show"], rid))
    assert r.status_code in (302, 303)
    req = st.get(rid, stage["owner_user"]["id"])
    assert req["state"] == "acknowledged" and req["engineer"] == "Support"
    trail = pstore.audit_trail(stage["partner"], subject_user_id=stage["owner_user"]["id"])
    assert any(a["action"] == "stage.stage_review" and a["detail"].endswith("/acknowledge") for a in trail)


# --- operate ---------------------------------------------------------------------------

def test_support_may_review_but_not_send_to_the_console(stage):
    rid = _ask(stage)
    st.approve(rid, stage["owner_user"]["id"], actor="Owner")
    desk = stage["seats"]["support"].get("/stage/%s" % stage["show"]).get_data(as_text=True)
    assert "Send to the console" not in desk
    r = stage["seats"]["support"].post("/stage/%s/request/%s/send" % (stage["show"], rid))
    assert r.status_code == 403
    assert st.get(rid, stage["owner_user"]["id"])["state"] == "approved"


def test_a_manager_sends_and_the_change_is_applied_in_the_owners_account(stage):
    rid = _ask(stage)
    st.approve(rid, stage["owner_user"]["id"], actor="Owner")
    desk = stage["seats"]["manager"].get("/stage/%s" % stage["show"]).get_data(as_text=True)
    assert "Send to the console" in desk
    r = stage["seats"]["manager"].post("/stage/%s/request/%s/send" % (stage["show"], rid))
    assert r.status_code in (302, 303) and "refused" not in r.headers["Location"]
    assert st.get(rid, stage["owner_user"]["id"])["state"] == "applied"


# --- configure and lockout --------------------------------------------------------------

def test_only_owner_and_admin_configure_the_bridge(stage):
    assert stage["seats"]["admin"].get("/stage/%s/bridge" % stage["show"]).status_code == 200
    for role in ("manager", "support", "viewer"):
        assert stage["seats"][role].get("/stage/%s/bridge" % stage["show"]).status_code == 403, role
        assert stage["seats"][role].post("/stage/%s/bridge/disarm" % stage["show"]).status_code == 403, role
    desk = stage["seats"]["manager"].get("/stage/%s" % stage["show"]).get_data(as_text=True)
    assert "/stage/%s/bridge\"" % stage["show"] not in desk, "no door to a room the seat cannot enter"


def test_every_seat_can_press_the_emergency_stop(stage):
    desk = stage["seats"]["support"].get("/stage/%s" % stage["show"]).get_data(as_text=True)
    assert "EMERGENCY LOCKOUT" in desk
    r = stage["seats"]["viewer"].post("/stage/%s/bridge/lockout" % stage["show"], data={"reason": "Feedback"})
    assert r.status_code in (302, 303)
    dev = sb.get_device(stage["device"]["id"])
    assert dev["lockout"] == 1 and dev["armed"] == 0
    assert sb.mode(stage["show"], stage["owner_user"]["id"])["code"] == "lockout"
    trail = pstore.audit_trail(stage["partner"], subject_user_id=stage["owner_user"]["id"])
    assert any(a["action"] == "stage.stage_lockout" for a in trail)


def test_the_owner_still_holds_everything_without_a_seat(stage):
    c = stage["owner"]
    assert c.get("/stage/%s" % stage["show"]).status_code == 200
    assert c.get("/stage/%s/bridge" % stage["show"]).status_code == 200
    rid = _ask(stage)
    st.approve(rid, stage["owner_user"]["id"], actor="Owner")
    r = c.post("/stage/%s/request/%s/send" % (stage["show"], rid))
    assert r.status_code in (302, 303)


def test_a_seat_at_the_partner_cannot_reach_a_show_the_partner_does_not_own(flask_app, stage):
    """Ownership is the account's partner_id, checked per show; a seat is not
    a key to every stage on the platform."""
    solo_client, solo = _account(flask_app, "solo")
    pid = ps.create_passport(solo["id"], artist_name="Solo")
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Solo", sort=1)
    ps.publish(pid, solo["id"])
    show = "show-" + uuid.uuid4().hex[:10]
    adv.attach(show, solo["id"], pid)
    assert stage["seats"]["admin"].get("/stage/%s" % show).status_code == 404

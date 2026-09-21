"""A Label seats its roster; anyone paying seats their team; nobody else
gets in.

Owner, 2026-09-17: "yes let labels invite their roster or team invites to
work", with public sign-up staying shut. That makes these two the only
doors through which an account other than the owner's can cause an account
to exist, which is why they get their own file.

The three things that have to stay true together. Any one of them alone is
worse than useless:

  the door opens      a Label's roster invitation creates an account while
                      /signup refuses a stranger
  only for those who  a Fan could mint invitation tokens before this; they
  may seat somebody   were merely unredeemable. Roster needs Label, team
                      needs a paid plan, and the issuing account is
                      checked again when the invitation is redeemed
  a plan cannot be    /plan/switch used to hand out any tier on a service
  taken for free      with no Stripe key, which would have let an account
                      promote itself to Label and then mint accounts
"""
import uuid

import pytest

import db as store
from app import create_app

PW = "customer-invites-1"


def _addr(tag):
    return "%s-%s@example.net" % (tag, uuid.uuid4().hex[:8])


@pytest.fixture
def app_obj(monkeypatch):
    """A deployed service with the public door shut, which is live."""
    monkeypatch.setenv("RENDER", "true")
    # RENDER is set here to reach the deployed-service behaviour,
    # not to exercise the sign-up guard. This file posts straight
    # to /signup with no rendered form, so it carries no signed
    # stamp and the guard would refuse it. The guard is tested on
    # purpose in tests/test_signup_guard_wired.py.
    monkeypatch.setenv("SIGNUP_GUARD", "off")
    monkeypatch.delenv("SIGNUP_MODE", raising=False)
    monkeypatch.setenv("OWNER_EMAILS", "nobody-here@example.invalid")
    return create_app()


def _account(app_obj, plan="artist"):
    """An account on a plan, seated the way the owner seats one: directly,
    not through /plan/switch, which is checkout's job."""
    email = _addr(plan)
    c = app_obj.test_client()
    # Sign-up is shut, so make the account the way an invitation does.
    from werkzeug.security import generate_password_hash
    with app_obj.app_context():
        uid = store.create_user(email, plan.title(), generate_password_hash(PW))
        store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    c._email, c._id = email, uid
    return c


# --- while sign-up is shut, a member's link makes no account ---------------
# Owner, 2026-09-19: "yes shut those also". The 2026-09-18 exception that let
# roster and team links mint accounts is closed while public sign-up is shut;
# they still join an account that exists. The owner's own invitation is the
# only door. The tests below that seat NEW people open sign-up first.

def test_while_shut_a_roster_or_team_link_makes_no_account(app_obj):
    label = _account(app_obj, "label")
    newcomer = _addr("newcomer")
    label.post("/roster/invite", data={"email": newcomer})
    with app_obj.app_context():
        rtoken = [m for m in store.list_roster(label._id) if m["email"] == newcomer][0]["invite_token"]
    page = app_obj.test_client().get("/roster/join/" + rtoken).get_data(as_text=True)
    assert "can only add someone who already has an account" in page and 'name="password"' not in page
    r = app_obj.test_client().post("/roster/join/" + rtoken, data={"name": "New", "password": PW})
    assert r.status_code == 403
    artist = _account(app_obj, "artist")
    manager = _addr("manager-shut")
    artist.post("/team/invite", data={"email": manager, "role": "manager"})
    with app_obj.app_context():
        ttoken = [m for m in store.list_team(artist._id) if m["email"] == manager][0]["invite_token"]
    r = app_obj.test_client().post("/team/join/" + ttoken, data={"name": "New", "password": PW})
    assert r.status_code == 403
    with app_obj.app_context():
        assert store.get_user_by_email(newcomer) is None and store.get_user_by_email(manager) is None


def test_while_shut_a_link_still_joins_an_account_that_exists(app_obj):
    label = _account(app_obj, "label")
    existing = _account(app_obj, "artist")
    label.post("/roster/invite", data={"email": existing._email})
    with app_obj.app_context():
        token = [m for m in store.list_roster(label._id) if m["email"] == existing._email][0]["invite_token"]
    r = app_obj.test_client().post("/roster/join/" + token, data={"password": PW})
    assert r.status_code == 302
    with app_obj.app_context():
        assert store.get_roster_member(label._id, existing._id) is not None


# --- the door opens for a Label ------------------------------------------

def test_a_label_seats_a_roster_artist_while_a_stranger_is_refused(app_obj, monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    label = _account(app_obj, "label")
    artist_email = _addr("signed")

    r = label.post("/roster/invite", data={"email": artist_email})
    assert r.status_code in (302, 200)
    with app_obj.app_context():
        rows = [m for m in store.list_roster(label._id) if m["email"] == artist_email]
    assert rows, "the invitation exists"
    token = rows[0]["invite_token"]

    joiner = app_obj.test_client()
    r = joiner.post("/roster/join/" + token,
                    data={"name": "Seated", "password": PW})
    assert r.status_code == 302, r.status_code
    with app_obj.app_context():
        assert store.get_user_by_email(artist_email) is not None

    # The public door is the owner's switch; the members' links follow it.
    monkeypatch.delenv("SIGNUP_MODE", raising=False)
    stranger = _addr("stranger")
    app_obj.test_client().post("/signup", data={"name": "No", "email": stranger,
                                                "password": PW})
    with app_obj.app_context():
        assert store.get_user_by_email(stranger) is None


def test_a_paying_artist_seats_a_manager(app_obj, monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    artist = _account(app_obj, "artist")
    manager = _addr("manager")
    r = artist.post("/team/invite", data={"email": manager, "role": "manager"})
    assert r.status_code == 200 and r.get_json().get("ok"), r.get_json()
    with app_obj.app_context():
        token = [m for m in store.list_team(artist._id)
                 if m["email"] == manager][0]["invite_token"]
    r = app_obj.test_client().post("/team/join/" + token,
                                   data={"name": "Manager", "password": PW})
    assert r.status_code == 302
    with app_obj.app_context():
        assert store.get_user_by_email(manager) is not None


def test_the_invitation_names_the_address_and_the_form_cannot_move_it(app_obj, monkeypatch):
    """Otherwise one invitation is an account for anybody who gets it."""
    monkeypatch.setenv("SIGNUP_MODE", "open")
    label = _account(app_obj, "label")
    invited = _addr("invited")
    label.post("/roster/invite", data={"email": invited})
    with app_obj.app_context():
        token = [m for m in store.list_roster(label._id)
                 if m["email"] == invited][0]["invite_token"]
    elsewhere = _addr("elsewhere")
    app_obj.test_client().post("/roster/join/" + token,
                               data={"name": "Someone", "password": PW,
                                     "email": elsewhere})
    with app_obj.app_context():
        assert store.get_user_by_email(elsewhere) is None, "the form was obeyed"
        assert store.get_user_by_email(invited) is not None


# --- only for accounts that may seat somebody ----------------------------

def test_a_fan_cannot_seat_a_team(app_obj):
    fan = _account(app_obj, "fan")
    r = fan.post("/team/invite", data={"email": _addr("nope"), "role": "manager"})
    assert r.status_code == 402, r.status_code
    with app_obj.app_context():
        assert store.list_team(fan._id) == []


def test_only_a_label_can_seat_a_roster(app_obj):
    for plan in ("fan", "artist", "pro"):
        c = _account(app_obj, plan)
        target = _addr("roster-" + plan)
        c.post("/roster/invite", data={"email": target})
        with app_obj.app_context():
            assert store.list_roster(c._id) == [], plan
            assert store.get_user_by_email(target) is None, plan


def test_a_label_that_downgrades_has_no_live_invitations_left(app_obj, monkeypatch):
    """Checked at redemption, not only when the invitation was written, so
    a cancelled Label cannot keep seating people from a stack of links."""
    monkeypatch.setenv("SIGNUP_MODE", "open")
    label = _account(app_obj, "label")
    later = _addr("later")
    label.post("/roster/invite", data={"email": later})
    with app_obj.app_context():
        token = [m for m in store.list_roster(label._id)
                 if m["email"] == later][0]["invite_token"]
        store.set_user_plan(label._id, "artist")       # downgraded

    r = app_obj.test_client().post("/roster/join/" + token,
                                   data={"name": "Late", "password": PW})
    assert r.status_code == 403
    with app_obj.app_context():
        assert store.get_user_by_email(later) is None


def test_an_invitation_from_an_account_that_no_longer_exists_is_dead(app_obj):
    label = _account(app_obj, "label")
    orphan = _addr("orphan")
    label.post("/roster/invite", data={"email": orphan})
    with app_obj.app_context():
        token = [m for m in store.list_roster(label._id)
                 if m["email"] == orphan][0]["invite_token"]
        with store.get_db() as db:
            db.execute("DELETE FROM users WHERE id = ?", (label._id,))
    r = app_obj.test_client().post("/roster/join/" + token,
                                   data={"name": "Orphan", "password": PW})
    # The page renders (200) or refuses (403/404); either is fine. What is
    # not fine is an account, and there must not be one.
    assert r.status_code in (200, 403, 404), r.status_code
    with app_obj.app_context():
        assert store.get_user_by_email(orphan) is None


# --- and a plan cannot be taken for free ---------------------------------

@pytest.mark.parametrize("plan", ["artist", "pro", "label"])
def test_no_account_reaches_a_paid_tier_without_checkout(app_obj, plan):
    """The gate above is only worth having if this holds: an account that
    can promote itself to Label can mint accounts."""
    c = _account(app_obj, "fan")
    c.post("/plan/switch", data={"plan": plan})
    with app_obj.app_context():
        assert (store.get_user(c._id).get("plan") or "") == "fan", plan


def test_off_a_deployed_service_the_suite_can_still_switch(monkeypatch):
    """The tests and a laptop keep instant switching, or most of the suite
    would have nothing to run against."""
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.setenv("SIGNUP_MODE", "open")
    local = create_app()
    email = _addr("local")
    c = local.test_client()
    c.post("/signup", data={"name": "Local", "email": email, "password": PW})
    c.post("/plan/switch", data={"plan": "label"})
    with local.app_context():
        assert (store.get_user_by_email(email).get("plan") or "") == "label"

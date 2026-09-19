"""An invitation proves it was sent, never who opened it.

Found by the 2026-09-18 launch check: both join doors signed the visitor
into the invited address's EXISTING account from the token alone. Any paid
account can mint a team invitation, so anyone paying $29 could invite a
stranger's address (or the owner's), open the link themselves and be signed
in as that person with no password. The same went for a Label's roster
link, and the shared demo login is a Label.

What has to hold now, for both doors:
  - a new address still becomes an account from the invitation alone
  - an existing account is joined only by its owner: someone signed in as
    exactly that account, or someone who types its password on the page
  - a wrong or missing password changes nothing and signs nobody in
  - someone signed in as a DIFFERENT account is not switched into it

Plus two holes closed beside it: the login page followed any ?next= off
the site, and any Label account could delete and re-create the platform's
production Stripe webhook.
"""
import uuid

import pytest
from werkzeug.security import generate_password_hash

import db as store
from app import create_app

PW = "takeover-pass-1"
VICTIM_PW = "victim-pass-1"


def _addr(tag):
    return "%s-%s@example.net" % (tag, uuid.uuid4().hex[:8])


@pytest.fixture
def app_obj(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.delenv("SIGNUP_MODE", raising=False)
    monkeypatch.setenv("OWNER_EMAILS", "nobody-here@example.invalid")
    return create_app()


def _account(app_obj, plan="artist", password=PW, sign_in=True):
    email = _addr(plan)
    c = app_obj.test_client()
    with app_obj.app_context():
        uid = store.create_user(email, plan.title(), generate_password_hash(password))
        store.set_user_plan(uid, plan)
    if sign_in:
        c.post("/login", data={"email": email, "password": password})
    c._email, c._id = email, uid
    return c


def _whoami(client):
    with client.session_transaction() as s:
        return s.get("user_id")


def _team_token(app_obj, inviter, email):
    r = inviter.post("/team/invite", data={"email": email, "role": "manager"})
    assert r.get_json().get("ok"), r.get_json()
    with app_obj.app_context():
        return [m for m in store.list_team(inviter._id) if m["email"] == email][0]["invite_token"]


def _roster_token(app_obj, label, email):
    label.post("/roster/invite", data={"email": email})
    with app_obj.app_context():
        return [m for m in store.list_roster(label._id) if m["email"] == email][0]["invite_token"]


DOORS = [("team", _team_token, "artist"), ("roster", _roster_token, "label")]


@pytest.mark.parametrize("door,mint,plan", DOORS)
def test_the_token_alone_no_longer_signs_anyone_into_an_existing_account(app_obj, door, mint, plan):
    victim = _account(app_obj, "pro", password=VICTIM_PW, sign_in=False)
    attacker = _account(app_obj, plan)
    token = mint(app_obj, attacker, victim._email)

    # The attack as found: the inviter opens its own link, no fields at all.
    r = attacker.post("/%s/join/%s" % (door, token), data={})
    assert r.status_code == 403
    assert _whoami(attacker) == attacker._id, "still the attacker, not the victim"
    assert b"Enter its password" in r.data

    # A stranger with no session and a wrong password gets nothing either.
    anon = app_obj.test_client()
    r = anon.post("/%s/join/%s" % (door, token), data={"password": "guessing-1"})
    assert r.status_code == 403 and _whoami(anon) is None


@pytest.mark.parametrize("door,mint,plan", DOORS)
def test_the_accounts_own_password_accepts_and_signs_in(app_obj, door, mint, plan):
    victim = _account(app_obj, "artist", password=VICTIM_PW, sign_in=False)
    inviter = _account(app_obj, plan)
    token = mint(app_obj, inviter, victim._email)

    page = app_obj.test_client().get("/%s/join/%s" % (door, token)).get_data(as_text=True)
    assert 'name="password"' in page and "already has a Street Banker account" in page

    joiner = app_obj.test_client()
    r = joiner.post("/%s/join/%s" % (door, token), data={"password": VICTIM_PW})
    assert r.status_code == 302 and "/command-center" in r.headers["Location"]
    assert _whoami(joiner) == victim._id


@pytest.mark.parametrize("door,mint,plan", DOORS)
def test_signed_in_as_that_account_it_accepts_without_asking_again(app_obj, door, mint, plan):
    invitee = _account(app_obj, "artist", password=VICTIM_PW)      # signed in
    inviter = _account(app_obj, plan)
    token = mint(app_obj, inviter, invitee._email)

    page = invitee.get("/%s/join/%s" % (door, token)).get_data(as_text=True)
    assert "signed in as" in page and 'name="password"' not in page
    r = invitee.post("/%s/join/%s" % (door, token), data={})
    assert r.status_code == 302 and _whoami(invitee) == invitee._id


@pytest.mark.parametrize("door,mint,plan", DOORS)
def test_a_new_address_still_becomes_an_account_from_the_invitation(app_obj, door, mint, plan, monkeypatch):
    # Only with sign-up open: while it is shut these links make no account
    # (owner, 2026-09-19; tests/test_customer_invites.py).
    monkeypatch.setenv("SIGNUP_MODE", "open")
    inviter = _account(app_obj, plan)
    fresh = _addr("fresh")
    token = mint(app_obj, inviter, fresh)
    joiner = app_obj.test_client()
    r = joiner.post("/%s/join/%s" % (door, token), data={"name": "Fresh", "password": PW})
    assert r.status_code == 302
    with app_obj.app_context():
        made = store.get_user_by_email(fresh)
    assert made is not None and _whoami(joiner) == made["id"]


def test_a_locked_account_is_not_signed_in_by_a_join_link(app_obj):
    victim = _account(app_obj, "artist", password=VICTIM_PW, sign_in=False)
    inviter = _account(app_obj, "artist")
    token = _team_token(app_obj, inviter, victim._email)
    with app_obj.app_context():
        with store.get_db() as db:
            cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
    if "locked" not in cols:
        pytest.skip("no lock column in this schema")
    with app_obj.app_context():
        with store.get_db() as db:
            db.execute("UPDATE users SET locked = 1 WHERE id = ?", (victim._id,))
    joiner = app_obj.test_client()
    r = joiner.post("/team/join/" + token, data={"password": VICTIM_PW})
    assert r.status_code == 403 and _whoami(joiner) is None


# --- the two holes beside it ---------------------------------------------

@pytest.mark.parametrize("nxt", ["https://evil.example/", "//evil.example/", "/\\evil.example/",
                                 "/ok\r\nSet-Cookie: x=1"])
def test_sign_in_never_leaves_the_site(app_obj, nxt):
    email = _addr("login")
    with app_obj.app_context():
        store.create_user(email, "Login", generate_password_hash(PW))
    c = app_obj.test_client()
    r = c.post("/login", query_string={"next": nxt}, data={"email": email, "password": PW})
    assert r.status_code == 302
    loc = r.headers["Location"]
    assert "evil.example" not in loc and "Set-Cookie" not in loc, loc


def test_sign_in_still_returns_to_a_page_on_the_site(app_obj):
    email = _addr("back")
    with app_obj.app_context():
        store.create_user(email, "Back", generate_password_hash(PW))
    r = app_obj.test_client().post("/login", query_string={"next": "/catalog"},
                                   data={"email": email, "password": PW})
    assert r.status_code == 302 and r.headers["Location"].endswith("/catalog")


def test_only_the_owner_may_recreate_the_stripe_webhook(app_obj, monkeypatch):
    import stripe_provider
    calls = []
    monkeypatch.setattr(stripe_provider, "setup_webhook_endpoint", lambda base: calls.append(base) or True,
                        raising=False)
    label = _account(app_obj, "label")
    assert label.post("/billing/webhook-setup").status_code == 404
    assert calls == [], "a Label customer reached the production webhook"

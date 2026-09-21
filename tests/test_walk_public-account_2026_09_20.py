"""The public and account-door findings of the 2026-09-20 page walk.

Everything a person meets before they are inside the app, and the account
plumbing behind it: the billing page, the public footer, the referral
link, the door pages, the password-reset mail, the start-here checklist
and the refusal Tour hands back.

What each test pins, in the walk's words:

  Billing showed a fabricated plan, a renewal date and three paid
  invoices to any real account on a service with no Stripe.
  "Contact" in the footer opened Submit Music and "About" opened Label
  Services, while /contact and /about existed and were better.
  A referral link dropped the referrer on the way through an invitation.
  The sign-up wizard promised a distributor import that does not exist.
  The start-here checklist told an Artist to open the Rack, which
  answers 402 on a deployed service.
  Tour's refusal named the plan the account already had.
  A used password-reset link kept working for the rest of its hour.
  A signed-in person on /login, /signup or /forgot got a blank form.
"""
import re
import uuid

import pytest

import app as appmod
import db as store
import email_provider as emailer

PW = "walk-public-pw-1234"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("NAV_ROOMS", "1")


def _account(plan="artist", name="Walk Person"):
    email = "pub-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    if plan != "artist":
        store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid, email


def _words(body):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


# --- Billing: a real account reads its own state, or nothing -----------------

INVENTED = ("Compare Plans", "INV-2026-06", "INV-2026-05", "INV-2026-04",
            "Renews 2026-08-01", "Demo only")


def test_a_real_account_is_never_shown_the_billing_sample():
    """The showcase is a sample. It used to render for every account that
    had no Stripe behind it, so a fresh Artist read a plan it had not
    bought, a renewal date and three invoices marked Paid."""
    c, _uid, _e = _account()
    body = _words(c.get("/billing").get_data(as_text=True))
    for invented in INVENTED:
        assert invented not in body, invented


def test_the_billing_page_keeps_its_heading_without_stripe():
    """The sample carried the only <h1>. Hiding it left a real account on
    a service with no payments looking at a page with no title."""
    c, _uid, _e = _account()
    body = c.get("/billing").get_data(as_text=True)
    assert '<h1 class="sb-h1">Billing</h1>' in body


def test_the_demo_login_still_gets_the_sample():
    """The block is not deleted, it is put where it belongs."""
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    body = _words(demo.get("/billing").get_data(as_text=True))
    assert "Compare Plans" in body and "Demo only" in body


def test_a_deployed_service_offers_no_switch_it_cannot_honour(monkeypatch):
    """With no Stripe on a deployed service, /plan/switch refuses a paid
    tier. The page offered the button anyway and said nothing when it did
    nothing, so the account was left guessing."""
    c, uid, _e = _account()
    monkeypatch.setenv("RENDER", "true")
    # RENDER is set here to reach the deployed-service behaviour,
    # not to exercise the sign-up guard. This file posts straight
    # to /signup with no rendered form, so it carries no signed
    # stamp and the guard would refuse it. The guard is tested on
    # purpose in tests/test_signup_guard_wired.py.
    monkeypatch.setenv("SIGNUP_GUARD", "off")
    body = c.get("/billing").get_data(as_text=True)
    assert "Switch (demo)" not in body
    assert "Payments are not switched on here yet" in _words(body)
    c.post("/plan/switch", data={"plan": "pro"})
    assert (store.get_user(uid).get("plan") or "artist") == "artist"


def test_off_a_deployment_the_demo_switch_is_still_there():
    """A laptop and the test suite have no payments and no Render, and
    switching plans by hand is how they are used."""
    c, _uid, _e = _account()
    assert "Switch (demo)" in c.get("/billing").get_data(as_text=True)


# --- The public footer points at the pages written for it --------------------

def test_the_public_footer_contact_opens_contact():
    anon = appmod.app.test_client()
    for path in ("/login", "/signup", "/forgot", "/terms", "/privacy", "/plan", "/start"):
        body = anon.get(path).get_data(as_text=True)
        assert '<a href="/contact">Contact</a>' in body, path
        assert '<a href="/submit">Contact</a>' not in body, path


def test_the_landing_company_column_names_the_company_pages():
    import landing_config
    company = [col for col in landing_config.get_landing_config()["footer"]["columns"]
               if col["title"] == "Company"][0]
    by_label = {link["label"]: link["href"] for link in company["links"]}
    assert by_label["About"] == "/about"
    assert by_label["Contact"] == "/contact"


def test_both_company_pages_answer():
    anon = appmod.app.test_client()
    about = _words(anon.get("/about").get_data(as_text=True))
    assert "Built for the part" in about and "nobody sees." in about
    assert "Talk to a person." in _words(anon.get("/contact").get_data(as_text=True))


# --- The referral survives the invitation ------------------------------------

def test_a_referral_is_kept_through_an_invitation(monkeypatch):
    """With the door shut, /signup?ref=CODE returned the closed page before
    it stored the code, so the referrer was lost even though the person was
    invited minutes later and did sign up."""
    _c, referrer_id, _e = _account()
    code = store.ensure_ref_code(referrer_id)
    friend_email = "friend-%s@example.net" % uuid.uuid4().hex[:8]

    monkeypatch.setenv("SIGNUP_MODE", "invite")
    friend = appmod.app.test_client()
    shut = friend.get("/signup?ref=" + code)
    assert shut.status_code == 200 and "invitation" in _words(shut.get_data(as_text=True))
    with friend.session_transaction() as sess:
        assert sess.get("ref_code") == code

    token = store.add_signup_invite(friend_email, "artist", referrer_id)
    friend.post("/signup?invite=" + token,
                data={"name": "Friend", "email": friend_email, "password": PW})
    assert store.get_user_by_email(friend_email)["referred_by"] == referrer_id


# --- A new account lands somewhere that reads its own state ------------------

def test_a_new_account_lands_on_the_command_center():
    """The wizard saved none of its ticks and told every new account that
    its songs would be imported from a connected distributor. The
    start-here panel on the Command Center reads what the account has."""
    c = appmod.app.test_client()
    email = "new-%s@example.net" % uuid.uuid4().hex[:8]
    r = c.post("/signup", data={"name": "New", "email": email, "password": PW})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/command-center")


# --- The checklist never points at a locked door -----------------------------

def test_the_checklist_drops_a_step_this_plan_cannot_open(monkeypatch):
    """The Rack answers 402 for an Artist once the suite gates are on, and
    the first step of the checklist was "Open the Rack"."""
    monkeypatch.setenv("SUITE_GATES", "on")
    c, _uid, _e = _account()
    body = c.get("/command-center").get_data(as_text=True)
    assert "Put a track through the Rack" not in body
    assert "Name the artist" in body, "the reachable steps stay"
    assert ">/4</span>" in body, "the tally counts the doors on offer"


def test_every_step_offered_actually_opens(monkeypatch):
    monkeypatch.setenv("SUITE_GATES", "on")
    c, _uid, _e = _account()
    import firstrun
    body = c.get("/command-center").get_data(as_text=True)
    for _key, title, _why, href, _cta in firstrun.STEPS:
        if title in body:
            assert c.get(href).status_code != 402, href


def test_a_label_still_gets_the_whole_checklist(monkeypatch):
    monkeypatch.setenv("SUITE_GATES", "on")
    c, _uid, _e = _account(plan="label")
    body = c.get("/command-center").get_data(as_text=True)
    assert "Put a track through the Rack" in body
    assert ">/5</span>" in body


# --- Tour names the plan it is asking for ------------------------------------

def test_the_tour_refusal_names_the_plan_it_wants(monkeypatch):
    """An Artist pressing New tour read "This is a Artist feature" and
    "Your current plan is Artist"."""
    monkeypatch.setenv("SUITE_GATES", "on")
    c, _uid, _e = _account()
    r = c.post("/tours/new", data={"name": "Spring run", "home_tz": "UTC"})
    assert r.status_code == 402
    body = _words(r.get_data(as_text=True))
    assert "Tour opens with Pro" in body
    assert "This is a Artist feature" not in body


# --- A reset link is spent once ----------------------------------------------

def _capture_reset(monkeypatch, email):
    sent = []
    monkeypatch.setattr(emailer, "configured", lambda: True)
    monkeypatch.setattr(emailer, "send",
                        lambda to, subject, html, **kw: sent.append(html) or True)
    appmod.app.test_client().post("/forgot", data={"email": email})
    assert sent, "no reset mail"
    return re.search(r"/reset/([A-Za-z0-9_.\-]+)", sent[0]).group(1)


def test_a_used_reset_link_does_not_open_again(monkeypatch):
    """The token carried only the user id, so it stayed valid for the whole
    hour. Anyone reading the mailbox after the owner had reset could take
    the account back within it."""
    _c, uid, email = _account()
    token = _capture_reset(monkeypatch, email)

    first = appmod.app.test_client()
    assert first.post("/reset/" + token, data={"password": "first-new-pw"}).status_code == 302

    second = appmod.app.test_client()
    again = second.post("/reset/" + token, data={"password": "second-new-pw"})
    assert again.status_code == 200
    refusal = _words(again.get_data(as_text=True))
    assert "already been used" in refusal, "the page names the real reason"
    assert "Request a new link" in refusal, "and offers the way out"
    with second.session_transaction() as sess:
        assert sess.get("user_id") is None

    # The second password was never set, and the first one still signs in.
    taken = appmod.app.test_client()
    refused = taken.post("/login", data={"email": email, "password": "second-new-pw"})
    assert "Incorrect email or password" in refused.get_data(as_text=True)
    owner = appmod.app.test_client()
    assert owner.post("/login", data={"email": email, "password": "first-new-pw"}
                      ).status_code == 302


def test_a_fresh_reset_link_still_works(monkeypatch):
    _c, _uid, email = _account()
    token = _capture_reset(monkeypatch, email)
    c = appmod.app.test_client()
    assert c.post("/reset/" + token, data={"password": "brand-new-pw"}).status_code == 302
    after = appmod.app.test_client()
    assert after.post("/login", data={"email": email, "password": "brand-new-pw"}
                      ).status_code == 302


def test_a_link_sent_before_a_settings_password_change_stops_opening(monkeypatch):
    """Same stamp, the other way round: the mail is overtaken by the real
    password change and cannot undo it."""
    _c, uid, email = _account()
    token = _capture_reset(monkeypatch, email)
    from werkzeug.security import generate_password_hash
    store.set_user_password(uid, generate_password_hash("changed-in-settings"))
    c = appmod.app.test_client()
    assert c.post("/reset/" + token, data={"password": "taken-over"}).status_code == 200


# --- The doors know you are already inside -----------------------------------

def test_a_signed_in_account_is_let_into_the_app_not_handed_a_form():
    c, _uid, _e = _account()
    for path in ("/login", "/signup", "/forgot"):
        r = c.get(path)
        assert r.status_code == 302, path
        assert r.headers["Location"].endswith("/command-center"), path


def test_a_signed_in_fan_goes_to_the_fan_side():
    c, uid, _e = _account(plan="fan")
    assert c.get("/login").headers["Location"].endswith("/discover")


def test_a_login_link_that_named_a_destination_still_honours_it():
    c, _uid, _e = _account()
    assert c.get("/login?next=/statements").headers["Location"].endswith("/statements")


def test_a_stranger_still_gets_the_form():
    anon = appmod.app.test_client()
    for path in ("/login", "/signup", "/forgot"):
        r = anon.get(path)
        assert r.status_code == 200, path
        assert 'name="password"' in r.get_data(as_text=True) or path == "/forgot"

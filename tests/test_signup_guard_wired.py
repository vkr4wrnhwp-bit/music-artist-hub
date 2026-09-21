"""The guard is actually on the door.

signup_guard.py was written, tested and then imported by nothing, so the
sign-up form had no protection at all while a file full of passing tests
said otherwise. test_signup_guard.py proves the judgement is sound. This
file proves the door uses it.

The rules this file holds:

  * the form hands out a signed stamp and the hidden field, on every
    render, including while sign-up is shut
  * a submission that fills the hidden field creates no account
  * a submission with no stamp, or one filled in faster than a person
    can read the form, creates no account
  * the refusal never says which check caught it
  * an invitation is not judged: the owner made that link for one
    address, and a real artist on a shared connection must still get in
  * a person filling the form normally is let through
"""
import time

import pytest

import db as store
import signup_guard
from app import create_app


@pytest.fixture(autouse=True)
def guard_on(monkeypatch):
    # The guard is off on a laptop so three thousand tests need not each
    # carry a signed stamp. These tests are the ones that want it on.
    monkeypatch.setenv("SIGNUP_GUARD", "on")
    monkeypatch.setenv("SIGNUP_MODE", "open")
    signup_guard.reset_for_tests()


@pytest.fixture
def client():
    app_obj = create_app()
    return app_obj, app_obj.test_client()


def _secret(app_obj):
    return app_obj.config["SECRET_KEY"]


def _address():
    return "guard-%s@example.com" % int(time.time() * 1000000)


def _fields(app_obj, opened_ago=30.0, **extra):
    """What a person's browser sends back: the stamp it was given, the
    hidden field left empty, and the answers they typed."""
    form = {"name": "A Real Artist",
            "email": _address(),
            "password": "long-enough-password",
            "account_type": "artist",
            signup_guard.HONEYPOT: "",
            signup_guard.STAMP_FIELD: signup_guard.stamp(
                _secret(app_obj), now=time.time() - opened_ago)}
    form.update(extra)
    return form


def test_the_form_hands_out_a_stamp_and_a_hidden_field(client):
    app_obj, c = client
    page = c.get("/signup").get_data(as_text=True)
    assert 'name="%s"' % signup_guard.STAMP_FIELD in page
    assert 'name="%s"' % signup_guard.HONEYPOT in page
    # An empty stamp would make every submission look forged.
    assert 'name="%s" value=""' % signup_guard.STAMP_FIELD not in page


def test_the_shut_door_still_hands_out_a_stamp(client, monkeypatch):
    """So that reopening sign-up does not require a second change."""
    monkeypatch.setenv("SIGNUP_MODE", "invite")
    app_obj, c = client
    page = c.get("/signup").get_data(as_text=True)
    assert 'name="%s"' % signup_guard.STAMP_FIELD in page
    assert 'name="%s"' % signup_guard.HONEYPOT in page


def test_a_person_gets_an_account(client):
    app_obj, c = client
    form = _fields(app_obj)
    reply = c.post("/signup", data=form, follow_redirects=False)
    assert reply.status_code in (301, 302), reply.get_data(as_text=True)[:400]
    assert store.get_user_by_email(form["email"]) is not None


def test_filling_the_hidden_field_creates_nothing(client):
    app_obj, c = client
    form = _fields(app_obj, **{signup_guard.HONEYPOT: "https://spam.example"})
    reply = c.post("/signup", data=form)
    assert reply.status_code == 429
    assert store.get_user_by_email(form["email"]) is None


def test_a_missing_stamp_creates_nothing(client):
    app_obj, c = client
    form = _fields(app_obj)
    form.pop(signup_guard.STAMP_FIELD)
    reply = c.post("/signup", data=form)
    assert reply.status_code == 429
    assert store.get_user_by_email(form["email"]) is None


def test_a_form_filled_faster_than_reading_creates_nothing(client):
    app_obj, c = client
    form = _fields(app_obj, opened_ago=0.2)
    reply = c.post("/signup", data=form)
    assert reply.status_code == 429
    assert store.get_user_by_email(form["email"]) is None


def test_the_refusal_does_not_say_which_check_caught_it(client):
    """Naming the check tells a script how to pass it next time. The
    reasons the guard returns are for the log only, so none of its
    wording may reach the page."""
    app_obj, c = client
    body = c.post("/signup", data=_fields(
        app_obj, **{signup_guard.HONEYPOT: "x"})).get_data(as_text=True).lower()
    assert signup_guard.REFUSAL.lower() in body
    # The exact phrasings signup_guard.judge returns, not loose words: the
    # page legitimately contains "generated", which a search for "rate"
    # matched when this test was first written.
    #
    # The honeypot's field name is deliberately NOT on this list. It is in
    # the form on every render, including this one, because the person has
    # to be able to try again. Hiding the name was never the defence: a
    # browser does not draw the field, so a person does not fill it.
    for reason in ("filled the hidden field", "signed form stamp",
                   "submitted in", "throwaway domain", "second account from"):
        assert reason.lower() not in body, reason


def test_the_refused_person_can_try_again(client):
    """A real artist will occasionally trip a check and must not be
    stranded: the refusal re-serves the whole form, with a fresh stamp."""
    app_obj, c = client
    body = c.post("/signup", data=_fields(
        app_obj, **{signup_guard.HONEYPOT: "x"})).get_data(as_text=True)
    assert 'name="password"' in body
    assert 'name="%s"' % signup_guard.STAMP_FIELD in body
    assert 'name="%s" value=""' % signup_guard.STAMP_FIELD not in body


def test_an_invitation_is_not_judged(client):
    """The owner made that link for one address. A guest arriving on a
    shared office connection, seconds after the page loads, still gets in."""
    app_obj, c = client
    email = _address()
    host = store.create_user("host-%s" % email, "Host",
                             "pbkdf2:sha256:1$x$" + "0" * 64)
    token = store.add_signup_invite(email, "pro", host)
    reply = c.post("/signup?invite=%s" % token,
                   data={"name": "Invited Artist", "email": email,
                         "password": "long-enough-password",
                         "account_type": "artist",
                         "invite": token,
                         # No stamp, no hidden field: the invitation is the proof.
                         },
                   follow_redirects=False)
    assert reply.status_code in (301, 302), reply.get_data(as_text=True)[:400]
    assert store.get_user_by_email(email) is not None

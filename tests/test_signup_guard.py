"""The sign-up door tells a person from a script, and never the other way.

Owner, 2026-09-17: bot protection is one of two things that must exist
before sign-up reopens for advertising. Hundreds of Fan accounts had
already registered themselves while the form was open.

The tests that matter most are the ones about people: a real artist who
types slowly, shares an office connection, or leaves the tab open over
lunch must still get an account.
"""
import time

import pytest

import signup_guard as g

SECRET = "guard-test-secret"


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setenv("SIGNUP_GUARD", "on")
    g.reset_for_tests()


def _form(secret=SECRET, opened_ago=30.0, **extra):
    form = {"email": "artist@example.com",
            g.STAMP_FIELD: g.stamp(secret, now=time.time() - opened_ago)}
    form.update(extra)
    return form


def test_a_person_filling_the_form_is_let_through():
    assert g.judge(_form(), "203.0.113.9", SECRET) is None


def test_the_hidden_field_is_the_giveaway():
    assert g.judge(_form(**{g.HONEYPOT: "https://spam.example"}),
                   "203.0.113.10", SECRET) == "filled the hidden field"
    # An empty one is what a browser sends, and is not held against anyone.
    assert g.judge(_form(**{g.HONEYPOT: ""}), "203.0.113.11", SECRET) is None


def test_nobody_reads_a_form_and_picks_a_password_in_under_a_second():
    r = g.judge(_form(opened_ago=0.2), "203.0.113.12", SECRET)
    assert r and r.startswith("submitted in")


def test_a_form_that_was_never_handed_out_is_refused():
    assert g.judge({"email": "a@b.co"}, "203.0.113.13", SECRET) == "no signed form stamp"


def test_the_clock_cannot_be_back_dated_by_whoever_is_posting():
    """A script that mints its own stamp with its own secret gets nowhere."""
    forged = g.stamp("not-the-servers-secret", now=time.time() - 600)
    assert g.judge({"email": "a@b.co", g.STAMP_FIELD: forged},
                   "203.0.113.14", SECRET) == "no signed form stamp"


def test_throwaway_addresses_are_turned_away(monkeypatch):
    assert "throwaway" in g.judge(_form(email="x@mailinator.com"), "203.0.113.15", SECRET)
    monkeypatch.setenv("SIGNUP_BLOCKED_DOMAINS", "burner.test, Another.Test")
    assert "throwaway" in g.judge(_form(email="x@burner.test"), "203.0.113.16", SECRET)
    assert "throwaway" in g.judge(_form(email="x@another.test"), "203.0.113.17", SECRET)
    assert g.judge(_form(email="x@gmail.com"), "203.0.113.18", SECRET) is None


def test_a_burst_from_one_address_gets_one_account():
    ip = "198.51.100.4"
    assert g.judge(_form(), ip, SECRET) is None
    for _ in range(5):
        r = g.judge(_form(), ip, SECRET)
        assert r and "inside" in r
    # A different artist, on a different connection, is unaffected.
    assert g.judge(_form(), "198.51.100.5", SECRET) is None


def test_two_people_on_one_office_connection_are_only_a_minute_apart():
    """On one fixed clock, so the stamp and the judgement agree about when
    "now" is."""
    ip, t0 = "198.51.100.6", 1_700_000_000.0
    handed = {"email": "a@b.co", g.STAMP_FIELD: g.stamp(SECRET, now=t0 - 30)}
    assert g.judge(handed, ip, SECRET, now=t0) is None
    assert g.judge(handed, ip, SECRET, now=t0 + 30) is not None
    assert g.judge(handed, ip, SECRET, now=t0 + g.RATE_WINDOW + 1) is None


def test_a_tab_left_open_over_lunch_still_works():
    assert g.judge(_form(opened_ago=3 * 60 * 60), "203.0.113.20", SECRET) is None


def test_a_tab_left_open_for_days_is_asked_for_the_form_again_not_refused():
    """The stamp has stopped being evidence, so it is not treated as proof of
    anything. The person reloads and carries on; nothing accuses them."""
    stale = g.stamp(SECRET, now=time.time() - (g.MAX_SECONDS + 600))
    assert g.judge({"email": "a@b.co", g.STAMP_FIELD: stale},
                   "203.0.113.21", SECRET) == "no signed form stamp"


def test_it_is_off_on_a_laptop_and_on_when_deployed(monkeypatch):
    monkeypatch.delenv("SIGNUP_GUARD", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert not g.enabled()
    assert g.judge({"email": "a@b.co"}, "203.0.113.22", SECRET) is None, "nothing is checked when off"
    monkeypatch.setenv("RENDER", "true")
    assert g.enabled()
    monkeypatch.setenv("SIGNUP_GUARD", "off")
    assert not g.enabled()


def test_the_refusal_never_says_which_check_caught_them():
    """Naming the check would tell a script how to pass it. It also has to
    leave a real person somewhere to go."""
    for word in ("hidden", "stamp", "domain", "seconds", "rate", "bot", "script "):
        assert word not in g.REFUSAL.lower().replace("not a script", ""), word
    assert "write to us" in g.REFUSAL


def test_the_rate_table_cannot_grow_for_ever():
    """A public form with advertising behind it sees a lot of addresses."""
    for i in range(g.RATE_MAX_TRACKED + 500):
        g.judge(_form(), "10.%d.%d.%d" % (i // 65536 % 256, i // 256 % 256, i % 256),
                SECRET, now=1000.0 + i)
    assert len(g._seen) <= g.RATE_MAX_TRACKED + 1, len(g._seen)


def test_the_client_address_prefers_the_forwarded_one():
    assert g.client_ip({"X-Forwarded-For": "203.0.113.7, 10.0.0.1"}, "10.0.0.1") == "203.0.113.7"
    assert g.client_ip({}, "10.0.0.2") == "10.0.0.2"

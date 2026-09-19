"""Street Banker hands a signed-in artist to a suite (sb_suite_sso).

One account for every suite (owner, 2026-09-17: "work on the logins from
Street Banker"): /suites/go/<key> mints a short-lived signed token naming the
account and the suite, and redirects to the suite's /auth/street-banker.
Without the shared secret the link is a plain visit, as before.
"""
import time
from urllib.parse import parse_qs, urlparse

import pytest

import app as appmod
import sb_suite_sso as sso

SECRET = "test-shared-secret-street-banker-suites"


@pytest.fixture
def artist():
    client = appmod.app.test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    return client


def test_a_stranger_is_sent_to_sign_in_first():
    r = appmod.app.test_client().get("/suites/go/reach")
    assert r.status_code == 302 and r.headers["Location"].endswith("/login?next=/suites/go/reach")


def test_an_unknown_suite_is_a_404(artist):
    assert artist.get("/suites/go/nope").status_code == 404


def test_without_a_shared_secret_the_link_is_a_plain_visit(artist, monkeypatch):
    monkeypatch.delenv("SUITE_SSO_SECRET", raising=False)
    r = artist.get("/suites/go/the-room")
    assert r.status_code == 302
    assert r.headers["Location"] == "https://street-banker-v2-workflows.onrender.com/song-builder/"
    assert "token" not in r.headers["Location"]


def test_with_the_secret_the_suite_receives_a_token_it_can_verify(artist, monkeypatch):
    monkeypatch.setenv("SUITE_SSO_SECRET", SECRET)
    r = artist.get("/suites/go/reach")
    assert r.status_code == 302
    url = urlparse(r.headers["Location"])
    assert url.scheme == "https" and url.netloc == "street-banker-v2-workflows.onrender.com"
    assert url.path == "/auth/street-banker"
    q = parse_qs(url.query)
    assert q["next"] == ["/reach/"]
    who = sso.verify(q["token"][0], {"reach"})
    assert who["email"] == "demo@streetbanker.io" and who["suite"] == "reach"
    assert who["plan"] in ("artist", "pro", "label", "fan")
    assert "password" not in who and "password_hash" not in who


def test_the_suite_address_comes_from_the_environment(artist, monkeypatch):
    monkeypatch.setenv("SUITE_SSO_SECRET", SECRET)
    monkeypatch.setenv("SUITE_URL_TOUR", "https://tour.streetbankermusic.com/")
    url = urlparse(artist.get("/suites/go/tour").headers["Location"])
    assert url.netloc == "tour.streetbankermusic.com" and url.path == "/auth/street-banker"


def test_a_token_only_opens_the_suite_it_was_minted_for(monkeypatch):
    monkeypatch.setenv("SUITE_SSO_SECRET", SECRET)
    token = sso.issue({"id": "u1", "email": "a@b.co", "name": "A", "plan": "artist"}, "tour")
    with pytest.raises(sso.HandoffRejected) as e:
        sso.verify(token, {"reach", "the-room"})
    assert e.value.reason == "wrong suite"
    assert sso.verify(token, {"tour"})["uid"] == "u1"


def test_a_token_expires(monkeypatch):
    monkeypatch.setenv("SUITE_SSO_SECRET", SECRET)
    monkeypatch.setattr(sso, "MAX_AGE_SECONDS", 0)
    token = sso.issue({"id": "u1", "email": "a@b.co", "name": "A", "plan": "artist"}, "reach")
    time.sleep(1.1)
    with pytest.raises(sso.HandoffRejected) as e:
        sso.verify(token, {"reach"})
    assert e.value.reason == "expired"


def test_a_tampered_or_foreign_token_is_refused(monkeypatch):
    monkeypatch.setenv("SUITE_SSO_SECRET", SECRET)
    token = sso.issue({"id": "u1", "email": "a@b.co", "name": "A", "plan": "artist"}, "reach")
    with pytest.raises(sso.HandoffRejected):
        sso.verify(token[:-4] + "zzzz", {"reach"})
    monkeypatch.setenv("SUITE_SSO_SECRET", "a-different-secret")
    with pytest.raises(sso.HandoffRejected) as e:
        sso.verify(token, {"reach"})
    assert e.value.reason == "bad signature"


def test_next_never_leaves_the_suite():
    assert sso.safe_next("//evil.example", "/reach/") == "/reach/"
    assert sso.safe_next("https://evil.example", "/reach/") == "/reach/"
    assert sso.safe_next("/reach/campaigns/1", "/reach/") == "/reach/campaigns/1"

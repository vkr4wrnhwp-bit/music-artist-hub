# -*- coding: utf-8 -*-
"""A real fan account is never served an invented artist or an invented figure.

THE DEFECT THIS LOCKS OUT
-------------------------
/discover presented discover_config's twelve hand-written tracks as a
music feed to every visitor. A fan who signed up to find music was shown
"Nova Reign" with 5.2M plays and a Follow button beside the name, and
nothing on the page let them tell that act from a real one. The product's
standing rule is that it never shows a number it does not have; an
invented figure dressed as a real one is the worst version of breaking
it, because the reader has no way to check.

THE FIX, AND WHY THESE TESTS ARE SHAPED THIS WAY
------------------------------------------------
The repo already settled this pattern on the Audience screen: showcase
rows go to a showcase session (_session_is_demo) and a real account gets
its own data or an honest empty state. Discover follows it.

The tests below are deliberately blunt. They do not check for a flag or
a CSS class; they read the rendered page and assert that not one of the
invented names, titles or play figures appears anywhere in it. That is
the only assertion that keeps working if somebody reshuffles the
template, renames the flag, or adds a thirteenth invented track: the
list of forbidden strings is read out of discover_config itself, so a
new fake act is covered the moment it is added.

THE TRAP
--------
Signing in as the demo account while testing the empty state hides the
whole defect, because the demo is exactly the session that is allowed to
see the feed. Every test here that means "a real fan" signs up a fresh
account with a random address, and _assert_no_invented_data is given the
account it is talking about so a mix-up fails loudly.
"""
import re
import uuid

import pytest

import discover_config
from app import create_app


@pytest.fixture
def app_obj():
    return create_app()


def _real_fan(app_obj):
    """A fan account of somebody's own. Never a seeded demo address."""
    client = app_obj.test_client()
    email = "fan-%s@example.net" % uuid.uuid4().hex[:10]
    r = client.post("/signup", data={"name": "A Fan", "email": email,
                                     "password": "fanpass1",
                                     "account_type": "fan"})
    assert r.headers["Location"] == "/discover", \
        "a fan sign-up is supposed to land on Discover; this test is testing nothing"
    return client


def _demo_fan(app_obj):
    client = app_obj.test_client()
    client.post("/login", data={"email": "demo-fan@streetbanker.io",
                                "password": "sweep"})
    return client


def _invented_strings():
    """Every name, title and rendered play figure in the sample feed.

    Read from the module, not typed out here, so a track added to
    discover_config is covered without anybody remembering to come back.
    """
    out = set()
    for t in discover_config._TRACKS:
        out.add(t["title"])
        out.add(t["artist"])
        out.add(discover_config._fmt_plays(t["plays"]))
    return out


def _assert_no_invented_data(body, where):
    found = sorted(s for s in _invented_strings() if s in body)
    assert not found, (
        "%s carries invented data from discover_config: %s" % (where, found))


# --- the page ------------------------------------------------------------

def test_a_real_fan_is_never_shown_an_invented_artist_or_figure(app_obj):
    """The state that matters: signed up this morning, nothing searched."""
    fan = _real_fan(app_obj)
    r = fan.get("/discover")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    _assert_no_invented_data(body, "/discover for a real fan")
    # Not just absent: replaced by something that invites an action and
    # says what will fill the page.
    assert "Start with a search" in body
    assert "is not built yet" in body
    assert "acts that do not exist" in body
    # And the page opens with the shared band, not a landing hero.
    assert "sb-plate" in body


def test_a_real_fans_filters_cannot_conjure_the_feed_back(app_obj):
    """Every filter the sample feed offers, tried by hand on a real
    account. A guard that only covers the unfiltered view is not a guard."""
    fan = _real_fan(app_obj)
    paths = ["/discover?genre=%s" % g for g in discover_config.GENRES]
    paths += ["/discover?mood=%s" % m["id"] for m in discover_config.MOODS]
    paths += ["/discover?genre=Synthwave&mood=late-night", "/discover?q="]
    for path in paths:
        _assert_no_invented_data(fan.get(path).get_data(as_text=True), path)


def test_a_real_fan_searching_gets_real_records_and_no_padding(app_obj, monkeypatch):
    """The one real thing on the page still works, and the sample feed is
    not quietly stapled underneath the results."""
    import music_apis
    monkeypatch.setattr(music_apis, "_fetch_json", lambda url: {"results": [{
        "trackName": "A Real Song", "artistName": "A Real Artist",
        "collectionName": "A Real Album",
        "artworkUrl100": "https://example.invalid/100x100bb.jpg",
        "previewUrl": "https://example.invalid/p.m4a",
        "trackViewUrl": "https://example.invalid/t"}]})
    fan = _real_fan(app_obj)
    body = fan.get("/discover?q=a+real+song").get_data(as_text=True)
    assert "A Real Song" in body and "A Real Artist" in body
    assert "preview-play" in body, "the 30s preview is the real offer"
    _assert_no_invented_data(body, "/discover?q=... for a real fan")


def test_an_artist_account_is_not_shown_the_feed_either(app_obj):
    """The rule is about real accounts, not about the fan plan. An artist
    who opens Discover is just as much a reader of invented numbers."""
    client = app_obj.test_client()
    client.post("/signup", data={"name": "An Artist",
                                 "email": "artist-%s@example.net" % uuid.uuid4().hex[:10],
                                 "password": "artistpw1"})
    _assert_no_invented_data(client.get("/discover").get_data(as_text=True),
                             "/discover for a real artist account")


def test_the_showcase_login_keeps_the_feed_and_is_told_it_is_a_sample(app_obj):
    """The owner's sample content is not deleted, it is labelled. If this
    fails, the fix went too far and took the demo walkthrough with it."""
    body = _demo_fan(app_obj).get("/discover").get_data(as_text=True)
    assert "Nova Reign" in body and "5.2M" in body, "the showcase feed is gone"
    # Labelled in words on the page, above the grid it describes, not in
    # a comment and not in colour alone.
    assert "Sample feed" in body
    assert "is made up" in body
    assert "A real account does not see this section" in body
    # The label is above the first invented name, not a footnote under it.
    assert body.index("Sample feed") < body.index("Nova Reign")


# --- the data module -----------------------------------------------------

def test_the_builder_defaults_to_telling_the_truth():
    """A caller that says nothing about the session gets nothing invented.

    The fail-safe direction, the same way the demo flags elsewhere in this
    repo default to False: the cost of forgetting the argument has to be a
    blank section, never a page of fabricated acts.
    """
    d = discover_config.get_discover_data({"genre": "Synthwave"})
    assert d["showcase"] is False
    for key in ("tracks", "spotlights", "new_releases", "genres", "moods"):
        assert d[key] == [], "%s is populated without showcase=True" % key
    assert d["result_count"] == 0
    assert d["summary"]["tracks"] == 0
    # And the shape is the same either way, so a template cannot crash
    # into the honest branch.
    assert set(d) == set(discover_config.get_discover_data({}, showcase=True))


def test_the_sample_rows_are_still_there_for_the_showcase():
    d = discover_config.get_discover_data({}, showcase=True)
    assert d["showcase"] is True and len(d["tracks"]) == len(discover_config._TRACKS)


# --- the endpoints -------------------------------------------------------

def test_a_real_account_cannot_like_or_follow_an_invented_act(app_obj):
    """A follow is a relationship. Handing one back for an artist who does
    not exist is the same lie as printing the feed, so the endpoints answer
    404: for this session there is no such track and no such artist."""
    fan = _real_fan(app_obj)
    for path in ("/discover/like/tr-1", "/discover/follow/nova-reign",
                 "/discover/follow/sable-wynn", "/discover/like/tr-9"):
        r = fan.post(path)
        assert r.status_code == 404, path
        assert r.get_json()["ok"] is False, path
    # Nothing was written to the session on the way out.
    with fan.session_transaction() as s:
        assert not s.get("discover_likes") and not s.get("discover_follows")


def test_follow_refuses_an_id_the_feed_does_not_carry(app_obj):
    """It used to accept any string: POST /discover/follow/beyonce
    answered {"following": true}. like_track always checked; this did not."""
    demo = _demo_fan(app_obj)
    assert demo.post("/discover/follow/beyonce").status_code == 404
    assert demo.post("/discover/follow/../../etc").status_code in (404, 308, 405)
    assert demo.post("/discover/follow/nova-reign").get_json()["following"] is True
    assert discover_config.follow_artist("nobody-at-all", set()) is None


def test_an_anonymous_visitor_gets_the_login_door_not_the_feed(app_obj):
    anon = app_obj.test_client()
    assert anon.get("/discover").status_code == 302
    for path in ("/discover/like/tr-1", "/discover/follow/nova-reign"):
        assert anon.post(path).status_code == 302, path


# --- the seam ------------------------------------------------------------

def test_the_only_door_to_the_sample_feed_is_the_demo_check(app_obj):
    """One gate, named once.

    If a second way into the feed ever appears, it will be a view that
    passes showcase= from something other than _session_is_demo, or a
    write that skips the refusal. Read each registered view's own source
    rather than a slice of create_app, so another route landing next door
    does not break this.
    """
    import inspect

    views = app_obj.view_functions
    page = inspect.getsource(views["discover"])
    assert "showcase = _session_is_demo()" in page
    assert "showcase=showcase" in page
    for name in ("discover_like_route", "discover_follow_route"):
        assert "_discover_sample_only()" in inspect.getsource(views[name]), name

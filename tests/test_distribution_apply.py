"""Street Banker Distribution, powered by Symphonic.

Owner, 2026-09-22: "can we lift some information out of it that they need,
make our own, and then once they submit it to ours, it's submitted to the
symphonic sheet", and "brand it as street banker distribution powered by
symphonic".

So our form posts into Symphonic's own HubSpot sheet. The things that must
stay true however the page is edited: Symphonic decides and the page says
so, the artist ticks a box before their details leave, and an application
is kept here whether or not their end took it.
"""
import json
import uuid

import pytest
from werkzeug.security import generate_password_hash

import app as appmod
import db as store
import symphonic_signup as sym


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    a = appmod.create_app()
    a.config.update(TESTING=True)
    with a.app_context():
        uid = store.create_user("d-%s@example.net" % uuid.uuid4().hex[:8],
                                "Lucas Joyner", generate_password_hash("a-long-password"))
        store.set_user_plan(uid, "label")
    c = a.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = uid
    return a, c, uid


GOOD = {
    "firstname": "Lucas", "lastname": "Joyner", "email": "lucas@example.net",
    "select_your_home_country": "United States",
    "which_of_these_best_describes_you": "Artist",
    "key_info_about_your_band": "Two records out, about to put out a third.",
    "transfer_existing_catalog_to_symphonic": "Yes",
    "primary_genre": "Rock",
    "artist_label_social_media_links": "Instagram",
    "how_did_you_hear_about_symphonic_": "Referral" if "Referral" in sym.HEARD else sym.HEARD[0],
    "planned_marketing_services": "Marketing Services",
    "consent": "1",
}


def _ok(*_a, **_k):
    class R:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return R()


# --- what the page must keep saying -----------------------------------------

def test_the_page_says_whose_decision_it_is(world):
    _a, c, _uid = world
    page = c.get("/distribution/apply").get_data(as_text=True)
    assert "Symphonic" in page
    assert "they decide" in page.lower() or "symphonic decides" in page.lower()
    # And it promises nothing it cannot keep.
    assert "Nothing here is a quote, a rate or a date" in page


def test_the_form_is_branded_as_ours_powered_by_theirs(world):
    _a, c, _uid = world
    page = c.get("/distribution/apply").get_data(as_text=True)
    assert "Street Banker Distribution" in page
    assert "Powered by Symphonic" in page


def test_the_account_fills_in_what_it_already_knows(world):
    _a, c, _uid = world
    page = c.get("/distribution/apply").get_data(as_text=True)
    assert 'value="Lucas"' in page and 'value="Joyner"' in page


def test_nothing_leaves_without_the_tick(world, monkeypatch):
    """The details typed here go to a third party. Same rule as RoEx."""
    a, c, uid = world
    called = []
    monkeypatch.setattr(sym, "submit", lambda *x, **k: called.append(1) or (True, ""))
    body = dict(GOOD)
    body.pop("consent")
    page = c.post("/distribution/apply", data=body).get_data(as_text=True)
    assert called == [], "not sent"
    assert "Tick this so we can send it." in page
    with a.app_context():
        assert store.distribution_applications(uid) == [], "and not kept as an application"


# --- what actually goes to HubSpot ------------------------------------------

def test_a_good_application_reaches_symphonic_and_is_kept(world, monkeypatch):
    a, c, uid = world
    seen = {}

    def fake(req, timeout=None):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data.decode())
        return _ok()

    monkeypatch.setattr(sym.urllib.request, "urlopen", fake)
    page = c.post("/distribution/apply", data=GOOD).get_data(as_text=True)

    assert sym.PORTAL_ID in seen["url"] and sym.FORM_GUID in seen["url"]
    names = {f["name"]: f["value"] for f in seen["body"]["fields"]}
    assert names["email"] == "lucas@example.net"
    assert names["primary_genre"] == "Rock"
    assert names["which_of_these_best_describes_you"] == "Artist"
    assert "Your application is with Symphonic." in page

    with a.app_context():
        kept = store.distribution_applications(uid)
    assert len(kept) == 1 and kept[0]["sent"] == 1


def test_a_value_they_would_refuse_is_refused_here_first(world, monkeypatch):
    """Their refusal is a number; ours is a sentence."""
    a, c, uid = world
    called = []
    monkeypatch.setattr(sym, "submit", lambda *x, **k: called.append(1) or (True, ""))
    page = c.post("/distribution/apply",
                  data=dict(GOOD, primary_genre="Skiffle")).get_data(as_text=True)
    assert called == []
    assert "Choose one of the listed options." in page


def test_a_refusal_is_told_to_the_artist_and_kept_for_the_owner(world, monkeypatch):
    """A form that loses an application silently is worse than no form."""
    a, c, uid = world
    monkeypatch.setattr(sym, "submit",
                        lambda *x, **k: (False, "Property \"primary_genre\" does not exist"))
    page = c.post("/distribution/apply", data=GOOD).get_data(as_text=True)
    assert "did not reach Symphonic" in page
    assert "primary_genre" in page, "their own words, so it can be acted on"
    with a.app_context():
        kept = store.distribution_applications(uid)
    assert len(kept) == 1 and kept[0]["sent"] == 0
    assert "does not exist" in kept[0]["error"]


def test_several_picks_go_as_one_semicolon_value(world, monkeypatch):
    seen = {}
    monkeypatch.setattr(sym.urllib.request, "urlopen",
                        lambda req, timeout=None: (seen.update(
                            body=json.loads(req.data.decode())), _ok())[1])
    a, c, _uid = world
    from werkzeug.datastructures import MultiDict
    body = MultiDict([(k, v) for k, v in GOOD.items()
                      if k != "artist_label_social_media_links"]
                     + [("artist_label_social_media_links", "Instagram"),
                        ("artist_label_social_media_links", "TikTok")])
    c.post("/distribution/apply", data=body)
    names = {f["name"]: f["value"] for f in seen["body"]["fields"]}
    assert names["artist_label_social_media_links"] == "Instagram;TikTok"


# --- the field list is theirs, not ours -------------------------------------

def test_the_options_are_the_ones_their_form_accepts():
    """A value they do not recognise is a submission they reject, so these
    are read from their own form definition rather than typed by hand."""
    assert len(sym.COUNTRIES) == 205 and sym.COUNTRIES[0] == "United States"
    assert len(sym.GENRES) == 49
    assert "Artist" in sym.WHO and "Label" in sym.WHO
    assert all(name in sym.WORDS for name, _req in sym.FIELDS), "every field has words"


def test_the_signed_out_are_sent_to_sign_in(world):
    a, _c, _uid = world
    anon = a.test_client()
    r = anon.get("/distribution/apply")
    assert r.status_code in (302, 303)

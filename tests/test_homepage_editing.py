"""The homepage, editable by its owner without a deploy.

The page was already config-driven — landing_config returns a dict and
the template renders it. The only reason changing a headline needed an
engineer is that the dict lived in Python source.

So the config stays as the default and a saved override sits on top.
That shape is the point: an empty override is the shipped page exactly,
"reset" is deleting a key rather than restoring a backup, and the
defaults stay in git so there is always a known-good state.

This is also the one surface where something wrong reaches the public
without a green run standing in the way. What can be checked is checked —
a link that goes nowhere, a sentence claiming a deployment state. Whether
the words are TRUE cannot be, and nothing here pretends otherwise.
"""
import os
import re
import uuid

import pytest

import homepage_edit as he
from landing_config import get_landing_config

PASSWORD = "homepage-edit-123"


@pytest.fixture(scope="module")
def application():
    os.environ["OWNER_EMAILS"] = "homepage-owner@example.net"
    import app as appmod
    return appmod.app


@pytest.fixture
def owner(application):
    c = application.test_client()
    c.post("/signup", data={"name": "Boss", "email": "homepage-owner@example.net",
                            "password": PASSWORD})
    c.post("/login", data={"email": "homepage-owner@example.net",
                           "password": PASSWORD})
    yield c
    with application.app_context():
        he.clear_override()


def _draft(owner):
    """A complete, valid draft built from the form the editor renders."""
    page = owner.get("/homepage").get_data(as_text=True)
    keys = re.findall(r'name="([a-z0-9.]+)"', page)
    return {k: ("/login" if k.endswith("href") else "Copy") for k in keys}


# --- who may reach it --------------------------------------------------------

def test_only_an_owner_can_open_it(application, owner):
    assert owner.get("/homepage").status_code == 200
    stranger = application.test_client()
    email = "not-owner-%s@example.net" % uuid.uuid4().hex[:8]
    stranger.post("/signup", data={"name": "N", "email": email, "password": PASSWORD})
    stranger.post("/login", data={"email": email, "password": PASSWORD})
    assert stranger.get("/homepage").status_code == 404
    assert stranger.post("/homepage", data={}).status_code == 404
    assert stranger.post("/homepage/reset").status_code == 404


# --- the override shape ------------------------------------------------------

def test_no_override_renders_exactly_what_ships(application, owner):
    """The feature existing must not change the page."""
    with application.app_context():
        assert not he.is_edited()
        assert he.apply_override(get_landing_config()) == get_landing_config()


def test_saving_reaches_the_public_homepage(application, owner):
    draft = _draft(owner)
    draft["hero.headline.0"] = "OWN THE MASTER."
    assert owner.post("/homepage", data=draft).status_code == 302
    home = application.test_client().get("/").get_data(as_text=True)
    assert "OWN THE MASTER." in home


def test_an_override_only_moves_what_it_names(application, owner):
    """A whole-dict replace would freeze every field it happened to
    include, so a later default improvement would never reach an edited
    page."""
    base = {"hero": {"eyebrow": "A", "support": "S"}, "brand": "B"}
    merged = he._deep_merge(base, {"hero": {"eyebrow": "NEW"}})
    assert merged == {"hero": {"eyebrow": "NEW", "support": "S"}, "brand": "B"}


def test_reset_puts_the_shipped_copy_back(application, owner):
    draft = _draft(owner)
    draft["hero.headline.0"] = "TEMPORARY."
    owner.post("/homepage", data=draft)
    owner.post("/homepage/reset")
    home = application.test_client().get("/").get_data(as_text=True)
    assert "TEMPORARY." not in home
    with application.app_context():
        assert not he.is_edited()


def test_a_corrupt_override_cannot_take_the_homepage_down(application, owner):
    import db as store
    with application.app_context():
        store.set_kv(he.KV_KEY, "{not json at all")
        assert he.read_override() == {}
    assert application.test_client().get("/").status_code == 200


# --- what it refuses ---------------------------------------------------------

def test_a_link_that_goes_nowhere_is_refused(application, owner):
    draft = _draft(owner)
    draft["hero.headline.0"] = "SHOULD NOT PUBLISH."
    draft["nav.cta.href"] = "/not-a-real-page"
    r = owner.post("/homepage", data=draft)
    assert r.status_code == 200
    assert "not a page on this site" in r.get_data(as_text=True)
    home = application.test_client().get("/").get_data(as_text=True)
    assert "SHOULD NOT PUBLISH." not in home, (
        "a refusal must publish nothing, not half the draft")


def test_a_sentence_claiming_a_deployment_state_is_refused(application, owner):
    draft = _draft(owner)
    draft["hero.support"] = "Royalty recovery coming soon."
    r = owner.post("/homepage", data=draft)
    assert "cannot know whether" in r.get_data(as_text=True)


def test_an_empty_field_is_refused_rather_than_rendered_blank(application, owner):
    draft = _draft(owner)
    draft["hero.headline.0"] = ""
    r = owner.post("/homepage", data=draft)
    assert "would render empty" in r.get_data(as_text=True)


def test_anchors_and_off_site_links_are_allowed(application):
    resolves = he.route_resolver(application)
    for good in ("#platform", "/#royalty-sweep", "https://instagram.com/x",
                 "mailto:hi@example.com", "/login"):
        assert resolves(good), good
    for bad in ("/nope-not-a-route", ""):
        assert not resolves(bad), bad


# --- one rule, two callers ---------------------------------------------------

def test_the_navigation_test_uses_this_resolver_rather_than_its_own():
    """Two copies of "is this a real route" drift, and the drift is
    silent: the editor accepts a link the suite rejects, or refuses one it
    allows, and nobody finds out until a visitor does."""
    import io
    import os as _os
    here = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    with io.open(_os.path.join(here, "tests/test_navigation_honesty.py"),
                 encoding="utf-8") as f:
        src = f.read()
    assert "homepage_edit.route_resolver" in src
    assert "def resolves(path):" not in src, "a second copy has grown back"


def test_the_page_says_what_it_cannot_check(owner):
    """The honest cost, stated where somebody is about to publish."""
    page = owner.get("/homepage").get_data(as_text=True)
    assert "Nothing checks whether what you write is true" in page

"""Three places the owner's or the demo's things landed in a real account.

All three were found by the 2026-09-18 launch check, and each one showed a
real artist something that was not theirs:

  press kit    every artist's public EPK embedded the server's Shopify store,
               which is the owner's, under the heading Merch
  walkthrough  "New here? Take the walkthrough" sat on every Command Center,
               and its first step uploads a sample statement, which in a real
               account reads as $1,504.68 of income and a $36,112 valuation
  mock tour    deleting the Mock Up Tour set its 36 invented shows loose, and
               the next visit to Tour adopted them into the artist's real run
"""
import uuid

import pytest

import app as appmod
import db as store
import tour_mockup
import tour_store as ts
from app import create_app

PW = "launch-leaks-pass-1"


def _real_artist(app_obj, plan="artist"):
    email = "leak-%s@example.net" % uuid.uuid4().hex[:10]
    c = app_obj.test_client()
    c.post("/signup", data={"name": "Vera Sound", "email": email, "password": PW})
    c.post("/login", data={"email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    return c, uid


def _store_on(monkeypatch):
    monkeypatch.setenv("SHOPIFY_DOMAIN", "owners-store.myshopify.com")
    monkeypatch.setenv("SHOPIFY_STOREFRONT_TOKEN", "sf-public-token")
    monkeypatch.setenv("SHOPIFY_COLLECTION_ID", "298812866663")


# --- press kit ---------------------------------------------------------------

def test_a_real_artists_press_kit_never_shows_the_owners_store(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    _store_on(monkeypatch)
    app_obj = create_app()
    c, uid = _real_artist(app_obj)
    c.post("/epk/save", json={"tagline": "Nocturne pop", "store_url": "https://vera.example/shop"})
    c.get("/epk")                                   # mints the public slug
    slug = store.get_epk(uid)["slug"]
    body = app_obj.test_client().get("/epk/" + slug).get_data(as_text=True)
    assert "owners-store.myshopify.com" not in body and 'id="shopify-collection"' not in body
    assert "https://vera.example/shop" in body, "their own store link still shows"

    # The private pitch link is the same page and follows the same rule.
    token = uuid.uuid4().hex[:20]
    store.upsert_epk_share(uid, token, "", "", [])
    pitch = app_obj.test_client().get("/pitch/" + token).get_data(as_text=True)
    assert "owners-store.myshopify.com" not in pitch and 'id="shopify-collection"' not in pitch


def test_the_demo_showcase_keeps_the_store_embed(monkeypatch):
    _store_on(monkeypatch)
    app_obj = create_app()
    demo = app_obj.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    demo.post("/epk/save", json={"store_url": "https://www.example.com"})
    demo.get("/epk")
    uid = store.get_user_by_email("demo@streetbanker.io")["id"]
    body = app_obj.test_client().get("/epk/" + store.get_epk(uid)["slug"]).get_data(as_text=True)
    assert 'id="shopify-collection"' in body and '"owners-store.myshopify.com"' in body


# --- walkthrough -------------------------------------------------------------

def test_a_real_account_is_not_offered_the_demo_walkthrough(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    app_obj = create_app()
    c, _uid = _real_artist(app_obj)
    cc = c.get("/command-center").get_data(as_text=True)
    assert "Take the walkthrough" not in cc
    r = c.get("/walkthrough")
    assert r.status_code == 302 and r.headers["Location"].endswith("/command-center")


def test_the_demo_still_has_its_walkthrough():
    app_obj = create_app()
    demo = app_obj.test_client()
    demo.post("/login", data={"email": "demo-artist@streetbanker.io", "password": "sweep"})
    assert "Take the walkthrough" in demo.get("/command-center").get_data(as_text=True)
    assert demo.get("/walkthrough").status_code == 200


# --- mock tour ---------------------------------------------------------------

@pytest.fixture
def mock_on(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("MOCK_UP_TOUR", "on")
    monkeypatch.delenv("SUITE_GATES", raising=False)
    monkeypatch.delenv("RENDER", raising=False)


def test_deleting_the_mock_up_tour_takes_its_invented_shows_with_it(mock_on):
    c, uid = _real_artist(appmod.app, "pro")
    c.get("/tours")                                          # builds the Mock Up Tour
    mock = ts.list_tours(uid)[0]
    assert mock["name"] == tour_mockup.NAME and len(ts.list_shows(mock["id"])) > 30

    # The artist adds one real show of their own to it, and starts a real run.
    mine = store.add_tour_show(uid, "2027-04-20", "Their Own Room", "Chicago, IL", "")
    ts.attach_show(mock["id"], mine, "")
    real = ts.create_tour(uid, {"name": "My own run", "status": "planning"})

    ts.delete_tour(mock["id"])
    c.get("/tours")                                          # the visit that used to adopt them
    kept = ts.list_shows(real)
    venues = {s.get("venue") for s in kept}
    assert "The Paper Mill" not in venues and "Cicada Hall" not in venues, "invented rooms leaked"
    assert "Their Own Room" in venues, "the artist's own show is never lost"


def test_deleting_a_real_tour_still_sets_its_shows_loose(mock_on):
    """The old rule, for every tour that is not the Mock Up Tour: a real show
    is never deleted with its tour."""
    c, uid = _real_artist(appmod.app, "pro")
    tid = ts.create_tour(uid, {"name": "Spring run", "status": "planning"})
    sid = store.add_tour_show(uid, "2027-04-06", "The Paper Mill", "St. Paul, MN", "")
    ts.attach_show(tid, sid, "")
    ts.delete_tour(tid)
    assert any(s["id"] == sid for s in ts.orphan_shows(uid)), "a real show with a mock venue name survives"

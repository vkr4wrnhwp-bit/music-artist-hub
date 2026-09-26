"""The Mock Up Tour is a sample, and a sample never reaches a public page.

Make-it-real audit, 2026-09-23 (not_real_today[1], finish_next[0]): every
Pro account that opened Tour on a deployed service was given the Mock Up
Tour, whose invented shows include about thirty marked CONFIRMED in April
and May 2027. The public press kit's tour dates, the public Artist Hub,
the Team-Up Board's "confirmed dates ahead" chip and the /connections
count read every confirmed show with no filter, so invented dates could
stand on a real artist's public page. Only the Stage room and the Action
Center filtered it.

Now: every reader outside Tour goes through tour_mockup.real_shows (or
tour_dates, which skips the sample itself); the sample is labelled on
every page of it; nothing can be shared, sold or advanced from it, and a
token minted on it before this rule opens nothing. Real shows keep
flowing, including a loose show that used to be adopted onto the sample.
"""
import uuid

import pytest

import app as appmod
import board_store as bs
import db as store
import fan_audience
import tour_dates
import tour_mockup
import tour_store as ts

PW = "mock-public-pass-1"
# Confirmed on the sheet, all in 2027, so all "upcoming" today.
INVENTED = ("Ninth Ward Social", "The Gilded Ox", "Longwave", "Static Hall",
            "The Velvet Anchor", "Halcyon Social", "The Drift")


@pytest.fixture
def mock_on(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("MOCK_UP_TOUR", "on")
    monkeypatch.delenv("SUITE_GATES", raising=False)
    monkeypatch.delenv("RENDER", raising=False)


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _pro(flask_app):
    email = "mockpub-%s@example.net" % uuid.uuid4().hex[:8]
    c = flask_app.test_client()
    c.post("/signup", data={"name": "Mock Public", "email": email, "password": PW})
    c.post("/login", data={"email": email, "password": PW})
    user = store.get_user_by_email(email)
    store.set_user_plan(user["id"], "pro")
    return c, store.get_user(user["id"])


def _with_mock(flask_app):
    """A fresh Pro account that has opened Tour (so holds the Mock Up Tour)
    and its press kit (so has a public slug)."""
    c, user = _pro(flask_app)
    assert c.get("/tours").status_code == 200
    tours = ts.list_tours(user["id"])
    assert len(tours) == 1 and tour_mockup.is_mock(tours[0]["id"])
    confirmed = [s for s in ts.list_shows(tours[0]["id"]) if s["status"] == "confirmed"]
    assert len(confirmed) > 20, "the sample does carry confirmed dates"
    c.get("/epk")
    slug = store.get_epk(user["id"])["slug"]
    return c, user, tours[0]["id"], slug


def _real_confirmed_show(c, venue, date_="2030-06-12"):
    r = c.post("/tours/new", data={"name": "My Real Run", "artist_name": "Mock Public",
                                   "start_date": "2030-06-10", "end_date": "2030-06-20",
                                   "home_tz": "America/New_York", "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = c.post("/tours/%s/days/add" % tid, data={"date": date_, "kind": "show", "venue": venue,
                                                 "city": "Knoxville, TN", "tz": "America/New_York"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    assert c.post("/tours/%s/shows/%s/ext" % (tid, sid), data={"status": "confirmed"}).status_code == 302
    return tid, sid


# --- the public readers -------------------------------------------------------

def test_a_fresh_pro_accounts_public_press_kit_shows_no_invented_dates(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    assert tour_dates.upcoming(user["id"]) == [], "the feed the kit and /connections read"
    assert tour_dates.epk_rows(user["id"]) == []
    kit = flask_app.test_client().get("/epk/" + slug)
    assert kit.status_code == 200
    body = kit.get_data(as_text=True)
    for venue in INVENTED:
        assert venue not in body, venue


def test_the_public_artist_hub_shows_no_invented_dates(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    hub = flask_app.test_client().get("/@" + slug).get_data(as_text=True)
    for venue in INVENTED:
        assert venue not in hub, venue


def test_the_team_up_board_badge_counts_no_invented_dates(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    chips = bs.verified_chips(user["id"])["chips"]
    assert not [ch for ch in chips if ch["key"] == "upcoming"], chips


def test_the_fans_screen_takes_no_show_city_from_the_sample(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    assert fan_audience.for_account(user["id"])["tour"]["shows"] == 0


def test_real_shows_keep_flowing_beside_the_sample(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    _real_confirmed_show(c, "Real Room Knoxville")
    assert [r["venue"] for r in tour_dates.upcoming(user["id"])] == ["Real Room Knoxville"]
    anon = flask_app.test_client()
    kit = anon.get("/epk/" + slug).get_data(as_text=True)
    hub = anon.get("/@" + slug).get_data(as_text=True)
    assert "Real Room Knoxville" in kit and "Real Room Knoxville" in hub
    assert "Ninth Ward Social" not in kit and "Ninth Ward Social" not in hub
    chips = bs.verified_chips(user["id"])["chips"]
    assert [ch["label"] for ch in chips if ch["key"] == "upcoming"] == ["1 confirmed date ahead"]


def test_a_loose_show_is_never_adopted_onto_the_sample(mock_on, flask_app):
    """An account whose only tour is the sample adds a show through the old
    /tour form. It used to be adopted onto the Mock Up Tour, where the
    filter would hide it from the kit; it gets a tour of its own."""
    c, user, mock_id, slug = _with_mock(flask_app)
    c.post("/tour/add", data={"date": "2030-07-04", "venue": "Loose Real Room", "city": "Akron, OH"})
    show = [s for s in store.list_tour_shows(user["id"]) if s["venue"] == "Loose Real Room"][0]
    c.post("/tour/%s/status" % show["id"], data={"status": "confirmed"})
    c.get("/tours")
    show = store.get_tour_show(user["id"], show["id"])
    assert show["tour_id"] and show["tour_id"] != mock_id
    assert "Loose Real Room" in flask_app.test_client().get("/epk/" + slug).get_data(as_text=True)


# --- labelled as sample -------------------------------------------------------

def test_the_sample_is_labelled_on_the_tour_home_its_pages_and_its_prints(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    home = c.get("/tours").get_data(as_text=True)
    assert "Sample</span>" in home
    page = c.get("/tours/%s" % mock_id).get_data(as_text=True)
    assert 'id="sample-tour-note"' in page and "This is a sample tour." in page
    assert "None of it appears on your press kit" in page
    sid = ts.list_shows(mock_id)[0]["id"]
    assert "This is a sample tour." in c.get("/tours/%s/shows/%s" % (mock_id, sid)).get_data(as_text=True)
    printed = c.get("/tours/%s/itinerary" % mock_id).get_data(as_text=True)
    assert "Sample tour." in printed
    real_tid, _sid = _real_confirmed_show(c, "Real Room Label Check")
    real = c.get("/tours/%s" % real_tid).get_data(as_text=True)
    assert "sample-tour-note" not in real


# --- nothing public is made from it -------------------------------------------

def test_no_share_link_is_made_on_the_sample_and_an_old_one_opens_nothing(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    sid = ts.list_shows(mock_id)[0]["id"]
    share = c.get("/tours/%s/share" % mock_id).get_data(as_text=True)
    assert 'id="sample-no-share"' in share and 'action="/tours/%s/share/new"' % mock_id not in share
    c.post("/tours/%s/share/new" % mock_id, data={"scope": "day_sheet", "show_id": sid})
    assert ts.list_share_links(mock_id) == []
    # A link minted before the rule: the token no longer opens the sample.
    token = ts.create_share_link(mock_id, user["id"], "day_sheet", sid)
    assert flask_app.test_client().get("/tour-share/%s" % token).status_code == 404


def test_nothing_is_sold_for_a_sample_date(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    sid = ts.list_shows(mock_id)[0]["id"]
    vip = c.get("/tours/%s/shows/%s?tab=vip" % (mock_id, sid)).get_data(as_text=True)
    assert 'id="vip-sample"' in vip and 'id="vip-link"' not in vip
    r = c.post("/tours/%s/shows/%s/vip/offers/add" % (mock_id, sid),
               data={"name": "Soundcheck party", "price": "150"})
    assert "offer=sample" in r.headers["Location"]
    assert ts.list_vip_offers(mock_id, sid) == []
    token = ts.ensure_vip_link(mock_id, sid)
    anon = flask_app.test_client()
    assert anon.get("/vip/%s" % token).status_code == 404
    assert anon.post("/vip/%s/buy" % token, data={"offer_id": "x"}).status_code == 404


def test_a_sample_date_has_no_public_rider_or_show_day_and_is_never_advanced(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    sid = ts.list_shows(mock_id)[0]["id"]
    token = uuid.uuid4().hex
    store.set_show_share_token(user["id"], sid, token)
    anon = flask_app.test_client()
    assert anon.get("/rider/%s" % token).status_code == 404
    assert anon.get("/showday/%s" % token).status_code == 404
    r = c.post("/tours/%s/shows/%s/advance/send" % (mock_id, sid),
               data={"to": "venue@example.com", "subject": "Advance", "body": "Hi"})
    assert "fail=sample" in r.headers["Location"]
    r = c.post("/tours/%s/advance/send-all" % mock_id, data={"show": [sid]})
    assert "advance_fail=sample" in r.headers["Location"]

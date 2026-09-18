"""The split home page, and the switch that shows it.

The owner is moving the public story to the store, after which this
address is the door to the system rather than a website with a login on
it. The page exists; it is off.

Four things have to hold, and they are the reasons this file exists
rather than a note in a commit message:

  it is off by default        a deploy must never change the front page.
                              Nothing set anywhere means the long page.
  the owner can flip it both  a Render variable means a redeploy to try
  ways while looking at it    it and a second one to put it back
  nobody else can flip it     not the switch, not the preview
  no section is forked        the EQ, the rack and the Twin are the same
                              partials the long page uses, so a fix to
                              one fixes both pages

The long page is untouched, so the whole thing is one radio button away
from being what it was.
"""
import io
import os
import uuid

import pytest

import app as appmod
import db as store
import split_home
import plans
from app import create_app

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PW = "split-home-12345"


@pytest.fixture
def client():
    return appmod.app.test_client()


def _signed_in(app_obj, plan="pro"):
    """A real account, created the way a person creates one."""
    c = app_obj.test_client()
    email = "split-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Split", "email": email, "password": PW})
    c.post("/plan/switch", data={"plan": plan})
    c._email = email
    return c


def _on(monkeypatch):
    monkeypatch.setenv("SPLIT_HOME", "1")


def _off(monkeypatch):
    monkeypatch.delenv("SPLIT_HOME", raising=False)


# --- the switch ----------------------------------------------------------

def test_it_is_off_with_nothing_set(monkeypatch, client):
    """A deploy of this must not change what the world sees."""
    _off(monkeypatch)
    assert split_home.enabled() is False
    body = client.get("/").get_data(as_text=True)
    assert 'id="sbdoor-h"' not in body
    # and the long page is intact, all nine sections of it
    for section in ('id="artist-eq"', 'id="eight-tools"', 'id="artist-twin-section"',
                    'id="platform"'):
        assert section in body, section


def test_the_environment_can_turn_it_on(monkeypatch, client):
    _on(monkeypatch)
    assert split_home.enabled() is True
    assert 'id="sbdoor-h"' in client.get("/").get_data(as_text=True)


def test_any_other_value_is_off(monkeypatch):
    for value in ("0", "off", "no", "", "  ", "later"):
        monkeypatch.setenv("SPLIT_HOME", value)
        assert split_home.enabled() is False, value


def test_a_saved_choice_beats_the_environment(monkeypatch):
    """The owner looking at the page wins over whoever set the variable."""
    _on(monkeypatch)
    import db
    try:
        split_home.set_layout("full")
        assert split_home.enabled() is False
        split_home.set_layout("split")
        assert split_home.enabled() is True
        _off(monkeypatch)
        assert split_home.enabled() is True, "saved choice stands with no variable"
    finally:
        db.set_kv("home_layout", "")


def test_anything_but_split_saves_as_full():
    import db
    try:
        for value in ("full", "", None, "rooms", "yes"):
            split_home.set_layout(value)
            assert split_home.enabled() is False, value
    finally:
        db.set_kv("home_layout", "")


def test_only_an_owner_can_flip_it(monkeypatch):
    """404, not 403: for anybody signed in who is not the owner, the
    endpoint does not exist. An anonymous post is sent to sign in first,
    which is the same answer every admin route gives."""
    _off(monkeypatch)
    app_obj = create_app()
    stranger = _signed_in(app_obj)
    monkeypatch.setenv("OWNER_EMAILS", "somebody-else@example.net")
    assert stranger.post("/admin/home-layout", data={"layout": "split"}).status_code == 404
    assert split_home.enabled() is False
    anon = app_obj.test_client()
    assert anon.post("/admin/home-layout", data={"layout": "split"}).status_code in (302, 404)
    assert split_home.enabled() is False, "and either way nothing moved"


def test_only_an_owner_gets_the_preview(monkeypatch, client):
    """?home=split must not show a stranger a page the owner has not
    chosen, or the switch is decoration."""
    _off(monkeypatch)
    body = client.get("/?home=split").get_data(as_text=True)
    assert 'id="sbdoor-h"' not in body


def test_the_owner_can_look_at_either_without_switching_it(monkeypatch):
    _off(monkeypatch)
    app_obj = create_app()
    owner = _signed_in(app_obj, "label")
    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    with app_obj.app_context():
        store.set_kv("home_layout", "")
    assert 'id="sbdoor-h"' in owner.get("/?home=split").get_data(as_text=True)
    assert 'id="sbdoor-h"' not in owner.get("/?home=full").get_data(as_text=True)
    # Looking at it switched nothing, for the owner or for anybody else.
    assert split_home.enabled() is False
    assert 'id="sbdoor-h"' not in app_obj.test_client().get("/").get_data(as_text=True)


# --- the page ------------------------------------------------------------

@pytest.fixture
def page(monkeypatch):
    monkeypatch.setenv("SPLIT_HOME", "1")
    return appmod.app.test_client().get("/").get_data(as_text=True)


def test_the_door_is_the_first_thing_and_carries_the_real_form(page):
    door = page.split('class="sbdoor"')[1].split("</section>")[0]
    assert "Pick up where you left off." in door
    assert "One platform. Every stage." in door
    # The form /login serves, not a second copy: these are the tokens
    # password managers pair on and the handler reads.
    assert 'action="/login' in door
    assert 'name="email"' in door and 'autocomplete="username"' in door
    assert 'name="password"' in door and 'autocomplete="current-password"' in door
    assert 'id="lsr-login-form"' in door


def test_the_form_appears_once_on_the_page(page):
    """Two sign-in forms would mean two elements with the same ids."""
    assert page.count('id="lsr-login-form"') == 1
    assert page.count('id="lsr-password"') == 1


def test_the_line_under_the_form_follows_whether_sign_up_is_open(page):
    """The worst version of this page tells a stranger to create an
    account that sign-up will then refuse to create, so the line is drawn
    from the same answer the sign-up route gives rather than written down.

    Whichever way the deployment has it, exactly one of the two lines
    appears, and each says the true thing."""
    said_invite = "opening by invitation" in page
    said_signup = "Create an account" in page
    assert said_invite != said_signup, "one line or the other, never both"

    # Both branches, rendered, so neither can rot while the other is the
    # one the deployment happens to show.
    # A request context, because the template's context processors read
    # the session to build the nav.
    with appmod.app.test_request_context("/"):
        from flask import render_template
        closed = render_template("partials/split_door.html",
                                 split_home=split_home.get_split_home_config(False))
        opened = render_template("partials/split_door.html",
                                 split_home=split_home.get_split_home_config(True))
    assert "opening by invitation" in closed and "Create an account" not in closed
    assert "Create an account" in opened and "opening by invitation" not in opened
    # Either way the form itself is the same form.
    for markup in (closed, opened):
        assert 'action="/login' in markup and 'name="password"' in markup


def test_the_rail_is_a_map_and_not_a_progress_bar(page):
    rail = page.split('class="sbrail"')[1].split("</nav>")[0]
    for stage in split_home.STAGES:
        assert ">%s</span>" % stage in rail, stage
    assert rail.count("sbrail-stage") == 8
    # Nothing is ticked, done, complete or current: the page does not know
    # who is reading it.
    for claim in ("is-done", "is-current", "aria-current", "complete"):
        assert claim not in rail, claim


def test_no_section_is_forked(page):
    """The EQ, the rack and the Twin must be the same partials the long
    page uses, or a fix to one silently misses the other."""
    for partial in ("artist_eq.html", "eight_tools.html", "artist_twin.html"):
        long_page = io.open(os.path.join(HERE, "templates", "landing.html"),
                            encoding="utf-8").read()
        split = io.open(os.path.join(HERE, "templates", "landing_split.html"),
                        encoding="utf-8").read()
        assert partial in long_page and partial in split, partial
    for section in ('id="artist-eq"', 'id="eight-tools"', 'id="artist-twin-section"'):
        assert section in page, section


def test_the_story_sections_are_gone_from_the_page_but_not_the_repo(page):
    """They moved to the store; they did not stop existing."""
    for gone in ("sblanes", "sbcs-", "sbro-", "sbbo-"):
        assert gone not in page, gone
    for kept in ("lanes.html", "creative_studio.html", "rollout.html",
                 "back_office.html"):
        assert os.path.exists(os.path.join(HERE, "templates", "partials", kept)), kept


def test_memberships_read_their_prices_from_plans(page):
    band = page.split('class="sbmem"')[1].split("</section>")[0]
    for key, name, price, _blurb, _inc in plans.PLANS:
        if key == "fan":
            # Free, and no photographed metal pass claiming otherwise.
            assert "pass-fan" not in band
            continue
        assert price in band, (key, price)
        assert ">%s</span>" % name in band, name
        assert "pass-%s.png" % key in band, key


def test_every_pass_and_the_token_ship(page):
    for name in ("pass-artist", "pass-pro", "pass-label", "credit-token"):
        for ext in ("png", "webp"):
            path = os.path.join(HERE, "static", "img", "%s.%s" % (name, ext))
            assert os.path.exists(path), path
    # The photograph is decoration; the words beside it are the content.
    band = page.split('class="sbmem"')[1].split("</section>")[0]
    assert band.count('alt=""') == 4


def test_the_credit_packs_are_the_real_packs(page):
    band = page.split('class="sbmem"')[1].split("</section>")[0]
    for credits, cents, _label in plans.CREDIT_PACKS.values():
        assert "{:,}".format(credits) in band, credits
        assert "$%d" % (cents // 100) in band, cents


def test_there_is_a_way_back_to_the_store(page):
    """A visitor who wants the story must not be stuck on the door."""
    back = page.split('class="sbback"')[1].split("</section>")[0]
    assert "Tools for a bigger tomorrow." in back
    assert "streetbankermusic.com" in back or "<a href=" in back


def test_the_page_carries_the_stylesheets_its_sections_need(page):
    for sheet in ("split-home.css", "artist-eq.css", "eight-tools.css",
                  "artist-twin.css", "login-session-recall.css"):
        assert sheet in page, sheet
    for script in ("login-session-recall.js", "artist-eq.js", "eight-tools.js",
                   "artist-twin.js"):
        assert script in page, script
    # Nothing loads for a section that is not on this page.
    for absent in ("lanes.css", "creative-studio.css", "rollout.css", "back-office.css"):
        assert absent not in page, absent


def test_the_settings_toggle_shows_the_owner_which_one_is_on():
    t = io.open(os.path.join(HERE, "templates", "settings.html"),
                encoding="utf-8").read()
    box = t.split('id="home-layout"')[1].split("</section>")[0]
    assert 'action="/admin/home-layout"' in box
    assert 'value="split"' in box and 'value="full"' in box
    assert "home_split" in box, "the radio must show the current choice"
    assert "/?home=split" in box, "and offer a look before committing"

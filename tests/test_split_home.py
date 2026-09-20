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


def test_there_is_no_stage_rail_on_the_app_home(page):
    """The owner, 2026-09-18, looking at the eight stage pills under the
    door: "you have 8 bullets made like the 8 suite names this makes no
    sense". Eight pills in a row read as the eight suites, which they were
    not, so the rail left the page. This keeps it from coming back, in the
    markup or as dead rules in the page's own stylesheet."""
    assert "sbrail" not in page
    door = io.open(os.path.join(HERE, "templates", "partials", "split_door.html"),
                   encoding="utf-8").read()
    assert "sh.stages" not in door and "<nav" not in door
    css = io.open(os.path.join(HERE, "static", "css", "split-home.css"),
                  encoding="utf-8").read()
    assert ".sbrail" not in css


def test_the_door_is_the_garage_door_with_the_sign_in_over_it(page):
    """The owner: "the hero image needs to be much bigger and overlay the
    text on it with the sign up", and the sign-in as "a few ... bars
    across the bottom of it" rather than a big box. The picture is his
    garage door (2026-09-19: "i like the garage door the best"); the form
    is still the /login form, labels and all."""
    door = page.split('class="sbdoor"')[1]
    assert "door-garage-wide.webp" in door
    assert os.path.exists(os.path.join(HERE, "static", "img",
                                       "door-garage-wide.webp"))
    # Hidden from sight on this page, never from a screen reader.
    assert '<label for="lsr-email">Email</label>' in door
    assert '<label for="lsr-password">Password</label>' in door
    assert 'placeholder="Email"' in door and 'placeholder="Password"' in door
    # The long page's scoping hook is this page's alone.
    assert '<body class="sbhome' in page


def test_the_slim_sign_in_stays_on_the_door_and_off_login(client):
    """/login serves the same partial, and it must look exactly as it did:
    visible labels, the old placeholder, and none of the door's rules."""
    body = client.get("/login").get_data(as_text=True)
    assert 'placeholder="you@domain.com"' in body
    assert 'placeholder="Email"' not in body
    assert 'placeholder="Password"' not in body
    assert "sbhome" not in body and "split-home.css" not in body


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


def test_the_engraved_price_still_matches_plans(page):
    """The prices are cut into metal in a photograph, so nothing in the
    code can correct them. This is the thing that goes wrong quietly:
    change a tier in plans.PLANS and the plate keeps advertising the old
    number to every visitor. Fail the build instead.

    If this breaks, the fix is a new photograph from the owner, not an
    edit here.
    """
    for key, name, price, _blurb, _inc in plans.PLANS:
        if key == "fan":
            # Free, and no photographed metal pass claiming otherwise.
            assert "pass-plate-fan" not in page
            continue
        reads = split_home.ENGRAVED[key]
        assert reads.startswith(price.split("/")[0] + " a month."), (
            "the %s plate is engraved %r but plans says %s - the "
            "photograph needs reshooting" % (key, reads, price))


def test_each_pass_is_a_plate_a_word_mask_and_the_light_between(page):
    """Two images per pass, and the mask is the one that matters: the
    light is poured through the words, which is what makes them light a
    line at a time. A pass that lost its mask would still look right at
    rest and do nothing on hover, so check the wiring, not the look.
    """
    band = page.split('class="sbmem"')[1].split("</section>")[0]
    for key, name, _price, _blurb, _inc in plans.PLANS:
        if key == "fan":
            continue
        for slot, f in (("--sbmem-plate", "pass-plate-%s.webp" % key),
                        ("--sbmem-words", "pass-words-%s.webp" % key)):
            assert f in band, (key, f)
            assert os.path.exists(os.path.join(HERE, "static", "img", f)), f
        assert ">Choose %s</span>" % name in band, name
    # The three light layers, once per pass.
    for layer in ("sbmem-bloom", "sbmem-glow", "sbmem-sheen"):
        assert band.count('class="%s"' % layer) == 3, layer
    # Every word on a plate is in its label, so the pass is readable
    # without seeing it.
    for key in ("artist", "pro", "label"):
        assert split_home.ENGRAVED[key] in band, key


def test_the_coins_ship_and_stay_decorative(page):
    for name in ("credit-pile", "credit-coin"):
        assert os.path.exists(
            os.path.join(HERE, "static", "img", "%s.webp" % name)), name
    band = page.split('class="sbmem"')[1].split("</section>")[0]
    # Only the two coin images are decorative. The plates are labelled,
    # because they carry words.
    assert band.count('alt=""') == 2


def _band(body):
    return body.split('class="sbmem"')[1].split("</section>")[0]


def test_no_pack_is_priced_while_packs_are_off_sale(page):
    """Owner, 2026-09-18: "hide them until we know what the credits
    actually cost". Billing hid the packs on plans.CREDIT_PACKS_ON_SALE;
    the app home kept listing 500 for $15, 2,000 for $50 and 5,000 for
    $100 anyway. While the flag is off there is no pack list at all."""
    assert plans.CREDIT_PACKS_ON_SALE is False
    band = _band(page)
    assert "sbmem-packs" not in band
    for credits, cents, _label in plans.CREDIT_PACKS.values():
        assert "$%d" % (cents // 100) not in band, cents
        assert ">%s<" % "{:,}".format(credits) not in band, credits
    assert split_home.get_split_home_config()["packs"] == []


def test_the_credit_packs_are_the_real_packs_once_on_sale(monkeypatch):
    monkeypatch.setattr(plans, "CREDIT_PACKS_ON_SALE", True)
    monkeypatch.setenv("SPLIT_HOME", "1")
    band = _band(appmod.app.test_client().get("/").get_data(as_text=True))
    assert "sbmem-packs" in band
    for credits, cents, _label in plans.CREDIT_PACKS.values():
        assert "{:,}".format(credits) in band, credits
        assert "$%d" % (cents // 100) in band, cents


def test_the_passes_and_the_plans_link_go_somewhere_real(page, client):
    """They went to /plan, which is the Artist EQ's recommendation rather
    than the price list, with #artist, #pro and #label anchors that do not
    exist on it. No public page lists the memberships but this band, so
    the bar's Plans scrolls to it and a pass opens Billing, where the three
    are bought; a visitor who is not signed in signs in first."""
    band = _band(page)
    assert "/plan#" not in page
    assert band.count('href="/billing"') == 3
    bar = page.split('class="sbbar"')[1].split("</header>")[0]
    assert 'href="#memberships">Plans</a>' in bar
    assert '<section class="sbmem" id="memberships"' in page
    r = client.get("/billing")
    assert r.status_code in (301, 302) and "/login" in r.headers["Location"]
    assert "next=%2Fbilling" in r.headers["Location"] or "next=/billing" in r.headers["Location"]


def test_each_pass_says_what_on_it_is_not_open_yet(page):
    """Owner, 2026-09-17: mark them coming soon. The plates are engraved,
    so the line under each pass says it, built from the list that puts
    Soon on the suites strip rather than written down a second time."""
    import hubs
    pending = hubs.suites_pending()
    names = {k: label for k, _h, _i, label, _d in hubs.tool_suites()}
    lines = split_home.coming_soon(("artist", "pro", "label"))
    band = _band(page)
    for tier, line in lines.items():
        if line:
            assert '<p class="sbmem-soon">%s</p>' % line in band, tier
    # Every waiting suite is named on the Label pass, which carries them all.
    for key in pending:
        assert names[key] in lines["label"], key
    # A pass names only what it carries: Noise Lab runs on credits, which
    # only the Label pass includes.
    if "noise-lab" in pending:
        assert "Noise Lab" not in lines["artist"] and "Noise Lab" not in lines["pro"]
    if "artifacts" in pending and "company" in pending:
        assert lines["pro"] == "Artifacts and Company open soon."


def test_a_pass_with_nothing_waiting_says_nothing(monkeypatch):
    import hubs
    monkeypatch.setattr(hubs, "suites_pending", lambda: set())
    assert split_home.coming_soon(("artist", "pro", "label")) == {
        "artist": "", "pro": "", "label": ""}
    monkeypatch.setenv("SPLIT_HOME", "1")
    band = _band(appmod.app.test_client().get("/").get_data(as_text=True))
    assert "sbmem-soon" not in band


def test_the_bottom_lines_are_centred():
    """Owner, 2026-09-19: "you always push stuff over to the left side
    margin". The way back is one centred stack, the credits words are
    centred in their column, and the copyright line of both homepage
    footers is centred."""
    css = io.open(os.path.join(HERE, "static", "css", "split-home.css"),
                  encoding="utf-8").read()
    back = css.split(".sbback-inner {")[1].split("}")[0]
    assert "flex-direction: column" in back and "text-align: center" in back
    assert "space-between" not in back
    assert ".sbmem-credits-say { text-align: center; }" in css
    assert "justify-content: center" in css.split(".sbmem-credits-h {")[1].split("}")[0]
    for name in ("landing.html", "landing_split.html"):
        t = io.open(os.path.join(HERE, "templates", name), encoding="utf-8").read()
        line = t.split("{{ f.copyright }}")[0].rsplit("<div", 1)[1]
        assert "justify-center" in line and "text-center" in line, name


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


def test_the_tightened_sections_do_not_move_or_shrink_under_a_finger():
    """Two things the tightening must not cost. The eight-tools readout
    changes as the pointer moves along the rack, so it keeps two lines of
    room or everything under it jumps with each plate. And the Artist Twin
    rows are tap targets: the one-line rows are for a mouse on a wide
    screen only, everywhere else they keep artist-twin.css's 44px floor."""
    css = io.open(os.path.join(HERE, "static", "css", "split-home.css"),
                  encoding="utf-8").read()
    assert ".sbhome .sbet-readout { margin-top: 10px; min-height: 3em; }" in css
    compact = "@media (min-width: 1180px) and (pointer: fine) {\n  .sbhome .sbtw-summary { min-height: 0; }\n}"
    assert compact in css
    assert ".sbhome .sbtw-summary { padding: 3px 12px; gap: 10px; }" in css


def test_the_door_picture_comes_in_three_widths(page):
    """A phone draws the banner about 622px wide, so it is offered the
    smaller files rather than only the 1672px one."""
    door = page.split('class="sbdoor"')[1]
    for name in ("door-garage-wide-800.webp", "door-garage-wide-1280.webp"):
        assert name in door
        assert os.path.exists(os.path.join(HERE, "static", "img", name))

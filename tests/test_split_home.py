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
import re
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
    monkeypatch.delenv("MEMBERSHIP_BAND", raising=False)
    return appmod.app.test_client().get("/").get_data(as_text=True)


@pytest.fixture
def passes(monkeypatch):
    """The page with the engraved metal passes, the band the rack replaced
    (owner, 2026-09-23). One switch away, and still tested."""
    monkeypatch.setenv("SPLIT_HOME", "1")
    monkeypatch.setenv("MEMBERSHIP_BAND", "passes")
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


def test_the_engraved_price_still_matches_plans(passes):
    page = passes
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


def test_each_pass_is_a_plate_a_word_mask_and_the_light_between(passes):
    page = passes
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


def test_the_credits_band_is_the_owners_plate_beneath_the_memberships(page):
    """Owner, 2026-09-26: "put the tokens back on the homepage. Beneath
    where the membership is", then "Use this plate for the home page for
    credits. You fill out the needed text and button placements on it."
    The band is his photographed plate with the words live on its black
    field: the monthly figure is the one Billing grants, the note is the
    shared one, and the two doors are Billing (Label) and the tiers above.
    Still no pack price while packs are off sale (the next test)."""
    assert split_home.SHOW_CREDITS is True
    assert os.path.exists(os.path.join(HERE, "static", "img", "credits-plate.webp"))
    band = page.split('class="sbmem"')[1].split("</section>")[0]
    assert band.index("sbrk-unit") < band.index("sbmem-credits"), "beneath the memberships"
    credits = band.split('class="sbmem-credits"', 1)[1]
    assert 'src="/static/img/credits-plate.webp?v=1"' in credits and 'width="1508" height="562"' in credits
    assert "credit-coin" not in credits and "credit-pile" not in credits, "the plate replaces the loose coin art"
    assert "Studio credits" in credits and split_home.CREDIT_NOTE in credits
    assert "<b>%s</b>" % "{:,}".format(plans.LABEL_MONTHLY_CREDITS) in credits, "the figure Billing grants"
    assert "credits every month with Label" in credits
    assert re.search(r'href="/billing">Choose Label</a>', credits)
    assert re.search(r'href="#memberships">Compare memberships</a>', credits)
    css = io.open(os.path.join(HERE, "static", "css", "split-home.css"),
                  encoding="utf-8").read().replace("\r\n", "\n")
    # the words sit inside the measured field (57.7-95.5% x, 10.1-89.3% y)
    rule = css.split(".sbcr-unit .sbmem-credits-say {", 1)[1].split("}", 1)[0]
    box = {k: float(v) for k, v in re.findall(r"(left|top|width|height): ([\d.]+)%", rule)}
    assert box["left"] >= 57.7 and box["left"] + box["width"] <= 95.5, box
    assert box["top"] >= 10.1 and box["top"] + box["height"] <= 89.3, box
    step = css.split("@media (max-width: 1099px) {\n  .sbcr-unit", 1)
    assert len(step) == 2 and "position: static" in step[1].split("}\n}", 1)[0], "the words step under the plate"
    assert ".sbmem-coin" not in css and ".sbmem-pile" not in css
    assert ".sbcr-go .sb-btn { min-height: 44px;" in css, "both doors are full tap targets"


def test_the_home_page_has_no_dim_text_and_the_artist_letters_are_bronze(passes):
    page = passes
    """Owner, 2026-09-20: the Plans link "is really hard to see... any text
    that color needs to be brighter", and "the artist package should be
    the same kind of brown as pro and label is written in". The home
    sheet sets nothing in the second ink; the bar's links are near-white
    and gold under the pointer; and only the ARTIST pass carries the
    bronze tint layer, masked by its own words, under the light layers."""
    css = io.open(os.path.join(HERE, "static", "css", "split-home.css"),
                  encoding="utf-8").read()
    assert "var(--sb-ink-2)" not in css
    assert ".sbbar-nav a { color: var(--sb-ink); text-decoration: none; }" in css
    assert ".sbbar-nav a:hover { color: var(--sb-gold-bright); }" in css
    tint = css.split(".sbmem-tint {")[1].split("}")[0]
    assert "var(--sbmem-words)" in tint and "var(--sbmem-ink)" in tint
    assert "mix-blend-mode: multiply" in tint
    band = page.split('class="sbmem"')[1].split("</section>")[0]
    assert band.count('class="sbmem-tint"') == 1
    artist = band.split('aria-label="Artist pass')[0].rsplit("<a class=", 1)[1]
    assert "--sbmem-ink: #8C6A3C;" in artist
    for other in ("Pro pass", "Label pass"):
        pass_markup = band.split('aria-label="%s' % other)[0].rsplit("<a class=", 1)[1]
        assert "--sbmem-ink" not in pass_markup, other
    # The tint sits before the light layers, so the hover still lights the letters.
    assert band.index('class="sbmem-tint"') < band.index('class="sbmem-bloom"')
    # A fresh sheet and script version, so no browser keeps the old look.
    assert "split-home.css?v=18" in page and "artist-eq.js?v=15" in page

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
    # one door per tier; the credits plate under them adds its own Label
    # door to Billing (owner's credits plate, 2026-09-26)
    tiers = band.split('class="sbmem-credits"', 1)[0]
    assert tiers.count('href="/billing"') == 3
    bar = page.split('class="sbbar"')[1].split("</header>")[0]
    assert 'href="#memberships">Plans</a>' in bar
    assert '<section class="sbmem" id="memberships"' in page
    r = client.get("/billing")
    assert r.status_code in (301, 302) and "/login" in r.headers["Location"]
    assert "next=%2Fbilling" in r.headers["Location"] or "next=/billing" in r.headers["Location"]


def test_each_pass_says_what_on_it_is_not_open_yet(page, passes):
    """Owner, 2026-09-17: mark them coming soon. The plates are engraved,
    so the line under each pass says it, built from the list that puts
    Soon on the suites strip rather than written down a second time. On
    the rack the same line is printed on the glass under the plan's."""
    import hubs
    pending = hubs.suites_pending()
    names = {k: label for k, _h, _i, label, _d in hubs.tool_suites()}
    lines = split_home.coming_soon(("artist", "pro", "label"))
    band = _band(passes)
    rack = _band(page)
    for tier, line in lines.items():
        if line:
            assert '<p class="sbmem-soon">%s</p>' % line in band, tier
            assert '<span class="sbrk-soon">%s</span>' % line in rack, tier
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

def test_the_bar_has_no_logo_and_no_sign_in_link(page):
    """Owner, 2026-09-19: "remove the logo in the header top left and
    remove the sign in also as there is another button for that inches
    away". The garage door carries the wordmark and the sign-in row sits
    on the door, so the bar keeps only Plans and the way back."""
    bar = page.split('class="sbbar"')[1].split("</header>")[0]
    assert "sbbar-mark" not in bar
    assert "streetbanker-logo" not in bar
    assert ">Sign in<" not in bar and 'aria-current="page"' not in bar
    assert 'href="#memberships">Plans</a>' in bar


# --- the membership rack (owner, 2026-09-23) --------------------------------

def _rack(body):
    band = _band(body)
    assert 'data-band="rack"' in band, "the rack is the band"
    return band


def test_the_rack_is_the_band_and_the_passes_are_one_switch_away(page, monkeypatch):
    """Nothing set anywhere means the rack. MEMBERSHIP_BAND=passes brings
    the engraved plates back; the owner's saved choice beats both."""
    band = _rack(page)
    assert "room-plate.webp" in band and "sbmem-pass" not in band
    assert "pass-plate-" not in band, "no photographed metal on the rack"
    monkeypatch.setenv("MEMBERSHIP_BAND", "passes")
    assert split_home.band() == "passes"
    other = _band(appmod.app.test_client().get("/").get_data(as_text=True))
    assert "sbmem-pass" in other and "sbrk-screen" not in other
    monkeypatch.setenv("MEMBERSHIP_BAND", "nonsense")
    assert split_home.band() == "rack", "anything else is the rack"


def test_each_screen_reads_its_price_from_plans(page):
    """The owner's render of this band had the prices cut into the
    picture. Here the figure is read from plans.PLANS at render, so a
    price change is one edit and this test would catch a template that
    typed a number instead."""
    band = _rack(page)
    assert band.count('<li class="sbrk-screen"') == 3
    for key, name, price, blurb, _inc in plans.PLANS:
        if key == "fan":
            assert "Fan" not in band.split("sbrk-screens")[1], "free, and no screen"
            continue
        amount = price.split("/")[0].lstrip("$")
        assert '<span class="sbrk-cur">$</span>%s</span>' % amount in band, (key, amount)
        assert '<span class="sbrk-k" data-t="%s">%s</span>' % (name, name) in band, name
        assert blurb in band, blurb
        assert 'aria-label="%s, %s a month. ' % (name, price.split("/")[0]) in band, name
        assert "Choose %s." % name in band, name
        assert price not in band, "the plans string itself is never printed"
    # every screen is the door to Billing, one per tier, as the passes were
    doors = re.findall(r'class="sbrk-door[^"]*" href="([^"]+)"', band)
    assert doors == ["/billing"] * 3, doors
    assert "sbrk-go" not in band, "the screens are the doors; no second button"


def test_the_membership_rack_is_the_rooms_slim_plate_at_its_measured_screens():
    """Owner, 2026-09-26: "Should we use this one for the memberships on the
    home page instead of the thicker, wider one? We don't necessarily need
    it to be as big." So the rack is the rooms' room-plate.webp (1774x421),
    and RACK_SCREENS are the boxes cc_rack.html measured off that file,
    held equal here so a re-measure moves both. The price and /month share
    a row and the plate steps aside from 1100px down, because this glass
    is a third as tall as the command plate's."""
    cc = io.open(os.path.join(HERE, "templates", "partials", "cc_rack.html"),
                 encoding="utf-8").read()
    boxes = tuple(tuple(re.findall(r'"([\d.]+)"', box))
                  for box in re.findall(r"\(([^()]+)\)", cc.split("set boxes = [", 1)[1].split("]", 1)[0]))
    assert len(boxes) == 3 and all(len(b) == 4 for b in boxes), boxes
    assert split_home.RACK_SCREENS == boxes, (split_home.RACK_SCREENS, boxes)
    t = io.open(os.path.join(HERE, "templates", "partials", "memberships_rack.html"),
                encoding="utf-8").read()
    assert 'src="/static/img/room-plate.webp?v=1"' in t and 'width="1774" height="421"' in t
    assert 'src="/static/img/command-plate' not in t, "the comment may name it as history; the img may not"
    assert '<span class="sbrk-row"><span class="sbrk-price">' in t and '<span class="sbrk-per">/month</span></span>' in t
    css = io.open(os.path.join(HERE, "static", "css", "split-home.css"),
                  encoding="utf-8").read()
    assert ".sbrk-row { display: flex; align-items: baseline;" in css
    assert "@media (max-width: 1099px) {\n  .sbrk-plate { display: none; }" in css.replace("\r\n", "\n")
    rooms = io.open(os.path.join(HERE, "templates", "partials", "cc_rack.html"),
                    encoding="utf-8").read()
    assert 'src="/static/img/room-plate.webp' in rooms
    assert 'src="/static/img/command-plate' not in rooms


def test_the_static_clears_under_the_pointer_and_never_shows_on_a_phone():
    """At rest the glass is dark with the tier's NAME on it and nothing
    else (owner, 2026-09-23: "no static, nothing" - snow, a drift and a
    particle layer were each rejected in turn; 2026-09-26: the empty glass
    "looks like an error", so the name sits there until the reading cuts
    in over it). Hover, focus or a first tap cuts the
    tier in the way the room racks do; the leave glitches it out. No media query decides who gets the static -
    a touchscreen laptop reports no hover at all in Chrome (the owner's
    own machine, 2026-09-23) and a gate would have shown him nothing. A
    phone gets the screens stacked and resolved. Less motion stops the
    jitter. The touch reveal is one small script; the band works as doors
    without it."""
    css = io.open(os.path.join(HERE, "static", "css", "split-home.css"),
                  encoding="utf-8").read()
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # Nothing on the glass: no snow, no drift, no particle layer, no sweep
    # (owner, 2026-09-23: "no static, nothing").
    for gone in ("sbrk-static", "crt-static.png", "crt-particles.png", "sbrk-drift",
                 "sbrk-gather", "sbrk-burst", "sbrk-sync", "sbrk-strike", ".sbrk-door::before",
                 # the scanlines: a pseudo-element over the whole glass, at
                 # rest and always (audit, 2026-09-23 - rack-1)
                 ".sbrk-door::after", "repeating-linear-gradient"):
        assert gone not in body, gone + " is an overlay"
    assert ".sbrk-k::before" in body, "the name's colour-split copies are the kit's grammar and stay"
    t = io.open(os.path.join(HERE, "templates", "partials", "memberships_rack.html"),
                encoding="utf-8").read()
    assert "sbrk-static" not in t
    # the name at rest (owner, 2026-09-26): one word before the reading,
    # dim, gone the instant the reading cuts in, back once the leave has
    # glitched the reading out; never on the phone, whose screens render
    # resolved and would say the name twice.
    assert t.index('class="sbrk-idle" aria-hidden="true">{{ t.name }}<') < t.index('class="sbrk-read"')
    assert ".sbrk-idle {" in body
    assert ".sbrk-door:hover .sbrk-idle, .sbrk-door:focus-visible .sbrk-idle, .sbrk-door.is-on .sbrk-idle { opacity: 0; }" in body
    assert "@keyframes sbrk-idle-back" in body and ".sbrk-door.is-out .sbrk-idle { animation: sbrk-idle-back" in body
    assert ".sbrk-idle { display: none; }" in body.split("@media (max-width: 1099px)", 1)[1]
    # the cut-in and the glitch-out, in the kit's grammar
    assert "@keyframes sbrk-out" in body and ".sbrk-door.is-out .sbrk-read" in body
    assert ".sbrk-door:focus-visible .sbrk-read" in body, "the keyboard cuts it in too"
    assert ".sbrk-door.is-on .sbrk-read" in body, "a first tap cuts it in too"
    # A RENDER, not a snap (owner, 2026-09-23: "more like the room renders
    # where it comes together, not so much static to an image in 1 second"):
    # the reading assembles over more than a second in the kit's own
    # grammar - stepped cuts, the colour-split copies on the name, the
    # price striking in, the lines arriving last.
    m = re.search(r"animation: sbrk-assemble ([\d.]+)s steps\(1, end\) both", body)
    assert m and float(m.group(1)) >= 1.2, "the picture comes together, it does not snap"
    for kf in ("sbrk-assemble", "sbrk-split-a", "sbrk-split-b", "sbrk-in"):
        assert "@keyframes %s" % kf in body, kf
    assert 'content: attr(data-t)' in body.split(".sbrk-k::before, .sbrk-k::after {", 1)[1].split("}", 1)[0]
    delays = re.findall(r"\.sbrk-door\.is-on \.sbrk-(k|per|line|soon) \{ animation-delay: ([\d.]+)s; \}", body)
    order = {k: float(v) for k, v in delays}
    assert order["k"] < order["per"] < order["line"] < order["soon"], order
    for q in ("@media (prefers-reduced-motion: reduce)", "@media (max-width: 1099px)"):
        assert q in body, q
    for gate in ("(hover: none)", "(any-hover: none)", "(pointer: coarse)"):
        assert gate not in body, gate + " would hide the static from a touchscreen laptop"
    js_path = os.path.join(HERE, "static", "js", "memberships-rack.js")
    assert os.path.exists(js_path)
    js = io.open(js_path, encoding="utf-8").read()
    assert '"touchend"' in js and 'classList.add("is-on")' in js and "preventDefault" in js
    assert 'getComputedStyle(read).opacity === "1"' in js, "a resolved screen opens on the first tap"
    assert '"mouseleave"' in js and 'classList.add("is-out")' in js, "the leave statics out"
    page_t = io.open(os.path.join(HERE, "templates", "landing_split.html"), encoding="utf-8").read()
    assert "memberships-rack.js?v=2" in page_t
    # every word renders on the glass: no ch cap on the lines, and the plate
    # steps aside below 960px where the glass is too short for five lines
    assert "max-width: 26ch" not in body and "max-width: 28ch" not in body
    phone = body.split("@media (max-width: 1099px)", 1)[1]
    assert ".sbrk-plate { display: none; }" in phone
    # ...and the stacked screens STAY resolved: pointing at one or tabbing
    # to it must not blank it and replay the cut-in (audit, 2026-09-23 -
    # rack-2). Every reveal state is switched off inside the phone block.
    rules = re.findall(r"([^{}]+)\{([^}]*)\}", phone)
    calmed = {sel.strip() for sels, decl in rules if "animation: none" in decl
              for sel in sels.split(",")}
    for state in (".sbrk-door:hover", ".sbrk-door:focus-visible", ".sbrk-door.is-on", ".sbrk-door.is-out"):
        for part in (" .sbrk-read", " .sbrk-k::before", " .sbrk-k::after"):
            assert state + part in calmed, state + part + " still animates on the stacked screens"
    for state in (".sbrk-door:hover", ".sbrk-door:focus-visible", ".sbrk-door.is-on"):
        assert state + " .sbrk-read > *" in calmed, state + " .sbrk-read > * still animates"
    calm = body.split("@media (prefers-reduced-motion: reduce)")
    assert any("animation: none" in part and ".sbrk-read" in part for part in calm[1:])
    t = io.open(os.path.join(HERE, "templates", "partials", "memberships_rack.html"),
                encoding="utf-8").read()
    assert "<script" not in t, "the script is the page's, loaded once with the others"
    assert "cqh" not in body.split(".sbrk-unit {", 1)[1], "nothing on a plate is sized off its height"


def test_only_an_owner_flips_the_band(monkeypatch):
    """Same rule as the home layout: 404 to anybody signed in who is not
    the owner, sign-in first for anybody else, and nothing moves."""
    _off(monkeypatch)
    monkeypatch.delenv("MEMBERSHIP_BAND", raising=False)
    app_obj = create_app()
    stranger = _signed_in(app_obj)
    monkeypatch.setenv("OWNER_EMAILS", "somebody-else@example.net")
    assert stranger.post("/admin/membership-band", data={"band": "passes"}).status_code == 404
    assert split_home.band() == "rack"
    anon = app_obj.test_client()
    assert anon.post("/admin/membership-band", data={"band": "passes"}).status_code in (302, 404)
    assert split_home.band() == "rack"
    # the owner can, both ways, and the saved choice beats the environment
    owner = _signed_in(app_obj, "label")
    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    try:
        r = owner.post("/admin/membership-band", data={"band": "passes"})
        assert r.status_code == 302 and r.headers["Location"].endswith("/settings?band=saved#home-layout")
        assert split_home.band() == "passes"
        monkeypatch.setenv("MEMBERSHIP_BAND", "rack")
        assert split_home.band() == "passes", "the saved choice wins"
        owner.post("/admin/membership-band", data={"band": "rack"})
        assert split_home.band() == "rack"
        settings = owner.get("/settings").get_data(as_text=True)
        assert 'action="/admin/membership-band"' in settings
    finally:
        with app_obj.app_context():
            store.set_kv("membership_band", "")


# ---- audit, 2026-09-23 -----------------------------------------------------

def test_every_screen_s_name_reads_the_whole_tier_and_its_focus_ring_is_pinned(page):
    """rack-10. The link's name carries the whole reading (the reading
    itself is aria-hidden): name, price, the plan's line and, where one
    exists, what on it is not open yet. Checked on the LABEL, not anywhere
    in the band - the blurb is also in the hidden reading. And the keyboard
    ring the rack draws is pinned."""
    band = _rack(page)
    labels = re.findall(r'class="sbrk-door[^"]*" href="/billing"\s+aria-label="([^"]*)"', band)
    assert len(labels) == 3, labels
    soon = split_home.coming_soon([k for k, *_r in plans.PLANS if k != "fan"])
    paid = [p for p in plans.PLANS if p[0] != "fan"]
    for label, (key, name, price, blurb, _inc) in zip(labels, paid):
        assert label.startswith("%s, %s a month. " % (name, price.split("/")[0])), label
        assert blurb.replace("'", "&#39;") in label or blurb in label, (key, label)
        if soon.get(key):
            assert soon[key].replace("'", "&#39;") in label or soon[key] in label, (key, label)
        assert label.endswith("Choose %s." % name), label
    css = io.open(os.path.join(HERE, "static", "css", "split-home.css"), encoding="utf-8").read()
    assert ".sbrk-door:focus-visible { outline: 2px solid var(--sb-gold-bright)" in css


def test_a_screen_the_pointer_only_crossed_stays_dark():
    """rack-3. The leave glitches OUT only a screen that showed something.
    sbrk-out starts at full opacity, so leaving a screen inside the cut-in's
    first step (opacity 0 for the first tenth of sbrk-assemble) used to
    flash the whole tier. The script's threshold is that first step,
    read off the sheet so the two cannot drift apart."""
    css = re.sub(r"/\*.*?\*/", "", io.open(os.path.join(HERE, "static", "css", "split-home.css"),
                                            encoding="utf-8").read(), flags=re.S)
    dur = float(re.search(r"animation: sbrk-assemble ([\d.]+)s", css).group(1))
    frames = css.split("@keyframes sbrk-assemble", 1)[1].split("@keyframes", 1)[0]
    assert re.search(r"0%\s*\{ opacity: 0;", frames)
    first = float(re.search(r"\n\s*(\d+)%\s*\{ opacity: \.", frames).group(1))
    js = io.open(os.path.join(HERE, "static", "js", "memberships-rack.js"), encoding="utf-8").read()
    ms = int(re.search(r"var LIT_AFTER_MS = (\d+);", js).group(1))
    assert ms == round(dur * 1000 * first / 100), (ms, dur, first)
    # the leave and the blur go through the check; only a lit screen goes out
    assert '"mouseleave", function (ev) { leave(ev.currentTarget); }' in js
    assert '"blur", function (ev) { leave(ev.currentTarget); }' in js
    body = js.split("function leave(door)", 1)[1].split("\n  }", 1)[0]
    assert 'classList.contains("is-on")' in body and "LIT_AFTER_MS" in body
    assert "out(door)" in body and 'classList.remove("is-on", "is-out")' in body


def test_the_owner_s_copy_describes_the_rack_that_ships():
    """rack-4 and rack-5. The Settings radio, the page and partial comments
    and the module docstring still described CRT static at rest (retired
    for dark glass, owner, 2026-09-23) and a stages rail the app home no
    longer has."""
    t = io.open(os.path.join(HERE, "templates", "settings.html"), encoding="utf-8").read()
    box = t.split('id="home-layout"')[1].split("</section>")[0]
    assert "static until" not in box
    assert "Rack: three dark screens, each shows its plan when you point at it" in box
    assert "stages rail" not in box, "the rail left the app home on 2026-09-18"
    for rel in (("templates", "landing_split.html"), ("templates", "partials", "memberships_band.html"),
                ("templates", "partials", "memberships_rack.html"), ("split_home.py",),
                ("static", "css", "split-home.css")):
        text = io.open(os.path.join(HERE, *rel), encoding="utf-8").read()
        for stale in ("CRT static", "static until", "The static needs the glass empty",
                      "No JavaScript anywhere in this band"):
            assert stale not in text, (rel, stale)
    assert "the stages rail" not in io.open(os.path.join(HERE, "split_home.py"), encoding="utf-8").read()
    ledger = io.open(os.path.join(HERE, "docs", "FEATURE-LEDGER.md"), encoding="utf-8").read()
    assert "CRT static on each screen at rest" not in ledger
    assert "Under 760px the plate steps aside" not in ledger

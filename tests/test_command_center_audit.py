"""The Command Center after the 2026-09-23 audit (group cc).

Each test pins a rule the page promised and did not keep, through the
real forms and the real way back where there is one - the gaps the audit
listed as cc-20: the done line reached through the back link, a read seat
on the page from zero, the 503 on every failed read, the icons' stroke,
the operational Start-here doors, an untouched Press Kit save. And the
cross-room doors: a seat is never handed a page every seat is bounced
from (x-1), and a page the owner switched off is words, not a door (x-2).
"""
import io
import re
import uuid
from urllib.parse import unquote

import pytest

import account_state as acs
import app as appmod
import db as store
import links_store as mls
import page_switches
import release_ready_store
import team_areas

PW = "cc-audit-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("RENDER", raising=False)


def _account(plan="pro", name="Fresh"):
    email = "ccaud-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    if plan:
        store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    c._email, c._id = email, uid
    return c, uid


def _flags(uid):
    return acs.read(uid, store, mls, release_ready_store)


def _back_link(body):
    m = re.search(r'<a href="([^"]+)" id="sb-room-back"', body)
    return m.group(1).replace("&amp;", "&") if m else None


def _hrefs(body):
    return [h.replace("&amp;", "&") for h in re.findall(r'href="([^"]+)"', body)]


# ---- cc-2: an untouched Press Kit save is not "who you are" ----------------

def test_saving_the_press_kit_untouched_is_not_identity():
    """The EPK form always sends the colour input's default. That alone used
    to complete "Tell us who you are" and say "Your profile was saved"."""
    c, uid = _account()
    untouched = {"tagline": "", "bio": "", "location": "", "genres": "",
                 "socials": {}, "contact": {}, "press": [], "show_sweep": False,
                 "bg_color": "#141210", "sections_off": [], "sections_on": [],
                 "deal_ask": "", "deal_terms": "", "video_url": "", "store_url": "",
                 "merch": []}
    assert c.post("/epk/save", json=untouched).status_code == 200
    assert store.get_epk(uid)["data"].get("bg_color") == "#141210", "the colour was saved"
    assert _flags(uid)["identity"] is False
    body = c.get("/command-center?from=identity").get_data(as_text=True)
    assert "Your profile was saved" not in body
    # a real detail is identity
    assert c.post("/epk/save", json=dict(untouched, tagline="Night drives, no brakes")).status_code == 200
    assert _flags(uid)["identity"] is True


# ---- cc-3: the done line through the REAL way back ---------------------------

def test_every_door_carries_the_step_inside_its_way_back():
    c, _uid = _account()
    body = c.get("/command-center").get_data(as_text=True)
    for key, href in (("identity", "/epk"), ("song", "/tracks")):
        assert "%s?returnTo=/command-center%%3Ffrom%%3D%s" % (href, key) in body, key
    assert "?returnTo=/command-center&amp;from=" not in body, "the from= that the back link dropped"


def test_the_profile_door_comes_back_with_the_sentence_through_the_back_link():
    c, uid = _account()
    door = re.search(r'<a class="cz-cta" href="([^"]+)"', c.get("/command-center").get_data(as_text=True))
    epk = c.get(door.group(1).replace("&amp;", "&")).get_data(as_text=True)
    assert c.post("/epk/save", json={"tagline": "Night drives"}).status_code == 200
    back = _back_link(epk)
    assert back == "/command-center?from=identity", back
    body = c.get(back).get_data(as_text=True)
    assert "Your profile was saved. Setup is now 1 of 5 complete." in body


def test_the_song_door_saves_and_lands_on_the_sentence():
    """The catalog's add form carries the way back through the save."""
    c, uid = _account()
    store.save_epk(uid, {"tagline": "Night drives"})
    door = [h for h in _hrefs(c.get("/command-center").get_data(as_text=True))
            if h.startswith("/tracks?returnTo=")][0]
    r = c.get(door)
    assert r.status_code == 302
    page = c.get(r.headers["Location"]).get_data(as_text=True)
    form = page.split('action="/tracks/add"', 1)[1].split("</form>", 1)[0]
    hidden = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)"', form))
    assert hidden.get("returnTo") == "/command-center?from=song", hidden
    r = c.post("/tracks/add", data=dict(hidden, title="Cell 5"))
    assert r.status_code == 302 and r.headers["Location"].endswith("/command-center?from=song")
    body = c.get(r.headers["Location"]).get_data(as_text=True)
    assert "Your first song was added. Setup is now 2 of 5 complete." in body


def test_the_link_door_keeps_its_way_back_after_the_save():
    c, uid = _account()
    store.save_epk(uid, {"tagline": "Night drives"})
    store.add_os_track(uid, "Cell 5")
    link_door = acs.door("/links/new", "link")
    r = c.post(link_door, data={"title": "Cell 5 out now", "campaign_type": "release"})
    assert r.status_code == 302
    loc = r.headers["Location"]
    assert re.match(r"^/links/[^/]+/edit\?returnTo=", loc), loc
    edit = c.get(loc).get_data(as_text=True)
    back = _back_link(edit)
    assert back == "/command-center?from=link", back
    assert "Your first smart link is ready." in c.get(back).get_data(as_text=True)


def test_the_capture_door_opens_the_campaign_at_its_capture_section():
    c, uid = _account()
    store.save_epk(uid, {"tagline": "Night drives"})
    tid = store.add_os_track(uid, "Cell 5")
    store.save_track_analysis(uid, {"track_id": tid, "filename": "c.wav", "integrated": -9.0})
    cid = mls.create_campaign(uid, "cap-%s" % uuid.uuid4().hex[:6], {"title": "Cell 5"})
    body = c.get("/command-center").get_data(as_text=True)
    door = "/links/%s/edit?returnTo=/command-center%%3Ffrom%%3Dcapture#capture" % cid
    assert door in body.replace("&amp;", "&"), "capture opens on the campaign's own capture section"
    edit = c.get(door.split("#")[0]).get_data(as_text=True)
    assert 'id="capture"' in edit


# ---- cc-4: a read seat is never handed a setup door ---------------------------

def _seat(owner_c, access):
    member_c, member_id = _account("artist", "Member")
    r = owner_c.post("/team/invite", data={"email": member_c._email, "role": "manager",
                                           "access": access, "areas_sent": "1",
                                           "areas": list(team_areas.keys())})
    assert r.get_json().get("ok"), r.get_json()
    token = [m for m in store.list_team(owner_c._id)
             if m["email"] == member_c._email][0]["invite_token"]
    assert member_c.post("/team/join/" + token, data={}).status_code == 302
    assert member_c.post("/portal/%s/open" % owner_c._id).status_code == 302
    return member_c


def test_a_read_seat_gets_no_setup_door_and_is_told_who_does_it():
    owner, _uid = _account("pro")
    reader = _seat(owner, "read")
    body = reader.get("/command-center").get_data(as_text=True)
    zone = body.split('class="cz"', 1)[1]
    assert 'class="cz-cta"' not in zone, "no Continue setup"
    assert "cz-btn--primary" not in zone and "cz-btn--outline\" href=\"/epk" not in zone
    for door in ("/epk?", "/tracks?", "/links/new?"):
        assert door not in zone, door
    assert "The account owner or a seat with edit access does this step." in zone
    # an edit seat keeps the doors
    editor = _seat(owner, "edit")
    assert 'class="cz-cta"' in editor.get("/command-center").get_data(as_text=True)


# ---- cc-5: every failed read is the 503 page ------------------------------------

@pytest.mark.parametrize("target", ["store.get_artist_signal_profile",
                                    "cc.open_actions", "mls.list_campaigns"])
def test_a_failed_read_on_the_page_from_zero_is_the_error_page(monkeypatch, target):
    import command_center as cc_mod
    c, uid = _account()
    store.add_os_track(uid, "Cell 5")
    mod, name = {"store": store, "cc": cc_mod, "mls": mls}[target.split(".")[0]], target.split(".")[1]
    calls = {"n": 0}
    real = getattr(mod, name)

    def boom(*a, **k):
        calls["n"] += 1
        # the state's own two reads of campaigns (its doors, its facts) pass,
        # so it is the PAGE's read that fails for mls.list_campaigns
        if name == "list_campaigns" and calls["n"] <= 2:
            return real(*a, **k)
        raise RuntimeError("db is down")
    monkeypatch.setattr(mod, name, boom)
    r = c.get("/command-center")
    assert r.status_code == 503, target
    assert "We could not load your Command Center" in r.get_data(as_text=True)


@pytest.mark.parametrize("target", ["build_alerts", "get_summary", "open_actions"])
def test_a_failed_read_on_the_operational_page_is_the_error_page(monkeypatch, target):
    import command_center as cc_mod
    c, uid = _account()
    store.save_statement(uid, "q1.csv", [
        {"title": "Higher Places", "source": "Spotify", "amount": 100.0, "period": "2026-01"}])

    def boom(*a, **k):
        raise RuntimeError("db is down")
    monkeypatch.setattr(cc_mod, target, boom)
    r = c.get("/command-center")
    assert r.status_code == 503, target
    assert "We could not load your Command Center" in r.get_data(as_text=True)


# ---- cc-6: the icons are strokes, never black shapes ---------------------------

def test_every_icon_on_the_page_from_zero_carries_the_stroke_rules():
    c, _uid = _account()
    body = c.get("/command-center").get_data(as_text=True)
    zone = body.split('class="cz"', 1)[1].split("Ask Street Banker</a>", 1)[0]
    svgs = re.findall(r"<svg([^>]*)>", zone)
    assert svgs, "the page draws icons"
    for attrs in svgs:
        assert re.search(r'class="[^"]*\bsb-i\b', attrs), attrs
    css = io.open("static/css/command-zero.css", encoding="utf-8").read()
    rule = re.search(r"\.cz svg\.cz-ico \{([^}]*)\}", css).group(1)
    assert "fill: none" in rule and "stroke: currentColor" in rule


# ---- cc-8, cc-12, cc-15: the operational page ---------------------------------

def test_an_account_with_fans_is_not_told_it_is_empty():
    c, uid = _account()
    # an imported fan, filed under no campaign: no essential is done, and
    # the account is working (a campaign would complete the link step)
    mls.upsert_fan(uid, "fan-%s@example.net" % uuid.uuid4().hex[:6], "", "Fan")
    assert mls.list_fans(uid) and not any(_flags(uid).values())
    body = c.get("/command-center").get_data(as_text=True)
    assert 'class="cz"' not in body, "fans on file: operational"
    assert "Start here" in body
    assert "completely empty" not in body


def test_the_operational_start_here_doors_carry_the_way_back():
    c, uid = _account()
    store.save_statement(uid, "q1.csv", [
        {"title": "Higher Places", "source": "Spotify", "amount": 100.0, "period": "2026-01"}])
    body = c.get("/command-center").get_data(as_text=True)
    panel = body.split("Start here", 1)[1].split("</section>", 1)[0]
    doors = [h for h in _hrefs(panel) if not h.startswith("#")]
    assert doors, "the panel offers doors"
    for h in doors:
        assert "returnTo=/command-center%3Ffrom%3D" in h, h


def test_the_operational_page_s_first_heading_is_its_h1():
    c, uid = _account()
    store.save_statement(uid, "q1.csv", [
        {"title": "Higher Places", "source": "Spotify", "amount": 100.0, "period": "2026-01"}])
    main = c.get("/command-center").get_data(as_text=True).split('id="sb-main"', 1)[1]
    first = re.search(r"<h([1-6])[\s>]", main)
    assert first.group(1) == "1", "the first heading in main is h%s" % first.group(1)


def test_all_tools_skips_no_heading_level():
    c, _uid = _account()
    main = c.get("/all-tools").get_data(as_text=True).split('id="sb-main"', 1)[1]
    levels = [int(x) for x in re.findall(r"<h([1-6])[\s>]", main)]
    jumps = [(a, b) for a, b in zip(levels, levels[1:]) if b > a + 1]
    assert not jumps, jumps[:3]


# ---- cc-9: one period is not a trend -----------------------------------------

def test_one_statement_period_draws_no_comparison():
    c, uid = _account()
    store.save_statement(uid, "q1.csv", [
        {"title": "Higher Places", "source": "Spotify", "amount": 100.0, "period": "2026-01"}])
    body = c.get("/command-center").get_data(as_text=True)
    assert "vs last month" not in body and "0.0%" not in body
    assert "One period on file, so there is nothing to compare it with yet." in body
    store.save_statement(uid, "q2.csv", [
        {"title": "Higher Places", "source": "Spotify", "amount": 150.0, "period": "2026-02"}])
    body = c.get("/command-center").get_data(as_text=True)
    assert "50.0%" in body, "two periods: the comparison is real"


# ---- cc-16: a locked step is a disabled button; Done is a state ---------------

def test_locked_is_a_disabled_button_and_done_is_words():
    c, uid = _account()
    body = c.get("/command-center").get_data(as_text=True)
    assert re.search(r'<button type="button" class="cz-btn cz-btn--locked" disabled>', body)
    store.save_epk(uid, {"tagline": "Night drives"})
    body = c.get("/command-center").get_data(as_text=True)
    done = re.search(r'<span class="cz-btn cz-btn--done"[^>]*>', body).group(0)
    assert "aria-disabled" not in done
    assert 'aria-disabled="true"' not in body.split('class="cz"', 1)[1]


# ---- cc-19: the explore panel's button goes under its words -----------------

def test_the_explore_panel_wraps_its_button_under_the_words():
    css = io.open("static/css/command-zero.css", encoding="utf-8").read()
    assert re.search(r"\.cz-explore \{ flex-wrap: wrap;", css)
    assert re.search(r"\.cz-explore > div \{ flex: 1 1 calc\(100% - 70px\); \}", css)


# ---- x-1: a seat is never handed a door every seat is bounced from ----------

def _follow(client, href):
    r = client.get(href)
    return r.status_code, r.headers.get("Location", "")


@pytest.mark.parametrize("access", ["edit", "read"])
def test_a_seat_is_offered_no_door_it_is_bounced_from(access):
    owner, _uid = _account("label")
    member = _seat(owner, access)
    pages = ["/command-center", "/all-tools", "/room/business", "/room/fans",
             "/room/stage", "/room/marketing"]
    for page in pages:
        body = member.get(page).get_data(as_text=True)
        main = body.split('id="sb-main"', 1)[1]
        for href in set(_hrefs(main)):
            if not href.startswith("/") or href.startswith("/static/"):
                continue
            code, loc = _follow(member, href.split("#")[0])
            assert "team=blocked" not in loc, (access, page, href, loc)


# ---- x-2: a switched-off page is words, not a door ---------------------------

@pytest.fixture
def hidden():
    before = page_switches.hidden_keys()

    def hide(*keys):
        saved = page_switches.set_hidden(set(before) | set(keys))
        assert set(keys) <= saved, (keys, saved)
    yield hide
    page_switches.set_hidden(before)


def test_a_switched_off_press_kit_is_not_a_door_on_the_command_center(hidden):
    key = [k for _n, k, h, _l in page_switches.entries() if h == "/epk"][0]
    hidden(key)
    c, _uid = _account()
    body = c.get("/command-center").get_data(as_text=True)
    zone = body.split('class="cz"', 1)[1]
    assert "/epk?" not in zone and 'class="cz-cta"' not in zone
    assert "This is switched off on this account for now." in zone


def test_a_switched_off_directory_takes_browse_all_tools_off(hidden):
    key = [k for _n, k, h, _l in page_switches.entries() if h == "/all-tools"][0]
    hidden(key)
    c, _uid = _account()
    zone = c.get("/command-center").get_data(as_text=True).split('class="cz"', 1)[1]
    assert 'href="/all-tools"' not in zone


def test_a_switched_off_page_is_no_room_s_door(hidden):
    """Statements off: Business's primary door and its help link go, the
    rest of the page stays. Smart Links off: Fans' Fan CRM tile (under
    /links) goes with it."""
    stmts = [k for _n, k, h, _l in page_switches.entries() if h == "/statements"][0]
    links = [k for _n, k, h, _l in page_switches.entries() if h == "/links"][0]
    hidden(stmts, links)
    c, _uid = _account("label")
    body = c.get("/room/business").get_data(as_text=True)
    main = body.split('id="sb-main"', 1)[1]
    assert "/statements?" not in main and 'href="/statements' not in main
    assert "This is switched off on this account for now." in main
    fans = c.get("/room/fans").get_data(as_text=True).split('id="sb-main"', 1)[1]
    assert 'href="/links/fans' not in fans and 'href="/links/new' not in fans


# ---- x-5: an Analytics action keeps Analytics off the brand-new page -------

def test_an_open_analytics_action_means_the_room_is_not_brand_new():
    """Analytics spec: brand-new only after confirming no Analytics
    actions. An action's "Open Analytics" door landed on a page that
    called the account brand-new."""
    import command_center as cc_mod
    c, uid = _account(None)          # the plan a sign-up gets, as the room's own tests
    zero = c.get("/room/analytics").get_data(as_text=True)
    assert "Connect your first source" in zero, "a fresh account: the page from zero"
    aid = cc_mod.create_action(uid, "Check the listener dip", room="analytics", priority="high")
    body = c.get("/room/analytics").get_data(as_text=True)
    assert "Connect your first source" not in body and "What is measured, by whom" in body
    # done, it no longer holds the room open
    assert cc_mod.set_action_status(aid, uid, "complete")
    assert "Connect your first source" in c.get("/room/analytics").get_data(as_text=True)

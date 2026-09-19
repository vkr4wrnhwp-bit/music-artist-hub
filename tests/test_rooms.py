"""The eight rooms (owner, 2026-09-15, by numbered mockup).

Command Center and Actions stay at the top; then Fans, Studio, Stage,
Analytics, Business, Publishing, Releases, Marketing; the account group
under them. A room's name opens its screen of cards, the chevron expands
it in place. No double tabs: a page that was a tab of another page is a
card of its own. Rooms are a layout over the hub definitions: same keys,
addresses, live flags and page switches. They are on when NAV_ROOMS=1 or
the owner switches them on in Settings; the hub sidebar is the default,
so every lock on it still holds.
"""
import re
import uuid

import pytest

import db as store
import hubs
import page_switches
import rooms
from app import create_app

PW = "rooms-12345"


def _client(app_obj, plan="pro"):
    c = app_obj.test_client()
    email = "rooms-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Rooms", "email": email, "password": PW})
    c.post("/plan/switch", data={"plan": plan})
    c._email = email
    return c


def _hubs(body):
    return re.findall(r'data-hub="([a-z-]+)"', body.split("</aside>")[0])


# test_the_signal_card_shows_only_to_a_login_that_holds_a_seat was removed
# on 2026-09-18: Signal left the Analytics room entirely (owner), so there
# is no card to gate. tests/test_signal_is_internal.py holds the new rule.
def test_every_sidebar_entry_and_every_folded_page_has_a_room():
    keys = {k for _r, _n, _p, ks in rooms.ROOMS for k in ks} | set(rooms.TOP_KEYS) | set(rooms.ACCOUNT_KEYS)
    for _hk, _name, _tag, items in hubs.HUBS:
        for it in items:
            assert it[0] in keys, it[0]
    for _g, items in (hubs.LABEL_GROUP, hubs.COMMUNITY_GROUP, hubs.ACCOUNT_GROUP):
        for it in items:
            if it[0] in ("inbox", "notifications"):
                continue                           # the corner marks
            assert it[0] in keys, it[0]
    # the unfolded pages are cards, each in exactly one room
    for key in ("contracts", "track-passports", "tax", "press-contacts", "fan-club", "deal-simulator"):
        assert rooms.room_for_key(key), key
    seen = [k for _r, _n, _p, ks in rooms.ROOMS for k in ks]
    assert len(seen) == len(set(seen)), "a card sits in one room only"
    assert [r[0] for r in rooms.ROOMS] == ["fans", "studio", "stage", "analytics", "business", "publishing", "releases", "marketing"]


def test_the_layout_is_off_by_default_and_on_by_flag_or_owner_choice(monkeypatch):
    monkeypatch.delenv("NAV_ROOMS", raising=False)
    app_obj = create_app()
    with app_obj.app_context():
        store.set_kv("nav_layout", "")
        assert rooms.enabled() is False
        monkeypatch.setenv("NAV_ROOMS", "1")
        assert rooms.enabled() is True
        store.set_kv("nav_layout", "hubs")
        assert rooms.enabled() is False, "the owner's choice wins over the environment"
        rooms.set_layout("rooms")
        assert rooms.enabled() is True
        store.set_kv("nav_layout", "")


def test_the_sidebar_shows_the_rooms_with_the_top_rows_and_the_account_group(monkeypatch):
    monkeypatch.setenv("NAV_ROOMS", "1")
    app_obj = create_app()
    with app_obj.app_context():
        store.set_kv("nav_layout", "")
    c = _client(app_obj, "label")
    body = c.get("/command-center").get_data(as_text=True)
    aside = body.split("</aside>")[0]
    assert _hubs(body) == ["fans", "studio", "stage", "analytics", "business", "publishing", "releases", "marketing", "account"]
    top = aside.split('id="sb-top-rows"')[1].split('<div class="room-row"')[0]
    assert re.findall(r'href="([^"]+)"', top) == ["/command-center", "/actions"]
    assert 'href="/room/stage"' in aside and 'aria-label="Expand Stage"' not in aside, "one row, one click, no dropdown"
    stage_row = aside.split('data-hub="stage"')[1].split("</div>")[0]
    assert 'href="/tours"' not in stage_row and "hub-items" not in stage_row
    assert 'data-hub="label"' not in aside, "no Label Services row"
    business = c.get("/room/business").get_data(as_text=True)
    assert 'data-room-card="services"' in business and 'data-room-card="roster"' in business, "a Label plan's pages sit in Business"
    account = aside.split('data-hub="account"')[1]
    assert 'href="/settings"' in account and 'href="/connections"' in account and 'href="/billing"' in account
    assert 'href="/inbox"' not in account and 'id="sb-corner-inbox"' in aside
    studio = c.get("/room/studio").get_data(as_text=True)
    assert 'href="/vault?view=contracts"' in studio, "no double tabs: Contracts is its own icon in the room"
    pro = _client(app_obj, "pro")
    b2 = pro.get("/room/business").get_data(as_text=True)
    assert 'data-room-card="services"' not in b2 and 'data-room-card="roster"' not in b2


def test_a_room_screen_is_one_grid_of_cards(monkeypatch):
    monkeypatch.setenv("NAV_ROOMS", "1")
    app_obj = create_app()
    with app_obj.app_context():
        store.set_kv("nav_layout", "")
    c = _client(app_obj, "pro")
    page = c.get("/room/stage").get_data(as_text=True)
    assert "Everything between the booking and the encore." in page
    cards = re.findall(r'data-room-card="([a-z-]+)"', page)
    assert cards[:3] == ["tours", "stage-plot", "lights"] and "tour-board" in cards and "passports" in cards
    assert 'data-hub="stage" data-room="1" data-active="1"' in page
    assert c.get("/room/nope").status_code == 404
    studio = c.get("/room/studio").get_data(as_text=True)
    assert 'data-room-card="vault"' in studio and 'data-room-card="contracts"' in studio
    assert ">Opens app<" in studio, "Motion is another app"
    # rooms answer even when the sidebar shows hubs: a link to one never dies
    monkeypatch.delenv("NAV_ROOMS", raising=False)
    assert c.get("/room/marketing").status_code == 200


def test_hidden_pages_leave_the_room_for_everybody_but_an_owner(monkeypatch):
    monkeypatch.setenv("NAV_ROOMS", "1")
    app_obj = create_app()
    owner = _client(app_obj, "pro")
    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    with app_obj.app_context():
        store.set_kv("nav_layout", "")
        page_switches.set_hidden({"press-desk"})
    try:
        page = owner.get("/room/marketing").get_data(as_text=True)
        assert 'data-room-card="press-desk"' in page and ">Hidden<" in page
        assert 'data-room-card="press-contacts"' in page, "a page under a hidden one is hidden too, and an owner still sees it"
        other = _client(app_obj, "pro")
        page = other.get("/room/marketing").get_data(as_text=True)
        assert 'data-room-card="press-desk"' not in page and 'data-room-card="press-contacts"' not in page
        assert 'data-room-card="links"' in page
    finally:
        with app_obj.app_context():
            page_switches.set_hidden(set())


def test_the_owner_switches_the_layout_in_settings(monkeypatch):
    monkeypatch.delenv("NAV_ROOMS", raising=False)
    app_obj = create_app()
    owner = _client(app_obj, "pro")
    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    with app_obj.app_context():
        store.set_kv("nav_layout", "")
    try:
        body = owner.get("/settings").get_data(as_text=True)
        assert 'action="/admin/nav-layout"' in body and 'value="hubs" class="accent-sb-gold" checked' in body
        r = owner.post("/admin/nav-layout", data={"layout": "rooms"})
        assert r.status_code == 302 and r.headers["Location"].endswith("nav=saved#nav-layout")
        body = owner.get("/settings?nav=saved").get_data(as_text=True)
        assert "Saved. The menu changed for everybody." in body
        assert _hubs(body)[:3] == ["fans", "studio", "stage"]
        stranger = _client(app_obj, "pro")
        assert stranger.post("/admin/nav-layout", data={"layout": "hubs"}).status_code == 404
        assert _hubs(stranger.get("/links").get_data(as_text=True))[:3] == ["fans", "studio", "stage"], "for everybody"
        owner.post("/admin/nav-layout", data={"layout": "hubs"})
        assert _hubs(owner.get("/links").get_data(as_text=True))[0] == "command"
    finally:
        with app_obj.app_context():
            store.set_kv("nav_layout", "")


def test_a_page_opened_from_a_room_offers_the_way_back(monkeypatch):
    monkeypatch.setenv("NAV_ROOMS", "1")
    app_obj = create_app()
    with app_obj.app_context():
        store.set_kv("nav_layout", "")
    c = _client(app_obj, "pro")
    body = c.get("/tours").get_data(as_text=True)
    assert 'id="sb-room-back"' in body and 'href="/room/stage"' in body and "Back to Stage" in body
    body = c.get("/vault?view=contracts").get_data(as_text=True)
    assert "Back to Studio" in body, "an unfolded page goes back to its parent's room"
    assert 'id="sb-room-back"' not in c.get("/room/stage").get_data(as_text=True), "a room screen is the top"
    assert 'id="sb-room-back"' not in c.get("/command-center").get_data(as_text=True), "the top rows have none"
    monkeypatch.delenv("NAV_ROOMS", raising=False)
    assert 'id="sb-room-back"' not in c.get("/tours").get_data(as_text=True), "hubs layout: no rooms, no way back"


def test_every_card_a_room_offers_opens_a_page_with_the_way_back(monkeypatch):
    """Audit, 2026-09-15: Fan Club, Audio Studio, Release check and
    Distribution opened with no way back; Fan CRM went back to Marketing;
    Mechanicals landed on Royalties in Business. Every in-app card of every
    room opens a page that carries the app frame and "Back to <its room>"."""
    monkeypatch.setenv("NAV_ROOMS", "1")
    app_obj = create_app()
    with app_obj.app_context():
        store.set_kv("nav_layout", "")
    c = _client(app_obj, "label")
    wrong = []
    for rkey, _name, _purpose, _icon, cards in rooms.build("label", False, False):
        for key, href, _i, _l, _d, state in cards:
            if state == "external":
                continue
            r = c.get(href)
            body = r.get_data(as_text=True)
            if r.status_code != 200 or 'id="sb-room-back"' not in body or 'href="/room/%s"' % rkey not in body:
                wrong.append((rkey, key, href, r.status_code))
    assert wrong == []
    assert 'id="sb-room-back"' in c.get("/vault?view=contracts").get_data(as_text=True)


def test_artist_accounts_keep_the_rooms_sidebar_on_the_fan_world_pages(monkeypatch):
    """Audit, 2026-09-15: /fans, /discover and /marketplace dropped the rooms
    and showed the fan-account menu; the Fans strip doubled the room's cards."""
    monkeypatch.setenv("NAV_ROOMS", "1")
    app_obj = create_app()
    with app_obj.app_context():
        store.set_kv("nav_layout", "")
    c = _client(app_obj, "label")
    for path in ("/fans", "/discover", "/marketplace"):
        body = c.get(path).get_data(as_text=True)
        aside = body.split("</aside>")[0]
        assert 'id="sb-top-rows"' in aside and 'data-hub="studio"' in aside, path
    for path in ("/fans", "/links/fans", "/fan-club", "/catalog?view=passports", "/vault?view=contracts"):
        body = c.get(path).get_data(as_text=True)
        assert 'class="sb-subnav"' not in body.split('id="sb-main"')[1], path
    fan = _client(app_obj, "fan")
    body = fan.get("/discover").get_data(as_text=True)
    assert 'id="sb-top-rows"' not in body and "Community" in body.split("</aside>")[0]


def test_billing_is_live_and_wears_no_sample_badge(monkeypatch):
    monkeypatch.setenv("NAV_ROOMS", "1")
    app_obj = create_app()
    with app_obj.app_context():
        store.set_kv("nav_layout", "")
    assert "billing" in hubs.live_keys()
    c = _client(app_obj, "pro")
    aside = c.get("/command-center").get_data(as_text=True).split("</aside>")[0]
    row = aside.split('href="/billing"')[1].split("</a>")[0]
    assert "Sample" not in row

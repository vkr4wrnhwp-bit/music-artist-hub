"""Every page live or hidden from the owner's Settings.

Owner, 2026-09-14: "can we do the toggles for the live version on
features not just read only?? but like hidden or live?" The rules:

  * only an owner sees the switchboard and can save it
  * a hidden page leaves the sidebar, the palette and the desk landing
    for everyone who is not an owner, and its address bounces them to
    the Command Center with a note; pages under it go with it
  * an owner keeps the entry, badged Hidden, and the page still opens
  * the Command Center and Settings can never be hidden
  * clearing the board shows everything again; a corrupt override hides
    nothing
"""
import uuid

import pytest

import db as store
import page_switches as ps
from app import create_app

PW = "switch-12345"


def _fresh(app_obj):
    client = app_obj.test_client()
    email = "sw-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Switch", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    client._email = email
    return client


@pytest.fixture
def world(monkeypatch):
    app_obj = create_app()
    owner, artist = _fresh(app_obj), _fresh(app_obj)
    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    with app_obj.app_context():
        ps.set_hidden([])
    yield app_obj, owner, artist
    with app_obj.app_context():
        ps.set_hidden([])


def _aside(client, path="/command-center"):
    return client.get(path).get_data(as_text=True).split("</aside>")[0]


def test_the_board_lists_every_entry_and_only_an_owner_may_save(world):
    app_obj, owner, artist = world
    assert 'id="page-switches"' not in artist.get("/settings").get_data(as_text=True)
    assert artist.post("/admin/pages", data={"live": ["links"]}).status_code == 404
    body = owner.get("/settings").get_data(as_text=True)
    assert 'id="page-switches"' in body
    for _n, key, _h, label in ps.entries():
        assert 'value="%s"' % key in body, key
    assert "Every page is live" in body


def test_a_hidden_page_leaves_the_menu_and_bounces_everyone_but_the_owner(world):
    app_obj, owner, artist = world
    assert 'href="/remix-lab"' in _aside(artist)
    live = [k for k in ps.known_keys() if k not in ("remix-lab", "links")]
    r = owner.post("/admin/pages", data={"live": live})
    assert r.status_code == 302 and "pages=saved" in r.headers["Location"]
    with app_obj.app_context():
        assert ps.hidden_keys() == {"remix-lab", "links"}

    aside = _aside(artist)
    assert 'href="/remix-lab"' not in aside and 'href="/links"' not in aside
    assert 'href="/statements"' in aside
    palette = artist.get("/command-center").get_data(as_text=True)
    assert '"key": "remix-lab"' not in palette and '"key":"remix-lab"' not in palette
    r = artist.get("/remix-lab")
    assert r.status_code == 302 and r.headers["Location"].startswith("/command-center?off=")
    r = artist.get("/links/new")
    assert r.status_code == 302 and "off=" in r.headers["Location"], "pages under a hidden entry go with it"
    assert artist.get("/royalty-recovery/cases").status_code == 200, "its own entry, not under /royalties"
    note = artist.get("/command-center?off=Remix%20Lab").get_data(as_text=True)
    assert "Remix Lab is switched off for now" in note
    landing = artist.get("/desk/studio").get_data(as_text=True)
    assert 'href="/remix-lab"' not in landing and 'href="/rack"' in landing

    # the owner keeps the entry, badged, and the page opens
    own = _aside(owner)
    assert 'href="/remix-lab"' in own and ">Hidden<" in own
    assert owner.get("/remix-lab").status_code == 200
    body = owner.get("/settings").get_data(as_text=True)
    assert "2 hidden" in body

    # everything back
    r = owner.post("/admin/pages", data={"live": sorted(ps.known_keys())})
    assert "pages=saved" in r.headers["Location"]
    assert 'href="/remix-lab"' in _aside(artist)
    assert artist.get("/remix-lab").status_code == 200


def test_the_shell_and_the_switch_can_never_be_hidden(world):
    app_obj, owner, artist = world
    owner.post("/admin/pages", data={"live": ["statements"]})
    with app_obj.app_context():
        hidden = ps.hidden_keys()
    assert "command-center" not in hidden and "settings" not in hidden
    assert "statements" not in hidden and "royalties" in hidden
    assert artist.get("/command-center").status_code == 200
    assert artist.get("/settings").status_code == 200
    aside = _aside(artist)
    assert 'href="/command-center"' in aside and 'href="/settings"' in aside


def test_a_corrupt_override_hides_nothing(world):
    app_obj, owner, artist = world
    with app_obj.app_context():
        store.set_kv(ps.KV_KEY, "{not json")
        assert ps.hidden_keys() == set()
        store.set_kv(ps.KV_KEY, '{"hidden": "links"}')
        assert ps.hidden_keys() == set()
    assert 'href="/links"' in _aside(artist)


def test_the_longest_address_wins():
    hidden = {"royalties"}
    assert ps.hidden_for_path("/royalties", hidden)["key"] == "royalties"
    assert ps.hidden_for_path("/royalties?period=JUN-26".split("?")[0], hidden)
    assert ps.hidden_for_path("/royalty-recovery/cases", hidden) is None
    assert ps.hidden_for_path("/royalty-recovery/cases", {"cases"})["label"] == "Recovery Cases"
    assert ps.hidden_for_path("/fingerprints/", {"fingerprints"})
    assert ps.hidden_for_path("/", {"links"}) is None
    assert ps.hidden_for_path("/links/fans", {"links"})["key"] == "links"

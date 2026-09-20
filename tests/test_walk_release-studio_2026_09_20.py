"""The Release Studio findings of the 2026-09-20 page walk, pinned.

A read-only agent walked Release Autopilot, the track passport, Smart
Links and the Studio room as a signed-in artist. What it found was a
desk that scored itself on rows it had created rather than on work the
artist had done: a rollout lamp lit by an empty rollout, a Clean Release
tick for a reminder that does not exist and another for assets nobody
uploaded, a "fix" button that left the field it was fixing, a nameless
campaign the editor was happy to save, and a shared /go/ link that kept
redirecting and counting after the campaign came down.
"""
import re
import uuid

import pytest

import app as appmod
import artist_os
import db as store
import links_store as mls
import rollout_store as ros

PW = "walk-release-pw-1234"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("NAV_ROOMS", "1")


def _account(name="Walk Artist", plan="label"):
    email = "relwalk-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _campaign(client, title="Walk Track One", **extra):
    data = {"title": title, "artist_name": "Walk Artist",
            "dest_spotify": "https://open.spotify.com/track/abc"}
    data.update(extra)
    r = client.post("/links/new", data=data)
    assert r.status_code == 302
    return r.headers["Location"].split("/")[2]


def _clean_state(body, label):
    """The colour of one Clean Release row on the track page."""
    m = re.search(r'<span class="text-(green|red|amber)-400">[^<]*</span>\s*'
                  + re.escape(label), body)
    return m.group(1) if m else None


# --- Release Autopilot ---------------------------------------------------


def test_the_rollout_lamp_waits_for_a_post_with_a_date():
    client, _uid = _account()
    cid = _campaign(client)
    r = client.post("/rollout-studio/new",
                    data={"title": "Walk Track One", "ml_campaign_id": cid,
                          "pf_tiktok": "1", "rollout_length": "14"})
    rid = r.headers["Location"].rsplit("/", 1)[-1]
    assert ros.list_posts(rid) == []

    body = client.get("/releases/autopilot?campaign=%s" % cid).get_data(as_text=True)
    # Open, not done, and the way out is the rollout that exists.
    assert '<span class="rd-check-name">Rollout scheduled</span>' in body
    assert '<span class="sb-lamp sb-lamp--on">Rollout scheduled</span>' not in body
    assert "/rollout-studio/%s" % rid in body

    client.post("/rollout-studio/%s/generate" % rid)
    posts = ros.list_posts(rid)
    assert posts and all(p["scheduled_date"] for p in posts)
    body = client.get("/releases/autopilot?campaign=%s" % cid).get_data(as_text=True)
    assert '<span class="sb-lamp sb-lamp--on">Rollout scheduled</span>' in body


def test_the_isrc_row_points_at_the_passport_once_the_track_is_in_the_catalog():
    client, uid = _account()
    cid = _campaign(client)
    body = client.get("/releases/autopilot?campaign=%s" % cid).get_data(as_text=True)
    assert "Add the track to your catalog so identifiers auto-pull." in body

    store.add_catalog_track(uid, {"title": "Walk Track One", "artist": "Walk Artist"})
    row = [t for t in store.get_catalog_tracks(uid) if t["title"] == "Walk Track One"][0]
    pid = row["passport_track_id"]
    assert pid
    body = client.get("/releases/autopilot?campaign=%s" % cid).get_data(as_text=True)
    assert "Add the ISRC on the track passport." in body
    assert "/tracks/%s#passport" % pid in body
    assert "Add the track to your catalog so identifiers auto-pull." not in body

    client.post("/tracks/%s/passport" % pid, data={"isrc": "USABC2600001"})
    body = client.get("/releases/autopilot?campaign=%s" % cid).get_data(as_text=True)
    assert '<span class="sb-lamp sb-lamp--on">ISRC on catalog track</span>' in body


def test_the_autopilot_foot_says_what_is_checked_today():
    client, _uid = _account()
    cid = _campaign(client)
    body = client.get("/releases/autopilot?campaign=%s" % cid).get_data(as_text=True)
    assert "arrive with the Deal Room and Metadata Passport modules" not in body
    assert "Lockbox sign-off" in body
    assert "Content ID are not checked here" in body
    # Both modules the old sentence promised are already open pages.
    assert client.get("/deal-room").status_code == 200
    assert client.get("/metadata-passport").status_code in (200, 302)


# --- Clean Release on the track passport ---------------------------------


def test_clean_release_drops_the_reminder_that_does_not_exist():
    labels = [i["label"] for i in
              artist_os.clean_release(
                  {"id": "t", "title": "T", "passport": {}, "lockbox": {}},
                  {"live_links": 0, "fans": 0, "rollout_assets": False})["items"]]
    assert not any("pitch reminder" in l for l in labels)
    assert len(labels) == len(set(labels)) == 16


def test_social_assets_stay_yellow_until_a_file_is_on_the_rollout():
    client, uid = _account()
    client.post("/tracks/add", data={"title": "Walk Track One"})
    tid = [t for t in store.list_os_tracks(uid)][0]["id"]
    cid = _campaign(client)
    r = client.post("/rollout-studio/new",
                    data={"title": "Walk Track One", "ml_campaign_id": cid,
                          "pf_tiktok": "1", "rollout_length": "14"})
    rid = r.headers["Location"].rsplit("/", 1)[-1]
    assert ros.list_assets(rid) == []

    body = client.get("/tracks/%s" % tid).get_data(as_text=True)
    assert "Spotify pitch reminder set" not in body
    assert _clean_state(body, "Social assets prepared") == "amber"

    ros.add_asset(rid, "lyrics", lyrics_text="a line the artist wrote")
    body = client.get("/tracks/%s" % tid).get_data(as_text=True)
    assert _clean_state(body, "Social assets prepared") == "green"


def test_a_passport_fix_button_never_leaves_the_field_it_fixes():
    gone = {"/publishing", "/mechanicals", "/neighboring-rights"}
    assert not [f for _k, _l, _c, f in artist_os.PASSPORT_FIELDS if f in gone]

    client, uid = _account()
    client.post("/tracks/add", data={"title": "Walk Track One"})
    tid = [t for t in store.list_os_tracks(uid)][0]["id"]
    body = client.get("/tracks/%s" % tid).get_data(as_text=True)
    for href in gone:
        assert 'href="%s"' % href not in body
    # The passport form is still the anchor the rest of the desk points at.
    assert 'id="passport"' in body


# --- Smart Links ---------------------------------------------------------


def test_the_links_tiles_count_this_accounts_own_links():
    client, uid = _account()
    cid = _campaign(client)
    client.post("/links/%s/publish" % cid)
    slug = mls.get_campaign(cid)["slug"]
    dest = mls.get_destinations(cid)[0]["id"]
    anon = appmod.app.test_client()
    for _ in range(3):
        anon.get("/l/%s/go/%s" % (slug, dest))
    assert mls.event_counts(cid)["service_click"] == 3

    body = client.get("/links").get_data(as_text=True)
    assert '<div id="kpi-links" class="mt-2 text-2xl font-bold tabular-nums text-sb-ink">1</div>' in body
    assert '<div id="kpi-clicks" class="mt-2 text-2xl font-bold tabular-nums">3</div>' in body
    assert "Walk Track One" in body
    # One list on the page: no second builder saying the account is empty.
    assert "No smart links yet" not in body


def test_editing_refuses_an_empty_title_the_way_creating_does():
    client, _uid = _account()
    cid = _campaign(client)
    r = client.post("/links/%s/edit" % cid,
                    data={"title": "", "artist_name": "Walk Artist"})
    assert r.status_code == 200
    assert "A campaign title is required." in r.get_data(as_text=True)
    assert mls.get_campaign(cid)["title"] == "Walk Track One"


def test_a_destination_link_stops_working_when_the_campaign_comes_down():
    client, uid = _account()
    cid = _campaign(client)
    client.post("/links/%s/publish" % cid)
    slug = mls.get_campaign(cid)["slug"]
    dest = mls.get_destinations(cid)[0]["id"]
    anon = appmod.app.test_client()
    assert anon.get("/l/%s/go/%s" % (slug, dest)).status_code == 302
    counted = mls.event_counts(cid)["service_click"]
    assert counted == 1

    client.post("/links/%s/unpublish" % cid)
    assert anon.get("/l/%s" % slug).status_code == 404
    assert anon.get("/l/%s/go/%s" % (slug, dest)).status_code == 404
    assert mls.event_counts(cid)["service_click"] == counted
    # The owner can still walk their own draft, and it is not a click.
    assert client.get("/l/%s/go/%s" % (slug, dest)).status_code == 302
    assert mls.event_counts(cid)["service_click"] == counted

    client.post("/links/%s/archive" % cid)
    assert anon.get("/l/%s" % slug).status_code == 410
    assert anon.get("/l/%s/go/%s" % (slug, dest)).status_code == 410
    assert mls.event_counts(cid)["service_click"] == counted


# --- The Studio room -----------------------------------------------------


def test_the_studio_room_and_the_page_inside_it_have_different_names():
    client, _uid = _account()
    room = client.get("/room/studio").get_data(as_text=True)
    page = client.get("/studio").get_data(as_text=True)
    assert "<title>Studio - Street Banker</title>" in room
    assert "<title>Mix Check - Street Banker</title>" in page
    assert "<title>Studio - Street Banker</title>" not in page
    # The card the room offers and the tab it opens now say the same thing.
    assert "Mix Check" in room

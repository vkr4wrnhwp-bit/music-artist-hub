"""Release Autopilot absorbed Clean Release.

Both pages rendered the same twelve derived checks against the same
campaign, through the same include, and then each added its own half:
Autopilot the arc, plan and kit; Clean Release the checks grouped, the
passport pulls and the per-track score. A person setting up a release
opened both and read the checklist twice. Now there is one desk.

What these tests hold: the old URL forwards and keeps the campaign, the
inbox and certificate still land somewhere, nothing in the nav or the
templates points at the folded page, and both halves render on the one
page — as instruments where the value is real.
"""
import io
import os
import re
import uuid

import pytest

import app as appmod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "release-desk-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def artist(application):
    """A fresh account with one dated campaign and one Track Passport that
    matches a catalog record — enough for both halves of the desk."""
    import db as store
    import links_store as mls
    from datetime import date, timedelta

    email = "rd-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Desk Tester", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        uid = store.get_user_by_email(email)["id"]
        soon = (date.today() + timedelta(days=10)).isoformat()
        cid = mls.create_campaign(uid, "rd-%s" % uuid.uuid4().hex[:6],
                                  {"title": "Desk Drop", "release_date": soon})
        tid = store.add_os_track(uid, "Desk Drop", "Desk EP", soon)
        store.update_os_track_passport(uid, tid, {"isrc": "USSB12600042"})
        ctid = store.add_catalog_track(uid, {"title": "Desk Drop",
                                             "artist": "Desk Tester"})
    return {"client": client, "uid": uid, "campaign": cid,
            "track": tid, "catalog": ctid}


# --- the old door ------------------------------------------------------------

def test_the_old_url_forwards_and_keeps_the_campaign(artist):
    r = artist["client"].get("/releases/clean-release?campaign=%s"
                             % artist["campaign"])
    assert r.status_code == 302
    assert r.headers["Location"].endswith(
        "/releases/autopilot?campaign=%s#clean" % artist["campaign"])


def test_the_old_url_without_a_campaign_still_lands_on_the_clean_half(artist):
    r = artist["client"].get("/releases/clean-release")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/releases/autopilot#clean")


def test_a_stranger_at_the_old_url_meets_the_login_not_the_desk(application):
    r = application.test_client().get("/releases/clean-release")
    assert r.status_code == 302
    assert "/releases/autopilot" not in r.headers["Location"]


def test_nothing_points_at_the_folded_page_any_more():
    """The nav, the palette, the command centre and every template. One
    stale link and the fold is a second door to the same room."""
    import glob

    import command_center
    import hubs

    keys = {k for _hk, _n, _t, items in hubs.HUBS for k, *_ in items}
    assert "clean-release" not in keys
    assert "clean-release" not in hubs.LIVE_KEYS
    assert not [m for m in command_center.MODULES
                if m[0] == "/releases/clean-release"]
    stale = []
    for p in glob.glob(os.path.join(HERE, "templates", "**", "*.html"),
                       recursive=True):
        if "/releases/clean-release" in io.open(p, encoding="utf-8").read():
            stale.append(os.path.basename(p))
    assert stale == [], stale
    assert not os.path.exists(os.path.join(HERE, "templates", "clean_release.html"))
    assert not os.path.exists(os.path.join(HERE, "templates", "_release_checks.html"))


# --- one desk, both halves ---------------------------------------------------

def test_both_halves_render_on_the_one_page(artist):
    body = artist["client"].get("/releases/autopilot?campaign=%s"
                                % artist["campaign"]).get_data(as_text=True)
    # Autopilot's half.
    assert "Autopilot Timeline" in body and "Campaign Plan" in body
    assert "Release Kit" in body and "Export full kit" in body
    # Clean Release's half.
    assert "Track Passports · Clean Release" in body
    assert "Resolve from Track Passport" in body and "USSB12600042" in body
    assert "Desk Drop" in body


def test_the_checks_are_grouped_into_meters_with_real_counts(artist):
    """The five groups of the release path, each a meter reading done/total
    from the checks themselves — not a dial fed by a percentage."""
    body = artist["client"].get("/releases/autopilot?campaign=%s"
                                % artist["campaign"]).get_data(as_text=True)
    for group in ("Release assets", "Metadata", "Distribution",
                  "Fans &amp; rights", "Rollout"):
        assert group in body, group
    # A dated campaign with nothing else: release assets is 1 of 3
    # (date set; cover and press kit open).
    assert 'aria-label="Release assets: 1/3"' in body


def test_only_open_checks_are_listed_and_each_has_a_way_out(artist):
    body = artist["client"].get("/releases/autopilot?campaign=%s"
                                % artist["campaign"]).get_data(as_text=True)
    # An open check: named, explained, with Fix and Create action.
    assert "Cover art set" in body and "Create action" in body
    assert body.count('class="rd-check"') == body.count("Create action")
    # A passed check is counted and folded away, not listed as open.
    assert "Release date set" in body
    assert "1 done" in body
    assert 'class="sb-lamp sb-lamp--on">Release date set' in body


def test_the_strip_reads_real_numbers(artist):
    body = artist["client"].get("/releases/autopilot?campaign=%s"
                                % artist["campaign"]).get_data(as_text=True)
    assert "days to release" in body
    assert "ready</span>" in body
    assert "open items" in body or "open item" in body


def test_the_arc_uses_the_shared_stage_rail(artist):
    body = artist["client"].get("/releases/autopilot?campaign=%s"
                                % artist["campaign"]).get_data(as_text=True)
    assert 'aria-current="step"' in body
    assert "sb-stages-i--now" in body
    # Ten days out is Pitch; Intake, Clean-up and Pre-save are behind.
    assert re.search(r'sb-stages-i--now[^>]*>\s*Pitch', body)
    assert body.count("sb-stages-i--done") == 3


def test_the_plan_length_is_a_switch(artist):
    body = artist["client"].get("/releases/autopilot?campaign=%s&days=30"
                                % artist["campaign"]).get_data(as_text=True)
    assert 'role="radiogroup"' in body
    assert 'value="30" checked' in body
    assert "30 days out" in body


def test_the_per_track_score_is_a_meter_and_a_block_is_a_word(artist):
    body = artist["client"].get("/releases/autopilot").get_data(as_text=True)
    assert re.search(r'aria-label="Desk Drop: \d+/100"', body)
    # A fresh passport has red critical items: blocked, in a word.
    assert "sb-lamp--crit\">Blocked" in body


def test_the_clean_half_is_there_even_before_any_campaign_exists(application):
    """The per-track score belongs to the passport, not to a campaign."""
    import db as store

    email = "rd-empty-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Empty", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        uid = store.get_user_by_email(email)["id"]
        store.add_os_track(uid, "Lonely Track", "", "")
    body = client.get("/releases/autopilot").get_data(as_text=True)
    assert "No releases yet" in body
    assert "Track Passports · Clean Release" in body and "Lonely Track" in body
    assert "Campaign Plan" not in body


# --- the things that used to live on the other page still work ----------------

def test_the_passport_pull_still_writes_the_catalog_and_comes_back_here(artist):
    import db as store

    r = artist["client"].post("/clean-release/resolve",
                              data={"catalog_id": artist["catalog"]})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/releases/autopilot#clean")
    with artist["client"].application.app_context():
        ct = [t for t in store.get_catalog_tracks(artist["uid"])
              if t["id"] == artist["catalog"]][0]
    assert ct["meta"]["isrc"] == "USSB12600042"


def test_the_release_risk_ping_points_at_the_desk(artist):
    import db as store

    artist["client"].get("/releases/autopilot")
    with artist["client"].application.app_context():
        pings = [n for n in store.list_notifications(artist["uid"])
                 if n["kind"] == "release_risk"]
    assert len(pings) == 1
    assert pings[0]["link"] == "/releases/autopilot#clean"


def test_an_unearned_certificate_comes_back_to_the_desk(artist):
    r = artist["client"].get("/tracks/%s/certificate" % artist["track"])
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/releases/autopilot#clean")


# --- the sheet ----------------------------------------------------------------

def test_the_desk_sheet_is_hand_written_and_cache_busted():
    css = io.open(os.path.join(HERE, "static", "css", "release-desk.css"),
                  encoding="utf-8").read()
    assert ".rd-strip {" in css and ".rd-check {" in css
    page = io.open(os.path.join(HERE, "templates", "release_autopilot.html"),
                   encoding="utf-8").read()
    assert "release-desk.css?v=" in page
    sw = io.open(os.path.join(HERE, "static", "js", "sw.js"),
                 encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 176

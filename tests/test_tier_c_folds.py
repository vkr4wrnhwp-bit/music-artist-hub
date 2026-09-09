"""Tier C, merged underneath (2026-09-09).

The three pairs were already tabs of one page; the data behind them was
still two tables each. These hold the merges: one song list under
Catalog + Track Passports, one file store under Vault + Contracts, one
page shell under Releases + Calendar. Every old URL still answers, as a
redirect; nothing is deleted by a start-up migration.
"""
import json
import os
import uuid

import pytest

import app as appmod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "tierc-tests-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def artist(application):
    import db as store

    email = "tierc-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Tier C", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})
    with application.app_context():
        uid = store.get_user_by_email(email)["id"]
    return {"client": client, "uid": uid}


# --- Merge 1: Track Passports into Catalog -------------------------------------

def test_the_track_list_forwards_to_the_catalog_section(artist):
    r = artist["client"].get("/tracks")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/catalog#passports")
    r = appmod.app.test_client().get("/tracks")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_an_artist_plan_account_keeps_its_passports_at_the_old_door(application):
    """Catalog is a Pro page and plans.py is left alone, so the redirect
    would put an Artist account in front of an upgrade card. For that
    plan the same section renders at /tracks - one list, two doors."""
    import db as store
    email = "tierc-artist-%s@example.net" % uuid.uuid4().hex[:8]
    c = application.test_client()
    c.post("/signup", data={"name": "Artist Plan", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    r = c.get("/tracks")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'id="passports"' in body and "Import CSV catalog" in body
    r = c.post("/tracks/add", data={"title": "Artist Door"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/tracks")
    uid = store.get_user_by_email(email)["id"]
    assert [t for t in store.get_catalog_tracks(uid) if t["title"] == "Artist Door"]
    assert c.get("/catalog").status_code == 402          # still the Pro page


def test_a_song_added_from_the_passport_form_is_one_catalog_row(artist):
    import db as store
    c = artist["client"]
    c.post("/tracks/add", data={"title": "One List", "release_title": "One EP",
                                "release_date": "2027-01-08"})
    cats = [t for t in store.get_catalog_tracks(artist["uid"]) if t["title"] == "One List"]
    osts = [t for t in store.list_os_tracks(artist["uid"]) if t["title"] == "One List"]
    assert len(cats) == 1 and len(osts) == 1
    assert cats[0]["passport_track_id"] == osts[0]["id"]
    assert osts[0]["catalog_track_id"] == cats[0]["id"]
    assert osts[0]["release_title"] == "One EP" and osts[0]["release_date"] == "2027-01-08"
    body = c.get("/catalog").get_data(as_text=True)
    assert body.count('href="/tracks/%s"' % osts[0]["id"]) >= 1
    assert body.count(">One List<") + body.count(">One List") >= 1
    # Once in the passports section: one row, one "Open passport".
    section = body.split('id="passports"')[1].split("</section>")[0]
    assert section.count("Open passport") == 1
    # Adding the same title again from the passport form does not open a
    # second passport - the song already has one.
    c.post("/tracks/add", data={"title": "One List"})
    assert len([t for t in store.list_os_tracks(artist["uid"]) if t["title"] == "One List"]) == 1


def test_a_song_saved_to_the_catalog_gets_a_passport_with_its_codes(artist):
    import db as store
    c = artist["client"]
    r = c.post("/catalog/add", json={"title": "Coded Drop", "artist": "Tier C"})
    cid = r.get_json()["id"]
    store.set_catalog_track_meta(artist["uid"], cid, {"isrc": "USSB12600101",
                                                     "upc": "198000000101",
                                                     "label": "Tier C Records"})
    ct = [t for t in store.get_catalog_tracks(artist["uid"]) if t["id"] == cid][0]
    passport = store.get_os_track(artist["uid"], ct["passport_track_id"])
    assert passport is not None and passport["title"] == "Coded Drop"
    assert passport["passport"]["artist_name"] == "Tier C"
    assert passport["passport"]["isrc"] == "USSB12600101"
    assert passport["passport"]["label"] == "Tier C Records"
    # A code the artist typed on the passport is a decision; a lookup
    # never overwrites it.
    store.update_os_track_passport(artist["uid"], passport["id"],
                                   dict(passport["passport"], isrc="USSB12600999"))
    store.set_catalog_track_meta(artist["uid"], cid, {"isrc": "USSB12600101"})
    assert store.get_os_track(artist["uid"], passport["id"])["passport"]["isrc"] == "USSB12600999"
    body = c.get("/catalog").get_data(as_text=True)
    section = body.split('id="passports"')[1].split("</section>")[0]
    assert "Coded Drop" in section and "USSB12600999" in section
    assert "MLC not checked" in section


def test_a_passport_first_song_is_claimed_by_the_catalog_save(artist):
    """The old two-call pattern: passport opened, then the same title saved
    from Discover with an artist. One row, not two."""
    import db as store
    c = artist["client"]
    c.post("/tracks/add", data={"title": "Claimed Song"})
    r = c.post("/catalog/add", json={"title": "Claimed Song", "artist": "Tier C"})
    assert r.status_code == 200 and r.get_json()["ok"]
    cats = [t for t in store.get_catalog_tracks(artist["uid"]) if t["title"] == "Claimed Song"]
    assert len(cats) == 1 and cats[0]["artist"] == "Tier C"
    osts = [t for t in store.list_os_tracks(artist["uid"]) if t["title"] == "Claimed Song"]
    assert len(osts) == 1 and osts[0]["passport"]["artist_name"] == "Tier C"
    assert cats[0]["passport_track_id"] == osts[0]["id"]
    # And a second save of the same title + artist is still a duplicate.
    assert c.post("/catalog/add", json={"title": "Claimed Song", "artist": "Tier C"}).status_code == 409


def test_removing_from_either_side_removes_the_song(artist):
    import db as store
    c = artist["client"]
    c.post("/tracks/add", data={"title": "Gone One"})
    ost = [t for t in store.list_os_tracks(artist["uid"]) if t["title"] == "Gone One"][0]
    assert c.post("/catalog/remove/" + ost["catalog_track_id"]).get_json()["ok"]
    assert store.get_os_track(artist["uid"], ost["id"]) is None
    assert not [t for t in store.get_catalog_tracks(artist["uid"]) if t["title"] == "Gone One"]
    c.post("/catalog/add", json={"title": "Gone Two", "artist": "Tier C"})
    ct = [t for t in store.get_catalog_tracks(artist["uid"]) if t["title"] == "Gone Two"][0]
    r = c.post("/tracks/%s/delete" % ct["passport_track_id"])
    assert r.status_code == 302 and r.headers["Location"].endswith("/catalog#passports")
    assert not [t for t in store.get_catalog_tracks(artist["uid"]) if t["title"] == "Gone Two"]


def test_the_startup_link_joins_rows_from_before_the_merge(artist):
    """Rows written the old way - no link either side - are joined on the
    next start: by ISRC first, then by title, else each side gets the
    row it lacked. Nothing is deleted."""
    import db as store
    uid = artist["uid"]
    now = "2026-01-01T00:00:00"
    with store.get_db() as db:
        # A catalog row and a passport that share an ISRC but not a title.
        db.execute("INSERT INTO catalog_tracks (id, user_id, title, artist, added, meta)"
                   " VALUES (?,?,?,?,?,?)", ("c-isrc", uid, "Old Title", "Tier C", now,
                                             json.dumps({"isrc": "USSB12600555"})))
        db.execute("INSERT INTO os_tracks (id, user_id, title, passport, created)"
                   " VALUES (?,?,?,?,?)", ("o-isrc", uid, "New Title",
                                           json.dumps({"isrc": "USSB12600555"}), now))
        # A pair that share only a title.
        db.execute("INSERT INTO catalog_tracks (id, user_id, title, artist, added)"
                   " VALUES (?,?,?,?,?)", ("c-title", uid, "same  name", "Tier C", now))
        db.execute("INSERT INTO os_tracks (id, user_id, title, passport, created)"
                   " VALUES (?,?,?,?,?)", ("o-title", uid, "Same Name", "{}", now))
        # A passport alone, and a catalog row alone.
        db.execute("INSERT INTO os_tracks (id, user_id, title, passport, created)"
                   " VALUES (?,?,?,?,?)", ("o-alone", uid, "Passport Only",
                                           json.dumps({"artist_name": "Tier C"}), now))
        db.execute("INSERT INTO catalog_tracks (id, user_id, title, artist, added, meta)"
                   " VALUES (?,?,?,?,?,?)", ("c-alone", uid, "Catalog Only", "Tier C", now,
                                             json.dumps({"isrc": "USSB12600556", "upc": "1"})))
    before_c = len(store.get_catalog_tracks(uid))
    before_o = len(store.list_os_tracks(uid))
    store.link_song_tables()
    cats = {t["id"]: t for t in store.get_catalog_tracks(uid)}
    osts = {t["id"]: t for t in store.list_os_tracks(uid)}
    assert cats["c-isrc"]["passport_track_id"] == "o-isrc"
    assert osts["o-isrc"]["catalog_track_id"] == "c-isrc"
    assert cats["c-title"]["passport_track_id"] == "o-title"
    assert osts["o-title"]["catalog_track_id"] == "c-title"
    # Each lone row got its other half, carrying what it knew.
    made_c = cats[osts["o-alone"]["catalog_track_id"]]
    assert made_c["title"] == "Passport Only" and made_c["artist"] == "Tier C"
    made_o = osts[cats["c-alone"]["passport_track_id"]]
    assert made_o["title"] == "Catalog Only"
    assert made_o["passport"]["isrc"] == "USSB12600556" and made_o["passport"]["upc"] == "1"
    assert len(cats) == before_c + 1 and len(osts) == before_o + 1
    # Idempotent: a second start changes nothing.
    store.link_song_tables()
    assert len(store.get_catalog_tracks(uid)) == before_c + 1
    assert len(store.list_os_tracks(uid)) == before_o + 1
    # The catalog lists each of them once.
    section = artist["client"].get("/catalog").get_data(as_text=True).split('id="passports"')[1].split("</section>")[0]
    for title in ("New Title", "Same Name", "Passport Only", "Catalog Only"):
        assert section.count(">" + title) == 1, title


# --- Merge 2: Release Scheduler into Release Autopilot ------------------------

def test_the_scheduler_forwards_into_the_desk_and_keeps_its_arguments(artist):
    c = artist["client"]
    r = c.get("/releases")
    assert r.status_code == 302 and r.headers["Location"].endswith("/releases/autopilot#calendar")
    r = c.get("/releases?preset=blitz")
    assert r.headers["Location"].endswith("/releases/autopilot?preset=blitz#calendar")
    assert appmod.app.test_client().get("/releases").status_code == 302   # login wall


def test_the_calendar_renders_inside_the_desk_with_the_campaign_kept(artist):
    import links_store as mls
    from datetime import date, timedelta
    c = artist["client"]
    soon = (date.today() + timedelta(days=30)).isoformat()
    cid = mls.create_campaign(artist["uid"], "cal-%s" % uuid.uuid4().hex[:6],
                              {"title": "Calendar Kept", "release_date": soon})
    body = c.get("/releases/autopilot?campaign=%s&days=30&preset=standard" % cid).get_data(as_text=True)
    assert 'id="calendar"' in body and "Release Scheduler" in body
    assert "Calendar Kept" in body and "Foundation" in body
    # Preset links carry the desk's own arguments, and the .ics link its URL.
    assert 'href="/releases/autopilot?campaign=%s&amp;days=30&amp;preset=blitz#calendar"' % cid in body
    assert 'href="/releases/autopilot?campaign=%s&amp;days=30#calendar"' % cid in body
    assert 'href="/releases/calendar.ics?preset=standard"' in body
    ics = c.get("/releases/calendar.ics?preset=standard")
    assert ics.status_code == 200 and "Calendar Kept" in ics.get_data(as_text=True)
    # One shell: the strip lights the desk, and the calendar tab points at the section.
    assert 'href="/releases/autopilot#calendar"' in body

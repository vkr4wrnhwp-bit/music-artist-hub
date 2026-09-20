"""The Rights Conflict Center reads the account's own passports.

Owner, 2026-09-20: "I would like to get it to compute." The page rendered
royalty_data.get_rights_conflicts, which reads five invented demo songs,
so every real account was told its ownership data was clean whatever its
catalogue held (walk, 2026-09-20).

A conflict here is two of the account's own records disagreeing, or a
right somebody else holds inside one of them. Nothing comes from outside
the account, nothing is estimated, and an account with no passports is
never called clean.
"""
import uuid

import pytest

import app as appmod
import db as store
import rights_conflicts as rc

PW = "conflict-test-pw-1234"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")


def _account():
    email = "conflicts-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Conflict Artist", "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, "label")
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _track(uid, title, passport=None, lockbox=None, release_title=""):
    tid = store.add_os_track(uid, title, release_title=release_title)
    if passport:
        store.update_os_track_passport(uid, tid, passport)
    if lockbox:
        store.update_os_track_lockbox(uid, tid, lockbox)
    return tid


def _titles(found):
    return {c["title"] for c in found}


def _kinds(found):
    return {c["conflict_type"] for c in found}


# --- the engine, on its own -------------------------------------------------

def test_an_empty_catalogue_finds_nothing_and_is_not_called_clean():
    assert rc.for_account([]) == []
    assert rc.summary([])["checked"] == 0


def test_one_isrc_on_two_recordings_is_a_conflict():
    tracks = [
        {"id": "a", "title": "Night Drive", "passport": {"isrc": "USABC1234567"}},
        {"id": "b", "title": "Night Drive (Live)", "passport": {"isrc": "usabc1234567"}},
    ]
    found = rc.for_account(tracks)
    assert "Duplicate identifier" in _kinds(found)
    conflict = next(c for c in found if c["conflict_type"] == "Duplicate identifier")
    assert conflict["severity"] == rc.HIGH
    assert set(conflict["songs_involved"]) == {"Night Drive", "Night Drive (Live)"}


def test_one_upc_across_two_releases_is_a_conflict_but_not_within_one():
    same_release = [
        {"id": "a", "title": "One", "release_title": "The EP", "passport": {"upc": "0123456789012"}},
        {"id": "b", "title": "Two", "release_title": "The EP", "passport": {"upc": "0123456789012"}},
    ]
    assert not [c for c in rc.for_account(same_release) if "UPC" in c["title"]]
    two_releases = [
        {"id": "a", "title": "One", "release_title": "The EP", "passport": {"upc": "0123456789012"}},
        {"id": "b", "title": "Two", "release_title": "The Album", "passport": {"upc": "0123456789012"}},
    ]
    assert [c for c in rc.for_account(two_releases) if "UPC" in c["title"]]


def test_two_passports_for_one_song_naming_different_owners():
    tracks = [
        {"id": "a", "title": "Same Song", "passport": {"master_owner": "The artist"}},
        {"id": "b", "title": "same song", "passport": {"master_owner": "Pissblood Records"}},
    ]
    found = rc.for_account(tracks)
    assert "Ownership disagreement" in _kinds(found)
    assert any("The artist" in c["description"] and "Pissblood Records" in c["description"]
               for c in found)


def test_writer_credits_that_differ_only_in_order_do_not_disagree():
    tracks = [
        {"id": "a", "title": "Same Song", "passport": {"songwriters": "Ann Lee, Bo Tran"}},
        {"id": "b", "title": "Same Song", "passport": {"songwriters": "bo tran; ann lee"}},
    ]
    assert not [c for c in rc.for_account(tracks)
                if c["conflict_type"] == "Ownership disagreement"]


def test_a_clearance_answered_no_is_a_conflict_and_a_blank_one_is_not():
    answered_no = [{"id": "a", "title": "Sampled", "passport": {"sample_clearance": "no"}}]
    found = rc.for_account(answered_no)
    assert "Unresolved clearance" in _kinds(found)
    blank = [{"id": "a", "title": "Sampled", "passport": {"sample_clearance": ""}}]
    assert not rc.for_account(blank), "a blank field is work to do, not a conflict"


def test_a_document_on_file_settles_a_clearance():
    tracks = [{"id": "a", "title": "Sampled",
               "passport": {"sample_clearance": "no"},
               "lockbox": {"sample_clearance": "yes"}}]
    assert not rc.for_account(tracks)


def test_several_writers_and_no_split_sheet():
    tracks = [{"id": "a", "title": "Co-write", "passport": {"songwriters": "Ann Lee, Bo Tran"}}]
    found = rc.for_account(tracks)
    assert "Splits not agreed" in _kinds(found)
    signed = [{"id": "a", "title": "Co-write",
               "passport": {"songwriters": "Ann Lee, Bo Tran", "split_sheet_status": "signed"}}]
    assert not rc.for_account(signed)
    alone = [{"id": "a", "title": "Solo", "passport": {"songwriters": "Ann Lee"}}]
    assert not rc.for_account(alone), "one writer has nobody to disagree with"


def test_the_worst_comes_first():
    tracks = [
        {"id": "a", "title": "Art", "passport": {"artwork_rights": "no"}},
        {"id": "b", "title": "Beat", "passport": {"beat_license": "no"}},
    ]
    found = rc.for_account(tracks)
    assert found[0]["severity"] == rc.HIGH
    assert found[-1]["severity"] == rc.LOW


def test_every_conflict_points_at_the_page_that_fixes_it():
    tracks = [{"id": "trk1", "title": "Co-write", "passport": {"songwriters": "Ann Lee, Bo Tran"}}]
    for c in rc.for_account(tracks):
        assert c["fix"] and c["fix"].startswith("/tracks/trk1")


# --- the page ---------------------------------------------------------------

def test_the_page_says_it_checked_nothing_rather_than_calling_it_clean():
    c, _uid = _account()
    body = c.get("/conflicts").get_data(as_text=True)
    assert "nothing to check" in body
    assert "your ownership data is clean" not in body
    assert "No rights conflicts detected" not in body


def test_the_page_reports_this_accounts_own_conflict():
    c, uid = _account()
    _track(uid, "Co-write", passport={"songwriters": "Ann Lee, Bo Tran"})
    body = c.get("/conflicts").get_data(as_text=True)
    assert "Co-write" in body
    assert "split sheet" in body
    assert "Checked 1 track" in body


def test_a_clean_catalogue_says_what_it_checked_and_what_it_cannot_see():
    c, uid = _account()
    _track(uid, "Solo Song", passport={"songwriters": "Ann Lee", "isrc": "USABC1234567"})
    body = c.get("/conflicts").get_data(as_text=True)
    assert "Nothing in your passports disagrees" in body
    assert "cannot see a claim somebody else has filed" in body


def test_one_account_never_sees_another_accounts_conflicts():
    mine, my_uid = _account()
    theirs, their_uid = _account()
    _track(their_uid, "Their Co-write", passport={"songwriters": "Ann Lee, Bo Tran"})
    body = mine.get("/conflicts").get_data(as_text=True)
    assert "Their Co-write" not in body
    assert "nothing to check" in body


def test_the_page_needs_a_sign_in():
    r = appmod.app.test_client().get("/conflicts")
    assert r.status_code in (302, 303) and "/login" in r.headers["Location"]

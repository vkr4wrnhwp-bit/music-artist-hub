"""A Live Lab set could never be put away.

archive_set sat in live_store with no caller, list_sets already filtered
archived rows, and there was no unarchive at all — so the one function
that existed would have been a one-way door if anything had called it.

A set is scenes, stems, pad maps and MIDI mappings built against a
particular room and rig. That work is the reason the set exists, so a
tour ending is when it starts being worth keeping, not when it stops.
Archiving is never a delete.
"""
import os
import uuid

import pytest

import db as store
import live_store as ls

PASSWORD = "livearch-123"


@pytest.fixture(scope="module")
def application():
    os.environ["LIVE_LAB_ENABLED"] = "1"
    import app as appmod
    return appmod.app


@pytest.fixture
def performer(application):
    c = application.test_client()
    email = "livearch-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Perf", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        c._uid = store.get_user_by_email(email)["id"]
    c.post("/live/new", data={"name": "Winter run", "venue": "Turf Club"})
    with application.app_context():
        c._sid = ls.list_sets(None, c._uid)[0]["id"]
    return c


def test_a_set_leaves_the_working_list_without_being_deleted(performer, application):
    performer.post("/live/%s/archive" % performer._sid, data={"archived": "1"})
    with application.app_context():
        assert ls.list_sets(None, performer._uid) == []
        kept = ls.list_sets(None, performer._uid, archived=True)
    assert [s["id"] for s in kept] == [performer._sid]


def test_the_archive_is_somewhere_you_go_on_purpose(performer):
    performer.post("/live/%s/archive" % performer._sid, data={"archived": "1"})
    working = performer.get("/live").get_data(as_text=True)
    assert "1 archived set" in working
    assert "Winter run" not in working, "the working list is the sets in use"
    archive = performer.get("/live?archived=1").get_data(as_text=True)
    assert "Winter run" in archive and "Restore" in archive


def test_an_archived_set_comes_back(performer, application):
    performer.post("/live/%s/archive" % performer._sid, data={"archived": "1"})
    performer.post("/live/%s/archive" % performer._sid, data={"archived": "0"})
    with application.app_context():
        assert [s["id"] for s in ls.list_sets(None, performer._uid)] == [performer._sid]
    assert performer.get("/live/%s" % performer._sid).status_code == 200


def test_every_other_page_still_refuses_an_archived_set(performer):
    """Archived means out of use, not merely out of one list."""
    performer.post("/live/%s/archive" % performer._sid, data={"archived": "1"})
    assert performer.get("/live/%s" % performer._sid).status_code == 404


def test_restore_can_still_find_what_every_page_refuses(performer, application):
    """The trap this walked into: get_set hid archived rows, so the
    restore button would have 404'd on exactly the sets it exists for."""
    with application.app_context():
        ls.archive_set(None, performer._uid, performer._sid, archived=True)
        assert ls.get_set(None, performer._uid, performer._sid) is None
        assert ls.get_set(None, performer._uid, performer._sid,
                          include_archived=True) is not None


def test_archiving_is_the_same_call_as_restoring(application, performer):
    """One code path, so the two cannot drift out of step."""
    with application.app_context():
        assert ls.archive_set(None, performer._uid, performer._sid, archived=True)
        assert ls.list_sets(None, performer._uid, archived=True)
        assert ls.archive_set(None, performer._uid, performer._sid, archived=False)
        assert ls.list_sets(None, performer._uid)


def test_somebody_elses_set_is_a_404(application, performer):
    other = application.test_client()
    email = "livearch-other-%s@example.net" % uuid.uuid4().hex[:8]
    other.post("/signup", data={"name": "X", "email": email, "password": PASSWORD})
    other.post("/login", data={"email": email, "password": PASSWORD})
    assert other.post("/live/%s/archive" % performer._sid,
                      data={"archived": "1"}).status_code == 404
    with application.app_context():
        assert ls.list_sets(None, performer._uid), "still in its owner's list"

"""A passport could never be archived, and neither could a version.

set_archived and archive_version both sat in passport_store with no
caller, and list_passports already took an include_archived flag nothing
ever passed. So the list only grew: a passport built for a tour that
ended two years ago sat beside the one the crew is working from tonight,
and the only way to be rid of it was to delete it and lose the history —
which is the part of a passport that matters.

archive_version carries a rule worth keeping visible: the version in
force cannot be archived, or the passport would point at a document it is
not offering. The route reports that refusal instead of swallowing it.
"""
import uuid

import pytest

import app as appmod
import db as store
import passport_store as ps

PASSWORD = "passport-arch-123"


@pytest.fixture
def crew():
    c = appmod.app.test_client()
    email = "passarch-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Crew", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    with appmod.app.app_context():
        c._uid = store.get_user_by_email(email)["id"]
    return c


def _passport(crew, artist="KING 810"):
    crew.post("/passports/new", data={"artist_name": artist,
                                      "production_name": "Winter run"})
    with appmod.app.app_context():
        return ps.list_passports(crew._uid)[0]["id"]


# --- the passport ------------------------------------------------------------

def test_a_passport_leaves_the_working_list_without_being_deleted(crew):
    pid = _passport(crew)
    crew.post("/passports/%s/archive" % pid)
    with appmod.app.app_context():
        assert ps.list_passports(crew._uid) == []
        kept = ps.list_passports(crew._uid, include_archived=True)
    assert [p["id"] for p in kept] == [pid], "archiving is not a delete"


def test_the_archive_is_somewhere_you_go_on_purpose(crew):
    pid = _passport(crew)
    crew.post("/passports/%s/archive" % pid)
    working = crew.get("/passports").get_data(as_text=True)
    assert "1 archived passport" in working
    assert "KING 810" not in working, "the working list is the ones in use"
    archive = crew.get("/passports?archived=1").get_data(as_text=True)
    assert "KING 810" in archive and "Restore" in archive


def test_an_archived_passport_comes_back(crew):
    pid = _passport(crew)
    crew.post("/passports/%s/archive" % pid)
    crew.post("/passports/%s/archive" % pid, data={"archived": "0"})
    with appmod.app.app_context():
        assert [p["id"] for p in ps.list_passports(crew._uid)] == [pid]


def test_the_detail_page_says_what_archiving_does(crew):
    pid = _passport(crew)
    body = crew.get("/passports/%s" % pid).get_data(as_text=True)
    assert "Archive this passport" in body
    assert "can be restored" in body, "say it is reversible before they press it"


def test_somebody_elses_passport_is_a_404(crew):
    pid = _passport(crew)
    other = appmod.app.test_client()
    email = "passarch-other-%s@example.net" % uuid.uuid4().hex[:8]
    other.post("/signup", data={"name": "X", "email": email, "password": PASSWORD})
    other.post("/login", data={"email": email, "password": PASSWORD})
    assert other.post("/passports/%s/archive" % pid).status_code == 404
    with appmod.app.app_context():
        assert ps.list_passports(crew._uid), "and it is still in its owner's list"


# --- versions ----------------------------------------------------------------

def _two_versions(crew):
    pid = _passport(crew)
    crew.post("/passports/%s/publish" % pid, data={"change_note": "first"})
    crew.post("/passports/%s/identity" % pid,
              data={"artist_name": "KING 810", "variant": "B"})
    crew.post("/passports/%s/publish" % pid, data={"change_note": "second"})
    with appmod.app.app_context():
        versions = ps.versions(pid)
    in_force = next(v for v in versions if v["state"] == "published")
    older = next(v for v in versions if v["state"] != "published")
    return pid, in_force, older


def test_a_superseded_version_can_be_retired(crew):
    pid, _in_force, older = _two_versions(crew)
    crew.post("/passports/%s/version/%s/archive" % (pid, older["id"]))
    with appmod.app.app_context():
        states = {v["number"]: v["state"] for v in ps.versions(pid)}
    assert states[older["number"]] == "archived"


def test_the_version_in_force_refuses_and_says_why(crew):
    """Archiving it would leave the passport pointing at a document it is
    not offering."""
    pid, in_force, _older = _two_versions(crew)
    r = crew.post("/passports/%s/version/%s/archive" % (pid, in_force["id"]),
                  follow_redirects=True)
    assert "version in force" in r.get_data(as_text=True)
    with appmod.app.app_context():
        states = {v["number"]: v["state"] for v in ps.versions(pid)}
    assert states[in_force["number"]] == "published", "and it is untouched"


def test_the_button_is_only_offered_where_the_store_would_allow_it(crew):
    """A control that silently does nothing is worse than one that is
    not there."""
    pid, in_force, older = _two_versions(crew)
    page = crew.get("/passports/%s/versions" % pid).get_data(as_text=True)
    assert "/version/%s/archive" % older["id"] in page
    assert "/version/%s/archive" % in_force["id"] not in page

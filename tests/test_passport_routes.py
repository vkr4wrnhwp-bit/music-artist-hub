"""Show Passport phase 2: the pages.

Two things are load-bearing here and the rest is plumbing:

  * a passport belongs to one account, and asking for somebody else's is a
    404 rather than a 403 - a stranger should not learn an id exists by the
    shape of the refusal;
  * a published version renders from its SNAPSHOT, never from the working
    tables, so a page showing v1 keeps showing v1 after the draft moves on.
"""
import uuid

import pytest

import app as appmod
import passport_store as ps


PASSWORD = "pp-pass-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


def _account(application):
    email = "pp-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Passport Tester", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client


@pytest.fixture
def owned(application):
    client = _account(application)
    r = client.post("/passports/new", data={"artist_name": "Prayers",
                                            "production_name": "No Tengo Calma",
                                            "variant": "Theatre"})
    pid = r.headers["Location"].rstrip("/").split("/")[-1]
    return client, pid


# --- access ------------------------------------------------------------------

def test_a_stranger_is_sent_to_the_login(application):
    r = application.test_client().get("/passports/")
    assert r.status_code in (302, 401)


def test_another_account_gets_a_404_not_a_403(owned, application):
    """403 would confirm the id exists."""
    _client, pid = owned
    other = _account(application)
    assert other.get("/passports/%s" % pid).status_code == 404


def test_the_index_lists_only_your_own(owned, application):
    client, _pid = owned
    other = _account(application)
    other.post("/passports/new", data={"artist_name": "Somebody Else"})
    body = client.get("/passports/").get_data(as_text=True)
    assert "Prayers" in body
    assert "Somebody Else" not in body


# --- editing -----------------------------------------------------------------

def test_the_editor_renders_every_section(owned):
    client, pid = owned
    body = client.get("/passports/%s" % pid).get_data(as_text=True)
    for anchor in ("identity", "stage_plot", "contacts", "personnel", "inputs",
                   "outputs", "equipment", "cues", "playback"):
        assert 'id="%s"' % anchor in body, anchor


def test_rows_can_be_added_edited_and_removed(owned):
    client, pid = owned
    client.post("/passports/%s/inputs/add" % pid,
                data={"channel": "1", "source": "Kick", "phantom": "1"})
    rows = ps.rows("inputs", pid)
    assert [r["source"] for r in rows] == ["Kick"]
    assert rows[0]["phantom"] == 1

    client.post("/passports/%s/inputs/%s/save" % (pid, rows[0]["id"]),
                data={"channel": "1", "source": "Kick In", "phantom": ""})
    rows = ps.rows("inputs", pid)
    assert rows[0]["source"] == "Kick In"
    assert rows[0]["phantom"] == 0, "an unchecked box clears the flag"

    client.post("/passports/%s/inputs/%s/delete" % (pid, rows[0]["id"]))
    assert ps.rows("inputs", pid) == []


def test_an_unknown_section_is_a_404(owned):
    """The web's list of writable sections is its own allowlist, so a store
    rename cannot silently widen it."""
    client, pid = owned
    assert client.post("/passports/%s/passports/add" % pid).status_code == 404
    assert client.post("/passports/%s/versions/add" % pid).status_code == 404


def test_gaps_are_shown_and_never_a_percentage(owned):
    client, pid = owned
    body = client.get("/passports/%s" % pid).get_data(as_text=True)
    assert "Not ready to send" in body
    assert "No input list" in body or "input list" in body


# --- publishing --------------------------------------------------------------

def test_publishing_freezes_what_the_page_shows(owned):
    client, pid = owned
    client.post("/passports/%s/inputs/add" % pid, data={"channel": "1", "source": "Kick"})
    client.post("/passports/%s/publish" % pid, data={"change_note": "First pass"})

    version = ps.versions(pid)[0]
    frozen = client.get("/passports/%s/version/%s" % (pid, version["id"]))
    assert b"Kick" in frozen.data

    client.post("/passports/%s/inputs/add" % pid, data={"channel": "2", "source": "Snare"})
    again = client.get("/passports/%s/version/%s" % (pid, version["id"]))
    assert b"Snare" not in again.data, "a published version must not follow the draft"
    assert b"Kick" in again.data


def test_the_publish_button_is_disabled_with_nothing_to_publish(owned):
    client, pid = owned
    client.post("/passports/%s/publish" % pid, data={"change_note": "one"})
    body = client.get("/passports/%s" % pid).get_data(as_text=True)
    assert "disabled" in body
    assert "Nothing has changed since version 1" in body


def test_the_change_log_shows_the_note_and_the_diff(owned):
    client, pid = owned
    client.post("/passports/%s/inputs/add" % pid, data={"channel": "1", "source": "Kick"})
    client.post("/passports/%s/publish" % pid, data={"change_note": "First pass"})
    row = ps.rows("inputs", pid)[0]
    client.post("/passports/%s/inputs/%s/save" % (pid, row["id"]),
                data={"channel": "1", "source": "Kick", "mic_di": "D112"})
    client.post("/passports/%s/publish" % pid, data={"change_note": "Kick mic"})

    body = client.get("/passports/%s/versions" % pid).get_data(as_text=True)
    assert "First pass" in body and "Kick mic" in body
    # The diff defaults to the newest publish, and names the FIELD.
    assert "mic di" in body.lower()
    assert "D112" in body


def test_a_version_of_another_passport_is_a_404(owned, application):
    """The version id must belong to the passport in the URL, not merely
    exist and belong to the same account."""
    client, pid = owned
    r = client.post("/passports/new", data={"artist_name": "Second"})
    other_pid = r.headers["Location"].rstrip("/").split("/")[-1]
    client.post("/passports/%s/publish" % other_pid)
    other_version = ps.versions(other_pid)[0]["id"]

    assert client.get("/passports/%s/version/%s" % (pid, other_version)).status_code == 404

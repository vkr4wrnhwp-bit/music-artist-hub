"""Partner OS phases 4 and 5: the roster, and acting on an artist's behalf.

Act-on-behalf is impersonation. The whole file is about the conditions under
which it stops, because every one of them can be withdrawn between one request
and the next, and a half-ended impersonation is how somebody edits the wrong
artist's release.

The rule the implementation follows: permission is re-checked on EVERY
request, never trusted from when the session started.
"""
import uuid

import pytest

import db as store
import partner_store as pstore


@pytest.fixture(scope="module")
def application():
    import app as appmod
    return appmod.app


def _account(application, label):
    email = "%s-%s@example.net" % (label, uuid.uuid4().hex[:8])
    client = application.test_client()
    client.post("/signup", data={"name": label.title(), "email": email,
                                 "password": "pa-pass-123"})
    client.post("/login", data={"email": email, "password": "pa-pass-123"})
    with application.app_context():
        return client, store.get_user_by_email(email)


@pytest.fixture
def reseller(application):
    """A partner with one staff seat and one artist on the roster."""
    staff_client, staff = _account(application, "staff")
    artist_client, artist = _account(application, "artist")
    with application.app_context():
        partner_id = pstore.create_partner("Reseller %s" % uuid.uuid4().hex[:6],
                                           slug="r-" + uuid.uuid4().hex[:8])
        pstore.add_member(partner_id, staff["email"], name=staff["name"],
                          role="admin", user_id=staff["id"])
        pstore.attach_user(partner_id, artist["id"])
    return {"partner_id": partner_id, "staff": staff, "artist": artist,
            "client": staff_client, "artist_client": artist_client}


def _acting(client):
    return "You are working in" in client.get("/overview").get_data(as_text=True)


# --- phase 4: the roster ---------------------------------------------------

def test_the_roster_shows_state_not_just_names(reseller):
    """A list of names answers "who is on this" and nothing else. What a
    partner decides against is whether the account has been used and whether
    there is anything in it."""
    body = reseller["client"].get("/partner/roster").get_data(as_text=True)
    assert reseller["artist"]["name"] in body
    assert "never signed in" in body or "last seen" in body


def test_a_missing_module_table_is_not_reported_as_zero(application, reseller):
    """None, not 0. A module that has not initialised its schema is not the
    same as an artist with nothing, and a confident zero on a management
    screen is a small lie."""
    with application.app_context():
        assert pstore._count("a_table_that_does_not_exist",
                             reseller["artist"]["id"]) is None

        # The positive control, against a table that really is there. Found
        # rather than named: _count needs a user_id column, and hard-coding a
        # table that turns out not to have one tests nothing (`users` keys on
        # `id`, so it returns None for the same reason a missing table does).
        import db as store
        with store.get_db() as conn:
            present = None
            for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"):
                columns = [c["name"] for c in
                           conn.execute("PRAGMA table_info(%s)" % row["name"])]
                if "user_id" in columns:
                    present = row["name"]
                    break
        assert present, "no table on this deployment has a user_id column"
        assert isinstance(
            pstore._count(present, reseller["artist"]["id"]), int)


# --- phase 5: acting on behalf ---------------------------------------------

def test_a_partner_can_open_an_artists_workspace(reseller):
    reseller["client"].post("/partner/act/%s" % reseller["artist"]["id"])
    assert _acting(reseller["client"])


def test_every_page_says_whose_account_it_is(reseller):
    """Not dismissible, and on every page. An operator who forgets which
    workspace they are in can change the wrong artist's release."""
    reseller["client"].post("/partner/act/%s" % reseller["artist"]["id"])
    body = reseller["client"].get("/overview").get_data(as_text=True)
    assert reseller["artist"]["name"] in body
    assert "Leave this account" in body


def test_the_start_is_audited_against_the_staff_members_own_name(application, reseller):
    """session["user_id"] keeps the impersonator. An impersonation record that
    loses the impersonator is not a record."""
    reseller["client"].post("/partner/act/%s" % reseller["artist"]["id"])
    with application.app_context():
        trail = pstore.audit_trail(reseller["partner_id"])
    started = [t for t in trail if t["action"] == "act_as.start"]
    assert started
    assert started[0]["actor_email"] == reseller["staff"]["email"]
    assert started[0]["subject_user_id"] == reseller["artist"]["id"]


def test_stopping_is_audited_too(application, reseller):
    reseller["client"].post("/partner/act/%s" % reseller["artist"]["id"])
    reseller["client"].post("/partner/act/stop")
    with application.app_context():
        trail = pstore.audit_trail(reseller["partner_id"])
    assert any(t["action"] == "act_as.stop" for t in trail)


def test_stopping_returns_the_staff_member_to_themselves(reseller):
    reseller["client"].post("/partner/act/%s" % reseller["artist"]["id"])
    reseller["client"].post("/partner/act/stop")
    assert not _acting(reseller["client"])


# --- every way it must end -------------------------------------------------

def test_detaching_the_artist_ends_it_on_the_next_request(application, reseller):
    """Not at next login. Withdrawing access has to take effect immediately."""
    reseller["client"].post("/partner/act/%s" % reseller["artist"]["id"])
    assert _acting(reseller["client"])

    with application.app_context():
        pstore.detach_user(reseller["partner_id"], reseller["artist"]["id"])
    assert not _acting(reseller["client"])


def test_suspending_the_partner_ends_it(application, reseller):
    """member_for_user joins partners, so a suspended one grants nothing -
    switching a reseller off is one column write and it reaches this."""
    reseller["client"].post("/partner/act/%s" % reseller["artist"]["id"])
    assert _acting(reseller["client"])

    with application.app_context():
        pstore.set_partner_status(reseller["partner_id"], "suspended")
    assert not _acting(reseller["client"])


def test_removing_the_seat_ends_it(application, reseller):
    reseller["client"].post("/partner/act/%s" % reseller["artist"]["id"])
    assert _acting(reseller["client"])

    with application.app_context():
        member = pstore.get_member(reseller["partner_id"],
                                   user_id=reseller["staff"]["id"])
        pstore.remove_member(reseller["partner_id"], member["id"])
    assert not _acting(reseller["client"])


def test_a_person_can_always_leave_even_with_no_seat(application, reseller):
    """`stop` is deliberately not behind the permission decorator. A seat that
    has just lost its permission still has to be able to get out."""
    reseller["client"].post("/partner/act/%s" % reseller["artist"]["id"])
    with application.app_context():
        member = pstore.get_member(reseller["partner_id"],
                                   user_id=reseller["staff"]["id"])
        pstore.remove_member(reseller["partner_id"], member["id"])

    response = reseller["client"].post("/partner/act/stop")
    assert response.status_code in (301, 302)
    assert not _acting(reseller["client"])


# --- who may never do it ---------------------------------------------------

def test_a_partner_cannot_act_as_an_account_it_does_not_own(application, reseller):
    _stranger_client, stranger = _account(application, "stranger")
    response = reseller["client"].post("/partner/act/%s" % stranger["id"])
    assert response.status_code == 404


def test_somebody_with_no_seat_cannot_act_as_anybody(application, reseller):
    outsider_client, _outsider = _account(application, "outsider")
    response = outsider_client.post("/partner/act/%s" % reseller["artist"]["id"])
    assert response.status_code in (403, 404, 302)


def test_a_street_banker_account_can_never_be_acted_as(application, reseller):
    """Direct accounts carry partner_id NULL, so owns_user can never match
    one. Safe by construction rather than by a check somebody could remove."""
    _direct_client, direct = _account(application, "direct")
    with application.app_context():
        assert not pstore.owns_user(reseller["partner_id"], direct["id"])
    assert reseller["client"].post(
        "/partner/act/%s" % direct["id"]).status_code == 404


def test_acting_as_yourself_is_refused(application, reseller):
    """A no-op that would still write an audit row implying otherwise."""
    import partner_os

    with application.app_context():
        assert partner_os.acting_context(reseller["staff"]["id"],
                                         reseller["staff"]["id"]) is None

"""A reseller could not be created except by hand on the database.

create_partner, add_member, set_seat_limit and set_partner_status all
lived in partner_store with no caller anywhere in the app. So a partner
could be guarded, rostered, granted plans, acted on behalf of and
audited — and could not be brought into existence. The white-label
product could not be sold, however well the rest of it was built.

Owner-only, and not on the /partner blueprint: that blueprint's guard
resolves an existing tenant, and this is the page that makes one.
"""
import os
import uuid

import pytest

import db as store
import partner_store as ps

PASSWORD = "backoffice-123"


@pytest.fixture(scope="module")
def application():
    os.environ["OWNER_EMAILS"] = "backoffice-owner@example.net"
    import app as appmod
    return appmod.app


@pytest.fixture
def owner(application):
    c = application.test_client()
    c.post("/signup", data={"name": "Boss", "email": "backoffice-owner@example.net",
                            "password": PASSWORD})
    c.post("/login", data={"email": "backoffice-owner@example.net",
                           "password": PASSWORD})
    return c


@pytest.fixture
def stranger(application):
    c = application.test_client()
    email = "not-owner-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Nobody", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    return c


def _make(owner, name=None, slug=None, domain=None):
    name = name or ("Northwind %s" % uuid.uuid4().hex[:6])
    slug = slug or ("nw-%s" % uuid.uuid4().hex[:6])
    owner.post("/partners", data={"name": name, "slug": slug,
                                  "domain": domain or ""})
    return next(p for p in ps.list_partners() if p["slug"] == slug)


# --- who may see it ---------------------------------------------------------

def test_an_owner_can_open_the_back_office(owner):
    assert owner.get("/partners").status_code == 200


def test_everybody_else_gets_a_404_not_a_403(stranger):
    """Nobody who is not an owner needs to learn this address exists."""
    assert stranger.get("/partners").status_code == 404


def test_a_signed_out_visitor_is_sent_to_log_in(application):
    r = application.test_client().get("/partners")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


@pytest.mark.parametrize("path,data", [
    ("/partners", {"name": "Sneaky"}),
    ("/partners/x/seats", {"seat_limit": "5"}),
    ("/partners/x/members", {"email": "a@b.com", "role": "owner"}),
    ("/partners/x/status", {"status": "suspended"}),
])
def test_none_of_the_writes_are_reachable_without_being_an_owner(stranger, path, data):
    assert stranger.post(path, data=data).status_code == 404


# --- what it can actually do ------------------------------------------------

def test_a_reseller_can_be_created(owner, application):
    with application.app_context():
        before = len(ps.list_partners())
        p = _make(owner, domain="app.northwind-%s.example" % uuid.uuid4().hex[:6])
        assert len(ps.list_partners()) == before + 1
        assert p["status"] == "active"
        assert p["domain"], "the domain is what makes their address resolve"


def test_a_taken_slug_is_named_rather_than_swallowed(owner, application):
    with application.app_context():
        p = _make(owner)
    r = owner.post("/partners", data={"name": "Someone else", "slug": p["slug"]})
    assert r.status_code == 200, "back to the page, not a redirect that lost it"
    assert "already belongs" in r.get_data(as_text=True)
    with application.app_context():
        same = [x for x in ps.list_partners() if x["slug"] == p["slug"]]
    assert len(same) == 1, "and nothing was created"


def test_a_seat_cap_can_be_set(owner, application):
    with application.app_context():
        p = _make(owner)
    owner.post("/partners/%s/seats" % p["id"], data={"seat_limit": "25"})
    with application.app_context():
        assert ps.seat_limit(p["id"]) == 25


def test_a_console_seat_can_be_added_before_anybody_has_signed_up(owner, application):
    """The seat waits for whoever holds that address; claim_seats attaches
    it when they sign in. A reseller can be set up before their staff exist."""
    with application.app_context():
        p = _make(owner)
    email = "future-%s@northwind.example" % uuid.uuid4().hex[:6]
    owner.post("/partners/%s/members" % p["id"],
               data={"email": email, "role": "owner"})
    with application.app_context():
        seats = ps.list_members(p["id"])
        seat = next(m for m in seats if m["email"] == email)
    assert seat["role"] == "owner"
    assert not seat["user_id"], "no account was invented for them"
    with application.app_context():
        assert store.get_user_by_email(email) is None


def test_adding_an_existing_address_changes_its_role(owner, application):
    with application.app_context():
        p = _make(owner)
    email = "dual-%s@northwind.example" % uuid.uuid4().hex[:6]
    owner.post("/partners/%s/members" % p["id"], data={"email": email, "role": "viewer"})
    owner.post("/partners/%s/members" % p["id"], data={"email": email, "role": "admin"})
    with application.app_context():
        seats = [m for m in ps.list_members(p["id"]) if m["email"] == email]
    assert len(seats) == 1 and seats[0]["role"] == "admin"


def test_an_invented_role_is_refused(owner, application):
    with application.app_context():
        p = _make(owner)
    r = owner.post("/partners/%s/members" % p["id"],
                   data={"email": "x@northwind.example", "role": "emperor"})
    assert r.status_code == 200
    assert "not a role this software has" in r.get_data(as_text=True)


def test_suspending_closes_the_console_without_deleting_anything(owner, application):
    """Their artists keep their accounts and their attachment, so
    reactivating puts everything back rather than rebuilding it."""
    with application.app_context():
        p = _make(owner)
        artist_email = "seated-%s@example.net" % uuid.uuid4().hex[:8]
    c = application.test_client()
    c.post("/signup", data={"name": "Seated", "email": artist_email,
                            "password": PASSWORD})
    with application.app_context():
        artist = store.get_user_by_email(artist_email)
        ps.attach_user(p["id"], artist["id"])
        assert ps.seats_used(p["id"]) == 1

    owner.post("/partners/%s/status" % p["id"], data={"status": "suspended"})
    with application.app_context():
        assert ps.get_partner(p["id"])["status"] == "suspended"
        assert store.get_user(artist["id"]) is not None, "the artist survives"
        assert ps.seats_used(p["id"]) == 1, "and stays attached"

    owner.post("/partners/%s/status" % p["id"], data={"status": "active"})
    with application.app_context():
        assert ps.get_partner(p["id"])["status"] == "active"


def test_an_invented_status_is_refused(owner, application):
    with application.app_context():
        p = _make(owner)
    r = owner.post("/partners/%s/status" % p["id"], data={"status": "deleted"})
    assert r.status_code == 200
    with application.app_context():
        assert ps.get_partner(p["id"])["status"] == "active"


def test_a_partner_that_does_not_exist_is_a_404(owner):
    assert owner.post("/partners/nope/seats", data={"seat_limit": "1"}).status_code == 404
    assert owner.post("/partners/nope/status", data={"status": "active"}).status_code == 404

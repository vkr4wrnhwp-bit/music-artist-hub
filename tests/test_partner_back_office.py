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
    owner.post("/resellers", data={"name": name, "slug": slug,
                                  "domain": domain or ""})
    return next(p for p in ps.list_partners() if p["slug"] == slug)


# --- who may see it ---------------------------------------------------------

def test_an_owner_can_open_the_back_office(owner):
    assert owner.get("/resellers").status_code == 200


def test_everybody_else_gets_a_404_not_a_403(stranger):
    """Nobody who is not an owner needs to learn this address exists."""
    assert stranger.get("/resellers").status_code == 404


def test_a_signed_out_visitor_is_sent_to_log_in(application):
    r = application.test_client().get("/resellers")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


@pytest.mark.parametrize("path,data", [
    ("/resellers", {"name": "Sneaky"}),
    ("/resellers/x/seats", {"seat_limit": "5"}),
    ("/resellers/x/members", {"email": "a@b.com", "role": "owner"}),
    ("/resellers/x/status", {"status": "suspended"}),
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
    r = owner.post("/resellers", data={"name": "Someone else", "slug": p["slug"]})
    assert r.status_code == 200, "back to the page, not a redirect that lost it"
    assert "already belongs" in r.get_data(as_text=True)
    with application.app_context():
        same = [x for x in ps.list_partners() if x["slug"] == p["slug"]]
    assert len(same) == 1, "and nothing was created"


def test_a_seat_cap_can_be_set(owner, application):
    with application.app_context():
        p = _make(owner)
    owner.post("/resellers/%s/seats" % p["id"], data={"seat_limit": "25"})
    with application.app_context():
        assert ps.seat_limit(p["id"]) == 25


def test_a_console_seat_can_be_added_before_anybody_has_signed_up(owner, application):
    """The seat waits for whoever holds that address; claim_seats attaches
    it when they sign in. A reseller can be set up before their staff exist."""
    with application.app_context():
        p = _make(owner)
    email = "future-%s@northwind.example" % uuid.uuid4().hex[:6]
    owner.post("/resellers/%s/members" % p["id"],
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
    owner.post("/resellers/%s/members" % p["id"], data={"email": email, "role": "viewer"})
    owner.post("/resellers/%s/members" % p["id"], data={"email": email, "role": "admin"})
    with application.app_context():
        seats = [m for m in ps.list_members(p["id"]) if m["email"] == email]
    assert len(seats) == 1 and seats[0]["role"] == "admin"


def test_an_invented_role_is_refused(owner, application):
    with application.app_context():
        p = _make(owner)
    r = owner.post("/resellers/%s/members" % p["id"],
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

    owner.post("/resellers/%s/status" % p["id"], data={"status": "suspended"})
    with application.app_context():
        assert ps.get_partner(p["id"])["status"] == "suspended"
        assert store.get_user(artist["id"]) is not None, "the artist survives"
        assert ps.seats_used(p["id"]) == 1, "and stays attached"

    owner.post("/resellers/%s/status" % p["id"], data={"status": "active"})
    with application.app_context():
        assert ps.get_partner(p["id"])["status"] == "active"


def test_an_invented_status_is_refused(owner, application):
    with application.app_context():
        p = _make(owner)
    r = owner.post("/resellers/%s/status" % p["id"], data={"status": "deleted"})
    assert r.status_code == 200
    with application.app_context():
        assert ps.get_partner(p["id"])["status"] == "active"


def test_a_partner_that_does_not_exist_is_a_404(owner):
    assert owner.post("/resellers/nope/seats", data={"seat_limit": "1"}).status_code == 404
    assert owner.post("/resellers/nope/status", data={"status": "active"}).status_code == 404


# --- a roster that can actually be filled ------------------------------------
#
# attach_user and detach_user had no caller anywhere, and nothing else in
# the app writes users.partner_id. A reseller's console read
# `WHERE partner_id = ?` and was therefore empty for ever - so the
# white-label product still could not be sold after the back office
# existed, because no artist could be seated.

def _artist(application, email=None):
    email = email or ("seatme-%s@example.net" % uuid.uuid4().hex[:8])
    c = application.test_client()
    c.post("/signup", data={"name": "Artist", "email": email, "password": PASSWORD})
    with application.app_context():
        return store.get_user_by_email(email)


def test_an_artist_can_be_put_on_a_roster(owner, application):
    with application.app_context():
        p = _make(owner)
    artist = _artist(application)
    owner.post("/resellers/%s/artists" % p["id"], data={"email": artist["email"]})
    with application.app_context():
        assert [r["id"] for r in ps.roster(p["id"])] == [artist["id"]]
        assert ps.seats_used(p["id"]) == 1


def test_an_account_that_does_not_exist_is_not_invented(owner, application):
    with application.app_context():
        p = _make(owner)
    missing = "ghost-%s@example.net" % uuid.uuid4().hex[:8]
    r = owner.post("/resellers/%s/artists" % p["id"], data={"email": missing})
    assert "have to sign up" in r.get_data(as_text=True)
    with application.app_context():
        assert store.get_user_by_email(missing) is None
        assert ps.roster(p["id"]) == []


def test_somebody_elses_artist_is_a_transfer_not_a_grab(owner, application):
    """attach_user refuses to move an account between resellers, and the
    page has to say why rather than failing silently."""
    with application.app_context():
        first = _make(owner)
        second = _make(owner)
    artist = _artist(application)
    owner.post("/resellers/%s/artists" % first["id"], data={"email": artist["email"]})
    r = owner.post("/resellers/%s/artists" % second["id"], data={"email": artist["email"]})
    body = r.get_data(as_text=True)
    assert "already belongs to" in body and "transfer" in body
    with application.app_context():
        assert ps.roster(second["id"]) == []
        assert len(ps.roster(first["id"])) == 1


def test_a_full_roster_refuses_and_says_it_is_the_cap(owner, application):
    with application.app_context():
        p = _make(owner)
    owner.post("/resellers/%s/seats" % p["id"], data={"seat_limit": "1"})
    a1, a2 = _artist(application), _artist(application)
    owner.post("/resellers/%s/artists" % p["id"], data={"email": a1["email"]})
    r = owner.post("/resellers/%s/artists" % p["id"], data={"email": a2["email"]})
    assert "seat cap" in r.get_data(as_text=True)
    with application.app_context():
        assert len(ps.roster(p["id"])) == 1


def test_removing_an_artist_keeps_the_account_and_its_work(owner, application):
    with application.app_context():
        p = _make(owner)
    artist = _artist(application)
    owner.post("/resellers/%s/artists" % p["id"], data={"email": artist["email"]})
    owner.post("/resellers/%s/artists/%s/remove" % (p["id"], artist["id"]))
    with application.app_context():
        assert ps.roster(p["id"]) == []
        assert store.get_user(artist["id"]) is not None, (
            "coming off a roster is not a deletion")


def test_a_reseller_cannot_reach_another_resellers_artists(owner, application, stranger):
    with application.app_context():
        p = _make(owner)
    artist = _artist(application)
    owner.post("/resellers/%s/artists" % p["id"], data={"email": artist["email"]})
    assert stranger.post("/resellers/%s/artists" % p["id"],
                         data={"email": artist["email"]}).status_code == 404
    assert stranger.post("/resellers/%s/artists/%s/remove"
                         % (p["id"], artist["id"])).status_code == 404
    with application.app_context():
        assert len(ps.roster(p["id"])) == 1


def test_a_seat_invited_by_email_binds_when_its_holder_signs_up(owner, application):
    """claim_seats had no caller either.

    member_for_user matches on user_id, and a seat created before its
    holder signed up has user_id NULL - so a reseller's own staff could
    not reach their console however correct the seat was. Unit tests all
    passed; only walking the whole lifecycle showed it.
    """
    with application.app_context():
        p = _make(owner)
    staff_email = "staff-%s@northwind.example" % uuid.uuid4().hex[:8]
    owner.post("/resellers/%s/members" % p["id"],
               data={"email": staff_email, "role": "owner"})
    with application.app_context():
        seat = next(m for m in ps.list_members(p["id"]) if m["email"] == staff_email)
        assert not seat["user_id"], "nobody has signed up yet"

    staff = application.test_client()
    staff.post("/signup", data={"name": "Staff", "email": staff_email,
                                "password": PASSWORD})
    staff.post("/login", data={"email": staff_email, "password": PASSWORD})
    assert staff.get("/partner/roster").status_code == 200, (
        "their own console has to be reachable")
    with application.app_context():
        seat = next(m for m in ps.list_members(p["id"]) if m["email"] == staff_email)
        assert seat["user_id"], "the seat bound to the account"


def test_the_whole_lifecycle_holds_together(owner, application):
    """Create, cap, seat staff, roster an artist, and let the reseller
    work. Each step passed on its own before the console 404'd on the
    step nothing tested."""
    with application.app_context():
        p = _make(owner)
    owner.post("/resellers/%s/seats" % p["id"], data={"seat_limit": "10"})
    staff_email = "lifecycle-%s@northwind.example" % uuid.uuid4().hex[:8]
    owner.post("/resellers/%s/members" % p["id"],
               data={"email": staff_email, "role": "owner"})
    artist = _artist(application)
    owner.post("/resellers/%s/artists" % p["id"], data={"email": artist["email"]})

    staff = application.test_client()
    staff.post("/signup", data={"name": "Staff", "email": staff_email,
                                "password": PASSWORD})
    staff.post("/login", data={"email": staff_email, "password": PASSWORD})
    page = staff.get("/partner/roster")
    assert page.status_code == 200
    assert artist["email"] in page.get_data(as_text=True), (
        "the reseller must see the artist they were given")

    staff.post("/partner/roster/%s/plan" % artist["id"], data={"plan": "pro"})
    with application.app_context():
        assert store.get_user(artist["id"])["plan"] == "pro", (
            "and be able to move them between tiers")


def test_the_back_office_never_takes_over_a_public_page(application):
    """It was registered on /partners, which is the public "Partner
    network" marketing page — listed in _PUBLIC_EXACT so a stranger can
    read it without a login wall.

    Flask allows two rules with the same path and different function
    names, so nothing raised; mine simply sat earlier in the file, won
    the match, and the public page became a redirect to login. Only the
    object-leak sweep, which walks every public route, caught it.
    """
    anon = application.test_client()
    public = anon.get("/partners")
    assert public.status_code == 200, (
        "the public Partner network page must answer a signed-out visitor")

    rules = [r for r in application.url_map.iter_rules() if str(r) == "/partners"]
    assert len(rules) == 1, "two handlers on one public path, silently"

    assert anon.get("/resellers").status_code == 302, (
        "and the back office lives somewhere of its own")

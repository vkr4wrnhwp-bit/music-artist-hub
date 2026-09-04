"""Partner OS phase 3: seats and entitlements.

A partner is a reseller — their artists never see Street Banker and never pay
it. Two things follow, and both are enforced here rather than in a template:

  * the artist does not hold their own tier. The partner grants it and
    carries the cost, so /plan/switch must refuse a seated account.
  * a partner cannot seat unlimited artists once a cap is set, because the
    cap is what the partner is billed against.

The seat cap defaults to 0 (unlimited) so that adding seats to a live
deployment changes nothing until somebody sets a number.
"""
import uuid

import pytest

import app as appmod
import db as store
import partner_store as pstore

PASSWORD = "seat-pass-123"


@pytest.fixture(scope="module")
def flask_app():
    app = appmod.create_app()
    pstore.init_partners()
    return app


def _account(flask_app, plan="fan"):
    email = "seat-%s@example.net" % uuid.uuid4().hex[:10]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Seat Tester", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    user = store.get_user_by_email(email)
    if plan != "fan":
        store.set_user_plan(user["id"], plan)
    return client, store.get_user(user["id"])


def _partner(name=None):
    name = name or ("Seats %s" % uuid.uuid4().hex[:6])
    return pstore.get_partner(pstore.create_partner(name))


# --- the cap -----------------------------------------------------------------

def test_a_partner_is_uncapped_by_default(flask_app):
    """Seats arrived in a migration. A cap that applied retroactively would
    lock existing resellers out of their own rosters."""
    p = _partner()
    assert pstore.seat_limit(p["id"]) == pstore.SEAT_UNLIMITED
    assert pstore.seats_left(p["id"]) is None


def test_the_cap_refuses_the_seat_that_would_exceed_it(flask_app):
    p = _partner()
    pstore.set_seat_limit(p["id"], 2)
    _c1, a1 = _account(flask_app)
    _c2, a2 = _account(flask_app)
    _c3, a3 = _account(flask_app)
    assert pstore.attach_user(p["id"], a1["id"]) is True
    assert pstore.attach_user(p["id"], a2["id"]) is True
    assert pstore.attach_user(p["id"], a3["id"]) is False, "third seat over a cap of 2"
    assert pstore.seats_used(p["id"]) == 2
    assert pstore.seats_left(p["id"]) == 0


def test_re_attaching_an_artist_already_seated_is_still_idempotent(flask_app):
    """Only a NEW seat consumes one. Re-attaching somebody the partner already
    owns must not fail merely because the roster is full."""
    p = _partner()
    pstore.set_seat_limit(p["id"], 1)
    _c, artist = _account(flask_app)
    assert pstore.attach_user(p["id"], artist["id"]) is True
    assert pstore.attach_user(p["id"], artist["id"]) is True
    assert pstore.seats_used(p["id"]) == 1


def test_lowering_the_cap_evicts_nobody(flask_app):
    """A billing change is not permission to throw an artist off the roster.
    The limit binds new seats only."""
    p = _partner()
    _c1, a1 = _account(flask_app)
    _c2, a2 = _account(flask_app)
    pstore.attach_user(p["id"], a1["id"])
    pstore.attach_user(p["id"], a2["id"])
    assert pstore.set_seat_limit(p["id"], 1) is True
    assert pstore.seats_used(p["id"]) == 2, "still seated"
    assert pstore.seats_left(p["id"]) == 0
    _c3, a3 = _account(flask_app)
    assert pstore.attach_user(p["id"], a3["id"]) is False


def test_a_nonsense_limit_is_refused_not_stored(flask_app):
    p = _partner()
    assert pstore.set_seat_limit(p["id"], "lots") is False
    assert pstore.seat_limit(p["id"]) == pstore.SEAT_UNLIMITED


# --- entitlements ------------------------------------------------------------

def test_the_partner_can_set_a_tier_it_owns(flask_app):
    p = _partner()
    _c, artist = _account(flask_app)
    pstore.attach_user(p["id"], artist["id"])
    assert pstore.grant_plan(p["id"], artist["id"], "pro") == "pro"
    assert store.get_user(artist["id"])["plan"] == "pro"


def test_a_partner_cannot_set_a_tier_it_does_not_own(flask_app):
    """The store asks the database rather than trusting the caller checked."""
    mine = _partner()
    theirs = _partner()
    _c, artist = _account(flask_app)
    pstore.attach_user(theirs["id"], artist["id"])
    before = store.get_user(artist["id"])["plan"]
    assert pstore.grant_plan(mine["id"], artist["id"], "label") is None
    assert store.get_user(artist["id"])["plan"] == before


def test_an_invented_tier_is_refused(flask_app):
    p = _partner()
    _c, artist = _account(flask_app)
    pstore.attach_user(p["id"], artist["id"])
    before = store.get_user(artist["id"])["plan"]
    assert pstore.grant_plan(p["id"], artist["id"], "platinum") is None
    assert store.get_user(artist["id"])["plan"] == before


def test_only_owner_and_admin_hold_the_grant(flask_app):
    """A manager runs the roster; paying for a tier is not their call."""
    assert pstore.can({"role": "owner"}, "entitlement_grant") is True
    assert pstore.can({"role": "admin"}, "entitlement_grant") is True
    for role in ("manager", "support", "viewer"):
        assert pstore.can({"role": role}, "entitlement_grant") is False, role


# --- the hole this phase closes ----------------------------------------------

def test_a_seated_artist_cannot_switch_their_own_plan(flask_app):
    """The reason phase 3 exists. /plan/switch called set_user_plan for any
    signed-in account, so a reseller's artist could unlock Label on an
    account the partner pays for."""
    p = _partner()
    client, artist = _account(flask_app)
    pstore.attach_user(p["id"], artist["id"])
    before = store.get_user(artist["id"])["plan"]
    assert before != "label", "the test needs a tier it does not already hold"

    client.post("/plan/switch", data={"plan": "label"})

    assert store.get_user(artist["id"])["plan"] == before, \
        "a partner-seated artist must not grant themselves a tier"


def test_a_direct_account_still_switches_freely(flask_app):
    """The guard must bite on seated accounts ONLY. Every existing Street
    Banker customer has partner_id NULL and keeps self-serve.

    Switched to "pro" deliberately: signup already leaves an account on
    "artist", so asserting that would pass even if the route did nothing.
    """
    client, user = _account(flask_app)
    assert user.get("partner_id") in (None, "")
    assert store.get_user(user["id"])["plan"] != "pro"
    client.post("/plan/switch", data={"plan": "pro"})
    assert store.get_user(user["id"])["plan"] == "pro"


def test_detaching_hands_self_serve_back(flask_app):
    """Leaving a partner returns the account to a direct customer, and a
    direct customer holds their own tier again."""
    p = _partner()
    client, artist = _account(flask_app)
    pstore.attach_user(p["id"], artist["id"])
    pstore.detach_user(p["id"], artist["id"])
    assert store.get_user(artist["id"])["plan"] != "pro"
    client.post("/plan/switch", data={"plan": "pro"})
    assert store.get_user(artist["id"])["plan"] == "pro"


# --- the grant route ---------------------------------------------------------
# These use the module-level app, the way tests/test_partner_act_as.py does,
# because that is what resolves the tenant from the staff member's seat.

@pytest.fixture(scope="module")
def application():
    return appmod.app


def _seat(application, label, role):
    email = "%s-%s@example.net" % (label, uuid.uuid4().hex[:8])
    client = application.test_client()
    client.post("/signup", data={"name": label.title(), "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        return client, store.get_user_by_email(email)


@pytest.fixture
def reseller(application):
    admin_client, admin = _seat(application, "padmin", "admin")
    artist_client, artist = _seat(application, "partist", "viewer")
    with application.app_context():
        pid = pstore.create_partner("Grant %s" % uuid.uuid4().hex[:6],
                                    slug="g-" + uuid.uuid4().hex[:8])
        pstore.add_member(pid, admin["email"], name=admin["name"],
                          role="admin", user_id=admin["id"])
        pstore.attach_user(pid, artist["id"])
    return {"partner_id": pid, "client": admin_client, "admin": admin,
            "artist": artist, "artist_client": artist_client}


def test_the_route_grants_and_records_who_did_it(reseller, application):
    """A disputed invoice asks who upgraded the account, so the grant is
    written to the audit trail with the tier it moved from and to."""
    artist_id = reseller["artist"]["id"]
    r = reseller["client"].post("/partner/roster/%s/plan" % artist_id,
                                data={"plan": "label"})
    assert r.status_code in (302, 303)
    with application.app_context():
        assert store.get_user(artist_id)["plan"] == "label"
        trail = pstore.audit_trail(reseller["partner_id"])
    grants = [row for row in trail if row["action"] == "entitlement.grant"]
    assert grants, "the grant is not on the record"
    assert "Label" in grants[0]["detail"]


def test_a_role_without_the_permission_is_refused(reseller, application):
    """A manager runs the roster; committing the partner to a paid tier is
    not their call, and the template hiding the control is not the check."""
    artist_id = reseller["artist"]["id"]
    with application.app_context():
        # add_member upserts by (partner, email), so this demotes the seat
        # rather than adding a second one.
        pstore.add_member(reseller["partner_id"], reseller["admin"]["email"],
                          role="manager", user_id=reseller["admin"]["id"])
        assert pstore.get_member(
            reseller["partner_id"],
            user_id=reseller["admin"]["id"])["role"] == "manager"
        before = store.get_user(artist_id)["plan"]

    r = reseller["client"].post("/partner/roster/%s/plan" % artist_id,
                                data={"plan": "label"})

    assert r.status_code == 403
    with application.app_context():
        assert store.get_user(artist_id)["plan"] == before


def test_an_artist_another_partner_owns_is_a_404(reseller, application):
    """Ownership is asked of the database, not inferred from the id arriving
    in a URL this partner was allowed to load."""
    outsider_client, outsider = _seat(application, "poutsider", "viewer")
    with application.app_context():
        other = pstore.create_partner("Other %s" % uuid.uuid4().hex[:6],
                                      slug="o-" + uuid.uuid4().hex[:8])
        pstore.attach_user(other, outsider["id"])
        before = store.get_user(outsider["id"])["plan"]
    r = reseller["client"].post("/partner/roster/%s/plan" % outsider["id"],
                                data={"plan": "label"})
    assert r.status_code == 404
    with application.app_context():
        assert store.get_user(outsider["id"])["plan"] == before


def test_the_roster_shows_seats_against_the_cap(reseller, application):
    """A reseller needs to see how close they are to the cap BEFORE an invite
    fails, so the ceiling is on the page next to the count."""
    with application.app_context():
        pstore.set_seat_limit(reseller["partner_id"], 5)
    body = reseller["client"].get("/partner/roster").get_data(as_text=True)
    assert "of 5 seats" in body


def test_an_uncapped_partner_is_not_shown_a_fake_ceiling(reseller, application):
    """seats_left is None when uncapped. Printing a made-up limit there would
    be worse than printing none."""
    with application.app_context():
        pstore.set_seat_limit(reseller["partner_id"], 0)
    body = reseller["client"].get("/partner/roster").get_data(as_text=True)
    # The failure this guards against is printing the sentinel as a ceiling.
    assert "of 0 seats" not in body
    assert "Every seat is taken" not in body
    assert "1 artist" in body


def test_the_tier_control_is_only_rendered_for_a_role_that_holds_it(reseller, application):
    """The template must not offer a button the server would refuse."""
    admin_body = reseller["client"].get("/partner/roster").get_data(as_text=True)
    assert "/plan" in admin_body and "<select" in admin_body

    with application.app_context():
        pstore.add_member(reseller["partner_id"], reseller["admin"]["email"],
                          role="viewer", user_id=reseller["admin"]["id"])
    viewer_body = reseller["client"].get("/partner/roster").get_data(as_text=True)
    assert "<select" not in viewer_body

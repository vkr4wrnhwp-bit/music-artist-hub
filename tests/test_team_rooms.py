"""Team rooms and the team review (2026-09-19).

The owner: "can we have check boxes on when they invite the person and
they an choose?" A seat opens only the rooms the artist ticked. The review
of team access found a read seat could still write, an edit seat could
empty the account, and a seat could reach things beyond its rooms; each
test here failed before the fix it names.
"""
import uuid

import pytest

import app as appmod
import db as store
import team_areas

PW = "team-rooms-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("RENDER", raising=False)


def _account(plan="pro", name="Artist"):
    email = "%s-%s@example.net" % (name.lower(), uuid.uuid4().hex[:8])
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    c._email, c._id = email, uid
    return c


def _seat(owner, member, access="read", areas=None, roster=False):
    data = {"email": member._email, "role": "manager", "access": access, "areas_sent": "1",
            "areas": list(areas if areas is not None else team_areas.keys())}
    if roster:
        data["can_roster"] = "1"
    r = owner.post("/team/invite", data=data)
    assert r.get_json().get("ok"), r.get_json()
    row = [m for m in store.list_team(owner._id) if m["email"] == member._email][0]
    member.post("/team/join/" + row["invite_token"], data={})
    return [m for m in store.list_team(owner._id) if m["email"] == member._email][0]


def _open_account(member, owner):
    return member.post("/portal/%s/open" % owner._id)


# --- the checkboxes ------------------------------------------------------------

def test_a_seat_opens_only_the_rooms_it_was_given():
    owner, member = _account("pro"), _account("artist", "Fanteam")
    seat = _seat(owner, member, areas=["fans", "studio"])
    assert seat["areas"] == "fans,studio"
    r = _open_account(member, owner)
    assert r.headers["Location"].endswith("/room/fans"), "lands in its first room"
    assert member.get("/fans").status_code == 200
    for shut in ("/royalties", "/statements", "/room/business", "/command-center", "/notifications"):
        r = member.get(shut)
        assert r.status_code == 302 and "team=room" in r.headers["Location"], shut
    page = member.get("/room/fans").get_data(as_text=True)
    assert "Rooms open to you: Fans, Studio" in page


def test_every_room_ticked_is_the_whole_account():
    owner, member = _account("pro"), _account("artist", "Allrooms")
    seat = _seat(owner, member)
    assert seat["areas"] == team_areas.ALL
    assert _open_account(member, owner).headers["Location"].endswith("/command-center")
    assert member.get("/royalties").status_code == 200


def test_an_invite_needs_at_least_one_room():
    owner = _account("pro")
    r = owner.post("/team/invite", data={"email": "none-%s@example.net" % uuid.uuid4().hex[:6],
                                         "role": "manager", "areas_sent": "1", "areas": []})
    assert r.status_code == 400 and "at least one room" in r.get_json()["error"]


def test_the_artist_changes_the_rooms_later():
    owner, member = _account("pro"), _account("artist", "Movedrooms")
    seat = _seat(owner, member, areas=["fans"])
    owner.post("/team/%s/access" % seat["id"], data={"access": "read", "areas_sent": "1",
                                                      "areas": ["business"]})
    _open_account(member, owner)
    assert member.get("/royalties").status_code == 200
    assert "team=room" in member.get("/fans").headers["Location"]


def test_the_rules_hold_for_pages_outside_the_room_cards():
    assert team_areas.room_for_path("/royalty-lanes") == "business"
    assert team_areas.room_for_path("/tracks/abc") == "publishing"
    assert not team_areas.allows("fans", "/mechanicals")
    assert not team_areas.allows("fans", "/api/artist-signal-profile")
    assert team_areas.allows("fans", "/links/fans")
    assert team_areas.allows(team_areas.ALL, "/command-center")
    assert team_areas.room_for_path("/tour") == "stage", "the old Tour Hub is the Stage room's"
    assert team_areas.room_for_path("/tour/abc/settlement") == "stage"
    assert not team_areas.allows("fans", "/tour/abc/add")
    assert team_areas.parse("") == set() and not team_areas.is_all("")


def test_the_rollout_pages_belong_to_the_releases_room_deliberately():
    """The Rollout Studio card moved to Releases on 2026-09-21, but
    team_areas still listed /rollout-studio under marketing as well. Two
    rooms claimed one prefix and room_for_path() answered "releases" only
    because rooms.ROOMS happens to name Releases first: change that order
    and a Marketing seat would silently gain the page (honesty review,
    2026-09-21). Marketing does not claim it at all now."""
    paths = team_areas.room_paths()
    assert "/rollout-studio" in paths["releases"]
    assert "/rollout-studio" not in paths["marketing"]
    assert "/rollout" in paths["releases"] and "/rollout" not in paths["marketing"]
    assert team_areas.room_for_path("/rollout-studio") == "releases"
    assert team_areas.room_for_path("/rollout-studio/abc/plan") == "releases"
    assert team_areas.room_for_path("/rollout") == "releases"
    assert not team_areas.allows("marketing", "/rollout-studio")
    assert team_areas.allows("releases", "/rollout-studio/abc")


def test_a_marketing_seat_is_offered_no_action_it_would_be_bounced_at():
    """The Marketing room drew a rollout row with a button, and the seat
    that pressed it was sent back with ?team=room."""
    import rollout_store as ros
    owner, member = _account("pro"), _account("artist", "Publicist")
    for i in range(2):
        ros.create_campaign(owner._id, {"title": "Rollout %d" % i})
    _seat(owner, member, areas=["marketing"])
    _open_account(member, owner)
    body = member.get("/room/marketing").get_data(as_text=True)
    assert "Rollout with no smart link connected" not in body
    assert 'href="/rollout-studio"' not in body
    r = member.get("/rollout-studio")
    assert r.status_code == 302 and "team=room" in r.headers["Location"]
    # the artist, on the same page, still has the row
    owner_body = owner.get("/room/marketing").get_data(as_text=True)
    assert "Rollout with no smart link connected" in owner_body


def test_a_seat_with_both_rooms_keeps_the_rollout_row():
    import rollout_store as ros
    owner, member = _account("pro"), _account("artist", "Bothrooms")
    ros.create_campaign(owner._id, {"title": "Rollout"})
    _seat(owner, member, areas=["marketing", "releases"])
    _open_account(member, owner)
    body = member.get("/room/marketing").get_data(as_text=True)
    assert "Rollout with no smart link connected" in body
    assert member.get("/rollout-studio").status_code == 200


# --- the review --------------------------------------------------------------------

def test_head_is_not_a_way_to_write():
    owner, member = _account("pro"), _account("artist", "Header")
    _seat(owner, member, access="read")
    _open_account(member, owner)
    before = store.get_artist_signal_profile(owner._id)
    member.open("/api/artist-signal-profile", method="HEAD",
                json={"priorities": {"streaming": 9}, "modules": []})
    assert store.get_artist_signal_profile(owner._id) == before


@pytest.mark.parametrize("path", ["/account/reset", "/account/delete"])
def test_an_editor_cannot_empty_or_delete_the_account(path):
    owner, member = _account("label"), _account("artist", "Wrecker")
    _seat(owner, member, access="edit")
    _open_account(member, owner)
    r = member.post(path, data={"confirm": owner._email})
    assert r.status_code == 302 and "team=blocked" in r.headers["Location"]
    assert store.get_user(owner._id) is not None


# Tour, the Tour Board and the Press Desk open to seats since they work in
# the artist's account (tests/test_team_tour.py). What stays shut: the
# backups, and accepting a tour invitation, which would attach the artist's
# account to someone else's tour; that banner says how to take it yourself.
@pytest.mark.parametrize("path,why", [("/backup", "team=blocked"),
                                      ("/tours/join/some-token", "team=join")])
def test_pages_that_stay_the_account_holders_are_shut_to_seats(path, why):
    owner, member = _account("label"), _account("artist", "Wanderer")
    _seat(owner, member)
    _open_account(member, owner)
    r = member.get(path)
    assert r.status_code == 302 and why in r.headers["Location"], path


@pytest.mark.parametrize("path", ["/tours", "/tour-board", "/press-desk"])
def test_tour_board_and_press_desk_open_to_a_seat_with_their_rooms(path):
    owner, member = _account("label"), _account("artist", "Worker")
    _seat(owner, member)
    _open_account(member, owner)
    assert member.get(path).status_code == 200, path


def test_looking_at_notifications_does_not_read_them_for_the_artist():
    owner, member = _account("pro"), _account("artist", "Peeker")
    _seat(owner, member)
    store.notify(owner._id, "billing", "Something for the artist", "", "/")
    before = store.unread_notifications(owner._id)
    _open_account(member, owner)
    member.get("/notifications")
    assert store.unread_notifications(owner._id) == before


def test_the_drop_box_is_the_account_holders(monkeypatch):
    monkeypatch.setattr(appmod.emailer, "inbound_configured", lambda: True)
    monkeypatch.setattr(appmod.emailer, "inbound_address", lambda token: token + "@in.example.net")
    owner, member = _account("pro"), _account("artist", "Dropper")
    seat = _seat(owner, member)
    assert "drop-box-addr" in owner.get("/statements").get_data(as_text=True)
    token = store.get_or_create_ingest_token(owner._id)
    _open_account(member, owner)
    assert token not in member.get("/statements").get_data(as_text=True)
    assert member.post("/statements/dropbox-test").status_code in (302, 403)
    member.post("/portal/leave")
    owner.post("/team/%s/remove" % seat["id"])
    assert store.get_or_create_ingest_token(owner._id) != token, "a removed seat's address stops working"


def test_a_seat_from_before_opens_nothing_until_confirmed():
    owner, member = _account("pro"), _account("artist", "Oldseat")
    seat = _seat(owner, member)
    with store.get_db() as db:
        db.execute("UPDATE team_members SET access = 'pending' WHERE id = ?", (seat["id"],))
    assert _open_account(member, owner).status_code == 404
    assert "Confirm what they can open" in owner.get("/team").get_data(as_text=True)
    owner.post("/team/%s/access" % seat["id"], data={"access": "read", "areas_sent": "1",
                                                      "areas": ["fans"]})
    assert _open_account(member, owner).status_code == 302


def test_a_downgrade_takes_edit_away_for_good():
    owner, member = _account("pro"), _account("artist", "Clamped")
    seat = _seat(owner, member, access="edit")
    store.set_user_plan(owner._id, "artist")
    store.set_user_plan(owner._id, "pro")
    row = [m for m in store.list_team(owner._id) if m["id"] == seat["id"]][0]
    assert row["access"] == "read", "an upgrade does not quietly bring edit back"


def test_seats_beyond_the_plan_open_nothing_after_a_downgrade():
    owner = _account("pro")
    members = [_account("artist", "Seat%d" % i) for i in range(3)]
    for m in members:
        _seat(owner, m)
    store.set_user_plan(owner._id, "artist")          # two seats on Artist
    assert _open_account(members[0], owner).status_code == 302
    assert _open_account(members[2], owner).status_code == 404


def test_the_last_seat_cannot_be_taken_twice():
    owner = _account("artist")
    assert store.add_team_invite(owner._id, "a-%s@x.net" % uuid.uuid4().hex[:6], "manager", limit=1) not in (None, "full")
    assert store.add_team_invite(owner._id, "b-%s@x.net" % uuid.uuid4().hex[:6], "manager", limit=1) == "full"


def test_only_a_change_that_went_through_is_recorded():
    owner, member = _account("pro"), _account("artist", "Auditor")
    _seat(owner, member, access="edit")
    _open_account(member, owner)
    member.post("/no-such-page", data={"x": "1"})
    assert store.list_team_audit(owner._id) == []
    member.post("/epk/save", json={"tagline": "recorded"})
    audit = store.list_team_audit(owner._id)
    assert audit and audit[0]["member_email"] == member._email


def test_the_chip_inside_the_account_is_the_artists():
    owner, member = _account("pro", "Chipowner"), _account("artist", "Chipmember")
    _seat(owner, member)
    _open_account(member, owner)
    page = member.get("/fans").get_data(as_text=True)
    assert "Team access" in page and member._email not in page.split("Leave this account")[1]


def test_deleting_the_account_takes_its_team_and_their_record():
    owner, member = _account("pro", "Leaver"), _account("artist", "Staying")
    _seat(owner, member, access="edit")
    store.add_team_audit(owner._id, member._id, "Staying", "POST", "/epk/save")
    owner.post("/account/delete", data={"confirm": owner._email})
    assert store.get_user(owner._id) is None
    assert store.list_team(owner._id) == [] and store.list_team_audit(owner._id) == []

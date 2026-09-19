"""Team access by plan (owner, 2026-09-19).

"a artist can invite someone that can read only not edit label and pro
different", then by question: an Artist's team reads only (2 seats); a Pro
member picks read or edit for each person (5 seats); a Label can also let an
editor manage its roster (no seat limit). A team member opens the artist's
account from their Portal; billing, settings, the team and the suites stay
with the account holder; every change an editor makes is recorded.
"""
import uuid

import pytest

import app as appmod
import db as store
import team_areas

PW = "team-access-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("RENDER", raising=False)


def _account(plan="artist", name="Artist"):
    email = "%s-%s@example.net" % (name.lower(), uuid.uuid4().hex[:8])
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    c._email, c._id = email, uid
    return c


def _invite(owner, member, access="read", roster=False, role="manager", areas=None):
    data = {"email": member._email, "role": role, "access": access, "areas_sent": "1",
            "areas": list(areas if areas is not None else team_areas.keys())}
    if roster:
        data["can_roster"] = "1"
    r = owner.post("/team/invite", data=data)
    assert r.get_json().get("ok"), r.get_json()
    token = [m for m in store.list_team(owner._id) if m["email"] == member._email][0]["invite_token"]
    assert member.post("/team/join/" + token, data={}).status_code == 302
    return [m for m in store.list_team(owner._id) if m["email"] == member._email][0]


def _open_account(member, owner):
    return member.post("/portal/%s/open" % owner._id)


# --- seats and what each plan may grant ------------------------------------------

@pytest.mark.parametrize("plan,seats", [("artist", 2), ("pro", 5)])
def test_each_plan_has_its_seats(plan, seats):
    owner = _account(plan)
    for i in range(seats):
        r = owner.post("/team/invite", data={"email": "seat%d-%s@example.net" % (i, uuid.uuid4().hex[:6]),
                                             "role": "assistant", "areas": ["fans"]})
        assert r.get_json()["ok"], r.get_json()
    r = owner.post("/team/invite", data={"email": "one-more-%s@example.net" % uuid.uuid4().hex[:6],
                                         "role": "assistant", "areas": ["fans"]})
    assert r.status_code == 402 and "all taken" in r.get_json()["error"]


def test_a_label_has_no_seat_limit():
    owner = _account("label")
    for i in range(7):
        r = owner.post("/team/invite", data={"email": "l%d-%s@example.net" % (i, uuid.uuid4().hex[:6]),
                                             "role": "assistant", "areas": ["fans"]})
        assert r.get_json()["ok"]


def test_an_artist_can_only_invite_readers():
    owner, member = _account("artist"), _account("artist", "Member")
    seat = _invite(owner, member, access="edit", roster=True)
    assert seat["access"] == "read" and not seat["can_roster"]
    assert "Can edit" not in owner.get("/team").get_data(as_text=True).split("Invite someone")[1].split("</form>")[0]


def test_pro_picks_per_person_and_only_label_grants_the_roster():
    pro, reader, editor = _account("pro"), _account("artist", "Reader"), _account("artist", "Editor")
    assert _invite(pro, reader, access="read")["access"] == "read"
    seat = _invite(pro, editor, access="edit", roster=True)
    assert seat["access"] == "edit" and not seat["can_roster"], "the roster is Label's"
    label, boss = _account("label"), _account("artist", "Boss")
    seat = _invite(label, boss, access="edit", roster=True)
    assert seat["access"] == "edit" and seat["can_roster"]


# --- working inside the account ---------------------------------------------------

def test_a_reader_sees_everything_and_changes_nothing():
    owner, member = _account("pro"), _account("artist", "Reader")
    _invite(owner, member, access="read")
    assert _open_account(member, owner).status_code == 302
    page = member.get("/command-center").get_data(as_text=True)
    assert "account as their manager" in page and "read-only access" in page
    r = member.post("/epk/save", json={"tagline": "changed by a reader"},
                    headers={"Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"})
    assert r.status_code == 403
    assert (store.get_epk(owner._id) or {}).get("data", {}).get("tagline") != "changed by a reader"


def test_an_editor_works_in_the_account_and_every_change_is_recorded():
    owner, member = _account("pro"), _account("artist", "Editor")
    _invite(owner, member, access="edit")
    _open_account(member, owner)
    assert "you can make changes" in member.get("/command-center").get_data(as_text=True)
    r = member.post("/epk/save", json={"tagline": "set by the editor"})
    assert r.status_code == 200
    assert store.get_epk(owner._id)["data"]["tagline"] == "set by the editor"
    audit = store.list_team_audit(owner._id)
    assert audit and audit[0]["path"] == "/epk/save" and audit[0]["member_name"] == "Editor"
    assert "Changes your team made" in owner.get("/team").get_data(as_text=True)


@pytest.mark.parametrize("path", ["/billing", "/settings", "/team", "/suites/go/reach", "/referrals"])
def test_billing_settings_team_and_suites_stay_with_the_account_holder(path):
    owner, member = _account("label"), _account("artist", "Editor")
    _invite(owner, member, access="edit", roster=True)
    _open_account(member, owner)
    r = member.get(path)
    assert r.status_code == 302 and "team=blocked" in r.headers["Location"], path


def test_a_downgrade_turns_an_editor_into_a_reader_on_the_next_click():
    owner, member = _account("pro"), _account("artist", "Editor")
    _invite(owner, member, access="edit")
    _open_account(member, owner)
    store.set_user_plan(owner._id, "artist")
    r = member.post("/epk/save", json={"tagline": "after the downgrade"},
                    headers={"Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty"})
    assert r.status_code == 403


def test_removing_a_member_ends_their_access_at_once():
    owner, member = _account("pro"), _account("artist", "Gone")
    seat = _invite(owner, member, access="edit")
    _open_account(member, owner)
    store.remove_team_member(owner._id, seat["id"])
    page = member.get("/command-center").get_data(as_text=True)
    assert "account as their" not in page
    with member.session_transaction() as s:
        assert "team_as" not in s


def test_leaving_returns_to_your_own_account():
    owner, member = _account("pro"), _account("artist", "Visitor")
    _invite(owner, member)
    _open_account(member, owner)
    member.post("/portal/leave")
    with member.session_transaction() as s:
        assert "team_as" not in s


def test_only_a_roster_manager_changes_a_labels_roster():
    label, plain, boss = _account("label"), _account("artist", "Plain"), _account("artist", "Boss")
    _invite(label, plain, access="edit")
    _invite(label, boss, access="edit", roster=True)
    _open_account(plain, label)
    r = plain.post("/roster/invite", data={"email": "new-%s@example.net" % uuid.uuid4().hex[:6]})
    assert r.status_code == 302 and "team=readonly" in r.headers["Location"]
    _open_account(boss, label)
    target = "signee-%s@example.net" % uuid.uuid4().hex[:6]
    boss.post("/roster/invite", data={"email": target})
    assert any(m["email"] == target for m in store.list_roster(label._id))


def test_the_owners_account_and_the_demo_are_never_opened(monkeypatch):
    owner = _account("label", "Owner")
    monkeypatch.setenv("OWNER_EMAILS", owner._email)
    member = _account("artist", "Staff")
    store.add_team_invite(owner._id, member._email, "manager", "edit")
    token = [m for m in store.list_team(owner._id) if m["email"] == member._email][0]["invite_token"]
    member.post("/team/join/" + token, data={})
    assert _open_account(member, owner).status_code == 404


def test_owner_only_doors_are_shut_in_team_mode():
    import sales_switch
    store.set_kv(sales_switch.KEY, "off")
    owner, member = _account("label"), _account("artist", "Editor")
    _invite(owner, member, access="edit")
    _open_account(member, owner)
    r = member.post("/admin/online-sales", data={"on": "1"})
    assert r.status_code == 302 and "team=blocked" in r.headers["Location"]
    assert not sales_switch.is_on()

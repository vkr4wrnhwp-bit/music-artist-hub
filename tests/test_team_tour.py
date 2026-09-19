"""Tour, the Tour Board and the Press Desk open to team seats (owner,
2026-09-19).

They used to read the signed-in person rather than the account a request
works in, so a seat inside the artist's account would have shown and
changed the member's own. They now resolve the account the way Studio
does, and open through their rooms (Stage; the Press Desk is Marketing).
What stays the account holder's stays shut: accepting a tour invitation,
the tour's crew invitations and public share links, deleting a tour, and
the artist's own record of what they have seen.
"""
import uuid

import pytest

import app as appmod
import board_store as bs
import db as store
import press_store
import team_areas
import tour_store as ts

PW = "team-tour-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("SUITE_GATES", raising=False)
    monkeypatch.setenv("MOCK_UP_TOUR", "off")


def _account(plan="pro", name="Artist"):
    email = "%s-%s@example.net" % (name.lower(), uuid.uuid4().hex[:8])
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    c._email, c._id, c._name = email, uid, name
    return c


def _seat(owner, member, access="edit", areas=None):
    data = {"email": member._email, "role": "manager", "access": access,
            "areas": list(areas if areas is not None else team_areas.keys())}
    r = owner.post("/team/invite", data=data)
    assert r.get_json().get("ok"), r.get_json()
    row = [m for m in store.list_team(owner._id) if m["email"] == member._email][0]
    member.post("/team/join/" + row["invite_token"], data={})
    r = member.post("/portal/%s/open" % owner._id)
    assert r.status_code == 302, "the seat opens"


def _tour(client, name):
    r = client.post("/tours/new", data={"name": name, "artist_name": name, "start_date": "2030-05-01",
                                        "end_date": "2030-05-10", "home_tz": "America/New_York",
                                        "currency": "USD"})
    assert r.status_code == 302, r.status_code
    return r.headers["Location"].rstrip("/").split("/")[-1]


def _show(client, tour_id, venue, date_="2030-05-02"):
    r = client.post("/tours/%s/days/add" % tour_id,
                    data={"date": date_, "kind": "show", "venue": venue, "city": "Nashville, TN",
                          "tz": "America/Chicago"})
    assert r.status_code == 302 and "/shows/" in r.headers["Location"], r.headers.get("Location")
    return r.headers["Location"].split("/shows/")[1].split("?")[0]


def _bounced(r, why):
    return r.status_code == 302 and ("team=%s" % why) in r.headers["Location"]


# --- Tour works in the artist's account -----------------------------------------

def test_a_stage_seat_sees_the_artists_tours_and_not_its_own():
    owner, member = _account("pro", "Headliner"), _account("pro", "Roadie")
    artist_tour = _tour(owner, "Artist Spring Run")
    own_tour = _tour(member, "Member Side Project")
    _seat(owner, member, areas=["stage"])
    page = member.get("/tours").get_data(as_text=True)
    assert "Artist Spring Run" in page
    assert "Member Side Project" not in page
    assert member.get("/tours/%s" % artist_tour).status_code == 200
    assert member.get("/tours/%s" % own_tour).status_code == 404, "their own tour is not the artist's"


def test_an_edit_seat_adds_a_show_to_the_artists_tour_under_its_own_name():
    owner, member = _account("pro", "Singer"), _account("artist", "Manny")
    tid = _tour(owner, "Summer Run")
    _seat(owner, member, areas=["stage"])
    sid = _show(member, tid, "Seat Hall")
    assert sid in {s["id"] for s in ts.list_shows(tid)}
    assert sid in {s["id"] for s in store.list_tour_shows(owner._id)}, "the show is the artist's"
    assert sid not in {s["id"] for s in store.list_tour_shows(member._id)}
    change = [c for c in ts.list_changes(tid) if c["entity_id"] == sid][0]
    assert change["actor_id"] == member._id
    assert change["actor_name"] == "Manny for Singer"
    audit = store.list_team_audit(owner._id)
    assert audit and audit[0]["path"] == "/tours/%s/days/add" % tid
    # A whole new tour made from the seat is the artist's too.
    made = _tour(member, "Seat Made Run")
    assert made in {t["id"] for t in ts.list_tours(owner._id)}
    assert made not in {t["id"] for t in ts.list_tours(member._id)}
    created = [c for c in ts.list_changes(made) if c["field"] == "created"][0]
    assert created["actor_id"] == member._id and created["actor_name"] == "Manny for Singer"


def test_the_artist_hears_about_a_seats_critical_change():
    owner, member = _account("pro", "Bandleader"), _account("artist", "Fixer")
    tid = _tour(owner, "Autumn Run")
    owner.post("/tours/%s/travel/add" % tid, data={"day_date": "2030-05-03", "mode": "air",
                                                   "number": "SB101"})
    leg = ts.list_travel(tid)[0]
    _seat(owner, member, areas=["stage"])
    before = len(store.list_notifications(owner._id))
    member.post("/tours/%s/travel/%s/edit" % (tid, leg["id"]), data={"action": "delete"})
    assert ts.list_travel(tid) == []
    notes = store.list_notifications(owner._id)
    assert len(notes) > before and "removed" in notes[0]["title"], "the artist is told"


def test_a_read_seat_changes_nothing_on_tour_board_or_press_desk():
    owner, member = _account("pro", "Quiet"), _account("artist", "Watcher")
    tid = _tour(owner, "Read Run")
    _seat(owner, member, access="read")
    shows = len(ts.list_shows(tid))
    r = member.post("/tours/%s/days/add" % tid, data={"date": "2030-05-04", "kind": "show",
                                                      "venue": "Nope Hall"})
    assert _bounced(r, "readonly") and len(ts.list_shows(tid)) == shows
    r = member.post("/tour-board/post", data={"kind": "artist", "title": "Should not post",
                                              "region_text": "Southeast US"})
    assert _bounced(r, "readonly") and bs.list_own(owner._id) == [] and bs.list_own(member._id) == []
    r = member.post("/press-desk/contacts/new", data={"name": "No One", "outlet": "Nowhere",
                                                      "email": "noone@example.com"})
    assert _bounced(r, "readonly")
    assert press_store.list_contacts(owner._id) == [] and press_store.list_contacts(member._id) == []


def test_a_seat_looking_at_tour_makes_nothing_for_the_artist(monkeypatch):
    monkeypatch.setenv("MOCK_UP_TOUR", "on")
    owner, member = _account("pro", "Newcomer"), _account("artist", "Browser")
    _seat(owner, member, access="edit")
    member.get("/tours")
    member.get("/tour")
    assert ts.list_tours(owner._id) == [], "no Mock Up Tour is built on a seat's visit"
    owner.get("/tours")
    assert [t["name"] for t in ts.list_tours(owner._id)] == ["Mock Up Tour"], "the artist's own visit still does"


def test_a_seat_looking_adopts_no_old_hub_show():
    owner, member = _account("pro", "Oldhub"), _account("artist", "Glancer")
    sid = store.add_tour_show(owner._id, "2030-06-01", "Old Hub Room", "Memphis, TN", "")
    _seat(owner, member, access="read")
    member.get("/tours")
    member.get("/tour")
    member.get("/tour/%s" % sid)
    assert ts.list_tours(owner._id) == [] and not store.get_tour_show(owner._id, sid).get("tour_id")
    owner.get("/tours")
    assert store.get_tour_show(owner._id, sid).get("tour_id"), "the artist's own visit adopts it"


def test_a_seat_without_the_stage_room_is_sent_back():
    owner, member = _account("pro", "Roomy"), _account("artist", "Fanonly")
    _seat(owner, member, areas=["fans"])
    for path in ("/tours", "/tour", "/tour-board", "/press-desk"):
        assert _bounced(member.get(path), "room"), path
    assert team_areas.room_for_path("/tour") == "stage"
    assert team_areas.room_for_path("/tour/abc/share") == "stage"


# --- what stays the account holder's -----------------------------------------------

def test_crew_invite_and_share_links_are_the_account_holders():
    owner, member = _account("pro", "Keyholder"), _account("artist", "Deputy")
    tid = _tour(owner, "Keys Run")
    sid = _show(owner, tid, "Link Room")
    crew_email = "crew-%s@example.net" % uuid.uuid4().hex[:6]
    owner.post("/tours/%s/team/invite" % tid, data={"email": crew_email, "name": "Crew", "role": "crew",
                                                    "scopes": ["view"]})
    join_token = ts.get_member_by_email(tid, crew_email)["invite_token"]
    owner.post("/tours/%s/share/new" % tid, data={"scope": "production", "show_id": sid})
    link = ts.list_share_links(tid)[0]
    assert join_token in owner.get("/tours/%s/team" % tid).get_data(as_text=True)
    assert link["token"] in owner.get("/tours/%s/share" % tid).get_data(as_text=True)
    assert link["token"] in owner.get("/tours/%s/shows/%s?tab=send" % (tid, sid)).get_data(as_text=True)
    owner_vip = owner.get("/tours/%s/shows/%s?tab=vip" % (tid, sid)).get_data(as_text=True)
    vip_token = ts.ensure_vip_link(tid, sid)
    assert "/vip/%s" % vip_token in owner_vip
    unopened = _show(owner, tid, "No VIP Yet", "2030-05-05")

    _seat(owner, member, access="edit")
    for path in ("/tours/%s/team" % tid, "/tours/%s/share" % tid,
                 "/tours/%s/share/%s/qr.svg" % (tid, link["id"])):
        assert _bounced(member.get(path), "blocked"), path
    r = member.post("/tours/%s/share/new" % tid, data={"scope": "day_sheet", "show_id": sid})
    assert r.status_code in (302, 403) and len(ts.list_share_links(tid)) == 1, "no link minted"
    r = member.post("/tours/%s/team/invite" % tid, data={"email": member._email, "role": "tour_manager",
                                                         "scopes": ["admin"]})
    assert r.status_code in (302, 403) and ts.get_member_by_email(tid, member._email) is None
    for path in ("/tours/%s" % tid, "/tours/%s/people" % tid,
                 "/tours/%s/shows/%s?tab=send" % (tid, sid), "/tours/%s/shows/%s?tab=vip" % (tid, sid),
                 "/tours/%s/shows/%s?tab=production" % (tid, sid)):
        body = member.get(path).get_data(as_text=True)
        assert link["token"] not in body and join_token not in body, path
        assert "/tours/%s/share" % tid not in body and "/tours/%s/team" % tid not in body, path
        assert vip_token not in body, path
    member.get("/tours/%s/shows/%s?tab=vip" % (tid, unopened))
    with store.get_db() as db:
        made = db.execute("SELECT COUNT(*) FROM tour_vip_links WHERE show_id = ?", (unopened,)).fetchone()[0]
    assert made == 0, "a seat's look mints no purchase link"


def test_a_seat_sends_the_advance_without_the_public_links(monkeypatch):
    import email_provider as emailer
    sent = []
    monkeypatch.setattr(emailer, "configured", lambda: True)
    monkeypatch.setattr(emailer, "using_shared_test_sender", lambda: False)
    monkeypatch.setattr(emailer, "send", lambda to, subject, html, *a, **k: sent.append((to, k.get("text") or html)) or True)
    owner, member = _account("pro", "Sender"), _account("artist", "Advancer")
    tid = _tour(owner, "Advance Run")
    sid = _show(owner, tid, "Advance Room")
    _seat(owner, member, access="edit", areas=["stage"])
    body = member.get("/tours/%s/shows/%s?tab=send" % (tid, sid)).get_data(as_text=True)
    assert "open without a login" in body
    r = member.post("/tours/%s/shows/%s/advance/send" % (tid, sid), data={"to": "venue@example.com"})
    assert r.status_code == 302 and "sent=1" in r.headers["Location"]
    assert sent and "/rider/" not in sent[-1][1] and "/tour-share/" not in sent[-1][1]
    assert not store.get_tour_show(owner._id, sid).get("share_token"), "no rider link was made"
    assert ts.list_share_links(tid) == [], "no production link was made"


def test_tours_join_is_shut_to_a_seat_and_the_invitation_stays_the_artists():
    other, owner, member = _account("pro", "Promoter"), _account("pro", "Invitee"), _account("artist", "Proxy")
    other_tid = _tour(other, "Promoter Package")
    other.post("/tours/%s/team/invite" % other_tid, data={"email": owner._email, "name": "Invitee",
                                                          "role": "artist", "scopes": ["view"]})
    token = ts.get_member_by_email(other_tid, owner._email)["invite_token"]
    _seat(owner, member, access="edit")
    assert token not in member.get("/notifications").get_data(as_text=True)
    r = member.get("/tours/join/%s" % token)
    assert _bounced(r, "join")
    assert ts.get_member_by_email(other_tid, owner._email)["status"] == "invited"
    assert ts.get_membership(other_tid, member._id) is None
    # The artist accepts from their own session; the seat still cannot
    # open another account's tour through the artist.
    owner.get("/tours/join/%s" % token)
    assert ts.get_membership(other_tid, owner._id)["status"] == "active"
    assert member.get("/tours/%s" % other_tid).status_code == 404
    assert "Promoter Package" not in member.get("/tours").get_data(as_text=True)
    assert "Promoter Package" in owner.get("/tours").get_data(as_text=True)


def test_what_the_artist_has_seen_stays_theirs():
    owner, member = _account("pro", "Reader"), _account("artist", "Skimmer")
    tid = _tour(owner, "Seen Run")
    owner.post("/tours/%s/travel/add" % tid, data={"day_date": "2030-05-03", "mode": "air", "number": "SB7"})
    leg = ts.list_travel(tid)[0]
    owner.post("/tours/%s/travel/%s/edit" % (tid, leg["id"]), data={"action": "delete"})
    critical = [c for c in ts.list_changes(tid) if c["severity"] == "critical"]
    assert critical
    ids = [c["id"] for c in ts.list_changes(tid)]
    before = ts.ack_state(tid, ids, owner._id)
    _seat(owner, member, access="edit")
    page = member.get("/tours/%s/changes?level=all" % tid).get_data(as_text=True)
    assert "Acknowledge</button>" not in page
    assert ts.ack_state(tid, ids, owner._id) == before, "looking marks nothing seen for the artist"
    r = member.post("/tours/%s/changes/%s/ack" % (tid, critical[0]["id"]))
    assert r.status_code == 403
    assert ts.ack_state(tid, ids, owner._id) == before


def test_deleting_a_tour_is_the_account_holders():
    owner, member = _account("pro", "Owner"), _account("artist", "Tidier")
    tid = _tour(owner, "Keep Run")
    _seat(owner, member, access="edit")
    assert "Delete this tour" not in member.get("/tours/%s/settings" % tid).get_data(as_text=True)
    r = member.post("/tours/%s/settings" % tid, data={"action": "delete", "confirm": "Keep Run"})
    assert r.status_code == 403 and ts.get_tour(tid) is not None
    assert "Delete this tour" in owner.get("/tours/%s/settings" % tid).get_data(as_text=True)


def test_the_old_hub_share_form_is_the_account_holders():
    owner, member = _account("pro", "Hubber"), _account("artist", "Minter")
    sid = store.add_tour_show(owner._id, "2030-07-01", "Hub Room", "Austin, TX", "")
    _seat(owner, member, access="edit", areas=["stage"])
    assert _bounced(member.post("/tour/%s/share" % sid), "blocked")
    assert not store.get_tour_show(owner._id, sid).get("share_token")


def test_press_contacts_inside_tour_need_the_marketing_room():
    owner = _account("pro", "Pressed")
    tid = _tour(owner, "Press Run")
    owner.post("/press-desk/contacts/new", data={"name": "Quill Writer", "outlet": "Loud Weekly",
                                                 "email": "quill@example.com"})
    assert "Quill Writer" in owner.get("/tours/%s/people" % tid).get_data(as_text=True)
    stage_only = _account("artist", "Stagehand")
    _seat(owner, stage_only, areas=["stage"])
    assert "Quill Writer" not in stage_only.get("/tours/%s/people" % tid).get_data(as_text=True)
    both = _account("artist", "Publicist")
    _seat(owner, both, areas=["stage", "marketing"])
    assert "Quill Writer" in both.get("/tours/%s/people" % tid).get_data(as_text=True)


# --- the Tour Board --------------------------------------------------------------

def test_the_tour_board_is_the_artists():
    owner, member = _account("pro", "Poster"), _account("artist", "Boarder")
    r = owner.post("/tour-board/post", data={"kind": "artist", "title": "Artist wants openers",
                                             "region_text": "Southeast US", "region_code": "us-southeast"})
    artist_lid = r.headers["Location"].rsplit("/", 1)[1]
    r = member.post("/tour-board/post", data={"kind": "artist", "title": "Member side listing",
                                              "region_text": "Southeast US", "region_code": "us-southeast"})
    member_lid = r.headers["Location"].rsplit("/", 1)[1]
    replier = _account("artist", "Replier")
    r = replier.post("/tour-board/%s/reply" % artist_lid, data={"message": "We can open in October."})
    thread_id = r.headers["Location"].split("/thread/")[1].split("?")[0]
    unread = bs.unread_total(owner._id)
    assert unread == 1

    _seat(owner, member, access="edit", areas=["stage"])
    page = member.get("/tour-board").get_data(as_text=True)
    assert "/tour-board/%s/edit" % artist_lid in page, "the artist's listings are the seat's to work"
    assert "/tour-board/%s/edit" % member_lid not in page
    thread = member.get("/tour-board/thread/%s" % thread_id).get_data(as_text=True)
    assert "We can open in October." in thread
    assert bs.unread_total(owner._id) == unread, "reading leaves it unread for the artist"
    r = member.post("/tour-board/post", data={"kind": "artist", "title": "Posted by the seat",
                                              "region_text": "Southeast US", "region_code": "us-southeast"})
    lid = r.headers["Location"].rsplit("/", 1)[1]
    assert bs.get_listing(lid)["user_id"] == owner._id


# --- the Press Desk --------------------------------------------------------------

def test_the_press_desk_is_the_artists():
    owner, member = _account("pro", "Announcer"), _account("artist", "Flack")
    owner.post("/press-desk/contacts/new", data={"name": "Artist Contact", "outlet": "Big Mag",
                                                 "email": "big-%s@example.com" % uuid.uuid4().hex[:6]})
    member.post("/press-desk/contacts/new", data={"name": "Member Contact", "outlet": "Own Mag",
                                                  "email": "own-%s@example.com" % uuid.uuid4().hex[:6]})
    _seat(owner, member, access="edit", areas=["marketing"])
    page = member.get("/press-desk/contacts").get_data(as_text=True)
    assert "Artist Contact" in page and "Member Contact" not in page
    member.post("/press-desk/contacts/new", data={"name": "Seat Added", "outlet": "New Mag",
                                                  "email": "new-%s@example.com" % uuid.uuid4().hex[:6]})
    assert "Seat Added" in {c["name"] for c in press_store.list_contacts(owner._id)}
    assert "Seat Added" not in {c["name"] for c in press_store.list_contacts(member._id)}


def test_a_seat_opening_a_pitch_link_is_not_the_journalists_open():
    owner, member = _account("pro", "Pitcher"), _account("artist", "Clicker")
    owner.post("/press-desk/contacts/new", data={"name": "Dee Writer", "outlet": "Nightdrive",
                                                 "email": "dee-%s@example.com" % uuid.uuid4().hex[:6]})
    owner.post("/press-desk/announcements/new", data={"title": "New single", "kind": "Single",
                                                      "headline": "Artist announces a single",
                                                      "body": "Words."})
    release = press_store.list_releases(owner._id)[0]
    contact = press_store.list_contacts(owner._id)[0]
    owner.post("/press-desk/pitch/new", data={"release_id": release["id"], "contact_ids": [contact["id"]],
                                              "subject": "{artist}: {title}",
                                              "body": "Hi {name}: {link}", "mode": "own_inbox"})
    pitch = press_store.list_pitches(owner._id)[0]
    recipient = press_store.pitch_recipients(owner._id, pitch["id"])[0]
    token = recipient["token"]
    assert 'href="/press/%s"' % token in owner.get("/press-desk/pitch/%s" % pitch["id"]).get_data(as_text=True)

    _seat(owner, member, access="read", areas=["marketing"])
    page = member.get("/press-desk/pitch/%s" % pitch["id"]).get_data(as_text=True)
    assert 'href="/press/%s"' % token not in page and token not in page
    notes = len(store.list_notifications(owner._id))
    assert member.get("/press/%s" % token).status_code == 200
    again = press_store.pitch_recipients(owner._id, pitch["id"])[0]
    assert again["open_count"] == 0 and again["status"] == recipient["status"]
    assert len(store.list_notifications(owner._id)) == notes, "the artist is not told of a false open"


# --- nobody else changes -----------------------------------------------------------

def test_tour_crew_and_the_owner_work_as_before():
    owner, crew = _account("pro", "Boss"), _account("fan", "Driver")
    tid = _tour(owner, "Crew Run")
    owner.post("/tours/%s/team/invite" % tid, data={"email": crew._email, "name": "Driver", "role": "driver",
                                                    "scopes": ["view", "schedule"]})
    token = ts.get_member_by_email(tid, crew._email)["invite_token"]
    assert crew.get("/tours/join/%s" % token).status_code == 302
    assert ts.get_membership(tid, crew._id)["status"] == "active"
    assert crew.get("/tours/%s" % tid).status_code == 200
    assert "Crew Run" in crew.get("/tours").get_data(as_text=True)
    assert crew.get("/tours/%s/team" % tid).status_code == 403
    assert owner.get("/tours/%s/team" % tid).status_code == 200
    assert owner.get("/tours/%s/share" % tid).status_code == 200


# --- the review's findings (2026-09-19) ----------------------------------------------

def _money_seen(body):
    return "98765" in body or "98,765" in body


def test_outreach_follows_the_stage_room():
    """The Tour Board's outreach tracker is also on /network, a page in no
    room. Its rows and its three forms follow the Stage room there too, as
    they do on /tour-board/outreach."""
    owner, member = _account("pro", "Tracker"), _account("artist", "Fanhand")
    owner.post("/network/outreach/add", data={"contact": "Venue Booker Vee", "role": "booker",
                                              "stage": "saved", "notes": "call back"})
    row = store.list_outreach(owner._id)[0]
    assert "Venue Booker Vee" in owner.get("/network?tab=my").get_data(as_text=True)
    _seat(owner, member, access="edit", areas=["fans"])
    assert _bounced(member.get("/tour-board/outreach"), "room")
    assert "Venue Booker Vee" not in member.get("/network?tab=my").get_data(as_text=True)
    assert _bounced(member.post("/network/outreach/%s/delete" % row["id"]), "room")
    assert _bounced(member.post("/network/outreach/%s/stage" % row["id"], data={"stage": "pitched"}), "room")
    assert _bounced(member.post("/network/outreach/add", data={"contact": "Seat Contact"}), "room")
    assert [(r["id"], r["stage"]) for r in store.list_outreach(owner._id)] == [(row["id"], "saved")]
    assert store.list_team_audit(owner._id) == []
    stage = _account("artist", "Booker")
    _seat(owner, stage, access="edit", areas=["stage"])
    assert "Venue Booker Vee" in stage.get("/network?tab=my").get_data(as_text=True)
    stage.post("/network/outreach/%s/stage" % row["id"], data={"stage": "pitched"})
    assert store.list_outreach(owner._id)[0]["stage"] == "pitched"


def test_head_writes_nothing_for_a_seat():
    """Flask answers HEAD with the GET view. Two handlers treated anything
    but GET as a POST, so a HEAD with a form body wrote as the artist and,
    being a HEAD, left no line on the artist's Team page."""
    owner, member = _account("pro", "Headline"), _account("artist", "Header")
    tid = _tour(owner, "Head Run")
    _show(owner, tid, "First Hall")
    _seat(owner, member, access="edit", areas=["stage"])
    listings = len(bs.list_own(owner._id))
    member.open("/tour-board/post", method="HEAD",
                data={"kind": "artist", "title": "Posted by HEAD", "region_text": "Southeast US"})
    assert len(bs.list_own(owner._id)) == listings
    shows = len(ts.list_shows(tid))
    csv_text = "date,city,venue,type\n2030-05-06,Memphis,Head Hall,show\n"
    member.open("/tours/%s/import" % tid, method="HEAD",
                data={"source": "csv", "text": csv_text, "action": "confirm", "pick": ["0"]})
    assert len(ts.list_shows(tid)) == shows
    assert store.list_team_audit(owner._id) == []
    # A plain HEAD still answers, and the real POST still works and is recorded.
    assert member.open("/tours/%s/import" % tid, method="HEAD").status_code == 200
    r = member.post("/tours/%s/import" % tid, data={"source": "csv", "text": csv_text, "action": "confirm",
                                                    "pick": ["0"]})
    assert r.status_code == 302 and len(ts.list_shows(tid)) == shows + 1
    assert [a["path"] for a in store.list_team_audit(owner._id)] == ["/tours/%s/import" % tid]
    # The artist's own HEAD was never a write either.
    owner.open("/tour-board/post", method="HEAD",
               data={"kind": "artist", "title": "Owner HEAD", "region_text": "Southeast US"})
    assert len(bs.list_own(owner._id)) == listings


def test_tour_money_needs_the_money_and_business_room():
    import tour_os
    owner = _account("pro", "Earner")
    tid = _tour(owner, "Paid Run")
    sid = _show(owner, tid, "Money Hall")
    owner.post("/tours/%s/shows/%s/money" % (tid, sid), data={"guarantee": "98765"})
    assert str(ts.get_show(tid, sid)["guarantee"]) == "98765"
    owner.post("/tours/%s/expenses/add" % tid, data={"show_id": sid, "vendor": "Van hire", "amount": "450"})
    hub = store.add_tour_show(owner._id, "2030-08-01", "Hub Money Room", "Austin, TX", "")
    owner.post("/tour/%s/settlement" % hub, data={"guarantee": "54321"})
    assert "54321" in str(store.get_tour_show(owner._id, hub)["settlement"])

    pages = ["/tours", "/tours/%s" % tid, "/tours/%s/money.csv" % tid,
             "/tours/%s/shows/%s/settlement-summary" % (tid, sid),
             "/tours/%s/ask?q=What+is+the+projected+net%%3F" % tid]
    pages += ["/tours/%s/%s" % (tid, p) for _k, _l, p in tour_os.TOUR_TABS if p]
    pages += ["/tours/%s/shows/%s?tab=%s" % (tid, sid, k) for k, _l in tour_os.SHOW_TABS]
    owner_sees = [p for p in pages if _money_seen(owner.get(p).get_data(as_text=True))]
    assert "/tours/%s/money" % tid in owner_sees and "/tours/%s/money.csv" % tid in owner_sees
    assert "/tours/%s/shows/%s?tab=money" % (tid, sid) in owner_sees

    stage = _account("artist", "Roadmgr")
    _seat(owner, stage, access="edit", areas=["stage"])
    for path in pages:
        assert not _money_seen(stage.get(path).get_data(as_text=True)), path
    assert stage.get("/tours/%s/money" % tid).status_code == 403
    assert "Money and business" in stage.get("/tours/%s/money" % tid).get_data(as_text=True)
    r = stage.post("/tours/%s/shows/%s/money" % (tid, sid), data={"guarantee": "1"})
    assert r.status_code == 403 and str(ts.get_show(tid, sid)["guarantee"]) == "98765"
    r = stage.post("/tour/%s/settlement" % hub, data={"guarantee": "1"})
    assert r.status_code == 403 and "54321" in str(store.get_tour_show(owner._id, hub)["settlement"])
    assert store.list_team_audit(owner._id) == [], "a refusal is not a change"

    both = _account("artist", "Accountant")
    _seat(owner, both, access="edit", areas=["stage", "business"])
    assert _money_seen(both.get("/tours/%s/money" % tid).get_data(as_text=True))
    r = both.post("/tours/%s/shows/%s/money" % (tid, sid), data={"guarantee": "12345"})
    assert r.status_code == 302 and str(ts.get_show(tid, sid)["guarantee"]) == "12345"


def _pitch(owner):
    owner.post("/press-desk/contacts/new", data={"name": "Dee Writer", "outlet": "Nightdrive",
                                                 "email": "dee-%s@example.com" % uuid.uuid4().hex[:6]})
    owner.post("/press-desk/announcements/new", data={"title": "New single", "kind": "Single",
                                                      "headline": "Artist announces a single",
                                                      "body": "Words."})
    release = press_store.list_releases(owner._id)[0]
    contact = press_store.list_contacts(owner._id)[0]
    owner.post("/press-desk/pitch/new", data={"release_id": release["id"], "contact_ids": [contact["id"]],
                                              "subject": "{artist}: {title}",
                                              "body": "Hi {name}: {link}", "mode": "own_inbox"})
    pitch = press_store.list_pitches(owner._id)[0]
    return pitch, press_store.pitch_recipients(owner._id, pitch["id"])[0]["token"]


def test_an_edit_seat_is_not_handed_the_journalists_link():
    owner, member = _account("pro", "Plugger"), _account("artist", "Publicity")
    pitch, token = _pitch(owner)
    owner_page = owner.get("/press-desk/pitch/%s" % pitch["id"]).get_data(as_text=True)
    assert token in owner_page and "Open in my email" in owner_page
    _seat(owner, member, access="edit", areas=["marketing"])
    page = member.get("/press-desk/pitch/%s" % pitch["id"]).get_data(as_text=True)
    assert token not in page, "the tracked link is its own key to a public page"
    assert "Open in my email" not in page
    assert "Mark sent" in page, "an editor still keeps the record"


def test_stage_bridge_credentials_are_the_account_holders():
    import advance_store as adv
    import passport_store as ps
    import stage_bridge as sb
    owner, member = _account("pro", "Rigger"), _account("artist", "Patcher")
    pid = ps.create_passport(owner._id, artist_name="Rigger")
    ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Rigger", safe_start="-20 dB", sort=1)
    ps.publish(pid, owner._id)
    show_id = "show-" + uuid.uuid4().hex[:10]
    adv.attach(show_id, owner._id, pid)
    _seat(owner, member, access="edit", areas=["stage"])
    r = member.post("/stage/%s/bridge/register" % show_id, data={"name": "Seat Rack", "adapter": "simulator"})
    assert r.status_code == 403 and sb.device_for_show(show_id, owner._id) is None
    assert "/bridge/register" not in member.get("/stage/%s/bridge" % show_id).get_data(as_text=True)
    r = owner.post("/stage/%s/bridge/register" % show_id, data={"name": "Rack A", "adapter": "simulator"})
    assert r.status_code == 302 and "credentials=once" in r.headers["Location"]
    owner.get(r.headers["Location"])
    before = sb.device_for_show(show_id, owner._id)
    assert member.post("/stage/%s/bridge/rotate" % show_id).status_code == 403
    after = sb.device_for_show(show_id, owner._id)
    assert (after["token_hash"], after["signing_key"]) == (before["token_hash"], before["signing_key"])
    page = member.get("/stage/%s/bridge" % show_id).get_data(as_text=True)
    assert "/bridge/rotate" not in page and before["signing_key"] not in page
    # The emergency stop is still every seat's to press.
    assert member.post("/stage/%s/bridge/lockout" % show_id, data={"reason": "test"}).status_code == 302
    assert sb.device_for_show(show_id, owner._id)["lockout"]
    assert store.list_team_audit(owner._id)[0]["path"] == "/stage/%s/bridge/lockout" % show_id


def test_a_partner_acting_for_the_artist_works_the_artists_tour_under_their_own_name():
    """A partner staff member acting on an artist's behalf works the
    artist's account on every page (app.py current_user), so Tour, the
    Tour Board and the Press Desk follow it too. What must not happen:
    a change filed under the artist's own name, the artist left off the
    notice about it, or the staff member's look at a pitch link counted
    as the journalist's open (review, 2026-09-19). Each change goes on the
    partner's audit trail under the staff member's name."""
    import partner_store as pstore
    artist, staff = _account("pro", "Signee"), _account("pro", "Labelhand")
    artist_tid = _tour(artist, "Signee Artist Run")
    _tour(staff, "Staff Own Run")
    artist.post("/tours/%s/travel/add" % artist_tid, data={"day_date": "2030-05-03", "mode": "air",
                                                          "number": "SB77"})
    leg = ts.list_travel(artist_tid)[0]
    r = artist.post("/tour-board/post", data={"kind": "artist", "title": "Signee wants openers",
                                              "region_text": "Southeast US", "region_code": "us-southeast"})
    lid = r.headers["Location"].rsplit("/", 1)[1]
    replier = _account("artist", "Opener")
    r = replier.post("/tour-board/%s/reply" % lid, data={"message": "We can open."})
    thread_id = r.headers["Location"].split("/thread/")[1].split("?")[0]
    pitch, token = _pitch(artist)

    partner_id = pstore.create_partner("Label %s" % uuid.uuid4().hex[:6], slug="l-" + uuid.uuid4().hex[:8])
    pstore.add_member(partner_id, staff._email, name="Labelhand", role="admin", user_id=staff._id)
    pstore.attach_user(partner_id, artist._id)
    staff.post("/partner/act/%s" % artist._id)
    with staff.session_transaction() as s:
        assert s.get("acting_as") == artist._id

    # Tour: the artist's, as on every other page.
    page = staff.get("/tours").get_data(as_text=True)
    assert "Signee Artist Run" in page and "Staff Own Run" not in page
    assert staff.get("/tours/%s" % artist_tid).status_code == 200
    sid = _show(staff, artist_tid, "Proxy Hall", "2030-05-04")
    assert sid in {s["id"] for s in store.list_tour_shows(artist._id)}, "the show is the artist's"
    change = [c for c in ts.list_changes(artist_tid) if c["entity_id"] == sid][0]
    assert change["actor_id"] == staff._id, "the change is the staff member's, not the artist's"
    assert change["actor_name"] == "Labelhand for Signee"
    made = _tour(staff, "Label Made Run")
    assert made in {t["id"] for t in ts.list_tours(artist._id)}
    created = [c for c in ts.list_changes(made) if c["field"] == "created"][0]
    assert created["actor_id"] == staff._id and created["actor_name"] == "Labelhand for Signee"
    # The artist hears about a critical change the partner made.
    before = len(store.list_notifications(artist._id))
    staff.post("/tours/%s/travel/%s/edit" % (artist_tid, leg["id"]), data={"action": "delete"})
    assert ts.list_travel(artist_tid) == []
    notes = store.list_notifications(artist._id)
    assert len(notes) > before and "removed" in notes[0]["title"], "the artist is told"
    # Each change is on the partner's audit trail under the staff member's name.
    trail = [t for t in pstore.audit_trail(partner_id) if t["action"] == "act_as.change"]
    assert trail and trail[0]["actor_email"] == staff._email
    assert trail[0]["subject_user_id"] == artist._id
    assert "POST /tours/%s/travel/%s/edit" % (artist_tid, leg["id"]) in {t["detail"] for t in trail}
    assert "POST /tours/%s/days/add" % artist_tid in {t["detail"] for t in trail}

    # The Tour Board and the Press Desk: the artist's too.
    assert staff.get("/tour-board/thread/%s" % thread_id).status_code == 200
    assert "/tour-board/%s/edit" % lid in staff.get("/tour-board").get_data(as_text=True)
    page = staff.get("/press-desk/pitch/%s" % pitch["id"]).get_data(as_text=True)
    assert 'href="/press/%s"' % token not in page, "the link is shown, not a way to open it"
    notes = len(store.list_notifications(artist._id))
    assert staff.get("/press/%s" % token).status_code == 200
    again = press_store.pitch_recipients(artist._id, pitch["id"])[0]
    assert again["open_count"] == 0 and again["status"] != "opened"
    assert len(store.list_notifications(artist._id)) == notes, "the artist is not told of a false open"

    # Handing the workspace back returns the staff member to their own tours.
    staff.post("/partner/act/stop")
    page = staff.get("/tours").get_data(as_text=True)
    assert "Staff Own Run" in page and "Signee Artist Run" not in page

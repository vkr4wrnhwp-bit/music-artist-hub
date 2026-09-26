"""The Action Center (owner's mockup + crawl, 2026-09-23).

The crawl found the underlying status engine working and the action itself
"just a persistent title with state buttons". Each test below pins one of
its ten findings, or a rule the rebuild had to keep: dismissed work set
aside from the completion figure, open actions on the Command Center, a
real assignee, priority shown and filterable, a details page with edit,
delete for what was typed in by hand, the room/record/source an action
belongs to, one name per state, a confirmation with three ways on, and
safe defaults that remember the last choice.
"""
import re
import uuid
from datetime import date, timedelta

import pytest

import account_state
import actions_center as acx
import app as appmod
import command_center as cc
import db as store
import links_store as mls
import team_areas

PW = "actions-center-1"
TODAY = date(2026, 10, 3)


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("RENDER", raising=False)


def _account(plan="label", name="Oddko"):
    email = "%s-%s@example.net" % (name.lower(), uuid.uuid4().hex[:8])
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    c._email, c._id = email, uid
    return c


def _seat(owner, member, access="read"):
    r = owner.post("/team/invite", data={"email": member._email, "role": "manager", "access": access,
                                         "areas_sent": "1", "areas": list(team_areas.keys())})
    assert r.get_json().get("ok"), r.get_json()
    row = [m for m in store.list_team(owner._id) if m["email"] == member._email][0]
    member.post("/team/join/" + row["invite_token"], data={})
    member.post("/portal/%s/open" % owner._id)


def _create(c, **fields):
    data = {"title": "An action", "category": "general", "priority": "medium"}
    data.update(fields)
    r = c.post("/actions", data=data)
    assert r.status_code == 302
    return re.search(r"created=([0-9a-f]+)", r.headers["Location"]).group(1)


def _page(c, path="/actions"):
    return c.get(path).get_data(as_text=True)


def _summary(page):
    return page.split('aria-label="Board summary"', 1)[1].split("</section>", 1)[0]


def _list(page):
    return page.split('id="ac-list-h"', 1)[1].split("</section>", 1)[0]


def _row(page, title):
    return _list(page).split(title, 1)[1].split("</li>", 1)[0]


# ---- finding 2: dismissed work is set aside, not unfinished ------------------

def test_dismissed_work_is_not_counted_as_unfinished():
    rows = [{"status": "dismissed", "priority": "low", "due_date": ""}]
    s = cc.board_summary(rows, TODAY)
    assert (s["total"], s["complete"], s["pct"], s["dismissed"]) == (0, 0, 0, 1)
    rows += [{"status": "complete", "priority": "low", "due_date": ""},
             {"status": "new", "priority": "low", "due_date": ""}]
    s = cc.board_summary(rows, TODAY)
    assert (s["total"], s["complete"], s["pct"], s["dismissed"]) == (2, 1, 50, 1)


def test_the_page_reports_dismissed_on_its_own_line():
    c = _account()
    aid = _create(c, title="Only one")
    c.post("/actions", data={"action_id": aid, "status": "dismissed"})
    summary = _summary(_page(c))
    assert "of 1</b> complete" not in summary and "%" not in summary
    assert "Nothing open. 1 dismissed action set aside, not counted." in summary
    _create(c, title="Second")
    page = _page(c, "/actions?status=all")
    assert "<b>0 of 1</b> complete" in page and "<b>1</b> dismissed, not counted" in page


# ---- finding 1: open actions reach the Command Center ------------------------

def test_any_open_action_replaces_nothing_needs_attention_on_the_page_from_zero():
    c = _account()
    assert "Nothing needs attention yet" in _page(c, "/command-center")
    # the crawl's own case: low priority, no due date, reopened
    aid = _create(c, title="[AUDIT TEST] Verify Actions workflow", priority="low")
    c.post("/actions", data={"action_id": aid, "status": "dismissed"})
    assert "Nothing needs attention yet" in _page(c, "/command-center")
    c.post("/actions", data={"action_id": aid, "status": "new"})
    page = _page(c, "/command-center")
    assert "Nothing needs attention yet" not in page
    assert "“[AUDIT TEST] Verify Actions workflow” is on your Actions board." in page
    assert 'href="/actions/%s"' % aid in page and "Open action" in page
    assert "Open Actions" not in page and "Today's Priorities" not in page, "the zero page keeps one panel"


def test_an_action_that_needs_attention_comes_before_the_link_step():
    campaign = {"id": "c1", "title": "Higher Places", "status": "draft"}
    urgent = {"id": "a1", "title": "Fix missing ISRC", "status": "new", "priority": "high",
              "due_date": "", "room": "releases"}
    calm = dict(urgent, id="a2", priority="low", title="Someday")
    assert account_state.attention([campaign], [urgent], TODAY)["href"] == "/actions/a1"
    assert account_state.attention([campaign], [calm], TODAY)["href"] == "/links/c1/edit"
    assert account_state.attention([], [calm], TODAY)["href"] == "/actions/a2"
    assert account_state.attention([campaign]) is not None, "the one-argument call still works"


def test_the_compass_names_the_top_open_action_when_there_is_no_alert():
    ess = {"complete": True}
    act = {"id": "a9", "title": "Send the advance"}
    nxt = account_state.compass(ess, [], [], False, [act])[1]
    assert nxt == {"k": "Next action", "v": "Send the advance", "href": "/actions/a9"}
    assert account_state.compass(ess, [], [], False)[1]["v"] == "Nothing on fire."


def test_open_actions_rank_the_most_urgent_first():
    rows = [
        {"id": "low", "status": "new", "priority": "low", "due_date": "", "created": "1"},
        {"id": "late", "status": "in_progress", "priority": "medium", "due_date": "2026-09-30", "created": "2"},
        {"id": "high", "status": "new", "priority": "high", "due_date": "", "created": "3"},
        {"id": "done", "status": "complete", "priority": "high", "due_date": "", "created": "4"},
    ]
    assert [a["id"] for a in cc.rank_open(rows, TODAY)] == ["late", "high", "low"]


# ---- finding 3: a real assignee ----------------------------------------------

def test_an_action_is_assigned_to_a_real_person_on_the_team():
    owner, member = _account(), _account(name="Mia")
    _seat(owner, member, access="edit")
    page = _page(owner)
    assert '<option value="%s" selected>Me</option>' % owner._id in page
    assert '<option value="%s">Mia</option>' % member._id in page
    _create(owner, title="Mix notes", assignee=member._id)
    page = _page(owner, "/actions?status=all")
    assert "Assigned to Mia" in page
    # on the seat's own screen it is theirs
    assert "Assigned to you" in _page(member, "/actions?status=all")


def test_a_stranger_cannot_be_assigned():
    c = _account()
    aid = _create(c, title="Stray", assignee="not-a-member")
    assert cc.get_action(aid, c._id)["assignee_id"] == ""


def test_a_seat_is_not_shown_the_rest_of_the_team():
    owner, mia, sam = _account(), _account(name="Mia"), _account(name="Sam")
    _seat(owner, mia, access="edit")
    _seat(owner, sam, access="edit")
    _create(owner, title="Mix it", assignee=sam._id)
    listed = _list(_page(mia, "/actions?status=all"))
    assert "Assigned to a teammate" in listed and "Sam" not in listed
    assert "Sam" not in _page(mia).split('id="ac-f-assignee"', 1)[1].split("</select>", 1)[0]


def test_a_read_seat_sees_the_board_and_is_offered_no_change():
    owner, member = _account(), _account(name="Rey")
    _seat(owner, member, access="read")
    _create(owner, title="Owner work")
    page = _page(member, "/actions?status=all")
    assert "Owner work" in page and "New Action" not in page
    assert "Create action" not in page and 'name="status"' not in page
    assert "Actions are created and changed by the account holder" in page


# ---- finding 4: priority, due date, account and room are shown ---------------

def test_the_row_shows_room_type_priority_due_and_assignee():
    c = _account()
    _create(c, title="Fix missing ISRC", room="releases", category="metadata", priority="high",
            due_date=date.today().isoformat(), assignee=c._id)
    page = _page(c)
    row = _row(page, "Fix missing ISRC")
    for words in ("Releases", "Metadata", "High", "Due today", "Assigned to you"):
        assert words in row, words
    assert "Oddko &middot; Label" in page, "the account chip says whose board it is"


def test_needs_attention_is_high_overdue_or_due_soon_and_is_filterable():
    assert cc.needs_attention({"status": "new", "priority": "high", "due_date": ""}, TODAY)
    assert cc.needs_attention({"status": "new", "priority": "low", "due_date": "2026-10-06"}, TODAY)
    assert not cc.needs_attention({"status": "new", "priority": "low", "due_date": "2026-10-07"}, TODAY)
    assert not cc.needs_attention({"status": "complete", "priority": "high", "due_date": ""}, TODAY)
    c = _account()
    _create(c, title="Urgent thing", priority="high")
    _create(c, title="Calm thing", priority="low")
    page = _page(c)
    assert "High priority, overdue, or due within 3 days." in page, "the board opens on Needs attention"
    listed = page.split('id="ac-list-h"', 1)[1]
    assert "Urgent thing" in listed and "Calm thing" not in listed


def test_due_words():
    row = lambda d, s="new": {"due_date": d, "status": s}
    assert acx.due(row("2026-10-03"), TODAY) == ("Due today", True)
    assert acx.due(row("2026-10-04"), TODAY) == ("Due tomorrow", True)
    assert acx.due(row("2026-10-07"), TODAY) == ("Due Oct 7", False)
    assert acx.due(row("2026-10-01"), TODAY) == ("Overdue · was due Oct 1", True)
    assert acx.due(row("2026-10-01", "complete"), TODAY) == ("Due Oct 1", False)
    assert acx.due(row("2027-01-05"), TODAY) == ("Due Jan 5, 2027", False)
    assert acx.due(row(""), TODAY) == ("", False)


def test_a_due_date_that_is_not_a_date_is_not_kept():
    c = _account()
    aid = _create(c, due_date="next week")
    assert cc.get_action(aid, c._id)["due_date"] == ""


# ---- finding 5: a details page with edit ------------------------------------

def test_every_field_can_be_changed_after_creation():
    c = _account()
    camp = mls.create_campaign(c._id, "md-%s" % uuid.uuid4().hex[:6], {"title": "Midnight Drive"})
    aid = _create(c, title="First words")
    page = _page(c, "/actions/%s" % aid)
    assert "Save changes" in page and "This action" in page
    r = c.post("/actions/%s" % aid, data={
        "title": "Better words", "room": "publishing", "category": "rights", "priority": "low",
        "due_date": "2026-11-01", "assignee": c._id, "related": "release:%s" % camp,
        "description": "What done looks like."})
    assert r.headers["Location"].endswith("/actions/%s?saved=1" % aid)
    a = cc.get_action(aid, c._id)
    assert (a["title"], a["room"], a["category"], a["priority"], a["due_date"]) == \
        ("Better words", "publishing", "rights", "low", "2026-11-01")
    assert (a["entity_type"], a["entity_id"], a["description"]) == ("release", camp, "What done looks like.")
    assert "Changes saved." in _page(c, "/actions/%s?saved=1" % aid)


def test_another_accounts_action_is_not_there():
    a, b = _account(), _account(name="Other")
    aid = _create(a, title="Private")
    assert b.get("/actions/%s" % aid).status_code == 404
    b.post("/actions", data={"action_id": aid, "status": "complete"})
    assert b.post("/actions/%s/delete" % aid).status_code == 404
    assert cc.get_action(aid, a._id)["status"] == "new"


# ---- finding 6: delete what was typed in; dismiss what a check raised ---------

def test_an_action_typed_in_by_hand_can_be_deleted():
    c = _account()
    aid = _create(c, title="Oops")
    assert "Delete&hellip;" in _page(c, "/actions?status=all")
    page = _page(c, "/actions/%s?confirm=delete" % aid)
    assert 'id="ac-delete"' in page and '<details class="ac-confirm" open>' in page
    r = c.post("/actions/%s/delete" % aid)
    assert cc.get_action(aid, c._id) is None
    assert "Action deleted." in _page(c, r.headers["Location"])


def test_an_action_a_check_raised_is_dismissed_not_deleted():
    c = _account()
    c.post("/actions/from-alert", data={"title": "Raise trust score: Splits", "category": "rights",
                                        "source": "trust_score"},
           headers={"Referer": "http://localhost/trust-score"})
    a = [x for x in cc.list_actions(c._id) if x["title"].startswith("Raise trust")][0]
    assert not cc.deletable(a) and a["source"] == "trust_score"
    page = _page(c, "/actions/%s" % a["id"])
    # "From the Trust score raised this action" was the label pasted into a
    # sentence; this pinned it until the audit of 2026-09-23.
    assert "Why this cannot be deleted" in page and "The Trust score raised this action" in page
    assert "From the Trust score raised" not in page
    c.post("/actions/%s/delete" % a["id"])
    assert cc.get_action(a["id"], c._id) is not None


# ---- finding 7: the room, the record and the source --------------------------

def test_a_release_check_keeps_its_release_its_room_and_the_way_back():
    c = _account()
    camp = mls.create_campaign(c._id, "md-%s" % uuid.uuid4().hex[:6], {"title": "Midnight Drive"})
    r = c.post("/actions/from-alert", data={
        "title": "Midnight Drive: Cover art set", "category": "release", "source": "release_check",
        "room": "releases", "entity_type": "release", "entity_id": camp},
        headers={"Referer": "http://localhost/releases/autopilot?campaign=%s" % camp})
    assert "action=Midnight" in r.headers["Location"] and "action_id=" in r.headers["Location"]
    a = [x for x in cc.list_actions(c._id) if x["title"].startswith("Midnight Drive:")][0]
    assert (a["source"], a["room"], a["entity_type"], a["entity_id"]) == ("release_check", "releases", "release", camp)
    assert a["source_href"] == "/releases/autopilot?campaign=%s" % camp
    row = _row(_page(c, "/actions?status=all"), "Midnight Drive: Cover art set")
    assert "Midnight Drive · Release" in row and "From Release Check" in row
    assert 'href="/releases/autopilot?campaign=%s">Open Release' % camp in row


def test_a_record_of_another_account_is_not_kept():
    a, b = _account(), _account(name="Other")
    theirs = mls.create_campaign(b._id, "x-%s" % uuid.uuid4().hex[:6], {"title": "Not yours"})
    a.post("/actions/from-alert", data={"title": "Sneaky", "entity_type": "release", "entity_id": theirs},
           headers={"Referer": "http://localhost/command-center"})
    row = [x for x in cc.list_actions(a._id) if x["title"] == "Sneaky"][0]
    assert (row["entity_type"], row["entity_id"]) == ("", "")
    aid = _create(a, title="Also sneaky", related="release:%s" % theirs)
    assert cc.get_action(aid, a._id)["entity_id"] == ""


def test_with_no_record_the_second_button_opens_the_room():
    c = _account()
    _create(c, title="Room work", room="publishing")
    row = _row(_page(c, "/actions?status=all"), "Room work")
    assert 'href="/room/publishing">Open Publishing' in row and "No linked record" in row


def test_a_record_that_is_gone_says_so_and_survives_an_edit():
    c = _account()
    aid = cc.create_action(c._id, "About a song", entity_type="song", entity_id="gone-track", source="manual")
    page = _page(c, "/actions/%s" % aid)
    assert "This song is no longer on file" in page and 'value="__keep__" selected' in page
    c.post("/actions/%s" % aid, data={"title": "About a song", "related": "__keep__", "priority": "high"})
    a = cc.get_action(aid, c._id)
    assert (a["entity_type"], a["entity_id"], a["priority"]) == ("song", "gone-track", "high")


def test_the_way_back_to_a_source_is_never_another_site():
    c = _account()
    c.get("/actions?returnTo=//evil.example/x")
    aid = _create(c, title="Hop", returnTo="https://evil.example/")
    assert cc.get_action(aid, c._id)["source_href"] == ""
    aid = _create(c, title="Hop 2", returnTo="/room/stage", source="release_check")
    assert cc.get_action(aid, c._id)["source_href"] == "/room/stage"


def test_a_tour_task_says_where_it_came_from_and_keeps_its_title():
    import tour_store as ts
    c = _account()
    tid = ts.create_tour(c._id, {"name": "Autumn run"})
    c.post("/tours/%s/tasks/add" % tid, data={"title": "Book the van"})
    a = [x for x in cc.list_actions(c._id) if x["title"] == "Book the van"]
    assert a and a[0]["source"] == "tour_task" and a[0]["room"] == "stage"


# ---- finding 8: one name per state, and the board is the whole list ----------

def test_the_list_filters_and_the_board_use_the_same_state_names():
    c = _account()
    aid = _create(c, title="Card")
    listing = _page(c, "/actions?status=all")
    for name in ("Not started", "In progress", "Complete", "Dismissed"):
        assert name in listing, name
    board = _page(c, "/actions?view=board")
    cols = re.findall(r'<h2 class="ac-col-h" id="ac-col-[a-z_]+">([^<]+?) <', board)
    assert cols == ["Not started", "In progress", "Complete", "Dismissed"]
    for old in (">To do", ">To Do", ">Done<", ">New<"):
        assert old not in board and old not in listing, old
    card = board.split("ac-col-new", 1)[1].split("ac-col-in_progress", 1)[0]
    assert 'value="dismissed">Dismiss</button>' in card, "Dismiss on a new card"


def test_a_status_change_goes_back_to_the_same_view():
    c = _account()
    aid = _create(c, title="Stay here")
    r = c.post("/actions", data={"action_id": aid, "status": "in_progress", "back": "/actions?status=all&view=board"})
    assert r.headers["Location"].endswith("/actions?status=all&view=board")
    r = c.post("/actions", data={"action_id": aid, "status": "complete", "back": "https://evil.example/"})
    assert r.headers["Location"].endswith("/actions")


# ---- finding 9: "Create action" and a confirmation with three ways on --------

def test_creation_is_confirmed_with_view_return_and_add_another():
    c = _account()
    page = _page(c)
    assert ">Create action</button>" in page and ">Add</button>" not in page
    aid = _create(c, title="Confirm me", source="release_check", returnTo="/releases/autopilot")
    page = _page(c, "/actions?created=%s" % aid)
    assert "Action created." in page and "&ldquo;Confirm me&rdquo;" in page
    assert 'href="/actions/%s">View action' % aid in page
    assert 'href="/releases/autopilot">Return to source' in page
    assert 'href="#ac-title">Add another' in page and 'id="ac-title"' in page


def test_the_confirmation_is_said_by_the_saved_row_not_the_param():
    a, b = _account(), _account(name="Other")
    aid = _create(b, title="Theirs")
    assert "Action created." not in _page(a, "/actions?created=%s" % aid)
    assert "Action created." not in _page(a, "/actions?created=nope")


def test_the_shared_confirmation_links_to_the_action_it_made():
    c = _account()
    r = c.post("/actions/from-alert", data={"title": "TS action", "category": "rights"},
               headers={"Referer": "http://localhost/trust-score"})
    loc = r.headers["Location"]
    aid = re.search(r"action_id=([0-9a-f]+)", loc).group(1)
    page = _page(c, "/trust-score?action=TS%20action&action_id=" + aid)
    assert 'href="/actions/%s" class="underline">View action' % aid in page
    # An id that is not this account's action says nothing at all: the
    # sentence used to be said by ?action= alone, and this test pinned it
    # (audit, 2026-09-23).
    page = _page(c, "/trust-score?action=TS%20action&action_id=0000")
    assert "is on your" not in page and "View action" not in page


# ---- finding 10: safe defaults, and the last choice is remembered ------------

def test_the_form_starts_safe_and_remembers_the_last_choices():
    c = _account()
    page = _page(c)
    assert '<option value="" selected' not in page.split('id="ac-f-room"', 1)[1][:80], "No room is first and default"
    assert 'value="general" selected' in page and 'value="medium" selected' in page
    assert 'value="release" selected' not in page
    r = c.post("/actions", data={"title": "Low general", "category": "general", "priority": "low"})
    page = _page(c, r.headers["Location"])
    assert 'value="general" selected' in page and 'value="low" selected' in page


def test_the_form_controls_all_carry_a_name():
    page = _page(_account())
    form = page[page.index("New Action"):page.index("</form>", page.index("New Action"))]
    for control in re.finditer(r"<(input|select|textarea)\b([^>]*)>", form):
        attrs = control.group(2)
        if 'type="hidden"' not in attrs:
            assert "id=" in attrs or "aria-label=" in attrs, attrs[:90]


# ---- the audit of 2026-09-23 (audit-group-mkact, actions-1 .. actions-23) --

import io  # noqa: E402


def _demo_client():
    c = appmod.app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = store.get_user_by_email("demo@streetbanker.io")["id"]
    return c


def _statement(uid):
    store.save_statement(uid, "s.csv", [{"title": "Song", "source": "Spotify",
                                         "amount": 10.0, "period": "2026-06"}])


def _boom(*_a, **_k):
    raise RuntimeError("store down")


def test_actions_1_a_tab_in_return_to_is_never_the_way_back():
    """Browsers strip a tab from a URL, so "/<TAB>/evil.example" is
    "//evil.example": another site."""
    c = _account()
    aid = _create(c, title="Tabbed", returnTo="/\t/evil.example/phish", source="release_check")
    assert cc.get_action(aid, c._id)["source_href"] == ""
    page = _page(c, "/actions?title=Fix+ISRC&source=release_check&returnTo=/%09/evil.example")
    assert 'name="returnTo"' not in page and "evil.example" not in page
    assert "evil.example" not in _page(c, "/royalties?returnTo=/%09/evil.example/back")
    for bad in ("/\t/x.example", "/\n/x.example", "/\r/x", "/\x0b/x", "/\x7f/x"):
        assert cc._safe_href(bad) == "", repr(bad)
    assert cc._safe_href("/room/stage") == "/room/stage"


def test_actions_2_a_failed_read_is_the_error_page_at_503(monkeypatch):
    c = _account()
    _create(c, title="Kept safe")
    monkeypatch.setitem(appmod.app.config, "PROPAGATE_EXCEPTIONS", False)
    monkeypatch.setattr(cc, "list_actions", _boom)
    r = c.get("/actions")
    assert r.status_code == 503
    body = r.get_data(as_text=True)
    assert "We could not load your actions" in body and "No actions yet" not in body
    assert 'href="/actions">Try again' in body and 'href="/command-center"' in body
    monkeypatch.undo()
    monkeypatch.setitem(appmod.app.config, "PROPAGATE_EXCEPTIONS", False)
    monkeypatch.setattr(cc, "open_actions", _boom)
    r = c.get("/command-center")
    assert r.status_code == 503, "the page from zero"
    assert "We could not load your Command Center" in r.get_data(as_text=True)
    _statement(c._id)
    r = c.get("/command-center")
    assert r.status_code == 503, "the operational page"
    assert "We could not load your Command Center" in r.get_data(as_text=True)


def test_actions_3_a_record_that_could_not_be_read_is_not_called_gone(monkeypatch):
    c = _account()
    camp = mls.create_campaign(c._id, "md-%s" % uuid.uuid4().hex[:6], {"title": "Midnight Drive"})
    aid = _create(c, title="About the release", related="release:%s" % camp)
    monkeypatch.setattr(mls, "list_campaigns", _boom)
    for page in (_page(c, "/actions?status=all"), _page(c, "/actions/%s" % aid)):
        assert "no longer on file" not in page
        assert "This release could not be read right now" in page
    assert 'value="__keep__" selected' in _page(c, "/actions/%s" % aid)
    c.post("/actions/%s" % aid, data={"title": "About the release", "related": "__keep__"})
    assert cc.get_action(aid, c._id)["entity_id"] == camp, "the link survives an edit"
    monkeypatch.undo()
    assert "Midnight Drive · Release" in _page(c, "/actions?status=all")


def test_actions_4_the_command_center_counts_every_open_action():
    c = _account()
    _statement(c._id)
    for i in range(8):
        _create(c, title="Low thing %d" % i, priority="low")
    page = _page(c, "/command-center")
    assert "No alerts right now." in page, "an operational account with no alert"
    assert "8 open actions on your board, the first 5 listed under Open Actions." in page
    assert "5 open actions on your board" not in page


def test_actions_5_22_the_menu_and_the_summary_keep_inside_the_page():
    css = io.open("static/css/actions.css", encoding="utf-8").read()
    assert "right: auto; left: 0" not in css, "the menu no longer grows right from a right-hand button"
    assert "max-width: calc(100vw - 32px)" in css and "min-width: min(250px, calc(100vw - 32px))" in css
    assert ".ac-row .ac-acts .ac-menu { margin-left: auto; }" in css
    assert ".ac-fig + .ac-fig" not in css, "no divider that can start a wrapped line"
    assert ".ac-figs { flex: 1 1 auto; min-width: 0; overflow: hidden; }" in css
    assert "margin-left: -25px" in css
    c = _account()
    _create(c, title="One")
    page = _page(c, "/actions?status=all")
    assert '<div class="ac-figs"><div class="ac-figs-in">' in page and "actions.css?v=3" in page


def test_actions_6_a_long_unbroken_title_wraps():
    zero = io.open("static/css/command-zero.css", encoding="utf-8").read()
    rule = re.search(r"\n\.cz-h \{([^}]*)\}", zero).group(1)
    assert "overflow-wrap: anywhere" in rule
    css = io.open("static/css/actions.css", encoding="utf-8").read()
    assert ".ac .sb-plate-title, .ac .sb-plate-sub { overflow-wrap: anywhere; min-width: 0; }" in css
    assert "command-zero.css?v=5" in _page(_account(), "/command-center")


def test_actions_7_a_rights_conflict_becomes_an_action_about_its_song():
    c = _account()
    t1 = store.add_os_track(c._id, "After Hours")
    store.update_os_track_passport(c._id, t1, {"songwriters": "Ann, Bo"})
    page = _page(c, "/conflicts")
    form = page.split('action="/actions/from-alert"', 1)[1].split("</form>", 1)[0]
    for field in ('name="source" value="rights_conflict"', 'name="room" value="publishing"',
                  'name="entity_type" value="song"', 'name="entity_id" value="%s"' % t1,
                  'value="Review split conflict: After Hours"'):
        assert field in form, field
    c.post("/actions/from-alert", data={"title": "Review split conflict: After Hours",
                                        "category": "rights", "source": "rights_conflict",
                                        "room": "publishing", "entity_type": "song", "entity_id": t1},
           headers={"Referer": "http://localhost/conflicts"})
    a = [x for x in cc.list_actions(c._id) if x["source"] == "rights_conflict"][0]
    assert (a["room"], a["entity_type"], a["entity_id"]) == ("publishing", "song", t1)
    row = _row(_page(c, "/actions?status=all"), "Review split conflict: After Hours")
    assert "After Hours · Song" in row and "From Rights Conflict" in row
    # a song that is not this account's is not kept
    other = _account(name="Other")
    other.post("/actions/from-alert", data={"title": "Sneaky song", "entity_type": "song",
                                            "entity_id": t1},
               headers={"Referer": "http://localhost/conflicts"})
    assert [x for x in cc.list_actions(other._id) if x["title"] == "Sneaky song"][0]["entity_id"] == ""


def test_actions_7_a_seat_that_cannot_file_an_action_is_told_who_can():
    owner, rey = _account(), _account(name="Rey")
    _seat(owner, rey, access="read")
    t1 = store.add_os_track(owner._id, "After Hours")
    store.update_os_track_passport(owner._id, t1, {"songwriters": "Ann, Bo"})
    page = _page(rey, "/conflicts")
    assert 'action="/actions/from-alert"' not in page
    assert "Actions are filed by the account holder or a seat with every room and edit access." in page


def test_actions_8_no_source_is_produced_by_nothing():
    band = io.open("templates/_real_royalty_band.html", encoding="utf-8").read()
    assert "band_mode == 'recovery'" not in band and 'value="royalty_check"' not in band
    assert "royalty_check" not in cc.ACTION_SOURCES
    assert acx.source_for_path("/recovery") == "" and acx.source_for_path("/statements") == ""


def test_actions_9_an_alert_action_keeps_its_campaign_room_and_fix_link():
    c = _account()
    camp = mls.create_campaign(c._id, "hp-%s" % uuid.uuid4().hex[:6], {"title": "Higher Places"})
    c.post("/actions/from-alert", data={
        "title": "“Higher Places” captures emails without consent copy", "category": "rights",
        "source": "alert", "fix": "/links/%s/edit" % camp},
        headers={"Referer": "http://localhost/command-center"})
    a = [x for x in cc.list_actions(c._id) if "consent copy" in x["title"]][0]
    assert a["room"] == team_areas.room_for_path("/links/%s/edit" % camp) == "marketing"
    assert a["entity_id"] == camp and a["entity_type"] in ("campaign", "release")
    assert a["source_href"] == "/links/%s/edit" % camp
    # a fix link that is another site is dropped
    c.post("/actions/from-alert", data={"title": "Hostile fix", "fix": "//evil.example/x"},
           headers={"Referer": "http://localhost/command-center"})
    h = [x for x in cc.list_actions(c._id) if x["title"] == "Hostile fix"][0]
    assert h["source_href"] == "/command-center"
    tpl = io.open("templates/command_center.html", encoding="utf-8").read()
    assert '<input type="hidden" name="fix" value="{{ link }}">' in tpl


def test_actions_10_the_shared_line_is_said_by_the_saved_action_only():
    c = _account()
    page = _page(c, "/qualification?action=Your%20royalties%20were%20claimed&action_id=nope")
    assert "Your royalties were claimed" not in page and "is on your" not in page


def test_actions_11_a_fresh_board_says_it_is_empty_once():
    page = _page(_account())
    assert page.count("No actions yet.") == 1
    assert 'aria-label="Filter actions"' not in page and 'class="ac-views"' not in page
    assert '<span class="ac-count">0</span>' not in page


def test_actions_12_the_demo_account_opens_on_the_showcase():
    import demo_seed
    page = _page(_demo_client(), "/actions?status=all")
    assert "No actions yet" not in page
    for title in ("Fix missing ISRC: Midnight Drive", "Review split conflict: Neon Dreams",
                  "Prepare press announcement"):
        assert title in page, title
    uid = store.get_user_by_email("demo@streetbanker.io")["id"]
    before = len(cc.list_actions(uid))
    assert demo_seed.seed_actions(uid) is False, "keyed: a reboot adds nothing"
    assert len(cc.list_actions(uid)) == before
    s = cc.board_summary([a for a in cc.list_actions(uid) if a["created_by"] == "demo-seed"])
    assert (s["complete"], s["in_progress"], s["not_started"], s["dismissed"]) == (3, 2, 2, 1)


def test_actions_13_18_tour_tasks_use_the_one_set_of_names_and_a_real_assignee():
    import tour_store as ts
    c = _account()
    tid = ts.create_tour(c._id, {"name": "Autumn run"})
    c.post("/tours/%s/tasks/add" % tid, data={"title": "Book the van", "assignee": "Sam"})
    a = [x for x in cc.list_actions(c._id) if x["title"].startswith("Book the van")][0]
    assert a["title"] == "Book the van", "the name is no longer glued onto the title"
    assert (a["assignee_id"], a["assignee_name"]) == ("", "Sam")
    page = _page(c, "/tours/%s/tasks" % tid)
    assert ">Not started</span>" in page and ">new</span>" not in page
    assert ">Complete</button>" in page and ">Done</button>" not in page
    assert 'href="/actions">Actions</a>' in page and "Command Center actions" not in page
    assert "Tour crew: Sam" in page
    assert "Tour crew: Sam" in _row(_page(c, "/actions?status=all"), "Book the van")
    c.post("/actions", data={"action_id": a["id"], "status": "dismissed"})
    assert ">Dismissed</span>" in _page(c, "/tours/%s/tasks" % tid)
    # a name that is a confirmed team member is that person
    mia = _account(name="Mia")
    _seat(c, mia, access="edit")
    c.post("/tours/%s/tasks/add" % tid, data={"title": "Load in", "assignee": "Mia"})
    b = [x for x in cc.list_actions(c._id) if x["title"] == "Load in"][0]
    assert (b["assignee_id"], b["assignee_name"]) == (mia._id, "")


def test_actions_14_a_seat_that_cannot_open_actions_is_told_in_words():
    import tour_store as ts
    owner, rey = _account(), _account(name="Rey")
    r = owner.post("/team/invite", data={"email": rey._email, "role": "manager", "access": "edit",
                                         "areas_sent": "1", "areas": ["stage", "fans"]})
    assert r.get_json().get("ok"), r.get_json()
    row = [m for m in store.list_team(owner._id) if m["email"] == rey._email][0]
    rey.post("/team/join/" + row["invite_token"], data={})
    rey.post("/portal/%s/open" % owner._id)
    assert rey.get("/actions").status_code == 302, "the whole-account page bounces this seat"
    tid = ts.create_tour(owner._id, {"name": "Autumn run"})
    r = rey.get("/tours/%s/tasks" % tid)
    assert r.status_code == 200
    head = r.get_data(as_text=True).split("Tour tasks</h1>", 1)[1][:900]
    assert 'href="/actions"' not in head and "Also on the account's Actions list" in head


def test_actions_15_the_reason_a_raised_action_stays_reads_as_a_sentence():
    c = _account()
    aid = cc.create_action(c._id, "Contract dates", source="document", entity_type="document",
                           entity_id="d1")
    assert "A contract reading raised this action" in _page(c, "/actions/%s" % aid)
    listing = _page(c, "/actions?status=all")
    assert "Raised by a contract reading, so it stays on record." in listing
    assert set(cc.SOURCE_NOUNS) == set(cc.ACTION_SOURCES)


def test_actions_16_action_deleted_is_said_by_a_delete_that_happened():
    c = _account()
    page = _page(c, "/actions?deleted=Your%20royalty%20claim")
    assert "Action deleted" not in page and "Your royalty claim" not in page
    aid = _create(c, title="Oops again")
    r = c.post("/actions/%s/delete" % aid)
    assert r.headers["Location"].endswith("/actions?deleted=1")
    assert "&ldquo;Oops again&rdquo; is gone for good" in _page(c, r.headers["Location"])
    assert "Action deleted" not in _page(c, r.headers["Location"]), "said once"


def test_actions_17_creating_from_the_board_stays_on_the_board():
    c = _account()
    r = c.post("/actions", data={"title": "From the board", "back": "/actions?status=all&view=board"})
    loc = r.headers["Location"]
    assert "view=board" in loc and "status=all" in loc and "created=" in loc
    assert 'class="ac-board"' in _page(c, loc)


def test_actions_21_repeated_controls_name_their_action():
    c = _account()
    _create(c, title="Name me", room="publishing")
    row = _row(_page(c, "/actions?status=all"), "Name me")
    assert 'aria-label="Start: Name me"' in row
    assert 'aria-label="Open Publishing for Name me" href="/room/publishing">Open Publishing' in row


def test_actions_23_titles_and_descriptions_are_escaped():
    c = _account()
    aid = _create(c, title="<script>x()</script>", description="<b>bold</b>")
    for page in (_page(c, "/actions?status=all"), _page(c, "/actions/%s" % aid)):
        assert "<script>x()</script>" not in page and "&lt;script&gt;" in page

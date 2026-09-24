"""The Mock Up Tour after two adversarial reviews of 9d281a45 (2026-09-23).

The sample is labelled and kept off public pages
(tests/test_mock_tour_off_public_pages.py). The reviews found the ways
round it, and the things the fix broke:

- the Stage blueprint's own door (/stage/guest/<token>) still opened a
  stage link minted on the sample;
- the old Tour Hub routes still mailed an advance, and minted a /showday
  token, for a sample date;
- the note said the sample "cannot be shared", but a team invitation
  shared it, and the invitee's Tour home had no Sample chip on it;
- the Light Studio's tour-date picker and the /tours calendar listed
  sample dates unlabelled beside real ones;
- a real tour became "the sample" if anyone uploaded a file named
  mock-up-tour.tsv to it, and a Mock Up Tour cut off half-built was
  never recognised;
- the sample's Share page still called its old links "live", and the
  Send tab still composed a rider link minted before the rule;
- a real date the member added to the sample was hidden with no way to
  move it to a tour of their own.
"""
import io
import uuid

import pytest

import db as store
import email_provider
import tour_dates
import tour_mockup
import tour_store as ts
from tests.test_mock_tour_off_public_pages import (  # noqa: F401  (fixtures)
    PW, _pro, _real_confirmed_show, _with_mock, flask_app, mock_on)


@pytest.fixture
def mock_off(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("MOCK_UP_TOUR", "off")
    monkeypatch.delenv("SUITE_GATES", raising=False)
    monkeypatch.delenv("RENDER", raising=False)


def _confirmed_sample_show(mock_id):
    return [s for s in ts.list_shows(mock_id) if s["status"] == "confirmed"][0]


def _member_added_show(c, mock_id, venue="Member Added Real Room", date_="2027-06-02"):
    """A real date the member put on the sample themselves (not one of the
    sheet's invented (date, venue) pairs), confirmed."""
    r = c.post("/tours/%s/days/add" % mock_id, data={"date": date_, "kind": "show", "venue": venue,
                                                     "city": "Knoxville, TN", "tz": "America/New_York"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    assert c.post("/tours/%s/shows/%s/ext" % (mock_id, sid), data={"status": "confirmed"}).status_code == 302
    assert (date_, venue) not in tour_mockup.sheet_show_keys()
    return sid


# --- the Stage door (stage-guest-alias-not-404) -----------------------------

def test_a_stage_link_on_the_sample_opens_nothing_through_the_stage_door(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    sid = _confirmed_sample_show(mock_id)["id"]
    tok = ts.create_share_link(mock_id, user["id"], "stage", sid)
    anon = flask_app.test_client()
    assert anon.get("/tour-share/%s" % tok).status_code == 404
    assert anon.get("/stage/guest/%s" % tok).status_code == 404
    assert anon.get("/stage/guest/%s/events" % tok).status_code == 404
    assert anon.post("/stage/guest/%s/ask" % tok, data={"kind": "more", "source": "vox"}).status_code == 404
    # The same kind of link on a real date still opens.
    tid, real_sid = _real_confirmed_show(c, "Real Stage Room")
    real_tok = ts.create_share_link(tid, user["id"], "stage", real_sid)
    assert anon.get("/stage/guest/%s" % real_tok).status_code == 200


# --- the old Tour Hub routes (legacy-send-advance-unguarded) ----------------

def test_the_old_hub_routes_neither_mail_nor_mint_a_link_for_a_sample_date(mock_on, flask_app, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    outbox = []
    monkeypatch.setattr(email_provider, "send",
                        lambda to, subject, html, *a, **k: outbox.append((to, subject)) or True)
    c, user, mock_id, slug = _with_mock(flask_app)
    sid = _confirmed_sample_show(mock_id)["id"]
    c.post("/tour/%s/advance" % sid, data={"contact_email": "venue@example.com"})
    r = c.post("/tour/%s/send-advance" % sid)
    assert "sent=1" not in r.headers["Location"]
    assert outbox == [], "no advance for an invented show reaches a real inbox"
    c.post("/tour/%s/share" % sid)
    assert not store.get_tour_show(user["id"], sid).get("share_token"), "no public token is minted"
    # A real date through the same old routes still mails and still mints.
    tid, real_sid = _real_confirmed_show(c, "Real Hub Room")
    c.post("/tour/%s/advance" % real_sid, data={"contact_email": "venue@example.com"})
    c.post("/tour/%s/share" % real_sid)
    assert store.get_tour_show(user["id"], real_sid).get("share_token")
    r = c.post("/tour/%s/send-advance" % real_sid)
    assert "sent=1" in r.headers["Location"] and len(outbox) == 1


# --- invitations (sample-note-cannot-be-shared-overclaim) -------------------

def test_the_sample_cannot_be_shared_by_invitation(mock_on, flask_app, monkeypatch):
    sent = []
    monkeypatch.setattr(email_provider, "send", lambda *a, **k: sent.append(a) or True)
    c, user, mock_id, slug = _with_mock(flask_app)
    r = c.post("/tours/%s/team/invite" % mock_id,
               data={"email": "crew-%s@example.net" % uuid.uuid4().hex[:6], "name": "Crew", "role": "crew"})
    assert r.status_code == 302 and "invite=sample" in r.headers["Location"]
    assert ts.list_members(mock_id) == [] and sent == []
    team = c.get("/tours/%s/team" % mock_id).get_data(as_text=True)
    assert 'id="sample-no-invite"' in team
    assert 'action="/tours/%s/team/invite"' % mock_id not in team


def test_someone_invited_before_the_rule_sees_the_sample_marked_on_their_tour_home(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    email = "crew-%s@example.net" % uuid.uuid4().hex[:8]
    m = ts.add_member(mock_id, user["id"], email, "Crew", "crew")
    crew = flask_app.test_client()
    crew.post("/signup", data={"name": "Crew", "email": email, "password": PW})
    crew.post("/login", data={"email": email, "password": PW})
    crew.get("/tours/join/%s" % m["invite_token"])
    home = crew.get("/tours").get_data(as_text=True)
    shared = home.split('id="shared"')[1].split("</div>\n  </div>")[0]
    assert "Mock Up Tour" in shared and "Sample</span>" in shared


# --- internal pickers (sample-unlabelled-internal-pickers) ------------------

def test_sample_dates_are_labelled_in_the_light_studio_picker(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    _real_confirmed_show(c, "Real Picker Room")
    page = c.get("/lights").get_data(as_text=True)
    picker = page.split('id="lx-tourshow"')[1].split("</select>")[0]
    assert "2027-04-08 · Milwaukee, WI (sample)</option>" in picker
    assert "2030-06-12 · Knoxville, TN</option>" in picker, "a real date carries no label"


def test_sample_dates_are_marked_on_the_tours_calendar(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    tid, _sid = _real_confirmed_show(c, "Real Calendar Room", date_="2027-04-09")
    cal = c.get("/tours?month=2027-04").get_data(as_text=True)
    grid = cal.split('id="all-cal"')[1]
    sample_cell = grid.split('aria-label="2027-04-08')[1].split("</a>")[0]
    assert 'class="pct is-sample">Sample' in sample_cell
    real_cell = grid.split('aria-label="2027-04-09')[1].split("</a>")[0]
    assert "Knoxville, TN" in real_cell


# --- recognising the sample (tour-safe-1, tour-safe-4) ----------------------

def test_an_upload_named_like_the_sample_sheet_leaves_a_real_tour_real(mock_off, flask_app):
    c, user = _pro(flask_app)
    tid, sid = _real_confirmed_show(c, "Real Room Knoxville")
    assert [r["venue"] for r in tour_dates.upcoming(user["id"])] == ["Real Room Knoxville"]
    r = c.post("/tours/%s/import" % tid, content_type="multipart/form-data",
               data={"action": "confirm", "source": "mockup",
                     "file": (io.BytesIO(b"DATE\tCITY\tVENUE\n"), tour_mockup.IMPORT_FILENAME)})
    assert r.status_code == 302
    assert not tour_mockup.is_mock(tid) and tour_mockup.mock_tour_ids(user["id"]) == set()
    assert [r["venue"] for r in tour_dates.upcoming(user["id"])] == ["Real Room Knoxville"]
    assert {i["source"] for i in ts.list_imports(tid)} <= {"paste", "csv", "ics"}
    assert "sample-tour-note" not in c.get("/tours/%s" % tid).get_data(as_text=True)
    # Nor can a pasted form claim to be the sample's own record.
    c.post("/tours/%s/import" % tid, data={"action": "confirm", "source": "mockup", "text": ""})
    assert not tour_mockup.is_mock(tid)


def test_the_sample_is_marked_by_what_only_ensure_for_writes(mock_on, flask_app):
    c, user, mock_id, slug = _with_mock(flask_app)
    assert [i["source"] for i in ts.list_imports(mock_id)] == [tour_mockup.IMPORT_SOURCE]


def test_a_sample_recorded_the_old_way_is_still_the_sample(mock_off, flask_app):
    """Mock Up Tours built before today carry ensure_for's old record:
    source csv, the sheet's filename, and a summary no import route
    writes ({"created": {"rows": N}})."""
    c, user = _pro(flask_app)
    tid = ts.create_tour(user["id"], {"name": tour_mockup.NAME, "status": "planning",
                                      "start_date": "2027-04-05", "end_date": "2027-05-19",
                                      "home_tz": "America/Chicago", "currency": "USD"})
    ts.record_import(tid, user["id"], "csv", tour_mockup.IMPORT_FILENAME, tour_mockup.SHEET,
                     {"created": {"rows": 44}, "problems": [], "rows": 44})
    assert tour_mockup.is_mock(tid) and tour_mockup.mock_tour_ids(user["id"]) == {tid}


def test_a_mock_up_tour_cut_off_half_built_is_still_the_sample(mock_on, flask_app, monkeypatch):
    c, user = _pro(flask_app)
    real_status = tour_mockup.store.update_tour_show_status
    calls = {"n": 0}

    def cut_off(*a, **k):
        calls["n"] += 1
        if calls["n"] > 3:
            raise RuntimeError("worker killed mid-build")
        return real_status(*a, **k)

    monkeypatch.setattr(tour_mockup.store, "update_tour_show_status", cut_off)
    with pytest.raises(RuntimeError):
        tour_mockup.ensure_for(user)
    monkeypatch.setattr(tour_mockup.store, "update_tour_show_status", real_status)
    tours = ts.list_tours(user["id"])
    assert len(tours) == 1
    tid = tours[0]["id"]
    assert [s for s in ts.list_shows(tid) if s["status"] == "confirmed"], "it did get invented confirmed dates"
    assert tour_mockup.is_mock(tid)
    assert tour_dates.upcoming(user["id"]) == []

"""Contract renewal reminders that run on their own, and words that wait.

Found by the make-it-real pass of 2026-09-23: the Contracts card promised
"renewal reminders", and reminders only go out when something POSTs to
/reminders/run. Nothing did: there is no scheduler in the repo. Worse, an
unsigned POST was redirected to /login, and a cron log reads a 302 as a
success - the exact false green the nightly backup hit on its first run.

Held here:

  * a scheduler reaches the run with REMINDERS_CRON_TOKEN in the
    X-Reminders-Token header (its own secret, not BACKUP_TOKEN) and gets
    200 JSON; anything else gets 401 JSON with the reason, never a
    redirect; a signed-in owner can still run it by hand
  * "are reminders going out?" is measured from the scheduler's own last
    run, not from the token being set
  * the Contracts card, the contract rows and the upload action promise
    reminders only while that is true, and say "dates on file" otherwise
"""
import io
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app as appmod
import contract_reminders as cr
import db as store
import rooms

PW = "reminders-cron-123"
TOKEN = "cron-" + uuid.uuid4().hex


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv(cr.TOKEN_ENV, raising=False)
    monkeypatch.delenv("BACKUP_TOKEN", raising=False)
    monkeypatch.delenv("OWNER_EMAILS", raising=False)


@pytest.fixture
def anon():
    return appmod.app.test_client()


def _member(plan="pro"):
    email = "cron-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Contracted", "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid, email


def _scheduled_run(monkeypatch, at=None, ok=True):
    """A scheduler run on record, as the route records one."""
    monkeypatch.setenv(cr.TOKEN_ENV, TOKEN)
    rec = {"checked": 0, "sent": 0, "emailed": 0, "ok": ok}
    return cr.record_run(rec, "scheduler", now=at)


# --- the door a scheduler knocks on -------------------------------------------

def test_no_token_configured_is_a_401_with_that_reason_not_a_redirect(anon):
    r = anon.post("/reminders/run")
    assert r.status_code == 401, "a redirect reads as success in a cron log"
    assert "Location" not in r.headers
    body = r.get_json()
    assert body["ok"] is False and "REMINDERS_CRON_TOKEN is not configured" in body["error"]


def test_a_wrong_token_is_a_401_saying_it_did_not_match(anon, monkeypatch):
    monkeypatch.setenv(cr.TOKEN_ENV, TOKEN)
    r = anon.post("/reminders/run", headers={cr.TOKEN_HEADER: "nope"})
    assert r.status_code == 401
    assert "did not match" in r.get_json()["error"]
    assert anon.post("/reminders/run").status_code == 401


def test_the_token_must_come_in_the_header(anon, monkeypatch):
    """A form field ends up in places a header does not."""
    monkeypatch.setenv(cr.TOKEN_ENV, TOKEN)
    assert anon.post("/reminders/run", data={"token": TOKEN}).status_code == 401


def test_the_backup_token_no_longer_runs_the_reminders(anon, monkeypatch):
    """The token that may copy the database is not the one that emails
    every artist. It used to be both."""
    monkeypatch.setenv("BACKUP_TOKEN", "backup-" + TOKEN)
    monkeypatch.setenv(cr.TOKEN_ENV, TOKEN)
    r = anon.post("/reminders/run", headers={"X-Backup-Token": "backup-" + TOKEN})
    assert r.status_code == 401


def test_a_get_is_refused_not_redirected(anon, monkeypatch):
    monkeypatch.setenv(cr.TOKEN_ENV, TOKEN)
    r = anon.get("/reminders/run", headers={cr.TOKEN_HEADER: TOKEN})
    assert r.status_code == 405


def test_the_right_token_runs_it_and_answers_200_json(anon, monkeypatch):
    monkeypatch.setenv(cr.TOKEN_ENV, TOKEN)
    r = anon.post("/reminders/run", headers={cr.TOKEN_HEADER: TOKEN})
    assert r.status_code == 200 and r.is_json
    body = r.get_json()
    assert body["ok"] is True and "checked" in body["run"]
    assert body["run"]["by"] == "scheduler"
    rec = cr.last_scheduled_run()
    assert rec and rec["by"] == "scheduler" and rec["ok"] is True
    assert cr.scheduled() is True


def test_a_run_that_fails_says_so_and_stops_the_promise(anon, monkeypatch):
    monkeypatch.setenv(cr.TOKEN_ENV, TOKEN)

    def boom(**_k):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(cr, "run", boom)
    r = anon.post("/reminders/run", headers={cr.TOKEN_HEADER: TOKEN})
    assert r.status_code == 500 and r.get_json()["ok"] is False
    assert cr.scheduled() is False, "a failed run is not reminders going out"


def test_a_plain_account_gets_404_and_an_owner_can_run_it_by_hand(monkeypatch):
    member, _uid, email = _member()
    assert member.post("/reminders/run").status_code == 404
    monkeypatch.setenv("OWNER_EMAILS", email)
    r = member.post("/reminders/run")
    assert r.status_code == 200 and r.get_json()["run"]["by"] == "owner"


# --- what "reminders are going out" means -------------------------------------

def test_the_token_alone_is_not_a_schedule(monkeypatch):
    monkeypatch.setenv(cr.TOKEN_ENV, "never-presented-" + uuid.uuid4().hex)
    before = cr.last_scheduled_run()
    if before:
        # This worker's database may hold a run from an earlier test; age
        # it past the window so only a fresh run could say yes.
        cr.record_run(before, "scheduler",
                      now=datetime.now(timezone.utc) - timedelta(days=5))
    assert cr.scheduled() is False


def test_a_scheduler_run_within_two_days_counts_and_an_older_one_does_not(monkeypatch):
    now = datetime.now(timezone.utc)
    _scheduled_run(monkeypatch, at=now - timedelta(hours=30))
    assert cr.scheduled(now) is True
    _scheduled_run(monkeypatch, at=now - timedelta(hours=49))
    assert cr.scheduled(now) is False


def test_an_owner_run_by_hand_does_not_stand_in_for_the_schedule(monkeypatch):
    now = datetime.now(timezone.utc)
    _scheduled_run(monkeypatch, at=now - timedelta(days=4))
    cr.record_run({"ok": True}, "owner", now=now)
    assert cr.scheduled(now) is False


def test_without_the_token_nothing_is_scheduled_whatever_is_on_record(monkeypatch):
    _scheduled_run(monkeypatch)
    monkeypatch.delenv(cr.TOKEN_ENV)
    assert cr.scheduled() is False


# --- the words ------------------------------------------------------------------

def test_the_contracts_card_says_dates_on_file_until_reminders_run(monkeypatch):
    line = rooms.catalogue()["contracts"][3]
    assert line == "The paperwork that proves who gets paid, with renewal dates on file."
    assert "reminder" not in line
    _scheduled_run(monkeypatch)
    assert rooms.catalogue()["contracts"][3] == (
        "The paperwork that proves who gets paid, with renewal reminders.")


def test_the_business_room_tile_carries_the_true_line(monkeypatch):
    monkeypatch.setenv("NAV_ROOMS", "1")
    member, _uid, _email = _member("label")
    body = member.get("/room/business").get_data(as_text=True)
    assert "with renewal dates on file" in body
    assert "with renewal reminders" not in body


def _contract(member, uid):
    member.post("/vault/documents",
                data={"document": (io.BytesIO(b"%PDF-1.4 fake"), "distribution.pdf"),
                      "doc_type": "Distribution"},
                content_type="multipart/form-data")
    return store.list_documents(uid)[0]


def test_the_contract_rows_promise_nothing_while_nothing_sends(monkeypatch):
    member, uid, _email = _member()
    doc = _contract(member, uid)
    body = member.get("/vault?view=contracts").get_data(as_text=True)
    assert "the app reminds you" not in body
    assert ("to keep the notice deadline on this row. Reminders at 60, 30, 7 and 1 "
            "days before it are not switched on yet.") in body
    member.post("/vault/documents/%s/terms" % doc["id"],
                data={"renews_on": "2031-03-01", "notice_days": "60"})
    body = member.get("/vault?view=contracts&terms=saved").get_data(as_text=True)
    assert "Renewal dates saved." in body and "Reminders follow them" not in body
    # The owner's milestones stay on the page, said as not yet running.
    assert "Reminders at 60, 30, 7 and 1 days before the notice date." not in body
    assert ("Reminders at 60, 30, 7 and 1 days before the notice date are not "
            "switched on yet, so keep an eye on this date.") in body


def test_the_contract_rows_promise_reminders_once_a_scheduler_runs(monkeypatch):
    member, uid, _email = _member()
    doc = _contract(member, uid)
    _scheduled_run(monkeypatch)
    member.post("/vault/documents/%s/terms" % doc["id"],
                data={"renews_on": "2031-03-01", "notice_days": "60"})
    body = member.get("/vault?view=contracts&terms=saved").get_data(as_text=True)
    assert "Renewal dates saved. Reminders follow them." in body
    assert "Reminders at 60, 30, 7 and 1 days before the notice date." in body
    assert "not switched on yet" not in body


def test_the_upload_action_asks_for_dates_not_reminders_while_nothing_sends(monkeypatch):
    """Reading a contract on upload raises one action. Its title named
    reminders that nothing would send."""
    import command_center as cc
    member, uid, _email = _member()
    text = (b"DISTRIBUTION AGREEMENT\n"
            b"2. Term. The initial term of this Agreement shall be two (2) years.\n"
            b"3. Renewal. This Agreement shall automatically renew for successive one (1) "
            b"year periods unless either party gives written notice of non-renewal at "
            b"least sixty (60) days prior to the end of the then-current term.\n")
    member.post("/vault/documents",
                data={"document": (io.BytesIO(text), "renewing.txt"),
                      "doc_type": "Distribution"},
                content_type="multipart/form-data")
    mine = [a["title"] for a in cc.list_actions(uid) if "renewing.txt" in a["title"]]
    assert mine, "the reader raised no action; the test's contract text needs a look"
    assert mine[0] == "Set the renewal dates for renewing.txt"

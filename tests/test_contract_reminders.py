"""Contract renewal reminders.

Owner, 2026-09-14: "is there a reminder alarm built to notify you when
your auto renewals are coming up?" There was not. This is the half that
needs no document reader: dates typed on the contract's row, reminders
at 90, 30 and 7 days before the notice deadline and on the day, in the
app and by email where one can be sent, each once, from a daily run the
nightly job triggers with the backup token.
"""
import io
import json
import uuid
from datetime import date, timedelta

import pytest

import contract_reminders as cr
import db as store
from app import create_app

PW = "renew-12345"


@pytest.fixture
def world():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "renew-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Renewing", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    client.post("/vault/documents",
                data={"document": (io.BytesIO(b"%PDF-1.4 fake"), "distribution.pdf"),
                      "doc_type": "Distribution", "note": "two year term"},
                content_type="multipart/form-data")
    with app_obj.app_context():
        uid = store.get_user_by_email(email)["id"]
        doc = store.list_documents(uid)[0]
    return app_obj, client, email, uid, doc


def test_status_speaks_plainly_about_the_notice_deadline():
    today = date(2026, 9, 14)
    terms = {"renews_on": "2027-03-01", "notice_days": 60, "auto_renews": 1}
    st = cr.status(terms, today)
    assert st["notice_by"] == "2026-12-31" and st["phase"] == "open" and st["days_left"] == 108
    assert st["sentence"] == "Renews 1 Mar 2027 automatically. Give notice by 31 Dec 2026, in 108 days."
    assert cr.status({"renews_on": "2026-09-20", "notice_days": 30}, today)["phase"] == "notice_closed"
    assert cr.status({"renews_on": "2026-01-01", "notice_days": 0}, today)["phase"] == "passed"
    assert cr.status({"renews_on": ""}, today) is None
    assert cr.status({"renews_on": "not a date"}, today) is None


def test_the_nearest_milestone_fires_and_the_passed_ones_are_superseded():
    terms = {"renews_on": "2026-12-31", "notice_days": 0}
    # 100 days out: nothing yet
    assert cr.due_milestone(terms, date(2026, 9, 22), set()) == (None, [])
    # 90 days out: the 90
    assert cr.due_milestone(terms, date(2026, 10, 2), set()) == (90, [])
    # terms typed 20 days out: only the 30 fires, the 90 is superseded
    assert cr.due_milestone(terms, date(2026, 12, 11), set()) == (30, [90])
    # once 30 and 90 are on record, the 7 waits its turn
    assert cr.due_milestone(terms, date(2026, 12, 11), {30, 90}) == (None, [])
    assert cr.due_milestone(terms, date(2026, 12, 24), {30, 90}) == (7, [])
    assert cr.due_milestone(terms, date(2026, 12, 31), {30, 90, 7}) == (0, [])
    # after the renewal date nothing fires: the page says update the date
    assert cr.due_milestone(terms, date(2027, 1, 5), set()) == (None, [])


def test_the_row_takes_the_dates_and_reads_them_back(world):
    app_obj, client, email, uid, doc = world
    body = client.get("/vault?view=contracts").get_data(as_text=True)
    assert "Renewal: not set." in body and 'action="/vault/documents/%s/terms"' % doc["id"] in body
    r = client.post("/vault/documents/%s/terms" % doc["id"],
                    data={"renews_on": "2027-03-01", "notice_days": "60", "auto_renews": "1",
                          "terms_note": "12-month term"})
    assert r.status_code == 302 and r.headers["Location"].endswith("terms=saved#doc-%s" % doc["id"])
    body = client.get("/vault?view=contracts&terms=saved").get_data(as_text=True)
    assert "Renewal dates saved" in body
    assert "Renews 1 Mar 2027 automatically. Give notice by 31 Dec 2026" in body
    assert "nobody has read the document" in body
    r = client.post("/vault/documents/%s/terms" % doc["id"], data={"renews_on": "31/12/2026"})
    assert "terms=baddate" in r.headers["Location"]
    assert client.post("/vault/documents/nope/terms", data={"renews_on": "2027-01-01"}).status_code == 404
    other = app_obj.test_client()
    other.post("/signup", data={"name": "Other", "email": "o-%s@example.net" % uuid.uuid4().hex[:6], "password": PW})
    assert other.post("/vault/documents/%s/terms" % doc["id"], data={"renews_on": "2027-01-01"}).status_code == 404


def test_the_run_reminds_once_per_milestone_in_the_app_and_by_email(world, monkeypatch):
    app_obj, client, email, uid, doc = world
    import email_provider as emailer
    with app_obj.app_context():
        store.set_document_terms(uid, doc["id"], "2026-12-31", 0, False, "")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("EMAIL_FROM", "Street Banker <hello@mail.example.net>")
    sent = []
    monkeypatch.setattr(emailer, "_http", lambda url, payload, headers: sent.append(payload) or {"id": "em1"})
    with app_obj.app_context():
        first = cr.run(date(2026, 10, 2), emailer=emailer, public_url=lambda p: "https://x.test" + p)
        again = cr.run(date(2026, 10, 3), emailer=emailer, public_url=lambda p: "https://x.test" + p)
        notes = [n for n in store.list_notifications(uid) if n["kind"] == "contract"]
        recorded = store.reminders_sent(doc["id"])
    # the tests share one database, so other accounts' contracts ride along: read only this one's
    mine = [p for p in sent if p["to"] == [email]]
    assert first["checked"] >= 1 and first["sent"] >= 1 and first["date"] == "2026-10-02"
    assert len(notes) == 1 and "Notice deadline for distribution.pdf is in 90 days" in notes[0]["title"]
    assert notes[0]["link"] == "/vault?view=contracts"
    assert len(mine) == 1 and "distribution.pdf" in mine[0]["subject"]
    assert "https://x.test/vault?view=contracts" in mine[0]["html"]
    assert recorded == {90}
    assert len([p for p in sent if p["to"] == [email]]) == 1, "the second run sent this account nothing"

    # a changed renewal date starts the reminders over
    with app_obj.app_context():
        store.set_document_terms(uid, doc["id"], "2027-06-30", 0, False, "")
        assert store.reminders_sent(doc["id"]) == set()

    # unconfigured (staging): the in-app reminder still lands, no mail is attempted
    monkeypatch.delenv("RESEND_API_KEY")
    monkeypatch.setattr(emailer, "_http", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not send")))
    with app_obj.app_context():
        out = cr.run(date(2027, 4, 1), emailer=emailer)
        notes = [n for n in store.list_notifications(uid) if n["kind"] == "contract"]
    assert out["emailed"] == 0 and len(notes) == 2


def test_the_daily_run_is_reachable_by_the_backup_token_or_an_owner(world, monkeypatch):
    app_obj, client, email, uid, doc = world
    anon = app_obj.test_client()
    assert anon.post("/reminders/run").status_code in (302, 404)
    monkeypatch.setenv("BACKUP_TOKEN", "tok-123")
    r = anon.post("/reminders/run", headers={"X-Backup-Token": "tok-123"})
    assert r.status_code == 200 and r.get_json()["ok"] is True and "checked" in r.get_json()["run"]
    assert anon.post("/reminders/run", headers={"X-Backup-Token": "wrong"}).status_code in (302, 404)
    assert client.post("/reminders/run").status_code == 404, "a plain account may not trigger it"
    monkeypatch.setenv("OWNER_EMAILS", email)
    assert client.post("/reminders/run").status_code == 200


def test_deleting_the_document_takes_its_terms_and_reminders(world):
    app_obj, client, email, uid, doc = world
    with app_obj.app_context():
        store.set_document_terms(uid, doc["id"], "2026-12-31", 0, False, "")
        store.mark_reminder_sent(uid, doc["id"], 90)
    client.post("/vault/documents/%s/delete" % doc["id"])
    with app_obj.app_context():
        assert store.get_document_terms(uid) == {} and store.reminders_sent(doc["id"]) == set()


def test_contract_is_a_notification_kind_people_can_mute():
    assert any(k == "contract" for k, _l, _d in store.NOTIFICATION_KINDS)

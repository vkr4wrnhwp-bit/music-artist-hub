"""The TOUR date page's Stage Control fold: attach a published passport
version to a date, keep it when the passport moves on, and reach the desk
from the date. Phase 3's missing UI, on the page the crew already uses.
"""
import uuid

import pytest

import advance_store as adv
import app as appmod
import db as store
import passport_store as ps

PASSWORD = "date-stage-123"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _owner(flask_app):
    email = "ds-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Date Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    r = client.post("/tours/new", data={
        "name": "Date Run", "artist_name": "Prayers", "start_date": "2030-05-01",
        "end_date": "2030-05-10", "home_tz": "America/New_York", "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = client.post("/tours/%s/days/add" % tid, data={
        "date": "2030-05-02", "kind": "show", "venue": "The Basement East",
        "city": "Nashville, TN", "tz": "America/Chicago"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    return client, store.get_user_by_email(email), tid, sid


def _passport(user, publish=True):
    pid = ps.create_passport(user["id"], artist_name="Prayers", production_name="No Tengo Calma")
    ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", safe_start="-20 dB", sort=1)
    if publish:
        ps.publish(pid, user["id"])
    return pid


def _fold(page):
    return page.split('id="stage"')[1].split("</details>")[0]


def test_an_unadvanced_date_offers_only_published_passports(flask_app):
    client, user, tid, sid = _owner(flask_app)
    draft = _passport(user, publish=False)
    live = _passport(user)
    page = client.get("/tours/%s/shows/%s?tab=advance" % (tid, sid)).get_data(as_text=True)
    fold = _fold(page)
    assert "no passport attached" in fold
    assert 'value="%s"' % live in fold and 'value="%s"' % draft not in fold
    assert "/stage/%s" % sid not in fold, "no desk link until there is something to read"


def test_attaching_stores_the_version_and_opens_the_desk(flask_app):
    client, user, tid, sid = _owner(flask_app)
    pid = _passport(user)
    r = client.post("/tours/%s/shows/%s/stage" % (tid, sid), data={"action": "attach", "passport_id": pid})
    assert r.status_code == 302 and "refused" not in r.headers["Location"]
    link = adv.get_attachment(sid, user["id"])
    assert link and link["version_id"] == ps.get_passport(pid, user["id"])["current_version_id"]
    fold = _fold(client.get("/tours/%s/shows/%s?tab=advance" % (tid, sid)).get_data(as_text=True))
    assert "v1" in fold and "/stage/%s" % sid in fold and "Request Mode" in fold
    desk = client.get("/stage/%s" % sid).get_data(as_text=True)
    assert "Mix 1" in desk or "The queue" in desk
    assert "This date in TOUR" in desk and "/tours/%s/shows/%s" % (tid, sid) in desk


def test_a_newer_version_is_a_notice_never_a_swap(flask_app):
    client, user, tid, sid = _owner(flask_app)
    pid = _passport(user)
    client.post("/tours/%s/shows/%s/stage" % (tid, sid), data={"action": "attach", "passport_id": pid})
    first = adv.get_attachment(sid, user["id"])["version_id"]
    ps.add_row("inputs", pid, channel="2", source="Kick", sort=2)
    ps.publish(pid, user["id"])
    assert adv.get_attachment(sid, user["id"])["version_id"] == first, "the date kept what the crew was handed"
    fold = _fold(client.get("/tours/%s/shows/%s?tab=advance" % (tid, sid)).get_data(as_text=True))
    assert "v2 published since" in fold and "Attach v2" in fold
    client.post("/tours/%s/shows/%s/stage" % (tid, sid), data={"action": "attach", "passport_id": pid})
    assert adv.get_attachment(sid, user["id"])["version_id"] != first


def test_a_draft_passport_is_refused_in_words(flask_app):
    client, user, tid, sid = _owner(flask_app)
    draft = _passport(user, publish=False)
    r = client.post("/tours/%s/shows/%s/stage" % (tid, sid), data={"action": "attach", "passport_id": draft})
    assert "stage=refused" in r.headers["Location"]
    page = client.get(r.headers["Location"].replace("#stage", "")).get_data(as_text=True)
    assert "nothing published yet" in page
    assert adv.get_attachment(sid, user["id"]) is None


def test_detaching_while_open_and_the_summary_counts(flask_app):
    import stage_store as st
    client, user, tid, sid = _owner(flask_app)
    pid = _passport(user)
    client.post("/tours/%s/shows/%s/stage" % (tid, sid), data={"action": "attach", "passport_id": pid})
    st.submit(sid, user["id"], "Leafar", "Mix 1", "more", source="Lead Vox", step_db=2,
              allowed_mixes=["Mix 1"], allowed_sources=["Lead Vox"])
    page = client.get("/tours/%s/shows/%s?tab=advance" % (tid, sid)).get_data(as_text=True)
    assert "1 open request" in page
    client.post("/tours/%s/shows/%s/stage" % (tid, sid), data={"action": "detach"})
    assert adv.get_attachment(sid, user["id"]) is None
    fold = _fold(client.get("/tours/%s/shows/%s?tab=advance" % (tid, sid)).get_data(as_text=True))
    assert "no passport attached" in fold


def test_a_stranger_cannot_attach(flask_app):
    client, user, tid, sid = _owner(flask_app)
    pid = _passport(user)
    other = flask_app.test_client()
    email = "ds-x-%s@example.net" % uuid.uuid4().hex[:8]
    other.post("/signup", data={"name": "X", "email": email, "password": PASSWORD})
    other.post("/login", data={"email": email, "password": PASSWORD})
    r = other.post("/tours/%s/shows/%s/stage" % (tid, sid), data={"action": "attach", "passport_id": pid})
    assert r.status_code in (302, 403, 404)
    assert adv.get_attachment(sid, user["id"]) is None

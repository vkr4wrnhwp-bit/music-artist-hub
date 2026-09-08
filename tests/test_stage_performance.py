"""Stage Control phase 7: the performance check.

Not a rewrite - a bound. The desk and the phone poll /events every few
seconds for the life of a show, and a show with thousands of events must
answer each poll from the index, not from a scan. Held here: the query is
`seq > ?` with a LIMIT, the index that serves it exists, and a show with
5,000 events answers the poll in under 200 ms through the test client.
"""
import inspect
import os
import time
import uuid

import pytest

import advance_store as adv
import app as appmod
import db as store
import passport_store as ps
import stage_bridge as sb
import stage_store as st

PASSWORD = "perf-rooms-123"
EVENTS = 5000
BUDGET_S = 0.2


def test_the_poll_query_is_bounded_by_cursor_and_limit():
    src = inspect.getsource(st.events_since)
    assert "seq > ?" in src and "LIMIT ?" in src and "ORDER BY seq" in src
    src = inspect.getsource(st.events_recent)
    assert "ORDER BY seq DESC LIMIT ?" in src


def test_the_indexes_the_poll_needs_exist():
    st.init_stage()
    sb.init_bridge()
    with store.get_db() as db:
        ev = {r["name"]: r["sql"] for r in db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='stage_events'")}
        cmd = {r["name"]: r["sql"] for r in db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='stage_commands'")}
        plan = [r["detail"] for r in db.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM stage_events WHERE show_id = ? AND seq > ? "
            "ORDER BY seq LIMIT ?", ("s", 0, 200))]
    assert "idx_sevents_show" in ev and "show_id, seq" in ev["idx_sevents_show"]
    assert "idx_scmd_show_state" in cmd, "expire_stale runs on every poll"
    assert any("idx_sevents_show" in d for d in plan), plan
    assert not any("SCAN" in d and "stage_events" in d for d in plan), plan


@pytest.fixture
def busy():
    application = appmod.app
    email = "perf-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Perf", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        user = store.get_user_by_email(email)
        pid = ps.create_passport(user["id"], artist_name="Prayers")
        ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
        ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", sort=1)
        ps.publish(pid, user["id"])
        sid = "show-" + uuid.uuid4().hex[:10]
        adv.attach(sid, user["id"], pid)
        # Straight into the table: the point is the poll, not emit().
        now = store._now()
        with store.get_db() as db:
            db.executemany(
                "INSERT INTO stage_events (id, show_id, user_id, request_id, kind, actor, detail, "
                "payload, created) VALUES (?,?,?,?,?,?,?,?,?)",
                [(uuid.uuid4().hex, sid, user["id"], "", "request.new", "Leafar", "More Lead Vox",
                  '{"mix": "Mix 1"}', now) for _ in range(EVENTS)])
        top = st.cursor(sid)
    return {"client": client, "user": user, "show": sid, "top": top, "app": application}


def _timed(fn, runs=5):
    best = None
    for _ in range(runs):
        t = time.perf_counter()
        out = fn()
        dt = time.perf_counter() - t
        best = dt if best is None else min(best, dt)
    return best, out


def test_a_show_with_five_thousand_events_answers_the_poll_inside_the_budget(busy):
    c, sid, top = busy["client"], busy["show"], busy["top"]
    with busy["app"].app_context():
        assert len(st.events_since(sid, 0, limit=10000)) >= EVENTS
    # From the end, which is every poll after the first.
    dt, r = _timed(lambda: c.get("/stage/%s/events?since=%d" % (sid, top)))
    assert r.status_code == 200 and r.get_json()["events"] == []
    assert dt < BUDGET_S, "poll from the cursor took %.0f ms" % (dt * 1000)
    # From the start, which is one page of the default limit, never the lot.
    dt, r = _timed(lambda: c.get("/stage/%s/events?since=0" % sid))
    assert len(r.get_json()["events"]) == 200
    assert dt < BUDGET_S, "poll from zero took %.0f ms" % (dt * 1000)
    # The desk page itself renders bounded slices.
    dt, r = _timed(lambda: c.get("/stage/%s" % sid), runs=2)
    assert r.status_code == 200


def test_the_guest_poll_is_bounded_the_same_way(busy):
    """The phone polls through the share link with no session; same query."""
    c, sid, top = busy["client"], busy["show"], busy["top"]
    r = c.post("/tours/new", data={
        "name": "Perf Run", "artist_name": "Prayers", "start_date": "2030-05-01",
        "end_date": "2030-05-10", "home_tz": "America/New_York", "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = c.post("/tours/%s/days/add" % tid, data={
        "date": "2030-05-02", "kind": "show", "venue": "Room", "city": "Nashville, TN",
        "tz": "America/Chicago"})
    date_id = r.headers["Location"].split("/shows/")[1].split("?")[0]
    with busy["app"].app_context():
        import tour_store as ts
        link = adv.get_attachment(sid, busy["user"]["id"])
        adv.attach(date_id, busy["user"]["id"], link["passport_id"])
        with store.get_db() as db:
            db.execute("UPDATE stage_events SET show_id = ? WHERE show_id = ?", (date_id, sid))
        top = st.cursor(date_id)
    c.post("/tours/%s/share/new" % tid, data={"scope": "stage", "show_id": date_id})
    with busy["app"].app_context():
        token = [l for l in ts.list_share_links(tid) if l["scope"] == "stage"][0]["token"]
    phone = busy["app"].test_client()
    dt, r = _timed(lambda: phone.get("/stage/guest/%s/events?since=%d" % (token, top)))
    assert r.status_code == 200 and r.get_json()["events"] == []
    assert dt < BUDGET_S, "guest poll took %.0f ms" % (dt * 1000)
    dt, r = _timed(lambda: phone.get("/stage/guest/%s/events?since=0" % token))
    assert len(r.get_json()["events"]) == 200 and dt < BUDGET_S

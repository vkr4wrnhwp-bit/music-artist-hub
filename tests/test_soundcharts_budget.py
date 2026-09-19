"""The owner's Soundcharts allowance: every call counted, customers capped.

Found by the 2026-09-18 check: nothing counted or limited Soundcharts
calls, and a customer switching Pulse artists could spend the month.
Owner, 2026-09-19: "call cap on free is 1000 on paid lowest is 10000".
Customers stop at 80% so the team keeps the rest; a stopped call serves
the last answer measured, never a blank or a zero.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app as appmod
import db
import pulse_everything
import signal_providers as providers
import soundcharts_budget as budget


@pytest.fixture
def kv(monkeypatch):
    """A private key/value store, so counts and cached answers never leak
    between tests that share the SQLite file."""
    store = {}
    monkeypatch.setattr(db, "get_kv", lambda key, default=None: store.get(key, default))
    monkeypatch.setattr(db, "set_kv", lambda key, value: store.__setitem__(key, value))

    def incr(key, by=1):
        store[key] = str(int(store.get(key) or 0) + by)
        return int(store[key])
    monkeypatch.setattr(db, "kv_incr", incr)
    return store


@pytest.fixture
def sc(monkeypatch, kv):
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "id")
    monkeypatch.setenv("SOUNDCHARTS_API_KEY", "key")
    calls = []

    def fetch(url):
        calls.append(url)
        return {"object": {"n": len(calls)}}
    return providers.SoundchartsAdapter(fetch=fetch), calls


def _as(path):
    return appmod.app.test_request_context(path)


def test_every_call_is_counted_by_who_made_it(sc, monkeypatch):
    monkeypatch.setenv("SOUNDCHARTS_CACHE_S", "0")
    adapter, calls = sc
    with _as("/pulse"):
        adapter._get("/api/v2/artist/a")
    with _as("/signal/artist/1"):
        adapter._get("/api/v2/artist/b")
    with _as("/operator-desk/leads"):
        adapter._get("/api/v2/artist/c")
    adapter._get("/api/v2/artist/d")                 # outside any page: a job
    assert len(calls) == 4
    assert budget.counts() == {"customers": 1, "team": 3, "total": 4}


def test_a_cached_answer_costs_nothing(sc):
    adapter, calls = sc
    with _as("/pulse"):
        adapter._get("/api/v2/artist/same")
        adapter._get("/api/v2/artist/same")
    assert len(calls) == 1 and budget.counts()["customers"] == 1


def test_customers_stop_at_80_percent_and_the_team_keeps_the_rest(sc, monkeypatch):
    monkeypatch.setenv("SOUNDCHARTS_CACHE_S", "0")
    adapter, calls = sc
    budget.set_budget(10)
    with _as("/pulse"):
        for i in range(8):
            adapter._get("/api/v2/artist/c%d" % i)
        with pytest.raises(providers.SoundchartsPaused):
            adapter._get("/api/v2/artist/c8")
    assert len(calls) == 8, "the ninth customer call never left"
    assert budget.customers_paused()
    with _as("/signal"):
        adapter._get("/api/v2/artist/t1")
        adapter._get("/api/v2/artist/t2")
        with pytest.raises(providers.SoundchartsPaused):
            adapter._get("/api/v2/artist/t3")
    assert len(calls) == 10 and budget.counts()["total"] == 10


def test_a_paused_page_is_served_the_last_answer_measured_never_a_blank(sc, kv):
    adapter, calls = sc
    with _as("/pulse"):
        first = adapter._get("/api/v2/artist/old")
    # Age that answer well past the six-hour cache.
    key = adapter.cache_key("/api/v2/artist/old", {})
    entry = json.loads(kv[key])
    entry["at"] = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(timespec="seconds")
    kv[key] = json.dumps(entry)
    budget.set_budget(1)                             # already spent
    with _as("/pulse"):
        again = adapter._get("/api/v2/artist/old")
    assert again == first and len(calls) == 1


def test_pulse_names_a_pause_as_a_pause_not_a_refusal():
    class Paused:
        label = "Soundcharts"

        def __getattr__(self, name):
            def call(*a, **k):
                raise providers.SoundchartsPaused("Soundcharts paused: this month's allowance")
            return call
    view = pulse_everything.build(Paused(), "artist-1")
    assert view["paused"] and not view["refused"] and not view["failed"]


def test_only_the_owner_sets_the_budget(kv, monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    email = "scowner-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Someone", "email": email, "password": "sc-pass-1"})
    c.post("/login", data={"email": email, "password": "sc-pass-1"})
    assert c.post("/admin/soundcharts-budget", data={"budget": "1000"}).status_code == 404
    assert budget.budget() == budget.DEFAULT_BUDGET
    monkeypatch.setenv("OWNER_EMAILS", email)
    assert "Soundcharts allowance" in c.get("/settings").get_data(as_text=True)
    c.post("/admin/soundcharts-budget", data={"budget": "1,000"})
    assert budget.budget() == 1000


def test_the_default_is_the_lowest_paid_plan(kv):
    assert budget.budget() == 10000 and budget.customer_ceiling() == 8000


def test_the_counter_adds_in_one_statement():
    key = "test-counter-%s" % uuid.uuid4().hex[:8]
    assert db.kv_incr(key) == 1 and db.kv_incr(key, 4) == 5
    assert db.get_kv(key) == "5"

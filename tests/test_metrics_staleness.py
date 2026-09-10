"""A failed live read must not read as a fresh one.

`_provider_metrics` caught every exception and fell back to what was
stored — right — and then said "Measured by <provider>, 3 hours ago",
which was not. A stale figure presented as a current one is the worst
shape of wrong: the page looks correct, so nobody has cause to doubt it.

It matters more now there are two metrics providers. An outage at one
would have read as ordinary data.

Two more faults on the same path, both the false-zero family that took
the site down this morning:

  - the write did `vals.get("spotify_followers") or 0` and hardcoded 0
    for popularity and deezer_fans, so every row the metrics provider
    stored claimed a popularity of zero and no Deezer following;
  - the read used `if s["followers"]`, so a genuine zero was skipped as
    though it had never been measured.
"""
import uuid

import pytest

import db as store
import signal_providers as sp
import spotify_provider as spot

PASSWORD = "stale-123"
SPOTIFY = {"name": "King 810", "image": "", "genres": [], "followers": 104233,
           "popularity": 47, "url": "", "top_tracks": []}


class Flaky(sp.MusicIntelligenceProvider):
    """A configured provider that can be made to fail on demand."""
    key, label = "fakecharts", "Fakecharts"
    capabilities = (sp.CAP_ARTIST, sp.CAP_METRICS)

    def __init__(self, fail=False):
        self.fail = fail

    def configured(self):
        return True

    def search_artists(self, query, limit=20):
        return [{"provider_artist_id": "fc-1", "name": "King 810"}]

    def get_artist_metrics(self, pid, start, end):
        if self.fail:
            raise sp.ProviderError("Fakecharts 503: down")
        return [{"date": end.isoformat(), "metric": "spotify_monthly_listeners",
                 "value": 45210}]


@pytest.fixture
def artist(monkeypatch):
    import app as appmod
    monkeypatch.setattr(spot, "pulse_configured", lambda: True)
    monkeypatch.setattr(spot, "artist_pulse", lambda aid: dict(SPOTIFY))
    c = appmod.app.test_client()
    email = "stale-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "A", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    with appmod.app.app_context():
        c._uid = store.get_user_by_email(email)["id"]
        store.save_pulse_profile(c._uid, "king810", "King 810")
    c._app = appmod.app
    return c


def _with(artist, fail):
    with artist._app.app_context():
        sp.reset_registry(sp.ProviderRegistry(adapters=[Flaky(fail=fail)]))
    return artist.get("/pulse").get_data(as_text=True)


def test_a_good_read_says_it_measured(artist):
    body = _with(artist, fail=False)
    assert "measured by Fakecharts" in body
    assert "last figures on file" not in body


def test_a_failed_read_says_the_read_failed(artist):
    _with(artist, fail=False)          # something on file to fall back to
    body = _with(artist, fail=True)
    assert "did not answer just now" in body
    assert "measured by Fakecharts" not in body, (
        "the heading must not claim a measurement it did not take")


def test_the_failure_is_quoted_in_the_vendors_own_words(artist):
    _with(artist, fail=False)
    body = _with(artist, fail=True)
    assert "Fakecharts 503: down" in body, (
        "'failed' sends nobody anywhere; their message might")


def test_the_stored_figure_is_still_shown_and_dated(artist):
    """Falling back is right. Presenting it as today's reading is not."""
    _with(artist, fail=False)
    body = _with(artist, fail=True)
    assert "45,210" in body, "the last real figure is still useful"
    assert "not a reading taken today" in body


def test_the_provider_never_writes_a_nought_it_did_not_measure(artist):
    """It measures listening. It says nothing about Deezer, and 0 there
    claims a following of nobody."""
    _with(artist, fail=False)
    with artist._app.app_context():
        rows = store.list_pulse_snapshots(artist._uid, provider="fakecharts")
    assert rows
    assert rows[-1]["popularity"] is None
    assert rows[-1]["deezer_fans"] is None
    assert rows[-1]["monthly_listeners"] == 45210


def test_a_genuine_zero_is_a_reading(artist):
    """The read filtered on truthiness, so nought followers looked like
    never-measured."""
    with artist._app.app_context():
        sp.reset_registry(sp.ProviderRegistry(adapters=[Flaky(fail=False)]))
        store.record_pulse_snapshot(artist._uid, 0, None, None,
                                    provider="fakecharts", day="2026-09-09")
        rows = store.list_pulse_snapshots(artist._uid, provider="fakecharts")
    assert any(r["followers"] == 0 for r in rows)

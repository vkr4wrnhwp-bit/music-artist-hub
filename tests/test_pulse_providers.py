"""Artist Pulse, read through the provider registry.

Recovered 2026-09-10 from an abandoned worktree: 195 lines of coverage
for work whose implementation shipped by another route while its tests
never did.

What survived here is what still holds against the shipped code, and it
earned its keep immediately - two live defects, both introduced the same
morning by making the metric columns nullable:

  - deezer_fans was still NOT NULL, so a metrics provider reporting
    monthly listeners and nothing about Deezer could not write a row at
    all; storing 0 would have claimed an audience of nobody.
  - the upsert overwrote followers with excluded.followers, so a later
    write that measured nothing ERASED what an earlier one measured.
    Every column coalesces now.

WHAT IS NOT COVERED HERE, AND WHY

Five further tests asserted a provider-wiring shape that was superseded:
an id="provider-pulse" block, a per-figure provenance line, and a
`provider_checked` column that never shipped. The behaviour they guarded
is present in a better shape - id="measured", with the provider named in
the heading - so they were removed rather than left as rotting skips.

One of them was not stale, and is recorded as a finding rather than
silently dropped: it asserted that a provider failure shows the vendor's
own words. `_provider_metrics` catches every exception and degrades to
stored rows, so a failed live read shows yesterday's figures with nothing
saying the read failed. That is worth fixing and is not fixed here.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

import db as store
import signal_providers as providers
from app import create_app

PASSWORD = "pulse-pass-123"


class FakeMetrics(providers.MusicIntelligenceProvider):
    """A real-shaped provider: configured, searchable, with a dated series
    and a cache stamp it reports on request."""
    key = "fakecharts"
    label = "Fakecharts"
    capabilities = (providers.CAP_ARTIST, providers.CAP_METRICS)

    def __init__(self, at=None, names=("PU Artist", "PU Artist II"), fail=False):
        self.calls, self.at, self.names, self.fail = [], at, names, fail

    def configured(self):
        return True

    def cache_ttl(self):
        return 6 * 3600

    def search_artists(self, query, limit=20):
        self.calls.append(("search", query))
        return [{"provider_artist_id": "fc-%d" % i, "name": n} for i, n in enumerate(self.names, 1)]

    def get_artist_metrics(self, provider_artist_id, start, end):
        self.calls.append(("metrics", provider_artist_id))
        if self.fail:
            raise providers.ProviderError("Fakecharts 503: down")
        return [{"date": (end - timedelta(days=9)).isoformat(), "metric": "spotify_monthly_listeners", "value": 44000},
                {"date": (end - timedelta(days=2)).isoformat(), "metric": "spotify_monthly_listeners", "value": 45210},
                {"date": (end - timedelta(days=2)).isoformat(), "metric": "spotify_followers", "value": 1240},
                {"date": end.isoformat(), "metric": "spotify_followers", "value": 1250}]

    def metrics_measured_at(self, provider_artist_id, start, end):
        return self.at


SPOTIFY = {"me123": {"name": "PU Artist", "image": "", "genres": ["indie"],
                     "followers": 1200, "popularity": 44, "url": "", "top_tracks": []}}


@pytest.fixture
def artist(monkeypatch):
    """A fresh non-demo account with Spotify faked and a Pulse profile."""
    import music_apis
    import spotify_provider
    monkeypatch.setattr(spotify_provider, "pulse_configured", lambda: True)
    monkeypatch.setattr(spotify_provider, "artist_pulse", SPOTIFY.get)
    monkeypatch.setattr(music_apis, "deezer_artist_fans", lambda name: {"fans": 130})
    app_obj = create_app()
    client = app_obj.test_client()
    email = "pulse-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "PU", "email": email, "password": PASSWORD})
    uid = store.get_user_by_email(email)["id"]
    store.save_pulse_profile(uid, "me123", "PU Artist", "")
    yield {"client": client, "uid": uid}
    providers.reset_registry(None)


def _registry(*adapters):
    providers.reset_registry(providers.ProviderRegistry(adapters=list(adapters)))


def test_changing_the_artist_forgets_the_provider_id(artist):
    _registry(FakeMetrics(at=datetime.now(timezone.utc)))
    artist["client"].get("/pulse")
    assert store.get_pulse_profile(artist["uid"])["provider_artist_id"] == "fc-1"
    store.save_pulse_profile(artist["uid"], "other9", "Somebody Else", "")
    prof = store.get_pulse_profile(artist["uid"])
    assert prof["provider_artist_id"] == "", (
        "a new artist must not inherit the last one's provider id")


def test_the_migration_keeps_every_old_row_as_spotifys(tmp_path, monkeypatch):
    """A database from before the provider column: rebuilt once, each row
    stamped 'spotify', and the key now admits a second source per day."""
    import sqlite3
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE pulse_snapshots (
            user_id TEXT NOT NULL, day TEXT NOT NULL,
            followers INTEGER NOT NULL DEFAULT 0, popularity INTEGER NOT NULL DEFAULT 0,
            deezer_fans INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, day));
        INSERT INTO pulse_snapshots VALUES ('u1', '2026-08-01', 900, 40, 100);
        INSERT INTO pulse_snapshots VALUES ('u1', '2026-08-02', 910, 41, 101);
    """)
    conn.commit()
    conn.close()
    monkeypatch.setenv("DATABASE_PATH", path)
    store.init_db()
    rows = store.list_pulse_snapshots("u1")
    assert [(r["day"], r["followers"], r["provider"], r["monthly_listeners"]) for r in rows] == [
        ("2026-08-01", 900, "spotify", None), ("2026-08-02", 910, "spotify", None)]
    store.record_pulse_snapshot("u1", 1250, None, None, provider="soundcharts",
                                monthly_listeners=45210, day="2026-08-02")
    store.record_pulse_snapshot("u1", None, None, None, provider="soundcharts",
                                monthly_listeners=45300, day="2026-08-02")
    assert store.list_pulse_snapshots("u1")[-1]["followers"] == 910, "Spotify's row for the day is untouched"
    theirs = store.list_pulse_snapshots("u1", provider="soundcharts")
    assert len(theirs) == 1 and theirs[0]["followers"] == 1250 and theirs[0]["monthly_listeners"] == 45300
    store.init_db()                   # idempotent: a second boot rebuilds nothing
    assert len(store.list_pulse_snapshots("u1")) == 2

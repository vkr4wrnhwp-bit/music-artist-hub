"""The meter bridge on Artist Pulse, approved from the mockup of 2026-09-13.

One instrument per growth signal. Each says what it read, who measured
it and when, and how it moved; a reading nobody took stays dark and
says so. The provider-measured figures sit in their own row, apart from
the platforms' own numbers, so the "measured" promise is kept exact.
"""
from datetime import date, timedelta

import pytest

import pulse_signals


TODAY = date(2026, 9, 12)


def _snaps(*rows):
    """(days_back, followers, popularity, deezer) -> stored-snapshot dicts."""
    return [{"day": (TODAY - timedelta(days=b)).isoformat(), "followers": f,
             "popularity": p, "deezer_fans": d, "monthly_listeners": None}
            for b, f, p, d in rows]


def test_a_reading_nobody_took_stays_dark():
    out = pulse_signals.build(None, None, None, None, [], today=TODAY)
    by = {i["key"]: i for i in out}
    assert by["followers"]["shown"] is None and by["followers"]["state"] == "none"
    assert by["followers"]["value"] is None, "not 0"
    assert by["tiktok"]["state"] == "none" and by["tiktok"]["detail"] == "No data available from this platform."
    assert by["tiktok"]["rail_pos"] is None and by["tiktok"]["spark"] is None


def test_a_live_reading_with_history_carries_movement_and_range():
    snaps = _snaps((28, 12640, 40, 9000), (14, 12700, 41, 9100), (7, 12830, 41, 9150))
    pulse = {"followers": 12908, "popularity": 42}
    out = pulse_signals.build(pulse, None, None, {"fans": 9200}, snaps, today=TODAY)
    f = {i["key"]: i for i in out}["followers"]
    assert f["shown"] == "12,908" and f["state"] == "fresh" and f["lamp"] == "fresh"
    assert f["delta28"] == 2.1 and f["delta7"] == 0.6
    assert f["low"] == 12640 and f["high"] == 12908 and f["rail_pos"] == 100
    assert f["spark"] and f["spark_first"] == "12.6k" and f["spark_last"] == "12.8k"
    assert f["provider"] == "Spotify" and f["as_of"] == "2026-09-12"


def test_an_omitted_live_figure_falls_back_to_the_last_snapshot_and_reads_stale():
    snaps = _snaps((3, 1000, 30, 50))
    out = pulse_signals.build({"followers": None, "popularity": None}, None, None, None, snaps, today=TODAY)
    f = {i["key"]: i for i in out}["followers"]
    assert f["shown"] == "1,000" and f["state"] == "stale" and f["lamp"] == "3 days old"
    assert "has not returned a follower count" in f["detail"]


def test_the_provider_row_is_kept_apart_from_the_platform_row():
    metrics = {"label": "FakeCharts", "monthly_listeners": 42100, "followers": 8800,
               "as_of": "2026-09-12", "stale": False, "note": "Measured by FakeCharts, 3 hours ago.",
               "snapshots": [{"day": "2026-09-01", "monthly_listeners": 39000, "followers": None},
                             {"day": "2026-09-12", "monthly_listeners": 42100, "followers": 8800}]}
    out = pulse_signals.build({"followers": 100, "popularity": 10}, metrics, None, None, [], today=TODAY)
    sources = [(i["key"], i["source"]) for i in out]
    assert ("listeners", "provider") in sources and ("followers_provider", "provider") in sources
    assert ("followers", "platform") in sources, "Spotify's own count is a separate instrument"
    listeners = [i for i in out if i["key"] == "listeners"][0]
    assert listeners["shown"] == "42,100" and listeners["delta28"] is None, "one point 11 days back is not a 28-day change"
    assert listeners["provider"] == "FakeCharts"


def test_youtube_has_no_line_and_says_so():
    out = pulse_signals.build(None, None, {"subscribers": 31400, "views": 1, "note": ""}, None, [], today=TODAY)
    y = {i["key"]: i for i in out}["youtube"]
    assert y["shown"] == "31,400" and y["history"] is False and y["spark"] is None
    assert y["detail"] == "Current total only; no history is available."


def test_the_page_draws_the_bridge_and_never_prints_none(monkeypatch):
    import uuid
    import db as store
    import spotify_provider as sp
    from app import create_app

    app_obj = create_app()
    client = app_obj.test_client()
    email = "bridge-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "B", "email": email, "password": "bridge-pass-12345"})
    client.post("/plan/switch", data={"plan": "pro"})
    with app_obj.app_context():
        uid = store.get_user_by_email(email)["id"]
        store.save_pulse_profile(uid, "spotify-artist-b", "Bridge Band")
        for followers, back in ((90000, 30), (95000, 14), (100500, 7)):
            store.record_pulse_snapshot(uid, followers, 40, 9000,
                                        day=(date.today() - timedelta(days=back)).isoformat())
    artist = {"id": "spotify-artist-b", "name": "Bridge Band", "followers": {"total": 104233},
              "popularity": 47, "genres": [], "images": [], "external_urls": {}}
    monkeypatch.setattr(sp, "pulse_configured", lambda: True)
    monkeypatch.setattr(sp, "app_token", lambda: "token")
    monkeypatch.setattr(sp, "_api", lambda path, token: (
        artist if "/artists/" in path and "top-tracks" not in path else {"tracks": []}))
    body = client.get("/pulse").get_data(as_text=True)
    assert 'id="pulse-bridge"' in body and 'data-signal="followers"' in body
    assert '<span class="sbm-v">104,233</span>' in body
    assert 'data-signal="tiktok"' in body and "No data available from this platform." in body
    assert "None" not in body.replace("NoneType", "")
    prov = body.split('data-signal="followers"')[1][:1600]
    assert "<b>Spotify</b>" in prov and date.today().isoformat() in prov, "provenance on the instrument"

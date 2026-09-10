"""A pinned peer whose numbers Spotify withheld must not 500 the page.

Follow-on from the Artist Pulse crash. `pulse_peer_snapshots.followers`
and `.popularity` were NOT NULL DEFAULT 0, and the writer passes the
provider's value straight through — and an explicit NULL is never
replaced by a column DEFAULT. So the moment Spotify omitted a follower
count for a pinned artist, SQLite raised a constraint error and took
/pulse down for that account, on a number that isn't even the owner's.

Also held here: the Artist OS audience line reads from the snapshots
that carry a number, so it can never print "Followers None → None"
directly beneath the words "Real numbers ... not projections."
"""
import uuid

import pytest

import app as appmod
import artist_os
import db as store
import spotify_provider as sp

PASSWORD = "peer-null-123"


@pytest.fixture
def client():
    c = appmod.app.test_client()
    email = "peer-%s@example.net" % uuid.uuid4().hex[:10]
    c.post("/signup", data={"name": "Owner", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    with appmod.app.app_context():
        c._uid = store.get_user_by_email(email)["id"]
    return c


def test_a_peer_with_no_follower_count_is_recorded_as_not_measured(client, monkeypatch):
    peer_id = "peer-%s" % uuid.uuid4().hex[:8]
    with appmod.app.app_context():
        store.save_pulse_profile(client._uid, "mine-%s" % uuid.uuid4().hex[:8], "King 810")
        store.add_pulse_peer(client._uid, peer_id, "Kublai Khan TX")
    monkeypatch.setattr(sp, "pulse_configured", lambda: True)
    monkeypatch.setattr(sp, "app_token", lambda: "token")
    # Spotify answers, but sends neither field — the shape that crashed.
    monkeypatch.setattr(sp, "_api", lambda path, token: (
        {"id": peer_id, "name": "Kublai Khan TX", "images": []}
        if "/artists/" in path and "top-tracks" not in path else {"tracks": []}))

    page = client.get("/pulse")
    assert page.status_code == 200, "a withheld peer number is not a page failure"

    with appmod.app.app_context():
        history = store.list_peer_snapshots(client._uid, peer_id)
    assert history, "the reading is still on file"
    assert history[0]["followers"] is None, "stored as a silence, not as nought"


def test_the_audience_line_never_reads_none():
    """Two snapshots, neither carrying a number: say nothing, not "None"."""
    silent = [{"followers": None, "popularity": None, "deezer_fans": 9200},
              {"followers": None, "popularity": None, "deezer_fans": 9000}]
    report = artist_os.twin_report([], {}, silent, [])
    blob = repr(report)
    assert "Followers None" not in blob and "popularity None" not in blob
    assert "Real numbers from your connected profiles" not in blob, (
        "an unmeasured pair cannot be presented as real numbers")

    measured = [{"followers": 104233, "popularity": 47, "deezer_fans": 9200},
                {"followers": 90000, "popularity": 41, "deezer_fans": 9000}]
    blob = repr(artist_os.twin_report([], {}, measured, []))
    assert "Followers 90000 → 104233" in blob, "real readings still report"


def test_a_mixed_history_counts_only_what_was_measured():
    mixed = [{"followers": 104233, "popularity": 47, "deezer_fans": 9300},
             {"followers": None, "popularity": None, "deezer_fans": 9200},
             {"followers": 90000, "popularity": 41, "deezer_fans": 9000}]
    blob = repr(artist_os.twin_report([], {}, mixed, []))
    assert "over your last 2 snapshots" in blob, (
        "the count names the readings behind the line, not the days on file")

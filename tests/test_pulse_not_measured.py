"""A day Spotify did not measure must not take the whole page down.

Live, 2026-09-10: /pulse returned 500. Spotify omits `followers` and
`popularity` for some applications, and the honest reading of that is
"not measured" rather than nought — so the provider now returns None and
the snapshot column is nullable. Nothing downstream was ready for it:

  app.py      my_delta7 = pulse["followers"] - base["followers"]
              TypeError: unsupported operand type(s) for -: 'NoneType' and 'int'
  pulse.html  {% set fmax = (snaps | map(attribute='followers') | max) %}
              TypeError: '>' not supported between instances of 'NoneType' and 'int'

The second one is the worse of the two: once a single unmeasured
snapshot is on file, the trendline breaks for every later reading as
well, measured or not. So the page must render both ways — an
unmeasured day is a gap in the line, and the scale is taken from the
days that were measured.
"""
import uuid
from datetime import date, timedelta

import pytest

import app as appmod
import db as store
import spotify_provider as sp

PASSWORD = "pulse-null-123"
ARTIST = {"id": "5eAWyUcuTM24ZC1LOWnzDL", "name": "King 810", "images": []}


@pytest.fixture
def client():
    c = appmod.app.test_client()
    email = "pulse-null-%s@example.net" % uuid.uuid4().hex[:10]
    c.post("/signup", data={"name": "Owner", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    with appmod.app.app_context():
        c._uid = store.get_user_by_email(email)["id"]
    return c


def _history(client, artist_id):
    """Three weeks of readings, so the page draws a trendline at all."""
    with appmod.app.app_context():
        store.save_pulse_profile(client._uid, artist_id, "King 810")
        for followers, back in ((90000, 30), (95000, 14), (100500, 7)):
            store.record_pulse_snapshot(
                client._uid, followers, 40, 9000,
                day=(date.today() - timedelta(days=back)).isoformat())


def _live(monkeypatch, artist):
    monkeypatch.setattr(sp, "pulse_configured", lambda: True)
    monkeypatch.setattr(sp, "app_token", lambda: "token")
    monkeypatch.setattr(sp, "_api", lambda path, token: (
        artist if "/artists/" in path and "top-tracks" not in path else {"tracks": []}))


def test_the_page_holds_when_spotify_sends_no_follower_count(client, monkeypatch):
    _history(client, "no-count-%s" % uuid.uuid4().hex[:8])
    _live(monkeypatch, dict(ARTIST))          # no `followers`, no `popularity`
    page = client.get("/pulse")
    assert page.status_code == 200, "an omitted field is a silence, not a crash"
    body = page.get_data(as_text=True)
    assert "Not measured" in body, "and it is named, not shown as zero"
    assert "0 followers" not in body


def test_a_measured_reading_still_reports_its_number(client, monkeypatch):
    _history(client, "measured-%s" % uuid.uuid4().hex[:8])
    _live(monkeypatch, dict(ARTIST, followers={"total": 104233}, popularity=47))
    body = client.get("/pulse").get_data(as_text=True)
    assert "104,233" in body
    assert "100,000 Spotify followers" in body, "the milestone still lands"


def test_an_unmeasured_day_is_a_gap_in_the_line_not_a_crash(client, monkeypatch):
    """The trendline is the part that broke for everyone, retroactively."""
    artist_id = "gap-%s" % uuid.uuid4().hex[:8]
    _history(client, artist_id)
    with appmod.app.app_context():
        # Yesterday: Spotify answered, but not with a number.
        store.record_pulse_snapshot(client._uid, None, None, 9200,
                                    day=(date.today() - timedelta(days=1)).isoformat())
    _live(monkeypatch, dict(ARTIST, followers={"total": 104233}, popularity=47))
    page = client.get("/pulse")
    assert page.status_code == 200, (
        "one unmeasured snapshot must not break the graph for every later "
        "reading as well")
    body = page.get_data(as_text=True)
    # The measured days are still plotted, and the scale comes from them.
    assert "<polyline" in body
    assert "1 of 5 days not measured" in body, "the gap is disclosed, not hidden"


def test_the_provider_returns_a_silence_rather_than_a_nought(monkeypatch):
    assert sp._count(None) is None, "absent is not zero"
    assert sp._count(0) == 0, "and zero, when sent, is a real reading"
    assert sp._count(104233) == 104233

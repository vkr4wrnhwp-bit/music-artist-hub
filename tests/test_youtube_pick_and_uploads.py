"""YouTube on Pulse, after the owner's two notes of 2026-09-14.

  * "no one ever knows their handle": a search by name lists the
    matching channels with handle, subscribers and picture, and the
    person picks one; the pick posts the id the way a paste does.
  * "is this all the info we get from youtube": the panel now also
    shows the video count, the year the channel started, and the latest
    uploads with their own view, like and comment counters. A counter
    a channel switched off is a dash, never a zero.
"""
import uuid
from urllib.parse import parse_qs, urlparse

import pytest

import signal_providers as providers
from tests.test_youtube_metrics import (CHANNEL, OTHER, PASSWORD, Wire, _channel_body,  # noqa: F401
                                        _yt_section, flask_app)


def _search_body(*hits):
    return {"items": [{"id": {"kind": "youtube#channel", "channelId": cid},
                       "snippet": {"title": title}} for cid, title in hits]}


class PickWire(Wire):
    """The canned transport, plus search hits with two channels and the
    uploads playlist of the first."""

    def __call__(self, url):
        u = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path.endswith("/search"):
            self.calls.append(url)
            return _search_body((CHANNEL, "Devora"), (OTHER, "Devora Covers"))
        if u.path.endswith("/channels") and "," in (q.get("id") or ""):
            self.calls.append(url)
            body = _channel_body(CHANNEL)
            body["items"][0]["snippet"]["thumbnails"] = {"default": {"url": "https://yt.test/devora.jpg"}}
            body["items"][0]["snippet"]["publishedAt"] = "2014-03-09T00:00:00Z"
            other = _channel_body(OTHER, subs="0", hidden=True, title="Devora Covers", custom="")["items"][0]
            body["items"].append(other)
            return body
        if u.path.endswith("/playlistItems"):
            self.calls.append(url)
            assert q["playlistId"] == "UU" + CHANNEL[2:], "the uploads playlist by convention"
            return {"items": [{"contentDetails": {"videoId": "vid1"}},
                              {"contentDetails": {"videoId": "vid2"}}]}
        if u.path.endswith("/videos"):
            self.calls.append(url)
            return {"items": [
                {"id": "vid1", "snippet": {"title": "Narrow (Official Video)", "publishedAt": "2026-08-30T12:00:00Z"},
                 "statistics": {"viewCount": "120400", "likeCount": "3100", "commentCount": "212"}},
                {"id": "vid2", "snippet": {"title": "Live at the Room", "publishedAt": "2026-07-02T12:00:00Z"},
                 "statistics": {"viewCount": "8021"}}]}
        return Wire.__call__(self, url)


@pytest.fixture
def yt(monkeypatch):
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_CACHE_S", "0")
    wire = PickWire()
    body = _channel_body(CHANNEL)
    body["items"][0]["snippet"]["publishedAt"] = "2014-03-09T00:00:00Z"
    body["items"][0]["snippet"]["country"] = "US"
    adapter = providers.YouTubeAdapter(fetch=wire)
    providers.reset_registry(providers.ProviderRegistry(adapters=[adapter]))
    yield adapter, wire
    providers.reset_registry(None)


def test_a_name_search_lists_channels_a_person_can_tell_apart(yt):
    adapter, wire = yt
    out = adapter.search_channels("Devora")
    assert [c["channel_id"] for c in out] == [CHANNEL, OTHER]
    first, second = out
    assert first["title"] == "Devora" and first["handle"] == "@devora"
    assert first["subscribers"] == 184000 and first["image"] == "https://yt.test/devora.jpg"
    assert first["url"] == "https://www.youtube.com/@devora"
    assert second["subscribers"] is None, "a hidden count is not a count of nobody"
    assert second["url"] == "https://www.youtube.com/channel/" + OTHER
    assert len([c for c in wire.calls if c.endswith("/search") or "/search?" in c]) == 1
    assert adapter.search_channels("   ") == [] and adapter.searches == 1


def test_the_latest_uploads_carry_their_own_counters_and_no_zero_for_absent(yt):
    adapter, _ = yt
    ups = adapter.get_recent_videos(CHANNEL)
    assert [u["video_id"] for u in ups] == ["vid1", "vid2"]
    assert ups[0] == {"video_id": "vid1", "title": "Narrow (Official Video)", "published": "2026-08-30",
                      "url": "https://www.youtube.com/watch?v=vid1",
                      "views": 120400, "likes": 3100, "comments": 212}
    assert ups[1]["views"] == 8021 and ups[1]["likes"] is None and ups[1]["comments"] is None
    assert adapter.get_recent_videos("not-a-channel") == []


@pytest.fixture
def artist(flask_app):
    import db as store
    email = "ytpick-%s@example.net" % uuid.uuid4().hex[:10]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "YT Picker", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with flask_app.app_context():
        uid = store.get_user_by_email(email)["id"]
        store.save_pulse_profile(uid, "spotify-artist-ytp", "YT Picker")
    return {"client": client, "uid": uid}


def test_the_page_searches_by_name_and_the_pick_is_a_plain_form(artist, yt, flask_app):
    import db as store
    client = artist["client"]
    body = client.get("/pulse").get_data(as_text=True)
    section = _yt_section(body)
    assert 'id="yt-q"' in section and "Or search the channel by name" in section
    assert '"/pulse/youtube/search?q="' in body and "Use this channel" in body
    r = client.get("/pulse/youtube/search?q=Devora")
    data = r.get_json()
    assert data["ok"] and [c["channel_id"] for c in data["results"]] == [CHANNEL, OTHER]
    assert client.get("/pulse/youtube/search?q=").get_json() == {"ok": True, "results": []}
    # the pick: the same post a paste makes, with the id
    r = client.post("/pulse/youtube", data={"channel": CHANNEL})
    assert r.status_code in (302, 303)
    with flask_app.app_context():
        assert store.get_pulse_profile(artist["uid"])["youtube_channel_id"] == CHANNEL


def test_the_panel_shows_videos_since_and_the_latest_uploads(artist, yt):
    client = artist["client"]
    client.post("/pulse/youtube", data={"channel": "@devora"})
    section = _yt_section(client.get("/pulse").get_data(as_text=True))
    assert '<span class="sb-lcd-v">35,211,870</span>' in section
    assert '<span class="sb-lcd-v">6,041</span>' in section and "videos" in section
    assert "Latest uploads" in section
    assert "Narrow (Official Video)" in section and "120,400 views" in section and "3,100 likes" in section
    assert "8,021 views" in section and "— likes" in section and "— comments" in section
    assert "A dash is a counter the channel switched off, not a zero." in section


def test_a_stranger_and_an_unconfigured_server_get_no_search(artist, monkeypatch):
    client = artist["client"]
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setenv("YOUTUBE_ENABLED", "1")
    providers.reset_registry(providers.ProviderRegistry(adapters=[providers.YouTubeAdapter(fetch=Wire())]))
    try:
        data = client.get("/pulse/youtube/search?q=Devora").get_json()
        assert data["ok"] is False and "no YouTube key" in data["error"]
    finally:
        providers.reset_registry(None)
    from app import create_app
    r = create_app().test_client().get("/pulse/youtube/search?q=Devora")
    assert r.status_code in (302, 401) and not (r.get_json() or {}).get("results"), "the login wall, nothing else"

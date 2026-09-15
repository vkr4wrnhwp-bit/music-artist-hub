"""Pulse says what Spotify no longer sends (owner, staging, 2026-09-15:
"the spotify information went away completely in pulse"). Spotify has
retired followers, popularity and genres for apps like this one, and the
top-tracks call came back empty on staging. The page names that instead
of showing an empty space, and the intro no longer promises those figures.
"""
import uuid

import db as store
import spotify_provider as spotify
from app import create_app


def test_an_empty_top_tracks_answer_is_named_with_spotifys_reason(monkeypatch):
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "secret")
    monkeypatch.setattr(spotify, "app_token", lambda: "tok")

    def api(path, token):
        if path.startswith("/artists/king810/top-tracks"):
            spotify._REFUSAL = "Insufficient client scope"
            raise RuntimeError("403")
        return {"id": "king810", "name": "King 810", "external_urls": {"spotify": "https://open.spotify.com/artist/king810"}}
    monkeypatch.setattr(spotify, "_api", api)
    monkeypatch.setattr(store, "cache_get", lambda key, ttl: None)
    monkeypatch.setattr(store, "cache_set", lambda key, value: None)
    pulse = spotify.artist_pulse("king810")
    assert pulse["top_tracks"] == [] and pulse["top_note"] == "Insufficient client scope"
    assert pulse["followers"] is None and pulse["popularity"] is None and pulse["genres"] == []

    app_obj = create_app()
    c = app_obj.test_client()
    email = "sp-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Sp", "email": email, "password": "sp-pass-123"})
    c.post("/plan/switch", data={"plan": "pro"})
    with app_obj.app_context():
        store.save_pulse_profile(store.get_user_by_email(email)["id"], "king810", "King 810")
    monkeypatch.setattr(spotify, "artist_pulse", lambda artist_id: pulse)
    body = c.get("/pulse").get_data(as_text=True)
    assert "Spotify sent no top tracks for this artist to this app: " in body
    assert "Insufficient client scope" in body
    assert "Spotify no longer sends follower, popularity or genre figures" in body
    assert "Spotify followers, popularity, and current top tracks" not in body

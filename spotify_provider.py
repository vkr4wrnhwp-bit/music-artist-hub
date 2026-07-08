"""Spotify pre-save provider.

Real OAuth against the Spotify Web API, entirely env-gated: with no
credentials configured the provider reports unavailable, the pre-save
button never renders, and the notify-me email fallback carries the page.
Nothing is faked and missing credentials never crash a public page.

Fan tokens are encrypted at rest (Fernet keyed from SECRET_KEY) and used
for exactly two things: saving the track to the fan's library on release
day and reading their email (with consent) for the Fan CRM.

Development-mode note: new Spotify apps are limited to 25 allowlisted
users until Spotify grants a quota extension — the artist manages that
in the Spotify dashboard, not here.
"""

import base64
import hashlib
import json
import os
import urllib.parse
import urllib.request

SCOPES = "user-library-modify user-read-email"
_TIMEOUT = 8


def configured():
    return bool(os.environ.get("SPOTIFY_CLIENT_ID")
                and os.environ.get("SPOTIFY_CLIENT_SECRET")
                and os.environ.get("SPOTIFY_REDIRECT_URI"))


def _fernet():
    from cryptography.fernet import Fernet
    secret = os.environ.get("SECRET_KEY", "royalty-sweep-demo-session")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_token(token):
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(blob):
    return _fernet().decrypt(blob.encode()).decode()


def _http(url, data=None, headers=None):
    """Single seam for every Spotify call — tests monkeypatch this."""
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        body = resp.read()
        return json.loads(body.decode("utf-8")) if body else {}


def auth_url(state):
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": os.environ["SPOTIFY_CLIENT_ID"],
        "response_type": "code",
        "redirect_uri": os.environ["SPOTIFY_REDIRECT_URI"],
        "scope": SCOPES,
        "state": state,
    })


def _basic_auth_header():
    raw = "%s:%s" % (os.environ["SPOTIFY_CLIENT_ID"],
                     os.environ["SPOTIFY_CLIENT_SECRET"])
    return {"Authorization": "Basic " + base64.b64encode(raw.encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded"}


def exchange_code(code):
    """Authorization code -> {access_token, refresh_token}."""
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": os.environ["SPOTIFY_REDIRECT_URI"]}).encode()
    return _http("https://accounts.spotify.com/api/token", data=data,
                 headers=_basic_auth_header())


def refresh_access(refresh_token):
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token", "refresh_token": refresh_token}).encode()
    out = _http("https://accounts.spotify.com/api/token", data=data,
                headers=_basic_auth_header())
    return out.get("access_token")


def get_me(access_token):
    """Fan's Spotify id + email (email scope is consented in the OAuth screen)."""
    return _http("https://api.spotify.com/v1/me",
                 headers={"Authorization": "Bearer " + access_token})


def save_track(access_token, track_id):
    req = urllib.request.Request(
        "https://api.spotify.com/v1/me/tracks?ids=" + urllib.parse.quote(track_id),
        data=b"", method="PUT",
        headers={"Authorization": "Bearer " + access_token})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.status in (200, 201)


def track_id_from_url(url):
    """open.spotify.com/track/<id>?... -> <id>, else None."""
    if "open.spotify.com/track/" in (url or ""):
        return url.split("open.spotify.com/track/")[1].split("?")[0].split("/")[0]
    return None

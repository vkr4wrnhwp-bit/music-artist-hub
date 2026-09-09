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


def refresh_access_full(refresh_token):
    """Like refresh_access but keeps the whole response (incl. scope)."""
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token", "refresh_token": refresh_token}).encode()
    return _http("https://accounts.spotify.com/api/token", data=data,
                 headers=_basic_auth_header())


def get_me(access_token):
    """Fan's Spotify id + email (email scope is consented in the OAuth screen)."""
    return _http("https://api.spotify.com/v1/me",
                 headers={"Authorization": "Bearer " + access_token})


def save_track(access_token, track_id):
    # Spotify's Feb 2026 migration deprecated PUT /me/tracks for dev-mode
    # apps (bare 403); the generic library endpoint takes URIs in the query.
    req = urllib.request.Request(
        "https://api.spotify.com/v1/me/library?" + urllib.parse.urlencode(
            {"uris": "spotify:track:" + track_id}),
        data=b"", method="PUT",
        headers={"Authorization": "Bearer " + access_token,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.status in (200, 201, 204)


def track_id_from_url(url):
    """open.spotify.com/track/<id>?... -> <id>, else None."""
    if "open.spotify.com/track/" in (url or ""):
        return url.split("open.spotify.com/track/")[1].split("?")[0].split("/")[0]
    return None


# --- Artist Pulse: app-level (client credentials) catalog reads -----------------
# No fan login involved — these read Spotify's public artist data with the
# same client id/secret the pre-save flow uses. Redirect URI not required.

PULSE_TOKEN_TTL = 3000       # Spotify app tokens last 3600s; refresh early
PULSE_DATA_TTL = 6 * 3600    # follower counts move slowly


def pulse_configured():
    return bool(os.environ.get("SPOTIFY_CLIENT_ID")
                and os.environ.get("SPOTIFY_CLIENT_SECRET"))


def app_token():
    """Client-credentials access token, cached until near expiry."""
    import db as store
    tok = store.cache_get("spotify:app_token", PULSE_TOKEN_TTL)
    if tok:
        return tok
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    out = _http("https://accounts.spotify.com/api/token", data=data,
                headers=_basic_auth_header())
    tok = out.get("access_token")
    if tok:
        store.cache_set("spotify:app_token", tok)
    return tok


def _api(path, token):
    return _http("https://api.spotify.com/v1" + path,
                 headers={"Authorization": "Bearer " + token})


_REFUSAL = None


def last_refusal():
    """Why the last lookup came back empty, when the reason was Spotify's
    and not the search term's - so a wrong credential is never shown to
    somebody as their own spelling mistake. None when nothing refused."""
    return _REFUSAL


def clear_refusal():
    global _REFUSAL
    _REFUSAL = None


def _note(exc):
    """Keep Spotify's own words. Their token endpoint answers 400 with
    {"error": "invalid_client", "error_description": "Invalid client
    secret"}, which is the one thing worth putting in front of a person."""
    global _REFUSAL
    body = ""
    try:
        body = (exc.read() or b"").decode("utf-8", "replace")
    except Exception:
        body = str(exc)
    said = ""
    try:
        doc = json.loads(body)
        said = doc.get("error_description") or doc.get("error") or ""
        if isinstance(doc.get("error"), dict):
            said = doc["error"].get("message") or said
    except Exception:
        said = (body or str(exc))[:200]
    _REFUSAL = said or str(exc)[:200]


def _count(value):
    """An int Spotify actually sent, or None. A field they omit is not a
    zero: printing 0 followers beside a name is a claim about the artist,
    and a wrong one - it is also the number somebody uses to tell two
    same-named profiles apart."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def search_artists(q, limit=8):
    """Live artist search: [{id, name, followers, popularity, image, genres}].

    `followers` and `popularity` are None when Spotify did not send them."""
    q = (q or "").strip()
    clear_refusal()
    if not q:
        return []
    if not pulse_configured():
        global _REFUSAL
        _REFUSAL = "Spotify is not connected on this deployment (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)."
        return []
    try:
        token = app_token()
        if not token:
            if _REFUSAL is None:
                _REFUSAL = "Spotify did not issue a token for this app's credentials."
            return []
        data = _api("/search?" + urllib.parse.urlencode(
            {"q": q, "type": "artist", "limit": limit}), token)
    except Exception as e:
        _note(e)
        return []
    out = []
    for a in (data.get("artists") or {}).get("items", []):
        images = a.get("images") or []
        out.append({
            "id": a.get("id"), "name": a.get("name"),
            "followers": _count((a.get("followers") or {}).get("total")),
            "popularity": _count(a.get("popularity")),
            "image": images[-1]["url"] if images else "",
            "genres": (a.get("genres") or [])[:3],
        })
    return [a for a in out if a["id"] and a["name"]]


def artist_pulse(artist_id):
    """Live profile + current top tracks for one artist; None on any miss."""
    import db as store
    if not artist_id or not pulse_configured():
        return None
    key = "pulse:%s" % artist_id
    cached = store.cache_get(key, PULSE_DATA_TTL)
    if cached:
        return cached
    try:
        token = app_token()
        if not token:
            return None
        artist = _api("/artists/" + urllib.parse.quote(artist_id), token)
    except Exception:
        return None
    try:
        top = _api("/artists/%s/top-tracks?market=US"
                   % urllib.parse.quote(artist_id), token)
    except Exception:
        top = {}  # top tracks are a bonus, never the whole pulse
    if not artist.get("id"):
        return None
    images = artist.get("images") or []
    pulse = {
        "id": artist["id"],
        "name": artist.get("name") or "",
        "followers": _count((artist.get("followers") or {}).get("total")),
        "popularity": _count(artist.get("popularity")),
        "genres": artist.get("genres") or [],
        "image": images[0]["url"] if images else "",
        "url": ((artist.get("external_urls") or {}).get("spotify") or ""),
        "top_tracks": [{
            "name": t.get("name") or "",
            "popularity": t.get("popularity", 0),
            "album": ((t.get("album") or {}).get("name") or ""),
            "url": ((t.get("external_urls") or {}).get("spotify") or ""),
        } for t in (top.get("tracks") or [])[:10]],
    }
    store.cache_set(key, pulse)
    return pulse

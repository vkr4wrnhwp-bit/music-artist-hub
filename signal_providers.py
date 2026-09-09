"""Street Banker Signal - provider adapter layer.

The product must never be a wrapper around one data vendor. Every external
source sits behind `MusicIntelligenceProvider`, and the rest of Signal only
ever talks to the interface. Swapping Soundcharts for Chartmetric, or using
one provider for city movement and another for playlists, is a registry
change - not a rewrite.

Phase 1 ships:
  * the interface,
  * a deterministic mock adapter so the whole product works with no
    credentials at all,
  * typed stubs for the real providers that declare their capabilities and
    report `configured=False` until their env vars exist.

Nothing here invents provider fields. A stub that has not been implemented
raises NotImplementedError rather than returning a plausible-looking guess,
because a fabricated distributor or manager is worse than a blank one.

Feature flags (all default off; see .env.example):
    SOUNDCHARTS_ENABLED, CHARTMETRIC_ENABLED, MUSICBRAINZ_ENABLED,
    MLC_ENABLED, SOUNDEXCHANGE_ENABLED, SPOTIFY_METADATA_ENABLED,
    WEB_ENRICHMENT_ENABLED, INTERNAL_REVENUE_ENABLED,
    PRIVATE_AUDIO_ENABLED, AUDIO_INTELLIGENCE_ENABLED, YOUTUBE_ENABLED
"""
import base64
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import random
import re
from datetime import date, datetime, timedelta, timezone

# --- capabilities -----------------------------------------------------------
# What a provider can answer. The registry picks a provider per capability,
# so no single vendor has to cover the whole product.

CAP_ARTIST = "artist"
CAP_METRICS = "metrics"
CAP_RELEASES = "releases"
CAP_CITIES = "cities"
CAP_PLAYLISTS = "playlists"
CAP_SOCIAL = "social"
CAP_EVENTS = "events"
CAP_DISTRIBUTOR = "distributor"
CAP_LABEL = "label"
CAP_CONTACTS = "contacts"
CAP_RIGHTS = "rights"

ALL_CAPABILITIES = (CAP_ARTIST, CAP_METRICS, CAP_RELEASES, CAP_CITIES,
                    CAP_PLAYLISTS, CAP_SOCIAL, CAP_EVENTS, CAP_DISTRIBUTOR,
                    CAP_LABEL, CAP_CONTACTS, CAP_RIGHTS)

CAPABILITY_LABELS = {
    CAP_ARTIST: "Artist identity",
    CAP_METRICS: "Streaming & audience metrics",
    CAP_RELEASES: "Releases & tracks",
    CAP_CITIES: "City / territory movement",
    CAP_PLAYLISTS: "Playlist activity",
    CAP_SOCIAL: "Social activity",
    CAP_EVENTS: "Live events",
    CAP_DISTRIBUTOR: "Distributor evidence",
    CAP_LABEL: "Label evidence",
    CAP_CONTACTS: "Professional contacts",
    CAP_RIGHTS: "Rights & registration evidence",
}


def _utcnow():
    """The clock the Soundcharts cache reads; a test moves it forward."""
    return datetime.now(timezone.utc)


def _flag(name):
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


class ProviderError(RuntimeError):
    """A provider failed. Callers degrade; they never crash a page."""


class _HttpError(ProviderError):
    """A non-2xx answer from a transport seam, before it is worded for the
    caller. `code` is the HTTP status; `msg` is the body's own message."""

    def __init__(self, code, msg):
        ProviderError.__init__(self, "%s %s" % (code, msg))
        self.code, self.msg = int(code or 0), msg or ""


class MusicIntelligenceProvider(object):
    """The one interface Signal talks to.

    Subclasses declare `key`, `label` and `capabilities`, and implement only
    the methods their capabilities claim. Anything not claimed must raise
    NotImplementedError - never a fabricated value.
    """

    key = "base"
    label = "Base provider"
    capabilities = ()
    # Cost per request in USD, used by the usage dashboard. 0 for free/mock.
    cost_per_request = 0.0

    def configured(self):
        """True when this provider has what it needs to make real calls."""
        return False

    def health_check(self):
        return {"provider": self.key, "configured": self.configured(),
                "ok": self.configured(), "detail": "not configured",
                "capabilities": list(self.capabilities)}

    def supports(self, capability):
        return capability in self.capabilities

    # Every method below is optional per capability.
    def search_artists(self, query, limit=20):
        raise NotImplementedError

    def get_artist(self, provider_artist_id):
        raise NotImplementedError

    def get_artist_metrics(self, provider_artist_id, start, end):
        raise NotImplementedError

    def get_artist_releases(self, provider_artist_id):
        raise NotImplementedError

    def get_artist_cities(self, provider_artist_id, start, end):
        raise NotImplementedError

    def get_playlist_activity(self, provider_artist_id, start, end):
        raise NotImplementedError

    def get_social_activity(self, provider_artist_id, start, end):
        raise NotImplementedError

    def get_events(self, provider_artist_id):
        raise NotImplementedError

    def get_distributor_evidence(self, provider_release_id):
        raise NotImplementedError

    def get_label_evidence(self, provider_release_id):
        raise NotImplementedError

    def get_contact_evidence(self, provider_artist_id):
        raise NotImplementedError

    def get_rights_evidence(self, isrc=None, title=None, artist=None):
        raise NotImplementedError


# --- real providers: declared, not faked ------------------------------------
# Each declares what it could answer and stays unconfigured until its
# credentials exist. Signal shows them in /signal/admin/data-sources as
# "not configured" rather than pretending they are live.

class _EnvProvider(MusicIntelligenceProvider):
    env_flag = ""
    env_keys = ()

    def configured(self):
        if not _flag(self.env_flag):
            return False
        return all((os.environ.get(k) or "").strip() for k in self.env_keys)

    def health_check(self):
        if not _flag(self.env_flag):
            detail = "disabled (%s is not set)" % self.env_flag
        elif not self.configured():
            missing = [k for k in self.env_keys if not (os.environ.get(k) or "").strip()]
            detail = "enabled but missing credentials: %s" % ", ".join(missing)
        else:
            detail = "configured"
        return {"provider": self.key, "configured": self.configured(),
                "ok": self.configured(), "detail": detail,
                "capabilities": list(self.capabilities)}


# Soundcharts' own career-stage words, on this product's three-step ladder.
_SC_STAGES = {"superstar": "Established", "mainstream": "Established",
              "mid_level": "Developing", "developing": "Developing",
              "long_tail": "Emerging"}
_SC_RELEASE_TYPES = {"single": "Single", "album": "Album", "ep": "EP",
                     "compilation": "Compilation"}
_SC_MAJORS = ("universal", "sony", "warner")
# Distributor names as Soundcharts prints them, lower-cased, on the ladder
# in signal_store.DISTRIBUTOR_CLASSES. A name not here is "Needs Research"
# - that class exists precisely so nobody guesses.
_SC_DISTRIBUTORS = {
    "distrokid": "DIY / Self-Service", "tunecore": "DIY / Self-Service",
    "cd baby": "DIY / Self-Service", "cdbaby": "DIY / Self-Service",
    "amuse": "DIY / Self-Service", "ditto": "DIY / Self-Service",
    "routenote": "DIY / Self-Service", "landr": "DIY / Self-Service",
    "unitedmasters": "DIY / Self-Service", "soundrop": "DIY / Self-Service",
    "symphonic": "Independent Distributor", "stem": "Independent Distributor",
    "empire": "Independent Distributor", "vydia": "Independent Distributor",
    "believe": "Enterprise Distribution", "kobalt": "Enterprise Distribution",
    "fuga": "Enterprise Distribution", "idol": "Enterprise Distribution",
    "awal": "Major-Affiliated Distribution", "the orchard": "Major-Affiliated Distribution",
    "orchard": "Major-Affiliated Distribution", "ingrooves": "Major-Affiliated Distribution",
    "virgin": "Major-Affiliated Distribution", "ada": "Major-Affiliated Distribution",
    "caroline": "Major-Affiliated Distribution", "alternative distribution alliance": "Major-Affiliated Distribution",
}


def _sc_distributor_class(name):
    n = (name or "").strip().lower()
    if not n:
        return "Unknown"
    if any(m in n for m in _SC_MAJORS):
        return "Major Label"
    tokens = set(t for t in re.split(r"[^a-z0-9]+", n) if t)
    for key, cls in _SC_DISTRIBUTORS.items():
        if all(t in tokens for t in key.split()):
            return cls
    return "Needs Research"


# Where a Soundcharts client id + secret is exchanged for a bearer token
# (their OAuth client-credentials grant). A test points this at nothing.
SOUNDCHARTS_TOKEN_URL = "https://account.soundcharts.com/oauth/token"

SOUNDCHARTS_AUTH_LABELS = {"oauth": "OAuth client credentials",
                           "token": "access token issued by Soundcharts",
                           "legacy": "legacy app id + api key"}


class SoundchartsAdapter(_EnvProvider):
    """Soundcharts, over its customer API (v2).

    Written and verified against their public sandbox - credentials
    `soundcharts` / `soundcharts`, two artists, fixed date ranges - so the
    shapes below are the sandbox's own, not a reading of the docs. A paid
    plan is the same base URL with the account's app id and key; an
    endpoint the plan does not include answers 403, which becomes a
    ProviderError and an empty capability, never a guess.

    What it measures: Spotify monthly listeners (their 28-day rolling
    figure, with a weekly city breakdown), Spotify followers (daily),
    current social counts, playlist positions, events, and per-album
    label / UPC / distributor. Soundcharts marks its distributor field
    beta, so that evidence carries a lower confidence here.

    Signing in: new integrations get a client id + secret and exchange them
    for a bearer token (OAuth client credentials, one hour, re-minted on
    expiry and on a 401). The older app id + api key headers still work
    for integrations that were issued them, so both pairs are accepted;
    when both are set the client pair wins.
    """
    key = "soundcharts"
    label = "Soundcharts"
    env_flag = "SOUNDCHARTS_ENABLED"
    env_keys = ("SOUNDCHARTS_APP_ID", "SOUNDCHARTS_API_KEY")          # legacy pair
    oauth_keys = ("SOUNDCHARTS_CLIENT_ID", "SOUNDCHARTS_CLIENT_SECRET")
    token_kv_key = "soundcharts:oauth-token"
    token_margin_s = 60          # a token this close to expiry is re-minted, not used
    capabilities = (CAP_ARTIST, CAP_METRICS, CAP_RELEASES, CAP_CITIES,
                    CAP_PLAYLISTS, CAP_SOCIAL, CAP_EVENTS, CAP_DISTRIBUTOR, CAP_LABEL)
    base_url = "https://customer.api.soundcharts.com"
    albums_per_artist = 8        # one metadata call each, so bounded
    max_pages = 4                # a paged list is followed this far, no further

    cache_ttl_default = 6 * 3600     # SOUNDCHARTS_CACHE_S overrides; 0 disables

    def __init__(self, fetch=None, http=None, token_http=None):
        # `fetch(url)` answers a whole API call (body or ProviderError) and
        # bypasses auth - the shape tests use it. `http(url, headers)` and
        # `token_http(url, headers, body)` replace only the wire, so the
        # auth path itself can be driven without a network.
        self._fetch = fetch
        self._http = http
        self._token_http = token_http

    # -- credentials --
    @staticmethod
    def _env(name):
        return (os.environ.get(name) or "").strip()

    token_key = "SOUNDCHARTS_ACCESS_TOKEN"   # a bearer Soundcharts issued ready-made
    _pair_instead = False                    # set when their 401 says it is an api key, not a bearer

    def auth_mode(self):
        """"oauth" with a client id + secret, "token" with a ready-made
        access token (what their dashboard hands a new account beside the
        app id), "legacy" with an app id + api key, "" with none. The
        client pair wins, then the token, then the legacy pair."""
        if all(self._env(k) for k in self.oauth_keys):
            return "oauth"
        if self._env(self.token_key):
            return "token"
        if all(self._env(k) for k in self.env_keys):
            return "legacy"
        return ""

    def configured(self):
        return _flag(self.env_flag) and self.auth_mode() != ""

    def health_check(self):
        mode = self.auth_mode()
        if not _flag(self.env_flag):
            detail = "disabled (%s is not set)" % self.env_flag
        elif not mode:
            detail = ("enabled but missing credentials: %s + %s, or %s (or, for an integration "
                      "issued them, %s + %s)" % (self.oauth_keys + (self.token_key,) + self.env_keys))
        else:
            detail = "configured"
        return {"provider": self.key, "configured": self.configured(),
                "ok": self.configured(), "detail": detail,
                "auth": SOUNDCHARTS_AUTH_LABELS.get(mode, ""),
                "capabilities": list(self.capabilities)}

    # -- bearer token --
    # Minted once, kept in the app's key/value store with its expiry, and
    # reused by every process until sixty seconds before it lapses. A 401
    # on an API call forgets it and mints once more before giving up.
    def _token_read(self):
        try:
            import db
            raw = db.get_kv(self.token_kv_key)
        except Exception:
            return None
        if not raw:
            return None
        try:
            entry = json.loads(raw)
            expires_at = datetime.fromisoformat(entry["expires_at"])
        except Exception:
            return None
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if entry.get("client_id") != self._env("SOUNDCHARTS_CLIENT_ID"):
            return None              # a token minted for other credentials
        if (expires_at - _utcnow()).total_seconds() <= self.token_margin_s:
            return None
        return entry.get("token") or None

    def _token_write(self, token, expires_in):
        expires_at = _utcnow() + timedelta(seconds=max(0, int(expires_in or 0)))
        try:
            import db
            db.set_kv(self.token_kv_key, json.dumps({
                "token": token, "expires_at": expires_at.isoformat(timespec="seconds"),
                "client_id": self._env("SOUNDCHARTS_CLIENT_ID")}))
        except Exception:
            pass                     # the token still serves this call

    def _token_forget(self):
        try:
            import db
            db.set_kv(self.token_kv_key, "")
        except Exception:
            pass

    def _mint_token(self):
        """POST the client-credentials grant; returns (token, expires_in)."""
        basic = base64.b64encode(("%s:%s" % (self._env("SOUNDCHARTS_CLIENT_ID"),
                                             self._env("SOUNDCHARTS_CLIENT_SECRET"))).encode("utf-8"))
        headers = {"Authorization": "Basic " + basic.decode("ascii"),
                   "Content-Type": "application/x-www-form-urlencoded",
                   "Accept": "application/json", "User-Agent": "StreetBanker/1.0"}
        form = {"grant_type": "client_credentials"}
        if self._env("SOUNDCHARTS_TEAM_ID"):
            form["team_id"] = self._env("SOUNDCHARTS_TEAM_ID")
        body = urllib.parse.urlencode(form)
        try:
            if self._token_http is not None:
                answer = self._token_http(SOUNDCHARTS_TOKEN_URL, headers, body)
            else:
                answer = self._urlopen(SOUNDCHARTS_TOKEN_URL, headers, data=body.encode("utf-8"))
        except _HttpError as e:
            raise ProviderError("Soundcharts sign-in failed: %s %s" % (e.code, e.msg))
        except ProviderError as e:
            raise ProviderError("Soundcharts sign-in failed: %s" % e)
        except Exception as e:
            raise ProviderError("Soundcharts sign-in failed: %s" % e)
        token = (answer or {}).get("access_token") if isinstance(answer, dict) else None
        if not token:
            raise ProviderError("Soundcharts sign-in failed: no access_token in the answer")
        return token, (answer.get("expires_in") or 3600)

    def _token(self):
        token = self._token_read()
        if token:
            return token
        token, expires_in = self._mint_token()
        self._token_write(token, expires_in)
        return token

    def _auth_headers(self, mode):
        if mode == "oauth":
            return {"Authorization": "Bearer " + self._token()}
        if mode == "token":
            # Their dashboard hands out an app id and a second value whose
            # name varies; if it is really an api key, "token" mode is the
            # wrong shape and _fetch_json swaps to this one after a 401.
            if self._pair_instead:
                return {"x-app-id": self._env("SOUNDCHARTS_APP_ID"),
                        "x-api-key": self._env(self.token_key)}
            return {"Authorization": "Bearer " + self._env(self.token_key)}
        return {"x-app-id": self._env("SOUNDCHARTS_APP_ID"),
                "x-api-key": self._env("SOUNDCHARTS_API_KEY")}

    # -- cache --
    # Every answer is billed per call and moves slowly (monthly listeners are
    # a 28-day figure), so the same question inside six hours is answered from
    # the app's key/value store. Only a 200 is kept: a transient error that
    # stuck for six hours would be worse than no cache at all.
    @staticmethod
    def cache_ttl():
        raw = (os.environ.get("SOUNDCHARTS_CACHE_S") or "").strip()
        if raw == "":
            return SoundchartsAdapter.cache_ttl_default
        try:
            return max(0, int(float(raw)))
        except ValueError:
            return SoundchartsAdapter.cache_ttl_default

    @staticmethod
    def cache_key(path, params):
        raw = path + "?" + json.dumps(sorted((str(k), str(v)) for k, v in (params or {}).items()))
        return "soundcharts:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _cache_read(self, key, ttl):
        try:
            import db
            raw = db.get_kv(key)
        except Exception:
            return None
        if not raw:
            return None
        try:
            entry = json.loads(raw)
            at = datetime.fromisoformat(entry["at"])
        except Exception:
            return None
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if (_utcnow() - at).total_seconds() > ttl or entry.get("status") != 200:
            return None
        return entry.get("body")

    def _cache_write(self, key, body):
        try:
            import db
            db.set_kv(key, json.dumps({"at": _utcnow().isoformat(timespec="seconds"),
                                       "status": 200, "body": body}))
        except Exception:
            pass                     # the answer is still good without a cache

    def cached_at(self, path, params=None):
        """When the live cache last stored an answer to this question, or
        None if it holds none it would still serve.

        A page that shows one of these figures has to be able to say how
        old it is. Without this the six-hour cache is invisible from
        outside, and a caption would have to call a figure live that can
        be six hours behind.
        """
        ttl = self.cache_ttl()
        if not ttl:
            return None
        try:
            import db
            raw = db.get_kv(self.cache_key(path, params or {}))
        except Exception:
            return None
        if not raw:
            return None
        try:
            entry = json.loads(raw)
            at = datetime.fromisoformat(entry["at"])
        except Exception:
            return None
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if entry.get("status") != 200 or (_utcnow() - at).total_seconds() > ttl:
            return None
        return at

    def metrics_cached_at(self, provider_artist_id, start, end):
        """When the monthly-listeners answer behind `get_artist_metrics`
        for this window was measured. The capability's own age, asked for
        without the caller needing to know the endpoint."""
        return self.cached_at(
            "/api/v2/artist/%s/streaming/spotify/listening" % provider_artist_id,
            {"startDate": start.isoformat(), "endDate": end.isoformat()})

    # -- transport --
    def _get(self, path, **params):
        if not self.configured():
            raise ProviderError("Soundcharts: not configured")
        ttl = self.cache_ttl()
        key = self.cache_key(path, params) if ttl else None
        if key:
            hit = self._cache_read(key, ttl)
            if hit is not None:
                return hit
        body = self._fetch_json(path, **params)
        if key:
            self._cache_write(key, body)
        return body

    def _fetch_json(self, path, **params):
        """One HTTP call; a non-200 raises ProviderError and is never cached.

        In oauth mode a 401 means the bearer token died early (revoked,
        or the clock drifted): it is forgotten and the call retried once
        with a fresh one. A second 401 is the account's answer.

        In token mode a 401 may mean the value is not a bearer at all but
        the api key of their `x-app-id` + `x-api-key` pair - the owner's
        account showed exactly that in 2026-09. The other shape is tried
        once and, if it works, is remembered for this process.
        """
        url = self.base_url + path
        if params:
            url += ("&" if "?" in path else "?") + urllib.parse.urlencode(params)
        if self._fetch is not None:
            return self._fetch(url)
        mode = self.auth_mode()
        try:
            return self._call(url, mode)
        except _HttpError as e:
            if e.code == 401 and mode == "oauth":
                self._token_forget()
                try:
                    return self._call(url, mode)
                except _HttpError as again:
                    raise ProviderError("Soundcharts %s: %s" % (again.code, again.msg))
            if e.code == 401 and mode == "token" and self._env("SOUNDCHARTS_APP_ID"):
                # The value may be an api key rather than a bearer: try the
                # pair once, and keep whichever the account accepts.
                self._pair_instead = not self._pair_instead
                try:
                    answer = self._call(url, mode)
                except _HttpError as again:
                    self._pair_instead = not self._pair_instead
                    raise ProviderError("Soundcharts %s: %s" % (again.code, again.msg))
                return answer
            raise ProviderError("Soundcharts %s: %s" % (e.code, e.msg))

    def _call(self, url, mode):
        headers = dict(self._auth_headers(mode),
                       Accept="application/json")
        headers["User-Agent"] = "StreetBanker/1.0"
        if self._http is not None:
            return self._http(url, headers)
        return self._urlopen(url, headers)

    @staticmethod
    def _urlopen(url, headers, data=None):
        """The wire. A non-2xx raises _HttpError with the body's own message;
        anything else (DNS, timeout) raises ProviderError as it stands."""
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            msg = ""
            try:
                body = json.loads(e.read().decode("utf-8"))
                errs = body.get("errors") or []
                msg = ((errs[0].get("message") or "") if errs else
                       (body.get("error_description") or body.get("message") or body.get("error") or ""))
            except Exception:
                pass
            raise _HttpError(e.code, msg or e.reason)
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError("Soundcharts: %s" % e)

    def _items(self, path, **params):
        """Every item of a paged list, following page.next a bounded way.

        The first page is the contract and its failure is raised. A later
        page is best effort: their own next-link can carry parameters the
        account cannot use (the sandbox does this), and losing page two
        must not throw away page one.
        """
        out, pages = [], 0
        data = self._get(path, **params)
        while True:
            out.extend(data.get("items") or [])
            pages += 1
            nxt = (data.get("page") or {}).get("next")
            if not nxt or pages >= self.max_pages:
                return out
            try:
                data = self._get(nxt)
            except ProviderError:
                return out

    def _album(self, album_id):
        return self._get("/api/v2.51/album/by-uuid/%s" % album_id).get("object") or {}

    # -- shapes --
    @staticmethod
    def _artist_fields(a, listeners=None):
        genres = a.get("genres") or []
        genre = (genres[0].get("root") or "") if genres else ""
        return {
            "provider_artist_id": a.get("uuid") or "",
            "name": a.get("name") or "",
            "genre": genre.title(),
            "country": a.get("countryCode") or "",
            "city": a.get("cityName") or "",
            "state": "",
            "region": "",
            "career_stage": _SC_STAGES.get(a.get("careerStage") or "", ""),
            "monthly_listeners": listeners,
            "image_url": a.get("imageUrl") or "",
            "website": a.get("webUrl") or "",
            # Their metadata carries no social links; blank beats a guess.
            "socials": {"instagram": "", "tiktok": "", "youtube": ""},
            "growth_level": a.get("growthLevel") or "",
            "isni": a.get("isni") or "",
            "ipi": a.get("ipi") or "",
        }

    def search_artists(self, query, limit=20):
        q = (query or "").strip()
        if not q:
            # Their universe is millions of artists; there is no honest
            # "some of them". The demo universe is the mock's job.
            return []
        data = self._get("/api/v2/artist/search/%s" % urllib.parse.quote(q),
                         offset=0, limit=max(1, min(int(limit or 20), 100)))
        return [self._artist_fields(a) for a in data.get("items") or []]

    def get_artist(self, provider_artist_id):
        obj = self._get("/api/v2.9/artist/%s" % provider_artist_id).get("object")
        if not obj or not obj.get("uuid"):
            return None
        listeners = None
        try:
            stats = self._get("/api/v2/artist/%s/current/stats" % provider_artist_id)
            for row in stats.get("streaming") or []:
                if row.get("platform") == "spotify" and row.get("value") is not None:
                    listeners = int(row["value"])
        except ProviderError:
            pass                     # identity without the number, not no identity
        return self._artist_fields(obj, listeners)

    def get_artist_metrics(self, provider_artist_id, start, end):
        span = {"startDate": start.isoformat(), "endDate": end.isoformat()}
        out, errors = [], []
        try:
            for it in self._items("/api/v2/artist/%s/streaming/spotify/listening"
                                  % provider_artist_id, **span):
                if it.get("value") is not None and it.get("date"):
                    out.append({"date": it["date"][:10], "metric": "spotify_monthly_listeners",
                                "value": int(it["value"])})
        except ProviderError as e:
            errors.append(e)
        try:
            for it in self._items("/api/v2/artist/%s/audience/spotify" % provider_artist_id, **span):
                if it.get("followerCount") is not None and it.get("date"):
                    out.append({"date": it["date"][:10], "metric": "spotify_followers",
                                "value": int(it["followerCount"])})
        except ProviderError as e:
            errors.append(e)
        if not out and errors:
            raise errors[0]
        out.sort(key=lambda x: (x["metric"], x["date"]))
        return out

    def get_artist_cities(self, provider_artist_id, start, end):
        """Spotify's "where people listen", from the newest weekly breakdown
        in the window; the change is against the breakdown nearest 28 days
        earlier, or None when the window holds no such point."""
        items = [it for it in self._items("/api/v2/artist/%s/streaming/spotify" % provider_artist_id,
                                          startDate=start.isoformat(), endDate=end.isoformat())
                 if it.get("cityPlots")]
        if not items:
            return []
        items.sort(key=lambda it: it.get("date") or "")
        latest = items[-1]
        latest_day = date.fromisoformat(latest["date"][:10])
        earlier = None
        for it in items[:-1]:
            day = date.fromisoformat(it["date"][:10])
            if 21 <= (latest_day - day).days <= 35:
                earlier = it
        before = {}
        for c in (earlier or {}).get("cityPlots") or []:
            before[(c.get("cityName"), c.get("countryCode"))] = c.get("value")
        out = []
        for c in latest["cityPlots"]:
            key = (c.get("cityName"), c.get("countryCode"))
            change = None
            if before.get(key) and c.get("value") is not None:
                change = round((float(c["value"]) - before[key]) / before[key] * 100.0, 1)
            out.append({"city": c.get("cityName") or "", "region": c.get("region") or "",
                        "country": c.get("countryCode") or "", "country_name": c.get("countryName") or "",
                        "listeners": int(c.get("value") or 0), "change_28d_pct": change,
                        "as_of": latest["date"][:10]})
        out.sort(key=lambda x: -x["listeners"])
        return out

    def get_artist_releases(self, provider_artist_id):
        data = self._get("/api/v2.34/artist/%s/albums" % provider_artist_id,
                         sortBy="releaseDate", sortOrder="desc", limit=self.albums_per_artist)
        out = []
        for a in (data.get("items") or [])[:self.albums_per_artist]:
            item = {
                "provider_release_id": a.get("uuid") or "",
                "title": a.get("name") or "",
                "release_type": _SC_RELEASE_TYPES.get((a.get("type") or "").lower(), "Unknown"),
                "release_date": (a.get("releaseDate") or "")[:10],
                "credit_name": a.get("creditName") or "",
                "upc": "", "label_text": "", "distributor_name": "",
                "distributor_class": "Unknown", "copyright_line": "", "track_count": 0,
                "provider": self.key,
            }
            # The list carries no label, UPC or distributor; the album does.
            try:
                album = self._album(item["provider_release_id"]) if item["provider_release_id"] else {}
            except ProviderError:
                album = {}
            if album:
                labels = [l.get("name") for l in album.get("labels") or [] if l.get("name")]
                item["label_text"] = ", ".join(labels)
                item["upc"] = album.get("upc") or ""
                item["distributor_name"] = album.get("distributor") or ""
                item["distributor_class"] = _sc_distributor_class(item["distributor_name"])
                item["copyright_line"] = album.get("copyright") or ""
                item["track_count"] = int(album.get("totalTracks") or 0)
                if album.get("type"):
                    item["release_type"] = _SC_RELEASE_TYPES.get(album["type"].lower(), item["release_type"])
            out.append(item)
        out.sort(key=lambda x: x["release_date"], reverse=True)
        return out

    def get_distributor_evidence(self, provider_release_id):
        album = self._album(provider_release_id)
        name = album.get("distributor") or ""
        if not name:
            return []
        return [{"distributor_name": name, "classification": _sc_distributor_class(name),
                 "source_type": "release_metadata",
                 "source_label": "Soundcharts album metadata (their distributor field is beta)",
                 "source_url": "", "excerpt": album.get("copyright") or "",
                 "confidence": 0.6,
                 "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}]

    def get_label_evidence(self, provider_release_id):
        album = self._album(provider_release_id)
        out = []
        for l in album.get("labels") or []:
            if not l.get("name"):
                continue
            group = (l.get("type") or "").lower()
            out.append({"label_name": l["name"],
                        "classification": "Major Label" if any(m in group for m in _SC_MAJORS)
                        else "Independent Label",
                        "source_type": "release_metadata", "source_label": "Soundcharts album metadata",
                        "source_url": "", "excerpt": album.get("copyright") or "",
                        "confidence": 0.8,
                        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        return out

    def get_playlist_activity(self, provider_artist_id, start, end):
        data = self._get("/api/v2.20/artist/%s/playlist/current/spotify" % provider_artist_id,
                         sortBy="position", limit=50)
        out = []
        for it in data.get("items") or []:
            pl = it.get("playlist") or {}
            out.append({"playlist_name": pl.get("name") or "",
                        "curator_type": pl.get("type") or "",
                        "editorial": (pl.get("type") or "").lower() == "editorial",
                        "followers": int(pl.get("latestSubscriberCount") or 0),
                        "added_on": (it.get("entryDate") or "")[:10],
                        "position": it.get("position"), "peak_position": it.get("peakPosition"),
                        "song": (it.get("song") or {}).get("name") or "",
                        # Not measured by them; never estimated here.
                        "estimated_streams": None})
        return out

    def get_social_activity(self, provider_artist_id, start, end):
        stats = self._get("/api/v2/artist/%s/current/stats" % provider_artist_id)
        out = []
        for row in stats.get("social") or []:
            if row.get("value") is None:
                continue
            out.append({"platform": row.get("platform") or "", "followers": int(row["value"]),
                        # Their evolution is over 7 days; the 28-day field stays honest.
                        "change_28d_pct": None, "change_7d_pct": row.get("percentEvolution"),
                        "as_of": (row.get("date") or "")[:10]})
        return out

    def get_events(self, provider_artist_id):
        today = date.today().isoformat()
        out = []
        for ev in self._items("/api/v2/artist/%s/events" % provider_artist_id, type="all", limit=100):
            day = (ev.get("date") or ev.get("startedAt") or "")[:10]
            if not day or day < today:
                continue
            venue = ev.get("venue") or {}
            out.append({"date": day, "city": venue.get("cityName") or "",
                        "region": venue.get("region") or "", "country": venue.get("countryCode") or "",
                        "venue": venue.get("name") or "", "name": ev.get("name") or "",
                        "kind": ev.get("type") or "",
                        "festival": (ev.get("festival") or {}).get("name") if isinstance(ev.get("festival"), dict) else ""})
        out.sort(key=lambda x: x["date"])
        return out


class ChartmetricAdapter(_EnvProvider):
    key = "chartmetric"
    label = "Chartmetric"
    env_flag = "CHARTMETRIC_ENABLED"
    env_keys = ("CHARTMETRIC_REFRESH_TOKEN",)
    capabilities = (CAP_ARTIST, CAP_METRICS, CAP_RELEASES, CAP_CITIES,
                    CAP_PLAYLISTS, CAP_SOCIAL)


class MusicBrainzAdapter(_EnvProvider):
    """The open MusicBrainz database, over its JSON web service.

    Free, no account: their policy asks for a User-Agent that names a
    contact, which is the one thing the environment has to carry, and one
    request per second, which the adapter keeps to itself. What it answers
    is identity and catalogue - who an artist is, where they are from, what
    they have released and on which label. What it does NOT answer is
    listeners, followers, cities or playlists: MusicBrainz measures nothing,
    so those stay "not measured" rather than borrowing the demo's numbers
    (see ProviderRegistry.for_capability).

    Every method returns the same shapes the mock does, so the rest of
    Signal cannot tell which one answered - except that these are true.
    """
    key = "musicbrainz"
    label = "MusicBrainz"
    env_flag = "MUSICBRAINZ_ENABLED"
    env_keys = ("MUSICBRAINZ_CONTACT",)      # their policy requires a UA contact
    capabilities = (CAP_ARTIST, CAP_RELEASES, CAP_LABEL)
    base_url = "https://musicbrainz.org/ws/2"
    min_interval = 1.05                       # seconds between requests, their limit
    release_groups_per_artist = 8             # one extra request each, so bounded

    def __init__(self, fetch=None, sleep=None):
        self._fetch = fetch
        self._sleep = sleep if sleep is not None else time.sleep
        self._last = 0.0

    # -- transport --
    def _get(self, path, **params):
        params.setdefault("fmt", "json")
        url = "%s/%s?%s" % (self.base_url, path.lstrip("/"), urllib.parse.urlencode(params))
        wait = self.min_interval - (time.time() - self._last)
        if wait > 0:
            self._sleep(wait)
        self._last = time.time()
        if self._fetch is not None:
            return self._fetch(url)
        contact = (os.environ.get("MUSICBRAINZ_CONTACT") or "").strip()
        req = urllib.request.Request(url, headers={
            "User-Agent": "StreetBanker/1.0 ( %s )" % contact, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ProviderError("MusicBrainz: %s" % e)

    # -- shapes --
    @staticmethod
    def _artist_fields(a):
        tags = sorted(a.get("tags") or [], key=lambda t: -(t.get("count") or 0))
        area = a.get("area") or {}
        begin = a.get("begin-area") or {}
        socials = {"instagram": "", "tiktok": "", "youtube": ""}
        website = ""
        for rel in a.get("relations") or []:
            url = (rel.get("url") or {}).get("resource") or ""
            kind = rel.get("type") or ""
            if kind == "official homepage" and not website:
                website = url
            for name in socials:
                if name in url and not socials[name]:
                    socials[name] = url
        return {
            "provider_artist_id": a.get("id") or "",
            "name": a.get("name") or "",
            "genre": (tags[0].get("name") or "").title() if tags else "",
            "country": a.get("country") or "",
            "city": begin.get("name") or "",
            "state": "",
            "region": area.get("name") or "",
            # Not measured here. Left empty on purpose - never a guess.
            "career_stage": "",
            "monthly_listeners": None,
            "image_url": "",
            "website": website,
            "socials": socials,
            "disambiguation": a.get("disambiguation") or "",
        }

    def search_artists(self, query, limit=20):
        q = (query or "").strip()
        if not q:
            # A blank search is how the demo universe is seeded; there is no
            # honest way to pick "some artists" out of a million real ones.
            return []
        data = self._get("artist/", query=q, limit=max(1, min(int(limit or 20), 50)))
        return [self._artist_fields(a) for a in data.get("artists") or []]

    def get_artist(self, provider_artist_id):
        data = self._get("artist/%s" % provider_artist_id, inc="tags+url-rels")
        if not data or not data.get("id"):
            return None
        return self._artist_fields(data)

    def get_artist_releases(self, provider_artist_id):
        data = self._get("release-group/", artist=provider_artist_id,
                         limit=self.release_groups_per_artist)
        out = []
        for rg in data.get("release-groups") or []:
            item = {
                "provider_release_id": rg.get("id") or "",
                "title": rg.get("title") or "",
                "release_type": (rg.get("primary-type") or "Single"),
                "release_date": rg.get("first-release-date") or "",
                "upc": "", "label_text": "", "distributor_name": "",
                "distributor_class": "Unknown", "copyright_line": "", "track_count": 0,
                "provider": self.key,
            }
            # One release per group for its label and barcode; the group
            # alone carries neither.
            try:
                rel = self._get("release/", **{"release-group": rg.get("id") or "",
                                              "inc": "labels+media", "limit": 1})
            except ProviderError:
                rel = {}
            releases = rel.get("releases") or []
            if releases:
                r0 = releases[0]
                labels = [li.get("label") or {} for li in r0.get("label-info") or []]
                item["label_text"] = ", ".join(l.get("name") for l in labels if l.get("name"))
                item["upc"] = r0.get("barcode") or ""
                item["track_count"] = sum(int(m.get("track-count") or 0) for m in r0.get("media") or [])
            out.append(item)
        out.sort(key=lambda x: x["release_date"], reverse=True)
        return out

    def get_label_evidence(self, provider_release_id):
        data = self._get("release/", **{"release-group": provider_release_id,
                                        "inc": "labels", "limit": 1})
        releases = data.get("releases") or []
        if not releases:
            return []
        out = []
        for li in releases[0].get("label-info") or []:
            label = li.get("label") or {}
            if label.get("name"):
                out.append({"label_name": label["name"], "catalog_number": li.get("catalog-number") or "",
                            "source_type": "release_metadata", "source_label": "MusicBrainz release",
                            "source_url": "https://musicbrainz.org/release/%s" % (releases[0].get("id") or ""),
                            "confidence": 0.8})
        return out


class YouTubeAdapter(_EnvProvider):
    """YouTube, over the public Data API v3 with a server API key.

    Verified against the API reference (developers.google.com/youtube/v3)
    rather than guessed:

      * base `https://www.googleapis.com/youtube/v3`;
      * `GET /channels?part=snippet,statistics` with exactly one filter -
        `id=`, `forHandle=` (with or without the @) or `forUsername=` -
        costs 1 quota unit;
      * `GET /search?part=snippet&type=channel&q=` returns candidates as
        `items[].id.channelId`. Its reference page states "a quota cost of
        1 unit in the Search Queries quota bucket" - a separate, small
        bucket (it was 100 units against the main one for years). Either
        reading makes it the expensive call, so resolution tries every
        1-unit lookup first and searches at most once, never again once a
        channel id is stored;
      * `statistics` carries `subscriberCount`, `viewCount`, `videoCount`
        and `hiddenSubscriberCount`. A channel that hides its subscriber
        count reports `hiddenSubscriberCount: true` and YouTube then
        returns 0 - which is not an audience of nobody, so this adapter
        answers None for subscribers and the page reads "Not measured";
      * an error body is `{"error": {"code": .., "message": ..,
        "errors": [{"reason": "quotaExceeded" | "keyInvalid" |
        "accessNotConfigured", ..}]}}`. Google's own reason is carried
        into the ProviderError, because "403" alone does not tell an
        owner whether to wait a day or fix the key.

    Capability: CAP_SOCIAL only.

    NOT CAP_METRICS. The Data API answers with the channel's counters as
    they stand right now - a lifetime view total and a current subscriber
    count - and offers no history to anyone but the channel's owner
    (that is YouTube Analytics, a different API behind OAuth; see the
    separate YOUTUBE_CLIENT_ID/SECRET integration in social_providers).
    Claiming CAP_METRICS here would mean either an empty series or one
    invented from repeated reads of a total, so it is not claimed.

    This is a public read: no OAuth, no acting on a channel, nothing
    account-specific. It measures whatever channel the owner names.
    """
    key = "youtube"
    label = "YouTube"
    env_flag = "YOUTUBE_ENABLED"
    env_keys = ("YOUTUBE_API_KEY",)
    capabilities = (CAP_SOCIAL,)
    base_url = "https://www.googleapis.com/youtube/v3"

    cache_ttl_default = 6 * 3600     # YOUTUBE_CACHE_S overrides; 0 disables
    search_results = 5               # candidates asked for in the one search

    # A channel id is "UC" and 22 more of the URL-safe alphabet. Checked
    # rather than assumed, so a pasted playlist or video id is not sent
    # to the id= filter as if it were a channel.
    _ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")

    def __init__(self, fetch=None):
        # `fetch(url)` answers a whole API call (a body, or ProviderError).
        # The tests drive the adapter through it; production leaves it None
        # and the call goes out over urllib.
        self._fetch = fetch
        self.searches = 0            # search.list calls made by this instance

    # -- credentials --
    @staticmethod
    def api_key():
        return (os.environ.get("YOUTUBE_API_KEY") or "").strip()

    def missing_env(self):
        """The env var names this adapter still needs, for a page that has
        to say WHICH one is absent rather than "not configured"."""
        if not _flag(self.env_flag):
            return [self.env_flag] + [k for k in self.env_keys
                                      if not (os.environ.get(k) or "").strip()]
        return [k for k in self.env_keys if not (os.environ.get(k) or "").strip()]

    # -- cache --
    # Same six-hour store the Soundcharts adapter uses, keyed separately.
    # Subscriber counts are rounded by YouTube itself and move slowly, so
    # a page reload inside six hours must not spend quota. Only a 200 is
    # kept: a quota error cached for six hours would outlast the quota.
    @staticmethod
    def cache_ttl():
        raw = (os.environ.get("YOUTUBE_CACHE_S") or "").strip()
        if raw == "":
            return YouTubeAdapter.cache_ttl_default
        try:
            return max(0, int(float(raw)))
        except ValueError:
            return YouTubeAdapter.cache_ttl_default

    @staticmethod
    def cache_key(path, params):
        # The API key is added at the wire and never reaches here, so a
        # rotated key does not orphan the cache and no secret is hashed
        # into a key/value name.
        raw = path + "?" + json.dumps(sorted((str(k), str(v)) for k, v in (params or {}).items()))
        return "youtube:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _cache_read(self, key, ttl):
        try:
            import db
            raw = db.get_kv(key)
        except Exception:
            return None
        if not raw:
            return None
        try:
            entry = json.loads(raw)
            at = datetime.fromisoformat(entry["at"])
        except Exception:
            return None
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if (_utcnow() - at).total_seconds() > ttl or entry.get("status") != 200:
            return None
        return entry.get("body")

    def _cache_write(self, key, body):
        try:
            import db
            db.set_kv(key, json.dumps({"at": _utcnow().isoformat(timespec="seconds"),
                                       "status": 200, "body": body}))
        except Exception:
            pass                     # the answer is still good without a cache

    def cached_at(self, path, params=None):
        """When the cache last stored an answer to this question, or None
        if it holds none it would still serve. A page showing one of these
        numbers has to be able to say how old it is."""
        ttl = self.cache_ttl()
        if not ttl:
            return None
        try:
            import db
            raw = db.get_kv(self.cache_key(path, params or {}))
        except Exception:
            return None
        if not raw:
            return None
        try:
            entry = json.loads(raw)
            at = datetime.fromisoformat(entry["at"])
        except Exception:
            return None
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if entry.get("status") != 200 or (_utcnow() - at).total_seconds() > ttl:
            return None
        return at

    def social_cached_at(self, channel_id):
        """When the counts behind `get_social` for this channel were read.
        The capability's own age, without the caller knowing the endpoint."""
        return self.cached_at("/channels", self._social_params(channel_id))

    @staticmethod
    def _social_params(channel_id):
        return {"part": "snippet,statistics", "id": channel_id}

    # -- transport --
    def _get(self, path, **params):
        if not self.configured():
            raise ProviderError("YouTube: not configured (%s)"
                                % ", ".join(self.missing_env()))
        ttl = self.cache_ttl()
        key = self.cache_key(path, params) if ttl else None
        if key:
            hit = self._cache_read(key, ttl)
            if hit is not None:
                return hit
        body = self._fetch_json(path, **params)
        if key:
            self._cache_write(key, body)
        return body

    def _fetch_json(self, path, **params):
        """One HTTP call. A non-200 raises ProviderError carrying Google's
        own reason, and is never cached."""
        url = self.base_url + path + "?" + urllib.parse.urlencode(
            dict(params, key=self.api_key()))
        if self._fetch is not None:
            return self._fetch(url)
        try:
            return self._urlopen(url)
        except _HttpError as e:
            raise ProviderError(self.redact("YouTube %s: %s" % (e.code, e.msg)))

    @staticmethod
    def _urlopen(url):
        req = urllib.request.Request(url, headers={
            "Accept": "application/json", "User-Agent": "StreetBanker/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = {}
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                pass
            raise _HttpError(e.code, YouTubeAdapter.error_text(body) or str(e.reason))
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(YouTubeAdapter.redact("YouTube: %s" % e))

    @classmethod
    def redact(cls, text):
        """The same text with the API key taken out.

        The key travels in the query string, so a transport failure that
        quotes the URL would put it on a page. Nothing that reaches a
        viewer goes out unredacted.
        """
        out, key = str(text), cls.api_key()
        return out.replace(key, "[key]") if key else out

    @staticmethod
    def error_text(body):
        """Google's error, worded as Google worded it.

        `error.errors[0].reason` is the machine word an owner needs -
        `quotaExceeded` means wait, `keyInvalid` means fix the key,
        `accessNotConfigured` means switch YouTube Data API v3 on for the
        project. Restating it as "forbidden" would throw that away.
        """
        err = (body or {}).get("error") or {}
        errs = err.get("errors") or []
        first = errs[0] if errs else {}
        reason = (first.get("reason") or "").strip()
        msg = (first.get("message") or err.get("message") or "").strip()
        if reason and msg:
            return "%s - %s" % (reason, msg)
        return reason or msg

    # -- resolution --
    @classmethod
    def parse_channel_input(cls, value):
        """What the owner typed, as (kind, term).

        kind is "id" for a channel id, "handle" for an @handle, "username"
        for a legacy /user/ name, or "name" for anything else. A full URL
        is unwrapped first, so pasting the address bar works.
        """
        raw = (value or "").strip()
        if not raw:
            return ("", "")
        if "youtube.com" in raw.lower() or "youtu.be" in raw.lower():
            path = urllib.parse.urlsplit(
                raw if "//" in raw else "https://" + raw).path.strip("/")
            parts = [p for p in path.split("/") if p]
            if parts:
                head = parts[0]
                if head == "channel" and len(parts) > 1:
                    raw = parts[1]
                elif head == "user" and len(parts) > 1:
                    return ("username", parts[1])
                elif head == "c" and len(parts) > 1:
                    # A legacy custom URL is not a handle and not a
                    # username; only a search can turn it into an id.
                    return ("name", parts[1])
                else:
                    raw = head
        if cls._ID_RE.match(raw):
            return ("id", raw)
        if raw.startswith("@"):
            return ("handle", raw)
        return ("name", raw)

    def resolve_channel(self, value):
        """The channel id for what the owner typed, or "" for no match.

        Order is by quota: every 1-unit `channels.list` filter that could
        apply is tried first, and `search.list` runs at most once and only
        when none of them could answer. An explicit @handle or /user/ name
        is never widened into a search - a handle either exists or it does
        not, and searching for it would hand back somebody else's channel
        under a name the owner typed exactly.
        """
        kind, term = self.parse_channel_input(value)
        if not term:
            return ""
        if kind == "id":
            return self._by("id", term)
        if kind == "handle":
            return self._by("forHandle", term)
        if kind == "username":
            return self._by("forUsername", term)
        # A bare word could be a handle or a legacy username; both are
        # 1 unit, so both are tried before the search.
        if " " not in term:
            found = self._by("forHandle", term) or self._by("forUsername", term)
            if found:
                return found
        return self._search_once(term)

    def _by(self, filter_name, term):
        """One `channels.list` lookup: 1 quota unit, no match is "".

        A filter YouTube rejects outright (400 for a malformed handle, say)
        is not an error the owner needs to see as a failure - it is a
        no-match on that filter, and the next one still gets its turn.
        """
        try:
            data = self._get("/channels", part="id", **{filter_name: term})
        except ProviderError as e:
            if self._is_quota_or_key(e):
                raise
            return ""
        items = data.get("items") or []
        return (items[0].get("id") or "") if items else ""

    @staticmethod
    def _is_quota_or_key(err):
        """A quota or credential failure is the account's answer and must
        surface. A 400 on one filter is not."""
        text = str(err)
        return any(w in text for w in ("quotaExceeded", "keyInvalid",
                                       "accessNotConfigured", "not configured",
                                       "403", "401"))

    def _search_once(self, term):
        """The fallback, run at most once per resolution."""
        self.searches += 1
        data = self._get("/search", part="snippet", type="channel", q=term,
                         maxResults=self.search_results)
        for item in (data.get("items") or []):
            cid = ((item.get("id") or {}).get("channelId") or "").strip()
            if cid:
                return cid
        return ""

    # -- shapes --
    @staticmethod
    def _count(value):
        """A counter as an int, or None when YouTube did not report one.
        Never 0 for "absent" - 0 is a real number on this page."""
        if value is None or value == "":
            return None
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    def get_social(self, channel_id):
        """The channel's current counters, or None when YouTube has no
        such channel.

        `subscribers` is None - not 0 - when the channel hides its count:
        YouTube sends `hiddenSubscriberCount: true` and a
        `subscriberCount` of 0, and printing that would say the artist has
        no subscribers.
        """
        cid = (channel_id or "").strip()
        if not cid:
            return None
        data = self._get("/channels", **self._social_params(cid))
        items = data.get("items") or []
        if not items:
            return None
        item = items[0]
        stats = item.get("statistics") or {}
        snip = item.get("snippet") or {}
        hidden = bool(stats.get("hiddenSubscriberCount"))
        custom = (snip.get("customUrl") or "").strip()
        at = self.social_cached_at(cid) or _utcnow()
        return {
            "channel_id": item.get("id") or cid,
            "subscribers": None if hidden else self._count(stats.get("subscriberCount")),
            "views": self._count(stats.get("viewCount")),
            "videos": self._count(stats.get("videoCount")),
            "hidden": hidden,
            "channel_title": snip.get("title") or "",
            "channel_url": ("https://www.youtube.com/%s" % custom if custom
                            else "https://www.youtube.com/channel/%s" % (item.get("id") or cid)),
            "measured_at": at,
        }

    def get_social_activity(self, provider_artist_id, start, end):
        """Deliberately absent. The Data API has no public history: a
        series here would be invented from repeated reads of a total."""
        raise NotImplementedError(
            "YouTube's public API reports current totals, not a series")


class BandsintownAdapter(MusicIntelligenceProvider):
    """Bandsintown's public events API, for live dates only.

    Shares the EPK's provider (bandsintown_provider), so one app id and
    one cache serve both. It is keyed by the artist's name as Bandsintown
    spells it, which for Signal is the canonical name; a miss is an empty
    list, never a guess, and the tab says whose listing it is.
    """
    key = "bandsintown"
    label = "Bandsintown"
    capabilities = (CAP_EVENTS,)

    def __init__(self, events=None, resolve=None):
        self._events = events            # name -> rows, injectable
        self._resolve = resolve          # provider_artist_id -> name, injectable

    def configured(self):
        import bandsintown_provider
        return bandsintown_provider.configured()

    def health_check(self):
        on = self.configured()
        return {"provider": self.key, "configured": on, "ok": on,
                "detail": "configured" if on else "disabled (BANDSINTOWN_APP_ID is not set)",
                "capabilities": list(self.capabilities)}

    def events_for_name(self, name):
        if not self.configured():
            raise ProviderError("Bandsintown: not configured")
        import bandsintown_provider
        return list((self._events or bandsintown_provider.event_rows)(name))

    def get_events(self, provider_artist_id):
        if self._resolve is not None:
            name = self._resolve(provider_artist_id)
        else:
            import signal_store as sstore
            name = sstore.artist_name_for_provider_id(provider_artist_id)
        if not (name or "").strip():
            return []
        return self.events_for_name(name.strip())


class TourDatesAdapter(MusicIntelligenceProvider):
    """The artist's own TOUR, read first-hand (tour_dates.py): confirmed
    and advanced upcoming dates, for live events only.

    Bandsintown declined this platform an app_id (2026-09-07), so the
    dates the app already holds are the source. There is no key: the
    adapter is "configured" for the viewer who is signed in and owns at
    least one upcoming confirmed date, and for nobody else - so it is per
    request, on the viewer's own data.

    It is a real adapter under the registry's one rule: once it is
    configured the mock stands down for EVERY capability, and anything no
    real source covers is "not measured", never invented. The stored
    universe is a separate question - rows the mock ingested earlier stay
    fictional whoever is looking - so the Signal shell keeps its demo
    banner while any mock-ingested artist remains on screen
    (signal_store.seeded_by), even with this adapter answering.

    Rows answer only for the Signal artist whose name matches the tour's
    artist name (case-insensitively), or, for a tour with no artist name,
    when the page is the owner's own act. Another act's page never
    borrows these dates.
    """
    key = "tour_dates"
    label = "Your tour in Street Banker"
    capabilities = (CAP_EVENTS,)

    def __init__(self, user_id=None, resolve=None, own_names=None):
        self._user_id = user_id      # injectable; default is the Flask session
        self._resolve = resolve      # provider_artist_id -> name, injectable
        self._own_names = own_names  # user_id -> names the owner goes by, injectable

    def _uid(self):
        if self._user_id is not None:
            return self._user_id
        try:
            from flask import has_request_context, session
            if has_request_context():
                return session.get("user_id")
        except Exception:
            return None
        return None

    def configured(self):
        uid = self._uid()
        if not uid:
            return False
        import tour_dates
        return bool(tour_dates.upcoming(uid, limit=1))

    def health_check(self):
        on = self.configured()
        return {"provider": self.key, "configured": on, "ok": on,
                "detail": ("answering with the signed-in owner's confirmed dates" if on else
                           "no key needed; answers only for a signed-in owner with a "
                           "confirmed upcoming date in TOUR"),
                "capabilities": list(self.capabilities)}

    def _name_for(self, provider_artist_id):
        if self._resolve is not None:
            return self._resolve(provider_artist_id) or ""
        import signal_store as sstore
        name = sstore.artist_name_for_provider_id(provider_artist_id)
        if not name:
            # _live_events hands over the canonical id when an artist has
            # no provider ids yet; that row still has a name.
            name = (sstore.get_artist(provider_artist_id) or {}).get("canonical_name") or ""
        return name

    def _owner_names(self, uid):
        if self._own_names is not None:
            return list(self._own_names(uid) or [])
        import db as store
        names = [(store.get_user(uid) or {}).get("name") or ""]
        try:
            names.append((store.get_pulse_profile(uid) or {}).get("artist_name") or "")
        except Exception:
            pass
        return [n for n in names if n]

    def get_events(self, provider_artist_id):
        uid = self._uid()
        if not uid:
            return []
        name = (self._name_for(provider_artist_id) or "").strip()
        if not name:
            return []
        import tour_dates
        return tour_dates.event_rows(uid, artist_name=name,
                                     own_names=self._owner_names(uid))


class MLCAdapter(_EnvProvider):
    """The MLC Public Search API (https://public-api.themlc.com/api/doc).

    Access is a username and password The MLC issues after their Public
    Search API registration; the adapter trades them for a bearer token
    at /oauth/token, keeps it until it expires, and uses the refresh
    token after that. The API answers four things: recordings by ISRC or
    by title + artist (each carrying an MLC song code), works by title +
    writers, and works by song code - the work is where the writers, the
    publishers and their collection shares live.

    What this turns into evidence: a recording whose ISRC The MLC links
    to a work is "matched"; writers are "complete" when every one carries
    an IPI; a publisher is "detected" when the work lists one; shares are
    "complete" when the publishers' collection shares total 100. An ISRC
    The MLC has no work for is a potential gap - that is the unmatched
    money Royalty Sweep exists for. A title + artist with no recording is
    NOT a gap: album titles are not works, so that answer is silence.
    """
    key = "mlc"
    label = "The MLC"
    env_flag = "MLC_ENABLED"
    env_keys = ("MLC_USERNAME", "MLC_PASSWORD")
    capabilities = (CAP_RIGHTS,)
    base_url = "https://public-api.themlc.com"
    portal_search = "https://portal.themlc.com/search"
    token_margin = 60             # seconds before expiry a token counts as spent

    def __init__(self, transport=None, now=None):
        self._transport = transport
        self._now = now or time.time
        self._access, self._refresh, self._expires_at = "", "", 0.0
        self._id = ""                 # the Cognito ID token, the other bearer they may want
        self._bearer_kind = "access"  # which of the two the gateway last accepted

    # -- transport --
    def _send(self, method, path, body=None, bearer=""):
        """(status, json) for one call. Injectable for tests."""
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "User-Agent": "StreetBanker/1.0"}
        if bearer:
            headers["Authorization"] = "Bearer " + bearer
        url = self.base_url + path
        if self._transport is not None:
            return self._transport(method, url, headers, body)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, (json.loads(raw) if raw.strip() else None)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"message": raw[:200]}
        except Exception as e:
            raise ProviderError("The MLC: %s" % e)

    def _token(self):
        if self._access and self._now() < self._expires_at - self.token_margin:
            return self._access
        if not self.configured():
            raise ProviderError("The MLC: not configured")
        attempts = []
        if self._refresh:
            attempts.append({"refreshToken": self._refresh})
        attempts.append({"username": (os.environ.get("MLC_USERNAME") or "").strip(),
                         "password": (os.environ.get("MLC_PASSWORD") or "").strip()})
        last = "no answer"
        for body in attempts:
            status, answer = self._send("POST", "/oauth/token", body)
            answer = answer or {}
            if status == 200 and answer.get("accessToken"):
                self._access = answer["accessToken"]
                self._id = answer.get("idToken") or ""
                self._refresh = answer.get("refreshToken") or self._refresh
                try:
                    ttl = float(answer.get("expiresIn") or 3600)
                except (TypeError, ValueError):
                    ttl = 3600.0
                self._expires_at = self._now() + ttl
                return self._access
            last = answer.get("errorDescription") or answer.get("error") or answer.get("message") or str(status)
            self._refresh = ""            # a refresh that failed is spent
        raise ProviderError("The MLC sign-in failed: %s" % last)

    def _bearer(self):
        """The token the gateway last accepted; the ID token when that is
        what it wanted, the access token otherwise."""
        self._token()
        if self._bearer_kind == "id" and self._id:
            return self._id
        return self._access

    def _call(self, path, body):
        status, answer = self._send("POST", path, body, bearer=self._bearer())
        if status == 401:
            # Their gateway may want the other token (Cognito takes the ID
            # token as the bearer). Try it once, and remember what worked.
            other = "id" if self._bearer_kind == "access" else "access"
            self._bearer_kind = other
            alt = self._bearer()
            if alt:
                status, answer = self._send("POST", path, body, bearer=alt)
            if status == 401:
                # One retry with a fresh sign-in; a second 401 is their answer.
                self._bearer_kind = "access"
                self._access, self._id, self._expires_at = "", "", 0.0
                status, answer = self._send("POST", path, body, bearer=self._bearer())
        if status == 204:
            return []                     # their "no such recording": an answer, not a failure
        if status != 200:
            msg = (answer or {}).get("message") if isinstance(answer, dict) else ""
            if status == 401:
                msg = ("signed in, but the search was refused with both tokens - "
                       "the account's Public Search API access is not active, or the API "
                       "expects a bearer this app does not send (%s)" % (msg or "Unauthorized"))
            raise ProviderError("The MLC %s: %s" % (status, msg or "request failed"))
        return answer if isinstance(answer, list) else []

    # -- lookups, in the API's own units --
    def find_recordings(self, isrc=None, title=None, artist=None):
        body = {}
        if (isrc or "").strip():
            body["isrc"] = isrc.strip().upper().replace("-", "")
        else:
            if (title or "").strip():
                body["title"] = title.strip()
            if (artist or "").strip():
                body["artist"] = artist.strip()
        if not body:
            return []
        return [{"recording_id": r.get("id") or "", "isrc": r.get("isrc") or "",
                 "title": r.get("title") or "", "artist": r.get("artist") or "",
                 "labels": r.get("labels") or "", "song_code": r.get("mlcsongCode") or ""}
                for r in self._call("/search/recordings", body)]

    def find_works_by_title(self, title, writers=()):
        body = {"title": (title or "").strip(),
                "writers": [{"writerFirstName": w.get("first") or "", "writerLastName": w.get("last") or "",
                             "writerIPI": w.get("ipi") or ""} for w in writers]}
        if not body["title"]:
            return []
        return [{"song_code": w.get("mlcSongCode") or "", "iswc": w.get("iswc") or "",
                 "title": w.get("workTitle") or "",
                 "writers": [self._writer(x) for x in w.get("writers") or []]}
                for w in self._call("/search/songcode", body)]

    def get_works(self, song_codes):
        codes = [c for c in dict.fromkeys(song_codes) if c]
        if not codes:
            return []
        return [self._work_fields(w) for w in self._call("/works", [{"mlcsongCode": c} for c in codes])]

    @staticmethod
    def _writer(w):
        name = " ".join(x for x in (w.get("writerFirstName"), w.get("writerLastName")) if x)
        return {"name": name, "ipi": w.get("writerIPI") or "", "role": w.get("writerRoleCode") or ""}

    @classmethod
    def _work_fields(cls, w):
        publishers = []
        for p in w.get("publishers") or []:
            try:
                share = float(p.get("collectionShare") or 0)
            except (TypeError, ValueError):
                share = 0.0
            publishers.append({
                "name": p.get("publisherName") or "", "ipi": p.get("publisherIpiNumber") or "",
                "role": p.get("publisherRoleCode") or "", "share": share,
                "mlc_number": p.get("mlcPublisherNumber") or "",
                "administrators": [a.get("publisherName") for a in p.get("administrators") or []
                                   if a.get("publisherName")]})
        return {"song_code": w.get("mlcSongCode") or "", "iswc": w.get("iswc") or "",
                "title": w.get("primaryTitle") or "", "artists": w.get("artists") or "",
                "writers": [cls._writer(x) for x in w.get("writers") or []],
                "publishers": publishers,
                "share_total": round(sum(p["share"] for p in publishers), 2)}

    # -- the capability --
    def lookup(self, isrc=None, title=None, artist=None):
        """Recordings and the works behind them, for a page to show."""
        recordings = self.find_recordings(isrc=isrc, title=title, artist=artist)
        works = self.get_works([r["song_code"] for r in recordings])
        return {"recordings": recordings, "works": works}

    def get_rights_evidence(self, isrc=None, title=None, artist=None):
        isrc = (isrc or "").strip()
        found = self.lookup(isrc=isrc, title=title, artist=artist)
        if not found["works"]:
            if not isrc:
                return []              # a title alone is not a question The MLC answers
            return [{"source_type": "work_registry", "source_label": "The MLC public search",
                     "source_url": self.portal_search, "work_match": False,
                     "writers_complete": False, "publisher_detected": False,
                     "shares_complete": False, "recording_linked": False,
                     "confidence": 0.8, "iswc": "", "song_code": "",
                     "excerpt": "No work at The MLC is linked to ISRC %s" % isrc.upper()}]
        out = []
        for w in found["works"]:
            writers = w["writers"]
            out.append({
                "source_type": "work_registry", "source_label": "The MLC public search",
                "source_url": self.portal_search,
                "work_match": True,
                "recording_linked": bool(isrc),
                "writers_complete": bool(writers) and all(x["ipi"] for x in writers),
                "publisher_detected": bool(w["publishers"]),
                "shares_complete": bool(w["publishers"]) and abs(w["share_total"] - 100.0) <= 0.5,
                "confidence": 0.9 if isrc else 0.7,
                "iswc": w["iswc"], "song_code": w["song_code"],
                "writers": writers, "publishers": w["publishers"], "share_total": w["share_total"],
                "excerpt": "MLC song code %s%s: %d writer%s, %d publisher%s, collection shares total %g%%" % (
                    w["song_code"], (" (ISWC %s)" % w["iswc"]) if w["iswc"] else "",
                    len(writers), "" if len(writers) == 1 else "s",
                    len(w["publishers"]), "" if len(w["publishers"]) == 1 else "s",
                    w["share_total"]),
            })
        return out


class SoundExchangeAdapter(_EnvProvider):
    key = "soundexchange"
    label = "SoundExchange"
    env_flag = "SOUNDEXCHANGE_ENABLED"
    env_keys = ("SOUNDEXCHANGE_API_KEY",)
    capabilities = (CAP_RIGHTS,)


class SpotifyMetadataAdapter(_EnvProvider):
    key = "spotify_metadata"
    label = "Spotify metadata"
    env_flag = "SPOTIFY_METADATA_ENABLED"
    env_keys = ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")
    capabilities = (CAP_ARTIST, CAP_RELEASES)


class PublicWebResearchAdapter(_EnvProvider):
    key = "web_research"
    label = "Public web research"
    env_flag = "WEB_ENRICHMENT_ENABLED"
    env_keys = ()
    capabilities = (CAP_CONTACTS, CAP_LABEL, CAP_DISTRIBUTOR)

    def configured(self):
        return _flag(self.env_flag)


class InternalStreetBankerAdapter(_EnvProvider):
    key = "internal"
    label = "Street Banker internal"
    env_flag = "INTERNAL_REVENUE_ENABLED"
    env_keys = ()
    capabilities = (CAP_DISTRIBUTOR, CAP_RIGHTS)

    def configured(self):
        return _flag(self.env_flag)


# --- mock provider ----------------------------------------------------------

_GENRES = ["Alternative", "Indie Rock", "Hip-Hop", "R&B", "Pop", "Americana",
           "Synthwave", "Latin", "Punk", "Soul"]
_CITIES = [
    ("Atlanta", "GA", "US"), ("Charlotte", "NC", "US"), ("Nashville", "TN", "US"),
    ("Austin", "TX", "US"), ("Seattle", "WA", "US"), ("Portland", "OR", "US"),
    ("Chicago", "IL", "US"), ("Brooklyn", "NY", "US"), ("Los Angeles", "CA", "US"),
    ("Miami", "FL", "US"), ("Denver", "CO", "US"), ("Detroit", "MI", "US"),
]
# Fictional on purpose. Demo mode must never imply a real company's business.
_DISTRIBUTORS = [
    ("Ridgeline Digital", "DIY / Self-Service"),
    ("Foxglove Distribution", "Independent Distributor"),
    ("Northwind Selective", "Selective Indie Services"),
    ("Pelham Row Records", "Independent Label"),
    ("Meridian Supply Co.", "Enterprise Distribution"),
    ("Continental Sound Group", "Major-Affiliated Distribution"),
]
_MGMT = ["Hollow Pine Management", "Rivet & Co.", "Quarter Note Partners",
         "Aldridge Artist Group", "Tin Roof Management"]
_AGENCIES = ["Broadstone Booking", "Cardinal Live", "Fieldhouse Agency"]
_FIRST = ["Marisol", "Devon", "Ivy", "Caleb", "Nadia", "Theo", "Junia", "Rafa",
          "Sloane", "Emory", "Priya", "Kofi", "Lena", "Silas", "Marguerite"]
_LAST = ["Vance", "Okonkwo", "Reyes", "Whitfield", "Barlow", "Nakamura",
         "Delacroix", "Ferraro", "Mbeki", "Sandoval", "Kettering", "Rowe"]


def _rng(*parts):
    """Deterministic RNG: the same mock artist looks the same every run, so
    tests and screenshots are stable."""
    seed = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return random.Random(int(seed[:16], 16))


class MockMusicIntelligenceAdapter(MusicIntelligenceProvider):
    """A believable, entirely fictional universe.

    Deterministic from the artist id, so Breaking Now is stable between
    requests and a test can assert on a specific artist. Every name here is
    invented; nothing maps to a real person or company.
    """

    key = "mock"
    label = "Demo data (no credentials)"
    capabilities = ALL_CAPABILITIES
    cost_per_request = 0.0

    def __init__(self, count=25):
        self.count = count

    def configured(self):
        return True

    def health_check(self):
        return {"provider": self.key, "configured": True, "ok": True,
                "detail": "demo universe of %d artists" % self.count,
                "capabilities": list(self.capabilities)}

    # -- identity
    def _artist_ids(self):
        return ["mock-a%02d" % i for i in range(1, self.count + 1)]

    def search_artists(self, query, limit=20):
        q = (query or "").strip().lower()
        out = []
        for aid in self._artist_ids():
            a = self.get_artist(aid)
            if not q or q in a["name"].lower() or q in a["genre"].lower():
                out.append(a)
            if len(out) >= limit:
                break
        return out

    def get_artist(self, provider_artist_id):
        r = _rng("artist", provider_artist_id)
        city, state, country = r.choice(_CITIES)
        listeners = int(r.choice([1, 1, 1, 2, 5, 12]) * r.randint(3000, 90000))
        return {
            "provider_artist_id": provider_artist_id,
            "name": "%s %s" % (r.choice(_FIRST), r.choice(_LAST)),
            "genre": r.choice(_GENRES),
            "country": country,
            "city": city,
            "state": state,
            "career_stage": ("Emerging" if listeners < 50000 else
                             "Developing" if listeners < 250000 else "Established"),
            "monthly_listeners": listeners,
            "image_url": "",
            "website": "",
            "socials": {"instagram": "", "tiktok": "", "youtube": ""},
        }

    # -- metrics
    def get_artist_metrics(self, provider_artist_id, start, end):
        """Daily listener/follower series. Some artists are deliberately
        accelerating so the discovery boards have something real to find."""
        r = _rng("metrics", provider_artist_id)
        base = self.get_artist(provider_artist_id)["monthly_listeners"]
        # A believable market is mostly ordinary. If every artist were a
        # three-period accelerator the discovery boards would be meaningless
        # and the scoring would look broken - the product exists to separate
        # real movement from noise, so the demo universe has to contain noise.
        shape = r.choices(
            ["flat", "drifting", "accelerating", "spike", "declining", "recovering"],
            weights=[26, 26, 16, 12, 14, 6])[0]
        # each artist has its own intensity, so two accelerators do not land on
        # the same number
        heat = r.uniform(0.25, 1.6)
        days = (end - start).days + 1
        out = []
        value = base * r.uniform(0.72, 0.95)
        spike_at = r.uniform(0.45, 0.9)
        follower_ratio = r.uniform(0.06, 0.34)
        for i in range(days):
            d = start + timedelta(days=i)
            t = i / max(1, days - 1)
            noise = r.uniform(-0.0035, 0.0035)
            if shape == "accelerating":
                growth = 1.0 + (0.002 + 0.010 * t) * heat + noise
            elif shape == "drifting":
                growth = 1.0 + 0.0012 * heat + noise
            elif shape == "spike":
                growth = (1.0 + 0.11 * heat) if abs(t - spike_at) < 0.03 else 1.0 + noise
            elif shape == "declining":
                growth = 1.0 - 0.0035 * heat + noise
            elif shape == "recovering":
                growth = (1.0 - 0.004 * heat + noise) if t < 0.55 else (1.0 + 0.006 * heat + noise)
            else:
                growth = 1.0 + noise
            value = max(50.0, value * growth)
            out.append({"date": d.isoformat(), "metric": "spotify_monthly_listeners",
                        "value": round(value)})
            # followers lag listeners, and on a spike they barely move at all -
            # which is exactly the divergence the anomaly check looks for
            lag = 0.25 if shape == "spike" else 1.0
            out.append({"date": d.isoformat(), "metric": "spotify_followers",
                        "value": round(value * follower_ratio * (1 - (1 - lag) * t))})
        return out

    def get_artist_cities(self, provider_artist_id, start, end):
        r = _rng("cities", provider_artist_id)
        picks = r.sample(_CITIES, r.randint(3, 6))
        out = []
        for city, state, country in picks:
            out.append({"city": city, "region": state, "country": country,
                        "listeners": r.randint(400, 40000),
                        "change_28d_pct": round(r.uniform(-12, 68), 1)})
        return out

    def get_playlist_activity(self, provider_artist_id, start, end):
        r = _rng("playlists", provider_artist_id)
        n = r.randint(2, 7)
        out = []
        for i in range(n):
            out.append({"playlist_name": "Demo Playlist %d" % (i + 1),
                        "editorial": r.random() < 0.35,
                        "followers": r.randint(2000, 900000),
                        "added_on": (end - timedelta(days=r.randint(1, 120))).isoformat(),
                        "estimated_streams": r.randint(500, 250000)})
        return out

    def get_social_activity(self, provider_artist_id, start, end):
        r = _rng("social", provider_artist_id)
        out = []
        for platform in ("tiktok", "instagram", "youtube"):
            out.append({"platform": platform,
                        "followers": r.randint(500, 400000),
                        "change_28d_pct": round(r.uniform(-6, 90), 1)})
        return out

    def get_events(self, provider_artist_id):
        r = _rng("events", provider_artist_id)
        out = []
        for i in range(r.randint(0, 5)):
            city, state, country = r.choice(_CITIES)
            out.append({"date": (date.today() + timedelta(days=r.randint(5, 200))).isoformat(),
                        "city": city, "region": state, "country": country,
                        "venue": "The %s Room" % r.choice(["Ivy", "Copper", "Lantern", "Foundry"])})
        return out

    # -- releases and business evidence
    def get_artist_releases(self, provider_artist_id):
        r = _rng("releases", provider_artist_id)
        dist_name, dist_class = r.choice(_DISTRIBUTORS)
        out = []
        for i in range(r.randint(3, 9)):
            rel_date = date.today() - timedelta(days=r.randint(10, 1500))
            # most artists are consistent; some have a split catalogue
            if r.random() < 0.18:
                d_name, d_class = r.choice(_DISTRIBUTORS)
            else:
                d_name, d_class = dist_name, dist_class
            out.append({
                "provider_release_id": "%s-r%d" % (provider_artist_id, i),
                "title": "%s %s" % (r.choice(["Night", "Paper", "Golden", "Static",
                                              "Cardinal", "Slow", "Riverbed"]),
                                    r.choice(["Hours", "Lines", "Weather", "Signal",
                                              "Machine", "Season", "Talk"])),
                "release_type": r.choice(["Single", "Single", "Single", "EP", "Album"]),
                "release_date": rel_date.isoformat(),
                "upc": "".join(str(r.randint(0, 9)) for _ in range(12)),
                "label_text": d_name if d_class != "DIY / Self-Service" else "",
                "distributor_name": d_name,
                "distributor_class": d_class,
                "copyright_line": "(C) %d %s" % (rel_date.year, d_name),
                "track_count": r.randint(1, 11),
            })
        out.sort(key=lambda x: x["release_date"], reverse=True)
        return out

    def get_distributor_evidence(self, provider_release_id):
        r = _rng("dist", provider_release_id)
        name, cls = r.choice(_DISTRIBUTORS)
        return [{
            "distributor_name": name,
            "classification": cls,
            "source_type": "release_metadata",
            "source_label": "Demo catalogue metadata",
            "source_url": "",
            "excerpt": "℗ %s" % name,
            "confidence": round(r.uniform(0.72, 0.96), 2),
            "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }]

    def get_label_evidence(self, provider_release_id):
        r = _rng("label", provider_release_id)
        name, cls = r.choice(_DISTRIBUTORS)
        return [{"label_name": name, "classification": cls,
                 "source_type": "release_metadata",
                 "source_label": "Demo catalogue metadata",
                 "source_url": "", "excerpt": "© %s" % name,
                 "confidence": round(r.uniform(0.6, 0.95), 2),
                 "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}]

    def get_contact_evidence(self, provider_artist_id):
        """Fictional public professional footprint. Roles and sources only -
        never a personal address or private number."""
        r = _rng("contacts", provider_artist_id)
        out = []
        if r.random() < 0.62:
            person = "%s %s" % (r.choice(_FIRST), r.choice(_LAST))
            company = r.choice(_MGMT)
            out.append({"role": "Manager", "person_name": person, "company_name": company,
                        "email": "management@%s.example" % company.split()[0].lower(),
                        "phone": "", "source_type": "official_site",
                        "source_label": "Demo artist site — Contact",
                        "source_url": "", "excerpt": "Management: %s, %s" % (person, company),
                        "confidence": round(r.uniform(0.78, 0.97), 2)})
        if r.random() < 0.44:
            company = r.choice(_AGENCIES)
            out.append({"role": "Booking Agent",
                        "person_name": "%s %s" % (r.choice(_FIRST), r.choice(_LAST)),
                        "company_name": company,
                        "email": "booking@%s.example" % company.split()[0].lower(),
                        "phone": "", "source_type": "agency_roster",
                        "source_label": "Demo agency roster",
                        "source_url": "", "excerpt": "Roster listing",
                        "confidence": round(r.uniform(0.7, 0.93), 2)})
        if r.random() < 0.3:
            out.append({"role": "Publicist",
                        "person_name": "%s %s" % (r.choice(_FIRST), r.choice(_LAST)),
                        "company_name": "Marlow Press",
                        "email": "press@marlow.example", "phone": "",
                        "source_type": "press_release",
                        "source_label": "Demo press release",
                        "source_url": "", "excerpt": "For press enquiries",
                        "confidence": round(r.uniform(0.55, 0.8), 2)})
        return out

    def get_rights_evidence(self, isrc=None, title=None, artist=None):
        r = _rng("rights", isrc or title or artist or "x")
        work_match = r.random() < 0.55
        return [{
            "source_type": "work_registry",
            "source_label": "Demo work registry",
            "source_url": "",
            "work_match": work_match,
            "writers_complete": work_match and r.random() < 0.7,
            "publisher_detected": work_match and r.random() < 0.65,
            "shares_complete": work_match and r.random() < 0.6,
            "recording_linked": r.random() < 0.6,
            "confidence": round(r.uniform(0.5, 0.95), 2),
            "excerpt": "Demo registry lookup",
        }]


# --- registry ---------------------------------------------------------------

# YouTubeAdapter sits at the END on purpose: Soundcharts already claims
# CAP_SOCIAL and is preferred where both are configured, so adding this
# one changes which provider serves nothing that was already served.
_REAL_ADAPTERS = (BandsintownAdapter, TourDatesAdapter, SoundchartsAdapter, ChartmetricAdapter,
                  MusicBrainzAdapter, MLCAdapter, SoundExchangeAdapter, SpotifyMetadataAdapter,
                  PublicWebResearchAdapter, InternalStreetBankerAdapter, YouTubeAdapter)


class ProviderRegistry(object):
    """Chooses a provider per capability.

    Preference order is explicit and inspectable in the admin screen. The
    mock is always last, so the moment a real provider is configured it
    takes over - and if it later fails, Signal falls back rather than
    showing an empty product.
    """

    def __init__(self, adapters=None, mock=None):
        self.mock = mock or MockMusicIntelligenceAdapter()
        self.adapters = list(adapters) if adapters is not None else [cls() for cls in _REAL_ADAPTERS]

    def all_providers(self):
        return list(self.adapters) + [self.mock]

    def configured_providers(self):
        return [p for p in self.all_providers() if p.configured()]

    def for_capability(self, capability):
        """Preferred provider for a capability.

        The mock answers only while NOTHING real is configured. The moment a
        real provider exists, a capability nobody real covers returns None,
        and the caller shows "not measured" - because a real artist with
        invented listener numbers beside their real name is the fabrication
        this product refuses everywhere else. Demo mode is all-or-nothing:
        the viewer's own TourDatesAdapter counts like any other real source.
        """
        for p in self.adapters:
            if p.supports(capability) and p.configured():
                return p
        if self.is_demo():
            return self.mock if self.mock.supports(capability) else None
        return None

    def is_demo(self):
        """True when no real provider is configured, so the mock answers -
        and the UI must say so. Whether the STORED universe is fictional is
        a separate question the shell asks the store (seeded_by)."""
        return not any(p.configured() for p in self.adapters)

    def health(self):
        return [p.health_check() for p in self.all_providers()]


_mlc = None


def mlc_adapter():
    """One MLC adapter for the process, so its token is exchanged once and
    reused by every page that asks. Tests swap the function."""
    global _mlc
    if _mlc is None:
        _mlc = MLCAdapter()
    return _mlc


_registry = None


def registry():
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def reset_registry(new=None):
    """Tests swap the registry; production never calls this."""
    global _registry
    _registry = new
    return _registry

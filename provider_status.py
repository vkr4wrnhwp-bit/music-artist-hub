"""Providers: is every outside service Street Banker depends on working
right now? (owner, 2026-09-23: "build the providers status page").

Two separate questions, answered separately, because they disagree exactly
when it matters:

  configured - are the keys this service needs present? Read from the
               environment by NAME only; a value never leaves the server.
  answering  - did the service answer one real, read-only question just
               now? A key can be revoked or a plan lapse without a single
               variable changing.

A check result is one of three, never two: True (it answered), False (it
was asked and refused, failed or timed out - in its own words), or None
(nothing was asked: not configured, switched off by an owner ruling, or no
safe check exists). "We did not ask" and "we asked and it failed" are
different answers and the page must not conflate them (the Signal
adapters' probe() rule, reused here).

Checks run only when the owner presses a button, one at a time or all the
free ones together; nothing here calls out on a page view. A check that
spends money or a scarce quota, or writes anything, is marked with its cost
and is never part of "Check all". Every check has a hard time limit, and
every word shown is scrubbed of the secret values themselves before it is
stored or rendered.

WHERE EACH CHECK COMES FROM. Every check goes through the app's own
adapter for that service - the same headers, host and parsing the product
uses - but BELOW any cache, so "working" means it answered just now, not
that an answer from six hours ago is still on file. Where an adapter keeps
a shared "last refusal" (Eventbrite, Ticketmaster, Google), the check calls
the adapter's one transport seam and reads the error itself, so a check
cannot wipe or overwrite the refusal a real sync is about to report. The
source of truth for every service, its variables, the cheapest safe
question and its traps is the 2026-09-23 providers inventory.
"""

import json
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

CHECK_TIMEOUT_S = 12          # a check that takes longer is reported as timed out
KV_PREFIX = "provider_status:"
BACKUP_STALE_H = 26           # the nightly backup, flagged when older than this

# The fixed questions. Real, public, and the same every time, so an answer
# means the service works rather than that some data happened to exist.
KNOWN_ISRC = "USUM71703861"
KNOWN_TRACK_URL = "https://open.spotify.com/track/7KXjTSCq5nL1LoYtL7XAwS"
KNOWN_CHANNEL = "UC_x5XG1OV2P6uZZ5FSM9Ttw"          # a public YouTube channel id
KNOWN_ROOM = "Ryman Auditorium, Nashville"
KNOWN_ADDRESS = "116 5th Ave N, Nashville, TN"
NASHVILLE = (36.1627, -86.7816)
MEMPHIS = (35.1495, -90.0490)


# ---- small helpers -------------------------------------------------------------

def _env(name):
    return (os.environ.get(name) or "").strip()


def _truthy(value):
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _sandbox():
    try:
        import sandbox
        return sandbox.active()
    except Exception:
        return False


def _ok(detail):
    return {"ok": True, "detail": detail}


def _fail(detail):
    return {"ok": False, "detail": detail}


def _not_asked(detail):
    return {"ok": None, "detail": detail}


def _plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def _from_doc(doc):
    """The message field of whichever error shape a vendor uses."""
    if isinstance(doc, list):
        doc = doc[0] if doc and isinstance(doc[0], dict) else {}
    if not isinstance(doc, dict):
        return ""
    err = doc.get("error")
    if isinstance(err, dict):                       # Google, Deezer
        return str(err.get("message") or err.get("status") or err.get("code") or "")
    fault = doc.get("fault")
    if isinstance(fault, dict):                     # Ticketmaster's gateway
        return str(fault.get("faultstring") or "")
    errors = doc.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        first = errors[0]
        return str(first.get("message") or first.get("detail") or first.get("code") or "")
    for key in ("error_description", "errorDescription", "message", "detail", "error",
                "msg", "name", "code"):
        value = doc.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict) and value.get("message"):
            return str(value["message"])
    return ""


def _words(raw):
    """What a vendor said in an error body, in its own words - whole. The
    only cut is scrub()'s, made after the secrets are out: a cut made first
    can split a key the vendor quoted, and the whole-value match then no
    longer finds what is left of it (providers review, 2026-09-23)."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    if isinstance(raw, (dict, list)):
        return _from_doc(raw)
    text = str(raw or "").strip()
    if text[:1] in ("{", "["):
        try:
            return _from_doc(json.loads(text))
        except ValueError:
            pass
    text = re.sub(r"<[^>]+>", " ", text)            # an HTML error page
    return " ".join(text.split())


def _is_timeout(exc):
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return True
    if "timeout" in type(exc).__name__.lower():     # httpx.ReadTimeout and kin
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(exc).lower()


# The public lookups carry no key, so a 401 there is not about ours.
_KEYLESS = ("Apple", "Deezer", "Odesli", "Google News")


def _refused(service, status, words=""):
    """An HTTP refusal, said the way an owner can act on."""
    words = (words or "").strip()
    tail = (": " + words) if words else "."
    if status in (401, 403) and service in _KEYLESS:
        head = "%s refused the request (HTTP %d)" % (service, status)
    elif status in (401, 403):
        head = "%s refused the credentials (HTTP %d)" % (service, status)
    elif status == 429:
        head = "%s is rate-limiting this app (HTTP 429)" % service
    elif isinstance(status, int) and status >= 500:
        head = "%s had a server error (HTTP %d)" % (service, status)
    else:
        head = "%s answered HTTP %s" % (service, status)
    return _fail(head + tail)


def _malformed(service):
    return _fail("%s answered, but not with anything this app can read." % service)


def _from_exception(service, exc):
    """Whatever one urllib call raised, turned into the three-way answer."""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            raw = exc.read() or b""
        except Exception:
            raw = b""
        return _refused(service, exc.code, _words(raw) or str(exc.reason or ""))
    if isinstance(exc, ValueError):                 # JSON that is not JSON
        return _malformed(service)
    if _is_timeout(exc):
        return _fail("%s did not answer in time." % service)
    reason = getattr(exc, "reason", None) or exc
    return _fail("%s could not be reached: %s" % (service, reason))


def _json_doc(body, service):
    """(doc, None) or (None, a failing result) for one response body."""
    try:
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        doc = json.loads(body)
    except (ValueError, TypeError):
        return None, _malformed(service)
    if not isinstance(doc, (dict, list)):
        return None, _malformed(service)
    return doc, None


def _from_provider_error(service, exc, fallback=None):
    """An adapter's ProviderError, read by what caused it: a body that was
    not JSON is unreadable, a timeout is no answer, an HTTP refusal whose
    status the adapter's words dropped is read from the response itself.
    Otherwise the adapter's own words stand."""
    cause = exc.__cause__ or exc.__context__
    text = fallback(str(exc)) if fallback else str(exc)
    if isinstance(cause, urllib.error.HTTPError) and str(cause.code) not in text:
        return _from_exception(service, cause)
    if isinstance(cause, ValueError):
        return _malformed(service)
    if cause is not None and _is_timeout(cause):
        return _fail("%s did not answer in time." % service)
    return _fail(text)


# ---- the checks: music data and rights ------------------------------------------

def _check_mlc():
    """Sign-in alone is not proof (2026-09-08: sign-in worked while search
    answered 401), so this searches by a known ISRC through the process's
    own adapter. Only a 204, or a 200 that is a list, means it works: the
    product reads any other 200 as "no recording", which here would turn
    an unreadable answer green (providers review, 2026-09-23)."""
    import signal_providers as sp
    adapter = sp.mlc_adapter()
    try:
        status, answer = adapter._call_raw("/search/recordings", {"isrc": KNOWN_ISRC})
    except sp.ProviderError as e:
        return _from_provider_error("The MLC", e)
    if status == 204:
        return _ok("Signed in and searched by ISRC: The MLC answered 204, its word for holding no "
                   "recording for the test ISRC, which is still an answer.")
    if status == 200 and isinstance(answer, list):
        if answer:
            return _ok("Signed in and searched by ISRC: The MLC answered with %s."
                       % _plural(len(answer), "recording"))
        return _ok("Signed in and searched by ISRC: The MLC answered, with an empty list for a "
                   "recording it has registered. The search works; if it keeps matching nothing, "
                   "ask The MLC.")
    if status == 200:
        return _malformed("The MLC")
    return _fail(adapter.refusal(status, answer))


def _registry_adapter(key):
    try:
        import signal_providers as sp
        return next((p for p in sp.registry().all_providers() if getattr(p, "key", "") == key), None)
    except Exception:
        return None


def _check_soundcharts():
    """One artist search below the six-hour cache, through the monthly
    budget: it is counted like any other call and refused, unasked, when
    the month's allowance is spent."""
    import signal_providers as sp
    import soundcharts_budget
    adapter = _registry_adapter("soundcharts")
    if not isinstance(adapter, sp.SoundchartsAdapter):
        adapter = sp.SoundchartsAdapter()
    try:
        body = adapter._fetch_json("/api/v2/artist/search/radiohead", offset=0, limit=1)
    except sp.SoundchartsPaused as e:
        return _not_asked("%s. Nothing was asked." % e)
    except sp.ProviderError as e:
        return _from_provider_error("Soundcharts", e)
    if not isinstance(body, dict) or not (isinstance(body.get("items"), list)
                                          or isinstance(body.get("page"), dict)):
        return _malformed("Soundcharts")
    month = soundcharts_budget.summary()
    return _ok("Answered an artist search. That was 1 paid call: {:,} of this month's {:,} are used."
               .format(month["total"], month["budget"]))


def _soundcharts_late():
    try:
        import soundcharts_budget
        month = soundcharts_budget.summary()
        return ("The call had already left and is counted as 1 paid call: this month's count "
                "stands at {:,} of {:,}. Check that count before pressing again."
                .format(month["total"], month["budget"]))
    except Exception:
        return "The call had already left and may still be counted as 1 paid call."


def _check_songstats():
    """The adapter's own artist search, below its cache, with the answer's
    shape read: probe() calls an unreadable list "no match"."""
    import signal_providers as sp
    try:
        payload = sp.SongstatsAdapter()._get("/artists/search", q="radiohead", limit=1)
    except sp.ProviderError as e:
        return _from_provider_error("Songstats", e)
    found = payload.get("artists", payload.get("results")) if isinstance(payload, dict) else None
    if not isinstance(found, list):
        return _malformed("Songstats")
    return _ok("Answered an artist search (%s). That spent 1 of Songstats' 1,000 calls this month."
               % _plural(len(found), "result"))


def _check_discogs():
    """Discogs' own who-am-I, below the adapter's six-hour cache, through
    the process's one adapter and its pacing, so the check neither spends
    the last call of a nearly-spent window nor lands unspaced beside a
    catalog lookup."""
    import signal_providers as sp
    adapter = sp.discogs_adapter()
    left = adapter._remaining
    if left is not None and left <= adapter.low_water:
        return _not_asked("Discogs' 60-a-minute window is nearly spent (%d left), so nothing was "
                          "asked: the catalog lookups keep it. Try again in a minute." % left)
    adapter._pace()
    try:
        status, headers, body = adapter._send("/oauth/identity", {})
    except sp.ProviderError as e:
        return _from_provider_error("Discogs", e)
    adapter._read_limits(headers)
    if status != 200:
        return _refused("Discogs", status, adapter._message(status, body))
    if not isinstance(body, dict) or not (body.get("username") or body.get("id")):
        return _malformed("Discogs")
    left = (adapter.rate_limit() or {}).get("remaining")
    return _ok("The token works: Discogs knows who it belongs to.%s"
               % ((" %d of 60 calls left this minute." % left) if isinstance(left, int) else ""))


def _check_spotify():
    """The client-credentials grant itself, not the app's 50-minute cached
    token, so a secret revoked in the last hour reads as refused."""
    import spotify_provider as spotify
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    try:
        out = spotify._http("https://accounts.spotify.com/api/token", data=data,
                            headers=spotify._basic_auth_header())
    except Exception as e:
        return _from_exception("Spotify", e)
    if isinstance(out, dict) and out.get("access_token"):
        return _ok("Spotify issued an app token, so the client id and secret work.")
    return _malformed("Spotify")


def _check_youtube():
    """One unit of the day's quota: a channel lookup, never /search. The key
    rides in the URL, so every word is passed through the adapter's redact."""
    import signal_providers as sp
    try:
        body = sp.YouTubeAdapter()._fetch_json("/channels", part="id", id=KNOWN_CHANNEL)
    except sp.ProviderError as e:
        return _from_provider_error("YouTube", e, fallback=sp.YouTubeAdapter.redact)
    if not isinstance(body, dict) or not (str(body.get("kind") or "").startswith("youtube#")
                                          or isinstance(body.get("pageInfo"), dict)
                                          or isinstance(body.get("items"), list)):
        return _malformed("YouTube")
    return _ok("Answered a one-unit channel lookup.")


def _check_acr_console():
    """A read of one bucket. The token can also write, so GET only."""
    import acr_console
    try:
        answer = acr_console._call("GET", acr_console.ACCOUNT_HOST, "/api/buckets",
                                   query={"page": 1, "per_page": 1})
    except acr_console.AcrConsoleError as e:
        if isinstance(e.status, int):
            return _refused("The ACRCloud console", e.status, e.msg)
        if _is_timeout(e):
            return _fail("The ACRCloud console did not answer in time.")
        return _fail("The ACRCloud console could not be reached: %s" % e.msg)
    if not isinstance(answer, dict) or "_raw" in answer or not isinstance(answer.get("data"), list):
        return _malformed("The ACRCloud console")
    return _ok("The console token works: it can read the account's buckets.")


def _check_musicbrainz():
    """Through the registry's own adapter, so the check waits its turn on
    the one-a-second pacing Signal's lookups keep, and with the answer's
    shape read rather than probe()'s "no match"."""
    import signal_providers as sp
    adapter = _registry_adapter("musicbrainz")
    if not isinstance(adapter, sp.MusicBrainzAdapter):
        adapter = sp.MusicBrainzAdapter()
    try:
        data = adapter._get("artist/", query="radiohead", limit=1)
    except sp.ProviderError as e:
        return _from_provider_error("MusicBrainz", e)
    if not isinstance(data, dict) or not isinstance(data.get("artists"), list):
        return _malformed("MusicBrainz")
    return _ok("Answered an artist search (%s), inside their one-a-second rule."
               % _plural(len(data["artists"]), "result"))


# ---- touring and places -----------------------------------------------------------

def _check_eventbrite():
    """The first call a real sync makes, once, through the adapter's seam."""
    import eventbrite_provider as eb
    try:
        body = eb._http(eb.ORGS_URL, {"Authorization": "Bearer %s" % eb._token()})
    except Exception as e:
        return _from_exception("Eventbrite", e)
    doc, bad = _json_doc(body, "Eventbrite")
    if bad:
        return bad
    orgs = doc.get("organizations") if isinstance(doc, dict) else None
    if not isinstance(orgs, list):
        return _malformed("Eventbrite")
    if not orgs:
        return _ok("The token works, but it belongs to no organization, so a ticket sync can match nothing.")
    return _ok("The token works: it reads %s." % _plural(len(orgs), "organization"))


def _gate_ticketmaster():
    import ticketmaster_provider as tm
    if tm.switched_off():
        return ("Off by owner ruling",
                "Off by owner ruling (2026-09-18): Ticketmaster stays off on deployed services until "
                "Ticketmaster confirms a paid product may use the Discovery API. The key is set; "
                "nothing was asked. TICKETMASTER_ENABLED=on switches it back on.")
    return None


def _check_ticketmaster():
    import ticketmaster_provider as tm
    try:
        body = tm._http(tm._url({"classificationName": "music", "size": 1}))
    except Exception as e:
        return _from_exception("Ticketmaster", e)
    doc, bad = _json_doc(body, "Ticketmaster")
    if bad:
        return bad
    if not isinstance(doc, dict) or not ("page" in doc or "_embedded" in doc):
        return _malformed("Ticketmaster")
    return _ok("The key works: Discovery answered an events search. Discovery publishes no "
               "sales counts, so this says nothing about tickets sold.")


def _google_http_error(service, exc):
    try:
        raw = exc.read() or b""
    except Exception:
        raw = b""
    return exc.code, _words(raw) or str(exc.reason or ""), raw


def _check_places():
    """Text search asking for place ids only - never a photo."""
    import venue_photos as vp
    try:
        body, _ct = vp._http(vp.SEARCH_URL, payload={"textQuery": KNOWN_ROOM, "maxResultCount": 1},
                             headers={"X-Goog-Api-Key": vp._key(), "X-Goog-FieldMask": "places.id"})
    except Exception as e:
        return _from_exception("Google Places", e)
    doc, bad = _json_doc(body, "Google Places")
    if bad:
        return bad
    if not isinstance(doc, dict) or doc.get("error"):
        return _malformed("Google Places")
    places = doc.get("places")
    if not isinstance(places, list) or not places:
        # The Ryman is always there: an answer without it is not one to trust.
        return _fail("Google Places answered, but found no place for the test venue (%s), which "
                     "it always has, so the answer cannot be trusted." % KNOWN_ROOM)
    return _ok("Places (New) answered a text search (%s)." % _plural(len(places), "place"))


def _classic_google(service, url, params):
    """Geocoding and Time Zone: a refused key still answers HTTP 200, so the
    body's status is the answer."""
    import venue_geo as vg
    try:
        body, _ct = vg._http(url + "?" + urllib.parse.urlencode(params))
    except Exception as e:
        return _from_exception(service, e)
    doc, bad = _json_doc(body, service)
    if bad:
        return bad
    if not isinstance(doc, dict):
        return _malformed(service)
    status = str(doc.get("status") or "")
    message = str(doc.get("error_message") or "")
    if status in ("OK", "ZERO_RESULTS"):
        return _ok("%s answered (%s), so the key may call it." % (service, status))
    if status == "UNKNOWN_ERROR":
        return _fail("%s answered UNKNOWN_ERROR, Google's word for try again." % service)
    if not status:
        return _malformed(service)
    return _fail("%s refused: %s%s" % (service, status, (" - " + message) if message else ""))


def _check_geocoding():
    import venue_geo as vg
    return _classic_google("Google Geocoding", vg.GEOCODE_URL,
                           {"address": KNOWN_ADDRESS, "key": vg._key()})


def _check_timezone():
    import venue_geo as vg
    return _classic_google("Google Time Zone", vg.TIMEZONE_URL,
                           {"location": "%s,%s" % NASHVILLE, "timestamp": int(time.time()),
                            "key": vg._key()})


def _check_routes():
    """Straight through the transport, never drive(): drive() switches Routes
    off for the worker after a refusal and writes the shared refusal."""
    import venue_geo as vg

    def point(lat_lng):
        return {"location": {"latLng": {"latitude": lat_lng[0], "longitude": lat_lng[1]}}}

    payload = {"origin": point(NASHVILLE), "destination": point(MEMPHIS), "travelMode": "DRIVE"}
    try:
        body, _ct = vg._http(vg.ROUTES_URL, payload=payload,
                             headers={"X-Goog-Api-Key": vg._key(),
                                      "X-Goog-FieldMask": vg.ROUTES_FIELD_MASK})
    except urllib.error.HTTPError as e:
        code, words, raw = _google_http_error("Google Routes", e)
        err = {}
        try:
            err = json.loads(raw.decode("utf-8", "replace")).get("error") or {}
        except Exception:
            pass
        err = err if isinstance(err, dict) else {}
        reasons = {str(d.get("reason") or "") for d in (err.get("details") or []) if isinstance(d, dict)}
        said = words or "no message"
        # Asked, and Google named a known state of the project or the key.
        # It gets its own label: "not asked" would be untrue after a call.
        if code == 403 and "API_KEY_SERVICE_BLOCKED" in reasons:
            return {"ok": None, "label": "Blocked by the key",
                    "detail": "Google refused Routes because the API key's restrictions do not "
                              "allow the Routes API (API_KEY_SERVICE_BLOCKED: %s). Add Routes to "
                              "the key's allowed APIs in the Cloud console; until then the route "
                              "page draws straight lines." % said}
        if code == 403 and ("SERVICE_DISABLED" in reasons or "has not been used in project" in said
                            or "is disabled" in said.lower()):
            return {"ok": None, "label": "Not enabled",
                    "detail": "Not enabled on this Google project: Google refused the Routes API "
                              "(%s). The route page draws straight lines until Routes is switched "
                              "on in the Cloud console." % said}
        return _refused("Google Routes", code, words)
    except Exception as e:
        return _from_exception("Google Routes", e)
    doc, bad = _json_doc(body, "Google Routes")
    if bad:
        return bad
    if not isinstance(doc, dict) or not isinstance(doc.get("routes"), list) or not doc["routes"]:
        return _malformed("Google Routes")
    return _ok("Routes answered: drives between dates are measured, not drawn as straight lines.")


# ---- money, shop and mail ------------------------------------------------------------

def _stripe_secret_state():
    """How the app verifies a Stripe delivery: True (STRIPE_WEBHOOK_SECRET
    is set), "app" (the per-mode secret the in-app setup keeps), "legacy"
    (only the secret kept from before per-mode setup), or False. The route
    accepts a delivery with any of them (stripe_provider.webhook_accepts)."""
    try:
        import stripe_provider
        if _env("STRIPE_WEBHOOK_SECRET"):
            return True
        if stripe_provider.webhook_configured():
            return "app"
        return "legacy" if stripe_provider.webhook_accepts() else False
    except Exception:
        return bool(_env("STRIPE_WEBHOOK_SECRET"))


def _this_base(given=None):
    """This deployment's own address: the one the owner pressed the button
    on (what Billing's one-click setup registers), else PUBLIC_BASE_URL."""
    if given:
        return given.rstrip("/")
    if _env("PUBLIC_BASE_URL"):
        return _env("PUBLIC_BASE_URL").rstrip("/")
    app_module = sys.modules.get("app")
    return str(getattr(app_module, "PUBLIC_BASE_URL", "") or "").rstrip("/")


def _host_of(url):
    try:
        return (urllib.parse.urlsplit(str(url or "")).netloc or "").lower()
    except ValueError:
        return ""


def _check_stripe(base_url=None):
    """A read of the webhook endpoints, through the GET seam only. Never
    setup_webhook_endpoint(): after the same read it POSTs changes.

    Only an endpoint on THIS deployment's host counts - live and staging
    can share one test-mode key, and the other's endpoint delivers nothing
    here. Every state in which no delivery lands (no endpoint for this
    host, one Stripe has disabled, or one whose secret the app does not
    hold) is failing, alike (providers review, 2026-09-23)."""
    import stripe_provider as stripe
    mode = stripe.mode()
    try:
        doc = stripe._http_get("/v1/webhook_endpoints?limit=100")
    except urllib.error.HTTPError as e:
        if e.code != 403:
            return _from_exception("Stripe", e)
        # A restricted key without webhook permission still takes money:
        # the smallest read tells a working key from a dead one.
        try:
            stripe._http_get("/v1/balance")
        except Exception as again:
            return _from_exception("Stripe", again)
        return _ok("The %s-mode key works (it read the balance). It is a restricted key that may "
                   "not read webhook endpoints, so the webhook could not be checked." % mode)
    except Exception as e:
        return _from_exception("Stripe", e)
    endpoints = doc.get("data") if isinstance(doc, dict) else None
    if not isinstance(endpoints, list):
        return _malformed("Stripe")
    base = _this_base(base_url)
    host = _host_of(base)
    hooks = [ep for ep in endpoints if isinstance(ep, dict)
             and urllib.parse.urlsplit(str(ep.get("url") or "")).path.rstrip("/") == "/webhooks/stripe"]
    ours = [ep for ep in hooks if host and _host_of(ep.get("url")) == host]
    others = sorted({_host_of(ep.get("url")) for ep in hooks} - {host, ""})
    where = "%s/webhooks/stripe" % (base or "this app")
    head = "The %s-mode key works." % mode
    lost = "plan changes, renewals and refunds do not reach the app"
    if not ours:
        return _fail("%s But no webhook endpoint in this mode points at %s, so %s; a checkout is "
                     "still claimed when the buyer comes back to the app.%s Billing's one-click "
                     "webhook setup makes one."
                     % (head, where, lost, (" Other endpoints on the account point at %s."
                                            % ", ".join(others)) if others else ""))
    ep = next((e for e in ours if e.get("status") == "enabled"), ours[0])
    if ep.get("status") != "enabled":
        return _fail("%s But Stripe has the webhook endpoint for %s %s, so %s. Billing's one-click "
                     "webhook setup switches it back on."
                     % (head, where, ep.get("status") or "switched off", lost))
    secret = _stripe_secret_state()
    if not secret:
        return _fail("%s The webhook endpoint for %s is enabled, but the app holds no signing "
                     "secret for it, so every delivery is refused and %s. Billing's one-click "
                     "webhook setup makes a new endpoint and keeps its secret." % (head, where, lost))
    events = set(ep.get("enabled_events") or [])
    current = "*" in events or set(stripe.WEBHOOK_EVENTS) <= events
    legacy = (" The app holds only the signing secret kept from before per-mode setup, which "
              "verifies a delivery only if it belongs to this endpoint; Billing's one-click "
              "setup replaces it." if secret == "legacy" else "")
    return _ok("%s The webhook endpoint for %s is enabled%s.%s" % (
        head, where, "" if current else ", but it is missing events the app listens for", legacy))


def _storefront_token_state():
    """Read without ever calling shopify_buy.token(): with no token kept and
    the Admin credentials set, that call MINTS one, which writes to the
    store."""
    try:
        import db
        import shopify_buy
        if shopify_buy.env_token():
            return True
        return "app" if (db.get_kv(shopify_buy.STOREFRONT_KEY) or "") else False
    except Exception:
        return bool(_env("SHOPIFY_STOREFRONT_TOKEN"))


def _storefront_pending(miss):
    """(label, detail) when all that is missing is a Storefront token the
    app makes for itself on the first Apparel visit (shopify_buy.
    minted_token) - not something the owner has to set. Read, never
    minted: a mint writes to the store."""
    if list(miss) != ["SHOPIFY_STOREFRONT_TOKEN"]:
        return None
    try:
        import shopify_buy
        import shopify_customers
        if not shopify_customers.uses_grant():
            return None
        err = shopify_buy.mint_error()
    except Exception:
        return None
    detail = ("No Storefront token yet: the app mints one with its Admin credentials on the "
              "first Apparel visit (or set SHOPIFY_STOREFRONT_TOKEN). Nothing was asked; a mint "
              "from here would write to the store.")
    if err:
        detail += (" The last mint was refused (%s%s): the app's version needs the "
                   "unauthenticated_* scopes." % (err.get("status") or "no answer",
                                                   (": " + err["why"]) if err.get("why") else ""))
    return ("Not minted yet", detail)


def _check_shopify_buy():
    """The embed's own query, with the saved token, past the ten-minute cache."""
    import shopify_buy
    out = shopify_buy.check(fresh=True)
    if out is None:
        return _not_asked("Not configured.")
    if not out.get("ok"):
        return _fail(out.get("error") or "Shopify refused the check.")
    detail = "Shopify answered: the Storefront token reads the store and the collection."
    if out.get("error"):                              # the empty-collection warning
        detail += " " + out["error"]
    return _ok(detail)


def _grant_failure(err):
    """Why the client credentials grant gave no token, by what it answered:
    only a refusal is about the credentials (providers review, 2026-09-23:
    an outage read as "refused" invites rotating a working secret)."""
    status = err.get("status")
    why = str(err.get("why") or "").strip()
    said = (": " + why) if why else ""
    if status in (401, 403) or "invalid_client" in why.lower():
        return _fail("Shopify refused the app's credentials: the client credentials grant "
                     "answered %s%s." % (status or "a refusal", said))
    if status == 429:
        return _fail("Shopify is rate-limiting the token grant (HTTP 429)%s. The credentials were "
                     "not judged; try again in a minute." % said)
    if isinstance(status, int) and status >= 500:
        return _fail("Shopify's token grant had a server error (HTTP %d)%s. That is Shopify's "
                     "side, not the credentials." % (status, said))
    if not status:
        return _fail("Shopify's token grant could not be reached or did not answer in time%s. The "
                     "credentials were not judged." % said)
    return _fail("Shopify's token grant answered HTTP %s%s." % (status, said))


def _check_shopify_admin():
    """{ shop { name } } with the Admin token: about one point of Shopify's
    cost bucket. The grant is asked only when the kept 24-hour token has
    lapsed. Never the Storefront mint, and never forget_grant(), which would
    drop the Buy Buttons' token with it."""
    import shopify_customers as sc
    admin = sc.token()
    if not admin:
        return _grant_failure(sc.grant_error() or {})
    url = "https://%s/admin/api/%s/graphql.json" % (sc.domain(), sc.API_VERSION)
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": admin,
               "User-Agent": "StreetBanker/1.0"}
    try:
        answer = sc._post(url, headers, {"query": "{ shop { name } }"})
    except sc.ShopifyError as e:
        text = str(e)
        if _is_timeout(e):
            return _fail("Shopify did not answer in time.")
        return _fail(text)
    if not isinstance(answer, dict):
        return _malformed("Shopify")
    if answer.get("errors"):
        return _fail("Shopify: %s" % _words(answer))
    shop = ((answer.get("data") or {}).get("shop") or {}).get("name")
    if not shop:
        return _malformed("Shopify")
    return _ok("The Admin API answered for the store, so a customer import can run.")


def _check_resend():
    """One read of the account's domains - no mail is sent."""
    import email_provider as mail
    data, err = mail._api_get("/domains")
    if err:
        text = str(err)
        if "restricted_api_key" in text:
            return _ok("Resend recognised the key. It is a sending-only key, so it cannot list "
                       "domains; whether the sending domain is verified is not shown here.")
        found = re.search(r"HTTP Error (\d{3})", text)
        if found:
            body = text[text.find("{"):] if "{" in text else text[found.end():]
            return _refused("Resend", int(found.group(1)), _words(body))
        if re.search(r"Expecting value|JSON|Unterminated|Extra data", text):
            return _malformed("Resend")
        if "timed out" in text.lower():
            return _fail("Resend did not answer in time.")
        return _fail("Resend could not be reached: %s" % text)
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return _malformed("Resend")
    if mail.using_shared_test_sender():
        return _fail("Resend answered, but EMAIL_FROM is not set: mail goes from Resend's shared "
                     "test sender, which delivers only to the Resend account owner.")
    sender = mail.sender()
    address = sender[sender.find("<") + 1:sender.rfind(">")] if "<" in sender else sender
    domain = address.rsplit("@", 1)[-1].strip().lower()
    verified = [d for d in rows if isinstance(d, dict)
                and str(d.get("name") or "").lower() == domain and d.get("status") == "verified"]
    if verified:
        return _ok("Resend answered: the domain EMAIL_FROM sends from is verified.")
    return _fail("Resend answered, but the domain EMAIL_FROM sends from is not verified on this "
                 "account (%s listed), so mail from it is refused." % _plural(len(rows), "domain"))


# ---- storage, backup and monitoring ------------------------------------------------------

def _check_r2():
    """Write a few bytes, read them back through a signed link the way RoEx
    does - at both lifetimes the app hands out - and delete them."""
    import blob_store
    try:
        import release_ready
        ttls = (release_ready.SOURCE_URL_TTL_ANALYSIS, release_ready.SOURCE_URL_TTL_TASK)
    except Exception:
        ttls = (3600, 7 * 24 * 3600)
    report = blob_store.round_trip(ttls=ttls)
    verdict = report.get("verdict") or "no verdict"
    tidy = _r2_tidy(report)
    if report.get("ok"):
        return _ok("Wrote a test object, read it back through a signed link and deleted it: %s.%s"
                   % (verdict, tidy))
    return _fail("The R2 round trip failed at the %s step: %s.%s"
                 % (report.get("step") or "read", verdict, tidy))


R2_TEST_PREFIX = "diagnostics/round-trip-"


def _r2_tidy(report):
    """Whether the test object is gone, said only as far as it is known:
    a missing answer after a write was attempted is "not confirmed", not
    "tidy" (providers review, 2026-09-23: a lost reply left one behind)."""
    key = report.get("key") or (R2_TEST_PREFIX + "...")
    cleaned = report.get("cleaned_up")
    if cleaned is True:
        return ""
    if cleaned is False:
        return (" The test object (%s) could not be deleted; it is a few bytes and safe to remove "
                "by hand." % key)
    if report.get("step") == "configured" or (report.get("step") == "put"
                                               and isinstance(report.get("status"), int)
                                               and report["status"] < 500):
        return ""                                     # nothing was stored
    return (" Whether the test object (%s) was deleted is not confirmed; look for keys starting "
            "%s in the bucket." % (key, R2_TEST_PREFIX))


def _r2_late():
    return ("The test write may still be in flight. The round trip deletes its object when it "
            "finishes; if it never does, look for keys starting %s in the bucket." % R2_TEST_PREFIX)


def _local_backup(store):
    """The stored record of the last nightly run - never a new run, which
    zips the whole database and uploads it."""
    raw = store.get_kv("backup_last_run")
    if not raw:
        return _not_asked("No backup run is recorded yet. The Render cron POSTs /backup/run nightly.")
    try:
        last = json.loads(raw)
        at = datetime.fromisoformat(str(last.get("at")))
    except Exception:
        return _not_asked("The stored record of the last run could not be read.")
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    hours = (datetime.now(timezone.utc) - at).total_seconds() / 3600.0
    when = at.strftime("%Y-%m-%d %H:%M UTC")
    if not last.get("ok"):
        return _fail("The last run (%s) failed: %s" % (when, last.get("detail") or "no reason recorded"))
    if hours > BACKUP_STALE_H:
        return _fail("The last good run was %d hours ago (%s). A nightly run should be under %d "
                     "hours old, so the schedule has stopped." % (hours, when, BACKUP_STALE_H))
    size = last.get("bytes") or 0
    return _ok("The last nightly run (%s) succeeded %d hours ago and uploaded %.1f MB."
               % (when, hours, size / 1e6))


def _local_sentry(store):
    try:
        from flask import current_app
        started = bool(current_app.config.get("SENTRY_ENABLED"))
    except Exception:
        started = False
    if started:
        return _not_asked("The DSN is set and the SDK started in this worker. Only an event "
                          "arriving in the Sentry project proves delivery, and sending one uses "
                          "Sentry quota, so nothing is sent from here.")
    return _fail("The DSN is set, but the SDK did not start in this worker: the sentry-sdk "
                 "package is missing or the DSN is not usable.")


def _local_webhooks(store):
    state = _stripe_secret_state()
    parts = [
        "Stripe: %s" % ({True: "secret set", "app": "secret held by the app (set up in-app)",
                         "legacy": "legacy secret held by the app (from before per-mode setup); "
                                   "Billing's one-click setup replaces it"}
                        .get(state, "no signing secret, so deliveries are refused")),
        "Resend: %s" % ("secret set" if _env("RESEND_WEBHOOK_SECRET") else "no secret"),
        "ElevenLabs: %s" % ("secret set" if _env("ELEVENLABS_WEBHOOK_SECRET") else "no secret"),
    ]
    return _not_asked("Inbound only, so nothing can be asked from here, and a rotated secret still "
                      "reads as set. " + "; ".join(parts) + ".")


# ---- audio tools ------------------------------------------------------------------------

def _check_elevenlabs():
    """The model list: read-only and free. The SDK is given a 10-second
    limit and no retries here; its default would hold the request for
    minutes on a dead vendor."""
    import audio_elevenlabs as el
    client = el._client()
    if client is None:
        return _not_asked("The ElevenLabs SDK could not start a client in this environment, so "
                          "nothing was asked.")
    try:
        models = client.models.list(request_options={"timeout_in_seconds": 10, "max_retries": 0})
    except Exception as e:
        status = getattr(e, "status_code", None)
        if isinstance(status, int):
            return _refused("ElevenLabs", status, _words(getattr(e, "body", "") or ""))
        if _is_timeout(e):
            return _fail("ElevenLabs did not answer in time.")
        if isinstance(e, ValueError):
            return _malformed("ElevenLabs")
        return _fail("%s: %s" % (type(e).__name__, e))      # scrub() makes the only cut
    try:
        n = len(list(models or []))
    except Exception:
        return _malformed("ElevenLabs")
    return _ok("Key accepted: %s visible to this account. Reading the list spends no credits."
               % _plural(n, "model"))


def _check_roex():
    """RoEx's /health through the app's own limiter: no credits."""
    import roex_client as roex
    out = roex.health()
    said = (" RoEx said: %s" % out.roex_message) if out.roex_message else ""
    if out.kind == "ok":
        return _ok("RoEx answered and accepted the key. /health spends no credits, and nothing "
                   "reports how many are left.")
    if out.kind == "busy" and not out.sent:
        return _not_asked("Our own RoEx rate limiter is full, so nothing was sent. Try again in a minute.")
    if out.kind == "not_configured":
        return _not_asked("No RoEx key is set on this server.")
    if out.kind == "busy":
        return _refused("RoEx", out.status if isinstance(out.status, int) else 429, out.roex_message)
    if out.kind == "auth":
        return _fail("RoEx refused the key (HTTP %s).%s" % (out.status, said))
    if out.kind == "unavailable":
        return _fail("RoEx couldn't be reached.")
    if out.kind == "unknown":
        return _fail("RoEx didn't answer in time, or answered with something unreadable.%s" % said)
    if out.kind == "server_error":
        return _refused("RoEx", out.status, out.roex_message)
    return _fail("RoEx answered %s.%s" % (out.status, said))


_CLOUDFLARE_1010 = re.compile(r"(?i)\berror\s*(?:code\s*:?\s*)?1010\b")
_BALANCE_WORDS = ("balance", "credit", "remaining", "minutes", "seconds")


def _balance_like(doc):
    keys = set(doc)
    if isinstance(doc.get("data"), dict):
        keys |= set(doc["data"])
    return any(w in str(k).lower() for k in keys for w in _BALANCE_WORDS)


def _check_stemsplit():
    """The free balance read - one path, not the five probe() walks - with
    the app's own host and headers, but read raw: stemsplit_provider._call
    keeps an error body only when it is JSON, and Cloudflare's 1010 is
    plain text ("error code: 1010"), so through _call the firewall read as
    a refused key (providers review, 2026-09-23)."""
    import stemsplit_provider as ss
    req = urllib.request.Request(ss.BASE + "/balance", headers=ss._headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        try:
            text = (e.read() or b"").decode("utf-8", "replace")
        except Exception:
            text = ""
        if e.code == 403 and _CLOUDFLARE_1010.search(text):
            return _fail("Cloudflare's firewall in front of StemSplit refused the request (error "
                         "1010) before StemSplit read the key.")
        if e.code == 404:
            return _fail("StemSplit answered 404 for /balance: the path is wrong, not the key.")
        return _refused("StemSplit", e.code, _words(text) or str(e.reason or ""))
    except Exception as e:
        return _from_exception("StemSplit", e)
    doc, bad = _json_doc(raw, "StemSplit")
    if bad:
        return bad
    if not isinstance(doc, dict) or not _balance_like(doc):
        return _malformed("StemSplit")
    return _ok("StemSplit answered the balance read. Reading it spends no credit.")


# ---- public music lookups (keyless) -------------------------------------------------------

def _check_itunes():
    import music_apis
    url = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(
        {"isrc": KNOWN_ISRC, "entity": "song"})
    try:
        doc = music_apis._fetch_json(url)
    except Exception as e:
        return _from_exception("Apple", e)
    if not isinstance(doc, dict) or not ("results" in doc or "resultCount" in doc):
        return _malformed("Apple")
    n = len(doc.get("results") or [])
    return _ok("Apple answered an ISRC lookup (%s)." % _plural(n, "result"))


def _check_deezer():
    import music_apis
    try:
        doc = music_apis._fetch_json("https://api.deezer.com/track/isrc:" + KNOWN_ISRC)
    except Exception as e:
        return _from_exception("Deezer", e)
    if isinstance(doc, dict) and isinstance(doc.get("error"), dict):
        code = doc["error"].get("code")
        if code == 800:
            return _ok("Deezer answered: it has no track for the test ISRC (code 800, its word for no data).")
        return _fail("Deezer refused (code %s): %s" % (code, doc["error"].get("message") or "no message"))
    if not isinstance(doc, dict) or not doc.get("id"):
        return _malformed("Deezer")
    return _ok("Deezer answered an ISRC lookup.")


def _check_odesli():
    import music_apis
    url = "https://api.song.link/v1-alpha.1/links?" + urllib.parse.urlencode({"url": KNOWN_TRACK_URL})
    try:
        doc = music_apis._fetch_json(url)
    except Exception as e:
        return _from_exception("Odesli", e)
    if not isinstance(doc, dict) or not isinstance(doc.get("linksByPlatform"), dict):
        return _malformed("Odesli")
    return _ok("Odesli answered with %s for the test track."
               % _plural(len(doc["linksByPlatform"]), "platform link"))


def _check_google_news():
    import xml.etree.ElementTree as ET

    import music_apis
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": "music", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    try:
        text = music_apis._fetch_text(url)
    except Exception as e:
        return _from_exception("Google News", e)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return _malformed("Google News")
    if root.tag != "rss" and root.find(".//channel") is None:
        return _malformed("Google News")
    return _ok("Google News answered with %s." % _plural(len(list(root.iter("item"))), "item"))


# ---- records the app already keeps (no call) -----------------------------------------------

def _local_acr_identify(store):
    base = ("No safe live check: every identify spends one recognition from the project's quota "
            "and needs audio.")
    try:
        with store.get_db() as conn:
            row = conn.execute("SELECT result, message, created FROM beat_fingerprint_checks"
                               " ORDER BY created DESC, rowid DESC LIMIT 1").fetchone()
    except Exception:
        row = None
    if not row:
        return _not_asked(base + " No identify has been run yet.")
    return _not_asked("%s The last one (%s) came back %s%s." % (
        base, str(row["created"])[:16].replace("T", " "), row["result"],
        (": " + row["message"]) if row["message"] else ""))


def _local_symphonic(store):
    base = "Never checked from here: every call files a real application with Symphonic."
    try:
        rows = store.distribution_applications(None, limit=1)
    except Exception:
        rows = []
    if not rows:
        return _not_asked(base + " No application has been sent yet.")
    last = rows[0]
    when = str(last.get("created") or "")[:16].replace("T", " ")
    if last.get("sent"):
        return _ok("%s The last real application (%s) went through." % (base, when))
    return _fail("%s The last real application (%s) was refused: %s"
                 % (base, when, last.get("error") or "no reason given"))


# ---- the providers ---------------------------------------------------------------------
# Each is a dict:
#   key, name, family, powers (one plain line), where (the page it feeds)
#   env        required names; optional: names that change behaviour
#   flags      *_ENABLED switches that must be on
#   any_of     alternative credential sets; one complete set is enough
#   present    {name: callable} for a key the app may hold outside the
#              environment (True, "app"/"legacy" = held by the app, or False)
#   pending    callable(missing) -> None, or (label, detail): what is missing
#              is something the app makes for itself, not a thing to set
#   sandboxed  the app's own configured() is False on a SANDBOX deployment
#   gate       callable -> None, or (label, detail): not asked, by ruling
#   check      callable -> {"ok", "detail"[, "label"]}; None when no safe
#              check exists. needs_base: it is called with this
#              deployment's base URL (the Stripe webhook is per host)
#   no_check   what the row says when there is no check
#   local      callable(store) -> a result read from what the app already
#              keeps (no network), shown on a page view
#   fixed      (label, detail) for a row whose state is a known fact
#   auto       part of "Check all": free, read-only, writes nothing
#   cost, cost_kind ("billed", "quota", "writes"), timeout, min_interval_s
#   late       callable -> what a costed check that ran past its limit has
#              already spent; its call is not recalled by the time limit
#
# Every costed row has a min_interval_s, so a second press inside it shows
# the stored answer instead of spending again, and its time limit sits
# above its adapter's own worst case, so a call that is still going to be
# counted is not reported as a plain failure.

FAMILIES = (
    ("music", "Music data and rights"),
    ("touring", "Touring and places"),
    ("money", "Money, shop and mail"),
    ("storage", "Storage, backup and monitoring"),
    ("audio", "Audio tools"),
    ("lookups", "Public music lookups"),
)

_GOOGLE_BILLED = ("Billed by Google above the free monthly cap. One call per press; "
                  "check the Cloud console's billing page for where you stand.")

PROVIDERS = [
    # -- music data and rights --
    dict(key="mlc", name="The MLC", family="music", where="/recovery",
         powers="Mechanical-rights matching: the MLC sweep on Recovery, a track's MLC check and "
                "songwriter credits on Add to catalog.",
         env=("MLC_USERNAME", "MLC_PASSWORD"), flags=("MLC_ENABLED",),
         check=_check_mlc, auto=True, timeout=20,
         cost="Free: a sign-in when none is kept, then one search by ISRC."),
    dict(key="soundcharts", name="Soundcharts", family="music", where="/pulse",
         powers="Monthly listeners on Pulse, and Signal's artist, city and playlist readings.",
         flags=("SOUNDCHARTS_ENABLED",),
         any_of=(("SOUNDCHARTS_CLIENT_ID", "SOUNDCHARTS_CLIENT_SECRET"),
                 ("SOUNDCHARTS_ACCESS_TOKEN",),
                 ("SOUNDCHARTS_APP_ID", "SOUNDCHARTS_API_KEY")),
         optional=("SOUNDCHARTS_TEAM_ID",),
         check=_check_soundcharts, auto=False, cost_kind="billed",
         timeout=35, min_interval_s=60, late=_soundcharts_late,
         cost="Spends 1 paid call from the plan's monthly quota, counted in the Soundcharts "
              "budget. Refused unasked when the month's allowance is spent."),
    dict(key="songstats", name="Songstats", family="music", where="/royalties",
         powers="Which stores carry an ISRC, for the store coverage check on Royalties and Statements.",
         env=("SONGSTATS_API_KEY",), flags=("SONGSTATS_ENABLED",),
         check=_check_songstats, auto=False, cost_kind="quota", timeout=15, min_interval_s=60,
         cost="Spends 1 of the 1,000 calls Songstats allows a month for artist search."),
    dict(key="discogs", name="Discogs", family="music", where="/catalog",
         powers="Finding a pressing and filling its label, catalogue number and credits on a track.",
         env=("DISCOGS_TOKEN",), flags=("DISCOGS_ENABLED",), sandboxed=True,
         check=_check_discogs, auto=True,
         cost="Free: 1 of 60 calls a minute."),
    dict(key="spotify", name="Spotify", family="music", where="/pulse",
         powers="Followers and popularity on Pulse, artist search, the store check, and the real "
                "pre-save button on a campaign link.",
         env=("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"), optional=("SPOTIFY_REDIRECT_URI",),
         note="Pre-save also needs SPOTIFY_REDIRECT_URI; Pulse and search do not.",
         check=_check_spotify, auto=True,
         cost="Free: one token request."),
    dict(key="youtube", name="YouTube Data API", family="music", where="/pulse",
         powers="The YouTube panel on Pulse: subscribers, views and recent uploads.",
         env=("YOUTUBE_API_KEY",), flags=("YOUTUBE_ENABLED",),
         check=_check_youtube, auto=True,
         cost="Free: 1 unit of the Google project's 10,000-unit daily quota."),
    dict(key="acr_console", name="ACRCloud console", family="music", where="/fingerprints",
         powers="The fingerprints desk: registering a master into a bucket and scanning long recordings.",
         env=("ACRCLOUD_CONSOLE_TOKEN",), sandboxed=True,
         check=_check_acr_console, auto=True,
         cost="Free: an account read, the same one the fingerprints desk makes on every visit."),
    dict(key="acr_identify", name="ACRCloud identify", family="music", where="/beats",
         powers="Identify on the Beats desk: a beat slice or a clip against released recordings.",
         env=("ACRCLOUD_HOST", "ACRCLOUD_ACCESS_KEY", "ACRCLOUD_ACCESS_SECRET"),
         check=None, local=_local_acr_identify,
         note="The console token above does not prove this key and secret."),
    dict(key="symphonic", name="Symphonic distribution applications", family="music",
         where="/distribution/apply",
         powers="The distribution application form, filed into Symphonic's HubSpot sheet.",
         check=None, local=_local_symphonic),
    dict(key="chartmetric", name="Chartmetric", family="music", built=False,
         powers="Nothing yet.",
         fixed=("Not built", "Not built: Signal and Release Signal each declare a Chartmetric "
                             "adapter, and neither has any code that calls Chartmetric. Setting "
                             "its variables would not connect anything.")),
    dict(key="soundexchange", name="SoundExchange", family="music", built=False,
         powers="Nothing yet.",
         fixed=("Not built", "Not built: SoundExchange publishes no public API, and the adapter "
                             "declared in Signal has no calls in it.")),
    dict(key="spotify_metadata", name="Spotify metadata for Signal", family="music", built=False,
         powers="Nothing yet; the working Spotify connection is the row above.",
         fixed=("Not built", "Not built: a declared Signal adapter with no calls in it.")),

    # -- touring and places --
    dict(key="eventbrite", name="Eventbrite", family="touring", where="/tours",
         powers="Sync ticket sales on the tour home: a date's ticket link, on-sale state and "
                "measured sold count.",
         env=("EVENTBRITE_TOKEN",), sandboxed=True,
         check=_check_eventbrite, auto=True,
         cost="Free: 1 of 2,000 calls an hour."),
    dict(key="ticketmaster", name="Ticketmaster", family="touring", where="/tours",
         powers="Ticket links and on-sale status for dates Eventbrite could not match. Never a "
                "sold count: Discovery publishes none.",
         env=("TICKETMASTER_API_KEY",), optional=("TICKETMASTER_ENABLED",), sandboxed=True,
         gate=_gate_ticketmaster, check=_check_ticketmaster, auto=True,
         cost="Free: 1 of 5,000 calls a day."),
    dict(key="bandsintown", name="Bandsintown", family="touring", where="/epk",
         powers="Would fill an EPK's tour dates when TOUR has none.",
         env=("BANDSINTOWN_APP_ID",), check=None,
         fixed=("Dormant", "Dormant: Bandsintown declined to issue an app id (2026-09-07). TOUR "
                           "is the dates source now, so there is nothing to check.")),
    dict(key="google_places", name="Google Places (venue photos)", family="touring", where="/tours",
         powers="The venue photo beside each tour date, with Google's credit.",
         env=("GOOGLE_MAPS_API_KEY",), sandboxed=True,
         check=_check_places, auto=False, cost_kind="billed", min_interval_s=60,
         cost=_GOOGLE_BILLED),
    dict(key="google_geocoding", name="Google Geocoding", family="touring", where="/tours",
         powers="Fetch coordinates on the tour home: a venue's map pin and its matched address.",
         env=("GOOGLE_MAPS_API_KEY",), sandboxed=True,
         check=_check_geocoding, auto=False, cost_kind="billed", min_interval_s=60,
         cost=_GOOGLE_BILLED),
    dict(key="google_timezone", name="Google Time Zone", family="touring", where="/tours",
         powers="Each venue's time zone, which the day sheet, My Day and the calendar file print.",
         env=("GOOGLE_MAPS_API_KEY",), sandboxed=True,
         check=_check_timezone, auto=False, cost_kind="billed", min_interval_s=60,
         cost=_GOOGLE_BILLED),
    dict(key="google_routes", name="Google Routes", family="touring", where="/tours",
         powers="Measured drives between dates on the route map, and the late-for-load-in flag.",
         env=("GOOGLE_MAPS_API_KEY",), sandboxed=True,
         note="Not enabled on the owner's Google project (2026-09-09), so the route page draws "
              "straight lines. Nothing is asked until you press the button.",
         check=_check_routes, auto=False, cost_kind="billed", min_interval_s=60,
         cost="Billed by Google above the free monthly cap once enabled; a refused call is not billed."),

    # -- money, shop and mail --
    dict(key="stripe", name="Stripe", family="money", where="/billing",
         powers="Memberships, fan-club subscriptions, VIP tickets and Release-Ready masters.",
         env=("STRIPE_SECRET_KEY",), optional=("STRIPE_WEBHOOK_SECRET",),
         present={"STRIPE_WEBHOOK_SECRET": _stripe_secret_state}, sandboxed=True,
         check=_check_stripe, needs_base=True, auto=True,
         cost="Free: a read of the webhook endpoints. Nothing is changed."),
    dict(key="shopify_buy", name="Shopify Buy Buttons", family="money", where="/apparel",
         powers="The store embed on Apparel and the merch shelf on the owner's EPK.",
         env=("SHOPIFY_DOMAIN", "SHOPIFY_COLLECTION_ID", "SHOPIFY_STOREFRONT_TOKEN"),
         present={"SHOPIFY_STOREFRONT_TOKEN": _storefront_token_state},
         pending=_storefront_pending,
         note="The embed loads Shopify's script in the visitor's browser; a pass here proves the "
              "token and collection it uses, not the script.",
         check=_check_shopify_buy, auto=True,
         cost="Free: the embed's own read-only query."),
    dict(key="shopify_admin", name="Shopify Admin (customer import)", family="money",
         where="/links/fans",
         powers="Importing the store's subscribed customers into the Fan CRM.",
         env=("SHOPIFY_DOMAIN",),
         any_of=(("SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET"), ("SHOPIFY_ADMIN_TOKEN",)),
         check=_check_shopify_admin, auto=True,
         cost="Free: one read of the shop's name."),
    dict(key="resend", name="Resend (email)", family="money",
         powers="Every email the app sends: password resets, invites, fan mail, advances, press.",
         env=("RESEND_API_KEY",), optional=("EMAIL_FROM",), sandboxed=True,
         check=_check_resend, auto=True,
         cost="Free: a read of the account's domains. No mail is sent."),
    dict(key="resend_inbound", name="Resend inbound (statement drop-box)", family="money",
         where="/statements",
         powers="Distributor statements emailed to the drop-box address landing in Statements.",
         env=("RESEND_INBOUND_DOMAIN", "RESEND_WEBHOOK_SECRET", "RESEND_API_KEY"),
         check=None,
         no_check="No live check: only a real email proves delivery. The drop-box self-test on "
                  "Statements sends one and files a test statement."),
    dict(key="webhooks", name="Inbound webhooks", family="money",
         powers="Billing changes from Stripe, inbound mail from Resend, finished audio jobs "
                "from ElevenLabs.",
         optional=("STRIPE_WEBHOOK_SECRET", "RESEND_WEBHOOK_SECRET", "ELEVENLABS_WEBHOOK_SECRET"),
         present={"STRIPE_WEBHOOK_SECRET": _stripe_secret_state},
         check=None, local=_local_webhooks),

    # -- storage, backup and monitoring --
    dict(key="r2", name="Cloudflare R2 (uploads)", family="storage", where="/vault",
         powers="Every upload surviving a deploy: masters, artwork, EPK kits, stems, and the "
                "links RoEx downloads from.",
         env=("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"),
         optional=("R2_PUBLIC_BASE_URL",), sandboxed=True,
         check=_check_r2, auto=False, cost_kind="writes", timeout=45, min_interval_s=60,
         late=_r2_late,
         cost="Writes and deletes one tiny test object in the bucket (a few R2 operations, "
              "inside the free tier)."),
    dict(key="backup", name="Off-box backup", family="storage", where="/settings",
         powers="The nightly copy of the database and uploads to a second bucket.",
         env=("BACKUP_S3_ENDPOINT", "BACKUP_S3_BUCKET", "BACKUP_S3_KEY", "BACKUP_S3_SECRET",
              "BACKUP_TOKEN"),
         optional=("BACKUP_S3_REGION",),
         check=None, local=_local_backup),
    dict(key="sentry", name="Sentry (error reporting)", family="storage",
         powers="Unhandled errors reported to Sentry, scrubbed first.",
         env=("SENTRY_DSN",), check=None, local=_local_sentry),
    dict(key="suite_sso", name="Suite sign-in secret", family="storage",
         powers="Signing artists into The Room, REACH, Noise Lab, Tour and Motion.",
         env=("SUITE_SSO_SECRET",), check=None,
         no_check="No live check: Street Banker never calls the suites. A secret that differs "
                  "from theirs shows only as a refused hand-off on the suite's side."),

    # -- audio tools --
    dict(key="elevenlabs", name="ElevenLabs", family="audio", where="/admin/audio",
         powers="Audio Studio's vendor lanes: dubbing, voiceover, sound effects, stems, "
                "transcription.",
         env=("ELEVENLABS_API_KEY",), flags=("ELEVENLABS_ENABLED",),
         optional=("AUDIO_INTELLIGENCE_ENABLED",),
         note="Audio jobs also need AUDIO_INTELLIGENCE_ENABLED; the key works without it.",
         check=_check_elevenlabs, auto=True,
         cost="Free: reads the model list; no characters are spent."),
    dict(key="roex", name="RoEx (Release-Ready)", family="audio", where="/admin/release-ready",
         powers="Release-Ready in Creative Studio: the mix report, previews and paid masters.",
         env=("ROEX_API_KEY",), sandboxed=True,
         check=_check_roex, auto=True,
         cost="Free: RoEx's /health spends no credits (one slot of our own rate limiter)."),
    dict(key="stemsplit", name="StemSplit (Studio Split)", family="audio", where="/rack",
         powers="The studio-quality stem split in the Rack.",
         env=("STEMSPLIT_API_KEY",),
         check=_check_stemsplit, auto=True,
         cost="Free: a balance read; only a split job spends credits."),

    # -- public music lookups --
    dict(key="itunes", name="Apple iTunes lookup", family="lookups", where="/discover",
         powers="Song results on Discover and the Apple lane of the store check.",
         check=_check_itunes, auto=True, cost="Free, no key."),
    dict(key="deezer", name="Deezer", family="lookups", where="/catalog",
         powers="ISRC, UPC and label autofill on Add to catalog, and the Deezer lane of the store check.",
         check=_check_deezer, auto=True, cost="Free, no key."),
    dict(key="odesli", name="Odesli (song.link)", family="lookups", where="/links",
         powers="Smart Links: one track link in, every platform's link out.",
         check=_check_odesli, auto=True, min_interval_s=60,
         cost="Free, no key, but 10 calls a minute shared with artists making links; asked at "
              "most once a minute from here."),
    dict(key="google_news", name="Google News", family="lookups", where="/epk",
         powers="The press-mention search on the EPK.",
         check=_check_google_news, auto=True, cost="Free, no key (an unofficial feed)."),
    dict(key="musicbrainz", name="MusicBrainz", family="lookups", where="/signal/admin/data-sources",
         powers="Signal's artist identity and releases, when Soundcharts is not serving them.",
         env=("MUSICBRAINZ_CONTACT",), flags=("MUSICBRAINZ_ENABLED",),
         check=_check_musicbrainz, auto=True,
         cost="Free, no account; one request, inside their one-a-second rule."),
]


def by_key(key):
    return next((p for p in PROVIDERS if p["key"] == key), None)


# ---- configuration, by name only ----------------------------------------------------------

def _is_set(p, name):
    """True, "app" (held by the app outside the environment) or False."""
    override = (p.get("present") or {}).get(name)
    if override is not None:
        try:
            return override() or False
        except Exception:
            return False
    return bool(_env(name))


def missing(p):
    """What stops this service from being called: required names not set,
    switches off, and - where alternatives exist - no complete set."""
    out = [n for n in p.get("env", ()) if not _is_set(p, n)]
    for flag in p.get("flags", ()):
        if not _truthy(os.environ.get(flag)):
            out.append("%s=1" % flag)
    groups = p.get("any_of") or ()
    if groups and not any(all(_is_set(p, n) for n in g) for g in groups):
        out.append("one of " + " or ".join(" + ".join(g) for g in groups))
    return out


def configured(p):
    return not missing(p)


def gate(p):
    """(label, detail) when the app itself would not call this service here,
    or None. Checked after configuration, before any call."""
    if p.get("sandboxed") and _sandbox():
        return ("Off in this sandbox",
                "Off on purpose: this is a sandbox deployment (SANDBOX is set), so the app does "
                "not call this service here. Nothing was asked.")
    if p.get("gate"):
        try:
            return p["gate"]()
        except Exception:
            return None
    return None


# ---- never show a secret -------------------------------------------------------------------

# Names whose values are credentials. Their values are blanked even when a
# vendor quoted only the first part of one; a bucket name, a domain or a
# sender address is blanked whole but not by its first characters, which
# would eat ordinary words ("Street B...").
_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|DSN|CLIENT_ID|APP_ID)")
_RUN = 8                      # this many characters of a secret in a row is a leak


def _all_names():
    names = set()
    for q in PROVIDERS:
        names.update(q.get("env", ()))
        names.update(q.get("optional", ()))
        for g in q.get("any_of") or ():
            names.update(g)
    return names


def _kv_many(store, keys):
    """{key: value} for the app_kv rows that exist among `keys`, in one
    read. Every connection is a file open and, for a write, a sync; a page
    view or a Check all that opened one per row spent seconds on them
    (fixer, 2026-09-23)."""
    keys = [k for k in dict.fromkeys(keys) if k]
    if not keys:
        return {}
    try:
        with store.get_db() as conn:
            found = conn.execute("SELECT key, value FROM app_kv WHERE key IN (%s)"
                                 % ",".join("?" * len(keys)), keys).fetchall()
    except Exception:
        return {}
    return {row["key"]: row["value"] for row in found}


def _kept_token(raw):
    """A secret the app keeps in app_kv: plain, or {"token": ...}."""
    raw = str(raw or "")
    if raw[:1] == "{":
        try:
            return str((json.loads(raw) or {}).get("token") or "")
        except ValueError:
            return ""
    return raw


def _held_secrets():
    """Credentials the app holds outside the environment, read as kept -
    never minted, never asked for: the Shopify Admin token from the client
    credentials grant, the Storefront token the app minted, the Stripe
    signing secrets the in-app setup saved (each mode's, and the legacy
    one), Soundcharts' kept bearer, and The MLC's bearers in this process.
    scrub() knew only the environment, so an echo of these came back whole
    (providers review, 2026-09-23)."""
    out = []
    try:
        import db
    except Exception:
        return out
    kv_keys = []
    for module, attr in (("shopify_customers", "GRANT_KEY"), ("shopify_buy", "STOREFRONT_KEY"),
                         ("stripe_provider", "_LEGACY_SECRET_KEY")):
        try:
            kv_keys.append(getattr(__import__(module), attr))
        except Exception:
            pass
    kv_keys += ["stripe_live_webhook_secret", "stripe_test_webhook_secret"]
    sp = sys.modules.get("signal_providers")
    if sp is not None:
        kv_keys.append(getattr(getattr(sp, "SoundchartsAdapter", None), "token_kv_key", ""))
    kept = _kv_many(db, [k for k in kv_keys if k])  # one read, not one per secret
    out.extend(_kept_token(v) for v in kept.values())
    mlc = getattr(sp, "_mlc", None) if sp is not None else None
    for attr in ("_access", "_id", "_refresh"):
        out.append(str(getattr(mlc, attr, "") or ""))
    return [v.strip() for v in out if v and len(v.strip()) >= 6]


def _spellings(value):
    """A value as typed, URL-encoded and JSON-escaped: the ways it leaves."""
    return {value, urllib.parse.quote(value, safe=""), urllib.parse.quote_plus(value),
            json.dumps(value)[1:-1]}


def _secret_forms():
    """(whole, runs): every configured value (not the on/off switches) and
    every held secret, in its spellings; and the credential spellings whose
    first characters alone are enough to blank (a URL-shaped one from past
    its scheme, where the key starts)."""
    whole, runs = set(), set()
    for n in _all_names():
        v = _env(n)
        if len(v) < 6:
            continue
        whole |= _spellings(v)
        if _SECRET_NAME.search(n):
            runs |= _spellings(v.split("://", 1)[1] if "://" in v else v)
    for v in _held_secrets():
        whole |= _spellings(v)
        runs |= _spellings(v)
    return whole, runs


def _blank_runs(text, value):
    """Blank every place `value` begins in `text`, however soon it stops:
    an adapter that cut a vendor's words at 200 characters may have cut a
    quoted key in two, and the part before the cut is still the key."""
    if len(value) < _RUN:
        return text
    head = value[:_RUN]
    if head not in text:
        return text
    out, i = [], 0
    while True:
        j = text.find(head, i)
        if j < 0:
            out.append(text[i:])
            return "".join(out)
        k = _RUN
        while j + k < len(text) and k < len(value) and text[j + k] == value[k]:
            k += 1
        out.append(text[i:j])
        out.append("[hidden]")
        i = j + k


# A header echoed back as a dict, a tuple or a line: the name, then the value.
_HEADER_VALUE = re.compile(
    r"(?i)\b(x-shopify-(?:storefront-)?access-token|x-goog-api-key|xi-api-key|x-api-key|"
    r"x-app-id|apikey|authorization)"
    r"(\s*['\"]?\s*[:=]\s*['\"]?\s*|['\"]\s*,\s*['\"])"
    r"((?:bearer|basic|discogs\s+token=|token)\s*)?"
    r"(?!\[hidden\])(?!(?:bearer|basic|token)\s)[^'\"\s,;}\]]+")


def scrub(text, p=None, limit=400, forms=None):
    """The words of a result with every secret blanked - every provider's
    and every one the app holds, whichever row the words belong to, since
    one vendor may quote a header another's key rode in - and anything
    shaped like a bearer token, a key parameter or a credential header cut
    out. Shortened for the page only after that: this is the only cut."""
    text = str(text or "")
    whole, runs = forms if forms is not None else _secret_forms()
    for v in sorted(whole, key=len, reverse=True):
        if v:
            text = text.replace(v, "[hidden]")
    for v in sorted(runs, key=len, reverse=True):
        text = _blank_runs(text, v)
    text = _HEADER_VALUE.sub(lambda m: m.group(1) + m.group(2) + (m.group(3) or "") + "[hidden]",
                             text)
    text = re.sub(r"(?i)\b(bearer)\s+[A-Za-z0-9\-._~+/=]{8,}", r"\1 [hidden]", text)
    text = re.sub(r"\bBasic\s+[A-Za-z0-9+/=]{16,}", "Basic [hidden]", text)
    # Stripe says "Invalid API Key provided: sk_test_****1234": even a
    # vendor's masked echo of a key stays off the page.
    text = re.sub(r"\b(?:sk|rk|pk|whsec|shpat|shpss|shpca)_[A-Za-z0-9_*]{4,}", "[hidden]", text)
    text = re.sub(r"(?i)((?:api_?key|apikey|key|token|secret|password|access_token|client_secret|"
                  r"client_id|signature|sig)=)[^&\s\"'<>]+", r"\1[hidden]", text)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


# ---- running a check ------------------------------------------------------------------------

# Results that say only "nothing was asked, because of how it is set up".
# They are shown live from the environment and never stored: a stored one
# outlives the setting that caused it (providers review, 2026-09-23).
_UNSTORED = ("unconfigured", "gated")

_LATE = {
    "billed": "The call had already left and may still be billed (1 call); check the provider's "
              "usage before pressing again.",
    "quota": "The call had already left and may still count against the quota (1 call); check "
             "the provider's usage before pressing again.",
    "writes": "The write may still complete after this.",
}


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _pending(p, miss):
    fn = p.get("pending")
    if not fn or not miss:
        return None
    try:
        return fn(miss)
    except Exception:
        return None


def run(p, timeout=None, base_url=None):
    """Run one provider's check under a hard time limit. Returns
    {ok, detail, ms, at} (plus "reason" when nothing could be asked, and
    "label" for a known state a service named), its words scrubbed. Never
    raises, and calls nobody unless the service is configured, not gated
    and has a safe check."""
    return _scrubbed(_ask(p, timeout, base_url), p, _secret_forms())


def _scrubbed(result, p, forms):
    """The result with its words scrubbed. The secrets are read after the
    check, since a check can leave a new one behind (a grant's token)."""
    return dict(result, detail=scrub(result.get("detail") or "", p, forms=forms))


def _ask(p, timeout=None, base_url=None):
    """run() without the scrub: the words as the check gave them. Check all
    scrubs every result at once, with the secrets read once."""
    timeout = timeout if timeout is not None else p.get("timeout", CHECK_TIMEOUT_S)
    started = time.monotonic()
    if p.get("fixed"):
        return {"ok": None, "detail": p["fixed"][1], "ms": 0, "at": _now_iso(), "reason": "fixed"}
    if p.get("check") is None:
        return {"ok": None, "detail": p.get("no_check") or
                "No safe live check exists for this service; only its keys are read.",
                "ms": 0, "at": _now_iso(), "reason": "no_check"}
    miss = missing(p)
    if miss:
        pend = _pending(p, miss)
        return {"ok": None, "ms": 0, "at": _now_iso(), "reason": "unconfigured",
                "detail": pend[1] if pend else
                "Not configured: set %s. Nothing was asked." % ", ".join(miss)}
    ruled = gate(p)
    if ruled:
        return {"ok": None, "detail": ruled[1], "ms": 0, "at": _now_iso(), "reason": "gated"}
    box = {}

    def work():
        try:
            fn = p["check"]
            box["r"] = (fn(base_url) if p.get("needs_base") else fn()) or {}
        except Exception as e:                      # the service's own words
            box["r"] = {"ok": False, "detail": "%s: %s" % (type(e).__name__, e)}

    t = threading.Thread(target=work, daemon=True, name="provider-check-%s" % p["key"])
    t.start()
    t.join(timeout)
    ms = int((time.monotonic() - started) * 1000)
    if t.is_alive():
        # The time limit stops the waiting, not the call. For a check that
        # costs, the call has left and will be counted; saying only "no
        # answer" would invite a second paid press.
        detail = "No answer within %g seconds." % timeout
        if p.get("cost_kind"):
            note = None
            try:
                note = p["late"]() if p.get("late") else None
            except Exception:
                note = None
            detail += " " + (note or _LATE.get(p["cost_kind"], ""))
        return {"ok": False, "detail": detail, "ms": ms, "at": _now_iso()}
    r = box.get("r") or {}
    ok = r.get("ok")
    out = {"ok": ok if ok in (True, False) else None,
           "detail": str(r.get("detail") or ("Answered." if ok else "No detail given.")),
           "ms": ms, "at": _now_iso()}
    if out["ok"] is None and r.get("label"):
        out["label"] = str(r["label"])[:40]
    return out


_UPSERT = ("INSERT INTO app_kv (key, value, updated) VALUES (?, ?, ?) "
           "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated = excluded.updated")


def save(key, result, store):
    store.set_kv(KV_PREFIX + key, json.dumps(result))


def _save_many(results, store):
    """Every result of one Check all, in one write."""
    rows = [(KV_PREFIX + key, json.dumps(r), _now_iso()) for key, r in results.items()]
    if rows:
        with store.get_db() as conn:
            conn.executemany(_UPSERT, rows)


def _parse(raw):
    try:
        return json.loads(raw) if raw else None
    except Exception:
        return None


def last(key, store):
    try:
        return _parse(store.get_kv(KV_PREFIX + key))
    except Exception:
        return None


def _lasts(keys, store):
    """{key: the last stored result or None} for many providers, in one read."""
    kept = _kv_many(store, [KV_PREFIX + k for k in keys])
    return {k: _parse(kept.get(KV_PREFIX + k)) for k in keys}


def _too_soon(p, prev):
    """A service with a tight shared limit, or a check that costs, is asked
    at most once per min_interval_s; inside it the last answer stands. An
    answer counts when something was asked: working, failing, or a known
    state the service named (a label) - Google Routes' "Not enabled" came
    back from a real call."""
    gap = p.get("min_interval_s")
    if not gap or not prev:
        return False
    if prev.get("ok") is None and not prev.get("label"):
        return False
    try:
        at = datetime.fromisoformat(prev["at"])
    except Exception:
        return False
    return (datetime.now(timezone.utc) - at).total_seconds() < gap


# One check per service at a time, across workers: a double-click sends two
# POSTs, and without this both ran - a paid check spent twice, and Check all
# asked Odesli and MusicBrainz twice inside their limits (providers review,
# 2026-09-23). A lease is a row in app_kv claimed in one statement; it
# lapses by itself after the check's time limit, so a crashed worker cannot
# hold it.
LEASE_PREFIX = KV_PREFIX + "running:"

_CLAIM = (_UPSERT + " WHERE app_kv.value = '' OR CAST(app_kv.value AS REAL) < ?")


def _claim_many(holds, store):
    """Claim leases in one write: {name: lease} for each (name, hold_s)
    claimed. The first name gates the rest - when it is held, nothing is
    claimed (Check all's own lease, before any service's)."""
    now = time.time()
    got = {}
    with store.get_db() as conn:
        for i, (name, hold_s) in enumerate(holds):
            value = "%.3f %s" % (now + hold_s, uuid.uuid4().hex)
            cur = conn.execute(_CLAIM, (LEASE_PREFIX + name, value, _now_iso(), now))
            if cur.rowcount == 1:
                got[name] = value
            elif i == 0:
                return {}
    return got


def _claim(name, hold_s, store):
    return _claim_many([(name, hold_s)], store).get(name)


def _release_many(leases, store):
    if not leases:
        return
    try:
        with store.get_db() as conn:
            conn.executemany("UPDATE app_kv SET value = '', updated = ? WHERE key = ? AND value = ?",
                             [(_now_iso(), LEASE_PREFIX + name, value)
                              for name, value in leases.items()])
    except Exception:
        pass                                        # each lapses by itself


def _release(name, value, store):
    _release_many({name: value}, store)


def _hold(p):
    return float(p.get("timeout", CHECK_TIMEOUT_S)) + 5.0


def _skipped(prev, why):
    """The last stored answer, marked as not asked again just now: "busy"
    (a check of it is already running) or "too_soon" (inside its
    min_interval_s). Never stored."""
    return dict(prev or {}, skipped=why)


def check(key, store, base_url=None):
    """Run and remember one provider's check - unless one is already
    running, or it was asked inside its interval: then the last answer,
    marked "skipped"."""
    p = by_key(key)
    if p is None:
        return None
    lease = _claim(key, _hold(p), store)
    if not lease:
        return _skipped(last(key, store), "busy")
    try:
        prev = last(key, store)
        if _too_soon(p, prev):
            return _skipped(prev, "too_soon")
        result = run(p, base_url=base_url)
        if result.get("reason") not in _UNSTORED:
            save(key, result, store)
        return result
    finally:
        _release(key, lease, store)


def auto_keys():
    """The free, read-only checks "Check all" runs."""
    return [p["key"] for p in PROVIDERS if p.get("auto")]


def check_all(store, base_url=None):
    """Every provider whose check is free, together, each under its own time
    limit. The ones that spend money or a scarce quota, or write anything,
    are left for their own button; the ones not configured or gated answer
    without calling anyone. One Check all at a time; a service already
    being checked, or asked inside its interval, is skipped (marked).

    The bookkeeping - leases, last results, the secrets to scrub, the saves
    - is one read or write each, not one per service, so the whole press
    stays close to its slowest check's limit."""
    auto = [p for p in PROVIDERS if p.get("auto")]
    if not auto:
        return {}
    leases = _claim_many([("all", max(_hold(p) for p in auto))] +
                         [(p["key"], _hold(p)) for p in auto], store)
    prevs = _lasts([p["key"] for p in auto], store)
    if "all" not in leases:
        return {p["key"]: _skipped(prevs[p["key"]], "busy") for p in auto}
    results, todo = {}, []
    try:
        for p in auto:
            key = p["key"]
            if key not in leases:
                results[key] = _skipped(prevs[key], "busy")
            elif _too_soon(p, prevs[key]):
                results[key] = _skipped(prevs[key], "too_soon")
            else:
                todo.append(p)
        if todo:
            with ThreadPoolExecutor(max_workers=len(todo)) as pool:
                ran = list(pool.map(lambda q: _ask(q, base_url=base_url), todo))
            forms = _secret_forms()
            ran = {p["key"]: _scrubbed(r, p, forms) for p, r in zip(todo, ran)}
            _save_many({k: r for k, r in ran.items() if r.get("reason") not in _UNSTORED}, store)
            results.update(ran)
    finally:
        _release_many(leases, store)
    return results


# ---- what the page shows ----------------------------------------------------------------

def _chip(p, name, pending=False):
    state = _is_set(p, name)
    return {"name": name, "set": state is True, "app": state in ("app", "legacy"),
            "legacy": state == "legacy", "pending": bool(pending and not state)}


def _lamp(result):
    if result is None:
        return None
    if result.get("ok") is True:
        return ("good", "Working")
    if result.get("ok") is False:
        return ("crit", "Failing")
    return None


def rows(store):
    """What the page shows, grouped by family, in the page's order. Reads
    the environment and what the app already keeps; calls nobody."""
    forms = _secret_forms()
    kept = _lasts([p["key"] for p in PROVIDERS], store)     # one read for every row
    out = []
    for fam_key, fam_name in FAMILIES:
        group = []
        for p in PROVIDERS:
            if p["family"] != fam_key:
                continue
            built = p.get("built", True)
            miss = missing(p) if built else []
            pend = _pending(p, miss)
            prev = kept.get(p["key"])
            if prev and prev.get("reason") in _UNSTORED:
                prev = None                 # "not configured then" says nothing about now
            detail, shown = "", None
            if p.get("fixed"):
                lamp, detail = ("idle", p["fixed"][0]), p["fixed"][1]
            elif pend:
                lamp, detail = ("idle", pend[0]), pend[1]
            elif miss:
                lamp = ("off", "Not configured")
                detail = "Set %s to switch it on." % ", ".join(miss)
            elif gate(p):
                label, detail = gate(p)
                lamp = ("idle", label)
            elif p.get("local"):
                try:
                    local = p["local"](store) or {}
                except Exception as e:
                    local = _not_asked("The app's own record could not be read (%s)." % type(e).__name__)
                lamp = _lamp(local) or ("idle", "No live check")
                detail = local.get("detail") or ""
            elif p.get("check") is None:
                lamp, detail = ("idle", "No live check"), p.get("no_check") or ""
            elif prev is None:
                lamp = ("idle", "Not checked yet")
                detail = "Nothing has been asked yet. Its button asks it once."
            else:
                lamp = _lamp(prev) or ("idle", prev.get("label") or "Not asked")
                shown = prev
            group.append({
                "key": p["key"], "name": p["name"], "powers": p["powers"],
                "built": built,
                "env": [_chip(p, n, pending=bool(pend) and n in miss)
                        for n in p.get("env", ())] if built else [],
                "flags": [{"name": f, "on": _truthy(os.environ.get(f))} for f in p.get("flags", ())],
                "any_of": [[_chip(p, n) for n in g] for g in (p.get("any_of") or ())],
                "optional": [_chip(p, n) for n in p.get("optional", ())],
                "missing": miss, "last": shown, "lamp": lamp,
                "detail": scrub(detail, p, forms=forms) if detail else "",
                "cost": p.get("cost") or "", "cost_kind": p.get("cost_kind") or "",
                "auto": bool(p.get("auto")),
                "can_check": bool(built and p.get("check") is not None and not miss and not gate(p)),
                "has_check": p.get("check") is not None,
                "where": p.get("where") or "", "note": p.get("note") or "",
            })
        if group:
            out.append({"key": fam_key, "name": fam_name, "providers": group})
    return out

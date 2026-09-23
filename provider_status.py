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
import threading
import time
import urllib.error
import urllib.parse
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


def _words(raw, limit=240):
    """What a vendor said in an error body, in its own words, shortened."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    if isinstance(raw, (dict, list)):
        return _from_doc(raw)[:limit]
    text = str(raw or "").strip()
    if text[:1] in ("{", "["):
        try:
            return _from_doc(json.loads(text))[:limit]
        except ValueError:
            pass
    text = re.sub(r"<[^>]+>", " ", text)            # an HTML error page
    return " ".join(text.split())[:limit]


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


# ---- the checks: music data and rights ------------------------------------------

def _check_mlc():
    """Sign-in alone is not proof (2026-09-08: sign-in worked while search
    answered 401), so this searches by a known ISRC through the process's
    own adapter. A 200 list and a 204 both mean it works."""
    import signal_providers as sp
    try:
        found = sp.mlc_adapter().find_recordings(isrc=KNOWN_ISRC)
    except sp.ProviderError as e:
        return _fail(str(e))
    n = len(found or [])
    if n:
        return _ok("Signed in and searched by ISRC: The MLC answered with %s." % _plural(n, "recording"))
    return _ok("Signed in and searched by ISRC: The MLC answered that it holds no recording "
               "for the test ISRC, which is still an answer.")


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
        return _fail(str(e))
    if not isinstance(body, dict):
        return _malformed("Soundcharts")
    month = soundcharts_budget.summary()
    return _ok("Answered an artist search. That was 1 paid call: {:,} of this month's {:,} are used."
               .format(month["total"], month["budget"]))


def _check_songstats():
    import signal_providers as sp
    result = sp.SongstatsAdapter().probe()
    if result.get("ok"):
        result = dict(result, detail="%s That spent 1 of Songstats' 1,000 calls this month."
                      % result.get("detail", "Answered."))
    return result


def _check_discogs():
    """Discogs' own who-am-I, below the adapter's six-hour cache, through
    the process's one adapter so its rate window stays in one place."""
    import signal_providers as sp
    adapter = sp.discogs_adapter()
    try:
        status, headers, body = adapter._send("/oauth/identity", {})
    except sp.ProviderError as e:
        return _fail(str(e))
    adapter._read_limits(headers)
    if status != 200:
        return _refused("Discogs", status, adapter._message(status, body))
    if not isinstance(body, dict):
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
        return _fail(sp.YouTubeAdapter.redact(str(e)))
    if not isinstance(body, dict):
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
    if "_raw" in answer or not isinstance(answer.get("data", []), list):
        return _malformed("The ACRCloud console")
    return _ok("The console token works: it can read the account's buckets.")


def _check_musicbrainz():
    import signal_providers as sp
    return sp.MusicBrainzAdapter().probe()


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
    if not isinstance(doc, dict):
        return _malformed("Google Places")
    n = len(doc.get("places") or [])
    return _ok("Places (New) answered a text search (%s)." % _plural(n, "place"))


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
        status_word = ""
        try:
            status_word = str((json.loads(raw.decode("utf-8", "replace")).get("error") or {}).get("status") or "")
        except Exception:
            pass
        if code == 403 and status_word == "PERMISSION_DENIED":
            return _not_asked("Not enabled on this Google project: Google refused the Routes API "
                              "with PERMISSION_DENIED (%s). The route page draws straight lines "
                              "until Routes is switched on in the Cloud console." % (words or "no message"))
        return _refused("Google Routes", code, words)
    except Exception as e:
        return _from_exception("Google Routes", e)
    doc, bad = _json_doc(body, "Google Routes")
    if bad:
        return bad
    if not isinstance(doc, dict):
        return _malformed("Google Routes")
    return _ok("Routes answered: drives between dates are measured, not drawn as straight lines.")


# ---- money, shop and mail ------------------------------------------------------------

def _stripe_secret_state():
    """The webhook signing secret: an env value, or the per-mode one the
    in-app setup stored. Either verifies a delivery."""
    try:
        import stripe_provider
        if _env("STRIPE_WEBHOOK_SECRET"):
            return True
        return "app" if stripe_provider.webhook_configured() else False
    except Exception:
        return bool(_env("STRIPE_WEBHOOK_SECRET"))


def _check_stripe():
    """A read of the webhook endpoints, through the GET seam only. Never
    setup_webhook_endpoint(): after the same read it POSTs changes."""
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
    ours = [ep for ep in endpoints if isinstance(ep, dict)
            and str(ep.get("url") or "").rstrip("/").endswith("/webhooks/stripe")]
    base = _env("PUBLIC_BASE_URL").rstrip("/")
    if base:
        ours = [ep for ep in ours if ep.get("url") == base + "/webhooks/stripe"] or ours
    held = bool(_stripe_secret_state())
    head = "The %s-mode key works." % mode
    if not ours:
        return _ok("%s No webhook endpoint in this mode points at /webhooks/stripe (%s on the "
                   "account); a checkout is still claimed when the buyer comes back to the app."
                   % (head, _plural(len(endpoints), "endpoint")))
    ep = ours[0]
    if ep.get("status") != "enabled":
        return _fail("%s But Stripe has the webhook endpoint %s, so plan changes, renewals and "
                     "refunds do not reach the app. Billing's one-click webhook setup switches it "
                     "back on." % (head, ep.get("status") or "switched off"))
    events = set(ep.get("enabled_events") or [])
    current = "*" in events or set(stripe.WEBHOOK_EVENTS) <= events
    return _ok("%s The webhook endpoint is enabled%s%s." % (
        head, "" if current else ", but it is missing events the app listens for",
        "" if held else ", and the app holds no signing secret for it, so deliveries are refused"))


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


def _check_shopify_admin():
    """{ shop { name } } with the Admin token: about one point of Shopify's
    cost bucket. The grant is asked only when the kept 24-hour token has
    lapsed. Never the Storefront mint, and never forget_grant(), which would
    drop the Buy Buttons' token with it."""
    import shopify_customers as sc
    admin = sc.token()
    if not admin:
        err = sc.grant_error() or {}
        return _fail("Shopify refused the app's credentials: the client credentials grant answered %s%s."
                     % (err.get("status") or "nothing", (": " + err["why"]) if err.get("why") else ""))
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
    tidy = "" if report.get("cleaned_up", True) else " The test object could not be deleted."
    if report.get("ok"):
        return _ok("Wrote a test object, read it back through a signed link and deleted it: %s.%s"
                   % (verdict, tidy))
    return _fail("The R2 round trip failed at the %s step: %s.%s"
                 % (report.get("step") or "read", verdict, tidy))


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
        "Stripe: %s" % ({True: "secret set", "app": "secret held by the app (set up in-app)"}
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
        return _fail("%s: %s" % (type(e).__name__, str(e)[:200]))
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


def _check_stemsplit():
    """The free balance read - one path, not the five probe() walks."""
    import stemsplit_provider as ss
    data, err = ss._call("GET", "/balance")
    if err:
        text = str(err)
        found = re.search(r"\(HTTP (\d{3})\)\s*$", text)
        status = int(found.group(1)) if found else None
        if status == 403 and "1010" in text:
            return _fail("Cloudflare's firewall in front of StemSplit refused the request (error "
                         "1010) before StemSplit read the key.")
        if status == 404:
            return _fail("StemSplit answered 404 for /balance: the path is wrong, not the key.")
        if status:
            return _refused("StemSplit", status, text[:found.start()].strip())
        if re.search(r"Expecting value|JSON|Unterminated|Extra data", text):
            return _malformed("StemSplit")
        if "timed out" in text.lower():
            return _fail("StemSplit did not answer in time.")
        return _fail("StemSplit could not be reached: %s" % text)
    if not isinstance(data, dict):
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
#              environment (True, "app" = held by the app, or False)
#   sandboxed  the app's own configured() is False on a SANDBOX deployment
#   gate       callable -> None, or (label, detail): not asked, by ruling
#   check      callable -> {"ok", "detail"}; None when no safe check exists
#   no_check   what the row says when there is no check
#   local      callable(store) -> a result read from what the app already
#              keeps (no network), shown on a page view
#   fixed      (label, detail) for a row whose state is a known fact
#   auto       part of "Check all": free, read-only, writes nothing
#   cost, cost_kind ("billed", "quota", "writes"), timeout, min_interval_s

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
         cost="Spends 1 paid call from the plan's monthly quota, counted in the Soundcharts "
              "budget. Refused unasked when the month's allowance is spent."),
    dict(key="songstats", name="Songstats", family="music", where="/royalties",
         powers="Which stores carry an ISRC, for the store coverage check on Royalties and Statements.",
         env=("SONGSTATS_API_KEY",), flags=("SONGSTATS_ENABLED",),
         check=_check_songstats, auto=False, cost_kind="quota",
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
         check=_check_places, auto=False, cost_kind="billed", cost=_GOOGLE_BILLED),
    dict(key="google_geocoding", name="Google Geocoding", family="touring", where="/tours",
         powers="Fetch coordinates on the tour home: a venue's map pin and its matched address.",
         env=("GOOGLE_MAPS_API_KEY",), sandboxed=True,
         check=_check_geocoding, auto=False, cost_kind="billed", cost=_GOOGLE_BILLED),
    dict(key="google_timezone", name="Google Time Zone", family="touring", where="/tours",
         powers="Each venue's time zone, which the day sheet, My Day and the calendar file print.",
         env=("GOOGLE_MAPS_API_KEY",), sandboxed=True,
         check=_check_timezone, auto=False, cost_kind="billed", cost=_GOOGLE_BILLED),
    dict(key="google_routes", name="Google Routes", family="touring", where="/tours",
         powers="Measured drives between dates on the route map, and the late-for-load-in flag.",
         env=("GOOGLE_MAPS_API_KEY",), sandboxed=True,
         note="Not enabled on the owner's Google project (2026-09-09), so the route page draws "
              "straight lines. Nothing is asked until you press the button.",
         check=_check_routes, auto=False, cost_kind="billed",
         cost="Billed by Google above the free monthly cap once enabled; a refused call is not billed."),

    # -- money, shop and mail --
    dict(key="stripe", name="Stripe", family="money", where="/billing",
         powers="Memberships, fan-club subscriptions, VIP tickets and Release-Ready masters.",
         env=("STRIPE_SECRET_KEY",), optional=("STRIPE_WEBHOOK_SECRET",),
         present={"STRIPE_WEBHOOK_SECRET": _stripe_secret_state}, sandboxed=True,
         check=_check_stripe, auto=True,
         cost="Free: a read of the webhook endpoints. Nothing is changed."),
    dict(key="shopify_buy", name="Shopify Buy Buttons", family="money", where="/apparel",
         powers="The store embed on Apparel and the merch shelf on the owner's EPK.",
         env=("SHOPIFY_DOMAIN", "SHOPIFY_COLLECTION_ID", "SHOPIFY_STOREFRONT_TOKEN"),
         present={"SHOPIFY_STOREFRONT_TOKEN": _storefront_token_state},
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
         check=_check_r2, auto=False, cost_kind="writes", timeout=45,
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
    dict(key="deezer", name="Deezer", family="lookups", where="/catalog/add",
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

def _all_names():
    names = set()
    for q in PROVIDERS:
        names.update(q.get("env", ()))
        names.update(q.get("optional", ()))
        for g in q.get("any_of") or ():
            names.update(g)
    return names


def _secret_forms():
    """Every configured value (not the on/off switches), in the spellings a
    value can take on its way out: as typed, URL-encoded, JSON-escaped."""
    out = set()
    for n in _all_names():
        v = _env(n)
        if len(v) < 6:
            continue
        out.add(v)
        out.add(urllib.parse.quote(v, safe=""))
        out.add(urllib.parse.quote_plus(v))
        out.add(json.dumps(v)[1:-1])
    return out


def scrub(text, p=None, limit=400):
    """The words of a result with every configured value blanked - every
    provider's, whichever row the words belong to, since one vendor may
    quote a header another's key rode in - and anything shaped like a bearer
    token or a key parameter cut out. Shortened for the page."""
    text = str(text or "")
    for v in sorted(_secret_forms(), key=len, reverse=True):
        if v:
            text = text.replace(v, "[hidden]")
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

def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run(p, timeout=None):
    """Run one provider's check under a hard time limit. Returns
    {ok, detail, ms, at}. Never raises, and calls nobody unless the service
    is configured, not gated and has a safe check."""
    timeout = timeout if timeout is not None else p.get("timeout", CHECK_TIMEOUT_S)
    started = time.monotonic()
    if p.get("fixed"):
        return {"ok": None, "detail": p["fixed"][1], "ms": 0, "at": _now_iso()}
    if p.get("check") is None:
        return {"ok": None, "detail": p.get("no_check") or
                "No safe live check exists for this service; only its keys are read.",
                "ms": 0, "at": _now_iso()}
    miss = missing(p)
    if miss:
        return {"ok": None, "detail": "Not configured: set %s. Nothing was asked." % ", ".join(miss),
                "ms": 0, "at": _now_iso()}
    ruled = gate(p)
    if ruled:
        return {"ok": None, "detail": ruled[1], "ms": 0, "at": _now_iso()}
    box = {}

    def work():
        try:
            box["r"] = p["check"]() or {}
        except Exception as e:                      # the service's own words
            box["r"] = {"ok": False, "detail": "%s: %s" % (type(e).__name__, e)}

    t = threading.Thread(target=work, daemon=True, name="provider-check-%s" % p["key"])
    t.start()
    t.join(timeout)
    ms = int((time.monotonic() - started) * 1000)
    if t.is_alive():
        return {"ok": False, "detail": "No answer within %d seconds." % timeout, "ms": ms, "at": _now_iso()}
    r = box.get("r") or {}
    ok = r.get("ok")
    return {"ok": ok if ok in (True, False) else None,
            "detail": scrub(r.get("detail") or ("Answered." if ok else "No detail given."), p),
            "ms": ms, "at": _now_iso()}


def save(key, result, store):
    store.set_kv(KV_PREFIX + key, json.dumps(result))


def last(key, store):
    try:
        raw = store.get_kv(KV_PREFIX + key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _too_soon(p, store):
    """A service with a tight shared limit is asked at most once per
    min_interval_s; inside it the last answer stands."""
    gap = p.get("min_interval_s")
    if not gap:
        return False
    prev = last(p["key"], store)
    if not prev or prev.get("ok") is None:
        return False
    try:
        at = datetime.fromisoformat(prev["at"])
    except Exception:
        return False
    return (datetime.now(timezone.utc) - at).total_seconds() < gap


def check(key, store):
    """Run and remember one provider's check."""
    p = by_key(key)
    if p is None:
        return None
    if _too_soon(p, store):
        return last(key, store)
    result = run(p)
    save(key, result, store)
    return result


def auto_keys():
    """The free, read-only checks "Check all" runs."""
    return [p["key"] for p in PROVIDERS if p.get("auto")]


def check_all(store):
    """Every provider whose check is free, together, each under its own time
    limit. The ones that spend money or a scarce quota, or write anything,
    are left for their own button; the ones not configured or gated are
    recorded as such without calling anyone."""
    todo = [p for p in PROVIDERS if p.get("auto") and not _too_soon(p, store)]
    if not todo:
        return {}
    with ThreadPoolExecutor(max_workers=len(todo)) as pool:
        results = dict(zip([p["key"] for p in todo], pool.map(run, todo)))
    for key, result in results.items():
        save(key, result, store)
    return results


# ---- what the page shows ----------------------------------------------------------------

def _chip(p, name):
    state = _is_set(p, name)
    return {"name": name, "set": state is True, "app": state == "app"}


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
    out = []
    for fam_key, fam_name in FAMILIES:
        group = []
        for p in PROVIDERS:
            if p["family"] != fam_key:
                continue
            built = p.get("built", True)
            miss = missing(p) if built else []
            prev = last(p["key"], store)
            detail, shown = "", None
            if p.get("fixed"):
                lamp, detail = ("idle", p["fixed"][0]), p["fixed"][1]
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
                lamp = _lamp(prev) or ("idle", "Not asked")
                shown = prev
            group.append({
                "key": p["key"], "name": p["name"], "powers": p["powers"],
                "built": built,
                "env": [_chip(p, n) for n in p.get("env", ())] if built else [],
                "flags": [{"name": f, "on": _truthy(os.environ.get(f))} for f in p.get("flags", ())],
                "any_of": [[_chip(p, n) for n in g] for g in (p.get("any_of") or ())],
                "optional": [_chip(p, n) for n in p.get("optional", ())],
                "missing": miss, "last": shown, "lamp": lamp,
                "detail": scrub(detail, p) if detail else "",
                "cost": p.get("cost") or "", "cost_kind": p.get("cost_kind") or "",
                "auto": bool(p.get("auto")),
                "can_check": bool(built and p.get("check") is not None and not miss and not gate(p)),
                "has_check": p.get("check") is not None,
                "where": p.get("where") or "", "note": p.get("note") or "",
            })
        if group:
            out.append({"key": fam_key, "name": fam_name, "providers": group})
    return out

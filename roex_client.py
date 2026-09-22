"""RoEx Tonn: the only module in the app that talks to RoEx.

Release-Ready (Creative Studio) sends an artist's mix to RoEx for a mix
report, 30-second mastering previews, a vocal-plus-beat recombine, and the
full master once the artist has paid. Every one of those requests leaves
through this file and through ONE function, `_http`, which the tests
replace. RoEx's output files (previews and masters on signed links that
expire in 24 hours) come back through a second function, `_download`, which
the tests replace too. Nothing else here opens a socket.

WHAT THE SPEC SAYS, AND WHERE IT DIFFERS FROM THE BRIEF
-------------------------------------------------------
Read from RoEx's own Swagger 2.0 spec (host tonn.roexaudio.com) on
2026-09-19. Field names below are the spec's, exactly.

  There is no /retrieve. A full master comes from /retrievefinalmaster; a
  vocal-plus-beat master comes from /retrieverecombine.
  /mixanalysis is synchronous (up to the gateway's 300 s deadline), takes
  no webhook and returns no score: labelled verdicts and a few measured
  figures. Callers run it in a background thread, never in a request.
  There is no status endpoint for mastering: /retrievepreviewmaster is
  polled, and HTTP 202 (or a body of {"status": 202}) means still working.
  /retrievefinalmaster is documented to return a string, while RoEx's own
  client reads an object with download_url_mastered, nested or at the top
  level. All three are accepted. A body "status" never overrides HTTP 200
  on that endpoint: the paid call is never read as "ask again".
  /retrieverecombine charges 250 credits on the first successful call only
  and is documented as safe to repeat. Nothing is documented about a
  repeat /retrievefinalmaster, so callers never repeat it on their own.
  Webhooks are unsigned and their body is undocumented. Callers treat a
  delivery as a nudge and read the task again from here.
  No endpoint reports the credit balance, and 402 is documented only on
  /retrieverecombine. Any 402, or a 200 carrying error:true with "credit"
  in the message, is read as the account being short of credits.
  A bad key is documented as HTTP 400 ("No input provided or invalid API
  key"), and the Google Cloud Endpoints gateway in front of RoEx answers
  "API key not valid". A 400 that names the API key is read as "auth",
  like a 401 or a 403.

THE KEY
-------
ROEX_API_KEY is read from the environment, here and nowhere else. It is
sent as the X-API-Key header only; the spec also allows ?key=, which would
put it into URLs and from there into logs, so that form is never used.
_http never follows a redirect (urllib would carry the header on to the
new host), so a 3xx is an answer, not a second request. _download follows
a redirect only to another public https address.
Every message that could reach a log, a page or a JSON body goes through
_scrub(), which removes the key and any URL query string (our own signed
R2 links carry a signature in theirs).

STEM SEPARATION IS NOT HERE ON PURPOSE
--------------------------------------
/separate, /retrievestems and /upload exist in RoEx's API. Separation was
ruled out on rights grounds, and RoEx's /upload is not needed because
RoEx fetches our own presigned links. ENDPOINTS is an allowlist, and
_http refuses anything outside it.

RATE
----
RoEx publishes 100 requests a minute per key. Every request here first
takes a slot from a sliding-window counter kept in SQLite (table
roex_rate), so both gunicorn workers and every thread share one count,
capped at RATE_LIMIT, a little under RoEx's figure. A refused slot is not
a request: nothing leaves, and the caller gets Outcome("busy").
"""
import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import db
import sandbox

log = logging.getLogger("roex_client")

BASE = "https://tonn.roexaudio.com"
KEY_ENV = "ROEX_API_KEY"

# RoEx's published limit is 100 a minute per key; this leaves a margin.
RATE_LIMIT = 90

# Every path this module may call. Nothing else leaves.
ENDPOINTS = (
    "/mixanalysis",
    "/masteringpreview",
    "/retrievepreviewmaster",
    "/retrievefinalmaster",
    "/recombine",
    "/recombinestatus/",          # + the task id
    "/retrieverecombinepreview",
    "/retrieverecombine",
    "/health",
)
_FORBIDDEN = ("/separate", "/retrievestems", "/upload")

# RoEx's price list in credits (pricing page and API Terms Exhibit A;
# recombine from the spec). Our own ledger uses these as estimates: no
# endpoint reports what was actually charged.
CREDITS = {"mix_analysis": 10, "master_final": 220, "recombine_final": 250, "preview": 0}

# Output files. A 10-minute 44.1 kHz 16-bit stereo WAV is about 106 MB.
MAX_MASTER_BYTES = 160 * 1024 * 1024
MAX_PREVIEW_BYTES = 20 * 1024 * 1024

MIX_ANALYSIS_TIMEOUT = 310        # the gateway cuts off at 300 s
FINAL_TIMEOUT = 310
DEFAULT_TIMEOUT = 30


# --- styles and loudness ----------------------------------------------------
# The spec's enums, each with the words an artist reads. Mix analysis uses
# its own list (DANCE left out: RoEx's own client dropped it to match the
# server); mastering and recombine have theirs.

ANALYSIS_STYLES = (
    ("POP", "Pop"), ("HIP_HOP_GRIME", "Hip-hop / grime"), ("TRAP", "Trap"),
    ("RNB", "R&B"), ("SOUL", "Soul"), ("FUNK", "Funk"), ("AFROBEAT", "Afrobeat"),
    ("LATIN", "Latin"), ("REGGAE", "Reggae"), ("ELECTRONIC", "Electronic"),
    ("HOUSE", "House"), ("TECHNO", "Techno"), ("TRANCE", "Trance"),
    ("DRUM_N_BASS", "Drum and bass"), ("LO_FI", "Lo-fi"), ("AMBIENT", "Ambient"),
    ("ROCK", "Rock"), ("INDIE_ROCK", "Indie rock"), ("INDIE_POP", "Indie pop"),
    ("PUNK", "Punk"), ("METAL", "Metal"), ("BLUES", "Blues"), ("JAZZ", "Jazz"),
    ("COUNTRY", "Country"), ("FOLK", "Folk"), ("ACOUSTIC", "Acoustic"),
    ("ORCHESTRAL", "Orchestral"), ("INSTRUMENTAL", "Instrumental"),
    ("EXPERIMENTAL", "Experimental"),
)

MASTER_STYLES = (
    ("POP", "Pop"), ("HIPHOP_GRIME", "Hip-hop / grime"), ("ELECTRONIC", "Electronic"),
    ("ROCK_INDIE", "Rock / indie"), ("ACOUSTIC", "Acoustic"),
    ("REGGAE_DUB", "Reggae / dub"), ("METAL", "Metal"), ("OTHER", "Something else"),
)

RECOMBINE_STYLES = (
    ("POP", "Pop"), ("HIPHOP_GRIME", "Hip-hop / grime"), ("TRAP", "Trap"),
    ("AFROBEAT", "Afrobeat"), ("REGGAETON", "Reggaeton"), ("LATIN", "Latin"),
    ("K_POP", "K-pop"), ("ELECTRONIC", "Electronic"), ("HOUSE", "House"),
    ("TECHNO", "Techno"), ("LO_FI", "Lo-fi"), ("ROCK_INDIE", "Rock / indie"),
    ("METAL", "Metal"), ("ACOUSTIC", "Acoustic"), ("COUNTRY_ACOUSTIC", "Country / acoustic"),
    ("JAZZ", "Jazz"), ("REGGAE_DUB", "Reggae / dub"), ("ORCHESTRAL", "Orchestral"),
    ("CINEMATIC", "Cinematic"), ("OTHER", "Something else"),
)

# A preset, not a LUFS target: the spec and RoEx's FAQ give different
# figures for each, so no figure is ever shown for a preset.
LOUDNESS = (("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"))

SAMPLE_RATES = ("44100", "48000")

# What the preview form starts on, from the genre picked at upload. The
# artist can always change it.
DEFAULT_MASTER_STYLE_FOR = {
    "POP": "POP", "INDIE_POP": "POP", "RNB": "POP", "SOUL": "POP", "FUNK": "POP",
    "LATIN": "POP", "AFROBEAT": "POP",
    "HIP_HOP_GRIME": "HIPHOP_GRIME", "TRAP": "HIPHOP_GRIME",
    "ELECTRONIC": "ELECTRONIC", "HOUSE": "ELECTRONIC", "TECHNO": "ELECTRONIC",
    "TRANCE": "ELECTRONIC", "DRUM_N_BASS": "ELECTRONIC", "AMBIENT": "ELECTRONIC",
    "ROCK": "ROCK_INDIE", "INDIE_ROCK": "ROCK_INDIE", "PUNK": "ROCK_INDIE",
    "ACOUSTIC": "ACOUSTIC", "FOLK": "ACOUSTIC", "COUNTRY": "ACOUSTIC", "BLUES": "ACOUSTIC",
    "REGGAE": "REGGAE_DUB", "METAL": "METAL",
}

DEFAULT_RECOMBINE_STYLE_FOR = {
    "POP": "POP", "INDIE_POP": "POP", "RNB": "POP", "SOUL": "POP", "FUNK": "POP",
    "HIP_HOP_GRIME": "HIPHOP_GRIME", "TRAP": "TRAP", "AFROBEAT": "AFROBEAT",
    "LATIN": "LATIN", "ELECTRONIC": "ELECTRONIC", "HOUSE": "HOUSE", "TECHNO": "TECHNO",
    "TRANCE": "ELECTRONIC", "DRUM_N_BASS": "ELECTRONIC", "LO_FI": "LO_FI",
    "ROCK": "ROCK_INDIE", "INDIE_ROCK": "ROCK_INDIE", "PUNK": "ROCK_INDIE",
    "METAL": "METAL", "ACOUSTIC": "ACOUSTIC", "FOLK": "ACOUSTIC",
    "COUNTRY": "COUNTRY_ACOUSTIC", "JAZZ": "JAZZ", "REGGAE": "REGGAE_DUB",
    "ORCHESTRAL": "ORCHESTRAL",
}


def codes(table):
    return tuple(code for code, _label in table)


def label_for(table, code):
    return dict(table).get(code, code or "")


def default_master_style(analysis_style):
    return DEFAULT_MASTER_STYLE_FOR.get(analysis_style or "", "OTHER")


def default_recombine_style(analysis_style):
    return DEFAULT_RECOMBINE_STYLE_FOR.get(analysis_style or "", "OTHER")


# --- configuration ------------------------------------------------------------

def _key():
    return (os.environ.get("ROEX_API_KEY") or "").strip()


def configured():
    """True when a key is set. A key is not a capability: this proves a
    value was typed, not that RoEx accepts it or that credits are left.
    A sandbox deployment never spends the owner's credits."""
    if sandbox.active():
        return False
    return bool(_key())


# --- outcomes ---------------------------------------------------------------------

class RoexBusy(Exception):
    """Our own limiter refused the slot. Nothing was sent."""


class RoexDownloadError(Exception):
    """An output file could not be fetched. The message never holds the URL."""


# The kinds an Outcome can have, and what each means for a caller:
#   ok              RoEx answered and the answer is usable
#   pending         still working (HTTP 202 or {"status": 202})
#   not_configured  no key: nothing was sent
#   busy            our limiter (nothing sent) or RoEx's 429/503
#   auth            401/403: the key was refused
#   credits         402, or error:true mentioning credits
#   not_found       404
#   bad_request     400, or a request refused here before sending
#   failed          RoEx processed it and said it failed
#   server_error    500 or another 5xx
#   unavailable     the connection failed before a request was sent
#   unknown         sent, and no answer came back (a timeout)
KINDS = ("ok", "pending", "not_configured", "busy", "auth", "credits", "not_found",
         "bad_request", "failed", "server_error", "unavailable", "unknown")


class Outcome:
    """What one call came to. roex_message is only ever RoEx's own words
    (an artist may read it, quoted as RoEx's). note is ours, for the
    owner's desk, when RoEx's answer lacked something we needed."""
    __slots__ = ("kind", "data", "roex_message", "status", "sent", "note")

    def __init__(self, kind, data=None, roex_message="", status=None, sent=True, note=""):
        self.kind = kind
        self.data = data if data is not None else {}
        self.roex_message = _scrub(roex_message or "")
        self.status = status
        self.sent = sent            # False: nothing left this process
        self.note = _scrub(note or "")

    @property
    def ok(self):
        return self.kind == "ok"

    def __repr__(self):
        return "Outcome(%s, status=%s)" % (self.kind, self.status)


_URL_QUERY = re.compile(r"(https?://[^\s?\"'<>]+)\?[^\s\"'<>]*")


def _scrub(text):
    """RoEx's own words, safe to keep: the key removed, any URL's query
    string removed, trimmed to 300 characters."""
    text = str(text or "")
    key = _key()
    if key:
        text = text.replace(key, "[key]")
    text = _URL_QUERY.sub(r"\1", text)
    return text.strip()[:300]


def _message(payload):
    if isinstance(payload, dict):
        for field in ("info", "message", "error_message"):
            val = payload.get(field)
            if isinstance(val, str) and val.strip():
                return val
        return ""
    if isinstance(payload, str):
        return payload
    return ""


def allowed_path(path):
    if not isinstance(path, str) or not path.startswith("/"):
        return False
    low = path.lower()
    if any(low.startswith(f) for f in _FORBIDDEN):
        return False
    if path.startswith("/recombinestatus/"):
        return len(path) > len("/recombinestatus/")
    return path in ENDPOINTS


# --- the one door -------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """RoEx's API has no reason to redirect, and urllib would send the
    X-API-Key header on to wherever a redirect points (and to http:// as
    readily as https://). Returning None makes the 3xx itself the answer:
    an HTTPError that the caller classifies."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _api_opener():
    """The opener every RoEx request goes through: redirects never followed."""
    return urllib.request.build_opener(_NoRedirect())


def _http(method, path, body=None, timeout=DEFAULT_TIMEOUT):
    """Send one request to RoEx and return (status, parsed body).

    Tests replace this function. It raises urllib.error.URLError when the
    connection fails and TimeoutError when the answer never comes; the
    caller turns both into an Outcome without ever printing the request.
    A redirect is never followed, so the key goes to RoEx's host only.
    """
    if not allowed_path(path):
        raise ValueError("not a RoEx endpoint this app calls")
    headers = {"X-API-Key": _key(), "Accept": "application/json",
               "User-Agent": "StreetBanker-ReleaseReady/1"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with _api_opener().open(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read(4_000_000)
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            raw = exc.read(200_000)
        except Exception:
            raw = b""
    return status, _parse(raw)


def _parse(raw):
    text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else (raw or "")
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return text


def _public_https(url):
    """True for an https link whose host is a public address. A private,
    loopback, link-local or otherwise non-global address is refused, so a
    link (or a redirect) cannot point this server at its own network."""
    parts = urllib.parse.urlsplit(url or "")
    if parts.scheme != "https" or not parts.hostname:
        return False
    host = parts.hostname
    try:
        addrs = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
        except (OSError, UnicodeError, ValueError):
            return False
        addrs = []
        for info in infos:
            try:
                addrs.append(ipaddress.ip_address(str(info[4][0]).split("%")[0]))
            except ValueError:
                return False
    return bool(addrs) and all(a.is_global for a in addrs)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """A file link may redirect (a storage CDN does), but only to another
    public https address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _public_https(newurl):
            raise RoexDownloadError("RoEx's file link redirected somewhere it may not go")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download_opener():
    return urllib.request.build_opener(_SafeRedirect())


def _download(url, max_bytes=MAX_MASTER_BYTES, timeout=120):
    """Fetch one of RoEx's output files into a temp file: (path, bytes, sha256).

    The second and last seam; tests replace it. Only public https links
    are fetched, a redirect included, no key is sent, and nothing about the
    link is kept in an error, because the link is signed.
    """
    if urllib.parse.urlsplit(url or "").scheme != "https":
        raise RoexDownloadError("RoEx's file link was not https")
    if not _public_https(url):
        raise RoexDownloadError("RoEx's file link pointed at a private address")
    fd, path = tempfile.mkstemp(prefix="rr-", suffix=".part")
    h, n = hashlib.sha256(), 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StreetBanker-ReleaseReady/1"})
        with os.fdopen(fd, "wb") as out, _download_opener().open(req, timeout=timeout) as resp:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                n += len(chunk)
                if n > max_bytes:
                    raise RoexDownloadError("RoEx's file was larger than expected")
                h.update(chunk)
                out.write(chunk)
    except RoexDownloadError:
        _unlink(path)
        raise
    except urllib.error.HTTPError as exc:
        # The status is the whole diagnosis when RoEx has produced a file we
        # then cannot fetch: 403 says the link needs something we are not
        # sending, 404 that it is not there, 5xx that RoEx's file host is
        # down. "(HTTPError)" said none of that and sent me looking at our
        # size cap instead. The URL still never appears: it is signed.
        _unlink(path)
        raise RoexDownloadError(
            "RoEx's file link answered HTTP %s" % exc.code) from None
    except Exception as exc:
        _unlink(path)
        raise RoexDownloadError("RoEx's file could not be fetched (%s)" % type(exc).__name__) from None
    return path, n, h.hexdigest()


def _unlink(path):
    try:
        os.remove(path)
    except OSError:
        pass


# --- the rate limiter ---------------------------------------------------------------

_RATE_READY = False


def init():
    """The limiter's table. Called from release_ready_store.init()."""
    global _RATE_READY
    with db.get_db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS roex_rate ("
                     " minute TEXT PRIMARY KEY, n INTEGER NOT NULL)")
    _RATE_READY = True


def _now():
    return datetime.now(timezone.utc)


def _minute(t):
    return t.strftime("%Y-%m-%dT%H:%M")


def _rate_take(now=None):
    """Take one slot, or raise RoexBusy. One transaction: the increment,
    the read and, on refusal, the take-back, so two workers cannot both
    squeeze past the cap."""
    if not _RATE_READY:
        init()
    now = now or _now()
    cur_m, prev_m = _minute(now), _minute(now - timedelta(minutes=1))
    frac = (now.second + now.microsecond / 1e6) / 60.0
    with db.get_db() as conn:
        conn.execute("INSERT INTO roex_rate (minute, n) VALUES (?, 1) "
                     "ON CONFLICT(minute) DO UPDATE SET n = n + 1", (cur_m,))
        rows = dict(conn.execute("SELECT minute, n FROM roex_rate WHERE minute IN (?, ?)",
                                 (cur_m, prev_m)).fetchall())
        conn.execute("DELETE FROM roex_rate WHERE minute < ?",
                     (_minute(now - timedelta(hours=2)),))
        weighted = rows.get(cur_m, 0) + rows.get(prev_m, 0) * (1.0 - frac)
        if weighted > RATE_LIMIT:
            conn.execute("UPDATE roex_rate SET n = n - 1 WHERE minute = ?", (cur_m,))
            raise RoexBusy("RoEx rate limit reached on our side")


def rate_counts(now=None):
    """This minute and the one before, for the owner's desk."""
    if not _RATE_READY:
        init()
    now = now or _now()
    cur_m, prev_m = _minute(now), _minute(now - timedelta(minutes=1))
    with db.get_db() as conn:
        rows = dict(conn.execute("SELECT minute, n FROM roex_rate WHERE minute IN (?, ?)",
                                 (cur_m, prev_m)).fetchall())
    return {"this_minute": rows.get(cur_m, 0), "last_minute": rows.get(prev_m, 0),
            "limit": RATE_LIMIT}


# --- classification -----------------------------------------------------------

def _is_timeout(exc):
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, (TimeoutError, socket.timeout))


def _call(method, path, body=None, timeout=DEFAULT_TIMEOUT, body_status=True):
    """One request through the limiter and the seam. body_status=False: a
    "status" field in a 200 body is not read as "still working" (the paid
    /retrievefinalmaster, which is never repeated on a body's say-so)."""
    if not configured():
        return Outcome("not_configured", sent=False)
    if not allowed_path(path):
        return Outcome("bad_request", sent=False)
    try:
        _rate_take()
    except RoexBusy:
        return Outcome("busy", sent=False)
    except Exception:
        # The limiter could not be read (a locked or missing table). Not
        # knowing the count is not permission to send.
        log.warning("roex_client: rate limiter unavailable; request held back")
        return Outcome("busy", sent=False)
    try:
        status, payload = _http(method, path, body, timeout)
    except urllib.error.URLError as exc:
        # URLError is raised while connecting or sending. A timeout while
        # connecting is still "not sent"; one while reading is below.
        log.info("roex_client: %s %s could not connect (%s)", method, _path_for_log(path),
                 type(getattr(exc, "reason", exc)).__name__)
        return Outcome("unavailable", sent=False)
    except Exception as exc:
        if _is_timeout(exc):
            log.info("roex_client: %s %s timed out", method, _path_for_log(path))
        else:
            log.info("roex_client: %s %s failed (%s)", method, _path_for_log(path),
                     type(exc).__name__)
        return Outcome("unknown")
    return _classify(status, payload, body_status)


def _path_for_log(path):
    return "/recombinestatus/<task>" if path.startswith("/recombinestatus/") else path


def _classify(status, payload, body_status=True):
    msg = _message(payload)
    if status == 202 or (body_status and isinstance(payload, dict)
                         and payload.get("status") in (202, "202")):
        return Outcome("pending", payload if isinstance(payload, dict) else {}, msg, status)
    if status == 200:
        if isinstance(payload, dict) and payload.get("error") is True:
            kind = "credits" if "credit" in msg.lower() else "failed"
            return Outcome(kind, payload, msg, status)
        return Outcome("ok", payload if isinstance(payload, dict) else {"text": payload}, msg, status)
    if status in (401, 403):
        return Outcome("auth", {}, msg, status)
    if status == 402:
        return Outcome("credits", {}, msg, status)
    if status == 404:
        return Outcome("not_found", {}, msg, status)
    if status == 400:
        low = msg.lower()
        # The spec: 400 is "No input provided or invalid API key", and the
        # gateway says "API key not valid". A refused key is the owner's to
        # fix, never a problem with the artist's file.
        if "api key" in low or "api_key" in low or "apikey" in low:
            return Outcome("auth", {}, msg, status)
        kind = "credits" if "credit" in low else "bad_request"
        return Outcome(kind, {}, msg, status)
    if status in (429, 503):
        return Outcome("busy", {}, msg, status)
    if isinstance(status, int) and status >= 500:
        return Outcome("server_error", {}, msg, status)
    return Outcome("unknown", {}, msg, status)


# --- the endpoints --------------------------------------------------------------

def mix_analysis(audio_url, musical_style, is_master, timeout=MIX_ANALYSIS_TIMEOUT):
    """POST /mixanalysis. Synchronous. ok -> data is RoEx's payload."""
    if musical_style not in codes(ANALYSIS_STYLES):
        return Outcome("bad_request", sent=False)
    out = _call("POST", "/mixanalysis", {"mixDiagnosisData": {
        "audioFileLocation": audio_url,
        "musicalStyle": musical_style,
        "isMaster": bool(is_master)}}, timeout)
    if not out.ok:
        return out
    # The spec nests the report under mixDiagnosisResults; RoEx's own client
    # also reads payload / error / info straight off the top of the answer.
    results = out.data.get("mixDiagnosisResults")
    if not isinstance(results, dict):
        results = out.data
    if results.get("error") is True:
        msg = results.get("info") or out.roex_message
        kind = "credits" if "credit" in str(msg).lower() else "failed"
        return Outcome(kind, {}, msg, out.status)
    payload = results.get("payload")
    if not isinstance(payload, dict) or not payload:
        # Our words, not RoEx's: kept for the owner, never quoted to the artist.
        return Outcome("failed", {}, results.get("info") or "", out.status,
                       note="RoEx's answer carried no report")
    return Outcome("ok", payload, "", out.status)


def mastering_preview(track_url, musical_style, desired_loudness, sample_rate="44100",
                      preview_start=None, webhook=None):
    """POST /masteringpreview. ok -> data {"task_id"}. Every call is a new task."""
    if (musical_style not in codes(MASTER_STYLES) or desired_loudness not in codes(LOUDNESS)
            or str(sample_rate) not in SAMPLE_RATES):
        return Outcome("bad_request", sent=False)
    body = {"trackData": [{"trackURL": track_url}],
            "musicalStyle": musical_style,
            "desiredLoudness": desired_loudness,
            "sampleRate": str(sample_rate)}
    if preview_start is not None and float(preview_start) >= 0:
        body["previewStartTime"] = float(preview_start)
    if webhook:                     # never an empty string: RoEx 500s on it
        body["webhookURL"] = webhook
    out = _call("POST", "/masteringpreview", {"masteringData": body})
    if not out.ok:
        return out
    task = out.data.get("mastering_task_id")
    if not task:
        return Outcome("failed", {}, out.roex_message, out.status, note="RoEx sent no task id")
    return Outcome("ok", {"task_id": str(task)}, "", out.status)


def retrieve_preview_master(task_id):
    """POST /retrievepreviewmaster. ok -> data {"url", "start"}."""
    out = _call("POST", "/retrievepreviewmaster",
                {"masteringData": {"masteringTaskId": task_id}})
    if not out.ok:
        return out
    res = out.data.get("previewMasterTaskResults")
    url = res.get("download_url_mastered_preview") if isinstance(res, dict) else None
    if not url:
        # An answer with no link is usually "still working". It is also how
        # a refusal arrives - RoEx unable to download the source, say - and
        # the two are indistinguishable from the missing link alone. So keep
        # what the answer did carry (its field names, never their values)
        # and RoEx's own message, the way retrieve_final_master does. The
        # caller polls either way; without this, a preview RoEx will never
        # produce looks exactly like a slow one until the deadline, and the
        # reason is thrown away every time we ask.
        keys = sorted(str(k) for k in (res if isinstance(res, dict) else out.data))[:12]
        note = ""
        if keys:
            note = "RoEx sent no preview link (its answer had: %s)" % ", ".join(keys)
        return Outcome("pending", {"keys": keys}, out.roex_message, out.status, note=note)
    start = res.get("preview_start_time")
    try:
        start = float(start)
    except (TypeError, ValueError):
        start = None
    if start is not None and start < 0:
        start = None                # -1: not applicable
    return Outcome("ok", {"url": url, "start": start}, "", out.status)


def retrieve_final_master(task_id):
    """POST /retrievefinalmaster. Charges RoEx credits (220 per the price
    list). Never called twice for one task without an owner's say-so.
    ok -> data {"url"}."""
    # The full-length master may be rendered during this call, and the
    # gateway allows 300 s: a shorter wait would turn a slow success (and a
    # charge) into "no answer". Callers run it in a background thread.
    out = _call("POST", "/retrievefinalmaster",
                {"masteringData": {"masteringTaskId": task_id}}, timeout=FINAL_TIMEOUT,
                body_status=False)
    if not out.ok:
        return out
    res = out.data.get("finalMasterTaskResults")
    url = None
    if isinstance(res, str):
        url = res                                   # the spec's shape
    elif isinstance(res, dict):
        url = res.get("download_url_mastered")      # RoEx's client's shape
    if not url and isinstance(out.data.get("download_url_mastered"), str):
        url = out.data["download_url_mastered"]     # RoEx's client's fallback
    if not url or not isinstance(url, str):
        # An answer with no link: charged or not, we cannot tell. What the
        # answer did carry (its field names, never their values) is kept
        # for the owner, who decides what happens next.
        keys = sorted(str(k) for k in out.data)[:12]
        note = "RoEx sent no master link"
        if keys:
            note += " (its answer had: %s)" % ", ".join(keys)
        return Outcome("unknown", {"keys": keys}, out.roex_message, out.status, note=note)
    return Outcome("ok", {"url": url}, "", out.status)


def recombine(vocal_url, backing_url, musical_style, desired_loudness="MEDIUM",
              vocal_gain_db=0.0, webhook=None):
    """POST /recombine. Free to submit. ok -> data {"task_id"}."""
    if musical_style not in codes(RECOMBINE_STYLES) or desired_loudness not in codes(LOUDNESS):
        return Outcome("bad_request", sent=False)
    try:
        gain = float(vocal_gain_db)
    except (TypeError, ValueError):
        gain = 0.0
    gain = max(-6.0, min(6.0, gain))
    body = {"vocalStemURL": vocal_url, "backingStemURL": backing_url,
            "musicalStyle": musical_style, "desiredLoudness": desired_loudness,
            "vocalGainDb": gain}
    if webhook:
        body["webhookURL"] = webhook
    out = _call("POST", "/recombine", {"recombineData": body})
    if not out.ok:
        return out
    task = out.data.get("recombineTaskId")
    if not task:
        return Outcome("failed", {}, out.roex_message, out.status, note="RoEx sent no task id")
    return Outcome("ok", {"task_id": str(task)}, "", out.status)


def recombine_status(task_id):
    """GET /recombinestatus/<id>. ok -> complete; failed carries RoEx's info."""
    out = _call("GET", "/recombinestatus/" + urllib.parse.quote(str(task_id), safe=""))
    if not out.ok:
        return out
    status = str(out.data.get("status") or "").lower()
    if status == "complete":
        return Outcome("ok", {"status": "complete"}, "", out.status)
    if status == "failed":
        return Outcome("failed", {}, out.data.get("info") or out.roex_message, out.status)
    return Outcome("pending", {}, out.roex_message, out.status)


def retrieve_recombine_preview(task_id):
    """POST /retrieverecombinepreview. Free. ok -> data {"url", "start",
    "measured_lufs_full"}."""
    out = _call("POST", "/retrieverecombinepreview",
                {"recombineData": {"recombineTaskId": task_id}})
    if not out.ok:
        return out
    prev = out.data.get("preview")
    url = prev.get("preview_url") if isinstance(prev, dict) else None
    if not url:
        return Outcome("pending", {}, out.roex_message, out.status)
    return Outcome("ok", {"url": url,
                          "start": _num(prev.get("preview_start_seconds")),
                          "measured_lufs_full": _num(prev.get("measured_lufs_full"))},
                   "", out.status)


def retrieve_recombine(task_id):
    """POST /retrieverecombine. Charges 250 credits on the first successful
    call; repeats return the same link free. ok -> data {"url", ...RoEx's
    measured figures}."""
    out = _call("POST", "/retrieverecombine",
                {"recombineData": {"recombineTaskId": task_id}}, timeout=FINAL_TIMEOUT)
    if not out.ok:
        return out
    res = out.data.get("result")
    url = res.get("master_url") if isinstance(res, dict) else None
    if not url:
        return Outcome("pending", {}, out.roex_message, out.status)
    proc = res.get("processing") if isinstance(res.get("processing"), dict) else {}
    return Outcome("ok", {
        "url": url,
        "measured_lufs": _num(res.get("measured_lufs")),
        "peak_level": _num(res.get("peak_level")),
        "track_length_seconds": _num(res.get("track_length_seconds")),
        "sample_rate": _int(res.get("sample_rate")),
        "bit_depth": _int(res.get("bit_depth")),
        "channels": _int(res.get("channels")),
        "processing": {"musical_style": proc.get("musical_style"),
                       "desired_loudness": proc.get("desired_loudness"),
                       "vocal_gain_db": _num(proc.get("vocal_gain_db"))},
    }, "", out.status)


def health():
    """GET /health, through the limiter. ok means RoEx answered 200. A
    refused key comes back as "auth": a 401, a 403, or the 400 that names
    the API key (the spec's own wording for a bad key)."""
    return _call("GET", "/health", None, timeout=15)


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None           # NaN is not a measurement


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

"""ACRCloud's Console (Open) API - buckets, audio registration, file scanning.

This is the OTHER half of ACRCloud, and it is not the half `acr_provider.py`
talks to. That module signs a project access key with HMAC-SHA1 and asks
`/v1/identify` on an identify- host "what is this twelve seconds of audio".
This one carries a CONSOLE TOKEN and manages the account itself: the custom
buckets a rights holder puts their own masters into, and the file-scanning
containers that walk a long recording end to end. Two credentials, two hosts,
two jobs; neither can do the other's.

WHAT WAS VERIFIED, AND WHERE
----------------------------
Checked against docs.acrcloud.com (Console API section) on 2026-09-09. The
paths and field names below are quoted from those pages, not inferred:

  reference/console-api/buckets
  reference/console-api/buckets/audio-files
  reference/console-api/file-scanning
  reference/console-api/file-scanning/file-scanning      (the FsFiles resource)
  reference/console-api/file-scanning/metadata/music

HOST. Account-wide resources - the bucket list, the container list - answer on
`https://api-v2.acrcloud.com`. The resources that carry audio, a bucket's
files and a container's files, answer on the region host
`https://api-<region>.acrcloud.com`, where <region> is that bucket's or
container's own `region` field: eu-west-1, us-west-2 or ap-southeast-1.

AUTH. `Authorization: Bearer <token>` with `Accept: application/json`. The
token is minted in the ACRCloud console and carries scopes; this module needs
`read-buckets` to list buckets, `write-audios` to register a master, and
`read-filescanning` to read a scan. A token missing one of those answers 401
or 403, and that answer is kept verbatim - see `last_refusal()`.

BUCKETS.   GET /api/buckets
  query    page, per_page (default 20), region, type
           (File | Live | LiveRec | LiveTimeshift)
  answer   {"data": [{id, name, type, region, uid, state, labels, net_type,
           num, size}], "meta": {current_page, total, last_page}}

REGISTER AN AUDIO.   POST /api/buckets/:bucket_id/files   (multipart)
  fields   file          the audio, or a fingerprint file
           title         what the bucket lists it as
           data_type     audio | fingerprint | audio_url | acrid
           user_defined  a JSON object of your own metadata
           url           required when data_type is audio_url
           acrid         required when data_type is acrid
  answer   {"data": {id, acr_id, state, title, duration, user_defined,
           bucket_id, created_at, updated_at}}
  state    0 processing, 1 ready, -1 error

FILE SCANNING.
  containers   GET  /api/fs-containers          (list; also POST to create)
               fields on create: name, region, buckets[], and optionally
               audio_type, engine, policy, callback_url, music_detection,
               ai_detection
  add a file   POST /api/fs-containers/:container_id/files   (multipart)
               file       the recording (their ceiling is 500 MB)
               data_type  audio | fingerprint | platforms | audio_url | isrc
               url        required for audio_url and platforms
               name       optional; defaults to the file or URL path
  read it back GET /api/fs-containers/:container_id/files/:file_ids
  state        0 processing, 1 ready, -1 no result, -2 / -3 error

  THERE IS NO SEPARATE RESULTS ENDPOINT. The GET of one file carries the
  state, and carries the results with it once the state is 1. That is why
  `scan_state()` and `scan_results()` here read the same call rather than two -
  inventing a second URL would have been a guess.

  results  data.results.music[] of {offset, played_duration, type, result},
           and each `result` is {acrid, title, artists[].name, album.name,
           label, release_date, external_ids.isrc, external_metadata,
           db_begin_time_offset_ms, db_end_time_offset_ms,
           sample_begin_time_offset_ms, sample_end_time_offset_ms,
           play_offset_ms, score}. Only acrid, title, artists, album and the
           *_time_offset_ms fields are documented as always present.

A JOB ID IS A PAIR. Every scan read needs the container AND the file, so a
"job id" here is the string "<container_id>:<file_id>". One opaque token to
store and pass around, and it decomposes back into the two the URL wants.

WHAT THIS MODULE WILL NOT DO. It never creates a bucket or a container. The
page says which one to make and what to call it, and a person makes it in
their own console - a silently-created bucket is a billing decision this code
does not get to take. And no call happens at all unless the token is set:
`configured()` is false in the sandbox, and false with no token, and every
entry point checks it first.
"""

import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid

import sandbox

ACCOUNT_HOST = "api-v2.acrcloud.com"
REGIONS = ("eu-west-1", "us-west-2", "ap-southeast-1")
DEFAULT_REGION = "us-west-2"

# Their documented ceiling for a file-scanning upload.
MAX_SCAN_BYTES = 500 * 1024 * 1024
# What a master sent to a custom bucket may weigh. Far under their limit on
# purpose: this runs inside a web request on a two-worker deployment.
MAX_REGISTER_BYTES = 60 * 1024 * 1024

# Their processing states, for both a bucket audio and a scanned file. Only
# `ready` is named as a constant because it is the only one anything branches
# on; the rest are words for a person to read.
STATE_READY = 1

STATE_WORDS = {
    0: "processing",
    1: "ready",
    -1: "no result",
    -2: "error",
    -3: "error",
}

# Bounded, always. An unbounded "while there is a next page" against somebody
# else's API is an outage waiting for a bad `meta`.
PAGE_SIZE = 100
MAX_PAGES = 10

TIMEOUT_S = 30

_refusals = threading.local()


class AcrConsoleError(Exception):
    """A refusal, or a call that never landed. `status` is ACRCloud's HTTP
    code when there was one, and `msg` is ACRCloud's own words - this class
    never paraphrases the vendor."""

    def __init__(self, status, msg):
        Exception.__init__(self, "ACRCloud console %s: %s" % (status, msg))
        self.status = status
        self.msg = msg


def configured():
    """A token, and not a sandbox.

    The sandbox check is first-class rather than an afterthought: this token
    can write into the owner's real ACRCloud account, and a throwaway
    deployment must not be able to put test audio in a paid bucket.
    """
    if sandbox.active():
        return False
    return bool((os.environ.get("ACRCLOUD_CONSOLE_TOKEN") or "").strip())


def missing_env():
    """Which variable the page should name. Returns [] when nothing is
    missing, so a template can say what to set instead of "not configured"."""
    if sandbox.active():
        return []
    if (os.environ.get("ACRCLOUD_CONSOLE_TOKEN") or "").strip():
        return []
    return ["ACRCLOUD_CONSOLE_TOKEN"]


def default_region():
    """The region the identify host already names, so one setting serves both
    halves. ACRCLOUD_HOST is `identify-us-west-2.acrcloud.com`."""
    host = (os.environ.get("ACRCLOUD_HOST") or "").strip().lower()
    for region in REGIONS:
        if region in host:
            return region
    return DEFAULT_REGION


def region_host(region=None):
    region = (region or "").strip().lower()
    if region not in REGIONS:
        region = default_region()
    return "api-%s.acrcloud.com" % region


def last_refusal():
    """ACRCloud's own message from the last 401 / 403 / 429 on this thread,
    or None.

    Kept per-thread rather than per-process: two people pressing buttons at
    once must not read each other's refusal. It is a courtesy for the page,
    not a control flow - every caller already got the exception.
    """
    return getattr(_refusals, "last", None)


def _remember_refusal(status, msg):
    if status in (401, 403, 429):
        _refusals.last = {"status": status, "message": msg}


# --- the one seam -------------------------------------------------------------

def _http(method, url, headers=None, body=None, timeout=TIMEOUT_S):
    """The only place this module touches the network. Returns (status, dict).

    Injected wholesale in tests: every public function below takes `http=` and
    passes it down, so a test canning one dict covers the whole call path
    including the multipart body it would have sent.
    """
    request = urllib.request.Request(url, data=body, method=method,
                                     headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            return response.getcode(), _loads(raw)
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        return e.code, _loads(raw)
    except Exception as e:
        raise AcrConsoleError("network", str(e))


def _loads(raw):
    try:
        parsed = json.loads(raw or "{}")
    except ValueError:
        return {"_raw": (raw or "")[:400]}
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def _headers(extra=None):
    token = (os.environ.get("ACRCLOUD_CONSOLE_TOKEN") or "").strip()
    head = {"Authorization": "Bearer " + token,
            "Accept": "application/json",
            "User-Agent": "StreetBanker/1.0"}
    head.update(extra or {})
    return head


def _vendor_message(status, answer):
    """ACRCloud's words, whichever field they used for them.

    Their errors come back as `message`, sometimes with a per-field `errors`
    map beside it, and a plain `error` on some routes. Nothing here invents a
    sentence: with no message at all, the caller is told the status and that
    the body carried none, which is itself the truth.
    """
    answer = answer if isinstance(answer, dict) else {}
    for key in ("message", "error", "msg"):
        value = answer.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            break
        if isinstance(value, dict) and value.get("message"):
            text = str(value["message"]).strip()
            break
    else:
        text = ""
    errors = answer.get("errors")
    if isinstance(errors, dict) and errors:
        detail = "; ".join(
            "%s: %s" % (field, ", ".join(v) if isinstance(v, list) else v)
            for field, v in sorted(errors.items()))
        text = ("%s (%s)" % (text, detail)) if text else detail
    if not text and answer.get("_raw"):
        text = answer["_raw"]
    return text or "no message in the answer (HTTP %s)" % status


def _call(method, host, path, http=None, headers=None, body=None, query=None):
    if not configured():
        raise AcrConsoleError("unconfigured",
                              "ACRCLOUD_CONSOLE_TOKEN is not set")
    url = "https://%s%s" % (host, path)
    if query:
        pairs = ["%s=%s" % (k, urllib.parse.quote(str(v), safe=""))
                 for k, v in sorted(query.items()) if v not in (None, "")]
        if pairs:
            url += "?" + "&".join(pairs)
    status, answer = (http or _http)(method, url, _headers(headers), body)
    if status < 200 or status >= 300:
        msg = _vendor_message(status, answer)
        _remember_refusal(status, msg)
        raise AcrConsoleError(status, msg)
    return answer if isinstance(answer, dict) else {}


def _multipart(fields, file_field=None, filename=None, payload=None):
    boundary = "----StreetBankerConsole" + uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        if value in (None, ""):
            continue
        parts.append(
            ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
             % (boundary, name, value)).encode("utf-8"))
    if file_field is not None:
        parts.append(
            ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
             "Content-Type: application/octet-stream\r\n\r\n"
             % (boundary, file_field, (filename or "audio").replace("\"", ""))
             ).encode("utf-8"))
        parts.append(payload or b"")
        parts.append(b"\r\n")
    parts.append(("--%s--\r\n" % boundary).encode("utf-8"))
    return ("multipart/form-data; boundary=%s" % boundary), b"".join(parts)


# --- buckets ------------------------------------------------------------------

def buckets(http=None, type_="File", region=None, max_pages=MAX_PAGES):
    """Every bucket the token can see, as a list of dicts.

    Paged with a hard ceiling. `meta.last_page` is trusted only as a stop
    signal, never as a loop condition on its own: a missing or nonsense
    `meta` stops the walk rather than spinning it.
    """
    out, page = [], 1
    while page <= max_pages:
        answer = _call("GET", ACCOUNT_HOST, "/api/buckets", http=http,
                       query={"page": page, "per_page": PAGE_SIZE,
                              "type": type_, "region": region})
        rows = answer.get("data")
        rows = rows if isinstance(rows, list) else []
        out.extend(_bucket_fields(r) for r in rows if isinstance(r, dict))
        meta = answer.get("meta") if isinstance(answer.get("meta"), dict) else {}
        try:
            last = int(meta.get("last_page") or 0)
        except (TypeError, ValueError):
            last = 0
        if len(rows) < PAGE_SIZE or page >= last:
            break
        page += 1
    return out


def _bucket_fields(row):
    return {
        "id": str(row.get("id") or ""),
        "name": row.get("name") or "",
        "type": row.get("type") or "",
        "region": row.get("region") or "",
        "state": row.get("state"),
        "num": row.get("num"),
        "size": row.get("size"),
    }


# --- registering a master ------------------------------------------------------

def upload_audio(bucket_id, filename, data, title, custom=None, http=None,
                 region=None):
    """Put one of the owner's own recordings into their custom bucket.

    `custom` is written to ACRCloud's `user_defined`, which is what comes
    back on a match - so the row that ties a detection to a Street Banker
    vault file is carried by ACRCloud itself, not only by our table.

    Returns {audio_id, acr_id, state, state_word, title, bucket_id, raw}.
    """
    data = data or b""
    if not data:
        raise AcrConsoleError("empty", "the file read back as zero bytes")
    if len(data) > MAX_REGISTER_BYTES:
        raise AcrConsoleError(
            "too_large",
            "the file is %d MB and this desk sends at most %d MB"
            % (len(data) // (1024 * 1024), MAX_REGISTER_BYTES // (1024 * 1024)))
    fields = {"title": (title or filename or "Untitled")[:200],
              "data_type": "audio"}
    if custom:
        fields["user_defined"] = json.dumps(custom, sort_keys=True)
    content_type, body = _multipart(fields, "file", filename or "master.wav", data)
    answer = _call("POST", region_host(region),
                   "/api/buckets/%s/files" % _seg(bucket_id), http=http,
                   headers={"Content-Type": content_type}, body=body)
    return _audio_fields(answer.get("data") if isinstance(answer.get("data"), dict)
                         else answer)


def _audio_fields(row):
    row = row if isinstance(row, dict) else {}
    state = _int_or_none(row.get("state"))
    return {
        "audio_id": str(row.get("id") or ""),
        "acr_id": row.get("acr_id") or "",
        "state": state,
        "state_word": STATE_WORDS.get(state, "unknown"),
        "title": row.get("title") or "",
        "bucket_id": str(row.get("bucket_id") or ""),
        "duration": row.get("duration"),
    }


# --- file scanning -------------------------------------------------------------

def containers(http=None, region=None, max_pages=MAX_PAGES):
    """The file-scanning containers the token can see. Same bounded walk."""
    out, page = [], 1
    while page <= max_pages:
        answer = _call("GET", ACCOUNT_HOST, "/api/fs-containers", http=http,
                       query={"page": page, "per_page": PAGE_SIZE,
                              "region": region})
        rows = answer.get("data")
        rows = rows if isinstance(rows, list) else []
        out.extend({"id": str(r.get("id") or ""), "name": r.get("name") or "",
                    "region": r.get("region") or "", "state": r.get("state"),
                    "audio_type": r.get("audio_type") or ""}
                   for r in rows if isinstance(r, dict))
        meta = answer.get("meta") if isinstance(answer.get("meta"), dict) else {}
        try:
            last = int(meta.get("last_page") or 0)
        except (TypeError, ValueError):
            last = 0
        if len(rows) < PAGE_SIZE or page >= last:
            break
        page += 1
    return out


def scan_file(container_id, filename=None, data=None, url=None, name=None,
              http=None, region=None):
    """Hand ACRCloud a long recording and get back a job id.

    Either bytes (`data` + `filename`) or a URL they fetch themselves
    (`url`). The URL form is the one that matters for a two-hour DJ set: the
    file never passes through this deployment at all.

    Returns {job_id, container_id, file_id, state, state_word, name}.
    """
    if data:
        if len(data) > MAX_SCAN_BYTES:
            raise AcrConsoleError(
                "too_large",
                "the recording is %d MB and ACRCloud takes at most %d MB"
                % (len(data) // (1024 * 1024), MAX_SCAN_BYTES // (1024 * 1024)))
        fields = {"data_type": "audio", "name": (name or filename or "")[:200]}
        content_type, body = _multipart(fields, "file", filename or "scan.wav", data)
    elif url:
        fields = {"data_type": "audio_url", "url": url,
                  "name": (name or url)[:200]}
        content_type, body = _multipart(fields)
    else:
        raise AcrConsoleError("no_input", "a scan needs a file or a URL")
    answer = _call("POST", region_host(region),
                   "/api/fs-containers/%s/files" % _seg(container_id), http=http,
                   headers={"Content-Type": content_type}, body=body)
    row = answer.get("data") if isinstance(answer.get("data"), dict) else answer
    file_id = str((row or {}).get("id") or "")
    state = _int_or_none((row or {}).get("state"))
    return {"job_id": "%s:%s" % (container_id, file_id),
            "container_id": str(container_id), "file_id": file_id,
            "state": state, "state_word": STATE_WORDS.get(state, "unknown"),
            "name": (row or {}).get("name") or (name or filename or url or "")}


def _split_job(job_id):
    container_id, _, file_id = str(job_id or "").partition(":")
    if not container_id or not file_id:
        raise AcrConsoleError("bad_job", "a job id is '<container>:<file>'")
    return container_id, file_id


def _fetch_job(job_id, http=None, region=None):
    container_id, file_id = _split_job(job_id)
    answer = _call("GET", region_host(region),
                   "/api/fs-containers/%s/files/%s" % (_seg(container_id), _seg(file_id)),
                   http=http)
    row = answer.get("data")
    if isinstance(row, list):
        row = row[0] if row else {}
    return row if isinstance(row, dict) else {}


def scan_state(job_id, http=None, region=None):
    """Where the job is. {state, state_word, name, duration}."""
    row = _fetch_job(job_id, http=http, region=region)
    state = _int_or_none(row.get("state"))
    return {"state": state, "state_word": STATE_WORDS.get(state, "unknown"),
            "name": row.get("name") or "", "duration": row.get("duration")}


def scan_results(job_id, http=None, region=None):
    """Every track ACRCloud found in the recording, flattened.

    Same call as `scan_state` - their API carries state and results together.
    Returns {state, state_word, hits: [...]}, and `hits` is empty for every
    state but ready, which is the honest answer while a job is still running.
    """
    row = _fetch_job(job_id, http=http, region=region)
    state = _int_or_none(row.get("state"))
    results = row.get("results") if isinstance(row.get("results"), dict) else {}
    music = results.get("music")
    music = music if isinstance(music, list) else []
    hits = [_hit_fields(item) for item in music if isinstance(item, dict)]
    hits.sort(key=lambda h: (h["start_ms"] if h["start_ms"] is not None else 0))
    return {"state": state, "state_word": STATE_WORDS.get(state, "unknown"),
            "name": row.get("name") or "", "hits": hits}


def _hit_fields(item):
    """One detection, in this app's words.

    START AND END ARE THE RECORDING'S CLOCK, not the database track's.
    ACRCloud sends both: `db_*_time_offset_ms` is where inside the released
    recording the match sits, and the item's own `offset` plus
    `played_duration` is where inside the file the owner uploaded it plays.
    The second pair is the one a person scrubs to, so it is the one shown,
    and the first pair is kept beside it rather than confused with it.

    UNITS. The item's `offset` and `played_duration` are documented in
    SECONDS, while every `*_time_offset_ms` field is milliseconds. Both are
    stored here in milliseconds, converted once, at the edge - so nothing
    downstream has to remember which of two numbers on the same row is
    which.
    """
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    ids = result.get("external_ids") if isinstance(result.get("external_ids"), dict) else {}
    album = result.get("album")
    start_s = _int_or_none(item.get("offset"))
    played_s = _int_or_none(item.get("played_duration"))
    start = start_s * 1000 if start_s is not None else None
    end = (start + played_s * 1000) if (start is not None and played_s is not None) else None
    artists = ", ".join(a.get("name") for a in result.get("artists") or []
                        if isinstance(a, dict) and a.get("name"))
    return {
        "acrid": result.get("acrid") or "",
        "title": result.get("title") or "",
        "artists": artists,
        "album": (album.get("name") or "") if isinstance(album, dict) else (album or ""),
        "label": result.get("label") or "",
        "isrc": ids.get("isrc") or "",
        "start_ms": start,
        "end_ms": end,
        "score": _int_or_none(result.get("score")),
        "kind": item.get("type") or "",
        "db_begin_ms": _int_or_none(result.get("db_begin_time_offset_ms")),
        "db_end_ms": _int_or_none(result.get("db_end_time_offset_ms")),
    }


# --- small helpers -------------------------------------------------------------

def _seg(value):
    """One path segment, quoted. An id from a vendor is still user input by
    the time it has been round-tripped through a form."""
    return urllib.parse.quote(str(value or "").strip(), safe="")


def _int_or_none(value):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def clock(ms):
    """Milliseconds as h:mm:ss, or "" when there is nothing measured. A
    timestamp is the whole point of a scan, so it never prints as 0:00:00
    because a field was missing."""
    if ms is None:
        return ""
    total = max(0, int(ms) // 1000)
    return "%d:%02d:%02d" % (total // 3600, (total % 3600) // 60, total % 60)

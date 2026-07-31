"""StemSplit.io — the Stem Deck's studio-quality separation tier.

Env-gated on STEMSPLIT_API_KEY (pasted into Render Environment, never
through chat). Without the key the feature does not render and its
endpoints answer 503 - nothing pretends.

Flow, shaped around the Render Starter's limits:
  1. The Rack uploads the loaded track once; we park it on disk under an
     unguessable token and lend StemSplit a public URL to fetch it from
     (their documented source_url flow) - the dyno never re-streams the
     source to the API.
  2. We create a FOUR_STEMS job and the browser polls our status proxy;
     the key stays server-side.
  3. Finished stems stream back through us (their presigned URLs make no
     CORS promises), then the temp source is deleted. A sweeper also
     drops anything older than an hour so restarts cannot leak files.

Uses urllib - no new dependency.
"""

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
import uuid

BASE = "https://stemsplit.io/api/v1"
# Who we are, said plainly, with somewhere to look us up.
UA = "StreetBanker/1.0 (+https://street-banker.onrender.com)"
JOBS = os.environ.get("STEMSPLIT_JOBS_PATH", "/jobs")
SRC_DIR = os.path.join(tempfile.gettempdir(), "sb-stem-src")
MAX_UPLOAD = 60 * 1024 * 1024          # a full-length WAV, with headroom
SRC_TTL = 3600

# job id -> temp source path, so terminal statuses can clean up
_sources = {}


def configured():
    return bool(os.environ.get("STEMSPLIT_API_KEY"))


def _headers():
    """Identify the client properly.

    StemSplit sits behind Cloudflare, whose browser-integrity check rejects
    requests carrying urllib's default `Python-urllib/3.x` agent - it
    answered 403 with Cloudflare error 1010 on EVERY path, including
    /balance and a job id that does not exist. Identical answers everywhere
    is the signature of a WAF, not an API: a real API 404s an unknown path
    and 401s a bad key, and that pattern is what showed the key was never
    the problem.

    This is a plain, honest product agent with a contact URL - the client
    saying who it is, which is what an API expects. It is not pretending to
    be a browser.
    """
    return {
        "Authorization": "Bearer " + os.environ.get("STEMSPLIT_API_KEY", ""),
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": UA,
    }


def _call(method, path, payload=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode()), None
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode())
            msg = detail.get("message") or detail.get("error") or str(e)
        except Exception:
            msg = str(e)
        return None, "%s (HTTP %s)" % (msg, e.code)
    except Exception as e:
        return None, str(e)


def _scrub(text):
    """Never let the key appear in anything we hand back, even by accident."""
    key = os.environ.get("STEMSPLIT_API_KEY")
    if key and len(key) > 6:
        text = text.replace(key, "[redacted]")
    return text


def probe():
    """Which read-only endpoints does this key actually reach?

    Two published sources disagree about the path (/jobs in the REST docs,
    /separate in the n8n node), and a wrong path answers 403 rather than
    404, which is indistinguishable from a dead key. So ask the API. Every
    path here is GET and free - no job is created and no credit is spent.
    Returns status codes and a scrubbed body snippet, never the key.
    """
    out = []
    for path in ("/balance", "/jobs", "/separate",
                 "/jobs/probe-no-such-job", "/separate/probe-no-such-job"):
        req = urllib.request.Request(BASE + path, headers=_headers(),
                                     method="GET")
        entry = {"path": path}
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                entry["status"] = resp.status
                entry["body"] = _scrub(resp.read(400).decode("utf8", "replace"))
        except urllib.error.HTTPError as e:
            entry["status"] = e.code
            try:
                entry["body"] = _scrub(e.read(400).decode("utf8", "replace"))
            except Exception:
                entry["body"] = ""
        except Exception as e:
            entry["status"] = None
            entry["body"] = _scrub(str(e))
        out.append(entry)
    return out


def sweep():
    """Drop parked sources older than an hour - restart-safe cleanup."""
    try:
        now = time.time()
        for name in os.listdir(SRC_DIR):
            p = os.path.join(SRC_DIR, name)
            if os.path.isfile(p) and now - os.path.getmtime(p) > SRC_TTL:
                os.remove(p)
    except OSError:
        pass


def park_source(data, ext):
    """Store the uploaded track under a token; returns (token, path)."""
    os.makedirs(SRC_DIR, exist_ok=True)
    sweep()
    token = uuid.uuid4().hex + (ext or "")
    path = os.path.join(SRC_DIR, token)
    with open(path, "wb") as f:
        f.write(data)
    return token, path


def source_path(token):
    """Resolve a token back to its file - tokens only, no path tricks."""
    if not token or "/" in token or "\\" in token or ".." in token:
        return None
    path = os.path.join(SRC_DIR, token)
    return path if os.path.isfile(path) else None


def create_job(source_url):
    """Four-stem job at best quality. Keys are camelCase per the published
    REST contract - snake_case is silently rejected."""
    body, err = _call("POST", JOBS, {
        "sourceUrl": source_url,
        "outputType": "FOUR_STEMS",
        "quality": "BEST",
        "outputFormat": "MP3",
    })
    if err:
        return None, err
    job_id = body.get("id") or body.get("jobId")
    if not job_id:
        return None, "StemSplit accepted the job but returned no id"
    return job_id, None


def remember_source(job_id, path):
    _sources[job_id] = path


STEMS = ("vocals", "drums", "bass", "other", "instrumental")


def _outputs(body):
    """Stem name -> url, from either published response shape: the docs'
    nested {"outputs": {"vocals": {"url": ...}}} or the n8n node's flat
    {"vocalsUrl": ...}. Whichever this account's API returns, we read it."""
    found = {}
    nested = body.get("outputs") or {}
    if isinstance(nested, dict):
        for name, entry in nested.items():
            url = entry.get("url") if isinstance(entry, dict) else entry
            if isinstance(url, str):
                found[name.lower()] = url
    for name in STEMS:
        url = body.get(name + "Url")
        if isinstance(url, str) and name not in found:
            found[name] = url
    return found


def job_status(job_id):
    """Normalized status: {status, progress, stems:[name]}. Terminal
    statuses delete the parked source."""
    body, err = _call("GET", JOBS + "/" + job_id)
    if err:
        return None, err
    status = str(body.get("status") or "PENDING").upper()
    out = {"status": status,
           "progress": body.get("progress") or 0,
           "stems": sorted(_outputs(body).keys())}
    if status in ("COMPLETED", "FAILED", "EXPIRED"):
        path = _sources.pop(job_id, None)
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
    return out, None


def stem_url(job_id, stem):
    """Fresh presigned URL for one stem, straight from the API - they
    expire in an hour, so we never cache them."""
    body, err = _call("GET", JOBS + "/" + job_id)
    if err:
        return None, err
    url = _outputs(body).get(stem)
    if not url or not url.startswith("https://"):
        return None, "stem not available"
    return url, None


def open_stream(url):
    """Open the presigned URL for streaming to the browser."""
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}),
        timeout=60)

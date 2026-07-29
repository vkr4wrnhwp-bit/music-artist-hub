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
SRC_DIR = os.path.join(tempfile.gettempdir(), "sb-stem-src")
MAX_UPLOAD = 60 * 1024 * 1024          # a full-length WAV, with headroom
SRC_TTL = 3600

# job id -> temp source path, so terminal statuses can clean up
_sources = {}


def configured():
    return bool(os.environ.get("STEMSPLIT_API_KEY"))


def _headers():
    return {
        "Authorization": "Bearer " + os.environ.get("STEMSPLIT_API_KEY", ""),
        "Content-Type": "application/json",
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
    body, err = _call("POST", "/jobs", {
        "source_url": source_url,
        "output_type": "FOUR_STEMS",
        "quality": "BEST",
        "output_format": "MP3",
    })
    if err:
        return None, err
    return body.get("id"), None


def remember_source(job_id, path):
    _sources[job_id] = path


def job_status(job_id):
    """Normalized status: {status, progress, stems:[{name}]}. Terminal
    statuses delete the parked source."""
    body, err = _call("GET", "/jobs/" + job_id)
    if err:
        return None, err
    status = str(body.get("status") or "PENDING").upper()
    out = {"status": status,
           "progress": body.get("progress") or 0,
           "stems": sorted((body.get("outputs") or {}).keys())}
    if status in ("COMPLETED", "FAILED", "EXPIRED"):
        path = _sources.pop(job_id, None)
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
    return out, None


def stem_url(job_id, stem):
    """Fresh presigned URL for one stem, straight from the API."""
    body, err = _call("GET", "/jobs/" + job_id)
    if err:
        return None, err
    entry = (body.get("outputs") or {}).get(stem) or {}
    url = entry.get("url")
    if not url or not url.startswith("https://"):
        return None, "stem not available"
    return url, None


def open_stream(url):
    """Open the presigned URL for streaming to the browser."""
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "StreetBanker"}),
        timeout=60)

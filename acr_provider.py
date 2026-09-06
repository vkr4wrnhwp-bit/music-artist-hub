"""Fingerprint identification through ACRCloud.

What this is: a check the producer runs. A short sample - a slice of the
beat itself, or a clip they found somewhere - goes to ACRCloud's
identify endpoint, which compares it with an index of released
recordings and answers with the recording it matches, or with nothing.

What this is NOT: monitoring. Nothing here crawls platforms, listens on
a schedule, or is Content ID (that is YouTube's, granted to rights
administrators rather than applied for). A match names a released
recording; whether that recording really carries the producer's beat is
still their ear's call, which is why a match is logged as a usage case
only when they press the button - and then it carries
`found_via='fingerprint'`, derived from the stored match row rather than
from anything the form could claim.

    ACRCLOUD_HOST           e.g. identify-us-west-2.acrcloud.com
    ACRCLOUD_ACCESS_KEY     project access key
    ACRCLOUD_ACCESS_SECRET  project secret

Their signing scheme (signature version 1): HMAC-SHA1 over the lines
POST, /v1/identify, the access key, the data type, the version and a
unix timestamp, base64-encoded, sent as a multipart form beside the
sample. Status code 0 is a result, 1001 is "no result"; anything else is
their error and is raised as AcrError with their code and message.
"""

import base64
import hashlib
import hmac
import json
import os
import struct
import time
import urllib.request
import uuid

MAX_CLIP_BYTES = 10 * 1024 * 1024      # a clip the producer uploads
SAMPLE_LIMIT = 1000 * 1000             # what goes over the wire, their ceiling
SAMPLE_SECONDS = 12                    # a WAV slice this long, from the middle


class AcrError(Exception):
    def __init__(self, code, msg):
        Exception.__init__(self, "ACRCloud %s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def configured():
    return bool(os.environ.get("ACRCLOUD_HOST")
                and os.environ.get("ACRCLOUD_ACCESS_KEY")
                and os.environ.get("ACRCLOUD_ACCESS_SECRET"))


def status():
    """What the producers desk tells the truth with."""
    if configured():
        return {
            "on": True,
            "headline": "Fingerprint identification is connected",
            "detail": "ACRCloud is set up. It runs only when you press a "
                      "button on a beat's page, and it compares a short "
                      "sample with its index of released recordings. It "
                      "does not crawl platforms or listen on its own. A "
                      "match you confirm becomes a usage case marked "
                      "'fingerprint' beside the ones you log by hand.",
        }
    return {
        "on": False,
        "headline": "Nothing here scans for you",
        "detail": "This desk does not listen to audio or crawl platforms, "
                  "and no part of it is Content ID - that is YouTube's, and "
                  "it is granted to rights administrators, not applied for. "
                  "A use appears here when somebody logs it. Connecting a "
                  "fingerprinting vendor (ACRCloud, Audible Magic, Pex) is "
                  "what would change that, and it is a paid account.",
    }


# --- the sample ---------------------------------------------------------------

def slice_sample(data, mime="", limit=SAMPLE_LIMIT, seconds=SAMPLE_SECONDS):
    """A piece of the audio small enough to send.

    A WAV is re-headed so the slice is a valid file taken from the middle
    of the beat, where the beat is (intros are silence and risers). An
    MP3 is frame-based and any decoder resyncs, so the middle slice is
    sent raw. Anything else goes from the start: containers that keep
    their index at the end would not survive a cut, and if the vendor
    cannot decode it, it says so and that is what the producer sees.
    """
    data = data or b""
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        wav = _slice_wav(data, limit, seconds)
        if wav is not None:
            return wav
    if (mime or "").lower() in ("audio/mpeg", "audio/mp3") or data[:3] == b"ID3":
        if len(data) <= limit:
            return data
        start = (len(data) - limit) // 2
        return data[start:start + limit]
    return data[:limit]


def _slice_wav(data, limit, seconds):
    pos, fmt_chunk, data_pos, data_len = 12, None, None, 0
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        if cid == b"fmt ":
            fmt_chunk = data[pos:pos + 8 + size + (size & 1)]
        elif cid == b"data":
            data_pos, data_len = pos + 8, min(size, len(data) - pos - 8)
            break
        pos += 8 + size + (size & 1)
    if fmt_chunk is None or data_pos is None or len(fmt_chunk) < 24:
        return None
    block_align = struct.unpack("<H", fmt_chunk[20:22])[0] or 1
    byte_rate = struct.unpack("<I", fmt_chunk[16:20])[0] or 1
    want = min(data_len, seconds * byte_rate, max(0, limit - 12 - len(fmt_chunk) - 8))
    want -= want % block_align
    start = (data_len - want) // 2
    start -= start % block_align
    body = data[data_pos + start:data_pos + start + want]
    riff_size = 4 + len(fmt_chunk) + 8 + len(body)
    return (b"RIFF" + struct.pack("<I", riff_size) + b"WAVE" + fmt_chunk
            + b"data" + struct.pack("<I", len(body)) + body)


# --- the call -----------------------------------------------------------------

def _signature(access_key, secret, timestamp, data_type="audio"):
    to_sign = "\n".join(["POST", "/v1/identify", access_key, data_type, "1", str(timestamp)])
    digest = hmac.new(secret.encode("ascii"), to_sign.encode("ascii"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _multipart(fields, file_field, filename, payload):
    boundary = "----StreetBanker" + uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (boundary, name, value)).encode("utf-8"))
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                  "Content-Type: application/octet-stream\r\n\r\n"
                  % (boundary, file_field, filename)).encode("utf-8"))
    parts.append(payload)
    parts.append(("\r\n--%s--\r\n" % boundary).encode("utf-8"))
    return "multipart/form-data; boundary=%s" % boundary, b"".join(parts)


def _post(url, content_type, body, timeout=20):
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": content_type,
                                          "User-Agent": "StreetBanker/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def identify(sample, post=None):
    """Matches for a sample, as a list; [] when their index has nothing.

    `post(url, content_type, body) -> dict` is injectable for tests.
    """
    if not configured():
        raise AcrError("unconfigured", "ACRCloud keys are not set")
    host = os.environ["ACRCLOUD_HOST"].strip().replace("https://", "").replace("http://", "").rstrip("/")
    access_key = os.environ["ACRCLOUD_ACCESS_KEY"].strip()
    secret = os.environ["ACRCLOUD_ACCESS_SECRET"].strip()
    timestamp = int(time.time())
    fields = {
        "access_key": access_key,
        "sample_bytes": str(len(sample)),
        "timestamp": str(timestamp),
        "signature": _signature(access_key, secret, timestamp),
        "data_type": "audio",
        "signature_version": "1",
    }
    content_type, body = _multipart(fields, "sample", "sample.bin", sample)
    try:
        answer = (post or _post)("https://%s/v1/identify" % host, content_type, body)
    except AcrError:
        raise
    except Exception as e:
        raise AcrError("network", str(e))
    status_ = (answer or {}).get("status") or {}
    code = status_.get("code")
    if code == 1001:
        return []
    if code != 0:
        raise AcrError(code if code is not None else "malformed",
                       status_.get("msg") or "no status in the answer")
    meta = answer.get("metadata") or {}
    out = [_match_fields(m, "music") for m in meta.get("music") or []]
    out += [_match_fields(m, "custom") for m in meta.get("custom_files") or []]
    out.sort(key=lambda m: -m["score"])
    return out


def _match_fields(m, kind):
    ext = m.get("external_metadata") or {}
    ids = m.get("external_ids") or {}
    url, platform = "", ""
    spotify = ((ext.get("spotify") or {}).get("track") or {}).get("id")
    youtube = (ext.get("youtube") or {}).get("vid")
    deezer = ((ext.get("deezer") or {}).get("track") or {}).get("id")
    if spotify:
        url, platform = "https://open.spotify.com/track/%s" % spotify, "Spotify"
    elif youtube:
        url, platform = "https://www.youtube.com/watch?v=%s" % youtube, "YouTube"
    elif deezer:
        url, platform = "https://www.deezer.com/track/%s" % deezer, "Deezer"
    artists = ", ".join(a.get("name") for a in m.get("artists") or [] if a.get("name"))
    album = m.get("album") or {}
    try:
        score = int(round(float(m.get("score") or 0)))
    except (TypeError, ValueError):
        score = 0
    try:
        offset = int(m.get("play_offset_ms") or 0)
    except (TypeError, ValueError):
        offset = 0
    return {
        "kind": kind,
        "acrid": m.get("acrid") or "",
        "title": m.get("title") or "",
        "artists": artists,
        "album": (album.get("name") or "") if isinstance(album, dict) else (album or ""),
        "label": m.get("label") or "",
        "release_date": m.get("release_date") or "",
        "isrc": ids.get("isrc") or "",
        "url": url,
        "platform": platform,
        "score": score,
        "play_offset_ms": offset,
    }

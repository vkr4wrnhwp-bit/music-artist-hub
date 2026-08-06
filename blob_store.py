"""Where uploaded files live.

Everything the app stores - vault audio, cover art, EPK photos, sync
packs, documents - has been landing on the Render disk next to the
SQLite database. That disk is 1 GB and shared with the database, so
audio is the line item that ends the arrangement: a handful of masters
fills it and takes the database down with it.

This puts an object store in front of that disk. Cloudflare R2 because
egress is free, which matters more than the storage price here - a fan
EPK player streams the same file repeatedly, and on S3 the bandwidth
bill outgrows the storage bill quickly.

DESIGN NOTES, in the order they will matter to whoever reads this next:

  Not configured means local disk, not broken. Set the four R2 env vars
  and new uploads go to the bucket; leave them unset and everything
  behaves exactly as it did. No feature disappears, nothing pretends.

  Old rows keep working. Paths already in the database look like
  "/uploads/vault_3_17...mp3" and still resolve to the disk. New objects
  are stored as "r2:<key>". Two shapes, one resolver, no migration
  required to deploy. A backfill can move the old ones later.

  Signed by hand rather than with boto3. SigV4 is hmac + hashlib, and
  boto3 would add ~50 MB to a Starter build for two API calls.

  Reads are presigned and short-lived. The bucket stays private, so a
  vault URL cannot be forwarded to somebody who should not have it -
  it expires. That is the whole reason not to make the bucket public.

Credentials come from the environment and are never logged:
  R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
Optional: R2_PUBLIC_BASE_URL, if you attach a custom domain and want
plain public URLs for non-sensitive assets instead of signed ones.
"""

import datetime
import hashlib
import hmac
import os
import urllib.error
import urllib.parse
import urllib.request

REGION = "auto"
SERVICE = "s3"
ALGO = "AWS4-HMAC-SHA256"
DEFAULT_TTL = 3600          # an hour is long enough to play a track

# Marker for objects that live in the bucket. Anything else is a legacy
# "/uploads/..." disk path.
PREFIX = "r2:"


def _env(name):
    return (os.environ.get(name) or "").strip()


def configured():
    return all(_env(k) for k in ("R2_ACCOUNT_ID", "R2_BUCKET",
                                 "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"))


def _endpoint():
    return "https://%s.r2.cloudflarestorage.com" % _env("R2_ACCOUNT_ID")


def _host():
    return "%s.r2.cloudflarestorage.com" % _env("R2_ACCOUNT_ID")


def _quote(path):
    """S3 wants each segment percent-encoded, with the slashes intact."""
    return "/".join(urllib.parse.quote(p, safe="~") for p in path.split("/"))


def _sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret, datestamp):
    k = _sign(("AWS4" + secret).encode("utf-8"), datestamp)
    k = _sign(k, REGION)
    k = _sign(k, SERVICE)
    return _sign(k, "aws4_request")


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


# --- signing --------------------------------------------------------------

def _canonical(method, uri, query, headers, payload_hash):
    canon_headers = "".join("%s:%s\n" % (k, headers[k]) for k in sorted(headers))
    signed = ";".join(sorted(headers))
    return ("%s\n%s\n%s\n%s\n%s\n%s"
            % (method, uri, query, canon_headers, signed, payload_hash)), signed


def _auth_header(method, key, payload, content_type):
    """Header-style SigV4, used for PUT and DELETE where we hold the bytes."""
    now = _now()
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    uri = "/%s/%s" % (_env("R2_BUCKET"), _quote(key))
    payload_hash = hashlib.sha256(payload or b"").hexdigest()

    headers = {"host": _host(), "x-amz-content-sha256": payload_hash,
               "x-amz-date": amzdate}
    if content_type:
        headers["content-type"] = content_type

    canon, signed = _canonical(method, uri, "", headers, payload_hash)
    scope = "%s/%s/%s/aws4_request" % (datestamp, REGION, SERVICE)
    to_sign = "%s\n%s\n%s\n%s" % (ALGO, amzdate, scope,
                                  hashlib.sha256(canon.encode()).hexdigest())
    sig = hmac.new(_signing_key(_env("R2_SECRET_ACCESS_KEY"), datestamp),
                   to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        "%s Credential=%s/%s, SignedHeaders=%s, Signature=%s"
        % (ALGO, _env("R2_ACCESS_KEY_ID"), scope, signed, sig))
    return headers, uri


def presigned_get(key, ttl=DEFAULT_TTL):
    """A time-limited URL. The bucket stays private."""
    now = _now()
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    uri = "/%s/%s" % (_env("R2_BUCKET"), _quote(key))
    scope = "%s/%s/%s/aws4_request" % (datestamp, REGION, SERVICE)

    params = {
        "X-Amz-Algorithm": ALGO,
        "X-Amz-Credential": "%s/%s" % (_env("R2_ACCESS_KEY_ID"), scope),
        "X-Amz-Date": amzdate,
        "X-Amz-Expires": str(int(ttl)),
        "X-Amz-SignedHeaders": "host",
    }
    query = "&".join("%s=%s" % (urllib.parse.quote(k, safe="~"),
                                urllib.parse.quote(params[k], safe="~"))
                     for k in sorted(params))
    canon, _ = _canonical("GET", uri, query, {"host": _host()},
                          "UNSIGNED-PAYLOAD")
    to_sign = "%s\n%s\n%s\n%s" % (ALGO, amzdate, scope,
                                  hashlib.sha256(canon.encode()).hexdigest())
    sig = hmac.new(_signing_key(_env("R2_SECRET_ACCESS_KEY"), datestamp),
                   to_sign.encode(), hashlib.sha256).hexdigest()
    return "%s%s?%s&X-Amz-Signature=%s" % (_endpoint(), uri, query, sig)


# --- the two calls the app makes -----------------------------------------

def put(key, data, content_type=None):
    headers, uri = _auth_header("PUT", key, data, content_type)
    req = urllib.request.Request(_endpoint() + uri, data=data,
                                 headers=headers, method="PUT")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return 200 <= resp.status < 300


def delete(key):
    headers, uri = _auth_header("DELETE", key, b"", None)
    req = urllib.request.Request(_endpoint() + uri, headers=headers,
                                 method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as exc:
        return exc.code == 404          # already gone is a success


# --- what app.py actually calls ------------------------------------------

def save(fname, data, content_type=None, uploads_dir=None):
    """Store bytes and return the path to record in the database.

    "r2:<key>" when the bucket is configured, "/uploads/<fname>" when it
    is not. The caller does not branch on which.
    """
    if configured():
        try:
            if put(fname, data, content_type):
                return PREFIX + fname
        except Exception:
            # A bucket outage must not lose the artist's upload. Fall
            # through to the disk; url_for resolves either shape.
            pass
    if uploads_dir:
        with open(os.path.join(uploads_dir, fname), "wb") as fh:
            fh.write(data)
    return "/uploads/" + fname


def is_remote(path):
    return bool(path) and path.startswith(PREFIX)


def key_of(path):
    return path[len(PREFIX):] if is_remote(path) else None


def url_for(path, ttl=DEFAULT_TTL):
    """Resolve a stored path to something a browser can fetch."""
    if not is_remote(path):
        return path                      # legacy disk path, served locally
    key = key_of(path)
    base = _env("R2_PUBLIC_BASE_URL")
    if base:
        return "%s/%s" % (base.rstrip("/"), _quote(key))
    if not configured():
        # Credentials were removed after objects were written, or a
        # worker booted without them. Signing here would raise and take
        # the whole page with it; a dead link is the smaller failure.
        return path
    try:
        return presigned_get(key, ttl)
    except Exception:
        return path


def fetch(path, timeout=30):
    """Read an object back as bytes, or None.

    Only the batch-download zip needs this: everything else hands the
    browser a presigned URL and lets it do the fetching. Returns None
    rather than raising, because one unreachable object should cost that
    file and not the whole archive.
    """
    if not is_remote(path) or not configured():
        return None
    try:
        url = presigned_get(key_of(path), ttl=120)
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read()
    except Exception:
        # Deliberately broad. Signing an unreachable or half-configured
        # endpoint raises things that are not URLError - an empty account
        # id produces a malformed host and a UnicodeError from idna - and
        # one bad object must not take the archive down with it.
        return None


def remove(path, uploads_dir=None):
    if is_remote(path):
        try:
            return delete(key_of(path))
        except Exception:
            return False
    if uploads_dir and path and path.startswith("/uploads/"):
        try:
            os.remove(os.path.join(uploads_dir, os.path.basename(path)))
            return True
        except OSError:
            return False
    return False

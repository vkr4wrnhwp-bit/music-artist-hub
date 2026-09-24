"""Cover art renders: OpenAI's image model, and each account's monthly allowance.

Owner, 2026-09-23: "open ai and we allow x amount of renders a month".
The Cover Studio's Generate button used to build a Pollinations.ai URL
(free, keyless, generic). With OPENAI_API_KEY set it now asks OpenAI's
gpt-image-1 instead, and every render spends the owner's money, so each
account gets a number of covers per calendar month (UTC), by plan.

THE REQUEST (OpenAI's Image API, checked against their docs 2026-09-23)
  POST https://api.openai.com/v1/images/generations
  Authorization: Bearer <OPENAI_API_KEY>
  {"model": "gpt-image-1", "prompt": ..., "n": 1, "size": "1024x1024",
   "quality": "medium", "output_format": "jpeg", "output_compression": 90}
  -> {"created": ..., "data": [{"b64_json": "<base64 image>"}], "usage": {...}}
  gpt-image-1 always answers in base64 (no URL to fetch later). A prompt
  the content filter blocks comes back as an error whose code is
  "moderation_blocked". JPEG rather than the PNG default because the
  uploads share a 1 GB disk with the database; a 1024 PNG is several
  times the size for no difference a cover proof can show.

THE ALLOWANCE
  DEFAULT_ALLOWANCE per plan, each changeable by the owner in Settings
  (app_kv "cover_renders:<plan>"). Owner logins are unlimited. A team seat
  works inside the account holder's account, so it draws on theirs.

  Every render is a row in cover_renders. A slot is RESERVED before the
  call (a "pending" row, taken inside BEGIN IMMEDIATE so two tabs or a
  double click cannot both take the last cover), then marked done, or
  failed / refused / timeout. Only done and fresh pending rows count
  against the month, so a failed, refused or timed-out render never uses
  the allowance up. A pending row older than PENDING_STALE_MINUTES is a
  worker that died mid-call and stops counting.

WHAT IT COSTS THE OWNER
  PRICE_PER_RENDER_USD is OpenAI's published gpt-image-1 price for one
  1024x1024 medium image, read off their model page on 2026-09-23. The
  prompt's text tokens are billed on top and are not counted here. A
  timeout may still have been charged by OpenAI; the owner's card counts
  those separately and says so.
"""
import base64
import json
import os
import socket
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import db

ENDPOINT = "https://api.openai.com/v1/images/generations"
MODEL = "gpt-image-1"
SIZE = "1024x1024"
QUALITY = "medium"
OUTPUT_FORMAT = "jpeg"
OUTPUT_COMPRESSION = 90
TIMEOUT = 120
MAX_IMAGE_BYTES = 12 * 1024 * 1024

PRICE_PER_RENDER_USD = Decimal("0.042")
PRICE_SOURCE = ("OpenAI's published gpt-image-1 price for one 1024x1024 "
                "medium image, checked 23 September 2026")

# Covers per account per calendar month (UTC). The owner changes these in
# Settings; this is what an account gets until he does.
DEFAULT_ALLOWANCE = {"fan": 0, "artist": 10, "pro": 30, "label": 100}
ALLOWANCE_MAX = 10000
PENDING_STALE_MINUTES = 10

# The codes OpenAI uses when its content filter refuses a prompt. The
# second is the DALL-E era name, kept so an older error shape is still
# read as a refusal rather than an outage.
REFUSAL_CODES = ("moderation_blocked", "content_policy_violation")

COUNTED = ("pending", "done")
STATUSES = ("pending", "done", "failed", "refused", "timeout")


class RenderError(Exception):
    """A render that produced no picture. kind is one of refused, failed,
    timeout; message is safe to show the artist (never the key, never
    OpenAI's raw body)."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind
        self.message = message


# --- the provider ---------------------------------------------------------------

def api_key():
    return (os.environ.get("OPENAI_API_KEY") or "").strip()


def configured():
    """True when OpenAI renders the covers. Unset (every local run, and a
    deployment before the owner pastes the key) the page keeps the free
    Pollinations path exactly as it was."""
    return bool(api_key())


def _transport(url, body, headers, timeout):
    """POST JSON, return (status, raw bytes). The seam tests monkeypatch,
    so no test ever reaches OpenAI. An HTTP error status is returned, not
    raised, so the caller can read OpenAI's error body."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
        except Exception:        # noqa: BLE001 - the status is enough
            raw = b""
        return e.code, raw


def request_body(prompt):
    return {"model": MODEL, "prompt": prompt, "n": 1, "size": SIZE,
            "quality": QUALITY, "output_format": OUTPUT_FORMAT,
            "output_compression": OUTPUT_COMPRESSION}


def _is_timeout(exc):
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, (socket.timeout, TimeoutError))


def render(prompt):
    """One cover from OpenAI. Returns the image bytes (JPEG), or raises
    RenderError. Never logs or returns the key."""
    key = api_key()
    if not key:
        raise RenderError("failed", "The cover generator is not switched on.")
    body = json.dumps(request_body(prompt)).encode("utf-8")
    headers = {"Authorization": "Bearer " + key,
               "Content-Type": "application/json"}
    try:
        status, raw = _transport(ENDPOINT, body, headers, TIMEOUT)
    except Exception as exc:     # noqa: BLE001 - every transport failure is one answer
        if _is_timeout(exc):
            raise RenderError("timeout", "The generator took too long and this cover "
                                         "was not made. It has not used one of your "
                                         "covers. Try again.") from None
        raise RenderError("failed", "The generator could not be reached. This cover "
                                    "has not used one of your covers. Try again "
                                    "in a minute.") from None
    try:
        payload = json.loads((raw or b"{}").decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        payload = {}
    if status != 200:
        err = payload.get("error") if isinstance(payload, dict) else None
        code = (err or {}).get("code") if isinstance(err, dict) else None
        if code in REFUSAL_CODES:
            raise RenderError("refused", "OpenAI's content rules refused this "
                                         "description, so no cover was made. It has "
                                         "not used one of your covers. Change the "
                                         "words and try again.")
        raise RenderError("failed", "The generator had a problem and this cover was "
                                    "not made. It has not used one of your covers. "
                                    "Try again in a minute.")
    try:
        b64 = payload["data"][0]["b64_json"]
        data = base64.b64decode(b64, validate=True)
    except (KeyError, IndexError, TypeError, ValueError):
        raise RenderError("failed", "The generator sent back no picture. This cover "
                                    "has not used one of your covers.") from None
    if not data or len(data) > MAX_IMAGE_BYTES or not (
            data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"):
        raise RenderError("failed", "The generator sent back something that is not "
                                    "a picture. This cover has not used one of your "
                                    "covers.")
    return data


def extension(data):
    return "png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "jpg"


# --- the allowance ------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc)


def month(now=None):
    return (now or _now()).strftime("%Y-%m")


def reset_date(now=None):
    """The first day of next month, the way the page says it: '1 October'."""
    now = now or _now()
    nxt = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    return "1 %s" % nxt.strftime("%B")


def _kv_key(plan):
    return "cover_renders:%s" % plan


def allowance(plan):
    """Covers a month for this plan: the owner's number, else the default."""
    plan = plan if plan in DEFAULT_ALLOWANCE else "artist"
    raw = db.get_kv(_kv_key(plan))
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_ALLOWANCE[plan]
    return n if 0 <= n <= ALLOWANCE_MAX else DEFAULT_ALLOWANCE[plan]


def allowances():
    return {p: allowance(p) for p in DEFAULT_ALLOWANCE}


def save_allowances(form):
    """Apply the owner's Settings form. Returns the plans refused (nothing
    saved for those; the rest are)."""
    refused = []
    for plan in DEFAULT_ALLOWANCE:
        field = "covers_" + plan
        if field not in form:
            continue
        try:
            n = int((form.get(field) or "").strip().replace(",", ""))
        except ValueError:
            n = -1
        if 0 <= n <= ALLOWANCE_MAX:
            db.set_kv(_kv_key(plan), str(n))
        else:
            refused.append(plan)
    return refused


def init_db():
    with db.get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cover_renders (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                actor_id TEXT,
                month TEXT NOT NULL,
                status TEXT NOT NULL,
                counts INTEGER NOT NULL DEFAULT 1,
                path TEXT,
                created_at TEXT NOT NULL,
                finished_at TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_cover_renders_account
                ON cover_renders (account_id, month, status);
            CREATE INDEX IF NOT EXISTS ix_cover_renders_month
                ON cover_renders (month, status);
        """)


def _stale_before(now=None):
    return ((now or _now()) - timedelta(minutes=PENDING_STALE_MINUTES)).isoformat(
        timespec="seconds")


def _used(conn, account_id, mon):
    row = conn.execute(
        "SELECT COUNT(*) FROM cover_renders WHERE account_id = ? AND month = ?"
        " AND counts = 1 AND (status = 'done'"
        " OR (status = 'pending' AND created_at >= ?))",
        (str(account_id), mon, _stale_before())).fetchone()
    return int(row[0] or 0)


def used(account_id, mon=None):
    """Covers this account has made (or is making right now) this month."""
    with db.get_db() as conn:
        return _used(conn, account_id, mon or month())


def reserve(account_id, actor_id, limit):
    """Hold one cover before the call. Returns the render id, or None when
    the month's covers are used. limit None is unlimited (an owner login):
    the row is still written, so the owner's monthly count includes it,
    but it counts against nobody's allowance."""
    rid = uuid.uuid4().hex
    mon = month()
    with db.get_db() as conn:
        # IMMEDIATE takes the write lock before the count, so a second tab
        # or a double click waits here and then sees this row.
        conn.execute("BEGIN IMMEDIATE")
        if limit is not None and _used(conn, account_id, mon) >= int(limit):
            conn.rollback()
            return None
        conn.execute(
            "INSERT INTO cover_renders (id, account_id, actor_id, month, status,"
            " counts, created_at) VALUES (?,?,?,?,?,?,?)",
            (rid, str(account_id), str(actor_id or account_id), mon, "pending",
             0 if limit is None else 1, _now().isoformat(timespec="seconds")))
    return rid


def finish(render_id, status, path=None):
    """Close a reservation. Anything but done gives the cover back, because
    only done and fresh pending rows are counted."""
    if status not in STATUSES or status == "pending":
        status = "failed"
    with db.get_db() as conn:
        conn.execute(
            "UPDATE cover_renders SET status = ?, path = ?, finished_at = ?"
            " WHERE id = ? AND status = 'pending'",
            (status, path, _now().isoformat(timespec="seconds"), render_id))


def status_for(account, owner=False, demo=False):
    """What the Cover Studio says about the generator for this account."""
    engine = "openai" if configured() else "pollinations"
    out = {"engine": engine, "model": MODEL, "demo": bool(demo),
           "unlimited": bool(owner), "resets": reset_date(),
           "limit": None, "used": 0, "left": None}
    if engine != "openai" or demo or not account:
        return out
    n = used(account["id"])
    out["used"] = n
    if not owner:
        limit = allowance(account.get("plan") or "artist")
        out["limit"] = limit
        out["left"] = max(0, limit - n)
    return out


def month_summary(mon=None):
    """Every account's renders this month, for the owner's Settings card."""
    mon = mon or month()
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM cover_renders WHERE month = ?"
            " GROUP BY status", (mon,)).fetchall()
        accounts = conn.execute(
            "SELECT COUNT(DISTINCT account_id) FROM cover_renders"
            " WHERE month = ? AND status = 'done'", (mon,)).fetchone()[0]
    by = {s: 0 for s in STATUSES}
    for r in rows:
        by[r["status"]] = int(r["n"])
    return {"month": mon, "done": by["done"], "refused": by["refused"],
            "failed": by["failed"], "timeout": by["timeout"],
            "pending": by["pending"], "accounts": int(accounts or 0),
            "cost_usd": "%.2f" % (PRICE_PER_RENDER_USD * by["done"]),
            "price_usd": str(PRICE_PER_RENDER_USD), "price_source": PRICE_SOURCE,
            "key_set": configured(), "model": MODEL,
            "allowances": allowances(), "defaults": dict(DEFAULT_ALLOWANCE),
            "resets": reset_date()}

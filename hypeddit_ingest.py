"""Hypeddit into the Fan CRM (owner, 2026-09-19: "build the hypeddit
webhook into fan crm").

Hypeddit > Account Settings > Automation holds one field, a webhook URL
meant for Zapier's Catch Hook, IFTTT or Make. When the artist pastes a URL
and presses Next, Hypeddit answers "Successfully Updated" and sends a TEST
record to it. From then on, once a fan completes every step of a Download
Gate, Link Gate, Pre-Save or Smart Link, Hypeddit POSTs that fan to the
URL. Zapier users map "Email Address" and "Name" from it; the exact JSON or
form field names are not published anywhere, so this receiver is tolerant
about where the email and name sit and keeps the raw shape of the last
deliveries so the artist (and we) can check the mapping against what
really arrived.

Everything here runs without a request: the route in app.py hands over a
plain dict and this module does the rest, so the logic is testable on its
own. Storage is app_kv:

  hypeddit_token:<user_id>   -> the account's token (its webhook address)
  hypeddit_user:<token>      -> the account, for the route's lookup
  hypeddit_log:<user_id>     -> JSON list, the last LOG_KEEP deliveries
  hypeddit_count:<user_id>   -> fans that came in through Hypeddit
  hypeddit_last:<user_id>    -> when the last delivery of any kind arrived
  hypeddit_day:<user_id>:<YYYY-MM-DD> -> deliveries today, for the cap
"""
import json
import re
import secrets
from datetime import datetime, timezone

import db as store
import links_engine
import links_store as mls

KEY_TOKEN = "hypeddit_token:%s"
KEY_USER = "hypeddit_user:%s"
KEY_LOG = "hypeddit_log:%s"
KEY_COUNT = "hypeddit_count:%s"
KEY_LAST = "hypeddit_last:%s"
KEY_DAY = "hypeddit_day:%s:%s"

LOG_KEEP = 10           # raw deliveries kept per account
VALUE_CUT = 200         # characters kept of each raw value
DAILY_CAP = 2000        # deliveries an account accepts per UTC day

TAG = "hypeddit"
CONSENT_TYPE = "hypeddit_gate"

# The kinds a delivery can be logged as.
KIND_TEST, KIND_FAN, KIND_UNUSABLE, KIND_DROPPED = "test", "fan", "unusable", "dropped"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]+$")
_EMAIL_IN_TEXT = re.compile(r"[^@\s\"']+@[^@\s\"']+\.[^@\s\"'.]+")

# Placeholder addresses Hypeddit's connection test (or a person poking the
# URL) would carry. None of these is a fan.
# example.net is left out on purpose: it is what this codebase's own tests
# file real fans under, and Hypeddit's test uses example.com.
_PLACEHOLDER_DOMAINS = ("example.com", "hypeddit.com", "test.com", "email.com", "domain.com")
_PLACEHOLDER_LOCALS = ("test", "testing", "sample", "example", "demo", "webhook", "zapier")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# --- tokens --------------------------------------------------------------------

def get_or_create_token(user_id):
    """The account's webhook token; minted on first ask."""
    token = store.get_kv(KEY_TOKEN % user_id)
    if token:
        return token
    token = secrets.token_urlsafe(24)
    store.set_kv(KEY_TOKEN % user_id, token)
    store.set_kv(KEY_USER % token, str(user_id))
    return token


def rotate_token(user_id):
    """A new address; the old one stops working at once (its reverse key
    goes). Nothing else about the connection changes: the log and the
    count are the account's, not the address's."""
    old = store.get_kv(KEY_TOKEN % user_id)
    token = secrets.token_urlsafe(24)
    store.set_kv(KEY_TOKEN % user_id, token)
    store.set_kv(KEY_USER % token, str(user_id))
    if old and old != token:
        store.delete_kv(KEY_USER % old)
    return token


def user_for_token(token):
    """The account a token belongs to, or None. The token must also still
    be the account's current one: a stale reverse key is not a door."""
    token = (token or "").strip()
    if not token or len(token) > 64:
        return None
    user_id = store.get_kv(KEY_USER % token)
    if not user_id:
        return None
    if store.get_kv(KEY_TOKEN % user_id) != token:
        return None
    return user_id


def webhook_url(host, token):
    """The address the artist pastes into Hypeddit. Always https: Hypeddit
    calls from its servers, and every deployed service sits behind TLS."""
    return "https://%s/webhooks/hypeddit/%s" % (host, token)


# --- reading a delivery ----------------------------------------------------------

def _norm_key(key):
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _flatten(payload, prefix="", depth=0, out=None):
    """One level of dotted keys per nesting, three deep at most: a Zapier
    style body may wrap the fan in {"data": {...}} or {"fan": {...}}."""
    if out is None:
        out = {}
    if isinstance(payload, dict):
        for k, v in payload.items():
            name = ("%s.%s" % (prefix, k)) if prefix else str(k)
            if isinstance(v, (dict, list)) and depth < 3:
                _flatten(v, name, depth + 1, out)
            else:
                out[name] = v
    elif isinstance(payload, list):
        for i, v in enumerate(payload):
            name = ("%s.%d" % (prefix, i)) if prefix else str(i)
            if isinstance(v, (dict, list)) and depth < 3:
                _flatten(v, name, depth + 1, out)
            else:
                out[name] = v
    return out


def valid_email(value):
    v = str(value or "").strip().lower()
    return v if _EMAIL_RE.match(v) else ""


def extract(payload):
    """What a delivery says about the fan: {email, name, link, extra}.

    The email is taken from any key that contains "email" however it is
    spelled (email, email_address, "Email Address", fan_email, e-mail,
    nested data.email), the first one that holds a valid address. Failing
    that, any value anywhere that is a valid address. The name comes from
    name / fan_name / full_name, or first + last. The link is whichever
    field names the gate, link, title or URL the fan came through. A
    delivery with no valid address has email "" and cannot be filed.
    """
    flat = _flatten(payload if isinstance(payload, (dict, list)) else {})
    email, name, first, last, link = "", "", "", "", ""
    extra = {}
    for key, value in flat.items():
        leaf = _norm_key(key.split(".")[-1])
        text = value if isinstance(value, str) else json.dumps(value) if value is not None else ""
        text = text.strip()
        if "email" in leaf or leaf == "mail":
            if not email and valid_email(text):
                email = valid_email(text)
                continue
        if leaf in ("name", "fanname", "fullname", "username", "subscribername", "contactname"):
            if not name and text:
                name = text
                continue
        if leaf in ("firstname", "first", "givenname", "fname"):
            first = first or text
            continue
        if leaf in ("lastname", "last", "surname", "familyname", "lname"):
            last = last or text
            continue
        if leaf in ("link", "gate", "gatename", "linkname", "title", "url", "linkurl",
                    "gateurl", "campaign", "campaignname", "release", "track"):
            if not link and text:
                link = text
                continue
        extra[key] = value
    if not email:
        for value in flat.values():
            if isinstance(value, str):
                if valid_email(value):
                    email = valid_email(value)
                    break
    if not name and (first or last):
        name = ("%s %s" % (first, last)).strip()
    return {"email": email, "name": name[:120], "link": link[:200], "extra": extra}


def is_test(payload):
    """Hypeddit's connection test, or anything else that is plainly not a
    fan: a placeholder address (test@, anything at example.com or
    hypeddit.com), or a field that says so (test: true, event: test)."""
    flat = _flatten(payload if isinstance(payload, (dict, list)) else {})
    for key, value in flat.items():
        leaf = _norm_key(key.split(".")[-1])
        if leaf in ("test", "istest", "testmode", "sample", "issample"):
            if value in (True, 1, "1", "true", "True", "yes", "TRUE"):
                return True
        if leaf in ("type", "event", "kind", "eventtype", "action") and \
                str(value or "").strip().lower() in ("test", "webhook_test", "ping", "sample"):
            return True
    email = extract(payload)["email"]
    if not email:
        return False
    local, _, domain = email.partition("@")
    if domain in _PLACEHOLDER_DOMAINS or domain.endswith(".example.com"):
        return True
    if local in _PLACEHOLDER_LOCALS or local.startswith("test@") or local.startswith("test+") \
            or local.startswith("test."):
        return True
    return False


# --- the log -------------------------------------------------------------------

def mask_email(email):
    """a***@domain: enough to tell whose delivery it was, not the address."""
    email = str(email or "")
    local, at, domain = email.partition("@")
    if not at:
        return email[:1] + "***" if email else ""
    return "%s***@%s" % (local[:1], domain)


def _mask_text(text):
    return _EMAIL_IN_TEXT.sub(lambda m: mask_email(m.group(0)), text)


def _raw_fields(payload):
    """The delivery as the artist may see it: every key, each value cut to
    VALUE_CUT characters, every address inside masked."""
    flat = _flatten(payload if isinstance(payload, (dict, list)) else {})
    fields = []
    for key, value in list(flat.items())[:40]:
        text = value if isinstance(value, str) else json.dumps(value) if value is not None else ""
        fields.append({"key": str(key)[:80], "value": _mask_text(text)[:VALUE_CUT]})
    return fields


def _read_log(user_id):
    try:
        log = json.loads(store.get_kv(KEY_LOG % user_id) or "[]")
    except ValueError:
        log = []
    return log if isinstance(log, list) else []


def record(user_id, kind, payload, note=""):
    """Append one delivery to the account's log (newest first, LOG_KEEP
    kept) and stamp the last-received time."""
    at = _now()
    entry = {"at": at, "kind": kind, "fields": _raw_fields(payload)}
    if note:
        entry["note"] = note[:200]
    log = [entry] + _read_log(user_id)
    store.set_kv(KEY_LOG % user_id, json.dumps(log[:LOG_KEEP]))
    store.set_kv(KEY_LAST % user_id, at)
    return entry


def status(user_id):
    """What the Fan CRM panel shows."""
    log = _read_log(user_id)
    return {"count": int(store.get_kv(KEY_COUNT % user_id) or 0),
            "last": store.get_kv(KEY_LAST % user_id) or "",
            "connected": bool(log),
            "log": log,
            "last_delivery": log[0] if log else None}


# --- filing --------------------------------------------------------------------

def _over_cap(user_id):
    return store.kv_incr(KEY_DAY % (user_id, _today())) > DAILY_CAP


def file_fan(user_id, email, name, received=None):
    """File one fan exactly as the smart-link subscribe route does, with no
    campaign: upsert, the hypeddit tag, one hypeddit_gate consent (never a
    second for the same fan), a capture counted, intent scored, the artist
    told. Returns (fan_id, newly_from_hypeddit)."""
    received = received or _now()
    fan_id = mls.upsert_fan(user_id, email, None, name or "")
    mls.add_fan_tags(fan_id, [TAG])
    new_here = False
    if mls.find_consent(fan_id, CONSENT_TYPE) is None:
        mls.add_consent(fan_id, None, CONSENT_TYPE,
                        "Gave their email address on the artist's Hypeddit gate, "
                        "pre-save or smart link (received %s)." % received)
        new_here = True
    mls.bump_fan(fan_id, "total_captures")
    fan = mls.get_fan(fan_id)
    score, level = links_engine.calculate_fan_intent(fan)
    mls.set_fan_intent(fan_id, score, level)
    store.notify(user_id, "fan", "New fan from Hypeddit: %s" % email,
                 "Consent logged, intent scored.", "/links/fans")
    return fan_id, new_here


def receive(user_id, payload):
    """One delivery for one account. Returns the kind it was logged as.

    Order: the daily cap (a runaway sender is dropped and the drop is
    logged), then Hypeddit's test record, then a fan, then a delivery
    with nothing usable in it. The very first delivery an account ever
    receives with no address in it is taken as Hypeddit's own test, which
    is what arrives right after the artist presses Next; after that, a
    delivery without an address is logged as unusable so it stands out.
    """
    if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
        payload = payload[0]
    if not isinstance(payload, (dict, list)):
        payload = {}
    if _over_cap(user_id):
        record(user_id, KIND_DROPPED, payload,
               "More than %d deliveries today; this one was not filed." % DAILY_CAP)
        return KIND_DROPPED
    if is_test(payload):
        record(user_id, KIND_TEST, payload)
        return KIND_TEST
    found = extract(payload)
    if not found["email"]:
        if not _read_log(user_id):
            record(user_id, KIND_TEST, payload, "First delivery, no address: taken as Hypeddit's test.")
            return KIND_TEST
        record(user_id, KIND_UNUSABLE, payload, "No email address was found in this delivery.")
        return KIND_UNUSABLE
    entry = record(user_id, KIND_FAN, payload)
    _, new_here = file_fan(user_id, found["email"], found["name"], entry["at"])
    if new_here:
        store.kv_incr(KEY_COUNT % user_id)
    return KIND_FAN

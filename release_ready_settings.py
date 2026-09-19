"""The owner's settings for Release-Ready, and what RoEx credits it spends.

Modelled on soundcharts_budget.py: plain app_kv values with defaults, and
monthly counters kept with db.kv_incr so two workers counting at once never
lose a count.

WHAT THE OWNER SETS (Settings > Release-Ready, owner only)
  rr_open                    Open to artists. Off until RoEx answers the
                             licence and naming questions; owner logins can
                             use the page while it is off.
  rr_price_master_cents      Price per full master. 699 ($6.99), the owner's
                             price (2026-09-19). Never written into a template.
  rr_price_recombine_cents   Price per vocal-and-beat master. 699.
  rr_monthly_credit_budget   RoEx credits a month for AUTOMATIC spending (the
                             mix report on upload). Reports pause at the cap.
  rr_artist_monthly_reports  Automatic reports per artist account a month.
                             Past that a report waits for a button press,
                             which still counts against the budget.
  rr_auto_analysis           Run the mix report on every mix upload.
  rr_credit_usd              What one RoEx credit costs the owner, for the
                             cost estimates on the admin desk.
  rr_previews_per_file       Free 30-second previews per uploaded file.
  rr_previews_per_day        Free previews per artist account per day.

WHAT IS COUNTED
  rr_credits:<YYYY-MM>:auto      credits reserved for automatic reports
  rr_credits:<YYYY-MM>:paid      credits for masters the artist paid for
  rr_reports:<YYYY-MM>:<user>    automatic reports per artist
  rr_report_runs:<YYYY-MM>:<src> presses of "Get the mix report" per upload,
                                 capped at MANUAL_REPORTS_PER_FILE, so a
                                 report that keeps failing (and may be
                                 charged each time) cannot be re-run forever
These are our own estimates from RoEx's price list: no RoEx endpoint says
what was actually charged, and the admin desk says so.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import db

DEFAULTS = {
    "rr_open": "0",
    "rr_price_master_cents": "699",
    "rr_price_recombine_cents": "699",
    "rr_monthly_credit_budget": "1000",
    "rr_artist_monthly_reports": "10",
    "rr_auto_analysis": "1",
    "rr_credit_usd": "0.01",
    "rr_previews_per_file": "6",
    "rr_previews_per_day": "20",
}

# Presses of "Get the mix report" (or "Run the report again") per upload per
# month. RoEx may charge for a report that fails, so re-runs are finite.
MANUAL_REPORTS_PER_FILE = 3

PRICE_MIN_CENTS = 50
PRICE_MAX_CENTS = 9900
PRICE_KEYS = {"master": "rr_price_master_cents", "recombine": "rr_price_recombine_cents"}


def month(now=None):
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


def _raw(key):
    val = db.get_kv(key)
    return DEFAULTS[key] if val in (None, "") else val


def _int(key, floor=0):
    try:
        return max(floor, int(_raw(key)))
    except (TypeError, ValueError):
        return int(DEFAULTS[key])


def _on(key):
    return str(_raw(key)).strip().lower() in ("1", "on", "true", "yes")


# --- reads ----------------------------------------------------------------------

def is_open():
    return _on("rr_open")


def available():
    """Artists can use Release-Ready right now: RoEx connected, private
    storage connected, and opened by the owner."""
    import blob_store
    import roex_client
    return bool(roex_client.configured() and blob_store.configured() and is_open())


def auto_analysis():
    return _on("rr_auto_analysis")


def price_cents(kind):
    """What the artist pays, in cents, for 'master' or 'recombine'."""
    cents = _int(PRICE_KEYS["recombine" if kind == "recombine" else "master"])
    if not PRICE_MIN_CENTS <= cents <= PRICE_MAX_CENTS:
        return int(DEFAULTS[PRICE_KEYS["master"]])
    return cents


def price_display(kind):
    cents = price_cents(kind)
    return "%d.%02d" % (cents // 100, cents % 100)


def budget():
    return _int("rr_monthly_credit_budget")


def artist_cap():
    return _int("rr_artist_monthly_reports")


def previews_per_file():
    return _int("rr_previews_per_file", floor=1)


def previews_per_day():
    return _int("rr_previews_per_day", floor=1)


def credit_usd():
    try:
        val = Decimal(str(_raw("rr_credit_usd")))
    except (InvalidOperation, TypeError):
        val = Decimal(DEFAULTS["rr_credit_usd"])
    return val if val >= 0 else Decimal(DEFAULTS["rr_credit_usd"])


# --- the owner's form -------------------------------------------------------------

def parse_dollars(text):
    """'6.99' -> 699. None for anything that is not a plain price between
    $0.50 and $99.00 ('7,49' is refused rather than guessed)."""
    text = (text or "").strip().lstrip("$").strip()
    if not text or "," in text:
        return None
    try:
        val = Decimal(text)
    except InvalidOperation:
        return None
    if val != val.quantize(Decimal("0.01")):
        return None
    cents = int(val * 100)
    return cents if PRICE_MIN_CENTS <= cents <= PRICE_MAX_CENTS else None


def _parse_int(text, lo, hi):
    try:
        n = int((text or "").strip().replace(",", ""))
    except ValueError:
        return None
    return n if lo <= n <= hi else None


def save_from_form(form):
    """Apply the owner's Settings card. Returns a list of the fields that
    were refused (nothing is saved for those; the rest are)."""
    errors = []
    for kind, field in (("master", "price_master"), ("recombine", "price_recombine")):
        if field in form:
            cents = parse_dollars(form.get(field))
            if cents is None:
                errors.append(field)
            else:
                db.set_kv(PRICE_KEYS[kind], str(cents))
    for key, field, lo, hi in (("rr_monthly_credit_budget", "budget", 0, 1_000_000),
                               ("rr_artist_monthly_reports", "artist_cap", 0, 1000),
                               ("rr_previews_per_file", "previews_per_file", 1, 50),
                               ("rr_previews_per_day", "previews_per_day", 1, 500)):
        if field in form:
            n = _parse_int(form.get(field), lo, hi)
            if n is None:
                errors.append(field)
            else:
                db.set_kv(key, str(n))
    if "credit_usd" in form:
        try:
            val = Decimal((form.get("credit_usd") or "").strip().lstrip("$"))
        except InvalidOperation:
            val = None
        if val is None or not Decimal("0") < val <= Decimal("1"):
            errors.append("credit_usd")
        else:
            db.set_kv("rr_credit_usd", str(val))
    # Checkboxes: present means on. The form sends a hidden marker so an
    # unticked box can be told apart from a form that did not carry it.
    if form.get("switches") == "1":
        db.set_kv("rr_open", "1" if form.get("open") else "0")
        db.set_kv("rr_auto_analysis", "1" if form.get("auto_analysis") else "0")
    return errors


# --- the monthly counters ------------------------------------------------------------

def _auto_key(mon=None):
    return "rr_credits:%s:auto" % (mon or month())


def _paid_key(mon=None):
    return "rr_credits:%s:paid" % (mon or month())


def _artist_key(user_id, mon=None):
    return "rr_reports:%s:%s" % (mon or month(), user_id)


def counts(mon=None):
    auto = int(db.get_kv(_auto_key(mon)) or 0)
    paid = int(db.get_kv(_paid_key(mon)) or 0)
    return {"auto": auto, "paid": paid, "total": auto + paid}


def artist_reports(user_id, mon=None):
    return int(db.get_kv(_artist_key(user_id, mon)) or 0)


def reserve_auto(user_id, credits, manual=False):
    """Hold credits for an automatic spend before it happens.

    Returns (True, month, counted_for_artist) or (False, reason, False)
    with reason "budget" or "artist_cap". A refused reservation leaves
    every counter as it was. A button press (manual=True) skips the
    per-artist cap but never the owner's budget."""
    mon = month()
    n = db.kv_incr(_auto_key(mon), credits)
    if n > budget():
        db.kv_incr(_auto_key(mon), -credits)
        return False, "budget", False
    if manual or user_id is None:
        return True, mon, False
    m = db.kv_incr(_artist_key(user_id, mon), 1)
    if m > artist_cap():
        db.kv_incr(_artist_key(user_id, mon), -1)
        db.kv_incr(_auto_key(mon), -credits)
        return False, "artist_cap", False
    return True, mon, True


def release_auto(user_id, credits, mon, counted_for_artist):
    """Give a reservation back, in the month it was taken. Only when RoEx
    certainly did not charge: nothing was sent, or RoEx refused the request
    before processing it (400, 404, 429). A timeout, a 5xx and a failure
    RoEx reports all keep it: RoEx may have charged, and nothing in its
    documentation says those are free."""
    if not credits or not mon:
        return
    db.kv_incr(_auto_key(mon), -int(credits))
    if counted_for_artist and user_id:
        db.kv_incr(_artist_key(user_id, mon), -1)


def budget_left():
    return max(0, budget() - counts()["auto"])


def _manual_key(source_id, mon=None):
    return "rr_report_runs:%s:%s" % (mon or month(), source_id)


def manual_runs_left(source_id, mon=None):
    used = int(db.get_kv(_manual_key(source_id, mon)) or 0)
    return max(0, MANUAL_REPORTS_PER_FILE - used)


def take_manual_run(source_id):
    """Count one press of the report button for this upload. Returns the
    month it was counted in, or None when this month's presses are used."""
    mon = month()
    if db.kv_incr(_manual_key(source_id, mon), 1) > MANUAL_REPORTS_PER_FILE:
        db.kv_incr(_manual_key(source_id, mon), -1)
        return None
    return mon


def give_manual_run_back(source_id, mon):
    """The press never reached RoEx (the budget refused it): uncounted."""
    if mon:
        db.kv_incr(_manual_key(source_id, mon), -1)


def record_paid(credits, mon=None):
    if credits:
        db.kv_incr(_paid_key(mon), int(credits))


def alert_once(kind, send, period="hour"):
    """Call send() at most once per hour (or per month) for this kind of
    alert, however many workers see the same trouble. Returns True when
    it was sent. An alert about one paid master carries the job in its
    kind ("paid_credits:<job>"), so a general alert in the same hour can
    never silence it."""
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m") if period == "month" else now.strftime("%Y-%m-%dT%H")
    if db.kv_incr("rr_alert:%s:%s" % (kind, stamp), 1) != 1:
        return False
    try:
        send()
    except Exception:
        return False
    return True


def summary():
    """Everything the owner's Settings card and the admin desk show."""
    c = counts()
    usd = credit_usd()
    return {
        "month": month(),
        "open": is_open(),
        "auto_analysis": auto_analysis(),
        "price_master": price_display("master"),
        "price_recombine": price_display("recombine"),
        "price_master_cents": price_cents("master"),
        "price_recombine_cents": price_cents("recombine"),
        "budget": budget(),
        "used_auto": c["auto"],
        "used_paid": c["paid"],
        "used_total": c["total"],
        "budget_left": max(0, budget() - c["auto"]),
        "paused": c["auto"] >= budget(),
        "artist_cap": artist_cap(),
        "previews_per_file": previews_per_file(),
        "previews_per_day": previews_per_day(),
        "credit_usd": str(usd),
        "cost_estimate_usd": "%.2f" % (Decimal(c["total"]) * usd),
    }

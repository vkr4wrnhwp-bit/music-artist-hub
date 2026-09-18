"""Who is filling in the sign-up form: a person, or a script?

Sign-up was open until 2026-09-17 and hundreds of Fan accounts registered
themselves. Reopening it for advertising would be worse, because traffic
brings scripts, so the door gets four cheap checks first. None of them
asks a person to prove anything: no puzzle, no pictures of traffic lights,
nothing that costs a real artist a second of their day.

  A hidden field    a browser never shows it, so a person never fills it.
                    A script fills every field it can find.
  A signed clock    a person reads the form and types a password. Under a
                    few seconds is a machine. The stamp is signed, so it
                    cannot be back-dated by whoever is posting.
  One at a time     a burst of accounts from one address inside a minute is
                    not four artists discovering the product together.
  Throwaway mail    the domains that exist to make an address that dies in
                    ten minutes.

Every refusal is a reason, and the reason is recorded rather than shown:
telling a script exactly which check caught it is telling it how to pass.
The person sees one plain sentence and a way to reach a human, because a
real artist WILL occasionally trip one of these and must not be stranded.

This is not a wall. It is the difference between a form that collects
hundreds of junk accounts and one that collects a few.
"""

import os
import time

# A browser never shows it, so a person never fills it. Named like a field
# a form-filler would want to complete.
HONEYPOT = "company_website"
STAMP_FIELD = "form_opened"
SALT = "street-banker-signup-guard-v1"

# Nobody reads a sign-up form and chooses a password faster than this.
MIN_SECONDS = 3.0
# Past this the stamp has stopped being evidence of anything. A form left
# open overnight is a stale tab, not an attack, so it is asked for again
# rather than refused.
MAX_SECONDS = 12 * 60 * 60
# One address, one account, per window. A second person on the same office
# or cafe connection waits a minute; a script trying two hundred does not
# get past the first.
RATE_WINDOW = 60.0
# Kept small so the table cannot grow without limit on a public site.
RATE_MAX_TRACKED = 4096

# The domains that exist to make an address that dies in ten minutes. A
# short list on purpose: a long one is out of date the day it is written,
# and the signed clock and the hidden field do most of the work. Extend it
# on a deployment with SIGNUP_BLOCKED_DOMAINS, comma separated.
THROWAWAY = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.net", "sharklasers.com",
    "10minutemail.com", "tempmail.com", "temp-mail.org", "throwawaymail.com",
    "yopmail.com", "trashmail.com", "getnada.com", "dispostable.com",
    "fakeinbox.com", "maildrop.cc", "mailnesia.com", "spamgourmet.com",
    "tempinbox.com", "mytemp.email", "emailondeck.com", "moakt.com",
}

_seen = {}


def blocked_domains():
    extra = {d.strip().lower() for d in
             (os.environ.get("SIGNUP_BLOCKED_DOMAINS") or "").split(",") if d.strip()}
    return THROWAWAY | extra


def enabled():
    """On wherever the form faces the public, which is every deployed
    service. Off on a laptop and in the tests unless one turns it on, so
    three thousand tests do not each have to carry a signed stamp."""
    mode = (os.environ.get("SIGNUP_GUARD") or "").strip().lower()
    if mode in ("on", "off"):
        return mode == "on"
    return bool(os.environ.get("RENDER"))


def _serializer(secret):
    from itsdangerous import URLSafeTimedSerializer
    return URLSafeTimedSerializer(secret or "street-banker-dev", salt=SALT)


def stamp(secret, now=None):
    """The value the form carries, saying when it was handed out. Signed, so
    a script cannot post a form it never asked for."""
    return _serializer(secret).dumps({"t": int(now or time.time())})


def _opened_at(value, secret):
    if not value:
        return None
    try:
        data = _serializer(secret).loads(value, max_age=MAX_SECONDS)
    except Exception:
        return None
    return data.get("t") if isinstance(data, dict) else None


def client_ip(headers, remote_addr):
    forwarded = (headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return forwarded or (remote_addr or "?")


def _rate_ok(ip, now):
    """One from this address per window. Prunes as it goes, so the table
    cannot grow one entry per visitor for the life of the process."""
    if len(_seen) > RATE_MAX_TRACKED:
        cutoff = now - RATE_WINDOW
        for key in [k for k, v in _seen.items() if v < cutoff]:
            _seen.pop(key, None)
        if len(_seen) > RATE_MAX_TRACKED:
            _seen.clear()
    last = _seen.get(ip)
    if last is not None and now - last < RATE_WINDOW:
        return False
    _seen[ip] = now
    return True


def judge(form, ip, secret, now=None, email=None):
    """None when this looks like a person. Otherwise a short reason, for the
    log and never for the screen.

    `form` is anything with .get. `email` is read from the form when it is
    not passed. Nothing here touches the database or sends anything.
    """
    if not enabled():
        return None
    now = float(now or time.time())

    if (form.get(HONEYPOT) or "").strip():
        return "filled the hidden field"

    opened = _opened_at(form.get(STAMP_FIELD), secret)
    if opened is None:
        return "no signed form stamp"
    # The age is read from the payload rather than the signature, because
    # that is the clock the form was actually handed out on. A stamp older
    # than the window, or one from the future, has stopped being evidence
    # of anything; the person reloads and carries on.
    age = now - opened
    if age > MAX_SECONDS or age < -MIN_SECONDS:
        return "no signed form stamp"
    if age < MIN_SECONDS:
        return "submitted in %.1fs" % age

    address = (email if email is not None else form.get("email") or "").strip().lower()
    domain = address.rsplit("@", 1)[-1] if "@" in address else ""
    if domain and domain in blocked_domains():
        return "throwaway domain %s" % domain

    if not _rate_ok(ip, now):
        return "second account from %s inside %ds" % (ip, int(RATE_WINDOW))
    return None


# One sentence for the person, whichever check caught them. Saying which
# one would tell a script how to pass it, and a real artist who trips a
# check needs a way through rather than a diagnosis.
REFUSAL = ("That did not go through. If you are a person and not a script, "
           "we are sorry: wait a moment and try again, or write to us and we "
           "will make the account ourselves.")


def reset_for_tests():
    _seen.clear()

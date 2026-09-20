"""Error reporting to Sentry, when a DSN is set and the SDK is installed.

Owner, 2026-09-19: "I believe Sentry is set up." It was set in Render and
read by nothing: no sentry in requirements.txt, no init anywhere. This is
the reader.

Three rules:

  - Errors only. traces_sample_rate is 0, so no performance sampling and
    no per-request overhead beyond the exception hook.
  - No personal data by default (send_default_pii=False) and a scrub on
    every event before it leaves: request cookies, Authorization headers,
    and any key whose name says token, secret, password, api_key or dsn.
  - The DSN is never logged or printed, here or anywhere. configured()
    answers yes or no and nothing more.

With SENTRY_DSN unset, init() returns without importing the SDK, so a
checkout without sentry-sdk installed boots exactly as before.
"""

import os

DSN_VAR = "SENTRY_DSN"

# Substrings that mark a key as a credential. Matched case-insensitively
# against every key at every level of the event.
SENSITIVE_KEY_PARTS = ("token", "secret", "password", "api_key", "apikey", "dsn")
SCRUBBED = "[scrubbed]"


def configured():
    """Whether a DSN is present. A presence check, like the other readiness
    rows: it proves somebody typed a value, not that Sentry accepts it."""
    return bool((os.environ.get(DSN_VAR) or "").strip())


def environment():
    """Where this process runs, for the event's environment tag."""
    for var in ("RENDER_SERVICE_NAME", "SB_ENV"):
        value = (os.environ.get(var) or "").strip()
        if value:
            return value
    return "local"


def release():
    """The deployed commit, when Render tells us; None otherwise so the SDK
    leaves the field unset rather than sending an empty string."""
    return (os.environ.get("RENDER_GIT_COMMIT") or "").strip() or None


def _sensitive(key):
    lowered = str(key).lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _scrub(value):
    """Walk dicts and lists; replace the value of any sensitive key."""
    if isinstance(value, dict):
        out = {}
        for key, inner in value.items():
            out[key] = SCRUBBED if _sensitive(key) else _scrub(inner)
        return out
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def before_send(event, hint=None):
    """Strip what must not leave the box.

    The request block is scrubbed by name first (cookies, and the
    Authorization header whatever its case), then the whole event is walked
    for sensitive keys, so a token in a query string, a form field or
    an extra lands as [scrubbed] too.
    """
    if not isinstance(event, dict):
        return event
    request = event.get("request")
    if isinstance(request, dict):
        request = dict(request)
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                name: (SCRUBBED if name.lower() in ("authorization", "cookie",
                                                    "x-csrf-token") else value)
                for name, value in headers.items()
            }
        event = dict(event, request=request)
    return _scrub(event)


def init(app):
    """Start the SDK for this app, or do nothing, and say which.

    Returns True when Sentry was initialised. False when no DSN is set or
    the SDK is not installed; neither is an error, and neither is logged
    with the DSN in it.
    """
    dsn = (os.environ.get(DSN_VAR) or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
    except ImportError:
        return False
    kwargs = {
        "dsn": dsn,
        "integrations": [FlaskIntegration()],
        "send_default_pii": False,
        "traces_sample_rate": 0,
        "environment": environment(),
        "before_send": before_send,
    }
    rel = release()
    if rel:
        kwargs["release"] = rel
    # A malformed DSN must never stop the app from booting: error
    # reporting is a helper, not a dependency. The message names the
    # variable, never its value.
    try:
        sentry_sdk.init(**kwargs)
    except Exception as exc:  # BadDsn and anything else the SDK raises
        app.logger.warning("Sentry not started: %s is not usable (%s)",
                           DSN_VAR, exc.__class__.__name__)
        return False
    app.config["SENTRY_ENABLED"] = True
    return True

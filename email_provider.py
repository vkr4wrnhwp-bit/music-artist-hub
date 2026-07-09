"""Transactional email via Resend — release-day notes to captured fans.

Env-gated like every other provider: without RESEND_API_KEY nothing
sends and nothing pretends to. The default sender is Resend's shared
test address (delivers only to the account owner's own inbox) until
EMAIL_FROM is set to an address on a domain verified in Resend.
`_http` is the seam tests monkeypatch.
"""

import json
import os
import urllib.request

_TIMEOUT = 12


def configured():
    return bool(os.environ.get("RESEND_API_KEY"))


def sender():
    return os.environ.get("EMAIL_FROM") or "Street Banker <onboarding@resend.dev>"


def _http(url, payload, headers):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        body = resp.read()
        return json.loads(body.decode("utf-8")) if body else {}


def send(to, subject, html):
    """One email. True only when Resend accepted it."""
    if not configured() or not to:
        return False
    try:
        out = _http("https://api.resend.com/emails", {
            "from": sender(), "to": [to], "subject": subject, "html": html,
        }, {
            "Authorization": "Bearer " + os.environ["RESEND_API_KEY"],
            "Content-Type": "application/json",
        })
        return bool(out.get("id"))
    except Exception:
        return False


def release_email_html(campaign_title, artist_name, listen_url, cover_url=""):
    """Branded release-day note. Plain, readable, one clear button."""
    cover = ('<img src="%s" alt="" width="120" style="border-radius:12px;display:block;margin:0 auto 16px;">'
             % cover_url) if cover_url else ""
    return (
        '<div style="background:#0f0e0c;padding:32px 16px;font-family:Arial,sans-serif;">'
        '<div style="max-width:480px;margin:0 auto;background:#161412;border:1px solid #3a2f1a;'
        'border-radius:16px;padding:32px;text-align:center;">'
        + cover +
        '<p style="color:#c9a24a;font-size:11px;letter-spacing:3px;margin:0;">OUT NOW</p>'
        '<h1 style="color:#f5f1e8;font-size:24px;margin:8px 0 4px;">%s</h1>'
        '<p style="color:#b8b0a0;font-size:14px;margin:0 0 24px;">%s</p>'
        '<a href="%s" style="display:inline-block;background:#d8b25a;color:#1c1302;'
        'font-weight:bold;font-size:14px;padding:12px 28px;border-radius:10px;'
        'text-decoration:none;">Listen Now</a>'
        '<p style="color:#6b6355;font-size:11px;margin:24px 0 0;">You asked to be notified '
        'about this release. Links open your preferred platform.</p>'
        '</div></div>'
    ) % (campaign_title, artist_name, listen_url)

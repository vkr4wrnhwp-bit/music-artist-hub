"""Fan email and fan links: the signed tokens that tie a click in an email
back to the fan it was sent to.

THE FAN LINK TOKEN (?f=)
------------------------
The Fan CRM's Visits and Clicks columns sat at 0 for every fan until
2026-09-23: the smart link page and its /go/ redirect recorded every view
and click anonymously, so nothing could credit one to a person. Now each
link the app puts in an email to a fan carries `?f=<token>`, a signed
fan id. A page view carrying a valid token for a fan of that page's own
account is that fan's visit; a click carrying it is that fan's click.

  * Signed with the app's secret key (itsdangerous, its own salt), so a
    fan id cannot be guessed or edited into somebody else's.
  * No expiry: a release-day email is read weeks later, and the link in
    it should still say who clicked.
  * Nothing is stored on the fan's device. The token rides in the link
    and the page passes it on to its own service buttons, so a fan is
    known for the visit their email started, and for the clicks after
    they sign up on the page, and at no other time.

The token identifies; it authorises nothing. The worst a copied one can
do is credit a visit to the fan it names.
"""

from itsdangerous import BadSignature, URLSafeSerializer

_FAN_LINK_SALT = "fan-link"

# A fan who reloads the page, or opens the same email twice in a sitting,
# has visited once. A visit is credited when that fan has no page view on
# the same smart link within this many minutes.
VISIT_WINDOW_MINUTES = 30


def fan_token(secret, fan_id):
    """The ?f= value for one fan."""
    return URLSafeSerializer(secret, salt=_FAN_LINK_SALT).dumps(str(fan_id))


def read_fan_token(secret, token):
    """The fan id a ?f= value names, or None when it is missing, tampered
    with or signed by another key."""
    if not token:
        return None
    try:
        value = URLSafeSerializer(secret, salt=_FAN_LINK_SALT).loads(token)
    except (BadSignature, ValueError, TypeError):
        return None
    return value if isinstance(value, str) and value else None


# --- The way out ------------------------------------------------------------
#
# Every marketing email the app sends a fan for an artist - the release-day
# note and the Fan Club drop notice - carries an unsubscribe link that
# works with no login: a signed token naming the artist's account and ONE
# ROW, the fan's CRM record (FAN_REF) or their Fan Club membership
# (MEMBER_REF). The server looks the address up when the link is used.
# Until 2026-09-23 the token carried the address itself: signed is not
# encrypted, so anyone who saw the link, in a List-Unsubscribe header, a
# request log or an error report, could read the fan's email address out
# of it. It never expires, because an unsubscribe link that stops working
# is not one.
#
# ONE LIST. A fan who unsubscribes, or whom the artist marks do not
# contact from the Fan CRM, is ml_fans.suppressed with the reason below;
# every send list goes through fan_segments.contactable() or
# suppressed_emails() before a message goes, the same door the CSV export
# and the Audience counts already use.
#
# WHO MAY UNDO WHAT. A fan's own unsubscribe is theirs: only they can
# reverse it, from the same link. The artist's do-not-contact mark is the
# artist's: only they can lift it, from the CRM. Neither can lift the
# other's.
#
# In the mail client: each message also carries List-Unsubscribe and
# List-Unsubscribe-Post (RFC 8058), so Gmail and Apple Mail offer their own
# unsubscribe button, which POSTs to the same address in one click. The
# link in the body opens a page with one button: a GET never unsubscribes,
# because mail scanners follow links in messages and would unsubscribe
# fans who never asked.

_UNSUB_SALT = "fan-unsubscribe"

UNSUBSCRIBED = "unsubscribed"       # the fan's own, from the link
DO_NOT_CONTACT = "do not contact"   # the artist's mark, from the CRM


FAN_REF = "f"       # an ml_fans row: the release-day email
MEMBER_REF = "m"    # a club_members row: the Fan Club drop notice


def unsubscribe_token(secret, owner_id, kind, ref_id):
    """The signed reference in one unsubscribe link: the artist's account,
    and the fan record or membership the email went to. Never the
    address."""
    if kind not in (FAN_REF, MEMBER_REF):
        raise ValueError("unsubscribe_token: kind must be FAN_REF or MEMBER_REF")
    return URLSafeSerializer(secret, salt=_UNSUB_SALT).dumps(
        [str(owner_id), kind, str(ref_id)])


def read_unsubscribe_token(secret, token):
    """(owner_id, kind, ref_id) the token names, or None."""
    if not token:
        return None
    try:
        value = URLSafeSerializer(secret, salt=_UNSUB_SALT).loads(token)
    except (BadSignature, ValueError, TypeError):
        return None
    if (not isinstance(value, list) or len(value) != 3
            or not all(isinstance(v, str) and v for v in value)
            or value[1] not in (FAN_REF, MEMBER_REF)):
        return None
    return value[0], value[1], value[2]


def unsubscribe_headers(url):
    """RFC 8058 one-click unsubscribe, for the mail client's own button."""
    return {"List-Unsubscribe": "<%s>" % url,
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


def suppressed_emails(fans):
    """The addresses on this list that must not be written to."""
    return {(f.get("email") or "").strip().lower() for f in fans or ()
            if (f.get("suppressed") or "").strip()}


def footer_html(why, unsubscribe_url):
    """The foot of every fan email: why they are getting it, and the way
    out. `why` is plain text and is escaped here."""
    import html as _html
    return ('<p style="color:#91836A;font-size:12px;margin:24px 0 0;">%s '
            '<a href="%s" style="color:#91836A;text-decoration:underline;">Unsubscribe</a></p>'
            % (_html.escape(why), _html.escape(unsubscribe_url, quote=True)))

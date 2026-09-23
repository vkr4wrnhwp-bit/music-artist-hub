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

"""Social publishing provider registry for Rollout Engine.

Manual posting is the only route that works: copy the caption, download
the asset, post it yourself, paste the published URL back, mark it
posted. Attribution still runs, because it hangs off each post's own
tracked link rather than off the platform.

NOTHING HERE PUBLISHES. There is no upload code in this module or behind
it, for any platform. That is worth stating plainly, because the status
this used to report did not: a platform whose environment variables
happened to be present was labelled "configured", which reads as working
and is not. Credentials sitting in the environment are not a connection -
every one of these platforms needs an OAuth grant the account holder has
to approve, and an upload path that has not been written.

When one is genuinely built, `publishes` on its row becomes True and the
page will say so on that platform's evidence, not on the presence of a
variable.
"""

import os

# (key, display name, env vars auto-posting would need, publishes today)
PROVIDERS = [
    ("manual", "Manual posting", (), True),
    ("meta", "Instagram / Facebook (Meta API)",
     ("META_APP_ID", "META_APP_SECRET"), False),
    ("tiktok", "TikTok Content Posting API",
     ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"), False),
    # The YouTube key already on this deployment reads public data. Uploading
    # to a channel is a different grant entirely - OAuth against the channel
    # owner, on a scope Google treats as sensitive and reviews before anyone
    # outside the developer's own account may use it.
    ("youtube", "YouTube Data API",
     ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"), False),
    ("x", "X / Twitter API", ("X_API_KEY", "X_API_SECRET"), False),
    ("threads", "Threads API", ("THREADS_APP_ID",), False),
    ("linkedin", "LinkedIn API", ("LINKEDIN_CLIENT_ID",), False),
    ("snapchat", "Snapchat", ("SNAP_CLIENT_ID",), False),
]

# What each status means, in one place, so the page cannot invent a third
# reading of the same word.
READY = "ready"                 # posts can go out through this route today
CREDENTIALS_ONLY = "not connected"   # variables exist; nothing can publish
MISSING = "needs credentials"


def provider_status():
    """[(key, name, status)] — the state of each publishing route.

    A platform only reads "ready" when something here can actually put a
    post out. Manual is the only one, and it is ready because a person
    does the posting.
    """
    out = []
    for key, name, env_vars, publishes in PROVIDERS:
        if publishes:
            status = READY
        elif env_vars and all(os.environ.get(v) for v in env_vars):
            # Deliberately NOT "configured". The variables are there and
            # the platform still cannot be posted to.
            status = CREDENTIALS_ONLY
        else:
            status = MISSING
        out.append((key, name, status))
    return out


def can_publish(key):
    """Is there code behind this key that puts a post out? Today: manual only."""
    for pkey, _name, _env, publishes in PROVIDERS:
        if pkey == key:
            return bool(publishes)
    return False


def any_automatic_publishing():
    """True when some platform other than manual can actually publish.

    The page asks this before it offers anything that implies automation,
    so a half-built adapter cannot quietly turn the copy optimistic.
    """
    return any(publishes for key, _n, _e, publishes in PROVIDERS
               if key != "manual")

"""What this deployment can actually do, on one page.

Street Banker reads 73 environment variables. Until now the only way to
learn which were set was to open six unrelated diagnostics and infer the
rest, so "is it live?" was answered from memory - and the 2026-09-10
audit could not answer it at all, marking 28 features "needs a
credential" when what it meant was "this checkout has no keys".

Two rules keep this page honest.

A KEY IS NOT A CAPABILITY. Every row says which of the two it reports.
`configured()` across the provider modules is a presence check: it proves
somebody typed a value, not that the vendor accepts it, that the account
has quota, or that the sending domain is verified. Where something stronger exists the row links it and says exactly
what that endpoint does, because they differ sharply: /storage/diag
genuinely writes an object, signs a URL, reads it back and deletes it,
while /presave/diag only reports which variables the process can see.
Calling both of those "proof" would reintroduce the confusion this page
exists to remove. A rotated Stripe
webhook secret reads "configured" forever, which is the exact shape of
the billing overclaim the audit found.

NO VALUES, EVER. Rows carry variable NAMES so the owner knows what to
set. Printing a key on a page - even to the owner, even masked - puts it
in a screenshot, a support thread and a browser cache.
"""

import os

import audio_policy


def _try(fn, default=False):
    """A provider that raises must not take the readiness page down.

    This page is most useful exactly when something is misconfigured, so
    a module throwing on a missing table is a thing to report rather than
    a reason to 500.
    """
    try:
        return bool(fn())
    except Exception:
        return default


def _call(fn, default):
    """_try answers a yes/no. This one hands back whatever the callable
    returned, for the providers that report a dict."""
    try:
        return fn()
    except Exception:
        return default


def _present(*names):
    return all((os.environ.get(n) or "").strip() for n in names)


def _signal_rows():
    """Every Signal provider, from the registry rather than from memory.

    Two things were wrong when these rows were written by hand. The
    Soundcharts row named SOUNDCHARTS_ID and SOUNDCHARTS_TOKEN, neither
    of which the app reads - the real pair is SOUNDCHARTS_APP_ID and
    SOUNDCHARTS_API_KEY, or SOUNDCHARTS_CLIENT_ID and
    SOUNDCHARTS_CLIENT_SECRET for OAuth. And every adapter needs its own
    *_ENABLED flag as well as a key, which the hand-written rows ignored
    entirely, so a provider with a key and no flag read as "Configured"
    while Signal was not calling it.

    The registry cannot drift from the adapters, so it is asked instead.
    """
    import signal_providers as sp

    rows = []
    for provider in sp.registry().all_providers():
        keys = list(getattr(provider, "env_keys", ()) or ())
        oauth = list(getattr(provider, "oauth_keys", ()) or ())
        flag = getattr(provider, "env_flag", "")
        if not (keys or oauth or flag):
            continue          # the demo universe and other no-credential ones
        health = _call(provider.health_check, {}) or {}
        rows.append({
            "name": provider.label,
            "on": bool(health.get("configured")),
            "env": ([flag] if flag else []) + keys + oauth,
            "unlocks": health.get("detail") or "",
            "signal": True,
        })
    return sorted(rows, key=lambda r: (not r["on"], r["name"]))


# Flags the app reads that do not live in audio_policy.FLAGS, so the
# audio section never showed them. LYRIC_SHEET_ENABLED in particular was
# set on this deployment and absent from the page, which is the exact
# failure this page exists to prevent.
OTHER_FLAGS = [
    ("LYRIC_SHEET_ENABLED", "Pulling the words up off a master in Audio Studio."),
    ("LIVE_LAB_ENABLED", "Live Lab: the set list, the stems and the stage view."),
    ("STUDIO_V1_ENABLED", "The Studio session surface."),
]


def _flags():
    """The audio lanes, each its own switch. Unset means off on purpose:
    a deployment gains a surface deliberately, not by upgrading."""
    return [{
        "name": f.replace("_ENABLED", "").replace("_", " ").capitalize(),
        "on": audio_policy.flag(f), "env": [f], "flag": True, "unlocks": "",
    } for f in audio_policy.FLAGS]


def _groups():
    # Each group is a question an owner actually has - "can my artists be
    # emailed?", "do uploads survive a deploy?" - and rows are ordered by
    # how much stops working when they are missing.
    import acr_provider
    import backup_store
    import bandsintown_provider
    import blob_store
    import email_provider
    import eventbrite_provider
    import spotify_provider
    import stripe_provider

    return [
        ("Email", "Nothing reaches anybody without this.", [
            dict(name="Sending (Resend)",
                 on=_try(email_provider.configured),
                 env=["RESEND_API_KEY", "EMAIL_FROM"],
                 unlocks="Password resets, team invites, co-writer signature "
                         "requests, fan-club blasts and press sends. Every one "
                         "refuses honestly while this is off.",
                 probe="/mail/diag?domains=1", roundtrip=True,
                 proof="asks Resend which of your domains are verified and "
                       "names the DNS records still missing. It does not send"),
            dict(name="Inbound replies",
                 on=_present("RESEND_INBOUND_DOMAIN"),
                 env=["RESEND_INBOUND_DOMAIN", "RESEND_WEBHOOK_SECRET"],
                 unlocks="A reply to a press pitch landing back on the desk "
                         "instead of in a mailbox nobody reads."),
        ]),
        ("Files", "Where uploads live.", [
            dict(name="Object storage (R2)",
                 on=_try(blob_store.configured),
                 env=["R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID",
                      "R2_SECRET_ACCESS_KEY", "R2_PUBLIC_BASE_URL"],
                 unlocks="Masters, artwork, EPK kits, stems and delivery zips "
                         "surviving a deploy. Without it they go to the "
                         "instance disk, which is replaced on every release.",
                 probe="/storage/diag", roundtrip=True,
                 proof="writes an object, signs a URL, reads it back and "
                       "deletes it - the check here that actually fails when "
                       "a key is wrong or a bucket name is misspelt"),
            dict(name="Off-box backup",
                 on=_try(backup_store.configured),
                 env=["BACKUP_S3_ENDPOINT", "BACKUP_S3_BUCKET",
                      "BACKUP_S3_KEY", "BACKUP_S3_SECRET", "BACKUP_TOKEN"],
                 unlocks="A scheduled copy of the database somewhere other "
                         "than the machine running it."),
        ]),
        ("Money", "Taking payment.", [
            dict(name="Stripe",
                 on=_try(stripe_provider.configured),
                 env=["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"],
                 unlocks="Paid plans, VIP ticket sales and fan-club "
                         "subscriptions. While this is off, /plan/switch "
                         "hands out any tier for free.",
                 caution="The webhook reading is a presence check on the "
                         "secret. A rotated or revoked secret still reads as "
                         "live - confirm deliveries in the Stripe dashboard."),
        ]),
        ("Signal providers",
         "Read from the registry, which knows the flag AND the key. Every "
         "adapter needs its own *_ENABLED flag set as well as credentials - "
         "a key on its own is not enough, and these rows used to miss that.",
         _signal_rows()),
        ("Pulse and pre-save", "Spotify's own credentials, separate from the "
         "Signal adapter above.", [
            dict(name="Spotify",
                 on=_try(__import__("spotify_provider").configured),
                 env=["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
                      "SPOTIFY_REDIRECT_URI"],
                 unlocks="Follower and popularity readings on Pulse, and the "
                         "real pre-save button on a campaign link. Without it, "
                         "the button labelled Pre-Save is an email box.",
                 probe="/presave/diag",
                 proof="reports which Spotify variables this process can "
                       "see. It does not attempt an OAuth exchange"),
        ]),
        ("Rights",
         "Registration and fingerprinting in the catalog and the fingerprints "
         "desk. These are the keys those surfaces read directly - Signal's own "
         "use of the same vendors is the section above, and needs its flags.", [
            dict(name="The MLC", on=_present("MLC_USERNAME", "MLC_PASSWORD"),
                 env=["MLC_USERNAME", "MLC_PASSWORD"],
                 unlocks="Matching a work, filling ISWC and publisher from a "
                         "real registration, and a Clean Release score that "
                         "can actually reach 100."),
            dict(name="ACRCloud", on=_try(acr_provider.configured),
                 env=["ACRCLOUD_HOST", "ACRCLOUD_ACCESS_KEY",
                      "ACRCLOUD_ACCESS_SECRET", "ACRCLOUD_CONSOLE_TOKEN"],
                 unlocks="Registering a master for fingerprinting, and "
                         "scanning audio against it."),
            dict(name="Discogs", on=_present("DISCOGS_TOKEN"),
                 env=["DISCOGS_TOKEN"],
                 unlocks="Finding a pressing and filling its metadata."),
        ]),
        ("Audio", "The key, the splitter, and one flag per lane.", [
            dict(name="ElevenLabs key", on=_present("ELEVENLABS_API_KEY"),
                 env=["ELEVENLABS_API_KEY"],
                 unlocks="Every lane below. Without it they return offline "
                         "placeholders rather than real audio.",
                 probe="/admin/audio",
                 proof="shows the flags, the key presence and the real job "
                       "and webhook history - a lane that has actually run "
                       "is the honest evidence here"),
            dict(name="Stem splitting", on=_present("STEMSPLIT_API_KEY"),
                 env=["STEMSPLIT_API_KEY"], unlocks="Studio Split.",
                 probe="/rack/studio-split/diag",
                 proof="reports the key length and whether it carries stray "
                       "quotes or whitespace - the three things that "
                       "silently break a pasted secret"),
        ] + _flags() + [
            dict(name=label.replace("_ENABLED", "").replace("_", " ").capitalize(),
                 on=audio_policy.flag(label), env=[label], flag=True,
                 unlocks=why)
            for label, why in OTHER_FLAGS
        ]),
        ("Live and tour", "Ticket counts, venues and maps.", [
            dict(name="Eventbrite", on=_try(eventbrite_provider.configured),
                 env=["EVENTBRITE_TOKEN"],
                 unlocks="Measured ticket counts rather than typed ones."),
            dict(name="Ticketmaster", on=_present("TICKETMASTER_API_KEY"),
                 env=["TICKETMASTER_API_KEY"],
                 unlocks="The same, for its own events."),
            dict(name="Bandsintown", on=_try(bandsintown_provider.configured),
                 env=["BANDSINTOWN_APP_ID"],
                 unlocks="Dates on an artist's Signal page."),
            dict(name="Google Maps", on=_present("GOOGLE_MAPS_API_KEY"),
                 env=["GOOGLE_MAPS_API_KEY"],
                 unlocks="Venue photos and coordinates on a show."),
        ]),
        ("Deployment", "The ones that are wrong quietly.", [
            dict(name="Public address", on=_present("PUBLIC_BASE_URL"),
                 env=["PUBLIC_BASE_URL"],
                 unlocks="Every link the app SENDS - password resets, rider "
                         "links, share links, QR codes - naming your own "
                         "domain rather than the hosting one."),
            dict(name="Session secret", on=_present("SECRET_KEY"),
                 env=["SECRET_KEY"],
                 unlocks="Sessions surviving a restart.",
                 caution="Unset, it falls back to a built-in value and "
                         "everybody is signed out on every deploy - which "
                         "never looks like a misconfiguration."),
            dict(name="Owner accounts", on=_present("OWNER_EMAILS"),
                 env=["OWNER_EMAILS", "OWNER_EMAIL"],
                 unlocks="Who reaches the Operator Desk, Signal, Artist "
                         "accounts and the database export.",
                 caution="Hashed addresses in the source count too, so this "
                         "reading off is not proof you are locked out."),
        ]),
    ]


def report():
    """Every group, with a count of what is live in each."""
    out = []
    for title, blurb, rows in _groups():
        rows = [dict(r, on=bool(r.get("on"))) for r in rows]
        out.append({"title": title, "blurb": blurb, "rows": rows,
                    "live": sum(1 for r in rows if r["on"]),
                    "total": len(rows)})
    return out


def init(app, is_owner_email, current_user, login_redirect, context):
    """Owner only, and a 404 for anybody else: the row labels alone tell
    a stranger which integrations are worth probing."""
    from flask import abort, render_template

    @app.route("/admin/readiness")
    def admin_readiness():
        user = current_user()
        if user is None:
            return login_redirect()
        if not is_owner_email(user.get("email")):
            abort(404)
        groups = report()
        # Named ready_* because build_dashboard_context() already carries
        # a `total`, and the collision is a TypeError at render time.
        return render_template(
            "admin_readiness.html", active_page="readiness", groups=groups,
            ready_live=sum(g["live"] for g in groups),
            ready_total=sum(g["total"] for g in groups), **context())

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


def _present(*names):
    return all((os.environ.get(n) or "").strip() for n in names)


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
        ("Music data", "Where the numbers on Pulse and Signal come from.", [
            dict(name="Spotify",
                 on=_try(spotify_provider.configured),
                 env=["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
                      "SPOTIFY_REDIRECT_URI"],
                 unlocks="Follower and popularity readings on Pulse, and the "
                         "real pre-save button on a campaign link. Without it, "
                         "the button labelled Pre-Save is an email box.",
                 probe="/presave/diag",
                 proof="reports which Spotify variables this process can "
                       "see. It does not attempt an OAuth exchange"),
            dict(name="Songstats", on=_present("SONGSTATS_API_KEY"),
                 env=["SONGSTATS_API_KEY"],
                 unlocks="Streaming and playlist history in Signal."),
            dict(name="Soundcharts",
                 on=_present("SOUNDCHARTS_ID", "SOUNDCHARTS_TOKEN"),
                 env=["SOUNDCHARTS_ID", "SOUNDCHARTS_TOKEN"],
                 unlocks="The same capabilities as Songstats. One provider "
                         "serves each capability, chosen by preference order.",
                 probe="/signal/admin/data-sources", roundtrip=True,
                 proof="names which adapter serves each capability, and its "
                       "Test connection button calls the vendor for real"),
            dict(name="YouTube", on=_present("YOUTUBE_API_KEY"),
                 env=["YOUTUBE_API_KEY"],
                 unlocks="Video counts on Pulse and in Signal."),
            dict(name="Chartmetric", on=_present("CHARTMETRIC_TOKEN"),
                 env=["CHARTMETRIC_TOKEN"],
                 unlocks="Audience and playlist data in Signal."),
        ]),
        ("Rights", "Registration and fingerprinting.", [
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
        ] + _flags()),
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

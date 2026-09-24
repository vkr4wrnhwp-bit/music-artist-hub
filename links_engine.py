"""Street Banker Links campaign engine.

Pure logic for the smart-link platform: the destination service catalog,
campaign types, the Street Banker release-readiness score, fan intent
scoring, and campaign status derivation (including the pre-save ->
released auto-conversion, which is derived from the release date so one
campaign URL stays alive before and after release day).
"""

from datetime import datetime, timedelta, timezone

# Destination services: (key, display name, logo key for the shared macro).
# Manual URLs now; provider integrations hang off the same keys later.
SERVICES = [
    ("spotify", "Spotify", "spotify"),
    ("apple_music", "Apple Music", "apple"),
    ("youtube", "YouTube", "youtube"),
    ("youtube_music", "YouTube Music", "youtube"),
    ("amazon_music", "Amazon Music", "other"),
    ("soundcloud", "SoundCloud", "other"),
    ("audiomack", "Audiomack", "other"),
    ("deezer", "Deezer", "other"),
    ("tidal", "TIDAL", "other"),
    ("pandora", "Pandora", "other"),
    ("itunes", "iTunes", "apple"),
    ("bandcamp", "Bandcamp", "other"),
    ("tiktok", "TikTok Sound", "tiktok"),
    ("custom", "Custom Link", "other"),
]
SERVICE_NAMES = dict((k, n) for k, n, _ in SERVICES)

# Odesli platform keys -> our destination service keys, for the builder's
# auto-scan (paste one track URL, fill every service).
ODESLI_TO_SERVICE = {
    "spotify": "spotify",
    "appleMusic": "apple_music",
    "itunes": "itunes",
    "youtube": "youtube",
    "youtubeMusic": "youtube_music",
    "amazonMusic": "amazon_music",
    "soundcloud": "soundcloud",
    "audiomack": "audiomack",
    "deezer": "deezer",
    "tidal": "tidal",
    "pandora": "pandora",
}


# Campaign types: MVP types are buildable now; the rest are registered in
# the architecture and appear as "coming soon" until their engines land.
# (key, the name on the chooser, buildable now, THE SHORT NAME)
# The short name is what the page calls itself once this type is picked -
# "New Release", "New Pre-Save" - so the builder never has to fall back
# on a word of its own (owner, 2026-09-22).
CAMPAIGN_TYPES = [
    ("release", "Released Music Smart Link", True, "Release"),
    ("presave", "Pre-Save Campaign", True, "Pre-Save"),
    ("bio", "Artist Bio / Fan Hub", True, "Fan Hub"),
    ("download_gate", "Download Gate", False, "Download Gate"),
    ("reward", "Reward Link", False, "Reward Link"),
    ("tour", "Tour / Ticket Page", False, "Tour Page"),
    ("merch", "Merch Drop", False, "Merch Drop"),
    ("contest", "Contest / Giveaway", False, "Contest"),
    ("epk", "EPK / Press Link", False, "EPK"),
    ("label_roster", "Label Roster Link", False, "Roster Link"),
]
CAMPAIGN_TYPE_NAMES = dict((k, n) for k, n, _a, _s in CAMPAIGN_TYPES)
CAMPAIGN_TYPE_SHORT = dict((k, s) for k, _n, _a, s in CAMPAIGN_TYPES)


def short_name(key):
    """What the builder calls itself for this type. Release when the key
    is unknown, because release is the chooser's default."""
    return CAMPAIGN_TYPE_SHORT.get(key or "", "Release")


def opening_type(value):
    """The type a door asked the builder to open on (?type=). Only a key
    that is BUILDABLE today is honoured - a door must not open the page
    on something whose engine has not landed - and anything else falls
    back to release, the chooser's own default."""
    key = (value or "").strip()
    for k, _name, available, _short in CAMPAIGN_TYPES:
        if k == key and available:
            return k
    return "release"

RELEASE_TYPES = ["Single", "EP", "Album", "Playlist", "Video", "Podcast", "Other"]

# Core DSPs the readiness score expects on every music campaign.
_CORE_SERVICES = ("spotify", "apple_music", "youtube")


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def effective_status(campaign):
    """Live campaigns auto-convert: future release date = pre-save,
    past = released. Same URL, no manual flip needed."""
    if campaign.get("archived_at"):
        return "Archived"
    if campaign["status"] != "live":
        return "Draft"
    date = campaign.get("release_date") or ""
    if date and date > _today():
        return "Pre-save live"
    if date:
        return "Released"
    return "Live"


def is_prerelease(campaign):
    date = campaign.get("release_date") or ""
    return bool(date and date > _today())


# How late the release-day email may still go: a week after release. Later
# than that it is not a reminder, it is news that is not news. Both senders
# obey it, the first page view after release and the daily run
# (/reminders/run), because the window is checked where the email is sent
# (app._send_release_emails), not by one of its callers.
RELEASE_EMAIL_DAYS = 7


def release_email_window_open(campaign, today=None):
    """Whether this campaign's release-day email may go today: it has a
    release date, that date has come, and it is no more than
    RELEASE_EMAIL_DAYS ago. A campaign with no release date never sends
    one: there is no release day to remind anybody of."""
    date = (campaign.get("release_date") or "")[:10]
    if not date:
        return False
    today = today or _today()
    since = (datetime.strptime(today, "%Y-%m-%d").date()
             - timedelta(days=RELEASE_EMAIL_DAYS)).isoformat()
    return since <= date <= today


# The email box on a pre-release page stores an address for the
# release-day email; it saves nothing to any library. Until 2026-09-23 its
# button defaulted to "Pre-Save", so on a deployment without Spotify keys
# the only thing on the page called Pre-Save was an email box (audit
# overclaim 17). An artist's own button text is kept unless it claims a
# save.
_SAVE_WORDS = ("save", "pre-add", "library")


def notify_button_text(settings, reminders_on):
    """What the pre-release email button says. "Remind me" only where the
    release-day email can go (emailer.configured()); otherwise the box is
    a sign-up and says so."""
    cta = ((settings or {}).get("cta_text") or "").strip()
    if cta and not any(w in cta.lower() for w in _SAVE_WORDS):
        return cta
    return "Remind me" if reminders_on else "Join the list"


def notify_done_text(reminders_on):
    """The line a pre-release sign-up gets back. It promises the reminder
    only where the release-day email can go."""
    return ("You're on the list. We'll email you on release day." if reminders_on
            else "You're on the list.")


STATUS_TONES = {
    "Draft": "gray", "Pre-save live": "gold", "Released": "green",
    "Live": "green", "Archived": "dim",
}


def calculate_street_banker_score(campaign, destinations):
    """0-100 release-readiness score with actionable warnings."""
    settings = campaign.get("settings") or {}
    active_keys = {d["service_key"] for d in destinations if d.get("is_active", 1)}
    score, warnings = 0, []

    # Destination completeness: 30
    for key in _CORE_SERVICES:
        if key in active_keys:
            score += 8
        else:
            warnings.append("%s destination missing." % SERVICE_NAMES[key])
    extra = len(active_keys - set(_CORE_SERVICES))
    score += min(extra * 2, 6)

    # Cover art: 12
    if campaign.get("cover_url"):
        score += 12
    else:
        warnings.append("No cover art set — links get skipped without artwork.")

    # Release date + countdown/pre-save readiness: 12
    if campaign.get("release_date"):
        score += 12
    elif campaign.get("campaign_type") == "presave":
        warnings.append("No release date set — pre-save countdown cannot run.")
    else:
        warnings.append("No release date set.")

    # Fan capture: 16
    if settings.get("email_capture"):
        score += 16
    else:
        warnings.append("No email capture enabled — you are renting fans, not owning them.")

    # Compliance/consent copy: 10
    if settings.get("consent_text"):
        score += 10
    else:
        warnings.append("Privacy/consent copy is missing.")

    # Story: description/announcement: 8
    if campaign.get("description"):
        score += 8
    else:
        warnings.append("No announcement text set.")

    # Published with active destinations: 12
    if campaign["status"] == "live" and active_keys:
        score += 12
    elif campaign["status"] == "live":
        warnings.append("Campaign is published but has no active destinations.")
    else:
        warnings.append("Campaign is not published yet.")

    return {"total": min(score, 100), "warnings": warnings}


# Fan intent: weighted from tracked behavior. Captures and pre-saves are
# worth far more than anonymous traffic — intent is what the artist owns.
def calculate_fan_intent(fan):
    score = 0
    score += min(fan.get("total_visits", 0) * 2, 10)
    score += min(fan.get("total_clicks", 0) * 5, 20)
    score += min(fan.get("total_captures", 0) * 25, 35)
    score += min(fan.get("total_presaves", 0) * 30, 35)
    score = min(score, 100)
    if score >= 70:
        level = "Superfan"
    elif score >= 45:
        level = "Hot"
    elif score >= 20:
        level = "Warm"
    else:
        level = "Cold"
    return score, level


INTENT_TONES = {"Cold": "gray", "Warm": "gold", "Hot": "amber", "Superfan": "green"}

"""Release-Ready: get a mix checked, hear two free previews, buy the master.

A Creative Studio page at /creative-studio/release-ready (owner's brief,
2026-09-19). The artist uploads a finished mix, or a vocal and a beat.
RoEx (roex_client.py, the only module that talks to RoEx) writes a mix
report, makes free 30-second previews, and, once the artist has paid
through a one-time Stripe Checkout, the full master. The master is stored
with us and attached to the song's Track Passport.

THE RULES THIS FILE KEEPS
-------------------------
  Nothing leaves without consent. Every upload needs two ticked boxes: the
  artist owns the audio or holds every licence it needs, and grants Street
  Banker a licence to process it, including through RoEx. Each file's
  consent is recorded (who, the person who ticked, when, the file's
  sha256, the wording's version and a hash of the exact words).

  Money is only spent on purpose. The mix report (10 RoEx credits) runs
  automatically under the owner's monthly credit budget and a per-artist
  cap (release_ready_settings). A paid final (/retrievefinalmaster,
  /retrieverecombine) is only ever requested for a job whose payment was
  claimed, or that the owner released by hand. Webhooks, status polls and
  the queue sweep move jobs along; none of them can start a paid final on
  their own, and /retrievefinalmaster is never asked twice for one job
  without the owner pressing a button. A payment is only claimed for a
  job still waiting to be bought and young enough for RoEx to finish it;
  any other payment is recorded as stale and the owner is told to refund.
  A report RoEx may have charged for (no answer, a 5xx, a failure RoEx
  reported) stays counted against the budget.

  Nothing is claimed that RoEx did not say. The report shows RoEx's
  verdicts and RoEx's figures, labelled as RoEx's, and "Not measured" for
  anything missing, never 0. There is no score: RoEx returns none. A
  master is "stored" only once the file is in our bucket.

  The key stays on the server. ROEX_API_KEY is read in roex_client only;
  no template, JSON body or log line carries it, nor any RoEx task id or
  RoEx link. RoEx fetches our audio from fresh presigned R2 links (never
  blob_store.url_for, which can hand out a permanent public URL).

  Whose data: user_id is always current_user(), the ARTIST's account, so a
  team member inside the account works on the artist's uploads, and a read
  seat is refused every write by app.team_seat_gate. The person who acted
  is recorded beside it (session["user_id"]).

WHAT MOVES A JOB
----------------
advance(job_id) runs one step under a database lease, in a background
thread (_spawn). It is kicked by: the upload or button that created the
job; the artist's page polling the JSON status; RoEx's webhook
(/webhooks/roex/<job>/<token>, unsigned, so it only triggers a fresh read);
the Stripe webhook or success redirect for a paid master; and run_due(),
called from the daily /reminders/run and from the owner's desk.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import tempfile
import threading
import time
import urllib.parse
import uuid
from datetime import timedelta
from decimal import Decimal

from flask import (Blueprint, abort, jsonify, redirect, render_template,
                   request, session)

import audio_probe
import blob_store
import db
import release_ready_settings as rrs
import release_ready_store as store
import roex_client as roex
import stripe_provider

bp = Blueprint("release_ready", __name__)
log = logging.getLogger("release_ready")

PAGE = "/creative-studio/release-ready"
ADMIN = "/admin/release-ready"

SOURCE_URL_TTL_ANALYSIS = 3600                 # the report is synchronous
SOURCE_URL_TTL_TASK = 7 * 24 * 3600            # R2's SigV4 maximum
# RoEx may read the upload again to finish a paid master, through the link
# it was given when the preview was made. A preview can be bought for six
# days, a checkout stays open for at most CHECKOUT_OPEN, and a payment that
# lands later than CLAIM_WITHIN is recorded as stale and never retrieved.
BUY_WITHIN = timedelta(days=6)
CHECKOUT_OPEN = timedelta(hours=2, minutes=30)
CLAIM_WITHIN = timedelta(seconds=SOURCE_URL_TTL_TASK) - timedelta(hours=1)
PREVIEW_DEADLINE = timedelta(minutes=45)
WAIT_FOR_START = timedelta(minutes=3)
BACKOFF = (15, 30, 60, 120)
REPORT_CREDITS = roex.CREDITS["mix_analysis"]

_hooks = {"current_user": None, "notify_owners": None, "is_owner_email": None,
          "public_url": None, "demo_locked": None}


# --- consent ---------------------------------------------------------------------
# The exact words on the upload form. Their hash is stored with every consent
# row, so what was agreed can be shown later word for word. Change a word,
# change the version.

# rr-consent-2 (review, 2026-09-19): version 1 said the licence covered
# "this service only", but RoEx's API Terms (section 5) take a licence for
# RoEx and its service providers to host, share, listen to and modify the
# content and output to provide AND IMPROVE RoEx's services. The artist is
# now told what they actually pass on.
CONSENT_VERSION = "rr-consent-2"
CONSENT_NOTE = ("Your file goes to RoEx, a mastering service we work with, to make the "
                "report, the previews and the master. Nothing is sent until you tick "
                "both boxes.")
CONSENT_RIGHTS = ("I own this audio, or I hold every licence it needs, including for "
                  "any beat or sample in it.")
CONSENT_LICENCE = ("I give Street Banker permission to process this file for "
                   "Release-Ready: a mix report, previews and, if I buy it, a finished "
                   "master, including by sending it to its processing partner, RoEx. "
                   "Under RoEx's own terms, RoEx and its service providers may then host, "
                   "share, listen to and change this file and what is made from it, to "
                   "provide and improve RoEx's service.")

# A team member (or a partner acting as the artist) cannot make the
# artist's own first-person statements: they confirm them on the artist's
# behalf, with their own wording and version (review, 2026-09-19).
CONSENT_VERSION_SEAT = "rr-consent-2-seat"
CONSENT_RIGHTS_SEAT = ("%s owns this audio, or holds every licence it needs, including for "
                       "any beat or sample in it, and I'm authorised to confirm that for them.")
CONSENT_LICENCE_SEAT = ("On behalf of %s, and with their authority, I give Street Banker "
                        "permission to process this file for Release-Ready: a mix report, "
                        "previews and, if they buy it, a finished master, including by "
                        "sending it to its processing partner, RoEx. Under RoEx's own terms, "
                        "RoEx and its service providers may then host, share, listen to and "
                        "change this file and what is made from it, to provide and improve "
                        "RoEx's service.")


def _consent_hash(text):
    return hashlib.sha256("\n".join(
        (text["version"], text["note"], text["rights"], text["licence"])).encode("utf-8")).hexdigest()


def consent_text(artist_name=None):
    """The exact words on the upload form. With artist_name: the words a
    team seat sees, confirming on that artist's behalf."""
    if artist_name is not None:
        name = (artist_name or "").strip()[:80] or "The artist"
        return {"version": CONSENT_VERSION_SEAT, "note": CONSENT_NOTE,
                "rights": CONSENT_RIGHTS_SEAT % name, "licence": CONSENT_LICENCE_SEAT % name}
    return {"version": CONSENT_VERSION, "note": CONSENT_NOTE, "rights": CONSENT_RIGHTS,
            "licence": CONSENT_LICENCE}


CONSENT_SHA256 = _consent_hash(consent_text())


def consent_for_viewer(user):
    """The wording this person sees: their own statement, or a seat's
    statement on the artist's behalf."""
    if _is_seat():
        return consent_text((user or {}).get("name") or (user or {}).get("email") or "")
    return consent_text()


# --- the artist's words ------------------------------------------------------------

COPY = {
    "not_connected": "Release-Ready isn't connected yet. Nothing can be uploaded until it is.",
    "no_storage": "Release-Ready can't store files on this server yet, so uploads are closed.",
    "opens_soon": "Release-Ready opens soon.",
    "owner_only": "Only owner logins can use this until you open it in Settings.",
    "boxes": "Tick both boxes to send this file.",
    "consent_changed": ("The wording above changed while this page was open. Read it again, "
                        "then send the file."),
    "no_file": "Choose a file to send.",
    "unsupported_format": "Release-Ready takes WAV, FLAC or MP3. This file looks like something else.",
    "too_long": "This file is %s long. Release-Ready takes up to 10 minutes per file.",
    "too_short": "This file is shorter than 10 seconds.",
    "sample_rate": "Export at 44.1 kHz or 48 kHz. This file is %s.",
    "unreadable": "We couldn't read how long this file is. Export it as WAV and try again.",
    "too_big": "This file is over 200 MB. Export it at 44.1 kHz or 48 kHz and send that.",
    "style": "Pick the genre closest to this song.",
    "storage_failed": "The file couldn't be saved just now. Nothing was sent. Try again in a minute.",
    "demo": "This is a shared demo account and it is read only.",
    "not_found": "That upload isn't here.",
    "previews_used": "You've used the free previews for this file.",
    "previews_today": "You've made today's free previews. Try again tomorrow.",
    "loudness": "Pick one or two loudness settings.",
    "report_here": "The mix report for this file is already here.",
    "report_not_mix": "Mix reports are for a finished mix.",
    "budget": ("Mix reports are paused for the rest of this month. Your file is saved, and "
               "you can still make free previews and buy a master."),
    "report_runs": ("You've asked for this file's mix report as many times as you can this "
                    "month. Your file is saved, and you can still make free previews and buy "
                    "a master."),
    "seat_buy": "Only the account holder can buy a master.",
    "seat_delete": "Only the account holder can delete a master they bought.",
    "fresh_preview": "Make a fresh preview first, it's free.",
    "no_payments": "Payments aren't switched on yet.",
    "not_buyable": "This preview can't be bought.",
    "checkout_failed": "Stripe couldn't be reached just now. Nothing was charged. Try again in a minute.",
    "checkout_open": ("A checkout for this upload is still open and couldn't be closed just now. "
                      "Try again in a minute."),
    "our_side": ("This couldn't run right now because of a problem on our side. We've told "
                 "the team. Try again later."),
    "paid_waiting": ("Your payment went through. Your master is waiting on our side and "
                     "we've told the team. You won't be charged again. It shows here, and "
                     "in your notifications, once it's stored."),
    "paid_working": "Payment received. We're getting your full master from RoEx.",
    "release_working": "We're getting your full master from RoEx.",
    "stale_payment": ("Your payment came in after this preview could no longer be used, so no "
                      "master was made from it and nothing more will be charged. We've told "
                      "the team about your payment."),
    "stored": "Your master is stored.",
    "roex_failed": ("RoEx couldn't process this file. RoEx said: \"%s\". Try again, or upload "
                    "a different export."),
    "roex_failed_plain": "RoEx couldn't process this file. Try again, or upload a different export.",
    "bad_answer": ("RoEx's answer didn't have what we needed, so there's nothing to show yet. "
                   "We've kept the details for the team. Try again later."),
    "roex_error": "RoEx had a problem on its side and nothing came back. Try again later.",
    "no_answer": "The report didn't come back. Try again.",
    "unreachable": "RoEx couldn't be reached. Try again later.",
    "preview_timeout": "RoEx didn't finish this preview within 45 minutes. Try again, it's free.",
    "preview_gone": "RoEx no longer has this preview. Make a new one, it's free.",
    "handoff": "We couldn't hand the file to RoEx. Try again.",
    # The other direction: RoEx finished and we could not keep what came
    # back. Our problem, not theirs, and not a timeout - so it does not
    # borrow the handoff sentence or the timeout one.
    "not_kept": ("RoEx finished this preview but we couldn't store it. Try again, "
                 "it's free - and it's been reported to us."),
    "checking": "RoEx is checking your mix. This can take a few minutes.",
    "making": "RoEx is making this preview. It usually takes a few minutes.",
    "artist_cap": ("You've used this month's automatic mix reports. Press Get the mix report "
                   "to run this one."),
    "on_request": "The mix report runs when you ask for it.",
    "cancelled": "This was cancelled.",
    "master_deleted": "You deleted this master.",
    "master_gone": "Master deleted.",
    "delete_wait": "Your master is still being fetched. Delete this upload once it's stored.",
    "deleted": ("Upload deleted. A master you bought stays on the song's Track Passport "
                "until you delete it there."),
}

# The owner's desk's own sentences. Like COPY, they travel in a redirect as
# a code (?msg=<key>), never as free text, so a crafted link cannot put its
# own words in the alert band.
DESK_COPY = {
    "report_not_waiting": "That report isn't waiting on you.",
    "budget_used": "The monthly credit budget is used up.",
    "report_queued": "Report queued again.",
    "never_started": "RoEx never started this one, so there is nothing to retrieve.",
    "job_not_waiting": "That job isn't waiting on you.",
    "job_busy": "That job is being worked on right now.",
    "job_paid": "This one is paid for. Use Try the retrieval again.",
    "tick_unpaid": "This master isn't paid for. Tick the box to release it without payment.",
    "retrieval_started": "Retrieval started.",
    "refetch_started": ("Fetching the master again from the link RoEx already gave. RoEx "
                        "isn't asked again."),
    "preview_again": "The free preview is being made again.",
    "preview_polled": "RoEx is being asked for the free preview again.",
    "resumed": "%d paused report(s) resumed.",
    "queue_ran": "The queue ran: %d step(s) started.",
    "bucket_ok": "The bucket answered. The result is below, beside the badge.",
    "bucket_bad": "The bucket test failed. What it found is below, beside the badge.",
    "health_ok": "RoEx answered and accepted the key.",
    "health_not_configured": "No RoEx key is set on this server.",
    "health_auth": "RoEx refused the key.",
    "health_busy": "Our side is at the rate limit. Try again in a minute.",
    "health_unavailable": "RoEx couldn't be reached.",
    "health_unknown": "RoEx didn't answer in time.",
    "health_status": "RoEx answered %d.",
}
_MESSAGES = dict(COPY, **DESK_COPY)
_CODE_FOR = {text: code for code, text in _MESSAGES.items() if "%" not in text}


def message_from_query(args):
    """The alert band's words for ?msg=<code>: only our own sentences, by
    code. Unknown codes, and free text, show nothing."""
    code = (args.get("msg") or "").strip()
    text = _MESSAGES.get(code) if code in _MESSAGES else None
    if not text:
        return ""
    if "%d" in text:
        try:
            return text % max(0, int(args.get("n") or 0))
        except (TypeError, ValueError):
            return text % 0
    if "%" in text:
        return ""                     # needs words we would have to take from the link
    return text

CHIPS = {
    ("mix_analysis", "queued"): "Checking your mix",
    ("mix_analysis", "analysing"): "Checking your mix",
    ("mix_analysis", "reported"): "Mix report ready",
    ("mix_analysis", "paused_budget"): "Report paused this month",
    ("mix_analysis", "on_request"): "Report not run yet",
    ("preview", "queued"): "Making previews",
    ("preview", "processing"): "Making previews",
    ("preview", "preview_ready"): "Preview ready",
    ("preview", "paid"): "Payment received, getting your master",
    ("preview", "retrieving"): "Payment received, getting your master",
    ("preview", "stored"): "Master stored",
    ("preview", "master_deleted"): "Master deleted",
}


def chip_for(jtype, status, paid=False):
    key = ("mix_analysis" if jtype == "mix_analysis" else "preview", status)
    if key[0] == "preview" and status in ("paid", "retrieving") and not paid:
        # The owner released it by hand: no payment was received.
        return "Getting your master"
    if key in CHIPS:
        return CHIPS[key]
    if status == "needs_owner" or (status == "credits_short" and paid):
        return "Our side is fixing this"
    if status in ("failed", "credits_short"):
        return "Needs a retry"
    if status == "cancelled":
        return "Cancelled"
    return status.replace("_", " ").capitalize()


_CHIP_TONES = {"stored": "good", "reported": "good", "preview_ready": "good",
               "queued": "info", "analysing": "info", "processing": "info",
               "paid": "info", "retrieving": "info",
               "failed": "warn", "credits_short": "warn", "needs_owner": "warn"}


def chip_tone(status):
    """The badge colour for a status chip; the chip's words carry the meaning."""
    return _CHIP_TONES.get(status, "idle")


def message_for(job):
    st, kind, paid = job["status"], job.get("error_kind") or "", bool(job.get("paid_at"))
    if st in ("paid", "retrieving"):
        return COPY["paid_working"] if paid else COPY["release_working"]
    if st == "stored":
        return COPY["stored"]
    if paid and st in ("credits_short", "needs_owner", "failed"):
        return COPY["paid_waiting"]
    if st in ("credits_short", "needs_owner"):
        return COPY["our_side"]
    if st in ("queued", "analysing") and job["type"] == "mix_analysis":
        return COPY["checking"]
    if st in ("queued", "processing"):
        return COPY["making"]
    if st == "paused_budget":
        return COPY["budget"]
    if st == "on_request":
        return COPY["artist_cap"] if kind == "artist_cap" else COPY["on_request"]
    if st == "cancelled":
        return COPY["cancelled"]
    if st == "master_deleted":
        return COPY["master_deleted"]
    if st == "failed":
        if kind == "roex_failed":
            # error_text holds RoEx's own words only (roex_client keeps our
            # notes apart), so quoting it as RoEx's is true.
            said = (job.get("error_text") or "").strip()
            return COPY["roex_failed"] % said if said else COPY["roex_failed_plain"]
        return COPY.get({"timeout": "preview_timeout", "not_found": "preview_gone",
                         "unreachable": "unreachable", "no_answer": "no_answer",
                         "storage": "handoff", "not_kept": "not_kept",
                         "not_connected": "not_connected",
                         "bad_answer": "bad_answer", "roex_error": "roex_error"}.get(kind, ""),
                        COPY["unreachable"])
    return ""


def _probe_message(res, who=""):
    reason = res.get("reason")
    if reason == "too_long":
        text = COPY["too_long"] % audio_probe.mmss(res.get("duration_s"))
    elif reason == "sample_rate":
        text = COPY["sample_rate"] % _khz(res.get("sample_rate"))
    else:
        text = COPY.get(reason, COPY["unreadable"])
    return ("%s: %s" % (who, text)) if who else text


def _khz(rate):
    if not rate:
        return "an unknown rate"
    k = rate / 1000.0
    return ("%g kHz" % round(k, 2))


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def day(iso):
    """'2026-09-19T10:04:00+00:00' -> '19 Sep 2026'. Blank for nothing."""
    text = (iso or "")[:10]
    try:
        y, m, d = int(text[:4]), int(text[5:7]), int(text[8:10])
        return "%d %s %d" % (d, _MONTHS[m - 1], y)
    except (ValueError, IndexError):
        return text


def day_time(iso):
    """'2026-09-22T05:09:13+00:00' -> '22 Sep 2026, 05:09 UTC'.

    The bucket test can be run twice in a minute while chasing something,
    so unlike day() this keeps the clock. Blank for nothing."""
    text = iso or ""
    stamp = day(text)
    clock = text[11:16]
    if not stamp or len(clock) != 5:
        return stamp
    return "%s, %s UTC" % (stamp, clock)


def size(n):
    """Bytes as the artist reads them: '106.2 MB'. Blank when unknown."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    if n >= 1024 * 1024:
        return "%.1f MB" % (n / 1048576.0)
    return "%d KB" % max(1, round(n / 1024.0))


# --- the mix report, in plain words ---------------------------------------------------
# RoEx's verdicts are easy to read backwards: for if_master_loudness, LESS
# means TOO LOUD and MORE means too quiet (spec, 2026-09-19).

_LOUDNESS_MIX = {"OPTIMAL": "Right level to send for mastering",
                 "LESS": "Too loud to send for mastering",
                 "MORE": "Too quiet for mastering"}
_LOUDNESS_MASTER = {"OPTIMAL": "In range for the major platforms",
                    "LESS": "Too loud for every major platform",
                    "LESS_APPLE": "Fine for Spotify and SoundCloud, too loud for Apple Music",
                    "MORE": "Quiet: platforms will turn it up"}
_DRC = {"OPTIMAL": "Dynamics in a good range", "LESS": "Too much compression",
        "MORE": "Not enough compression"}
_CLIPPING = {"NONE": "No clipping found", "MINOR": "Some minor clipping",
             "MAJOR": "Heavy clipping"}
# The spec: NARROW "stereo image is too narrow", WIDE "stereo image is too
# wide", BALANCED "well-balanced stereo field". Those are RoEx's verdicts.
_STEREO = {"WIDE": "Too wide", "NARROW": "Too narrow", "BALANCED": "Balanced", "MONO": "Mono",
           "STEREO_UPMIX": "Mono spread out to stereo (an upmix)"}
_TONE = {"LOW": "Low for the genre", "MEDIUM": "In line with the genre",
         "HIGH": "High for the genre"}
_NOTES = (("intro", "Overview"), ("mix_loudness", "Mix loudness"),
          ("master_loudness", "Master loudness"), ("mix_drc", "Mix dynamics"),
          ("master_drc", "Master dynamics"), ("clipping", "Clipping"),
          ("stereo_field", "Stereo field"), ("mono_compatibility", "Mono"),
          ("phase_issues", "Phase"), ("tonal_profile", "Tone"),
          ("summary", "Summary"), ("outro", "Closing note"))

NOT_MEASURED = "Not measured"

# The colour of a verdict's dot, read off RoEx's own word for it: OPTIMAL,
# NONE and BALANCED are RoEx saying "fine", LESS / MORE / MINOR and a stereo
# field RoEx calls too wide or too narrow are RoEx flagging something,
# MAJOR clipping is RoEx flagging it hard. Where RoEx only describes (a mono
# file, an upmix), the dot stays neutral. The word always carries the
# meaning; the dot only repeats it.
_TONE_LOUDNESS = {"OPTIMAL": "good", "LESS": "warn", "MORE": "warn", "LESS_APPLE": "warn"}
_TONE_DRC = {"OPTIMAL": "good", "LESS": "warn", "MORE": "warn"}
_TONE_CLIPPING = {"NONE": "good", "MINOR": "warn", "MAJOR": "crit"}
_TONE_STEREO = {"BALANCED": "good", "WIDE": "warn", "NARROW": "warn"}
_TONE_BAND = {"MEDIUM": "good", "LOW": "warn", "HIGH": "warn"}


def _verdict(table, value):
    if value is None or value == "":
        return NOT_MEASURED
    if isinstance(value, str) and value in table:
        return table[value]
    return "RoEx said %s" % value


def _tone(table, value):
    return table.get(value, "idle") if isinstance(value, str) else "idle"


def _flag(value, yes, no):
    if value is True:
        return yes
    if value is False:
        return no
    return NOT_MEASURED


def _flag_tone(value, good_when):
    if value is True or value is False:
        return "good" if value is good_when else "warn"
    return "idle"


def _figure(value, unit, digits=1):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return NOT_MEASURED
    if f != f:
        return NOT_MEASURED
    return ("%." + str(digits) + "f %s") % (f, unit)


def report_view(payload, is_master):
    """RoEx's report as rows of plain words, with RoEx's own figures and
    RoEx's AI-written notes, each labelled as RoEx's. No score."""
    p = payload if isinstance(payload, dict) else {}
    tone = p.get("tonal_profile") if isinstance(p.get("tonal_profile"), dict) else {}
    loud_key, drc_key = (("if_master_loudness", "if_master_drc") if is_master
                         else ("if_mix_loudness", "if_mix_drc"))
    loud = _verdict(_LOUDNESS_MASTER if is_master else _LOUDNESS_MIX, p.get(loud_key))
    drc = _verdict(_DRC, p.get(drc_key))
    rate = p.get("sample_rate")
    try:
        rate_text = _khz(float(rate)) if rate and float(rate) > 0 else NOT_MEASURED
    except (TypeError, ValueError):
        rate_text = NOT_MEASURED
    bits = p.get("bit_depth")
    bits_text = "%d-bit" % bits if isinstance(bits, int) and bits > 0 else NOT_MEASURED
    summary = p.get("summary") if isinstance(p.get("summary"), dict) else {}
    notes = [{"label": label, "text": str(summary[key]).strip()} for key, label in _NOTES
             if isinstance(summary.get(key), str) and summary[key].strip()]
    return {
        "title": "Mix report by RoEx",
        "is_master": bool(is_master),
        "verdicts": [
            {"label": "Loudness", "value": loud, "tone": _tone(_TONE_LOUDNESS, p.get(loud_key))},
            {"label": "Dynamics", "value": drc, "tone": _tone(_TONE_DRC, p.get(drc_key))},
            {"label": "Clipping", "value": _verdict(_CLIPPING, p.get("clipping")),
             "tone": _tone(_TONE_CLIPPING, p.get("clipping"))},
            {"label": "Stereo field", "value": _verdict(_STEREO, p.get("stereo_field")),
             "tone": _tone(_TONE_STEREO, p.get("stereo_field"))},
            {"label": "Mono", "value": _flag(p.get("mono_compatible"),
                                             "Holds up in mono", "Loses something in mono"),
             "tone": _flag_tone(p.get("mono_compatible"), True)},
            {"label": "Phase", "value": _flag(p.get("phase_issues"),
                                              "Phase problems found", "No phase problems found"),
             "tone": _flag_tone(p.get("phase_issues"), False)},
            {"label": "Bass", "value": _verdict(_TONE, tone.get("bass_frequency")),
             "tone": _tone(_TONE_BAND, tone.get("bass_frequency"))},
            {"label": "Low mids", "value": _verdict(_TONE, tone.get("low_mid_frequency")),
             "tone": _tone(_TONE_BAND, tone.get("low_mid_frequency"))},
            {"label": "High mids", "value": _verdict(_TONE, tone.get("high_mid_frequency")),
             "tone": _tone(_TONE_BAND, tone.get("high_mid_frequency"))},
            {"label": "Highs", "value": _verdict(_TONE, tone.get("high_frequency")),
             "tone": _tone(_TONE_BAND, tone.get("high_frequency"))},
        ],
        "figures_label": "Measured by RoEx",
        "figures": [
            {"label": "Integrated loudness", "value": _figure(p.get("integrated_loudness_lufs"), "LUFS")},
            {"label": "True peak", "value": _figure(p.get("peak_loudness_dbfs"), "dBFS")},
            {"label": "Sample rate", "value": rate_text},
            {"label": "Bit depth", "value": bits_text},
        ],
        "notes_label": "Written by RoEx's AI",
        "notes": notes,
    }


# --- plumbing ---------------------------------------------------------------------------

def _user():
    fn = _hooks["current_user"]
    return fn() if fn else None


def _is_owner(user):
    fn = _hooks["is_owner_email"]
    return bool(user and fn and not session.get("team_as") and not session.get("acting_as")
                and fn(user.get("email")))


def _is_seat():
    return bool(session.get("team_as") or session.get("acting_as"))


READ_ONLY = "Your seat on this account is read only, so you can look but not send or change anything."


def _read_only_seat():
    """A team member whose seat is read only: the page shows them the
    artist's work and offers no control that the team gate would refuse."""
    if not session.get("team_as"):
        return False
    from flask import g
    seat = (getattr(g, "_team_seat", None) or (None, None))[1]
    return bool(seat and seat.get("access") != "edit")


def _wants_json():
    accept = (request.headers.get("Accept") or "").strip().lower()
    if accept.startswith("text/html"):
        return False
    if "application/json" in accept or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    mode = (request.headers.get("Sec-Fetch-Mode") or "").lower()
    dest = (request.headers.get("Sec-Fetch-Dest") or "").lower()
    return mode in ("cors", "same-origin", "no-cors") or dest == "empty"


def _answer(ok, message="", status=200, where=None, code=None, n=None, **extra):
    """A script gets JSON; a page form gets sent back to the page. The page
    is told what happened by a message code (?msg=<code>, and ?n= for a
    count), never by the sentence itself: the page maps the code back to
    our own words, so nobody can write a sentence into a link."""
    if _wants_json():
        return jsonify(dict(extra, ok=ok, message=message)), status
    code = code or _CODE_FOR.get(message)
    if where and (not ok or code):
        if not code:
            return redirect(where)
        sep = "&" if "?" in where else "?"
        query = {"msg": code}
        if n is not None:
            query["n"] = str(int(n))
        return redirect(where + sep + urllib.parse.urlencode(query))
    if where:
        return redirect(where)
    return jsonify(dict(extra, ok=ok, message=message)), status


def storage_ready():
    return blob_store.configured()


def connection_state(user):
    owner = _is_owner(user)
    if not roex.configured():
        return {"open": False, "code": "not_connected", "message": COPY["not_connected"], "owner": owner}
    if not storage_ready():
        return {"open": False, "code": "no_storage", "message": COPY["no_storage"], "owner": owner}
    if not rrs.is_open():
        if owner:
            return {"open": True, "code": "owner_only", "message": COPY["owner_only"], "owner": True}
        return {"open": False, "code": "opens_soon", "message": COPY["opens_soon"], "owner": False}
    return {"open": True, "code": "open", "message": "", "owner": owner}


def _alert(kind, title, body, period="hour"):
    send = _hooks["notify_owners"]
    if not send:
        return False
    return rrs.alert_once(kind, lambda: send(title, body, ADMIN), period=period)


_SEM = threading.BoundedSemaphore(4)


def _spawn(fn, *args):
    """Run one background step. At most four at once per process; when
    all four are busy the job simply stays due and the next poll picks
    it up. Tests replace this with an inline call."""
    if not _SEM.acquire(blocking=False):
        return False

    def run():
        try:
            fn(*args)
        except Exception as exc:
            log.warning("release_ready: background step stopped (%s)", type(exc).__name__)
        finally:
            _SEM.release()

    threading.Thread(target=run, name="release-ready", daemon=True).start()
    return True


def _later(seconds):
    return store.iso(store.now() + timedelta(seconds=seconds))


def _backoff(attempts):
    return BACKOFF[min(max(attempts, 0), len(BACKOFF) - 1)]


def _roex_url(source, ttl):
    """A fresh presigned link to our copy of the audio, for RoEx only.
    Minted per call; never stored, never logged, never shown."""
    key = blob_store.key_of(source.get("storage_key") or "")
    if not key:
        return None
    try:
        return blob_store.presigned_get(key, ttl)
    except Exception:
        return None


def _webhook_for(job_id):
    """The per-job webhook address, or None. Only when this deployment has
    its own https address set: without PUBLIC_BASE_URL a staging copy would
    send RoEx's calls to the live site. The token is new for every
    submission and only its hash is kept."""
    base = (os.environ.get("PUBLIC_BASE_URL") or "").strip()
    make = _hooks["public_url"]
    if not base.startswith("https://") or not make:
        store.update_job(job_id, webhook_token_hash=None)
        return None
    token = secrets.token_urlsafe(32)
    store.update_job(job_id, webhook_token_hash=hashlib.sha256(token.encode()).hexdigest())
    return make("/webhooks/roex/%s/%s" % (job_id, token))


def _take_reservation_back(job):
    """Refund a reserved report when RoEx certainly did not charge."""
    held = store.take_reservation(job["id"])
    if held:
        rrs.release_auto(held["user_id"], held["budget_reserved"], held["budget_month"],
                         bool(held["budget_artist"]))


def _reservation_spent(job):
    """RoEx may have charged (no answer came back): the reservation stays
    counted and is written against the job."""
    held = store.take_reservation(job["id"])
    if held:
        store.update_job(job["id"], credits_spent_estimate=(job.get("credits_spent_estimate") or 0)
                         + int(held["budget_reserved"]))


def _store_private(key, data, content_type):
    """Our copy, in the private bucket only. Returns 'r2:<key>' or None.
    Never the disk: the Render disk is 1 GB and shared with the database."""
    if not blob_store.configured():
        return None
    try:
        return blob_store.PREFIX + key if blob_store.put(key, data, content_type) else None
    except Exception as exc:
        log.warning("release_ready: storing %s failed (%s)", key.rsplit("/", 1)[-1],
                    type(exc).__name__)
        return None


# --- the steps ---------------------------------------------------------------------------

def advance(job_id):
    """One step of one job, under a lease. Safe to call from anywhere, any
    number of times: a job nobody can move right now is left alone."""
    job = store.get_job(job_id)
    if job is None or job["status"] not in store.ADVANCEABLE:
        return job
    if job["status"] in ("paid", "retrieving"):
        seconds = 1200      # a 300 s RoEx call, then up to 160 MB down and up
    elif job["type"] == "mix_analysis":
        seconds = 360
    else:
        seconds = 120
    if not store.claim(job_id, seconds):
        return job
    nudged = False
    try:
        job = store.get_job(job_id)
        hooks_before = job.get("webhook_count") or 0
        if job["type"] == "mix_analysis":
            _step_analysis(job)
        elif job["type"] == "master_preview":
            _step_master(job)
        elif job["type"] == "recombine":
            _step_recombine(job)
        # RoEx's webhook came in while this step held the lease, so the
        # webhook could not start a step of its own, and the step just
        # ended may have set the next poll well ahead. Read RoEx again now.
        after = store.get_job(job_id) or {}
        if (after.get("webhook_count") or 0) > hooks_before and \
                after.get("status") in ("queued", "processing"):
            store.update_job(job_id, next_poll_at=store.iso())
            nudged = True
    finally:
        store.release_lease(job_id)
    if nudged:
        _spawn(advance, job_id)
    return store.get_job(job_id)


_COUNT_TAIL = re.compile(r", on \d+ ask\(s\) so far$")


def _without_count(text):
    return _COUNT_TAIL.sub("", (text or "").strip())


def _fail(job, kind, text="", status="failed"):
    store.update_job(job["id"], status=status, error_kind=kind, error_text=(text or "")[:300],
                     next_poll_at=None)


def _step_analysis(job):
    if job["status"] == "analysing":
        # A step that died mid-call (a restart). RoEx may have charged.
        _reservation_spent(job)
        return _fail(job, "no_answer")
    if job["status"] != "queued":
        return None
    src = store.get_source(job["source_id"])
    if not src or src.get("deleted_at") or not src.get("storage_key"):
        _take_reservation_back(job)
        return _fail(job, "", status="cancelled")
    if not store.set_status_if(job["id"], ("queued",), status="analysing",
                               attempts=(job.get("attempts") or 0) + 1):
        return None
    url = _roex_url(src, SOURCE_URL_TTL_ANALYSIS)
    if not url:
        _take_reservation_back(job)
        return _fail(job, "storage")
    out = roex.mix_analysis(url, src.get("analysis_style"), bool(src.get("is_master")))
    k = out.kind
    refused_unsent = k == "unavailable" or (k == "busy" and (not out.sent or out.status == 429))
    if k == "ok":
        store.take_reservation(job["id"])          # spent, as planned
        store.update_job(job["id"], status="reported", result=out.data,
                         credits_spent_estimate=(job.get("credits_spent_estimate") or 0) + REPORT_CREDITS,
                         error_kind=None, error_text=None, next_poll_at=None)
    elif k == "failed":
        # RoEx processed it and said it failed (or answered without a
        # report). Nothing in RoEx's documentation says a failed report is
        # free, so the reservation stays counted.
        _reservation_spent(job)
        _fail_roex(job, out)
    elif k in ("bad_request", "not_found"):
        # Refused before processing: nothing was charged.
        _take_reservation_back(job)
        _fail_roex(job, out)
    elif k == "credits":
        _take_reservation_back(job)
        _fail(job, "credits", out.roex_message, status="credits_short")
        _alert("credits", "RoEx is out of credits",
               "A mix report couldn't run because RoEx says the account is short of "
               "credits. Top up in the RoEx portal, then use Try again on the Release-Ready desk.")
    elif k == "auth":
        _take_reservation_back(job)
        _fail(job, "auth", "RoEx refused the API key", status="needs_owner")
        _alert_auth(out)
    elif refused_unsent:
        # Nothing reached RoEx (our limiter, no connection) or RoEx refused
        # it at the door (429): safe to try again, and nothing was charged.
        attempts = (job.get("attempts") or 0) + 1
        if attempts < 3:
            store.update_job(job["id"], status="queued", next_poll_at=_later(_backoff(attempts) * 4))
        else:
            _take_reservation_back(job)
            _fail(job, "unreachable", out.roex_message)
    elif k in ("server_error", "busy"):
        # A 5xx after the request went out, a gateway timeout included:
        # RoEx may have run the report and charged. Not repeated on its
        # own, and the credits stay counted.
        _reservation_spent(job)
        _fail(job, "roex_error", out.roex_message)
    elif k == "not_configured":
        _take_reservation_back(job)
        _fail(job, "not_connected")
    else:                                          # unknown / pending: may have charged
        _reservation_spent(job)
        _fail(job, "no_answer")
    return None


def _fail_roex(job, out):
    """RoEx said no. Its own words are quoted to the artist; when all we
    have is our own note (RoEx's answer lacked something), the artist gets
    a plain sentence and the note stays on the owner's desk."""
    if out.roex_message:
        return _fail(job, "roex_failed", out.roex_message)
    if out.note:
        return _fail(job, "bad_answer", out.note)
    return _fail(job, "roex_failed", "")


def _alert_auth(out):
    _alert("auth", "RoEx refused the API key",
           "RoEx refused Release-Ready's API key (HTTP %s). Check ROEX_API_KEY in Render."
           % (out.status or "no status"))


def _preview_elapsed(job):
    started = store.parse(job.get("submitted_at") or job.get("created_at"))
    return (store.now() - started) if started else timedelta(0)


def _submit_common(job, out):
    """What happens after asking RoEx to start a preview (either kind)."""
    k = out.kind
    if k == "ok":
        store.update_job(job["id"], status="processing", roex_task_id=out.data["task_id"],
                         submitted_at=store.iso(), attempts=0, next_poll_at=_later(BACKOFF[0]),
                         error_kind=None, error_text=None)
    elif k in ("busy", "unavailable", "server_error"):
        attempts = (job.get("attempts") or 0) + 1
        if attempts < 5:
            store.update_job(job["id"], attempts=attempts, next_poll_at=_later(_backoff(attempts)))
        else:
            _fail(job, "unreachable", out.roex_message)
    elif k == "credits":
        _fail(job, "credits", out.roex_message, status="credits_short")
        _alert("credits", "RoEx is out of credits",
               "A free preview couldn't start because RoEx says the account is short of "
               "credits (previews are free only once credits have been bought). Top up in "
               "the RoEx portal.")
    elif k == "auth":
        _fail(job, "auth", "RoEx refused the API key", status="needs_owner")
        _alert_auth(out)
    elif k == "not_configured":
        _fail(job, "not_connected")
    elif k == "unknown":
        # RoEx may have started a task we have no id for. Previews are free;
        # the artist can ask again.
        _fail(job, "unreachable")
    else:
        _fail_roex(job, out)


def _preview_poll_result(job, out, measured=None):
    """What happens after asking RoEx whether a preview is ready."""
    k = out.kind
    if k == "ok":
        return _store_preview(job, out.data, measured)
    if k in ("pending", "busy", "unavailable", "unknown", "server_error"):
        # Whatever RoEx said while not producing a link. Keeping it is the
        # difference between "the provider is slow" and "the provider is
        # telling us something is wrong", which are otherwise the same
        # thing seen from here for the full forty-five minutes. It goes on
        # the job for the owner's desk, and into the log the first time it
        # changes - a poll every fifteen seconds must not fill the log with
        # one repeated sentence. The artist's wording is chosen by
        # error_kind and never quotes this, so nothing leaks into their page.
        said = (out.note or out.roex_message or "").strip()
        if not said:
            # The commonest case, and the one that left the desk blank: a
            # bare HTTP 202 with nothing in it. roex_client returns that
            # before it ever looks for a download link, so there is no
            # answer to quote - but "RoEx said 202 thirty times and never
            # sent a file" is still the fact worth having, because it
            # separates a provider that is refusing us from one whose queue
            # has swallowed the task.
            said = ("RoEx keeps answering %s (%s) and has sent no file, on %d "
                    "ask(s) so far" % (out.status if out.status is not None else "no status",
                                       k, (job.get("attempts") or 0) + 1))
        said = said[:300]
        note = {"error_text": said}
        # The count inside `said` changes on every poll, so comparing whole
        # strings would log the same sentence every fifteen seconds. Only a
        # change in what RoEx is doing is worth a line.
        before = (job.get("error_text") or "").strip()
        if _without_count(said) != _without_count(before):
            log.info("release_ready: preview %s not ready, RoEx said: %s", job["id"], said)
        if _preview_elapsed(job) > PREVIEW_DEADLINE:
            return _fail(job, "timeout", said or (job.get("error_text") or ""))
        attempts = (job.get("attempts") or 0) + 1
        return store.update_job(job["id"], attempts=attempts,
                                next_poll_at=_later(_backoff(attempts)), **note)
    if k == "not_found":
        return _fail(job, "not_found")
    if k == "credits":
        _alert("credits", "RoEx is out of credits",
               "A free preview couldn't be fetched because RoEx says the account is short "
               "of credits. Top up in the RoEx portal.")
        return _fail(job, "credits", out.roex_message, status="credits_short")
    if k == "auth":
        _alert_auth(out)
        return _fail(job, "auth", "RoEx refused the API key", status="needs_owner")
    if k == "not_configured":
        return store.update_job(job["id"], next_poll_at=_later(600))
    return _fail_roex(job, out)


def _store_preview(job, data, measured=None):
    """RoEx says the preview is ready. Fetch it and put it in our bucket.

    Every failure here used to be silent: the job went back on the clock
    with nothing recorded, so a preview RoEx had already produced and we
    could not keep looked exactly like a preview RoEx was still making, for
    forty-five minutes, and then failed as a timeout. It is not a timeout -
    RoEx finished - and the difference matters, because these are our
    problems to fix, not RoEx's. RoexDownloadError already says which one
    ("larger than expected" is MAX_PREVIEW_BYTES; the rest name the
    exception), so all that was missing was keeping it."""
    try:
        path, n, _sha = roex._download(data["url"], roex.MAX_PREVIEW_BYTES)
    except roex.RoexDownloadError as exc:
        return _preview_snag(job, str(exc) or "RoEx's file could not be fetched", 60)
    try:
        with open(path, "rb") as fh:
            body = fh.read()
    finally:
        _remove(path)
    if not body:
        return _preview_snag(job, "RoEx's file arrived empty", 60)
    wav = body[:4] == b"RIFF" and body[8:12] == b"WAVE"
    ext, ctype = (".wav", "audio/wav") if wav else (".mp3", "audio/mpeg")
    stored = _store_private("release_ready/%s/%s-preview%s" % (job["user_id"], job["id"], ext),
                            body, ctype)
    if not stored:
        return _preview_snag(job, "the preview came back from RoEx but our bucket "
                                  "would not take it", 120)
    result = dict(job.get("result") or {})
    result["preview"] = {"start": data.get("start"), "bytes": n, "mime_type": ctype}
    if measured is not None:
        result["preview"]["measured_lufs_full"] = measured
    store.update_job(job["id"], status="preview_ready", preview_key=stored,
                     preview_start=data.get("start"), result=result, next_poll_at=None,
                     error_kind=None, error_text=None)
    return None


def _preview_snag(job, said, seconds):
    """Our side could not keep a preview RoEx had ready. Say so and retry.

    Recorded on the job for the owner's desk and logged once per distinct
    reason, the same way a stalled poll is. The artist still reads their own
    plain sentence, chosen by error_kind."""
    said = said[:300]
    if _without_count(said) != _without_count((job.get("error_text") or "").strip()):
        log.warning("release_ready: preview %s came back but could not be kept: %s",
                    job["id"], said)
    if _preview_elapsed(job) > PREVIEW_DEADLINE:
        return _fail(job, "not_kept", said)
    return store.update_job(job["id"], error_text=said, next_poll_at=_later(seconds))


def _step_master(job):
    st = job["status"]
    if st == "queued":
        return _submit_master(job)
    if st == "processing":
        if not job.get("roex_task_id"):
            return _fail(job, "no_answer")
        return _preview_poll_result(job, roex.retrieve_preview_master(job["roex_task_id"]))
    if st in ("paid", "retrieving"):
        return _final(job)
    return None


def _submit_master(job):
    src = store.get_source(job["source_id"])
    if not src or src.get("deleted_at") or not src.get("storage_key"):
        return _fail(job, "", status="cancelled")
    s = job.get("settings") or {}
    start = None
    if job.get("wait_for_job_id"):
        first = store.get_job(job["wait_for_job_id"])
        if first and first.get("preview_start") is not None:
            start = first["preview_start"]
        elif (first and first["status"] in ("queued", "processing")
              and _preview_elapsed(dict(job, submitted_at=None)) < WAIT_FOR_START):
            # Same 30 seconds for a fair A/B: wait for the first preview to
            # say where it starts, for up to three minutes.
            return store.update_job(job["id"], next_poll_at=_later(10))
    url = _roex_url(src, SOURCE_URL_TTL_TASK)
    if not url:
        return _fail(job, "storage")
    hook = _webhook_for(job["id"])
    out = roex.mastering_preview(url, s.get("style"), s.get("loudness"),
                                 s.get("sample_rate") or "44100", start, hook)
    return _submit_common(job, out)


def _step_recombine(job):
    st = job["status"]
    if st == "queued":
        vocal = store.get_source(job["source_id"])
        beat = store.get_source(job.get("backing_source_id"))
        if not (vocal and beat) or vocal.get("deleted_at") or beat.get("deleted_at"):
            return _fail(job, "", status="cancelled")
        vurl = _roex_url(vocal, SOURCE_URL_TTL_TASK)
        burl = _roex_url(beat, SOURCE_URL_TTL_TASK)
        if not (vurl and burl):
            return _fail(job, "storage")
        s = job.get("settings") or {}
        hook = _webhook_for(job["id"])
        return _submit_common(job, roex.recombine(vurl, burl, s.get("style"),
                                                  s.get("loudness") or "MEDIUM",
                                                  s.get("vocal_gain_db") or 0.0, hook))
    if st == "processing":
        if not job.get("roex_task_id"):
            return _fail(job, "no_answer")
        out = roex.recombine_status(job["roex_task_id"])
        if out.kind == "failed":
            return _fail_roex(job, out)
        if out.kind != "ok":
            return _preview_poll_result(job, out)
        prev = roex.retrieve_recombine_preview(job["roex_task_id"])
        if prev.kind == "ok":
            return _preview_poll_result(job, prev, prev.data.get("measured_lufs_full"))
        return _preview_poll_result(job, prev)
    if st in ("paid", "retrieving"):
        return _final(job)
    return None


# --- the paid final -------------------------------------------------------------------------

def _may_retrieve(job):
    """The one guard in front of every paid RoEx call: a claimed payment,
    or the owner's own release."""
    return bool(job.get("paid_at") or job.get("owner_release_by"))


def _needs_owner(job, kind, text, title, body):
    """A paid (or owner-released) master stopped. The alert is this job's
    own, so another alert in the same hour cannot silence it."""
    _fail(job, kind, text, status="needs_owner")
    _alert("paid_needs_owner:%s" % job["id"], title, body)


def _final(job):
    if not _may_retrieve(job):
        log.warning("release_ready: job %s reached a paid step without a payment", job["id"])
        return _fail(job, "unpaid", "reached a paid step without a payment", status="needs_owner")
    master = job["type"] == "master_preview"
    if job["status"] == "retrieving":
        if job.get("roex_output_url"):
            return _store_master(job)
        if master and job.get("retrieve_called_at"):
            # Interrupted after asking RoEx. It may have charged; asking
            # again may charge again (the spec does not say). The owner
            # decides.
            return _needs_owner(job, "interrupted", "the retrieval was interrupted",
                                "A paid master needs you",
                                "A master retrieval was interrupted. Check it on the "
                                "Release-Ready desk before trying again.")
    if not store.set_status_if(job["id"], ("paid", "retrieving"), status="retrieving",
                               retrieve_called_at=store.iso()):
        return None
    out = (roex.retrieve_final_master if master else roex.retrieve_recombine)(job["roex_task_id"])
    k = out.kind
    if k == "ok":
        result = dict(job.get("result") or {})
        if not master:
            result["master"] = {f: out.data.get(f) for f in (
                "measured_lufs", "peak_level", "track_length_seconds", "sample_rate",
                "bit_depth", "channels", "processing")}
        store.update_job(job["id"], roex_output_url=out.data["url"],
                         roex_output_expires=_later(24 * 3600), result=result, attempts=0)
        return _store_master(store.get_job(job["id"]))
    if k == "busy" and (not out.sent or out.status == 429):
        # Refused before RoEx did anything: nothing was charged.
        return store.update_job(job["id"], status="paid", retrieve_called_at=None,
                                next_poll_at=_later(60))
    if k == "credits":
        _fail(job, "credits", out.roex_message, status="credits_short")
        _alert("paid_credits:%s" % job["id"], "A paid master is waiting on RoEx credits",
               "An artist paid for a master and RoEx says the account is short of credits. "
               "Top up in the RoEx portal, then press Try the retrieval again on the "
               "Release-Ready desk.")
        return None
    # A master that is not ready (HTTP 202) is NOT asked again here: RoEx
    # does not document whether a repeat /retrievefinalmaster charges again,
    # so every repeat is the owner's decision, from the desk.
    if not master and k in ("pending", "busy", "unavailable", "unknown"):
        # /retrieverecombine is documented as safe to repeat.
        attempts = (job.get("attempts") or 0) + 1
        if attempts <= 8:
            return store.update_job(job["id"], attempts=attempts,
                                    next_poll_at=_later(_backoff(attempts) * 2))
    if k == "auth":
        _alert_auth(out)
    # For the owner's desk only: our note on what the answer lacked, and
    # RoEx's own words, both kept.
    said = "; RoEx said: ".join(t for t in (out.note, out.roex_message) if t) or k
    return _needs_owner(job, k, said, "A paid master needs you",
                        "RoEx didn't hand over a paid master (%s). Check it on the "
                        "Release-Ready desk." % k.replace("_", " "))


def _store_master(job):
    expires = store.parse(job.get("roex_output_expires"))
    expired = bool(expires and store.now() > expires)
    try:
        path, n, sha = roex._download(job["roex_output_url"], roex.MAX_MASTER_BYTES)
    except roex.RoexDownloadError:
        if expired:
            return _needs_owner(job, "expired", "RoEx's link ran out before the master was stored",
                                "A paid master needs you",
                                "RoEx's download link ran out before the master was stored.")
        attempts = (job.get("attempts") or 0) + 1
        return store.update_job(job["id"], attempts=attempts, next_poll_at=_later(60))
    try:
        facts = audio_probe.wav_facts(path)
        with open(path, "rb") as fh:
            data = fh.read()
    finally:
        _remove(path)
    if not n or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return _needs_owner(job, "not_wav", "RoEx's file wasn't a WAV",
                            "A paid master needs you", "RoEx's master file wasn't a WAV.")
    key = "release_ready/%s/%s-master.wav" % (job["user_id"], job["id"])
    stored = _store_private(key, data, "audio/wav")
    if not stored:
        if expired:
            return _needs_owner(job, "storage", "the master couldn't be stored",
                                "A paid master needs you",
                                "A paid master couldn't be written to storage.")
        return store.update_job(job["id"], next_poll_at=_later(120))
    credits = roex.CREDITS["master_final" if job["type"] == "master_preview" else "recombine_final"]
    # What the stored file's own header says, so the page's format line is
    # read off the file, not assumed.
    result = dict(job.get("result") or {})
    if facts:
        result["master_file"] = {f: facts.get(f) for f in
                                 ("sample_rate", "bit_depth", "channels", "duration_s")}
    # The file is ours now, so the job says so, even if a step that thought
    # this one had died already handed it to the owner.
    moved = store.set_status_if(
        job["id"], ("retrieving", "needs_owner"), status="stored", master_key=stored,
        master_sha256=sha, result=result,
        master_bytes=n, output_url="%s/jobs/%s/master.wav" % (PAGE, job["id"]),
        stored_at=store.iso(), roex_output_url=None, roex_output_expires=None,
        credits_spent_estimate=(job.get("credits_spent_estimate") or 0) + credits,
        error_kind=None, error_text=None, next_poll_at=None)
    if moved:
        rrs.record_paid(credits)
        attach_master(store.get_job(job["id"]))
    return None


def attach_master(job):
    """The stored master joins the song's Track Passport: the one picked at
    upload, or the passport matched (or opened) by the song's title."""
    src = store.get_source(job["source_id"]) or {}
    uid = job["user_id"]
    track_id = src.get("os_track_id")
    if track_id and not db.get_os_track(uid, track_id):
        track_id = None
    if not track_id:
        track_id = db.add_os_track(uid, (src.get("title") or "Untitled")[:120])
    store.update_job(job["id"], os_track_id=track_id)
    db.notify(uid, "billing", "Your master is stored",
              "%s is in your catalog, on its Track Passport." % (src.get("title") or "Your song"),
              "%s/sources/%s" % (PAGE, job["source_id"]))
    return track_id


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


# --- the queue sweep ---------------------------------------------------------------------

def run_due(limit=20):
    """Move whatever is due: budget-paused reports when the budget allows,
    jobs whose next poll is due, leases that ran out. Called from the
    daily /reminders/run and the owner's Run the queue now. Never starts a
    paid final on its own: those only move for a paid or released job."""
    out = {"resumed": 0, "started": 0, "stuck_paid": 0}
    if roex.configured():
        for job in store.jobs_with_status(("paused_budget",), limit):
            ok, mon, _counted = rrs.reserve_auto(job["user_id"], REPORT_CREDITS, manual=True)
            if not ok:
                break
            if store.set_status_if(job["id"], ("paused_budget",), status="queued",
                                   budget_reserved=REPORT_CREDITS, budget_month=mon,
                                   budget_artist=0, next_poll_at=store.iso(),
                                   error_kind=None, error_text=None):
                out["resumed"] += 1
            else:
                rrs.release_auto(job["user_id"], REPORT_CREDITS, mon, False)
    cutoff = store.now() - timedelta(minutes=30)
    for job in store.jobs_with_status(("paid", "retrieving", "credits_short", "needs_owner")):
        if job["status"] in ("credits_short", "needs_owner") and not job.get("paid_at"):
            continue                # an unpaid preview: not money waiting
        paid = store.parse(job.get("paid_at") or job.get("owner_release_at"))
        if paid and paid < cutoff:
            out["stuck_paid"] += 1
    if out["stuck_paid"]:
        _alert("paid_stuck", "A paid master is taking too long",
               "%d paid master(s) have not been stored 30 minutes after payment. See the "
               "Release-Ready desk." % out["stuck_paid"])
    for job in store.due_jobs(limit):
        if _spawn(advance, job["id"]):
            out["started"] += 1
    return out


def _kick(jobs):
    """A status poll moves the jobs that are due and free. It cannot start
    a paid final for an unpaid job: _final checks for itself."""
    t = store.now()
    for job in jobs:
        if job["status"] not in store.IN_FLIGHT:
            continue
        due = store.parse(job.get("next_poll_at"))
        lease = store.parse(job.get("lease_until"))
        if (due is None or due <= t) and (lease is None or lease < t):
            _spawn(advance, job["id"])


# --- what the page and its script read ----------------------------------------------------

def _style_label(jtype, code):
    table = roex.RECOMBINE_STYLES if jtype == "recombine" else roex.MASTER_STYLES
    return roex.label_for(table, code)


def public_job(job, viewer=None, seat=False):
    """A job as the artist's page may see it. Never a RoEx task id, a RoEx
    link, a webhook token or anything the owner's desk keeps."""
    paid = bool(job.get("paid_at"))
    s = job.get("settings") or {}
    out = {
        "id": job["id"], "type": job["type"], "status": job["status"],
        "chip": chip_for(job["type"], job["status"], paid),
        "tone": chip_tone(job["status"]),
        "message": message_for(job),
        "in_flight": job["status"] in store.IN_FLIGHT,
        "created_at": job.get("created_at"),
        "created_day": day(job.get("created_at")),
        "paid": paid,
    }
    if job["type"] == "mix_analysis":
        out["report"] = (report_view(job.get("result"), s.get("is_master"))
                         if job["status"] == "reported" else None)
        return out
    out["settings"] = {
        "style": s.get("style"), "style_label": _style_label(job["type"], s.get("style")),
        "loudness": s.get("loudness"),
        "loudness_label": "Loudness setting: %s" % roex.label_for(roex.LOUDNESS, s.get("loudness")),
    }
    if job["type"] == "recombine":
        out["settings"]["vocal_gain_db"] = s.get("vocal_gain_db") or 0.0
    prev = (job.get("result") or {}).get("preview") or {}
    if job.get("preview_key"):
        start = job.get("preview_start")
        out["preview"] = {"url": "%s/jobs/%s/preview" % (PAGE, job["id"]),
                          "starts_at": ("Starts at %s" % audio_probe.mmss(start))
                          if start is not None else ""}
        lufs = prev.get("measured_lufs_full")
        if job["type"] == "recombine" and lufs is not None:
            out["preview"]["measured"] = ("Measured by RoEx: %.1f LUFS (the whole master)"
                                          % float(lufs))
    else:
        out["preview"] = None
    if job["status"] == "stored" and job.get("master_key"):
        m = (job.get("result") or {}).get("master") or {}
        master = {"url": job.get("output_url"), "bytes": job.get("master_bytes"),
                  "size": size(job.get("master_bytes")),
                  "stored_at": job.get("stored_at"), "stored_day": day(job.get("stored_at")),
                  "format": master_format(job),
                  "delete_url": "%s/jobs/%s/master/delete" % (PAGE, job["id"])}
        if job["type"] == "recombine":
            loud = _figure(m.get("measured_lufs"), "LUFS")
            peak = _figure(m.get("peak_level"), "dBFS")
            master["measured"] = {
                "label": "Measured by RoEx",
                "loudness": loud,
                "true_peak": peak,
                # One "Not measured" when RoEx sent neither figure.
                "text": (NOT_MEASURED if loud == NOT_MEASURED and peak == NOT_MEASURED
                         else "%s, true peak %s" % (loud, peak)),
            }
        out["master"] = master
        track = job.get("os_track_id")
        src = store.get_source(job["source_id"]) or {}
        title = src.get("title") or ""
        out["next"] = {
            "passport": "/tracks/%s" % track if track else None,
            "smart_link": "/links/new?" + urllib.parse.urlencode({"title": title}),
            "rollout": "/rollout-studio/new",
        }
    else:
        out["master"] = None
    out["buy"] = _buy_state(job, seat)
    # A payment that came in too late to be used (claim_session "stale").
    out["payment_note"] = (COPY["stale_payment"]
                           if (job.get("settings") or {}).get("stale_payments")
                           and not job.get("paid_at") else "")
    return out


def master_format(job):
    """The stored master's format line, from what the file's own header
    said when it was stored, else from the figures RoEx returned with it,
    else just "WAV". Never a figure nobody read."""
    res = job.get("result") or {}
    facts = res.get("master_file") or {}
    rate, bits = facts.get("sample_rate"), facts.get("bit_depth")
    if not rate and not bits:
        m = res.get("master") or {}
        rate, bits = m.get("sample_rate"), m.get("bit_depth")
    tail = []
    try:
        if rate and float(rate) > 0:
            tail.append(_khz(float(rate)))
    except (TypeError, ValueError):
        pass
    if isinstance(bits, int) and bits > 0:
        tail.append("%d-bit" % bits)
    return ("WAV, " + " ".join(tail)) if tail else "WAV"


def _buy_state(job, seat=False):
    kind = "master" if job["type"] == "master_preview" else "recombine"
    price = rrs.price_display(kind)
    state = {"can": False, "reason": "", "price": price,
             "label": "Buy this master: $%s" % price,
             "note": "One payment. The full master is stored in your catalog when it's ready.",
             "url": "%s/jobs/%s/buy" % (PAGE, job["id"])}
    if job["status"] != "preview_ready" or job.get("paid_at"):
        state["hidden"] = True
        return state
    if seat:
        state["reason"] = COPY["seat_buy"]
    elif _too_old(job):
        state["reason"] = COPY["fresh_preview"]
    elif not stripe_provider.configured():
        state["reason"] = COPY["no_payments"]
    else:
        state["can"] = True
    return state


def _too_old(job):
    made = store.parse(job.get("submitted_at") or job.get("created_at"))
    return bool(made and store.now() - made > BUY_WITHIN)


def _too_late_to_claim(job):
    """The link RoEx was given for this preview's audio has run out, or is
    about to: a payment now cannot become a master."""
    made = store.parse(job.get("submitted_at") or job.get("created_at"))
    return bool(made and store.now() - made > CLAIM_WITHIN)


def source_kind(src):
    return "pair" if src.get("pair_id") else "mix"


_CHIP_ORDER = ("stored", "paid", "retrieving", "needs_owner", "credits_short", "preview_ready",
               "processing", "queued", "analysing", "reported", "paused_budget", "on_request",
               "failed")


def _furthest(jobs):
    best = None
    for job in jobs:
        if job["status"] not in _CHIP_ORDER:
            continue
        if best is None or _CHIP_ORDER.index(job["status"]) < _CHIP_ORDER.index(best["status"]):
            best = job
    return best


def source_chip(jobs):
    """One chip for an upload, from its jobs: the furthest along wins."""
    best = _furthest(jobs)
    if best is None:
        return ""
    if best["status"] == "preview_ready":
        return "Previews ready"
    return chip_for(best["type"], best["status"], bool(best.get("paid_at")))


# The path an upload walks, as the artist sees it. Where it stands is read
# off the jobs' stored statuses; nothing here is a stage nobody reached.
STEPS_MIX = (("check", "Mix report"), ("preview", "Free previews"), ("buy", "Buy the master"),
             ("stored", "In your catalog"))
STEPS_PAIR = STEPS_MIX[1:]


def source_stage(kind, jobs):
    """(steps, current key, done keys) for the progress rail."""
    steps = STEPS_PAIR if kind == "pair" else STEPS_MIX
    keys = [k for k, _l in steps]
    statuses = {j["status"] for j in jobs if j["type"] != "mix_analysis"}
    paid = any(j.get("paid_at") for j in jobs if j["type"] != "mix_analysis")
    if "stored" in statuses:
        current = "stored"
    elif paid or statuses & {"paid", "retrieving", "preview_ready"}:
        current = "buy"
    elif statuses & {"queued", "processing"}:
        current = "preview"
    elif kind == "pair" or any(j["type"] == "mix_analysis" and j["status"] == "reported"
                               for j in jobs):
        current = "preview"
    else:
        current = "check"
    done = keys[:keys.index(current)]
    if current == "stored":
        done = keys
    return steps, current, done


def public_source(src, jobs=None, seat=False):
    jobs = jobs if jobs is not None else store.jobs_for_source(src["id"])
    report = next((j for j in reversed(jobs) if j["type"] == "mix_analysis"), None)
    previews = [j for j in jobs if j["type"] in ("master_preview", "recombine")]
    kind = source_kind(src)
    beat = None
    if kind == "pair":
        _vocal, beat = store.pair_sources(src["user_id"], src["pair_id"])
    used = previews_used(src["id"])
    per_file = rrs.previews_per_file()
    style = src.get("analysis_style")
    steps, current, done = source_stage(kind, jobs)
    best = _furthest(jobs)
    views = [public_job(j, seat=seat) for j in previews]
    report_waits = kind == "mix" and (
        report is None or report["status"] in ("on_request", "paused_budget", "failed",
                                               "credits_short"))
    budget_room = rrs.budget_left() >= REPORT_CREDITS
    runs_left = rrs.manual_runs_left(src["id"])
    report_view_ = public_job(report, seat=seat) if report else None
    report_note = ""
    if report_waits and not budget_room:
        if report_view_ and report["status"] == "on_request":
            # "Press Get the mix report" would point at a button that is not
            # there: the budget is what stops it, so that is what it says.
            report_view_["message"] = COPY["budget"]
        elif (report or {}).get("status") != "paused_budget":
            report_note = COPY["budget"]
    elif report_waits and not runs_left:
        if report_view_ and report["status"] == "on_request":
            report_view_["message"] = COPY["report_runs"]
        else:
            report_note = COPY["report_runs"]
    return {
        "id": src["id"], "kind": kind, "title": src.get("title") or "Untitled",
        "kind_label": "A vocal and a beat" if kind == "pair" else "A finished mix",
        "created_at": src.get("created_at"), "created_day": day(src.get("created_at")),
        "files": [{"role": src["role"], "filename": src.get("filename"),
                   "length": audio_probe.mmss(src.get("duration_s"))}]
                 + ([{"role": "beat", "filename": beat.get("filename"),
                      "length": audio_probe.mmss(beat.get("duration_s"))}] if beat else []),
        "is_master": bool(src.get("is_master")),
        "genre": roex.label_for(roex.ANALYSIS_STYLES, style) if style else "",
        "chip": source_chip(jobs),
        "chip_tone": chip_tone(best["status"]) if best else "idle",
        "in_flight": any(j["status"] in store.IN_FLIGHT for j in jobs),
        "steps": [{"key": k, "label": l} for k, l in steps],
        "stage": current, "stage_done": done,
        "report": report_view_,
        # A button that would only be refused is not offered: pressing it
        # needs room in the owner's monthly budget, like any report, and a
        # press left this month for this file.
        "report_can_run": bool(report_waits and budget_room and runs_left),
        "report_budget_note": report_note,
        "previews": views,
        "masters": [v for v in views if v.get("master")],
        "stale_payment": any(v.get("payment_note") for v in views),
        "excerpt_note": excerpt_note(kind, previews),
        "previews_used": used,
        "previews_per_file": per_file,
        "previews_left": max(0, per_file - used),
        "previews_note": COPY["previews_used"] if used >= per_file else "",
        "defaults": {
            # The style of the last preview made, so "Try other settings"
            # starts where the artist left off; else the upload's genre.
            "style": ((views[-1]["settings"] or {}).get("style") if views else None)
                     or (roex.default_recombine_style(style) if kind == "pair"
                         else roex.default_master_style(style)),
            "loudness": ["MEDIUM", "HIGH"],
            "vocal_gain_db": 0.0,
        },
        "page": "%s/sources/%s" % (PAGE, src["id"]),
    }


def previews_used(source_id):
    """Free previews this upload has used: an unbought one older than the
    buy window no longer counts, so "make a fresh preview" can be done."""
    return store.previews_made(source_id, stale_before=store.iso(store.now() - BUY_WITHIN))


def excerpt_note(kind, previews):
    """What the previews card says about where the 30 seconds come from.
    Only what is true of these previews: RoEx picks the excerpt for a vocal
    and a beat, and a mix's previews only share one start when they do."""
    if kind == "pair":
        return ("Each preview is 30 seconds RoEx picks from the loudest part of the song, "
                "so two previews can start in different places. Each one says where it "
                "starts. The settings are RoEx's presets, not exact LUFS targets.")
    starts = [j.get("preview_start") for j in previews if j.get("preview_key")]
    if len(starts) >= 2 and None not in starts and len(set(starts)) == 1:
        return ("These previews are the same 30 seconds at different loudness settings. "
                "Listen to them, then buy the one you like. The settings are RoEx's "
                "presets, not exact LUFS targets.")
    if len(starts) >= 2:
        return ("These previews don't all start at the same place in the song. Each one "
                "says where it starts, so check that before you compare them. The settings "
                "are RoEx's presets, not exact LUFS targets.")
    return ("30 seconds at each loudness setting. We ask RoEx to start every preview of "
            "this file where the first one starts, so you can compare them. The settings "
            "are RoEx's presets, not exact LUFS targets.")


def auto_report_note(user):
    """The upload form's line about the mix report: only a promise the
    budget, the artist's monthly cap and the owner's switch will keep."""
    if not rrs.auto_analysis():
        return COPY["on_request"]
    if rrs.budget_left() < REPORT_CREDITS:
        return ("Mix reports are paused for the rest of this month. You can still send a "
                "mix, make free previews and buy a master.")
    if user and rrs.artist_reports(user["id"]) >= rrs.artist_cap():
        return ("You've used this month's automatic mix reports. A new upload's mix report "
                "runs when you ask for it.")
    return "A finished mix gets its mix report as soon as it lands."


def page_context(user):
    """Everything the page needs, for the template and the JSON alike."""
    state = connection_state(user)
    sources = []
    tracks = []
    if user:
        for src in store.list_sources(user["id"]):
            if src["role"] == "beat":
                continue                  # a pair is listed once, by its vocal
            sources.append(public_source(src, seat=_is_seat()))
        try:
            tracks = [(t["id"], t.get("title") or "Untitled")
                      for t in db.list_os_tracks(user["id"])]
        except Exception:
            tracks = []
    return {
        "state": state,
        "consent": consent_for_viewer(user),
        "sources": sources,
        # The Track Passports this account already has, for "which song is
        # this": the stored master joins the one picked here.
        "tracks": tracks,
        "analysis_styles": roex.ANALYSIS_STYLES,
        "master_styles": roex.MASTER_STYLES,
        "recombine_styles": roex.RECOMBINE_STYLES,
        "loudness_options": roex.LOUDNESS,
        "file_hint": "WAV, FLAC or MP3, up to 10 minutes, 44.1 or 48 kHz.",
        "price_master": rrs.price_display("master"),
        "price_recombine": rrs.price_display("recombine"),
        "payments_on": stripe_provider.configured(),
        "auto_report": rrs.auto_analysis(),
        "report_note": auto_report_note(user),
        "previews_per_file": rrs.previews_per_file(),
        "is_seat": _is_seat(),
        "read_only": _read_only_seat(),
        "read_only_note": READ_ONLY,
    }


# --- routes: the page ------------------------------------------------------------------------

def _need_user():
    user = _user()
    if user is None:
        abort(redirect("/login?next=" + urllib.parse.quote(request.path)))
    return user


@bp.route(PAGE)
def page():
    user = _need_user()
    ctx = page_context(user)
    return render_template("release_ready.html", active_page="release-ready",
                           msg=message_from_query(request.args), **ctx)


@bp.route(PAGE + "/state.json")
def page_state():
    user = _need_user()
    ctx = page_context(user)
    return jsonify({"ok": True, "state": ctx["state"], "consent": ctx["consent"],
                    "sources": ctx["sources"], "file_hint": ctx["file_hint"],
                    "price_master": ctx["price_master"],
                    "price_recombine": ctx["price_recombine"]})


@bp.route(PAGE + "/sources/<sid>")
def source_page(sid):
    user = _need_user()
    as_json = sid.endswith(".json")
    sid = sid[:-5] if as_json else sid
    src = store.source_for(user["id"], sid)
    if src is None or src["role"] == "beat":
        abort(404)
    jobs = store.jobs_for_source(src["id"])
    _kick(jobs)
    jobs = store.jobs_for_source(src["id"])
    view = public_source(src, jobs, seat=_is_seat())
    if as_json:
        return jsonify({"ok": True, "source": view, "state": connection_state(user)})
    return render_template("release_ready_source.html", active_page="release-ready",
                           source=view, state=connection_state(user),
                           master_styles=roex.MASTER_STYLES,
                           recombine_styles=roex.RECOMBINE_STYLES,
                           loudness_options=roex.LOUDNESS, is_seat=_is_seat(),
                           read_only=_read_only_seat(), read_only_note=READ_ONLY,
                           payments_on=stripe_provider.configured(),
                           price=rrs.price_display("recombine" if view["kind"] == "pair"
                                                   else "master"),
                           just_paid=request.args.get("paid") == "1",
                           msg=message_from_query(request.args))


@bp.route(PAGE + "/jobs/<jid>.json")
def job_state(jid):
    user = _need_user()
    job = store.job_for(user["id"], jid)
    if job is None:
        abort(404)
    _kick([job])
    job = store.get_job(jid)
    return jsonify({"ok": True, "job": public_job(job, seat=_is_seat())})


# --- routes: upload ----------------------------------------------------------------------------

def _refuse(message, status=400, where=None):
    if _wants_json() or where is None:
        return jsonify({"ok": False, "message": message}), status
    user = _user()
    ctx = page_context(user)
    return render_template("release_ready.html", active_page="release-ready",
                           msg=message, **ctx), status


def _gate(user, write=True):
    """The refusals every write shares, in order. None when it may go on."""
    state = connection_state(user)
    if not state["open"]:
        return state["message"], 409
    lock = _hooks["demo_locked"]
    if write and lock and lock():
        return COPY["demo"], 403
    return None


def _spool(fs):
    """Stream an uploaded file to a temp file: (path, bytes, sha256), or
    (None, bytes, None) when it passes the size cap."""
    fd, path = tempfile.mkstemp(prefix="rr-up-", suffix=".part")
    h, n = hashlib.sha256(), 0
    with os.fdopen(fd, "wb") as out:
        while True:
            chunk = fs.stream.read(1 << 20)
            if not chunk:
                break
            n += len(chunk)
            if n > audio_probe.MAX_BYTES:
                out.close()
                _remove(path)
                return None, n, None
            h.update(chunk)
            out.write(chunk)
    return path, n, h.hexdigest()


def _take_file(fs, who=""):
    """(file dict, None) or (None, refusal message)."""
    if fs is None or not fs.filename:
        return None, (("%s: choose a file." % who) if who else COPY["no_file"])
    path, n, sha = _spool(fs)
    if path is None:
        return None, _probe_message({"reason": "too_big"}, who)
    res = audio_probe.probe(path, fs.filename)
    if not res.get("ok"):
        _remove(path)
        return None, _probe_message(res, who)
    ext = os.path.splitext(fs.filename.lower())[1]
    name = os.path.basename(fs.filename.replace("\\", "/"))[:200]
    return {"path": path, "bytes": n, "sha256": sha, "ext": ext, "filename": name,
            "probe": res}, None


@bp.route(PAGE + "/upload", methods=["POST"])
def upload():
    user = _need_user()
    refused = _gate(user)
    if refused:
        return _refuse(*refused, where=PAGE)
    f = request.form
    if not (f.get("rights") and f.get("licence")):
        return _refuse(COPY["boxes"], 400, where=PAGE)
    # The words this person was shown: their own statement, or a seat's
    # statement on the artist's behalf. A form from the other kind of page
    # (or an older wording) is sent back to be read again.
    if (f.get("consent_version") or "") != consent_for_viewer(user)["version"]:
        return _refuse(COPY["consent_changed"], 400, where=PAGE)
    mode = "pair" if f.get("mode") == "pair" else "mix"
    style = f.get("analysis_style") or ""
    if mode == "mix" and style not in roex.codes(roex.ANALYSIS_STYLES):
        return _refuse(COPY["style"], 400, where=PAGE)
    if style not in roex.codes(roex.ANALYSIS_STYLES):
        style = ""          # a vocal and a beat: the genre only prefills the previews
    track_id = (f.get("os_track_id") or "").strip()
    track = db.get_os_track(user["id"], track_id) if track_id else None
    files = []
    try:
        wanted = (("file", ""),) if mode == "mix" else (("vocal", "The vocal"), ("beat", "The beat"))
        for field, who in wanted:
            got, why = _take_file(request.files.get(field), who)
            if why:
                return _refuse(why, 400, where=PAGE)
            got["role"] = "mix" if mode == "mix" else field
            files.append(got)
        title = ((f.get("title") or "").strip() or (track or {}).get("title")
                 or os.path.splitext(files[0]["filename"])[0] or "Untitled")[:120]
        return _accept(user, mode, files, title, track["id"] if track else None, style,
                       f.get("is_master") == "1")
    finally:
        for got in files:
            _remove(got["path"])


def _accept(user, mode, files, title, track_id, style, is_master):
    """Everything checked: record consent, store, open the jobs."""
    uid, actor = user["id"], session.get("user_id") or user["id"]
    actor_user = db.get_user(actor) or {}
    org = user.get("partner_id")
    words = consent_for_viewer(user)
    consents = [store.add_consent(uid, actor, actor_user.get("email"), got["sha256"],
                                  got["filename"], got["role"], words["version"],
                                  _consent_hash(words))
                for got in files]
    if mode == "mix":
        same = store.find_same_mix(uid, files[0]["sha256"], style, is_master)
        if same:
            # The same bytes with the same settings: its report is reused,
            # and nothing is charged twice.
            where = "%s/sources/%s" % (PAGE, same["id"])
            return _answer(True, "", 200, where, source_id=same["id"], reused=True, url=where)
    pair_id = uuid.uuid4().hex if mode == "pair" else None
    made = []
    for got, consent_id in zip(files, consents):
        sid = uuid.uuid4().hex
        with open(got["path"], "rb") as fh:
            data = fh.read()
        stored = _store_private("release_ready/%s/%s%s" % (uid, sid, got["ext"]), data,
                                got["probe"]["mime_type"])
        if not stored:
            for s in made:
                _delete_object(s["storage_key"])
                store.mark_source_deleted(s["id"])
            return _refuse(COPY["storage_failed"], 503, where=PAGE)
        p = got["probe"]
        store.add_source(id=sid, user_id=uid, uploaded_by=actor, organization_id=org,
                         pair_id=pair_id, role=got["role"], title=title, os_track_id=track_id,
                         filename=got["filename"], ext=got["ext"], mime_type=p["mime_type"],
                         storage_key=stored, bytes=got["bytes"], sha256=got["sha256"],
                         duration_s=p.get("duration_s"), sample_rate=p.get("sample_rate"),
                         bit_depth=p.get("bit_depth"), channels=p.get("channels"),
                         analysis_style=style or None, is_master=1 if is_master else 0,
                         consent_id=consent_id)
        made.append({"id": sid, "storage_key": stored})
    lead = made[0]["id"]
    if mode == "mix":
        _open_report(user, lead, style, is_master, actor, org)
    where = "%s/sources/%s" % (PAGE, lead)
    return _answer(True, "", 200, where, source_id=lead, url=where)


def _open_report(user, source_id, style, is_master, actor, org):
    uid = user["id"]
    fields = {"status": "on_request", "budget_reserved": 0}
    if rrs.auto_analysis():
        ok, mon_or_reason, counted = rrs.reserve_auto(uid, REPORT_CREDITS)
        if ok:
            fields = {"status": "queued", "budget_reserved": REPORT_CREDITS,
                      "budget_month": mon_or_reason, "budget_artist": 1 if counted else 0,
                      "next_poll_at": store.iso()}
        elif mon_or_reason == "budget":
            fields = {"status": "paused_budget", "error_kind": "budget"}
            _alert("budget", "Release-Ready mix reports are paused",
                   "This month's RoEx credit budget for automatic mix reports is used up. "
                   "Raise it in Settings, or reports resume on the 1st.", period="month")
        else:
            fields = {"status": "on_request", "error_kind": "artist_cap"}
    jid = store.add_job(user_id=uid, organization_id=org, type="mix_analysis",
                        credits_estimate=REPORT_CREDITS, created_by=actor, source_id=source_id,
                        settings={"style": style, "is_master": bool(is_master)}, **fields)
    if fields["status"] == "queued":
        _spawn(advance, jid)
    return jid


@bp.route(PAGE + "/sources/<sid>/report", methods=["POST"])
def run_report(sid):
    """Get the mix report (a button press): counts against the owner's
    budget, not the per-artist automatic cap."""
    user = _need_user()
    refused = _gate(user)
    if refused:
        return _answer(False, refused[0], refused[1], "%s/sources/%s" % (PAGE, sid))
    src = store.source_for(user["id"], sid)
    if src is None:
        abort(404)
    where = "%s/sources/%s" % (PAGE, sid)
    if src["role"] != "mix":
        return _answer(False, COPY["report_not_mix"], 400, where)
    jobs = store.jobs_for_source(sid, ("mix_analysis",))
    job = jobs[-1] if jobs else None
    if job and job["status"] == "reported":
        return _answer(False, COPY["report_here"], 409, where)
    if job and job["status"] not in ("on_request", "paused_budget", "failed", "credits_short"):
        return _answer(True, "", 200, where, job=public_job(job))
    # A report that keeps failing may be charged each time: a few presses
    # per file a month, then it waits for next month (or a new export).
    run_month = rrs.take_manual_run(sid)
    if run_month is None:
        return _answer(False, COPY["report_runs"], 429, where)
    ok, mon_or_reason, _counted = rrs.reserve_auto(user["id"], REPORT_CREDITS, manual=True)
    if not ok:
        rrs.give_manual_run_back(sid, run_month)
        if job:
            store.update_job(job["id"], status="paused_budget", error_kind="budget")
        return _answer(False, COPY["budget"], 409, where)
    fields = dict(status="queued", budget_reserved=REPORT_CREDITS, budget_month=mon_or_reason,
                  budget_artist=0, attempts=0, next_poll_at=store.iso(), error_kind=None,
                  error_text=None)
    if job:
        store.update_job(job["id"], **fields)
        jid = job["id"]
    else:
        jid = store.add_job(user_id=user["id"], organization_id=user.get("partner_id"),
                            type="mix_analysis", credits_estimate=REPORT_CREDITS,
                            created_by=session.get("user_id"), source_id=sid,
                            settings={"style": src.get("analysis_style"),
                                      "is_master": bool(src.get("is_master"))}, **fields)
    _spawn(advance, jid)
    return _answer(True, "", 200, where, job=public_job(store.get_job(jid)))


@bp.route(PAGE + "/sources/<sid>/previews", methods=["POST"])
def make_previews(sid):
    user = _need_user()
    where = "%s/sources/%s" % (PAGE, sid)
    refused = _gate(user)
    if refused:
        return _answer(False, refused[0], refused[1], where)
    src = store.source_for(user["id"], sid)
    if src is None or src["role"] == "beat":
        abort(404)
    pair = source_kind(src) == "pair"
    f = request.form
    loud = []
    for v in f.getlist("loudness") or [f.get("loudness_a"), f.get("loudness_b")]:
        if v and v in roex.codes(roex.LOUDNESS) and v not in loud:
            loud.append(v)
    if not loud or len(loud) > 2:
        return _answer(False, COPY["loudness"], 400, where)
    table = roex.RECOMBINE_STYLES if pair else roex.MASTER_STYLES
    style = f.get("style") or ""
    if style not in roex.codes(table):
        return _answer(False, COPY["style"], 400, where)
    if previews_used(sid) + len(loud) > rrs.previews_per_file():
        return _answer(False, COPY["previews_used"], 429, where)
    if store.previews_today(user["id"]) + len(loud) > rrs.previews_per_day():
        return _answer(False, COPY["previews_today"], 429, where)
    beat = None
    if pair:
        _vocal, beat = store.pair_sources(user["id"], src["pair_id"])
        if beat is None:
            abort(404)
        try:
            gain = max(-6.0, min(6.0, float(f.get("vocal_gain_db") or 0)))
        except ValueError:
            gain = 0.0
    # The first preview of this file sets where the 30 seconds start; every
    # later master preview waits for it, so the comparison is fair.
    earlier = [j for j in store.jobs_for_source(sid, ("master_preview",))
               if j["status"] not in ("failed", "cancelled")]
    first = earlier[0]["id"] if earlier else None
    made = []
    for level in loud:
        settings = {"style": style, "loudness": level}
        if pair:
            settings["vocal_gain_db"] = gain
        else:
            settings["sample_rate"] = "44100"
        jid = store.add_job(user_id=user["id"], organization_id=user.get("partner_id"),
                            type="recombine" if pair else "master_preview", status="queued",
                            credits_estimate=0, created_by=session.get("user_id"),
                            source_id=sid, backing_source_id=beat["id"] if beat else None,
                            settings=settings, wait_for_job_id=None if pair else first,
                            next_poll_at=store.iso())
        if not pair and first is None:
            first = jid
        made.append(jid)
    for jid in made:
        _spawn(advance, jid)
    return _answer(True, "", 200, where,
                   jobs=[public_job(store.get_job(j), seat=_is_seat()) for j in made])


@bp.route(PAGE + "/sources/<sid>/delete", methods=["POST"])
def delete_source(sid):
    """Our copies of the upload and its previews go; open work is
    cancelled. A paid master still being fetched is not touched, and a
    stored master stays until it is deleted on its own."""
    user = _need_user()
    src = store.source_for(user["id"], sid)
    if src is None or src["role"] == "beat":
        abort(404)
    where = "%s/sources/%s" % (PAGE, sid)
    group = [src]
    if src.get("pair_id"):
        _vocal, beat = store.pair_sources(user["id"], src["pair_id"])
        if beat:
            group.append(beat)
    if any(j["status"] in ("paid", "retrieving", "needs_owner", "credits_short") and j.get("paid_at")
           for j in store.jobs_for_source(src["id"])):
        # RoEx may read the upload again to finish a paid master.
        return _answer(False, COPY["delete_wait"], 409, where)
    # A checkout the artist opened for one of these previews and did not
    # pay is closed first, so nothing can be paid for an upload that is
    # gone. One paid in the meantime is claimed instead, and the upload
    # stays until its master is stored.
    refusal = _close_checkouts(store.jobs_for_source(src["id"]))
    if refusal:
        return _answer(False, refusal, 409, where)
    open_states = ("queued", "processing", "on_request", "paused_budget", "preview_ready")
    for s in group:
        for job in store.jobs_for_source(s["id"]):
            if job.get("preview_key"):
                _delete_object(job["preview_key"])
                store.update_job(job["id"], preview_key=None)
            if job["status"] in open_states:
                if store.set_status_if(job["id"], open_states, status="cancelled",
                                       next_poll_at=None):
                    _take_reservation_back(job)
        _delete_object(s.get("storage_key"))
        store.mark_source_deleted(s["id"])
    return _answer(True, COPY["deleted"], 200, PAGE)


def _close_checkouts(jobs):
    """Close every unpaid checkout opened for these jobs. None when they
    are all closed; otherwise the sentence to refuse the deletion with."""
    if not stripe_provider.configured():
        # Nothing can be checked. A payment that still arrives meets a
        # cancelled job, is recorded as stale and the owner is told.
        return None
    for job in jobs:
        if job.get("paid_at") or job["type"] not in ("master_preview", "recombine"):
            continue
        offered = set(((job.get("settings") or {}).get("offers") or {}).keys())
        offered.add(job.get("checkout_session_id") or "")
        offered.discard("")
        for session_id in sorted(offered):
            if store.payment_for_session(session_id):
                continue                  # already claimed, one way or another
            state, sess = stripe_provider.close_open_checkout(session_id)
            if state == "closed":
                continue
            if state == "complete" and (sess or {}).get("payment_status") == "paid":
                if claim_session(sess) in ("paid", "already", "retry"):
                    return COPY["delete_wait"]
                continue                  # recorded for the owner to refund
            return COPY["checkout_open"]
    return None


def _delete_object(path):
    if path and blob_store.is_remote(path):
        try:
            blob_store.delete(blob_store.key_of(path))
        except Exception:
            pass


# --- routes: audio out -----------------------------------------------------------------------

def _send_private(path, mime, filename=None):
    """Our copy of a file, to its owner only: always a short signed
    redirect to the bucket. Nothing is read into this server's memory (a
    master can be 160 MB), and no page needs it streamed through here."""
    if not path or not blob_store.is_remote(path):
        abort(404)
    try:
        signed = blob_store.presigned_get(blob_store.key_of(path), 300)
    except Exception:
        abort(503)
    return redirect(signed)


@bp.route(PAGE + "/jobs/<jid>/preview")
def preview_audio(jid):
    user = _need_user()
    job = store.job_for(user["id"], jid)
    if job is None or not job.get("preview_key"):
        abort(404)
    mime = ((job.get("result") or {}).get("preview") or {}).get("mime_type") or "audio/mpeg"
    return _send_private(job["preview_key"], mime)


@bp.route(PAGE + "/jobs/<jid>/master.wav")
def master_audio(jid):
    user = _need_user()
    job = store.job_for(user["id"], jid)
    if job is None or job["status"] != "stored" or not job.get("master_key"):
        abort(404)
    src = store.get_source(job["source_id"]) or {}
    name = "".join(c for c in (src.get("title") or "master") if c.isalnum() or c in " -_")
    return _send_private(job["master_key"], "audio/wav",
                         (name.strip()[:60] or "master") + " (master).wav")


@bp.route(PAGE + "/jobs/<jid>/master/delete", methods=["POST"])
def delete_master(jid):
    """The artist deletes a master they bought. Only the account holder:
    a team seat (or a partner acting as the artist) cannot throw away
    something paid for, which could not simply be bought again."""
    user = _need_user()
    job = store.job_for(user["id"], jid)
    if job is None or job["status"] != "stored":
        abort(404)
    src = store.get_source(job["source_id"]) or {}
    if request.form.get("from") == "passport" and job.get("os_track_id"):
        where = "/tracks/%s" % job["os_track_id"]
    elif src.get("deleted_at") or not src:
        where = PAGE
    else:
        where = "%s/sources/%s" % (PAGE, job["source_id"])
    if _is_seat():
        return _answer(False, COPY["seat_delete"], 403, where)
    _delete_object(job.get("master_key"))
    store.update_job(jid, status="master_deleted", master_key=None, output_url=None)
    return _answer(True, COPY["master_gone"], 200, where)


# --- routes: buying the master ----------------------------------------------------------------

@bp.route(PAGE + "/jobs/<jid>/buy", methods=["POST"])
def buy(jid):
    user = _need_user()
    job = store.job_for(user["id"], jid)
    if job is None or job["type"] not in ("master_preview", "recombine"):
        abort(404)
    where = "%s/sources/%s" % (PAGE, job["source_id"])
    if _is_seat():
        return _answer(False, COPY["seat_buy"], 403, where)
    refused = _gate(user)
    if refused:
        return _answer(False, refused[0], refused[1], where)
    if job.get("paid_at"):
        return _answer(True, "", 200, where)
    if job["status"] != "preview_ready":
        return _answer(False, COPY["not_buyable"], 409, where)
    if _too_old(job):
        return _answer(False, COPY["fresh_preview"], 409, where)
    if not stripe_provider.configured():
        return _answer(False, COPY["no_payments"], 409, where)
    if job.get("checkout_session_id"):
        # A checkout opened before may already be paid (the webhook and the
        # redirect both missed): claim it rather than sell it twice.
        prior = stripe_provider.get_checkout_session(job["checkout_session_id"])
        if prior and prior.get("status") == "complete" and prior.get("payment_status") == "paid":
            claim_session(prior)
            return _answer(True, "", 200, where)
    kind = "master" if job["type"] == "master_preview" else "recombine"
    cents = rrs.price_cents(kind)
    store.update_job(jid, price_cents=cents)
    src = store.get_source(job["source_id"]) or {}
    base = _hooks["public_url"]("") if _hooks["public_url"] else request.url_root.rstrip("/")
    # The checkout closes by itself (Stripe's default is 24 hours), well
    # inside the life of the link RoEx has to the audio. Opened in
    # half-hour windows, so a double click in one window reuses one
    # session (the idempotency key carries the window).
    window = int(time.time()) // 1800 * 1800
    sess = stripe_provider.create_release_ready_checkout(
        user["id"], user.get("email"), jid, kind, cents, src.get("title") or "", base,
        cancel_path=where, expires_at=window + int(CHECKOUT_OPEN.total_seconds()),
        window=window)
    if not sess or not sess.get("url"):
        return _answer(False, COPY["checkout_failed"], 502, where)
    # The price each checkout was opened at, so a payment is checked against
    # what that session asked for even if the owner changes the price later.
    settings = dict(job.get("settings") or {})
    offers = dict(settings.get("offers") or {})
    offers[sess.get("id") or ""] = cents
    settings["offers"] = offers
    store.update_job(jid, checkout_session_id=sess.get("id"), settings=settings)
    if _wants_json():
        return jsonify({"ok": True, "checkout_url": sess["url"]})
    return redirect(sess["url"], code=303)


def claim_session(obj):
    """A paid Release-Ready checkout, from the Stripe webhook or the success
    redirect, claimed once. Returns "paid", "already", "duplicate",
    "mismatch", "stale", "ignored" or "retry" (the database could not be
    reached: the webhook answers 503 so Stripe sends it again). "stale": the
    job could no longer be bought (its upload deleted, already stored, or
    too old for RoEx to finish), so nothing is retrieved and the owner is
    told to refund."""
    meta = obj.get("metadata") or {}
    if meta.get("kind") != "release_ready":
        return "ignored"
    if obj.get("payment_status") != "paid":
        return "ignored"
    try:
        job = store.get_job(meta.get("job_id") or "")
    except Exception:
        return "retry"
    if job is None:
        return "ignored"
    session_id = obj.get("id") or ""
    amount = int(obj.get("amount_total") or 0)
    currency = (obj.get("currency") or "").lower()
    if obj.get("client_reference_id") != job["user_id"]:
        _alert("pay_account", "A Release-Ready payment doesn't match its account",
               "A paid checkout named a different account than the master it was for. "
               "Nothing was retrieved. Check it in Stripe and refund if needed.")
        return "ignored"
    expected = ((job.get("settings") or {}).get("offers") or {}).get(session_id, job.get("price_cents"))
    amount_ok = currency == "usd" and expected is not None and amount == int(expected)
    try:
        result = store.claim_payment(session_id, job["id"], job["user_id"], amount, currency,
                                     amount_ok, payment_intent=obj.get("payment_intent"),
                                     fresh=not _too_late_to_claim(job))
    except Exception:
        return "retry"
    if result == "stale":
        settings = dict(job.get("settings") or {})
        settings["stale_payments"] = sorted(set(settings.get("stale_payments") or [])
                                            | {session_id})
        store.update_job(job["id"], settings=settings)
        _alert("pay_stale:%s" % job["id"], "A Release-Ready payment came in too late",
               "An artist paid $%.2f for a master that can no longer be made from that "
               "preview (the upload was deleted, the master was already released, or the "
               "preview was too old for RoEx to finish). Nothing was retrieved and no RoEx "
               "credits were spent. Refund it in Stripe." % (amount / 100.0))
    elif result == "mismatch":
        _alert("pay_amount", "A Release-Ready payment doesn't match the price",
               "A master was paid at a different amount than its price, so it was not "
               "retrieved. Check it in Stripe and refund or release it by hand.")
    elif result == "duplicate":
        _alert("pay_duplicate", "A master was paid for twice",
               "A second payment came in for a master that was already paid. Refund one "
               "of them in Stripe.")
    elif result == "paid":
        _spawn(advance, job["id"])
    elif result == "already" and job["status"] == "paid":
        _spawn(advance, job["id"])            # leased: a second step cannot run
    return result


@bp.route(PAGE + "/jobs/<jid>/paid")
def paid_return(jid):
    """Stripe's success redirect. The webhook usually gets there first;
    this claims the session itself if it did not."""
    user = _need_user()
    job = store.job_for(user["id"], jid)
    if job is None:
        abort(404)
    where = "%s/sources/%s" % (PAGE, job["source_id"])
    sid = (request.args.get("session_id") or "").strip()
    if sid and not job.get("paid_at"):
        sess = stripe_provider.get_checkout_session(sid)
        if (sess and sess.get("client_reference_id") == user["id"]
                and (sess.get("metadata") or {}).get("job_id") == jid):
            claim_session(sess)
    src = store.get_source(job["source_id"]) or {}
    if not src or src.get("deleted_at"):
        # The upload is gone, so its page is too: say what became of the
        # payment on the uploads page instead of a 404.
        job = store.get_job(jid) or job
        stale = (job.get("settings") or {}).get("stale_payments")
        return redirect(PAGE + ("?msg=stale_payment" if stale else ""))
    return redirect(where + "?paid=1")


# --- route: RoEx's webhook ------------------------------------------------------------------------

@bp.route("/webhooks/roex/<jid>/<token>", methods=["POST"])
def roex_webhook(jid, token):
    """RoEx calls this when a preview or recombine moves. Deliveries are
    unsigned and can repeat, so the body is never read for a status: a
    valid token only makes the job due now, and the next step reads RoEx
    itself. RoEx sends several updates per job (started, completed,
    failed), however close together, so none is dropped for coming soon
    after another: each one is counted, makes the job due, and starts a
    step when nobody holds the job. One that arrives while a step holds it
    is picked up when that step ends (advance compares the count). Every
    step is one free read, and the lease stops two running at once. An
    unknown job and a wrong token answer the same 404."""
    job = store.get_job(jid)
    want = (job or {}).get("webhook_token_hash") or ""
    got = hashlib.sha256((token or "").encode()).hexdigest()
    if not job or not want or not hmac.compare_digest(want, got):
        abort(404)
    store.touch_webhook(jid)
    if job["status"] in ("queued", "processing"):
        store.update_job(jid, next_poll_at=store.iso())
        lease = store.parse(job.get("lease_until"))
        if lease is None or lease < store.now():
            _spawn(advance, jid)
    return jsonify({"ok": True})


# --- the owner's desk --------------------------------------------------------------------------------

TYPE_WORDS = {"mix_analysis": "Mix report", "master_preview": "Master",
              "recombine": "Vocal and beat"}
# The owner's words for a status: plainer than the artist's chips, and
# honest about whose side a problem is on.
STATUS_WORDS = {
    "queued": "Waiting to run", "analysing": "RoEx is checking", "reported": "Report stored",
    "paused_budget": "Paused on the budget", "on_request": "Waits for the artist",
    "processing": "RoEx is working", "preview_ready": "Preview stored", "paid": "Paid, not fetched",
    "retrieving": "Fetching the master", "stored": "Master stored",
    "credits_short": "RoEx short of credits", "needs_owner": "Needs you", "failed": "Failed",
    "cancelled": "Cancelled", "master_deleted": "Master deleted by the artist",
}


def _owner_or_404():
    user = _user()
    if user is None:
        abort(redirect("/login?next=" + urllib.parse.quote(request.path)))
    if not _is_owner(user):
        abort(404)
    return user


def admin_data():
    """The owner's desk: credits this month against the budget, job counts,
    and for each organisation and artist: jobs, credits (an estimate from
    RoEx's price list), masters sold, revenue, estimated RoEx cost and the
    margin before Stripe's fees."""
    s = rrs.summary()
    usd = rrs.credit_usd()
    jobs = store.all_jobs()
    names = store.partner_names()
    counts, orgs, artists = {}, {}, {}
    for j in jobs:
        key = (j["type"], j["status"])
        counts[key] = counts.get(key, 0) + 1
        credits = int(j.get("credits_spent_estimate") or 0)
        revenue = 0
        if j.get("paid_at"):
            # What the payment still brings in: a refund comes off it, a
            # dispute takes all of it (Stripe's charge.refunded and
            # charge.dispute.created, via money_back()).
            pay = store.payment_for_session(j.get("paid_session_id"))
            revenue = store.net_cents(pay) if pay else int(j.get("amount_paid_cents") or 0)
        sold = 1 if revenue > 0 else 0
        org = j.get("organization_id") or ""
        for table, k, label in ((orgs, org, names.get(org) or ("Direct" if not org else org)),
                                (artists, j["user_id"],
                                 j.get("artist_name") or j.get("artist_email") or j["user_id"])):
            row = table.setdefault(k, {"id": k, "name": label, "jobs": 0, "credits": 0,
                                       "masters": 0, "revenue_cents": 0})
            row["jobs"] += 1
            row["credits"] += credits
            row["masters"] += sold
            row["revenue_cents"] += revenue
    for table in (orgs, artists):
        for row in table.values():
            cost = Decimal(row["credits"]) * usd
            row["revenue"] = "%.2f" % (Decimal(row["revenue_cents"]) / 100)
            row["cost"] = "%.2f" % cost
            row["margin"] = "%.2f" % (Decimal(row["revenue_cents"]) / 100 - cost)
    mon = s["month"]
    pays = [p for p in store.payments() if (p.get("claimed_at") or "").startswith(mon)
            and not p.get("duplicate") and not p.get("mismatch") and store.net_cents(p) > 0]
    cutoff = store.now() - timedelta(minutes=30)
    needs = []
    for j in jobs:
        paid_at = store.parse(j.get("paid_at") or j.get("owner_release_at"))
        stuck = j["status"] in ("paid", "retrieving") and paid_at and paid_at < cutoff
        if j["status"] in ("needs_owner", "credits_short") or stuck:
            paid = bool(j.get("paid_at"))
            expires = store.parse(j.get("roex_output_expires"))
            needs.append({"id": j["id"], "type": j["type"], "status": j["status"],
                          "type_label": TYPE_WORDS.get(j["type"], j["type"]),
                          "status_label": STATUS_WORDS.get(j["status"], j["status"]),
                          "artist": j.get("artist_name") or j.get("artist_email") or "",
                          "paid": paid, "error": j.get("error_text") or "",
                          # An unpaid preview gets its free preview made again;
                          # a paid final (or an owner release) is a separate,
                          # clearly named control.
                          "preview": (not paid and j["type"] != "mix_analysis"
                                      and not j.get("owner_release_by")),
                          "has_task": bool(j.get("roex_task_id")),
                          "link_held": bool(j.get("roex_output_url") and expires
                                            and expires > store.now()),
                          "created_at": j.get("created_at"), "created_day": day(j.get("created_at")),
                          "retry_url": "%s/jobs/%s/retry" % (ADMIN, j["id"])})
    return {
        "summary": s,
        "estimate_note": "Estimated from RoEx's price list. RoEx does not report what it charged.",
        "masters_sold_month": len(pays),
        "revenue_month": "%.2f" % (Decimal(sum(store.net_cents(p) for p in pays)) / 100),
        "counts": [{"type": t, "status": st, "n": n,
                    "type_label": TYPE_WORDS.get(t, t),
                    "status_label": STATUS_WORDS.get(st, st)}
                   for (t, st), n in sorted(counts.items())],
        "orgs": sorted(orgs.values(), key=lambda r: -r["jobs"]),
        "artists": sorted(artists.values(), key=lambda r: -r["jobs"]),
        "needs": needs,
        "payment_problems": [{"job_id": p["job_id"], "amount": "%.2f" % (int(p["amount_cents"] or 0) / 100),
                              "duplicate": bool(p["duplicate"]), "mismatch": p.get("mismatch") or "",
                              "text": _problem_words(p),
                              "claimed_at": p["claimed_at"]} for p in store.payment_problems()],
        "paused_reports": len(store.jobs_with_status(("paused_budget",))),
        "rate": roex.rate_counts(),
        "key_set": roex.configured(),
        "storage": storage_ready(),
        "provider_notes": _provider_notes(jobs),
    }


def _provider_notes(jobs, limit=10):
    """What RoEx last said about work that did not come back.

    "needs" is for jobs waiting on the owner, so a preview that failed or
    is still in flight never reaches it, and a preview's stored reason had
    nowhere on this desk to appear. That is how three quarters of an hour
    passed with the desk showing nothing but "Making previews": the reason
    existed and was never displayed. The artist's page still shows only its
    own plain sentence; this is the owner's copy, RoEx's words and ours
    kept apart by roex_client."""
    rows = []
    for j in jobs:
        said = (j.get("error_text") or "").strip()
        if not said:
            continue
        if j["status"] not in store.IN_FLIGHT and j["status"] != "failed":
            continue
        rows.append({"id": j["id"], "status": j["status"],
                     "status_label": STATUS_WORDS.get(j["status"], j["status"]),
                     "type_label": TYPE_WORDS.get(j["type"], j["type"]),
                     "artist": j.get("artist_name") or j.get("artist_email") or "",
                     "said": said,
                     "still_trying": j["status"] in store.IN_FLIGHT,
                     "created_day": day(j.get("created_at")),
                     "updated_at": j.get("updated_at") or j.get("created_at") or "",
                     "retry_url": "%s/jobs/%s/retry" % (ADMIN, j["id"])})
    rows.sort(key=lambda r: r["updated_at"], reverse=True)
    return rows[:limit]


def _problem_words(p):
    if p.get("disputed_at"):
        return "disputed by the card holder. Answer it in Stripe. It no longer counts as revenue"
    if p.get("duplicate"):
        return "paid twice for the same master, refund one in Stripe"
    if p.get("mismatch") == "stale":
        return ("paid after the preview could no longer be used, so nothing was retrieved. "
                "Refund it in Stripe")
    return "the amount didn't match the price, so nothing was retrieved"


def money_back(payment_intent, what, cents=0):
    """Stripe's charge.refunded or charge.dispute.created, for a
    Release-Ready payment: the payment row is marked, so the desk stops
    counting it as revenue and margin, and the owner is told. The master
    stays in the artist's catalog: whether it should go is the owner's call.
    Returns how many Release-Ready payments it touched."""
    rows = store.mark_money_back(payment_intent, what, cents)
    for p in rows:
        _alert("money_back:%s:%s" % (what, p.get("session_id")),
               "A Release-Ready payment was %s" % what,
               "A payment of $%.2f for a Release-Ready master was %s in Stripe. The desk no "
               "longer counts it as revenue. The master is still in the artist's catalog."
               % (int(p.get("amount_cents") or 0) / 100.0, what))
    return len(rows)


@bp.route(ADMIN)
def admin_page():
    _owner_or_404()
    return render_template("release_ready_admin.html", active_page="release-ready-admin",
                           data=admin_data(), msg=message_from_query(request.args),
                           storage_report=_last_storage_report())


STORAGE_REPORT_KEY = "release_ready:storage_report"


def _last_storage_report():
    """The most recent bucket test, or None.

    Kept rather than rendered straight back, for two reasons. A POST that
    renders its own page does not survive this desk's own round trip - every
    other button here redirects, and one that did not came back to the plain
    page with the answer lost. And an answer worth having is worth still
    being there on the next page view, beside the badge it corrects."""
    raw = db.get_kv(STORAGE_REPORT_KEY)
    if not raw:
        return None
    try:
        got = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(got, dict):
        return None
    got["tested_day"] = day_time(got.get("tested_at"))
    return got


@bp.route(ADMIN + "/storage", methods=["POST"])
def admin_storage():
    """Prove the bucket end to end, rather than reporting that its four
    variables are set.

    The badge beside this button reads "connected" whenever those
    variables are non-empty, which is how a run can sit at "Making
    previews" for three quarters of an hour while RoEx is in fact unable
    to download the track at all: it is handed a presigned link, the link
    is refused, and a provider that cannot fetch its input simply never
    reports a result. This stores a few bytes, fetches them back through a
    presigned link with no credentials attached - RoEx's exact position -
    and deletes them, at both a short lifetime and the seven-day one the
    app really hands out."""
    _owner_or_404()
    # Both lifetimes this module really hands out: the hour an analysis
    # gets and the seven days a mastering task gets. The long one is
    # R2's stated maximum, so it is the one most likely to be refused
    # while a short test link sails through.
    report = blob_store.round_trip(ttls=(SOURCE_URL_TTL_ANALYSIS, SOURCE_URL_TTL_TASK))
    report["tested_at"] = store.iso()
    db.set_kv(STORAGE_REPORT_KEY, json.dumps(report))
    return _answer(report["ok"], "", 200, ADMIN,
                   code="bucket_ok" if report["ok"] else "bucket_bad")


@bp.route(ADMIN + ".json")
def admin_json():
    _owner_or_404()
    return jsonify(dict(admin_data(), ok=True))


@bp.route(ADMIN + "/settings", methods=["POST"])
def admin_settings():
    _owner_or_404()
    errors = rrs.save_from_form(request.form)
    if _wants_json():
        return jsonify({"ok": not errors, "refused": errors, "settings": rrs.summary()}), \
            (400 if errors else 200)
    return redirect("/settings?rr=%s#release-ready" % ("saved" if not errors else "refused:" + ",".join(errors)))


@bp.route(ADMIN + "/jobs/<jid>/retry", methods=["POST"])
def admin_retry(jid):
    """The owner acts on a job that needs them. Three different things,
    never mixed up:

      a mix report       queued again, against the monthly budget
      action=preview     an unpaid preview that stopped on our side (RoEx
                         out of credits, the key refused): the FREE preview
                         is read again, or asked for again. No paid call.
      action=retrieve    a paid master (or one the owner releases without
                         payment, which needs the box ticked). If RoEx
                         already handed over its download link and the link
                         still works, only the download and the store run
                         again: RoEx is not asked a second time. Otherwise
                         exactly one more /retrievefinalmaster (or
                         /retrieverecombine), after the owner has looked.
    """
    owner = _owner_or_404()
    job = store.get_job(jid)
    if job is None:
        abort(404)
    if job["type"] == "mix_analysis":
        if job["status"] not in ("needs_owner", "credits_short", "failed", "paused_budget"):
            return _answer(False, DESK_COPY["report_not_waiting"], 409, ADMIN)
        ok, mon, _c = rrs.reserve_auto(job["user_id"], REPORT_CREDITS, manual=True)
        if not ok:
            return _answer(False, DESK_COPY["budget_used"], 409, ADMIN)
        store.update_job(jid, status="queued", budget_reserved=REPORT_CREDITS, budget_month=mon,
                         budget_artist=0, attempts=0, next_poll_at=store.iso(),
                         error_kind=None, error_text=None)
        _spawn(advance, jid)
        return _answer(True, DESK_COPY["report_queued"], 200, ADMIN)
    lease = store.parse(job.get("lease_until"))
    if lease and lease > store.now():
        return _answer(False, DESK_COPY["job_busy"], 409, ADMIN)
    paid = bool(job.get("paid_at"))
    released = paid or job.get("owner_release_by") or request.form.get("unpaid_ok") == "1"
    action = request.form.get("action") or ("retrieve" if released else "preview")
    if action == "preview":
        return _admin_preview_again(job)
    if not job.get("roex_task_id"):
        return _answer(False, DESK_COPY["never_started"], 409, ADMIN)
    if job["status"] not in ("needs_owner", "credits_short", "paid", "retrieving", "preview_ready"):
        return _answer(False, DESK_COPY["job_not_waiting"], 409, ADMIN)
    if not paid and not job.get("owner_release_by") and request.form.get("unpaid_ok") != "1":
        return _answer(False, DESK_COPY["tick_unpaid"], 409, ADMIN)
    fields = dict(attempts=0, next_poll_at=store.iso(), error_kind=None, error_text=None)
    if not paid:
        fields.update(owner_release_by=session.get("user_id") or owner["id"],
                      owner_release_at=store.iso())
    expires = store.parse(job.get("roex_output_expires"))
    if job.get("roex_output_url") and expires and expires > store.now():
        # RoEx has handed the master over already: fetch and store it again
        # from that link. Asking RoEx again could charge again.
        store.update_job(jid, status="retrieving", **fields)
        _spawn(advance, jid)
        return _answer(True, DESK_COPY["refetch_started"], 200, ADMIN)
    store.update_job(jid, status="paid", retrieve_called_at=None, roex_output_url=None,
                     roex_output_expires=None, **fields)
    _spawn(advance, jid)
    return _answer(True, DESK_COPY["retrieval_started"], 200, ADMIN)


def _admin_preview_again(job):
    """An unpaid preview that stopped on our side: made again for free. If
    RoEx started it, RoEx is asked for it again; if RoEx never started it,
    or no longer has it, it is asked for afresh."""
    jid = job["id"]
    if job.get("paid_at") or job.get("owner_release_by"):
        return _answer(False, DESK_COPY["job_paid"], 409, ADMIN)
    if job["status"] not in ("needs_owner", "credits_short", "failed"):
        return _answer(False, DESK_COPY["job_not_waiting"], 409, ADMIN)
    fields = dict(attempts=0, next_poll_at=store.iso(), error_kind=None, error_text=None)
    if job.get("roex_task_id") and (job.get("error_kind") or "") not in (
            "not_found", "timeout", "roex_failed", "bad_answer"):
        store.update_job(jid, status="processing", **fields)
        _spawn(advance, jid)
        return _answer(True, DESK_COPY["preview_polled"], 200, ADMIN)
    store.update_job(jid, status="queued", roex_task_id=None, submitted_at=None, **fields)
    _spawn(advance, jid)
    return _answer(True, DESK_COPY["preview_again"], 200, ADMIN)


@bp.route(ADMIN + "/resume", methods=["POST"])
def admin_resume():
    _owner_or_404()
    got = run_due()
    return _answer(True, DESK_COPY["resumed"] % got["resumed"], 200, ADMIN, code="resumed",
                   n=got["resumed"], run=got)


@bp.route(ADMIN + "/run", methods=["POST"])
def admin_run():
    _owner_or_404()
    got = run_due()
    return _answer(True, DESK_COPY["queue_ran"] % got["started"], 200, ADMIN, code="queue_ran",
                   n=got["started"], run=got)


@bp.route(ADMIN + "/health", methods=["POST"])
def admin_health():
    _owner_or_404()
    out = roex.health()
    code = "health_" + out.kind
    if code in DESK_COPY:
        return _answer(out.ok, DESK_COPY[code], 200, ADMIN, code=code, kind=out.kind)
    status = out.status if isinstance(out.status, int) else 0
    return _answer(out.ok, DESK_COPY["health_status"] % status, 200, ADMIN,
                   code="health_status", n=status, kind=out.kind)


# --- wiring ---------------------------------------------------------------------------------------------

def init(app, current_user, notify_owners, is_owner_email, public_url, demo_locked=None):
    _hooks.update(current_user=current_user, notify_owners=notify_owners,
                  is_owner_email=is_owner_email, public_url=public_url,
                  demo_locked=demo_locked)
    store.init()
    app.register_blueprint(bp)

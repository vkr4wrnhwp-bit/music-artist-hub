"""The Studio room, as one screen.

The owner's mockup, 2026-09-22, and his brief for every room: "I want the
rooms to open up to engagement and awesomeness, not a lot of reading."

So this room opens on ONE thing - a photoreal master bus analyser carrying
the artist's last measured master: their cover art in the bay, the waveform
in the display, and the two figures that matter read out on the unit itself
rather than in a strip of stat cards above it.

WHERE EVERY FIGURE COMES FROM
-----------------------------
  measurement   db.latest_track_analysis - the Rack's own last run, to
                ITU-R BS.1770 / EBU R128. integrated is LUFS, true_peak is
                the dBTP headroom, and both are nullable because a
                measurement that did not produce one must not read as 0.
  tracks        db.list_os_tracks
  masters       release_ready_store.stored_masters - a master this account
                actually owns, not a job that was started
  covers        artwork_config.list_uploads, the artist's own files, each
                one's `path`
  ready         artist_os.clean_release over the catalogue

WHAT IT REFUSES TO DO
---------------------
  * Nothing unmeasured reads 0. -0.0 LUFS is a measurement; "Not measured
    yet" is the absence, and they must never look alike.
  * Nothing here claims a track is approved, released, or will survive a
    platform's encoder. We measured a file; the encoder has the last word
    and the unit says which standard we used.
  * No bit depth. The Rack stores sample rate and channels and does NOT
    store bit depth, so the unit does not print one.
  * The room edits nothing. Every control on the plate is photographed
    hardware; the knobs do not turn because nothing here would turn them.

THE PAGE FROM ZERO (owner's Studio spec, 2026-09-22)
----------------------------------------------------
An account with nothing tracked, measured or on file does not meet an
empty instrument. It meets an onboarding page: the Command Center's
three-screen plate drawn STATIC with this room's words, one card that
adds the first song, what Studio keeps together, the five-stage workflow
as education, the two empties in words, help, and the tools folded away.
The analyser above waits for a record - one track, cover or reading and
the populated room returns untouched. zero_page() holds it all; the
animated standby that used to run on the analyser is retired here.
"""
import artwork_config

# The path from a take to a record anybody can release. Each rung is a
# stored fact, and each one names what it counted.
STEPS = (
    ("tracked", "Tracked", "Recordings on file"),
    ("measured", "Measured", "The Rack has read them"),
    ("mastered", "Mastered", "A master you own"),
    ("art", "Art", "Covers on file"),
    ("ready", "Ready", "Checked before release"),
)

# What the analyser prints. The unit says the standard because a loudness
# figure without one is a number, not a measurement.
STANDARD = "ITU-R BS.1770 / EBU R128"

# How many covers the row shows before "View all".
COVERS_SHOWN = 5


def _n(value):
    return "{:,}".format(int(value))


def clock(seconds):
    """2:48, the way a transport reads. Blank when nothing measured it."""
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    m = int(seconds // 60)
    return "%d:%02d" % (m, int(seconds - m * 60))


def decibels(value, unit):
    """A reading, or the words that say nobody took one.

    A null is not a zero here and the difference matters more than usual:
    0.0 LUFS would be an extraordinarily loud master, and -0.0 dBTP would
    be a master clipping the ceiling. Printing either for "we never
    measured" would be alarming and wrong.
    """
    if value is None:
        return {"value": "Not measured yet", "unit": "", "measured": False}
    try:
        return {"value": "%.1f" % float(value), "unit": unit, "measured": True}
    except (TypeError, ValueError):
        return {"value": "Not measured yet", "unit": "", "measured": False}


def source_line(analysis):
    """The line under the title: what was measured, not what it will be.

    Bit depth is deliberately absent - track_analysis stores sample rate and
    channels and has no bit-depth column, so a "24-bit" here would be a
    number nobody read off the file.
    """
    if not analysis:
        return ""
    bits = []
    length = clock(analysis.get("duration"))
    if length:
        bits.append(length)
    rate = analysis.get("sample_rate")
    if rate:
        try:
            bits.append("%g kHz" % (int(rate) / 1000.0))
        except (TypeError, ValueError):
            pass
    channels = analysis.get("channels")
    if channels:
        bits.append("Stereo" if int(channels) == 2 else "Mono" if int(channels) == 1
                    else "%d channels" % int(channels))
    return " · ".join(bits)


def title_of(analysis):
    """What to call the measured file. Its own name, never a guess."""
    if not analysis:
        return ""
    name = (analysis.get("filename") or "").strip()
    if not name:
        return "Untitled measurement"
    for ext in (".wav", ".mp3", ".flac", ".aiff", ".aif", ".m4a", ".ogg"):
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return name


def analyser(analysis, cover):
    """The unit: what goes in the bay, the display and the two readouts."""
    return {
        "measured": bool(analysis),
        "title": title_of(analysis),
        "source": source_line(analysis),
        "standard": STANDARD,
        "cover": cover or "",
        "loudness": decibels((analysis or {}).get("integrated"), "LUFS"),
        "headroom": decibels((analysis or {}).get("true_peak"), "dBTP"),
        # The needles. A meter with nothing to show rests at the bottom of
        # its scale rather than sitting mid-dial as if it had a reading.
        "left": needle((analysis or {}).get("integrated")),
        "right": needle((analysis or {}).get("short_term_max")
                        if (analysis or {}).get("short_term_max") is not None
                        else (analysis or {}).get("integrated")),
        "when": (analysis or {}).get("measured_at") or "",
    }


def needle(lufs):
    """Where a VU needle sits for a loudness reading, 0 to 1.

    -30 LUFS or quieter is the bottom of the dial and 0 is the top. It is a
    picture of the figure printed beside it, never a substitute for it, and
    an unmeasured reading parks the needle at rest.
    """
    if lufs is None:
        return 0.0
    try:
        lufs = float(lufs)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, (lufs + 30.0) / 30.0))


def covers(files, limit=COVERS_SHOWN):
    """The artist's own artwork, newest first.

    artwork_config.list_uploads hands each file back as `path`
    ("/uploads/artup_<user>_<unix>.png"). This read only `url` and `href`
    until 2026-09-23, so every file was dropped and every account with
    covers was told "No art yet" (audit studio-1). `url` and `href` are
    still read for a caller that uses them.
    """
    rows = []
    for f in files or ():
        url = f.get("path") or f.get("url") or f.get("href") or ""
        if not url:
            continue
        # The file's own name is a storage key (artup_12_1727...png), not
        # a title, so the label is what the studio calls it and when.
        kind = (f.get("kind") or "").strip()
        when = (f.get("when") or "").strip()
        name = f.get("label") or (
            ("%s cover%s" % (kind, (", " + when) if when else "")) if kind else "Cover art")
        rows.append({"url": url, "name": name})
    return {"shown": rows[:limit], "total": len(rows),
            "more": max(0, len(rows) - limit)}


def path(tracks, measured, masters, covers_n, ready):
    """The five gold circles, each carrying what it counted."""
    state = {
        "tracked": (tracks > 0,
                    ("%s track%s" % (_n(tracks), "" if tracks == 1 else "s"))
                    if tracks else "No tracks yet"),
        "measured": (measured is not None,
                     measured or "Never measured"),
        "mastered": (masters > 0,
                     ("%s master%s" % (_n(masters), "" if masters == 1 else "s"))
                     if masters else "No master yet"),
        "art": (covers_n > 0,
                ("%s cover%s" % (_n(covers_n), "" if covers_n == 1 else "s"))
                if covers_n else "No art yet"),
        "ready": (ready is not None, ready or "Never checked"),
    }
    out = []
    for i, (key, name, sub) in enumerate(STEPS, start=1):
        reached, line = state[key]
        out.append({"key": key, "n": i, "name": name, "sub": sub,
                    "line": line, "reached": bool(reached)})
    return out


# --- THE PAGE FROM ZERO (owner's Studio spec, 2026-09-22) ----------------
# The rack is the Command Center's photographed three-screen plate
# (partials/cc_rack.html, static/img/command-plate.webp), STATIC: three
# stable screens, no rotation, no reel, no ticker. Words only, and the
# spec's words exactly.
ZERO_SUBTITLE = "Turn a song into a release-ready package."
ZERO_RACK = (
    ("Purpose", "Move music from working track to release-ready."),
    ("Start here", "Add your first song to open its Rack."),
    ("Good to know", "One approved version feeds Publishing and Releases."),
)
# The one door: the catalog's own add-a-song workflow, carrying the way
# back. /tracks forwards to /catalog?view=passports on a Pro plan and keeps
# both params (app.py os_tracks), so the return works on every plan.
SONG_DOOR = "/tracks?returnTo=/room/studio&from=song"
ZERO_PROJECT = {
    "title": "Create your first Studio project",
    "desc": ("Add a song and Street Banker opens its Studio workspace: the Rack "
             "for the working audio, Mix Check for the measurement, "
             "Release-Ready for the master."),
    "cta": "Add your first song",
    "href": SONG_DOOR,
    "note": "One catalog record, shared with Publishing and Releases.",
    # /tracks is the Publishing room's (team_areas), so a Studio-only seat
    # is told who adds songs rather than handed a button that bounces.
    "locked": ("Songs are added by the account owner or a seat with the "
               "Publishing room. The Studio opens here once one exists."),
}
# What one song record carries through this room. GOLD icons - the spec's
# ruling over the mockup's green ticks. These are not steps and not
# progress; they are the parts.
KEEPS = (
    ("song", "The song record", "The catalog entry every room shares."),
    ("tracked", "Working audio", "The takes and bounces in its Rack."),
    ("measured", "Measurements", "Loudness and headroom to the broadcast standard."),
    ("mastered", "Masters", "The versions you own, and the one you approve."),
    ("art", "Cover art", "Artwork at release size, on the same record."),
)
# The five stages, EDUCATIONAL on a new account: nothing is complete, in
# progress or blocked, and there is no percentage. The song record is
# highlighted as the first step. STEPS (Tracked .. Ready) stays the
# populated room's rail; this is the onboarding one.
WORKFLOW = (
    ("song", "Song record", "Create the catalog record everything else attaches to."),
    ("tracked", "Working audio", "Add the take or bounce to its Rack."),
    ("measured", "Mix Check", "Measure it to the broadcast standard, in your browser."),
    ("mastered", "Master", "Approve one version you own."),
    ("ready", "Release-ready package", "Art, master and checks, together for Releases."),
)
ZERO_TRACKS = ("Your tracks will appear here",
               "Once you add a song, its Studio workspace opens here with the "
               "Rack, Mix Check and Release-Ready on one record.")
ZERO_REVIEW = ("Nothing to review yet",
               "Masters waiting for your approval and checks that need "
               "attention will appear here.")
ZERO_HELP = ("Not sure where to begin?",
             "Start with the song record. Everything in Studio hangs off it.")
HELP_QUESTIONS = ("What is the difference between a track and a master?",
                  "How does Mix Check measure loudness?",
                  "What does Release-Ready need before it approves a version?")
# The two doors under "Your tracks will appear here", each with the way
# back; a seat sees only the ones it can open.
ZERO_LINKS = (("How the Rack measures", "/rack?returnTo=/room/studio"),
              ("What a song record holds", "/tracks?returnTo=/room/studio"))
# The sentence the room carries back from the song door.
DONE_LINE = "Your first song was added. Its Studio workspace is ready."


def done_line(came_from, tracks):
    """Said by the SAVED record, never by the param alone: ?from=song with
    no track on file says nothing."""
    return DONE_LINE if came_from == "song" and tracks > 0 else ""


def zero_page(can_open=None):
    """The page from zero. A seat sees only the doors it can open."""
    def may(href):
        return can_open is None or bool(can_open(href))
    song = may(SONG_DOOR)
    return {
        "subtitle": ZERO_SUBTITLE,
        "screens": [{"k": k, "v": v} for k, v in ZERO_RACK],
        "cta": ({"label": ZERO_PROJECT["cta"], "href": SONG_DOOR} if song else None),
        "project": dict(ZERO_PROJECT, can=song),
        "keeps": KEEPS,
        "workflow": WORKFLOW,
        "tracks": ZERO_TRACKS,
        "review": ZERO_REVIEW,
        "help": ZERO_HELP,
        "questions": HELP_QUESTIONS,
        "links": [(label, href) for label, href in ZERO_LINKS if may(href)],
    }


# The reel a READING window shows while it has nothing to read (owner,
# 2026-09-22: no words in an empty window, icons). This is the one piece
# of the old standby that is still read: a populated unit's empty LCDs.
STANDBY_FILL = ("rack", "mastered", "measured", "tracked", "art", "ready")


def _six(icons):
    """Six stops, always: the roll's keyframes step through six, and a
    five-icon reel ran its last stop into blank glass."""
    icons = list(icons or ())
    while icons and len(icons) < 6:
        icons.append(icons[len(icons) % len(icons)])
    return icons[:6]


def standby():
    """What a populated unit's empty windows fill with. The animated
    standby that once ran on an empty account is retired: that account
    meets the page from zero instead."""
    return {"fill": _six(STANDBY_FILL)}


# --- THE SHOWCASE (the demo account) --------------------------------------
# Owner's ruling: the demo account shows the showcase, never the page from
# zero. The demo seed carries statements only, so the demo's own rows
# opened the onboarding page - with an "Add your first song" door a locked
# demo cannot use - beside the "Sample data" lamp (audit studio-7). These
# figures are generated for the example, the page marks them Sample, and
# only the route decides who sees them (app.py _studio_room, the way
# _marketing_room does): a real account's figures are its own rows.
SHOWCASE_ANALYSIS = {
    "filename": "Midnight Drive.wav", "integrated": -9.4, "true_peak": -1.1,
    "short_term_max": -7.2, "duration": 214, "sample_rate": 48000,
    "channels": 2, "measured_at": "",
}
# The demo's five recordings (demo_seed.CSV), one master, one song blocked.
SHOWCASE_TRACKS = 5
SHOWCASE_MASTERS = 1
SHOWCASE_READY = "1 blocked"
# A sample has no date anybody measured it on, so the circle says so.
SHOWCASE_MEASURED = "Sample reading"


def showcase():
    """The demo account's studio: what build() takes, generated."""
    return {"analysis": dict(SHOWCASE_ANALYSIS), "art_files": [],
            "tracks": SHOWCASE_TRACKS, "masters": SHOWCASE_MASTERS,
            "ready": SHOWCASE_READY, "measured_label": SHOWCASE_MEASURED}


def new_account(analysis, tracks, covers_total):
    """Nothing measured, tracked or drawn: the page from zero."""
    return not analysis and not tracks and not covers_total


def build(analysis, cover, art_files, tracks, masters, ready, cards,
          artist_name="", measured_label=None, sample=False, can_open=None,
          zero=None):
    """Everything the screen renders. No page logic beyond this.

    `zero` is the route's decision (False for the showcase, whatever its
    rows); None decides it here from the counts."""
    art = covers(art_files)

    tiles = []
    # Release-Ready and Mix Check are still TWO pages, so they are still two
    # tiles (owner, 2026-09-22: "if it's going to be two doors, then leave
    # it two tiles"). They become one tile when they become one page.
    for key in ("rack", "release-ready", "studio", "remix-lab",
                "audio-studio", "artwork"):
        card = (cards or {}).get(key)
        if not card:
            continue
        href = card[0]
        if can_open and not can_open(href):
            continue
        # The owner's mark on a page they hid rides with the tile: the
        # drawer from zero shows it as the populated Marketing room does.
        tiles.append({"key": key, "href": href, "icon": card[1],
                      "name": card[2], "line": card[3],
                      "state": card[4] if len(card) > 4 else ""})

    # Nothing measured, nothing tracked, no art: the page from zero. One
    # track, one cover or one reading and the unit takes over untouched.
    idle = (new_account(analysis, tracks, art["total"])
            if zero is None else bool(zero))
    return {
        "artist_name": artist_name or "",
        "analyser": analyser(analysis, cover),
        "idle": idle,
        "zero": zero_page(can_open) if idle else None,
        "standby": standby(),
        "covers": art,
        "path": path(tracks, measured_label, masters, art["total"], ready),
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }

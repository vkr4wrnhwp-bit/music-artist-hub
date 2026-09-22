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
  covers        artwork_config.list_uploads, the artist's own files
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
    """The artist's own artwork, newest first."""
    rows = []
    for f in files or ():
        url = f.get("url") or f.get("href") or ""
        if not url:
            continue
        rows.append({"url": url, "name": f.get("label") or f.get("name") or ""})
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


# --- THE PLATE, as data ------------------------------------------------
# These fractions have always lived in static/css/studio-room.css (.sd-unit),
# which predates the shared kit. They are repeated here ONLY so the standby
# display can position itself the way every other room's does, and must
# stay in step with that sheet - tests/test_studio_room.py holds them
# together.
PLATE = {
    "bay":     (8.08, 12.34, 17.51, 70.47),
    "display": (29.00, 12.66, 47.22, 38.75),
    "lcd-top": (79.43, 12.66, 12.24, 16.88),
    "lcd-bot": (79.43, 36.88, 12.24, 16.41),
}


def box(key):
    """The inline custom properties that put a window on its glass."""
    x, y, w, h = PLATE[key]
    return "--x:%s%%;--y:%s%%;--w:%s%%;--h:%s%%" % (x, y, w, h)


# --- THE STANDBY DISPLAY, the owner's way (2026-09-22) -------------------
# The display sequences the room's features and glitches between them;
# the bay is a reel of icons, the top LCD ticks the feature names, the
# bottom LCD carries a hint of three words - that window is about 150px
# square at a desktop plate. Words only, never a figure. The owner
# supplies the final text per room at the audit.
STANDBY_FRAMES = (
    ("The Rack", "Measure a master to the broadcast standard, in your browser"),
    ("Release-Ready", "One master, checked and mastered, per track"),
    ("Remix Lab", "Stems in, a remix out, and a record of what was done"),
    ("Cover Art", "Artwork at release size, yours to keep"),
)
STANDBY_REELS = [("bay", "The bay", ("rack", "mastered", "measured", "tracked", "art", "ready"))]
# The LCDs are about 150px square at a desktop plate - the smallest
# windows on any plate - so the words are two apiece and the sizes go
# in with them (the first cut bled off the glass by half).
STANDBY_TIPS = ("lcd-bot", "Headroom", ["Measure a master", "Make a cover", "Remix a stem", "Check a release"])
STANDBY_TIP_SIZE = "clamp(8px, .78cqw, 12px)"
STANDBY_TICK_SIZE = "clamp(8px, .82cqw, 12.5px)"
STANDBY_TICKER = ("lcd-top", "Loudness", ["The Rack", "Release-Ready", "Mix Check", "Remix Lab", "Cover Art"])
STANDBY_CINE = ("display", "The display")
STANDBY_SIZE = ("clamp(22px, 4cqw, 64px)", "clamp(11px, 1.3cqw, 19px)")
STANDBY_IMAGES = tuple("static/img/standby/studio-%d.webp" % n for n in (1, 2, 3, 4))
STANDBY_IMAGE_V = 1


def _standby_image(n):
    import os
    path = STANDBY_IMAGES[n] if n < len(STANDBY_IMAGES) else ""
    return "/%s?v=%d" % (path, STANDBY_IMAGE_V) if path and os.path.exists(path) else ""

# The reel a READING window shows while it has nothing to read
# (owner, 2026-09-22: no words in an empty window, icons).
STANDBY_FILL = STANDBY_REELS[0][2]


def _six(icons):
    """Six stops, always: the roll's keyframes step through six, and a
    five-icon reel ran its last stop into blank glass."""
    icons = list(icons or ())
    while icons and len(icons) < 6:
        icons.append(icons[len(icons) % len(icons)])
    return icons[:6]


def standby():
    """The unit with nothing measured: a sequence, a reel, a hint, a ticker."""
    key, name = STANDBY_CINE
    size, line = STANDBY_SIZE
    out = {
        "cine": {"box": box(key), "name": name, "size": size, "line": line},
        "frames": [{"n": i, "title": t, "line": l, "image": _standby_image(i)}
                   for i, (t, l) in enumerate(STANDBY_FRAMES)],
        "count": len(STANDBY_FRAMES),
        "reels": [{"box": box(k), "name": n, "icons": _six(icons), "n": i}
                  for i, (k, n, icons) in enumerate(STANDBY_REELS, start=1)],
        "tips": None, "ticker": None,
    }
    k, n, lines = STANDBY_TIPS
    out["tips"] = {"box": box(k), "name": n, "lines": lines, "count": len(lines),
                   "size": STANDBY_TIP_SIZE}
    k, n, lines = STANDBY_TICKER
    out["ticker"] = {"box": box(k), "name": n, "lines": lines, "size": STANDBY_TICK_SIZE}
    out["fill"] = _six(STANDBY_FILL)
    return out


def build(analysis, cover, art_files, tracks, masters, ready, cards,
          artist_name="", measured_label=None, sample=False, can_open=None):
    """Everything the screen renders. No page logic beyond this."""
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
        tiles.append({"key": key, "href": href, "icon": card[1],
                      "name": card[2], "line": card[3]})

    return {
        "artist_name": artist_name or "",
        "analyser": analyser(analysis, cover),
        # Nothing measured, nothing tracked, no art: the unit explains
        # itself. One track, one cover or one reading and this is gone.
        "idle": not analysis and not tracks and not art["total"],
        "standby": standby(),
        "covers": art,
        "path": path(tracks, measured_label, masters, art["total"], ready),
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }

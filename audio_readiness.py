"""What the measurements say about whether a record is ready to release.

The Rack already measures a master properly: integrated loudness to
ITU-R BS.1770-4, loudness range to EBU 3342, a true peak found by 4x
oversampling, tempo, and key. Those numbers lived and died in the browser
tab. Meanwhile Release Readiness was scored from campaign link setup,
ISRC presence and how many cover images existed - every input
administrative, none of them the record.

So an artist could score "Release Ready" on a master that clips on every
streaming platform, and nothing in the app would say a word.

This module is the missing arrow. It takes measurements the Rack really
made and turns them into rulings a person can act on. It invents nothing:
every ruling below is derived from a stored measurement, and when there
is no measurement the answer is "not measured yet" rather than a guess.

The thresholds are not opinions either:

  -1 dBTP is the mastering ceiling every major platform publishes, and
  the reason is mechanical - lossy encoders reconstruct a waveform that
  overshoots the samples they were given, so a file peaking at 0 dBFS
  clips after encoding even though the file itself never did.

  Platform targets come from loudness.js's TARGETS table, which is the
  same one the Rack shows.

  A loudness range under about 3 LU means the record is compressed flat
  enough that a listener hears no light and shade. Over about 15 LU on a
  modern release usually means an unmastered bounce.
"""

# The ceiling. Anything above this is at risk once a platform encodes it.
TRUE_PEAK_CEILING = -1.0

# Below this the file is almost certainly not a finished master.
TRUE_PEAK_SUSPICIOUS_LOW = -6.0

# Streaming normalisation targets, in LUFS. Same figures the Rack shows.
PLATFORM_TARGETS = (
    ("Spotify", -14.0),
    ("Apple Music", -16.0),
    ("YouTube", -14.0),
    ("Amazon Music", -14.0),
    ("Tidal", -14.0),
    ("Deezer", -15.0),
)

# Loudness range, in LU.
LRA_FLAT = 3.0
LRA_WIDE = 15.0

# Below this, a detected tempo is a suggestion rather than a fact.
BPM_TRUSTWORTHY = 0.5


def _ruling(key, level, headline, detail, evidence, action=None):
    """One finding. `level` is ok | watch | problem | unknown."""
    return {
        "key": key,
        "level": level,
        "headline": headline,
        "detail": detail,
        "evidence": evidence,
        "action": action,
    }


def true_peak_ruling(true_peak):
    """The one that actually costs people quality, and the one nobody sees
    coming - a peak meter reads the samples, and the damage happens
    between them."""
    if true_peak is None:
        return _ruling("true_peak", "unknown", "True peak not measured",
                       "Run the master through the Rack's loudness meter to "
                       "find out whether it survives encoding.", None,
                       "Open the Rack and load this master")
    if true_peak > TRUE_PEAK_CEILING:
        over = true_peak - TRUE_PEAK_CEILING
        return _ruling(
            "true_peak", "problem",
            "True peak is %.2f dBTP, above the -1 dBTP ceiling" % true_peak,
            "Every major platform re-encodes to a lossy format, and the "
            "decoded waveform overshoots the samples it was built from. At "
            "%.2f dBTP there is no room for that overshoot, so this will "
            "clip on playback even though the file itself does not. Pulling "
            "the master down %.2f dB fixes it and costs nothing - streaming "
            "normalisation turns everything down anyway."
            % (true_peak, over),
            "Measured true peak %.2f dBTP (4x oversampled), ceiling -1.0"
            % true_peak,
            "Lower the master by %.2f dB and re-measure" % over)
    if true_peak < TRUE_PEAK_SUSPICIOUS_LOW:
        return _ruling(
            "true_peak", "watch",
            "True peak is %.2f dBTP, unusually low for a finished master"
            % true_peak,
            "Nothing is wrong with the file, but a master this far below the "
            "ceiling is often a rough bounce rather than a final one. Worth "
            "checking this is the version you meant to release.",
            "Measured true peak %.2f dBTP" % true_peak, None)
    return _ruling(
        "true_peak", "ok", "True peak is safe at %.2f dBTP" % true_peak,
        "Sits under the -1 dBTP ceiling, so lossy encoding has room to "
        "overshoot without clipping.",
        "Measured true peak %.2f dBTP (4x oversampled)" % true_peak, None)


def loudness_ruling(integrated, true_peak=None):
    """Where this lands against what platforms normalise to."""
    if integrated is None:
        return _ruling("loudness", "unknown", "Loudness not measured",
                       "Nothing here can be said about how loud this will "
                       "sound next to other records.", None,
                       "Measure the master in the Rack")

    rows = []
    for name, target in PLATFORM_TARGETS:
        delta = integrated - target
        gain = -delta
        clips = (true_peak is not None and gain > 0
                 and (true_peak + gain) > TRUE_PEAK_CEILING)
        rows.append({"platform": name, "target": target,
                     "delta": round(delta, 1), "gain": round(gain, 1),
                     "turned_down": delta > 0.5, "clips_if_raised": clips})

    louder_than_all = all(r["turned_down"] for r in rows)
    if louder_than_all:
        worst = max(rows, key=lambda r: r["delta"])
        return _ruling(
            "loudness", "watch",
            "At %.1f LUFS this is louder than every platform's target"
            % integrated,
            "They will all turn it down - %s by %.1f dB - so the loudness "
            "you pushed for is not loudness anyone hears. What survives the "
            "turn-down is the dynamic range you spent to get there. This is "
            "not a fault, it is a choice worth making on purpose."
            % (worst["platform"], worst["delta"]),
            "Integrated %.1f LUFS against published platform targets"
            % integrated, None)

    below = [r for r in rows if r["gain"] > 2]
    headroom = [r for r in below if not r["clips_if_raised"]]

    if len(below) >= 3 and not headroom:
        # Quiet AND already near the ceiling. That combination is the
        # interesting one: it means the peaks are far above the average,
        # so the loudness cannot be raised without clipping. Usually a
        # stray transient, or a master that was never limited.
        return _ruling(
            "loudness", "problem",
            "Quiet at %.1f LUFS, yet there is no headroom to raise it"
            % integrated,
            "The average sits well below every platform target, but the "
            "peaks are already close to the ceiling - so turning it up to "
            "compete would clip. That gap between average and peak usually "
            "means one stray transient is holding the whole record down, or "
            "that it was never limited. Finding that peak is worth more "
            "than any amount of gain.",
            "Integrated %.1f LUFS with true peak %.2f dBTP: raising to the "
            "nearest target would breach the ceiling"
            % (integrated, true_peak if true_peak is not None else 0.0),
            "Find what is peaking and control it, then re-measure")

    if len(headroom) >= 3:
        return _ruling(
            "loudness", "watch",
            "At %.1f LUFS this is quieter than most platform targets"
            % integrated,
            "Platforms do not turn quiet material up, so next to louder "
            "records this will simply sound smaller. There is room to raise "
            "it without breaching the peak ceiling.",
            "Integrated %.1f LUFS; %d platforms target louder"
            % (integrated, len(headroom)),
            "Consider raising the master, or leave it if the quiet is intentional")

    return _ruling(
        "loudness", "ok", "Loudness sits in the normal band at %.1f LUFS"
        % integrated,
        "Close enough to the platform targets that normalisation will not "
        "move it much either way.",
        "Integrated %.1f LUFS" % integrated, None)


def range_ruling(lra):
    """Loudness range - how much light and shade survived the master."""
    if lra is None:
        return _ruling("range", "unknown", "Loudness range not measured",
                       "", None, None)
    if lra < LRA_FLAT:
        return _ruling(
            "range", "watch", "Loudness range is %.1f LU - very flat" % lra,
            "Under about 3 LU there is little difference between the "
            "quietest and loudest parts, so the record arrives at one level "
            "and stays there. That works for some material and flattens the "
            "life out of others.",
            "EBU 3342 loudness range %.1f LU" % lra, None)
    if lra > LRA_WIDE:
        return _ruling(
            "range", "watch", "Loudness range is %.1f LU - very wide" % lra,
            "Over about 15 LU usually means the material has not been "
            "mastered, or that a quiet passage is dragging the range out. "
            "Worth confirming this is the finished version.",
            "EBU 3342 loudness range %.1f LU" % lra, None)
    return _ruling("range", "ok", "Loudness range is %.1f LU" % lra,
                   "Normal dynamic spread for a finished master.",
                   "EBU 3342 loudness range %.1f LU" % lra, None)


def tempo_key_ruling(bpm, bpm_confidence, key, key_fit):
    """Tempo and key are useful for pitching and for metadata, but only
    when the detector was actually sure. A confident-sounding wrong BPM in
    a pitch document is worse than no BPM."""
    if bpm is None and key is None:
        return _ruling("tempo_key", "unknown", "Tempo and key not measured",
                       "", None, None)
    parts, trust = [], True
    if bpm is not None:
        if bpm_confidence is not None and bpm_confidence < BPM_TRUSTWORTHY:
            parts.append("tempo reads %.0f BPM but the detector was not "
                         "confident (%.2f)" % (bpm, bpm_confidence))
            trust = False
        else:
            parts.append("%.0f BPM" % bpm)
    if key:
        parts.append("key of %s%s" % (key, "" if key_fit is None
                                      else " (fit %.2f)" % key_fit))
    level = "ok" if trust else "watch"
    return _ruling(
        "tempo_key", level, "Measured " + " and ".join(parts),
        "Useful on a pitch or a sync submission - but only worth quoting "
        "where the detector was confident." if not trust else
        "Ready to carry into metadata and pitch documents.",
        " · ".join(parts),
        "Confirm the tempo by ear before quoting it" if not trust else None)


def assess(analysis):
    """All rulings for one measured track.

    `analysis` is whatever the Rack stored, or None/empty when the track
    has never been measured. The distinction matters: "not measured" is an
    honest state and gets said out loud rather than scored as a pass.
    """
    a = analysis or {}
    measured = bool(a.get("measured_at"))
    rulings = [
        true_peak_ruling(a.get("true_peak")),
        loudness_ruling(a.get("integrated"), a.get("true_peak")),
        range_ruling(a.get("lra")),
        tempo_key_ruling(a.get("bpm"), a.get("bpm_confidence"),
                         a.get("key"), a.get("key_fit")),
    ]
    problems = [r for r in rulings if r["level"] == "problem"]
    watch = [r for r in rulings if r["level"] == "watch"]
    unknown = [r for r in rulings if r["level"] == "unknown"]

    if not measured:
        verdict, summary = "unmeasured", (
            "This master has not been through the Rack, so nothing here "
            "knows how it will behave on a streaming platform.")
    elif problems:
        verdict, summary = "problem", problems[0]["headline"]
    elif watch:
        verdict, summary = "watch", watch[0]["headline"]
    else:
        verdict, summary = "ok", "Measured and clean: safe peak, sensible " \
                                 "loudness, normal dynamic range."

    return {
        "measured": measured,
        "measured_at": a.get("measured_at"),
        "verdict": verdict,
        "summary": summary,
        "rulings": rulings,
        "problem_count": len(problems),
        "watch_count": len(watch),
        "unknown_count": len(unknown),
    }


def readiness_points(analysis):
    """Audio's contribution to Release Readiness, as (points, max, note).

    Deliberately not generous. An unmeasured master scores zero rather
    than a default pass, because the whole point is that the score should
    mean the record was checked.
    """
    a = assess(analysis)
    if not a["measured"]:
        return 0, 25, ("Master not measured — the readiness score cannot "
                       "speak for the audio yet.")
    if a["verdict"] == "problem":
        return 5, 25, a["summary"]
    if a["verdict"] == "watch":
        return 18, 25, a["summary"]
    return 25, 25, a["summary"]

"""Street Banker Studio - the Control Room's view models.

THREE QUESTIONS, KEPT APART
---------------------------
The cockpit used to answer three different questions with one kind of
number. "Is the mix in good shape" is a measurement question; "is this
ready to master" is a mastering question over the same measurements; "can
this ship" is a workflow question about rights, versions and titles. When
a version's approval sat in the mix score, the mix looked worse every time
somebody forgot to click a button, and a bare stereo file wore a 100 for
"clipping" as if 100 meant something.

Here each question gets its own list, and every entry is a StudioMetric:

    key, label, state, value, note, source, tone

`state` is one of STATES - a word a person can read, never a number for a
yes/no test. `value` is the measured figure with its unit, or None. `note`
says what the value was judged against, or what was not measured and why.
`tone` is for the lamp: good / warn / crit / idle - and crit is reserved
for an actual over or a blocking finding, as the design rules require.

NOTHING HERE MEASURES ANYTHING
------------------------------
It reads what the browser measured (studio_measure), what the Rack's
rulings said (audio_readiness), what the findings table holds, and the
delivery checklist the store computed. When a thing was not measured, the
metric says so; it never fills the gap with a plausible figure.
"""

STATES = {
    "pass": "Pass", "clear": "Clear", "healthy": "Healthy", "in_range": "In range",
    "watch": "Watch", "review": "Review",
    "low_confidence": "Low confidence", "medium_confidence": "Medium confidence",
    "high_confidence": "High confidence",
    "not_measured": "Not measured", "not_available": "Not available",
    "needs_stems": "Needs stems", "needs_reference": "Needs reference",
    "simulation": "Simulation available",
}

_TONE = {
    "pass": "good", "clear": "good", "healthy": "good", "in_range": "good",
    "high_confidence": "good", "medium_confidence": "warn", "low_confidence": "warn",
    "watch": "warn", "review": "warn", "simulation": "info",
}

# The streaming band and the mastering ceiling, by convention. The same
# figures studio_score names; they are conventions, not laws, and the note
# on every metric says which one it was judged against.
STREAM_LO, STREAM_HI = -16.0, -13.0
CEILING_DBTP = -1.0


def metric(key, label, state, value=None, note="", source="measured", tone=None):
    if state not in STATES:
        raise ValueError("unknown metric state: %s" % state)
    return {"key": key, "label": label, "state": state,
            "state_label": STATES[state], "value": value, "note": note,
            "source": source, "tone": tone or _TONE.get(state, "idle")}


def _confidence_state(conf):
    if conf is None:
        return "low_confidence"
    if conf >= 0.8:
        return "high_confidence"
    if conf >= 0.5:
        return "medium_confidence"
    return "low_confidence"


# --- the shared audio metrics ------------------------------------------------

def headroom(m):
    tp = m.get("true_peak")
    if tp is None:
        return metric("headroom", "Headroom", "not_measured",
                      note="True peak has not been measured.", source="unmeasured")
    value = "%.1f dBTP" % tp
    if tp <= CEILING_DBTP:
        return metric("headroom", "Headroom", "pass", value,
                      "%.1f dB under the -1 dBTP mastering ceiling." % (CEILING_DBTP - tp))
    if tp <= 0.0:
        return metric("headroom", "Headroom", "watch", value,
                      "Above the -1 dBTP ceiling; lossy encodes will overshoot.")
    return metric("headroom", "Headroom", "review", value,
                  "Over full scale. Bring the peak down before mastering.", tone="crit")


def clipping(m):
    peak = m.get("true_peak") if m.get("true_peak") is not None else m.get("sample_peak")
    if peak is None:
        return metric("clipping", "Clipping", "not_measured",
                      note="No peak has been measured.", source="unmeasured")
    value = "%.2f dB peak" % peak
    if peak < -0.3:
        return metric("clipping", "Clipping", "clear", value, "No overs.")
    if peak < 0.0:
        return metric("clipping", "Clipping", "watch", value,
                      "Inter-sample overs are likely on a lossy encode.")
    return metric("clipping", "Clipping", "review", value,
                  "At or over full scale.", tone="crit")


def loudness(m):
    integrated = m.get("integrated")
    if integrated is None:
        return metric("loudness", "Loudness", "not_measured",
                      note="Integrated loudness has not been measured.", source="unmeasured")
    value = "%.1f LUFS" % integrated
    if STREAM_LO <= integrated <= STREAM_HI:
        return metric("loudness", "Loudness", "in_range", value,
                      "Inside the -16 to -13 LUFS streaming band.")
    if integrated > STREAM_HI:
        return metric("loudness", "Loudness", "watch", value,
                      "%.1f LU above the streaming band; platforms turn it down."
                      % (integrated - STREAM_HI))
    return metric("loudness", "Loudness", "watch", value,
                  "%.1f LU under the streaming band; platforms turn it up, noise and all."
                  % (STREAM_LO - integrated))


def dynamics(m):
    lra = m.get("lra")
    if lra is None:
        return metric("dynamics", "Dynamics", "not_measured",
                      note="Loudness range needs a longer file than this one gave the meter.",
                      source="unmeasured")
    value = "%.1f LU range" % lra
    if 4.0 <= lra <= 10.0:
        return metric("dynamics", "Dynamics", "healthy", value,
                      "Inside the 4 to 10 LU working band.")
    if lra < 4.0:
        return metric("dynamics", "Dynamics", "watch", value, "Reads compressed.")
    return metric("dynamics", "Dynamics", "watch", value, "Reads unmastered.")


def tempo(m):
    bpm, conf = m.get("bpm"), m.get("bpm_confidence")
    if bpm is None:
        return metric("tempo", "Tempo", "not_measured",
                      note="No stable tempo the detector could lock to.", source="unmeasured")
    if conf is not None and conf < 0.3:
        return metric("tempo", "Tempo", "not_measured",
                      note="Not confident enough to report.", source="unmeasured")
    return metric("tempo", "Tempo", _confidence_state(conf), "%.0f BPM" % bpm,
                  "Detected in the browser; confidence %.0f%%." % ((conf or 0) * 100))


def key(m):
    k, fit = m.get("key"), m.get("key_fit")
    if not k:
        return metric("key", "Key", "not_measured",
                      note="No key was detected.", source="unmeasured")
    if fit is not None and fit < 0.3:
        return metric("key", "Key", "not_measured",
                      note="Not confident enough to report.", source="unmeasured")
    return metric("key", "Key", _confidence_state(fit), str(k),
                  "Detected in the browser; fit %.0f%%." % ((fit or 0) * 100))


def mix_metrics(measurements):
    m = measurements or {}
    return [
        headroom(m), clipping(m), loudness(m), dynamics(m), tempo(m), key(m),
        metric("stereo", "Stereo image", "not_measured",
               note="A correlation measurement is not built yet.", source="unmeasured"),
        metric("vocal", "Vocal balance", "needs_stems",
               note="A stereo file cannot say how the vocal sits.", source="unmeasurable"),
        metric("lowend", "Low-end control", "needs_reference",
               note="Needs stems or a reference to compare against.", source="unmeasurable"),
    ]


def master_metrics(measurements):
    m = measurements or {}
    return [
        headroom(m), clipping(m), loudness(m), dynamics(m),
        metric("tonal", "Tonal balance", "not_measured",
               note="A spectral measurement is not built yet.", source="unmeasured"),
        metric("translation", "Playback translation", "simulation",
               note="Listening tools, not measurements. Your ears are the meter.",
               source="simulation"),
    ]


def measured_count(metrics):
    return sum(1 for x in metrics if x["source"] == "measured")


# The four tests that are about the audio. Tempo/key confidence and version
# completeness are real facts, but they are not how the mix sounds, so they
# never move this number.
AUDIO_CATEGORIES = ("headroom", "clipping", "loudness", "dynamics")


_PASSING = ("pass", "clear", "healthy", "in_range")


def mix_score(metrics):
    """The section-level summary for Mix readiness, in words.

    Counts the four audio tests by state. A number here would read as a
    grade of the mix - "100" on a set of pass/fail tests says "perfect",
    which nothing measured. "All 4 audio tests pass" says what happened.
    `summary` is None until something has been measured.
    """
    rows = [x for x in metrics or [] if x["key"] in AUDIO_CATEGORIES]
    passed = sum(1 for x in rows if x["state"] in _PASSING)
    watch = sum(1 for x in rows if x["state"] == "watch")
    review = sum(1 for x in rows if x["state"] == "review")
    measured = sum(1 for x in rows if x["source"] == "measured")
    total = len(AUDIO_CATEGORIES)
    if not measured:
        summary = None
    elif watch or review:
        summary = "%d of %d pass" % (passed, measured)
        if watch:
            summary += " · %d watch" % watch
        if review:
            summary += " · %d review" % review
    elif measured == total:
        summary = "All %d audio tests pass" % total
    else:
        summary = "%d of %d measured, all pass" % (measured, total)
    return {"pass": passed, "watch": watch, "review": review,
            "measured": measured, "total": total, "summary": summary,
            "tone": "crit" if review else ("warn" if watch else "good")}


# What a person needs to know about this workspace, in their words. The
# engineering rows stay underneath for whoever runs the deployment.
_SYSTEM_WORDS = {
    "processing": "Master rendering is not enabled on this workspace yet. "
                  "Analysis, preview and version tracking all work.",
    "worker": "Long processing jobs are queued here and reported queued, "
              "never reported finished early.",
    "storage": "Object storage is not connected, so upload size is limited "
               "until it is.",
    "analysis": "Audio measurement is unavailable in this workspace.",
}


def system_notes(readiness):
    """Plain sentences for every component that is off. Empty when all is on."""
    return [_SYSTEM_WORDS[key] for key, ok, _h, _d in (readiness or [])
            if not ok and key in _SYSTEM_WORDS]


# --- delivery ----------------------------------------------------------------

# The first failing REQUIRED line decides the one button. key -> (label, room)
_CTA = {
    "source": ("Upload the source", "session"),
    "rights": ("Confirm rights", "session"),
    "measured": ("Measure the audio", "measure"),
    "blocking": ("Resolve the blocking finding", "mix"),
    "locked": ("Lock final version", "versions"),
    "title": ("Add project title", "session"),
}


def delivery(checklist):
    """{required_met, required_total, met, total, ready, cta: {label, room}}."""
    rows = checklist or []
    required = [c for c in rows if c.get("required")]
    required_met = [c for c in required if c.get("ok")]
    first_gap = next((c for c in required if not c.get("ok")), None)
    if first_gap is None:
        cta = {"label": "Prepare delivery", "room": "deliver", "key": "ready"}
    else:
        label, room = _CTA.get(first_gap["key"], ("Meet the checklist", "deliver"))
        cta = {"label": label, "room": room, "key": first_gap["key"]}
    return {
        "required_met": len(required_met), "required_total": len(required),
        "met": sum(1 for c in rows if c.get("ok")), "total": len(rows),
        "ready": first_gap is None and bool(required),
        "cta": cta,
    }


# --- the Mix Doctor ----------------------------------------------------------

_SEVERITY_RANK = {"blocking": 0, "review": 1, "informational": 2}


def mix_doctor(findings, rulings, metrics):
    """One observation, the highest-priority one, with its provenance.

    Order of authority: an open finding on the recording (it has a time and
    evidence), then a platform ruling that said watch or problem, then the
    first metric that reads watch or review. When nothing was flagged the
    Doctor says so and names what it could not measure - it has no ears and
    says so.
    """
    open_findings = sorted([f for f in findings or [] if f.get("status") == "open"],
                           key=lambda f: _SEVERITY_RANK.get(f.get("severity"), 3))
    if open_findings:
        f = open_findings[0]
        missing = f.get("missing_inputs")
        if isinstance(missing, str):
            missing = [x for x in missing.strip("[]").replace('"', "").split(",") if x.strip()]
        label = (f.get("category") or "finding").replace("_", " ").capitalize()
        text = (f.get("explanation") or "").strip()
        # The explanation opens with the ruling's one-line observation. That
        # line is the headline; what follows is the body. A long single
        # sentence keeps the category as its headline instead.
        head, sep, rest = text.partition(". ")
        if sep and len(head) <= 110:
            headline, body = head, rest
        else:
            headline, body = label, text
        return {
            "kind": "finding", "severity": f.get("severity") or "review",
            "label": label,
            "headline": headline,
            "body": body,
            "confidence": f.get("confidence") or "moderate",
            "source": f.get("evidence_source") or "measured",
            "at": f.get("start_seconds"),
            "measured": f.get("measured_evidence") or {},
            "missing": missing or [],
            "test": f.get("recommendation") or "",
            "blocking": f.get("severity") == "blocking",
        }
    flagged = [r for r in rulings or [] if r.get("level") in ("problem", "watch")]
    if flagged:
        r = flagged[0]
        return {
            "kind": "ruling", "severity": "review" if r.get("level") == "problem" else "watch",
            "headline": r.get("headline") or "Worth a look",
            "body": r.get("detail") or r.get("summary") or "",
            "confidence": "strong", "source": "measured", "at": None,
            "measured": {"evidence": r.get("evidence")} if r.get("evidence") else {},
            "missing": [], "test": r.get("action") or "", "blocking": r.get("level") == "problem",
        }
    watched = [x for x in metrics or [] if x["state"] in ("watch", "review")]
    if watched:
        x = watched[0]
        return {
            "kind": "metric", "severity": x["state"],
            "headline": "%s: %s" % (x["label"], x["state_label"].lower()),
            "body": x["note"], "confidence": "strong", "source": x["source"], "at": None,
            "measured": {x["label"]: x["value"]}, "missing": [], "test": "",
            "blocking": x["tone"] == "crit",
        }
    measured = measured_count(metrics or [])
    unmeasured = [x["label"] for x in metrics or [] if x["source"] != "measured"]
    if not measured:
        return {"kind": "unmeasured", "severity": "none",
                "headline": "Nothing has been measured yet",
                "body": "Run the measurement and the Doctor has something to read.",
                "confidence": "limited", "source": "unmeasured", "at": None,
                "measured": {}, "missing": unmeasured, "test": "", "blocking": False}
    return {"kind": "clear", "severity": "none",
            "headline": "Nothing flagged from what was measured",
            "body": "The measured figures sit inside their conventions.",
            "confidence": "strong", "source": "measured", "at": None,
            "measured": {}, "missing": unmeasured, "test": "", "blocking": False}


# --- the lifecycle, with the conditions behind each stage --------------------

def lifecycle_detail(stages, project, summary, checklist):
    """Each stage from studio_score.lifecycle(), plus the conditions that
    make it and the next thing to do. Computed, never ticked."""
    versions = (summary or {}).get("versions") or []
    source = (summary or {}).get("source")
    approved = any(v.get("status") in ("approved", "locked") for v in versions)
    locked = any(v.get("status") == "locked" for v in versions)
    rights = bool((project or {}).get("rights_confirmed_at"))
    required = [c for c in checklist or [] if c.get("required")]
    released = bool(((project or {}).get("release_id") or "").strip())
    conditions = {
        "create": [("Project exists", True)],
        "finish": [("Source uploaded", bool(source))],
        "approve": [("Source uploaded", bool(source)), ("A version approved", approved)],
        "protect": [("Rights confirmed", rights), ("Final version locked", locked)],
        "deliver": [(c["label"], bool(c["ok"])) for c in required],
        "release": [("Linked to a release", released)],
        "market": [("Rollout Engine connection", False)],
        "monetize": [("Royalty Sweep connection", False)],
    }
    nexts = {
        "finish": "Upload the record.",
        "approve": "Approve the version that is ready, in Versions.",
        "protect": "Confirm the rights, then lock the version that ships." if not rights
                   else "Lock the version that ships.",
        "deliver": "Meet the delivery checklist.",
        "release": "Link this project to a release.",
        "market": "Not connected yet.",
        "monetize": "Not connected yet.",
    }
    out = []
    for s in stages or []:
        entry = dict(s)
        entry["conditions"] = conditions.get(s["key"], [])
        entry["next"] = "" if s.get("state") == "done" else nexts.get(s["key"], "")
        out.append(entry)
    return out


# --- team and activity -------------------------------------------------------

def team_state(member):
    """active | invite_pending | credit. Access is a fact of the team seat,
    never of the name on the card."""
    if member.get("team_status") == "active" and member.get("team_user_id"):
        return "active"
    if member.get("team_member_id"):
        return "invite_pending"
    return "credit"


def collapse_activity(events):
    """Consecutive events of one type fold into a row with a count. The rows
    underneath are untouched; this is presentation, not deletion."""
    out = []
    for e in events or []:
        if out and out[-1]["event_type"] == e.get("event_type"):
            out[-1]["count"] += 1
            continue
        out.append({"event_type": e.get("event_type") or "", "created_at": e.get("created_at") or "",
                    "count": 1})
    return out

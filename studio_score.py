"""Street Banker Studio - readiness scoring.

The mockup shows Mix Readiness 78/100 with eight subscores. The rule this
module exists to enforce is that every one of those numbers must be traceable:
a score is computed from a MEASURED property against a NAMED engineering
convention, or it is not shown at all.

A stereo master cannot tell you how the vocal sits or whether the low end is
controlled - those need stems or a reference, and this module says so in a
`missing` field instead of inventing a plausible-looking 72. The mockup's
"Vocal Translation 82" on a bare stereo file is exactly the fabrication rule
12 forbids, so here it renders as "needs stems", which is the truth.

Conventions used (each one named on the category it scores):
  - Mastering ceilings sit at -1 dBTP because 4x oversampled true peak
    under-reads by up to ~0.7 dB.
  - Streaming platforms normalise to roughly -16..-14 LUFS; sitting far above
    buys nothing and costs dynamics.
  - An LRA between about 4 and 10 LU is the working band for a modern master;
    under 3 reads as crushed, over 12 as unmastered.
These are conventions, not laws, and every score says which kind it is.
"""

# Status bands, chosen so the words match what a score means in practice.
def _status(score):
    if score >= 85:
        return "good"
    if score >= 70:
        return "almost"
    if score >= 40:
        return "attention"
    return "blocked"


def _cat(key, label, score, evidence, source, confidence, missing=None,
         action=None):
    return {
        "key": key,
        "label": label,
        "score": None if score is None else int(round(score)),
        "status": "unknown" if score is None else _status(score),
        "evidence": evidence,
        "source": source,            # measured | convention | unmeasurable
        "confidence": confidence,    # strong | moderate | limited
        "missing": missing,
        "action": action,
    }


def _clamp(value, lo=0.0, hi=100.0):
    return max(lo, min(hi, value))


def _headroom(m):
    tp = m.get("true_peak")
    if tp is None:
        return _cat("headroom", "Headroom", None, "True peak was not measured.",
                    "unmeasurable", "limited", missing="a measurement run")
    if tp <= -1.0:
        score = 100.0
    elif tp <= 0.0:
        score = _clamp(60.0 * (-tp))     # -1.0 -> 60, 0.0 -> 0... scaled below
        score = _clamp(40.0 + 60.0 * (-tp))
    else:
        score = 5.0
    return _cat("headroom", "Headroom", score,
                "True peak %.2f dBTP against the -1 dBTP convention ceiling."
                % tp,
                "measured", "strong",
                action=None if tp <= -1.0 else
                "Bring the true peak under -1 dBTP before mastering.")


def _clipping(m):
    sp = m.get("sample_peak")
    tp = m.get("true_peak")
    peak = tp if tp is not None else sp
    if peak is None:
        return _cat("clipping", "Clipping", None, "No peak was measured.",
                    "unmeasurable", "limited", missing="a measurement run")
    if peak < -0.3:
        score, note = 100.0, "No clipping: peak %.2f dB." % peak
    elif peak < 0.0:
        score, note = 70.0, ("Peak %.2f dB - inter-sample overs are likely "
                             "on lossy encode." % peak)
    else:
        score, note = 10.0, "Peak at or over full scale (%.2f dB)." % peak
    return _cat("clipping", "Clipping", score, note, "measured", "strong")


def _loudness(m):
    integrated = m.get("integrated")
    if integrated is None:
        return _cat("loudness", "Loudness position", None,
                    "Integrated loudness was not measured.",
                    "unmeasurable", "limited", missing="a measurement run")
    # Distance from the -16..-14 LUFS streaming band, by convention.
    if -16.0 <= integrated <= -13.0:
        score = 100.0
    else:
        distance = min(abs(integrated - -16.0), abs(integrated - -13.0))
        score = _clamp(100.0 - distance * 12.0)
    return _cat("loudness", "Loudness position", score,
                "Integrated %.1f LUFS against the -16..-14 streaming band."
                % integrated,
                "measured", "strong",
                action=None if score >= 70 else
                "Platforms will normalise this; the level buys nothing.")


def _dynamics(m):
    lra = m.get("lra")
    if lra is None:
        return _cat("dynamics", "Dynamics", None,
                    "Loudness range was not measured (the file may be too "
                    "short for EBU 3342 gating).",
                    "unmeasurable", "limited",
                    missing="a longer measurement or a full-length file")
    if 4.0 <= lra <= 10.0:
        score = 100.0
    elif lra < 4.0:
        score = _clamp(30.0 + lra / 4.0 * 70.0)
    else:
        score = _clamp(100.0 - (lra - 10.0) * 8.0)
    return _cat("dynamics", "Dynamics", score,
                "%.1f LU range against the 4-10 LU working band." % lra,
                "measured", "moderate")


def _tempo_key(m):
    bpm = m.get("bpm")
    conf = m.get("bpm_confidence")
    if bpm is None:
        return _cat("groove", "Tempo & key detection", None,
                    "No stable tempo was measurable in this recording.",
                    "unmeasurable", "limited",
                    missing="transient material the detector can lock to")
    score = _clamp((conf or 0.0) * 100.0)
    key = m.get("key")
    return _cat("groove", "Tempo & key detection", score,
                "%.1f BPM at %.2f confidence%s." % (
                    bpm, conf or 0.0,
                    (", key %s" % key) if key else ""),
                "measured", "strong" if (conf or 0) >= 0.7 else "moderate")


def _unmeasurable(key, label, needs):
    """The honest card for what a stereo file cannot tell you."""
    return _cat(key, label, None,
                "Cannot be judged from a stereo master alone.",
                "unmeasurable", "limited", missing=needs)


def mix_readiness(measurements, versions=None):
    """The Mix Station's category board.

    Returns {overall, measured_count, categories}. `overall` averages ONLY
    the measured categories and says how many that was - a single confident
    number over invisible gaps is how scores turn into lies.
    """
    m = measurements or {}
    categories = [
        _headroom(m),
        _clipping(m),
        _loudness(m),
        _dynamics(m),
        _tempo_key(m),
        _unmeasurable("vocal", "Vocal translation",
                      "stems, or a vocal + instrumental session"),
        _unmeasurable("lowend", "Low-end control",
                      "stems, or a reference comparison"),
        _unmeasurable("stereo", "Stereo image",
                      "a correlation measurement - not built yet"),
    ]
    versions = versions or []
    approved = any(v.get("status") in ("approved", "locked") for v in versions)
    categories.append(_cat(
        "versions", "Version completeness",
        100.0 if approved else 40.0 if versions else 0.0,
        "%d version%s, %s" % (len(versions), "" if len(versions) == 1 else "s",
                              "one approved" if approved else "none approved"),
        "measured", "strong",
        action=None if approved else "Approve the version that is ready."))

    scored = [c for c in categories if c["score"] is not None]
    overall = (int(round(sum(c["score"] for c in scored) / len(scored)))
               if scored else None)
    return {
        "overall": overall,
        "measured_count": len(scored),
        "total_count": len(categories),
        "categories": categories,
    }


def master_intelligence(measurements):
    """The Master Station's board - same rules, mastering framing."""
    m = measurements or {}
    categories = [
        _headroom(m),
        _clipping(m),
        _loudness(m),
        _dynamics(m),
        _unmeasurable("tonal", "Tonal balance",
                      "a spectral measurement - not built yet"),
        _unmeasurable("translation", "Playback translation",
                      "your ears, on the simulation chips below"),
    ]
    scored = [c for c in categories if c["score"] is not None]
    overall = (int(round(sum(c["score"] for c in scored) / len(scored)))
               if scored else None)
    return {
        "overall": overall,
        "measured_count": len(scored),
        "total_count": len(categories),
        "categories": categories,
    }


# --- the lifecycle rail ------------------------------------------------------

def lifecycle(project, summary, checklist):
    """CREATE -> FINISH -> APPROVE -> PROTECT -> DELIVER -> RELEASE -> MARKET
    -> MONETIZE, computed from real project state.

    Each stage: {key, label, state: done|current|blocked|future, why}. The
    rail is a report, not a decoration - a stage only reads done because the
    thing it names actually happened, and a blocked stage says what blocks it.
    """
    versions = summary.get("versions") or []
    source = summary.get("source")
    approved = any(v.get("status") in ("approved", "locked") for v in versions)
    locked = any(v.get("status") == "locked" for v in versions)
    rights = bool(project.get("rights_confirmed_at"))
    required_met = all(c["ok"] for c in checklist if c["required"]) \
        if checklist else False
    released = bool((project.get("release_id") or "").strip())

    stages = []

    def stage(key, label, done, why_blocked=None):
        stages.append({"key": key, "label": label,
                       "done": bool(done), "why": why_blocked})

    stage("create", "Create", True)                       # the project exists
    stage("finish", "Finish", bool(source),
          None if source else "Upload the record.")
    stage("approve", "Approve", approved,
          None if approved else "Approve a version in the Vault.")
    stage("protect", "Protect", rights and locked,
          None if (rights and locked) else
          ("Confirm the rights." if not rights else
           "Lock the version that ships - the lock is what makes the "
           "checksum mean something."))
    stage("deliver", "Deliver", required_met,
          None if required_met else "Meet the delivery checklist.")
    stage("release", "Release", released,
          None if released else "Link this project to a release.")
    stage("market", "Market", False,
          "Not connected to the Rollout Engine yet - honestly future.")
    stage("monetize", "Monetize", False,
          "Not connected to Royalty Sweep yet - honestly future.")

    current_set = False
    for entry in stages:
        if entry["done"]:
            entry["state"] = "done"
        elif not current_set:
            entry["state"] = "current"
            current_set = True
        else:
            entry["state"] = "blocked" if entry["why"] else "future"
    return stages

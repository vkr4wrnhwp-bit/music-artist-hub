"""Ask the Room - the project-aware answerer.

WHAT THIS IS, AND IS NOT
------------------------
The spec asks for "an experienced producer, mix engineer, A&R executive and
release operator sitting in the control room". What sits here is the part of
that person this deployment can honestly provide: someone who has READ the
whole project - every measurement, finding, note, version, checklist line and
lifecycle stage - and answers from that, with the evidence attached.

It is deterministic, not a language model. There is no LLM configured on this
deployment, and wiring one in without grounding would manufacture exactly the
confident-sounding fabrication the spec forbids. A rule-based answerer over
real state can never claim to have heard something no analysis measured -
which is the property that matters most in this seat.

EVERY ANSWER IS THE SAME SHAPE
------------------------------
observation / why / confidence / missing / action / links - the structure the
spec requires. Questions about things a stereo master cannot reveal (how the
vocal sits, whether the low end is controlled) get a LIMITED-confidence answer
that says what input would change that, instead of a guess.

The one hard rule, tested: no answer ever says "I heard" or "I listened".
Nothing here has ears. It has measurements, and it says so.
"""


def _answer(observation, why, confidence, missing=None, action=None,
            links=None, topic="general"):
    return {
        "topic": topic,
        "observation": observation,
        "why": why,
        "confidence": confidence,        # strong | moderate | limited
        "missing": missing,
        "action": action,
        "links": links or [],
    }


def _fmt_time(seconds):
    if seconds is None:
        return "?"
    return "%d:%02d" % (int(seconds // 60), int(seconds % 60))


# Each intent: (topic, matcher keywords, handler). First match wins; matchers
# are deliberately generous because artists do not type like search engines.
def _intents():
    return [
        ("blocking", ("blocking", "block", "release ready", "ready for release",
                      "ship", "what's stopping", "whats stopping",
                      "stopping the release", "can i release"), _blocking),
        ("next", ("what next", "next step", "what should", "where do i start",
                  "what now", "priority", "first"), _next),
        ("loudness", ("loud", "lufs", "quiet", "level", "volume",
                      "compressed", "compression", "crushed", "dynamics",
                      "smashed"), _loudness),
        ("peak", ("clip", "peak", "distort", "over"), _peak),
        ("vocal", ("vocal", "voice", "singer", "phone", "disappear",
                   "buried"), _vocal),
        ("lowend", ("low end", "low-end", "bass", "sub", "kick"), _lowend),
        ("chorus", ("chorus", "smaller", "bigger", "lift", "drop hits"),
         _chorus),
        ("versions", ("changed between", "difference between", "mix 3",
                      "compare", "version", "what changed"), _versions),
        ("notes", ("notes", "unresolved", "comments", "feedback",
                   "what did", "asked to change"), _notes),
        ("engineer", ("send the engineer", "send my engineer", "handoff",
                      "hand off", "engineer"), _engineer),
        ("tempo", ("bpm", "tempo", "key", "what key"), _tempo),
    ]


def ask(question, ctx):
    """Answer one question from project state.

    ctx carries: measurements, findings, comments, versions, checklist, rail,
    masters, project. All optional; every handler copes with absence, because
    "nothing is measured yet" is a real and common project state.
    """
    q = (question or "").strip().lower()
    if not q:
        return _fallback(ctx)
    for topic, keys, handler in _intents():
        if any(k in q for k in keys):
            return handler(ctx)
    return _fallback(ctx)


# --- handlers ----------------------------------------------------------------

def _blocking(ctx):
    checklist = ctx.get("checklist") or []
    missing = [c for c in checklist if c["required"] and not c["ok"]]
    if not missing:
        return _answer(
            "Every required delivery check is met.",
            "The checklist is computed from the project - source, rights, "
            "measurement, blocking findings, a locked version - not ticked "
            "by hand.",
            "strong", action="Build the delivery package on the Deliver page.",
            links=[("Deliver", "deliver")], topic="blocking")
    lines = "; ".join("%s (%s)" % (c["label"].lower(), c["detail"])
                      for c in missing[:3])
    return _answer(
        "%d required check%s not met: %s." % (
            len(missing), "" if len(missing) == 1 else "s are", lines),
        "The delivery package refuses to build until these are met, because "
        "a package that can ship before the version is locked can ship the "
        "wrong file.",
        "strong", action="Start with: %s." % missing[0]["label"].lower(),
        links=[("Deliver", "deliver")], topic="blocking")


def _next(ctx):
    findings = [f for f in (ctx.get("findings") or [])
                if f.get("status") == "open"]
    blocking = [f for f in findings if f.get("severity") == "blocking"]
    if blocking:
        f = blocking[0]
        return _answer(
            "The most urgent measured problem is %s%s." % (
                f["category"].replace("_", " "),
                (" at %s" % _fmt_time(f.get("start_seconds")))
                if f.get("start_seconds") is not None else ""),
            f.get("explanation") or "It was flagged blocking by the analyser.",
            "strong",
            action=f.get("recommendation") or "Open the Mix room and hear it.",
            links=[("Mix room", "mix")], topic="next")
    rail = ctx.get("rail") or []
    current = next((s for s in rail if s.get("state") == "current"), None)
    if current:
        return _answer(
            "The project is at the %s stage." % current["label"].upper(),
            current.get("why") or "That is the next thing the lifecycle "
            "rail is waiting on.",
            "strong", action=current.get("why"), topic="next")
    return _fallback(ctx)


def _loudness(ctx):
    m = ctx.get("measurements") or {}
    integrated, lra = m.get("integrated"), m.get("lra")
    if integrated is None:
        return _answer(
            "Loudness has not been measured yet.",
            "Nothing here guesses at a number the analyser has not produced.",
            "limited", missing="a measurement run on the Mix or Master page",
            action="Press Measure on the session console.", topic="loudness")
    parts = ["Integrated loudness is %.1f LUFS" % integrated]
    if lra is not None:
        parts.append("loudness range %.1f LU" % lra)
    observation = ", ".join(parts) + "."
    if lra is not None and lra < 4.0 and integrated > -10.0:
        return _answer(
            observation,
            "Hot AND narrow is the signature of over-compression: platforms "
            "will turn the level down (that part is lossless) but the lost "
            "dynamics do not come back.",
            "moderate",
            action="Ease the limiting and re-measure - the platform table on "
                   "the Master page shows what each service would do.",
            links=[("Master room", "master")], topic="loudness")
    return _answer(
        observation,
        "Streaming platforms normalise to roughly -16 to -14 LUFS; distance "
        "from that band buys nothing and costs headroom.",
        "strong", links=[("Master room", "master")], topic="loudness")


def _peak(ctx):
    m = ctx.get("measurements") or {}
    tp = m.get("true_peak")
    if tp is None:
        return _answer(
            "True peak has not been measured yet.",
            "Clipping is a measurement, not an impression.",
            "limited", missing="a measurement run",
            action="Press Measure on the session console.", topic="peak")
    if tp > -1.0:
        return _answer(
            "True peak is %.2f dBTP - over the -1 dBTP convention ceiling." % tp,
            "4x oversampled true peak under-reads by up to about 0.7 dB, "
            "which is why mastering ceilings sit at -1 rather than 0; lossy "
            "encoders push inter-sample peaks higher still.",
            "strong",
            action="Bring the ceiling down before rendering - the Clean "
                   "render caps this automatically.",
            links=[("Master room", "master")], topic="peak")
    return _answer(
        "True peak is %.2f dBTP - under the ceiling with margin." % tp,
        "Nothing here will clip on encode.", "strong", topic="peak")


def _vocal(ctx):
    comments = [c for c in (ctx.get("comments") or [])
                if c.get("status") == "open"
                and "vocal" in (c.get("body") or "").lower()]
    note = ""
    if comments:
        note = (" There is an open note that may be about this: \"%s\" at %s."
                % (comments[0]["body"][:80],
                   _fmt_time(comments[0].get("start_seconds"))))
    return _answer(
        "How the vocal sits cannot be measured from a stereo master - there "
        "is no separated vocal to measure.%s" % note,
        "Any number offered here would be invented, and this room does not "
        "do that.",
        "limited",
        missing="stems, or a vocal + instrumental session",
        action="Use the Phone and Low volume chips on the playback "
               "translation rail - if the vocal vanishes there, your ears "
               "have the finding a stereo file cannot give the analyser.",
        topic="vocal")


def _lowend(ctx):
    m = ctx.get("measurements") or {}
    extra = ""
    if m.get("loudest_at") is not None:
        extra = (" The loudest three-second window sits at %s, which is "
                 "where low-end problems usually live if they exist."
                 % _fmt_time(m["loudest_at"]))
    return _answer(
        "Low-end control cannot be judged from a stereo master alone - the "
        "kick and the bass are one signal here.%s" % extra,
        "Separating them takes stems or a spectral comparison, and neither "
        "is on this deployment yet.",
        "limited", missing="stems, or a reference comparison",
        action="A/B against a rendered master with match ticked, on the Car "
               "and Club chips - the low shelf those add makes collisions "
               "easier to hear.",
        topic="lowend")


def _chorus(ctx):
    m = ctx.get("measurements") or {}
    if m.get("loudest_at") is None:
        return _answer(
            "Section energy has not been measured yet.",
            "The short-term loudness series is what locates the biggest "
            "moment, and it comes from the measurement run.",
            "limited", missing="a measurement run",
            action="Press Measure, then ask again.", topic="chorus")
    return _answer(
        "The loudest sustained moment of this file is at %s."
        % _fmt_time(m["loudest_at"]),
        "If that is not where your chorus is, the arrangement is not "
        "delivering the lift where you intend it - the biggest measured "
        "moment and the intended biggest moment should coincide.",
        "moderate",
        missing="section boundaries (not detected on this deployment), so "
                "this uses the loudness series only",
        action="Press Hear it on the loudness marker and listen either side "
               "of it.",
        links=[("Mix room", "mix")], topic="chorus")


def _versions(ctx):
    versions = ctx.get("versions") or []
    if len(versions) < 2:
        return _answer(
            "There is only %s version, so there is nothing to compare."
            % ("one" if versions else "no"),
            "Comparison needs two.", "strong",
            action="Render a master or upload a revision first.",
            topic="versions")
    a, b = versions[1], versions[0]     # newest first in the store
    return _answer(
        "Between %s and %s: %s." % (
            a["version_name"], b["version_name"],
            b.get("change_summary") or "no change summary was recorded"),
        "This is the RECORDED difference - what the render or upload wrote "
        "down when it happened. A measured waveform-level diff between two "
        "versions is not built on this deployment yet, and this room does "
        "not fake one.",
        "moderate",
        missing="a measured version diff (planned, not built)",
        action="Put %s on the transport's B slot and flip with match ticked "
               "- your ears do the diff at equal loudness." % b["version_name"],
        links=[("Versions", "versions")], topic="versions")


def _notes(ctx):
    open_notes = [c for c in (ctx.get("comments") or [])
                  if c.get("status") == "open"]
    if not open_notes:
        return _answer(
            "No notes are open on this recording.",
            "Every note is pinned to the exact file it was written against, "
            "so a resolved list means resolved on THIS audio.",
            "strong", topic="notes")
    lines = "; ".join("%s - \"%s\"" % (_fmt_time(c.get("start_seconds")),
                                       c["body"][:60])
                      for c in open_notes[:4])
    return _answer(
        "%d note%s open: %s." % (len(open_notes),
                                 "" if len(open_notes) == 1 else "s", lines),
        "These are the asks collaborators have pinned to moments of this "
        "file.",
        "strong",
        action="Each timestamp seeks the transport - work top to bottom.",
        links=[("Mix room", "mix")], topic="notes")


def _engineer(ctx):
    findings = [f for f in (ctx.get("findings") or [])
                if f.get("status") == "open"]
    open_notes = [c for c in (ctx.get("comments") or [])
                  if c.get("status") == "open"]
    m = ctx.get("measurements") or {}
    pieces = []
    if m.get("integrated") is not None:
        pieces.append("the measurements (%.1f LUFS, %.2f dBTP, %s LU)"
                      % (m["integrated"], m.get("true_peak") or 0,
                         ("%.1f" % m["lra"]) if m.get("lra") is not None
                         else "unmeasured"))
    if findings:
        pieces.append("%d open finding%s with timestamps and evidence"
                      % (len(findings), "" if len(findings) == 1 else "s"))
    if open_notes:
        pieces.append("%d open note%s" % (len(open_notes),
                                          "" if len(open_notes) == 1 else "s"))
    if not pieces:
        return _answer(
            "There is nothing measured or noted to hand over yet.",
            "An engineer handoff built from an unmeasured project would be "
            "a blank page with a letterhead.",
            "strong", action="Measure first, and pin your notes.",
            topic="engineer")
    return _answer(
        "The handoff should carry %s." % ", ".join(pieces),
        "An engineer works fastest from timestamps and numbers, not "
        "adjectives.",
        "strong",
        action="The delivery package already bundles the manifest and "
               "provenance; the findings and notes are on the Mix page to "
               "walk through together.",
        links=[("Mix room", "mix"), ("Deliver", "deliver")], topic="engineer")


def _tempo(ctx):
    m = ctx.get("measurements") or {}
    if m.get("bpm") is None:
        return _answer(
            "No stable tempo was measurable in this recording.",
            "The detector refuses to report a BPM when the transients do not "
            "agree - a wrong number would be worse than none.",
            "limited",
            missing="material with transients the detector can lock to",
            topic="tempo")
    key = m.get("key")
    return _answer(
        "%.1f BPM at %.2f confidence%s." % (
            m["bpm"], m.get("bpm_confidence") or 0,
            (", key estimate %s (fit %.2f)"
             % (key, m.get("key_fit") or 0)) if key else ""),
        "Tempo is onset autocorrelation; the key is chroma against the "
        "Krumhansl-Schmuckler profiles. Both are estimates with the number "
        "that says how much to trust them - autocorrelation genuinely "
        "cannot tell a tempo from its double.",
        "strong" if (m.get("bpm_confidence") or 0) >= 0.7 else "moderate",
        topic="tempo")


def _fallback(ctx):
    return _answer(
        "That is outside what this room can answer from the project.",
        "This room answers ONLY from what the project holds - measurements, "
        "findings, notes, versions, the checklist and the lifecycle - so it "
        "can never invent an answer that sounds measured.",
        "strong",
        missing=None,
        action="Try: what is blocking the release; what should I fix first; "
               "is this too compressed; is it clipping; what changed between "
               "versions; what notes are open; what should I send the "
               "engineer; what tempo and key is it.",
        topic="fallback")

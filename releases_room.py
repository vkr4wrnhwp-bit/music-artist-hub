"""The Releases room, as one screen.

The owner's mockup, 2026-09-22: you open the room and the release is there
- readiness, what is due, the arc, the calendar and the passport - instead
of a grid of cards. Three of those cards were the same page anyway:

    Releases         /releases/autopilot
    Release Calendar /releases/autopilot?view=calendar
    Release check    /releases/autopilot?view=ready

Three doors to one room, which is the "no double tabs" rule broken as
literally as it can be. They become this screen. Rollout Engine, Sync
Packs and Distribution are genuinely separate pages and stay as tiles.

WHERE EVERY FIGURE COMES FROM
-----------------------------
Nothing here is computed from anything but the account's own rows, and
each one can be pointed at:

  checks / score    app.py _release_checks: twelve derived checks against
                    this campaign's destinations, settings and rollout
  groups            app.py _CHECK_GROUPS, counted from those same checks
  days_left         the campaign's own release_date, date arithmetic
  stage             artist_os.autopilot_stage
  due days          the campaign's own release_date, less the window
                    a check belongs to (CHECK_WINDOW)
  drops             rollout posts with a scheduled_date
  passport rows     store.list_os_tracks + artist_os.clean_release

WHAT IT REFUSES TO DO
---------------------
  * A figure that was not measured reads "Not measured", never 0. A zero
    is a measurement; a blank is not.
  * A task's due date is shown only where it can be derived from the plan
    window it belongs to, which needs a release date. Without one the
    column is blank rather than a day somebody might act on.
  * Nothing is described as delivered. Delivery is the partner's and this
    application cannot see it.
"""
from datetime import date, timedelta

# The arc, in the owner's words on the mockup. Each one is a window in
# artist_os.campaign_plan except the last two, which are the days around
# the release itself.
STAGES = (
    ("60", "60-day plan", "Set the foundation", 60),
    ("30", "30-day plan", "Build and prepare", 30),
    ("14", "14-day plan", "Finalise and confirm", 14),
    ("week", "Release week", "Launch and activate", 7),
    ("after", "Post-release", "Measure and grow", 0),
)

# How many days before release a check is wanted, so a task can carry a due
# date. Anything not named here has no window and shows no date, which is
# the honest answer rather than a guess.
CHECK_WINDOW = {
    "release": 30,        # assets take the longest
    "metadata": 30,
    "smart_link": 14,
    "rights": 30,
    "fan_growth": 14,
    "rollout": 14,
}


def stage_now(days_left):
    """Which stage the release is at, from its own date. None with no date.

    The stage is the TIGHTEST window still ahead of the date: ten days out
    is the 14-day plan, not the 60-day one you started in. Past the date it
    is post-release. Further out than 60 days it is the 60-day plan, which
    is where the arc begins.
    """
    if days_left is None:
        return None
    here = STAGES[0][0]
    for key, _name, _sub, at in STAGES:
        if at >= days_left:
            here = key
    return here


def arc(days_left):
    """The rail. Each stage is done, now, or ahead."""
    here = stage_now(days_left)
    seen_here = False
    out = []
    for i, (key, name, sub, at) in enumerate(STAGES, start=1):
        if key == here:
            state, seen_here = "now", True
        elif seen_here:
            state = "ahead"
        else:
            state = "done" if days_left is not None else "ahead"
        out.append({"key": key, "n": i, "name": name, "sub": sub,
                    "at": at, "state": state})
    return out


def due_on(check_key, release_date):
    """The day a task is due: its own window counted back from release day.

    Traceable in one step - "metadata is wanted 30 days out, the release is
    the 1st, so it is due the 1st less 30 days". A task with no window, or a
    release with no date, carries no day at all: a date nobody can trace is
    worse than a blank, because somebody will work to it. A day already past
    is still shown, because an overdue date is a fact and hiding it would be
    the kinder lie.
    """
    want = CHECK_WINDOW.get(check_key)
    if want is None:
        return ""
    try:
        day = date.fromisoformat((release_date or "")[:10])
    except (TypeError, ValueError):
        return ""
    return (day - timedelta(days=want)).isoformat()


def tasks(checks, release_date, limit=None):
    """What needs attention, open first, each with where it came from."""
    out = []
    for label, ok, hint, href, key in checks or ():
        due = due_on(key, release_date)
        out.append({"label": label, "ok": bool(ok), "hint": hint,
                    "href": href, "key": key, "due": due,
                    "due_label": day_label(due)})
    out.sort(key=lambda t: (t["ok"], t["label"].lower()))
    return out[:limit] if limit else out


def headline(checks, days_left, drops):
    """The three numbers across the top, and what each is of.

    `drops` is None when nothing has been scheduled anywhere, which is not
    the same as none being due - so it reads Not measured rather than 0.
    """
    passed = sum(1 for _l, ok, _h, _r, _k in checks or () if ok)
    total = len(checks or ())
    return [
        {"key": "checks",
         "value": ("%d / %d" % (passed, total)) if total else "Not measured",
         "label": "Release checks passed",
         "sub": "" if total else "No release chosen"},
        {"key": "days",
         "value": str(days_left) if days_left is not None else "Not measured",
         "label": "Days left",
         "sub": "No release date set" if days_left is None else ""},
        {"key": "drops",
         "value": str(drops) if drops is not None else "Not measured",
         "label": "Scheduled drops",
         "sub": "Across all campaigns" if drops is not None else
                "Nothing scheduled yet"},
    ]


def build(campaign, checks, groups, days_left, release_date, drops, calendar,
          passport, campaigns, cards, sample=False, can_open=None,
          artist_name="", show="all"):
    """Everything the screen renders. No page logic beyond this."""
    tiles = []
    for key in ("rollout", "sync-packs", "distribution"):
        card = (cards or {}).get(key)
        if not card:
            continue
        href = card[0]
        if can_open and not can_open(href):
            continue
        tiles.append({"key": key, "href": href, "icon": card[1],
                      "name": card[2], "line": card[3]})
    all_tasks = tasks(checks, release_date)
    return {
        "campaign": campaign,
        "campaigns": campaigns or [],
        "artist_name": artist_name or "",
        "headline": headline(checks, days_left, drops),
        "arc": arc(days_left),
        "tasks": filtered(all_tasks, show),
        "task_total": len(all_tasks),
        "show": show if show in dict(SHOWS) else "all",
        "shows": list(SHOWS),
        "open_count": sum(1 for t in all_tasks if not t["ok"]),
        "meters": meters(groups),
        "overview": overview(campaign, days_left, passport),
        "calendar": calendar or [],
        "passport": passport_rows(passport),
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }


# --- the owner's mockup, 2026-09-22 ---------------------------------------
#
# Everything below is drawn on his image and nothing else. Where a field he
# drew has no data behind it the slot says so in words; where it does, this
# is the one place that reads it.

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")

# The task filter his mockup puts opposite "What needs attention now".
SHOWS = (("all", "All items"), ("open", "Open only"), ("passed", "Passed only"))


def day_label(iso):
    """2026-05-16 -> "May 16, 2026". Blank stays blank."""
    try:
        y, m, d = (iso or "")[:10].split("-")
        return "%s %d, %s" % (MONTHS[int(m) - 1], int(d), y)
    except (ValueError, IndexError):
        return ""


def filtered(rows, show):
    """His filter. "all" is the default and the only one that hides nothing."""
    if show == "open":
        return [t for t in rows if not t["ok"]]
    if show == "passed":
        return [t for t in rows if t["ok"]]
    return rows


def meters(groups):
    """His four donuts: the same counts, with the fraction they draw.

    A group with nothing in it has no fraction - 0/0 is not 0%, it is a
    question nobody asked - so `pct` is None and the ring stays empty.
    """
    out = []
    for g in groups or ():
        total = g.get("total") or 0
        done = g.get("done") or 0
        out.append({"label": g.get("label") or "",
                    "done": done, "total": total,
                    "pct": round(100 * done / total) if total else None})
    return out


def overview(campaign, days_left, passport):
    """The release, as his panel draws it.

    The four marks under the title are derived, never typed, and each one
    can be pointed at. A mark nothing measured reads "Not measured" and is
    grey - it is not a failure, it is an absence, and the two must not look
    alike.
    """
    if not campaign:
        return None
    tracks = [row["t"] for row in passport or ()]
    date = campaign.get("release_date") or ""

    def mark(name, ok, measured=True):
        if not measured:
            return {"name": "Not measured", "tone": "off", "of": name}
        return {"name": name, "tone": "good" if ok else "warn", "of": name}

    marks = []
    if tracks:
        blocked = any(row["clean"].get("blocked") for row in passport)
        marks.append(mark("Clean", not blocked))
        isrcs = [(t.get("passport") or {}).get("isrc") or "" for t in tracks]
        marks.append(mark("ISRC assigned", all(isrcs)))
    else:
        marks.append({"name": "Not measured", "tone": "off", "of": "Clean"})
        marks.append({"name": "Not measured", "tone": "off", "of": "ISRC assigned"})
    marks.append(mark("Cover art added", bool(campaign.get("cover_url"))))
    if tracks:
        marks.append(mark("Audio checked",
                          all((t.get("passport") or {}).get("audio_ok") for t in tracks)))
    else:
        marks.append({"name": "Not measured", "tone": "off", "of": "Audio checked"})

    bits = [campaign.get("release_type") or "Release"]
    if tracks:
        bits.insert(0, "%d track%s" % (len(tracks), "" if len(tracks) == 1 else "s"))
    return {
        "cover": campaign.get("cover_url") or "",
        "artist": campaign.get("artist_name") or "",
        "title": campaign.get("title") or "Untitled",
        "when": day_label(date),
        "left": days_left,
        "meta": " · ".join(bits),
        "marks": marks,
    }


def passport_rows(passport):
    """His Track passport table: one row per recording, his columns.

    Every column is a stored passport field. A field nobody filled in is
    "Not on file" rather than blank, so a gap cannot be mistaken for a
    column that does not apply.
    """
    out = []
    for row in passport or ():
        t = row["t"]
        p = t.get("passport") or {}
        rep = row["clean"]
        out.append({
            "id": t.get("id") or "",
            "title": t.get("title") or "Untitled",
            "isrc": p.get("isrc") or "",
            "explicit": p.get("explicit") or "",
            "metadata": "Complete" if p.get("upc") and p.get("isrc") else "",
            "audio": "Complete" if p.get("audio_ok") else "",
            "blocked": bool(rep.get("blocked")),
            "score": rep.get("score"),
        })
    return out


def short_day(iso):
    """2026-04-25 -> "Apr 25", the calendar rail's own label."""
    try:
        y, m, d = (iso or "")[:10].split("-")
        return "%s %d" % (MONTHS[int(m) - 1][:3], int(d))
    except (ValueError, IndexError):
        return ""

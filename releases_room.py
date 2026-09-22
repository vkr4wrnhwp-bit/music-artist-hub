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
        out.append({"label": label, "ok": bool(ok), "hint": hint,
                    "href": href, "key": key, "due": due_on(key, release_date)})
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
          passport, campaigns, cards, sample=False, can_open=None):
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
    return {
        "campaign": campaign,
        "campaigns": campaigns or [],
        "headline": headline(checks, days_left, drops),
        "arc": arc(days_left),
        "tasks": tasks(checks, release_date),
        "open_count": sum(1 for t in tasks(checks, release_date)
                          if not t["ok"]),
        "groups": groups or [],
        "calendar": calendar or [],
        "passport": passport or [],
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }

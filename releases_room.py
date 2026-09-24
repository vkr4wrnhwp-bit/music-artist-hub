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


# --- THE PLATE --------------------------------------------------------
# The working room is on the rooms' shared three-window plate (owner,
# 2026-09-23: every room's rack uses static/img/room-plate.webp, drawn by
# templates/partials/cc_rack.html). Its three screens carry this room's
# three figures - checks passed, days to release, open tasks - and the
# plate prints no names, so each screen says what it is. The release
# clock this room had before (releases-plate.webp) also carried THE PLAN,
# a ribbon of dated posts; that moved into its own panel directly under
# the plate (ribbon() below), so nothing the old plate showed is lost.
# Neither is the five-stage rail: that is the gold arc further down, and
# drawing it twice would be the screen folding onto itself.

# The label each screen prints. A days figure past its date is counted the
# other way under its own name: "-5 days to release" is a sum nobody reads.
SCREEN_CHECKS = "Checks passed"
SCREEN_DAYS = "Days to release"
SCREEN_DAYS_PAST = "Days past release"
SCREEN_TASKS = "Open tasks"
# The line under a dated countdown: the zero page's own words. A release
# date is a plan; delivery is the distributor's to confirm.
DATE_IS_A_PLAN = "A plan — not proof of delivery"
# Every line on these screens is ONE line on the short glass: measured
# with headless Chrome in Archivo at 12px, the widest (the plan line,
# 168px) fits its screen at every rack width the plate is drawn at
# (881px and up). A second line was clipped by the glass at 1280.


def rack_screens(checks, days_left, release_date):
    """The working room's three screens on the rooms' shared plate.

    Checks passed is passed over total, never a score. Days to release is
    the campaign's own date less today, and its line says the date is a
    PLAN - it is never proof of delivery, which is the distributor's to
    confirm. Open tasks is the checks still open, and a release whose checks
    all pass reads a measured 0 with the line that says why. Anything
    nothing measured - no release chosen, no release date - is words, set
    as an absence, never a 0 and never a countdown of 0.
    """
    total = len(checks or ())
    passed = sum(1 for c in checks or () if c[1])
    left = total - passed

    def fig(k, v, sub):
        return {"k": k, "v": v, "sub": sub, "fig": True, "none": False}

    def none(k, sub):
        return {"k": k, "v": "Not measured", "sub": sub, "fig": False, "none": True}

    out = [fig(SCREEN_CHECKS, "%d / %d" % (passed, total), "Read from your own records")
           if total else none(SCREEN_CHECKS, "No release chosen")]
    if days_left is None or not day_label(release_date):
        out.append(none(SCREEN_DAYS, "No release date set"))
    elif days_left > 0:
        out.append(fig(SCREEN_DAYS, str(days_left), DATE_IS_A_PLAN))
    elif days_left == 0:
        out.append(fig(SCREEN_DAYS, "Today", DATE_IS_A_PLAN))
    else:
        out.append(fig(SCREEN_DAYS_PAST, str(-days_left), DATE_IS_A_PLAN))
    if total:
        out.append(fig(SCREEN_TASKS, str(left),
                       ("Of %d checks, listed below" % total) if left
                       else "All %d checks passed" % total))
    else:
        out.append(none(SCREEN_TASKS, "No release chosen"))
    return out


# --- THE PAGE FROM ZERO (owner's Releases spec + mockup, 2026-09-23) ------
# An account with no release and no rollout does not meet an empty plate,
# twelve empty checks, an empty calendar, a countdown or a distribution
# status. It meets an onboarding page: the Command Center's photographed
# three-screen plate drawn STATIC with this room's words, one card that
# opens the campaign builder on a release, the four areas as doors, the
# five-step workflow as education, the two empties in words, help, and
# the tools in a drawer that starts open. A target date is a plan, not
# proof of delivery, and nothing here says otherwise. The animated
# standby that used to run on the plate is retired here, and so is the
# fill reel its empty windows ran: the working room's screens say an
# absence in words (rack_screens above).
ZERO_SUBTITLE = "Build the release record, check what is ready, and plan what happens next."
ZERO_RACK = (
    ("Purpose", "Turn finished music into a release-ready plan."),
    ("Start here", "Create one release and add its recordings."),
    ("Good to know", "A target date is a plan \u2014 not proof of delivery."),
)
# The one door. A release IS a campaign row of type "release" in
# links_store (ml_campaigns): the record the twelve checks, the arc, the
# calendar and the rollout all read - so the builder opened on that type
# creates the release record, not "only a smart link". The spec asked
# for exactly this confirmation (section 1).
DOOR = "/links/new?type=release&returnTo=/room/releases&from=releases-zero-state"
ZERO_PROJECT = {
    "heading": "Start with one release",
    "title": "Create your first release plan",
    "desc": "Choose a single, EP, or album. Add recordings now, or connect them later.",
    "cta": "Create a release",
    "need": "What do I need before I start?",
    # A seat that may not write here is told who creates releases rather
    # than handed a door that bounces. The builder is the Marketing room's
    # page (/links), so an edit seat needs that room too (audit releases-1).
    "locked": ("Releases are created by the account owner or a seat with edit "
               "access to the Releases and Marketing rooms. Releases opens here "
               "once one exists."),
    # A plan the builder is not part of is told so rather than handed a
    # door that answers 402 (audit releases-20).
    "tier": "Creating a release needs an Artist membership or higher.",
    # An account under the read-only demo lock is offered no write door:
    # the builder would only bounce at the lock (audit, 2026-09-23).
    "readonly": "This account is read only, so releases cannot be created here.",
}
# What the first save needs (spec section 3), shown in place when the
# card's second action is opened.
FIRST_SAVE = ("The release type: single, EP, or album",
              "A working title",
              "The primary artist or label account")
# The four areas (spec section 4), each a door by its own room card.
LENSES = (
    ("record", "Release record",
     "Type, title, artists, recordings, identifiers, rights, artwork, territories, and dates.",
     "autopilot"),
    ("checks", "Readiness checks",
     "The twelve checks, grouped, with blockers, warnings, and improvements.",
     "release-check"),
    ("rollout", "Rollout & calendar",
     "Working date, campaign milestones, scheduled posts, approvals, and follow-up.",
     "release-calendar"),
    ("distribution", "Distribution & sync packs",
     "Application status, distributor responses, delivery evidence, and sync-pack readiness.",
     "distribution"),
)
# The five steps, EDUCATIONAL on a new account: Create lit, the rest
# neutral, numbered as the owner's mockup numbers them, no percentage.
# STAGES (the 60/30/14-day arc) stays the populated room's rail.
WORKFLOW = (
    ("create", "Create", "Choose type and title"),
    ("music", "Add music", "Connect recordings"),
    ("prepare", "Prepare", "Add metadata & artwork"),
    ("check", "Check", "Review readiness"),
    ("launch", "Launch", "Plan rollout & delivery"),
)
ZERO_PLAN = ("Your release plan will appear here",
             "Each release will show its recordings, checks, target date, rollout, "
             "and next action.")
ZERO_SCHEDULE = ("Nothing is scheduled yet",
                 "A target date, application, or rollout is never shown as confirmed delivery.")
ZERO_HELP = ("Not sure whether your music is ready?",
             "Ask Street Banker what to finish now and what can wait.")
# The two links under "Your release plan will appear here": the checks are
# explained by the workflow on this page, the requirements by the card's
# own list - neither opens a page that has nothing to show before a
# release exists.
ZERO_LINKS = (("How release checks work", "#rl-z-flow-h"),
              ("Release requirements", "#rl-z-need"))
# The drawer at the foot: the spec's four areas, each tool by its room card.
# Track Passports is the Publishing room's card; spec section 4 names it
# under More Release tools, so the route lends it to this drawer (audit
# releases-11) and a seat that cannot open /catalog does not see it.
ZERO_BANDS = (
    ("Release record", ("autopilot", "track-passports")),
    ("Readiness checks", ("release-check",)),
    ("Rollout & calendar", ("release-calendar", "rollout")),
    ("Distribution & sync packs", ("distribution", "sync-packs")),
)
# The sentence the room carries back from the builder.
DONE_LINE = "Your first release was created. Its twelve checks are ready to run."


# --- THE SHOWCASE (the demo account) ------------------------------------
# The demo account is the showcase and never the page from zero (owner's
# ruling; the Marketing room's pattern, app.py _marketing_room). With no
# release and no rollout of its own it is shown this in-memory example:
# one release, its twelve checks, a dated rollout and a passport row,
# marked Sample data wherever they appear and never written to the
# database. The route decides who sees it; a release or rollout the demo
# really made is shown instead, unmarked. Nothing in it is a door into a
# record, because there is no record behind it: its tasks and passport
# row are words, and the header offers the real builder.
SHOWCASE_TITLE = "Night Drive"
SHOWCASE_DAYS_OUT = 24
# The twelve checks app.py _release_checks derives, in its order, with the
# example's answers: eight passed, four open. (label, passed, hint, key)
SHOWCASE_CHECKS = (
    ("Cover art set", False, "Upload or auto-scan cover art in the campaign builder.", "release"),
    ("Release date set", True, "A date drives the pre-save countdown and auto-conversion.", "release"),
    ("Spotify destination", True, "Add the Spotify link (auto-scan can find it).", "smart_link"),
    ("Apple Music destination", True, "Add the Apple Music link.", "smart_link"),
    ("YouTube destination", False, "Add the YouTube link.", "smart_link"),
    ("Campaign published", True, "Publish the campaign so the public page is live.", "smart_link"),
    ("Fan capture enabled", True, "Own the fan: enable email capture.", "fan_growth"),
    ("Consent copy set", True, "Consent text is stored with every signup.", "rights"),
    ("ISRC on catalog track", False, "Add the track to your catalog so identifiers auto-pull.", "metadata"),
    ("Rollout scheduled", True, "Generate the social rollout with tracked links per post.", "rollout"),
    ("Promo variants created", False, "Create per-channel variants so every door is measured.", "smart_link"),
    ("Press kit ready", True, "Update your EPK: press and promoters will ask for it.", "release"),
)
# The example rollout's dated posts: (days from today, caption, platform).
SHOWCASE_POSTS = (
    (3, "Cover reveal", "Instagram"),
    (9, "Teaser clip", "TikTok"),
    (17, "Pre-save push", "Instagram"),
    (24, "Out now", "TikTok"),
)


def showcase(today, artist=""):
    """The example release, dated from `today` so its countdown and arc
    stay live: a single SHOWCASE_DAYS_OUT days out, its checks, its
    rollout's dated posts and one passport row. A fresh copy each call."""
    release_date = (today + timedelta(days=SHOWCASE_DAYS_OUT)).isoformat()
    campaign = {"id": "", "title": SHOWCASE_TITLE, "artist_name": artist or "",
                "release_type": "Single", "release_date": release_date,
                "cover_url": "", "status": "live"}
    checks = [(label, ok, hint, "", key) for label, ok, hint, key in SHOWCASE_CHECKS]
    calendar = []
    for days, caption, platform in SHOWCASE_POSTS:
        when = (today + timedelta(days=days)).isoformat()
        calendar.append({"date": when, "when_label": short_day(when), "title": caption,
                         "where": platform, "campaign": "%s rollout" % SHOWCASE_TITLE})
    passport = [{"t": {"id": "", "title": SHOWCASE_TITLE,
                       "passport": {"explicit": "No", "audio_ok": True}},
                 "clean": {"blocked": False, "score": None}}]
    return {"campaign": campaign, "checks": checks, "release_date": release_date,
            "calendar": calendar, "drops": len(calendar), "passport": passport}


def releases_of(campaigns):
    """The campaigns that ARE releases: a campaign row of type "release"
    (an unset type is the builder's default, release). A Fan Hub or a
    Pre-save is a campaign, not a release, and ends nothing here (audit
    releases-3)."""
    return [c for c in campaigns or () if (c.get("campaign_type") or "release") == "release"]


def new_account(campaigns, drops):
    """The spec's new_account: no release, and no rollout at all (drops is
    None when the account has no rollout; a rollout with nothing dated is
    0, which is activity). The arguments are what the stores returned;
    an unreadable store never reaches here - the route shows the error
    page."""
    return not campaigns and drops is None


def done_line(came_from, campaigns):
    """Said by the SAVED release, never by the param alone."""
    return DONE_LINE if came_from == "releases-zero-state" and campaigns > 0 else ""


def _tile(cards, key, can_open=None):
    card = (cards or {}).get(key)
    if not card:
        return None
    href = card[0]
    if can_open and not can_open(href):
        return None
    # The owner's mark on a page they hid rides with the tile (rooms.build
    # keeps a hidden page for the owner alone); nothing else is judged.
    return {"key": key, "href": href, "icon": card[1], "name": card[2], "line": card[3],
            "state": card[4] if len(card) > 4 else ""}


def zero_page(can_add=True, can_open=None, cards=None):
    """The page from zero. A seat sees only the doors it can open; an area
    whose page a seat cannot open is words, not a door."""
    lenses = []
    for key, name, line, card_key in LENSES:
        tile = _tile(cards, card_key, can_open)
        lenses.append({"key": key, "name": name, "line": line,
                       "href": tile["href"] if tile else ""})
    bands = []
    for title, keys in ZERO_BANDS:
        got = [t for t in (_tile(cards, k, can_open) for k in keys) if t]
        if got:
            bands.append({"title": title, "tiles": got})
    return {
        "subtitle": ZERO_SUBTITLE,
        "screens": [{"k": k, "v": v} for k, v in ZERO_RACK],
        "door": DOOR,
        "project": dict(ZERO_PROJECT, can=can_add),
        "first_save": FIRST_SAVE,
        "lenses": lenses,
        "workflow": WORKFLOW,
        "plan": ZERO_PLAN,
        "schedule": ZERO_SCHEDULE,
        "help": ZERO_HELP,
        "links": ZERO_LINKS,
        "bands": bands,
    }


def ribbon(calendar, limit=5):
    """THE PLAN: the next dated posts, soonest first - the panel directly
    under the plate (it was the old release clock's ribbon window).

    Every row is a post somebody actually scheduled. Nothing here is
    predicted, and an account with no rollout at all gets the words that
    say so rather than an empty list. A scheduled day is a plan: nothing
    here says a post went out.
    """
    return [{"when": r.get("when_label") or r.get("date") or "",
             "what": r.get("title") or "",
             "where": r.get("where") or ""}
            for r in (calendar or ())[:limit]]


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
          artist_name="", show="all", zero=None, can_add=True):
    """Everything the screen renders. No page logic beyond this.

    `zero` is new_account() decided by the route (None here means: decide
    from the campaigns and the rollouts); `can_add` is who may create a
    release (see zero_page)."""
    if zero is None:
        zero = new_account(campaigns, drops)
    tiles = []
    for key in ("rollout", "sync-packs", "distribution"):
        card = (cards or {}).get(key)
        if not card:
            continue
        href = card[0]
        if can_open and not can_open(href):
            continue
        # The owner's mark on a page they hid rides with the tile.
        tiles.append({"key": key, "href": href, "icon": card[1],
                      "name": card[2], "line": card[3],
                      "state": card[4] if len(card) > 4 else ""})
    all_tasks = tasks(checks, release_date)
    return {
        "campaign": campaign,
        "campaigns": campaigns or [],
        "artist_name": artist_name or "",
        "headline": headline(checks, days_left, drops),
        # The plate: the rooms' three screens - checks passed, days to
        # release, open tasks (owner, 2026-09-23).
        "screens": rack_screens(checks, days_left, release_date),
        # THE PLAN, the old clock's ribbon window: its own panel directly
        # under the plate now.
        "ribbon": ribbon(calendar),
        # The third headline figure. The plate has no screen for it - its
        # three are checks, days and open tasks - so it rides on the line
        # under the plate, just above the plan it counts. Without this it
        # was computed by _release_drops and rendered nowhere.
        "drops": headline(checks, days_left, drops)[2],
        # Nothing AT ALL: no release chosen and no dated post anywhere.
        # The calendar has to be in this test - an account can have a
        # rollout with dated posts and no chosen release, and the first
        # cut of this hid that ribbon behind the standby, so a post the
        # artist had scheduled simply vanished (caught by
        # test_a_dated_rollout_post_appears_on_the_page...).
        # No release and no rollout: the page from zero. One of either and
        # the plate takes over untouched (a rollout's dated posts included,
        # which the first standby hid - test_a_dated_rollout_post...).
        "idle": bool(zero),
        "zero": zero_page(can_add, can_open, cards) if zero else None,
        # Who may write, for the working room's header door too: "locked"
        # (the read-only demo lock) is offered none. The showcase's header
        # door is the real builder, since its example has no record to edit.
        "can_add": can_add,
        "door": DOOR,
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
        # The mark is literal: it appears when the release on the page is
        # the showcase's example, and never as decoration.
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

"""The Stage room, as one screen.

The Stage Plot's own designer is the room, with the Light Designer as a card
beside the others. Tour appears nowhere: it is its own suite.

The room DID open on a lit stage you could drag lights around (owner,
2026-09-22). It was withdrawn the same day, in his words: "this looks way too
cheap ... looks like a two-year-old did it." He was right, and the reason is
worth keeping, because the fix is known and cheap when it is wanted:

    the room drew its stage as flat SVG rectangles and triangles, while the
    Light Designer itself draws onto a PHOTOGRAPH (static/img/stage-bg-2.jpg)
    using a sprite that is an 8-lens LED bar photographed head-on
    (static/img/light-bar.png). Vector primitives next to a product whose
    whole look is photo plates read as a toy.

Both assets already ship. A second pass that uses them would look like the
Designer rather than like a diagram, and the rig/cue/look code that drove it
is intact in the history (87fcbcc9).

WHERE EVERY FIGURE COMES FROM
-----------------------------
One saved show and one saved plot per account, both JSON blobs the editors
write, read back here without a second copy of their rules:

  show      db.get_light_show  -> {name, bars, chans, cues[], pos{}, rot{},
                                   rigName, dmxUniverse, dmxStart, dmxAddr{}}
  cues      each {t, group, color, intensity, fade, note, look, move}
  plot      db.get_stage_plot  -> {items{}, pos{}}
  inputs    stage_plot_catalog.as_input_rows - the SAME catalogue the editor
            uses, already mirrored server-side and guarded by
            tests/test_stage_plot_catalog.py against the two drifting
  version   passport_store - a passport has no version until it is published

WHAT IT REFUSES TO DO
---------------------
  * Nothing here claims a venue has received, confirmed or approved
    anything. A plot and a rig are what the artist intends.
  * Nothing unsaved reads 0. "No show saved yet" and "Never published" are
    the honest words, and a passport really does have no version until a
    first publish.
  * No control on this screen edits anything. The room is a door: every
    action links into the editor that owns it. A button that looks like it
    programmes a cue and does not is worse than no button.
  * No phantom power on the input list, and no fade-in/fade-out pair. The
    editor saves neither - a cue has ONE fade - and a column nothing can
    fill is a promise the page cannot keep.
"""
import stage_plot_catalog

# The path from a rig to a published technical record. Each rung is a
# stored fact.
STEPS = (
    ("rigged", "Rigged", "Fixtures placed on the stage"),
    ("patched", "Patched", "Channels addressed on the desk"),
    ("cued", "Cued", "Looks programmed against the song"),
    ("plotted", "Plotted", "Backline and inputs drawn"),
    ("passported", "Passported", "The technical record published"),
)

# A fixture is an LED bar. Each takes 3 or 4 DMX channels, and the editor
# offers only those two.
DEFAULT_CHANS = 4

# What the Light Studio itself starts a new user with (static/js/lights.js:16
# boots `{name: "", bars: 6, chans: 4, cues: []}` when nothing is saved). The
# room shows the same thing rather than a black rectangle, because an empty
# stage is not what the editor would give you and a new account should see
# what the tool IS. It is marked as the starter on the page, every time.
STARTER_BARS = 6


def _int(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def timecode(t):
    """Seconds -> M:SS, the way the studio's own transport reads."""
    try:
        t = max(0.0, float(t))
    except (TypeError, ValueError):
        return "0:00"
    m = int(t // 60)
    s = int(t - m * 60)
    return "%d:%02d" % (m, s)


def rig(show):
    """The strip an LD reads first: whose rig, which universe, from where."""
    show = show or {}
    bars = max(0, _int(show.get("bars")))
    chans = 3 if _int(show.get("chans"), DEFAULT_CHANS) == 3 else DEFAULT_CHANS
    return {
        "name": (show.get("rigName") or show.get("name") or "").strip(),
        "universe": max(1, _int(show.get("dmxUniverse"), 1)),
        "start": max(1, _int(show.get("dmxStart"), 1)),
        "chans": chans,
        "fixtures": bars,
        # What the rig actually occupies on the desk. Not a round number
        # somebody typed: it is the bars times their channel width.
        "channels": bars * chans,
    }


def address_of(show, bar):
    """A bar's start address: its own patch if it has one, else in order.

    Mirrors lights-engine.js fixtureAddress(). The editor lets a bar be
    patched explicitly, and an explicit patch wins.
    """
    show = show or {}
    chans = 3 if _int(show.get("chans"), DEFAULT_CHANS) == 3 else DEFAULT_CHANS
    own = _int((show.get("dmxAddr") or {}).get(str(bar)), 0)
    if own >= 1:
        return max(1, min(512, own))
    start = max(1, _int(show.get("dmxStart"), 1))
    return max(1, min(512, start + (bar - 1) * chans))


def starter_fixtures():
    """The starting rig, evenly across the truss.

    Only ever drawn when NOTHING is saved, and always beside the words that
    say so. The editor places an un-dragged bar itself; this is the room's
    reading of the same six, spread along the truss so the stage is a rig
    rather than an empty box.
    """
    step = 100.0 / (STARTER_BARS + 1)
    return [{"n": i, "address": 1 + (i - 1) * DEFAULT_CHANS,
             "place": "Truss", "across": round(step * i)}
            for i in range(1, STARTER_BARS + 1)]


def fixtures(show):
    """One row per bar: where it hangs and what it answers to.

    "Truss" or "floor" is the editor's own reading of a bar's height on the
    stage (lights.js: p[1] < 0.5 is truss), not a field somebody typed.
    """
    show = show or {}
    bars = max(0, _int(show.get("bars")))
    pos = show.get("pos") or {}
    out = []
    for i in range(1, bars + 1):
        p = pos.get(str(i)) or pos.get(i) or []
        try:
            across, height = float(p[0]), float(p[1])
        except (IndexError, TypeError, ValueError):
            across, height = None, None
        out.append({
            "n": i,
            "address": address_of(show, i),
            "place": ("Truss" if height is not None and height < 0.5
                      else ("Floor" if height is not None else "")),
            "across": round(across * 100) if across is not None else None,
        })
    return out


def fixture_groups(show):
    """The owner's fixture list: all, and the two places a bar can hang.

    His mockup drew Front Truss and Back Truss. The editor does not know
    front from back - only truss from floor - so this is two groups, not
    three. A group the data cannot fill would be a filter that lies.
    """
    rows = fixtures(show)
    truss = sum(1 for r in rows if r["place"] == "Truss")
    floor = sum(1 for r in rows if r["place"] == "Floor")
    return [{"key": "all", "label": "All fixtures", "n": len(rows)},
            {"key": "truss", "label": "Truss", "n": truss},
            {"key": "floor", "label": "Floor", "n": floor}]


def cue_name(cue):
    """What the studio calls this look when nobody named it."""
    note = (cue.get("note") or "").strip()
    if note:
        return note
    if _int(cue.get("intensity"), 0) <= 0:
        return "Blackout"
    return "Look"


def cues(show, limit=None):
    """The cue list, in time order, with the columns the mockup draws.

    ONE fade. The editor saves `fade` and nothing else; a fade-in and a
    fade-out would be the same number printed twice under two headings.
    """
    show = show or {}
    rows = []
    for cue in show.get("cues") or ():
        if not isinstance(cue, dict):
            continue
        rows.append({
            "t": float(cue.get("t") or 0),
            "at": timecode(cue.get("t")),
            "name": cue_name(cue),
            "group": (cue.get("group") or "all").strip() or "all",
            "intensity": max(0, min(100, _int(cue.get("intensity"), 0))),
            "fade": round(float(cue.get("fade") or 0), 2),
            "colour": cue.get("color") or "",
            "blackout": _int(cue.get("intensity"), 0) <= 0,
        })
    rows.sort(key=lambda c: c["t"])
    for i, row in enumerate(rows, start=1):
        row["n"] = i
    return rows[:limit] if limit else rows


def span(rows):
    """How long the programmed show runs, for the timeline's own scale."""
    return max([c["t"] for c in rows] or [0])


def plot(state, image):
    """The saved plot: its drawing if one exists, and its input list.

    Three states, because there really are three. The drawing is made in
    the browser and posted back - this server has no renderer - so a plot
    can exist with no picture, and that is said rather than shown as an
    empty frame.
    """
    rows = stage_plot_catalog.as_input_rows(state or {})
    items = sum(_int(n) for n in ((state or {}).get("items") or {}).values())
    return {
        "saved": bool(state),
        "has_image": bool(image),
        "items": items,
        "inputs": rows,
        "state": ("drawn" if state and image else
                  ("list_only" if state else "empty")),
    }


def figures(show, the_rig, version):
    """The three across the top, each able to say it has nothing."""
    cue_rows = cues(show)
    return [
        {"key": "cues",
         "value": str(len(cue_rows)) if show else "No show saved yet",
         "measured": bool(show),
         "label": "Cues", "sub": "In your saved show",
         "note": ("From %s" % (show.get("name") or "your show")) if show else ""},
        {"key": "channels",
         "value": str(the_rig["channels"]) if the_rig["fixtures"] else "Nothing patched",
         "measured": bool(the_rig["fixtures"]),
         "label": "Channels", "sub": "Patched on the rig",
         "note": ("From universe %d" % the_rig["universe"]) if the_rig["fixtures"] else ""},
        {"key": "version",
         # A passport with no published version has none - not version 0.
         "value": ("Version %s" % version) if version else "Never published",
         "measured": bool(version),
         "label": "Passport version", "sub": "The technical record",
         "note": "" if version else "No version yet"},
    ]


def path(show, the_rig, the_plot, version):
    """The five circles, each carrying what it counted."""
    cue_rows = cues(show)
    placed = sum(1 for f in fixtures(show) if f["place"])
    state = {
        "rigged": (the_rig["fixtures"] > 0,
                   ("%d fixture%s placed" % (the_rig["fixtures"],
                                             "" if the_rig["fixtures"] == 1 else "s"))
                   if the_rig["fixtures"] else "No fixtures yet"),
        "patched": (the_rig["fixtures"] > 0,
                    ("%d channels from address %d" % (the_rig["channels"], the_rig["start"]))
                    if the_rig["fixtures"] else "Nothing patched"),
        "cued": (bool(cue_rows),
                 ("%d cue%s" % (len(cue_rows), "" if len(cue_rows) == 1 else "s"))
                 if cue_rows else "No cues yet"),
        "plotted": (the_plot["saved"],
                    "Plot saved" if the_plot["saved"] else "No plot yet"),
        "passported": (bool(version),
                       ("Version %s" % version) if version else "Never published"),
    }
    out = []
    for i, (key, name, sub) in enumerate(STEPS, start=1):
        reached, line = state[key]
        out.append({"key": key, "n": i, "name": name, "sub": sub,
                    "line": line, "reached": bool(reached)})
    # `placed` is read for the rigged rung's truthfulness: a bar with no
    # stored position is counted in bars but is not yet ON the stage.
    out[0]["placed"] = placed
    return out


# --- THE RACK ---------------------------------------------------------
# The working room on the rooms' shared three-window plate (owner,
# 2026-09-23: every room's rack is the shorter plate drawn by
# templates/partials/cc_rack.html). The Show Control desk it replaces
# (static/img/stage-plate.webp, left in place) silkscreened CUES,
# CHANNELS, PASSPORT and THE STAGE; the new plate prints no names, so
# each screen says what it is. Its fourth, wide window - THE STAGE, the
# saved cue list - is not lost: it is its own panel directly under the
# plate (templates/room_stage.html), and still the only place in this
# room the cue list appears.
RACK_ORDER = ("cues", "channels", "version")


def rack_screens(show, the_rig, version):
    """The three screens: Cues, Channels, Passport - figures() again,
    each worded for the glass. A reading is a figure; an absence is words
    and never a nought, and the line under it says what the light show or
    the passport actually holds."""
    show = show or {}
    by = {f["key"]: f for f in figures(show, the_rig, version)}
    n_cues = len(cues(show))
    name = (show.get("name") or "").strip() or "your saved show"
    fixtures_n = the_rig["fixtures"]

    if not show:
        # The room can be open with no light show at all (a tour show or a
        # plot is enough), so this names the light show, not "a show".
        cue = {"v": "No light show saved", "sub": "Programme one in the Light Designer"}
    elif not n_cues:
        cue = {"v": "No cues yet", "sub": "Nothing programmed in %s" % name}
    else:
        cue = {"v": str(n_cues), "sub": "In %s" % name}

    if fixtures_n:
        chan = {"v": by["channels"]["value"],
                "sub": "%d fixture%s · universe %d" % (
                    fixtures_n, "" if fixtures_n == 1 else "s", the_rig["universe"])}
    else:
        chan = {"v": by["channels"]["value"],
                "sub": "No fixtures on the rig" if show else "No rig saved yet"}

    ver = by["version"]
    pas = {"v": ver["value"],
           "sub": "The technical record, published" if ver["measured"]
                  else "The technical record has no version yet"}

    read = {"cues": (cue, bool(n_cues)),
            "channels": (chan, bool(fixtures_n)),
            "version": (pas, bool(ver["measured"]))}
    label = {"cues": "Cues", "channels": "Channels", "version": "Passport"}
    out = []
    for key in RACK_ORDER:
        sc, measured = read[key]
        out.append({"key": key, "k": label[key], "v": sc["v"], "sub": sc["sub"],
                    "fig": measured, "none": not measured})
    return out


# --- THE PAGE FROM ZERO (owner's Stage spec + mockup, 2026-09-23) ---------
# An account with no shows, no tours, no plot, no light show and no
# passport does not meet an empty desk or the plot editor. It meets an
# onboarding page: the Command Center's photographed three-screen plate
# drawn STATIC with this room's words, one card that adds the first show
# (the four fields the spec asks for and nothing else), what Stage keeps
# together, the five-stage workflow as education, the two empties in
# words, help, and the tools in a drawer that starts open. The animated
# standby that used to run on the desk for an empty account is retired,
# and since the working room moved onto the same plate (2026-09-23) so is
# the fill reel its empty windows showed: an absence there is words.
ZERO_SUBTITLE = "Turn show details into a plan everyone can use."
ZERO_RACK = (
    ("Purpose", "Make every show operationally ready."),
    ("Start here", "Add your first show or tour date."),
    ("Good to know", "One show record connects the plot, team, lights, and advance."),
)
# The one door. A show is the Tour desk's record - tour_shows, on a tour
# of one date - made by POST /tours/new with one_off=1, so Stage never
# invents a second kind of show (spec: one Show record for every tool).
# returnTo brings the person back here; the route answers with ?from=show.
SHOW_FORM = {"action": "/tours/new", "return_to": "/room/stage"}
ZERO_PROJECT = {
    "heading": "Create your first Stage project",
    "title": "Start with a show",
    "desc": ("Add the date, venue, and basic schedule that the stage plot, "
             "team, and advance will share."),
    "cta": "Add your first show",
    "note": "You can complete technical details after the show is saved.",
    # A seat that may not write, or a plan without Tour, is told who adds
    # shows rather than handed a form that bounces.
    "locked": ("Shows are added by the account owner or a seat with edit "
               "access to the Stage room. The Stage opens here once one exists."),
    "tier": "Adding a show needs a membership that includes Tour.",
}
# What one show record carries through this room. GOLD icons: these
# explain capabilities and must not look completed (spec).
KEEPS = (
    ("show", "Venue, date, and schedule", "The show record every Stage tool reads."),
    ("plotted", "Stage plot and equipment", "Where people and gear stand, and the input list."),
    ("lights", "Team, lighting, and advance",
     "Who is coming, what the rig does, and the package the venue gets."),
)
# The five stages, EDUCATIONAL on a new account: Show details lit, every
# later stage neutral, no percentage, nothing in progress until something
# is saved. STEPS (Rigged .. Passported) stays the populated room's rail.
WORKFLOW = (
    ("show", "Show details", "Create the show record"),
    ("plotted", "Stage plot", "Place people and equipment"),
    ("team", "Team & tech", "Confirm people, contacts, and requirements"),
    ("advance", "Build advance", "Package the confirmed show information"),
    ("showday", "Show day", "Use the final plan and record outcomes"),
)
ZERO_SHOWS = ("Your shows will appear here",
              "After you add a show, Street Banker will create one Stage workspace "
              "for its venue, plot, people, and advance.")
ZERO_ADVANCE = ("Nothing to advance yet",
                "Readiness, missing technical details, and advance status will "
                "appear after you add a show.")
ZERO_HELP = ("Need help planning your first show?",
             "Ask Street Banker what to collect from the venue before load-in.")
HELP_QUESTIONS = ("What should I ask the venue for?",
                  "What belongs on a stage plot?",
                  "What is an advance?",
                  "When should I send the advance?",
                  "What should I confirm before show day?")
# The two links under "Your shows will appear here". No page explains
# stage planning or the advance yet, so both point into this page - the
# workflow rail says how planning goes, the help band is where the
# advance question is asked - and neither opens the plot editor (spec:
# no contextless editor before a show exists).
ZERO_LINKS = (("How stage planning works", "#sg-z-flow-h"),
              ("What belongs in an advance", "#sg-z-help-h"))
# The drawer at the foot: the spec's six tools, by their room cards.
ZERO_TILES = ("stage-plot", "lights", "tour-board", "passports", "live", "tours")
# The sentence the room carries back from the show door, with one next
# action (spec: "tasks return with a completion message and one next
# action").
DONE_LINE = "Your first show was added. Its Stage workspace is ready. Next, draw the stage plot."


def new_account(shows, tours, light_show, plot_state, passports):
    """The spec's new_account: confirmed empty on every count it names.
    Every argument is what the store returned, so an unreadable store
    never reaches here - the route shows the error page instead."""
    return not shows and not tours and not light_show and not plot_state and not passports


def done_line(came_from, shows):
    """Said by the SAVED show, never by the param alone."""
    return DONE_LINE if came_from == "show" and shows > 0 else ""


def zero_page(can_add=True, can_open=None):
    """The page from zero. can_add is True, "seat" (a seat that may not
    write here) or "tier" (a plan without Tour); the card says which."""
    return {
        "subtitle": ZERO_SUBTITLE,
        "screens": [{"k": k, "v": v} for k, v in ZERO_RACK],
        "project": dict(ZERO_PROJECT, can=can_add),
        "form": dict(SHOW_FORM),
        "keeps": KEEPS,
        "workflow": WORKFLOW,
        "shows": ZERO_SHOWS,
        "advance": ZERO_ADVANCE,
        "help": ZERO_HELP,
        "questions": HELP_QUESTIONS,
        "links": ZERO_LINKS,
    }


def build(show, plot_state, plot_image, version, cards,
          artist_name="", sample=False, can_open=None,
          zero=False, can_add=True):
    """Everything the screen renders. No page logic beyond this.

    `zero` is new_account() decided by the route from every count the
    spec names; `can_add` is who may add a show (see zero_page)."""
    the_rig = rig(show)
    the_plot = plot(plot_state, plot_image)
    cue_rows = cues(show)

    tiles = []
    for key in ("lights", "passports", "tour-board", "live"):
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

    # With no show at all the stage draws the editor's own starter rig,
    # marked. With one, it draws the artist's.
    placed = fixtures(show) if show else starter_fixtures()

    # The drawer on the page from zero: the spec's six tools, each a card
    # of this room, and a seat sees only the ones it can open.
    zero_tiles = []
    for key in ZERO_TILES:
        card = (cards or {}).get(key)
        if not card:
            continue
        href = card[0]
        if can_open and not can_open(href):
            continue
        # The owner's mark on a page they hid rides with the tile
        # (rooms.build keeps a hidden page for the owner alone).
        zero_tiles.append({"key": key, "href": href, "icon": card[1],
                           "name": card[2], "line": card[3],
                           "state": card[4] if len(card) > 4 else ""})

    return {
        "artist_name": artist_name or "",
        "starter": not bool(show),
        "show_name": (show or {}).get("name") or "",
        "has_show": bool(show),
        "rig": the_rig,
        "fixtures": placed,
        "groups": fixture_groups(show),
        "cues": cue_rows,
        "span": span(cue_rows),
        "span_label": timecode(span(cue_rows)),
        "plot": the_plot,
        "figures": figures(show, the_rig, version),
        # The rooms' shared plate: Cues, Channels, Passport, each on its
        # own screen. The cue list the old desk's wide window held is its
        # own panel under the plate, drawn from "cues" above.
        "screens": rack_screens(show, the_rig, version),
        # Nothing saved on any count: the page from zero. One show, plot,
        # light show or passport and the desk takes over untouched.
        "idle": bool(zero),
        "zero": zero_page(can_add, can_open) if zero else None,
        "zero_tiles": zero_tiles,
        "path": path(show, the_rig, the_plot, version),
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }

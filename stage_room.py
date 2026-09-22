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


def build(show, plot_state, plot_image, version, cards,
          artist_name="", sample=False, can_open=None):
    """Everything the screen renders. No page logic beyond this."""
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
        tiles.append({"key": key, "href": href, "icon": card[1],
                      "name": card[2], "line": card[3]})

    # With no show at all the stage draws the editor's own starter rig,
    # marked. With one, it draws the artist's.
    placed = fixtures(show) if show else starter_fixtures()

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
        "path": path(show, the_rig, the_plot, version),
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }

"""What the Stage Plot editor can put on a stage, server-side.

The Stage Plot page (static/js/stageplot.js) already derives a channel list
from what you drag on: place a drum kit and seven inputs appear. That list is
good, it is already exported in the PNG the TOUR advance email attaches, and
duplicating the act of typing it into a Show Passport would be absurd.

So the passport imports it instead. To do that the server has to know the same
catalogue the browser does, which means the list below is a SECOND COPY of the
one in stageplot.js. That is a real risk - two copies drift - so
`tests/test_stage_plot_catalog.py` parses the JavaScript and fails if they stop
agreeing. Duplication guarded by a test is a trade; duplication nobody checks
is a bug waiting.

Only `key` and `inputs` are mirrored. Width, height and glyph are drawing
concerns and the server has no use for them.
"""
import re

# key -> the input templates that key contributes. "{n}" is the instance
# number, blank when there is only one of that thing on stage.
CATALOG = [
    ("riser", []),
    ("drums", ["Kick — Beta 52", "Snare — SM57", "Hi-Hat — SM81",
               "Rack Tom — e604", "Floor Tom — e604", "OH L — SM81", "OH R — SM81"]),
    ("gtr", ["Guitar Amp {n} — SM57"]),
    ("bass", ["Bass — DI"]),
    ("keys", ["Keys {n} L — DI", "Keys {n} R — DI"]),
    ("acoustic", ["Acoustic {n} — DI"]),
    ("vox", ["Vocal {n} — SM58"]),
    ("playback", ["Tracks L — DI", "Tracks R — DI"]),
    ("dj", ["DJ L — DI", "DJ R — DI"]),
    ("wedge", []),
    ("power", []),
]

# The channel strings read "Source — Mic". An em dash, not a hyphen: it is what
# the editor writes and what the exported PNG shows.
_SPLIT = re.compile(r"\s+—\s+")


def channel_list(state):
    """The same list the editor draws, from a saved plot.

    Mirrors stageplot.js channelList(): walk the catalogue in order, and for
    each unit on stage emit its templates with {n} filled in - blank when there
    is only one, so a solo guitarist gets "Guitar Amp" and not "Guitar Amp 1".
    """
    items = (state or {}).get("items") or {}
    out = []
    for key, templates in CATALOG:
        try:
            count = int(items.get(key) or 0)
        except (TypeError, ValueError):
            count = 0
        for i in range(1, count + 1):
            for tpl in templates:
                label = tpl.replace("{n}", str(i) if count > 1 else "")
                out.append(re.sub(r"\s+", " ", label).strip())
    return out


def as_input_rows(state):
    """The channel list as passport input rows.

    Splits "Kick — Beta 52" into source and mic, because the passport's input
    list is structured and the editor's is a line of text. Everything the
    editor does not know - phantom, patch, stagebox, the performer - is left
    empty rather than guessed: an invented patch number on a technical rider is
    worse than a blank one.
    """
    rows = []
    for n, label in enumerate(channel_list(state), start=1):
        parts = _SPLIT.split(label, 1)
        source = parts[0].strip()
        mic = parts[1].strip() if len(parts) > 1 else ""
        rows.append({"channel": str(n), "source": source, "mic_di": mic,
                     "required": 1, "sort": n})
    return rows

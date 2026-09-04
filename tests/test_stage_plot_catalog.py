"""The server's copy of the stage-plot catalogue must match the browser's.

stage_plot_catalog.py mirrors the CATALOG in static/js/stageplot.js so the
Show Passport can import the channel list the editor already derives. Two
copies drift, so this parses the JavaScript and fails when they stop agreeing.

If this test fails, the fix is to update stage_plot_catalog.py to match the
JS - the editor is the source of truth, because it is what the artist actually
drags things around in and what the exported PNG comes from.
"""
import io
import os
import re

import stage_plot_catalog as cat

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(HERE, "static", "js", "stageplot.js")


def _catalog_from_js():
    """Pull key + inputs out of the JS literal. Deliberately narrow: it reads
    the one array it knows about rather than trying to be a JS parser."""
    src = io.open(JS, encoding="utf-8").read()
    block = re.search(r"var CATALOG = \[(.*?)\n  \];", src, re.S)
    assert block, "CATALOG literal not found in stageplot.js"
    body = block.group(1)
    out = []
    for entry in re.finditer(r"\{key:\s*\"([^\"]+)\".*?inputs:\s*\[(.*?)\]\s*\}", body, re.S):
        key = entry.group(1)
        inputs = re.findall(r"\"([^\"]*)\"", entry.group(2))
        out.append((key, inputs))
    return out


def test_the_two_catalogues_agree():
    assert _catalog_from_js() == cat.CATALOG


def test_every_key_is_unique():
    keys = [k for k, _ in cat.CATALOG]
    assert len(keys) == len(set(keys))


# --- deriving the channel list -----------------------------------------------

def test_one_of_a_thing_gets_no_number():
    """A solo guitarist's rider should say "Guitar Amp", not "Guitar Amp 1" -
    the editor does this and the import has to match or the two lists read
    differently for the same stage."""
    chans = cat.channel_list({"items": {"gtr": 1}})
    assert chans == ["Guitar Amp — SM57"]


def test_several_of_a_thing_are_numbered():
    chans = cat.channel_list({"items": {"vox": 3}})
    assert chans == ["Vocal 1 — SM58", "Vocal 2 — SM58", "Vocal 3 — SM58"]


def test_the_catalogue_order_is_the_channel_order():
    """Channel order is not arbitrary on a real desk - drums first, vocals
    later - and it comes from the catalogue order, not from what was dragged
    on first."""
    chans = cat.channel_list({"items": {"vox": 1, "drums": 1, "bass": 1}})
    assert chans[0] == "Kick — Beta 52"
    assert chans[-1] == "Vocal — SM58"
    assert "Bass — DI" in chans


def test_furniture_contributes_no_channels():
    assert cat.channel_list({"items": {"riser": 1, "wedge": 4, "power": 2}}) == []


def test_an_empty_or_broken_plot_is_empty_not_an_error():
    assert cat.channel_list(None) == []
    assert cat.channel_list({}) == []
    assert cat.channel_list({"items": {"drums": "lots"}}) == []


# --- as passport rows --------------------------------------------------------

def test_rows_split_source_from_microphone():
    rows = cat.as_input_rows({"items": {"drums": 1}})
    assert rows[0]["source"] == "Kick" and rows[0]["mic_di"] == "Beta 52"
    assert rows[6]["source"] == "OH R" and rows[6]["mic_di"] == "SM81"


def test_channels_are_numbered_from_one():
    rows = cat.as_input_rows({"items": {"drums": 1, "bass": 1}})
    assert [r["channel"] for r in rows] == [str(i) for i in range(1, 9)]


def test_what_the_editor_cannot_know_is_left_blank():
    """An invented patch number on a technical rider is worse than a blank
    one, so the import fills in only what it actually knows."""
    row = cat.as_input_rows({"items": {"bass": 1}})[0]
    assert "patch" not in row and "stagebox" not in row and "performer" not in row

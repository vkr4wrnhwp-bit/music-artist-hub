"""The Rack — three bugs that shipped, and the structural rules that stop
them coming back.

None of these were caught by a test because none of them are visible in a
single file: two of the three are about what a name means once the whole
IIFE has run, and the third is about the order of two script tags.
"""
import os
import re

import pytest

import app as appmod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "static", "js", "rackdsp.js")
HTML = os.path.join(ROOT, "templates", "rack.html")


def _js():
    return open(JS, encoding="utf-8").read()


def _html():
    return open(HTML, encoding="utf-8").read()


def test_the_saved_rack_is_set_before_the_script_that_reads_it():
    """rackdsp.js does `var saved = window.__savedRack || null` ONCE, at
    load. The template used to set __savedRack on the line AFTER the
    script tag, so it was always undefined and no saved rack ever came
    back — silently, with no error anywhere."""
    js = _js()
    assert "var saved = window.__savedRack || null;" in js, (
        "if this read moves, the ordering rule below needs rechecking")
    html = _html()
    assert html.index("__savedRack") < html.index("rackdsp.js"), (
        "__savedRack must be set BEFORE rackdsp.js loads")


def test_the_dsp_tables_are_not_shadowed_by_the_drawing_tables():
    """rackdsp.js is one IIFE. Declaring `var CABS` twice inside it is one
    binding, not two: the second assignment wins for the whole file. The
    drawing table ({cap,w,h,cones}) overwrote the DSP table
    ({hp,ls,p1,...}), so voiceCabMic read a mic NAME where it wanted a
    filter triple and every cab except Direct threw."""
    js = _js()
    for name in ("CABS", "MICS"):
        n = len(re.findall(r"^\s*var %s\s*=" % name, js, re.M))
        assert n == 1, "%s is declared %d times in one scope" % (name, n)
    # The DSP table is the one that must survive: it carries filter values.
    m = re.search(r"var CABS = \{(.*?)\n  \};", js, re.S)
    assert m and "hp:" in m.group(1) and "lp1:" in m.group(1), (
        "CABS must be the DSP table, not the drawing table")
    m = re.search(r"var MICS = \{(.*?)\n  \};", js, re.S)
    assert m and "presence:" in m.group(1), (
        "MICS must carry filter triples, not display names")
    # The drawing tables still exist, under their own names.
    assert "var CAB_ART = {" in js and "var MIC_LABELS = {" in js


def test_every_module_button_has_a_MOD_KEYS_entry():
    """The A/B compare button reads MOD_KEYS[button.dataset.mod] directly.
    A button whose module is missing from that table throws on click.
    `vlv` — the valve bank — was missing, so Compare was dead on it."""
    js, html = _js(), _html()
    mods = sorted(set(re.findall(r'data-mod="([a-z]+)"', html)))
    assert mods, "no module buttons found — has the template changed?"
    block = re.search(r"var MOD_KEYS = \{(.*?)\};", js, re.S).group(1)
    keys = set(re.findall(r"(\w+):\s*\[", block))
    missing = [m for m in mods if m not in keys]
    assert not missing, "buttons with no MOD_KEYS entry: %s" % missing


def test_every_MOD_KEYS_entry_names_real_state():
    """A MOD_KEYS entry that names a key the state does not have would
    snapshot `undefined` and restore it over a real setting. `vlv` maps to
    `valves`, which is what ensureFx actually creates."""
    js = _js()
    block = re.search(r"var MOD_KEYS = \{(.*?)\};", js, re.S).group(1)
    named = set(re.findall(r'"(\w+)"', block))
    # Every state key a module claims must be written somewhere in the file.
    for key in sorted(named):
        assert re.search(r"\bstate\.%s\b|\bs\.%s\b|\b%s:" % (key, key, key), js), (
            "MOD_KEYS names %r but nothing in the rack sets it" % key)
    assert 'vlv: ["valves"]' in js


def test_the_rack_page_still_renders(flask_app_rack):
    client = flask_app_rack
    page = client.get("/rack")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "rackdsp.js" in html and 'data-mod="vlv"' in html


@pytest.fixture(scope="module")
def flask_app_rack():
    import uuid
    import db as store
    app = appmod.create_app()
    c = app.test_client()
    email = "rack-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Rack User", "email": email, "password": "rack-pass-123"})
    c.post("/login", data={"email": email, "password": "rack-pass-123"})
    return c


def test_undo_is_hooked_at_the_single_choke_point():
    """applyState() is called after every mutation, from nineteen places.
    Hooking history there means a change made from anywhere is captured
    without each caller having to remember to record it."""
    js = _js()
    assert "if (!hist.quiet) histMark(histLabel);" in js
    body = js.split("function applyState()")[1].split("\n  }")[0]
    assert "histMark" in body, "history must be recorded from applyState"


def test_the_history_baseline_is_seeded_at_load_not_lazily():
    """applyState is NOT called during boot, so a lazily-seeded baseline
    consumed the user's first real change as the starting point — and that
    change could then never be undone."""
    js = _js()
    assert "if (hist.prev === null) { hist.prev = snap(); hist.label = \"\"; }" in js


def test_a_history_entry_is_named_for_the_change_it_undoes():
    """An entry means 'this is what it looked like BEFORE label'. Pairing
    the previous state with the previous LABEL named every step after the
    one before it."""
    js = _js()
    push = js.split("hist.past.push(")[1].split(")")[0]
    assert "s: hist.prev" in push and "label: label" in push, push


def test_one_gesture_is_one_history_step():
    """Sixty pointermove events on one knob are one thing the user did.
    Coalescing has to compare against the entry on the STACK, not against
    a field histMark overwrites on every call — that never matched, and a
    single knob drag produced sixty entries."""
    js = _js()
    assert "var top = hist.past[hist.past.length - 1];" in js
    assert "top && top.label === label" in js
    assert "HIST_COALESCE_MS" in js


def test_undo_keys_do_not_steal_the_browsers_undo_in_a_text_field():
    js = _js()
    block = js.split('e.key.toLowerCase() !== "z"')[0]
    assert "isContentEditable" in block and "INPUT|TEXTAREA|SELECT" in block


def test_the_undo_controls_are_on_the_page():
    html = _html()
    for el_id in ("rk-undo", "rk-redo", "rk-hist-btn", "rk-hist-pop", "rk-hist-list", "rk-live"):
        assert 'id="%s"' % el_id in html, el_id
    # The popover lives in a dock pinned to the bottom, so it opens upward.
    assert "bottom: calc(100% + 8px)" in html
    assert 'aria-haspopup="true"' in html and 'aria-expanded="false"' in html


# --- the preset library -------------------------------------------------


def _fresh_client():
    """A signed-in client with its own account, so a test that fills the
    library to its cap cannot bleed into the module-scoped fixture."""
    import uuid
    app = appmod.create_app()
    c = app.test_client()
    email = "racklib-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Lib User", "email": email, "password": "rack-pass-123"})
    c.post("/login", data={"email": email, "password": "rack-pass-123"})
    return c


def test_a_named_rack_survives_a_round_trip():
    c = _fresh_client()
    r = c.post("/rack/library/save",
               json={"name": "Vocal chain", "note": "bright", "data": {"eq": [1, 2], "out": 0.8}})
    assert r.status_code == 200 and r.get_json()["ok"]
    pid = r.get_json()["id"]

    listed = c.get("/rack/library").get_json()
    assert listed["ok"] and len(listed["presets"]) == 1
    assert listed["presets"][0]["name"] == "Vocal chain"
    assert listed["presets"][0]["note"] == "bright"
    # The list is a menu, not the racks themselves: no blob in the index.
    assert "data" not in listed["presets"][0]

    got = c.get("/rack/library/%s" % pid).get_json()
    assert got["ok"] and got["preset"]["data"] == {"eq": [1, 2], "out": 0.8}

    assert c.post("/rack/library/%s/delete" % pid).get_json()["ok"]
    assert c.get("/rack/library").get_json()["presets"] == []


def test_one_artists_racks_are_invisible_to_another():
    """Every query in the store is scoped by user_id. This is the test that
    would have caught the inbox bug, where a table without a user_id meant
    every account read every row."""
    a, b = _fresh_client(), _fresh_client()
    pid = a.post("/rack/library/save",
                 json={"name": "Mine", "data": {"eq": [1]}}).get_json()["id"]

    assert b.get("/rack/library").get_json()["presets"] == []      # not listed
    assert b.get("/rack/library/%s" % pid).status_code == 404      # not readable
    assert b.post("/rack/library/%s/delete" % pid).status_code == 404  # not deletable
    # ...and A still has it after B tried.
    assert len(a.get("/rack/library").get_json()["presets"]) == 1


def test_saving_over_a_name_replaces_it_rather_than_duplicating():
    c = _fresh_client()
    first = c.post("/rack/library/save",
                   json={"name": "Drum bus", "data": {"eq": [1]}}).get_json()["id"]
    again = c.post("/rack/library/save",
                   json={"name": "drum BUS", "data": {"eq": [2]}}).get_json()["id"]
    assert again == first, "same name, case-insensitively, is the same preset"
    presets = c.get("/rack/library").get_json()["presets"]
    assert len(presets) == 1
    assert c.get("/rack/library/%s" % first).get_json()["preset"]["data"] == {"eq": [2]}


def test_the_library_has_a_ceiling_and_says_so():
    import db as store
    c = _fresh_client()
    for i in range(store.MAX_RACK_PRESETS):
        assert c.post("/rack/library/save",
                      json={"name": "rack %d" % i, "data": {"eq": [i]}}).status_code == 200
    over = c.post("/rack/library/save", json={"name": "one too many", "data": {"eq": [0]}})
    assert over.status_code == 409
    assert str(store.MAX_RACK_PRESETS) in over.get_json()["error"]


def test_a_nameless_or_empty_rack_is_refused():
    c = _fresh_client()
    assert c.post("/rack/library/save", json={"name": "  ", "data": {"eq": [1]}}).status_code == 400
    assert c.post("/rack/library/save", json={"name": "ok", "data": {}}).status_code == 400
    assert c.post("/rack/library/save", json={"name": "ok", "data": "not a dict"}).status_code == 400


def test_the_library_is_shut_to_signed_out_visitors():
    """The whole app is login-gated, so these redirect to /login before the
    route's own 401 ever runs. Either answer is fine; what must never happen
    is a 200 with somebody's racks in it."""
    owner = _fresh_client()
    pid = owner.post("/rack/library/save",
                     json={"name": "Secret rack", "data": {"eq": [1]}}).get_json()["id"]

    out = appmod.create_app().test_client()
    for resp in (out.get("/rack/library"),
                 out.post("/rack/library/save", json={"name": "x", "data": {"eq": [1]}}),
                 out.get("/rack/library/%s" % pid),
                 out.post("/rack/library/%s/delete" % pid)):
        assert resp.status_code in (301, 302, 401), resp.status_code
        assert b"Secret rack" not in resp.data

    # The delete attempt did not land.
    assert len(owner.get("/rack/library").get_json()["presets"]) == 1


def test_a_preset_name_is_written_as_text_not_markup():
    """Preset names are user input rendered back into the page. innerHTML
    here would be stored XSS with the artist's own rack as the vector."""
    js = _js()
    start = js.index("function rackLibrary()")
    block = js[start:js.index("})();", start)]
    assert "nm.textContent = pr.name;" in block
    assert ".innerHTML" not in block, "the library must never build markup from a preset name"


def test_the_library_controls_are_on_the_page():
    html = _html()
    for hook in ('id="rk-lib-btn"', 'id="rk-lib-back"', 'id="rk-lib-form"',
                 'id="rk-lib-list"', 'id="rk-lib-name"'):
        assert hook in html, hook
    # It is a real dialog, and the trigger says so.
    assert 'role="dialog"' in html and 'aria-modal="true"' in html
    assert 'aria-controls="rk-lib-back"' in html

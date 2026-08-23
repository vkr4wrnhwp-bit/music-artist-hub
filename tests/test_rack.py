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


# --- the "drop audio" empty state ---------------------------------------


def test_the_empty_state_guides_without_blocking_the_controls():
    """The scrim covers the whole faceplate, so if it swallowed clicks the
    rack would be unusable until audio loaded — and you are meant to be
    able to dial a rack in blind and save it to the library. Only the card
    inside it takes the mouse."""
    html = _html()
    assert 'id="rk-empty"' in html
    css = html[html.index(".rk-empty {"):html.index(".rk-empty-h")]
    assert "pointer-events: none" in css, "the scrim must let clicks through"
    card = html[html.index(".rk-empty-card {"):html.index(".rk-empty-h")]
    assert "pointer-events: auto" in card, "the card itself must be clickable"


def test_the_empty_state_sits_inside_the_chassis():
    """inset:0 only covers the faceplate if it is a child of .chassis,
    which is the positioned ancestor."""
    html = _html()
    chassis = html.index('<div class="chassis">')
    fit_close = html.index("<!-- /chassis-fit -->")
    assert chassis < html.index('id="rk-empty"') < fit_close


def test_the_scrim_lifts_only_after_a_file_actually_decodes():
    """Hiding it on drop would strand anyone who dropped a PDF: the rack
    would look armed and play nothing. hideEmpty() belongs in the resolve
    arm, after decodeAudioData has come back."""
    js = _js()
    start = js.index("function loadFile(file)")
    body = js[start:js.index("fileInput.addEventListener", start)]
    assert "hideEmpty();" in body
    assert body.index("decodeAudioData") < body.index("hideEmpty();")
    # and the catch arm must NOT hide it
    catch = body[body.index(".catch("):]
    assert "hideEmpty" not in catch, "a failed decode must leave the scrim up"


def test_the_drag_highlight_counts_depth_rather_than_toggling():
    """dragenter/dragleave fire for every child element the pointer
    crosses. A bare boolean flickers the whole time you are dragging over
    the rack; a depth counter does not."""
    js = _js()
    assert "var dragDepth = 0;" in js
    assert "dragDepth++" in js
    assert "dragDepth = Math.max(0, dragDepth - 1);" in js
    # the drop handler resets it, or the next drag starts already-counted
    start = js.index('document.addEventListener("drop"')
    drop = js[start:js.index("var stems", start)]
    assert "dragDepth = 0;" in drop


def test_the_empty_state_button_opens_the_real_file_picker():
    """A second <input type=file> would be a second load path to keep in
    step. This one points at the input that already exists."""
    html = _html()
    card = html[html.index('id="rk-empty"'):html.index("<!-- /chassis-fit -->")]
    assert 'for="rk-file"' in card
    assert "<input" not in card, "no second file input — reuse rk-file"


# --- per-module level meters --------------------------------------------


def _meter_taps():
    js = _js()
    body = js[js.index("function meterTaps"):js.index("function buildMeters")]
    return set(re.findall(r"([a-z]+):\s*ch\.", body))


def test_every_module_has_a_meter_tap_and_a_bar():
    """Three lists have to agree or a module quietly has no meter: the
    modules the rack knows about, the tap points, and the bars on the
    faceplate. Adding a module to MOD_KEYS without a tap is the silent
    failure this catches."""
    js = _js()
    modkeys = set(re.findall(r"([a-z]+):\s*\[",
                             js[js.index("var MOD_KEYS"):js.index("function modSlice")]))
    bars = set(re.findall(r'class="rk-lvl" data-mod="([a-z]+)"', _html()))
    taps = _meter_taps()
    assert taps == modkeys, "tap points and MOD_KEYS disagree: %s" % (taps ^ modkeys)
    assert bars == modkeys, "faceplate bars and MOD_KEYS disagree: %s" % (bars ^ modkeys)


def test_the_time_based_effects_meter_their_wet_send():
    """The fx bus carries the dry signal too, so metering fx.outNode reads
    hot with delay and reverb both at zero — it would say the effect is
    working when it is doing nothing. The wet send reads 0 when the effect
    is off and rises as it comes in. Measured: 0.000 off, 0.430 at 60% mix."""
    taps = _js()[_js().index("function meterTaps"):_js().index("function buildMeters")]
    assert "dly: ch.fx.dWet" in taps
    assert "rev: ch.fx.rWet" in taps
    assert "fx.outNode" not in taps, "metering the bus tells you nothing about the effect"


def test_a_meter_is_a_tap_and_never_a_link_in_the_chain():
    """An analyser inserted INTO the path would still pass audio, so this
    would not be audible — it would just silently add nine nodes of
    latency and a second reference to every module output."""
    js = _js()
    body = js[js.index("function buildMeters"):js.index("var lvlEls")]
    assert "taps[k].connect(a);" in body, "the module output feeds the analyser"
    assert "a.connect(" not in body, "an analyser must not feed anything onward"


def test_the_meter_falls_slower_than_it_rises():
    """A meter with a symmetric envelope is a strobe on any material with
    transients. Rise is instant so peaks are not missed; the fall is
    smoothed."""
    js = _js()
    assert "m.peak = peak > m.peak ? peak : m.peak * 0.86 + peak * 0.14;" in js


def test_buildchain_hands_back_the_bus_the_tube_meter_needs():
    """The tube stage sums its wet and dry legs into a node that used to
    be local to buildChain. Without it returned there is nowhere to tap
    the tube's real output."""
    js = _js()
    ret = js[js.index("return {input: input, filters: filters"):]
    ret = ret[:ret.index("}")]
    assert "sum: sum" in ret


def test_the_meters_are_painted_from_the_animation_loop():
    js = _js()
    draw = js[js.index("function draw() {"):]
    assert "paintMeters();" in draw[:400], "meters must repaint every frame"


# --- what the rack costs ------------------------------------------------


def _cost_js():
    js = _js()
    return js[js.index("var COST_SECONDS"):js.index("function renderMaster()")]


def test_the_cost_readout_never_claims_to_be_a_cpu_meter():
    """Web Audio exposes no DSP load. A percentage here would be a
    decoration shaped like an instrument, which is worse than showing
    nothing. What is reported is a timed render, and the wording has to
    keep saying so."""
    js = _cost_js()
    assert "realtime" in js, "the unit is a speed, not a load"
    assert "not a CPU reading" in js
    for lie in ("cpu%", "CPU%", "DSP load", "dspLoad", "cpuLoad"):
        assert lie not in js, "do not claim a reading the browser does not give: %s" % lie


def test_the_cost_is_measured_through_the_same_chain_the_export_uses():
    """Measuring a hand-rolled approximation of the rack would drift from
    the rack. buildChain + voiceChain is the one description of the
    signal path, and renderMasterBuffer uses the same pair."""
    js = _cost_js()
    assert "buildChain(oc, oc.destination)" in js
    assert "voiceChain(chain, oc)" in js
    assert "startRendering()" in js
    assert "performance.now()" in js, "it has to be timed, not estimated"


def test_the_cost_probe_is_fed_signal_not_silence():
    """A chain fed zeros does not exercise the waveshaper curve and gives
    the compressor nothing to do, so silence would time a rack that is not
    the one being listened to."""
    js = _cost_js()
    assert "costNoiseBuf" in js
    body = js[js.index("function costSource"):js.index("function measureCost")]
    assert "getChannelData(0)" in body
    assert "1103515245" in body, "a fixed generator, so two runs are comparable"


def test_the_cost_is_measured_once_and_not_on_every_knob_turn():
    """It began as a per-change meter. Measured, idle, six alternating
    samples at a three-second render: a 0.3s reverb tail cost 205 ms per
    second of audio and a 3.0s tail cost 180 ms — the larger one FASTER,
    with more spread inside each setting than between them. The graph's
    cost does not track its settings, so re-rendering on every change was
    burning real CPU to report a number that never moved."""
    js = _js()
    assert "scheduleCost" not in js, "no debounced re-measure: there is nothing to re-measure"
    a0 = js.index("function applyState()")
    apply_body = js[a0:js.index("function ", a0 + 10)]
    assert "measureCost" not in apply_body, "a knob turn must not trigger a render"
    assert "measureCost();" in js, "but it must be measured once, at load"
    assert "costBusy" in _cost_js(), "and never started twice at once"


def test_the_readout_answers_the_question_the_number_can_answer():
    """A render speed on its own is trivia. With a track loaded the same
    measurement answers something real — how long the bounce takes — so
    that is what it says, and it uses that track's own length."""
    js = _cost_js()
    assert 'el.textContent = "export ~" + fmtDur(dur / costFactor);' in js
    assert "buffer ? buffer.duration : 0" in js
    assert "s.buffer.duration" in js, "stems have their own length"


def test_the_heavy_threshold_means_something():
    """The first threshold was a guess at x8, taken from readings on a
    machine running a full test suite. Idle it reads about x5, so that
    guess would have cried wolf permanently. Below x1 is the line that
    means something: the export takes longer than the song."""
    assert "el.classList.toggle(\"is-heavy\", costFactor < 1);" in _cost_js()


def test_the_cost_readout_is_on_the_page_and_not_announced():
    """The number changes every time the rack settles. Announcing that to
    a screen reader would be a tic, so it is a status region that does not
    interrupt."""
    html = _html()
    assert 'id="rk-cost"' in html
    assert 'aria-live="off"' in html

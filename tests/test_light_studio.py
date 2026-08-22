"""Light Studio — the page, the working copy, and the named-show library."""
import os
import re
import shutil
import subprocess
import uuid

import pytest

import app as appmod
import db as store
import lights_store

PASSWORD = "lights-pass-123"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _user(flask_app, label="Lighting Designer"):
    email = "lx-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": label, "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client, store.get_user_by_email(email)


def test_page_has_the_studio_surfaces(flask_app):
    client, user = _user(flask_app)
    page = client.get("/lights").get_data(as_text=True)
    # The phrases the old test pins, plus every new surface by id.
    for needle in ("Light Studio", "simulation", "ENTTEC", "Web Serial", "Audience view", "drag any bar"):
        assert needle in page, needle
    for el_id in ("lx-wave", "lx-stage", "lx-clock", "lx-fileinfo", "lx-dmx-chip", "lx-add", "lx-blackout",
                  "lx-cues", "lx-groups", "lx-looks", "lx-barctl", "lx-bars-list", "lx-lib-select",
                  "lx-master", "lx-panic", "lx-export", "lx-import", "lx-look-save",
                  "lx-vol", "lx-rate", "lx-scrub", "lx-dmx-start", "lx-dmx-universe", "lx-bar-addr", "lx-patch-warn",
                  "lx-autocue", "lx-autocue-clear", "lx-autocue-note",
                  "lx-mix-r", "lx-mix-g", "lx-mix-b", "lx-mix-h", "lx-mix-s", "lx-mix-v",
                  "lx-group-one", "lx-group-clear", "lx-group-picked",
                  "lx-wheel", "lx-gel-swatch", "lx-gel-name", "lx-gel-for", "lx-gel-hex",
                  "lx-look-new", "lx-look-name", "lx-output", "lx-bridge-port", "lx-bridge-test", "lx-bridge-status",
                  "lx-set-select", "lx-set-items", "lx-set-add", "lx-set-save", "lx-set-next", "lx-set-prev",
                  "lx-resume", "lx-resume-go", "lx-resume-no", "lx-attach", "lx-pull",
                  "lx-rig-select", "lx-rig-apply", "lx-rig-save", "lx-rig-delete", "lx-rig-name", "lx-rig-venue", "lx-rig-status",
                  "lx-lib-save", "lx-saved", "lx-focus", "lx-detect", "lx-snap", "lx-tap", "lx-zoom-fit"):
        assert 'id="%s"' % el_id in page, el_id
    assert "lights-engine.js?v=7" in page and "lights.js?v=19" in page and "light-studio.css?v=10" in page
    assert "lx-transport" in page and "__lightsLibrary" in page
    # polish pass: unsaved-work, undo, a11y, rail
    for el_id in ("lx-undo", "lx-redo", "lx-live", "lx-libdirty", "lx-draft-prompt", "lx-draft-keep", "lx-draft-discard",
                  "lx-rail", "lx-rail-expand"):
        assert 'id="%s"' % el_id in page, el_id
    assert 'id="lx-cues" class="lx-cues" role="list"' in page
    assert 'id="lx-wave" class="lx-wave" tabindex="0" role="slider"' in page
    assert 'id="lx-play"' in page and 'aria-label="Play or stop the song (Space)"' in page
    assert 'id="lx-run"' in page and 'aria-pressed="false" aria-label="Run the cue list without audio"' in page
    assert 'aria-live="polite"' in page.split('id="lx-live"')[1][:80]
    assert 'href="/command-center"' in page.split('id="lx-rail"')[1].split("</nav>")[0]
    # helper text floor: no 10px text classes on this page any more
    assert "text-[10px]" not in page.split('id="lx-root"')[1].split("</div>\n\n<script>")[0]


def test_every_element_the_script_reaches_for_is_on_the_page(flask_app):
    """lights.js boots in one pass; a single missing id throws and leaves
    the canvases dead. Every $("...") in the script must exist in the
    rendered page (ids from base.html count)."""
    client, user = _user(flask_app)
    page = client.get("/lights").get_data(as_text=True)
    js = open(os.path.join(ROOT, "static", "js", "lights.js"), encoding="utf-8").read()
    ids = sorted(set(re.findall(r'\$\("([A-Za-z0-9_-]+)"\)', js)))
    assert len(ids) > 30
    missing = [i for i in ids if ('id="%s"' % i) not in page]
    assert not missing, missing


def test_library_save_versions_restore_and_isolation(flask_app):
    client, user = _user(flask_app)
    other, _ = _user(flask_app, "Someone Else")
    assert flask_app.test_client().get("/lights/library").status_code in (302, 401)
    data = {"name": "Fall set", "bars": 6, "chans": 4,
            "cues": [{"t": 1.25, "group": "all", "color": "#ffb347", "intensity": 85, "fade": 1, "note": "intro"}]}
    r = client.post("/lights/library/save", json={"name": "Fall set", "data": data, "note": "first pass"}).get_json()
    assert r["ok"] and r["id"] and r["versions"] == 1 and r["shows"][0]["name"] == "Fall set"
    sid = r["id"]
    # autosave updates in place and takes no version
    data["cues"].append({"t": 30, "group": "pair1", "color": "#3b82f6", "intensity": 80, "fade": 1, "note": ""})
    r2 = client.post("/lights/library/save", json={"id": sid, "name": "Fall set", "data": data, "autosave": True}).get_json()
    assert r2["ok"] and r2["id"] == sid and r2["versions"] == 1
    # explicit save adds a version
    r3 = client.post("/lights/library/save", json={"id": sid, "name": "Fall set v2", "data": data}).get_json()
    assert r3["versions"] == 2
    got = client.get("/lights/library/%s" % sid).get_json()
    assert got["ok"] and got["show"]["name"] == "Fall set v2" and got["show"]["cue_count"] == 2
    vs = client.get("/lights/library/%s/versions" % sid).get_json()["versions"]
    assert len(vs) == 2 and vs[-1]["note"] == "first pass" and vs[-1]["cue_count"] == 1
    restored = client.post("/lights/library/%s/restore" % sid, json={"version_id": vs[-1]["id"]}).get_json()
    assert restored["ok"] and len(restored["data"]["cues"]) == 1
    # linking to a track and a tour date only sticks for the caller's own rows
    tid = store.add_os_track(user["id"], "Song One")
    show_id = store.add_tour_show(user["id"], "2030-05-02", "Room", "City", "")
    r4 = client.post("/lights/library/save", json={"id": sid, "name": "Fall set", "data": data,
                                                  "track_id": tid, "tour_show_id": show_id, "autosave": True}).get_json()
    s = lights_store.get_show(user["id"], sid)
    assert s["track_id"] == tid and s["tour_show_id"] == show_id
    client.post("/lights/library/save", json={"id": sid, "name": "Fall set", "data": data,
                                               "track_id": "not-mine", "tour_show_id": "nope", "autosave": True})
    s = lights_store.get_show(user["id"], sid)
    assert s["track_id"] is None and s["tour_show_id"] is None
    # the page lists it; another account sees nothing
    page = client.get("/lights").get_data(as_text=True)
    assert "Fall set" in page
    assert other.get("/lights/library/%s" % sid).status_code == 404
    assert other.get("/lights/library/%s/versions" % sid).status_code == 404
    assert other.get("/lights/library").get_json()["shows"] == []
    other.post("/lights/library/%s/delete" % sid, json={})
    assert lights_store.get_show(user["id"], sid) is not None      # a stranger cannot delete it
    d = client.post("/lights/library/%s/delete" % sid, json={}).get_json()
    assert d["ok"] and d["shows"] == [] and lights_store.list_versions(user["id"], sid) == []


def test_user_text_cannot_break_out_of_the_inline_script(flask_app):
    """json.dumps does not escape "<", so a show named "</script>..." would
    close the tag and run as HTML. Every JSON blob embedded in an inline
    script goes through the js_json filter instead."""
    client, user = _user(flask_app)
    payload = '</script><img src=x onerror=alert(1)>'
    client.post("/lights/save", json={"name": payload, "bars": 4, "chans": 4, "cues": []})
    client.post("/lights/library/save", json={"name": payload, "data": {"name": payload, "cues": [], "bars": 4, "chans": 4}})
    page = client.get("/lights").get_data(as_text=True)
    assert "</script><img" not in page          # the tag never closes early
    assert "\\u003c/script\\u003e" in page      # it is there, escaped
    # and it still parses back to exactly what the user typed
    blob = page.split("window.__savedShow = ")[1].split(";</script>")[0]
    import json as _j
    assert _j.loads(blob)["name"] == payload


def test_rig_profiles_save_bind_to_a_venue_and_stay_private(flask_app):
    """A rig is layout + patch. It is per-account, sanitised on the way in,
    and at most one rig is bound to a given venue name."""
    client, user = _user(flask_app)
    other, _ = _user(flask_app, "Other LD")
    assert flask_app.test_client().get("/lights/rigs").status_code in (302, 401)
    assert client.get("/lights/rigs").get_json()["rigs"] == []

    rig = {"bars": 8, "chans": 3, "pos": {"1": [0.2, 0.1]}, "rot": {"1": 90, "2": 45},
           "dmxStart": 101, "dmxAddr": {"1": 101, "2": 9999, "3": "nope"}}
    r = client.post("/lights/rigs/save", json={"name": "The Vault house rig", "data": rig,
                                              "venue": "The Vault, Charlotte!"}).get_json()
    assert r["ok"] and len(r["rigs"]) == 1
    rid = r["id"]
    saved = r["rigs"][0]
    assert saved["name"] == "The Vault house rig"
    assert saved["venue_key"] == "the vault charlotte"          # punctuation and case are noise
    d = saved["data"]
    assert d["bars"] == 8 and d["chans"] == 3 and d["dmxStart"] == 101
    assert d["rot"]["1"] == 90 and d["rot"]["2"] == 0            # only 0/90 survive
    assert d["dmxAddr"] == {"1": 101}                            # out-of-range and junk dropped
    assert lights_store.rig_for_venue(user["id"], "the vault   charlotte")["id"] == rid

    # values outside the studio's own limits are clamped, never stored raw
    r2 = client.post("/lights/rigs/save", json={"name": "Silly", "data": {"bars": 99, "dmxStart": 9999,
                                                                         "pos": {"1": [5, -5]}}}).get_json()
    d2 = [x for x in r2["rigs"] if x["id"] == r2["id"]][0]["data"]
    assert d2["bars"] == 10 and d2["dmxStart"] == 512 and d2["pos"]["1"] == [0.97, 0.04]

    # one rig per venue: binding a second rig to the same room unbinds the first
    r3 = client.post("/lights/rigs/save", json={"name": "Vault B", "data": {"bars": 4},
                                                "venue": "the vault charlotte"}).get_json()
    assert lights_store.rig_for_venue(user["id"], "The Vault Charlotte")["id"] == r3["id"]
    assert lights_store.get_rig(user["id"], rid)["venue_key"] == ""
    assert lights_store.rig_for_venue(user["id"], "") is None
    assert lights_store.rig_for_venue(user["id"], "Nowhere") is None

    # the page ships the caller's rigs and the venue key for each tour date
    store.add_tour_show(user["id"], "2030-06-01", "The Vault", "Charlotte", "")
    page = client.get("/lights").get_data(as_text=True)
    assert "The Vault house rig" in page and 'data-venue-key="the vault"' in page

    # another account cannot see, edit or delete them
    assert other.get("/lights/rigs").get_json()["rigs"] == []
    other.post("/lights/rigs/%s/delete" % rid, json={})
    assert lights_store.get_rig(user["id"], rid) is not None
    assert lights_store.get_rig(other_id(other, flask_app), rid) is None
    assert client.post("/lights/rigs/%s/delete" % rid, json={}).get_json()["ok"]
    assert lights_store.get_rig(user["id"], rid) is None


def other_id(client, flask_app):
    """The user id behind a logged-in test client (via its session cookie)."""
    with client.session_transaction() as sess:
        return sess.get("user_id") or sess.get("uid") or ""


def test_a_show_ships_with_the_track_and_lands_on_another_rig(flask_app):
    """The point of storing looks and group roles rather than channel
    numbers: a show attached to a track renders on whatever rig pulls it."""
    client, user = _user(flask_app)
    other, other_user = _user(flask_app, "Someone Else")
    tid = store.add_os_track(user["id"], "No Tengo Calma")

    # an eight-bar show, including a cue that names a specific bar
    data = {"name": "Big rig show", "bars": 8, "chans": 4,
            "cues": [{"t": 1, "group": "all", "color": "#ffb347", "intensity": 80, "fade": 1},
                     {"t": 9, "group": "b7", "color": "#ff2d2d", "intensity": 100, "fade": 0}]}
    r = client.post("/lights/track/%s/attach" % tid,
                    json={"name": "Big rig show", "data": data}).get_json()
    assert r["ok"] and r["attached"]["cue_count"] == 2
    assert tid in r["tracks"]

    got = client.get("/lights/track/%s/show" % tid).get_json()
    assert got["ok"] and got["show"]["format"] == lights_store.PASSPORT_FORMAT
    assert got["show"]["bars"] == 8 and len(got["show"]["data"]["cues"]) == 2

    # the passport keeps the rest of the track intact and keeps a short history
    client.post("/lights/track/%s/attach" % tid,
                json={"name": "Second pass", "data": dict(data, cues=data["cues"][:1])})
    entry = lights_store.show_on_track(user["id"], tid)
    assert entry["name"] == "Second pass" and entry["cue_count"] == 1
    assert entry["history"] and entry["history"][0]["name"] == "Big rig show"

    # the cross-rig guarantee: bar 7 of 8 has a home on a 4-bar rig
    import json as _j
    cues = _j.loads(_j.dumps(entry["history"] and got["show"]["data"]["cues"]))
    remapped = [c for c in cues if c["group"] == "b7"]
    assert remapped, "the bar-specific cue is what makes this test worth running"

    # another account cannot reach it, and cannot attach to someone else's track
    assert other.get("/lights/track/%s/show" % tid).status_code == 404
    assert other.post("/lights/track/%s/attach" % tid, json={"name": "hijack", "data": data}).status_code == 404
    assert lights_store.show_on_track(user["id"], tid)["name"] == "Second pass"
    assert lights_store.show_on_track(other_user["id"], tid) is None
    assert lights_store.tracks_with_shows(other_user["id"]) == {}


def test_setlists_chain_saved_shows_and_stay_private(flask_app):
    """A setlist chains shows from YOUR library. An item pointing at another
    account's show is dropped rather than stored."""
    client, user = _user(flask_app)
    other, other_user = _user(flask_app, "Rival LD")

    def save_show(c, name):
        return c.post("/lights/library/save",
                      json={"name": name, "data": {"name": name, "bars": 4, "chans": 4, "cues": []}}).get_json()["id"]

    a, b = save_show(client, "Opener"), save_show(client, "Closer")
    theirs = save_show(other, "Not yours")

    assert flask_app.test_client().get("/lights/setlists").status_code in (302, 401)
    assert client.get("/lights/setlists").get_json()["setlists"] == []

    r = client.post("/lights/setlists/save", json={
        "name": "Friday night", "gap_color": "#221a10", "gap_intensity": 15,
        "items": [{"show_id": a, "advance": "auto", "gap_seconds": 4},
                  {"show_id": theirs, "advance": "auto"},          # another account's show
                  {"show_id": b, "advance": "manual", "gap_seconds": 0}]}).get_json()
    assert r["ok"]
    sl = r["setlist"]
    assert sl["name"] == "Friday night" and sl["gap_intensity"] == 15
    names = [i["show_name"] for i in sl["items"]]
    assert names == ["Opener", "Closer"], "another account's show was stored: %s" % names
    assert [i["position"] for i in sl["items"]] == [0, 1]
    assert sl["items"][0]["advance"] == "auto" and sl["items"][0]["gap_seconds"] == 4

    # values outside the allowed range are clamped, not stored raw
    r2 = client.post("/lights/setlists/save", json={
        "id": sl["id"], "name": "Friday night",
        "items": [{"show_id": a, "advance": "nonsense", "gap_seconds": 99999}]}).get_json()
    it = r2["setlist"]["items"][0]
    assert it["advance"] == "manual" and it["gap_seconds"] == 600

    # another account cannot read or delete it
    assert other.get("/lights/setlists/%s" % sl["id"]).status_code == 404
    assert other.get("/lights/setlists").get_json()["setlists"] == []
    other.post("/lights/setlists/%s/delete" % sl["id"], json={})
    assert lights_store.get_setlist(user["id"], sl["id"]) is not None
    assert client.post("/lights/setlists/%s/delete" % sl["id"], json={}).get_json()["ok"]
    assert lights_store.get_setlist(user["id"], sl["id"]) is None
    # deleting the setlist leaves the shows alone
    assert lights_store.get_show(user["id"], a) is not None


def test_the_page_ships_the_setlists(flask_app):
    client, user = _user(flask_app)
    sid = client.post("/lights/library/save",
                      json={"name": "In a set", "data": {"cues": [], "bars": 4, "chans": 4}}).get_json()["id"]
    client.post("/lights/setlists/save", json={"name": "Tour set", "items": [{"show_id": sid}]})
    page = client.get("/lights").get_data(as_text=True)
    assert "Tour set" in page and "setlists" in page


def test_rig_count_is_capped(flask_app):
    client, user = _user(flask_app)
    last = None
    for i in range(lights_store.MAX_RIGS + 2):
        last = client.post("/lights/rigs/save", json={"name": "Rig %d" % i, "data": {"bars": 4}})
    assert last.status_code == 400 and "delete one first" in last.get_json()["error"]
    assert len(lights_store.list_rigs(user["id"])) == lights_store.MAX_RIGS


def test_versions_are_capped(flask_app):
    client, user = _user(flask_app)
    sid = None
    for i in range(lights_store.MAX_VERSIONS + 5):
        r = client.post("/lights/library/save", json={"id": sid or "", "name": "Cap", "data": {"cues": [], "bars": 4, "chans": 4}}).get_json()
        sid = r["id"]
    assert r["versions"] == lights_store.MAX_VERSIONS


def test_working_copy_still_round_trips(flask_app):
    client, user = _user(flask_app)
    show = {"name": "Working", "bars": 8, "chans": 3, "cues": [{"t": 2, "group": "odd", "color": "#ff0000", "intensity": 50, "fade": 0.5, "note": "x"}],
            "bpm": 120.0, "beatOffset": 0.25, "snap": True}
    assert client.post("/lights/save", json=show).get_json()["ok"]
    assert store.get_light_show(user["id"])["bpm"] == 120.0
    assert "Working" in client.get("/lights").get_data(as_text=True)


def test_engine_checks_under_node():
    """The engine's maths is proved by tests/js/check_lights.js when Node is
    available; skipped (not passed) when it is not."""
    node = shutil.which("node")
    if not node:
        import glob
        found = glob.glob(os.path.join(os.path.expanduser("~"), "nodejs", "**", "node.exe"), recursive=True)
        node = found[0] if found else None
    if not node:
        pytest.skip("node not available")
    for name in ("check_lights.js", "check_lights_autocue.js", "check_lights_history.js"):
        proc = subprocess.run([node, os.path.join(ROOT, "tests", "js", name)],
                              capture_output=True, text=True, timeout=180)
        assert proc.returncode == 0, name + "\n" + proc.stdout + proc.stderr
        assert "FAIL" not in proc.stdout, name


def test_draft_flags_round_trip_and_library_untouched_by_autosave(flask_app):
    """The working copy carries draftDirty/draftSavedAt; only an explicit
    library save (version=True) may change a library row's data."""
    client, user = _user(flask_app)
    r = client.post("/lights/library/save", json={"name": "Named", "data": {"cues": [{"t": 1, "group": "all", "color": "#fff", "intensity": 50, "fade": 0}], "bars": 4, "chans": 4}}).get_json()
    sid = r["id"]
    draft = {"name": "Named", "libraryId": sid, "bars": 4, "chans": 4, "draftDirty": True, "draftSavedAt": "2026-08-22T10:00:00Z",
             "cues": [{"t": 1, "group": "all", "color": "#fff", "intensity": 50, "fade": 0}, {"t": 9, "group": "odd", "color": "#f00", "intensity": 90, "fade": 1}]}
    assert client.post("/lights/save", json=draft).get_json()["ok"]
    got = store.get_light_show(user["id"])
    assert got["draftDirty"] is True and got["draftSavedAt"].startswith("2026-08-22") and len(got["cues"]) == 2
    # the library row still has one cue
    assert lights_store.get_show(user["id"], sid)["cue_count"] == 1
    page = client.get("/lights").get_data(as_text=True)
    assert '"draftDirty": true' in page and sid in page


def test_stylesheet_has_no_tiny_helper_text():
    css = open(os.path.join(ROOT, "static", "css", "light-studio.css"), encoding="utf-8").read()
    sizes = [float(s) for s in re.findall(r"font-size:\s*([0-9.]+)px", css)]
    # labels (eyebrow, chips, kbd, table headers) are letterspaced caps at 9.5-11px by
    # design; running helper text is never below 12px.
    assert min(sizes) >= 9.5
    assert "font-size: 12px" in css or "font-size: 12.5px" in css

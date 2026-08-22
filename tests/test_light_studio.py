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
                  "lx-cues", "lx-groups", "lx-looks", "lx-barctl", "lx-bars-tbody", "lx-lib-select",
                  "lx-lib-save", "lx-saved", "lx-focus", "lx-detect", "lx-snap", "lx-tap", "lx-zoom-fit"):
        assert 'id="%s"' % el_id in page, el_id
    assert "lights-engine.js?v=2" in page and "lights.js?v=8" in page and "light-studio.css?v=3" in page
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

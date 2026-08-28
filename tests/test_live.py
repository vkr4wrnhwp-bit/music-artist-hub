# -*- coding: utf-8 -*-
"""Street Banker Live - the set, and the contract with the engine.

Live Lab was built inside the MASTERCLIP OS repository and never merged. Its
engine came across unchanged as `static/js/livelab.js`; this half is new. The
seam between them is `live_store.set_manifest()`, and it is a real contract:
the engine validates the project with zod when it loads it, so a field renamed
on this side is not a cosmetic problem - it is a set that refuses to open, and
the place that gets discovered is a venue.

So the manifest is tested twice. Here, that the function still emits the
agreed shape; and in tests/js/check_livelab.js, that the real engine still
accepts it. Either half moving alone fails one of them.
"""
import os
import shutil
import subprocess
import uuid

import pytest

import live_store as lstore

NODE = os.environ.get("SB_NODE_BIN") or shutil.which("node") or shutil.which("node.exe")
CHECK = os.path.join(os.path.dirname(__file__), "js", "check_livelab.js")

needs_node = pytest.mark.skipif(
    not NODE,
    reason="node is not on PATH; set SB_NODE_BIN to point at a binary")


@pytest.fixture(scope="module")
def application():
    os.environ["LIVE_LAB_ENABLED"] = "1"
    import app as appmod
    return appmod.app


@pytest.fixture(scope="module", autouse=True)
def _restore_flag():
    saved = os.environ.get("LIVE_LAB_ENABLED")
    yield
    if saved is None:
        os.environ.pop("LIVE_LAB_ENABLED", None)
    else:
        os.environ["LIVE_LAB_ENABLED"] = saved


def _artist(application, label="rig"):
    email = "lv-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": label.title(), "email": email,
                                 "password": "lv-pass-123"})
    client.post("/login", data={"email": email, "password": "lv-pass-123"})
    import db as store
    with application.app_context():
        return client, store.get_user_by_email(email)


@pytest.fixture
def rig(application):
    client, user = _artist(application)
    response = client.post("/live/new", data={
        "name": "Friday headline", "venue": "The Ritz", "tempo_bpm": "128"})
    set_id = response.headers["Location"].rstrip("/").split("/")[-1]
    client.post("/live/%s/scene" % set_id,
                data={"name": "Intro", "quantization": "1bar",
                      "follow_action": "next_scene"})
    client.post("/live/%s/scene" % set_id,
                data={"name": "Drop", "quantization": "4bars",
                      "follow_action": "stop"})
    return {"client": client, "user": user, "set_id": set_id}


# --- the flag ----------------------------------------------------------------

def test_live_is_on_unless_a_deployment_turns_it_off():
    """It was off by default and the owner could not find his own stage rig.
    An unset variable now means on; LIVE_LAB_ENABLED=0 still switches it off."""
    import live

    saved = os.environ.get("LIVE_LAB_ENABLED")
    try:
        os.environ.pop("LIVE_LAB_ENABLED", None)
        assert live.enabled()
        os.environ["LIVE_LAB_ENABLED"] = "0"
        assert not live.enabled()
    finally:
        if saved is None:
            os.environ.pop("LIVE_LAB_ENABLED", None)
        else:
            os.environ["LIVE_LAB_ENABLED"] = saved


def test_every_route_is_absent_while_the_section_is_locked(application, rig):
    os.environ["LIVE_LAB_ENABLED"] = "0"
    try:
        for path in ("/live", "/live/%s" % rig["set_id"],
                     "/live/%s/perform" % rig["set_id"],
                     "/live/%s/manifest.json" % rig["set_id"]):
            assert rig["client"].get(path).status_code == 404, path
    finally:
        os.environ["LIVE_LAB_ENABLED"] = "1"


def test_the_sidebar_entry_follows_the_flag(application, rig):
    body = rig["client"].get("/overview").get_data(as_text=True)
    assert 'href="/live"' in body

    os.environ["LIVE_LAB_ENABLED"] = "0"
    try:
        assert 'href="/live"' not in rig["client"].get("/overview").get_data(as_text=True)
    finally:
        os.environ["LIVE_LAB_ENABLED"] = "1"


def test_live_is_gated_at_the_same_tier_as_the_rack():
    """It is the same kind of thing - an artist's own audio, in the browser -
    so it unlocks with the Rack and the Vault rather than on its own rule."""
    import plans

    assert plans.required_tier("/live") == "artist"
    assert plans.required_tier("/rack") == "artist"


# --- tenancy -----------------------------------------------------------------

def test_another_account_cannot_open_the_set(application, rig):
    other_client, _other = _artist(application, "stranger")
    assert other_client.get("/live/%s" % rig["set_id"]).status_code == 404
    assert other_client.get(
        "/live/%s/manifest.json" % rig["set_id"]).status_code == 404


def test_another_account_cannot_read_the_set_through_the_store(application, rig):
    _other_client, other = _artist(application, "stranger")
    with application.app_context():
        assert lstore.get_set(None, other["id"], rig["set_id"]) is None
        assert lstore.list_sets(None, other["id"]) == []
        assert lstore.get_set(None, rig["user"]["id"], rig["set_id"]) is not None


def test_another_account_cannot_add_a_scene(application, rig):
    other_client, _other = _artist(application, "stranger")
    response = other_client.post("/live/%s/scene" % rig["set_id"],
                                 data={"name": "Theirs"})
    assert response.status_code == 404
    with application.app_context():
        names = [s["name"] for s in
                 lstore.list_scenes(None, rig["user"]["id"], rig["set_id"])]
    assert "Theirs" not in names


# --- MIDI --------------------------------------------------------------------

def test_the_same_control_cannot_be_mapped_twice(application, rig):
    """A duplicate behaves according to whichever mapping is checked first,
    which is not behaviour anybody chose. The engine's Learn refuses one; this
    is the same rule for a mapping that arrives by form post."""
    for target in ("scene_launch", "panic"):
        rig["client"].post("/live/%s/midi" % rig["set_id"],
                           data={"label": "Pad 1", "channel": "0",
                                 "data1": "60", "target": target})
    with application.app_context():
        maps = lstore.list_mappings(None, rig["user"]["id"], rig["set_id"])
    assert len(maps) == 1
    assert maps[0]["target"] == "scene_launch"


def test_an_unknown_target_is_refused_rather_than_stored(application, rig):
    """A mapping that resolves to nothing is a dead pad somebody hits on stage
    while nothing happens."""
    with application.app_context():
        assert lstore.add_mapping(None, rig["user"]["id"], rig["set_id"],
                                  "Bad", "note_on", 0, 61,
                                  "launch_the_confetti") is None
        assert lstore.add_mapping(None, rig["user"]["id"], rig["set_id"],
                                  "Good", "note_on", 0, 62,
                                  "scene_launch") is not None


# --- vocabulary --------------------------------------------------------------

def test_a_value_the_engine_would_reject_is_corrected_on_the_way_in(application, rig):
    """The engine validates with zod on load. An unknown follow action is not
    a cosmetic problem - it is a set that will not open."""
    with application.app_context():
        scene_id = lstore.add_scene(None, rig["user"]["id"], rig["set_id"],
                                    "Odd", follow_action="explode",
                                    quantization="whenever",
                                    scene_type="interpretive_dance")
        scene = [s for s in lstore.list_scenes(None, rig["user"]["id"],
                                               rig["set_id"])
                 if s["id"] == scene_id][0]
    assert scene["follow_action"] in lstore.FOLLOW_ACTIONS
    assert scene["quantization"] in lstore.QUANTIZATIONS
    assert scene["scene_type"] in lstore.SCENE_TYPES


def test_the_vocabulary_matches_the_engines_own_enums():
    """Copied from packages/performance-project/src/types.ts. If the engine is
    rebundled with different values, tests/js/check_livelab.js fails first."""
    assert lstore.FOLLOW_ACTIONS == ("stop", "loop", "next_scene", "target")
    assert lstore.QUANTIZATIONS == ("none", "1/4", "1/2", "1bar", "2bars",
                                    "4bars", "scene_end")
    assert lstore.STEM_TYPES == ("vocal", "drums", "bass", "music", "fx",
                                 "click", "custom")


# --- the manifest ------------------------------------------------------------

def test_the_manifest_is_an_engine_project(application, rig):
    with application.app_context():
        manifest = lstore.set_manifest(None, rig["user"]["id"], rig["set_id"])
    project = manifest["project"]
    for key in ("projectId", "masterTempo", "timeSignature", "items", "scenes",
                "clips", "stems", "padMap"):
        assert key in project, key
    assert project["timeSignature"] == "4/4"
    assert len(project["items"]) == len(project["scenes"]) == 2


def test_every_scene_gets_its_own_set_item(application, rig):
    """The engine's model is item -> scene -> clip, with stems on the item.
    This module's is flatter, so the mapping has to be explicit rather than
    assumed."""
    with application.app_context():
        project = lstore.set_manifest(None, rig["user"]["id"],
                                      rig["set_id"])["project"]
    item_ids = {i["id"] for i in project["items"]}
    for scene in project["scenes"]:
        assert scene["liveSetItemId"] in item_ids


def test_stop_is_always_on_the_last_pad(application, rig):
    """On a dark stage the one control that must be in the same place every
    time is the one that makes everything stop."""
    with application.app_context():
        pads = lstore.set_manifest(None, rig["user"]["id"],
                                   rig["set_id"])["project"]["padMap"]
    assert len(pads) == 16
    assert pads[15]["mode"] == "stop"
    assert pads[15]["label"] == "STOP"


def test_the_manifest_is_one_request(application, rig):
    """A stage rig that has to make six network calls before it can play is a
    rig that fails in a venue with bad wifi."""
    response = rig["client"].get("/live/%s/manifest.json" % rig["set_id"])
    assert response.status_code == 200
    data = response.get_json()
    assert data["project"]["scenes"]
    assert "assets" in data and "midi" in data


# --- the engine's half -------------------------------------------------------

@needs_node
def test_the_engine_still_accepts_what_this_repository_emits():
    """The other side of the contract, run in Node against the real bundle.

    Python cannot execute static/js/livelab.js, so without this the two halves
    could drift until somebody opened a set at a show.
    """
    proc = subprocess.run([NODE, CHECK], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "failed" in proc.stdout
    assert " 0 failed" in proc.stdout


# --- the Rack is untouched ---------------------------------------------------

def test_live_did_not_take_the_rack_away(application):
    client, _user = _artist(application)
    assert client.get("/rack").status_code == 200
    assert client.get("/rack?stems=abc123").status_code == 200

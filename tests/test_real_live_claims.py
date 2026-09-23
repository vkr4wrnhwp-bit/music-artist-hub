# -*- coding: utf-8 -*-
"""Live: the page claims only what the performance page does.

The Live page said two things the performance page did not do (overclaims
list, 2026-09-11, items 13-14):

  "stems go to separate outputs so each player gets their own mix"
      The engine's master, cue and click buses all connect to the one
      AudioContext destination, and perform.html never calls setSinkId.
      Not built: the page now says so.

  "the whole show is cached in the browser so a reload at the venue does
   not end it"
      perform.html fetched every stem from the network on every open.
      Made real: it now keeps the manifest and the stems in IndexedDB through
      the bundle's own IndexedDbCacheStore (static/js/live-perform-cache.js,
      proved in Node by tests/js/check_live_cache.js), and the service worker
      keeps the page itself (static/js/sw.js LIVE_PERFORM).
"""
import os
import re
import shutil
import subprocess
import uuid

import pytest

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
NODE = (os.environ.get("SB_NODE_BIN") or shutil.which("node")
        or shutil.which("node.exe"))
needs_node = pytest.mark.skipif(
    not NODE, reason="node is not on PATH; set SB_NODE_BIN to point at a binary")


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


@pytest.fixture
def rig(application):
    email = "lc-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Rig", "email": email,
                                 "password": "lc-pass-123"})
    client.post("/login", data={"email": email, "password": "lc-pass-123"})
    response = client.post("/live/new", data={
        "name": "Friday headline", "venue": "The Ritz", "tempo_bpm": "128"})
    set_id = response.headers["Location"].rstrip("/").split("/")[-1]
    import db as store
    with application.app_context():
        user_id = store.get_user_by_email(email)["id"]
    return {"client": client, "set_id": set_id, "user_id": user_id}


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# --- the words ---------------------------------------------------------------

def test_the_live_page_no_longer_promises_a_separate_output_per_player(rig):
    body = _text(rig["client"].get("/live").get_data(as_text=True))
    assert "stems go to separate outputs" not in body
    assert "setSinkId" not in body
    assert "one output" in body
    assert "a separate mix for each player is not built yet" in body


def test_the_live_page_states_the_offline_promise_it_now_keeps(rig):
    body = _text(rig["client"].get("/live").get_data(as_text=True))
    assert "the whole show is cached in the browser" not in body
    assert "Open a set once with internet" in body
    assert "opens again at the venue without a connection" in body


def test_the_readiness_list_matches_the_page():
    import live

    rows = dict((key, detail) for key, _name, detail in live.readiness())
    assert "not built yet" in rows["outputs"]
    assert "setSinkId" not in rows["outputs"]
    assert "kept in this browser" in rows["offline"]


def test_the_stem_control_names_a_bus_not_an_in_ear_feed(application, rig):
    """The add-stem form (and its bus picker) only draws when the Vault
    holds audio, so the account gets one file first."""
    import db as store

    client = rig["client"]
    client.post("/live/%s/scene" % rig["set_id"], data={"name": "Intro"})
    with application.app_context():
        store.add_vault_file(rig["user_id"], "/uploads/vault_bus_check.wav",
                             "Kick", "stems")
    body = client.get("/live/%s" % rig["set_id"]).get_data(as_text=True)
    assert 'name="output_bus"' in body          # the picker is on the page
    assert "Cue / in-ear" not in body
    assert ">Cue</option>" in body


# --- the behaviour -----------------------------------------------------------

def test_the_performance_page_keeps_the_set_in_this_browser(rig):
    body = rig["client"].get("/live/%s/perform" % rig["set_id"]).get_data(as_text=True)
    assert '/static/js/live-perform-cache.js' in body
    assert "IndexedDbCacheStore.open(SET_ID)" in body
    assert "KEEP.loadManifest(store, fetchJson)" in body
    assert "KEEP.loadStems(" in body
    # The page registers the service worker itself: it does not extend
    # base.html, where the other pages register it.
    assert 'navigator.serviceWorker.register("/sw.js")' in body


def test_the_service_worker_keeps_the_performance_page():
    source = open(os.path.join(ROOT, "static", "js", "sw.js"), encoding="utf-8").read()
    match = re.search(r"var LIVE_PERFORM = /(.+)/;", source)
    assert match, "no LIVE_PERFORM pattern in sw.js"
    pattern = re.compile(match.group(1).replace("\\/", "/"))
    assert pattern.match("/live/%s/perform" % ("a" * 32))
    assert not pattern.match("/live/%s" % ("a" * 32))
    assert not pattern.match("/live/%s/manifest.json" % ("a" * 32))
    assert "LIVE_PERFORM.test(url.pathname)" in source
    # A new pattern only reaches browsers that already hold the old worker
    # when the version moves.
    assert 'var VERSION = "sb-v320"' not in source


@needs_node
def test_the_cache_wiring_passes_its_node_check():
    proc = subprocess.run([NODE, os.path.join(HERE, "js", "check_live_cache.js")],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert " 0 failed" in proc.stdout

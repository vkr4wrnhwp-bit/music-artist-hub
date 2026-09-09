# -*- coding: utf-8 -*-
"""Every script a page actually SERVES parses.

`test_inline_scripts.py` compiles the script in each template with the
Jinja neutralised - it proves the source is sound. This file compiles what
the server sends, which is a different thing, because autoescape runs
between the two.

The bug that made it necessary, live on 2026-09-09: Artist Pulse had

    g.fillText({{ ('{:,}'.format(milestone) | tojson) if milestone else "''" }}, ...)

The else-branch is a bare Python string, and autoescape applies to the
whole expression, so it rendered as `&#39;&#39;`. That is a SyntaxError,
which killed the entire <script> block - and with it every handler on the
page, including the artist search the owner was trying to use. The
template parsed perfectly; only the rendered page was broken. Worse, the
branch is taken only when there is no artist picked and no milestone, so
it hit exactly the accounts doing first-time setup and never the ones
already set up.

It renders as a fresh account on purpose: empty state is where the
untaken branches live.
"""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid

import pytest

import app as appmod

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(HERE, "js", "check_inline_scripts.js")
NODE = os.environ.get("SB_NODE_BIN") or shutil.which("node") or shutil.which("node.exe")
PASSWORD = "rendered-scripts-123"

# Inline blocks only: a src= script is a static file, and those are
# compiled by test_inline_scripts.py already.
SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)(?![^>]*type=[\"']?(?:application|text)/(?:json|template))"
                    r"[^>]*>(.*?)</script>", re.S)

# Pages a signed-in owner meets early, each of which ships handlers that a
# parse error would silently disable. Kept small on purpose: this test
# renders real pages, so every entry costs a request.
PAGES = ["/pulse", "/catalog", "/tracks", "/vault", "/links", "/epk"]

needs_node = pytest.mark.skipif(
    not NODE, reason="node is needed to parse the rendered scripts; set SB_NODE_BIN "
                     "to a node binary to run this")


@pytest.fixture(scope="module")
def fresh():
    """A brand-new account: no artist, no catalog, no milestones - the
    state whose branches never render for an established one."""
    client = appmod.app.test_client()
    email = "rsc-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client


def _blocks(client):
    out = []
    for path in PAGES:
        r = client.get(path)
        if r.status_code != 200:          # plan-gated or redirected; not this test's business
            continue
        body = r.get_data(as_text=True)
        for i, src in enumerate(SCRIPT.findall(body)):
            if src.strip():
                out.append({"id": "%s#%d" % (path, i), "file": path, "source": src})
    return out


def _compile(blocks):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(blocks, fh)
        manifest = fh.name
    try:
        done = subprocess.run([NODE, HARNESS, manifest], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr[:400]
        return [r for r in json.loads(done.stdout) if not r.get("ok")]
    finally:
        os.unlink(manifest)


@needs_node
def test_every_script_a_fresh_account_is_served_parses(fresh):
    blocks = _blocks(fresh)
    assert blocks, "no inline scripts rendered - the extractor is broken, not the pages"
    bad = _compile(blocks)
    assert not bad, "rendered script(s) that do not parse:\n" + "\n".join(
        "  %s line %s: %s" % (b["id"], b.get("line"), b.get("message")) for b in bad)


@needs_node
def test_the_check_catches_an_escaped_quote(fresh):
    """The exact shape autoescape produced, so this file cannot rot into a
    test that passes because the extractor stopped finding anything."""
    bad = _compile([{"id": "canary", "file": "canary",
                     "source": "g.fillText(&#39;&#39;, 1, 2);"}])
    assert bad and "canary" in bad[0]["id"]

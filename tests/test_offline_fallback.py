"""The offline page must not claim something it has not checked.

Live, 2026-09-09: a signed-in owner opened /catalog and got the app's
"You're offline" screen while curl fetched the same host successfully
five times in a row. The service worker answered ONE rejected navigation
with the fallback, and the fallback stated, as a fact about the reader's
machine, that they had no connection — sending them to check a router
when the server was the thing that had stalled.

Held here: a navigation is retried before the fallback is served; the
fallback words itself from `navigator.onLine` rather than assuming; and
it comes back on its own instead of waiting to be reloaded by hand.
"""
import io
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with io.open(os.path.join(HERE, rel), encoding="utf-8") as f:
        return f.read()


def test_a_navigation_is_retried_before_anyone_is_told_they_are_offline():
    sw = _read("static/js/sw.js")
    assert "function retryThenFallback(" in sw
    body = sw[sw.index("function retryThenFallback("):]
    body = body[:body.index("self.addEventListener")]
    # The helper's whole job: ask a second time, and only then fall back.
    assert "fetch(request)" in body and "/static/offline.html" in body
    # Neither navigation handler may reach the fallback without it.
    nav = sw[sw.index('e.request.mode === "navigate"'):sw.index('url.pathname.indexOf("/static/")')]
    for hit in re.findall(r'caches\.match\("/static/offline\.html"\)', nav):
        assert False, "a navigation still serves the fallback on the first failure"
    assert nav.count("retryThenFallback") == 2, "both the TOUR path and the ordinary one"


def test_the_fallback_does_not_assert_that_the_reader_is_offline():
    page = _read("static/offline.html")
    head = page.split("<script>")[0]
    assert "You're offline" not in head, (
        "the served markup must not claim a connection state before the "
        "browser has been asked")
    assert "Can't reach Street Banker" in head
    assert "<title>Can't reach Street Banker</title>" in page


def test_the_fallback_reads_the_browser_before_it_words_itself():
    page = _read("static/offline.html")
    script = page[page.index("<script>"):]
    assert "navigator.onLine === false" in script, "asked, not assumed"
    # Both sentences exist, and the offline one is only reachable through
    # that check.
    assert "You're offline" in script and "the server didn't answer" in script
    on = script.index("navigator.onLine === false")
    assert script.index("You're offline") > on


def test_the_fallback_comes_back_on_its_own():
    script = _read("static/offline.html")
    assert 'addEventListener("online"' in script, "reconnecting is enough"
    assert "setTimeout" in script and "location.reload()" in script
    assert 'method: "HEAD"' in script, "a probe, not a full page fetch"
    assert 'cache: "no-store"' in script, "never satisfied by the cached failure"
    # It gives up rather than retrying for ever.
    assert "Reload when you're ready" in script


def test_the_worker_version_moved_so_browsers_take_the_new_one():
    sw = _read("static/js/sw.js")
    version = int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1))
    assert version >= 214, (
        "an installed worker keeps serving the old fallback until VERSION "
        "changes, so this fix does not reach anybody without a bump")

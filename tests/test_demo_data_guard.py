"""What a brand-new artist sees, and whether it is honest.

Every other test in this suite logs in as demo@streetbanker.io. That
account is *meant* to be full of sample data - it is the showcase. So the
suite has been exercising the one path where fabricated numbers are
harmless, and almost never the path where they are dangerous: a real
artist who signed up ten seconds ago, has uploaded nothing, and has no
way to tell which figures on screen are theirs.

The standing rule is that demo data, estimates, simulations and
integration-ready features must be clearly labelled. These tests hold the
line on a fresh, empty, non-demo account.
"""
import re

from app import create_app

# Words that count as telling the user the number is not theirs. Kept
# deliberately broad - the point is to catch pages with NO disclosure at
# all, not to police wording.
DISCLOSURE = re.compile(
    r"sample data|demo data|example data|placeholder"
    r"|estimate|estimated|projection|projected|illustrative"
    r"|preview|not yet connected|nothing connected|no source linked"
    r"|upload a (royalty )?statement|connect .{0,24}to see"
    r"|signal only|not an appraisal|not financial advice"
    r"|not a guarantee|once you connect|when you connect",
    re.I,
)

_counter = [0]


def fresh_artist(app_obj=None):
    """A real account with an empty world: no statements, no catalog, no
    connections. This is the state every paying user starts in."""
    app_obj = app_obj or create_app()
    client = app_obj.test_client()
    _counter[0] += 1
    email = "guard%d@example.com" % _counter[0]
    r = client.post("/signup", data={
        "name": "Guard Test",
        "email": email,
        "password": "guardpw123",
    })
    assert r.status_code == 302, "signup failed: %s" % r.status_code
    return client, app_obj


def _artist_get_routes(app_obj):
    """Every plain GET page an artist can reach - no parameters, no
    downloads, no logout, no redirect-only endpoints."""
    skip = ("/logout", "/static/", "/sw.js", "/manifest",
            "/health", "/healthz", "/robots.txt")
    out = []
    for rule in app_obj.url_map.iter_rules():
        if "GET" not in rule.methods or "<" in rule.rule:
            continue
        if any(rule.rule.startswith(s) or rule.rule == s for s in skip):
            continue
        out.append(rule.rule)
    return sorted(out)


def test_a_fresh_account_can_load_every_page_without_erroring():
    """The suite logs in as demo everywhere else. An empty account takes
    different branches - empty lists, None totals, no catalog - and those
    branches are the ones that have never been walked."""
    client, app_obj = fresh_artist()
    broken = []
    for path in _artist_get_routes(app_obj):
        try:
            r = client.get(path)
        except Exception as exc:                       # pragma: no cover
            broken.append((path, "raised %s: %s" % (type(exc).__name__, exc)))
            continue
        if r.status_code >= 500:
            broken.append((path, r.status_code))
    assert not broken, (
        "%d page(s) break for a brand-new artist:\n%s"
        % (len(broken), "\n".join("  %s -> %s" % b for b in broken)))

"""Global Distribution on the homepage: one column of the back office band.

Mostly a claims test, as it always was. The reference image carried eight
statements this codebase cannot support, and the load-bearing job of the
column is to say what is true instead: Street Banker prepares and
validates, the partner delivers, and nothing on the page says otherwise.
The capabilities, the workflow and the guide live on /distribution.
"""

import re

from app import create_app


def _anon():
    return create_app().test_client()


def _home():
    return _anon().get("/").get_data(as_text=True)


def _column(body=None):
    body = body or _home()
    start = body.index('id="global-distribution"')
    return body[start:start + body[start:].index("</article>")]


# --- placement and copy ---------------------------------------------------

def test_the_column_sits_after_the_sweep_and_before_the_passport():
    body = _home()
    assert body.index('id="royalty-sweep-section"') < body.index('id="global-distribution"')
    assert body.index('id="global-distribution"') < body.index('id="metadata-passport"')
    assert body.index('id="metadata-passport"') < body.index('id="closing"')


def test_the_copy_is_the_approved_copy():
    eq = _column()
    assert "Global Distribution" in eq
    assert "Your music. Everywhere." in eq and "On your terms." in eq
    assert ("Prepare, validate and deliver the release. Masters, timing "
            "and territories stay under your control." in eq)
    assert "Check release readiness" in eq
    assert "View distribution guide" in eq
    assert "Ready to release?" not in eq
    assert "Start a release" not in eq


# --- the claims audit -----------------------------------------------------

def test_the_unsupported_claims_from_the_reference_are_absent():
    """Eight statements were drawn into the reference image. Nothing in
    this codebase or in the terms on file supports any of them, so none
    of them is on the page or on the guide."""
    pages = _column() + _anon().get("/distribution").get_data(as_text=True)
    text = re.sub(r"<[^>]+>", " ", pages).lower()
    for claim in ("200+ countries", "every major platform", "keep 100%",
                  "you own your masters", "real time reports",
                  "real-time reports", "no hidden fees", "free to get started",
                  "no credit card", "cancel anytime", "100% of your"):
        assert claim not in text, claim


def test_it_says_who_actually_delivers():
    from distro_config import PARTNER

    eq = _column()
    assert "Symphonic Distribution" in PARTNER["line"]
    assert PARTNER["line"][:60] in eq
    body = _anon().get("/distribution").get_data(as_text=True)
    assert "Street Banker does not hold a direct connection to a streaming platform" in body
    assert "Delivery is the partner" in body


def test_the_integration_statuses_are_honest():
    from distro_config import INTEGRATIONS

    statuses = {s for _n, s in INTEGRATIONS}
    assert statuses <= {"Connected", "Supported", "Delivered through partner",
                        "Integration ready", "Coming soon"}
    # Nothing claims a direct connection this app does not hold.
    assert "Connected" not in statuses
    assert ("Direct platform connections from Street Banker", "Coming soon") in INTEGRATIONS
    body = _anon().get("/distribution").get_data(as_text=True)
    for name, status in INTEGRATIONS:
        assert name in body, name
        assert status in body, status


def test_no_fabricated_figures_anywhere_in_the_column():
    eq = _column()
    text = re.sub(r"<[^>]+>", " ", eq)
    text = re.sub(r"&#?\w+;", " ", text)
    for banned in ("$", "%", "artists trust", "testimonial", "as seen in"):
        assert banned not in text, banned
    assert not re.findall(r"\d", text)


def test_ownership_is_qualified_not_promised():
    from distro_config import CAPABILITIES

    names = [name for _n, name, _d in CAPABILITIES]
    assert names == ["Platform Delivery", "Ownership Control", "Release Control"]
    ownership = next(d for _n, name, d in CAPABILITIES if name == "Ownership Control")
    assert "according to your agreement" in ownership


def test_the_workflow_lives_on_the_guide_page_not_the_homepage():
    from distro_config import WORKFLOW

    eq = _column()
    assert [s for s, _ in WORKFLOW] == ["Prepare", "Validate", "Deliver",
                                        "Monitor", "Maintain"]
    for step, detail in WORKFLOW:
        assert ">%s<" % step not in eq, step
    body = _anon().get("/distribution").get_data(as_text=True)
    for step, detail in WORKFLOW:
        assert step in body, step
        assert detail[:40] in body, step


def test_the_checklist_is_not_duplicated_on_the_homepage():
    """It lives at /release-check, where it is interactive."""
    from distro_config import PRIMARY_CTA

    eq = _column()
    assert "Example release checklist" not in eq
    assert PRIMARY_CTA["href"] == "/release-check"


# --- destinations ---------------------------------------------------------

def test_every_cta_is_public_and_explains_before_it_asks():
    eq = _column()
    hrefs = [re.search(r'class="sbbo-cta" href="([^"]+)"', eq).group(1),
             re.search(r'class="sbbo-col-link" href="([^"]+)"', eq).group(1)]
    # Two destinations, and they must not share one: they once did, which
    # made the primary button do exactly what the guide link did.
    assert hrefs == ["/release-check", "/distribution#guide"]
    client = _anon()
    page = client.get("/distribution")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'id="guide"' in body                     # the anchor exists
    assert body.index("The five stages") < body.index("/signup")
    # The gated release tooling is still gated.
    for gated in ("/releases", "/metadata-passport", "/releases/clean-release"):
        assert client.get(gated).status_code == 302, gated


def test_the_guide_covers_what_a_release_needs():
    from distro_config import GUIDE

    body = _anon().get("/distribution").get_data(as_text=True)
    titles = [t for t, _b in GUIDE]
    for needed in ("Audio", "Artwork", "Metadata", "Credits", "Ownership",
                   "ISRC and UPC", "Release date", "Territories",
                   "Delivery timelines", "Changes after delivery", "Reporting",
                   "Takedowns and updates"):
        assert needed in titles, needed
        assert needed in body, needed
    assert "Delivery is a queue, not a switch" in body

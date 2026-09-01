"""Royalty Sweep on the homepage: one column of the back office band.

Section 9 used to be a photograph, five stages, an example case and a
paragraph. On 2026-09-01 it became one column - name, headline, one
line, one button, one honesty line - and the stages, the example and
the method moved to /royalty-sweep where they always lived in full.

What still has to hold: nothing is guaranteed, found or recovered; the
careful words are actually used; the sources say which are live; the
CTA opens a public preliminary check that calls itself one.
"""

import re

from app import create_app


def _anon():
    return create_app().test_client()


def _home():
    return _anon().get("/").get_data(as_text=True)


def _column(body=None):
    body = body or _home()
    start = body.index('id="royalty-sweep-section"')
    return body[start:start + body[start:].index("</article>")]


# --- placement and copy ---------------------------------------------------

def test_the_sweep_is_a_column_in_the_back_office_band():
    body = _home()
    assert 'id="royalty-sweep"' in body                  # the header links at it
    assert body.index('id="rollout-engine"') < body.index('id="back-office"')
    assert body.index('id="back-office"') < body.index('id="royalty-sweep-section"')
    assert body.index('id="royalty-sweep-section"') < body.index('id="closing"')
    # The old section's furniture is gone with it.
    for gone in ('class="sbsw-flow"', 'id="sbsw-example"', "sweep-wide-1672",
                 "FIND WHAT YOU EARNED."):
        assert gone not in body, gone


def test_the_copy_is_the_approved_copy():
    eq = _column()
    assert "Royalty Sweep" in eq
    assert "Find what&#39;s yours." in eq or "Find what's yours." in eq
    assert "Keep what&#39;s earned." in eq or "Keep what's earned." in eq
    assert "Connect the catalog. Every potential gap becomes a case." in eq
    assert "Run a Free Royalty Sweep" in eq
    assert "Every finding requires verification before submission." in eq
    assert 'href="/royalty-sweep"' in eq                # the method, one link


# --- the language ---------------------------------------------------------

def test_nothing_is_guaranteed_found_or_free():
    from sweep_config import get_sweep_config, METHOD

    cfg = get_sweep_config()
    prose = " ".join(
        [cfg["support"], cfg["trust"], cfg["trust_copy"]] +
        [d for _n, _s, d in cfg["workflow"]] +
        [v for _k, v in cfg["example"]["fields"]] +
        [cfg["example"]["action"], cfg["example"]["note"]] +
        [b for _t, b in METHOD]).lower()
    for banned in ("guaranteed recovery", "free money", "instant payout",
                   "we found your money", "100% success", "claim everything",
                   "guarantee", "risk-free"):
        assert banned not in prose, banned
    # The careful words are actually used.
    for careful in ("potential", "possible", "requires verification",
                    "estimated value range"):
        assert careful in prose, careful


def test_no_money_and_no_figure_appears_in_the_column():
    eq = _column()
    text = re.sub(r"<[^>]+>", " ", eq)
    text = re.sub(r"&#?\w+;", " ", text)
    for banned in ("$", "£", "€", "%", "USD"):
        assert banned not in text, banned
    assert not re.findall(r"\d", text)


def test_the_sources_say_which_are_live():
    from sweep_config import SOURCES

    statuses = {s for _n, s in SOURCES}
    assert statuses <= {"Connected", "Upload Supported", "Integration Ready",
                        "Coming Soon"}
    # Nothing claims a live connection this app does not hold.
    assert "Connected" not in statuses
    body = _anon().get("/royalty-sweep").get_data(as_text=True)
    for name, status in SOURCES:
        assert name in body, name
        assert status in body, status
    assert "Nothing" in body and "claims a live connection" in body


# --- destinations ---------------------------------------------------------

def test_the_cta_opens_a_public_preliminary_check():
    eq = _column()
    href = re.search(r'class="sbbo-cta" href="([^"]+)"', eq).group(1)
    assert href == "/catalog-sweep"
    client = _anon()
    page = client.get("/catalog-sweep")
    assert page.status_code == 200
    assert "Tell us what to look at" in page.get_data(as_text=True)
    # The result of the intake is labelled a preliminary check, not a scan.
    body = client.post("/catalog-sweep", data={
        "catalog": "Example Artist", "role": "artist",
        "url": "https://open.spotify.com/artist/x"}).get_data(as_text=True)
    assert "Preliminary catalog coverage check" in body
    assert "No scan has run" in body
    for lie in ("we scanned", "we found", "uncollected royalties found"):
        assert lie.lower() not in body.lower(), lie
    # The gated recovery workspace is still gated.
    assert client.get("/recovery").status_code == 302


def test_the_methodology_page_is_public_and_explains_the_estimate():
    body = _anon().get("/royalty-sweep").get_data(as_text=True)
    for heading in ("What gets reviewed", "What counts as a potential opportunity",
                    "How estimates are calculated", "How cases are verified",
                    "Which steps need a person", "How your data is handled"):
        assert heading in body, heading
    assert "It does not find money" in body
    assert "estimated value range" in body
    assert "requires verification" in body
    assert "not used to train models without your explicit permission" in body

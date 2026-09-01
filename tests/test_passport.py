"""Metadata Passport + Rights on the homepage: one column of the back
office band.

What has to hold: the seven records and their detail live on /metadata
and are named there in order; the example is labelled an example; the
completeness figure is completion and named for it; nothing claims a
conflict has been verified; and the column on the homepage says only
what the section always said in one breath.
"""

import re

from app import create_app


def _anon():
    return create_app().test_client()


def _home():
    return _anon().get("/").get_data(as_text=True)


def _column(body=None):
    body = body or _home()
    start = body.index('id="metadata-passport"')
    return body[start:start + body[start:].index("</article>")]


# --- placement and copy ---------------------------------------------------

def test_the_column_sits_after_distribution_and_before_the_close():
    body = _home()
    assert body.index('id="global-distribution"') < body.index('id="metadata-passport"')
    assert body.index('id="metadata-passport"') < body.index('id="closing"')


def test_the_copy_is_the_approved_copy():
    eq = _column()
    assert "Metadata Passport + Rights" in eq
    assert "One release." in eq and "Every detail connected." in eq
    assert ("Credits, splits, identifiers, agreements, versions and "
            "history — one living record." in eq)
    assert "Open Metadata Passport" in eq
    assert "control what is confirmed, shared or submitted" in eq
    assert 'href="/metadata#used"' in eq              # how metadata is used


# --- the seven records ----------------------------------------------------

def test_seven_records_in_order_on_the_public_page():
    from passport_config import CATEGORIES

    labels = [c["label"] for c in CATEGORIES]
    assert labels == ["Credits", "Ownership", "Identifiers", "Versions",
                      "Agreements", "Assets", "Release History"]
    body = _anon().get("/metadata").get_data(as_text=True)
    last = -1
    for cat in CATEGORIES:
        at = body.index(cat["label"], last + 1)
        assert at > last, cat["slug"]
        last = at
        assert cat["why"][:40] in body, cat["slug"]
    # The long detail is not on the homepage.
    eq = _column()
    for cat in CATEGORIES:
        assert cat["why"][:40] not in eq, cat["slug"]


def test_the_zone_geometry_is_still_sane():
    """The zones are the record of where each category sits in the scene
    on /metadata; nothing on the homepage renders them any more."""
    from passport_config import CATEGORIES

    boxes = []
    for cat in CATEGORIES:
        left, top, right, bottom = cat["zone"]
        assert 0 <= left < right <= 1 and 0 <= top < bottom <= 1, cat["slug"]
        assert right - left > 0.15 and bottom - top > 0.15, cat["slug"]
        boxes.append((cat["slug"], left, top, right, bottom))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            overlap = (a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4])
            assert not overlap, (a[0], b[0])


# --- the example, and what it never claims --------------------------------

def test_the_passport_is_labelled_an_example():
    eq = _column()
    assert "Example metadata passport" not in eq   # lives on /metadata
    body = _anon().get("/metadata").get_data(as_text=True)
    assert "From the example passport" in body
    assert "Nothing here has been verified" in body


def test_completeness_is_completion_and_named_for_it():
    from passport_config import HEALTH_LABEL, HEALTH_STATUSES, completeness

    assert HEALTH_LABEL == "Metadata completeness"
    for banned in ("Hit Score", "Success Score", "Artist Value",
                   "Revenue Score"):
        assert banned.lower() not in HEALTH_LABEL.lower(), banned
    assert HEALTH_STATUSES == ["Incomplete", "Needs Review",
                               "Conflicts Detected", "Ready for Confirmation",
                               "Complete", "Verified"]
    # Deterministic: it is a count of categories with nothing outstanding.
    assert completeness() == 29
    # A percentage on a marketing page invites reading as a score for the
    # artist rather than a count of filled fields on a worked example.
    eq = _column()
    assert "Metadata completeness" not in eq


def test_nothing_predicts_and_no_conflict_is_called_verified():
    from passport_config import CATEGORIES, ISSUES, HEALTH_NOTE, get_passport_config

    cfg = get_passport_config()
    prose = " ".join(
        [cfg["support"], cfg["trust_copy"], HEALTH_NOTE] +
        [c["why"] for c in CATEGORIES] + [c["action"] for c in CATEGORIES] +
        [i["action"] for i in ISSUES]).lower()
    for banned in ("guarantee", "we predict", "predicts your", "chart position",
                   "hit score", "valuation of", "will earn", "success score"):
        assert banned not in prose, banned
    # And the disclaimer that uses the word is actually present.
    assert "not a prediction" in prose
    # Every example issue is open or waiting - none is claimed as verified.
    for issue in ISSUES:
        assert issue["status"] in ("Open", "Awaiting Signature"), issue["issue"]
        assert issue["severity"] in ("High", "Medium", "Low"), issue["issue"]
        assert issue["evidence"], issue["issue"]


def test_the_connected_example_is_the_agreed_five():
    from passport_config import CONNECTED

    assert CONNECTED["trigger"] == "A songwriter is added under Credits."
    areas = [a for a, _e in CONNECTED["effects"]]
    assert areas == ["Ownership", "Identifiers", "Agreements", "Versions",
                     "Release History"]


# --- destinations ---------------------------------------------------------

def test_the_cta_explains_before_it_asks_for_an_account():
    eq = _column()
    href = re.search(r'class="sbbo-cta" href="([^"]+)"', eq).group(1)
    assert href == "/metadata"
    client = _anon()
    page = client.get("/metadata")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'id="used"' in body
    assert body.index("The seven records") < body.index("/signup")
    # The gated passport itself is still gated.
    assert client.get("/metadata-passport").status_code == 302


def test_the_public_page_says_what_happens_to_the_information():
    from passport_config import USE

    body = _anon().get("/metadata").get_data(as_text=True)
    for heading, _b in USE:
        assert heading in body, heading
    for honest in ("A collaborator sees the release they were invited to",
                   "only when you submit it", "Nothing is overwritten silently",
                   "export it, or remove it"):
        assert honest in body, honest


def test_the_standards_language_claims_no_certification():
    from passport_config import STANDARDS

    assert "not DDEX-certified today" in STANDARDS
    assert "future DDEX integration" in STANDARDS
    body = _anon().get("/metadata").get_data(as_text=True)
    assert STANDARDS[:50] in body
    for banned in ("ddex certified", "ddex-compliant", "officially certified"):
        assert banned not in body.lower(), banned

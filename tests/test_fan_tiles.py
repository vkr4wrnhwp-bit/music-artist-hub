"""The Fan Dashboard, less to read.

The same brief as the TOUR date page (2026-09-06: "more meters and
images and less verbiage"): the numbers sit in windows, the engagement
bands and the sources are meters, consent is a lamp, and the sentences
that explained the page became captions. And the page now shows the one
thing its intro always promised: where each fan came from, counted from
the campaign that captured the email or the Shopify import's tag.
"""
import re
import uuid

import fan_dashboard
import links_store as mls
from tests.test_fan_dashboard import application, artist, _seed, _text  # noqa: F401


def _lcds(html):
    return re.findall(r'<span class="sb-lcd-cap">([^<]+)</span>', html)


def _meters(html):
    return re.findall(r'aria-label="([^"]+)"', html.split('id="main"')[-1]) if 'id="main"' in html else re.findall(r'aria-label="([^"]+)"', html)


def test_the_numbers_are_windows_and_the_bands_are_meters(application, artist):
    client, user = artist
    _seed(application, user["id"], qr_scans=2)
    html = client.get("/fans").get_data(as_text=True)
    assert _lcds(html) == ["fans captured", "consent on file", "pre-saves", "QR scans", "page views"]
    assert '<span class="sb-lcd-v">4</span>' in html and '<span class="sb-lcd-v">2</span>' in html
    meters = _meters(html)
    for band in ("Hot", "Warm", "Cool", "Cold"):
        assert "%s: 1 · 25.0%%" % band in meters, band
    assert "Smart link · Seed: 4" in meters, "where they came from, counted"
    assert 'sb-lamp sb-lamp--good">every fan consented' in html
    assert 'sb-lamp sb-lamp--good">hot' in html and 'sb-lamp sb-lamp--warn">warm' in html
    # The paragraphs went; the captions stayed.
    for gone in ("not invented tiers", "Ranked by the same intent score", "Counted apart from ordinary visits",
                 "People who gave you an email"):
        assert gone not in html, gone
    assert "The smart-link scorer's own bands." in html and "first captured each email" in html
    text = _text(client.get("/fans"))
    assert "doesn't track individual fans" not in text and "LTV" not in text


def test_sources_and_the_consent_gap_come_from_the_records(application, artist):
    client, user = artist
    _seed(application, user["id"])
    with application.app_context():
        fan_id = mls.upsert_fan(user["id"], "ev-%s@example.net" % uuid.uuid4().hex[:6], None, "Ev")
        mls.add_fan_tags(fan_id, ["shopify", "customer"])
        mls.set_fan_intent(fan_id, 5, "Cold")
        data = fan_dashboard.fan_dashboard_for(user["id"])
    assert data["summary"]["total_fans"] == 5 and data["summary"]["without_consent"] == 1
    assert data["sources"] == [{"source": "Smart link · Seed", "count": 4, "share": 80.0},
                               {"source": "Shopify import", "count": 1, "share": 20.0}]
    html = client.get("/fans").get_data(as_text=True)
    assert 'sb-lamp sb-lamp--warn">1 without consent on file' in html
    assert "Shopify import: 1" in _meters(html)
    assert "ltv" not in str(data).lower() and "spend" not in str(data).lower()


def test_the_empty_state_is_unchanged(application, artist):
    client, user = artist
    html = client.get("/fans").get_data(as_text=True)
    assert "No fans captured yet" in html and _lcds(html) == []

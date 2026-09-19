"""The Fans screen's tiles, after the Audience redesign (2026-09-18).

This file used to lock the LCD windows and meters of the old Fan Dashboard.
The owner approved the Audience mockup in their place: four tiles (Owned
fans, Contactable, Never engaged, With a location), each from the account's
own records. What stayed true is locked here: the figures are the account's,
sources and consent come from the records, and the empty state says what
makes a fan.
"""
import re
import uuid

import fan_dashboard
import links_store as mls
from tests.test_fan_dashboard import application, artist, _seed, _text  # noqa: F401


def _tiles(html):
    return re.findall(r'<div class="au-lab">([^<]+)</div>', html)


def test_the_four_tiles_are_the_accounts_own(application, artist):
    client, user = artist
    _seed(application, user["id"], qr_scans=2)
    html = client.get("/fans").get_data(as_text=True)
    assert _tiles(html) == ["Owned fans", "Contactable", "Never engaged", "With a location"]
    assert 'data-au-stat="total">4<' in html and 'data-au-stat="contactable">4<' in html
    # Every seeded fan visited, so nobody is waiting on a first send.
    assert 'data-au-stat="never">0<' in html
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
    # Four of five have a consent record: the health row says 80, not 100.
    assert re.search(r"Consent on file</span>\s*<span class=\"au-hbar\"><i class=\"good\" style=\"width: 80%;\"></i></span><span class=\"au-hsc\">80/100", html)
    assert "Added from your Shopify customers" in html
    assert "ltv" not in str(data).lower() and "spend" not in str(data).lower()


def test_the_empty_state_is_honest(application, artist):
    client, user = artist
    html = client.get("/fans").get_data(as_text=True)
    # 2026-09-18: a real account with nobody on file gets the owner-approved
    # first-run page at /fans, not the old "No fans captured yet" panel
    # (tests/test_fans_first_run.py locks it). Updated deliberately.
    assert "Your audience already exists" in html and ">Not measured<" in html
    assert ">None yet<" in html

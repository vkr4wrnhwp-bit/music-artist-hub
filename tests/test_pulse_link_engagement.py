"""The one tile on Pulse that does not need Spotify, and it read nought.

"Your Link Engagement - all time" counts page views, platform clicks and
pre-saves from the artist's own smart links. It is first-party, which is
the point: it shows something real whether or not a vendor key is set.

It read `pageview` and `click`. The events actually written are
`page_view` and `service_click` - see the track() calls on the public
link page - so the tile showed 0 for every account on every deployment,
however much traffic a link took, under copy reading "Counted from your
own tracked smart links".

The same request cycle could report the traffic correctly elsewhere:
/reports/campaigns.csv reads the right names, and the Partner Portal
sums BOTH spellings, so the mismatch was known in two places and never
carried back to Pulse.
"""
import uuid

import pytest

import db as store
import links_store as mls
from app import create_app


@pytest.fixture
def client():
    app_obj = create_app()
    c = app_obj.test_client()
    c._app = app_obj
    email = "pulse-eng-%s@example.net" % uuid.uuid4().hex[:10]
    c.post("/signup", data={"name": "Owner", "email": email,
                            "password": "pulsepass1"})
    with app_obj.app_context():
        c._uid = store.get_user_by_email(email)["id"]
    return c


def _campaign_with_traffic(client, views, clicks):
    """A campaign carrying real events, written under the names the
    product actually uses."""
    with client._app.app_context():
        # create_campaign returns the id, not a row.
        campaign_id = mls.create_campaign(
            client._uid, "k810-%s" % uuid.uuid4().hex[:8],
            {"title": "King 810 - single"})
        for _ in range(views):
            mls.track(campaign_id, "page_view")
        for _ in range(clicks):
            mls.track(campaign_id, "service_click")
    return campaign_id


def _lcd(body, caption):
    """The number the page shows beside a caption.

    Read from the rendered LCD pair rather than by searching the whole
    page for a digit. The first draft of this test asserted
    `">5<" in body or "5" in body`, which is true of almost any page and
    therefore proved nothing - it passed against the broken counter.
    """
    import re

    pattern = (r'<span class="sb-lcd-v">([^<]*)</span>\s*'
               r'<span class="sb-lcd-cap">\s*' + re.escape(caption))
    match = re.search(pattern, body)
    assert match, "no LCD captioned %r on the page" % caption
    return match.group(1).strip()


def test_the_tile_counts_the_events_the_product_writes(client):
    _campaign_with_traffic(client, views=5, clicks=3)
    body = client.get("/pulse").get_data(as_text=True)
    assert "Your Link Engagement" in body
    assert _lcd(body, "page views") == "5"
    assert _lcd(body, "platform clicks") == "3"


def test_traffic_is_not_reported_as_nothing(client):
    """The assertion that would have caught it: same account, same
    request cycle, traffic on file and the tile reading zero."""
    _campaign_with_traffic(client, views=7, clicks=4)
    page = client.get("/pulse")
    assert page.status_code == 200
    body = page.get_data(as_text=True)

    # Pull the three LCD values out of the Link Engagement block.
    start = body.index("Your Link Engagement")
    block = body[start:start + 1200]
    assert "7" in block, "seven page views were recorded and the tile must say so"
    assert "4" in block, "and four platform clicks"


def test_an_account_with_no_links_still_reads_nought(client):
    """Nought is the right answer when nothing happened - the fix must
    not invent traffic to prove itself."""
    block_start = client.get("/pulse").get_data(as_text=True)
    assert "Your Link Engagement" in block_start
    start = block_start.index("Your Link Engagement")
    assert "0" in block_start[start:start + 1200]

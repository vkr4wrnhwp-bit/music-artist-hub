"""The money page showed an artist somebody else's money.

get_royalties_overview() takes five inputs and only `balances` was gated
on the showcase account. A real artist with two months of their own
statements uploaded saw:

    Total Royalties   $0.00        (balances empty - correct)
    ...up 14.3% vs last month      (an invented earnings trend)
    Payouts Received  $720.40      (invented payout rows)
    Pending Payouts   $2,616.70    (invented, "5 upcoming")
    Platforms Connected 9 / 25     (nobody connected anything)
    Total this month  $3,200.00    (their real total was $6,529.01)
    A payout calendar: The MLC $180.18, BMI $340.00, ASCAP $780.00...

Zero with a growth rate beside it is not internally coherent, and all of
it sat directly above the by-source table built from their own upload.

Payouts are gone rather than corrected: Street Banker has no payout
schedule - no table, no feed, no distributor API - so there is nothing
honest to put there.
"""
import io
import uuid

import pytest

from app import create_app

MAY = ("Reporting Period,Track Title,ISRC Code,Digital Service Provider,"
       "Royalty ($US)\n"
       "MAY-26,Hungry Gods,GBWUL2686921,Spotify,100.00\n"
       "MAY-26,Hungry Gods,GBWUL2686921,Apple Music,50.00\n")
JUN = ("Reporting Period,Track Title,ISRC Code,Digital Service Provider,"
       "Royalty ($US)\n"
       "JUN-26,Hungry Gods,GBWUL2686921,Spotify,200.00\n"
       "JUN-26,Hungry Gods,GBWUL2686921,Apple Music,100.00\n")

INVENTED = ("720.40", "2,616.70", "3,200.00", "2,800.00", "14.3",
            "9 / 25", "Payout Calendar", "180.18", "780.00")


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "royalties-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "King 810", "email": email,
                                 "password": "royaltiespw1"})
    client.post("/plan/switch", data={"plan": "pro"})
    return client


def _upload(client, name, csv):
    return client.post("/statements",
                       data={"statement": (io.BytesIO(csv.encode()), name)},
                       content_type="multipart/form-data")


def test_an_account_with_no_statements_is_told_so(artist):
    body = artist.get("/royalties").get_data(as_text=True)
    assert "Nothing to report yet" in body
    assert "Upload a statement" in body
    for invented in INVENTED:
        assert invented not in body, invented


def test_the_figures_are_the_accounts_own(artist):
    _upload(artist, "may.csv", MAY)
    _upload(artist, "jun.csv", JUN)
    body = artist.get("/royalties").get_data(as_text=True)

    assert "$450.00" in body, "150 + 300 from their own two statements"
    assert "Reported earnings" in body
    assert "Stores that paid you" in body
    for invented in INVENTED:
        assert invented not in body, invented


def test_the_change_is_between_their_own_periods(artist):
    _upload(artist, "may.csv", MAY)
    _upload(artist, "jun.csv", JUN)
    body = artist.get("/royalties").get_data(as_text=True)
    # 300 against 150 is +100%, and both period labels are named so the
    # reader can see which two are being compared.
    assert "100.0%" in body
    assert "JUN-26" in body and "MAY-26" in body


def test_one_period_cannot_be_compared_to_anything(artist):
    _upload(artist, "jun.csv", JUN)
    body = artist.get("/royalties").get_data(as_text=True)
    assert "Not measured" in body
    assert "Upload a second period" in body


def test_the_period_picker_lists_real_periods_and_filters(artist):
    """It read "This month / Last 3 months / Last 6 months" and had no
    listener anywhere - three dead options on a money page."""
    _upload(artist, "may.csv", MAY)
    _upload(artist, "jun.csv", JUN)

    body = artist.get("/royalties").get_data(as_text=True)
    assert 'value="JUN-26"' in body and 'value="MAY-26"' in body
    assert "Last 3 months" not in body, "a window this app cannot compute"

    only_june = artist.get("/royalties?period=JUN-26").get_data(as_text=True)
    assert "$300.00" in only_june
    assert "$450.00" not in only_june, "the whole page follows the period"


def test_an_unknown_period_falls_back_rather_than_emptying_the_page(artist):
    _upload(artist, "jun.csv", JUN)
    body = artist.get("/royalties?period=NOPE-99").get_data(as_text=True)
    assert "$300.00" in body, "an unrecognised period shows everything"


def test_the_platform_filter_offers_stores_that_actually_paid(artist):
    _upload(artist, "jun.csv", JUN)
    body = artist.get("/royalties").get_data(as_text=True)
    assert '<option value="Spotify"' in body
    assert '<option value="Apple Music"' in body

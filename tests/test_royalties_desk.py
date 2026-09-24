"""The Royalties desk, approved from the numbered mockup of 2026-09-13.

One page where there were three. Every figure follows the period; the
streams stand up as columns and a dashed one is a statement nobody
uploaded; the lanes are read per track; stores and tracks are drawn as
movement between the last two periods; markets come off the territory
column or say there is none.
"""
import io
import uuid

import pytest

import royalties_desk as desk
import statements_engine as se


def test_periods_order_the_way_a_calendar_does_whatever_the_distributor_wrote():
    assert desk.order_periods(["JUN-26", "MAY-26"]) == ["MAY-26", "JUN-26"]
    assert desk.order_periods(["2026-06", "2026-05", "2025-12"]) == ["2025-12", "2026-05", "2026-06"]
    assert desk.order_periods(["May 2026", "April 2026"]) == ["April 2026", "May 2026"]
    assert desk.order_periods(["Q2", "Q1"]) == ["Q1", "Q2"], "unknown shapes keep their written order"


ROWS = [
    {"title": "Hungry Gods", "source": "Spotify", "amount": 300.0, "period": "MAY-26", "territory": "US", "isrc": ""},
    {"title": "Hungry Gods", "source": "SoundExchange: Sirius XM", "amount": 20.0, "period": "MAY-26", "territory": "", "isrc": ""},
    {"title": "Hellhounds", "source": "Spotify", "amount": 150.0, "period": "JUN-26", "territory": "GB", "isrc": ""},
    {"title": "Hellhounds", "source": "YouTube Streaming", "amount": 50.0, "period": "JUN-26", "territory": "US", "isrc": ""},
    {"title": "Hungry Gods", "source": "Spotify", "amount": 330.0, "period": "JUN-26", "territory": "US", "isrc": ""},
]


def test_streams_stand_up_and_a_silent_stream_is_not_on_file_not_zero():
    a = se.analyze(ROWS)
    out = desk.streams(a)
    by = {c["key"]: c for c in out["cols"]}
    assert by["recording"]["on_file"] and by["recording"]["amount"] == 830.0 and by["recording"]["height"] == 100
    assert by["neighboring"]["on_file"] and by["neighboring"]["amount"] == 20.0 and by["neighboring"]["height"] == 4
    assert not by["publishing"]["on_file"] and by["publishing"]["shown"] == "—" and by["publishing"]["sub"] == "no PRO statement"
    assert not by["mechanical"]["on_file"] and by["mechanical"]["sub"] == "no MLC statement"
    rows = {r["key"]: r for r in out["ledger"]}
    assert rows["publishing"]["lamp"] == "not on file" and "PRO" in rows["publishing"]["what"]
    assert rows["recording"]["lamp"] == "on file" and "Spotify" in rows["recording"]["what"]
    assert out["on_file"] == 2


def test_the_mlc_sweep_shows_on_the_mechanical_row():
    a = se.analyze(ROWS)
    mlc = {"on": True, "latest": {"summary": {"unmatched": 2, "partial": 1}}}
    row = {r["key"]: r for r in desk.streams(a, mlc)["ledger"]}["mechanical"]
    assert row["lamp"] == "2 works unregistered" and row["tone"] == "crit"
    assert "2 works with no registration and 1 partly claimed" in row["what"]
    assert row["href"] == "/recovery#mlc"


def test_movement_reads_the_last_two_periods_and_folds_the_tail():
    periods = desk.order_periods(r["period"] for r in ROWS)
    import store_identity
    out = desk.movement(ROWS, periods, lambda r: store_identity.store_of(r["source"]), limit=1)
    assert out["a"] == "MAY-26" and out["b"] == "JUN-26" and out["enough"]
    spotify = out["rows"][0]
    assert spotify["key"] == "Spotify" and spotify["a"] == 300.0 and spotify["b"] == 480.0
    assert spotify["delta_text"] == "+60.0%" and spotify["tone"] == "up"
    assert out["tail"]["count"] == 2 and out["tail"]["total"] == 70.0
    tail = {e["key"]: e for e in out["tail"]["rows"]}
    assert tail["YouTube"]["delta_text"] == "new" and tail["SoundExchange"]["delta_text"] == "gone"
    one = desk.movement([r for r in ROWS if r["period"] == "JUN-26"], ["JUN-26"], lambda r: r["source"])
    assert one["enough"] is False and one["rows"] == []


def test_markets_read_the_territory_column_and_say_how_many_rows_carried_one():
    out = desk.markets(ROWS)
    assert out["covered"] == 4 and out["total_rows"] == 5
    assert out["rows"][0] == {"code": "US", "amount": 680.0} and out["rows"][1] == {"code": "GB", "amount": 150.0}
    bare = desk.markets([dict(r, territory="") for r in ROWS])
    assert bare["rows"] == [] and bare["covered"] == 0


def test_earnings_compare_the_last_two_periods_in_calendar_order():
    a = se.analyze(ROWS)
    e = desk.earnings(a, [("MAY-26", 320.0), ("JUN-26", 530.0)])
    assert e["delta_text"].startswith("+65.6%") and "JUN-26 vs MAY-26" in e["delta_text"]
    assert e["spark"] and e["spark_first"] == "MAY-26 $320" and e["spark_last"] == "JUN-26 $530"
    one = desk.earnings(a, [("JUN-26", 530.0)])
    assert one["spark"] is None and one["delta_text"] == "Not measured · one period"
    assert "Upload a second period" in one["note"]


def test_lanes_count_the_lanes_that_show_money_and_price_the_registrations():
    tracks = [{"id": "t1", "title": "Hungry Gods", "passport": {}, "lockbox": {}}]
    # earned_by_track: Hungry Gods' own $850. A lane is priced from the
    # track's own rows since 2026-09-23, never from statement_total alone.
    ctx = {"statement_rows": 5, "statement_total": 850.0, "lanes_with_data": {"master", "soundexchange"},
           "earned_by_track": {"t1": 850.0},
           "live_links": 0, "fans": 0, "club_members": 0, "sync_active": False,
           "release_scheduled": False, "rollout_assets": False}
    out = desk.lanes(tracks, ctx)
    assert out["paying"] == 2 and out["of"] == 9 and out["cells"][0] is True
    cells = {c["key"]: c for c in out["rows"][0]["cells"]}
    assert cells["master"]["dot"] == "claimed" and cells["mechanicals"]["dot"] == "action"
    assert cells["sync"]["dot"] == "missing" and cells["sync"]["word"] == "no evidence"
    footer = {f["key"]: f for f in out["footer"]}
    assert footer["mechanicals"]["estimate"] == 51.0 and footer["mechanicals"]["share"] == "6% share"
    assert footer["sync"]["estimate"] == 0 and out["missing_est"] > 0
    empty = desk.lanes([], ctx)
    assert empty["paying"] == 0 and "No Track Passports" in empty["note"]
    # Two tracks do not double the catalogue estimate: a track with no rows
    # of its own adds nothing...
    two = desk.lanes(tracks + [dict(tracks[0], id="t2", title="Hellhounds")], ctx)
    assert {f["key"]: f for f in two["footer"]}["mechanicals"]["estimate"] == 51.0
    assert two["missing_est"] == out["missing_est"]
    # ...and two that each earned part of the $850 add up to 6% of it.
    split = dict(ctx, earned_by_track={"t1": 600.0, "t2": 250.0})
    both = desk.lanes(tracks + [dict(tracks[0], id="t2", title="Hellhounds")], split)
    assert {f["key"]: f for f in both["footer"]}["mechanicals"]["estimate"] == 51.0


# --- the page -----------------------------------------------------------

MAY = "title,source,amount,period,territory\nHungry Gods,Spotify,300,MAY-26,US\nHungry Gods,ASCAP,20,MAY-26,\n"
JUN = "title,source,amount,period,territory\nHungry Gods,Spotify,330,JUN-26,US\nHellhounds,Deezer,150,JUN-26,GB\n"


@pytest.fixture
def artist():
    from app import create_app
    app_obj = create_app()
    client = app_obj.test_client()
    email = "roy-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Roy", "email": email, "password": "roy-pass-12345"})
    client.post("/plan/switch", data={"plan": "pro"})
    return client


def _upload(client, name, csv):
    r = client.post("/statements", data={"statement": (io.BytesIO(csv.encode()), name)},
                    content_type="multipart/form-data")
    assert r.status_code == 302


def test_the_page_follows_the_period_and_stands_the_streams_up(artist):
    _upload(artist, "may.csv", MAY)
    _upload(artist, "jun.csv", JUN)
    body = artist.get("/royalties").get_data(as_text=True)
    assert '<span class="sbm-v">$800.00</span>' in body
    assert "2 statements" in body and "2 tracks" in body and "MAY-26 – JUN-26" in body
    assert 'data-stream="recording"' in body and 'data-stream="publishing"' in body
    assert '<div class="bar none">' in body, "mechanical: nothing on file, drawn dashed"
    assert 'data-stream-row="publishing"' in body and "ASCAP" in body and "$20.00" in body
    assert "By store, MAY-26 against JUN-26" in body and "Tracks, MAY-26 against JUN-26" in body
    assert "GB" in body and "no imputed geography" in body
    assert "annualised run rate" in body and "not financial advice" in body
    for invented in ("Payouts Received", "Pending Payouts", "Platforms Connected", "Payout Calendar"):
        assert invented not in body, invented
    assert "None" not in body.replace("NoneType", "")
    june = artist.get("/royalties?period=JUN-26").get_data(as_text=True)
    assert '<span class="sbm-v">$480.00</span>' in june and "$800.00" not in june


def test_the_old_pages_land_on_their_section_of_the_one_page(artist):
    for old, anchor in (("/royalty-lanes", "#lanes"), ("/publishing", "#streams"), ("/mechanicals", "#streams"),
                        ("/neighboring-rights", "#streams"), ("/territories", "#markets")):
        r = artist.get(old)
        assert r.status_code == 302 and r.headers["Location"].endswith("/royalties" + anchor), old


def test_the_lanes_matrix_reads_the_tracks(artist):
    _upload(artist, "may.csv", MAY)
    artist.post("/tracks/add", data={"title": "Lane Song"})
    # Lane Song has no statement rows, so it prices nothing; this used to
    # pass on 6% of the whole catalogue drawn under it. Hungry Gods earned
    # $320 in MAY-26, and its missing lanes are priced from that
    # (make-it-real, 2026-09-23).
    artist.post("/tracks/add", data={"title": "Hungry Gods"})
    body = artist.get("/royalties").get_data(as_text=True)
    assert "Lane Song" in body and 'class="ry-dot claimed"' in body and 'class="ry-dot action"' in body
    assert "Est. missing" in body and "6% share" in body and "$19.20" in body


def test_the_sidebar_lists_royalties_once_and_the_folded_pages_not_at_all():
    import hubs
    entries = [it for _k, _l, _d, items in hubs.HUBS for it in items]
    hrefs = {it[1] for it in entries}
    assert "/royalties" in hrefs
    for gone in ("/royalty-lanes", "/publishing", "/mechanicals", "/territories"):
        assert gone not in hrefs, gone


# --- the roster ---------------------------------------------------------

ROSTER = ("Reporting Period,Artist,Track Title,Digital Service Provider,Territory,Royalty ($US)\n"
          "MAY-26,Hungry Gods,Narrow,Spotify,US,300\n"
          "MAY-26,Hellhounds,Howl,Spotify,GB,100\n"
          "JUN-26,Hungry Gods,Narrow,Spotify,US,330\n"
          "JUN-26,Hungry Gods,Wide,Deezer,US,70\n"
          "JUN-26,Hellhounds,Howl,Spotify,GB,120\n")


def test_a_label_export_offers_the_roster_and_one_act_puts_the_whole_page_in_scope(artist):
    _upload(artist, "label.csv", ROSTER)
    body = artist.get("/royalties").get_data(as_text=True)
    assert 'id="royalties-artist"' in body and "Whole roster" in body
    assert 'id="artists"' in body and "2 artists in the statements on file" in body
    assert 'aria-label="Hungry Gods: $700.00"' in body and 'aria-label="Hellhounds: $220.00"' in body
    assert "2 tracks · 76%" in body and "1 track · 24%" in body
    assert '<span class="sbm-v">$920.00</span>' in body
    assert "Read Hellhounds" in body and "Read Hungry Gods" in body

    one = artist.get("/royalties?artist=Hellhounds").get_data(as_text=True)
    assert '<span class="sbm-v">$220.00</span>' in one and "$920.00" not in one
    assert "Wide" not in one and "Howl" in one
    assert '<option value="Hellhounds" selected>' in one
    assert "Whole roster</a>" in one, "the act in scope offers the way back"
    assert 'href="/royalties?artist=Hungry%20Gods"' in one

    both = artist.get("/royalties?artist=Hellhounds&period=JUN-26").get_data(as_text=True)
    assert '<span class="sbm-v">$120.00</span>' in both
    assert 'aria-label="Hungry Gods: $700.00"' in both, "the roster shares stay whole-roster"

    unknown = artist.get("/royalties?artist=Nobody").get_data(as_text=True)
    assert '<span class="sbm-v">$920.00</span>' in unknown, "an unknown act is the whole roster"


def test_one_artist_on_file_gets_no_roster_control(artist):
    _upload(artist, "may.csv", MAY)
    body = artist.get("/royalties").get_data(as_text=True)
    assert 'id="royalties-artist"' not in body and 'id="artists"' not in body
    assert "Whole roster" not in body

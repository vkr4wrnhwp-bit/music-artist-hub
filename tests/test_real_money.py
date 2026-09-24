"""The money pages say only what the code measures (make-it-real, 2026-09-23).

The owner believed everything in V1 was real. These hold the money group's
fixes to that standard:

  * The MLC row in the directory opens the real MLC sweep on Recovery, not
    a preview page saying the engine is being built.
  * Missing money prices a gap from THAT track's own statement rows, or
    shows no figure. It used to take the whole account's total times a
    lane share for every track and add them up, so the headline could
    exceed everything the catalogue ever earned.
  * The Command Center money card shows actual and estimated money side
    by side, never one total that adds them.
  * The sidebar badges a page Sample only when it shows sample data.
  * The statements card, the Artist Pulse line and the P&L line claim no
    more than the code does.
"""

import io
import re
import uuid

import artist_os
import command_center as cc
import db as store
import hubs
import rooms
from app import create_app


def _client(app_obj=None, plan="pro"):
    app_obj = app_obj or create_app()
    client = app_obj.test_client()
    email = "realmoney%s@x.com" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "RM", "email": email,
                                 "password": "secret1", "account_type": "artist"})
    client.post("/plan/switch", data={"plan": plan})
    return client, store.get_user_by_email(email)["id"]


_CSV = (b"Track Title,Store,Net Revenue,Sales Period\n"
        b"Midnight Drive,Spotify,120.50,2026-04\n"
        b"Midnight Drive,Apple Music,80.25,2026-05\n"
        b"Neon Dreams,Spotify,60.00,2026-05\n"
        b",Spotify,12.40,2026-05\n")


def _upload(client, data=_CSV):
    return client.post("/statements",
                       data={"statement": (io.BytesIO(data), "s.csv")},
                       content_type="multipart/form-data")


def _sidebar_line(key):
    for _h, _n, _t, items in hubs.HUBS:
        for k, _href, _icon, label, desc in items:
            if k == key:
                return label, desc
    raise AssertionError(key)


# --- the MLC row opens the real sweep ---------------------------------------

def test_the_mlc_address_opens_the_real_sweep_on_recovery():
    client, _uid = _client()
    r = client.get("/royalty-recovery/mlc")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/recovery#mlc")
    # A door's way back rides through, before the fragment.
    r = client.get("/royalty-recovery/mlc?returnTo=/all-tools&from=all-tools")
    assert r.headers["Location"].endswith(
        "/recovery?returnTo=/all-tools&from=all-tools#mlc")
    # The section it lands on is the sweep, not a preview page.
    body = client.get("/recovery").get_data(as_text=True)
    assert 'id="mlc"' in body
    assert "in preview" not in body


def test_the_directory_lists_the_mlc_sweep_as_live():
    route, name, blurb, status, _disc = cc.MODULE_BY_ROUTE["/royalty-recovery/mlc"]
    assert status == "live"
    assert "The MLC" in blurb and "claim packet" not in blurb
    assert "/royalty-recovery/mlc" not in cc.PREVIEW_FEATURES
    client, _uid = _client()
    tools = client.get("/all-tools").get_data(as_text=True)
    assert 'href="/royalty-recovery/mlc"' in tools
    assert not re.search(r'class="sb-mod sb-mod--preview" href="/royalty-recovery/mlc"', tools)


# --- Missing money: a track's own money, or no figure -----------------------

def _track(tid, title, isrc=""):
    return {"id": tid, "title": title, "passport": {"isrc": isrc} if isrc else {},
            "lockbox": {}}


def _ctx(rows, tracks):
    return {"statement_rows": len(rows),
            "statement_total": round(sum(r["amount"] for r in rows), 2),
            "lanes_with_data": set(), "live_links": 0, "fans": 0,
            "club_members": 0, "sync_active": False, "rollout_assets": False,
            "earned_by_track": artist_os.earnings_by_track(tracks, rows)}


def test_a_row_belongs_to_one_track_at_most():
    a = _track("a", "Night Drive", "US-AB1-26-00001")
    b = _track("b", "Hollow")
    c = _track("c", "Twice")
    d = _track("d", "twice ")
    rows = [
        # by ISRC, however it is punctuated
        {"title": "Night Drive (Remaster)", "isrc": "USAB12600001", "amount": 40.0},
        # by title when the row names no ISRC
        {"title": "night drive", "isrc": "", "amount": 10.0},
        # a different recording with the same title is not this track's money
        {"title": "Night Drive", "isrc": "GBXYZ2600009", "amount": 500.0},
        {"title": "Hollow", "isrc": "", "amount": 25.0},
        # two passports share the title: nobody can say whose it is
        {"title": "Twice", "isrc": "", "amount": 70.0},
        # nobody's
        {"title": "Somebody Else", "isrc": "", "amount": 900.0},
    ]
    earned = artist_os.earnings_by_track([a, b, c, d], rows)
    assert earned == {"a": 50.0, "b": 25.0}
    assert sum(earned.values()) <= sum(r["amount"] for r in rows)


def test_a_lane_is_priced_from_the_tracks_own_earnings_or_not_at_all():
    earner = _track("a", "Night Drive")
    silent = _track("b", "Never Played")
    rows = [{"title": "Night Drive", "source": "Spotify", "isrc": "", "amount": 100.0},
            {"title": "Somebody Else", "source": "Spotify", "isrc": "", "amount": 900.0}]
    ctx = _ctx(rows, [earner, silent])
    mech = {l["key"]: l for l in artist_os.lane_grid(earner, ctx)}["mechanicals"]
    # 6% of the $100 this track earned, not 6% of the account's $1,000.
    assert mech["estimate"] == 6.0
    assert "this track's own" in mech["estimate_basis"]
    assert mech["track_earned"] == 100.0
    assert all(l["estimate"] is None for l in artist_os.lane_grid(silent, ctx))


def test_the_queue_never_multiplies_the_account_total_by_the_track_count():
    tracks = [_track("t%d" % i, "Song %d" % i) for i in range(5)]
    rows = [{"title": "Song 0", "source": "Spotify", "isrc": "", "amount": 50.0},
            {"title": "Song 1", "source": "Spotify", "isrc": "", "amount": 30.0},
            {"title": "Catalogue Hit", "source": "Spotify", "isrc": "", "amount": 920.0}]
    ctx = _ctx(rows, tracks)
    queue = artist_os.action_queue([(t, ctx) for t in tracks])
    priced = [a for a in queue if a["impact"]]
    assert {a["track_id"] for a in priced} == {"t0", "t1"}
    # Every figure is a share of its own track's money...
    for a in priced:
        own = ctx["earned_by_track"][a["track_id"]]
        assert a["impact"] <= own
    # ...so even added up they stay inside what those tracks earned. The
    # old figure was 36% of $1,000 on each of five tracks: $1,800.
    assert sum(a["impact"] for a in priced) <= 80.0


def test_the_missing_money_page_prices_only_what_a_track_earned():
    app_obj = create_app()
    client, uid = _client(app_obj)
    store.add_os_track(uid, "Paid Song")
    store.add_os_track(uid, "Quiet Song")
    store.save_statement(uid, "s.csv", [
        {"title": "Paid Song", "source": "Spotify", "amount": 200.0, "period": "2026-05"},
        {"title": "Not On A Passport", "source": "Spotify", "amount": 800.0, "period": "2026-05"},
    ])
    body = client.get("/money-queue").get_data(as_text=True)
    assert "Missing Money Action Queue" in body
    # 6% of Paid Song's own $200, never 6% of the account's $1,000.
    assert "~$12.00" in body
    assert "~$60.00" not in body
    # No headline that adds the estimates up.
    assert "Est. On The Table" not in body
    queue = body.split("Missing Money Action Queue", 1)[1]
    quiet = [chunk for chunk in queue.split('class="rounded-2xl border')
             if "Quiet Song" in chunk]
    assert quiet and not any("~$" in chunk for chunk in quiet)


def test_the_missing_money_line_does_not_promise_a_price_on_every_gap():
    label, desc = _sidebar_line("money-queue")
    assert label == "Missing money"
    assert "priced by what each is costing you" not in desc
    assert "most urgent first" in desc and "own earnings" in desc


# --- the Command Center card: actual and estimated, never added -------------

def _money_card(body):
    start = body.index("Money Left on the Table")
    return body[start:body.index("Scan", start)]


def test_the_money_card_shows_actual_and_estimated_apart():
    app_obj = create_app()
    client, uid = _client(app_obj)
    _upload(client)
    import recovery_engine
    with app_obj.app_context():
        view = recovery_engine.build(uid)
    actual, estimated = view["actual_unattributed"], view["estimated_gaps"]
    assert actual > 0 and estimated > 0
    card = _money_card(client.get("/overview").get_data(as_text=True))
    assert "${:,.2f}".format(actual) in card
    assert "${:,.2f}".format(estimated) in card
    assert "Actual" in card and "Estimate" in card
    # The two bases are never printed as one figure.
    assert "${:,.2f}".format(round(actual + estimated, 2)) not in card


def test_the_valuation_driver_does_not_add_actual_and_estimated():
    app_obj = create_app()
    client, uid = _client(app_obj)
    _upload(client)
    import recovery_engine
    import valuation_engine
    with app_obj.app_context():
        view = recovery_engine.build(uid)
        drivers = valuation_engine.build(uid)["drivers"]
    total = "${:,.2f}".format(round(view["actual_unattributed"] + view["estimated_gaps"], 2))
    collect = [d for d in drivers if d["route"] == "/recovery"]
    assert collect
    assert total not in collect[0]["impact"] and "at stake" not in collect[0]["impact"]
    assert "${:,.2f}".format(view["actual_unattributed"]) in collect[0]["impact"]


def test_the_scan_answer_names_actual_and_estimated_apart():
    client, _uid = _client()
    _upload(client)
    out = client.post("/scan/missing-royalties").get_json()
    assert out["total_actual"] == 12.40
    # "estimated" is the estimate alone; it used to carry the actual too.
    assert out["total_estimated"] == round(
        sum(f["estimated_value"] for f in out["findings"]
            if f["issue_type"] != "Unattributed revenue"), 2)


# --- Sample badges only where sample data is shown --------------------------

def test_real_pages_are_not_badged_sample():
    live = set(hubs.live_keys())
    for key in ("conflicts", "money-queue", "discover"):
        assert key in live, key
    states = {c[0]: c[5] for r in rooms.build("pro") for c in r[4]}
    for key in ("conflicts", "money-queue", "discover"):
        assert states[key] == "live", (key, states[key])


def test_a_real_account_sees_no_sample_feed_on_discover():
    client, _uid = _client()
    body = client.get("/discover").get_data(as_text=True)
    assert "Sample feed" not in body and "Nova Reign" not in body


# --- words that claim only what the code does -------------------------------

def test_the_statements_card_names_only_the_format_it_has_proven():
    client, _uid = _client()
    body = client.get("/statements").get_data(as_text=True)
    assert "Symphonic, DistroKid, TuneCore, ASCAP, BMI and The MLC" not in body
    assert "Tested on a real Symphonic export" in body
    assert "not yet proven" in body


def test_the_pulse_line_does_not_promise_what_spotify_retired():
    _route, _name, blurb, _status, _disc = cc.MODULE_BY_ROUTE["/pulse"]
    assert "popularity" not in blurb.lower()
    assert "Deezer" not in blurb
    assert "Soundcharts" in blurb
    _label, line = _sidebar_line("pulse")
    assert "popularity" not in line.lower() and "Daily" not in line
    twin = artist_os.twin_report([], {"statement_rows": 0, "fans": 0,
                                      "live_links": 0}, [], [])
    said = " ".join(" ".join(s["lines"]) for s in twin)
    assert "popularity" not in said.lower() and "Deezer" not in said


def test_the_twin_reads_followers_without_waiting_for_popularity():
    """Spotify retired popularity; Soundcharts' follower readings carry
    none. The Twin's audience section waited for both and never came."""
    snaps = [{"followers": 1200, "popularity": None, "deezer_fans": None},
             {"followers": 1350, "popularity": None, "deezer_fans": None}]
    twin = artist_os.twin_report([], {"fans": 0, "live_links": 0}, snaps, [])
    audience = [s for s in twin if s["title"].startswith("Audience")][0]
    assert audience["state"] == "ready"
    assert "Followers 1200 → 1350 over your last 2 snapshots." in audience["lines"]


def test_the_profit_and_loss_line_says_what_the_page_reads():
    label, desc = _sidebar_line("revenue-os")
    assert label == "Profit & Loss"
    assert desc == "Statement income against the spending you log."


def test_the_twin_reads_the_soundcharts_follower_series_without_spotify(monkeypatch):
    """The live site has Soundcharts and no Spotify app keys. /pulse writes
    Soundcharts' dated follower series under the provider's own key, and
    the Twin read only the Spotify series, so its audience section waited
    for ever while its line said pinning the artist on Pulse would fill it.
    It reads the metrics provider's series when Spotify's has none."""
    import signal_providers as providers

    class _Metrics(providers.MusicIntelligenceProvider):
        key = "fakecharts"
        label = "Fakecharts"
        capabilities = (providers.CAP_ARTIST, providers.CAP_METRICS)

        def configured(self):
            return True

    providers.reset_registry(providers.ProviderRegistry(adapters=[_Metrics()]))
    try:
        client, uid = _client()
        store.record_pulse_snapshot(uid, 1200, None, None, provider="fakecharts",
                                    day="2026-09-01")
        store.record_pulse_snapshot(uid, 1350, None, None, provider="fakecharts",
                                    day="2026-09-20")
        body = client.get("/artist-twin").get_data(as_text=True)
        assert "Followers 1200 \u2192 1350 over your last 2 snapshots." in body
    finally:
        providers.reset_registry(None)

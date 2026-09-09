"""One source of truth: the cross-surface assertions.

Four facts about an account were stored in more than one table and
computed by more than one rule, so two pages could disagree about the
same artist. Each section below picks the surfaces a real person
actually compares - a press kit against a money page, a passport against
a catalog row - and asserts they say the same thing for the same
account.

The per-module rules live with their modules (catalog_value,
artist_identity, db.get_catalog_tracks). This file is where the pages
are held to them.
"""
import io as _io
import uuid

import pytest

from app import create_app

PASSWORD = "one-truth-123"

STATEMENT_CSV = "".join(line + "\n" for line in (
    "Track Title,Store,Net Revenue,Sales Period",
    "Midnight Drive,Spotify,120.50,2026-05",
    "Midnight Drive,Apple Music,80.25,2026-05",
    "Neon Dreams,Spotify,60.00,2026-06",
)).encode()


@pytest.fixture(scope="module")
def application():
    return create_app()


@pytest.fixture
def artist(application):
    """A fresh Pro account. Never the demo showcase: the whole point of
    these assertions is that the numbers belong to one real account."""
    import db as store

    email = "onetruth-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Vera Kane", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})
    with application.app_context():
        uid = store.get_user_by_email(email)["id"]
    return {"client": client, "uid": uid, "email": email}


def _upload_statements(client):
    r = client.post("/statements",
                    data={"statement": (_io.BytesIO(STATEMENT_CSV), "dist.csv")},
                    content_type="multipart/form-data")
    assert r.status_code == 302


# --- Finding 4: one catalog-value rule ----------------------------------------

def test_the_money_page_the_press_kit_and_benchmark_quote_one_valuation(artist):
    """Same account, same statements, three surfaces, one figure.

    /valuation used 3-5x, the press kit re-derived 3-5x from its own
    copy, and /benchmark applied 8/12/16x to an illustrative trend. A
    label reading the kit and the page saw two catalog values three
    times apart.
    """
    import benchmark_config
    import db as store
    import epk_config
    import valuation_engine

    _upload_statements(artist["client"])
    rows = store.get_statement_rows(artist["uid"])

    money = valuation_engine.build(artist["uid"])
    assert money["has_data"] and money["value"]["mid"] > 0

    kit = epk_config.real_stats(rows, track_count=0)
    kit_value = next(s for s in kit if s["label"] == "Est. Catalog Value")

    bench = benchmark_config.get_benchmark_data(rows)
    bench_value = next(m for m in bench["metrics"]
                       if m["label"] == "Est. catalog value")

    assert kit_value["value"] == "${:,.0f}".format(money["value"]["mid"])
    assert round(bench_value["you"]) == money["value"]["mid"]


def test_every_valuation_multiple_in_the_app_comes_from_one_module():
    """No second copy of the band, and no second opinion about it."""
    import catalog_value
    import royalty_data
    import statements_engine
    import valuation_engine

    assert valuation_engine.MULTIPLES is catalog_value.MULTIPLES
    assert royalty_data.CATALOG_VALUE_MULTIPLES is catalog_value.MULTIPLES
    summary = statements_engine.build_royalty_summary(
        [{"title": "T", "source": "S", "amount": 1000.0, "period": "2026-01"}])
    assert summary["valuation"] == catalog_value.band(12000.0)
    # The band the money pages show, not an average of the three that
    # used to be in the tree.
    assert catalog_value.MULTIPLES == {"low": 3, "mid": 4, "high": 5}


def test_the_valuation_page_renders_the_band_it_computed(artist):
    _upload_statements(artist["client"])
    import valuation_engine
    money = valuation_engine.build(artist["uid"])
    body = artist["client"].get("/valuation").get_data(as_text=True)
    assert "${:,.0f}".format(money["value"]["mid"]) in body
    assert "Catalog signal (mid, 4x)" in body
# --- Finding 1: one artist name -----------------------------------------------

ACT = "COLD FURNACE"


def _name_the_act(uid, name=ACT):
    """What connecting a profile does: bind the account to an act that has
    a provider id behind it."""
    import db as store
    store.save_pulse_profile(uid, "sp-artist-1", name)


def test_the_accessor_prefers_the_act_the_account_is_bound_to(artist):
    import artist_identity
    import db as store

    # Nothing connected: the signup box is all there is.
    assert artist_identity.name_for(artist["uid"]) == "Vera Kane"
    _name_the_act(artist["uid"])
    assert artist_identity.name_for(artist["uid"]) == ACT
    # Clearing the profile falls back rather than blanking the name.
    store.clear_pulse_profile(artist["uid"])
    assert artist_identity.name_for(artist["uid"]) == "Vera Kane"
    assert artist_identity.name_for("") == ""


def test_naming_the_act_once_changes_every_surface_that_shows_it(artist):
    """A person signs up as themselves and records as somebody else.

    Until this was one accessor, "Vera Kane" was offered to the press
    desk, introduced the artist twin and headlined the public press kit,
    while Pulse, Signal and the metrics provider all measured COLD
    FURNACE.
    """
    import artist_twin
    import db as store

    client = artist["client"]
    _name_the_act(artist["uid"])

    # Press Desk: the name offered on an announcement.
    body = client.get("/press-desk/announcements/new").get_data(as_text=True)
    assert ACT in body

    # The artist twin's own introduction.
    facts, _used = artist_twin.gather_context(artist["uid"], {"epk"})
    assert facts["name"] == ACT

    # The public press kit.
    store.save_epk(artist["uid"], {"tagline": "Loud rooms"})
    client.get("/epk")                      # mints the public address
    slug = (store.get_epk(artist["uid"]) or {}).get("slug")
    assert slug, "opening the kit mints its public address"
    assert store.get_epk_by_slug(slug)["user_name"] == ACT
    public = create_app().test_client().get("/epk/" + slug)
    assert public.status_code == 200 and ACT in public.get_data(as_text=True)


def test_the_kit_the_artist_edits_and_the_kit_a_label_opens_carry_one_name(artist):
    """The editor read the sidebar chip (users.name) and the public page
    read a join on users.name, so naming the act moved neither."""
    import db as store

    client = artist["client"]
    _name_the_act(artist["uid"])
    store.save_epk(artist["uid"], {"tagline": "Loud rooms"})
    editor = client.get("/epk").get_data(as_text=True)
    slug = (store.get_epk(artist["uid"]) or {}).get("slug")
    public = create_app().test_client().get("/epk/" + slug).get_data(as_text=True)
    assert ACT in editor and ACT in public


def test_a_new_tour_defaults_to_the_act_not_the_signup_box(artist):
    """artist_name stays per tour - a tour can be for another act - but
    the default offered is the one resolved name."""
    import tour_store

    _name_the_act(artist["uid"])
    r = artist["client"].post("/tours/new", data={
        "name": "Fall run", "start_date": "2026-10-01",
        "end_date": "2026-10-20", "home_tz": "UTC", "currency": "USD"})
    assert r.status_code == 302
    tours = tour_store.list_tours(artist["uid"])
    assert tours and tours[0]["artist_name"] == ACT


# --- Finding 2: one ISRC ------------------------------------------------------

ISRC = "USAIW2600777"


def test_an_isrc_typed_on_the_passport_is_the_one_catalog_shows(artist):
    """Catalog read `catalog_tracks.meta["isrc"]`, a second copy filled
    only by the Deezer lookup. A code the artist typed on the passport -
    the copy the MLC check asks with - was invisible on the catalog row,
    counted as a missing ISRC on the health card, and had to be entered
    twice."""
    import db as store

    client = artist["client"]
    client.post("/tracks/add", data={"title": "Night Drive",
                                     "release_title": "Midnight EP"})
    track = [t for t in store.list_os_tracks(artist["uid"])
             if t["title"] == "Night Drive"][0]
    assert (store.get_catalog_tracks(artist["uid"])[0].get("meta") or {}
            ).get("isrc") in (None, "")

    passport = track["passport"]
    passport["isrc"] = ISRC
    store.update_os_track_passport(artist["uid"], track["id"], passport)

    row = store.get_catalog_tracks(artist["uid"])[0]
    assert row["meta"]["isrc"] == ISRC
    assert row["passport_track_id"] == track["id"], "read through the link"

    body = client.get("/catalog").get_data(as_text=True)
    assert ISRC in body


def test_a_code_looked_up_on_the_catalog_side_reaches_the_mlc_check(artist):
    """The other direction, which already worked and must keep working:
    the passport is what recovery_mlc and the /tracks MLC button read."""
    import db as store

    artist["client"].post("/tracks/add", data={"title": "Cold Room"})
    track = [t for t in store.list_os_tracks(artist["uid"])
             if t["title"] == "Cold Room"][0]
    catalog_id = [c for c in store.get_catalog_tracks(artist["uid"])
                  if c["passport_track_id"] == track["id"]][0]["id"]

    store.set_catalog_track_meta(artist["uid"], catalog_id, {"isrc": ISRC})
    assert store.get_os_track(artist["uid"], track["id"])["passport"]["isrc"] == ISRC
    assert store.get_catalog_tracks(artist["uid"])[0]["meta"]["isrc"] == ISRC


def test_a_passport_code_never_loses_to_a_looked_up_one(artist):
    """A code the artist typed is a decision. A lookup fills an empty
    field and nothing else - in either direction."""
    import db as store

    artist["client"].post("/tracks/add", data={"title": "Hollow"})
    track = [t for t in store.list_os_tracks(artist["uid"])
             if t["title"] == "Hollow"][0]
    passport = track["passport"]
    passport["isrc"] = ISRC
    store.update_os_track_passport(artist["uid"], track["id"], passport)

    catalog_id = [c for c in store.get_catalog_tracks(artist["uid"])
                  if c["passport_track_id"] == track["id"]][0]["id"]
    store.set_catalog_track_meta(artist["uid"], catalog_id,
                                 {"isrc": "USAIW2600000", "label": "Ghost Rec"})

    assert store.get_os_track(artist["uid"], track["id"])["passport"]["isrc"] == ISRC
    row = [c for c in store.get_catalog_tracks(artist["uid"])
           if c["id"] == catalog_id][0]
    assert row["meta"]["isrc"] == ISRC, "one code, the artist's"
    # An empty passport field still learns from the lookup.
    assert row["meta"]["label"] == "Ghost Rec"


def test_nothing_still_calls_a_coded_track_uncoded(artist):
    """The health card and the Command Center alert both counted a track
    with a passport ISRC as missing one, because both read the second
    copy."""
    import command_center
    import db as store

    client = artist["client"]
    client.post("/tracks/add", data={"title": "Signal Fire"})
    track = [t for t in store.list_os_tracks(artist["uid"])
             if t["title"] == "Signal Fire"][0]
    alerts = command_center.build_alerts(artist["uid"])
    assert any("missing an ISRC" in a[1] for a in alerts)

    passport = track["passport"]
    passport["isrc"] = ISRC
    store.update_os_track_passport(artist["uid"], track["id"], passport)

    alerts = command_center.build_alerts(artist["uid"])
    assert not any("missing an ISRC" in a[1] for a in alerts)
    assert ISRC in client.get("/catalog").get_data(as_text=True)


# --- Finding 3: two follower series, on purpose --------------------------------

def test_the_two_audience_series_are_documented_as_separate(artist):
    """NOT consolidated (audit ruling, 2026-09-09).

    signal_metrics is keyed on a `signal_artists` roster row, which has no
    account column, so there is no link to read a per-user view through;
    and its writer replaces a provider's whole series on every ingest run.
    pulse_snapshots is now provider-stamped in its own primary key, which
    was the audit's only stated reason for preferring the other table.
    What must not happen is the duplication going unrecorded.
    """
    import inspect

    import db as store
    import signal_store

    source = inspect.getsource(store)
    i = source.index("def record_pulse_snapshot")
    assert "signal_metrics" in source[max(0, i - 2500):i], (
        "the pulse series must say why it is not the signal one")
    assert "pulse_snapshots" in inspect.getdoc(signal_store.replace_metrics)

    # And the thing that made them look alike is gone: both are attributed.
    store.record_pulse_snapshot(artist["uid"], 100, 10, 0, provider="spotify")
    store.record_pulse_snapshot(artist["uid"], 900, 10, 0, provider="soundcharts")
    spotify = store.list_pulse_snapshots(artist["uid"], provider="spotify")
    assert [s["followers"] for s in spotify] == [100], (
        "trust_score, insights_engine, qualification and twin_report read "
        "this series and must keep meaning the same thing")

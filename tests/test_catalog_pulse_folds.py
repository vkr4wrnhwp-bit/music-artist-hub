"""Two more pages folded into the one that already had their data.

/identifiers rendered the catalog's own records a second time, read for
their codes. /stats rendered Artist Pulse's own numbers a second time -
the same followers, popularity, Deezer fans and snapshot history - plus
one section of owned link engagement. Each is now a section of the page
it duplicated, the old URL forwards, and the nav has one entry fewer.
"""
import io
import os
import uuid

import pytest

import app as appmod

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "fold-tests-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def artist(application):
    """A fresh pro account (the catalog is a pro page) with two catalog
    records: one carrying real codes, one carrying none."""
    import db as store

    email = "fold-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Fold Tester", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})
    with application.app_context():
        uid = store.get_user_by_email(email)["id"]
        coded = store.add_catalog_track(uid, {"title": "Coded Song",
                                              "artist": "Fold Tester"})
        store.set_catalog_track_meta(uid, coded, {"isrc": "USSB12600077",
                                                  "upc": "198000000077",
                                                  "label": "Fold Records"})
        store.add_catalog_track(uid, {"title": "Bare Song", "artist": "Fold Tester"})
    return {"client": client, "uid": uid}


# --- the old doors -------------------------------------------------------------

def test_identifiers_forwards_to_the_catalog_section(artist):
    r = artist["client"].get("/identifiers")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/catalog#identifiers")


def test_stats_forwards_to_the_pulse_section(artist):
    r = artist["client"].get("/stats")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/pulse#engagement")


def test_nothing_points_at_the_folded_pages_any_more():
    import glob
    import inspect

    import artist_os
    import hubs
    import insights_engine

    keys = {k for _hk, _n, _t, items in hubs.HUBS for k, *_ in items}
    assert "identifiers" not in keys and "stats" not in keys
    assert "identifiers" not in hubs.LIVE_KEYS and "stats" not in hubs.LIVE_KEYS
    stale = []
    for p in glob.glob(os.path.join(HERE, "templates", "**", "*.html"),
                       recursive=True):
        s = io.open(p, encoding="utf-8").read()
        if 'href="/identifiers"' in s or 'href="/stats"' in s:
            stale.append(os.path.basename(p))
    assert stale == [], stale
    for name in ("identifiers.html", "stats.html"):
        assert not os.path.exists(os.path.join(HERE, "templates", name)), name
    # The two links that lived in code rather than templates.
    assert '"/stats"' not in inspect.getsource(insights_engine)
    assert all(link != "/identifiers" for *_, link in artist_os.PASSPORT_FIELDS)
    assert any(link == "/catalog#identifiers" for *_, link in artist_os.PASSPORT_FIELDS)


# --- identifiers, on the catalog ---------------------------------------------------

def test_the_codes_sit_beside_their_records(artist):
    body = artist["client"].get("/catalog").get_data(as_text=True)
    assert 'id="identifiers"' in body and "Your Identifiers" in body
    assert "USSB12600077" in body and "198000000077" in body
    assert "Fold Records" in body


def test_coverage_is_a_meter_counted_from_the_records(artist):
    body = artist["client"].get("/catalog").get_data(as_text=True)
    assert 'aria-label="ISRC (recordings): 1/2"' in body
    assert 'aria-label="UPC (releases): 1/2"' in body


def test_the_iswc_meter_says_it_is_not_pulled_rather_than_reading_empty(artist):
    """Nothing this app reads fetches an ISWC. An empty meter would read as
    zero works registered, which is a claim; "not pulled" is the truth."""
    body = artist["client"].get("/catalog").get_data(as_text=True)
    assert 'aria-label="ISWC (works): Not pulled"' in body
    assert "sb-meter--none" in body


def test_a_missing_isrc_is_a_word_and_an_action(artist):
    body = artist["client"].get("/catalog").get_data(as_text=True)
    assert 'sb-lamp--crit">MISSING' in body
    assert 'value="Resolve 1 missing ISRC(s) in catalog"' in body


def test_the_registration_rings_read_the_real_percentage(artist):
    """Found while folding: the Registered / Unregistered rings were drawn
    at 82% and 17% for every account - constants, beside the real count.
    One track of two carries an ISRC, so the rings are 50 and 50."""
    body = artist["client"].get("/catalog").get_data(as_text=True)
    rings = body.split('id="identifiers"')[1]
    assert rings.count(">50%</div>") == 2
    assert "82%" not in body and "17%" not in body


def test_an_empty_catalog_does_not_pretend_to_measure(application):
    import db as store

    email = "fold-empty-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Empty", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})
    body = client.get("/catalog").get_data(as_text=True)
    assert 'aria-label="ISRC (recordings): No tracks"' in body
    assert "MISSING" not in body.split('id="identifiers"')[1].split("</section>")[0]


# --- engagement, on the pulse ---------------------------------------------------------

def test_link_engagement_shows_without_spotify(artist, monkeypatch):
    """First-party counts from the artist's own smart links do not depend
    on a Spotify credential, so they show in the Not Connected state too."""
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
    body = artist["client"].get("/pulse").get_data(as_text=True)
    assert "Not Connected" in body
    assert 'id="engagement"' in body and "Your Link Engagement" in body
    for cap in ("page views", "platform clicks", "pre-saves"):
        assert cap + "</span>" in body, cap


def test_link_engagement_counts_the_artists_own_links(artist):
    import links_store as mls

    with artist["client"].application.app_context():
        cid = mls.create_campaign(artist["uid"], "fold-%s" % uuid.uuid4().hex[:6],
                                  {"title": "Counted Drop"})
        mls.track(cid, "pageview")
        mls.track(cid, "pageview")
        mls.track(cid, "click", service_key="spotify")
    body = artist["client"].get("/pulse").get_data(as_text=True)
    section = body.split('id="engagement"')[1].split("</section>")[0]
    assert '<span class="sb-lcd-v">2</span>' in section
    assert '<span class="sb-lcd-v">1</span>' in section

"""Signal admin: find a real artist by name, add them, retire the demo.

With a real identity provider a blank search is empty on purpose, so the
board kept showing the mock's fictional universe with no way to add a real
act or clear the demo rows. These tests drive the two admin routes that fix
that against a fake real provider, and pin the two honesty points: a blank
query calls nobody, and the demo universe cannot be retired into an empty
product.
"""
import uuid

import pytest

import app as appmod
import db as store
import signal_ingest as ingest
import signal_providers as providers
import signal_store as sstore

PASSWORD = "signal-admin-123"
DEVORA_ID = "fake-devora-1"
DEVORA = {"provider_artist_id": DEVORA_ID, "name": "Devora", "genre": "Alternative",
          "country": "US", "city": "Charlotte", "state": "", "region": "",
          "career_stage": "Emerging", "monthly_listeners": None,
          "image_url": "https://img.example.net/devora.jpg", "website": "",
          "socials": {"instagram": "", "tiktok": "", "youtube": ""}}


class FakeReal(providers.MusicIntelligenceProvider):
    """A configured identity-only provider. It answers one name and records
    every call, so a test can assert that a blank query cost nothing."""
    key = "fakereal"
    label = "Fake real provider"
    capabilities = (providers.CAP_ARTIST,)

    def __init__(self):
        self.calls = []

    def configured(self):
        return True

    def health_check(self):
        return {"provider": self.key, "configured": True, "ok": True,
                "detail": "test double", "capabilities": list(self.capabilities)}

    def search_artists(self, query, limit=20):
        self.calls.append(("search", query, limit))
        if (query or "").strip().lower() == "devora":
            return [dict(DEVORA)]
        return []

    def get_artist(self, provider_artist_id):
        self.calls.append(("get", provider_artist_id))
        return dict(DEVORA) if provider_artist_id == DEVORA_ID else None


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _user(flask_app, label="Admin", role="owner"):
    email = "sig-adm-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": label, "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    user = store.get_user_by_email(email)
    org = sstore.default_org()
    if role:
        sstore.upsert_member(org["id"], email, label, role, user_id=user["id"])
    return client, user, org


def _mock_universe(n=5):
    """Seed the fictional universe the way the product does when nothing
    real is configured, then leave a real provider in charge. Starts from
    an empty universe so counts are exact."""
    sstore.retire_artists([a["id"] for a in sstore.list_artists()])
    providers.reset_registry(providers.ProviderRegistry(adapters=[]))
    ingest.refresh_universe(max_artists=n, force=True)
    fake = FakeReal()
    providers.reset_registry(providers.ProviderRegistry(adapters=[fake]))
    return fake


def _mock_ids():
    return sstore.artists_seeded_by("mock")


def _rows(table, artist_ids, col="artist_id"):
    if not artist_ids:
        return 0
    marks = ",".join("?" * len(artist_ids))
    with store.get_db() as db:
        return db.execute("SELECT COUNT(*) AS n FROM %s WHERE %s IN (%s)" % (table, col, marks),
                          list(artist_ids)).fetchone()["n"]


# --- permission -------------------------------------------------------------

def test_a_viewer_cannot_find_add_or_retire(flask_app):
    _mock_universe()
    viewer, _, _ = _user(flask_app, "Viewer", role="viewer")
    assert viewer.get("/signal/admin/find?q=devora").status_code == 403
    assert viewer.post("/signal/admin/add", data={"provider_artist_id": DEVORA_ID}).status_code == 403
    assert viewer.post("/signal/admin/retire-demo").status_code == 403
    scout, _, _ = _user(flask_app, "Scout", role="scout")
    assert scout.get("/signal/admin/find?q=devora").status_code == 403


# --- find -------------------------------------------------------------------

def test_a_blank_query_renders_the_page_and_calls_nobody(flask_app):
    fake = _mock_universe()
    client, _, _ = _user(flask_app)
    for q in ("", "   "):
        r = client.get("/signal/admin/find?q=%s" % q)
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert "Add to Signal" not in body and "No artist named" not in body
    assert fake.calls == [], "a blank search must not reach the provider"


def test_find_renders_the_provider_s_results_with_an_add_form(flask_app):
    fake = _mock_universe()
    client, _, _ = _user(flask_app)
    r = client.get("/signal/admin/find?q=devora")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert fake.calls == [("search", "devora", 10)]
    assert "<b>Devora</b>" in body
    assert "<code>%s</code>" % DEVORA_ID in body
    assert 'src="https://img.example.net/devora.jpg"' in body
    assert "Alternative · US" in body
    assert 'action="/signal/admin/add"' in body
    assert 'name="provider_artist_id" value="%s"' % DEVORA_ID in body
    assert "Add to Signal" in body
    # the search form keeps the query and names the provider it asked
    assert 'value="devora"' in body and "Search Fake real provider" in body
    # a real provider is serving identity, so the page does not call it demo
    assert "serving this search is the demo adapter" not in body
    # the call is on the usage table like every other provider call
    assert any(u["provider"] == "fakereal" for u in sstore.provider_usage())


def test_a_name_nobody_has_says_so(flask_app):
    _mock_universe()
    client, _, _ = _user(flask_app)
    body = client.get("/signal/admin/find?q=nobody+here").get_data(as_text=True)
    assert "No artist named" in body and "nobody here" in body
    assert "Add to Signal" not in body


def test_with_the_mock_in_charge_the_search_works_and_the_page_says_so(flask_app):
    providers.reset_registry(providers.ProviderRegistry(adapters=[]))
    ingest.refresh_universe(max_artists=3, force=True)
    client, _, _ = _user(flask_app)
    mock = providers.registry().mock
    name = mock.get_artist("mock-a01")["name"]
    body = client.get("/signal/admin/find?q=%s" % name.split()[0]).get_data(as_text=True)
    assert "Add to Signal" in body
    assert "serving this search is the demo adapter" in body and "fictional" in body
    assert "re-seeds the fictional demo universe" in body


def test_the_owner_s_own_acts_are_suggested_as_links_not_lookups(flask_app):
    import tour_store
    fake = _mock_universe()
    client, user, _ = _user(flask_app, "Kit Owner")
    tour_store.create_tour(user["id"], {"name": "Fall run", "artist_name": "Devora"})
    tour_store.create_tour(user["id"], {"name": "Spring run", "artist_name": "devora"})
    tour_store.create_tour(user["id"], {"name": "Side gig", "artist_name": "Night Owls & Co"})
    body = client.get("/signal/admin/data-sources").get_data(as_text=True)
    assert "Suggested: your own acts" in body
    assert 'href="/signal/admin/find?q=Devora"' in body
    assert body.count("/signal/admin/find?q=") == 2, "distinct names, case-insensitively"
    assert 'href="/signal/admin/find?q=Night%20Owls%20%26%20Co"' in body
    assert fake.calls == [], "suggestions are links; nothing is fetched until clicked"


# --- add --------------------------------------------------------------------

def test_add_ingests_the_artist_and_redirects_to_their_page(flask_app):
    fake = _mock_universe()
    client, _, _ = _user(flask_app)
    r = client.post("/signal/admin/add", data={"provider_artist_id": DEVORA_ID})
    assert r.status_code in (302, 303)
    loc = r.headers["Location"]
    assert "/signal/artist/" in loc
    artist_id = loc.rsplit("/signal/artist/", 1)[1].split("?")[0]
    a = sstore.get_artist(artist_id)
    assert a and a["canonical_name"] == "Devora" and a["country"] == "US"
    assert {"provider": "fakereal", "provider_id": DEVORA_ID} in sstore.provider_ids(artist_id)
    assert ("get", DEVORA_ID) in fake.calls
    assert sstore.latest_scores(artist_id), "an added artist is scored like any other"
    assert client.get(loc).status_code == 200
    # no number was invented for a provider that measures none
    assert a["monthly_listeners"] == 0 or a["monthly_listeners"] is None


def test_add_with_an_unknown_id_writes_nothing_and_says_so(flask_app):
    _mock_universe()
    client, _, _ = _user(flask_app)
    before = sstore.counts()["artists"]
    r = client.post("/signal/admin/add", data={"provider_artist_id": "no-such-id"})
    assert r.status_code in (302, 303) and "notice=add-failed" in r.headers["Location"]
    assert sstore.counts()["artists"] == before
    assert "Not added" in client.get(r.headers["Location"]).get_data(as_text=True)
    assert client.post("/signal/admin/add", data={}).status_code == 400


# --- retire -----------------------------------------------------------------

def test_retire_is_refused_while_the_universe_is_mock_only(flask_app):
    _mock_universe(4)
    assert sstore.count_artists_not_seeded_by("mock") == 0
    client, _, _ = _user(flask_app)
    n = len(_mock_ids())
    assert n == 4
    page = client.get("/signal/admin/data-sources").get_data(as_text=True)
    assert "Retire the demo universe · 4 fictional artists" in page
    assert 'disabled title="Add one real artist first"' in page
    r = client.post("/signal/admin/retire-demo")
    assert r.status_code in (302, 303) and "notice=retire-blocked" in r.headers["Location"]
    assert len(_mock_ids()) == n, "nothing was deleted"
    assert "Add one real artist first" in client.get(r.headers["Location"]).get_data(as_text=True)
    assert sstore.seeded_by("mock") is True


def test_retire_deletes_every_mock_artist_and_their_rows_and_keeps_the_real_one(flask_app):
    _mock_universe(5)
    client, user, org = _user(flask_app)
    mock_ids = _mock_ids()
    assert len(mock_ids) == 5
    # hang tenant rows off a fictional artist so the cascade is exercised
    victim = mock_ids[0]
    wl = sstore.ensure_watchlist(org["id"], "Retire me", "Admin")
    sstore.add_to_watchlist(org["id"], wl, victim, "Admin")
    sstore.raise_alert(org["id"], "momentum_above", "fictional alert", artist_id=victim)
    sstore.link_to_desk(org["id"], victim, "lead-x", {}, "v", "why", "Admin")
    for table in ("signal_metrics", "signal_releases", "signal_city_metrics", "signal_scores",
                  "signal_artist_ids", "signal_watch_items", "signal_alerts", "signal_desk_links"):
        assert _rows(table, mock_ids) > 0, "%s has nothing to delete - the test proves nothing" % table
    assert _rows("signal_evidence", mock_ids, col="subject_id") > 0

    # the fold is armed only once a real artist exists
    page = client.get("/signal/admin/data-sources").get_data(as_text=True)
    assert 'disabled title="Add one real artist first"' in page
    r = client.post("/signal/admin/add", data={"provider_artist_id": DEVORA_ID})
    real_id = r.headers["Location"].rsplit("/signal/artist/", 1)[1]
    page = client.get("/signal/admin/data-sources").get_data(as_text=True)
    assert "Retire the demo universe · 5 fictional artists" in page
    assert "Add one real artist first" not in page
    assert client.get("/signal").get_data(as_text=True).count("Demo data") == 1

    r = client.post("/signal/admin/retire-demo")
    assert r.status_code in (302, 303) and "notice=retired-5" in r.headers["Location"]

    assert _mock_ids() == [] and sstore.seeded_by("mock") is False
    for table in ("signal_metrics", "signal_releases", "signal_city_metrics", "signal_scores",
                  "signal_artist_ids", "signal_watch_items", "signal_alerts", "signal_desk_links"):
        assert _rows(table, mock_ids) == 0, table
    assert _rows("signal_evidence", mock_ids, col="subject_id") == 0
    assert _rows("signal_artists", mock_ids, col="id") == 0
    assert all(sstore.get_artist(i) is None for i in mock_ids)

    real = sstore.get_artist(real_id)
    assert real and real["canonical_name"] == "Devora"
    assert sstore.latest_scores(real_id)
    body = client.get("/signal").get_data(as_text=True)
    assert body.count("Demo data") == 0 and "Devora" in body
    after = client.get(r.headers["Location"]).get_data(as_text=True)
    assert "Demo universe retired" in after and "Retire the demo universe" not in after
    assert "re-pulls the artists already tracked and adds none" in after


def test_retire_artists_never_takes_a_real_artist_that_shares_a_mock_id():
    """upsert_artist name-matches across providers, so one canonical row
    can carry a mock id AND a real one. That row is a real artist the mock
    happened to name; it is not in the retire set."""
    providers.reset_registry(providers.ProviderRegistry(adapters=[FakeReal()]))
    shared = sstore.upsert_artist("mock", "mock-shared-%s" % uuid.uuid4().hex[:6],
                                  {"name": "Shared Name %s" % uuid.uuid4().hex[:6]})
    name = sstore.get_artist(shared)["canonical_name"]
    also = sstore.upsert_artist("fakereal", "real-shared", {"name": name})
    assert also == shared
    assert shared not in sstore.artists_seeded_by("mock")
    assert sstore.count_artists_not_seeded_by("mock") >= 1
    assert sstore.retire_artists([]) == 0
    sstore.retire_artists([shared])
    assert sstore.get_artist(shared) is None

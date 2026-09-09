"""The headline strip on a press kit, on all three of its doors.

`epk_config.real_stats` only ever emitted money and a release count, and
two of the three routes that render a kit passed no `stats_override` at
all - so the demo catalogue's Total Streams, Catalog Earnings and Est.
Catalog Value rendered in gold over a real artist's name, on a page whose
whole purpose is to leave the building.

What has to hold now: one helper feeds the editor, the public slug and
the private pitch link; audience figures from whatever the registry has
for CAP_METRICS count as real without a single statement; a public kit
never spends the artist's provider quota on a stranger's page load; and a
private pitch link for a real account shows "Not measured" rather than
somebody else's totals.
"""
import uuid

import pytest

import db as store
import epk_config
import signal_providers as providers
from app import create_app

PASSWORD = "epk-stats-123"


class FakeMetrics(providers.MusicIntelligenceProvider):
    """A configured CAP_ARTIST + CAP_METRICS provider that reaches no
    network and counts what it is asked."""

    key = "fakecharts"
    label = "FakeCharts"
    capabilities = (providers.CAP_ARTIST, providers.CAP_METRICS)

    def __init__(self):
        self.searches = self.metric_calls = 0

    def configured(self):
        return True

    def search_artists(self, query, limit=20):
        self.searches += 1
        return [{"provider_artist_id": "fc-1", "name": query}]

    def get_artist_metrics(self, provider_artist_id, start, end):
        self.metric_calls += 1
        return [{"date": "2026-09-08", "metric": "spotify_monthly_listeners",
                 "value": 61200},
                {"date": "2026-09-08", "metric": "spotify_followers", "value": 4310}]


@pytest.fixture
def app_obj():
    return create_app()


@pytest.fixture
def artist(app_obj):
    """A real (non-demo) account with a saved kit and a pitch link."""
    email = "epkstats-%s@example.net" % uuid.uuid4().hex[:10]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Vera Sound", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    uid = store.get_user_by_email(email)["id"]
    client.post("/epk/save", json={"tagline": "Nocturne pop", "bio": "A bio."})
    client.get("/epk")                       # mints the public slug
    token = uuid.uuid4().hex[:20]
    store.upsert_epk_share(uid, token, "", "", [])
    return {"client": client, "uid": uid, "token": token,
            "slug": store.get_epk(uid)["slug"]}


@pytest.fixture
def measured():
    """A real metrics provider, with a reading already on file - which is
    what a public kit reads, because it must not fetch."""
    fake = FakeMetrics()
    providers.reset_registry(providers.ProviderRegistry(adapters=[fake]))
    yield fake
    providers.reset_registry(None)


def _seed_reading(uid, listeners=61200, followers=4310):
    store.save_pulse_profile(uid, "sp-1", "Vera Sound")
    store.save_pulse_provider_artist(uid, "fakecharts", "fc-1")
    store.record_pulse_snapshot(uid, followers, 0, 0, provider="fakecharts",
                                day="2026-09-08", monthly_listeners=listeners)


# --- the private pitch link ------------------------------------------------------

def test_a_pitch_link_for_a_real_account_never_shows_the_demo_totals(artist):
    """This link goes to one named person who asked for it. A demo
    catalogue's figures there are not an illustration; they are a claim
    about this artist."""
    anon = artist["client"].application.test_client()
    body = anon.get("/pitch/" + artist["token"]).get_data(as_text=True)
    assert body.count("Not measured") >= 2
    assert "Sample metrics" not in body
    assert "Total Streams" not in body and "Est. Catalog Value" not in body
    assert "Monthly Listeners" in body and "No metrics provider connected" in body


def test_a_pitch_link_shows_what_the_registry_measured(artist, measured):
    _seed_reading(artist["uid"])
    anon = artist["client"].application.test_client()
    body = anon.get("/pitch/" + artist["token"]).get_data(as_text=True)
    assert "61,200" in body and "Monthly Listeners" in body
    assert "Measured by FakeCharts" in body
    assert "Not measured" not in body.split("Media Assets")[0]
    assert "Sample metrics" not in body


def test_a_public_kit_never_spends_the_artists_provider_quota(artist, measured):
    """A stranger opening a link must not bill the artist, and a press
    kit is not the place to discover a vendor is down."""
    _seed_reading(artist["uid"])
    anon = artist["client"].application.test_client()
    anon.get("/pitch/" + artist["token"])
    anon.get("/epk/" + artist["slug"])
    assert measured.metric_calls == 0 and measured.searches == 0


# --- the editor and the public slug ----------------------------------------------

def test_the_editor_and_the_slug_read_the_same_helper(artist, measured):
    _seed_reading(artist["uid"])
    editor = artist["client"].get("/epk").get_data(as_text=True)
    assert "61,200" in editor and "Monthly Listeners" in editor
    assert "Sample figures" not in editor
    public = artist["client"].get("/epk/" + artist["slug"]).get_data(as_text=True)
    assert "61,200" in public


def test_an_empty_real_account_keeps_the_sample_strip_but_labels_it(artist):
    """The editor is the artist's own workspace, so the demo strip still
    stands in there - as long as the banner under it says so."""
    body = artist["client"].get("/epk").get_data(as_text=True)
    assert "Sample figures" in body


# --- the figures themselves -------------------------------------------------------

def test_audience_alone_makes_the_figures_real():
    """Before this, `stats_are_real` could only be earned by uploading a
    royalty statement, so an artist with a live audience and no paperwork
    was shown somebody else's career."""
    stats = epk_config.real_stats([], 0, metrics={
        "label": "FakeCharts", "monthly_listeners": 61200, "followers": 4310})
    assert [s["label"] for s in stats] == ["Monthly Listeners", "Followers"]
    assert stats[0]["value"] == "61,200" and stats[1]["value"] == "4,310"
    assert all(s["sub"] == "Measured by FakeCharts" for s in stats)
    data = epk_config.get_epk_data({"name": "V", "initials": "V"},
                                   {"mid": 0, "low": 0, "high": 0},
                                   stats_override=stats)
    assert data["stats_are_real"] is True and data["stats_are_sample"] is False


def test_audience_leads_the_strip_because_the_cover_shows_two():
    """epk_public renders stats[:2] across the cover. The two a label
    opens a kit for are the audience ones."""
    stats = epk_config.real_stats(
        [{"title": "A", "source": "Spotify", "amount": 100.0, "period": "2026-01"}],
        3, metrics={"label": "FakeCharts", "monthly_listeners": 10, "followers": 20})
    assert [s["label"] for s in stats[:2]] == ["Monthly Listeners", "Followers"]
    assert "Releases" in [s["label"] for s in stats]


def test_a_provider_that_measured_nothing_adds_nothing():
    assert epk_config.real_stats([], 0, metrics={"label": "FakeCharts",
                                                 "monthly_listeners": None,
                                                 "followers": None}) == []
    assert epk_config.real_stats([], 0, metrics=None) == []


def test_not_measured_is_a_state_of_its_own_not_a_sample():
    """Reading the sample banner off `not stats_are_real` made a kit with
    nothing measured accuse itself of showing somebody else's numbers."""
    data = epk_config.get_epk_data({"name": "V", "initials": "V"},
                                   {"mid": 0, "low": 0, "high": 0},
                                   stats_override=epk_config.not_measured_stats())
    assert data["stats_are_real"] is False and data["stats_are_sample"] is False
    assert all(s["value"] == "Not measured" for s in data["stats"])
    sample = epk_config.get_epk_data({"name": "V", "initials": "V"},
                                     {"mid": 1, "low": 1, "high": 1}, demo=True)
    assert sample["stats_are_sample"] is True and sample["stats_are_real"] is False

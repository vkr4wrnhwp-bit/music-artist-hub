"""Everything Soundcharts holds on the Pulse artist (owner, 2026-09-14:
"i want everything it can pull on the artist pulse").

The canned wire below answers in the shapes their public sandbox gave on
that day, trimmed. Each of the nine questions is its own call and its own
failure: a platform the plan refuses reads "Not in the plan", one they
hold nothing for reads "Nothing on file", and a counter they left out is a
dash, never a zero.
"""
import json
import uuid
from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest

import db as store
import pulse_everything
import signal_providers as providers
from signal_providers import ProviderError

A = "11e81bcc-9c1c-ce38-b96b-a0369fe50396"
PW = "everything-123"


def _aud(day, followers, **extra):
    d = {"date": "%sT00:00:00+00:00" % day, "likeCount": None, "followerCount": followers,
         "followingCount": None, "postCount": None, "viewCount": None}
    d.update(extra)
    return d


class Wire(object):
    """Every Soundcharts answer the section needs, by path."""

    def __init__(self, refuse=(), empty=()):
        self.calls = []
        self.refuse = set(refuse)
        self.empty = set(empty)

    def __call__(self, url):
        self.calls.append(url)
        u = urlparse(url)
        p = u.path
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        for needle in self.refuse:
            if needle in p:
                raise ProviderError("Soundcharts 403: Not in your plan.")
        for needle in self.empty:
            if needle in p:
                return {"items": [], "page": {"total": 0, "next": None}}
        if p == "/api/v2.9/artist/%s" % A:
            return {"object": {"uuid": A, "name": "Billie Eilish", "imageUrl": "https://img.test/b.jpg",
                               "webUrl": "http://www.billieeilish.com/", "appUrl": "https://app.soundcharts.com/app/artist/billie-eilish/overview",
                               "countryCode": "US", "cityName": "Los Angeles",
                               "genres": [{"root": "pop", "sub": ["pop"]}, {"root": "alternative", "sub": ["alternative"]}],
                               "biography": "A short life.", "isni": "000000046748058X", "ipi": "00792187700",
                               "type": "person", "careerStage": "superstar", "growthLevel": "average_growth"}}
        if "/audience/" in p and p.endswith("/report/latest"):
            platform = p.split("/audience/")[1].split("/")[0]
            return {"object": {
                "userProfile": {"fullName": "BILLIE EILISH", "verified": True, "ageGroup": "25-34", "gender": "FEMALE",
                                "geo": {"country": {"code": "US", "name": "United States"}}, "language": {"name": "English"}},
                "top": {"posts": [{"likeCount": 16369961, "commentCount": 85162, "viewCount": 0, "shareCount": 446141,
                                   "date": "2025-02-12T04:21:26+00:00", "url": "https://www.instagram.com/p/x"}],
                        "hashtags": [{"code": "magicmountain", "weight": 0.5}], "mentions": [{"code": "finneas", "weight": 0.1}],
                        "recentPosts": []},
                "audience": {"stats": {"followerCount": 124103562, "postCount": 1059, "engagementRate": 0.018528,
                                       "averageLikesPerPost": 2299351, "averageCommentsPerPost": 12765,
                                       "averageViewsPerPost": 0, "averageReelsPlays": 26857059},
                             "audienceFollower": {"genders": [{"code": "FEMALE", "weight": 0.704556}, {"code": "MALE", "weight": 0.295444}],
                                                  "ages": [{"code": "18-24", "weight": 0.497303}, {"code": "25-34", "weight": 0.344372}],
                                                  "countries": [{"code": "US", "name": "United States", "weight": 0.31}],
                                                  "cities": [], "languages": []},
                             "interests": ["Music", "Sports"], "brandsAffinity": ["Apple", "Converse"]}}}
        if "/audience/" in p:
            platform = p.rsplit("/", 1)[1]
            if platform == "tiktok":
                return {"items": [], "page": {"next": None}}
            base = {"spotify": 33404686, "deezer": 3492165, "soundcloud": 1370376, "youtube": 34300000,
                    "instagram": 67072519, "facebook": 20000000, "twitter": 5000000}[platform]
            items = [_aud("2020-10-01", base), _aud("2020-10-03", base + 1000),
                     _aud("2020-10-10", base + 3000, **({"postCount": 395, "viewCount": 1708951024} if platform == "youtube" else {}))]
            return {"items": items, "page": {"next": None}}
        if "/playlist/current/" in p:
            platform = p.rsplit("/", 1)[1]
            return {"items": [{"playlist": {"name": "Running & Gym & Cardio", "type": "Curators & Listeners",
                                            "latestSubscriberCount": 922, "platform": platform},
                               "position": 2, "peakPosition": 1, "entryDate": "2021-09-10T00:00:00+00:00",
                               "song": {"name": "bad guy"}},
                              {"playlist": {"name": "New Music Friday", "type": "editorial", "latestSubscriberCount": 4000000},
                               "position": 9, "peakPosition": 3, "entryDate": "2026-09-05T00:00:00+00:00", "song": {"name": "Narrow"}}],
                    "page": {"total": 768810 if platform == "spotify" else 446, "next": None}}
        if p.endswith("/related"):
            return {"items": [{"uuid": "r1", "name": "Lana Del Rey", "appUrl": "https://app.soundcharts.com/app/artist/lana-del-rey/overview", "imageUrl": ""},
                              {"uuid": "r2", "name": "Adele", "appUrl": "", "imageUrl": ""}]}
        if p.endswith("/identifiers"):
            return {"items": [{"platformName": "AllMusic", "platformCode": "allmusic", "url": "https://www.allmusic.com/artist/mn0003475903", "verified": False},
                              {"platformName": "Spotify", "platformCode": "spotify", "url": "https://open.spotify.com/artist/6qqNVTkY8uBg9cP3Jd7DAH", "verified": True},
                              {"platformName": "ISNI", "platformCode": "isni", "url": "", "verified": False},
                              {"platformName": "Spotify", "platformCode": "spotify", "url": "https://open.spotify.com/artist/dup", "verified": False}],
                    "page": {"next": None}}
        if p.endswith("/broadcast-groups"):
            return {"items": [{"playCount": 189, "radio": {"name": "XHITZ", "cityName": "San Diego, CA", "countryCode": "US"}},
                              {"playCount": 112, "radio": {"name": "KIIS", "cityName": "Los Angeles, CA", "countryCode": "US"}}],
                    "page": {"total": 1159, "next": None}}
        if p.endswith("/broadcasts"):
            return {"items": [{"song": {"name": "bad guy"}, "radio": {"name": "WPIA-FM", "cityName": "Eureka, CA", "countryCode": "US"},
                               "airedAt": "2026-09-15T06:11:00+00:00"}],
                    "page": {"total": 23747, "next": None}}
        if p.endswith("/streaming/youtube/listening"):
            return {"items": [{"date": "2020-10-10T00:00:00+00:00", "value": 10355797},
                              {"date": "2020-10-09T00:00:00+00:00", "value": 10726228},
                              {"date": "2020-10-08T00:00:00+00:00", "value": 9900000}],
                    "page": {"next": None}}
        if p.endswith("/songs"):
            return {"items": [{"uuid": "s1", "name": "What Was I Made For?", "creditName": "Billie Eilish", "releaseDate": "2026-06-04T00:00:00+00:00", "imageUrl": ""},
                              {"uuid": "s2", "name": "bad guy", "creditName": "Billie Eilish", "releaseDate": "2019-03-29T00:00:00+00:00", "imageUrl": ""}],
                    "page": {"total": 299, "next": None}}
        if p.endswith("/streaming/spotify/listening"):
            return {"items": [{"date": "2020-10-10T00:00:00+00:00", "value": 62000000}], "page": {"next": None}}
        if "/artist/search/" in p:
            return {"items": [{"uuid": A, "name": "Billie Eilish", "imageUrl": ""}]}
        raise AssertionError("unexpected call " + url)


@pytest.fixture
def sc(monkeypatch):
    monkeypatch.setenv("SOUNDCHARTS_ENABLED", "1")
    monkeypatch.setenv("SOUNDCHARTS_APP_ID", "app")
    monkeypatch.setenv("SOUNDCHARTS_API_KEY", "key")
    monkeypatch.setenv("SOUNDCHARTS_CACHE_S", "0")
    for k in ("SOUNDCHARTS_CLIENT_ID", "SOUNDCHARTS_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)

    def make(**kw):
        wire = Wire(**kw)
        return providers.SoundchartsAdapter(fetch=wire), wire
    return make


def test_the_nine_questions_come_back_in_plain_shapes(sc):
    adapter, wire = sc()
    ev = pulse_everything.build(adapter, A, today=date(2020, 10, 10))
    assert ev["label"] == "Soundcharts" and ev["refused"] == [] and ev["failed"] == []
    assert ev["profile"]["genres"] == ["pop", "alternative"] and ev["profile"]["career_stage"] == "superstar"
    assert ev["profile"]["growth_level"] == "average growth" and ev["profile"]["city"] == "Los Angeles"
    by = {r["platform"]: r for r in ev["audience_rows"]}
    assert by["spotify"]["state"] == "measured" and by["spotify"]["followers"] == 33407686
    assert by["spotify"]["change_7d_pct"] == 0.01 and by["spotify"]["change_28d_pct"] is None
    assert by["youtube"]["posts"] == 395 and by["youtube"]["views"] == 1708951024
    assert by["tiktok"]["state"] == "empty" and by["tiktok"].get("followers") is None
    assert by["twitter"]["name"] == "X (Twitter)"
    pl = {r["platform"]: r for r in ev["playlist_rows"]}
    assert pl["spotify"]["total"] == 768810 and pl["apple-music"]["name"] == "Apple Music"
    assert pl["spotify"]["items"][1]["editorial"] is True
    rep = {r["platform"]: r for r in ev["report_rows"]}
    ig = rep["instagram"]
    assert ig["stats"]["engagement_rate_pct"] == 1.85 and ig["account"]["verified"] is True
    assert ig["followers"]["genders"][0] == {"code": "FEMALE", "pct": 70.5}
    assert ig["followers"]["countries"] == [{"code": "United States", "pct": 31.0}]
    assert ig["top_posts"][0]["likes"] == 16369961 and ig["top_posts"][0]["date"] == "2025-02-12"
    assert ig["hashtags"] == ["magicmountain"] and ig["interests"] == ["Music", "Sports"]
    assert ev["radio"]["stations"][0] == {"name": "XHITZ", "city": "San Diego, CA", "country": "US", "plays": 189}
    assert ev["radio"]["plays_total"] == 23747 and ev["radio"]["stations_total"] == 1159
    assert ev["radio"]["recent"][0]["aired_at"] == "2026-09-15 06:11"
    assert [p["date"] for p in ev["youtube_views"]] == ["2020-10-08", "2020-10-09", "2020-10-10"], "sorted, oldest first"
    assert ev["youtube_line"]["latest"]["views"] == 10355797 and ev["youtube_line"]["total"] == 30982025
    assert ev["youtube_line"]["points"].count(",") == 3
    assert [r["name"] for r in ev["related"]] == ["Lana Del Rey", "Adele"]
    assert [l["platform"] for l in ev["links"]] == ["allmusic", "spotify"], "no url and duplicates are dropped"
    assert ev["links"][1]["verified"] is True
    assert ev["songs"]["total"] == 299 and ev["songs"]["items"][0]["release_date"] == "2026-06-04"
    # one call per question, per platform: nothing loops over a list twice
    paths = [urlparse(u).path for u in wire.calls]
    assert len(paths) == len(set(paths)) == 1 + 8 + 5 + 3 + 2 + 1 + 1 + 1 + 1


def test_a_refusal_and_an_empty_answer_are_named_not_filled(sc):
    adapter, _ = sc(refuse=("/audience/facebook", "/playlist/current/apple-music", "/broadcast",
                            "/audience/tiktok/report"),
                    empty=("/related",))
    ev = pulse_everything.build(adapter, A, today=date(2020, 10, 10))
    by = {r["platform"]: r for r in ev["audience_rows"]}
    assert by["facebook"]["state"] == "refused" and "403" in by["facebook"]["why"]
    pl = {r["platform"]: r for r in ev["playlist_rows"]}
    assert pl["apple-music"]["state"] == "refused" and pl["apple-music"]["items"] == []
    rep = {r["platform"]: r for r in ev["report_rows"]}
    assert rep["tiktok"]["state"] == "refused" and rep["instagram"]["state"] == "measured"
    assert ev["radio"] is None and "radio" in ev["refused"]
    assert ev["related"] == [] and "related" in ev["empty"]


def test_a_provider_without_these_questions_gives_no_section():
    assert pulse_everything.build(None, A) is None
    assert pulse_everything.build(object(), A) is None
    adapter = providers.SoundchartsAdapter(fetch=lambda url: {})
    assert pulse_everything.build(adapter, "") is None


@pytest.fixture
def page(sc):
    from app import create_app
    adapter, wire = sc(refuse=("/audience/facebook", "/playlist/current/amazon"))
    providers.reset_registry(providers.ProviderRegistry(adapters=[adapter]))
    app_obj = create_app()
    client = app_obj.test_client()
    email = "ev-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Everything", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    with app_obj.app_context():
        uid = store.get_user_by_email(email)["id"]
        store.save_pulse_profile(uid, "spotify-artist-ev", "Billie Eilish")
        store.save_pulse_provider_artist(uid, "soundcharts", A)
    yield app_obj, client, wire
    providers.reset_registry(None)


def test_the_page_carries_every_section_and_names_what_the_plan_refused(page):
    app_obj, client, wire = page
    body = client.get("/pulse").get_data(as_text=True)
    assert 'id="everything"' in body
    section = body.split('id="everything"')[1].split("</section>")[0]
    assert "Everything Soundcharts holds on this artist" in section
    assert "Los Angeles, US" in section and "pop, alternative" in section and "career stage: superstar" in section
    assert "Audience by platform" in section and "33,407,686" in section and "Not in the plan" in section
    assert "Nothing on file" in section, "TikTok holds nothing"
    assert "Playlists by platform" in section and "768,810 placements" in section and "Editorial" in section
    assert "Audience reports" in section and "1.85%" in section and "Age 18-24" in section
    assert "Radio, last 28 days" in section and "23,747 plays logged" in section and "XHITZ" in section
    assert "YouTube views by day" in section and "10,355,797" in section and "<polyline" in section
    assert "Lana Del Rey" in section and "AllMusic" in section and "299 songs" in section
    assert "Every figure in this section was measured by Soundcharts." in section
    assert " 0 followers" not in section and ">0<" not in section and "$" not in section
    # the search was never spent: the id was on the profile
    assert not any("/artist/search/" in u for u in wire.calls)


def test_without_a_provider_id_the_page_has_no_section(sc):
    from app import create_app
    adapter, wire = sc()
    providers.reset_registry(providers.ProviderRegistry(adapters=[adapter]))
    try:
        app_obj = create_app()
        client = app_obj.test_client()
        email = "ev2-%s@example.net" % uuid.uuid4().hex[:8]
        client.post("/signup", data={"name": "Nobody", "email": email, "password": PW})
        body = client.get("/pulse").get_data(as_text=True)
        assert 'id="everything"' not in body, "no artist picked, nothing to ask about"
    finally:
        providers.reset_registry(None)

"""Signal's MLC adapter, against The MLC Public Search API's documented shapes.

The OpenAPI document at https://public-api.themlc.com/api/doc (v1.2.0)
is the source: /oauth/token trades a username and password for a bearer
token, /search/recordings finds recordings by ISRC or title + artist,
/works returns writers, publishers and collection shares by song code.
The live API refuses anonymous calls (401), so these run against a fake
transport shaped like the spec; the sign-in error shape below is what
the real /oauth/token returned for a wrong password.

What is held: the token is exchanged once and reused, refreshed when it
runs out, and retried once on a 401; an ISRC with no work is a potential
gap; a title with no recording is silence, not a gap; and every flag on
an evidence row follows from what The MLC actually returned.
"""
import json

import pytest

import signal_providers as providers

WORK_FULL = {
    "mlcSongCode": "BA1234", "iswc": "T-123.456.789-0", "primaryTitle": "NIGHT DRIVE",
    "artists": "Ava Kane", "membersSongId": "",
    "writers": [{"writerFirstName": "Ava", "writerLastName": "Kane", "writerIPI": "00123456789",
                 "writerRoleCode": "CA", "writerId": "w1"},
                {"writerFirstName": "J.", "writerLastName": "Ro", "writerIPI": "00987654321",
                 "writerRoleCode": "C", "writerId": "w2"}],
    "publishers": [{"publisherName": "Art Is War Publishing", "publisherIpiNumber": "00555", "publisherRoleCode": "E",
                    "collectionShare": 50.0, "mlcPublisherNumber": "P100",
                    "administrators": [{"publisherName": "Kobalt Music Publishing"}]},
                   {"publisherName": "Ro Songs", "publisherIpiNumber": "00666", "publisherRoleCode": "E",
                    "collectionShare": 50.0, "mlcPublisherNumber": "P200", "administrators": []}],
}
WORK_HALF = dict(WORK_FULL, mlcSongCode="BA9999", iswc="", primaryTitle="PAPER LINES",
                 writers=[{"writerFirstName": "Ava", "writerLastName": "Kane", "writerIPI": ""}],
                 publishers=[{"publisherName": "Art Is War Publishing", "collectionShare": 50.0}])
WORK_BARE = dict(WORK_FULL, mlcSongCode="BA7777", iswc="", primaryTitle="STATIC", writers=[], publishers=[])


class Fake(object):
    """A transport shaped like the API. Records every call it sees."""
    def __init__(self, password="right", ttl="3600", deny_bearer_once=False):
        self.calls, self.password, self.ttl = [], password, ttl
        self.tokens_issued, self.deny_bearer_once = 0, deny_bearer_once

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        path = url.replace(providers.MLCAdapter.base_url, "")
        if path == "/oauth/token":
            if body.get("refreshToken") == "refresh-1" or body.get("password") == self.password:
                self.tokens_issued += 1
                return 200, {"accessToken": "access-%d" % self.tokens_issued, "refreshToken": "refresh-1",
                             "idToken": "id", "scope": None, "expiresIn": self.ttl, "tokenType": "Bearer",
                             "error": None, "errorDescription": None}
            return 403, {"accessToken": None, "refreshToken": None, "error": "invalid_grant",
                         "errorDescription": "Request failed with status code 403: Wrong email or password."}
        if headers.get("Authorization") != "Bearer access-%d" % self.tokens_issued or self.deny_bearer_once:
            self.deny_bearer_once = False
            return 401, {"message": "Unauthorized"}
        if path == "/search/recordings":
            if body.get("isrc") == "USAIW2600123":
                return 200, [{"id": "r1", "isrc": "USAIW2600123", "title": "Night Drive", "artist": "Ava Kane",
                              "labels": "Art Is War", "mlcsongCode": "BA1234"}]
            if body.get("title") == "Paper Lines" and body.get("artist") == "Ava Kane":
                return 200, [{"id": "r2", "isrc": "USAIW2600200", "title": "Paper Lines", "artist": "Ava Kane",
                              "labels": "", "mlcsongCode": "BA9999"},
                             {"id": "r3", "isrc": "USAIW2600201", "title": "Paper Lines (Live)", "artist": "Ava Kane",
                              "labels": "", "mlcsongCode": "BA9999"}]
            if body.get("isrc") == "USAIW2600777":
                return 200, [{"id": "r4", "isrc": "USAIW2600777", "title": "Static", "artist": "Ava Kane",
                              "labels": "", "mlcsongCode": "BA7777"}]
            return 200, []
        if path == "/works":
            wanted = [q.get("mlcsongCode") for q in body]
            return 200, [w for w in (WORK_FULL, WORK_HALF, WORK_BARE) if w["mlcSongCode"] in wanted]
        if path == "/search/songcode":
            return 200, [{"iswc": WORK_FULL["iswc"], "mlcSongCode": "BA1234", "workTitle": "NIGHT DRIVE",
                          "writers": WORK_FULL["writers"]}]
        return 404, {"message": "Not found"}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("MLC_ENABLED", "1")
    monkeypatch.setenv("MLC_USERNAME", "api-user@example.net")
    monkeypatch.setenv("MLC_PASSWORD", "right")


def _adapter(fake, clock=None):
    return providers.MLCAdapter(transport=fake, now=clock)


def test_it_is_inert_until_the_login_exists(monkeypatch):
    for k in ("MLC_ENABLED", "MLC_USERNAME", "MLC_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    a = _adapter(lambda *args: pytest.fail("must not call out"))
    assert a.configured() is False
    with pytest.raises(providers.ProviderError):
        a.get_rights_evidence(isrc="USAIW2600123")
    monkeypatch.setenv("MLC_ENABLED", "1")
    monkeypatch.setenv("MLC_USERNAME", "u")
    assert a.configured() is False, "a username without its password is not configured"


def test_the_token_is_exchanged_once_and_sent_as_a_bearer(env):
    fake = Fake()
    a = _adapter(fake)
    a.find_recordings(isrc="usaiw2600123")
    a.find_recordings(isrc="USAIW2600123")
    tokens = [c for c in fake.calls if c[1].endswith("/oauth/token")]
    assert len(tokens) == 1 and tokens[0][3] == {"username": "api-user@example.net", "password": "right"}
    searches = [c for c in fake.calls if c[1].endswith("/search/recordings")]
    assert len(searches) == 2
    assert all(c[2]["Authorization"] == "Bearer access-1" for c in searches)
    assert searches[0][3] == {"isrc": "USAIW2600123"}, "the ISRC is normalised before it is sent"
    assert searches[0][0] == "POST" and searches[0][2]["Content-Type"] == "application/json"


def test_a_spent_token_is_refreshed_not_re_entered(env):
    clock = {"t": 1000.0}
    fake = Fake(ttl="600")
    a = _adapter(fake, clock=lambda: clock["t"])
    a.find_recordings(isrc="USAIW2600123")
    clock["t"] += 700
    a.find_recordings(isrc="USAIW2600123")
    tokens = [c[3] for c in fake.calls if c[1].endswith("/oauth/token")]
    assert tokens == [{"username": "api-user@example.net", "password": "right"}, {"refreshToken": "refresh-1"}]
    last = [c for c in fake.calls if c[1].endswith("/search/recordings")][-1]
    assert last[2]["Authorization"] == "Bearer access-2"


def test_a_401_is_retried_once_with_a_fresh_token(env):
    fake = Fake(deny_bearer_once=True)
    a = _adapter(fake)
    recs = a.find_recordings(isrc="USAIW2600123")
    assert recs and recs[0]["song_code"] == "BA1234"
    assert sum(1 for c in fake.calls if c[1].endswith("/oauth/token")) == 2
    assert sum(1 for c in fake.calls if c[1].endswith("/search/recordings")) == 2


def test_a_wrong_password_is_their_sentence_not_a_crash(monkeypatch):
    monkeypatch.setenv("MLC_ENABLED", "1")
    monkeypatch.setenv("MLC_USERNAME", "api-user@example.net")
    monkeypatch.setenv("MLC_PASSWORD", "wrong")
    a = _adapter(Fake(password="right"))
    with pytest.raises(providers.ProviderError) as err:
        a.find_recordings(isrc="USAIW2600123")
    assert "Wrong email or password" in str(err.value)


def test_an_isrc_becomes_a_fully_described_work(env):
    a = _adapter(Fake())
    rows = a.get_rights_evidence(isrc="USAIW2600123")
    assert len(rows) == 1
    r = rows[0]
    assert r["work_match"] is True and r["recording_linked"] is True
    assert r["writers_complete"] is True, "both writers carry an IPI"
    assert r["publisher_detected"] is True and r["shares_complete"] is True, "50 + 50"
    assert r["confidence"] == 0.9 and r["iswc"] == "T-123.456.789-0" and r["song_code"] == "BA1234"
    assert r["source_type"] == "work_registry" and r["source_label"] == "The MLC public search"
    assert r["source_url"].startswith("https://portal.themlc.com/")
    assert [w["name"] for w in r["writers"]] == ["Ava Kane", "J. Ro"]
    assert r["publishers"][0]["administrators"] == ["Kobalt Music Publishing"]
    assert r["excerpt"] == "MLC song code BA1234 (ISWC T-123.456.789-0): 2 writers, 2 publishers, collection shares total 100%"


def test_half_claimed_and_bare_works_read_as_gaps_with_the_reason_visible(env):
    a = _adapter(Fake())
    half = a.get_rights_evidence(title="Paper Lines", artist="Ava Kane")
    assert len(half) == 1, "two recordings of one work are one work"
    h = half[0]
    assert h["work_match"] is True and h["recording_linked"] is False, "matched by title, so no recording is pinned"
    assert h["writers_complete"] is False, "a writer without an IPI"
    assert h["publisher_detected"] is True and h["shares_complete"] is False, "50% claimed"
    assert h["share_total"] == 50.0 and h["confidence"] == 0.7
    assert "collection shares total 50%" in h["excerpt"]
    bare = a.get_rights_evidence(isrc="USAIW2600777")[0]
    assert bare["work_match"] is True
    assert bare["writers_complete"] is False and bare["publisher_detected"] is False and bare["shares_complete"] is False


def test_an_unknown_isrc_is_a_gap_but_an_unknown_title_is_silence(env):
    fake = Fake()
    a = _adapter(fake)
    gap = a.get_rights_evidence(isrc="USXXX9999999")
    assert len(gap) == 1 and gap[0]["work_match"] is False and gap[0]["recording_linked"] is False
    assert "No work at The MLC is linked to ISRC USXXX9999999" in gap[0]["excerpt"]
    assert a.get_rights_evidence(title="Happier Than Ever", artist="Ava Kane") == []
    assert a.get_rights_evidence() == [] and not any(c[1].endswith("/works") for c in fake.calls[-1:])


def test_lookup_and_title_search_expose_the_raw_units(env):
    a = _adapter(Fake())
    found = a.lookup(isrc="USAIW2600123")
    assert found["recordings"][0]["labels"] == "Art Is War" and found["works"][0]["share_total"] == 100.0
    works = a.find_works_by_title("Night Drive", writers=[{"last": "Kane"}])
    assert works[0]["song_code"] == "BA1234" and works[0]["writers"][0]["ipi"] == "00123456789"
    assert a.find_works_by_title("") == [] and a.get_works([]) == []


def test_the_registry_serves_rights_from_it_and_nothing_else(env):
    a = _adapter(Fake())
    reg = providers.ProviderRegistry(adapters=[a])
    assert reg.is_demo() is False
    assert reg.for_capability(providers.CAP_RIGHTS).key == "mlc"
    assert reg.for_capability(providers.CAP_ARTIST) is None, "a registry is not a music database"


def test_ingest_asks_with_the_artists_name_and_stores_the_codes(env, monkeypatch):
    import db as store
    import signal_ingest as ingest
    import signal_store as sstore
    store.init_db()
    sstore.init_signal()
    monkeypatch.setenv("MUSICBRAINZ_ENABLED", "1")
    monkeypatch.setenv("MUSICBRAINZ_CONTACT", "ops@example.net")
    from tests.test_signal_musicbrainz import MBID, _fake_fetch as mb_fetch
    mb = providers.MusicBrainzAdapter(fetch=mb_fetch([]), sleep=lambda s: None)
    fake = Fake()
    reg = providers.ProviderRegistry(adapters=[mb, _adapter(fake)])
    artist_id = ingest.ingest_artist(MBID, reg=reg, force=True)
    assert artist_id
    asked = [c[3] for c in fake.calls if c[1].endswith("/search/recordings")]
    assert asked and all(q.get("artist") == "Nirvana" for q in asked), "the artist disambiguates the title"
    assert {q.get("title") for q in asked} >= {"Nevermind", "In Utero"}
    # Album titles with no recording at The MLC leave no evidence - not a gap.
    assert sstore.list_evidence("artist", artist_id, sstore.CLAIM_RIGHTS) == []

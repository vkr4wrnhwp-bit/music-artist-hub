"""Apple's catalogue, asked by ISRC (2026-09-14).

Same contract as the Deezer check: True with the store page, False for a
real "no", None when the question was not answered - and None is never
read as absence, because a bad afternoon at Apple must not become a
letter claiming a track was never delivered.
"""
import coverage_check as cc
import music_apis


def _no_cache(monkeypatch):
    monkeypatch.setattr(music_apis.store, "cache_get", lambda key, ttl: None)
    monkeypatch.setattr(music_apis.store, "cache_set", lambda key, data: None)


def test_a_hit_is_the_song_page(monkeypatch):
    _no_cache(monkeypatch)
    monkeypatch.setattr(music_apis, "_fetch_json", lambda url: {
        "resultCount": 1, "results": [{"wrapperType": "track", "kind": "song",
                                       "trackViewUrl": "https://music.apple.com/us/album/x/1?i=2"}]})
    assert music_apis.apple_has_isrc("QZTB32240214") == (True, "https://music.apple.com/us/album/x/1?i=2")


def test_result_count_zero_is_a_real_no(monkeypatch):
    _no_cache(monkeypatch)
    monkeypatch.setattr(music_apis, "_fetch_json", lambda url: {"resultCount": 0, "results": []})
    assert music_apis.apple_has_isrc("QZTB32240214") == (False, "not in Apple's catalogue")


def test_a_failure_or_an_unreadable_reply_is_not_an_answer(monkeypatch):
    _no_cache(monkeypatch)

    def boom(url):
        raise OSError("timed out")
    monkeypatch.setattr(music_apis, "_fetch_json", boom)
    present, why = music_apis.apple_has_isrc("QZTB32240214")
    assert present is None and "did not answer" in why
    monkeypatch.setattr(music_apis, "_fetch_json", lambda url: ["not", "a", "dict"])
    assert music_apis.apple_has_isrc("QZTB32240214")[0] is None
    assert music_apis.apple_has_isrc("")[0] is None


def test_the_lookup_asks_by_isrc_and_only_for_songs(monkeypatch):
    _no_cache(monkeypatch)
    asked = {}
    monkeypatch.setattr(music_apis, "_fetch_json", lambda url: asked.setdefault("url", url) and {"resultCount": 0, "results": []})
    music_apis.apple_has_isrc("qztb-32240214")
    assert "isrc=QZTB32240214" in asked["url"] and "entity=song" in asked["url"]


def test_one_apple_answer_covers_both_apple_lines_in_the_store_check(monkeypatch):
    monkeypatch.setattr(cc.music_apis, "deezer_has_isrc", lambda isrc: (None, "stubbed"))
    monkeypatch.setattr(cc, "_spotify_url_for_isrc", lambda isrc: (None, "stubbed"))
    monkeypatch.setattr(cc, "_songstats_links", lambda isrc, spotify_track_id="": ({}, ""))
    monkeypatch.setattr(cc.music_apis, "apple_has_isrc", lambda isrc: (True, "https://music.apple.com/x"))
    out = cc.check_gap("QZTB32240214", ["Apple Music", "iTunes", "iTunes Match", "Deezer", "Anghami"])
    carried = {c["source"] for c in out["carried"]}
    assert carried == {"Apple Music", "iTunes", "iTunes Match"}
    assert out["unchecked"] == ["Anghami", "Deezer"]

    monkeypatch.setattr(cc.music_apis, "apple_has_isrc", lambda isrc: (False, "not in Apple's catalogue"))
    out = cc.check_gap("QZTB32240214", ["Apple Music", "iTunes"])
    assert out["absent"] == ["Apple Music", "iTunes"] and out["carried"] == []

    monkeypatch.setattr(cc.music_apis, "apple_has_isrc", lambda isrc: (None, "Apple did not answer"))
    out = cc.check_gap("QZTB32240214", ["Apple Music"])
    assert out["unchecked"] == ["Apple Music"] and out["absent"] == [], "not answered is not absent"

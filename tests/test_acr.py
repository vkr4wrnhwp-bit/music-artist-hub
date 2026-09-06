"""ACRCloud: a fingerprint check the producer runs, held to what it is.

Three things are guarded. The wire call matches ACRCloud's documented
signing scheme (nobody can test the vendor here, so the test pins the
scheme). The sample sent is a valid slice from the middle of the beat,
never the whole file. And the page never claims monitoring: a check
happens on a button press, every run is stored including "no match" and
the vendor's errors, and the `fingerprint` badge on a usage case can
only come from a stored match row.
"""
import base64
import hashlib
import hmac
import io
import os
import struct
import uuid
from urllib.parse import parse_qs, urlparse

import pytest

import acr_provider
import db as store
from app import create_app

KEYS = {"ACRCLOUD_HOST": "identify-us-west-2.acrcloud.com",
        "ACRCLOUD_ACCESS_KEY": "AK-test", "ACRCLOUD_ACCESS_SECRET": "SK-test"}

MUSIC = {"acrid": "acr-1", "title": "Night Drive", "score": 92, "play_offset_ms": 41000,
         "artists": [{"name": "Ava Kane"}, {"name": "J. Ro"}],
         "album": {"name": "After Hours"}, "label": "Art Is War", "release_date": "2026-03-14",
         "external_ids": {"isrc": "USAIW2600123"},
         "external_metadata": {"spotify": {"track": {"id": "7abc"}}, "youtube": {"vid": "yt1"}}}


def _configure(monkeypatch, on=True):
    for k, v in KEYS.items():
        if on:
            monkeypatch.setenv(k, v)
        else:
            monkeypatch.delenv(k, raising=False)


def _parse_multipart(content_type, body):
    boundary = content_type.split("boundary=")[1].encode()
    fields, files = {}, {}
    for part in body.split(b"--" + boundary)[1:-1]:
        head, _, value = part.partition(b"\r\n\r\n")
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        if b"filename=" in head:
            files[name] = value[:-2]
        else:
            fields[name] = value[:-2].decode()
    return fields, files


def _wav(seconds=30, rate=8000):
    """Mono 16-bit, with each second's samples set to that second's number
    so a slice can say where in the file it came from."""
    body = b"".join(struct.pack("<h", s) * rate for s in range(seconds))
    head = (b"RIFF" + struct.pack("<I", 36 + len(body)) + b"WAVEfmt " + struct.pack("<I", 16)
            + struct.pack("<HHIIHH", 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", len(body)))
    return head + body


# --- the wire ------------------------------------------------------------------

def test_the_call_is_signed_the_way_their_docs_say(monkeypatch):
    _configure(monkeypatch)
    seen = {}

    def post(url, content_type, body):
        seen["url"] = url
        seen["fields"], seen["files"] = _parse_multipart(content_type, body)
        return {"status": {"code": 0, "msg": "Success"}, "metadata": {"music": [MUSIC]}}

    matches = acr_provider.identify(b"\x00" * 100, post=post)
    assert seen["url"] == "https://identify-us-west-2.acrcloud.com/v1/identify"
    f = seen["fields"]
    assert f["access_key"] == "AK-test" and f["data_type"] == "audio" and f["signature_version"] == "1"
    assert f["sample_bytes"] == "100" and seen["files"]["sample"] == b"\x00" * 100
    to_sign = "\n".join(["POST", "/v1/identify", "AK-test", "audio", "1", f["timestamp"]])
    want = base64.b64encode(hmac.new(b"SK-test", to_sign.encode(), hashlib.sha1).digest()).decode()
    assert f["signature"] == want
    assert len(matches) == 1


def test_a_match_carries_the_recording_and_where_to_hear_it(monkeypatch):
    _configure(monkeypatch)
    m = acr_provider.identify(b"x", post=lambda *a: {
        "status": {"code": 0}, "metadata": {"music": [MUSIC]}})[0]
    assert m["title"] == "Night Drive" and m["artists"] == "Ava Kane, J. Ro"
    assert m["album"] == "After Hours" and m["label"] == "Art Is War"
    assert m["isrc"] == "USAIW2600123" and m["score"] == 92 and m["play_offset_ms"] == 41000
    assert m["url"] == "https://open.spotify.com/track/7abc" and m["platform"] == "Spotify"
    assert m["kind"] == "music"


def test_no_result_is_an_empty_list_not_an_error(monkeypatch):
    _configure(monkeypatch)
    assert acr_provider.identify(b"x", post=lambda *a: {"status": {"code": 1001, "msg": "No result"}}) == []


def test_their_error_is_raised_with_their_code(monkeypatch):
    _configure(monkeypatch)
    with pytest.raises(acr_provider.AcrError) as err:
        acr_provider.identify(b"x", post=lambda *a: {"status": {"code": 3014, "msg": "Invalid Signature"}})
    assert err.value.code == 3014 and "Invalid Signature" in str(err.value)


def test_without_keys_it_refuses_rather_than_guessing(monkeypatch):
    _configure(monkeypatch, on=False)
    with pytest.raises(acr_provider.AcrError):
        acr_provider.identify(b"x", post=lambda *a: {"status": {"code": 0}})


# --- the sample ----------------------------------------------------------------

def test_a_wav_slice_is_a_valid_file_from_the_middle():
    data = _wav(seconds=30, rate=8000)
    out = acr_provider.slice_sample(data, "audio/wav")
    assert out[:4] == b"RIFF" and out[8:16] == b"WAVEfmt "
    assert struct.unpack("<I", out[4:8])[0] == len(out) - 8
    data_len = struct.unpack("<I", out[40:44])[0]
    assert len(out) == 44 + data_len
    assert data_len == 12 * 8000 * 2, "twelve seconds at the file's own rate"
    first = struct.unpack("<h", out[44:46])[0]
    assert 8 <= first <= 10, "taken from the middle of thirty seconds, not the top"
    assert len(out) <= acr_provider.SAMPLE_LIMIT


def test_a_short_wav_is_sent_whole_and_anything_else_is_capped():
    short = _wav(seconds=3, rate=8000)
    out = acr_provider.slice_sample(short, "audio/wav")
    assert struct.unpack("<I", out[40:44])[0] == 3 * 8000 * 2
    big = b"\x01" * (3 * acr_provider.SAMPLE_LIMIT)
    assert len(acr_provider.slice_sample(big, "audio/flac")) == acr_provider.SAMPLE_LIMIT
    mp3 = b"\xff\xfb" * (2 * acr_provider.SAMPLE_LIMIT)
    assert len(acr_provider.slice_sample(mp3, "audio/mpeg")) == acr_provider.SAMPLE_LIMIT


# --- the words -----------------------------------------------------------------

def test_the_status_never_claims_monitoring(monkeypatch):
    _configure(monkeypatch, on=False)
    off = acr_provider.status()
    assert off["on"] is False and off["headline"] == "Nothing here scans for you"
    _configure(monkeypatch)
    on = acr_provider.status()
    assert on["on"] is True and "identification" in on["headline"]
    assert "monitoring" not in on["headline"].lower()
    assert "does not crawl" in on["detail"] and "press a button" in on["detail"]


# --- the page --------------------------------------------------------------------

def _producer(app_obj):
    email = "acr-%s@example.net" % uuid.uuid4().hex[:8]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Producer", "email": email, "password": "beats-pass-123"})
    client.post("/login", data={"email": email, "password": "beats-pass-123"})
    return client, store.get_user_by_email(email)


def _beat_with_audio(client, user):
    client.post("/beats", data={"title": "Night Drive Type Beat", "bpm": "140", "song_key": "F#m"})
    beat = store.list_beats(user["id"])[0]
    client.post("/beats/%s/audio" % beat["id"],
                data={"file": (io.BytesIO(_wav(seconds=20)), "beat.wav", "audio/wav")},
                content_type="multipart/form-data")
    return beat


def test_the_page_stays_quiet_without_keys(monkeypatch):
    _configure(monkeypatch, on=False)
    app_obj = create_app()
    client, user = _producer(app_obj)
    beat = _beat_with_audio(client, user)
    body = client.get("/beats/" + beat["id"]).get_data(as_text=True)
    assert "Check this beat against released music" not in body
    assert "Nothing here scans for you" in client.get("/beats").get_data(as_text=True)
    r = client.post("/beats/%s/identify" % beat["id"], data={"source": "beat"})
    assert r.status_code == 302
    assert store.list_beat_fingerprint_checks(user["id"], beat["id"]) == []


def test_a_check_on_the_beat_sends_a_slice_and_stores_the_answer(monkeypatch):
    _configure(monkeypatch)
    sent = {}

    def fake_identify(sample, post=None):
        sent["sample"] = sample
        return [acr_provider._match_fields(MUSIC, "music")]
    monkeypatch.setattr(acr_provider, "identify", fake_identify)
    app_obj = create_app()
    client, user = _producer(app_obj)
    beat = _beat_with_audio(client, user)
    page = client.get("/beats/" + beat["id"]).get_data(as_text=True)
    assert "Check this beat against released music" in page and "No checks run yet" in page

    r = client.post("/beats/%s/identify" % beat["id"], data={"source": "beat"})
    assert r.status_code == 302 and r.headers["Location"].endswith("#fingerprint")
    assert sent["sample"][:4] == b"RIFF" and len(sent["sample"]) < 20 * 8000 * 2, "a slice, not the file"
    checks = store.list_beat_fingerprint_checks(user["id"], beat["id"])
    assert len(checks) == 1 and checks[0]["result"] == "match" and checks[0]["source"] == "beat"
    assert checks[0]["sample_bytes"] == len(sent["sample"])
    m = checks[0]["matches"][0]
    assert m["title"] == "Night Drive" and m["url"].startswith("https://open.spotify.com/")

    page = client.get("/beats/" + beat["id"]).get_data(as_text=True)
    assert "Night Drive" in page and "Ava Kane, J. Ro" in page and "Log as usage case" in page
    assert "USAIW2600123" in page and "score 92" in page

    # The badge comes from the match row, not from anything the form says.
    client.post("/beats/" + beat["id"], data={"action": "use_from_match", "match_id": m["id"]})
    uses = store.list_beat_uses(user["id"], beat["id"])
    assert len(uses) == 1 and uses[0]["found_via"] == "fingerprint"
    assert uses[0]["url"] == m["url"] and uses[0]["platform"] == "Spotify"
    assert "Confirm by ear" in uses[0]["notes"]
    page = client.get("/beats/" + beat["id"]).get_data(as_text=True)
    assert ">Fingerprint</span>" in page

    # A hand-logged use with a forged found_via stays manual.
    client.post("/beats/" + beat["id"], data={"action": "use", "url": "https://x", "found_via": "fingerprint"})
    assert sorted(u["found_via"] for u in store.list_beat_uses(user["id"], beat["id"])) == ["fingerprint", "manual"]
    # And a match id from another account is not yours to log.
    other, other_user = _producer(app_obj)
    other.post("/beats", data={"title": "Other"})
    other_beat = store.list_beats(other_user["id"])[0]
    other.post("/beats/" + other_beat["id"], data={"action": "use_from_match", "match_id": m["id"]})
    assert store.list_beat_uses(other_user["id"]) == []


def test_no_match_and_a_vendor_error_are_both_kept_and_shown(monkeypatch):
    _configure(monkeypatch)
    answers = [[], acr_provider.AcrError(3003, "Limit exceeded")]

    def fake_identify(sample, post=None):
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a
    monkeypatch.setattr(acr_provider, "identify", fake_identify)
    app_obj = create_app()
    client, user = _producer(app_obj)
    beat = _beat_with_audio(client, user)
    client.post("/beats/%s/identify" % beat["id"], data={
        "source": "clip", "clip": (io.BytesIO(_wav(seconds=5)), "found.wav", "audio/wav")},
        content_type="multipart/form-data")
    client.post("/beats/%s/identify" % beat["id"], data={"source": "beat"})
    checks = store.list_beat_fingerprint_checks(user["id"], beat["id"])
    assert [c["result"] for c in checks] == ["error", "none"], "newest first"
    assert checks[0]["message"] == "ACRCloud 3003: Limit exceeded"
    assert checks[1]["source"] == "clip" and checks[1]["clip_name"] == "found.wav"
    page = client.get("/beats/" + beat["id"]).get_data(as_text=True)
    assert "Limit exceeded" in page and "not a clean bill" in page
    assert ">no match<" in page and ">error<" in page
    assert store.list_beat_uses(user["id"], beat["id"]) == []


def test_a_missing_clip_or_audio_is_a_note_not_a_check(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(acr_provider, "identify", lambda *a, **k: pytest.fail("nothing to send"))
    app_obj = create_app()
    client, user = _producer(app_obj)
    client.post("/beats", data={"title": "Silent"})
    beat = store.list_beats(user["id"])[0]
    r = client.post("/beats/%s/identify" % beat["id"], data={"source": "beat"})
    assert "fp=noaudio" in r.headers["Location"]
    r = client.post("/beats/%s/identify" % beat["id"], data={"source": "clip"},
                    content_type="multipart/form-data")
    assert "fp=noclip" in r.headers["Location"]
    page = client.get("/beats/%s?fp=noaudio" % beat["id"]).get_data(as_text=True)
    assert "Attach audio to this beat first." in page
    assert "disabled" in page.split('name="source" value="beat"')[1].split("</form>")[0]
    assert store.list_beat_fingerprint_checks(user["id"], beat["id"]) == []


def test_deleting_the_beat_takes_its_checks_with_it(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(acr_provider, "identify", lambda *a, **k: [acr_provider._match_fields(MUSIC, "music")])
    app_obj = create_app()
    client, user = _producer(app_obj)
    beat = _beat_with_audio(client, user)
    client.post("/beats/%s/identify" % beat["id"], data={"source": "beat"})
    m = store.list_beat_fingerprint_checks(user["id"], beat["id"])[0]["matches"][0]
    client.post("/beats/%s/delete" % beat["id"])
    assert store.list_beat_fingerprint_checks(user["id"], beat["id"]) == []
    assert store.get_beat_fingerprint_match(user["id"], m["id"]) is None

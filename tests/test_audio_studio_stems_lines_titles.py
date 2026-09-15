"""Five Audio Studio notes from the owner, 2026-09-15.

  * "open stems in the rack also doesnt work": on the bucket-backed live
    deployment the output route redirected to a signed bucket URL. A
    script's fetch follows that cross-origin, the bucket sends no CORS
    headers, and the Rack's stem loader got nothing and said nothing.
    The manifest and the deck now ask for the bytes through the app.
  * "in the recent works theres no title on what it is": an item started
    without a typed title takes the recording's own file name.
  * "the lyrics ... shows up as one giant paragraph": a transcript breaks
    into lines at a breath or after a dozen words; an older one-segment
    transcript is wrapped when it is read.
  * a playhead line on the deck and a group bar that plays every stem
    together, with a Mute on each row.
"""
import io
import os
import uuid

import pytest

import audio_elevenlabs as el
import audio_store as astore
import audio_studio
import audio_works as works
import blob_store
import db as store

PW = "stems-lines-123"


@pytest.fixture(scope="module")
def application():
    keep = {}
    for flag in ("AUDIO_INTELLIGENCE_ENABLED", "LYRIC_SHEET_ENABLED", "STEM_SEPARATION_ENABLED"):
        keep[flag] = os.environ.get(flag)
        os.environ[flag] = "1"
    import app as appmod
    yield appmod.app
    for flag, was in keep.items():
        if was is None:
            os.environ.pop(flag, None)
        else:
            os.environ[flag] = was


@pytest.fixture
def artist(application):
    email = "stems-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Stems", "email": email, "password": PW})
    client.post("/login", data={"email": email, "password": PW})
    with application.app_context():
        uid = store.get_user_by_email(email)["id"]
    return {"client": client, "uid": uid}


def _stems_work(application, uid, keys):
    """A ready stem-separation item whose outputs live at the given keys."""
    with application.app_context():
        work = works.create_work(uid, "stem_separation", title="Narrow")
        ids = []
        for name, key in keys:
            ids.append(astore.create_asset(None, uid, key, file_name=name, mime_type="audio/wav",
                                           file_size=4, asset_type="output"))
        works.set_status(work["id"], "ready", output_asset_ids=ids)
        return work["id"], ids


def test_bucket_stems_reach_the_rack_through_the_app(application, artist, monkeypatch):
    client, uid = artist["client"], artist["uid"]
    remote = blob_store.PREFIX + "studio/out/vocals.wav"
    work_id, ids = _stems_work(application, uid, [("vocals.wav", remote), ("drums.wav", blob_store.PREFIX + "studio/out/drums.wav")])
    monkeypatch.setattr(blob_store, "url_for", lambda path, ttl=300: "https://bucket.test/signed/" + path.split("/")[-1])
    monkeypatch.setattr(blob_store, "fetch", lambda path, timeout=30: b"RIFF" if path == remote else None)
    data = client.get("/audio-studio/%s/outputs.json" % work_id).get_json()
    assert data["ok"] and [f["name"] for f in data["files"]] == ["vocals.wav", "drums.wav"]
    assert all(f["url"].endswith("?via=app") for f in data["files"]), "the Rack fetches through the app"
    r = client.get(data["files"][0]["url"])
    assert r.status_code == 200 and r.data == b"RIFF" and r.mimetype == "audio/wav"
    # the download link still goes to the bucket, which costs no bandwidth here
    plain = client.get("/audio-studio/%s/output/%s" % (work_id, ids[0]))
    assert plain.status_code == 302 and plain.headers["Location"] == "https://bucket.test/signed/vocals.wav"
    # an object the bucket will not give back is a 503, not a 500 or a redirect
    assert client.get(data["files"][1]["url"]).status_code == 503
    # the item page's decks read through the app too, and the Rack says so when it fails
    body = client.get("/audio-studio/%s" % work_id).get_data(as_text=True)
    assert 'data-sd-src="/audio-studio/%s/output/%s?via=app" data-sd-name="vocals.wav"' % (work_id, ids[0]) in body
    assert "stemdeck.js?v=2" in body
    rack = io.open("static/js/rackdsp.js", encoding="utf-8").read()
    assert "The stems could not be read from the Audio Studio" in rack
    deck = io.open("static/js/stemdeck.js", encoding="utf-8").read()
    assert "Play all" in deck and '"Mute"' in deck and "--sd-head" in deck
    css = io.open("static/css/app-chrome.css", encoding="utf-8").read()
    assert "--sd-played: var(--sb-gold-bright)" in css and ".sd-group {" in css


def test_an_untitled_item_takes_the_recordings_own_name(application, artist):
    client, uid = artist["client"], artist["uid"]
    r = client.post("/audio-studio/new",
                    data={"lane": "lyric_sheet", "rights": "1", "title": "  ",
                          "file": (io.BytesIO(b"RIFF....WAVEfmt " + b"\x00" * 64), "Narrow take 3.wav")},
                    content_type="multipart/form-data")
    assert r.status_code in (302, 303), r.get_data(as_text=True)[:200]
    with application.app_context():
        item = works.list_works(user_id=uid)[0]
    assert item["title"] == "Narrow take 3"
    r = client.post("/audio-studio/new",
                    data={"lane": "lyric_sheet", "rights": "1", "title": "Take three, the keeper",
                          "file": (io.BytesIO(b"RIFF....WAVEfmt " + b"\x00" * 64), "x.wav")},
                    content_type="multipart/form-data")
    with application.app_context():
        item = works.list_works(user_id=uid)[0]
    assert item["title"] == "Take three, the keeper", "a typed title always wins"


def _word(text, start, end, kind="word"):
    return {"type": kind, "text": text, "start": start, "end": end}


def test_a_transcript_breaks_into_lines_at_a_breath_or_a_dozen_words():
    words = []
    t = 0.0
    for i in range(5):                       # a five-word line
        words.append(_word("la%d" % i, t, t + 0.3)); words.append(_word(" ", t + 0.3, t + 0.35, "spacing")); t += 0.4
    t += 1.2                                 # a breath
    for i in range(14):                      # fourteen words: twelve, then two
        words.append(_word("da%d" % i, t, t + 0.3)); words.append(_word(" ", t + 0.3, t + 0.35, "spacing")); t += 0.4
    norm = el.ElevenLabsTranscription()._normalise({"words": words, "text": "x", "language_code": "en"})
    lines = [s["text"] for s in norm["segments"]]
    assert lines[0] == "la0 la1 la2 la3 la4"
    assert lines[1].split()[0] == "da0" and len(lines[1].split()) == 12
    assert lines[2] == "da12 da13"
    assert norm["segments"][1]["start_ms"] == int(round((5 * 0.4 + 1.2) * 1000))
    assert all("words" not in s for s in norm["segments"])


def test_an_old_one_paragraph_transcript_is_wrapped_when_read(application, artist):
    uid = artist["uid"]
    with application.app_context():
        asset = astore.create_asset(None, uid, "studio/src.wav", file_name="src.wav")
        work = works.create_work(uid, "lyric_sheet", title="Old", source_asset_id=asset)
        text = " ".join("w%d" % i for i in range(30))
        astore.save_transcript(None, asset, "elevenlabs",
                               {"segments": [{"speaker": "Speaker 1", "start_ms": 5000, "end_ms": 90000, "text": text}]})
        lines = audio_studio._transcript(works.get_work(work["id"]))
    assert [len(l["text"].split()) for l in lines] == [12, 12, 6]
    assert all(l["start_ms"] == 5000 for l in lines), "every wrapped line keeps the only start it has"

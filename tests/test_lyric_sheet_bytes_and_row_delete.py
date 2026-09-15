"""Two Audio Studio fixes from the owner's notes of 2026-09-14.

  * "lyric sheet still doesn't work": on the live deployment uploads sit
    in the bucket, so audio_works._source_file hands the adapter BYTES,
    and ElevenLabsTranscription.transcribe only ever opened a path. Every
    lyric sheet died on open(None) (live log: "TypeError: expected str,
    bytes or os.PathLike object, not NoneType"). Bytes are now sent as a
    named file; neither path nor bytes is a refusal that says so.
  * "there needs to be a x for deletion next to the generated works so
    you dont have to click into them": each row of Recent work carries
    the same delete post the item page makes, with the same warning.
"""
import io
import os
import uuid

import pytest

import audio_elevenlabs as el
import audio_providers as ap
import audio_works as works
import db as store


class _Health(object):
    ok = True
    detail = ""


class _Convert(object):
    def __init__(self):
        self.calls = []

    def convert(self, **kw):
        self.calls.append(kw)
        f = kw.get("file")
        if isinstance(f, tuple):
            name, fh = f[0], f[1]
            self.calls[-1]["_read"] = (name, fh.read())
        return {"text": "narrow road", "words": []}


class _Client(object):
    def __init__(self):
        self.speech_to_text = _Convert()


@pytest.fixture
def adapter(monkeypatch):
    client = _Client()
    monkeypatch.setattr(el, "_health", lambda: _Health())
    monkeypatch.setattr(el, "_client", lambda: client)
    a = el.ElevenLabsTranscription()
    monkeypatch.setattr(a, "_normalise", lambda resp: {"text": resp["text"], "segments": []})
    monkeypatch.setattr(a, "_logging_flag", lambda zero: True)
    return a, client


def test_bytes_from_the_bucket_are_sent_as_a_named_file(adapter):
    a, client = adapter
    req = ap.TranscriptionRequest(diarize=False, timestamps=True)
    req.audio_path = None
    req.audio_bytes = b"RIFF....WAVE"
    req.file_name = "narrow.wav"
    out = a.transcribe(req)
    assert out["status"] == "completed" and out["inline"]["text"] == "narrow road"
    call = client.speech_to_text.calls[-1]
    assert call["_read"] == ("narrow.wav", b"RIFF....WAVE")
    assert "cloud_storage_url" not in call


def test_a_path_still_streams_and_nothing_at_all_is_a_refusal(adapter, tmp_path):
    a, client = adapter
    p = tmp_path / "take.wav"
    p.write_bytes(b"RIFF....WAVE")
    req = ap.TranscriptionRequest(audio_path=str(p), diarize=False)
    a.transcribe(req)
    assert hasattr(client.speech_to_text.calls[-1]["file"], "read"), "a path is streamed, not read into memory"
    empty = ap.TranscriptionRequest(diarize=False)
    empty.audio_bytes = None
    with pytest.raises(ap.ProviderRefusal) as err:
        a.transcribe(empty)
    assert "could not be read back from storage" in str(err.value)


@pytest.fixture(scope="module")
def application():
    keep = {}
    for flag in ("AUDIO_INTELLIGENCE_ENABLED", "LYRIC_SHEET_ENABLED"):
        keep[flag] = os.environ.get(flag)
        os.environ[flag] = "1"
    import app as appmod
    yield appmod.app
    for flag, was in keep.items():
        if was is None:
            os.environ.pop(flag, None)
        else:
            os.environ[flag] = was


def test_recent_work_rows_carry_their_own_delete(application):
    email = "rowx-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Row", "email": email, "password": "rowx-pass-123"})
    client.post("/login", data={"email": email, "password": "rowx-pass-123"})
    with application.app_context():
        uid = store.get_user_by_email(email)["id"]
        work_id = works.create_work(uid, "lyric_sheet", title="Narrow take 3")["id"]
    body = client.get("/audio-studio").get_data(as_text=True)
    row = body.split('class="asx-row"')[1].split("</li>")[0]
    assert "Narrow take 3" in row
    assert 'action="/audio-studio/%s/delete"' % work_id in row
    assert 'aria-label="Delete Narrow take 3"' in row and "destroy the audio you uploaded" in row
    r = client.post("/audio-studio/%s/delete" % work_id)
    assert r.status_code in (302, 303) and r.headers["Location"].endswith("/audio-studio")
    with application.app_context():
        assert works.get_work(work_id) is None
    assert "Narrow take 3" not in client.get("/audio-studio").get_data(as_text=True)

"""The Audio Studio against the real adapter, with the vendor faked.

Every green result before this was proven against the mocks, which never
open a file and never return audio. Run against the real adapter the same
lanes fell over before a byte left the building: the request carried an
asset id and the adapter opened `request["audio_path"]`; the stem call kept
the vendor's raw stream under a key the harvester never reads; the dubbing
adapter reported "dubbed" to a poller waiting for "completed", and nothing
ever downloaded the result.

These tests stand a fake SDK client behind audio_elevenlabs and drive each
lane through works.submit_work() with adapter_key="elevenlabs" - the same
path production takes, minus the network. They assert on what reached the
fake (the file, the variation, the voice) and on what the artist gets (files
with real bytes, a player, a download).
"""
import io
import json
import os
import types
import uuid
import zipfile

import pytest

import audio_elevenlabs as el
import audio_providers as ap
import audio_store as astore
import audio_works as works
import db as store

FLAGS = ("AUDIO_INTELLIGENCE_ENABLED", "STEM_SEPARATION_ENABLED",
         "VOICE_ISOLATION_ENABLED", "CAMPAIGN_AUDIO_TOOLKIT_ENABLED",
         "SOUND_EFFECTS_ENABLED", "GLOBAL_RELEASE_PACK_ENABLED",
         "DUBBING_ENABLED")


@pytest.fixture(scope="module")
def application():
    """Every lane on for this module, and exactly as it was afterwards.
    The lane flags are read per request, so leaving them set would switch
    lanes on for whichever suite runs next - test_audio_studio checks that
    an off lane refuses a post, and it ran after this one once."""
    saved = {flag: os.environ.get(flag) for flag in FLAGS}
    for flag in FLAGS:
        os.environ[flag] = "1"
    import app as appmod
    yield appmod.app
    for flag, value in saved.items():
        if value is None:
            os.environ.pop(flag, None)
        else:
            os.environ[flag] = value


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buf.getvalue()


class FakeVendor(object):
    """Just enough of the SDK's surface, recording every call it gets."""

    def __init__(self):
        self.calls = []
        self.dub_state = "dubbing"
        ns = types.SimpleNamespace
        self.models = ns(list=lambda **kw: [1, 2, 3])
        self.music = ns(separate_stems=self._separate_stems)
        self.audio_isolation = ns(convert=self._isolate)
        self.text_to_speech = ns(convert=self._tts)
        self.text_to_sound_effects = ns(convert=self._sfx)
        self.dubbing = ns(create=self._dub_create, get=self._dub_get,
                          audio=ns(get=self._dub_audio))
        self.voices = ns(get_all=self._voices)

    @staticmethod
    def _read(file_arg):
        name, content = file_arg[0], file_arg[1]
        data = content.read() if hasattr(content, "read") else content
        return name, data

    def _separate_stems(self, **kw):
        name, data = self._read(kw["file"])
        self.calls.append(("separate_stems", name, data, kw.get("stem_variation_id"),
                           kw.get("output_format")))
        blob = _zip({"vocals.mp3": b"ID3vox" * 40, "drums.mp3": b"ID3drm" * 30,
                     "bass.mp3": b""})
        return iter([blob[:100], blob[100:]])

    def _isolate(self, **kw):
        name, data = self._read(kw["audio"])
        self.calls.append(("audio_isolation", name, data))
        return iter([b"ID3", b"isolated" * 20])

    def _tts(self, voice_id, **kw):
        self.calls.append(("text_to_speech", voice_id, kw.get("text"),
                           kw.get("output_format")))
        return iter([b"ID3read" * 10])

    def _sfx(self, **kw):
        self.calls.append(("sound_effects", kw.get("text"), kw.get("duration_seconds")))
        return iter([b"ID3fx" * 10])

    def _dub_create(self, **kw):
        name, data = self._read(kw["file"])
        self.calls.append(("dubbing.create", name, data, kw.get("target_lang")))
        return types.SimpleNamespace(dubbing_id="dub_%s" % kw.get("target_lang"),
                                     expected_duration_sec=45)

    def _dub_get(self, dubbing_id, **kw):
        return types.SimpleNamespace(dubbing_id=dubbing_id, status=self.dub_state,
                                     target_languages=["es"], error=None)

    def _dub_audio(self, dubbing_id, language_code, **kw):
        self.calls.append(("dubbing.audio", dubbing_id, language_code))
        return iter([b"ID3dub-", language_code.encode("ascii")])

    def _voices(self, **kw):
        ns = types.SimpleNamespace
        return ns(voices=[ns(voice_id="v_narrator", name="Narrator", category="premade",
                             labels={"accent": "neutral", "use_case": "narration"}),
                          ns(voice_id="v_bright", name="Bright", category="premade",
                             labels={})])


@pytest.fixture
def vendor(monkeypatch):
    fake = FakeVendor()
    monkeypatch.setenv("ELEVENLABS_ENABLED", "1")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key-never-real")
    monkeypatch.delenv("ELEVENLABS_DEFAULT_VOICE_ID", raising=False)
    monkeypatch.setattr(el, "_client", lambda: fake)
    el.reset_health_cache()
    el.reset_voice_cache()
    yield fake
    el.reset_health_cache()
    el.reset_voice_cache()


def _artist(application):
    email = "live-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Live Artist", "email": email,
                                 "password": "lv-pass-123"})
    client.post("/login", data={"email": email, "password": "lv-pass-123"})
    with application.app_context():
        return client, store.get_user_by_email(email)


def _source(application, user, name="master.wav", data=b"RIFF" + b"\0" * 400):
    """An upload the way the Studio stores one: a private file under the
    studio prefix, and an asset row pointing at it."""
    import audio_studio
    with application.app_context():
        fname = "src_%s.wav" % uuid.uuid4().hex[:8]
        with open(os.path.join(audio_studio._studio_dir(), fname), "wb") as fh:
            fh.write(data)
        return astore.create_asset(None, user["id"], audio_studio.STUDIO_PREFIX + fname,
                                   file_name=name, mime_type="audio/wav",
                                   file_size=len(data))


def _work(application, user, kind, **fields):
    with application.app_context():
        item = works.create_work(user["id"], kind, title=fields.pop("title", kind),
                                 **fields)
        works.confirm_rights(item["id"], user["name"])
        return item


# --- the source reaches the vendor ------------------------------------------

def test_the_uploaded_file_is_what_the_vendor_receives(application, vendor):
    """The request used to carry an asset id and nothing else. The adapter
    must be handed the bytes the artist uploaded, under their own name."""
    client, user = _artist(application)
    payload = b"RIFF" + b"stemsource" * 50
    asset_id = _source(application, user, name="gods-timing.wav", data=payload)
    item = _work(application, user, "stem_separation", source_asset_id=asset_id,
                 options={"stem_variation": "six_stems_v1"})
    with application.app_context():
        works.submit_work(item["id"], adapter_key="elevenlabs")

    call = [c for c in vendor.calls if c[0] == "separate_stems"][0]
    assert call[1] == "gods-timing.wav"
    assert call[2] == payload
    assert call[3] == "six_stems_v1"
    assert call[4] == el.OUTPUT_FORMAT


def test_a_bucket_source_is_fetched_rather_than_linked(application, vendor, monkeypatch):
    """The vendor cannot be handed a private signed URL that expires under
    it, so a remote object is fetched and sent as bytes."""
    import blob_store

    client, user = _artist(application)
    monkeypatch.setattr(blob_store, "is_remote", lambda path: path.startswith("r2:"))
    monkeypatch.setattr(blob_store, "fetch", lambda path, timeout=30:
                        b"RIFF-from-bucket" if path == "r2:studio/x.wav" else None)
    with application.app_context():
        asset_id = astore.create_asset(None, user["id"], "r2:studio/x.wav",
                                       file_name="x.wav", mime_type="audio/wav")
    item = _work(application, user, "voice_isolation", source_asset_id=asset_id)
    with application.app_context():
        works.submit_work(item["id"], adapter_key="elevenlabs")

    call = [c for c in vendor.calls if c[0] == "audio_isolation"][0]
    assert call[2] == b"RIFF-from-bucket"


def test_a_source_that_cannot_be_read_is_a_refusal_not_a_crash(application, vendor):
    """A missing file is something the artist can act on. It must not be
    recorded as an adapter bug and buried."""
    client, user = _artist(application)
    with application.app_context():
        asset_id = astore.create_asset(None, user["id"], "studio:does-not-exist.wav",
                                       file_name="gone.wav")
    item = _work(application, user, "voice_isolation", source_asset_id=asset_id)
    with application.app_context():
        with pytest.raises(works.WorkRefusal):
            works.submit_work(item["id"], adapter_key="elevenlabs")
        after = works.get_work(item["id"])
    assert after["status"] == "refused"


# --- stems come back as files ------------------------------------------------

def test_stems_are_unpacked_from_the_zip_and_kept(application, vendor):
    """The vendor answers with a ZIP. Before this the stream was kept under
    "raw", the harvester read "stems", and a paid separation produced no
    files."""
    client, user = _artist(application)
    asset_id = _source(application, user)
    item = _work(application, user, "stem_separation", source_asset_id=asset_id,
                 options={"stem_variation": "two_stems_v1"})
    with application.app_context():
        after, result = works.submit_work(item["id"], adapter_key="elevenlabs")
        outputs = [astore.get_asset(None, aid) for aid in after["output_asset_ids"]]

    assert after["status"] == "ready" and not after["is_mock"]
    names = sorted(o["file_name"] for o in outputs)
    assert names == ["stem_separation_drums.mp3", "stem_separation_vocals.mp3"]
    assert all(o["mime_type"] == "audio/mpeg" for o in outputs)
    # The empty bass entry never became a file.
    assert not any("bass" in n for n in names)

    manifest = client.get("/audio-studio/%s/outputs.json" % item["id"]).get_json()
    assert len(manifest["files"]) == 2
    for entry in manifest["files"]:
        assert client.get(entry["url"]).get_data().startswith(b"ID3")


def test_the_item_page_plays_and_downloads_each_file(application, vendor):
    client, user = _artist(application)
    asset_id = _source(application, user)
    item = _work(application, user, "stem_separation", source_asset_id=asset_id)
    with application.app_context():
        works.submit_work(item["id"], adapter_key="elevenlabs")
    body = client.get("/audio-studio/%s" % item["id"]).get_data(as_text=True)
    assert body.count("<audio controls") == 2
    assert 'download>' in body
    assert "/rack?stems=%s" % item["id"] in body


# --- isolation, effects, voiceover ------------------------------------------

def test_isolation_keeps_the_returned_audio(application, vendor):
    client, user = _artist(application)
    asset_id = _source(application, user)
    item = _work(application, user, "voice_isolation", source_asset_id=asset_id)
    with application.app_context():
        after, _ = works.submit_work(item["id"], adapter_key="elevenlabs")
        outputs = [astore.get_asset(None, aid) for aid in after["output_asset_ids"]]
    assert after["status"] == "ready"
    assert len(outputs) == 1 and outputs[0]["file_size"] > 100


def test_sound_effects_keep_the_returned_audio(application, vendor):
    client, user = _artist(application)
    item = _work(application, user, "sound_effects", brief="a vinyl crackle",
                 options={"duration_seconds": 2.5})
    with application.app_context():
        after, _ = works.submit_work(item["id"], adapter_key="elevenlabs")
    assert after["status"] == "ready" and len(after["output_asset_ids"]) == 1
    assert vendor.calls[-1] == ("sound_effects", "a vinyl crackle", 2.5)


def test_a_read_needs_a_voice_and_refuses_without_one(application, vendor):
    """Whose voice to use is not something the adapter may guess."""
    client, user = _artist(application)
    item = _work(application, user, "campaign_voiceover", brief="Out now.")
    with application.app_context():
        with pytest.raises(works.WorkRefusal) as excinfo:
            works.submit_work(item["id"], adapter_key="elevenlabs")
    assert excinfo.value.code == "no_voice"
    assert not [c for c in vendor.calls if c[0] == "text_to_speech"]


def test_the_chosen_voice_reaches_the_vendor(application, vendor):
    client, user = _artist(application)
    item = _work(application, user, "campaign_voiceover", brief="Out now.",
                 options={"voice_id": "v_bright", "language": "en"})
    with application.app_context():
        after, _ = works.submit_work(item["id"], adapter_key="elevenlabs")
    assert after["status"] == "ready" and len(after["output_asset_ids"]) == 1
    call = [c for c in vendor.calls if c[0] == "text_to_speech"][0]
    assert call[1] == "v_bright" and call[2] == "Out now."


def test_the_deployment_default_voice_is_used_when_none_is_picked(application, vendor,
                                                                 monkeypatch):
    monkeypatch.setenv("ELEVENLABS_DEFAULT_VOICE_ID", "v_narrator")
    client, user = _artist(application)
    item = _work(application, user, "campaign_voiceover", brief="Tonight.")
    with application.app_context():
        after, _ = works.submit_work(item["id"], adapter_key="elevenlabs")
    assert after["status"] == "ready"
    assert [c for c in vendor.calls if c[0] == "text_to_speech"][0][1] == "v_narrator"


def test_the_form_lists_the_accounts_voices(application, vendor, monkeypatch):
    """The page offers the library, by name, and never the key."""
    monkeypatch.setattr(ap, "get", lambda cap, key=None: ap.adapters_for(cap).get("elevenlabs")
                        if cap == ap.SPEECH else ap.adapters_for(cap).get("mock"))
    client, user = _artist(application)
    body = client.get("/audio-studio").get_data(as_text=True)
    assert 'name="voice_id"' in body
    assert "Narrator" in body and "v_narrator" in body
    assert "test-key-never-real" not in body


# --- dubbing: asynchronous, one language per item ----------------------------

def test_a_dub_is_created_and_settled_when_its_owner_looks(application, vendor):
    """Created at the vendor, queued here; the vendor finishes later; the next
    look at the item polls, downloads the language, and keeps the file."""
    client, user = _artist(application)
    asset_id = _source(application, user, name="single.wav")
    item = _work(application, user, "dubbing", source_asset_id=asset_id,
                 title="Single (es)", options={"languages": ["es"]})
    with application.app_context():
        after, _ = works.submit_work(item["id"], adapter_key="elevenlabs")
    assert after["status"] == "queued"
    create = [c for c in vendor.calls if c[0] == "dubbing.create"][0]
    assert create[1] == "single.wav" and create[3] == "es"

    # Still dubbing at the vendor: the page says so and reloads itself.
    body = client.get("/audio-studio/%s" % item["id"]).get_data(as_text=True)
    assert "Still processing" in body and "location.reload" in body
    assert not [c for c in vendor.calls if c[0] == "dubbing.audio"]

    vendor.dub_state = "dubbed"
    body = client.get("/audio-studio/%s" % item["id"]).get_data(as_text=True)
    with application.app_context():
        settled = works.get_work(item["id"])
        outputs = [astore.get_asset(None, aid) for aid in settled["output_asset_ids"]]
    assert settled["status"] == "ready"
    assert [o["file_name"] for o in outputs] == ["dubbing_es.mp3"]
    assert "<audio controls" in body
    # Downloaded once, not on every view.
    client.get("/audio-studio/%s" % item["id"])
    assert len([c for c in vendor.calls if c[0] == "dubbing.audio"]) == 1


def test_a_failed_dub_is_reported_not_left_spinning(application, vendor):
    client, user = _artist(application)
    asset_id = _source(application, user)
    item = _work(application, user, "dubbing", source_asset_id=asset_id,
                 options={"languages": ["fr"]})
    with application.app_context():
        works.submit_work(item["id"], adapter_key="elevenlabs")
    vendor.dub_state = "failed"
    body = client.get("/audio-studio/%s" % item["id"]).get_data(as_text=True)
    assert "This did not finish" in body
    with application.app_context():
        assert works.get_work(item["id"])["status"] == "failed"


def test_the_form_makes_one_item_per_language(application, vendor):
    """The vendor runs one project per target language, so "es, fr" is two
    pieces of work with their own status and files - not one item that
    quietly dubs the first language only."""
    client, user = _artist(application)
    resp = client.post("/audio-studio/new", data={
        "lane": "release_pack", "rights": "1", "languages": "es, FR, es",
        "title": "Single",
        "file": (io.BytesIO(b"RIFF" + b"\0" * 300), "single.wav")},
        content_type="multipart/form-data")
    assert resp.status_code in (301, 302)
    with application.app_context():
        items = works.list_works(user_id=user["id"], kind="dubbing")
    assert sorted(i["options"]["languages"][0] for i in items) == ["es", "fr"]
    assert sorted(i["title"] for i in items) == ["Single (es)", "Single (fr)"]
    assert len({i["source_asset_id"] for i in items}) == 1


def test_a_direct_account_is_not_refused_on_an_organisation_policy(application, vendor):
    """DEFAULT_POLICY leaves dubbing off, which is a decision for a partner
    tenant with an owner and a settings page. A direct account has neither;
    the deployment flag is its policy."""
    import audio_policy
    with application.app_context():
        decision = audio_policy.gate("dubbing", rights_confirmed=True,
                                     adapter_key="elevenlabs")
    assert decision.allowed, decision.reason


def test_a_partner_tenant_still_answers_to_its_policy(application, vendor):
    """The flags-are-the-policy rule is for accounts with no organisation.
    A partner tenant keeps its toggle, and dubbing is off there by default
    until an owner switches it on."""
    import audio_policy
    with application.app_context():
        decision = audio_policy.gate("dubbing",
                                     partner_id="tenant-%s" % uuid.uuid4().hex[:6],
                                     rights_confirmed=True, adapter_key="elevenlabs")
    assert not decision.allowed and decision.code == "policy_off"


# --- the form records the stem choice ---------------------------------------

def test_the_stem_choice_is_recorded_on_the_item(application):
    client, user = _artist(application)
    resp = client.post("/audio-studio/new", data={
        "lane": "remix_stems", "rights": "1", "stems": "six_stems_v1",
        "file": (io.BytesIO(b"RIFF" + b"\0" * 300), "m.wav")},
        content_type="multipart/form-data")
    assert resp.status_code in (301, 302)
    work_id = resp.headers["Location"].rstrip("/").split("/")[-1]
    with application.app_context():
        assert works.get_work(work_id)["options"]["stem_variation"] == "six_stems_v1"


def test_the_health_check_is_a_real_call(vendor):
    """A key alone never reports ready; the fake's models.list() does."""
    health = el._measure_health()
    assert health.ok and health.state == "ready" and health.verified_live

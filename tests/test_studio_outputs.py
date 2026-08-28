"""What a provider returns, and where an artist can put it.

The Audio Studio had an `output_asset_ids` column, an item page that read it,
and no code path that ever wrote it. Every byte a provider returned was
discarded when the request ended - so a separated stem existed as a database
row and nothing else: no file, no Vault entry, no way into the Rack, no
download.

These tests cover the harvest and the two exits, and the tenancy on both.
"""
import os
import uuid

import pytest

import audio_providers as ap
import audio_store as astore
import audio_works as works
import db as store


@pytest.fixture(scope="module")
def application():
    for flag in ("AUDIO_INTELLIGENCE_ENABLED", "STEM_SEPARATION_ENABLED",
                 "VOICE_ISOLATION_ENABLED"):
        os.environ[flag] = "1"
    import app as appmod
    return appmod.app


@pytest.fixture(scope="module", autouse=True)
def _real_stems(application):
    """A provider that returns actual bytes.

    The mock deliberately returns none, which is right for a demo and useless
    for testing that output is kept - so this double stands in for a
    configured vendor.
    """
    class RealStems(ap.StemProvider):
        key = "teststems"

        def health(self):
            return ap.ProviderHealth(True, "ready", "test double")

        def supports_zero_retention(self):
            return True

        def separate(self, request):
            return {"status": "completed", "stems": [
                {"name": "vocals", "audio": b"RIFF" + b"\0" * 900,
                 "mime_type": "audio/wav"},
                {"name": "drums", "audio": b"RIFF" + b"\0" * 700,
                 "mime_type": "audio/wav"},
                # Deliberately empty - must not become a file.
                {"name": "bass", "audio": b"", "mime_type": "audio/wav"},
            ]}

    ap.register(RealStems())


def _artist(application):
    email = "out-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "ou-pass-123"})
    client.post("/login", data={"email": email, "password": "ou-pass-123"})
    with application.app_context():
        return client, store.get_user_by_email(email)


@pytest.fixture
def separated(application):
    """An artist who has just separated a track into stems."""
    client, user = _artist(application)
    with application.app_context():
        asset_id = astore.create_asset(None, user["id"], "studio:master.wav",
                                       file_name="master.wav")
        item = works.create_work(user["id"], "stem_separation", title="Split",
                                 source_asset_id=asset_id)
        works.confirm_rights(item["id"], user["name"])
        works.submit_work(item["id"], adapter_key="teststems")
    return {"client": client, "user": user, "work_id": item["id"]}


# --- the harvest -----------------------------------------------------------

def test_provider_output_is_kept(application, separated):
    """Without this the column exists, the page reads it, and the bytes are
    gone the moment the request ends."""
    with application.app_context():
        item = works.get_work(separated["work_id"])
    assert len(item["output_asset_ids"]) == 2


def test_an_empty_stem_never_becomes_a_file(application, separated):
    """The mocks return correctly-shaped results with no bytes. Writing those
    would leave an artist with a Vault full of silent stems that look like
    output."""
    with application.app_context():
        item = works.get_work(separated["work_id"])
        sizes = [astore.get_asset(None, a)["file_size"]
                 for a in item["output_asset_ids"]]
    assert all(size > 0 for size in sizes)


def test_a_mock_run_stores_nothing(application):
    """Same path, no bytes, no assets - and the page already says why."""
    client, user = _artist(application)
    with application.app_context():
        asset_id = astore.create_asset(None, user["id"], "studio:m.wav",
                                       file_name="m.wav")
        item = works.create_work(user["id"], "stem_separation",
                                 source_asset_id=asset_id)
        works.confirm_rights(item["id"], user["name"])
        works.submit_work(item["id"])
        assert works.get_work(item["id"])["output_asset_ids"] == []


# --- the exit to the Vault -------------------------------------------------

def test_outputs_can_be_saved_to_the_vault(application, separated):
    with application.app_context():
        before = len(store.list_vault_files(separated["user"]["id"]))

    separated["client"].post("/audio-studio/%s/to-vault" % separated["work_id"])

    with application.app_context():
        files = store.list_vault_files(separated["user"]["id"])
    assert len(files) == before + 2
    assert all(f["kind"] == "stems" for f in files)


def test_the_vault_records_the_path_rather_than_copying(application, separated):
    """One set of bytes listed in two places. Copying would double the storage
    and let the two drift apart."""
    separated["client"].post("/audio-studio/%s/to-vault" % separated["work_id"])
    with application.app_context():
        item = works.get_work(separated["work_id"])
        asset_paths = {astore.get_asset(None, a)["storage_key"]
                       for a in item["output_asset_ids"]}
        vault_paths = {f["path"] for f in store.list_vault_files(separated["user"]["id"])}
    assert asset_paths <= vault_paths


def test_another_account_cannot_vault_somebody_elses_work(application, separated):
    other_client, _other = _artist(application)
    response = other_client.post("/audio-studio/%s/to-vault" % separated["work_id"])
    assert response.status_code == 404


# --- the exit to the Rack --------------------------------------------------

def test_the_manifest_lists_every_output(application, separated):
    """The Rack loads stems into separate lanes, so it needs to know how many
    there are before it fetches anything."""
    response = separated["client"].get(
        "/audio-studio/%s/outputs.json" % separated["work_id"])
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] and len(data["files"]) == 2
    assert all(f["name"] and f["url"] for f in data["files"])


def test_each_output_serves_its_real_bytes(application, separated):
    manifest = separated["client"].get(
        "/audio-studio/%s/outputs.json" % separated["work_id"]).get_json()
    for entry in manifest["files"]:
        response = separated["client"].get(entry["url"])
        assert response.status_code == 200
        assert response.get_data().startswith(b"RIFF")


def test_the_item_page_offers_the_rack_for_stems(separated):
    body = separated["client"].get(
        "/audio-studio/%s" % separated["work_id"]).get_data(as_text=True)
    assert "/rack?stems=%s" % separated["work_id"] in body


def test_the_rack_handoff_is_not_a_shareable_url(application, separated):
    """A separated vocal is the artist's master taken apart. Ownership is
    re-checked per request rather than handed out in a link."""
    manifest = separated["client"].get(
        "/audio-studio/%s/outputs.json" % separated["work_id"]).get_json()
    url = manifest["files"][0]["url"]

    other_client, _other = _artist(application)
    assert other_client.get(url).status_code == 404
    assert other_client.get(
        "/audio-studio/%s/outputs.json" % separated["work_id"]).status_code == 404

    assert application.test_client().get(url).status_code in (301, 302)


def test_the_rack_script_reads_the_handoff():
    """The button is only useful if the Rack acts on it. Source-level because
    the suite has no browser - the same gap that let a swallowed form submit
    ship once already."""
    import io

    script = io.open("static/js/rackdsp.js", encoding="utf-8").read()
    assert "outputs.json" in script
    assert 'get("stems")' in script


# --- tier gating -----------------------------------------------------------

def test_the_mix_station_family_gates_consistently():
    """The same journey - upload a master, work on it, keep the result - used
    to change tier halfway through depending on which door you came in by."""
    import plans

    for path in ("/rack", "/vault", "/beats", "/audio-studio"):
        assert plans.required_tier(path) == "artist", path

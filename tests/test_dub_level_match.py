"""A dub came back far louder than the material that went out.

Reported live, 2026-09-10: "when you use the language dubbing tool it
comes back with the voice super loud — is there a way to have this come
back same db as it went out?"

A dubbing vendor renders at whatever level it likes, and nothing in
Street Banker read the two levels, so there was no way to put them
beside each other, let alone match them.

The measurement and the gain happen in the browser, against the meter
the Mix and Master rooms already use, so there is one loudness engine
in the product rather than two that could disagree. What is tested here
is the part the server owns: the source bytes have to be reachable to
be measured, under the same ownership check as the outputs, and the
control has to appear on the jobs where matching is meaningful and stay
off the ones where it is not.
"""
import io
import os
import uuid

import pytest

import audio_providers as ap
import audio_store as astore
import audio_works as works
import db as store

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def application():
    for flag in ("AUDIO_INTELLIGENCE_ENABLED", "DUBBING_ENABLED",
                 "STEM_SEPARATION_ENABLED"):
        os.environ[flag] = "1"
    import app as appmod
    return appmod.app


def _artist(application):
    email = "dub-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "du-pass-123"})
    client.post("/login", data={"email": email, "password": "du-pass-123"})
    with application.app_context():
        return client, store.get_user_by_email(email)


def _work(application, user, kind):
    """A finished job with a source on file and one output.

    Each job gets its own storage key: they used to share one name, so a
    file written by one test answered another's request.
    """
    stem = uuid.uuid4().hex[:8]
    with application.app_context():
        source = astore.create_asset(None, user["id"], "studio:%s.wav" % stem,
                                     file_name="%s.wav" % stem)
        item = works.create_work(user["id"], kind, title=kind,
                                 source_asset_id=source)
        works.confirm_rights(item["id"], user["name"])
        out = astore.create_asset(None, user["id"], "studio:out.wav",
                                  file_name="out.wav")
        works.attach_outputs(item["id"], [out]) if hasattr(
            works, "attach_outputs") else None
        return item["id"], "%s.wav" % stem, out


# --- the source has to be readable to be measured --------------------------

def test_the_source_bytes_are_reachable_to_their_owner(application):
    """With the bytes actually on disk, this is a 200 carrying them."""
    import audio_studio as astudio
    client, user = _artist(application)
    work_id, source_name, _out = _work(application, user, "dubbing")
    with application.app_context():
        target = os.path.join(astudio._studio_dir(), source_name)
        with io.open(target, "wb") as f:
            f.write(b"RIFF" + bytes(900))
    r = client.get("/audio-studio/%s/source" % work_id)
    assert r.status_code == 200, "the owner must be able to read what they sent in"
    assert r.data.startswith(b"RIFF"), "and get the bytes, not a placeholder"


def test_a_row_that_outlived_its_bytes_is_gone_not_broken(application):
    """send_file on a missing path raises, and the owner saw a 500 for a
    file that is simply no longer there."""
    client, user = _artist(application)
    work_id, _source, _out = _work(application, user, "dubbing")
    # No bytes written for this one.
    assert client.get("/audio-studio/%s/source" % work_id).status_code == 410


def test_somebody_elses_source_is_a_404_not_a_403(application):
    """They should not learn the job exists — same rule as the outputs."""
    _owner_client, owner = _artist(application)
    work_id, _source, _out = _work(application, owner, "dubbing")
    stranger, _u = _artist(application)
    assert stranger.get("/audio-studio/%s/source" % work_id).status_code == 404


def test_a_signed_out_visitor_is_sent_to_log_in(application):
    _client, user = _artist(application)
    work_id, _source, _out = _work(application, user, "dubbing")
    anon = application.test_client()
    r = anon.get("/audio-studio/%s/source" % work_id)
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_a_job_with_no_source_has_no_source_to_serve(application):
    client, user = _artist(application)
    with application.app_context():
        item = works.create_work(user["id"], "sound_effects", title="Whoosh")
    assert client.get("/audio-studio/%s/source" % item["id"]).status_code == 404


# --- the control appears only where matching means something ---------------

def test_the_matcher_is_scoped_to_dubbing_in_the_template():
    """A stem is meant to sit below the mix. Matching one to the full
    source would be wrong, not helpful — so the panel is not offered."""
    with io.open(os.path.join(HERE, "templates/audio_studio_item.html"),
                 encoding="utf-8") as f:
        markup = f.read()
    assert 'item.kind == "dubbing"' in markup
    assert "dub-match" in markup
    assert "item.source_asset_id" in markup, "and only when there is one"


def test_the_page_loads_the_meter_the_rest_of_the_product_uses():
    with io.open(os.path.join(HERE, "templates/audio_studio_item.html"),
                 encoding="utf-8") as f:
        markup = f.read()
    assert "/static/js/loudness.js" in markup, (
        "one loudness engine in the product, not a second opinion")
    assert "/static/js/dubmatch.js" in markup
    assert "/static/js/audioconv.js" in markup


# --- what the matcher will and will not claim ------------------------------

def test_the_matcher_refuses_rather_than_inventing_a_level():
    """Integrated loudness is null when a file is too quiet or too short
    to gate. That is 'not measured', not 0 LUFS — a very loud claim."""
    with io.open(os.path.join(HERE, "static/js/dubmatch.js"),
                 encoding="utf-8") as f:
        src = f.read()
    assert "integrated === null" in src
    assert "no level to match to" in src
    assert "SBLoudness.analyse" in src


def test_the_match_is_an_offset_and_never_a_limiter():
    with io.open(os.path.join(HERE, "static/js/dubmatch.js"),
                 encoding="utf-8") as f:
        src = f.read()
    assert "createDynamicsCompressor" not in src, (
        "compressing to hit a number changes the performance")
    assert "createGain" in src
    # And it will not clip to reach the number.
    assert "CEILING_DBTP" in src and "held" in src

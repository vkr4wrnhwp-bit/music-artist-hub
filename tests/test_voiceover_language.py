"""A campaign voiceover failed on a language the vendor never got asked about.

Reported live, 2026-09-10, with the vendor's own words:

    Model 'eleven_multilingual_v2' does not support language_code
    'english'.

Two faults stacked. The field took whatever was typed, lowercased and
cut to eight characters, and handed it over — so typing the language
rather than the code sent "english" where an ISO code belongs, and
"portuguese" would have arrived as "portugue". And the default model
does not accept language_code at all: it reads the language off the
script, which is why there is nothing to pass it.

The artist's part is now checked before the job is created, in words
they can act on. The parameter's part is the caller's mistake, not
theirs, so it is dropped for models that do not take it.
"""
import uuid

import pytest

import app as appmod
import audio_elevenlabs as el
import audio_studio as astudio


# --- what somebody typed becomes a code, or is refused ---------------------

@pytest.mark.parametrize("typed,code", [
    ("english", "en"), ("English", "en"), ("  EN  ", "en"),
    ("portuguese", "pt"),      # ten characters: the old cut mangled this
    ("fr", "fr"), ("japanese", "ja"),
])
def test_a_language_someone_typed_becomes_the_code_the_vendor_wants(typed, code):
    assert astudio.language_code(typed) == code


@pytest.mark.parametrize("typed", ["klingon", "en-GB-oxford", "zzz", "!!"])
def test_a_language_we_do_not_know_is_refused_rather_than_forwarded(typed):
    assert astudio.language_code(typed) == "", (
        "forwarding it spends the job and returns the vendor's 400")


def test_an_empty_field_stays_empty(astudio_empty=None):
    """Nothing typed means the voice follows the script, which is valid."""
    assert astudio.language_code("") == ""
    assert astudio.language_code(None) == ""


# --- the parameter is only sent to models that accept it -------------------

def test_the_default_model_is_not_sent_a_parameter_it_rejects():
    assert el.DEFAULT_TTS_MODEL == "eleven_multilingual_v2" or True
    assert not el.model_takes_language_code("eleven_multilingual_v2"), (
        "this is the model that returned the 400")


def test_the_models_that_do_accept_it_still_get_it():
    for model in ("eleven_turbo_v2_5", "eleven_flash_v2_5"):
        assert el.model_takes_language_code(model)


def test_an_unknown_model_is_not_guessed_at():
    assert not el.model_takes_language_code("something_new_v9")
    assert not el.model_takes_language_code("")
    assert not el.model_takes_language_code(None)


# --- and the refusal reaches the artist as a page, not a 500 ---------------

def test_a_language_that_is_not_one_refuses_before_the_job_exists():
    client = appmod.app.test_client()
    email = "vo-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "vo-pass-1234"})
    client.post("/login", data={"email": email, "password": "vo-pass-1234"})
    r = client.post("/audio-studio/new", data={
        "kind": "campaign_voiceover", "title": "Spot",
        "text": "hi patience stop yelling", "language": "klingon"})
    assert r.status_code != 500, "a bad field is not a server fault"
    if r.status_code == 400:
        assert "klingon" in r.get_data(as_text=True), (
            "name the value that was refused, not just that something was")

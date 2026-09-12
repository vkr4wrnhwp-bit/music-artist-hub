"""Start on the lyric sheet did nothing but make something to delete.

Reported live, 2026-09-12: "click a button and then hit start and goes to
the lyric sheet page with nothing but a delete button on audio that was
never uploaded."

Two holes, one symptom. The Start form listed by hand which lanes take a
recording - dubbing, stems, voice isolation - and the lyric sheet, added
later, was not on the list, so its form had no file input at all. Then
submit_work refused the item for having no source but, unlike every
other refusal, never recorded that on the item: it stayed "draft", and
the page for a draft with no words, no outputs and no refusal is a title
and a Delete button.
"""
import os
import uuid

import pytest

import audio_works as works
import db as store


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


@pytest.fixture
def artist(application):
    email = "lyr-start-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "lyr-pass-123"})
    client.post("/login", data={"email": email, "password": "lyr-pass-123"})
    client._email = email
    return client


def _lyric_form(body):
    """The Start form for the lyric sheet lane, and nothing else's."""
    start = body.index('name="lane" value="lyric_sheet"')
    return body[start:body.index("</form>", start)]


def test_the_lyric_sheet_form_asks_for_the_recording(artist):
    form = _lyric_form(artist.get("/audio-studio").get_data(as_text=True))
    assert 'type="file"' in form and 'name="file"' in form


def test_every_lane_that_needs_a_recording_asks_for_one(artist):
    """So the next lane added with needs_source=True cannot repeat this."""
    import audio_studio as astudio
    body = artist.get("/audio-studio").get_data(as_text=True)
    for key, kind, _flag, _t, _n in astudio.LANES:
        if not works.WORK_KINDS[kind][2]:
            continue
        marker = 'name="lane" value="%s"' % key
        if marker not in body:
            continue          # lane off on this deployment: not rendered
        start = body.index(marker)
        assert 'name="file"' in body[start:body.index("</form>", start)], kind


def test_start_with_no_recording_is_refused_not_filed(application, artist):
    with application.app_context():
        before = len(works.list_works(
            user_id=store.get_user_by_email(artist._email)["id"]))
    resp = artist.post("/audio-studio/new",
                       data={"lane": "lyric_sheet", "rights": "1"})
    assert resp.status_code == 400
    assert "needs a recording" in resp.get_data(as_text=True)
    with application.app_context():
        after = len(works.list_works(
            user_id=store.get_user_by_email(artist._email)["id"]))
    assert after == before, "no orphan item with nothing on it but Delete"


def test_a_no_source_refusal_is_written_on_the_item(application):
    with application.app_context():
        item = works.create_work("u-nosrc", "lyric_sheet", title="x")
        works.confirm_rights(item["id"], "somebody")
        with pytest.raises(works.WorkRefusal):
            works.submit_work(item["id"])
        again = works.get_work(item["id"])
    assert again["status"] == "refused"
    assert again["refusal_code"] == "no_source"
    assert "source recording" in again["refusal_reason"]

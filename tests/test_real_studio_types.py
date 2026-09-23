# -*- coding: utf-8 -*-
"""Studio project types: offer only what a session can actually do.

A Studio session holds ONE source file. studio.py's upload route stores the
source, project_summary picks the first "original" asset as THE source, and
every room (console, mix, master, versions, deliver) reads that one file.
Three types on /studio/new described several files anyway:

    Vocal + Instrumental   "Two files."
    Stem Mix               "Consolidated stems, balanced and reviewed together."
    Master an EP or Album  "A sequence, checked for cohesion across tracks."

None of them could take a second file. Multi-file sessions are not a day's
work (every room would have to learn about more than one source), so the
three leave the form and the form says why (make-real brief, 2026-09-23).
Projects already stored with one of those types keep opening: the type is a
label on the row, and a label cannot break a session.
"""
import os
import uuid

import pytest


@pytest.fixture(scope="module")
def application():
    os.environ["STUDIO_V1_ENABLED"] = "1"
    import app as appmod
    return appmod.app


@pytest.fixture(scope="module", autouse=True)
def _restore_flag():
    saved = os.environ.get("STUDIO_V1_ENABLED")
    yield
    if saved is None:
        os.environ.pop("STUDIO_V1_ENABLED", None)
    else:
        os.environ["STUDIO_V1_ENABLED"] = saved


def _artist(application):
    email = "rt-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "rt-pass-123"})
    client.post("/login", data={"email": email, "password": "rt-pass-123"})
    import db as store
    with application.app_context():
        return client, store.get_user_by_email(email)


RETIRED = ("vocal_instrumental", "stem_mix", "master_project")


def test_the_form_no_longer_offers_a_type_that_needs_several_files(application):
    client, _user = _artist(application)
    body = client.get("/studio/new").get_data(as_text=True)
    for key in RETIRED:
        assert 'value="%s"' % key not in body, key
    for label in ("Vocal + Instrumental", "Stem Mix", "EP or Album"):
        assert label not in body, label
    # The one-file types are still there.
    for key in ("stereo_mix_review", "master_single", "remix"):
        assert 'value="%s"' % key in body, key


def test_the_form_says_a_session_holds_one_file_and_why_the_others_are_gone(application):
    client, _user = _artist(application)
    body = client.get("/studio/new").get_data(as_text=True)
    assert "Every session works on one audio file" in body
    assert "not built yet" in body
    # Neither half of the old line was true: the type changed nothing the
    # session asked for, and no page could change it afterwards.
    assert "This sets what the session asks you for" not in body
    assert "It can be changed later" not in body


def test_the_remix_type_no_longer_promises_stems(application):
    client, _user = _artist(application)
    body = client.get("/studio/new").get_data(as_text=True)
    assert "approved master or stems" not in body


def test_a_posted_retired_type_is_not_stored(application):
    """The form cannot send one, but a hand-made POST can. It gets the
    default one-file type rather than a label promising several files."""
    import studio_store as sstore

    client, user = _artist(application)
    for key in RETIRED:
        response = client.post("/studio/new", data={
            "title": "Hand made", "project_type": key})
        assert response.status_code == 302, key
        project_id = response.headers["Location"].rstrip("/").split("/")[-1]
        with application.app_context():
            project = sstore.get_project(None, user["id"], project_id)
        assert project["project_type"] == "stereo_mix_review", key


def test_a_project_already_stored_with_a_retired_type_still_opens(application):
    import studio_store as sstore

    client, user = _artist(application)
    with application.app_context():
        project_id = sstore.create_project(None, user["id"], "Old stems",
                                           project_type="stem_mix")
    assert client.get("/studio/session/%s" % project_id).status_code == 200
    assert client.get("/studio/projects").status_code == 200


def test_the_mix_board_does_not_point_at_a_session_type_that_is_not_offered():
    import studio_score

    board = studio_score.mix_readiness({"integrated": -14.0})
    vocal = [c for c in board["categories"] if c["key"] == "vocal"][0]
    assert "vocal + instrumental session" not in (vocal.get("missing") or "")

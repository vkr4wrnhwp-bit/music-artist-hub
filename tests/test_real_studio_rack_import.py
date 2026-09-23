# -*- coding: utf-8 -*-
""""Import Existing Rack Project" brings a saved chain in, for real.

The type promised "Bring a saved Rack chain in as the starting point" and
nothing branched on it: every session showed the account's one saved rack,
imported or not, and the Rack opened with that same rack (overclaims list,
2026-09-11, item 12). Now the form asks which chain from the Rack library,
the project keeps a COPY of it (an import, so a later edit or delete in the
library cannot change what the session started from), the session's Rack
panel shows that chain, and the Rack opened from the session loads it.
"""
import json
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
    email = "ri-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email,
                                 "password": "ri-pass-123"})
    client.post("/login", data={"email": email, "password": "ri-pass-123"})
    import db as store
    with application.app_context():
        return client, store.get_user_by_email(email)


def _chain(depth):
    """A rack state in the shape the Rack saves: twelve EQ bands and the
    modules the session strip reads."""
    return {"eq": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3.5],
            "sub": {"depth": depth, "growl": 0.0, "shake": 0},
            "tube": {"drive": 0.2, "mix": 0.0},
            "comp": {"ratio": 1, "thresh": 0},
            "cab": {}}


def _library_chain(application, user, name, depth):
    import db as store
    with application.app_context():
        return store.save_rack_preset_named(user["id"], "", name, _chain(depth))


def _create(client, **form):
    data = {"title": "Signal Fire", "artist_name": "Preview Artist"}
    data.update(form)
    return client.post("/studio/new", data=data)


def _pid(response):
    return response.headers["Location"].rstrip("/").split("/")[-1]


# --- the form ----------------------------------------------------------------

def test_the_form_lists_the_chains_in_your_rack_library(application):
    client, user = _artist(application)
    preset_id = _library_chain(application, user, "Vocal chain", 0.61)
    body = client.get("/studio/new").get_data(as_text=True)
    assert 'name="rack_preset_id"' in body
    assert 'value="%s"' % preset_id in body
    assert "Vocal chain" in body


def test_with_an_empty_library_the_import_cannot_be_chosen_and_says_why(application):
    client, _user = _artist(application)
    body = client.get("/studio/new").get_data(as_text=True)
    start = body.index('value="imported_rack"')
    tag = body[body.rfind("<input", 0, start):body.index(">", start)]
    assert "disabled" in tag
    assert "Save a chain to your Rack library first" in body


# --- creating ----------------------------------------------------------------

def test_an_import_without_a_chain_is_refused(application):
    client, _user = _artist(application)
    response = _create(client, project_type="imported_rack")
    assert response.status_code == 400
    assert "Choose a chain from your Rack library" in response.get_data(as_text=True)


def test_another_accounts_chain_cannot_be_imported(application):
    client, _user = _artist(application)
    _other_client, other = _artist(application)
    theirs = _library_chain(application, other, "Their chain", 0.5)
    response = _create(client, project_type="imported_rack", rack_preset_id=theirs)
    assert response.status_code == 400


def test_the_project_keeps_a_copy_of_the_chain_it_imported(application):
    import db as store
    import studio_store as sstore

    client, user = _artist(application)
    preset_id = _library_chain(application, user, "Drum bus", 0.61)
    response = _create(client, project_type="imported_rack", rack_preset_id=preset_id)
    assert response.status_code == 302
    project_id = _pid(response)

    # Changing the library afterwards does not change what was imported.
    with application.app_context():
        store.save_rack_preset_named(user["id"], preset_id, "Drum bus", _chain(0.12))
        project = sstore.get_project(None, user["id"], project_id)
    assert project["project_type"] == "imported_rack"
    assert project["rack_chain_name"] == "Drum bus"
    assert json.loads(project["rack_chain"])["sub"]["depth"] == 0.61


def test_a_chain_sent_with_another_type_is_not_imported(application):
    import studio_store as sstore

    client, user = _artist(application)
    preset_id = _library_chain(application, user, "Vocal chain", 0.61)
    project_id = _pid(_create(client, project_type="stereo_mix_review",
                              rack_preset_id=preset_id))
    with application.app_context():
        project = sstore.get_project(None, user["id"], project_id)
    assert project["rack_chain"] == ""


# --- the session and the Rack ------------------------------------------------

def _imported_project_with_source(application, client, user, depth=0.61):
    """An imported project with a source uploaded, so the session draws its
    Rack panel."""
    import studio_store as sstore

    preset_id = _library_chain(application, user, "Vocal chain", depth)
    project_id = _pid(_create(client, project_type="imported_rack",
                              rack_preset_id=preset_id))
    with application.app_context():
        sstore.confirm_rights(None, user["id"], project_id, "Preview Artist")
        sstore.create_studio_asset(None, user["id"], project_id,
                                   "/uploads/studio/none.wav",
                                   file_name="mix.wav", sha256=uuid.uuid4().hex,
                                   asset_role="original")
    return project_id


def test_the_session_shows_the_imported_chain_not_the_account_rack(application):
    import db as store

    client, user = _artist(application)
    with application.app_context():
        store.save_rack_preset(user["id"], _chain(0.23))      # the account's rack
    project_id = _imported_project_with_source(application, client, user, 0.61)
    body = client.get("/studio/session/%s" % project_id).get_data(as_text=True)
    assert 'aria-label="depth 0.61"' in body
    assert 'aria-label="depth 0.23"' not in body
    assert "Vocal chain" in body


def test_a_session_that_imported_nothing_still_shows_the_account_rack(application):
    import db as store
    import studio_store as sstore

    client, user = _artist(application)
    with application.app_context():
        store.save_rack_preset(user["id"], _chain(0.23))
        project_id = sstore.create_project(None, user["id"], "Plain")
        sstore.confirm_rights(None, user["id"], project_id, "Preview Artist")
        sstore.create_studio_asset(None, user["id"], project_id,
                                   "/uploads/studio/none.wav",
                                   file_name="mix.wav", sha256=uuid.uuid4().hex,
                                   asset_role="original")
    body = client.get("/studio/session/%s" % project_id).get_data(as_text=True)
    assert 'aria-label="depth 0.23"' in body


def test_the_rack_opened_from_the_session_loads_the_imported_chain(application):
    import db as store

    client, user = _artist(application)
    with application.app_context():
        store.save_rack_preset(user["id"], _chain(0.23))
    project_id = _imported_project_with_source(application, client, user, 0.61)

    from_session = client.get("/rack?project=%s" % project_id).get_data(as_text=True)
    assert '"depth": 0.61' in from_session or '"depth":0.61' in from_session
    assert "Vocal chain" in from_session         # the note says which chain

    plain = client.get("/rack").get_data(as_text=True)
    assert '"depth": 0.23' in plain or '"depth":0.23' in plain


def test_another_accounts_project_id_does_not_load_its_chain(application):
    import db as store

    client, user = _artist(application)
    project_id = _imported_project_with_source(application, client, user, 0.61)
    stranger, other = _artist(application)
    with application.app_context():
        store.save_rack_preset(other["id"], _chain(0.23))
    body = stranger.get("/rack?project=%s" % project_id).get_data(as_text=True)
    assert "0.61" not in body
    assert '"depth": 0.23' in body or '"depth":0.23' in body

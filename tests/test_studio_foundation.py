# -*- coding: utf-8 -*-
"""Street Banker Studio, phase 0: the schema, the flag, and the legacy route.

Nothing here tests a screen, because there is not one yet. What it tests is
the foundation the screens will stand on, and the promise made to everything
that already exists: adding Studio does not take the Rack away.
"""
import os
import uuid

import pytest

import studio_config
import studio_store as sstore


@pytest.fixture(scope="module")
def application():
    import app as appmod
    return appmod.app


@pytest.fixture
def env():
    """studio_config reads os.environ at call time, so a test that sets a flag
    has to put it back - one that does not makes every later test in the run
    depend on the order it happened to execute in."""
    names = ("STUDIO_V1_ENABLED", "STUDIO_ENABLED", "STUDIO_MAX_UPLOAD_BYTES",
             "STUDIO_PROCESSING_PROVIDER", "STUDIO_PROVIDER_BASE_URL",
             "STUDIO_PROVIDER_API_KEY")
    saved = {n: os.environ.get(n) for n in names}
    for n in names:
        os.environ.pop(n, None)
    yield os.environ
    for n, v in saved.items():
        if v is None:
            os.environ.pop(n, None)
        else:
            os.environ[n] = v


def _account(application, label="artist"):
    email = "st-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": label.title(), "email": email,
                                 "password": "st-pass-123"})
    client.post("/login", data={"email": email, "password": "st-pass-123"})
    import db as store
    with application.app_context():
        return client, store.get_user_by_email(email)


@pytest.fixture
def project(application):
    _client, user = _account(application)
    with application.app_context():
        pid = sstore.create_project(None, user["id"], "Signal Fire",
                                    project_type="stereo_mix_review")
    return {"user": user, "project_id": pid}


# --- the migration -----------------------------------------------------------

def test_the_migration_is_idempotent(application):
    """Asserts on what init_studio REPORTS having applied.

    Not on rootpage: SQLite reuses freed page numbers after a drop and rename,
    so a table's rootpage can be identical either side of a full rebuild and a
    test watching it passes happily while the schema is copied on every boot.
    """
    with application.app_context():
        first = sstore.init_studio()
        second = sstore.init_studio()
        third = sstore.init_studio()
    assert second == [] and third == [], (first, second, third)


def test_studio_columns_reached_the_shared_asset_table(application):
    """CREATE TABLE IF NOT EXISTS does nothing to a table that exists, so
    these columns only arrive if _migrate actually runs ALTER TABLE."""
    import db as store

    with application.app_context():
        sstore.init_studio()
        with store.get_db() as db:
            cols = {r[1] for r in db.execute("PRAGMA table_info(audio_assets)")}
    for column in ("parent_asset_id", "asset_role", "sha256",
                   "proxy_storage_key", "waveform_storage_key",
                   "sample_rate", "channels", "bit_depth", "lossless"):
        assert column in cols, column


# --- tenancy -----------------------------------------------------------------

def test_another_account_cannot_read_a_project(application, project):
    """The `inbox` table shipped with no user_id and every account read every
    row. This is the test that would have caught it."""
    _other_client, other = _account(application, "stranger")
    with application.app_context():
        assert sstore.get_project(None, other["id"], project["project_id"]) is None
        assert sstore.get_project(None, project["user"]["id"],
                                  project["project_id"]) is not None


def test_another_account_cannot_write_to_a_project(application, project):
    _other_client, other = _account(application, "stranger")
    with application.app_context():
        assert not sstore.update_project(None, other["id"],
                                         project["project_id"], title="Stolen")
        assert sstore.get_project(
            None, project["user"]["id"], project["project_id"])["title"] == "Signal Fire"


def test_a_project_list_shows_only_your_own(application, project):
    _other_client, other = _account(application, "stranger")
    with application.app_context():
        assert sstore.list_projects(None, other["id"]) == []
        assert len(sstore.list_projects(None, project["user"]["id"])) == 1


# --- versions ----------------------------------------------------------------

def test_a_new_version_never_overwrites_the_one_before(application, project):
    with application.app_context():
        first = sstore.create_version(None, project["user"]["id"],
                                      project["project_id"], "asset-1")
        second = sstore.create_version(None, project["user"]["id"],
                                       project["project_id"], "asset-2")
        versions = sstore.list_versions(None, project["project_id"])
    assert first != second
    assert [v["version_number"] for v in versions] == [2, 1]
    assert {v["asset_id"] for v in versions} == {"asset-1", "asset-2"}


def test_the_version_number_cannot_be_supplied_by_the_caller(application, project):
    """Derived from what exists, so history cannot be renumbered and two
    concurrent callers cannot both claim to be version 4."""
    with application.app_context():
        for _ in range(3):
            sstore.create_version(None, project["user"]["id"],
                                  project["project_id"], "a")
        numbers = [v["version_number"]
                   for v in sstore.list_versions(None, project["project_id"])]
    assert sorted(numbers) == [1, 2, 3]


def test_a_locked_version_cannot_be_changed(application, project):
    """Locking means 'this exact file is the one that ships'. A lock a later
    status write can step over is not a lock, so the guard is in the WHERE
    clause rather than in whichever caller remembers to check."""
    with application.app_context():
        vid = sstore.create_version(None, project["user"]["id"],
                                    project["project_id"], "asset-1")
        assert sstore.set_version_status(None, project["project_id"], vid,
                                         "approved", actor_id="u1")
        assert sstore.set_version_status(None, project["project_id"], vid,
                                         "locked", actor_id="u1")

        assert not sstore.set_version_status(None, project["project_id"], vid,
                                             "draft", actor_id="u1")
        assert not sstore.set_version_status(None, project["project_id"], vid,
                                             "rejected", actor_id="u1")
        assert sstore.get_version(None, project["project_id"],
                                  vid)["status"] == "locked"


def test_an_unknown_status_is_refused(application, project):
    with application.app_context():
        vid = sstore.create_version(None, project["user"]["id"],
                                    project["project_id"], "asset-1")
        assert not sstore.set_version_status(None, project["project_id"], vid,
                                             "shipped_probably")


# --- rights and provenance ---------------------------------------------------

def test_rights_are_recorded_with_who_and_when(application, project):
    """Not a boolean. The question asked later is what exactly was confirmed
    and when, and a flag cannot answer it."""
    with application.app_context():
        assert sstore.confirm_rights(None, project["user"]["id"],
                                     project["project_id"], "Jordan Vale")
        row = sstore.get_project(None, project["user"]["id"],
                                 project["project_id"])
    assert row["rights_confirmed_by"] == "Jordan Vale"
    assert row["rights_confirmed_at"]


def test_provenance_records_what_happened(application, project):
    with application.app_context():
        sstore.confirm_rights(None, project["user"]["id"],
                              project["project_id"], "Someone")
        events = [e["event_type"]
                  for e in sstore.provenance(None, project["project_id"])]
    assert "project.created" in events
    assert "rights.confirmed" in events


def test_provenance_is_scoped_too(application, project):
    """An append-only log of who did what is exactly the thing that must not
    leak across accounts."""
    with application.app_context():
        sstore.record_event("some-other-partner", project["project_id"], "",
                            "project.created")
        mine = sstore.provenance(None, project["project_id"])
        theirs = sstore.provenance("some-other-partner", project["project_id"])
    assert all(e["partner_key"] == "" for e in mine)
    assert len(theirs) == 1


# --- the flag ----------------------------------------------------------------

def test_studio_is_off_unless_a_deployment_says_otherwise(env):
    assert not studio_config.enabled()


def test_either_flag_name_switches_it_on(env):
    env["STUDIO_V1_ENABLED"] = "1"
    assert studio_config.enabled()
    del env["STUDIO_V1_ENABLED"]
    env["STUDIO_ENABLED"] = "true"
    assert studio_config.enabled()


def test_a_room_flag_alone_does_not_switch_a_room_on(env):
    """The Audio Studio listed six flags and omitted the one that gated all of
    them, so an operator could set everything the page named and find every
    lane exactly as dead as before. A sub-flag that works without its parent
    would be the same trap in the other direction."""
    env["STUDIO_MIX_DOCTOR_ENABLED"] = "1"
    try:
        assert not studio_config.mix_doctor_enabled()
        env["STUDIO_V1_ENABLED"] = "1"
        assert studio_config.mix_doctor_enabled()
    finally:
        env.pop("STUDIO_MIX_DOCTOR_ENABLED", None)


def test_the_upload_cap_stays_under_the_request_ceiling(application, env):
    """A cap above MAX_CONTENT_LENGTH is a number this code prints and never
    enforces - Werkzeug refuses the body before routing. That exact bug shipped
    once as a 250 MB Remix Lab against a 25 MB ceiling."""
    assert studio_config.max_upload_bytes() < application.config["MAX_CONTENT_LENGTH"]

    env["STUDIO_MAX_UPLOAD_BYTES"] = str(5 * 1024 * 1024 * 1024)
    assert studio_config.max_upload_bytes() < application.config["MAX_CONTENT_LENGTH"]


def test_a_provider_name_alone_is_not_a_configured_provider(env):
    """Reporting it ready would move the failure from the settings screen to a
    job that dies somewhere else later."""
    env["STUDIO_PROCESSING_PROVIDER"] = "some-vendor"
    assert not studio_config.provider_configured()
    env["STUDIO_PROVIDER_BASE_URL"] = "https://example.invalid"
    assert not studio_config.provider_configured()
    env["STUDIO_PROVIDER_API_KEY"] = "not-a-real-key"
    assert studio_config.provider_configured()


def test_readiness_reports_each_component_separately(env):
    """One "Studio: on" would be the same lie the Audio Studio told. Storage,
    processing and the worker fail independently and are reported that way."""
    keys = {k for k, _ok, _h, _d in studio_config.readiness()}
    assert keys == {"analysis", "storage", "processing", "worker"}

    report = dict((k, ok) for k, ok, _h, _d in studio_config.readiness())
    assert report["analysis"] is True          # browser-side, needs no vendor
    assert report["processing"] is False       # no provider configured here
    assert report["worker"] is False           # one web service, no worker


def test_readiness_says_why_rather_than_just_no(env):
    for _key, ok, headline, detail in studio_config.readiness():
        assert headline and detail
        if not ok:
            assert len(detail) > 40, headline


# --- the promise to what already exists --------------------------------------

def test_the_rack_still_works(application):
    """Studio must not take the Rack away. It is in the sidebar, in the
    command palette, in command_center, and it is the target of the ?stems=
    handoff from the Audio Studio."""
    client, _user = _account(application)
    response = client.get("/rack")
    assert response.status_code == 200
    assert b"rackdsp.js" in response.data


def test_the_rack_keeps_its_stems_parameter(application):
    """A redirect that dropped the query string would break the Audio Studio's
    "Open the stems in the Rack" button, which is a shipped path."""
    client, _user = _account(application)
    response = client.get("/rack?stems=abc123")
    assert response.status_code == 200
    assert b"rackdsp.js" in response.data


def test_the_rack_is_still_in_the_navigation(application):
    client, _user = _account(application)
    body = client.get("/overview").get_data(as_text=True)
    assert 'href="/rack"' in body


def test_saved_rack_chains_are_untouched_by_the_studio_schema(application):
    """rack_library and rack_presets hold work people did. The Studio
    migration adds columns to audio_assets and creates its own tables; it must
    not so much as look at these."""
    import db as store

    _client, user = _account(application)
    with application.app_context():
        store.save_rack_preset(user["id"], {"eq": [1, 2, 3]})
        sstore.init_studio()
        assert store.get_rack_preset(user["id"]) == {"eq": [1, 2, 3]}

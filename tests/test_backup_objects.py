"""A backup that omits the files is not a backup of the files.

/backup walked UPLOADS_DIR only. With R2 configured, blob_store.save
returns "r2:<key>" and does NOT also write to disk - so that directory
holds no real uploads and the zip carried the database alone, while
Settings promised "accounts, members, fans, statements, and uploads".

This went from latent to live the moment R2 started working: /storage/diag
returned put/get/delete all true on 2026-09-12, which means masters,
artwork, EPK kits, stems and delivery zips now exist only in the bucket.

The paths come from the database rather than from a bucket listing,
because every stored object is referenced by a row and the database is
already in the archive. The sweep is generic - sqlite_master for tables,
every text column - because a hardcoded list of table-and-column pairs
stops covering a feature the day somebody stores a blob somewhere new.
That already happened once: the vault export learned to fetch r2: paths
and the backup never did.
"""
import io
import uuid
import zipfile

import pytest

import blob_inventory
import blob_store
import db as store
from app import create_app


@pytest.fixture
def owner(monkeypatch):
    app_obj = create_app()
    email = "backup-%s@example.net" % uuid.uuid4().hex[:10]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Owner", "email": email,
                                 "password": "backuppw12345"})
    monkeypatch.setenv("OWNER_EMAILS", email)
    client._app = app_obj
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
    return client


def _plant(client, key):
    """Record a bucket path the way a real upload would."""
    with client._app.app_context(), store.get_db() as db:
        db.execute("INSERT INTO documents (id, user_id, filename, path,"
                   " doc_type, created) VALUES (?,?,?,?,?,?)",
                   (uuid.uuid4().hex, client._uid, "master.wav",
                    blob_store.PREFIX + key, "audio", "2026-09-12"))


def test_the_sweep_finds_a_path_recorded_anywhere(owner):
    _plant(owner, "masters/king810/hungry-gods.wav")
    with owner._app.app_context(), store.get_db() as db:
        keys = blob_inventory.stored_keys(db)
    assert "masters/king810/hungry-gods.wav" in keys


def test_the_archive_carries_the_object_and_names_it(owner, monkeypatch):
    _plant(owner, "masters/one.wav")
    monkeypatch.setattr(blob_store, "configured", lambda: True)
    monkeypatch.setattr(blob_store, "fetch", lambda path: b"AUDIOBYTES")

    response = owner.get("/backup")
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.data))
    assert "streetbanker.db" in archive.namelist()
    assert "objects/masters/one.wav" in archive.namelist(), (
        "the file itself, not just a reference to it")
    assert archive.read("objects/masters/one.wav") == b"AUDIOBYTES"

    manifest = archive.read("OBJECTS.csv").decode()
    assert "masters/one.wav,10,yes" in manifest


def test_an_object_the_bucket_will_not_return_is_named_not_hidden(owner, monkeypatch):
    """The failure that must never be silent. A key recorded in the
    database that the bucket cannot serve is exactly what somebody needs
    to know BEFORE a restore, not during one."""
    _plant(owner, "masters/gone.wav")
    monkeypatch.setattr(blob_store, "configured", lambda: True)
    monkeypatch.setattr(blob_store, "fetch", lambda path: None)

    archive = zipfile.ZipFile(io.BytesIO(owner.get("/backup").data))
    assert "objects/masters/gone.wav" not in archive.namelist()
    assert "masters/gone.wav,,fetch failed" in archive.read("OBJECTS.csv").decode()


def test_an_object_past_the_size_budget_is_named_not_dropped(owner, monkeypatch):
    """A catalogue of masters runs to gigabytes, so there is a ceiling -
    and anything past it has to be NAMED. An archive that silently drops
    the biggest file is how somebody finds out during a restore.

    The first version of this test did not test the budget at all: the
    ceiling lived inside create_app where nothing could reach it, and the
    test asserted the ordinary path while its own comment deferred to a
    skip case that was never exercised. The ceiling moved to module scope
    so this can lower it rather than allocating two gigabytes.
    """
    import app as appmod

    _plant(owner, "masters/huge.wav")
    monkeypatch.setattr(blob_store, "configured", lambda: True)
    monkeypatch.setattr(blob_store, "fetch", lambda path: b"x" * 64)
    monkeypatch.setattr(appmod, "BACKUP_BLOB_BUDGET", 16)

    archive = zipfile.ZipFile(io.BytesIO(owner.get("/backup").data))
    assert "objects/masters/huge.wav" not in archive.namelist()
    manifest = archive.read("OBJECTS.csv").decode()
    assert "masters/huge.wav,64,skipped - archive size limit" in manifest


def test_the_manifest_exists_even_with_no_objects_at_all(owner, monkeypatch):
    """So the archive always states what it believes exists, rather than
    only what it managed to include."""
    monkeypatch.setattr(blob_store, "configured", lambda: False)
    archive = zipfile.ZipFile(io.BytesIO(owner.get("/backup").data))
    manifest = archive.read("OBJECTS.csv").decode()
    assert "object storage is not configured" in manifest

"""The vault stores to the object store when it is configured, and to the
disk when it is not — and neither shape breaks the other.

The deployment this runs on has no R2 credentials, so every test here
that needs the bucket fakes it. That is deliberate: the useful thing to
prove is not that Cloudflare works, it is that the *fallback* is real and
that a database holding both path shapes at once still resolves both.
"""
import io
import os
import tempfile

import pytest

import blob_store


@pytest.fixture()
def uploads():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture()
def no_r2(monkeypatch):
    for name in ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID",
                 "R2_SECRET_ACCESS_KEY", "R2_PUBLIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def fake_r2(monkeypatch):
    """Credentials shaped like the real thing, pointing nowhere."""
    monkeypatch.setenv("R2_ACCOUNT_ID", "acct123")
    monkeypatch.setenv("R2_BUCKET", "street-banker")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "AKIAEXAMPLE")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "s3cr3t")
    monkeypatch.delenv("R2_PUBLIC_BASE_URL", raising=False)


# --- unconfigured: nothing changes -----------------------------------------

def test_without_credentials_it_is_not_configured(no_r2):
    assert blob_store.configured() is False


def test_without_credentials_uploads_land_on_disk(no_r2, uploads):
    path = blob_store.save("vault_1_9.mp3", b"audio-bytes", uploads_dir=uploads)
    assert path == "/uploads/vault_1_9.mp3"
    assert os.path.exists(os.path.join(uploads, "vault_1_9.mp3"))
    with open(os.path.join(uploads, "vault_1_9.mp3"), "rb") as fh:
        assert fh.read() == b"audio-bytes"


def test_a_disk_path_resolves_to_itself(no_r2):
    assert blob_store.url_for("/uploads/vault_1_9.mp3") == "/uploads/vault_1_9.mp3"
    assert blob_store.is_remote("/uploads/vault_1_9.mp3") is False


def test_removing_a_disk_upload_unlinks_it(no_r2, uploads):
    path = blob_store.save("vault_1_9.mp3", b"x", uploads_dir=uploads)
    assert blob_store.remove(path, uploads_dir=uploads) is True
    assert not os.path.exists(os.path.join(uploads, "vault_1_9.mp3"))


# --- configured ------------------------------------------------------------

def test_with_credentials_it_is_configured(fake_r2):
    assert blob_store.configured() is True


def test_an_upload_that_reaches_the_bucket_is_recorded_as_r2(fake_r2, uploads, monkeypatch):
    monkeypatch.setattr(blob_store, "put", lambda *a, **k: True)
    path = blob_store.save("vault_1_9.mp3", b"x", uploads_dir=uploads)
    assert path == "r2:vault_1_9.mp3"
    assert blob_store.is_remote(path)
    assert blob_store.key_of(path) == "vault_1_9.mp3"
    # And it did NOT also write to the disk.
    assert not os.path.exists(os.path.join(uploads, "vault_1_9.mp3"))


def test_a_bucket_outage_falls_back_to_disk_rather_than_losing_the_file(
        fake_r2, uploads, monkeypatch):
    """The property that matters most: an upload is never dropped."""
    def explode(*a, **k):
        raise OSError("bucket unreachable")
    monkeypatch.setattr(blob_store, "put", explode)

    path = blob_store.save("vault_1_9.mp3", b"precious", uploads_dir=uploads)
    assert path == "/uploads/vault_1_9.mp3"
    with open(os.path.join(uploads, "vault_1_9.mp3"), "rb") as fh:
        assert fh.read() == b"precious"


def test_a_remote_path_signs_to_a_url_that_expires(fake_r2):
    url = blob_store.url_for("r2:vault_1_9.mp3", ttl=120)
    assert url.startswith("https://")
    assert "acct123" in url and "street-banker" in url
    # Signed, scoped and time-limited — the bucket stays private.
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Expires=120" in url
    # The secret itself never appears in the URL.
    assert "s3cr3t" not in url


def test_a_public_base_url_is_used_instead_of_signing(fake_r2, monkeypatch):
    monkeypatch.setenv("R2_PUBLIC_BASE_URL", "https://cdn.example.com")
    url = blob_store.url_for("r2:vault_1_9.mp3")
    assert url == "https://cdn.example.com/vault_1_9.mp3"
    assert "X-Amz-Signature" not in url


# --- the mixed database, which is the whole point --------------------------

def test_both_path_shapes_coexist(fake_r2):
    """No migration is needed to deploy: old rows keep resolving."""
    legacy = "/uploads/vault_1_old.mp3"
    modern = "r2:vault_1_new.mp3"
    assert blob_store.url_for(legacy) == legacy
    assert blob_store.url_for(modern).startswith("https://")


# --- failure modes must not raise ------------------------------------------

@pytest.mark.parametrize("path", ["/uploads/x.mp3", "r2:x.mp3", "", None])
def test_url_for_never_raises(no_r2, path):
    """A page rendering a stored path must not 500 because credentials
    were rotated away after the object was written."""
    blob_store.url_for(path)


@pytest.mark.parametrize("path", ["/uploads/x.mp3", "r2:x.mp3", "", None])
def test_fetch_never_raises_and_returns_none_when_it_cannot(no_r2, path):
    assert blob_store.fetch(path) is None


def test_fetch_on_a_configured_but_unreachable_bucket_returns_none(fake_r2):
    """acct123 does not exist. This must be a None, not an exception —
    one unreachable object cannot be allowed to kill a batch download."""
    assert blob_store.fetch("r2:x.mp3") is None

"""The bucket check has to prove a download, not a configuration.

release_ready's owner desk reported "Storage (R2): connected" from four
environment variables being non-empty. A run then sat at "Making previews"
for forty-five minutes and failed, because a provider that is handed a
presigned link it cannot fetch never reports a result at all. These lock
the check that tells those two states apart, and the wording it gives back.
"""
import urllib.error
import urllib.request

import pytest

import blob_store
import release_ready


@pytest.fixture
def creds(monkeypatch):
    for name, value in (("R2_ACCOUNT_ID", "a" * 32), ("R2_BUCKET", "holer-test"),
                        ("R2_ACCESS_KEY_ID", "b" * 32),
                        ("R2_SECRET_ACCESS_KEY", "c" * 64)):
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(blob_store.sandbox, "active", lambda: False)


def _http_error(code, body=b""):
    return urllib.error.HTTPError("https://x/", code, "no", {},
                                  __import__("io").BytesIO(body))


def _reads(monkeypatch, answer):
    """answer(url) -> bytes, or raises. Stands in for the outside caller."""
    seen = []

    class Opener:
        def open(self, req, timeout=None):
            seen.append(req.full_url)
            # An outside caller carries no credentials. If we ever signed
            # the fetch with a header the test URL would pass while RoEx's
            # fetch failed, which is the whole bug this guards.
            assert "Authorization" not in req.headers
            assert not any(k.lower() == "authorization" for k in req.headers)
            return answer(req.full_url)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a: Opener())
    return seen


class _Body:
    def __init__(self, data):
        self.data = data

    def read(self, n=None):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_a_configured_bucket_is_not_a_working_one(creds, monkeypatch):
    """The point of the whole check: put and delete succeed, the outside
    read is refused, and the verdict says RoEx gets that same refusal."""
    monkeypatch.setattr(blob_store, "put", lambda *a, **k: True)
    monkeypatch.setattr(blob_store, "delete", lambda k: True)
    _reads(monkeypatch, lambda url: (_ for _ in ()).throw(
        _http_error(403, b"<Error><Code>SignatureDoesNotMatch</Code></Error>")))

    out = blob_store.round_trip()
    assert out["ok"] is False
    assert "cannot download the track" in out["verdict"]
    assert all(r["status"] == 403 for r in out["reads"])
    assert all(r["code"] == "SignatureDoesNotMatch" for r in out["reads"])
    assert out["cleaned_up"] is True


def test_a_working_bucket_reports_every_lifetime(creds, monkeypatch):
    stored = {}
    monkeypatch.setattr(blob_store, "put",
                        lambda k, d, c=None: stored.setdefault(k, d) or True)
    monkeypatch.setattr(blob_store, "delete", lambda k: True)
    seen = _reads(monkeypatch, lambda url: _Body(b"round trip"))

    out = blob_store.round_trip()
    assert out["ok"] is True
    assert [r["ttl"] for r in out["reads"]] == [300, blob_store.DEFAULT_TTL]
    assert all(r["bytes_match"] for r in out["reads"])
    # Every lifetime we hand out is actually exercised, separately.
    assert len(seen) == 2 and seen[0] != seen[1]


def test_the_seven_day_link_is_the_one_roex_gets(creds, monkeypatch):
    """R2's documented maximum is 604800 seconds and that is exactly what
    presigned_get defaults to. A bound Cloudflare checked exclusively
    would refuse every real link while a short test link passed, so the
    check has to name the lifetime rather than report a flat failure."""
    monkeypatch.setattr(blob_store, "put", lambda *a, **k: True)
    monkeypatch.setattr(blob_store, "delete", lambda k: True)

    def answer(url):
        if "X-Amz-Expires=604800" in url:
            raise _http_error(400, b"<Error><Code>AuthorizationQueryParametersError"
                                   b"</Code></Error>")
        return _Body(b"round trip")

    _reads(monkeypatch, answer)
    out = blob_store.round_trip(ttls=(300, release_ready.SOURCE_URL_TTL_TASK))
    assert out["ok"] is False
    assert "604800-second link RoEx is given" in out["verdict"]
    assert "lifetime is the problem, not the credentials" in out["verdict"]
    # The desk must ask for that lifetime, not blob_store's own hour-long
    # default, or the check passes on a link nobody is ever handed.
    assert release_ready.SOURCE_URL_TTL_TASK == 604800
    assert blob_store.DEFAULT_TTL != release_ready.SOURCE_URL_TTL_TASK


def test_a_refused_write_names_the_permission_to_fix(creds, monkeypatch):
    monkeypatch.setattr(blob_store, "put", lambda *a, **k: (_ for _ in ()).throw(
        _http_error(403, b"<Error><Code>AccessDenied</Code></Error>")))
    out = blob_store.round_trip()
    assert out["ok"] is False and out["step"] == "put"
    assert "Object Read & Write" in out["verdict"]
    assert out["code"] == "AccessDenied"
    assert out["reads"] == []


def test_a_missing_bucket_says_so(creds, monkeypatch):
    monkeypatch.setattr(blob_store, "put", lambda *a, **k: (_ for _ in ()).throw(
        _http_error(404, b"<Error><Code>NoSuchBucket</Code></Error>")))
    out = blob_store.round_trip()
    assert "does not exist on this account" in out["verdict"]


def test_writes_and_reads_hitting_different_buckets_is_named(creds, monkeypatch):
    monkeypatch.setattr(blob_store, "put", lambda *a, **k: True)
    monkeypatch.setattr(blob_store, "delete", lambda k: True)
    _reads(monkeypatch, lambda url: (_ for _ in ()).throw(
        _http_error(404, b"<Error><Code>NoSuchKey</Code></Error>")))
    out = blob_store.round_trip()
    assert "not hitting the same bucket" in out["verdict"]


def test_the_test_object_is_always_cleaned_up(creds, monkeypatch):
    """It writes into the production bucket, so it must not leave litter
    there even when the read half fails."""
    gone = []
    monkeypatch.setattr(blob_store, "put", lambda *a, **k: True)
    monkeypatch.setattr(blob_store, "delete", lambda k: gone.append(k) or True)
    _reads(monkeypatch, lambda url: (_ for _ in ()).throw(_http_error(403)))

    out = blob_store.round_trip()
    assert gone == [out["key"]]
    assert out["key"].startswith("diagnostics/round-trip-")


def test_an_unset_bucket_does_not_pretend_to_test_anything(monkeypatch):
    for name in ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID",
                 "R2_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(name, raising=False)
    out = blob_store.round_trip()
    assert out["ok"] is False and out["step"] == "configured"


def test_no_secret_reaches_the_report(creds, monkeypatch):
    monkeypatch.setattr(blob_store, "put", lambda *a, **k: True)
    monkeypatch.setattr(blob_store, "delete", lambda k: True)
    _reads(monkeypatch, lambda url: _Body(b"round trip"))
    printed = repr(blob_store.round_trip())
    assert "c" * 64 not in printed
    assert "b" * 32 not in printed

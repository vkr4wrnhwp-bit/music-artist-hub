"""A scheduler that is turned away must be told so, not redirected.

The first nightly run on Render read as a success: curl -f does not treat
a 302 as failure, the app bounced the anonymous POST to /login, Render
printed "Redirecting..." and marked the run green. A backup job that
reports success while backing nothing up is worse than no job.

/backup/run answers a POST with no valid token with a 403 and a reason -
whether the server has no BACKUP_TOKEN at all, or the one presented did
not match. Everything else that is not signed in still goes to /login.
"""
import pytest

from app import create_app


@pytest.fixture
def anon():
    return create_app().test_client()


def test_no_token_configured_is_a_403_with_that_reason(anon, monkeypatch):
    monkeypatch.delenv("BACKUP_TOKEN", raising=False)
    r = anon.post("/backup/run")
    assert r.status_code == 403, "not a redirect a scheduler would read as success"
    assert r.get_json()["ok"] is False
    assert "not configured" in r.get_json()["error"]


def test_a_wrong_token_is_a_403_saying_it_did_not_match(anon, monkeypatch):
    monkeypatch.setenv("BACKUP_TOKEN", "right-token-xyz")
    r = anon.post("/backup/run", headers={"X-Backup-Token": "wrong"})
    assert r.status_code == 403
    assert "did not match" in r.get_json()["error"]


def test_a_get_or_any_other_page_still_goes_to_login(anon, monkeypatch):
    monkeypatch.delenv("BACKUP_TOKEN", raising=False)
    assert anon.get("/backup/run").status_code in (302, 405)
    r = anon.get("/settings")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_the_right_token_gets_past_the_wall(anon, monkeypatch):
    """Past the wall - the route itself then reports there is no bucket,
    which is a 503, not a 403 and not /login."""
    monkeypatch.setenv("BACKUP_TOKEN", "right-token-xyz")
    for k in ("BACKUP_S3_ENDPOINT", "BACKUP_S3_BUCKET", "BACKUP_S3_KEY", "BACKUP_S3_SECRET"):
        monkeypatch.delenv(k, raising=False)
    r = anon.post("/backup/run", headers={"X-Backup-Token": "right-token-xyz"})
    assert r.status_code == 503
    assert "No off-box target" in r.get_json()["error"]

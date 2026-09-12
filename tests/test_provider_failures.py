"""An error rate is a number. The reason is what the operator needs.

The usage table on the data-sources page read "soundcharts 57.1%" for a
fortnight, and nothing on the page said 57% of WHAT. The key was fine -
Test connection answered - so the failures were somewhere in the calls
themselves: a rate limit, a lapsed entitlement on one endpoint, a shape
the adapter could not read. The detail column has held that answer
since the runs table was created. It was recorded and never shown.

The rule: a failure is reported as the adapter raised it, grouped so the
same failure forty times is one line with a count, and dated so an old
one does not read as current.
"""
import uuid

import pytest

import app as appmod
import db as store
import signal_store as sstore

PASSWORD = "sig-fail-pw-12345"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _owner(flask_app):
    email = "sig-fail-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": "Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    user = store.get_user_by_email(email)
    sstore.upsert_member(sstore.default_org()["id"], email, "Owner", "owner", user_id=user["id"])
    return client


def _clear(provider):
    with store.get_db() as db:
        db.execute("DELETE FROM signal_provider_runs WHERE provider = ?", (provider,))


def test_the_same_failure_many_times_is_one_line_with_a_count(flask_app):
    with flask_app.app_context():
        _clear("sc-test")
        for _ in range(3):
            sstore.record_provider_run("sc-test", "metrics", False, 120, 0,
                                       "ProviderError: Soundcharts 429: Too Many Requests")
        sstore.record_provider_run("sc-test", "releases", False, 90, 0,
                                   "ProviderError: Soundcharts 403: plan does not include releases")
        sstore.record_provider_run("sc-test", "metrics", True, 80, 0)
        rows = [r for r in sstore.provider_failures() if r["provider"] == "sc-test"]
    by_detail = {r["detail"]: r for r in rows}
    assert by_detail["ProviderError: Soundcharts 429: Too Many Requests"]["n"] == 3
    assert by_detail["ProviderError: Soundcharts 403: plan does not include releases"]["n"] == 1
    assert len(rows) == 2, "the successful call is not a failure"


def test_the_page_shows_the_reason_beside_the_rate(flask_app):
    client = _owner(flask_app)
    with flask_app.app_context():
        _clear("sc-page")
        sstore.record_provider_run("sc-page", "metrics", False, 100, 0,
                                   "ProviderError: Soundcharts 429: Too Many Requests")
    body = client.get("/signal/admin/data-sources").get_data(as_text=True)
    assert 'data-testid="provider-failures"' in body
    assert "Soundcharts 429: Too Many Requests" in body
    assert "Streaming &amp; audience metrics" in body, "the call is named, not its internal key"


def test_no_failures_means_no_table_not_an_empty_one(flask_app):
    client = _owner(flask_app)
    with flask_app.app_context(), store.get_db() as db:
        db.execute("DELETE FROM signal_provider_runs WHERE ok = 0")
    body = client.get("/signal/admin/data-sources").get_data(as_text=True)
    assert 'data-testid="provider-failures"' not in body

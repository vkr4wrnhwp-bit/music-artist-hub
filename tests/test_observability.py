"""Sentry starts only when asked, sends nothing personal, and the
readiness page tells the truth about whether it is on.

The SDK is not a test dependency: a fake sentry_sdk is planted in
sys.modules so the tests run on a checkout without it installed, and so a
call to init() is something the test can see. No network anywhere.
"""
import sys
import types

import pytest

import observability
import readiness


@pytest.fixture
def fake_sdk(monkeypatch):
    """A stand-in sentry_sdk that records init() calls."""
    calls = []
    sdk = types.ModuleType("sentry_sdk")
    sdk.init = lambda **kwargs: calls.append(kwargs)
    integrations = types.ModuleType("sentry_sdk.integrations")
    flask_mod = types.ModuleType("sentry_sdk.integrations.flask")

    class FlaskIntegration:
        pass

    flask_mod.FlaskIntegration = FlaskIntegration
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations", integrations)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.flask", flask_mod)
    return calls


class _App:
    def __init__(self):
        self.config = {}


def test_nothing_starts_without_a_dsn(monkeypatch, fake_sdk):
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    def explode(**_kwargs):
        raise AssertionError("sentry_sdk.init must not be called without a DSN")

    sys.modules["sentry_sdk"].init = explode
    app = _App()
    assert observability.init(app) is False
    assert observability.configured() is False
    assert "SENTRY_ENABLED" not in app.config


def test_a_dsn_starts_errors_only_with_no_pii(monkeypatch, fake_sdk):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@o1.ingest.example/1")
    monkeypatch.setenv("RENDER_SERVICE_NAME", "street-banker")
    monkeypatch.setenv("RENDER_GIT_COMMIT", "0d1a0496")
    app = _App()
    assert observability.init(app) is True
    assert len(fake_sdk) == 1
    kwargs = fake_sdk[0]
    assert kwargs["send_default_pii"] is False
    assert kwargs["traces_sample_rate"] == 0
    assert kwargs["environment"] == "street-banker"
    assert kwargs["release"] == "0d1a0496"
    assert kwargs["before_send"] is observability.before_send
    assert type(kwargs["integrations"][0]).__name__ == "FlaskIntegration"
    assert app.config["SENTRY_ENABLED"] is True


def test_environment_falls_back_to_sb_env_then_local(monkeypatch):
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.setenv("SB_ENV", "staging")
    assert observability.environment() == "staging"
    monkeypatch.delenv("SB_ENV")
    assert observability.environment() == "local"
    assert observability.release() is None


def test_missing_sdk_is_not_an_error(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@o1.ingest.example/1")
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)   # import raises
    assert observability.init(_App()) is False


def test_before_send_strips_cookies_auth_and_token_keys():
    event = {
        "request": {
            "url": "https://app.example/x",
            "cookies": {"session": "abc"},
            "headers": {"Authorization": "Bearer xyz", "Cookie": "session=abc",
                        "User-Agent": "test"},
            "query_string": "api_key=123",
            "data": {"password": "hunter2", "name": "fine"},
        },
        "extra": {"stripe_secret_key": "sk_live", "SENTRY_DSN": "https://x",
                  "nested": {"access_token": "t", "list": [{"token": "t2"}]}},
    }
    out = observability.before_send(event, {})
    req = out["request"]
    assert "cookies" not in req
    assert req["headers"]["Authorization"] == observability.SCRUBBED
    assert req["headers"]["Cookie"] == observability.SCRUBBED
    assert req["headers"]["User-Agent"] == "test"
    assert req["data"]["password"] == observability.SCRUBBED
    assert req["data"]["name"] == "fine"
    assert out["extra"]["stripe_secret_key"] == observability.SCRUBBED
    assert out["extra"]["SENTRY_DSN"] == observability.SCRUBBED
    assert out["extra"]["nested"]["access_token"] == observability.SCRUBBED
    assert out["extra"]["nested"]["list"][0]["token"] == observability.SCRUBBED
    # The original event is not mutated; the SDK gets a copy.
    assert event["request"]["cookies"] == {"session": "abc"}
    assert "abc" not in repr(out) and "xyz" not in repr(out)


def _row():
    for group in readiness.report():
        for row in group["rows"]:
            if row["name"] == "Error reporting (Sentry)":
                return row
    raise AssertionError("no Sentry row on the readiness page")


def test_readiness_row_reads_not_set_without_a_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    row = _row()
    assert row["on"] is False
    assert row["env"] == ["SENTRY_DSN"]


def test_readiness_row_reads_on_with_a_dsn(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "https://abc@o1.ingest.example/1")
    assert _row()["on"] is True


def test_create_app_calls_init_once(monkeypatch, fake_sdk):
    """The hook sits at the top of create_app(), so a DSN set in the
    environment is read on boot rather than by nothing."""
    from app import create_app     # app.py builds one app on import too
    monkeypatch.setenv("SENTRY_DSN", "https://abc@o1.ingest.example/1")
    before = len(fake_sdk)
    app = create_app()
    assert len(fake_sdk) == before + 1
    assert app.config.get("SENTRY_ENABLED") is True

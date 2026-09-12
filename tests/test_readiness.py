"""The readiness page tells the truth about the deployment, or it is worse
than nothing.

Three ways it could lie, and one way it could leak:

  - report a key as a working integration
  - report a flag as on when it is unset
  - go blank, or 500, because one provider module raised
  - print a credential

The first is handled in the copy and by linking the real probes; the rest
are held here.
"""
import uuid

import pytest

import readiness
from app import create_app

FLAG = "DUBBING_ENABLED"
KEY = "SONGSTATS_API_KEY"


@pytest.fixture
def app_obj():
    return create_app()


def _owner(app_obj, monkeypatch):
    email = "ready-%s@example.net" % uuid.uuid4().hex[:10]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Owner", "email": email,
                                 "password": "readypass1"})
    monkeypatch.setenv("OWNER_EMAILS", email)
    return client


def _row(name):
    for group in readiness.report():
        for row in group["rows"]:
            if row["name"] == name:
                return row
    raise AssertionError("no row named %r" % name)


def test_a_missing_key_reads_as_missing(monkeypatch):
    monkeypatch.delenv(KEY, raising=False)
    assert _row("Songstats")["on"] is False


def test_a_present_key_reads_as_configured(monkeypatch):
    monkeypatch.setenv(KEY, "sk-whatever")
    assert _row("Songstats")["on"] is True


def test_an_empty_value_is_not_a_key(monkeypatch):
    """Render keeps a variable with an empty value, and the old provider
    checks that used bool(os.environ.get(...)) would call that set."""
    monkeypatch.setenv(KEY, "   ")
    assert _row("Songstats")["on"] is False


def test_an_unset_flag_is_off_and_a_set_one_is_on(monkeypatch):
    label = FLAG.replace("_ENABLED", "").replace("_", " ").capitalize()
    monkeypatch.delenv(FLAG, raising=False)
    assert _row(label)["on"] is False
    monkeypatch.setenv(FLAG, "1")
    assert _row(label)["on"] is True


def test_a_provider_that_raises_is_reported_not_fatal(monkeypatch):
    """The page matters most when something is misconfigured, so a module
    throwing must read as "off" rather than taking the page down."""
    import blob_store

    def boom():
        raise RuntimeError("no bucket")

    monkeypatch.setattr(blob_store, "configured", boom)
    assert _row("Object storage (R2)")["on"] is False


def test_the_page_never_prints_a_value(app_obj, monkeypatch):
    """Names, never values. A page that renders a key puts it in a
    screenshot, a support thread and a browser cache."""
    secret = "sk-live-%s" % uuid.uuid4().hex
    monkeypatch.setenv(KEY, secret)
    monkeypatch.setenv("EVENTBRITE_TOKEN", secret)
    client = _owner(app_obj, monkeypatch)
    body = client.get("/admin/readiness").get_data(as_text=True)
    assert secret not in body
    assert KEY in body, "the NAME is the useful part"


def test_only_an_owner_reaches_it(app_obj, monkeypatch):
    stranger = app_obj.test_client()
    stranger.post("/signup", data={
        "name": "S", "password": "readypass1",
        "email": "not-owner-%s@example.net" % uuid.uuid4().hex[:8]})
    assert stranger.get("/admin/readiness").status_code == 404, (
        "the row labels alone name every integration worth probing")
    assert "/admin/readiness" not in stranger.get("/overview").get_data(as_text=True)

    owner = _owner(app_obj, monkeypatch)
    assert owner.get("/admin/readiness").status_code == 200
    assert "/admin/readiness" in owner.get("/overview").get_data(as_text=True)


def test_it_links_the_probes_that_actually_prove_something(app_obj, monkeypatch):
    """A green row is a presence check. The round trips are what settle
    it, so the page has to point at them."""
    client = _owner(app_obj, monkeypatch)
    body = client.get("/admin/readiness").get_data(as_text=True)
    for probe in ("/mail/diag", "/storage/diag", "/presave/diag",
                  "/admin/audio", "/rack/studio-split/diag"):
        assert probe in body, probe
    assert "not the same as an integration working" in body


def test_every_row_says_what_it_switches_on():
    """A row an owner cannot act on is decoration. Flags are exempt: the
    lane names are the explanation."""
    for group in readiness.report():
        for row in group["rows"]:
            if row.get("flag"):
                continue
            assert row["unlocks"].strip(), "%s says nothing" % row["name"]
            assert row["env"], "%s names no variable" % row["name"]

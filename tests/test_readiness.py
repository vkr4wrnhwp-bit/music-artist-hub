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
    # Both halves: a Signal adapter is its flag AND its credentials. This
    # test used to set only the key and expect a green row, which is the
    # assumption that made four providers read as in service when Signal
    # was not calling them.
    monkeypatch.setenv(KEY, "sk-whatever")
    monkeypatch.setenv("SONGSTATS_ENABLED", "1")
    assert _row("Songstats")["on"] is True


def test_an_empty_value_is_not_a_key(monkeypatch):
    """Render keeps a variable with an empty value, and the old provider
    checks that used bool(os.environ.get(...)) would call that set."""
    monkeypatch.setenv("SONGSTATS_ENABLED", "1")     # the flag is not the gap
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


def test_a_setup_check_is_not_offered_as_proof():
    """The first draft of this page said /mail/diag "sends a real
    message" and /presave/diag "checks the OAuth round trip". Neither
    does: one asks Resend read-only about domain verification, the other
    reports which variables the process can see. A page built to stop a
    presence check reading as proof must not make that mistake itself.

    So the two are separated in the data, and the link text follows: only
    a row that really calls the vendor says "Prove it".
    """
    real, shape = [], []
    for group in readiness.report():
        for row in group["rows"]:
            if row.get("probe"):
                (real if row.get("roundtrip") else shape).append(row["name"])
    assert "Object storage (R2)" in real, "the R2 check is a genuine round trip"
    assert "Spotify" in shape, "/presave/diag reads variables, it does not sign in"
    assert "Stem splitting" in shape, "that one inspects the key, not the vendor"
    for group in readiness.report():
        for row in group["rows"]:
            if row.get("probe"):
                assert row["proof"].strip(), "%s links a probe and does not say what it does" % row["name"]


def test_the_page_marks_the_two_kinds_differently(app_obj, monkeypatch):
    client = _owner(app_obj, monkeypatch)
    body = client.get("/admin/readiness").get_data(as_text=True)
    assert "Prove it" in body and "Check the setup" in body
    assert "never tells you the vendor agreed" in body


def test_every_row_says_what_it_switches_on():
    """A row an owner cannot act on is decoration. Flags are exempt: the
    lane names are the explanation."""
    for group in readiness.report():
        for row in group["rows"]:
            if row.get("flag"):
                continue
            assert row["unlocks"].strip(), "%s says nothing" % row["name"]
            assert row["env"], "%s names no variable" % row["name"]


def test_every_variable_named_is_one_the_app_actually_reads():
    """The guard that was missing, and the bug that proved it necessary.

    The Soundcharts row named SOUNDCHARTS_ID and SOUNDCHARTS_TOKEN. The
    app reads neither - the real pair is SOUNDCHARTS_APP_ID and
    SOUNDCHARTS_API_KEY, or the OAuth pair. So the row read "Not set" on
    a deployment where Soundcharts was configured, and told the owner to
    set two variables nothing would ever look at. A readiness page that
    invents a name is worse than no page: it sends somebody to the
    dashboard to type something with no effect.

    A name is only counted if it appears as its own quoted string in a
    non-test module. SOUNDCHARTS_TOKEN passed a substring check because
    SOUNDCHARTS_TOKEN_URL exists, which is how the first sweep missed it.
    """
    import os

    # ONE dirname: readiness.py sits at the repo root, so two would walk
    # the directory ABOVE it - which on this machine holds every sibling
    # worktree, and turned a two-second test into a ten-minute one.
    repo = os.path.dirname(os.path.abspath(readiness.__file__))
    blob = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs
                   if d not in (".git", "tests", "__pycache__", "tools",
                                "node_modules", "static", "templates")]
        for name in files:
            if name.endswith(".py") and name != "readiness.py":
                try:
                    with open(os.path.join(root, name), encoding="utf-8",
                              errors="ignore") as fh:
                        blob.append(fh.read())
                except OSError:
                    pass
    source = chr(10).join(blob)

    unknown = []
    for group in readiness.report():
        for row in group["rows"]:
            for var in row["env"]:
                # The name has to appear as its own quoted string. A plain
                # substring search passes SOUNDCHARTS_TOKEN on the strength
                # of SOUNDCHARTS_TOKEN_URL, which is how the first sweep
                # for this missed it.
                quoted = ['"' + var + '"', "'" + var + "'"]
                if not any(q in source for q in quoted):
                    unknown.append("%s -> %s" % (row["name"], var))
    assert not unknown, (
        "the page names variables the app never reads: %s" % unknown)


def test_a_signal_provider_needs_its_flag_as_well_as_its_key(monkeypatch):
    """A key on its own does not put a provider into service.

    Every Signal adapter is gated on its own *_ENABLED flag too. The
    hand-written rows checked only the key, so a provider read
    "Configured" while Signal was not calling it at all.
    """
    monkeypatch.setenv("SONGSTATS_API_KEY", "sk-real-looking")
    monkeypatch.delenv("SONGSTATS_ENABLED", raising=False)
    assert _row("Songstats")["on"] is False, (
        "a key with no flag is not a provider in service")

    monkeypatch.setenv("SONGSTATS_ENABLED", "1")
    assert _row("Songstats")["on"] is True


def test_a_default_on_flag_is_not_reported_off_when_unset(monkeypatch):
    """Not every flag is off until set, and assuming so was wrong twice.

    audio_policy.FLAGS genuinely are: an unset flag is OFF there, so a
    deployment gains a surface deliberately. Live Lab and Studio are the
    reverse - both are ON unless a deployment sets the variable to 0,
    because both work and hiding them behind a variable nobody had been
    told about only meant the owner could not find his own rig.

    Reading them with audio_policy.flag() reported both as Off on a
    deployment where both were running, which would have sent somebody
    to the dashboard to switch on what was already on. Each is asked of
    the module that owns it now.
    """
    monkeypatch.delenv("LIVE_LAB_ENABLED", raising=False)
    monkeypatch.delenv("STUDIO_V1_ENABLED", raising=False)
    monkeypatch.delenv("STUDIO_ENABLED", raising=False)
    assert _row("Live Lab")["on"] is True, "unset means running for Live Lab"
    assert _row("Studio")["on"] is True, "and for Studio"

    monkeypatch.setenv("LIVE_LAB_ENABLED", "0")
    assert _row("Live Lab")["on"] is False, "an explicit 0 does switch it off"

    # And the audio lanes keep the opposite rule.
    monkeypatch.delenv("LYRIC_SHEET_ENABLED", raising=False)
    assert _row("Lyric sheet")["on"] is False, "unset means off for a lane"


def test_each_flag_row_agrees_with_the_module_that_owns_it():
    """The page must not hold a second opinion about a flag."""
    import live as live_mod
    import studio_config

    assert _row("Live Lab")["on"] is bool(live_mod.enabled())
    assert _row("Studio")["on"] is bool(studio_config.enabled())


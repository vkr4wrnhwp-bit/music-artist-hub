"""The five cheap ones from the Signal audit, and two things they exposed.

Asked for 2026-09-10 after an audit of the live Signal module: filter the
discovery boards by shape, tier, genre and listener ceiling; test an
adapter's connection from the admin page; keep a readable transcript
beside an audio brief.

Two of those turned out to be already built - the brief page has carried
its full script all along - and looking for them turned up two real
defects instead:

  - "Export CSV" ignored the board AND its filters, writing the whole
    universe every time. On Breaking Now it offered the breaking cohort
    and delivered every artist on file.
  - Writing a brief was gated on the speech flag, though it only reads
    the database and calls no vendor. A deployment with no speech
    provider could not read its own weekly brief at all.
"""
import os
import re
import uuid

import pytest

BOARDS = ("breaking", "early", "undervalued", "deal-ready")


@pytest.fixture(scope="module")
def application():
    os.environ["OWNER_EMAILS"] = "sigboard@example.net"
    import app as appmod
    return appmod.app


@pytest.fixture
def owner(application, monkeypatch):
    """A signed-in owner, a real adapter list, and a universe to filter.

    None of that can be assumed: another test in the suite swaps the
    provider registry for an empty one, which removes the very adapters
    these tests probe, and leaves a universe too small to narrow. Both
    are restored here rather than inherited.
    """
    import signal_ingest as ingest
    import signal_providers as providers

    for var in ("SOUNDCHARTS_ENABLED", "CHARTMETRIC_ENABLED",
                "MUSICBRAINZ_ENABLED", "MLC_ENABLED"):
        monkeypatch.delenv(var, raising=False)
    providers.reset_registry(providers.ProviderRegistry())
    with application.app_context():
        ingest.refresh_universe(force=True)

    c = application.test_client()
    email = "sigboard@example.net"
    c.post("/signup", data={"name": "Owner", "email": email,
                            "password": "board-pass-123"})
    c.post("/login", data={"email": email, "password": "board-pass-123"})
    return c


def _count_line(body):
    m = re.search(r'<p class="sg-h2">\s*([^<]+?)\s*</p>', body)
    return m.group(1) if m else ""


# --- one rail, every board --------------------------------------------------

@pytest.mark.parametrize("board", BOARDS)
def test_every_board_can_be_narrowed(owner, board):
    body = owner.get("/signal/%s" % board).get_data(as_text=True)
    assert "Growth shape" in body, "%s has no filter rail" % board
    assert "Distribution tier" in body
    assert "Listener ceiling" in body


def test_a_filter_says_how_much_it_is_hiding(owner):
    """A narrowed board that looks like the whole board is a lie of omission."""
    body = owner.get("/signal/breaking?max_listeners=50000").get_data(as_text=True)
    line = _count_line(body)
    assert " of " in line and "shown" in line, line


def test_an_unfiltered_board_does_not_pretend_to_be_filtered(owner):
    line = _count_line(owner.get("/signal/breaking").get_data(as_text=True))
    assert "shown" not in line and "artist" in line, line


def test_a_filter_that_matches_nothing_says_so(owner):
    """Different from a board nobody clears, and it must read differently."""
    body = owner.get("/signal/breaking?max_listeners=1").get_data(as_text=True)
    assert "matches that filter" in body
    assert "Nothing meets this board's bar" not in body


def test_the_choices_come_from_the_rows_the_board_holds(owner):
    """A facet built from filtered rows removes itself once chosen."""
    body = owner.get("/signal/breaking?max_listeners=50000").get_data(as_text=True)
    assert 'value="50000"' in body and "selected" in body


# --- the export writes what is on the screen --------------------------------

def test_the_export_used_to_send_the_whole_universe(owner):
    everything = owner.get("/signal/export/board.csv").get_data(as_text=True)
    breaking = owner.get("/signal/export/board.csv?board=breaking").get_data(as_text=True)
    assert len(breaking.strip().split("\n")) < len(everything.strip().split("\n")), (
        "the board's own bar was not applied to its export")


def test_the_export_carries_the_filter_too(owner):
    page = owner.get("/signal/breaking?max_listeners=50000").get_data(as_text=True)
    shown = int(_count_line(page).split(" of ")[0])
    csv = owner.get("/signal/export/board.csv?board=breaking&max_listeners=50000")
    rows = len(csv.get_data(as_text=True).strip().split("\n")) - 1
    assert rows == shown, "%d in the file, %d on the screen" % (rows, shown)


def test_the_export_link_names_the_board_it_is_on(owner):
    for board in BOARDS:
        body = owner.get("/signal/%s" % board).get_data(as_text=True)
        assert "board=%s" % board in body, board


# --- a connection test that connects ----------------------------------------

def test_the_state_column_no_longer_calls_credentials_a_connection(owner):
    body = owner.get("/signal/admin/data-sources").get_data(as_text=True)
    assert "credentials present" in body
    assert "Credentials present is not the same as the vendor answering" in body
    assert "Test connection" in body


def test_an_unconfigured_adapter_fails_its_probe(owner):
    answer = owner.post("/signal/admin/probe/soundcharts").get_json()
    assert answer["ok"] is False
    assert "SOUNDCHARTS_ENABLED" in answer["detail"], (
        "say which switch, not just that it failed")


def test_an_adapter_with_no_test_says_so_rather_than_passing(owner):
    """`ok` is None, not False: we did not ask is not we asked and it failed."""
    answer = owner.post("/signal/admin/probe/mock").get_json()
    assert answer["ok"] is None
    assert "No connection test" in answer["detail"]


def test_an_adapter_that_does_not_exist_is_a_404(owner):
    r = owner.post("/signal/admin/probe/not-a-provider")
    assert r.status_code == 404


def test_probe_is_separate_from_health_check():
    """health_check reads the environment; probe asks the vendor."""
    import signal_providers as sp
    for adapter in sp.registry().adapters:
        assert hasattr(adapter, "probe")
        assert adapter.probe is not adapter.health_check

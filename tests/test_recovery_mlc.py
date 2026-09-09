"""Recovery, asked of The MLC: every passport ISRC, one sweep, on request.

The sweep is bounded, kept whole, and honest about what it did not ask:
passports without an ISRC are listed as unable to be checked, never
matched by title. Every gap - no work linked, or a work only partly
claimed - is offered as a case; a fully claimed work is not.
"""
import io
import uuid

import pytest

import db as store
import recovery_mlc
import signal_providers as providers
from app import create_app
from tests.test_signal_mlc import Fake

PASSWORD = "recovery-pass-123"


def _artist(app_obj):
    email = "rmlc-%s@example.net" % uuid.uuid4().hex[:8]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Ava", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    client.post("/plan/switch", data={"plan": "pro"})      # Recovery is a Pro page
    return client, store.get_user_by_email(email)


def _track(client, user, title, **passport):
    client.post("/tracks/add", data={"title": title})
    track = [t for t in store.list_os_tracks(user["id"]) if t["title"] == title][0]
    if passport:
        p = track["passport"]
        p.update(passport)
        store.update_os_track_passport(user["id"], track["id"], p)
    return track


def _connect(monkeypatch, fake=None):
    monkeypatch.setenv("MLC_ENABLED", "1")
    monkeypatch.setenv("MLC_USERNAME", "api-user@example.net")
    monkeypatch.setenv("MLC_PASSWORD", "right")
    adapter = providers.MLCAdapter(transport=fake or Fake())
    monkeypatch.setattr(providers, "mlc_adapter", lambda: adapter)
    return adapter


def _catalogue(client, user):
    full = _track(client, user, "Night Drive", isrc="us-aiw-26-00123")
    bare = _track(client, user, "Static", isrc="USAIW2600777")
    gone = _track(client, user, "Ghost", isrc="USXXX9999999")
    _track(client, user, "Night Drive (Radio Edit)", isrc="USAIW2600123")   # a duplicate ISRC
    no_isrc = _track(client, user, "Untitled Demo", artist_name="Ava Kane")
    return full, bare, gone, no_isrc


def test_candidates_are_isrcs_deduped_and_the_rest_are_named(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    full, bare, gone, no_isrc = _catalogue(client, user)
    ready, missing = recovery_mlc.candidates(user["id"])
    assert sorted(r["isrc"] for r in ready) == ["USAIW2600123", "USAIW2600777", "USXXX9999999"]
    assert [m["track_id"] for m in missing] == [no_isrc["id"]]


def test_without_the_login_the_page_says_so_and_the_sweep_refuses(monkeypatch):
    for k in ("MLC_ENABLED", "MLC_USERNAME", "MLC_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(providers, "mlc_adapter", lambda: providers.MLCAdapter(
        transport=lambda *a: pytest.fail("must not call out")))
    app_obj = create_app()
    client, user = _artist(app_obj)
    _catalogue(client, user)
    page = client.get("/recovery").get_data(as_text=True)
    assert 'id="mlc"' in page and "Not connected" in page and "at The MLC</button>" not in page
    r = client.post("/recovery/mlc")
    assert "mlc=off" in r.headers["Location"]
    assert store.latest_recovery_mlc_sweep(user["id"]) is None
    assert "not connected on this service" in client.get("/recovery?mlc=off").get_data(as_text=True)


def test_a_sweep_sorts_the_catalogue_into_claimed_partial_and_gone(monkeypatch):
    fake = Fake()
    _connect(monkeypatch, fake)
    app_obj = create_app()
    client, user = _artist(app_obj)
    full, bare, gone, no_isrc = _catalogue(client, user)
    page = client.get("/recovery").get_data(as_text=True)
    assert "Check 3 ISRCs at The MLC" in page and "No check run yet" in page
    assert "carries no ISRC and cannot be checked" in page and "Untitled Demo" in page

    r = client.post("/recovery/mlc")
    assert r.status_code == 302 and r.headers["Location"].endswith("/recovery#mlc")
    sweep = store.latest_recovery_mlc_sweep(user["id"])
    assert sweep["summary"] == {"checked": 3, "matched": 1, "partial": 1, "unmatched": 1, "errors": 0, "skipped": 0}
    by_isrc = {row["isrc"]: row for row in sweep["rows"]}
    assert by_isrc["USAIW2600123"]["result"] == "match" and by_isrc["USAIW2600123"]["share_total"] == 100.0
    assert by_isrc["USAIW2600777"]["result"] == "match" and by_isrc["USAIW2600777"]["publishers"] == 0
    assert by_isrc["USXXX9999999"]["result"] == "none"
    asked = [c[3]["isrc"] for c in fake.calls if c[1].endswith("/search/recordings")]
    assert sorted(asked) == ["USAIW2600123", "USAIW2600777", "USXXX9999999"], "each ISRC once, nothing by title"

    page = client.get("/recovery").get_data(as_text=True)
    assert "1 fully claimed" in page and "1 partly claimed" in page and "1 no work linked" in page
    assert "100.0% claimed" in page and "0.0% claimed" in page and "no work linked" in page
    assert 'href="/tracks/%s#mlc"' % gone["id"] in page
    # A case is offered on each gap and on nothing else.
    assert page.count('name="category" value="mechanical"') == 2
    assert 'value="Unmatched at The MLC: Ghost (USXXX9999999)"' in page
    assert 'value="Partly claimed at The MLC: Static (USAIW2600777)"' in page
    assert "Night Drive (USAIW2600123)" not in page


def test_a_case_opened_from_a_gap_is_shown_as_open_next_time(monkeypatch):
    _connect(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    _catalogue(client, user)
    client.post("/recovery/mlc")
    client.post("/royalty-recovery/cases/from-finding", data={
        "title": "Unmatched at The MLC: Ghost (USXXX9999999)", "category": "mechanical",
        "amount": "0", "notes": "The MLC has no work linked to ISRC USXXX9999999."})
    cases = store.list_recovery_cases(user["id"])
    assert len(cases) == 1 and cases[0]["category"] == "mechanical"
    page = client.get("/recovery").get_data(as_text=True)
    assert page.count("Case open →") == 1 and page.count('name="category" value="mechanical"') == 1


def test_errors_are_counted_and_shown_and_an_empty_catalogue_is_a_note(monkeypatch):
    fake = Fake()
    _connect(monkeypatch, fake)
    app_obj = create_app()
    client, user = _artist(app_obj)
    r = client.post("/recovery/mlc")
    assert "mlc=none" in r.headers["Location"]
    assert "nothing to ask about" in client.get("/recovery?mlc=none").get_data(as_text=True)
    _track(client, user, "Night Drive", isrc="USAIW2600123")
    fake.password = "rotated"
    client.post("/recovery/mlc")
    sweep = store.latest_recovery_mlc_sweep(user["id"])
    assert sweep["summary"]["errors"] == 1 and sweep["rows"][0]["result"] == "error"
    page = client.get("/recovery").get_data(as_text=True)
    assert "1 error" in page and "Wrong email or password" in page
    assert 'name="category" value="mechanical"' not in page, "an error is not a gap"


def test_the_sweep_is_bounded_and_says_what_it_skipped(monkeypatch):
    _connect(monkeypatch)
    monkeypatch.setattr(recovery_mlc, "PER_SWEEP", 2)
    app_obj = create_app()
    client, user = _artist(app_obj)
    _catalogue(client, user)
    client.post("/recovery/mlc")
    sweep = store.latest_recovery_mlc_sweep(user["id"])
    assert sweep["summary"]["checked"] == 2 and sweep["summary"]["skipped"] == 1
    assert "1 more not checked this run" in client.get("/recovery").get_data(as_text=True)


# --- what a gap is worth ----------------------------------------------------
#
# A case opened at 0 tells the artist nothing and keeps the whole MLC sweep
# out of the pipeline total. The figure below is never guessed: it is money
# the title has already earned in the owner's own statements, and for a
# partly claimed work the unclaimed fraction of that. It is not money The
# MLC owes, and every note says which rows it came from.


class _Registry(object):
    """The MLC, answering exactly the shares a case figure is built on."""

    def __init__(self, works=None):
        self.works = works or {}

    def configured(self):
        return True

    def lookup(self, isrc=None, title=None, artist=None):
        return {"works": self.works.get(isrc, [])}


def _registry(monkeypatch, works=None):
    monkeypatch.setattr(providers, "mlc_adapter", lambda: _Registry(works))


def _statements(client, csv):
    client.post("/statements",
                data={"statement": (io.BytesIO(csv.encode()), "s.csv")},
                content_type="multipart/form-data")


def _row(user, isrc):
    rows = recovery_mlc.state(user["id"])["latest"]["rows"]
    return [r for r in rows if r["isrc"] == isrc][0]


def test_an_unmatched_isrc_carries_what_that_title_already_earned(monkeypatch):
    """No work at The MLC means the whole mechanical share of this title is
    at risk, so the case is worth what the title has earned in the lanes a
    mechanical gap is about - here The MLC's own line plus a publishing
    admin's, and not the streaming line beside them."""
    _registry(monkeypatch)                       # nothing is linked
    app_obj = create_app()
    client, user = _artist(app_obj)
    _track(client, user, "Ghost", isrc="USXXX9999999")
    _statements(client, "title,source,amount,period,territory\n"
                        "Ghost,The MLC,12.5,2026-02,\n"
                        "Ghost,Songtrust,7.5,2026-02,\n"
                        "Ghost,Spotify,500,2026-02,US\n")
    client.post("/recovery/mlc")

    row = _row(user, "USXXX9999999")
    assert row["case_amount"] == 20.0, "12.50 mechanical + 7.50 publishing, not the 500 streaming"
    assert row["case_figure"] == "$20.00"
    assert row["case_caption"] == "already earned, work unregistered"
    assert ("$20.00 has already been earned by this title in your own statements "
            "(its mechanical and publishing rows), and the work behind it is "
            "unregistered - so the whole mechanical share of that money is at risk. "
            "This is not money The MLC owes.") in row["case_note"]

    page = client.get("/recovery").get_data(as_text=True)
    assert "$20.00" in page and "already earned, work unregistered" in page
    assert 'name="amount" value="20.0"' in page

    client.post("/royalty-recovery/cases/from-finding",
                data={"title": row["case_title"], "category": "mechanical",
                      "amount": row["case_amount"], "notes": row["case_note"]})
    case = store.list_recovery_cases(user["id"])[0]
    assert case["estimated_amount"] == 20.0 and "$20.00" in case["notes"]
    # And the pipeline counts it, which it could never do at 0.
    assert "$20.00" in client.get("/royalty-recovery/cases").get_data(as_text=True)


def test_a_partly_claimed_work_is_the_unclaimed_share_of_what_it_earned(monkeypatch):
    """60% claimed, 40% unclaimed: the case is 40% of the title's own
    earnings, and the note says that is a share of money already earned,
    not a promise of what will be paid."""
    _registry(monkeypatch, {"USAIW2600777": [
        {"song_code": "BA9000", "iswc": "", "share_total": 60.0,
         "writers": [{"name": "Ava"}], "publishers": [{"name": "AIW"}]}]})
    app_obj = create_app()
    client, user = _artist(app_obj)
    _track(client, user, "Static", isrc="USAIW2600777")
    _statements(client, "title,source,amount,period,territory\n"
                        "Static,The MLC,45,2026-02,\n")
    client.post("/recovery/mlc")

    row = _row(user, "USAIW2600777")
    assert row["case_amount"] == 18.0                       # 45.00 x 40%
    assert row["case_figure"] == "$18.00"
    assert row["case_caption"] == "40% unclaimed share of $45.00 earned"
    assert row["case_note"] == (
        "The MLC links ISRC USAIW2600777 to song code BA9000 with 60% of the work "
        "claimed, so 40% is unclaimed. $18.00 is 40% of the $45.00 this title has "
        "already earned in your own statements (its mechanical and publishing rows) "
        "- a share of what it has earned, not a promise of what will be paid. "
        "Claim the missing share.")

    page = client.get("/recovery").get_data(as_text=True)
    assert "$18.00" in page and "40% unclaimed share of $45.00 earned" in page
    assert 'name="amount" value="18.0"' in page


def test_a_title_with_no_mechanical_row_names_what_its_figure_includes(monkeypatch):
    """When the statements never name a mechanical or publishing source
    there is no lane figure to use, so the case falls back to the title's
    whole total - and says so, rather than passing a streaming total off
    as a mechanical one."""
    _registry(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    _track(client, user, "Ghost", isrc="USXXX9999999")
    _statements(client, "title,source,amount,period,territory\n"
                        "Ghost,Spotify,500,2026-02,US\n")
    client.post("/recovery/mlc")

    row = _row(user, "USXXX9999999")
    assert row["case_amount"] == 500.0
    assert ("$500.00 has already been earned by this title in your own statements "
            "(every stream on it, since no row names a mechanical or publishing "
            "source)") in row["case_note"]


def test_with_no_statement_rows_the_case_still_opens_at_zero_and_says_why(monkeypatch):
    """A catalogue with no statements has nothing to measure, and an
    invented figure would be worse than none. Both kinds of gap open at 0
    with the same sentence."""
    _registry(monkeypatch, {"USAIW2600777": [
        {"song_code": "BA9000", "iswc": "", "share_total": 60.0,
         "writers": [], "publishers": []}]})
    app_obj = create_app()
    client, user = _artist(app_obj)
    _track(client, user, "Ghost", isrc="USXXX9999999")
    _track(client, user, "Static", isrc="USAIW2600777")
    client.post("/recovery/mlc")

    for isrc in ("USXXX9999999", "USAIW2600777"):
        row = _row(user, isrc)
        assert row["case_amount"] == 0.0 and row["case_figure"] is None
        assert row["case_caption"] == "no statement rows for this title yet"
        assert "No statement rows for this title yet." in row["case_note"]
    # The partial still states the arithmetic it could not do.
    assert "so 40% is unclaimed." in _row(user, "USAIW2600777")["case_note"]

    page = client.get("/recovery").get_data(as_text=True)
    assert page.count("no statement rows for this title yet") == 2
    assert page.count('name="amount" value="0.0"') == 2
    client.post("/royalty-recovery/cases/from-finding",
                data={"title": _row(user, "USXXX9999999")["case_title"],
                      "category": "mechanical", "amount": "0.0",
                      "notes": _row(user, "USXXX9999999")["case_note"]})
    assert store.list_recovery_cases(user["id"])[0]["estimated_amount"] == 0.0


def test_the_sweep_hides_a_second_case_but_the_route_does_not_dedupe(monkeypatch):
    """Recorded, not invented. The only guard against opening the same gap
    twice is the sweep partial, which swaps the button for "Case open" once
    a case with that exact title exists. `/royalty-recovery/cases/from-finding`
    has no dedupe of its own, so a repeated POST does make a second case and
    the pipeline does count both. Adding a route-level guard was out of scope
    here; this test says what today's behaviour is instead of implying a
    protection that is not there."""
    _registry(monkeypatch)
    app_obj = create_app()
    client, user = _artist(app_obj)
    _track(client, user, "Ghost", isrc="USXXX9999999")
    _statements(client, "title,source,amount,period,territory\n"
                        "Ghost,The MLC,20,2026-02,\n")
    client.post("/recovery/mlc")
    row = _row(user, "USXXX9999999")
    post = {"title": row["case_title"], "category": "mechanical",
            "amount": row["case_amount"], "notes": row["case_note"]}

    client.post("/royalty-recovery/cases/from-finding", data=post)
    page = client.get("/recovery").get_data(as_text=True)
    assert "Case open" in page
    assert 'name="title" value="%s"' % row["case_title"] not in page

    client.post("/royalty-recovery/cases/from-finding", data=post)
    assert len(store.list_recovery_cases(user["id"])) == 2
    assert "$40.00" in client.get("/royalty-recovery/cases").get_data(as_text=True)

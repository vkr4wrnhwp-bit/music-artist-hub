# -*- coding: utf-8 -*-
"""royalty_lag reaches an artist.

The module answered "late, or just how long it takes?" correctly from the
day it was written, was covered by tests/test_royalty_lag.py, and was
imported by nothing. So the arithmetic was proved and the product still
could not say the one thing both distributor conversations and the
outside audit named as the client's pain.

That is the lesson this file exists to lock: a green unit-test file
proves nothing about whether the thing is connected. Almost every test
here goes through a route and reads the page an artist would read.

The honesty rules, each with a test that fails if it breaks:

  * every verdict rests on a published industry figure, and the page
    says so in the reader's words. Nothing here is measured from this
    account, because nothing in this app records the day a distributor
    reported a period. The day the ARTIST uploaded a CSV is a fact about
    the artist, so it is never read as a platform's pace.
  * a source with no published figure keeps a visible row saying it has
    no reading, rather than being smoothed into a pass
  * no number the data did not produce, and no date invented for a
    period the distributor did not date
"""
import datetime
import io
import uuid

import pytest

import app as appmod
import db as store
import royalty_lag
import statements_engine as se

PW = "reporting-lag-pass-1"
TODAY = datetime.date.today()

HEAD = ("Reporting Period,Track Title,ISRC Code,Digital Service Provider,"
        "Royalty ($US)\n")


def month_label(back):
    """The "YYYY-MM" label of the month `back` months before this one, so
    these fixtures mean the same thing whenever they are run."""
    year, month = TODAY.year, TODAY.month - back
    while month <= 0:
        month += 12
        year -= 1
    return "%04d-%02d" % (year, month)


def rows_csv(period, sources):
    return HEAD + "".join("%s,Hungry Gods,GBWUL2686921,%s,%s\n" % (period, s, 100 + i)
                          for i, s in enumerate(sources))


@pytest.fixture
def artist(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    email = "lag-%s@example.net" % uuid.uuid4().hex[:10]
    client = appmod.app.test_client()
    client.post("/signup", data={"name": "Hungry Gods", "email": email, "password": PW})
    user = store.get_user_by_email(email)
    assert user is not None, "the sign-up door refused the test account"
    store.set_user_plan(user["id"], "label")
    client.user = user
    return client


def upload(client, name, csv):
    res = client.post("/statements",
                      data={"statement": (io.BytesIO(csv.encode()), name)},
                      content_type="multipart/form-data")
    assert res.status_code in (200, 302), res.status_code


def page(client, path="/statements"):
    res = client.get(path)
    assert res.status_code == 200, "%s answered %s" % (path, res.status_code)
    return res.get_data(as_text=True)


def reading(html):
    """Just the reporting-lag section, so a word somewhere else on a busy
    money page cannot pass a test about this one."""
    start = html.find('id="reporting"')
    assert start > 0, "the reporting-lag section is not on this page at all"
    start = html.rfind("<section", 0, start)
    return html[start:html.find("</section>", start)]


# --- the wiring itself ---------------------------------------------------

def test_the_module_is_no_longer_imported_by_nothing():
    """The defect this whole batch exists to fix: 235 tested lines that
    ran for nobody."""
    assert se.royalty_lag is royalty_lag
    assert appmod.reporting_lag is se.reporting_lag


def test_the_statements_page_carries_the_reading(artist):
    upload(artist, "jan.csv", rows_csv(month_label(8), ["Deezer"]))
    section = reading(page(artist))
    assert "Has each store reported?" in section
    assert "Deezer" in section


def test_the_royalties_page_carries_it_too_and_points_at_the_full_one(artist):
    upload(artist, "jan.csv", rows_csv(month_label(8), ["Deezer"]))
    section = reading(page(artist, "/royalties"))
    assert "Deezer" in section
    assert "/statements#reporting" in section, "no way through to the row-by-row reading"


def test_the_reading_is_not_narrowed_by_the_period_control(artist):
    """A store owes a period whatever period the artist is looking at."""
    upload(artist, "old.csv", rows_csv(month_label(8), ["Deezer"]))
    upload(artist, "new.csv", rows_csv(month_label(1), ["Spotify"]))
    section = reading(page(artist, "/royalties?period=" + month_label(1)))
    assert "Deezer" in section, "the period filter hid a store from its own verdict"


# --- the five states, as an artist reads them ----------------------------

def test_a_store_that_is_genuinely_overdue_is_named_and_called_overdue(artist):
    upload(artist, "stale.csv", rows_csv(month_label(8), ["Deezer"]))
    section = reading(page(artist))
    assert "Overdue" in section
    assert "Deezer" in section and "worth asking about" in section


def test_a_store_being_itself_is_reassured_about_rather_than_flagged(artist):
    """The whole point: an artist must stop worrying about a platform
    behaving normally."""
    upload(artist, "recent.csv", rows_csv(month_label(2), ["Spotify"]))
    section = reading(page(artist))
    assert "Normal" in section and "normal for Spotify" in section
    assert "Overdue" not in section.split('class="rl-key"')[0], \
        "a store inside its usual wait was flagged"
    assert "nothing to chase" in section


def test_a_period_that_has_arrived_with_nothing_yet_outstanding_says_so(artist):
    upload(artist, "current.csv", rows_csv(month_label(0), ["Spotify"]))
    section = reading(page(artist))
    assert "Reported" in section and "has arrived" in section
    assert "not recorded anywhere" in section, \
        "the page offered a figure for how long it took"


def test_a_store_nobody_has_a_figure_for_keeps_a_visible_row_saying_so(artist):
    """Unknown is not a pass and is not hidden."""
    upload(artist, "mixed.csv", rows_csv(month_label(2), ["Spotify", "Qobuz (JPY)"]))
    section = reading(page(artist))
    assert "Qobuz" in section, "a store with no reading was dropped off the page"
    assert "No reading" in section
    assert "nothing has been assumed" in section
    assert "Normal" in section, "the ones that ARE fine still read as fine"


def test_an_account_with_no_statements_is_told_it_has_no_reading(artist):
    """The state a new artist sees first, and the one most likely to be
    quietly wrong. It must not read as a pass."""
    for path in ("/statements", "/royalties"):
        section = reading(page(artist, path))
        assert "no reading" in section.lower()
        assert "Overdue" not in section and "Normal" not in section
        assert "nothing to chase" not in section, \
            "an account with nothing on file was told everything is fine"
    statements = reading(page(artist))
    assert "This is not a pass" in statements


# --- what the verdict rests on -------------------------------------------

def test_every_verdict_says_it_is_a_general_figure_and_not_this_account(artist):
    upload(artist, "one.csv", rows_csv(month_label(2), ["Spotify"]))
    section = reading(page(artist))
    assert "a general figure for this platform, not yours" in section
    assert "Not measured from your account" in section, "royalty_lag's own words"
    assert "Not one of these figures is measured from your account." in section
    # Two money-desk tests lock the literal word None out of the page,
    # because that is how a Python None reaching a template is caught.
    assert "None" not in section


def test_no_page_ever_claims_a_verdict_measured_from_this_account(artist):
    """The rule, checked on a busy account in every state at once: a
    published table is never dressed up as the artist's own evidence."""
    upload(artist, "stale.csv", rows_csv(month_label(9), ["Deezer", "Qobuz (JPY)"]))
    upload(artist, "fresh.csv", rows_csv(month_label(2), ["Spotify"]))
    upload(artist, "now.csv", rows_csv(month_label(0), ["Apple Music"]))
    for path in ("/statements", "/royalties"):
        section = reading(page(artist, path))
        for claim in ("measured from your own statements",
                      "Measured from your own statements",
                      "your own history", "over 3 periods", "over 4 periods"):
            assert claim not in section, claim


def test_the_day_the_artist_uploaded_is_never_read_as_a_platforms_pace(artist):
    """One file carrying a year of history is a backfill, not a store
    that took a year. Nothing on the page may turn the upload day into a
    reporting lag, in either direction."""
    csv = HEAD + "".join(
        "%s,Hungry Gods,GBWUL2686921,Spotify,100\n" % month_label(b)
        for b in range(12, 0, -1))
    upload(artist, "history.csv", csv)
    section = reading(page(artist))
    assert "is the latest period on file for this store" in section
    assert "not recorded anywhere" in section
    for invented in ("300 days", "330 days", "360 days", "365 days"):
        assert invented not in section


def test_nothing_in_the_reading_ever_reaches_observed_days(monkeypatch):
    """The lock under all of the above. observed_days() turns a history of
    arrivals into a per-source pace, and the only arrival dates this app
    holds are the artist's own upload days, so it must never be called
    from here."""
    def boom(*args, **kwargs):
        raise AssertionError("upload history was read as a platform's reporting pace")
    monkeypatch.setattr(royalty_lag, "observed_days", boom)
    view = se.reporting_lag(_rows(("Spotify", JAN), ("Deezer", JAN)), today=NOW)
    assert [r["basis"] for r in view["rows"]] == ["typical", "typical"]


def test_the_reading_never_dates_a_period_the_distributor_did_not(artist):
    csv = (HEAD + "Q1 whenever,Hungry Gods,GBWUL2686921,Spotify,100.00\n")
    upload(artist, "undated.csv", csv)
    section = reading(page(artist))
    assert "No reading" in section
    assert "says which period they cover" in section
    for month in ("January", "Jan 20", "Feb 20", "Mar 20"):
        assert month not in section, "a date was invented for an undatable period"


# --- what the page owes a reader who cannot see colour -------------------

def test_no_state_is_carried_by_colour_alone(artist):
    upload(artist, "stale.csv", rows_csv(month_label(8), ["Deezer", "Qobuz (JPY)"]))
    upload(artist, "fresh.csv", rows_csv(month_label(2), ["Spotify"]))
    section = reading(page(artist))
    rows = section.count('class="rl-row"')
    assert rows == 3, rows
    words = sum(section.count(">%s<" % w) for w in se.LAG_WORDS.values())
    assert words >= rows, "a row carried its state in a colour and not in a word"


def test_the_two_questions_are_told_apart_on_the_page(artist):
    """A coverage gap is a track missing from a store. This is a store
    that has not reported. Same page, different remedy."""
    upload(artist, "stale.csv", rows_csv(month_label(8), ["Deezer"]))
    section = reading(page(artist))
    assert "Not a coverage gap." in section
    assert "has not reported for a period" in section


# --- the engine, where a date can be pinned ------------------------------

JAN = "2026-01"
NOW = datetime.date(2026, 9, 21)


def _rows(*pairs):
    return [{"source": s, "period": p, "amount": 100.0} for s, p in pairs]


def test_the_engine_reads_the_wait_from_the_calendar_and_nothing_else():
    """A period ended on a known day, today is a known day, and no row
    covers the period after it. That subtraction is the only number."""
    view = se.reporting_lag(_rows(("Spotify", JAN)), today=NOW)
    spotify = view["rows"][0]
    assert spotify["state"] == "overdue"
    assert spotify["basis"] == "typical" and spotify["expected"] == 45
    assert spotify["waited"] == (NOW - datetime.date(2026, 2, 28)).days
    assert spotify["waiting_for"] == "Feb 2026"


def test_the_engine_keeps_an_unknown_store_out_of_the_settled_pile():
    view = se.reporting_lag(_rows(("Qobuz (JPY)", JAN), ("Spotify", JAN)), today=NOW)
    by = {r["store"]: r for r in view["rows"]}
    assert by["Qobuz"]["state"] == "unknown"
    assert by["Qobuz"] in view["flagged"] and by["Qobuz"] not in view["settled"]
    assert by["Qobuz"]["expected"] is None, "a figure was assumed for a store with none"


def test_the_engine_says_nothing_rather_than_something_when_there_is_nothing():
    view = se.reporting_lag([], today=NOW)
    assert view["rows"] == [] and view["flagged"] == [] and view["settled"] == []
    assert "no reading" in view["summary"]["headline"]
    assert view["summary"]["basis_note"] == ""


def test_the_engine_folds_a_stores_payee_lines_into_one_verdict():
    """A distributor reports YouTube as four lines and reports them
    together, so four rows are one question, not four."""
    view = se.reporting_lag(
        _rows(("YouTube Streaming", JAN), ("YouTube Shorts", JAN),
              ("YouTube Content ID", JAN)), today=NOW)
    assert [r["store"] for r in view["rows"]] == ["YouTube"]
    assert view["rows"][0]["lines"] == 3


def test_the_engine_reads_the_period_shapes_distributors_actually_write():
    for label in ("2026-01", "JAN-26", "January 2026", "2026/01"):
        assert se._period_end(label) == datetime.date(2026, 1, 31), label
    for nonsense in ("", None, "Q1", "2026-13", "whenever"):
        assert se._period_end(nonsense) is None, nonsense

"""The zero-guards from the owner-notes batch of 2026-09-21.

The standing rule behind all of them: this product never shows a number it
does not have, and never shows a bare zero where words belong. A 0 printed
as a measurement is a lie, because the reader cannot tell it from a real
zero. "Not measured" is an honest state; an em dash is not, because it does
not say which of the two it means.

The Command Center half of it is the other half of the same rule. A
coverage gap on its own is not a finding: stores report months apart, so
"missing from Deezer" only means something when Deezer is late for Deezer.
royalty_lag makes that call, and these lock in that the Command Center asks
it rather than counting rows.
"""
import datetime

import pytest

import command_center as cc


# --- the LCD says what it means ----------------------------------------------

@pytest.fixture(scope="module")
def sb():
    from app import create_app
    app = create_app()
    with app.app_context():
        return app.jinja_env.get_template("_sb.html").make_module({})


def _flat(html):
    return " ".join(str(html).split())


def test_an_lcd_with_no_reading_says_so_in_words(sb):
    out = _flat(sb.lcd(None, "total views"))
    assert "Not measured" in out
    assert "—" not in out, "an em dash does not say which kind of blank this is"


def test_an_lcd_never_prints_a_bare_zero_for_a_missing_reading(sb):
    assert ">0<" not in _flat(sb.lcd(None, "followers"))


def test_a_real_zero_still_prints_because_it_is_a_reading(sb):
    """The rule is against a FAKE zero. A measured zero is a measurement."""
    out = _flat(sb.lcd(0, "sold on the road"))
    assert ">0<" in out and "Not measured" not in out


# --- the newest period a statement covers ------------------------------------

def _row(source, period, amount=10.0, title="Signal Fire"):
    return {"source": source, "period": period, "amount": amount, "title": title}


def test_the_newest_period_becomes_the_last_day_of_that_month():
    rows = [_row("Spotify", "2026-01"), _row("Spotify", "2026-02")]
    assert cc._latest_period_end(rows) == datetime.date(2026, 2, 28)


def test_a_period_nobody_can_parse_is_skipped_rather_than_guessed_at():
    rows = [_row("Spotify", "2026-03"), _row("Spotify", "whenever")]
    assert cc._latest_period_end(rows) == datetime.date(2026, 3, 31)


def test_no_dated_period_at_all_is_none_and_not_today():
    assert cc._latest_period_end([_row("Spotify", "")]) is None
    assert cc._latest_period_end([]) is None


# --- a gap is only a finding when the store is late for itself ---------------

def _summary(missing, estimate=90.0, title="Signal Fire"):
    return {"coverage_gaps": [{"title": title, "missing_sources": missing,
                               "estimated_value": estimate}]}


def test_a_store_still_inside_its_usual_wait_is_not_a_finding():
    """Deezer's published wait is 60 days. Three weeks after the period
    closed it is a platform being a platform, not a problem."""
    rows = [_row("Spotify", "2026-08"), _row("Deezer", "2026-08", 30.0, "Night Drive")]
    end, late = cc._overdue_gaps(_summary(["Deezer"]), rows, datetime.date(2026, 9, 21))
    assert end == datetime.date(2026, 8, 31)
    assert late == [], "three weeks is not late for Deezer"


def test_a_store_far_past_its_own_pace_is_a_finding():
    rows = [_row("Spotify", "2025-06"), _row("Deezer", "2025-06", 30.0, "Night Drive")]
    end, late = cc._overdue_gaps(_summary(["Deezer"]), rows, datetime.date(2026, 9, 21))
    assert [f["source"] for f in late] == ["Deezer"]
    assert late[0]["judgement"]["state"] == "overdue"


def test_no_dated_period_gives_no_verdict_rather_than_a_pass():
    rows = [_row("Deezer", "")]
    end, late = cc._overdue_gaps(_summary(["Deezer"]), rows, datetime.date(2026, 9, 21))
    assert end is None and late == []


def test_the_verdict_is_never_presented_as_this_accounts_own_figure():
    """Nothing records when a distributor reported a period, so every
    verdict here rests on the published table and has to say so."""
    rows = [_row("Deezer", "2025-06", 30.0, "Night Drive")]
    _, late = cc._overdue_gaps(_summary(["Deezer"]), rows, datetime.date(2026, 9, 21))
    assert late[0]["judgement"]["basis"] == "typical"
    assert "Not measured from your account" in late[0]["judgement"]["detail"]


def test_a_track_missing_from_several_stores_is_judged_store_by_store():
    """Bandcamp pays in a fortnight and TikTok takes a quarter. Collapsing
    them hides which of the two is the real delivery failure."""
    rows = [_row("Bandcamp", "2026-06", 100.0, "Night Drive"),
            _row("TikTok", "2026-06", 100.0, "Night Drive")]
    _, late = cc._overdue_gaps(_summary(["Bandcamp", "TikTok"]), rows,
                               datetime.date(2026, 8, 1))
    assert [f["source"] for f in late] == ["Bandcamp"]


# --- ordering ----------------------------------------------------------------

def test_money_orders_money_by_value_times_confidence():
    ranked = cc.rank_alerts([
        ("high", "small", "r", "/a", "c", 10.0),
        ("high", "big", "r", "/b", "c", 900.0),
    ])
    assert [a[1] for a in ranked] == ["big", "small"]


def test_money_never_reorders_an_alert_that_carries_none():
    """An amount nobody has is not a zero. A live link sending fans to a
    dead page must not drop below a twelve dollar estimate."""
    ranked = cc.rank_alerts([
        ("high", "dead page", "r", "/a", "smart_link"),
        ("high", "twelve dollars", "r", "/b", "royalty_recovery", 12.0),
    ])
    assert [a[1] for a in ranked] == ["dead page", "twelve dollars"]


def test_severity_still_decides_the_bands():
    ranked = cc.rank_alerts([
        ("medium", "medium money", "r", "/a", "c", 900.0),
        ("high", "high money", "r", "/b", "c", 5.0),
    ])
    assert [a[1] for a in ranked] == ["high money", "medium money"]


def test_every_alert_comes_back_as_the_five_tuple_the_page_unpacks():
    ranked = cc.rank_alerts([("high", "t", "r", "/a", "c", 5.0),
                             ("medium", "t2", "r", "/b", "c")])
    assert all(len(a) == 5 for a in ranked)


def test_an_unlisted_severity_keeps_its_place_instead_of_vanishing():
    ranked = cc.rank_alerts([("high", "a", "r", "/a", "c"),
                             ("whatever", "b", "r", "/b", "c")])
    assert [a[1] for a in ranked] == ["a", "b"]

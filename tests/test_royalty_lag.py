"""Late, or just slow? The difference decides whether anyone should care.

Both distributor conversations and the outside audit named the same thing:
a coverage gap on its own is meaningless because every store reports at its
own pace, so an artist cannot tell a real problem from a platform being a
platform.

The rule under test is which evidence wins. What this account has actually
waited beats a published industry figure, a published figure beats nothing,
and nothing means no verdict at all rather than a comfortable guess.
"""
import datetime

import royalty_lag as rl

JAN = datetime.date(2026, 1, 31)


def _d(s):
    return datetime.date.fromisoformat(s)


def test_a_normal_wait_is_named_as_normal_rather_than_flagged():
    j = rl.judge("Spotify", JAN, _d("2026-03-05"))
    assert j["state"] == "normal"
    assert "normal for Spotify" in j["headline"]
    assert j["waited"] == 33 and j["expected"] == 45


def test_a_little_over_is_slow_and_says_that_is_common():
    j = rl.judge("Spotify", JAN, _d("2026-03-25"))
    assert j["state"] == "slow"
    assert "not on its own a sign of a problem" in j["detail"]


def test_far_past_its_own_pace_is_worth_chasing():
    j = rl.judge("Spotify", JAN, _d("2026-06-30"))
    assert j["state"] == "overdue"
    assert "worth asking about" in j["detail"]
    assert "150 days, against a usual 45" == j["headline"]


def test_the_accounts_own_history_beats_the_published_figure():
    """Ninety days is alarming for Spotify in general and unremarkable if
    this account has always waited ninety days."""
    # Day 28, because February has no thirtieth and a bad date is dropped.
    history = [("Spotify", "2025-0%d-28" % m, "2025-%02d-28" % (m + 3)) for m in (1, 2, 3, 4)]
    observed = rl.observed_days(history)
    assert observed["spotify"]["periods"] == 4
    plain = rl.judge("Spotify", JAN, _d("2026-04-20"))
    mine = rl.judge("Spotify", JAN, _d("2026-04-20"), observed=observed)
    assert plain["state"] == "overdue" and plain["basis"] == "typical"
    assert mine["state"] in ("normal", "slow") and mine["basis"] == "measured"
    assert "Measured from your own statements" in mine["detail"]


def test_a_thin_history_is_not_treated_as_a_pattern():
    thin = [("Deezer", "2025-01-31", "2025-03-05"), ("Deezer", "2025-02-28", "2025-04-02")]
    assert rl.observed_days(thin) == {}, "two periods is a coincidence"
    assert rl.expectation("Deezer", rl.observed_days(thin))["basis"] == "typical"


def test_a_platform_nobody_knows_gets_no_verdict_at_all():
    j = rl.judge("Some Regional Store", JAN, _d("2026-09-01"))
    assert j["state"] == "unknown"
    assert "nothing has been assumed" in j["detail"]
    assert j["expected"] is None
    assert "no way to say whether that is late" in j["headline"]


def test_a_published_figure_says_it_is_not_this_accounts_own():
    e = rl.expectation("Apple Music")
    assert e["basis"] == "typical"
    assert "Not measured from your account" in e["detail"]


def test_a_platform_with_a_territory_after_it_is_the_same_platform():
    for name in ("Spotify (US)", "Spotify - UK", "Apple Music (DE)"):
        assert rl.typical_days(name) is not None, name


def test_one_that_has_arrived_reports_how_long_it_took():
    j = rl.judge("Spotify", JAN, _d("2026-06-01"), reported_on=_d("2026-03-10"))
    assert j["state"] == "reported" and j["waited"] == 38
    assert "Reported after 38 days" == j["headline"]


def test_ranking_drops_the_platforms_that_are_only_being_themselves():
    findings = [
        {"source": "Spotify", "judgement": rl.judge("Spotify", JAN, _d("2026-03-05"))},
        {"source": "TikTok", "judgement": rl.judge("TikTok", JAN, _d("2026-04-01"))},
        {"source": "Deezer", "estimate": 210.0,
         "judgement": rl.judge("Deezer", JAN, _d("2026-09-01"))},
    ]
    ranked = rl.rank(findings)
    assert [f["source"] for f in ranked] == ["Deezer"], "only the overdue one is a finding"


def test_money_leads_but_an_unknown_amount_is_not_treated_as_a_small_one():
    late = rl.judge("Deezer", JAN, _d("2026-09-01"))
    very_late = rl.judge("Spotify", JAN, _d("2026-12-01"))
    ranked = rl.rank([
        {"source": "small", "estimate": 4.0, "judgement": late},
        {"source": "unknown amount", "judgement": very_late},
        {"source": "big", "estimate": 900.0, "judgement": late},
    ])
    assert [f["source"] for f in ranked][0] == "big"
    names = [f["source"] for f in ranked]
    assert names.index("unknown amount") < names.index("small") or \
        ranked[names.index("unknown amount")]["priority"]["estimated"] is False
    assert ranked[names.index("unknown amount")]["priority"]["estimated"] is False


def test_evidence_outranks_a_table_when_the_money_is_the_same():
    observed = rl.observed_days([("Deezer", "2025-0%d-28" % m, "2025-0%d-28" % (m + 1))
                                 for m in (1, 2, 3, 4)])
    measured = {"source": "measured", "estimate": 100.0,
                "judgement": rl.judge("Deezer", JAN, _d("2026-09-01"), observed=observed)}
    guessed = {"source": "guessed", "estimate": 100.0,
               "judgement": rl.judge("Deezer", JAN, _d("2026-09-01"))}
    ranked = rl.rank([guessed, measured])
    assert ranked[0]["source"] == "measured"
    assert ranked[0]["priority"]["confidence"] > ranked[1]["priority"]["confidence"]


def test_rubbish_dates_never_produce_a_verdict():
    for bad in ("", None, "not a date", "2026-13-45"):
        assert rl.judge("Spotify", bad, _d("2026-06-01"))["state"] == "unknown"
        assert rl.judge("Spotify", JAN, bad)["state"] == "unknown"


def test_a_statement_that_arrived_before_its_period_ended_is_ignored():
    """Not evidence of a fast platform; evidence of a bad row."""
    assert rl.observed_days([("Spotify", "2026-03-31", "2026-01-01")] * 5) == {}

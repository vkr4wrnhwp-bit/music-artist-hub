"""A gap estimate is a number somebody may put in a letter.

The old rule was the track's own AVERAGE per-source earnings times the
COUNT of stores it was missing from, which treats every store as equally
valuable. On a real Symphonic report - King 810, June 2026, 22,502 rows
across 39 sources - the largest source was 50.3% of all earnings and the
smallest 0.0001%, so a missing Qobuz (JPY) listing was valued exactly
like a missing Spotify one. The Recovery page reported $3,079 recoverable
against $3,278 earned: 94%.

The rule now is that a track worth X% of the catalogue would have earned
roughly X% of what a store paid overall. On the same report that is $94,
or 3%.

These tests hold the property rather than the arithmetic: a missing
BIG store must be worth more than a missing tiny one, and the total can
never run away.
"""
import statements_engine as se


def _rows(*triples):
    return [{"title": t, "source": s, "amount": a, "period": "2026-06",
             "territory": "", "isrc": ""} for t, s, a in triples]


def test_a_missing_big_store_is_worth_more_than_a_missing_tiny_one():
    """The whole point. Under the old rule these two gaps were equal."""
    rows = _rows(
        ("Anchor", "Spotify", 1000.0),      # Spotify is the big store
        ("Anchor", "Qobuz", 1.0),           # Qobuz is the tiny one
        ("MissesBig", "Qobuz", 10.0),       # earns only on the tiny store
        ("MissesTiny", "Spotify", 10.0),    # earns only on the big store
    )
    gaps = {g["title"]: g["estimated_value"]
            for g in se.analyze(rows)["coverage_gaps"]}
    assert gaps["MissesBig"] > gaps["MissesTiny"], (
        "missing the store that pays 99%% of the money must dominate: %r"
        % gaps)


def test_the_estimate_cannot_run_away_on_a_track_that_only_earned_pennies():
    """A track present only on a negligible store used to extrapolate
    to a fortune under a coverage-ratio rule. Bounded by construction
    here: a track can never be estimated above the catalogue total."""
    rows = _rows(
        ("Giant", "Spotify", 100000.0),
        ("Pennies", "Qobuz", 0.01),
        ("Giant", "Qobuz", 0.01),
    )
    analysis = se.analyze(rows)
    for gap in analysis["coverage_gaps"]:
        assert gap["estimated_value"] <= analysis["total"], gap


def test_the_total_gap_stays_a_sane_fraction_of_real_earnings():
    """The failure that started this: 94% of earnings reported as
    recoverable. A catalogue whose tracks are mostly present everywhere
    cannot be mostly missing."""
    rows = []
    for i in range(10):
        rows += _rows(("T%d" % i, "Spotify", 100.0),
                      ("T%d" % i, "Apple Music", 40.0))
    # One track absent from a single small store.
    rows += _rows(("Odd", "Spotify", 50.0), ("Anchor", "Qobuz", 0.50))
    analysis = se.analyze(rows)
    assert analysis["gap_estimate_total"] < analysis["total"] * 0.5, (
        "estimated %.2f against %.2f earned"
        % (analysis["gap_estimate_total"], analysis["total"]))


def test_a_track_present_everywhere_has_no_gap():
    rows = _rows(("Everywhere", "Spotify", 10.0),
                 ("Everywhere", "Apple Music", 5.0),
                 ("Other", "Spotify", 3.0),
                 ("Other", "Apple Music", 2.0))
    assert se.analyze(rows)["coverage_gaps"] == []


def test_the_isrc_travels_with_the_row():
    """The store check needs the recording's own identifier, so the
    parser has to keep it - a title match breaks on remixes and features,
    and a wrong match becomes a wrong claim in a letter."""
    parsed = se.parse_statement(
        "Track Title,Digital Service Provider,Royalty ($US),ISRC Code\n"
        "Hungry Gods,Spotify,12.34,GB-RKQ-24-54700\n")
    assert parsed["columns"]["isrc"] == "ISRC Code"
    assert parsed["rows"][0]["isrc"] == "GBRKQ2454700", "dashes normalised out"

"""The instrument geometry never invents a reading.

meters.py turns dated series and scores into paths. The rules it holds:
a gap stays a gap, a trailing gap is drawn as a dashed tail, one point
is not a line, a change from nothing is not a percentage, and the dial's
lit track is only as long as the share of the score that was measured.
"""
import meters


def test_short_reads_like_a_person_would_write_it():
    assert meters.short(812) == "812"
    assert meters.short(45300) == "45.3k"
    assert meters.short(12000) == "12k"
    assert meters.short(1350000) == "1.35M"
    assert meters.short(None) == ""


def test_a_change_from_nothing_is_not_a_percentage():
    assert meters.pct_change(None, 10) is None
    assert meters.pct_change(10, None) is None
    assert meters.pct_change(0, 10) is None
    assert meters.pct_change(100, 106.4) == 6.4
    assert meters.pct_change(100, 89) == -11.0


def test_one_point_is_not_a_line():
    assert meters.sparkline([("d1", 5)]) is None
    assert meters.sparkline([("d1", 5), ("d2", None)]) is None
    assert meters.sparkline([]) is None


def test_gaps_are_skipped_and_a_trailing_gap_is_a_dashed_tail():
    sp = meters.sparkline([("d1", 100), ("d2", None), ("d3", 120), ("d4", None), ("d5", None)])
    assert sp["measured"] == 3 - 1 and sp["total"] == 5   # two measured of five
    assert sp["line"].count("L") == 1, "only the measured points are joined"
    assert sp["gap_tail"], "the unmeasured days at the end are drawn, dashed, at the last reading"
    assert sp["first"] == 100 and sp["last"] == 120
    assert sp["low"] == 100 and sp["high"] == 120


def test_a_complete_series_has_no_tail():
    sp = meters.sparkline([("d1", 1), ("d2", 2), ("d3", 3)])
    assert sp["gap_tail"] == "" and sp["measured"] == 3


def test_the_rail_places_today_between_the_low_and_the_high():
    assert meters.rail(100, 200, 200) == 100
    assert meters.rail(100, 200, 100) == 0
    assert meters.rail(100, 200, 150) == 50
    assert meters.rail(5, 5, 5) == 50, "a flat range still has a position"
    assert meters.rail(None, 200, 150) is None


def test_the_dial_lights_only_what_was_measured():
    g = meters.gauge(67, coverage=0.9, base=74)
    assert g["value"] and g["measurable"] and g["tail"], "value, lit track, dashed tail"
    assert g["penalty"], "74 back to 67 is drawn"
    full = meters.gauge(67, coverage=1.0)
    assert full["tail"] == "" and full["penalty"] == ""


def test_the_dial_end_point_moves_with_the_score():
    x0, _ = meters.gauge(0)["end"]
    x50, y50 = meters.gauge(50)["end"]
    x100, _ = meters.gauge(100)["end"]
    assert x0 < x50 < x100
    assert y50 < meters.gauge(0)["end"][1], "50 sits at the top of the arc"


def test_the_dial_clamps_rather_than_drawing_past_the_arc():
    g = meters.gauge(140, coverage=3, base=-5)
    assert g["end"] == meters.gauge(100)["end"]
    assert g["penalty"] == ""

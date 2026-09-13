"""SB Momentum as a half-dial with a receipt (mockup 2026-09-13).

The lit track is only as long as the share of the score that could be
measured; the anomaly adjustment is drawn as a red segment and stated
as one receipt line with its reason; the score is shown once; the
caption reads in plain words; the cohort comparison is a plain average.
"""
import signal_scoring as scoring


def test_the_dial_reads_the_explanation():
    expl = {"score": 67.0, "base_before_penalty": 74.0, "coverage": 0.9,
            "anomaly_penalty": 7.0,
            "anomaly_reasons": ["Followers rose 9% in one day on 3 Sep with no release or playlist placement"],
            "missing": ["catalog_consistency"],
            "contributions": {k: {"value": 60.0, "weight": w, "points": 6.0}
                              for k, w in scoring.MOMENTUM_WEIGHTS.items() if k != "catalog_consistency"}}
    dial = scoring.momentum_dial(expl)
    assert dial["caption"] == "Based on 7 of 8 measured inputs."
    assert dial["gauge"]["penalty"] and dial["gauge"]["tail"], "74 back to 67 drawn; the unmeasured tenth dashed"
    labels = [r["label"] for r in dial["receipt"]]
    assert labels == ["Measured inputs, weighted", "Anomaly adjustment"]
    assert dial["receipt"][0]["value"] == 74 and dial["receipt"][1]["value"] == "-7"
    assert "Withheld until the increase is sustained." in dial["receipt"][1]["small"]
    assert "SB Momentum" not in labels, "the gauge is the total; the score is shown once"
    rows = {r["label"]: r for r in dial["inputs"]}
    assert rows["Catalog consistency"]["value"] is None, "not padded with a number"
    assert rows["Velocity"]["value"] == 60 and rows["Velocity"]["weight"] == ".20"


def test_a_missing_explanation_draws_an_empty_dial_not_a_false_one():
    dial = scoring.momentum_dial({})
    assert dial["gauge"]["value"] == "" and dial["gauge"]["penalty"] == ""
    assert dial["receipt"][0]["value"] == 0 and len(dial["receipt"]) == 1


def test_no_penalty_means_no_penalty_line():
    dial = scoring.momentum_dial({"score": 50, "base_before_penalty": 50, "coverage": 1.0,
                                  "anomaly_penalty": 0, "missing": [], "contributions": {}})
    assert len(dial["receipt"]) == 1 and dial["gauge"]["tail"] == ""

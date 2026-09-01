# -*- coding: utf-8 -*-
"""The Studio scoreboard, and the rule it exists to enforce.

Every 0-100 on the cockpit must trace to a measured property against a named
convention - or refuse to be a number at all. The mockup showed "Vocal
Translation 82" for a bare stereo file; that number cannot be measured from a
stereo master, so here it must render as "needs stems", not as a plausible
invention. These tests are the fence around that rule.
"""
import studio_score


HOT = {"integrated": -6.2, "true_peak": -0.2, "sample_peak": -0.4, "lra": 2.1,
       "bpm": 120.1, "bpm_confidence": 0.9, "key": "A minor"}
CLEAN = {"integrated": -14.0, "true_peak": -1.8, "sample_peak": -2.0,
         "lra": 7.0, "bpm": 120.0, "bpm_confidence": 0.95, "key": "A minor"}


def _by_key(board):
    return {c["key"]: c for c in board["categories"]}


# --- nothing is invented ------------------------------------------------------

def test_unmeasurable_categories_carry_no_score():
    """The vocal, the low end and the stereo image cannot be judged from a
    stereo master. A number there would be the fabrication rule 12 forbids."""
    cats = _by_key(studio_score.mix_readiness(CLEAN))
    for key in ("vocal", "lowend", "stereo"):
        assert cats[key]["score"] is None, key
        assert cats[key]["status"] == "unknown"
        assert cats[key]["missing"], key
        assert cats[key]["source"] == "unmeasurable"


def test_an_empty_measurement_yields_no_overall():
    board = studio_score.mix_readiness({})
    assert board["overall"] is None or board["measured_count"] <= 1
    # version completeness is derivable with zero measurements, nothing else is
    measured = [c for c in board["categories"] if c["score"] is not None]
    assert all(c["key"] == "versions" for c in measured)


def test_the_overall_says_how_many_categories_it_stands_on():
    board = studio_score.mix_readiness(CLEAN)
    assert board["measured_count"] < board["total_count"]
    assert board["overall"] is not None


# --- the measured ones score honestly ----------------------------------------

def test_a_clean_master_scores_well_and_a_hot_one_does_not():
    clean = _by_key(studio_score.mix_readiness(CLEAN))
    hot = _by_key(studio_score.mix_readiness(HOT))
    for key in ("headroom", "loudness", "dynamics"):
        assert clean[key]["score"] > hot[key]["score"], key
    assert clean["headroom"]["status"] == "good"
    assert hot["headroom"]["status"] in ("attention", "blocked")


def test_every_scored_category_names_its_evidence_and_source():
    for board in (studio_score.mix_readiness(CLEAN),
                  studio_score.master_intelligence(CLEAN)):
        for c in board["categories"]:
            assert c["evidence"], c["key"]
            assert c["source"] in ("measured", "convention", "unmeasurable")
            assert c["confidence"] in ("strong", "moderate", "limited")


def test_version_completeness_reads_the_vault():
    none_approved = [{"status": "draft"}]
    approved = [{"status": "draft"}, {"status": "locked"}]
    a = _by_key(studio_score.mix_readiness(CLEAN, none_approved))
    b = _by_key(studio_score.mix_readiness(CLEAN, approved))
    assert b["versions"]["score"] > a["versions"]["score"]


def test_no_score_claims_commercial_success():
    """Rule 13. The words on the board are technical, never predictive."""
    import json

    text = json.dumps(studio_score.mix_readiness(CLEAN)).lower()
    for banned in ("hit", "chart", "viral", "commercial success", "streams"):
        assert banned not in text, banned


# --- the lifecycle rail -------------------------------------------------------

def _project(rights=True, release=""):
    return {"rights_confirmed_at": "2026-09-01" if rights else None,
            "rights_confirmed_by": "King Logic" if rights else "",
            "release_id": release}


def test_the_rail_reports_rather_than_decorates():
    """A stage is done only because the thing it names happened."""
    summary = {"versions": [], "source": None}
    rail = {s["key"]: s for s in studio_score.lifecycle(
        _project(rights=False), summary, [])}
    assert rail["create"]["state"] == "done"          # the project exists
    assert rail["finish"]["state"] == "current"       # nothing uploaded yet
    assert rail["approve"]["state"] in ("blocked", "future")


def test_market_and_monetize_admit_they_are_not_wired():
    summary = {"versions": [{"status": "locked"}], "source": {"id": "a"}}
    checklist = [{"required": True, "ok": True}]
    rail = {s["key"]: s for s in studio_score.lifecycle(
        _project(release="rel-1"), summary, checklist)}
    for key in ("market", "monetize"):
        assert rail[key]["state"] != "done"
        assert "not connected" in (rail[key]["why"] or "").lower()


def test_a_blocked_stage_carries_its_reason():
    summary = {"versions": [{"status": "approved"}], "source": {"id": "a"}}
    rail = {s["key"]: s for s in studio_score.lifecycle(
        _project(rights=True), summary,
        [{"required": True, "ok": False}])}
    assert rail["protect"]["why"]                      # approved but not locked
    assert "lock" in rail["protect"]["why"].lower()

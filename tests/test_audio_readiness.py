"""Rulings on a measured master.

The numbers in these tests are from a real record run through the Rack:
-12.5 LUFS integrated, 4.2 LU range, -0.03 dBTP true peak. That last
figure is the whole reason this module exists - it looks harmless on a
peak meter and clips on every platform it is sent to.
"""
import audio_readiness as ar

REAL = {"measured_at": "2026-07-31T00:00:00", "integrated": -12.5,
        "lra": 4.2, "true_peak": -0.03, "bpm": 117.1,
        "bpm_confidence": 0.3, "key": "A minor", "key_fit": 0.79}


# --- the ceiling ---------------------------------------------------------

def test_a_peak_above_the_ceiling_is_a_problem():
    r = ar.true_peak_ruling(-0.03)
    assert r["level"] == "problem"
    assert "-1 dBTP" in r["headline"]
    # It must say how far to come down, not just that something is wrong.
    assert "0.97" in r["action"]


def test_a_safe_peak_passes():
    assert ar.true_peak_ruling(-1.5)["level"] == "ok"


def test_exactly_at_the_ceiling_is_not_over_it():
    assert ar.true_peak_ruling(-1.0)["level"] == "ok"


def test_a_very_low_peak_is_flagged_as_probably_a_rough_bounce():
    r = ar.true_peak_ruling(-12.0)
    assert r["level"] == "watch"


def test_an_unmeasured_peak_says_so_rather_than_passing():
    r = ar.true_peak_ruling(None)
    assert r["level"] == "unknown"      # never a silent pass


# --- loudness against real platform targets -----------------------------

def test_louder_than_every_target_is_reported_as_a_tradeoff_not_a_fault():
    r = ar.loudness_ruling(-8.0)
    assert r["level"] == "watch"
    assert "turn it down" in r["detail"]


def test_a_normal_master_sits_in_the_band():
    assert ar.loudness_ruling(-14.2)["level"] == "ok"


def test_a_quiet_master_with_headroom_is_flagged_as_raisable():
    # -22 LUFS peaking at -20 dBTP: plenty of room to come up.
    assert ar.loudness_ruling(-22.0, true_peak=-20.0)["level"] == "watch"


def test_quiet_but_already_peaking_is_the_worse_case():
    """Quiet average, peaks near the ceiling. Raising it would clip, so
    the useful finding is the gap itself - usually one stray transient
    holding the whole record down."""
    r = ar.loudness_ruling(-22.0, true_peak=-6.0)
    assert r["level"] == "problem"
    assert "no headroom" in r["headline"]
    assert "transient" in r["detail"]


def test_raising_a_quiet_master_that_would_clip_is_not_suggested():
    # Quiet, but with a peak so close to the ceiling that gain would
    # breach it. Suggesting "turn it up" there would be bad advice.
    r = ar.loudness_ruling(-20.0, true_peak=-0.5)
    assert "raise" not in (r.get("action") or "").lower()


# --- dynamic range -------------------------------------------------------

def test_a_flat_master_is_flagged():
    assert ar.range_ruling(1.5)["level"] == "watch"


def test_a_very_wide_range_suggests_an_unmastered_bounce():
    assert ar.range_ruling(20.0)["level"] == "watch"


def test_a_normal_range_passes():
    assert ar.range_ruling(4.2)["level"] == "ok"


# --- tempo and key: only quote what the detector was sure of ------------

def test_an_unconfident_tempo_is_hedged_not_stated():
    r = ar.tempo_key_ruling(117.1, 0.3, "A minor", 0.79)
    assert r["level"] == "watch"
    assert "not confident" in r["detail"] or "not confident" in r["headline"]


def test_a_confident_tempo_is_stated_plainly():
    r = ar.tempo_key_ruling(120.0, 0.9, "C major", 0.85)
    assert r["level"] == "ok"


# --- the whole assessment ------------------------------------------------

def test_the_real_track_is_caught():
    a = ar.assess(REAL)
    assert a["measured"] is True
    assert a["verdict"] == "problem"
    assert "dBTP" in a["summary"]


def test_never_measured_is_its_own_state():
    a = ar.assess(None)
    assert a["measured"] is False
    assert a["verdict"] == "unmeasured"
    # The distinction that matters: absent evidence is not a pass.
    assert a["verdict"] != "ok"


def test_a_clean_master_passes_cleanly():
    a = ar.assess({"measured_at": "x", "integrated": -14.1, "lra": 6.0,
                   "true_peak": -1.4})
    assert a["verdict"] == "ok"


def test_every_ruling_carries_its_evidence():
    for r in ar.assess(REAL)["rulings"]:
        if r["level"] != "unknown":
            assert r["evidence"], r["key"]


# --- what it contributes to Release Readiness ---------------------------

def test_an_unmeasured_master_scores_zero_not_a_default_pass():
    pts, mx, note = ar.readiness_points(None)
    assert pts == 0 and mx == 25
    assert "not measured" in note.lower()


def test_a_clipping_master_scores_near_zero():
    pts, _, note = ar.readiness_points(REAL)
    assert pts <= 5
    assert "dBTP" in note


def test_a_clean_master_scores_full():
    pts, mx, _ = ar.readiness_points(
        {"measured_at": "x", "integrated": -14.0, "lra": 5.0,
         "true_peak": -1.2})
    assert pts == mx

import pytest

from royalty_data import (
    HealthFactor,
    Kpi,
    Payout,
    PlatformBalance,
    get_action_items,
    get_health_factors,
    get_health_recommendations,
    get_platform_balances,
    get_platform_catalog,
    meter_lit_segments,
    reset_connection_state,
    royalty_health_score,
    royalty_progress,
    set_connection_status,
    total_royalties,
)


def test_total_royalties_empty():
    assert total_royalties([]) == 0


def test_total_royalties_single():
    assert total_royalties([PlatformBalance("Spotify", "Streaming", 100.0)]) == 100.0


def test_total_royalties_multiple():
    balances = [
        PlatformBalance("Spotify", "Streaming", 100.0),
        PlatformBalance("ASCAP", "Performance", 50.5),
    ]
    assert total_royalties(balances) == 150.5


def test_royalty_progress_under_goal():
    assert royalty_progress(5000, 20000) == 0.25


def test_royalty_progress_capped_at_one():
    assert royalty_progress(30000, 20000) == 1.0


def test_royalty_progress_zero_goal():
    assert royalty_progress(100, 0) == 0.0


def test_meter_lit_segments_full():
    assert meter_lit_segments(100, 100, segments=12) == 12


def test_meter_lit_segments_half():
    assert meter_lit_segments(50, 100, segments=12) == 6


def test_meter_lit_segments_zero_max():
    assert meter_lit_segments(50, 0, segments=12) == 0


def test_get_action_items_processing_payout():
    balances = [PlatformBalance("Spotify", "Streaming", 100.0)]
    payouts = [Payout("City Lights", "ASCAP", "Processing", 350.0)]
    kpis = [Kpi("Active Streams", "+1", "no pending items here", [1])]
    actions = get_action_items(balances, payouts, kpis)
    payout_actions = [a for a in actions if "City Lights" in a.title]
    assert len(payout_actions) == 1
    assert "ASCAP" in payout_actions[0].result_message


def test_get_action_items_lowest_earner():
    balances = [
        PlatformBalance("Spotify", "Streaming", 100.0),
        PlatformBalance("The MLC", "Mechanical", 10.0),
    ]
    actions = get_action_items(balances, [], [])
    lowest_actions = [a for a in actions if "The MLC" in a.title]
    assert len(lowest_actions) == 1


def test_get_action_items_pending_kpi():
    kpis = [Kpi("Sync Licenses", "1", "1 pending negotiation", [1])]
    actions = get_action_items([], [], kpis)
    assert any("pending negotiation" in a.title.lower() for a in actions)


def test_get_action_items_fallback_when_nothing_applies():
    actions = get_action_items([], [], [])
    assert len(actions) == 1
    assert actions[0].id == "scan"


def test_catalog_includes_all_statuses():
    statuses = {p.status for p in get_platform_catalog()}
    assert statuses == {"connected", "not_connected", "syncing", "needs_login", "error"}


def test_only_connected_platforms_count_toward_balances():
    names = [b.platform for b in get_platform_balances()]
    assert "Spotify" in names
    assert "Tidal" not in names


def test_connecting_platform_adds_it_to_balances_and_total():
    try:
        before = total_royalties(get_platform_balances())
        set_connection_status("tidal", "connected")
        balances = get_platform_balances()
        assert "Tidal" in [b.platform for b in balances]
        assert total_royalties(balances) == pytest.approx(before + 95.20)
    finally:
        reset_connection_state()


def test_disconnecting_platform_removes_it():
    try:
        set_connection_status("spotify", "not_connected")
        assert "Spotify" not in [b.platform for b in get_platform_balances()]
    finally:
        reset_connection_state()


def test_set_connection_status_unknown_platform_returns_none():
    assert set_connection_status("not-a-platform", "connected") is None


def test_health_score_within_range():
    score = royalty_health_score(get_health_factors(get_platform_catalog()))
    assert 0 <= score <= 100


def test_health_score_all_perfect_is_100():
    factors = [
        HealthFactor("a", "A", 1.0, 0.5, "", ""),
        HealthFactor("b", "B", 1.0, 0.5, "", ""),
    ]
    assert royalty_health_score(factors) == 100


def test_health_score_all_zero_is_0():
    factors = [HealthFactor("a", "A", 0.0, 1.0, "", "")]
    assert royalty_health_score(factors) == 0


def test_health_score_no_factors_is_0():
    assert royalty_health_score([]) == 0


def test_health_recommendations_weakest_first_and_excludes_complete():
    factors = [
        HealthFactor("perfect", "Perfect", 1.0, 0.25, "", "done"),
        HealthFactor("mid", "Mid", 0.6, 0.25, "", "improve mid"),
        HealthFactor("worst", "Worst", 0.1, 0.25, "", "fix worst"),
    ]
    recs = get_health_recommendations(factors)
    assert [r.key for r in recs] == ["worst", "mid"]


def test_health_recommendations_limit():
    factors = [HealthFactor(str(i), str(i), i / 10, 0.1, "", "") for i in range(5)]
    assert len(get_health_recommendations(factors, limit=2)) == 2


def test_connecting_platform_raises_health_score():
    try:
        before = royalty_health_score(get_health_factors(get_platform_catalog()))
        set_connection_status("tidal", "connected")
        after = royalty_health_score(get_health_factors(get_platform_catalog()))
        assert after > before
    finally:
        reset_connection_state()

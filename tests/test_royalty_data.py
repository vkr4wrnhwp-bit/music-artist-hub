import pytest

from royalty_data import (
    HealthFactor,
    Kpi,
    Payout,
    PlatformBalance,
    PlatformConnection,
    Song,
    SplitEntry,
    get_health_factors,
    get_health_recommendations,
    get_missing_royalty_findings,
    get_platform_balances,
    get_platform_catalog,
    get_royalty_leak_alerts,
    get_song,
    get_songs,
    meter_lit_segments,
    metadata_completion_score,
    registration_checklist_score,
    reset_connection_state,
    royalty_health_score,
    royalty_progress,
    set_connection_status,
    song_check_status,
    song_missing_issues,
    split_total_percentage,
    splits_fully_confirmed,
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


def test_alerts_processing_payout_is_medium_severity():
    payouts = [Payout("City Lights", "ASCAP", "Processing", 350.0)]
    kpis = [Kpi("Active Streams", "+1", "no pending items here", [1])]
    alerts = get_royalty_leak_alerts([], payouts, kpis, [])
    payout_alerts = [a for a in alerts if "City Lights" in a.title]
    assert len(payout_alerts) == 1
    assert payout_alerts[0].severity == "Medium"
    assert "ASCAP" in payout_alerts[0].resolution_message


def test_alerts_needs_login_platform_is_high_severity():
    catalog = [PlatformConnection("deezer", "Deezer", "Streaming", 200.0, "needs_login")]
    alerts = get_royalty_leak_alerts([], [], [], catalog)
    deezer_alerts = [a for a in alerts if a.source == "Deezer"]
    assert len(deezer_alerts) == 1
    assert deezer_alerts[0].severity == "High"
    assert deezer_alerts[0].estimated_impact == 100.0


def test_alerts_sync_error_platform_is_high_severity():
    catalog = [PlatformConnection("tidal", "Tidal", "Streaming", 95.0, "error")]
    alerts = get_royalty_leak_alerts([], [], [], catalog)
    assert alerts[0].severity == "High"
    assert alerts[0].estimated_impact == 95.0


def test_alerts_not_connected_severity_by_amount():
    catalog = [
        PlatformConnection("big", "Big Platform", "Streaming", 500.0, "not_connected"),
        PlatformConnection("small", "Small Platform", "Streaming", 50.0, "not_connected"),
    ]
    alerts = get_royalty_leak_alerts([], [], [], catalog)
    by_source = {a.source: a for a in alerts}
    assert by_source["Big Platform"].severity == "Medium"
    assert by_source["Small Platform"].severity == "Low"


def test_alerts_pending_kpi_is_low_severity():
    kpis = [Kpi("Sync Licenses", "1", "1 pending negotiation", [1])]
    alerts = get_royalty_leak_alerts([], [], kpis, [])
    matches = [a for a in alerts if "needs review" in a.title.lower()]
    assert len(matches) == 1
    assert matches[0].severity == "Low"


def test_alerts_fallback_when_nothing_applies():
    alerts = get_royalty_leak_alerts([], [], [], [])
    assert len(alerts) == 1
    assert alerts[0].id == "scan"


def test_alerts_sorted_high_severity_first():
    catalog = [
        PlatformConnection("a", "A", "Streaming", 50.0, "not_connected"),
        PlatformConnection("b", "B", "Streaming", 200.0, "error"),
    ]
    alerts = get_royalty_leak_alerts([], [], [], catalog)
    assert alerts[0].severity == "High"


def test_connecting_platform_removes_its_leak_alert():
    try:
        set_connection_status("tidal", "connected")
        alerts = get_royalty_leak_alerts([], [], [], get_platform_catalog())
        assert not any(a.source == "Tidal" for a in alerts)
    finally:
        reset_connection_state()


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


def test_scan_findings_include_unconnected_source():
    findings = get_missing_royalty_findings(get_platform_catalog())
    yt = [f for f in findings if f.source == "YouTube Music"]
    assert len(yt) == 1
    assert yt[0].issue_type == "Uncollected royalties"
    assert yt[0].recommended_action == "Connect YouTube Music"


def test_scan_findings_have_all_fields_and_valid_confidence():
    for f in get_missing_royalty_findings(get_platform_catalog()):
        assert f.source and f.issue_type and f.recommended_action
        assert f.estimated_value > 0
        assert f.confidence in {"High", "Medium", "Low"}


def test_scan_findings_sorted_by_value_desc():
    values = [f.estimated_value for f in get_missing_royalty_findings(get_platform_catalog())]
    assert values == sorted(values, reverse=True)


def test_connecting_source_clears_its_uncollected_finding():
    try:
        set_connection_status("youtube-music", "connected")
        findings = get_missing_royalty_findings(get_platform_catalog())
        uncollected = [
            f for f in findings
            if f.source == "YouTube Music" and f.issue_type == "Uncollected royalties"
        ]
        assert uncollected == []
    finally:
        reset_connection_state()


def test_connected_source_deep_scan_finding_present():
    findings = get_missing_royalty_findings(get_platform_catalog())
    mlc = [f for f in findings if f.source == "The MLC"]
    assert any(f.issue_type == "Unclaimed mechanical royalties" for f in mlc)


def test_get_songs_returns_expected_titles():
    titles = [s.title for s in get_songs()]
    assert "Midnight Drive" in titles
    assert "City Lights" in titles
    assert len(titles) >= 5


def test_get_song_by_id():
    song = get_song("midnight-drive")
    assert song is not None
    assert song.title == "Midnight Drive"


def test_get_song_unknown_id_returns_none():
    assert get_song("not-a-real-song") is None


def test_split_total_percentage_sums_to_100_when_complete():
    song = next(s for s in get_songs() if s.id == "midnight-drive")
    assert split_total_percentage(song) == 100.0


def test_splits_fully_confirmed_true_when_all_confirmed():
    complete = Song(
        id="x", title="X", isrc="A", iswc="B", upc="C", master_owner="M",
        writers=["W"], producers=["P"], publisher="Pub", lyrics_on_file=True,
        alternate_titles=[], registrations={}, total_earned=0, streams=0,
        platform_earnings={}, splits=[SplitEntry("A", "Writer", 100.0, True)],
        monthly_trend=[],
    )
    assert splits_fully_confirmed(complete) is True


def test_splits_fully_confirmed_false_when_any_unconfirmed():
    partial = Song(
        id="x", title="X", isrc="A", iswc="B", upc="C", master_owner="M",
        writers=["W"], producers=["P"], publisher="Pub", lyrics_on_file=True,
        alternate_titles=[], registrations={}, total_earned=0, streams=0,
        platform_earnings={},
        splits=[SplitEntry("A", "Writer", 50.0, True), SplitEntry("B", "Writer", 50.0, False)],
        monthly_trend=[],
    )
    assert splits_fully_confirmed(partial) is False


def test_splits_fully_confirmed_false_when_no_splits():
    empty = Song(
        id="x", title="X", isrc="A", iswc="B", upc="C", master_owner="M",
        writers=["W"], producers=["P"], publisher="Pub", lyrics_on_file=True,
        alternate_titles=[], registrations={}, total_earned=0, streams=0,
        platform_earnings={}, splits=[], monthly_trend=[],
    )
    assert splits_fully_confirmed(empty) is False


def test_song_check_status_all_true_for_fully_complete_song():
    complete = Song(
        id="x", title="X", isrc="A", iswc="B", upc="C", master_owner="M",
        writers=["W"], producers=["P"], publisher="Pub", lyrics_on_file=True,
        alternate_titles=["Alt"],
        registrations={
            "distribution": True, "pro": True, "mlc": True,
            "soundexchange": True, "youtube_content_id": True, "tiktok_meta_rights": True,
        },
        total_earned=0, streams=0, platform_earnings={},
        splits=[SplitEntry("A", "Writer", 100.0, True)], monthly_trend=[],
    )
    status = song_check_status(complete)
    assert all(status.values())
    assert song_missing_issues(complete) == []
    assert metadata_completion_score(complete) == 1.0
    assert registration_checklist_score(complete) == 1.0


def test_song_check_status_empty_song_all_false():
    empty = Song(
        id="x", title="X", isrc=None, iswc=None, upc=None, master_owner="M",
        writers=[], producers=[], publisher=None, lyrics_on_file=False,
        alternate_titles=[], registrations={}, total_earned=0, streams=0,
        platform_earnings={}, splits=[], monthly_trend=[],
    )
    status = song_check_status(empty)
    assert not any(status.values())
    assert len(song_missing_issues(empty)) == len(status)
    assert metadata_completion_score(empty) == 0.0
    assert registration_checklist_score(empty) == 0.0


def test_metadata_and_registration_scores_within_range():
    for song in get_songs():
        assert 0.0 <= metadata_completion_score(song) <= 1.0
        assert 0.0 <= registration_checklist_score(song) <= 1.0

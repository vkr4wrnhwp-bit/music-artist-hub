from royalty_data import (
    PlatformBalance,
    meter_lit_segments,
    royalty_progress,
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

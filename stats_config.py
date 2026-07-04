"""Config-driven data for the Streaming Stats aggregator.

Aggregates real per-song platform_earnings and streams across the whole
catalog into a cross-platform performance view. Earnings and streams are
real; the per-platform stream split is apportioned from each platform's
share of earnings (the app tracks earnings per platform, not streams).
"""

from royalty_data import get_songs, platform_logo_key


def get_stats_data():
    songs = get_songs()
    total_streams = sum(s.streams for s in songs)

    platform_earnings = {}
    for s in songs:
        for platform, amount in (s.platform_earnings or {}).items():
            platform_earnings[platform] = platform_earnings.get(platform, 0) + amount

    total_earnings = sum(platform_earnings.values())
    platforms = []
    for name, earned in sorted(platform_earnings.items(), key=lambda kv: kv[1], reverse=True):
        share = (earned / total_earnings) if total_earnings else 0
        platforms.append({
            "name": name,
            "logo": platform_logo_key(name),
            "earnings": round(earned, 2),
            "share_pct": round(share * 100, 1),
            # Streams apportioned by earnings share (illustrative split).
            "streams": round(total_streams * share),
        })

    top_platform = platforms[0]["name"] if platforms else "—"
    return {
        "summary": {
            "total_streams": total_streams,
            "total_earnings": round(total_earnings, 2),
            "platforms": len(platforms),
            "top_platform": top_platform,
        },
        "platforms": platforms,
        "max_earnings": max((p["earnings"] for p in platforms), default=0),
    }

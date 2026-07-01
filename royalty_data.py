from dataclasses import dataclass


@dataclass
class PlatformBalance:
    platform: str
    royalty_type: str
    amount: float


@dataclass
class Kpi:
    label: str
    value: str
    delta_label: str
    trend: list = None


@dataclass
class Payout:
    song: str
    platform: str
    status: str
    amount: float


def get_platform_balances():
    return [
        PlatformBalance("Spotify", "Streaming Royalties", 2500.00),
        PlatformBalance("Apple Music", "Streaming Royalties", 1234.56),
        PlatformBalance("ASCAP", "Performance Royalties", 8765.43),
        PlatformBalance("BMI", "Performance Royalties", 4321.00),
    ]


def total_royalties(balances):
    return sum(balance.amount for balance in balances)


def get_kpis():
    return [
        Kpi("Active Streams", "+2,350", "+180.1% from last month", [12, 18, 15, 22, 27, 35]),
        Kpi("New Listeners", "+1,200", "+50 from last month", [8, 10, 9, 13, 14, 16]),
        Kpi("Sync Licenses", "2", "1 pending negotiation", [0, 1, 1, 1, 2, 2]),
        Kpi("Follower Growth", "+842", "+5.2% this month", [20, 19, 24, 26, 25, 29]),
    ]


def get_earnings_trend():
    return [
        ("Jan", 800.0),
        ("Feb", 1450.0),
        ("Mar", 1900.0),
        ("Apr", 2200.0),
        ("May", 2800.0),
        ("Jun", 3200.0),
    ]


def get_recent_payouts():
    return [
        Payout("Midnight Drive", "Spotify", "Paid", 250.00),
        Payout("Neon Dreams", "Apple Music", "Paid", 150.00),
        Payout("City Lights", "ASCAP", "Processing", 350.00),
    ]


def get_royalty_goal():
    return 20000.0


def royalty_progress(total, goal):
    if goal <= 0:
        return 0.0
    return min(total / goal, 1.0)


def meter_lit_segments(amount, max_amount, segments=12):
    if max_amount <= 0:
        return 0
    fraction = min(amount / max_amount, 1.0)
    return round(fraction * segments)

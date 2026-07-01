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


@dataclass
class Action:
    id: str
    title: str
    description: str
    cta_label: str
    result_message: str


def get_platform_balances():
    return [
        PlatformBalance("Spotify", "Streaming Royalties", 2500.00),
        PlatformBalance("Apple Music", "Streaming Royalties", 1234.56),
        PlatformBalance("ASCAP", "Performance Royalties", 8765.43),
        PlatformBalance("BMI", "Performance Royalties", 4321.00),
        PlatformBalance("SESAC", "Performance Royalties", 3120.75),
        PlatformBalance("SoundExchange", "Digital Performance Royalties", 1850.32),
        PlatformBalance("The MLC", "Mechanical Royalties", 940.18),
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
    return 25000.0


def royalty_progress(total, goal):
    if goal <= 0:
        return 0.0
    return min(total / goal, 1.0)


def meter_lit_segments(amount, max_amount, segments=12):
    if max_amount <= 0:
        return 0
    fraction = min(amount / max_amount, 1.0)
    return round(fraction * segments)


def get_action_items(balances, payouts, kpis):
    actions = []

    processing_payout = next((p for p in payouts if p.status == "Processing"), None)
    if processing_payout is not None:
        actions.append(Action(
            id=f"payout-{processing_payout.song.lower().replace(' ', '-')}",
            title=f'Follow up on the "{processing_payout.song}" payout',
            description=(
                f"${processing_payout.amount:.2f} from {processing_payout.platform} "
                "is still processing."
            ),
            cta_label="Send Follow-Up",
            result_message=(
                f'Sent a follow-up to {processing_payout.platform} about '
                f'"{processing_payout.song}".'
            ),
        ))

    if balances:
        lowest = min(balances, key=lambda b: b.amount)
        actions.append(Action(
            id=f"lowest-earner-{lowest.platform.lower().replace(' ', '-')}",
            title=f"Boost your lowest earner: {lowest.platform}",
            description=f"{lowest.platform} has collected only ${lowest.amount:.2f} so far.",
            cta_label="Start Royalty Boost",
            result_message=f"Started a Royalty Boost analysis for {lowest.platform}.",
        ))

    pending_kpi = next((k for k in kpis if "pending" in k.delta_label.lower()), None)
    if pending_kpi is not None:
        actions.append(Action(
            id="pending-negotiation",
            title=f"{pending_kpi.label}: {pending_kpi.delta_label}",
            description=f"Current value: {pending_kpi.value}.",
            cta_label="Review Negotiation",
            result_message="Marked the pending negotiation for review.",
        ))

    if not actions:
        actions.append(Action(
            id="scan",
            title="Run a fresh royalty scan across all platforms",
            description="Check for newly reported usage data since your last scan.",
            cta_label="Scan Now",
            result_message="Scan complete — no new missing royalties found this time.",
        ))

    return actions

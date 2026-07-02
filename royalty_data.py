from dataclasses import dataclass, replace


@dataclass
class PlatformBalance:
    platform: str
    royalty_type: str
    amount: float


@dataclass
class PlatformConnection:
    id: str
    platform: str
    royalty_type: str
    amount: float
    status: str  # connected | not_connected | syncing | needs_login | error


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


@dataclass
class HealthFactor:
    key: str
    label: str
    score: float  # 0..1
    weight: float
    detail: str
    recommendation: str


@dataclass
class Finding:
    id: str
    source: str
    issue_type: str
    estimated_value: float
    confidence: str  # High | Medium | Low
    recommended_action: str


_DEFAULT_PLATFORMS = [
    PlatformConnection("spotify", "Spotify", "Streaming Royalties", 2500.00, "connected"),
    PlatformConnection("apple-music", "Apple Music", "Streaming Royalties", 1234.56, "connected"),
    PlatformConnection("ascap", "ASCAP", "Performance Royalties", 8765.43, "connected"),
    PlatformConnection("bmi", "BMI", "Performance Royalties", 4321.00, "connected"),
    PlatformConnection("sesac", "SESAC", "Performance Royalties", 3120.75, "connected"),
    PlatformConnection("soundexchange", "SoundExchange", "Digital Performance Royalties", 1850.32, "connected"),
    PlatformConnection("the-mlc", "The MLC", "Mechanical Royalties", 940.18, "connected"),
    PlatformConnection("youtube-music", "YouTube Music", "Streaming Royalties", 612.44, "not_connected"),
    PlatformConnection("amazon-music", "Amazon Music", "Streaming Royalties", 430.10, "syncing"),
    PlatformConnection("deezer", "Deezer", "Streaming Royalties", 210.77, "needs_login"),
    PlatformConnection("tidal", "Tidal", "Streaming Royalties", 95.20, "error"),
    PlatformConnection("pandora", "Pandora", "Digital Performance Royalties", 150.00, "not_connected"),
    PlatformConnection("ppl", "PPL", "Performance Royalties", 320.90, "not_connected"),
]

_status_overrides = {}


def get_platform_catalog():
    return [
        replace(p, status=_status_overrides.get(p.id, p.status))
        for p in _DEFAULT_PLATFORMS
    ]


def set_connection_status(platform_id, status):
    entry = next((p for p in _DEFAULT_PLATFORMS if p.id == platform_id), None)
    if entry is None:
        return None
    _status_overrides[platform_id] = status
    return replace(entry, status=status)


def reset_connection_state():
    _status_overrides.clear()


def get_platform_balances():
    return [
        PlatformBalance(p.platform, p.royalty_type, p.amount)
        for p in get_platform_catalog()
        if p.status == "connected"
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


_HEALTH_TRACK_TOTAL = 24
_HEALTH_METADATA_DONE = 20
_HEALTH_SPLITS_DONE = 15
_HEALTH_SCAN_RUN = False


def _plural(n, noun):
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def get_health_factors(catalog):
    connected = sum(1 for p in catalog if p.status == "connected")
    total_platforms = len(catalog)
    tracks = _HEALTH_TRACK_TOTAL
    metadata_gap = tracks - _HEALTH_METADATA_DONE
    splits_gap = tracks - _HEALTH_SPLITS_DONE
    platform_gap = total_platforms - connected

    return [
        HealthFactor(
            key="connections",
            label="Platform connections",
            score=(connected / total_platforms) if total_platforms else 0.0,
            weight=0.30,
            detail=f"{connected} of {total_platforms} platforms connected",
            recommendation=f"Connect {_plural(platform_gap, 'more platform')}",
        ),
        HealthFactor(
            key="metadata",
            label="Metadata completeness",
            score=(_HEALTH_METADATA_DONE / tracks) if tracks else 0.0,
            weight=0.25,
            detail=f"{_HEALTH_METADATA_DONE} of {tracks} tracks have complete metadata",
            recommendation=f"Complete metadata on {_plural(metadata_gap, 'track')}",
        ),
        HealthFactor(
            key="splits",
            label="Split confirmation",
            score=(_HEALTH_SPLITS_DONE / tracks) if tracks else 0.0,
            weight=0.25,
            detail=f"{_HEALTH_SPLITS_DONE} of {tracks} tracks have confirmed splits",
            recommendation=f"Confirm splits on {_plural(splits_gap, 'track')}",
        ),
        HealthFactor(
            key="scan",
            label="Missing royalty scan",
            score=1.0 if _HEALTH_SCAN_RUN else 0.0,
            weight=0.20,
            detail="Scan up to date" if _HEALTH_SCAN_RUN else "No scan run yet",
            recommendation="Run a missing royalties scan",
        ),
    ]


def royalty_health_score(factors):
    total_weight = sum(f.weight for f in factors)
    if total_weight <= 0:
        return 0
    weighted = sum(f.score * f.weight for f in factors)
    return round((weighted / total_weight) * 100)


def get_health_recommendations(factors, limit=3):
    incomplete = sorted(
        (f for f in factors if f.score < 1.0), key=lambda f: f.score
    )
    return incomplete[:limit]


# Deep-scan findings that apply to *connected* sources (shown only when the
# platform is connected, since you can't audit a source you aren't pulling from).
_CONNECTED_FINDINGS = [
    ("spotify", "Unmatched ISRC", 142.50, "Medium", "Submit ISRC correction"),
    ("the-mlc", "Unclaimed mechanical royalties", 318.00, "High", "File a claim"),
    ("ascap", "Missing live performance royalties", 96.25, "Low", "Register setlists"),
]


def _slug(text):
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def get_missing_royalty_findings(catalog):
    findings = []
    by_id = {p.id: p for p in catalog}

    for p in catalog:
        if p.status == "not_connected":
            findings.append(Finding(
                id=f"{p.id}-uncollected",
                source=p.platform,
                issue_type="Uncollected royalties",
                estimated_value=round(p.amount, 2),
                confidence="High" if p.amount >= 300 else "Medium",
                recommended_action=f"Connect {p.platform}",
            ))
        elif p.status == "needs_login":
            findings.append(Finding(
                id=f"{p.id}-login",
                source=p.platform,
                issue_type="Login expired — collections paused",
                estimated_value=round(p.amount * 0.5, 2),
                confidence="Medium",
                recommended_action=f"Re-authenticate {p.platform}",
            ))
        elif p.status == "error":
            findings.append(Finding(
                id=f"{p.id}-sync",
                source=p.platform,
                issue_type="Sync failure",
                estimated_value=round(p.amount, 2),
                confidence="Medium",
                recommended_action=f"Retry {p.platform} sync",
            ))

    for pid, issue, value, confidence, action in _CONNECTED_FINDINGS:
        p = by_id.get(pid)
        if p is not None and p.status == "connected":
            findings.append(Finding(
                id=f"{pid}-{_slug(issue)}",
                source=p.platform,
                issue_type=issue,
                estimated_value=value,
                confidence=confidence,
                recommended_action=action,
            ))

    findings.sort(key=lambda f: f.estimated_value, reverse=True)
    return findings


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

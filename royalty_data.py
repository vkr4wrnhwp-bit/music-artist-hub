from dataclasses import dataclass, replace
from datetime import date, timedelta


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
class Alert:
    id: str
    title: str
    description: str
    severity: str  # High | Medium | Low
    source: str
    estimated_impact: float
    cta_label: str
    resolution_message: str


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


@dataclass
class SplitEntry:
    collaborator: str
    role: str
    percentage: float
    confirmed: bool


@dataclass
class Claim:
    id: str
    source: str
    issue_type: str
    estimated_value: float
    status: str  # Detected | Needs Info | Submitted | In Review | Approved | Paid | Rejected
    recommended_action: str


@dataclass
class Song:
    id: str
    title: str
    isrc: str
    iswc: str
    upc: str
    master_owner: str
    writers: list
    producers: list
    publisher: str
    lyrics_on_file: bool
    alternate_titles: list
    registrations: dict  # distribution|pro|mlc|soundexchange|youtube_content_id|tiktok_meta_rights -> bool
    total_earned: float
    streams: int
    platform_earnings: dict
    splits: list  # list[SplitEntry]
    monthly_trend: list


@dataclass
class ScheduledPayout:
    id: str
    source: str
    amount: float
    pay_date: date
    status: str  # Scheduled | Processing | Delayed | Paid


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
    PlatformConnection("youtube-content-id", "YouTube Content ID", "Sync Royalties", 480.00, "not_connected"),
    PlatformConnection("distrokid", "DistroKid", "Distribution Royalties", 275.40, "connected"),
    PlatformConnection("tunecore", "TuneCore", "Distribution Royalties", 190.15, "not_connected"),
    PlatformConnection("cd-baby", "CD Baby", "Distribution Royalties", 88.60, "not_connected"),
    PlatformConnection("unitedmasters", "UnitedMasters", "Distribution Royalties", 132.75, "not_connected"),
    PlatformConnection("meta", "Meta", "Sync Royalties", 64.20, "not_connected"),
    PlatformConnection("tiktok", "TikTok", "Sync Royalties", 340.90, "syncing"),
    PlatformConnection("twitch", "Twitch", "Streaming Royalties", 41.30, "not_connected"),
    PlatformConnection("bandcamp", "Bandcamp", "Streaming Royalties", 210.00, "connected"),
    PlatformConnection("beatstars", "BeatStars", "Licensing Royalties", 155.50, "not_connected"),
    PlatformConnection("songtrust", "Songtrust", "Publishing Royalties", 265.90, "needs_login"),
    PlatformConnection("harry-fox-agency", "Harry Fox Agency", "Mechanical Royalties", 175.25, "not_connected"),
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


def get_payout_calendar():
    today = date.today()
    entries = [
        ("cal-1", "The MLC", 180.18, -10, "Paid"),
        ("cal-2", "BMI", 340.00, -4, "Delayed"),
        ("cal-3", "Apple Music", 295.75, 2, "Processing"),
        ("cal-4", "Spotify", 410.20, 5, "Scheduled"),
        ("cal-5", "ASCAP", 780.00, 12, "Scheduled"),
        ("cal-6", "SoundExchange", 610.75, 20, "Scheduled"),
        ("cal-7", "SESAC", 520.00, 28, "Scheduled"),
    ]
    payouts = [
        ScheduledPayout(id=eid, source=source, amount=amount, pay_date=today + timedelta(days=offset), status=status)
        for eid, source, amount, offset, status in entries
    ]
    payouts.sort(key=lambda p: p.pay_date)
    return payouts


def upcoming_payout_total(payouts):
    return sum(p.amount for p in payouts if p.status in ("Scheduled", "Processing"))


_SONGS = [
    Song(
        id="midnight-drive",
        title="Midnight Drive",
        isrc="USRC12345678",
        iswc="T-034.524.680-1",
        upc="810012345671",
        master_owner="Synthwave Surfer",
        writers=["Synthwave Surfer", "Jamie Rowe"],
        producers=["Synthwave Surfer"],
        publisher="Street Banker Publishing",
        lyrics_on_file=True,
        alternate_titles=[],
        registrations={
            "distribution": True, "pro": True, "mlc": True,
            "soundexchange": True, "youtube_content_id": True, "tiktok_meta_rights": False,
        },
        total_earned=4120.55,
        streams=5_200_000,
        platform_earnings={"Spotify": 2450.00, "Apple Music": 890.55, "ASCAP": 780.00},
        splits=[
            SplitEntry("Synthwave Surfer", "Writer/Performer", 70.0, True),
            SplitEntry("Jamie Rowe", "Co-Writer", 20.0, True),
            SplitEntry("Street Banker Publishing", "Publisher", 10.0, True),
        ],
        monthly_trend=[520, 610, 700, 780, 820, 890],
    ),
    Song(
        id="neon-dreams",
        title="Neon Dreams",
        isrc="USRC12345679",
        iswc=None,
        upc="810012345672",
        master_owner="Synthwave Surfer",
        writers=["Synthwave Surfer"],
        producers=["Marco Velocity"],
        publisher="Street Banker Publishing",
        lyrics_on_file=True,
        alternate_titles=["Neon Dreams (Extended Mix)"],
        registrations={
            "distribution": True, "pro": True, "mlc": False,
            "soundexchange": True, "youtube_content_id": False, "tiktok_meta_rights": False,
        },
        total_earned=2340.10,
        streams=3_100_000,
        platform_earnings={"Apple Music": 1234.56, "Spotify": 1105.54},
        splits=[
            SplitEntry("Synthwave Surfer", "Writer/Performer", 60.0, True),
            SplitEntry("Marco Velocity", "Producer", 40.0, False),
        ],
        monthly_trend=[310, 340, 360, 400, 410, 430],
    ),
    Song(
        id="city-lights",
        title="City Lights",
        isrc=None,
        iswc=None,
        upc=None,
        master_owner="Synthwave Surfer",
        writers=["Synthwave Surfer", "Lila Rose"],
        producers=[],
        publisher=None,
        lyrics_on_file=False,
        alternate_titles=[],
        registrations={
            "distribution": True, "pro": False, "mlc": False,
            "soundexchange": False, "youtube_content_id": False, "tiktok_meta_rights": False,
        },
        total_earned=350.00,
        streams=980_000,
        platform_earnings={"ASCAP": 350.00},
        splits=[
            SplitEntry("Synthwave Surfer", "Writer/Performer", 50.0, False),
            SplitEntry("Lila Rose", "Featured Vocalist", 50.0, False),
        ],
        monthly_trend=[40, 55, 60, 70, 62, 63],
    ),
    Song(
        id="digital-paradise",
        title="Digital Paradise",
        isrc="USRC12345680",
        iswc="T-034.524.681-2",
        upc="810012345673",
        master_owner="Synthwave Surfer",
        writers=["Synthwave Surfer"],
        producers=["Synthwave Surfer", "DJ Codec"],
        publisher="Street Banker Publishing",
        lyrics_on_file=False,
        alternate_titles=[],
        registrations={
            "distribution": True, "pro": True, "mlc": True,
            "soundexchange": True, "youtube_content_id": True, "tiktok_meta_rights": True,
        },
        total_earned=1980.75,
        streams=2_500_000,
        platform_earnings={"Spotify": 980.00, "SoundExchange": 620.75, "BMI": 380.00},
        splits=[
            SplitEntry("Synthwave Surfer", "Writer/Performer", 100.0, True),
        ],
        monthly_trend=[260, 280, 300, 330, 340, 350],
    ),
    Song(
        id="velvet-static",
        title="Velvet Static",
        isrc=None,
        iswc=None,
        upc=None,
        master_owner="Synthwave Surfer",
        writers=[],
        producers=[],
        publisher=None,
        lyrics_on_file=False,
        alternate_titles=["Velvet Static (Demo)"],
        registrations={
            "distribution": False, "pro": False, "mlc": False,
            "soundexchange": False, "youtube_content_id": False, "tiktok_meta_rights": False,
        },
        total_earned=95.20,
        streams=210_000,
        platform_earnings={"Tidal": 95.20},
        splits=[],
        monthly_trend=[10, 12, 15, 14, 18, 20],
    ),
]


def get_songs():
    return list(_SONGS)


def get_song(song_id):
    return next((s for s in _SONGS if s.id == song_id), None)


def split_total_percentage(song):
    return sum(s.percentage for s in song.splits)


def splits_fully_confirmed(song):
    return bool(song.splits) and all(s.confirmed for s in song.splits)


_METADATA_CHECK_KEYS = [
    "isrc", "iswc", "upc", "writers", "producers", "publisher",
    "pro", "mlc", "soundexchange", "lyrics", "alternate_titles",
]

_REGISTRATION_CHECK_KEYS = [
    "distribution", "isrc", "upc", "pro", "publisher",
    "mlc", "soundexchange", "youtube_content_id", "tiktok_meta_rights", "split_confirmation",
]


def song_check_status(song):
    """Single source of truth: every checklist item this song could be scored on."""
    return {
        "isrc": bool(song.isrc),
        "iswc": bool(song.iswc),
        "upc": bool(song.upc),
        "writers": bool(song.writers),
        "producers": bool(song.producers),
        "publisher": bool(song.publisher),
        "lyrics": song.lyrics_on_file,
        "alternate_titles": bool(song.alternate_titles),
        "distribution": song.registrations.get("distribution", False),
        "pro": song.registrations.get("pro", False),
        "mlc": song.registrations.get("mlc", False),
        "soundexchange": song.registrations.get("soundexchange", False),
        "youtube_content_id": song.registrations.get("youtube_content_id", False),
        "tiktok_meta_rights": song.registrations.get("tiktok_meta_rights", False),
        "split_confirmation": splits_fully_confirmed(song),
    }


def song_missing_issues(song):
    status = song_check_status(song)
    labels = {
        "isrc": "Missing ISRC", "iswc": "Missing ISWC", "upc": "Missing UPC",
        "writers": "No writers on file", "producers": "No producers on file",
        "publisher": "No publisher on file", "lyrics": "Lyrics not on file",
        "alternate_titles": "No alternate titles logged",
        "distribution": "Not registered with a distributor", "pro": "Not registered with a PRO",
        "mlc": "Not registered with The MLC", "soundexchange": "Not registered with SoundExchange",
        "youtube_content_id": "Not registered with YouTube Content ID",
        "tiktok_meta_rights": "TikTok/Meta rights not secured",
        "split_confirmation": "Splits not fully confirmed",
    }
    return [labels[key] for key, ok in status.items() if not ok]


def metadata_completion_score(song):
    status = song_check_status(song)
    checks = [status[k] for k in _METADATA_CHECK_KEYS]
    return sum(checks) / len(checks)


def registration_checklist_score(song):
    status = song_check_status(song)
    checks = [status[k] for k in _REGISTRATION_CHECK_KEYS]
    return sum(checks) / len(checks)


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


CLAIM_PIPELINE = ["Detected", "Needs Info", "Submitted", "In Review", "Approved", "Paid"]

_claim_status_overrides = {}


def get_claims(catalog):
    findings = get_missing_royalty_findings(catalog)
    claims = [
        Claim(
            id=f.id,
            source=f.source,
            issue_type=f.issue_type,
            estimated_value=f.estimated_value,
            status=_claim_status_overrides.get(f.id, "Detected"),
            recommended_action=f.recommended_action,
        )
        for f in findings
    ]
    claims.sort(key=lambda c: c.estimated_value, reverse=True)
    return claims


def advance_claim(claim_id, catalog):
    findings = get_missing_royalty_findings(catalog)
    if not any(f.id == claim_id for f in findings):
        return None
    current = _claim_status_overrides.get(claim_id, "Detected")
    if current in ("Paid", "Rejected"):
        return current
    idx = CLAIM_PIPELINE.index(current)
    new_status = CLAIM_PIPELINE[min(idx + 1, len(CLAIM_PIPELINE) - 1)]
    _claim_status_overrides[claim_id] = new_status
    return new_status


def reject_claim(claim_id, catalog):
    findings = get_missing_royalty_findings(catalog)
    if not any(f.id == claim_id for f in findings):
        return None
    current = _claim_status_overrides.get(claim_id, "Detected")
    if current == "Paid":
        return current
    _claim_status_overrides[claim_id] = "Rejected"
    return "Rejected"


def reset_claim_state():
    _claim_status_overrides.clear()


_SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def get_royalty_leak_alerts(balances, payouts, kpis, catalog):
    alerts = []

    for p in catalog:
        if p.status == "needs_login":
            alerts.append(Alert(
                id=f"{p.id}-needs-login",
                title=f"{p.platform} login expired",
                description="Collections are paused until you re-authenticate this connection.",
                severity="High",
                source=p.platform,
                estimated_impact=round(p.amount * 0.5, 2),
                cta_label="Re-authenticate",
                resolution_message=f"Re-authenticated {p.platform}. Collections resumed.",
            ))
        elif p.status == "error":
            alerts.append(Alert(
                id=f"{p.id}-sync-error",
                title=f"{p.platform} sync failure",
                description="This platform hasn't synced successfully — royalties may be going uncounted.",
                severity="High",
                source=p.platform,
                estimated_impact=round(p.amount, 2),
                cta_label="Retry Sync",
                resolution_message=f"Resynced {p.platform} successfully.",
            ))
        elif p.status == "not_connected":
            alerts.append(Alert(
                id=f"{p.id}-not-connected",
                title=f"{p.platform} isn't connected",
                description="Estimated royalties are going uncollected on this platform.",
                severity="Medium" if p.amount >= 250 else "Low",
                source=p.platform,
                estimated_impact=round(p.amount, 2),
                cta_label="Connect Platform",
                resolution_message=f"Connected {p.platform}.",
            ))

    processing_payout = next((x for x in payouts if x.status == "Processing"), None)
    if processing_payout is not None:
        alerts.append(Alert(
            id=f"payout-{_slug(processing_payout.song)}",
            title=f'"{processing_payout.song}" payout delayed',
            description=(
                f"${processing_payout.amount:.2f} from {processing_payout.platform} "
                "is still processing."
            ),
            severity="Medium",
            source=processing_payout.platform,
            estimated_impact=round(processing_payout.amount, 2),
            cta_label="Send Follow-Up",
            resolution_message=(
                f'Sent a follow-up to {processing_payout.platform} about '
                f'"{processing_payout.song}".'
            ),
        ))

    pending_kpi = next((k for k in kpis if "pending" in k.delta_label.lower()), None)
    if pending_kpi is not None:
        alerts.append(Alert(
            id="pending-negotiation",
            title=f"{pending_kpi.label} needs review",
            description=f"{pending_kpi.delta_label}.",
            severity="Low",
            source="Internal",
            estimated_impact=0.0,
            cta_label="Review Negotiation",
            resolution_message="Marked the pending negotiation for review.",
        ))

    if not alerts:
        alerts.append(Alert(
            id="scan",
            title="No active leaks detected",
            description="Run a scan periodically to catch new issues early.",
            severity="Low",
            source="System",
            estimated_impact=0.0,
            cta_label="Scan Now",
            resolution_message="Scan complete — no new missing royalties found this time.",
        ))

    alerts.sort(key=lambda a: (_SEVERITY_ORDER.get(a.severity, 3), -a.estimated_impact))
    return alerts

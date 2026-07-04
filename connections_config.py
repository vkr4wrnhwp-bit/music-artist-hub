"""Mock data + config for the Connections command center (Flask
equivalent of the spec's mockConnectionsData.js). All page content --
summary metrics, gap breakdown, source rows, opportunities, and recent
activity -- comes from here so the template stays content-free.
"""

CONNECTION_TABS = [
    "All Sources", "Audio Streaming", "Performance",
    "Mechanical", "YouTube & Social", "Distributors",
]

STATUS_OPTIONS = [
    "All Statuses", "Connected", "Partial Connection", "Not Connected",
    "Invite Sent", "Needs Login", "Sync Error", "Action Required",
]
CATEGORY_OPTIONS = [
    "All Categories", "Audio Streaming", "Performance", "Mechanical",
    "YouTube & Social", "Distributor", "Publishing Admin",
    "Neighboring Rights", "Direct Sales",
]

# status -> (tone, sparkline stroke)
STATUS_TONE = {
    "Connected": "green",
    "Partial Connection": "amber",
    "Not Connected": "red",
    "Invite Sent": "gold",
    "Needs Login": "amber",
    "Sync Error": "red",
    "Action Required": "amber",
}
SPARK_COLOR = {"green": "#22c55e", "amber": "#eab308", "red": "#ef4444", "gold": "#eab308"}

# status -> the modal/drawer the Action button opens
STATUS_ACTION = {
    "Connected": {"label": "Manage", "type": "manage"},
    "Partial Connection": {"label": "Fix Gaps", "type": "fix_gaps"},
    "Not Connected": {"label": "Connect", "type": "add_connection"},
    "Invite Sent": {"label": "Resend Invite", "type": "invite"},
    "Needs Login": {"label": "Reconnect", "type": "reconnect"},
    "Sync Error": {"label": "Reconnect", "type": "reconnect"},
    "Action Required": {"label": "Fix Gaps", "type": "fix_gaps"},
}


def _sources():
    return [
        {"id": "source_spotify", "name": "Spotify", "logo": "spotify",
         "sublabel": "Audio Streaming", "category": "Audio Streaming",
         "status": "Connected", "status_detail": "Live Data",
         "last_data": "May 31, 2025", "last_relative": "2 hours ago",
         "unit": "tracks", "count": 2842, "amount": 1240.32,
         "sparkline": [12, 18, 14, 21, 19, 26, 31], "issues": [], "missing": 0},
        {"id": "source_apple_music", "name": "Apple Music", "logo": "apple",
         "sublabel": "Audio Streaming", "category": "Audio Streaming",
         "status": "Connected", "status_detail": "Live Data",
         "last_data": "May 31, 2025", "last_relative": "1 hour ago",
         "unit": "tracks", "count": 1921, "amount": 982.45,
         "sparkline": [10, 13, 17, 12, 20, 22, 28], "issues": [], "missing": 0},
        {"id": "source_ascap", "name": "ASCAP", "logo": "ascap",
         "sublabel": "Performance Rights", "category": "Performance",
         "status": "Connected", "status_detail": "Live Data",
         "last_data": "May 30, 2025", "last_relative": "5 hours ago",
         "unit": "works", "count": 892, "amount": 642.18,
         "sparkline": [8, 12, 11, 17, 13, 19, 22], "issues": [], "missing": 0},
        {"id": "source_bmi", "name": "BMI", "logo": "bmi",
         "sublabel": "Performance Rights", "category": "Performance",
         "status": "Connected", "status_detail": "Live Data",
         "last_data": "May 30, 2025", "last_relative": "3 hours ago",
         "unit": "works", "count": 1203, "amount": 784.10,
         "sparkline": [9, 14, 18, 12, 16, 20, 25], "issues": [], "missing": 0},
        {"id": "source_mlc", "name": "The MLC", "logo": "mlc",
         "sublabel": "Mechanical Licensing", "category": "Mechanical",
         "status": "Partial Connection", "status_detail": "Gaps Detected",
         "last_data": "May 29, 2025", "last_relative": "1 day ago",
         "unit": "recordings", "count": 634, "amount": 308.45,
         "sparkline": [5, 9, 7, 13, 10, 15, 17],
         "issues": [
             {"title": "Unmatched recordings found", "severity": "warning"},
             {"title": "3 works need registration", "severity": "warning"},
         ], "missing": 950},
        {"id": "source_soundexchange", "name": "SoundExchange", "logo": "soundexchange",
         "sublabel": "Performance Royalties", "category": "Performance",
         "status": "Not Connected", "status_detail": "No Data",
         "last_data": None, "last_relative": "Never",
         "unit": "tracks", "count": 0, "amount": 0.0,
         "sparkline": [0, 0, 0, 0, 0, 0, 0],
         "issues": [
             {"title": "Source not connected", "severity": "critical"},
             {"title": "Performance royalties may be missing", "severity": "warning"},
         ], "missing": 1200},
        {"id": "source_youtube_content_id", "name": "YouTube Content ID", "logo": "youtube",
         "sublabel": "YouTube & Social", "category": "YouTube & Social",
         "status": "Connected", "status_detail": "Live Data",
         "last_data": "May 31, 2025", "last_relative": "30 min ago",
         "unit": "tracks", "count": 935, "amount": 215.60,
         "sparkline": [6, 8, 7, 12, 16, 15, 21], "issues": [], "missing": 0},
        {"id": "source_tiktok_soundon", "name": "TikTok SoundOn", "logo": "tiktok",
         "sublabel": "YouTube & Social", "category": "YouTube & Social",
         "status": "Invite Sent", "status_detail": "Pending",
         "last_data": "May 28, 2025", "last_relative": "3 days ago",
         "unit": "tracks", "count": 0, "amount": 0.0,
         "sparkline": [0, 1, 0, 1, 0, 1, 0],
         "issues": [{"title": "Invite pending", "severity": "warning"}], "missing": 300},
    ]


def get_connections_data():
    sources = _sources()
    for s in sources:
        s["tone"] = STATUS_TONE.get(s["status"], "amber")
        s["spark_color"] = SPARK_COLOR[s["tone"]]
        s["action"] = STATUS_ACTION.get(s["status"], STATUS_ACTION["Connected"])

    summary = {
        "connection_health": 84,
        "connection_health_status": "Good",
        "connected_sources": 24,
        "total_sources": 32,
        "active_data_flows": 47,
        "missing_royalties_found": 4820,
        "potential_yearly_value": 28650,
    }
    summary["connected_pct"] = round(summary["connected_sources"] / summary["total_sources"] * 100)

    gaps = {
        "total": 7,
        "breakdown": [
            {"label": "Not Connected", "count": 3, "tone": "red"},
            {"label": "Partial Connection", "count": 2, "tone": "amber"},
            {"label": "Action Required", "count": 2, "tone": "gold"},
            {"label": "All Good", "count": 24, "tone": "green"},
        ],
    }

    opportunities = [
        {"id": "opp_001", "title": "Connect SoundExchange", "logo": "soundexchange",
         "description": "Performance royalties missing", "source": "SoundExchange",
         "estimated_value": 1200, "cta": "Connect", "action_type": "add_connection"},
        {"id": "opp_002", "title": "Fix MLC Gaps", "logo": "mlc",
         "description": "Unmatched recordings found", "source": "The MLC",
         "estimated_value": 950, "cta": "Fix", "action_type": "fix_gaps"},
        {"id": "opp_003", "title": "Complete Split Data", "logo": "other",
         "description": "7 tracks with split conflicts", "source": "Catalog",
         "estimated_value": 640, "cta": "Review", "action_type": "review_splits"},
    ]

    recent_activity = [
        {"id": "act_001", "title": "Spotify data received", "source": "Spotify",
         "timestamp": "2 hours ago", "status": "success"},
        {"id": "act_002", "title": "Apple Music data received", "source": "Apple Music",
         "timestamp": "1 hour ago", "status": "success"},
        {"id": "act_003", "title": "ASCAP statement generated", "source": "ASCAP",
         "timestamp": "5 hours ago", "status": "info"},
        {"id": "act_004", "title": "MLC gaps detected", "source": "The MLC",
         "timestamp": "1 day ago", "status": "warning"},
    ]

    return {
        "summary": summary,
        "gaps": gaps,
        "sources": sources,
        "opportunities": opportunities,
        "recent_activity": recent_activity,
        "tabs": CONNECTION_TABS,
        "status_options": STATUS_OPTIONS,
        "category_options": CATEGORY_OPTIONS,
    }

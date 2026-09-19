"""Config-driven data for the Reports page.

Composes the report library (grouped by category), a KPI summary, the
live "recently generated" history, and the illustrative scheduled-report
list into a single dict the template renders with zero hard-coded content.
"""

from royalty_data import (
    REPORT_CATEGORY_ORDER,
    get_available_reports,
    get_report_history,
    get_scheduled_reports,
)

CATEGORY_TONE = {
    "Financial": "border-amber-500/20 bg-amber-500/10 text-amber-400",
    "Recovery": "border-green-500/20 bg-green-500/10 text-green-400",
    "Rights": "border-blue-500/20 bg-blue-500/10 text-blue-400",
    "Investor": "border-purple-500/20 bg-purple-500/10 text-purple-400",
}

# Badge tones of the shared instrument set (sb.badge), not hand-rolled
# colour classes (audit, 2026-09-15).
FORMAT_TONE = {
    "PDF": "crit",
    "CSV": "good",
    "XLSX": "good",
}


# The signed-in account's own report cards: (title, description, href,
# kind). They sit above the library on the page, so they live here too and
# the "Report Types" tile can count every card the page actually shows.
# It counted the library's six while the page drew twelve (owner notes,
# 2026-09-19).
REAL_REPORTS = [
    ("Executive Report", "Qualification, royalty findings, campaigns, and fan ownership in one partner-ready document.", "/reports/executive", "Print / PDF"),
    ("Campaign Performance", "Every campaign with visits, clicks, CTR, captures, and SB score.", "/reports/campaigns.csv", "CSV"),
    ("Recovery Findings", "Unmatched revenue and coverage gaps from your uploaded statements.", "/reports/recovery.csv", "CSV"),
    ("Fan CRM Export", "Owned fans with consent status and intent scores.", "/links/fans/export.csv", "CSV"),
    ("Royalty Rows", "Raw parsed statement rows for accounting.", "/reports/royalty-report/download.csv", "CSV"),
    # The one-sheet is the EPK (owner, 2026-09-19: "It just needs to be an
    # EPK. The EPK goes to the vault."); saved copies live in the Vault.
    ("Press Kit (EPK)", "The one document you send: bio, photos, tracks, measured figures, and the For deals section when it is on. Save to Vault files a dated copy.", "/epk", "Web page / print"),
]


def get_reports_data(user_id, demo=False):
    """`demo` decides whether the example saved schedules are included.

    `user_id` decides whose "generated this session" log comes back. It
    used to come back unconditionally from a process-global list, so
    every Pro account was shown every other account's report labels,
    filenames and dates. It comes first and has no default so a call site
    that forgets it raises here instead of quietly serving the whole
    box's; passing None is the deliberate signed-out case and returns no
    rows.

    There is no scheduler behind them. Nothing runs monthly, nothing is
    emailed to "2 recipients", and the next-run dates are literals - the
    same three rows for every account, under a heading that reads as
    configuration the artist set up themselves. Real accounts get an
    empty list, and the page says the scheduler is not built yet rather
    than showing three jobs that will never run.
    """
    reports = get_available_reports()
    history = get_report_history(user_id)
    scheduled = get_scheduled_reports() if demo else []

    # Group the library by category, preserving the canonical order.
    grouped = {}
    for r in reports:
        grouped.setdefault(r["category"], []).append(r)
    categories = [
        {
            "name": name,
            "tone": CATEGORY_TONE.get(name, CATEGORY_TONE["Financial"]),
            "reports": grouped[name],
        }
        for name in REPORT_CATEGORY_ORDER
        if name in grouped
    ]

    formats = sorted({r["format"] for r in reports})
    # Only a signed-in account is shown its own cards.
    real = list(REAL_REPORTS) if user_id else []

    # The "Generated This Session" tile is gone. The log it counted lives
    # in one server process's memory per account (royalty_data
    # _report_history): not this session, cleared by every deploy, and
    # possibly different between the two web workers. It also drew a 0
    # on most visits (owner, 2026-09-15: "if a card shows 0 it needs to
    # not show up"). The list below it says what it is instead.
    return {
        "summary": {
            "total_reports": len(reports),
            # Every report card the page draws: the account's own above
            # the library.
            "cards_shown": len(reports) + len(real),
            "categories": len(categories),
            "scheduled_active": sum(1 for s in scheduled if s["enabled"]),
        },
        "real_reports": real,
        "categories": categories,
        "scheduled": scheduled,
        "recent": history,
        "formats": formats,
        "format_tone": FORMAT_TONE,
    }

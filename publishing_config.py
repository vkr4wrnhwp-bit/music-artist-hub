"""Config-driven data for the Publishing Administration page.

Publishing royalties split into two streams: performance (collected by
PROs like ASCAP/BMI) and mechanical (collected by the MLC for US
streaming). This composes a per-composition ("work") view from the live
song catalog -- PRO/MLC registration status, ISWC presence, writers,
publisher -- plus performance income already showing in platform
earnings and an illustrative estimate of mechanicals left uncollected
where a work isn't registered. Estimates are marked; registration
status and performance income are real, derived from the catalog.
"""

from royalty_data import get_songs

# Sources whose earnings represent performance royalties (PRO income).
_PRO_SOURCES = {"ASCAP", "BMI", "SESAC", "PRS", "SOCAN", "GEMA"}

# Illustrative shares used only where the app doesn't track the figure
# directly: mechanicals aren't line-itemed, so we estimate them as a
# fraction of a work's total earnings, and estimate uncollected income
# for works missing PRO/MLC registration.
_MECHANICAL_SHARE = 0.12
_PERFORMANCE_UNCOLLECTED_SHARE = 0.10


def _work_from_song(song):
    performance_income = sum(
        amt for src, amt in (song.platform_earnings or {}).items() if src in _PRO_SOURCES
    )
    mechanical_estimate = round(song.total_earned * _MECHANICAL_SHARE, 2)

    pro_registered = bool(song.registrations.get("pro"))
    mlc_registered = bool(song.registrations.get("mlc"))
    iswc_missing = not song.iswc

    # Uncollected = the streams a work can't collect on because it isn't
    # registered with the relevant society.
    uncollected = 0.0
    if not mlc_registered:
        uncollected += mechanical_estimate
    if not pro_registered:
        uncollected += round(song.total_earned * _PERFORMANCE_UNCOLLECTED_SHARE, 2)

    if iswc_missing or not pro_registered or not mlc_registered:
        status = "Action Needed"
    else:
        status = "Fully Registered"

    return {
        "id": song.id,
        "title": song.title,
        "writers": song.writers,
        "publisher": song.publisher,
        "iswc": song.iswc or "Not assigned",
        "iswc_missing": iswc_missing,
        "pro_registered": pro_registered,
        "mlc_registered": mlc_registered,
        "performance_income": round(performance_income, 2),
        "mechanical_estimate": mechanical_estimate,
        "uncollected": round(uncollected, 2),
        "status": status,
    }


def get_publishing_data():
    works = [_work_from_song(s) for s in get_songs()]

    pro_registered = sum(1 for w in works if w["pro_registered"])
    mlc_registered = sum(1 for w in works if w["mlc_registered"])
    performance_total = round(sum(w["performance_income"] for w in works), 2)
    mechanical_total = round(sum(w["mechanical_estimate"] for w in works), 2)
    uncollected_total = round(sum(w["uncollected"] for w in works), 2)

    issues = [
        {"label": "Missing ISWC", "count": sum(1 for w in works if w["iswc_missing"]), "tone": "amber"},
        {"label": "Unregistered with PRO", "count": sum(1 for w in works if not w["pro_registered"]), "tone": "red"},
        {"label": "Not registered with the MLC", "count": sum(1 for w in works if not w["mlc_registered"]), "tone": "red"},
    ]

    total = len(works) or 1
    return {
        "summary": {
            "total_works": len(works),
            "pro_registered": pro_registered,
            "mlc_registered": mlc_registered,
            "pro_pct": round(pro_registered / total * 100),
            "mlc_pct": round(mlc_registered / total * 100),
            "performance_total": performance_total,
            "mechanical_total": mechanical_total,
            "uncollected_total": uncollected_total,
        },
        "works": works,
        "issues": issues,
    }

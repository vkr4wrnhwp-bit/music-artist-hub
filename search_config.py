"""Global search across the app's real data — songs, connected sources,
claims, and disputes. Returns results grouped by type with a link to the
relevant page, so search is a fast way to jump anywhere.
"""

from royalty_data import get_songs, get_platform_catalog, get_claims
from disputes_config import get_disputes_data


def search(query):
    q = (query or "").strip().lower()
    groups = []
    if not q:
        return {"query": "", "groups": [], "total": 0}

    # Songs (title / ISRC / writers).
    song_hits = []
    for s in get_songs():
        hay = " ".join([s.title, s.isrc or "", s.iswc or "", " ".join(s.writers)]).lower()
        if q in hay:
            song_hits.append({"label": s.title, "sub": "Song · " + (s.isrc or "no ISRC"), "route": "/catalog"})
    if song_hits:
        groups.append({"type": "Songs", "items": song_hits})

    # Connected sources / platforms.
    catalog = get_platform_catalog()
    source_hits = [
        {"label": p.platform, "sub": "Source · " + p.status.replace("_", " "), "route": "/connections"}
        for p in catalog if q in p.platform.lower()
    ]
    if source_hits:
        groups.append({"type": "Sources", "items": source_hits})

    # Claims.
    claim_hits = [
        {"label": c.issue_type, "sub": "Claim · " + c.source, "route": "/recovery"}
        for c in get_claims(catalog)
        if q in c.issue_type.lower() or q in c.source.lower()
    ]
    if claim_hits:
        groups.append({"type": "Claims", "items": claim_hits})

    # Disputes.
    dispute_hits = [
        {"label": d["title"], "sub": "Dispute · " + d["counterparty"], "route": "/disputes"}
        for d in get_disputes_data()["disputes"]
        if q in d["title"].lower() or q in d["counterparty"].lower() or (d.get("song") and q in d["song"].lower())
    ]
    if dispute_hits:
        groups.append({"type": "Disputes", "items": dispute_hits})

    total = sum(len(g["items"]) for g in groups)
    return {"query": query, "groups": groups, "total": total}

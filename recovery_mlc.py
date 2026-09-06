"""Recovery, asked of The MLC.

Every ISRC on a Track Passport, checked against The MLC's public database
when the artist presses the button: the work the registry links it to and
how much of that work is claimed, or nothing linked at all - which, for a
released recording, is mechanical money nobody is collecting. Every sweep
is kept whole, answers and errors alike, so the page can say when it last
ran and what it said. Nothing here registers, claims or changes anything
on the artist's behalf; a case is opened only when they press that.

Only an ISRC is asked about. A title match proves a work of that name
exists, not that this recording is registered, so passports without an
ISRC are listed as unable to be checked rather than guessed at.
"""
import db as store
import signal_providers as providers

PER_SWEEP = 25        # bounded: their limits are not published


def candidates(user_id):
    """(ready, missing): passports with an ISRC, and those without one."""
    ready, missing, seen = [], [], set()
    for t in store.list_os_tracks(user_id):
        p = t.get("passport") or {}
        isrc = (p.get("isrc") or "").strip().upper().replace("-", "")
        row = {"track_id": t["id"], "title": t["title"],
               "artist": (p.get("artist_name") or "").strip(), "isrc": isrc}
        if not isrc:
            missing.append(row)
        elif isrc not in seen:
            seen.add(isrc)
            ready.append(row)
    return ready, missing


def sweep(user_id, adapter=None):
    """Ask about every ready ISRC (up to PER_SWEEP), keep the sweep, return its id."""
    adapter = adapter or providers.mlc_adapter()
    ready, _missing = candidates(user_id)
    rows = []
    for c in ready[:PER_SWEEP]:
        row = dict(c, result="none", song_code="", iswc="", share_total=0.0,
                   writers=0, publishers=0, message="")
        try:
            works = adapter.lookup(isrc=c["isrc"])["works"]
        except providers.ProviderError as e:
            row["result"], row["message"] = "error", str(e)
            rows.append(row)
            continue
        if works:
            w = works[0]
            row.update(result="match", song_code=w.get("song_code") or "",
                       iswc=w.get("iswc") or "", share_total=float(w.get("share_total") or 0),
                       writers=len(w.get("writers") or []),
                       publishers=len(w.get("publishers") or []))
        rows.append(row)
    summary = {
        "checked": len(rows),
        "matched": sum(1 for r in rows if r["result"] == "match" and r["share_total"] >= 99.5),
        "partial": sum(1 for r in rows if r["result"] == "match" and r["share_total"] < 99.5),
        "unmatched": sum(1 for r in rows if r["result"] == "none"),
        "errors": sum(1 for r in rows if r["result"] == "error"),
        "skipped": max(0, len(ready) - PER_SWEEP),
    }
    return store.add_recovery_mlc_sweep(user_id, summary, rows)


def _case_for(row):
    if row["result"] == "none":
        return ("Unmatched at The MLC: %s (%s)" % (row["title"], row["isrc"]),
                "The MLC has no work linked to ISRC %s for \"%s\". Register the work at "
                "The MLC, then check again." % (row["isrc"], row["title"]))
    if row["result"] == "match" and row["share_total"] < 99.5:
        return ("Partly claimed at The MLC: %s (%s)" % (row["title"], row["isrc"]),
                "The MLC links ISRC %s to song code %s with %g%% of the work claimed. "
                "Claim the missing share." % (row["isrc"], row["song_code"], row["share_total"]))
    return ("", "")


def state(user_id):
    """What the Recovery page may say: connected or not, what a sweep would
    ask, the latest sweep with a case offered on every gap."""
    ready, missing = candidates(user_id)
    latest = store.latest_recovery_mlc_sweep(user_id)
    if latest:
        titles = {(c.get("title") or "").strip().lower() for c in store.list_recovery_cases(user_id)}
        for row in latest["rows"]:
            row["case_title"], row["case_note"] = _case_for(row)
            row["gap"] = bool(row["case_title"])
            row["has_case"] = row["case_title"].strip().lower() in titles if row["case_title"] else False
    return {"on": providers.mlc_adapter().configured(), "ready": ready, "missing": missing,
            "latest": latest, "per_sweep": PER_SWEEP}

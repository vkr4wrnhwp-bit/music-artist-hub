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

A case opened from a gap carries a measured figure rather than a zero:
money this title has already earned in the owner's own statements, and
for a partly claimed work the unclaimed fraction of that. It is not
money The MLC owes - nothing here can know that - and the note on every
case says which rows the figure came from.
"""
import db as store
import royalty_types
import signal_providers as providers

PER_SWEEP = 25        # bounded: their limits are not published

# The statement lanes a mechanical gap is about.
LANES = ("mechanical", "publishing")
NO_ROWS = "No statement rows for this title yet."


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


def earnings_by_title(user_id):
    """What each title has already earned in the owner's own statements.

    Two figures per title. `lanes` is what its mechanical and publishing
    rows paid - the money a mechanical gap is actually about - and `total`
    is every stream on it. A catalogue whose statements never name a
    mechanical or publishing source has no lane figure, and the case says
    which of the two it used rather than passing a streaming total off as
    a mechanical one.
    """
    out = {}
    for r in store.get_statement_rows(user_id):
        title = (r.get("title") or "").strip().lower()
        if not title:
            continue
        money = out.setdefault(title, {"lanes": 0.0, "total": 0.0})
        amount = float(r.get("amount") or 0)
        money["total"] += amount
        if royalty_types.classify(r.get("source")) in LANES:
            money["lanes"] += amount
    return out


def _cash(value):
    return "$%s" % "{:,.2f}".format(value)


def _earned(money):
    """(amount, what that amount is) for one title's statement rows."""
    if not money:
        return 0.0, ""
    if money["lanes"] > 0:
        return round(money["lanes"], 2), "its mechanical and publishing rows"
    if money["total"] > 0:
        return (round(money["total"], 2),
                "every stream on it, since no row names a mechanical "
                "or publishing source")
    return 0.0, ""


def _case_for(row, money=None):
    """What a case opened from this row would carry, or blanks if it is no gap.

    `title` and `note` go on the case; `amount` is the measured figure the
    case is opened with; `figure` and `caption` are what the sweep partial
    shows beside the row. Nothing here is invented: with no statement rows
    for the title the amount stays 0 and the note says why.

    `key` is what the gap *is*, so the route can refuse to open it twice:
    the ISRC the registry has no work for, or the song code it only partly
    claims. Not the title - two recordings can share one, and the title
    changes the moment the sweep's answer does. A partly claimed work that
    came back without a song code falls back to its ISRC, which is then the
    only identifying fact it has.
    """
    blank = {"title": "", "note": "", "amount": 0.0, "figure": None,
             "caption": "", "key": ""}
    earned, basis = _earned(money)
    if row["result"] == "none":
        note = 'The MLC has no work linked to ISRC %s for "%s". ' % (row["isrc"], row["title"])
        if earned:
            note += ("%s has already been earned by this title in your own statements "
                     "(%s), and the work behind it is unregistered - so the whole "
                     "mechanical share of that money is at risk. This is not money "
                     "The MLC owes. " % (_cash(earned), basis))
            caption = "already earned, work unregistered"
        else:
            note += NO_ROWS + " "
            caption = NO_ROWS.rstrip(".").lower()
        return {"title": "Unmatched at The MLC: %s (%s)" % (row["title"], row["isrc"]),
                "note": note + "Register the work at The MLC, then check again.",
                "amount": earned,
                "figure": _cash(earned) if earned else None,
                "caption": caption,
                "key": "mlc:isrc:%s" % row["isrc"]}
    if row["result"] == "match" and row["share_total"] < 99.5:
        unclaimed = max(0.0, 100.0 - row["share_total"])
        amount = round(earned * unclaimed / 100.0, 2)
        note = ("The MLC links ISRC %s to song code %s with %g%% of the work claimed, "
                "so %g%% is unclaimed. " % (row["isrc"], row["song_code"],
                                            row["share_total"], unclaimed))
        if earned:
            note += ("%s is %g%% of the %s this title has already earned in your own "
                     "statements (%s) - a share of what it has earned, not a promise "
                     "of what will be paid. " % (_cash(amount), unclaimed,
                                                 _cash(earned), basis))
            caption = "%g%% unclaimed share of %s earned" % (unclaimed, _cash(earned))
        else:
            note += NO_ROWS + " "
            caption = NO_ROWS.rstrip(".").lower()
        return {"title": "Partly claimed at The MLC: %s (%s)" % (row["title"], row["isrc"]),
                "note": note + "Claim the missing share.",
                "amount": amount,
                "figure": _cash(amount) if amount else None,
                "caption": caption,
                "key": ("mlc:song:%s" % row["song_code"] if row["song_code"]
                        else "mlc:isrc:%s" % row["isrc"])}
    return blank


def attach_earnings(view, top_tracks):
    """Mark each sweep row with what its title earns in a stream, by title.
    A title match is a hint for the eye, not an identity claim, so it only
    decorates rows the registry already answered about."""
    earning = {(title or "").strip().lower(): amt for title, amt in (top_tracks or [])}
    for row in ((view or {}).get("latest") or {}).get("rows") or []:
        row["earning"] = earning.get((row.get("title") or "").strip().lower())
    return view


def state(user_id):
    """What the Recovery page may say: connected or not, what a sweep would
    ask, the latest sweep with a case offered on every gap - each carrying
    the measured figure that gap is worth."""
    ready, missing = candidates(user_id)
    latest = store.latest_recovery_mlc_sweep(user_id)
    if latest:
        titles = {(c.get("title") or "").strip().lower() for c in store.list_recovery_cases(user_id)}
        earnings = earnings_by_title(user_id)
        for row in latest["rows"]:
            case = _case_for(row, earnings.get((row.get("title") or "").strip().lower()))
            row["case_title"], row["case_note"] = case["title"], case["note"]
            row["case_amount"], row["case_figure"] = case["amount"], case["figure"]
            row["case_caption"], row["case_key"] = case["caption"], case["key"]
            row["gap"] = bool(row["case_title"])
            row["has_case"] = row["case_title"].strip().lower() in titles if row["case_title"] else False
    return {"on": providers.mlc_adapter().configured(), "ready": ready, "missing": missing,
            "latest": latest, "per_sweep": PER_SWEEP}

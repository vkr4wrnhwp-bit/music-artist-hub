"""Rights conflicts computed from the account's own track passports.

The Rights Conflict Center used to render royalty_data.get_rights_conflicts,
which reads the five invented demo songs. On a real account that list is
empty, so the page told every artist "no rights conflicts detected, your
ownership data is clean" whatever their catalogue held (walk, 2026-09-20).
The owner's ruling: compute it.

What a conflict is here: two records that disagree, or a rights fact the
account needs and does not have. Both come from the artist's own passports
(db.list_os_tracks: title, release_title, and the passport and lockbox
dicts). Nothing is inferred from outside, nothing is estimated, and a
missing passport is never counted as a conflict, because an artist who has
not opened one has not said anything to contradict.

Severity says what it costs: HIGH is money a payor can hold or a claim
somebody else can make, MEDIUM is a payment that may not reach you,
LOW is a record that will not match cleanly.
"""

HIGH, MEDIUM, LOW = "High", "Medium", "Low"


def _clean(value):
    return (value or "").strip()


def _norm(value):
    return " ".join(_clean(value).lower().split())


def _names(value):
    """A credit line split into comparable names."""
    parts = [p.strip() for p in _clean(value).replace(";", ",").split(",")]
    return {_norm(p) for p in parts if p.strip()}


def _yes(value):
    """A passport or lockbox flag the artist has answered yes to."""
    return _norm(value) in ("yes", "y", "true", "1", "done", "signed",
                            "cleared", "on file", "complete", "confirmed")


def _no(value):
    """Answered, and the answer is no. An empty field is not a no."""
    return _norm(value) in ("no", "n", "false", "0", "none", "not cleared",
                            "uncleared", "missing", "pending", "unsigned")


def _conflict(cid, kind, title, description, severity, tracks, fix=None):
    return {
        "id": cid,
        "conflict_type": kind,
        "title": title,
        "description": description,
        "severity": severity,
        "songs_involved": tracks,
        "fix": fix,
        # The passport the fix opens: the song an action made from this
        # conflict is about (the Action Center's "After Hours · Song").
        "track_id": _track_of(fix),
        # What the work is called when this conflict becomes an action
        # (the owner's mockup: "Review split conflict").
        "action_title": ("%s: %s" % (ACTION_WORDS.get(kind, "Review rights conflict"),
                                     ", ".join(tracks)))[:200],
    }


# The action each kind of conflict asks for, as its title's first words.
ACTION_WORDS = {
    "Duplicate identifier": "Fix duplicate identifier",
    "Ownership disagreement": "Resolve ownership disagreement",
    "Unresolved clearance": "Resolve clearance",
    "Splits not agreed": "Review split conflict",
}


def _track_of(fix):
    """The track id in a /tracks/<id>#... fix link, or ''."""
    path = (fix or "").split("#", 1)[0]
    parts = path.strip("/").split("/")
    return parts[1] if len(parts) == 2 and parts[0] == "tracks" else ""


def _identifier_clashes(tracks):
    """One identifier, two recordings. An ISRC names a single recording and
    a UPC a single release, so a repeat is a real clash: royalties for both
    land against whichever record the payor matched."""
    out = []
    for field, label, severity in (("isrc", "ISRC", HIGH), ("upc", "UPC", MEDIUM)):
        seen = {}
        for t in tracks:
            value = _clean((t.get("passport") or {}).get(field)).upper()
            if value:
                seen.setdefault(value, []).append(t)
        for value, rows in seen.items():
            if len(rows) < 2:
                continue
            titles = [r.get("title") or "Untitled" for r in rows]
            if field == "upc" and len({_norm(r.get("release_title")) for r in rows}) < 2:
                continue   # one release, several of its tracks: correct
            out.append(_conflict(
                "dup-%s-%s" % (field, value.lower()), "Duplicate identifier",
                "%s %s is on %d tracks" % (label, value, len(rows)),
                "An %s names one %s. While two of yours carry it, a payor "
                "cannot tell which record it owes." % (
                    label, "recording" if field == "isrc" else "release"),
                severity, titles, fix="/tracks/%s#passport" % rows[0]["id"]))
    return out


def _ownership_disagreements(tracks):
    """The same song, told two different ways. Two passports for one title
    that name different master owners, songwriters or publishers are the
    account disagreeing with itself, and that is what freezes a claim."""
    out = []
    by_title = {}
    for t in tracks:
        by_title.setdefault(_norm(t.get("title")), []).append(t)
    checks = (
        ("master_owner", "master owner", HIGH,
         "Two of your own records claim a different owner of this master. "
         "A payor or a platform that reads both will hold the claim."),
        ("songwriters", "songwriters", HIGH,
         "The writer credits on this song do not match between your own "
         "records, so a mechanical claim can be disputed."),
        ("publishers", "publishers", MEDIUM,
         "The publisher on this song is named differently on your own "
         "records, so publishing royalties may go to the wrong place."),
    )
    for key, rows in by_title.items():
        if len(rows) < 2 or not key:
            continue
        for field, label, severity, why in checks:
            values = {}
            for t in rows:
                value = _clean((t.get("passport") or {}).get(field))
                if value:
                    values.setdefault(_norm(value) if field != "songwriters"
                                      else tuple(sorted(_names(value))), value)
            if len(values) > 1:
                title = rows[0].get("title") or "Untitled"
                out.append(_conflict(
                    "disagree-%s-%s" % (field, key.replace(" ", "-")),
                    "Ownership disagreement",
                    '"%s" names two different %s' % (title, label),
                    why + " On file: " + "; ".join(sorted(values.values())) + ".",
                    severity, [title],
                    fix="/tracks/%s#passport" % rows[0]["id"]))
    return out


def _unresolved_clearances(tracks):
    """A clearance the artist answered no to. Not a blank: a blank is work
    to do and the passport score already says so. A no is somebody else's
    right inside your record."""
    out = []
    checks = (
        ("sample_clearance", "Sample clearance", HIGH,
         "A sample that is not cleared can take the record down and the "
         "income with it."),
        ("beat_license", "Beat licence", HIGH,
         "Without the licence on file the beat's owner can claim this "
         "recording's income."),
        ("featured_approval", "Featured artist approval", MEDIUM,
         "A featured artist who has not approved the release can ask for "
         "it to come down."),
        ("artwork_rights", "Artwork rights", LOW,
         "Artwork you do not hold the rights to can be claimed by the "
         "photographer or designer."),
    )
    for t in tracks:
        passport = t.get("passport") or {}
        lockbox = t.get("lockbox") or {}
        title = t.get("title") or "Untitled"
        for field, label, severity, why in checks:
            answer = passport.get(field)
            if _no(answer) and not _yes(lockbox.get(field)):
                out.append(_conflict(
                    "clearance-%s-%s" % (field, t["id"]), "Unresolved clearance",
                    '"%s": %s is not cleared' % (title, label.lower()),
                    why, severity, [title],
                    fix="/tracks/%s#lockbox" % t["id"]))
    return out


def _split_gaps(tracks):
    """More than one writer and no split sheet. The song has people in it
    who have not signed for their share, which is the argument that takes
    the longest to settle and the one a payor will not settle for you."""
    out = []
    for t in tracks:
        passport = t.get("passport") or {}
        lockbox = t.get("lockbox") or {}
        writers = _names(passport.get("songwriters"))
        if len(writers) < 2:
            continue
        if _yes(passport.get("split_sheet_status")) or _yes(lockbox.get("split_sheet")):
            continue
        title = t.get("title") or "Untitled"
        out.append(_conflict(
            "splits-%s" % t["id"], "Splits not agreed",
            '"%s" has %d writers and no signed split sheet' % (title, len(writers)),
            "Nobody has signed for their share of this song. Until they "
            "have, every writer can claim a different number.",
            HIGH, [title], fix="/tracks/%s#lockbox" % t["id"]))
    return out


def for_account(tracks):
    """Every conflict in this account's catalogue, worst first.

    `tracks` is db.list_os_tracks(user_id). An empty catalogue returns an
    empty list, and the page says there is nothing to check yet rather
    than calling it clean.
    """
    tracks = [t for t in (tracks or []) if t.get("id")]
    found = (_identifier_clashes(tracks) + _ownership_disagreements(tracks)
             + _unresolved_clearances(tracks) + _split_gaps(tracks))
    order = {HIGH: 0, MEDIUM: 1, LOW: 2}
    found.sort(key=lambda c: (order.get(c["severity"], 3), c["title"]))
    return found


def summary(tracks):
    """What the page needs to be honest about what it just checked."""
    tracks = [t for t in (tracks or []) if t.get("id")]
    found = for_account(tracks)
    return {
        "conflicts": found,
        "checked": len(tracks),
        "high": sum(1 for c in found if c["severity"] == HIGH),
        "medium": sum(1 for c in found if c["severity"] == MEDIUM),
        "low": sum(1 for c in found if c["severity"] == LOW),
    }

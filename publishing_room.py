"""The Publishing room, as one screen.

The owner's mockup, 2026-09-22. Publishing is where a song's OWNERSHIP
lives: who wrote it, who gets paid, which registries know about it, and
where the record contradicts itself. Recordings are the Catalog; works are
the publishing. The room's one job is to make uncollected money and broken
paperwork visible.

WHERE EVERY FIGURE COMES FROM
-----------------------------
Nothing here is computed from anything but the account's own rows:

  works on file   store.list_os_tracks
  share claimed   artist_os.mlc_evidence -> the MLC's own answer, which
                  carries share_total and song_code
  uncollected     the same evidence, where the registry answered that no
                  work is linked to the recording's ISRC
  states          the ladder below, each rung a stored fact
  conflicts       rights_conflicts.summary over the same tracks
  splits          the passport's own words plus the Rights Lockbox's split
                  sheet state

WHAT IT REFUSES TO DO
---------------------
  * A registry that has not answered is "Not measured", never 0 and never
    green. A blank is not a zero.
  * Something typed into a passport is never drawn as verified. It has its
    own state, distinct from a registry's confirmation.
  * Nothing here says a registration was accepted, money was recovered or
    a society paid. We show what a registry answered, and when.
  * No percentages are shown on the splits panel. The passport holds
    songwriters as one line of free text; there are no writer shares on
    file anywhere, so the panel shows what IS on file and says what is
    not (owner's ruling, 2026-09-22).
"""
import artist_os
import royalty_types

# The ladder. A song sits in exactly ONE state: the furthest rung it has
# reached, not every rung it satisfies. That is why the counts add up to
# the works on file and can be read as a funnel.
#
# "Furthest reached" is deliberate and it is not the same as "all the
# earlier rungs are done". A song can be collecting with no split sheet on
# file; it is counted as collecting, because that is the truer statement
# about it, and its missing split sheet is a conflict, which is the panel
# that exists to say so.
STATES = (
    ("written", "Written", "On file here"),
    ("split_agreed", "Split agreed", "Split sheet signed or marked n/a"),
    ("registered", "Registered", "A registry holds a work for it"),
    ("claimed", "Claimed", "The whole collection share is claimed"),
    ("collecting", "Collecting", "Publishing money has arrived for it"),
)

# Statement sources that mean publishing money, as royalty_types classifies
# them. Recording income is the master's, not the work's, so it is not here.
PUBLISHING_BUCKETS = ("publishing", "mechanical")


def _norm(text):
    """A title reduced to what two spellings of it have in common."""
    return "".join(c for c in (text or "").lower() if c.isalnum())


def collecting_titles(rows):
    """Normalised titles on statement rows that are publishing money.

    Statements name songs in the payer's words, not ours, so this matches
    on the title alone. That UNDERCOUNTS: a song a society spells
    differently is read as not collecting. The page says so rather than
    quietly rounding the figure up.
    """
    out = set()
    for r in rows or ():
        if royalty_types.classify(r.get("source")) in PUBLISHING_BUCKETS:
            key = _norm(r.get("title"))
            if key:
                out.add(key)
    return out


def state_of(track, collecting):
    """Which rung this song has reached. Always one of STATES' keys."""
    if _norm(track.get("title")) in collecting:
        return "collecting"
    mlc = artist_os.mlc_evidence(track)
    if mlc["source"] == "check":
        share = mlc.get("share_total")
        if share is not None and share >= artist_os.MLC_SHARE_FLOOR:
            return "claimed"
        if mlc.get("song_code"):
            return "registered"
    box = artist_os.lockbox_report(track)
    sheet = next((d for d in box["docs"] if d["key"] == "split_sheet"), None)
    if sheet and sheet["state"] in ("ready", "n/a"):
        return "split_agreed"
    return "written"


def states(tracks, collecting):
    """The rail: one count per rung, and they sum to the works on file."""
    counts = {key: 0 for key, _n, _s in STATES}
    for t in tracks or ():
        counts[state_of(t, collecting)] += 1
    return [{"key": key, "name": name, "sub": sub, "count": counts[key]}
            for key, name, sub in STATES]


def uncollected(tracks):
    """One row per recording a registry has something to say about.

    Ordered worst first: money going uncollected, then a part share, then
    what nobody has evidence for, and finally what is confirmed. A song
    whose state is green is still listed, because a table that shows only
    problems cannot be checked against the catalogue.
    """
    rank = {"red": 0, "yellow": 1, "green": 2}
    # artist_os speaks in colours; the room kit's lamps are named for what
    # they MEAN. Emitting the colour word straight into the class left every
    # pill in this table with no rule at all and therefore no colour, which
    # is how the room shipped.
    tone = {"red": "crit", "yellow": "warn", "green": "good"}
    rows = []
    for t in tracks or ():
        mlc = artist_os.mlc_evidence(t)
        rows.append({
            "id": t.get("id") or "",
            "title": t.get("title") or "Untitled",
            "release": t.get("release_title") or "",
            "wrong": mlc["detail"],
            "label": mlc["label"],
            "state": mlc["state"],
            "tone": tone.get(mlc["state"], "off"),
            "source": mlc["source"],
        })
    rows.sort(key=lambda r: (rank.get(r["state"], 3), r["title"].lower()))
    return rows


def headline(tracks, rows):
    """The three figures, and what each one is of."""
    answered = [r for r in rows if r["source"] == "check"]
    missing = [r for r in rows if r["state"] == "red" and r["source"] == "check"]

    share = "Not measured"
    share_sub = "No registry has answered yet"
    if answered:
        got = 0.0
        for t in tracks or ():
            mlc = artist_os.mlc_evidence(t)
            if mlc["source"] == "check":
                got += float(mlc.get("share_total") or 0.0)
        share = "%g%%" % round(got / len(answered), 1)
        share_sub = ("Across the %d recording%s a registry has answered about"
                     % (len(answered), "" if len(answered) == 1 else "s"))

    return [
        {"key": "works",
         "value": str(len(tracks or ())) if tracks else "Not measured",
         "label": "Works on file",
         "sub": "" if tracks else "Nothing in the catalogue yet"},
        {"key": "share", "value": share,
         "label": "Share claimed", "sub": share_sub},
        {"key": "uncollected",
         "value": str(len(missing)) if answered else "Not measured",
         "label": "Uncollected",
         "sub": ("Recordings with no work linked to them" if answered
                 else "Nobody has asked a registry yet")},
    ]


def splits(track):
    """What is actually on file about who owns the selected song.

    No percentages: the passport holds songwriters as one line of free
    text and there are no writer shares stored anywhere in this
    application. The owner's ruling (2026-09-22) is to show what IS on
    file and say plainly what is not, rather than draw a table of shares
    nothing could fill.
    """
    if not track:
        return None
    passport = track.get("passport") or {}
    box = artist_os.lockbox_report(track)
    sheet = next((d for d in box["docs"] if d["key"] == "split_sheet"), None)
    producer = next((d for d in box["docs"] if d["key"] == "producer_agreement"), None)
    fields = [("Songwriters", passport.get("songwriters") or ""),
              ("Producers", passport.get("producers") or ""),
              ("Publishers", passport.get("publishers") or ""),
              ("PRO affiliation", passport.get("pro") or ""),
              ("Publishing administrator", passport.get("pub_admin") or "")]
    return {
        "id": track.get("id") or "",
        "title": track.get("title") or "Untitled",
        "fields": [{"label": lbl, "value": val, "on_file": bool(val.strip())}
                   for lbl, val in fields],
        "sheet": (sheet or {}).get("state") or "missing",
        "producer": (producer or {}).get("state") or "missing",
    }


def build(tracks, statement_rows, conflicts, selected, cards,
          artist_name="", sample=False, can_open=None):
    """Everything the screen renders. No page logic beyond this."""
    tracks = list(tracks or ())
    collecting = collecting_titles(statement_rows)
    rows = uncollected(tracks)

    tiles = []
    counts = {"track-passports": ("%d record%s" % (len(tracks),
                                                   "" if len(tracks) == 1 else "s")
                                  ) if tracks else "",
              "conflicts": ("%d open" % len(conflicts or ())
                            ) if conflicts else ""}
    for key in ("catalog", "track-passports", "conflicts", "beats",
                "certified"):
        card = (cards or {}).get(key)
        if not card:
            continue
        href = card[0]
        if can_open and not can_open(href):
            continue
        name, line = card[2], card[3]
        if key == "beats":
            # ONE tile over beats and fingerprints (owner, 2026-09-22:
            # "beats and fingerprints should become like beat fingerprints
            # ... not be two different ones in publishing"). Both keep their
            # card in rooms.py, so both keep a room and a team seat's
            # access; only one door is drawn. The pages themselves still
            # need merging - this is the surface, not the surgery.
            name = "Beat Fingerprints"
            line = ("Your beats, their licences and the cleared list — and the "
                    "fingerprints that find them being used.")
        tiles.append({"key": key, "href": href, "icon": card[1],
                      "name": name, "line": line,
                      "status": counts.get(key, "")})

    return {
        "artist_name": artist_name or "",
        "headline": headline(tracks, rows),
        "states": states(tracks, collecting),
        "rows": rows,
        "conflicts": list(conflicts or ()),
        "splits": splits(selected),
        "songs": [{"id": t.get("id") or "", "title": t.get("title") or "Untitled"}
                  for t in tracks],
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }

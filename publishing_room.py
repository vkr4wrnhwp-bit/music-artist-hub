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


# --- THE PLATE --------------------------------------------------------
# static/img/publishing-plate.webp, 1859x846: a RIGHTS REGISTRY unit, two
# equal halves over a narrow ledger strip. Each window is (x, y, w, h) as
# a PERCENTAGE of the plate, MEASURED off the file with PIL. RE-MEASURE
# ALL OF THEM if the plate is regenerated or re-cropped.
#
# The plate silkscreens WORKS ON FILE, UNCOLLECTED and THE SPLIT, so the
# markup never prints those words.
#
# The strip carries SHARE CLAIMED as a bar - the third headline figure,
# which has no window of its own and is literally what a split is. It is
# not the "Who owns it" table: that has its own panel with its own song
# picker further down, and drawing it twice would be the screen folding
# onto itself.
PLATE = {
    "works":       (5.11, 18.56, 43.30, 37.47),
    "uncollected": (51.37, 18.91, 43.46, 37.12),
    "split":       (5.11, 73.88, 90.05, 9.93),
}


def box(key):
    """The inline custom properties that put a window on its glass."""
    x, y, w, h = PLATE[key]
    return "--x:%s%%;--y:%s%%;--w:%s%%;--h:%s%%" % (x, y, w, h)


# --- THE PAGE FROM ZERO (owner's Publishing spec + mockup, 2026-09-23) ----
# An account with no song does not meet an empty plate, five zero-count
# states and blank conflict tables. It meets an onboarding page: the
# Command Center's photographed three-screen plate drawn STATIC with this
# room's words, one card that opens the shared add-song form, the four
# categories as doors, the five-step workflow as education, the two
# empties in words, help, and the tools in a drawer that starts open. No
# catalog total, registry count, collection number, ownership chart or
# percentage: a missing registry answer is Not measured, never zero. The
# animated standby that used to run on the plate is retired here; the
# fill reel below stays for a populated plate's empty windows.
ZERO_SUBTITLE = ("Keep every song's writers, splits, rights, and registration status "
                 "in one trusted record.")
ZERO_RACK = (
    ("Purpose", "Know who owns each song and who is collecting."),
    ("Start here", "Add one song and its writers."),
    ("Good to know", "A missing registry answer is Not measured, never zero."),
)
# The one door, as the spec suggests it. /catalog/new is an alias of the
# ONE shared add-song form (the catalog's passports view, the same form
# Studio and the Command Center send people to) that carries the way
# back - not a second song-creation form.
DOOR = "/catalog/new?returnTo=/room/publishing&from=publishing-zero-state"
ZERO_PROJECT = {
    "heading": "Start with one song",
    "title": "Create your first song record",
    "desc": ("Add the title and writers now. Complete splits, identifiers, and "
             "registrations step by step."),
    "cta": "Add a song",
    "need": "What information do I need?",
    # A seat that may not write here is told who adds songs rather than
    # handed a door that bounces.
    "locked": ("Songs are added by the account owner or a seat with edit access. "
               "Publishing opens here once one is on file."),
}
# What the first draft needs (spec section 3) - shown in place when the
# card's second action is opened, because the spec says it and nothing on
# the catalog page does yet.
FIRST_DRAFT = ("The song title",
               "The artist or label account it belongs to",
               "At least one known writer, or \u201cWriters not known yet\u201d")
# The four categories (spec section 5), each a door by its own room card
# where a page exists for it; Writers & splits lives on each Track
# Passport, Registrations & collection on the Certified ladder (the
# registration wizard was deleted - its status lives on the passport
# too, and /registration forwards there).
LENSES = (
    ("catalog", "Catalog & passports",
     "The composition, its recordings, identifiers, credits, documents, and next step.",
     "catalog"),
    ("writers", "Writers & splits",
     "Writers, roles, ownership, publishers, administrators, and agreement status.",
     "track-passports"),
    ("registrations", "Registrations & collection",
     "Registrations you recorded, registry responses, claims, and publishing income evidence.",
     "certified"),
    ("conflicts", "Conflicts & clearances",
     "Rights conflicts, beats, licences, samples, and contradictory records.",
     "conflicts"),
)
# The five steps, EDUCATIONAL on a new account: Add song lit, the rest
# neutral, numbered as the owner's mockup numbers them, no percentage.
# STATES (Written .. Collecting) stays the populated room's ladder.
WORKFLOW = (
    ("song", "Add song", "Create title record"),
    ("writers", "Add writers", "Name contributors"),
    ("splits", "Confirm splits", "Agree ownership"),
    ("status", "Record status", "Add registrations"),
    ("monitor", "Monitor", "See registry answers"),
)
ZERO_CATALOG = ("Your publishing catalog will appear here",
                "Each song will show its writers, splits, identifiers, documents, and "
                "next required step.")
ZERO_VERIFIED = ("Nothing has been verified yet",
                 "Missing registry answers are Not measured \u2014 never zero, "
                 "registered, or collecting.")
ZERO_HELP = ("Not sure what belongs in Publishing?",
             "Ask Street Banker what to record now and what can wait.")
# The link under "Your publishing catalog will appear here". The spec
# names two - "How song records work" and "Import catalog" - and there
# is no catalog import in the app, so the second waits until there is
# one; a link to nothing is the dead control the audits keep finding.
ZERO_LINKS = (("How song records work", "#pb-z-flow-h"),)
# The drawer at the foot: the spec's four categories, each tool by its
# room card. A category with no page of its own yet is not drawn.
ZERO_BANDS = (
    ("Catalog & passports", ("catalog", "track-passports")),
    ("Writers & splits", ()),
    ("Registrations & collection", ("certified",)),
    ("Conflicts & clearances", ("conflicts", "beats", "fingerprints")),
)
# The sentence the room carries back from the add-song form.
DONE_LINE = "Your first song was added. Publishing is ready for its writers."


def new_account(tracks):
    """The spec's new_account: no song on file. Registrations, conflicts
    and clearances all hang off songs, so with none there is nothing
    else to count. The argument is what the store returned; an
    unreadable store never reaches here - the route shows the error page."""
    return not tracks


def done_line(came_from, tracks):
    """Said by the SAVED song, never by the param alone."""
    return DONE_LINE if came_from == "publishing-zero-state" and tracks > 0 else ""


def _tile(cards, key, can_open=None):
    card = (cards or {}).get(key)
    if not card:
        return None
    href = card[0]
    if can_open and not can_open(href):
        return None
    return {"key": key, "href": href, "icon": card[1], "name": card[2], "line": card[3]}


def zero_page(can_add=True, can_open=None, cards=None):
    """The page from zero. A seat sees only the doors it can open; a
    category whose page a seat cannot open is words, not a door."""
    lenses = []
    for key, name, line, card_key in LENSES:
        tile = _tile(cards, card_key, can_open)
        lenses.append({"key": key, "name": name, "line": line,
                       "href": tile["href"] if tile else ""})
    bands = []
    for title, keys in ZERO_BANDS:
        got = [t for t in (_tile(cards, k, can_open) for k in keys) if t]
        if got:
            bands.append({"title": title, "tiles": got})
    return {
        "subtitle": ZERO_SUBTITLE,
        "screens": [{"k": k, "v": v} for k, v in ZERO_RACK],
        "door": DOOR,
        "project": dict(ZERO_PROJECT, can=can_add),
        "first_draft": FIRST_DRAFT,
        "lenses": lenses,
        "workflow": WORKFLOW,
        "catalog": ZERO_CATALOG,
        "verified": ZERO_VERIFIED,
        "help": ZERO_HELP,
        "links": ZERO_LINKS,
        "bands": bands,
    }


# The reel a READING window shows while it has nothing to read (owner,
# 2026-09-22: no words in an empty window, icons). The one piece of the
# old standby still read: a populated plate's empty windows.
STANDBY_FILL = ("written", "registered", "claimed", "collecting", "doc")


def _six(icons):
    """Six stops, always: the roll's keyframes step through six, and a
    five-icon reel ran its last stop into blank glass."""
    icons = list(icons or ())
    while icons and len(icons) < 6:
        icons.append(icons[len(icons) % len(icons)])
    return icons[:6]


def standby():
    """What a populated plate's empty windows fill with. The animated
    standby that once ran on an empty account is retired: that account
    meets the page from zero instead."""
    return {"fill": _six(STANDBY_FILL)}


def plate_windows(rows):
    """The two big windows, in the order the silkscreen prints them."""
    by = {r["key"]: r for r in rows or ()}
    return [dict(by[k], box=box(k)) for k in ("works", "uncollected") if k in by]


def claimed_bar(rows):
    """The share-claimed strip: the figure, and how full the bar is.

    `fill` is None when no registry has answered - the bar is then not
    drawn at all rather than drawn empty, because an empty bar reads as
    "you have claimed nothing" when the truth is "nobody has asked".
    """
    row = {r["key"]: r for r in rows or ()}.get("share") or {}
    value = row.get("value") or "Not measured"
    fill = None
    if value.endswith("%"):
        try:
            fill = max(0.0, min(100.0, float(value[:-1])))
        except ValueError:
            fill = None
    return {"value": value, "sub": row.get("sub") or "",
            "measured": fill is not None, "fill": fill,
            "box": box("split")}


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
          artist_name="", sample=False, can_open=None, zero=None, can_add=True):
    """Everything the screen renders. No page logic beyond this.

    `zero` is new_account() decided by the route (None here means: decide
    from the tracks); `can_add` is who may add a song (see zero_page)."""
    tracks = list(tracks or ())
    if zero is None:
        zero = new_account(tracks)
    collecting = collecting_titles(statement_rows)
    rows = uncollected(tracks)

    tiles = []
    counts = {"track-passports": ("%d record%s" % (len(tracks),
                                                   "" if len(tracks) == 1 else "s")
                                  ) if tracks else "",
              "conflicts": ("%d open" % len(conflicts or ())
                            ) if conflicts else ""}
    # ONE DOOR MEANS ONE PAGE (owner, 2026-09-22): "if there's going to be
    # two pages behind it, then we don't need them to be one door ... if
    # it's going to be two doors, then leave it two tiles."
    #
    # Beats and Fingerprints ARE meant to become one - Beat Fingerprints -
    # but they are still two pages, so they are still two tiles. A single
    # tile over two pages is a door that lies about what is behind it, and
    # that is worse than the duplication it was hiding. The tile becomes one
    # when the pages do.
    for key in ("catalog", "track-passports", "conflicts", "beats",
                "fingerprints", "certified"):
        card = (cards or {}).get(key)
        if not card:
            continue
        href = card[0]
        if can_open and not can_open(href):
            continue
        name, line = card[2], card[3]
        tiles.append({"key": key, "href": href, "icon": card[1],
                      "name": name, "line": line,
                      "status": counts.get(key, "")})

    return {
        "artist_name": artist_name or "",
        "headline": headline(tracks, rows),
        # The plate: the two big readings, and the claimed-share strip.
        "windows": plate_windows(headline(tracks, rows)),
        "claimed": claimed_bar(headline(tracks, rows)),
        # No song on file: the page from zero. One song and the plate
        # takes over untouched.
        "idle": bool(zero),
        "zero": zero_page(can_add, can_open, cards) if zero else None,
        "standby": standby(),
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

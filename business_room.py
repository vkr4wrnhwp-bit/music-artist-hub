"""The Business room, as one screen.

The owner's mockup, 2026-09-22. Eighteen cards became one screen, one
instrument and eighteen tiles, and the screen opens on a photographed analyser with THREE
windows: what was reported, what is not collected, and what was kept.

THE RULE THIS ROOM IS BUILT ON
------------------------------
There are three kinds of money here and they are NEVER added together:

  reported    what statements actually said. Measured.
  not         split in two and shown as two: what is ACTUALLY unattributed
  collected   on the statements, beside what is ESTIMATED to be missing.
  kept        reported income less the expenses the artist logged.

recovery_engine computes a `total_at_stake` that sums the actual and the
estimate (recovery_engine.py:238) and the Recovery page deliberately
refuses to print it. So does this room. A single figure adding a
measurement to an estimate is the one thing this screen must not do, and
build() has no code path that produces one.

WHERE EVERY FIGURE COMES FROM
-----------------------------
  rows        db.get_statement_rows, scoped to this account
  analysis    statements_engine.analyze(rows) - ONCE, and passed on. This
              room reads the heaviest table in the schema and is about to
              become one of the most-opened doors in the app.
  recovery    recovery_engine.build(user_id, rows=, analysis=) - it takes
              both precisely so nothing is analysed twice
  expenses    db.list_expenses
  claims      db.list_recovery_cases, db.list_disputes

WHAT IT REFUSES TO DO
---------------------
  * No total across the three windows.
  * Income is None, not 0, when there is no statement - and so is "kept".
    The defect of 2026-09-15 was a page printing "$0.00 Profitable".
  * An estimate always carries the word "estimate", beside the actual.
  * NO FIGURE FROM THE MISSING-MONEY QUEUE. Its dollars come from six
    hardcoded coefficients applied to the whole-account total once per
    track, so its estimate can exceed everything the catalogue has ever
    earned. Its tile carries a count and nothing else.
  * Nothing claims money will be recovered - only what was claimed, and
    what arrived.
"""

# The path money takes through this app. Each rung is a stored fact.
#
# The rail sits directly under the plate, and the plate silkscreens
# REPORTED, NOT COLLECTED and KEPT across its windows. So no rung is
# called Reported or Kept: the window is the figure, the rung is the step
# that produced it, and two of them wearing the same word forty pixels
# apart is the "folding things on top of each other" the owner asked to
# watch for. The KEYS are unchanged - they carry the icons.
STEPS = (
    ("reported", "Statements", "Statements on file"),
    ("named", "Matched", "Revenue matched to a track"),
    ("chased", "Chased", "Claims and disputes opened"),
    ("recovered", "Recovered", "Money that actually arrived"),
    ("kept", "Costs", "What you logged against it"),
)

# The tiles, money first, then the paperwork, then the people.
#
# EIGHTEEN CARDS, EIGHTEEN DOORS, and that is the honest answer.
#
# Two pairs looked like free merges and are not. Tax and Contracts are
# each a second VIEW of another card's handler - /statements?view=tax and
# /vault?view=contracts - but the templates switch on that argument
# ({% if view == "tax" %}, {% if view == "contracts" %}), so the bare page
# does NOT contain the other view. One handler, two pages. Folding either
# tile away does not tidy a page, it deletes its only door, which is the
# "no way out" shape from the route walk. tests/test_rooms.py caught it.
#
# They can be merged for real - by making /vault and /statements show both
# halves on one page - and that is a change to those pages, not to this
# list. Roster, Portal and Services stay for the same reason: a grep for
# their hrefs finds no other door in the rooms layout.
# THREE BANDS, not one wall (owner, 2026-09-22: "group, do not delete").
# Sixteen tiles on a pro account, against three to six in every other
# room, and four of them - Recovery, Claims, Missing money, Disputes -
# are the same job. Nothing moved and nothing was deleted; the board
# just says which of this room's three jobs each door belongs to.
BANDS = (
    ("The money you have",
     ("royalties", "statements", "tax", "revenue-os", "valuation")),
    ("The money you're owed",
     ("recovery", "cases", "money-queue", "disputes")),
    ("The paperwork and the people",
     ("vault", "contracts", "deals", "deal-simulator", "hours", "team",
      "portal", "roster", "services")),
)
# The flat order, still, for everything that reads the board as a list.
TILES = tuple(k for _title, keys in BANDS for k in keys)

# What the tile is called when its card's own label is about the archive
# rather than the paperwork this room exists for.
RENAMED = {
    "cases": ("Claims", "Manage open claims and submissions."),
    "money-queue": ("Missing money", "Review and investigate unattributed activity."),
}


# --- THE PLATE --------------------------------------------------------
# This room's fractions have always lived in static/css/business-room.css,
# which predates the shared kit. They are repeated here ONLY so the
# standby state can position itself the way every other room's does, and
# they must stay in step with that sheet: same file, same measurements.
PLATE = {
    "reported":      (6.70, 19.95, 26.61, 56.94),
    "not-collected": (35.94, 19.95, 28.05, 56.94),
    "kept":          (66.75, 19.95, 26.61, 56.94),
}


def box(key):
    """The inline custom properties that put a window on its glass."""
    x, y, w, h = PLATE[key]
    return "--x:%s%%;--y:%s%%;--w:%s%%;--h:%s%%" % (x, y, w, h)


# --- THE STANDBY DISPLAY, the owner's way (2026-09-22) -------------------
# "Slot machine-y": the big window sequences the room's FEATURES, each
# frame cutting in large and glitching out to the next; the small windows
# each do a different thing - icons rolling like a reel, a hint that
# changes, the feature names ticking through - and never carry a caption.
# One voice, phosphor green: the plate's own screen.
#
# The frames name cards that exist in rooms.ROOMS for this room, by what
# they actually do. The owner supplies the final text per room at the
# audit; until then nothing here claims more than the card does.
# WORDS ONLY - never a figure, not even an example one.
STANDBY_FRAMES = [('Statements', 'Upload one and every figure reads from it'), ('Royalties', 'Every stream, store, lane and track on one page'), ('Recovery', 'Findings pulled from your own uploads'), ('Profit & Loss', 'Income beside the costs you log')]
STANDBY_REELS = []
STANDBY_TIPS = ('not-collected', 'Not collected', ['Upload a statement to begin', 'Every stream, store and track', 'Findings from your own uploads', 'Income less the costs you log'])
STANDBY_TICKER = ('kept', 'Kept', ['Royalties', 'Statements', 'Recovery', 'Claims', 'Deals'])
STANDBY_CINE = ('reported', 'Reported')
STANDBY_SIZE = ('clamp(20px, 3.2cqw, 50px)', 'clamp(10px, 1.15cqw, 16px)')
# One picture per frame, generated by the owner; a missing file draws
# nothing rather than a broken image. The ?v moves when one is replaced.
STANDBY_IMAGES = tuple("static/img/standby/business-%d.webp" % n for n in (1, 2, 3, 4))
STANDBY_IMAGE_V = 1


def _standby_image(n):
    import os
    path = STANDBY_IMAGES[n] if n < len(STANDBY_IMAGES) else ""
    return "/%s?v=%d" % (path, STANDBY_IMAGE_V) if path and os.path.exists(path) else ""

# The reel a READING window shows while it has nothing to read
# (owner, 2026-09-22: no words in an empty window, icons).
STANDBY_FILL = ("reported", "named", "chased", "recovered", "kept", "upload")


def _six(icons):
    """Six stops, always: the roll's keyframes step through six, and a
    five-icon reel ran its last stop into blank glass."""
    icons = list(icons or ())
    while icons and len(icons) < 6:
        icons.append(icons[len(icons) % len(icons)])
    return icons[:6]


def standby():
    """The plate with nothing measured: a sequence, reels, a hint, a ticker."""
    key, name = STANDBY_CINE
    size, line = STANDBY_SIZE
    out = {
        "cine": {"box": box(key), "name": name, "size": size, "line": line},
        "frames": [{"n": i, "title": t, "line": l, "image": _standby_image(i)}
                   for i, (t, l) in enumerate(STANDBY_FRAMES)],
        "count": len(STANDBY_FRAMES),
        "reels": [{"box": box(k), "name": n, "icons": _six(icons), "n": i}
                  for i, (k, n, icons) in enumerate(STANDBY_REELS, start=1)],
        "tips": None, "ticker": None,
    }
    if STANDBY_TIPS:
        k, n, lines = STANDBY_TIPS
        out["tips"] = {"box": box(k), "name": n, "lines": lines, "count": len(lines)}
    if STANDBY_TICKER:
        k, n, lines = STANDBY_TICKER
        out["ticker"] = {"box": box(k), "name": n, "lines": lines}
    out["fill"] = _six(STANDBY_FILL)
    return out


def money(value):
    """A figure, or the words that say nobody measured one.

    DOLLARS, and formatted by statements_desk.money - the same helper the
    Statements desk, the Royalties desk and Recovery all print through, so
    a figure on this plate reconciles character for character with the page
    behind it. The first cut of this room printed pounds, because the
    owner's mockup was rendered with them and I took that for a spec
    instead of reading the app - which has never had one in it.

    None is not 0. A page printing "0.00 Profitable" for an account with no
    statements is the defect this exists to prevent, so the absence is
    words and a genuine nought still prints.
    """
    if value is None:
        return {"value": "Not measured", "measured": False}
    try:
        value = float(value)
    except (TypeError, ValueError):
        return {"value": "Not measured", "measured": False}
    if value != value or abs(value) == float("inf"):
        return {"value": "Not measured", "measured": False}
    import statements_desk
    return {"value": statements_desk.money(value), "measured": True}


def change(now, before):
    """The period-over-period move, or nothing at all.

    One period is not a trend. Rather than draw a 0% that looks like "no
    change" when the truth is "nothing to compare", this returns None and
    the window prints the reason.
    """
    if now is None or before is None:
        return None
    try:
        now, before = float(now), float(before)
    except (TypeError, ValueError):
        return None
    if before == 0:
        return None
    pct = (now - before) / abs(before) * 100.0
    return {"pct": "%+.0f%%" % pct, "up": pct >= 0}


def windows(reported, prior, actual, estimated, kept, kept_prior,
            note="", kept_note=""):
    """The three, and the middle one is two readings rather than one.

    They are returned as three separate entries with no sum anywhere,
    because the honesty of this screen is that an actual and an estimate
    never become one number.

    `note` NAMES the basis - "2026-02 vs. 2026-01" - because the window is
    one period's money and a reader cannot otherwise tell it from the
    lifetime total. The note that used to sit here said "One period on
    file" on every account, including accounts with twelve.
    """
    return [
        {"key": "reported", "label": "Reported",
         "figure": money(reported),
         "change": change(reported, prior),
         "note": note,
         "split": None},
        {"key": "not-collected", "label": "Not collected",
         "figure": None, "change": None, "note": "",
         # TWO readings, side by side, each named for what it is.
         "split": [
             {"label": "Actual unattributed", "figure": money(actual),
              "tag": ""},
             {"label": "Estimated missing", "figure": money(estimated),
              "tag": "estimate"},
         ]},
        {"key": "kept", "label": "Kept",
         "figure": money(kept),
         "change": change(kept, kept_prior),
         "note": kept_note or ("Needs a statement" if kept is None else ""),
         "split": None},
    ]


def provenance(statements, rows, tracks, stores, periods, span):
    """What the reading was taken from. No figure on this screen floats."""
    if not statements:
        return ""
    bits = ["%s statement%s" % (statements, "" if statements == 1 else "s")]
    for n, word in ((rows, "row"), (tracks, "track"),
                    (stores, "store"), (periods, "period")):
        if n:
            bits.append("{:,} {}{}".format(n, word, "" if n == 1 else "s"))
    line = " · ".join(bits)
    return "%s · %s" % (line, span) if span else line


def path(statements, unmatched, open_claims, recovered, expenses):
    """The five circles. Each says what it counted."""
    state = {
        "reported": (statements > 0,
                     ("%d statement%s" % (statements, "" if statements == 1 else "s"))
                     if statements else "No statements yet"),
        "named": (statements > 0,
                  ("%s unmatched" % money(unmatched)["value"])
                  if unmatched is not None else "Nothing to match yet"),
        "chased": (open_claims > 0,
                   ("%d open claim%s" % (open_claims, "" if open_claims == 1 else "s"))
                   if open_claims else "Nothing opened"),
        # Gated on the money itself, not on the upload count. It used to
        # read `if statements`, which counts FILES: an upload that parsed
        # to no rows printed "$0.00 recovered" on this rung while every
        # window above it said "Not measured" - two bases on one screen.
        "recovered": ((recovered or 0) > 0,
                      ("%s recovered" % money(recovered)["value"])
                      if recovered else "Nothing recovered"),
        "kept": (expenses > 0,
                 ("%d expense%s logged" % (expenses, "" if expenses == 1 else "s"))
                 if expenses else "No costs logged"),
    }
    out = []
    for i, (key, name, sub) in enumerate(STEPS, start=1):
        reached, line = state[key]
        out.append({"key": key, "n": i, "name": name, "sub": sub,
                    "line": line, "reached": bool(reached)})
    return out


# The streams a statement can name, and what the absence of each one means.
# A stream with nothing behind it says WHICH statement is missing; a nought
# there would be a claim about the artist's income rather than a fact about
# their paperwork.
STREAMS = (
    ("recording", "Streaming", ""),
    ("publishing", "Performance", "No PRO statement"),
    ("mechanical", "Mechanicals", "No MLC statement"),
    ("neighboring", "Neighbouring rights", "No society statement"),
)


def streams(rows):
    """Where the money comes from, folded out of the rows themselves.

    NOT out of analyze(): the route used to read analysis["by_bucket"],
    a key analyze() has never returned, so every stream read "—" on every
    account. An artist with a Spotify statement was told they had no
    measured streaming income. Folding the rows through
    royalty_types.classify is the same rule Royalties uses.

    Money from a source nobody can classify gets its own line rather than
    vanishing between the four named ones.
    """
    import royalty_types
    pots = {}
    for r in rows or ():
        pots[royalty_types.classify(r.get("source"))] = (
            pots.get(royalty_types.classify(r.get("source")), 0.0)
            + _amount(r.get("amount")))

    out = []
    for key, label, why in STREAMS:
        amount = pots.get(key)
        out.append({
            "label": label,
            "amount": money(amount)["value"] if amount is not None else "—",
            "measured": amount is not None,
            "source": royalty_types.LABELS.get(key, ""),
            "why": "" if amount is not None else why,
        })
    other = pots.get("other")
    if other:
        out.append({
            "label": "Unclassified",
            "amount": money(other)["value"], "measured": True,
            "source": royalty_types.LABELS.get("other", ""),
            "why": "",
        })
    return out


def _amount(value):
    """A row's amount as a number. A non-finite one reads as 0 rather than
    taking the page down - one inf row did exactly that on 2026-09-20."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return value if value == value and abs(value) != float("inf") else 0.0


def periods(rows):
    """(ordered period labels, total per label, rows in no readable period).

    analyze() returns no by_period, so the route invented one and the
    window silently fell back to the lifetime total while the note under
    it claimed "One period on file". Here the buckets come from the rows.

    A label whose shape period_key cannot read sorts to the very end, so
    it is kept OUT of the ordering entirely - otherwise "Q1-2026" would be
    handed to the window as the most recent period.
    """
    import statements_engine
    totals, unreadable = {}, 0
    for r in rows or ():
        label = (r.get("period") or "").strip()
        if label and statements_engine.period_key(label)[0] != 9999:
            totals[label] = totals.get(label, 0.0) + _amount(r.get("amount"))
        else:
            unreadable += 1
    return statements_engine.order_periods(list(totals)), totals, unreadable


def costs_in(expenses, label):
    """What was logged against ONE period, or None if it cannot be told.

    Kept has to be reported LESS costs from the SAME period. Subtracting
    every cost an account ever logged from one period's income is how a
    page comes to report a negative month.
    """
    import statements_engine
    if not label:
        return None
    key = statements_engine.period_key(label)
    if key[0] == 9999:
        return None
    total = 0.0
    for e in expenses or ():
        when = (e.get("spend_date") or "")[:7]
        if when and statements_engine.period_key(when) == key:
            total += _amount(e.get("amount"))
    return round(total, 2)


def reading(order, totals, analysis_total):
    """The reported figure, the one before it, and what to call them.

    Returns (reported, prior, note). Every window on the plate is then on
    the same basis, which is the only way Kept can be Reported less costs.
    """
    if not order:
        # Nothing carries a readable period. The window is then everything
        # on file, and the note says so rather than naming a period.
        return analysis_total, None, ("No period on file · all statements"
                                      if analysis_total is not None
                                      else "Needs a statement")
    latest = order[-1]
    reported = round(totals[latest], 2)
    if len(order) < 2:
        return reported, None, "%s · the only period on file" % latest
    prev = order[-2]
    return reported, round(totals[prev], 2), "%s vs. %s" % (latest, prev)


def build(reported, prior, actual, estimated, kept, kept_prior,
          scan, steps, rows, chasing, cards,
          artist_name="", sample=False, can_open=None, note="",
          kept_note=""):
    """Everything the screen renders. No page logic beyond this."""
    def _tile(key):
        card = (cards or {}).get(key)
        if not card:
            return None
        href = card[0]
        if can_open and not can_open(href):
            return None
        name, line = card[2], card[3]
        if key in RENAMED:
            name, line = RENAMED[key]
        return {"key": key, "href": href, "icon": card[1],
                "name": name, "line": line}

    # A band with nothing in it is not drawn - a Label-only card or a
    # seat's gate can empty one.
    bands, tiles = [], []
    for title, keys in BANDS:
        got = [t for t in (_tile(k) for k in keys) if t]
        if got:
            bands.append({"title": title, "tiles": got})
            tiles.extend(got)

    return {
        "artist_name": artist_name or "",
        "bands": bands,
        "windows": windows(reported, prior, actual, estimated, kept,
                           kept_prior, note, kept_note),
        "measured": reported is not None,
        # On the flip like every other room. Owner, 2026-09-22, twice in
        # the hour: first "let's not do that" to the statement figures on
        # the plate, then "switch to business too, so all the text
        # matches in that green" - the display until a statement exists,
        # the readings in the screen's own green once one does.
        "idle": reported is None,
        "standby": standby(),
        "scan": scan or "",
        "path": steps,
        # The RAW statement rows: streams() folds them itself.
        "streams": streams(rows),
        "chasing": list(chasing or ()),
        "tiles": tiles,
        # The mark is literal: it appears when this account is looking at
        # the showcase, and never as decoration.
        "sample": bool(sample),
    }

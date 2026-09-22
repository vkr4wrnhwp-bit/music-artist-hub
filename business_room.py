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
TILES = ("royalties", "statements", "tax", "recovery", "cases", "disputes",
         "money-queue", "revenue-os", "valuation", "hours", "deals",
         "deal-simulator", "vault", "contracts", "team", "roster", "portal",
         "services")

# What the tile is called when its card's own label is about the archive
# rather than the paperwork this room exists for.
RENAMED = {
    "cases": ("Claims", "Manage open claims and submissions."),
    "money-queue": ("Missing money", "Review and investigate unattributed activity."),
}


def money(value, currency="£"):
    """A figure, or the words that say nobody measured one.

    None is not 0. A page printing "0.00 Profitable" for an account with no
    statements is the defect this exists to prevent.
    """
    if value is None:
        return {"value": "Not measured", "measured": False}
    try:
        return {"value": "%s%s" % (currency, "{:,.0f}".format(float(value))),
                "measured": True}
    except (TypeError, ValueError):
        return {"value": "Not measured", "measured": False}


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
        "recovered": ((recovered or 0) > 0,
                      ("%s recovered" % money(recovered or 0)["value"])
                      if statements else "Nothing recovered"),
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
    tiles = []
    for key in TILES:
        card = (cards or {}).get(key)
        if not card:
            continue
        href = card[0]
        if can_open and not can_open(href):
            continue
        name, line = card[2], card[3]
        if key in RENAMED:
            name, line = RENAMED[key]
        tiles.append({"key": key, "href": href, "icon": card[1],
                      "name": name, "line": line})

    return {
        "artist_name": artist_name or "",
        "windows": windows(reported, prior, actual, estimated, kept,
                           kept_prior, note, kept_note),
        "measured": reported is not None,
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

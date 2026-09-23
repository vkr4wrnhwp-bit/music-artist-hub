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


# --- THE PAGE FROM ZERO (owner's Business spec + mockup, 2026-09-23) ------
# An account with no statement, no row, no cost, no claim and no dispute
# does not meet an empty analyser. It meets an onboarding page: the
# Command Center's photographed three-screen plate drawn STATIC with this
# room's words, one card that opens the statements desk, the four
# categories as doors to the pages that own the work, the five-step
# workflow as education, the two empties in words, help, and the tools in
# a drawer that starts open. No date range, no income total, no profit,
# no recovery estimate, no percentage - and never a nought: missing
# paperwork is never shown as zero income. The animated standby that
# used to run on the analyser is retired here; the fill reel below stays
# for a populated analyser's empty windows.
ZERO_SUBTITLE = "See what you earned, what you spent, and what still needs attention."
ZERO_RACK = (
    ("Purpose", "Know what came in, what went out, and what you kept."),
    ("Start here", "Upload one royalty statement."),
    ("Good to know", "Missing paperwork is never shown as zero income."),
)
# The one door: the statements desk, carrying the way back exactly as the
# spec writes it. The desk's intake section is the top of that page.
DOOR = "/statements?returnTo=/room/business&from=business-zero-state"
ZERO_PROJECT = {
    "heading": "Start with your first statement",
    "title": "Upload a statement",
    "desc": ("Add a CSV, spreadsheet, or PDF from a distributor, PRO, publisher, "
             "or rights society."),
    "cta": "Upload statement",
    "how": "How statements work",
    # A seat that may not write here is told who uploads rather than
    # handed a door that bounces.
    "locked": ("Statements are uploaded by the account owner or a seat with edit "
               "access. Business opens here once one is on file."),
}
# The four categories (spec section 7). Each is a door to the page that
# owns the work, by that page's own room card, so a renamed or moved page
# follows; a seat that cannot open the page gets the words alone.
LENSES = (
    ("statements", "Statements & royalties",
     "Reported income by source, store, track, territory, period, and currency.",
     "statements"),
    ("costs", "Costs & profit",
     "Measured income beside the costs you choose to log.",
     "revenue-os"),
    ("recovery", "Recovery & claims",
     "Evidence-backed gaps, and the follow-up work on each.",
     "recovery"),
    ("people", "Contracts & people",
     "The documents and the people connected to the business.",
     "vault"),
)
# The five steps, EDUCATIONAL on a new account: Upload lit, the rest
# neutral, numbered as the owner's mockup numbers them, no percentage -
# "each statement can move through the workflow independently". STEPS
# (Statements .. Costs) stays the populated room's rail.
WORKFLOW = (
    ("upload", "Upload", "Add one statement"),
    ("review", "Review", "Confirm the import"),
    ("match", "Match", "Connect income to music"),
    ("investigate", "Investigate", "Find gaps and issues"),
    ("track", "Track", "See what you kept"),
)
ZERO_MONEY = ("Your money picture will appear here",
              "After the first statement is reviewed, Street Banker will organize "
              "income, sources, tracks, and periods.")
ZERO_LANGUAGE = ("No income is measured yet",
                 "Business uses Not measured until real paperwork exists. Missing "
                 "statements never become $0.")
ZERO_HELP = ("Not sure which statement to upload?",
             "Ask Street Banker which document gives you the clearest first picture.")
# The link under "Your money picture will appear here". The spec names
# two - "Supported statements" and "Import history" - and both would
# open the statements desk, which is one door under two names (the
# owner's own rule); an import history with nothing in it is the empty
# table the spec forbids. So: the one link, to the desk's intake.
ZERO_LINKS = (("Supported statements", "/statements?returnTo=/room/business#intake"),)
# The drawer at the foot: the spec's four categories, each tool by its
# room card, in place of one wall of eighteen. The populated room keeps
# its own three bands (owner, 2026-09-22).
ZERO_BANDS = (
    # In the room's own card order (tests/test_rooms.py holds every room
    # screen's first cards to rooms.ROOMS).
    ("Statements & royalties", ("royalties", "statements", "tax", "valuation")),
    ("Costs & profit", ("revenue-os",)),
    ("Recovery & claims", ("recovery", "cases", "money-queue", "disputes")),
    ("Contracts & people", ("vault", "contracts", "deals", "deal-simulator", "hours",
                            "team", "portal", "roster", "services")),
)
# The sentence the room carries back from the statements desk.
DONE_LINE = "Your first statement was added. Business is organizing what it reports."


def new_account(uploads, rows, expenses, cases, disputes):
    """The spec's new_account: confirmed empty on every count the room
    reads - no statement, no measured row, no cost, no claim, no dispute.
    Every argument is what the store returned; an unreadable store never
    reaches here - the route shows the error page instead."""
    return not uploads and not rows and not expenses and not cases and not disputes


def done_line(came_from, uploads):
    """Said by the SAVED statement, never by the param alone."""
    return DONE_LINE if came_from == "business-zero-state" and uploads > 0 else ""


def _tile(cards, key, can_open=None):
    """A tile from a room card, renamed where this room renames it, or
    None when there is no card or the seat cannot open its page."""
    card = (cards or {}).get(key)
    if not card:
        return None
    href = card[0]
    if can_open and not can_open(href):
        return None
    name, line = card[2], card[3]
    if key in RENAMED:
        name, line = RENAMED[key]
    # The owner's mark on a page they hid rides with the tile (rooms.build
    # keeps a hidden page for the owner alone); nothing else is judged.
    return {"key": key, "href": href, "icon": card[1], "name": name, "line": line,
            "state": card[4] if len(card) > 4 else ""}


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
        "lenses": lenses,
        "workflow": WORKFLOW,
        "money": ZERO_MONEY,
        "language": ZERO_LANGUAGE,
        "help": ZERO_HELP,
        "links": ZERO_LINKS,
        "bands": bands,
    }


# The reel a READING window shows while it has nothing to read (owner,
# 2026-09-22: no words in an empty window, icons). The one piece of the
# old standby still read: a populated analyser's empty windows.
STANDBY_FILL = ("reported", "named", "chased", "recovered", "kept", "upload")


def _six(icons):
    """Six stops, always: the roll's keyframes step through six, and a
    five-icon reel ran its last stop into blank glass."""
    icons = list(icons or ())
    while icons and len(icons) < 6:
        icons.append(icons[len(icons) % len(icons)])
    return icons[:6]


def standby():
    """What a populated analyser's empty windows fill with. The animated
    standby that once ran on an empty account is retired: that account
    meets the page from zero instead."""
    return {"fill": _six(STANDBY_FILL)}


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


def rack_screens(wins):
    """The working room's three screens on the rooms' shared plate (owner,
    2026-09-23): Reported, Not collected, Kept. Not collected stays TWO
    readings and never one sum: the actual unattributed figure is the
    screen's reading and the estimate is named as an estimate on the line
    under it. An absence is words, never a nought."""
    out = []
    for w in wins or ():
        if w.get("split"):
            actual, est = w["split"][0]["figure"], w["split"][1]["figure"]
            out.append({"k": w["label"], "v": actual["value"],
                        "fig": actual["measured"], "none": not actual["measured"],
                        "sub": "Actual unattributed · estimated missing %s" % est["value"]
                               if est["measured"] else "Actual unattributed · no estimate yet"})
            continue
        fig = w["figure"]
        if w.get("change"):
            sub = "%s %s%s" % ("▲" if w["change"]["up"] else "▼", w["change"]["pct"],
                               (" · " + w["note"]) if w.get("note") else "")
        else:
            sub = w.get("note") or ""
        out.append({"k": w["label"], "v": fig["value"], "fig": fig["measured"],
                    "none": not fig["measured"], "sub": sub})
    return out


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
          kept_note="", zero=None, can_add=True):
    """Everything the screen renders. No page logic beyond this.

    `zero` is new_account() decided by the route from every count the
    spec names (None here means: nothing reported, the old rule);
    `can_add` is who may upload a statement (see zero_page)."""
    # A band with nothing in it is not drawn - a Label-only card or a
    # seat's gate can empty one.
    bands, tiles = [], []
    for title, keys in BANDS:
        got = [t for t in (_tile(cards, k, can_open) for k in keys) if t]
        if got:
            bands.append({"title": title, "tiles": got})
            tiles.extend(got)
    if zero is None:
        zero = reported is None

    return {
        "artist_name": artist_name or "",
        "bands": bands,
        "windows": windows(reported, prior, actual, estimated, kept,
                           kept_prior, note, kept_note),
        "screens": rack_screens(windows(reported, prior, actual, estimated, kept,
                                        kept_prior, note, kept_note)),
        "measured": reported is not None,
        # Nothing on file on any count: the page from zero. One
        # statement, cost, claim or dispute and the analyser takes over
        # untouched, its readings in the screen's own green.
        "idle": bool(zero),
        "zero": zero_page(can_add, can_open, cards) if zero else None,
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

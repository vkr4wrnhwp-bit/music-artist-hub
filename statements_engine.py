"""Royalty-statement ingestion + real recovery analysis.

Parses distributor/PRO/MLC statement CSVs with flexible column detection
(every service names its columns differently), then runs genuinely
computable findings on the artist's own numbers:

- totals by source and by track (real)
- unmatched revenue: rows with no track title — money that can't be
  attributed (the "black box" made concrete) (real)
- cross-source coverage gaps: tracks earning on some sources but absent
  from others, with an estimated value based on that track's own average
  per-source earnings (estimate, labeled as such)
"""

import calendar
import csv
import datetime
import io
import math
import re

import catalog_value
import royalty_lag
import store_identity

# Header aliases -> canonical fields. Compared lowercased/stripped.
_TITLE_COLS = {"title", "track", "track title", "song", "song title", "track_name",
               "trackname", "song_name", "release title", "asset title", "work title"}
# The Statements page used to claim exports from Symphonic, DistroKid,
# TuneCore, ASCAP, BMI and The MLC all work. Only Symphonic had ever been
# tried, and since 2026-09-23 the page says so.
# CD Baby calls the store "Partner", which matched nothing - every row
# would have landed under "Unknown source", leaving income-by-store empty
# and the coverage analysis unable to see a second store at all.
_SOURCE_COLS = {"source", "platform", "store", "dsp", "retailer", "service",
                "store name", "channel", "distributor", "society",
                "partner", "outlet", "vendor", "storefront", "shop",
                "provider", "dsp name", "sales channel", "delivery channel"}
_AMOUNT_COLS = {"amount", "revenue", "earnings", "royalty", "royalties", "net",
                "net revenue", "net earnings", "payable", "total", "usd",
                "amount due", "net amount", "earnings (usd)", "royalty amount"}
_PERIOD_COLS = {"period", "date", "month", "statement period", "sales period",
                "reporting period", "sale month", "accounting period"}
_TERRITORY_COLS = {"territory", "country", "region", "market", "country code",
                   "country of sale", "sales territory"}
# The recording's own identifier. Worth capturing even though nothing
# needed it until now: a coverage gap can only be CHECKED against a
# store's catalogue by an exact identifier. Matching on a title alone
# fails on remixes, live versions, features and anything with a comma in
# it, and a wrong match here becomes a wrong claim in a letter.
_ISRC_COLS = {"isrc", "isrc code", "isrc_code", "recording isrc",
              "track isrc", "isrc/upc"}
# Whose recording the row is. A label's export carries every act on the
# roster in one file (2026-09-14: "it has multiple artists so it would be
# a label view"), and the Royalties desk reads one act at a time from it.
# A single artist's export usually has the column too; then every row
# names them and nothing changes.
_ARTIST_COLS = {"artist", "artist name", "artist_name", "artistname",
                "track artist", "release artist", "primary artist",
                "main artist", "performer", "act"}


_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun",
           "jul", "aug", "sep", "oct", "nov", "dec")


def period_year(period):
    """The calendar year a statement period belongs to, or "" if unknown.

    Distributors write periods however they like, and the Tax Center took
    the first four characters as the year. That works for "2026-06" and
    fails silently for Symphonic's "JUN-26", which yields "JUN-" - so a
    real catalogue's entire income was filed under "Undated", with the
    $600 reporting threshold evaluated against a bucket that meant nothing.

    Two-digit years read as 20xx. Royalty statements are recent by
    nature, and a 1926 pressing is not what anybody is uploading.
    """
    import re as _re

    text = (period or "").strip().lower()
    if not text:
        return ""
    four = _re.search(r"(19|20)\d{2}", text)
    if four:
        return four.group(0)
    months = "|".join(_MONTHS)
    two = _re.search(r"(?:^|[^a-z])(?:" + months + r")[a-z]*[^0-9]{0,3}(\d{2})(?![0-9])", text)
    if two:
        return "20" + two.group(1)
    bare = _re.fullmatch(r"(\d{2})", text)
    if bare:
        return "20" + bare.group(1)
    return ""

def _match(headers, aliases):
    for h in headers:
        if h.lower().strip() in aliases:
            return h
    # loose contains-match fallback (e.g. "Net Revenue (USD)")
    for h in headers:
        hl = h.lower()
        if any(a in hl for a in aliases if len(a) > 4):
            return h
    return None


def _to_amount(raw):
    if raw is None:
        return None
    s = str(raw).strip().replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    if not s:
        return None
    try:
        value = float(s)
    except ValueError:
        return None
    if not math.isfinite(value):
        # "NaN", "nan", "inf", "1e400": what a pandas or R export writes
        # for a blank cell. A blank cell, not a figure (walk, 2026-09-20:
        # a NaN row was a 500 and an inf row broke every money page).
        return None
    return round(value, 4)


def period_key(label):
    """(year, month) for ordering, for the ways distributors write a
    period: "2026-05", "MAY-26", "May 2026", "2026/05". Unknown shapes
    sort last, in the order they were written."""
    text = (label or "").strip().lower()
    m = re.match(r"^(\d{4})[-/](\d{1,2})", text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    for i, mon in enumerate(_MONTHS, 1):
        if text.startswith(mon):
            year = re.search(r"(\d{4}|\d{2})\b", text[3:])
            if year:
                y = int(year.group(1))
                return (y if y > 99 else 2000 + y, i)
    return (9999, 0)


def order_periods(labels):
    return sorted(set(labels), key=lambda p: (period_key(p), p))


def annualize(rows):
    """The one run rate every money page reads.

    Three pages used to annualise the same statements three ways
    (2026-09-14): Statements and Capital divided EVERY dollar, undated
    rows included, by the count of dated periods; Valuation averaged the
    dated months and left undated money out. The same account could show
    two run rates, and the Command Center's recorded valuation came from
    a third path. This is the rule now:

      dated money only, over the distinct periods it covers, times 12.

    Undated money is real and is reported beside the run rate; it is
    never spread across months it may not belong to. The months come
    back in calendar order whatever the distributor wrote ("JUN-26" after
    "MAY-26"), because a trend drawn in alphabetical order lies.
    """
    monthly, undated = {}, 0.0
    for r in rows or []:
        period = (r.get("period") or "").strip()
        amount = float(r.get("amount") or 0)
        if period:
            monthly[period] = monthly.get(period, 0.0) + amount
        else:
            undated += amount
    periods = order_periods(monthly)
    months = len(periods)
    dated = round(sum(monthly.values()), 2)
    return {
        "annualized": round(dated / months * 12, 2) if months else 0.0,
        "months": months,
        "dated_total": dated,
        "undated_total": round(undated, 2),
        "monthly": [(p, round(monthly[p], 2)) for p in periods],
    }


def parse_statement(data, filename="statement.csv"):
    """Parse CSV bytes/str -> {rows, columns, skipped, error}."""
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
    else:
        text = data

    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if not headers:
        return {"rows": [], "columns": {}, "skipped": 0, "error": "No header row found."}

    col_title = _match(headers, _TITLE_COLS)
    col_source = _match(headers, _SOURCE_COLS)
    col_amount = _match(headers, _AMOUNT_COLS)
    col_period = _match(headers, _PERIOD_COLS)
    col_territory = _match(headers, _TERRITORY_COLS)
    col_isrc = _match(headers, _ISRC_COLS)
    col_artist = _match(headers, _ARTIST_COLS)
    if not col_amount:
        return {"rows": [], "columns": {}, "skipped": 0,
                "error": "Couldn't find an amount/revenue column. Headers seen: " + ", ".join(headers)}

    rows, skipped = [], 0
    for raw in reader:
        amount = _to_amount(raw.get(col_amount))
        if amount is None:
            skipped += 1
            continue
        rows.append({
            "title": (raw.get(col_title) or "").strip() if col_title else "",
            "source": ((raw.get(col_source) or "").strip() if col_source else "") or "Unknown source",
            "amount": amount,
            "period": (raw.get(col_period) or "").strip() if col_period else "",
            "territory": (raw.get(col_territory) or "").strip() if col_territory else "",
            "isrc": ((raw.get(col_isrc) or "").strip().upper().replace("-", "")
                     if col_isrc else ""),
            "artist": (raw.get(col_artist) or "").strip() if col_artist else "",
        })

    return {
        "rows": rows,
        "columns": {"title": col_title, "source": col_source, "amount": col_amount,
                    "period": col_period, "territory": col_territory,
                    "isrc": col_isrc, "artist": col_artist},
        "skipped": skipped,
        "error": None if rows else "No usable rows found.",
    }


def analyze(rows):
    """Real findings from parsed statement rows."""
    if not rows:
        return None

    total = round(sum(r["amount"] for r in rows), 2)
    sources = {}
    tracks = {}
    store_totals = {}
    track_stores = {}
    unmatched = 0.0
    periods = set()
    artists = {}

    for r in rows:
        sources[r["source"]] = sources.get(r["source"], 0) + r["amount"]
        act = (r.get("artist") or "").strip()
        if act:
            slot = artists.setdefault(act, {"amount": 0.0, "titles": set()})
            slot["amount"] += r["amount"]
            if r["title"]:
                slot["titles"].add(r["title"])
        title = r["title"] or "(no title)"
        if not r["title"]:
            unmatched += r["amount"]
        tracks.setdefault(title, {}).setdefault(r["source"], 0)
        tracks[title][r["source"]] += r["amount"]
        # The delivery question is per STORE. A report names revenue
        # lines - six of Hungry Gods' twenty-seven "missing" sources were
        # tiers of Amazon, Qobuz and YouTube, all three of which it was
        # already earning on.
        store = store_identity.store_of(r["source"])
        store_totals[store] = store_totals.get(store, 0) + r["amount"]
        track_stores.setdefault(title, {}).setdefault(store, 0)
        track_stores[title][store] += r["amount"]
        if r["period"]:
            periods.add(r["period"])

    by_source = sorted(({"source": s, "amount": round(a, 2)} for s, a in sources.items()),
                       key=lambda x: x["amount"], reverse=True)
    by_track = sorted(
        ({"title": t, "amount": round(sum(m.values()), 2), "sources": len(m),
          "stores": len(track_stores.get(t, {}))} for t, m in tracks.items()),
        key=lambda x: x["amount"], reverse=True)

    # Cross-source coverage gaps (estimate): a titled track missing from
    # sources where other tracks earn.
    #
    # This used to be the track's own AVERAGE per-source earnings times
    # the COUNT of missing sources, which treats every store as equally
    # valuable. On a real Symphonic report the biggest source was 50.3%
    # of all earnings and the smallest was 0.0001%, so a missing Qobuz
    # (JPY) listing was valued the same as a missing Spotify one. The
    # page then told the artist they might be owed $3,079 against $3,278
    # earned - 94% - when weighting by each store's actual share says
    # about 3%. That is a number a label takes apart in the first
    # meeting, and with the letter feature it would have gone to a
    # distributor in writing.
    #
    # Now: this track is X% of the catalogue's money, so on a store it is
    # missing from it would have earned roughly X% of what that store
    # paid overall. Bounded by construction - a track present only on a
    # negligible store cannot extrapolate to a fortune, which the
    # coverage-ratio alternative does.
    # Only stores a recording is actually DELIVERED to. A society and a
    # licensing arrangement collect on use; nothing is delivered to them,
    # so their absence is not evidence of anything and reporting it as a
    # gap is a false alarm an artist would send to a distributor.
    all_stores = {st for st in store_totals if store_identity.is_deliverable(st)}
    findings = []
    for title, per_store in track_stores.items():
        if title == "(no title)":
            continue
        missing = all_stores - set(per_store)
        if not missing or len(all_stores) < 2:
            continue
        track_total = sum(per_store.values())
        share = (track_total / total) if total else 0
        est = round(share * sum(store_totals[st] for st in missing), 2)
        if est <= 0:
            continue
        findings.append({
            "title": title,
            "missing_sources": sorted(missing),
            "estimated_value": est,
        })
    findings.sort(key=lambda f: f["estimated_value"], reverse=True)

    return {
        "total": total,
        "row_count": len(rows),
        "source_count": len(sources),
        # 49 report lines from Symphonic are 29 stores: YouTube alone
        # arrives as Streaming, Shorts, Content ID and Audio Tier. The
        # page says both, so "49 sources" stops reading as 49 shops.
        "store_count": len(store_identity.group(sources)),
        "period_count": len(periods),
        "by_source": by_source,
        # Every track, not the first fifteen: the cap here made a 40-track
        # catalogue read as "15 tracks" on three pages and put 15 into the
        # benchmark as the catalogue size. Pages fold their own long tails.
        "by_track": by_track,
        "track_count": sum(1 for t in tracks if t != "(no title)"),
        "unmatched_revenue": round(unmatched, 2),
        # The roster, when the export names one: each act's money and how
        # many of its titles earned. Rows without an artist column are
        # not an act; a one-artist export yields one entry.
        "by_artist": sorted(
            ({"artist": a, "amount": round(v["amount"], 2), "tracks": len(v["titles"]),
              "share": round(v["amount"] / total, 4) if total else 0.0}
             for a, v in artists.items()),
            key=lambda x: x["amount"], reverse=True),
        "artist_count": len(artists),
        "coverage_gaps": findings,
        "gap_estimate_total": round(sum(f["estimated_value"] for f in findings), 2),
    }


def build_royalty_summary(rows):
    """Everything the money pages need from real uploaded statements:
    the core analysis plus a monthly trend and an honest catalog-value
    estimate (labeled, never presented as financial advice)."""
    result = analyze(rows)
    if result is None:
        return None
    # One run rate (annualize) and one calendar order for the trend. The
    # band itself is catalog_value's to decide - this used to hardcode a
    # second copy of 3/4/5, and epk_config.real_stats reads the answer
    # straight onto a press kit.
    run = annualize(rows)
    result["monthly_trend"] = run["monthly"][-12:]
    result["annualized"] = run["annualized"]
    result["annualized_months"] = run["months"]
    result["undated_revenue"] = run["undated_total"]
    result["valuation"] = catalog_value.band(run["annualized"])
    return result


# --- REPORTING LAG --------------------------------------------------------
#
# royalty_lag.py answers "is this platform late, or is this just how long
# it takes?" for one source and one period. It has been tested since it
# was written and imported by nothing, so no artist had ever seen it.
# This turns the rows an account has uploaded into the inputs it needs.
#
# WHAT THIS ACCOUNT CANNOT KNOW, AND THEREFORE NEVER SAYS
#
# Nothing in this app records the day a distributor actually reported a
# period. A statement row carries the PERIOD it covers; the statements
# table carries the day the ARTIST uploaded the CSV. Those are different
# facts. An artist who exports quarterly and uploads when they remember
# would have their own habits measured, averaged and printed under the
# platform's name, and it would carry the authority of "measured from
# your own statements" while being a fact about the artist.
#
# So royalty_lag.observed_days is deliberately not called from here, and
# `observed` is never passed to judge(). Every verdict rests on the
# published order-of-magnitude figure for the platform, which the page
# says in the reader's words and never as this account's own. A store
# with no published figure gets no verdict at all.
#
# What IS computable, and is all that is shown: a period ended on a known
# date, today is a known date, and no statement on file covers that
# period. The wait so far is the difference. How long a period that HAS
# arrived took is not computable here, and the page says so rather than
# offering the upload day in its place.
#
# This is NOT the coverage gap above. A coverage gap asks whether a TRACK
# is missing from a store its siblings reported to, and the remedy is a
# delivery or an accounting request. This asks whether a SOURCE has
# reported for a PERIOD yet, and the remedy is to wait or to chase.

# Reader-facing words for each state royalty_lag can return. A state is
# never carried by colour alone, so every row prints one of these.
LAG_WORDS = {
    "reported": "Reported",
    "normal": "Normal",
    "slow": "Slow",
    "overdue": "Overdue",
    "unknown": "No reading",
}

# What the verdict rests on, in the reader's words rather than the code's.
# "typical" must never read as this account's own figure. "measured" is
# unreachable today and is kept only so a future caller that has a real
# distributor reporting date cannot hand this a basis it cannot name.
LAG_BASIS_WORDS = {
    "measured": "measured from your own statements",
    "typical": "a general figure for this platform, not yours",
    "unknown": "no figure for this platform, and none assumed",
}

# Worth chasing first, then worth knowing, then the ones behaving. A
# store with no reading sits ABOVE the ones that are fine: it is not a
# pass and must not be tidied away below them.
_LAG_ORDER = {"overdue": 0, "slow": 1, "unknown": 2, "normal": 3, "reported": 4}


def _period_end(label):
    """The last day of the month a statement period covers, or None.

    Reads the same shapes period_key does ("2026-05", "MAY-26",
    "May 2026", "2026/05"). A period nobody can date returns None and
    gets no verdict at all rather than a guessed one.
    """
    year, month = period_key(label)
    if year == 9999 or not 1 <= month <= 12:
        return None
    return datetime.date(year, month, calendar.monthrange(year, month)[1])


def _end_of_next_month(day):
    """The last day of the month after this one."""
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    return datetime.date(year, month, calendar.monthrange(year, month)[1])


def _month_name(day):
    return "%s %d" % (_MONTHS[day.month - 1].title(), day.year)


def _names(items):
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def reporting_lag(rows, today=None):
    """Per store: has it reported for the period it owes, and is that
    normal for it?

    `rows` are statement rows as db.get_statement_rows returns them. No
    upload date is read: see the note above. Returns {"rows", "flagged",
    "settled", "summary"} always, with an empty row list when an account
    has nothing on file, so a new artist is shown that there is no
    reading yet rather than a quiet pass.
    """
    today = today or datetime.date.today()

    money, lines, ends = {}, {}, {}
    for r in rows or ():
        store = store_identity.store_of(r.get("source"))
        try:
            amount = float(r.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if not math.isfinite(amount):
            amount = 0.0
        money[store] = money.get(store, 0.0) + amount
        name = (r.get("source") or "").strip()
        if name:
            lines.setdefault(store, set()).add(name)
        end = _period_end(r.get("period"))
        if end is None:
            continue          # a period nobody can date gets no verdict
        ends.setdefault(store, set()).add(end)

    out = []
    for store in sorted(money):
        seen_ends = sorted(ends.get(store, ()))
        latest = seen_ends[-1] if seen_ends else None
        waiting_for = ""
        if latest is None:
            judgement = royalty_lag.judge(store, None, today)
            arrived_note = ("Nothing on this store's rows says which period they "
                            "cover, so there is no reading for it.")
        else:
            latest_label = _month_name(latest)
            due = _end_of_next_month(latest)
            if due > today:
                # The next period has not ended, so nothing is outstanding.
                # How long this one took is not on file, so no figure is
                # offered in place of it.
                expected = royalty_lag.expectation(store)
                judgement = {"state": "reported", "waited": None,
                             "expected": expected["days"], "basis": expected["basis"],
                             "detail": expected["detail"],
                             "headline": "%s has arrived" % latest_label}
            else:
                judgement = royalty_lag.judge(store, due, today)
                waiting_for = _month_name(due)
            arrived_note = ("%s is the latest period on file for this store. How long "
                            "it took to arrive is not recorded anywhere, so no figure "
                            "is given for it." % latest_label)

        state = judgement["state"]
        out.append({
            "store": store,
            "amount": round(money[store], 2),
            "lines": len(lines.get(store, ())) or 1,
            "state": state,
            "word": LAG_WORDS[state],
            "headline": judgement["headline"],
            "detail": judgement["detail"],
            "basis": judgement["basis"],
            "basis_word": LAG_BASIS_WORDS[judgement["basis"]],
            "waited": judgement["waited"],
            "expected": judgement["expected"],
            "waiting_for": waiting_for,
            "arrived_note": arrived_note,
        })
    out.sort(key=lambda r: (_LAG_ORDER[r["state"]], -r["amount"], r["store"]))
    settled = ("normal", "reported")
    return {
        "rows": out,
        # Split for the page: what is worth a look, and what is only a
        # platform being a platform. Both are shown - the reassurance is
        # half the point - but the second half folds.
        "flagged": [r for r in out if r["state"] not in settled],
        "settled": [r for r in out if r["state"] in settled],
        "summary": _lag_summary(out),
    }


def _lag_summary(out):
    """The one sentence above the list, and what it rests on."""
    overdue = [r["store"] for r in out if r["state"] == "overdue"]
    slow = [r["store"] for r in out if r["state"] == "slow"]
    blind = [r["store"] for r in out if r["state"] == "unknown"]
    settled = [r for r in out if r["state"] in ("normal", "reported")]

    if not out:
        headline = "No statements on file yet, so there is no reading for any store."
    elif overdue:
        headline = ("%s %s far enough past the usual wait to be worth asking about."
                    % (_names(overdue), "is" if len(overdue) == 1 else "are"))
    elif slow:
        headline = ("Nothing is overdue. %s %s a little past the usual wait, which is "
                    "common and is not on its own a sign of a problem."
                    % (_names(slow), "is" if len(slow) == 1 else "are"))
    elif settled:
        headline = ("Every store that has reported here is inside the wait it normally "
                    "takes. There is nothing to chase.")
    else:
        headline = "Nothing here can be judged either way yet."

    if blind:
        blind_note = ("%s %s no reading at all. Nothing is known about how long %s take%s "
                      "to report and nothing has been assumed, so silence from %s means "
                      "neither good news nor bad."
                      % (_names(blind), "has" if len(blind) == 1 else "have",
                         "it" if len(blind) == 1 else "they",
                         "s" if len(blind) == 1 else "",
                         "it" if len(blind) == 1 else "them"))
    else:
        blind_note = ""

    if out:
        # "None of these numbers" would be the literal word None in the
        # page source, and two money-desk tests lock that word out: it is
        # how a Python None leaking into a template is caught.
        basis_note = ("Every verdict here rests on a published figure for the platform, "
                      "because this app has no record of the day a distributor reported. "
                      "Not one of these figures is measured from your account.")
    else:
        basis_note = ""

    return {
        "headline": headline,
        "blind_note": blind_note,
        "basis_note": basis_note,
        "overdue": overdue,
        "slow": slow,
        "blind": blind,
        "settled_count": len(settled),
    }

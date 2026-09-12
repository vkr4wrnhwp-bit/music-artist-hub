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

import csv
import io

import catalog_value
import store_identity

# Header aliases -> canonical fields. Compared lowercased/stripped.
_TITLE_COLS = {"title", "track", "track title", "song", "song title", "track_name",
               "trackname", "song_name", "release title", "asset title", "work title"}
_SOURCE_COLS = {"source", "platform", "store", "dsp", "retailer", "service",
                "store name", "channel", "distributor", "society"}
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
        return round(float(s), 4)
    except ValueError:
        return None


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
        })

    return {
        "rows": rows,
        "columns": {"title": col_title, "source": col_source, "amount": col_amount,
                    "period": col_period, "territory": col_territory,
                    "isrc": col_isrc},
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

    for r in rows:
        sources[r["source"]] = sources.get(r["source"], 0) + r["amount"]
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
        ({"title": t, "amount": round(sum(m.values()), 2), "sources": len(m)} for t, m in tracks.items()),
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
        "period_count": len(periods),
        "by_source": by_source,
        "by_track": by_track[:15],
        "unmatched_revenue": round(unmatched, 2),
        "coverage_gaps": findings[:15],
        "gap_estimate_total": round(sum(f["estimated_value"] for f in findings), 2),
    }


def build_royalty_summary(rows):
    """Everything the money pages need from real uploaded statements:
    the core analysis plus a monthly trend and an honest catalog-value
    estimate (labeled, never presented as financial advice)."""
    result = analyze(rows)
    if result is None:
        return None
    monthly = {}
    for r in rows:
        if r["period"]:
            monthly[r["period"]] = monthly.get(r["period"], 0) + r["amount"]
    trend = [(p, round(a, 2)) for p, a in sorted(monthly.items())]
    result["monthly_trend"] = trend[-12:]
    # Valuation signal: annualize the average tracked month, apply the
    # conservative independent-catalog multiple range. The band itself is
    # catalog_value's to decide - this used to hardcode a second copy of
    # 3/4/5, and epk_config.real_stats reads the answer straight onto a
    # press kit.
    months = max(len(monthly), 1)
    annualized = round(result["total"] / months * 12, 2)
    result["annualized"] = annualized
    result["valuation"] = catalog_value.band(annualized)
    return result

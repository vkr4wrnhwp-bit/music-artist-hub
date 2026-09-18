"""Bring in a fan list from wherever it lives now.

The Fans page could only import from one connected Shopify store, which
belongs to the owner. An artist whose list sits in Mailchimp, Klaviyo,
Bandcamp, Eventbrite, Squarespace or a spreadsheet had no way in at all
(owner, 2026-09-17).

Every one of those tools exports a CSV, and they disagree about almost
everything: the column is Email or "Email Address" or "Email_Address",
the consent column is Status or "Accepts Email Marketing" or "Email
Marketing Consent", and the value meaning yes is "subscribed" or "yes" or
"TRUE" or "1". So the columns are read rather than demanded, and anything
unrecognised is reported instead of guessed at.

Two rules run through this:

  Never invent consent. A row that says unsubscribed, cleaned, bounced or
  never subscribed is left out and counted, whatever the artist ticked. A
  file with no consent column at all is not read as permission; the artist
  has to say so themselves, and what they said is what gets recorded.

  Never silently drop anything. Every row that does not come in is counted
  under a reason, and the reasons add up to the number of rows read. A
  summary that does not add up is how a list quietly loses half of itself.
"""

import csv
import io
import re

EMAIL_HEADERS = ("email", "email address", "email_address", "e-mail", "emailaddress",
                 "email addresses", "contact email", "primary email", "mail")
NAME_HEADERS = ("name", "full name", "full_name", "display name", "customer name",
                "contact name", "subscriber name")
FIRST_HEADERS = ("first name", "first_name", "firstname", "given name")
LAST_HEADERS = ("last name", "last_name", "lastname", "surname", "family name")
# Where somebody is, as the exporting tool spells it. Read, never
# inferred: an email domain says nothing reliable about a person's
# country, and a list that quietly invents locations is worse than one
# that admits it does not know (owner, 2026-09-18).
COUNTRY_HEADERS = ("country", "country code", "country_code", "country name",
                   "billing country", "shipping country", "addr country",
                   "address country", "region", "nation")
CITY_HEADERS = ("city", "town", "billing city", "shipping city", "locality",
                "address city", "addr city")

STATUS_HEADERS = ("status", "subscribed", "email marketing consent",
                  "accepts email marketing", "marketing consent", "consent",
                  "subscription status", "email subscription", "opt in", "opt-in",
                  "email opt in", "member status", "state")

# What each tool writes when the answer is no. Mailchimp says cleaned for an
# address that kept bouncing and unsubscribed for a person who left; both
# mean do not mail this person, and both used to arrive as a fan.
NO_VALUES = {"unsubscribed", "cleaned", "bounced", "no", "false", "0", "n",
             "never_subscribed", "never subscribed", "opted_out", "opted out",
             "spam", "complained", "declined", "pending", "inactive", "archived",
             "suppressed", "unconfirmed", "hard bounce", "soft bounce"}
YES_VALUES = {"subscribed", "yes", "true", "1", "y", "active", "opted_in",
              "opted in", "confirmed", "enabled", "ok"}

_EMAIL = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]{2,}$")

MAX_ROWS = 50000


def _norm(header):
    return re.sub(r"[\s_]+", " ", (header or "").strip().lower()).strip()


def _sniff_delimiter(text):
    head = text[:4096]
    counts = {d: head.count(d) for d in (",", ";", "\t", "|")}
    best = max(counts, key=counts.get)
    return best if counts[best] else ","


def read_columns(text):
    """Which column is which, read from the header row.

    Returns {"email", "name", "first", "last", "status", "country",
    "city", "headers", "delimiter"}; the values are column indexes, or None
    where that column is not in the file. email is None when nothing in the
    header looks like an address column, which is the one thing this cannot
    work without. country and city are usually None, and that is fine: a
    fan with no location is Unknown rather than missing.
    """
    delimiter = _sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        headers = next(reader)
    except StopIteration:
        return {"email": None, "name": None, "first": None, "last": None,
                "status": None, "country": None, "city": None,
                "headers": [], "delimiter": delimiter}
    found = {"email": None, "name": None, "first": None, "last": None,
             "status": None, "country": None, "city": None}
    for i, raw in enumerate(headers):
        h = _norm(raw)
        if found["email"] is None and h in EMAIL_HEADERS:
            found["email"] = i
        elif found["first"] is None and h in FIRST_HEADERS:
            found["first"] = i
        elif found["last"] is None and h in LAST_HEADERS:
            found["last"] = i
        elif found["name"] is None and h in NAME_HEADERS:
            found["name"] = i
        elif found["status"] is None and h in STATUS_HEADERS:
            found["status"] = i
        elif found["country"] is None and h in COUNTRY_HEADERS:
            found["country"] = i
        elif found["city"] is None and h in CITY_HEADERS:
            found["city"] = i
    # A file with no header row at all, just addresses: in the first column,
    # or several to a line (a block pasted from a mail client).
    if found["email"] is None and headers and _addresses_in(headers[0]):
        found["email"] = 0
        headers = []
    found["headers"] = headers
    found["delimiter"] = delimiter
    return found


_SPLIT = re.compile(r"[\s,;|]+")


def _addresses_in(cell):
    """The things in one cell that look like addresses at all (they carry
    an @). Used only for a list with no header row, where one line can hold
    several: "a@x.com, b@x.com; c@x.com"."""
    # "Jo Park <jo@x.com>" is how a mail client copies a person; the
    # brackets and quotes are wrapping, not part of the address.
    return [t.strip("<>\"'()[]") for t in _SPLIT.split((cell or "").strip()) if "@" in t]


def _headerless_emails(row):
    """Every address on one line of a list with no header row, in order.

    The paste box invites "a block copied from anywhere", and a block
    copied out of a mail client puts several addresses on one line. This
    used to read the first cell only, so every address after the first
    vanished with no reason given and the ledger still added up, because it
    counted lines (review, 2026-09-18). Now each address is its own row.
    Cells with no @ (a name typed beside an address) are not addresses and
    are ignored, as they always were. A line with no @ anywhere is one row,
    read from its first cell, so it is still counted under a reason."""
    found = []
    for c in row:
        found.extend(_addresses_in(c))
    return found or [(row[0] if row else "")]


def _consent(value):
    """True, False, or None when the file does not say. None is not yes."""
    v = _norm(value)
    if not v:
        return None
    if v in NO_VALUES:
        return False
    if v in YES_VALUES:
        return True
    return None


def parse(text, limit=MAX_ROWS):
    """Read a list. Returns {"rows", "skipped", "columns", "had_header",
    "has_status_column", "read"}.

    `rows` are the ones that can come in: {"email", "name"}. `skipped` is
    every row that cannot, each with its reason, so the counts add up to
    the number of rows read.
    """
    text = (text or "").lstrip("﻿")
    cols = read_columns(text)
    out = {"rows": [], "skipped": [], "columns": cols,
           "had_header": bool(cols["headers"]),
           "has_status_column": cols["status"] is not None,
           "has_location": cols["country"] is not None or cols["city"] is not None,
           "read": 0, "truncated": False}
    if cols["email"] is None:
        return out

    reader = csv.reader(io.StringIO(text), delimiter=cols["delimiter"])
    if cols["headers"]:
        next(reader, None)
    seen = set()
    headerless = not cols["headers"]

    def lines():
        # One (line number, row, address) per row to read. A headed file is
        # one row a line; a headerless list can carry several addresses on
        # a line, and each is read and counted as its own row.
        for line_no, row in enumerate(reader, start=1 if headerless else 2):
            if not row or not any((c or "").strip() for c in row):
                continue
            if headerless:
                for address in _headerless_emails(row):
                    yield line_no, [address], address
            else:
                i = cols["email"]
                yield line_no, row, (row[i] if i < len(row) else "")

    for line_no, row, raw_email in lines():
        if out["read"] >= limit:
            out["truncated"] = True
            break
        out["read"] += 1

        def cell(key):
            i = cols[key]
            if headerless:
                return ""
            return (row[i].strip() if i is not None and i < len(row) else "")

        email = (raw_email or "").strip().lower()
        if not email:
            out["skipped"].append({"line": line_no, "email": "", "why": "no email address"})
            continue
        if not _EMAIL.match(email):
            out["skipped"].append({"line": line_no, "email": email,
                                   "why": "not a readable email address"})
            continue
        said = _consent(cell("status"))
        if said is False:
            out["skipped"].append({"line": line_no, "email": email,
                                   "why": "their list says unsubscribed"})
            continue
        if email in seen:
            out["skipped"].append({"line": line_no, "email": email,
                                   "why": "the same address twice in this file"})
            continue
        seen.add(email)
        name = cell("name") or " ".join(p for p in (cell("first"), cell("last")) if p)
        out["rows"].append({"email": email, "name": name.strip(),
                            "country": cell("country")[:80],
                            "city": cell("city")[:80]})
    return out


def preview(parsed, known_emails=()):
    """What would happen, before anything happens. Counts only, and they add
    up: new + already here + every skipped reason equals the rows read."""
    known = {e.strip().lower() for e in known_emails or ()}
    new = [r for r in parsed["rows"] if r["email"] not in known]
    already = len(parsed["rows"]) - len(new)
    reasons = {}
    for s in parsed["skipped"]:
        reasons[s["why"]] = reasons.get(s["why"], 0) + 1
    counted = len(new) + already + sum(reasons.values())
    return {
        "read": parsed["read"],
        "new": len(new),
        "already_here": already,
        "skipped": sum(reasons.values()),
        "reasons": reasons,
        "adds_up": counted == parsed["read"],
        "truncated": parsed["truncated"],
        "has_status_column": parsed["has_status_column"],
        # So the page can say "this file carried no locations" rather than
        # showing every fan under Unknown with no explanation.
        "has_location": bool(parsed.get("has_location")),
        "located": sum(1 for r in parsed["rows"] if r.get("country") or r.get("city")),
        "sample": [r["email"] for r in new[:5]],
    }


def draft_rows(parsed, on_file=None):
    """The rows a preview promises, each marked new or already here as the
    preview counted it. Confirm files these and nothing else.

    `on_file` maps each address already on file to its record (at least
    country and city). A row already on file is marked `fills` only when
    the file carries a country or city that the record is missing: that is
    the one thing confirm changes about a fan already here. A place the
    record already holds is never replaced (review, 2026-09-18: confirm
    used to overwrite Lyon with Berlin while the preview said "left as they
    are")."""
    on_file = {(e or "").strip().lower(): (rec or {})
               for e, rec in (on_file or {}).items()}
    out = []
    for r in parsed["rows"]:
        rec = on_file.get(r["email"])
        if rec is None:
            out.append(dict(r, new=True, fills=False))
        else:
            fills = bool((r.get("country") and not (rec.get("country") or "").strip())
                         or (r.get("city") and not (rec.get("city") or "").strip()))
            out.append(dict(r, new=False, fills=fills))
    return out


def mask_email(email):
    """a***@example.com: enough to recognise a list, not enough to lift one
    off a screen share."""
    email = (email or "").strip()
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return "%s***@%s" % (local[:1], domain)


def sample(rows, n=6):
    """A few rows as the preview shows them: the new ones first, the email
    masked, the place exactly as the file gave it (blank when it gave none)."""
    ordered = [r for r in rows if r.get("new")] + [r for r in rows if not r.get("new")]
    return [{"name": r.get("name") or "", "email": mask_email(r.get("email")),
             "city": r.get("city") or "", "country": r.get("country") or "",
             "new": bool(r.get("new"))} for r in ordered[:n]]


def consent_note(source, when, has_status_column):
    """What goes on each imported fan's consent record. It says where the
    list came from and that the artist vouched for it, because that is what
    happened. It never claims the fan agreed inside Street Banker."""
    where = (source or "").strip() or "an uploaded list"
    line = ("Imported from %s. The artist confirmed on %s that these people "
            "agreed to hear from them." % (where, when))
    if not has_status_column:
        line += (" That list carried no subscribed or unsubscribed column, so "
                 "the artist's word is the only record of consent.")
    return line

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

    Returns {"email", "name", "first", "last", "status", "headers",
    "delimiter"}; the values are column indexes, or None where that column
    is not in the file. email is None when nothing in the header looks like
    an address column, which is the one thing this cannot work without.
    """
    delimiter = _sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        headers = next(reader)
    except StopIteration:
        return {"email": None, "name": None, "first": None, "last": None,
                "status": None, "headers": [], "delimiter": delimiter}
    found = {"email": None, "name": None, "first": None, "last": None, "status": None}
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
    # A file with no header row at all, just addresses in the first column.
    if found["email"] is None and headers and _EMAIL.match((headers[0] or "").strip()):
        found["email"] = 0
        headers = []
    found["headers"] = headers
    found["delimiter"] = delimiter
    return found


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
           "read": 0, "truncated": False}
    if cols["email"] is None:
        return out

    reader = csv.reader(io.StringIO(text), delimiter=cols["delimiter"])
    if cols["headers"]:
        next(reader, None)
    seen = set()
    for line_no, row in enumerate(reader, start=2 if cols["headers"] else 1):
        if not row or not any((c or "").strip() for c in row):
            continue
        if out["read"] >= limit:
            out["truncated"] = True
            break
        out["read"] += 1

        def cell(key):
            i = cols[key]
            return (row[i].strip() if i is not None and i < len(row) else "")

        email = cell("email").lower()
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
        out["rows"].append({"email": email, "name": name.strip()})
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
        "sample": [r["email"] for r in new[:5]],
    }


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

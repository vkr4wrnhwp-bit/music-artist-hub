"""Renewal reminders for the contracts in the vault.

The vault filed a contract and never read it; nothing in the product
reminded anyone of anything (owner, 2026-09-14: "is there a reminder
alarm built to notify you when your auto renewals are coming up?").
This is the half that needs no reader: the artist types the renewal
date and the notice period on the contract's row, and the app tells
them at 60, 30, 7 and 1 days before the notice deadline -
in the app, and by email where the deployment can send one.

The other half - reading the dates out of the document itself - waits
on a PDF reader and a decision about it. Until then a date here is one
a person typed, which is the honest state and is said on the page.

Rules:
  * the deadline that matters is the NOTICE date (renewal minus the
    notice period), because that is the last day a person can act
  * each milestone fires once per contract; if terms are set inside
    the 60-day window, only the nearest milestone fires and the ones
    already passed are recorded as superseded, so nobody gets three
    alarms at once for one contract
  * nothing fires for a contract whose renewal is in the past: the
    page says the date needs updating instead
"""
from datetime import date, timedelta

import db as store

# Days before the notice deadline; 0 is the deadline itself.
# The owner's numbers (2026-09-22): 60, 30, 7 and "24 hours out". The
# job runs once a day, at 09:00 UTC, so 24 hours is the 1-day milestone
# - the day before the deadline - not an exact hour. There is no 0: a
# warning on the deadline itself is too late to act on.
MILESTONES = (60, 30, 7, 1)


def _day(text):
    try:
        return date.fromisoformat((text or "")[:10])
    except ValueError:
        return None


def _say(d):
    return "%d %s %d" % (d.day, d.strftime("%b"), d.year)


def status(terms, today=None):
    """What the row says about a contract's terms, or None with no date."""
    today = today or date.today()
    renews = _day((terms or {}).get("renews_on"))
    if not renews:
        return None
    notice_days = int((terms or {}).get("notice_days") or 0)
    notice_by = renews - timedelta(days=notice_days)
    days_left = (notice_by - today).days
    auto = bool((terms or {}).get("auto_renews"))
    if renews < today:
        phase = "passed"
        sentence = ("Renewal date %s has passed%s. Update the date." %
                    (_say(renews), " and it auto-renews" if auto else ""))
    elif days_left < 0:
        phase = "notice_closed"
        sentence = ("Notice deadline %s has passed; it renews on %s%s." %
                    (_say(notice_by), _say(renews), " automatically" if auto else ""))
    else:
        phase = "open"
        when = ("today" if days_left == 0 else
                "tomorrow" if days_left == 1 else "in %d days" % days_left)
        sentence = ("Renews %s%s. Give notice by %s, %s." %
                    (_say(renews), " automatically" if auto else "", _say(notice_by), when))
    return {"renews_on": renews.isoformat(), "notice_by": notice_by.isoformat(),
            "days_left": days_left, "phase": phase, "auto_renews": auto,
            "sentence": sentence, "notice_days": notice_days}


def due_milestone(terms, today, sent):
    """The one milestone to fire now, and every milestone it supersedes.

    Returns (milestone, superseded) or (None, []). `sent` is the set of
    milestones already recorded for this contract."""
    st = status(terms, today)
    if not st or st["phase"] == "passed":
        return None, []
    notice_by = _day(st["notice_by"])
    due = [m for m in MILESTONES if m not in sent and today >= notice_by - timedelta(days=m)]
    if not due:
        return None, []
    nearest = min(due)
    return nearest, [m for m in due if m != nearest]


def _subject(doc, st, milestone):
    when = ("is tomorrow" if milestone == 1
            else "is today" if milestone == 0
            else "is in %d days" % milestone)
    return "Notice deadline for %s %s" % (doc.get("filename") or "a contract", when)


def _body(doc, st, milestone):
    lines = [
        st["sentence"],
        "Filed as %s%s." % (doc.get("doc_type") or "a document",
                            (" for " + doc["track"]) if doc.get("track") else ""),
        "This date was typed on the contract's row in the vault; nobody has read the document.",
    ]
    return " ".join(lines)


def run(today=None, emailer=None, public_url=None):
    """Fire every reminder that is due. Returns counts, for the record.

    `emailer` is the app's mail module (or None to send nothing);
    `public_url` builds the absolute link for the mail."""
    today = today or date.today()
    checked, sent, emailed = 0, 0, 0
    for row in store.list_document_terms():
        checked += 1
        already = store.reminders_sent(row["document_id"])
        milestone, superseded = due_milestone(row, today, already)
        if milestone is None:
            continue
        st = status(row, today)
        doc = {"filename": row.get("filename"), "doc_type": row.get("doc_type"),
               "track": row.get("track")}
        title = _subject(doc, st, milestone)
        body = _body(doc, st, milestone)
        store.notify(row["user_id"], "contract", title[:200], body[:400], "/vault?view=contracts")
        for m in superseded:
            store.mark_reminder_sent(row["user_id"], row["document_id"], m, "superseded")
        ok = False
        if emailer is not None and row.get("email"):
            try:
                if emailer.configured() and not emailer.using_shared_test_sender():
                    link = public_url("/vault?view=contracts") if public_url else "/vault?view=contracts"
                    ok = bool(emailer.send(
                        row["email"], title,
                        '<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">'
                        "<h2>%s</h2><p>%s</p>"
                        '<p><a href="%s" style="display:inline-block;background:#E8B950;color:#14100A;'
                        'font-weight:bold;padding:12px 24px;border-radius:10px;text-decoration:none;">'
                        "Open the vault</a></p>"
                        '<p style="color:#91836A;font-size:12px;">You set this reminder on the contract\'s '
                        "row. Change the dates there and the reminders follow.</p></div>"
                        % (_esc(title), _esc(body), link)))
            except Exception:          # noqa: BLE001 - a mail failure never stops the in-app reminder
                ok = False
        store.mark_reminder_sent(row["user_id"], row["document_id"], milestone,
                                 "emailed" if ok else "notified")
        sent += 1
        emailed += 1 if ok else 0
    return {"checked": checked, "sent": sent, "emailed": emailed, "date": today.isoformat()}


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))

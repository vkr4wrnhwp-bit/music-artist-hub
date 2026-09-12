"""The letter an artist sends their distributor about a coverage gap.

Drafted, never sent. A letter about money is the artist's to send from
their own address, under their own name - the app assembles the evidence
and gets out of the way.

Which letter depends entirely on what the store check found, and the
three are not interchangeable:

  CARRIED   the store lists the recording and the statement shows nothing
            from it. That is a question about accounting, and it is the
            only one that mentions money.

  ABSENT    the store does not list it. Nobody owes anything; the ask is
            delivery. Sending a payment demand here is how an artist
            burns the credibility they will need for a real claim.

  UNCHECKED nothing was established. The letter asks the distributor to
            confirm, and states plainly that the app could not - rather
            than implying a check that never happened.

The estimate is deliberately the last thing in the letter and is labelled
as an estimate with its method in one line. It is a reason to look, not a
figure to invoice: the previous estimator reported 94% of a real
catalogue's earnings as recoverable, and a number like that in writing is
retracted in the first reply.
"""

_GREETING = "Hello,"


def _fmt_list(items, limit=12):
    items = list(items)
    if not items:
        return ""
    if len(items) > limit:
        return "%s, and %d more" % (", ".join(items[:limit]), len(items) - limit)
    if len(items) == 1:
        return items[0]
    # A letter is read by a person, so the last item gets an "and".
    return "%s and %s" % (", ".join(items[:-1]), items[-1])


def draft(artist, track, period, check, estimate=None,
          distributor="Symphonic", isrc=""):
    """Return {"subject": str, "body": str} for one track's gap.

    `check` is coverage_check.check_gap output, or None when the stores
    have not been asked - which produces the UNCHECKED letter rather than
    a confident one.
    """
    artist = (artist or "").strip() or "our artist"
    track = (track or "").strip() or "the recording"
    period = (period or "").strip()
    carried = [c["source"] for c in (check or {}).get("carried", [])]
    absent = list((check or {}).get("absent", []))
    unchecked = list((check or {}).get("unchecked", []))
    checked_at_all = bool(check and check.get("ok"))

    ident = '"%s"' % track
    if isrc:
        ident += " (ISRC %s)" % isrc

    lines = [_GREETING, ""]

    if carried:
        subject = "%s - %s: live on %s, no earnings reported" % (
            artist, track, _fmt_list(carried, 3))
        lines += [
            "I am writing about %s by %s." % (ident, artist),
            "",
            "The recording is listed on %s, but the statement for %s shows "
            "no earnings from %s at all."
            % (_fmt_list(carried), period or "the period in question",
               "those stores" if len(carried) > 1 else "that store"),
            "",
            "Could you confirm whether earnings from %s were reported to you "
            "for this period, and if so where they appear on the statement? "
            "If they have not yet been reported, please let me know what the "
            "expected reporting lag is."
            % ("those stores" if len(carried) > 1 else "that store"),
        ]
    elif absent and checked_at_all:
        subject = "%s - %s: not listed on %s" % (
            artist, track, _fmt_list(absent, 3))
        lines += [
            "I am writing about %s by %s." % (ident, artist),
            "",
            "The recording does not appear on %s. It is earning on other "
            "stores, so this looks like a delivery that did not complete "
            "rather than a reporting issue." % _fmt_list(absent),
            "",
            "Could you check whether %s %s delivered, and re-deliver if not?"
            % ("those stores were" if len(absent) > 1 else "that store was",
               "ever"),
        ]
    else:
        subject = "%s - %s: please confirm store delivery" % (artist, track)
        missing = unchecked or absent or carried
        lines += [
            "I am writing about %s by %s." % (ident, artist),
            "",
            "The statement for %s shows earnings from some stores and "
            "nothing from %s."
            % (period or "the period in question", _fmt_list(missing)),
            "",
            "I have not been able to confirm from the outside whether those "
            "stores carry the recording, so I am asking rather than "
            "assuming: could you confirm whether it was delivered to them, "
            "and whether any earnings were reported for this period?",
        ]

    if carried and absent:
        lines += ["",
                  "Separately, it does not appear on %s at all, which may be "
                  "a delivery that did not complete." % _fmt_list(absent)]

    if unchecked and (carried or absent):
        lines += ["",
                  "I could not check %s from the outside - those are not "
                  "catalogues that can be searched - so I have made no "
                  "assumption either way about them." % _fmt_list(unchecked, 6)]

    # Money appears only in the accounting conversation. A store that does
    # not carry the recording owes nothing, and a delivery request with a
    # dollar figure in it reads as a demand - which is retracted the
    # moment the distributor points out the track was never delivered.
    if estimate and carried:
        lines += [
            "",
            "For scale rather than as an invoice: this recording is a share "
            "of the catalogue's earnings this period, and on that basis the "
            "stores above would represent roughly $%.2f. That is an "
            "estimate from my own statement, not a figure I am asking you "
            "to pay." % float(estimate),
        ]

    lines += ["", "Thank you,", artist]
    return {"subject": subject, "body": "\n".join(lines), "to": distributor}

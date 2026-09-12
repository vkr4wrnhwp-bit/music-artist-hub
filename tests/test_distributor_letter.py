"""The letter must never claim more than the check established.

Three shapes, and sending the wrong one has a real cost. A payment demand
about a track that was never delivered to the store is retracted in the
first reply, and the artist spends credibility they will need for the
claim that IS real.
"""
import distributor_letter as dl

ARTIST, TRACK, PERIOD, ISRC = "King 810", "Hungry Gods", "JUN-26", "GBRKQ2454700"


def _check(carried=(), absent=(), unchecked=(), ok=True):
    return {"ok": ok,
            "carried": [{"source": s, "url": "https://x/%s" % s} for s in carried],
            "absent": list(absent), "unchecked": list(unchecked)}


def test_a_carried_store_asks_about_accounting_and_may_mention_money():
    letter = dl.draft(ARTIST, TRACK, PERIOD,
                      _check(carried=["Apple Music", "Deezer"]),
                      estimate=24.17, isrc=ISRC)
    assert letter["to"] == "Symphonic"
    assert "no earnings reported" in letter["subject"]
    assert "is listed on Apple Music and Deezer" in letter["body"]
    assert "where they appear on the statement" in letter["body"]
    assert ISRC in letter["body"], "the recording is identified exactly"


def test_an_absent_store_asks_for_delivery_and_never_for_money():
    """The one that costs credibility if it gets the money paragraph."""
    letter = dl.draft(ARTIST, TRACK, PERIOD, _check(absent=["TIDAL"]),
                      estimate=24.17, isrc=ISRC)
    assert "not listed on TIDAL" in letter["subject"]
    body = letter["body"]
    assert "re-deliver" in body
    assert "$" not in body, "a delivery problem is not an invoice"
    assert "owe" not in body.lower()


def test_an_unchecked_gap_says_plainly_that_nothing_was_checked():
    letter = dl.draft(ARTIST, TRACK, PERIOD,
                      _check(unchecked=["Qobuz (JPY)"], ok=False))
    body = letter["body"]
    assert "please confirm store delivery" in letter["subject"]
    assert "have not been able to confirm" in body
    assert "asking rather than" in body
    assert "$" not in body, "nothing established, nothing costed"


def test_no_check_at_all_produces_the_asking_letter_not_a_confident_one():
    letter = dl.draft(ARTIST, TRACK, PERIOD, None)
    assert "confirm store delivery" in letter["subject"]
    assert "have not been able to confirm" in letter["body"]


def test_a_mixed_result_keeps_the_three_groups_apart():
    letter = dl.draft(ARTIST, TRACK, PERIOD,
                      _check(carried=["Apple Music"], absent=["TIDAL"],
                             unchecked=["SoundExchange: Sirius XM Radio, Inc"]),
                      estimate=24.17, isrc=ISRC)
    body = letter["body"]
    assert "is listed on Apple Music" in body
    assert "does not appear on TIDAL" in body
    assert "could not check SoundExchange" in body
    assert "made no assumption either way" in body


def test_the_estimate_is_labelled_and_last():
    letter = dl.draft(ARTIST, TRACK, PERIOD, _check(carried=["Apple Music"]),
                      estimate=24.17)
    body = letter["body"]
    assert "not a figure I am asking you to pay" in body
    assert body.index("24.17") > body.index("Could you confirm"), (
        "the ask comes before the number")


def test_it_is_a_draft_and_nothing_sends_it():
    """The module has no send path at all - a letter about money goes
    from the artist's own address, under their own name."""
    assert not hasattr(dl, "send")
    source = open(dl.__file__, encoding="utf-8").read()
    for forbidden in ("emailer", "email_provider", "resend", "smtp"):
        assert forbidden not in source.lower(), forbidden

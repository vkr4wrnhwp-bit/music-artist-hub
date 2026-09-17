"""What a white-label partner owes: per seat, not a share of revenue.

Owner, 2026-09-17: a flat $499 platform fee, then every seat at 40% off the
public price of the membership the partner put it on. A Fan seat is free.
The figure is shown with its working; nothing is charged from it.
"""
import partner_billing as pb


def test_seats_are_forty_percent_off_list_and_fan_is_free():
    assert pb.seat_price_cents("artist") == 1740
    assert pb.seat_price_cents("pro") == 4740
    assert pb.seat_price_cents("label") == 11940
    assert pb.seat_price_cents("fan") == 0


def test_the_statement_shows_its_working():
    roster = [{"plan": "artist"}] * 10 + [{"plan": "pro"}] * 3 + [{"plan": "fan"}] * 2
    s = pb.statement(roster)
    assert s["platform"] == 49900
    assert [(l["plan"], l["seats"], l["cents"]) for l in s["lines"]] == [("artist", 10, 17400), ("pro", 3, 14220)]
    assert s["total"] == 49900 + 17400 + 14220 == 81520
    assert s["free_seats"] == 2


def test_an_empty_roster_still_owes_the_platform_fee():
    s = pb.statement([])
    assert s["lines"] == [] and s["total"] == 49900

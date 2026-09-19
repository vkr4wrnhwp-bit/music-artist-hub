"""Grouping an imported list, and knowing who not to email.

Owner, 2026-09-18: sort fans by region, allow selecting a region or all,
and do something better than a cold blast.

The rules that matter here are the ones that decide whether a list quietly
loses people. Each has its own test because each has cost somebody a third
of their audience somewhere:

  a fan with no location is Unknown, and Unknown is SELECTABLE
  an unreadable consent date is unknown, not new
  a suppressed fan cannot come back through another door
  everyone is either contactable or suppressed; nobody is both or neither
"""
from datetime import date

import fan_segments as seg


def fan(email, city="", country="", suppressed="", created="2026-09-01",
        visits=0, clicks=0):
    return {"email": email, "city": city, "country": country,
            "suppressed": suppressed, "created": created,
            "total_visits": visits, "total_clicks": clicks,
            "total_presaves": 0, "total_captures": 0}


# --- regions -------------------------------------------------------------

def test_regions_are_biggest_first_with_unknown_last():
    fans = [fan("a@x.io", "Atlanta", "US"), fan("b@x.io", "Atlanta", "US"),
            fan("c@x.io", "Nashville", "US"), fan("d@x.io"), fan("e@x.io")]
    out = seg.regions(fans)
    assert [g["region"] for g in out] == ["Atlanta, US", "Nashville, US", "Unknown"]
    assert [g["count"] for g in out] == [2, 1, 2]


def test_unknown_is_a_group_and_not_a_hole():
    """The largest group on a fresh import is usually Unknown. Dropping it
    would mean every select-all missed most of the list."""
    out = seg.regions([fan("a@x.io"), fan("b@x.io")])
    assert len(out) == 1
    assert out[0]["region"] == seg.UNKNOWN and out[0]["unknown"] is True
    assert sorted(out[0]["emails"]) == ["a@x.io", "b@x.io"]


def test_every_fan_lands_in_exactly_one_region():
    fans = [fan("a@x.io", "Leeds", "GB"), fan("b@x.io", "", "GB"),
            fan("c@x.io", "Leeds"), fan("d@x.io")]
    out = seg.regions(fans)
    assert sum(g["count"] for g in out) == len(fans)
    seen = [e for g in out for e in g["emails"]]
    assert sorted(seen) == ["a@x.io", "b@x.io", "c@x.io", "d@x.io"]


def test_a_city_without_a_country_still_groups_by_city():
    out = seg.regions([fan("a@x.io", "Leeds"), fan("b@x.io", "Leeds")])
    assert out[0]["region"] == "Leeds" and out[0]["count"] == 2


# --- tour overlap --------------------------------------------------------

def test_the_list_says_where_to_play_not_only_who_to_tell():
    fans = ([fan("a%d@x.io" % i, "Atlanta") for i in range(4)]
            + [fan("b%d@x.io" % i, "Nashville") for i in range(2)])
    out = seg.tour_overlap(fans, ["Nashville", "Memphis"])
    assert [c["city"] for c in out["covered"]] == ["Nashville"]
    # The booking argument: four fans in a city with no show.
    assert [c["city"] for c in out["uncovered"]] == ["Atlanta"]
    assert out["uncovered"][0]["count"] == 4
    # A show where this list has nobody is stated, not judged.
    assert out["unmatched_shows"] == ["Memphis"]


def test_city_matching_ignores_case_and_padding_and_nothing_else():
    """And the city is reported stripped, because the padding is an
    accident of the export rather than part of the name."""
    out = seg.tour_overlap([fan("a@x.io", " atlanta ")], ["ATLANTA"])
    assert [c["city"] for c in out["covered"]] == ["atlanta"]
    assert out["uncovered"] == []


def test_fans_with_no_city_are_not_counted_into_any_show():
    out = seg.tour_overlap([fan("a@x.io"), fan("b@x.io", "Leeds")], ["Leeds"])
    assert sum(c["count"] for c in out["covered"]) == 1


# --- consent age ---------------------------------------------------------

def test_an_unreadable_date_is_unknown_rather_than_new():
    """The dangerous default: treating a missing date as today would make
    an ancient list look fresh."""
    today = date(2026, 9, 18)
    out = seg.consent_ages([fan("a@x.io", created=""),
                            fan("b@x.io", created="not-a-date"),
                            fan("c@x.io", created="2026-09-01")], today)
    assert len(out["unknown"]) == 2
    assert len(out["fresh"]) == 1


def test_consent_buckets_split_fresh_ageing_and_stale():
    today = date(2026, 9, 18)
    out = seg.consent_ages([fan("a@x.io", created="2026-06-01"),
                            fan("b@x.io", created="2025-01-01"),
                            fan("c@x.io", created="2019-01-01")], today)
    assert len(out["fresh"]) == 1 and len(out["ageing"]) == 1 and len(out["stale"]) == 1


# --- suppression ---------------------------------------------------------

def test_suppression_records_why_and_counts_the_reasons():
    fans = [fan("a@x.io", suppressed="bounced"), fan("b@x.io", suppressed="bounced"),
            fan("c@x.io", suppressed="unsubscribed on their list"), fan("d@x.io")]
    out = seg.suppressed(fans)
    assert out["count"] == 3
    assert out["reasons"][0] == ("bounced", 2)


def test_a_suppressed_fan_cannot_come_back_through_another_door():
    """One definition of contactable, used everywhere. Regions, the first
    send and the tour all read it, so there is no path that forgets."""
    fans = [fan("gone@x.io", "Atlanta", suppressed="bounced"),
            fan("here@x.io", "Atlanta")]
    live = seg.contactable(fans)
    assert [f["email"] for f in live] == ["here@x.io"]
    s = seg.summary(fans, ["Atlanta"])
    assert s["regions"][0]["count"] == 1
    assert s["regions"][0]["emails"] == ["here@x.io"]
    assert s["tour"]["covered"][0]["count"] == 1
    assert "gone@x.io" not in seg.first_send(fans)


# --- the first send ------------------------------------------------------

def test_the_first_send_is_for_whoever_has_never_done_anything():
    fans = [fan("cold@x.io"), fan("warm@x.io", clicks=3), fan("seen@x.io", visits=1)]
    assert [f["email"] for f in seg.first_send(fans)] == ["cold@x.io"]


def test_the_first_send_skips_the_suppressed():
    fans = [fan("cold@x.io"), fan("no@x.io", suppressed="bounced")]
    assert [f["email"] for f in seg.first_send(fans)] == ["cold@x.io"]


# --- the invariant -------------------------------------------------------

def test_everybody_is_contactable_or_suppressed_and_never_both():
    fans = [fan("a@x.io"), fan("b@x.io", suppressed="bounced"),
            fan("c@x.io", "Leeds"), fan("d@x.io", suppressed="  ")]
    s = seg.summary(fans)
    assert s["total"] == 4
    assert s["contactable"] + s["suppressed"]["count"] == s["total"]
    assert s["adds_up"] is True
    # A whitespace-only reason is not a suppression.
    assert s["contactable"] == 3


def test_summary_survives_an_empty_list():
    s = seg.summary([])
    assert s["total"] == 0 and s["adds_up"] is True
    assert s["regions"] == [] and s["tour"]["covered"] == []

"""Ticketmaster as the second ticket source, and the line it may not cross.

Most club dates are not on Eventbrite. Ticketmaster's free Discovery API
lists a great many of them - but it is a public listing: it publishes the
ticket link, the on-sale status and the announced date, and nothing at
all about how many tickets have sold or how big the room is. So this
source may fill a link and a status, and it may never write a count, and
it may never take one away from the source that measured it.

Every outbound call is canned here: nothing in this file goes near the
network, and the sandbox and no-key cases assert that no call is even
attempted.
"""
import io
import json
import urllib.error

import eventbrite_provider as eb
import sandbox
import ticketmaster_provider as tm
import tour_store as ts
import tour_tickets as tickets
from tests.test_tour_date_page import _user, _tour, _show, _member_join, flask_app  # noqa: F401
from tests.test_tour_tickets import _classes, _event as _eb_event, _eventbrite, _http_error

EVENTS_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
EVENT_URL = "https://app.ticketmaster.com/discovery/v2/events/"


def _tm_event(eid, date_="2030-05-02", name="Test Artist", venue="The Basement East",
              city="Nashville", state="TN", status="onsale", time_="20:00:00"):
    """One event exactly as Discovery serialises it: the venues under
    _embedded, the local date under dates.start, the on-sale word under
    dates.status.code - and no field anywhere for a sold count, because
    Ticketmaster publishes none."""
    return {
        "name": name, "id": eid, "type": "event",
        "url": "https://www.ticketmaster.com/event/%s" % eid,
        "dates": {"start": {"localDate": date_, "localTime": time_,
                            "dateTime": date_ + "T01:00:00Z"},
                  "status": {"code": status}, "timezone": "America/Chicago"},
        "sales": {"public": {"startDateTime": "2030-01-10T15:00:00Z",
                             "endDateTime": date_ + "T01:00:00Z"}},
        "priceRanges": [{"type": "standard", "currency": "USD", "min": 25.0, "max": 45.0}],
        "_embedded": {"venues": [{"name": venue, "city": {"name": city},
                                  "state": {"stateCode": state},
                                  "country": {"countryCode": "US"}}]},
    }


def _ticketmaster(monkeypatch, events, pages=1, raise_with=None):
    """Key on, HTTP canned. `pages` makes the search answer in that many
    pages (one event a page), `raise_with` fails every call with it.
    Returns the list of URLs called."""
    calls = []

    def fake_http(url):
        calls.append(url)
        assert "apikey=tm-test-key" in url, "the key goes on every call"
        if raise_with is not None:
            raise raise_with
        if url.startswith(EVENT_URL):
            eid = url[len(EVENT_URL):].split(".json")[0]
            row = next((e for e in events if e["id"] == eid), None)
            if row is None:
                raise AssertionError("no such event %s" % eid)
            return json.dumps(row).encode("utf-8")
        assert url.startswith(EVENTS_URL), "only the documented endpoints"
        assert "classificationName=music" in url
        page = 0
        for part in url.split("&"):
            if part.startswith("page="):
                page = int(part.split("=")[1])
        if pages > 1:
            rows = events[page:page + 1]
        else:
            rows = events if page == 0 else []
        return json.dumps({"_embedded": {"events": rows},
                           "page": {"size": 50, "totalElements": len(events),
                                    "totalPages": pages, "number": page}}).encode("utf-8")

    monkeypatch.setenv("TICKETMASTER_API_KEY", "tm-test-key")
    monkeypatch.delenv("SANDBOX", raising=False)
    monkeypatch.setattr(tm, "_http", fake_http)
    tm.clear_refusal()
    return calls


def _no_key(monkeypatch):
    """No Ticketmaster key; any outbound call is a test failure."""
    def fake_http(url):
        raise AssertionError("no call may leave without a key: %s" % url)

    monkeypatch.delenv("TICKETMASTER_API_KEY", raising=False)
    monkeypatch.setattr(tm, "_http", fake_http)
    tm.clear_refusal()


def _no_eventbrite(monkeypatch):
    def fake_http(url, headers=None):
        raise AssertionError("no Eventbrite call may leave without a token: %s" % url)

    monkeypatch.delenv("EVENTBRITE_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.setattr(eb, "_http", fake_http)
    eb.clear_refusal()


def _fault(code, errorcode, faultstring):
    """Ticketmaster's own error body, the shape their docs publish."""
    body = json.dumps({"fault": {"faultstring": faultstring,
                                 "detail": {"errorcode": errorcode}}}).encode("utf-8")
    return urllib.error.HTTPError(EVENTS_URL, code, errorcode, {}, io.BytesIO(body))


def _home(client, tid):
    r = client.get("/tours/%s" % tid)
    assert r.status_code == 200
    return r.get_data(as_text=True)


def _sync(client, tid):
    r = client.post("/tours/%s/tickets/sync" % tid)
    assert r.status_code == 302
    return r


def _marketing(client, tid, sid):
    r = client.get("/tours/%s/shows/%s?tab=marketing" % (tid, sid))
    assert r.status_code == 200
    return r.get_data(as_text=True)


# --- what Discovery has, and what it does not --------------------------------

def test_a_date_only_ticketmaster_lists_gets_the_link_and_the_status_and_no_count(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [])                       # a token, and no event on the date
    calls = _ticketmaster(monkeypatch, [_tm_event("G5v1")])
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)                           # 2030-05-02, The Basement East
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert show["ticket_url"] == "https://www.ticketmaster.com/event/G5v1"
    assert show["ticket_status"] == "on sale"
    assert show["ticketmaster_event_id"] == "G5v1" and show["tickets_synced_at"]
    assert show["ticket_source"] == "ticketmaster"
    assert not show["tickets_sold"], "Discovery publishes no sold count"
    assert not show["capacity"], "and no capacity"
    assert not show["eventbrite_event_id"]
    assert len(calls) == 1, "one search a run"
    assert "keyword=Test+Artist" in calls[0] and "startDateTime=2030-05-02T00%3A00%3A00Z" in calls[0]
    home = _home(client, tid)
    assert "Eventbrite matched 0; Ticketmaster matched 1; 0 dates had no match" in home


def test_the_page_says_the_count_is_not_published_rather_than_showing_a_blank(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [])
    _ticketmaster(monkeypatch, [_tm_event("G5v1")])
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    page = _marketing(client, tid, sid)
    assert "Ticketmaster" in page, "the source is named on the date"
    assert "does not publish how many tickets have sold" in page
    assert "https://www.ticketmaster.com/event/G5v1" in page
    assert "of 0 sold" not in page and "0 of" not in page, "nothing reads as zero sold"
    # And the tour-wide list says the same thing on that row.
    rows = client.get("/tours/%s/marketing" % tid).get_data(as_text=True)
    assert "Ticketmaster · no count published" in rows
    assert "no platform is connected" not in rows


def test_a_typed_count_beside_a_ticketmaster_listing_still_reads_as_typed(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [])
    _ticketmaster(monkeypatch, [_tm_event("G5v1")])
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    client.post("/tours/%s/shows/%s/marketing" % (tid, sid),
                data={"tickets_sold": "60", "capacity": "400"})
    page = _marketing(client, tid, sid)
    assert ">typed<" in page and "the figure above is one you typed" in page
    assert ts.get_show(tid, sid)["ticket_source"] == "typed"
    assert "synced" not in page.split("Timeline")[0], "nothing here was measured"


# --- the two sources together -------------------------------------------------

def test_a_date_on_both_keeps_eventbrites_count_and_does_not_lose_it(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [_eb_event("E1")], {"E1": _classes((150, 400))})
    calls = _ticketmaster(monkeypatch, [_tm_event("G5v1")])
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert show["tickets_sold"] == "150" and show["capacity"] == "400"
    assert show["ticket_source"] == "eventbrite"
    assert show["ticket_url"] == "https://www.eventbrite.com/e/E1", "the measured link stands"
    assert not show["ticketmaster_event_id"]
    assert calls == [], "Ticketmaster is not even asked about a date Eventbrite matched"
    # And a second press does not let the source that cannot measure
    # overwrite the count or the link.
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert show["tickets_sold"] == "150" and show["ticket_source"] == "eventbrite"
    assert "Eventbrite matched 1; Ticketmaster matched 0; 0 dates had no match" in _home(client, tid)


def test_one_press_runs_both_and_the_line_names_each(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [_eb_event("E1")], {"E1": _classes((150, 400))})
    _ticketmaster(monkeypatch, [_tm_event("G5v1", date_="2030-05-04", venue="Exit/In")])
    client, owner = _user(flask_app)
    tid = _tour(client)
    eb_sid = _show(client, tid)                                  # Eventbrite's date
    tm_sid = _show(client, tid, "2030-05-04", "Exit/In")         # Ticketmaster's
    _show(client, tid, "2030-05-06", "Cannery Ballroom")         # nobody's
    _sync(client, tid)
    assert ts.get_show(tid, eb_sid)["tickets_sold"] == "150"
    assert ts.get_show(tid, tm_sid)["ticketmaster_event_id"] == "G5v1"
    assert not ts.get_show(tid, tm_sid)["tickets_sold"]
    assert "Eventbrite matched 1; Ticketmaster matched 1; 1 dates had no match" in _home(client, tid)


def test_a_ticketmaster_match_never_replaces_a_link_typed_or_an_eventbrite_one(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [])
    _ticketmaster(monkeypatch, [_tm_event("G5v1")])
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    typed = "https://tickets.example.com/basement-east"
    client.post("/tours/%s/shows/%s/marketing" % (tid, sid), data={"ticket_url": typed})
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert show["ticket_url"] == typed, "the owner's ticketer is not replaced"
    assert show["ticketmaster_event_id"] == "G5v1" and show["ticket_status"] == "on sale"
    assert not tickets.ours("https://www.eventbrite.com/e/E1", "ticketmaster")
    assert tickets.ours("https://www.ticketmaster.com/event/G5v1", "ticketmaster")
    assert tickets.ours("https://www.ticketmaster.co.uk/event/G5v1", "ticketmaster")
    assert tickets.ours("", "ticketmaster")


def test_two_ticketmaster_listings_on_a_date_are_named_and_linked_by_hand(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [])
    _ticketmaster(monkeypatch, [_tm_event("G5v1", name="Test Artist Live"),
                                _tm_event("G5v2", name="Test Artist Late Show")])
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    assert not ts.get_show(tid, sid)["ticketmaster_event_id"], "nothing is guessed"
    home = _home(client, tid)
    assert "Test Artist Late Show" in home and 'name="source" value="ticketmaster"' in home
    r = client.post("/tours/%s/shows/%s/tickets/link" % (tid, sid),
                    data={"event_id": "G5v2", "source": "ticketmaster"})
    assert r.status_code == 302
    show = ts.get_show(tid, sid)
    assert show["ticketmaster_event_id"] == "G5v2"
    assert show["ticket_url"] == "https://www.ticketmaster.com/event/G5v2"
    # And the next sync honours the answer rather than calling it ambiguous.
    _sync(client, tid)
    assert ts.get_show(tid, sid)["ticketmaster_event_id"] == "G5v2"
    assert "Ticketmaster matched 1; 0 dates had no match" in _home(client, tid)


def test_a_second_page_of_listings_is_followed(flask_app, monkeypatch):
    events = [_tm_event("G5v1", date_="2030-05-09", venue="Exit/In"), _tm_event("G5v2")]
    calls = _ticketmaster(monkeypatch, events, pages=2)
    _eventbrite(monkeypatch, [])
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    assert any("page=1" in c for c in calls), "the next page is asked for"
    assert ts.get_show(tid, sid)["ticketmaster_event_id"] == "G5v2"


# --- a key Ticketmaster refuses -----------------------------------------------

def test_a_refused_key_is_reported_in_ticketmasters_own_words_and_writes_nothing(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [])
    _ticketmaster(monkeypatch, [_tm_event("G5v1")],
                  raise_with=_fault(401, "oauth.v2.InvalidApiKey", "Invalid ApiKey"))
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert not show["ticket_url"] and not show["ticketmaster_event_id"]
    assert not show["tickets_sold"] and not show["ticket_source"]
    home = _home(client, tid)
    assert "Ticketmaster refused: Invalid ApiKey" in home
    assert "Ticketmaster matched 0" in home
    assert tm.last_refusal()["status"] == "oauth.v2.InvalidApiKey"


def test_a_quota_violation_is_a_refusal_too(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [])
    _ticketmaster(monkeypatch, [_tm_event("G5v1")],
                  raise_with=_fault(429, "policies.ratelimit.QuotaViolation",
                                    "Rate limit quota violation. Quota limit exceeded."))
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid)
    _sync(client, tid)
    assert "Ticketmaster refused: Rate limit quota violation." in _home(client, tid)


def test_a_404_on_one_listing_is_not_a_refusal(monkeypatch):
    _ticketmaster(monkeypatch, [], raise_with=urllib.error.HTTPError(
        EVENTS_URL, 404, "Not Found", {}, io.BytesIO(b'{"errors":[{"code":"DIS1004"}]}')))
    assert tm.find_events("Test Artist", "2030-05-01", "2030-05-10") == []
    assert tm.last_refusal() is None


# --- the gates ----------------------------------------------------------------

def test_without_a_key_ticketmaster_is_silently_skipped_and_eventbrite_is_unchanged(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [_eb_event("E1")], {"E1": _classes((150, 400))})
    _no_key(monkeypatch)
    assert not tm.configured()
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert show["tickets_sold"] == "150" and show["ticket_source"] == "eventbrite"
    home = _home(client, tid)
    assert "Tickets synced for 1 shows; 0 had no match" in home, "the old line, unchanged"
    assert "Ticketmaster is not connected (TICKETMASTER_API_KEY)" in home
    assert tm.find_events("Test Artist", "2030-05-01", "2030-05-10") == []
    assert tm.get_event("G5v1") is None


def test_neither_key_leaves_the_button_off_and_names_both_variables(flask_app, monkeypatch):
    _no_eventbrite(monkeypatch)
    _no_key(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    home = _home(client, tid)
    assert "Sync ticket sales" not in home
    assert "no Eventbrite token on this deployment (EVENTBRITE_TOKEN)" in home
    assert "no Ticketmaster key (TICKETMASTER_API_KEY)" in home
    _sync(client, tid)                                  # the route still answers
    assert not ts.get_show(tid, sid)["ticket_url"]
    assert tickets.report_line(None).startswith("No ticket source")


def test_a_sandbox_deployment_never_calls_ticketmaster_even_with_a_key(flask_app, monkeypatch):
    _no_eventbrite(monkeypatch)
    calls = _ticketmaster(monkeypatch, [_tm_event("G5v1")])
    monkeypatch.setenv("SANDBOX", "1")
    assert sandbox.active() and not tm.configured()
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    assert calls == [], "nothing left the sandbox"
    assert not ts.get_show(tid, sid)["ticket_url"]
    assert "no Ticketmaster key (TICKETMASTER_API_KEY)" in _home(client, tid)


def test_a_view_only_member_reads_the_listing_but_presses_nothing(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [])
    _ticketmaster(monkeypatch, [_tm_event("G5v1")])
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    viewer, _v = _member_join(flask_app, client, tid, ["view", "marketing"], label="Viewer")
    home = viewer.get("/tours/%s" % tid).get_data(as_text=True)
    assert "Sync ticket sales" not in home and "/tickets/sync" not in home
    page = viewer.get("/tours/%s/shows/%s?tab=marketing" % (tid, sid)).get_data(as_text=True)
    assert "does not publish how many tickets have sold" in page
    assert "/tickets/link" not in page


# --- the units ----------------------------------------------------------------

def test_discovery_is_flattened_to_the_fields_a_match_needs_and_no_count(monkeypatch):
    _ticketmaster(monkeypatch, [_tm_event("G5v1")])
    rows = tm.find_events("Test Artist", "2030-05-01", "2030-05-10")
    assert len(rows) == 1
    ev = rows[0]
    assert ev["id"] == "G5v1" and ev["source"] == "ticketmaster"
    assert ev["date"] == "2030-05-02" and ev["start_local"] == "2030-05-02T20:00:00"
    assert ev["venue"] == "The Basement East" and ev["city"] == "Nashville" and ev["region"] == "TN"
    assert ev["status"] == "onsale" and ev["onsale_start"] == "2030-01-10T15:00:00Z"
    assert ev["price_min"] == 25.0 and ev["price_max"] == 45.0 and ev["currency"] == "USD"
    assert "tickets_sold" not in ev and "capacity" not in ev and "sold" not in ev
    # An artist nobody typed is never searched for.
    assert tm.find_events("", "2030-05-01", "2030-05-10") == []


def test_the_status_words_are_ticketmasters_own_and_offsale_is_not_sold_out():
    assert tickets.tm_status_for({"status": "onsale"}) == "on sale"
    assert tickets.tm_status_for({"status": "offsale"}) == "off sale"
    assert tickets.tm_status_for({"status": "cancelled"}) == "cancelled"
    assert tickets.tm_status_for({"status": "canceled"}) == "cancelled"
    assert tickets.tm_status_for({"status": "postponed"}) == "postponed"
    assert tickets.tm_status_for({"status": "rescheduled"}) == "rescheduled"
    assert tickets.tm_status_for({"status": ""}) == "listed"


def test_a_ticketmaster_match_writes_no_number_at_all():
    show = {"id": "s1", "date": "2030-05-02", "venue": "The Basement East",
            "tickets_sold": "150", "capacity": "400", "ticket_url": ""}
    event = {"id": "G5v1", "url": "https://www.ticketmaster.com/event/G5v1", "status": "onsale"}
    fields = tickets.tm_fields_for(show, event)
    assert "tickets_sold" not in fields and "capacity" not in fields
    assert fields["ticket_source"] == "ticketmaster"
    assert fields["ticket_url"] == "https://www.ticketmaster.com/event/G5v1"
    assert fields["ticket_status"] == "on sale"

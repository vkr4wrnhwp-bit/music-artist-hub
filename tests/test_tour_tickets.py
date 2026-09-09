"""What Eventbrite has sold, on the date that sold it.

The owner holds a private token. With it, a date's ticket fields come
from Eventbrite's own quantity_sold and quantity_total instead of a
number somebody typed a week ago — but only when exactly one event on
that local date is plausibly this show. Zero or several is listed as
unmatched with the events' names, and one press links the right one for
good. Without the token the tour home says so and names the variable;
in sandbox nothing goes out even with a token. Every outbound call is
canned here.
"""
import io
import json
import urllib.error

import eventbrite_provider as eb
import sandbox
import tour_store as ts
import tour_tickets as tickets
from tests.test_tour_date_page import _user, _tour, _show, _member_join, flask_app  # noqa: F401

ORGS_URL = "https://www.eventbriteapi.com/v3/users/me/organizations/"
EVENTS_URL = "https://www.eventbriteapi.com/v3/organizations/"
TC_URL = "https://www.eventbriteapi.com/v3/events/"


def _event(eid, date_="2030-05-02", name="Test Artist Live", venue="The Basement East",
           city="Nashville", region="TN", status="live", sold_out=False, capacity=400):
    """One event exactly as Eventbrite serialises it: a multipart-text
    name, a datetime-tz start, the venue and ticket_availability
    expansions this app asks for."""
    return {
        "id": eid, "name": {"text": name, "html": "<p>%s</p>" % name},
        "url": "https://www.eventbrite.com/e/%s" % eid,
        "status": status, "capacity": capacity,
        "start": {"timezone": "America/Chicago", "utc": date_ + "T01:00:00Z",
                  "local": date_ + "T20:00:00"},
        "venue": {"id": "V1", "name": venue,
                  "address": {"city": city, "region": region, "country": "US"}},
        "ticket_availability": {"is_sold_out": sold_out,
                                "has_available_tickets": not sold_out},
    }


def _classes(*pairs):
    return [{"name": "GA %d" % i, "quantity_total": total, "quantity_sold": sold}
            for i, (sold, total) in enumerate(pairs, start=1)]


class _Boom(Exception):
    pass


def _eventbrite(monkeypatch, events, classes=None, orgs=("777",), pages=None, raise_for=None):
    """Token on, HTTP canned. `classes` is {event_id: [ticket class...]},
    `pages` an optional {url_fragment: continuation token} to make one
    endpoint answer in two pages, `raise_for` a (fragment, exception)
    that fails one call. Returns the list of (url, headers) calls."""
    calls = []
    classes = classes or {}

    def fake_http(url, headers=None):
        calls.append((url, headers or {}))
        assert (headers or {}).get("Authorization") == "Bearer test-token", \
            "the private token is the bearer on every call"
        if raise_for and raise_for[0] in url:
            raise raise_for[1]
        if url.startswith(ORGS_URL):
            return json.dumps({"pagination": {"has_more_items": False},
                               "organizations": [{"id": o, "name": "Org %s" % o}
                                                 for o in orgs]}).encode("utf-8")
        if url.startswith(EVENTS_URL) and "/events/" in url:
            assert "status=live%2Cstarted%2Cended" in url
            assert "expand=venue%2Cticket_availability" in url
            token = (pages or {}).get("events")
            if token and "continuation=" not in url:
                return json.dumps({"pagination": {"has_more_items": True, "continuation": token},
                                   "events": events[:1]}).encode("utf-8")
            rest = events[1:] if token else events
            return json.dumps({"pagination": {"has_more_items": False},
                               "events": rest}).encode("utf-8")
        if url.startswith(TC_URL) and "/ticket_classes/" in url:
            eid = url[len(TC_URL):].split("/")[0]
            return json.dumps({"pagination": {"has_more_items": False},
                               "ticket_classes": classes.get(eid, [])}).encode("utf-8")
        if url.startswith(TC_URL):                       # one event by id
            eid = url[len(TC_URL):].split("/")[0]
            row = next((e for e in events if e["id"] == eid), None)
            if row is None:
                raise _Boom("no such event")
            return json.dumps(row).encode("utf-8")
        raise AssertionError("unexpected call to %s" % url)

    monkeypatch.setenv("EVENTBRITE_TOKEN", "test-token")
    monkeypatch.delenv("SANDBOX", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.setattr(eb, "_http", fake_http)
    eb.clear_refusal()
    return calls


def _no_token(monkeypatch):
    """No token; any outbound call is a test failure."""
    def fake_http(url, headers=None):
        raise AssertionError("no call may leave without a token: %s" % url)
    monkeypatch.delenv("EVENTBRITE_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.setattr(eb, "_http", fake_http)
    eb.clear_refusal()


def _http_error(code, error, description):
    """Eventbrite's own error body: {"error", "error_description", "status_code"}."""
    body = json.dumps({"error": error, "error_description": description,
                       "status_code": code}).encode("utf-8")
    return urllib.error.HTTPError("https://www.eventbriteapi.com/v3/", code, error,
                                  {}, io.BytesIO(body))


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


# --- the match ----------------------------------------------------------------

def test_a_date_in_the_same_room_takes_eventbrites_own_numbers(flask_app, monkeypatch):
    ev = _event("E1")
    calls = _eventbrite(monkeypatch, [ev], {"E1": _classes((120, 300), (30, 100))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)                      # 2030-05-02, The Basement East
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert show["tickets_sold"] == "150", "the sum of quantity_sold across the classes"
    assert show["capacity"] == "400", "the sum of quantity_total, the field being empty"
    assert show["ticket_url"] == "https://www.eventbrite.com/e/E1"
    assert show["ticket_status"] == "on sale"
    assert show["eventbrite_event_id"] == "E1" and show["tickets_synced_at"]
    urls = [c[0] for c in calls]
    assert urls[0].startswith(ORGS_URL), "the organizations first"
    assert "/organizations/777/events/" in urls[1]
    assert "/events/E1/ticket_classes/" in urls[2]
    assert len(urls) == 3, "one walk, one count"
    home = _home(client, tid)
    assert "Tickets synced for 1 shows; 0 had no match" in home
    assert "Sync ticket sales" in home


def test_the_report_and_the_page_say_sold_out_and_ended(flask_app, monkeypatch):
    events = [_event("E1", sold_out=True),
              _event("E2", date_="2030-05-04", venue="Exit/In", status="ended")]
    _eventbrite(monkeypatch, events, {"E1": _classes((300, 300)), "E2": _classes((88, 250))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid1 = _show(client, tid)
    sid2 = _show(client, tid, "2030-05-04", "Exit/In")
    _sync(client, tid)
    assert ts.get_show(tid, sid1)["ticket_status"] == "sold out"
    assert ts.get_show(tid, sid2)["ticket_status"] == "ended"
    assert ts.get_show(tid, sid2)["tickets_sold"] == "88"


def test_a_second_page_of_events_is_followed(flask_app, monkeypatch):
    events = [_event("E1", date_="2030-05-09", venue="Exit/In"),
              _event("E2", date_="2030-05-02")]
    calls = _eventbrite(monkeypatch, events, {"E2": _classes((10, 50))},
                        pages={"events": "TOKEN-2"})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    assert "continuation=TOKEN-2" in "".join(c[0] for c in calls), "the token goes back"
    assert ts.get_show(tid, sid)["eventbrite_event_id"] == "E2"


def test_a_show_on_another_date_is_never_matched(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [_event("E1", date_="2030-05-06")], {"E1": _classes((10, 50))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)                      # 2030-05-02
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert not show["tickets_sold"] and not show["eventbrite_event_id"]
    assert "Tickets synced for 0 shows; 1 had no match" in _home(client, tid)


def test_the_artist_billed_in_the_same_city_matches_a_renamed_room(flask_app, monkeypatch):
    # The room's name shares nothing with the show's, so the fallback is
    # the billing: this artist, this city, this date.
    ev = _event("E1", name="Test Artist + guests", venue="Cannery Ballroom")
    _eventbrite(monkeypatch, [ev], {"E1": _classes((44, 500))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    assert ts.get_show(tid, sid)["tickets_sold"] == "44"


def test_another_act_in_the_same_city_is_not_this_show(flask_app, monkeypatch):
    ev = _event("E1", name="Somebody Else Band", venue="Cannery Ballroom")
    _eventbrite(monkeypatch, [ev], {"E1": _classes((44, 500))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    assert not ts.get_show(tid, sid)["tickets_sold"], "same city and date is not enough"


# --- what a sync must never overwrite -----------------------------------------

def test_a_ticket_link_typed_to_another_ticketer_is_kept(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [_event("E1")], {"E1": _classes((150, 400))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    typed = "https://tickets.example.com/basement-east"
    client.post("/tours/%s/shows/%s/marketing" % (tid, sid),
                data={"ticket_url": typed, "capacity": "500"})
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert show["ticket_url"] == typed, "the owner's ticketer is not replaced"
    assert show["capacity"] == "500", "a capacity already entered is left alone"
    assert show["tickets_sold"] == "150", "the measured count still lands"
    assert show["eventbrite_event_id"] == "E1"
    # The event is still reachable from the page, by the stored id.
    page = _marketing(client, tid, sid)
    assert "https://www.eventbrite.com/e/E1" in page


def test_an_eventbrite_link_is_refreshed(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [_event("E1")], {"E1": _classes((10, 40))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    client.post("/tours/%s/shows/%s/marketing" % (tid, sid),
                data={"ticket_url": "https://www.eventbrite.com/e/OLD-999"})
    _sync(client, tid)
    assert ts.get_show(tid, sid)["ticket_url"] == "https://www.eventbrite.com/e/E1"


# --- two candidates, and the answer given once --------------------------------

def test_two_events_on_the_date_are_listed_by_name_and_linked_by_hand(flask_app, monkeypatch):
    events = [_event("E1", name="Test Artist Live"),
              _event("E2", name="Test Artist Late Show")]
    _eventbrite(monkeypatch, events,
                {"E1": _classes((11, 100)), "E2": _classes((222, 400))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert not show["tickets_sold"] and not show["eventbrite_event_id"], "nothing is guessed"
    home = _home(client, tid)
    assert "Tickets synced for 0 shows; 1 had no match" in home
    assert "Test Artist Live" in home and "Test Artist Late Show" in home, "by name"
    assert 'name="event_id" value="E1"' in home and 'name="event_id" value="E2"' in home
    # The owner says which one. It is stored, and filled straight away.
    r = client.post("/tours/%s/shows/%s/tickets/link" % (tid, sid), data={"event_id": "E2"})
    assert r.status_code == 302
    show = ts.get_show(tid, sid)
    assert show["eventbrite_event_id"] == "E2" and show["tickets_sold"] == "222"
    # And the next sync honours it rather than calling it ambiguous again.
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert show["eventbrite_event_id"] == "E2" and show["tickets_sold"] == "222"
    assert "Tickets synced for 1 shows; 0 had no match" in _home(client, tid)


# --- a token Eventbrite refuses -----------------------------------------------

def test_a_refused_token_is_reported_in_eventbrites_own_words_and_writes_nothing(flask_app, monkeypatch):
    denied = _http_error(401, "ACCESS_DENIED", "The OAuth token you provided was invalid.")
    _eventbrite(monkeypatch, [_event("E1")], {"E1": _classes((150, 400))},
                raise_for=("/users/me/organizations/", denied))
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    show = ts.get_show(tid, sid)
    assert not show["tickets_sold"] and not show["ticket_url"] and not show["eventbrite_event_id"]
    home = _home(client, tid)
    assert "refused: The OAuth token you provided was invalid." in home
    assert "Tickets synced for 0 shows" in home


def test_a_rate_limit_is_a_refusal_too(flask_app, monkeypatch):
    limited = _http_error(429, "HIT_RATE_LIMIT", "Hourly rate limit has been reached.")
    _eventbrite(monkeypatch, [_event("E1")], raise_for=("/ticket_classes/", limited))
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    assert "refused: Hourly rate limit has been reached." in _home(client, tid)
    assert not ts.get_show(tid, sid)["tickets_sold"], "no count came back to write"


def test_a_404_on_one_event_is_not_a_refusal(flask_app, monkeypatch):
    gone = _http_error(404, "NOT_FOUND", "The event you requested does not exist.")
    _eventbrite(monkeypatch, [_event("E1")], raise_for=("/ticket_classes/", gone))
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid)
    _sync(client, tid)
    assert eb.last_refusal() is None
    assert "refused:" not in _home(client, tid)


# --- the gates ----------------------------------------------------------------

def test_without_a_token_there_is_no_button_and_the_page_names_the_variable(flask_app, monkeypatch):
    _no_token(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    home = _home(client, tid)
    assert "Sync ticket sales" not in home
    assert "no Eventbrite token on this deployment (EVENTBRITE_TOKEN)" in home
    # And the route still answers, doing nothing at all.
    _sync(client, tid)
    assert not ts.get_show(tid, sid)["tickets_sold"]
    assert not eb.configured() and eb.list_events() == []
    assert eb.ticket_counts("E1") == (None, None)


def test_a_sandbox_deployment_never_calls_out_even_with_a_token(flask_app, monkeypatch):
    calls = _eventbrite(monkeypatch, [_event("E1")], {"E1": _classes((150, 400))})
    monkeypatch.setenv("SANDBOX", "1")
    assert sandbox.active() and not eb.configured()
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    assert calls == [], "nothing left the sandbox"
    assert not ts.get_show(tid, sid)["tickets_sold"]
    assert "no Eventbrite token on this deployment (EVENTBRITE_TOKEN)" in _home(client, tid)


# --- what the date page says --------------------------------------------------

def test_a_synced_count_reads_as_measured_and_a_typed_one_says_typed(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [_event("E1")], {"E1": _classes((150, 400))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    # Typed first: the same numbers, said as what they are.
    client.post("/tours/%s/shows/%s/marketing" % (tid, sid),
                data={"tickets_sold": "150", "capacity": "400"})
    typed = _marketing(client, tid, sid)
    assert ">typed<" in typed and "not linked to an Eventbrite event" in typed
    assert "150 of 400 sold" not in typed, "the lcd is for a measured count only"
    assert "synced" not in typed
    # Then measured.
    _sync(client, tid)
    page = _marketing(client, tid, sid)
    assert "sb-lcd" in page and "150 of 400 sold" in page and "synced just now" in page
    assert "https://www.eventbrite.com/e/E1" in page
    assert ">typed<" not in page
    # The header sheet carries the same figure, with the same caption.
    assert page.count("150 of 400 sold") >= 2, "the sheet facts and the Marketing feature"


def test_the_caption_ages_with_the_reading(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [_event("E1")], {"E1": _classes((150, 400))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    assert "synced just now" in _marketing(client, tid, sid)
    from datetime import datetime, timedelta, timezone
    then = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    ts.update_show_ext(tid, sid, {"tickets_synced_at": then})
    assert "synced 2 h ago" in _marketing(client, tid, sid)


def test_the_marketing_list_never_says_nothing_is_connected_when_something_is(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [_event("E1")], {"E1": _classes((150, 400))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    _show(client, tid)                                   # 2030-05-02, matched
    sid2 = _show(client, tid, "2030-05-05", "Exit/In")   # no event that day
    client.post("/tours/%s/shows/%s/marketing" % (tid, sid2),
                data={"tickets_sold": "20", "capacity": "100"})
    _sync(client, tid)
    page = client.get("/tours/%s/marketing" % tid).get_data(as_text=True)
    assert "no platform is connected" not in page, "one of these rows was measured"
    assert "synced just now" in page and ">typed<" in page, "each row says which"


def test_the_marketing_list_keeps_its_old_words_without_a_token(flask_app, monkeypatch):
    _no_token(monkeypatch)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    client.post("/tours/%s/shows/%s/marketing" % (tid, sid),
                data={"tickets_sold": "20", "capacity": "100"})
    page = client.get("/tours/%s/marketing" % tid).get_data(as_text=True)
    assert "Ticket counts are what you enter; no platform is connected." in page


def test_a_view_only_member_reads_the_numbers_but_presses_nothing(flask_app, monkeypatch):
    _eventbrite(monkeypatch, [_event("E1")], {"E1": _classes((150, 400))})
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    _sync(client, tid)
    viewer, _v = _member_join(flask_app, client, tid, ["view", "marketing"], label="Viewer")
    home = viewer.get("/tours/%s" % tid).get_data(as_text=True)
    assert "Sync ticket sales" not in home and "/tickets/sync" not in home
    page = viewer.get("/tours/%s/shows/%s?tab=marketing" % (tid, sid)).get_data(as_text=True)
    assert "150 of 400 sold" in page, "the measured number is not a secret"
    assert "/tickets/link" not in page
    # And the route itself refuses, not just the button.
    assert viewer.post("/tours/%s/tickets/sync" % tid).status_code in (302, 403)
    assert ts.get_show(tid, sid)["tickets_sold"] == "150"


# --- the units ----------------------------------------------------------------

def test_the_match_rules_stand_on_their_own():
    show = {"id": "s1", "date": "2030-05-02", "venue": "The Basement East", "city": "Nashville, TN"}
    room = {"id": "E1", "date": "2030-05-02", "name": "Whoever", "venue": "Basement East",
            "city": "Nashville", "region": "TN"}
    billed = {"id": "E2", "date": "2030-05-02", "name": "Test Artist and friends",
              "venue": "Cannery Ballroom", "city": "Nashville", "region": "TN"}
    other = {"id": "E3", "date": "2030-05-02", "name": "Test Artist", "venue": "Bowery Ballroom",
             "city": "New York", "region": "NY"}
    assert tickets.plausible(show, "Test Artist", room)
    assert tickets.plausible(show, "Test Artist", billed)
    assert not tickets.plausible(show, "Test Artist", other), "another city is another show"
    assert not tickets.names_artist("Test Artist Live", "Testing Artist")
    assert tickets.match(show, "Test Artist", [room])[0] is room
    assert tickets.match(show, "Test Artist", [room, billed])[0] is None, "two is not one"
    assert [c["id"] for c in tickets.match(show, "Test Artist", [room, billed])[1]] == ["E1", "E2"]


def test_only_an_eventbrite_link_is_ours_to_replace():
    assert tickets.ours("")
    assert tickets.ours("https://www.eventbrite.com/e/123")
    assert tickets.ours("https://myband.eventbrite.com/e/123")
    assert tickets.ours("https://www.eventbrite.co.uk/e/123")
    assert not tickets.ours("https://tickets.example.com/x")
    assert not tickets.ours("https://not-eventbrite.com/e/1")


def test_the_status_words_are_the_ones_the_page_uses():
    assert tickets.status_for({"status": "live"}) == "on sale"
    assert tickets.status_for({"status": "live", "is_sold_out": True}) == "sold out"
    assert tickets.status_for({"status": "started"}) == "on sale"
    assert tickets.status_for({"status": "ended"}) == "ended"
    assert tickets.status_for({"status": "completed", "is_sold_out": True}) == "ended"


def test_an_unlimited_class_adds_its_sales_but_not_a_capacity(monkeypatch):
    _eventbrite(monkeypatch, [], {"E1": [{"quantity_sold": 5, "quantity_total": None},
                                         {"quantity_sold": 7, "quantity_total": 40}]})
    assert eb.ticket_counts("E1") == (12, 40)
    _eventbrite(monkeypatch, [], {"E2": []})
    assert eb.ticket_counts("E2") == (None, None)

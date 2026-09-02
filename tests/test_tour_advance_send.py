"""Send the advance: one email to the venue with the rider and the plot.

The tour module had the checklist, the files, the share links and an
inbox for the venue's reply - everything except the act of sending the
packet. These tests cover the composer (every line traces to a row, money
never), the input list staying in step with the stage-plot designer, the
stage-plot image round trip, and the route: who may send, what reaches
the mailer, what is recorded, and the honest refusal when the deployment's
sender could not reach a venue anyway.
"""
import base64
import io
import os
import re
import uuid

import pytest

import app as appmod
import db as store
import email_provider as emailer
import tour_advance_mail as tam
import tour_store as ts
import tour_engine as eng

PASSWORD = "adv-pass-123"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _user(flask_app, label="Tour Owner"):
    email = "adv-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": label, "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client, store.get_user_by_email(email)


def _tour(client, **over):
    data = {"name": "Test Run", "artist_name": "Test Artist", "start_date": "2030-05-01",
            "end_date": "2030-05-10", "home_tz": "America/New_York", "currency": "USD"}
    data.update(over)
    r = client.post("/tours/new", data=data)
    assert r.status_code == 302
    return r.headers["Location"].rstrip("/").split("/")[-1]


def _show(client, tour_id, date_="2030-05-02", venue="The Basement East", city="Nashville, TN"):
    r = client.post("/tours/%s/days/add" % tour_id,
                    data={"date": date_, "kind": "show", "venue": venue, "city": city, "tz": "America/Chicago"})
    assert r.status_code == 302
    return r.headers["Location"].split("/shows/")[1].split("?")[0]


@pytest.fixture
def live_mail(monkeypatch):
    """A real sender, and a mailer that records instead of sending."""
    sent = []

    def fake_send(to, subject, html, attachments=None, reply_to=None, cc=None, text=None):
        sent.append({"to": to, "subject": subject, "html": html, "attachments": attachments or [],
                     "reply_to": reply_to, "cc": cc, "text": text})
        return True

    monkeypatch.setattr(emailer, "configured", lambda: True)
    monkeypatch.setattr(emailer, "using_shared_test_sender", lambda: False)
    monkeypatch.setattr(emailer, "sender", lambda: "Street Banker <advance@example.net>")
    monkeypatch.setattr(emailer, "send", fake_send)
    return sent


# --- the composer ------------------------------------------------------------

def _rows(**status_by_key):
    """Advance rows the way list_advance returns them, every item present."""
    out = []
    for category, items in ts.ADVANCE_CATEGORIES.items():
        for key, label in items:
            status, value = status_by_key.get(key, ("incomplete", ""))
            out.append({"item_key": key, "category": category, "label": label,
                        "status": status, "value": value, "comments": ""})
    return out


def test_the_email_confirms_what_it_has_and_asks_what_it_lacks():
    rows = _rows(catering=("complete", "Hot meal x8 at 5:30 PM"),
                 venue_contact=("complete", "Jane Doe, jane@venue.example"),
                 load_in=("incomplete", ""), parking=("waiting", ""))
    schedule = [{"category": "load_in", "start_time": "15:00", "precision": "exact"},
                {"category": "doors", "start_time": "19:00", "precision": "approx"},
                {"category": "set", "start_time": "", "precision": "tbd"}]
    lineup = [{"act_name": "Opener", "running_order": 1, "set_start": "20:00", "set_end": "20:30"},
              {"act_name": "Test Artist", "running_order": 2, "is_headliner": 1, "set_start": "21:00", "set_end": ""}]
    tour = {"name": "Test Run", "artist_name": "Test Artist"}
    show = {"date": "2030-05-02", "venue": "The Basement East", "city": "Nashville, TN",
            "guarantee": "5000", "deposit_required": "2500", "settlement_amount": "5200",
            "guest_allocation": "10", "guest_cutoff": "5 PM day of"}
    mail = tam.compose(tour, show, schedule, lineup, rows,
                       sender={"name": "Sam Booker", "email": "sam@example.net", "phone": "555-0100", "role": "Tour manager"},
                       links={"rider": "https://x.example/rider/abc", "production": ""},
                       attachment_names=["Stage plot (PNG)", "rider.pdf"],
                       fmt_time=eng.fmt_time, fmt_day=eng.fmt_day_long)
    text = mail["text"]
    assert mail["subject"].startswith("Advance: Test Artist at The Basement East")
    assert text.startswith("Hi Jane,")
    assert "Load-in: 3:00 PM" in text and "Doors: about 7:00 PM" in text and "Set: TBD" in text
    assert "Opener (8:00 PM–8:30 PM) · Test Artist (9:00 PM, headline)" in text
    assert "Catering: Hot meal x8 at 5:30 PM" in text
    assert "What time can we load in" in text and "Where does the van park" in text
    assert "We have 10 spots" in text and "5 PM day of" in text
    assert "https://x.example/rider/abc" in text and "rider.pdf" in text
    assert text.rstrip().endswith("sam@example.net · 555-0100")
    # Money never leaves in an advance.
    for figure in ("5000", "2500", "5200", "guarantee", "deposit", "settlement amount"):
        assert figure not in text.lower()


def test_travel_and_vip_items_are_never_asked_of_the_venue():
    rows = _rows()
    text = tam.compose({"name": "T", "artist_name": "A"}, {"date": "2030-05-02", "venue": "V"}, [], [], rows,
                       sender={"name": "S"}, links={}, attachment_names=[],
                       fmt_time=eng.fmt_time, fmt_day=eng.fmt_day_long)["text"]
    assert "Hotel" not in text and "VIP" not in text and "Airport" not in text
    assert "Please confirm: Curfew" not in text          # curfew has its own question
    assert "Is there a curfew" in text


def test_recipients_come_from_people_and_the_advance_only():
    people = [{"category": "Venue", "email": "prod@venue.example", "shows": []},
              {"category": "Crew", "email": "roadie@example.net", "shows": []},
              {"category": "Promoters", "email": "buyer@promo.example", "shows": ["other-show"]}]
    rows = _rows(venue_contact=("complete", "Jane <jane@venue.example> 555-0100"))
    assert tam.candidate_recipients(people, rows, "this-show") == ["prod@venue.example", "jane@venue.example"]


def test_the_input_list_matches_the_designer():
    """tour_advance_mail.PLOT_INPUTS mirrors stageplot.js CATALOG. Diffed,
    so a mic added on one side shows up as a red test rather than a wrong
    channel list in a venue's inbox."""
    js = io.open("static/js/stageplot.js", encoding="utf-8").read()
    catalog = js[js.index("var CATALOG = ["):js.index("];", js.index("var CATALOG = ["))]
    entries = re.findall(r'\{key: "(\w+)".*?inputs: \[(.*?)\]\}', catalog, re.S)
    from_js = [(key, re.findall(r'"([^"]*)"', inputs)) for key, inputs in entries]
    assert from_js == tam.PLOT_INPUTS


def test_channel_numbers_only_when_there_is_more_than_one():
    chans = tam.channel_list({"items": {"vox": 2, "bass": 1, "gtr": 1}})
    assert chans == ["Guitar Amp — SM57", "Bass — DI", "Vocal 1 — SM58", "Vocal 2 — SM58"]
    assert "1. Guitar Amp — SM57" in tam.input_list_text(chans, "Test Artist")


# --- the stage plot image ----------------------------------------------------

def test_the_plot_image_round_trips(flask_app):
    client, user = _user(flask_app)
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 200
    r = client.post("/stage-plot/image", data={"image": (io.BytesIO(png), "stage-plot.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 200 and r.get_json()["ok"]
    assert client.get("/stage-plot/image.png").get_data() == png
    bad = client.post("/stage-plot/image", data={"image": (io.BytesIO(b"GIF89a"), "x.png")},
                      content_type="multipart/form-data")
    assert bad.status_code == 400
    # Another account has no image and gets nothing, not somebody else's.
    other, _ = _user(flask_app, "Other")
    assert other.get("/stage-plot/image.png").status_code == 404


# --- the route ---------------------------------------------------------------

def test_the_tab_renders_and_refuses_on_the_shared_sender(flask_app, monkeypatch):
    monkeypatch.setattr(emailer, "configured", lambda: True)
    monkeypatch.setattr(emailer, "using_shared_test_sender", lambda: True)
    monkeypatch.setattr(emailer, "sender", lambda: "Street Banker <onboarding@resend.dev>")
    sent = []
    monkeypatch.setattr(emailer, "send", lambda *a, **k: sent.append((a, k)) or True)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    page = client.get("/tours/%s/shows/%s?tab=send" % (tid, sid))
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'name="to"' in body and "Advance: Test Artist at The Basement East" in body
    assert "shared test address" in body and "disabled" in body
    r = client.post("/tours/%s/shows/%s/advance/send" % (tid, sid), data={"to": "prod@venue.example"})
    assert r.status_code == 302 and "fail=sender" in r.headers["Location"]
    assert not sent and not ts.list_advance_sends(tid, sid)


def test_sending_delivers_the_packet_and_records_it(flask_app, live_mail):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    # Times, a bill, an answered item and an open one.
    client.post("/tours/%s/shows/%s/standard-day" % (tid, sid))
    client.post("/tours/%s/shows/%s/advance-bulk" % (tid, sid), data={
        "status__catering": "complete", "value__catering": "Hot meal x8",
        "status__venue_contact": "complete", "value__venue_contact": "Jane Doe, jane@venue.example"})
    # A rider on the show, a tech pack on the tour, an invoice that must not be offered.
    for entity, category, name in (("show", "rider", "rider.txt"), ("tour", "tech_pack", "tech.txt"),
                                   ("show", "invoice", "invoice.txt")):
        r = client.post("/tours/%s/files/upload" % tid, data={
            "entity_type": entity, "entity_id": sid if entity == "show" else "", "category": category,
            "file": (io.BytesIO(("contents of " + name).encode()), name)}, content_type="multipart/form-data")
        assert r.status_code == 302
    # A plot with inputs, and its image.
    client.post("/stage-plot/save", json={"name": "Test Artist", "items": {"vox": 2, "bass": 1}, "pos": {}})
    png = b"\x89PNG\r\n\x1a\n" + b"\1" * 64
    client.post("/stage-plot/image", data={"image": (io.BytesIO(png), "p.png")}, content_type="multipart/form-data")

    page = client.get("/tours/%s/shows/%s?tab=send" % (tid, sid)).get_data(as_text=True)
    assert 'value="jane@venue.example"' in page
    assert "rider.txt" in page and "tech.txt" in page and "invoice.txt" not in page
    assert "Input list (3 channels" in page and "Stage plot (PNG" in page
    assert "created when you send" in page

    rider_id = [f["id"] for f in ts.list_files(tid) if f["file_name"] == "rider.txt"][0]
    tech_id = [f["id"] for f in ts.list_files(tid) if f["file_name"] == "tech.txt"][0]
    r = client.post("/tours/%s/shows/%s/advance/send" % (tid, sid), data={
        "to": "jane@venue.example", "cc": "agent@example.net, not-an-address",
        "attach": ["plot", "inputs", rider_id, tech_id]})
    assert r.status_code == 302 and "sent=1" in r.headers["Location"], r.headers["Location"]

    mail = live_mail[-1]
    assert mail["to"] == "jane@venue.example" and mail["cc"] == ["agent@example.net"]
    assert mail["reply_to"] == owner["email"]
    assert mail["subject"].startswith("Advance: Test Artist at The Basement East")
    names = [a["filename"] for a in mail["attachments"]]
    assert names == ["test-artist-stage-plot.png", "test-artist-input-list.txt", "rider.txt", "tech.txt"]
    blobs = {a["filename"]: base64.b64decode(a["content"]) for a in mail["attachments"]}
    assert blobs["test-artist-stage-plot.png"] == png
    assert "Vocal 2 — SM58".encode("utf-8") in blobs["test-artist-input-list.txt"]
    assert blobs["rider.txt"] == b"contents of rider.txt"
    # The text carries the rows and the links; the links now exist. The
    # standard day set the schedule, not the checklist, so load-in is a
    # time we are working to AND a question still open with the venue.
    text = mail["text"]
    # A standard day is approximate by design, and the email says so.
    assert "Load-in: about 3:00 PM" in text and "Catering: Hot meal x8" in text
    assert "What time can we load in" in text
    hub = store.get_tour_show(owner["id"], sid)
    assert hub["share_token"] and "/rider/%s" % hub["share_token"] in text
    prod = [l for l in ts.list_share_links(tid) if l["scope"] == "production" and l["show_id"] == sid]
    assert len(prod) == 1 and "/tour-share/%s" % prod[0]["token"] in text
    assert flask_app.test_client().get("/rider/%s" % hub["share_token"]).status_code == 200
    # Recorded, and on the activity log.
    sends = ts.list_advance_sends(tid, sid)
    assert len(sends) == 1 and sends[0]["status"] == "sent" and sends[0]["attachments"] == names
    assert any(c["field"] == "sent" and "jane@venue.example" in c["after"] for c in ts.list_changes(tid))
    again = client.get("/tours/%s/shows/%s?tab=send" % (tid, sid)).get_data(as_text=True)
    assert "jane@venue.example" in again and "4 attachment" in ts.list_changes(tid)[0]["after"]
    # A second send reuses the links rather than minting new ones.
    client.post("/tours/%s/shows/%s/advance/send" % (tid, sid), data={"to": "jane@venue.example"})
    assert store.get_tour_show(owner["id"], sid)["share_token"] == hub["share_token"]
    assert len([l for l in ts.list_share_links(tid) if l["scope"] == "production" and l["show_id"] == sid]) == 1


def test_a_failed_send_is_recorded_as_failed(flask_app, live_mail, monkeypatch):
    monkeypatch.setattr(emailer, "send", lambda *a, **k: False)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    r = client.post("/tours/%s/shows/%s/advance/send" % (tid, sid), data={"to": "prod@venue.example"})
    assert "fail=send" in r.headers["Location"]
    sends = ts.list_advance_sends(tid, sid)
    assert sends and sends[0]["status"] == "failed"
    assert "This did not" not in client.get(r.headers["Location"]).get_data(as_text=True)
    assert "Not sent" in client.get(r.headers["Location"]).get_data(as_text=True)


def test_a_bad_address_never_reaches_the_mailer(flask_app, live_mail):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    r = client.post("/tours/%s/shows/%s/advance/send" % (tid, sid), data={"to": "venue"})
    assert "fail=to" in r.headers["Location"] and not live_mail


def test_a_stranger_cannot_send_from_somebody_elses_tour(flask_app, live_mail):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    stranger, _ = _user(flask_app, "Stranger")
    assert stranger.get("/tours/%s/shows/%s?tab=send" % (tid, sid)).status_code == 404
    assert stranger.post("/tours/%s/shows/%s/advance/send" % (tid, sid),
                         data={"to": "prod@venue.example"}).status_code == 404
    assert not live_mail


# --- advancing the whole run ------------------------------------------------

def test_bulk_advancing_sends_to_every_ticked_venue_with_an_address(flask_app, live_mail):
    client, owner = _user(flask_app)
    tid = _tour(client)
    s1 = _show(client, tid, "2030-05-02", "Room One")
    s2 = _show(client, tid, "2030-05-03", "Room Two")
    s3 = _show(client, tid, "2030-05-04", "Room Three")
    client.post("/tours/%s/shows/%s/advance-bulk" % (tid, s1), data={
        "status__venue_contact": "complete", "value__venue_contact": "Ana, one@venue.example"})
    client.post("/tours/%s/shows/%s/advance-bulk" % (tid, s2), data={
        "status__promoter": "complete", "value__promoter": "two@venue.example"})

    page = client.get("/tours/%s/shows" % tid).get_data(as_text=True)
    assert "one@venue.example" in page and "two@venue.example" in page and "no address" in page
    assert 'value="%s"' % s1 in page and 'value="%s"' % s2 in page
    assert "Send 2 advances" in page

    r = client.post("/tours/%s/advance/send-all" % tid, data={"show": [s1, s2, s3]})
    assert r.status_code == 302
    assert "advanced=2" in r.headers["Location"] and "advance_skipped=1" in r.headers["Location"]
    assert sorted(m["to"] for m in live_mail) == ["one@venue.example", "two@venue.example"]
    for m in live_mail:
        assert m["subject"].startswith("Advance: Test Artist at Room")
        assert m["reply_to"] == owner["email"]
        assert "Hi" in m["text"] and "Room" in m["text"]
    assert [m["text"].startswith("Hi Ana,") for m in live_mail].count(True) == 1
    assert len(ts.list_advance_sends(tid)) == 2
    assert all(s["status"] == "sent" for s in ts.list_advance_sends(tid))

    # The page the redirect lands on says what happened; the list shows the
    # two as sent and offers only what is left.
    page = client.get(r.headers["Location"]).get_data(as_text=True)
    assert page.count("to-chip--ok") >= 2 and "2 advances sent" in page
    assert 'value="%s"' % s1 not in page and "Every show with an address has been advanced" in page
    assert "Room Three" in page          # still listed under "No address yet"


def test_bulk_advancing_refuses_on_the_shared_sender(flask_app, monkeypatch):
    monkeypatch.setattr(emailer, "configured", lambda: True)
    monkeypatch.setattr(emailer, "using_shared_test_sender", lambda: True)
    sent = []
    monkeypatch.setattr(emailer, "send", lambda *a, **k: sent.append(1) or True)
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, "2030-05-02", "Room One")
    client.post("/tours/%s/shows/%s/advance-bulk" % (tid, sid), data={
        "status__venue_contact": "complete", "value__venue_contact": "one@venue.example"})
    page = client.get("/tours/%s/shows" % tid).get_data(as_text=True)
    assert "disabled" in page and "shared test address" in page
    r = client.post("/tours/%s/advance/send-all" % tid, data={"show": [sid]})
    assert "advance_fail=sender" in r.headers["Location"] and not sent


def test_a_stranger_cannot_advance_somebody_elses_run(flask_app, live_mail):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid, "2030-05-02", "Room One")
    stranger, _ = _user(flask_app, "Stranger")
    assert stranger.post("/tours/%s/advance/send-all" % tid, data={"show": [sid]}).status_code == 404
    assert not live_mail

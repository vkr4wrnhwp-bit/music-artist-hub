# -*- coding: utf-8 -*-
"""The announcement desk: one page for writing it and one for pitching it.

The owner's design of 2026-09-20 put the announcement and the pitch side
by side, because the two pages they replaced made an artist choose who a
story goes to on a screen that no longer showed the story.

Three things these tests care about more than the layout:

  The rail counts only what it has. A chosen count, a contact list and a
  send button that says "Send 4 pitches" are all measurements, and every
  one of them is drawn from this artist's own rows or replaced by a
  sentence saying there is nothing to draw from.

  The two forms stay two forms. The announcement saves without sending
  anything, and /press-desk/pitch/new is still its own page, still
  reachable, still working. A second way to pitch was added; the first
  was not taken away.

  The mockup's furniture stays in the mockup. It carried a preview
  switch and a cast of invented journalists to demonstrate the states.
  None of that ships.
"""
import io
import os
import re
import uuid

import pytest

import app as appmod
import db as store
import press_desk
import press_store

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "announce-secret-1"

TEMPLATE = os.path.join(HERE, "templates", "press", "announcement_desk.html")


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _artist(flask_app, label="Desk Artist"):
    email = "desk-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": label, "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client, store.get_user_by_email(email)


def _contact(client, name="Dee Okafor", outlet="Nightdrive Mag", **fields):
    data = {"name": name, "outlet": outlet, "role": "Writer",
            "email": "dee-%s@example.com" % uuid.uuid4().hex[:6]}
    data.update(fields)
    client.post("/press-desk/contacts/new", data=data)
    return data


def _announcement(client, user, **fields):
    data = {"title": "Nightdrive single", "kind": "Single",
            "headline": "The band announces Nightdrive",
            "body": "First paragraph.\n\nSecond paragraph."}
    data.update(fields)
    client.post("/press-desk/announcements/new", data=data)
    return press_store.list_releases(user["id"])[0]


def _page(client, release):
    response = client.get("/press-desk/announcements/%s" % release["id"])
    assert response.status_code == 200
    return response.get_data(as_text=True)


def _template_source():
    return io.open(TEMPLATE, encoding="utf8").read()


def _input_value(body, name):
    """What the box called `name` is showing, whatever order its other
    attributes happen to be written in."""
    match = re.search(r'<input[^>]*\bname="%s"[^>]*>' % re.escape(name), body)
    assert match, "no input named %r on the page" % name
    value = re.search(r'\bvalue="([^"]*)"', match.group(0))
    return value.group(1) if value else None


# --- the page itself --------------------------------------------------------

def test_the_desk_opens_for_a_signed_in_artist(flask_app):
    client, user = _artist(flask_app)
    release = _announcement(client, user)
    body = _page(client, release)

    # The announcement is the main column and the pitch is the rail, and
    # they are two forms: one saves, the other sends.
    assert 'id="ad-announcement"' in body
    assert 'action="/press-desk/announcements/%s"' % release["id"] in body
    assert 'id="ad-pitch"' in body
    assert 'action="/press-desk/pitch/new"' in body
    assert '<input type="hidden" name="release_id" value="%s">' % release["id"] in body

    # The rail's recap shows what was written, not a placeholder.
    assert "The band announces Nightdrive" in body
    assert "Pitch it" in body


def test_the_announcement_form_is_not_the_pitch_form(flask_app):
    """Two forms, so an artist can save what they wrote without sending
    anything to anybody. A single form would make Save a send."""
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user)
    body = _page(client, release)

    main = body[body.index('id="ad-announcement"'):body.index("</form>")]
    assert 'name="contact_ids"' not in main
    assert 'name="mode"' not in main
    assert "</form>" in body


def test_every_announcement_field_round_trips(flask_app):
    client, user = _artist(flask_app)
    release = _announcement(client, user)

    posted = {
        "title": "Internal name for it",
        "kind": "Music video",
        "headline": "The video for Nightdrive is out",
        "subhead": "Shot in one take on the last night of the tour",
        "dateline_city": "Bristol",
        "dateline_date": "2026-10-03",
        "body": "What happened.\n\nWhy it matters.",
        "quote": "We only had the room for an hour.",
        "quote_source": "Dee Okafor, director",
        "listen_url": "https://example.com/listen",
        "epk_url": "https://example.com/kit",
        "release_date": "2026-10-17",
        "embargo_date": "2026-10-17",
        "embargo_time": "09:00",
        "contact_name": "Ray Mensah",
        "contact_email": "press@example.com",
        "boilerplate": "Two sentences that never change.",
        "status": "ready",
    }
    response = client.post("/press-desk/announcements/%s" % release["id"],
                           data=posted)
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    saved = press_store.get_release(user["id"], release["id"])
    assert saved["title"] == "Internal name for it"
    assert saved["kind"] == "Music video"
    assert saved["dateline"] == "Bristol, 3 October 2026"
    assert saved["embargo_until"] == "2026-10-17T09:00"
    assert saved["status"] == "ready"

    # And every one of them comes back into the boxes it came from.
    for name, value in (
            ("title", "Internal name for it"),
            ("headline", "The video for Nightdrive is out"),
            ("subhead", "Shot in one take on the last night of the tour"),
            ("dateline_city", "Bristol"),
            ("dateline_date", "2026-10-03"),
            ("listen_url", "https://example.com/listen"),
            ("epk_url", "https://example.com/kit"),
            ("release_date", "2026-10-17"),
            ("embargo_date", "2026-10-17"),
            ("embargo_time", "09:00"),
            ("contact_name", "Ray Mensah"),
            ("contact_email", "press@example.com")):
        assert _input_value(body, name) == value, name
    assert "What happened.\n\nWhy it matters." in body
    assert "We only had the room for an hour." in body
    assert "Two sentences that never change." in body
    assert 'name="quote_source" value="Dee Okafor, director"' in body
    assert '<option value="ready" selected>' in body


def test_the_internal_title_is_kept_and_labelled(flask_app):
    """The design omits it; the column is still there and still the name
    the announcement carries around the desk."""
    client, user = _artist(flask_app)
    release = _announcement(client, user)
    body = _page(client, release)
    assert "Internal title" in body
    assert "Only you see this" in body


def test_the_kind_list_is_the_stores_own(flask_app):
    """Not the mockup's invented list: Album / EP is a kind, Album is
    not, and a kind the store does not know silently becomes Single."""
    client, user = _artist(flask_app)
    release = _announcement(client, user)
    body = _page(client, release)
    for kind in press_store.RELEASE_KINDS:
        assert ">%s</option>" % kind in body, kind
    assert ">Tour</option>" not in body
    assert ">Signing</option>" not in body


# --- the dateline, split and composed ---------------------------------------

def test_compose_dateline():
    assert press_store.compose_dateline("Atlanta", "2026-10-03") == \
        "Atlanta, 3 October 2026"
    assert press_store.compose_dateline("Atlanta", "") == "Atlanta"
    assert press_store.compose_dateline("  Atlanta  ", None) == "Atlanta"
    # A date with no place is not a dateline.
    assert press_store.compose_dateline("", "2026-10-03") == ""
    assert press_store.compose_dateline(None, None) == ""


def test_split_dateline():
    assert press_store.split_dateline("Atlanta, 3 October 2026") == \
        ("Atlanta", "2026-10-03")
    assert press_store.split_dateline("New York, NY, 14 August 2026") == \
        ("New York, NY", "2026-08-14")
    assert press_store.split_dateline("") == ("", "")
    assert press_store.split_dateline(None) == ("", "")


def test_a_dateline_round_trips():
    for city, iso in (("Atlanta", "2026-10-03"), ("London", "2026-01-01"),
                      ("New York, NY", "2026-12-31")):
        stored = press_store.compose_dateline(city, iso)
        assert press_store.split_dateline(stored) == (city, iso)


def test_an_unparseable_dateline_is_never_lost():
    """Whatever the desk cannot read goes back into the city box whole,
    rather than being dropped on the way through the form."""
    for odd in ("Somewhere in Kent", "Atlanta 3 October 2026",
                "Atlanta, October 2026", "Atlanta, 3 Octobre 2026",
                "Atlanta, 3/10/2026"):
        assert press_store.split_dateline(odd) == (odd, ""), odd


def test_an_unparseable_dateline_survives_the_page(flask_app):
    client, user = _artist(flask_app)
    release = _announcement(client, user)
    press_store.update_release(user["id"], release["id"],
                               {"dateline": "Somewhere in Kent"})
    body = _page(client, release)
    assert 'name="dateline_city" value="Somewhere in Kent"' in body
    assert 'name="dateline_date" value=""' in body


def test_a_caller_that_posts_a_raw_dateline_is_left_alone(flask_app):
    """The two boxes are the desk's idea, not the store's. Anything that
    posts the column straight through still works."""
    client, user = _artist(flask_app)
    release = _announcement(client, user)
    client.post("/press-desk/announcements/%s" % release["id"],
                data={"title": "Kept", "dateline": "Leeds, 2 May 2026"})
    saved = press_store.get_release(user["id"], release["id"])
    assert saved["dateline"] == "Leeds, 2 May 2026"


# --- the embargo, now with a time -------------------------------------------

def test_compose_and_split_embargo():
    assert press_store.compose_embargo("2026-10-17", "09:00") == \
        "2026-10-17T09:00"
    assert press_store.compose_embargo("2026-10-17", "") == "2026-10-17"
    assert press_store.compose_embargo("", "09:00") == ""
    assert press_store.split_embargo("2026-10-17T09:00") == \
        ("2026-10-17", "09:00")
    assert press_store.split_embargo("2026-10-17") == ("2026-10-17", "")
    assert press_store.split_embargo("") == ("", "")


def test_an_embargo_stores_its_time(flask_app):
    client, user = _artist(flask_app)
    release = _announcement(client, user)
    client.post("/press-desk/announcements/%s" % release["id"],
                data={"title": "Held", "embargo_date": "2026-10-17",
                      "embargo_time": "09:00"})
    saved = press_store.get_release(user["id"], release["id"])
    assert saved["embargo_until"] == "2026-10-17T09:00"

    body = _page(client, release)
    assert 'name="embargo_date" value="2026-10-17"' in body
    assert 'name="embargo_time" value="09:00"' in body
    assert "Held under embargo until 17 October 2026, 09:00." in body


def test_embargo_active_reads_an_old_date_only_row_exactly_as_before():
    """The column widened from ten characters to sixteen. A row written
    before that has to answer the same question the same way."""
    old = {"embargo_until": "2026-10-17"}
    assert press_store.embargo_active(old, today="2026-10-16") is True
    assert press_store.embargo_active(old, today="2026-10-17") is False
    assert press_store.embargo_active(old, today="2026-10-18") is False
    assert press_store.embargo_active({"embargo_until": ""}) is False
    assert press_store.embargo_active(None) is False


def test_embargo_active_ignores_the_time_of_day():
    timed = {"embargo_until": "2026-10-17T09:00"}
    assert press_store.embargo_active(timed, today="2026-10-16") is True
    assert press_store.embargo_active(timed, today="2026-10-17") is False


def test_embargo_label_says_what_is_true():
    assert press_store.embargo_label({"embargo_until": "2026-10-17T09:00"}) == \
        "Held under embargo until 17 October 2026, 09:00."
    assert press_store.embargo_label({"embargo_until": "2026-10-17"}) == \
        "Held under embargo until 17 October 2026."
    assert press_store.embargo_label({"embargo_until": ""}) == \
        "No embargo set. Journalists may publish as soon as they read it."
    assert press_store.embargo_label(None) == \
        "No embargo set. Journalists may publish as soon as they read it."


def test_no_embargo_says_so_on_the_page(flask_app):
    client, user = _artist(flask_app)
    release = _announcement(client, user)
    body = _page(client, release)
    assert "No embargo set. Journalists may publish as soon as they read it." \
        in body


# --- the rail's contacts ----------------------------------------------------

def test_the_rail_lists_this_artists_contacts_and_no_others(flask_app):
    mine, me = _artist(flask_app, "Mine")
    _contact(mine, name="Dee Okafor", outlet="Nightdrive Mag")
    release = _announcement(mine, me)

    theirs, _them = _artist(flask_app, "Theirs")
    _contact(theirs, name="Someone Else", outlet="Another Outlet")

    body = _page(mine, release)
    assert "Dee Okafor" in body
    assert "Nightdrive Mag" in body
    assert "Someone Else" not in body
    assert "Another Outlet" not in body


def test_the_count_line_never_renders_a_zero_as_a_measurement(flask_app):
    client, user = _artist(flask_app)
    for name in ("One Writer", "Two Writer", "Three Writer"):
        _contact(client, name=name)
    release = _announcement(client, user)
    body = _page(client, release)

    assert "No contacts chosen yet. Tick the people this should reach." in body
    assert "0 chosen from" not in body
    # The pattern the script fills in as boxes are ticked carries the
    # real total, so the sentence cannot start counting a different list.
    assert 'data-some="%d chosen from 3 contacts on your list."' in body


def test_the_count_line_is_written_once():
    assert press_desk.count_line(0, 12) == \
        "No contacts chosen yet. Tick the people this should reach."
    assert press_desk.count_line(4, 12) == "4 chosen from 12 contacts on your list."
    assert press_desk.count_line(1, 1) == "1 chosen from 1 contact on your list."
    assert press_desk.count_line("%d", 12) == \
        "%d chosen from 12 contacts on your list."


def test_an_empty_media_list_is_a_sentence_not_an_empty_box(flask_app):
    client, user = _artist(flask_app)
    release = _announcement(client, user)
    body = _page(client, release)
    assert "Your media list is empty, so there is nobody to pitch." in body
    assert 'href="/press-desk/contacts"' in body
    assert 'id="ad-list"' not in body
    assert 'name="contact_ids"' not in body


def test_the_hundred_per_pitch_cap_is_said_out_loud(flask_app):
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user)
    body = _page(client, release)
    assert "A pitch carries at most %d contacts." % press_store.MAX_RECIPIENTS \
        in body


# --- the send button --------------------------------------------------------

def test_the_send_button_counts_what_is_ticked():
    own, platform = press_store.MODE_OWN_INBOX, press_store.MODE_PLATFORM
    assert press_desk.send_button(own, 1, "h", "b") == \
        {"label": "Prepare 1 email in my inbox", "disabled": False}
    assert press_desk.send_button(own, 4, "h", "b") == \
        {"label": "Prepare 4 emails in my inbox", "disabled": False}
    assert press_desk.send_button(platform, 1, "h", "b") == \
        {"label": "Send 1 pitch", "disabled": False}
    assert press_desk.send_button(platform, 4, "h", "b") == \
        {"label": "Send 4 pitches", "disabled": False}


def test_the_send_button_names_what_is_missing():
    own = press_store.MODE_OWN_INBOX
    assert press_desk.send_button(own, 4, "", "b") == \
        {"label": "Write a headline first", "disabled": True}
    assert press_desk.send_button(own, 0, "h", "b") == \
        {"label": "Choose who it goes to", "disabled": True}
    assert press_desk.send_button(own, 4, "h", "") == \
        {"label": "Write the announcement first", "disabled": True}


def test_the_send_button_arrives_disabled_with_nobody_ticked(flask_app):
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user)
    body = _page(client, release)
    button = body[body.index('id="ad-send"'):body.index("</button>",
                                                        body.index('id="ad-send"'))]
    assert "disabled" in button
    assert "Choose who it goes to" in button
    # And the phrasing the script will use is handed to it, not invented.
    assert 'data-own-one="Prepare %d email in my inbox"' in button
    assert 'data-own-many="Prepare %d emails in my inbox"' in button
    assert 'data-platform-one="Send %d pitch"' in button
    assert 'data-platform-many="Send %d pitches"' in button


def test_a_headline_that_is_missing_is_the_first_thing_said(flask_app):
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user, headline="")
    body = _page(client, release)
    assert "Write a headline first" in body


# --- how it goes out --------------------------------------------------------

def test_the_platform_radio_is_disabled_with_its_real_reason(flask_app,
                                                             monkeypatch):
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user)

    monkeypatch.setattr(press_desk, "send_state", lambda: {
        "platform": False,
        "reason": "The sending address has not been set up yet.",
        "detail": "So it is switched off until a real domain is configured."})
    body = _page(client, release)

    radio = body[body.index('value="%s"' % press_store.MODE_PLATFORM):]
    radio = radio[:radio.index("</label>")]
    assert "disabled" in radio
    assert "The sending address has not been set up yet." in radio
    # The always-available route stays available.
    assert 'value="%s" checked' % press_store.MODE_OWN_INBOX in body
    assert "From my own inbox" in body


def test_a_deployment_that_can_send_says_so(flask_app, monkeypatch):
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user)

    monkeypatch.setattr(press_desk, "send_state",
                        lambda: {"platform": True, "reason": "", "detail": ""})
    body = _page(client, release)
    radio = body[body.index('value="%s"' % press_store.MODE_PLATFORM):]
    radio = radio[:radio.index("</label>")]
    assert "disabled" not in radio
    assert "We send them and track who opens." in radio


# --- the press kit control --------------------------------------------------

def test_no_press_kit_means_no_control(flask_app, monkeypatch):
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user)
    monkeypatch.setattr(press_desk, "_kit_choices", lambda u: [])
    body = _page(client, release)
    assert 'name="kit"' not in body
    assert "Attach the press kit" not in body


def test_one_press_kit_is_a_checkbox_with_its_own_label(flask_app, monkeypatch):
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user)
    monkeypatch.setattr(press_desk, "_kit_choices", lambda u: [
        ("public", "Public press kit (live page)", "https://e/x", "")])
    body = _page(client, release)
    assert '<input type="checkbox" name="kit" value="public">' in body
    assert "Public press kit (live page)" in body
    assert 'id="ad-kit"' not in body


def test_two_press_kits_are_a_select_that_can_say_no(flask_app, monkeypatch):
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user)
    monkeypatch.setattr(press_desk, "_kit_choices", lambda u: [
        ("public", "Public press kit (live page)", "https://e/x", ""),
        ("vault:1", "Kit saved 14 August", "https://e/y", "1")])
    body = _page(client, release)
    assert '<select id="ad-kit" name="kit">' in body
    assert '<option value="">Do not attach one</option>' in body
    assert "Public press kit (live page)" in body
    assert "Kit saved 14 August" in body
    assert 'type="checkbox" name="kit"' not in body


# --- a new announcement does not pretend ------------------------------------

def test_a_new_announcement_has_no_pitch_controls(flask_app):
    client, _user = _artist(flask_app)
    _contact(client)
    response = client.get("/press-desk/announcements/new")
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "Save the announcement before you can pitch it." in body
    assert 'id="ad-pitch"' not in body
    assert 'name="contact_ids"' not in body
    assert 'name="release_id"' not in body
    assert 'id="ad-send"' not in body
    # The recap is a placeholder and says so.
    assert "Your headline appears here as you write it." in body
    assert "Add a dateline and a release date." in body
    # The announcement itself still creates, and still lands on the edit page.
    assert 'action="/press-desk/announcements/new"' in body


def test_creating_an_announcement_still_redirects_to_its_page(flask_app):
    client, user = _artist(flask_app)
    response = client.post("/press-desk/announcements/new",
                           data={"title": "Fresh", "headline": "Fresh news"})
    release = press_store.list_releases(user["id"])[0]
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/press-desk/announcements/%s" % release["id"])


# --- the standalone pitch page is still there -------------------------------

def test_the_standalone_pitch_page_still_renders(flask_app):
    client, user = _artist(flask_app)
    _contact(client)
    _announcement(client, user)
    response = client.get("/press-desk/pitch/new")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Send one announcement to a chosen few" in body
    assert 'action="/press-desk/pitch/new"' in body


def test_the_standalone_pitch_page_still_pitches(flask_app):
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user)
    ids = [c["id"] for c in press_store.list_contacts(user["id"])]
    response = client.post("/press-desk/pitch/new", data={
        "release_id": release["id"], "contact_ids": ids,
        "subject": "{artist}: {title}", "body": "Hi {name}, {link}",
        "mode": press_store.MODE_OWN_INBOX})
    assert response.status_code == 302
    pitch = press_store.list_pitches(user["id"])[0]
    assert response.headers["Location"].endswith(
        "/press-desk/pitch/%s" % pitch["id"])
    assert len(press_store.pitch_recipients(user["id"], pitch["id"])) == 1


def test_the_rail_pitches_the_same_way_the_page_does(flask_app):
    """The rail is a second door onto /press-desk/pitch/new, not a second
    implementation of it."""
    client, user = _artist(flask_app)
    _contact(client)
    release = _announcement(client, user)
    ids = [c["id"] for c in press_store.list_contacts(user["id"])]

    body = _page(client, release)
    assert 'value="%s"' % ids[0] in body

    response = client.post("/press-desk/pitch/new", data={
        "release_id": release["id"], "contact_ids": ids,
        "subject": press_desk.DEFAULT_SUBJECT,
        "body": press_desk.DEFAULT_BODY,
        "mode": press_store.MODE_OWN_INBOX})
    assert response.status_code == 302
    pitch = press_store.list_pitches(user["id"])[0]
    recipients = press_store.pitch_recipients(user["id"], pitch["id"])
    assert len(recipients) == 1
    assert recipients[0]["status"] == "prepared"


def test_the_desk_still_offers_the_standalone_pitch(flask_app):
    client, user = _artist(flask_app)
    _announcement(client, user)
    for path in ("/press-desk", "/press-desk/announcements"):
        body = client.get(path).get_data(as_text=True)
        assert 'href="/press-desk/pitch/new"' in body, path


# --- the mockup's furniture stays in the mockup -----------------------------

INVENTED = [
    "Nova Vale", "Hollow Lights", "Wire Season", "Isaiah Bell", "Renata Cole",
    "Dana Whitfield", "Marcus Iyer", "Priya Raman", "Toby Vance",
    "Elena Sarr", "Jonah Park", "Ruth Adeyemi", "Sam Delgado",
    "The Fader", "Pitchfork", "Rolling Stone", "Stereogum",
    "Creative Loafing", "Atlanta Journal", "Terminal West", "WRAS",
    "Adeem the Artist", "Sarah Shook", "BBC Radio 6",
]

TOUCHED = ["templates/press/announcement_desk.html", "press_desk.py",
           "press_store.py", "static/css/press-desk.css"]


def test_no_invented_name_from_the_mockup_ships():
    for rel in TOUCHED:
        source = io.open(os.path.join(HERE, rel), encoding="utf8").read()
        for name in INVENTED:
            assert name not in source, "%s carries %r" % (rel, name)


def test_the_preview_switch_does_not_ship():
    """New / Half written / Ready was a device for showing the owner
    three states in one file. There is one state here: the real one."""
    source = _template_source()
    for fixture in ("View state", "Half written", 'data-state="blank"',
                    "READY =", "BLANK =", "HALF ="):
        assert fixture not in source, fixture


def test_the_new_copy_carries_no_em_dashes():
    """A comma or a full stop, on everything written for this page. The
    press desk's older prose keeps its own, and so does DEFAULT_SUBJECT,
    which is a string artists have already used."""
    for rel in ("templates/press/announcement_desk.html",):
        source = io.open(os.path.join(HERE, rel), encoding="utf8").read()
        assert "—" not in source, rel

    css = io.open(os.path.join(HERE, "static", "css", "press-desk.css"),
                  encoding="utf8").read()
    assert "—" not in css[css.index("/* --- the announcement desk"):]

    written_here = list(press_desk.SEND_LABELS[press_store.MODE_OWN_INBOX])
    written_here += list(press_desk.SEND_LABELS[press_store.MODE_PLATFORM])
    written_here += [press_desk.NEEDS_HEADLINE, press_desk.NEEDS_CONTACTS,
                     press_desk.NEEDS_BODY, press_desk.NO_CONTACTS_CHOSEN,
                     press_store.embargo_label({"embargo_until": "2026-10-17"}),
                     press_store.embargo_label(None),
                     press_desk.count_line(2, 9)]
    for line in written_here:
        assert "—" not in line, line


def test_the_style_lives_in_the_stylesheet():
    """Ported into the desk's own sheet rather than inlined, and drawn
    from the app's tokens rather than the mockup's hex values."""
    source = _template_source()
    assert "<style" not in source
    css = io.open(os.path.join(HERE, "static", "css", "press-desk.css"),
                  encoding="utf8").read()
    assert ".ad-work" in css and ".ad-rail" in css
    ad = css[css.index("/* --- the announcement desk"):]
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", ad), \
        "the announcement desk section carries a raw colour"
    for mockup_hex in ("#0E0E0E", "#151515", "#242424", "#F2EFE9", "#C9A45C"):
        assert mockup_hex not in css


def test_the_page_stacks_for_a_phone():
    css = io.open(os.path.join(HERE, "static", "css", "press-desk.css"),
                  encoding="utf8").read()
    ad = css[css.index("/* --- the announcement desk"):]
    assert "@media (max-width: 1040px)" in ad
    assert "@media (max-width: 620px)" in ad
    collapsed = ad[ad.index("@media (max-width: 1040px)"):]
    assert "grid-template-columns: 1fr;" in collapsed
    stacked = ad[ad.index("@media (max-width: 620px)"):]
    assert ".ad-grid2, .ad-grid3 { grid-template-columns: 1fr; }" in stacked

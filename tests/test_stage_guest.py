"""Performer access by QR: a TOUR share link with scope "stage".

The phase 1 audit said the brief's QR requirement was already built in
tour_share_links, so this is that link opening the performer page for
somebody with no account. What must hold: the token is the only
authorisation and it is checked on every call; revoked and expired links
are dead; a password is asked for first; requests land in the owner's
queue exactly as they do from the owner's own session.
"""
import uuid

import pytest

import advance_store as adv
import app as appmod
import db as store
import passport_store as ps
import stage_store as st
import tour_store as ts

PASSWORD = "guest-rooms-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def show(application):
    """An owner with a tour, one date, a published passport attached to that
    date, and a live Stage Control share link for it."""
    email = "gst-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Guest Owner", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    r = client.post("/tours/new", data={
        "name": "Guest Run", "artist_name": "Prayers", "start_date": "2030-05-01",
        "end_date": "2030-05-10", "home_tz": "America/New_York", "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = client.post("/tours/%s/days/add" % tid, data={
        "date": "2030-05-02", "kind": "show", "venue": "The Basement East",
        "city": "Nashville, TN", "tz": "America/Chicago"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    with application.app_context():
        user = store.get_user_by_email(email)
        pid = ps.create_passport(user["id"], artist_name="Prayers")
        ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
        ps.add_row("inputs", pid, channel="2", source="Kick", sort=2)
        ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", safe_start="-20 dB", sort=1)
        ps.publish(pid, user["id"])
        adv.attach(sid, user["id"], pid)
    client.post("/tours/%s/share/new" % tid, data={"scope": "stage", "show_id": sid})
    with application.app_context():
        link = [l for l in ts.list_share_links(tid) if l["scope"] == "stage"][0]
    return {"client": client, "user": user, "tour": tid, "show": sid, "link": link,
            "token": link["token"]}


def _phone(application):
    return application.test_client()


# --- making the link ---------------------------------------------------------------

def test_the_share_page_offers_stage_control_and_a_qr(show):
    page = show["client"].get("/tours/%s/share" % show["tour"]).get_data(as_text=True)
    assert 'value="stage"' in page and "Stage Control" in page
    assert "/share/%s/qr.svg" % show["link"]["id"] in page
    qr = show["client"].get("/tours/%s/share/%s/qr.svg" % (show["tour"], show["link"]["id"]))
    assert qr.status_code == 200 and qr.mimetype == "image/svg+xml"
    assert b"<svg" in qr.data


def test_the_desk_points_at_where_the_qr_is_made(show):
    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    assert "Performer access" in desk and "/tours/%s/share" % show["tour"] in desk


# --- opening it -----------------------------------------------------------------------

def test_a_stranger_opens_the_performer_page_from_the_link(show, application):
    phone = _phone(application)
    r = phone.get("/tour-share/%s" % show["token"])
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Who is this?" in body and "Leafar" in body
    assert "/stage/guest/%s?as=" % show["token"] in body
    with application.app_context():
        assert ts.get_share_link(show["token"])["access_count"] == 1


def test_the_guest_page_shows_their_mix_and_posts_a_request(show, application):
    phone = _phone(application)
    body = phone.get("/stage/guest/%s?as=Leafar" % show["token"]).get_data(as_text=True)
    assert "Mix 1" in body and "Lead Vox" in body and "Kick" in body
    assert 'action="/stage/guest/%s/ask"' % show["token"] in body
    assert "/stage/%s/" % show["show"] not in body, "no owner URL leaks to a guest"
    r = phone.post("/stage/guest/%s/ask" % show["token"], data={
        "performer": "Leafar", "mix": "Mix 1", "kind": "more", "source": "Lead Vox", "step_db": "2"})
    assert r.status_code in (302, 303) and "refused" not in r.headers["Location"]
    with application.app_context():
        queue = st.for_show(show["show"], show["user"]["id"], open_only=True)
    assert len(queue) == 1 and queue[0]["performer"] == "Leafar"
    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    assert "Leafar" in desk and "Lead Vox" in desk
    # The performer sees it as sent, and can cancel it.
    body = phone.get("/stage/guest/%s?as=Leafar" % show["token"]).get_data(as_text=True)
    assert "Sent" in body
    phone.post("/stage/guest/%s/cancel/%s" % (show["token"], queue[0]["id"]))
    with application.app_context():
        assert st.get(queue[0]["id"], show["user"]["id"])["state"] == "cancelled"


def test_a_guest_cannot_claim_somebody_elses_mix(show, application):
    phone = _phone(application)
    r = phone.post("/stage/guest/%s/ask" % show["token"], data={
        "performer": "Leafar", "mix": "Mix 9", "kind": "more", "source": "Lead Vox", "step_db": "2"})
    assert "refused" in r.headers["Location"]
    with application.app_context():
        assert st.for_show(show["show"], show["user"]["id"]) == []


def test_the_guest_poll_works_without_a_session(show, application):
    phone = _phone(application)
    data = phone.get("/stage/guest/%s/events?since=0" % show["token"]).get_json()
    assert "cursor" in data and data["summary"]["open"] == 0


# --- the link is the authorisation -----------------------------------------------------

def test_a_revoked_link_is_dead_everywhere(show, application):
    show["client"].post("/tours/%s/share/%s/revoke" % (show["tour"], show["link"]["id"]))
    phone = _phone(application)
    assert phone.get("/tour-share/%s" % show["token"]).status_code == 404
    assert phone.get("/stage/guest/%s" % show["token"]).status_code == 404
    assert phone.post("/stage/guest/%s/ask" % show["token"], data={}).status_code == 404
    assert phone.get("/stage/guest/%s/events" % show["token"]).status_code == 404
    assert show["client"].get("/tours/%s/share/%s/qr.svg" % (show["tour"], show["link"]["id"])).status_code == 404


def test_an_expired_link_is_gone(show, application):
    show["client"].post("/tours/%s/share/new" % show["tour"],
                        data={"scope": "stage", "show_id": show["show"], "expires": "2001-01-01"})
    with application.app_context():
        old = [l for l in ts.list_share_links(show["tour"]) if l["expires"] == "2001-01-01"][0]
    assert _phone(application).get("/stage/guest/%s" % old["token"]).status_code == 410


def test_a_password_is_asked_for_first(show, application):
    show["client"].post("/tours/%s/share/new" % show["tour"],
                        data={"scope": "stage", "show_id": show["show"], "password": "encore"})
    with application.app_context():
        locked = [l for l in ts.list_share_links(show["tour"]) if l["password_hash"]][0]
    phone = _phone(application)
    r = phone.get("/stage/guest/%s" % locked["token"])
    assert r.status_code in (302, 303) and "/tour-share/" in r.headers["Location"]
    form = phone.get("/tour-share/%s" % locked["token"]).get_data(as_text=True)
    assert "password" in form.lower() and "Who is this?" not in form
    assert phone.post("/tour-share/%s" % locked["token"], data={"password": "wrong"}).status_code == 401
    ok = phone.post("/tour-share/%s" % locked["token"], data={"password": "encore"})
    assert ok.status_code == 200 and "Who is this?" in ok.get_data(as_text=True)
    assert phone.get("/stage/guest/%s?as=Leafar" % locked["token"]).status_code == 200


def test_another_scope_does_not_open_the_stage(show, application):
    show["client"].post("/tours/%s/share/new" % show["tour"],
                        data={"scope": "setlist", "show_id": show["show"]})
    with application.app_context():
        other = [l for l in ts.list_share_links(show["tour"]) if l["scope"] == "setlist"][0]
    assert _phone(application).get("/stage/guest/%s" % other["token"]).status_code == 404


def test_the_owners_own_page_still_works(show):
    body = show["client"].get("/stage/%s/me?as=Leafar" % show["show"]).get_data(as_text=True)
    assert 'action="/stage/%s/ask"' % show["show"] in body and "Mix 1" in body

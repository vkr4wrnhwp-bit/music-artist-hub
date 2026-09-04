"""Stage Control phase 4: the desk and the phone.

The store's state machine is tested in test_stage_store.py. This is about the
two rooms honouring it — in particular that the server checks mix ownership
itself rather than trusting the form, and that nothing on either screen says a
change happened when it has not.
"""
import uuid

import pytest

import advance_store as adv
import app as appmod
import passport_store as ps
import stage_store as st

PASSWORD = "stage-rooms-123"


@pytest.fixture(scope="module")
def application():
    return appmod.app


@pytest.fixture
def show(application):
    """A signed-in owner, a published passport with two mixes, and a show
    advanced against it."""
    email = "stage-%s@example.net" % uuid.uuid4().hex[:10]
    client = application.test_client()
    client.post("/signup", data={"name": "Stage Tester", "email": email,
                                 "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    with application.app_context():
        import db as store
        user = store.get_user_by_email(email)
        pid = ps.create_passport(user["id"], artist_name="Prayers")
        ps.add_row("inputs", pid, channel="1", source="Lead Vox", sort=1)
        ps.add_row("inputs", pid, channel="2", source="Kick", sort=2)
        ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar",
                   safe_start="-20 dB", sort=1)
        ps.add_row("outputs", pid, mix_name="Mix 2", performer="Javon",
                   safe_start="-20 dB", sort=2)
        ps.publish(pid, user["id"])
        sid = "show-" + uuid.uuid4().hex[:10]
        adv.attach(sid, user["id"], pid)
    return {"client": client, "user": user, "show": sid, "passport": pid}


def _ask(show, **over):
    args = {"performer": "Leafar", "mix": "Mix 1", "kind": "more",
            "source": "Lead Vox", "step_db": "2"}
    args.update(over)
    return show["client"].post("/stage/%s/ask" % show["show"], data=args)


# --- access ------------------------------------------------------------------

def test_a_stranger_is_sent_to_the_login(application):
    r = application.test_client().get("/stage/anything")
    assert r.status_code in (302, 401)


def test_a_show_with_no_passport_says_so(show, application):
    """You cannot take requests against a show nobody advanced - there are no
    mixes to take them against."""
    body = show["client"].get("/stage/show-nothing-here").get_data(as_text=True)
    assert "no passport attached" in body.lower()


# --- the phone ---------------------------------------------------------------

def test_the_picker_offers_only_performers_on_the_version(show):
    body = show["client"].get("/stage/%s/me" % show["show"]).get_data(as_text=True)
    assert "Leafar" in body and "Javon" in body


def test_a_performer_sees_their_own_mix_and_the_sources(show):
    body = show["client"].get("/stage/%s/me?as=Leafar" % show["show"]).get_data(as_text=True)
    assert "Mix 1" in body
    assert "Lead Vox" in body and "Kick" in body


def test_the_form_cannot_claim_somebody_elses_mix(show, application):
    """The phone only offers a performer their own mixes, but a template that
    hides a control is not a check. The server asks the frozen version."""
    _ask(show, performer="Leafar", mix="Mix 2")
    with application.app_context():
        assert st.for_show(show["show"], show["user"]["id"]) == []


def test_only_the_fixed_steps_are_accepted(show, application):
    _ask(show, step_db="11")
    with application.app_context():
        assert st.for_show(show["show"], show["user"]["id"]) == []


def test_a_request_reaches_the_queue(show, application):
    _ask(show)
    with application.app_context():
        queue = st.for_show(show["show"], show["user"]["id"], open_only=True)
    assert len(queue) == 1
    assert queue[0]["performer"] == "Leafar" and queue[0]["source"] == "Lead Vox"

    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    assert "Leafar" in desk and "Lead Vox" in desk


def test_a_report_needs_no_source(show, application):
    show["client"].post("/stage/%s/ask" % show["show"],
                        data={"performer": "Leafar", "mix": "Mix 1", "kind": "feedback"})
    with application.app_context():
        queue = st.for_show(show["show"], show["user"]["id"], open_only=True)
    assert queue and queue[0]["kind"] == "feedback" and queue[0]["urgent"] == 1


def test_a_refusal_comes_back_in_words_the_performer_can_read(show):
    r = _ask(show, mix="Mix 2")
    assert r.status_code in (302, 303)
    assert "refused" in r.headers["Location"]


# --- the desk ----------------------------------------------------------------

def test_done_on_the_desk_is_not_the_same_as_applied(show, application):
    """An engineer moving a fader is not a console confirming a command. The
    desk's button must produce applied_manually, never applied."""
    _ask(show)
    with application.app_context():
        rid = st.for_show(show["show"], show["user"]["id"], open_only=True)[0]["id"]
    show["client"].post("/stage/%s/request/%s/applied" % (show["show"], rid))
    with application.app_context():
        assert st.get(rid, show["user"]["id"])["state"] == "applied_manually"


def test_the_desk_can_acknowledge_and_reject(show, application):
    _ask(show)
    with application.app_context():
        rid = st.for_show(show["show"], show["user"]["id"], open_only=True)[0]["id"]
    show["client"].post("/stage/%s/request/%s/acknowledge" % (show["show"], rid))
    with application.app_context():
        assert st.get(rid, show["user"]["id"])["state"] == "acknowledged"
    show["client"].post("/stage/%s/request/%s/reject" % (show["show"], rid),
                        data={"reason": "Wedge is already at the feedback point"})
    with application.app_context():
        req = st.get(rid, show["user"]["id"])
    assert req["state"] == "rejected"
    assert "feedback point" in req["engineer_note"]


def test_an_illegal_move_is_refused_by_the_route_too(show, application):
    """The transition table is the guard, and the route does not get to skip
    it: there is no way to reach `applied` from `pending`."""
    _ask(show)
    with application.app_context():
        rid = st.for_show(show["show"], show["user"]["id"], open_only=True)[0]["id"]
    assert show["client"].post(
        "/stage/%s/request/%s/nonsense" % (show["show"], rid)).status_code == 404
    with application.app_context():
        assert st.get(rid, show["user"]["id"])["state"] == "pending"


def test_a_request_from_another_show_is_a_404(show, application):
    _ask(show)
    with application.app_context():
        rid = st.for_show(show["show"], show["user"]["id"], open_only=True)[0]["id"]
    assert show["client"].post(
        "/stage/other-show/request/%s/acknowledge" % rid).status_code == 404


# --- locks and the cursor ----------------------------------------------------

def test_a_lock_stops_new_requests(show, application):
    show["client"].post("/stage/%s/lock" % show["show"],
                        data={"scope": "show", "reason": "Doors are open."})
    _ask(show)
    with application.app_context():
        assert st.for_show(show["show"], show["user"]["id"]) == []

    show["client"].post("/stage/%s/lock" % show["show"],
                        data={"scope": "show", "release": "1"})
    _ask(show)
    with application.app_context():
        assert len(st.for_show(show["show"], show["user"]["id"])) == 1


def test_the_poll_returns_a_cursor_and_only_what_is_new(show):
    start = show["client"].get("/stage/%s/events?since=0" % show["show"]).get_json()
    _ask(show)
    later = show["client"].get(
        "/stage/%s/events?since=%d" % (show["show"], start["cursor"])).get_json()
    assert later["cursor"] > start["cursor"]
    assert [e["kind"] for e in later["events"]] == ["request.new"]
    assert later["summary"]["open"] == 1

    caught_up = show["client"].get(
        "/stage/%s/events?since=%d" % (show["show"], later["cursor"])).get_json()
    assert caught_up["events"] == []


def test_a_nonsense_cursor_does_not_explode(show):
    r = show["client"].get("/stage/%s/events?since=banana" % show["show"])
    assert r.status_code == 200 and "cursor" in r.get_json()


def test_the_mode_banner_is_always_on_screen(show):
    """The brief: the active mode must always be visible, and the product must
    never move from Request Mode into Connected Control silently."""
    desk = show["client"].get("/stage/%s" % show["show"]).get_data(as_text=True)
    phone = show["client"].get("/stage/%s/me?as=Leafar" % show["show"]).get_data(as_text=True)
    assert "Request Mode" in desk and "Request Mode" in phone
    assert "No console is connected" in desk

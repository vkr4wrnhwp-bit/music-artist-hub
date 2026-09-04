"""Stage Control phase 4: Request Mode.

The brief's hardest rule is "never present a requested change as applied until
confirmation is received". In this module that is not a promise, it is a data
structure: `applied` is not reachable from `pending`, so no caller can write it
by mistake. Most of this file leans on that table.

The rest is the things a template must not be trusted with - mix ownership,
bounded steps, rate limits, locks - and the event cursor that stands in for the
websockets this deployment cannot host.
"""
import uuid

import pytest

import stage_store as st

USER = "stage-tests"


@pytest.fixture(scope="module", autouse=True)
def schema():
    st.init_stage()


@pytest.fixture
def show():
    return "show-" + uuid.uuid4().hex[:10]


MIXES = ["Mix 1", "Mix 2"]
SOURCES = ["Lead Vox", "Kick", "Bass DI"]


def _submit(show, **over):
    args = dict(show_id=show, user_id=USER, performer="Leafar", mix="Mix 1",
                kind="more", source="Lead Vox", step_db=2,
                allowed_mixes=MIXES, allowed_sources=SOURCES)
    args.update(over)
    return st.submit(**args)


# --- the state machine, which is the safety feature ---------------------------

def test_a_request_cannot_jump_to_applied(show):
    """The whole confirmation rule, in one assertion. `applied` means a device
    said so; nothing may reach it by asking nicely."""
    rid = _submit(show)
    assert st.advance(rid, USER, "applied") is None
    assert st.get(rid, USER)["state"] == "pending"


def test_the_transition_table_is_the_only_writer(show):
    rid = _submit(show)
    assert st.can_move("pending", "acknowledged") is True
    assert st.can_move("pending", "applied") is False
    assert st.can_move("sent", "applied") is False, "a device must acknowledge first"
    assert st.can_move("device_acknowledged", "applied") is True
    assert st.can_move("rejected", "approved") is False, "terminal is terminal"
    assert st.advance(rid, USER, "not_a_state") is None


def test_applying_by_hand_is_not_the_same_as_applied(show):
    """Request Mode's honest end state. An engineer moving a fader is not a
    console confirming a command, and the two must not read alike."""
    rid = _submit(show)
    st.acknowledge(rid, USER, actor="Monitor eng")
    req = st.apply_manually(rid, USER, actor="Monitor eng")
    assert req["state"] == "applied_manually"
    assert st.PERFORMER_WORDING["applied_manually"] == "Done"
    assert req["state"] != "applied"


def test_the_device_path_needs_every_step(show):
    rid = _submit(show)
    st.acknowledge(rid, USER)
    st.approve(rid, USER, actor="Eng")
    assert st.advance(rid, USER, "queued_for_device") is not None
    assert st.advance(rid, USER, "applied") is None, "not without sending"
    assert st.advance(rid, USER, "sent") is not None
    assert st.advance(rid, USER, "applied") is None, "not without an acknowledgement"
    assert st.advance(rid, USER, "device_acknowledged", device_ack="0.62") is not None
    assert st.advance(rid, USER, "applied") is not None
    assert st.get(rid, USER)["state"] == "applied"


def test_a_failure_is_never_silently_a_success(show):
    rid = _submit(show)
    st.acknowledge(rid, USER)
    st.approve(rid, USER)
    st.advance(rid, USER, "queued_for_device")
    st.advance(rid, USER, "sent")
    req = st.advance(rid, USER, "failed", failure="No answer from the console")
    assert req["state"] == "failed"
    assert req["failure"] == "No answer from the console"
    assert st.advance(rid, USER, "applied") is None


# --- what a template must not be trusted with --------------------------------

def test_a_mix_that_is_not_yours_is_refused(show):
    with pytest.raises(st.Refused) as e:
        _submit(show, mix="Mix 9")
    assert "not yours" in str(e.value)


def test_a_source_outside_your_mix_is_refused(show):
    with pytest.raises(st.Refused):
        _submit(show, source="Somebody else's guitar")


def test_only_the_fixed_steps_are_accepted(show):
    """No sliders. The brief forbids a control that can jump a level, and this
    is where that is actually enforced."""
    for bad in (0, 4, 12, 99, -3):
        with pytest.raises(st.Refused) as e:
            _submit(show, step_db=bad)
        assert "fixed steps" in str(e.value)
    assert _submit(show, step_db=1)


def test_an_adjustment_needs_a_source(show):
    with pytest.raises(st.Refused):
        _submit(show, source="")


def test_a_report_needs_no_source_or_step(show):
    """Feedback is not an adjustment - it is a person telling you something is
    wrong, and demanding they pick a channel first would be absurd."""
    rid = st.submit(show_id=show, user_id=USER, performer="Leafar", mix="Mix 1",
                    kind="feedback", allowed_mixes=MIXES)
    assert st.get(rid, USER)["kind"] == "feedback"


def test_an_invented_kind_is_refused(show):
    with pytest.raises(st.Refused):
        _submit(show, kind="launch_pyro")


def test_the_rate_limit_counts_what_is_still_open(show):
    """Six unanswered requests is a person who needs the engineer to look up,
    not a person who needs a seventh."""
    for _ in range(6):
        _submit(show)
    with pytest.raises(st.Refused) as e:
        _submit(show)
    assert "still waiting" in str(e.value)
    # Answering one frees a slot: the limit is about the queue, not the clock.
    first = st.for_performer(show, "Leafar", open_only=True)[0]["id"]
    st.acknowledge(first, USER)
    st.apply_manually(first, USER)
    assert _submit(show)


# --- locks -------------------------------------------------------------------

def test_a_show_lock_stops_everybody(show):
    st.lock(show, "show", reason="Soundcheck over, doors open.")
    with pytest.raises(st.Refused) as e:
        _submit(show)
    assert "Soundcheck over" in str(e.value)
    st.unlock(show, "show")
    assert _submit(show)


def test_a_performer_lock_stops_only_them(show):
    st.lock(show, "performer", target="Leafar", reason="Talk to me on comms.")
    with pytest.raises(st.Refused):
        _submit(show)
    assert _submit(show, performer="Javon", mix="Mix 2")


def test_the_widest_lock_is_the_one_reported(show):
    """Telling somebody their mix is locked while the whole show is locked
    sends them to argue with the wrong person."""
    st.lock(show, "mix", target="Mix 1", reason="mix reason")
    st.lock(show, "show", reason="show reason")
    assert st.locked_reason(show, performer="Leafar", mix="Mix 1") == "show reason"


# --- the event cursor, standing in for websockets ----------------------------

def test_the_cursor_is_monotonic_and_replayable(show):
    start = st.cursor(show)
    a = _submit(show)
    b = _submit(show, performer="Javon", mix="Mix 2")
    events = st.events_since(show, start)
    assert [e["request_id"] for e in events] == [a, b]
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


def test_a_client_that_misses_a_poll_catches_up(show):
    start = st.cursor(show)
    rid = _submit(show)
    st.acknowledge(rid, USER, actor="Eng")
    st.apply_manually(rid, USER, actor="Eng")
    # One poll from the beginning sees every step, in order.
    kinds = [e["kind"] for e in st.events_since(show, start)]
    assert kinds == ["request.new", "request.acknowledged", "request.applied_manually"]


def test_polling_from_now_replays_nothing(show):
    _submit(show)
    now = st.cursor(show)
    assert st.events_since(show, now) == []


def test_events_are_scoped_to_their_show(show):
    other = "show-" + uuid.uuid4().hex[:10]
    _submit(show)
    _submit(other)
    assert all(e["show_id"] == show for e in st.events_since(show, 0))


def test_every_state_change_is_on_the_record(show):
    """The brief: realtime messages must not be the only durable record. Here
    they are not the record at all - the tables are - but the log still has to
    be complete or the desk misses things between polls."""
    start = st.cursor(show)
    rid = _submit(show)
    st.acknowledge(rid, USER)
    st.modify(rid, USER, 1, actor="Eng")
    st.approve(rid, USER)
    st.apply_manually(rid, USER)
    events = st.events_since(show, start)
    assert len(events) == 5
    assert events[-1]["payload"]["from"] == "approved"


# --- the queue ---------------------------------------------------------------

def test_urgent_reports_sort_above_adjustments(show):
    """Feedback behind four "more vocal" requests is a queue that has failed."""
    _submit(show)
    _submit(show, performer="Javon", mix="Mix 2")
    st.submit(show_id=show, user_id=USER, performer="Chriz", mix="Mix 2",
              kind="feedback", allowed_mixes=MIXES)
    first = st.for_show(show, USER, open_only=True)[0]
    assert first["kind"] == "feedback"


def test_the_summary_counts_what_the_desk_needs(show):
    _submit(show)
    rid = _submit(show, performer="Javon", mix="Mix 2")
    st.acknowledge(rid, USER)
    st.submit(show_id=show, user_id=USER, performer="Chriz", mix="Mix 2",
              kind="no_signal", allowed_mixes=MIXES)
    s = st.summary(show, USER)
    assert s["open"] == 3 and s["urgent"] == 1 and s["unseen"] == 2


def test_performer_wording_never_overclaims(show):
    """Only two states may say the change happened, and both require somebody
    or something to have confirmed it."""
    said_done = [k for k, v in st.PERFORMER_WORDING.items() if v == "Done"]
    assert sorted(said_done) == ["applied", "applied_manually"]
    assert st.PERFORMER_WORDING["sent"] != "Done"
    assert st.PERFORMER_WORDING["approved"] != "Done"


def test_a_cancelled_request_is_closed_and_stays_closed(show):
    rid = _submit(show)
    st.cancel(rid, USER, actor="Leafar")
    req = st.get(rid, USER)
    assert req["state"] == "cancelled" and req["closed_at"]
    assert st.advance(rid, USER, "approved") is None


def test_another_account_cannot_read_or_move_a_request(show):
    rid = _submit(show)
    assert st.get(rid, "somebody-else") is None
    assert st.advance(rid, "somebody-else", "acknowledged") is None
    assert st.get(rid, USER)["state"] == "pending"

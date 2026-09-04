"""Show advancement phase 3: a show keeps the document it agreed to.

The brief says it twice - "a booked show should retain the specific passport
version used during advancement" and "later passport edits must not silently
change historical shows" - so that is what most of this file is about. The
rest is the advance conversation: questions, conflicts, and refusing to call
something approved while either is open.
"""
import pytest

import advance_store as adv
import passport_store as ps

USER = "advance-tests"
SHOW = "show-fixture-1"


@pytest.fixture(scope="module", autouse=True)
def schema():
    ps.init_passports()
    adv.init_advance()


@pytest.fixture
def ready():
    """A published passport, and a show id to advance against it."""
    import uuid
    pid = ps.create_passport(USER, artist_name="Prayers", production_name="NTC")
    ps.add_row("inputs", pid, channel="1", source="Kick", sort=1)
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar",
               safe_start="-20 dB", sort=1)
    vid = ps.publish(pid, USER)
    return {"passport": pid, "version": vid, "show": "show-" + uuid.uuid4().hex[:10]}


# --- attaching ---------------------------------------------------------------

def test_attaching_defaults_to_the_version_in_force(ready):
    got = adv.attach(ready["show"], USER, ready["passport"])
    assert got == ready["version"]
    assert adv.get_attachment(ready["show"], USER)["state"] == "draft"


def test_a_passport_with_nothing_published_cannot_be_attached(ready):
    """There is no frozen document to advance against, and attaching a draft
    would be exactly the silent rewrite this module prevents."""
    empty = ps.create_passport(USER, artist_name="Unpublished")
    assert adv.attach(ready["show"], USER, empty) is None
    assert adv.get_attachment(ready["show"], USER) is None


def test_another_account_cannot_read_the_attachment(ready):
    adv.attach(ready["show"], USER, ready["passport"])
    assert adv.get_attachment(ready["show"], "somebody-else") is None


def test_a_version_from_a_different_passport_is_refused(ready):
    other = ps.create_passport(USER, artist_name="Other")
    ps.add_row("inputs", other, channel="1", source="X")
    other_version = ps.publish(other, USER)
    assert adv.attach(ready["show"], USER, ready["passport"],
                      version_id=other_version) is None


# --- the promise -------------------------------------------------------------

def test_the_show_keeps_its_version_when_the_passport_moves_on(ready):
    adv.attach(ready["show"], USER, ready["passport"])
    assert [r["source"] for r in adv.snapshot_for(ready["show"], USER)["inputs"]] == ["Kick"]

    ps.add_row("inputs", ready["passport"], channel="2", source="Snare", sort=2)
    ps.publish(ready["passport"], USER)

    frozen = adv.snapshot_for(ready["show"], USER)
    assert [r["source"] for r in frozen["inputs"]] == ["Kick"], \
        "the show must not follow the passport"


def test_a_newer_version_is_a_notice_never_an_action(ready):
    adv.attach(ready["show"], USER, ready["passport"])
    assert adv.newer_version_available(ready["show"], USER) is None

    ps.add_row("inputs", ready["passport"], channel="2", source="Snare", sort=2)
    ps.publish(ready["passport"], USER)

    notice = adv.newer_version_available(ready["show"], USER)
    assert notice["attached"] == 1 and notice["available"] == 2
    assert "inputs" in notice["diff"]
    # And it did NOT re-attach itself.
    assert adv.get_attachment(ready["show"], USER)["version_id"] == ready["version"]


def test_an_approved_show_cannot_have_its_document_swapped(ready):
    adv.attach(ready["show"], USER, ready["passport"])
    assert adv.approve(ready["show"], USER, actor="TM") is True

    ps.add_row("inputs", ready["passport"], channel="2", source="Snare", sort=2)
    newer = ps.publish(ready["passport"], USER)
    assert adv.attach(ready["show"], USER, ready["passport"], version_id=newer) is None
    assert adv.get_attachment(ready["show"], USER)["version_id"] == ready["version"]


def test_an_approved_show_cannot_be_detached(ready):
    """Detaching would delete the record of what was agreed."""
    adv.attach(ready["show"], USER, ready["passport"])
    assert adv.detach(ready["show"], USER) is True
    adv.attach(ready["show"], USER, ready["passport"])
    adv.approve(ready["show"], USER)
    assert adv.detach(ready["show"], USER) is False


# --- the conversation --------------------------------------------------------

def test_a_question_moves_the_advance_along_by_itself(ready):
    adv.attach(ready["show"], USER, ready["passport"])
    adv.set_state(ready["show"], USER, "reviewing")
    adv.ask(ready["show"], USER, "Is the stagebox on stage left?", section="inputs")
    assert adv.get_attachment(ready["show"], USER)["state"] == "questions_open"


def test_an_empty_question_is_not_stored(ready):
    adv.attach(ready["show"], USER, ready["passport"])
    assert adv.ask(ready["show"], USER, "   ") is None
    assert adv.questions(ready["show"], USER) == []


def test_answering_closes_the_question(ready):
    adv.attach(ready["show"], USER, ready["passport"])
    qid = adv.ask(ready["show"], USER, "Where is the stagebox?")
    assert adv.questions(ready["show"], USER, open_only=True)
    assert adv.answer(ready["show"], USER, qid, "Stage left, by the riser.") is True
    assert adv.questions(ready["show"], USER, open_only=True) == []


def test_conflicts_are_raised_and_resolved(ready):
    adv.attach(ready["show"], USER, ready["passport"])
    cid = adv.raise_conflict(ready["show"], USER,
                             "Passport needs 24 inputs; the house desk has 16.",
                             kind="inputs")
    assert adv.conflicts(ready["show"], USER, open_only=True)
    assert adv.resolve_conflict(ready["show"], USER, cid,
                                "Submixing keys to a stereo pair.") is True
    assert adv.conflicts(ready["show"], USER, open_only=True) == []


# --- approval ----------------------------------------------------------------

def test_a_show_with_no_passport_says_so_first(ready):
    found = adv.blockers(ready["show"], USER)
    assert found and "nothing to work from" in found[0]


def test_approval_is_blocked_while_anything_is_open(ready):
    """An approval with three unanswered questions on it is an approval
    nobody should trust."""
    adv.attach(ready["show"], USER, ready["passport"])
    adv.ask(ready["show"], USER, "Power?")
    assert adv.can_approve(ready["show"], USER) is False
    assert adv.approve(ready["show"], USER) is False

    qid = adv.questions(ready["show"], USER)[0]["id"]
    adv.answer(ready["show"], USER, qid, "63A three phase.")
    cid = adv.raise_conflict(ready["show"], USER, "No riser available.")
    assert adv.approve(ready["show"], USER) is False

    adv.resolve_conflict(ready["show"], USER, cid, "Band plays flat.")
    assert adv.can_approve(ready["show"], USER) is True
    assert adv.approve(ready["show"], USER, actor="Tour manager") is True

    link = adv.get_attachment(ready["show"], USER)
    assert link["state"] == "approved"
    assert link["approved_by"] == "Tour manager" and link["approved_at"]


def test_blockers_are_facts_not_a_percentage(ready):
    adv.attach(ready["show"], USER, ready["passport"])
    adv.ask(ready["show"], USER, "One")
    adv.ask(ready["show"], USER, "Two")
    found = adv.blockers(ready["show"], USER)
    assert "2 questions unanswered." in found
    assert not any("%" in f for f in found)


def test_an_unknown_state_is_refused(ready):
    adv.attach(ready["show"], USER, ready["passport"])
    assert adv.set_state(ready["show"], USER, "vibes") is False
    assert adv.get_attachment(ready["show"], USER)["state"] == "draft"

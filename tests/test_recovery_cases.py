"""An outcome means nothing if nothing was ever sent.

The case page offered "Mark Submitted", "Won - record payout" and "Lost"
the moment a case existed. So a case could read as submitted with no
letter sent and no document filed - self-reported state of exactly the
kind this product removes everywhere else, and worse here because the
pipeline total is money an artist may quote to somebody.

An outcome now opens up only once the case has actually been taken up:
a letter recorded as sent, or a document attached. And a case can be
deleted, which it could not be - one opened by mistake sat in the
pipeline for ever.
"""
import uuid

import pytest

import db as store
from app import create_app


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "cases-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "King 810", "email": email,
                                 "password": "casespw12345"})
    client.post("/plan/switch", data={"plan": "pro"})
    client._app = app_obj
    with app_obj.app_context():
        client._uid = store.get_user_by_email(email)["id"]
    return client


def _case(client, title="Coverage gap: Hungry Gods"):
    client.post("/royalty-recovery/cases",
                data={"title": title, "category": "coverage_gap",
                      "estimated_amount": "24.17"})
    with client._app.app_context():
        return store.list_recovery_cases(client._uid)[0]


def test_an_outcome_is_not_offered_before_anything_was_sent(artist):
    _case(artist)
    body = artist.get("/royalty-recovery/cases").get_data(as_text=True)
    assert "Draft the letter" in body
    assert "An outcome opens up once" in body
    assert "Won — record payout" not in body
    assert "Mark Submitted" not in body, (
        "submitted is a consequence of sending, not a button")


def test_recording_the_letter_moves_it_to_submitted_and_opens_the_outcome(artist):
    case = _case(artist)
    artist.post("/royalty-recovery/cases/%s/sent" % case["id"],
                data={"to": "Symphonic"})
    with artist._app.app_context():
        after = store.get_recovery_case(artist._uid, case["id"])
    assert after["status"] == "submitted"
    assert after["evidence_kind"] == "letter"
    assert "Symphonic" in after["evidence_detail"]
    assert after["evidence_at"]

    body = artist.get("/royalty-recovery/cases").get_data(as_text=True)
    assert "Won — record payout" in body
    assert "Letter sent to Symphonic" in body


def test_the_letter_is_a_draft_and_names_the_distributor(artist):
    case = _case(artist)
    body = artist.get("/royalty-recovery/cases/%s/letter"
                      % case["id"]).get_data(as_text=True)
    assert "Symphonic" in body
    assert "<textarea" in body, "editable, not a fixed block of text"
    # Phrased to survive the template's line wrapping.
    assert "it is a draft" in body
    assert "I have sent this" in body


def test_a_case_can_be_deleted_and_only_by_its_owner(artist):
    case = _case(artist)
    other = create_app().test_client()
    other.post("/signup", data={
        "name": "Someone", "password": "casespw12345",
        "email": "other-%s@example.net" % uuid.uuid4().hex[:8]})

    other.post("/royalty-recovery/cases/%s/delete" % case["id"])
    with artist._app.app_context():
        assert store.get_recovery_case(artist._uid, case["id"]), (
            "a guessed id must delete nothing")

    artist.post("/royalty-recovery/cases/%s/delete" % case["id"])
    with artist._app.app_context():
        assert store.get_recovery_case(artist._uid, case["id"]) is None


def test_evidence_does_not_overwrite_a_decided_case(artist):
    """A won case stays won; recording a letter later must not reopen it."""
    case = _case(artist)
    artist.post("/royalty-recovery/cases/%s/sent" % case["id"],
                data={"to": "Symphonic"})
    artist.post("/royalty-recovery/cases",
                data={"case_id": case["id"], "status": "won",
                      "payout_result": "12.00"})
    artist.post("/royalty-recovery/cases/%s/sent" % case["id"],
                data={"to": "Symphonic again"})
    with artist._app.app_context():
        after = store.get_recovery_case(artist._uid, case["id"])
    assert after["status"] == "won"

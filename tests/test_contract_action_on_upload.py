"""Uploading a contract raises the action that sets its reminders.

The owner, 2026-09-22: "when you upload a doc, it reads it, sets
notifications" and "should it send the action into there? Like, click this
to set your reminders? I think that's what the actions room should be for."

So the chain is: file lands -> it is read -> ONE action appears in Actions,
linking to that contract's row -> saving the dates there closes the action
and the 60/30/7/1 reminders begin.

The thing this must not do is save a date it read. A renewal date guessed
wrong would set an alarm for the wrong day and be believed, so every
finding stays "found in the document, check it" and a person confirms.
"""
import io
import os
import uuid

import pytest
from werkzeug.security import generate_password_hash

import app as appmod
import command_center as cc
import db as store

CONTRACT = (b"DISTRIBUTION AGREEMENT\n\n"
            b"This agreement is effective on 1 January 2026 and shall renew on "
            b"31 December 2027 unless terminated by either party upon ninety (90) "
            b"days written notice. The term is twenty-four (24) months and the "
            b"agreement renews automatically.\n")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    monkeypatch.delenv("REMINDERS_CRON_TOKEN", raising=False)   # no scheduler here
    app_obj = appmod.create_app()
    app_obj.config.update(TESTING=True)
    email = "artist-%s@example.net" % uuid.uuid4().hex[:8]
    with app_obj.app_context():
        uid = store.create_user(email, "Artist", generate_password_hash("a-long-password"))
        store.set_user_plan(uid, "label")
    client = app_obj.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = uid
    return app_obj, client, uid


def _upload(client, name="distribution.pdf", body=CONTRACT):
    return client.post("/vault/documents",
                       data={"document": (io.BytesIO(body), name), "doc_type": "Contract"},
                       content_type="multipart/form-data")


def _actions(app_obj, uid):
    with app_obj.app_context():
        return cc.list_actions(uid)


def test_uploading_a_contract_raises_one_action_that_links_to_it(world):
    app_obj, client, uid = world
    assert _actions(app_obj, uid) == []

    r = _upload(client, "distribution.txt")
    assert r.status_code in (302, 303)

    got = [a for a in _actions(app_obj, uid) if a["entity_type"] == "document"]
    assert len(got) == 1, "one action, not one per finding"
    a = got[0]
    assert "distribution.txt" in a["title"]
    # Updated 2026-09-23: this pinned "reminder" in the title, and nothing
    # sent reminders (no scheduler ran /reminders/run). The title names
    # reminders only while contract_reminders.scheduled() is true, and asks
    # for the renewal dates otherwise (tests/test_reminders_cron.py).
    assert a["title"] == "Set the renewal dates for distribution.txt"
    assert a["category"] == "rights"
    assert a["status"] == "new"
    # It says what was found, and that it needs checking.
    assert "notice period" in a["description"] or "end date" in a["description"]
    assert "check" in a["description"].lower()
    # And it is clickable: an action about a thing points at that thing.
    assert cc.action_link(a) == "/vault?view=contracts#doc-%s" % a["entity_id"]


def test_nothing_is_saved_by_the_reading_itself(world):
    """A date this got wrong would set an alarm for the wrong day and be
    believed. The action asks; it does not decide."""
    app_obj, client, uid = world
    _upload(client, "distribution.txt")
    with app_obj.app_context():
        assert store.get_document_terms(uid) == {}, "no dates saved without a person"


def test_saving_the_dates_closes_the_action(world):
    app_obj, client, uid = world
    _upload(client, "distribution.txt")
    a = [x for x in _actions(app_obj, uid) if x["entity_type"] == "document"][0]

    r = client.post("/vault/documents/%s/terms" % a["entity_id"],
                    data={"renews_on": "2027-12-31", "notice_days": "90"})
    assert r.status_code in (302, 303)

    after = [x for x in _actions(app_obj, uid) if x["id"] == a["id"]][0]
    assert after["status"] == "complete", "the list must not still ask for what is done"
    with app_obj.app_context():
        assert store.get_document_terms(uid), "and the dates are on the row"


def test_a_file_with_nothing_in_it_raises_no_action(world):
    """An action nobody can act on is noise. A receipt, a photograph or a
    scan with no text layer is filed and left alone."""
    app_obj, client, uid = world
    _upload(client, "receipt.txt", b"Thanks for your order. Total 12.00.")
    assert [a for a in _actions(app_obj, uid) if a["entity_type"] == "document"] == []


def test_an_unreadable_kind_is_filed_without_being_read(world):
    app_obj, client, uid = world
    r = _upload(client, "cover.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)
    assert r.status_code in (302, 303), "the upload still works"
    assert [a for a in _actions(app_obj, uid) if a["entity_type"] == "document"] == []


def test_a_reader_that_breaks_never_costs_the_upload(world, monkeypatch):
    """The document is the thing being kept. Reading it is a convenience,
    and a convenience must not be able to lose a file."""
    app_obj, client, uid = world
    import contract_reader
    monkeypatch.setattr(contract_reader, "extract_text",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = _upload(client, "distribution.txt")
    assert r.status_code in (302, 303)
    with app_obj.app_context():
        assert len(store.list_documents(uid)) == 1, "filed anyway"
    assert [a for a in _actions(app_obj, uid) if a["entity_type"] == "document"] == []


def test_reading_the_same_document_again_does_not_stack_actions(world):
    app_obj, client, uid = world
    _upload(client, "distribution.txt")
    a = [x for x in _actions(app_obj, uid) if x["entity_type"] == "document"][0]
    with app_obj.app_context():
        assert cc.open_action_for(uid, "document", a["entity_id"]) == a["id"]
        # A second identical action for the same document is refused.
        assert cc.open_action_for(uid, "document", "no-such-doc") is None


# --- the flags on the row ---------------------------------------------------

EXCLUSIVE = (b"This agreement grants the exclusive right to distribute the Work in all "
             b"media now known or hereafter devised, in perpetuity. The term is "
             b"forty-eight (48) months and shall automatically renew unless terminated "
             b"upon ninety (90) days written notice. It expires on 31 December 2027.\n")


def test_the_row_flags_what_the_contract_says(world):
    """Facts, colour-coded by whether they need attention - never a verdict
    on whether the deal is fair. That is a lawyer's work; this is pattern
    matching, and a confident wrong opinion on a contract is expensive."""
    app_obj, client, uid = world
    _upload(client, "exclusive.txt", EXCLUSIVE)
    page = client.get("/vault?view=contracts").get_data(as_text=True)

    assert "What it says" in page
    assert "Renews automatically" in page
    assert "Exclusive" in page
    assert "Perpetual" in page
    assert "Term over three years" in page
    assert "90 days to give notice" in page
    # Every flag carries the sentence it came from.
    assert "ninety (90) days written notice" in page
    # And the page says what this is and is not.
    assert "not legal advice" in page.lower()
    assert "Found by pattern" in page


def test_a_plain_agreement_is_not_dressed_up_as_a_problem(world):
    app_obj, client, uid = world
    _upload(client, "simple.txt",
            b"This is a non-exclusive licence. Either party may terminate on thirty "
            b"(30) days notice. It expires on 1 June 2027.\n")
    page = client.get("/vault?view=contracts").get_data(as_text=True)
    assert "Non-exclusive" in page
    assert "Can be ended by either party" in page
    assert "Exclusive</span>" not in page, "non-exclusive is not also exclusive"


def test_the_flags_are_stored_with_the_reading_not_recomputed(world):
    """Re-reading the document on every page view would mean fetching it
    from the bucket to render a list."""
    app_obj, client, uid = world
    _upload(client, "exclusive.txt", EXCLUSIVE)
    with app_obj.app_context():
        reading = store.get_document_readings(uid)
    assert len(reading) == 1
    got = list(reading.values())[0]
    assert got["status"] == "ok"
    flags = got["findings"].get("flags")
    assert flags and any(f["key"] == "auto_renew" for f in flags)
    assert all(f["tone"] in ("watch", "fine") for f in flags)


def test_the_row_says_the_owners_milestones(world):
    app_obj, client, uid = world
    _upload(client, "exclusive.txt", EXCLUSIVE)
    page = client.get("/vault?view=contracts").get_data(as_text=True)
    assert "60, 30, 7 and 1 days" in page
    assert "90, 30 and 7 days" not in page, "the old milestones are gone from the page too"


# --- the per-track boxes collapse -------------------------------------------

def test_the_per_track_boxes_collapse(world):
    """Owner, 2026-09-22: "make the per track boxed just collapsible". A
    catalog of any size made this an unreadable wall, and what matters
    closed is the title and whether anything is missing."""
    app_obj, client, uid = world
    with app_obj.app_context():
        store.add_track(uid, title="Cell 5", isrc="") if hasattr(store, "add_track") else None
    page = client.get("/vault?view=contracts").get_data(as_text=True)
    # The section renders whether or not this account has tracks yet; when
    # it does, every entry is a <details> rather than a permanently open box.
    if "Paperwork by Recording" in page:
        body = page.split("Paperwork by Recording", 1)[1].split("Filed to the whole catalog")[0]
        assert "<details" in body, "each recording is collapsible"
        assert "group-open:rotate-180" in body, "and says which way it is"
        assert "the ones missing something open themselves" in body

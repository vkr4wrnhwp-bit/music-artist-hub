"""A mandate could be created and deleted but never changed.

update_mandate sat in signal_store with no caller, so tuning one
criterion meant deleting the mandate and building it again. Everything
that references a mandate does so by id — the Deal Ready filter, the
audit trail — so delete-and-recreate silently breaks those links. It is
the crudest possible edit, and it is the same mistake VIP offers
deliberately avoid: deletion is not how you change your mind.

Pausing comes with it. Deal Ready filters on
list_mandates(active_only=True), so before this the only way to stop a
mandate applying was to destroy it.
"""
import os
import uuid

import pytest

import signal_store as sstore

PASSWORD = "mandate-edit-123"
BASE = {"genres": "alternative", "max_listeners": "250000",
        "min_momentum": "55", "min_gap": "65", "territories": "US Southeast"}


@pytest.fixture(scope="module")
def application():
    os.environ["OWNER_EMAILS"] = "mandate-owner@example.net"
    import app as appmod
    return appmod.app


@pytest.fixture
def owner(application):
    c = application.test_client()
    c.post("/signup", data={"name": "Owner", "email": "mandate-owner@example.net",
                            "password": PASSWORD})
    c.post("/login", data={"email": "mandate-owner@example.net", "password": PASSWORD})
    return c


def _make(owner, application, name=None):
    name = name or ("Mandate %s" % uuid.uuid4().hex[:6])
    owner.post("/signal/mandates", data=dict(BASE, name=name))
    with application.app_context():
        org = sstore.default_org()
        return org["id"], next(m for m in sstore.list_mandates(org["id"])
                               if m["name"] == name)


def test_a_criterion_can_be_changed_without_rebuilding_the_mandate(owner, application):
    org_id, m = _make(owner, application)
    owner.post("/signal/mandates/%s/edit" % m["id"],
               data=dict(BASE, name=m["name"], min_gap="70"))
    with application.app_context():
        after = sstore.get_mandate(org_id, m["id"])
    assert after["id"] == m["id"], (
        "the id is what every board and the audit trail refer to")
    assert after["criteria"]["min_gap"] == "70"
    assert after["criteria"]["min_momentum"] == "55", "the rest is untouched"


def test_the_edit_form_is_prefilled_with_what_it_holds_now(owner, application):
    _org_id, m = _make(owner, application)
    page = owner.get("/signal/mandates").get_data(as_text=True)
    assert "Edit this mandate" in page
    assert 'value="55"' in page and 'value="US Southeast"' in page, (
        "an edit is a change, not a retype")


def test_create_and_edit_read_the_criteria_the_same_way():
    """One reader, so a criterion you can set is one you can change."""
    import inspect

    import signal_hub
    src = inspect.getsource(signal_hub)
    assert src.count('request.form.get("min_gap")') == 1, (
        "two readers will drift into accepting different fields")
    assert "_mandate_criteria()" in src


def test_a_mandate_can_be_paused_instead_of_destroyed(owner, application):
    org_id, m = _make(owner, application)
    owner.post("/signal/mandates/%s/active" % m["id"], data={"active": "0"})
    with application.app_context():
        assert not sstore.get_mandate(org_id, m["id"])["active"]
        active = [x["id"] for x in sstore.list_mandates(org_id, active_only=True)]
        listed = [x["id"] for x in sstore.list_mandates(org_id)]
    assert m["id"] not in active, "Deal Ready stops filtering by it"
    assert m["id"] in listed, "and it is still there to come back to"


def test_a_paused_mandate_says_so_and_can_be_resumed(owner, application):
    org_id, m = _make(owner, application)
    owner.post("/signal/mandates/%s/active" % m["id"], data={"active": "0"})
    page = owner.get("/signal/mandates").get_data(as_text=True)
    assert "paused" in page and "Resume" in page
    owner.post("/signal/mandates/%s/active" % m["id"], data={"active": "1"})
    with application.app_context():
        assert sstore.get_mandate(org_id, m["id"])["active"]


def test_deleting_warns_that_pausing_is_the_gentler_answer(owner, application):
    _org_id, _m = _make(owner, application)
    page = owner.get("/signal/mandates").get_data(as_text=True)
    assert "Pausing keeps it" in page


def test_a_blank_name_is_refused_rather_than_saved(owner, application):
    org_id, m = _make(owner, application)
    owner.post("/signal/mandates/%s/edit" % m["id"], data=dict(BASE, name="   "))
    with application.app_context():
        assert sstore.get_mandate(org_id, m["id"])["name"] == m["name"]


def test_a_mandate_that_does_not_exist_is_a_404(owner):
    assert owner.post("/signal/mandates/nope/edit",
                      data={"name": "x"}).status_code == 404
    assert owner.post("/signal/mandates/nope/active",
                      data={"active": "0"}).status_code == 404

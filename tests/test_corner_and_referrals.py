"""Three sidebar and copy notes from the owner, 2026-09-15.

  * "cant inbox and notifications be up in the corner and not take up
    navigation space?": two small marks beside the search, the bell
    carrying the unread count; the Account group loses those two rows.
  * "all of label services are gone": the group was there, folded shut,
    because a group this browser had never toggled starts closed. Label
    Services now opens on first sight.
  * "referrals can definitely be worded better": plain words.
"""
import uuid

import db as store
from app import create_app

PW = "corner-12345"


def _client(app_obj, plan="pro"):
    c = app_obj.test_client()
    email = "corner-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Corner", "email": email, "password": PW})
    c.post("/plan/switch", data={"plan": plan})
    c._email = email
    return c


def test_inbox_and_the_bell_sit_in_the_corner_not_the_account_group():
    app_obj = create_app()
    c = _client(app_obj)
    body = c.get("/command-center").get_data(as_text=True)
    aside = body.split("</aside>")[0]
    assert 'id="sb-corner-inbox"' in aside and 'id="sb-corner-bell"' in aside
    account = aside.split('data-hub="account"')[1]
    assert 'href="/inbox"' not in account and 'href="/notifications"' not in account
    assert 'href="/settings"' in account and 'href="/billing"' in account, "the rest of the group stays"
    # the bell carries the unread count, in the corner and on the phone row
    with app_obj.app_context():
        uid = store.get_user_by_email(c._email)["id"]
        store.notify(uid, "system", "Two things happened", "while you were away")
        store.notify(uid, "system", "And a third", "")
    body = c.get("/command-center").get_data(as_text=True)
    aside = body.split("</aside>")[0]
    assert 'aria-label="Notifications, 2 unread"' in aside
    assert aside.count(">2</span>") >= 2, "the corner bell and the phone row both show it"


def test_label_services_opens_the_first_time_it_is_seen():
    app_obj = create_app()
    label = _client(app_obj, "label")
    body = label.get("/command-center").get_data(as_text=True)
    assert 'data-hub="label" data-open="1"' in body
    assert 'h.dataset.open === "1"' in body, "the collapse script honours it"
    pro = _client(app_obj, "pro")
    assert 'data-hub="label"' not in pro.get("/command-center").get_data(as_text=True)


def test_referrals_read_in_plain_words():
    app_obj = create_app()
    c = _client(app_obj)
    body = c.get("/referrals").get_data(as_text=True)
    assert "Share your link with another artist." in body
    # The offer is 50/50 (owner, 2026-09-18): half off their first month,
    # half off the referrer's next.
    assert "50% off their first month" in body and "50% off your next month" in body
    assert "Joined through your link" in body and "Now paying, half a month earned each" in body
    assert "How your 50% reaches you:" in body and "$9" not in body
    for gone in ("Give a month, get $9", "Converted · credits applied", "How it settles, honestly", "expiry games"):
        assert gone not in body, gone

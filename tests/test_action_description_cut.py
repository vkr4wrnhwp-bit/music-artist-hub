"""An action's description was cut mid-word at 600 characters.

Seen on the Action Center (2026-09-12): a coverage-gap action whose
store list ended "SoundExchange: Sirius XM Radio, Inc, Sound". A cut
happens at a word boundary now, and says it happened.
"""
import uuid

import command_center as cc
import db as store
from app import create_app


def _uid():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "cut-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "C", "email": email, "password": "cut-pass-12345"})
    with app_obj.app_context():
        return app_obj, store.get_user_by_email(email)["id"]


def test_a_long_description_is_cut_at_a_boundary_and_says_so():
    stores = ", ".join("Store %02d" % i for i in range(120))      # ~1,000 chars
    app_obj, uid = _uid()
    with app_obj.app_context():
        aid = cc.create_action(uid, "Verify delivery", description=stores)
        row = cc.get_action(uid, aid) if hasattr(cc, "get_action") else None
        if row is None:
            row = [a for a in cc.list_actions(uid) if a["id"] == aid][0]
    text = row["description"]
    assert len(text) <= 600
    assert text.endswith("…")
    body = text[:-2]
    assert body.endswith(tuple("0123456789")), "ends on a whole store name, not mid-word: %r" % body[-20:]


def test_a_short_description_is_left_alone():
    assert cc._cut("Deezer, Anghami", 600) == "Deezer, Anghami"

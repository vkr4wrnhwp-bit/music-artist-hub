"""One malformed row must not take the shared inbox down.

Found by walking every GET route during the dead-code sweep, not by
a user report - which is the argument for walking them.
"""

import json
import uuid

import db as store
from app import create_app


def _client(app_obj):
    client = app_obj.test_client()
    client.post("/signup", data={"name": "I",
                                 "email": "inbox%s@x.com" % uuid.uuid4().hex[:8],
                                 "password": "secret1", "account_type": "artist"})
    return client


def test_inbox_survives_a_double_encoded_payload():
    app_obj = create_app()
    client = _client(app_obj)
    with app_obj.app_context():
        # A row written already-encoded: json.loads gives back a string,
        # and the template calls .items() on it.
        store.add_inbox("demo-access", json.dumps({"email": "lead@test.io"}))
        store.add_inbox("booking_enquiry", {"name": "Real Dict"})
        items = store.get_inbox()
    assert all(isinstance(i["payload"], dict) for i in items)
    response = client.get("/inbox")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    # The bad row is shown, and it does not hide the good one.
    assert "lead@test.io" in text and "Real Dict" in text

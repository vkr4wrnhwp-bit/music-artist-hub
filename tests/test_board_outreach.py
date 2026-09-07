"""Network parked, outreach on the board.

The Network directory is sample profiles - not real people - so it is
parked with its code kept, like Capital and Benchmark. The one real thing
on that page, the outreach pitch tracker, moved to the Team-Up Board,
where real accounts already find each other. Same rows, same POST routes;
the forms say where to come back to, and anything else goes home.
"""
import uuid

import db as store
from app import create_app

PASSWORD = "board-pass-123"


def _artist(app_obj):
    email = "ob-%s@example.net" % uuid.uuid4().hex[:8]
    client = app_obj.test_client()
    client.post("/signup", data={"name": "Ava", "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    return client, store.get_user_by_email(email)


def test_the_board_has_an_outreach_page_and_links_to_it():
    app_obj = create_app()
    client, user = _artist(app_obj)
    board = client.get("/tour-board").get_data(as_text=True)
    assert 'href="/tour-board/outreach"' in board
    page = client.get("/tour-board/outreach").get_data(as_text=True)
    assert "Outreach Pipeline" in page and "real entries only" in page and "Nothing tracked yet" in page
    assert 'name="back" value="/tour-board/outreach"' in page


def test_adding_and_moving_a_pitch_comes_back_to_the_board():
    app_obj = create_app()
    client, user = _artist(app_obj)
    r = client.post("/network/outreach/add", data={"contact": "Midnight Radio", "role": "Curator",
                                                   "stage": "pitched", "notes": "sent smart link",
                                                   "back": "/tour-board/outreach"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/tour-board/outreach")
    page = client.get("/tour-board/outreach").get_data(as_text=True)
    assert "Midnight Radio" in page and "pitched · 1" in page
    item = store.list_outreach(user["id"])[0]
    r = client.post("/network/outreach/%s/stage" % item["id"], data={"stage": "discussion", "back": "/network?tab=my"})
    assert r.headers["Location"].endswith("/network?tab=my"), "the old page still works and returns to itself"
    r = client.post("/network/outreach/%s/delete" % item["id"], data={"back": "https://evil.example/"})
    assert r.headers["Location"].endswith("/tour-board/outreach"), "an unknown return goes home"
    assert store.list_outreach(user["id"]) == []


def test_the_network_page_is_parked_but_still_carries_the_tracker():
    app_obj = create_app()
    client, user = _artist(app_obj)
    page = client.get("/network?tab=my").get_data(as_text=True)
    assert "Parked." in page and "sample profiles" in page and "Team-Up Board" in page
    assert "Outreach Pipeline" in page and 'name="back" value="/network?tab=my"' in page
    # The inbox and the release desk now point at the board, not the directory.
    assert 'href="/network"' not in client.get("/inbox").get_data(as_text=True)

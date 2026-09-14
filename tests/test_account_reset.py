"""Start over: empty the account, keep the login.

Asked for on 2026-09-14 - the owner wanted their own login blank and a
demo account loaded with the label's statements, without making a new
account for either. The rules this file holds:

  * the confirmation is the account's own email typed back; a wrong
    address empties nothing
  * every row the account owns goes, INCLUDING the rows that only reach
    the account through a parent (statement rows, link clicks) and the
    rows keyed by a column that is not user_id (fan-club members)
  * the login, the plan and the drop-box address survive
  * fans paying the account through Stripe for its fan club refuse the
    wipe, so nobody keeps paying an account that has forgotten them
  * an owner may reset (it is deletion that refuses owners)
  * the table map the sweep uses matches the schema it runs against
"""
import io
import uuid

import pytest

import db as store
from app import create_app

PW = "start-over-12345"
CSV = ("Reporting Period,Artist,Track Title,ISRC Code,Digital Service Provider,Royalty\n"
       "JUN-26,Hungry Gods,Narrow,GBWUL2686921,Spotify,100.00\n"
       "JUN-26,Hungry Gods,Wide,GBWUL2686922,Deezer,40.00\n")


@pytest.fixture
def artist():
    app_obj = create_app()
    client = app_obj.test_client()
    email = "reset-%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": "Starting Over", "email": email, "password": PW})
    client.post("/plan/switch", data={"plan": "pro"})
    client.post("/statements",
                data={"statement": (io.BytesIO(CSV.encode()), "jun.csv")},
                content_type="multipart/form-data")
    client._app, client._email = app_obj, email
    with app_obj.app_context():
        uid = client._uid = store.get_user_by_email(email)["id"]
        store.notify(uid, "fan", "A fan", "", "/fans")
        store.save_gap_check(uid, "narrow", "GBWUL2686921", {"deezer": "absent"})
        store.create_recovery_case(uid, {"title": "Narrow on Deezer", "category": "coverage",
                                         "estimated_amount": "12.50"})
        slug = store.create_db_link("start-over-%s" % uuid.uuid4().hex[:6], uid,
                                    "Narrow", "https://example.net/narrow", ["spotify"])
        store.log_click(slug)
        with store.get_db() as db:
            db.execute("INSERT INTO club_members (id, artist_id, member_email, status, created)"
                       " VALUES (?,?,?,?,?)",
                       (uuid.uuid4().hex, uid, "fan@example.net", "active", "2026-09-14"))
    return client


def _count(client, sql, *args):
    with client._app.app_context(), store.get_db() as db:
        return db.execute(sql, args).fetchone()[0]


def _owned(client):
    """Rows under the account: the user_id sweep, the children, the
    extra-keyed tables. The users row itself is not counted."""
    uid = client._uid
    with client._app.app_context(), store.get_db() as db:
        out = {t: db.execute('SELECT COUNT(*) FROM "%s" WHERE "%s" = ?' % (t, k),
                             (uid,)).fetchone()[0]
               for t, k in store._tables_keyed_by_user(db)
               if t not in store.RESET_KEEPS}
        out["statement_rows"] = db.execute(
            "SELECT COUNT(*) FROM statement_rows WHERE statement_id IN"
            " (SELECT id FROM statements WHERE user_id = ?)", (uid,)).fetchone()[0]
        out["link_clicks"] = db.execute(
            "SELECT COUNT(*) FROM link_clicks WHERE slug IN"
            " (SELECT slug FROM smart_links WHERE user_id = ?)", (uid,)).fetchone()[0]
        out["club_members"] = db.execute(
            "SELECT COUNT(*) FROM club_members WHERE artist_id = ?", (uid,)).fetchone()[0]
    return out


def test_the_page_offers_it_above_deletion(artist):
    body = artist.get("/settings").get_data(as_text=True)
    assert 'id="start-over"' in body and "/account/reset" in body
    assert body.index('id="start-over"') < body.index('id="delete-account"')


def test_the_fixture_planted_rows_the_old_sweep_could_not_see(artist):
    before = _owned(artist)
    assert before["statements"] == 1 and before["statement_rows"] == 2
    assert before["link_clicks"] == 1 and before["club_members"] == 1
    assert before["gap_checks"] == 1 and before["recovery_cases"] == 1


def test_a_wrong_address_empties_nothing(artist):
    before = _owned(artist)
    r = artist.post("/account/reset", data={"confirm": "someone@else.net"})
    assert "reset=mismatch" in r.headers["Location"]
    assert _owned(artist) == before


def test_the_right_address_empties_everything_and_keeps_the_login(artist):
    r = artist.post("/account/reset", data={"confirm": artist._email.upper()})
    assert r.headers["Location"].endswith("/settings?reset=1#start-over")
    after = _owned(artist)
    assert all(n == 0 for n in after.values()), {t: n for t, n in after.items() if n}
    with artist._app.app_context():
        user = store.get_user_by_email(artist._email)
        assert user is not None and user["plan"] == "pro"
    assert artist.get("/settings").status_code == 200, "still signed in"
    fresh = artist._app.test_client()
    login = fresh.post("/login", data={"email": artist._email, "password": PW})
    assert login.status_code == 302 and "/login" not in login.headers["Location"]
    body = artist.get("/settings?reset=1").get_data(as_text=True)
    assert "This account is empty and still yours" in body
    assert artist.get("/royalties").status_code == 200


def test_fans_paying_through_stripe_refuse_the_wipe(artist):
    with artist._app.app_context(), store.get_db() as db:
        db.execute("UPDATE club_members SET stripe_subscription_id = 'sub_live' WHERE artist_id = ?",
                   (artist._uid,))
    before = _owned(artist)
    r = artist.post("/account/reset", data={"confirm": artist._email})
    assert "reset=fans" in r.headers["Location"]
    assert _owned(artist) == before
    body = artist.get("/settings?reset=fans").get_data(as_text=True)
    assert "Cancel those subscriptions first" in body


def test_an_owner_may_start_over(artist, monkeypatch):
    monkeypatch.setenv("OWNER_EMAILS", artist._email)
    r = artist.post("/account/reset", data={"confirm": artist._email})
    assert "reset=1" in r.headers["Location"]
    assert sum(_owned(artist).values()) == 0


def test_signed_out_it_is_a_login_redirect(artist):
    fresh = artist._app.test_client()
    r = fresh.post("/account/reset", data={"confirm": artist._email})
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_the_sweep_map_matches_the_schema(artist):
    """A wrong column name here would raise on the first real reset. Every
    (table, column) the sweep names must exist, and every table with a
    user column that is NOT kept must be reachable by the sweep."""
    with artist._app.app_context(), store.get_db() as db:
        def cols(table):
            return {r[1] for r in db.execute('PRAGMA table_info("%s")' % table).fetchall()}
        for child, ccol, parent, pcol, ucol in store.RESET_CHILDREN:
            assert ccol in cols(child), (child, ccol)
            assert pcol in cols(parent) and ucol in cols(parent), (parent, pcol, ucol)
        for child, ccol, parent, pcol, mid, grand, gcol, ucol in store.RESET_GRANDCHILDREN:
            assert ccol in cols(child), (child, ccol)
            assert pcol in cols(parent) and mid in cols(parent), (parent, pcol, mid)
            assert gcol in cols(grand) and ucol in cols(grand), (grand, gcol, ucol)
        for table, key in store.RESET_EXTRA_KEYS:
            assert key in cols(table), (table, key)
        for table in store.RESET_KEEPS:
            assert table in store._table_names(db), table


def test_deleting_an_account_takes_the_children_too(artist):
    """The delete sweep used to leave statement rows and click logs
    behind under parents that no longer existed."""
    r = artist.post("/account/delete", data={"confirm": artist._email})
    assert "deleted=1" in r.headers["Location"]
    after = _owned(artist)
    assert all(n == 0 for n in after.values()), {t: n for t, n in after.items() if n}

"""The money findings of the 2026-09-20 page walk, pinned.

Three could hurt a real account: a split sheet and a master served to
anyone with the address (after the doc_ fix had closed contracts), a
statement with a NaN cell that was a 500, and a recovery case whose
typed amount was a 500. The rest were figures that read wrong: a tax
banner about "one payor" over $600 when none had crossed it, an unsold
sync pack read as a lane that pays, a catalog card that said Not
measured beside a valuation that had a range, a "removed" notice for a
delete that removed nothing, and a Rights Conflict Center that found
nothing on every real account.
"""
import io
import json
import math
import os
import re
import uuid

import pytest

import app as appmod
import capital_engine
import catalog_value
import db as store
import qualification
import statements_desk
import statements_engine

PW = "walk-money-pw-1234"

# $697.40 across two periods; six payors, none of them at $600.
TWO_PERIODS = (
    "title,source,amount,period,isrc\n"
    "Hungry Gods,Spotify,300,2026-05,USX000000001\n"
    "Hungry Gods,YouTube Streaming,40,2026-05,USX000000001\n"
    "Hungry Gods,YouTube Content ID,30,2026-05,USX000000001\n"
    "Hungry Gods,YouTube Shorts,10,2026-05,USX000000001\n"
    "Hungry Gods,SoundExchange: Sirius XM,25,2026-05,USX000000001\n"
    "Hellhounds,Spotify,200,2026-06,USX000000002\n"
    "Hellhounds,Deezer,60,2026-06,USX000000002\n"
    "Hellhounds,YouTube Streaming,20,2026-06,USX000000002\n"
    ",Spotify,12.40,2026-06,\n"
)

# One payor alone over $600.
ONE_PAYOR_OVER = (
    "title,source,amount,period\n"
    "Hungry Gods,Spotify,850,2026-05\n"
    "Hungry Gods,Deezer,10,2026-05\n"
)


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.setenv("NAV_ROOMS", "1")


def _uploads_dir():
    d = os.path.join(os.path.dirname(store.db_path()), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _account(name="Walk Label", plan="label"):
    email = "money-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": name, "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


def _upload(c, csv=TWO_PERIODS, name="s.csv"):
    return c.post("/statements", data={"statement": (io.BytesIO(csv.encode()), name)},
                  content_type="multipart/form-data")


def _text(r):
    return r.get_data(as_text=True)


def _strip(html):
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass  # Windows keeps a served file open a moment; the dir is temporary


def _plant_upload(fname, body):
    path = os.path.join(_uploads_dir(), fname)
    with open(path, "wb") as fh:
        fh.write(body)
    return path


# --- BLOCKER: lockbox contracts are the account's -----------------------------

def _track(c, uid, title="Hungry Gods"):
    c.post("/tracks/add", data={"title": title})
    return next(t for t in store.list_os_tracks(uid) if t["title"] == title)


def test_a_lockbox_split_sheet_is_served_only_to_its_owner():
    owner, uid = _account()
    other, _uid2 = _account()
    track = _track(owner, uid)
    marker = b"%PDF-1.4 split sheet " + uuid.uuid4().hex.encode()
    r = owner.post("/tracks/%s/lockbox/split_sheet" % track["id"],
                   data={"action": "upload", "file": (io.BytesIO(marker), "split-sheet.pdf")},
                   content_type="multipart/form-data")
    assert r.status_code in (302, 303)
    path = store.get_os_track(uid, track["id"])["lockbox"]["split_sheet"]["file"]
    assert path.startswith("/uploads/")
    try:
        anon = appmod.app.test_client().get(path)
        assert anon.status_code in (302, 303) and "/login" in anon.headers["Location"]
        assert other.get(path).status_code == 404
        mine = owner.get(path)
        assert mine.status_code == 200 and mine.data == marker
        mine.close()
    finally:
        _remove(os.path.join(_uploads_dir(), path[len("/uploads/"):]))


def test_an_approver_reads_the_lockbox_contract_by_their_token():
    """The approver is not signed in; the sign page hands them the file
    through /sign/<token>/document, never the /uploads address."""
    owner, uid = _account()
    track = _track(owner, uid, "Hellhounds")
    marker = b"%PDF-1.4 producer agreement " + uuid.uuid4().hex.encode()
    owner.post("/tracks/%s/lockbox/producer_agreement" % track["id"],
               data={"action": "upload", "file": (io.BytesIO(marker), "producer.pdf")},
               content_type="multipart/form-data")
    owner.post("/tracks/%s/lockbox/producer_agreement" % track["id"],
               data={"action": "approver", "email": "producer@example.net", "name": "Prod"})
    path = store.get_os_track(uid, track["id"])["lockbox"]["producer_agreement"]["file"]
    with store.get_db() as db:
        token = db.execute("SELECT token FROM sign_tokens WHERE user_id = ? AND track_id = ?",
                           (uid, track["id"])).fetchone()["token"]
    try:
        anon = appmod.app.test_client()
        page = _text(anon.get("/sign/" + token))
        assert "/sign/%s/document" % token in page
        assert path not in page
        doc = anon.get("/sign/%s/document" % token)
        assert doc.status_code == 200 and doc.data == marker
        doc.close()
        assert anon.get("/sign/%s/document" % uuid.uuid4().hex).status_code == 404
    finally:
        _remove(os.path.join(_uploads_dir(), path[len("/uploads/"):]))


# --- BLOCKER: vault masters and stems are the account's ------------------------

def _vault_upload(c, kind, fname, body):
    r = c.post("/vault/upload", data={"kind": kind, "file": (io.BytesIO(body), fname)},
               content_type="multipart/form-data")
    assert r.status_code == 200, r.data
    return r.get_json()["path"]


def test_a_vault_master_is_served_only_to_its_owner():
    owner, _uid = _account()
    other, _uid2 = _account()
    marker = b"RIFF master " + uuid.uuid4().hex.encode()
    path = _vault_upload(owner, "master", "final.wav", marker)
    assert path.startswith("/uploads/vault_")
    try:
        anon = appmod.app.test_client().get(path)
        assert anon.status_code in (302, 303) and "/login" in anon.headers["Location"]
        assert other.get(path).status_code == 404
        mine = owner.get(path)
        assert mine.status_code == 200 and mine.data == marker
        mine.close()
    finally:
        _remove(os.path.join(_uploads_dir(), path[len("/uploads/"):]))


def test_vault_cover_art_and_a_shared_master_stay_public():
    """Cover art goes on public pages by design. A master the owner put
    on a one-sheet was sent out on purpose and keeps answering."""
    owner, uid = _account()
    art = _vault_upload(owner, "cover_art", "art.png", b"\x89PNG art")
    shared = _vault_upload(owner, "master", "single.wav", b"RIFF shared")
    with store.get_db() as db:
        db.execute("INSERT INTO onesheet_shares (user_id, token, audio, created)"
                   " VALUES (?,?,?,?)",
                   (uid, uuid.uuid4().hex, json.dumps([{"path": shared, "label": "Single"}]),
                    "2026-09-20T00:00:00"))
    try:
        anon = appmod.app.test_client()
        r = anon.get(art)
        assert r.status_code == 200
        r.close()
        r = anon.get(shared)
        assert r.status_code == 200
        r.close()
    finally:
        for p in (art, shared):
            _remove(os.path.join(_uploads_dir(), p[len("/uploads/"):]))


# --- BLOCKER: a NaN amount is a blank cell, not a 500 --------------------------

@pytest.mark.parametrize("cell", ["NaN", "nan", "inf", "-inf", "1e400"])
def test_a_non_finite_amount_is_a_blank_cell(cell):
    assert statements_engine._to_amount(cell) is None
    assert statements_engine._to_amount("$1,234.50") == 1234.5
    assert statements_engine._to_amount("(12.50)") == -12.5


def test_a_statement_with_a_nan_cell_uploads_the_other_rows():
    c, uid = _account()
    r = _upload(c, "title,source,amount\nA,Spotify,12.5\nZ,Spotify,NaN\n")
    assert r.status_code in (302, 303)
    rows = store.get_statement_rows(uid)
    assert [x["amount"] for x in rows] == [12.5]
    assert c.get("/statements").status_code == 200


def test_a_statement_of_only_nan_cells_is_an_ordinary_upload_error():
    c, uid = _account()
    r = _upload(c, "title,source,amount\nZ,Spotify,NaN\n")
    assert r.status_code == 200
    assert "No usable rows found." in _text(r)
    assert store.get_statements(uid) == []


def test_save_statement_refuses_a_non_finite_total():
    _c, uid = _account()
    with pytest.raises(ValueError, match="not a number"):
        store.save_statement(uid, "x.csv", [{"amount": float("nan"), "source": "Spotify"}])
    with pytest.raises(ValueError, match="not a number"):
        store.save_statement(uid, "x.csv", [{"amount": float("inf"), "source": "Spotify"}])
    assert store.get_statements(uid) == []


def test_an_ingest_that_hits_the_second_lock_reads_as_an_upload_error(monkeypatch):
    """The parser drops the cell; if a row still arrives non-finite the
    store's refusal is the page's normal error line, not a 500."""
    c, _uid = _account()
    real = statements_engine.parse_statement

    def poisoned(data, filename="statement.csv"):
        out = real(data, filename)
        for row in out["rows"]:
            row["amount"] = float("nan")
        return out
    monkeypatch.setattr(appmod, "parse_statement", poisoned)
    r = _upload(c, "title,source,amount\nA,Spotify,12.5\n")
    assert r.status_code == 200
    assert "An amount in this file is not a number." in _text(r)


# --- DEFECT: a stored inf does not take down the money pages -------------------

def test_the_helpers_read_a_stored_inf_as_nothing():
    inf = float("inf")
    assert catalog_value.band(inf) == {"low": 0, "mid": 0, "high": 0}
    assert capital_engine._pts(inf, 100, 20) == 0
    assert qualification._pts(inf, 100) == 0
    assert statements_desk._whole(inf) is None
    assert statements_desk._whole(12.4) == 12


def _plant_inf_statement(uid):
    """An upload from before the parser refused one, planted straight
    into the store the way such a row already sits on disk."""
    sid = uuid.uuid4().hex
    with store.get_db() as db:
        db.execute("INSERT INTO statements (id, user_id, filename, uploaded, row_count, total, via)"
                   " VALUES (?,?,?,?,?,?,?)",
                   (sid, uid, "old.csv", "2026-09-01T00:00:00", 1, float("inf"), "upload"))
        db.execute("INSERT INTO statement_rows (statement_id, title, source, amount, period,"
                   " territory, isrc, artist) VALUES (?,?,?,?,?,?,?,?)",
                   (sid, "Z", "Spotify", float("inf"), "2026-06", "", "", ""))
        assert math.isinf(db.execute("SELECT total FROM statements WHERE id = ?",
                                     (sid,)).fetchone()["total"])
    return sid


def test_a_stored_inf_reads_as_nothing():
    _c, uid = _account()
    sid = _plant_inf_statement(uid)
    assert [r["amount"] for r in store.get_statement_rows(uid)] == [0.0]
    assert [s["total"] for s in store.get_statements(uid) if s["id"] == sid] == [0.0]
    assert store._readable_amount(float("nan")) == 0.0
    assert store._readable_amount("") == 0.0
    assert store._readable_amount(12.4) == 12.4


def test_every_money_page_survives_a_stored_inf():
    c, uid = _account()
    _upload(c)
    sid = _plant_inf_statement(uid)
    for url in ("/statements", "/statements?view=tax", "/royalties", "/valuation",
                "/capital-score", "/funding", "/reports/executive", "/catalog",
                "/reports/catalog-valuation-report/download"):
        r = c.get(url)
        assert r.status_code == 200, (url, r.status_code)
        r.close()
    # The rest of the account's money is still right beside it, and the
    # delete button on the bad statement is reachable.
    body = _text(c.get("/statements"))
    assert "697.40" in _strip(body)
    assert "/statements/%s/delete" % sid in body
    assert c.post("/statements/%s/delete" % sid).status_code in (302, 303)


# --- DEFECT: a recovery case amount is parsed, not crashed on -----------------

@pytest.mark.parametrize("raw, expected", [
    ("$10", 10.0), ("1,000", 1000.0), ("10 USD", 0.0), ("abc", 0.0),
    ("nan", 0.0), ("inf", 0.0), ("(12.50)", -12.5), ("", 0.0)])
def test_a_typed_case_amount_parses_like_a_statement_cell(raw, expected):
    assert store._money(raw) == expected


def test_a_recovery_case_with_a_dollar_sign_opens():
    c, uid = _account()
    r = c.post("/royalty-recovery/cases",
               data={"title": "C", "category": "coverage_gap", "estimated_amount": "$10"})
    assert r.status_code in (302, 303)
    cases = store.list_recovery_cases(uid)
    assert len(cases) == 1 and cases[0]["estimated_amount"] == 10.0
    for raw in ("1,000", "10 USD", "abc", "nan"):
        r = c.post("/royalty-recovery/cases",
                   data={"title": "Case " + raw, "category": "other", "estimated_amount": raw})
        assert r.status_code in (302, 303), raw
    amounts = {x["title"]: x["estimated_amount"] for x in store.list_recovery_cases(uid)}
    assert amounts["Case 1,000"] == 1000.0
    assert amounts["Case 10 USD"] == 0.0
    assert amounts["Case abc"] == 0.0
    assert amounts["Case nan"] == 0.0


def test_a_case_from_a_finding_with_a_bad_amount_opens_at_zero():
    c, uid = _account()
    for raw in ("abc", "$10", "nan"):
        r = c.post("/royalty-recovery/cases/from-finding",
                   data={"case_key": "walk:" + raw, "title": "Finding " + raw,
                         "category": "unmatched", "amount": raw})
        assert r.status_code in (302, 303), raw
    amounts = {x["title"]: x["estimated_amount"] for x in store.list_recovery_cases(uid)}
    assert amounts == {"Finding abc": 0.0, "Finding $10": 10.0, "Finding nan": 0.0}


# --- DEFECT: "removed" only when something was removed ------------------------

def test_deleting_another_accounts_statement_is_a_404_not_a_removed_notice():
    a, uid_a = _account()
    b, _uid_b = _account()
    _upload(a)
    sid = store.get_statements(uid_a)[0]["id"]
    assert store.delete_statement(_uid_b, sid) == 0
    r = b.post("/statements/%s/delete" % sid)
    assert r.status_code == 404
    assert len(store.get_statements(uid_a)) == 1
    r = b.post("/statements/%s/delete" % uuid.uuid4().hex)
    assert r.status_code == 404
    r = a.post("/statements/%s/delete" % sid)
    assert r.status_code in (302, 303) and r.headers["Location"].endswith("/statements?removed=1")
    assert store.get_statements(uid_a) == []


def test_delete_statement_reports_how_many_went():
    _c, uid = _account()
    sid = store.save_statement(uid, "x.csv", [{"amount": 1.0, "source": "Spotify"}])
    assert store.delete_statement(uid, sid) == 1
    assert store.delete_statement(uid, sid) == 0


# --- DEFECT: the $600 mark is per payor --------------------------------------

def test_the_tax_banner_names_the_payors_that_crossed_600():
    c, _uid = _account()
    _upload(c)
    page = _strip(_text(c.get("/statements?view=tax")))
    assert "697.40" in page
    assert "Over $600" not in page, "six payors under $600 each are not one payor over it"
    c2, _uid2 = _account()
    _upload(c2, ONE_PAYOR_OVER)
    page = _strip(_text(c2.get("/statements?view=tax")))
    assert "Over $600 from Spotify:" in page
    assert "Deezer:" not in page.split("Over $600 from")[1].split("expect")[0]


# --- DEFECT: a lane set up but silent is not a lane that pays ------------------

def test_an_unsold_sync_pack_is_set_up_not_paying():
    c, uid = _account()
    _upload(c)
    _track(c, uid, "Hungry Gods")
    _track(c, uid, "Hellhounds")
    before = _strip(_text(c.get("/royalties")))
    count = re.search(r"(\d+) of 9 lanes show money", before)
    assert count, before[:400]
    assert "are paying." in before
    assert "Sync licensing" not in before.split("are paying.")[0].rsplit(".", 1)[-1]
    r = c.post("/sync/clearance-packs",
               data={"title": "Hungry Gods", "main_audio": (io.BytesIO(b"ID3 sync"), "main.mp3")},
               content_type="multipart/form-data")
    assert r.status_code in (302, 303)
    after = _strip(_text(c.get("/royalties")))
    assert re.search(r"(\d+) of 9 lanes show money", after).group(1) == count.group(1)
    assert "Sync licensing is set up, no income yet." in after
    assert "Sync licensing are paying" not in after and "Sync licensing is paying" not in after


def test_the_lane_note_counts_and_conjugates():
    import royalties_desk
    tracks = [{"id": "t", "title": "Hungry Gods"}]
    assert royalties_desk._lane_note([], {"master"}, set()).startswith("No Track Passports yet")
    assert royalties_desk._lane_note(tracks, set(), set()) == "No lane shows money yet."
    one = royalties_desk._lane_note(tracks, {"master"}, {"sync"})
    assert "is paying." in one and "Sync licensing is set up, no income yet." in one
    many = royalties_desk._lane_note(tracks, {"master", "neighboring"}, set())
    assert "are paying." in many


# --- DEFECT: the catalog card reads the same estimate as the valuation ---------

def test_the_catalog_card_shows_the_valuation_estimate():
    c, uid = _account()
    card = _strip(_text(c.get("/catalog")))
    assert "Not measured" in card
    _upload(c)
    mid = catalog_value.band(statements_engine.annualize(
        store.get_statement_rows(uid))["annualized"])["mid"]
    assert mid > 0
    card = _strip(_text(c.get("/catalog")))
    assert "${:,.0f}".format(mid) in card
    assert "Catalog Value (Estimated) Not measured" not in card
    valuation = _strip(_text(c.get("/valuation")))
    assert "{:,.0f}".format(mid) in valuation
    assert "vs last month" not in card, "no month-by-month value is recorded, so none is drawn"


# --- DEFECT: the Rights Conflict Center is retired into the money queue -------

def test_conflicts_computes_from_the_accounts_own_passports(client_factory=None):
    """Owner, 2026-09-20: "I would like to get it to compute." The page
    was going to be retired into the money queue; the owner ruled instead
    that it should read the account's own passports. Pinned properly in
    tests/test_rights_conflicts.py; this only holds the address open."""
    import app as _app
    rules = {r.rule for r in _app.app.url_map.iter_rules()}
    assert "/conflicts" in rules

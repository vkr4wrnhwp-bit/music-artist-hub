"""The Recovery desk, approved from the numbered mockup of 2026-09-13.

Three bases stood side by side and never added into one headline; a
findings ledger grouped by basis with a store strip per gap; a case
edited in a strip in the page's own flow; The MLC's works as claim
meters; the actual part of a mixed bar in its own tone.
"""
import io
import uuid

import pytest

import recovery_desk as desk


# --- the builder ----------------------------------------------------------

def test_the_three_bases_stand_side_by_side_and_a_zero_is_dashed_not_hidden():
    rv = {"actual_unattributed": 0.0, "estimated_gaps": 26.56, "_unattributed_rows": 0}
    cols = desk.stake(rv, {"amount": 412.30, "works": 2, "checked": "2026-09-12"}, 15)
    by = {c["key"]: c for c in cols}
    assert by["actual"]["state"] == "zero" and by["actual"]["shown"] == "$0.00"
    assert by["estimate"]["state"] == "value" and by["estimate"]["est"] is True
    assert by["registry"]["height"] == 100 and by["estimate"]["height"] == 6, "shares of the largest"
    assert by["estimate"]["sub"] == "15 tracks" and by["registry"]["sub"] == "2 works"


def test_no_sweep_is_not_checked_not_zero():
    rv = {"actual_unattributed": 5.0, "estimated_gaps": 0.0, "_unattributed_rows": 1}
    by = {c["key"]: c for c in desk.stake(rv, None, 0)}
    assert by["registry"]["state"] == "unchecked" and by["registry"]["shown"] == "—"
    assert by["registry"]["sub"] == "no check run yet"
    assert by["actual"]["state"] == "value" and by["actual"]["height"] == 100


def test_gaps_checked_counts_one_cell_per_gap():
    gaps = [{"title": "Hungry Gods"}, {"title": "Black Rifle"}, {"title": "Vendettas"}]
    out = desk.checked(gaps, {"hungry-gods": {"checked": "2026-09-13"}})
    assert out["n"] == 1 and out["of"] == 3 and out["cells"] == [True, False, False]
    assert out["note"].startswith("2 gaps not asked yet")
    assert desk.checked([], {})["note"] == "No gaps to ask about."


def test_the_rail_lights_only_as_far_as_the_record_goes():
    opened = desk.rail({"status": "open"})
    assert [s["on"] for s in opened] == [True, False, False, False] and opened[0]["now"]
    sent = desk.rail({"status": "submitted", "evidence_at": "2026-09-13T10:00:00"})
    assert [s["on"] for s in sent] == [True, True, False, False] and sent[1]["now"]
    won = desk.rail({"status": "won"})
    assert all(s["on"] for s in won) and won[3]["now"]


def test_a_gap_row_folds_its_stores_into_a_strip_and_counts_them_in_words():
    card = {"chips": [{"state": "carried"}, {"state": "carried"}, {"state": "absent"},
                      {"state": "unchecked"}], "checked": "2026-09-13", "has_case": False}
    (row,) = desk.gap_rows([card])
    assert row["strip"] == ["carried", "carried", "absent", "unchecked"]
    assert [t for t, _ in row["caption"]] == ["carried", "absent", "unchecked"]
    assert row["caption"][0][1] == "2 carry it, paid nothing" and row["caption"][2][1] == "1 not asked"
    assert row["lamp"] == "Carried, unpaid" and row["step"] == "letter"
    (unasked,) = desk.gap_rows([{"chips": [{"state": "unchecked"}], "checked": "", "has_case": False}])
    assert unasked["lamp"] == "Not checked" and unasked["step"] == "check"


def test_registry_rows_draw_claim_meters_and_sum_what_is_at_risk():
    mlc = {"latest": {"created": "2026-09-12T14:02:00", "rows": [
        {"isrc": "A", "result": "match", "share_total": 100.0, "gap": False},
        {"isrc": "B", "result": "match", "share_total": 60.0, "gap": True, "case_amount": 174.19},
        {"isrc": "C", "result": "none", "gap": True, "case_amount": 238.11},
        {"isrc": "D", "result": "error", "gap": False}]}}
    rows = desk.registry_rows(mlc)
    by = {r["isrc"]: r for r in rows["all"]}
    assert by["A"]["meter"] == "full" and by["B"]["meter"] == "partial" and by["B"]["claimed_pct"] == 60.0
    assert by["C"]["meter"] == "none" and by["D"]["meter"] == "error"
    assert [r["isrc"] for r in rows["gaps"]] == ["B", "C"] and [r["isrc"] for r in rows["claimed"]] == ["A"]
    risk = desk.registry_at_risk(mlc)
    assert risk == {"amount": 412.3, "works": 2, "checked": "2026-09-12"}
    assert desk.registry_at_risk({"latest": None}) is None, "no sweep is not zero"


# --- the page -----------------------------------------------------------

CSV = ("title,source,amount,period,isrc\n"
       "Hungry Gods,Spotify,300,2026-05,USX000000001\n"
       "Hungry Gods,YouTube,80,2026-05,USX000000001\n"
       "Hellhounds,Spotify,200,2026-06,USX000000002\n"
       "Hellhounds,Deezer,60,2026-06,USX000000002\n"
       "Hellhounds,YouTube,20,2026-06,USX000000002\n"
       ",Spotify,12.40,2026-06,\n")


@pytest.fixture
def artist():
    import db as store
    from app import create_app
    app_obj = create_app()
    client = app_obj.test_client()
    email = "rdesk-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Desk", "email": email, "password": "desk-pass-12345"})
    client.post("/plan/switch", data={"plan": "pro"})
    with app_obj.app_context():
        client.uid = store.get_user_by_email(email)["id"]
    client.app_obj = app_obj
    return client


def _upload(client, csv=CSV):
    r = client.post("/statements", data={"statement": (io.BytesIO(csv.encode()), "s.csv")},
                    content_type="multipart/form-data")
    assert r.status_code == 302


def test_the_page_stands_the_bases_up_and_groups_the_ledger(artist):
    _upload(artist)
    body = artist.get("/recovery").get_data(as_text=True)
    assert "1 statement" in body and "6 statement rows" in body and "May 2026 – Jun 2026" in body
    assert "Stores not asked yet" in body
    assert 'data-instrument="stake"' in body and 'data-basis="actual"' in body
    assert '<div class="bar value"><i class="actual"' in body, "the $12.40 stands up in the actual tone"
    assert 'data-instrument="checked"' in body and "0<span" in body and " of 1</span>" in body
    assert 'data-finding="gap-hungry-gods"' in body and "silent on 1" in body
    assert '<i class="unchecked"></i>' in body and "1 not asked" in body
    assert 'href="/statements#gap-hungry-gods"' in body, "which stores jumps to the chips"
    assert "Unclaimed" in body and 'name="case_key" value="recovery:unattributed:spotify"' in body
    assert "Create recovery action" not in body, "a case is the action"
    assert "None" not in body.replace("NoneType", "")


def test_a_case_opened_from_a_row_returns_to_recovery_with_the_strip_open(artist):
    _upload(artist)
    body = artist.get("/recovery").get_data(as_text=True)
    form = body.split('data-finding="gap-hungry-gods"')[1].split("</form>")[-2]
    fields = dict(__import__("re").findall(r'name="(\w+)" value="([^"]*)"', form))
    assert fields["next"] == "/recovery"
    r = artist.post("/royalty-recovery/cases/from-finding", data=fields)
    assert r.status_code == 302 and r.headers["Location"].startswith("/recovery?opened=opened&case=")
    body = artist.get(r.headers["Location"].split("#")[0]).get_data(as_text=True)
    assert 'id="case-strip"' in body and "Coverage gap: Hungry Gods" in body
    assert 'class="rv-row is-open"' in body, "the row the strip belongs to is lit"
    assert 'name="status"' in body and 'value="won"' not in body, "no outcome before anything was sent"
    assert "Mark the letter sent" in body and "Draft the letter" in body


def test_saving_the_strip_edits_the_estimate_and_deadline_and_stays_on_recovery(artist):
    import db as store
    _upload(artist)
    artist.post("/royalty-recovery/cases", data={"title": "Coverage gap: Hungry Gods",
                                                  "category": "coverage_gap", "estimated_amount": "9"})
    with artist.app_obj.app_context():
        case = store.list_recovery_cases(artist.uid)[0]
    r = artist.post("/royalty-recovery/cases", data={
        "case_id": case["id"], "status": "open", "estimated_amount": "13.99",
        "deadline": "2026-10-01", "notes": "asked Symphonic",
        "next": "/recovery?case=%s#case-strip" % case["id"]})
    assert r.headers["Location"].endswith("/recovery?case=%s#case-strip" % case["id"])
    with artist.app_obj.app_context():
        after = store.get_recovery_case(artist.uid, case["id"])
    assert after["estimated_amount"] == 13.99 and after["deadline"] == "2026-10-01"
    assert after["notes"] == "asked Symphonic"
    body = artist.get("/recovery?case=%s" % case["id"]).get_data(as_text=True)
    assert 'value="13.99"' in body and 'value="2026-10-01"' in body


def test_marking_the_letter_sent_from_the_strip_lights_the_rail(artist):
    import db as store
    _upload(artist)
    artist.post("/royalty-recovery/cases", data={"title": "Coverage gap: Hungry Gods",
                                                  "category": "coverage_gap", "estimated_amount": "9"})
    with artist.app_obj.app_context():
        case = store.list_recovery_cases(artist.uid)[0]
    r = artist.post("/royalty-recovery/cases/%s/sent" % case["id"],
                    data={"to": "Symphonic", "next": "/recovery?case=%s#case-strip" % case["id"]})
    assert r.headers["Location"].endswith("#case-strip")
    body = artist.get("/recovery?case=%s" % case["id"]).get_data(as_text=True)
    assert "Letter sent to Symphonic" in body and 'value="won"' in body, "an outcome opens up"
    assert '<span class="on now"><i></i>Sent</span>' in body


def test_a_return_path_off_site_is_refused(artist):
    _upload(artist)
    r = artist.post("/royalty-recovery/cases", data={"title": "X", "category": "other",
                                                      "estimated_amount": "1",
                                                      "next": "https://evil.example/x"})
    assert r.headers["Location"].endswith("/royalty-recovery/cases")


def test_the_store_check_pressed_on_recovery_returns_to_recovery(artist, monkeypatch):
    import coverage_check
    _upload(artist)
    monkeypatch.setattr(coverage_check, "check_gap", lambda isrc, missing: {
        "ok": True, "why": "", "absent": [], "unchecked": [],
        "carried": [{"source": "Deezer", "url": "https://www.deezer.com/track/1"}]})
    r = artist.post("/statements/gaps/check", data={"title": "Hungry Gods", "next": "/recovery#findings"})
    assert r.headers["Location"] == "/recovery?checked=hungry-gods#findings"
    body = artist.get("/recovery").get_data(as_text=True)
    assert '<i class="carried"></i>' in body and "1 carries it, paid nothing" in body
    assert "Carried, unpaid" in body and "Stores last asked" in body
    assert "1<span" in body and " of 1</span>" in body, "the gaps-checked instrument counts it"


def test_where_it_sits_draws_the_actual_part_in_its_own_tone(artist):
    _upload(artist)
    body = artist.get("/recovery").get_data(as_text=True)
    assert 'class="sb-meter-part"' in body, "the $12.40 on Spotify is actual"
    assert "draws green: money on the statement" in body


def test_the_case_desk_opens_the_strip_instead_of_a_form_panel(artist):
    body = artist.get("/royalty-recovery/cases").get_data(as_text=True)
    assert 'href="/royalty-recovery/cases?new=1#case-strip"' in body and 'id="case-strip"' not in body
    body = artist.get("/royalty-recovery/cases?new=1").get_data(as_text=True)
    assert 'id="case-strip"' in body and 'name="title"' in body and "Open case" in body
    r = artist.post("/royalty-recovery/cases", data={"title": "Content ID claim", "category": "content_id",
                                                      "estimated_amount": "85", "next": "/royalty-recovery/cases"})
    assert r.headers["Location"].endswith("/royalty-recovery/cases")
    body = artist.get("/royalty-recovery/cases").get_data(as_text=True)
    assert "Content ID claim" in body and "Edit ▸" in body

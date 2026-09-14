"""The Statements desk, approved from the numbered mockup of 2026-09-13.

Four readings each tagged with what they are; stores with their payee
lines folded under them and societies marked as not a store; tracks
that carry their coverage; gaps whose silent stores are chips in three
states, read from a check the artist ran - never asserted.
"""
import io
import uuid

import pytest

import statements_desk as desk
import statements_engine as se


def _analysis(csv):
    parsed = se.parse_statement(csv)
    assert parsed["error"] is None, parsed["error"]
    return se.analyze(parsed["rows"]), parsed["rows"]


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


def test_the_ladder_folds_payee_lines_under_their_store_and_marks_societies():
    a, _ = _analysis(TWO_PERIODS)
    ladder = desk.ladder(a)
    by = {r["store"]: r for r in ladder["rows"]}
    assert by["YouTube"]["line_count"] == 3 and by["YouTube"]["amount"] == 100.0
    assert by["YouTube"]["line_names"] == ["Content ID", "Shorts", "Streaming"]
    assert by["Spotify"]["line_count"] == 1 and by["Spotify"]["line_names"] == []
    assert by["SoundExchange"]["deliverable"] is False, "a society is not a store"
    assert ladder["rows"][0]["store"] == "Spotify" and ladder["top"] == 512.4
    assert ladder["society_count"] == 1
    assert "paid" in ladder["top3_note"] and "%" in ladder["top3_note"]


def test_the_ladder_folds_a_long_tail_and_adds_it_up():
    csv = "title,source,amount\n" + "".join(
        "T,Store %02d,%d\n" % (i, 100 - i) for i in range(14))
    a, _ = _analysis(csv)
    ladder = desk.ladder(a, limit=11)
    assert len(ladder["rows"]) == 11 and len(ladder["tail"]) == 3
    assert ladder["tail_amount"] == (89 + 88 + 87)


def test_the_four_readings_carry_their_tags_and_the_movement_between_periods():
    a, rows = _analysis(TWO_PERIODS)
    d = desk.build(a, rows, [{"filename": "a.csv", "via": "upload"}], [], {}, [])
    by = {i["key"]: i for i in d["instruments"]}
    assert by["earnings"]["tag"] == "actual" and by["earnings"]["shown"] == "$697.40"
    assert by["earnings"]["spark"] is not None, "two periods draw a line"
    assert by["earnings"]["delta_text"].startswith("-") and "Jun 2026 vs May 2026" in by["earnings"]["delta_text"]
    assert by["earnings"]["spark_first"].startswith("May 2026") and by["earnings"]["spark_last"].startswith("Jun 2026")
    assert by["stores"]["tag"] == "derived" and by["stores"]["shown"] == "4"
    assert by["stores"]["delta_text"] == "across 6 payee lines"
    assert by["gaps"]["tag"] == "estimate" and by["gaps"]["est"] is True
    assert by["gaps"]["prov"][0].endswith("% of reported")
    assert by["unmatched"]["tag"] == "actual" and by["unmatched"]["shown"] == "$12.40"
    assert by["unmatched"]["delta_text"] == "1 row"


def test_one_period_is_not_a_line_and_says_so():
    a, rows = _analysis("title,source,amount,period\nA,Spotify,10,2026-05\nB,Deezer,5,2026-05\n")
    d = desk.build(a, rows, [], [], {}, [])
    e = d["instruments"][0]
    assert e["spark"] is None and e["delta_text"] == "one period: May 2026"
    assert "second one draws the line" in e["note"]


def test_a_clean_catalogue_reads_nothing_to_chase_not_zero_dollars_of_gap():
    a, rows = _analysis("title,source,amount\nA,Spotify,10\nA,Deezer,5\n")
    d = desk.build(a, rows, [], [], {}, [])
    gaps = d["instruments"][2]
    assert gaps["est"] is False and gaps["prov"] == ["Nothing to chase here"]
    assert d["gaps"]["count"] == 0


def test_tracks_carry_their_coverage_and_their_gap():
    a, rows = _analysis(TWO_PERIODS)
    d = desk.build(a, rows, [], [], {}, [])
    by = {t["title"]: t for t in d["tracks"]}
    assert by["Hungry Gods"]["of"] == 4 and by["Hungry Gods"]["stores"] == 3
    assert by["Hungry Gods"]["dots"].count(True) == 8, "3 of 4 lit, rounded onto ten dots"
    assert by["Hungry Gods"]["gap"] is not None and by["Hungry Gods"]["slug"] == "hungry-gods"
    assert by["Hellhounds"]["gap"] is None and by["Hellhounds"]["slug"] == ""
    assert by["(no title)"]["untitled"] is True


def _findings(a, rows):
    import recovery_engine
    return recovery_engine.build(None, rows=rows, analysis=a)["findings"]


def test_an_unchecked_gap_keeps_every_store_dashed_and_says_who_can_be_asked():
    a, rows = _analysis(TWO_PERIODS)
    cards = desk.gap_cards(_findings(a, rows), a, {}, [], {"Hungry Gods": "USX000000001"})
    g = cards["featured"][0]
    assert g["title"] == "Hungry Gods" and g["isrc"] == "USX000000001"
    assert {c["state"] for c in g["chips"]} == {"unchecked"}
    assert g["check_note"].startswith("Not checked yet. Deezer answers by ISRC")
    assert g["letter_href"] == "" and g["has_case"] is False


def test_a_gap_with_no_isrc_cannot_be_checked_and_says_so():
    a, rows = _analysis(TWO_PERIODS)
    cards = desk.gap_cards(_findings(a, rows), a, {}, [], {})
    g = cards["featured"][0]
    assert g["isrc"] == "" and "No ISRC" in g["check_note"]


def test_a_stored_check_sorts_the_chips_and_dates_the_note():
    a, rows = _analysis(TWO_PERIODS)
    checks = {"hungry-gods": {
        "isrc": "USX000000001", "checked": "2026-09-12T10:00:00+00:00",
        "result": {"ok": True, "why": "",
                   "carried": [{"source": "Deezer", "url": "https://www.deezer.com/track/1"}],
                   "absent": [], "unchecked": []}}}
    cases = [{"id": "c1", "finding_key": "recovery:coverage_gap:hungry-gods", "closed_at": None}]
    cards = desk.gap_cards(_findings(a, rows), a, checks, cases, {"Hungry Gods": "USX000000001"})
    g = cards["featured"][0]
    chip = {c["source"]: c for c in g["chips"]}["Deezer"]
    assert chip["state"] == "carried" and chip["url"].startswith("https://www.deezer.com/")
    assert g["checked"] == "2026-09-12"
    assert g["check_note"] == "Checked 2026-09-12. Deezer answered by ISRC; the rest could not be asked."
    assert g["letter_href"] == "/royalty-recovery/cases/c1/letter" and g["has_case"] is True


def test_the_long_tail_is_folded_and_the_under_a_dollar_claim_is_only_made_when_true():
    csv = "title,source,amount\n" + "Big,Spotify,1000\nBig,Deezer,500\n" + "".join(
        "Small %d,Spotify,0.5\n" % i for i in range(5))
    a, rows = _analysis(csv)
    cards = desk.gap_cards(_findings(a, rows), a, {}, [], {})
    assert len(cards["featured"]) == 2 and len(cards["tail"]) == 3
    assert cards["tail_under_floor"] is True


# --- the page -----------------------------------------------------------

@pytest.fixture
def artist():
    from app import create_app
    app_obj = create_app()
    client = app_obj.test_client()
    email = "desk-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Desk", "email": email, "password": "desk-pass-12345"})
    client.post("/plan/switch", data={"plan": "pro"})
    client.email = email
    return client


def _drop_box(monkeypatch):
    """A configured inbound address, so the drop-box panel renders."""
    import email_provider as emailer
    monkeypatch.setattr(emailer, "inbound_configured", lambda: True)
    monkeypatch.setattr(emailer, "inbound_address", lambda token: "sb-%s@inbound-t.resend.app" % token)


def _upload(client, csv, name="s.csv"):
    r = client.post("/statements", data={"statement": (io.BytesIO(csv.encode()), name)},
                    content_type="multipart/form-data")
    assert r.status_code == 302, r.status_code


def test_the_page_draws_the_desk_from_the_rows(artist, monkeypatch):
    _drop_box(monkeypatch)
    _upload(artist, TWO_PERIODS)
    body = artist.get("/statements").get_data(as_text=True)
    assert 'data-instrument="earnings"' in body and '<span class="sbm-v">$697.40</span>' in body
    assert 'class="sd-tag estimate"' in body and 'class="sd-tag actual"' in body
    assert 'data-store="YouTube"' in body and "3 lines" in body and "Content ID, Shorts, Streaming" in body
    assert "licensing, not a store" in body
    assert "3 of 4" in body and 'href="#gap-hungry-gods"' in body
    assert 'id="gap-hungry-gods"' in body and 'class="sd-st unchecked">Deezer</span>' in body
    assert "Not checked yet. Deezer answers by ISRC" in body
    assert "Check the stores" in body and "Create a recovery case" in body
    assert "Last received: nothing yet" in body
    assert "None" not in body.replace("NoneType", "")


def test_checking_a_gap_keeps_the_answer_and_the_page_reads_it(artist, monkeypatch):
    import coverage_check
    _upload(artist, "title,source,amount,isrc\n"
                    "Wide,Spotify,100,USX000000009\nWide,Deezer,50,USX000000009\n"
                    "Wide,YouTube,20,USX000000009\nNarrow,Spotify,20,USX000000010\n")
    asked = {}

    def fake_check(isrc, missing):
        asked["isrc"], asked["missing"] = isrc, list(missing)
        return {"ok": True, "why": "", "absent": ["YouTube"], "unchecked": [],
                "carried": [{"source": "Deezer", "url": "https://www.deezer.com/track/9"}]}
    monkeypatch.setattr(coverage_check, "check_gap", fake_check)
    r = artist.post("/statements/gaps/check", data={"title": "Narrow"})
    assert r.status_code == 302 and r.headers["Location"].endswith("?checked=narrow#gap-narrow")
    assert asked["isrc"] == "USX000000010" and asked["missing"] == ["Deezer", "YouTube"]
    body = artist.get("/statements?checked=narrow").get_data(as_text=True)
    assert 'class="sd-st carried" href="https://www.deezer.com/track/9"' in body
    assert 'class="sd-st absent">YouTube · not listed</span>' in body
    assert "Check the stores again" in body and "Stores checked." in body


def test_a_gap_without_an_isrc_is_not_checked_by_title(artist, monkeypatch):
    import coverage_check
    _upload(artist, "title,source,amount\nA,Spotify,100\nA,Deezer,50\nB,Spotify,20\n")
    monkeypatch.setattr(coverage_check, "check_gap",
                        lambda *a, **k: pytest.fail("checked a track with no ISRC"))
    r = artist.post("/statements/gaps/check", data={"title": "B"})
    assert r.status_code == 302 and "checked=no-isrc" in r.headers["Location"]
    body = artist.get("/statements?checked=no-isrc").get_data(as_text=True)
    assert "carry no ISRC" in body and "Check the stores" not in body


def test_a_track_that_is_not_a_gap_cannot_be_checked(artist):
    _upload(artist, TWO_PERIODS)
    assert artist.post("/statements/gaps/check", data={"title": "Hellhounds"}).status_code == 404


def test_the_letter_reads_the_stored_check(artist, monkeypatch):
    import coverage_check
    _upload(artist, TWO_PERIODS)
    monkeypatch.setattr(coverage_check, "check_gap", lambda isrc, missing: {
        "ok": True, "why": "", "absent": [], "unchecked": ["YouTube"],
        "carried": [{"source": "Deezer", "url": "https://www.deezer.com/track/9"}]})
    artist.post("/statements/gaps/check", data={"title": "Hungry Gods"})
    body = artist.get("/statements").get_data(as_text=True)
    form = body.split('action="/royalty-recovery/cases/from-finding"')[1].split("</form>")[0]
    fields = dict(__import__("re").findall(r'name="(\w+)" value="([^"]*)"', form))
    artist.post("/royalty-recovery/cases/from-finding", data=fields)
    body = artist.get("/statements").get_data(as_text=True)
    assert "Draft the letter" in body
    href = body.split('class="sb-btn sb-btn-primary sb-btn-sm" href="')[1].split('"')[0]
    letter = artist.get(href).get_data(as_text=True)
    assert "listed on Deezer" in letter or "live on Deezer" in letter, "the letter says what the store said"


def test_a_statement_that_arrived_by_email_is_the_last_received(artist, monkeypatch):
    import db as store
    _drop_box(monkeypatch)
    _upload(artist, TWO_PERIODS)
    body = artist.get("/statements").get_data(as_text=True)
    assert "Last received: nothing yet" in body
    # the drop-box path records where the file came from
    email_uid = store.get_user_by_email(artist.email)["id"]
    store.save_statement(email_uid, "forwarded.csv",
                         [{"title": "X", "source": "Spotify", "amount": 1.0, "period": "2026-07"}],
                         via="email")
    body = artist.get("/statements").get_data(as_text=True)
    assert "Last received: nothing yet" not in body
    assert "forwarded.csv" in body and "drop-box" in body


def test_the_header_has_no_photograph_and_one_upload_control(artist, monkeypatch):
    """Two "Upload a statement" doors sat a hand-span apart (plate button
    and the intake form under it) and the stock photograph is being
    replaced (owner, 2026-09-14). One form, no image, the band stays."""
    _drop_box(monkeypatch)
    body = artist.get("/statements").get_data(as_text=True)
    assert 'class="sb-plate"' in body and 'class="sb-plate-img"' not in body
    assert body.count('name="statement"') == 1
    assert 'href="#intake"' not in body


# --- the roster ---------------------------------------------------------

ROSTER_ = ("Reporting Period,Artist,Track Title,Digital Service Provider,Territory,Royalty ($US)\n"
          "MAY-26,Hungry Gods,Narrow,Spotify,US,300\n"
          "MAY-26,Hellhounds,Howl,Spotify,GB,100\n"
          "JUN-26,Hungry Gods,Narrow,Spotify,US,330\n"
          "JUN-26,Hungry Gods,Wide,Deezer,US,70\n"
          "JUN-26,Hellhounds,Howl,Spotify,GB,120\n")


def test_a_label_export_offers_the_roster_on_statements_too(artist, monkeypatch):
    _drop_box(monkeypatch)
    _upload(artist, ROSTER_)
    body = artist.get("/statements").get_data(as_text=True)
    assert 'id="statements-artist"' in body and "2 artists in the statements on file" in body
    assert "Wide" in body and "Howl" in body
    one = artist.get("/statements?artist=Hellhounds").get_data(as_text=True)
    assert '<option value="Hellhounds" selected>' in one and "Reading Hellhounds only" in one
    assert "Howl" in one and "Wide" not in one, "the track table follows the act"
    assert "$220.00" in one
    unknown = artist.get("/statements?artist=Nobody").get_data(as_text=True)
    assert "Wide" in unknown, "an unknown act is the whole roster"


def test_one_artist_on_file_shows_no_roster_control_on_statements(artist, monkeypatch):
    _drop_box(monkeypatch)
    _upload(artist, TWO_PERIODS)
    body = artist.get("/statements").get_data(as_text=True)
    assert 'id="statements-artist"' not in body and "Whole roster" not in body

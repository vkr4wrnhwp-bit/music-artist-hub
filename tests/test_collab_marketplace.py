"""The Collab Marketplace screen (owner's approved mock, 2026-09-18).

Locks the honesty rules the screen was built under:
  * a fresh account sees no invented briefs, people or numbers;
  * the tiles are the counts of real rows and add up;
  * every tab, tile and button link answers < 400 for the account;
  * the demo showcase (Maya Chen and friends) never reaches a real account;
  * the marketplace is live (no Sample badge) and Discover is a sample (F-5).
"""
import re
import uuid

import pytest

import db as store
import hubs
from app import create_app

MOCK_PEOPLE = ("Maya Chen", "Darius Cole", "Nia Brooks", "Jasmine R.",
               "Lucas Joyner", "92% match", "Trusted by 86")


def _member(app_obj, name="Member"):
    client = app_obj.test_client()
    email = "cm%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": name, "email": email,
                                 "password": "secret123"})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, "label")
    return client, uid, email


def _tiles(body):
    return {k: int(v) for k, v in
            re.findall(r'data-tile="(\w+)">(\d+)<', body)}


def _live_count():
    """Every open brief not past its closing date: a COUNT, never a list
    length (list_collab_requests stops at 200 rows)."""
    import datetime as _dt
    today = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    with store.get_db() as db:
        return db.execute(
            "SELECT COUNT(*) FROM collab_requests c JOIN users u ON u.id = c.user_id"
            " WHERE c.status = 'open' AND (c.closes = '' OR c.closes >= ?)",
            (today,)).fetchone()[0]


def _main(body):
    """The screen's own body: from the .cm wrapper to the end of <main>.
    (The shell after it, e.g. base.html's guided tour, is not this screen.)"""
    main = body.split('class="cm ')[1] if 'class="cm ' in body else body
    return main.split("</main>")[0]


@pytest.fixture()
def app_obj():
    return create_app()


def test_a_fresh_account_sees_no_invented_people_or_numbers(app_obj):
    client, uid, _ = _member(app_obj)
    body = client.get("/marketplace").get_data(as_text=True)
    assert "Collab Marketplace" in body and "Nothing here is seeded" in body
    for name in MOCK_PEOPLE:
        assert name not in body, name
    tiles = _tiles(body)
    assert set(tiles) == {"open", "mine", "sent", "saved"}
    # "New Matches" had no source; it is gone.
    assert "New Matches" not in body
    assert tiles["mine"] == tiles["sent"] == tiles["saved"] == 0
    assert tiles["open"] == _live_count()
    # Nothing to recommend on, and the page says why rather than guessing.
    assert "Nothing to recommend yet" in body
    assert "No brief yet" in body            # the pipeline's honest empty line


def test_the_tiles_are_real_counts_and_add_up(app_obj):
    poster, puid, _ = _member(app_obj, "Jordan Vale")
    me, uid, email = _member(app_obj, "Rae Cole")
    before = _tiles(me.get("/marketplace").get_data(as_text=True))
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Vocalist", "genre": "Zydeco-%s" % puid[:4],
        "title": "Hook for a zydeco single", "terms": "$300"})
    rid = store.list_own_collab_requests(puid)[0]["id"]
    me.post("/marketplace/post", data={
        "kind": "fun", "role": "Producer", "genre": "Zydeco-%s" % puid[:4],
        "title": "My own brief"})
    me.post("/marketplace/%s/apply" % rid, data={
        "message": "I sing.", "contact": email, "proposal": "$250"})
    me.post("/marketplace/%s/save" % rid)
    body = me.get("/marketplace").get_data(as_text=True)
    t = _tiles(body)
    assert t["open"] == before["open"] + 2
    assert t["mine"] == 1 and t["sent"] == 1 and t["saved"] == 1
    # The applications count on the row is the replies table.
    assert len(store.list_collab_replies(rid)) == 1
    # The Applications tab lists exactly what the tile counts.
    apps = me.get("/marketplace?tab=applications").get_data(as_text=True)
    assert "Hook for a zydeco single" in apps and "$250" in apps
    # Saved filter shows the saved brief only.
    saved = me.get("/marketplace?saved=1").get_data(as_text=True)
    table = saved.split('id="opps"')[1].split('id="cm-pipe-h"')[0]
    assert "Hook for a zydeco single" in table and "My own brief" not in table
    # The poster sees an active project with the real application count.
    proj = poster.get("/marketplace?tab=projects").get_data(as_text=True)
    assert "Hook for a zydeco single" in proj and "1 received" in proj
    assert "Not tracked here" in proj


def test_recommendations_have_a_stated_basis(app_obj):
    poster, puid, _ = _member(app_obj, "Poster")
    me, uid, email = _member(app_obj, "Applicant")
    genre = "Gqom-%s" % uid[:5]
    poster.post("/marketplace/post", data={
        "kind": "split", "role": "Producer", "genre": genre,
        "title": "Gqom beat wanted"})
    me.post("/marketplace/post", data={
        "kind": "fun", "role": "Vocalist", "genre": genre, "title": "Mine"})
    body = me.get("/marketplace").get_data(as_text=True)
    rec = body.split('id="cm-rec-h"')[1].split('id="opps"')[0]
    assert "Gqom beat wanted" in rec and "You post %s briefs" % genre in rec


def test_every_tab_tile_and_button_resolves(app_obj):
    poster, puid, _ = _member(app_obj)
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "title": "Resolve check"})
    rid = store.list_own_collab_requests(puid)[0]["id"]
    me, uid, email = _member(app_obj)
    me.post("/marketplace/%s/apply" % rid, data={"message": "hi", "contact": email})
    for page in ("/marketplace", "/marketplace?tab=briefs",
                 "/marketplace?tab=applications", "/marketplace?tab=projects",
                 "/marketplace?brief=%s" % rid):
        for c in (me, poster):
            body = c.get(page).get_data(as_text=True)
            main = body.split('id="sb-main"')[-1] if 'id="sb-main"' in body else body
            main = main.split("Tool suites")[0].split("TOOL SUITES")[0]
            hrefs = set(re.findall(r'href="(/[^"#]*)', main.split('class="cm ')[1]
                                   if 'class="cm ' in main else main))
            for href in hrefs:
                if href.startswith("/static/"):
                    continue
                code = c.get(href).status_code
                assert code < 400, (page, href, code)
    # Tabs are real links, never anchors.
    body = me.get("/marketplace").get_data(as_text=True)
    nav = body.split('class="cm-tabs"')[1].split("</nav>")[0]
    assert 'href="#' not in nav
    for label in ("Discover", "My Briefs", "Applications", "Active Projects", "Network"):
        assert ">%s<" % label in nav


def test_demo_showcase_never_reaches_a_real_account(app_obj):
    real, _uid, _ = _member(app_obj)
    for tab in ("", "?tab=briefs", "?tab=applications", "?tab=projects"):
        body = real.get("/marketplace" + tab).get_data(as_text=True)
        assert "Showcase" not in body and "Maya Chen" not in body
    demo = app_obj.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    body = demo.get("/marketplace").get_data(as_text=True)
    if "Maya Chen" in body:
        assert "Showcase" in body and "They are not members" in body


def test_existing_actions_still_work(app_obj):
    poster, puid, _ = _member(app_obj)
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "title": "Action check"})
    rid = store.list_own_collab_requests(puid)[0]["id"]
    assert poster.post("/marketplace/%s/close" % rid).status_code == 302
    assert store.get_collab_request(rid)["status"] == "closed"
    assert poster.post("/marketplace/%s/delete" % rid).status_code == 302
    assert store.get_collab_request(rid) is None


def test_badges_are_the_right_way_round():
    """F-5: the marketplace is a real board; Discover shows example artists."""
    live = set(hubs.live_keys())
    assert "marketplace" in live
    assert "discover" not in live


# --- Review fixes, 2026-09-18 -------------------------------------------------

def _parked():
    import importlib.util
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "_sidebar_fold_for_collab", os.path.join(here, "test_sidebar_fold.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PARKED


def test_no_link_on_the_screen_points_at_a_parked_page(app_obj):
    """/network is parked (sample directory profiles); nothing may link to it."""
    import collab_market
    parked = _parked()
    client, _uid, _ = _member(app_obj)
    for _key, _label, href in collab_market.TABS:
        assert href.split("?")[0] not in parked, href
    for tab in ("", "?tab=briefs", "?tab=applications", "?tab=projects"):
        main = _main(client.get("/marketplace" + tab).get_data(as_text=True))
        for href in re.findall(r'href="(/[^"#?]*)', main):
            assert href not in parked, (tab, href)
    nav = client.get("/marketplace").get_data(as_text=True).split(
        'class="cm-tabs"')[1].split("</nav>")[0]
    assert 'href="/tour-board/outreach"' in nav
    assert client.get("/tour-board/outreach").status_code < 400


def test_a_brief_past_its_closing_date_is_labelled_the_same_everywhere(app_obj):
    import datetime as _dt
    yesterday = (_dt.datetime.now(_dt.timezone.utc).date()
                 - _dt.timedelta(days=1)).isoformat()
    poster, puid, _ = _member(app_obj, "Expiry Poster")
    applicant, _auid, aemail = _member(app_obj, "Expiry Applicant")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "title": "Still open brief"})
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "title": "Expired brief"})
    rid = next(r["id"] for r in store.list_own_collab_requests(puid)
               if r["title"] == "Expired brief")
    applicant.post("/marketplace/%s/apply" % rid, data={
        "message": "hi", "contact": aemail})
    assert len(store.list_collab_replies(rid)) == 1
    with store.get_db() as db:
        db.execute("UPDATE collab_requests SET closes = ? WHERE id = ?",
                   (yesterday, rid))
    tiles = _tiles(poster.get("/marketplace").get_data(as_text=True))
    assert tiles["mine"] == 1
    mine = poster.get("/marketplace?tab=briefs").get_data(as_text=True)
    # One "Open" chip per open brief the tile counts; the expired one says so.
    assert mine.count(">Open</span>") == tiles["mine"]
    assert "Closing date passed" in mine
    # An expired brief is not an active project.
    proj = poster.get("/marketplace?tab=projects").get_data(as_text=True)
    assert "Expired brief" not in proj.split('id="cm-proj-h"')[1]
    # The applicant sees the same effective status.
    apps = applicant.get("/marketplace?tab=applications").get_data(as_text=True)
    row = apps.split("Expired brief")[1].split("</tr>")[0]
    assert "Closing date passed" in row and ">Open<" not in row
    # The poster's own pipeline for it says the closing date passed.
    focus = poster.get("/marketplace?brief=%s" % rid).get_data(as_text=True)
    assert "Closing date passed" in focus


def test_tiles_stay_true_above_the_old_200_row_cap(app_obj):
    _poster, puid, _ = _member(app_obj, "Bulk Poster")
    me, uid, _ = _member(app_obj, "Cap Checker")
    marker = "capcheck%s" % uid[:6]
    me.post("/marketplace/post", data={
        "kind": "fun", "role": "Producer", "title": "Oldest %s" % marker})
    oldest = store.list_own_collab_requests(uid)[0]["id"]
    with store.get_db() as db:
        db.execute("UPDATE collab_requests SET created = '2000-01-01T00:00:00'"
                   " WHERE id = ?", (oldest,))
    me.post("/marketplace/%s/save" % oldest)
    made = [store.add_collab_request(puid, "Vocalist", "", "bid", "Bulk %d" % i,
                                     "", "", "", "") for i in range(205)]
    try:
        body = me.get("/marketplace").get_data(as_text=True)
        t = _tiles(body)
        assert t["open"] == _live_count() and t["open"] > 200
        assert t["mine"] == 1 and t["saved"] == 1
        # The table shows a page of rows and says how many more there are.
        assert "more match" in body
        found = me.get("/marketplace?q=%s" % marker).get_data(as_text=True)
        assert "Oldest %s" % marker in found.split('id="opps"')[1]
        saved = me.get("/marketplace?saved=1").get_data(as_text=True)
        assert "Oldest %s" % marker in saved.split('id="opps"')[1]
    finally:
        for rid in made:
            store.delete_collab_request(puid, rid)
        store.delete_collab_request(uid, oldest)


def test_suppressed_fans_are_not_consented_data(app_obj):
    import links_store as mls
    import trust_score
    _client, uid, _ = _member(app_obj)
    for e in ("a@fans.example", "b@fans.example"):
        mls.upsert_fan(uid, e, "")
    pts = dict((n, p) for n, p, _x in trust_score.calculate(uid)["factors"])
    assert pts["Fan data consented"] == 10
    for e in ("a@fans.example", "b@fans.example"):
        mls.suppress_fan(uid, e, "unsubscribed")
    pts = dict((n, p) for n, p, _x in trust_score.calculate(uid)["factors"])
    assert pts["Fan data consented"] == 0


def test_a_fresh_account_is_not_shown_zeros_it_never_measured(app_obj):
    poster, _puid, _ = _member(app_obj, "Unscored Poster")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "title": "Unscored brief"})
    main = _main(poster.get("/marketplace").get_data(as_text=True))
    assert "0/100" not in main and "Trust 0" not in main
    assert "not scored yet" in main
    assert "Not measured yet: no catalog tracks yet" in main
    assert "Not measured yet: no Spotify profile linked" in main


def test_no_em_dash_reaches_the_screen(app_obj):
    client, _uid, _ = _member(app_obj)
    for tab in ("", "?tab=briefs", "?tab=applications", "?tab=projects"):
        main = _main(client.get("/marketplace" + tab).get_data(as_text=True))
        assert "—" not in main and "&mdash;" not in main, tab


def test_save_and_apply_return_to_the_view_they_came_from(app_obj):
    poster, puid, _ = _member(app_obj)
    poster.post("/marketplace/post", data={
        "kind": "split", "role": "Producer", "title": "Back check"})
    rid = store.list_own_collab_requests(puid)[0]["id"]
    me, _uid, email = _member(app_obj)
    r = me.post("/marketplace/%s/save" % rid,
                data={"back": "/marketplace?saved=1"})
    assert r.headers["Location"].endswith("/marketplace?saved=1")
    r = me.post("/marketplace/%s/save" % rid,
                data={"back": "/marketplace?brief=%s#brief" % rid})
    assert r.headers["Location"].endswith("/marketplace?brief=%s#brief" % rid)
    # Anything off this screen falls back to it.
    for bad in ("https://evil.example/", "//evil.example", "/network?tab=my",
                "/marketplaceevil"):
        r = me.post("/marketplace/%s/save" % rid, data={"back": bad})
        assert r.headers["Location"].endswith("/marketplace"), bad
    r = me.post("/marketplace/%s/apply" % rid, data={
        "message": "hi", "contact": email,
        "back": "/marketplace?brief=%s#brief" % rid})
    assert r.headers["Location"].endswith(
        "/marketplace?brief=%s&applied=1#brief" % rid)
    # The opened brief now says you applied instead of offering the form again.
    body = me.get("/marketplace?brief=%s" % rid).get_data(as_text=True)
    assert "You have applied to this brief" in body
    # The rendered forms carry the view they came from.
    assert 'name="back" value="/marketplace?brief=%s#brief"' % rid in body


def test_table_rows_have_one_way_in_and_their_own_deal_chip(app_obj):
    poster, puid, _ = _member(app_obj)
    for kind, title in (("bid", "Chip paid"), ("split", "Chip split"),
                        ("fun", "Chip fun")):
        poster.post("/marketplace/post", data={
            "kind": kind, "role": "Producer", "title": title})
    body = poster.get("/marketplace").get_data(as_text=True)
    table = body.split('class="cm-table"')[1].split("</table>")[0]
    assert "cm-save" not in table and "★" not in table and "☆" not in table
    assert ">Applicants<" in table
    for r in store.list_own_collab_requests(puid):
        assert 'class="bt" href="/marketplace?brief=%s#brief"' % r["id"] in table
    assert 'cm-chip gold">Paid<' in table
    assert 'cm-chip warn">Royalty split<' in table
    assert 'cm-chip ">For fun<' in table


def test_dates_are_short_month_day_labels():
    import datetime as _dt
    import collab_market
    today = _dt.date(2026, 9, 18)
    assert collab_market.short_date("2026-10-02", today) == "Oct 2"
    assert collab_market.short_date("2027-01-05T00:00:00", today) == "Jan 5, 2027"
    assert collab_market.short_date("", today) == ""

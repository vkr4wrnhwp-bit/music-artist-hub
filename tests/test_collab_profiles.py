"""Collaborator profiles (PROFILES-SPEC.md, owner-approved 2026-09-18).

Locks the rules the profiles were built under:
  * opt-in is the privacy line: an unlisted member is never shown,
    matched, counted or listed, and their page does not exist;
  * a rating needs a CLOSED brief the rater posted and an applicant the
    rater marked chosen; once per brief and person; it vanishes with its
    basis;
  * every match % carries the rules that produced it, and no % is shown
    without a basis;
  * unstated stays unstated: "Not stated", "No ratings yet", never 0 or 5.0;
  * briefs' optional location and budget filter only on what is stated.
"""
import datetime as _dt
import io
import re
import uuid

import pytest

import collab_market
import db as store
from app import create_app


def _member(app_obj, name="Member"):
    client = app_obj.test_client()
    email = "cp%s@example.net" % uuid.uuid4().hex[:10]
    client.post("/signup", data={"name": name, "email": email,
                                 "password": "secret123"})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, "label")
    return client, uid, email


def _save_profile(client, **fields):
    data = {"genres": "", "city": "", "country": "", "rate_min": "",
            "rate_max": "", "rate_unit": "", "currency": "USD",
            "availability": "", "available_from": "", "credits": "",
            "bio": ""}
    data.update(fields)
    return client.post("/marketplace/profile", data=data)


def _tiles(body):
    return {k: int(v) for k, v in re.findall(r'data-tile="(\w+)">(\d+)<', body)}


def _main(body):
    main = body.split('class="cm ')[1] if 'class="cm ' in body else body
    return main.split("</main>")[0]


@pytest.fixture()
def app_obj():
    # Every test starts and ends with nobody listed, so one test's listed
    # members never reach another test's "fresh account" (shared test DB).
    app = create_app()
    with store.get_db() as db:
        db.execute("UPDATE collab_profiles SET listed = 0")
    yield app
    with store.get_db() as db:
        db.execute("UPDATE collab_profiles SET listed = 0")


# --- opt-in ----------------------------------------------------------------

def test_nobody_is_listed_until_they_switch_it_on(app_obj):
    member, muid, _ = _member(app_obj, "Quiet Producer")
    viewer, _vuid, _ = _member(app_obj, "Looking Viewer")
    r = _save_profile(member, roles=["Producer"], genres="Drill")
    assert r.status_code == 302
    assert store.get_collab_profile(muid)["listed"] == 0     # default off
    for page in ("/marketplace", "/marketplace/people"):
        assert "Quiet Producer" not in _main(viewer.get(page).get_data(as_text=True)), page
    assert viewer.get("/marketplace/people/%s" % muid).status_code == 404
    assert muid not in {p["user_id"] for p in store.list_listed_collab_profiles()}
    # Switched on: shown.
    _save_profile(member, listed="1", roles=["Producer"], genres="Drill")
    body = viewer.get("/marketplace").get_data(as_text=True)
    assert "Quiet Producer" in _main(body)
    assert viewer.get("/marketplace/people/%s" % muid).status_code == 200
    # Switched off again: gone at once, everywhere.
    _save_profile(member, roles=["Producer"], genres="Drill")
    for page in ("/marketplace", "/marketplace/people"):
        assert "Quiet Producer" not in _main(viewer.get(page).get_data(as_text=True)), page
    assert viewer.get("/marketplace/people/%s" % muid).status_code == 404


def test_an_unlisted_member_is_never_matched_or_counted(app_obj):
    poster, puid, _ = _member(app_obj, "Match Poster")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "genre": "Drill", "title": "Drill beat"})
    member, muid, _ = _member(app_obj, "Hidden Match")
    _save_profile(member, roles=["Producer"], genres="Drill", availability="available")
    body = poster.get("/marketplace").get_data(as_text=True)
    assert _tiles(body)["matches"] == 0
    assert "% match<" not in _main(body)
    people = poster.get("/marketplace/people").get_data(as_text=True)
    assert "0 listed collaborators" in people
    # Listed: now it is a match, and it is new.
    _save_profile(member, listed="1", roles=["Producer"], genres="Drill",
                  availability="available")
    body = poster.get("/marketplace").get_data(as_text=True)
    assert _tiles(body)["matches"] == 1
    assert "100% match" in _main(body)
    # Seen: the next visit counts it as seen, not new.
    assert _tiles(poster.get("/marketplace").get_data(as_text=True))["matches"] == 0


def test_listing_needs_a_role(app_obj):
    member, muid, _ = _member(app_obj)
    body = _save_profile(member, listed="1", genres="Jazz").get_data(as_text=True)
    assert "Pick at least one role" in body
    assert store.get_collab_profile(muid) is None       # nothing saved


def test_the_owner_is_sent_to_their_edit_page_not_a_404(app_obj):
    member, muid, _ = _member(app_obj)
    r = member.get("/marketplace/people/%s" % muid)
    assert r.status_code == 302 and r.headers["Location"].endswith("/marketplace/profile")
    page = member.get("/marketplace/profile").get_data(as_text=True)
    assert "List me in the marketplace" in page and 'name="listed"' in page
    assert "Not listed: only you can see this preview" in page


# --- unstated stays unstated -------------------------------------------------

def test_unstated_fields_say_so_and_are_never_zero(app_obj):
    member, muid, _ = _member(app_obj, "Bare Minimum")
    viewer, _v, _ = _member(app_obj)
    _save_profile(member, listed="1", roles=["Vocalist"])
    card = _main(viewer.get("/marketplace/people").get_data(as_text=True))
    card = card.split("Bare Minimum")[1].split("</article>")[0]
    for text in ("Location not stated", "Genres not stated", "Not stated",
                 "No ratings yet"):
        assert text in card, text
    for bad in ("$0", "0.0", "5.0", "Trusted by 0"):
        assert bad not in card, bad
    page = viewer.get("/marketplace/people/%s" % muid).get_data(as_text=True)
    assert "No ratings yet" in page and "Trusted by 0" not in page


def test_money_and_availability_labels():
    today = _dt.date(2026, 9, 18)
    assert collab_market.money_range(None, None) == ""
    assert collab_market.money_range(150, 400) == "$150–$400"   # en dash, as in the mock
    assert collab_market.money_range(150, None) == "From $150"
    assert collab_market.money_range(None, 2500) == "Up to $2,500"
    assert collab_market.parse_money("") is None
    assert collab_market.parse_money("$1,500") == 1500
    assert collab_market.availability_label({}, today) == "Not stated"
    assert collab_market.availability_label(
        {"availability": "from", "available_from": "2026-10-02"}, today) == "From Oct 2"
    assert collab_market.rating_line(None) == ("No ratings yet", None, 0)


# --- match % -------------------------------------------------------------------

def test_every_match_has_its_reasons_and_unstated_rules_are_left_out():
    today = _dt.date(2026, 9, 18)
    profile = {"roles": ["Producer"], "genres": ["Drill"], "remote_ok": 1,
               "rate_min": 150, "rate_max": 400, "currency": "USD",
               "availability": "available"}
    full = {"role": "Producer", "genre": "Drill", "remote_ok": 1,
            "budget_min": 200, "budget_max": 500, "title": "Full brief"}
    m = collab_market.match_brief(profile, full, today)
    assert m["pct"] == 100
    assert [r["rule"] for r in m["reasons"] if r["hit"]] == [
        "role", "genre", "location", "availability", "budget"]
    assert "Role: Producer matches your brief" in collab_market.why_line(m)
    # A brief that states no genre, place or budget: those rules are not
    # counted, and say so, rather than scoring as misses or hits.
    bare = {"role": "Producer", "genre": "", "title": "Bare brief"}
    m = collab_market.match_brief(profile, bare, today)
    assert m["pct"] == 100
    skipped = [r for r in m["reasons"] if not r["counted"]]
    assert {r["rule"] for r in skipped} == {"genre", "location", "budget"}
    assert all("not counted" in r["text"] for r in skipped)
    # A miss is counted against the %.
    m = collab_market.match_brief(dict(profile, availability="booked"), bare, today)
    assert m["pct"] == 80
    # Nothing in common: no match at all, not 0%.
    assert collab_market.match_brief(
        profile, {"role": "Vocalist", "genre": "Jazz"}, today) is None


def test_no_percent_without_a_basis(app_obj):
    member, _muid, _ = _member(app_obj, "Listed Drummer")
    _save_profile(member, listed="1", roles=["Instrumentalist"], genres="Funk")
    viewer, _vuid, _ = _member(app_obj)
    body = _main(viewer.get("/marketplace").get_data(as_text=True))
    assert "Listed Drummer" in body
    assert "% match<" not in body and "cm-why" not in body
    # With a genre of their own, the viewer gets a % that says why.
    _save_profile(viewer, roles=["Vocalist"], genres="Funk")
    body = _main(viewer.get("/marketplace").get_data(as_text=True))
    assert "% match" in body and "Genre: you both list Funk" in body
    assert "Scored against your own profile" in body


def test_the_match_shows_why_on_the_card_and_the_profile(app_obj):
    poster, _puid, _ = _member(app_obj, "Brief Owner")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Mixing / Mastering", "genre": "Soul",
        "title": "Mix my soul EP", "budget_min": "200", "budget_max": "600",
        "remote_ok": "1"})
    member, muid, _ = _member(app_obj, "Soul Mixer")
    _save_profile(member, listed="1", roles=["Mixing / Mastering"], genres="Soul",
                  remote_ok="1", rate_min="300", rate_max="450",
                  rate_unit="per track", availability="available")
    body = _main(poster.get("/marketplace").get_data(as_text=True))
    card = body.split("Soul Mixer")[0].rsplit("<article", 1)[1] + body.split("Soul Mixer")[1].split("</article>")[0]
    assert "100% match" in card and "Why 100%" in card
    assert "Budget: their rate $300–$450 fits your budget $200–$600" in card
    assert 'your open brief "Mix my soul EP"' in card
    page = poster.get("/marketplace/people/%s" % muid).get_data(as_text=True)
    assert "Why 100%" in page and "Role: Mixing / Mastering matches your brief" in page


# --- ratings ----------------------------------------------------------------------

def _brief_with_applicant(app_obj):
    poster, puid, _ = _member(app_obj, "Rating Poster")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Vocalist", "title": "Hook to rate"})
    rid = store.list_own_collab_requests(puid)[0]["id"]
    singer, suid, semail = _member(app_obj, "Rated Singer")
    singer.post("/marketplace/%s/apply" % rid, data={"message": "hi", "contact": semail})
    reply = store.list_collab_replies(rid)[0]
    _save_profile(singer, listed="1", roles=["Vocalist"])
    return poster, puid, rid, singer, suid, reply


def test_a_rating_needs_a_closed_brief_and_a_chosen_collaborator(app_obj):
    poster, puid, rid, singer, suid, reply = _brief_with_applicant(app_obj)
    rate = "/marketplace/%s/rate/%s" % (rid, suid)
    # Open and not chosen: refused.
    poster.post(rate, data={"stars": "5"})
    assert store.collab_rating_summary([suid]) == {}
    # Chosen, still open: refused.
    poster.post("/marketplace/%s/choose/%s" % (rid, reply["id"]), data={"chosen": "1"})
    assert store.list_collab_replies(rid)[0]["chosen"] == 1
    poster.post(rate, data={"stars": "5"})
    assert store.collab_rating_summary([suid]) == {}
    # Closed but NOT chosen: refused.
    poster.post("/marketplace/%s/choose/%s" % (rid, reply["id"]), data={"chosen": "0"})
    poster.post("/marketplace/%s/close" % rid)
    poster.post(rate, data={"stars": "5"})
    assert store.collab_rating_summary([suid]) == {}
    # Closed AND chosen: allowed, once.
    poster.post("/marketplace/%s/choose/%s" % (rid, reply["id"]), data={"chosen": "1"})
    poster.post(rate, data={"stars": "4", "note": "Sang it in one take."})
    poster.post(rate, data={"stars": "1"})
    s = store.collab_rating_summary([suid])[suid]
    assert s["count"] == 1 and s["mean"] == 4 and s["clients"] == 1
    # Out-of-range stars never land.
    assert store.add_collab_rating(puid, rid, suid, "9", "") is False
    page = poster.get("/marketplace/people/%s" % suid).get_data(as_text=True)
    assert "Trusted by 1 client" in page and "4.0" in page
    assert "Sang it in one take." in page and "Hook to rate" in page
    # Unmarking the collaborator takes the rating's basis, and the rating.
    poster.post("/marketplace/%s/choose/%s" % (rid, reply["id"]), data={"chosen": "0"})
    page = poster.get("/marketplace/people/%s" % suid).get_data(as_text=True)
    assert "No ratings yet" in page and "Sang it in one take." not in page


def test_only_the_poster_can_choose_or_rate(app_obj):
    poster, puid, rid, singer, suid, reply = _brief_with_applicant(app_obj)
    stranger, xuid, _ = _member(app_obj)
    stranger.post("/marketplace/%s/choose/%s" % (rid, reply["id"]), data={"chosen": "1"})
    assert store.list_collab_replies(rid)[0]["chosen"] == 0
    poster.post("/marketplace/%s/choose/%s" % (rid, reply["id"]), data={"chosen": "1"})
    poster.post("/marketplace/%s/close" % rid)
    stranger.post("/marketplace/%s/rate/%s" % (rid, suid), data={"stars": "1"})
    singer.post("/marketplace/%s/rate/%s" % (rid, suid), data={"stars": "5"})
    assert store.collab_rating_summary([suid]) == {}
    # Deleting the brief takes its ratings with it.
    poster.post("/marketplace/%s/rate/%s" % (rid, suid), data={"stars": "5"})
    assert store.collab_rating_summary([suid])[suid]["count"] == 1
    poster.post("/marketplace/%s/delete" % rid)
    assert store.collab_rating_summary([suid]) == {}


def test_active_projects_tile_counts_what_is_chosen(app_obj):
    """One definition for the tile and the tab (review of 2026-09-18): open
    briefs with applications, chosen collaborators still to rate, and open
    briefs where you were chosen."""
    poster, puid, rid, singer, suid, reply = _brief_with_applicant(app_obj)
    # An open brief with an application is in the pipeline: 1 for the poster.
    assert _tiles(poster.get("/marketplace").get_data(as_text=True))["active"] == 1
    assert "active" not in _tiles(singer.get("/marketplace").get_data(as_text=True))
    poster.post("/marketplace/%s/choose/%s" % (rid, reply["id"]), data={"chosen": "1"})
    # Chosen and still open: the singer has a project too.
    assert _tiles(singer.get("/marketplace").get_data(as_text=True))["active"] == 1
    mine = singer.get("/marketplace?tab=projects").get_data(as_text=True)
    assert "You were chosen" in mine and "Hook to rate" in mine
    poster.post("/marketplace/%s/close" % rid)
    # Closed: out of the pipeline, into "to rate" for the poster; finished
    # for the singer.
    assert _tiles(poster.get("/marketplace").get_data(as_text=True))["active"] == 1
    assert "active" not in _tiles(singer.get("/marketplace").get_data(as_text=True))
    proj = poster.get("/marketplace?tab=projects").get_data(as_text=True)
    assert "Rate Rated Singer" in proj
    poster.post("/marketplace/%s/rate/%s" % (rid, suid), data={"stars": "5"})
    assert "active" not in _tiles(poster.get("/marketplace").get_data(as_text=True))


# --- briefs: location and budget -----------------------------------------------------

def test_location_and_budget_filter_only_on_what_briefs_state(app_obj):
    poster, puid, _ = _member(app_obj, "Filter Poster")
    tag = uuid.uuid4().hex[:6]
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "title": "Cheap %s" % tag,
        "budget_min": "100", "budget_max": "300", "city": "Lagos", "country": "Nigeria"})
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "title": "Big %s" % tag,
        "budget_min": "3000", "remote_ok": "1"})
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "title": "Silent %s" % tag})

    def table(qs):
        body = poster.get("/marketplace?q=%s&%s" % (tag, qs)).get_data(as_text=True)
        return body.split('id="opps"')[1].split("</section>")[0]
    t = table("budget=u500")
    assert "Cheap" in t and "Big" not in t and "Silent" not in t
    t = table("budget=2000up")
    assert "Big" in t and "Cheap" not in t and "Silent" not in t
    t = table("budget=unstated")
    assert "Silent" in t and "Cheap" not in t and "Big" not in t
    t = table("loc=remote")
    assert "Big" in t and "Cheap" not in t
    t = table("loc=lagos,+nigeria")
    assert "Cheap" in t and "Big" not in t
    t = table("loc=unstated")
    assert "Silent" in t and "Cheap" not in t and "Big" not in t
    t = table("")
    assert ">Location<" in t and "Lagos, Nigeria" in t and "Remote OK" in t
    silent_row = t.split("Silent %s</a>" % tag)[1].split("</tr>")[0]
    assert "Not stated" in silent_row
    assert "Budget $100–$300" in t and "Budget From $3,000" in t
    stored = [r for r in store.list_own_collab_requests(puid) if r["title"] == "Silent %s" % tag][0]
    assert stored["budget_min"] is None and stored["city"] == "" and stored["remote_ok"] == 0


# --- empty state, photo, links, design -------------------------------------------------

def test_the_empty_state_invites_the_viewer_to_list_themselves(app_obj):
    fresh, _uid, _ = _member(app_obj)
    body = _main(fresh.get("/marketplace").get_data(as_text=True))
    rec = body.split('id="cm-rec-h"')[1].split('id="opps"')[0]
    assert "No member has listed themselves" in rec
    assert 'href="/marketplace/profile"' in rec and "List me in the marketplace" in rec


def test_the_photo_is_their_own_or_their_initials(app_obj):
    member, muid, _ = _member(app_obj, "Photo Person")
    viewer, _v, _ = _member(app_obj)
    _save_profile(member, listed="1", roles=["Producer"])
    card = _main(viewer.get("/marketplace/people").get_data(as_text=True))
    card = card.split("Photo Person")[0].rsplit("<article", 1)[1]
    assert "<img" not in card and ">PP<" in card
    png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
           b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f"
           b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
    r = member.post("/marketplace/profile/photo",
                    data={"photo": (io.BytesIO(png), "me.png")},
                    content_type="multipart/form-data")
    assert r.status_code == 302 and "photo=1" in r.headers["Location"]
    assert store.get_epk(muid)["photo"] == "/uploads/epk_%s.png" % muid
    card = _main(viewer.get("/marketplace/people").get_data(as_text=True))
    assert 'src="/uploads/epk_%s.png"' % muid in card
    bad = member.post("/marketplace/profile/photo",
                      data={"photo": (io.BytesIO(b"x"), "me.gif")},
                      content_type="multipart/form-data")
    assert "photo_error" in bad.headers["Location"]


def test_every_link_on_the_profile_pages_resolves(app_obj):
    member, muid, _ = _member(app_obj, "Link Walker")
    _save_profile(member, listed="1", roles=["Songwriter"], genres="Folk",
                  links=["https://example.com/folk"])
    viewer, _v, _ = _member(app_obj)
    for page in ("/marketplace/profile", "/marketplace/people",
                 "/marketplace/people/%s" % muid):
        for c in (member, viewer):
            body = c.get(page).get_data(as_text=True)
            main = _main(body)
            assert "—" not in main and "&mdash;" not in main, page
            for href in set(re.findall(r'href="(/[^"#]*)', main)):
                if href.startswith(("/static/", "/uploads/")):
                    continue
                assert c.get(href).status_code < 400, (page, href)
    body = viewer.get("/marketplace/people/%s" % muid).get_data(as_text=True)
    assert 'href="https://example.com/folk"' in body and 'rel="noopener noreferrer nofollow"' in body
    # Every profile page opens with the shared plate band.
    for page in ("/marketplace/profile", "/marketplace/people",
                 "/marketplace/people/%s" % muid):
        assert 'class="sb-plate"' in member.get(page).get_data(as_text=True), page


def test_bad_links_are_refused_not_stored(app_obj):
    member, muid, _ = _member(app_obj)
    body = _save_profile(member, roles=["Producer"],
                         links=["javascript:alert(1)"]).get_data(as_text=True)
    assert "must start with http" in body
    assert store.get_collab_profile(muid) is None


def test_the_migration_is_additive_and_repeatable(app_obj):
    store.init_db()
    store.init_db()
    with store.get_db() as db:
        cols = {r[1] for r in db.execute("PRAGMA table_info(collab_requests)")}
        assert {"city", "country", "remote_ok", "budget_min", "budget_max"} <= cols
        assert "chosen" in {r[1] for r in db.execute("PRAGMA table_info(collab_replies)")}
        listed_default = [r for r in db.execute("PRAGMA table_info(collab_profiles)")
                          if r[1] == "listed"][0][4]
        assert listed_default == "0"


# --- review of 2026-09-18: one regression test per finding --------------------

class _Form(dict):
    """A request.form stand-in for clean_profile."""
    def __init__(self, **kw):
        super().__init__({k: v for k, v in kw.items() if not isinstance(v, list)})
        self._lists = {k: v for k, v in kw.items() if isinstance(v, list)}

    def getlist(self, key):
        return self._lists.get(key, [])


def _demo(app_obj):
    demo = app_obj.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    duid = store.get_user_by_email("demo@streetbanker.io")["id"]
    with demo.session_transaction() as s:
        assert s.get("user_id") == duid, "demo login failed"
    return demo, duid


def test_the_demo_account_can_never_be_listed(app_obj):
    demo, duid = _demo(app_obj)
    poster, puid, _ = _member(app_obj, "Real Poster")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "genre": "Synthwave", "title": "Synth beat"})
    store.set_collab_seen(puid, "2000-01-01")
    before = _tiles(poster.get("/marketplace").get_data(as_text=True))["matches"]
    store.set_collab_seen(puid, "2000-01-01")
    # The route refuses the switch...
    body = _save_profile(demo, listed="1", roles=["Producer"],
                         genres="Synthwave").get_data(as_text=True)
    assert "cannot be listed" in body
    assert (store.get_collab_profile(duid) or {}).get("listed", 0) == 0
    # ...and the reads refuse the row even when it is forced on in SQL.
    fields = collab_market.clean_profile(
        _Form(listed="1", roles=["Producer"], genres="Synthwave"))[0]
    store.save_collab_profile(duid, dict(fields, listed=1))
    assert store.get_collab_profile(duid)["listed"] == 1
    name = store.get_user(duid)["name"]
    try:
        for page in ("/marketplace", "/marketplace/people"):
            assert name not in _main(poster.get(page).get_data(as_text=True)), page
        assert poster.get("/marketplace/people/%s" % duid).status_code == 404
        assert _tiles(poster.get("/marketplace").get_data(as_text=True))["matches"] == before
        assert duid not in {p["user_id"] for p in store.list_listed_collab_profiles()}
    finally:
        with store.get_db() as db:
            db.execute("UPDATE collab_profiles SET listed = 0 WHERE user_id = ?", (duid,))


def test_the_demo_login_never_sees_a_member(app_obj):
    member, muid, _ = _member(app_obj, "Private Rita")
    _save_profile(member, listed="1", roles=["Producer"], genres="Synthwave")
    demo, _duid = _demo(app_obj)
    body = demo.get("/marketplace").get_data(as_text=True)
    assert "Private Rita" not in _main(body)
    people = demo.get("/marketplace/people").get_data(as_text=True)
    assert "Private Rita" not in _main(people)
    assert "does not see members&#39; profiles" in people or \
        "does not see members' profiles" in people
    assert demo.get("/marketplace/people/%s" % muid).status_code == 404


def test_locked_and_ended_accounts_leave_the_marketplace(app_obj):
    poster, puid, _ = _member(app_obj, "Shut Poster")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "genre": "Drill", "title": "Drill job"})
    locked, luid, _ = _member(app_obj, "Locked Larry")
    ended, euid, _ = _member(app_obj, "Ended Erin")
    for c in (locked, ended):
        _save_profile(c, listed="1", roles=["Producer"], genres="Drill",
                      availability="available")
    store.set_account_locked(luid, True)
    store.set_access_ends(euid, "2020-01-01T00:00:00+00:00")
    store.set_collab_seen(puid, "2000-01-01")
    body = poster.get("/marketplace").get_data(as_text=True)
    people = _main(poster.get("/marketplace/people").get_data(as_text=True))
    for name in ("Locked Larry", "Ended Erin"):
        assert name not in _main(body) and name not in people, name
    assert _tiles(body)["matches"] == 0
    for uid in (luid, euid):
        assert poster.get("/marketplace/people/%s" % uid).status_code == 404
    # Opened again (the lock lifted, a future end date): back as they left it.
    store.set_account_locked(luid, False)
    store.set_access_ends(euid, "2999-01-01T00:00:00+00:00")
    people = _main(poster.get("/marketplace/people").get_data(as_text=True))
    assert "Locked Larry" in people and "Ended Erin" in people


def test_saying_less_never_scores_more():
    today = _dt.date(2026, 9, 18)
    brief = {"role": "Producer", "genre": "Drill", "city": "Atlanta",
             "country": "USA", "budget_min": 200, "budget_max": 500, "title": "B"}
    sparse = {"roles": ["Producer"], "genres": ["Drill"]}
    full = dict(sparse, city="London", country="UK", availability="available",
                rate_min=300, rate_max=400, currency="USD", credits="x", bio="y")
    ms = collab_market.match_brief(sparse, brief, today)
    mf = collab_market.match_brief(full, brief, today)
    assert ms["pct"] < mf["pct"] and ms["pct"] < 100
    # Rules the brief states and the profile leaves unanswered are counted,
    # not earned, and say so.
    by_rule = {r["rule"]: r for r in ms["reasons"]}
    for rule in ("location", "availability", "budget"):
        assert by_rule[rule]["counted"] and not by_rule[rule]["hit"], rule
        assert "not earned" in by_rule[rule]["text"], rule
    # One matching role on a role-only brief is not 100%: availability is
    # always asked.
    m = collab_market.match_brief({"roles": ["Producer"]}, {"role": "Producer"}, today)
    assert m["pct"] == 80
    # The self-match: one shared genre and nothing else said is not 100%.
    me = {"genres": ["Funk"], "city": "Leeds"}
    assert collab_market.match_self({"genres": ["Funk"]}, me, today)["pct"] == 60


def test_a_fuller_profile_never_ranks_below_a_sparser_one(app_obj):
    poster, puid, _ = _member(app_obj, "Rank Poster")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "genre": "Drill", "title": "Rank brief",
        "city": "Atlanta", "country": "USA", "budget_min": "200", "budget_max": "500"})
    sparse, _s, _ = _member(app_obj, "Sparse Sam")
    full, _f, _ = _member(app_obj, "Complete Cara")
    _save_profile(sparse, listed="1", roles=["Producer"], genres="Drill")
    _save_profile(full, listed="1", roles=["Producer"], genres="Drill",
                  city="London", country="UK", availability="available",
                  rate_min="300", rate_max="400", credits="Ten drill tapes")
    for page in ("/marketplace", "/marketplace/people"):
        body = _main(poster.get(page).get_data(as_text=True))
        assert body.index("Complete Cara") < body.index("Sparse Sam"), page


def _budget_reason(profile, brief):
    today = _dt.date(2026, 9, 18)
    m = collab_market.match_brief(dict(profile, roles=["Producer"]),
                                  dict(brief, role="Producer"), today)
    return [r for r in m["reasons"] if r["rule"] == "budget"][0]


def test_one_sided_ranges_stay_open():
    b = _budget_reason({"rate_min": 100, "rate_max": 200}, {"budget_max": 500})
    assert b["hit"] and b["text"] == (
        "Budget: their rate $100–$200 fits your budget up to $500")
    b = _budget_reason({"rate_min": 150}, {"budget_min": 200, "budget_max": 500})
    assert b["hit"] and "their rate from $150 fits" in b["text"]
    b = _budget_reason({"rate_max": 100}, {"budget_min": 200})
    assert b["counted"] and not b["hit"]
    assert "their rate up to $100 is outside your budget from $200" in b["text"]
    f = collab_market.budget_filter
    assert f({"budget_max": 3000}, "500-2000") and f({"budget_max": 3000}, "u500")
    assert f({"budget_max": 3000}, "2000up")
    assert f({"budget_min": 150}, "500-2000") and f({"budget_min": 150}, "2000up")
    assert not f({"budget_min": 2500}, "u500")
    assert not f({"budget_max": 400}, "500-2000")


def test_money_is_read_strictly():
    read = collab_market.read_money
    assert read("") == (None, True) and read("  ") == (None, True)
    assert read("$1,500") == (1500, True) and read("300") == (300, True)
    assert read("2k") == (2000, True) and read("$1.5k") == (1500, True)
    assert read("199.99") == (200, True)
    for bad in ("-100", "150-400", "USD 200", "1,50", "abc", "$", "1e5", "99999999"):
        assert read(bad) == (None, False), bad
    assert collab_market.parse_money("150-400") is None


def test_a_bad_amount_is_refused_not_guessed(app_obj):
    member, muid, _ = _member(app_obj)
    body = _save_profile(member, roles=["Producer"],
                         rate_min="150-400").get_data(as_text=True)
    assert "is not an amount" in body and store.get_collab_profile(muid) is None
    _save_profile(member, roles=["Producer"], rate_min="1k", rate_max="2k")
    saved = store.get_collab_profile(muid)
    assert (saved["rate_min"], saved["rate_max"]) == (1000, 2000)
    poster, puid, _ = _member(app_obj)
    for lo, hi in (("2k", "5k-6k"), ("-100", ""), ("USD 200", "")):
        r = poster.post("/marketplace/post", data={
            "kind": "bid", "role": "Producer", "title": "Money %s" % lo,
            "budget_min": lo, "budget_max": hi})
        assert "post_error=" in r.headers["Location"], (lo, hi)
    assert store.list_own_collab_requests(puid) == []
    page = poster.get(r.headers["Location"]).get_data(as_text=True)
    assert "Not posted." in page and "is not an amount" in page
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Producer", "title": "Money ok",
        "budget_min": "2k", "budget_max": "5k"})
    b = store.list_own_collab_requests(puid)[0]
    assert (b["budget_min"], b["budget_max"]) == (2000, 5000)


def _rated_pair(app_obj):
    poster, puid, rid, singer, suid, reply = _brief_with_applicant(app_obj)
    poster.post("/marketplace/%s/choose/%s" % (rid, reply["id"]), data={"chosen": "1"})
    poster.post("/marketplace/%s/close" % rid)
    poster.post("/marketplace/%s/rate/%s" % (rid, suid),
                data={"stars": "2", "note": "late"})
    assert store.collab_rating_summary([suid])[suid]["count"] == 1
    return poster, puid, rid, singer, suid


def test_start_over_keeps_ratings_about_the_account(app_obj):
    poster, puid, rid, singer, suid = _rated_pair(app_obj)
    store.reset_user_data(suid)
    assert store.get_user(suid) is not None
    assert store.collab_rating_summary([suid])[suid]["count"] == 1
    _save_profile(singer, listed="1", roles=["Vocalist"])
    viewer, _v, _ = _member(app_obj)
    page = viewer.get("/marketplace/people/%s" % suid).get_data(as_text=True)
    assert "No ratings yet" not in page and "Trusted by 1 client" in page


def test_deleting_the_account_removes_ratings_about_it(app_obj):
    poster, puid, rid, singer, suid = _rated_pair(app_obj)
    store.delete_user_everything(suid)
    with store.get_db() as db:
        n = db.execute("SELECT COUNT(*) FROM collab_ratings WHERE ratee_id = ?",
                       (suid,)).fetchone()[0]
    assert n == 0


def test_nobody_can_rate_themselves(app_obj):
    poster, puid, _ = _member(app_obj, "Self Rater")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Vocalist", "title": "My own brief"})
    rid = store.list_own_collab_requests(puid)[0]["id"]
    store.add_collab_reply(rid, puid, "me", "self@example.net", "", "")
    reply = store.list_collab_replies(rid)[0]
    assert store.set_collab_reply_chosen(puid, reply["id"], True)
    poster.post("/marketplace/%s/close" % rid)
    assert store.add_collab_rating(puid, rid, puid, 5, "great") is False
    poster.post("/marketplace/%s/rate/%s" % (rid, puid), data={"stars": "5"})
    assert store.collab_rating_summary([puid]) == {}
    # Even a row forced into the table is never read back.
    with store.get_db() as db:
        db.execute("INSERT INTO collab_ratings (id, request_id, user_id, ratee_id,"
                   " stars, note, created) VALUES (?,?,?,?,5,'','2026-09-18')",
                   (uuid.uuid4().hex, rid, puid, puid))
    assert store.collab_rating_summary([puid]) == {}


def test_a_finished_brief_is_not_an_active_project(app_obj):
    poster, puid, rid, singer, suid = _rated_pair(app_obj)
    assert "active" not in _tiles(singer.get("/marketplace").get_data(as_text=True))
    assert "active" not in _tiles(poster.get("/marketplace").get_data(as_text=True))
    tab = singer.get("/marketplace?tab=projects").get_data(as_text=True)
    assert "Finished" in tab and "Hook to rate" in tab


def test_the_tile_counts_what_the_tab_lists(app_obj):
    poster, puid, _ = _member(app_obj, "Pipeline Poster")
    for i in range(3):
        poster.post("/marketplace/post", data={
            "kind": "bid", "role": "Vocalist", "title": "Pipe %d" % i})
    applicant, auid, aemail = _member(app_obj)
    for r in store.list_own_collab_requests(puid):
        applicant.post("/marketplace/%s/apply" % r["id"],
                       data={"message": "hi", "contact": aemail})
    assert _tiles(poster.get("/marketplace").get_data(as_text=True))["active"] == 3
    tab = poster.get("/marketplace?tab=projects").get_data(as_text=True)
    assert tab.count('class="cm-proj"') == 3


def test_reasons_say_what_is_true():
    today = _dt.date(2026, 9, 18)
    b = _budget_reason({"rate_min": 100, "rate_max": 300, "currency": "GBP"},
                       {"budget_min": 200, "budget_max": 500})
    assert b["text"] == "Budget: their rate is in GBP and only USD is compared, not counted"
    b = _budget_reason({}, {"budget_min": 200, "budget_max": 500})
    assert b["text"] == "Budget: they have not stated a rate, not earned"
    b = _budget_reason({"rate_min": 100}, {})
    assert b["text"] == "Budget: your brief states none, not counted"
    m = collab_market.match_brief(
        {"roles": ["Producer"], "city": "London", "country": "UK"},
        {"role": "Producer", "remote_ok": 1}, today)
    t = [r for r in m["reasons"] if r["rule"] == "location"][0]["text"]
    assert "remote only" not in t and "open to remote" in t and "London, UK" in t


def test_a_listed_viewer_is_not_told_to_list_themselves(app_obj):
    viewer, vuid, _ = _member(app_obj, "Listed Viewer")
    _save_profile(viewer, listed="1", roles=["Producer"])
    body = viewer.get("/marketplace/people").get_data(as_text=True)
    assert "0 other listed collaborators" in body
    assert "No other member has listed themselves yet. You are listed" in body
    assert "List me in the marketplace</a>" not in _main(body)


def test_the_recommended_row_fills_to_three(app_obj):
    poster, puid, _ = _member(app_obj, "Row Poster")
    poster.post("/marketplace/post", data={
        "kind": "bid", "role": "Mixing / Mastering", "genre": "Hip Hop", "title": "Mix"})
    names = ("Row Ari", "Row Tomasina", "Row Lena")
    for name, roles, genres in ((names[0], ["Mixing / Mastering"], "Hip Hop"),
                                (names[1], ["Producer"], "R&B"),
                                (names[2], ["Visuals / Cover Art"], "")):
        c, _u, _ = _member(app_obj, name)
        _save_profile(c, listed="1", roles=roles, genres=genres)
    body = _main(poster.get("/marketplace").get_data(as_text=True))
    rec = body.split('id="cm-rec-h"')[1].split('id="opps"')[0]
    assert all(n in rec for n in names)
    assert rec.index("Row Ari") < rec.index("Row Tomasina")
    assert rec.count("% match<") == 1 and "A card with no %" in rec


def test_new_pages_use_no_green_notice_and_card_polish(app_obj):
    member, muid, _ = _member(app_obj, "Polish Pat")
    _save_profile(member, listed="1", roles=["Producer"],
                  genres="Soul, Funk, Jazz, R&B, Pop, Rock",
                  rate_min="150", rate_max="400")
    for page in ("/marketplace/profile?saved=1&photo=1",
                 "/marketplace/people/%s" % muid):
        body = member.get(page).get_data(as_text=True)
        assert "cm-notice" in body and "cm-flash" not in _main(body), page
    viewer, _v, _ = _member(app_obj)
    people = _main(viewer.get("/marketplace/people").get_data(as_text=True))
    card = people.split("Polish Pat")[1].split("</article>")[0]
    assert ">+2<" in card and "$150–<wbr>$400" in card
    bare, _b, _ = _member(app_obj, "Bare Bob")
    _save_profile(bare, listed="1", roles=["Producer"])
    people = _main(viewer.get("/marketplace/people").get_data(as_text=True))
    card = people.split("Bare Bob")[1].split("</article>")[0]
    assert '<div class="k">Rate</div><div class="v">Not stated</div>' in card
    edit = member.get("/marketplace/profile").get_data(as_text=True)
    assert "This is your card as last saved." in edit
    assert "It reflects the details in the form" not in edit


def test_the_tile_row_has_one_column_per_tile(app_obj):
    poster, puid, _ = _member(app_obj)
    body = poster.get("/marketplace").get_data(as_text=True)
    assert 'class="cm-tiles n4"' in body and len(_tiles(body)) == 4
    poster.post("/marketplace/post", data={"kind": "bid", "role": "Producer", "title": "T"})
    body = poster.get("/marketplace").get_data(as_text=True)
    assert 'class="cm-tiles n5"' in body and len(_tiles(body)) == 5
    assert "cm-sub" not in body

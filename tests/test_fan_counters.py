"""The Fan CRM's Visits and Clicks count what a known fan really did.

Until 2026-09-23 both columns were 0 for every fan on every account: the
smart link page and its /go/ redirect recorded each view and click with no
fan attached, and nothing ever called bump_fan with total_visits or
total_clicks. The CRM table had dropped the two columns; the CSV still
printed them, always 0, and 30 of the intent score's 100 points could
never move.

Now a fan is known on a smart link when the request carries their signed
?f= (fan_mail.fan_token): the link in every release-day email the app
sends them, passed on by the page to its own service buttons, and handed
to the page when they sign up on it. A known fan's view is their visit
(once per sitting), their button press is their click, and both re-score
them. Anonymous traffic credits nobody, and a token only ever counts on
its own account's links.
"""
import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

import app as appmod
import db as store
import fan_mail
import links_store as mls

PW = "fan-counters-12345"
SECRET = appmod.app.config["SECRET_KEY"]


def _account():
    email = "counters-%s@example.net" % uuid.uuid4().hex[:10]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Counter Artist", "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    c.post("/plan/switch", data={"plan": "pro"})
    return c, uid


def _live_campaign(uid, title="Counted"):
    slug = "cnt-%s" % uuid.uuid4().hex[:8]
    cid = mls.create_campaign(uid, slug, {"title": title, "release_date": "2020-01-01",
                                          "settings": {"email_capture": True}})
    mls.update_campaign(cid, uid, {"status": "live"})
    mls.set_destinations(cid, [{"service_key": "spotify", "service_name": "Spotify",
                                "url": "https://open.spotify.com/track/T1", "sort_order": 0}])
    dest = mls.get_destinations(cid)[0]
    return cid, slug, dest["id"]


def _fan(uid, cid, email=None):
    fid = mls.upsert_fan(uid, email or "fan-%s@example.net" % uuid.uuid4().hex[:8], cid, "A Fan")
    mls.add_consent(fid, cid, "email_marketing", "yes")
    return fid


def _events(cid, event_type):
    with store.get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM ml_events WHERE campaign_id = ? AND event_type = ?",
            (cid, event_type)).fetchall()]


def test_a_view_through_a_fans_own_link_is_their_visit_once_per_sitting():
    _c, uid = _account()
    cid, slug, _d = _live_campaign(uid)
    fid = _fan(uid, cid)
    anon = appmod.app.test_client()
    tok = fan_mail.fan_token(SECRET, fid)
    assert anon.get("/l/%s?f=%s" % (slug, tok)).status_code == 200
    assert mls.get_fan(fid)["total_visits"] == 1
    assert [e["fan_id"] for e in _events(cid, "page_view")] == [fid]
    # A reload inside the window is still a recorded view, not a second visit.
    anon.get("/l/%s?f=%s" % (slug, tok))
    assert mls.get_fan(fid)["total_visits"] == 1
    assert len(_events(cid, "page_view")) == 2
    # The next sitting is the next visit.
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    with store.get_db() as db:
        db.execute("UPDATE ml_events SET created = ? WHERE campaign_id = ?", (old, cid))
    anon.get("/l/%s?f=%s" % (slug, tok))
    fan = mls.get_fan(fid)
    assert fan["total_visits"] == 2
    # and the visit moved the score: 2 points a visit
    assert fan["intent_score"] == 4


def test_the_page_passes_the_fans_link_on_to_its_service_buttons_and_the_click_counts():
    _c, uid = _account()
    cid, slug, dest = _live_campaign(uid)
    fid = _fan(uid, cid)
    anon = appmod.app.test_client()
    tok = fan_mail.fan_token(SECRET, fid)
    body = anon.get("/l/%s?f=%s" % (slug, tok)).get_data(as_text=True)
    href = "/l/%s/go/%s?f=%s" % (slug, dest, tok)
    assert href in body, "the service button must carry the fan's own link"
    r = anon.get(href)
    assert r.status_code == 302 and r.headers["Location"] == "https://open.spotify.com/track/T1"
    fan = mls.get_fan(fid)
    assert fan["total_clicks"] == 1
    assert fan["intent_score"] == 2 + 5
    clicks = _events(cid, "service_click")
    assert [(e["fan_id"], e["service_key"]) for e in clicks] == [(fid, "spotify")]


def test_anonymous_views_and_clicks_credit_nobody():
    _c, uid = _account()
    cid, slug, dest = _live_campaign(uid)
    fid = _fan(uid, cid)
    anon = appmod.app.test_client()
    body = anon.get("/l/" + slug).get_data(as_text=True)
    assert "?f=" not in body.split("/go/", 1)[1].split('"', 1)[0]
    anon.get("/l/%s/go/%s" % (slug, dest))
    fan = mls.get_fan(fid)
    assert (fan["total_visits"], fan["total_clicks"]) == (0, 0)
    assert [e["fan_id"] for e in _events(cid, "page_view")] == [None]
    assert [e["fan_id"] for e in _events(cid, "service_click")] == [None]


def test_a_token_counts_only_on_its_own_accounts_links_and_a_forged_one_never():
    _a, uid_a = _account()
    _b, uid_b = _account()
    cid_a, slug_a, dest_a = _live_campaign(uid_a)
    cid_b, _slug_b, _dest_b = _live_campaign(uid_b)
    fan_b = _fan(uid_b, cid_b)
    anon = appmod.app.test_client()
    foreign = fan_mail.fan_token(SECRET, fan_b)
    anon.get("/l/%s?f=%s" % (slug_a, foreign))
    anon.get("/l/%s/go/%s?f=%s" % (slug_a, dest_a, foreign))
    forged = fan_mail.fan_token("not-the-key", fan_b)
    anon.get("/l/%s/go/%s?f=%s" % (slug_a, dest_a, forged))
    anon.get("/l/%s/go/%s?f=%s" % (slug_a, dest_a, foreign + "x"))
    fan = mls.get_fan(fan_b)
    assert (fan["total_visits"], fan["total_clicks"]) == (0, 0)
    assert all(e["fan_id"] is None for e in _events(cid_a, "service_click"))
    assert all(e["fan_id"] is None for e in _events(cid_a, "page_view"))


def test_signing_up_on_the_page_hands_back_the_link_that_credits_the_next_click():
    _c, uid = _account()
    cid, slug, dest = _live_campaign(uid)
    anon = appmod.app.test_client()
    anon.get("/l/" + slug)
    r = anon.post("/l/%s/subscribe" % slug, data={"email": "joined@example.net"})
    data = r.get_json()
    assert data["ok"] and data["fan_token"]
    fan = mls.fan_by_email(uid, "joined@example.net")
    assert fan_mail.read_fan_token(SECRET, data["fan_token"]) == fan["id"]
    anon.get("/l/%s/go/%s?f=%s" % (slug, dest, data["fan_token"]))
    fan = mls.get_fan(fan["id"])
    assert fan["total_captures"] == 1 and fan["total_clicks"] == 1
    assert fan["intent_score"] == 25 + 5
    # The page script sets the token on the buttons and strips it from
    # the address bar; both halves are in the page.
    page = anon.get("/l/" + slug).get_data(as_text=True)
    assert "data.fan_token" in page and 'searchParams.delete("f")' in page
    assert "data-go" in page


def test_the_owners_preview_of_a_draft_credits_nobody():
    c, uid = _account()
    slug = "cnt-%s" % uuid.uuid4().hex[:8]
    cid = mls.create_campaign(uid, slug, {"title": "Draft"})
    fid = _fan(uid, cid)
    tok = fan_mail.fan_token(SECRET, fid)
    assert c.get("/l/%s?f=%s" % (slug, tok)).status_code == 200
    assert mls.get_fan(fid)["total_visits"] == 0
    assert _events(cid, "page_view") == []


def test_the_crm_shows_visits_and_clicks_and_the_csv_carries_the_same_figures():
    c, uid = _account()
    cid, slug, dest = _live_campaign(uid)
    fid = _fan(uid, cid, "counted@example.net")
    anon = appmod.app.test_client()
    tok = fan_mail.fan_token(SECRET, fid)
    anon.get("/l/%s?f=%s" % (slug, tok))
    anon.get("/l/%s/go/%s?f=%s" % (slug, dest, tok))
    anon.get("/l/%s/go/%s?f=%s" % (slug, dest, tok))
    body = c.get("/links/fans").get_data(as_text=True)
    head = body.split("<thead>", 1)[1].split("</thead>", 1)[0]
    assert ">Visits</th>" in head and ">Clicks</th>" in head
    row = body.split("counted@example.net", 1)[1].split("</tr>", 1)[0]
    cells = [x.split("</td>", 1)[0].strip() for x in row.split('text-right sb-num text-gray-200">')[1:]]
    assert cells[:2] == ["1", "2"], cells
    assert "data-crm-counts" in body, "the page says what the two columns count"
    out = c.get("/links/fans/export.csv").get_data(as_text=True)
    rows = list(csv.reader(io.StringIO(out)))
    head, rec = rows[0], next(r for r in rows[1:] if r[0] == "counted@example.net")
    assert rec[head.index("Visits")] == "1" and rec[head.index("Clicks")] == "2"


def test_each_release_day_email_carries_the_fans_own_link(monkeypatch):
    import email_provider as emailer
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    sent = []
    monkeypatch.setattr(emailer, "_http",
                        lambda url, payload, headers: sent.append(payload) or {"id": "em"})
    _c, uid = _account()
    cid, slug, _d = _live_campaign(uid)
    one = _fan(uid, cid, "one-%s@example.net" % uuid.uuid4().hex[:6])
    two = _fan(uid, cid, "two-%s@example.net" % uuid.uuid4().hex[:6])
    anon = appmod.app.test_client()
    anon.get("/l/" + slug)          # released: the first view sends
    by_to = {p["to"][0]: p["html"] for p in sent}
    assert len(by_to) == 2
    for fid in (one, two):
        email = mls.get_fan(fid)["email"]
        assert "/l/%s?f=%s" % (slug, fan_mail.fan_token(SECRET, fid)) in by_to[email]
    # Following the link in the email is that fan's visit.
    link = by_to[mls.get_fan(one)["email"]].split('href="', 1)[1].split('"', 1)[0]
    anon.get(link.replace("http://localhost", ""))
    assert mls.get_fan(one)["total_visits"] == 1
    assert mls.get_fan(two)["total_visits"] == 0

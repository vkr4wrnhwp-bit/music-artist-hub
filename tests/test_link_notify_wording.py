"""The pre-release email box says what it does, and the reminder it
promises goes out.

Audit overclaim 17 (2026-09-11), still true at 9852efb5: on a pre-release
smart link the email button defaulted to "Pre-Save" and the Spotify,
Apple Music and Deezer rows read "Pre-save". The box only stores an
address for the release-day email; nothing is saved to any library, and
without Spotify keys it was the only thing on the page called Pre-Save.
The real Spotify pre-save button is separate and appears on its own when
the owner's Spotify app is configured.

Now the box says "Remind me" where the release-day email can go, and
"Join the list" where it cannot; an artist's own button text is kept
unless it claims a save. The service rows say "Open" before release. The
sign-up's reply promises a release-day email only where one can be sent,
and the daily run (/reminders/run) sends that email for a page nobody has
opened since release day, within a week of it.
"""
import uuid
from datetime import date, timedelta

import app as appmod
import db as store
import email_provider as emailer
import links_engine
import links_store as mls

PW = "notify-pass-12345"


def _account():
    email = "notify-%s@example.net" % uuid.uuid4().hex[:10]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Notify Artist", "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    return uid


def _campaign(uid, release_date, cta=""):
    slug = "ntf-%s" % uuid.uuid4().hex[:8]
    settings = {"email_capture": True}
    if cta:
        settings["cta_text"] = cta
    cid = mls.create_campaign(uid, slug, {"title": "Soon", "release_date": release_date,
                                          "settings": settings})
    mls.update_campaign(cid, uid, {"status": "live"})
    mls.set_destinations(cid, [
        {"service_key": "spotify", "service_name": "Spotify",
         "url": "https://open.spotify.com/album/A1", "sort_order": 0},
        {"service_key": "apple_music", "service_name": "Apple Music",
         "url": "https://music.apple.com/album/A1", "sort_order": 1}])
    return cid, slug


def _no_spotify(monkeypatch):
    for k in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI"):
        monkeypatch.delenv(k, raising=False)


def test_the_button_text_never_claims_a_save():
    t = links_engine.notify_button_text
    assert t({}, True) == "Remind me"
    assert t({}, False) == "Join the list"
    for claim in ("Pre-Save", "presave now", "Save it", "Pre-add on Apple", "Add to library"):
        assert t({"cta_text": claim}, True) == "Remind me", claim
    assert t({"cta_text": "Get the drop"}, True) == "Get the drop"
    assert "release day" in links_engine.notify_done_text(True)
    assert links_engine.notify_done_text(False) == "You're on the list."


def test_the_pre_release_page_says_remind_me_and_open_not_pre_save(monkeypatch):
    _no_spotify(monkeypatch)
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    uid = _account()
    _cid, slug = _campaign(uid, (date.today() + timedelta(days=20)).isoformat(),
                           cta="Pre-Save")
    body = appmod.app.test_client().get("/l/" + slug).get_data(as_text=True)
    form = body.split('id="capture-form"', 1)[1].split("</form>", 1)[0]
    assert ">Remind me</button>" in form
    assert "pre-save" not in body.lower(), "nothing on the page is called a pre-save"
    rows = body.split("data-go", 1)[1]
    assert "Open →" in rows


def test_without_email_the_box_is_a_sign_up_and_promises_nothing(monkeypatch):
    _no_spotify(monkeypatch)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    uid = _account()
    _cid, slug = _campaign(uid, (date.today() + timedelta(days=20)).isoformat())
    anon = appmod.app.test_client()
    body = anon.get("/l/" + slug).get_data(as_text=True)
    assert ">Join the list</button>" in body
    r = anon.post("/l/%s/subscribe" % slug, data={"email": "quiet@example.net"}).get_json()
    assert r["ok"] and r["message"] == "You're on the list."


def test_with_email_the_reply_promises_the_release_day_email(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    uid = _account()
    _cid, slug = _campaign(uid, (date.today() + timedelta(days=20)).isoformat())
    r = appmod.app.test_client().post("/l/%s/subscribe" % slug,
                                      data={"email": "loud@example.net"}).get_json()
    assert r["message"] == "You're on the list. We'll email you on release day."


def test_the_daily_run_sends_the_release_day_email_nobody_opened_the_page_for(monkeypatch):
    import contract_reminders
    import release_ready
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("BACKUP_TOKEN", "tok-notify")
    monkeypatch.setattr(contract_reminders, "run", lambda **k: {"sent": 0})
    monkeypatch.setattr(release_ready, "run_due", lambda: {})
    sent = []
    monkeypatch.setattr(emailer, "_http",
                        lambda url, payload, headers: sent.append(payload) or {"id": "em"})
    uid = _account()
    today = date.today()
    fresh, fresh_slug = _campaign(uid, (today - timedelta(days=1)).isoformat())
    stale, _s = _campaign(uid, (today - timedelta(days=40)).isoformat())
    soon, _n = _campaign(uid, (today + timedelta(days=3)).isoformat())
    who = {}
    for cid in (fresh, stale, soon):
        email = "run-%s@example.net" % uuid.uuid4().hex[:8]
        fid = mls.upsert_fan(uid, email, cid)
        mls.add_consent(fid, cid, "presave_notify", "remind me")
        who[cid] = email
    r = appmod.app.test_client().post("/reminders/run",
                                      headers={"X-Backup-Token": "tok-notify"})
    assert r.status_code == 200
    to = [p["to"][0] for p in sent]
    assert who[fresh] in to, "released yesterday, never viewed: the run sends it"
    assert who[stale] not in to, "forty days late is not a reminder"
    assert who[soon] not in to, "not released yet"
    assert r.get_json()["release_emails"] >= 1
    assert mls.get_campaign(fresh)["settings"]["release_email_sent"] is True
    # A later view, or a second run, sends nothing more.
    before = len(sent)
    appmod.app.test_client().get("/l/" + fresh_slug)
    appmod.app.test_client().post("/reminders/run", headers={"X-Backup-Token": "tok-notify"})
    assert [p["to"][0] for p in sent[before:]].count(who[fresh]) == 0


def _run_patched(monkeypatch):
    import contract_reminders
    import release_ready
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("BACKUP_TOKEN", "tok-notify")
    monkeypatch.setattr(contract_reminders, "run", lambda **k: {"sent": 0})
    monkeypatch.setattr(release_ready, "run_due", lambda: {})


def _remind(uid, cid):
    email = "once-%s@example.net" % uuid.uuid4().hex[:8]
    fid = mls.upsert_fan(uid, email, cid)
    mls.add_consent(fid, cid, "presave_notify", "remind me")
    return email


def test_a_first_view_during_the_daily_run_never_mails_a_fan_twice(monkeypatch):
    # Review finding F1 (2026-09-23): the run read its list of campaigns
    # once, before it started, and _send_release_emails checked the
    # once-only flag on that stale copy. A first page view of campaign B
    # while the run was still sending campaign A's email claimed B and
    # mailed B's fan; the run then reached B and mailed them again.
    _run_patched(monkeypatch)
    uid = _account()
    yday = (date.today() - timedelta(days=1)).isoformat()
    a, a_slug = _campaign(uid, yday)
    b, b_slug = _campaign(uid, yday)
    fan_a, fan_b = _remind(uid, a), _remind(uid, b)
    other_slug = {fan_a: b_slug, fan_b: a_slug}
    sent, viewed = [], []

    def http(url, payload, headers):
        to = payload["to"][0]
        sent.append(to)
        if to in other_slug and not viewed:
            # the other campaign's first page view lands mid-run
            viewed.append(to)
            appmod.app.test_client().get("/l/" + other_slug[to])
        return {"id": "em"}

    monkeypatch.setattr(emailer, "_http", http)
    r = appmod.app.test_client().post("/reminders/run",
                                      headers={"X-Backup-Token": "tok-notify"})
    assert r.status_code == 200 and viewed
    assert sent.count(fan_a) == 1 and sent.count(fan_b) == 1, sent


def test_two_claims_on_one_campaign_only_one_wins():
    uid = _account()
    cid, _slug = _campaign(uid, (date.today() - timedelta(days=1)).isoformat())
    assert mls.claim_release_email(cid) is True
    assert mls.claim_release_email(cid) is False
    assert mls.get_campaign(cid)["settings"]["release_email_sent"] is True
    assert mls.get_campaign(cid)["settings"]["email_capture"] is True, "the rest is kept"


def test_a_view_long_after_release_sends_nothing_and_a_view_in_the_week_still_does(monkeypatch):
    # Review finding fans-real-2 (2026-09-23): the week's window was kept
    # only by the daily run, so the first page view of a release twenty
    # months old mailed its fans "out now". The window is kept where the
    # email is sent now, for both callers.
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    sent = []
    monkeypatch.setattr(emailer, "_http",
                        lambda url, payload, headers: sent.append(payload["to"][0]) or {"id": "em"})
    uid = _account()
    old, old_slug = _campaign(uid, (date.today() - timedelta(days=40)).isoformat())
    new, new_slug = _campaign(uid, (date.today() - timedelta(days=2)).isoformat())
    undated, undated_slug = _campaign(uid, "")
    who = {cid: _remind(uid, cid) for cid in (old, new, undated)}
    anon = appmod.app.test_client()
    for slug in (old_slug, new_slug, undated_slug):
        anon.get("/l/" + slug)
    assert who[old] not in sent, "forty days late is not a reminder"
    assert who[undated] not in sent, "no release date, no release day"
    assert sent.count(who[new]) == 1
    assert links_engine.release_email_window_open({"release_date": "2026-09-16"}, "2026-09-23")
    assert not links_engine.release_email_window_open({"release_date": "2026-09-15"}, "2026-09-23")
    assert not links_engine.release_email_window_open({"release_date": "2026-09-24"}, "2026-09-23")


def _mail_to(sent, email):
    return next(p for p in sent if p["to"] == [email])


def test_the_daily_runs_mail_points_at_the_public_address_not_the_schedulers_host(monkeypatch):
    # Review findings fans-real-3 and F6 (2026-09-23): the release-day
    # email built its listen link, its unsubscribe link and the
    # List-Unsubscribe header from request.url_root, so when the daily run
    # sent it they carried the scheduler's own host (and its scheme).
    import re
    _run_patched(monkeypatch)
    sent = []
    monkeypatch.setattr(emailer, "_http",
                        lambda url, payload, headers: sent.append(payload) or {"id": "em"})
    uid = _account()
    cid, slug = _campaign(uid, (date.today() - timedelta(days=1)).isoformat())
    fan = _remind(uid, cid)
    r = appmod.app.test_client().post("/reminders/run", base_url="http://10.0.0.5:10000",
                                      headers={"X-Backup-Token": "tok-notify"})
    assert r.status_code == 200
    msg = _mail_to(sent, fan)
    base = appmod.PUBLIC_BASE_URL
    assert base.startswith("https://")
    hrefs = re.findall(r'href="([^"]+)"', msg["html"])
    assert len(hrefs) == 2 and all(h.startswith(base + "/") for h in hrefs), hrefs
    assert hrefs[0].startswith(base + "/l/" + slug + "?f=")
    assert "10.0.0.5" not in msg["html"]
    assert msg["headers"]["List-Unsubscribe"].startswith("<" + base + "/unsubscribe/")


def test_a_resellers_artists_fans_get_the_resellers_address_and_name(monkeypatch):
    # fans-real-3: the sender name followed the request's tenant, and the
    # daily run has none, so a reseller's artist's fans got the platform's
    # name. It follows the artist's own reseller now, from either caller.
    import partner_store as ps
    _run_patched(monkeypatch)
    sent = []
    monkeypatch.setattr(emailer, "_http",
                        lambda url, payload, headers: sent.append(payload) or {"id": "em"})
    uid = _account()
    tag = "fx%s" % uuid.uuid4().hex[:6]
    domain = "fans.%s.example" % tag
    pid = ps.create_partner("Foxglove Records", slug=tag, domain=domain)
    ps.set_branding(pid, display_name="FOXGLOVE")
    assert ps.attach_user(pid, uid)
    cid, slug = _campaign(uid, (date.today() - timedelta(days=1)).isoformat())
    fan = _remind(uid, cid)
    appmod.app.test_client().post("/reminders/run", base_url="http://10.0.0.5:10000",
                                  headers={"X-Backup-Token": "tok-notify"})
    msg = _mail_to(sent, fan)
    assert msg["from"].startswith("FOXGLOVE <"), msg["from"]
    assert 'href="https://%s/l/%s?f=' % (domain, slug) in msg["html"]
    assert msg["headers"]["List-Unsubscribe"].startswith("<https://%s/unsubscribe/" % domain)

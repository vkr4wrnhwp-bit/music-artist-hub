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

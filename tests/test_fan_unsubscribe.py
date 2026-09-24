"""Every marketing email to a fan carries a way out, and every send list
honours it.

Until 2026-09-23 the release-day email had no unsubscribe link, the Fan
Club drop notice had none, nothing in the app could mark a fan do not
contact (links_store.suppress_fan had no caller), and neither send list
was filtered by suppression - while the Audience screen said unsubscribe
was "Needed before any send".

Now (fan_mail):
  * each release-day and drop email carries a signed, no-login unsubscribe
    link and List-Unsubscribe / List-Unsubscribe-Post headers (RFC 8058);
  * GET shows one button and changes nothing; POST unsubscribes, including
    the mail client's one-click POST;
  * the artist can mark a fan do not contact from the Fan CRM, and lift
    only that mark; the fan can undo only their own unsubscribe;
  * both send paths skip every suppressed address.
"""
import uuid
from datetime import date, timedelta

import app as appmod
import db as store
import email_provider as emailer
import fan_mail
import links_store as mls

PW = "unsub-pass-12345"
SECRET = appmod.app.config["SECRET_KEY"]
_YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def _account():
    email = "unsub-%s@example.net" % uuid.uuid4().hex[:10]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Unsub Artist", "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    c.post("/login", data={"email": email, "password": PW})
    c.post("/plan/switch", data={"plan": "pro"})
    return c, uid


def _released(uid, title="Out Now"):
    slug = "uns-%s" % uuid.uuid4().hex[:8]
    # Released yesterday: the release-day email goes only in the week after
    # release (links_engine.RELEASE_EMAIL_DAYS), so 2020-01-01 no longer sends.
    cid = mls.create_campaign(uid, slug, {"title": title, "release_date": _YESTERDAY,
                                          "settings": {"email_capture": True}})
    mls.update_campaign(cid, uid, {"status": "live"})
    mls.set_destinations(cid, [{"service_key": "spotify", "service_name": "Spotify",
                                "url": "https://open.spotify.com/track/U1", "sort_order": 0}])
    return cid, slug


def _consent(uid, cid, email):
    fid = mls.upsert_fan(uid, email, cid)
    mls.add_consent(fid, cid, "email_marketing", "yes")
    return fid


def _outbox(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    sent = []
    monkeypatch.setattr(emailer, "_http",
                        lambda url, payload, headers: sent.append(payload) or {"id": "em"})
    return sent


def _path(url):
    # Fan email links are built on the public address (app._fan_mail_base).
    return url.replace(appmod.PUBLIC_BASE_URL, "").replace("http://localhost", "")


def _unsub_link(html):
    return html.split("/unsubscribe/", 1)[1].split('"', 1)[0]


def test_the_release_email_carries_a_way_out_and_a_one_click_post_unsubscribes(monkeypatch):
    sent = _outbox(monkeypatch)
    _c, uid = _account()
    cid, slug = _released(uid)
    fan = "leaver-%s@example.net" % uuid.uuid4().hex[:6]
    _consent(uid, cid, fan)
    anon = appmod.app.test_client()
    anon.get("/l/" + slug)
    assert [p["to"] for p in sent] == [[fan]]
    msg = sent[0]
    url = msg["headers"]["List-Unsubscribe"].strip("<>")
    assert msg["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "/unsubscribe/" in url and url in msg["html"] and ">Unsubscribe</a>" in msg["html"]
    assert fan_mail.read_unsubscribe_token(SECRET, url.rsplit("/", 1)[1]) == (uid, fan)
    # A GET is a page with one button; it changes nothing (mail scanners).
    page = anon.get(_path(url))
    assert page.status_code == 200
    assert 'data-unsub-state="ask"' in page.get_data(as_text=True)
    assert mls.fan_by_email(uid, fan)["suppressed"] == ""
    # The mail client's own button: a POST whose body is the RFC 8058 line.
    r = anon.post(_path(url), data="List-Unsubscribe=One-Click",
                  content_type="application/x-www-form-urlencoded")
    assert r.status_code == 200 and 'data-unsub-state="out"' in r.get_data(as_text=True)
    assert mls.fan_by_email(uid, fan)["suppressed"] == fan_mail.UNSUBSCRIBED
    notes = [n for n in store.list_notifications(uid) if n["title"] == "A fan unsubscribed"]
    assert notes and fan in notes[0]["body"]
    # The next release email leaves them out and still reaches the others.
    cid2, slug2 = _released(uid, "Second One")
    _consent(uid, cid2, fan)
    stayer = "stayer-%s@example.net" % uuid.uuid4().hex[:6]
    _consent(uid, cid2, stayer)
    anon.get("/l/" + slug2)
    assert [p["to"] for p in sent[1:]] == [[stayer]]


def test_a_fan_can_subscribe_again_but_the_artist_cannot_lift_their_unsubscribe(monkeypatch):
    c, uid = _account()
    cid, _slug = _released(uid)
    fan = "back-%s@example.net" % uuid.uuid4().hex[:6]
    fid = _consent(uid, cid, fan)
    token = fan_mail.unsubscribe_token(SECRET, uid, fan)
    anon = appmod.app.test_client()
    anon.post("/unsubscribe/" + token, data={"action": "unsubscribe"})
    assert mls.get_fan(fid)["suppressed"] == fan_mail.UNSUBSCRIBED
    # The artist's CRM has no way to lift it, and the route refuses to.
    crm = c.get("/links/fans").get_data(as_text=True)
    row = crm.split(fan, 1)[1].split("</tr>", 1)[0]
    assert "Only they can undo it" in row and "contact-again" not in row
    c.post("/links/fans/%s/contact-again" % fid)
    assert mls.get_fan(fid)["suppressed"] == fan_mail.UNSUBSCRIBED
    # The fan can, from their own link.
    r = anon.post("/unsubscribe/" + token, data={"action": "resubscribe"})
    assert 'data-unsub-state="back"' in r.get_data(as_text=True)
    assert mls.get_fan(fid)["suppressed"] == ""


def test_the_artist_marks_do_not_contact_and_the_send_list_leaves_them_out(monkeypatch):
    sent = _outbox(monkeypatch)
    c, uid = _account()
    cid, slug = _released(uid)
    held = "held-%s@example.net" % uuid.uuid4().hex[:6]
    other = "other-%s@example.net" % uuid.uuid4().hex[:6]
    fid = _consent(uid, cid, held)
    _consent(uid, cid, other)
    page = c.get("/links/fans").get_data(as_text=True)
    assert "/links/fans/%s/do-not-contact" % fid in page
    r = c.post("/links/fans/%s/do-not-contact" % fid)
    assert r.status_code == 302 and r.headers["Location"].endswith("/links/fans?marked=1")
    assert mls.get_fan(fid)["suppressed"] == fan_mail.DO_NOT_CONTACT
    page = c.get("/links/fans?marked=1").get_data(as_text=True)
    assert "Marked do not contact." in page
    assert "/links/fans/%s/contact-again" % fid in page
    appmod.app.test_client().get("/l/" + slug)
    assert [p["to"] for p in sent] == [[other]]
    # The fan's own link cannot lift the artist's mark.
    token = fan_mail.unsubscribe_token(SECRET, uid, held)
    anon = appmod.app.test_client()
    r = anon.post("/unsubscribe/" + token, data={"action": "resubscribe"})
    assert 'data-unsub-state="held"' in r.get_data(as_text=True)
    assert mls.get_fan(fid)["suppressed"] == fan_mail.DO_NOT_CONTACT
    # The artist can.
    c.post("/links/fans/%s/contact-again" % fid)
    assert mls.get_fan(fid)["suppressed"] == ""
    # The Audience screen no longer says unsubscribe is missing.
    assert "In every fan email the app sends" in c.get("/fans").get_data(as_text=True)


def test_nobody_else_can_mark_or_lift_a_fan(monkeypatch):
    _c, uid = _account()
    cid, _slug = _released(uid)
    fid = _consent(uid, cid, "mine-%s@example.net" % uuid.uuid4().hex[:6])
    other, _other_uid = _account()
    assert other.post("/links/fans/%s/do-not-contact" % fid).status_code == 404
    assert mls.get_fan(fid)["suppressed"] == ""
    anon = appmod.app.test_client()
    r = anon.post("/links/fans/%s/do-not-contact" % fid)
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert mls.get_fan(fid)["suppressed"] == ""


def test_a_bad_or_foreign_key_token_changes_nothing():
    _c, uid = _account()
    cid, _slug = _released(uid)
    fan = "safe-%s@example.net" % uuid.uuid4().hex[:6]
    fid = _consent(uid, cid, fan)
    anon = appmod.app.test_client()
    good = fan_mail.unsubscribe_token(SECRET, uid, fan)
    for bad in (good[:-2] + "zz", fan_mail.unsubscribe_token("another-key", uid, fan),
                fan_mail.fan_token(SECRET, fid)):
        r = anon.post("/unsubscribe/" + bad, data={"action": "unsubscribe"})
        assert r.status_code == 404
        assert 'data-unsub-state="invalid"' in r.get_data(as_text=True)
    assert mls.get_fan(fid)["suppressed"] == ""


def test_fan_club_drops_carry_the_way_out_and_skip_who_took_it(monkeypatch):
    sent = _outbox(monkeypatch)
    c, uid = _account()
    store.save_fan_club(uid, "Inner Room", "b", 500, ["Early drops"], True)
    stay = "stay-%s@example.net" % uuid.uuid4().hex[:6]
    leave = "leave-%s@example.net" % uuid.uuid4().hex[:6]
    for e in (stay, leave):
        store.add_club_member(uid, e, "cus_%s" % e[:5], "sub_%s" % uuid.uuid4().hex[:8])
    r = c.post("/fan-club/drops", data={"title": "First Drop", "body": "Hi"})
    assert "notified=2" in r.headers["Location"] and "unsubscribed=0" in r.headers["Location"]
    by_to = {p["to"][0]: p for p in sent}
    assert set(by_to) == {stay, leave}
    msg = by_to[leave]
    assert msg["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "your membership stays as it is" in msg["html"]
    # These members have no CRM record (add_club_member writes none), so
    # the unsubscribe makes the row the suppression lives on, dated from
    # when they joined rather than counted as a new fan today.
    assert mls.fan_by_email(uid, leave) is None
    appmod.app.test_client().post("/unsubscribe/" + _unsub_link(msg["html"]),
                                  data={"action": "unsubscribe"})
    row = mls.fan_by_email(uid, leave)
    member = store.get_active_club_member(uid, leave)
    assert row["suppressed"] == fan_mail.UNSUBSCRIBED
    assert row["created"] == member["created"]
    assert member["status"] == "active", "unsubscribing is not cancelling"
    del sent[:]
    r = c.post("/fan-club/drops", data={"title": "Second Drop", "body": "Hi"})
    assert "notified=1" in r.headers["Location"] and "unsubscribed=1" in r.headers["Location"]
    assert [p["to"] for p in sent] == [[stay]]
    banner = c.get(_path(r.headers["Location"])).get_data(as_text=True)
    assert "1 member not emailed: unsubscribed or marked do not contact." in banner


def test_a_stranger_with_no_record_is_told_the_truth():
    _c, uid = _account()
    token = fan_mail.unsubscribe_token(SECRET, uid, "never-%s@example.net" % uuid.uuid4().hex[:6])
    anon = appmod.app.test_client()
    r = anon.post("/unsubscribe/" + token, data={"action": "unsubscribe"})
    assert r.status_code == 200 and 'data-unsub-state="out"' in r.get_data(as_text=True)

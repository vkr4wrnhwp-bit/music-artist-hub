"""VIP sold online.

The owner, 2026-09-07: "vip should have a link to purchase for the user
to share and we automate the emails etc for a percentage."

One public link per date. A fan picks a package, pays Stripe, and the
sale exists only once Stripe says the session is paid - claimed by the
webhook or the success redirect, whichever comes first, never twice.
The sale is mirrored into tour_vip so the door checks it in like any
package. Street Banker keeps VIP_PLATFORM_FEE_PCT of each sale, the
buyer gets a confirmation, the artist can email day-of details, and
every ledger says payouts are settled outside the app.
"""
import json
import re

import email_provider
import stripe_provider
import tour_os
import tour_store as ts
from tests.test_app import _stripe_sig
from tests.test_tour_date_page import _user, _tour, _show, _member_join, flask_app  # noqa: F401


def _offer(client, tid, sid, **over):
    data = {"name": "Soundcheck party", "price": "150", "capacity": "", "schedule_time": "16:30",
            "blurb": "Meet at the stage door.", "meet_greet": "1", "merch": "1"}
    data.update(over)
    r = client.post("/tours/%s/shows/%s/vip/offers/add" % (tid, sid), data=data)
    assert r.status_code == 302
    return next(o for o in ts.list_vip_offers(tid, sid) if o["name"] == data["name"])


def _selling(flask_app, **over):
    client, owner = _user(flask_app)
    tid = _tour(client)
    sid = _show(client, tid)
    offer = _offer(client, tid, sid, **over)
    token = ts.ensure_vip_link(tid, sid)
    return client, owner, tid, sid, offer, token


def _stripe_on(monkeypatch, calls):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_vip")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_stripetest")
    monkeypatch.setattr(stripe_provider, "_http", lambda path, fields: calls.append((path, fields)) or
                        {"id": "cs_vip_%d" % len(calls), "url": "https://checkout.stripe.com/c/vip"})


def _paid_session(session_id, offer, tid, sid, email="fan@example.net", name="Fan One", quantity=2):
    return {"id": session_id, "payment_status": "paid", "currency": "usd",
            "metadata": {"kind": "tour_vip", "tour_id": tid, "show_id": sid, "offer_id": offer["id"],
                         "email": email, "name": name, "quantity": str(quantity)}}


def test_the_link_is_public_and_honest_until_stripe_is_connected(flask_app, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    client, owner, tid, sid, offer, token = _selling(flask_app)
    page = client.get("/tours/%s/shows/%s?tab=vip" % (tid, sid)).get_data(as_text=True)
    assert 'value="https://street-banker.onrender.com/vip/%s"' % token in page, "the artist gets one link to share"
    assert 'sb-lamp sb-lamp--crit">not live</span>' in page and "No payment provider is connected" in page
    assert "Soundcheck party" in page and '<span class="to-fig"><span>sold</span><b>0</b></span>' in page
    assert '<details class="to-add" id="add-offer">' in page, "a package exists: the form waits"
    assert page.count('<span class="sb-lcd-v">—</span>') >= 4, "nothing sold: every window is a dash"
    anon = flask_app.test_client()
    pub = anon.get("/vip/%s" % token).get_data(as_text=True)
    assert "Soundcheck party" in pub and "USD 150.00" in pub and "meet at 4:30 PM" in pub.lower().replace("4:30 pm", "4:30 PM")
    assert 'id="closed"' in pub and "/buy" not in pub, "not live: no buy button, and it says why"
    assert "owed" not in pub and "Street Banker keeps" not in pub, "the fan never sees the ledger"
    r = anon.post("/vip/%s/buy" % token, data={"offer_id": offer["id"], "name": "Fan", "email": "f@example.net"})
    assert r.status_code == 302 and r.headers["Location"].endswith("?err=closed")
    assert anon.get("/vip/nope").status_code == 404


def test_a_fan_buys_and_the_sale_exists_once_stripe_says_paid(flask_app, monkeypatch):
    calls, mails = [], []
    _stripe_on(monkeypatch, calls)
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("EMAIL_FROM", "Street Banker <tour@example.net>")
    monkeypatch.setattr(email_provider, "send", lambda to, subject, html, attachments=None, reply_to=None, cc=None, text=None:
                        mails.append({"to": to, "subject": subject, "html": html, "reply_to": reply_to, "text": text}) or True)
    client, owner, tid, sid, offer, token = _selling(flask_app)
    anon = flask_app.test_client()
    r = anon.post("/vip/%s/buy" % token, data={"offer_id": offer["id"], "name": "Fan One", "email": "Fan@Example.net", "quantity": "2"})
    assert r.status_code == 303 and r.headers["Location"] == "https://checkout.stripe.com/c/vip"
    path, fields = calls[0]
    assert path == "/v1/checkout/sessions" and fields["mode"] == "payment"
    assert fields["line_items[0][price_data][unit_amount]"] == "15000" and fields["line_items[0][quantity]"] == "2"
    assert fields["metadata[kind]"] == "tour_vip" and fields["metadata[offer_id]"] == offer["id"]
    assert fields["success_url"].startswith("https://street-banker.onrender.com/vip/%s?paid=1" % token)
    assert not ts.list_vip_sales(tid), "a checkout is not a sale"
    # The success redirect trusts only what Stripe says about the session.
    monkeypatch.setattr(stripe_provider, "get_checkout_session",
                        lambda s: {"id": s, "payment_status": "unpaid", "metadata": {"kind": "tour_vip"}} if s == "cs_unpaid"
                        else _paid_session(s, offer, tid, sid))
    assert not ts.list_vip_sales(tid) and 'id="paid"' not in anon.get("/vip/%s?paid=1&session_id=cs_unpaid" % token).get_data(as_text=True)
    page = anon.get("/vip/%s?paid=1&session_id=cs_vip_1" % token).get_data(as_text=True)
    assert 'id="paid"' in page and "2 × Soundcheck party" in page and "on its way to fan@example.net" in page
    sales = ts.list_vip_sales(tid)
    assert len(sales) == 1
    sale = sales[0]
    assert (sale["quantity"], sale["unit_cents"], sale["gross_cents"], sale["fee_pct"], sale["fee_cents"], sale["net_cents"]) == (2, 15000, 30000, 10.0, 3000, 27000)
    assert sale["email"] == "fan@example.net" and sale["confirmation_sent"] == 1
    assert len(mails) == 1 and mails[0]["to"] == "fan@example.net" and mails[0]["reply_to"] == owner["email"]
    assert "Soundcheck party" in mails[0]["subject"] or "Your VIP package" in mails[0]["subject"]
    assert "Meet at 4:30 PM" in mails[0]["text"] and "Meet at the stage door." in mails[0]["text"]
    # The door sees it like any package; the artist sees the money.
    door = [v for v in ts.list_vip(tid, sid)]
    assert len(door) == 1 and door[0]["status"] == "sold" and door[0]["guest"] == "Fan One" and door[0]["quantity"] == 2
    artist = client.get("/tours/%s/shows/%s?tab=vip" % (tid, sid)).get_data(as_text=True)
    assert '<span class="sb-lcd-v">2</span>' in artist and '<span class="sb-lcd-v">300.00</span>' in artist
    assert '<span class="sb-lcd-v">30.00</span>' in artist and '<span class="sb-lcd-v">270.00</span>' in artist
    assert "Street Banker keeps 10%" in artist and "payouts are not automatic" in artist
    run = client.get("/tours/%s/vip" % tid).get_data(as_text=True)
    assert 'id="vip-online"' in run and '<span class="sb-lcd-v">270.00</span>' in run
    # Replays - the webhook after the redirect, the redirect twice - never record twice.
    payload = json.dumps({"type": "checkout.session.completed", "data": {"object": _paid_session("cs_vip_1", offer, tid, sid)}})
    assert anon.post("/webhooks/stripe", data=payload, headers={"Stripe-Signature": "t=1,v1=forged"},
                     content_type="application/json").status_code == 401
    anon.post("/webhooks/stripe", data=payload, headers=_stripe_sig(payload), content_type="application/json")
    anon.get("/vip/%s?paid=1&session_id=cs_vip_1" % token)
    assert len(ts.list_vip_sales(tid)) == 1 and len(ts.list_vip(tid, sid)) == 1 and len(mails) == 1
    # A second buyer arrives by webhook first: recorded, confirmed, once.
    p2 = json.dumps({"type": "checkout.session.completed",
                     "data": {"object": _paid_session("cs_vip_2", offer, tid, sid, email="two@example.net", name="Fan Two", quantity=1)}})
    anon.post("/webhooks/stripe", data=p2, headers=_stripe_sig(p2), content_type="application/json")
    assert len(ts.list_vip_sales(tid)) == 2 and len(mails) == 2 and mails[1]["to"] == "two@example.net"
    assert ts.get_vip_offer(tid, offer["id"])["sold"] == 3


def test_capacity_is_refused_not_oversold_and_the_fan_is_told(flask_app, monkeypatch):
    calls = []
    _stripe_on(monkeypatch, calls)
    client, owner, tid, sid, offer, token = _selling(flask_app, capacity="2")
    anon = flask_app.test_client()
    pub = anon.get("/vip/%s" % token).get_data(as_text=True)
    assert '<span class="to-fig"><span>left</span><b>2</b></span>' in pub and 'max="2"' in pub
    r = anon.post("/vip/%s/buy" % token, data={"offer_id": offer["id"], "name": "Fan", "email": "f@example.net", "quantity": "3"})
    assert r.headers["Location"].endswith("?err=sold_out") and not calls, "no session is opened for more than is left"
    monkeypatch.setattr(stripe_provider, "get_checkout_session", lambda s: _paid_session(s, offer, tid, sid, quantity=2))
    anon.get("/vip/%s?paid=1&session_id=cs_full" % token)
    pub = anon.get("/vip/%s" % token).get_data(as_text=True)
    assert 'sb-lamp sb-lamp--crit">sold out</span>' in pub and "/buy" not in pub
    assert "That package is sold out." in anon.get("/vip/%s?err=sold_out" % token).get_data(as_text=True)
    r = anon.post("/vip/%s/buy" % token, data={"offer_id": offer["id"], "name": "Fan", "email": "g@example.net"})
    assert r.headers["Location"].endswith("?err=sold_out") and not calls
    # Without a capacity nothing invents a remaining count.
    open_offer = _offer(client, tid, sid, name="Photo only", price="40")
    pub = anon.get("/vip/%s" % token).get_data(as_text=True)
    assert "Photo only" in pub and pub.count("<span>left</span>") == 1
    artist = client.get("/tours/%s/shows/%s?tab=vip" % (tid, sid)).get_data(as_text=True)
    assert 'sb-lamp sb-lamp--info">sold out</span>' in artist
    assert ('value="delete" aria-label="Remove %s"' % open_offer["name"]) in artist and 'aria-label="Remove Soundcheck party"' not in artist, "sold packages cannot be deleted"


def test_day_of_details_go_to_every_buyer_only_when_email_is_live(flask_app, monkeypatch):
    calls, mails = [], []
    _stripe_on(monkeypatch, calls)
    client, owner, tid, sid, offer, token = _selling(flask_app)
    monkeypatch.setattr(stripe_provider, "get_checkout_session", lambda s: _paid_session(s, offer, tid, sid, email="a@example.net", name="A", quantity=1))
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    anon = flask_app.test_client()
    page = anon.get("/vip/%s?paid=1&session_id=cs_a" % token).get_data(as_text=True)
    assert "no confirmation email went out from this deployment" in page
    sale = ts.list_vip_sales(tid)[0]
    assert sale["confirmation_sent"] == 0
    artist = client.get("/tours/%s/shows/%s?tab=vip" % (tid, sid)).get_data(as_text=True)
    assert 'sb-lamp sb-lamp--warn">emails off</span>' in artist and "Email day-of details to 1 buyer</button>" in artist
    r = client.post("/tours/%s/shows/%s/vip/dayof" % (tid, sid), data={"message": "Bring ID."})
    assert r.headers["Location"].endswith("&mail=off") and not mails
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("EMAIL_FROM", "Street Banker <tour@example.net>")
    monkeypatch.setattr(email_provider, "send", lambda to, subject, html, attachments=None, reply_to=None, cc=None, text=None:
                        mails.append({"to": to, "subject": subject, "text": text, "reply_to": reply_to}) or True)
    r = client.post("/tours/%s/shows/%s/vip/dayof" % (tid, sid), data={"message": "Bring ID."})
    assert r.headers["Location"].endswith("&dayof=1")
    assert len(mails) == 1 and mails[0]["to"] == "a@example.net" and "Show day" in mails[0]["subject"]
    assert "Bring ID." in mails[0]["text"] and "Meet at 4:30 PM" in mails[0]["text"] and mails[0]["reply_to"] == owner["email"]
    assert ts.list_vip_sales(tid)[0]["dayof_sent"]


def test_scopes_sandbox_and_the_fee_setting(flask_app, monkeypatch):
    calls = []
    _stripe_on(monkeypatch, calls)
    client, owner, tid, sid, offer, token = _selling(flask_app)
    viewer, _v = _member_join(flask_app, client, tid, ["view"], label="Viewer")
    assert viewer.post("/tours/%s/shows/%s/vip/offers/add" % (tid, sid), data={"name": "X", "price": "5"}).status_code == 403
    assert viewer.post("/tours/%s/shows/%s/vip/dayof" % (tid, sid)).status_code == 403
    assert client.post("/tours/%s/shows/%s/vip/offers/add" % (tid, sid), data={"name": "Free", "price": "0"}).headers["Location"].endswith("&offer=invalid")
    # The fee is a setting, clamped, and written on each sale at the time.
    monkeypatch.setenv("VIP_PLATFORM_FEE_PCT", "12.5")
    assert tour_os.vip_fee_pct() == 12.5
    monkeypatch.setenv("VIP_PLATFORM_FEE_PCT", "500")
    assert tour_os.vip_fee_pct() == 50.0
    monkeypatch.setenv("VIP_PLATFORM_FEE_PCT", "junk")
    assert tour_os.vip_fee_pct() == 10.0
    monkeypatch.setenv("VIP_PLATFORM_FEE_PCT", "15")
    monkeypatch.setattr(stripe_provider, "get_checkout_session", lambda s: _paid_session(s, offer, tid, sid, quantity=1))
    flask_app.test_client().get("/vip/%s?paid=1&session_id=cs_fee" % token)
    sale = ts.list_vip_sales(tid)[0]
    assert (sale["fee_pct"], sale["fee_cents"], sale["net_cents"]) == (15.0, 2250, 12750)
    assert "Street Banker keeps 15%" in client.get("/tours/%s/shows/%s?tab=vip" % (tid, sid)).get_data(as_text=True)
    # A sandbox never opens a checkout, whatever key is set.
    import sandbox
    monkeypatch.setattr(sandbox, "active", lambda: True)
    anon = flask_app.test_client()
    assert 'id="closed"' in anon.get("/vip/%s" % token).get_data(as_text=True)
    r = anon.post("/vip/%s/buy" % token, data={"offer_id": offer["id"], "name": "Fan", "email": "f@example.net"})
    assert r.headers["Location"].endswith("?err=closed") and not calls
    # Pausing takes a package off the public page without losing it.
    monkeypatch.setattr(sandbox, "active", lambda: False)
    client.post("/tours/%s/shows/%s/vip/offers/%s" % (tid, sid, offer["id"]), data={"action": "pause"})
    assert "Soundcheck party" not in anon.get("/vip/%s" % token).get_data(as_text=True)
    assert 'sb-lamp sb-lamp--warn">paused</span>' in client.get("/tours/%s/shows/%s?tab=vip" % (tid, sid)).get_data(as_text=True)
    r = anon.post("/vip/%s/buy" % token, data={"offer_id": offer["id"], "name": "Fan", "email": "f@example.net"})
    assert r.headers["Location"].endswith("?err=offer")


def test_the_sheet_and_the_worker_moved_on():
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "tour-os.css"), encoding="utf-8").read()
    assert ".to-date--offer" in css and ".to-buy" in css
    for rel in ("templates/tour/_shell.html", "templates/tour/_public.html"):
        src = open(os.path.join(here, rel), encoding="utf-8").read()
        assert int(re.search(r"tour-os\.css\?v=(\d+)", src).group(1)) >= 20, rel
    sw = open(os.path.join(here, "static", "js", "sw.js"), encoding="utf-8").read()
    assert int(re.search(r'VERSION = "sb-v(\d+)"', sw).group(1)) >= 202

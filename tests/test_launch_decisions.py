"""The owner's launch decisions, 2026-09-18, each held by a test.

  1 credit packs    "hide them until we know what the credits actually cost"
  2 Noise Lab       "soon as we need to finish it"
  4 VIP, fan clubs  "in a on off that i control (they need to email for details)"
  6 Pro             consulting at a member rate replaces "Consulting hours (with
                    ambassadors)"
  9 Ticketmaster    "off"
  Pulse             "make pulse only changable on pro accounts"
  MLC               "switch to mlc", "brainz off for customers"
Plus the shared demo logins stay out of Motion until every account has its
own Motion workspace.
"""
import uuid

import pytest

import app as appmod
import db as store
import plans
import sales_switch
import stripe_provider
import ticketmaster_provider as tm

PW = "launch-decisions-1"


def _client(plan="artist", email=None):
    email = email or "decide-%s@example.net" % uuid.uuid4().hex[:10]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Decide", "email": email, "password": PW})
    uid = store.get_user_by_email(email)["id"]
    store.set_user_plan(uid, plan)
    c.post("/login", data={"email": email, "password": PW})
    return c, uid


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("SUITE_SSO_SECRET", raising=False)


# --- 1 credit packs ----------------------------------------------------------

def test_credit_packs_are_off_sale_and_cannot_be_bought(monkeypatch):
    assert plans.CREDIT_PACKS_ON_SALE is False
    calls = []
    monkeypatch.setattr(stripe_provider, "configured", lambda: True)
    monkeypatch.setattr(stripe_provider, "create_credit_pack_checkout",
                        lambda *a, **k: calls.append(a) or {"url": "https://stripe.example/x"})
    c, _uid = _client("pro")
    page = c.get("/billing").get_data(as_text=True)
    assert "Credit packs are not on sale yet." in page and 'action="/billing/credits"' not in page
    r = c.post("/billing/credits", data={"pack": "pack-500"})
    assert r.status_code == 302 and "stripe.example" not in r.headers["Location"]
    assert calls == [], "no checkout was opened for a pack"


# --- 2 Noise Lab -------------------------------------------------------------

def test_noise_lab_is_marked_soon_and_its_door_says_so():
    c, _uid = _client("label")
    r = c.get("/suites/go/noise-lab")
    assert r.status_code == 200 and "Noise Lab is coming soon" in r.get_data(as_text=True)
    strip = c.get("/billing").get_data(as_text=True)
    assert "Noise Lab" in strip and "Soon" in strip
    import hubs
    assert "noise-lab" in hubs.suites_pending()


def test_the_owner_still_opens_noise_lab(monkeypatch):
    email = "owner-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setenv("OWNER_EMAILS", email)
    c, _uid = _client("label", email=email)
    assert c.get("/suites/go/noise-lab").status_code == 302


def test_the_shared_demo_login_does_not_enter_motion():
    demo = appmod.app.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    r = demo.get("/suites/go/motion")
    assert r.status_code == 200 and "Motion is not in the demo" in r.get_data(as_text=True)


# --- 4 online sales switch ---------------------------------------------------

def test_online_sales_start_off_and_a_fan_is_asked_to_email(monkeypatch):
    store.set_kv(sales_switch.KEY, "off")
    calls = []
    monkeypatch.setattr(stripe_provider, "configured", lambda: True)
    monkeypatch.setattr(stripe_provider, "create_club_checkout",
                        lambda *a, **k: calls.append(a) or {"url": "https://stripe.example/c"})
    c, uid = _client("artist")
    store.save_fan_club(uid, "Inner Circle", "Early music.", 500, ["Early access"], True)
    c.get("/epk")                                         # mints the slug
    slug = store.get_epk(uid)["slug"]
    anon = appmod.app.test_client()
    page = anon.get("/club/" + slug).get_data(as_text=True)
    assert sales_switch.CLOSED in page and 'action="/club/%s/join"' % slug not in page
    r = anon.post("/club/%s/join" % slug, data={"email": "fan@example.net"})
    assert r.status_code == 302 and calls == []
    assert "switched off" in c.get("/fan-club").get_data(as_text=True)


def test_only_the_owner_flips_the_switch(monkeypatch):
    store.set_kv(sales_switch.KEY, "off")
    c, _uid = _client("label")
    assert c.post("/admin/online-sales", data={"on": "1"}).status_code == 404
    assert not sales_switch.is_on()
    email = "owner-%s@example.net" % uuid.uuid4().hex[:8]
    monkeypatch.setenv("OWNER_EMAILS", email)
    owner, _ = _client("label", email=email)
    assert "Online sales are off." in owner.get("/settings").get_data(as_text=True)
    owner.post("/admin/online-sales", data={"on": "1"})
    assert sales_switch.is_on()
    owner.post("/admin/online-sales", data={"on": "0"})
    assert not sales_switch.is_on()


def test_vip_checkout_waits_for_the_switch(monkeypatch):
    import tour_store as ts
    store.set_kv(sales_switch.KEY, "off")
    calls = []
    monkeypatch.setattr(stripe_provider, "configured", lambda: True)
    monkeypatch.setattr(stripe_provider, "create_vip_checkout",
                        lambda *a, **k: calls.append(a) or {"url": "https://stripe.example/v"})
    _c, uid = _client("pro")
    tid = ts.create_tour(uid, {"name": "Spring run", "status": "planning"})
    sid = store.add_tour_show(uid, "2030-04-06", "The Room", "Chicago, IL", "")
    ts.attach_show(tid, sid, "")
    oid = ts.add_vip_offer(tid, uid, sid, {"name": "Meet", "price": "50", "capacity": "10"})
    token = ts.ensure_vip_link(tid, sid)
    anon = appmod.app.test_client()
    page = anon.get("/vip/" + token).get_data(as_text=True)
    assert sales_switch.CLOSED in page and 'action="/vip/%s/buy"' % token not in page
    r = anon.post("/vip/%s/buy" % token, data={"offer_id": oid, "name": "Fan", "email": "fan@example.net"})
    assert r.status_code == 302 and "err=closed" in r.headers["Location"] and calls == []


# --- 6 Pro plan line ---------------------------------------------------------

def test_pro_lists_consulting_at_a_member_rate_not_ambassadors():
    pro = [p for p in plans.PLANS if p[0] == "pro"][0]
    joined = " ".join(pro[4])
    assert "$50 for 30 minutes, $75 for an hour" in joined and "ambassador" not in joined.lower()


# --- 9 Ticketmaster ----------------------------------------------------------

def test_ticketmaster_is_off_on_a_deployed_service_until_switched_on(monkeypatch):
    monkeypatch.delenv("SANDBOX", raising=False)
    monkeypatch.setenv("TICKETMASTER_API_KEY", "tm-key")
    monkeypatch.delenv("TICKETMASTER_ENABLED", raising=False)
    monkeypatch.setenv("RENDER", "true")
    assert not tm.configured() and tm.switched_off()
    monkeypatch.setenv("TICKETMASTER_ENABLED", "on")
    assert tm.configured() and not tm.switched_off()
    monkeypatch.delenv("TICKETMASTER_ENABLED", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    assert tm.configured(), "a laptop follows the key, as the tests expect"


# --- Pulse -------------------------------------------------------------------

def _pick(c, artist_id):
    return c.post("/pulse/select", json={"id": artist_id, "name": "Artist " + artist_id})


def test_an_artist_account_picks_its_pulse_artist_once():
    c, uid = _client("artist")
    assert _pick(c, "sp-first").status_code == 200
    r = _pick(c, "sp-second")
    assert r.status_code == 402 and "comes with the Pro membership" in r.get_json()["error"]
    assert store.get_pulse_profile(uid)["artist_id"] == "sp-first"
    assert c.post("/pulse/clear").status_code == 402, "clearing is how a change starts"
    assert _pick(c, "sp-first").status_code == 200, "re-saving the same artist is fine"


@pytest.mark.parametrize("plan", ["pro", "label"])
def test_pro_and_label_change_it_freely(plan):
    c, uid = _client(plan)
    _pick(c, "sp-a")
    assert _pick(c, "sp-b").status_code == 200
    assert c.post("/pulse/clear").status_code == 200


# --- MLC instead of MusicBrainz ----------------------------------------------

def test_catalog_credits_come_from_the_mlc_and_musicbrainz_is_never_asked(monkeypatch):
    import music_apis
    import signal_providers as sp

    def refuse(*a, **k):
        raise AssertionError("MusicBrainz was called for a customer")
    monkeypatch.setattr(music_apis, "musicbrainz_credits", refuse)
    monkeypatch.setattr(appmod, "deezer_track_metadata",
                        lambda title, artist: {"isrc": "USAAA2600001", "label": "Indie"}, raising=False)

    class FakeMLC:
        def configured(self):
            return True

        def lookup(self, isrc=None, title=None, artist=None):
            assert isrc == "USAAA2600001"
            return {"works": [{"writers": [{"name": "Vera Sound", "ipi": "00012345678"}],
                               "publishers": [{"name": "Sound Songs", "collection_share": 100}]}]}
    monkeypatch.setattr(sp, "mlc_adapter", lambda: FakeMLC())
    c, _uid = _client("artist")
    r = c.post("/catalog/add", json={"title": "Night Drive", "artist": "Vera Sound"})
    meta = r.get_json()["meta"]
    assert meta["writers"] == ["Vera Sound"] and meta["publishers"] == ["Sound Songs"]
    assert meta["credits_source"] == "The MLC"

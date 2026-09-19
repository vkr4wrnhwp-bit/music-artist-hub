"""The owner's three rulings of 2026-09-19.

  "move tax center with statements"           Tax is a view of /statements.
  "Sync packs should go more in like releases  Sync packs sit with the
   because it's a sync pack. You're making a   releases, in the sidebar and
   product for sale."                          in the Releases room.
  "there's way too many one sheets... It just  The EPK is the one document;
   needs to be an EPK. The EPK goes to the     it saves to the Vault as a
   vault. And then from the vault you can      dated copy; the advance and
   send and attach it to the advance or mail   the pitch offer that copy;
   it out to press... download it."            the one-sheets redirect.
"""
import base64
import io
import os
import re
import uuid

import pytest

import app as appmod
import db as store
import email_provider as emailer
import hubs
import press_desk
import press_store
import rooms
import tour_store as ts

PASSWORD = "rulings-pass-1"


@pytest.fixture(scope="module")
def flask_app():
    return appmod.create_app()


def _artist(flask_app, plan="pro", label="Rulings Artist"):
    email = "rul-%s@example.net" % uuid.uuid4().hex[:8]
    client = flask_app.test_client()
    client.post("/signup", data={"name": label, "email": email, "password": PASSWORD})
    client.post("/login", data={"email": email, "password": PASSWORD})
    user = store.get_user_by_email(email)
    store.set_user_plan(user["id"], plan)
    return client, user


def _body(client, path, **kw):
    return client.get(path, **kw).get_data(as_text=True)


# --- Ruling 1: Tax is a view of Statements ---------------------------------

def test_the_old_tax_addresses_land_on_the_statements_tax_view(flask_app):
    client, _ = _artist(flask_app)
    for path in ("/tax", "/tax-center", "/tax/2026"):
        r = client.get(path)
        assert r.status_code == 301, path
        assert r.headers["Location"].endswith("/statements?view=tax"), path


def test_the_tax_view_files_the_uploaded_rows_by_year(flask_app):
    client, _ = _artist(flask_app)
    body = _body(client, "/statements?view=tax")
    assert "Upload a royalty statement" in body
    assert 'href="/statements?view=tax"' in body and 'aria-current="page"' in body
    csv = ("title,source,amount,period\n"
           "Song A,Spotify,700.00,2026-01\n"
           "Song A,Apple Music,50.25,2026-02\n"
           "Song B,Spotify,10.00,2025-11\n")
    client.post("/statements", data={"statement": (io.BytesIO(csv.encode()), "tax.csv")},
                content_type="multipart/form-data")
    body = _body(client, "/statements?view=tax")
    assert "2026" in body and "$750.25" in body
    assert "2025" in body and "$10.00" in body
    assert "Over $600" in body
    assert "not tax advice" in body
    # The desk view is still the desk, with the Tax tab beside it.
    desk = _body(client, "/statements")
    assert "Total Reported Income" not in desk and 'href="/statements?view=tax"' in desk


def test_nothing_links_to_the_old_tax_page():
    keys = {it[0] for _h, _n, _t, items in hubs.nav_hubs() for it in items}
    hrefs = {it[1] for _h, _n, _t, items in hubs.nav_hubs() for it in items}
    assert "tax" not in keys and "/tax" not in hrefs
    assert "tax" not in hubs.LIVE_KEYS
    cat = rooms.catalogue()
    assert cat["tax"][0] == "/statements?view=tax"
    assert rooms.room_for_key("tax") == "business"
    assert rooms.parent_of("tax") == "statements"
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in os.listdir(os.path.join(here, "templates")):
        if name.endswith(".html"):
            text = io.open(os.path.join(here, "templates", name), encoding="utf-8").read()
            assert 'href="/tax"' not in text, name


# --- Ruling 2: Sync packs sit with the releases ------------------------------

def test_sync_packs_is_a_releases_entry_not_a_deals_one():
    launch = next(items for hk, _n, _t, items in hubs.nav_hubs() if hk == "launch")
    keys = [it[0] for it in launch]
    assert "sync-packs" in keys
    assert keys.index("sync-packs") == keys.index("autopilot") + 1
    assert "sync-packs" in hubs.LIVE_KEYS
    assert rooms.room_for_key("sync-packs") == "releases"
    assert "sync-packs" not in rooms.EXTRA
    deals = next(it for _h, _n, _t, items in hubs.nav_hubs() for it in items if it[0] == "deals")
    assert "sync" not in deals[4].lower()


def test_sync_packs_keeps_its_address_and_wears_the_releases_strip(flask_app, monkeypatch):
    monkeypatch.setattr(rooms, "enabled", lambda: False)
    client, _ = _artist(flask_app)
    body = _body(client, "/sync/clearance-packs")
    assert 'href="/releases/autopilot"' in body and 'href="/releases/autopilot?view=ready"' in body
    strip = body.split('class="sb-subnav"', 1)[1].split("</nav>", 1)[0]
    assert "/deal-room" not in strip
    for path in ("/deal-room", "/sync/deal-simulator"):
        strip = _body(client, path).split('class="sb-subnav"', 1)[1].split("</nav>", 1)[0]
        assert "/sync/clearance-packs" not in strip, path
    autopilot = _body(client, "/releases/autopilot")
    strip = autopilot.split('class="sb-subnav"', 1)[1].split("</nav>", 1)[0]
    assert "/sync/clearance-packs" in strip


# --- Ruling 3: one document, the EPK -----------------------------------------

def test_both_one_sheets_redirect_to_the_press_kit(flask_app):
    client, _ = _artist(flask_app, plan="label")
    for path in ("/artist-profile", "/deal-room/onesheet"):
        r = client.get(path)
        assert r.status_code == 301, path
        assert r.headers["Location"].endswith("/epk"), path


def test_no_page_links_to_a_one_sheet_any_more(flask_app, monkeypatch):
    monkeypatch.setattr(rooms, "enabled", lambda: False)
    client, _ = _artist(flask_app, plan="label")
    for path in ("/epk", "/press-desk", "/deal-room", "/reports", "/trust-score",
                 "/certified", "/inbox", "/qualification", "/settings"):
        body = _body(client, path, follow_redirects=True)
        assert "/artist-profile" not in body, path
        assert "/deal-room/onesheet" not in body, path
        assert "One-Sheet" not in body and "One-sheet" not in body, path
    assert "onesheet" not in rooms.EXTRA
    assert not any(k == "onesheet" for _r, _n, _p, ks in rooms.ROOMS for k in ks)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert not os.path.exists(os.path.join(here, "templates", "artist_profile.html"))
    assert not os.path.exists(os.path.join(here, "templates", "deal_onesheet.html"))


def test_the_for_deals_section_is_private_and_carries_the_one_sheet_lines(flask_app):
    client, user = _artist(flask_app, plan="label")
    client.post("/tracks/add", data={"title": "Night Drive R3",
                                     "release_title": "Midnight EP",
                                     "release_date": "2026-10-30"})
    r = client.post("/epk/save", json={"sections_on": ["deals"],
                                       "deal_ask": "$40,000 advance",
                                       "deal_terms": "Two-year term, North America"})
    assert r.status_code == 200
    saved = store.get_epk(user["id"])["data"]
    assert saved["sections_on"] == ["deals"] and saved["deal_ask"] == "$40,000 advance"
    body = _body(client, "/epk")
    assert 'data-section="deals"' in body
    assert "Night Drive R3" in body                 # the artist's real track
    assert "$40,000 advance" in body and "North America" in body
    assert "not scored" in body                     # stream integrity, unscored
    assert "Nothing measured yet" not in body or "Night Drive R3" in body
    # Never on the public slug or the pitch link.
    slug = store.get_epk(user["id"])["slug"]
    public = flask_app.test_client().get("/epk/" + slug).get_data(as_text=True)
    assert "For deals" not in public and "$40,000 advance" not in public
    assert "Collected revenue" not in public


def test_an_empty_for_deals_section_prints_to_discuss_not_zeros(flask_app):
    client, _ = _artist(flask_app, plan="label")
    client.post("/epk/save", json={"sections_on": ["deals"]})
    body = _body(client, "/epk")
    section = body.split('data-section="deals"', 1)[1].split("</section>", 1)[0]
    assert "To discuss" in section
    assert "Nothing measured yet" in section
    for banned in ("$0.00", "0 of 0", "0/100"):
        assert banned not in section, banned


def test_save_to_vault_files_a_dated_web_page_each_time(flask_app):
    client, user = _artist(flask_app, plan="label")
    client.post("/epk/save", json={"bio": "Two sentences a journalist could lift.",
                                   "sections_on": ["deals"], "deal_ask": "Open to offers"})
    page = _body(client, "/epk")
    assert 'action="/epk/vault-save"' in page and "Save to Vault" in page
    r = client.post("/epk/vault-save")
    assert r.status_code == 302 and "/epk?saved=" in r.headers["Location"]
    kits = [v for v in store.list_vault_files(user["id"]) if v["kind"] == "press_kit"]
    assert len(kits) == 1
    assert re.fullmatch(r"Press kit, saved \d{4}-\d{2}-\d{2}", kits[0]["label"])
    assert kits[0]["path"].endswith(".html")
    # The kit page says plainly what was saved and why it is not a PDF.
    after = _body(client, r.headers["Location"])
    assert "as a web page" in after and "no PDF engine" in after
    # The copy is the document, self-contained, with the private section.
    copy = client.get(kits[0]["path"]).get_data(as_text=True)
    assert "Two sentences a journalist could lift." in copy
    assert "Open to offers" in copy and "For deals" in copy
    assert "<style>" in copy and "Saved from Street Banker" in copy
    # A second save is a second version, never an overwrite.
    client.post("/epk/vault-save")
    kits = [v for v in store.list_vault_files(user["id"]) if v["kind"] == "press_kit"]
    assert len(kits) == 2 and kits[0]["path"] != kits[1]["path"]
    # The Vault lists it as a document with a download, not a picture.
    vault = _body(client, "/vault")
    assert "Press kit, saved" in vault and "/vault/%s/download" % kits[0]["id"] in vault
    assert "Attach it to a tour advance" in vault
    dl = client.get("/vault/%s/download" % kits[0]["id"])
    assert dl.status_code == 200
    assert "attachment" in dl.headers.get("Content-Disposition", "")
    # Somebody else's id downloads nothing.
    other, _ = _artist(flask_app)
    assert other.get("/vault/%s/download" % kits[0]["id"]).status_code == 404


def _live_mail(monkeypatch):
    sent = []

    def fake_send(to, subject, html, attachments=None, reply_to=None, cc=None, text=None):
        sent.append({"to": to, "subject": subject, "html": html,
                     "attachments": attachments or []})
        return True
    monkeypatch.setattr(emailer, "configured", lambda: True)
    monkeypatch.setattr(emailer, "using_shared_test_sender", lambda: False)
    monkeypatch.setattr(emailer, "sender", lambda: "Street Banker <advance@example.net>")
    monkeypatch.setattr(emailer, "send", fake_send)
    return sent


def test_the_tour_advance_offers_the_saved_kit_and_attaches_it(flask_app, monkeypatch):
    sent = _live_mail(monkeypatch)
    client, user = _artist(flask_app, plan="label")
    client.post("/epk/save", json={"bio": "A kit for the venue."})
    client.post("/epk/vault-save")
    kit = next(v for v in store.list_vault_files(user["id"]) if v["kind"] == "press_kit")
    r = client.post("/tours/new", data={"name": "Rulings Run", "artist_name": "Rulings Artist",
                                        "start_date": "2030-05-01", "end_date": "2030-05-10",
                                        "home_tz": "America/New_York", "currency": "USD"})
    tid = r.headers["Location"].rstrip("/").split("/")[-1]
    r = client.post("/tours/%s/days/add" % tid,
                    data={"date": "2030-05-02", "kind": "show", "venue": "The Hall",
                          "city": "Austin, TX", "tz": "America/Chicago"})
    sid = r.headers["Location"].split("/shows/")[1].split("?")[0]
    page = _body(client, "/tours/%s/shows/%s?tab=send" % (tid, sid))
    assert 'value="kit:%s"' % kit["id"] in page
    assert "web page, from the Vault" in page
    r = client.post("/tours/%s/shows/%s/advance/send" % (tid, sid), data={
        "to": "prod@venue.example", "subject": "Advance", "body": "Hello",
        "attach": ["kit:" + kit["id"]]})
    assert r.status_code == 302 and "sent=1" in r.headers["Location"]
    assert len(sent) == 1
    names = [a["filename"] for a in sent[0]["attachments"]]
    assert any(n.endswith("-press-kit.html") for n in names), names
    blob = base64.b64decode(sent[0]["attachments"][0]["content"]).decode("utf-8")
    assert "A kit for the venue." in blob
    assert ts.list_advance_sends(tid, sid)[0]["attachments"] == names


def test_the_press_pitch_offers_the_saved_kit_as_link_and_attachment(flask_app, monkeypatch):
    sent = _live_mail(monkeypatch)
    monkeypatch.setattr(press_desk.emailer, "configured", lambda: True)
    monkeypatch.setattr(press_desk.emailer, "using_shared_test_sender", lambda: False)
    monkeypatch.setattr(press_desk.emailer, "send", emailer.send)
    client, user = _artist(flask_app, plan="label")
    client.post("/epk/save", json={"bio": "A kit for the press."})
    client.post("/epk/vault-save")
    kit = next(v for v in store.list_vault_files(user["id"]) if v["kind"] == "press_kit")
    client.post("/press-desk/contacts/new", data={"name": "Jane Writer", "outlet": "The Fader",
                                                  "email": "jane@fader.example"})
    client.post("/press-desk/announcements/new", data={"title": "New single", "headline": "New single out"})
    contact = press_store.list_contacts(user["id"])[0]
    release = press_store.list_releases(user["id"])[0]
    form = _body(client, "/press-desk/pitch/new")
    assert 'value="vault:%s"' % kit["id"] in form
    assert "nothing is called attached that was not sent" in form
    r = client.post("/press-desk/pitch/new", data={
        "release_id": release["id"], "contact_ids": [contact["id"]],
        "subject": "{title}", "body": "Hi {name}. Kit: {kit}. Story: {link}",
        "mode": "platform", "kit": "vault:" + kit["id"]})
    assert r.status_code == 302
    pitch_id = r.headers["Location"].rsplit("/", 1)[1]
    rec = press_store.pitch_recipients(user["id"], pitch_id)[0]
    assert kit["path"].rsplit("/", 1)[1] in rec["body"]           # the link
    page = _body(client, "/press-desk/pitch/" + pitch_id)
    assert "Press kit: Press kit, saved" in page and "attached file" in page
    client.post("/press-desk/pitch/%s/send" % pitch_id)
    assert len(sent) == 1
    assert sent[0]["attachments"] and sent[0]["attachments"][0]["filename"].endswith(".html")
    assert "A kit for the press." in base64.b64decode(sent[0]["attachments"][0]["content"]).decode("utf-8")


def test_a_pitch_from_your_own_inbox_offers_the_link_and_says_so(flask_app):
    client, user = _artist(flask_app, plan="label")
    client.post("/epk/vault-save")
    kit = next(v for v in store.list_vault_files(user["id"]) if v["kind"] == "press_kit")
    client.post("/press-desk/contacts/new", data={"name": "Sam", "outlet": "Pitchfork",
                                                  "email": "sam@pf.example"})
    client.post("/press-desk/announcements/new", data={"title": "EP", "headline": "EP out"})
    contact = press_store.list_contacts(user["id"])[0]
    release = press_store.list_releases(user["id"])[0]
    r = client.post("/press-desk/pitch/new", data={
        "release_id": release["id"], "contact_ids": [contact["id"]],
        "subject": "{title}", "body": "Kit: {kit}", "mode": "own_inbox",
        "kit": "vault:" + kit["id"]})
    page = _body(client, r.headers["Location"])
    assert "carries its link" in page and "attach the file yourself" in page
    assert "/vault/%s/download" % kit["id"] in page
    # No kit chosen: {kit} comes out blank rather than staying literal.
    r = client.post("/press-desk/pitch/new", data={
        "release_id": release["id"], "contact_ids": [contact["id"]],
        "subject": "{title}", "body": "Kit:{kit}.", "mode": "own_inbox", "kit": ""})
    rec = press_store.pitch_recipients(user["id"], r.headers["Location"].rsplit("/", 1)[1])[0]
    assert rec["body"] == "Kit:."

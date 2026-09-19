"""The Fans first-run page and the preview-then-confirm list import.

Owner, 2026-09-18: "do the fans empty state with the leftovers" and "yes
start the first-run page". The approved design promises "Nothing is added
to Fans until you confirm them" behind a "Preview the import" button, and
until this build the import saved the moment the form was sent. These lock
the promise:

  * a real account with nobody on file gets the first-run page at /fans;
    one fan, and it is the Audience screen; the demo showcase never sees it
  * the preview writes no ml_fans row, and its counts add up to the rows read
  * confirm writes exactly the previewed count, once; a second confirm, a
    stale id or another account's id writes nothing
  * cancel throws the draft away and writes nothing
  * consent and "where the permission came from" are required before a
    preview is even made
  * the Fan CRM's form goes through the same preview
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import db as store
import fan_list_import
import links_store as mls

# Six rows read: two good with a city, one good without, one unsubscribed,
# one duplicate, one bad address. One of the good ones is already on file
# in the tests that seed it.
MIXED = (
    "Email,Name,City,Country,Status\n"
    "ada@example.com,Ada Lovelace,Atlanta,US,subscribed\n"
    "grace@example.com,Grace Hopper,London,GB,subscribed\n"
    "nowhere@example.com,No Place,,,subscribed\n"
    "left@example.com,Someone Gone,Paris,FR,unsubscribed\n"
    "ada@example.com,Ada Again,Atlanta,US,subscribed\n"
    "not-an-address,Who,,,subscribed\n"
)


@pytest.fixture(scope="module")
def application():
    import app as appmod
    return appmod.app


def _account(application):
    email = "fr-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email, "password": "fr-pass-123"})
    client.post("/login", data={"email": email, "password": "fr-pass-123"})
    return client, store.get_user_by_email(email)


def _fan_rows(user_id):
    with store.get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM ml_fans WHERE user_id = ?", (user_id,)).fetchone()[0]


def _preview(client, text=MIXED, origin="fans", **extra):
    data = {"text": text, "source": "Mailchimp list, merch table 2025", "confirm": "1",
            "origin": origin}
    data.update(extra)
    return client.post("/fans/import/preview", data=data)


def _draft_id(client):
    html = client.get("/fans/import").get_data(as_text=True)
    return re.search(r'name="draft_id" value="([0-9a-f]+)"', html).group(1)


def _main(html):
    """The page's own body, without the shell around it."""
    i = html.find('class="au ')
    j = html.find("fans-audience.js", i)
    if j < 0:
        j = html.find("</main>", i)
    return html[i:j if j > 0 else None] if i >= 0 else html


# --- which screen /fans is ----------------------------------------------------

def test_a_new_real_account_gets_the_first_run_page(application):
    client, _user = _account(application)
    main = _main(client.get("/fans").get_data(as_text=True))
    assert "Your audience already exists. Bring it in." in main
    # Under the shared fans header: the plate and the three tabs.
    assert 'id="sb-plate-title">Audience' in main
    assert re.search(r'href="/links/fans"[^>]*>Fan CRM', main)
    # The approved sections.
    for piece in ("Fans on file", "Last import", "Engagement scores",
                  "Import the list you already have", "Choose a file", "Paste a list",
                  "These people agreed to hear from me, and I hold the record of it.",
                  "Where the permission came from", "Preview the import",
                  "No list yet", "What the file needs", "What happens after that"):
        assert piece in main, piece
    # No invented numbers: nothing measured reads as zero.
    assert ">None yet<" in main and ">Not measured<" in main
    assert not re.search(r'data-fr-stat="total">0<', main)
    # The Audience screen's empty panels are not drawn.
    assert "au-tiles" not in main and "Fan Geography" not in main
    # One h1, and it is the plate's.
    assert len(re.findall(r"<h1\b", main)) == 1


def test_the_row_limit_on_the_page_is_the_parsers(application):
    client, _user = _account(application)
    main = _main(client.get("/fans").get_data(as_text=True))
    assert "Up to %s rows a file" % "{:,}".format(fan_list_import.MAX_ROWS) in main


def test_consent_and_its_source_are_required_on_the_form(application):
    client, _user = _account(application)
    main = _main(client.get("/fans").get_data(as_text=True))
    form = re.search(r'<form id="import".*?</form>', main, re.S).group(0)
    assert 'action="/fans/import/preview"' in form
    assert re.search(r'<input type="checkbox"[^>]*name="confirm"[^>]*required', form)
    assert re.search(r'<input[^>]*name="source"[^>]*required', form)


def test_the_first_run_links_all_resolve(application):
    client, _user = _account(application)
    main = _main(client.get("/fans").get_data(as_text=True))
    for href in set(re.findall(r'href="(/[^"#]*)"', main)):
        if href.startswith("/static/"):
            continue
        assert client.get(href).status_code < 400, href
    for src in re.findall(r'src="(/static/img/[^"]+)"', main):
        assert client.get(src).status_code == 200, src


def test_one_fan_and_it_is_the_audience_screen(application):
    client, user = _account(application)
    mls.upsert_fan(user["id"], "one-%s@example.org" % uuid.uuid4().hex[:6], None)
    main = _main(client.get("/fans").get_data(as_text=True))
    assert "au-tiles" in main and "Your audience already exists" not in main


def test_the_showcase_never_gets_the_first_run_page(application):
    demo = application.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    main = _main(demo.get("/fans").get_data(as_text=True))
    assert "Showcase." in main and "Your audience already exists" not in main
    anon = application.test_client().get("/fans").get_data(as_text=True)
    assert "Your audience already exists" not in anon


# --- the preview writes nothing -----------------------------------------------

def test_the_preview_writes_no_fan_and_its_counts_add_up(application):
    client, user = _account(application)
    r = _preview(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/fans/import")
    assert _fan_rows(user["id"]) == 0, "a preview must not write a fan"
    html = _main(client.get("/fans/import").get_data(as_text=True))
    assert _fan_rows(user["id"]) == 0
    assert 'data-fr-prev="new">3<' in html
    assert 'data-fr-prev="already">0<' in html
    assert 'data-fr-prev="skipped">3<' in html
    assert re.search(r'data-fr-prev="located">2 <small>of 3', html)
    for why in ("Their list says unsubscribed", "The same address twice in this file",
                "Not a readable email address"):
        assert why in html, why
    assert re.search(r"Rows read</span><span class=\"n\">6<", html)
    d = store.get_fan_import_draft(user["id"])
    s = d["summary"]
    assert s["new"] + s["already_here"] + sum(s["reasons"].values()) == s["read"] == 6
    # A masked sample with the place as the file gave it.
    assert "a***@example.com" in html and "ada@example.com" not in html
    assert "Atlanta, US" in html and "Not in the file" in html
    assert "Nothing is added yet" in html
    assert "Confirm and import 3" in html


def test_the_preview_is_held_server_side_not_in_the_cookie(application):
    client, user = _account(application)
    _preview(client)
    with client.session_transaction() as sess:
        assert "grace@example.com" not in repr(dict(sess))
    d = store.get_fan_import_draft(user["id"])
    assert d["user_id"] == user["id"] and len(d["rows"]) == 3


def test_no_consent_no_preview(application):
    client, user = _account(application)
    r = client.post("/fans/import/preview", data={"text": MIXED, "source": "Mailchimp", "origin": "fans"})
    assert "imp=needs-source" in r.headers["Location"]
    r = client.post("/fans/import/preview", data={"text": MIXED, "confirm": "1", "origin": "fans"})
    assert "imp=needs-source" in r.headers["Location"]
    assert store.get_fan_import_draft(user["id"]) is None and _fan_rows(user["id"]) == 0
    main = _main(client.get(r.headers["Location"]).get_data(as_text=True))
    assert "Say where these people gave you permission" in main


def test_a_file_with_no_address_column_makes_no_preview(application):
    client, user = _account(application)
    r = _preview(client, text="Name,Phone\nAda,555\n")
    assert "imp=no-address" in r.headers["Location"]
    assert store.get_fan_import_draft(user["id"]) is None


# --- confirm writes exactly the preview, once ---------------------------------

def test_confirm_writes_exactly_the_previewed_count_and_lands_on_fans(application):
    client, user = _account(application)
    _preview(client)
    draft_id = _draft_id(client)
    r = client.post("/fans/import/confirm", data={"draft_id": draft_id})
    assert r.status_code == 302 and "/fans" in r.headers["Location"]
    assert "/links/" not in r.headers["Location"]
    assert _fan_rows(user["id"]) == 3
    ada = mls.fan_by_email(user["id"], "ada@example.com")
    assert (ada["city"], ada["country"]) == ("Atlanta", "US")
    assert mls.find_consent(ada["id"], "list_import")
    assert mls.fan_by_email(user["id"], "left@example.com") is None
    # The draft is gone and the import is recorded with the preview's counts.
    assert store.get_fan_import_draft(user["id"]) is None
    last = store.latest_fan_import(user["id"], "list")
    assert last["summary"]["new"] == 3 and last["summary"]["read"] == 6
    # /fans is now the Audience screen.
    main = _main(client.get(r.headers["Location"]).get_data(as_text=True))
    assert "au-tiles" in main and "Your audience already exists" not in main


def test_a_second_confirm_of_the_same_draft_does_nothing(application):
    client, user = _account(application)
    _preview(client)
    draft_id = _draft_id(client)
    client.post("/fans/import/confirm", data={"draft_id": draft_id})
    mls.delete_fan(user["id"], mls.fan_by_email(user["id"], "grace@example.com")["id"])
    before = _fan_rows(user["id"])
    r = client.post("/fans/import/confirm", data={"draft_id": draft_id})
    assert "imp=stale" in r.headers["Location"]
    assert _fan_rows(user["id"]) == before == 2, "a replayed confirm must not re-file anybody"
    with store.get_db() as conn:
        n = conn.execute("SELECT COUNT(*) FROM fan_imports WHERE user_id = ? AND source = 'list'",
                         (user["id"],)).fetchone()[0]
    assert n == 1


def test_another_account_cannot_confirm_or_cancel_the_draft(application):
    owner, owner_user = _account(application)
    _preview(owner)
    draft_id = _draft_id(owner)
    other, other_user = _account(application)
    r = other.post("/fans/import/confirm", data={"draft_id": draft_id})
    assert "imp=stale" in r.headers["Location"]
    other.post("/fans/import/cancel", data={"draft_id": draft_id})
    assert _fan_rows(other_user["id"]) == 0 and _fan_rows(owner_user["id"]) == 0
    assert store.get_fan_import_draft(owner_user["id"], draft_id) is not None, "still the owner's"
    # Signed out, nothing either.
    anon = application.test_client()
    assert anon.post("/fans/import/confirm", data={"draft_id": draft_id}).status_code in (302, 303)
    assert _fan_rows(owner_user["id"]) == 0
    owner.post("/fans/import/confirm", data={"draft_id": draft_id})
    assert _fan_rows(owner_user["id"]) == 3


def test_a_stale_draft_is_refused(application):
    client, user = _account(application)
    _preview(client)
    draft_id = _draft_id(client)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    with store.get_db() as conn:
        conn.execute("UPDATE fan_import_drafts SET expires = ? WHERE id = ?", (past, draft_id))
    r = client.post("/fans/import/confirm", data={"draft_id": draft_id})
    assert "imp=stale" in r.headers["Location"] and _fan_rows(user["id"]) == 0
    assert client.get("/fans/import").status_code == 302


def test_one_live_draft_per_user(application):
    client, user = _account(application)
    _preview(client)
    first = _draft_id(client)
    _preview(client, text="Email\nzed@example.com\n")
    second = _draft_id(client)
    assert first != second
    r = client.post("/fans/import/confirm", data={"draft_id": first})
    assert "imp=stale" in r.headers["Location"] and _fan_rows(user["id"]) == 0
    with store.get_db() as conn:
        n = conn.execute("SELECT COUNT(*) FROM fan_import_drafts WHERE user_id = ?",
                         (user["id"],)).fetchone()[0]
    assert n == 1


def test_confirm_files_what_was_previewed_even_if_a_fan_arrives_between(application):
    client, user = _account(application)
    _preview(client)
    draft_id = _draft_id(client)
    # Grace gives her email on a smart link while the preview is open.
    grace_id = mls.upsert_fan(user["id"], "grace@example.com", None, "Grace")
    mls.add_consent(grace_id, None, "smart_link", "Gave it on a smart link")
    client.post("/fans/import/confirm", data={"draft_id": draft_id})
    assert _fan_rows(user["id"]) == 3, "the previewed three, not four and not two"
    # Review 2026-09-18: she used to be stamped "imported" with a list_import
    # consent laid over the way she really arrived, and the record said 3
    # added when 2 were. She is treated as already here now.
    grace = mls.fan_by_email(user["id"], "grace@example.com")
    assert "imported" not in grace["tags"]
    assert [c["consent_type"] for c in mls.list_consents(grace["id"])] == ["smart_link"]
    assert (grace["city"], grace["country"]) == ("London", "GB"), "her missing place is filled"
    done = store.latest_fan_import(user["id"], "list")["summary"]
    assert done["new"] == 2 and done["already_here"] == 1 and done["arrived_since_preview"] == 1
    assert done["new"] + done["already_here"] + done["skipped"] == done["read"]


def test_cancel_deletes_the_draft_and_writes_nothing(application):
    client, user = _account(application)
    _preview(client)
    draft_id = _draft_id(client)
    r = client.post("/fans/import/cancel", data={"draft_id": draft_id})
    assert r.status_code == 302 and r.headers["Location"].endswith("/fans")
    assert store.get_fan_import_draft(user["id"]) is None and _fan_rows(user["id"]) == 0


def test_already_on_file_is_counted_and_left_alone(application):
    client, user = _account(application)
    mls.upsert_fan(user["id"], "ada@example.com", None, "Ada")
    _preview(client)
    html = _main(client.get("/fans/import").get_data(as_text=True))
    assert 'data-fr-prev="new">2<' in html and 'data-fr-prev="already">1<' in html
    client.post("/fans/import/confirm", data={"draft_id": _draft_id(client)})
    assert _fan_rows(user["id"]) == 3
    ada = mls.fan_by_email(user["id"], "ada@example.com")
    assert (ada["city"], ada["country"]) == ("Atlanta", "US"), "a gap in place is filled"
    assert not mls.find_consent(ada["id"], "list_import"), "an existing fan's consent is not rewritten"


def test_a_place_already_on_file_is_never_replaced(application):
    """Review 2026-09-18: the preview said "left as they are" and confirm
    replaced Lyon with Berlin. A place the record holds is kept; only a
    missing one is filled."""
    client, user = _account(application)
    ada_id = mls.upsert_fan(user["id"], "ada@example.com", None, "Ada")
    mls.set_fan_place(ada_id, "FR", "Lyon")
    grace_id = mls.upsert_fan(user["id"], "grace@example.com", None, "Grace")
    mls.set_fan_place(grace_id, "GB", "")  # a country, no city: the city is a gap
    _preview(client)
    assert store.get_fan_import_draft(user["id"])["summary"]["places_to_fill"] == 1
    html = _main(client.get("/fans/import").get_data(as_text=True))
    assert "A place a record already holds is kept" in html
    client.post("/fans/import/confirm", data={"draft_id": _draft_id(client)})
    ada = mls.fan_by_email(user["id"], "ada@example.com")
    assert (ada["city"], ada["country"]) == ("Lyon", "FR")
    grace = mls.fan_by_email(user["id"], "grace@example.com")
    assert (grace["city"], grace["country"]) == ("London", "GB")
    assert store.latest_fan_import(user["id"], "list")["summary"]["places_filled"] == 1


def test_nothing_to_change_offers_no_confirm(application):
    """Review 2026-09-18: a file whose only rows are already on file, with
    the place the record already holds, showed "Confirm: fill in places"
    and recorded an import that changed nothing."""
    client, user = _account(application)
    fan_id = mls.upsert_fan(user["id"], "same@example.com", None, "Same")
    mls.set_fan_place(fan_id, "US", "Atlanta")
    _preview(client, text="email,city,country\nsame@example.com,Atlanta,US\n")
    html = _main(client.get("/fans/import").get_data(as_text=True))
    assert 'action="/fans/import/confirm"' not in html
    assert "Nothing in this list would change your records" in html


def test_the_consent_sentence_is_dated_the_day_the_box_was_ticked(application):
    """Review 2026-09-18: the preview quoted today's date and confirm wrote
    the date of confirming, which differ across midnight. Both now read the
    draft's own date."""
    client, user = _account(application)
    _preview(client)
    draft_id = _draft_id(client)
    with store.get_db() as conn:
        conn.execute("UPDATE fan_import_drafts SET created = ? WHERE id = ?",
                     ("2026-01-02T23:59:00+00:00", draft_id))
    html = _main(client.get("/fans/import").get_data(as_text=True))
    assert "confirmed on 2026-01-02" in html
    client.post("/fans/import/confirm", data={"draft_id": draft_id})
    ada = mls.fan_by_email(user["id"], "ada@example.com")
    assert "confirmed on 2026-01-02" in mls.find_consent(ada["id"], "list_import")["consent_text"]


def test_confirm_is_one_transaction(application):
    """Review 2026-09-18: confirm deleted the draft and then filed row by
    row, so a request killed partway left half a list and no draft. Now a
    failure part way through writes nothing and leaves the draft."""
    client, user = _account(application)
    _preview(client)
    draft_id = _draft_id(client)

    def boom(draft):
        raise RuntimeError("killed")
    with pytest.raises(RuntimeError):
        mls.confirm_list_import(user["id"], draft_id, boom)
    assert _fan_rows(user["id"]) == 0
    assert store.get_fan_import_draft(user["id"], draft_id) is not None
    assert store.latest_fan_import(user["id"], "list") is None


def test_a_big_list_confirms_quickly():
    """The page says up to MAX_ROWS a file. Filing is one transaction now;
    5,000 rows must take seconds, not the minutes the per-row loop took
    (300 rows took 42s in review)."""
    import time
    user_id = "big-%s" % uuid.uuid4().hex[:8]
    text = "email,city\n" + "".join("fan%05d@example.com,Leeds\n" % i for i in range(5000))
    parsed = fan_list_import.parse(text)
    summary = fan_list_import.preview(parsed, [])
    draft_id = store.put_fan_import_draft(user_id, "fans", "Test", False, summary,
                                          fan_list_import.draft_rows(parsed, {}))
    t = time.time()
    done = mls.confirm_list_import(user_id, draft_id, lambda d: "note")
    assert done["new"] == 5000 and _fan_rows(user_id) == 5000
    assert time.time() - t < 20


def test_the_showcase_cannot_preview_or_confirm(application):
    """Review 2026-09-18: the demo session could preview and confirm, which
    wrote real rows onto the demo account."""
    demo = application.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    demo_user = store.get_user_by_email("demo@streetbanker.io")
    before = _fan_rows(demo_user["id"])
    r = _preview(demo)
    assert r.status_code == 302 and r.headers["Location"].endswith("/fans")
    assert store.get_fan_import_draft(demo_user["id"]) is None
    for path in ("/fans/import/confirm", "/fans/import/cancel"):
        r = demo.post(path, data={"draft_id": "x"})
        assert r.headers["Location"].endswith("/fans")
    assert demo.get("/fans/import").headers["Location"].endswith("/fans")
    assert _fan_rows(demo_user["id"]) == before


def test_an_expired_draft_is_removed_not_just_ignored(application):
    client, user = _account(application)
    _preview(client)
    draft_id = _draft_id(client)
    with store.get_db() as conn:
        conn.execute("UPDATE fan_import_drafts SET expires = ? WHERE id = ?",
                     ("2000-01-01T00:00:00+00:00", draft_id))
    assert store.get_fan_import_draft(user["id"]) is None
    with store.get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM fan_import_drafts WHERE id = ?",
                            (draft_id,)).fetchone()[0] == 0


def test_a_long_permission_source_wraps(application):
    """Review 2026-09-18: a pasted signup URL with no spaces pushed the
    preview sideways at 390px. User-supplied text wraps anywhere."""
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css = open(os.path.join(here, "static", "css", "fans-first-run.css"), encoding="utf-8").read()
    rule = re.search(r"([^{}]*)\{\s*overflow-wrap:\s*anywhere;\s*\}", css)
    assert rule and ".fr-hero-sub" in rule.group(1) and ".fr-quote" in rule.group(1)
    client, user = _account(application)
    url = "https://mailchimp.com/lists/audience/export/" + "a" * 70
    _preview(client, source=url)
    html = _main(client.get("/fans/import").get_data(as_text=True))
    assert url in html


# --- the Fan CRM goes the same way --------------------------------------------

def test_the_crm_form_goes_through_the_same_preview(application):
    client, user = _account(application)
    mls.upsert_fan(user["id"], "seed-%s@example.org" % uuid.uuid4().hex[:6], None)
    crm = client.get("/links/fans").get_data(as_text=True)
    form = re.search(r'<form method="post" action="/fans/import/preview".*?</form>', crm, re.S).group(0)
    assert 'name="origin" value="crm"' in form and "Preview the import" in form
    assert "Nothing is added to Fans until you confirm them" in crm
    before = _fan_rows(user["id"])
    _preview(client, origin="crm")
    assert _fan_rows(user["id"]) == before
    html = _main(client.get("/fans/import").get_data(as_text=True))
    assert re.search(r'is-on" href="/links/fans"\s*aria-current="page">Fan CRM', html)
    r = client.post("/fans/import/confirm", data={"draft_id": _draft_id(client)})
    assert r.headers["Location"].endswith("/links/fans?imp=done#import")
    assert _fan_rows(user["id"]) == before + 3
    done = client.get("/links/fans?imp=done").get_data(as_text=True)
    assert "3</strong> added" in done


def test_the_old_import_url_previews_too(application):
    client, user = _account(application)
    r = client.post("/links/fans/import/list",
                    data={"text": MIXED, "source": "Old form", "confirm": "1"})
    assert r.headers["Location"].endswith("/fans/import")
    assert _fan_rows(user["id"]) == 0
    assert store.get_fan_import_draft(user["id"])["origin"] == "crm"


def test_the_first_run_page_says_only_what_exists(application):
    """Review 2026-09-18: "What happens after that" promised sending, open
    tracking and journeys, none of which exist. It now describes smart-link
    scoring and says sending is not in this build (a departure from the
    approved mockup's copy, flagged to the owner). The chip and the preview
    use one name for one state, and the page has one gold primary."""
    client, _ = _account(application)
    html = _main(client.get("/fans").get_data(as_text=True))
    for gone in ("You send once", "journeys", "Whoever opens"):
        assert gone not in html
    assert "Sending from Fans is not in this build" in html
    assert "Already on file" in html and "Already here" not in html
    assert html.count("fr-btn--primary") == 1
    assert 'href="#import"' not in html, "the header's jump link is not drawn here"
    assert "Import subscribed Shopify customers" not in html or "no preview" in html


def test_the_mask_shows_only_the_first_letter():
    assert fan_list_import.mask_email("ada@example.com") == "a***@example.com"
    assert fan_list_import.mask_email("") == "***"

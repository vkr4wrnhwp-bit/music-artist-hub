"""The Audience screen (/fans), built from the owner's approved mockup
(static/_mock_audience.html, 2026-09-18) and filled only from the account's
own records.

What these lock:
  * a fresh account shows no invented number: counts are 0, ratios say
    "Not measured yet", and nothing from the showcase leaks in
  * the counts add up: contactable + suppressed = on file, the region rows
    sum to the contactable count, the funnel nests
  * the selection export is the ticked places' contactable fans, never a
    suppressed one
  * every tab, link and form on the screen answers under 400 for the account
  * the showcase reaches the demo account only, and is labelled there
  * nothing on the screen sends email
"""
import csv
import io
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

import db as store
import fan_audience
import links_store as mls


@pytest.fixture(scope="module")
def application():
    import app as appmod
    return appmod.app


def _account(application, email=None):
    email = email or "au-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Artist", "email": email, "password": "au-pass-123"})
    client.post("/login", data={"email": email, "password": "au-pass-123"})
    with application.app_context():
        return client, store.get_user_by_email(email)


def _import(client, rows):
    lines = ["email,name,city,country"] + ["%s,%s,%s,%s" % r for r in rows]
    return client.post("/links/fans/import/list", data={
        "text": "\n".join(lines), "source": "Mailchimp, shows 2025", "confirm": "1"})


def _populated(application):
    client, user = _account(application)
    tag = uuid.uuid4().hex[:6]
    rows = ([("a%d-%s@example.org" % (i, tag), "Fan A%d" % i, "Atlanta", "US") for i in range(6)]
            + [("l%d-%s@example.org" % (i, tag), "Fan L%d" % i, "London", "GB") for i in range(3)]
            + [("n%d-%s@example.org" % (i, tag), "", "", "") for i in range(4)])
    assert _import(client, rows).status_code == 302
    with application.app_context():
        mls.suppress_fan(user["id"], "a0-%s@example.org" % tag, "unsubscribed")
        mls.suppress_fan(user["id"], "n0-%s@example.org" % tag, "bounced")
        store.add_tour_show(user["id"], (date.today() + timedelta(days=12)).isoformat(),
                            "The Masquerade", "Atlanta", "")
    return client, user, tag


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _main(html):
    """The page's own body, without the shell around it."""
    i = html.find('class="au ')
    j = html.find("fans-audience.js", i)
    return html[i:j if j > 0 else None] if i >= 0 else html


# --- a fresh account ---------------------------------------------------------

def test_a_fresh_account_shows_no_invented_numbers(application):
    client, _user = _account(application)
    html = client.get("/fans").get_data(as_text=True)
    main = _main(html)
    assert "No fans captured yet" in main and "smart link" in main.lower()
    for stat in ("total", "contactable", "never"):
        assert re.search(r'data-au-stat="%s">0<' % stat, main), stat
    assert "Not measured yet" in main
    assert "Showcase" not in main
    # No figure other than zero appears in the tiles and panels: no
    # percentages, no trend chip, no dot on the map, no funnel.
    text = _text(main)
    assert "%" not in re.sub(r"\d+/100", "", text.split("Where the audience")[0]).replace("100%", "")
    assert "&#9650;" not in main and "▲" not in main
    assert "au-top5" not in main
    # The funnel is drawn as empty outlines: stage names, no counts.
    assert "au-fun-slab" not in main and 'class="au-fun-count"' not in main
    assert "Nobody on file yet, so nothing is counted" in main


def test_nothing_unmeasured_is_drawn_as_zero(application):
    client, _user, _tag = _populated(application)
    main = _main(client.get("/fans").get_data(as_text=True))
    # Nothing has been sent, so deliverability is not measured; nobody
    # clicked, so engagement is not measured either.
    assert re.search(r"Deliverability.*?Not measured<", main, re.S)
    assert re.search(r"Engagement</span>.*?Not measured yet<", main, re.S)
    assert ">0/100<" not in main
    assert re.search(r"Consent freshness</span>.*?Not measured<", main, re.S), "imports carry no consent date"


# --- counts that add up ------------------------------------------------------

def test_the_counts_add_up(application):
    _client, user, _tag = _populated(application)
    with application.app_context():
        a = fan_audience.for_account(user["id"])
    assert a["total"] == 13 and a["suppressed"] == 2 and a["contactable"] == 11
    assert a["contactable"] + a["suppressed"] == a["total"] and a["adds_up"]
    assert sum(r["count"] for r in a["regions"]) == a["contactable"]
    assert sum(r["suppressed"] for r in a["regions"]) == a["suppressed"]
    assert a["regions"][-1]["unknown"] and a["regions"][-1]["count"] == 3
    # Located is over the contactable: 5 Atlanta + 3 London. The suppressed
    # Atlanta fan is not in it, so "the rest are Unknown" is exactly the
    # Unknown row.
    assert a["located"] == 8
    assert a["contactable"] - a["located"] == a["regions"][-1]["count"]
    # Nobody has clicked, so only On file is measured.
    # The owner's six-row funnel (2026-09-18) dropped "Clicked through":
    # with no visits, no Shopify import and no Fan Club, the rows are On
    # file, then Engaged and Pre-saved, which are not measured until a click.
    assert [s["count"] for s in a["funnel"]] == [a["total"], None, None]
    assert [s["measured"] for s in a["funnel"]] == [True, False, False]
    assert a["growth"] is None, "one day of history is no trend"


def test_the_map_plots_only_known_us_cities(application):
    _client, user, _tag = _populated(application)
    with application.app_context():
        a = fan_audience.for_account(user["id"])
    assert [d["city"] for d in a["geo"]["dots"]] == ["Atlanta"]
    assert [t["city"] for t in a["geo"]["top"]] == ["Atlanta", "London"]
    assert a["geo"]["unplotted"] == 1
    assert fan_audience.coords_for("Paris", "") is None
    assert fan_audience.coords_for("Atlanta", "GB") is None


def test_tour_demand_reads_the_accounts_own_shows(application):
    client, user, _tag = _populated(application)
    with application.app_context():
        a = fan_audience.for_account(user["id"])
    assert [c["city"] for c in a["tour"]["covered"]] == ["Atlanta"]
    assert [c["city"] for c in a["tour"]["uncovered"]] == ["London"]
    fresh, _ = _account(application)
    assert "No shows are booked yet" in fresh.get("/fans").get_data(as_text=True)


# --- the selection -----------------------------------------------------------

def test_the_selection_export_never_includes_a_suppressed_fan(application):
    client, _user, tag = _populated(application)
    r = client.get("/fans?export=csv&region=Atlanta, US&region=Unknown")
    assert r.status_code == 200 and r.mimetype == "text/csv"
    rows = list(csv.DictReader(io.StringIO(r.get_data(as_text=True))))
    emails = {row["Email"] for row in rows}
    assert "a0-%s@example.org" % tag not in emails and "n0-%s@example.org" % tag not in emails
    assert len(rows) == 5 + 3
    assert not any(e.startswith("l") for e in emails), "London was not ticked"
    assert client.get("/fans?export=csv").status_code == 302


def test_the_region_rows_are_real_checkboxes_in_a_form(application):
    client, _user, _tag = _populated(application)
    main = _main(client.get("/fans").get_data(as_text=True))
    assert '<form id="au-sel" method="get" action="/fans">' in main
    assert 'name="region" value="Atlanta, US" data-count="5"' in main
    assert 'name="region" value="Unknown" data-count="3"' in main
    assert "Use this selection" in main and "data-au-all" in main


# --- links and tabs ----------------------------------------------------------

def test_every_link_tab_and_form_on_the_screen_resolves(application):
    client, _user, _tag = _populated(application)
    for page in ("/fans", "/links/fans"):
        main = _main(client.get(page).get_data(as_text=True))
        targets = set(re.findall(r'href="(/[^"#]*)"', main))
        # GET forms are navigations; POST forms are actions, checked by
        # their own route tests.
        targets |= {m.group(2) for m in re.finditer(r'<form([^>]*)action="(/[^"]*)"', main)
                    if 'method="post"' not in m.group(1) + m.group(0)}
        targets = {t for t in targets if not t.startswith("/static/")}
        assert {"/fans", "/links/fans", "/fan-club"} <= targets
        for t in sorted(targets):
            if t.startswith("/links/fans/") and t.endswith("/delete"):
                continue
            assert client.get(t).status_code < 400, (page, t)
        # No tab is an in-page anchor.
        nav = re.search(r'<div class="au-tabs">.*?</nav>', main, re.S).group(0)
        assert "href=\"#" not in nav
        for gone in ("Journeys", "Insights", "Community"):
            assert gone not in nav


def test_the_crm_tab_keeps_working_under_the_same_header(application):
    client, user, tag = _populated(application)
    html = client.get("/links/fans").get_data(as_text=True)
    assert 'sb-plate-title" id="sb-plate-title">Audience' in html
    assert re.search(r'is-on" href="/links/fans"\s*aria-current="page">Fan CRM', html)
    assert "a1-%s@example.org" % tag in html
    assert "a1-%s@example.org" % tag in client.get("/links/fans?q=a1-").get_data(as_text=True)
    assert client.get("/links/fans/export.csv").status_code == 200
    done = client.get("/links/fans?imp=done").get_data(as_text=True)
    assert "13</strong> added" in done, "the import's own counts are read back"
    assert "Say where these people gave you permission" in client.get(
        "/links/fans?imp=needs-source").get_data(as_text=True)


# --- the showcase ------------------------------------------------------------

def test_the_showcase_is_the_demo_accounts_only(application):
    client, _user, _tag = _populated(application)
    main = _main(client.get("/fans").get_data(as_text=True))
    for leak in ("Showcase", "Jasmine", "Marcus", "Talia", "showcase-", "2,840"):
        assert leak not in main, leak

    demo = application.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    shown = _main(demo.get("/fans").get_data(as_text=True))
    assert "Showcase." in shown and "not anybody's fans" in shown
    assert "Jasmine R." in shown and "data-au-import" not in shown


def test_the_showcase_counts_add_up_too(application):
    a = fan_audience.showcase(datetime(2026, 9, 18, tzinfo=timezone.utc))
    assert a["showcase"] and a["adds_up"]
    assert sum(r["count"] for r in a["regions"]) == a["contactable"]


# --- nothing sends -----------------------------------------------------------

def test_the_screen_never_sends_email(application, monkeypatch):
    import email_provider

    def boom(*a, **k):
        raise AssertionError("the Audience screen must not send")
    monkeypatch.setattr(email_provider, "send", boom)
    monkeypatch.setenv("RESEND_API_KEY", "re_test_not_real")
    client, _user, _tag = _populated(application)
    html = client.get("/fans").get_data(as_text=True)
    assert "Resend configured" in html and "Resend connected" not in html
    assert "Not started" in html
    assert client.get("/fans?export=csv&region=Unknown").status_code == 200
    monkeypatch.delenv("RESEND_API_KEY")
    assert "Resend configured" not in client.get("/fans").get_data(as_text=True)


# --- review fixes, 2026-09-18 -------------------------------------------------

def _backdate(user_id, email, days):
    stamp = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with store.get_db() as conn:
        conn.execute("UPDATE ml_fans SET created = ? WHERE user_id = ? AND email = ?",
                     (stamp, user_id, email.lower()))


def test_the_crm_export_leaves_suppressed_fans_out_unless_asked(application):
    client, _user, tag = _populated(application)
    gone = {"a0-%s@example.org" % tag, "n0-%s@example.org" % tag}
    rows = list(csv.DictReader(io.StringIO(
        client.get("/links/fans/export.csv").get_data(as_text=True))))
    assert len(rows) == 11 and not gone & {r["Email"] for r in rows}
    assert all(r["Suppressed"] == "" for r in rows)
    everyone = list(csv.DictReader(io.StringIO(
        client.get("/links/fans/export.csv?include=suppressed").get_data(as_text=True))))
    assert len(everyone) == 13
    marked = {r["Email"]: r["Suppressed"] for r in everyone if r["Suppressed"]}
    assert marked == {"a0-%s@example.org" % tag: "unsubscribed", "n0-%s@example.org" % tag: "bounced"}
    page = client.get("/links/fans").get_data(as_text=True)
    assert "Suppressed: unsubscribed" in page and "Suppressed: bounced" in page
    assert 'href="/links/fans/export.csv?include=suppressed"' in page


def test_an_import_is_not_growth(application):
    client, user = _account(application)
    old = "old-%s@example.org" % user["id"]
    with application.app_context():
        mls.upsert_fan(user["id"], old, None)
        _backdate(user["id"], old, 90)
    tag = uuid.uuid4().hex[:6]
    _import(client, [("i%d-%s@example.org" % (i, tag), "", "Atlanta", "US") for i in range(60)])
    with application.app_context():
        a = fan_audience.for_account(user["id"])
    assert a["total"] == 61 and a["growth"] is None
    main = _main(client.get("/fans").get_data(as_text=True))
    assert "&#9650;" not in main and "\u25b2" not in main and "joined" not in main


def test_the_trend_chip_counts_smart_link_captures_against_a_real_base(application):
    client, user = _account(application)
    uid = user["id"]
    with application.app_context():
        for i in range(25):
            mls.upsert_fan(uid, "old%d-%s@example.org" % (i, uid), None)
            _backdate(uid, "old%d-%s@example.org" % (i, uid), 120)
        for i in range(5):
            mls.upsert_fan(uid, "new%d-%s@example.org" % (i, uid), None)
        a = fan_audience.for_account(uid)
    assert a["growth"] == {"pct": 20.0, "recent": 5, "before": 25}
    main = _main(client.get("/fans").get_data(as_text=True))
    assert "&#9650;20.0%" in main and "last 30 days" in main


def test_the_showcase_never_claims_to_be_live(application):
    demo = application.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    shown = _main(demo.get("/fans").get_data(as_text=True))
    assert "Showcase." in shown
    assert ">Live<" not in shown and "your own records" not in shown
    assert "au-mark--example" in shown
    client, _user, _tag = _populated(application)
    real = _main(client.get("/fans").get_data(as_text=True))
    assert "Live</span> your own records" in real and "au-mark--example" not in real


def test_one_city_is_one_group_however_it_was_typed(application):
    client, user = _account(application)
    tag = uuid.uuid4().hex[:6]
    _import(client, [("c1-%s@ex.org" % tag, "", "chicago", "us"),
                     ("c2-%s@ex.org" % tag, "", "chicago", "US"),
                     ("c3-%s@ex.org" % tag, "", "Chicago", "USA")])
    with application.app_context():
        store.add_tour_show(user["id"], (date.today() + timedelta(days=9)).isoformat(),
                            "Metro", "CHICAGO", "")
        a = fan_audience.for_account(user["id"])
    assert [(r["key"], r["count"]) for r in a["regions"]] == [("Chicago, US", 3)]
    assert [(t["city"], t["count"]) for t in a["geo"]["top"]] == [("Chicago", 3)]
    assert [(c["city"], c["count"]) for c in a["tour"]["covered"]] == [("Chicago", 3)]
    main = _main(client.get("/fans").get_data(as_text=True))
    assert 'value="Chicago, US" data-count="3"' in main
    rows = list(csv.DictReader(io.StringIO(client.get(
        "/fans?export=csv&region=Chicago, US").get_data(as_text=True))))
    assert len(rows) == 3


def test_engagement_is_one_statement_across_the_screen(application):
    client, _user, _tag = _populated(application)
    text = _text(_main(client.get("/fans").get_data(as_text=True)))
    # Health says engagement is not measured; the funnel agrees rather than
    # printing a row of zeros.
    assert "Engaged 0" not in text and "Pre-saved 0" not in text
    assert "only On file is measured" in text
    # The Never engaged tile counts the contactable, and says so.
    assert "Contactable, never engaged" in text and "On file, never clicked" not in text


def test_use_this_selection_works_without_javascript(application):
    client, _user, _tag = _populated(application)
    main = _main(client.get("/fans").get_data(as_text=True))
    button = re.search(r"<button[^>]*data-au-use[^>]*>", main).group(0)
    assert "disabled" not in button


def test_map_labels_are_html_so_the_type_floor_holds(application):
    client, _user, _tag = _populated(application)
    main = _main(client.get("/fans").get_data(as_text=True))
    assert "<text" not in main.split("au-map-svg", 1)[1].split("</svg>", 1)[0]
    assert re.search(r'class="au-lbl-html"[^>]*style="left: [\d.]+%; top: [\d.]+%;"', main)
    css = open("static/css/fans-audience.css", encoding="utf-8").read()
    assert "@container aumap" in css


def test_green_is_only_for_a_score_over_most_of_the_list(application):
    client, user = _account(application)
    uid = user["id"]
    tag = uuid.uuid4().hex[:6]
    _import(client, [("m%d-%s@ex.org" % (i, tag), "", "", "") for i in range(20)])
    with application.app_context():
        mls.upsert_fan(uid, "cap-%s@ex.org" % tag, None)
        a = fan_audience.for_account(uid)
    fresh = [h for h in a["health"] if h["label"] == "Consent freshness"][0]
    assert fresh["score"] == 100 and fresh["tone"] == "mid" and fresh["basis"] == "of 1"
    main = _main(client.get("/fans").get_data(as_text=True))
    assert re.search(r'Consent freshness</span>.*?100/100 <span class="au-hbase">of 1</span>', main, re.S)


def test_segments_keep_the_pin_for_places(application):
    a = fan_audience.showcase(datetime(2026, 9, 18, tzinfo=timezone.utc))
    assert "pin" not in {s["icon"] for s in a["segments"]}


def test_an_artist_keeps_their_whole_menu_on_audience_and_collab():
    """plans.world_for_path filed /fans and /marketplace under the fan
    world, so an artist opening either lost their sidebar and got the fan
    side's Community-only menu. Both are artist tools. A fan account still
    gets the fan sidebar there, because the fan plan forces it."""
    import uuid
    import app as appmod
    import db as store

    def client(plan):
        email = "world-%s@example.net" % uuid.uuid4().hex[:8]
        c = appmod.app.test_client()
        c.post("/signup", data={"name": "W", "email": email, "password": "world-pass-1"})
        store.set_user_plan(store.get_user_by_email(email)["id"], plan)
        return c

    artist = client("label")
    for path in ("/fans", "/marketplace"):
        page = artist.get(path).get_data(as_text=True)
        assert 'data-hub="' in page, "%s lost the artist menu" % path
    fan = client("fan")
    assert 'data-hub="' not in fan.get("/fans").get_data(as_text=True)


def _stages(**kw):
    import fan_audience as fa
    return [(s["name"], s["count"], s["measured"]) for s in fa.build(**kw)["funnel"]]


def _fan(i, **over):
    f = {"id": "f%d" % i, "email": "f%d@example.com" % i, "name": "", "city": "", "country": "",
         "suppressed": "", "tags": "[]", "total_visits": 0, "total_clicks": 0,
         "total_presaves": 0, "total_captures": 0, "intent_level": "Cold",
         "created": "2026-09-01T00:00:00+00:00"}
    f.update(over)
    return f


def test_the_funnel_rows_each_need_their_own_source():
    """Owner, 2026-09-18: the six rows from the mockup, each from a record
    that exists. A row with no source is left out, never drawn as zero."""
    plain = [_fan(i) for i in range(10)]
    # No visits, no Shopify import, no Fan Club, nobody clicked.
    assert _stages(fans=plain) == [("On file", 10, True), ("Engaged", None, False),
                                   ("Pre-saved", None, False)]
    # Views fewer than fans on file: the top row would claim a narrower
    # top than the second, so it is left out.
    assert _stages(fans=plain, link_visits=4)[0][0] == "On file"
    assert _stages(fans=plain, link_visits=40)[0] == ("Link visits", 40, True)


def test_buyer_needs_a_shopify_import_and_member_needs_a_fan_club():
    fans = [_fan(i, total_clicks=1 if i < 3 else 0, total_presaves=1 if i < 1 else 0,
                 tags='["shopify", "customer"]' if i < 4 else ('["shopify"]' if i < 6 else "[]"))
            for i in range(10)]
    names = [s[0] for s in _stages(fans=fans)]
    assert "Buyer" in names and "Member" not in names
    club = [{"member_email": "f1@example.com", "status": "active"},
            {"member_email": "f2@example.com", "status": "cancelled"},
            {"member_email": "stranger@example.com", "status": "active"}]
    rows = dict((s[0], s[1]) for s in _stages(fans=fans, club_members=club, club_on=True))
    assert rows["Buyer"] == 4
    assert rows["Member"] == 1, "cancelled members and non-fans are not counted"
    assert rows["Engaged"] == 3 and rows["Pre-saved"] == 1
    # No store imported: no Buyer row, rather than "0 buyers".
    no_store = [_fan(i) for i in range(5)]
    assert "Buyer" not in [s[0] for s in _stages(fans=no_store)]

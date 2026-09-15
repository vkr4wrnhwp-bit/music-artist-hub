"""The sidebar's head, after the owner's three notes of 2026-09-14.

  * "Royalty Sweep, Track it. Collect it. Sweep it." belongs only on the
    Royalty Sweep pages; everywhere else the sidebar carries the Street
    Banker mark.
  * The four world boxes (Promote, Royalty Sweep, Label Services, Fan
    Side) read as a second menu and came off. Label Services shows for a
    Label plan on every page; the fan card stays for fans.
  * Recent sits under the groups, not above them.
A reseller's artists keep the reseller's mark, as before.
"""
import uuid

import pytest

from app import create_app

PW = "brand-12345"


def _client(app_obj, plan):
    c = app_obj.test_client()
    email = "brand-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Brand", "email": email, "password": PW})
    c.post("/plan/switch", data={"plan": plan})
    return c


def test_the_mark_follows_the_page():
    app_obj = create_app()
    c = _client(app_obj, "label")
    money = c.get("/royalties").get_data(as_text=True).split('id="sb-menu"')[0]
    assert "ROYALTY" in money and "SWEEP" in money and "Track it. Collect it. Sweep it." in money
    assert "streetbanker-logo.svg" not in money
    for path in ("/command-center", "/links", "/tours", "/settings", "/vault"):
        head = c.get(path).get_data(as_text=True).split('id="sb-menu"')[0]
        assert "streetbanker-logo.svg" in head, path
        assert "Track it. Collect it. Sweep it." not in head and "ROYALTY SWEEP" not in head, path


def test_the_world_boxes_are_gone_and_label_services_shows_by_plan():
    app_obj = create_app()
    label = _client(app_obj, "label")
    for path in ("/command-center", "/links", "/tours"):
        body = label.get(path).get_data(as_text=True)
        assert "/world/" not in body.split("</aside>")[0], path
        assert 'data-hub="label"' in body and 'href="/services"' in body, path
    pro = _client(app_obj, "pro")
    body = pro.get("/command-center").get_data(as_text=True)
    assert "/world/" not in body.split("</aside>")[0]
    assert 'data-hub="label"' not in body, "a Pro plan has no Label Services group on a Pro page"
    fan = _client(app_obj, "fan")
    body = fan.get("/discover").get_data(as_text=True)
    assert "Fan Account" in body and "/world/" not in body.split("</aside>")[0]


def test_recent_sits_under_the_groups():
    app_obj = create_app()
    c = _client(app_obj, "pro")
    aside = c.get("/command-center").get_data(as_text=True).split("</aside>")[0]
    assert aside.index('data-hub="account"') < aside.index('id="sb-recent"')

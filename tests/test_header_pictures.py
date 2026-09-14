"""No header photograph anywhere but the homepage and the login.

Owner, 2026-09-14: "remove all header pictures besides the login page and
home page for the moment". The stock pictures are being replaced. Until
the new ones arrive every plate - the signed-in sb.plate band and the
public pp-plate band - opens on the band, the veil and the words alone.
The homepage keeps its photographs and the login keeps its band picture.
"""
import glob
import io
import os
import re
import uuid

import pytest

from app import create_app

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP = {"templates/landing.html", "templates/auth_base.html", "templates/login.html"}


def _templates():
    for path in glob.glob(os.path.join(HERE, "templates", "**", "*.html"), recursive=True):
        rel = os.path.relpath(path, HERE).replace(os.sep, "/")
        yield rel, io.open(path, encoding="utf-8").read()


def test_no_template_names_a_plate_picture():
    for rel, s in _templates():
        if rel in KEEP:
            continue
        assert not re.search(r'sb\.plate\("/static/img', s), rel
        assert '"stem": "/static/img' not in s, rel
        assert "sbrl-band-photo\">" not in s.split("sbrl-doc-hero-inner")[0] or "sbrl-doc-hero" not in s, rel


def test_the_public_plate_default_is_no_picture():
    s = io.open(os.path.join(HERE, "templates", "partials", "plate.html"), encoding="utf-8").read()
    assert '{"stem": none}' in s and '{% if p.get("stem") %}' in s


def test_rendered_pages_carry_no_header_picture_and_the_two_keepers_do():
    app_obj = create_app()
    anon = app_obj.test_client()
    for path in ("/sweep-method", "/catalog-sweep", "/plan", "/legal", "/start"):
        r = anon.get(path)
        if r.status_code != 200:
            continue
        body = r.get_data(as_text=True)
        assert 'class="pp-plate-img"' not in body, path
        assert 'class="pp-plate"' in body, path
    login = anon.get("/login").get_data(as_text=True)
    assert "hero-band-wide" in login, "the login keeps its picture"
    home = anon.get("/").get_data(as_text=True)
    assert "/static/img/" in home, "the homepage keeps its photographs"

    client = app_obj.test_client()
    email = "plate-%s@example.net" % uuid.uuid4().hex[:8]
    client.post("/signup", data={"name": "Plate", "email": email, "password": "plate-12345"})
    client.post("/plan/switch", data={"plan": "pro"})
    for path in ("/statements", "/royalties", "/recovery", "/passports", "/audio-studio", "/releases/autopilot", "/remix-lab"):
        r = client.get(path)
        if r.status_code != 200:
            continue
        body = r.get_data(as_text=True)
        assert 'class="sb-plate-img"' not in body, path

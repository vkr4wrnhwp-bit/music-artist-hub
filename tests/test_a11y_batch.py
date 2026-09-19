"""The outside audit's accessibility and narrow-screen findings.

Codex, 2026-09-17: the Action Center's selects had no accessible name, the
earnings chart had none either, the Artist Signal Profile line truncated at
narrower desktop widths, and the public header crowded until Log in wrapped
and the button pressed the edge of the window.
"""
import io
import os
import re
import uuid

import pytest

import app as appmod
import db as store

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PW = "a11y-batch-pass-1"


@pytest.fixture
def signed_in(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    email = "a11y-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "A", "email": email, "password": PW})
    store.set_user_plan(store.get_user_by_email(email)["id"], "label")
    return c


def test_every_control_on_the_action_form_has_a_name(signed_in):
    form = signed_in.get("/actions").get_data(as_text=True)
    form = form[form.index("New Action"):form.index("</form>", form.index("New Action"))]
    for control in re.finditer(r'<(input|select)\b([^>]*)>', form):
        attrs = control.group(2)
        if 'type="hidden"' in attrs:
            continue
        assert "aria-label=" in attrs or "id=" in attrs, attrs[:90]


def test_the_earnings_chart_says_what_it_draws(signed_in):
    body = signed_in.get("/command-center").get_data(as_text=True)
    m = re.search(r'<canvas id="earningsChart"(.*?)</canvas>', body, re.S)
    assert m, "the chart is gone"
    assert 'role="img"' in m.group(1) and "aria-label=" in m.group(1)
    # A reader who cannot see it is told the same thing in words.
    assert "<p" in m.group(1)


def test_the_signal_profile_line_wraps_instead_of_being_cut_off():
    card = io.open(os.path.join(HERE, "templates", "partials", "signal_profile_card.html"),
                   encoding="utf-8").read()
    assert "truncate" not in card, "the priorities were cut off with no way to read them"


def test_the_public_header_never_wraps():
    css = io.open(os.path.join(HERE, "static", "css", "public-header.css"), encoding="utf-8").read()
    assert ".sbh-inner { flex-wrap: nowrap; }" in css
    assert "@media (min-width: 1024px) and (max-width: 1179px)" in css, \
        "the band where the bar ran out of room"
    for page in ("landing.html", "public_base.html", "release_check.html"):
        html = io.open(os.path.join(HERE, "templates", page), encoding="utf-8").read()
        assert "public-header.css?v=5" in html, page

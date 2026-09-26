"""A Light Studio button with the hidden attribute is hidden.

.lx-btn sets display:inline-flex, which outranks the browser's [hidden]
rule, so four buttons the script hides still showed on a first visit
(audit, 2026-09-26).
"""
import io
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_hidden_lx_buttons_are_hidden():
    css = io.open(os.path.join(HERE, "static", "css", "light-studio.css"), encoding="utf-8").read()
    assert re.search(r"\.lx-btn\[hidden\]\s*\{\s*display:\s*none;?\s*\}", css)
    page = io.open(os.path.join(HERE, "templates", "lights.html"), encoding="utf-8").read()
    for bid in ("lx-pull", "lx-bump", "lx-autocue-clear"):
        tag = re.search(r'<button id="%s"[^>]*>' % bid, page).group(0)
        assert "lx-btn" in tag and "hidden" in tag, bid

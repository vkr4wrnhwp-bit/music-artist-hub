"""The rooms' three-window plate (owner, 2026-09-23).

"is it possible to switch out the room rack plates? they are too tall" -
and "one room has a different plate on it... swap it out to this
three-window one like the rest". The Command Center and every room's page
from zero draw the same shorter plate through partials/cc_rack.html; the
Fans room's map plate is its working page's; the membership rack on the
home page keeps the taller command-plate.webp.
"""
import io
import os
import re
import uuid

import pytest
from PIL import Image

import app as appmod
import db as store

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PW = "room-plate-1"


@pytest.fixture(autouse=True)
def _open(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    monkeypatch.delenv("RENDER", raising=False)


def _read(*parts):
    return io.open(os.path.join(HERE, *parts), encoding="utf-8").read()


def test_the_plate_is_the_owners_shorter_image_at_its_measured_size():
    im = Image.open(os.path.join(HERE, "static", "img", "room-plate.webp"))
    assert im.size == (1774, 421), "cropped from the owner's image, rows 233-653"
    rack = _read("templates", "partials", "cc_rack.html")
    assert 'src="/static/img/room-plate.webp?v=' in rack and 'width="1774" height="421"' in rack


def test_the_screens_sit_on_the_glass_measured_off_the_file():
    """Glass columns 94-569, 627-1136, 1194-1678 and rows 326-540 of the
    source, as percentages of the cropped plate. A round number would be
    an unmeasured placeholder."""
    rack = _read("templates", "partials", "cc_rack.html")
    boxes = re.findall(r'\("([\d.]+)","([\d.]+)","([\d.]+)","([\d.]+)"\)', rack)
    assert boxes == [("5.30", "22.09", "26.83", "51.07"),
                     ("35.34", "22.09", "28.75", "51.07"),
                     ("67.31", "22.09", "27.34", "51.07")]


def test_below_the_measured_width_the_screens_stack_by_the_racks_own_width():
    """The glass is short: under an 880px rack the sentences stop fitting,
    so the three screens stack as boxes. It keys off the rack's width,
    not the window's - beside the sidebar a 1280 window gives a ~958px
    rack, which keeps the plate."""
    css = _read("static", "css", "command-zero.css")
    assert "container: czrack / inline-size" in css
    block = css.split("@container czrack (max-width: 880px) {", 1)[1].split("\n}", 1)[0]
    assert ".cz-plate { display: none; }" in block and "position: static" in block
    assert "container-type: normal" not in css, "the rack stays a container at every width"


def test_the_fans_page_from_zero_uses_the_same_rack_as_every_room():
    email = "plate-%s@example.net" % uuid.uuid4().hex[:8]
    c = appmod.app.test_client()
    c.post("/signup", data={"name": "Plate", "email": email, "password": PW})
    c.post("/login", data={"email": email, "password": PW})
    for path in ("/room/fans", "/room/studio", "/room/marketing"):
        body = c.get(path).get_data(as_text=True)
        assert 'class="cz-plate" src="/static/img/room-plate.webp' in body, path
        assert body.count('<li class="cz-screen"') == 3, path
        assert "command-zero.css?v=3" in body, path
    fans = c.get("/room/fans").get_data(as_text=True)
    assert "fans-plate.webp" not in fans, "the map plate is the working room's"
    for words in ("Own the listener relationship", "Choose how to add your first fans",
                  "Nothing is added until you review and confirm"):
        assert words in fans, words


def test_every_sentence_fits_the_short_glass_and_a_live_title_is_clamped():
    """Measured with headless Chrome on 2026-09-23 on all nine pages at
    rack widths 890-1320: every word inside its glass once the lines use
    the screen's full width and the size steps from 14px. The live values
    (a campaign or action title on the working Command Center) can be any
    length, so four lines is the most a screen shows; a linked value keeps
    its full words in its title."""
    css = _read("static", "css", "command-zero.css")
    rule = css.split(".cz-screen-v {", 1)[1].split("}", 1)[0]
    assert "font-size: clamp(14px, 1.5cqw, 26px)" in rule
    assert "max-width: none" in rule
    assert "-webkit-line-clamp: 4" in rule and "overflow: hidden" in rule
    rack = _read("templates", "partials", "cc_rack.html")
    assert 'href="{{ sc.href }}" title="{{ sc.v }}"' in rack


"""The room kit: Fans, Marketing, Releases and Publishing are ONE object.

Owner, 2026-09-22: "we need to make sure that fans and marketing, that these
three pages are coherent and cohesive with each other. Everything looks the
same. It's not starting to drift." And, about the closing tiles: "the tiles
are the same size, you know, everything, font, etc."

It HAD drifted, in ways nobody would name and everybody would feel: his two
rooms set the title at 46px with the width axis at 112, mine set 44px with
no width axis; the tiles came in three different sizes (108px, 132px, 148px
minimum height, over three different column rules), and Marketing had one
oversized lead tile that no other room had.

static/css/room-kit.css now declares every shared part once. These tests
fail if a room's own sheet declares one of them again, which is what makes
the fix permanent rather than a thing I did on a Tuesday.
"""
import io
import os
import re

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(HERE, "static", "css")
KIT = os.path.join(CSS, "room-kit.css")
ROOMS = {"fans": ("fan-room.css", "fr"),
         "marketing": ("marketing-room.css", "mk"),
         "releases": ("releases-room.css", "rl"),
         "publishing": ("publishing-room.css", "pb")}

# What the kit owns. A room may not redefine any of these for itself.
SHARED = ("hero", "hero-top", "eyebrow", "title", "sub", "controls", "chip",
          "chip-name", "avatar", "cta", "panel", "kicker",
          "tiles", "tile", "tile-top", "tile-ico", "tile-text", "tile-foot",
          "tile-status", "tile-go", "tone-good", "tone-info", "tone-gold",
          "tone-off")


def _read(name):
    return io.open(os.path.join(CSS, name), encoding="utf-8").read()


def _selectors(css):
    """Every selector in the sheet, at the top level and inside @media."""
    out = []
    for chunk in re.findall(r'([^{}]*)\{', css):
        head = chunk.split("*/")[-1].strip()
        if head and not head.startswith("@"):
            out.extend(p.strip() for p in head.split(","))
    return out


def test_the_kit_exists_and_every_room_loads_it():
    assert os.path.exists(KIT)
    for key in ROOMS:
        page = io.open(os.path.join(HERE, "templates", "room_%s.html" % key),
                       encoding="utf-8").read()
        assert "room-kit.css" in page, key
        # And loads it FIRST, so a room's own sheet can still override.
        sheet = ROOMS[key][0]
        assert page.index("room-kit.css") < page.index(sheet), (
            "%s must load the kit before its own sheet" % key)


@pytest.mark.parametrize("room", sorted(ROOMS))
def test_a_room_never_redeclares_what_the_kit_owns(room):
    sheet, prefix = ROOMS[room]
    mine = set()
    for sel in _selectors(_read(sheet)):
        m = re.match(r'^\.%s-([a-z0-9-]+)' % prefix, sel)
        if m and m.group(1) in SHARED and "." not in sel[len(m.group(0)):2]:
            # A compound selector like .mk-panel-head is its own thing; only
            # an exact match on a shared name is a redeclaration.
            if sel.rstrip(":hover").rstrip() == ".%s-%s" % (prefix, m.group(1)):
                mine.add(sel)
    assert not mine, (
        "%s re-declares what room-kit.css owns: %s. Delete it there and let "
        "the kit's rule stand, or the rooms drift apart again."
        % (sheet, ", ".join(sorted(mine))))


def test_the_kit_answers_to_every_room_s_own_class_names():
    """A room's markup keeps its own prefix, so the kit has to claim those
    names too. If an alias is missing the room silently loses the shared
    rule and looks subtly different - the exact failure this file exists
    to prevent."""
    kit = _read(KIT)
    for room, (_sheet, prefix) in sorted(ROOMS.items()):
        page = io.open(os.path.join(HERE, "templates", "room_%s.html" % room),
                       encoding="utf-8").read()
        used = set(re.findall(r'class="([^"]*)"', page))
        names = {c for group in used for c in group.split()
                 if c.startswith(prefix + "-") or c.startswith("rk-")}
        for name in sorted(names):
            if name.startswith("rk-"):
                continue                      # the kit's own name: covered
            base = name[len(prefix) + 1:]
            if base not in SHARED:
                continue
            assert ".%s" % name in kit, (
                "%s uses .%s but room-kit.css does not claim it" % (room, name))


def test_every_room_s_tiles_are_the_same_tile():
    """His actual words. One grid rule, one minimum height, one icon size,
    one type scale - and no room with a bigger first tile."""
    kit = _read(KIT)
    tiles = re.search(r'\n(\.rk-tiles[^{]*)\{([^}]*)\}', kit)
    tile = re.search(r'\n(\.rk-tile[,\s][^{]*)\{([^}]*)\}', kit)
    assert tiles and tile

    for room, (sheet, prefix) in sorted(ROOMS.items()):
        css = _read(sheet)
        # the markup's tile classes must be claimed by the kit's rules
        page = io.open(os.path.join(HERE, "templates", "room_%s.html" % room),
                       encoding="utf-8").read()
        if "-tile" not in page:
            continue
        for cls in ("tiles", "tile"):
            used = ".%s-%s" % (prefix, cls)
            if used in page:
                block = tiles.group(1) if cls == "tiles" else tile.group(1)
                assert used in block or used in kit, (
                    "%s: %s is not on the kit's %s rule" % (room, used, cls))
        assert "is-lead" not in css, (
            "%s still styles a lead tile; the owner asked for tiles that are "
            "all the same size" % sheet)


def test_the_shared_title_is_declared_exactly_once():
    """The drift that started this: two sheets at 46px, two at 44px.

    Checked on the title RULE, not on the number: a room is still free to
    set 46px on something of its own, and Marketing's big figure does.
    """
    kit = _read(KIT)
    rule = re.search(r'\.rk-title[^{]*\{([^}]*)\}', kit)
    assert rule and "font-size: 46px" in rule.group(1)
    for sheet, prefix in ROOMS.values():
        css = _read(sheet)
        assert not re.search(r'\.%s-title[^-{,][^{]*\{' % prefix, css), (
            "%s declares its own title; the kit owns it" % sheet)

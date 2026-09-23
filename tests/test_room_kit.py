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
# All EIGHT, since the 2026-09-22 audit. The lock covered four, so half
# the rooms could redeclare a shared part and nothing would say so. They
# had not - the audit checked - but a lock that guards half the doors is
# the kind of thing that is true until the week it matters.
ROOMS = {"fans": ("fan-room.css", "fr"),
         "marketing": ("marketing-room.css", "mk"),
         "releases": ("releases-room.css", "rl"),
         "publishing": ("publishing-room.css", "pb"),
         "stage": ("stage-room.css", "sg"),
         "studio": ("studio-room.css", "sd"),
         "analytics": ("analytics-room.css", "an"),
         "business": ("business-room.css", "bz")}

# What the kit owns. A room may not redefine any of these for itself.
# hero-aside joined 2026-09-23: marketing-room.css redeclared it and beat
# the kit's narrow-width rule, floating the chip mid-header at 768.
SHARED = ("hero", "hero-top", "hero-aside", "eyebrow", "title", "sub", "controls", "chip",
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

def test_a_tile_is_the_same_WIDTH_in_every_room():
    """Owner, 2026-09-22: "your tiles at the bottom are not the same width as
    the other three. You need to lock that."

    The bug was auto-fit with a 1fr track: a tile's width became a share of
    the row, so Releases' three tiles were a third of the page each and
    Publishing's five a fifth each. Same height, different width. A FIXED
    track is the only way a Publishing tile and a Releases tile are the same
    object - the cost, which he chose, is that a row which does not fill
    stops early instead of stretching.
    """
    kit = _read(KIT)
    rule = re.search(r'\.rk-tiles[^{]*\{([^}]*)\}', kit).group(1)
    assert "auto-fill, 240px" in rule, rule
    assert "1fr" not in rule, (
        "a fractional track makes tile width depend on how many tiles the "
        "room happens to have: " + rule)
    assert "auto-fit" not in rule, (
        "auto-fit collapses empty tracks and stretches the rest, which is the "
        "same failure by another name")

def test_the_ring_is_gold_in_every_room_and_every_state():
    """Owner, 2026-09-22: "if you look in marketing and in fans, they have a
    gold ring around them. The two publishing and releases don't."

    I had given a not-yet-reached step a grey, unlit ring. On an account with
    nothing on record every step is unreached, so every ring went out - which
    is precisely the two rooms he was looking at. Fans and Marketing have no
    such state and never dimmed. The ring keeps its gold border and its glow
    in every state; only the symbol inside goes quiet.
    """
    kit = _read(KIT)
    ring = re.search(r'\.rk-ring, [^{]*\{([^}]*)\}', kit).group(1)
    assert "var(--sb-gold)" in ring and "box-shadow" in ring

    ahead = re.search(r'\.rk-step--ahead \.rk-ring \{([^}]*)\}', kit)
    assert ahead, "the unreached state should still exist, quietly"
    body = ahead.group(1)
    for killed in ("border-color", "box-shadow", "background"):
        assert killed not in body, (
            "a step not yet reached must not lose the gold ring: it sets %s"
            % killed)

def test_every_plate_steps_aside_on_a_phone():
    """The readings ARE the screen. Below 560px the photograph goes and
    they become a stacked list, because a phone that kept the picture
    would show an instrument instead of this artist's numbers.

    The six rooms that share .rk-pl get this from the kit. The two with
    bespoke units - Business and Studio - have to do it themselves, and
    STUDIO DID NOT until the 2026-09-22 audit looked at it on a phone:
    the plate stayed at 375px and "Record or upload a track, then measure
    your master here." was clipped mid-sentence by the window edge.
    """
    phone = r"@media \(max-width: 560px\)"
    kit = _read(KIT)
    assert re.search(phone + r"[^@]*\.rk-pl-img \{ display: none", kit), (
        "the kit must drop the shared plate photograph on a phone")
    for sheet, img in (("business-room.css", "bz-plate"),
                       ("studio-room.css", "sd-plate")):
        css = _read(sheet)
        blocks = [css[m.end():m.end() + 1400]
                  for m in re.finditer(phone, css)]
        assert blocks, "%s has no 560px block: its plate never steps aside" % sheet
        joined = "".join(blocks)
        assert re.search(r"\.%s \{[^}]*display: none" % img, joined), (
            "%s must hide .%s below 560px" % (sheet, img))
        assert "container-type: normal" in joined, (
            "%s: with no plate there is nothing for a cqw to scale against" % sheet)


def test_reduced_motion_stops_the_big_window_too():
    """Audit, 2026-09-22. The reduced-motion block stopped the reel, the
    hint and the ticker and MISSED the frame sequence - the largest
    moving thing on the plate, and its colour-split glitch with it. A
    viewer who asks for less motion gets a still plate now: the first
    frame lit, nothing rotating, no glitch copies.
    """
    kit = _read(KIT)
    # There is more than one reduced-motion block in this sheet (an early
    # one covers tile transitions), so take them ALL - the first cut of
    # this test read only the first and failed on a correct sheet.
    blocks = re.findall(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", kit, re.S)
    assert blocks, "the kit has no reduced-motion block"
    body = "".join(blocks)
    for sel in (".rk-reel", ".rk-tick", ".rk-tip", ".rk-cine-frame"):
        assert sel in body, "%s keeps animating under reduced motion" % sel
    assert "animation: none" in body
    # and the glitch copies, which are pseudo-elements of the frame
    assert "rk-cine-frame b::before" in body and "rk-cine-frame b::after" in body

"""Section 4 of the homepage: one system, eight tools.

This replaces "One system. Six departments." (owner, 2026-09-17: "yes swap
it"). The six were a way of describing the product before the suites
existed; everything else now says eight, from the footer strip to the
memberships to the subdomains, and a visitor who reads six and then counts
eight has been given something to wonder about.

Four of the six have not gone anywhere. Artist Twin, Rollout Engine,
Rights and Fan Intelligence are parts of Street Banker itself, so they
stopped being departments and became things Street Banker does.

The picture is a real rack of eight faceplates, photographed. Only the
lights are drawn: each window carries its suite's mark in its own colour
and they switch on one after another when the section is reached, once,
and then stay lit and still. Nothing here is a link. A stranger pointing
at a tool gets a sentence about it, not a password field, and the single
call to action under the section goes to the plans page.
"""

EYEBROW = "One system. Eight tools."
SUPPORT = "Everything behind the artist, working together."

# The owner's order, the same everywhere: TR NL RE RS TO CO AR MO.
# (key, mark, name, what it does, colour, what opens it)
TOOLS = [
    ("the-room", "TR", "The Room", "Write, build and finish songs.", "#FF7A1A", "Credits"),
    ("noise-lab", "NL", "Noise Lab", "Build your own effects and pedal chains for playing live.", "#F2E600", "Soon"),
    ("reach", "RE", "REACH", "Find your audience, and the people who can move it.", "#1E9BFF", "Pro"),
    ("royalty-sweep", "RS", "Royalty Sweep", "Rights, royalties and clarity: the money desk.", "#19E68C", "Artist"),
    ("tour-suite", "TO", "Tour", "Route it, advance it, play it, settle it.", "#FF2D2D", "Pro"),
    ("company", "CO", "Company", "Your team, your partners and your paperwork.", "#FF2DD1", "Soon"),
    ("artifacts", "AR", "Artifacts", "Merch, collectibles and moments for fans.", "#9B5CFF", "Soon"),
    ("masterclip", "MO", "Motion", "Video and visuals for every release.", "#12C8FF", "Credits"),
]

# Where a plate sits on the photograph, as a fraction of it. Brushed steel
# since 2026-09-18 (owner's option 2: vent grilles, a riveted name plate).
# The owner's photograph spaced its bays a few pixels unevenly, so the
# plates were re-spaced to one exact step (each plate cut, set to 280px of
# the 2508px original, and laid on a 289.57px pitch with its own gap
# between). That is what lets the stacked rows line up plate for plate.
# The photograph's bottom rail was cut to match its top (40px of black
# either side of the plates), so the rack sits evenly in its frame.
PLATE = {
    "first_left": 4.027,     # left edge of the first faceplate, per cent
    "step": 11.5459,         # to the next one
    "width": 11.164,
    "top": 7.167,
    "height": 86.177,
    # Inside a plate: the smoked window, the riveted name plate under the
    # vents (between its four rivets), and the dome lamp top right.
    "window_left": 13.6, "window_width": 71.8, "window_top": 21.4, "window_height": 33.5,
    "label_top": 78.8, "label_height": 9.0,
    "lamp_left": 80.2, "lamp_top": 12.3, "lamp_size": 11.0,
}

IMAGE = {
    "stem": "/static/img/eight-tools",
    "widths": [900, 1200, 1553, 2508],
    "width": 2508,
    "height": 586,
    # Bumped when the photograph changes, so the year-long cache that a
    # query string earns cannot keep showing the old rack.
    "v": 4,
    "alt": ("A rack of eight brushed-steel faceplates in a black rail, one for "
            "each Street Banker tool, each with a lit window and its name on "
            "a riveted plate below it."),
}

# The one thing to press. Not a suite: those need an account, and a stranger
# who asks what a tool is must never be handed a password field.
CTA = {"label": "See what each membership opens", "href": "/plan"}

NOTE = ("Each is its own app. One Street Banker sign-in opens them, and your "
        "membership decides which.")


# THE TWO HALVES
# The rack is drawn as two halves of four, side by side on a wide screen
# and one above the other on a phone. The owner, 2026-09-18: "we don't
# want to have to scroll left and right that's stupid". His artifact did
# it this way from the start; the live page had shipped with a sideways
# scroller instead.
#
# Each half shows the same photograph at twice its width, the second one
# shifted left by a full half, so the seam falls between plates four and
# five. A plate's position inside its half is its position on the whole
# picture, doubled, minus the half it is in.
def _halves(tools):
    out = []
    for h in (0, 1):
        units = []
        for i in range(4):
            n = h * 4 + i
            k, m, name, d, c, o = tools[n]
            units.append({
                "key": k, "mark": m, "name": name, "desc": d, "colour": c, "opens": o,
                "left": round((PLATE["first_left"] + n * PLATE["step"]) * 2 - h * 100, 3),
            })
        out.append({"index": h, "units": units})
    return out


# STACKED, THE TABS COME OFF
# One above the other, each half would show a rack ear: the left one on
# the top row, the right one on the bottom, so the two rows of four did
# not line up (owner, 2026-09-18: "crop the mounting tabs off so they
# line up properly on the 8"). Stacked, each half is cropped to its four
# plates: the same small margin before the first plate on both rows, and
# one shared width, so plate 1 sits over plate 5 and both rows are the
# same size. Side by side (1180px and up) it is one rack again, ears and
# all. The first row's crop ends at the seam, never on plate five.
CROP_MARGIN = 0.6   # per cent of a half, before the first plate of a row


def _crop(halves, unit_width):
    starts = [hf["units"][0]["left"] - CROP_MARGIN for hf in halves]
    span = max(hf["units"][-1]["left"] + unit_width - st for hf, st in zip(halves, starts)) + CROP_MARGIN
    # The first row may run past the seam into the gap, never onto plate 5.
    assert starts[0] + span < 100 + halves[1]["units"][0]["left"], "the crop reaches plate five"
    k = 100 / span
    for hf, st in zip(halves, starts):
        hf["start"] = round(st, 3)
    half = IMAGE["width"] / 2 / IMAGE["height"]   # a half's shape, uncropped
    return {"k": round(k, 5), "ratio": round(half / k, 5), "half": round(half, 5),
            "span": round(span, 3)}


def get_eight_tools_config():
    halves = _halves(TOOLS)
    crop = _crop(halves, PLATE["width"] * 2)
    return {
        "eyebrow": EYEBROW,
        "support": SUPPORT,
        "tools": [
            {"key": k, "mark": m, "name": n, "desc": d, "colour": c, "opens": o}
            for k, m, n, d, c, o in TOOLS
        ],
        "halves": halves,
        # Inside a half, a plate is twice as wide as it is on the whole.
        "unit_width": PLATE["width"] * 2,
        "plate": PLATE,
        "crop": crop,
        "image": IMAGE,
        "cta": CTA,
        "note": NOTE,
        "count": len(TOOLS),
    }

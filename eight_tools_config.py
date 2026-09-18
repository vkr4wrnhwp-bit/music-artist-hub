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
    ("noise-lab", "NL", "Noise Lab", "Build your own effects and pedal chains for playing live.", "#F2E600", "Credits"),
    ("reach", "RE", "REACH", "Find your audience, and the people who can move it.", "#1E9BFF", "Pro"),
    ("royalty-sweep", "RS", "Royalty Sweep", "Rights, royalties and clarity: the money desk.", "#19E68C", "Artist"),
    ("tour-suite", "TO", "Tour", "Route it, advance it, play it, settle it.", "#FF2D2D", "Pro"),
    ("company", "CO", "Company", "Your team, your partners and your paperwork.", "#FF2DD1", "Soon"),
    ("artifacts", "AR", "Artifacts", "Merch, collectibles and moments for fans.", "#9B5CFF", "Soon"),
    ("masterclip", "MO", "Motion", "Video and visuals for every release.", "#12C8FF", "Credits"),
]

# Where a plate sits on the photograph, as a fraction of it. The rack is
# eight identical bays across one wide frame, so the geometry is a step
# rather than a table of measurements.
PLATE = {
    "first_left": 3.75,      # left edge of the first faceplate, per cent
    "step": 11.58,           # to the next one
    "width": 11.25,
    "top": 7.0,
    "height": 83.6,
    # Inside a plate: the smoked window and the label strip under it.
    "window_left": 13.3, "window_width": 74.2, "window_top": 24.6, "window_height": 34.9,
    "label_top": 68.7, "label_height": 9.6,
    "lamp_left": 78.2, "lamp_top": 15.1, "lamp_size": 9.0,
}

IMAGE = {
    "stem": "/static/img/eight-tools",
    "widths": [900, 1200, 1553],
    "width": 1553,
    "height": 388,
    "alt": ("A rack of eight faceplates in a steel rail, one for each Street "
            "Banker tool, each with a lit window and a name below it."),
}

# The one thing to press. Not a suite: those need an account, and a stranger
# who asks what a tool is must never be handed a password field.
CTA = {"label": "See what each membership opens", "href": "/plan"}

NOTE = ("Each is its own app. One Street Banker sign-in opens them, and your "
        "membership decides which.")


def get_eight_tools_config():
    return {
        "eyebrow": EYEBROW,
        "support": SUPPORT,
        "tools": [
            {"key": k, "mark": m, "name": n, "desc": d, "colour": c, "opens": o}
            for k, m, n, d, c, o in TOOLS
        ],
        "plate": PLATE,
        "image": IMAGE,
        "cta": CTA,
        "note": NOTE,
        "count": len(TOOLS),
    }

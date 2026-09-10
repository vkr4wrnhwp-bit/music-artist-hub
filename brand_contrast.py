"""Whether a colour can be read on the surface it will sit on.

A reseller picks an accent, and it is stored in the database. That puts
it out of reach of the design lock, which reads source files for colour
literals and cannot see a value that arrives at runtime. The lock is not
only about tidiness - part of what it enforces is that every ink clears
WCAG AA on every surface - so a colour it cannot see is a colour nobody
is checking.

So the check moves to the point of entry, which is the same answer the
homepage editor reached for links: validate what is checkable, at save,
and say plainly what could not be checked.

The maths here is WCAG 2.1 relative luminance and contrast ratio. It was
inline in tests/test_design_system.py; the test imports it from here now,
so there is one implementation rather than two that drift.
"""

AA_NORMAL = 4.5      # body text
AA_LARGE = 3.0       # >=24px, or >=19px bold - and UI component edges


def luminance(hex_colour):
    """WCAG relative luminance of #rrggbb."""
    h = (hex_colour or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError("not a six-digit hex colour: %r" % hex_colour)
    channels = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def ratio(a, b):
    """Contrast ratio between two colours, 1.0 to 21.0."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def normalise(value):
    """A hex colour from what somebody typed, or None.

    Accepts with or without the hash and in three- or six-digit form,
    because a person pasting a brand colour should not have to know which
    one this field wants.
    """
    text = (value or "").strip().lstrip("#")
    if len(text) == 3 and all(c in "0123456789abcdefABCDEF" for c in text):
        text = "".join(c * 2 for c in text)
    if len(text) != 6 or not all(c in "0123456789abcdefABCDEF" for c in text):
        return None
    return "#" + text.lower()


def check_accent(value, surfaces):
    """Can this accent be read on the surfaces it will sit on?

    `surfaces` is {name: hex}. Returns (colour, problems). The colour is
    None when it is not a colour at all; problems is empty when it clears
    AA everywhere it is used.

    Large-text AA is the bar rather than normal-text: an accent is worn by
    wordmarks, headings and control edges, not body copy. Holding it to
    4.5 would reject most brand colours that are perfectly legible in the
    role they actually play here.
    """
    colour = normalise(value)
    if colour is None:
        return None, ["“%s” is not a colour. Six hex digits, with or"
                  " without the hash, such as 4FA3D1."
                      % (value or "")]
    problems = []
    for name, surface in sorted(surfaces.items()):
        got = ratio(colour, surface)
        if got < AA_LARGE:
            problems.append(
                "%s reads at %.1f:1 against the %s, and needs %.1f:1. It "
                "would be hard to read for anyone, and unreadable for some."
                % (colour, got, name, AA_LARGE))
    return colour, problems

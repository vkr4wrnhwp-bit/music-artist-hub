"""Build the Section 7 photograph derivatives.

    python tools/clean_creative_photo.py path/to/photograph.png

The clean backstage photograph did not come through with the brief - only
the layout mockup did - so the production asset is recovered from that
mockup: the picture is taken from the area the overlay type never covers,
and the generated lettering inside it is cleared.

What is cleared, and why: a price sheet reading "STREET BANKER / SECTION
7" with invented prices, a hanging shirt printed "SECTIN 7", two more
shirts printed with a Street Banker logo, a reaper logo across the merch
cloth, and SB7 stickers on the road cases. The brief for this section
rules out fake Street Banker logos, malformed merchandise text, invented
prices and branded clothing that looks artificial.

The marks are removed morphologically rather than blurred: a closing
erases dark print on a light sheet, an opening erases light print on dark
fabric, and both are computed from the surface's own pixels. A blurred
rectangle reads as a censored photograph; this reads as a blank sheet and
an unprinted shirt.

Nothing else is touched: the people, the room, the light, the road cases,
the folded merchandise and the movement blur are as supplied.
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter

try:
    import pillow_avif  # noqa: F401
    HAVE_AVIF = True
except ImportError:                      # pragma: no cover
    HAVE_AVIF = False

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "static", "img")

# The picture inside the mockup: right of the overlay type, above the
# label rule.
PHOTO = (618, 0, 1448, 980)
FEATHER = 9

# (box, mode, size). "dark" = dark print on a light surface, "light" =
# light print on a dark one. The size has to exceed the stroke width or
# the mark survives; too far past it and the surface flattens.
ZONES = [
    ((414, 184, 542, 366), "fill", 0.30),  # price sheet on the wall
    ((529, 258, 649, 434), "light", 17),   # hanging shirt, centre
    ((634, 262, 720, 332), "light", 13),   # hanging shirt, right
    ((680, 372, 820, 556), "light", 19),   # printed shirt, foreground figure
    ((46, 406, 110, 464), "fill", 0.35),   # sticker, road case
    ((46, 626, 116, 686), "fill", 0.35),   # sticker, road case
    ((95, 715, 240, 840), "fill", 0.35),   # stickers, front road case
    ((484, 780, 830, 980), "light", 25),   # reaper logo across the merch cloth
]

GRAIN_SOURCE = (300, 120)               # plain venue wall, no lettering

# Desktop keeps the room; the phone gets the table and the one working
# light, which is the composition that survives a narrow frame.
CROPS = {
    "wide": ((0, 0, 830, 980), [520, 830]),
    "close": ((120, 380, 720, 900), [400, 600]),
}


def _mask(size, feather):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rectangle(
        [feather, feather, size[0] - feather - 1, size[1] - feather - 1], fill=255)
    return m.filter(ImageFilter.GaussianBlur(feather * 0.8))


def _fill_from_edges(photo, box):
    """A smooth surface pinned to the pixels just outside the box."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    px = photo.load()
    left = [px[max(0, x0 - 1), y] for y in range(y0, y1)]
    right = [px[min(photo.width - 1, x1), y] for y in range(y0, y1)]
    top = [px[x, max(0, y0 - 1)] for x in range(x0, x1)]
    bottom = [px[x, min(photo.height - 1, y1)] for x in range(x0, x1)]
    out = Image.new("RGB", (w, h))
    op = out.load()
    for j in range(h):
        for i in range(w):
            u, v = (i + 0.5) / w, (j + 0.5) / h
            wh, wv = min(v, 1 - v) + 1e-6, min(u, 1 - u) + 1e-6
            total = wh + wv
            op[i, j] = tuple(
                int(round(((left[j][c] * (1 - u) + right[j][c] * u) * wh +
                           (top[i][c] * (1 - v) + bottom[i][c] * v) * wv) / total))
                for c in range(3))
    return out.filter(ImageFilter.GaussianBlur(2))


def _grain(photo, size, amount):
    """The high-frequency part of a clean piece of the same room."""
    w, h = size
    sx, sy = GRAIN_SOURCE
    patch = photo.crop((sx, sy, sx + w, sy + h))
    base = patch.filter(ImageFilter.GaussianBlur(3))
    pp, bp = patch.load(), base.load()
    out = Image.new("RGB", size)
    op = out.load()
    for j in range(h):
        for i in range(w):
            op[i, j] = tuple(int(round((pp[i, j][c] - bp[i, j][c]) * amount)) + 128
                             for c in range(3))
    return out


def clean(photo):
    for box, mode, size in ZONES:
        w, h = box[2] - box[0], box[3] - box[1]
        if mode == "fill":
            region = _fill_from_edges(photo, box)
            grain = _grain(photo, (w, h), size)
            rp, gp = region.load(), grain.load()
            for j in range(h):
                for i in range(w):
                    rp[i, j] = tuple(max(0, min(255, rp[i, j][c] + gp[i, j][c] - 128))
                                     for c in range(3))
            photo.paste(region, (box[0], box[1]), _mask((w, h), FEATHER))
            continue
        region = photo.crop(box)
        if mode == "dark":                      # close: dilate then erode
            region = region.filter(ImageFilter.MaxFilter(size))
            region = region.filter(ImageFilter.MinFilter(size))
        else:                                   # open: erode then dilate
            region = region.filter(ImageFilter.MinFilter(size))
            region = region.filter(ImageFilter.MaxFilter(size))
        # A pixel of blur takes the staircase off the morphology without
        # softening the surface enough to read as defocus.
        region = region.filter(ImageFilter.GaussianBlur(1.2))
        photo.paste(region, (box[0], box[1]), _mask((w, h), FEATHER))
    return photo


def write(photo, name, crop, widths):
    piece = photo.crop(crop)
    pw, ph = piece.size
    print("%s: %d x %d (ratio %.3f)" % (name, pw, ph, pw / ph))
    for width in widths:
        if width > pw:
            print("  skipping %d: the source is %dpx wide" % (width, pw))
            continue
        scaled = piece if width == pw else piece.resize(
            (width, round(ph * width / pw)), Image.LANCZOS)
        stem = os.path.join(OUT, "creative-%s-%d" % (name, width))
        scaled.save(stem + ".jpg", quality=86, optimize=True, progressive=True)
        scaled.save(stem + ".webp", quality=82, method=6)
        if HAVE_AVIF:
            scaled.save(stem + ".avif", quality=60)
        print("  wrote", stem, scaled.size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--already-clean", action="store_true",
                        help="the source is the photograph, not the mockup")
    args = parser.parse_args()

    im = Image.open(args.source).convert("RGB")
    photo = im if args.already_clean else clean(im.crop(PHOTO))
    for name, (crop, widths) in CROPS.items():
        write(photo, name, crop, widths)


if __name__ == "__main__":
    main()

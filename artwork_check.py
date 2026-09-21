"""Will the stores refuse this cover? Answered before it is submitted.

A rejected cover costs the artist a release date and the distributor a
support ticket, and the reason is almost always something measurable that
nobody measured: the file is 1400 square when the store wants 3000, it is
CMYK from a print designer, it carries an alpha channel, or it is a JPEG
that has been enlarged until it is soft.

Two lists come back, and they are never mixed:

  MEASURED   things this module actually looked at and can defend.
  UNCHECKED  rules that decide real rejections and that no file inspection
             can settle. They are listed with the rule, so the person
             reading knows the check was not done rather than assuming it
             passed. A checklist that quietly skips half the rules is worse
             than no checklist, because it is trusted.

The numbers in SPEC are the requirements distributors publish, and they
move. They are gathered in one place so a change is one edit, and DSP_NOTE
says out loud that they should be verified against the store's own current
sheet rather than trusted from here forever.
"""

import io
import os

DSP_NOTE = ("The requirements below are the ones the stores and distributors "
            "publish. They change. Verify them against the store's own current "
            "specification before treating a pass as a guarantee.")

SPEC = {
    # Apple Music asks for 3000 square and most distributors pass that on as
    # their own requirement, so it is the bar. Below 1400 nothing will take
    # it at all, which is a different and worse answer than "too small".
    "preferred_edge": 3000,
    "minimum_edge": 1400,
    # A cover is square everywhere. A few pixels out is a crop; far out is
    # the wrong asset entirely, usually a banner or a press shot.
    "square_tolerance": 0.01,
    "formats": ("JPEG", "PNG"),
    # Transparency has no meaning on a store tile and gets flattened against
    # something the artist did not choose, so it is refused rather than
    # silently composited.
    "allow_alpha": False,
    # Common upload cap. Over it the upload itself fails, which reads to the
    # artist as the store rejecting the art.
    "max_bytes": 10 * 1024 * 1024,
    # Laplacian variance. Below the floor the image is soft enough that a
    # human reviewer would call it blurry or upscaled.
    "sharpness_floor": 60.0,
    "sharpness_warn": 140.0,
}

# The rules that reject covers and that reading the file cannot settle. Each
# is shown to the person with its rule, and never counted as passed.
UNCHECKED = [
    ("Text matches the release",
     "Any words on the cover must match the artist name and release title in "
     "the metadata exactly. A different spelling, a stray subtitle or an old "
     "title is one of the most common rejections."),
    ("No web or social addresses",
     "No URLs, handles, email addresses, phone numbers or QR codes."),
    ("No other party's marks",
     "No store logos, no streaming service names, no trademarks or brands you "
     "do not own, and no pricing."),
    ("Advisory mark matches the release",
     "A parental advisory mark may appear only when the release itself is "
     "marked explicit, and it must be the official mark."),
    ("The image is yours to use",
     "Licensed, owned or cleared, including any photograph of a person."),
    ("Nothing misleading",
     "No claim of a feature, a label or a collaborator that is not on the "
     "release."),
]


def _add(out, key, label, state, detail, value=None):
    out.append({"key": key, "label": label, "state": state,
                "detail": detail, "value": value})


def _sharpness(image):
    """Variance of the Laplacian on a downscaled greyscale copy.

    Downscaled first so the number means the same thing for a 1400 file and
    a 6000 one; otherwise a big soft image scores like a small sharp one.
    """
    try:
        import numpy as np
    except ImportError:
        return None
    grey = image.convert("L")
    grey.thumbnail((1024, 1024))
    a = np.asarray(grey, dtype="float32")
    if a.size < 64:
        return None
    lap = (-4 * a[1:-1, 1:-1] + a[:-2, 1:-1] + a[2:, 1:-1]
           + a[1:-1, :-2] + a[1:-1, 2:])
    return float(lap.var())


def _flatness(image):
    """How much of the picture is one colour, 0 to 1. A cover that is almost
    entirely one flat field is usually a placeholder somebody forgot."""
    try:
        import numpy as np
    except ImportError:
        return None
    small = image.convert("RGB")
    small.thumbnail((128, 128))
    a = np.asarray(small).reshape(-1, 3)
    if not len(a):
        return None
    q = (a // 24).astype("int32")
    keys = q[:, 0] * 1000 + q[:, 1] * 100 + q[:, 2]
    counts = np.bincount(keys)
    return float(counts.max()) / float(len(keys))


def _read(source, filename):
    if isinstance(source, (bytes, bytearray)):
        return bytes(source), filename
    if hasattr(source, "read"):
        return source.read(), filename
    with open(source, "rb") as fh:
        raw = fh.read()
    return raw, (filename or os.path.basename(source))


def check(source, filename=""):
    """Look at one cover. `source` is a path, bytes or a file object.

    Returns a dict with a verdict, the measured findings and the rules this
    cannot settle. The verdict is "fix" when a store would refuse it,
    "review" when something is risky but passable, and "pass" when
    everything measured is clean. A pass is never a guarantee, and the
    unchecked list is what says so.
    """
    # Guarded on purpose. If the image library is not installed on this
    # deployment, an upload must still succeed and the person must be told
    # the check did not run, rather than shown a pass it never measured.
    try:
        from PIL import Image
    except ImportError:
        return unavailable(filename)

    measured = []
    raw, filename = _read(source, filename)
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:
        _add(measured, "readable", "The file opens", "fix",
             "This file could not be read as an image. It may be damaged, or "
             "it may not be an image at all.")
        return _result(measured, filename)

    fmt = (image.format or "").upper()
    w, h = image.size
    mode = image.mode

    # --- shape ---------------------------------------------------------
    off = abs(w - h) / float(max(w, h) or 1)
    if off > SPEC["square_tolerance"]:
        _add(measured, "square", "Square", "fix",
             "A cover is square. This one is %d by %d, which is %.0f per cent "
             "out." % (w, h, off * 100), "%dx%d" % (w, h))
    else:
        _add(measured, "square", "Square", "pass",
             "%d by %d." % (w, h), "%dx%d" % (w, h))

    edge = min(w, h)
    if edge < SPEC["minimum_edge"]:
        _add(measured, "size", "Size", "fix",
             "%d pixels on the short side. Nothing will take it below %d, and "
             "the stores ask for %d."
             % (edge, SPEC["minimum_edge"], SPEC["preferred_edge"]), edge)
    elif edge < SPEC["preferred_edge"]:
        _add(measured, "size", "Size", "fix",
             "%d pixels on the short side. The stores ask for %d, so most "
             "distributors refuse this. Enlarging it will not help; it needs "
             "exporting again at full size."
             % (edge, SPEC["preferred_edge"]), edge)
    else:
        _add(measured, "size", "Size", "pass",
             "%d pixels, at or above the %d the stores ask for."
             % (edge, SPEC["preferred_edge"]), edge)

    # --- file ----------------------------------------------------------
    if fmt not in SPEC["formats"]:
        _add(measured, "format", "File type", "fix",
             "This is %s. Stores take %s." % (fmt or "an unknown type",
                                              " or ".join(SPEC["formats"])), fmt)
    else:
        _add(measured, "format", "File type", "pass", "%s." % fmt, fmt)

    has_alpha = mode in ("RGBA", "LA", "PA") or (
        mode == "P" and "transparency" in image.info)
    if mode == "CMYK":
        _add(measured, "colour", "Colour", "fix",
             "This is CMYK, which is for print. Screens are RGB, and CMYK art "
             "arrives at the store with its colours shifted.", mode)
    elif has_alpha:
        _add(measured, "colour", "Colour", "fix" if not SPEC["allow_alpha"] else "review",
             "This carries transparency. A store tile has nothing behind it, "
             "so the see-through parts become whatever the store puts there. "
             "Flatten it onto the background you want.", mode)
    elif mode == "RGB":
        _add(measured, "colour", "Colour", "pass", "RGB.", mode)
    elif mode == "L":
        _add(measured, "colour", "Colour", "pass",
             "Greyscale, which stores accept.", mode)
    else:
        _add(measured, "colour", "Colour", "review",
             "Colour mode %s. Save it as RGB to be certain the colours "
             "survive." % mode, mode)

    size_mb = len(raw) / 1048576.0
    if len(raw) > SPEC["max_bytes"]:
        _add(measured, "weight", "File size", "review",
             "%.1f MB. Many upload forms stop at %d MB, and a failed upload "
             "looks to the artist like a rejection."
             % (size_mb, SPEC["max_bytes"] // 1048576), round(size_mb, 1))
    else:
        _add(measured, "weight", "File size", "pass",
             "%.1f MB." % size_mb, round(size_mb, 1))

    # --- picture -------------------------------------------------------
    sharp = _sharpness(image)
    if sharp is None:
        _add(measured, "sharpness", "Sharpness", "skipped",
             "Not measured on this server.")
    elif sharp < SPEC["sharpness_floor"]:
        _add(measured, "sharpness", "Sharpness", "fix",
             "Soft enough that a reviewer would call it blurry, or enlarged "
             "from a smaller file. Export it again from the original.",
             round(sharp, 1))
    elif sharp < SPEC["sharpness_warn"]:
        _add(measured, "sharpness", "Sharpness", "review",
             "On the soft side. Worth checking against the original before it "
             "goes out.", round(sharp, 1))
    else:
        _add(measured, "sharpness", "Sharpness", "pass", "Crisp.", round(sharp, 1))

    flat = _flatness(image)
    if flat is None:
        _add(measured, "content", "Not blank", "skipped",
             "Not measured on this server.")
    elif flat > 0.97:
        _add(measured, "content", "Not blank", "fix",
             "Almost the whole picture is one colour. This is usually a "
             "placeholder that was never replaced.", round(flat, 2))
    elif flat > 0.88:
        _add(measured, "content", "Not blank", "review",
             "Most of the picture is one flat colour. Deliberate on some "
             "covers, a missing layer on others.", round(flat, 2))
    else:
        _add(measured, "content", "Not blank", "pass",
             "There is a picture here.", round(flat, 2))

    return _result(measured, filename)


def unavailable(filename=""):
    """The check could not run here. Says so, and claims nothing.

    Every rule moves to the unchecked list, because a rule nobody looked
    at has not passed. The verdict is its own state, so no caller can
    mistake it for a clean cover."""
    return {
        "filename": filename,
        "verdict": "not-checked",
        "summary": ("This cover was not checked. The image library this "
                    "check needs is not installed here."),
        "measured": [],
        "fixes": [],
        "reviews": [],
        "unchecked": ([{"label": "Everything measurable",
                        "rule": "Nothing about this file was inspected."}]
                      + [{"label": a, "rule": b} for a, b in UNCHECKED]),
        "note": DSP_NOTE,
    }


def _result(measured, filename):
    fixes = [m for m in measured if m["state"] == "fix"]
    reviews = [m for m in measured if m["state"] == "review"]
    verdict = "fix" if fixes else ("review" if reviews else "pass")
    if verdict == "fix":
        summary = ("%d thing%s here would be refused."
                   % (len(fixes), "" if len(fixes) == 1 else "s"))
    elif verdict == "review":
        summary = ("Nothing here would be refused outright, but %d thing%s "
                   "worth a look."
                   % (len(reviews), " is" if len(reviews) == 1 else "s are"))
    else:
        summary = "Everything this check can measure is clean."
    return {
        "filename": filename,
        "verdict": verdict,
        "summary": summary,
        "measured": measured,
        "fixes": fixes,
        "reviews": reviews,
        "unchecked": [{"label": a, "rule": b} for a, b in UNCHECKED],
        "note": DSP_NOTE,
    }

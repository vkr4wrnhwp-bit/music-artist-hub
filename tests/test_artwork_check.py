"""The cover check catches what stores actually refuse, and admits the rest.

Built 2026-09-17 as the first piece of the Creative Studio, for the
Symphonic and Ditto conversations. Their shared pain is artwork rejections:
a rejection costs the artist a release date and the distributor a support
ticket, and the cause is nearly always measurable.

The honesty rule matters more here than anywhere: a pass must never imply
the rules this cannot read were checked. Those come back in their own list.
"""
import io
import random

import pytest
from PIL import Image, ImageDraw, ImageFilter

import artwork_check as ac


def _art(size=(3000, 3000), mode="RGB", fmt="JPEG", detail=True, blur=0):
    """A plausible cover: noise and shapes, so it is neither flat nor soft."""
    w, h = size
    im = Image.new(mode if mode != "P" else "RGB", size, (24, 18, 40))
    d = ImageDraw.Draw(im)
    if detail:
        rnd = random.Random(7)
        for _ in range(240):
            x, y = rnd.randrange(w), rnd.randrange(h)
            r = rnd.randrange(max(8, w // 90), max(20, w // 12))
            d.ellipse((x - r, y - r, x + r, y + r),
                      outline=(rnd.randrange(120, 255), rnd.randrange(60, 255),
                               rnd.randrange(60, 255)), width=max(2, w // 300))
        for i in range(0, w, max(6, w // 60)):
            d.line((i, 0, i, h), fill=(200, 220, 90) if i % 3 else (120, 60, 240), width=2)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    if mode not in ("RGB",):
        im = im.convert(mode)
    buf = io.BytesIO()
    im.save(buf, fmt)
    return buf.getvalue()


def _state(result, key):
    return next(m["state"] for m in result["measured"] if m["key"] == key)


def test_a_good_cover_passes_and_still_says_what_it_did_not_check():
    r = ac.check(_art(), "cover.jpg")
    assert r["verdict"] == "pass", [m for m in r["measured"] if m["state"] != "pass"]
    assert r["summary"].startswith("Everything this check can measure")
    # The half it cannot read is listed, not silently counted as passing.
    labels = [u["label"] for u in r["unchecked"]]
    assert "Text matches the release" in labels and len(labels) >= 6
    assert all(u["rule"] for u in r["unchecked"])
    assert "verify" in r["note"].lower()


def test_too_small_is_refused_and_says_enlarging_will_not_help():
    r = ac.check(_art((1500, 1500)), "small.jpg")
    assert r["verdict"] == "fix" and _state(r, "size") == "fix"
    detail = next(m["detail"] for m in r["measured"] if m["key"] == "size")
    assert "3000" in detail and "Enlarging it will not help" in detail


def test_below_the_floor_says_nothing_will_take_it():
    r = ac.check(_art((900, 900)), "tiny.jpg")
    assert _state(r, "size") == "fix"
    assert "Nothing will take it" in next(
        m["detail"] for m in r["measured"] if m["key"] == "size")


def test_a_banner_is_not_a_cover():
    r = ac.check(_art((3000, 1500)), "banner.jpg")
    assert _state(r, "square") == "fix"
    assert "3000 by 1500" in next(m["detail"] for m in r["measured"] if m["key"] == "square")


def test_print_art_and_transparency_are_both_caught():
    cmyk = ac.check(_art(mode="CMYK", fmt="JPEG"), "print.jpg")
    assert _state(cmyk, "colour") == "fix"
    assert "CMYK" in next(m["detail"] for m in cmyk["measured"] if m["key"] == "colour")
    clear = ac.check(_art(mode="RGBA", fmt="PNG"), "logo.png")
    assert _state(clear, "colour") == "fix"
    assert "transparency" in next(
        m["detail"] for m in clear["measured"] if m["key"] == "colour").lower()


def test_the_wrong_kind_of_file_is_refused_rather_than_guessed_at():
    assert ac.check(b"this is not an image at all", "notes.txt")["verdict"] == "fix"
    r = ac.check(_art(fmt="BMP"), "cover.bmp")
    assert _state(r, "format") == "fix" and "BMP" in str(r["measured"])


def test_a_blurred_or_upscaled_cover_is_caught():
    r = ac.check(_art(blur=9), "soft.jpg")
    assert _state(r, "sharpness") in ("fix", "review")


def test_a_placeholder_nobody_replaced_is_caught():
    flat = Image.new("RGB", (3000, 3000), (17, 17, 17))
    buf = io.BytesIO()
    flat.save(buf, "JPEG")
    r = ac.check(buf.getvalue(), "placeholder.jpg")
    assert _state(r, "content") == "fix"
    assert r["verdict"] == "fix"


def test_softening_a_cover_lowers_the_reading_until_it_stops_passing():
    """The measure has to track the thing it claims to measure, so blur it
    by degrees and watch the number fall and the verdict turn."""
    readings, verdicts = [], []
    for blur in (0, 4, 8, 14):
        r = ac.check(_art(blur=blur), "b.jpg")
        readings.append(next(m["value"] for m in r["measured"] if m["key"] == "sharpness"))
        verdicts.append(_state(r, "sharpness"))
    assert readings == sorted(readings, reverse=True), readings
    assert verdicts[0] == "pass" and verdicts[-1] == "fix", verdicts


def test_a_review_is_not_a_refusal():
    """Two different answers, and the wording keeps them apart."""
    big = _art()
    padded = ac.check(big + b" " * (11 * 1024 * 1024), "heavy.jpg")
    assert padded["verdict"] == "review"
    assert padded["fixes"] == [] and len(padded["reviews"]) == 1
    assert "Nothing here would be refused" in padded["summary"]
    assert "worth a look" in padded["summary"]


def test_every_finding_carries_its_reason_and_what_was_seen():
    r = ac.check(_art((1500, 1500)), "small.jpg")
    for m in r["measured"]:
        assert m["label"] and m["detail"], m
        assert m["state"] in ("pass", "review", "fix", "skipped"), m
        if m["state"] != "skipped":
            assert m["value"] is not None, m


def test_it_reads_a_path_bytes_or_a_file_object(tmp_path):
    data = _art()
    p = tmp_path / "cover.jpg"
    p.write_bytes(data)
    by_path = ac.check(str(p))
    assert by_path["filename"] == "cover.jpg"
    assert by_path["verdict"] == ac.check(data, "cover.jpg")["verdict"]
    with open(p, "rb") as fh:
        assert ac.check(fh, "cover.jpg")["verdict"] == by_path["verdict"]

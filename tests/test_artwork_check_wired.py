"""The cover check is reachable, and it never lies about what it measured.

artwork_check.py was written and tested and then imported by nothing, so
no artist ever saw it. test_artwork_check.py proves the measurements. This
file proves the door exists, that a refusal is honest, and that a cover the
check could not read is reported as unread rather than as clean.

The rules this file holds:

  * signed out, there is no check
  * a real cover that meets the store specification comes back clean
  * a cover the stores would refuse comes back with the reasons
  * a file that is not an image is a fix, never a pass
  * the rules no file inspection can settle always come back, so a pass
    is never mistaken for a guarantee
  * nothing is saved: the file is measured and dropped
"""
import io
import os

import pytest

import artwork_check
from app import create_app

pytest.importorskip("PIL", reason="the cover check needs the image library")
from PIL import Image, ImageDraw  # noqa: E402


@pytest.fixture
def client():
    app_obj = create_app()
    return app_obj, app_obj.test_client()


def _cover(edge=3000, mode="RGB", fmt="JPEG"):
    """A cover with hard edges and real colour, because that is what a
    cover is. A flat or smooth synthetic image trips the checks for a
    placeholder and for softness, which are exactly the checks working."""
    image = Image.new(mode if mode in ("RGB", "L") else "RGB", (edge, edge),
                      (18, 20, 24))
    draw = ImageDraw.Draw(image)
    step = max(1, edge // 12)
    for i in range(12):
        for j in range(12):
            if (i + j) % 2:
                draw.rectangle([i * step, j * step, (i + 1) * step, (j + 1) * step],
                               fill=((i * 21) % 256, (j * 19) % 256,
                                     ((i + j) * 13) % 256))
    draw.ellipse([edge * 0.2, edge * 0.2, edge * 0.8, edge * 0.8],
                 outline=(255, 240, 200), width=max(1, edge // 60))
    if mode not in ("RGB", "L"):
        image = image.convert(mode)
    buf = io.BytesIO()
    image.save(buf, format=fmt, **({"quality": 88} if fmt == "JPEG" else {}))
    return buf.getvalue()

def _post(c, data, name="cover.jpg"):
    return c.post("/artwork/check",
                  data={"art": (io.BytesIO(data), name)},
                  content_type="multipart/form-data")


def _sign_in(app_obj, c):
    import db as store
    from werkzeug.security import generate_password_hash
    email = "art-%d@example.com" % int(os.urandom(4).hex(), 16)
    uid = store.create_user(email, "Cover Artist",
                            generate_password_hash("a-long-password"))
    with c.session_transaction() as sess:
        sess["user_id"] = uid
    return uid


def test_signed_out_there_is_no_check(client):
    """The app gates every page, so a signed-out caller is turned away
    before the route runs. What matters is that no verdict comes back."""
    app_obj, c = client
    reply = _post(c, _cover())
    assert reply.status_code != 200, reply.status_code
    assert b'"check"' not in reply.data

def test_a_cover_that_meets_the_specification_comes_back_clean(client):
    app_obj, c = client
    _sign_in(app_obj, c)
    reply = _post(c, _cover())
    assert reply.status_code == 200
    found = reply.get_json()["check"]
    assert found["verdict"] == "pass", found["measured"]
    assert found["fixes"] == []


def test_a_cover_the_stores_would_refuse_says_why(client):
    app_obj, c = client
    _sign_in(app_obj, c)
    found = _post(c, _cover(edge=1400)).get_json()["check"]
    assert found["verdict"] == "fix"
    assert any("1400" in (m["detail"] or "") for m in found["fixes"]), found["fixes"]


def test_a_cover_that_is_not_square_is_refused(client):
    app_obj, c = client
    _sign_in(app_obj, c)
    image = Image.new("RGB", (3000, 2000), (18, 20, 24))
    draw = ImageDraw.Draw(image)
    draw.rectangle([100, 100, 1400, 900], fill=(230, 40, 60))
    draw.rectangle([1500, 950, 2900, 1900], fill=(40, 190, 230))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=88)
    found = _post(c, buf.getvalue()).get_json()["check"]
    assert found["verdict"] == "fix"
    assert any(m["key"] == "square" for m in found["fixes"]), found["fixes"]


def test_a_file_that_is_not_an_image_is_never_a_pass(client):
    app_obj, c = client
    _sign_in(app_obj, c)
    found = _post(c, b"this is not a picture", name="notes.txt").get_json()["check"]
    assert found["verdict"] == "fix"


def test_the_unsettled_rules_always_come_back(client):
    """A checklist that quietly skips half its rules is worse than none,
    because it is trusted. Even a clean cover carries the list."""
    app_obj, c = client
    _sign_in(app_obj, c)
    found = _post(c, _cover()).get_json()["check"]
    assert found["unchecked"], "a pass must still say what it did not check"
    assert found["note"]


def test_a_check_that_cannot_run_says_so_rather_than_passing(monkeypatch):
    """If the image library is missing on a deployment, the artist is told
    the check did not run. It must never read as a clean cover."""
    result = artwork_check.unavailable("cover.png")
    assert result["verdict"] == "not-checked"
    assert result["verdict"] != "pass"
    assert result["measured"] == []
    assert result["unchecked"]


def test_nothing_is_saved_by_a_check(client, tmp_path):
    app_obj, c = client
    _sign_in(app_obj, c)
    uploads = app_obj.config.get("UPLOADS_DIR") or ""
    before = sorted(os.listdir(uploads)) if uploads and os.path.isdir(uploads) else []
    _post(c, _cover())
    after = sorted(os.listdir(uploads)) if uploads and os.path.isdir(uploads) else []
    assert before == after

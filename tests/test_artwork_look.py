"""The ticked boxes that tell the model what to make.

The cover art generator is Pollinations.ai: free, keyless, and generic
unless it is told what to make. Every prompt used to get the same four
words appended, so every cover came back looking like the same cover
(owner, 2026-09-22: "how do we get the cover art generator to create
better images? and maybe have some check boxes below it like lighting and
realism").

The rule these hold: the boxes add REAL WORDS to the prompt, and the words
are shown. A preset that hides what it did cannot be argued with when the
picture comes back wrong.
"""
import json
import uuid

import pytest

import artwork_config as ac
import app as appmod
import db as store
from werkzeug.security import generate_password_hash


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    a = appmod.create_app()
    a.config.update(TESTING=True)
    with a.app_context():
        uid = store.create_user("art-%s@example.net" % uuid.uuid4().hex[:8], "Artist",
                                generate_password_hash("a-long-password"))
        store.set_user_plan(uid, "label")
    c = a.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = uid
    return c


def _gen(client, **body):
    r = client.post("/artwork/generate", data=json.dumps(body),
                    content_type="application/json")
    assert r.status_code == 200
    return r.get_json()


def test_the_words_the_boxes_add_are_real_words():
    """Not a style id the model never sees."""
    out = ac.build_prompt("moody synthwave", ["photo", "moody", "grain", "wide"])
    assert out.startswith("moody synthwave, ")
    assert "shot on film" in out
    assert "low-key lighting" in out
    assert "35mm film grain" in out
    assert "negative space" in out


def test_one_tick_per_row_wins():
    """Photographic and illustrated together is a muddle, and the model
    resolves it by quietly ignoring one of them."""
    out = ac.build_prompt("a cover", ["photo", "illustrated"])
    assert "photographic" in out
    assert "hand-drawn" not in out


def test_what_every_cover_gets_whatever_is_ticked():
    """Stores reject a cover with the wrong shape or stray text, so this
    is not a style choice and cannot be unticked."""
    for look in ([], ["illustrated"], ["photo", "bright", "clean", "close"]):
        out = ac.build_prompt("a cover", look)
        assert "square" in out
        assert "no text" in out and "no lettering" in out


def test_nothing_ticked_still_makes_a_prompt():
    out = ac.build_prompt("just this", [])
    assert out.startswith("just this, album cover art")


def test_an_empty_description_asks_for_no_picture(client):
    got = _gen(client, prompt="")
    assert got["ok"] and got["image_url"] is None, "no prompt, no generation"


def test_the_ticks_reach_the_model_and_are_shown_back(client):
    got = _gen(client, prompt="neon city", look=["photo", "moody"])
    assert got["image_url"] and "image.pollinations.ai" in got["image_url"]
    # The words are in the URL the browser will load...
    assert "shot%20on%20film" in got["image_url"] or "shot+on+film" in got["image_url"]
    # ...and shown back, so a person can see what was asked for.
    assert "shot on film" in got["prompt_used"]
    assert "low-key lighting" in got["prompt_used"]
    assert got["prompt_used"].startswith("neon city, ")


def test_a_junk_look_value_is_ignored_not_echoed(client):
    """The look keys come from a fixed list. Anything else is dropped
    rather than pasted into a prompt that goes to a third party."""
    got = _gen(client, prompt="neon city", look=["photo", "not-a-real-key", 7, None])
    assert "not-a-real-key" not in got["prompt_used"]
    assert "shot on film" in got["prompt_used"]


def test_a_look_that_is_not_a_list_does_not_break_it(client):
    got = _gen(client, prompt="neon city", look="photo")
    assert got["ok"] and got["image_url"]


def test_every_option_belongs_to_a_row_the_page_renders():
    """An option in no group would be defined and never shown."""
    groups = {g for _k, g, _l, _w in ac.LOOK_OPTIONS}
    assert groups == set(ac.LOOK_GROUPS)
    keys = [k for k, _g, _l, _w in ac.LOOK_OPTIONS]
    assert len(keys) == len(set(keys)), "no two options share a key"

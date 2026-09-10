"""Four pages over the same rows became one.

Asked for live, 2026-09-10: "posts, drafts, storyboard and calendar can
definetly merge i think" — and "i can see the assets in storyboard, so
why cant we just have the drafts for the rollout come up in story board
as well".

They were already the same rows in ro_posts. Nothing separated the pages
but which columns each chose to show: the words on Posts, the picture on
Storyboard, the dates on Calendar. So a single post could not be
finished anywhere — you wrote the caption on one page, went to another
to attach the asset, and to a third to see where it landed.

Held here: one page, three arrangements, and every arrangement can edit.
The old addresses still answer, because they are in people's history.
"""
import uuid
from datetime import date, timedelta

import pytest

import app as appmod
import db as store
import rollout_engine
import rollout_store as ros

PASSWORD = "plan-merge-123"


@pytest.fixture
def campaign():
    c = appmod.app.test_client()
    email = "plan-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Artist", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    with appmod.app.app_context():
        uid = store.get_user_by_email(email)["id"]
        cid = ros.create_campaign(uid, {
            "title": "Cold Corner", "artist_name": "King 810",
            "release_date": (date.today() + timedelta(days=14)).isoformat(),
            "rollout_length": 7, "goal": "streams", "tone": "raw",
            "platforms": ["instagram_reels", "tiktok", "x"]})
        for post in rollout_engine.generate_rollout(ros.get_campaign(cid)):
            ros.add_post(cid, post)
    c._cid = cid
    c._uid = uid
    return c


def _plan(client, view="list"):
    return client.get("/rollout-studio/%s/plan?view=%s"
                      % (client._cid, view)).get_data(as_text=True)


def test_all_three_arrangements_render_the_same_posts(campaign):
    with appmod.app.app_context():
        expected = len(ros.list_posts(campaign._cid))
    assert expected > 1
    for view in ("list", "board", "calendar"):
        page = _plan(campaign, view)
        assert "%d posts" % expected in page, (
            "%s does not show the whole plan" % view)


def test_the_old_addresses_still_answer(campaign):
    """They are in people's history — a dead link is a worse answer."""
    for path, view in (("posts", "list"), ("storyboard", "board"),
                       ("calendar", "calendar")):
        r = campaign.get("/rollout-studio/%s/%s" % (campaign._cid, path))
        assert r.status_code == 301
        assert r.headers["Location"].endswith("/plan?view=%s" % view)


def test_the_picture_and_the_words_are_on_the_same_page(campaign):
    """The split this removed: caption on one page, asset on another."""
    page = _plan(campaign, "list")
    assert "Attach from Vault" in page, "the asset picker was Storyboard-only"
    assert 'name="caption"' in page, "and the caption was Posts-only"


def test_the_board_can_edit_a_caption_without_leaving_it(campaign):
    page = _plan(campaign, "board")
    assert 'name="caption"' in page, (
        "reading a board and having to leave it to fix one word is the "
        "split this page removed")
    assert "Attach from Vault" in page


def test_the_calendar_can_move_a_post(campaign):
    """Moving a post is what a calendar is for; it used to be read-only."""
    page = _plan(campaign, "calendar")
    assert 'name="scheduled_date"' in page
    with appmod.app.app_context():
        pid = ros.list_posts(campaign._cid)[0]["id"]
    moved = (date.today() + timedelta(days=40)).isoformat()
    campaign.post("/rollout-studio/%s/plan" % campaign._cid,
                  data={"post_id": pid, "action": "save",
                        "scheduled_date": moved})
    with appmod.app.app_context():
        assert ros.get_post(pid)["scheduled_date"] == moved


def test_a_partial_form_never_blanks_a_field_it_did_not_carry(campaign):
    """The board sends a caption and no date; the calendar sends a date
    and no caption. Either one wiping the other would lose work."""
    with appmod.app.app_context():
        post = ros.list_posts(campaign._cid)[0]
        pid, original_caption = post["id"], post["caption"]
    assert original_caption
    campaign.post("/rollout-studio/%s/plan" % campaign._cid,
                  data={"post_id": pid, "action": "save",
                        "scheduled_date": "2027-01-01"})
    with appmod.app.app_context():
        after = ros.get_post(pid)
    assert after["caption"] == original_caption, "the caption was wiped"
    assert after["scheduled_date"] == "2027-01-01"


def test_filtering_says_how_much_it_is_hiding(campaign):
    """A filtered list that looks like the whole plan is a lie of omission."""
    with appmod.app.app_context():
        total = len(ros.list_posts(campaign._cid))
    page = campaign.get("/rollout-studio/%s/plan?view=list&platform=tiktok"
                        % campaign._cid).get_data(as_text=True)
    assert "of %d shown" % total in page


def test_an_unknown_view_falls_back_rather_than_failing(campaign):
    r = campaign.get("/rollout-studio/%s/plan?view=nonsense" % campaign._cid)
    assert r.status_code == 200
    assert 'name="caption"' in r.get_data(as_text=True), "the list view"


def test_a_stranger_cannot_open_the_plan(campaign):
    other = appmod.app.test_client()
    email = "plan-other-%s@example.net" % uuid.uuid4().hex[:8]
    other.post("/signup", data={"name": "X", "email": email, "password": PASSWORD})
    other.post("/login", data={"email": email, "password": PASSWORD})
    r = other.get("/rollout-studio/%s/plan" % campaign._cid)
    assert r.status_code in (302, 403, 404)

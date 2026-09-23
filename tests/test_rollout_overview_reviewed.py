"""The Rollout Studio overview once every post is out of draft.

Found by the make-it-real pass of 2026-09-23: rollout_overview read
`user["id"]` for the learned next step without ever defining `user`. The
branch only runs when every post has been approved, rejected or marked
posted, so the page answered with an error at exactly the moment an
artist had finished reviewing the plan. The unit tests of
rollout_learning covered the helper and never the page.

Held here through the real pages: sign up, build a rollout, review every
post on the plan page, then open the overview.
"""
import uuid
from datetime import date, timedelta

import pytest

import app as appmod
import db as store
import rollout_engine
import rollout_learning
import rollout_store as ros

PASSWORD = "overview-reviewed-123"


@pytest.fixture
def campaign(monkeypatch):
    monkeypatch.setenv("SIGNUP_MODE", "open")
    c = appmod.app.test_client()
    email = "ro-review-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Artist", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    with appmod.app.app_context():
        uid = store.get_user_by_email(email)["id"]
        cid = ros.create_campaign(uid, {
            "title": "Cold Corner", "artist_name": "King 810",
            "release_date": (date.today() + timedelta(days=14)).isoformat(),
            "rollout_length": 7, "goal": "streams", "tone": "raw",
            "platforms": ["tiktok", "x"]})
        for post in rollout_engine.generate_rollout(ros.get_campaign(cid)):
            ros.add_post(cid, post)
    c._cid = cid
    c._uid = uid
    return c


def _review_every_post(client, action="approve"):
    with appmod.app.app_context():
        posts = ros.list_posts(client._cid)
    assert len(posts) > 1
    for p in posts:
        r = client.post("/rollout-studio/%s/plan" % client._cid,
                        data={"post_id": p["id"], "action": action})
        assert r.status_code == 302
    with appmod.app.app_context():
        assert all(p["status"] != "draft" for p in ros.list_posts(client._cid))


def test_the_overview_opens_while_posts_are_still_drafts(campaign):
    r = campaign.get("/rollout-studio/%s" % campaign._cid)
    assert r.status_code == 200


def test_the_overview_opens_once_every_post_is_approved(campaign):
    _review_every_post(campaign, "approve")
    r = campaign.get("/rollout-studio/%s" % campaign._cid)
    assert r.status_code == 200, (
        "the page broke at the moment the artist finished reviewing")
    assert "Cold Corner" in r.get_data(as_text=True)


def test_the_overview_opens_once_every_post_is_rejected(campaign):
    _review_every_post(campaign, "reject")
    assert campaign.get("/rollout-studio/%s" % campaign._cid).status_code == 200


def test_the_learned_next_step_reads_the_signed_in_artists_history(campaign, monkeypatch):
    """The branch that crashed now runs, and it asks about THIS account's
    past rollouts: the learned line it returns is the one on the page."""
    asked = []

    def fake_report(ml_campaigns, *_a, **_k):
        asked.append(ml_campaigns)
        return {"platforms": {"finding": {"key": "tiktok", "lift": 42}},
                "phases": {}, "measured": True}

    seen_users = []
    real_list = appmod.mls.list_campaigns

    def spy_list(user_id):
        seen_users.append(user_id)
        return real_list(user_id)

    monkeypatch.setattr(rollout_learning, "report", fake_report)
    monkeypatch.setattr(appmod.mls, "list_campaigns", spy_list)
    _review_every_post(campaign, "approve")
    body = campaign.get("/rollout-studio/%s" % campaign._cid).get_data(as_text=True)
    assert asked, "the learned next step was never asked for"
    assert campaign._uid in seen_users
    line = rollout_learning.next_action_line(fake_report([]))
    assert line and line in body

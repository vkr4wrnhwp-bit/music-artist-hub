"""Video and images are made in Motion, not in Street Banker.

Owner, 2026-09-19: asked for a video editor and an image generator in
Rollout; ruled the same day that everything goes to Motion and comes back
into the Vault. So every Rollout page offers "Make it in Motion" (the suite
door, new tab) and "upload the finished file to your Vault", and none of
them promises an editor or a generator here. The Cover Studio keeps its
Pollinations cover art and is labelled as cover art.

The receiving endpoint for a hand-off Motion does not have yet is a stub
behind a flag that is off.
"""
import io

from app import create_app
from rollout_config import MOTION, MOTION_HANDOFF_FLAG
import rollout_engine

MOTION_DOOR = 'href="/suites/go/motion" target="_blank"'
VAULT_LINE = "upload the finished file to your Vault"

# Words that would claim an in-app editor or generator. None may appear on
# a Rollout page.
FORBIDDEN = ("video editor", "image generator", "edit video here",
             "renders your video", "generate a video", "generate an image",
             "Generate artwork")


def _client():
    client = create_app().test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    return client


def _campaign(client, with_video=True):
    data = {"title": "Motion Test", "artist_name": "Test Artist",
            "release_date": "2031-03-01", "rollout_length": "7",
            "goal": "presaves", "tone": "premium",
            "pf_instagram_reels": "1", "pf_tiktok": "1", "pf_x": "1",
            "lyrics": "Neon lights across the bay\nWe ride until the break of day"}
    if with_video:
        data["video_file"] = (io.BytesIO(b"0" * 128), "clip.mp4")
    r = client.post("/rollout-studio/new", data=data, content_type="multipart/form-data")
    return r.headers["Location"].split("/")[2]


def _clean(body):
    for phrase in FORBIDDEN:
        assert phrase.lower() not in body.lower(), phrase


def test_the_action_is_the_suite_door_and_has_no_em_dash():
    assert MOTION["href"] == "/suites/go/motion"
    assert MOTION["vault_href"] == "/vault"
    for value in MOTION.values():
        assert "—" not in value, value


def test_dashboard_and_new_form_point_at_motion_then_vault():
    client = _client()
    for path in ("/rollout-studio", "/rollout-studio/new"):
        body = client.get(path).get_data(as_text=True)
        assert MOTION_DOOR in body, path
        assert VAULT_LINE in body or "upload the finished file" in body, path
        _clean(body)


def test_overview_and_plan_carry_the_action_next_to_the_edit_plan():
    client = _client()
    cid = _campaign(client)
    client.post("/rollout-studio/%s/generate" % cid)
    overview = client.get("/rollout-studio/%s" % cid).get_data(as_text=True)
    assert MOTION["label"] in overview
    assert MOTION_DOOR in overview
    assert MOTION["then"] in overview
    _clean(overview)
    plan = client.get("/rollout-studio/%s/plan" % cid).get_data(as_text=True)
    assert "Video edit plan" in plan            # the brief stays
    assert MOTION_DOOR in plan
    assert MOTION["then"] in plan
    assert "then attach it to this post" in plan
    _clean(plan)


def test_the_edit_plan_names_motion_and_the_vault():
    campaign = {"title": "T", "artist_name": "A", "release_date": "2031-03-01",
                "rollout_length": 3, "goal": "presaves", "tone": "premium",
                "platforms": ["tiktok"]}
    posts = rollout_engine.generate_rollout(campaign, lyrics="", video_asset_id=7)
    plans = [p["edit_plan"] for p in posts if p.get("edit_plan")]
    assert plans
    for plan in plans:
        assert plan["make_in"] is MOTION
        assert plan["export_checklist"][0].startswith("In Motion:")
        assert any("Vault" in step for step in plan["export_checklist"])
    # No video yet: the next action says where to make one.
    line = rollout_engine.next_action(campaign, [{"status": "approved"}], [])
    assert "Motion" in line and "Vault" in line


def test_the_public_page_says_video_and_images_come_from_motion():
    body = create_app().test_client().get("/rollout").get_data(as_text=True)
    assert "Video and images are made in Motion" in body
    assert "Make the video and images in Motion" in body
    assert "Generate or organise the creative" not in body
    _clean(body)


def test_cover_studio_is_labelled_cover_art_not_an_image_generator():
    body = _client().get("/artwork").get_data(as_text=True)
    assert "Generate cover art" in body
    assert "Generate artwork" not in body
    assert 'alt="Generated cover art"' in body
    assert "Square cover art only" in body
    assert MOTION_DOOR in body
    assert "AI Artwork" in body                 # the working tool stays


def test_the_receiving_stub_is_invisible_until_flagged(monkeypatch):
    client = _client()
    monkeypatch.delenv(MOTION_HANDOFF_FLAG, raising=False)
    assert client.post("/api/vault/from-motion", json={"token": "x"}).status_code == 404
    monkeypatch.setenv(MOTION_HANDOFF_FLAG, "1")
    r = client.post("/api/vault/from-motion", json={"token": "x"})
    assert r.status_code == 501
    assert "MOTION_HANDOFF.md" in r.get_json()["error"]

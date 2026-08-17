"""Web-layer tests: every REACH screen renders inside the host application,
and the honest-labelling rules hold in the rendered HTML.

Covers Phase One scenarios 16, 33, 38 and the "no screen is a shell" bar.
"""

import pytest

from app import create_app
from reach import analytics, approvals, campaigns, catalog, drafts, humanactions, outcomes

from .conftest import first_ready_target


@pytest.fixture
def client():
    return create_app().test_client()


@pytest.fixture
def live_campaign(scouted, sender_ready):
    """A campaign with a full lifecycle: discovered, sent, answered, placed."""
    analytics.capture_baseline(scouted)
    humanactions.build_dsp_tasks(scouted)
    target = first_ready_target(scouted)
    drafts.generate(target["id"])
    approvals.approve(target["id"])
    approvals.send_approved(target["id"])
    outcomes.record_response(target["id"], outcomes.ACCEPT)
    outcomes.record_placement(target["id"], outcomes.EVIDENCE_URL,
                              url="https://bassforge.example/promo")
    return scouted


def page(client, path):
    response = client.get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}"
    return response.get_data(as_text=True)


# --- host integration -------------------------------------------------------

def test_reach_is_mounted_in_the_host_navigation(client):
    body = page(client, "/dashboard")
    assert 'href="/reach"' in body
    assert "REACH" in body
    # The host dashboard still works exactly as before.
    assert "Total Royalties" in body


def test_reach_index_lists_catalog_tracks(client):
    body = page(client, "/reach")
    assert "Midnight Drive" in body
    assert "Neon Dreams" in body
    assert "Synthwave Surfer" in body


def test_campaign_wizard_shows_unknown_profile_fields(client):
    recording = catalog.recording_for_host_song("velvet-static")
    body = page(client, f"/reach/new?recording_id={recording['id']}")
    assert "Track intelligence profile" in body
    assert "UNKNOWN" in body
    assert "Rights attestation" in body
    assert "Release readiness" in body


# --- campaign screens -------------------------------------------------------

@pytest.mark.parametrize("suffix,marker", [
    ("", "Campaign health"),
    ("/discover", "Planned query families"),
    ("/opportunities", "Pipeline"),
    ("/review", "Queue"),
    ("/outreach", "Sender health"),
    ("/responses", "Record a response"),
    ("/placements", "Record a placement"),
])
def test_campaign_screens_render_with_content(client, live_campaign, suffix, marker):
    body = page(client, f"/reach/campaigns/{live_campaign}{suffix}")
    assert marker in body


def test_opportunity_detail_shows_evidence_and_score_reasons(client, live_campaign):
    target = campaigns.targets(live_campaign)[0]
    body = page(client, f"/reach/campaigns/{live_campaign}/targets/{target['id']}")
    assert "Why do we know this?" in body
    assert "Why this score?" in body
    assert "Compliance decision" in body
    assert "retrieved" in body


def test_review_screen_shows_the_exact_payload(client, live_campaign):
    body = page(client, f"/reach/campaigns/{live_campaign}/review")
    assert "Exactly what will be sent" in body
    assert "Payload hash" in body
    assert "Source of every factual claim" in body
    assert "Independent verification of this address" in body


# --- global screens ---------------------------------------------------------

def test_provider_health_never_shows_a_fake_green(client, live_campaign):
    body = page(client, "/reach/providers")
    assert "NOT CONNECTED" in body
    assert "MANUAL ONLY" in body
    assert "APPROVAL REQUIRED" in body
    # Spotify's restrictions are stated on the screen, not buried in code.
    assert "LLM blocked" in body
    assert "Contact resolution blocked" in body


def test_needs_you_lists_dsp_tasks_with_reasons(client, live_campaign):
    body = page(client, "/reach/needs-you")
    assert "Spotify for Artists editorial pitch" in body
    assert "Amazon Music for Artists new-release pitch" in body
    assert "Pandora AMP submission" in body
    assert "Why it isn&#39;t automated" in body or "Why it isn't automated" in body
    assert "Opening the destination does not mark this submitted." in body


def test_settings_shows_flags_suppression_and_audit(client, live_campaign):
    body = page(client, "/reach/settings")
    assert "reach.autopilot" in body
    assert "Emergency stops" in body
    assert "Audit trail" in body
    assert "Chain verified" in body


def test_relationships_screen_renders(client, live_campaign):
    body = page(client, "/reach/relationships")
    assert "Relationships" in body


def test_fixture_mode_is_labelled_in_the_interface(client, live_campaign):
    body = page(client, "/reach")
    assert "Fixture corpus" in body


# --- API endpoints ----------------------------------------------------------

def test_evidence_endpoint_returns_provenance(client, live_campaign):
    target = campaigns.targets(live_campaign)[0]
    response = client.get(f"/reach/evidence/outlet/{target['outlet_id']}")
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["evidence"]
    assert payload["evidence"][0]["source_url"]


def test_provider_policy_endpoint_exposes_the_machine_readable_record(client):
    payload = client.get("/reach/providers/spotify/policy").get_json()
    assert payload["policy"]["maySendDataToLanguageModel"] is False
    assert payload["usage"]["maySendToLLM"] is False


def test_webhook_rejects_an_unsigned_request(client, live_campaign):
    response = client.post("/reach/webhooks/email", json={"type": "bounce",
                                                          "email": "x@example.test"})
    assert response.status_code == 401


def test_webhook_suppresses_on_a_signed_bounce(client, live_campaign):
    from reach import contacts

    response = client.post(
        "/reach/webhooks/email",
        json={"type": "bounce", "email": "bouncer@example.test"},
        headers={"X-Reach-Signature": "test-webhook-secret"},
    )
    assert response.get_json()["outcome"] == "SUPPRESSED"
    assert contacts.is_suppressed("bouncer@example.test") is not None


def test_campaign_creation_endpoint_rejects_an_incomplete_profile(client):
    recording = catalog.recording_for_host_song("velvet-static")
    catalog.attest_rights(recording["id"])
    response = client.post("/reach/campaigns", json={"recording_id": recording["id"]})
    payload = response.get_json()
    assert payload["ok"] is False
    assert "incomplete" in payload["error"]


def test_metrics_on_the_overview_match_the_database(client, live_campaign):
    metrics = analytics.campaign_metrics(live_campaign)
    body = page(client, f"/reach/campaigns/{live_campaign}")
    assert str(metrics["discovered"]) in body
    assert str(metrics["placed"]) in body

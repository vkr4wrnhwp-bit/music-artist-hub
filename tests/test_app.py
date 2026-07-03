from app import create_app
from royalty_data import get_platform_balances, reset_claim_state, reset_connection_state, reset_split_state


def test_index_redirects_to_dashboard():
    client = create_app().test_client()
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/dashboard"


def test_dashboard_renders_expected_content():
    client = create_app().test_client()
    response = client.get("/dashboard")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Total Royalties" in body
    assert "Spotify" in body
    assert "Midnight Drive" in body


def test_dashboard_includes_set_goal_ui():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert 'id="set-goal-btn"' in body
    assert 'id="goal-modal"' in body
    assert 'id="goal-amount"' in body
    assert 'id="goal-type"' in body
    assert 'id="goal-deadline"' in body


def test_dashboard_includes_leak_alerts_ui():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Royalty Leak Alerts" in body
    assert 'id="alert-filters"' in body
    assert 'data-filter="High"' in body
    assert 'data-filter="Resolved"' in body


def test_resolve_alert_returns_result_message():
    client = create_app().test_client()
    response = client.post("/alerts/pending-negotiation/resolve")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["message"]


def test_resolve_unknown_alert_returns_404():
    client = create_app().test_client()
    response = client.post("/alerts/not-a-real-id/resolve")
    assert response.status_code == 404


def test_dashboard_includes_add_connection_ui():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert 'id="add-connection-btn"' in body
    assert 'id="connections-modal"' in body
    assert 'id="connection-search"' in body
    assert "YouTube Music" in body


def test_dashboard_includes_health_score():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Royalty Health Score" in body
    assert "Recommended actions" in body
    assert "out of 100" in body


def test_dashboard_includes_scanner_ui():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert 'id="scan-btn"' in body
    assert "Missing Money Scanner" in body


def test_scan_endpoint_returns_findings():
    client = create_app().test_client()
    response = client.post("/scan/missing-royalties")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["count"] == len(data["findings"])
    assert data["count"] > 0
    assert data["total_estimated"] > 0
    required = {"id", "source", "issue_type", "estimated_value", "confidence", "recommended_action"}
    assert required <= set(data["findings"][0].keys())


def test_connect_and_disconnect_platform():
    client = create_app().test_client()
    try:
        response = client.post("/connections/youtube-music/connect")
        assert response.status_code == 200
        assert response.get_json() == {"ok": True, "status": "connected"}
        assert "YouTube Music" in [b.platform for b in get_platform_balances()]

        response = client.post("/connections/youtube-music/disconnect")
        assert response.status_code == 200
        assert "YouTube Music" not in [b.platform for b in get_platform_balances()]
    finally:
        reset_connection_state()


def test_connect_unknown_platform_returns_404():
    client = create_app().test_client()
    response = client.post("/connections/not-a-platform/connect")
    assert response.status_code == 404


def test_dashboard_includes_song_breakdown_and_metadata_ui():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Song-Level Royalty Breakdown" in body
    assert "Metadata Completion" in body
    assert 'id="song-drawer"' in body
    assert "Midnight Drive" in body


def test_song_detail_endpoint_returns_full_payload():
    client = create_app().test_client()
    response = client.get("/songs/midnight-drive")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    song = data["song"]
    required = {
        "isrc", "iswc", "upc", "master_owner", "splits", "platform_earnings",
        "check_status", "missing_issues", "recent_payouts", "metadata_score",
        "registration_score",
    }
    assert required <= set(song.keys())
    assert song["title"] == "Midnight Drive"


def test_song_detail_unknown_id_returns_404():
    client = create_app().test_client()
    response = client.get("/songs/not-a-real-song")
    assert response.status_code == 404


def test_dashboard_includes_payout_calendar():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Payout Calendar" in body
    assert "Upcoming total" in body


def test_dashboard_includes_claim_workflow_ui():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Claim Workflow" in body
    assert "Detected" in body


def test_advance_claim_route():
    client = create_app().test_client()
    try:
        response = client.post("/claims/youtube-music-uncollected/advance")
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["status"] == "Needs Info"
    finally:
        reset_claim_state()


def test_reject_claim_route():
    client = create_app().test_client()
    try:
        response = client.post("/claims/youtube-music-uncollected/reject")
        assert response.status_code == 200
        assert response.get_json() == {"ok": True, "status": "Rejected"}
    finally:
        reset_claim_state()


def test_advance_unknown_claim_returns_404():
    client = create_app().test_client()
    response = client.post("/claims/not-a-real-claim/advance")
    assert response.status_code == 404


def test_dashboard_includes_smart_recommendations():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Smart Recommendations" in body
    assert "urgency" in body


def test_dashboard_includes_catalog_value_and_advance_eligibility():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Catalog Value Estimate" in body
    assert "Advance Eligibility" in body
    assert 'id="custom-multiple"' in body
    assert "Suggested advance amount" in body


def test_add_split_route():
    client = create_app().test_client()
    try:
        response = client.post(
            "/songs/midnight-drive/splits",
            json={"collaborator": "New Collaborator", "role": "Mixer", "percentage": 15.0},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert len(data["splits"]) == 4
        assert data["split_total"] == 115.0
    finally:
        reset_split_state()


def test_add_split_missing_fields_returns_400():
    client = create_app().test_client()
    response = client.post("/songs/midnight-drive/splits", json={"collaborator": "", "role": "Mixer", "percentage": 10.0})
    assert response.status_code == 400


def test_add_split_unknown_song_returns_404():
    client = create_app().test_client()
    response = client.post(
        "/songs/not-a-real-song/splits",
        json={"collaborator": "X", "role": "Writer", "percentage": 100.0},
    )
    assert response.status_code == 404


def test_remove_split_route():
    client = create_app().test_client()
    try:
        client.post("/songs/midnight-drive/splits", json={"collaborator": "Temp", "role": "Mixer", "percentage": 10.0})
        response = client.post("/songs/midnight-drive/splits/3/remove")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["splits"]) == 3
    finally:
        reset_split_state()


def test_toggle_split_route():
    client = create_app().test_client()
    try:
        response = client.post("/songs/neon-dreams/splits/1/toggle")
        assert response.status_code == 200
        data = response.get_json()
        assert data["splits"][1]["confirmed"] is True
    finally:
        reset_split_state()


def test_toggle_split_unknown_song_returns_404():
    client = create_app().test_client()
    response = client.post("/songs/not-a-real-song/splits/0/toggle")
    assert response.status_code == 404


def test_dashboard_includes_split_manager_ui():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert 'id="add-split-form"' in body
    assert 'id="split-collaborator"' in body
    assert 'id="song-drawer-split-warning"' in body

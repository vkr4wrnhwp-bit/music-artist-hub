from app import create_app
from royalty_data import get_platform_balances, reset_connection_state


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

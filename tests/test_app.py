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


def test_complete_action_returns_result_message():
    client = create_app().test_client()
    response = client.post("/actions/pending-negotiation/complete")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["message"]


def test_complete_unknown_action_returns_404():
    client = create_app().test_client()
    response = client.post("/actions/not-a-real-id/complete")
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

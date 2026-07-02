from app import create_app


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

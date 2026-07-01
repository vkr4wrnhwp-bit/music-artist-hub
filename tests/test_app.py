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


def test_variant_routes_render():
    client = create_app().test_client()
    for path in ("/v2", "/v3"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Total Royalties" in body
        assert "Spotify" in body

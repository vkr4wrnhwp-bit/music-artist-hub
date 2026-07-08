from app import create_app
from royalty_data import (
    get_platform_balances,
    reset_claim_state,
    reset_collaborator_state,
    reset_connection_state,
    reset_fix_status_state,
    reset_registration_wizard_state,
    reset_split_state,
)


def test_index_renders_landing_page():
    client = create_app().test_client()
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "STREET BANKER" in body
    assert "ARTIST INFRASTRUCTURE" in body
    assert "THE ARTIST" in body  # hero headline
    assert "ROYALTY SWEEP" in body  # engine section label (or SVG desk)


def test_landing_page_nav_and_ctas_link_into_the_app():
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    assert 'href="/overview"' in body
    assert "Start Free Scan" in body
    assert "Login" in body


def _all_landing_hrefs(config):
    hrefs = [l["href"] for l in config["nav"]["links"]]
    hrefs += [a["href"] for a in config["nav"]["actions"]]
    hrefs += [cta["href"] for cta in config["hero"]["ctas"]]
    hrefs += [config["hero_visual"]["recoveries_cta"]["href"]]
    hrefs += [f["link"]["href"] for f in config["features"]]
    hrefs += [config["lanes"]["cta"]["href"]]
    hrefs += [i["href"] for i in config["lanes"]["items"]]
    hrefs += [config["royalty_sweep"]["cta"]["href"], config["royalty_sweep"]["engine"]["results_cta"]["href"]]
    hrefs += [s["href"] for s in config["services"]["items"]]
    for p in config.get("pillars", []):
        hrefs.append(p["cta"]["href"])
        if p.get("secondary_cta"):
            hrefs.append(p["secondary_cta"]["href"])
    for col in config["footer"]["columns"]:
        hrefs += [l["href"] for l in col["links"]]
    return hrefs


def test_landing_page_links_all_resolve():
    """Every landing link points at a real GET route or an on-page anchor
    that exists -- no dead placeholder routes or hashes."""
    import re
    from landing_config import get_landing_config

    app = create_app()
    body = app.test_client().get("/").get_data(as_text=True)
    page_ids = set(re.findall(r'id="([^"]+)"', body))
    real_routes = {rule.rule for rule in app.url_map.iter_rules()
                   if "GET" in rule.methods and "<" not in rule.rule}
    # Prefixes for parameterized GET routes, e.g. "/services/<slug>" -> "/services/".
    param_prefixes = [rule.rule.split("<", 1)[0] for rule in app.url_map.iter_rules()
                      if "GET" in rule.methods and "<" in rule.rule]

    for href in _all_landing_hrefs(get_landing_config()):
        if href.startswith("#"):
            assert href[1:] in page_ids, f"dead anchor: {href}"
        elif href.startswith("http"):
            continue
        else:
            ok = href in real_routes or any(
                href.startswith(pfx) and len(href) > len(pfx) for pfx in param_prefixes)
            assert ok, f"unknown route: {href}"


def test_landing_command_desk_shows_all_sources():
    # The command desk lists these sources; when a photo replaces the built-in
    # SVG the names live in the image, so assert the editable config data.
    from landing_config import get_landing_config
    sources = [s["name"] for s in get_landing_config()["hero_visual"]["connected_sources"]]
    for platform in ["Spotify", "Apple Music", "ASCAP", "BMI", "The MLC", "SoundExchange", "YouTube Content ID"]:
        assert platform in sources


def test_landing_page_includes_feature_cards():
    # Features may render as built-in cards or as the clickable image whose
    # region aria-labels carry the same names -- match case-insensitively.
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True).lower()
    for name in ["find missing money", "connect everything", "maximize your value", "you stay in control"]:
        assert name in body


def test_landing_page_includes_trust_strip():
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    assert "TRUSTED BY INDEPENDENT ARTISTS AND LABELS WORLDWIDE" in body


def test_landing_includes_lanes_engine_and_pillars():
    body = create_app().test_client().get("/").get_data(as_text=True)
    # Lanes section renders (headline lives in the graphic when an image is set).
    assert 'id="infrastructure"' in body
    assert "Explore The Three Lanes" in body
    assert "THE RECOVERY ENGINE" in body
    # Pillar sections (one per part of the ecosystem) replaced the thin list.
    assert "Everything Street Banker Is" in body
    assert "Music Distribution" in body
    assert "The Industry Network" in body


def test_landing_pillars_config():
    from landing_config import get_landing_config
    pillars = get_landing_config()["pillars"]
    assert len(pillars) >= 5
    # Every pillar links at a real route or on-page target.
    for p in pillars:
        assert p["cta"]["href"].startswith("/")
        assert p["visual"]["type"] in {"stats", "cards", "avatars", "tiles"}


def test_scan_recovery_summary_route():
    client = create_app().test_client()
    response = client.post("/scan/recovery-summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    summary = data["summary"]
    required = {"estimated_uncollected", "flagged_issues", "affected_recordings", "ready_to_claim", "confidence_pct", "sources", "chart"}
    assert required <= set(summary.keys())
    assert data["scanned_at"]


def test_all_pages_render():
    client = create_app().test_client()
    for route in ["/overview", "/royalties", "/catalog", "/connections", "/recovery", "/valuation", "/reports", "/settings"]:
        response = client.get(route)
        assert response.status_code == 200, route


def test_dashboard_redirects_to_overview():
    client = create_app().test_client()
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"] == "/overview"


def test_nav_highlights_active_page():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
    assert 'href="/royalties"' in body
    assert "bg-amber-500/10 font-semibold text-amber-400" in body


def test_nav_includes_all_eight_routes():
    client = create_app().test_client()
    body = client.get("/overview").get_data(as_text=True)
    for href in ["/overview", "/royalties", "/catalog", "/connections", "/recovery", "/valuation", "/reports", "/settings"]:
        assert 'href="{}"'.format(href) in body


def test_overview_renders_command_center():
    client = create_app().test_client()
    response = client.get("/overview")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Your royalty command center." in body
    assert "Total Royalties Collected" in body


def test_overview_includes_goal_card_and_modal():
    client = create_app().test_client()
    body = client.get("/overview").get_data(as_text=True)
    assert 'id="edit-goal-btn"' in body
    assert 'id="goal-modal"' in body
    assert 'id="goal-amount"' in body
    assert 'id="goal-type"' in body
    assert 'id="goal-deadline"' in body


def test_overview_includes_health_score_card():
    client = create_app().test_client()
    body = client.get("/overview").get_data(as_text=True)
    assert "Royalty Health Score" in body
    assert "Improve Score" in body
    assert "/100" in body


def test_overview_includes_money_left_card():
    client = create_app().test_client()
    body = client.get("/overview").get_data(as_text=True)
    assert "Money Left on the Table" in body
    assert "Scan Now" in body
    assert 'href="/recovery"' in body


def test_overview_includes_action_center_and_payouts():
    client = create_app().test_client()
    body = client.get("/overview").get_data(as_text=True)
    assert "Action Center" in body
    assert "Recent Payouts" in body
    assert 'id="payout-drawer"' in body


def test_overview_includes_last_visit_summary():
    client = create_app().test_client()
    body = client.get("/overview").get_data(as_text=True)
    assert "What Changed Since Your Last Visit" in body
    assert "New royalties collected" in body
    assert "Tasks completed" in body
    assert "Catalog value increase" in body


def test_overview_includes_date_range_selector():
    client = create_app().test_client()
    body = client.get("/overview").get_data(as_text=True)
    assert 'id="date-range"' in body


def test_overview_includes_earnings_trend():
    client = create_app().test_client()
    body = client.get("/overview").get_data(as_text=True)
    assert "Earnings Trend" in body
    assert 'id="earningsChart"' in body


def test_recovery_includes_leak_alerts_ui():
    client = create_app().test_client()
    body = client.get("/recovery").get_data(as_text=True)
    assert "Royalty Leak Alerts" in body
    assert 'id="alert-filters"' in body
    assert 'data-filter="High"' in body
    assert 'data-filter="Resolved"' in body


def test_royalties_page_matches_tracking_dashboard():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
    assert "Track every royalty stream in one place." in body
    assert "Total Royalties" in body
    assert "Payouts Received" in body
    assert "Pending Payouts" in body
    assert "Platforms Connected" in body
    assert "Royalties by Source" in body
    assert 'id="royaltiesChart"' in body
    assert 'id="export-btn"' in body


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


def test_connections_page_matches_command_center():
    client = create_app().test_client()
    body = client.get("/connections").get_data(as_text=True)
    assert "Connect every source. Close every gap. Maximize every dollar." in body
    assert "Connection Health" in body
    assert "Connected Sources" in body
    assert "Missing Royalties Found" in body
    assert "Potential Yearly Value" in body


def test_connections_table_and_intelligence_column():
    client = create_app().test_client()
    body = client.get("/connections").get_data(as_text=True)
    assert "Connection Gaps" in body
    assert "Top Opportunities" in body
    assert "Recent Activity" in body
    assert "SoundExchange" in body
    assert "TikTok SoundOn" in body


def test_connections_has_all_tabs_and_controls():
    client = create_app().test_client()
    body = client.get("/connections").get_data(as_text=True)
    for tab in ["All Sources", "Audio Streaming", "Performance", "Mechanical", "Distributors"]:
        assert 'data-tab="{}"'.format(tab) in body
    assert 'data-tab="YouTube &amp; Social"' in body
    assert 'id="refresh-all-btn"' in body
    assert 'id="add-connection-btn"' in body
    assert 'id="status-filter"' in body


def test_connections_data_config_shapes():
    from connections_config import get_connections_data
    data = get_connections_data()
    assert len(data["sources"]) == 8
    assert data["summary"]["connected_pct"] == 75
    statuses = {s["status"] for s in data["sources"]}
    assert {"Connected", "Partial Connection", "Not Connected", "Invite Sent"} <= statuses
    assert len(data["opportunities"]) == 3
    assert len(data["recent_activity"]) == 4


def test_settings_links_to_connections_page():
    client = create_app().test_client()
    body = client.get("/settings").get_data(as_text=True)
    assert 'href="/connections"' in body


def test_settings_includes_account_profile_ui():
    client = create_app().test_client()
    body = client.get("/settings").get_data(as_text=True)
    assert "Account Profile" in body
    assert 'id="profile-form"' in body
    assert 'id="profile-name"' in body
    assert 'id="profile-email"' in body
    assert 'id="profile-plan"' in body


def test_settings_includes_notification_preferences_ui():
    client = create_app().test_client()
    body = client.get("/settings").get_data(as_text=True)
    assert "Notification Preferences" in body
    assert 'id="notification-list"' in body
    assert "High severity leak alerts" in body
    assert "Weekly summary email" in body
    assert 'data-key="leak_high"' in body
    assert 'data-key="new_song_detected"' in body


def test_recovery_includes_scanner_ui():
    client = create_app().test_client()
    body = client.get("/recovery").get_data(as_text=True)
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


def test_catalog_page_matches_control_center():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert "Your entire catalog. Organized. Verified. Maximized." in body
    assert "Total Tracks" in body
    assert "Total Releases" in body
    assert "Registered Tracks" in body
    assert "Total ISRCs" in body
    assert "Blood in the Groove" in body


def test_catalog_has_all_five_tabs():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    for tab in ["Tracks", "Releases", "Songwriters", "Publishers", "Splits"]:
        assert 'data-tab="{}"'.format(tab) in body


def test_catalog_right_column_and_recently_added():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert "Catalog Health" in body
    assert "Metadata Issues" in body
    assert "Catalog Value (Estimated)" in body
    assert "Recently Added" in body
    assert "Improve Catalog Health" in body


def test_catalog_includes_add_release_and_filters():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert 'id="add-release-modal"' in body
    assert 'id="status-filter"' in body
    assert 'id="genre-filter"' in body
    assert 'id="source-filter"' in body


def test_sidebar_account_is_config_driven():
    from catalog_config import get_account
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    account = get_account()
    assert account["name"] in body
    assert account["plan"] in body


def test_base_includes_song_drawer():
    client = create_app().test_client()
    for route in ["/overview", "/royalties", "/catalog"]:
        body = client.get(route).get_data(as_text=True)
        assert 'id="song-drawer"' in body


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


def test_royalties_includes_payout_calendar():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
    assert "Payout Calendar" in body
    assert "Upcoming total" in body


def test_recovery_includes_claim_workflow_ui():
    client = create_app().test_client()
    body = client.get("/recovery").get_data(as_text=True)
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


def test_recovery_includes_smart_recommendations():
    client = create_app().test_client()
    body = client.get("/recovery").get_data(as_text=True)
    assert "Smart Recommendations" in body
    assert "urgency" in body


def test_valuation_includes_catalog_value_and_advance_eligibility():
    client = create_app().test_client()
    body = client.get("/valuation").get_data(as_text=True)
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


def test_base_includes_split_manager_ui():
    client = create_app().test_client()
    body = client.get("/overview").get_data(as_text=True)
    assert 'id="add-split-form"' in body
    assert 'id="split-collaborator"' in body
    assert 'id="song-drawer-split-warning"' in body


def test_base_includes_collapsible_section_script():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert "section-chevron" in body
    assert "royaltySweep.collapsed." in body


def test_recovery_includes_fixes_queue_ui():
    client = create_app().test_client()
    body = client.get("/recovery").get_data(as_text=True)
    assert "Fixes Needed Queue" in body
    assert 'id="fixes-queue-list"' in body
    assert "Fix Now" in body
    assert "Mark Complete" in body


def test_recovery_includes_top_royalty_leaks():
    client = create_app().test_client()
    body = client.get("/recovery").get_data(as_text=True)
    assert "Top Royalty Leaks" in body


def test_recovery_includes_command_center_header():
    client = create_app().test_client()
    body = client.get("/recovery").get_data(as_text=True)
    assert "Estimated Uncollected" in body
    assert "Ready to Claim" in body
    assert "Affected Recordings" in body
    assert 'id="recoveryChart"' in body
    assert "Top Sources" in body


def test_catalog_releases_tab_lists_releases():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert 'id="tab-Releases"' in body
    assert "The Collection Vol. 1" in body
    assert "Survival Mode" in body


def test_valuation_includes_royalty_forecast():
    client = create_app().test_client()
    body = client.get("/valuation").get_data(as_text=True)
    assert "Royalty Forecast" in body
    assert "Conservative" in body
    assert "Aggressive" in body


def test_valuation_includes_catalog_value_tracker():
    client = create_app().test_client()
    body = client.get("/valuation").get_data(as_text=True)
    assert "Catalog Value Tracker" in body
    assert 'id="value-tracker-current"' in body


def test_catalog_splits_tab_lists_splits():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert 'id="tab-Splits"' in body
    assert "Collaborator" in body
    assert "Conflict" in body


def test_catalog_metadata_issues_have_counts():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert "Missing ISRCs" in body
    assert "Unregistered Tracks" in body
    assert "Split Conflicts" in body


def test_reports_page_includes_report_library():
    client = create_app().test_client()
    body = client.get("/reports").get_data(as_text=True)
    assert "Investor Snapshot" in body
    assert "Recently Generated" in body
    assert "Scheduled Reports" in body
    assert "Report Types" in body


def test_reports_data_config_shapes():
    from reports_config import get_reports_data
    data = get_reports_data()
    assert data["summary"]["total_reports"] == len(data["categories"][0]["reports"]) + sum(
        len(c["reports"]) for c in data["categories"][1:]
    )
    assert [c["name"] for c in data["categories"]] == ["Financial", "Recovery", "Rights", "Investor"]
    assert data["formats"] and data["scheduled"]
    assert all("tone" in c for c in data["categories"])


def test_epk_page_includes_press_kit():
    client = create_app().test_client()
    body = client.get("/epk").get_data(as_text=True)
    assert 'id="epk-document"' in body
    assert "Biography" in body
    assert "Top Tracks" in body
    assert "Press Kit Sections" in body
    assert "section-toggle" in body


def test_epk_sidebar_and_export():
    client = create_app().test_client()
    assert 'href="/epk"' in client.get("/links").get_data(as_text=True)
    resp = client.post("/epk/export")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] and data["filename"].endswith(".pdf")
    assert "press-kit" in data["filename"]


def test_epk_data_config_shapes():
    from epk_config import get_epk_data
    from catalog_config import get_account
    data = get_epk_data(get_account(), {"mid": 296400.0})
    assert data["name"] == get_account()["name"]
    assert len(data["stats"]) == 4
    assert data["top_tracks"]
    # Top tracks sorted by streams descending.
    streams = [t["streams"] for t in data["top_tracks"]]
    assert streams == sorted(streams, reverse=True)
    assert all(s["key"] for s in data["sections"])


def test_artwork_page_includes_generator():
    client = create_app().test_client()
    body = client.get("/artwork").get_data(as_text=True)
    assert 'id="cover-frame"' in body
    assert "AI Concept" in body
    assert "colorway-btn" in body
    assert 'href="/artwork"' in body


def test_artwork_generate_endpoint():
    client = create_app().test_client()
    resp = client.post("/artwork/generate", json={"prompt": "warm ember sunset fire heat"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"]
    assert data["suggestion"]["colorway_id"] == "ember"
    assert "template_id" in data["suggestion"]


def test_smart_links_page_and_create():
    from links_config import reset_smart_links_state
    reset_smart_links_state()
    client = create_app().test_client()
    body = client.get("/links").get_data(as_text=True)
    assert 'id="links-list"' in body
    assert "Create Smart Link" in body
    assert 'href="/links"' in body
    ok = client.post("/links/create", json={"title": "New Single", "platforms": ["Spotify", "TikTok"]})
    assert ok.status_code == 200
    link = ok.get_json()["link"]
    assert link["slug"] == "new-single"
    assert link["url"].endswith("/new-single")
    bad = client.post("/links/create", json={"title": "", "platforms": []})
    assert bad.status_code == 400


def test_links_data_config_shapes():
    from links_config import get_links_data, reset_smart_links_state
    reset_smart_links_state()
    data = get_links_data()
    assert data["summary"]["total_links"] == len(data["links"])
    assert data["summary"]["total_clicks"] == sum(l["clicks"] for l in data["links"])
    assert all("url" in l and "platform_logos" in l for l in data["links"])
    assert data["platforms"]


def test_publishing_page_includes_compositions():
    client = create_app().test_client()
    body = client.get("/publishing").get_data(as_text=True)
    assert "Publishing Administration" in body
    assert "Your Compositions" in body
    assert "Performance Income" in body
    assert "Registration Gaps" in body
    assert 'href="/publishing"' in body


def test_publishing_data_config_shapes():
    from publishing_config import get_publishing_data
    data = get_publishing_data()
    assert data["summary"]["total_works"] == len(data["works"])
    assert data["summary"]["pro_registered"] <= data["summary"]["total_works"]
    # Uncollected total is the sum of per-work uncollected estimates.
    assert round(sum(w["uncollected"] for w in data["works"]), 2) == data["summary"]["uncollected_total"]
    assert len(data["issues"]) == 3
    # A work missing MLC registration should carry a positive uncollected estimate.
    unreg = [w for w in data["works"] if not w["mlc_registered"]]
    assert all(w["uncollected"] > 0 for w in unreg)


def test_tier2_pages_render_and_are_in_nav():
    client = create_app().test_client()
    nav = client.get("/overview").get_data(as_text=True)
    for href in ("/documents", "/identifiers", "/conflicts", "/releases", "/registration"):
        assert 'href="%s"' % href in nav
        assert client.get(href).status_code == 200
    # Grouped sidebar sections are split across product worlds now.
    for group in ("Collect", "Catalog", "Value", "Account"):
        assert ">%s<" % group in nav
    promote_nav = client.get("/links").get_data(as_text=True)
    for group in ("Grow", "Promote"):
        assert ">%s<" % group in promote_nav


def test_documents_page_content():
    body = create_app().test_client().get("/documents").get_data(as_text=True)
    assert "Documents Vault" in body
    assert "Vault Completeness" in body


def test_identifiers_page_content():
    body = create_app().test_client().get("/identifiers").get_data(as_text=True)
    assert "Identifiers" in body
    assert "ISRC" in body and "ISWC" in body and "UPC" in body


def test_conflicts_page_content():
    body = create_app().test_client().get("/conflicts").get_data(as_text=True)
    assert "Rights Conflict Center" in body


def test_releases_page_content():
    body = create_app().test_client().get("/releases").get_data(as_text=True)
    assert "Release Scheduler" in body
    assert "Readiness Checklist" in body


def test_registration_page_and_complete_step():
    client = create_app().test_client()
    body = client.get("/registration").get_data(as_text=True)
    assert "Registration Wizard" in body
    # The completion endpoint the page posts to should advance a missing target.
    resp = client.post("/songs/neon-dreams/registration-wizard/mlc/complete")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] and data["wizard"]["status"]["mlc"] is True


def test_neighboring_rights_page_content():
    client = create_app().test_client()
    body = client.get("/neighboring-rights").get_data(as_text=True)
    assert "Neighboring Rights" in body
    assert "SoundExchange" in body
    assert "Collection Societies" in body
    assert 'href="/neighboring-rights"' in body


def test_neighboring_rights_data_config_shapes():
    from neighboring_rights_config import get_neighboring_rights_data
    data = get_neighboring_rights_data()
    assert data["summary"]["recordings"] == len(data["recordings"])
    # SoundExchange is the first society and reflects real registration.
    assert data["societies"][0]["name"] == "SoundExchange"
    assert data["summary"]["territories_total"] == len(data["societies"])
    # Every recording carries a positive uncollected estimate (intl always uncollected).
    assert all(r["uncollected"] > 0 for r in data["recordings"])
    assert round(sum(r["uncollected"] for r in data["recordings"]), 2) == data["summary"]["uncollected_total"]


def test_sync_page_content():
    client = create_app().test_client()
    body = client.get("/sync").get_data(as_text=True)
    assert "Sync / Licensing" in body
    assert "Placements" in body
    assert "Incoming Requests" in body
    assert 'href="/sync"' in body


def test_sync_data_config_shapes():
    from sync_config import get_sync_data
    from royalty_data import get_songs
    data = get_sync_data()
    assert data["placements"] and data["requests"] and data["opportunities"]
    # Placements reference real catalog song titles.
    titles = {s.title for s in get_songs()}
    assert all(p["song"] in titles for p in data["placements"])
    # Sync income counts only live placements.
    live = round(sum(p["fee"] for p in data["placements"] if p["status"] == "Live"), 2)
    assert data["summary"]["sync_income"] == live


def test_territories_page_content():
    client = create_app().test_client()
    body = client.get("/territories").get_data(as_text=True)
    assert "Territories" in body
    assert "Earnings by Territory" in body
    assert 'href="/territories"' in body


def test_territories_data_config_shapes():
    from territories_config import get_territories_data
    data = get_territories_data()
    assert data["territories"]
    # Sorted by earnings descending.
    earnings = [t["earnings"] for t in data["territories"]]
    assert earnings == sorted(earnings, reverse=True)
    # Only non-collecting territories carry an uncollected gap.
    assert all((t["uncollected"] > 0) == (not t["collecting"]) for t in data["territories"])
    assert round(sum(t["uncollected"] for t in data["territories"]), 2) == data["summary"]["uncollected_total"]


def test_mechanicals_page_content():
    client = create_app().test_client()
    body = client.get("/mechanicals").get_data(as_text=True)
    assert "Mechanical Royalties" in body
    assert "Black Box" in body
    assert 'href="/mechanicals"' in body


def test_mechanicals_data_config_shapes():
    from mechanicals_config import get_mechanicals_data
    data = get_mechanicals_data()
    s = data["summary"]
    assert round(s["matched_total"] + s["blackbox_total"], 2) == s["mechanical_total"]
    # Unmatched works contribute to the black box, matched ones don't.
    for w in data["works"]:
        assert (w["blackbox_amount"] > 0) == (not w["mlc_matched"])


def test_mechanicals_agree_with_publishing():
    from mechanicals_config import get_mechanicals_data
    from publishing_config import get_publishing_data
    mech = {w["id"]: w["mechanical_total"] for w in get_mechanicals_data()["works"]}
    pub = {w["id"]: w["mechanical_estimate"] for w in get_publishing_data()["works"]}
    assert mech == pub


def test_funding_page_and_request():
    client = create_app().test_client()
    body = client.get("/funding").get_data(as_text=True)
    assert "Advance &amp; Funding" in body
    assert "Available Offers" in body
    assert 'href="/funding"' in body
    ok = client.post("/funding/request", json={"offer_id": "offer-royalty-advance"})
    assert ok.status_code == 200 and ok.get_json()["ok"]
    assert ok.get_json()["reference"].startswith("REQ-")
    bad = client.post("/funding/request", json={"offer_id": "nope"})
    assert bad.status_code == 400


def test_funding_offers_derive_from_advance():
    from funding_config import get_funding_data
    elig = {"suggested_advance": 70000, "tier": "Eligible", "score": 95}
    data = get_funding_data(elig)
    assert data["eligibility"]["suggested_advance"] == 70000
    # Recommended offer matches the suggested advance.
    rec = next(o for o in data["offers"] if o["recommended"])
    assert rec["amount"] == 70000
    # Total repayable exceeds the amount by the cost of funds.
    for o in data["offers"]:
        assert round(o["amount"] + o["cost"], 2) == o["total_repayable"]


def test_tax_page_content():
    client = create_app().test_client()
    body = client.get("/tax").get_data(as_text=True)
    assert "Tax Center" in body
    assert "Suggested Set-Aside" in body
    assert "Taxpayer Forms" in body
    assert 'href="/tax"' in body


def test_tax_data_config_shapes():
    from tax_config import get_tax_data
    data = get_tax_data()
    s = data["summary"]
    assert s["set_aside"] == round(s["ytd_earnings"] * s["set_aside_rate"] / 100, 2)
    assert s["forms_total"] == len(data["forms"])
    assert any(f["status"] == "Available" for f in data["forms"])
    assert {t["form"] for t in data["tax_profile"]} == {"W-9", "W-8BEN"}


def test_disputes_page_content():
    from disputes_config import reset_disputes_state
    reset_disputes_state()
    client = create_app().test_client()
    body = client.get("/disputes").get_data(as_text=True)
    assert "Dispute &amp; Audit Center" in body
    assert "Amount in Dispute" in body
    assert 'href="/disputes"' in body


def test_disputes_advance_flow():
    from disputes_config import reset_disputes_state, get_disputes_data
    reset_disputes_state()
    client = create_app().test_client()
    # disp-3 starts at "Filed" (stage_index 0) -> advancing moves to "Submitted".
    resp = client.post("/disputes/disp-3/advance")
    assert resp.status_code == 200
    assert resp.get_json()["stage"] == "Submitted"
    assert client.post("/disputes/nope/advance").status_code == 404
    reset_disputes_state()


def test_disputes_data_config_shapes():
    from disputes_config import get_disputes_data, reset_disputes_state
    reset_disputes_state()
    data = get_disputes_data()
    assert data["stages"] == ["Filed", "Submitted", "Under Review", "Resolved"]
    open_amt = round(sum(d["amount"] for d in data["disputes"] if not d["resolved"]), 2)
    assert data["summary"]["amount_in_dispute"] == open_amt


def test_tier3_pages_render_and_nav():
    client = create_app().test_client()
    nav = client.get("/links").get_data(as_text=True)
    for href in ("/audience", "/playlists", "/stats"):
        assert 'href="%s"' % href in nav
        assert client.get(href).status_code == 200


def test_audience_data_config_shapes():
    from audience_config import get_audience_data
    data = get_audience_data()
    assert data["trend"] and data["top_tracks"]
    assert sum(a["pct"] for a in data["age_brackets"]) == 100
    # Top tracks are ranked by streams.
    streams = [t["streams"] for t in data["top_tracks"]]
    assert streams == sorted(streams, reverse=True)


def test_stats_data_matches_catalog():
    from stats_config import get_stats_data
    from royalty_data import get_songs
    data = get_stats_data()
    assert data["summary"]["total_streams"] == sum(s.streams for s in get_songs())
    # Platform earnings share sums to ~100%.
    assert abs(sum(p["share_pct"] for p in data["platforms"]) - 100) < 0.5


def test_playlists_data_config_shapes():
    from playlists_config import get_playlists_data, reset_playlists_state
    reset_playlists_state()
    data = get_playlists_data()
    assert data["summary"]["total_pitches"] == len(data["pitches"])
    assert data["summary"]["placements"] == sum(1 for p in data["pitches"] if p["stage"] == "Added")


def test_notifications_page_and_mark_read():
    from notifications_config import reset_notifications_state
    reset_notifications_state()
    client = create_app().test_client()
    body = client.get("/notifications").get_data(as_text=True)
    assert "Notifications" in body
    assert 'href="/notifications"' in body
    assert client.post("/notifications/ntf-sys-welcome/read").get_json()["ok"]
    assert client.post("/notifications/read-all").get_json()["ok"]
    reset_notifications_state()


def test_global_search_finds_songs_and_sources():
    from search_config import search
    client = create_app().test_client()
    assert client.get("/search").status_code == 200
    assert 'action="/search"' in client.get("/overview").get_data(as_text=True)
    res = search("spotify")
    assert res["total"] >= 1
    assert any(g["type"] == "Sources" for g in res["groups"])
    assert search("")["total"] == 0


def test_billing_page_content():
    client = create_app().test_client()
    body = client.get("/billing").get_data(as_text=True)
    assert "Compare Plans" in body
    assert 'href="/billing"' in body


def test_team_page_renders_and_in_nav():
    client = create_app().test_client()
    assert 'href="/team"' in client.get("/overview").get_data(as_text=True)
    assert client.get("/team").status_code == 200


def test_onboarding_page_renders():
    client = create_app().test_client()
    body = client.get("/onboarding").get_data(as_text=True)
    assert "Connect your sources" in body


def test_real_auth_flow():
    import uuid
    client = create_app().test_client()
    email = "u%s@example.com" % uuid.uuid4().hex[:8]
    assert client.get("/login").status_code == 200
    assert client.get("/signup").status_code == 200
    # Signup -> onboarding; weak input rejected.
    ok = client.post("/signup", data={"name": "T", "email": email, "password": "secret1"})
    assert ok.status_code == 302 and "/onboarding" in ok.headers["Location"]
    dup = client.post("/signup", data={"name": "T", "email": email, "password": "secret1"})
    assert "already exists" in dup.get_data(as_text=True)
    assert client.post("/logout").status_code == 302
    # Login with right/wrong password.
    good = client.post("/login", data={"email": email, "password": "secret1"})
    assert good.status_code == 302
    bad = client.post("/login", data={"email": email, "password": "nope"})
    assert "Incorrect email or password" in bad.get_data(as_text=True)
    # One-click demo account works.
    assert client.post("/login/demo").status_code == 302


def test_statements_upload_and_real_findings():
    import io, uuid
    client = create_app().test_client()
    email = "s%s@example.com" % uuid.uuid4().hex[:8]
    # Requires login.
    assert client.get("/statements").status_code == 302
    client.post("/signup", data={"name": "S", "email": email, "password": "secret1"})
    client.post("/plan/switch", data={"plan": "pro"})  # Royalty Sweep is Pro tier
    csv_data = (b"Track Title,Store,Net Revenue,Sales Period\n"
                b"Midnight Drive,Spotify,120.50,2026-05\n"
                b"Midnight Drive,Apple Music,80.25,2026-05\n"
                b"Neon Dreams,Spotify,60.00,2026-05\n"
                b",Spotify,12.40,2026-05\n")
    up = client.post("/statements", data={"statement": (io.BytesIO(csv_data), "symphonic.csv")},
                     content_type="multipart/form-data")
    assert up.status_code == 302
    body = client.get("/statements").get_data(as_text=True)
    assert "273.15" in body            # real total
    assert "12.40" in body             # unmatched revenue detected
    assert "Coverage Gaps" in body     # Neon Dreams missing Apple Music
    # Real CSV export includes the uploaded rows.
    csv_out = client.get("/reports/royalty-report/download.csv")
    assert csv_out.status_code == 200 and "Midnight Drive" in csv_out.get_data(as_text=True)


def test_statement_engine_math():
    from statements_engine import parse_statement, analyze
    parsed = parse_statement("Song,Platform,Earnings\nA,Spotify,10\nA,Apple,20\nB,Spotify,5\n")
    assert parsed["error"] is None and len(parsed["rows"]) == 3
    a = analyze(parsed["rows"])
    assert a["total"] == 35.0
    assert a["by_source"][0]["source"] in ("Apple", "Spotify")
    # B earns on Spotify but not Apple -> one coverage gap, est = B's avg (5).
    assert a["coverage_gaps"][0]["title"] == "B"
    assert a["coverage_gaps"][0]["estimated_value"] == 5.0
    assert parse_statement("no,amount,columns\nx,y,z\n")["error"]


def test_real_smart_link_redirect_and_click():
    client = create_app().test_client()
    link = client.post("/links/create", json={"title": "Wire Test", "platforms": ["Spotify"]}).get_json()["link"]
    assert link["real"] and "/l/" in link["url"]
    r = client.get("/l/" + link["slug"])
    assert r.status_code == 302 and "spotify.com/search" in r.headers["Location"]
    assert client.get("/l/does-not-exist").status_code == 302  # falls back to /links
    assert "real clicks" in client.get("/links").get_data(as_text=True)


def test_inbox_persists_submissions():
    import uuid
    from network_config import reset_network_state
    reset_network_state()
    client = create_app().test_client()
    assert client.get("/inbox").status_code == 302  # requires login
    client.post("/signup", data={"name": "I", "email": "i%s@example.com" % uuid.uuid4().hex[:8], "password": "secret1"})
    client.post("/network/playlist/late-night-synth/submit", json={"song": "Midnight Drive"})
    client.post("/network/nova-reign/enquire", json={"city": "Chicago"})
    body = client.get("/inbox").get_data(as_text=True)
    assert "Playlist Submission" in body and "Booking Enquiry" in body
    reset_network_state()


def test_tier5_and_community_pages_render_and_nav():
    client = create_app().test_client()
    promote_nav = client.get("/links").get_data(as_text=True)
    fan_nav = client.get("/discover").get_data(as_text=True)
    for href in ("/insights", "/benchmark"):
        assert 'href="%s"' % href in promote_nav
        assert client.get(href).status_code == 200
    for href in ("/marketplace", "/network", "/fan-label", "/fans"):
        assert 'href="%s"' % href in fan_nav
        assert client.get(href).status_code == 200
    assert ">Intelligence<" in promote_nav
    assert ">Community<" in fan_nav


def test_insights_ranked_and_consolidated():
    from insights_config import get_insights_data
    from app import build_dashboard_context
    data = get_insights_data(build_dashboard_context()["smart_recommendations"])
    impacts = [i["impact"] for i in data["insights"]]
    assert impacts == sorted(impacts, reverse=True)
    # Consolidates more than one category (recovery + publishing/etc).
    assert data["summary"]["categories"] >= 2
    assert data["summary"]["total_impact"] == round(sum(impacts), 2)


def test_benchmark_uses_real_metrics():
    from benchmark_config import get_benchmark_data
    from royalty_data import get_songs
    data = get_benchmark_data()
    streams = next(m for m in data["metrics"] if m["label"] == "Total streams")
    assert streams["you"] == sum(s.streams for s in get_songs())
    assert data["summary"]["ahead"] + data["summary"]["behind"] == data["summary"]["metrics"]


def test_marketplace_post_flow():
    from community_config import reset_marketplace_state
    reset_marketplace_state()
    client = create_app().test_client()
    ok = client.post("/marketplace/post", json={"artist": "Me", "need": "Vocalist", "deal_type": "For Fun"})
    assert ok.status_code == 200 and ok.get_json()["ok"]
    bad = client.post("/marketplace/post", json={"artist": "", "need": "", "deal_type": "Nope"})
    assert bad.status_code == 400
    reset_marketplace_state()


def test_fan_label_vote_flow():
    from community_config import reset_fan_label_state, get_fan_label_data
    reset_fan_label_state()
    before = {d["id"]: d["votes"] for d in get_fan_label_data()["demos"]}
    client = create_app().test_client()
    resp = client.post("/fan-label/vote/demo-1")
    assert resp.status_code == 200 and resp.get_json()["votes"] == before["demo-1"] + 1
    assert client.post("/fan-label/vote/nope").status_code == 404
    reset_fan_label_state()


def test_fan_dashboard_content():
    body = create_app().test_client().get("/fans").get_data(as_text=True)
    assert "Fan Segments" in body and "Fan Leaderboard" in body


def test_capital_page_content_and_disclaimer():
    client = create_app().test_client()
    body = client.get("/capital").get_data(as_text=True)
    assert 'href="/capital"' in body
    assert "Fan Royalty Passes" in body
    assert "Royalty Futures Marketplace" in body
    assert "Roll the Dice" in body
    # Must carry the prominent simulated-demo disclaimer.
    assert "Simulated demo" in body
    assert "no royalties are actually assigned, transferred, or forfeited" in body


def test_capital_data_config_shapes():
    from capital_config import get_capital_data
    from royalty_data import get_songs
    data = get_capital_data()
    assert set(data.keys()) == {"passes", "crowdfunding", "futures", "staking", "dice"}
    titles = {s.title for s in get_songs()}
    assert data["passes"]["release"] in titles
    assert all(f["release"] in titles for f in data["futures"])
    assert data["crowdfunding"]["pct"] == round(data["crowdfunding"]["raised"] / data["crowdfunding"]["goal"] * 100)


def test_label_services_pages_and_nav():
    client = create_app().test_client()
    nav = client.get("/services").get_data(as_text=True)
    assert 'href="/services"' in nav
    assert 'href="/submit"' in nav
    assert ">Label Services<" in nav
    for path in ("/services", "/services/distribution", "/services/marketing", "/services/management", "/submit"):
        assert client.get(path).status_code == 200
    # Unknown service slug redirects back to the hub.
    assert client.get("/services/nope").status_code == 302


def test_label_services_content_from_site():
    client = create_app().test_client()
    hub = client.get("/services").get_data(as_text=True)
    # Platform branding is Street Banker; the AIW Shopify store is only a link.
    assert "Street Banker" in hub
    assert "artiswarrecords.com" in hub  # store link retained
    assert "team.summitarts@gmail.com" in hub
    assert "200+" in hub
    dist = client.get("/services/distribution").get_data(as_text=True)
    assert "No physical or digital set-up fees" in dist
    assert "Content ID" in dist  # UGC monetization sell point
    submit = client.get("/submit").get_data(as_text=True)
    assert "artiswarrecords@gmail.com" in submit
    assert 'href="/epk"' in submit  # submissions tie into the EPK builder


def test_landing_links_to_label_services():
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    assert 'href="/services"' in body


def test_network_directory_filters_and_sort():
    from network_config import get_network_data, reset_network_state
    reset_network_state()
    client = create_app().test_client()
    assert client.get("/network").status_code == 200
    # Role filter narrows results to that role only.
    data = get_network_data({"role": "Producer"})
    assert data["people"] and all(p["role"] == "Producer" for p in data["people"])
    # Genre filter.
    house = get_network_data({"genre": "House"})
    assert all("House" in p["genres"] for p in house["people"])
    # Name sort is alphabetical.
    names = [p["name"] for p in get_network_data({"sort": "name"})["people"]]
    assert names == sorted(names, key=str.lower)
    # Search matches location/role/genre text.
    assert get_network_data({"q": "berlin"})["result_count"] >= 1


def test_network_profile_and_playlist_pages():
    client = create_app().test_client()
    assert client.get("/network/nova-reign").status_code == 200
    assert client.get("/network/does-not-exist").status_code == 302  # redirect to /network
    assert client.get("/network/playlist/late-night-synth").status_code == 200
    assert client.get("/network/playlist/nope").status_code == 302
    body = client.get("/network/echo-lin").get_data(as_text=True)
    assert "Late Night Synth" in body  # curator's playlist listed on profile


def test_network_connect_pitch_submit_flows():
    from network_config import reset_network_state
    reset_network_state()
    client = create_app().test_client()
    assert client.post("/network/kilo-byte/connect").get_json()["status"] == "Pending"
    assert client.post("/network/nope/connect").status_code == 404
    assert client.post("/network/kilo-byte/pitch", json={"song": "Midnight Drive"}).get_json()["ok"]
    # Submit to an open playlist works; closed one is rejected.
    assert client.post("/network/playlist/late-night-synth/submit", json={"song": "Midnight Drive"}).get_json()["ok"]
    assert client.post("/network/playlist/chill-drive/submit", json={"song": "X"}).status_code == 400
    assert client.post("/network/playlist/late-night-synth/submit", json={"song": ""}).status_code == 400
    # My Network reflects the connection + submission.
    my = client.get("/network?tab=my").get_data(as_text=True)
    assert "Kilo Byte" in my and "Late Night Synth" in my
    reset_network_state()


def test_network_shows_and_booking():
    from network_config import reset_network_state
    reset_network_state()
    client = create_app().test_client()
    assert client.get("/network?tab=shows").status_code == 200
    assert "Tour Dates" in client.get("/network/nova-reign").get_data(as_text=True)
    # Enquire works for booking profiles, rejected for non-booking.
    assert client.post("/network/nova-reign/enquire", json={"city": "Chicago"}).get_json()["ok"]
    assert client.post("/network/vera-sound/enquire", json={"city": "X"}).status_code == 400
    reset_network_state()


def test_network_moments_and_claim():
    from network_config import reset_network_state, get_moment
    reset_network_state()
    client = create_app().test_client()
    assert client.get("/network?tab=moments").status_code == 200
    body = client.get("/network/moment/mo-1").get_data(as_text=True)
    # Watermark/serial + honest deterrent labeling present.
    assert "SB-1-0001" in body
    assert "can't truly block screenshots" in body
    assert client.get("/network/moment/nope").status_code == 302
    # Claim marks it owned.
    resp = client.post("/network/moment/mo-1/claim")
    assert resp.get_json()["serial"] == "SB-1-0001"
    assert get_moment("mo-1")["claimed"] is True
    assert client.post("/network/moment/nope/claim").status_code == 404
    reset_network_state()


def test_discover_page_and_filters():
    from discover_config import get_discover_data, reset_discover_state
    reset_discover_state()
    client = create_app().test_client()
    assert client.get("/discover").status_code == 200
    assert 'href="/discover"' in client.get("/discover").get_data(as_text=True)  # fan-world sidebar
    assert "/discover" in client.get("/login").get_data(as_text=True)  # Continue as a Fan
    # Genre filter narrows the feed.
    data = get_discover_data({"genre": "Synthwave"})
    assert data["tracks"] and all(t["genre"] == "Synthwave" for t in data["tracks"])
    # Mood filter.
    assert all(t["mood"] == "late-night" for t in get_discover_data({"mood": "late-night"})["tracks"])


def test_discover_like_and_follow():
    from discover_config import reset_discover_state
    reset_discover_state()
    client = create_app().test_client()
    r = client.post("/discover/like/tr-1").get_json()
    assert r["liked"] is True and r["count"] == 1
    assert client.post("/discover/like/tr-1").get_json()["liked"] is False  # toggles off
    assert client.post("/discover/like/nope").status_code == 404
    assert client.post("/discover/follow/nova-reign").get_json()["following"] is True
    reset_discover_state()


def test_epk_editable_savable_real():
    import uuid
    client = create_app().test_client()
    # Anonymous can view the demo kit but cannot save.
    assert "Make it yours" in client.get("/epk").get_data(as_text=True)
    assert client.post("/epk/save", json={"tagline": "X"}).status_code == 401
    # Signed-in edits persist across requests.
    client.post("/signup", data={"name": "EPK Artist",
                                 "email": "epk%s@example.com" % uuid.uuid4().hex[:6],
                                 "password": "secret1"})
    assert client.post("/epk/save", json={
        "tagline": "Custom tagline here.", "bio": "Custom biography.",
        "genres": "Synthwave, House", "socials": {"instagram": "@custom"},
        "contact": {"booking": "book@custom.com"},
        "press": [{"quote": "Stellar.", "source": "MagX"}],
    }).get_json()["ok"]
    body = client.get("/epk").get_data(as_text=True)
    for s in ("Custom tagline here.", "Custom biography.", "House",
              "@custom", "book@custom.com", "Stellar.", "EPK Artist"):
        assert s in body


def test_epk_photo_upload_real():
    import io, uuid
    client = create_app().test_client()
    assert client.post("/epk/photo").status_code == 401  # login required
    client.post("/signup", data={"name": "P", "email": "p%s@example.com" % uuid.uuid4().hex[:6],
                                 "password": "secret1"})
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    r = client.post("/epk/photo", data={"photo": (io.BytesIO(png), "me.png")},
                    content_type="multipart/form-data")
    photo = r.get_json()["photo"]
    assert photo.startswith("/uploads/epk_")
    assert client.get(photo).status_code == 200          # actually served
    assert photo in client.get("/epk").get_data(as_text=True)
    bad = client.post("/epk/photo", data={"photo": (io.BytesIO(b"x"), "x.exe")},
                      content_type="multipart/form-data")
    assert bad.status_code == 400                        # non-image rejected


def _fake_itunes(url):
    return {"results": [{"trackName": "Fake Song", "artistName": "Fake Artist",
                         "collectionName": "Fake LP", "artworkUrl100": "https://x/100x100bb.jpg",
                         "previewUrl": "https://x/p.m4a", "trackViewUrl": "https://x/t"}]}


def _fake_odesli(url):
    return {"entityUniqueId": "E", "pageUrl": "https://song.link/x",
            "entitiesByUniqueId": {"E": {"title": "Fake Song", "artistName": "Fake Artist",
                                          "thumbnailUrl": "https://x/art.jpg"}},
            "linksByPlatform": {"spotify": {"url": "https://sp/x"},
                                 "appleMusic": {"url": "https://ap/x"},
                                 "youtube": {"url": "https://yt/x"}}}


def test_discover_real_search_offline(monkeypatch):
    import music_apis
    monkeypatch.setattr(music_apis, "_fetch_json", _fake_itunes)
    client = create_app().test_client()
    body = client.get("/discover?q=offline+test+query").get_data(as_text=True)
    assert "Fake Song" in body and "Fake Artist" in body
    assert "preview-play" in body                       # playable preview button
    assert "300x300bb.jpg" in body                      # artwork upscaled


def test_universal_link_via_odesli_offline(monkeypatch):
    import music_apis
    monkeypatch.setattr(music_apis, "_fetch_json", _fake_odesli)
    client = create_app().test_client()
    r = client.post("/links/create", json={"title": "Uni", "platforms": ["Spotify"],
                                            "source_url": "https://open.spotify.com/track/offlinetest"})
    link = r.get_json()["link"]
    assert link["universal"] is True and link["platform_count"] == 3
    landing = client.get("/l/" + link["slug"]).get_data(as_text=True)
    for s in ("Fake Song", "Fake Artist", "Spotify", "Apple Music", "YouTube",
              "Powered by Street Banker", "https://sp/x"):
        assert s in landing
    # Odesli failure falls back to a plain redirect link.
    monkeypatch.setattr(music_apis, "_fetch_json",
                        lambda url: (_ for _ in ()).throw(Exception("down")))
    r2 = client.post("/links/create", json={"title": "Plain Fallback", "platforms": ["Spotify"],
                                             "source_url": "https://open.spotify.com/track/failing"})
    l2 = r2.get_json()["link"]
    assert l2["universal"] is False
    assert client.get("/l/" + l2["slug"]).status_code == 302


def test_add_discover_track_to_catalog():
    client = create_app().test_client()
    # Anonymous adds are rejected so the button can redirect to sign-in.
    assert client.post("/catalog/add", json={"title": "Neon Ride"}).status_code == 401
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    r = client.post("/catalog/add", json={"title": "Neon Ride", "artist": "Test Artist",
                                           "art": "https://x/300x300bb.jpg", "url": "https://x/t"})
    assert r.status_code == 200 and r.get_json()["ok"]
    track_id = r.get_json()["id"]
    # Same title+artist can't be added twice.
    assert client.post("/catalog/add", json={"title": "Neon Ride",
                                              "artist": "Test Artist"}).status_code == 409
    body = client.get("/catalog").get_data(as_text=True)
    assert "Add from Discover" in body and "Neon Ride" in body
    assert client.post("/catalog/remove/" + track_id).get_json()["ok"] is True
    body = client.get("/catalog").get_data(as_text=True)
    assert "Neon Ride" not in body and "Nothing saved yet" in body
    # Signed out, the personal section disappears entirely.
    client.post("/logout")
    assert "Add from Discover" not in client.get("/catalog").get_data(as_text=True)


def test_discover_results_have_add_button(monkeypatch):
    import music_apis
    monkeypatch.setattr(music_apis, "_fetch_json", _fake_itunes)
    client = create_app().test_client()
    body = client.get("/discover?q=offline+add+button").get_data(as_text=True)
    assert "add-to-catalog" in body and "+ Catalog" in body


def _fake_deezer(url):
    if "api.deezer.com/search" in url:
        return {"data": [{"id": 42}]}
    if "api.deezer.com/track/" in url:
        return {"isrc": "USTEST2500001", "duration": 200, "release_date": "2025-01-10",
                "album": {"id": 7, "title": "Test LP"}}
    if "api.deezer.com/album/" in url:
        return {"upc": "123456789012", "label": "Test Label", "title": "Test LP",
                "release_date": "2025-01-10", "nb_tracks": 10,
                "genres": {"data": [{"name": "Electro"}]}}
    if "musicbrainz.org/ws/2/isrc/" in url:
        return {"recordings": [{"id": "rec1"}]}
    if "musicbrainz.org/ws/2/recording/" in url:
        return {"relations": [{"work": {"id": "work1"}}]}
    if "musicbrainz.org/ws/2/work/" in url:
        return {"relations": [{"type": "composer", "artist": {"name": "Fake Writer"}},
                              {"type": "publisher", "label": {"name": "Fake Publishing Co"}}]}
    return {"results": []}


def test_catalog_add_pulls_metadata(monkeypatch):
    import music_apis
    monkeypatch.setattr(music_apis, "_fetch_json", _fake_deezer)
    monkeypatch.setattr(music_apis.time, "sleep", lambda s: None)
    client = create_app().test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    r = client.post("/catalog/add", json={"title": "Meta Song", "artist": "Meta Artist"})
    meta = r.get_json()["meta"]
    assert meta["isrc"] == "USTEST2500001" and meta["upc"] == "123456789012"
    assert meta["label"] == "Test Label" and meta["album"] == "Test LP"
    assert meta["writers"] == ["Fake Writer"]
    assert meta["publishers"] == ["Fake Publishing Co"]
    body = client.get("/catalog").get_data(as_text=True)
    assert "My Releases" in body and "UPC 123456789012" in body
    assert "ISRC USTEST2500001" in body and "Test Label" in body
    # Credits populate the Songwriters and Publishers tabs + release row.
    assert "My Songwriters" in body and "Fake Writer" in body
    assert "My Publishers" in body and "Fake Publishing Co" in body
    assert "Written by Fake Writer" in body
    # A failed lookup must never block the save itself.
    monkeypatch.setattr(music_apis, "_fetch_json",
                        lambda url: (_ for _ in ()).throw(Exception("down")))
    r2 = client.post("/catalog/add", json={"title": "No Meta Song", "artist": "X"})
    assert r2.status_code == 200 and r2.get_json()["meta"] is None


def test_fresh_account_gets_clean_catalog(monkeypatch):
    import music_apis
    monkeypatch.setattr(music_apis, "_fetch_json", _fake_deezer)
    client = create_app().test_client()
    client.post("/signup", data={"name": "Clean Artist", "email": "clean@a.com",
                                  "password": "pass1234"})
    client.post("/login", data={"email": "clean@a.com", "password": "pass1234"})
    client.post("/plan/switch", data={"plan": "pro"})  # catalog is Royalty Sweep (Pro)
    body = client.get("/catalog").get_data(as_text=True)
    # No sample-catalog remnants for a real account.
    assert "1,248" not in body and "New World Order" not in body
    assert "Nothing saved yet" in body
    client.post("/catalog/add", json={"title": "First Song", "artist": "Clean Artist"})
    body = client.get("/catalog").get_data(as_text=True)
    assert "First Song" in body
    # Demo tour account keeps the rich showcase.
    client.post("/logout")
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    assert "1,248" in client.get("/catalog").get_data(as_text=True)


def test_public_epk_share_link():
    app_obj = create_app()
    client = app_obj.test_client()
    # Signed-out editor has no share block.
    assert "Public link" not in client.get("/epk").get_data(as_text=True)
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    body = client.get("/epk").get_data(as_text=True)
    # Visiting the editor mints a stable slug and shows the copyable link.
    assert "Public link" in body and "/epk/synthwave-surfer" in body
    assert "f-show-sweep" in body
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert "Official Press Kit" in public and "Synthwave Surfer" in public
    assert "Customize" not in public          # no editor UI on the public page
    assert "Powered by Royalty Sweep" not in public  # private by default
    # The artist opts in to showing backend stats publicly.
    client.post("/epk/save", json={"show_sweep": True})
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert "Powered by Royalty Sweep" in public and "Strongest Platform" in public
    assert "Sample metrics" in public          # honesty disclaimer stays
    # Anyone can open it without signing in; unknown slugs 404.
    anon = app_obj.test_client()
    assert anon.get("/epk/synthwave-surfer").status_code == 200
    assert anon.get("/epk/no-such-artist").status_code == 404


def test_epk_section_visibility_persists():
    client = create_app().test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    client.get("/epk")  # mints the public slug
    body = client.get("/epk").get_data(as_text=True)
    assert "Press Kit Sections" in body and "section-jump" in body
    assert ">Complete<" in body            # readiness statuses render
    # Hide press + stats; the editor reflects it and the public page drops them.
    client.post("/epk/save", json={"sections_off": ["press", "stats"]})
    body = client.get("/epk").get_data(as_text=True)
    assert body.count(">Hidden<") == 2
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert "Indie Wave" not in public and "Total Streams" not in public
    assert "Biography" in public           # untouched sections stay
    client.post("/epk/save", json={"sections_off": []})
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert "Indie Wave" in public and "Total Streams" in public


def test_epk_media_assets_and_zip():
    import io
    import zipfile
    client = create_app().test_client()
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    # Anonymous uploads rejected; unknown kinds rejected.
    assert client.post("/epk/asset/logo", data={"asset": (io.BytesIO(png), "a.png")},
                       content_type="multipart/form-data").status_code == 401
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    client.get("/epk")
    assert client.post("/epk/asset/nonsense", data={"asset": (io.BytesIO(png), "a.png")},
                       content_type="multipart/form-data").status_code == 400
    for kind in ("press_photo", "logo"):
        r = client.post("/epk/asset/" + kind, data={"asset": (io.BytesIO(png), "a.png")},
                        content_type="multipart/form-data")
        assert r.get_json()["ok"]
    # Public page gains the downloads section and the ZIP bundles both files.
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert "Media Assets" in public and "Download Press Kit (ZIP)" in public
    z = zipfile.ZipFile(io.BytesIO(client.get("/epk/synthwave-surfer/kit.zip").data))
    assert sorted(z.namelist()) == ["synthwave-surfer-logo.png",
                                    "synthwave-surfer-press-photo.png"]
    # Making the logo private removes it from the public page and the ZIP.
    client.post("/epk/asset/logo/visibility", json={"public": False})
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert "Logo" not in public
    z = zipfile.ZipFile(io.BytesIO(client.get("/epk/synthwave-surfer/kit.zip").data))
    assert z.namelist() == ["synthwave-surfer-press-photo.png"]
    # A YouTube link saves and renders as an embed.
    client.post("/epk/save", json={"video_url": "https://www.youtube.com/watch?v=abc123"})
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert "youtube.com/embed/abc123" in public


def test_epk_cover_color_logo_video_press():
    import io
    import music_apis
    client = create_app().test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    client.get("/epk")
    # Cover color: valid hex persists to the public page; junk is rejected.
    client.post("/epk/save", json={"bg_color": "#2a1015"})
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert "background-color: #2a1015" in public
    client.post("/epk/save", json={"bg_color": "javascript:alert(1)"})
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert "background-color: #141210" in public          # falls back to default
    # Logo asset renders above the hero on both editor and public page.
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    client.post("/epk/asset/logo", data={"asset": (io.BytesIO(png), "logo.png")},
                content_type="multipart/form-data")
    # An earlier test may have made the demo logo private; visibility is
    # deliberately preserved across re-uploads, so re-enable it here.
    client.post("/epk/asset/logo/visibility", json={"public": True})
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert 'alt="Synthwave Surfer logo"' in public
    # Video URL yields a thumbnail in the editor and an embed publicly.
    client.post("/epk/save", json={"video_url": "https://www.youtube.com/watch?v=xyz789"})
    editor = client.get("/epk").get_data(as_text=True)
    assert "img.youtube.com/vi/xyz789/hqdefault.jpg" in editor
    # Press quotes keep their source links on the public page.
    client.post("/epk/save", json={"press": [{"quote": "Brilliant live show.",
                                               "source": "Test Mag",
                                               "url": "https://example.com/review"}]})
    public = client.get("/epk/synthwave-surfer").get_data(as_text=True)
    assert 'href="https://example.com/review"' in public


def test_epk_press_search(monkeypatch):
    import music_apis
    rss = ('<rss><channel><item><title>Great new single - Test Weekly</title>'
           '<link>https://example.com/a</link><source url="https://tw.com">Test Weekly</source>'
           '<pubDate>Tue, 08 Jul 2026 01:00:00 GMT</pubDate></item></channel></rss>')
    monkeypatch.setattr(music_apis, "_fetch_text", lambda url: rss)
    client = create_app().test_client()
    # Requires sign-in.
    assert client.get("/epk/press/search?q=x").status_code == 401
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    data = client.get("/epk/press/search?q=Test Artist").get_json()
    assert data["ok"] and data["results"][0] == {
        "title": "Great new single", "source": "Test Weekly",
        "url": "https://example.com/a", "date": "Tue, 08 Jul 2026"}
    # Editor ships the finder UI.
    body = client.get("/epk").get_data(as_text=True)
    assert "press-search-btn" in body and "Find press on the web" in body
    assert "bg-swatch" in body                     # cover color swatches too


# --- Street Banker Links: campaign engine ------------------------------------

def _ml_login(app_obj):
    client = app_obj.test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    return client


def _ml_create(client, **overrides):
    data = {"title": "Test Drop", "artist_name": "Test Artist",
            "release_type": "Single", "campaign_type": "release",
            "cover_url": "https://x/art.jpg", "description": "New single.",
            "email_capture": "1", "consent_text": "I agree to updates.",
            "dest_spotify": "https://open.spotify.com/track/x",
            "dest_apple_music": "https://music.apple.com/x",
            "dest_youtube": "https://youtube.com/watch?v=x"}
    data.update(overrides)
    r = client.post("/links/new", data=data)
    assert r.status_code == 302
    return r.headers["Location"].split("/")[2]


def test_ml_campaign_lifecycle_and_public_page():
    import links_store as mls
    app_obj = create_app()
    client = _ml_login(app_obj)
    # Anonymous cannot create.
    anon = app_obj.test_client()
    assert anon.post("/links/new", data={"title": "x"}).status_code == 302  # -> login
    cid = _ml_create(client)
    camp = mls.get_campaign(cid)
    assert camp["status"] == "draft"
    # Draft is invisible to the public but previewable by the owner.
    assert anon.get("/l/" + camp["slug"]).status_code == 404
    assert "Draft preview" in client.get("/l/" + camp["slug"]).get_data(as_text=True)
    client.post("/links/%s/publish" % cid)
    page = anon.get("/l/" + camp["slug"]).get_data(as_text=True)
    assert "Test Drop" in page and "Listen Now" in page
    assert "Powered by" in page and "Street Banker" in page
    assert "I agree to updates." in page          # consent copy on public form
    # Page view tracked; service click via /go/ redirects and tracks.
    dests = mls.get_destinations(cid)
    r = anon.get("/l/%s/go/%s" % (camp["slug"], dests[0]["id"]))
    assert r.status_code == 302 and "spotify" in r.headers["Location"]
    counts = mls.event_counts(cid)
    assert counts["page_view"] >= 1 and counts["service_click"] == 1
    # Archive -> public 410 unavailable state.
    client.post("/links/%s/archive" % cid)
    assert anon.get("/l/" + camp["slug"]).status_code == 410


def test_ml_presave_capture_consent_and_intent():
    import links_store as mls
    app_obj = create_app()
    client = _ml_login(app_obj)
    cid = _ml_create(client, campaign_type="presave", release_date="2030-01-01",
                     title="Future Drop")
    client.post("/links/%s/publish" % cid)
    camp = mls.get_campaign(cid)
    anon = app_obj.test_client()
    page = anon.get("/l/" + camp["slug"]).get_data(as_text=True)
    assert "Dropping in" in page and 'id="countdown"' in page  # pre-save state
    # Bad email rejected; good email creates fan + consent + presave event.
    assert anon.post("/l/%s/subscribe" % camp["slug"],
                     data={"email": "junk"}).status_code == 400
    r = anon.post("/l/%s/subscribe" % camp["slug"],
                  data={"email": "Fan@Example.com", "name": "Fan One"})
    assert r.get_json()["ok"]
    fans = mls.list_fans(camp["user_id"], "fan@example.com")
    assert fans and fans[0]["total_presaves"] == 1
    assert fans[0]["intent_score"] > 0 and fans[0]["intent_level"] != ""
    consents = mls.list_consents(fans[0]["id"])
    assert consents[0]["consent_type"] == "presave_notify"
    assert consents[0]["consent_text"] == "I agree to updates."
    # Fan CRM lists + exports the fan.
    assert "fan@example.com" in client.get("/links/fans").get_data(as_text=True)
    assert "fan@example.com" in client.get("/links/fans/export.csv").get_data(as_text=True)
    # Duplicate emails update, not duplicate.
    anon.post("/l/%s/subscribe" % camp["slug"], data={"email": "fan@example.com"})
    assert len(mls.list_fans(camp["user_id"], "fan@example.com")) == 1


def test_ml_score_variants_qr_duplicate():
    import links_store as mls
    app_obj = create_app()
    client = _ml_login(app_obj)
    # Bare campaign scores low with actionable warnings.
    bare = _ml_create(client, title="Bare", cover_url="", description="",
                      email_capture="", consent_text="", dest_spotify="",
                      dest_apple_music="", dest_youtube="")
    body = client.get("/links/%s/edit" % bare).get_data(as_text=True)
    assert "Spotify destination missing." in body
    assert "No email capture enabled" in body
    import links_engine
    camp = mls.get_campaign(bare)
    score = links_engine.calculate_street_banker_score(camp, [])
    assert score["total"] < 40
    # Full campaign scores high once published.
    full = _ml_create(client, title="Full", release_date="2030-06-01")
    client.post("/links/%s/publish" % full)
    camp = mls.get_campaign(full)
    score = links_engine.calculate_street_banker_score(
        camp, mls.get_destinations(full))
    assert score["total"] >= 70
    # Variants: unique slug, tracked separately, QR per variant.
    client.post("/links/%s/variants" % full,
                data={"name": "Instagram bio", "utm_source": "instagram"})
    variants = mls.list_variants(full)
    assert len(variants) == 1
    anon = app_obj.test_client()
    anon.get("/l/%s?v=%s" % (camp["slug"], variants[0]["slug"]))
    assert mls.variant_stats(full)[variants[0]["id"]]["page_view"] == 1
    r = client.get("/links/%s/qr.svg?v=%s" % (full, variants[0]["slug"]))
    assert r.status_code == 200 and b"<svg" in r.data
    # Duplicate copies destinations, resets to draft.
    r = client.post("/links/%s/duplicate" % full)
    new_id = r.headers["Location"].split("/")[2]
    dup = mls.get_campaign(new_id)
    assert dup["status"] == "draft" and "(copy)" in dup["title"]
    assert len(mls.get_destinations(new_id)) == len(mls.get_destinations(full))
    # Dashboard shows campaign cards with the score.
    body = client.get("/links").get_data(as_text=True)
    assert "Music Link Campaigns" in body and "SB Score" in body


def test_ml_autofill_and_cover_upload(monkeypatch):
    import io
    import music_apis
    import links_store as mls
    monkeypatch.setattr(music_apis, "_fetch_json", _fake_odesli)
    app_obj = create_app()
    # Autofill requires sign-in, then maps Odesli platforms to service keys.
    anon = app_obj.test_client()
    assert anon.get("/links/autofill?url=https://x").status_code == 401
    client = _ml_login(app_obj)
    data = client.get("/links/autofill?url=https://open.spotify.com/track/t").get_json()
    assert data["ok"] and data["title"] == "Fake Song" and data["artist"] == "Fake Artist"
    assert data["links"]["spotify"] == "https://sp/x"
    assert data["links"]["apple_music"] == "https://ap/x"
    assert data["links"]["youtube"] == "https://yt/x"
    # A bad URL fails gracefully.
    monkeypatch.setattr(music_apis, "_fetch_json",
                        lambda url: (_ for _ in ()).throw(Exception("down")))
    assert client.get("/links/autofill?url=https://bad").get_json()["ok"] is False
    # Cover art uploads as a file and overrides the URL field.
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    r = client.post("/links/new", data={
        "title": "Upload Test", "cover_url": "https://ignored.example/x.jpg",
        "cover_file": (io.BytesIO(png), "cover.png")},
        content_type="multipart/form-data")
    cid = r.headers["Location"].split("/")[2]
    camp = mls.get_campaign(cid)
    assert camp["cover_url"].startswith("/uploads/mlcover_")
    assert client.get(camp["cover_url"]).status_code == 200  # actually served


# --- Rollout Studio ------------------------------------------------------------

def test_rollout_studio_full_flow():
    import io
    import links_store as mls
    import rollout_store as ros
    app_obj = create_app()
    client = _ml_login(app_obj)
    # Attach a published Links campaign for attribution.
    ml_id = _ml_create(client, title="Rollout Base", release_date="2031-01-01")
    client.post("/links/%s/publish" % ml_id)
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    r = client.post("/rollout-studio/new", data={
        "title": "Rollout Base", "artist_name": "Test Artist",
        "release_date": "2031-01-01", "rollout_length": "7", "goal": "presaves",
        "tone": "street", "ml_campaign_id": ml_id,
        "pf_instagram_reels": "1", "pf_tiktok": "1", "pf_x": "1",
        "art_file": (io.BytesIO(png), "art.png"),
        "video_file": (io.BytesIO(b"0" * 128), "clip.mp4"),
        "lyrics": "Neon lights across the bay\nWe ride until the break of day\nNothing left to prove",
    }, content_type="multipart/form-data")
    cid = r.headers["Location"].split("/")[2]
    # Generation: dated posts across the phase arc, one Links variant each.
    client.post("/rollout-studio/%s/generate" % cid)
    posts = ros.list_posts(cid)
    assert len(posts) == 10                      # 7 pre-release + release + 2 follow-ups
    phases = [p["phase"] for p in posts]
    assert phases[0] == "tease" and "release_day" in phases and "post_release" in phases
    assert all(p["variant_id"] for p in posts)
    variants = mls.list_variants(ml_id)
    assert len(variants) == len(posts)
    assert variants[0]["name"].startswith("rollout_")
    assert variants[0]["utm_medium"] == "rollout"
    # Lyrics feed the lyric-reveal caption; video posts get edit plans.
    lyric_posts = [p for p in posts if p["phase"] == "lyric_reveal"]
    assert any("ride until the break" in p["caption"] for p in lyric_posts)
    video_posts = [p for p in posts if p["edit_plan"]]
    assert video_posts and video_posts[0]["edit_plan"]["aspect_ratio"] == "9:16"
    assert "export_checklist" in video_posts[0]["edit_plan"]
    # Approval workflow + manual posting with published URL.
    pid = posts[0]["id"]
    client.post("/rollout-studio/%s/posts" % cid,
                data={"post_id": pid, "action": "approve"})
    assert ros.get_post(pid)["status"] == "approved"
    client.post("/rollout-studio/%s/posts" % cid,
                data={"post_id": pid, "action": "posted",
                      "published_url": "https://instagram.com/p/abc"})
    post = ros.get_post(pid)
    assert post["status"] == "posted" and post["published_url"].endswith("/abc")
    # Attribution: a fan hitting this post's variant shows on performance.
    ml_camp = mls.get_campaign(ml_id)
    vslug = next(v["slug"] for v in variants if v["id"] == posts[0]["variant_id"])
    anon = app_obj.test_client()
    anon.get("/l/%s?v=%s" % (ml_camp["slug"], vslug))
    perf = client.get("/rollout-studio/%s/performance" % cid).get_data(as_text=True)
    assert "Top Posts" in perf and "1v" in perf
    # All pages render; socials shows manual mode ready.
    for path in ("", "/posts", "/calendar", "/socials"):
        assert client.get("/rollout-studio/%s%s" % (cid, path)).status_code == 200
    socials = client.get("/rollout-studio/%s/socials" % cid).get_data(as_text=True)
    assert "Manual posting" in socials and "ready" in socials
    assert "TikTok" in socials and "needs credentials" in socials
    # Dashboard card with attribution totals.
    dash = client.get("/rollout-studio").get_data(as_text=True)
    assert "Rollout Base" in dash and "link clicks" in dash
    # Other users cannot see this rollout.
    other = app_obj.test_client()
    import uuid as _uuid
    other.post("/signup", data={"name": "O", "email": "o%s@x.com" % _uuid.uuid4().hex[:6],
                                "password": "secret1"})
    assert other.get("/rollout-studio/%s" % cid).status_code == 404


# --- Artist OS: Command Center + Actions ---------------------------------------

def test_command_center_and_actions():
    import command_center as cc_mod
    import db as store_mod
    from datetime import date, timedelta
    app_obj = create_app()
    # Anonymous users are sent to sign in.
    assert app_obj.test_client().get("/command-center").status_code == 302
    client = _ml_login(app_obj)
    # A live campaign with gaps drives real derived alerts.
    soon = (date.today() + timedelta(days=3)).isoformat()
    r = client.post("/links/new", data={"title": "OS Drop", "release_date": soon,
                                        "dest_spotify": "https://open.spotify.com/track/x"})
    cid = r.headers["Location"].split("/")[2]
    client.post("/links/%s/publish" % cid)
    body = client.get("/command-center").get_data(as_text=True)
    assert "Command Center" in body and "capturing fans" in body
    assert "with no rollout" in body           # release in 3 days, no rollout
    assert "OS Drop" in body and "Autopilot" in body
    assert "Fraud Sentinel" in body            # module grid with previews
    # Alert -> action -> lifecycle.
    client.post("/actions/from-alert", data={"title": "Enable capture on OS Drop",
                                             "description": "x", "category": "fan_growth"})
    body = client.get("/actions").get_data(as_text=True)
    assert "Enable capture on OS Drop" in body
    user = store_mod.get_user_by_email("demo@streetbanker.io")
    action = next(a for a in cc_mod.list_actions(user["id"])
                  if a["title"] == "Enable capture on OS Drop")
    client.post("/actions", data={"action_id": action["id"], "status": "in_progress"})
    client.post("/actions", data={"action_id": action["id"], "status": "complete"})
    refreshed = next(a for a in cc_mod.list_actions(user["id"])
                     if a["id"] == action["id"])
    assert refreshed["status"] == "complete" and refreshed["completed_at"]
    # Manual action creation with priority ordering.
    client.post("/actions", data={"title": "Call the plant", "category": "release",
                                  "priority": "high"})
    body = client.get("/actions?status=new").get_data(as_text=True)
    assert "Call the plant" in body


def test_release_autopilot_and_clean_release():
    app_obj = create_app()
    client = _ml_login(app_obj)
    r = client.post("/links/new", data={"title": "Checklist Drop",
                                        "dest_spotify": "https://open.spotify.com/track/x"})
    cid = r.headers["Location"].split("/")[2]
    for route in ("/releases/autopilot", "/releases/clean-release"):
        body = client.get("%s?campaign=%s" % (route, cid)).get_data(as_text=True)
        assert "Checklist Drop" in body
        assert "Spotify destination" in body          # passing check listed
        assert "Apple Music destination" in body      # failing check listed
        assert "Create action" in body                # failed checks are actionable
        assert "ready" in body                        # score badge


def test_preview_modules_are_honest():
    client = _ml_login(create_app())
    routes = ["/fraud-sentinel", "/deal-room", "/revenue-os", "/capital-score",
              "/metadata-passport", "/ai-rights", "/trust-score", "/artist-twin",
              "/opportunities", "/voice-of-fan", "/spend-optimizer", "/fan-club",
              "/partner-portal", "/royalty-recovery/cases", "/royalty-recovery/mlc",
              "/sync/clearance-packs", "/sync/deal-simulator"]
    for route in routes:
        r = client.get(route)
        assert r.status_code == 200, route
        body = r.get_data(as_text=True)
        assert "in preview" in body, route            # no fake functionality
    assert "not legal advice" in client.get("/sync/deal-simulator").get_data(as_text=True)
    assert "not financial advice" in client.get("/capital-score").get_data(as_text=True)


# --- Plan tiers + product worlds -------------------------------------------------

def test_plan_tiers_gate_sections():
    import uuid as _uuid
    app_obj = create_app()
    client = app_obj.test_client()
    email = "tier%s@x.com" % _uuid.uuid4().hex[:6]
    client.post("/signup", data={"name": "T", "email": email, "password": "secret1",
                                 "account_type": "artist"})
    # Artist tier: Promote works, Royalty Sweep is gated with the upgrade page.
    assert client.get("/links").status_code == 200
    assert client.get("/command-center").status_code == 200
    r = client.get("/overview")
    assert r.status_code == 402
    assert "This is a Pro feature" in r.get_data(as_text=True)
    assert client.get("/statements").status_code == 402
    # Demo plan switch unlocks it (labeled demo until Stripe).
    client.post("/plan/switch", data={"plan": "pro"})
    assert client.get("/overview").status_code == 200
    assert client.get("/catalog").status_code == 200
    # Billing shows the plan cards.
    body = client.get("/billing").get_data(as_text=True)
    assert "Your Plan" in body and "Switch (demo)" in body


def test_fan_accounts_get_fan_shell():
    import uuid as _uuid
    app_obj = create_app()
    client = app_obj.test_client()
    email = "fanshell%s@x.com" % _uuid.uuid4().hex[:6]
    r = client.post("/signup", data={"name": "F", "email": email, "password": "secret1",
                                     "account_type": "fan"})
    assert r.headers["Location"] == "/discover"
    body = client.get("/discover").get_data(as_text=True)
    # Fan shell: Community nav, no artist tooling, no world switcher.
    assert "Fan Account" in body and ">Community<" in body
    assert "Rollout Studio" not in body and "Statements" not in body
    # Artist tools are gated for fans.
    assert client.get("/links").status_code == 402
    assert client.get("/overview").status_code == 402
    # Fan login lands on Discover.
    fresh = app_obj.test_client()
    r = fresh.post("/login", data={"email": email, "password": "secret1"})
    assert r.headers["Location"] == "/discover"


def test_world_switcher_and_public_pages():
    app_obj = create_app()
    client = app_obj.test_client()
    client.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    # Demo account has the Label plan: everything open, switcher rendered.
    body = client.get("/links").get_data(as_text=True)
    assert "/world/sweep" in body and "/world/fan" in body
    assert "Rollout Studio" in body and "Statements" not in body   # promote world nav
    body = client.get("/overview").get_data(as_text=True)
    assert "Statements" in body and "Rollout Studio" not in body   # sweep world nav
    assert client.get("/world/label").headers["Location"] == "/services"
    # Public pages stay open for signed-out visitors.
    anon = app_obj.test_client()
    assert anon.get("/links").status_code == 200
    assert anon.get("/epk").status_code == 200


# --- Release OS: qualification, profile, vault, review queue ---------------------

def test_qualification_score_from_real_data():
    import qualification
    import db as store_mod
    app_obj = create_app()
    client = _ml_login(app_obj)
    user = store_mod.get_user_by_email("demo@streetbanker.io")
    before = qualification.calculate(user["id"])["total"]
    # Real work moves the score: publish a fully-set-up campaign.
    cid = _ml_create(client, title="Qual Drop", release_date="2031-06-01")
    client.post("/links/%s/publish" % cid)
    after = qualification.calculate(user["id"])
    # Other tests may have already saturated some categories in the shared DB.
    assert after["total"] >= before and after["total"] > 0
    assert "Fan Capture Enabled" in after["badges"]
    assert after["recommendation"] in ("Needs work", "Approve — with guidance",
                                       "High potential")
    # Page renders meters, unlocks, and action shortcuts.
    body = client.get("/qualification").get_data(as_text=True)
    assert "Growth Score" in body and "Release Readiness" in body
    assert "What Your Score Unlocks" in body and "Raise growth score" in body


def test_artist_profile_and_vault():
    client = _ml_login(create_app())
    cid = _ml_create(client, title="Sheet Drop")
    body = client.get("/artist-profile").get_data(as_text=True)
    assert "Label-Facing One-Sheet" in body and "SB Score" in body
    assert "Sheet Drop" in body            # campaign history is real
    assert "Fans owned" in body
    vault = client.get("/vault").get_data(as_text=True)
    assert "Archive Drawer" in vault and "Sheet Drop" in vault
    assert "Cover art" in vault and "Manage" in vault


def test_admin_review_queue_label_only():
    import uuid as _uuid
    app_obj = create_app()
    label_client = _ml_login(app_obj)   # demo account holds the Label plan
    body = label_client.get("/admin/review").get_data(as_text=True)
    assert "Review Queue" in body and "Synthwave Surfer" in body
    # Artist-tier accounts cannot see the curation desk.
    artist = app_obj.test_client()
    artist.post("/signup", data={"name": "A", "email": "rq%s@x.com" % _uuid.uuid4().hex[:6],
                                 "password": "secret1", "account_type": "artist"})
    assert artist.get("/admin/review").status_code == 402
    assert artist.get("/qualification").status_code == 200  # own score always visible


def test_ml_quick_links_still_work():
    # The original quick smart links share /l/ and must be untouched.
    client = create_app().test_client()
    r = client.post("/links/create", json={"title": "Quick", "platforms": ["Spotify"]})
    slug = r.get_json()["link"]["slug"]
    assert client.get("/l/" + slug).status_code == 302


def test_api_cache_roundtrip():
    import db as store
    store.cache_set("t:key", {"a": 1})
    assert store.cache_get("t:key", 60) == {"a": 1}
    assert store.cache_get("t:key", -1) is None  # expired
    assert store.cache_get("missing", 60) is None


def test_catalog_data_config_shapes():
    from catalog_config import get_catalog_data
    data = get_catalog_data()
    assert data["tabs"] == ["Tracks", "Releases", "Songwriters", "Publishers", "Splits"]
    assert data["tracks"] and data["releases"] and data["songwriters"]
    assert data["publishers"] and data["splits"] and data["recently_added"]
    assert data["registered_pct"] == 82.7
    assert data["health"]["total"] == 76


def test_update_fix_status_route():
    client = create_app().test_client()
    body = client.get("/recovery").get_data(as_text=True)
    import re
    match = re.search(r'data-fix-id="([^"]+)"', body)
    fix_id = match.group(1)
    try:
        response = client.post(f"/fixes/{fix_id}/status", json={"status": "Complete"})
        assert response.status_code == 200
        assert response.get_json() == {"ok": True, "status": "Complete"}
    finally:
        reset_fix_status_state()


def test_update_fix_status_invalid_status_returns_400():
    client = create_app().test_client()
    response = client.post("/fixes/some-id/status", json={"status": "NotAStatus"})
    assert response.status_code == 400


def test_registration_wizard_route():
    client = create_app().test_client()
    response = client.get("/songs/midnight-drive/registration-wizard")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["wizard"]["song_id"] == "midnight-drive"


def test_registration_wizard_unknown_song_returns_404():
    client = create_app().test_client()
    response = client.get("/songs/not-a-real-song/registration-wizard")
    assert response.status_code == 404


def test_complete_registration_wizard_step_route():
    client = create_app().test_client()
    try:
        response = client.post("/songs/midnight-drive/registration-wizard/publishing_admin/complete")
        assert response.status_code == 200
        data = response.get_json()
        assert data["wizard"]["status"]["publishing_admin"] is True
    finally:
        reset_registration_wizard_state()


def test_complete_registration_wizard_step_unknown_song_returns_404():
    client = create_app().test_client()
    response = client.post("/songs/not-a-real-song/registration-wizard/pro/complete")
    assert response.status_code == 404


def test_generate_report_route():
    client = create_app().test_client()
    response = client.post("/reports/royalty-report/generate")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["report"]["id"] == "royalty-report"


def test_generate_report_unknown_id_returns_404():
    client = create_app().test_client()
    response = client.post("/reports/not-a-report/generate")
    assert response.status_code == 404


def test_team_page_includes_collaborator_access_ui():
    # Collaborator access moved from Settings to the dedicated Team page.
    client = create_app().test_client()
    body = client.get("/team").get_data(as_text=True)
    assert "Collaborators" in body
    assert "Jamie Rowe" in body
    assert 'id="invite-name"' in body
    assert 'id="invite-email"' in body


def test_settings_has_quick_links_and_signout():
    client = create_app().test_client()
    body = client.get("/settings").get_data(as_text=True)
    assert 'href="/team"' in body
    assert 'href="/billing"' in body
    assert 'action="/logout"' in body


def test_invite_collaborator_route():
    client = create_app().test_client()
    try:
        response = client.post(
            "/collaborators/invite",
            json={"name": "New Person", "email": "new@example.com", "role": "Viewer", "songs": ["City Lights"]},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["collaborator"]["name"] == "New Person"
        assert data["collaborator"]["status"] == "Invited"
    finally:
        reset_collaborator_state()


def test_invite_collaborator_invalid_returns_400():
    client = create_app().test_client()
    response = client.post(
        "/collaborators/invite",
        json={"name": "", "email": "new@example.com", "role": "Viewer", "songs": []},
    )
    assert response.status_code == 400


def test_update_collaborator_role_route():
    client = create_app().test_client()
    try:
        response = client.post("/collaborators/jamie-rowe/role", json={"role": "Admin"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["collaborator"]["role"] == "Admin"
    finally:
        reset_collaborator_state()


def test_update_collaborator_role_unknown_id_returns_404():
    client = create_app().test_client()
    response = client.post("/collaborators/not-a-real-id/role", json={"role": "Viewer"})
    assert response.status_code == 404


def test_remove_collaborator_route():
    client = create_app().test_client()
    try:
        response = client.post("/collaborators/marco-velocity/remove")
        assert response.status_code == 200
        assert response.get_json() == {"ok": True}
    finally:
        reset_collaborator_state()


def test_remove_collaborator_unknown_id_returns_404():
    client = create_app().test_client()
    response = client.post("/collaborators/not-a-real-id/remove")
    assert response.status_code == 404


def test_build_landing_hero_reflects_catalog_status():
    from app import build_landing_hero
    from royalty_data import get_platform_catalog, get_missing_royalty_findings, get_recovery_summary, get_songs, live_song, get_earnings_trend

    catalog = get_platform_catalog()
    songs = [live_song(s) for s in get_songs()]
    summary = get_recovery_summary(catalog, songs, get_earnings_trend())
    hero = build_landing_hero(catalog, summary)

    assert len(hero["nodes"]) == 7
    assert len(hero["cards"]) == 7
    assert hero["center_amount"] == summary["estimated_uncollected"]
    spotify_node = next(n for n in hero["nodes"] if n["name"] == "Spotify")
    assert spotify_node["status_tone"] == "ok"


def test_get_landing_config_has_swappable_hero_visual():
    from landing_config import get_landing_config
    config = get_landing_config()
    # Hero visual is swappable via a variant, and command-desk data is editable.
    assert config["hero_visual"]["variant"] == "commandDesk"
    assert config["hero_visual"]["connected_sources"]
    assert config["hero_visual"]["recovery_opportunities"]
    assert len(config["hero"]["headline"]) == 4
    assert len(config["features"]) == 4

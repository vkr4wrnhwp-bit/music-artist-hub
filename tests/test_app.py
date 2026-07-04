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
    assert "ROYALTY SWEEP" in body
    assert "COMMAND DESK" in body


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

    for href in _all_landing_hrefs(get_landing_config()):
        if href.startswith("#"):
            assert href[1:] in page_ids, f"dead anchor: {href}"
        elif href.startswith("http"):
            continue
        else:
            assert href in real_routes, f"unknown route: {href}"


def test_landing_command_desk_shows_all_sources():
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    for platform in ["Spotify", "Apple Music", "ASCAP", "BMI", "The MLC", "SoundExchange", "YouTube Content ID"]:
        assert platform in body


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


def test_landing_includes_lanes_engine_and_services():
    body = create_app().test_client().get("/").get_data(as_text=True)
    # Lanes section renders (headline lives in the graphic when an image is set).
    assert 'id="infrastructure"' in body
    assert "Explore The Three Lanes" in body
    assert "THE RECOVERY ENGINE" in body
    assert "BUILT FOR EVERY STAGE OF YOUR CAREER" in body


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
    assert "Included Sections" in body
    assert "section-toggle" in body


def test_epk_sidebar_and_export():
    client = create_app().test_client()
    assert 'href="/epk"' in client.get("/overview").get_data(as_text=True)
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
    # Grouped sidebar section labels present.
    for group in ("Collect", "Catalog", "Grow", "Promote", "Account"):
        assert ">%s<" % group in nav


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
    nav = client.get("/overview").get_data(as_text=True)
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


def test_login_flow():
    client = create_app().test_client()
    assert client.get("/login").status_code == 200
    ok = client.post("/login", data={"passkey": "sweep"})
    assert ok.status_code == 302 and "/onboarding" in ok.headers["Location"]
    bad = client.post("/login", data={"passkey": "nope"})
    assert bad.status_code == 200 and "Incorrect passkey" in bad.get_data(as_text=True)
    assert client.post("/logout").status_code == 302


def test_tier5_and_community_pages_render_and_nav():
    client = create_app().test_client()
    nav = client.get("/overview").get_data(as_text=True)
    for href in ("/insights", "/benchmark", "/marketplace", "/network", "/fan-label", "/fans"):
        assert 'href="%s"' % href in nav
        assert client.get(href).status_code == 200
    for group in ("Intelligence", "Community"):
        assert ">%s<" % group in nav


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
    nav = client.get("/overview").get_data(as_text=True)
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
    assert "Art Is War Records" in hub
    assert "team.summitarts@gmail.com" in hub
    assert "170+" in hub
    dist = client.get("/services/distribution").get_data(as_text=True)
    assert "No physical product set-up fees" in dist
    submit = client.get("/submit").get_data(as_text=True)
    assert "artiswarrecords@gmail.com" in submit
    assert 'href="/epk"' in submit  # submissions tie into the EPK builder


def test_landing_links_to_label_services():
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    assert 'href="/services"' in body


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

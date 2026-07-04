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
    assert "Find the Royalties" in body
    assert "ROYALTY SWEEP" in body
    assert "Scan for Missing Royalties" in body
    assert "Potential Missing Royalties Found" in body
    assert "Ready to Claim" in body


def test_landing_page_nav_and_ctas_link_into_the_app():
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    assert 'href="/overview"' in body
    assert "Start Free Scan" in body
    assert "Login" in body


def test_landing_page_nav_links_all_resolve():
    """Every landing nav/CTA link must point at a real route or an
    on-page anchor that exists -- no dead placeholder hashes."""
    import re
    from landing_config import get_landing_config

    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    page_ids = set(re.findall(r'id="([^"]+)"', body))

    config = get_landing_config()
    hrefs = [link["href"] for link in config["nav"]["links"]]
    hrefs += [config["nav"]["login"]["href"], config["nav"]["cta"]["href"]]
    hrefs += [config["hero"]["primary_cta"]["href"], config["hero"]["secondary_cta"]["href"]]
    hrefs += [f["link"]["href"] for f in config["features"]]

    real_routes = {"/overview", "/royalties", "/catalog", "/connections",
                   "/recovery", "/valuation", "/reports", "/settings", "/"}
    for href in hrefs:
        if href.startswith("#"):
            assert href[1:] in page_ids, f"dead anchor: {href}"
        else:
            assert href in real_routes, f"unknown route: {href}"


def test_landing_page_hero_visual_uses_live_catalog_data():
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    for platform in ["Spotify", "Apple Music", "ASCAP", "BMI", "The MLC", "SoundExchange", "YouTube Content ID"]:
        assert platform in body


def test_landing_page_includes_feature_cards():
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    assert "Find Missing Royalties" in body
    assert "Connect Every Source" in body
    assert "Value Your Catalog" in body


def test_landing_page_includes_trust_strip():
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    assert "Trusted by artists, managers, and labels" in body


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


def test_settings_includes_collaborator_access_ui():
    client = create_app().test_client()
    body = client.get("/settings").get_data(as_text=True)
    assert "Collaborator Access" in body
    assert "Jamie Rowe" in body
    assert 'id="invite-collaborator-form"' in body
    assert 'id="invite-name"' in body
    assert 'id="invite-email"' in body


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
    assert config["hero_visual"]["template"] == "landing/hero_recovery.html"
    assert config["hero"]["headline"][1]["accent"] is True
    assert len(config["features"]) == 4

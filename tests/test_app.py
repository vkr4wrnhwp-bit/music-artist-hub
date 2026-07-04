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
    assert "Find the" in body
    assert "Royalties" in body
    assert "ROYALTY SWEEP" in body
    assert 'id="run-audit-btn"' in body
    assert "Sources Scanned" in body
    assert "Recovery Potential Over Time" in body


def test_landing_page_links_into_dashboard_and_royalties():
    client = create_app().test_client()
    body = client.get("/").get_data(as_text=True)
    assert 'href="/dashboard"' in body
    assert 'href="/royalties#missing-money-scanner"' in body


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
    for route in ["/dashboard", "/royalties", "/catalog", "/valuation", "/settings"]:
        response = client.get(route)
        assert response.status_code == 200, route


def test_nav_highlights_active_page():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
    assert 'href="/royalties" class="flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors bg-white/5 text-white"' in body


def test_overview_renders_expected_content():
    client = create_app().test_client()
    response = client.get("/dashboard")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Total Royalties" in body
    assert "Spotify" in body


def test_overview_includes_set_goal_ui():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert 'id="set-goal-btn"' in body
    assert 'id="goal-modal"' in body
    assert 'id="goal-amount"' in body
    assert 'id="goal-type"' in body
    assert 'id="goal-deadline"' in body


def test_overview_includes_health_score():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Royalty Health Score" in body
    assert "Recommended actions" in body
    assert "out of 100" in body


def test_overview_includes_catalog_completeness_meter():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Catalog Completeness Meter" in body
    assert "ready to collect" in body


def test_overview_includes_story_hero():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "What you made" in body
    assert "What you're missing" in body
    assert ">Why<" in body
    assert "How to collect it" in body
    assert "What your catalog may be worth" in body
    assert "The next move" in body
    assert 'id="story-next-move"' in body


def test_overview_includes_money_left_on_the_table():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Money Left on the Table" in body
    assert "High confidence" in body
    assert "View Missing Money" in body


def test_overview_includes_since_last_login():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "What Changed Since Last Login" in body
    assert "New Royalties" in body


def test_royalties_includes_leak_alerts_ui():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
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


def test_settings_includes_connections_ui():
    client = create_app().test_client()
    body = client.get("/settings").get_data(as_text=True)
    assert "Platform Connections" in body
    assert 'id="connection-search"' in body
    assert "YouTube Music" in body


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


def test_royalties_includes_scanner_ui():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
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


def test_catalog_includes_song_breakdown_ui():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert "Song-Level Royalty Breakdown" in body
    assert "Midnight Drive" in body


def test_overview_includes_metadata_completion_ui():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "Metadata Completion" in body


def test_base_includes_song_drawer():
    client = create_app().test_client()
    for route in ["/dashboard", "/royalties", "/catalog"]:
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


def test_royalties_includes_claim_workflow_ui():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
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


def test_royalties_includes_smart_recommendations():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
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
    body = client.get("/dashboard").get_data(as_text=True)
    assert 'id="add-split-form"' in body
    assert 'id="split-collaborator"' in body
    assert 'id="song-drawer-split-warning"' in body


def test_base_includes_collapsible_section_script():
    client = create_app().test_client()
    body = client.get("/dashboard").get_data(as_text=True)
    assert "section-chevron" in body
    assert "royaltySweep.collapsed." in body


def test_royalties_includes_fixes_queue_ui():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
    assert "Fixes Needed Queue" in body
    assert 'id="fixes-queue-list"' in body
    assert "Fix Now" in body
    assert "Mark Complete" in body


def test_royalties_includes_top_royalty_leaks():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
    assert "Top Royalty Leaks" in body


def test_catalog_includes_release_readiness_checker():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert "Release Readiness Checker" in body
    assert "Neon Echoes" in body
    assert "% ready" in body


def test_royalties_includes_royalty_forecast():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
    assert "Royalty Forecast" in body
    assert "Conservative" in body
    assert "Aggressive" in body


def test_valuation_includes_catalog_value_tracker():
    client = create_app().test_client()
    body = client.get("/valuation").get_data(as_text=True)
    assert "Catalog Value Tracker" in body
    assert 'id="value-tracker-current"' in body


def test_catalog_includes_register_everywhere_wizard():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert "Register Everywhere Wizard" in body
    assert 'id="wizard-song-select"' in body


def test_catalog_includes_documents_vault():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert "Documents Vault" in body
    assert "Split Sheet" in body


def test_valuation_includes_exportable_reports():
    client = create_app().test_client()
    body = client.get("/valuation").get_data(as_text=True)
    assert "Exportable Reports" in body
    assert "Investor Snapshot" in body


def test_catalog_includes_rights_conflict_center():
    client = create_app().test_client()
    body = client.get("/catalog").get_data(as_text=True)
    assert "Rights Conflict Center" in body


def test_update_fix_status_route():
    client = create_app().test_client()
    body = client.get("/royalties").get_data(as_text=True)
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

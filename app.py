import math
import os
from dataclasses import asdict
from datetime import datetime

from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db as store
from statements_engine import analyze as analyze_statement, parse_statement

from landing_config import get_landing_config
from catalog_config import get_account, get_catalog_data
from connections_config import get_connections_data
from reports_config import get_reports_data
from epk_config import get_epk_data, normalize_epk_overrides
from artwork_config import get_artwork_data, suggest_from_prompt
from links_config import get_links_data, create_smart_link
from publishing_config import get_publishing_data
from neighboring_rights_config import get_neighboring_rights_data
from sync_config import get_sync_data
from territories_config import get_territories_data
from mechanicals_config import get_mechanicals_data
from funding_config import get_funding_data
from tax_config import get_tax_data
from disputes_config import get_disputes_data, advance_dispute
from audience_config import get_audience_data
from playlists_config import get_playlists_data
from stats_config import get_stats_data
from notifications_config import (
    get_notifications_data,
    mark_notification_read,
    mark_all_read,
)
from search_config import search as global_search
from billing_config import get_billing_data
from insights_config import get_insights_data
from benchmark_config import get_benchmark_data
from capital_config import get_capital_data
from label_config import get_label_data, get_service, BRAND as LABEL_BRAND
from community_config import (
    get_marketplace_data,
    post_request,
    get_fan_label_data,
    vote_demo,
    get_fan_dashboard_data,
)
from discover_config import get_discover_data, like_track, follow_artist
from music_apis import itunes_search, odesli_lookup, ordered_platform_links
from network_config import (
    get_network_data,
    get_profile,
    get_playlist,
    get_moment,
    connect as network_connect_action,
    pitch as network_pitch_action,
    submit_to_playlist,
    enquire_show,
    claim_moment,
)

from royalty_data import (
    add_split,
    advance_claim,
    assess_advance_eligibility,
    catalog_completeness_score,
    complete_registration_step,
    COLLABORATOR_ROLES,
    estimate_catalog_value,
    get_action_center,
    get_collaborators,
    get_overview_health,
    get_royalties_overview,
    get_valuation_overview,
    platform_logo_key,
    recent_payout_rows,
    get_recovery_summary,
    invite_collaborator,
    generate_report,
    get_available_reports,
    get_catalog_value_tracker,
    get_claims,
    get_dashboard_story,
    get_documents_vault,
    get_earnings_trend,
    get_fixes_queue,
    get_health_factors,
    get_health_recommendations,
    get_kpis,
    get_missing_royalty_findings,
    get_platform_balances,
    get_platform_catalog,
    get_recent_payouts,
    get_registration_wizard,
    get_rights_conflicts,
    get_royalty_forecast,
    get_royalty_goal,
    get_royalty_leak_alerts,
    get_since_last_login_summary,
    get_smart_recommendations,
    get_song,
    get_songs,
    get_top_royalty_leaks,
    get_payout_calendar,
    get_upcoming_releases,
    WIZARD_TARGETS,
    WIZARD_TARGET_LABELS,
    live_song,
    meter_lit_segments,
    metadata_completion_score,
    money_left_on_table,
    registration_checklist_score,
    reject_claim,
    remove_collaborator,
    remove_split,
    royalty_health_score,
    royalty_progress,
    set_connection_status,
    set_fix_status,
    update_collaborator_role,
    song_check_status,
    song_missing_issues,
    split_total_percentage,
    splits_fully_confirmed,
    toggle_split_confirmed,
    total_royalties,
    upcoming_payout_total,
)


def _account_with_user(account):
    """Overlay the signed-in user's identity on the sidebar account chip.
    Safe outside a request context (tests call this directly)."""
    try:
        user_id = session.get("user_id")
    except RuntimeError:
        return account
    if not user_id:
        return account
    user = store.get_user(user_id)
    if not user:
        return account
    initials = "".join(p[0] for p in user["name"].split()[:2]).upper() or "?"
    return {**account, "name": user["name"], "initials": initials,
            "email": user["email"], "role": "Artist Account"}


def build_dashboard_context():
    balances = get_platform_balances()
    payouts = get_recent_payouts()
    kpis = get_kpis()
    total = total_royalties(balances)
    goal = get_royalty_goal()
    max_balance = max((balance.amount for balance in balances), default=0)
    balance_meters = [
        {"balance": b, "segments": meter_lit_segments(b.amount, max_balance)}
        for b in balances
    ]
    catalog = get_platform_catalog()
    health_factors = get_health_factors(catalog)

    songs = [live_song(s) for s in get_songs()]
    songs_summary = [
        {
            "song": s,
            "missing_count": len(song_missing_issues(s)),
            "connected_platform_count": len(s.platform_earnings),
            "splits_confirmed": splits_fully_confirmed(s),
            "split_total": split_total_percentage(s),
        }
        for s in songs
    ]
    metadata_scores = [metadata_completion_score(s) for s in songs]
    avg_metadata_score = round(sum(metadata_scores) / len(metadata_scores) * 100) if songs else 0
    worst_metadata_songs = sorted(songs, key=metadata_completion_score)[:3]

    payout_calendar = get_payout_calendar()
    claims = get_claims(catalog)
    alerts = get_royalty_leak_alerts(balances, payouts, kpis, catalog)
    smart_recommendations = get_smart_recommendations(alerts, songs)
    missing_findings = get_missing_royalty_findings(catalog)

    earnings_trend = get_earnings_trend()
    catalog_value = estimate_catalog_value(earnings_trend)
    advance_eligibility = assess_advance_eligibility(
        earnings_trend, payout_calendar, catalog_value["mid"], total
    )

    documents_vault = get_documents_vault(songs)
    value_tracker = get_catalog_value_tracker(earnings_trend)

    return {
        "story": get_dashboard_story(total, missing_findings, catalog_value, smart_recommendations),
        "money_left": money_left_on_table(missing_findings),
        "recovery_summary": get_recovery_summary(catalog, songs, earnings_trend),
        "fixes_queue": get_fixes_queue(catalog, songs, missing_findings),
        "top_leaks": get_top_royalty_leaks(missing_findings),
        "documents_vault": documents_vault,
        "completeness_score": catalog_completeness_score(songs, catalog, documents_vault),
        "releases": get_upcoming_releases(),
        "forecast": get_royalty_forecast(earnings_trend),
        "value_tracker": value_tracker,
        "available_reports": get_available_reports(),
        "since_last_login": get_since_last_login_summary(catalog, songs, value_tracker["pct_change"], catalog_value["mid"]),
        "account": _account_with_user(get_account()),
        "overview_health": get_overview_health(catalog, songs),
        "action_center": get_action_center(alerts, payouts),
        "recent_payout_rows": recent_payout_rows(),
        "royalties_overview": get_royalties_overview(
            balances, catalog, payout_calendar, earnings_trend, recent_payout_rows()
        ),
        "valuation_overview": get_valuation_overview(
            earnings_trend, catalog_value, advance_eligibility, value_tracker
        ),
        "logo_key": platform_logo_key,
        "conflicts": get_rights_conflicts(songs),
        "registration_wizards": [get_registration_wizard(s) for s in songs],
        "wizard_targets": WIZARD_TARGETS,
        "wizard_target_labels": WIZARD_TARGET_LABELS,
        "collaborators": get_collaborators(),
        "collaborator_roles": COLLABORATOR_ROLES,
        "alerts": alerts,
        "smart_recommendations": smart_recommendations,
        "platform_catalog": catalog,
        "health_score": royalty_health_score(health_factors),
        "health_factors": health_factors,
        "health_recommendations": get_health_recommendations(health_factors),
        "balance_meters": balance_meters,
        "total": total,
        "goal": goal,
        "progress": royalty_progress(total, goal),
        "kpis": kpis,
        "earnings_trend": earnings_trend,
        "payouts": payouts,
        "songs_summary": songs_summary,
        "avg_metadata_score": avg_metadata_score,
        "worst_metadata_songs": [
            {"song": s, "score": round(metadata_completion_score(s) * 100)}
            for s in worst_metadata_songs
        ],
        "payout_calendar": payout_calendar,
        "upcoming_payout_total": round(upcoming_payout_total(payout_calendar), 2),
        "claims": claims,
        "catalog_value": catalog_value,
        "advance_eligibility": advance_eligibility,
    }


def build_song_detail(song_id):
    song = get_song(song_id)
    if song is None:
        return None
    song = live_song(song)
    payouts = [p for p in get_recent_payouts() if p.song == song.title]
    status = song_check_status(song)
    return {
        "id": song.id,
        "title": song.title,
        "isrc": song.isrc,
        "iswc": song.iswc,
        "upc": song.upc,
        "master_owner": song.master_owner,
        "writers": song.writers,
        "producers": song.producers,
        "publisher": song.publisher,
        "lyrics_on_file": song.lyrics_on_file,
        "alternate_titles": song.alternate_titles,
        "total_earned": round(song.total_earned, 2),
        "streams": song.streams,
        "platform_earnings": song.platform_earnings,
        "splits": [
            {"collaborator": sp.collaborator, "role": sp.role, "percentage": sp.percentage, "confirmed": sp.confirmed}
            for sp in song.splits
        ],
        "split_total": split_total_percentage(song),
        "splits_confirmed": splits_fully_confirmed(song),
        "monthly_trend": song.monthly_trend,
        "check_status": status,
        "missing_issues": song_missing_issues(song),
        "metadata_score": round(metadata_completion_score(song) * 100),
        "registration_score": round(registration_checklist_score(song) * 100),
        "recent_payouts": [
            {"platform": p.platform, "status": p.status, "amount": p.amount} for p in payouts
        ],
    }


_LANDING_SOURCES = [
    ("spotify", "Spotify", "spotify"),
    ("apple-music", "Apple Music", "apple"),
    ("ascap", "ASCAP", "ascap"),
    ("bmi", "BMI", "bmi"),
    ("the-mlc", "The MLC", "mlc"),
    ("soundexchange", "SoundExchange", "soundexchange"),
    ("youtube-content-id", "YouTube Content ID", "youtube"),
]

_STATUS_LABELS = {
    "connected": ("Connected", "ok"),
    "not_connected": ("Not Connected", "danger"),
    "needs_login": ("Partial Match", "warning"),
    "error": ("Partial Match", "warning"),
    "syncing": ("Syncing", "warning"),
}

_ACTIONS = {
    "connected": ("Ready to Claim", "success"),
    "not_connected": ("Connect", "danger"),
    "needs_login": ("Investigate", "warning"),
    "error": ("Investigate", "warning"),
    "syncing": ("Investigate", "warning"),
}


def build_landing_hero(catalog, summary):
    """Assemble the recovery-scan hero visual's live data — source nodes,
    per-source recovery cards, and the center scan panel — from the real
    platform catalog and scan summary. Copy stays in the config; only the
    data-shaped parts are built here."""
    by_id = {p.id: p for p in catalog}
    by_source_amount = {s["source"]: s["amount"] for s in summary["sources"]}

    nodes, cards = [], []
    for pid, name, logo in _LANDING_SOURCES:
        p = by_id.get(pid)
        status = p.status if p else "not_connected"
        label, tone = _STATUS_LABELS.get(status, _STATUS_LABELS["not_connected"])
        action_label, action_tone = _ACTIONS.get(status, _ACTIONS["not_connected"])
        est = by_source_amount.get(name)
        if est is None:
            est = round(p.amount, 2) if p else 0.0
        nodes.append({"name": name, "logo": logo, "status_label": label, "status_tone": tone})
        cards.append({
            "name": name, "logo": logo, "est_recovery": round(est, 2),
            "action_label": action_label, "action_tone": action_tone,
        })

    return {
        "center_amount": summary["estimated_uncollected"],
        "issues_detected": summary["flagged_issues"],
        "ready_to_claim": sum(1 for c in cards if c["action_tone"] == "success"),
        "confidence_pct": summary["confidence_pct"],
        "nodes": nodes,
        "cards": cards,
    }


def create_app():
    app = Flask(__name__)
    # Session key: override via SECRET_KEY env in production.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "royalty-sweep-demo-session")
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # statement uploads
    # Trig helpers for the homepage's analog VU-meter / knob SVGs.
    app.jinja_env.globals.update(cos=math.cos, sin=math.sin, pi=math.pi)

    store.init_db()
    # Seed a one-click demo account so partners can tour without signing up.
    if store.get_user_by_email("demo@streetbanker.io") is None:
        store.create_user("demo@streetbanker.io", "Synthwave Surfer",
                          generate_password_hash("sweep"))

    def current_user():
        user_id = session.get("user_id")
        return store.get_user(user_id) if user_id else None

    def login_required_redirect():
        return redirect(url_for("login", next=request.path))

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        error = None
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            if not name or "@" not in email or len(password) < 6:
                error = "Please provide a name, a valid email, and a password of 6+ characters."
            else:
                user_id = store.create_user(email, name, generate_password_hash(password))
                if user_id is None:
                    error = "An account with that email already exists."
                else:
                    session["user_id"] = user_id
                    return redirect(url_for("onboarding"))
        return render_template("signup.html", error=error)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            user = store.get_user_by_email(email)
            if user and check_password_hash(user["password_hash"], password):
                session["user_id"] = user["id"]
                return redirect(request.args.get("next") or url_for("overview"))
            error = "Incorrect email or password."
        return render_template("login.html", error=error)

    @app.route("/login/demo", methods=["POST"])
    def login_demo():
        user = store.get_user_by_email("demo@streetbanker.io")
        session["user_id"] = user["id"]
        return redirect(url_for("onboarding"))

    @app.route("/logout", methods=["POST"])
    def logout():
        session.pop("user_id", None)
        session.pop("signed_in", None)
        return redirect(url_for("login"))

    # --- Statements: real CSV ingestion + recovery findings -------------------

    @app.route("/statements", methods=["GET", "POST"])
    def statements():
        user = current_user()
        if user is None:
            return login_required_redirect()
        error = None
        if request.method == "POST":
            f = request.files.get("statement")
            if f is None or not f.filename:
                error = "Choose a CSV file to upload."
            else:
                parsed = parse_statement(f.read(), f.filename)
                if parsed["error"]:
                    error = parsed["error"]
                else:
                    store.save_statement(user["id"], f.filename, parsed["rows"])
                    return redirect(url_for("statements"))
        ctx = build_dashboard_context()
        ctx["user"] = user
        ctx["error"] = error
        ctx["uploads"] = store.get_statements(user["id"])
        rows = store.get_statement_rows(user["id"])
        ctx["analysis"] = analyze_statement(
            [{"title": r["title"], "source": r["source"], "amount": r["amount"], "period": r["period"]}
             for r in rows]
        )
        return render_template("statements.html", active_page="statements", **ctx)

    # --- Smart links: real redirects + click tracking --------------------------

    @app.route("/l/<slug>")
    def smart_link_redirect(slug):
        link = store.get_db_link(slug)
        if link is None:
            return redirect(url_for("links"))
        store.log_click(slug)
        meta = link.get("meta")
        if meta and meta.get("links"):
            return render_template("link_landing.html", link=link, meta=meta,
                                   platform_links=ordered_platform_links(meta["links"]))
        return redirect(link["target"])

    # --- Reports: real CSV download --------------------------------------------

    @app.route("/reports/royalty-report/download.csv")
    def royalty_report_csv():
        import csv as _csv
        import io as _io
        out = _io.StringIO()
        w = _csv.writer(out)
        user = current_user()
        rows = store.get_statement_rows(user["id"]) if user else []
        if rows:
            w.writerow(["Title", "Source", "Amount", "Period"])
            for r in rows:
                w.writerow([r["title"], r["source"], "%.2f" % r["amount"], r["period"]])
        else:
            # No uploaded data yet — export the demo catalog earnings.
            w.writerow(["Title", "Platform", "Earnings"])
            for s in get_songs():
                for platform, amount in (s.platform_earnings or {}).items():
                    w.writerow([s.title, platform, "%.2f" % amount])
        return Response(
            out.getvalue(), mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=royalty-report.csv"},
        )

    # --- Inbox: persisted submissions ------------------------------------------

    @app.route("/inbox")
    def inbox():
        user = current_user()
        if user is None:
            return login_required_redirect()
        ctx = build_dashboard_context()
        ctx["inbox_items"] = store.get_inbox()
        return render_template("inbox.html", active_page="inbox", **ctx)

    @app.route("/")
    def index():
        # Homepage content is fully config-driven (landing_config); the
        # command-desk figures are editable there, not injected live.
        config = get_landing_config()

        # Only use a section image if the file is actually on disk, so a
        # not-yet-uploaded asset falls back to the built-in visual instead
        # of rendering a broken image.
        def _has_file(img):
            return bool(img) and os.path.exists(
                os.path.join(app.static_folder, img["src"].split("/static/", 1)[-1])
            )

        if not _has_file(config.get("lanes", {}).get("image")):
            config["lanes"] = {**config["lanes"], "image": None}
        if not _has_file(config.get("features_image")):
            config["features_image"] = None
        if not _has_file(config.get("royalty_sweep", {}).get("image")):
            config["royalty_sweep"] = {**config["royalty_sweep"], "image": None}
        if not _has_file(config.get("hero_visual", {}).get("image")):
            config["hero_visual"] = {**config["hero_visual"], "image": None}
        if not _has_file(config.get("top_banner")):
            config["top_banner"] = None

        return render_template("landing.html", config=config)

    @app.route("/scan/recovery-summary", methods=["POST"])
    def scan_recovery_summary():
        songs = [live_song(s) for s in get_songs()]
        catalog = get_platform_catalog()
        earnings_trend = get_earnings_trend()
        summary = get_recovery_summary(catalog, songs, earnings_trend)
        return jsonify({
            "ok": True, "summary": summary,
            "scanned_at": datetime.now().strftime("%I:%M %p").lstrip("0"),
        })

    @app.route("/overview")
    def overview():
        return render_template("overview.html", active_page="overview", **build_dashboard_context())

    @app.route("/dashboard")
    def dashboard():
        return redirect("/overview")

    @app.route("/royalties")
    def royalties():
        return render_template("royalties.html", active_page="royalties", **build_dashboard_context())

    @app.route("/catalog")
    def catalog_page():
        ctx = build_dashboard_context()
        ctx["catalog"] = get_catalog_data()
        return render_template("catalog.html", active_page="catalog", **ctx)

    @app.route("/connections")
    def connections():
        ctx = build_dashboard_context()
        ctx["conn"] = get_connections_data()
        return render_template("connections.html", active_page="connections", **ctx)

    @app.route("/recovery")
    def recovery():
        return render_template("recovery.html", active_page="recovery", **build_dashboard_context())

    @app.route("/valuation")
    def valuation():
        return render_template("valuation.html", active_page="valuation", **build_dashboard_context())

    @app.route("/reports")
    def reports():
        ctx = build_dashboard_context()
        ctx["reports_data"] = get_reports_data()
        return render_template("reports.html", active_page="reports", **ctx)

    UPLOADS_DIR = os.path.join(os.path.dirname(store.db_path()), "uploads")
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        from flask import send_from_directory
        return send_from_directory(UPLOADS_DIR, filename)

    @app.route("/epk")
    def epk():
        ctx = build_dashboard_context()
        user = current_user()
        overrides, photo = None, None
        if user:
            saved = store.get_epk(user["id"])
            if saved:
                overrides, photo = saved["data"], saved["photo"]
        ctx["user"] = user
        ctx["epk"] = get_epk_data(ctx["account"], ctx["catalog_value"],
                                  overrides=overrides, photo=photo)
        return render_template("epk.html", active_page="epk", **ctx)

    @app.route("/epk/save", methods=["POST"])
    def epk_save():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in to save your EPK."}), 401
        overrides = normalize_epk_overrides(request.get_json(silent=True) or {})
        store.save_epk(user["id"], overrides)
        return jsonify({"ok": True})

    @app.route("/epk/photo", methods=["POST"])
    def epk_photo():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in to upload a photo."}), 401
        f = request.files.get("photo")
        if f is None or not f.filename:
            return jsonify({"ok": False, "error": "Choose an image file."}), 400
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("png", "jpg", "jpeg", "webp"):
            return jsonify({"ok": False, "error": "Use a PNG, JPG, or WebP image."}), 400
        fname = "epk_%s.%s" % (user["id"], ext)
        f.save(os.path.join(UPLOADS_DIR, fname))
        photo_path = "/uploads/" + fname
        store.save_epk_photo(user["id"], photo_path)
        return jsonify({"ok": True, "photo": photo_path})

    @app.route("/epk/export", methods=["POST"])
    def epk_export():
        ctx = build_dashboard_context()
        data = get_epk_data(ctx["account"], ctx["catalog_value"])
        slug = data["name"].lower().replace(" ", "-")
        filename = f"{slug}-press-kit-{datetime.today().strftime('%Y%m%d')}.pdf"
        return jsonify({"ok": True, "filename": filename})

    @app.route("/artwork")
    def artwork():
        ctx = build_dashboard_context()
        ctx["artwork"] = get_artwork_data(ctx["account"])
        return render_template("artwork.html", active_page="artwork", **ctx)

    @app.route("/artwork/generate", methods=["POST"])
    def artwork_generate():
        payload = request.get_json(silent=True) or {}
        suggestion = suggest_from_prompt(payload.get("prompt", ""))
        return jsonify({"ok": True, "suggestion": suggestion})

    @app.route("/links")
    def links():
        ctx = build_dashboard_context()
        ctx["links_data"] = get_links_data()
        # Real, persisted links with genuine click counts sit above the demo set.
        ctx["real_links"] = store.get_db_links()
        return render_template("links.html", active_page="links", **ctx)

    @app.route("/links/create", methods=["POST"])
    def links_create():
        payload = request.get_json(silent=True) or {}
        link = create_smart_link(payload.get("title", ""), payload.get("platforms", []))
        if link is None:
            return jsonify({"ok": False, "error": "A title and at least one platform are required."}), 400
        # Universal link: if the artist pasted a track URL, resolve every
        # platform via Odesli and serve a branded all-platform landing page.
        meta = odesli_lookup(payload.get("source_url", ""))
        from urllib.parse import quote
        target = (meta or {}).get("page") or \
            "https://open.spotify.com/search/" + quote(payload.get("title", "").strip())
        user = current_user()
        slug = store.create_db_link(link["slug"], user["id"] if user else None,
                                    link["title"], target, link["platforms"], meta=meta)
        link["slug"] = slug
        link["url"] = request.host_url.rstrip("/") + "/l/" + slug
        link["real"] = True
        link["universal"] = bool(meta)
        link["platform_count"] = len((meta or {}).get("links", {}))
        return jsonify({"ok": True, "link": link})

    @app.route("/publishing")
    def publishing():
        ctx = build_dashboard_context()
        ctx["publishing"] = get_publishing_data()
        return render_template("publishing.html", active_page="publishing", **ctx)

    @app.route("/neighboring-rights")
    def neighboring_rights():
        ctx = build_dashboard_context()
        ctx["neighboring"] = get_neighboring_rights_data()
        return render_template("neighboring_rights.html", active_page="neighboring", **ctx)

    @app.route("/sync")
    def sync():
        ctx = build_dashboard_context()
        ctx["sync"] = get_sync_data()
        return render_template("sync.html", active_page="sync", **ctx)

    @app.route("/territories")
    def territories():
        ctx = build_dashboard_context()
        ctx["territories"] = get_territories_data()
        return render_template("territories.html", active_page="territories", **ctx)

    @app.route("/mechanicals")
    def mechanicals():
        ctx = build_dashboard_context()
        ctx["mechanicals"] = get_mechanicals_data()
        return render_template("mechanicals.html", active_page="mechanicals", **ctx)

    @app.route("/insights")
    def insights():
        ctx = build_dashboard_context()
        ctx["insights"] = get_insights_data(ctx["smart_recommendations"])
        return render_template("insights.html", active_page="insights", **ctx)

    @app.route("/benchmark")
    def benchmark():
        ctx = build_dashboard_context()
        ctx["benchmark"] = get_benchmark_data()
        return render_template("benchmark.html", active_page="benchmark", **ctx)

    @app.route("/marketplace")
    def marketplace():
        ctx = build_dashboard_context()
        ctx["marketplace"] = get_marketplace_data()
        return render_template("marketplace.html", active_page="marketplace", **ctx)

    @app.route("/marketplace/post", methods=["POST"])
    def marketplace_post():
        p = request.get_json(silent=True) or {}
        req = post_request(p.get("artist"), p.get("need"), p.get("genre"),
                           p.get("deal_type"), p.get("detail"))
        if req is None:
            return jsonify({"ok": False, "error": "Artist, need, and a valid deal type are required."}), 400
        store.add_inbox("marketplace_post", {k: v for k, v in req.items() if k != "deal_tone"})
        return jsonify({"ok": True, "request": req})

    @app.route("/discover")
    def discover():
        ctx = build_dashboard_context()
        ctx["discover"] = get_discover_data(request.args)
        # Real music search: iTunes catalog with artwork + 30s previews.
        q = (request.args.get("q") or "").strip()
        ctx["real_query"] = q
        ctx["real_results"] = itunes_search(q) if q else []
        return render_template("discover.html", active_page="discover", **ctx)

    @app.route("/discover/like/<track_id>", methods=["POST"])
    def discover_like_route(track_id):
        res = like_track(track_id)
        if res is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, **res})

    @app.route("/discover/follow/<artist_id>", methods=["POST"])
    def discover_follow_route(artist_id):
        return jsonify({"ok": True, **follow_artist(artist_id)})

    @app.route("/network")
    def network():
        ctx = build_dashboard_context()
        ctx["network"] = get_network_data(request.args)
        return render_template("network.html", active_page="network", **ctx)

    @app.route("/network/playlist/<playlist_id>")
    def network_playlist(playlist_id):
        pl = get_playlist(playlist_id)
        if pl is None:
            return redirect(url_for("network"))
        ctx = build_dashboard_context()
        ctx["playlist"] = pl
        ctx["curator"] = get_profile(pl["curator_id"])
        return render_template("network_playlist.html", active_page="network", **ctx)

    @app.route("/network/playlist/<playlist_id>/submit", methods=["POST"])
    def network_submit_route(playlist_id):
        data = request.get_json(silent=True) or {}
        entry = submit_to_playlist(playlist_id, data.get("song"), data.get("message"))
        if entry is None:
            return jsonify({"ok": False, "error": "This playlist isn't accepting submissions, or no track was selected."}), 400
        store.add_inbox("playlist_submission", entry)
        return jsonify({"ok": True})

    @app.route("/network/<profile_id>")
    def network_profile(profile_id):
        profile = get_profile(profile_id)
        if profile is None:
            return redirect(url_for("network"))
        ctx = build_dashboard_context()
        ctx["profile"] = profile
        return render_template("network_profile.html", active_page="network", **ctx)

    @app.route("/network/<profile_id>/connect", methods=["POST"])
    def network_connect_route(profile_id):
        status = network_connect_action(profile_id)
        if status is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "status": status})

    @app.route("/network/<profile_id>/pitch", methods=["POST"])
    def network_pitch_route(profile_id):
        data = request.get_json(silent=True) or {}
        entry = network_pitch_action(profile_id, data.get("message"), data.get("song"))
        if entry is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True})

    @app.route("/network/<profile_id>/enquire", methods=["POST"])
    def network_enquire_route(profile_id):
        data = request.get_json(silent=True) or {}
        entry = enquire_show(profile_id, data.get("city"), data.get("date"), data.get("message"))
        if entry is None:
            return jsonify({"ok": False, "error": "This profile isn't taking booking enquiries."}), 400
        store.add_inbox("booking_enquiry", entry)
        return jsonify({"ok": True})

    @app.route("/network/moment/<moment_id>")
    def network_moment(moment_id):
        moment = get_moment(moment_id)
        if moment is None:
            return redirect(url_for("network"))
        ctx = build_dashboard_context()
        ctx["moment"] = moment
        return render_template("network_moment.html", active_page="network", **ctx)

    @app.route("/network/moment/<moment_id>/claim", methods=["POST"])
    def network_claim_route(moment_id):
        serial = claim_moment(moment_id)
        if serial is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "serial": serial})

    @app.route("/fan-label")
    def fan_label():
        ctx = build_dashboard_context()
        ctx["fan_label"] = get_fan_label_data()
        return render_template("fan_label.html", active_page="fan-label", **ctx)

    @app.route("/fan-label/vote/<demo_id>", methods=["POST"])
    def fan_label_vote(demo_id):
        votes = vote_demo(demo_id)
        if votes is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "votes": votes})

    @app.route("/fans")
    def fans():
        ctx = build_dashboard_context()
        ctx["fans"] = get_fan_dashboard_data()
        return render_template("fans.html", active_page="fans", **ctx)

    @app.route("/capital")
    def capital():
        ctx = build_dashboard_context()
        ctx["capital"] = get_capital_data()
        return render_template("capital.html", active_page="capital", **ctx)

    @app.route("/services")
    def services():
        ctx = build_dashboard_context()
        ctx["label"] = get_label_data()
        return render_template("services.html", active_page="services", **ctx)

    @app.route("/services/<slug>")
    def service_detail(slug):
        service = get_service(slug)
        if service is None:
            return redirect(url_for("services"))
        ctx = build_dashboard_context()
        ctx["label"] = get_label_data()
        ctx["service"] = service
        return render_template("service_detail.html", active_page="services", **ctx)

    @app.route("/submit")
    def submit():
        ctx = build_dashboard_context()
        ctx["label"] = get_label_data()
        # Full-page designed image with clickable HTML overlays; the coded
        # page renders as the fallback until the file exists.
        ctx["submit_page_img"] = (
            "/static/img/submit-page.png"
            if os.path.exists(os.path.join(app.static_folder, "img", "submit-page.png"))
            else None
        )
        # Photoreal turntable crop (used by the coded fallback layout).
        ctx["turntable_img"] = (
            "/static/img/turntable.png"
            if os.path.exists(os.path.join(app.static_folder, "img", "turntable.png"))
            else None
        )
        return render_template("submit.html", active_page="submit", **ctx)

    @app.route("/audience")
    def audience():
        ctx = build_dashboard_context()
        ctx["audience"] = get_audience_data()
        return render_template("audience.html", active_page="audience", **ctx)

    @app.route("/playlists")
    def playlists():
        ctx = build_dashboard_context()
        ctx["playlists"] = get_playlists_data()
        return render_template("playlists.html", active_page="playlists", **ctx)

    @app.route("/stats")
    def stats():
        ctx = build_dashboard_context()
        ctx["stats"] = get_stats_data()
        return render_template("stats.html", active_page="stats", **ctx)

    @app.route("/funding")
    def funding():
        ctx = build_dashboard_context()
        ctx["funding"] = get_funding_data(ctx["advance_eligibility"])
        return render_template("funding.html", active_page="funding", **ctx)

    @app.route("/funding/request", methods=["POST"])
    def funding_request():
        payload = request.get_json(silent=True) or {}
        offer_id = (payload.get("offer_id") or "").strip()
        data = get_funding_data(build_dashboard_context()["advance_eligibility"])
        offer = next((o for o in data["offers"] if o["id"] == offer_id), None)
        if offer is None:
            return jsonify({"ok": False, "error": "Unknown offer."}), 400
        # Simulated only: record interest and return a reference. No money
        # moves and no application is actually submitted.
        reference = "REQ-" + offer_id.split("-")[-1].upper() + "-" + datetime.today().strftime("%Y%m%d")
        return jsonify({"ok": True, "reference": reference, "offer": offer["name"]})

    @app.route("/documents")
    def documents():
        return render_template("documents.html", active_page="documents", **build_dashboard_context())

    @app.route("/identifiers")
    def identifiers():
        return render_template("identifiers.html", active_page="identifiers", **build_dashboard_context())

    @app.route("/conflicts")
    def conflicts():
        return render_template("conflicts.html", active_page="conflicts", **build_dashboard_context())

    @app.route("/releases")
    def releases():
        return render_template("releases.html", active_page="releases", **build_dashboard_context())

    @app.route("/registration")
    def registration():
        return render_template("registration.html", active_page="registration", **build_dashboard_context())

    @app.route("/search")
    def search_route():
        ctx = build_dashboard_context()
        ctx["search_results"] = global_search(request.args.get("q", ""))
        return render_template("search.html", active_page="search", **ctx)

    @app.route("/notifications")
    def notifications():
        ctx = build_dashboard_context()
        ctx["notifications_data"] = get_notifications_data()
        return render_template("notifications.html", active_page="notifications", **ctx)

    @app.route("/notifications/<notification_id>/read", methods=["POST"])
    def notification_read_route(notification_id):
        mark_notification_read(notification_id)
        return jsonify({"ok": True})

    @app.route("/notifications/read-all", methods=["POST"])
    def notifications_read_all_route():
        ids = [n["id"] for n in get_notifications_data()["notifications"]]
        mark_all_read(ids)
        return jsonify({"ok": True})

    @app.route("/tax")
    def tax():
        ctx = build_dashboard_context()
        ctx["tax"] = get_tax_data()
        return render_template("tax.html", active_page="tax", **ctx)

    @app.route("/billing")
    def billing():
        ctx = build_dashboard_context()
        ctx["billing"] = get_billing_data(ctx["account"])
        return render_template("billing.html", active_page="billing", **ctx)

    @app.route("/team")
    def team():
        return render_template("team.html", active_page="team", **build_dashboard_context())

    @app.route("/onboarding")
    def onboarding():
        catalog = get_platform_catalog()
        sources = [{"name": p.platform, "logo": platform_logo_key(p.platform),
                    "connected": p.status == "connected"} for p in catalog[:8]]
        return render_template("onboarding.html", sources=sources)

    @app.route("/disputes")
    def disputes():
        ctx = build_dashboard_context()
        ctx["disputes"] = get_disputes_data()
        return render_template("disputes.html", active_page="disputes", **ctx)

    @app.route("/disputes/<dispute_id>/advance", methods=["POST"])
    def advance_dispute_route(dispute_id):
        dispute = advance_dispute(dispute_id)
        if dispute is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "stage": dispute["stage"], "resolved": dispute["resolved"]})

    @app.route("/settings")
    def settings():
        return render_template("settings.html", active_page="settings", **build_dashboard_context())

    @app.route("/scan/missing-royalties", methods=["POST"])
    def scan_missing_royalties():
        findings = get_missing_royalty_findings(get_platform_catalog())
        return jsonify({
            "ok": True,
            "count": len(findings),
            "total_estimated": round(sum(f.estimated_value for f in findings), 2),
            "findings": [asdict(f) for f in findings],
        })

    @app.route("/connections/<platform_id>/connect", methods=["POST"])
    def connect_platform(platform_id):
        entry = set_connection_status(platform_id, "connected")
        if entry is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "status": entry.status})

    @app.route("/connections/<platform_id>/disconnect", methods=["POST"])
    def disconnect_platform(platform_id):
        entry = set_connection_status(platform_id, "not_connected")
        if entry is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "status": entry.status})

    @app.route("/songs/<song_id>")
    def song_detail(song_id):
        detail = build_song_detail(song_id)
        if detail is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "song": detail})

    @app.route("/songs/<song_id>/splits", methods=["POST"])
    def add_split_route(song_id):
        data = request.get_json(silent=True) or {}
        collaborator = (data.get("collaborator") or "").strip()
        role = (data.get("role") or "").strip()
        try:
            percentage = float(data.get("percentage"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Invalid percentage"}), 400
        if not collaborator or not role or percentage <= 0:
            return jsonify({"ok": False, "error": "Missing required fields"}), 400
        splits = add_split(song_id, collaborator, role, percentage)
        if splits is None:
            return jsonify({"ok": False}), 404
        song = live_song(get_song(song_id))
        return jsonify({
            "ok": True,
            "splits": [asdict(s) for s in splits],
            "split_total": split_total_percentage(song),
        })

    @app.route("/songs/<song_id>/splits/<int:index>/remove", methods=["POST"])
    def remove_split_route(song_id, index):
        splits = remove_split(song_id, index)
        if splits is None:
            return jsonify({"ok": False}), 404
        song = live_song(get_song(song_id))
        return jsonify({
            "ok": True,
            "splits": [asdict(s) for s in splits],
            "split_total": split_total_percentage(song),
        })

    @app.route("/songs/<song_id>/splits/<int:index>/toggle", methods=["POST"])
    def toggle_split_route(song_id, index):
        splits = toggle_split_confirmed(song_id, index)
        if splits is None:
            return jsonify({"ok": False}), 404
        song = live_song(get_song(song_id))
        return jsonify({
            "ok": True,
            "splits": [asdict(s) for s in splits],
            "split_total": split_total_percentage(song),
            "splits_confirmed": splits_fully_confirmed(song),
        })

    @app.route("/claims/<claim_id>/advance", methods=["POST"])
    def advance_claim_route(claim_id):
        new_status = advance_claim(claim_id, get_platform_catalog())
        if new_status is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "status": new_status})

    @app.route("/claims/<claim_id>/reject", methods=["POST"])
    def reject_claim_route(claim_id):
        new_status = reject_claim(claim_id, get_platform_catalog())
        if new_status is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "status": new_status})

    @app.route("/fixes/<item_id>/status", methods=["POST"])
    def update_fix_status(item_id):
        data = request.get_json(silent=True) or {}
        status = data.get("status")
        result = set_fix_status(item_id, status)
        if result is None:
            return jsonify({"ok": False}), 400
        return jsonify({"ok": True, "status": result})

    @app.route("/songs/<song_id>/registration-wizard")
    def registration_wizard(song_id):
        song = get_song(song_id)
        if song is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "wizard": get_registration_wizard(song)})

    @app.route("/songs/<song_id>/registration-wizard/<target>/complete", methods=["POST"])
    def complete_registration_wizard_step(song_id, target):
        wizard = complete_registration_step(song_id, target)
        if wizard is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "wizard": wizard})

    @app.route("/reports/<report_id>/generate", methods=["POST"])
    def generate_report_route(report_id):
        report = generate_report(report_id)
        if report is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "report": report})

    @app.route("/collaborators/invite", methods=["POST"])
    def invite_collaborator_route():
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        role = data.get("role")
        songs = data.get("songs") or []
        collaborator = invite_collaborator(name, email, role, songs)
        if collaborator is None:
            return jsonify({"ok": False, "error": "Invalid name, email, or role"}), 400
        return jsonify({"ok": True, "collaborator": asdict(collaborator)})

    @app.route("/collaborators/<collaborator_id>/role", methods=["POST"])
    def update_collaborator_role_route(collaborator_id):
        data = request.get_json(silent=True) or {}
        collaborator = update_collaborator_role(collaborator_id, data.get("role"))
        if collaborator is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "collaborator": asdict(collaborator)})

    @app.route("/collaborators/<collaborator_id>/remove", methods=["POST"])
    def remove_collaborator_route(collaborator_id):
        removed = remove_collaborator(collaborator_id)
        if not removed:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True})

    @app.route("/alerts/<alert_id>/resolve", methods=["POST"])
    def resolve_alert(alert_id):
        balances = get_platform_balances()
        payouts = get_recent_payouts()
        kpis = get_kpis()
        catalog = get_platform_catalog()
        alerts = get_royalty_leak_alerts(balances, payouts, kpis, catalog)
        alert = next((a for a in alerts if a.id == alert_id), None)
        if alert is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "message": alert.resolution_message})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))

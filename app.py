import math
import os
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from flask import (Flask, Response, abort, jsonify, redirect, render_template,
                   request, session, url_for)
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
from music_apis import (itunes_search, odesli_lookup, ordered_platform_links,
                        deezer_track_metadata, musicbrainz_credits, press_mentions)
import links_engine
import links_store as mls
import rollout_engine
import rollout_store as ros
import social_providers
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

    def _ml_variant_id(campaign_id):
        """Resolve ?v= variant slug to an id for event attribution."""
        vslug = (request.args.get("v") or request.form.get("v") or "").strip()
        if not vslug:
            return None
        variant = mls.get_variant_by_slug(vslug)
        return variant["id"] if variant and variant["campaign_id"] == campaign_id else None

    @app.route("/l/<slug>")
    def smart_link_redirect(slug):
        # Street Banker Links campaigns share the /l/ namespace with quick links.
        campaign = mls.get_campaign_by_slug(slug)
        if campaign is not None:
            if campaign.get("archived_at"):
                return render_template("link_campaign_unavailable.html"), 410
            owner_preview = (campaign["status"] != "live"
                             and session.get("user_id") == campaign["user_id"])
            if campaign["status"] != "live" and not owner_preview:
                abort(404)
            variant_id = _ml_variant_id(campaign["id"])
            if not owner_preview:
                mls.track(campaign["id"], "page_view", variant_id=variant_id,
                          referrer=request.referrer,
                          utm_source=request.args.get("utm_source"))
                if request.args.get("src") == "qr":
                    mls.track(campaign["id"], "qr_scan", variant_id=variant_id)
            return render_template(
                "link_campaign.html", c=campaign,
                destinations=mls.get_destinations(campaign["id"], active_only=True),
                prerelease=links_engine.is_prerelease(campaign),
                status=links_engine.effective_status(campaign),
                variant_slug=(request.args.get("v") or ""),
                owner_preview=owner_preview,
                service_logo=dict((k, l) for k, _, l in links_engine.SERVICES))
        link = store.get_db_link(slug)
        if link is None:
            return redirect(url_for("links"))
        store.log_click(slug)
        meta = link.get("meta")
        if meta and meta.get("links"):
            return render_template("link_landing.html", link=link, meta=meta,
                                   platform_links=ordered_platform_links(meta["links"]))
        return redirect(link["target"])

    @app.route("/l/<slug>/go/<dest_id>")
    def ml_go(slug, dest_id):
        campaign = mls.get_campaign_by_slug(slug)
        dest = mls.get_destination(dest_id)
        if campaign is None or dest is None or dest["campaign_id"] != campaign["id"]:
            abort(404)
        mls.track(campaign["id"], "service_click", variant_id=_ml_variant_id(campaign["id"]),
                  service_key=dest["service_key"], referrer=request.referrer)
        target = dest["url"]
        if not target.startswith(("http://", "https://")):
            abort(400)
        return redirect(target)

    @app.route("/l/<slug>/subscribe", methods=["POST"])
    def ml_subscribe(slug):
        campaign = mls.get_campaign_by_slug(slug)
        if campaign is None or campaign["status"] != "live":
            return jsonify({"ok": False, "error": "This link is not accepting signups."}), 404
        email = (request.form.get("email") or "").strip().lower()
        name = (request.form.get("name") or "").strip()
        if "@" not in email or "." not in email.split("@")[-1]:
            return jsonify({"ok": False, "error": "Enter a valid email address."}), 400
        settings = campaign.get("settings") or {}
        consent_text = settings.get("consent_text") or (
            "I agree to receive updates about this release.")
        prerelease = links_engine.is_prerelease(campaign)
        fan_id = mls.upsert_fan(campaign["user_id"], email, campaign["id"], name)
        consent_type = "presave_notify" if prerelease else "email_marketing"
        mls.add_consent(fan_id, campaign["id"], consent_type, consent_text)
        event = "presave_notify" if prerelease else "email_capture"
        mls.track(campaign["id"], event, variant_id=_ml_variant_id(campaign["id"]),
                  fan_id=fan_id)
        mls.bump_fan(fan_id, "total_presaves" if prerelease else "total_captures")
        fan = mls.get_fan(fan_id)
        score, level = links_engine.calculate_fan_intent(fan)
        mls.set_fan_intent(fan_id, score, level)
        message = ("You're locked in — we'll remind you the moment it drops."
                   if prerelease else "You're on the list. Welcome to the inner circle.")
        return jsonify({"ok": True, "message": message})

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
        user = current_user()
        ctx["catalog_user"] = user
        ctx["my_tracks"] = store.get_catalog_tracks(user["id"]) if user else []
        # Group saved tracks into real releases keyed by UPC (or album title).
        releases = {}
        for t in ctx["my_tracks"]:
            m = t.get("meta") or {}
            key = m.get("upc") or m.get("album") or t.get("album") or t["title"]
            r = releases.setdefault(key, {
                "title": m.get("album") or t.get("album") or t["title"],
                "artist": t["artist"], "art": t["art"],
                "upc": m.get("upc") or "", "label": m.get("label") or "",
                "release_date": m.get("release_date") or "",
                "genre": m.get("genre") or "",
                "total_tracks": m.get("track_count") or 0,
                "saved_tracks": 0, "isrcs": [], "writers": [],
            })
            r["saved_tracks"] += 1
            if m.get("isrc"):
                r["isrcs"].append(m["isrc"])
            for w in m.get("writers") or []:
                if w not in r["writers"]:
                    r["writers"].append(w)
        ctx["my_releases"] = list(releases.values())
        # Aggregate real songwriter/publisher credits across saved tracks.
        writers, pubs = {}, {}
        for t in ctx["my_tracks"]:
            m = t.get("meta") or {}
            for name in m.get("writers") or []:
                writers[name] = writers.get(name, 0) + 1
            for name in m.get("publishers") or []:
                pubs.setdefault(name, {"kind": "Publisher", "songs": 0})["songs"] += 1
            if m.get("label"):
                pubs.setdefault(m["label"], {"kind": "Label", "songs": 0})["songs"] += 1
        ctx["my_writers"] = [{"name": n, "songs": c} for n, c in writers.items()]
        ctx["my_publishers"] = [{"name": n, **v} for n, v in pubs.items()]
        # Real accounts see only their own catalog — the rich sample data is
        # for the demo tour account and signed-out visitors only.
        if user and user["email"] != "demo@streetbanker.io":
            tracks = ctx["my_tracks"]
            n = len(tracks)
            with_isrc = sum(1 for t in tracks if (t.get("meta") or {}).get("isrc"))
            with_meta = sum(1 for t in tracks if t.get("meta"))
            month = datetime.now(timezone.utc).strftime("%Y-%m")
            releases_n = len(ctx["my_releases"])
            c = ctx["catalog"]
            c["summary"] = {
                "total_tracks": n,
                "tracks_added_this_month": sum(1 for t in tracks if (t.get("added") or "").startswith(month)),
                "total_releases": releases_n, "releases_added_this_month": 0,
                "registered_tracks": with_isrc, "unregistered_tracks": n - with_isrc,
                "total_isrcs": with_isrc,
                "isrc_assignment_rate": round(100 * with_isrc / n, 1) if n else 0,
            }
            c["registered_pct"] = round(100 * with_isrc / n) if n else 0
            c["unregistered_pct"] = 100 - c["registered_pct"] if n else 0
            meta_pct = round(100 * with_meta / n) if n else 0
            isrc_pct = round(100 * with_isrc / n) if n else 0
            c["health"] = {
                "total": round((meta_pct + isrc_pct) / 2),
                "status": "Good" if isrc_pct >= 80 else ("Fair" if n else "Empty"),
                "bars": [{"label": "Metadata", "pct": meta_pct},
                         {"label": "ISRCs", "pct": isrc_pct}],
            }
            missing = n - with_isrc
            c["issues"] = ([{"id": "real_isrc", "title": "Missing ISRCs", "count": missing,
                             "severity": "critical", "filter_tab": "Tracks",
                             "filter_status": "Missing ISRC"}] if missing else [])
            c["catalog_value"] = {"estimated_value": 0, "monthly_change": 0,
                                  "trend": [{"month": m, "value": 0}
                                            for m in ("Jan", "Feb", "Mar", "Apr", "May")]}
            c["tracks"], c["releases"], c["songwriters"] = [], [], []
            c["publishers"], c["splits"] = [], []
            c["recently_added"] = [{"id": t["id"], "title": t["title"], "type": "Single",
                                    "date_added": (t.get("added") or "")[:10],
                                    "status": "Registered" if (t.get("meta") or {}).get("isrc") else "Pending"}
                                   for t in tracks[:5]]
        return render_template("catalog.html", active_page="catalog", **ctx)

    @app.route("/catalog/add", methods=["POST"])
    def catalog_add():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "sign_in"}), 401
        track = request.get_json(silent=True) or {}
        if not (track.get("title") or "").strip():
            return jsonify({"ok": False, "error": "A track title is required."}), 400
        track_id = store.add_catalog_track(user["id"], track)
        if track_id is None:
            return jsonify({"ok": False, "error": "Already in your catalog."}), 409
        # Best-effort metadata enrichment: ISRC/UPC/label from Deezer.
        # The track stays saved even when the lookup finds nothing.
        meta = deezer_track_metadata(track.get("title"), track.get("artist"))
        if meta:
            # Second hop: the ISRC unlocks songwriter/publisher credits.
            credits = musicbrainz_credits(meta.get("isrc"))
            if credits:
                meta.update(credits)
            store.set_catalog_track_meta(user["id"], track_id, meta)
        return jsonify({"ok": True, "id": track_id, "meta": meta})

    @app.route("/catalog/remove/<track_id>", methods=["POST"])
    def catalog_remove(track_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "sign_in"}), 401
        return jsonify({"ok": store.remove_catalog_track(user["id"], track_id)})

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

    def _slugify(name):
        s = "".join(c if c.isalnum() else "-" for c in (name or "").lower())
        return "-".join(p for p in s.split("-") if p) or "artist"

    def _ensure_epk_slug(user):
        saved = store.get_epk(user["id"])
        if saved and saved.get("slug"):
            return saved["slug"]
        slug = _slugify(user["name"])
        while store.get_epk_by_slug(slug) is not None:
            slug = "%s-%s" % (_slugify(user["name"]), uuid.uuid4().hex[:4])
        store.set_epk_slug(user["id"], slug)
        return slug

    _EPK_ASSET_KINDS = [("press_photo", "Press Photo"), ("logo", "Logo"),
                        ("cover_art", "Cover Art"), ("live_photo", "Live Photo")]
    _EPK_KIND_LABELS = dict(_EPK_ASSET_KINDS)

    def _labeled_assets(assets):
        return [{**a, "label": _EPK_KIND_LABELS.get(a["kind"], a["kind"])}
                for a in assets if a["kind"] in _EPK_KIND_LABELS]

    @app.route("/epk")
    def epk():
        ctx = build_dashboard_context()
        user = current_user()
        overrides, photo, assets = None, None, []
        if user:
            saved = store.get_epk(user["id"])
            if saved:
                overrides, photo = saved["data"], saved["photo"]
            assets = _labeled_assets(store.get_epk_assets(user["id"]))
            ctx["epk_public_url"] = "/epk/" + _ensure_epk_slug(user)
        ctx["user"] = user
        ctx["asset_kinds"] = _EPK_ASSET_KINDS
        ctx["epk"] = get_epk_data(ctx["account"], ctx["catalog_value"],
                                  overrides=overrides, photo=photo, assets=assets)
        return render_template("epk.html", active_page="epk", **ctx)

    @app.route("/epk/press/search")
    def epk_press_search():
        if current_user() is None:
            return jsonify({"ok": False, "results": []}), 401
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"ok": False, "results": []})
        return jsonify({"ok": True, "results": press_mentions(q)})

    @app.route("/epk/asset/<kind>", methods=["POST"])
    def epk_asset_upload(kind):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in to upload assets."}), 401
        if kind not in _EPK_KIND_LABELS:
            return jsonify({"ok": False, "error": "Unknown asset type."}), 400
        f = request.files.get("asset")
        if f is None or not f.filename:
            return jsonify({"ok": False, "error": "Choose an image file."}), 400
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("png", "jpg", "jpeg", "webp"):
            return jsonify({"ok": False, "error": "Use a PNG, JPG, or WebP image."}), 400
        fname = "epkasset_%s_%s.%s" % (user["id"], kind, ext)
        f.save(os.path.join(UPLOADS_DIR, fname))
        path = "/uploads/" + fname
        store.save_epk_asset(user["id"], kind, path)
        return jsonify({"ok": True, "path": path})

    @app.route("/epk/asset/<kind>/visibility", methods=["POST"])
    def epk_asset_visibility(kind):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        public = bool((request.get_json(silent=True) or {}).get("public"))
        return jsonify({"ok": store.set_epk_asset_public(user["id"], kind, public)})

    @app.route("/epk/<slug>")
    def epk_public(slug):
        prof = store.get_epk_by_slug(slug)
        if prof is None:
            abort(404)
        ctx = build_dashboard_context()
        name = prof["user_name"]
        initials = "".join(w[0] for w in name.split()[:2]).upper() or "SB"
        assets = _labeled_assets(store.get_epk_assets(prof["user_id"], public_only=True))
        data = get_epk_data({"name": name, "initials": initials},
                            ctx["catalog_value"],
                            overrides=prof["data"], photo=prof["photo"],
                            assets=assets)
        return render_template("epk_public.html", e=data, slug=slug)

    @app.route("/epk/<slug>/kit.zip")
    def epk_kit_zip(slug):
        prof = store.get_epk_by_slug(slug)
        if prof is None:
            abort(404)
        assets = _labeled_assets(store.get_epk_assets(prof["user_id"], public_only=True))
        import io
        import zipfile
        buf = io.BytesIO()
        added = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for a in assets:
                fpath = os.path.join(UPLOADS_DIR, os.path.basename(a["path"]))
                if os.path.exists(fpath):
                    ext = fpath.rsplit(".", 1)[-1]
                    zf.write(fpath, "%s-%s.%s" % (slug, a["kind"].replace("_", "-"), ext))
                    added += 1
        if not added:
            abort(404)
        buf.seek(0)
        return Response(buf.read(), mimetype="application/zip", headers={
            "Content-Disposition": "attachment; filename=%s-press-kit.zip" % slug})

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

    def _ml_campaign_card(c):
        counts = mls.event_counts(c["id"])
        visits = counts.get("page_view", 0)
        clicks = counts.get("service_click", 0)
        dests = mls.get_destinations(c["id"])
        score = links_engine.calculate_street_banker_score(c, dests)
        status = links_engine.effective_status(c)
        return {**c, "visits": visits, "clicks": clicks,
                "ctr": round(100 * clicks / visits, 1) if visits else 0.0,
                "captures": counts.get("email_capture", 0),
                "presaves": counts.get("presave_notify", 0),
                "score": score["total"], "warnings": score["warnings"],
                "eff_status": status,
                "status_tone": links_engine.STATUS_TONES.get(status, "gray"),
                "dest_count": len(dests)}

    @app.route("/links")
    def links():
        ctx = build_dashboard_context()
        ctx["links_data"] = get_links_data()
        # Real, persisted links with genuine click counts sit above the demo set.
        ctx["real_links"] = store.get_db_links()
        user = current_user()
        ctx["links_user"] = user
        ctx["ml_campaigns"] = ([_ml_campaign_card(c) for c in mls.list_campaigns(user["id"])]
                               if user else [])
        return render_template("links.html", active_page="links", **ctx)

    def _ml_slug(title):
        base = _slugify(title)
        slug = base
        while (mls.get_campaign_by_slug(slug) is not None
               or store.get_db_link(slug) is not None
               or mls.get_variant_by_slug(slug) is not None):
            slug = "%s-%s" % (base, uuid.uuid4().hex[:4])
        return slug

    def _ml_form_fields():
        f = request.form
        settings = {
            "email_capture": bool(f.get("email_capture")),
            "consent_text": (f.get("consent_text") or "").strip()[:400],
            "privacy_url": (f.get("privacy_url") or "").strip()[:300],
            "cta_text": (f.get("cta_text") or "").strip()[:60],
            "accent": (f.get("accent") or "").strip()[:7],
        }
        uploaded = _ml_cover_upload()
        return {
            "title": (f.get("title") or "").strip()[:120],
            "artist_name": (f.get("artist_name") or "").strip()[:120],
            "release_type": f.get("release_type") if f.get("release_type") in links_engine.RELEASE_TYPES else "Single",
            "campaign_type": f.get("campaign_type") if f.get("campaign_type") in links_engine.CAMPAIGN_TYPE_NAMES else "release",
            "release_date": (f.get("release_date") or "").strip()[:10],
            "cover_url": uploaded or (f.get("cover_url") or "").strip()[:500],
            "description": (f.get("description") or "").strip()[:600],
            "settings": settings,
        }

    def _ml_form_destinations():
        out, order = [], 0
        for key, name, _logo in links_engine.SERVICES:
            url = (request.form.get("dest_" + key) or "").strip()[:500]
            if url and url.startswith(("http://", "https://")):
                out.append({"service_key": key, "service_name": name,
                            "url": url, "sort_order": order})
                order += 1
        return out

    @app.route("/links/autofill")
    def ml_autofill():
        """Paste one track URL -> Odesli resolves every platform + metadata."""
        if current_user() is None:
            return jsonify({"ok": False}), 401
        url = (request.args.get("url") or "").strip()
        meta = odesli_lookup(url)
        if not meta:
            return jsonify({"ok": False, "error": "Couldn't resolve that link — check the URL or fill services manually."})
        links = {}
        for odesli_key, service_key in links_engine.ODESLI_TO_SERVICE.items():
            if meta["links"].get(odesli_key):
                links[service_key] = meta["links"][odesli_key]
        return jsonify({"ok": True, "title": meta.get("title") or "",
                        "artist": meta.get("artist") or "",
                        "art": meta.get("art") or "", "links": links,
                        "found": len(links)})

    def _ml_cover_upload():
        """Optional cover art file upload; returns a served path or None."""
        f = request.files.get("cover_file")
        if f is None or not f.filename:
            return None
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("png", "jpg", "jpeg", "webp"):
            return None
        fname = "mlcover_%s.%s" % (uuid.uuid4().hex, ext)
        f.save(os.path.join(UPLOADS_DIR, fname))
        return "/uploads/" + fname

    @app.route("/links/new", methods=["GET", "POST"])
    def ml_new():
        user = current_user()
        if user is None:
            return login_required_redirect()
        if request.method == "POST":
            fields = _ml_form_fields()
            if not fields["title"]:
                return render_template("links_builder.html", active_page="links",
                                       c=None, destinations=[], engine=links_engine,
                                       error="A campaign title is required.",
                                       **build_dashboard_context())
            cid = mls.create_campaign(user["id"], _ml_slug(fields["title"]), fields)
            mls.set_destinations(cid, _ml_form_destinations())
            return redirect("/links/%s/edit" % cid)
        return render_template("links_builder.html", active_page="links",
                               c=None, destinations=[], engine=links_engine,
                               error=None, **build_dashboard_context())

    def _ml_owned(campaign_id):
        user = current_user()
        if user is None:
            return None, login_required_redirect()
        campaign = mls.get_campaign(campaign_id, user["id"])
        if campaign is None:
            return None, abort(404)
        return campaign, None

    @app.route("/links/<cid>/edit", methods=["GET", "POST"])
    def ml_edit(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        if request.method == "POST":
            mls.update_campaign(cid, campaign["user_id"], _ml_form_fields())
            mls.set_destinations(cid, _ml_form_destinations())
            campaign = mls.get_campaign(cid)
        dests = mls.get_destinations(cid)
        score = links_engine.calculate_street_banker_score(campaign, dests)
        return render_template("links_builder.html", active_page="links",
                               c=campaign, destinations=dests, engine=links_engine,
                               score=score, error=None,
                               eff_status=links_engine.effective_status(campaign),
                               **build_dashboard_context())

    @app.route("/links/<cid>/publish", methods=["POST"])
    def ml_publish(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        mls.update_campaign(cid, campaign["user_id"],
                            {"status": "live", "published_at": store._now(),
                             "archived_at": None})
        return redirect("/links/%s/edit" % cid)

    @app.route("/links/<cid>/unpublish", methods=["POST"])
    def ml_unpublish(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        mls.update_campaign(cid, campaign["user_id"], {"status": "draft"})
        return redirect("/links/%s/edit" % cid)

    @app.route("/links/<cid>/archive", methods=["POST"])
    def ml_archive(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        mls.update_campaign(cid, campaign["user_id"],
                            {"status": "draft", "archived_at": store._now()})
        return redirect("/links")

    @app.route("/links/<cid>/duplicate", methods=["POST"])
    def ml_duplicate(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        new_id = mls.duplicate_campaign(cid, campaign["user_id"],
                                        _ml_slug(campaign["title"] + "-copy"))
        return redirect("/links/%s/edit" % new_id)

    @app.route("/links/<cid>/analytics")
    def ml_analytics(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        counts = mls.event_counts(cid)
        visits = counts.get("page_view", 0)
        clicks = counts.get("service_click", 0)
        variants = mls.list_variants(cid)
        vstats = mls.variant_stats(cid)
        dests = mls.get_destinations(cid)
        return render_template(
            "links_analytics.html", active_page="links", c=campaign,
            counts=counts, visits=visits, clicks=clicks,
            ctr=round(100 * clicks / visits, 1) if visits else 0.0,
            top_services_named=[(links_engine.SERVICE_NAMES.get(k, k), n)
                                for k, n in mls.breakdown(cid, "service_key", "service_click")],
            top_referrers=mls.breakdown(cid, "referrer"),
            top_utm=mls.breakdown(cid, "utm_source"),
            timeline=mls.timeline(cid),
            variants=variants, vstats=vstats,
            score=links_engine.calculate_street_banker_score(campaign, dests),
            eff_status=links_engine.effective_status(campaign),
            service_names=links_engine.SERVICE_NAMES,
            **build_dashboard_context())

    @app.route("/links/<cid>/variants", methods=["GET", "POST"])
    def ml_variants(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()[:80]
            if name:
                mls.create_variant(cid, name, _ml_slug(campaign["slug"] + "-" + name),
                                   utm_source=(request.form.get("utm_source") or "").strip()[:80],
                                   utm_medium=(request.form.get("utm_medium") or "").strip()[:80])
        return render_template(
            "links_variants.html", active_page="links", c=campaign,
            variants=mls.list_variants(cid), vstats=mls.variant_stats(cid),
            **build_dashboard_context())

    @app.route("/links/<cid>/qr.svg")
    def ml_qr(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        import io as _io
        import segno
        url = request.host_url.rstrip("/") + "/l/" + campaign["slug"] + "?src=qr"
        vslug = (request.args.get("v") or "").strip()
        if vslug:
            url += "&v=" + vslug
        buf = _io.BytesIO()
        segno.make(url, error="m").save(buf, kind="svg", scale=6,
                                        dark="#141210", light=None)
        return Response(buf.getvalue(), mimetype="image/svg+xml")

    # --- Rollout Studio: social rollout campaigns wired into Links ------------

    def _ro_owned(cid):
        user = current_user()
        if user is None:
            return None, login_required_redirect()
        campaign = ros.get_campaign(cid, user["id"])
        if campaign is None:
            abort(404)
        return campaign, None

    def _ro_post_attribution(campaign):
        """Per-post visits/clicks/fans pulled from ml_events via each
        post's Links variant."""
        posts = ros.list_posts(campaign["id"])
        stats = (mls.variant_stats(campaign["ml_campaign_id"])
                 if campaign.get("ml_campaign_id") else {})
        for p in posts:
            st = stats.get(p["variant_id"], {})
            p["visits"] = st.get("page_view", 0)
            p["clicks"] = st.get("service_click", 0)
            p["fans"] = st.get("email_capture", 0) + st.get("presave_notify", 0)
        return posts

    @app.route("/rollout-studio")
    def rollout_dashboard():
        user = current_user()
        ctx = build_dashboard_context()
        cards = []
        if user:
            for c in ros.list_campaigns(user["id"]):
                counts = ros.post_status_counts(c["id"])
                posts = _ro_post_attribution(c)
                cards.append({**c, "counts": counts,
                              "total_posts": sum(counts.values()),
                              "clicks": sum(p["clicks"] for p in posts),
                              "fans": sum(p["fans"] for p in posts)})
        return render_template("rollout_dashboard.html", active_page="rollout",
                               campaigns=cards, rollout_user=user, **ctx)

    @app.route("/rollout-studio/new", methods=["GET", "POST"])
    def rollout_new():
        user = current_user()
        if user is None:
            return login_required_redirect()
        ml_campaigns = mls.list_campaigns(user["id"])
        if request.method == "POST":
            f = request.form
            platforms = [k for k, _, _ in rollout_engine.PLATFORMS if f.get("pf_" + k)]
            ml_id = f.get("ml_campaign_id") or None
            if ml_id and mls.get_campaign(ml_id, user["id"]) is None:
                ml_id = None
            cid = ros.create_campaign(user["id"], {
                "title": (f.get("title") or "").strip()[:120],
                "artist_name": (f.get("artist_name") or "").strip()[:120],
                "release_date": (f.get("release_date") or "").strip()[:10],
                "rollout_length": f.get("rollout_length") or 14,
                "goal": f.get("goal") if f.get("goal") in dict(rollout_engine.CAMPAIGN_GOALS) else "presaves",
                "tone": f.get("tone") if f.get("tone") in dict(rollout_engine.TONES) else "premium",
                "platforms": platforms,
                "ml_campaign_id": ml_id,
            })
            # Creative uploads: art + optional video, plus lyrics text.
            for field, kind in (("art_file", "image"), ("video_file", "video")):
                up = request.files.get(field)
                if up and up.filename:
                    ext = up.filename.rsplit(".", 1)[-1].lower()
                    allowed = ("png", "jpg", "jpeg", "webp") if kind == "image" else ("mp4", "mov", "webm")
                    if ext in allowed:
                        fname = "ro_%s_%s.%s" % (cid, kind, ext)
                        up.save(os.path.join(UPLOADS_DIR, fname))
                        ros.add_asset(cid, kind, file_path="/uploads/" + fname)
            lyrics = (f.get("lyrics") or "").strip()[:8000]
            if lyrics:
                ros.add_asset(cid, "lyrics", lyrics_text=lyrics)
            return redirect("/rollout-studio/%s" % cid)
        return render_template("rollout_new.html", active_page="rollout",
                               engine=rollout_engine, ml_campaigns=ml_campaigns,
                               **build_dashboard_context())

    @app.route("/rollout-studio/<cid>/generate", methods=["POST"])
    def rollout_generate(cid):
        campaign, err = _ro_owned(cid)
        if err:
            return err
        assets = ros.list_assets(cid)
        lyrics = next((a["lyrics_text"] for a in assets if a["asset_type"] == "lyrics"), "")
        video = next((a["id"] for a in assets if a["asset_type"] == "video"), None)
        image = next((a["id"] for a in assets if a["asset_type"] == "image"), None)
        ros.clear_posts(cid)
        posts = rollout_engine.generate_rollout(campaign, lyrics=lyrics,
                                                video_asset_id=video, image_asset_id=image)
        for p in posts:
            # One tracked Links variant per post — the attribution backbone.
            if campaign.get("ml_campaign_id"):
                vname = rollout_engine.variant_name(p["platform"], p["phase"],
                                                    p["scheduled_date"])
                vslug = _ml_slug(vname.replace("_", "-"))
                p["variant_id"] = mls.create_variant(
                    campaign["ml_campaign_id"], vname, vslug,
                    utm_source=p["platform"], utm_medium="rollout")
            ros.add_post(cid, p)
        ros.set_status(cid, "generated")
        return redirect("/rollout-studio/%s" % cid)

    @app.route("/rollout-studio/<cid>")
    def rollout_overview(cid):
        campaign, err = _ro_owned(cid)
        if err:
            return err
        posts = _ro_post_attribution(campaign)
        assets = ros.list_assets(cid)
        ml_campaign = (mls.get_campaign(campaign["ml_campaign_id"])
                       if campaign.get("ml_campaign_id") else None)
        variants = ({v["id"]: v for v in mls.list_variants(campaign["ml_campaign_id"])}
                    if campaign.get("ml_campaign_id") else {})
        return render_template("rollout_overview.html", active_page="rollout",
                               c=campaign, posts=posts, assets=assets,
                               ml_campaign=ml_campaign, variants=variants,
                               direction=rollout_engine.creative_direction(campaign),
                               next_action=rollout_engine.next_action(campaign, posts, assets),
                               counts=ros.post_status_counts(cid),
                               phase_names=rollout_engine.PHASE_NAMES,
                               platform_names=rollout_engine.PLATFORM_NAMES,
                               **build_dashboard_context())

    @app.route("/rollout-studio/<cid>/posts", methods=["GET", "POST"])
    def rollout_posts(cid):
        campaign, err = _ro_owned(cid)
        if err:
            return err
        if request.method == "POST":
            post = ros.get_post(request.form.get("post_id") or "")
            if post and post["campaign_id"] == cid:
                action = request.form.get("action")
                if action == "approve":
                    ros.update_post(post["id"], {"status": "approved"})
                elif action == "reject":
                    ros.update_post(post["id"], {"status": "rejected"})
                elif action == "posted":
                    ros.update_post(post["id"], {
                        "status": "posted",
                        "published_url": (request.form.get("published_url") or "").strip()[:300]})
                elif action == "save":
                    ros.update_post(post["id"], {
                        "caption": (request.form.get("caption") or "").strip()[:2200],
                        "hashtags": (request.form.get("hashtags") or "").strip()[:300],
                        "scheduled_date": (request.form.get("scheduled_date") or "").strip()[:10]})
            return redirect("/rollout-studio/%s/posts" % cid)
        posts = _ro_post_attribution(campaign)
        variants = ({v["id"]: v for v in mls.list_variants(campaign["ml_campaign_id"])}
                    if campaign.get("ml_campaign_id") else {})
        ml_campaign = (mls.get_campaign(campaign["ml_campaign_id"])
                       if campaign.get("ml_campaign_id") else None)
        return render_template("rollout_posts.html", active_page="rollout",
                               c=campaign, posts=posts, variants=variants,
                               ml_campaign=ml_campaign,
                               phase_names=rollout_engine.PHASE_NAMES,
                               platform_names=rollout_engine.PLATFORM_NAMES,
                               **build_dashboard_context())

    @app.route("/rollout-studio/<cid>/calendar")
    def rollout_calendar(cid):
        campaign, err = _ro_owned(cid)
        if err:
            return err
        posts = ros.list_posts(cid)
        by_date = {}
        for p in posts:
            by_date.setdefault(p["scheduled_date"], []).append(p)
        return render_template("rollout_calendar.html", active_page="rollout",
                               c=campaign, by_date=sorted(by_date.items()),
                               phase_names=rollout_engine.PHASE_NAMES,
                               platform_names=rollout_engine.PLATFORM_NAMES,
                               **build_dashboard_context())

    @app.route("/rollout-studio/<cid>/performance")
    def rollout_performance(cid):
        campaign, err = _ro_owned(cid)
        if err:
            return err
        posts = _ro_post_attribution(campaign)
        ranked = sorted(posts, key=lambda p: (p["fans"], p["clicks"], p["visits"]),
                        reverse=True)
        by_platform = {}
        for p in posts:
            agg = by_platform.setdefault(p["platform"], {"visits": 0, "clicks": 0, "fans": 0})
            for k in agg:
                agg[k] += p[k]
        return render_template("rollout_performance.html", active_page="rollout",
                               c=campaign, posts=ranked, by_platform=by_platform,
                               totals={"visits": sum(p["visits"] for p in posts),
                                       "clicks": sum(p["clicks"] for p in posts),
                                       "fans": sum(p["fans"] for p in posts)},
                               phase_names=rollout_engine.PHASE_NAMES,
                               platform_names=rollout_engine.PLATFORM_NAMES,
                               **build_dashboard_context())

    @app.route("/rollout-studio/<cid>/socials")
    def rollout_socials(cid):
        campaign, err = _ro_owned(cid)
        if err:
            return err
        return render_template("rollout_socials.html", active_page="rollout",
                               c=campaign, providers=social_providers.provider_status(),
                               **build_dashboard_context())

    @app.route("/links/fans")
    def ml_fans():
        user = current_user()
        if user is None:
            return login_required_redirect()
        q = (request.args.get("q") or "").strip()
        fans = mls.list_fans(user["id"], q)
        campaigns = {c["id"]: c["title"] for c in mls.list_campaigns(user["id"])}
        return render_template("links_fans.html", active_page="links",
                               fans=fans, q=q, campaign_titles=campaigns,
                               intent_tones=links_engine.INTENT_TONES,
                               **build_dashboard_context())

    @app.route("/links/fans/export.csv")
    def ml_fans_export():
        user = current_user()
        if user is None:
            return login_required_redirect()
        import csv as _csv
        import io as _io
        out = _io.StringIO()
        w = _csv.writer(out)
        w.writerow(["Email", "Name", "Visits", "Clicks", "Pre-saves", "Captures",
                    "Intent Score", "Intent Level", "First Seen", "Last Active"])
        for f in mls.list_fans(user["id"]):
            w.writerow([f["email"], f["name"], f["total_visits"], f["total_clicks"],
                        f["total_presaves"], f["total_captures"], f["intent_score"],
                        f["intent_level"], f["created"], f["updated"]])
        return Response(out.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=street-banker-fans.csv"})

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

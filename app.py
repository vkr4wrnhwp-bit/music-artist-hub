import json
import hmac
import math
import os
import time
import urllib.parse
import uuid
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone

from flask import (Flask, Response, abort, g, jsonify, redirect, render_template,
                   request, session, url_for)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

import db as store
import demo_seed
import acr_provider
import documents_engine
import inbox_engine
import board
import lights_store
import operator_desk
import audio_admin
import readiness
import audio_providers
import audio_studio
import audio_store
import live
import live_store
import studio
import studio_store
import audio_webhooks
import homepage_edit
import partner_os
import passport_os
import stage_os
import partner_store
# NB: signal_hub, not signal - a module named `signal` in the repo root would
# shadow the standard library module that gunicorn and Werkzeug import.
import signal_hub
import press_desk
import tour_os
import demo_accounts
import page_switches
import rooms
import team_areas
import producers
import distributor_letter
import recovery_engine
import recovery_mlc
import report_builder
import sandbox
import shopify_buy
import shopify_customers
import since_engine
import tutor
import valuation_engine

# The address this product answers to in anything that outlives the
# request that made it - emails, and the user-agent we identify as to
# third parties.
#
# Everything else builds links from request.url_root, which follows
# whichever host the visitor arrived on. That is right for share links:
# a fan who opened a smart link on one domain should get the same domain
# back. It is wrong for email, because a link in an inbox has no request
# behind it, and because Host is attacker-controlled input - a forged
# Host on a password-reset request would mail a real token pointing at
# somebody else's server.
#
# Render's edge currently refuses unconfigured hosts (a forged Host gets
# a 403 and never reaches this process), so that is not exploitable
# today. This does not depend on that holding.
#
# Set PUBLIC_BASE_URL in Render when the real domain lands.
PUBLIC_BASE_URL = (os.environ.get("PUBLIC_BASE_URL")
                   or "https://street-banker.onrender.com").rstrip("/")

# The host partner subdomains hang off: foxglove.street-banker.onrender.com
# resolves the partner with slug "foxglove". Set PARTNER_ROOT_DOMAIN on a
# deployment that owns a shorter apex. A partner with its own custom
# domain never touches this - that is matched first, exactly.
_PARTNER_ROOT = (os.environ.get("PARTNER_ROOT_DOMAIN")
                 or PUBLIC_BASE_URL.split("//")[-1].split("/")[0]).strip().lower()


def public_url(path=""):
    return PUBLIC_BASE_URL + "/" + path.lstrip("/") if path else PUBLIC_BASE_URL

# Accounts that get the top plan without paying: the owner's own.
#
# Stored as SHA-256, not plaintext, because this repo is on GitHub and an
# email in source is an email in a scraper's list. Add more without a
# deploy by setting OWNER_EMAILS to a comma-separated list.
#
# This grants a PLAN. It is not an authentication bypass - the password
# check still has to pass first, and nothing here touches login, billing
# integrity, or the demo account.
_OWNER_EMAIL_HASHES = {
    "9bc043ae1f94a567c427d016bd0f42293a724c71e59b5b6b6c9ad3bf869e8c30",
    "aa35acb84a0b782e5bdf902478d53127d9fc68f885493cd231fbe98b1f5ad020",
}
OWNER_PLAN = "label"          # top of plans.TIER_RANK


def _is_owner_email(email):
    import hashlib
    email = (email or "").strip().lower()
    if not email:
        return False
    extra = {e.strip().lower()
             for e in (os.environ.get("OWNER_EMAILS") or "").split(",")
             if e.strip()}
    if email in extra:
        return True
    digest = hashlib.sha256(email.encode()).hexdigest()
    return digest in _OWNER_EMAIL_HASHES


def _ref_spent_key(email):
    import hashlib
    return "ref_spent:" + hashlib.sha256((email or "").strip().lower().encode()).hexdigest()


def _grant_owner_plan(user):
    """Put an owner account on the top plan. Idempotent, and a no-op for
    everybody else."""
    if not user or not _is_owner_email(user.get("email")):
        return False
    if (user.get("plan") or "") != OWNER_PLAN:
        store.set_user_plan(user["id"], OWNER_PLAN)
        return True
    return False
import sb_suite_sso as suite_sso   # one account for every suite: Street Banker hands the artist across
import tour_hub_rules as touring   # the old Tour Hub's rule set: public rider/show-day pages, Money Queue fallback
import tour_store
import artist_identity
import artist_os
import hubs as hub_defs
from statements_engine import (
period_year,analyze as analyze_statement, parse_statement,
                               build_royalty_summary)

from landing_config import get_landing_config
from artist_eq_config import get_artist_eq_config
from departments_config import get_departments_config
from eight_tools_config import get_eight_tools_config
import fan_list_import
import hypeddit_ingest
import split_home
from artist_twin_config import get_artist_twin_config
from lanes_config import get_lanes_config
from creative_config import get_creative_config
from rollout_config import get_rollout_config
from sweep_config import get_sweep_config
from distro_config import get_distro_config
from passport_config import get_passport_config, completeness as passport_completeness
from closing_config import get_closing_config
from release_signal import get_release_signal_config
import capability_status
# How many bytes of bucket objects one backup archive will carry. A
# catalogue of masters runs to gigabytes and a download that never
# finishes is not a backup, so anything past this is NAMED in
# OBJECTS.csv rather than dropped in silence. Module scope so a test
# can lower it rather than allocating two gigabytes to prove the
# skip path works.
BACKUP_BLOB_BUDGET = 2 * 1024 * 1024 * 1024

import blob_inventory
import blob_store
import stemsplit_provider as stemsplit
import hours_engine
import backup_store
import convert_engine
import audio_readiness
import epk_config
import rollout_learning
import score_history
import firstrun

def _hours_float(value, default=0.0):
    """Form numbers, forgivingly: a blank or a typo becomes the default
    rather than a 500, and nothing negative ever reaches the database."""
    try:
        return max(0.0, float(str(value).strip()))
    except (TypeError, ValueError):
        return default

from catalog_config import get_account, get_catalog_data
from reports_config import get_reports_data
from epk_config import get_epk_data, normalize_epk_overrides
from artwork_config import (get_artwork_data, suggest_from_prompt,
                            list_uploads as list_artwork_uploads,
                            take_upload as take_artwork_upload,
                            owned_prefixes as artwork_upload_prefixes)
from links_config import get_links_data, create_smart_link
from funding_config import get_funding_data
from disputes_config import get_disputes_data, advance_dispute
from search_config import search as global_search
from billing_config import get_billing_data
from benchmark_config import get_benchmark_data
from capital_config import get_capital_data
from label_config import get_label_data, get_service, BRAND as LABEL_BRAND
from community_config import (
    get_marketplace_data,
    get_fan_label_data,
    vote_demo,
    get_fan_dashboard_data,
)
from discover_config import get_discover_data, like_track, follow_artist
import coverage_check
import music_apis
from music_apis import (itunes_search, odesli_lookup, ordered_platform_links,
                        deezer_track_metadata, press_mentions)
import links_engine
import links_store as mls
import press_store
import rollout_engine
import rollout_store as ros
import social_providers
import command_center as cc
import qualification
import sync_simulator
import trust_score
import bandsintown_provider as bandsintown
import tour_dates as tour_dates_feed
import capital_engine
import stripe_provider as stripe_billing
import sales_switch
import soundcharts_budget
import release_ready               # Creative Studio's Release-Ready: RoEx mix report, previews, paid master
import release_ready_settings
import release_ready_store
import royalty_types
import insights_engine
import email_provider as emailer
import spotify_provider as spotify
import artist_twin as twin
import plans
from network_config import (
    blank_state as network_blank_state,
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
    assess_advance_eligibility,
    estimate_catalog_value,
    get_action_center,
    get_overview_health,
    get_royalties_overview,
    get_valuation_overview,
    platform_logo_key,
    recent_payout_rows,
    get_recovery_summary,
    report_type,
    record_generated_report,
    get_catalog_value_tracker,
    get_claims,
    get_dashboard_story,
    get_documents_vault,
    get_earnings_trend,
    get_fixes_queue,
    get_kpis,
    get_missing_royalty_findings,
    get_platform_balances,
    get_platform_catalog,
    get_recent_payouts,
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
    live_song,
    metadata_completion_score,
    money_left_on_table,
    registration_checklist_score,
    royalty_progress,
    song_check_status,
    song_missing_issues,
    split_total_percentage,
    splits_fully_confirmed,
    total_royalties,
    upcoming_payout_total,
)


def _team_owner():
    """The account a team seat is working inside this request, or None.
    team_seat_gate resolved the seat before any page renders, and
    current_user() drops team_as the moment the seat is gone."""
    try:
        if not session.get("team_as"):
            return None
    except RuntimeError:
        return None
    return ((getattr(g, "_team_seat", None) or (None, None))[1] or {}).get("owner")


def _account_with_user(account):
    """Overlay the signed-in user's identity on the sidebar account chip.
    Safe outside a request context (tests call this directly). Inside an
    artist's account through a team seat it is the artist's chip: it said
    the member's own name, email and plan (team review, 2026-09-19)."""
    try:
        user_id = session.get("user_id")
    except RuntimeError:
        return account
    if not user_id:
        return account
    user = _team_owner() or store.get_user(user_id)
    if not user:
        return account
    initials = "".join(p[0] for p in user["name"].split()[:2]).upper() or "?"
    # catalog_config.get_account() is mock data. Overlaying only identity
    # used to let its two invented figures through to the sidebar, which
    # base.html renders on every authenticated page: a hardcoded
    # "Next payout: $2,500 in 6 days" and a hardcoded "Pro Plan". Both
    # read as the user's own. The plan is knowable, so use the real one;
    # the payout is not, so send None and let the template omit the line
    # rather than invent a figure.
    plan_key = (user.get("plan") or "artist") if hasattr(user, "get") else "artist"
    return {**account, "name": user["name"], "initials": initials,
            "email": user["email"], "role": "Team access" if _team_owner() else "Artist Account",
            "plan": plans.PLAN_NAMES.get(plan_key, "Artist"),
            "next_payout": None, "next_payout_in": None}


def _epk_account(account, user):
    """The identity a press kit is published under.

    The sidebar chip is the account - a person, with an email and a plan.
    A press kit is the act, and the public slug already headlines the act
    (db.get_epk_by_slug resolves it). The editor and the export used the
    chip's name, so the same artist could see one name while writing the
    kit and a different one on the page a label opens. Both resolve
    through artist_identity now.
    """
    name = (artist_identity.display_name(user)
            or (account or {}).get("name") or "")
    initials = "".join(p[0] for p in name.split()[:2]).upper() or "?"
    return {**(account or {}), "name": name, "initials": initials}


def _session_is_demo():
    """Whether the current request belongs to the showcase account.

    build_dashboard_context() feeds roughly sixty renders and takes no
    user argument, so it reads the session itself - the same trick
    _account_with_user already uses. Safe outside a request context;
    tests call these directly.
    """
    try:
        user_id = session.get("user_id")
    except RuntimeError:
        return False
    if not user_id:
        return False
    user = store.get_user(user_id)
    if not user:
        return False
    # _is_demo_email lives inside create_app(), so it is out of scope
    # here. Same rule, stated once more rather than reached for.
    return demo_accounts.is_demo_email(user["email"])


def _internal_tools():
    """Which internal tools this login can actually open.

    Checked against the real rosters, so the sidebar never offers a link
    that would answer 403. Reads the session itself for the same reason
    _session_is_demo does: build_dashboard_context feeds ~60 renders and
    takes no user argument, and current_user() is a closure inside
    create_app that module level cannot see.
    """
    try:
        user_id = session.get("user_id")
    except RuntimeError:                   # outside a request context (tests)
        return []
    if not user_id or _team_owner():
        return []                          # none of the member's own, inside an artist's account
    user = store.get_user(user_id)
    if not user:
        return []
    email = (user.get("email") or "").strip().lower()
    if not email:
        return []
    owner = _is_owner_email(email)
    out = []
    try:
        import desk_store
        seat = desk_store.get_user_by_email(email)
        if owner or (seat and (seat.get("status") or "active") == "active"):
            out.append({"href": "/operator-desk/", "label": "Operator Desk"})
    except Exception:                      # a missing table must not break every page
        pass
    try:
        import signal_store as _sig
        org = _sig.default_org()
        if owner or _sig.get_member(org["id"], email):
            out.append({"href": "/signal", "label": "Signal"})
    except Exception:
        pass
    # Owner only, and offered even when audio is switched off: a page whose
    # whole job is explaining why a surface is refusing is most useful
    # exactly when it is refusing.
    if owner:
        out.append({"href": "/admin/audio", "label": "Audio Intelligence"})
        # Named for what the page is. It used to sit under Label Services
        # as "Review Queue - submissions awaiting review", which described
        # the inbox rather than this, and put a roster of every customer's
        # email behind a tier anyone could buy.
        out.append({"href": "/admin/review", "label": "Artist accounts"})
        out.append({"href": "/admin/readiness", "label": "Readiness"})
        # The reseller back office (/resellers) was built and linked from
        # nowhere (audit, 2026-09-19). Owner only, like its route.
        out.append({"href": "/resellers", "label": "Resellers"})
        # RoEx credits, jobs, and cost against revenue for Release-Ready.
        out.append({"href": "/admin/release-ready", "label": "Release-Ready desk"})
        # Core, the template builder new suites are made from (owner,
        # 2026-09-17: "add this into the street banker back side owner
        # account, it's a template for making new suites"). Another
        # service, so it opens in a new tab like the suites do.
        core = (os.environ.get("CORE_BUILDER_URL")
                or "https://street-banker-core-builder.onrender.com/").strip()
        out.append({"href": core, "label": "Core builder", "away": True})
    return out


def build_dashboard_context():
    # royalty_data's module-level seed data is the showcase's, not the
    # signed-in artist's. Handing it to a real account produced
    # "Total Royalties Collected $23,217.64" on an empty dashboard and a
    # catalogue of five recordings with ISRCs belonging to nobody.
    demo = _session_is_demo()
    balances = get_platform_balances() if demo else []
    # The seeded payouts and the leak alerts built on them rendered on a
    # fresh account's Overview as five paid rows and an action feed
    # (scout of 2026-09-14). The showcase keeps them; nobody else does.
    payouts = get_recent_payouts() if demo else []
    kpis = get_kpis()
    total = total_royalties(balances) if demo else 0.0
    goal = get_royalty_goal()
    catalog = get_platform_catalog()

    # Same reasoning: _SONGS is five invented recordings. On /identifiers
    # they rendered as the artist's own catalogue, complete with ISRCs.
    songs = [live_song(s) for s in get_songs()] if demo else []
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
    payout_calendar = get_payout_calendar()
    claims = get_claims(catalog)
    alerts = get_royalty_leak_alerts(balances, payouts, kpis, catalog) if demo else []
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
        # Templates that still carry showcase-only sections check this
        # rather than guessing from whichever seeded value they happen to
        # render.
        "is_showcase": demo,
        # Internal tools (Operator Desk, Signal) are roster-gated and were
        # reachable only by typing the URL. They get a footer group in the
        # sidebar, shown only to people who actually hold a seat - offering
        # everyone a link that answers 403 is worse than no link.
        "internal_tools": _internal_tools(),
        "story": get_dashboard_story(total, missing_findings, catalog_value, smart_recommendations),
        "money_left": money_left_on_table(missing_findings),
        "recovery_summary": get_recovery_summary(catalog, songs, earnings_trend),
        "fixes_queue": get_fixes_queue(catalog, songs, missing_findings),
        "top_leaks": get_top_royalty_leaks(missing_findings),
        "documents_vault": documents_vault,
        "releases": get_upcoming_releases(),
        "forecast": get_royalty_forecast(earnings_trend),
        "value_tracker": value_tracker,
        "since_last_login": get_since_last_login_summary(catalog, songs, value_tracker["pct_change"], catalog_value["mid"]),
        "account": _account_with_user(get_account()),
        "overview_health": get_overview_health(catalog, songs),
        "action_center": get_action_center(alerts, payouts),
        "recent_payout_rows": recent_payout_rows() if demo else [],
        "royalties_overview": get_royalties_overview(
            balances, catalog, payout_calendar, earnings_trend, recent_payout_rows()
        ),
        "valuation_overview": get_valuation_overview(
            earnings_trend, catalog_value, advance_eligibility, value_tracker
        ),
        "logo_key": platform_logo_key,
        "conflicts": get_rights_conflicts(songs),
        "alerts": alerts,
        "smart_recommendations": smart_recommendations,
        "total": total,
        "goal": goal,
        "progress": royalty_progress(total, goal),
        "earnings_trend": earnings_trend,
        "payouts": payouts,
        "songs_summary": songs_summary,
        "payout_calendar": payout_calendar,
        "upcoming_payout_total": round(upcoming_payout_total(payout_calendar), 2),
        "claims": claims,
        "catalog_value": catalog_value,
        "advance_eligibility": advance_eligibility,
    }


class StaticCacheHeaders:
    """Let the edge and the browser keep /static/ instead of re-fetching it.

    Flask touches the session on nearly every request, so it stamps
    "Vary: Cookie" on the response, and no shared cache will store anything
    carrying that header. Together with Werkzeug's default
    "Cache-Control: no-cache" it meant Cloudflare answered every asset with
    cf-cache-status: DYNAMIC and the origin re-sent all of it on every
    visit - crawlers included, around the clock. Static files are byte
    identical for every visitor, so neither header belongs on them.

    This is WSGI middleware rather than an after_request hook because
    save_session runs AFTER those hooks and puts "Cookie" back; a hook
    cannot win that race, so this sits outside the app and gets the last
    word.

    Two lifetimes, because only some references are cache-busted. A URL
    carrying a query string is safe to freeze for a year - changing the
    file changes the "?v=" and therefore the URL. The bare references
    (mostly images) get a day: long enough to stop the re-fetching, short
    enough that replacing one is not a year-long mistake.
    """

    YEAR = "public, max-age=31536000, immutable"
    DAY = "public, max-age=86400"

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if not environ.get("PATH_INFO", "").startswith("/static/"):
            return self.app(environ, start_response)
        busted = bool(environ.get("QUERY_STRING"))

        def _start(status, headers, exc_info=None):
            # Only cache what actually succeeded. A 404 or a redirect
            # frozen at the edge for a year is a bug nobody can clear.
            # 304 is included because a revalidation that answers without
            # Cache-Control leaves the browser's copy stale-by-default, so
            # it would come back and ask again on the very next page load.
            if status.startswith("200") or status.startswith("304"):
                headers = [(k, v) for (k, v) in headers
                           if k.lower() not in ("cache-control", "vary")]
                headers.append(("Cache-Control", self.YEAR if busted else self.DAY))
                # Static bytes differ only by how they were compressed.
                headers.append(("Vary", "Accept-Encoding"))
            return start_response(status, headers, exc_info)

        return self.app(environ, _start)


def create_app():
    app = Flask(__name__)
    # Error reporting. Owner 2026-09-19: the SENTRY_DSN he set in Render
    # was read by nothing. observability.init is a no-op without it.
    import observability
    observability.init(app)
    # Session key: override via SECRET_KEY env in production.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "royalty-sweep-demo-session")
    # Session cookie: 31 days when "remember this device" is ticked, and
    # Lax + Secure in production. Without SameSite set explicitly, a
    # browser applies its own default and the cookie can be dropped on a
    # cross-site return - arriving from an email link, say, which is
    # exactly how somebody comes back to a dashboard.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Secure only where the site is actually served over TLS. Render sets
    # RENDER=true; keying off SECRET_KEY instead would silently break
    # local sign-in the moment somebody set a key over http.
    app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("RENDER"))
    # Request-body ceiling. Statements are small CSVs, but TOUR files -
    # riders, tech packs, venue maps, receipt photos - are routinely over
    # 8 MB, and Werkzeug enforces this cap before any handler's own check,
    # so it must be at least tour_os.MAX_UPLOAD (25 MB). Large parts are
    # spooled to disk by the form parser, not held in memory.
    #
    # It must also clear every cap the app ADVERTISES, or the advertised
    # number is one this code prints and never enforces. That is exactly what
    # happened: the Remix Lab offered 250 MB and the Audio Studio 200 MB
    # against a 25 MB ceiling, so a normal WAV master was rejected by Werkzeug
    # before routing and the artist got a bare "Request Entity Too Large" with
    # no sentence telling them what to do. Raise this WITH the advertised caps,
    # never past them. See audio_studio.MAX_UPLOAD_BYTES.
    app.config["MAX_CONTENT_LENGTH"] = 210 * 1024 * 1024

    @app.errorhandler(413)
    def _too_large(_error):
        """Werkzeug aborts oversize requests before any route runs, so this is
        the only place that can explain one. Without it the artist sees the
        server's bare error page and has no idea what the limit is."""
        limit = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        message = ("That file is over the %d MB limit. Bounce a smaller file - "
                   "a 320 kbps MP3 of a full-length master is usually well "
                   "under 20 MB - and upload that instead." % limit)
        wants_json = (request.path.endswith(".json")
                      or request.accept_mimetypes.best == "application/json"
                      or request.headers.get("X-Requested-With") == "XMLHttpRequest")
        if wants_json:
            return jsonify({"ok": False, "error": message, "max_mb": limit}), 413
        return render_template("too_large.html", message=message,
                               limit_mb=limit), 413
    # Trig helpers for the homepage's analog VU-meter / knob SVGs.
    app.jinja_env.globals.update(cos=math.cos, sin=math.sin, pi=math.pi)
    # The public header reads its links from landing_config. A callable
    # rather than a context processor, so an authenticated page that never
    # renders the header never pays to build the landing config - and so
    # the partial cannot collide with Flask's own `config` in templates
    # that do not pass the landing one.
    app.jinja_env.globals["public_nav"] = lambda: get_landing_config()["nav"]
    # Capability status, resolved against the running deployment. One
    # source of truth for every public surface - see capability_status.py.
    app.jinja_env.globals["cap"] = capability_status.resolve
    # The identity of a statement finding, for the two bands that offer a
    # case straight from one. Computed here rather than spelled out in the
    # template, so the Recovery page and the Real Numbers band cannot
    # drift into keying the same gap two different ways.
    app.jinja_env.globals["case_key"] = recovery_engine.finding_key
    # Stored paths come in two shapes - "/uploads/..." on disk and
    # "r2:<key>" in the bucket. Templates print media_url(path) and do
    # not care which; the bucket stays private and the URL expires.
    app.jinja_env.globals["media_url"] = blob_store.url_for
    app.jinja_env.filters["media_url"] = blob_store.url_for

    def _js_json(value):
        """JSON for embedding inside an inline <script>.

        json.dumps does not escape "<", so a user-supplied string containing
        "</script>" would close the tag and everything after it would be
        parsed as HTML - stored XSS on any page that echoes a name the user
        typed. These four escapes are ordinary JSON string escapes, so the
        parsed value is byte-for-byte identical; U+2028/U+2029 are escaped
        too because they are literal line terminators in JavaScript.
        Accepts an object or an already-serialised JSON string. A string
        that is NOT valid JSON is serialised rather than trusted: passing
        one through raw would drop bare text into a <script>, which is the
        exact injection this filter exists to stop. (Found the hard way —
        a bare hex token landed as `x = 691ae30b…;` and took the whole
        inline script down with a syntax error. A name would have been
        worse than a syntax error.)
        """
        if isinstance(value, str):
            try:
                json.loads(value)
                text = value
            except ValueError:
                text = json.dumps(value)
        else:
            text = json.dumps(value)
        return Markup(text.replace("<", "\\u003c").replace(">", "\\u003e")
                          .replace("&", "\\u0026")
                          .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))

    app.jinja_env.filters["js_json"] = _js_json

    store.init_db()
    # Seed one demo account per tier so partners can tour exactly what each
    # plan buys. All share the demo password; DEMO_PASSWORD rotates them all.
    _DEMO_ACCOUNTS = demo_accounts.ACCOUNTS
    for _email, _name, _plan in _DEMO_ACCOUNTS:
        if store.get_user_by_email(_email) is None:
            store.create_user(_email, _name, generate_password_hash("sweep"))
        _acct = store.get_user_by_email(_email)
        if (_acct.get("plan") or "artist") != _plan:
            store.set_user_plan(_acct["id"], _plan)
        if os.environ.get("DEMO_PASSWORD"):
            with store.get_db() as _db:
                _db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                            (generate_password_hash(os.environ["DEMO_PASSWORD"]),
                             _acct["id"]))
        # Real statements for the non-fan demos, so the showcase runs on
        # the same engines an artist's account does. Idempotent, and it
        # never touches an account that already has rows.
        if _plan != "fan":
            demo_seed.seed_statements(_acct["id"])

    # Owner accounts get the top plan at boot as well as at login, so an
    # existing long-lived session does not have to sign out and back in
    # for it to take effect.
    for _u in store.list_users():
        _grant_owner_plan(_u)

    def current_user():
        """The account this request is acting AS.

        Normally the signed-in person. When a partner seat is acting on behalf
        of an artist it owns, this returns the ARTIST, so every page, query and
        permission check downstream sees the workspace it is meant to.

        The staff member's own id stays in session["user_id"] and is never
        overwritten - that is what the audit trail records, and an
        impersonation that loses the impersonator is not an audit trail.

        Ownership is re-checked on EVERY request rather than trusted from when
        the session started. Detaching an artist, suspending the partner or
        removing the seat has to end this immediately, not at next login.
        """
        user_id = session.get("user_id")
        if not user_id:
            return None

        acting_as = session.get("acting_as")
        if acting_as:
            actor = partner_os.acting_context(user_id, acting_as)
            if actor is None:
                # No longer permitted. Drop it rather than silently falling
                # back to the staff account mid-journey.
                session.pop("acting_as", None)
                session.pop("acting_as_name", None)
            else:
                return actor

        # A team member working inside the artist's account (owner,
        # 2026-09-19): re-checked on every request, like acting_as, so a
        # removal, a lock or a downgrade ends it on the next click.
        team_as = session.get("team_as")
        if team_as:
            seat = _team_seat(user_id, team_as)
            if seat is None:
                session.pop("team_as", None)
                session.pop("team_as_name", None)
            else:
                return seat["owner"]

        me = store.get_user(user_id)
        if me and store.account_shut(me) and not _is_owner_email(me.get("email")):
            # Locked by the owner, or a guest pass that ran out. Shut off,
            # not deleted: the session ends here and sign-in says why.
            session.clear()
            return None
        return me

    def _team_seat(member_id, owner_id):
        """What this team member may do inside this account right now, or
        None. Read once per request. Edit needs the account to be on Pro or
        Label today, so a downgrade turns an editor into a reader at once.
        The platform owner's account and the shared demo logins are never
        opened this way."""
        key = (member_id, owner_id)
        cached = getattr(g, "_team_seat", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        seat = None
        m = store.get_portal_membership(member_id, owner_id)
        owner = store.get_user(owner_id) if m else None
        me = store.get_user(member_id) if m else None
        if (m and owner and me and not store.account_shut(owner) and not store.account_shut(me)
                and not _is_owner_email(owner.get("email"))
                and not demo_accounts.is_demo_email(owner.get("email") or "")
                # A seat the artist has not confirmed opens nothing (team
                # review, 2026-09-19), nor one beyond the plan's count.
                and m.get("access") in ("read", "edit")):
            plan = owner.get("plan") or "artist"
            limit = plans.team_seats(plan)
            pos = store.team_seat_position(owner_id, member_id)
            if limit is None or (pos is not None and pos < limit):
                edit = m.get("access") == "edit" and plans.team_can_edit(plan)
                seat = {"owner": owner, "member_id": member_id,
                        "member_name": me.get("name") or me.get("email") or "",
                        "member_email": me.get("email") or "",
                        "role": m.get("role") or "", "access": "edit" if edit else "read",
                        "can_roster": bool(edit and m.get("can_roster") and plans.team_can_roster(plan)),
                        "areas": m.get("areas") if m.get("areas") is not None else team_areas.ALL,
                        "rooms": team_areas.describe(m.get("areas"))}
        g._team_seat = (key, seat)
        return seat

    def current_team_seat():
        """The team seat this request works through, or None. The artist's
        own session, a tour crew member and a partner acting for an artist
        have none. Resolved the same way current_user() resolves it, so a
        seat that has gone is None here too."""
        if not session.get("team_as"):
            return None
        current_user()                      # resolves the seat, or ends it
        if not session.get("team_as"):
            return None
        return (getattr(g, "_team_seat", None) or (None, None))[1]

    def current_acting():
        """The partner staff member working this request in an artist's
        account through act-on-behalf, or None. Tour uses it to file a
        change under the person who made it rather than the artist, so
        the artist still hears about it (review, 2026-09-19). Resolved the
        way current_user() resolves it, so an act-on-behalf that has ended
        is None here too."""
        if not session.get("acting_as"):
            return None
        artist = current_user()             # re-checks the permission, or ends it
        if artist is None or not session.get("acting_as"):
            return None
        staff = store.get_user(session.get("user_id")) or {}
        return {"id": session.get("user_id"),
                "name": staff.get("name") or staff.get("email") or "A partner",
                "for": artist.get("name") or artist.get("email") or "the artist"}

    @app.route("/suites/go/<key>")
    def suite_go(key):
        """Hand a signed-in artist across to one of the tool suites.

        Street Banker is the account of record. The suite receives a
        short-lived signed token naming this account (sb_suite_sso) and
        starts its own session from it, so nobody signs in twice. With no
        shared secret configured the link is a plain visit, which is what
        it was before.
        """
        if key not in suite_sso.SUITES:
            abort(404)
        user = current_user()
        if not user:
            return redirect(url_for("login", next=request.path))
        is_owner = _is_owner_email(user.get("email"))
        names = {"the-room": "The Room", "noise-lab": "Noise Lab", "reach": "REACH",
                 "tour": "Tour", "motion": "Motion"}
        # A suite marked Soon is still being finished: only the owner goes in.
        if key in hub_defs.suites_pending() and not is_owner:
            return render_template("suite_soon.html", suite_name=names.get(key, key),
                                   **build_dashboard_context())
        # Motion keeps one workspace per deployment until each account gets
        # its own, so the shared demo logins would see other people's
        # projects there. Kept out until then (2026-09-18 launch check).
        if key == "motion" and _is_demo_email(user.get("email") or ""):
            return render_template("suite_soon.html", suite_name="Motion", demo=True,
                                   **build_dashboard_context())
        # The membership decides which suites open (owner, 2026-09-17). The
        # creation suites spend credits: Label carries them, anybody else
        # gets in by holding some.
        wallet = _wallet(user)
        plan = user.get("plan") or "artist"
        # The owner's own account opens every door whatever plan it sits on.
        if not is_owner and not plans.suite_open(plan, key, wallet["total"]):
            need = plans.suite_access(key)
            return render_template("upgrade.html", required="label" if need == "credits" else need,
                                   needs_credits=(need == "credits"),
                                   suite_name=names.get(key, key),
                                   plans_list=plans.PLANS, **build_dashboard_context()), 402
        if not suite_sso.configured():
            return redirect(suite_sso.suite_base(key) + suite_sso.suite_home(key))
        return redirect(suite_sso.handoff_url(user, key))

    def _wallet(user):
        """The account's credit wallet, with this month's Label credits put in
        first if they have not been. The month is the ref, so however many
        doors ask, a month is granted once."""
        if (user.get("plan") or "") == "label":
            today = datetime.now(timezone.utc)
            nxt = (today.replace(day=1) + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            store.add_credits(user["id"], plans.LABEL_MONTHLY_CREDITS, "monthly", bucket="monthly",
                              note="Included with Label for %s" % today.strftime("%B %Y"),
                              ref="monthly:%s:%s" % (user["id"], today.strftime("%Y-%m")),
                              expires=nxt.isoformat(timespec="seconds"))
        return store.credit_balances(user["id"])

    @app.route("/api/suites/credits", methods=["POST"])
    def suite_credits_call():
        """A suite asks what an artist holds, or spends some of it. Server to
        server: the body is a token signed with the suites' shared secret.
        {"op": "balance"|"spend", "email", "suite", "amount", "ref"}."""
        body = request.get_json(silent=True) or {}
        call = suite_sso.verify_credit_call(body.get("token") or request.form.get("token"))
        if call is None:
            return jsonify({"ok": False, "error": "unsigned"}), 401
        who = store.get_user_by_email((call.get("email") or "").strip().lower())
        suite = call.get("suite") or ""
        if who is not None and store.account_shut(who):
            return jsonify({"ok": False, "error": "account shut off"}), 403
        if who is None or plans.suite_access(suite) != "credits":
            return jsonify({"ok": False, "error": "unknown account or suite"}), 404
        if call.get("op") == "spend":
            try:
                amount = int(call.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0
            if amount <= 0 or not call.get("ref"):
                return jsonify({"ok": False, "error": "a spend needs an amount and a ref"}), 400
            _wallet(who)
            after = store.spend_credits(who["id"], amount, suite, note=(call.get("note") or "")[:200],
                                        ref="spend:%s:%s" % (suite, call["ref"]))
            if after is None:
                return jsonify({"ok": False, "error": "not enough credits",
                                "balance": store.credit_balances(who["id"])}), 402
            return jsonify({"ok": True, "balance": after})
        return jsonify({"ok": True, "balance": _wallet(who)})

    def login_required_redirect():
        return redirect(url_for("login", next=request.path))

    def _signup_open():
        """May a stranger register? Owner, 2026-09-17: "make sure no one can
        make an account unless i give them one". On Render, which is every
        deployed service, the door is shut unless SIGNUP_MODE=open is set
        there on purpose. Off Render (the tests, a laptop) it stays open."""
        mode = (os.environ.get("SIGNUP_MODE") or "").strip().lower()
        if mode in ("open", "invite"):
            return mode == "open"
        return not os.environ.get("RENDER")

    _INVITE_ONLY = ("Street Banker is invitation only right now. "
                    "Ask Street Banker for an invitation, then open the link it sends you.")
    # While sign-up is shut, a roster or team link joins an account that
    # already exists and makes none (owner, 2026-09-19: "yes shut those
    # also", on the 2026-09-18 exception that let those links mint
    # accounts). The owner's own invitation from Settings is the only door.
    _MEMBER_LINK_SHUT = ("Street Banker is invitation only right now, so this link can only add "
                         "someone who already has an account. Ask Street Banker for an "
                         "invitation, then open this link again to join.")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        error = None
        # An invitation is a link the owner made in Settings: one address,
        # one plan, one use. With the door shut it is the only way in.
        invite = store.get_signup_invite(request.values.get("invite") or "")
        if request.method == "GET" and invite is None and current_user() is not None:
            # Somebody already signed in has no account to make here.
            return redirect(_signed_in_home(current_user()))
        # Kept before the shut door below: an invitation that follows
        # still credits the referrer (walk, 2026-09-20).
        if request.method == "GET" and request.args.get("ref"):
            session["ref_code"] = request.args.get("ref")[:16]
        if invite is None and not _signup_open():
            # The page stays, form and all (owner, 2026-09-17: "I don't want
            # the sign up page to go away. I just want it to not be able to
            # sign anybody up"). Submitting it creates nothing and says why.
            preselect = "fan" if request.args.get("as") == "fan" else "artist"
            if request.method == "POST":
                return render_template("signup.html", error=_INVITE_ONLY, preselect=preselect,
                                       closed=True, invite=None), 403
            return render_template("signup.html", error=None, preselect=preselect,
                                   closed=True, invite=None)
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            if invite is not None:
                email = invite["email"]        # the invitation names the address; the form cannot change it
            password = request.form.get("password") or ""
            if not name or "@" not in email or len(password) < 6:
                error = "Please provide a name, a valid email, and a password of 6+ characters."
            else:
                user_id = store.create_user(email, name, generate_password_hash(password))
                if user_id is None:
                    error = "An account with that email already exists."
                else:
                    if invite is not None:
                        store.set_user_plan(user_id, invite["plan"])
                        store.use_signup_invite(invite["token"], user_id)
                        if invite.get("guest_hours"):
                            # The clock starts now, when the guest arrives,
                            # not when the owner sent the link.
                            store.set_access_ends(user_id, (datetime.now(timezone.utc) + timedelta(
                                hours=int(invite["guest_hours"]))).isoformat(timespec="seconds"))
                    _grant_owner_plan(store.get_user(user_id))
                    ref = session.pop("ref_code", None) or request.form.get("ref")
                    referrer = store.user_by_ref_code(ref) if ref else None
                    if referrer and store.get_kv(_ref_spent_key(email)):
                        referrer = None     # deleted and came back: once per address
                    if referrer and referrer["id"] != user_id:
                        store.set_referred_by(user_id, referrer["id"])
                        store.notify(referrer["id"], "network", "Referral signed up",
                                     "%s joined from your link. Your 50%% credit "
                                     "applies once they have paid for their plan." % email,
                                     "/referrals")
                    if request.form.get("account_type") == "fan" and invite is None:
                        store.set_user_plan(user_id, "fan")
                        session.permanent = True
                        session["user_id"] = user_id
                        return redirect("/discover")
                    # Somebody who just created an account should not be
                    # signed out by closing the window.
                    session.permanent = True
                    session["user_id"] = user_id
                    # The Command Center start-here panel reads what the
                    # account has. /onboarding saved nothing and promised a
                    # distributor import that does not exist (walk, 2026-09-20).
                    return redirect("/command-center")
        # /signup?as=fan preselects the fan side. The login page offers a
        # fan account as a distinct choice, and it landed on a form with
        # Artist already ticked - a link that names a destination has to
        # arrive there.
        preselect = "fan" if request.args.get("as") == "fan" else "artist"
        return render_template("signup.html", error=error, preselect=preselect,
                               closed=False, invite=invite)

    @app.route("/demo-open", methods=["POST"])
    def demo_open():
        """Open a demo workspace with the shared demo password.

        Split out of /login so the login page carries exactly one form
        that posts a credential pair. It shared the /login action and the
        email/password field names, which is what stopped browsers
        offering to save a real sign-in on this page - and sometimes had
        them save the demo address instead of the artist's own.
        """
        email = (request.form.get("demo_workspace") or "").strip().lower()
        password = request.form.get("demo_password") or ""
        if not demo_accounts.is_demo_email(email):
            return redirect("/login")
        user = store.get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session.permanent = True
            session["user_id"] = user["id"]
            session.pop("seen_rolled", None)
            if (user.get("plan") or "artist") == "fan":
                return redirect("/discover")
            return redirect("/walkthrough")
        return redirect("/login?demo=wrong")

    def _signed_in_home(user):
        """Where an account that is already signed in belongs when it
        opens a door page (/login, /signup, /forgot): the same place a
        fresh sign-in lands (walk, 2026-09-20: it was handed the form)."""
        if (user.get("plan") or "artist") == "fan":
            return "/discover"
        if _is_demo_email(user.get("email")):
            return "/walkthrough"
        return "/command-center"

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "GET" and current_user() is not None:
            return redirect(_safe_next(request.args.get("next"), _signed_in_home(current_user())))
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            user = store.get_user_by_email(email)
            shut = store.account_shut(user) if user and check_password_hash(user["password_hash"], password) else ""
            if shut and not _is_owner_email(user.get("email")):
                error = ("Your guest access has ended. Contact Street Banker to continue."
                         if shut == "ended" else
                         "This account is locked. Contact Street Banker to continue.")
                user = None
            if user and check_password_hash(user["password_hash"], password):
                session["user_id"] = user["id"]
                # A fresh sign-in is a fresh visit: let the Overview
                # strip roll its window again on the next dashboard view.
                session.pop("seen_rolled", None)
                # The owner does not pay to use their own product. This
                # grants the top plan, nothing more - the password check
                # above still had to pass, and every other protection is
                # untouched.
                _grant_owner_plan(user)
                # "Remember this device": a real 31-day session, only when
                # asked for. Unchecked keeps the browser-session cookie.
                # Explicit either way. Absent used to mean "browser session",
                # which is a reasonable choice on a shared machine and a
                # surprising default everywhere else.
                session.permanent = bool(request.form.get("remember"))
                is_demo = (email == "demo@streetbanker.io"
                           or email.startswith("demo-") and email.endswith("@streetbanker.io"))
                if is_demo:
                    # The shared demo logins keep the Rack and the audio pages
                    # open (owner, 2026-09-17: "let them use the rack"): a
                    # standing balance, granted once per account by its ref.
                    store.add_credits(user["id"], 100000, "grant", note="Standing demo balance",
                                      ref="demo-standing:%s" % user["id"])
                if (user.get("plan") or "artist") == "fan":
                    default = "/discover"
                elif is_demo:
                    # The demo IS the walkthrough — land partners on the tour.
                    default = "/walkthrough"
                else:
                    default = "/command-center"
                # Same-site paths only: ?next=https://elsewhere used to send
                # a fresh sign-in straight off the site.
                return redirect(_safe_next(request.args.get("next"), default))
            error = error or "Incorrect email or password."
        return render_template(
            "login.html", error=error,
            # Tour-rack state: was demo access just requested, and is this
            # browser already a known lead (cookie set by /demo-access)?
            demo_state=request.args.get("demo"),
            demo_lead=request.cookies.get("sb_demo_lead"))

    # One lead per IP per half-minute is plenty; this only guards the
    # public capture form against dumb floods, not determined abuse.
    _demo_access_seen = {}

    @app.route("/demo-access", methods=["POST"])
    def demo_access():
        """Demo password is earned, not shown: leave an email, the lead is
        stored in the owner's inbox, and if the mailer is live the password
        goes out automatically. A cookie marks the browser as a known lead
        so the tour rack switches to its password state."""
        # Honeypot: real visitors never see this field.
        if request.form.get("company"):
            return redirect("/login#tour-rack")
        email = (request.form.get("email") or "").strip().lower()
        workspace = (request.form.get("workspace") or "artist").strip().lower()
        if workspace not in ("artist", "pro", "label", "fan"):
            workspace = "artist"
        if not email or "@" not in email or len(email) > 254:
            return redirect("/login?demo=error#tour-rack")
        ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "?")
              .split(",")[0].strip())
        now = time.time()
        if now - _demo_access_seen.get(ip, 0) < 30:
            resp = redirect("/login?demo=pending#tour-rack")
            resp.set_cookie("sb_demo_lead", email, max_age=90 * 24 * 3600,
                            httponly=True, samesite="Lax")
            return resp
        _demo_access_seen[ip] = now

        sent = False
        if emailer.configured():
            try:
                pw = os.environ.get("DEMO_PASSWORD", "sweep")
                emailer.send(
                    email,
                    "Your Street Banker demo access",
                    "<p>Thanks for your interest in Street Banker.</p>"
                    "<p>Your demo password: <strong>%s</strong></p>"
                    "<p>Sign in at <a href='%s/login'>%s/login</a>, pick the "
                    "<strong>%s</strong> workspace in Tour Street Banker, and "
                    "enter the password.</p>"
                    "<p>The demo is illustrative sample data - no account is "
                    "created and nothing is shared.</p>"
                    % (pw, PUBLIC_BASE_URL,
                       PUBLIC_BASE_URL.split("//", 1)[-1], workspace.title()))
                sent = True
            except Exception:
                sent = False
        store.add_inbox("demo-access", {
            "email": email, "workspace": workspace, "password_sent": sent,
            "requested": datetime.now().isoformat(timespec="seconds")})
        resp = redirect("/login?demo=%s#tour-rack" % ("sent" if sent else "pending"))
        resp.set_cookie("sb_demo_lead", email, max_age=90 * 24 * 3600,
                        httponly=True, samesite="Lax")
        return resp

    def _clean_signal_profile(raw):
        """Server-side validation of an Artist Signal Profile.

        Only known priority keys, clamped 0-10; only known module names;
        strings length-capped. Returns the canonical dict or None - raw
        client JSON is never stored or echoed."""
        from artist_eq_config import get_artist_eq_config

        if not isinstance(raw, dict):
            return None
        cfg = get_artist_eq_config()
        keys = [c["key"] for c in cfg["channels"]]
        labels = {c["key"]: c["label"] for c in cfg["channels"]}
        prio_in = raw.get("priorities")
        if not isinstance(prio_in, dict):
            return None
        priorities = {}
        for k in keys:
            try:
                v = int(round(float(prio_in.get(k))))
            except (TypeError, ValueError):
                return None
            priorities[k] = max(0, min(10, v))

        def _s(value, cap):
            return str(value)[:cap] if isinstance(value, str) else ""

        known_lanes = [l["name"] for l in cfg["lanes"]]
        lane = _s(raw.get("recommendedLane"), 64)
        if lane not in known_lanes:
            lane = ""
        known_modules = {name for options in cfg["modules"].values()
                         for name, _slug in options}
        modules = [m for m in (raw.get("recommendedModules") or [])
                   if isinstance(m, str) and m in known_modules][:4]
        actions = [_s(a, 120) for a in (raw.get("firstActions") or [])
                   if isinstance(a, str)][:3]
        top = sorted(keys, key=lambda k: -priorities[k])[:3]
        return {
            "version": 1,
            "createdAt": _s(raw.get("createdAt"), 40),
            "updatedAt": _s(raw.get("updatedAt"), 40),
            "preset": _s(raw.get("preset"), 32) or "Custom Mix",
            "priorities": priorities,
            "topPriorities": [labels[k] for k in top],
            "recommendedLane": lane,
            "recommendedModules": modules,
            "firstActions": actions,
            "source": "homepage_artist_eq",
        }

    @app.route("/api/artist-signal-profile", methods=["GET", "POST"])
    def artist_signal_profile_api():
        """The saved EQ mix, associated with the signed-in account so the
        Command Center and Artist Twin can read it server-side."""
        user = current_user()
        if user is None:
            return jsonify({"error": "auth required"}), 401
        if request.method != "POST":
            return jsonify({"profile": store.get_artist_signal_profile(user["id"])})
        clean = _clean_signal_profile(request.get_json(silent=True))
        if clean is None:
            return jsonify({"error": "invalid profile"}), 400
        store.set_artist_signal_profile(user["id"], clean)
        return jsonify({"ok": True})

    @app.route("/webhooks/resend", methods=["POST"])
    def resend_webhook():
        """Statement drop-box: Resend inbound email -> parsed statements.
        Env-gated; every request is signature-verified."""
        if not emailer.inbound_configured():
            abort(404)
        body = request.get_data()
        if not emailer.verify_webhook(request.headers, body):
            return jsonify({"ok": False, "error": "bad signature"}), 401
        event = request.get_json(silent=True) or {}
        if event.get("type") != "email.received":
            return jsonify({"ok": True, "ignored": True})
        data = event.get("data") or {}
        # The recipient's local part is the account's ingest token.
        user_id = None
        for rcpt in (data.get("to") or []):
            token = str(rcpt).split("@")[0].lower().strip()
            user_id = store.user_by_ingest_token(token)
            if user_id:
                break
        if user_id is None:
            return jsonify({"ok": True, "ignored": True})
        ingested, errors = 0, []
        try:
            attachments = emailer.list_received_attachments(data.get("email_id")
                                                            or data.get("id") or "")
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502
        for att in attachments:
            name = att.get("filename") or "statement.csv"
            if not (name.lower().endswith(".csv")
                    or "csv" in (att.get("content_type") or "")):
                continue
            try:
                content = emailer.download_attachment(att.get("download_url") or "")
            except Exception:
                errors.append(name)
                continue
            err = _ingest_statement(user_id, name, content, via="email")
            if err:
                errors.append("%s: %s" % (name, err))
            else:
                ingested += 1
        if errors and not ingested:
            store.notify(user_id, "statement", "Emailed statement failed to parse",
                         "; ".join(errors)[:300], "/statements")
        return jsonify({"ok": True, "ingested": ingested, "errors": errors})

    @app.route("/webhooks/hypeddit/<token>", methods=["GET", "POST"])
    def hypeddit_webhook(token):
        """Hypeddit's automation webhook, one address per account.

        The token in the URL is the authorisation (it is the artist's
        secret, minted on the Fan CRM page, rotated there too). An
        unknown one is 404. A known one is always answered 200 quickly,
        whatever was in the body, so Hypeddit never retries a delivery
        into a duplicate; what the body held is logged for the artist.
        GET answers without filing anything, because some automation
        tools ping an address before they trust it. Field names are not
        documented by Hypeddit, so hypeddit_ingest reads JSON, a form
        body or query fields and finds the address wherever it sits.
        """
        user_id = hypeddit_ingest.user_for_token(token)
        if user_id is None:
            return jsonify({"ok": False, "error": "unknown address"}), 404
        if request.method == "GET":
            return jsonify({"ok": True, "listening": True})
        payload = request.get_json(silent=True)
        if not isinstance(payload, (dict, list)):
            if request.form:
                payload = request.form.to_dict(flat=True)
            else:
                payload = request.args.to_dict(flat=True)
        try:
            hypeddit_ingest.receive(user_id, payload)
        except Exception as exc:                      # noqa: BLE001
            app.logger.exception("hypeddit delivery for %s failed: %s", user_id, exc)
        return jsonify({"ok": True})

    def _reset_serializer():
        from itsdangerous import URLSafeTimedSerializer
        return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="pw-reset")

    def _reset_stamp(user):
        """A fingerprint of the password the reset link is meant to
        replace. Setting a new one changes it, so a link that has been
        used, or one sent before the password was changed in Settings,
        stops opening (walk, 2026-09-20: a used link stayed live for
        the rest of its hour, so whoever read the mailbox next could
        take the account again)."""
        import hashlib
        return hashlib.sha256((user.get("password_hash") or "").encode("utf-8")).hexdigest()[:16]

    @app.route("/forgot", methods=["GET", "POST"])
    def forgot_password():
        sent, error = False, None
        if request.method == "GET" and current_user() is not None:
            return redirect(_signed_in_home(current_user()))
        if request.method == "POST":
            if not emailer.configured():
                error = ("Password reset email isn't enabled on this server yet. "
                         "Contact the site owner to reset your password.")
            else:
                email = (request.form.get("email") or "").strip().lower()
                user = store.get_user_by_email(email) if "@" in email else None
                if user:
                    token = _reset_serializer().dumps([user["id"], _reset_stamp(user)])
                    # Pinned, not request-derived. This is the one link
                    # where trusting the Host header would hand a valid
                    # reset token to whoever set it.
                    link = public_url("/reset/" + token)
                    emailer.send(
                        email, "Reset your Street Banker password",
                        '<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">'
                        "<h2>Reset your password</h2>"
                        "<p>Someone (hopefully you) asked to reset the password for this "
                        "Street Banker account. The link works for 1 hour.</p>"
                        '<p><a href="%s" style="display:inline-block;background:#E8B950;'
                        'color:#14100A;font-weight:bold;padding:12px 24px;border-radius:10px;'
                        'text-decoration:none;">Choose a new password</a></p>'
                        "<p style=\"color:#91836A;font-size:12px;\">If you didn't ask for this, "
                        "ignore this email — your password is unchanged.</p></div>" % link)
                # Same response either way: never confirm whether an email exists.
                sent = True
        return render_template("forgot.html", sent=sent, error=error)

    @app.route("/reset/<token>", methods=["GET", "POST"])
    def reset_password(token):
        from itsdangerous import BadSignature, SignatureExpired
        try:
            payload = _reset_serializer().loads(token, max_age=3600)
        except (BadSignature, SignatureExpired):
            return render_template("reset.html", invalid=True, error=None)
        # [user id, password stamp]; a link from before the stamp existed
        # carried the id alone and is refused with the rest.
        user = store.get_user(payload[0]) if isinstance(payload, list) and len(payload) == 2 else None
        if user is None or payload[1] != _reset_stamp(user):
            return render_template("reset.html", invalid=True, error=None)
        user_id = user["id"]
        error = None
        if request.method == "POST":
            password = request.form.get("password") or ""
            if len(password) < 6:
                error = "Use a password of 6+ characters."
            else:
                store.set_user_password(user_id, generate_password_hash(password))
                session["user_id"] = user_id
                return redirect("/command-center" if (user.get("plan") or "artist") != "fan"
                                else "/discover")
        return render_template("reset.html", invalid=False, error=error)

    @app.route("/terms")
    def terms():
        return render_template("legal.html", title="Terms of Service",
                               updated="July 9, 2026", sections=[
            ("The service", "Street Banker provides software tools for independent artists: royalty statement analysis, smart links, press kits, fan capture, and related workflows. We provide software, not professional services — nothing in the app is legal, financial, or tax advice."),
            ("Your account", "You're responsible for your account credentials and for the accuracy of the data you upload. You must be 13 or older (16 in the EU) to create an account."),
            ("Your content", "You keep all rights to the music, artwork, statements, and other material you upload. You grant us only the license needed to store, process, and display it back to you and to the people you share it with (public press kits, smart links, sync packs)."),
            ("Fan data", "Fan emails and pre-save data captured through your campaigns belong to your account. You agree to use them lawfully — including honoring the consent language shown at capture and applicable anti-spam law."),
            ("Acceptable use", "No unlawful content, no infringing uploads, no abusing the platform to send spam, and no attempts to breach or overload the service."),
            ("Paid plans", "Paid tiers unlock additional features. Fees, billing cadence, and cancellation terms are shown at checkout. You can cancel anytime; access continues through the paid period."),
            ("Estimates and simulations", "Catalog valuations, recovery estimates, deal simulations, and scores are informational estimates computed from your data. They are not offers, appraisals, or professional advice."),
            ("Termination", "You can delete your account at any time. We may suspend accounts that violate these terms."),
            ("Warranty & liability", "The service is provided as-is. To the maximum extent permitted by law, our liability is limited to the amount you paid us in the 12 months before a claim."),
            ("Changes", "We'll post updates to these terms here and note the date above. Continued use after changes means acceptance."),
        ])

    @app.route("/privacy")
    def privacy():
        return render_template("legal.html", title="Privacy Policy",
                               updated="July 9, 2026", sections=[
            ("What we collect", "Account data (name, email, hashed password), the content you upload (statements, artwork, documents), campaign analytics (link clicks, referrers), and — when you connect them — data from services you authorize, like Spotify artist stats."),
            # The pre-save sentence is resolved against the running
            # deployment rather than asserted. With Spotify credentials
            # unset the flow falls back to notify-me and no token is ever
            # requested - claiming we encrypt one would be false.
            ("Fan data you capture", "When a fan subscribes on your campaign pages, we store their email with a consent record, on your behalf. Artists control this data; we process it. " + (
                "Where a fan pre-saves, they authorize Spotify directly; that token is encrypted at rest and deleted once the release-day save completes."
                if capability_status.is_live("spotify_presave")
                else "Spotify pre-save is not connected on this deployment: pre-save buttons collect a notify-me address instead, and no Spotify token is requested, stored or processed.")),
            ("What we don't do", "We don't sell personal data. We don't use your uploads to train AI models. We don't read fan tokens for anything beyond the save and the consented email."),
            ("Service providers", "We use Render (hosting), Resend (email delivery), and public music APIs (Spotify, Deezer, iTunes, Odesli, MusicBrainz, Bandsintown) to provide features you invoke. Each receives only what's needed for that feature."),
            ("Cookies", "We use a single session cookie to keep you signed in. No advertising trackers."),
            ("Retention & deletion", "Your data stays while your account is active. Ask us to delete your account and we remove your data within 30 days, except records we must keep by law."),
            ("Your rights", "Depending on where you live (GDPR, CCPA), you can request access, correction, export, or deletion of your personal data — email us and we'll handle it."),
            ("Security", "Passwords are hashed, fan tokens are encrypted, and data lives on access-controlled infrastructure. No system is perfect; we'll notify affected users of any breach as required by law."),
            ("Contact", "Privacy questions and requests: team.summitarts@gmail.com."),
        ])

    @app.route("/logout", methods=["POST"])
    def logout():
        session.pop("user_id", None)
        session.pop("signed_in", None)
        session.pop("team_as", None)
        session.pop("team_as_name", None)
        return redirect(url_for("login"))

    # --- Statements: real CSV ingestion + recovery findings -------------------

    def _ingest_statement(user_id, filename, data, via=""):
        """Parse + save + notify. Returns an error string or None."""
        parsed = parse_statement(data, filename)
        if parsed["error"]:
            return parsed["error"]
        store.save_statement(user_id, filename, parsed["rows"],
                             via="email" if via == "email" else "upload")
        finding = analyze_statement(parsed["rows"])
        tag = (" (via email drop-box)" if via == "email" else "")
        if finding and (finding["unmatched_revenue"] or finding["coverage_gaps"]):
            store.notify(user_id, "recovery",
                         "Recovery findings in %s%s" % (filename, tag),
                         "$%.2f unmatched revenue and %d coverage gap(s) detected."
                         % (finding["unmatched_revenue"], len(finding["coverage_gaps"])),
                         "/recovery")
        else:
            store.notify(user_id, "statement",
                         "Statement processed: %s%s" % (filename, tag),
                         "%d rows parsed, no recovery flags." % len(parsed["rows"]),
                         "/statements")
        return None

    @app.route("/statements/dropbox-new", methods=["POST"])
    def dropbox_new_address():
        """A new drop-box address; the old one stops working at once."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if _working_as_someone():
            return redirect("/statements")
        store.rotate_ingest_token(user["id"])
        return redirect("/statements?dropbox=new")

    @app.route("/statements/dropbox-test", methods=["POST"])
    def dropbox_test():
        """Round-trip self-test: email a sample CSV to your own drop-box.
        It comes back through Resend's webhook like any distributor email."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        if _working_as_someone():
            return jsonify({"ok": False, "error": "Only the account holder can use the drop-box."}), 403
        if not emailer.inbound_configured():
            return jsonify({"ok": False, "error": "Drop-box not configured."}), 400
        import base64 as _b64
        addr = emailer.inbound_address(store.get_or_create_ingest_token(user["id"]))
        csv = ("title,source,amount,period,territory\n"
               "Drop-box Test,Street Banker Self-Test,0.01,%s,US\n"
               % date.today().strftime("%Y-%m"))
        sent = emailer.send(addr, "Street Banker drop-box self-test",
                            "<p>Sample statement attached — this email should "
                            "round-trip into your Statements automatically.</p>",
                            attachments=[{"filename": "dropbox-test.csv",
                                          "content": _b64.b64encode(csv.encode()).decode()}])
        return jsonify({"ok": sent, "address": addr,
                        "error": None if sent else "Resend did not accept the email."})

    def _act_scope(rows_all):
        """(roster, act, rows): the acts the statements on file name, the
        act in scope from ?artist=, and the rows narrowed to it. A label's
        export carries the whole roster (2026-09-14); Statements, Recovery
        and Royalties all read one act at a time through this, so the
        three pages agree on what "in scope" means."""
        import royalties_desk
        roster = royalties_desk.roster(rows_all)
        act = (request.args.get("artist") or request.form.get("artist") or "").strip()
        if act and any(a["name"] == act for a in roster):
            return roster, act, [r for r in rows_all if (r.get("artist") or "").strip() == act]
        return roster, "", rows_all

    def _tax_years(rows):
        """The Tax view of Statements: every uploaded row filed under its
        tax year, per payor, with the $600 mark. Was the Tax Center's own
        page; the owner folded it here (2026-09-19: "move tax center with
        statements"). Returns (years newest first, grand total)."""
        years = {}
        for r in rows:
            # Was (period or "")[:4], which reads "JUN-" out of Symphonic's
            # "JUN-26" and files a whole catalogue under "Undated" - with
            # the $600 threshold then evaluated against a bucket that means
            # nothing. statements_engine.period_year knows the shapes
            # distributors actually write.
            year = period_year(r.get("period")) or "Undated"
            y = years.setdefault(year, {"total": 0.0, "sources": {}, "rows": 0})
            y["total"] += r["amount"]
            y["rows"] += 1
            src = r.get("source") or "Unknown"
            y["sources"][src] = y["sources"].get(src, 0.0) + r["amount"]
        year_list = sorted([
            {"year": k, "total": round(v["total"], 2), "rows": v["rows"],
             "sources": sorted(v["sources"].items(), key=lambda s: -s[1]),
             "over_600": v["total"] >= 600}
            for k, v in years.items()], key=lambda y: y["year"], reverse=True)
        return year_list, round(sum(y["total"] for y in year_list), 2)

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
                error = _ingest_statement(user["id"], f.filename, f.read())
                if error is None:
                    return redirect(url_for("statements"))
        ctx = build_dashboard_context()
        ctx["user"] = user
        ctx["error"] = error
        # ?view=tax is the Tax view: the same rows, filed by tax year. A
        # tab is a view, not an anchor (2026-09-12), and the old /tax page
        # redirects here (owner, 2026-09-19).
        ctx["view"] = "tax" if request.args.get("view") == "tax" else "desk"
        if ctx["view"] == "tax":
            ctx["tax_years"], ctx["tax_total"] = _tax_years(
                store.get_statement_rows(user["id"]))
        # The address is a key to the account: anyone who has it can put
        # statements in, so it is shown to the account holder only, never
        # to a team seat or a partner working inside (team review).
        ctx["drop_box"] = (emailer.inbound_address(
            store.get_or_create_ingest_token(user["id"]))
            if emailer.inbound_configured() and not _working_as_someone() else None)
        ctx["uploads"] = store.get_statements(user["id"])
        ctx["roster"], ctx["act"], rows = _act_scope(store.get_statement_rows(user["id"]))
        ctx["analysis"] = analyze_statement(
            [{"title": r["title"], "source": r["source"], "amount": r["amount"], "period": r["period"]}
             for r in rows]
        )
        # The desk: the four readings, the store ladder, the track table
        # and the gap cards with what the stores said when last asked.
        ctx["desk"] = None
        if ctx["analysis"]:
            import statements_desk
            view = recovery_engine.build(user["id"], rows=rows, analysis=ctx["analysis"])
            ctx["desk"] = statements_desk.build(
                ctx["analysis"], rows, ctx["uploads"], view["findings"],
                store.get_gap_checks(user["id"]), store.list_recovery_cases(user["id"]))
        return render_template("statements.html", active_page="statements", **ctx)

    @app.route("/statements/gaps/check", methods=["POST"])
    def statements_gap_check():
        """Ask the stores about one gap and keep the answer.

        Runs on a press, not on a page view: it is a round of network
        calls, and the answer is kept so the page and the letter read the
        same one. A track whose rows carry no ISRC cannot be asked about
        and is sent back saying so, never checked by title.
        """
        import statements_desk
        user = current_user()
        if user is None:
            return login_required_redirect()
        title = (request.form.get("title") or "").strip()
        # The gap is read in the same scope the page showed it in.
        _roster, act, rows = _act_scope(store.get_statement_rows(user["id"]))
        analysis = analyze_statement(rows) if rows else None
        gap = next((g for g in (analysis or {}).get("coverage_gaps", [])
                    if g["title"] == title), None)
        if gap is None:
            abort(404)
        key = statements_desk.slug(title)
        isrc = next((r["isrc"] for r in rows
                     if (r["title"] or "").strip() == title and r["isrc"]), "")
        back = _safe_next(request.form.get("next"), "/statements")
        on_recovery = back.startswith("/recovery")
        scope = ("&artist=" + urllib.parse.quote(act)) if act else ""
        if not isrc:
            return redirect("/recovery?checked=no-isrc%s#findings" % scope if on_recovery
                            else "/statements?checked=no-isrc%s#gap-%s" % (scope, key))
        store.save_gap_check(user["id"], key, isrc,
                             coverage_check.check_gap(isrc, gap["missing_sources"]))
        return redirect("/recovery?checked=%s%s#findings" % (key, scope) if on_recovery
                        else "/statements?checked=%s%s#gap-%s" % (key, scope, key))

    @app.route("/statements/<statement_id>/delete", methods=["POST"])
    def statement_delete(statement_id):
        """Remove an upload and its rows.

        Needed for a reason worth stating: the ISRC column arrived after
        some statements were already uploaded, so those rows carry no
        ISRC and the store check has nothing to look up. Re-uploading is
        the fix, and without a delete that would double every figure on
        the money pages.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_statement(user["id"], statement_id)
        return redirect("/statements?removed=1")

    # --- Spotify pre-save OAuth (env-gated; notify-me fallback otherwise) ------

    def _send_release_emails(campaign):
        """Once per campaign, on the first page view after release: email
        every consented fan the listen link. Env-gated on RESEND_API_KEY."""
        if (not emailer.configured() or links_engine.is_prerelease(campaign)
                or (campaign.get("settings") or {}).get("release_email_sent")):
            return
        # Claim the flag before sending so concurrent page views can't double-send.
        settings = dict(campaign.get("settings") or {})
        settings["release_email_sent"] = True
        mls.update_campaign(campaign["id"], campaign["user_id"],
                            {"settings": settings})
        listen_url = request.url_root.rstrip("/") + "/l/" + campaign["slug"]
        html = emailer.release_email_html(
            campaign["title"], campaign.get("artist_name") or "",
            listen_url, campaign.get("cover_url") or "")
        # Replies go to the artist, never to the sending address.
        owner = store.get_user(campaign["user_id"]) or {}
        sent = sum(1 for f in mls.campaign_fans(campaign["id"])
                   if emailer.send(f["email"], "%s is out now" % campaign["title"], html,
                                   reply_to=owner.get("email") or None))
        if sent:
            store.notify(campaign["user_id"], "fan",
                         "Release emails sent: %s" % campaign["title"],
                         "%d fan%s notified with the listen link." % (sent, "" if sent == 1 else "s"),
                         "/links/%s/analytics" % campaign["id"])

    def _process_due_presaves(campaign):
        """Lazy release-day conversion: whenever a released campaign page is
        hit, complete a small batch of pending pre-saves. No cron needed."""
        _send_release_emails(campaign)
        if not spotify.configured() or links_engine.is_prerelease(campaign):
            return
        dest = next((d for d in mls.get_destinations(campaign["id"])
                     if d["service_key"] == "spotify"), None)
        track_id = spotify.track_id_from_url(dest["url"]) if dest else None
        for p in store.pending_spotify_presaves(campaign["id"]):
            if not track_id:
                store.resolve_spotify_presave(p["id"], "retry", "No Spotify track URL on campaign")
                continue
            try:
                grant = spotify.refresh_access_full(
                    spotify.decrypt_token(p["refresh_token_enc"]))
                access = grant.get("access_token")
                if access and spotify.save_track(access, track_id):
                    store.resolve_spotify_presave(p["id"], "completed")
                    store.notify(campaign["user_id"], "fan",
                                 "Pre-save delivered: %s" % campaign["title"],
                                 "Saved to a fan's Spotify library on release.",
                                 "/links/%s/analytics" % campaign["id"])
                else:
                    store.resolve_spotify_presave(p["id"], "retry", "Save failed")
            except Exception as exc:
                detail = str(exc)
                if hasattr(exc, "read"):
                    try:
                        detail += " " + exc.read().decode("utf-8", "replace")[:120]
                    except Exception:
                        pass
                try:
                    detail += " scope=" + (grant.get("scope") or "none")
                except Exception:
                    pass
                store.resolve_spotify_presave(p["id"], "retry", detail)

    @app.route("/mail/diag")
    def mail_diag():
        """Why aren't emails reaching anyone? Reports the SHAPE of the mail
        setup and, read-only, what Resend says about the account's domains -
        including the exact DNS records each still needs, so nobody has to
        go hunting for them. Requires a signed-in account; no secret ever
        leaves this endpoint."""
        user = current_user()
        if user is None:
            return jsonify({"error": "auth required"}), 401
        info = {
            "configured": emailer.configured(),
            "sender": emailer.sender(),
            "using_shared_test_sender": emailer.using_shared_test_sender(),
            "email_from_set": bool(os.environ.get("EMAIL_FROM")),
            "inbound_domain": os.environ.get("RESEND_INBOUND_DOMAIN", ""),
            "webhook_secret_set": bool(os.environ.get("RESEND_WEBHOOK_SECRET")),
        }
        if emailer.configured() and request.args.get("domains") == "1":
            info["resend"] = emailer.domain_status()
        return jsonify(info)

    def _r2_check():
        """Write, sign, read back and delete one tiny object.

        Presence booleans only prove four variables are set. This is the
        thing that actually fails when a key is wrong, the bucket name is
        misspelled or the account id belongs to a different tenant.
        """
        if not blob_store.configured():
            return {"configured": False, "note": "R2 vars not set; uploads go to disk"}
        key = "_diag/roundtrip-%d.txt" % int(datetime.now(timezone.utc).timestamp())
        payload = b"street-banker r2 round trip"
        result = {"configured": True}
        try:
            result["put"] = bool(blob_store.put(key, payload, "text/plain"))
        except Exception as exc:
            result["put"] = False
            result["put_error"] = type(exc).__name__
            result["put_reason"] = str(getattr(exc, "reason", exc))[:180]
            # S3 puts a machine-readable <Code> in the error body and it
            # names the failure exactly: InvalidAccessKeyId,
            # SignatureDoesNotMatch, NoSuchBucket, AccessDenied. Throwing
            # that away and reporting "Unauthorized" loses the answer.
            body = getattr(exc, "read", None)
            if callable(body):
                try:
                    raw = exc.read().decode("utf-8", "replace")[:600]
                    result["s3_error_body"] = raw
                    code = re.search(r"<Code>([^<]+)</Code>", raw)
                    msg = re.search(r"<Message>([^<]+)</Message>", raw)
                    if code:
                        result["s3_code"] = code.group(1)
                    if msg:
                        result["s3_message"] = msg.group(1)[:200]
                except Exception:
                    pass
            result["why"] = blob_store.diagnose()
            return result
        try:
            got = blob_store.fetch(blob_store.PREFIX + key)
            result["get"] = got == payload
            if got is not None and got != payload:
                result["get_note"] = "read back %d bytes, expected %d" % (len(got), len(payload))
        except Exception as exc:
            result["get"] = False
            result["get_error"] = type(exc).__name__
        try:
            result["delete"] = bool(blob_store.delete(key))
        except Exception as exc:
            result["delete"] = False
            result["delete_error"] = type(exc).__name__
        result["ok"] = bool(result.get("put") and result.get("get") and result.get("delete"))
        return result

    @app.route("/storage/diag")
    def storage_diag():
        """Is object storage actually working, and if not, which variable is
        wrong? The round-trip below writes, reads and deletes one tiny
        object; `why` reports the SHAPE of each credential (lengths, hex,
        whether two of them are the same string) and never a value.

        It lived inside /presave/diag, which only a label-plan account could
        open, so the person who owns the bucket could not see it.
        """
        user = current_user()
        if user is None:
            return jsonify({"error": "auth required"}), 401
        report = _r2_check()
        if not report.get("configured"):
            report["next"] = ("Set R2_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID and "
                              "R2_SECRET_ACCESS_KEY in Render. Until then uploads "
                              "stay on this server's disk.")
        elif not report.get("ok"):
            why = report.get("why") or {}
            hints = []
            if not why.get("secret_is_64_hex"):
                hints.append("R2_SECRET_ACCESS_KEY should be 64 hex characters "
                             "(it is %d). Cloudflare shows it once, on R2 -> "
                             "Manage R2 API Tokens -> Create token."
                             % why.get("secret_len", 0))
            if not why.get("access_key_is_32_hex"):
                hints.append("R2_ACCESS_KEY_ID should be 32 hex characters "
                             "(it is %d)." % why.get("access_key_len", 0))
            if why.get("bucket_looks_like_an_id"):
                hints.append("R2_BUCKET looks like an id, not a name. It is the "
                             "bucket's name as typed when it was created.")
            if why.get("bucket_equals_access_key_id") or why.get("account_id_equals_access_key_id"):
                hints.append("Two of the four variables hold the same string, so "
                             "the paste was shifted across the fields.")
            if not why.get("account_id_is_32_hex"):
                hints.append("R2_ACCOUNT_ID should be 32 hex characters "
                             "(it is %d); it is in the R2 endpoint URL."
                             % why.get("account_id_len", 0))
            report["next"] = hints or ["The four variables have the right shape; "
                                       "read s3_code above for what Cloudflare said."]
        return jsonify(report)

    @app.route("/presave/diag")
    def presave_diag():
        # Owner-only config check: reports WHICH credentials the running
        # process can see (presence booleans only, never values).
        user = current_user()
        if user is None or (user.get("plan") or "artist") != "label":
            abort(404)
        return jsonify({
            "SPOTIFY_CLIENT_ID": bool(os.environ.get("SPOTIFY_CLIENT_ID")),
            "SPOTIFY_CLIENT_SECRET": bool(os.environ.get("SPOTIFY_CLIENT_SECRET")),
            "SPOTIFY_REDIRECT_URI": bool(os.environ.get("SPOTIFY_REDIRECT_URI")),
            "configured": spotify.configured(),
            "DATABASE_PATH_set": bool(os.environ.get("DATABASE_PATH")),
            "db_path_in_use": store.db_path(),
            "v": 13,
            "presave_states": _presave_states(user["id"]),
            "stripe_activity": _stripe_activity(),
            "STRIPE_SECRET_KEY": bool(os.environ.get("STRIPE_SECRET_KEY")),
            "STRIPE_WEBHOOK_SECRET": bool(os.environ.get("STRIPE_WEBHOOK_SECRET")),
            "webhook_secret_stored": bool(store.get_kv("stripe_webhook_secret")),
            "RESEND_WEBHOOK_SECRET": bool(os.environ.get("RESEND_WEBHOOK_SECRET")),
            "RESEND_INBOUND_DOMAIN": os.environ.get("RESEND_INBOUND_DOMAIN", ""),
            "RESEND_API_KEY": bool(os.environ.get("RESEND_API_KEY")),
            "email_configured": emailer.configured(),
            "email_sender": emailer.sender(),
            "var_data_is_real_mount": os.path.ismount("/var/data"),
            "R2_ACCOUNT_ID": bool(os.environ.get("R2_ACCOUNT_ID")),
            "R2_BUCKET": bool(os.environ.get("R2_BUCKET")),
            "R2_ACCESS_KEY_ID": bool(os.environ.get("R2_ACCESS_KEY_ID")),
            "R2_SECRET_ACCESS_KEY": bool(os.environ.get("R2_SECRET_ACCESS_KEY")),
            # Not a secret - it is a public CDN hostname if it is set at all.
            "R2_PUBLIC_BASE_URL": os.environ.get("R2_PUBLIC_BASE_URL", ""),
            "r2_check": _r2_check(),
            "app_token_check": _app_token_check(),
            "search_check": _search_check(),
            "artist_check": _probe("/artists/3TVXtAsR1Inumwj472S9r4"),
            "toptracks_check": _probe(
                "/artists/3TVXtAsR1Inumwj472S9r4/top-tracks?market=US"),
        })

    def _probe(path):
        """Owner-only: raw API attempt, reporting the exact failure."""
        try:
            spotify._api(path, spotify.app_token())
            return "ok"
        except Exception as exc:
            detail = ""
            if hasattr(exc, "read"):
                try:
                    detail = " body=" + exc.read().decode("utf-8", "replace")[:150]
                except Exception:
                    pass
            return "%s: %s%s" % (type(exc).__name__, exc, detail)

    def _presave_states(user_id):
        """Owner-only: status/retries/error per pre-save on own campaigns."""
        out = []
        with store.get_db() as conn:
            rows = conn.execute(
                "SELECT sp.status, sp.retry_count, sp.error, mc.slug "
                "FROM spotify_presaves sp JOIN ml_campaigns mc ON mc.id = sp.campaign_id "
                "WHERE mc.user_id = ? ORDER BY sp.created DESC LIMIT 10",
                (user_id,)).fetchall()
        for r in rows:
            out.append({"slug": r["slug"], "status": r["status"],
                        "retries": r["retry_count"], "error": (r["error"] or "")[:120]})
        return out

    def _stripe_activity():
        """Owner-only: proof the billing webhook fired — counts only."""
        with store.get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM users WHERE stripe_customer_id IS NOT NULL "
                "AND stripe_customer_id != ''").fetchone()
            plans_row = conn.execute(
                "SELECT plan, COUNT(*) AS n FROM users WHERE stripe_customer_id IS NOT NULL "
                "AND stripe_customer_id != '' GROUP BY plan").fetchall()
        return {"customers": row["n"],
                "plans": {r["plan"]: r["n"] for r in plans_row}}

    def _app_token_check():
        """Owner-only: does the client-credentials grant actually work?
        Reports the failure class, never the credentials themselves."""
        try:
            return "ok" if spotify.app_token() else "no token in response"
        except Exception as exc:
            return "%s: %s" % (type(exc).__name__, exc)

    def _search_check():
        """Owner-only: raw /v1/search attempt, reporting the exact failure."""
        try:
            data = spotify._api("/search?q=drake&type=artist&limit=1",
                                spotify.app_token())
            items = (data.get("artists") or {}).get("items", [])
            return "ok: %d items" % len(items)
        except Exception as exc:
            detail = ""
            if hasattr(exc, "read"):
                try:
                    detail = " body=" + exc.read().decode("utf-8", "replace")[:200]
                except Exception:
                    pass
            return "%s: %s%s" % (type(exc).__name__, exc, detail)

    @app.route("/presave/retry-reset", methods=["POST"])
    def presave_retry_reset():
        """Owner tool: re-arm pending/failed pre-saves on own campaigns after
        fixing an external cause (e.g. Spotify allowlist)."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        with store.get_db() as conn:
            cur = conn.execute(
                "UPDATE spotify_presaves SET retry_count = 0, status = 'pending' "
                "WHERE status != 'completed' AND campaign_id IN "
                "(SELECT id FROM ml_campaigns WHERE user_id = ?)", (user["id"],))
        return jsonify({"ok": True, "reset": cur.rowcount})

    @app.route("/presave/<slug>/start")
    def presave_start(slug):
        campaign = mls.get_campaign_by_slug(slug)
        if campaign is None or campaign["status"] != "live" or not spotify.configured():
            return redirect("/l/" + slug)
        nonce = uuid.uuid4().hex
        session["presave_nonce"] = nonce
        return redirect(spotify.auth_url("%s.%s" % (slug, nonce)))

    @app.route("/presave/callback")
    def presave_callback():
        state = request.args.get("state") or ""
        slug = state.split(".")[0] if "." in state else ""
        campaign = mls.get_campaign_by_slug(slug) if slug else None
        if campaign is None or not spotify.configured():
            return redirect("/")
        if state.split(".")[-1] != session.pop("presave_nonce", None):
            return redirect("/l/%s?presave=error" % slug)
        if request.args.get("error") or not request.args.get("code"):
            return redirect("/l/%s?presave=denied" % slug)
        try:
            tokens = spotify.exchange_code(request.args["code"])
            me = spotify.get_me(tokens["access_token"])
        except Exception:
            return redirect("/l/%s?presave=error" % slug)
        email = (me.get("email") or "").lower()
        presave_id = store.add_spotify_presave(
            campaign["id"], me.get("id") or "unknown", email,
            spotify.encrypt_token(tokens.get("refresh_token") or ""))
        if presave_id is None:
            return redirect("/l/%s?presave=already" % slug)
        # The OAuth consent screen covered email sharing; log it into the CRM.
        if email:
            fan_id = mls.upsert_fan(campaign["user_id"], email, campaign["id"],
                                    me.get("display_name") or "")
            mls.add_consent(fan_id, campaign["id"], "spotify_presave",
                            "Authorized Spotify pre-save (library save + email).")
            mls.bump_fan(fan_id, "total_presaves")
            fan = mls.get_fan(fan_id)
            score, level = links_engine.calculate_fan_intent(fan)
            mls.set_fan_intent(fan_id, score, level)
            mls.track(campaign["id"], "presave_notify", fan_id=fan_id)
        else:
            mls.track(campaign["id"], "presave_notify")
        store.notify(campaign["user_id"], "fan",
                     "Spotify pre-save: %s" % (email or me.get("id") or "a fan"),
                     "Via \u201c%s\u201d \u2014 track saves to their library on release day." % campaign["title"],
                     "/links/fans")
        # Already released? Deliver immediately.
        if not links_engine.is_prerelease(campaign):
            _process_due_presaves(campaign)
        return redirect("/l/%s?presave=done" % slug)

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
                _process_due_presaves(campaign)
            owner_epk = store.get_epk(campaign["user_id"]) or {}
            return render_template(
                "link_campaign.html", c=campaign,
                store_url=((owner_epk.get("data") or {}).get("store_url") or ""),
                spotify_presave=spotify.configured(),
                presave_state=(request.args.get("presave") or ""),
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
        store.notify(campaign["user_id"], "fan",
                     "%s: %s" % ("New pre-save" if prerelease else "New fan captured", email),
                     "Via “%s” — consent logged, intent scored." % campaign["title"],
                     "/links/fans")
        # Fan gate: the reward resolves through the owner's own vault listing,
        # and the link is only handed out after a real capture.
        reward = None
        gate_id = settings.get("gate_reward") or ""
        if gate_id:
            v = next((v for v in store.list_vault_files(campaign["user_id"])
                      if v["id"] == gate_id), None)
            if v:
                reward = {"url": v["path"],
                          "label": settings.get("gate_label")
                          or v["label"] or "Your unlock"}
        return jsonify({"ok": True, "message": message, "reward": reward})

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

    # A question a stranger asks is free to answer, because every answer is
    # written down here already. Sending one to the owner is not free, so
    # only the escalations are throttled, and per address.
    _support_asked = {}

    @app.route("/support/ask", methods=["POST"])
    def support_ask():
        """Answer from what support has written down, or admit nobody knows.

        There is no model behind this. Every sentence comes from
        support_kb.ENTRIES, so it cannot invent an answer about an account's
        money, and a question nobody wrote an answer for goes to the owner
        rather than being improvised at.
        """
        import support_kb

        body = request.get_json(silent=True) or request.form or {}
        question = (body.get("q") or "").strip()[:2000]
        page = (body.get("page") or "")[:200]
        if not question:
            return jsonify({"kind": "empty"}), 400

        found = support_kb.answer(question)
        if found:
            return jsonify({"kind": "answer", "question": found["question"],
                            "answer": found["answer"], "where": found["where"]})

        user = current_user()
        note = support_kb.escalation(question, page=page,
                                     account=(user or {}).get("email") or "")
        ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "?")
              .split(",")[0].strip())
        now = time.time()
        if len(_support_asked) > 4096:
            _support_asked.clear()
        if now - _support_asked.get(ip, 0) > 20:
            _support_asked[ip] = now
            try:
                store.add_inbox("support-question", note)
            except Exception:
                current_app.logger.exception("support question")
        return jsonify({"kind": "unknown", "reply": note["reply"]})

    @app.route("/inbox")
    def inbox():
        user = current_user()
        if user is None:
            return login_required_redirect()
        # Owner accounts also see the rows that belong to no account:
        # demo-access leads, and anything written before inbox rows had
        # an owner at all.
        is_owner = _is_owner_email(user.get("email"))
        rows = store.get_inbox(user["id"], unowned=is_owner)
        ctx = build_dashboard_context()
        ctx["inbox"] = inbox_engine.build(rows)
        ctx["inbox_is_owner"] = is_owner
        return render_template("inbox.html", active_page="inbox", **ctx)

    @app.route("/")
    def index():
        # Homepage content is fully config-driven (landing_config); the
        # command-desk figures are editable there, not injected live.
        config = get_landing_config()

        # A missing image leaves its slot empty rather than 500-ing. The
        # hero now ships a responsive set rather than one src, so it is
        # checked by its widest derivative - if that is missing the whole
        # set is.
        def _has_file(img, key="src"):
            if not img or not img.get(key):
                return False
            rel = img[key].split("/static/", 1)[-1].split("?", 1)[0]
            return os.path.exists(os.path.join(app.static_folder, rel))

        hero_img = config["hero"].get("image") or {}
        widest = "%s-%s.jpg" % (hero_img.get("wide", ""),
                                max(hero_img.get("wide_widths") or [0]))
        if not _has_file({"src": widest}):
            config["hero"] = {**config["hero"], "image": None}

        # Whatever the owner has saved, on top of what ships. An empty
        # override is the shipped page exactly, so this cannot break the
        # homepage by existing.
        config = homepage_edit.apply_override(config)

        # The Artist EQ ships its data twice: once as a dict for Jinja to
        # render the plate from, once as JSON for the component script.
        eq = get_artist_eq_config()
        departments = get_departments_config()
        # After the split the public story lives on the store and this
        # address is the door to the system. Off unless the owner switched
        # it in Settings or the deployment sets SPLIT_HOME (split_home.py).
        # The owner can look at either one without switching it for
        # anybody: /?home=split and /?home=full. Only owner logins; for
        # everybody else the parameter does nothing at all, so a link to
        # it cannot show a stranger a page the owner has not chosen.
        want = (request.args.get("home") or "").strip().lower()
        me = current_user()
        if want in ("split", "full") and me and _is_owner_email(me.get("email")):
            split_on = want == "split"
        else:
            split_on = split_home.enabled()

        page = "landing.html"
        split_cfg = None
        if split_on:
            page = "landing_split.html"
            split_cfg = split_home.get_split_home_config(_signup_open())
        return render_template(page, config=config, artist_eq=eq,
                               split_home=split_cfg,
                               public_base=PUBLIC_BASE_URL,
                               artist_eq_json=json.dumps(eq),
                               departments=departments,
                               departments_json=json.dumps(departments),
                               eight_tools=get_eight_tools_config(),
                               artist_twin=get_artist_twin_config(),
                               lanes=get_lanes_config(),
                               creative=get_creative_config(),
                               rollout=get_rollout_config(),
                               sweep=get_sweep_config(),
                               distro=get_distro_config(),
                               passport=get_passport_config(),
                               completeness=passport_completeness(),
                               closing=get_closing_config(),
                               release_signal=get_release_signal_config())

    def _real_royalty():
        """Real statement analysis for the signed-in user, or None."""
        user = current_user()
        if user is None:
            return None
        rows = store.get_statement_rows(user["id"])
        return build_royalty_summary(rows) if rows else None

    TUTOR_COOKIE = "sb_tutor"

    def _tutor_on():
        return request.cookies.get(TUTOR_COOKIE) == "1"

    def _tutor_panel(user):
        """The full walkthrough, when tutor mode is switched on.

        Same discipline as firstrun below: every flag is a real query, so
        a step is done when the thing exists and comes back if the thing
        is deleted. Steps whose route the plan cannot open are dropped -
        a walkthrough must never point at a locked door.
        """
        if user is None or (user.get("plan") or "") == "fan":
            return None
        if not _tutor_on():
            return None
        uid = user["id"]
        try:
            campaigns = mls.list_campaigns(uid)
            epk = store.get_epk(uid) or {}
            profile_data = epk.get("data") if isinstance(epk, dict) else None
            state = {
                "profile": bool((user.get("name") or "").strip()
                                or (profile_data and profile_data not in ("{}", {}))),
                "track": bool(store.list_os_tracks(uid)) or bool(store.statement_titles(uid, 1)),
                "link": bool(campaigns) or bool(store.get_db_links(uid)),
                "rack": bool(store.get_rack_preset(uid)),
                "rate": bool(store.list_hours_rates(uid)),
                "campaign": bool(campaigns),
                "release_date": any((c.get("release_date") or "").strip()
                                    for c in campaigns),
                "publish": any(c.get("status") == "live" for c in campaigns),
                "press_contact": bool(press_store.list_contacts(uid)),
                "announcement": bool(press_store.list_releases(uid)),
                "statement": bool(store.get_statements(uid)),
            }
            plan = user.get("plan") or "artist"
            reachable = set()
            for skey, _n, _p, steps in tutor.STAGES:
                for key, _t, _w, href, _c in steps:
                    if plans.allowed(plan, plans.required_tier(href)):
                        reachable.add(key)
            # Plainly started: there is real work in here, so the
            # walkthrough stops taking the top of the dashboard.
            settled = bool(state["statement"] or state["campaign"]
                           or mls.list_fans(uid) or store.list_os_tracks(uid))
        except Exception:
            # A walkthrough is never worth breaking a page over.
            return None
        return tutor.build(state, reachable, settled=settled)

    @app.route("/tutor/toggle", methods=["POST"])
    def tutor_toggle():
        user = current_user()
        if user is None:
            return login_required_redirect()
        turning_on = request.form.get("on") == "1"
        response = redirect(request.form.get("back") or "/command-center")
        # A year: the choice should outlive the session, in this browser.
        response.set_cookie(TUTOR_COOKIE, "1" if turning_on else "0",
                            max_age=31536000, samesite="Lax",
                            secure=bool(os.environ.get("RENDER")))
        return response

    def _firstrun_panel(user):
        """The start-here checklist, or None once the account outgrows it.

        Every flag is a real query. Nothing here reads a "dismissed
        onboarding" bit: a step is done when the thing exists, so deleting
        the thing brings the step back. It is describing the account, not
        remembering a click.
        """
        if user is None or (user.get("plan") or "") == "fan":
            return None
        uid = user["id"]
        try:
            epk = store.get_epk(uid) or {}
            profile_data = epk.get("data") if isinstance(epk, dict) else None
            has_profile = bool(
                (user.get("name") or "").strip()
                or (profile_data and profile_data not in ("{}", {})))
            # Both halves of each answer, so this list and the tutor and
            # the scores cannot disagree about the same account (Codex
            # audit, 2026-09-17). A smart link lives in one of two tables
            # depending on which door made it, and an account's songs are
            # known from its passports OR from the statements it uploaded.
            state = {
                "profile": has_profile,
                "track": bool(store.list_os_tracks(uid)) or bool(store.statement_titles(uid, 1)),
                "link": bool(store.get_db_links(uid)) or bool(mls.list_campaigns(uid)),
                "rack": bool(store.get_rack_preset(uid)),
                "rate": bool(store.list_hours_rates(uid)),
            }
        except Exception:
            # A checklist is never worth breaking a page over.
            return None
        # Same rule as the walkthrough: never point at a locked door. The
        # tier gate and the suite gate both have to open (walk, 2026-09-20:
        # an Artist was told to open the Rack, which answers 402).
        plan = user.get("plan") or "artist"
        try:
            credits = _wallet(user)["total"]
        except Exception:
            credits = 0
        reachable = {key for key, _t, _w, href, _c in firstrun.STEPS
                     if plans.allowed(plan, plans.required_tier(href))
                     and plans.suite_open(plan, plans.path_suite(href), credits)}
        return firstrun.build(state, reachable)

    @app.route("/overview")
    def overview():
        """The Overview and the Command Center are one page (owner,
        2026-09-15). This address keeps answering with it, so no link,
        bookmark or test dies; the sidebar and the rooms only name the
        Command Center."""
        return command_center_page()

    def _front_money_context():
        """What the Overview page computed, for the front door."""
        # Money Left on the Table used to read from the same hardcoded
        # platform list as /recovery, so every account was told it was
        # owed $3,301.38. Hand the card the account's own scan instead.
        user = current_user()
        # Roll the visit stamp once per session, so the "since your last
        # visit" window does not close behind the reader on a refresh.
        since = None
        if user is not None:
            if not session.get("seen_rolled") and not session.get("team_as"):
                store.roll_seen(user["id"])
                session["seen_rolled"] = True
            since = store.get_prev_seen(user["id"])
        # The months this page charts and totals. A template should not be
        # choosing between a real trend and the showcase's hardcoded one -
        # and a {% set %} at the top of a template is invisible inside
        # {% block scripts %}, which is how the chart came to read seed
        # data on an account that had statements of its own.
        rr = _real_royalty()
        showcase = _session_is_demo()
        balances = get_platform_balances() if showcase else []
        ctx = build_dashboard_context()
        # The account's own goal, or none. build_dashboard_context still
        # carries royalty_data's $25,000 for the showcase; a real account
        # gets what it set, and "no goal yet" rather than a number it
        # never chose.
        goal_row = store.get_royalty_goal(user["id"]) if user is not None and not showcase else None
        if not showcase:
            ctx["goal"] = goal_row["amount"] if goal_row else 0
        ctx["goal_row"] = goal_row
        ctx.update(since_visit=(since_engine.build(user["id"], since)
                                if user is not None and not showcase else None),
                   real_royalty=rr,
                   months=(rr["monthly_trend"] if rr
                           else (get_earnings_trend() if showcase else [])),
                   tracked=(rr["total"] if rr
                            else (total_royalties(balances) if showcase else 0)),
                   recovery_view=(recovery_engine.build(user["id"])
                                  if user is not None and not showcase else None))
        return ctx

    @app.route("/overview/goal", methods=["POST"])
    def overview_goal():
        """Save the royalty goal on the account. It used to go to
        localStorage - "Saved on this device" - so it never followed the
        artist to their phone, and the ring showed a $25,000 nobody set."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if request.form.get("clear") == "1":
            store.clear_royalty_goal(user["id"])
            return redirect("/overview")
        try:
            amount = float(request.form.get("amount") or "")
        except ValueError:
            amount = 0.0
        if amount <= 0:
            return redirect("/overview?goal=invalid")
        store.set_royalty_goal(user["id"], amount, request.form.get("kind") or "yearly",
                               request.form.get("deadline") or "")
        return redirect("/overview")

    @app.route("/dashboard")
    def dashboard():
        return redirect("/overview")

    @app.route("/royalties")
    def royalties():
        # The period control used to read "This month / Last 3 months /
        # Last 6 months" and had no listener anywhere - three options that
        # did nothing, on a money page. It lists the periods actually on
        # file now and filters to one, because a statement period is a
        # label a distributor chose ("JUN-26"), not a rolling window this
        # app can compute.
        #
        # One page where there were three (2026-09-13): Royalty Lanes and
        # Income by type are read here too, laid out by royalties_desk.
        import royalties_desk
        user = current_user()
        # A label's export names every act on the roster. One act can be
        # put in scope (2026-09-14) and every figure on the page follows
        # it, the way every figure already follows the period.
        roster, act, rows_all = _act_scope(store.get_statement_rows(user["id"]) if user else [])
        periods = royalties_desk.order_periods(
            (r["period"] or "").strip() for r in rows_all if r["period"])
        chosen = (request.args.get("period") or "").strip()
        if chosen and chosen in periods:
            rows = [r for r in rows_all if (r["period"] or "").strip() == chosen]
        else:
            chosen, rows = "", rows_all
        desk = None
        if rows:
            desk = royalties_desk.build(
                rows_all, rows, store.get_statements(user["id"]), chosen,
                store.list_os_tracks(user["id"]), _os_ctx(user["id"]),
                mlc=recovery_mlc.state(user["id"]), artist=act, roster_rows=roster)
        return render_template("royalties.html", active_page="royalties",
                               desk=desk, roy_periods=periods, roy_period=chosen,
                               **build_dashboard_context())

    @app.route("/catalog")
    def catalog_page():
        ctx = build_dashboard_context()
        ctx["catalog"] = get_catalog_data()
        user = current_user()
        ctx["catalog_user"] = user
        ctx["my_tracks"] = store.get_catalog_tracks(user["id"]) if user else []
        # Identifiers, folded in from /identifiers: the same records, read
        # for their codes. The ISWC is pulled: a matched work at The MLC
        # carries one, and the passport link puts it on the catalog row.
        ids_rows = []
        for t in ctx["my_tracks"]:
            m = t.get("meta") or {}
            ids_rows.append({"id": t["id"], "title": t["title"], "artist": t["artist"],
                             "isrc": m.get("isrc") or "", "upc": m.get("upc") or "",
                             "label": m.get("label") or "", "iswc": "",
                             "release_date": m.get("release_date") or ""})
        ctx["ids_rows"] = ids_rows
        ctx["ids_with_isrc"] = sum(1 for r in ids_rows if r["isrc"])
        ctx["ids_with_upc"] = sum(1 for r in ids_rows if r["upc"])
        ctx["ids_missing_isrc"] = len(ids_rows) - ctx["ids_with_isrc"]
        # TRACK PASSPORTS - folded in from /tracks (tier C, 2026-09-09). One
        # song list: each catalog row carries its passport (rights, splits,
        # MLC checks, certificate). A passport that sits on no catalog row -
        # data from before the two tables were linked - is listed too, so
        # nothing is hidden; the start-up link makes that rare.
        ctx.update(_passport_section(user, ctx["my_tracks"]) if user else
                   {"passport_rows": [], "passport_pipeline": [],
                    "passport_cert": None, "passport_summary": None,
                    "discogs": _DISCOGS_OFF})
        # ISWC coverage: catalog rows whose linked passport holds an MLC
        # check with a work code on it. Counted after the passports are
        # read, because that is where the code comes from.
        ctx["ids_with_iswc"] = len([r for r in ctx["passport_rows"]
                                    if r["catalog"] and r["iswc"]])
        _iswc_by_catalog_id = {r["catalog"]["id"]: r["iswc"]
                               for r in ctx["passport_rows"] if r["catalog"]}
        for row in ids_rows:
            row["iswc"] = _iswc_by_catalog_id.get(row["id"], "")
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
                "total_releases": releases_n,
                "releases_added_this_month": sum(
                    1 for r in ctx["my_releases"]
                    if (r.get("release_date") or "").startswith(month)),
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
            # The filter beside the search is built from the same sample
            # releases and was NOT zeroed with the rest, so a brand-new
            # account with an empty catalog got a dropdown offering four
            # albums by the fictional Synthwave Surfer. It follows the
            # account's own releases now, which is an empty list until
            # they have some.
            c["release_filter_options"] = (
                ["All Releases"] + [r["title"] for r in c["releases"]])
            c["recently_added"] = [{"id": t["id"], "title": t["title"], "type": "Single",
                                    "date_added": (t.get("added") or "")[:10],
                                    "status": "Registered" if (t.get("meta") or {}).get("isrc") else "Pending"}
                                   for t in tracks[:5]]
        ctx["view"] = "passports" if request.args.get("view") == "passports" else "catalog"
        return render_template("catalog.html", active_page="catalog", **ctx)

    def _passport_section(user, my_tracks):
        """The Track Passports section: each song once, with its passport
        state. A passport on no catalog row (from before the link) is
        listed too, so nothing is hidden."""
        os_tracks = store.list_os_tracks(user["id"])
        by_id = {t["id"]: t for t in os_tracks}
        osctx = _os_ctx(user["id"])
        ordered, seen = [], set()
        for ct in my_tracks:
            t = by_id.get(ct.get("passport_track_id") or "")
            if t is not None and t["id"] not in seen:
                seen.add(t["id"])
                ordered.append((ct, t))
        for t in os_tracks:
            if t["id"] not in seen:
                seen.add(t["id"])
                ordered.append((None, t))
        rows = []
        for ct, t in ordered:
            checks = store.list_track_mlc_checks(user["id"], t["id"], limit=1)
            passport = t.get("passport") or {}
            meta = (ct or {}).get("meta") or {}
            clean = artist_os.clean_release(t, osctx)
            rows.append({"t": t, "catalog": ct,
                         "passport": artist_os.passport_report(t),
                         "clean": clean,
                         "caps": artist_os.lockbox_report(t)["caps"],
                         "isrc": (passport.get("isrc") or meta.get("isrc") or "").strip(),
                         "mlc": checks[0] if checks else None,
                         # The one identifier nothing in this app used to
                         # pull: a matched work at The MLC carries it.
                         "iswc": artist_os.mlc_evidence(t)["iswc"],
                         "certificate": (not clean["blocked"]
                                         and clean["score"] >= 100)})
        discogs = _discogs_state(user, rows)
        summary = _os_summary(user["id"], [t for _ct, t in ordered], osctx)
        return {
            "passport_rows": rows,
            "discogs": discogs,
            "passport_summary": summary,
            "passport_cert": artist_os.certification(summary),
            "passport_pipeline": [
                ("In catalog", len(rows)),
                ("Metadata complete", len([r for r in rows
                                           if r["passport"]["pct"] == 100])),
                ("Rights signed", len([r for r in rows if r["caps"]["release"]])),
                ("Release-ready", len([r for r in rows
                                       if not r["clean"]["blocked"]
                                       and r["clean"]["score"] >= 80])),
            ],
        }

    # --- Discogs: the pressing behind a song ------------------------------------
    #
    # Discogs is a discography, not an audience source: it answers what a
    # record IS - the label, the catalogue number, the country, the year,
    # the format and the people printed on the sleeve. The owner looks a
    # song up, picks the pressing that is actually theirs, and attaches
    # it; the attach fills only passport fields that are still EMPTY, the
    # same rule the MLC fill action follows, and records which fields came
    # from Discogs so a filled value can always be told from a typed one.
    #
    # Credits are the deliberate exception: they are shown and never
    # written. A songwriter field is a rights claim, and a third-party
    # database does not get to make one on somebody else's behalf.

    _DISCOGS_OFF = {"on": False, "flag": "DISCOGS_ENABLED", "token": "DISCOGS_TOKEN",
                    "open": "", "candidates": [], "error": "", "asked": "",
                    "sandbox": False}

    # passport field <- the field of a normalised Discogs release that may
    # fill it. Nothing derived from a credit is in this list, on purpose.
    _DISCOGS_FILLS = (("label", "label"), ("release_title", "title"),
                      ("release_date", "released"), ("upc", "barcode"),
                      ("isrc", "isrc"), ("catalog_number", "catno"))

    def _discogs_back(user, track_id):
        """Where a lookup lands: the catalog section for a plan that has
        the Catalog page, the passports page for one that has not."""
        home = _passports_home(user)
        if "?" in home:                       # the catalog's passports view
            return "%s&discogs=%s" % (home, track_id)
        return "%s?discogs=%s#passports" % (home, track_id)

    def _discogs_query(row):
        """What this song would be looked up by: the artist and title, plus
        a catalogue number or barcode when the passport holds one."""
        passport = row["t"].get("passport") or {}
        meta = (row["catalog"] or {}).get("meta") or {}
        link = row.get("discogs") or {}
        return {
            "artist": (passport.get("artist_name")
                       or (row["catalog"] or {}).get("artist") or "").strip(),
            "title": (row["t"]["title"] or "").strip(),
            # A catalogue number identifies a pressing almost on its own.
            # The typed one wins: the artist reading it off their own
            # sleeve is better evidence than the pressing already
            # attached, and it is the only one a FIRST lookup can have.
            "catno": ((passport.get("catalog_number") or "").strip()
                      or (link.get("catno") or "").strip()),
            "barcode": (passport.get("upc") or meta.get("upc") or "").strip(),
        }

    def _discogs_state(user, rows):
        """The Discogs surface for the catalog page.

        Every row gets its attached pressing (or None). A lookup runs only
        for the one song named in ?discogs=, which is only ever set by the
        Look up button - so opening /catalog calls nothing.
        """
        import signal_providers as sp
        for r in rows:
            r["discogs"] = None
        links = store.discogs_links_by_track(user["id"])
        for r in rows:
            r["discogs"] = links.get(r["t"]["id"])
        adapter = sp.discogs_adapter()
        state = dict(_DISCOGS_OFF, on=adapter.configured(),
                     sandbox=sandbox.active(), candidates=[])
        open_id = (request.args.get("discogs") or "").strip()
        if not state["on"] or not open_id:
            return state
        row = next((r for r in rows if r["t"]["id"] == open_id), None)
        if row is None:
            return state
        state["open"] = open_id
        q = _discogs_query(row)
        state["asked"] = " ".join(p for p in
                                  [q["artist"], q["title"],
                                   ("catalogue " + q["catno"]) if q["catno"] else "",
                                   ("barcode " + q["barcode"]) if q["barcode"] else ""] if p)
        try:
            state["candidates"] = adapter.search_release(
                q["artist"], q["title"], catno=q["catno"], barcode=q["barcode"])
        except sp.ProviderError as e:
            # Discogs' own words - "Invalid consumer token...", the rate
            # limit - travel to the owner, because a bare 401 does not say
            # whether to fix the token or wait a minute.
            state["error"] = str(e)
        return state

    @app.route("/tracks/<track_id>/discogs", methods=["POST"])
    def os_track_discogs(track_id):
        """Look a song up on Discogs, or attach the pressing the owner picked.

        'attach' stores the release and fills passport fields that are
        still empty. A value the artist typed is a decision and is never
        overwritten. Credits are stored with the link so the owner can
        read them; nothing copies them into splits or songwriter fields.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        track = store.get_os_track(user["id"], track_id)
        if track is None:
            abort(404)
        import signal_providers as sp
        adapter = sp.discogs_adapter()
        back = _discogs_back(user, track_id)
        if not adapter.configured():
            return redirect(_discogs_back(user, "off"))
        if request.form.get("action") == "attach":
            release_id = (request.form.get("release_id") or "").strip()
            if not release_id:
                return redirect(back)
            try:
                release = adapter.get_release(release_id)
            except sp.ProviderError:
                # The lookup that follows the redirect reports it in
                # Discogs' own words; nothing is written on a failure.
                return redirect(back)
            if not release:
                return redirect(back)
            passport = track.get("passport") or {}
            fills = {}
            for field, source in _DISCOGS_FILLS:
                value = (release.get(source) or "").strip()
                if value and not (passport.get(field) or "").strip():
                    fills[field] = value[:200]
            if fills:
                passport.update(fills)
                store.update_os_track_passport(user["id"], track_id, passport)
            store.set_discogs_link(user["id"], track_id, release, fills)
            return redirect(back)
        return redirect(back)

    def _mlc_credits(isrc):
        """Writers and publishers for a recording from The MLC, by ISRC, or
        None: no ISRC, no MLC login on this deployment, no work linked, or
        The MLC did not answer. The track is saved either way."""
        isrc = (isrc or "").strip().upper()
        if not isrc:
            return None
        import signal_providers as sp
        adapter = sp.mlc_adapter()
        if not adapter.configured():
            return None
        try:
            works = adapter.lookup(isrc=isrc)["works"]
        except sp.ProviderError:
            return None
        if not works:
            return None
        work = works[0]
        writers = [w.get("name") for w in work.get("writers") or [] if w.get("name")]
        publishers = [p.get("name") for p in work.get("publishers") or [] if p.get("name")]
        if not writers and not publishers:
            return None
        return {"writers": writers, "publishers": publishers, "credits_source": "The MLC"}

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
            # Second hop: the ISRC unlocks songwriter/publisher credits,
            # from The MLC's register. This used MusicBrainz, whose free
            # service is for non-commercial use, on every paying artist's
            # add; the owner switched it to The MLC, which Street Banker
            # already licenses and which carries IPIs and shares
            # (2026-09-18: "switch to mlc", "brainz off for customers").
            credits = _mlc_credits(meta.get("isrc"))
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
        user = current_user()
        if user is None:
            return login_required_redirect()
        pulse_profile = store.get_pulse_profile(user["id"])
        statements = store.get_statements(user["id"])
        epk_dates_n = len(tour_dates_feed.upcoming(user["id"]))
        integrations = [
            {"name": "Spotify", "kind": "Live API",
             "on": spotify.pulse_configured(),
             "detail": ("Powers Artist Pulse, real pre-saves, and artist search."
                        if spotify.pulse_configured() else
                        "Server credentials not configured."),
             "action": ("/pulse", "Open Artist Pulse")},
            {"name": "Your Spotify profile", "kind": "Artist link",
             "on": bool(pulse_profile),
             "detail": ("Linked: %s — followers and popularity track daily."
                        % pulse_profile["artist_name"]) if pulse_profile
             else "Pick your artist on Artist Pulse to start tracking.",
             "action": ("/pulse", "Link on Artist Pulse")},
            {"name": "Deezer", "kind": "Public API",
             "on": True,
             "detail": "Fan counts and track identifiers — no key needed.",
             "action": ("/pulse", "See fan count")},
            {"name": "Email (Resend)", "kind": "Delivery",
             "on": emailer.configured(),
             "detail": ("Release-day fan emails, team invites, and password "
                        "resets send from %s." % emailer.sender())
             if emailer.configured() else "RESEND_API_KEY not set on the server.",
             "action": ("/links", "Campaigns that use it")},
            {"name": "Tour dates", "kind": "Your tour (first-party)",
             "on": bool(epk_dates_n),
             "detail": (("Tour dates: from your tour in Street Banker (%d confirmed)."
                         % epk_dates_n if epk_dates_n else
                         "Tour dates: confirm a date in TOUR and it appears here.")
                        + " Bandsintown declined this platform an app_id "
                        "(2026-09-07); that listing stays dormant."),
             "action": ("/epk", "EPK tour section")},
            {"name": "Royalty statements", "kind": "Your uploads",
             "on": bool(statements),
             "detail": ("%d statement%s uploaded — powering Royalties, Recovery, "
                        "Tax, and Capital." % (len(statements),
                                               "" if len(statements) == 1 else "s"))
             if statements else "Upload CSVs — they power the entire money engine.",
             "action": ("/statements", "Upload statements")},
            {"name": "iTunes / Odesli / MusicBrainz", "kind": "Public APIs",
             "on": True,
             "detail": "Catalog search, universal links, credits — no keys needed.",
             "action": ("/catalog", "Search the catalog")},
        ]
        # Not honest to pretend these connect today.
        unavailable = [
            ("Distributor analytics (DistroKid, TuneCore, CD Baby)",
             "Per-track stream counts and listener data need distributor feeds — no public API exists yet."),
            ("PRO / MLC registrations (ASCAP, BMI, MLC)",
             "Registration status requires society data access."),
        ]
        return render_template("connections.html", active_page="settings",
                               integrations=integrations, unavailable=unavailable,
                               **build_dashboard_context())

    def _safe_next(value, default):
        """A same-site path to return to, or the default. A form pressed
        from the Recovery page goes back to Recovery; one pressed on the
        case desk stays there. Never an absolute URL."""
        v = (value or "").strip()
        # "/\host" is read by browsers as "//host", another site, and a
        # line break could smuggle a header.
        ok = (v.startswith("/") and not v.startswith(("//", "/\\"))
              and not any(c in v for c in ("\n", "\r")))
        return v if ok else default

    def _strip_case(user_id, case_id):
        """The case the strip edits, with its rail, or None."""
        import recovery_desk
        case = store.get_recovery_case(user_id, case_id) if case_id else None
        if case:
            case["rail"] = recovery_desk.rail(case)
        return case

    @app.route("/recovery")
    def recovery():
        # One page for every account, including the showcase - the demo
        # has real statements now, so it is scanned by the same engine
        # rather than shown a hardcoded copy of what a scan looks like.
        #
        # The desk (recovery_desk) lays the engine's findings out by
        # basis, with the store checks and the case desk read alongside.
        import recovery_desk
        user = current_user()
        rv = mlc = desk = strip_case = None
        doc_list = []
        roster, act = [], ""
        if user:
            roster, act, rows = _act_scope(store.get_statement_rows(user["id"]))
            analysis = analyze_statement(rows) if rows else None
            rv = recovery_engine.build(user["id"], rows=rows, analysis=analysis)
            mlc = recovery_mlc.state(user["id"])
            cases = store.list_recovery_cases(user["id"])
            isrc_by_title = {}
            for r in rows:
                title = (r["title"] or "").strip()
                if title and r["isrc"] and title not in isrc_by_title:
                    isrc_by_title[title] = r["isrc"]
            desk = recovery_desk.build(rv, analysis, rows, store.get_statements(user["id"]),
                                       mlc, store.get_gap_checks(user["id"]), cases, isrc_by_title)
            strip_case = _strip_case(user["id"], request.args.get("case"))
            doc_list = store.list_documents(user["id"]) if strip_case else []
        return render_template(
            "recovery.html", active_page="recovery",
            recovery_view=rv, mlc=mlc, desk=desk, roster=roster, act=act,
            strip_case=strip_case,
            strip_next=("/recovery?case=%s#case-strip" % strip_case["id"]) if strip_case else "/recovery",
            strip_close="/recovery#findings",
            doc_list=doc_list, categories=_CASE_CATEGORIES, statuses=_CASE_STATUSES,
            mlc_note={"off": "The MLC is not connected on this service.",
                      "none": "No Track Passport carries an ISRC yet, so there is nothing to ask about."
                      }.get(request.args.get("mlc") or "", ""),
            **build_dashboard_context())

    @app.route("/recovery/mlc", methods=["POST"])
    def recovery_mlc_sweep():
        """One sweep of every passport ISRC through The MLC, on request."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        import signal_providers as sp
        back = "/recovery"          # Mechanicals folded into Royalties (2026-09-13); the sweep lives here
        if not sp.mlc_adapter().configured():
            return redirect(back + "?mlc=off#mlc")
        if not recovery_mlc.candidates(user["id"])[0]:
            return redirect(back + "?mlc=none#mlc")
        recovery_mlc.sweep(user["id"])
        return redirect(back + "#mlc")

    @app.route("/valuation")
    def valuation():
        user = current_user()
        # The valuation is recorded by the Command Center, which computes
        # it from the same statements. Read it back here rather than
        # recompute, so both pages agree on what today's number was.
        trend = (score_history.summarise(
            "valuation", store.score_trend(user["id"], "valuation"))
            if user else None)
        return render_template(
            "valuation.html", active_page="valuation",
            valuation_view=valuation_engine.build(user["id"]) if user else None,
            trend=trend, **build_dashboard_context())

    @app.route("/reports")
    def reports():
        ctx = build_dashboard_context()
        ctx["reports_user"] = current_user()
        ctx["reports_data"] = get_reports_data(
            demo=_is_demo_email((ctx["reports_user"] or {}).get("email") or ""),
            user_id=(ctx["reports_user"] or {}).get("id"))
        return render_template("reports.html", active_page="reports", **ctx)

    @app.route("/reports/campaigns.csv")
    def report_campaigns_csv():
        user = current_user()
        if user is None:
            return login_required_redirect()
        import csv as _csv
        import io as _io
        out = _io.StringIO()
        w = _csv.writer(out)
        w.writerow(["Campaign", "Artist", "Status", "Release Date", "SB Score",
                    "Visits", "Service Clicks", "CTR %", "Pre-saves",
                    "Email Captures", "QR Scans", "Public URL"])
        for c in mls.list_campaigns(user["id"]):
            counts = mls.event_counts(c["id"])
            visits = counts.get("page_view", 0)
            clicks = counts.get("service_click", 0)
            score = links_engine.calculate_street_banker_score(
                c, mls.get_destinations(c["id"]))
            w.writerow([c["title"], c["artist_name"],
                        links_engine.effective_status(c), c["release_date"],
                        score["total"], visits, clicks,
                        round(100 * clicks / visits, 1) if visits else 0,
                        counts.get("presave_notify", 0),
                        counts.get("email_capture", 0), counts.get("qr_scan", 0),
                        request.host_url.rstrip("/") + "/l/" + c["slug"]])
        return Response(out.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition": "attachment; filename=street-banker-campaigns.csv"})

    @app.route("/reports/recovery.csv")
    def report_recovery_csv():
        user = current_user()
        if user is None:
            return login_required_redirect()
        import csv as _csv
        import io as _io
        summary = build_royalty_summary(store.get_statement_rows(user["id"]))
        out = _io.StringIO()
        w = _csv.writer(out)
        w.writerow(["Finding", "Track", "Detail", "Amount / Estimate", "Type"])
        if summary:
            if summary["unmatched_revenue"]:
                w.writerow(["Unmatched revenue", "(rows with no title)",
                            "Money paid but not attributed — request corrected metadata",
                            summary["unmatched_revenue"], "Actual"])
            for g in summary["coverage_gaps"]:
                w.writerow(["Coverage gap", g["title"],
                            "Missing from: " + ", ".join(g["missing_sources"]),
                            g["estimated_value"], "Estimate"])
        return Response(out.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition": "attachment; filename=street-banker-recovery-findings.csv"})

    @app.route("/reports/executive")
    def report_executive():
        user = current_user()
        if user is None:
            return login_required_redirect()
        campaigns = []
        for c in mls.list_campaigns(user["id"]):
            counts = mls.event_counts(c["id"])
            campaigns.append({**c, "visits": counts.get("page_view", 0),
                              "clicks": counts.get("service_click", 0),
                              "fans": counts.get("email_capture", 0)
                                      + counts.get("presave_notify", 0),
                              "eff_status": links_engine.effective_status(c)})
        campaigns.sort(key=lambda c: c["visits"], reverse=True)
        return render_template(
            "report_executive.html",
            user=user, summary=cc.get_summary(user["id"]),
            q=qualification.calculate(user["id"]),
            rr=build_royalty_summary(store.get_statement_rows(user["id"])),
            campaigns=campaigns,
            fans=mls.list_fans(user["id"]),
            today=datetime.now(timezone.utc).strftime("%B %d, %Y"))

    UPLOADS_DIR = os.path.join(os.path.dirname(store.db_path()), "uploads")
    try:
        os.makedirs(UPLOADS_DIR, exist_ok=True)
    except OSError:
        # DATABASE_PATH points at an unmounted disk — degrade to the local
        # instance dir (ephemeral) instead of crashing the deploy.
        UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "instance", "uploads")
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        print("WARNING: uploads dir unusable; falling back to", UPLOADS_DIR)

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        from flask import send_from_directory
        # Vault and Deal Room documents (doc_*) belong to one account:
        # contracts, split agreements, licences. Everything else under
        # /uploads is a public asset by design (press photos, cover art,
        # link images, sync audio) and stays open. Walk, 2026-09-20: a
        # contract PDF was served to anyone who had its address.
        if filename.startswith("doc_"):
            user = current_user()
            if user is None:
                return login_required_redirect()
            if not store.document_path_owned("/uploads/" + filename, user["id"]):
                abort(404)
        return send_from_directory(UPLOADS_DIR, filename)

    def _slugify(name):
        s = "".join(c if c.isalnum() else "-" for c in (name or "").lower())
        return "-".join(p for p in s.split("-") if p) or "artist"

    def _ensure_epk_slug(user):
        """A kit's public address, minted once and never re-minted.

        The name in it is the act's, not the signup box's - the page it
        opens is headlined by the act. An existing slug is left exactly
        as it is: a press link that has been sent out must keep working.
        """
        saved = store.get_epk(user["id"])
        if saved and saved.get("slug"):
            return saved["slug"]
        act = artist_identity.display_name(user) or user["name"]
        slug = _slugify(act)
        while store.get_epk_by_slug(slug) is not None:
            slug = "%s-%s" % (_slugify(act), uuid.uuid4().hex[:4])
        store.set_epk_slug(user["id"], slug)
        return slug

    _EPK_ASSET_KINDS = [("press_photo", "Press Photo"), ("logo", "Logo"),
                        ("cover_art", "Cover Art"), ("live_photo", "Live Photo")]
    _EPK_KIND_LABELS = dict(_EPK_ASSET_KINDS)

    def _epk_tour_dates(user_id, overrides):
        """(rows, bandsintown_profile, source) for the kit's Tour Dates
        block. TOUR is the source whenever the artist holds a confirmed or
        advanced upcoming date there - their own word, first-hand. Only
        when TOUR has nothing do the Bandsintown rows answer, and those
        are empty while that provider is dormant (no app_id, 2026-09-07)."""
        rows = tour_dates_feed.epk_rows(user_id) if user_id else []
        if rows:
            return rows, None, "tour"
        name = (overrides or {}).get("bandsintown_artist")
        return (bandsintown.upcoming_events(name), bandsintown.artist_info(name),
                "bandsintown")

    def _labeled_assets(assets):
        return [{**a, "label": _EPK_KIND_LABELS.get(a["kind"], a["kind"])}
                for a in assets if a["kind"] in _EPK_KIND_LABELS]

    # A press kit saved to the Vault files under this kind (owner,
    # 2026-09-19: "The EPK goes to the vault"). Not in VAULT_KINDS: it is
    # written by /epk/vault-save, never chosen on the upload form.
    PRESS_KIT_KIND = "press_kit"

    def _saved_press_kits(user_id):
        """Every dated copy of the press kit in this artist's Vault,
        newest first, for the kit page, the tour advance and the pitch."""
        return [v for v in store.list_vault_files(user_id)
                if v["kind"] == PRESS_KIT_KIND]

    def _epk_kit_context(user):
        """Everything the press kit document renders from. One builder for
        the editor and for the copy saved to the Vault (2026-09-19), so a
        saved copy cannot differ from what the editor showed."""
        ctx = build_dashboard_context()
        overrides, photo, assets = None, None, []
        if user:
            saved = store.get_epk(user["id"])
            if saved:
                overrides, photo = saved["data"], saved["photo"]
            assets = _labeled_assets(store.get_epk_assets(user["id"]))
            ctx["epk_public_url"] = "/epk/" + _ensure_epk_slug(user)
        ctx["user"] = user
        tour, bit, tour_source = _epk_tour_dates(user["id"] if user else None,
                                                 overrides)
        ctx["tour_dates_count"] = len(tour) if tour_source == "tour" else 0
        ctx["epk"] = get_epk_data(_epk_account(ctx["account"], user),
                                  ctx["catalog_value"],
                                  overrides=overrides, photo=photo, assets=assets,
                                  tour_dates=tour, bandsintown_profile=bit,
                                  tour_source=tour_source,
                                  # A real account's editor shows what was
                                  # measured or "Not measured" - the sample
                                  # strip is the showcase's alone (2026-09-14).
                                  stats_override=(_epk_stats_for(user["id"], _is_demo_email(user["email"]))
                                                  if user else None),
                                  top_tracks_override=(_epk_real_tracks(user["id"])[0] if user and not _is_demo_email(user["email"]) else None),
                                  top_platform_override=(_epk_real_tracks(user["id"])[1] if user and not _is_demo_email(user["email"]) else None),
                                  demo=_is_demo_email(user["email"]))
        # The For deals section: what the Deal Room one-sheet carried
        # (owner, 2026-09-19: "It just needs to be an EPK"). Private: it
        # is never on the public slug or the pitch link, only on the
        # editor, the print and the saved copy.
        ctx["deal"] = _deal_facts(user["id"]) if user else None
        ctx["press_kits"] = _saved_press_kits(user["id"]) if user else []
        return ctx

    @app.route("/epk")
    def epk():
        user = current_user()
        ctx = _epk_kit_context(user)
        ctx["asset_kinds"] = _EPK_ASSET_KINDS
        share = store.get_epk_share(user["id"]) if user else None
        ctx["pitch_share"] = share
        ctx["pitch_stats"] = (store.epk_share_stats(share["token"])
                              if share else {"views": 0, "plays": [],
                                             "last_view": ""})
        vault = store.list_vault_files(user["id"]) if user else []
        ctx["vault_audio"] = [v for v in vault
                              if v["path"].rsplit(".", 1)[-1].lower()
                              in ("wav", "mp3", "flac")]
        ctx["vault_images"] = [v for v in vault
                               if v["path"].rsplit(".", 1)[-1].lower()
                               in ("png", "jpg", "jpeg", "webp")]
        ctx["just_saved"] = request.args.get("saved") or ""
        return render_template("epk.html", active_page="press-desk", **ctx)

    def _inline_image(path):
        """A local photo as a data URI, so the saved copy carries it and
        opens the same off this server; anything else (an object-store
        path, a missing file) stays an absolute address."""
        if path and path.startswith("/uploads/") and not blob_store.is_remote(path):
            try:
                local = blob_store.safe_local_path(path, UPLOADS_DIR)
                with open(local, "rb") as fh:
                    data = fh.read()
                if len(data) <= 2 * 1024 * 1024:
                    import base64
                    import mimetypes
                    mime = mimetypes.guess_type(local)[0] or "image/jpeg"
                    return "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))
            except (OSError, ValueError):
                pass
        if not path:
            return ""
        url = blob_store.url_for(path)
        return url if url.startswith("http") else request.url_root.rstrip("/") + url

    @app.route("/epk/vault-save", methods=["POST"])
    def epk_vault_save():
        """Save to Vault: the press kit as it stands, rendered as one
        self-contained web page and filed in the Vault as a new dated
        version (owner, 2026-09-19: "The EPK goes to the vault. And then
        from the vault you can send and attach it to the advance or mail
        it out to press... download it"). A web page, not a PDF: this
        server has no PDF engine (nothing in requirements.txt renders
        one), and the page says so rather than naming a format it cannot
        make. The saved page prints to PDF from any browser."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        ctx = _epk_kit_context(user)
        stamp = datetime.now(timezone.utc)
        # The same document partial the editor renders, with the photo
        # and logo carried inside the file and every other asset given
        # its absolute address, so the page opens the same anywhere.
        e = dict(ctx["epk"])
        e["photo"] = _inline_image(e.get("photo"))
        e["logo_path"] = _inline_image(e.get("logo_path"))
        base = request.url_root.rstrip("/")
        e["assets"] = [{**a, "path": (a["path"] if blob_store.url_for(a["path"]).startswith("http")
                                      else base + blob_store.url_for(a["path"]))}
                       for a in (e.get("assets") or [])]
        try:
            with open(os.path.join(app.static_folder, "css", "tailwind.css"),
                      encoding="utf-8") as fh:
                css = fh.read()
        except OSError:
            css = ""
        html = render_template("epk_saved.html", e=e, deal=ctx["deal"], css=css,
                               saved_on=stamp.strftime("%Y-%m-%d %H:%M UTC"),
                               base=base,
                               public_url=ctx.get("epk_public_url") or "")
        fname = "presskit_%s_%d.html" % (user["id"], int(stamp.timestamp() * 1000))
        path = blob_store.save(fname, html.encode("utf-8"),
                               content_type="text/html; charset=utf-8",
                               uploads_dir=UPLOADS_DIR)
        file_id = store.add_vault_file(
            user["id"], path, "Press kit, saved %s" % stamp.date().isoformat(),
            PRESS_KIT_KIND)
        return redirect("/epk?saved=" + file_id)

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

    @app.route("/epk/asset/<kind>/delete", methods=["POST"])
    def epk_asset_delete(kind):
        """Remove an asset slot, and the file behind it when this route
        wrote it.

        Hidden was never gone: `visibility` only unsets `public`, so a
        press photo an artist wanted rid of stayed in the row and stayed
        on disk forever. This deletes both.

        The unlink is deliberately narrow, the same rule /vault/<id>/delete
        uses: only a basename this uploader writes -
        `epkasset_<user>_<kind>.<ext>` - is removed. An asset pointed at a
        Vault image by /epk/asset/<kind>/from-vault shares that file with
        the Vault, which still lists and owns it, so clearing the EPK slot
        must leave the file exactly where it is.
        """
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        if kind not in _EPK_KIND_LABELS:
            return jsonify({"ok": False, "error": "Unknown asset type."}), 400
        path = store.delete_epk_asset(user["id"], kind)
        removed_file = False
        if path and os.path.basename(path.split("?")[0]).startswith(
                "epkasset_%s_%s." % (user["id"], kind)):
            removed_file = blob_store.remove(path, uploads_dir=UPLOADS_DIR)
        # An empty slot answers ok. Nothing was there to remove, which is
        # the state the caller asked for.
        return jsonify({"ok": True, "removed": bool(path), "file": removed_file})

    # --- Audience metrics through the provider registry ----------------------
    #
    # Artist Pulse read Spotify's own Web API directly, so the one number
    # a label asks for first - monthly listeners - was not on the page at
    # all: Spotify's public API does not carry it. A provider that does
    # (Soundcharts, today) answers CAP_METRICS through the registry, and
    # its figures are stored as provider-stamped snapshots beside the
    # Spotify ones rather than replacing them.

    _METRICS_WINDOW_DAYS = 30

    # What /pulse?yt=... means. Anything not in here is Google's own error
    # text, passed through as it stands rather than flattened to "failed".
    _YT_ERRORS = {
        "": "",
        "notfound": ("No YouTube channel matched that. The surest form is the "
                     "channel's own URL, copied from YouTube."),
        "unconfigured": ("This server has no YouTube key, so nothing was looked "
                         "up."),
    }

    def _metrics_provider():
        """The registry's REAL metrics provider, or None.

        `for_capability` answers with the mock while nothing real is
        configured. A real artist's name beside invented listener counts
        is the fabrication this product refuses everywhere else, so the
        mock is not accepted here: no provider means "Not measured".
        """
        import signal_providers as sp
        reg = sp.registry()
        prov = reg.for_capability(sp.CAP_METRICS)
        return None if prov is None or prov is reg.mock else prov

    def _metrics_artist_id(prov, user_id, profile):
        """The provider's own id for this artist: read from the pulse
        profile, or resolved once by search and stored there.

        Searching on every page load would spend a billed call to learn
        what the last one already established.
        """
        if profile.get("provider") == prov.key and profile.get("provider_artist_id"):
            return profile["provider_artist_id"]
        try:
            found = prov.search_artists(profile.get("artist_name") or "", limit=1)
        except Exception:
            return ""                # a provider that is down is not an answer
        pid = (found[0].get("provider_artist_id") or "") if found else ""
        if pid:
            store.save_pulse_provider_artist(user_id, prov.key, pid)
        return pid

    # --- YouTube, as a public read ------------------------------------------
    # A second, unrelated source beside the metrics provider: the owner names
    # a channel and YouTube reports its current subscriber and view totals.
    # There is no history in the public API, so there is no line for it on
    # the graph - only two windows and the age of the reading.

    def _youtube_adapter():
        """The YouTube adapter itself, configured or not.

        Deliberately NOT registry().for_capability(CAP_SOCIAL). The two
        windows say "measured by YouTube", so they come from YouTube or
        from nowhere; another social provider's counts are not YouTube
        subscribers, and the registry may well be preferring one.
        """
        import signal_providers as sp
        for p in sp.registry().all_providers():
            if isinstance(p, sp.YouTubeAdapter):
                return p
        return None

    def _youtube_pulse(user_id, profile, error=""):
        """The whole state of the YouTube panel, in every case.

        None only when this build carries no YouTube adapter at all.
        Otherwise the dict always renders, because "not measured" is a
        state that has to be shown: `configured` says whether the server
        has the key and `missing` names what it lacks, `channel_id` says
        whether the OWNER has named a channel, and the counts are None -
        "Not measured" - until both are true and YouTube answered.

        Nothing here guesses a channel from the artist name. A channel
        that merely shares a name is somebody else's audience, so the
        owner types the handle or URL and the panel prints back the title
        YouTube returned for it.
        """
        prov = _youtube_adapter()
        if prov is None or not profile:
            return None
        out = {"configured": prov.configured(), "missing": prov.missing_env(),
               "channel_id": profile.get("youtube_channel_id") or "",
               "subscribers": None, "views": None, "videos": None,
               "hidden": False, "channel_title": "", "channel_url": "",
               "started": "", "country": "", "uploads": [],
               "cached_hours": None, "note": "", "error": error}
        if not out["configured"]:
            out["note"] = ("This server has no YouTube key yet, so nothing here is "
                           "measured. Missing: %s." % ", ".join(out["missing"]))
            return out
        if not out["channel_id"]:
            out["note"] = ("Name your channel below and these read live. Nothing "
                           "is fetched from YouTube until you do.")
            return out
        try:
            social = prov.get_social(out["channel_id"])
        except Exception as e:                                  # noqa: BLE001
            out["note"] = ("YouTube did not answer just now (%s), so these stay "
                           "unmeasured." % prov.redact(e))
            return out
        if not social:
            out["note"] = ("YouTube no longer has a channel with that id. Set it "
                           "again below.")
            return out
        for k in ("subscribers", "views", "videos", "hidden",
                  "channel_title", "channel_url", "started", "country"):
            out[k] = social.get(k) if k in ("started", "country") else social[k]
        # The latest uploads: a bonus, never the whole panel. A failure
        # here leaves the channel's own counters standing.
        try:
            out["uploads"] = prov.get_recent_videos(out["channel_id"])
        except Exception:                                       # noqa: BLE001
            out["uploads"] = []
        hours = int((datetime.now(timezone.utc)
                     - social["measured_at"]).total_seconds() // 3600)
        out["cached_hours"] = hours
        when = ("less than an hour ago" if hours < 1 else
                "1 hour ago" if hours == 1 else "%d hours ago" % hours)
        out["note"] = "Measured by YouTube, %s." % when
        if out["hidden"]:
            out["note"] += (" This channel hides its subscriber count, so YouTube "
                            "does not report one.")
        return out

    def _provider_metrics(user_id, profile, fetch=True):
        """Followers and monthly listeners from the metrics provider.

        Returns None when no real provider covers CAP_METRICS, or when it
        holds nothing for this artist - never a placeholder number.
        `fetch=False` reads only what is already stored, which is what a
        public press kit does: a stranger opening a pitch link must not
        spend the artist's provider quota.
        """
        prov = _metrics_provider()
        if prov is None or not profile:
            return None
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=_METRICS_WINDOW_DAYS)
        pid = ""
        refusal = ""
        if fetch:
            pid = _metrics_artist_id(prov, user_id, profile)
            if pid:
                try:
                    rows = prov.get_artist_metrics(pid, start, end)
                except Exception as e:
                    # Kept, not swallowed. Falling back to what is stored is
                    # right; presenting it as a fresh reading is not, and
                    # that is what the note used to do.
                    rows = []
                    refusal = str(e).strip() or "%s did not answer." % prov.label
                by_day = {}
                for r in rows:
                    by_day.setdefault(r["date"], {})[r["metric"]] = r["value"]
                for day, vals in by_day.items():
                    # None, not nought, for anything this provider did not
                    # report. It measures listening; it says nothing about
                    # Deezer, and writing 0 there claims a following of
                    # nobody. The columns are nullable for exactly this.
                    store.record_pulse_snapshot(
                        user_id, vals.get("spotify_followers"),
                        vals.get("spotify_popularity"), None,
                        provider=prov.key, day=day,
                        monthly_listeners=vals.get("spotify_monthly_listeners"))
        snaps = store.list_pulse_snapshots(user_id, limit=_METRICS_WINDOW_DAYS + 5,
                                           provider=prov.key)
        if not snaps:
            return None
        latest = snaps[-1]
        listeners = next((s["monthly_listeners"] for s in reversed(snaps)
                          if s["monthly_listeners"] is not None), None)
        followers = next((s["followers"] for s in reversed(snaps)
                          if s["followers"] is not None), None)
        hours = None
        cached_at = getattr(prov, "metrics_cached_at", None)
        if pid and cached_at is not None:
            try:
                at = cached_at(pid, start, end)
            except Exception:
                at = None
            if at is not None:
                hours = int((datetime.now(timezone.utc) - at).total_seconds() // 3600)
        if refusal:
            # The vendor's own words, and the age of what is on screen.
            # Anything softer invites the figure to be read as current.
            note = ("%s did not answer just now (%s). These are the last "
                    "figures on file, from %s - not a reading taken today."
                    % (prov.label, refusal, latest["day"]))
        elif hours is None:
            note = "Measured by %s; the snapshot on file is from %s." % (
                prov.label, latest["day"])
        elif hours < 1:
            note = "Measured by %s, less than an hour ago." % prov.label
        elif hours == 1:
            note = "Measured by %s, 1 hour ago." % prov.label
        else:
            note = "Measured by %s, %d hours ago." % (prov.label, hours)
        return {"provider": prov.key, "label": prov.label,
                "monthly_listeners": listeners, "followers": followers,
                "as_of": latest["day"], "cached_hours": hours,
                "stale": bool(refusal), "refusal": refusal,
                "snapshots": snaps, "note": note}

    def _epk_real_tracks(user_id):
        """(top tracks, strongest store) from the account's own statements,
        for all three doors of the kit. Empty with nothing on file."""
        try:
            return epk_config.real_top_tracks(store.get_statement_rows(user_id))
        except Exception:
            return [], ""

    def _epk_stats_for(user_id, demo):
        """The kit's headline strip: measured figures, or "Not measured" in
        every slot. Only the showcase keeps its sample strip."""
        real = _epk_real_stats(user_id)
        return real or (None if demo else epk_config.not_measured_stats())

    def _epk_real_stats(user_id):
        """Headline figures for a press kit, from the artist's own data.

        One helper for all three doors - the editor, the public slug and
        the private pitch link. Two of them used to pass nothing, so the
        demo catalogue's four numbers rendered on a page that goes to a
        label, over the artist's name.

        Audience comes from whatever the registry has for CAP_METRICS,
        read from the snapshots Artist Pulse already stored: a stranger
        opening a pitch link must not spend the artist's provider quota,
        and a kit is not the place to discover a vendor is down.

        Returns [] when there is nothing real to show.
        """
        try:
            metrics = _provider_metrics(user_id, store.get_pulse_profile(user_id),
                                        fetch=False)
            return epk_config.real_stats(
                store.get_statement_rows(user_id),
                len(store.get_catalog_tracks(user_id) or []),
                metrics=metrics)
        except Exception:
            return []

    def _epk_store(kit_owner):
        """The Buy Button store embed for a press kit, or None.

        The embed is the server's own Shopify store (SHOPIFY_DOMAIN and the
        collection in Render), which is the owner's. It was passed to every
        press kit, so every artist's public EPK showed the owner's store
        under the heading Merch, as if it were theirs (found by the
        2026-09-18 launch check). Only the owner's own kit and the demo
        showcase carry it now; every other artist shows their own store
        link and merch items, which they set on their EPK."""
        email = (kit_owner or {}).get("email") or ""
        if _is_owner_email(email) or _is_demo_email(email):
            return shopify_buy.context()
        return None

    @app.route("/epk/<slug>")
    def epk_public(slug):
        prof = store.get_epk_by_slug(slug)
        if prof is None:
            abort(404)
        ctx = build_dashboard_context()
        name = prof["user_name"]
        initials = "".join(w[0] for w in name.split()[:2]).upper() or "SB"
        assets = _labeled_assets(store.get_epk_assets(prof["user_id"], public_only=True))
        tour, bit, tour_source = _epk_tour_dates(prof["user_id"], prof["data"])
        real = _epk_real_stats(prof["user_id"])
        _demo_owner = _is_demo_email((store.get_user(prof["user_id"]) or {})
                                     .get("email") or "")
        data = get_epk_data({"name": name, "initials": initials},
                            ctx["catalog_value"],
                            overrides=prof["data"], photo=prof["photo"],
                            assets=assets, tour_dates=tour, bandsintown_profile=bit,
                            tour_source=tour_source,
                            # Whose kit this is decides whose defaults
                            # apply - a real artist's public EPK must
                            # never fall back to the showcase identity.
                            demo=_demo_owner,
                            # The public slug follows the same rule as the
                            # private pitch link (owner ruling, 2026-09-09):
                            # a real account shows what was measured, or
                            # says "Not measured" in every slot - never the
                            # demo catalogue's totals standing over this
                            # artist's name on a page that leaves the
                            # building. The showcase keeps its sample strip,
                            # which the page labels as samples.
                            stats_override=(real or (None if _demo_owner
                                                     else epk_config.not_measured_stats())),
                            top_tracks_override=(None if _demo_owner else _epk_real_tracks(prof["user_id"])[0]),
                            top_platform_override=(None if _demo_owner else _epk_real_tracks(prof["user_id"])[1]))
        return render_template("epk_public.html", e=data, slug=slug,
                               shopify=_epk_store(store.get_user(prof["user_id"])))

    @app.route("/epk/share", methods=["POST"])
    def epk_share_save():
        """Private pitch link settings — audio resolves through the artist's
        own vault listing, same rule as every other share surface."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        action = request.form.get("action") or "save"
        if action == "disable":
            store.delete_epk_share(user["id"])
            return redirect("/epk")
        share = store.get_epk_share(user["id"])
        token = (uuid.uuid4().hex[:20]
                 if (share is None or action == "regenerate")
                 else share["token"])
        pin = "".join(ch for ch in (request.form.get("pin") or "")
                      if ch.isdigit())[:8]
        if pin and len(pin) < 4:
            pin = ""
        expires = (request.form.get("expires") or "").strip()[:10]
        vault = {v["id"]: v for v in store.list_vault_files(user["id"])}
        audio = []
        for vid in request.form.getlist("audio")[:3]:
            v = vault.get(vid)
            if v and v["path"].rsplit(".", 1)[-1].lower() in ("wav", "mp3",
                                                              "flac"):
                audio.append({"path": v["path"],
                              "label": v["label"] or "Untitled"})
        store.upsert_epk_share(user["id"], token, pin, expires, audio)
        return redirect("/epk")

    @app.route("/pitch/<token>", methods=["GET", "POST"])
    def epk_pitch(token):
        share = store.get_epk_share_by_token(token)
        if share is None:
            abort(404)
        today = datetime.now(timezone.utc).date().isoformat()
        if share["expires"] and today > share["expires"]:
            return render_template("link_campaign_unavailable.html"), 410
        pin_key = "pitch_ok_" + token
        prof = store.get_epk(share["user_id"])
        owner = store.get_user(share["user_id"])
        if share["pin"] and not session.get(pin_key):
            if request.method == "POST":
                if (request.form.get("pin") or "").strip() == share["pin"]:
                    session[pin_key] = True
                    return redirect("/pitch/" + token)
                return render_template("sheet_public.html", mode="pin",
                                       token=token, bad_pin=True,
                                       gate_title="Private Press Kit",
                                       artist=(owner or {}).get("name", "")), 403
            return render_template("sheet_public.html", mode="pin",
                                   token=token, bad_pin=False,
                                   gate_title="Private Press Kit",
                                   artist=(owner or {}).get("name", ""))
        slug = (prof or {}).get("slug") or _ensure_epk_slug(owner)
        ctx = build_dashboard_context()
        _acct = _epk_account({"name": (owner or {}).get("name", "Artist")}, owner)
        name = _acct["name"] or "Artist"
        initials = "".join(w[0] for w in name.split()[:2]).upper() or "SB"
        assets = _labeled_assets(store.get_epk_assets(share["user_id"],
                                                      public_only=True))
        tour, bit, tour_source = _epk_tour_dates(share["user_id"],
                                                 (prof or {}).get("data"))
        _demo_owner = _is_demo_email((owner or {}).get("email") or "")
        data = get_epk_data({"name": name, "initials": initials},
                            ctx["catalog_value"],
                            overrides=(prof or {}).get("data"),
                            photo=(prof or {}).get("photo"),
                            assets=assets, tour_dates=tour, bandsintown_profile=bit,
                            tour_source=tour_source,
                            # A private pitch link is not a showcase: it
                            # goes to one named person who asked for it,
                            # so sample totals there read as this
                            # artist's. With nothing measured the strip
                            # says "Not measured" in every slot instead.
                            stats_override=(_epk_real_stats(share["user_id"])
                                            or (None if _demo_owner
                                                else epk_config.not_measured_stats())),
                            top_tracks_override=(None if _demo_owner else _epk_real_tracks(share["user_id"])[0]),
                            top_platform_override=(None if _demo_owner else _epk_real_tracks(share["user_id"])[1]),
                            demo=_demo_owner)
        viewer = current_user()
        if viewer is None or viewer["id"] != share["user_id"]:
            first_today = not store.epk_viewed_today(token, today)
            store.log_epk_event(token, "view")
            if first_today:
                store.notify(share["user_id"], "pitch",
                             "Your pitch EPK was opened",
                             "First open today on the private link. "
                             "Play counts land on the EPK editor.", "/epk")
        return render_template("epk_public.html", e=data, slug=slug, shopify=_epk_store(owner),
                               pitch_token=token,
                               pitch_audio=share["audio"])

    @app.route("/pitch/<token>/play", methods=["POST"])
    def epk_pitch_play(token):
        share = store.get_epk_share_by_token(token)
        if share is None:
            abort(404)
        label = ((request.get_json(silent=True) or {}).get("label") or "")[:120]
        if label in [a["label"] for a in share["audio"]]:
            store.log_epk_event(token, "play", label)
            return jsonify({"ok": True})
        return jsonify({"ok": False}), 400

    @app.route("/epk/asset/<kind>/from-vault", methods=["POST"])
    def epk_asset_from_vault(kind):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        if kind not in _EPK_KIND_LABELS:
            return jsonify({"ok": False, "error": "Unknown asset type."}), 400
        vid = (request.get_json(silent=True) or {}).get("vault_id") or ""
        v = next((v for v in store.list_vault_files(user["id"])
                  if v["id"] == vid), None)
        if v is None or v["path"].rsplit(".", 1)[-1].lower() not in (
                "png", "jpg", "jpeg", "webp"):
            return jsonify({"ok": False, "error": "Pick an image from your "
                            "own Vault."}), 400
        store.save_epk_asset(user["id"], kind, v["path"])
        return jsonify({"ok": True, "path": v["path"]})

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
                name = os.path.basename(a["path"].split("?")[0])
                ext = name.rsplit(".", 1)[-1]
                arc = "%s-%s.%s" % (slug, a["kind"].replace("_", "-"), ext)
                if blob_store.is_remote(a["path"]):
                    blob = blob_store.fetch(a["path"])
                    if blob is not None:
                        zf.writestr(arc, blob)
                        added += 1   # a kit held in the object store counted as empty (walk, 2026-09-20)
                    continue
                fpath = os.path.join(UPLOADS_DIR, name)
                if os.path.exists(fpath):
                    zf.write(fpath, arc)
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

    def _store_epk_photo(user, f):
        """The one artist-photo uploader: /epk/photo and the collaborator
        profile's photo form both write through here, so a member has one
        photo. Returns (path, error)."""
        if f is None or not f.filename:
            return None, "Choose an image file."
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("png", "jpg", "jpeg", "webp"):
            return None, "Use a PNG, JPG, or WebP image."
        fname = "epk_%s.%s" % (user["id"], ext)
        f.save(os.path.join(UPLOADS_DIR, fname))
        photo_path = "/uploads/" + fname
        store.save_epk_photo(user["id"], photo_path)
        return photo_path, None

    @app.route("/epk/photo", methods=["POST"])
    def epk_photo():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in to upload a photo."}), 401
        photo_path, error = _store_epk_photo(user, request.files.get("photo"))
        if error:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True, "photo": photo_path})

    @app.route("/epk/photo/delete", methods=["POST"])
    def epk_photo_delete():
        """Remove the artist photo, and the file /epk/photo wrote for it.

        Same narrow unlink as the asset route: only `epk_<user>.<ext>`,
        the one name this uploader produces.
        """
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        path = store.delete_epk_photo(user["id"])
        removed_file = False
        if path and os.path.basename(path.split("?")[0]).startswith(
                "epk_%s." % user["id"]):
            removed_file = blob_store.remove(path, uploads_dir=UPLOADS_DIR)
        return jsonify({"ok": True, "removed": bool(path), "file": removed_file})

    @app.route("/epk/delete", methods=["POST"])
    def epk_delete():
        """Take the whole press kit down.

        Every piece could already be cleared on its own - the photo, one
        asset slot, the share link - and the kit itself could not, so an
        artist who wanted to start again had to empty it field by field
        and still keep the slug and the share token they were trying to
        be rid of.

        The unlink is the same narrow rule the two single-item routes
        use, applied per file: only names this app wrote - `epk_<user>.`
        for the photo and `epkasset_<user>_<kind>.` for a slot - are
        removed. An asset pointed at a Vault image shares that file with
        the Vault, which still lists and owns it, so it must stay exactly
        where it is.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        paths = store.delete_epk(user["id"])
        ours = ("epk_%s." % user["id"], "epkasset_%s_" % user["id"])
        for path in paths:
            name = os.path.basename((path or "").split("?")[0])
            if name.startswith(ours):
                try:
                    blob_store.remove(path, uploads_dir=UPLOADS_DIR)
                except Exception:
                    # A file already gone is the state we were after.
                    pass
        return redirect("/epk")

    @app.route("/epk/export", methods=["POST"])
    def epk_export():
        ctx = build_dashboard_context()
        user = current_user()
        data = get_epk_data(
            _epk_account(ctx["account"], user), ctx["catalog_value"],
            demo=_is_demo_email((user or {}).get("email") or ""))
        slug = data["name"].lower().replace(" ", "-")
        filename = f"{slug}-press-kit-{datetime.today().strftime('%Y%m%d')}.pdf"
        return jsonify({"ok": True, "filename": filename})

    @app.route("/artwork")
    def artwork():
        ctx = build_dashboard_context()
        ctx["artwork"] = get_artwork_data(ctx["account"])
        # What this studio has already written to the disk, so it can be
        # taken back off it. Signed out, there is nothing to list.
        user = current_user()
        ctx["art_uploads"] = (list_artwork_uploads(user["id"], UPLOADS_DIR)
                              if user else [])
        return render_template("artwork.html", active_page="artwork", **ctx)

    @app.route("/artwork/generate", methods=["POST"])
    def artwork_generate():
        payload = request.get_json(silent=True) or {}
        prompt = (payload.get("prompt") or "").strip()[:300]
        suggestion = suggest_from_prompt(prompt)
        image_url, seed = None, None
        if prompt:
            # Real AI image via Pollinations.ai — free community model, no key.
            # The browser loads the URL directly so slow generations never
            # tie up a server worker. A remix reuses the seed so the model
            # re-imagines the same concept with the requested changes.
            import random
            try:
                seed = int(payload.get("seed"))
            except (TypeError, ValueError):
                seed = random.randint(1, 10 ** 9)
            image_url = ("https://image.pollinations.ai/prompt/"
                         + urllib.parse.quote(prompt + ", album cover art, square, "
                                              "no text, high detail")
                         + "?width=1024&height=1024&nologo=true&seed=%d" % seed)
        return jsonify({"ok": True, "suggestion": suggestion,
                        "image_url": image_url, "seed": seed})

    @app.route("/artwork/upload", methods=["POST"])
    def artwork_upload():
        """Bring your own cover art into the designer."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in to upload artwork."}), 401
        f = request.files.get("art")
        if f is None or not f.filename:
            return jsonify({"ok": False, "error": "Choose an image file."}), 400
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in ("png", "jpg", "jpeg", "webp"):
            return jsonify({"ok": False, "error": "Use a PNG, JPG, or WebP image."}), 400
        fname = "artup_%s_%d.%s" % (user["id"],
                                    int(datetime.now(timezone.utc).timestamp()), ext)
        f.save(os.path.join(UPLOADS_DIR, fname))
        return jsonify({"ok": True, "path": "/uploads/" + fname})

    @app.route("/artwork/save", methods=["POST"])
    def artwork_save():
        """Pull a generated image into the user's uploads so it can be used
        as campaign cover art or an EPK asset."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in to save artwork."}), 401
        payload = request.get_json(silent=True) or {}
        url = (payload.get("url") or "").strip()
        if not url.startswith("https://image.pollinations.ai/"):
            return jsonify({"ok": False, "error": "Only generated images can be saved."}), 400
        try:
            data = music_apis.fetch_image_bytes(url)
        except Exception:
            return jsonify({"ok": False, "error": "Couldn't download the image — "
                                                  "generate it again and retry."}), 502
        if not data or len(data) > 8 * 1024 * 1024:
            return jsonify({"ok": False, "error": "Image missing or too large."}), 400
        fname = "aiart_%s_%d.jpg" % (user["id"], int(datetime.now(timezone.utc).timestamp()))
        with open(os.path.join(UPLOADS_DIR, fname), "wb") as f:
            f.write(data)
        return jsonify({"ok": True, "path": "/uploads/" + fname})

    @app.route("/artwork/upload/delete", methods=["POST"])
    def artwork_upload_delete():
        """Take one studio file back off the disk.

        /artwork/upload and /artwork/save each wrote a file and recorded
        nothing, so every second idea orphaned the first one permanently.
        This is the way back, and the Cover Studio now lists what it has
        written so there is something to point it at.

        Ownership and the unlink are one check, the rule /vault/<id>/delete
        established: only a basename this studio writes for THIS artist -
        `artup_<user>_` or `aiart_<user>_` - can be named at all. Another
        account's file cannot be addressed, so the answer is 404 rather
        than a refusal that confirms whose it is.

        A finished cover saved through "Save cover to uploads" is a Vault
        file (`vault_<user>_<ms>`), owned and listed by the Vault. It is
        not offered here and cannot be reached from here.
        """
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        name = (request.get_json(silent=True) or {}).get("name") or ""
        if not os.path.basename(name.split("?")[0]).startswith(
                artwork_upload_prefixes(user["id"])):
            abort(404)
        path = take_artwork_upload(user["id"], name, UPLOADS_DIR)
        # A name of theirs with no file behind it is a no-op, not an
        # error: already gone is the state the caller asked for.
        removed_file = False
        if path and os.path.basename(path).startswith(
                artwork_upload_prefixes(user["id"])):
            removed_file = blob_store.remove(path, uploads_dir=UPLOADS_DIR)
        return jsonify({"ok": True, "removed": bool(path), "file": removed_file})

    def _ml_campaign_card(c):
        counts = mls.event_counts(c["id"])
        visits = counts.get("page_view", 0)
        clicks = counts.get("service_click", 0)
        dests = mls.get_destinations(c["id"])
        score = links_engine.calculate_street_banker_score(c, dests)
        status = links_engine.effective_status(c)
        # 7-day sparkline: real page-view counts, missing days filled with 0.
        tl = dict(mls.timeline(c["id"], days=7))
        spark = [tl.get((date.today() - timedelta(days=i)).isoformat(), 0)
                 for i in range(6, -1, -1)]
        return {**c, "visits": visits, "clicks": clicks,
                "ctr": round(100 * clicks / visits, 1) if visits else 0.0,
                "captures": counts.get("email_capture", 0),
                "presaves": counts.get("presave_notify", 0),
                "score": score["total"], "warnings": score["warnings"],
                "eff_status": status, "spark": spark,
                "spark_max": max(spark) or 1,
                "status_tone": links_engine.STATUS_TONES.get(status, "gray"),
                "dest_count": len(dests)}

    @app.route("/links")
    def links():
        ctx = build_dashboard_context()
        user = current_user()
        ctx["links_data"] = get_links_data(
            demo=_is_demo_email((user or {}).get("email") or ""))
        # Real, persisted links with genuine click counts sit above the demo
        # set - this account's links, and only this account's.
        ctx["real_links"] = store.get_db_links(user["id"]) if user else []
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
            "gate_reward": (f.get("gate_reward") or "").strip()[:64],
            "gate_label": (f.get("gate_label") or "").strip()[:120],
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

    def _ml_drop_cover_file(old, new=""):
        """Unlink a cover file once nothing points at it any more.

        Every `_ml_cover_upload` writes a fresh UUID name, so replacing a
        cover used to leave the previous file on the disk permanently
        unreferenced - a new orphan for every re-upload.

        The unlink is the narrow one /vault/<id>/delete established: only
        `mlcover_<uuid>`, the name THIS uploader writes. A cover pointed
        at a Vault image, at a Cover Studio file, or at an external URL
        belongs to somebody else, so the campaign gives up the reference
        and the bytes stay exactly where they are.
        """
        if not old or old == new:
            return False
        if not os.path.basename(old.split("?")[0]).startswith("mlcover_"):
            return False
        return blob_store.remove(old, uploads_dir=UPLOADS_DIR)

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
                                       vault_files=store.list_vault_files(user["id"]),
                                       **build_dashboard_context())
            cid = mls.create_campaign(user["id"], _ml_slug(fields["title"]), fields)
            mls.set_destinations(cid, _ml_form_destinations())
            return redirect("/links/%s/edit" % cid)
        return render_template("links_builder.html", active_page="links",
                               c=None, destinations=[], engine=links_engine,
                               error=None,
                               vault_files=store.list_vault_files(user["id"]),
                               prefill_title=(request.args.get("title") or "")[:80],
                               rack_facts=(request.args.get("rack") or "")[:160],
                               **build_dashboard_context())

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
            was = campaign["cover_url"]
            fields = _ml_form_fields()
            mls.update_campaign(cid, campaign["user_id"], fields)
            # Replacing a cover is the common case and used to orphan the
            # file it replaced. The row is written first: nothing is
            # unlinked until the database no longer points at it.
            _ml_drop_cover_file(was, fields["cover_url"])
            mls.set_destinations(cid, _ml_form_destinations())
            campaign = mls.get_campaign(cid)
        dests = mls.get_destinations(cid)
        score = links_engine.calculate_street_banker_score(campaign, dests)
        return render_template("links_builder.html", active_page="links",
                               c=campaign, destinations=dests, engine=links_engine,
                               score=score, error=None,
                               vault_files=store.list_vault_files(campaign["user_id"]),
                               eff_status=links_engine.effective_status(campaign),
                               **build_dashboard_context())

    @app.route("/links/<cid>/cover/delete", methods=["POST"])
    def ml_cover_delete(cid):
        """Clear the campaign's cover art, and remove the file when it is
        this uploader's own.

        The builder could point the cover somewhere new; it could never
        point it at nothing. `_ml_owned` answers 404 for a campaign that
        is not this artist's, so a stranger learns nothing about it.
        """
        campaign, err = _ml_owned(cid)
        if err:
            return err
        was = mls.clear_campaign_cover(cid, campaign["user_id"])
        _ml_drop_cover_file(was)
        return redirect("/links/%s/edit" % cid)

    @app.route("/links/<cid>/publish", methods=["POST"])
    def ml_publish(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        mls.update_campaign(cid, campaign["user_id"],
                            {"status": "live", "published_at": store._now(),
                             "archived_at": None})
        store.notify(campaign["user_id"], "campaign",
                     "Campaign live: %s" % campaign["title"],
                     "Public page is up at /l/%s — start sharing variant links." % campaign["slug"],
                     "/l/" + campaign["slug"])
        return redirect("/links/%s/edit" % cid)

    @app.route("/links/<cid>/unpublish", methods=["POST"])
    def ml_unpublish(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        mls.update_campaign(cid, campaign["user_id"], {"status": "draft"})
        return redirect("/links/%s/edit" % cid)

    @app.route("/links/legacy/<slug>/delete", methods=["POST"])
    def legacy_link_delete(slug):
        """The older single-target smart links (/l/<slug>) listed on /links
        had no control at all. Scoped to the account in the DELETE."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_db_link(user["id"], slug)
        return redirect("/links")

    @app.route("/links/<cid>/archive", methods=["POST"])
    def ml_archive(cid):
        campaign, err = _ml_owned(cid)
        if err:
            return err
        mls.update_campaign(cid, campaign["user_id"],
                            {"status": "draft", "archived_at": store._now()})
        # Release Autopilot offers this too now; it sends the artist back
        # to the desk rather than to the links list. Only a local path is
        # honoured - never an address somebody else put in a form.
        nxt = request.form.get("next") or ""
        if nxt.startswith("/") and not nxt.startswith("//"):
            return redirect(nxt)
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
                                        dark="#1A1714", light=None)
        return Response(buf.getvalue(), mimetype="image/svg+xml")

    # --- Plan tiers + product worlds -------------------------------------------

    def _palette_for(user):
        """The palette's destinations for this account."""
        idx = hub_defs.command_index()
        plan = (user or {}).get("plan") or ""
        if plan != "fan":
            return idx
        allowed = {k for k, _h, _i, _l, _d in hub_defs.COMMUNITY_GROUP[1]}
        allowed |= set(hub_defs.FAN_ACCOUNT_KEYS)
        return [e for e in idx if e["key"] in allowed]

    @app.context_processor
    def inject_brand():
        """The tenant's brand, for every template, or None for our own.

        A context processor rather than a per-route argument: the wordmark
        renders in the shell, on the login page and in the manifest, and a
        route that forgot to pass it would quietly show the platform's name
        to a reseller's artist. There is no route to forget here.

        None means Street Banker's own, and the templates read it as that
        rather than as a missing value to paper over.
        """
        try:
            return {"brand": partner_store.branding(getattr(g, "partner", None))}
        except Exception:
            # A partner table mid-migration must not take every page down.
            return {"brand": None}

    # _signal_seat lived here until 2026-09-17. It decided whether the
    # Analytics room drew the Signal card; the card left the room, so the
    # question stopped being asked. Signal's own guard is unchanged:
    # signal_hub.require() runs before every handler.

    @app.context_processor
    def inject_the_door():
        """Whether a stranger can make an account, and the words to offer
        them either way.

        Owner, 2026-09-17: "i still want no sign ups until i say so keep
        that locked". The lock itself is _signup_open, and it holds: no
        route mints an account while the door is shut. What did not hold
        was the advertising. Twelve public pages and the footer said
        "Create an account", which sent a stranger to a page that told
        them no. The route was honest and the buttons were not.

        So every one of those buttons asks here instead of deciding for
        itself. Shut, they all offer an invitation; open, each keeps its
        own specific wording ("Create an account to build one" rather than
        one label pasted everywhere). Nothing needs a second edit on the
        day the owner opens sign-up.
        """
        shut = not _signup_open()

        def signup_cta(open_label="Create an account"):
            return "Ask for an invitation" if shut else open_label

        return {"signup_open": not shut, "signup_cta": signup_cta}

    @app.context_processor
    def inject_hub_context():
        # The Ecosystem Hub model: one source of truth (hubs.py) feeds the
        # sidebar and the /desk/<hub> landing pages.
        nav, label, community, account = (hub_defs.nav_hubs(), hub_defs.LABEL_GROUP,
                                          hub_defs.COMMUNITY_GROUP, hub_defs.ACCOUNT_GROUP)
        palette = _palette_for(current_user())
        # The owner's switchboard: a hidden page leaves the menu and the
        # palette for everyone but an owner, who keeps it badged Hidden.
        off = _page_hidden()
        me = current_user()
        page_hidden = set()
        if off:
            if me and _is_owner_email(me.get("email")):
                page_hidden = off
            else:
                nav = hub_defs.without(nav, off)
                label, community, account = (
                    (g_[0], [it for it in g_[1] if it[0] not in off])
                    for g_ in (label, community, account))
                palette = [e for e in palette if e["key"] not in off]
        if _demo_locked_account():
            # A shared demo hides the Sample pages and Billing. The
            # routes stay reachable; the sidebar and the palette do not
            # offer them.
            hidden = hub_defs.demo_hidden_keys()
            nav = hub_defs.without(nav, hidden)
            label, community, account = (
                (g_[0], [it for it in g_[1] if it[0] not in hidden])
                for g_ in (label, community, account))
            palette = [e for e in palette if e["key"] not in hidden]
        # A team seat sees only the rooms the artist opened to it.
        seat = (getattr(g, "_team_seat", None) or (None, None))[1] if session.get("team_as") else None
        shut_rooms = team_areas.hidden_page_keys(seat["areas"]) if seat else set()
        if shut_rooms:
            nav = hub_defs.without(nav, shut_rooms)
            palette = [e for e in palette if e["key"] not in shut_rooms]
        # The eight rooms (owner, 2026-09-15, by numbered mockup): the
        # same keys, addresses and switches as the hubs, laid out as rooms.
        # Staging first: on when NAV_ROOMS=1 or the owner switched it.
        rooms_nav = None
        if me and rooms.enabled() and (me.get("plan") or "artist") != "fan":
            is_owner = bool(_is_owner_email(me.get("email")))
            demo = bool(_demo_locked_account())
            granted = team_areas.parse(seat["areas"]) if seat else None
            rooms_nav = {"rooms": [r for r in rooms.build(me.get("plan") or "artist", is_owner, demo)
                                   if granted is None or r[0] in granted],
                         "top": [r for r in rooms.top_rows(is_owner, demo) if r[0] not in shut_rooms],
                         "account": rooms.account_rows(is_owner, demo),
                         "back": rooms.back_map()}
        return {"hubs_nav": nav, "hubs_label": label,
                "hubs_community": community,
                "hubs_account": account,
                "rooms_nav": rooms_nav,
                "tool_suites": hub_defs.tool_suites(),
                "suite_marks": hub_defs.SUITE_MARKS,
                "suites_pending": hub_defs.suites_pending(),
                # The same answer for a sidebar entry, asked by its address.
                "nav_lock": ((lambda href: "") if not me or _is_owner_email(me.get("email")) else (
                    lambda held: (lambda href: plans.nav_lock(me.get("plan") or "artist", href, held)))(
                        0 if (me.get("plan") or "") == "label" else store.credit_balances(me["id"])["total"])),
                # What this membership cannot open yet: strip key -> the word
                # the strip shows ("Pro", "Credits"). Empty when signed out.
                "suite_locks": ({} if not me or _is_owner_email(me.get("email")) else (lambda held: {
                    k: plans.suite_tag(k) for k in plans.SUITE_ACCESS
                    if not plans.suite_open(me.get("plan") or "artist", k, held)})(
                        0 if (me.get("plan") or "") == "label" else store.credit_balances(me["id"])["total"])),
                "page_hidden": page_hidden,
                "fan_account_keys": hub_defs.FAN_ACCOUNT_KEYS,
                "hub_icons": hub_defs.HUB_ICONS,
                # Flag-aware: a page whose engine is on must not be
                # badged "example data, not yours".
                "live_keys": hub_defs.live_keys(),
                # One flat list for the command palette, derived from the
                # same definitions - so it cannot list a page the nav has
                # dropped, or miss one the nav has gained. Filtered to the
                # SAME shell the sidebar shows: a fan account must not be
                # offered artist tooling it would only be refused at, and
                # the whole point of the fan shell is that those pages are
                # not part of their world.
                "command_index": palette}

    @app.route("/room/<room_key>")
    def room_screen(room_key):
        """A room's screen: what it is for, then a card per feature
        (owner, 2026-09-15, mockup 3). Rooms exist whether or not the
        sidebar shows them, so a link to one never dies with the layout."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        is_owner = bool(_is_owner_email(user.get("email")))
        room = rooms.get_room(room_key, user.get("plan") or "artist", is_owner,
                              bool(_demo_locked_account()))
        if room is None:
            abort(404)
        if room_key == "fans":
            return _fan_room(user, room)
        return render_template("room.html", active_page="room-" + room_key,
                               room=room, room_images=rooms.images(),
                               **build_dashboard_context())

    def _fan_room_rows(user):
        """The fans this screen reads: the account's own, or the labelled
        example for the demo, the same split the Audience screen makes."""
        import fan_audience
        if _session_is_demo():
            return fan_audience.showcase_rows(), fan_audience.showcase(), True
        return (mls.list_fans(user["id"]),
                fan_audience.for_account(user["id"], resend_configured=emailer.configured()),
                False)

    def _fan_room(user, room):
        """The Fans room's opening screen, the owner's mockup (2026-09-19).
        fan_room.py says where each figure comes from."""
        import fan_audience
        import fan_room
        rows, audience, showcase = _fan_room_rows(user)
        club_row = None if showcase else store.get_fan_club(user["id"])
        members = 0
        if club_row:
            members = sum(1 for m in store.list_club_members(user["id"])
                          if (m.get("status") or "active") == "active")
        today = datetime.now(timezone.utc).date().isoformat()
        with store.get_db() as db:
            open_briefs = db.execute(
                "SELECT COUNT(*) FROM collab_requests c JOIN users u ON u.id = c.user_id"
                " WHERE c.status = 'open' AND (c.closes IS NULL OR c.closes = ''"
                " OR substr(c.closes, 1, 10) >= ?)", (today,)).fetchone()[0]
        fr = fan_room.build(rows, audience, room["cards"], days=request.args.get("days"),
                            club={"on": bool(club_row), "members": members},
                            open_briefs=open_briefs,
                            link_visits=0 if showcase else fan_audience._visits(user["id"]),
                            showcase=showcase, artist_name=user.get("name") or "")
        return render_template("room_fans.html", active_page="room-fans", room=room, fr=fr,
                               **build_dashboard_context())

    @app.route("/room/fans/new.csv")
    def fan_room_new_csv():
        """The "Get their emails" move: the contactable fans who joined
        through a link in the chosen window, as a CSV."""
        import fan_room
        user = current_user()
        if user is None:
            return login_required_redirect()
        rows, _audience, _showcase = _fan_room_rows(user)
        days = fan_room.days_from(request.args.get("days"))
        body = fan_room.new_fans_csv(rows, days, datetime.now(timezone.utc).date())
        return Response(body, mimetype="text/csv", headers={
            "Content-Disposition": "attachment; filename=street-banker-new-fans-%dd.csv" % days})

    @app.route("/admin/nav-layout", methods=["POST"])
    def admin_nav_layout():
        """The owner's choice of sidebar: rooms or hubs, for everybody,
        on the next request. Owner only, 404 to everybody else."""
        _user, bail = _owner_or_404()
        if bail:
            return bail
        rooms.set_layout(request.form.get("layout") or "hubs")
        return redirect("/settings?nav=saved#nav-layout")

    @app.route("/admin/home-layout", methods=["POST"])
    def admin_home_layout():
        """The owner's choice of front page: the long homepage, or the
        split one for after the story moves to the store. Owner only,
        404 to everybody else, and flippable both ways while looking at
        the page rather than through a redeploy."""
        _user, bail = _owner_or_404()
        if bail:
            return bail
        split_home.set_layout(request.form.get("layout") or "full")
        return redirect("/settings?home=saved#home-layout")

    @app.route("/desk/<hub_key>")
    def hub_desk(hub_key):
        user = current_user()
        if user is None:
            return login_required_redirect()
        hub = hub_defs.get_hub(hub_key)
        if hub is None:
            abort(404)
        off = _page_hidden()
        if off and not _is_owner_email(user.get("email")):
            hub = dict(hub, modules=[m for m in hub["modules"] if m[0] not in off])
        # The Command desk tiles carry live micro-dashboards — every number
        # below comes from the same engines that power the full pages.
        desk = {}
        if hub_key == "command":
            desk = {"growth": qualification.calculate(user["id"])["total"],
                    "trust": trust_score.calculate(user["id"])["total"],
                    "actions": cc.open_actions(user["id"], limit=3),
                    "insights": insights_engine.build_insights(user["id"])[:2]}
        elif hub_key == "launch":
            # Next drop + real blockers: campaign dates, track release dates,
            # and Clean Release verdicts all come from the user's own records.
            today = datetime.now(timezone.utc).date().isoformat()
            drops = sorted(
                [c for c in mls.list_campaigns(user["id"])
                 if (c.get("release_date") or "") >= today],
                key=lambda c: c["release_date"])
            tracks, ctx, summary, _cert = _os_full(user["id"])
            alerts = []
            for t in sorted([t for t in tracks
                             if (t.get("release_date") or "") >= today],
                            key=lambda t: t["release_date"]):
                clean = artist_os.clean_release(t, ctx)
                passport = artist_os.passport_report(t)
                if clean["blocked"]:
                    first_red = next((i["label"] for i in clean["items"]
                                      if i["state"] == "red"), "rights issue")
                    alerts.append({"level": "red", "track": t["title"],
                                   "date": t["release_date"],
                                   "text": "%s unresolved" % first_red})
                elif passport["pct"] < 100:
                    alerts.append({"level": "amber", "track": t["title"],
                                   "date": t["release_date"],
                                   "text": "passport %d%% complete"
                                           % passport["pct"]})
            desk = {"next_release": drops[0] if drops else None,
                    "reds": summary["reds"], "alerts": alerts[:4],
                    "flow": [("Track Passport", "/tracks"),
                             ("Clean Release", "/releases/autopilot#clean"),
                             ("Schedule", "/releases/autopilot?view=calendar"),
                             ("Smart Link", "/links"),
                             ("Rollout", "/rollout-studio"),
                             ("Pulse", "/pulse")]}
        return render_template("hub_desk.html", active_page="desk-" + hub_key,
                               hub=hub, desk=desk, **build_dashboard_context())

    @app.context_processor
    def inject_plan_context():
        user = None
        try:
            user = current_user()
        except RuntimeError:
            pass
        plan = (user.get("plan") or "artist") if user else None
        world = plans.world_for_path(request.path) or session.get("world")
        if plan == "fan":
            world = "fan"
        return {"user_plan": plan, "nav_world": world or "promote",
                # The wordmark: Royalty Sweep on its own pages, Street Banker
                # everywhere else (owner, 2026-09-14).
                "path_world": plans.world_for_path(request.path),
                "plan_worlds": plans.WORLDS, "plan_rank": plans.TIER_RANK,
                "plan_names": plans.PLAN_NAMES,
                "unread_ntf": store.unread_notifications(user["id"]) if user else 0}

    _PUBLIC_PREFIXES = ("/static/", "/uploads/", "/l/", "/s/", "/epk/",
                        "/stem-src/",
                        # A Stage Bridge is a machine on a venue network; it
                        # holds a device token, not a session, and every
                        # route under here answers 401 without one.
                        "/bridge/",
                        # A performer's phone, through a TOUR share link: the
                        # token is the authorisation, checked on every call.
                        "/stage/guest/",
                        "/services", "/favicon", "/presave/", "/reset/",
                        "/team/join/", "/webhooks/", "/club/", "/showday/",
                        # A fan buying a VIP package from a date's shared link:
                        # the token is the page, Stripe is the authorisation.
                        "/vip/",
                        "/rider/", "/roster/join/", "/sign/", "/sheet/", "/pitch/", "/@",
                        # A journalist who was sent an announcement reads it
                        # without an account. The token in the URL is the
                        # authorisation, and it identifies which recipient
                        # opened it. ("/press-desk" does not match this
                        # prefix - that one stays behind the wall.)
                        "/press/",
                        # The Light Studio phone remote. The unguessable code
                        # in the URL is the authorisation, like a share link,
                        # so a second operator can pick it up without an
                        # account. It carries buttons, never show data.
                        "/lights/remote/",
                        # A light show sent out for notes. Carries one show
                        # and no audio; the trailing slash keeps it from
                        # swallowing anything else under /lights.
                        "/lights/show/",
                        # A beat sent to one artist. One beat, no
                        # catalogue. The trailing slash matters: "/beats"
                        # and "/beats/<id>" stay behind the wall, and so
                        # does "/beat-link/<token>/revoke", which is the
                        # producer's control and not the recipient's.
                        "/beat/",
                        # A beat licence is read and signed by somebody who
                        # has no account here, and the cleared list exists to
                        # be checked by a label that never will.
                        "/licence/", "/cleared/",
                        # A TOUR share link - a day sheet for the local crew,
                        # a check-in list for the door - is read by somebody
                        # without an account. The token is the authorisation
                        # and it is scoped to one thing; /tours/ itself stays
                        # behind the wall.
                        "/tour-share/",
                        # The Team-Up Board's one-click renew link from the
                        # expiry email; single-use token, renews one listing.
                        "/board-renew/")
    _PUBLIC_EXACT = {"/", "/login", "/signup", "/logout", "/submit", "/forgot",
                     "/catalog-sweep", "/demo-open", "/plan",
                     "/terms", "/privacy", "/sw.js", "/demo-access",
                     # A crawler bounced to /login never reads the rules.
                     "/robots.txt",
                     "/api/artist-signal-profile",
                     # The suites' credit call: no session, a signed token.
                     "/api/suites/credits",
                     # A stranger asking what the Artist Twin does, and how
                     # their music would be treated, must not meet a password
                     # field first. /artist-twin itself stays gated.
                     "/artist-twin/start", "/ai", "/lanes",
                     "/creative-studio", "/rollout",
                     "/royalty-sweep", "/distribution",
                     "/metadata",
                     # The closing CTAs and the trust band. A guided start
                     # that demands an account before it will say anything
                     # is not a guided start, and a control policy nobody
                     # can read without signing in is not a policy.
                     "/start", "/artist-control",
                     "/product-tour", "/product-tour/smart-link",
                     "/about", "/contact", "/partners", "/release-check",
                     "/release-signal",
                     # Exact only. "/press" explains the desk to a stranger;
                     # "/press-desk" and everything under it stays gated,
                     # and "/press/<token>" is covered by the prefix above.
                     "/press"}

    def _is_public_path(path):
        if path in _PUBLIC_EXACT:
            return True
        return any(path.startswith(p) for p in _PUBLIC_PREFIXES)

    def _valid_backup_token():
        """A scheduler has no session, so the login wall would bounce it to
        /login and the backup would silently never run. This lets a request
        carrying the right token through - and ONLY that one path, only
        when a token is actually configured. The route re-checks; this is
        not a way in, it is a way past the redirect."""
        token = os.environ.get("BACKUP_TOKEN") or ""
        # The same token lets the same scheduler reach the reminders run.
        if not token or request.path not in ("/backup/run", "/reminders/run"):
            return False
        presented = (request.headers.get("X-Backup-Token")
                     or request.form.get("token") or "")
        return hmac.compare_digest(presented, token)

    def resolve_partner():
        """Which reseller's front door is this request standing at?

        Order matters. The host is the strongest signal because it is the
        thing the artist actually typed, and a partner's own domain must
        never resolve to somebody else's tenant. The seat is the fallback
        for staff reaching the app on the plain address. None means
        Street Banker itself, which is every request today.

        Read-only and side-effect free: it sets g and returns nothing, so
        it cannot bounce a request. Enforcement belongs to the decorator.
        """
        g.partner = None
        g.partner_member = None
        host = (request.host or "").split(":")[0].lower()
        try:
            if not partner_store.any_partners():
                return          # no resellers on this instance: nothing to resolve
            p = partner_store.partner_by_domain(host)
            if p is None and host.endswith(_PARTNER_ROOT) and host != _PARTNER_ROOT:
                p = partner_store.partner_by_slug(host[:-len(_PARTNER_ROOT) - 1])
            if p is None:
                uid = session.get("user_id")
                # Bind any seat invited by email to this account first.
                # member_for_user matches on user_id, and a seat created
                # before its holder signed up has user_id NULL - so without
                # this the reseller's own staff could not reach their
                # console at all, however correct the seat was.
                user = store.get_user(uid) if uid else None
                if user:
                    partner_store.claim_seats(user["id"], user.get("email"))
                seat = partner_store.member_for_user(uid) if uid else None
                if seat:
                    p = partner_store.get_partner(seat["partner_id"])
                    g.partner_member = seat
            if p and p.get("status") == "active":
                g.partner = p
                if g.partner_member is None:
                    uid = session.get("user_id")
                    user = store.get_user(uid) if uid else None
                    if user:
                        g.partner_member = partner_store.get_member(
                            p["id"], user_id=user["id"], email=user.get("email"))
        except Exception:
            # A partner table that is missing or mid-migration must not
            # take down every page. No tenant resolved is a safe answer.
            g.partner = None
            g.partner_member = None

    @app.before_request
    def _resolve_partner():
        """Registered BEFORE plan_gate, so g.partner is set by the time
        the login wall runs. Never returns a response - resolution
        must not be able to bounce a request."""
        resolve_partner()
        return None

    @app.before_request
    def plan_gate():
        user = current_user()
        if user is None:
            if _is_public_path(request.path) or _valid_backup_token():
                return None
            if request.path == "/backup/run" and request.method == "POST":
                # A scheduler cannot follow a redirect to /login, and the
                # first nightly run proved that a 302 reads as success in
                # a cron log: Render printed "Redirecting..." and marked
                # the run green. The failure has to be a failure.
                why = ("BACKUP_TOKEN is not configured on the server"
                       if not os.environ.get("BACKUP_TOKEN")
                       else "the token presented did not match BACKUP_TOKEN")
                return jsonify({"ok": False, "error": why}), 403
            return redirect(url_for("login", next=request.path))
        tier = plans.required_tier(request.path)
        if tier and not plans.allowed(user.get("plan") or "artist", tier):
            return render_template("upgrade.html", required=tier,
                                   plans_list=plans.PLANS,
                                   **build_dashboard_context()), 402
        # A page that is really one of the suites opens the way the suite
        # does. Public links under the same prefixes stay public, and the
        # owner's own account opens everything.
        suite = plans.path_suite(request.path)
        if suite and not _is_public_path(request.path) and not _is_owner_email(user.get("email")):
            plan = user.get("plan") or "artist"
            held = 0 if plan == "label" else store.credit_balances(user["id"])["total"]
            if not plans.suite_open(plan, suite, held):
                need = plans.suite_access(suite)
                return render_template("upgrade.html", required="label" if need == "credits" else need,
                                       needs_credits=(need == "credits"),
                                       suite_name={"the-room": "The Room", "tour": "Tour"}[suite],
                                       plans_list=plans.PLANS, **build_dashboard_context()), 402
        return None

    def _demo_locked_account():
        """The signed-in account if it is under the read-only demo lock,
        else None. Reads the SESSION account as well as current_user(),
        because a partner seat acting on an artist's behalf presents the
        artist; a locked staff login must stay locked. Cached per request."""
        if hasattr(g, "_demo_locked"):
            return g._demo_locked
        found = None
        uid = session.get("user_id")
        if uid:
            me = store.get_user(uid)
            if me and me.get("demo_lock"):
                found = me
            else:
                acting = current_user()
                if acting and acting.get("demo_lock"):
                    found = acting
        g._demo_locked = found
        return found

    # Writes a locked demo may still make: the way in and out, and the
    # store check on Statements, which only caches what the stores said.
    _DEMO_LOCK_ALLOWED = ("/login", "/logout", "/demo-open", "/partner/act/stop",
                          "/statements/gaps/check")
    _DEMO_READ_ONLY = ("This is a shared demo account and it is read only. "
                       "Browse everything; nothing you change is saved. "
                       "Start your own account to do this.")

    def _wants_json():
        """A script call, as opposed to a page form. Browsers stamp every
        fetch() with Sec-Fetch-Mode cors/same-origin and Sec-Fetch-Dest empty,
        and a form submission with navigate/document - without reading
        those, a delete button's fetch followed the refusal redirect to a
        200 page, read it as success and took the row off the screen
        (owner, on staging, 2026-09-14: "you can delete things")."""
        # A page form asks for HTML first; a script call asks for anything
        # (fetch() sends Accept: */*). On staging a Remove button's form
        # still got the JSON answer as a white page (owner, 2026-09-14), so
        # the Accept header decides before anything else does.
        accept = (request.headers.get("Accept") or "").strip().lower()
        if accept.startswith("text/html"):
            return False
        mode = (request.headers.get("Sec-Fetch-Mode") or "").lower()
        dest = (request.headers.get("Sec-Fetch-Dest") or "").lower()
        return (request.is_json
                or request.path.endswith(".json")
                or request.accept_mimetypes.best == "application/json"
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or mode in ("cors", "same-origin", "no-cors")
                or dest == "empty")

    @app.before_request
    def demo_lock_gate():
        """A locked demo can read everything and change nothing.

        Runs after the login wall, on state-changing methods only. A
        page form is bounced back to the page it came from with
        ?demo=readonly, which the shell turns into the sentence above;
        a script call gets the same sentence as a 403 JSON answer.
        """
        # Anything but a read is a write: Flask answers HEAD with the GET
        # handler, and a handler that writes on "not GET" wrote on HEAD
        # (team review, 2026-09-19).
        if request.method in ("GET", "OPTIONS"):
            return None
        if request.path in _DEMO_LOCK_ALLOWED:
            return None
        if not _demo_locked_account():
            return None
        if _wants_json():
            return jsonify({"ok": False, "error": _DEMO_READ_ONLY, "demo": "readonly"}), 403
        back = "/command-center"
        ref = urllib.parse.urlsplit(request.referrer or "")
        if ref.path.startswith("/") and (not ref.netloc or ref.netloc == request.host):
            back = ref.path
            if ref.query:
                back += "?" + "&".join(p for p in ref.query.split("&") if not p.startswith("demo="))
        return redirect(back + ("&" if "?" in back else "?") + "demo=readonly")

    # Areas a team seat never reaches, whatever its access: the account
    # holder's money, settings, team and suites stay theirs (2026-09-19).
    # /account (start over, delete) and /backup were reachable from a seat.
    # Tour, the Tour Board and the Press Desk now work in the account a
    # request is in, as Studio does, so they open to seats through their
    # rooms (Stage; the Press Desk is Marketing). What in them stays the
    # account holder's is shut here:
    #   /tours/join  a tour crew invitation's link makes whoever accepts it
    #                a member of that tour. From a seat it would attach the
    #                ARTIST's account to someone else's tour (owner,
    #                2026-09-19). tour_os refuses it for a seat as well.
    # Accepting a team or roster invitation (/team, /roster/join) and
    # opening a seat (/portal) are the same kind of door and stay shut.
    _TEAM_BLOCKED = ("/billing", "/settings", "/team", "/admin", "/partner", "/plan/switch",
                     "/suites/go", "/api/suites", "/referrals", "/portal", "/roster/join",
                     "/upgrade", "/owner", "/operator-desk", "/signal", "/account", "/backup",
                     "/tours/join")
    _TEAM_ALLOWED = ("/portal/leave", "/logout")

    def _team_blocked_inside(path):
        """The account holder's pages whose id sits mid-path, which no
        prefix above can name: a tour's crew invitations and their join
        links (/tours/<id>/team...), its public share links and their QR
        codes (/tours/<id>/share...; a link outlives the seat that saw
        it), and the old Tour Hub forms that mint a show's public rider
        link or mail it out (/tour/<id>/share, /tour/<id>/send-advance).
        tour_os refuses the tour pages to a seat as well."""
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "tours" and parts[2] in ("team", "share"):
            return True
        return len(parts) == 3 and parts[0] == "tour" and parts[2] in ("share", "send-advance")

    _TEAM_READ_ONLY = ("You have read-only access to this account. Look at everything; "
                       "changes are made by the artist or a team member who can edit.")

    def _under(path, prefix):
        return path == prefix or path.startswith(prefix + "/")

    @app.before_request
    def team_seat_gate():
        """A team seat inside the artist's account: blocked areas stay shut,
        a read seat changes nothing, and every change an editor makes is
        recorded under their name on the artist's Team page."""
        if not session.get("team_as") or not session.get("user_id"):
            return None
        path = request.path
        if path in _TEAM_ALLOWED or path.startswith("/static/"):
            return None
        current_user()                      # resolves the seat, or ends it
        seat = (getattr(g, "_team_seat", None) or (None, None))[1]
        if not session.get("team_as") or seat is None:
            return None
        writes = request.method not in ("GET", "OPTIONS")
        home = team_areas.home(seat["areas"])
        if any(_under(path, p) for p in _TEAM_BLOCKED) or _team_blocked_inside(path):
            if writes and _wants_json():
                return jsonify({"ok": False, "error": "Only the account holder can do this."}), 403
            # A tour invitation may be the member's own, so that banner
            # says how they take it rather than that it is the artist's.
            return redirect(home + ("?team=join" if _under(path, "/tours/join") else "?team=blocked"))
        # The rooms the artist ticked for this person (owner, 2026-09-19).
        if not team_areas.allows(seat["areas"], path):
            if _wants_json():
                return jsonify({"ok": False, "error": "That room is not open to you."}), 403
            return redirect(home + "?team=room")
        if request.method == "HEAD" and request.content_length:
            # Flask answers HEAD with the GET view and a HEAD is not
            # recorded below. One carrying a form body is no browser's
            # read, so it is refused rather than left to each view to
            # tell from a POST (review, 2026-09-19).
            return ("", 400)
        if not writes:
            return None
        if seat["access"] != "edit" or (_under(path, "/roster") and not seat["can_roster"]):
            if _wants_json():
                return jsonify({"ok": False, "error": _TEAM_READ_ONLY, "team": "readonly"}), 403
            back = home
            ref = urllib.parse.urlsplit(request.referrer or "")
            if ref.path.startswith("/") and (not ref.netloc or ref.netloc == request.host):
                back = ref.path
            return redirect(back + "?team=readonly")
        # Recorded once the change has gone through, not when it is asked
        # for: a refused or unrouted request is not a change (team review).
        if request.method != "HEAD":
            g._team_audit = (seat["owner"]["id"], seat["member_id"], seat["member_name"],
                             request.method, path)
        return None

    @app.after_request
    def _team_audit_write(resp):
        a = getattr(g, "_team_audit", None)
        if a and request.url_rule is not None and resp.status_code < 400:
            store.add_team_audit(*a)
        return resp

    @app.before_request
    def acting_as_change_note():
        """A partner staff member acting on an artist's behalf works the
        artist's account as the artist. Each change they make goes on the
        partner's audit trail under their own name, next to the start and
        stop of the act-on-behalf (review, 2026-09-19): an impersonation
        whose changes are not on the record is not on the record. Read
        here, before the view can end the act-on-behalf, and written
        after, once the change has gone through."""
        if not session.get("acting_as") or request.method in ("GET", "OPTIONS", "HEAD"):
            return None
        path = request.path
        if _under(path, "/partner") or path == "/logout" or path.startswith("/static/"):
            return None
        acting = current_acting()
        member = partner_store.member_for_user(acting["id"]) if acting else None
        if member:
            g._acting_audit = (member["partner_id"], member, session.get("acting_as"),
                               "%s %s" % (request.method, path))
        return None

    @app.after_request
    def _acting_as_change_write(resp):
        a = getattr(g, "_acting_audit", None)
        if a and request.url_rule is not None and resp.status_code < 400:
            partner_store.audit(a[0], "act_as.change", actor=a[1], subject_user_id=a[2], detail=a[3])
        return resp

    @app.context_processor
    def _team_banner():
        seat = (getattr(g, "_team_seat", None) or (None, None))[1] if session.get("team_as") else None
        return {"team_seat": seat}

    def _page_hidden():
        """The pages switched off, read once per request."""
        if not hasattr(g, "_page_hidden"):
            g._page_hidden = page_switches.hidden_keys()
        return g._page_hidden

    @app.before_request
    def page_switch_gate():
        """A page the owner switched off bounces everyone but an owner to
        the Command Center, with the page's name so the note can say
        which. Pages under it go with it (see page_switches)."""
        if request.path.startswith("/static/"):
            return None
        hidden = _page_hidden()
        if not hidden:
            return None
        hit = page_switches.hidden_for_path(request.path, hidden)
        if not hit:
            return None
        user = current_user()
        if user and _is_owner_email(user.get("email")):
            return None
        return redirect("/command-center?off=" + urllib.parse.quote(hit["label"]))

    @app.route("/admin/pages", methods=["POST"])
    def admin_pages():
        """The owner's switchboard: every sidebar page live or hidden,
        saved at once, live for everybody else on the next request.
        Owner only, 404 to everybody else."""
        _user, bail = _owner_or_404()
        if bail:
            return bail
        live = set(request.form.getlist("live"))
        page_switches.set_hidden(page_switches.known_keys() - live)
        return redirect("/settings?pages=saved#page-switches")

    @app.context_processor
    def _demo_lock_context():
        return {"demo_locked": bool(_demo_locked_account()),
                "demo_readonly_refused": request.args.get("demo") == "readonly"}

    @app.route("/admin/demo-lock", methods=["POST"])
    def admin_demo_lock():
        """The owner locks or unlocks an account as a read-only demo.

        Owner, 2026-09-14: "make the demo account read only for everyone
        but me". There is no second password: the owner unlocks from
        their own login, signs into the demo to load it, and locks it
        again. Owner only, 404 to everybody else.
        """
        _user, bail = _owner_or_404()
        if bail:
            return bail
        email = (request.form.get("email") or "").strip().lower()
        action = (request.form.get("action") or "lock").strip().lower()
        target = store.get_user_by_email(email) if email else None
        if target is None:
            return redirect("/settings?demo_lock=unknown#demo-lock")
        if _is_owner_email(target.get("email")):
            return redirect("/settings?demo_lock=owner#demo-lock")
        store.set_demo_lock(target["id"], action != "unlock")
        return redirect("/settings?demo_lock=%s&to=%s#demo-lock"
                        % ("unlocked" if action == "unlock" else "locked",
                           urllib.parse.quote(email)))

    @app.route("/world/<world>")
    def switch_world(world):
        homes = {k: home for k, _, home, _ in plans.WORLDS}
        if world not in homes:
            abort(404)
        session["world"] = world
        return redirect(homes[world])

    def _is_demo_email(email):
        return demo_accounts.is_demo_email(email)

    @app.context_processor
    def _acting_as():
        """Every template needs to know, so it is a context processor rather
        than something each route remembers to pass."""
        return {"acting_as_name": session.get("acting_as_name") or ""}

    @app.context_processor
    def _billing_flags():
        user = current_user()
        return {"stripe_live": stripe_billing.configured(),
                "is_demo_account": bool(user and _is_demo_email(user["email"])),
                # Only an owner may re-create the production Stripe webhook.
                "viewer_is_owner": bool(user and _is_owner_email(user.get("email")))}

    def _demo_switching(user):
        """May /plan/switch hand this account a paid tier with no payment?
        The demo logins always; anyone else only off Render with no
        Stripe (a laptop, the test suite). Billing offers the demo switch
        only where this holds, so a deployed service without Stripe never
        shows a button that does nothing (walk, 2026-09-20)."""
        return _is_demo_email(user["email"]) or not (
            stripe_billing.configured() or os.environ.get("RENDER"))

    @app.route("/plan/switch", methods=["POST"])
    def plan_switch():
        user = current_user()
        if user is None:
            return login_required_redirect()
        plan = request.form.get("plan") or ""
        # An artist seated at a partner does not hold their own tier. The
        # partner grants it (/partner/roster/<id>/plan) and carries the cost,
        # so self-serve here would let a reseller's artist unlock paid
        # features nobody agreed to pay for. current_user() returns the
        # ARTIST while a partner seat is acting on their behalf, so this one
        # check covers the artist doing it and staff doing it through
        # act-on-behalf.
        if user.get("partner_id"):
            return redirect(request.referrer or "/billing")
        # A paying subscriber never drops their tier here: the Stripe
        # subscription would keep billing while the account lost the plan
        # (walk, 2026-09-20: "Switch to Fan", then a 402 on the Command
        # Center). Billing owns cancellation and downgrades.
        if user.get("stripe_subscription_id") and not _is_demo_email(user["email"]):
            return redirect("/billing")
        # With Stripe live, paid tiers go through real checkout — the demo
        # accounts keep instant switching so the tier demos still work.
        #
        # And on a deployed service a paid tier is never granted here even
        # when Stripe looks unconfigured (2026-09-17). It used to be: a
        # service missing STRIPE_SECRET_KEY handed out any tier for the
        # asking, which since Labels may now seat a roster would have let
        # an account promote itself and then mint accounts. This fails
        # toward refusing an upgrade rather than giving one away, so a key
        # that goes missing stops sales instead of starting a giveaway.
        paid = plan in stripe_billing.PRICES
        if paid and not _demo_switching(user):
            return redirect("/billing")
        if plan in plans.TIER_RANK:
            store.set_user_plan(user["id"], plan)
        return redirect(request.referrer or "/billing")

    def _billing_hands_off(user):
        """Accounts whose card this page must not charge: an artist seated at
        a partner (the partner holds their tier), and anyone working as an
        artist through a partner seat, who would be spending that artist's
        saved card (2026-09-19 review; the same rule as /plan/switch)."""
        return bool(user.get("partner_id") or session.get("acting_as") or session.get("team_as"))

    def _working_as_someone():
        """Signed in as yourself but working in somebody else's account."""
        return bool(session.get("acting_as") or session.get("team_as"))

    def _plan_grant_key(user_id):
        return "plan_grant:" + user_id

    def _plan_held(user):
        """A plan Stripe must never move: the owner's, a partner-seated
        artist's (the partner holds it), and one the owner granted by hand
        in Settings, which renewals used to undo (2026-09-19 second
        review)."""
        user = user or {}
        return bool(_is_owner_email(user.get("email")) or user.get("partner_id")
                    or (user.get("id") and store.get_kv(_plan_grant_key(user["id"]))))

    def _notify_owners(title, body, link="/billing"):
        """Money the app cannot settle alone goes to the people who run the
        Stripe account."""
        for u in store.list_users():
            if _is_owner_email(u.get("email")):
                store.notify(u["id"], "billing", title, body, link)

    def _checkout_error(message):
        return render_template("billing_error.html", message=message,
                               **build_dashboard_context()), 502

    def _open_checkout_key(user_id):
        return "stripe_open_checkout:" + user_id

    @app.route("/billing/checkout", methods=["POST"])
    def billing_checkout():
        user = current_user()
        if user is None:
            return login_required_redirect()
        plan = request.form.get("plan") or ""
        if not stripe_billing.configured() or plan not in stripe_billing.PRICES:
            return redirect("/billing")
        if _billing_hands_off(user):
            return redirect("/billing")
        # Ids Stripe gave under the sandbox key do not exist under the live
        # one; an account that checked out in the sandbox kept them and
        # could never check out again (2026-09-19 second review).
        if user.get("stripe_customer_id"):
            known = stripe_billing.customer_exists(user["stripe_customer_id"])
            if known is None:
                return _checkout_error("Stripe couldn't be reached just now. Nothing was "
                                       "started: try again in a minute.")
            if known is False:
                store.set_stripe_ids(user["id"], None, None)
                user = dict(user, stripe_customer_id=None, stripe_subscription_id=None)
        # A member changes tier on the subscription they already have. This
        # used to open a second checkout, so the old subscription kept
        # billing beside the new one (2026-09-18 launch check). Only a
        # subscription that is gone may lead to a fresh checkout: any other
        # failure stops here, because the old one may still be billing
        # (2026-09-19 review).
        if user.get("stripe_subscription_id"):
            changed = stripe_billing.change_subscription_plan(user["stripe_subscription_id"], plan)
            result = changed.get("result")
            if result in ("changed", "same"):
                if not _plan_held(user):
                    store.set_user_plan(user["id"], plan)
                if result == "changed":
                    store.notify(user["id"], "billing",
                                 "You're on %s" % plans.PLAN_NAMES.get(plan, plan),
                                 "Your subscription moved to %s. Stripe adjusts the "
                                 "difference on your bill." % plans.PLAN_NAMES.get(plan, plan),
                                 "/billing")
                return redirect("/billing?changed=" + plan)
            if result == "pending":
                return redirect("/billing?changed=pending")
            if result != "gone":
                if changed.get("status") in ("unpaid", "incomplete", "paused"):
                    return _checkout_error("Your subscription has a bill waiting. Settle it in "
                                           "Manage Billing first, then change your plan.")
                return _checkout_error("Stripe couldn't change your plan just now. Nothing new "
                                       "was started: try again in a minute, or open Manage Billing.")
            # Gone: forget it, and the paid tier it carried, then check out
            # again as the same customer (2026-09-19 second review: the tier
            # stayed on after Stripe said the subscription had ended).
            store.set_stripe_ids(user["id"], user.get("stripe_customer_id"), None)
            if not _plan_held(user) and user.get("plan") in stripe_billing.PRICES:
                store.set_user_plan(user["id"], "fan")
        # Somebody who already pays, or owes, is never sold a second
        # subscription, and a checkout already open for this account is
        # settled first, so two clicks cannot become two subscriptions.
        if user.get("stripe_customer_id"):
            live = stripe_billing.active_subscription_for_customer(user["stripe_customer_id"])
            if live and live.get("error"):
                return _checkout_error("Stripe couldn't be reached just now. Nothing was "
                                       "started: try again in a minute.")
            if live:
                store.set_stripe_ids(user["id"], user["stripe_customer_id"], live["subscription_id"])
                if live.get("status") not in ("active", "trialing"):
                    return _checkout_error("Your subscription has a bill waiting. Settle it in "
                                           "Manage Billing first, then change your plan.")
                if not _plan_held(user):
                    store.set_user_plan(user["id"], live["plan"])
                return redirect("/billing?sync=found")
        opened = store.get_kv(_open_checkout_key(user["id"]))
        if opened:
            state, sess = stripe_billing.close_open_checkout(opened)
            if state == "complete":
                # Paid, and its webhook has not landed yet: claim it here
                # rather than open a second one. One already handled belongs
                # to a subscription that has since ended.
                claimed = _claim_plan_session(sess)
                if claimed == "retry":
                    return _checkout_error("Stripe couldn't be reached just now. Nothing was "
                                           "started: try again in a minute.")
                if claimed != "done":
                    return redirect("/billing?upgraded=1")
            elif state != "closed":
                return _checkout_error("The checkout you opened a moment ago is still open. "
                                       "Finish it in that tab, or try again in a minute.")
            store.set_kv(_open_checkout_key(user["id"]), "")
        # The referral's 50% is for a first subscription only: never for an
        # account Stripe has already billed (2026-09-19 review).
        eligible = (user.get("referred_by") and not user.get("stripe_customer_id")
                    and not user.get("ref_credited"))
        coupon = stripe_billing.ensure_referral_coupon() if eligible else None
        if eligible and not coupon:
            _notify_owners("Referral discount missing",
                           "%s joined from a referral and is checking out, but Stripe "
                           "would not make the 50%% coupon, so they are paying full price. "
                           "Check the secret key, or refund them half from Stripe."
                           % user.get("email"))
        session_obj = stripe_billing.create_checkout_session(
            user["id"], user["email"], plan, request.url_root.rstrip("/"),
            coupon=coupon, customer_id=user.get("stripe_customer_id"))
        if not session_obj or not session_obj.get("url"):
            return _checkout_error("Stripe couldn't start checkout. Try again in a minute or "
                                   "contact support.")
        if session_obj.get("id"):
            store.set_kv(_open_checkout_key(user["id"]), session_obj["id"])
        return redirect(session_obj["url"], code=303)

    @app.route("/billing/credits", methods=["POST"])
    def billing_credits():
        """Buy a credit pack. Any membership can; bought credits never expire.
        Closed while plans.CREDIT_PACKS_ON_SALE is off (owner, 2026-09-18)."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if not plans.CREDIT_PACKS_ON_SALE:
            return redirect("/billing#credits")
        pack = plans.CREDIT_PACKS.get(request.form.get("pack") or "")
        if pack is None or not stripe_billing.configured() or _demo_locked_account():
            return redirect("/billing#credits")
        credits, cents, name = pack
        session_obj = stripe_billing.create_credit_pack_checkout(
            user["id"], user["email"], request.form.get("pack"), credits, cents, name,
            request.url_root.rstrip("/"))
        if not session_obj or not session_obj.get("url"):
            return redirect("/billing?credits=fail#credits")
        return redirect(session_obj["url"])

    def _claim_credit_pack(obj):
        """Fill a wallet from a paid pack session, once, whoever sees it first
        (the webhook or the success redirect)."""
        meta = obj.get("metadata") or {}
        pack = plans.CREDIT_PACKS.get(meta.get("pack") or "")
        uid = obj.get("client_reference_id")
        if meta.get("kind") != "credit_pack" or pack is None or obj.get("payment_status") != "paid":
            return False
        if not uid or not store.get_user(uid):
            return False
        return store.add_credits(uid, pack[0], "pack", bucket="bought", note=pack[2],
                                 ref="stripe:%s" % obj.get("id"))

    @app.route("/billing/sync", methods=["POST"])
    def billing_sync():
        """Webhook-less fallback: claim a completed Stripe checkout by
        matching an active subscription to the signed-in account's email."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if not stripe_billing.configured():
            return redirect("/billing")
        if _billing_hands_off(user):
            return redirect("/billing")
        found = stripe_billing.active_subscription_for_email(user["email"], user_id=user["id"])
        if found:
            if not _plan_held(user):
                store.set_user_plan(user["id"], found["plan"])
            store.set_stripe_ids(user["id"], found["customer_id"],
                                 found["subscription_id"])
            store.notify(user["id"], "billing",
                         "Welcome to %s" % plans.PLAN_NAMES.get(found["plan"]),
                         "Subscription synced from Stripe — everything is unlocked.",
                         "/command-center")
            _settle_referrals(user["id"])
        return redirect("/billing" + ("?upgraded=1" if found else "?sync=none"))

    def _ref_paid_key(user_id):
        return "ref_paid:" + user_id

    def _ref_paid_cents_key(user_id):
        return "ref_paid_cents:" + user_id

    def _credit_referrer(referrer, referred_id, referred_email, cents):
        """Claim this referral once, in the database, then credit Stripe with
        a key so a retry cannot credit twice (2026-09-19 review: two workers
        could both credit). Only a credit Stripe refused gives the claim
        back. One Stripe did not answer about is looked for on the balance;
        if it cannot be found the claim stays and the owner is told, because
        a retry after the key expires would credit twice (second review)."""
        if not cents or not store.claim_ref_credit(referred_id):
            return False
        customer = referrer["stripe_customer_id"]
        result = stripe_billing.apply_credit(
            customer, cents,
            "Street Banker referral: 50%% off for referring %s" % referred_email,
            idempotency_key="sb-ref-credit-" + referred_id,
            metadata={"sb_ref_friend": referred_id})
        if result == "unknown" and stripe_billing.find_credit(customer, "sb_ref_friend", referred_id):
            result = "ok"
        if result == "ok":
            store.notify(referrer["id"], "billing", "Referral credit applied",
                         "$%.2f, toward half your next month, landed on your Stripe balance: "
                         "%s paid for their plan." % (cents / 100.0, referred_email), "/referrals")
            return True
        if result == "refused":
            store.release_ref_credit(referred_id)
            return False
        _notify_owners("Check a referral credit",
                       "Stripe did not answer when crediting $%.2f to %s for referring %s. "
                       "Open that customer in Stripe: if their balance has no \"Street Banker "
                       "referral\" credit for %s, add $%.2f by hand."
                       % (cents / 100.0, referrer.get("email"), referred_email,
                          referred_email, cents / 100.0))
        return False

    def _billed_plan(user):
        """The tier Stripe bills this account for now, or None. The plan the
        app shows can be higher (an owner's grant), and the referral credit
        is half of what the referrer actually pays (2026-09-19 second
        review)."""
        sub = stripe_billing.subscription_state((user or {}).get("stripe_subscription_id"))
        if sub and sub.get("status") in ("active", "trialing", "past_due"):
            return stripe_billing.plan_for_subscription(sub)
        return None

    def _referral_cents(referrer, paid_cents):
        """Half the referrer's own billed month, and never more than the
        friend actually paid: a Label referrer earning $99.50 from a $14.50
        payment would make referrals a way to print credit. Nothing until
        the friend's payment is known."""
        if not paid_cents:
            return 0
        half = stripe_billing.referrer_credit_cents(_billed_plan(referrer))
        return min(half, int(paid_cents))

    def _settle_referrals(payer_id, paid_cents=0):
        """Settle referrals on real money. When this account has just paid
        (paid_cents > 0), its referrer is credited half their own month,
        capped at what was paid; a referrer not on a paid plan yet keeps it
        waiting. And any referral this account earned while it was not
        paying is settled now that it is."""
        payer = store.get_user(payer_id)
        if not payer:
            return
        ref_id = payer.get("referred_by")
        if ref_id and paid_cents and not payer.get("ref_credited"):
            store.set_kv(_ref_paid_key(payer_id), "1")
            if not store.get_kv(_ref_paid_cents_key(payer_id)):
                store.set_kv(_ref_paid_cents_key(payer_id), str(int(paid_cents)))
            referrer = store.get_user(ref_id)
            if referrer and referrer.get("stripe_customer_id"):
                _credit_referrer(referrer, payer_id, payer["email"],
                                 _referral_cents(referrer, int(store.get_kv(_ref_paid_cents_key(payer_id)) or paid_cents)))
        if payer.get("stripe_customer_id") and stripe_billing.referrer_credit_cents(payer.get("plan")):
            for u in store.list_uncredited_referrals(payer_id):
                if store.get_kv(_ref_paid_key(u["id"])) != "1":
                    continue            # they have not actually paid yet
                _credit_referrer(payer, u["id"], u["email"],
                                 _referral_cents(payer, int(store.get_kv(_ref_paid_cents_key(u["id"])) or 0)))

    @app.route("/referrals")
    def referrals():
        user = current_user()
        if user is None:
            return login_required_redirect()
        code = store.ensure_ref_code(user["id"])
        return render_template("referrals.html", active_page="referrals",
                               ref_link=(request.url_root.rstrip("/")
                                         + "/signup?ref=" + code),
                               stats=store.referral_stats(user["id"]),
                               stripe_live=stripe_billing.configured(),
                               **build_dashboard_context())

    @app.route("/billing/webhook-setup", methods=["POST"])
    def billing_webhook_setup():
        # Owner-only: the server creates the Stripe webhook endpoint itself
        # and keeps the signing secret in app_kv — no dashboard copy-paste.
        # It used to check only for the Label plan, so any Label customer,
        # and the shared demo Label login, could delete and re-create the
        # platform's production webhook. The owner is who runs the Stripe
        # account, so the owner is who may touch it.
        user, deny = _owner_or_404()
        if deny:
            return deny
        result = stripe_billing.setup_webhook_endpoint(
            request.url_root.rstrip("/"))
        return redirect("/billing?webhook=" + ("ok" if result else "fail"))

    @app.route("/billing/portal", methods=["POST"])
    def billing_portal():
        user = current_user()
        if user is None:
            return login_required_redirect()
        # Someone working in another account never opens its card. An
        # artist seated at a partner still pays for, and may cancel, the
        # subscription they already had (2026-09-19 second review).
        if _working_as_someone():
            return redirect("/billing")
        if not (stripe_billing.configured() and user.get("stripe_customer_id")):
            return redirect("/billing")
        if stripe_billing.customer_exists(user["stripe_customer_id"]) is False:
            store.set_stripe_ids(user["id"], None, None)
            return redirect("/billing?sync=none")
        session_obj = stripe_billing.create_portal_session(
            user["stripe_customer_id"], request.url_root.rstrip("/") + "/billing")
        if not session_obj or not session_obj.get("url"):
            return redirect("/billing")
        return redirect(session_obj["url"], code=303)

    def _claim_plan_session(obj):
        """Put an account on the tier a paid membership checkout bought,
        once, whoever sees the session first (the webhook, or the member's
        next Subscribe click). Returns:
          claimed   done now
          done      handled before
          skipped   not a paid membership checkout of a known account
          conflict  the account already has another subscription billing:
                    nothing is overwritten and the owner is told
          retry     Stripe could not be asked; try again later
        The done mark is written last, so a run that failed half way is
        run again (2026-09-19 second review)."""
        obj = obj or {}
        user_id = obj.get("client_reference_id")
        plan = (obj.get("metadata") or {}).get("plan")
        paid = obj.get("payment_status") in ("paid", "no_payment_required")
        sid = obj.get("id") or ""
        member = store.get_user(user_id) if user_id else None
        if not (paid and member and plan in stripe_billing.PRICES):
            return "skipped"
        done_key = "stripe_cs_done:" + sid
        if sid and store.get_kv(done_key):
            return "done"
        new_sub = obj.get("subscription")
        stored = member.get("stripe_subscription_id")
        if stored and new_sub and stored != new_sub:
            # A late first delivery of an old checkout, or two checkouts
            # that both went through: the subscription on file wins while
            # it can still bill (2026-09-19 second review).
            cur = stripe_billing.subscription_state(stored)
            if cur is None:
                return "retry"
            if cur.get("status") in stripe_billing.BILLING_STATUSES:
                _notify_owners("Two subscriptions on one account",
                               "%s has subscription %s on file and checkout %s started %s as "
                               "well. Both can bill: cancel and refund the extra one in Stripe."
                               % (member.get("email"), stored, sid or "?", new_sub))
                store.notify(user_id, "billing", "Two memberships are billing",
                             "A second checkout went through while your membership was "
                             "already active. Street Banker has been told; you can also "
                             "cancel the extra one in Manage Billing.", "/billing")
                if sid:
                    store.set_kv(done_key, "1")
                return "conflict"
        if not _plan_held(member):
            store.set_user_plan(user_id, plan)
        store.set_stripe_ids(user_id, obj.get("customer"), new_sub)
        store.notify(user_id, "billing",
                     "Welcome to %s" % plans.PLAN_NAMES.get(plan, plan),
                     "Your subscription is active: every %s feature is "
                     "unlocked." % plans.PLAN_NAMES.get(plan, plan),
                     "/command-center")
        # The first payment is this session's own: settled here as well as
        # on invoice.paid, which can arrive before this has linked the
        # customer (2026-09-19 review).
        if int(obj.get("amount_total") or 0) > 0:
            _settle_referrals(user_id, int(obj.get("amount_total")))
        if sid:
            store.set_kv(done_key, "1")
            # Only this session's own mark: a newer checkout the member
            # opened since stays guarded (2026-09-19 second review).
            if store.get_kv(_open_checkout_key(user_id)) == sid:
                store.set_kv(_open_checkout_key(user_id), "")
        return "claimed"

    def _refund_touches_referral(customer_id, amount_cents, what):
        """A refunded or disputed payment from a referred friend. A credit
        not paid yet waits for real money again; one already paid is the
        owner's to reverse, so they are told."""
        friend = store.user_by_stripe_customer(customer_id)
        if not (friend and friend.get("referred_by")):
            return
        referrer = store.get_user(friend["referred_by"]) or {}
        if friend.get("ref_credited"):
            _notify_owners("Referral credit on a %s payment" % what,
                           "%s's payment of $%.2f was %s. Their referrer %s already has a "
                           "referral credit for them: reverse it in Stripe if the %s stands."
                           % (friend.get("email"), amount_cents / 100.0, what,
                              referrer.get("email") or "?",
                              "refund" if what == "refunded" else "dispute"))
        else:
            store.set_kv(_ref_paid_key(friend["id"]), "")
            store.set_kv(_ref_paid_cents_key(friend["id"]), "")

    @app.route("/webhooks/stripe", methods=["POST"])
    def stripe_webhook():
        if not stripe_billing.webhook_accepts():
            abort(404)
        body = request.get_data()
        if not stripe_billing.verify_webhook(
                request.headers.get("Stripe-Signature", ""), body):
            return jsonify({"ok": False, "error": "bad signature"}), 401
        event = request.get_json(silent=True) or {}
        etype = event.get("type") or ""
        obj = (event.get("data") or {}).get("object") or {}
        if etype == "checkout.session.completed" and \
                (obj.get("metadata") or {}).get("kind") == "fan_club":
            meta = obj.get("metadata") or {}
            artist_id = meta.get("artist_id")
            email = (meta.get("member_email") or "").lower()
            if artist_id and store.get_user(artist_id) and email:
                new_id = store.add_club_member(artist_id, email, obj.get("customer"),
                                               obj.get("subscription"))
                fan_id = mls.upsert_fan(artist_id, email, None)
                if new_id:  # replayed events and rejoins shouldn't re-notify
                    mls.add_consent(fan_id, None, "fan_club",
                                    "Paid fan club membership via Stripe checkout.")
                    store.notify(artist_id, "fan", "New fan club member",
                                 "%s joined your fan club." % email, "/fan-club")
        elif etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded") and \
                (obj.get("metadata") or {}).get("kind") == "tour_vip":
            # A VIP package for a tour date; claimed once, however many times
            # Stripe replays it or the success redirect got there first. A
            # delayed payment method completes unpaid and settles later: the
            # second event carries the same session, now paid.
            tour_os.claim_vip_session(obj)
        elif etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded") and \
                (obj.get("metadata") or {}).get("kind") == "credit_pack":
            _claim_credit_pack(obj)
        elif etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded") and \
                (obj.get("metadata") or {}).get("kind") == "release_ready":
            # A Release-Ready master: claimed once, whoever gets here first
            # (this or the success redirect); only then is RoEx asked for it.
            if release_ready.claim_session(obj) == "retry":
                return jsonify({"ok": False, "error": "database unavailable; retry"}), 503
        elif etype == "checkout.session.completed":
            # Granted on money, not on a completed form: a session can
            # complete unpaid (2026-09-18 launch check). Each session is
            # handled once, so a replay of an old one cannot put back an old
            # subscription (2026-09-19 review).
            if _claim_plan_session(obj) == "retry":
                return jsonify({"ok": False, "error": "Stripe unreachable; retry"}), 503
        elif etype in ("charge.refunded", "charge.dispute.created"):
            if etype == "charge.refunded":
                _refund_touches_referral(obj.get("customer"),
                                         int(obj.get("amount_refunded") or 0), "refunded")
                # A Release-Ready master paid with this charge stops counting
                # as revenue on the owner's desk (review, 2026-09-19).
                release_ready.money_back(obj.get("payment_intent"), "refunded",
                                         int(obj.get("amount_refunded") or 0))
            else:
                charge = stripe_billing.get_charge(obj.get("charge"))
                if charge is None:
                    return jsonify({"ok": False, "error": "Stripe unreachable; retry"}), 503
                _refund_touches_referral(charge.get("customer"),
                                         int(obj.get("amount") or 0), "disputed")
                release_ready.money_back(obj.get("payment_intent") or charge.get("payment_intent"),
                                         "disputed", int(obj.get("amount") or 0))
        elif etype == "invoice.paid":
            # A referral settles on real money, not on the checkout form.
            user = store.user_by_stripe_customer(obj.get("customer"))
            if user and int(obj.get("amount_paid") or 0) > 0:
                _settle_referrals(user["id"], int(obj.get("amount_paid")))
        elif etype == "customer.subscription.updated":
            # Keeps the plan in step with Stripe whatever changed it: the
            # portal, the dashboard, or a payment retry running out.
            user = store.user_by_stripe_customer(obj.get("customer"))
            held = user and _plan_held(user)
            if user and not held and obj.get("id") and obj.get("id") == user.get("stripe_subscription_id"):
                # An event is a snapshot: a late or repeated one would roll
                # the plan back, so the subscription is read as Stripe holds
                # it now (2026-09-19 review). When it cannot be read, Stripe
                # is asked to send the event again rather than the snapshot
                # being trusted (second review).
                obj = stripe_billing.subscription_state(obj["id"])
                if obj is None:
                    return jsonify({"ok": False, "error": "Stripe unreachable; retry"}), 503
                status = obj.get("status") or ""
                tier = stripe_billing.plan_for_subscription(obj)
                if status in ("active", "trialing") and tier and tier != user.get("plan"):
                    store.set_user_plan(user["id"], tier)
                    store.notify(user["id"], "billing",
                                 "You're on %s" % plans.PLAN_NAMES.get(tier, tier),
                                 "Your subscription changed in Stripe; your plan here "
                                 "follows it.", "/billing")
                elif status in ("unpaid", "incomplete_expired", "canceled"):
                    store.set_user_plan(user["id"], "fan")
                    store.notify(user["id"], "billing", "Plan paused",
                                 "Stripe could not collect your membership, so your "
                                 "plan moved to the free Fan tier. Your data is "
                                 "untouched: update your card in Manage Billing to "
                                 "carry on.", "/billing")
                elif status == "past_due":
                    store.notify(user["id"], "billing", "Payment is past due",
                                 "Stripe could not charge your card. Update it in "
                                 "Manage Billing to keep your plan.", "/billing")
        elif etype == "customer.subscription.deleted":
            # Fan club cancellations first — they aren't plan subscriptions.
            artist_id = store.cancel_club_member_by_subscription(obj.get("id"))
            if artist_id:
                store.notify(artist_id, "fan", "Fan club member left",
                             "A membership was canceled — the fan stays in your CRM.",
                             "/fan-club")
                return jsonify({"ok": True})
            user = store.user_by_stripe_customer(obj.get("customer"))
            # Only the subscription the account is on ends its plan; an old
            # or duplicate one ending must not drop a paying member.
            current_sub = (user or {}).get("stripe_subscription_id")
            held = user and _plan_held(user)
            if user and not held and (not current_sub or current_sub == obj.get("id")):
                store.set_user_plan(user["id"], "fan")
                store.set_stripe_ids(user["id"], user.get("stripe_customer_id"), None)
                store.notify(user["id"], "billing", "Subscription ended",
                             "Your plan moved to the free Fan tier. Your data is "
                             "untouched — resubscribe anytime to unlock it again.",
                             "/billing")
        elif etype == "invoice.payment_failed":
            user = store.user_by_stripe_customer(obj.get("customer"))
            billed = stripe_billing.invoice_subscription_id(obj)
            ours = user and (not billed or billed == user.get("stripe_subscription_id"))
            if ours and not obj.get("next_payment_attempt") and not _plan_held(user) \
                    and user.get("plan") in stripe_billing.PRICES:
                # Stripe has stopped trying. Depending on a dashboard setting
                # it cancels, marks unpaid, or leaves the subscription past
                # due forever, which kept a paid plan with no end (2026-09-19
                # second review). Paying the invoice in Manage Billing brings
                # the plan back through customer.subscription.updated.
                store.set_user_plan(user["id"], "fan")
                store.notify(user["id"], "billing", "Plan paused",
                             "Stripe could not collect your membership and has stopped "
                             "trying, so your plan moved to the free Fan tier. Your data "
                             "is untouched: pay the bill in Manage Billing to carry on.",
                             "/billing")
            elif user:
                store.notify(user["id"], "billing", "Payment failed",
                             "Stripe couldn't charge your card. Update it in "
                             "Manage Billing to keep your plan.", "/billing")
        return jsonify({"ok": True})

    # --- Artist OS: Command Center, Actions, Autopilot, Clean Release ----------

    @app.route("/command-center")
    def command_center_page():
        user = current_user()
        if user is None:
            return login_required_redirect()
        signal = store.get_artist_signal_profile(user["id"])
        signal_ctx = None
        if signal and isinstance(signal.get("priorities"), dict):
            from artist_eq_config import get_artist_eq_config
            channel_keys = [c["key"] for c in get_artist_eq_config()["channels"]]
            vals = [signal["priorities"].get(k, 5) for k in channel_keys]
            # simplified curve: one point per channel on a 300x60 canvas
            span = max(len(vals) - 1, 1)
            pts = " ".join("%d,%d" % (i * 300 // span, 60 - v * 6)
                           for i, v in enumerate(vals))
            updated = (signal.get("_updated") or "")[:10]
            stale = False
            try:
                stale = (datetime.now() -
                         datetime.fromisoformat(signal["_updated"])).days >= 60
            except Exception:
                pass
            signal_ctx = {"profile": signal, "points": pts,
                          "updated": updated, "stale": stale}
        tutor_panel = _tutor_panel(user)
        return render_template(
            "command_center.html", active_page="command-center",
            summary=cc.get_summary(user["id"]),
            cc_alerts=cc.build_alerts(user["id"]),
            cc_actions=cc.open_actions(user["id"]),
            modules=cc.MODULES, module_groups=cc.module_groups(),
            signal=signal_ctx,
            tutor=tutor_panel,
            # The tutor's first stage IS the firstrun checklist, so when
            # it is on the smaller panel steps aside rather than showing
            # the same five steps twice.
            firstrun=None if tutor_panel else _firstrun_panel(user),
            # The Overview's figures, on the same page (2026-09-15).
            **_front_money_context())

    @app.route("/actions", methods=["GET", "POST"])
    def actions_page():
        user = current_user()
        if user is None:
            return login_required_redirect()
        if request.method == "POST":
            f = request.form
            if f.get("action_id"):
                cc.set_action_status(f["action_id"], user["id"], f.get("status") or "new")
            elif (f.get("title") or "").strip():
                cc.create_action(user["id"], f["title"].strip(),
                                 category=f.get("category") or "general",
                                 priority=f.get("priority") or "medium",
                                 description=(f.get("description") or "").strip(),
                                 due_date=(f.get("due_date") or "").strip())
            return redirect("/actions")
        status_filter = request.args.get("status") or None
        all_actions = cc.list_actions(user["id"])
        done = len([a for a in all_actions if a["status"] == "complete"])
        active_n = len([a for a in all_actions
                        if a["status"] in ("new", "in_progress")])
        stats = {"total": len(all_actions), "complete": done,
                 "in_progress": len([a for a in all_actions
                                     if a["status"] == "in_progress"]),
                 "open": active_n,
                 "pct": round(100 * done / len(all_actions)) if all_actions else 0}
        return render_template(
            "actions.html", active_page="actions",
            actions=cc.list_actions(user["id"], status_filter),
            all_actions=all_actions, stats=stats,
            view=request.args.get("view") or "list",
            today=datetime.now(timezone.utc).date().isoformat(),
            status_filter=status_filter or "",
            categories=cc.ACTION_CATEGORIES, priorities=cc.ACTION_PRIORITIES,
            **build_dashboard_context())

    @app.route("/actions/from-alert", methods=["POST"])
    def action_from_alert():
        user = current_user()
        if user is None:
            return login_required_redirect()
        f = request.form
        title = (f.get("title") or "").strip()[:200]
        cc.create_action(user["id"], title,
                         category=f.get("category") or "general", priority="high",
                         description=(f.get("description") or "").strip())
        # It used to redirect to the referrer and say nothing, so pressing
        # "Create recovery action" put you back on the page you were
        # already on with no sign anything had happened - the action was
        # created and invisible. Back to the same page, because an artist
        # reviewing findings usually creates several, but carrying a
        # confirmation and a way to the thing that was made.
        back = request.referrer or "/command-center"
        mark = "&" if "?" in back.split("#")[0] else "?"
        head, _, frag = back.partition("#")
        target = "%s%saction=%s" % (head, mark, urllib.parse.quote(title[:60]))
        return redirect(target + (("#" + frag) if frag else ""))

    def _release_checks(user, campaign):
        """Clean-release + autopilot share one derived checklist."""
        dests = mls.get_destinations(campaign["id"])
        keys = {d["service_key"] for d in dests}
        settings = campaign.get("settings") or {}
        rollouts = ros.list_campaigns(user["id"])
        has_rollout = any(r.get("ml_campaign_id") == campaign["id"] for r in rollouts)
        variants = mls.list_variants(campaign["id"])
        tracks = store.get_catalog_tracks(user["id"])
        title_l = campaign["title"].lower()
        track = next((t for t in tracks if t["title"].lower() == title_l), None)
        epk = store.get_epk(user["id"])
        checks = [
            ("Cover art set", bool(campaign.get("cover_url")),
             "Upload or auto-scan cover art in the campaign builder.", "/links/%s/edit" % campaign["id"], "release"),
            ("Release date set", bool(campaign.get("release_date")),
             "A date drives the pre-save countdown and auto-conversion.", "/links/%s/edit" % campaign["id"], "release"),
            ("Spotify destination", "spotify" in keys,
             "Add the Spotify link (auto-scan can find it).", "/links/%s/edit" % campaign["id"], "smart_link"),
            ("Apple Music destination", "apple_music" in keys or "itunes" in keys,
             "Add the Apple Music link.", "/links/%s/edit" % campaign["id"], "smart_link"),
            ("YouTube destination", "youtube" in keys or "youtube_music" in keys,
             "Add the YouTube link.", "/links/%s/edit" % campaign["id"], "smart_link"),
            ("Campaign published", campaign["status"] == "live",
             "Publish the campaign so the public page is live.", "/links/%s/edit" % campaign["id"], "smart_link"),
            ("Fan capture enabled", bool(settings.get("email_capture")),
             "Own the fan — enable email capture.", "/links/%s/edit" % campaign["id"], "fan_growth"),
            ("Consent copy set", bool(settings.get("consent_text")),
             "Consent text is stored with every signup.", "/links/%s/edit" % campaign["id"], "rights"),
            ("ISRC on catalog track", bool(track and (track.get("meta") or {}).get("isrc")),
             "Add the track to your catalog so identifiers auto-pull.", "/catalog", "metadata"),
            ("Rollout scheduled", has_rollout,
             "Generate the social rollout with tracked links per post.", "/rollout-studio/new", "rollout"),
            ("Promo variants created", bool(variants),
             "Create per-channel variants so every door is measured.", "/links/%s/variants" % campaign["id"], "smart_link"),
            ("Press kit ready", bool(epk and (epk.get("data") or epk.get("photo"))),
             "Update your EPK — press and promoters will ask for it.", "/epk", "release"),
        ]
        passed = sum(1 for _, ok, _, _, _ in checks if ok)
        return checks, round(100 * passed / len(checks))

    def _campaign_picker(user):
        return [c for c in mls.list_campaigns(user["id"]) if not c.get("archived_at")]

    # The checklist grouped into the real release path. Two categories share
    # one meter on purpose: fan capture and consent are one conversation.
    _CHECK_GROUPS = ((("release",), "Release assets"),
                     (("metadata",), "Metadata"),
                     (("smart_link",), "Distribution"),
                     (("fan_growth", "rights"), "Fans & rights"),
                     (("rollout",), "Rollout"))
    _CHECK_LABELS = {k: label for keys, label in _CHECK_GROUPS for k in keys}

    def _check_groups(checks):
        """One meter per group, counted from the checks themselves."""
        out = []
        for keys, label in _CHECK_GROUPS:
            in_cat = [ck for ck in checks if ck[4] in keys]
            out.append({"label": label, "total": len(in_cat),
                        "done": sum(1 for ck in in_cat if ck[1])})
        return out

    @app.route("/releases/autopilot")
    def release_autopilot():
        """The release desk. This page absorbed Clean Release: both rendered
        the same twelve checks against the same campaign, so the checks live
        here once, with the arc, plan and kit around them and the per-track
        Clean Release score below."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        campaigns = _campaign_picker(user)
        selected = request.args.get("campaign") or (campaigns[0]["id"] if campaigns else None)
        campaign = mls.get_campaign(selected, user["id"]) if selected else None
        checks, score = _release_checks(user, campaign) if campaign else ([], 0)
        today = datetime.now(timezone.utc).date().isoformat()
        stage = artist_os.autopilot_stage(
            (campaign or {}).get("release_date"), today)
        plan_days = request.args.get("days")
        plan_days = int(plan_days) if plan_days in ("14", "30", "60") else 14
        kit = plan = days_left = None
        if campaign:
            link_url = request.url_root.rstrip("/") + "/l/" + campaign["slug"]
            kit = artist_os.release_kit(artist_identity.display_name(user),
                                        campaign["title"],
                                        campaign.get("release_date"), link_url)
            plan = artist_os.campaign_plan(plan_days, campaign["title"],
                                           campaign.get("release_date"))
            if campaign.get("release_date"):
                try:
                    days_left = (date.fromisoformat(
                        campaign["release_date"][:10]) -
                        datetime.now(timezone.utc).date()).days
                except ValueError:
                    pass
            # Flag plan windows the calendar has already closed — pure date
            # math against the campaign's own release date.
            plan["windows"] = [
                {"label": lbl, "sub": sub, "tasks": tasks,
                 "passed": days_left is not None and (
                     (lbl.endswith("days out") and
                      days_left < int(lbl.split(" ")[0])) or
                     (lbl == "Release day" and days_left < 0))}
                for lbl, sub, tasks in plan["windows"]]
        # --- the Clean Release half: per Track Passport, not per campaign ---
        osctx = _os_ctx(user["id"])
        os_rows = [{"t": t, "clean": artist_os.clean_release(t, osctx)}
                   for t in store.list_os_tracks(user["id"])]
        # Passport pull: fields a matching Track Passport could fill in the
        # catalog record — shown side-by-side, applied only on click.
        resolves = _passport_resolves(user["id"])
        # In-app ping: a dated track inside 14 days with open items gets one
        # notification (deduped by exact title, so it fires once per date).
        today_d = datetime.now(timezone.utc).date()
        known = {n["title"] for n in store.list_notifications(user["id"], 200)}
        for r in os_rows:
            rd = r["t"].get("release_date") or ""
            try:
                delta = (date.fromisoformat(rd[:10]) - today_d).days
            except ValueError:
                continue
            if 0 <= delta <= 14 and (r["clean"]["blocked"]
                                     or r["clean"]["score"] < 100):
                title = "Release risk: %s drops %s" % (r["t"]["title"], rd)
                if title not in known:
                    store.notify(user["id"], "release_risk", title,
                                 "Clean Release is at %d with %s open. "
                                 "Computed when the checklist ran — clear it "
                                 "before submission." % (
                                     r["clean"]["score"],
                                     "blockers" if r["clean"]["blocked"]
                                     else "open items"),
                                 "/releases/autopilot#clean")
        cal = _release_calendar(user["id"], request.args.get("preset") or "off",
                                keep_args={"campaign": request.args.get("campaign") or "",
                                           "days": request.args.get("days") or ""})
        # ?view=calendar puts the scheduler first and alone. The Calendar
        # tab used to be an anchor to the section at the foot of this same
        # page, which read as "the tab jumps to the bottom and nothing
        # opens". A tab is a view; an anchor is not.
        # ?view=ready is the release check alone: the strip and the twelve
        # derived checks, which the Releases room's card opens (2026-09-15;
        # the card used to open the public page).
        return render_template("release_autopilot.html", active_page="autopilot",
                               view=(request.args.get("view")
                                     if request.args.get("view") in ("calendar", "ready")
                                     else "autopilot"),
                               cal=cal,
                               campaigns=campaigns, c=campaign, checks=checks,
                               open_checks=[ck for ck in checks if not ck[1]],
                               done_checks=[ck for ck in checks if ck[1]],
                               cat_nodes=_check_groups(checks) if campaign else [],
                               cat_labels=_CHECK_LABELS,
                               score=score, stage=stage, stages=artist_os.STAGES,
                               stage_pairs=[(s, s) for s in artist_os.STAGES],
                               kit=kit, plan=plan, plan_days=plan_days,
                               days_left=days_left, os_rows=os_rows,
                               resolves=resolves,
                               **build_dashboard_context())

    @app.route("/releases/autopilot/kit.txt")
    def autopilot_kit_export():
        """The whole release kit + plan as one plain-text bundle for the
        team thread. Same generators, nothing added."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        campaign = mls.get_campaign(request.args.get("campaign") or "",
                                    user["id"])
        if campaign is None:
            abort(404)
        plan_days = request.args.get("days")
        plan_days = int(plan_days) if plan_days in ("14", "30", "60") else 14
        link_url = request.url_root.rstrip("/") + "/l/" + campaign["slug"]
        kit = artist_os.release_kit(artist_identity.display_name(user),
                                    campaign["title"],
                                    campaign.get("release_date"), link_url)
        plan = artist_os.campaign_plan(plan_days, campaign["title"],
                                       campaign.get("release_date"))
        lines = ["RELEASE KIT — %s" % campaign["title"],
                 "Drops: %s · Smart link: %s" % (
                     campaign.get("release_date") or "[set a date]", link_url),
                 "Generated by Street Banker from this campaign's real title,"
                 " date, and link. [Brackets] mark what only you know.", "",
                 "== CAPTIONS =="] + kit["captions"] + [
                "", "== SHORT-FORM IDEAS =="] + kit["shorts"] + [
                "", "== EMAIL ==", "Subject: " + kit["email"]["subject"], "",
                kit["email"]["body"], "", "== SMS ==", kit["sms"], "",
                "== PLAYLIST PITCH ==", kit["pitch"], "",
                "== %d-DAY PLAN ==" % plan_days]
        for w in plan["windows"]:
            lines += ["", "%s — %s" % (w[0], w[1])] + ["- " + t for t in w[2]]
        lines += ["", "== CREATOR BRIEF ==", plan["brief"], "",
                  "== AD TEST CONCEPTS =="] + ["- " + a for a in plan["ads"]]
        return Response("\n".join(lines), mimetype="text/plain; charset=utf-8",
                        headers={"Content-Disposition":
                                 "attachment; filename=release-kit-%s.txt"
                                 % campaign["slug"]})

    @app.route("/releases/clean-release")
    def clean_release():
        """Folded into Release Autopilot. The same twelve checks were
        rendered here and there against the same campaign; now there is one
        desk. The URL stays because the inbox, the certificate and old
        bookmarks point at it - it forwards, campaign kept."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        target = "/releases/autopilot"
        if request.args.get("campaign"):
            target += "?" + urllib.parse.urlencode(
                {"campaign": request.args["campaign"]})
        return redirect(target + "#clean")

    # Passport fields the catalog record does NOT read through the link,
    # as (passport key, catalog meta key, label).
    #
    # ISRC, UPC and Label used to be here too. They were the manual bridge
    # between two copies of the same code: a code typed on the passport
    # sat there until somebody noticed this card and pressed Pull into
    # catalog. db.get_catalog_tracks reads those three through the
    # passport link now (see _META_TO_PASSPORT in db.py), so there is
    # nothing left to pull - offering the button anyway would promise to
    # copy something already visible.
    _RESOLVE_MAP = [("songwriters", "writers", "Songwriters"),
                    ("publishers", "publishers", "Publishers")]

    def _passport_resolves(user_id):
        """Side-by-side diffs: passport fields that exist but are missing on
        the matching catalog record. Real values only, applied on click."""
        os_tracks = store.list_os_tracks(user_id)
        os_by_id = {t["id"]: t for t in os_tracks}
        os_by_title = {t["title"].casefold(): t for t in os_tracks}
        out = []
        for ct in store.get_catalog_tracks(user_id):
            ost = (os_by_id.get(ct.get("passport_track_id") or "")
                   or os_by_title.get((ct["title"] or "").casefold()))
            if ost is None:
                continue
            passport = ost.get("passport") or {}
            meta = ct.get("meta") or {}
            fields = [{"label": lbl, "value": passport[pk]}
                      for pk, mk, lbl in _RESOLVE_MAP
                      if passport.get(pk) and not meta.get(mk)]
            if fields:
                out.append({"catalog_id": ct["id"], "title": ct["title"],
                            "fields": fields})
        return out

    @app.route("/clean-release/resolve", methods=["POST"])
    def clean_release_resolve():
        """Apply one passport pull. Values are recomputed server-side from
        the user's own records — the form only names the catalog row."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        target = request.form.get("catalog_id") or ""
        for ct in store.get_catalog_tracks(user["id"]):
            if ct["id"] != target:
                continue
            ost = (store.get_os_track(user["id"], ct.get("passport_track_id") or "")
                   or next((t for t in store.list_os_tracks(user["id"])
                            if t["title"].casefold() ==
                            (ct["title"] or "").casefold()), None))
            if ost is None:
                break
            passport = ost.get("passport") or {}
            meta = dict(ct.get("meta") or {})
            for pk, mk, _lbl in _RESOLVE_MAP:
                if passport.get(pk) and not meta.get(mk):
                    meta[mk] = passport[pk]
            store.set_catalog_track_meta(user["id"], ct["id"], meta)
            break
        return redirect("/releases/autopilot#clean")

    @app.route("/tracks/<track_id>/certificate")
    def clean_release_certificate(track_id):
        """Print-ready record of a 100-score Clean Release: what was checked,
        what was signed, and when this page was generated. It is a timestamped
        snapshot of Street Banker's own checks — not a legal document."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        track = store.get_os_track(user["id"], track_id)
        if track is None:
            abort(404)
        ctx = _os_ctx(user["id"])
        clean = artist_os.clean_release(track, ctx)
        if clean["blocked"] or clean["score"] < 100:
            return redirect("/releases/autopilot#clean")
        box = artist_os.lockbox_report(track)
        passport = track.get("passport") or {}
        return render_template("clean_certificate.html", user=user, t=track,
                               clean=clean, box=box, passport=passport,
                               generated=datetime.now(timezone.utc)
                               .strftime("%Y-%m-%d %H:%M UTC"))

    _PASSPORT_FIELDS = [("isrc", "ISRC"), ("upc", "UPC"), ("label", "Label"),
                        ("release_date", "Release date"), ("album", "Album"),
                        ("writers", "Songwriters"), ("publishers", "Publishers")]

    def _passport_rows(user_id):
        rows = []
        for t in store.get_catalog_tracks(user_id):
            meta = t.get("meta") or {}
            fields = [{"key": k, "label": lbl, "ok": bool(meta.get(k)),
                       "value": (", ".join(meta[k]) if isinstance(meta.get(k), list)
                                 else (meta.get(k) or ""))}
                      for k, lbl in _PASSPORT_FIELDS]
            done = sum(1 for f in fields if f["ok"])
            rows.append({"track": t, "fields": fields, "done": done,
                         "total": len(fields),
                         "pct": round(100 * done / len(fields))})
        return rows

    @app.route("/metadata-passport")
    def metadata_passport():
        user = current_user()
        if user is None:
            return login_required_redirect()
        rows = _passport_rows(user["id"])
        overall = round(sum(r["pct"] for r in rows) / len(rows)) if rows else 0
        os_rows = [{"t": t, "rep": artist_os.passport_report(t)}
                   for t in store.list_os_tracks(user["id"])]
        return render_template("metadata_passport.html", active_page="identifiers",
                               rows=rows, overall=overall, os_rows=os_rows,
                               # Tracks with a Release-Ready master stored:
                               # a marker, not part of the passport's score.
                               rr_masters=release_ready_store.masters_by_track(user["id"]),
                               field_labels=[lbl for _, lbl in _PASSPORT_FIELDS],
                               **build_dashboard_context())

    @app.route("/metadata-passport/export.csv")
    def metadata_passport_export():
        user = current_user()
        if user is None:
            return login_required_redirect()
        import csv as _csv
        import io as _io
        buf = _io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["title", "artist", "album", "isrc", "upc", "label",
                    "release_date", "writers", "publishers"])
        for t in store.get_catalog_tracks(user["id"]):
            m = t.get("meta") or {}
            w.writerow([t["title"], t["artist"], m.get("album") or t["album"],
                        m.get("isrc") or "", m.get("upc") or "",
                        m.get("label") or "", m.get("release_date") or "",
                        "; ".join(m.get("writers") or []),
                        "; ".join(m.get("publishers") or [])])
        return Response(buf.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition": "attachment; filename=metadata-passport.csv"})

    # --- Fan Club: recurring fan memberships through Stripe ---------------------

    @app.route("/fan-club", methods=["GET", "POST"])
    def fan_club():
        user = current_user()
        if user is None:
            return login_required_redirect()
        if request.method == "POST":
            try:
                price = max(1.0, min(float(request.form.get("price") or 5), 500.0))
            except ValueError:
                price = 5.0
            perks = [p.strip() for p in (request.form.get("perks") or "").splitlines()
                     if p.strip()][:8]
            store.save_fan_club(user["id"], (request.form.get("name") or "").strip(),
                                (request.form.get("blurb") or "").strip(),
                                round(price * 100), perks,
                                request.form.get("active") == "1")
            return redirect("/fan-club")
        club = store.get_fan_club(user["id"])
        members = store.list_club_members(user["id"])
        active_members = [m for m in members if m["status"] == "active"]
        slug = _ensure_epk_slug(user)
        return render_template("fan_club.html", active_page="fan-club",
                               club=club, members=members,
                               drops=store.list_club_drops(user["id"]),
                               active_count=len(active_members),
                               mrr=round(len(active_members)
                                         * (club["price_cents"] if club else 0) / 100, 2),
                               club_url="/club/" + slug,
                               stripe_live=stripe_billing.configured(),
                               sales_open=sales_switch.is_on(),
                               sales_closed=sales_switch.CLOSED,
                               **build_dashboard_context())

    @app.route("/club/<slug>")
    def club_public(slug):
        prof = store.get_epk_by_slug(slug)
        club = store.get_fan_club(prof["user_id"]) if prof else None
        if prof is None or club is None or not club["active"]:
            abort(404)
        sid = request.args.get("session_id")
        if sid and request.args.get("joined"):
            # Trust only what Stripe says about the session, never the URL.
            sess = stripe_billing.get_checkout_session(sid)
            meta = (sess or {}).get("metadata") or {}
            if (sess and sess.get("payment_status") == "paid"
                    and meta.get("kind") == "fan_club"
                    and meta.get("artist_id") == prof["user_id"]
                    and meta.get("member_email")):
                email = meta["member_email"].lower()
                new_id = store.add_club_member(
                    prof["user_id"], email, sess.get("customer"),
                    sess.get("subscription"))
                fan_id = mls.upsert_fan(prof["user_id"], email, None)
                if new_id:
                    mls.add_consent(fan_id, None, "fan_club",
                                    "Paid fan club membership via Stripe checkout.")
                    store.notify(prof["user_id"], "fan", "New fan club member",
                                 "%s joined your fan club." % email, "/fan-club")
                session.permanent = True
                session["club_member_" + prof["user_id"]] = email
                return redirect("/club/" + slug + "/members")
        return render_template("club_public.html", club=club, slug=slug,
                               artist_name=prof["user_name"],
                               joined=bool(request.args.get("joined")),
                               stripe_live=stripe_billing.configured(),
                               sales_open=sales_switch.is_on(),
                               sales_closed=sales_switch.CLOSED)

    @app.route("/club/<slug>/join", methods=["POST"])
    def club_join(slug):
        prof = store.get_epk_by_slug(slug)
        club = store.get_fan_club(prof["user_id"]) if prof else None
        if prof is None or club is None or not club["active"]:
            abort(404)
        email = (request.form.get("email") or "").strip().lower()
        # Paid joins wait for the owner's switch (sales_switch).
        if "@" not in email or not stripe_billing.configured() or not sales_switch.is_on():
            return redirect("/club/" + slug)
        session_obj = stripe_billing.create_club_checkout(
            prof["user_id"], club["name"], club["price_cents"], email, slug,
            request.url_root.rstrip("/"))
        if not session_obj or not session_obj.get("url"):
            return redirect("/club/" + slug)
        return redirect(session_obj["url"], code=303)

    def _club_serializer():
        from itsdangerous import URLSafeTimedSerializer
        return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="club-member")

    def _club_or_404(slug):
        prof = store.get_epk_by_slug(slug)
        club = store.get_fan_club(prof["user_id"]) if prof else None
        if prof is None or club is None:
            abort(404)
        return prof, club

    @app.route("/club/<slug>/members")
    def club_members_area(slug):
        # Members keep access while their subscription is active, even if the
        # artist later closes the club to new joins.
        prof, club = _club_or_404(slug)
        token = request.args.get("token")
        if token:
            from itsdangerous import BadSignature, SignatureExpired
            try:
                data = _club_serializer().loads(token, max_age=7 * 86400)
            except (BadSignature, SignatureExpired):
                data = None
            if data and data.get("artist_id") == prof["user_id"]:
                session.permanent = True
                session["club_member_" + prof["user_id"]] = data.get("email", "")
            return redirect("/club/" + slug + "/members")
        email = session.get("club_member_" + prof["user_id"])
        member = store.get_active_club_member(prof["user_id"], email) if email else None
        if member is None:
            return render_template("club_members.html", mode="gate", club=club,
                                   slug=slug, artist_name=prof["user_name"],
                                   email_live=emailer.configured(),
                                   sent=request.args.get("sent"),
                                   email_error=request.args.get("email_error"))
        return render_template("club_members.html", mode="feed", club=club,
                               slug=slug, artist_name=prof["user_name"],
                               member_email=email,
                               drops=store.list_club_drops(prof["user_id"]))

    @app.route("/club/<slug>/members/link", methods=["POST"])
    def club_members_link(slug):
        prof, club = _club_or_404(slug)
        email = (request.form.get("email") or "").strip().lower()
        member = (store.get_active_club_member(prof["user_id"], email)
                  if "@" in email else None)
        if member:
            token = _club_serializer().dumps(
                {"artist_id": prof["user_id"], "email": email})
            link = (request.url_root.rstrip("/") + "/club/" + slug
                    + "/members?token=" + token)
            ok = emailer.send(
                email, "Your %s access link" % (club["name"] or "fan club"),
                '<p>Tap to open the members area for <b>%s</b>:</p>'
                '<p><a href="%s">%s</a></p>'
                '<p style="color:#91836A;font-size:12px">The link works for 7 days '
                'and keeps you signed in on this device.</p>'
                % (club["name"] or "the fan club", link, link), reply_to=(store.get_user(prof["user_id"]) or {}).get("email") or None)
            if not ok:
                # Honesty first: the send failed (sandbox until a domain is
                # verified), so don't tell anyone to go check their inbox.
                return redirect("/club/" + slug + "/members?email_error=1")
        return redirect("/club/" + slug + "/members?sent=1")

    @app.route("/fan-club/drops", methods=["POST"])
    def fan_club_drop_post():
        user = current_user()
        if user is None:
            return login_required_redirect()
        title = (request.form.get("title") or "").strip()
        if not title:
            return redirect("/fan-club")
        body = (request.form.get("body") or "").strip()
        store.add_club_drop(user["id"], title, body,
                            (request.form.get("link_url") or "").strip())
        club = store.get_fan_club(user["id"])
        if not emailer.configured() or not club:
            return redirect("/fan-club?posted=1&email_off=1")
        import html as _html
        notified = failed = 0
        slug = _ensure_epk_slug(user)
        base = request.url_root.rstrip("/")
        for m in store.list_club_members(user["id"])[:200]:
            if m["status"] != "active":
                continue
            token = _club_serializer().dumps(
                {"artist_id": user["id"], "email": m["member_email"]})
            link = base + "/club/" + slug + "/members?token=" + token
            ok = emailer.send(
                m["member_email"],
                "%s: new members-only drop" % (club["name"] or "Fan club"),
                '<div style="font-family:sans-serif;max-width:480px">'
                '<p style="color:#8A6E30;font-weight:800;letter-spacing:2px;'
                'text-transform:uppercase;font-size:12px">%s</p>'
                '<h2 style="margin:6px 0 12px">%s</h2>%s'
                '<p style="margin-top:18px"><a href="%s" style="background:#E8B950;'
                'color:#14100A;padding:11px 20px;border-radius:10px;'
                'text-decoration:none;font-weight:800">Open the drop</a></p>'
                '<p style="color:#91836A;font-size:12px">This link signs you '
                'straight in and works for 7 days.</p></div>'
                % (_html.escape(artist_identity.display_name(user)
                                or "Your artist"),
                   _html.escape(title),
                   ('<p style="color:#3A3226">%s</p>' % _html.escape(body[:300])
                    if body else ""),
                   link), reply_to=user["email"])
            if ok:
                notified += 1
            else:
                failed += 1
        return redirect("/fan-club?posted=1&notified=%d&failed=%d"
                        % (notified, failed))

    @app.route("/fan-club/drops/<drop_id>/delete", methods=["POST"])
    def fan_club_drop_delete(drop_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_club_drop(user["id"], drop_id)
        return redirect("/fan-club")

    # --- Label Mode: real roster seats for the Label tier -------------------------

    def _artist_snapshot(aid, today):
        rows = store.get_statement_rows(aid)
        return {
            "revenue": round(sum(r["amount"] for r in rows), 2),
            "statements": len(store.get_statements(aid)),
            "fans": len(mls.list_fans(aid)),
            "links": [c for c in mls.list_campaigns(aid)
                      if c["status"] == "live" and not c.get("archived_at")],
            "shows": [s for s in store.list_tour_shows(aid)
                      if s["date"] >= today and s["status"] in ("confirmed", "advanced")],
        }

    @app.route("/roster")
    def roster():
        user = current_user()
        if user is None:
            return login_required_redirect()
        members = store.list_roster(user["id"])
        today = datetime.now(timezone.utc).date().isoformat()
        stats, totals = [], {"revenue": 0.0, "fans": 0, "links": 0, "shows": 0}
        calendar = []
        for m in members:
            if m["status"] != "active" or not m["artist_user_id"]:
                continue
            snap = _artist_snapshot(m["artist_user_id"], today)
            _t, _c, osum, ocert = _os_full(m["artist_user_id"])
            for c in mls.list_campaigns(m["artist_user_id"]):
                rd = c.get("release_date") or ""
                if rd >= today:
                    calendar.append({"date": rd, "title": c["title"],
                                     "artist": m.get("artist_name") or m["email"]})
            stats.append({"m": m, "revenue": snap["revenue"], "fans": snap["fans"],
                          "links": len(snap["links"]), "shows": len(snap["shows"]),
                          "os": osum, "cert": ocert["level"]})
            totals["revenue"] = round(totals["revenue"] + snap["revenue"], 2)
            totals["fans"] += snap["fans"]
            totals["links"] += len(snap["links"])
            totals["shows"] += len(snap["shows"])
        calendar.sort(key=lambda c: c["date"])
        return render_template("roster.html", active_page="roster",
                               members=members, stats=stats, totals=totals,
                               calendar=calendar[:10],
                               **build_dashboard_context())

    @app.route("/roster/export.csv")
    def roster_export():
        user = current_user()
        if user is None:
            return login_required_redirect()
        import csv as _csv
        import io as _io
        today = datetime.now(timezone.utc).date().isoformat()
        buf = _io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["artist", "email", "statement_revenue", "fans", "live_links",
                    "upcoming_shows", "tracks", "passport_avg_pct",
                    "clean_release_avg", "red_rights_issues", "certification"])
        for m in store.list_roster(user["id"]):
            if m["status"] != "active" or not m["artist_user_id"]:
                continue
            snap = _artist_snapshot(m["artist_user_id"], today)
            _t, _c, osum, ocert = _os_full(m["artist_user_id"])
            w.writerow([m.get("artist_name") or "", m["email"], snap["revenue"],
                        snap["fans"], len(snap["links"]), len(snap["shows"]),
                        osum["tracks"], osum["passport_avg"], osum["clean_avg"],
                        osum["reds"], ocert["level"]])
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition":
                                 "attachment; filename=roster-report.csv"})

    def _may_seat(user, kind):
        """May this account put somebody else on Street Banker?

        Until 2026-09-17 the answer was "anybody signed in", which was
        harmless only because the invitations could not be redeemed while
        sign-up was shut. Now they can, so the question is real.

        A roster is a Label feature, so roster seats need the Label plan.
        Team is for every tier - a manager, an accountant, an attorney -
        so a team seat needs any paid plan, and Fan is not one. The owner
        may always seat anybody, which is how the owner has always worked.
        """
        if user is None:
            return False
        if _is_owner_email(user.get("email")):
            return True
        plan = (user.get("plan") or "artist").lower()
        if kind == "roster":
            return plan == "label"
        return plan in ("artist", "pro", "label")

    _NO_SEAT = {
        "roster": "A roster comes with the Label membership.",
        "team": "Inviting your team comes with a paid membership.",
    }

    _JOIN_NEEDS_PASSWORD = ("This email already has a Street Banker account. "
                            "Enter its password to accept, or sign in as it first.")

    def _join_existing_ok(existing):
        """May this request attach the invitation to an account that
        already exists? Only its owner may: someone already signed in as
        exactly that account, or someone who types its password here.

        Both join doors used to sign the visitor into the existing account
        from the token alone. Anyone who could mint an invitation, which is
        any paid account for a team seat, could invite a stranger's address
        (or the owner's), open the link themselves and be signed in as that
        person with no password (found by the 2026-09-18 launch check). The
        token proves the invitation was sent; it never proved who opened it.
        Returns (ok, error)."""
        me = current_user()
        if me is not None and me["id"] == existing["id"]:
            return True, None
        password = request.form.get("password") or ""
        if not password or not check_password_hash(existing["password_hash"], password):
            return False, _JOIN_NEEDS_PASSWORD
        shut = store.account_shut(existing)
        if shut and not _is_owner_email(existing.get("email")):
            return False, ("Your guest access has ended. Contact Street Banker to continue."
                           if shut == "ended" else
                           "This account is locked. Contact Street Banker to continue.")
        return True, None

    def _signed_in_as(email):
        me = current_user()
        return bool(me and (me.get("email") or "").lower() == (email or "").lower())

    @app.route("/roster/invite", methods=["POST"])
    def roster_invite():
        user = current_user()
        if user is None:
            return login_required_redirect()
        if not _may_seat(user, "roster"):
            return redirect("/upgrade?why=roster")
        email = (request.form.get("email") or "").strip().lower()
        if "@" in email and email != user["email"].lower():
            invite = store.add_roster_invite(user["id"], email)
            if invite and invite.get("invite_token") and emailer.configured():
                # Best-effort — the join link stays visible on the roster
                # either way, so a sandbox-blocked send loses nothing.
                link = (request.url_root.rstrip("/") + "/roster/join/"
                        + invite["invite_token"])
                emailer.send(email, "%s wants you on their roster" % user["name"],
                             '<p><b>%s</b> runs their label on Street Banker and '
                             'wants to add you to the roster (they see read-only '
                             'stats, never your login).</p>'
                             '<p><a href="%s">Accept the invite</a></p>'
                             % (user["name"], link), reply_to=user["email"])
        return redirect("/roster")

    @app.route("/roster/join/<token>", methods=["GET", "POST"])
    def roster_join(token):
        invite = store.get_roster_invite(token)
        if invite is None:
            return render_template("roster_join.html", invalid=True,
                                   invite=None, error=None, has_account=False)
        if request.method == "POST":
            existing = store.get_user_by_email(invite["email"])
            if existing:
                ok, why = _join_existing_ok(existing)
                if not ok:
                    return render_template(
                        "roster_join.html", invalid=False, invite=invite,
                        has_account=True, signed_in_as_invitee=False,
                        error=why), 403
                artist_id = existing["id"]
            else:
                if not _signup_open():
                    return render_template(
                        "roster_join.html", invalid=False, invite=invite,
                        has_account=False, closed=True, error=_MEMBER_LINK_SHUT), 403
                # With sign-up open, the invitation is the authorisation,
                # the way /signup?invite= is. What is checked is the label:
                # still an account, and still on the plan that may seat
                # somebody. A downgrade ends its pending invitations.
                label = store.get_user(invite["label_id"])
                if not _may_seat(label, "roster"):
                    return render_template(
                        "roster_join.html", invalid=False, invite=invite,
                        has_account=False, error=_INVITE_ONLY), 403
                name = (request.form.get("name") or "").strip()
                password = request.form.get("password") or ""
                if not name or len(password) < 6:
                    return render_template(
                        "roster_join.html", invalid=False, invite=invite,
                        has_account=False,
                        error="Enter your name and a password of 6+ characters.")
                artist_id = store.create_user(invite["email"], name,
                                              generate_password_hash(password))
            store.accept_roster_invite(token, artist_id)
            store.notify(invite["label_id"], "team", "Roster invite accepted",
                         "%s is now on your roster." % invite["email"], "/roster")
            session["user_id"] = artist_id
            return redirect("/command-center")
        return render_template("roster_join.html", invalid=False, invite=invite,
                               has_account=store.get_user_by_email(invite["email"]) is not None,
                               signed_in_as_invitee=_signed_in_as(invite["email"]),
                               closed=not _signup_open(), error=None)

    @app.route("/roster/artist/<artist_id>")
    def roster_artist(artist_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        member = store.get_roster_member(user["id"], artist_id)
        if member is None:
            abort(404)
        today = datetime.now(timezone.utc).date().isoformat()
        snap = _artist_snapshot(artist_id, today)
        return render_template("roster_artist.html", active_page="roster",
                               member=member, snap=snap,
                               # Release-Ready work, status only: no audio,
                               # no downloads, no buying (label view).
                               rr_rows=release_ready_store.status_rows(artist_id),
                               **build_dashboard_context())

    @app.route("/roster/<member_id>/remove", methods=["POST"])
    def roster_remove(member_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.remove_roster_member(user["id"], member_id)
        return redirect("/roster")

    # --- Artist Hub: the one link-in-bio URL, assembled from real data -----------

    @app.route("/@<slug>")
    def artist_hub(slug):
        prof = store.get_epk_by_slug(slug)
        if prof is None:
            abort(404)
        uid = prof["user_id"]
        data = prof["data"]
        club = store.get_fan_club(uid)
        campaigns = [c for c in mls.list_campaigns(uid)
                     if c["status"] == "live" and not c.get("archived_at")]
        today = datetime.now(timezone.utc).date().isoformat()
        shows = [s for s in store.list_tour_shows(uid)
                 if s["date"] >= today and s["status"] in ("confirmed", "advanced")]
        return render_template("artist_hub.html", prof=prof, data=data,
                               artist_name=prof["user_name"], slug=slug,
                               club=(club if club and club["active"] else None),
                               campaigns=campaigns[:8], shows=shows[:8],
                               store_url=data.get("store_url", ""),
                               merch=data.get("merch", []))

    # --- Artist OS spine: tracks + engines ----------------------------------------

    def _os_ctx(user_id):
        """Real account signals only — every key names where it came from."""
        rows = store.get_statement_rows(user_id)
        campaigns = [c for c in mls.list_campaigns(user_id)
                     if c["status"] == "live" and not c.get("archived_at")]
        return {
            "statement_rows": len(rows),
            "statement_total": round(sum(r["amount"] for r in rows), 2),
            "lanes_with_data": artist_os.lanes_from_sources(
                r.get("source") for r in rows),
            "live_links": len(campaigns),
            "fans": len(mls.list_fans(user_id)),
            "club_members": len([m for m in store.list_club_members(user_id)
                                 if m["status"] == "active"]),
            "sync_active": bool(store.list_sync_packs(user_id)),
            # A future-dated campaign is what the scheduler and pitch
            # windows read; a rollout campaign means generated assets exist.
            "release_scheduled": any(
                (c.get("release_date") or "") >=
                datetime.now(timezone.utc).date().isoformat()
                for c in mls.list_campaigns(user_id)
                if not c.get("archived_at")),
            "rollout_assets": bool(ros.list_campaigns(user_id)),
        }

    def _os_summary(user_id, tracks, ctx):
        if not tracks:
            return {"tracks": 0, "passport_avg": 0, "clean_avg": 0, "reds": 0,
                    "lanes_connected": 0, "lockbox_ready": 0,
                    "fans": ctx["fans"], "statement_rows": ctx["statement_rows"]}
        reports = [artist_os.passport_report(t) for t in tracks]
        cleans = [artist_os.clean_release(t, ctx) for t in tracks]
        boxes = [artist_os.lockbox_report(t) for t in tracks]
        lanes = artist_os.lane_grid(tracks[0], ctx)
        return {
            "tracks": len(tracks),
            "passport_avg": round(sum(r["pct"] for r in reports) / len(reports)),
            "clean_avg": round(sum(c["score"] for c in cleans) / len(cleans)),
            "reds": sum(r["reds"] for r in reports),
            "lanes_connected": len([l for l in lanes if l["state"] == "connected"]),
            "lockbox_ready": len([b for b in boxes if b["caps"]["release"]]),
            "fans": ctx["fans"], "statement_rows": ctx["statement_rows"],
        }

    @app.route("/tracks")
    def os_tracks():
        """Folded into the catalog (tier C, 2026-09-09). This page listed
        the same songs as /catalog from a second table; the two tables now
        point at each other and the catalog shows each song once with its
        passport state. The passport itself stays at /tracks/<id>.

        Catalog is a Pro page and this was an Artist one (plans.py, left
        as it is): an Artist-plan account would meet an upgrade card at the
        redirect, so for that plan the section renders here on its own."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if plans.allowed(user.get("plan") or "artist", plans.required_tier("/catalog")):
            # Keep the one query the passports section reads, so an old
            # /tracks?discogs=<id> link still opens that song's lookup.
            looked_up = request.args.get("discogs")
            return redirect("/catalog?view=passports" + ("&discogs=%s" % urllib.parse.quote(looked_up) if looked_up else ""))
        ctx = build_dashboard_context()
        ctx["my_tracks"] = store.get_catalog_tracks(user["id"])
        ctx.update(_passport_section(user, ctx["my_tracks"]))
        return render_template("os_tracks.html", active_page="catalog", **ctx)

    # CSV column -> passport field, for catalog migrations.
    _CSV_PASSPORT = {"isrc": "isrc", "upc": "upc", "writers": "songwriters",
                     "songwriters": "songwriters", "producers": "producers",
                     "publishers": "publishers", "pro": "pro",
                     "label": "label", "master_owner": "master_owner",
                     "catalog_number": "catalog_number",
                     "catno": "catalog_number"}

    def _passports_home(user):
        """Where the passport forms land: the catalog section for a plan
        that has the Catalog page, the passports page for one that has not."""
        if plans.allowed(user.get("plan") or "artist", plans.required_tier("/catalog")):
            return "/catalog?view=passports"
        return "/tracks"

    @app.route("/tracks/import", methods=["POST"])
    def os_tracks_import():
        """Bulk CSV import: title required per row; known metadata columns
        land straight in each new passport."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        f = request.files.get("csv")
        if f is None or not f.filename:
            return redirect(_passports_home(user))
        import csv as _csv
        import io as _io
        try:
            text = f.read().decode("utf-8-sig", errors="replace")
            reader = _csv.DictReader(_io.StringIO(text))
            made = 0
            for row in reader:
                if made >= 200:
                    break
                low = {(k or "").strip().lower(): (v or "").strip()
                       for k, v in row.items()}
                title = low.get("title") or low.get("track") or low.get("track_title")
                if not title:
                    continue
                tid = store.add_os_track(user["id"], title[:120],
                                         (low.get("release") or low.get("album") or "")[:120],
                                         (low.get("release_date") or low.get("date") or "")[:10])
                passport = {pf: low[col] for col, pf in _CSV_PASSPORT.items()
                            if low.get(col)}
                if passport:
                    store.update_os_track_passport(user["id"], tid, passport)
                made += 1
        except (UnicodeDecodeError, _csv.Error):
            pass
        return redirect(_passports_home(user))

    @app.route("/tracks/add", methods=["POST"])
    def os_tracks_add():
        user = current_user()
        if user is None:
            return login_required_redirect()
        title = (request.form.get("title") or "").strip()
        if title:
            store.add_os_track(user["id"], title,
                               (request.form.get("release_title") or "").strip(),
                               (request.form.get("release_date") or "").strip())
        return redirect(_passports_home(user))

    @app.route("/tracks/<track_id>")
    def os_track_detail(track_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        track = store.get_os_track(user["id"], track_id)
        if track is None:
            abort(404)
        ctx = _os_ctx(user["id"])
        return render_template("os_track_detail.html", active_page="catalog",
                               track=track, passports_home=_passports_home(user),
                               mlc=_track_mlc_state(user["id"], track),
                               passport=artist_os.passport_report(track),
                               clean=artist_os.clean_release(track, ctx),
                               lanes=artist_os.lane_grid(track, ctx),
                               lockbox=artist_os.lockbox_report(track),
                               fields=artist_os.PASSPORT_FIELDS,
                               passport_notes=artist_os.PASSPORT_NOTES,
                               rr_master=_rr_master_block(user["id"], track),
                               **build_dashboard_context())

    def _rr_master_block(user_id, track):
        """The Release-Ready master stored for this Track Passport, if any:
        when, a download through the owner-checked route, and where next.
        Not part of the passport's completeness score."""
        job = release_ready_store.masters_by_track(user_id).get(track["id"])
        if not job:
            return None
        title = (track.get("title") or "").strip()
        src = release_ready_store.get_source(job["source_id"]) or {}
        # The upload's page is gone once the upload is deleted, so this
        # block is where the master is deleted from then (review, 2026-09-19).
        # Only the account holder: a seat cannot delete a paid master.
        seat = bool(session.get("team_as") or session.get("acting_as"))
        return {"stored_at": release_ready.day(job.get("stored_at")),
                "note": "Mastered by RoEx through Release-Ready",
                "format": release_ready.master_format(job),
                "download": job.get("output_url"),
                "bytes": job.get("master_bytes"),
                "source": ("%s/sources/%s" % (release_ready.PAGE, job["source_id"])
                           if src and not src.get("deleted_at") else None),
                "delete_url": ("%s/jobs/%s/master/delete" % (release_ready.PAGE, job["id"])
                               if not seat else None),
                "smart_link": "/links/new?" + urllib.parse.urlencode({"title": title}),
                "rollout": "/rollout-studio/new"}

    def _track_mlc_state(user_id, track):
        """What the passport page may say about The MLC: whether the
        registry is connected, what a check would ask, and the checks so
        far. Nothing here is a registration status - that stays the
        field the artist fills, until a check by ISRC matches."""
        import signal_providers as sp
        passport = track.get("passport") or {}
        return {
            "on": sp.mlc_adapter().configured(),
            "isrc": (passport.get("isrc") or "").strip().upper(),
            "artist": (passport.get("artist_name") or "").strip(),
            "evidence": artist_os.mlc_evidence(track),
            "checks": store.list_track_mlc_checks(user_id, track["id"]),
            "note": {
                "off": "The MLC is not connected on this service.",
                "need": "Add an ISRC, or at least an artist name, to the passport first.",
            }.get(request.args.get("mlc") or "", ""),
        }

    @app.route("/tracks/<track_id>/mlc", methods=["POST"])
    def os_track_mlc(track_id):
        """Ask The MLC about this track, on the artist's say-so, and keep
        the answer. 'fill' copies names from a stored match into passport
        fields that are still empty - a name they typed is a decision, a
        name the registry holds is evidence, and evidence never overwrites
        a decision."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        track = store.get_os_track(user["id"], track_id)
        if track is None:
            abort(404)
        import signal_providers as sp
        adapter = sp.mlc_adapter()
        if not adapter.configured():
            return redirect("/tracks/%s?mlc=off#mlc" % track_id)
        passport = track.get("passport") or {}
        if request.form.get("action") == "fill" and request.form.get("check_id"):
            check = store.get_track_mlc_check(user["id"], request.form["check_id"])
            if check and check["track_id"] == track_id and check["works"]:
                work = check["works"][0]
                fills = {}
                writers = ", ".join(w.get("name") for w in work.get("writers") or [] if w.get("name"))
                pubs = ", ".join(x.get("name") for x in work.get("publishers") or [] if x.get("name"))
                if writers and not (passport.get("songwriters") or "").strip():
                    fills["songwriters"] = writers[:200]
                if pubs and not (passport.get("publishers") or "").strip():
                    fills["publishers"] = pubs[:200]
                # The registration status is NOT written here any more.
                # It used to compose a sentence into mlc_status, and the
                # engines then graded that sentence - evidence laundered
                # into prose, and indistinguishable afterwards from a
                # sentence the artist typed. The check itself is the
                # record; artist_os.mlc_evidence reads it.
                if fills:
                    passport.update(fills)
                    store.update_os_track_passport(user["id"], track_id, passport)
            return redirect("/tracks/%s#mlc" % track_id)
        isrc = (passport.get("isrc") or "").strip().upper()
        artist = (passport.get("artist_name") or "").strip()
        if isrc:
            asked, args = "ISRC " + isrc, {"isrc": isrc}
        elif artist:
            asked, args = "%s by %s" % (track["title"], artist), {"title": track["title"], "artist": artist}
        else:
            return redirect("/tracks/%s?mlc=need#mlc" % track_id)
        try:
            works = adapter.lookup(**args)["works"]
            result, message = ("match" if works else "none"), ""
        except sp.ProviderError as e:
            works, result, message = [], "error", str(e)
        store.add_track_mlc_check(user["id"], track_id, asked, result, message, works)
        return redirect("/tracks/%s#mlc" % track_id)

    @app.route("/tracks/<track_id>/passport", methods=["POST"])
    def os_track_passport(track_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        track = store.get_os_track(user["id"], track_id)
        if track is None:
            abort(404)
        passport = track["passport"]
        for key, _label, _crit, _fix in artist_os.PASSPORT_FIELDS:
            passport[key] = (request.form.get(key) or "").strip()[:200]
        for key, _label, _hint in artist_os.PASSPORT_NOTES:
            passport[key] = (request.form.get(key) or "").strip()[:200]
        for extra in ("audio_ok", "artwork_ok"):
            passport[extra] = "1" if request.form.get(extra) else ""
        store.update_os_track_passport(user["id"], track_id, passport)
        return redirect("/tracks/" + track_id)

    @app.route("/royalty-lanes")
    def royalty_lanes():
        """Folded into Royalties (owner, 2026-09-13): the nine lanes per
        track are the matrix on that page. The queue keeps its own page."""
        return redirect("/royalties#lanes")

    @app.route("/money-queue")
    def money_queue():
        user = current_user()
        if user is None:
            return login_required_redirect()
        tracks = store.list_os_tracks(user["id"])
        ctx = _os_ctx(user["id"])
        queue = artist_os.action_queue([(t, ctx) for t in tracks])
        est_total = round(sum(a["impact"] or 0 for a in queue), 2)
        criticals = len([a for a in queue if a["critical"]])
        # Settled tour income: money already collected, shown beside the money
        # still missing. TOUR's settlements (tour_show_ext, marked settled with
        # an amount) are read first; a legacy Tour Hub settlement blob counts
        # only for a show that has no TOUR settlement, so a sheet saved on
        # the old hub still comes out as the walk-away it computed.
        tour_settlements = tour_store.settled_income(user["id"])
        tour_income = round(sum(tour_settlements.values()), 2)
        tour_settled = len(tour_settlements)
        for s in store.list_tour_shows(user["id"]):
            if s["id"] in tour_settlements or s["status"] != "settled":
                continue
            try:
                st = json.loads(s.get("settlement") or "{}")
            except ValueError:
                continue
            if st:
                tour_income = round(
                    tour_income + touring.settlement_totals(st)["walk"], 2)
                tour_settled += 1
        return render_template("money_queue.html", active_page="royalties",
                               queue=queue, est_total=est_total,
                               criticals=criticals, ctx=ctx,
                               tour_income=tour_income,
                               tour_settled=tour_settled,
                               **build_dashboard_context())

    def _os_full(user_id):
        tracks = store.list_os_tracks(user_id)
        ctx = _os_ctx(user_id)
        summary = _os_summary(user_id, tracks, ctx)
        return tracks, ctx, summary, artist_os.certification(summary)

    @app.route("/certified")
    def certified_page():
        user = current_user()
        if user is None:
            return login_required_redirect()
        tracks, ctx, summary, cert = _os_full(user["id"])
        return render_template("certified.html", active_page="certified",
                               cert=cert, summary=summary,
                               **build_dashboard_context())

    @app.route("/deal-room/onesheet")
    def deal_onesheet():
        """The Deal Room one-sheet is the press kit now (owner, 2026-09-19:
        "there's way too many one sheets... It just needs to be an EPK").
        What this page carried that the kit lacked - certification, the
        statement figures, rights position, lanes, the ask - is the kit's
        optional For deals section, built by _deal_facts() below."""
        return redirect("/epk", code=301)

    def _deal_facts(user_id):
        """The deal-facing figures the Deal Room one-sheet used to print,
        for the press kit's For deals section. Every line names its
        basis; nothing here is a number the app invented."""
        tracks, ctx, summary, cert = _os_full(user_id)
        reports = sorted(
            [{"title": t["title"], "score": artist_os.clean_release(t, ctx)["score"]}
             for t in tracks], key=lambda r: -r["score"])
        today = datetime.now(timezone.utc).date().isoformat()
        upcoming = [c for c in mls.list_campaigns(user_id)
                    if (c.get("release_date") or "") >= today]
        lanes = artist_os.lane_grid(tracks[0], ctx) if tracks else []
        # Only the Pulse readings that carry a number: a snapshot can say
        # "not measured", and a growth claim built out of two silences is
        # not a claim this sheet can put in front of a label.
        pulse = store.list_pulse_snapshots(user_id, limit=30)
        counted = [p for p in pulse if p.get("followers") is not None]
        growth = None
        if len(counted) >= 2:
            growth = {"first": counted[0], "last": counted[-1],
                      "delta": counted[-1]["followers"] - counted[0]["followers"]}
        return {
            "cert": cert, "summary": summary,
            "statement_rows": ctx.get("statement_rows") or 0,
            "statement_total": ctx.get("statement_total") or 0.0,
            "fans": ctx.get("fans") or 0,
            "top": reports[:6],
            "lanes_claimed": [l["label"] for l in lanes if l["state"] == "claimed"],
            "upcoming": upcoming[:5],
            "growth": growth, "pulse_count": len(pulse), "counted": counted,
            "today": today,
        }

    @app.route("/onesheet/share", methods=["POST"])
    def onesheet_share_save():
        """Share settings for the old /sheet/<token> page. The page that
        held this form redirects to the press kit now (2026-09-19); links
        already sent keep answering, and the press kit's own private pitch
        link is the replacement. Everything on the public sheet resolves
        through the artist's own vault listing - nothing else is reachable
        by id."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        action = request.form.get("action") or "save"
        if action == "disable":
            store.delete_onesheet_share(user["id"])
            return redirect("/epk")
        share = store.get_onesheet_share(user["id"])
        token = (uuid.uuid4().hex[:20] if (share is None or action == "regenerate")
                 else share["token"])
        pin = "".join(c for c in (request.form.get("pin") or "") if c.isdigit())[:8]
        if pin and len(pin) < 4:
            pin = ""
        vault = {v["id"]: v for v in store.list_vault_files(user["id"])}
        banner = ""
        pick = request.form.get("banner") or ""
        if pick in vault and vault[pick]["path"].rsplit(".", 1)[-1].lower() in (
                "png", "jpg", "jpeg", "webp", "gif"):
            banner = vault[pick]["path"]
        audio = []
        for vid in request.form.getlist("audio")[:3]:
            v = vault.get(vid)
            if v and v["path"].rsplit(".", 1)[-1].lower() in ("wav", "mp3", "flac"):
                audio.append({"path": v["path"],
                              "label": v["label"] or "Untitled"})
        store.upsert_onesheet_share(user["id"], token, pin, banner, audio)
        return redirect("/epk")

    def _sheet_context(share):
        owner = store.get_user(share["user_id"])
        if owner is None:
            abort(404)
        tracks, ctx, summary, cert = _os_full(owner["id"])
        reports = sorted(
            [{"t": t, "clean": artist_os.clean_release(t, ctx)} for t in tracks],
            key=lambda r: -r["clean"]["score"])
        upcoming = [c for c in mls.list_campaigns(owner["id"])
                    if (c.get("release_date") or "") >=
                    datetime.now(timezone.utc).date().isoformat()]
        return owner, summary, cert, reports[:3], upcoming[:3]

    @app.route("/sheet/<token>", methods=["GET", "POST"])
    def sheet_public(token):
        share = store.get_onesheet_share_by_token(token)
        if share is None:
            abort(404)
        pin_ok_key = "sheet_ok_" + token
        if share["pin"] and not session.get(pin_ok_key):
            if request.method == "POST":
                if (request.form.get("pin") or "").strip() == share["pin"]:
                    session[pin_ok_key] = True
                    return redirect("/sheet/" + token)
                owner = store.get_user(share["user_id"])
                return render_template("sheet_public.html", mode="pin",
                                       token=token, bad_pin=True,
                                       artist=(owner or {}).get("name", "")), 403
            owner = store.get_user(share["user_id"])
            return render_template("sheet_public.html", mode="pin", token=token,
                                   bad_pin=False,
                                   artist=(owner or {}).get("name", ""))
        owner, summary, cert, reports, upcoming = _sheet_context(share)
        viewer = current_user()
        if viewer is None or viewer["id"] != owner["id"]:
            store.log_onesheet_view(token)
        return render_template("sheet_public.html", mode="sheet", token=token,
                               owner=owner, summary=summary, cert=cert,
                               reports=reports, upcoming=upcoming, share=share,
                               sent=request.args.get("sent") == "1",
                               today=datetime.now(timezone.utc).date().isoformat())

    @app.route("/sheet/<token>/pitch", methods=["POST"])
    def sheet_pitch(token):
        share = store.get_onesheet_share_by_token(token)
        if share is None:
            abort(404)
        if (request.form.get("website") or "").strip():
            return redirect("/sheet/" + token)  # honeypot: silently drop bots
        name = (request.form.get("name") or "").strip()[:120]
        email = (request.form.get("email") or "").strip()[:200]
        message = (request.form.get("message") or "").strip()[:2000]
        if "@" not in email or not message:
            return redirect("/sheet/" + token)
        owner = store.get_user(share["user_id"])
        store.add_inbox("onesheet_pitch", {
            "artist_id": share["user_id"],
            "artist": (owner or {}).get("name", ""),
            "name": name, "email": email, "message": message},
            user_id=share["user_id"])
        store.notify(share["user_id"], "pitch",
                     "One-sheet pitch from %s" % (name or email),
                     message[:300], "/reports")
        return redirect("/sheet/" + token + "?sent=1")

    _LOCKBOX_KEYS = tuple(k for k, _l, _r in artist_os.LOCKBOX_DOCS)

    def _is_lockbox_upload(path):
        """Is this the name the lockbox uploader itself writes?

        `uuid4().hex + "-" + <original filename>` - so 32 hex characters,
        a dash, and then something. Nothing else in the uploads directory
        has that shape, which is what makes it safe to unlink: the same
        narrow rule /vault/<id>/delete uses in the other direction.
        """
        base = os.path.basename((path or "").split("?")[0])
        return (len(base) > 33 and base[32] == "-"
                and all(c in "0123456789abcdef" for c in base[:32]))

    @app.route("/tracks/<track_id>/lockbox/<doc_key>", methods=["POST"])
    def os_lockbox_update(track_id, doc_key):
        user = current_user()
        if user is None:
            return login_required_redirect()
        track = store.get_os_track(user["id"], track_id)
        if track is None or doc_key not in _LOCKBOX_KEYS:
            abort(404)
        box = track["lockbox"]
        entry = box.get(doc_key) or {}
        action = request.form.get("action") or ""
        if action == "na":
            entry["not_applicable"] = not entry.get("not_applicable")
        elif action == "upload":
            f = request.files.get("file")
            if f and f.filename:
                fname = uuid.uuid4().hex + "-" + os.path.basename(f.filename)[-60:]
                f.save(os.path.join(UPLOADS_DIR, fname))
                entry["file"] = "/uploads/" + fname
                entry["not_applicable"] = False
        elif action in ("approver", "resend"):
            email = (request.form.get("email") or "").strip().lower()
            name = (request.form.get("name") or "").strip()
            if "@" in email:
                token = uuid.uuid4().hex
                approvals = entry.setdefault("approvals", [])
                existing = [a for a in approvals if a.get("email") == email]
                if action == "resend" and existing:
                    existing[0]["state"] = "pending"
                    existing[0]["token"] = token
                elif not existing:
                    approvals.append({"name": name[:80], "email": email,
                                      "state": "pending", "token": token})
                store.add_sign_token(token, user["id"], track_id, doc_key, email)
                if emailer.configured():
                    # Best-effort: the sign link also stays visible on the page.
                    doc_label = dict((k, l) for k, l, _r in artist_os.LOCKBOX_DOCS)[doc_key]
                    link = request.url_root.rstrip("/") + "/sign/" + token
                    emailer.send(email,
                                 "Signature needed: %s — %s" % (doc_label, track["title"]),
                                 '<p><b>%s</b> needs your sign-off on the %s for '
                                 '\u201c%s\u201d.</p><p><a href="%s">Review and sign</a></p>'
                                 % (user["name"], doc_label.lower(),
                                    track["title"], link), reply_to=user["email"])
        box[doc_key] = entry
        store.update_os_track_lockbox(user["id"], track_id, box)
        return redirect("/tracks/" + track_id)

    @app.route("/tracks/<track_id>/lockbox/<doc_key>/delete", methods=["POST"])
    def os_lockbox_file_delete(track_id, doc_key):
        """Detach one document from a lockbox slot, and remove the file.

        /tracks/<id>/delete removed a whole track and everything on it;
        one wrongly attached document - the split sheet for the other
        song, a contract carrying a name that should not have been
        shared - could only be overwritten, never removed. So the way to
        take one document back was to destroy the passport around it.

        Scoped exactly like the upload it undoes: `get_os_track` is
        already owner-scoped, so another artist's track and an unknown
        doc_key get the same 404 and neither confirms the other exists.
        The approvals stay - they record who was asked and what they
        answered - and lockbox_report puts the slot back to "missing" on
        the file's absence by itself.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        track = store.get_os_track(user["id"], track_id)
        if track is None or doc_key not in _LOCKBOX_KEYS:
            abort(404)
        # An empty slot answers the same way: nothing was there to
        # remove, which is the state the caller asked for.
        path = store.delete_os_track_lockbox_file(user["id"], track_id, doc_key)
        if path and _is_lockbox_upload(path):
            blob_store.remove(path, uploads_dir=UPLOADS_DIR)
        return redirect("/tracks/" + track_id)

    @app.route("/sign/<token>", methods=["GET", "POST"])
    def sign_document(token):
        row = store.get_sign_token(token)
        if row is None:
            return render_template("sign.html", invalid=True, row=None,
                                   doc_label=None, track=None, done=None)
        track = store.get_os_track(row["user_id"], row["track_id"])
        doc_label = dict((k, l) for k, l, _r in artist_os.LOCKBOX_DOCS).get(row["doc_key"])
        if track is None or doc_label is None:
            return render_template("sign.html", invalid=True, row=None,
                                   doc_label=None, track=None, done=None)
        entry = (track["lockbox"] or {}).get(row["doc_key"]) or {}
        approval = next((a for a in entry.get("approvals", [])
                         if a.get("email") == row["email"]), None)
        if request.method == "POST" and not row["used"] and approval:
            decision = request.form.get("decision")
            if decision in ("signed", "declined"):
                approval["state"] = decision
                store.update_os_track_lockbox(row["user_id"], row["track_id"],
                                              track["lockbox"])
                store.use_sign_token(token)
                store.notify(row["user_id"], "team",
                             "%s %s the %s" % (approval.get("name") or row["email"],
                                               decision, doc_label.lower()),
                             "Track: %s." % track["title"],
                             "/tracks/" + row["track_id"])
                return render_template("sign.html", invalid=False, row=row,
                                       doc_label=doc_label, track=track,
                                       done=decision)
        return render_template("sign.html", invalid=False, row=row,
                               doc_label=doc_label, track=track,
                               done=("signed" if row["used"] else None),
                               file_url=entry.get("file", ""))

    @app.route("/tracks/<track_id>/delete", methods=["POST"])
    def os_track_delete(track_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_os_track(user["id"], track_id)
        return redirect(_passports_home(user))

    # --- Tour Hub (folded into TOUR) + Stage Plot ------------------------------
    # Phase 3 of the TOUR restructure: there is one tour product at /tours.
    # The Tour Hub's addresses survive for bookmarks and old forms - GET /tour
    # and /tour/<show_id> redirect into TOUR, every POST route still answers
    # exactly as it did - and the public /showday and /rider pages are
    # untouched. The pipeline (hold -> confirmed -> advanced -> played ->
    # settled) now lives on the tour's Dates page.

    _SHOW_STATUSES = tour_store.SHOW_STATUSES

    def _tour_dates_url(user_id):
        """Where /tour lands now: the newest tour's Dates page, or the TOUR
        index (which offers to bring unattached shows onto a tour). A team
        member's visit adopts nothing: no tour is made for the artist by a
        seat looking (the artist's own visit and the boot sweep do it)."""
        if not session.get("team_as"):
            tour_store.adopt_orphan_shows(user_id)   # an old /tour link never lands on a dead page
        tours = tour_store.list_tours(user_id)
        return "/tours/%s/shows" % tours[0]["id"] if tours else "/tours"

    @app.route("/tour")
    def tour_hub():
        user = current_user()
        if user is None:
            return login_required_redirect()
        # ?view=board went to the same list; it lands on the same Dates page.
        return redirect(_tour_dates_url(user["id"]))

    @app.route("/tour/add", methods=["POST"])
    def tour_add():
        user = current_user()
        if user is None:
            return login_required_redirect()
        date_str = (request.form.get("date") or "").strip()
        venue = (request.form.get("venue") or "").strip()
        if date_str and venue:
            store.add_tour_show(user["id"], date_str, venue,
                                (request.form.get("city") or "").strip(),
                                (request.form.get("notes") or "").strip())
        return redirect("/tour")

    @app.route("/tour/<show_id>/status", methods=["POST"])
    def tour_status(show_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        status = request.form.get("status") or ""
        if status in _SHOW_STATUSES:
            store.update_tour_show_status(user["id"], show_id, status)
        return redirect("/tour")

    @app.route("/tour/<show_id>/delete", methods=["POST"])
    def tour_delete(show_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_tour_show(user["id"], show_id)
        return redirect("/tour")

    @app.route("/tour/<show_id>")
    def tour_show_detail(show_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        # Strangers still get a 404, never a redirect that confirms the id.
        show = store.get_tour_show(user["id"], show_id)
        if show is None:
            abort(404)
        if not show.get("tour_id") and not session.get("team_as"):
            # Not on a tour yet: adopt it onto one now, the way the boot
            # sweep does, so an old link lands on its date page. Not on a
            # team seat's visit, which lands on /tours instead.
            tour_store.adopt_orphan_shows(user["id"])
            show = store.get_tour_show(user["id"], show_id) or show
        if show.get("tour_id"):
            return redirect("/tours/%s/shows/%s" % (show["tour_id"], show_id))
        return redirect("/tours")

    @app.route("/tour/<show_id>/advance", methods=["POST"])
    def tour_show_advance(show_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        advance = {k: (request.form.get(k) or "").strip()[:300]
                   for k in touring.FIELD_KEYS}
        store.save_show_advance(user["id"], show_id, advance)
        return redirect("/tour/" + show_id)

    @app.route("/tour/<show_id>/settlement", methods=["POST"])
    def tour_show_settlement(show_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        seat = current_team_seat()
        if seat and not team_areas.money_open(seat["areas"]):
            # A show's deal and settlement are the Money and business
            # room's, as they are inside Tour (review, 2026-09-19).
            abort(403)
        settlement = {k: (request.form.get(k) or "").strip()[:60]
                      for k in ("deal_type", "guarantee", "door_gross", "split_pct",
                                "merch_gross", "merch_cut_pct", "expenses", "notes")}
        store.save_show_settlement(user["id"], show_id, settlement)
        if request.form.get("mark_settled"):
            store.update_tour_show_status(user["id"], show_id, "settled")
        return redirect("/tour/" + show_id)

    @app.route("/tour/<show_id>/share", methods=["POST"])
    def tour_show_share(show_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.set_show_share_token(user["id"], show_id, uuid.uuid4().hex)
        return redirect("/tour/" + show_id)

    @app.route("/tour/<show_id>/send-advance", methods=["POST"])
    def tour_send_advance(show_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        show = store.get_tour_show(user["id"], show_id)
        if show is None:
            abort(404)
        to = (show["advance"].get("contact_email") or "").strip()
        if not (to and "@" in to and emailer.configured()):
            return redirect("/tour/" + show_id + "?email_fail=1")
        share_url = ((request.url_root.rstrip("/") + "/showday/" + show["share_token"])
                     if show.get("share_token") else None)
        mail = touring.advance_email(show, show["advance"],
                                     artist_identity.display_name(user)
                                     or "The artist", share_url)
        import html as _html
        ok = emailer.send(to, mail["subject"],
                          '<pre style="font-family:inherit;white-space:pre-wrap">%s</pre>'
                          % _html.escape(mail["body"]), reply_to=user["email"])
        return redirect("/tour/" + show_id + ("?sent=1" if ok else "?email_fail=1"))

    @app.route("/showday/<token>")
    def showday(token):
        import json as _json
        show = store.get_show_by_share_token(token)
        if show is None:
            abort(404)
        adv = show["advance"]
        schedule = [(label, adv.get(key)) for key, label in (
            ("load_in", "Load-in"), ("soundcheck", "Soundcheck"), ("doors", "Doors"),
            ("set_time", "Set"), ("curfew", "Curfew")) if (adv.get(key) or "").strip()]
        plot = store.get_stage_plot(show["user_id"])
        return render_template("showday.html", show=show, adv=adv,
                               schedule=schedule,
                               plot_json=(_json.dumps(plot) if plot else "null"))

    @app.route("/rider/<token>")
    def tech_rider(token):
        # Public tech rider for venue staff: stage plot + input list, schedule,
        # backline, and the lighting rig — everything real, nothing invented.
        import json as _json
        show = store.get_show_by_share_token(token)
        if show is None:
            abort(404)
        adv = show["advance"]
        schedule = [(label, adv.get(key)) for key, label in (
            ("load_in", "Load-in"), ("soundcheck", "Soundcheck"), ("doors", "Doors"),
            ("set_time", "Set"), ("curfew", "Curfew")) if (adv.get(key) or "").strip()]
        plot = store.get_stage_plot(show["user_id"])
        lightshow = store.get_light_show(show["user_id"])
        lights = None
        if lightshow:
            lights = {"name": lightshow.get("name") or "",
                      "bars": int(lightshow.get("bars") or 0),
                      "chans": int(lightshow.get("chans") or 3),
                      "cues": len(lightshow.get("cues") or [])}
        return render_template("rider.html", show=show, adv=adv,
                               schedule=schedule, lights=lights,
                               plot_json=(_json.dumps(plot) if plot else "null"))

    @app.route("/lights")
    def lights():
        import json as _json
        user = current_user()
        if user is None:
            return login_required_redirect()
        saved = store.get_light_show(user["id"])
        library = {
            "shows": [{"id": s["id"], "name": s["name"], "cue_count": s["cue_count"],
                       "track_id": s["track_id"], "tour_show_id": s["tour_show_id"],
                       "updated": s["updated"]} for s in lights_store.list_shows(user["id"])],
            "rigs": _lights_rigs(user["id"]),
            "setlists": lights_store.list_setlists(user["id"]),
            "track_shows": lights_store.tracks_with_shows(user["id"]),
        }
        tracks = [{"id": t["id"], "title": t["title"]} for t in store.list_os_tracks(user["id"])]
        # venue_key lets the page pick the rig bound to the room without a
        # round trip when a show is linked to a tour date.
        tour_shows = [{"id": s["id"], "date": s["date"], "venue": s["venue"], "city": s.get("city") or "",
                       "venue_key": lights_store.venue_key(s["venue"])}
                      for s in store.list_tour_shows(user["id"])]
        return render_template("lights.html", active_page="lights",
                               saved_show=(_json.dumps(saved) if saved else "null"),
                               lights_library=_json.dumps(library),
                               lights_tracks=tracks, lights_tour_shows=tour_shows,
                               **build_dashboard_context())

    @app.route("/lights/save", methods=["POST"])
    def lights_save():
        """The working copy - one per account, what the page opens with.
        Autosave writes here; the library below is the named shows."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        store.save_light_show(user["id"], request.get_json(silent=True) or {})
        return jsonify({"ok": True})

    def _lights_shows(user_id):
        return [{"id": s["id"], "name": s["name"], "cue_count": s["cue_count"],
                 "track_id": s["track_id"], "tour_show_id": s["tour_show_id"],
                 "updated": s["updated"]} for s in lights_store.list_shows(user_id)]

    @app.route("/lights/library")
    def lights_library():
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        return jsonify({"ok": True, "shows": _lights_shows(user["id"])})

    @app.route("/lights/library/save", methods=["POST"])
    def lights_library_save():
        """Explicit save -> new version snapshot; autosave -> update in
        place. Track and tour-date links are validated against the
        caller's own rows; anything else is dropped, not stored."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        body = request.get_json(silent=True) or {}
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        track_id = (body.get("track_id") or "") or None
        if track_id and store.get_os_track(user["id"], track_id) is None:
            track_id = None
        tour_show_id = (body.get("tour_show_id") or "") or None
        if tour_show_id and store.get_tour_show(user["id"], tour_show_id) is None:
            tour_show_id = None
        show_id = lights_store.save_show(
            user["id"], body.get("id") or None, body.get("name") or data.get("name") or "Untitled show",
            data, track_id, tour_show_id, version=not body.get("autosave"),
            note=str(body.get("note") or "")[:200])
        return jsonify({"ok": True, "id": show_id, "shows": _lights_shows(user["id"]),
                        "versions": len(lights_store.list_versions(user["id"], show_id))})

    @app.route("/lights/library/<show_id>")
    def lights_library_get(show_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        s = lights_store.get_show(user["id"], show_id)
        if s is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "show": s})

    @app.route("/lights/library/<show_id>/versions")
    def lights_library_versions(show_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        if lights_store.get_show(user["id"], show_id) is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "versions": lights_store.list_versions(user["id"], show_id)})

    @app.route("/lights/library/<show_id>/restore", methods=["POST"])
    def lights_library_restore(show_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        body = request.get_json(silent=True) or {}
        v = lights_store.get_version(user["id"], body.get("version_id") or "")
        if v is None or v["show_id"] != show_id:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "data": v["data"]})

    @app.route("/lights/library/<show_id>/delete", methods=["POST"])
    def lights_library_delete(show_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        lights_store.delete_show(user["id"], show_id)
        return jsonify({"ok": True, "shows": _lights_shows(user["id"])})

    # --- sharing a show for notes (epic 5) ------------------------------
    # The designer sends one show and asks what people think. The link
    # carries that show and nothing else about the account, and no audio -
    # the song never left the designer's machine to begin with.

    # The reader needs the light show: cues, the rig they render on, the
    # looks and the patch. Everything else in a saved show is the
    # designer's own bookkeeping and has no business on a public link.
    _SHARED_SHOW_KEYS = ("cues", "bars", "chans", "looks", "sections", "stops",
                         "bpm", "beatOffset", "rigName", "dmxStart", "dmxUniverse", "dmxAddr")

    def _share_payload(share):
        """What a share link is allowed to reveal. Assembled field by
        field rather than handing over the row, so a column added to
        light_show_library later cannot quietly start travelling — and
        the show blob is filtered to a whitelist for the same reason:
        `trackId`, `tourShowId` and `libraryId` are account-internal ids
        that a tour manager has no reason to receive."""
        show = share["show"]
        data = show["data"] if isinstance(show["data"], dict) else {}
        return {
            "name": show["name"],
            "data": {k: data[k] for k in _SHARED_SHOW_KEYS if k in data},
            "updated": show["updated"],
            "cue_count": show["cue_count"],
            "permission": share["permission"],
        }

    @app.route("/lights/library/<show_id>/share", methods=["POST"])
    def lights_share_create(show_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        body = request.get_json(silent=True) or {}
        token = lights_store.create_share(user["id"], show_id,
                                          permission=body.get("permission") or "read",
                                          label=body.get("label") or "")
        if token is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "token": token,
                        "url": "%s/lights/show/%s" % (_remote_origin(), token),
                        "shares": lights_store.list_shares(user["id"], show_id)})

    @app.route("/lights/library/<show_id>/shares")
    def lights_share_list(show_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        # A show this account does not have is a 404, not an empty list:
        # "no shares" and "no such show" are different answers.
        if lights_store.get_show(user["id"], show_id) is None:
            return jsonify({"ok": False, "error": "No such show on this account."}), 404
        return jsonify({"ok": True, "shares": lights_store.list_shares(user["id"], show_id),
                        "origin": _remote_origin()})

    @app.route("/lights/share/<token>/revoke", methods=["POST"])
    def lights_share_revoke(token):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        if not lights_store.revoke_share(user["id"], token):
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True})

    @app.route("/lights/show/<token>")
    def lights_share_page(token):
        """Public on purpose: the unguessable token is the authorisation,
        like every other share link on the platform. Standalone template —
        it must render for someone with no account."""
        share = lights_store.get_share(token)
        if share is None:
            return render_template("lights_share.html", gone=True, token=""), 404
        return render_template("lights_share.html", gone=False, token=token,
                               share=_share_payload(share),
                               comments=lights_store.list_comments(share["show_id"]))

    @app.route("/lights/show/<token>/comments")
    def lights_share_comments(token):
        share = lights_store.get_share(token)
        if share is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "comments": lights_store.list_comments(share["show_id"])})

    @app.route("/lights/show/<token>/comment", methods=["POST"])
    def lights_share_comment(token):
        share = lights_store.get_share(token)
        if share is None:
            return jsonify({"ok": False}), 404
        if share["permission"] != "comment":
            return jsonify({"ok": False, "error": "read-only"}), 403
        body = request.get_json(silent=True) or {}
        cid = lights_store.add_comment(share["show_id"], share["user_id"],
                                       body.get("author") or "", body.get("body") or "",
                                       t=body.get("t"), parent_id=body.get("parent_id") or "")
        if cid is None:
            return jsonify({"ok": False, "error": "empty"}), 400
        return jsonify({"ok": True, "id": cid,
                        "comments": lights_store.list_comments(share["show_id"])})

    @app.route("/lights/library/<show_id>/comments")
    def lights_comments_list(show_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        if lights_store.get_show(user["id"], show_id) is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "comments": lights_store.list_comments(show_id)})

    @app.route("/lights/library/<show_id>/comment", methods=["POST"])
    def lights_comment_add(show_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        if lights_store.get_show(user["id"], show_id) is None:
            return jsonify({"ok": False}), 404
        body = request.get_json(silent=True) or {}
        cid = lights_store.add_comment(show_id, user["id"], user.get("name") or "You",
                                       body.get("body") or "", t=body.get("t"),
                                       parent_id=body.get("parent_id") or "")
        if cid is None:
            return jsonify({"ok": False}), 400
        return jsonify({"ok": True, "id": cid, "comments": lights_store.list_comments(show_id)})

    @app.route("/lights/comments/<comment_id>/resolve", methods=["POST"])
    def lights_comment_resolve(comment_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        body = request.get_json(silent=True) or {}
        if not lights_store.resolve_comment(user["id"], comment_id, bool(body.get("resolved", True))):
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True})

    @app.route("/lights/comments/<comment_id>/delete", methods=["POST"])
    def lights_comment_delete(comment_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        if not lights_store.delete_comment(user["id"], comment_id):
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True})

    # Mirrors LOOKS in static/js/lights-engine.js — the phone shows the
    # names and swatches, the laptop owns what they actually do. Order is
    # the contract: the phone sends the index, not a colour.
    _LIGHT_REMOTE_LOOKS = [
        # sb-keep: stage gels, not interface. These are the colours the
        # lamps make; the design tokens have no business here.
        {"name": "Amber wash", "color": "#ffb347"}, {"name": "Cold blue", "color": "#3b82f6"},
        {"name": "Red alert", "color": "#ff2d2d"}, {"name": "White full", "color": "#ffffff"},
        {"name": "Violet haze", "color": "#8b5cf6"}, {"name": "Blackout", "color": "#000000"},
    ]

    def _remote_origin():
        """Where the phone should point.

        Unlike a share link, this one is scanned off the operator's own
        screen seconds after it is made, so it has to be the host the
        laptop is actually being served from — a local run, a self-hosted
        box, or the public site. PUBLIC_BASE_URL is only the fallback.
        """
        host = request.host
        if not host:
            return PUBLIC_BASE_URL
        scheme = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip() or request.scheme
        return "%s://%s" % ("https" if scheme == "https" else "http", host)

    @app.route("/lights/remote/start", methods=["POST"])
    def lights_remote_start():
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        code = lights_store.start_remote(user["id"])
        return jsonify({"ok": True, "code": code,
                        "url": "%s/lights/remote/%s" % (_remote_origin(), code)})

    @app.route("/lights/remote/end", methods=["POST"])
    def lights_remote_end():
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        lights_store.end_remote(user["id"])
        return jsonify({"ok": True})

    @app.route("/lights/remote/poll")
    def lights_remote_poll():
        """The laptop drains whatever the phone has sent. The laptop stays
        the source of truth; this only carries button presses."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        if session.get("team_as"):
            # The artist's queue is theirs to drain, and the remote code
            # drives their rig: a seat gets neither (team review).
            return jsonify({"ok": True, "code": "", "commands": [], "phone_seen": ""})
        return jsonify(dict(lights_store.drain_remote_commands(user["id"]), ok=True))

    @app.route("/lights/remote/<code>")
    def lights_remote_page(code):
        """The phone page. Public on purpose - the unguessable code in the
        URL is the authorisation, exactly like a share link, so a second
        operator can pick it up without an account. It carries no show
        data: only buttons."""
        session_row = lights_store.get_remote(code)
        if session_row is None:
            return render_template("lights_remote.html", code="", expired=True,
                                   looks=[]), 404
        return render_template("lights_remote.html", code=code, expired=False,
                               looks=[(i + 1, l["name"], l["color"]) for i, l in enumerate(_LIGHT_REMOTE_LOOKS)])

    @app.route("/lights/remote/<code>/cmd", methods=["POST"])
    def lights_remote_cmd(code):
        body = request.get_json(silent=True) or {}
        ok = lights_store.push_remote_command(code, body.get("kind") or "", body.get("value") or "")
        if not ok:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True})

    @app.route("/lights/remote/<code>/qr.svg")
    def lights_remote_qr(code):
        user = current_user()
        if user is None:
            return "", 401
        # Only a live remote of this account gets a code drawn: a QR for a
        # code that names nothing would send a phone to a dead page.
        remote = lights_store.get_remote(code)
        if remote is None or remote.get("user_id") != user["id"]:
            return "", 404
        import segno
        import io as _io
        url = "%s/lights/remote/%s" % (PUBLIC_BASE_URL.rstrip("/"), code)
        buf = _io.BytesIO()
        segno.make(url, error="m").save(buf, kind="svg", scale=5, dark="#E8B950", light=None)
        return Response(buf.getvalue(), mimetype="image/svg+xml",
                        headers={"Cache-Control": "no-store"})

    @app.route("/lights/track/<track_id>/attach", methods=["POST"])
    def lights_track_attach(track_id):
        """Make the show travel with the song. Only the caller's own track."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        body = request.get_json(silent=True) or {}
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        entry = lights_store.attach_to_track(user["id"], track_id,
                                             body.get("name") or data.get("name") or "Untitled show",
                                             data, body.get("show_id") or "")
        if entry is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "attached": {"name": entry["name"], "cue_count": entry["cue_count"],
                                                 "saved_at": entry["saved_at"]},
                        "tracks": lights_store.tracks_with_shows(user["id"])})

    @app.route("/lights/track/<track_id>/show")
    def lights_track_show(track_id):
        """Pull the show attached to a track so it can be rendered on this
        account's own rig."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        entry = lights_store.show_on_track(user["id"], track_id)
        if entry is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "show": entry})

    @app.route("/lights/setlists")
    def lights_setlists():
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        return jsonify({"ok": True, "setlists": lights_store.list_setlists(user["id"])})

    @app.route("/lights/setlists/<setlist_id>")
    def lights_setlist_get(setlist_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        s = lights_store.get_setlist(user["id"], setlist_id)
        if s is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "setlist": s})

    @app.route("/lights/setlists/save", methods=["POST"])
    def lights_setlist_save():
        """Items referencing another account's show are dropped, not stored."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        body = request.get_json(silent=True) or {}
        items = body.get("items") if isinstance(body.get("items"), list) else []
        sid = lights_store.save_setlist(
            user["id"], body.get("id") or None, body.get("name") or "Setlist", items,
            gap_color=(body.get("gap_color") or "#1A1714")[:7],
            gap_intensity=body.get("gap_intensity") or 0)
        return jsonify({"ok": True, "id": sid, "setlists": lights_store.list_setlists(user["id"]),
                        "setlist": lights_store.get_setlist(user["id"], sid)})

    @app.route("/lights/setlists/<setlist_id>/delete", methods=["POST"])
    def lights_setlist_delete(setlist_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        lights_store.delete_setlist(user["id"], setlist_id)
        return jsonify({"ok": True, "setlists": lights_store.list_setlists(user["id"])})

    def _lights_rigs(user_id):
        return [{"id": r["id"], "name": r["name"], "venue_key": r["venue_key"], "data": r["data"]}
                for r in lights_store.list_rigs(user_id)]

    @app.route("/lights/rigs")
    def lights_rigs():
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        return jsonify({"ok": True, "rigs": _lights_rigs(user["id"])})

    @app.route("/lights/rigs/save", methods=["POST"])
    def lights_rigs_save():
        """A rig is layout + patch, not a show. Only the fields the studio
        knows how to render are stored; anything else is dropped."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        body = request.get_json(silent=True) or {}
        raw = body.get("data") if isinstance(body.get("data"), dict) else {}

        def _fracmap(m):
            out = {}
            if isinstance(m, dict):
                for k, v in list(m.items())[:10]:
                    if isinstance(v, list) and len(v) == 2:
                        try:
                            out[str(k)[:2]] = [min(0.97, max(0.03, float(v[0]))),
                                               min(0.92, max(0.04, float(v[1])))]
                        except (TypeError, ValueError):
                            pass
            return out

        def _rotmap(m):
            out = {}
            if isinstance(m, dict):
                for k, v in list(m.items())[:10]:
                    out[str(k)[:2]] = 90 if v == 90 else 0
            return out

        def _addrmap(m):
            out = {}
            if isinstance(m, dict):
                for k, v in list(m.items())[:10]:
                    try:
                        n = int(v)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= n <= 512:
                        out[str(k)[:2]] = n
            return out

        try:
            bars = int(raw.get("bars") or 6)
        except (TypeError, ValueError):
            bars = 6
        try:
            start = int(raw.get("dmxStart") or 1)
        except (TypeError, ValueError):
            start = 1
        data = {"bars": max(2, min(10, bars)),
                "chans": 3 if raw.get("chans") == 3 else 4,
                "pos": _fracmap(raw.get("pos")), "rot": _rotmap(raw.get("rot")),
                "dmxStart": max(1, min(512, start)), "dmxAddr": _addrmap(raw.get("dmxAddr"))}
        rig_id, err = lights_store.save_rig(
            user["id"], body.get("id") or None, body.get("name") or "Untitled rig",
            data, str(body.get("venue") or "")[:120])
        if err:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({"ok": True, "id": rig_id, "rigs": _lights_rigs(user["id"])})

    @app.route("/lights/rigs/<rig_id>/delete", methods=["POST"])
    def lights_rigs_delete(rig_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        lights_store.delete_rig(user["id"], rig_id)
        return jsonify({"ok": True, "rigs": _lights_rigs(user["id"])})

    @app.route("/rack")
    def rack():
        import json as _json
        user = current_user()
        if user is None:
            return login_required_redirect()
        saved = store.get_rack_preset(user["id"])
        return render_template("rack.html", active_page="rack",
                               saved_rack=(_json.dumps(saved) if saved else "null"),
                               studio_split=stemsplit.configured(),
                               studio_modes=stemsplit.mode_list(),
                               server_convert=convert_engine.available(),
                               convert_formats=convert_engine.format_list(),
                               **build_dashboard_context())

    # ---- Studio Split: StemSplit.io quality tier for the Stem Deck -------
    # Env-gated on STEMSPLIT_API_KEY. The one Deck feature that uploads:
    # the track is parked under a token, StemSplit fetches it from the
    # public /stem-src URL, and finished stems stream back through us.
    # The key never reaches the browser.

    @app.route("/rack/studio-split/diag")
    def studio_split_diag():
        """Why isn't Studio Split showing up? Reports the SHAPE of the
        environment, never a value: which STEM-ish names exist, how long
        the key is, and whether it carries stray whitespace or quotes -
        the three things that silently break a pasted secret. Requires a
        signed-in account; no secret ever leaves this endpoint."""
        import json as _json
        user = current_user()
        if user is None:
            return jsonify({"error": "auth required"}), 401
        raw = os.environ.get("STEMSPLIT_API_KEY")
        names = sorted(k for k in os.environ
                       if "STEM" in k.upper() or "SPLIT" in k.upper())
        info = {
            "configured": stemsplit.configured(),
            "expected_name": "STEMSPLIT_API_KEY",
            "matching_env_names": names,
            "present": raw is not None,
        }
        if raw is not None:
            info.update({
                "length": len(raw),
                "has_surrounding_whitespace": raw != raw.strip(),
                "wrapped_in_quotes": len(raw) > 1 and raw[0] in "'\"",
                "starts_with_sk": raw.strip().startswith("sk_"),
            })
        if raw and request.args.get("probe") == "1":
            info["probe"] = stemsplit.probe()
        if request.args.get("encoders") == "1":
            # Can this box encode lossy audio at all? Decides whether MP3
            # export is a server job or has to happen in the browser.
            import shutil
            import subprocess
            found = {}
            for tool in ("ffmpeg", "avconv", "lame", "flac", "sox"):
                found[tool] = shutil.which(tool) or None
            if found.get("ffmpeg"):
                try:
                    out = subprocess.run(
                        [found["ffmpeg"], "-hide_banner", "-encoders"],
                        capture_output=True, text=True, timeout=20).stdout
                    found["ffmpeg_codecs"] = sorted(
                        c for c in ("libmp3lame", "aac", "flac", "libopus",
                                    "libvorbis", "alac", "pcm_s24le")
                        if c in out)
                except Exception as exc:
                    found["ffmpeg_codecs"] = "probe failed: %s" % exc
            info["encoders"] = found
        if raw and request.args.get("job"):
            # The whole job body, so we can see what the API actually
            # returns rather than what we assumed. Signatures are stripped
            # from the URLs - the path is the part that answers the
            # question, because it carries the file extension.
            import re as _re
            body, err = stemsplit._call(
                "GET", stemsplit.JOBS + "/" + request.args["job"])
            if err:
                info["job_raw"] = {"error": err}
            else:
                dumped = _json.dumps(body)
                info["job_raw"] = _json.loads(
                    _re.sub(r'\?[^"]*', "?<signature-stripped>", dumped))
        if raw and request.args.get("modes") == "1":
            # Which separation modes does this account actually have? Asked
            # against a source that cannot be fetched, so no audio is
            # separated and no credits are spent - see probe_output_types.
            info["output_types"] = stemsplit.probe_output_types()
        return jsonify(info)

    @app.route("/rack/studio-split", methods=["POST"])
    def studio_split_start():
        user = current_user()
        if user is None:
            return jsonify({"error": "auth required"}), 401
        if not stemsplit.configured():
            return jsonify({"error": "Studio Split isn't configured on this "
                            "server yet."}), 503
        f = request.files.get("audio")
        if f is None or not f.filename:
            return jsonify({"error": "no audio file"}), 400
        data = f.read()
        if len(data) > stemsplit.MAX_UPLOAD:
            return jsonify({"error": "file too large - bounce an MP3 first"}), 413
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in (".wav", ".mp3", ".flac", ".m4a"):
            return jsonify({"error": "use WAV, MP3, FLAC or M4A"}), 400
        mode = (request.form.get("mode") or "").strip().upper()
        if mode not in stemsplit.MODES:
            mode = stemsplit.DEFAULT_MODE
        token, path = stemsplit.park_source(data, ext)
        source_url = request.url_root.rstrip("/") + "/stem-src/" + token
        job_id, err = stemsplit.create_job(source_url, mode)
        if err:
            try:
                os.remove(path)
            except OSError:
                pass
            return jsonify({"error": "StemSplit rejected the job: " + err}), 502
        stemsplit.remember_source(job_id, path)
        # The lanes this mode yields travel with the job, so the deck never
        # has to keep its own copy of which stems go together.
        return jsonify({"job": job_id, "mode": mode,
                        "stems": stemsplit.mode_stems(mode)})

    @app.route("/stem-src/<token>")
    def stem_src(token):
        from flask import send_file

        path = stemsplit.source_path(token)
        if not path:
            return "", 404
        return send_file(path)

    @app.route("/rack/studio-split/<job_id>")
    def studio_split_status(job_id):
        user = current_user()
        if user is None:
            return jsonify({"error": "auth required"}), 401
        if not stemsplit.configured():
            return jsonify({"error": "not configured"}), 503
        status, err = stemsplit.job_status(job_id)
        if err:
            return jsonify({"error": err}), 502
        return jsonify(status)

    @app.route("/rack/studio-split/<job_id>/stem/<stem>")
    def studio_split_stem(job_id, stem):
        user = current_user()
        if user is None:
            return jsonify({"error": "auth required"}), 401
        if not stemsplit.configured():
            return jsonify({"error": "not configured"}), 503
        if stem not in stemsplit.STEMS:
            return jsonify({"error": "unknown stem"}), 400
        url, err = stemsplit.stem_url(job_id, stem)
        if err:
            return jsonify({"error": err}), 502
        upstream = stemsplit.open_stream(url)
        ctype = upstream.headers.get("Content-Type") or "audio/wav"
        resp = app.response_class(upstream, mimetype=ctype,
                                  direct_passthrough=True)
        # Name the file. Without this the browser saves it as "vocals"
        # with no extension, which nothing can open.
        resp.headers["Content-Disposition"] = (
            'attachment; filename="%s"'
            % stemsplit.stem_filename(stem, url, ctype))
        length = upstream.headers.get("Content-Length")
        if length:
            resp.headers["Content-Length"] = length   # so the bar moves
        return resp

    @app.route("/rack/convert", methods=["POST"])
    def rack_convert():
        """Compressed formats, encoded on the server.

        WAV and AIFF stay in the browser - they are already instant there
        and never leave the machine. This is for the ones a browser has no
        encoder for: MP3, FLAC, AAC, ALAC, Opus, Vorbis. It uploads, and
        the UI says so before the button is pressed.
        """
        user = current_user()
        if user is None:
            return jsonify({"error": "auth required"}), 401
        if not convert_engine.available():
            return jsonify({"error": "This server has no audio encoder "
                            "installed."}), 503
        f = request.files.get("audio")
        if f is None or not f.filename:
            return jsonify({"error": "no audio file"}), 400

        def num(name):
            try:
                return int(request.form.get(name) or 0)
            except ValueError:
                return 0

        data, name, err = convert_engine.convert(
            f.read(), f.filename,
            (request.form.get("format") or "").strip().lower(),
            bitrate=num("bitrate"), rate=num("rate"),
            channels=num("channels"), depth=num("depth"))
        if err:
            return jsonify({"error": err}), 400
        key = request.form["format"].strip().lower()
        fmt = convert_engine.FORMATS[key]
        resp = app.response_class(data, mimetype=fmt["mime"])
        resp.headers["Content-Disposition"] = \
            'attachment; filename="%s"' % name
        resp.headers["Content-Length"] = str(len(data))
        # If the codec could not take the rate that was asked for, the
        # file still arrives - but the panel has to say what changed
        # rather than quietly hand back something else.
        _, note = convert_engine.resolve_rate(key, num("rate"))
        if note:
            resp.headers["X-Convert-Note"] = note
        return resp

    @app.route("/rack/analysis", methods=["POST"])
    def rack_analysis():
        """The Rack reporting what it measured.

        Everything the meter computes has, until now, died with the tab.
        This is the arrow that was missing from the loop: the numbers
        persist, so Release Readiness can speak about the record rather
        than only about the paperwork around it.

        Nothing here is computed server-side - these are the browser's own
        measurements, and the only job is to store them faithfully.
        """
        user = current_user()
        if user is None:
            return jsonify({"error": "auth required"}), 401
        body = request.get_json(silent=True) or {}

        def num(key):
            v = body.get(key)
            try:
                f = float(v)
            except (TypeError, ValueError):
                return None
            # Reject anything that is not a real measurement.
            return f if f == f and abs(f) != float("inf") else None

        row = {
            "track_id": str(body.get("track_id") or "")[:80],
            "filename": str(body.get("filename") or "")[:200],
            "integrated": num("integrated"), "lra": num("lra"),
            "true_peak": num("true_peak"), "sample_peak": num("sample_peak"),
            "short_term_max": num("short_term_max"),
            "momentary_max": num("momentary_max"),
            "bpm": num("bpm"), "bpm_confidence": num("bpm_confidence"),
            "key": str(body.get("key") or "")[:40], "key_fit": num("key_fit"),
            "duration": num("duration"), "sample_rate": num("sample_rate"),
            "channels": num("channels"),
            "hook_15s": num("hook_15s"), "hook_30s": num("hook_30s"),
            "first_beat": num("first_beat"),
            "bar_seconds": num("bar_seconds"),
            "grid_confidence": num("grid_confidence"),
            "engine": str(body.get("engine") or "rack")[:60],
        }
        if row["integrated"] is None and row["true_peak"] is None:
            return jsonify({"error": "no measurements in this report"}), 400
        store.save_track_analysis(user["id"], row)
        saved = store.latest_track_analysis(user["id"])
        return jsonify({"ok": True, "assessment": audio_readiness.assess(saved)})

    # --- the rack preset library ----------------------------------------
    # /rack/save keeps ONE rack: the one that loads with the page. These
    # keep many, named, so a vocal chain and a drum bus can both exist.

    @app.route("/rack/library")
    def rack_library():
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        return jsonify({"ok": True, "presets": store.list_rack_presets(user["id"]),
                        "max": store.MAX_RACK_PRESETS})

    @app.route("/rack/library/save", methods=["POST"])
    def rack_library_save():
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "a preset needs a name"}), 400
        data = body.get("data")
        if not isinstance(data, dict) or not data:
            return jsonify({"ok": False, "error": "nothing to save"}), 400
        pid = store.save_rack_preset_named(user["id"], body.get("id") or "",
                                           name, data, body.get("note") or "")
        if pid is None:
            return jsonify({"ok": False,
                            "error": "that is %d presets — delete one first"
                                     % store.MAX_RACK_PRESETS}), 409
        return jsonify({"ok": True, "id": pid, "presets": store.list_rack_presets(user["id"])})

    @app.route("/rack/library/<preset_id>")
    def rack_library_get(preset_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        p = store.get_rack_preset_by_id(user["id"], preset_id)
        if p is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "preset": p})

    @app.route("/rack/library/<preset_id>/delete", methods=["POST"])
    def rack_library_delete(preset_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        if not store.delete_rack_preset(user["id"], preset_id):
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "presets": store.list_rack_presets(user["id"])})

    @app.route("/rack/save", methods=["POST"])
    def rack_save():
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        store.save_rack_preset(user["id"], request.get_json(silent=True) or {})
        return jsonify({"ok": True})

    @app.route("/sw.js")
    def service_worker():
        # Served from the root so the worker's scope covers the whole app.
        from flask import send_from_directory
        resp = send_from_directory(os.path.join(app.static_folder, "js"), "sw.js")
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    # Every prefix here is a share link whose token IS the authorisation:
    # an EPK, a press announcement, a beat sent to one artist, a signed
    # licence, a day sheet for the local crew. They are public so the
    # recipient can open them without an account, which is exactly why a
    # crawler must not index them - a search result would hand a private
    # link to everyone. /uploads/ is the same argument for files.
    _NO_CRAWL = ("/uploads/", "/l/", "/s/", "/epk/", "/stem-src/", "/presave/",
                 "/reset/", "/team/join/", "/webhooks/", "/club/", "/showday/",
                 "/rider/", "/roster/join/", "/sign/", "/sheet/", "/pitch/",
                 "/press/", "/lights/remote/", "/lights/show/", "/beat/",
                 "/licence/", "/cleared/", "/tour-share/", "/board-renew/",
                 "/@", "/login", "/signup", "/logout", "/demo-access")

    @app.route("/robots.txt")
    def robots_txt():
        """Steer crawlers off the share links and the sign-in pages.

        The marketing pages stay open - they exist to be found. /static/ is
        explicitly allowed because a crawler that cannot fetch the CSS
        renders the page wrongly and judges it on that.
        """
        lines = ["User-agent: *", "Allow: /static/"]
        lines += ["Disallow: " + p for p in _NO_CRAWL]
        lines.append("")
        return Response("\n".join(lines), mimetype="text/plain")

    @app.route("/stage-plot")
    def stage_plot():
        import json as _json
        user = current_user()
        if user is None:
            return login_required_redirect()
        plot = store.get_stage_plot(user["id"])
        return render_template("stage_plot.html", active_page="stage-plot",
                               saved_plot=(_json.dumps(plot) if plot else "null"),
                               **build_dashboard_context())

    @app.route("/stage-plot/save", methods=["POST"])
    def stage_plot_save():
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        data = request.get_json(silent=True) or {}
        store.save_stage_plot(user["id"], data)
        return jsonify({"ok": True})

    @app.route("/stage-plot/image", methods=["POST"])
    def stage_plot_image_save():
        """The rendered plot, kept so the advance email can attach it. The
        browser rasterises the SVG - this server has no renderer - and
        posts the PNG. One per artist, replaced on each save."""
        import plot_images
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        up = request.files.get("image")
        data = up.read(plot_images.MAX_BYTES + 1) if up is not None else b""
        if not data or not data.startswith(b"\x89PNG"):
            return jsonify({"ok": False, "error": "That is not a PNG."}), 400
        if len(data) > plot_images.MAX_BYTES:
            return jsonify({"ok": False, "error": "The image is over 4 MB."}), 413
        plot_images.save(user["id"], data)
        return jsonify({"ok": True})

    @app.route("/stage-plot/image.png")
    def stage_plot_image_get():
        import plot_images
        user = current_user()
        if user is None:
            return login_required_redirect()
        data = plot_images.read(user["id"])
        if not data:
            abort(404)
        return app.response_class(data, mimetype="image/png")

    # --- Team-Up Board: artists seeking partners, venues seeking acts ------------
    # Moved to board.py (blueprint "board"): same URLs, structured fields,
    # in-platform reply threads, lifecycle, saved searches. Registered in
    # init at the bottom of create_app.

    # --- Partner Portal: team roles open real (read-only) doors ------------------

    @app.route("/portal")
    def portal():
        user = current_user()
        if user is None:
            return login_required_redirect()
        return render_template("portal.html", active_page="portal",
                               memberships=store.list_portal_memberships(user["id"]),
                               **build_dashboard_context())

    @app.route("/portal/<owner_id>/open", methods=["POST"])
    def portal_open(owner_id):
        """Work inside an account this person is on the team of. What they
        may do there is their seat's access, checked on every request."""
        uid = session.get("user_id")
        if not uid:
            return login_required_redirect()
        if session.get("acting_as"):
            return redirect("/portal")
        seat = _team_seat(uid, owner_id)
        if seat is None:
            abort(404)
        session["team_as"] = owner_id
        session["team_as_name"] = seat["owner"].get("name") or "the artist"
        return redirect(team_areas.home(seat["areas"]))

    @app.route("/portal/leave", methods=["POST"])
    def portal_leave():
        session.pop("team_as", None)
        session.pop("team_as_name", None)
        return redirect("/portal")

    @app.route("/portal/<owner_id>")
    def portal_view(owner_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        membership = store.get_portal_membership(user["id"], owner_id)
        if membership is None:
            abort(404)
        role = membership["role"]
        rooms_open = team_areas.parse(membership.get("areas"))
        money = None
        # The summary follows the rooms the artist opened, as the account does.
        if role in ("manager", "accountant", "attorney") and "business" in rooms_open:
            rows = store.get_statement_rows(owner_id)
            money = {"total": round(sum(r["amount"] for r in rows), 2),
                     "rows": len(rows),
                     "statements": len(store.get_statements(owner_id))}
        promo = None
        if role in ("manager", "publicist", "assistant") and "marketing" in rooms_open:
            campaigns = [c for c in mls.list_campaigns(owner_id)
                         if not c.get("archived_at")]
            clicks = views = 0
            for c in campaigns:
                n = mls.event_counts(c["id"])
                views += n.get("page_view", 0) + n.get("pageview", 0)
                clicks += n.get("service_click", 0) + n.get("click", 0)
            promo = {"campaigns": len(campaigns), "views": views, "clicks": clicks,
                     "fans": len(mls.list_fans(owner_id))}
        seat = _team_seat(user["id"], owner_id)
        return render_template("portal_view.html", active_page="portal",
                               m=membership, role=role, money=money, promo=promo,
                               seat_access=(seat or {}).get("access") or "read",
                               can_open=seat is not None,
                               trust=trust_score.calculate(owner_id)["total"],
                               growth=qualification.calculate(owner_id)["total"],
                               **build_dashboard_context())

    @app.route("/capital-score")
    def capital_score_page():
        user = current_user()
        if user is None:
            return login_required_redirect()
        cs = capital_engine.capital_score(user["id"])   # records itself
        return render_template("capital_score.html", active_page="command-center",
                               cs=cs,
                               trend=score_history.summarise(
                                   "capital",
                                   store.score_trend(user["id"], "capital")),
                               **build_dashboard_context())

    @app.route("/spend-optimizer")
    def spend_optimizer_page():
        user = current_user()
        if user is None:
            return login_required_redirect()
        try:
            budget = max(50.0, min(float(request.args.get("budget") or 500), 100000.0))
        except ValueError:
            budget = 500.0
        return render_template("spend_optimizer.html", active_page="command-center",
                               plan=capital_engine.spend_plan(user["id"], budget),
                               **build_dashboard_context())

    # Preview modules: registered honestly, one generic page each.
    def _module_preview(route):
        def view():
            module = cc.MODULE_BY_ROUTE[route]
            return render_template("module_preview.html",
                                   active_page="command-center", m=module,
                                   features=cc.PREVIEW_FEATURES.get(route, []),
                                   **build_dashboard_context())
        view.__name__ = "preview_" + route.strip("/").replace("/", "_").replace("-", "_")
        return view

    for _route, _name, _blurb, _status, _disc in cc.MODULES:
        if _status == "preview":
            app.add_url_rule(_route, view_func=_module_preview(_route))

    # --- Producers: beats, licences, cleared list, usage cases ----------------

    @app.route("/beats", methods=["GET", "POST"])
    def beats():
        user = current_user()
        if user is None:
            return login_required_redirect()
        if request.method == "POST":
            title = (request.form.get("title") or "").strip()
            if title:
                store.add_beat(user["id"], title,
                               (request.form.get("bpm") or "").strip(),
                               (request.form.get("song_key") or "").strip(),
                               (request.form.get("tags") or "").strip(),
                               (request.form.get("note") or "").strip())
            return redirect("/beats")
        ctx = build_dashboard_context()
        ctx["desk"] = producers.desk(user["id"])
        ctx["monitoring"] = acr_provider.status()
        rows = store.beat_audio_for(user["id"])
        ctx["audio"] = rows
        # The script needs peaks and durations; it must not need the
        # storage path, which is an R2 key or a disk location.
        ctx["audio_public"] = {k: _beat_audio_public(v) for k, v in rows.items()}
        ctx["max_beat_mb"] = store.MAX_BEAT_BYTES // (1024 * 1024)
        return render_template("beats.html", active_page="beats", **ctx)

    @app.route("/beats/register", methods=["POST"])
    def beat_register():
        """Create the registry row a dropped file hangs off. Separate from
        the form POST above because a bulk drop needs an id back, not a
        redirect."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        body = request.get_json(silent=True) or {}
        title = (body.get("title") or "").strip()[:200]
        if not title:
            return jsonify({"ok": False, "error": "a beat needs a title"}), 400
        return jsonify({"ok": True, "id": store.add_beat(user["id"], title)})

    @app.route("/beats/<beat_id>", methods=["GET", "POST"])
    def beat_detail(beat_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        beat = store.get_beat(beat_id, user["id"])
        if beat is None:
            abort(404)
        if request.method == "POST":
            action = request.form.get("action")
            if action == "licence":
                store.add_beat_licence(beat_id, user["id"], {
                    "licensee_name": request.form.get("licensee_name"),
                    "licensee_email": request.form.get("licensee_email"),
                    "licence_type": (request.form.get("licence_type")
                                     if request.form.get("licence_type") in
                                     dict(producers.LICENCE_TYPES) else "lease"),
                    "territory": request.form.get("territory"),
                    "term": request.form.get("term"),
                    "fee": _hours_float(request.form.get("fee")),
                    "producer_split": _hours_float(
                        request.form.get("producer_split"), 50.0),
                    "terms": request.form.get("terms"),
                    "send": True})
            elif action == "clear" and (request.form.get("value") or "").strip():
                store.add_beat_clearance(
                    beat_id,
                    (request.form.get("kind")
                     if request.form.get("kind") in dict(producers.CLEARANCE_KINDS)
                     else "channel"),
                    request.form.get("value"), request.form.get("note") or "",
                    request.form.get("licence_id") or "")
            elif action == "unclear" and request.form.get("row_id"):
                store.delete_beat_clearance(beat_id, request.form["row_id"])
            elif action == "use":
                store.add_beat_use(beat_id, user["id"], {
                    "url": request.form.get("url"),
                    "platform": request.form.get("platform"),
                    "notes": request.form.get("notes")})
            elif action == "use_from_match" and request.form.get("match_id"):
                # found_via='fingerprint' comes from a stored match row, so
                # the badge can only appear beside something ACRCloud said.
                m = store.get_beat_fingerprint_match(user["id"], request.form["match_id"])
                if m and m["beat_id"] == beat_id:
                    note = "ACRCloud match: %s" % m["title"]
                    if m["artists"]:
                        note += " - " + m["artists"]
                    if m["album"]:
                        note += " (" + m["album"] + ")"
                    if m["isrc"]:
                        note += " ISRC " + m["isrc"]
                    note += ", score %d. Confirm by ear." % m["score"]
                    store.add_beat_use(beat_id, user["id"], {
                        "url": m["url"], "platform": m["platform"],
                        "found_via": "fingerprint", "notes": note})
            elif action == "use_status" and request.form.get("use_id"):
                fields = {"status": request.form.get("status")
                          if request.form.get("status") in producers.USE_STATUSES
                          else "open"}
                if request.form.get("resolved_amount"):
                    fields["resolved_amount"] = _hours_float(
                        request.form.get("resolved_amount"))
                store.update_beat_use(user["id"], request.form["use_id"], fields)
            elif action == "revoke" and request.form.get("licence_id"):
                store.set_beat_licence_status(user["id"],
                                              request.form["licence_id"], "revoked")
            return redirect("/beats/" + beat_id)
        ctx = build_dashboard_context()
        ctx.update({
            "beat": beat,
            "licences": store.list_beat_licences(beat_id),
            "clearances": store.list_beat_clearances(beat_id),
            "uses": store.list_beat_uses(user["id"], beat_id),
            "summary": producers.beat_summary(beat_id),
            "licence_types": producers.LICENCE_TYPES,
            "clearance_kinds": producers.CLEARANCE_KINDS,
            "use_statuses": producers.USE_STATUSES,
            "monitoring": acr_provider.status(),
            "fingerprint_checks": store.list_beat_fingerprint_checks(user["id"], beat_id),
            "fp_note": {
                "noaudio": "Attach audio to this beat first.",
                "noclip": "Choose a file to identify.",
                "big": "Clips are capped at %d MB. Fifteen seconds is plenty."
                       % (acr_provider.MAX_CLIP_BYTES // (1024 * 1024)),
            }.get(request.args.get("fp") or "", ""),
            "public_base": request.host_url.rstrip("/"),
            "audio": _beat_audio_public(store.get_beat_audio(beat_id)),
            "shares": store.list_beat_shares(user["id"], beat_id),
            "share_origin": _remote_origin(),
        })
        return render_template("beat_detail.html", active_page="beats", **ctx)

    # --- Beat audio, analysis, and private links -------------------------
    # The browser decodes the file, measures tempo and key with the same
    # detector the Rack uses (static/js/tempokey.js) and sends the numbers
    # up with the bytes. Nothing here listens to audio server-side, and no
    # third party is handed the beat to analyse it.

    _BEAT_AUDIO_TYPES = ("audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
                         "audio/wave", "audio/aiff", "audio/x-aiff", "audio/flac",
                         "audio/x-flac", "audio/mp4", "audio/aac", "audio/ogg",
                         "audio/webm", "application/octet-stream")

    def _beat_num(value, lo=None, hi=None):
        """A measurement or nothing. NaN and infinity are neither."""
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        if f != f or abs(f) == float("inf"):
            return None
        if lo is not None and f < lo:
            return None
        if hi is not None and f > hi:
            return None
        return f

    @app.route("/beats/<beat_id>/audio", methods=["POST"])
    def beat_audio_upload(beat_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        if store.get_beat(beat_id, user["id"]) is None:
            return jsonify({"ok": False}), 404
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify({"ok": False, "error": "no file"}), 400
        data = f.read()
        if not data:
            return jsonify({"ok": False, "error": "empty file"}), 400
        if len(data) > store.MAX_BEAT_BYTES:
            return jsonify({"ok": False,
                            "error": "that file is %d MB; the ceiling is %d MB"
                                     % (len(data) // (1024 * 1024),
                                        store.MAX_BEAT_BYTES // (1024 * 1024))}), 413
        mime = (f.mimetype or "application/octet-stream")[:80]
        if mime not in _BEAT_AUDIO_TYPES:
            return jsonify({"ok": False, "error": "that is not an audio file"}), 415

        ext = os.path.splitext(f.filename)[1][:10] or ".audio"
        key = "beats/%s/%s%s" % (user["id"], uuid.uuid4().hex, ext)
        try:
            path = blob_store.save(key, data, mime, uploads_dir=UPLOADS_DIR)
        except RuntimeError:
            return jsonify({"ok": False, "error": "nowhere to store the file"}), 503

        # Replacing audio orphans the old object; drop it rather than pay
        # to keep a file nothing can reach.
        old = store.delete_beat_audio(user["id"], beat_id)
        if old and old != path:
            try:
                blob_store.remove(old, uploads_dir=UPLOADS_DIR)
            except Exception:
                pass

        peaks = request.form.get("peaks") or "[]"
        try:
            peaks = [max(0.0, min(1.0, float(x))) for x in json.loads(peaks)][:900]
        except (ValueError, TypeError):
            peaks = []
        store.save_beat_audio(user["id"], beat_id, {
            "filename": f.filename, "path": path, "mime": mime, "bytes": len(data),
            "duration": _beat_num(request.form.get("duration"), 0, 60 * 60 * 6),
            "peaks": peaks,
            "bpm": _beat_num(request.form.get("bpm"), 20, 400),
            "bpm_confidence": _beat_num(request.form.get("bpm_confidence"), 0, 1),
            "bpm_alternates": (request.form.get("bpm_alternates") or "")[:60],
            "song_key": (request.form.get("song_key") or "")[:40],
            "key_fit": _beat_num(request.form.get("key_fit"), -1, 1),
            "key_runner_up": (request.form.get("key_runner_up") or "")[:40],
            "sample_rate": _beat_num(request.form.get("sample_rate"), 1000, 400000),
        })
        # The measurement fills the registry fields only where the producer
        # left them empty. A number they typed is a decision; a number we
        # measured is a guess, and a guess must not overwrite a decision.
        beat = store.get_beat(beat_id, user["id"])
        audio = store.get_beat_audio(beat_id)
        fills = {}
        if not (beat["bpm"] or "").strip() and audio.get("bpm"):
            fills["bpm"] = str(int(round(audio["bpm"])))
        if not (beat["song_key"] or "").strip() and audio.get("song_key"):
            fills["song_key"] = audio["song_key"]
        if fills:
            store.update_beat(user["id"], beat_id, fills)
        return jsonify({"ok": True, "audio": _beat_audio_public(audio),
                        "filled": fills})

    def _beat_audio_public(audio):
        """What the page is allowed to know about a stored file. The
        storage path never travels — it is an R2 key or a disk location,
        and the browser reaches audio through /beats/<id>/stream."""
        if not audio:
            return None
        return {"filename": audio["filename"], "bytes": audio["bytes"],
                "duration": audio["duration"], "peaks": audio["peaks"],
                "bpm": audio["bpm"], "bpm_confidence": audio["bpm_confidence"],
                "bpm_alternates": audio["bpm_alternates"],
                "song_key": audio["song_key"], "key_fit": audio["key_fit"],
                "key_runner_up": audio["key_runner_up"],
                "sample_rate": audio["sample_rate"], "created": audio["created"]}

    def _stream_beat(audio):
        """Serve the stored bytes. R2 objects are handed over as a signed
        redirect so the file does not travel through this process twice."""
        path = audio["path"]
        if blob_store.is_remote(path):
            return redirect(blob_store.url_for(path))
        # The key is nested ("beats/<user>/<id>.wav"), so basename() would
        # look in the wrong place. send_from_directory takes the relative
        # path and refuses to leave UPLOADS_DIR itself.
        from flask import send_from_directory
        return send_from_directory(UPLOADS_DIR, path[len("/uploads/"):],
                                   mimetype=audio["mime"] or "audio/mpeg",
                                   conditional=True)

    def _beat_audio_bytes(audio):
        """The stored file, read back for a fingerprint sample. Returns
        None when the object cannot be reached; the check records that."""
        path = audio["path"]
        if blob_store.is_remote(path):
            return blob_store.fetch(path)
        try:
            with open(blob_store.safe_local_path(path, UPLOADS_DIR), "rb") as f:
                return f.read()
        except (OSError, ValueError):
            return None

    @app.route("/beats/<beat_id>/identify", methods=["POST"])
    def beat_identify(beat_id):
        """Send one sample to ACRCloud, on the producer's say-so.

        This is the one place a beat leaves the building for analysis,
        and it happens only when the button is pressed. The answer, or
        the vendor's error, is stored as a check so the page can show
        when it last ran and what it said.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        beat = store.get_beat(beat_id, user["id"])
        if beat is None:
            abort(404)
        if not acr_provider.configured():
            return redirect("/beats/" + beat_id)
        source = request.form.get("source") or "beat"
        if source == "clip":
            clip = request.files.get("clip")
            if clip is None or not clip.filename:
                return redirect("/beats/%s?fp=noclip#fingerprint" % beat_id)
            data = clip.read(acr_provider.MAX_CLIP_BYTES + 1)
            if len(data) > acr_provider.MAX_CLIP_BYTES:
                return redirect("/beats/%s?fp=big#fingerprint" % beat_id)
            mime, clip_name = clip.mimetype or "", clip.filename
        else:
            source = "beat"
            audio = store.get_beat_audio(beat_id)
            if audio is None or not audio["path"]:
                return redirect("/beats/%s?fp=noaudio#fingerprint" % beat_id)
            data = _beat_audio_bytes(audio)
            mime, clip_name = audio["mime"] or "", audio["filename"] or ""
            if data is None:
                store.add_beat_fingerprint_check(
                    beat_id, user["id"], source, clip_name, "error",
                    "The stored audio could not be read back.", [])
                return redirect("/beats/%s#fingerprint" % beat_id)
        sample = acr_provider.slice_sample(data, mime)
        try:
            matches = acr_provider.identify(sample)
            result, message = ("match" if matches else "none"), ""
        except acr_provider.AcrError as e:
            matches, result, message = [], "error", str(e)
        store.add_beat_fingerprint_check(beat_id, user["id"], source, clip_name,
                                         result, message, matches, sample_bytes=len(sample))
        return redirect("/beats/%s#fingerprint" % beat_id)

    @app.route("/beats/<beat_id>/stream")
    def beat_stream(beat_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        if store.get_beat(beat_id, user["id"]) is None:
            abort(404)
        audio = store.get_beat_audio(beat_id)
        if audio is None or not audio["path"]:
            abort(404)
        return _stream_beat(audio)

    @app.route("/beats/<beat_id>/audio/delete", methods=["POST"])
    def beat_audio_delete(beat_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        path = store.delete_beat_audio(user["id"], beat_id)
        if path is None:
            return jsonify({"ok": False}), 404
        try:
            blob_store.remove(path, uploads_dir=UPLOADS_DIR)
        except Exception:
            pass
        return jsonify({"ok": True})

    @app.route("/beats/<beat_id>/share", methods=["POST"])
    def beat_share_create(beat_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        body = request.get_json(silent=True) or {}
        token = store.create_beat_share(user["id"], beat_id,
                                        label=body.get("label") or "",
                                        days=body.get("days") or 0)
        if token is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "token": token,
                        "url": "%s/beat/%s" % (_remote_origin(), token),
                        "shares": store.list_beat_shares(user["id"], beat_id)})

    @app.route("/beats/<beat_id>/shares")
    def beat_share_list(beat_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        if store.get_beat(beat_id, user["id"]) is None:
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True, "shares": store.list_beat_shares(user["id"], beat_id),
                        "origin": _remote_origin()})

    @app.route("/beat-link/<token>/revoke", methods=["POST"])
    def beat_share_revoke(token):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        if not store.revoke_beat_share(user["id"], token):
            return jsonify({"ok": False}), 404
        return jsonify({"ok": True})

    @app.route("/beat/<token>")
    def beat_share_page(token):
        """Public on purpose: an artist listens to a beat somebody sent
        them without making an account. Standalone template, one beat,
        no catalogue."""
        share = store.get_beat_share(token)
        if share is None:
            return render_template("beat_share.html", gone=True), 404
        beat = share["beat"]
        audio = store.get_beat_audio(beat["id"])
        producer = store.get_user(beat["user_id"]) or {}
        return render_template(
            "beat_share.html", gone=False, token=token, beat=beat,
            audio=_beat_audio_public(audio), has_audio=bool(audio and audio["path"]),
            producer_name=producer.get("name") or "the producer",
            licence_types=producers.LICENCE_TYPES)

    @app.route("/beat/<token>/stream")
    def beat_share_stream(token):
        share = store.get_beat_share(token)
        if share is None:
            abort(404)
        audio = store.get_beat_audio(share["beat_id"])
        if audio is None or not audio["path"]:
            abort(404)
        # Count the play, not the page load: opening a link is not interest.
        if request.headers.get("Range", "").strip() in ("", "bytes=0-"):
            store.count_beat_share_play(token)
        return _stream_beat(audio)

    @app.route("/beats/<beat_id>/delete", methods=["POST"])
    def beat_delete(beat_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_beat(user["id"], beat_id)
        return redirect("/beats")

    @app.route("/beats/<beat_id>/clearance.csv")
    def beat_clearance_csv(beat_id):
        """The cleared list as a file, for the label that asked for it."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        beat = store.get_beat(beat_id, user["id"])
        if beat is None:
            abort(404)
        import csv as _csv
        import io as _io
        out = _io.StringIO()
        w = _csv.writer(out, lineterminator="\n")
        w.writerow(["Beat", "Cleared item", "Kind", "Licence", "Note", "Added"])
        licences = {l["id"]: l for l in store.list_beat_licences(beat_id)}
        for row in store.list_beat_clearances(beat_id):
            lic = licences.get(row["licence_id"] or "")
            w.writerow([beat["title"], row["value"], row["kind"],
                        ("%s (%s)" % (lic["licensee_name"] or lic["licensee_email"],
                                      lic["status"])) if lic else "",
                        row["note"], row["created"][:10]])
        return Response(out.getvalue(), mimetype="text/csv", headers={
            "Content-Disposition":
                'attachment; filename="cleared-%s.csv"' % beat_id[:8]})

    @app.route("/licence/<token>", methods=["GET", "POST"])
    def beat_licence_public(token):
        """The licensee's end: read the terms, sign once, keep the link."""
        licence = store.get_beat_licence_by_token(token)
        if licence is None:
            abort(404)
        signed = False
        if request.method == "POST":
            name = (request.form.get("signed_by") or "").strip()
            if name:
                signed = store.sign_beat_licence(token, name)
                if signed:
                    store.notify(licence["producer_id"], "recovery",
                                 "Licence signed: %s" % licence["beat_title"],
                                 "%s signed the %s licence." % (
                                     name, producers.licence_label(
                                         licence["licence_type"])),
                                 "/beats/%s" % licence["beat_id"])
                licence = store.get_beat_licence_by_token(token)
        return render_template("licence_public.html", licence=licence,
                               just_signed=signed,
                               signable=store.SIGNABLE_LICENCE_STATUSES,
                               type_label=producers.licence_label(
                                   licence["licence_type"]))

    @app.route("/cleared/<beat_id>")
    def beat_cleared_public(beat_id):
        """The page a label, distributor or supervisor checks.

        Public on purpose: its whole job is being checkable by somebody
        with no account here. It shows what the producer listed and the
        licence status behind it - never the fee, the terms text or the
        licensee's email.
        """
        beat = store.get_beat(beat_id)
        if beat is None:
            abort(404)
        query = (request.args.get("q") or "").strip()
        result = producers.clearance_for(beat_id, query) if query else None
        producer = store.get_user(beat["user_id"]) or {}
        rows = []
        licences = {l["id"]: l for l in store.list_beat_licences(beat_id)}
        for row in store.list_beat_clearances(beat_id):
            lic = licences.get(row["licence_id"] or "")
            rows.append({"value": row["value"], "kind": row["kind"],
                         "note": row["note"],
                         "licence_status": lic["status"] if lic else "",
                         "licence_type": producers.licence_label(
                             lic["licence_type"]) if lic else ""})
        return render_template("cleared_public.html", beat=beat, rows=rows,
                               query=query, result=result,
                               producer_name=producer.get("name") or "the producer")

    # --- OS Phase 2: recovery case management + deal room ----------------------

    _CASE_CATEGORIES = ["unmatched", "coverage_gap", "mechanical", "publishing",
                        "neighboring", "content_id", "distributor", "split_conflict",
                        "other"]
    _CASE_STATUSES = ["open", "submitted", "waiting", "won", "lost"]
    _DEAL_TYPES = ["split", "producer", "feature", "work_for_hire", "management",
                   "distribution", "label_services", "sync", "publishing_admin",
                   "advance", "merch", "touring", "brand"]
    _DEAL_STATUSES = ["draft", "sent", "negotiating", "signed", "expired", "cancelled"]

    @app.route("/royalty-recovery/cases", methods=["GET", "POST"])
    def recovery_cases():
        user = current_user()
        if user is None:
            return login_required_redirect()
        if request.method == "POST":
            f = request.form
            if f.get("case_id"):
                fields = {}
                if f.get("status") in _CASE_STATUSES:
                    fields["status"] = f["status"]
                if "notes" in f:
                    fields["notes"] = (f.get("notes") or "").strip()[:600]
                if f.get("evidence_doc_id"):
                    fields["evidence_doc_id"] = f["evidence_doc_id"]
                if f.get("payout_result"):
                    try:
                        fields["payout_result"] = float(f["payout_result"])
                    except ValueError:
                        pass
                if f.get("estimated_amount"):
                    try:
                        fields["estimated_amount"] = max(0.0, float(f["estimated_amount"]))
                    except ValueError:
                        pass
                if "deadline" in f:
                    fields["deadline"] = (f.get("deadline") or "").strip()[:10]
                if f.get("category") in _CASE_CATEGORIES:
                    fields["category"] = f["category"]
                store.update_recovery_case(user["id"], f["case_id"], fields)
                case = store.get_recovery_case(user["id"], f["case_id"])
                if case and f.get("status") == "won":
                    store.notify(user["id"], "recovery",
                                 "Case won: %s" % case["title"],
                                 "Recovered $%.2f." % (case.get("payout_result") or 0),
                                 "/royalty-recovery/cases")
            elif (f.get("title") or "").strip():
                store.create_recovery_case(user["id"], {
                    "title": f["title"].strip(),
                    "category": f.get("category") if f.get("category") in _CASE_CATEGORIES else "other",
                    "estimated_amount": f.get("estimated_amount") or 0,
                    "confidence": f.get("confidence") or "medium",
                    "deadline": (f.get("deadline") or "").strip(),
                    "notes": (f.get("notes") or "").strip()})
            return redirect(_safe_next(f.get("next"), "/royalty-recovery/cases"))
        cases = store.list_recovery_cases(user["id"])
        recovered = sum(c.get("payout_result") or 0 for c in cases if c["status"] == "won")
        pipeline = sum(c["estimated_amount"] for c in cases
                       if c["status"] in ("open", "submitted", "waiting"))
        docs = {d["id"]: d for d in store.list_documents(user["id"])}
        # The strip: ?new=1 opens it empty, ?case=<id> opens it on a case.
        strip_case = _strip_case(user["id"], request.args.get("case"))
        strip_open = bool(strip_case) or bool(request.args.get("new"))
        return render_template("recovery_cases.html", active_page="cases",
                               cases=cases, recovered=recovered, pipeline=pipeline,
                               docs=docs, doc_list=list(docs.values()),
                               categories=_CASE_CATEGORIES, statuses=_CASE_STATUSES,
                               strip_case=strip_case, strip_open=strip_open,
                               strip_next=("/royalty-recovery/cases?case=%s#case-strip" % strip_case["id"])
                               if strip_case else "/royalty-recovery/cases",
                               strip_close="/royalty-recovery/cases",
                               # What the press that arrived here did. A press
                               # that changed nothing has to say so, or the
                               # page looks like it ignored it.
                               opened=request.args.get("opened", ""),
                               **build_dashboard_context())

    @app.route("/isrc/diag")
    def isrc_diag():
        """What each store says about one recording, and what it could not say.

        Exists because the Songstats response shape could not be confirmed
        while writing the lookup: the key is on the deployment rather than
        in a development shell, and their documentation site serves no
        readable content. Rather than guess twice, the parser reports the
        top-level keys it did not recognise and this prints them - so the
        real shape is read off production once and fixed precisely.

        Owner only, and no value from any credential appears in the reply.
        """
        user, bail = _owner_or_404()
        if bail:
            return bail
        isrc = (request.args.get("isrc") or "").strip()
        if not isrc:
            rows = store.get_statement_rows(user["id"])
            isrc = next((r["isrc"] for r in rows if r["isrc"]), "")
        report = {
            "isrc": isrc or None,
            "deezer": None,
            "songstats": None,
            "sorted": None,
        }
        if isrc:
            present, detail = music_apis.deezer_has_isrc(isrc)
            report["deezer"] = {"carries_it": present, "detail": detail}
            spotify_id = coverage_check.spotify_track_id_for(isrc)
            report["spotify_track_id"] = spotify_id or None
            links, note = coverage_check._songstats_links(isrc, spotify_track_id=spotify_id)
            report["songstats"] = {"platforms": sorted(links), "note": note}
            report["sorted"] = coverage_check.check_gap(
                isrc, ["Deezer", "Spotify", "Anghami", "Pandora",
                       "SoundExchange: Sirius XM Radio, Inc"])
            # ?probe=1 tries every candidate Songstats lookup and reports
            # which one answers, plus the keys it sent back. /tracks/info
            # with a raw ISRC returns "Entity not found" against a valid
            # key, so the path is right and the lookup key is not - and
            # one round trip against the real API settles which, rather
            # than one guess per deploy.
            if request.args.get("probe"):
                import signal_providers as sp
                report["songstats_probe"] = sp.SongstatsAdapter().probe_track(
                    isrc, spotify_track_id=spotify_id)
        return jsonify(report)

    @app.route("/royalty-recovery/cases/<case_id>/delete", methods=["POST"])
    def recovery_case_delete(case_id):
        """Remove a case. There was no way to, so a case opened by
        mistake stayed in the pipeline total for ever."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_recovery_case(user["id"], case_id)
        return redirect(_safe_next(request.form.get("next"), "/royalty-recovery/cases?deleted=1"))

    @app.route("/royalty-recovery/cases/<case_id>/letter")
    def recovery_case_letter(case_id):
        """The draft to send the distributor about this case.

        Drafted, never sent: a letter about money goes from the artist's
        own address under their own name. What the app can do is assemble
        the evidence and get the wording right.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        case = store.get_recovery_case(user["id"], case_id)
        if case is None:
            abort(404)
        # The track this case is about, and what the stores said when
        # asked - if they were asked at all. An unchecked case gets the
        # letter that says so rather than a confident one.
        view = recovery_engine.build(user["id"])
        finding = next((f for f in view["findings"]
                        if f.get("case_title") == case["title"]), None)
        rows = store.get_statement_rows(user["id"])
        track = (finding or {}).get("track") or ""
        isrc = next((r["isrc"] for r in rows
                     if (r["title"] or "").strip() == track and r["isrc"]), "")
        periods = sorted({(r["period"] or "").strip() for r in rows if r["period"]})
        # The stores' answer, if the artist asked them from the Statements
        # page: a letter about a store that carries the recording can say
        # so; one about an unchecked store must not.
        import statements_desk
        stored = store.get_gap_checks(user["id"]).get(statements_desk.slug(track)) if track else None
        letter = distributor_letter.draft(
            artist=user.get("name") or "", track=track,
            period=", ".join(periods), check=(stored or {}).get("result"),
            estimate=(finding or {}).get("amount"), isrc=isrc)
        return render_template("recovery_case_letter.html", case=case,
                               letter=letter, track=track, isrc=isrc,
                               **build_dashboard_context())

    @app.route("/royalty-recovery/cases/<case_id>/sent", methods=["POST"])
    def recovery_case_sent(case_id):
        """Record that the letter actually went out.

        This is what moves a case to submitted. The old page offered
        "Mark Submitted" against nothing at all, so a case could read as
        submitted with no letter and no document behind it.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        to = (request.form.get("to") or "the distributor").strip()[:80]
        store.record_case_evidence(user["id"], case_id, "letter",
                                   "Letter sent to %s" % to)
        return redirect(_safe_next(request.form.get("next"),
                                   "/royalty-recovery/cases?sent=1#case-%s" % case_id))

    @app.route("/royalty-recovery/cases/from-finding", methods=["POST"])
    def case_from_finding():
        """Open the case behind a finding - once.

        A finding is a repeatable thing: the sweep runs again, the browser
        replays the POST, the hand double-presses. This route used to make
        a new case every time, and the only guard was cosmetic - the MLC
        sweep swapping its button for "Case open" once a case with that
        exact title existed, which a second sweep or a back button walks
        straight past. That was untidy and nothing more while every
        finding-sourced case was worth 0. It is not, now that a case
        carries the money the gap is measured at: the duplicate adds that
        money to the recovery pipeline a second time, and the money only
        exists once. So the form posts the finding's own identity and the
        store keeps one live case per identity - refreshed, not repeated,
        when a later sweep measures a different share.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        f = request.form
        case_id, opened = store.open_case_for_finding(
            user["id"], f.get("case_key"), {
                "title": (f.get("title") or "Statement finding").strip(),
                "category": f.get("category") if f.get("category") in _CASE_CATEGORIES else "other",
                "estimated_amount": f.get("amount") or 0,
                "confidence": "high" if f.get("category") == "unmatched" else "medium",
                "notes": (f.get("notes") or "").strip()})
        if _safe_next(f.get("next"), "").startswith("/recovery"):
            return redirect("/recovery?opened=%s&case=%s#case-strip" % (opened, case_id))
        return redirect("/royalty-recovery/cases?opened=%s#case-%s" % (opened, case_id))

    @app.route("/deal-room", methods=["GET", "POST"])
    def deal_room():
        user = current_user()
        if user is None:
            return login_required_redirect()
        if request.method == "POST":
            f = request.form
            if f.get("deal_id"):
                fields = {}
                if f.get("status") in _DEAL_STATUSES:
                    fields["status"] = f["status"]
                if "terms" in f:
                    fields["terms"] = (f.get("terms") or "").strip()[:600]
                if f.get("doc_id"):
                    fields["doc_id"] = f["doc_id"]
                store.update_deal(user["id"], f["deal_id"], fields)
                if f.get("status") == "signed":
                    store.notify(user["id"], "campaign", "Deal signed",
                                 "A deal moved to signed in your Deal Room.",
                                 "/deal-room")
            elif (f.get("title") or "").strip():
                store.create_deal(user["id"], {
                    "title": f["title"].strip(),
                    "deal_type": f.get("deal_type") if f.get("deal_type") in _DEAL_TYPES else "split",
                    "counterparty": (f.get("counterparty") or "").strip(),
                    "terms": (f.get("terms") or "").strip(),
                    "deadline": (f.get("deadline") or "").strip()})
            return redirect("/deal-room")
        deals = store.list_deals(user["id"])
        docs = {d["id"]: d for d in store.list_documents(user["id"])}
        return render_template("deal_room.html", active_page="deals",
                               deals=deals, docs=docs, doc_list=list(docs.values()),
                               deal_types=_DEAL_TYPES, deal_statuses=_DEAL_STATUSES,
                               **build_dashboard_context())

    @app.route("/deal-room/generate-split", methods=["POST"])
    def generate_split_agreement():
        user = current_user()
        if user is None:
            return login_required_redirect()
        f = request.form
        track = (f.get("track") or "Untitled Track").strip()[:120]
        parties = []
        for i in range(1, 5):
            name = (f.get("party%d_name" % i) or "").strip()
            share = (f.get("party%d_share" % i) or "").strip()
            if name and share:
                parties.append((name, share))
        if len(parties) < 2:
            return redirect("/deal-room")
        lines = [
            "SPLIT AGREEMENT (TEMPLATE)",
            "=" * 40, "",
            "Track: %s" % track,
            "Date: %s" % datetime.now(timezone.utc).strftime("%Y-%m-%d"), "",
            "The undersigned agree to the following ownership splits for the",
            "composition and/or master recording of the track named above:", "",
        ]
        for name, share in parties:
            lines.append("  %s ....... %s%%" % (name.ljust(30, " "), share))
        lines += ["", "Each party warrants their contribution is original.",
                  "Signatures:", ""]
        for name, _unused in parties:
            lines.append("  ______________________  (%s)   Date: __________" % name)
        lines += ["", "-" * 40,
                  "Generated by Street Banker Deal Room as a starting template.",
                  "NOT LEGAL ADVICE - have an attorney review before signing."]
        fname = "doc_%s.txt" % uuid.uuid4().hex
        with open(os.path.join(UPLOADS_DIR, fname), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        doc_id = store.add_document(user["id"], "split-agreement-%s.txt" % _slugify(track),
                                    "/uploads/" + fname, "Split Agreement",
                                    "Generated template - attorney review required")
        store.create_deal(user["id"], {
            "title": "Split: %s" % track, "deal_type": "split",
            "counterparty": ", ".join(n for n, _unused in parties),
            "terms": " / ".join("%s %s%%" % (n, sh) for n, sh in parties),
            "doc_id": doc_id})
        return redirect("/deal-room")

    _SYNC_AUDIO_EXTS = ("mp3", "wav", "m4a", "aiff", "aif", "flac")

    def _sync_audio_upload(field):
        f = request.files.get(field)
        if f is None or not f.filename:
            return ""
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in _SYNC_AUDIO_EXTS:
            return ""
        fname = "sync_%s.%s" % (uuid.uuid4().hex, ext)
        f.save(os.path.join(UPLOADS_DIR, fname))
        return "/uploads/" + fname

    @app.route("/sync/clearance-packs", methods=["GET", "POST"])
    def sync_packs():
        user = current_user()
        if user is None:
            return login_required_redirect()
        error = None
        if request.method == "POST":
            f = request.form
            if f.get("pack_id"):
                fields = {}
                if f.get("status") in ("active", "archived"):
                    fields["status"] = f["status"]
                for key in ("master_status", "publishing_status"):
                    if f.get(key) in ("cleared", "pending", "unconfirmed"):
                        fields[key] = f[key]
                store.update_sync_pack(user["id"], f["pack_id"], fields)
                return redirect("/sync/clearance-packs")
            title = (f.get("title") or "").strip()
            if not title:
                error = "A track title is required."
            else:
                main_url = _sync_audio_upload("main_audio")
                if not main_url:
                    error = "Upload the main audio (MP3, WAV, M4A, AIFF, or FLAC)."
                else:
                    # The slug is the pack's public address and unique across
                    # every account; a title somebody already used gets a
                    # short suffix instead of a 500 (walk, 2026-09-20).
                    base = _ml_slug("sync-" + title)
                    slug = base
                    while store.get_sync_pack_by_slug(slug) is not None:
                        slug = "%s-%s" % (base, uuid.uuid4().hex[:4])
                    store.create_sync_pack(user["id"], slug, {
                        "title": title,
                        "artist_name": (f.get("artist_name") or "").strip(),
                        "bpm": (f.get("bpm") or "").strip(),
                        "song_key": (f.get("song_key") or "").strip(),
                        "moods": (f.get("moods") or "").strip(),
                        "master_status": f.get("master_status") if f.get("master_status") in ("cleared", "pending", "unconfirmed") else "unconfirmed",
                        "publishing_status": f.get("publishing_status") if f.get("publishing_status") in ("cleared", "pending", "unconfirmed") else "unconfirmed",
                        "ownership_note": (f.get("ownership_note") or "").strip(),
                        "contact_email": (f.get("contact_email") or "").strip(),
                        "main_url": main_url,
                        "instrumental_url": _sync_audio_upload("instrumental_audio"),
                        "clean_url": _sync_audio_upload("clean_audio")})
                    return redirect("/sync/clearance-packs")
        # Its own sidebar entry beside the releases since 2026-09-19 (owner:
        # "You're making a product for sale"), so it lights itself.
        return render_template("sync_packs.html", active_page="sync-packs",
                               packs=store.list_sync_packs(user["id"]), error=error,
                               **build_dashboard_context())

    @app.route("/sync/clearance-packs/<pack_id>/delete", methods=["POST"])
    def sync_pack_delete(pack_id):
        """Delete a clearance pack, and the audio it holds.

        Archiving only hid a pack from supervisors: the row stayed, the
        private /s/<slug> link stayed, and up to three uploaded files
        stayed on the disk with nothing left that could reach them. A
        pitch pack an artist wants gone - a track they lost the rights
        to, a version they should never have sent - has to actually go.

        `delete_sync_pack` scopes the row to this account and returns
        None otherwise, so a pack belonging to somebody else is answered
        the same way as one that never existed: 404, and nothing about
        whose it was. An empty list is different - a real pack that held
        no audio - and deletes without complaint.

        The unlink is the narrow rule /vault/<id>/delete established:
        only `sync_<uuid>`, the name `_sync_audio_upload` writes. Nothing
        else in the uploads directory can be reached from here.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        paths = store.delete_sync_pack(user["id"], pack_id)
        if paths is None:
            abort(404)
        # Only the slots that held something are unlinked; an absent
        # instrumental or clean edit is a no-op, not a failure.
        for path in paths:
            if os.path.basename(path.split("?")[0]).startswith("sync_"):
                blob_store.remove(path, uploads_dir=UPLOADS_DIR)
        return redirect("/sync/clearance-packs")

    @app.route("/s/<slug>")
    def sync_pack_public(slug):
        pack = store.get_sync_pack_by_slug(slug, count_view=True)
        if pack is None or pack["status"] != "active":
            abort(404)
        return render_template("sync_pack_public.html", p=pack)

    @app.route("/s/<slug>/request", methods=["POST"])
    def sync_pack_request(slug):
        pack = store.get_sync_pack_by_slug(slug)
        if pack is None or pack["status"] != "active":
            abort(404)
        f = request.form
        email = (f.get("email") or "").strip()
        message = (f.get("message") or "").strip()[:600]
        if "@" not in email:
            return jsonify({"ok": False, "error": "Enter a valid email."}), 400
        store.add_inbox("sync_request", {"pack": pack["title"], "slug": slug,
                                         "email": email, "message": message},
                        user_id=pack["user_id"])
        store.notify(pack["user_id"], "campaign",
                     "License request: %s" % pack["title"],
                     "%s asked about this track via your sync pack link." % email,
                     "/inbox")
        return jsonify({"ok": True,
                        "message": "Request sent - the rights holder will follow up."})

    @app.route("/sync/deal-simulator", methods=["GET", "POST"])
    def deal_simulator():
        user = current_user()
        if user is None:
            return login_required_redirect()
        result, inp = None, {}
        if request.method == "POST":
            f = request.form
            inp = {"fee": f.get("fee") or 0, "media": f.get("media"),
                   "term": f.get("term"), "territory": f.get("territory"),
                   "exclusive": bool(f.get("exclusive")),
                   "all_media": bool(f.get("all_media")),
                   "mfn": bool(f.get("mfn")), "buyout": bool(f.get("buyout"))}
            try:
                inp["fee"] = float(inp["fee"])
            except (TypeError, ValueError):
                inp["fee"] = 0
            result = sync_simulator.simulate(inp)
        return render_template("deal_simulator.html", active_page="deals",
                               result=result, inp=inp, sim=sync_simulator,
                               **build_dashboard_context())

    @app.route("/artist-twin", methods=["GET", "POST"])
    def artist_twin_page():
        user = current_user()
        if user is None:
            return login_required_redirect()
        settings = store.get_twin_settings(user["id"]) or {
            "sources": [k for k, _label in twin.SOURCES], "tone": "premium",
            "do_not_say": ""}
        generated = None
        if request.method == "POST":
            f = request.form
            if f.get("save_settings"):
                sources = [k for k, _label in twin.SOURCES if f.get("src_" + k)]
                tone = f.get("tone") if f.get("tone") in dict(twin.TONES) else "premium"
                store.save_twin_settings(user["id"], sources, tone,
                                         (f.get("do_not_say") or "").strip())
                return redirect("/artist-twin")
            kind = f.get("kind")
            if kind in twin.OUTPUT_KEYS:
                enabled = set(settings["sources"])
                facts, used = twin.gather_context(user["id"], enabled)
                do_not_say = [p.strip() for p in
                              (settings.get("do_not_say") or "").split(",") if p.strip()]
                text = twin.generate(kind, facts, settings.get("tone", "premium"),
                                     do_not_say)
                store.save_twin_generation(user["id"], kind, text, ", ".join(used))
                generated = {"kind": kind, "text": text, "used": used}
        os_tracks_list = store.list_os_tracks(user["id"])
        osctx = _os_ctx(user["id"])
        strategist = artist_os.twin_report(
            os_tracks_list, osctx,
            store.list_pulse_snapshots(user["id"], limit=30),
            artist_os.action_queue([(t, osctx) for t in os_tracks_list]),
            analysis=store.latest_track_analysis(user["id"]))
        # Artist Signal Profile: priorities the artist set on the homepage
        # EQ. Selected, not measured - the template labels it that way.
        signal = store.get_artist_signal_profile(user["id"])
        signal_ctx = None
        if signal and signal.get("topPriorities"):
            signal_ctx = {
                "top": signal["topPriorities"][:3],
                "lane": signal.get("recommendedLane") or "",
                "preset": signal.get("preset") or "Custom Mix",
                "updated": (signal.get("_updated") or "")[:10],
            }
        return render_template("artist_twin.html", active_page="artist-twin",
                               settings=settings, twin=twin, generated=generated,
                               strategist=strategist, signal=signal_ctx,
                               history=store.list_twin_generations(user["id"]),
                               **build_dashboard_context())

    _EXPENSE_CATEGORIES = ["production", "mixing_mastering", "artwork", "video",
                           "marketing_ads", "content", "street_team",
                           "playlist_press", "travel", "other"]

    @app.route("/revenue-os", methods=["GET", "POST"])
    def revenue_os():
        user = current_user()
        if user is None:
            return login_required_redirect()
        if request.method == "POST":
            f = request.form
            if f.get("delete_id"):
                store.delete_expense(user["id"], f["delete_id"])
            elif (f.get("description") or "").strip() and f.get("amount"):
                try:
                    amount = float(f["amount"])
                except ValueError:
                    amount = 0
                if amount > 0:
                    store.add_expense(
                        user["id"],
                        f.get("category") if f.get("category") in _EXPENSE_CATEGORIES else "other",
                        f["description"].strip(), amount,
                        (f.get("spend_date") or "").strip())
            return redirect("/revenue-os")
        expenses = store.list_expenses(user["id"])
        total_expenses = sum(e["amount"] for e in expenses)
        by_category = {}
        for e in expenses:
            by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount"]
        summary = build_royalty_summary(store.get_statement_rows(user["id"]))
        # No statement, no income figure: None, never 0, so the page says
        # "Not measured" and draws no net and no verdict (audit, 2026-09-15:
        # a fresh account read "$0.00 Profitable").
        income = summary["total"] if summary else None
        return render_template("revenue_os.html", active_page="revenue-os",
                               expenses=expenses, total_expenses=total_expenses,
                               by_category=sorted(by_category.items(),
                                                  key=lambda x: x[1], reverse=True),
                               income=income,
                               net=(round(income - total_expenses, 2)
                                    if income is not None else None),
                               summary=summary, categories=_EXPENSE_CATEGORIES,
                               **build_dashboard_context())

    @app.route("/trust-score")
    def trust_score_page():
        user = current_user()
        if user is None:
            return login_required_redirect()
        t = trust_score.calculate(user["id"])            # records itself
        return render_template("trust_score.html", active_page="scores",
                               t=t,
                               trend=score_history.summarise(
                                   "trust",
                                   store.score_trend(user["id"], "trust")),
                               **build_dashboard_context())

    @app.route("/pulse")
    def pulse_page():
        user = current_user()
        if user is None:
            return login_required_redirect()
        profile = store.get_pulse_profile(user["id"])
        pulse, deezer = None, None
        if profile and spotify.pulse_configured():
            pulse = spotify.artist_pulse(profile["artist_id"])
            if pulse:
                deezer = music_apis.deezer_artist_fans(pulse["name"])
                # None when Deezer was not reached. `.get("fans", 0)` wrote
                # a nought for an unanswered call, which claims a following
                # of nobody - the same false reading the column was made
                # nullable to stop.
                store.record_pulse_snapshot(
                    user["id"], pulse["followers"], pulse["popularity"],
                    (deezer or {}).get("fans"))
        # Monthly listeners, which Spotify's own public API does not
        # carry, from whichever provider the registry has for CAP_METRICS.
        # None of this is required for the Spotify and Deezer blocks: with
        # no real metrics provider the page is exactly what it was.
        metrics = _provider_metrics(user["id"], profile) if profile else None
        # Everything else the provider holds on the artist (owner,
        # 2026-09-14: "as much information as we can find"): nine
        # questions, each its own call and its own failure, cached six
        # hours like the instruments. The provider id was resolved and
        # stored by _provider_metrics, so this spends no search.
        everything = None
        if profile and metrics is not None:
            import pulse_everything
            _prov = _metrics_provider()
            _pid = (profile.get("provider_artist_id") or "") if profile.get("provider") == getattr(_prov, "key", None) else ""
            if _prov is not None and _pid:
                everything = pulse_everything.build(_prov, _pid)
        # YouTube: only for a channel the owner has named, and never
        # derived from the artist name (see _youtube_pulse).
        youtube = _youtube_pulse(user["id"], profile,
                                 error=_YT_ERRORS.get(request.args.get("yt") or "",
                                                      (request.args.get("yt") or "")[:200]))
        snaps = store.list_pulse_snapshots(user["id"], limit=30)
        # Peers: pinned artists' PUBLIC Spotify numbers, snapshotted on the
        # same cadence — a real comparison, not a modeled one.
        peers = []
        for peer in store.list_pulse_peers(user["id"]):
            row = {"artist_id": peer["artist_id"], "name": peer["name"],
                   "image": peer["image"], "followers": None,
                   "popularity": None, "delta7": None}
            if spotify.pulse_configured():
                live = spotify.artist_pulse(peer["artist_id"])
                if live:
                    store.record_peer_snapshot(user["id"], peer["artist_id"],
                                               live["followers"],
                                               live["popularity"])
                    row["followers"] = live["followers"]
                    row["popularity"] = live["popularity"]
            history = store.list_peer_snapshots(user["id"], peer["artist_id"])
            week_ago = (datetime.now(timezone.utc).date()
                        - timedelta(days=7)).isoformat()
            base = next((s for s in history if s["day"] <= week_ago),
                        history[0] if history else None)
            if base and row["followers"] is not None and base["followers"]:
                row["delta7"] = row["followers"] - base["followers"]
            peers.append(row)
        my_delta7 = None
        if pulse and snaps:
            week_ago = (datetime.now(timezone.utc).date()
                        - timedelta(days=7)).isoformat()
            base = next((s for s in snaps if s["day"] <= week_ago), snaps[0])
            # Both ends have to be measured. Spotify omits `followers`
            # for some apps, and the difference between a number and a
            # silence is not a change - it is one reading.
            if base["followers"] and pulse["followers"] is not None:
                my_delta7 = pulse["followers"] - base["followers"]
        # Milestone: the largest round follower number crossed between the
        # oldest snapshot on file and today — detection, not prediction.
        milestone = None
        if pulse and snaps and len(snaps) > 1 and pulse["followers"] is not None:
            start = min(s["followers"] for s in snaps if s["followers"]) \
                if any(s["followers"] for s in snaps) else 0
            for level in (1000000, 500000, 100000, 50000, 10000, 5000,
                          1000, 500, 100):
                if start < level <= pulse["followers"]:
                    milestone = level
                    break
        # Owned engagement, folded in from /stats: counts from the artist's
        # own tracked smart links. First-party, so it shows whether or not
        # Spotify is configured.
        # The events written are "page_view" and "service_click" - see the
        # track() calls on the public link page. This read "pageview" and
        # "click", which nothing writes, so the tile showed 0 for every
        # account no matter how much traffic a link took, under copy
        # saying "Counted from your own tracked smart links".
        #
        # The Partner Portal already summed both spellings, so the
        # mismatch was known there and never carried back here. Both are
        # summed for the same reason: it costs nothing and a row written
        # under an older spelling still counts.
        clicks = pageviews = presaves = 0
        for c in mls.list_campaigns(user["id"]):
            n = mls.event_counts(c["id"])
            pageviews += n.get("page_view", 0) + n.get("pageview", 0)
            clicks += n.get("service_click", 0) + n.get("click", 0)
            ps = store.count_spotify_presaves(c["id"])
            presaves += ps.get("pending", 0) + ps.get("completed", 0)
        import pulse_signals
        instruments = pulse_signals.build(pulse, metrics, youtube, deezer, snaps) if profile else []
        return render_template("pulse.html", active_page="pulse",
                               instruments=instruments,
                               everything=everything,
                               pulse_configured=spotify.pulse_configured(),
                               profile=profile, pulse=pulse, deezer=deezer,
                               metrics=metrics, youtube=youtube,
                               snaps=snaps, peers=peers, my_delta7=my_delta7,
                               pulse_can_change=_pulse_change_allowed(user),
                               soundcharts_paused=soundcharts_budget.customers_paused(),
                               milestone=milestone,
                               link_stats={"pageviews": pageviews, "clicks": clicks,
                                           "presaves": presaves},
                               **build_dashboard_context())

    @app.route("/pulse/peer/add", methods=["POST"])
    def pulse_peer_add():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        p = request.get_json(silent=True) or {}
        artist_id = (p.get("id") or "").strip()[:64]
        name = (p.get("name") or "").strip()[:120]
        if not artist_id or not name:
            return jsonify({"ok": False, "error": "Pick an artist from the "
                            "search results."}), 400
        profile = store.get_pulse_profile(user["id"])
        if profile and profile["artist_id"] == artist_id:
            return jsonify({"ok": False, "error": "That's you — pin someone "
                            "to compare against."}), 400
        if len(store.list_pulse_peers(user["id"])) >= 3:
            return jsonify({"ok": False, "error": "Three peers max — remove "
                            "one first."}), 400
        store.add_pulse_peer(user["id"], artist_id, name,
                             (p.get("image") or "").strip()[:300])
        return jsonify({"ok": True})

    @app.route("/pulse/peer/<artist_id>/remove", methods=["POST"])
    def pulse_peer_remove(artist_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        store.delete_pulse_peer(user["id"], artist_id)
        return jsonify({"ok": True})

    @app.route("/pulse/search")
    def pulse_search():
        if current_user() is None:
            return jsonify({"ok": False, "results": []}), 401
        results = spotify.search_artists(request.args.get("q"))
        # An empty list has two very different causes. Say which one.
        refused = spotify.last_refusal() if not results else None
        return jsonify({"ok": True, "results": results,
                        "refused": refused or ""})

    # Every new Pulse artist costs about two dozen Soundcharts calls from the
    # owner's monthly allowance, and nothing capped how often an account
    # could switch (2026-09-18 check: 12 switches, 276 calls). Owner, the
    # same day: "make pulse only changable on pro accounts". Every account
    # picks its artist once; changing it, or clearing it to pick again,
    # comes with Pro and Label. The owner is never held.
    _PULSE_LOCKED = ("Changing your Pulse artist comes with the Pro membership. "
                     "Picked the wrong artist? Email hello@streetbankermusic.com.")

    def _pulse_change_allowed(user):
        return (_is_owner_email(user.get("email"))
                or (user.get("plan") or "artist") in ("pro", "label"))

    @app.route("/pulse/select", methods=["POST"])
    def pulse_select():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        p = request.get_json(silent=True) or {}
        artist_id = (p.get("id") or "").strip()[:64]
        name = (p.get("name") or "").strip()[:120]
        if not artist_id or not name:
            return jsonify({"ok": False, "error": "Pick an artist from the search results."}), 400
        current = store.get_pulse_profile(user["id"])
        if current and current["artist_id"] != artist_id and not _pulse_change_allowed(user):
            return jsonify({"ok": False, "error": _PULSE_LOCKED}), 402
        store.save_pulse_profile(user["id"], artist_id, name,
                                 (p.get("image") or "").strip()[:300])
        return jsonify({"ok": True})

    @app.route("/pulse/youtube/search")
    def pulse_youtube_search():
        """Channels matching a typed name, for the person to pick from
        (owner, 2026-09-14: "no one ever knows their handle"). The pick
        itself posts to /pulse/youtube with the channel id, like a paste."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "results": [], "error": "Sign in first."}), 401
        prov = _youtube_adapter()
        if prov is None or not prov.configured():
            return jsonify({"ok": False, "results": [], "error": _YT_ERRORS["unconfigured"]})
        q = (request.args.get("q") or "").strip()[:100]
        if not q:
            return jsonify({"ok": True, "results": []})
        try:
            results = prov.search_channels(q)
        except Exception as e:                                  # noqa: BLE001
            return jsonify({"ok": False, "results": [], "error": prov.redact(e)[:200]})
        return jsonify({"ok": True, "results": results})

    @app.route("/pulse/youtube", methods=["POST"])
    def pulse_youtube():
        """Save the channel the owner named, resolved to YouTube's own id.

        The typed value is resolved ONCE here rather than on every page
        load, so the id is what is stored and the page then only ever
        spends the 1-unit channels.list read. An empty field clears it.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        raw = (request.form.get("channel") or "").strip()[:200]
        if not raw:
            store.save_pulse_youtube_channel(user["id"], "")
            return redirect("/pulse#youtube")
        prov = _youtube_adapter()
        if prov is None or not prov.configured():
            return redirect("/pulse?yt=unconfigured#youtube")
        try:
            channel_id = prov.resolve_channel(raw)
        except Exception as e:                                  # noqa: BLE001
            # Google's own reason travels to the owner: quotaExceeded means
            # wait, keyInvalid means fix the key. "Something went wrong"
            # would tell them neither.
            return redirect("/pulse?" + urllib.parse.urlencode(
                {"yt": prov.redact(e)[:200]}) + "#youtube")
        if not channel_id:
            return redirect("/pulse?yt=notfound#youtube")
        store.save_pulse_youtube_channel(user["id"], channel_id)
        return redirect("/pulse#youtube")

    @app.route("/pulse/clear", methods=["POST"])
    def pulse_clear():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        # Clearing is how a change starts, so it follows the same rule.
        if store.get_pulse_profile(user["id"]) and not _pulse_change_allowed(user):
            return jsonify({"ok": False, "error": _PULSE_LOCKED}), 402
        store.clear_pulse_profile(user["id"])
        return jsonify({"ok": True})

    @app.route("/walkthrough")
    def walkthrough():
        user = current_user()
        if user is None:
            return login_required_redirect()
        # The walkthrough is the demo's tour: step one uploads a sample
        # statement, and in a real account that became real-looking income
        # ($1,504.68 on Royalties and Tax, a $36,112 valuation; found by the
        # 2026-09-18 launch check). A real account gets tutor mode on its
        # own Command Center instead, which works from its own data.
        if not _is_demo_email(user.get("email") or ""):
            return redirect("/command-center")
        return render_template("walkthrough.html", active_page="command-center",
                               user_plan=(user.get("plan") or "artist"),
                               **build_dashboard_context())

    @app.route("/walkthrough/sample-statement.csv")
    def walkthrough_sample_csv():
        rows = ["Track Title,Store,Net Revenue,Sales Period",
                "Midnight Drive,Spotify,412.83,2026-04",
                "Midnight Drive,Apple Music,208.11,2026-04",
                "Midnight Drive,Spotify,391.20,2026-05",
                "Neon Dreams,Spotify,146.55,2026-04",
                "Neon Dreams,Spotify,171.32,2026-05",
                "Digital Paradise,Apple Music,88.90,2026-05",
                ",Spotify,64.27,2026-05",
                ",Apple Music,21.50,2026-04"]
        return Response("\n".join(rows) + "\n", mimetype="text/csv", headers={
            "Content-Disposition": "attachment; filename=sample-statement.csv"})

    # --- Release OS: qualification, artist profile, vault, review queue --------

    @app.route("/qualification")
    def qualification_page():
        user = current_user()
        if user is None:
            return login_required_redirect()
        # calculate() records today's reading itself, so the trend below
        # always includes it.
        q = qualification.calculate(user["id"])
        return render_template("qualification.html", active_page="scores",
                               q=q,
                               trend=score_history.summarise(
                                   "qualification",
                                   store.score_trend(user["id"], "qualification")),
                               **build_dashboard_context())

    @app.route("/artist-profile")
    def artist_profile():
        """The label-facing one-sheet was a second read of the press kit
        with no field on it. The press kit is the one document now (owner,
        2026-09-19: "It just needs to be an EPK"), so this address lands
        there; the template was removed with it."""
        return redirect("/epk", code=301)

    # --- The homepage, editable without a deploy ---------------------------

    def _homepage_fields(cfg):
        """Every editable field, flat, as (key, label, value, kind).

        Flat on purpose: the form, the save and the validator all walk the
        same list, so a field cannot exist in one and be missed by another.
        """
        hero, nav, footer = cfg["hero"], cfg["nav"], cfg["footer"]
        head = (hero.get("headline") or ["", ""]) + ["", ""]
        rows = [
            ("hero.eyebrow", "Eyebrow, above the headline", hero.get("eyebrow") or "", "text"),
            ("hero.headline.0", "Headline, first line", head[0], "text"),
            ("hero.headline.1", "Headline, second line", head[1], "text"),
            ("hero.support", "Supporting paragraph", hero.get("support") or "", "long"),
            ("nav.logo.primary", "Logo wordmark", nav["logo"].get("primary") or "", "text"),
            ("nav.logo.secondary", "Logo strapline", nav["logo"].get("secondary") or "", "text"),
            ("nav.cta.label", "Header button", nav["cta"].get("label") or "", "text"),
            ("nav.cta.short", "Header button, short form", nav["cta"].get("short") or "", "text"),
            ("nav.cta.href", "Header button link", nav["cta"].get("href") or "", "link"),
            ("footer.copyright", "Footer copyright line", footer.get("copyright") or "", "text"),
        ]
        for i, cta in enumerate(hero.get("ctas") or []):
            rows.append(("hero.ctas.%d.label" % i,
                         "Hero button %d" % (i + 1), cta.get("label") or "", "text"))
            rows.append(("hero.ctas.%d.href" % i,
                         "Hero button %d link" % (i + 1), cta.get("href") or "", "link"))
        for i, link in enumerate(nav.get("links") or []):
            rows.append(("nav.links.%d.label" % i,
                         "Menu item %d" % (i + 1), link.get("label") or "", "text"))
            rows.append(("nav.links.%d.href" % i,
                         "Menu item %d link" % (i + 1), link.get("href") or "", "link"))
        return rows

    def _homepage_nest(flat):
        """Turn dotted keys back into the shape landing_config uses."""
        out = {}
        for key, value in flat.items():
            node, parts = out, key.split(".")
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value
        return _homepage_lists(out)

    def _homepage_lists(node):
        """A dict whose keys are 0,1,2... was a list before it was flattened."""
        if not isinstance(node, dict):
            return node
        node = {k: _homepage_lists(v) for k, v in node.items()}
        if node and all(k.isdigit() for k in node):
            return [node[k] for k in sorted(node, key=int)]
        return node

    def _homepage_view(error_lines=None, draft=None):
        cfg = homepage_edit.apply_override(get_landing_config())
        rows = _homepage_fields(cfg)
        if draft:
            rows = [(k, label, draft.get(k, v), kind) for k, label, v, kind in rows]
        return render_template("homepage_edit.html", active_page="",
                               fields=rows, edited=homepage_edit.is_edited(),
                               problems=error_lines or [],
                               **build_dashboard_context())

    @app.route("/homepage")
    @app.route("/homepage/")
    def homepage_edit_page():
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        return _homepage_view()

    @app.route("/homepage", methods=["POST"])
    def homepage_edit_save():
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        cfg = homepage_edit.apply_override(get_landing_config())
        draft = {}
        for key, _label, current, _kind in _homepage_fields(cfg):
            draft[key] = (request.form.get(key) or "").strip()[:600]

        # Validate before anything is saved. A page that half-published is
        # worse than one that refused.
        resolves = homepage_edit.route_resolver(app)
        buckets = {"_links": [], "_text": []}
        for key, label, _current, kind in _homepage_fields(cfg):
            buckets["_links" if kind == "link" else "_text"].append(
                (label, draft[key]))
        problems = homepage_edit.check(buckets, resolves)
        blank = [label for key, label, _c, _k in _homepage_fields(cfg)
                 if not draft[key]]
        if blank:
            problems.append(
                "These would render empty: %s. Clear the whole page back to "
                "the shipped copy instead, if that is what you want."
                % ", ".join(blank[:4]))
        if problems:
            return _homepage_view(problems, draft)

        homepage_edit.write_override(_homepage_nest(draft))
        return redirect("/homepage?saved=1")

    @app.route("/homepage/reset", methods=["POST"])
    def homepage_edit_reset():
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        homepage_edit.clear_override()
        return redirect("/homepage")

    # --- Resellers: Street Banker's own back office ------------------------

    def _owner_or_404():
        """Owner accounts only. A 404 rather than a 403: nobody who is not
        an owner needs to learn this address exists."""
        user = current_user()
        if user is None:
            return None, login_required_redirect()
        if session.get("team_as") or not _is_owner_email(user.get("email")):
            abort(404)
        return user, None

    def _partners_view(error=None):
        rows = []
        for p in partner_store.list_partners():
            rows.append(dict(
                p,
                seats_used=partner_store.seats_used(p["id"]),
                seat_limit=partner_store.seat_limit(p["id"]),
                members=partner_store.list_members(p["id"]),
                roster=partner_store.roster_detail(p["id"]),
            ))
        return render_template("partners_admin.html", active_page="",
                               partners=rows, roles=partner_store.ROLES,
                               error=error, **build_dashboard_context())

    @app.route("/resellers")
    def partners_admin():
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        return _partners_view()

    @app.route("/resellers", methods=["POST"])
    def partners_create():
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        name = (request.form.get("name") or "").strip()
        if not name:
            return _partners_view("A reseller needs a name.")
        slug = (request.form.get("slug") or "").strip()
        domain = (request.form.get("domain") or "").strip()
        pid = partner_store.create_partner(name, slug=slug or None,
                                           domain=domain or None)
        if pid is None:
            # The store returns None for a taken slug or domain. Say which
            # rather than "could not create", which sends nobody anywhere.
            return _partners_view(
                "That slug or domain already belongs to another reseller. "
                "Both have to be unique, because both decide which tenant "
                "an address resolves to.")
        return redirect("/resellers")

    @app.route("/resellers/<pid>/seats", methods=["POST"])
    def partners_seats(pid):
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        if partner_store.get_partner(pid) is None:
            abort(404)
        partner_store.set_seat_limit(pid, request.form.get("seat_limit") or 0)
        return redirect("/resellers")

    @app.route("/resellers/<pid>/members", methods=["POST"])
    def partners_add_member(pid):
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        if partner_store.get_partner(pid) is None:
            abort(404)
        email = (request.form.get("email") or "").strip().lower()
        role = (request.form.get("role") or "viewer").strip()
        if not email:
            return _partners_view("A seat needs an email address.")
        if role not in partner_store.ROLES:
            return _partners_view("That is not a role this software has.")
        # No account is created here. The seat waits for whoever holds that
        # address to sign up, and claim_seats attaches it when they do -
        # so a reseller can be set up before anybody has signed in.
        # Idempotent per (partner, email): adding an address that already
        # holds a seat changes its role rather than refusing, which is what
        # typing a colleague's address into this box usually means.
        partner_store.add_member(pid, email, email.split("@")[0], role)
        return redirect("/resellers")

    @app.route("/resellers/<pid>/artists", methods=["POST"])
    def partners_attach(pid):
        """Put an existing account on a reseller's roster.

        Owner-only on purpose. Attaching by email means learning whether an
        account exists at that address, and giving that to every reseller
        would be an enumeration oracle over the whole platform.
        """
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        if partner_store.get_partner(pid) is None:
            abort(404)
        email = (request.form.get("email") or "").strip().lower()
        if not email:
            return _partners_view("Which account? An email address, please.")
        artist = store.get_user_by_email(email)
        if artist is None:
            return _partners_view(
                "No account here uses %s. They have to sign up before they can "
                "be put on a roster - an account is not invented for them."
                % email)
        current = artist.get("partner_id")
        if current and current != pid:
            other = partner_store.get_partner(current)
            return _partners_view(
                "That account already belongs to %s. Moving it is a transfer, "
                "and a transfer is a deliberate two-step: take it off that "
                "roster first."
                % ((other or {}).get("name") or "another reseller"))
        if not partner_store.attach_user(pid, artist["id"]):
            return _partners_view(
                "That roster is at its seat cap. Raise the cap, or take "
                "somebody off before adding another.")
        return redirect("/resellers")

    @app.route("/resellers/<pid>/artists/<uid>/remove", methods=["POST"])
    def partners_detach(pid, uid):
        """Take an account off a roster. The account and everything in it
        survives: it goes back to being an ordinary Street Banker account."""
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        if partner_store.get_partner(pid) is None:
            abort(404)
        partner_store.detach_user(pid, uid)
        return redirect("/resellers")

    @app.route("/resellers/<pid>/status", methods=["POST"])
    def partners_status(pid):
        _user, bounce = _owner_or_404()
        if bounce:
            return bounce
        if partner_store.get_partner(pid) is None:
            abort(404)
        wanted = (request.form.get("status") or "").strip()
        if wanted not in ("active", "suspended"):
            return _partners_view("A reseller is either active or suspended.")
        # Deliberately not a delete. Suspending closes the console and stops
        # the domain resolving; the artists keep their accounts and their
        # work, and the attachment survives so reactivating restores it.
        partner_store.set_partner_status(pid, wanted)
        return redirect("/resellers")

    @app.route("/vault")
    def asset_vault():
        user = current_user()
        if user is None:
            return login_required_redirect()
        return _render_vault(user)

    def _render_vault(user, doc_error=None):
        items = []
        for v in store.list_vault_files(user["id"]):
            # A saved press kit says where it can go from here (owner,
            # 2026-09-19): the tour advance offers it as an attachment, the
            # press pitch as a link or an attachment, and Download is here.
            kit = v["kind"] == PRESS_KIT_KIND
            items.append({"name": v["label"] or "Vault file",
                          "type": v["kind"].replace("_", " ").title(),
                          "path": v["path"], "date": v["created"][:10],
                          "usage": ("Saved from the press kit as a web page. Attach it to a tour advance or a press pitch, or download it."
                                    if kit else "Vault upload — yours to deploy"),
                          "status": "Archived", "manage": "/epk" if kit else "/vault",
                          "vid": v["id"], "kit": kit})
        for a in store.get_epk_assets(user["id"]):
            items.append({"name": a["kind"].replace("_", " ").title(), "type": "Press asset",
                          "path": a["path"], "date": a["updated"][:10],
                          "usage": "EPK downloads + press outreach",
                          "status": "Public" if a["public"] else "Private",
                          "manage": "/epk"})
        epk = store.get_epk(user["id"]) or {}
        if epk.get("photo"):
            items.append({"name": "Artist Photo", "type": "Press asset",
                          "path": epk["photo"], "date": "", "usage": "EPK hero + profile",
                          "status": "Public", "manage": "/epk"})
        for c in mls.list_campaigns(user["id"]):
            if c.get("cover_url"):
                items.append({"name": c["title"], "type": "Cover art",
                              "path": c["cover_url"], "date": c["updated"][:10],
                              "usage": "Smart link + social cards",
                              "status": links_engine.effective_status(c),
                              "manage": "/links/%s/edit" % c["id"]})
        for r in ros.list_campaigns(user["id"]):
            for a in ros.list_assets(r["id"]):
                if a["asset_type"] == "lyrics":
                    items.append({"name": "%s — Lyrics" % r["title"], "type": "Lyrics",
                                  "path": "", "date": a["created"][:10],
                                  "usage": "Lyric posts + video overlays",
                                  "status": "In rollout",
                                  "manage": "/rollout-studio/%s" % r["id"]})
                else:
                    items.append({"name": "%s — %s" % (r["title"], a["asset_type"].title()),
                                  "type": a["asset_type"].title(),
                                  "path": a["file_path"], "date": a["created"][:10],
                                  "usage": "Rollout content + edit plans",
                                  "status": "In rollout",
                                  "manage": "/rollout-studio/%s" % r["id"]})
        # Contracts & licences - folded in from /documents (tier C,
        # 2026-09-09). Same store now; the paperwork facts and coverage
        # come from documents_engine, which says what it says when empty.
        # /documents was a Pro page and the vault is an Artist one; plans.py
        # is left alone, so the section is offered to the plan that had it.
        contracts_allowed = plans.allowed(user.get("plan") or "artist",
                                          plans.required_tier("/documents"))
        return render_template("vault.html", active_page="vault", items=items,
                               view=("contracts" if request.args.get("view") == "contracts"
                                     else "files"),
                               contracts_allowed=contracts_allowed,
                               contracts_tier=plans.required_tier("/documents"),
                               documents_view=(documents_engine.build(user["id"])
                                               if contracts_allowed else None),
                               documents_per_track_types=documents_engine.PER_TRACK_TYPES,
                               documents_catalog_types=documents_engine.CATALOG_TYPES,
                               doc_types=_DOC_TYPES, doc_error=doc_error,
                               doc_terms=_document_terms_view(user["id"]),
                               terms_saved=request.args.get("terms"),
                               doc_readings=_document_readings_view(user["id"]),
                               read_result=request.args.get("read"),
                               **build_dashboard_context())

    def _document_terms_view(user_id):
        """{document_id: {terms, status}} for the contracts section."""
        import contract_reminders
        out = {}
        for doc_id, terms in store.get_document_terms(user_id).items():
            out[doc_id] = {"terms": terms, "status": contract_reminders.status(terms)}
        return out

    def _document_readings_view(user_id):
        """{document_id: reading + its one-line summary}."""
        import contract_reader
        out = store.get_document_readings(user_id)
        for reading in out.values():
            reading["summary"] = contract_reader.summary(reading["findings"], reading["status"])
        return out

    @app.route("/vault/documents/<doc_id>/read", methods=["POST"])
    def document_read(doc_id):
        """Pull the renewal terms out of the file's own text, for a person
        to check. Nothing reaches the row until they press Save dates."""
        import contract_reader
        user = current_user()
        if user is None:
            return login_required_redirect()
        doc = next((d for d in store.list_documents(user["id"]) if d["id"] == doc_id), None)
        if doc is None:
            abort(404)
        path = doc.get("path") or ""
        data = None
        if blob_store.is_remote(path):
            data = blob_store.fetch(path)
        elif path.startswith("/uploads/"):
            try:
                with open(blob_store.safe_local_path(path, UPLOADS_DIR), "rb") as fh:
                    data = fh.read(40 * 1024 * 1024)
            except (OSError, ValueError):
                data = None
        if data is None:
            status, findings, chars = "unavailable", {}, 0
        else:
            ext = (doc.get("filename") or "").rsplit(".", 1)[-1].lower()
            text, status = contract_reader.extract_text(data, ext)
            findings = contract_reader.find_terms(text) if status == "ok" else {}
            chars = len(text)
        store.set_document_reading(user["id"], doc_id, status, findings, chars)
        return redirect("/vault?view=contracts&read=%s#doc-%s" % (status, doc_id))

    @app.route("/vault/documents/<doc_id>/terms", methods=["POST"])
    def document_terms(doc_id):
        """The renewal date and notice period a person types on a
        contract's row. Nobody has read the document; the row says so."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        renews_on = (request.form.get("renews_on") or "").strip()[:10]
        if renews_on:
            try:
                datetime.strptime(renews_on, "%Y-%m-%d")
            except ValueError:
                return redirect("/vault?view=contracts&terms=baddate#doc-%s" % doc_id)
        try:
            notice_days = max(0, min(365, int(request.form.get("notice_days") or 0)))
        except ValueError:
            notice_days = 0
        ok = store.set_document_terms(user["id"], doc_id, renews_on, notice_days,
                                      request.form.get("auto_renews") == "1",
                                      (request.form.get("terms_note") or "").strip())
        if not ok:
            abort(404)
        return redirect("/vault?view=contracts&terms=saved#doc-%s" % doc_id)

    @app.route("/reminders/run", methods=["POST"])
    def reminders_run():
        """Fire the contract reminders that are due today.

        Meant for the same scheduler that runs the nightly backup,
        presenting BACKUP_TOKEN; an owner can also trigger it, so it is
        testable without waiting for a schedule.
        """
        import contract_reminders
        token = os.environ.get("BACKUP_TOKEN") or ""
        presented = (request.headers.get("X-Backup-Token")
                     or request.form.get("token") or "")
        by_token = bool(token) and hmac.compare_digest(presented, token)
        user = current_user()
        if not (by_token or (user and _is_owner_email(user.get("email")))):
            abort(404)
        result = contract_reminders.run(emailer=emailer, public_url=public_url)
        store.set_kv("reminders_last_run", json.dumps(result))
        # The same daily run moves Release-Ready's queue: reports paused on
        # the budget when it allows again, polls that came due, and an alert
        # for a paid master not stored after 30 minutes. It never starts a
        # paid RoEx retrieval that was not paid for.
        try:
            rr = release_ready.run_due()
        except Exception as exc:           # noqa: BLE001 - reminders already ran
            rr = {"error": type(exc).__name__}
        return jsonify({"ok": True, "run": result, "release_ready": rr})

    VAULT_KINDS = ("cover_art", "master", "stems", "press_photo", "video", "file")
    VAULT_EXTS = ("png", "jpg", "jpeg", "webp", "gif", "wav", "mp3", "flac",
                  "zip", "pdf", "mp4", "mov")

    @app.route("/vault/upload", methods=["POST"])
    def vault_upload():
        """The real vault door: any release asset in, tagged and listed."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in to use the vault."}), 401
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify({"ok": False, "error": "Choose a file."}), 400
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in VAULT_EXTS:
            return jsonify({"ok": False,
                            "error": "Use an image, audio, video, zip, or PDF file."}), 400
        kind = request.form.get("kind") or "file"
        if kind not in VAULT_KINDS:
            kind = "file"
        label = (request.form.get("label") or f.filename.rsplit(".", 1)[0])[:120]
        fname = "vault_%s_%d.%s" % (user["id"],
                                    int(datetime.now(timezone.utc).timestamp() * 1000),
                                    ext)
        # The object store when it is configured, the disk when it is
        # not. blob_store.save returns the path to record either way:
        # "r2:<key>" or "/uploads/<name>". Nothing below branches on it.
        path = blob_store.save(fname, f.read(),
                               content_type=f.mimetype,
                               uploads_dir=UPLOADS_DIR)
        store.add_vault_file(user["id"], path, label, kind)
        return jsonify({"ok": True, "path": path})

    @app.route("/vault/<file_id>/delete", methods=["POST"])
    def vault_delete(file_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        path = store.delete_vault_file(user["id"], file_id)
        # Handles both shapes: deletes the object, or unlinks the file.
        # A document's file is vault-owned too (doc_ prefix).
        if path and (blob_store.is_remote(path)
                     or path.startswith(("/uploads/vault_", "/uploads/doc_",
                                         "/uploads/presskit_"))):
            blob_store.remove(path, uploads_dir=UPLOADS_DIR)
        return redirect("/vault")

    def _vault_file_bytes(path):
        """A vault file read back for an attachment, or None when it cannot
        be reached - which the caller reports as itself, never as sent."""
        if not path:
            return None
        if blob_store.is_remote(path):
            return blob_store.fetch(path)
        try:
            with open(blob_store.safe_local_path(path, UPLOADS_DIR), "rb") as fh:
                return fh.read()
        except (OSError, ValueError):
            return None

    @app.route("/vault/<file_id>/download")
    def vault_download(file_id):
        """One vault file as a download, by the account that owns it
        (owner, 2026-09-19: from the vault you can "download it"). The
        listing is the allowlist, so a guessed id serves nothing."""
        from flask import send_file
        user = current_user()
        if user is None:
            return login_required_redirect()
        row = next((v for v in store.list_vault_files(user["id"], include_documents=True)
                    if v["id"] == file_id), None)
        if row is None:
            abort(404)
        path = row["path"]
        if blob_store.is_remote(path):
            return redirect(blob_store.url_for(path))
        try:
            local = blob_store.safe_local_path(path, UPLOADS_DIR)
        except ValueError:
            abort(404)
        if not os.path.exists(local):
            abort(404)
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        name = _slugify(row["label"] or "vault-file") + ("." + ext if ext else "")
        return send_file(local, as_attachment=True, download_name=name)

    @app.route("/vault/zip", methods=["POST"])
    def vault_zip():
        # Batch download: only paths that genuinely belong to this user's
        # vault are honored — the vault listing itself is the allowlist.
        user = current_user()
        if user is None:
            return login_required_redirect()
        wanted = set(request.form.getlist("paths"))
        allowed = set()
        for v in store.list_vault_files(user["id"], include_documents=True):
            allowed.add(v["path"])
        for a in store.get_epk_assets(user["id"]):
            allowed.add(a["path"])
        epk = store.get_epk(user["id"]) or {}
        if epk.get("photo"):
            allowed.add(epk["photo"])
        for c in mls.list_campaigns(user["id"]):
            if c.get("cover_url"):
                allowed.add(c["cover_url"])
        for r in ros.list_campaigns(user["id"]):
            for a in ros.list_assets(r["id"]):
                if a.get("file_path"):
                    allowed.add(a["file_path"])
        import io as _io
        import zipfile
        buf = _io.BytesIO()
        added = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in wanted & allowed:
                name = os.path.basename(p.split("?")[0])
                if blob_store.is_remote(p):
                    # Pull the object back through the presigned URL. A
                    # failure skips that one file rather than losing the
                    # whole archive.
                    blob = blob_store.fetch(p)
                    if blob is not None:
                        zf.writestr(name, blob)
                        added += 1
                    continue
                if not p.startswith("/uploads/"):
                    continue
                fpath = os.path.join(UPLOADS_DIR, name)
                if os.path.exists(fpath):
                    zf.write(fpath, name)
                    added += 1
        if not added:
            return redirect("/vault")
        buf.seek(0)
        return Response(buf.read(), mimetype="application/zip", headers={
            "Content-Disposition": "attachment; filename=vault-assets.zip"})

    @app.route("/admin/review")
    def admin_review():
        # Every non-fan account on the deployment, by name and email
        # address. That is a cross-tenant read, so the gate is ownership
        # and not a plan: `label` is a tier anybody can buy, /plan/switch
        # hands it out for free while Stripe is unconfigured, and the
        # shared demo login holds it - all three read every customer's
        # email until 2026-09-10.
        user, bail = _owner_or_404()
        if bail:
            return bail
        with store.get_db() as db:
            rows = db.execute(
                "SELECT id, name, email, plan, created FROM users"
                " WHERE plan != 'fan' ORDER BY created").fetchall()
        queue = []
        for row in rows:
            q = qualification.calculate(row["id"])
            queue.append({"name": row["name"], "email": row["email"],
                          "plan": row["plan"], "total": q["total"],
                          "badges": q["badges"],
                          "missing": [n for n, _, _ in q["needs_work"]][:3],
                          "recommendation": q["recommendation"]})
        queue.sort(key=lambda a: a["total"], reverse=True)
        return render_template("admin_review.html", active_page="review",
                               queue=queue, **build_dashboard_context())

    # --- Rollout Engine: social rollout campaigns wired into Links ------------

    def _ro_owned(cid):
        user = current_user()
        if user is None:
            return None, login_required_redirect()
        campaign = ros.get_campaign(cid, user["id"])
        if campaign is None:
            abort(404)
        return campaign, None

    @app.route("/rollout-studio/<cid>/delete", methods=["POST"])
    def rollout_delete(cid):
        """A rollout, its posts and its assets. The smart-link campaign it
        was linked to is a separate thing and stays."""
        campaign, err = _ro_owned(cid)
        if err:
            return err
        ros.delete_campaign(cid, campaign["user_id"])
        return redirect("/rollout-studio")

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

    def _rollout_learning(user_id):
        """What past rollouts converted, from variants that outlive them.

        clear_posts wipes ro_posts on every regenerate but never touches
        ml_variants, so the platform and phase attribution survives - the
        whole history is already there, no migration needed.
        """
        try:
            return rollout_learning.report(
                mls.list_campaigns(user_id), mls.list_variants,
                mls.variant_stats)
        except Exception:
            # A learned suggestion is never worth breaking a page over.
            return {"platforms": {}, "phases": {}, "measured": False}

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
                               campaigns=cards, rollout_user=user,
                               motion=rollout_engine.MOTION, **ctx)

    @app.route("/rollout-studio/new", methods=["GET", "POST"])
    def rollout_new():
        user = current_user()
        if user is None:
            return login_required_redirect()
        ml_campaigns = mls.list_campaigns(user["id"])
        if request.method == "POST":
            f = request.form
            platforms = [k for k, _, _ in rollout_engine.PLATFORMS if f.get("pf_" + k)]
            if not platforms:
                # Nothing ticked. Rather than a fixed default, start from
                # the platforms this artist's past rollouts actually
                # converted on - and fall back to the fixed list when
                # there is not enough traffic to say.
                platforms = rollout_learning.suggested_platforms(
                    _rollout_learning(user["id"]),
                    [k for k, _, _ in rollout_engine.PLATFORMS],
                    ["instagram_reels", "tiktok", "x"])
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
                               motion=rollout_engine.MOTION,
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
        store.notify(campaign["user_id"], "rollout",
                     "Rollout generated: %s" % campaign["title"],
                     "%d posts drafted across the release arc — review and approve." % len(posts),
                     "/rollout-studio/%s/plan" % cid)
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
                               motion=rollout_engine.MOTION,
                               ml_campaign=ml_campaign, variants=variants,
                               direction=rollout_engine.creative_direction(campaign),
                               next_action=(
                                   rollout_learning.next_action_line(
                                       _rollout_learning(user["id"]))
                                   if posts and all(
                                       p["status"] != "draft" for p in posts)
                                   else None)
                               or rollout_engine.next_action(campaign, posts, assets),
                               counts=ros.post_status_counts(cid),
                               phase_names=rollout_engine.PHASE_NAMES,
                               platform_names=rollout_engine.PLATFORM_NAMES,
                               **build_dashboard_context())

    # --- One plan, three arrangements ---------------------------------------
    #
    # Posts, Storyboard and Calendar were three pages over the same rows in
    # ro_posts. Nothing separated them but which columns each chose to show:
    # the words on one, the picture on another, the dates on a third. So a
    # single post could not be finished anywhere - you wrote the caption on
    # Posts, went to Storyboard to attach the asset, and to Calendar to see
    # where it landed.
    #
    # They are one page now. The post is the unit of work and carries
    # everything it needs; `view` chooses how the same set is arranged.

    RO_VIEWS = ("list", "board", "calendar")

    def _ro_plan_view():
        wanted = (request.args.get("view") or "list").strip().lower()
        return wanted if wanted in RO_VIEWS else "list"

    @app.route("/rollout-studio/<cid>/plan", methods=["GET", "POST"])
    def rollout_plan(cid):
        campaign, err = _ro_owned(cid)
        if err:
            return err
        user = current_user()
        view = _ro_plan_view()

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
                    fields = {}
                    # Only what the form actually carried. The board and the
                    # calendar send a subset, and a missing field must not
                    # blank a caption somebody wrote on the list view.
                    if "caption" in request.form:
                        fields["caption"] = (request.form.get("caption") or "").strip()[:2200]
                    if "hashtags" in request.form:
                        fields["hashtags"] = (request.form.get("hashtags") or "").strip()[:300]
                    if "scheduled_date" in request.form:
                        fields["scheduled_date"] = (request.form.get("scheduled_date") or "").strip()[:10]
                    if fields:
                        ros.update_post(post["id"], fields)
                elif action == "asset":
                    # Attach or detach a Vault file. The file is looked up in
                    # this user's own vault listing - nothing else is
                    # reachable by id.
                    vid = request.form.get("vault_id") or ""
                    if vid == "":
                        ros.update_post(post["id"], {"asset_id": None})
                    else:
                        v = next((v for v in store.list_vault_files(user["id"])
                                  if v["id"] == vid), None)
                        if v:
                            ext = v["path"].rsplit(".", 1)[-1].lower()
                            atype = ("video" if ext in ("mp4", "mov")
                                     else "image" if ext in ("png", "jpg", "jpeg",
                                                             "webp", "gif")
                                     else "file")
                            aid = ros.add_asset(cid, atype, v["path"])
                            ros.update_post(post["id"], {"asset_id": aid})
            return redirect("/rollout-studio/%s/plan?view=%s" % (cid, view))

        posts = _ro_post_attribution(campaign)
        variants = ({v["id"]: v for v in mls.list_variants(campaign["ml_campaign_id"])}
                    if campaign.get("ml_campaign_id") else {})
        ml_campaign = (mls.get_campaign(campaign["ml_campaign_id"])
                       if campaign.get("ml_campaign_id") else None)
        twin_cfg = store.get_twin_settings(user["id"]) if user else None
        avoid = [p.strip() for p in
                 ((twin_cfg or {}).get("do_not_say") or "").split(",")
                 if p.strip()]
        assets = {a["id"]: a for a in ros.list_assets(cid)}
        for p in posts:
            v = variants.get(p["variant_id"])
            link = (request.url_root.rstrip("/") + "/l/" + ml_campaign["slug"]
                    + "?v=" + v["slug"]) if (v and ml_campaign) else ""
            p["casts"] = rollout_engine.platform_casts(
                p["caption"], p["hashtags"], campaign["title"], link, avoid)
            p["asset"] = assets.get(p["asset_id"])

        # Filters, so one arrangement does not have to show everything.
        phase = (request.args.get("phase") or "").strip()
        platform = (request.args.get("platform") or "").strip()
        shown = [p for p in posts
                 if (not phase or p["phase"] == phase)
                 and (not platform or p["platform"] == platform)]

        by_date = {}
        for p in shown:
            by_date.setdefault(p["scheduled_date"], []).append(p)

        return render_template(
            "rollout_plan.html", active_page="rollout", c=campaign,
            posts=shown, total_posts=len(posts), view=view,
            motion=rollout_engine.MOTION,
            by_date=sorted(by_date.items()),
            vault=store.list_vault_files(user["id"]),
            variants=variants, ml_campaign=ml_campaign,
            avoid_count=len(avoid),
            phase=phase, platform=platform,
            phases_present=sorted({p["phase"] for p in posts}),
            platforms_present=sorted({p["platform"] for p in posts}),
            phase_names=rollout_engine.PHASE_NAMES,
            platform_names=rollout_engine.PLATFORM_NAMES,
            **build_dashboard_context())

    # The three pages this replaced. Kept as redirects because they are in
    # people's history and in the subnav of anything not yet redeployed -
    # a dead link is a worse answer than the page they were looking for.
    @app.route("/rollout-studio/<cid>/posts")
    def rollout_posts(cid):
        return redirect("/rollout-studio/%s/plan?view=list" % cid, code=301)

    @app.route("/rollout-studio/<cid>/storyboard")
    def rollout_storyboard(cid):
        return redirect("/rollout-studio/%s/plan?view=board" % cid, code=301)

    @app.route("/rollout-studio/<cid>/calendar")
    def rollout_calendar(cid):
        return redirect("/rollout-studio/%s/plan?view=calendar" % cid, code=301)

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

    @app.route("/api/vault/from-motion", methods=["POST"])
    def vault_from_motion():
        """The receiving end of a Motion "send to Street Banker Vault"
        button that Motion does not have yet (owner ruling 2026-09-19:
        everything is made in Motion and pulled into the Vault).

        A stub behind MOTION_HANDOFF_ENABLED, off by default. Off, the
        route is a 404 like any address that does not exist. On, it still
        does nothing but say so: Motion exposes no signed download URL for
        a finished render and no outbound call, so there is nothing to
        receive. docs/MOTION_HANDOFF.md is the spec for both halves.
        """
        from rollout_config import MOTION_HANDOFF_FLAG
        if (os.environ.get(MOTION_HANDOFF_FLAG) or "").strip().lower() not in ("1", "true", "yes", "on"):
            abort(404)
        return jsonify({"ok": False,
                        "error": "The Motion hand-off is specified, not built. "
                                 "See docs/MOTION_HANDOFF.md."}), 501

    def _shopify_import_allowed(user):
        """Reading the connected store's customers is the OWNER'S alone.

        The connection is server configuration (SHOPIFY_*), so it is one
        store: the owner's. Until 2026-09-17 the button was offered to any
        signed-in account, which meant a partner's artist could file the
        owner's customer list as their own fans. Nobody had pressed it.
        A per-account connection is a different feature; this is the door.
        """
        return bool(user and _is_owner_email(user.get("email")))

    @app.route("/links/fans")
    def ml_fans():
        user = current_user()
        if user is None:
            return login_required_redirect()
        q = (request.args.get("q") or "").strip()
        fans = mls.list_fans(user["id"], q)
        campaigns = {c["id"]: c["title"] for c in mls.list_campaigns(user["id"])}
        # Fan CRM is a Fans page (the Fans front: Dashboard, Fan CRM, Fan
        # Club); "fans" is a key in both layouts, so the Fans row lights
        # and the rooms layout goes back to Fans, not Marketing.
        #
        # 2026-09-18: it is the Fan CRM tab of the Audience screen, under
        # the same header. The list import redirects here with ?imp=...;
        # until now nothing read that back, so an import finished in
        # silence. The counts shown are the ones the import stored.
        imp = request.args.get("imp") or ""
        fan_import_result = _import_result(user["id"], imp)
        return render_template("links_fans.html", active_page="fans",
                               fan_import_result=fan_import_result,
                               au_resend=emailer.configured(),
                               fans=fans, q=q, campaign_titles=campaigns,
                               intent_tones=links_engine.INTENT_TONES,
                               shopify=(shopify_customers.status()
                                        if _shopify_import_allowed(user) else None),
                               last_import=store.latest_fan_import(user["id"], "shopify"),
                               imp_note={"off": "Shopify is not connected on this service."}.get(
                                   request.args.get("imp") or "", ""),
                               hypeddit=_hypeddit_panel(user),
                               **build_dashboard_context())

    def _hypeddit_panel(user):
        """What the Connect Hypeddit panel needs, or None when there is no
        panel: the showcase account files nothing, and a read seat is
        not shown the artist's secret address (the template hides it for
        any seat below edit)."""
        if _session_is_demo():
            return None
        token = hypeddit_ingest.get_or_create_token(user["id"])
        data = hypeddit_ingest.status(user["id"])
        data["url"] = hypeddit_ingest.webhook_url(request.host, token)
        return data

    @app.route("/links/fans/hypeddit/rotate", methods=["POST"])
    def ml_fans_hypeddit_rotate():
        """A new Hypeddit address; the old one stops working at once. For
        when the address was pasted somewhere it should not have been."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if _session_is_demo():
            abort(404)
        hypeddit_ingest.rotate_token(user["id"])
        return redirect("/links/fans#hypeddit")

    @app.route("/links/fans/import/shopify", methods=["POST"])
    def ml_fans_import_shopify():
        """Read the store's customers and file the subscribed ones, on the
        artist's say-so. Every run is kept, counts and the vendor's error
        alike, so the page can say what it did."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if not _shopify_import_allowed(user):
            abort(404)
        if not shopify_customers.configured():
            return redirect("/links/fans?imp=off#import")
        last = store.latest_fan_import(user["id"], "shopify")
        after = (last or {}).get("cursor") or None
        try:
            customers, cursor = shopify_customers.fetch_customers(after=after)
        except shopify_customers.ShopifyError as e:
            # A token minted before the owner approved new scopes is refused
            # with 401 or access denied: drop it and try once with a fresh one.
            if shopify_customers.uses_grant() and shopify_customers._denied(str(e)):
                shopify_customers.forget_grant()
                try:
                    customers, cursor = shopify_customers.fetch_customers(after=after)
                except shopify_customers.ShopifyError as e2:
                    store.add_fan_import(user["id"], "shopify", {}, error=str(e2))
                    return redirect("/links/fans#import")
            else:
                store.add_fan_import(user["id"], "shopify", {}, error=str(e))
                return redirect("/links/fans#import")
        summary = shopify_customers.import_fans(user["id"], customers)
        store.add_fan_import(user["id"], "shopify", summary, cursor=cursor or "")
        return redirect("/links/fans#import")

    # Where a list import can send the artist back to, by the form it came
    # from. Anything else is refused rather than followed.
    _IMPORT_ORIGINS = {"fans": "/fans", "crm": "/links/fans"}

    _IMPORT_ERRORS = {
        "needs-source": "Say where these people gave you permission, and tick the box, before the list is read.",
        "unreadable": "That file could not be read as text. Export it as a CSV and try again.",
        "empty": "There was nothing in the file or the box to read.",
        "no-address": "No column of email addresses was found. The file needs one, however it is spelled; a bare list of addresses works too.",
        "stale": "That preview is no longer here: it was confirmed, cancelled, replaced by a newer one or is older than a day. Nothing more was added from it.",
    }

    def _import_result(user_id, imp):
        """What the import panel says after a round trip: an error, or the
        counts of the import that just ran, read back from its own record."""
        if imp in _IMPORT_ERRORS:
            return {"error": _IMPORT_ERRORS[imp]}
        if imp == "done":
            last_list = store.latest_fan_import(user_id, "list")
            return (last_list or {}).get("summary") or None
        return None

    @app.route("/fans/import/preview", methods=["POST"])
    @app.route("/links/fans/import/list", methods=["POST"])
    def ml_fans_import_list():
        """Read a list the artist already has, from a file or pasted text,
        and show what it would do. Writes no fan.

        Until 2026-09-18 this route filed every row the moment the form was
        sent, while the page promised a preview first. It now parks the
        parsed rows as a draft (db.fan_import_drafts) and sends the artist
        to /fans/import, where nothing is added until they confirm. The old
        URL is kept and goes the same way, so there is one path in.

        Open to any signed-in account, unlike the Shopify import, which
        reads the owner's own store and is owner-only. This one reads what
        the artist hands over, so it is theirs to run.

        Consent is never inferred from the fact that somebody uploaded a
        file. Where the export carries a status column, fan_list_import
        leaves out every row that says unsubscribed, cleaned, bounced or
        never subscribed, whatever is ticked here. Where it does not, the
        artist's own sentence about where the permission came from is what
        gets written onto each record.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        if _session_is_demo():
            # The showcase has no import on it (partials/fans_head.html), and
            # a preview it could confirm would write real rows onto the demo
            # account (review, 2026-09-18).
            return redirect("/fans")
        origin = request.form.get("origin")
        if origin not in _IMPORT_ORIGINS:
            origin = "crm" if request.path.startswith("/links/") else "fans"
        back = _IMPORT_ORIGINS[origin]

        source = (request.form.get("source") or "").strip()[:120]
        if not request.form.get("confirm") or not source:
            return redirect(back + "?imp=needs-source#import")

        text = request.form.get("text") or ""
        upload = request.files.get("file")
        if upload and upload.filename:
            try:
                text = upload.read().decode("utf-8-sig", "replace")
            except Exception:
                return redirect(back + "?imp=unreadable#import")
        if not text.strip():
            return redirect(back + "?imp=empty#import")

        parsed = fan_list_import.parse(text)
        if parsed["columns"]["email"] is None:
            return redirect(back + "?imp=no-address#import")
        on_file = {f.get("email") or "": f for f in mls.list_fans(user["id"])}
        summary = fan_list_import.preview(parsed, on_file.keys())
        rows = fan_list_import.draft_rows(parsed, on_file)
        # How many fans already here would get a missing place filled in:
        # the only change confirm makes to them, counted now so the preview
        # can say it (and say nothing would change when it is 0).
        summary["places_to_fill"] = sum(1 for r in rows if r.get("fills"))
        store.put_fan_import_draft(user["id"], origin, source,
                                   parsed["has_status_column"], summary, rows)
        return redirect("/fans/import")

    @app.route("/fans/import")
    def fans_import_preview():
        """The preview: counts, reasons, a masked sample. Nothing written."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if _session_is_demo():
            return redirect("/fans")
        draft = store.get_fan_import_draft(user["id"])
        if draft is None:
            return redirect("/fans?imp=stale#import")
        ctx = build_dashboard_context()
        ctx.update(draft=draft, s=draft["summary"],
                   sample=fan_list_import.sample(draft["rows"]),
                   places_to_fill=int(draft["summary"].get("places_to_fill") or 0),
                   consent_line=_import_consent_line(draft),
                   au_resend=emailer.configured(),
                   au_tab="crm" if draft["origin"] == "crm" else "audience")
        return render_template("fans_import_preview.html", active_page="fans", **ctx)

    def _import_consent_line(draft):
        """The sentence written on each new record. Dated the day the box
        was ticked, which is the day the draft was made, so the preview's
        quote and the note confirm writes are the same sentence even when
        confirm comes after midnight (review, 2026-09-18)."""
        return fan_list_import.consent_note(
            draft["source"], (draft.get("created") or "")[:10]
            or datetime.now(timezone.utc).date().isoformat(),
            bool(draft.get("has_status_column")))

    @app.route("/fans/import/confirm", methods=["POST"])
    def fans_import_confirm():
        """File exactly what the preview showed, once.

        links_store.confirm_list_import does it all in one transaction: the
        draft's DELETE is the claim, so a second press, a replayed form or
        another account's id finds nothing and writes nothing, and a request
        killed partway leaves the draft and writes nothing. Fans already
        here only get a missing place filled; a place they hold is kept."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if _session_is_demo():
            return redirect("/fans")
        draft_id = request.form.get("draft_id") or ""
        origin = (store.get_fan_import_draft(user["id"], draft_id) or {}).get("origin")
        done = mls.confirm_list_import(user["id"], draft_id, _import_consent_line)
        if done is None:
            return redirect("/fans?imp=stale#import")
        if origin == "crm":
            return redirect("/links/fans?imp=done#import")
        return redirect("/fans?imp=done")

    @app.route("/fans/import/cancel", methods=["POST"])
    def fans_import_cancel():
        """Throw the draft away. Only the owner's own; nothing was written."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if _session_is_demo():
            return redirect("/fans")
        draft_id = request.form.get("draft_id") or ""
        draft = store.get_fan_import_draft(user["id"], draft_id)
        store.drop_fan_import_draft(user["id"], draft_id)
        return redirect(_IMPORT_ORIGINS.get((draft or {}).get("origin"), "/fans"))

    @app.route("/links/fans/shopify/reconnect", methods=["POST"])
    def ml_fans_shopify_reconnect():
        """Owner: forget the cached Shopify tokens and mint afresh - the
        button to press after approving new scopes on the store."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        if not _shopify_import_allowed(user):
            abort(404)
        if shopify_customers.uses_grant():
            shopify_customers.forget_grant()
            shopify_customers.token()
        return redirect("/links/fans?imp=reconnected#import")

    @app.route("/links/fans/<fan_id>/delete", methods=["POST"])
    def ml_fan_delete(fan_id):
        """The fans page said "manage or delete records in the Fan CRM" and
        the Fan CRM had no such control (route walk, 2026-09-12). Scoped
        to the account in the DELETE itself."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        mls.delete_fan(user["id"], fan_id)
        return redirect("/links/fans?removed=1")

    @app.route("/links/fans/export.csv")
    def ml_fans_export():
        user = current_user()
        if user is None:
            return login_required_redirect()
        # A file that leaves this app goes into mail tools. By default it
        # carries only the contactable: somebody who unsubscribed, bounced
        # or complained is not in it. ?include=suppressed is the explicit
        # full record, and every suppressed row says why in its own column.
        import csv as _csv
        import io as _io
        everyone = request.args.get("include") == "suppressed"
        out = _io.StringIO()
        w = _csv.writer(out)
        w.writerow(["Email", "Name", "Visits", "Clicks", "Pre-saves", "Captures",
                    "Intent Score", "Intent Level", "First Seen", "Last Active", "Suppressed"])
        for f in mls.list_fans(user["id"]):
            why = (f.get("suppressed") or "").strip()
            if why and not everyone:
                continue
            w.writerow([f["email"], f["name"], f["total_visits"], f["total_clicks"],
                        f["total_presaves"], f["total_captures"], f["intent_score"],
                        f["intent_level"], f["created"], f["updated"], why])
        name = "street-banker-fans-all.csv" if everyone else "street-banker-fans.csv"
        return Response(out.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=" + name})

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

    # Income by type - Publishing, Mechanicals, Neighboring rights and By
    # market - folded into Royalties (owner, 2026-09-13): the four stream
    # pages are the stream columns and the ledger there, By market is the
    # markets panel, and the MLC registry check lives on Recovery.
    @app.route("/publishing")
    def publishing():
        return redirect("/royalties#streams")

    @app.route("/neighboring-rights")
    def neighboring_rights():
        return redirect("/royalties#streams")

    @app.route("/sync")
    def sync():
        """Deleted (owner decision, 2026-09-05): the page was illustrative
        placements, requests and fees. The sync tooling that is real lives
        under /sync/clearance-packs and /sync/deal-simulator."""
        return redirect("/sync/clearance-packs")

    @app.route("/territories")
    def territories():
        return redirect("/royalties#markets")

    @app.route("/mechanicals")
    def mechanicals():
        return redirect("/royalties#streams")

    @app.route("/insights")
    def insights():
        user = current_user()
        if user is None:
            return login_required_redirect()
        return render_template("insights.html", active_page="scores",
                               items=insights_engine.build_insights(user["id"]),
                               **build_dashboard_context())

    @app.route("/benchmark")
    def benchmark():
        ctx = build_dashboard_context()
        # The account's own statements, so Est. catalog value is the same
        # figure /valuation and the press kit show rather than a second
        # estimate at a second multiple.
        user = current_user()
        rows = store.get_statement_rows(user["id"]) if user else []
        ctx["benchmark"] = get_benchmark_data(rows)
        return render_template("benchmark.html", active_page="benchmark", **ctx)

    def _ago(created):
        try:
            then = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if then.tzinfo is None:
                then = then.replace(tzinfo=timezone.utc)
            mins = int((datetime.now(timezone.utc) - then).total_seconds() // 60)
        except (ValueError, AttributeError):
            return ""
        if mins < 60:
            return "just now" if mins < 2 else "%dm ago" % mins
        if mins < 60 * 48:
            return "%dh ago" % (mins // 60)
        return "%dd ago" % (mins // (60 * 24))

    import collab_market as _cm
    # One role vocabulary for briefs and collaborator profiles.
    COLLAB_ROLES = _cm.ROLES

    @app.route("/marketplace")
    def marketplace():
        user = current_user()
        if user is None:
            return login_required_redirect()
        # The approved Collab Marketplace screen (owner mock, 2026-09-18).
        # Every count below is a query on the collab tables; see
        # collab_market.py for what each section is allowed to show.
        import collab_market
        tab = request.args.get("tab") or "discover"
        if tab not in ("discover", "briefs", "applications", "projects"):
            tab = "discover"
        kind = request.args.get("kind") or None
        role = request.args.get("role") or None
        genre = (request.args.get("genre") or "").strip() or None
        loc = (request.args.get("loc") or "").strip().lower()
        budget = request.args.get("budget") or ""
        if budget not in [b[0] for b in collab_market.BUDGET_BANDS] + ["unstated"]:
            budget = ""
        q = (request.args.get("q") or "").strip()
        saved_only = request.args.get("saved") == "1"
        today_d = datetime.now(timezone.utc).date()
        today = today_d.isoformat()
        uid = user["id"]
        # One rule for "on the board": open, and its closing date (if any)
        # not yet passed. The tiles count with it and the board reads with
        # it, with no row cap, so neither stops at a list length.
        live_sql = ("c.status = 'open' AND (c.closes IS NULL OR c.closes = ''"
                    " OR substr(c.closes, 1, 10) >= ?)")
        with store.get_db() as db:
            counts = {row["request_id"]: row["n"] for row in db.execute(
                "SELECT request_id, COUNT(*) AS n FROM collab_replies "
                "GROUP BY request_id").fetchall()}
            sent = [dict(row) for row in db.execute(
                "SELECT r.*, c.title, c.role, c.kind, c.status, c.closes,"
                " c.user_id AS owner_id, u.name AS poster_name"
                " FROM collab_replies r"
                " JOIN collab_requests c ON c.id = r.request_id"
                " JOIN users u ON u.id = c.user_id"
                " WHERE r.user_id = ? ORDER BY r.created DESC",
                (uid,)).fetchall()]
            board = [dict(row) for row in db.execute(
                "SELECT c.*, u.name AS poster_name FROM collab_requests c"
                " JOIN users u ON u.id = c.user_id WHERE " + live_sql
                + " ORDER BY c.created DESC", (today,)).fetchall()]
            tiles = {
                "open": db.execute(
                    "SELECT COUNT(*) FROM collab_requests c JOIN users u"
                    " ON u.id = c.user_id WHERE " + live_sql,
                    (today,)).fetchone()[0],
                "mine": db.execute(
                    "SELECT COUNT(*) FROM collab_requests c"
                    " WHERE c.user_id = ? AND " + live_sql,
                    (uid, today)).fetchone()[0],
                "sent": db.execute(
                    "SELECT COUNT(*) FROM collab_replies WHERE user_id = ?",
                    (uid,)).fetchone()[0],
                "saved": db.execute(
                    "SELECT COUNT(*) FROM collab_saves s"
                    " JOIN collab_requests c ON c.id = s.request_id"
                    " JOIN users u ON u.id = c.user_id"
                    " WHERE s.user_id = ? AND " + live_sql,
                    (uid, today)).fetchone()[0],
            }
        trust_cache = {}

        def _dress(r):
            r["ago"] = _ago(r["created"])
            r["applicants"] = counts.get(r["id"], 0)
            r["days_left"] = collab_market.days_left(r["closes"], today_d)
            r["closes_label"] = collab_market.short_date(r["closes"], today_d)
            r["initials"] = collab_market.initials(r.get("poster_name"))
            r["photo"] = collab_market.ROLE_PHOTOS.get(
                r["role"], collab_market.DEFAULT_PHOTO)
            r["chip"] = collab_market.KIND_CHIPS.get(r["kind"], "")
            r["state"] = collab_market.brief_state(r, today_d)
            r["state_label"] = collab_market.STATE_LABELS[r["state"]]
            r["place"] = collab_market.brief_place(r)
            r["budget_label"] = collab_market.brief_budget(r)
            return r

        def _with_trust(r):
            # Scored only for rows on screen: a poster's score is a real
            # calculation, so it is not run for rows nobody sees.
            if r["user_id"] not in trust_cache:
                t = trust_score.calculate(r["user_id"])
                trust_cache[r["user_id"]] = (
                    t["total"], any(pts for _n, pts, _x in t["factors"]))
            total, measured = trust_cache[r["user_id"]]
            r["trust"] = total
            r["trust_label"] = collab_market.trust_label(total, measured)
            return r

        board = [_dress(r) for r in board]
        saves = store.list_collab_saves(uid)
        reqs = [r for r in board
                if (not kind or r["kind"] == kind)
                and (not role or r["role"] == role)
                and (not genre or r["genre"] == genre)
                and (not saved_only or r["id"] in saves)
                and collab_market.location_filter(r, loc)
                and collab_market.budget_filter(r, budget)
                and (not q or q.lower() in " ".join(
                    (r["title"], r["role"], r["genre"], r["details"],
                     r["poster_name"] or "")).lower())]
        shown = [_with_trust(r) for r in reqs[:collab_market.TABLE_ROWS]]
        own = store.list_own_collab_requests(uid)
        replies_by_req = {r["id"]: store.list_collab_replies(r["id"]) for r in own}
        for r in own:
            r["applicants"] = len(replies_by_req[r["id"]])
            r["days_left"] = collab_market.days_left(r["closes"], today_d)
            r["state"] = collab_market.brief_state(r, today_d)
            r["state_label"] = collab_market.STATE_LABELS[r["state"]]
        for a in sent:
            a["state"] = collab_market.brief_state(a, today_d)
            a["state_label"] = collab_market.STATE_LABELS[a["state"]]
            a["sent_label"] = collab_market.short_date(a["created"], today_d)
        applied_ids = {a["request_id"] for a in sent}
        recs, rec_basis = collab_market.recommendations(board, uid, own, sent)
        recs = [_with_trust(r) for r in recs]
        # Active projects: your briefs still open (and not past their
        # closing date) that have drawn at least one application - the
        # only work in progress this board records.
        projects = [collab_market.pipeline(r, replies_by_req[r["id"]], today_d)
                    for r in own if r["state"] == "open" and r["applicants"]]
        latest = (collab_market.pipeline(own[0], replies_by_req[own[0]["id"]],
                                         today_d) if own else None)

        # COLLABORATOR PROFILES (PROFILES-SPEC.md). Only listed members
        # come back from the store; the viewer is never matched with
        # themselves. Matching is against the viewer's own open briefs,
        # else the viewer's own profile, else nothing (no % shown).
        open_own = [r for r in own if r["state"] == "open"]
        me_profile = store.get_collab_profile(uid)
        # The shared demo login is handed to prospects who are not members:
        # it never sees a member's profile (it keeps its labelled showcase).
        demo = _session_is_demo()
        listed = ([] if demo else
                  store.list_listed_collab_profiles(exclude_user_id=uid))
        scored = [(p, collab_market.best_match(p, open_own, me_profile, today_d))
                  for p in listed]
        matched = sorted([s for s in scored if s[1]], key=lambda s: -s[1]["pct"])
        # Best matches first; the slots left are filled with listed members
        # who share no role or genre (newest first, no % badge), so a listed
        # member is never dropped from a short row.
        row = (matched + [s for s in scored if not s[1]])[:3]
        summaries = store.collab_rating_summary([p["user_id"] for p, _m in row])
        rec_people = [collab_market.person_card(p, today_d, m,
                                                summaries.get(p["user_id"]))
                      for p, m in row]
        people_unmatched = any(m is None for _p, m in row)
        # Tiles that need a source. New Matches: listed profiles at or over
        # the threshold against an open brief of yours, new or changed
        # since you last opened Discover. Shown only while you have an
        # open brief to match against.
        new_matches = None
        if open_own:
            seen = store.get_collab_seen(uid)
            new_matches = sum(
                1 for p, m in scored
                if m and m["basis"] == "brief"
                and m["pct"] >= collab_market.MATCH_THRESHOLD
                and (not seen or (p.get("updated") or "") > seen))
            if tab == "discover" and not session.get("team_as"):
                store.set_collab_seen(uid)
        # Active Projects, one definition for the tile and the tab: your
        # open briefs with applications (the pipeline), your closed briefs
        # with a chosen collaborator still to rate, and OPEN briefs where you
        # were the one chosen. A finished brief you were chosen for is kept
        # on the tab under "Finished", and is not counted.
        rated = store.rated_pairs_by(uid)
        to_rate = []
        for r in own:
            if r["status"] != "closed":
                continue
            for a in replies_by_req[r["id"]]:
                if a.get("chosen") and a["user_id"] != uid \
                        and (r["id"], a["user_id"]) not in rated:
                    to_rate.append({"brief": r, "reply": a})
        chosen_all = store.list_collab_chosen_for(uid)
        for c in chosen_all:
            c["state"] = collab_market.brief_state(c, today_d)
            c["state_label"] = collab_market.STATE_LABELS[c["state"]]
        chosen_for = [c for c in chosen_all if c["state"] == "open"]
        chosen_done = [c for c in chosen_all if c["state"] != "open"]
        active_count = len(projects) + len(to_rate) + len(chosen_for)
        focus = None
        brief_id = request.args.get("brief")
        if brief_id:
            focus = next((r for r in board if r["id"] == brief_id), None)
            if focus is None:
                mine = next((r for r in own if r["id"] == brief_id), None)
                focus = _dress(dict(mine, poster_name=user["name"])) if mine else None
            if focus is not None:
                _with_trust(focus)
        # Whether this member already reported the post on screen: the
        # button becomes the confirmation instead of asking again.
        focus_reported = bool(focus is not None and focus["user_id"] != uid
                              and store.get_kv(_collab_report_key(focus["id"], uid)) is not None)
        # The view a save or apply form returns to (the applied and
        # reported flags are dropped so the flash does not follow the
        # user around).
        kept = [(k, v) for k, v in request.args.items(multi=True)
                if k not in ("applied", "reported")]
        here = request.path + ("?" + urllib.parse.urlencode(kept) if kept else "")
        trust = trust_score.calculate(uid)
        trust_rows = [
            {"name": name, "pts": pts, "note": note,
             "unmeasured": trust["unmeasured"].get(name),
             "icon": Markup(collab_market.TRUST_ICONS.get(
                 name, collab_market.DEFAULT_TRUST_ICON))}
            for name, pts, note in trust["factors"]]
        trust_scored = any(r["pts"] for r in trust_rows)
        return render_template(
            "marketplace.html", active_page="marketplace",
            tab=tab, tabs=collab_market.TABS, q=q, saved_only=saved_only,
            requests=shown, more=len(reqs) - len(shown),
            kind=kind or "", role=role or "", genre=genre or "",
            roles=COLLAB_ROLES, user=user, saves=saves, own=own,
            replies_by_req=replies_by_req, sent=sent, tiles=tiles,
            applied_ids=applied_ids, here=here,
            recs=recs, rec_basis=rec_basis, projects=projects, latest=latest,
            focus=focus, focus_reported=focus_reported,
            trust=trust, trust_rows=trust_rows,
            trust_scored=trust_scored, kind_labels=collab_market.KIND_LABELS,
            genres=sorted({r["genre"] for r in board if r["genre"]}),
            loc=loc, budget=budget,
            loc_options=collab_market.location_options(board),
            budget_bands=collab_market.BUDGET_BANDS,
            rec_people=rec_people, people_matched=bool(matched),
            people_unmatched=people_unmatched, chosen_done=chosen_done,
            post_error=request.args.get("post_error") or "",
            money_pattern=collab_market.MONEY_PATTERN,
            me_profile=me_profile, new_matches=new_matches,
            match_threshold=collab_market.MATCH_THRESHOLD,
            to_rate=to_rate, chosen_for=chosen_for, active_count=active_count,
            rated=rated,
            showcase=(collab_market.SHOWCASE
                      if _session_is_demo() and not recs and not rec_people
                      else []),
            **build_dashboard_context())

    @app.route("/marketplace/post", methods=["POST"])
    def marketplace_post():
        user = current_user()
        if user is None:
            return login_required_redirect()
        kind = request.form.get("kind") or ""
        role = (request.form.get("role") or "").strip()
        title = (request.form.get("title") or "").strip()
        if kind in ("bid", "split", "fun") and role and title:
            lo, hi, money_errors = _cm.read_money_pair(
                request.form.get("budget_min"), request.form.get("budget_max"),
                "Budget")
            if money_errors:
                # Nothing is saved: a number the member never typed must not
                # reach the board, the filters or the match.
                return redirect("/marketplace?tab=briefs&post_error=%s#post"
                                % urllib.parse.quote(money_errors[0]))
            store.add_collab_request(
                user["id"], role,
                (request.form.get("genre") or "").strip(), kind, title,
                (request.form.get("details") or "").strip(),
                (request.form.get("terms") or "").strip(),
                (request.form.get("ref_url") or "").strip(),
                (request.form.get("closes") or "").strip(),
                city=(request.form.get("city") or "").strip(),
                country=(request.form.get("country") or "").strip(),
                remote_ok=request.form.get("remote_ok") == "1",
                budget_min=lo, budget_max=hi)
        return redirect("/marketplace")

    @app.route("/marketplace/<req_id>/apply", methods=["POST"])
    def marketplace_apply(req_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        import collab_market
        back = collab_market.safe_back(request.form.get("back"))
        req = store.get_collab_request(req_id)
        message = (request.form.get("message") or "").strip()
        contact = (request.form.get("contact") or "").strip()
        if (req is None or req["status"] != "open"
                or req["user_id"] == user["id"] or not message
                or "@" not in contact):
            return redirect(back)
        store.add_collab_reply(req_id, user["id"], message, contact,
                               (request.form.get("proposal") or "").strip(),
                               (request.form.get("ref_url") or "").strip())
        store.notify(req["user_id"], "network",
                     "New application on your collab request",
                     "%s applied to “%s”. Reach them at %s."
                     % (user["name"] or "A member", req["title"], contact),
                     "/marketplace")
        if emailer.configured():
            import html as _html
            owner = store.get_user(req["user_id"])
            if owner:
                emailer.send(
                    owner["email"], "New application on your collab request",
                    "<p><b>%s</b> applied to “%s”:</p><p>%s</p>"
                    "<p>Reach them at <a href=\"mailto:%s\">%s</a>.</p>"
                    % (_html.escape(user["name"] or "A member"),
                       _html.escape(req["title"]),
                       _html.escape(message[:500]), _html.escape(contact),
                       _html.escape(contact)), reply_to=contact)
        return redirect(collab_market.with_flag(back, "applied=1"))

    @app.route("/marketplace/<req_id>/save", methods=["POST"])
    def marketplace_save(req_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        if store.get_collab_request(req_id):
            store.toggle_collab_save(user["id"], req_id)
        import collab_market
        return redirect(collab_market.safe_back(request.form.get("back")))

    @app.route("/marketplace/<req_id>/close", methods=["POST"])
    def marketplace_close(req_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.close_collab_request(user["id"], req_id)
        return redirect("/marketplace")

    @app.route("/marketplace/<req_id>/delete", methods=["POST"])
    def marketplace_delete(req_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_collab_request(user["id"], req_id)
        return redirect("/marketplace")

    def _collab_report_key(req_id, user_id):
        return "collab_report:%s:%s" % (req_id, user_id)

    @app.route("/marketplace/<req_id>/report", methods=["POST"])
    def marketplace_report(req_id):
        """Report this post, and it reaches the owner (owner-approved,
        2026-09-19). Signed-in members only, never on their own post, and
        one report per member per post: a repeat press is ignored rather
        than sending the owner the same report twice."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        back = _cm.safe_back(request.form.get("back"))
        req = store.get_collab_request(req_id)
        if req is None or req["user_id"] == user["id"]:
            return redirect(back)
        key = _collab_report_key(req_id, user["id"])
        if store.get_kv(key) is None:
            store.set_kv(key, json.dumps({"at": datetime.now(timezone.utc).isoformat()}))
            body = "%s (%s) reported “%s” by %s." % (
                user.get("name") or "A member", user.get("email") or "no email",
                req["title"], req.get("poster_name") or "a member")
            # Straight to the owners, under its own kind: _notify_owners files
            # everything as "billing", and an owner who muted billing mail
            # must still hear about a reported post.
            for u in store.list_users():
                if _is_owner_email(u.get("email")):
                    store.notify(u["id"], "report", "Collab post reported", body,
                                 "/marketplace?brief=%s#brief" % req_id)
        return redirect(_cm.with_flag(back, "reported=1"))

    # --- Collaborator profiles (PROFILES-SPEC.md, owner-approved 2026-09-18) ---

    def _own_card(user, profile, today_d):
        """The viewer's own card, as others would see it once listed."""
        epk = store.get_epk(user["id"]) or {}
        base = dict(profile or {}, user_id=user["id"], name=user["name"],
                    photo=epk.get("photo") or "")
        summary = store.collab_rating_summary([user["id"]]).get(user["id"])
        return _cm.person_card(base, today_d, None, summary)

    @app.route("/marketplace/profile", methods=["GET", "POST"])
    def marketplace_profile():
        """The member's own collaborator profile and the opt-in switch.
        Nobody is listed until they tick "List me in the marketplace"."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        today_d = datetime.now(timezone.utc).date()
        errors = []
        profile = store.get_collab_profile(user["id"])
        demo = _session_is_demo()
        if request.method == "POST":
            fields, errors = _cm.clean_profile(request.form)
            if demo and fields["listed"]:
                # The shared demo login is not a member: it is never listed.
                fields["listed"] = 0
                errors.append("The demo account cannot be listed in the "
                              "marketplace: it is not a member.")
            if not errors:
                store.save_collab_profile(user["id"], fields)
                return redirect("/marketplace/profile?saved=1")
            profile = dict(profile or {}, **fields)
        blank = {"listed": 0, "roles": [], "genres": [], "city": "", "country": "",
                 "remote_ok": 0, "rate_min": None, "rate_max": None,
                 "rate_unit": "", "currency": "USD", "availability": "",
                 "available_from": "", "credits": "", "links": [], "bio": ""}
        form = dict(blank, **(profile or {}))
        card = _own_card(user, form, today_d)
        return render_template(
            "collab_profile.html", active_page="marketplace", user=user,
            form=form, card=card, errors=errors, roles=COLLAB_ROLES,
            is_demo=demo, money_pattern=_cm.MONEY_PATTERN,
            rate_units=_cm.RATE_UNITS, currencies=_cm.CURRENCIES,
            max_links=_cm.MAX_LINKS, saved=request.args.get("saved") == "1",
            photo_error=request.args.get("photo_error") or "",
            photo_saved=request.args.get("photo") == "1",
            **build_dashboard_context())

    @app.route("/marketplace/profile/photo", methods=["POST"])
    def marketplace_profile_photo():
        """The member's own photo, stored as their EPK photo (one photo per
        member). Never a placeholder: no upload means initials."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        _path, error = _store_epk_photo(user, request.files.get("photo"))
        if error:
            return redirect("/marketplace/profile?photo_error=" +
                            urllib.parse.quote(error) + "#photo")
        return redirect("/marketplace/profile?photo=1#photo")

    def _people_cards(user, today_d, only=None):
        """Listed collaborators with the viewer's match, best first."""
        uid = user["id"]
        own = store.list_own_collab_requests(uid)
        open_own = [r for r in own if _cm.brief_state(r, today_d) == "open"]
        me = store.get_collab_profile(uid)
        # The demo login never sees a member's profile (see marketplace()).
        listed = ([] if _session_is_demo() else
                  store.list_listed_collab_profiles(exclude_user_id=uid))
        if only:
            listed = [p for p in listed if only in (p.get("roles") or [])]
        scored = [(p, _cm.best_match(p, open_own, me, today_d)) for p in listed]
        scored.sort(key=lambda s: -(s[1]["pct"] if s[1] else -1))
        summaries = store.collab_rating_summary([p["user_id"] for p, _m in scored])
        return ([_cm.person_card(p, today_d, m, summaries.get(p["user_id"]))
                 for p, m in scored], bool(open_own), me)

    @app.route("/marketplace/people")
    def marketplace_people():
        """Every listed collaborator (opt-in only), best match first."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        today_d = datetime.now(timezone.utc).date()
        role = request.args.get("role") or ""
        if role not in COLLAB_ROLES:
            role = ""
        cards, has_open, me = _people_cards(user, today_d, only=role or None)
        return render_template(
            "collab_people.html", active_page="marketplace", user=user,
            people=cards, role=role, roles=COLLAB_ROLES, has_open=has_open,
            me_profile=me, is_demo=_session_is_demo(),
            **build_dashboard_context())

    @app.route("/marketplace/people/<member_id>")
    def marketplace_person(member_id):
        """One listed member's profile. Unlisted means not here at all."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        profile = store.get_listed_collab_profile(member_id)
        if profile is None or (_session_is_demo() and member_id != user["id"]):
            if member_id == user["id"]:
                return redirect("/marketplace/profile")
            abort(404)
        today_d = datetime.now(timezone.utc).date()
        is_me = member_id == user["id"]
        match = None
        if not is_me:
            own = store.list_own_collab_requests(user["id"])
            open_own = [r for r in own if _cm.brief_state(r, today_d) == "open"]
            match = _cm.best_match(profile, open_own,
                                   store.get_collab_profile(user["id"]), today_d)
        summary = store.collab_rating_summary([member_id]).get(member_id)
        card = _cm.person_card(profile, today_d, match, summary)
        ratings = store.list_collab_ratings_for(member_id)
        for g in ratings:
            g["when"] = _cm.short_date(g["created"], today_d)
        briefs = [r for r in store.list_own_collab_requests(member_id)
                  if _cm.brief_state(r, today_d) == "open"]
        t = trust_score.calculate(member_id)
        trust_rows = [
            {"name": name, "pts": pts, "unmeasured": t["unmeasured"].get(name),
             "icon": Markup(_cm.TRUST_ICONS.get(name, _cm.DEFAULT_TRUST_ICON))}
            for name, pts, _note in t["factors"]]
        return render_template(
            "collab_person.html", active_page="marketplace", user=user,
            card=card, ratings=ratings, briefs=briefs, is_me=is_me,
            kind_labels=_cm.KIND_LABELS, trust=t, trust_rows=trust_rows,
            trust_scored=any(r["pts"] for r in trust_rows),
            **build_dashboard_context())

    @app.route("/marketplace/<req_id>/choose/<reply_id>", methods=["POST"])
    def marketplace_choose(req_id, reply_id):
        """The brief's poster marks an applicant as chosen (or undoes it).
        A chosen applicant on a closed brief is who may be rated."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        req = store.get_collab_request(req_id)
        if req is not None and req["user_id"] == user["id"]:
            store.set_collab_reply_chosen(user["id"], reply_id,
                                          request.form.get("chosen") == "1")
        return redirect("/marketplace?tab=briefs#brief-%s" % req_id)

    @app.route("/marketplace/<req_id>/rate/<ratee_id>", methods=["POST"])
    def marketplace_rate(req_id, ratee_id):
        """1 to 5 stars and an optional note, once per brief and person,
        only on a closed brief of yours where you chose them."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.add_collab_rating(user["id"], req_id, ratee_id,
                                request.form.get("stars"),
                                (request.form.get("note") or "").strip())
        back = _cm.safe_back(request.form.get("back"),
                             "/marketplace?tab=projects")
        return redirect(back)

    def _discover_state():
        """This browser's likes and follows.

        They used to be two module-level sets in discover_config, with
        no user key at all: one process serves every account, so
        account A liking a track drew a filled heart on account B's
        page. The footer has always read "Likes & follows save for
        your session" - the session is where they live now, so the
        sentence is true.

        The session and not a table, deliberately. The twelve tracks
        are a fixture with illustrative play counts, and persisting a
        like against an invented track would add a second false claim
        on top of the one being fixed. If the feed ever becomes real
        music, this is the seam to move.
        """
        return (set(session.get("discover_likes") or ()),
                set(session.get("discover_follows") or ()))

    def _keep_discover_state(likes, follows):
        # Sorted lists, because the session is JSON on the way to a
        # cookie and a set will not serialise.
        session["discover_likes"] = sorted(likes)
        session["discover_follows"] = sorted(follows)

    @app.route("/discover")
    def discover():
        likes, follows = _discover_state()
        ctx = build_dashboard_context()
        ctx["discover"] = get_discover_data(request.args, likes, follows)
        # Real music search: iTunes catalog with artwork + 30s previews.
        q = (request.args.get("q") or "").strip()
        ctx["real_query"] = q
        ctx["real_results"] = itunes_search(q) if q else []
        return render_template("discover.html", active_page="discover", **ctx)

    @app.route("/discover/like/<track_id>", methods=["POST"])
    def discover_like_route(track_id):
        likes, follows = _discover_state()
        res = like_track(track_id, likes)
        if res is None:
            return jsonify({"ok": False}), 404
        _keep_discover_state(likes, follows)
        return jsonify({"ok": True, **res})

    @app.route("/discover/follow/<artist_id>", methods=["POST"])
    def discover_follow_route(artist_id):
        likes, follows = _discover_state()
        res = follow_artist(artist_id, follows)
        _keep_discover_state(likes, follows)
        return jsonify({"ok": True, **res})

    def _network_state():
        """This visitor's side of the sample directory.

        The five collections behind the My Network tab - connections,
        pitches, playlist submissions, booking enquiries and claimed
        moments - were module-level in network_config with no user key.
        One process, every account: A's pending connection rendered on
        B's tab, and the serial number on a moment A claimed was shown to
        everybody. templates/network.html calls this tab "private to
        you".

        The session, because the people being connected to are invented
        (docs/PARKED_PAGES.md). The real outreach tracker on the same
        page is a different thing entirely - it is in the database, keyed
        by user_id, and is not touched here.
        """
        st = session.get("network")
        if not isinstance(st, dict) or set(st) != set(network_blank_state()):
            st = network_blank_state()
        return st

    def _keep_network_state(st):
        session["network"] = st

    @app.route("/network")
    def network():
        user = current_user()
        ctx = build_dashboard_context()
        ctx["network"] = get_network_data(request.args, _network_state())
        # The outreach tracker is the Tour Board's (Stage room). This page
        # is in no room, so a team seat without Stage is not shown it here
        # either (review, 2026-09-19).
        seat = current_team_seat()
        shut = bool(seat and not team_areas.allows(seat["areas"], "/tour-board/outreach"))
        ctx["outreach"] = store.list_outreach(user["id"]) if user and not shut else []
        ctx["outreach_shut"] = shut
        ctx["outreach_stages"] = store.OUTREACH_STAGES
        return render_template("network.html", active_page="network", **ctx)

    def _outreach_back():
        """The outreach forms live on the Team-Up Board and on the parked
        Network page; each says where to return. Anything else goes home."""
        back = request.form.get("back") or ""
        return back if back in ("/tour-board/outreach", "/network?tab=my") else "/tour-board/outreach"

    @app.route("/network/outreach/add", methods=["POST"])
    def outreach_add():
        user = current_user()
        if user is None:
            return login_required_redirect()
        contact = (request.form.get("contact") or "").strip()
        if contact:
            store.add_outreach(user["id"], contact,
                               (request.form.get("role") or "").strip(),
                               request.form.get("stage") or "saved",
                               (request.form.get("notes") or "").strip())
        return redirect(_outreach_back())

    @app.route("/network/outreach/<item_id>/stage", methods=["POST"])
    def outreach_stage(item_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.set_outreach_stage(user["id"], item_id,
                                 request.form.get("stage") or "")
        return redirect(_outreach_back())

    @app.route("/network/outreach/<item_id>/delete", methods=["POST"])
    def outreach_delete(item_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_outreach(user["id"], item_id)
        return redirect(_outreach_back())

    @app.route("/network/playlist/<playlist_id>")
    def network_playlist(playlist_id):
        pl = get_playlist(playlist_id, _network_state())
        if pl is None:
            return redirect(url_for("network"))
        ctx = build_dashboard_context()
        ctx["playlist"] = pl
        ctx["curator"] = get_profile(pl["curator_id"], _network_state())
        return render_template("network_playlist.html", active_page="network", **ctx)

    @app.route("/network/playlist/<playlist_id>/submit", methods=["POST"])
    def network_submit_route(playlist_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        data = request.get_json(silent=True) or {}
        st = _network_state()
        entry = submit_to_playlist(playlist_id, data.get("song"),
                                   data.get("message"), st)
        if entry is None:
            return jsonify({"ok": False, "error": "This playlist isn't accepting submissions, or no track was selected."}), 400
        # A record of what this account sent, filed to this account.
        _keep_network_state(st)
        store.add_inbox("playlist_submission", entry, user_id=user["id"])
        return jsonify({"ok": True})

    @app.route("/network/<profile_id>")
    def network_profile(profile_id):
        profile = get_profile(profile_id, _network_state())
        if profile is None:
            return redirect(url_for("network"))
        ctx = build_dashboard_context()
        ctx["profile"] = profile
        return render_template("network_profile.html", active_page="network", **ctx)

    @app.route("/network/<profile_id>/connect", methods=["POST"])
    def network_connect_route(profile_id):
        st = _network_state()
        status = network_connect_action(profile_id, st)
        if status is None:
            return jsonify({"ok": False}), 404
        _keep_network_state(st)
        return jsonify({"ok": True, "status": status})

    @app.route("/network/<profile_id>/pitch", methods=["POST"])
    def network_pitch_route(profile_id):
        data = request.get_json(silent=True) or {}
        st = _network_state()
        entry = network_pitch_action(profile_id, data.get("message"),
                                     data.get("song"), st)
        if entry is None:
            return jsonify({"ok": False}), 404
        _keep_network_state(st)
        return jsonify({"ok": True})

    @app.route("/network/<profile_id>/enquire", methods=["POST"])
    def network_enquire_route(profile_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        data = request.get_json(silent=True) or {}
        st = _network_state()
        entry = enquire_show(profile_id, data.get("city"), data.get("date"),
                             data.get("message"), st)
        if entry is None:
            return jsonify({"ok": False, "error": "This profile isn't taking booking enquiries."}), 400
        _keep_network_state(st)
        store.add_inbox("booking_enquiry", entry, user_id=user["id"])
        return jsonify({"ok": True})

    @app.route("/network/moment/<moment_id>")
    def network_moment(moment_id):
        moment = get_moment(moment_id, _network_state())
        if moment is None:
            return redirect(url_for("network"))
        ctx = build_dashboard_context()
        ctx["moment"] = moment
        return render_template("network_moment.html", active_page="network", **ctx)

    @app.route("/network/moment/<moment_id>/claim", methods=["POST"])
    def network_claim_route(moment_id):
        st = _network_state()
        serial = claim_moment(moment_id, st)
        if serial is None:
            return jsonify({"ok": False}), 404
        _keep_network_state(st)
        return jsonify({"ok": True, "serial": serial})

    def _fan_label_votes():
        """Which demos this browser has voted for.

        community_config held the three demos in a list and incremented
        their counts in place, so one visitor's vote raised the number
        every other account saw and the tally drifted from its seed for
        the life of the process. The counts are placeholders - the page
        says so twice - which is the reason they must not accumulate: an
        invented number that moves reads as a measured one.
        """
        return set(session.get("fan_label_votes") or ())

    @app.route("/fan-label")
    def fan_label():
        ctx = build_dashboard_context()
        ctx["fan_label"] = get_fan_label_data(_fan_label_votes())
        return render_template("fan_label.html", active_page="fan-label", **ctx)

    @app.route("/fan-label/vote/<demo_id>", methods=["POST"])
    def fan_label_vote(demo_id):
        voted = _fan_label_votes()
        votes = vote_demo(demo_id, voted)
        if votes is None:
            return jsonify({"ok": False}), 404
        session["fan_label_votes"] = sorted(voted)
        return jsonify({"ok": True, "votes": votes})

    @app.route("/fans")
    def fans():
        """Real fan records for a real account; the showcase only for the demo.

        This page used to hand community_config's invented figures - 1,240
        superfans, a leaderboard of made-up handles and spend - to every
        account, under a line reading "the app doesn't track individual fans".
        Both halves were wrong: the numbers were nobody's, and the Fan CRM at
        /links/fans has held named fans with intent scores since smart links
        shipped.

        Same rule as the royalty dashboard, for the same reason: showcase data
        handed to a real artist reads as their own.

        2026-09-18: this is now the Audience screen from the owner's approved
        mockup, built by fan_audience over the same records. ?export=csv with
        region=... is the "Use this selection" step: the contactable fans in
        the ticked places, as a CSV. Suppressed fans are never in it.
        """
        import fan_audience

        user = current_user()
        showcase = _session_is_demo() or user is None

        if request.args.get("export") == "csv":
            if user is None:
                return login_required_redirect()
            keys = [k for k in request.args.getlist("region") if k]
            if not keys:
                return redirect("/fans")
            rows = fan_audience.selection_rows(
                fan_audience.showcase_rows() if showcase else mls.list_fans(user["id"]), keys)
            import csv as _csv
            import io as _io
            out = _io.StringIO()
            w = _csv.writer(out)
            w.writerow(["Email", "Name", "City", "Country"])
            for f in rows:
                w.writerow([f.get("email") or "", f.get("name") or "",
                            f.get("city") or "", f.get("country") or ""])
            return Response(out.getvalue(), mimetype="text/csv", headers={
                "Content-Disposition": "attachment; filename=street-banker-fans-selection.csv"})

        ctx = build_dashboard_context()
        if showcase:
            ctx["audience"] = fan_audience.showcase()
        else:
            ctx["audience"] = fan_audience.for_account(
                user["id"], resend_configured=emailer.configured())
        ctx["shopify_import"] = (shopify_customers.status()
                                 if _shopify_import_allowed(user) else None)
        if not showcase:
            ctx["fan_import_result"] = _import_result(user["id"], request.args.get("imp") or "")
        # FIRST RUN (owner-approved mockup, 2026-09-18). A real account with
        # nobody on file gets the import as the page, not a screen of empty
        # panels; from the first fan it is the Audience screen as before.
        # The showcase never sees this: it always has its generated rows.
        if not showcase and not ctx["audience"]["total"]:
            ctx["last_list_import"] = store.latest_fan_import(user["id"], "list")
            ctx["pending_draft"] = store.get_fan_import_draft(user["id"])
            ctx["import_max_rows"] = fan_list_import.MAX_ROWS
            return render_template("fans_first_run.html", active_page="fans", **ctx)
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

    @app.route("/apparel")
    def apparel():
        # The label store, embedded when the store's own Buy Button
        # credentials are set and linked when they are not. No payment
        # code on this side either way.
        ctx = build_dashboard_context()
        ctx["label"] = get_label_data()
        ctx["shopify"] = shopify_buy.context()
        user = current_user()
        ctx["is_owner"] = bool(user and _is_owner_email(user.get("email")))
        # The owner sees whether Shopify accepts the saved token and finds
        # the collection - the same call the embed makes, cached, so a
        # blank widget has a sentence beside it instead of a mystery.
        ctx["shopify_check"] = shopify_buy.check() if ctx["is_owner"] else None
        return render_template("apparel.html", active_page="apparel", **ctx)

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
        """Deleted: listener, follower, age and country splits were invented.
        The live numbers the app does have are on Artist Pulse."""
        return redirect("/pulse")

    @app.route("/playlists")
    def playlists():
        """Deleted: playlists, curators and follower counts were invented.
        Pitch tracking that is real - who was sent what, who opened it -
        is the Press Desk."""
        return redirect("/press-desk")

    @app.route("/stats")
    def stats():
        """Folded into Artist Pulse. Every number here was already on the
        Pulse page - the same followers, popularity, Deezer fans and
        snapshot history - except the owned link engagement, which moved
        there too."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        return redirect("/pulse#engagement")

    @app.route("/funding")
    def funding():
        user = current_user()
        if user is None:
            return login_required_redirect()
        ctx = build_dashboard_context()
        # From the artist's own statements. This page used to quote a
        # suggested advance - with a Request button under it - scaled off
        # a hardcoded earnings trend identical for every account.
        elig = capital_engine.advance_eligibility(user["id"])
        ctx["advance_eligibility"] = elig
        ctx["funding"] = get_funding_data(elig)
        return render_template("funding.html", active_page="funding", **ctx)

    @app.route("/funding/request", methods=["POST"])
    def funding_request():
        payload = request.get_json(silent=True) or {}
        offer_id = (payload.get("offer_id") or "").strip()
        user = current_user()
        if user is None:
            return jsonify({"error": "auth required"}), 401
        data = get_funding_data(capital_engine.advance_eligibility(user["id"]))
        offer = next((o for o in data["offers"] if o["id"] == offer_id), None)
        if offer is None:
            return jsonify({"ok": False, "error": "Unknown offer."}), 400
        # No money moves and no application is submitted - the lenders on
        # this page are examples, and the page says so. What the page also
        # said was that requesting "records interest", and nothing was
        # written anywhere: the reference was assembled and returned and
        # the request dropped. It is recorded now, against the account
        # that made it, so the sentence is true and the artist can see
        # later what they asked about.
        #
        # The reference took offer_id.split("-")[-1], so offer-royalty-
        # advance and offer-catalog-advance both produced REQ-ADVANCE-
        # <date> - two different requests, one reference. It uses the
        # whole id now.
        reference = "REQ-%s-%s" % (
            offer_id.replace("offer-", "", 1).upper().replace("-", ""),
            datetime.today().strftime("%Y%m%d"))
        store.notify(user["id"], "recovery",
                     "Funding interest recorded: %s" % offer["name"],
                     "Reference %s. Nothing was submitted to a lender - the "
                     "providers on this page are examples - and no money "
                     "moves. This is your own note that you looked at it."
                     % reference,
                     "/funding")
        return jsonify({"ok": True, "reference": reference, "offer": offer["name"]})

    _DOC_TYPES = ["Split Agreement", "Producer Agreement", "Feature Agreement",
                  "Distribution", "Publishing", "Sync License", "Statement",
                  "Registration", "Other"]
    _DOC_EXTS = ("pdf", "doc", "docx", "txt", "csv", "png", "jpg", "jpeg", "webp")

    @app.route("/documents", methods=["GET", "POST"])
    @app.route("/vault/documents", methods=["POST"])
    def documents():
        """Contracts & licences are a section of the Vault (tier C,
        2026-09-09): one store. GET forwards; POST still files a document
        from either address, into the vault, with its paperwork facts."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        # The old page was Pro; the vault is Artist. The section is gated
        # the way the page was, from either address.
        tier = plans.required_tier("/documents")
        if not plans.allowed(user.get("plan") or "artist", tier):
            return render_template("upgrade.html", required=tier,
                                   plans_list=plans.PLANS,
                                   **build_dashboard_context()), 402
        if request.method != "POST":
            return redirect("/vault?view=contracts")
        f = request.files.get("document")
        if f is None or not f.filename:
            return _render_vault(user, doc_error="Choose a file to upload.")
        ext = f.filename.rsplit(".", 1)[-1].lower()
        if ext not in _DOC_EXTS:
            return _render_vault(user, doc_error="Use PDF, DOC/DOCX, TXT, CSV, or an image file.")
        fname = "doc_%s.%s" % (uuid.uuid4().hex, ext)
        # Same store as every other vault file: the object store when it
        # is configured, the disk when it is not.
        path = blob_store.save(fname, f.read(), content_type=f.mimetype,
                               uploads_dir=UPLOADS_DIR)
        doc_type = request.form.get("doc_type") or "Other"
        store.add_document(user["id"], f.filename, path,
                           doc_type if doc_type in _DOC_TYPES else "Other",
                           (request.form.get("note") or "").strip(),
                           (request.form.get("track") or "").strip())
        return redirect("/vault?view=contracts")

    @app.route("/documents/<doc_id>/delete", methods=["POST"])
    @app.route("/vault/documents/<doc_id>/delete", methods=["POST"])
    def document_delete(doc_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        path = store.delete_document(user["id"], doc_id)
        if path and (blob_store.is_remote(path)
                     or path.startswith(("/uploads/doc_", "/uploads/vault_"))):
            blob_store.remove(path, uploads_dir=UPLOADS_DIR)
        return redirect("/vault?view=contracts")

    @app.route("/identifiers")
    def identifiers():
        """Folded into the catalog. This page rendered the catalog's own
        records a second time, read for their codes; the codes now sit on
        the catalog beside the records they belong to."""
        return redirect("/catalog#identifiers")

    @app.route("/conflicts")
    def conflicts():
        return render_template("conflicts.html", active_page="conflicts", **build_dashboard_context())

    # Milestone presets are parameterized date math over each campaign's
    # own release date — nothing is stored, nothing is predicted.
    _SCHED_PRESETS = {"standard": ("Standard 30-day", 30),
                      "blitz": ("14-day blitz", 14),
                      "surprise": ("Surprise drop", 0)}

    def _scheduler_events(user_id, preset):
        today = date.today().isoformat()
        events = []
        warnings = []
        for c in mls.list_campaigns(user_id):
            if c.get("archived_at") or not c.get("release_date"):
                continue
            events.append({"date": c["release_date"], "kind": "release",
                           "lane": c["title"], "title": c["title"],
                           "detail": "%s release day" % (c.get("release_type") or "single"),
                           # /links/<id> has no page; the campaign lives at /edit.
                           "href": "/links/%s/edit" % c["id"],
                           "status": c["status"]})
            try:
                days_left = (date.fromisoformat(c["release_date"][:10])
                             - date.today()).days
            except ValueError:
                continue
            if 0 <= days_left < 21:
                warnings.append({
                    "campaign": c["title"], "days": days_left,
                    "level": "red" if days_left < 7 else "amber",
                    "text": ("inside the 7-day Spotify editorial minimum — "
                             "the pitch window is effectively closed"
                             if days_left < 7 else
                             "under the recommended 21-day runway — pitch "
                             "and pre-save windows are compressed"),
                    "href": "/releases/autopilot?campaign=%s" % c["id"]})
            if days_left > 0 and preset in _SCHED_PRESETS:
                plan_days = _SCHED_PRESETS[preset][1]
                if plan_days:
                    plan = artist_os.campaign_plan(plan_days, c["title"],
                                                   c["release_date"])
                    for lbl, sub, tasks in plan["windows"]:
                        if not lbl.endswith("days out"):
                            continue
                        offset = int(lbl.split(" ")[0])
                        mdate = (date.fromisoformat(c["release_date"][:10])
                                 - timedelta(days=offset)).isoformat()
                        if mdate < today:
                            continue
                        events.append({
                            "date": mdate, "kind": "milestone",
                            "lane": c["title"],
                            "title": "%s — %s" % (sub, c["title"]),
                            "detail": tasks[0],
                            "href": "/releases/autopilot?campaign=%s&days=%d"
                                    % (c["id"], plan_days),
                            "status": lbl})
        for r in ros.list_campaigns(user_id):
            for p in ros.list_posts(r["id"]):
                if not p.get("scheduled_date"):
                    continue
                events.append({"date": p["scheduled_date"], "kind": "post",
                               "lane": r["title"],
                               "title": "%s post — %s" % (p.get("platform", "").title(),
                                                          r["title"]),
                               "detail": (p.get("caption") or "")[:90],
                               "href": "/rollout-studio/%s" % r["id"],
                               "status": p["status"]})
        events.sort(key=lambda e: e["date"])
        return events, warnings

    def _release_calendar(user_id, preset, keep_args=None):
        """The Release Scheduler's page: lanes, warnings, presets and the
        month rail, computed from the account's campaigns and rollout
        posts. Rendered as the Calendar section of Release Autopilot
        (tier C, 2026-09-09); the .ics feed reads the same events."""
        if preset not in _SCHED_PRESETS:
            preset = "off"
        today = date.today().isoformat()
        events, warnings = _scheduler_events(user_id, preset)
        upcoming = [e for e in events if e["date"] >= today]
        past = [e for e in events if e["date"] < today][-15:]
        # Swimlanes: one horizontal track per campaign over the next 90 days.
        horizon = 90
        lanes = []
        for e in upcoming:
            try:
                off = (date.fromisoformat(e["date"][:10]) - date.today()).days
            except ValueError:
                continue
            if off > horizon:
                continue
            lane = next((l for l in lanes if l["name"] == e["lane"]), None)
            if lane is None:
                lane = {"name": e["lane"], "events": []}
                lanes.append(lane)
            lane["events"].append(dict(e, pct=round(off / horizon * 100, 1)))
        # Group upcoming by month for the calendar rail.
        months = []
        for e in upcoming:
            label = e["date"][:7]
            if not months or months[-1]["month"] != label:
                months.append({"month": label, "events": []})
            months[-1]["events"].append(e)
        # Preset links keep the desk's own arguments (campaign, days) so a
        # milestone overlay never loses the release it was read beside.
        base = {"view": "calendar"}
        base.update({k: v for k, v in (keep_args or {}).items() if v})
        def _href(key):
            q = dict(base, preset=key) if key != "off" else dict(base)
            return "/releases/autopilot?%s" % urllib.parse.urlencode(q)
        preset_links = [("off", "Off", _href("off"), preset == "off")] + [
            (key, label, _href(key), preset == key)
            for key, (label, _days) in _SCHED_PRESETS.items()]
        return {"months": months, "past": past, "lanes": lanes,
                "warnings": warnings, "preset": preset,
                "presets": _SCHED_PRESETS, "preset_links": preset_links,
                "total_upcoming": len(upcoming)}

    @app.route("/releases")
    def releases():
        """The Release Scheduler is the Calendar section of Release
        Autopilot now (tier C, 2026-09-09): one page shell, one campaign
        context. The .ics feed below keeps its URL - calendar
        subscriptions point at it."""
        if current_user() is None:
            return login_required_redirect()
        qs = request.query_string.decode("utf-8", "replace")
        return redirect("/releases/autopilot?view=calendar" + ("&" + qs if qs else ""))

    @app.route("/releases/calendar.ics")
    def releases_ics():
        """One-way iCalendar feed of the same derived events — import it
        into Google/Apple/Outlook. (Two-way sync would need their OAuth
        apps; this file is honest about being an export.)"""
        user = current_user()
        if user is None:
            return login_required_redirect()
        preset = request.args.get("preset") or "off"
        events, _w = _scheduler_events(user["id"], preset)
        def esc(s):
            return (s or "").replace("\\", "\\\\").replace(";", "\\;") \
                            .replace(",", "\\,").replace("\n", "\\n")
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
                 "PRODID:-//Street Banker//Release Scheduler//EN"]
        for i, e in enumerate(events):
            d = e["date"][:10].replace("-", "")
            lines += ["BEGIN:VEVENT",
                      "UID:sb-%s-%d@streetbanker" % (d, i),
                      "DTSTART;VALUE=DATE:" + d,
                      "SUMMARY:" + esc(e["title"]),
                      "DESCRIPTION:" + esc(e["detail"]),
                      "END:VEVENT"]
        lines.append("END:VCALENDAR")
        return Response("\r\n".join(lines), mimetype="text/calendar",
                        headers={"Content-Disposition":
                                 "attachment; filename=street-banker-releases.ics"})

    @app.route("/registration")
    def registration():
        """Deleted: the wizard only ever ran over the demo songs, so a real
        account saw an empty page. PRO, MLC, SoundExchange and Content ID
        status live on each Track Passport."""
        return redirect("/tracks")

    def _search_pages(user):
        """Every page this account's sidebar offers, as {key, href, label,
        desc, group}, for /search to find by name (audit, 2026-09-19: the
        sidebar's Search box could not find the Statements page). The hub
        pages come from the palette's list and the rooms from rooms.build,
        under the rules inject_hub_context applies: a fan gets the fan
        shell, a switched-off page is kept only for an owner, a locked demo
        loses the Sample pages, a team seat sees only the rooms opened to
        it, and the Label cards need a Label plan."""
        if not user:
            return []
        plan = user.get("plan") or "artist"
        is_owner = bool(_is_owner_email(user.get("email")))
        demo = bool(_demo_locked_account())
        hide = set() if is_owner else set(_page_hidden())
        if demo:
            hide |= hub_defs.demo_hidden_keys()
        seat = (getattr(g, "_team_seat", None) or (None, None))[1] if session.get("team_as") else None
        if seat:
            hide |= team_areas.hidden_page_keys(seat["areas"])
        if plan != "label":
            hide |= set(rooms.LABEL_ONLY)
        pages = [dict(e) for e in _palette_for(user) if e["key"] not in hide]
        if plan != "fan":
            granted = team_areas.parse(seat["areas"]) if seat else None
            for rkey, name, purpose, _icon, cards in rooms.build(plan, is_owner, demo):
                if granted is not None and rkey not in granted:
                    continue
                pages.append({"key": "room " + rkey, "href": "/room/" + rkey,
                              "label": name, "desc": purpose, "group": "Rooms"})
                pages.extend({"key": key, "href": href, "label": label,
                              "desc": desc, "group": name}
                             for key, href, _i, label, desc, _state in cards
                             if key not in hide)
        return pages

    @app.route("/search")
    def search_route():
        ctx = build_dashboard_context()
        user = current_user()
        ctx["search_results"] = global_search(
            request.args.get("q", ""),
            user_id=(user or {}).get("id"),
            demo=_is_demo_email((user or {}).get("email") or ""),
            pages=_search_pages(user))
        return render_template("search.html", active_page="search", **ctx)

    @app.route("/notifications")
    def notifications():
        # Signed in is the only way anyone arrives: plan_gate sends an
        # anonymous request for this path to /login before it gets here.
        # The old `if user:` had an else branch rendering a showcase feed
        # out of notifications_config, plus /notifications/<id>/read and
        # /notifications/read-all writing a module-level set of read ids
        # shared by every account. No user in any state could reach any
        # of it - notifications_real.html has no mark-read control - so
        # it went with the rest of the shared-state family.
        user = current_user()
        if user is None:
            return login_required_redirect()
        items = store.list_notifications(user["id"])
        if not session.get("team_as"):
            store.mark_notifications_read(user["id"])  # viewing clears the badge
        return render_template("notifications_real.html", active_page="notifications",
                               items=items, **build_dashboard_context())

    @app.route("/notifications/<int:notification_id>/dismiss", methods=["POST"])
    def notification_dismiss(notification_id):
        """Reported live: a notification, once read, could never be removed.
        Scoped to the account in the DELETE itself, so a guessed id belonging
        to somebody else removes nothing."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_notification(user["id"], notification_id)
        return redirect(url_for("notifications"))

    @app.route("/notifications/clear", methods=["POST"])
    def notifications_clear():
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.clear_notifications(user["id"])
        return redirect(url_for("notifications"))

    @app.route("/tax")
    @app.route("/tax-center")
    @app.route("/tax/<path:_rest>")
    @app.route("/tax-center/<path:_rest>")
    def tax(_rest=None):
        """The Tax Center is the Tax view of Statements now (owner,
        2026-09-19: "move tax center with statements"). The old addresses
        stay alive and land on it; _tax_years() beside the statements
        route does the work the page used to."""
        return redirect("/statements?view=tax", code=301)

    @app.route("/billing")
    def billing():
        user = current_user()
        if user is None:
            return login_required_redirect()
        ctx = build_dashboard_context()
        ctx["billing"] = get_billing_data(ctx["account"])
        ctx["plan_cards"] = plans.PLANS
        ctx["user"] = user
        ctx["demo_switching"] = _demo_switching(user)
        ctx["webhook_live"] = stripe_billing.webhook_accepts()
        ctx["webhook_current"] = stripe_billing.webhook_events_current()
        sid = request.args.get("session_id") or ""
        if request.args.get("credits") == "1" and sid:
            paid = stripe_billing.get_checkout_session(sid)
            if paid and paid.get("client_reference_id") == user["id"]:
                _claim_credit_pack(paid)
        ctx["wallet"] = _wallet(user)
        ctx["credit_packs"] = [(k,) + v for k, v in plans.CREDIT_PACKS.items()]
        ctx["credit_packs_on_sale"] = plans.CREDIT_PACKS_ON_SALE
        ctx["credit_history"] = store.credit_history(user["id"], 12)
        return render_template("billing.html", active_page="billing", **ctx)

    _TEAM_ROLES = ("manager", "accountant", "publicist", "attorney", "assistant")

    @app.route("/team")
    def team():
        user = current_user()
        if user is None:
            return login_required_redirect()
        plan = user.get("plan") or "artist"
        owner = _is_owner_email(user.get("email"))
        seats = None if owner else plans.team_seats(plan)
        page = max(0, int(request.args.get("older") or 0)) if (request.args.get("older") or "").isdigit() else 0
        members = store.list_team(user["id"])
        for m in members:
            m["rooms_label"] = team_areas.describe(m.get("areas"))
            m["rooms_set"] = team_areas.parse(m.get("areas"))
        return render_template("team.html", active_page="team",
                               members=members,
                               room_choices=[(k, team_areas.LABELS[k]) for k in team_areas.keys()],
                               # The platform owner's account is never opened
                               # from a Portal, so its page says so (review).
                               team_opens=not owner,
                               audit_page=page, audit_older=len(store.list_team_audit(user["id"], 1, (page + 1) * 25)) > 0,
                               roles=_TEAM_ROLES,
                               email_configured=emailer.configured(),
                               seats_total=seats, seats_used=store.count_team_seats(user["id"]),
                               can_grant_edit=owner or plans.team_can_edit(plan),
                               can_grant_roster=owner or plans.team_can_roster(plan),
                               audit=store.list_team_audit(user["id"], 25, page * 25),
                               **build_dashboard_context())

    @app.route("/team/<member_id>/access", methods=["POST"])
    def team_member_access(member_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        plan = user.get("plan") or "artist"
        owner = _is_owner_email(user.get("email"))
        access = "edit" if (request.form.get("access") == "edit"
                            and (owner or plans.team_can_edit(plan))) else "read"
        roster = (request.form.get("can_roster") == "1" and access == "edit"
                  and (owner or plans.team_can_roster(plan)))
        # The Team page's form says it carries the room boxes; a request
        # without them changes access and leaves the rooms as they are.
        areas = (team_areas.from_form(request.form.getlist("areas"))
                 if request.form.get("areas_sent") else None)
        if areas == "":
            return redirect("/team?rooms=none")
        store.set_team_access(user["id"], member_id, access, roster, areas)
        return redirect("/team")

    @app.route("/team/invite", methods=["POST"])
    def team_invite():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        if not _may_seat(user, "team"):
            return jsonify({"ok": False, "error": _NO_SEAT["team"]}), 402
        email = (request.form.get("email") or "").strip().lower()
        role = request.form.get("role") or "manager"
        plan = user.get("plan") or "artist"
        owner = _is_owner_email(user.get("email"))
        seats = None if owner else plans.team_seats(plan)
        if seats is not None and store.count_team_seats(user["id"]) >= seats:
            return jsonify({"ok": False, "error": (
                "Your %s membership includes %d team seat%s, and they are all taken. "
                "Remove someone, or move up a plan for more." % (
                    plans.PLAN_NAMES.get(plan, plan), seats, "" if seats == 1 else "s"))}), 402
        access = "edit" if (request.form.get("access") == "edit"
                            and (owner or plans.team_can_edit(plan))) else "read"
        can_roster = (request.form.get("can_roster") == "1" and access == "edit"
                      and (owner or plans.team_can_roster(plan)))
        if "@" not in email or role not in _TEAM_ROLES:
            return jsonify({"ok": False, "error": "Enter a valid email and pick a role."}), 400
        if email == user["email"]:
            return jsonify({"ok": False, "error": "That's you — no invite needed."}), 400
        # From the Team page the rooms are whatever was ticked, and none is
        # refused. An invite made any other way opens every room, which is
        # what a seat opened before rooms existed (owner, 2026-09-19).
        areas = (team_areas.from_form(request.form.getlist("areas"))
                 if request.form.get("areas_sent") else team_areas.ALL)
        if not areas:
            return jsonify({"ok": False, "error": "Tick at least one room they can open."}), 400
        invite = store.add_team_invite(user["id"], email, role, access, can_roster, areas,
                                       limit=seats)
        if invite == "full":
            return jsonify({"ok": False, "error": (
                "Your %s membership includes %d team seat%s, and they are all taken. "
                "Remove someone, or move up a plan for more." % (
                    plans.PLAN_NAMES.get(plan, plan), seats, "" if seats == 1 else "s"))}), 402
        if invite is None:
            return jsonify({"ok": False, "error": "That email is already on your team."}), 400
        link = request.url_root.rstrip("/") + "/team/join/" + invite["invite_token"]
        emailed = False
        if emailer.configured():
            emailed = emailer.send(
                email, "%s invited you to their Street Banker team" % user["name"],
                '<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">'
                "<h2>You're invited</h2>"
                "<p><strong>%s</strong> added you to their Street Banker team as their "
                "<strong>%s</strong>.</p>"
                '<p><a href="%s" style="display:inline-block;background:#E8B950;color:#14100A;'
                'font-weight:bold;padding:12px 24px;border-radius:10px;text-decoration:none;">'
                "Accept the invite</a></p></div>" % (user["name"], role, link), reply_to=user["email"])
        return jsonify({"ok": True, "link": link, "emailed": emailed})

    @app.route("/team/join/<token>", methods=["GET", "POST"])
    def team_join(token):
        invite = store.get_team_invite(token)
        if invite is None:
            return render_template("team_join.html", invalid=True, invite=None, error=None)
        error = None
        if request.method == "POST":
            existing = store.get_user_by_email(invite["email"])
            if existing:
                ok, why = _join_existing_ok(existing)
                if not ok:
                    return render_template("team_join.html", invalid=False,
                                           invite=invite, has_account=True,
                                           signed_in_as_invitee=False, error=why), 403
                member_id = existing["id"]
            else:
                if not _signup_open():
                    return render_template("team_join.html", invalid=False, invite=invite,
                                           has_account=False, closed=True,
                                           error=_MEMBER_LINK_SHUT), 403
                # Same rule as the roster door: with sign-up open the
                # invitation authorises the account, and the account that
                # issued it must still be allowed to.
                inviter = store.get_user(invite["owner_id"])
                if not _may_seat(inviter, "team"):
                    return render_template("team_join.html", invalid=False,
                                           invite=invite, error=_INVITE_ONLY), 403
                name = (request.form.get("name") or "").strip()
                password = request.form.get("password") or ""
                if not name or len(password) < 6:
                    error = "Enter your name and a password of 6+ characters."
                    return render_template("team_join.html", invalid=False,
                                           invite=invite, error=error)
                member_id = store.create_user(invite["email"], name,
                                              generate_password_hash(password))
            store.accept_team_invite(token, member_id)
            store.notify(invite["owner_id"], "team",
                         "Team invite accepted",
                         "%s joined your team as %s." % (invite["email"], invite["role"]),
                         "/team")
            session["user_id"] = member_id
            return redirect("/command-center")
        return render_template("team_join.html", invalid=False, invite=invite,
                               has_account=store.get_user_by_email(invite["email"]) is not None,
                               signed_in_as_invitee=_signed_in_as(invite["email"]),
                               closed=not _signup_open(), error=None)

    @app.route("/team/<member_id>/remove", methods=["POST"])
    def team_remove(member_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        ok = store.remove_team_member(user["id"], member_id)
        if ok:
            # Whoever leaves may have seen the drop-box address: it changes,
            # so what they saw stops working (team review, 2026-09-19).
            store.rotate_ingest_token(user["id"])
        return jsonify({"ok": ok})

    @app.route("/onboarding")
    def onboarding():
        catalog = get_platform_catalog()
        # Nothing is pre-checked. The status column on _DEFAULT_PLATFORMS is
        # seed data, and reading it here meant seven of these eight boxes -
        # Spotify, Apple Music, ASCAP, BMI, SESAC, SoundExchange, The MLC -
        # rendered ticked on the first screen a brand-new artist ever sees,
        # under the heading "Connect your sources". It told them their PRO
        # and MLC accounts were already linked, and flatly contradicted
        # /connections, which says "Not connectable yet - and we won't fake
        # them". The tick state was never submitted or persisted anywhere,
        # so it claimed those integrations while doing nothing at all.
        sources = [{"name": p.platform, "logo": platform_logo_key(p.platform),
                    "connected": False} for p in catalog[:8]]
        eq = get_artist_eq_config()
        return render_template(
            "onboarding.html", sources=sources,
            program_links_json=json.dumps({
                "modules": eq["module_routes"], "actions": eq["action_routes"]}))

    _DISPUTE_TYPES = ["missing payment", "wrong split", "content claim",
                      "takedown", "metadata error", "chargeback", "other"]
    _DISPUTE_STATUSES = ["open", "submitted", "resolved", "rejected"]

    # ---------- Hours desk ------------------------------------------------
    # Four things that all come down to time: what you worked, what you
    # charge, what other people worked for you, and how the day is laid out.
    # Every figure on the page is summed from stored rows.

    _HOURS_STARTER = [
        ("Mixing", 75.0, 0.0, True),
        ("Studio time", 40.0, 2.0, True),
        ("Vocal feature", 250.0, 2.0, True),
        ("Beat session", 60.0, 0.0, False),
    ]

    def _hours_ctx(user_id, day=None):
        entries = store.list_hours_entries(user_id)
        invoices = store.list_hours_invoices(user_id)
        bookings = store.list_hours_bookings(user_id)
        subs = store.list_hours_submissions(user_id)
        rates = store.list_hours_rates(user_id)
        today = hours_engine.parse_day(day)
        day_str = today.strftime("%Y-%m-%d")
        blocks = store.list_hours_blocks(user_id, day_str)
        for e in entries:
            e["value"] = hours_engine.entry_value(e)
            e["flags"] = hours_engine.flag_entry(e)
        return {
            "entries": entries,
            "invoices": invoices,
            "bookings": bookings,
            "submissions": subs,
            "rates": rates,
            "bookable": hours_engine.bookable_services(rates),
            "totals": hours_engine.session_totals(entries),
            "groups": hours_engine.group_by_client(entries),
            "invoice_totals": hours_engine.invoice_totals(invoices),
            "booking_totals": hours_engine.booking_totals(bookings),
            "sub_totals": hours_engine.submission_totals(subs),
            "summary": hours_engine.desk_summary(entries, invoices, bookings, subs),
            "plan": hours_engine.day_plan(blocks, bookings, day=day_str),
            "next_number": hours_engine.next_invoice_number(invoices),
            "plan_day": day_str,
            "week": hours_engine.week_days(),
            "today": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

    @app.route("/hours")
    def hours_desk():
        user = current_user()
        if user is None:
            return login_required_redirect()
        return render_template("hours.html", active_page="hours",
                               starter=_HOURS_STARTER,
                               **_hours_ctx(user["id"], request.args.get("day")),
                               **build_dashboard_context())

    @app.route("/hours/log", methods=["POST"])
    def hours_log():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        f = request.form
        hours = _hours_float(f.get("hours"))
        if hours <= 0:
            return jsonify({"ok": False,
                            "error": "Enter how many hours you worked."}), 400
        store.add_hours_entry(user["id"], f.get("day"), f.get("project"),
                              f.get("client"), f.get("service"), hours,
                              _hours_float(f.get("rate")), f.get("note"))
        return redirect(url_for("hours_desk"))

    @app.route("/hours/entry/<entry_id>/delete", methods=["POST"])
    def hours_entry_delete(entry_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        # Billed lines stay: removing one would leave its invoice claiming
        # hours that no longer exist anywhere.
        if not store.delete_hours_entry(user["id"], entry_id):
            return jsonify({"ok": False,
                            "error": "Already invoiced — that line stays."}), 400
        return redirect(url_for("hours_desk"))

    @app.route("/hours/invoice", methods=["POST"])
    def hours_invoice():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        ids = request.form.getlist("entry_id")
        inv = store.create_hours_invoice(
            user["id"], ids,
            request.form.get("number") or hours_engine.next_invoice_number(
                store.list_hours_invoices(user["id"])),
            request.form.get("client"), request.form.get("project"))
        if inv is None:
            return jsonify({"ok": False,
                            "error": "Nothing unbilled in that selection."}), 400
        # Leave a trail in the inbox: an invoice that went out with no record
        # of going out is how you end up chasing the wrong client.
        store.add_inbox("invoice", {
            "number": inv["number"], "client": inv["client"],
            "project": inv["project"], "hours": inv["hours"],
            "total": inv["total"]}, user_id=user["id"])
        return redirect(url_for("hours_desk"))

    @app.route("/hours/invoice/<invoice_id>/paid", methods=["POST"])
    def hours_invoice_paid(invoice_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        store.set_hours_invoice_paid(user["id"], invoice_id)
        return redirect(url_for("hours_desk"))

    @app.route("/hours/rate", methods=["POST"])
    def hours_rate():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        f = request.form
        if f.get("starter"):
            # One click to a usable rate card; every line still editable.
            for i, (svc, rate, mins, book) in enumerate(_HOURS_STARTER):
                store.set_hours_rate(user["id"], svc, rate, mins, book, "", i)
            return redirect(url_for("hours_desk"))
        if not (f.get("service") or "").strip():
            return jsonify({"ok": False, "error": "Name the service."}), 400
        store.set_hours_rate(user["id"], f.get("service"),
                             _hours_float(f.get("rate")),
                             _hours_float(f.get("min_hours")),
                             bool(f.get("bookable")), f.get("notes"),
                             len(store.list_hours_rates(user["id"])))
        return redirect(url_for("hours_desk"))

    @app.route("/hours/rate/<rate_id>/delete", methods=["POST"])
    def hours_rate_delete(rate_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        store.delete_hours_rate(user["id"], rate_id)
        return redirect(url_for("hours_desk"))

    @app.route("/hours/booking", methods=["POST"])
    def hours_booking():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        f = request.form
        svc = (f.get("service") or "").strip()
        # The rate comes from your own card, not from the form: a booking
        # form that lets the booker name the price is not a rate card.
        rate, mins = 0.0, 0.0
        for r in store.list_hours_rates(user["id"]):
            if r["service"] == svc and r["bookable"]:
                rate, mins = r["rate"], r["min_hours"]
                break
        else:
            return jsonify({"ok": False,
                            "error": "That service is not bookable."}), 400
        hours = _hours_float(f.get("hours"), 1.0)
        if mins and hours < mins:
            return jsonify({"ok": False, "error":
                            "%s has a %g hour minimum." % (svc, mins)}), 400
        store.add_hours_booking(user["id"], svc, f.get("who"), f.get("contact"),
                                f.get("day"), _hours_float(f.get("start_hour")),
                                hours, rate, f.get("note"))
        return redirect(url_for("hours_desk"))

    @app.route("/hours/booking/<booking_id>/<status>", methods=["POST"])
    def hours_booking_status(booking_id, status):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        if not store.set_hours_booking_status(user["id"], booking_id, status):
            return jsonify({"ok": False, "error": "Unknown status."}), 400
        return redirect(url_for("hours_desk"))

    @app.route("/hours/submission", methods=["POST"])
    def hours_submission():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        f = request.form
        if _hours_float(f.get("hours")) <= 0:
            return jsonify({"ok": False, "error": "Enter the hours."}), 400
        store.add_hours_submission(user["id"], f.get("who"), f.get("role"),
                                   f.get("day"), _hours_float(f.get("hours")),
                                   _hours_float(f.get("rate")), f.get("note"))
        return redirect(url_for("hours_desk"))

    @app.route("/hours/submission/<sub_id>/<decision>", methods=["POST"])
    def hours_submission_decide(sub_id, decision):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        if decision not in ("approve", "reject"):
            return jsonify({"ok": False, "error": "Unknown decision."}), 400
        store.decide_hours_submission(user["id"], sub_id, decision == "approve",
                                      request.form.get("reason"))
        return redirect(url_for("hours_desk"))

    @app.route("/hours/block", methods=["POST"])
    def hours_block():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        f = request.form
        if not (f.get("label") or "").strip():
            return jsonify({"ok": False, "error": "Name the block."}), 400
        day = f.get("day")
        store.add_hours_block(user["id"], day, _hours_float(f.get("start_hour"), 9),
                              _hours_float(f.get("hours"), 1), f.get("label"),
                              f.get("kind") or "work")
        return redirect(url_for("hours_desk", day=day))

    @app.route("/hours/block/<block_id>/<action>", methods=["POST"])
    def hours_block_action(block_id, action):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        if action == "done":
            store.toggle_hours_block(user["id"], block_id)
        elif action == "delete":
            store.delete_hours_block(user["id"], block_id)
        else:
            return jsonify({"ok": False, "error": "Unknown action."}), 400
        return redirect(url_for("hours_desk", day=request.form.get("day")))

    @app.route("/disputes")
    def disputes():
        user = current_user()
        if user is None:
            return login_required_redirect()
        items = store.list_disputes(user["id"])
        return render_template("disputes.html", active_page="disputes",
                               disputes=items, types=_DISPUTE_TYPES,
                               statuses=_DISPUTE_STATUSES,
                               open_count=sum(1 for d in items
                                              if d["status"] in ("open", "submitted")),
                               disputed_total=round(sum(
                                   d["amount"] for d in items
                                   if d["status"] in ("open", "submitted")), 2),
                               recovered_total=round(sum(
                                   d["amount"] for d in items
                                   if d["status"] == "resolved"), 2),
                               **build_dashboard_context())

    @app.route("/disputes/new", methods=["POST"])
    def dispute_new():
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        platform = (request.form.get("platform") or "").strip()
        dtype = request.form.get("dispute_type") or ""
        if not platform or dtype not in _DISPUTE_TYPES:
            return jsonify({"ok": False, "error": "Name the platform and pick a type."}), 400
        try:
            amount = max(0.0, float(request.form.get("amount") or 0))
        except ValueError:
            amount = 0.0
        store.add_dispute(user["id"], platform, dtype,
                          (request.form.get("description") or "").strip(), amount)
        return jsonify({"ok": True})

    @app.route("/disputes/<dispute_id>/delete", methods=["POST"])
    def dispute_delete(dispute_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_dispute(user["id"], dispute_id)
        return redirect("/disputes")

    @app.route("/disputes/<dispute_id>/status", methods=["POST"])
    def dispute_status(dispute_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False}), 401
        status = (request.get_json(silent=True) or {}).get("status") or ""
        if status not in _DISPUTE_STATUSES:
            return jsonify({"ok": False, "error": "Unknown status."}), 400
        ok = store.set_dispute_status(user["id"], dispute_id, status)
        if ok and status == "resolved":
            store.notify(user["id"], "money", "Dispute resolved",
                         "Marked resolved — log the payout in Revenue OS if money moved.",
                         "/disputes")
        return jsonify({"ok": ok})

    def _backup_allowed(user):
        if session.get("team_as") or session.get("acting_as"):
            return False
        return _backup_allowed_for(user)

    def _backup_allowed_for(user):
        """Full-database export: owners only.

        This zip is every account on the deployment - names, email
        addresses, statements, fans - so it cannot hang off a tier. It
        used to qualify any `label` account, and /plan/switch sets that
        tier directly whenever Stripe is unconfigured, so a fresh signup
        could take the whole database. Same shape as the /admin/review
        leak, with a larger payload.

        OWNER_EMAIL (singular) is still honoured: it named exactly this
        capability before _is_owner_email existed, and dropping it would
        lock a live deployment out of its own backups. It is not read
        anywhere else, so it grants the export and nothing more.
        """
        if user is None:
            return False
        if _is_demo_email(user["email"]):        # the shared logins, never
            return False
        if _is_owner_email(user.get("email")):
            return True
        legacy = (os.environ.get("OWNER_EMAIL") or "").strip().lower()
        return bool(legacy) and (user["email"] or "").lower() == legacy

    @app.route("/settings/notifications", methods=["POST"])
    def settings_notifications():
        """Which kinds of notification this account wants. A kind whose box
        is unticked is muted: notify() drops it before it is written."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        wanted = set(request.form.getlist("kind"))
        muted = [k for k, _l, _d in store.NOTIFICATION_KINDS if k not in wanted]
        store.set_muted_kinds(user["id"], muted)
        return redirect("/settings?saved=notifications#notification-preferences")

    @app.route("/settings")
    def settings():
        user = current_user()
        return render_template("settings.html", active_page="settings",
                               home_split=split_home.enabled(),
                               notification_kinds=store.NOTIFICATION_KINDS,
                               muted_kinds=(store.muted_kinds(user["id"]) if user else set()),
                               can_backup=_backup_allowed(current_user()),
                               backup_state=_backup_state(),
                               saved=request.args.get("saved"),
                               deleted=request.args.get("deleted"),
                               reset=request.args.get("reset"),
                               granted=request.args.get("granted"),
                               invited=request.args.get("invited"),
                               signup_open=_signup_open(),
                               **_accounts_panel(user),
                               account_msg=request.args.get("account"),
                               cleared=request.args.get("cleared"),
                               signup_invites=([dict(i, link=public_url("/signup?invite=" + i["token"]))
                                                for i in store.list_signup_invites()]
                                               if user and _is_owner_email(user.get("email")) else []),
                               granted_to=request.args.get("to"),
                               granted_mail=request.args.get("emailed"),
                               granted_why=request.args.get("why"),
                               demo_lock_msg=request.args.get("demo_lock"),
                               demo_lock_to=request.args.get("to"),
                               pages_msg=request.args.get("pages"),
                               page_groups=_page_groups() if user and _is_owner_email(user.get("email")) else [],
                               page_hidden_now=(page_switches.hidden_keys()
                                                if user and _is_owner_email(user.get("email")) else set()),
                               page_protected=page_switches.PROTECTED,
                               demo_locked_accounts=(store.list_demo_locked()
                                                     if user and _is_owner_email(user.get("email")) else []),
                               is_owner=bool(user and _is_owner_email(user.get("email"))),
                               online_sales_on=sales_switch.is_on(),
                               soundcharts_month=(soundcharts_budget.summary()
                                                  if user and _is_owner_email(user.get("email")) else None),
                               # Release-Ready's owner card: prices, the credit
                               # budget and this month's use. Never the key.
                               rr_month=(dict(release_ready_settings.summary(),
                                              key_set=release_ready.roex.configured(),
                                              storage=release_ready.storage_ready())
                                         if user and _is_owner_email(user.get("email")) else None),
                               rr_msg=request.args.get("rr"),
                               online_sales_contact=sales_switch.CONTACT,
                               **build_dashboard_context())

    def _page_groups():
        """The switchboard's rows, grouped by hub in sidebar order."""
        groups, order = {}, []
        for name, key, href, label in page_switches.entries():
            if name not in groups:
                groups[name] = []
                order.append(name)
            groups[name].append((key, href, label, page_switches.is_external(href)))
        return [(name, groups[name]) for name in order]

    @app.route("/account/reset", methods=["POST"])
    def account_reset():
        """Empty the signed-in account and keep the login.

        The owner asked for it (2026-09-14) to hand a demo account their
        label's statements and start their own login blank. Same
        confirmation as deleting - the address typed back - and one
        refusal: fans paying this account through Stripe for its fan
        club, because dropping those rows would leave the subscriptions
        charging with no record of who pays whom.

        The plan, the seats other people gave this account and the
        drop-box address survive; everything filed under the account
        goes, children first, and the bucket objects after the rows.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        typed = (request.form.get("confirm") or "").strip().lower()
        if typed != (user.get("email") or "").strip().lower():
            return redirect("/settings?reset=mismatch#start-over")
        if store.fan_club_subscriptions(user["id"]):
            return redirect("/settings?reset=fans#start-over")
        keys = store.stored_keys_for_user(user["id"])
        store.reset_user_data(user["id"])
        if keys and blob_store.configured():
            for key in keys:
                try:
                    blob_store.delete(key)
                except Exception:          # noqa: BLE001 - rows are gone; do not fail the reset
                    pass
        return redirect("/settings?reset=1#start-over")

    @app.route("/admin/soundcharts-budget", methods=["POST"])
    def admin_soundcharts_budget():
        """The owner sets this month's Soundcharts allowance (the plan's
        monthly calls). Owner only; a 404 for everyone else."""
        user, deny = _owner_or_404()
        if deny:
            return deny
        try:
            soundcharts_budget.set_budget(int((request.form.get("budget") or "").replace(",", "")))
        except ValueError:
            return redirect("/settings?soundcharts=bad#soundcharts")
        return redirect("/settings?soundcharts=saved#soundcharts")

    @app.route("/admin/online-sales", methods=["POST"])
    def admin_online_sales():
        """The owner's switch for online VIP packages and paid fan club
        joins (sales_switch). Owner only; a 404 for everyone else."""
        user, deny = _owner_or_404()
        if deny:
            return deny
        sales_switch.set_on(request.form.get("on") == "1")
        return redirect("/settings#online-sales")

    @app.route("/admin/invite", methods=["POST"])
    def admin_invite():
        """The owner gives somebody an account: an invitation link for one
        address on one plan, good for one use. Owner only, 404 to the rest."""
        user, bail = _owner_or_404()
        if bail:
            return bail
        email = (request.form.get("email") or "").strip().lower()
        plan = (request.form.get("plan") or "artist").strip().lower()
        if "@" not in email or plan not in plans.TIER_RANK:
            return redirect("/settings?invited=bad#invite-someone")
        if store.get_user_by_email(email) is not None:
            return redirect("/settings?invited=exists#invite-someone")
        store.add_signup_invite(email, plan, user["id"],
                                guest_hours=72 if request.form.get("guest") else 0)
        return redirect("/settings?invited=ok#invite-someone")

    def _clearable_fan_accounts(scope, rows=None):
        """The Fan accounts a bulk clear-out may take, and the ones it holds
        back. Held back always: the owner, the shared demo logins, an account
        a partner owns, and anyone who has paid for anything. A bulk button
        must never be able to reach somebody's paid account; those are dealt
        with one at a time or not at all."""
        go, held = [], []
        for a in (rows if rows is not None else store.list_accounts()):
            if (a.get("plan") or "") != "fan":
                continue
            if (_is_owner_email(a.get("email")) or _is_demo_email(a.get("email") or "")
                    or a.get("partner_id") or a.get("has_paid")):
                held.append(a)
                continue
            if scope == "never" and not a.get("never_returned"):
                continue
            go.append(a)
        return go, held

    def _accounts_panel(user):
        """Everything the owner's Accounts panel shows, or nothing at all.

        Hundreds of Fan accounts registered themselves while sign-up was open
        (owner, 2026-09-17), so the panel has to say when each one arrived and
        whether it ever came back: that is what separates a fan from a script.
        """
        if not (user and _is_owner_email(user.get("email"))):
            return {"all_accounts": [], "account_counts": {}, "clear_counts": {},
                    "plan_filter": ""}
        rows, counts = [], {}
        for a in store.list_accounts():
            plan = a.get("plan") or "artist"
            counts[plan] = counts.get(plan, 0) + 1
            rows.append(dict(a, shut=store.account_shut(a),
                             is_owner_row=bool(_is_owner_email(a.get("email"))),
                             is_demo_row=bool(_is_demo_email(a.get("email") or ""))))
        counts["all"] = len(rows)
        never, held = _clearable_fan_accounts("never", rows)
        every, _ = _clearable_fan_accounts("all", rows)
        keep = (request.args.get("plan") or "").strip().lower()
        if keep in plans.TIER_RANK:
            rows = [r for r in rows if (r.get("plan") or "artist") == keep]
        return {"all_accounts": rows, "account_counts": counts, "plan_filter": keep,
                "clear_counts": {"never": len(never), "all": len(every), "held": len(held)}}

    @app.route("/admin/accounts/clear", methods=["POST"])
    def admin_accounts_clear():
        """Clear out the Fan accounts that registered themselves while sign-up
        was open. The owner presses it, the word is typed rather than clicked,
        and the count is on the page before the press. Everything a cleared
        account owned goes with it, in one transaction each."""
        user, bail = _owner_or_404()
        if bail:
            return bail
        scope = request.form.get("scope") or ""
        if scope not in ("never", "all"):
            return redirect("/settings?cleared=bad#accounts")
        if (request.form.get("confirm") or "").strip() != "DELETE":
            return redirect("/settings?cleared=unconfirmed#accounts")
        go, _held = _clearable_fan_accounts(scope)
        for row in go:
            store.delete_user_everything(row["id"])
        return redirect("/settings?cleared=%d#accounts" % len(go))

    @app.route("/admin/account", methods=["POST"])
    def admin_account():
        """The owner's door on any account: lock, unlock, give a guest 72 more
        hours, or make a guest permanent. Nothing here deletes anything."""
        user, bail = _owner_or_404()
        if bail:
            return bail
        target = store.get_user(request.form.get("user_id") or "")
        action = request.form.get("action") or ""
        if target is None or _is_owner_email(target.get("email")):
            return redirect("/settings?account=unknown#accounts")
        if action == "lock":
            store.set_account_locked(target["id"], True)
        elif action == "unlock":
            store.set_account_locked(target["id"], False)
        elif action == "extend":
            store.set_access_ends(target["id"], (datetime.now(timezone.utc) + timedelta(hours=72))
                                  .isoformat(timespec="seconds"))
        elif action == "permanent":
            store.set_access_ends(target["id"], None)
        else:
            return redirect("/settings?account=unknown#accounts")
        return redirect("/settings?account=%s#accounts" % action)

    @app.route("/admin/plan", methods=["POST"])
    def admin_plan():
        """An owner sets the plan on any account by address.

        The one card-free way to put a demo account on Pro or Label
        without leaning on the showcase wildcard (closed 2026-09-14) or a
        Render shell. Owner only, 404 to everybody else.
        """
        user, bail = _owner_or_404()
        if bail:
            return bail
        email = (request.form.get("email") or "").strip().lower()
        plan = (request.form.get("plan") or "").strip().lower()
        target = store.get_user_by_email(email) if email else None
        if target is None:
            return redirect("/settings?granted=unknown#grant-plan")
        if plan not in plans.TIER_RANK:
            return redirect("/settings?granted=badplan#grant-plan")
        store.set_user_plan(target["id"], plan)
        # A paid tier granted by hand holds: renewals and plan changes in
        # Stripe no longer move it (2026-09-19 second review). Granting a
        # free tier hands the account back to its subscription.
        store.set_kv(_plan_grant_key(target["id"]),
                     plan if plan in stripe_billing.PRICES else "")
        # The account is told twice: a notification inside the app, and
        # an email (owner, 2026-09-14: "we do need it to send a email
        # saying they have access now to a plan"). The page reports what
        # the email did - on its way, could not be delivered, or not set
        # up on this deployment - and never says "sent" on a guess.
        emailed, why = _grant_plan_notify(user, target, plan)
        return redirect("/settings?granted=%s&to=%s&emailed=%s%s#grant-plan"
                        % (plan, urllib.parse.quote(email), emailed,
                           ("&why=" + urllib.parse.quote(why[:160])) if why else ""))

    def _grant_plan_email_html(owner_name, target_email, plan):
        """The access email. Same wrapped style as the password reset and
        the team invite; plain standard English; the plan's own blurb and
        feature list from plans.PLANS, so the mail cannot drift from the
        Billing page."""
        import html as _html
        name = plans.PLAN_NAMES.get(plan, plan.title())
        blurb, includes = "", []
        for key, _n, _price, b, inc in plans.PLANS:
            if key == plan:
                blurb, includes = b, list(inc)
        items = "".join("<li>%s</li>" % _html.escape(i) for i in includes)
        return (
            '<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">'
            "<h2>You have %s access</h2>"
            "<p><strong>%s</strong> has put your Street Banker account (%s) on the "
            "<strong>%s</strong> plan. %s</p>"
            "%s"
            '<p><a href="%s" style="display:inline-block;background:#E8B950;color:#14100A;'
            'font-weight:bold;padding:12px 24px;border-radius:10px;text-decoration:none;">'
            "Sign in</a></p>"
            '<p style="color:#91836A;font-size:12px;">No card was charged and nothing renews. '
            "If you were not expecting this, reply to this email.</p></div>"
            % (_html.escape(name), _html.escape(owner_name or "The owner"),
               _html.escape(target_email), _html.escape(name), _html.escape(blurb),
               ("<p>What is open now:</p><ul>%s</ul>" % items) if items else "",
               public_url("/login")))

    def _grant_plan_notify(owner, target, plan):
        """Tell the account. Returns (state, reason): state is "1" when
        the email service accepted the mail, "0" when it refused (reason
        holds the vendor's words), "off" when this deployment cannot send
        - no key, the sandbox, or the shared test sender that delivers
        only to the operator's own inbox. The in-app notification is
        posted whatever the email does."""
        name = plans.PLAN_NAMES.get(plan, plan.title())
        store.notify(target["id"], "billing", "You have %s access" % name,
                     "%s put this account on the %s plan. Everything in it is open."
                     % (owner.get("name") or "The owner", name), "/command-center")
        if not emailer.configured():
            return "off", "Email is not set up on this deployment."
        if emailer.using_shared_test_sender():
            return "off", "The email sender is still the shared test address, which only delivers to the operator."
        ok = emailer.send(target["email"],
                          "You have Street Banker %s access" % name,
                          _grant_plan_email_html(owner.get("name"), target["email"], plan),
                          reply_to=owner.get("email") or None)
        if ok:
            return "1", ""
        return "0", emailer.last_send_error() or "The email service refused it."


    @app.route("/settings/profile", methods=["POST"])
    def settings_profile():
        """Save the display name, for real.

        The form used to call preventDefault() and write localStorage
        under "royaltySweep.profile", which nothing server-side has ever
        read - and it pre-filled DEFAULT_PROFILE, so an artist with no
        localStorage saw "Synthwave Surfer" and artist@streetbanker.io in
        fields labelled as their own account, next to a badge rendering
        their REAL plan. Changing anything and pressing Save changed
        nothing and said "Saved".

        Only the name is writable. Email is the sign-in credential and
        the address every reset goes to, so it is shown and not edited
        here; the plan is billing's to change, and the page links there.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        name = (request.form.get("name") or "").strip()
        if not name:
            return redirect("/settings?saved=empty#account-profile")
        store.set_user_name(user["id"], name)
        return redirect("/settings?saved=1#account-profile")

    @app.route("/account/delete", methods=["POST"])
    def account_delete():
        """Delete the signed-in account and everything filed under it.

        Reported live: Settings had no way to leave. The confirmation is
        the account's own email address typed back, not a checkbox - this
        is the one action on the site that cannot be undone, and the
        backup is the operator's, not the artist's.

        Two refusals, both said on the page: an owner account (deleting it
        locks the operator out of their own deployment - remove it from
        OWNER_EMAILS first) and an account with a live Stripe subscription
        (no cancel call exists here yet; a deleted login that keeps
        billing is worse than a refusal, so Billing comes first).

        Bucket objects are deleted best-effort AFTER the rows commit; a
        bucket that will not answer does not resurrect the account.
        """
        user = current_user()
        if user is None:
            return login_required_redirect()
        typed = (request.form.get("confirm") or "").strip().lower()
        if typed != (user.get("email") or "").strip().lower():
            return redirect("/settings?deleted=mismatch#delete-account")
        if _is_owner_email(user.get("email")):
            return redirect("/settings?deleted=owner#delete-account")
        if user.get("stripe_subscription_id"):
            return redirect("/settings?deleted=billing#delete-account")

        keys = store.stored_keys_for_user(user["id"])
        if user.get("referred_by") or user.get("stripe_customer_id"):
            # Deleting and signing up again must not earn the referral's 50%
            # and the referrer's credit a second time (2026-09-19 second
            # review). Only a hash of the address is kept.
            store.set_kv(_ref_spent_key(user.get("email")), "1")
        store.delete_user_everything(user["id"])
        session.clear()
        if keys and blob_store.configured():
            for key in keys:
                try:
                    blob_store.delete(key)
                except Exception:          # noqa: BLE001 - rows are gone; do not fail the goodbye
                    pass
        return redirect("/login?deleted=1")

    def _snapshot_zip():
        """The archive itself: a consistent database copy plus uploads.

        Uses SQLite's backup API rather than copying the file, because a
        raw copy taken mid-write restores as a corrupt database - and a
        backup you cannot restore is worse than none, since you stop
        worrying about it.
        """
        import sqlite3 as _sq
        import tempfile
        import zipfile
        snap = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        snap.close()
        src = _sq.connect(store.db_path())
        dst = _sq.connect(snap.name)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        buf = tempfile.TemporaryFile()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap.name, "streetbanker.db")
            for root, _dirs, files in os.walk(UPLOADS_DIR):
                for fname in files:
                    full = os.path.join(root, fname)
                    z.write(full, "uploads/" + os.path.relpath(full, UPLOADS_DIR))

            # Objects in the bucket. With R2 configured, blob_store.save
            # returns "r2:<key>" and does NOT also write to disk, so the
            # walk above finds nothing and this zip carried the database
            # alone - while Settings promised "accounts, members, fans,
            # statements, and uploads".
            #
            # A manifest is written whether or not the objects fit, so the
            # archive always says what exists rather than only what it
            # managed to include. A backup that quietly omits things is
            # how somebody discovers at restore time that it stopped
            # working months ago.
            manifest = ["key,bytes,in_this_archive"]
            if blob_store.configured():
                budget = BACKUP_BLOB_BUDGET
                with store.get_db() as _db:
                    keys = blob_inventory.stored_keys(_db)
                for key in keys:
                    data = None
                    try:
                        data = blob_store.fetch(blob_store.PREFIX + key)
                    except Exception:
                        data = None
                    if data is None:
                        manifest.append("%s,,fetch failed" % key)
                        continue
                    if len(data) > budget:
                        manifest.append("%s,%d,skipped - archive size limit"
                                        % (key, len(data)))
                        continue
                    z.writestr("objects/" + key, data)
                    budget -= len(data)
                    manifest.append("%s,%d,yes" % (key, len(data)))
            else:
                manifest.append(",,object storage is not configured on this deployment")
            z.writestr("OBJECTS.csv", "\n".join(manifest) + "\n")
        os.unlink(snap.name)
        buf.seek(0)
        return buf

    def _backup_state():
        """What the last off-box run did, for the settings page. Reads the
        stored record rather than claiming anything about right now."""
        import json as _json
        raw = store.get_kv("backup_last_run")
        last = {}
        if raw:
            try:
                last = _json.loads(raw)
            except ValueError:
                last = {}
        return {
            "offsite_configured": backup_store.configured(),
            "target": backup_store.target(),
            "scheduler_ready": bool(os.environ.get("BACKUP_TOKEN")),
            "last": last,
        }

    @app.route("/backup")
    def backup_download():
        from flask import send_file
        user = current_user()
        if not _backup_allowed(user):
            abort(404)
        buf = _snapshot_zip()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return send_file(buf, mimetype="application/zip", as_attachment=True,
                         download_name="streetbanker-backup-%s.zip" % stamp)

    @app.route("/backup/run", methods=["POST"])
    def backup_run():
        """Take a snapshot and push it off-box.

        Meant for a scheduler (Render Cron, GitHub Actions, cron-job.org)
        presenting BACKUP_TOKEN. An account that may already download the
        backup by hand can also trigger it, so it is testable without
        waiting for a schedule.

        Every outcome is recorded - including the failures. A backup system
        that only logs its successes is how people find out at restore time
        that it stopped working in March.
        """
        import json as _json
        token = os.environ.get("BACKUP_TOKEN") or ""
        presented = (request.headers.get("X-Backup-Token")
                     or request.form.get("token") or "")
        by_token = bool(token) and hmac.compare_digest(presented, token)
        if not (by_token or _backup_allowed(current_user())):
            abort(404)
        if not backup_store.configured():
            return jsonify({
                "ok": False,
                "error": "No off-box target configured. Set BACKUP_S3_ENDPOINT, "
                         "BACKUP_S3_BUCKET, BACKUP_S3_KEY and BACKUP_S3_SECRET.",
            }), 503
        started = datetime.now(timezone.utc)
        buf = _snapshot_zip()
        data = buf.read()
        buf.close()
        name = backup_store.object_name(started)
        ok, detail = backup_store.put(name, data)
        record = {
            "at": started.isoformat(),
            "ok": bool(ok),
            "bytes": len(data),
            "object": name,
            "detail": detail,
            "seconds": round((datetime.now(timezone.utc) - started)
                             .total_seconds(), 1),
        }
        store.set_kv("backup_last_run", _json.dumps(record))
        if not ok:
            # Route the alert to a real account. notify() keys rows by user,
            # so a None here would file it where nobody can read it — a
            # failure alarm nobody hears.
            owner_email = (os.environ.get("OWNER_EMAIL") or "").strip()
            owner = store.get_user_by_email(owner_email) if owner_email else None
            if owner:
                store.notify(owner["id"], "system", "Off-box backup failed",
                             detail[:200], "/settings")
        return jsonify({"ok": bool(ok), "run": record}), (200 if ok else 502)

    _SWEEP_ROLES = [("artist", "Artist"), ("songwriter", "Songwriter"),
                    ("producer", "Producer"), ("manager", "Manager"),
                    ("label", "Label")]

    @app.route("/plan")
    def artist_plan():
        """The Artist EQ's plan, recomputed server-side from the link.

        The console builds this URL from the six channel values, and this
        route runs the same functions in artist_eq_config that the browser
        mirrors - so the plan the visitor clicked is the plan they land
        on. Public: the whole point is that the recommendation is readable
        before anybody makes an account.
        """
        from artist_eq_config import CHANNELS, CHANNEL_KEYS, build_plan

        values = {}
        for key in CHANNEL_KEYS:
            raw = request.args.get(key)
            if raw is not None:
                values[key] = raw
        preset = (request.args.get("preset") or "").strip()[:40]
        plan = build_plan(values, preset)
        return render_template("plan.html", plan=plan, channels=CHANNELS)

    @app.route("/start")
    def guided_start():
        """BUILD MY STREET BANKER - the guided start, in public.

        The closing CTA carries the Artist EQ mix down the page as query
        parameters, so this opens on the plan those settings produce
        rather than on a default. Same build_plan the console and /plan
        already use, so the two surfaces cannot disagree. A visitor can
        change the mix here with the preset buttons; an account is asked
        for only when there is something to save.
        """
        from artist_eq_config import CHANNEL_KEYS, PRESETS, build_plan

        values, carried = {}, False
        for key in CHANNEL_KEYS:
            raw = request.args.get(key)
            if raw is not None:
                values[key] = raw
                carried = True
        preset = (request.args.get("preset") or "").strip()[:40]
        plan = build_plan(values, preset)
        return render_template("start_public.html", plan=plan,
                               presets=PRESETS, carried=carried)

    # About, Contact and Partner Network. The footer named all three and
    # had none of them: About went to /services, Contact went to /submit,
    # and Partner Network went to /network, which is behind the login wall.
    @app.route("/release-signal")
    def release_signal_page():
        """Release Signal, in public.

        No analysis provider is connected on this deployment, so the page
        explains what the read contains and does not accept an upload.
        Taking a file and returning an invented genre would be a fake
        scan, which is the one thing this feature must never do.
        """
        from release_signal import get_release_signal_config

        return render_template("release_signal.html",
                               rs=get_release_signal_config())

    @app.route("/remix-lab")
    def remix_lab():
        """Remix Lab - remix briefs from audio the artist owns.

        Signed-in only. The rights gate, the likeness screen and the worked
        example are on the page; with the engine off nothing on it uploads
        or stores anything. When a backend lands, every
        reference string must pass remix_lab_config.check_reference_text
        server-side before a generation request is made - the browser
        copy of that screen is convenience, not enforcement.
        """
        from remix_lab_config import (get_remix_lab_config,
                                      get_remix_lab_client_config)

        # Signed-in only, inside the shell. It used to be a public page with
        # its own header, which read as being logged out the moment it opened.
        if current_user() is None:
            return login_required_redirect()
        return render_template(
            "remix_lab.html", active_page="remix-lab", remix=get_remix_lab_config(),
            remix_json=json.dumps(get_remix_lab_client_config()),
            **build_dashboard_context())

    @app.route("/remix-lab/brief", methods=["POST"])
    def remix_lab_brief():
        """Run a real remix brief on a track the artist owns.

        The page shipped saying generation was not connected. It now can be,
        because a MusicProvider exposes composition_plan() - tempo, section
        boundaries and an energy curve, measured rather than guessed.

        This is also the server-side likeness screen that remix_lab_config
        asked for in as many words: "the authoritative copy the server must
        call before any generation request leaves the building". It runs on
        every reference line before anything is uploaded or spent.
        """
        import audio_retention
        import audio_store as astore
        import audio_studio
        import audio_works as works
        import remix_lab_config as rlc
        import remix_lab_engine as rle

        user = current_user()
        if user is None:
            return redirect(url_for("login", next="/remix-lab"))
        if not rlc.engine_live():
            abort(404)

        def refuse(message, offending=None):
            return render_template("remix_lab_refused.html", message=message,
                                   offending=offending,
                                   warning=rlc.SAFETY_WARNING,
                                   examples=rlc.ALLOWED_EXAMPLES), 400

        # 1. The screen, first, on every reference line. Before the upload is
        #    read, before an asset exists, before anything is spent.
        references = [r.strip() for r in request.form.getlist("reference") if r.strip()]
        for line in references:
            offending = works.screen_reference(line)
            if offending:
                return refuse("That reference asks for an imitation of a real "
                              "person, so the brief was not run.", offending)

        # 2. Both rights confirmations, which the page has always required.
        if request.form.get("rights_own") != "1" or                 request.form.get("rights_likeness") != "1":
            return refuse("Both rights confirmations are needed before a track "
                          "is uploaded.")

        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return refuse("Choose the track you want a brief for.")
        ext = os.path.splitext(upload.filename)[1].lower()
        if ext not in set(rlc.UPLOAD_FORMATS):
            return refuse("Remix Lab reads %s."
                          % ", ".join(f.upper().lstrip(".") for f in rlc.UPLOAD_FORMATS))
        data = upload.read()
        if not data:
            return refuse("That file is empty.")
        if len(data) > rlc.UPLOAD_MAX_MB * 1024 * 1024:
            return refuse("That track is larger than the %d MB limit."
                          % rlc.UPLOAD_MAX_MB)

        # 3. Stored privately - never the public uploads tree. A master an
        #    artist uploaded is the most valuable file they own.
        path = audio_studio._save(
            "remix_%d%s" % (int(time.time() * 1000), ext), data,
            upload.mimetype or "audio/mpeg")
        asset_id = astore.create_asset(
            None, user["id"], path, file_name=upload.filename[:200],
            mime_type=upload.mimetype or "audio/mpeg", file_size=len(data),
            rights_status="confirmed",
            retention_days=audio_retention.retention_days(None, "source"))

        choices = {
            "lane": request.form.get("remixLane") or "",
            "targetUse": request.form.get("targetUse") or "",
            "energy": request.form.get("energy") or "",
            "tempoDirection": request.form.get("tempoDirection") or "",
            "vocalTreatment": request.form.get("vocalTreatment") or "",
            "instrumentation": request.form.get("instrumentation") or "",
            "riskLevel": request.form.get("riskLevel") or "",
        }

        item = works.create_work(
            user["id"], "remix_plan",
            title=upload.filename[:120],
            brief=" ".join(references)[:2000],
            options=choices, source_asset_id=asset_id)
        works.confirm_rights(item["id"], user.get("name") or user.get("email") or "")

        plan, error = {}, None
        try:
            _item, result = works.submit_work(item["id"])
            result = result or {}
            # The real adapter returns the plan under "plan"; the offline
            # adapter returns it flat. Reading the wrapper as the plan is how
            # a real reading came back as "nothing measured".
            plan = result.get("plan") if isinstance(result.get("plan"), dict) else result
            if result.get("is_mock") and isinstance(plan, dict):
                plan = dict(plan, is_mock=True)
        except works.WorkRefusal as refusal:
            # The item carries the reason; the page shows it rather than a
            # stack trace, and the brief still composes from the choices with
            # every line marked as not measured.
            error = refusal.reason

        brief = rle.compose_brief(plan, choices, track_name=upload.filename)
        return render_template(
            "remix_lab_brief.html", rl=rlc.get_remix_lab_config(),
            brief=brief, plan=plan, choices=choices, error=error,
            grounded=rle.brief_is_grounded(brief),
            is_mock=bool(plan.get("is_mock")),
            track_name=upload.filename, work_id=item["id"])

    @app.route("/release-check")
    def release_check():
        """DISTRIBUTE NOW - the public release-readiness check.

        The distribution section had both of its buttons pointing at
        /distribution, so "Distribute now" and "View distribution guide"
        were the same click. This is the first one: tick what you have,
        see what the release still needs. Counted server-side so the page
        works with JavaScript off and the URL stays shareable.

        A completion count, never a judgement about the record.
        """
        from distro_config import CHECKLIST

        have = set(request.args.getlist("have"))
        total = sum(len(entries) for _, entries in CHECKLIST)
        # Only count ticks that correspond to a real requirement, so a
        # hand-edited query string cannot inflate the readout.
        valid = set()
        for group, entries in CHECKLIST:
            for entry in entries:
                slug = ("%s-%s" % (group, entry)).lower().replace(" ", "-").replace(",", "")
                valid.add(slug)
        have &= valid
        done = len(have)

        if done == total:
            state = "Delivery ready"
        elif done >= -(-total * 3 // 4):
            state = "Ready for review"
        elif done >= -(-total * 35 // 100):
            state = "Needs information"
        else:
            state = "Setup incomplete"

        return render_template("release_check.html", checklist=CHECKLIST,
                               have=have, done=done, total=total, state=state,
                               pct=round(100 * done / total) if total else 0)

    @app.route("/about")
    def about_page():
        from public_pages_config import get_about

        return render_template(
            "public_page.html", pg=get_about(), page_title="About",
            page_description=("What Street Banker is, why it exists, how it "
                              "makes money, and what it is not."))

    @app.route("/contact")
    def contact_page():
        from public_pages_config import get_contact

        return render_template(
            "public_page.html", pg=get_contact(), page_title="Contact",
            page_description=("How to reach Street Banker, and where each "
                              "kind of question actually goes."))

    @app.route("/partners")
    def partners_page():
        from public_pages_config import get_partners

        return render_template(
            "public_page.html", pg=get_partners(), page_title="Partner network",
            page_description=("Who delivers what: the distribution "
                              "partnership that exists today, and the "
                              "integrations we are looking for."))

    @app.route("/artist-control")
    def artist_control_policy():
        """The artist-control policy the trust band links to.

        Public by design: a promise a visitor has to make an account to
        read is not a promise. Ten statements, each one a commitment made
        somewhere else on the homepage.
        """
        from closing_config import POLICY

        return render_template("artist_control.html", policy=POLICY)

    # The public product tour. Named /product-tour rather than /tour
    # because /tour is the signed-in touring pipeline (/tour/<id>,
    # /tour/add, /tour/<id>/status) and has been for a long time.
    @app.route("/product-tour")
    def product_tour():
        """Twelve steps through one example release, no account anywhere."""
        from product_tour_config import get_tour_config

        return render_template("product_tour.html", tour=get_tour_config())

    @app.route("/product-tour/smart-link")
    def product_tour_smart_link():
        """The Smart Links, Fan Intelligence and artwork-generator proof.

        Everything here is a labelled example: the destination rows are
        not connected to a platform, the fan readings are invented for
        illustration, and the page collects nothing from the visitor.
        """
        from product_tour_config import (SMART_LINK, FAN_PANEL, CREATIVE_STEPS,
                                 CREATIVE_OUTPUTS, BRAND_MEMORY)

        return render_template("product_tour_smart_link.html",
                               sl=SMART_LINK, fi=FAN_PANEL,
                               creative_steps=CREATIVE_STEPS,
                               creative_outputs=CREATIVE_OUTPUTS,
                               brand=BRAND_MEMORY)

    @app.route("/artist-twin/history/<generation_id>/delete", methods=["POST"])
    def artist_twin_forget(generation_id):
        """Saved Generations was a list that only grew (table audit,
        2026-09-12): twin_generations had inserts and nothing else."""
        user = current_user()
        if user is None:
            return login_required_redirect()
        store.delete_twin_generation(user["id"], generation_id)
        return redirect("/artist-twin#history")

    @app.route("/artist-twin/start")
    def artist_twin_start():
        """The public Artist Twin entry.

        A visitor picks what they are working on and gets the route the
        Twin would take, plus what it would need to read. No account, no
        upload, and no claim that anything of theirs has been looked at -
        an account is offered at the end, when there is something to save.
        """
        from artist_twin_config import GOALS

        wanted = (request.args.get("goal") or "").strip()[:40]
        selected = next((g for g in GOALS if g["id"] == wanted), None)
        return render_template("artist_twin_start.html", goals=GOALS,
                               selected=selected)

    @app.route("/metadata")
    def passport_public():
        """The Metadata Passport, explained before an account is asked for.

        The seven records, what a conflict looks like, how one entry moves
        the others, and what happens to the information. Everything shown
        is the labelled example; nothing is anybody's release.
        """
        from passport_config import (CATEGORIES, CONNECTED, ISSUES, USE,
                                     STANDARDS)

        return render_template("passport_public.html", categories=CATEGORIES,
                               connected=CONNECTED, issues=ISSUES, use=USE,
                               standards=STANDARDS)

    @app.route("/distribution")
    def distribution_guide():
        """The distribution guide, in public.

        Who delivers, what a release package needs, what each stage does,
        and which parts are the partner's rather than Street Banker's.
        No account, and no claim that a release has been delivered.
        """
        from distro_config import (GUIDE, WORKFLOW, CHECKLIST, INTEGRATIONS,
                                   PARTNER)

        # Signed in, the same guide wears the app frame (with the way back
        # to the Releases room); a stranger gets the public page.
        return render_template("distribution_public.html", guide=GUIDE,
                               workflow=WORKFLOW, checklist=CHECKLIST,
                               integrations=INTEGRATIONS, partner=PARTNER,
                               active_page="distribution")

    @app.route("/royalty-sweep")
    def sweep_method():
        """How Royalty Sweep works, in public.

        What is read, what counts as an opportunity, how an estimate is
        arrived at, how a case is verified, which steps need a person and
        what happens to the data. No figures and no promises.
        """
        from sweep_config import METHOD, SOURCES

        return render_template("sweep_method.html", method=METHOD,
                               sources=SOURCES)

    @app.route("/rollout")
    def rollout_public():
        """Rollout Engine, explained before an account is asked for.

        The example campaign is printed in full and labelled as one, and
        the middle group says plainly that nothing posts itself.
        """
        from rollout_config import (TOUR_SECTIONS, WORKFLOW, SAMPLE, STATUSES,
                                    PLAN_LENGTHS)

        return render_template("rollout_public.html", sections=TOUR_SECTIONS,
                               workflow=WORKFLOW, sample=SAMPLE,
                               statuses=STATUSES, plan_lengths=PLAN_LENGTHS)

    @app.route("/creative-studio")
    def creative_studio_public():
        """Creative Studio, explained before an account is asked for.

        Grouped by what is true rather than by feature: what is in the
        app today, what is guided rather than automatic, and what is not
        built. A visitor should be able to decide against it from here.
        """
        from creative_config import CAPABILITIES, WORKFLOW, MEMORY_TITLE, MEMORY_COPY

        return render_template("creative_studio_public.html",
                               capabilities=CAPABILITIES, workflow=WORKFLOW,
                               memory_title=MEMORY_TITLE, memory_copy=MEMORY_COPY)

    @app.route("/press")
    def press_public():
        """The Press Desk, explained before an account is asked for.

        Sits at /press rather than /press-desk because /press-desk is the
        artist's own workspace and stays behind the wall. The two live in
        one namespace on purpose: /press says what the desk is, and
        /press/<token> is one announcement sent to one recipient.

        The sending status on this page is resolved from capability_status
        at request time, so it cannot promise a delivery route the running
        deployment has not been given credentials for.
        """
        from press_config import get_press_config

        return render_template("press_public.html", press=get_press_config())

    @app.route("/lanes")
    def lanes_public():
        """Find my lane, in public.

        One situation in, one lane out, with the reason printed next to
        it and all three lanes set out underneath - so the suggestion can
        be disagreed with rather than just accepted. No account.
        """
        from lanes_config import LANES, SITUATIONS

        wanted = (request.args.get("situation") or "").strip()[:40]
        picked = next((s for s in SITUATIONS if s["id"] == wanted), None)
        suggested = next((l for l in LANES if picked and l["slug"] == picked["lane"]),
                         None)
        return render_template("lanes_public.html", lanes=LANES,
                               situations=SITUATIONS, picked=picked,
                               suggested=suggested)

    @app.route("/ai")
    def ai_trust():
        """How Street Banker uses AI, in five statements, signed out."""
        from artist_twin_config import TRUST_POINTS

        return render_template("ai_trust.html", points=TRUST_POINTS)

    @app.route("/catalog-sweep", methods=["GET", "POST"])
    def catalog_sweep():
        """The free-sweep entry, open to a visitor with no account.

        The CTA used to point at /recovery, which is behind the login
        wall - so the first thing a stranger got for asking what a sweep
        is was a password field. This asks three questions and then says
        plainly what a sweep checks and what it cannot know yet. It does
        not claim a scan has run, because none has: the engine reads
        uploaded statements, and there are none until somebody uploads
        one.
        """
        form = {}
        error = None
        result = None
        if request.method == "POST":
            form = {
                "catalog": (request.form.get("catalog") or "").strip()[:120],
                "url": (request.form.get("url") or "").strip()[:400],
                "role": request.form.get("role") or "artist",
            }
            roles = dict(_SWEEP_ROLES)
            if not form["catalog"]:
                error = "Tell us which artist or catalog to look at."
            else:
                if form["role"] not in roles:
                    form["role"] = "artist"
                # A lead worth keeping, filed where demo-access requests
                # already go: platform-level, owner-visible, never on an
                # artist's own inbox page.
                try:
                    store.add_inbox("catalog_sweep", {
                        "catalog": form["catalog"], "url": form["url"],
                        "role": form["role"]})
                except Exception:
                    pass  # a lead record must never cost the visitor the page
                result = {
                    "catalog": form["catalog"],
                    "role_label": roles[form["role"]],
                    "checks": [
                        {"title": "Unattributed revenue",
                         "detail": "Rows on your statements that were paid "
                                   "with no track title on them. Actual "
                                   "money, missing its attribution."},
                        {"title": "Coverage gaps",
                         "detail": "Tracks earning on some sources and "
                                   "silent on others, priced at that "
                                   "track's own per-source average."},
                        {"title": "Royalty lanes per song",
                         "detail": "Nine income lanes, marked claimed or "
                                   "missing from what your statements show."},
                        {"title": "Catalog valuation",
                         "detail": "A 3-5x range on the run rate your own "
                                   "statement months produce."},
                    ],
                    "limits": [
                        "It does not read a platform, a PRO or The MLC "
                        "directly - no public feed exists for that.",
                        "It cannot see revenue from a source you have never "
                        "uploaded, and it will not guess at one.",
                        "Estimates are labelled as estimates everywhere they "
                        "appear, and separated from money already paid.",
                    ],
                }
        return render_template("catalog_sweep.html", form=form, error=error,
                               result=result, roles=_SWEEP_ROLES)

    @app.route("/scan/missing-royalties", methods=["POST"])
    def scan_missing_royalties():
        # Same split as /recovery: a real account is scanned against its
        # own statements, and gets an empty result when it has uploaded
        # none rather than the showcase's seventeen findings.
        user = current_user()
        if user is not None and not _session_is_demo():
            view = recovery_engine.build(user["id"])
            return jsonify({
                "ok": True,
                "count": view["finding_count"],
                "total_estimated": view["total_at_stake"],
                "findings": [{"id": f["id"], "source": f["source"],
                              "issue_type": f["issue_type"],
                              "estimated_value": f["amount"],
                              "confidence": f["confidence"],
                              "recommended_action": f["action"]}
                             for f in view["findings"]],
            })
        findings = get_missing_royalty_findings(get_platform_catalog())
        return jsonify({
            "ok": True,
            "count": len(findings),
            "total_estimated": round(sum(f.estimated_value for f in findings), 2),
            "findings": [asdict(f) for f in findings],
        })

    @app.route("/reports/<report_id>/generate", methods=["POST"])
    def generate_report_route(report_id):
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Sign in first."}), 401
        # Build it for real before claiming it exists. When there is no
        # data the honest answer is the reason, not a header-row file -
        # an empty "Missing Money Report" reads as "nothing is missing".
        #
        # That was the intent; the order was wrong. The history row went
        # in first, carrying a filename assembled from the id and today's
        # date, and only then was the builder asked whether it could make
        # anything. Six refusals on an account with no statements still
        # produced six entries under "Recently Generated", every one of
        # them a 404 on download. So: check the id, build, and only file
        # what exists - under the name the builder gave it.
        if report_type(report_id) is None:
            return jsonify({"ok": False, "error": "Unknown report."}), 404
        filename, body, reason = report_builder.build(report_id, user["id"])
        if filename is None:
            return jsonify({"ok": False, "error": reason}), 200
        report = record_generated_report(report_id, user["id"], filename)
        report = {**report, "rows": body.count("\n") - 1,
                  "download": "/reports/%s/download" % report_id}
        return jsonify({"ok": True, "report": report})

    @app.route("/reports/<report_id>/download")
    def download_report_route(report_id):
        user = current_user()
        if user is None:
            return login_required_redirect()
        # Rebuilt from live statement data rather than served from a
        # cache, so the file can never disagree with the page.
        filename, body, reason = report_builder.build(report_id, user["id"])
        if filename is None:
            abort(404, reason)
        return Response(
            body, mimetype="text/csv",
            headers={"Content-Disposition":
                     'attachment; filename="%s"' % filename})

    @app.after_request
    def _mark_sandbox(response):
        """Stamp every HTML page on a sandbox deployment.

        Registered unconditionally but inert unless SANDBOX is set, so
        production returns the identical bytes it returned before this
        existed. Skips streamed files and anything that is not HTML.
        """
        if not sandbox.active() or response.direct_passthrough:
            return response
        if (response.mimetype or "") != "text/html":
            return response
        try:
            html = response.get_data(as_text=True)
        except (UnicodeDecodeError, RuntimeError):
            return response
        marked = sandbox.mark(html)
        if marked != html:
            response.set_data(marked)
        return response

    operator_desk.init(app, is_owner_email=_is_owner_email)
    # Tour, the Tour Board and the Press Desk work in the account a request
    # is in, as Studio and every other page do: the artist's for a team
    # seat and for a partner acting on the artist's behalf (owner,
    # 2026-09-19). tour_os also takes the seat, for what stays the account
    # holder's, and the acting partner, so a change is filed under the
    # person who made it (review, 2026-09-19).
    # Press links are baked into emails and read days later, so they are
    # built from the canonical address rather than whichever host the
    # request happened to arrive on.
    press_desk.init(app, base_url=lambda: PUBLIC_BASE_URL, current_user=current_user,
                    uploads_dir=lambda: UPLOADS_DIR)
    # TOUR: invitation and share links are pasted into messages and read
    # later, so they too are built from the canonical address.
    tour_os.init(app, base_url=lambda: PUBLIC_BASE_URL, current_user=current_user,
                 team_seat=current_team_seat, acting=current_acting)
    # Signal's reading of the artist's own tour dates follows the same
    # account as Tour (it read the signed-in person's).
    import signal_providers as _sp
    _sp.set_account_resolver(lambda: (current_user() or {}).get("id"))
    # Signal: the A&R / distribution / rights intelligence layer. Access is a
    # row in its own roster, seeded from the Operator Desk roster and the
    # owner predicate - no person's name lives in the module.
    signal_hub.init(app, base_url=lambda: PUBLIC_BASE_URL,
                    is_owner_email=_is_owner_email)
    lights_store.init_lights()
    # Partner OS: resellers who put their own name on this software.
    # users.partner_id is the spine - scoping the ACCOUNT to a partner
    # scopes everything the account owns without touching the tables
    # underneath, all of which are already scoped by user_id.
    partner_store.init_partners()
    partner_os.init(app)
    # Audio Intelligence: the provider seam plus its policy, jobs and
    # usage ledger. Adapters register themselves on import; the mock is
    # the default, so the app runs with no vendor and no key.
    audio_store.init_audio()
    audio_providers.bootstrap()   # adapters register here; mock is the default
    # Street Banker Studio: the project record that connects a bounce to the
    # release it becomes. Schema lands unconditionally so a migration can ship
    # one release ahead of the surface; the surface itself is behind studio_v1
    # and every route re-checks that flag.
    studio_store.init_studio()
    # Street Banker Live: the stage rig. The engine is browser code -
    # bundled at static/js/livelab.js - so the server's whole job is the
    # set, the stems and one manifest. Schema lands unconditionally;
    # the section itself is behind LIVE_LAB_ENABLED.
    live_store.init_live()
    # Slow audio work answers on the vendor's clock. /webhooks/ is already a
    # public prefix, so this endpoint carries its own signature check and is
    # 404 unless the feature and a signing secret are both configured.
    audio_webhooks.init(app)
    # The operator's window on all of the above. Owner-gated on the same
    # predicate as every other internal surface; no name lives in code.
    audio_admin.init(app, is_owner_email=_is_owner_email,
                     current_user=current_user)
    # One page answering "what can this deployment actually do", because
    # the answer was previously spread across six unrelated diagnostics
    # and 73 environment variables.
    readiness.init(app, is_owner_email=_is_owner_email,
                   current_user=current_user,
                   login_redirect=login_required_redirect,
                   context=build_dashboard_context)
    # The artist-facing lanes: dubbing, campaign audio, stems, voice vault.
    # Every lane is off until its own flag is set, and the page says so per
    # lane rather than hiding what the product does.
    audio_studio.init(app, current_user=current_user)
    # Release-Ready (owner's brief, 2026-09-19): a mix report, two free
    # previews and a paid master, through RoEx. roex_client is the only
    # module that talks to RoEx; the page is closed to artists until the
    # owner opens it in Settings.
    release_ready.init(app, current_user=current_user, notify_owners=_notify_owners,
                       is_owner_email=_is_owner_email, public_url=public_url,
                       demo_locked=_demo_locked_account)
    # Street Banker Studio. Every route re-checks studio_v1 rather than
    # trusting registration time: blueprints are module-level singletons
    # and this factory runs at import, so a flag read here would freeze.
    studio.init(app, current_user=current_user)
    live.init(app, current_user=current_user)
    # Team-Up Board: renew and thread links go into emails, so they are
    # built from the canonical address too.
    board.init(app, base_url=lambda: PUBLIC_BASE_URL, current_user=current_user)
    # Show Passport. Takes current_user and the dashboard context so a
    # passport page wears the same shell as every other internal page rather
    # than becoming a second-looking product inside the first.
    passport_os.init(app, current_user=current_user,
                     dashboard_context=build_dashboard_context)
    # Stage Control's two rooms. Same shell as everything else; the rooms
    # themselves are dark by design because they are read beside a console.
    stage_os.init(app, current_user=current_user,
                  dashboard_context=build_dashboard_context)
    import acr_desk; acr_desk.init(app, current_user=current_user, dashboard_context=build_dashboard_context, uploads_dir=lambda: UPLOADS_DIR)

    # Last, so it wraps everything above and gets the final say on the
    # headers Flask's session handling would otherwise leave in place.
    app.wsgi_app = StaticCacheHeaders(app.wsgi_app)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))

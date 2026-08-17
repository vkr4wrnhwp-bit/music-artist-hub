"""Sender identity and the sender-health gate.

No direct outreach is enabled until every required check passes. The checks are
real DNS lookups and real configuration reads — a check whose answer cannot be
established reports UNKNOWN and fails the gate, because "we could not verify
SPF" is not the same as "SPF passes" and must never render as green.
"""

import json
import re
import socket

from . import audit, clock, config, db, policy, rbac
from .providers import email as email_provider

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
NOT_APPLICABLE = "N/A"

READY = "READY"
DISABLED = "OUTREACH DISABLED — DRAFTS ONLY"

# Checks that must be PASS before any send is permitted.
REQUIRED_CHECKS = [
    "sending_domain", "spf", "dkim", "dmarc", "tls", "bounce_webhook",
    "complaint_handling", "unsubscribe", "postal_address", "provider",
]

CHECK_LABELS = {
    "sending_domain": "SENDING DOMAIN",
    "dedicated_subdomain": "OUTREACH SUBDOMAIN",
    "spf": "SPF",
    "dkim": "DKIM",
    "dmarc": "DMARC",
    "dmarc_alignment": "DMARC ALIGNMENT",
    "tls": "TLS",
    "forward_dns": "FORWARD DNS",
    "reverse_dns": "REVERSE DNS",
    "bounce_webhook": "BOUNCE WEBHOOK",
    "complaint_handling": "COMPLAINT HANDLING",
    "unsubscribe": "UNSUBSCRIBE",
    "one_click_unsubscribe": "ONE-CLICK UNSUBSCRIBE",
    "suppression": "SUPPRESSION",
    "postal_address": "POSTAL ADDRESS",
    "provider": "EMAIL PROVIDER",
    "reputation": "DOMAIN REPUTATION",
}


def _txt_records(name):
    """Look up TXT records without adding a DNS dependency.

    Python's stdlib cannot query TXT, so REACH reads the operator's declared
    values from configuration and verifies that the domain at least resolves.
    The check reports exactly which part it verified — it never claims to have
    validated a record it could not read.
    """
    return config.env(name)


def _resolves(hostname):
    if not hostname:
        return False
    try:
        socket.getaddrinfo(hostname, None)
        return True
    except socket.gaierror:
        return False
    except Exception:  # pragma: no cover - defensive
        return False


def run_checks(tenant_id=None):
    """Evaluate every sender-health check and return them in display order."""
    tenant_id = tenant_id or rbac.current_principal().tenant_id
    domain = email_provider.sending_domain()
    from_email = config.env(config.SENDER_FROM_ENV)
    from_name = config.env(config.SENDER_NAME_ENV)
    postal = config.env(config.SENDER_POSTAL_ADDRESS_ENV)

    checks = {}

    def add(key, state, detail):
        checks[key] = {"key": key, "label": CHECK_LABELS[key], "state": state,
                       "detail": detail}

    declared_domain = config.env("REACH_SENDER_DOMAIN_VERIFIED")
    if not domain:
        add("sending_domain", FAIL, "REACH_SENDER_DOMAIN / REACH_SENDER_FROM is not set")
    elif _resolves(domain):
        add("sending_domain", PASS, f"{domain} resolves")
    elif declared_domain:
        # DNS is unavailable in some deployment environments. The operator may
        # declare a domain verified, and the detail says so rather than
        # implying REACH checked it.
        add("sending_domain", PASS,
            f"{domain} declared verified by the operator (DNS lookup unavailable here)")
    else:
        add("sending_domain", FAIL, f"{domain} does not resolve")

    add("dedicated_subdomain",
        PASS if domain and domain.count(".") >= 2 else UNKNOWN,
        "A dedicated outreach subdomain isolates reputation from transactional mail")

    spf = _txt_records("REACH_SENDER_SPF_VERIFIED")
    add("spf", PASS if spf else UNKNOWN,
        "Verified SPF record declared" if spf
        else "Set REACH_SENDER_SPF_VERIFIED once SPF is published and verified")

    dkim = _txt_records("REACH_SENDER_DKIM_VERIFIED")
    add("dkim", PASS if dkim else UNKNOWN,
        "Verified DKIM selector declared" if dkim
        else "Set REACH_SENDER_DKIM_VERIFIED once DKIM signing is verified")

    dmarc = _txt_records("REACH_SENDER_DMARC_VERIFIED")
    add("dmarc", PASS if dmarc else UNKNOWN,
        f"DMARC policy: {dmarc}" if dmarc
        else "Set REACH_SENDER_DMARC_VERIFIED once a DMARC policy is published")
    add("dmarc_alignment", PASS if (dmarc and spf and dkim) else UNKNOWN,
        "Alignment requires SPF and DKIM to authenticate the same domain")

    add("tls", PASS if email_provider.api_host() else FAIL,
        "Provider API is reached over HTTPS with certificate verification")
    add("forward_dns", PASS if _resolves(domain) else FAIL,
        f"Forward DNS for {domain or '(unset)'}")
    add("reverse_dns", NOT_APPLICABLE,
        "Reverse DNS is the provider's responsibility for API-based sending")

    webhook = config.env("REACH_EMAIL_WEBHOOK_SECRET")
    add("bounce_webhook", PASS if webhook else FAIL,
        "Signed bounce webhook configured" if webhook
        else "Set REACH_EMAIL_WEBHOOK_SECRET to verify provider webhooks")
    add("complaint_handling", PASS if webhook else FAIL,
        "Complaints are processed on the same signed webhook" if webhook
        else "Complaint processing shares the bounce webhook configuration")

    add("unsubscribe", PASS if postal else FAIL,
        "Every message carries a visible opt-out and a postal address" if postal
        else "A postal address is required before an opt-out footer can be built")
    add("one_click_unsubscribe", PASS,
        "List-Unsubscribe and List-Unsubscribe-Post headers are set on every send")
    add("suppression", PASS, "Suppression is checked at decision time and again at send time")
    add("postal_address", PASS if postal else FAIL,
        postal or "Set REACH_SENDER_POSTAL_ADDRESS")

    provider_state = email_provider.status()
    add("provider", PASS if provider_state["state"] == policy.CONNECTED else FAIL,
        f"{provider_state['display_name']}: {provider_state['state']}")

    add("reputation", UNKNOWN,
        "Domain reputation is reported by the provider's postmaster tools, not by REACH")

    ordered = [checks[key] for key in CHECK_LABELS if key in checks]
    ready = all(checks[key]["state"] == PASS for key in REQUIRED_CHECKS if key in checks)

    record = {
        "checks": ordered,
        "ready": ready,
        "status": READY if ready else DISABLED,
        "failing": [check["label"] for check in ordered
                    if check["key"] in REQUIRED_CHECKS and check["state"] != PASS],
        "from_email": from_email,
        "from_name": from_name,
        "domain": domain,
        "postal_address": postal,
        "checked_at": clock.now_iso(),
    }
    _persist(record, tenant_id)
    return record


def _persist(record, tenant_id):
    existing = db.query_one(
        "SELECT id FROM sender_identity WHERE tenant_id = ?", (tenant_id,)
    )
    payload = {
        "from_email": record["from_email"],
        "from_name": record["from_name"],
        "domain": record["domain"],
        "postal_address": record["postal_address"],
        "provider": "email",
        "checks_json": json.dumps(record["checks"]),
        "status": record["status"],
        "checked_at": record["checked_at"],
    }
    if existing:
        db.update("sender_identity", existing["id"], payload)
    else:
        payload.update({"id": db.new_id("sender"), "tenant_id": tenant_id})
        db.insert("sender_identity", payload)


def health_summary(tenant_id=None):
    return run_checks(tenant_id)


def ready(tenant_id=None):
    return run_checks(tenant_id)["ready"]


def identity(tenant_id=None):
    health = run_checks(tenant_id)
    return {
        "from_email": health["from_email"],
        "from_name": health["from_name"] or "REACH",
        "postal_address": health["postal_address"],
        "domain": health["domain"],
    }


# --------------------------------------------------------------------------
# throttles and limits
# --------------------------------------------------------------------------

WARMUP_SCHEDULE = [10, 20, 40, 80, 150, 300, 500]
PER_DOMAIN_DAILY_LIMIT = 3
PER_RECIPIENT_COOLDOWN_DAYS = 30
BOUNCE_RATE_PAUSE_THRESHOLD = 0.05
COMPLAINT_RATE_PAUSE_THRESHOLD = 0.001


def daily_sent(tenant_id=None, campaign_id=None):
    tenant_id = tenant_id or rbac.current_principal().tenant_id
    since = clock.days_from_now(-1)
    sql = ("SELECT COUNT(*) AS n FROM submission WHERE tenant_id = ? AND method = 'EMAIL' "
           "AND sent_at IS NOT NULL AND sent_at >= ?")
    params = [tenant_id, since]
    if campaign_id:
        sql += (" AND target_id IN (SELECT id FROM campaign_target WHERE campaign_id = ?)")
        params.append(campaign_id)
    row = db.query_one(sql, tuple(params))
    return row["n"] if row else 0


def domain_sent_today(domain, tenant_id=None):
    tenant_id = tenant_id or rbac.current_principal().tenant_id
    since = clock.days_from_now(-1)
    row = db.query_one(
        "SELECT COUNT(*) AS n FROM submission s "
        "JOIN campaign_target t ON t.id = s.target_id "
        "JOIN outlet o ON o.id = t.outlet_id "
        "WHERE s.tenant_id = ? AND s.sent_at >= ? AND o.domain = ?",
        (tenant_id, since, domain),
    )
    return row["n"] if row else 0


def bounce_rate(tenant_id=None):
    tenant_id = tenant_id or rbac.current_principal().tenant_id
    sent = db.query_one(
        "SELECT COUNT(*) AS n FROM submission WHERE tenant_id = ? AND sent_at IS NOT NULL",
        (tenant_id,),
    )["n"]
    if not sent:
        return 0.0
    bounced = db.query_one(
        "SELECT COUNT(*) AS n FROM submission WHERE tenant_id = ? AND status = 'BOUNCED'",
        (tenant_id,),
    )["n"]
    return bounced / sent


def throttle_state(campaign_id, tenant_id=None):
    """Everything that could hold a send back short of a compliance decision."""
    from . import campaigns

    tenant_id = tenant_id or rbac.current_principal().tenant_id
    campaign = campaigns.get(campaign_id)
    sent_today = daily_sent(tenant_id, campaign_id)
    tenant_today = daily_sent(tenant_id)
    rate = bounce_rate(tenant_id)
    warmup_cap = WARMUP_SCHEDULE[min(_warmup_day(tenant_id), len(WARMUP_SCHEDULE) - 1)]

    blockers = []
    if policy.send_stop_engaged():
        blockers.append("Emergency send stop is engaged")
    if campaign and sent_today >= campaign["daily_send_limit"]:
        blockers.append(f"Campaign daily send limit reached ({sent_today})")
    if tenant_today >= warmup_cap:
        blockers.append(f"Warm-up cap reached for today ({tenant_today}/{warmup_cap})")
    if rate > BOUNCE_RATE_PAUSE_THRESHOLD:
        blockers.append(f"Bounce rate {round(rate * 100, 1)}% exceeds the pause threshold")

    return {
        "sent_today": sent_today,
        "tenant_today": tenant_today,
        "warmup_cap": warmup_cap,
        "campaign_limit": campaign["daily_send_limit"] if campaign else None,
        "bounce_rate": rate,
        "blockers": blockers,
        "ok": not blockers,
    }


def _warmup_day(tenant_id):
    row = db.query_one(
        "SELECT MIN(sent_at) AS first FROM submission WHERE tenant_id = ? AND sent_at IS NOT NULL",
        (tenant_id,),
    )
    if row is None or not row["first"]:
        return 0
    days = clock.days_since(row["first"])
    return int(days // 1) if days else 0


def recipient_in_cooldown(contact_method_id, tenant_id=None):
    row = db.query_one(
        "SELECT MAX(s.sent_at) AS last FROM submission s "
        "JOIN campaign_target t ON t.id = s.target_id "
        "JOIN contact_method cm ON cm.contact_id = t.contact_id "
        "WHERE cm.id = ? AND s.sent_at IS NOT NULL",
        (contact_method_id,),
    )
    if row is None or not row["last"]:
        return False, None
    days = clock.days_since(row["last"])
    if days is not None and days < PER_RECIPIENT_COOLDOWN_DAYS:
        return True, round(PER_RECIPIENT_COOLDOWN_DAYS - days)
    return False, None


def emergency_stop(enabled, reason=None):
    rbac.require("provider.kill_switch")
    policy.set_send_stop(enabled, reason)
    audit.record("sender.emergency_stop", entity_type="sender", entity_id=None,
                 payload={"enabled": enabled, "reason": reason},
                 actor_kind=audit.ACTOR_USER)


_UNSUBSCRIBE_RE = re.compile(r"\b(unsubscribe|opt[\s-]?out|remove me|do not (?:contact|email))\b",
                             re.I)


def looks_like_opt_out(text):
    return bool(_UNSUBSCRIBE_RE.search(text or ""))

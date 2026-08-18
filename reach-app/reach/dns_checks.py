"""Real DNS lookups for sender authentication.

Until now SPF, DKIM and DMARC were *operator-declared*: REACH could not query
TXT records with the standard library, so it read a variable saying "I checked
this myself". That is a weak link in a gate whose whole purpose is to refuse to
show green for something unverified.

This module performs the lookups. The three states it returns are deliberately
distinct:

* ``FOUND``      — the record exists and REACH read it
* ``ABSENT``     — the lookup succeeded and the record is genuinely not there
* ``UNRESOLVED`` — the lookup itself failed (no resolver, timeout, SERVFAIL)

``ABSENT`` and ``UNRESOLVED`` both fail the sender-health gate, but they are
never conflated: one means "you have not published this", the other means
"REACH could not find out", and the operator needs to tell them apart.
"""

import threading
import time

try:
    import dns.exception
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:  # pragma: no cover - dnspython is in requirements.txt
    DNS_AVAILABLE = False

FOUND = "FOUND"
ABSENT = "ABSENT"
UNRESOLVED = "UNRESOLVED"

TIMEOUT_SECONDS = 5.0
CACHE_TTL_SECONDS = 300

_cache = {}
_lock = threading.Lock()

# Tests and offline environments install their own resolver here rather than
# reaching the network. A resolver is a callable (name, rdtype) -> Lookup.
_resolver_override = None


def set_resolver(resolver):
    """Install a resolver. Pass None to restore real DNS."""
    global _resolver_override
    _resolver_override = resolver
    clear_cache()


def offline_resolver(records=None):
    """A resolver backed by a dict of {(name, rdtype): [values]}.

    Anything not in the dict resolves as ABSENT — the honest answer for "this
    name exists in DNS but publishes no such record".
    """
    table = {(name.lower(), rdtype): values for (name, rdtype), values in (records or {}).items()}

    def resolve(name, rdtype):
        values = table.get((name.lower(), rdtype))
        if values is None:
            return Lookup(ABSENT, name=name, rdtype=rdtype,
                          detail=f"No {rdtype} record published at {name}")
        return Lookup(FOUND, records=list(values), name=name, rdtype=rdtype,
                      detail=f"{len(values)} {rdtype} record(s) at {name}")

    return resolve


class Lookup:
    """One DNS answer, with enough context to render an honest detail line."""

    __slots__ = ("state", "records", "detail", "name", "rdtype")

    def __init__(self, state, records=None, detail="", name="", rdtype=""):
        self.state = state
        self.records = records or []
        self.detail = detail
        self.name = name
        self.rdtype = rdtype

    @property
    def found(self):
        return self.state == FOUND

    @property
    def first(self):
        return self.records[0] if self.records else None

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"Lookup({self.state}, {self.name} {self.rdtype}, {len(self.records)} records)"


def clear_cache():
    with _lock:
        _cache.clear()


def _cached(key):
    with _lock:
        entry = _cache.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if time.monotonic() > expires_at:
        with _lock:
            _cache.pop(key, None)
        return None
    return value


def _store(key, value):
    with _lock:
        _cache[key] = (time.monotonic() + CACHE_TTL_SECONDS, value)
    return value


def query(name, rdtype):
    """Resolve one record set. Never raises — the failure is the answer."""
    if not name:
        return Lookup(UNRESOLVED, detail="No domain configured", name=name, rdtype=rdtype)
    if not DNS_AVAILABLE and _resolver_override is None:
        return Lookup(UNRESOLVED, name=name, rdtype=rdtype,
                      detail="dnspython is not installed, so REACH cannot verify this record")

    key = (name.lower(), rdtype)
    cached = _cached(key)
    if cached is not None:
        return cached

    if _resolver_override is not None:
        return _store(key, _resolver_override(name, rdtype))

    resolver = dns.resolver.Resolver()
    resolver.timeout = TIMEOUT_SECONDS
    resolver.lifetime = TIMEOUT_SECONDS

    try:
        answer = resolver.resolve(name, rdtype)
    except dns.resolver.NXDOMAIN:
        return _store(key, Lookup(ABSENT, name=name, rdtype=rdtype,
                                  detail=f"{name} does not exist"))
    except dns.resolver.NoAnswer:
        return _store(key, Lookup(ABSENT, name=name, rdtype=rdtype,
                                  detail=f"No {rdtype} record published at {name}"))
    except dns.exception.Timeout:
        return _store(key, Lookup(UNRESOLVED, name=name, rdtype=rdtype,
                                  detail=f"DNS timed out resolving {name}"))
    except Exception as exc:
        return _store(key, Lookup(UNRESOLVED, name=name, rdtype=rdtype,
                                  detail=f"DNS lookup failed for {name}: {exc}"))

    records = [_render(rdata, rdtype) for rdata in answer]
    return _store(key, Lookup(FOUND, records=records, name=name, rdtype=rdtype,
                              detail=f"{len(records)} {rdtype} record(s) at {name}"))


def _render(rdata, rdtype):
    if rdtype == "TXT":
        # A TXT record arrives as one or more chunks that must be concatenated.
        return "".join(
            part.decode("utf-8", errors="replace") if isinstance(part, bytes) else str(part)
            for part in rdata.strings
        )
    if rdtype == "MX":
        return f"{rdata.preference} {rdata.exchange.to_text()}"
    return rdata.to_text()


# --------------------------------------------------------------------------
# sender authentication records
# --------------------------------------------------------------------------

def spf(domain):
    """SPF lives in a TXT record at the domain itself, starting ``v=spf1``."""
    lookup = query(domain, "TXT")
    if not lookup.found:
        return lookup
    matches = [record for record in lookup.records
               if record.strip().lower().startswith("v=spf1")]
    if not matches:
        return Lookup(ABSENT, name=domain, rdtype="TXT",
                      detail=f"{domain} publishes TXT records but none is an SPF policy")
    return Lookup(FOUND, records=matches, name=domain, rdtype="TXT",
                  detail=matches[0][:160])


def dkim(domain, selector):
    """DKIM lives at ``<selector>._domainkey.<domain>``."""
    if not selector:
        return Lookup(UNRESOLVED, name=domain, rdtype="TXT",
                      detail="No DKIM selector configured — set REACH_SENDER_DKIM_SELECTOR")
    name = f"{selector}._domainkey.{domain}"
    lookup = query(name, "TXT")
    if not lookup.found:
        return lookup
    matches = [record for record in lookup.records if "p=" in record]
    if not matches:
        return Lookup(ABSENT, name=name, rdtype="TXT",
                      detail=f"{name} exists but publishes no DKIM public key")
    return Lookup(FOUND, records=matches, name=name, rdtype="TXT",
                  detail=f"DKIM key published at {name}")


def dmarc(domain):
    """DMARC lives at ``_dmarc.<domain>``, starting ``v=DMARC1``."""
    name = f"_dmarc.{domain}"
    lookup = query(name, "TXT")
    if not lookup.found:
        return lookup
    matches = [record for record in lookup.records
               if record.strip().lower().startswith("v=dmarc1")]
    if not matches:
        return Lookup(ABSENT, name=name, rdtype="TXT",
                      detail=f"{name} exists but publishes no DMARC policy")
    return Lookup(FOUND, records=matches, name=name, rdtype="TXT",
                  detail=matches[0][:160])


def dmarc_policy(domain):
    """The ``p=`` value, or None. ``p=none`` is published but not enforcing."""
    lookup = dmarc(domain)
    if not lookup.found:
        return None
    for part in lookup.first.split(";"):
        key, _, value = part.strip().partition("=")
        if key.strip().lower() == "p":
            return value.strip().lower()
    return None


def mx(domain):
    """Mail exchangers for a recipient domain. Used for non-intrusive contact
    validation — REACH never probes a mailbox with an SMTP callback."""
    lookup = query(domain, "MX")
    if lookup.found:
        return lookup
    if lookup.state == ABSENT:
        # RFC 5321: a domain with an A record but no MX still accepts mail.
        fallback = query(domain, "A")
        if fallback.found:
            return Lookup(FOUND, records=fallback.records, name=domain, rdtype="A",
                          detail=f"No MX record; {domain} has an A record and may "
                                 "still accept mail")
    return lookup

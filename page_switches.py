"""Every page live or hidden, from the owner's Settings, without a deploy.

Owner, 2026-09-14: "can we do the toggles for the live version on
features not just read only?? but like hidden or live?" A hidden page
leaves the sidebar, the command palette and the desk landings for
everybody who is not an owner, and its address bounces them to the
Command Center with a note. Owners keep seeing it, badged Hidden, so a
page can be checked on the live site before it is switched on.

Same shape as the homepage editor: the shipped sidebar (hubs.py) is the
default and one saved override sits on top, so an empty override is
exactly the product that ships and "show everything again" is deleting
a key. The Command Center and Settings can never be hidden - the shell
needs a home, and the owner needs the switch itself.
"""
import json

import db as store
import hubs

KV_KEY = "page_switches"
PROTECTED = frozenset({"command-center", "settings"})


def entries():
    """Every sidebar entry as (hub name, key, href, label), in sidebar
    order, hubs first then the three groups."""
    out = []
    for _hkey, name, _tag, items in hubs.nav_hubs():
        for key, href, _icon, label, _desc in items:
            out.append((name, key, href, label))
    for gname, items in (hubs.LABEL_GROUP, hubs.COMMUNITY_GROUP, hubs.ACCOUNT_GROUP):
        for key, href, _icon, label, _desc in items:
            out.append((gname, key, href, label))
    return out


def known_keys():
    return {key for _n, key, _h, _l in entries()}


def hidden_keys():
    """The keys switched off. A corrupt or missing override hides nothing."""
    try:
        raw = store.get_kv(KV_KEY)
    except Exception:
        return set()
    if not raw:
        return set()
    try:
        loaded = json.loads(raw)
    except (TypeError, ValueError):
        return set()
    keys = loaded.get("hidden") if isinstance(loaded, dict) else None
    if not isinstance(keys, list):
        return set()
    return {k for k in keys if isinstance(k, str)} - PROTECTED


def set_hidden(keys):
    """Save the hidden set: only keys the sidebar knows, never the
    protected two. Returns what was saved."""
    keep = sorted((set(keys) & known_keys()) - PROTECTED)
    store.set_kv(KV_KEY, json.dumps({"hidden": keep}) if keep else "")
    return set(keep)


def is_external(href):
    return href.startswith(("http://", "https://"))


def hidden_for_path(path, hidden=None):
    """The hidden entry a request path falls under - the entry whose
    address is the LONGEST prefix of the path - or None. /links/fans is
    /links's; /royalty-recovery/cases is its own entry, not /royalties'."""
    hidden = hidden_keys() if hidden is None else hidden
    if not hidden:
        return None
    path = (path or "/").rstrip("/") or "/"
    best = None
    for _n, key, href, label in entries():
        if is_external(href):
            continue
        h = href.rstrip("/") or "/"
        if h == "/":
            continue
        if path == h or path.startswith(h + "/"):
            if best is None or len(h) > len(best[0]):
                best = (h, key, label)
    if best and best[1] in hidden:
        return {"key": best[1], "label": best[2]}
    return None

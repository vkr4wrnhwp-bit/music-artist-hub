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
import urllib.parse

import db as store
import hubs

KV_KEY = "page_switches"
PROTECTED = frozenset({"command-center", "settings"})


def entries():
    """Every switchable page as (hub name, key, href, label): the sidebar
    entries in sidebar order, hubs first then the three groups, and after
    each one the room cards that unfolded from it (see _unfolded)."""
    out = []
    for _hkey, name, _tag, items in hubs.nav_hubs():
        for key, href, _icon, label, _desc in items:
            out.append((name, key, href, label))
    for gname, items in (hubs.LABEL_GROUP, hubs.COMMUNITY_GROUP, hubs.ACCOUNT_GROUP):
        for key, href, _icon, label, _desc in items:
            out.append((gname, key, href, label))
    return _unfolded(out)


def _unfolded(out):
    """A room card that is not a sidebar entry (rooms.EXTRA: Fan Club, Tax,
    Contracts, Track Passports, the two release views...) gets a switch of
    its own, so the owner can hide THAT page and not the one it unfolded
    from. It sits right after its parent's row, under the parent's hub; a
    card with no parent (Distribution) closes the hub its room's sidebar
    entries are under. A page in no room (Signal, the three folded press
    pages, Connections) is not a switch: it still follows its parent
    through rooms.hidden_keys(). Owner, 2026-09-23."""
    import rooms  # rooms imports this module; the loop is broken here
    hub_of = {key: name for name, key, _h, _l in out}
    under, closing = {}, {}  # parent key -> rows; hub name -> rows
    for room in rooms.ROOMS:
        keys = room[3]
        room_hub = next((hub_of[k] for k in keys if k in hub_of), None)
        for key in keys:
            if key in hub_of or key not in rooms.EXTRA:
                continue
            href, _icon, label, _desc, parent = rooms.EXTRA[key]
            if parent in hub_of:
                hub = hub_of[parent]
                under.setdefault(parent, []).append((hub, key, href, label))
            elif room_hub:
                hub = room_hub
                closing.setdefault(hub, []).append((hub, key, href, label))
            else:
                continue
            hub_of[key] = hub
    rows = []
    for i, row in enumerate(out):
        rows.append(row)
        rows.extend(under.get(row[1], ()))
        if i + 1 == len(out) or out[i + 1][0] != row[0]:
            rows.extend(closing.pop(row[0], ()))
    return rows


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
    # A suite reached through the sign-in hand-off (/suites/go/<key>) lands on
    # another service after one redirect, so it is external like a full URL.
    return href.startswith(("http://", "https://", "/suites/go/"))


def hidden_for_path(path, hidden=None, args=None):
    """The hidden entry a request falls under - the entry whose address
    is the LONGEST prefix of the path - or None. /links/fans is /links's;
    /royalty-recovery/cases is its own entry, not /royalties'.

    A VIEW of a page that is a switch of its own (/statements?view=tax is
    Tax) is the hit only when the request asks for that view, by `args`
    (request.args); hiding Tax leaves /statements open, and hiding
    Statements still takes its views with it by the plain address."""
    hidden = hidden_keys() if hidden is None else hidden
    if not hidden:
        return None
    path = (path or "/").rstrip("/") or "/"
    if args:
        for _n, key, href, label in entries():
            if "?" not in href or key not in hidden:
                continue
            h, _q, query = href.partition("?")
            if (h.rstrip("/") or "/") != path:
                continue
            want = urllib.parse.parse_qs(query)
            if all(args.get(k) in v for k, v in want.items()):
                return {"key": key, "label": label}
    # The longest HIDDEN address the path falls under. A live entry nearer
    # the path does not shelter it: /links/fans is Fan CRM's own switch
    # now, but hiding Smart Links still takes everything under /links.
    best = None
    for _n, key, href, label in entries():
        if is_external(href) or "?" in href or key not in hidden:
            continue
        h = href.rstrip("/") or "/"
        if h == "/":
            continue
        if path == h or path.startswith(h + "/"):
            if best is None or len(h) > len(best[0]):
                best = (h, key, label)
    if best:
        return {"key": best[1], "label": best[2]}
    return None

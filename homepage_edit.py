"""The homepage, editable by its owner without a deploy.

The page is already config-driven: landing_config returns a dict and the
template renders it. The only reason changing a headline needed an
engineer is that the dict lives in Python source.

So the Python config stays as the DEFAULT and a saved override sits on
top of it. Three things follow, and they are the reason for this shape
rather than moving the copy into the database outright:

  - an empty override renders exactly the page that ships today, so
    nothing can be broken by the feature merely existing;
  - "reset to default" is deleting a key, not restoring a backup;
  - the defaults stay in git, so there is always a known-good state to
    fall back to and a diff that explains what changed.

WHAT THIS DELIBERATELY DOES NOT DO

Layout. Editing what the hero says is a form; letting somebody rearrange
sections is a page builder, and it would walk straight into the design
locks - the type scale, the radius tokens, the colour ramp. Text and
links only.

THE HONEST COST

This is the one surface in the product where something wrong can reach
the public without a green test run first. The validators below refuse a
link that goes nowhere and copy that claims a deployment state, because
those are checkable. Whether a sentence is TRUE is not checkable here,
and this module does not pretend otherwise.
"""
import copy
import json

import db as store

KV_KEY = "landing_override"

# Phrases a static string must not contain, because a fixed sentence
# cannot know whether a flag-gated engine is on today. Same list the hub
# honesty test enforces; imported from here so there is one copy.
STATE_CLAIMS = ("preview today", "coming soon", "not connected",
                "not yet built")


def route_resolver(app):
    """Does this path match a real route? Returns a predicate.

    The navigation test needs exactly this and had it inline. A second
    copy here would drift from that one silently, and the whole point of
    validating a link at save time is that it agrees with the check that
    guards the rest of the app.
    """
    import re

    rules = {str(r) for r in app.url_map.iter_rules()}
    patterned = [r for r in rules if "<" in r]

    def resolves(path):
        path = (path or "").strip()
        if not path:
            return False
        # An anchor or an off-site link is not this app's route to own.
        if path.startswith(("#", "http://", "https://", "mailto:", "tel:")):
            return True
        if path.startswith("/#"):
            return True
        if path.startswith(("/static/", "/uploads/")):
            return True
        bare = path.split("?")[0].split("#")[0]
        if bare in rules or bare.rstrip("/") in rules:
            return True
        return any(re.match("^" + re.sub(r"<[^>]+>", "[^/]+", rule) + "$", bare)
                   for rule in patterned)

    return resolves


def check(fields, resolves):
    """Every reason this draft cannot be published, in the owner's words.

    Returns a list of strings. Empty means it is publishable - which is
    not the same as true, and the caller must not read it as such.
    """
    problems = []
    for label, value in fields.get("_links", []):
        if not resolves(value):
            problems.append(
                "“%s” points at %s, which is not a page on this site. A link "
                "that goes nowhere is worse than no link." % (label, value))
    for label, value in fields.get("_text", []):
        lowered = (value or "").lower()
        for claim in STATE_CLAIMS:
            if claim in lowered:
                problems.append(
                    "“%s” says “%s”. A fixed sentence cannot know whether "
                    "something is switched on today, and this one will still "
                    "be saying it after it is." % (label, claim))
    return problems


# --- the override ------------------------------------------------------------

def _deep_merge(base, over):
    """Override wins, key by key, leaving anything it does not mention.

    A whole-dict replace would mean an override written today freezes
    every field it happens to include - so a later default improvement
    would never reach a page that had been edited once.
    """
    out = copy.deepcopy(base)
    for key, value in (over or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def read_override():
    try:
        raw = store.get_kv(KV_KEY)
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except (TypeError, ValueError):
        # A corrupt override must not take the homepage down. The page
        # falls back to what ships, which is always renderable.
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_override(data):
    store.set_kv(KV_KEY, json.dumps(data or {}))


def clear_override():
    store.set_kv(KV_KEY, "")


def apply_override(config):
    """The shipped config with whatever the owner has saved on top."""
    over = read_override()
    return _deep_merge(config, over) if over else config


def is_edited():
    return bool(read_override())

"""Progressive disclosure — which modules a simple-mode account can see.

Data, not conditionals. Every threshold is a name at the top of this file
and every gated module is one row in MODULES, so tuning the system means
editing this file and nothing else. No feature code asks "is this user
new"; it asks this table.

Three rules the design rests on:

  Only listed modules are gated. Anything absent from MODULES is always
  visible. The default is showing a feature, not hiding it — a mistake
  here should mean somebody sees a module early, never that a module
  silently disappears.

  Unlocks latch. Once a key is opened for an account it stays open, even
  if the count later falls or the scheduled release comes and goes.
  Losing a feature you had started using is worse than never having been
  shown it.

  A trigger must be reachable from simple mode. If uploading a statement
  unlocks the Royalty Sweep, then the statements page cannot itself be
  behind the Royalty Sweep, or the account can never escape. That is a
  circular lock, and test_unlocks.py fails the build if one is ever
  introduced.
"""

# --- the tunable numbers ----------------------------------------------------
# These are the whole configuration surface. Change one and the system
# changes; no feature code reads a literal.

FAN_INTELLIGENCE_VISITS = 25     # smart-link visits before the audience opens
SWEEP_RELEASES = 3               # releases that open the sweep without a statement
PARTNERSHIP_RELEASES = 5         # releases before partnership tooling opens
ROLLOUT_LEAD_DAYS = 14           # days ahead a release must be scheduled


# --- milestone names --------------------------------------------------------
# Booleans that latch the moment something happens.
FLAGS = (
    "first_release_completed",
    "smart_link_created",
    "statement_uploaded",
    "second_contributor_added",
    "release_scheduled_2wk_out",
)
# Running totals.
COUNTERS = (
    "releases_count",
    "smart_link_visit_count",
)


# --- rule constructors ------------------------------------------------------
# A rule is a plain dict so it stays inspectable and testable without an
# app or a database anywhere near it.

def flag(name):
    return {"kind": "flag", "flag": name}


def at_least(counter, n):
    return {"kind": "count", "counter": counter, "n": n}


def either(*rules):
    return {"kind": "either", "rules": list(rules)}


# --- what gates what --------------------------------------------------------
# key -> (rule, the one line shown on the locked module)
#
# The keys are hubs.py module keys. The hint is written to tell somebody
# what to go and do, not to tell them they are not allowed.

MODULES = {
    # Fan Intelligence. The audience page is the only one gated on it:
    # /fans and /stats stay open so an account is not blind to its own
    # numbers while it waits.
    "audience": (
        at_least("smart_link_visit_count", FAN_INTELLIGENCE_VISITS),
        "Unlocks when your smart links reach %d visits" % FAN_INTELLIGENCE_VISITS,
    ),

    # Rights, full depth. Conflict and dispute tooling only means anything
    # once a second name is on a track — which is exactly the trigger.
    # Track Passports, Documents and Identifiers stay open: a solo artist
    # has rights and paperwork too.
    "conflicts": (
        flag("second_contributor_added"),
        "Unlocks when a second contributor is added to a track",
    ),
    "disputes": (
        flag("second_contributor_added"),
        "Unlocks when a second contributor is added to a track",
    ),

    # Royalty Sweep. Statements is deliberately NOT here — it is the way
    # in. Neither is Connections, which is how statements start arriving.
    "overview": (
        either(flag("statement_uploaded"),
               at_least("releases_count", SWEEP_RELEASES)),
        "Unlocks when you upload a royalty statement, or after %d releases"
        % SWEEP_RELEASES,
    ),
    "royalties": (
        either(flag("statement_uploaded"),
               at_least("releases_count", SWEEP_RELEASES)),
        "Unlocks when you upload a royalty statement, or after %d releases"
        % SWEEP_RELEASES,
    ),
    "recovery": (
        either(flag("statement_uploaded"),
               at_least("releases_count", SWEEP_RELEASES)),
        "Unlocks when you upload a royalty statement, or after %d releases"
        % SWEEP_RELEASES,
    ),
    "royalty-lanes": (
        either(flag("statement_uploaded"),
               at_least("releases_count", SWEEP_RELEASES)),
        "Unlocks when you upload a royalty statement, or after %d releases"
        % SWEEP_RELEASES,
    ),
    "money-queue": (
        either(flag("statement_uploaded"),
               at_least("releases_count", SWEEP_RELEASES)),
        "Unlocks when you upload a royalty statement, or after %d releases"
        % SWEEP_RELEASES,
    ),

    # Rollout Engine. A rollout plan is only useful with runway in front
    # of it, so the trigger is the runway.
    "rollout": (
        flag("release_scheduled_2wk_out"),
        "Unlocks when you schedule a release %d or more days ahead"
        % ROLLOUT_LEAD_DAYS,
    ),

    # Partnership and capital tooling. A deal conversation needs a
    # catalog behind it.
    "deal-room": (
        at_least("releases_count", PARTNERSHIP_RELEASES),
        "Unlocks after %d releases" % PARTNERSHIP_RELEASES,
    ),
    "deal-simulator": (
        at_least("releases_count", PARTNERSHIP_RELEASES),
        "Unlocks after %d releases" % PARTNERSHIP_RELEASES,
    ),
    "capital": (
        at_least("releases_count", PARTNERSHIP_RELEASES),
        "Unlocks after %d releases" % PARTNERSHIP_RELEASES,
    ),
    "funding": (
        at_least("releases_count", PARTNERSHIP_RELEASES),
        "Unlocks after %d releases" % PARTNERSHIP_RELEASES,
    ),
}

# Modules named in the brief as never gated. Listed explicitly rather
# than left implicit, so the invariant test can prove they are reachable
# and so nobody adds them to MODULES by accident later.
ALWAYS_VISIBLE = (
    "releases", "autopilot", "clean-release",   # the release workspace
    "artwork",                                  # Creative Studio
    "links",                                    # Smart Links
    "statements",                               # the way into the sweep
    "connections",                              # how statements start arriving
    "tracks",                                   # where contributors are added
    "command-center", "actions", "settings", "notifications", "billing",
)

# What each trigger needs the account to be able to REACH. The invariant
# test walks this: if a module here ever appears in MODULES, the account
# could never satisfy the rule that opens it.
TRIGGER_ROUTES = {
    "smart_link_visit_count": "links",
    "statement_uploaded": "statements",
    "releases_count": "releases",
    "release_scheduled_2wk_out": "releases",
    "second_contributor_added": "tracks",
    "smart_link_created": "links",
    "first_release_completed": "releases",
}


# --- evaluation -------------------------------------------------------------

def _met(rule, flags, counters):
    kind = rule["kind"]
    if kind == "flag":
        return bool(flags.get(rule["flag"]))
    if kind == "count":
        return int(counters.get(rule["counter"]) or 0) >= rule["n"]
    if kind == "either":
        return any(_met(r, flags, counters) for r in rule["rules"])
    raise ValueError("unknown rule kind: %r" % kind)


def unlocked_keys(flags, counters):
    """Every gated key this account's milestones currently satisfy.

    Pure: takes two dicts, returns a set, touches no database. The
    latching lives in unlock_store, which unions this with whatever was
    already open.
    """
    return {key for key, (rule, _hint) in MODULES.items()
            if _met(rule, flags or {}, counters or {})}


# Modules that open together belong to one group, and the account is told
# once. Uploading a statement opens five money modules; five separate
# banners about one action is noise, and noise is what gets dismissed
# without being read.
GROUP = {
    "audience": "fan-intelligence",
    "conflicts": "rights-depth",
    "disputes": "rights-depth",
    "overview": "royalty-sweep",
    "royalties": "royalty-sweep",
    "recovery": "royalty-sweep",
    "royalty-lanes": "royalty-sweep",
    "money-queue": "royalty-sweep",
    "rollout": "rollout",
    "deal-room": "partnership",
    "deal-simulator": "partnership",
    "capital": "partnership",
    "funding": "partnership",
}

# What the account is told at the moment a group opens. Written as news
# about their own work rather than as a reward: the thing that changed is
# something they did, and the sentence should say what to go and look at.
OPENED = {
    "fan-intelligence":
        "Your smart links passed %d visits — Audience is open. "
        "See who is listening, and where." % FAN_INTELLIGENCE_VISITS,
    "rights-depth":
        "A second name is on a track — Rights Conflicts and Disputes are open.",
    "royalty-sweep":
        "Your Royalty Sweep is open — Overview, Royalties, Recovery, "
        "Royalty Lanes and the Money Queue.",
    "rollout":
        "You have a release with runway — Rollout Engine is open.",
    "partnership":
        "Deal Room, Deal Simulator, Capital and Funding are open.",
}


def group_of(key):
    return GROUP.get(key, key)


def opened_copy(group):
    return OPENED.get(group) or "Something new is open."


def hint(key):
    entry = MODULES.get(key)
    return entry[1] if entry else ""


def is_gated(key):
    return key in MODULES


def gated_keys():
    return set(MODULES)

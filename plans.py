"""Street Banker plan tiers and product worlds.

Owner, 2026-09-17: Artist is Street Banker with Royalty Sweep and
Artifacts; Pro adds REACH, Tour and Company; Label opens everything and
carries monthly credits. The Room, Noise Lab and Motion cost money every
time they run, so they run on credits, "just like Suno does": one wallet,
packs any membership can buy, included credits that lapse each month and
bought credits that never do. Pages above your tier render an upgrade card.
"""

TIER_RANK = {"fan": 0, "artist": 1, "pro": 2, "label": 3}

PLANS = [
    ("fan", "Fan", "Free", "Discover music, follow artists, collect moments.",
     ["Discover & Network", "Fan Dashboard", "Mintable Moments", "Marketplace"]),
    ("artist", "Artist", "$29/mo", "Street Banker, Royalty Sweep and Artifacts.",
     ["Street Banker: links, rollouts, press kit, fan tools",
      "Royalty Sweep: statements, recovery, catalog, valuation",
      "Artifacts (coming soon)"]),
    ("pro", "Pro", "$79/mo", "Everything in Artist plus REACH, Tour and Company.",
     ["REACH", "Tour", "Company (coming soon)",
      # Owner, 2026-09-18, replacing "Consulting hours (with ambassadors)",
      # which nothing stood behind.
      # "At a member rate" read as a discount (owner, 2026-09-19: remove any
      # suggestion of a discount). The prices are the prices.
      "Consulting with the founder: $50 for 30 minutes, $75 for an hour"]),
    ("label", "Label", "$199/mo", "Everything, with credits included every month.",
     ["The Room and Motion", "Noise Lab (coming soon)", "Credits included every month",
      "Roster seats and team permissions", "Partner reports"]),
]
PLAN_NAMES = {key: name for key, name, _, _, _ in PLANS}

# Product worlds shown in the sidebar switcher: (key, label, home, min tier or None)
WORLDS = [
    ("promote", "Promote", "/links", "artist"),
    ("sweep", "Royalty Sweep", "/overview", "artist"),
    ("label", "Label Services", "/services", None),
    ("fan", "Fan Side", "/discover", None),
]

# Path-prefix tier gates. Public pages (/l/, /epk/<slug>, uploads, auth)
# are never listed here, so they stay open.
_ARTIST_PATHS = ("/live", "/links", "/rollout-studio", "/artwork", "/command-center",
                 "/actions", "/releases", "/audience", "/playlists", "/stats",
                 "/insights", "/benchmark", "/pulse", "/metadata-passport",
                 "/fan-club", "/tour", "/stage-plot", "/rack", "/lights", "/tracks", "/certified",
                 # The rest of the mix-station family. /rack and /vault were
                 # artist-tier and these two were not, so the same journey -
                 # upload a master, work on it, keep the result - changed tier
                 # halfway through depending on which door you came in by.
                 "/beats", "/audio-studio",
                 # Release-Ready spends the owner's RoEx credits; the public
                 # /creative-studio explainer (an exact match) stays open.
                 "/creative-studio/release-ready",
                 "/qualification", "/artist-profile",
                 "/vault", "/artist-twin", "/trust-score")
# /fingerprints is here beside /recovery deliberately. It had no entry at
# all, so required_tier() returned None for it and a free Fan account could
# open the desk that spends the owner's ACRCloud quota.
_PRO_PATHS = ("/overview", "/royalties", "/statements", "/recovery", "/disputes",
              "/fingerprints",
              "/publishing", "/mechanicals", "/neighboring-rights", "/territories",
              "/connections", "/catalog", "/identifiers", "/documents",
              "/conflicts", "/registration", "/valuation", "/funding", "/sync",
              "/tax", "/reports", "/royalty-recovery", "/deal-room", "/onesheet",
              "/revenue-os",
              "/capital-score", "/spend-optimizer", "/royalty-lanes",
              "/money-queue")


def _matches(path, prefixes):
    return any(path == p or path.startswith(p + "/") for p in prefixes)


def required_tier(path):
    if path == "/epk":  # exact only — /epk/<slug> is the public press page
        return "artist"
    # /roster/join/<token> stays open to invited artists of any tier.
    if path == "/roster" or (path.startswith("/roster/")
                             and not path.startswith("/roster/join/")):
        return "label"
    # Royalty Sweep came down to the Artist membership (owner, 2026-09-17).
    # _PRO_PATHS keeps its name because it still marks the Sweep world below.
    if _matches(path, _PRO_PATHS) or _matches(path, _ARTIST_PATHS):
        return "artist"
    return None


# What opens each suite. A tier name means that membership or higher. "credits"
# means the suite spends credits: Label has them included, and anybody else
# gets in by holding some. Keyed by the strip key AND the hand-off key, which
# differ for Tour and Motion.
SUITE_ACCESS = {
    "royalty-sweep": "artist", "artifacts": "artist",
    "reach": "pro", "reach-suite": "pro", "tour": "pro", "tour-suite": "pro", "company": "pro",
    "the-room": "credits", "noise-lab": "credits", "motion": "credits", "masterclip": "credits",
}

# Credits a Label membership is given at the start of each month. They lapse
# at the next grant. An owner decision still to confirm; one place to change.
LABEL_MONTHLY_CREDITS = 1000

# Packs any membership can buy: key -> (credits, cents, name). Bought credits
# never expire. NOT ON SALE (owner, 2026-09-18: "hide them until we know what
# the credits actually cost"): nothing spends a credit per render yet, so a
# pack would be a permanent unlock sold as a metered one. Label's included
# credits still open The Room and Motion. Turn this on once burn rates exist.
CREDIT_PACKS_ON_SALE = False
CREDIT_PACKS = {
    "pack-500": (500, 1500, "500 credits"),
    "pack-2000": (2000, 5000, "2,000 credits"),
    "pack-5000": (5000, 10000, "5,000 credits"),
}


# Pages inside this app that are really one of the suites under another
# name (owner, 2026-09-17: "build them as part of the room"). The audio pages
# cost money every time they render, so they open the way The Room does:
# Label, or a wallet with credits in it. The live pages are Tour, so they
# open with Pro. /tours itself is not path-gated, because a crew member on
# any membership opens the tours they were invited to; owning one is what
# needs the membership (tour_os._artist_tier).
_ROOM_PATHS = ("/rack", "/remix-lab", "/audio-studio", "/beats", "/studio")
_TOUR_PATHS = ("/passports", "/stage-plot", "/lights", "/tour-board", "/live")
_TOUR_NAV_ONLY = ("/tours", "/tour")


def gates_on():
    """Are the suite gates on the in-app pages enforced? On every deployed
    service (Render sets RENDER), and wherever SUITE_GATES=on. Off on a
    laptop and in the test suite unless a test turns them on, the same
    arrangement as the sign-up door."""
    import os
    mode = (os.environ.get("SUITE_GATES") or "").strip().lower()
    if mode in ("on", "off"):
        return mode == "on"
    return bool(os.environ.get("RENDER"))


def path_suite(path, nav=False):
    """The suite an in-app path belongs to, or None. `nav=True` also names
    the pages that are tagged in the sidebar without being path-gated."""
    if not gates_on():
        return None
    if _matches(path, _ROOM_PATHS):
        return "the-room"
    if _matches(path, _TOUR_PATHS) or (nav and _matches(path, _TOUR_NAV_ONLY)):
        return "tour"
    return None


def nav_lock(plan, href, credits=0):
    """The word the sidebar shows on an entry this membership cannot open
    ("Pro", "Credits"), or "". Knows the suite doors and the in-app pages."""
    if href.startswith("/suites/go/"):
        key = href[len("/suites/go/"):].split("/")[0].split("?")[0]
    else:
        key = path_suite(href.split("?")[0].rstrip("/") or "/", nav=True)
    if not key or suite_open(plan, key, credits):
        return ""
    return suite_tag(key)


def suite_access(key):
    return SUITE_ACCESS.get(key)


def suite_open(plan, key, credits=0):
    """May this membership open this suite? `credits` is the wallet balance."""
    need = SUITE_ACCESS.get(key)
    if need is None:
        return True
    if need == "credits":
        return allowed(plan, "label") or (credits or 0) > 0
    return allowed(plan, need)


def suite_tag(key):
    """The short word the strip shows on a suite this account cannot open."""
    need = SUITE_ACCESS.get(key)
    if need == "credits":
        return "Credits"
    return PLAN_NAMES.get(need, "") if need else ""


# Team seats and what a seat may do (owner, 2026-09-19): an Artist's team
# reads only; a Pro member picks read or edit for each person; a Label can
# also let an editor manage its roster. Seats per plan; None is no limit.
# Billing, settings and the team itself always stay with the account holder.
TEAM_SEATS = {"artist": 2, "pro": 5, "label": None}


def team_seats(plan):
    return TEAM_SEATS.get(plan or "", 0)


def team_can_edit(plan):
    return plan in ("pro", "label")


def team_can_roster(plan):
    return plan == "label"


def allowed(plan, tier):
    return TIER_RANK.get(plan, 1) >= TIER_RANK.get(tier, 0)


# The pages whose sidebar head carries the Royalty Sweep mark ("Track it.
# Collect it. Sweep it."). The owner, 2026-09-15: the mark "only needs to be
# under the royalty sweep page". _PRO_PATHS was doing this job and it is the
# whole money desk (Catalog, Fingerprints, Reports, Deal Room, Sync, Tax,
# Valuation, /overview...), so every one of those wore it. Kept apart from
# _PRO_PATHS so the mark can narrow without touching a tier gate. Recovery
# Cases (/royalty-recovery) is a page of Recovery; the Money queue is a tab
# of Royalties.
_SWEEP_MARK_PATHS = ("/royalties", "/statements", "/recovery", "/royalty-recovery",
                     "/disputes", "/money-queue")


def world_for_path(path):
    """Which product world a path belongs to. The switcher boxes are gone
    (2026-09-14); what reads this now is the sidebar wordmark (path_world
    "sweep" draws the Royalty Sweep mark) and the sidebar's fan and label
    groups (nav_world)."""
    if _matches(path, _SWEEP_MARK_PATHS):
        return "sweep"
    if _matches(path, _PRO_PATHS):
        # The rest of the money desk is Street Banker's, mark and all. Named
        # rather than None so nav_world does not fall back to a stale
        # session world ("fan" would take an artist's menu away here).
        return "promote"
    if path == "/epk" or _matches(path, _ARTIST_PATHS):
        return "promote"
    if _matches(path, ("/services", "/submit", "/roster")):
        return "label"
    # /fans (the artist's own Audience screen) and /marketplace (Collab)
    # used to be listed here, which gave an ARTIST the fan-side sidebar on
    # both: only Community and a slim Account, their whole menu gone. Both
    # are artist tools. A fan account still gets the fan sidebar on them,
    # because inject_plan_context forces world "fan" for the fan plan
    # whatever the path says. Found by the 2026-09-18 Audience review.
    if _matches(path, ("/discover", "/network", "/fan-label", "/capital")):
        return "fan"
    return None

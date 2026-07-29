"""Data for the Artist EQ — the 15-band priority equaliser on the homepage.

Content and wiring live here so the route mapping stays testable; the live
behaviour (dragging, presets, the curve, the recommendation) runs in
static/js/artist-eq.js off the JSON this module emits.

Nothing here forecasts money, streams, or results. The EQ reports what the
visitor told it: which lane their own priorities point at, which real
modules serve those priorities, and what to do first.
"""

# --- the fifteen channels ------------------------------------------------
# `hz` is the engraved frequency on the faceplate. `short` is the engraved
# priority word - one word per channel so fifteen labels stay readable.
# `label` is the full business name and lives everywhere that has room:
# aria-labels, tooltips, the recommendation panel, saved profiles.
# `bank` groups the channel for the mobile view (five sliders at a time).
# The keys are the stable storage identifiers - display names may evolve,
# keys never do, or every saved profile orphans.
BANDS = [
    {"key": "rightsSplits",    "hz": "25 Hz",   "short": "RIGHTS",
     "label": "Rights & Splits",    "bank": "foundation"},
    {"key": "royaltyRecovery", "hz": "40 Hz",   "short": "ROYALTIES",
     "label": "Royalty Recovery",   "bank": "foundation"},
    {"key": "distribution",    "hz": "63 Hz",   "short": "DISTRO",
     "label": "Distribution",       "bank": "foundation"},
    {"key": "metadata",        "hz": "100 Hz",  "short": "METADATA",
     "label": "Metadata",           "bank": "foundation"},
    {"key": "releaseStrategy", "hz": "160 Hz",  "short": "RELEASE",
     "label": "Release Strategy",   "bank": "foundation"},
    {"key": "content",         "hz": "250 Hz",  "short": "CONTENT",
     "label": "Content & Rollout",  "bank": "growth"},
    {"key": "audienceGrowth",  "hz": "400 Hz",  "short": "AUDIENCE",
     "label": "Audience Growth",    "bank": "growth"},
    {"key": "fanOwnership",    "hz": "630 Hz",  "short": "FANS",
     "label": "Fan Ownership",      "bank": "growth"},
    {"key": "touringLive",     "hz": "1 kHz",   "short": "LIVE",
     "label": "Touring & Live",     "bank": "growth"},
    {"key": "syncLicensing",   "hz": "1.6 kHz", "short": "SYNC",
     "label": "Sync & Licensing",   "bank": "opportunity"},
    {"key": "funding",         "hz": "2.5 kHz", "short": "FUNDING",
     "label": "Funding & Valuation", "bank": "opportunity"},
    {"key": "brand",           "hz": "4 kHz",   "short": "BRAND",
     "label": "Brand Development",  "bank": "growth"},
    {"key": "partnerships",    "hz": "6.3 kHz", "short": "PARTNERS",
     "label": "Label Partnerships", "bank": "opportunity"},
    {"key": "catalogValue",    "hz": "10 kHz",  "short": "CATALOG",
     "label": "Catalog Value",      "bank": "opportunity"},
    {"key": "longTermVision",  "hz": "16 kHz",  "short": "VISION",
     "label": "Long-Term Vision",   "bank": "opportunity"},
]

# Mobile banks: five channels each, shown one bank at a time below 640px.
# Membership is an attribute, not a slice - Brand (4 kHz) belongs to
# Growth even though it sits between two Opportunity frequencies.
BANKS = [
    {"id": "foundation", "name": "FOUNDATION"},
    {"id": "growth", "name": "GROWTH"},
    {"id": "opportunity", "name": "OPPORTUNITY"},
]

# --- presets -------------------------------------------------------------
# 0-10 per channel, mapped onto the -12/0/+12 dB engraving. Custom Mix
# carries no values: it is what the panel switches to the moment a visitor
# moves a slider themselves.
PRESETS = [
    {"id": "new-artist", "name": "New Artist", "values": {
        "rightsSplits": 9, "royaltyRecovery": 4, "distribution": 9,
        "metadata": 9, "releaseStrategy": 8, "content": 6,
        "audienceGrowth": 6, "fanOwnership": 4, "touringLive": 3,
        "syncLicensing": 3, "funding": 3, "brand": 8, "partnerships": 3,
        "catalogValue": 4, "longTermVision": 6}},
    {"id": "releasing-soon", "name": "Releasing Soon", "values": {
        "rightsSplits": 6, "royaltyRecovery": 3, "distribution": 9,
        "metadata": 9, "releaseStrategy": 10, "content": 9,
        "audienceGrowth": 8, "fanOwnership": 5, "touringLive": 4,
        "syncLicensing": 3, "funding": 3, "brand": 8, "partnerships": 3,
        "catalogValue": 3, "longTermVision": 4}},
    {"id": "growing-catalog", "name": "Growing Catalog", "values": {
        "rightsSplits": 6, "royaltyRecovery": 5, "distribution": 6,
        "metadata": 6, "releaseStrategy": 8, "content": 9,
        "audienceGrowth": 9, "fanOwnership": 8, "touringLive": 5,
        "syncLicensing": 5, "funding": 4, "brand": 6, "partnerships": 4,
        "catalogValue": 9, "longTermVision": 9}},
    {"id": "missing-royalties", "name": "Missing Royalties", "values": {
        "rightsSplits": 9, "royaltyRecovery": 10, "distribution": 4,
        "metadata": 9, "releaseStrategy": 3, "content": 2,
        "audienceGrowth": 3, "fanOwnership": 3, "touringLive": 2,
        "syncLicensing": 4, "funding": 4, "brand": 3, "partnerships": 4,
        "catalogValue": 8, "longTermVision": 5}},
    {"id": "label-ready", "name": "Label Ready", "values": {
        "rightsSplits": 9, "royaltyRecovery": 6, "distribution": 7,
        "metadata": 9, "releaseStrategy": 8, "content": 6,
        "audienceGrowth": 8, "fanOwnership": 6, "touringLive": 5,
        "syncLicensing": 6, "funding": 9, "brand": 8, "partnerships": 9,
        "catalogValue": 9, "longTermVision": 9}},
    {"id": "custom-mix", "name": "Custom Mix", "values": None},
]

DEFAULT_PRESET = "new-artist"

# --- lanes ---------------------------------------------------------------
# Royalty Recovery deliberately belongs to no lane group: it is not a lane,
# it is the thing you do before a lane, so it gets its own rule below.
LANES = [
    {"id": "distribution", "name": "Distribution Lane",
     "href": "/services/distribution",
     "blurb": "Get the record out clean, registered, and collecting.",
     "keys": ["rightsSplits", "distribution", "metadata", "releaseStrategy"]},
    {"id": "development", "name": "Development Lane",
     "href": "/audience",
     "blurb": "Grow the audience and the direct relationship with it.",
     "keys": ["releaseStrategy", "content", "audienceGrowth", "fanOwnership",
              "touringLive", "brand"]},
    {"id": "partnership", "name": "Partnership Lane",
     "href": "/capital",
     "blurb": "Build the catalog into an asset other people invest in.",
     "keys": ["syncLicensing", "funding", "partnerships", "catalogValue",
              "longTermVision"]},
]

# Royalty Recovery has to be a top-two priority AND at least this high.
SWEEP_FIRST_MIN = 8
SWEEP_FIRST = {
    "id": "sweep-first", "name": "Royalty Sweep First", "href": "/recovery",
    "blurb": "Money already earned comes before money not yet made.",
}
# When the top two lane scores sit inside this many points of each other,
# there is no dominant lane and we say so instead of picking one.
LANE_TIE_GAP = 0.75
INTEGRATED = {
    "id": "integrated", "name": "Integrated Artist Program", "href": "/overview",
    "blurb": "Your priorities span every lane, so the work runs in parallel.",
}

# --- modules -------------------------------------------------------------
# href None means the module is real but has no page of its own yet: the
# panel prints the name without wrapping it in a dead link.
MODULES = {
    "Clean Release": "/releases/clean-release",
    "Metadata Passport": "/metadata-passport",
    "Royalty Sweep": "/recovery",
    "Money Queue": "/money-queue",
    "Distribution": "/services/distribution",
    "Release Autopilot": "/releases/autopilot",
    "Rollout Studio": "/rollout-studio",
    "Artist Twin": "/artist-twin",
    "Smart Links": "/links",
    "Fan CRM": "/fans",
    "Fan Club": "/fan-club",
    "Tour Hub": "/tour",
    "Sync Packs": "/sync/clearance-packs",
    "Funding": "/funding",
    "Catalog Valuation": "/valuation",
    "EPK": "/epk",
    "Deal Room": "/deal-room",
    "Label Services": None,
    "Command Center": "/command-center",
}

PRIORITY_MODULES = {
    "rightsSplits":    ["Clean Release", "Metadata Passport"],
    "royaltyRecovery": ["Royalty Sweep", "Money Queue"],
    "distribution":    ["Distribution"],
    "metadata":        ["Metadata Passport", "Clean Release"],
    "releaseStrategy": ["Release Autopilot"],
    "content":         ["Rollout Studio"],
    "audienceGrowth":  ["Artist Twin", "Smart Links"],
    "fanOwnership":    ["Fan CRM", "Fan Club"],
    "touringLive":     ["Tour Hub"],
    "syncLicensing":   ["Sync Packs"],
    "funding":         ["Funding", "Catalog Valuation"],
    "brand":           ["Artist Twin", "EPK"],
    "partnerships":    ["Deal Room", "Label Services"],
    "catalogValue":    ["Catalog Valuation", "Deal Room"],
    "longTermVision":  ["Artist Twin", "Command Center"],
}
MAX_MODULES = 4

# --- first actions -------------------------------------------------------
PRIORITY_ACTIONS = {
    "rightsSplits":    ["Confirm ownership and collaborator splits"],
    "royaltyRecovery": ["Connect your royalty sources", "Run your Royalty Sweep"],
    "distribution":    ["Prepare your next release"],
    "metadata":        ["Complete your Metadata Passport"],
    "releaseStrategy": ["Build your release timeline"],
    "content":         ["Generate your rollout campaign"],
    "audienceGrowth":  ["Connect audience analytics"],
    "fanOwnership":    ["Set up your fan capture system"],
    "touringLive":     ["Build your Tour Hub"],
    "syncLicensing":   ["Prepare a sync-ready rights pack"],
    "funding":         ["Review funding readiness"],
    "brand":           ["Complete your Artist Twin profile"],
    "partnerships":    ["Build your Deal Room"],
    "catalogValue":    ["Run a catalog valuation"],
    "longTermVision":  ["Create your 12-month artist plan"],
}
ACTION_COUNT = 3

# Every first action leads somewhere real. Used by the onboarding program
# panel to turn the three actions into links; anything unmapped renders as
# plain text rather than a dead link.
ACTION_ROUTES = {
    "Confirm ownership and collaborator splits": "/releases/clean-release",
    "Connect your royalty sources": "/connections",
    "Run your Royalty Sweep": "/recovery",
    "Prepare your next release": "/releases/autopilot",
    "Complete your Metadata Passport": "/metadata-passport",
    "Build your release timeline": "/releases/autopilot",
    "Generate your rollout campaign": "/rollout-studio",
    "Connect audience analytics": "/audience",
    "Set up your fan capture system": "/fans",
    "Build your Tour Hub": "/tour",
    "Prepare a sync-ready rights pack": "/sync/clearance-packs",
    "Review funding readiness": "/funding",
    "Complete your Artist Twin profile": "/artist-twin",
    "Build your Deal Room": "/deal-room",
    "Run a catalog valuation": "/valuation",
    "Create your 12-month artist plan": "/command-center",
}

# Where BUILD MY PROGRAM continues to. Reuses the existing signup flow and
# tags the source so the saved mix can become an Artist Priorities profile.
CTA = {"label": "BUILD MY PROGRAM", "href": "/signup?source=artist-eq"}

# The final homepage CTA rewrites to the recommended program. Keys are the
# lane/result ids; the href never changes - only the words do.
FINAL_CTA_BY_LANE = {
    "distribution": "BUILD MY DISTRIBUTION PROGRAM",
    "development": "BUILD MY DEVELOPMENT PROGRAM",
    "partnership": "BUILD MY PARTNERSHIP PROGRAM",
    "sweep-first": "START MY RECOVERY PROGRAM",
    "integrated": "BUILD MY ARTIST PROGRAM",
}
SWEEP_CTA_RECOMMENDED = "START YOUR RECOMMENDED SCAN"

# Storage: the Artist Signal Profile. The old key is read once and
# migrated; new writes go to the new key only.
STORAGE_KEY = "streetBankerArtistSignalProfile"
LEGACY_STORAGE_KEY = "streetBankerArtistEq"
PROFILE_VERSION = 1
PROFILE_SOURCE = "homepage_artist_eq"

# Lane hysteresis: a challenger must beat the incumbent by this much
# (normalized 0-10 scale) to switch mid-drag; anything closer waits for
# the settle timer, so the recommendation never flickers under a moving
# slider.
LANE_SWITCH_MARGIN = 0.5
SETTLE_MS = 600
SAVE_DEBOUNCE_MS = 500


def get_artist_eq_config():
    """Everything the section needs, in one dict."""
    return {
        "eyebrow": "THE ARTIST EQ",
        "heading": "WHAT MATTERS MOST TO YOUR ART?",
        "support": ("Tune your priorities and Street Banker will build your "
                    "recommended path."),
        "instruction": ("Choose a preset or adjust the mix yourself. "
                        "Your program updates instantly."),
        "helper": "Lower = less important · Higher = more important",
        "bands": BANDS,
        "banks": BANKS,
        "presets": PRESETS,
        "default_preset": DEFAULT_PRESET,
        "lanes": LANES,
        "sweep_first": SWEEP_FIRST,
        "sweep_first_min": SWEEP_FIRST_MIN,
        "integrated": INTEGRATED,
        "lane_tie_gap": LANE_TIE_GAP,
        "lane_switch_margin": LANE_SWITCH_MARGIN,
        "settle_ms": SETTLE_MS,
        "save_debounce_ms": SAVE_DEBOUNCE_MS,
        "modules": MODULES,
        "priority_modules": PRIORITY_MODULES,
        "max_modules": MAX_MODULES,
        "priority_actions": PRIORITY_ACTIONS,
        "action_count": ACTION_COUNT,
        "action_routes": ACTION_ROUTES,
        "cta": CTA,
        "final_cta_by_lane": FINAL_CTA_BY_LANE,
        "sweep_cta_recommended": SWEEP_CTA_RECOMMENDED,
        "storage_key": STORAGE_KEY,
        "legacy_storage_key": LEGACY_STORAGE_KEY,
        "profile_version": PROFILE_VERSION,
        "profile_source": PROFILE_SOURCE,
        "columns": ["YOUR LANE", "YOUR RECOMMENDED MODULES",
                    "YOUR FIRST THREE ACTIONS"],
        "reset_label": "RESET MIX",
    }

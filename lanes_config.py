"""Section 6 — the three Street Banker lanes.

One unit, three channels. The hardware carries the idea; the words carry
the meaning, and they live here rather than inside the photograph, so a
reader on a phone, a screen reader and a search engine all get the same
copy the picture is illustrating.

Nothing in this section is a price list. A lane is a level of support,
and the only claim made about any of them is what is in it.
"""

EYEBROW = "Three lanes. One system."
HEADLINE = ["Choose your lane.", "Build what's next."]
SUPPORT = ("Some artists need the record out. Some need a plan around it. "
           "Some are building a catalog with real long-term value. Street "
           "Banker meets you there.")

# Where each channel sits across the unit, measured off the asset. The
# overlays that light a lane on hover use these, so the highlight lands
# on the right channel at every width instead of on a guessed third.
SEAMS = [0.3370, 0.6553]

LANES = [
    {
        "num": "01",
        "slug": "distribution",
        "name": "Distribution",
        "subline": "Release the Record",
        "description": ("Get your music released with the core infrastructure: "
                        "delivery, release tools, metadata support, smart links "
                        "and launch essentials."),
        "includes": ["Delivery to the stores and services",
                     "Metadata and credits kept release-ready",
                     "Smart links and pre-save pages",
                     "Uploaded and partner-provided statements organized in one place"],
        "for_you_if": ("You have the record and you need it out, correctly and "
                       "on time."),
        "cta": "Start a release",
    },
    {
        "num": "02",
        "slug": "development",
        "name": "Development",
        "subline": "Build the Artist",
        "description": ("Add deeper creative, strategic and growth support "
                        "through Artist Twin guidance, rollout planning, "
                        "audience development and artist-building tools."),
        "includes": ["Everything in Distribution",
                     "Artist Twin guidance on releases and artwork",
                     "Rollout planning built backwards from release day",
                     "Audience and fan development, read from your own data"],
        "for_you_if": ("The releases are landing and the next thing you need is "
                       "a plan around them."),
        "cta": "Build my artist plan",
    },
    {
        "num": "03",
        "slug": "partnership",
        "name": "Partnership",
        "subline": "Build the Asset",
        "description": ("For artists with momentum who are building long-term "
                        "value through catalog strategy, higher-touch support "
                        "and partnership-level opportunities."),
        "includes": ["Everything in Development",
                     "Catalog strategy and rights work",
                     "Higher-touch support on the decisions that compound",
                     "Partnership-level opportunities, case by case"],
        "for_you_if": ("There is a catalog behind you and the question is what "
                       "it is worth in five years."),
        "cta": "See if I qualify",
    },
]

# What the main fader means. It is depth of support - not audio volume,
# and not a quality setting. Partnership is review-based at every
# position, which is why its top detent still says "case by case".
SUPPORT_LEVELS = ["Core", "Guided", "High-touch"]

# Where each lane's fader sits by default, as an index into
# SUPPORT_LEVELS: the deeper the lane, the higher the resting position.
FADER_REST = {"distribution": 0, "development": 1, "partnership": 2}

# The lane CTAs. "Explore <lane>" said nothing about what happens next,
# and "Join Partnership" would promise an outcome that is reviewed case
# by case rather than joined.
LANE_CTAS = {
    "distribution": {"label": "Start a release", "href": "/release-check"},
    "development": {"label": "Build my artist plan", "href": "/start"},
    "partnership": {"label": "See if I qualify", "href": "/lanes#partnership"},
}

# The public matcher. Five situations, each pointing at one lane, and the
# page says why - a selector that will not explain itself is a quiz, not
# an answer.
SITUATIONS = [
    {"id": "first-release", "label": "Releasing my first music",
     "lane": "distribution",
     "why": ("The first thing to get right is the release itself: delivered "
             "clean, registered properly, and pointing somewhere.")},
    {"id": "growing", "label": "Actively growing an audience",
     "lane": "development",
     "why": ("Growth is a plan, not a post. Development is where the rollout "
             "and the audience work sit.")},
    {"id": "royalties", "label": "I need royalty help",
     "lane": "distribution",
     "why": ("Start by reading the statements you already have. That runs on "
             "the Distribution lane and does not need anything above it.")},
    {"id": "hands-on", "label": "I want hands-on development",
     "lane": "development",
     "why": ("Hands-on shaping of releases, artwork and campaigns is what "
             "Development is for.")},
    {"id": "catalog", "label": "Building long-term catalog value",
     "lane": "partnership",
     "why": ("Catalog value is a rights and strategy question, and it is worth "
             "the higher-touch lane.")},
]

IMAGE = {
    "stem": "/static/img/lanes-unit",
    "widths": [760, 1100, 1626],
    "width": 1626,
    "height": 892,
    "alt": ("Street Banker hardware-style unit with three channels representing "
            "Distribution, Development and Partnership."),
}

PRIMARY_CTA = {"label": "Find my lane", "href": "/lanes"}
SECONDARY_CTA = {"label": "Compare the lanes"}


def get_lanes_config():
    return {
        "eyebrow": EYEBROW,
        "headline": HEADLINE,
        "support": SUPPORT,
        "lanes": LANES,
        "seams": SEAMS,
        "image": IMAGE,
        "support_levels": SUPPORT_LEVELS,
        "fader_rest": FADER_REST,
        "lane_ctas": LANE_CTAS,
        "primary_cta": PRIMARY_CTA,
        "secondary_cta": SECONDARY_CTA,
        "situations": SITUATIONS,
    }

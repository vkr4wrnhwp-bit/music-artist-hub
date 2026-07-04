"""Central content config for the marketing homepage.

All homepage copy lives here, not in the template markup, so the page
can be re-worded or re-sequenced without touching HTML. The hero visual
is referenced by template path (`hero_visual.template`) so it can be
swapped for a different treatment without changing the page shell — the
recovery-scan visual is version one of that system.

Live numbers (scan totals, per-source recovery) are injected by the
route at render time; everything here is static copy and structure.
"""


def get_landing_config():
    return {
        "brand": "Royalty Sweep",
        "nav": {
            "links": [
                {"label": "Product", "href": "/overview", "menu": True},
                {"label": "Features", "href": "#features"},
                {"label": "For Artists", "href": "/catalog"},
                {"label": "Label Services", "href": "/services"},
                {"label": "Pricing", "href": "/overview"},
                {"label": "Resources", "href": "/reports", "menu": True},
                {"label": "About", "href": "#features"},
            ],
            "login": {"label": "Login", "href": "/login"},
            "cta": {"label": "Start Free Scan", "href": "/overview"},
        },
        "hero": {
            "eyebrow": "The #1 Royalty Recovery Platform",
            "headline": [
                {"text": "Find the Royalties", "accent": False},
                {"text": "You're Missing", "accent": True},
            ],
            "subhead": (
                "Royalty Sweep finds the money your catalog has earned but never "
                "collected — across every platform, every stream, every time."
            ),
            "primary_cta": {"label": "Scan for Missing Royalties", "href": "/overview", "icon": "search"},
            "secondary_cta": {"label": "See How It Works", "href": "#features", "icon": "play"},
            "value_props": [
                {"icon": "dollar", "title": "Find Missing Money", "desc": "We uncover what's uncollected."},
                {"icon": "link", "title": "Connect Everything", "desc": "All platforms. One complete picture."},
                {"icon": "chart", "title": "Maximize Your Value", "desc": "More data. More leverage. More money."},
            ],
        },
        "hero_visual": {
            "template": "landing/hero_recovery.html",
            "kind": "recovery_scan",
            "eyebrow": "Royalty Recovery Scan",
            "center_label": "Potential Missing Royalties Found",
            "callouts": [
                {"severity": "warning", "title": "MLC Gap Found", "desc": "Unmatched recordings detected"},
                {"severity": "warning", "title": "SoundExchange Not Connected", "desc": "Performance royalties may be missing"},
                {"severity": "danger", "title": "Split Conflict", "desc": "Blocking revenue from distribution"},
            ],
        },
        "trust": {
            "heading": "Trusted by artists, managers, and labels",
            "logos": [
                {"name": "ASCAP", "logo": "ascap"},
                {"name": "BMI", "logo": "bmi"},
                {"name": "The MLC", "logo": "mlc"},
                {"name": "SoundExchange", "logo": "soundexchange"},
                {"name": "Spotify", "logo": "spotify"},
                {"name": "Apple Music", "logo": "apple"},
                {"name": "YouTube", "logo": "youtube"},
            ],
        },
        "features": [
            {"icon": "search", "title": "Find Missing Royalties",
             "desc": "Our proprietary scan identifies unclaimed royalties across every source.",
             "link": {"label": "Learn More", "href": "/recovery"}},
            {"icon": "link", "title": "Connect Every Source",
             "desc": "We connect and verify all your catalog data across platforms and territories.",
             "link": {"label": "Learn More", "href": "/connections"}},
            {"icon": "shield", "title": "Recover & Collect",
             "desc": "We resolve issues, file claims, and get you paid.",
             "link": {"label": "Learn More", "href": "/recovery"}},
            {"icon": "chart", "title": "Value Your Catalog",
             "desc": "Know what your catalog is worth and how to grow it.",
             "link": {"label": "Learn More", "href": "/valuation"}},
        ],
    }

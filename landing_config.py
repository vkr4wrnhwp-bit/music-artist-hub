"""Central content config for the Street Banker homepage.

This is the editable source of truth for the marketing home page (the
Python equivalent of a homePageContent.js). Every label, link, card,
stat, and panel row lives here so the template holds no hard-coded copy.

Art direction: Street Banker is the white, luxury, editorial parent
brand; Royalty Sweep is the dark hardware/software recovery engine
inside it. Section hrefs point at real in-app routes (the marketing
routes like /platform don't exist), and can be re-pointed here freely.
"""


def get_landing_config():
    return {
        # Kept for the <title> and legacy references; the product name.
        "brand": "Royalty Sweep",

        "nav": {
            "logo": {"primary": "STREET BANKER", "secondary": "ARTIST INFRASTRUCTURE"},
            "links": [
                {"label": "Platform", "href": "/overview"},
                {"label": "Solutions", "href": "#services"},
                {"label": "Resources", "href": "/reports"},
                {"label": "Company", "href": "#infrastructure"},
                {"label": "Pricing", "href": "/billing"},
            ],
            "actions": [
                {"label": "Login", "href": "/login", "variant": "text"},
                {"label": "Start Free Scan", "href": "/overview", "variant": "primary"},
            ],
        },

        "hero": {
            "eyebrow": "STREET BANKER",
            "headline": ["THE ARTIST", "BACK OFFICE", "FOR MONEY", "YOU'RE MISSING"],
            "subheadline": (
                "Street Banker's infrastructure and Royalty Sweep work end-to-end to "
                "find, collect, and protect the royalties you've earned across every "
                "platform and territory."
            ),
            "ctas": [
                {"label": "Start Free Scan", "href": "/overview", "variant": "primary"},
                {"label": "See How It Works", "href": "#features", "variant": "secondary"},
            ],
            "value_points": [
                {"icon": "shield", "title": "No Upfront Fees", "description": "We work on results, not promises."},
                {"icon": "globe", "title": "Maximum Recovery", "description": "We pursue every source, every territory."},
                {"icon": "lock", "title": "Artist-Owned System", "description": "You own your data, connections, and catalog."},
            ],
        },

        "hero_visual": {
            "variant": "commandDesk",
            "title": "ROYALTY SWEEP",
            "label": "COMMAND DESK",
            "center": {
                "title": "Missing Royalties Found",
                "amount": "$3,301.38",
                "delta": "+9 new matches found",
                "status": "Scan in Progress",
                "description": "Analyzing 347 sources across 192 territories.",
            },
            "connected_sources": [
                {"name": "Spotify", "logo": "spotify", "status": "Connected"},
                {"name": "Apple Music", "logo": "apple", "status": "Connected"},
                {"name": "ASCAP", "logo": "ascap", "status": "Connected"},
                {"name": "BMI", "logo": "bmi", "status": "Connected"},
                {"name": "SoundExchange", "logo": "soundexchange", "status": "Connected"},
                {"name": "YouTube Content ID", "logo": "youtube", "status": "Connected"},
                {"name": "The MLC", "logo": "mlc", "status": "Connected"},
            ],
            "recovery_opportunities": [
                {"title": "Unclaimed Royalties", "amount": "$1,250.00"},
                {"title": "Underpaid Streaming", "amount": "$876.21"},
                {"title": "Performance Royalties", "amount": "$642.17"},
                {"title": "Mechanical Royalties", "amount": "$389.00"},
                {"title": "Sync Licenses", "amount": "$144.00"},
            ],
            "recent_recoveries": [
                {"source": "ASCAP", "logo": "ascap", "amount": "$786.43", "status": "Recovered"},
                {"source": "Spotify", "logo": "spotify", "amount": "$2,500.00", "status": "Recovered"},
                {"source": "Apple Music", "logo": "apple", "amount": "$1,234.56", "status": "Recovered"},
                {"source": "BMI", "logo": "bmi", "amount": "$4,321.00", "status": "Recovered"},
                {"source": "The MLC", "logo": "mlc", "amount": "$318.00", "status": "Recovered"},
                {"source": "SoundExchange", "logo": "soundexchange", "amount": "$1,850.32", "status": "Recovered"},
            ],
            "recoveries_cta": {"label": "View All Recoveries", "href": "/recovery"},
        },

        "trust": {
            # Placeholder names only — NOT verified clients or partners.
            # Replace with real, verified partners before implying endorsement.
            "heading": "TRUSTED BY INDEPENDENT ARTISTS AND LABELS WORLDWIDE",
            "items": ["Nightdrive Records", "Summit Collective", "Neon District",
                      "Vantage Group", "Lumen Studios", "Halcyon", "Wavecrest", "+ More"],
        },

        "features": [
            {"icon": "search", "texture": "vu", "title": "Find Missing Money",
             "description": "We uncover what's unclaimed, unpaid, or unmatched.",
             "link": {"label": "Learn More", "href": "/recovery"}},
            {"icon": "link", "texture": "knob", "title": "Connect Everything",
             "description": "All platforms. All territories. One infrastructure.",
             "link": {"label": "Learn More", "href": "/connections"}},
            {"icon": "chart", "texture": "grille", "title": "Maximize Your Value",
             "description": "More data. More leverage. More recovery.",
             "link": {"label": "Learn More", "href": "/valuation"}},
            {"icon": "lock", "texture": "patchbay", "title": "You Stay in Control",
             "description": "You own your catalog, connections, and future.",
             "link": {"label": "Learn More", "href": "/catalog"}},
        ],

        "lanes": {
            "label": "OUR INFRASTRUCTURE",
            "headline": "THREE LANES. ONE INFRASTRUCTURE.",
            "subheadline": (
                "Street Banker is built on a core system with three integrated lanes. "
                "Each lane solves a different problem — together, they build complete "
                "artist infrastructure."
            ),
            "cta": {"label": "Explore The Three Lanes", "href": "/overview"},
            "items": [
                {"number": "01", "title": "Distribution", "description": "Release. Collect. Report.", "href": "/royalties"},
                {"number": "02", "title": "Development", "description": "Build the artist. Grow the audience.", "href": "/audience"},
                {"number": "03", "title": "Partnership", "description": "Build assets. Create ownership.", "href": "/capital"},
            ],
            "status": [
                {"label": "Distribution", "value": "Active"},
                {"label": "Development", "value": "Active"},
                {"label": "Partnership", "value": "Active"},
            ],
        },

        "royalty_sweep": {
            "label": "ROYALTY SWEEP",
            "headline": ["THE RECOVERY ENGINE", "POWERING YOUR INFRASTRUCTURE"],
            "subheadline": (
                "Royalty Sweep is the technology layer inside Street Banker's "
                "Distribution Lane. It scans, matches, and recovers what others miss — "
                "so you know more of what you've earned."
            ),
            "cta": {"label": "Explore Royalty Sweep", "href": "/recovery"},
            "engine": {
                "status_label": "Scan Complete",
                "matches_label": "Matches Found",
                "matches_value": "347",
                "sensitivity_label": "Sensitivity",
                "results_cta": {"label": "View Results", "href": "/recovery"},
            },
        },

        "services": {
            "label": "SERVICES & SOLUTIONS",
            "headline": "BUILT FOR EVERY STAGE OF YOUR CAREER",
            "items": [
                {"title": "Royalty Recovery", "description": "Find and collect what you're owed across every source.", "href": "/recovery"},
                {"title": "Catalog Management", "description": "Organize, protect, and maximize the value of your catalog.", "href": "/catalog"},
                {"title": "Sync & Licensing", "description": "Unlock new revenue through sync and commercial use.", "href": "/sync"},
                {"title": "Reporting & Analytics", "description": "Real-time data. Clear insights. Smarter decisions.", "href": "/reports"},
                {"title": "Infrastructure Setup", "description": "We build your system so you can focus on your art.", "href": "/services"},
            ],
        },

        "footer": {
            "logo": {"primary": "STREET BANKER", "secondary": "ARTIST INFRASTRUCTURE"},
            "description": (
                "We build the infrastructure independent artists and labels need to "
                "release, collect, and grow — on their own terms."
            ),
            "columns": [
                {"title": "Platform", "links": [
                    {"label": "Royalty Sweep", "href": "/recovery"},
                    {"label": "Three Lanes", "href": "#infrastructure"},
                    {"label": "How It Works", "href": "#features"},
                    {"label": "Integrations", "href": "/connections"},
                ]},
                {"title": "Solutions", "links": [
                    {"label": "Royalty Recovery", "href": "/recovery"},
                    {"label": "Catalog Management", "href": "/catalog"},
                    {"label": "Sync & Licensing", "href": "/sync"},
                    {"label": "Analytics", "href": "/stats"},
                ]},
                {"title": "Resources", "links": [
                    {"label": "Guides", "href": "/reports"},
                    {"label": "Case Studies", "href": "/reports"},
                    {"label": "Blog", "href": "/reports"},
                    {"label": "Support", "href": "/settings"},
                ]},
                {"title": "Company", "links": [
                    {"label": "Label Services", "href": "/services"},
                    {"label": "Team", "href": "/team"},
                    {"label": "Partners", "href": "/network"},
                    {"label": "Contact", "href": "/submit"},
                ]},
            ],
            "socials": [
                {"label": "Instagram", "href": "https://instagram.com/summitartsgroup"},
                {"label": "X", "href": "https://x.com"},
                {"label": "YouTube", "href": "https://youtube.com"},
                {"label": "LinkedIn", "href": "https://linkedin.com"},
            ],
            "legal": ["Terms of Service", "Privacy Policy", "Cookie Policy"],
            "copyright": "© 2026 Street Banker LLC. All rights reserved.",
        },
    }

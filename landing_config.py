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

        # Full-width banner graphic pinned to the very top (under the nav,
        # above the hero). Carries its own headline + modules; links into the
        # app. Renders only when the file is on disk.
        "top_banner": {
            "src": "/static/img/hero-banner.png",
            "alt": "Release Music. Build Equity. — Infrastructure for the business of music: distribution, development, asset partnership, and backend intelligence.",
            "bare": True,
            "href": "/overview",
        },

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
            # Photo of the command desk; replaces the built-in SVG panel when
            # present. Whole panel links into the app. Falls back to the SVG
            # until the file is on disk.
            "image": {
                "src": "/static/img/command-desk.png",
                "alt": "Royalty Sweep Command Desk — connected sources, missing royalties found, recovery opportunities",
                "bare": True,
                "href": "/overview",
            },
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

        # A single strip graphic that replaces the four feature cards. Its
        # labels/CTAs are baked in, so each quarter is a clickable region
        # (left to right) rather than a duplicate button. Drop the file at
        # this path; falls back to the built-in cards until it exists.
        "features_image": {
            "src": "/static/img/features.png",
            "alt": "Find Missing Money · Connect Everything · Maximize Your Value · You Stay In Control",
            "bare": True,
            "regions": [
                {"label": "Find Missing Money", "href": "/recovery"},
                {"label": "Connect Everything", "href": "/connections"},
                {"label": "Maximize Your Value", "href": "/valuation"},
                {"label": "You Stay In Control", "href": "/catalog"},
            ],
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
            {"icon": "lock", "texture": "patchbay", "title": "You Stay In Control",
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
            # Full-bleed graphic that carries its own title + all lane detail.
            # Engagement buttons render BELOW it (the art has no empty space
            # to safely overlay). Drop the file at this exact path.
            "image": {
                "src": "/static/img/three-lanes.png",
                "alt": "The Three Distro Lanes — 01 Distribution, 02 Development, 03 Partnership",
                "bare": True,          # borderless, blends on the white page
                "center_buttons": True,
                "buttons_below": [
                    {"label": "01 Distribution", "href": "/royalties", "variant": "outline-dark"},
                    {"label": "02 Development", "href": "/audience", "variant": "outline-dark"},
                    {"label": "03 Partnership", "href": "/capital", "variant": "outline-dark"},
                    {"label": "Explore The Three Lanes", "href": "/overview", "variant": "primary"},
                ],
            },
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
            # Photo panel for the right side; overlay sits in the dark
            # bottom-left area so the VU meters stay uncovered. Falls back to
            # the built-in engine rack until the file is on disk.
            "image": {
                "src": "/static/img/recovery-engine.png",
                "alt": "Royalty Sweep recovery engine — analog VU meters and rack gear",
                "height_class": "h-full min-h-[240px]",  # fill the box, minimal margin
                "overlay": {
                    "position": "bottom-left",
                    "heading": "347 Matches",
                    "subtext": "Scan Complete",
                    "buttons": [{"label": "View Results", "href": "/recovery", "variant": "gold"}],
                },
            },
        },

        # Tiered "what everything is" sections — one per part of the
        # ecosystem. Rendered alternating light/dark; each links into its area.
        "pillars": [
            {
                "eyebrow": "STREET BANKER", "title": "Music Distribution",
                "tagline": "CDs, vinyl & digital — everywhere, no setup fees.",
                "description": "Get your releases onto every platform and into physical retail, with real-time sales and streaming data and no upfront fees.",
                "theme": "light",
                "bullets": ["170+ digital streaming & download services", "CD & vinyl into 2,500 national and independent retailers",
                            "No physical or digital set-up fees", "Real-time sales + streaming data, optional Soundscan"],
                "cta": {"label": "Explore Distribution", "href": "/services/distribution"},
                "visual": {"type": "stats", "items": [
                    {"value": "170+", "label": "DSPs"}, {"value": "2,500", "label": "Retailers"},
                    {"value": "$0", "label": "Setup fees"}, {"value": "Live", "label": "Sales data"}]},
            },
            {
                "eyebrow": "ART IS WAR RECORDS", "title": "Full-Service Label",
                "tagline": "Distribution, marketing, and management under one roof.",
                "description": "The SummitArts team builds artists end-to-end — from release strategy and marketing to consulting and management.",
                "theme": "light",
                "bullets": ["Music marketing to a 200,000+ fan list", "Artist consulting & day-to-day management",
                            "Branding, apparel, web & advertising", "Sync, licensing & rights support"],
                "cta": {"label": "See Label Services", "href": "/services"},
                "visual": {"type": "cards", "items": [
                    {"title": "Distribution", "desc": "Release. Collect. Report."},
                    {"title": "Marketing", "desc": "Grow the audience."},
                    {"title": "Management", "desc": "Build the career."}]},
            },
            {
                "eyebrow": "ROYALTY SWEEP", "title": "Recover What You're Owed",
                "tagline": "The engine that finds money others miss.",
                "description": "Royalty Sweep scans every source, matches your catalog, and recovers uncollected royalties — publishing, neighboring rights, mechanicals, and more.",
                "theme": "dark",
                "bullets": ["Missing-money scan across every source", "Publishing, neighboring rights & mechanicals",
                            "Claims worked through to payout", "Catalog valuation & advance eligibility"],
                "cta": {"label": "Open Royalty Sweep", "href": "/recovery"},
                "visual": {"type": "stats", "items": [
                    {"value": "$3.3K", "label": "Found"}, {"value": "347", "label": "Matches"},
                    {"value": "9", "label": "Sources"}, {"value": "192", "label": "Territories"}]},
            },
            {
                "eyebrow": "STREET BANKER", "title": "Value & Fund Your Catalog",
                "tagline": "Know what it's worth — and unlock capital.",
                "description": "See a live valuation of your catalog and turn that eligibility into real advance offers, on terms you control.",
                "theme": "light",
                "bullets": ["Low / mid / high catalog valuation", "Advance eligibility scoring",
                            "Comparable offers, side by side", "You keep ownership"],
                "cta": {"label": "Value My Catalog", "href": "/valuation"},
                "visual": {"type": "stats", "items": [
                    {"value": "$296K", "label": "Est. value"}, {"value": "$70K", "label": "Advance"},
                    {"value": "95", "label": "Score"}, {"value": "18mo", "label": "Term"}]},
            },
            {
                "eyebrow": "COMMUNITY", "title": "The Industry Network",
                "tagline": "Connect, collaborate, and book.",
                "description": "A directory of artists, producers, labels, curators, and A&R — connect, pitch tracks, submit to playlists, and enquire about shows.",
                "theme": "dark",
                "bullets": ["Search by role, genre & location", "Pitch tracks and submit to playlists",
                            "Tour dates & booking enquiries", "Mintable Moments — timed collectibles"],
                "cta": {"label": "Enter the Network", "href": "/network"},
                "visual": {"type": "avatars", "items": ["Nova Reign", "Kilo Byte", "Echo Lin", "Sable Wynn", "Prism Collective"]},
            },
            {
                "eyebrow": "FOR FANS", "title": "Discover & Collect",
                "tagline": "A home for fans, not just the industry.",
                "description": "Fans browse new music by genre and mood, follow artists, collect limited Mintable Moments, and catch shows — all from one door.",
                "theme": "dark",
                "bullets": ["Browse by genre & mood", "Follow artists & save tracks",
                            "Collect limited, watermarked Moments", "RSVP and enquire about shows"],
                "cta": {"label": "Open Discover", "href": "/discover"},
                "secondary_cta": {"label": "Continue as a Fan", "href": "/login"},
                "visual": {"type": "tiles", "items": [
                    {"name": "Late Night", "from": "#1e1b4b", "to": "#0f172a"},
                    {"name": "Energetic", "from": "#7f1d1d", "to": "#b45309"},
                    {"name": "Chill", "from": "#0e7490", "to": "#0f172a"},
                    {"name": "Focus", "from": "#064e3b", "to": "#0c0a09"}]},
            },
        ],

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

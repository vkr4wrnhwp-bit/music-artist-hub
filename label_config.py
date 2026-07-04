"""Config-driven data for the Label Services section.

Content adapted from artiswarrecords.com (Art Is War Records / SummitArts).
No public pricing tiers exist on the source site, so services use
"request a quote / custom package" CTAs rather than invented prices.
"""

BRAND = {
    "name": "Art Is War Records",
    "sub": "SummitArts",
    "tagline": "Music Marketing, Management & Label",
    "contact_email": "team.summitarts@gmail.com",
    "submissions_emails": ["team.summitarts@gmail.com", "artiswarrecords@gmail.com"],
    "consulting_contact": "Lucas Joyner",
    "socials": [
        {"label": "Facebook", "handle": "/artiswarrecords", "url": "https://facebook.com/artiswarrecords/", "logo": "other"},
        {"label": "Instagram", "handle": "@summitartsgroup", "url": "https://instagram.com/summitartsgroup", "logo": "other"},
        {"label": "YouTube", "handle": "Art Is War Records", "url": "https://youtube.com", "logo": "youtube"},
    ],
}

# Illustrative reach figures quoted from the source site.
DISTRIBUTION_STATS = [
    {"label": "Digital service providers", "value": "170+"},
    {"label": "National & indie retailers", "value": "2,500"},
    {"label": "E-commerce customers", "value": "3,700+"},
    {"label": "Ship-to locations", "value": "16,000"},
]

SERVICES = [
    {
        "slug": "distribution",
        "title": "Music Distribution",
        "tagline": "CDs, vinyl & digital — no setup fees.",
        "icon": "disc",
        "summary": "Full physical and digital distribution with no setup fees, real-time sales and streaming data, and access to thousands of retailers.",
        "features": [
            "No physical product set-up fees",
            "No digital set-up fees",
            "Digital delivery to 170+ streaming & download services",
            "Physical: CD & vinyl into 2,500 national and independent retailers",
            "Metadata management + real-time sales/streaming data",
            "Optional Soundscan reporting and analysis",
            "Free marketing platform access to thousands of retailers",
            "Digital distribution via SummitArts on Symphonic Distribution",
        ],
        "cta": "Start distributing",
    },
    {
        "slug": "marketing",
        "title": "Music Marketing",
        "tagline": "Reach a 200,000+ fan email list — and grow it daily.",
        "icon": "megaphone",
        "summary": "End-to-end marketing: branding, apparel, web, advertising, and promotion built to turn listeners into fans.",
        "features": [
            "Logo design with print-ready 300 DPI files",
            "In-house apparel design and production",
            "Website development with e-commerce + SEO management",
            "Print-on-demand and bulk water-based ink printing",
            "Promotional posters, stickers, and materials",
            "Multi-company promotional mailers (100s weekly, domestic & international)",
            "YouTube optimization, metatags & Google Search Console setup",
            "Targeted social media and YouTube video advertising",
            "Street team promotion at major festivals",
            "Entertainment-lawyer consulting, contracts & brand protection",
        ],
        "cta": "Plan a campaign",
    },
    {
        "slug": "management",
        "title": "Consulting & Management",
        "tagline": "Talent consulting for music artists and actors.",
        "icon": "briefcase",
        "summary": "Guidance for professional entertainment careers — from one-time consulting to full long-term management.",
        "features": [
            "Day-to-day business affairs management",
            "Advice on professional matters, long-term plans & personal decisions",
            "Meetings with clients and potential talent buyers",
            "Radio connections and publicity events",
            "Booking agents for worldwide regions",
            "Shopping current releases for licensing or deals",
            "Travel arrangements and advertising strategy",
            "Accounting and entertainment-lawyer relationships",
            "Multiple levels — one-time consulting through long-term contracts",
        ],
        "cta": "Request consulting",
    },
]


def get_service(slug):
    return next((s for s in SERVICES if s["slug"] == slug), None)


def get_label_data():
    return {"brand": BRAND, "services": SERVICES, "distribution_stats": DISTRIBUTION_STATS}

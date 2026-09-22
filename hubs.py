"""The Ecosystem Hub model: five core hubs that group every tool.

Single source of truth for the sidebar navigation AND the /desk/<hub>
landing pages, so the two can never drift apart. Each item is
(key, href, icon_path, label, one_line_desc). Icon paths are pipe-joined
SVG path lists rendered by base.html.
"""

HUBS = [
    ("command", "Command Center", "Your whole operation on one screen — scores, actions, and the strategist read.", [
        ("command-center", "/command-center", "M4 4h5v5H4zM11 4h5v3h-5zM11 9h5v7h-5zM4 11h5v5H4z", "Command Center", "Every module's live status on one board."),
        ("actions", "/actions", "M8 4h8M8 10h8M8 16h8|M4 4l1 1 2-2M4 10l1 1 2-2M4 16l1 1 2-2", "Actions", "The prioritized to-do list your data generates."),
        ("scores", "/qualification", "M4 16V9M9 16V5M14 16v-8|M3 16h14M14 4l1.5 1.5L18 3", "Scores", "Growth, trust and insights — three reads, each from your own numbers."),
        ("artist-twin", "/artist-twin", "M10 3a4 4 0 100 8 4 4 0 000-8z|M4 17c0-3 2.5-5 6-5s6 2 6 5M14 4l1 1 2-2", "Artist Twin", "The strategist read on your next best moves."),
    ]),
    ("studio", "Studio & Assets", "Make the record and keep its paperwork straight — audio, art, files, and passports.", [
        ("rack", "/rack", "M3 4h14v4H3z|M3 12h14v4H3z|M6 6h.01|M6 14h.01|M13 6h2|M13 14h2", "The Rack", "Mix and master in the browser: EQ, tube, compressor, LUFS loudness against platform targets, WAV export."),
        # Release-Ready (owner's brief, 2026-09-19): RoEx's mix report, free
        # 30-second previews and the paid full master, in the main app's
        # Creative Studio. The page says "not connected" or "opens soon"
        # until the key, the storage and the owner's switch are all there.
        ("release-ready", "/creative-studio/release-ready", "M3 9v2|M6 6v8|M9 4v12|M12 7v6|M13.5 14l2 2 3.5-4.5", "Release-Ready", "Upload a mix, or a vocal and a beat. RoEx checks it and makes free 30-second previews; buy the full master when you like one."),
        ("remix-lab", "/remix-lab", "M15.5 6.5A6 6 0 004.9 8.2|M4.5 13.5A6 6 0 0015.1 11.8|M16 3v4h-4|M4 17v-4h4", "Remix Lab", "One master in, a measured remix brief back."),
        ("audio-studio", "/audio-studio", "M4 10h2v4H4z|M8 6h2v12H8z|M12 8h2v8h-2z|M16 11h2v2h-2z", "Audio Studio", "Dub a release, cut campaign audio, split stems, register a voice."),
        # MASTERCLIP OS, the video render factory, on its own service like
        # the two above (owner, 2026-09-15: "missing the video edit tool").
        # Motion is MASTERCLIP's proper name (owner, 2026-09-15).
        ("masterclip", "/suites/go/motion", "M3 5h14v10H3z|M3 8h14|M6 5v10M14 5v10|M9 10l3-1.5v3z", "Motion", "Video from your masters and art, in its own suite (opens Motion)."),
        ("artwork", "/artwork", "M4 4h12v12H4z|M4 13l4-4 3 3 2-2 3 3M13 7.5a.5.5 0 100-1 .5.5 0 000 1z", "Cover Art", "Generate and manage release artwork."),
        ("vault", "/vault", "M4 5h12v11H4z|M4 8h12M7 5V3h6v2M10 11v2", "Vault", "Stems, bounces and press assets, yours to deploy."),
        ("beats", "/beats", "M5 14a3 3 0 106 0 3 3 0 00-6 0z|M11 14V4l5 2v8|M14 12a2 2 0 104 0 2 2 0 00-4 0z", "Beats", "Beat registry, licences, cleared list, usage cases."),
        # The ACRCloud desk. It registered its blueprint and appeared in no
        # navigation at all - not the sidebar, not a hub desk, not the
        # command palette - so the only way in was to type the URL.
        ("fingerprints", "/fingerprints/", "M3.5 12a6.5 6.5 0 0113 0v3|M6.5 13a3.5 3.5 0 017 0v2|M9.2 14a0.8 0.8 0 011.6 0v1", "Fingerprints", "Register your masters with ACRCloud, then scan a DJ set or stream for them - a hit opens a usage case with its timestamp."),
        ("catalog", "/catalog", "M7 4v10a2 2 0 11-2-2h2M7 4l9-1v9a2 2 0 11-2-2h2", "Catalog", "Every song you own, its identifiers, and its Track Passport."),
        # Off the sidebar while it rendered the demo songs and told every
        # artist their data was clean. It reads the account's own passports
        # now (owner, 2026-09-20: "I would like to get it to compute"), so
        # it sits beside the catalogue it reads.
        ("conflicts", "/conflicts", "M10 3l7 13H3z|M10 8v4M10 14h.01", "Rights Conflicts", "Where your own records disagree about who owns a song, and the clearances still open."),
    ]),
    ("launch", "Launch Engine", "From finished master to the world — prepare, release, promote, and measure.", [
        ("autopilot", "/releases/autopilot", "M10 3l7 7-7 7-7-7z|M10 7v6M7 10h6", "Releases", "One release at a time - readiness, the arc, the plan, the kit - and the calendar of all of them."),
        # Out of Deals and in with the releases (owner, 2026-09-19: "Sync
        # packs should go more in like releases because it's a sync pack.
        # You're making a product for sale."). Same address as before.
        ("sync-packs", "/sync/clearance-packs", "M3 6h14v10H3z|M3 6l2-3h10l2 3|M8 10h4", "Sync Packs", "Cleared, ready-to-send packs: the product you sell to a sync request."),
        ("links", "/links", "M8 11a3 3 0 004 0l2-2a3 3 0 00-4-4l-1 1M12 9a3 3 0 00-4 0l-2 2a3 3 0 004 4l1-1", "Smart Links", "One link per release with real click analytics."),
        ("rollout", "/rollout-studio", "M4 4h12v9H4z|M4 13l3 4M16 13l-3 4M7 8l2 2 4-4", "Rollout Engine", "Generated captions, briefs, and rollout plans."),
        # Back on the sidebar in its own right (owner, 2026-09-15: "epk should
        # be back in the nav bar, anything thats a major usage or plus from
        # other platforms should be visible"). It stays a tab of Press too.
        ("epk", "/epk", "M4 3h9l3 3v11H4z|M13 3v3h3|M7 9h6M7 12h6M7 15h4", "Press Kit", "Your electronic press kit on one link: bio, photos, tracks and the figures that are measured."),
        ("press-desk", "/press-desk", "M4 4h9v12H4z|M13 7h3v7a2 2 0 11-2-2h2|M6 7h5M6 10h5M6 13h3", "Press", "Media list, pitches and coverage, with the press kit they send."),
        # REACH runs no paid promotion (2026-09-19 audit: its paid pitching
        # platforms are adapters switched off), so the line says what it does.
        ("reach", "/suites/go/reach", "M3 10a7 7 0 0114 0|M6 10a4 4 0 018 0|M10 10v7|M8 17h4", "REACH", "Find playlist, press and radio opportunities, pitch them once you approve, track the replies (opens the REACH app)."),
        ("pulse", "/pulse", "M2 10h3l2-5 3 10 3-8 2 3h3", "Artist Pulse", "Daily follower and popularity snapshots, growth over time, and your link engagement."),
    ]),
    ("stage", "Live Stage Suite", "Everything between the booking and the encore — shows, plots, lights, and the rider.", [
        ("tours", "/tours", "M3 4h14v12H3z|M3 8h14|M6 12h3|M12 12h2|M7 2v4|M13 2v4", "Tour", "The whole run: My Day, Show Command, advance, stage plot, travel, rooms, guests, money."),
        ("passports", "/passports", "M5 3h10a1 1 0 011 1v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4a1 1 0 011-1z|M7 7h6M7 10h6M7 13h4",
         "Show Passport", "The technical record, versioned — a show keeps the version it was advanced against."),
        # Back in the sidebar (owner, 2026-09-07: "stage plot should still be
        # under stage suite"). TOUR keeps its own framed copy per tour.
        ("stage-plot", "/stage-plot", "M3 4h14v10H3z|M6 7h3v3H6z|M11 7h3v3h-3z|M7 17h6",
         "Stage Plot", "One drawing per act, attached to every advance you send. Draw it here before there is a tour."),
        ("lights", "/lights", "M10 2v4|M4 6l2 2|M16 6l-2 2|M6 12a4 4 0 118 0v4H6z", "Light Designer", "Cue programming with real DMX output."),
        ("tour-board", "/tour-board", "M7 8a3 3 0 116 0 3 3 0 01-6 0z|M2 17c1-3 4-4 8-4s7 1 8 4", "Team-Up Board", "Artists and venues finding each other."),
        # Tour used to be listed twice: this hub's "Tour" and a "Tour Suite"
        # that opened the separate service. An audit on 2026-09-17 found that
        # service is a fork from August, twenty routes behind this app's Tour
        # (VIP, ticket sync, advance sending, venue photos, setlists, the show
        # page the owner approved) and asleep on a free instance, so the link
        # cost a cold start to reach the older copy. One Tour, and it is this
        # one; the strip's TO mark points here too, from TOOL_SUITES_OWN. The
        # suite is rebuilt from this code after partner week.
    ]),
    ("money", "Royalty Sweep & Banking", "The money side — find it, claim it, value it, and keep the books straight.", [
        # Overview is a tab of the Command Center front (2026-09-07: "overview
        # and command center need to be in the same window"). Same URL.
        ("royalties", "/royalties", "M4 7l6-3 6 3v6l-6 3-6-3z|M4 7l6 3 6-3M10 10v6", "Royalties", "Every stream, lane, store, track and market from your statements - one page."),
        # Tax is a view of this page (owner, 2026-09-19: "move tax center
        # with statements"); the Tax Center entry left with it.
        ("statements", "/statements", "M6 3h6l3 3v11a1 1 0 01-1 1H6a1 1 0 01-1-1V4a1 1 0 011-1z|M8 9h5M8 12h5M8 15h3M10 3v4h4", "Statements", "Upload or email statements and the rows become data you can read."),
        ("recovery", "/recovery", "M10 4a6 6 0 100 12 6 6 0 000-12z|M10 7v3l2 2", "Recovery", "Findings pulled from your own uploads."),
        # "Money Queue" read like money queued to arrive; the page's own
        # heading is "Missing Money Action Queue" and that is what it does
        # (owner, 2026-09-22: "we dont want to show people this is coming
        # only what they may miss"). Beside Recovery because they answer
        # the same question from different rows: this one reads the track
        # passports, Recovery reads the statements.
        ("money-queue", "/money-queue", "M10 4a6 6 0 100 12 6 6 0 000-12z|M10 7v3M10 13v.01|M7 7l6 6", "Missing money", "Rights gaps on your passports, priced by what each is costing you."),
        ("cases", "/royalty-recovery/cases", "M4 5h12v10H4z|M4 8h12M8 5V3h4v2M10 11v2", "Recovery Cases", "Tracked claims from open to paid."),
        ("disputes", "/disputes", "M10 3l7 4v5c0 3-3 5-7 5s-7-2-7-5V7z|M10 8v3M10 13v0", "Disputes", "Log and track conflicts on your catalog."),
        ("valuation", "/valuation", "M10 3l6 4v6l-6 4-6-4V7z|M10 8v4", "Valuation", "Catalog value from your real history."),
        # The page reads "Profit & Loss" and the owner calls it the P&L, so
        # the entry does too; the address stays /revenue-os.
        ("revenue-os", "/revenue-os", "M4 16V4h12v12z|M7 13V9M10 13V7M13 13v-3", "Profit & Loss", "Income structure across your whole operation."),
        ("deals", "/deal-room", "M7 9l3-3 3 3M10 6v8|M4 16h12M4 4h4M12 4h4", "Deals", "The Deal Room and the simulator."),
        ("reports", "/reports", "M6 3h6l3 3v11a1 1 0 01-1 1H6a1 1 0 01-1-1V4a1 1 0 011-1z|M8 10h5M8 13h5", "Reports", "Exports and summaries of everything above."),
        ("hours", "/hours", "M10 3a7 7 0 100 14 7 7 0 000-14z|M10 6v4l3 2|M3 3l2 2M17 3l-2 2", "Hours Desk", "Bill your time, take bookings, approve collaborators."),
    ]),
]

# Groups outside the five hubs.
LABEL_GROUP = ("Label Services", [
    ("services", "/services", "M4 6h12v10H4z|M4 9h12M8 6V4h4v2", "Services", "Street Banker label services."),
    ("apparel", "/apparel", "M6 6l4-2 2 2 2-2 4 2-2 4h-1v6H9v-6H8L6 6z", "Apparel & Merch", "The store's own checkout, on the page you are on."),
    # Submit Music moved to the footer row (owner, 2026-09-22): it is a door
    # to the label desk, not a service on this list. FOOTER_LINKS holds it,
    # still label-only.
    # /admin/review is NOT here. It lists every account on the deployment
    # by email address, so it is an owner tool rather than a label-plan
    # feature, and it is offered from _internal_tools() in app.py beside
    # the Operator Desk. The old entry also misdescribed it: it read
    # "Submissions awaiting review", and submissions go to the inbox.
])
COMMUNITY_GROUP = ("Community", [
    ("discover", "/discover", "M10 3a7 7 0 100 14 7 7 0 000-14z|M13 7l-2 4-4 2 2-4z", "Discover (Fans)", "Find artists to follow and support."),
    ("marketplace", "/marketplace", "M4 7h12l-1 8H5zM4 7l-1-3|M8 11h4", "Collab Marketplace", "Post or answer real collaboration requests."),
    # Network is parked (docs/PARKED_PAGES.md): sample profiles. Its one real
    # part, the outreach tracker, lives on the Team-Up Board.
    # Fan Label is parked (docs/PARKED_PAGES.md): an invented fund, votes and
    # backers. Fans is one front: Dashboard · Fan CRM · Fan Club on a strip.
    ("fans", "/fans", "M7 8a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM13 8a2.5 2.5 0 100-5 2.5 2.5 0 000 5z|M3 16c0-2.2 1.8-4 4-4M13 12c2.2 0 4 1.8 4 4", "Fans", "Your fans, your CRM, your club."),
])
ACCOUNT_GROUP = ("Account", [
    ("inbox", "/inbox", "M3 12l3-8h8l3 8v4a1 1 0 01-1 1H4a1 1 0 01-1-1z|M3 12h4l1.5 2h3L13 12h4", "Inbox", "Messages and submissions."),
    ("notifications", "/notifications", "M10 3a4 4 0 00-4 4c0 4-2 5-2 5h12s-2-1-2-5a4 4 0 00-4-4z|M8.5 16a1.5 1.5 0 003 0", "Notifications", "Everything that happened while you were away."),
    ("team", "/team", "M7 8a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM13 8a2.5 2.5 0 100-5 2.5 2.5 0 000 5z|M3 16c0-2.2 1.8-4 4-4M13 12c2.2 0 4 1.8 4 4", "Team", "Invite your manager, accountant, attorney."),
    ("billing", "/billing", "M3 6h14v8H3z|M3 9h14M6 12h3", "Billing", "Plan and payments."),
    ("portal", "/portal", "M4 4h12v12H4z|M4 8h12M8 8v8", "Partner Portal", "Read-only views for your team memberships."),
    ("roster", "/roster", "M6 7a3 3 0 116 0 3 3 0 01-6 0z|M1 17c1-3 3.5-4 8-4|M13 9h6|M13 13h6|M13 17h4", "Label Roster", "Your artists, one desk (Label plan)."),
    ("referrals", "/referrals", "M10 3v14|M3 10h14|M6 6l8 8|M14 6l-8 8", "Referrals", "Bring an artist, both sides win."),
    ("certified", "/certified", "M10 2l2.4 4.9 5.6.8-4 3.9.9 5.4-4.9-2.6-4.9 2.6.9-5.4-4-3.9 5.6-.8z", "Certified", "Six rungs computed from your real record."),
    ("settings", "/settings", "M10 7a3 3 0 100 6 3 3 0 000-6z|M10 3v2M10 15v2M3 10h2M15 10h2", "Settings", "Account and preferences."),
])

FAN_ACCOUNT_KEYS = ("notifications", "billing", "settings")

# One icon per hub, for the collapsed rail. Kept in a dict rather than a
# sixth field on the HUBS tuples so nothing that unpacks them - the
# sidebar, the desk pages, command_index - has to change to gain it.
HUB_ICONS = {
    "command": "M4 4h5v5H4zM11 4h5v3h-5zM11 9h5v7h-5zM4 11h5v5H4z",
    "studio": "M3 4h14v4H3z|M3 12h14v4H3z|M6 6h.01|M6 14h.01",
    "launch": "M10 3l7 7-7 7-7-7z|M10 7v6M7 10h6",
    "stage": "M3 5h14v11H3z|M3 9h14|M7 3v4|M13 3v4",
    "money": "M10 3v14M6 7h6a2 2 0 010 4H8a2 2 0 000 4h6",
    "account": "M10 4a3 3 0 100 6 3 3 0 000-6z|M4 17c0-3 2.5-5 6-5s6 2 6 5",
    "label": "M4 6h12v10H4z|M4 9h12M8 6V4h4v2",
    "community": "M10 3a7 7 0 100 14 7 7 0 000-14z|M13 7l-2 4-4 2 2-4z",
}

# Features that genuinely work today; everything else shows a lock.
#
# Anything gated on a deployment flag CANNOT be a literal here. Remix Lab was,
# and once its engine was connected the sidebar badge, the hub-desk tile, the
# hub-desk footnote and the command palette all went on calling a live page
# "example data, not yours" - four surfaces wrong from one stale list entry.
# Flag-gated keys are appended by live_keys() instead.
_BASE_LIVE = ["apparel", "beats", "statements", "notifications", "cases",
             # Billing is live Stripe checkout and portal; the page says so
             # honestly when Stripe is not configured (audit, 2026-09-15:
             # it wore a Sample badge for every account).
             "billing",
             "artist-twin",
             "revenue-os", "overview", "royalties", "recovery",
             "valuation", "links", "rollout", "artwork", "services", "submit",
             "inbox", "settings", "catalog", "command-center",
             # F-5 (audit 2026-09-18): the badges were backwards. The Collab
             # Marketplace is a real db-backed board (nothing seeded), so it
             # is live; Discover shows example artists, so it is NOT here and
             # wears the Sample badge.
             "marketplace",
             "actions", "autopilot", "scores",
             "vault", "pulse", "team",
             # Real packs from the artist's own uploads (it was live through
             # its Deals parent before it had an entry of its own).
             "sync-packs",
             "income", "disputes", "fans", "portal",
             "tours", "passports", "stage-plot", "tour-board", "rack", "roster", "referrals",
             # Real registrations and real scan answers, or an honest "not
             # connected" when the console has no token. Nothing invented.
             "fingerprints",
             "lights", "certified",
             "press-desk", "deals",
             # The press kit reads the account's own tracks and stats and says
             # "Not measured" where nothing was; nothing on it is invented.
             "epk",
             # Real apps on their own services, opened in a new tab - not
             # previews of anything.
             "noise-lab", "the-room", "reach", "masterclip", "tour-suite",
             # Reports has five real export routes; only the demo account's
             # scheduled-report list is illustrative. It was badged as a
             # sample for want of this entry.
             "reports",
             "hours"]


def live_keys():
    """LIVE_KEYS, plus whatever the deployment's flags have actually switched on.

    Called per request rather than computed at import: the flags are read from
    the environment, and a module-level list would freeze whatever was set when
    the process booted.
    """
    keys = list(_BASE_LIVE)
    try:
        import remix_lab_config
        if remix_lab_config.engine_live():
            keys.append("remix-lab")
    except Exception:
        pass
    try:
        import audio_studio
        if any(lane["on"] for lane in audio_studio._lanes_for_render()):
            keys.append("audio-studio")
    except Exception:
        pass
    # Studio and Live are real working product, not example data. Leaving
    # them off this list stamped both with the "Sample" badge - the sidebar
    # itself telling the owner his mix and master rooms were a demo.
    try:
        import studio_config
        if studio_config.enabled():
            keys.append("studio")
    except Exception:
        pass
    try:
        import live
        if live.enabled():
            keys.append("live")
    except Exception:
        pass
    # Release-Ready is live only when an artist can actually use it: RoEx
    # connected, private storage connected, and opened by the owner. Until
    # then its card and palette entry must not read as a working page
    # (review, 2026-09-19); like Remix Lab without its engine, it is not live.
    try:
        import release_ready_settings
        if release_ready_settings.available():
            keys.append("release-ready")
    except Exception:
        pass
    return keys


# Kept as a name because templates and tests read it. It is the BASE list -
# call live_keys() for the flag-aware answer.
LIVE_KEYS = _BASE_LIVE


# A shared, read-only demo hides the entries that would only confuse a
# stranger: every page still marked Sample (it shows example data, not
# the account's) and Billing (a visitor cannot buy a plan for a demo).
# Owner, 2026-09-14: "any pages we should hide on there that dont work
# yet". The pages stay reachable at their addresses, as parked pages do.
DEMO_HIDDEN_ALWAYS = ("billing",)


def demo_hidden_keys():
    live = set(live_keys())
    hidden = set(DEMO_HIDDEN_ALWAYS)
    for _hkey, _name, _tag, items in nav_hubs():
        hidden.update(k for k, _h, _i, _l, _d in items if k not in live)
    for _gname, items in (LABEL_GROUP, COMMUNITY_GROUP, ACCOUNT_GROUP):
        hidden.update(k for k, _h, _i, _l, _d in items if k not in live)
    return hidden


def without(hubs, hidden):
    """The hub list minus the hidden keys; a hub left empty is dropped."""
    out = []
    for hkey, name, tagline, items in hubs:
        kept = [it for it in items if it[0] not in hidden]
        if kept:
            out.append((hkey, name, tagline, kept))
    return out


def tool_suites():
    """The owner's off-site apps, the tool suites of the desk (owner,
    2026-09-15: "think of street banker like adobe and the off site apps
    are tool suites"). Every hub entry whose address is another service,
    in sidebar order, so the footer strip and the rooms cannot disagree."""
    out = []
    for _hk, _name, _tag, items in nav_hubs():
        for key, href, icon, label, desc in items:
            if is_away(href):
                out.append((key, href, icon, label, desc))
    every = list(TOOL_SUITES_OWN) + out + list(TOOL_SUITES_PENDING)
    # The owner's order for the eight (suite artwork, 2026-09-17): TR NL RE RS
    # TO CO AR MO. Anything not named keeps its place after them.
    rank = {k: i for i, k in enumerate(SUITE_ORDER)}
    return sorted(every, key=lambda row: rank.get(row[0], len(rank)))


def is_away(href):
    """True for a link that leaves this app: another service outright, or
    one of the suites reached through the sign-in hand-off at /suites/go/
    (sb_suite_sso), which lands on another service after one redirect.
    The sidebar, the strip and the palette open these in a new tab."""
    return href.startswith(("http://", "https://", "/suites/go/"))


# Suites the owner has named but not yet addressed (2026-09-15: "have
# company and artifacts in the footer just for the moment, the link is
# to command center"). They sit on the strip marked Soon and open the
# Command Center until their addresses arrive; then they become entries
# above like the others and leave this list.
# The two suites that left the Studio hub (owner, 2026-09-15: "remove
# noise lab and the room from studio"). They are their own products with
# their own sign-in, so they belong on the suites strip rather than in a
# hub of Street Banker's own pages.
SUITE_ORDER = ("the-room", "noise-lab", "reach", "royalty-sweep", "tour-suite", "company", "artifacts", "masterclip")

# Suites that have an address but are not open to members yet: they keep
# their place and their link on the strip, marked Soon, and the door sends
# everyone but the owner to a Coming soon page (owner, 2026-09-18, on Noise
# Lab: "soon as we need to finish it").
SUITES_SOON = {"noise-lab"}


# The strip entries that are waiting; everything else is live.
def suites_pending():
    return {row[0] for row in TOOL_SUITES_PENDING} | SUITES_SOON


TOOL_SUITES_OWN = (
    # Royalty Sweep is this app: rights, royalties, clarity. It sits on the
    # strip with the other seven (owner, 2026-09-17: "yes put royalty sweep in
    # the footer") and opens the Royalties desk in this tab.
    ("royalty-sweep", "/royalties", "M4 6h12M4 10h12M4 14h8", "Royalty Sweep", "Rights, royalties and clarity: the money desk of this app."),
    # Says what ships (audit, 2026-09-20): a loop or WAV processor with AI-set
    # effects, A/B and patches; no live input or pedal chains yet.
    ("noise-lab", "/suites/go/noise-lab", "M3 10c1-3 2-3 3 0s2 3 3 0 2-3 3 0 2 3 3 0 2-3 3 0|M4 15h12", "Noise Lab", "Shape a loop or your own WAV with AI-set effects, compare A/B, save patches and export (opens the Noise Lab app)."),
    ("the-room", "/suites/go/the-room", "M3 17V8l7-5 7 5v9H3z|M8 17v-5h4v5", "The Room", "Songwriting, arrangement and production: build the record part by part, in its own app."),
    ("tour-suite", "/tours", "M3 15h14|M5 15V9l5-4 5 4v6|M8 15v-3h4v3|M15 4l2 2", "Tour", "Route it, advance it, play it, settle it: the tour desk of this app."),
)

TOOL_SUITES_PENDING = (
    ("company", "/command-center", "M3 17V6l7-3 7 3v11H3z|M8 17v-5h4v5|M7 9h.01M13 9h.01", "Company",
     "Your team, your partners and your paperwork. Coming to the suites; opens the Command Center for now."),
    ("artifacts", "/command-center", "M4 4h12v12H4z|M4 9h12|M9 9v7|M7 6.5h.01", "Artifacts",
     "Merch, collectibles and moments for fans. Coming to the suites; opens the Command Center for now."),
)

# The suites strip draws every suite the same way (owner, 2026-09-17: "fix the
# images in the footer to be the same size and look"): one bracket frame, a
# two-letter monogram, the suite's own colour, as on the owner's flight-case
# artwork. The marks the owner sent were each built differently (frame
# shape, line weight, glow), so they are drawn here as one system instead of
# resized. Keyed by strip key: (monogram, colour).
SUITE_MARKS = {
    "noise-lab": ("NL", "#F2E600"),
    "the-room": ("TR", "#FF7A1A"),
    "masterclip": ("MO", "#12C8FF"),
    "reach": ("RE", "#1E9BFF"),
    "royalty-sweep": ("RS", "#19E68C"),
    "tour-suite": ("TO", "#FF2D2D"),
    "company": ("CO", "#FF2DD1"),
    "artifacts": ("AR", "#9B5CFF"),
}


# Words a page is looked for by that are not in its name. The palette ranks
# these below a match on the name itself and above a stray word in a
# description, so "mastering" finds Release-Ready without anybody having to
# know what the page is called.
PALETTE_WORDS = {
    "release-ready": "master mastering release ready roex mix report previews loudness",
}


def command_index():
    """Every destination as one flat list, for the command palette.

    Built from the same HUBS/LABEL/COMMUNITY/ACCOUNT definitions the
    sidebar renders, so the palette cannot drift from the nav - a search
    box that finds a page which no longer exists is worse than no search
    box. Each entry carries the hub it belongs to, so a result can say
    where it lives, and whether the feature is actually live.

    Returns [{key, href, label, desc, group, live}].
    """
    out = []
    seen = set()

    def add(key, href, label, desc, group):
        if key in seen:
            return
        seen.add(key)
        out.append({"key": key, "href": href, "label": label,
                    "desc": desc, "group": group,
                    "aka": PALETTE_WORDS.get(key, ""),
                    "live": key in live_now})

    live_now = live_keys()

    for _hkey, name, _tagline, items in nav_hubs():
        for key, href, _icon, label, desc in items:
            add(key, href, label, desc, name)
    for group_name, items in (LABEL_GROUP, COMMUNITY_GROUP, ACCOUNT_GROUP):
        for key, href, _icon, label, desc in items:
            add(key, href, label, desc, group_name)
    # The Hours desk sits in the money hub already; anything reachable but
    # not in a group would be invisible here, so keep this list honest by
    # deriving it rather than hand-maintaining a second one.
    return out


def get_hub(key):
    for hkey, name, tagline, items in HUBS:
        if hkey == key:
            return {"key": hkey, "name": name, "tagline": tagline, "modules": items}
    return None


# --- Studio (flag-gated) -----------------------------------------------------
# Not a literal inside HUBS. studio_v1 is off by default and every Studio route
# 404s while it is, so a sidebar entry baked into the list would be a link to
# nothing on every deployment that has not switched it on. Remix Lab taught the
# same lesson from the other direction: a flag-gated page listed as a literal
# went on describing itself wrongly across four surfaces.
_STUDIO_ITEM = (
    "studio", "/studio",
    "M3 5h14v10H3z|M3 15h14|M6 8v4|M9 7v6|M12 9v3|M15 8v4",
    # "Studio" inside a room called Studio said nothing about the work
    # (owner, 2026-09-17). The page keeps its Control Room heading.
    "Mix Check",
    "Check a mix or master before it goes out: loudness, headroom, versions and approvals.",
)


def nav_hubs():
    """HUBS, plus Studio when this deployment has switched it on.

    Called per request rather than computed at import, for the same reason
    live_keys() is: the flag comes from the environment, and a module-level
    list would freeze whatever was set when the process booted.
    """
    try:
        import studio_config
        if not studio_config.enabled():
            return _with_live(HUBS)
    except Exception:
        return _with_live(HUBS)

    out = []
    for hkey, name, tagline, items in HUBS:
        if hkey == "studio" and not any(i[0] == "studio" for i in items):
            items = [_STUDIO_ITEM] + list(items)
        out.append((hkey, name, tagline, items))
    return _with_live(out)


# --- Live (flag-gated) -------------------------------------------------------
# Same reasoning as Studio's entry: LIVE_LAB_ENABLED is off by default and
# every /live route 404s while it is, so a literal in HUBS would be a sidebar
# link to nothing on most deployments.
_LIVE_ITEM = (
    "live", "/live",
    "M4 14a2 2 0 104 0 2 2 0 00-4 0z|M12 14a2 2 0 104 0 2 2 0 00-4 0z"
    "|M6 14V5l10-2v9|M6 8l10-2",
    "Live",
    "Set, stems and triggers. Scenes launch on the bar; stems go to separate outputs.",
)


def _with_live(hubs):
    try:
        import live
        if not live.enabled():
            return hubs
    except Exception:
        return hubs
    out = []
    for hkey, name, tagline, items in hubs:
        if hkey == "stage" and not any(i[0] == "live" for i in items):
            items = [_LIVE_ITEM] + list(items)
        out.append((hkey, name, tagline, items))
    return out


# --- the quiet row under the suites -----------------------------------------
# Pages that are a door to somewhere rather than a step in the work. They
# had cards in rooms, where they read as part of the job on that screen;
# the footer is where a door belongs (owner, 2026-09-22: "submit music can
# be removed from studio and you can move that into the footer").
#
# (key, href, label, plans that see it - empty means everyone)
FOOTER_LINKS = (
    ("submit", "/submit", "Submit music", ("label",)),
    # The legal row. These pages existed and nothing in the app linked to
    # them, which is the one place a footer is not a nicety (owner,
    # 2026-09-22: "shouldn't we have a footer anyways for policies and all
    # the legal things"). Everyone sees these, on every plan.
    #
    # White label: /terms and /privacy are the two pages that keep naming
    # the operating entity when a reseller's artists are looking, because
    # an agreement has to say who it is with. Linking them does not change
    # that; white_label.py decides what they say.
    # For a label or manager wondering whether they could run this under
    # their own name. There was nowhere to read about it.
    ("white-label", "/white-label", "White label", ()),
    ("terms", "/terms", "Terms", ()),
    ("privacy", "/privacy", "Privacy", ()),
    ("contact", "/contact", "Contact", ()),
)


def footer_links(plan):
    """The footer row for this membership."""
    plan = (plan or "").strip().lower()
    return [(k, h, lab) for k, h, lab, plans_ in FOOTER_LINKS
            if not plans_ or plan in plans_]

"""The app home page for after the split, and the switch that shows it.

The owner is moving the public story to the Shopify store at
streetbankermusic.com. When that happens app.streetbankermusic.com stops
being a website with a login on it and becomes the door to the system: a
stranger who lands here has already read the story somewhere else, and a
member who lands here wants to be inside.

So the long homepage loses four of its nine sections and its hero is
replaced by the door. What is left is what only the app can do:

  the door          headline, the words over it, and the sign-in form
                    where the marketing hero used to be
  the stages rail   the eight words the whole product is organised by
  the Artist EQ     the one thing on the page a visitor operates
  eight tools       the rack, so a member can see which doors exist
  the Artist Twin   because it is the argument for the account
  memberships       three passes and the credit wallet
  the way back      one line pointing at the store

The sections it drops (the three lanes, Creative Studio, the Rollout
Engine, the back office) are not deleted. They are the story, and the
story now lives on Shopify, where the owner can edit it without a deploy.

THE SWITCH
----------
This ships off. The store pages are not up yet, and a home page that
sends people to a store that does not exist is worse than a long one.
It follows the rooms-layout pattern exactly: the owner's saved choice
wins, and a deployment can set SPLIT_HOME=1 to try it without touching
the database. Settings > Home page is the toggle, owner only.

The owner asked for it that way after I said it would be "one switch in
Render", which was sloppy: a Render switch means a redeploy, a wait, and
a second redeploy to put it back, and it is invisible to him. A toggle
he can flip and unflip while looking at the page is the same work and a
better answer.
"""

import os

# The lifecycle every desk in the app hangs off. The rail that shows
# these is a map, not a progress bar: the homepage does not know who is
# reading it, and a lit stage on a stranger's screen would be a claim
# about them.
STAGES = ["Create", "Finish", "Approve", "Protect",
          "Deliver", "Release", "Market", "Monetize"]

HERO = {
    "eyebrow": "One platform. Every stage.",
    "headline": "Pick up where you left off.",
    "lede": "One sign-in opens Street Banker and all eight suites.",
    # Accounts are by invitation until the owner opens sign-up. The line
    # says so rather than letting somebody fill in a form that creates
    # nothing.
    "closed": "Street Banker is opening by invitation.",
    "closed_link": ("Have an invitation link?", "/signup"),
    "open": "New here?",
    "open_link": ("Create an account", "/signup"),
}

FOOT = {
    "line": "Tools for a bigger tomorrow.",
    "store": "The full story, plans and the store live at",
}

# What is cut into each plate, line for line. The image is the only
# place these words are drawn, so they live here too: a screen reader
# reads this, and anyone changing what a tier includes can see here that
# a new photograph is needed. tests/test_split_home.py checks the price
# in each line still matches plans.PLANS.
ENGRAVED = {
    "artist": "$29 a month. Street Banker, Royalty Sweep, Artifacts.",
    "pro": "$79 a month. All of Artist, REACH, Tour, Company.",
    "label": ("$199 a month. All of Pro, The Room, Noise Lab, Motion, "
              "monthly credits."),
}

CREDIT_NOTE = (
    "The Room, Noise Lab and Motion spend credits, because every render "
    "costs real compute. One wallet covers all three. Label includes "
    "credits every month, any membership can buy a pack, and bought "
    "credits never expire.")


def enabled():
    """Is the split home page the home page?

    The owner's saved choice wins over the environment, the same way the
    menu layout works. Nothing set anywhere means the long homepage, so
    this cannot change the front page by being deployed.
    """
    try:
        import db
        choice = db.get_kv("home_layout")
    except Exception:
        choice = None
    if choice in ("split", "full"):
        return choice == "split"
    return (os.environ.get("SPLIT_HOME") or "").strip().lower() in (
        "1", "true", "yes", "on")


def set_layout(value):
    import db
    db.set_kv("home_layout", "split" if value == "split" else "full")


def get_split_home_config(signup_open=False):
    """Everything the split page says that is not already a section's own
    config. Prices come from plans so they can never drift from Billing.
    """
    import plans
    # Fan is free and has no pass: a photographed metal pass for a free
    # tier would say something about it that is not true.
    paid = ("artist", "pro", "label")
    # THE PASSES
    # ----------
    # Two images per pass, and this is the whole trick. PLATE is the
    # metal with the engraving cut into it and no light on the letters.
    # WORDS is the same engraving as an alpha mask: white glyphs on
    # nothing. The mask is what the light is poured through, so the
    # letters can be lit without lighting the plate.
    #
    # Both are the owner's, shot for this band. He asked for them back
    # by name after I shipped blank plates with live type over them:
    # that version could not do the effect, because live text lights as
    # one block. The words are stacked lines inside one image, so a
    # light edge rising through the mask crosses them one line at a
    # time, which is the thing he remembered and the thing he wanted.
    #
    # The cost of engraved metal is that the prices and the contents are
    # baked into a photograph. tests/test_split_home.py asserts every
    # engraved price still matches plans.PLANS, so changing a price
    # fails the build instead of quietly making the plate lie.
    #
    # LIT is the colour the letters reach. BLOOM is the colour that
    # spills off them, blurred and screened, and it is warmer than LIT
    # because hot metal throws warmer light than it holds.
    #
    # Paths are named here, not assembled in the template.
    # tests/test_image_slots.py scans templates for /static/img/... and
    # cannot evaluate Jinja, so a path built from a loop variable reads
    # to it as a missing file - correctly, since it cannot know what the
    # variable holds. Naming them here keeps that check meaningful.
    #
    # sb-keep: these six are not chrome and must not be snapped onto the
    # gold ramp. They are the colour of light on three specific pieces of
    # metal in three specific photographs, matched to them by eye. Moving
    # black metal's highlight to --sb-gold-bright makes it glow the same
    # colour as the gold plate, which is the one thing that tells the
    # three passes apart at a glance. Same reason the Light Studio gel
    # book is exempt: this is data about a physical thing, not a theme.
    metal = {
        # sb-keep: light on the owner's black plate
        "artist": ("black metal", "#FFF6E0", "#E9B949"),
        # sb-keep: light on the owner's bronze plate
        "pro": ("bronze", "#FFD79A", "#FF9A3D"),
        # sb-keep: light on the owner's gold plate
        "label": ("gold", "#FFFBE6", "#FFD45E"),
    }
    tiers = []
    for key, name, price, blurb, includes in plans.PLANS:
        if key not in paid:
            continue
        finish, lit, bloom = metal[key]
        tiers.append({
            "key": key, "name": name, "price": price, "blurb": blurb,
            "includes": includes, "top": key == "label",
            "finish": finish, "lit": lit, "bloom": bloom,
            "plate": "/static/img/pass-plate-%s.webp" % key,
            "words": "/static/img/pass-words-%s.webp" % key,
            # What the engraving actually says, so a screen reader gets
            # the pass and the repo carries the copy in text.
            "reads": ENGRAVED[key],
        })
    packs = [{"credits": credits, "price": "$%d" % (cents // 100), "label": label}
             for credits, cents, label in sorted(plans.CREDIT_PACKS.values())]
    return {
        "stages": STAGES,
        "hero": HERO,
        "foot": FOOT,
        "signup_open": bool(signup_open),
        "tiers": tiers,
        "credit_note": CREDIT_NOTE,
        "packs": packs,
    }

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
    # The pass images are named here rather than assembled in the
    # template. tests/test_image_slots.py scans templates for
    # /static/img/... and cannot evaluate Jinja, so a path built from a
    # loop variable reads to it as a missing file - correctly, since it
    # cannot know what the variable holds. Naming them here keeps that
    # check meaningful; tests/test_split_home.py asserts the four files
    # actually ship.
    tiers = [{"key": key, "name": name, "price": price, "blurb": blurb,
              "includes": includes, "top": key == "label",
              "pass_webp": "/static/img/pass-%s.webp" % key,
              "pass_png": "/static/img/pass-%s.png" % key}
             for key, name, price, blurb, includes in plans.PLANS
             if key in paid]
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

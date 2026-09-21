"""Whose product is this? One answer, for every surface that has to say it.

A reseller pays for a white-label tenant, and their artists must see the
reseller's brand everywhere. The owner's ruling, 2026-09-10, has exactly
two exceptions: /terms and /privacy keep naming the operating entity,
because they describe who actually holds the data and who the artist is
contracting with, and that does not change because somebody else's logo
sits above it.

Before this module the answer was written out by hand in every place that
needed it - a hundred and fifty-one page titles, a manifest, four email
subjects - and every one of them said Street Banker. The point of putting
it here is that a new page cannot get it wrong by forgetting: the frame
asks this, the leaf only names itself.

Nothing here reads the database. The tenant is already resolved onto `g`
by app.resolve_partner before any of this runs, and a background job with
no request context is the platform's own mail, not an error.
"""

# The platform's own names. SWEEP is not a second brand: it is the mark
# Royalty Sweep's own pages wear, and only those (owner, 2026-09-14),
# which is the same rule the sidebar wordmark follows in base.html.
PLATFORM = "Street Banker"
SWEEP = "Royalty Sweep"

# Who holds the data and who the artist is contracting with. This one is
# never swapped - see the module docstring.
OPERATING_ENTITY = "Street Banker LLC"

# A tenant's logo. Two megabytes is a wordmark in a sidebar, not
# artwork; no TIFF, no BMP, nothing a browser will not draw.
# SVG is deliberately absent. An SVG is a document, not a picture:
# served from /uploads it is same-origin with every artist's session,
# and opened directly its script runs. Rasterising or sanitising one
# is a real feature and a separate one.
LOGO_EXTENSIONS = ("png", "jpg", "webp")
LOGO_MAX_BYTES = 2 * 1024 * 1024

# Ink for text that sits ON the accent. Both are taken from the token
# sheet's ends rather than pure black and white, so a tenant's button
# looks like it belongs to this product.
INK_DARK = "#0b0a08"
INK_LIGHT = "#f2ece0"


def tenant():
    """The partner row this request resolved to, or None.

    Never raises. Mail sent from a background path has no request context
    at all, and that is not an error - it is the platform's own.
    """
    try:
        from flask import g, has_request_context
        if not has_request_context():
            return None
        return getattr(g, "partner", None) or None
    except Exception:
        return None


def tenant_name():
    """The reseller's display name, or "" for Street Banker's own."""
    partner = tenant()
    if not partner:
        return ""
    try:
        return (partner.get("display_name") or partner.get("name") or "").strip()
    except Exception:
        return ""


def product_name(path=None):
    """The name to print where the product names itself.

    A tenant's name wins outright. Without one, Royalty Sweep's own pages
    wear Royalty Sweep and everything else wears Street Banker, which is
    what the sidebar has done since 2026-09-14 - the tab now agrees with
    the wordmark beside it instead of contradicting it.
    """
    name = tenant_name()
    if name:
        return name
    if path is None:
        try:
            from flask import has_request_context, request
            path = request.path if has_request_context() else None
        except Exception:
            path = None
    if path:
        try:
            import plans
            if plans.world_for_path(path) == "sweep":
                return SWEEP
        except Exception:
            pass
    return PLATFORM


def brand_text(text):
    """Swap the platform's name for the tenant's inside a phrase.

    For the places that build a label out of the product name and
    something else - "Street Banker . Beats" in a page band's eyebrow -
    where the part that is ours is a substring rather than the whole
    string. Returns the text untouched when there is no tenant, so the
    platform's own pages render exactly what they always did.

    Registered as a Jinja GLOBAL, not handed to templates by the context
    processor: templates/_sb.html is imported with {% import %}, which is
    context-free, so a macro in it cannot see `brand` at all. A global
    can. This is the difference between the swap working on every page
    and appearing to work while doing nothing.
    """
    name = tenant_name()
    if not name or not text:
        return text
    return text.replace(PLATFORM, name).replace(SWEEP, name)


def page_title(page, path=None):
    """One tab title: the page's own name, then whose product it is.

    A page with nothing to say for itself gets the product name alone
    rather than a stray separator hanging off the front.
    """
    page = (page or "").strip()
    product = product_name(path)
    return "%s - %s" % (page, product) if page else product


# --- the accent -------------------------------------------------------------
# partner_os.branding refuses an accent that cannot be read on the dark
# surfaces it sits on (brand_contrast.check_accent, AA large). That gate
# proves one thing: the accent is legible AS INK on this product's dark
# ground. It proves nothing about text sitting ON the accent, which is a
# different pair of colours, so that question is asked separately here.


def accent_ink(accent):
    """The better of the two inks to put on this accent, and its ratio."""
    import brand_contrast
    colour = brand_contrast.normalise(accent)
    if colour is None:
        return INK_DARK, 0.0
    dark = brand_contrast.ratio(colour, INK_DARK)
    light = brand_contrast.ratio(colour, INK_LIGHT)
    return (INK_DARK, dark) if dark >= light else (INK_LIGHT, light)


def accent_fill_ok(accent):
    """May this accent be a FILL behind text, not only ink and edges?

    Only when the better ink on it clears AA for body text. An accent can
    pass the save-time gate at 3.1:1 against the sidebar and still leave
    nothing readable on top of it; a button nobody can read is worse than
    a button in the platform's gold.
    """
    import brand_contrast
    return accent_ink(accent)[1] >= brand_contrast.AA_NORMAL


def accent_vars(brand):
    """The CSS custom properties a tenant's accent sets, as one string.

    Empty when there is no tenant or no accent, so the platform's own
    pages carry no inline style at all and static/css/white-label.css
    falls through to the tokens it already had.
    """
    accent = ((brand or {}).get("accent") or "").strip()
    if not accent:
        return ""
    import brand_contrast
    colour = brand_contrast.normalise(accent)
    if colour is None:
        return ""
    ink, _ratio = accent_ink(colour)
    out = ["--sb-brand-accent: %s;" % colour]
    if accent_fill_ok(colour):
        out.append("--sb-brand-fill: %s;" % colour)
        out.append("--sb-brand-on-fill: %s;" % ink)
    return " ".join(out)

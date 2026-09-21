"""The browser tab, the install card, the accent and the logo.

tests/test_white_label_brand.py holds the 2026-09-10 ruling: a reseller's
artists see the reseller everywhere, with exactly two exceptions, /terms
and /privacy. It checked the sidebar, the sign-in page and the sender's
display name, and it passed, while a reseller's artist still read STREET
BANKER in the browser tab on a hundred and fifty-one pages, got the
platform's name under the icon when they installed the app, and read it
again in every password-reset email. The owner, 2026-09-17: "we missed
alot ... white label".

The first test in this file is the lock. A mechanical fix with nothing
holding it in place comes undone: the whole leak was 151 leaf templates
each doing the obvious thing, and the 152nd would have joined them. It
reads the templates themselves, so it fails on a page that has not been
written yet.
"""
import io
import os
import re
import uuid

import pytest

import brand_contrast
import db as store
import partner_store as ps
import white_label

PASSWORD = "brand-swap-123"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")

# The six templates that are allowed to name a product in a title.
#
# The four frames COMPOSE the title - they print the brand once, which is
# the whole point - and desk/layout.html and signal/_shell.html are Street
# Banker's own staff tools. The Operator Desk and Signal sit behind
# operator_desk.require() and signal_hub.require(); no reseller's artist
# can reach either, and neither is part of what a reseller sells. They go
# on saying whose they are on purpose.
TITLE_EXEMPT = {
    "base.html", "auth_base.html", "public_base.html",
    os.path.join("tour", "_public.html"),
    os.path.join("desk", "layout.html"),
    os.path.join("desk", "denied.html"),
    os.path.join("signal", "_shell.html"),
    os.path.join("signal", "denied.html"),
}

PRODUCT = re.compile(r"Street Banker|Royalty Sweep", re.I)
TITLE_LINE = re.compile(r"\{% block title %\}.*?\{% endblock %\}|<title>.*?</title>")


def _templates():
    for root, _dirs, files in os.walk(TEMPLATES):
        for name in sorted(files):
            if name.endswith(".html"):
                path = os.path.join(root, name)
                yield os.path.relpath(path, TEMPLATES), path


# --- the lock ----------------------------------------------------------------

def test_no_page_bakes_the_product_name_into_its_own_title():
    """The 152nd page cannot reintroduce the leak.

    A page names the PAGE. Whose product it is comes from the frame, once,
    so there is nothing for a new template to get wrong and nothing to
    keep in step by hand.
    """
    offenders = []
    for rel, path in _templates():
        if rel in TITLE_EXEMPT:
            continue
        with io.open(path, encoding="utf-8") as fh:
            body = fh.read()
        for title in TITLE_LINE.findall(body):
            if PRODUCT.search(title):
                offenders.append("%s: %s" % (rel, title.strip()))
    assert not offenders, (
        "These titles name the product instead of the page, so a reseller's "
        "artist reads it in their browser tab. Name the page and let the "
        "frame add the brand:\n  " + "\n  ".join(offenders))


def test_the_frame_is_where_the_brand_goes_in():
    """A lock on the leaves is worth nothing if the frame stops substituting."""
    with io.open(os.path.join(TEMPLATES, "base.html"), encoding="utf-8") as fh:
        head = fh.read()
    assert "{{ product_name }}" in head, "base.html must compose the title"
    assert "block title" in head


# --- the tenant --------------------------------------------------------------

@pytest.fixture(scope="module")
def application():
    import app as appmod
    return appmod.app


@pytest.fixture
def tenant(application):
    """A reseller with a domain and a brand, and an artist on its roster."""
    slug = "tb%s" % uuid.uuid4().hex[:6]
    domain = "app.%s.example" % slug
    with application.app_context():
        pid = ps.create_partner("Foxglove Music Group", slug=slug, domain=domain)
        ps.set_branding(pid, display_name="FOXGLOVE", accent="#4fa3d1",
                        tagline="Sign. Ship. Get paid.")

    admin_email = "fg-admin-%s@example.net" % uuid.uuid4().hex[:8]
    admin = application.test_client()
    admin.post("/signup", data={"name": "Admin", "email": admin_email,
                                "password": PASSWORD})
    artist_email = "fg-artist-%s@example.net" % uuid.uuid4().hex[:8]
    artist = application.test_client()
    artist.post("/signup", data={"name": "Wren", "email": artist_email,
                                 "password": PASSWORD})
    with application.app_context():
        ps.add_member(pid, admin_email, "Admin", "owner",
                      user_id=store.get_user_by_email(admin_email)["id"])
        ps.attach_user(pid, store.get_user_by_email(artist_email)["id"])
    admin.post("/login", data={"email": admin_email, "password": PASSWORD})
    artist.post("/login", data={"email": artist_email, "password": PASSWORD},
                headers={"Host": domain})
    return {"id": pid, "domain": domain, "admin": admin, "artist": artist,
            "artist_email": artist_email, "app": application}


def _title(html):
    found = re.search(r"<title>(.*?)</title>", html, re.S)
    return found.group(1).strip() if found else ""


# --- leak 1: the browser tab -------------------------------------------------

@pytest.mark.parametrize("path", ["/overview", "/settings", "/royalties",
                                  "/releases", "/tour"])
def test_a_tenants_artist_reads_the_tenant_in_the_tab(tenant, path):
    page = tenant["artist"].get(path, headers={"Host": tenant["domain"]},
                                follow_redirects=True)
    title = _title(page.get_data(as_text=True))
    assert "FOXGLOVE" in title, "%s tab reads %r" % (path, title)
    assert "Street Banker" not in title
    assert "Royalty Sweep" not in title


def test_the_page_still_says_which_page_it_is(tenant):
    page = tenant["artist"].get("/settings", headers={"Host": tenant["domain"]},
                                follow_redirects=True)
    title = _title(page.get_data(as_text=True))
    assert title.startswith("Settings"), title
    assert title.endswith("FOXGLOVE"), title


def test_the_sign_in_tab_is_the_tenants_before_anyone_has_an_account(tenant):
    anon = tenant["app"].test_client()
    page = anon.get("/login", headers={"Host": tenant["domain"]})
    assert "FOXGLOVE" in _title(page.get_data(as_text=True))


def test_street_bankers_own_tab_is_untouched(application):
    c = application.test_client()
    email = "own-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Solo", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    assert _title(c.get("/settings", follow_redirects=True)
                  .get_data(as_text=True)) == "Settings - Street Banker"
    # Royalty Sweep's own pages keep their own mark, which is the rule the
    # sidebar wordmark has followed since 2026-09-14. Before this change the
    # tab said "Royalty Sweep" on nineteen pages the sidebar called Street
    # Banker; now the two agree because one expression decides both.
    assert _title(c.get("/royalties", follow_redirects=True)
                  .get_data(as_text=True)) == "Royalties - Royalty Sweep"


def test_a_page_with_nothing_to_say_for_itself_gets_the_brand_alone():
    """Never a stray separator where a page name should be."""
    assert white_label.page_title("", "/overview") == "Street Banker"
    assert white_label.page_title("  ", "/overview") == "Street Banker"


# --- the two exceptions the owner ruled on -----------------------------------

@pytest.mark.parametrize("path", ["/terms", "/privacy"])
def test_the_legal_pages_keep_naming_the_operating_entity(tenant, path):
    """They describe who holds the data and who the artist is contracting
    with. That does not change because somebody else's logo is above it."""
    page = tenant["app"].test_client().get(path, headers={"Host": tenant["domain"]})
    assert page.status_code == 200
    assert white_label.PLATFORM in page.get_data(as_text=True)


# --- leak 2: the install card ------------------------------------------------

def test_the_install_card_wears_the_tenant(tenant):
    card = tenant["app"].test_client().get(
        "/manifest.webmanifest", headers={"Host": tenant["domain"]})
    assert card.status_code == 200
    body = card.get_json()
    assert body["name"] == "FOXGLOVE"
    assert "Street Banker" not in card.get_data(as_text=True)
    # Two tenants must never share one cached copy.
    assert "Host" in card.headers.get("Vary", "")


def test_the_tenants_pages_point_at_it(tenant):
    page = tenant["artist"].get("/overview", headers={"Host": tenant["domain"]},
                                follow_redirects=True).get_data(as_text=True)
    assert 'rel="manifest" href="/manifest.webmanifest"' in page


def test_street_banker_keeps_the_static_file(application):
    """It is the name static/js/sw.js precaches, and a static file is
    cacheable at the edge in a way a per-tenant document is not."""
    c = application.test_client()
    email = "own2-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Solo", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    page = c.get("/overview", follow_redirects=True).get_data(as_text=True)
    assert 'rel="manifest" href="/static/manifest.json"' in page


def test_the_card_is_readable_with_no_session(tenant):
    """A browser asks for the manifest with no cookie at all. Behind the
    login wall every tenant would have been handed a redirect."""
    card = tenant["app"].test_client().get(
        "/manifest.webmanifest", headers={"Host": tenant["domain"]})
    assert card.status_code == 200


# --- leak 3: the mail --------------------------------------------------------

def _captured(monkeypatch):
    sent = []
    import email_provider as ep
    monkeypatch.setattr(ep, "configured", lambda: True)
    monkeypatch.setattr(ep, "send",
                        lambda to, subject, html, **kw: sent.append(
                            (to, subject, html)) or True)
    return sent


def test_the_password_reset_email_names_the_tenant(tenant, monkeypatch):
    sent = _captured(monkeypatch)
    tenant["app"].test_client().post(
        "/forgot", data={"email": tenant["artist_email"]},
        headers={"Host": tenant["domain"]})
    assert sent, "nothing was sent"
    _to, subject, html = sent[-1]
    assert subject == "Reset your FOXGLOVE password"
    assert "Street Banker" not in subject
    assert "Street Banker" not in html
    assert "FOXGLOVE account" in html


def test_street_bankers_own_reset_email_is_unchanged(application, monkeypatch):
    sent = _captured(monkeypatch)
    email = "own3-%s@example.net" % uuid.uuid4().hex[:8]
    c = application.test_client()
    c.post("/signup", data={"name": "Solo", "email": email, "password": PASSWORD})
    c.post("/forgot", data={"email": email})
    assert sent[-1][1] == "Reset your Street Banker password"


def test_the_senders_name_and_the_words_inside_cannot_disagree():
    """They did: the display name swapped and the subject did not. One
    resolver now answers both."""
    import email_provider as ep
    assert ep._tenant_display_name() == white_label.tenant_name()


# --- leak 4: how far the accent reaches --------------------------------------

def test_the_accent_reaches_the_page_and_not_just_the_logo(tenant):
    page = tenant["artist"].get("/overview", headers={"Host": tenant["domain"]},
                                follow_redirects=True).get_data(as_text=True)
    assert "--sb-brand-accent: #4fa3d1" in page
    assert "/static/css/white-label.css" in page


def test_street_bankers_own_pages_declare_no_accent(application):
    c = application.test_client()
    email = "own4-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Solo", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    page = c.get("/overview", follow_redirects=True).get_data(as_text=True)
    assert "--sb-brand-accent" not in page, (
        "the platform's own pages must fall through to their own tokens")


def test_an_accent_nothing_can_be_read_on_never_becomes_a_fill():
    """The save-time gate proves the accent is legible AS INK on a dark
    sidebar. It proves nothing about text sitting ON it, which is a
    different pair of colours."""
    # Passes the 3:1 ink gate against the sidebar, but neither black nor
    # white clears AA body text on top of it.
    dim = "#6a6a6a"
    assert brand_contrast.check_accent(dim, {"sidebar": "#0B0A08"})[1] == []
    assert not white_label.accent_fill_ok(dim)
    css = white_label.accent_vars({"accent": dim})
    assert "--sb-brand-accent" in css
    assert "--sb-brand-fill" not in css, "a button nobody can read is worse than gold"


def test_a_workable_accent_does_become_a_fill_with_ink_chosen_for_it():
    css = white_label.accent_vars({"accent": "#E8B950"})
    assert "--sb-brand-fill: #e8b950" in css
    ink, ratio = white_label.accent_ink("#E8B950")
    assert ratio >= brand_contrast.AA_NORMAL
    assert "--sb-brand-on-fill: %s" % ink in css


def test_the_screen_says_so_rather_than_silently_using_gold(tenant):
    r = tenant["admin"].post("/partner/branding",
                             data={"display_name": "FOXGLOVE", "accent": "6a6a6a"})
    assert "Filled buttons keep the platform's gold" in r.get_data(as_text=True)


def test_an_unreadable_accent_is_still_refused_outright(tenant):
    r = tenant["admin"].post("/partner/branding",
                             data={"display_name": "FOXGLOVE", "accent": "1a1a1a"})
    assert "needs 3.0:1" in r.get_data(as_text=True)


# --- leak 5: the logo --------------------------------------------------------

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
       b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")


def _upload(client, data, name="mark.png"):
    from io import BytesIO
    return client.post("/partner/branding", content_type="multipart/form-data",
                       data={"display_name": "FOXGLOVE",
                             "logo": (BytesIO(data), name)})


def test_a_logo_uploads_and_a_tenants_artist_sees_it(tenant):
    r = _upload(tenant["admin"], PNG)
    assert "Saved" in r.get_data(as_text=True)
    with tenant["app"].app_context():
        stored = ps.get_partner(tenant["id"])["logo_path"]
    assert stored.startswith("/uploads/partnerlogo_")
    page = tenant["artist"].get("/overview", headers={"Host": tenant["domain"]},
                                follow_redirects=True).get_data(as_text=True)
    assert stored in page
    assert "streetbanker-logo" not in page


def test_the_file_really_lands_where_the_row_says(tenant):
    _upload(tenant["admin"], PNG)
    with tenant["app"].app_context():
        stored = ps.get_partner(tenant["id"])["logo_path"]
        folder = tenant["app"].config["UPLOADS_DIR"]
    assert os.path.exists(os.path.join(folder, stored[len("/uploads/"):]))


def test_a_logo_can_be_taken_back_off(tenant):
    _upload(tenant["admin"], PNG)
    with tenant["app"].app_context():
        was = ps.get_partner(tenant["id"])["logo_path"]
        folder = tenant["app"].config["UPLOADS_DIR"]
    tenant["admin"].post("/partner/branding",
                         data={"display_name": "FOXGLOVE", "remove_logo": "1"})
    with tenant["app"].app_context():
        assert ps.get_partner(tenant["id"])["logo_path"] == ""
    assert not os.path.exists(os.path.join(folder, was[len("/uploads/"):])), (
        "removing the logo leaves the file behind")


def test_a_replacement_does_not_leave_the_old_file_on_disk(tenant):
    _upload(tenant["admin"], PNG)
    with tenant["app"].app_context():
        first = ps.get_partner(tenant["id"])["logo_path"]
        folder = tenant["app"].config["UPLOADS_DIR"]
    _upload(tenant["admin"], PNG, name="second.png")
    with tenant["app"].app_context():
        second = ps.get_partner(tenant["id"])["logo_path"]
    if second != first:
        assert not os.path.exists(os.path.join(folder, first[len("/uploads/"):]))


def test_an_svg_is_refused_and_says_why(tenant):
    r = _upload(tenant["admin"], b"<svg xmlns='http://www.w3.org/2000/svg'/>",
                name="mark.svg")
    body = r.get_data(as_text=True)
    assert "not a picture" in body or "SVG is a document" in body


def test_a_file_that_is_not_an_image_is_refused(tenant):
    r = _upload(tenant["admin"], b"PK\x03\x04 this is a zip", name="mark.png")
    assert "not an image" in r.get_data(as_text=True)


def test_an_oversized_logo_is_refused_with_its_size(tenant):
    r = _upload(tenant["admin"], b"\x89PNG\r\n\x1a\n" + b"0" * (3 * 1024 * 1024))
    body = r.get_data(as_text=True)
    assert "The limit is 2 MB" in body


def test_a_refusal_changes_nothing(tenant):
    tenant["admin"].post("/partner/branding",
                         data={"display_name": "FOXGLOVE", "tagline": "Keep me"})
    _upload(tenant["admin"], b"nope", name="mark.svg")
    with tenant["app"].app_context():
        assert ps.get_partner(tenant["id"])["tagline"] == "Keep me"


def test_only_a_seat_holding_branding_edit_can_set_one(tenant):
    """A template hiding a button is cosmetic; this is the check."""
    r = tenant["artist"].post("/partner/branding",
                              data={"display_name": "MINE"},
                              headers={"Host": tenant["domain"]})
    assert r.status_code in (403, 404)


def test_the_upload_is_held_like_every_other_upload_here():
    """One whitelist, one cap, and a name the uploader does not choose."""
    assert white_label.LOGO_MAX_BYTES == 2 * 1024 * 1024
    assert "svg" not in white_label.LOGO_EXTENSIONS


# --- what the walk found, which reading never would ------------------------

def test_the_legal_tab_also_keeps_the_operating_entity(tenant):
    """The body and the page band always named Street Banker on these two.
    The TAB said FOXGLOVE until the walk, because the frame appended the
    tenant to every page without exception. legal.html sets title_product."""
    for path in ("/terms", "/privacy"):
        page = tenant["app"].test_client().get(
            path, headers={"Host": tenant["domain"]}).get_data(as_text=True)
        assert _title(page).endswith(white_label.PLATFORM), (
            "%s tab reads %r" % (path, _title(page)))
        assert "FOXGLOVE" not in _title(page)


def test_every_other_tab_is_still_the_tenants(tenant):
    """title_product is for the owner's two exceptions and nothing else."""
    page = tenant["artist"].get("/overview", headers={"Host": tenant["domain"]},
                                follow_redirects=True).get_data(as_text=True)
    assert _title(page).endswith("FOXGLOVE")


def test_the_page_band_eyebrow_swaps_too(tenant):
    """Every internal page opens with the shared band, and its eyebrow read
    "STREET BANKER" directly above the reseller's own name in the sidebar."""
    page = tenant["app"].test_client().get(
        "/product-tour", headers={"Host": tenant["domain"]}).get_data(as_text=True)
    found = re.search(r'pp-eyebrow">([^<]*)', page)
    assert found and "FOXGLOVE" in found.group(1), found and found.group(1)


def test_the_platforms_own_eyebrow_is_untouched(application):
    page = application.test_client().get("/product-tour").get_data(as_text=True)
    found = re.search(r'pp-eyebrow">([^<]*)', page)
    assert found and found.group(1).strip() == "Street Banker"


def test_brand_text_is_reachable_from_an_imported_macro(application):
    """The trap that made the first attempt at this do nothing at all:
    templates/_sb.html is pulled in with {% import %}, which is
    context-free, so a macro inside it cannot see anything the context
    processor provides. A Jinja GLOBAL it can."""
    assert "brand_text" in application.jinja_env.globals
    rendered = application.jinja_env.from_string(
        '{% import "_sb.html" as sb %}'
        '{{ sb.plate(none, [], "Street Banker - Beats", "Registry") }}')
    with application.test_request_context("/"):
        import flask
        flask.g.partner = {"display_name": "FOXGLOVE"}
        out = rendered.render()
    assert "FOXGLOVE - Beats" in out, out[:300]


def test_brand_text_leaves_the_platform_alone():
    assert white_label.brand_text("Street Banker - Beats") == "Street Banker - Beats"
    assert white_label.brand_text("") == ""
    assert white_label.brand_text(None) is None

"""A reseller's artists saw Street Banker everywhere.

Partner OS could guard, roster, grant, act-on-behalf and audit — and the
artists under a reseller still read ROYALTY SWEEP in the sidebar and
Street Banker on the page where they sign in. The partners table had no
logo, no colour, no display name; `branding_edit` was a permission
guarding nothing at all.

Owner's ruling, 2026-09-10: a full swap — shell, login page, email
display name — with ONE exception. Terms and Privacy keep naming Street
Banker LLC, because they describe who actually holds the data and who the
artist is contracting with, and that does not change because somebody
else's logo is above it.
"""
import os
import uuid

import pytest

import brand_contrast
import db as store
import partner_store as ps

PASSWORD = "brand-swap-123"


@pytest.fixture(scope="module")
def application():
    import app as appmod
    return appmod.app


@pytest.fixture
def tenant(application):
    """A reseller with a domain, a brand, and an admin on its console."""
    slug = "nw%s" % uuid.uuid4().hex[:6]
    domain = "app.%s.example" % slug
    with application.app_context():
        pid = ps.create_partner("Northwind Music Group", slug=slug, domain=domain)
        ps.set_branding(pid, display_name="NORTHWIND", accent="#4fa3d1",
                        tagline="Sign. Ship. Get paid.")
    email = "nw-admin-%s@example.net" % uuid.uuid4().hex[:8]
    c = application.test_client()
    c.post("/signup", data={"name": "Admin", "email": email, "password": PASSWORD})
    with application.app_context():
        ps.add_member(pid, email, "Admin", "owner",
                      user_id=store.get_user_by_email(email)["id"])
    c.post("/login", data={"email": email, "password": PASSWORD})
    return {"id": pid, "domain": domain, "client": c, "app": application}


# --- the swap ----------------------------------------------------------------

def test_the_sign_in_page_wears_the_resellers_name(tenant):
    """On their domain the tenant resolves from the hostname before the
    login wall, so the brand is there with no session at all — which is
    exactly when somebody decides whose product this is."""
    anon = tenant["app"].test_client()
    page = anon.get("/login", headers={"Host": tenant["domain"]}).get_data(as_text=True)
    assert "NORTHWIND" in page
    assert "Sign. Ship. Get paid." in page
    assert "streetbanker-logo-light.svg" not in page


def test_street_bankers_own_sign_in_is_untouched(tenant):
    page = tenant["app"].test_client().get("/login").get_data(as_text=True)
    assert "streetbanker-logo-light.svg" in page
    assert "NORTHWIND" not in page


def test_the_shell_wears_it_too(tenant):
    markup = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "templates/base.html"), encoding="utf-8").read()
    assert "brand.name" in markup, "the sidebar reads the tenant"
    assert markup.count("ROYALTY SWEEP") <= 1, (
        "the platform name should survive only as the fallback")


# --- the exception the owner ruled on ---------------------------------------

def test_the_legal_line_still_names_the_operating_entity(tenant):
    """Terms and Privacy describe who holds the data. Branding them as the
    reseller would be an exposure, not a styling choice."""
    anon = tenant["app"].test_client()
    page = anon.get("/login", headers={"Host": tenant["domain"]}).get_data(as_text=True)
    assert "Street Banker LLC" in page


@pytest.mark.parametrize("path", ["/terms", "/privacy"])
def test_the_legal_pages_are_not_swapped(tenant, path):
    anon = tenant["app"].test_client()
    page = anon.get(path, headers={"Host": tenant["domain"]})
    assert page.status_code == 200
    assert "Street Banker" in page.get_data(as_text=True), (
        "%s must keep naming the operating entity" % path)


# --- the accent, which no lock can see --------------------------------------

def test_an_unreadable_accent_is_refused_with_the_contrast_it_managed(tenant):
    r = tenant["client"].post("/partner/branding",
                              data={"display_name": "NORTHWIND", "accent": "1a1a1a"})
    body = r.get_data(as_text=True)
    assert "needs 3.0:1" in body, "say the number, not just no"
    with tenant["app"].app_context():
        assert ps.get_partner(tenant["id"])["accent"] == "#4fa3d1", (
            "a refusal keeps what was there")


def test_a_readable_accent_saves(tenant):
    r = tenant["client"].post("/partner/branding",
                              data={"display_name": "NORTHWIND", "accent": "#E8B950"})
    assert "Your artists see this now" in r.get_data(as_text=True)
    with tenant["app"].app_context():
        assert ps.get_partner(tenant["id"])["accent"] == "#e8b950"


def test_the_contrast_rule_is_shared_with_the_design_suite():
    """The lock reads source for colour literals and cannot see a colour
    from the database. One implementation, so the bar is the same."""
    import io as _io
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with _io.open(os.path.join(here, "tests/test_design_system.py"),
                  encoding="utf-8") as f:
        src = f.read()
    assert "brand_contrast" in src, "a second copy of the maths has grown"


def test_a_blank_name_is_refused(tenant):
    r = tenant["client"].post("/partner/branding",
                              data={"display_name": "   ", "accent": "#E8B950"})
    assert "A name is needed" in r.get_data(as_text=True)


# --- email ------------------------------------------------------------------

def test_the_display_name_swaps_but_the_address_never_does(monkeypatch):
    """SPF and DKIM are published for the verified domain and no other.
    Sending from a partner's domain without their DNS does not fail
    loudly - it lands in spam."""
    import email_provider as ep
    monkeypatch.setenv("EMAIL_FROM", "Street Banker <noreply@streetbankermusic.com>")
    assert ep.sender() == "Street Banker <noreply@streetbankermusic.com>"
    assert ep.sender("Northwind Music Group") == \
        "Northwind Music Group <noreply@streetbankermusic.com>"


def test_a_display_name_cannot_forge_the_address(monkeypatch):
    import email_provider as ep
    monkeypatch.setenv("EMAIL_FROM", "Street Banker <noreply@streetbankermusic.com>")
    forged = ep.sender("Evil <attacker@elsewhere.com>")
    assert forged.count("<") == 1 and "attacker@elsewhere.com" not in forged.split("<")[1]


def test_mail_outside_a_request_is_the_platforms_own():
    import email_provider as ep
    assert ep._tenant_display_name() == ""


# --- nothing changes for a tenant that has not branded ----------------------

def test_an_unbranded_partner_renders_the_platform(application):
    slug = "plain%s" % uuid.uuid4().hex[:6]
    with application.app_context():
        ps.create_partner("Plain Partner", slug=slug,
                          domain="app.%s.example" % slug)
    page = application.test_client().get(
        "/login", headers={"Host": "app.%s.example" % slug}).get_data(as_text=True)
    # branding() falls back to the partner's own name, never to a blank.
    assert "Plain Partner" in page or "Street Banker" in page
    assert "None" not in page.replace("NoneType", "")

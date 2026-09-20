"""Billing must not tell a paying artist that nothing is charged.

/billing stacked two sections. The upper one is a showcase: an invented
renewal date, three hardcoded "Paid" invoices, usage tiles read from
royalty_data's seed catalogue rather than the account, and a line reading
"Demo only - no payment method is stored or charged".

The lower one is a live Stripe Checkout.

With STRIPE_SECRET_KEY set, both rendered. An artist paying every month was
shown somebody else's invoices and told they were not being charged, thirty
lines above the button that charges them. That is not a disclaimer that needed
rewording.

The first fix hid the upper block wherever Stripe was live, which left it
rendering on every deployment without a key. The 2026-09-20 walk read it
there, on a fresh Artist: a plan it had not bought, a renewal date and
three invoices marked Paid. A missing payment provider is not a licence to
invent a billing history, so the block is a sample and it belongs to the
demo logins alone.
"""
import re
import uuid

import pytest

import stripe_provider


@pytest.fixture(scope="module")
def application():
    import app as appmod
    return appmod.app


@pytest.fixture
def payer(application):
    email = "billing-%s@example.net" % uuid.uuid4().hex[:8]
    client = application.test_client()
    client.post("/signup", data={"name": "Payer", "email": email,
                                 "password": "bl-pass-123"})
    client.post("/login", data={"email": email, "password": "bl-pass-123"})
    return client


@pytest.fixture
def stripe_live(monkeypatch):
    """A deployment with a real payment provider configured."""
    monkeypatch.setattr(stripe_provider, "configured", lambda: True)


def _text(client):
    body = client.get("/billing").get_data(as_text=True)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


# --- the sentence that was false -------------------------------------------

def test_a_live_deployment_never_says_nothing_is_charged(payer, stripe_live):
    """The whole point. It sat directly above a working Subscribe button."""
    assert "Demo only" not in _text(payer)
    assert "no payment method is stored or charged" not in _text(payer)


def test_a_live_deployment_shows_no_fabricated_invoices(payer, stripe_live):
    """Three hardcoded rows marked Paid, shown to accounts that really are
    paying - their actual invoices are in Stripe's portal."""
    body = _text(payer)
    for invented in ("INV-2026-06", "INV-2026-05", "INV-2026-04"):
        assert invented not in body


def test_a_live_deployment_shows_no_invented_renewal_date(payer, stripe_live):
    assert "Renews 2026-08-01" not in _text(payer)


def test_a_live_deployment_hides_the_whole_showcase_block(payer, stripe_live):
    """Not just the sentence. The plan table, the usage tiles and the
    non-functional "Choose" buttons are all part of the same fiction."""
    assert "Compare Plans" not in _text(payer)


# --- and still works ------------------------------------------------------

def test_a_live_deployment_still_offers_checkout(payer, stripe_live):
    """Removing the showcase must not remove the product."""
    body = _text(payer)
    assert "Subscribe" in body
    assert "Billing" in body, "the page lost its heading with the legacy block"


def test_the_live_page_says_where_the_real_invoices_are(payer, stripe_live):
    """The showcase's invoice list is gone, so the page has to point at the
    thing that replaced it rather than leaving a hole."""
    body = _text(payer).lower()
    assert "portal" in body or "invoices" in body


def test_the_live_page_states_it_holds_no_card(payer, stripe_live):
    assert "never stores a card number" in _text(payer)


# --- who the showcase was written for --------------------------------------

def test_without_a_provider_a_real_account_still_sees_no_sample(payer):
    """This file used to allow the showcase wherever Stripe was missing. The
    2026-09-20 walk read it on a fresh Artist on a deployed service with no
    Stripe key: a plan it had not bought, a renewal date and three invoices
    marked Paid, none of them its own. A missing payment provider is not a
    licence to invent an account's billing history, so the block belongs to
    the demo logins and to nobody else."""
    body = _text(payer)
    assert "Demo only" not in body
    assert "INV-2026-06" not in body


def test_the_demo_login_is_the_one_that_sees_it(application):
    """The sample is not deleted. It is the demo tour's billing page."""
    demo = application.test_client()
    demo.post("/login", data={"email": "demo@streetbanker.io", "password": "sweep"})
    body = _text(demo)
    assert "Demo only" in body
    assert "INV-2026-06" in body


def test_the_page_always_has_a_heading(payer):
    """The sample carried the only h1, so narrowing it to the demo left a
    real account on a service with no payments reading an untitled page."""
    assert '<h1 class="sb-h1">Billing</h1>' in payer.get("/billing").get_data(as_text=True)


def test_the_guard_is_the_same_one_the_checkout_uses(application):
    """real_checkout drives the Subscribe button and is_demo_account drives
    the sample, both settled once at the top. Two separate conditions would
    eventually disagree, and the disagreement would look exactly like the
    bug this file is about."""
    import io

    template = io.open("templates/billing.html", encoding="utf-8").read()
    assert template.count("{% set real_checkout") == 1, \
        "real_checkout must be computed once, at the top"

    guard = template.index("{% set real_checkout")
    showcase = template.index("{% if is_demo_account %}")
    assert guard < showcase, "the sample must be settled above everything it feeds"

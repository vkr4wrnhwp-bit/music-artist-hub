"""The footer row, and the legal links that were never linked.

Two owner asks on 2026-09-22: "submit music can be removed from studio and
you can move that into the footer", and "shouldn't we have a footer anyways
for policies and all the legal things that we would need".

The second one matters more than it sounds. /terms and /privacy were
already pages and nothing in the whole app pointed at them, so the only way
to read the terms you are bound by was to know the URL.
"""
import re

import pytest

import hubs
import rooms


def test_everyone_gets_the_legal_links_whatever_they_pay():
    """A person is bound by the terms whether or not they bought anything."""
    for plan in ("", "artist", "pro", "label", None):
        got = {k for k, _h, _l in hubs.footer_links(plan)}
        assert {"terms", "privacy", "contact"} <= got, plan


def test_submit_music_is_label_only_and_nobody_elses():
    assert "submit" in {k for k, _h, _l in hubs.footer_links("label")}
    for plan in ("artist", "pro", ""):
        assert "submit" not in {k for k, _h, _l in hubs.footer_links(plan)}, plan


def test_every_footer_link_goes_somewhere_real(client_app):
    """A footer link that 404s is worse than no footer."""
    app_obj, client = client_app
    for _key, href, label in hubs.footer_links("label"):
        r = client.get(href, follow_redirects=False)
        assert r.status_code in (200, 302), "%s (%s) -> %s" % (label, href, r.status_code)


def test_submit_music_left_the_rooms_and_the_sidebar():
    """It was in Releases and in the sidebar's Label Services group. A page
    in a room AND the footer is in two places at once."""
    for _key, _label, _desc, cards in rooms.ROOMS:
        assert "submit" not in cards
    flat = repr(hubs.LABEL_GROUP)
    assert '"/submit"' not in flat and "'/submit'" not in flat


def test_the_legal_pages_are_not_label_gated():
    """LABEL_ONLY is for what a Label plan buys. Terms are not a feature."""
    assert "terms" not in rooms.LABEL_ONLY
    assert "privacy" not in rooms.LABEL_ONLY


@pytest.fixture
def client_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    import app as appmod
    a = appmod.create_app()
    a.config.update(TESTING=True)
    return a, a.test_client()


def test_the_row_is_rendered_for_a_signed_in_page(client_app, monkeypatch):
    import uuid
    from werkzeug.security import generate_password_hash
    import db as store
    app_obj, client = client_app
    with app_obj.app_context():
        uid = store.create_user("f-%s@example.net" % uuid.uuid4().hex[:8], "A",
                                generate_password_hash("a-long-password"))
        store.set_user_plan(uid, "label")
    with client.session_transaction() as sess:
        sess["user_id"] = uid
    page = client.get("/command-center").get_data(as_text=True)
    assert 'href="/terms"' in page
    assert 'href="/privacy"' in page
    assert 'href="/submit"' in page
    assert 'aria-label="More"' in page

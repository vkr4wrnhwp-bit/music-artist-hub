"""There was no way to take a press kit down.

Reported live, 2026-09-10. Every piece could be cleared on its own —
the photo, one asset slot, the share link — and the kit itself could
not. Somebody who wanted to start again had to empty it field by field,
and still kept the slug it was published at and the pitch token they
were trying to be rid of.

What must hold: the kit goes, its public address stops answering, the
pitch link and its open log go with it, files this app wrote are
unlinked, and files that belong to the Vault are left exactly where
they are because the Vault still lists and owns them.
"""
import os
import uuid

import pytest

import app as appmod
import db as store

PASSWORD = "epk-del-123"


@pytest.fixture
def artist():
    c = appmod.app.test_client()
    email = "epk-%s@example.net" % uuid.uuid4().hex[:8]
    c.post("/signup", data={"name": "Artist", "email": email, "password": PASSWORD})
    c.post("/login", data={"email": email, "password": PASSWORD})
    with appmod.app.app_context():
        c._uid = store.get_user_by_email(email)["id"]
    return c


def _kit(uid, slug):
    with appmod.app.app_context():
        store.save_epk(uid, {"tagline": "Loud and from Flint"})
        store.set_epk_slug(uid, slug)
        store.save_epk_photo(uid, "/uploads/epk_%s.jpg" % uid)
        store.save_epk_asset(uid, "logo", "/uploads/epkasset_%s_logo.png" % uid)
        store.upsert_epk_share(uid, "tok-" + slug, pin="", audio=[])
        store.log_epk_event("tok-" + slug, "open", "a label")


def test_the_whole_kit_comes_down(artist):
    slug = "kit-%s" % uuid.uuid4().hex[:6]
    _kit(artist._uid, slug)
    assert artist.post("/epk/delete").status_code == 302

    with appmod.app.app_context():
        assert store.get_epk(artist._uid) is None, "the written kit"
        assert store.get_epk_assets(artist._uid) == [], "the uploaded assets"
        assert store.get_epk_share(artist._uid) is None, "the pitch link"
        assert store.get_epk_by_slug(slug) is None, (
            "the public address must stop answering")


def test_the_pitch_links_open_log_goes_with_it(artist):
    slug = "log-%s" % uuid.uuid4().hex[:6]
    _kit(artist._uid, slug)
    with appmod.app.app_context():
        assert store.epk_share_stats("tok-" + slug)
    artist.post("/epk/delete")
    with appmod.app.app_context():
        assert store.get_epk_share_by_token("tok-" + slug) is None, (
            "a record of who opened something the artist just destroyed")


def test_a_file_from_the_vault_is_not_unlinked(artist):
    """The Vault still lists and owns it — clearing the kit must not
    reach into somebody's archive and delete the original."""
    shared = "/uploads/vault_something_shared.png"
    with appmod.app.app_context():
        store.save_epk(artist._uid, {})
        store.save_epk_asset(artist._uid, "logo", shared)
        uploads = os.path.join(os.path.dirname(store.db_path()), "uploads")
        target = os.path.join(uploads, "vault_something_shared.png")
        os.makedirs(uploads, exist_ok=True)
        with open(target, "wb") as f:
            f.write(b"not mine to delete")
    artist.post("/epk/delete")
    assert os.path.exists(target), "the Vault's own file was destroyed"
    os.remove(target)


def test_deleting_a_kit_that_was_never_made_is_not_an_error(artist):
    assert artist.post("/epk/delete").status_code == 302
    with appmod.app.app_context():
        assert store.get_epk(artist._uid) is None


def test_a_signed_out_visitor_cannot_delete_anything(artist):
    slug = "anon-%s" % uuid.uuid4().hex[:6]
    _kit(artist._uid, slug)
    anon = appmod.app.test_client()
    anon.post("/epk/delete")
    with appmod.app.app_context():
        assert store.get_epk(artist._uid) is not None, "still there"


def test_one_artists_delete_does_not_touch_another(artist):
    slug_a = "a-%s" % uuid.uuid4().hex[:6]
    _kit(artist._uid, slug_a)
    other = appmod.app.test_client()
    email = "epk-other-%s@example.net" % uuid.uuid4().hex[:8]
    other.post("/signup", data={"name": "Other", "email": email, "password": PASSWORD})
    other.post("/login", data={"email": email, "password": PASSWORD})
    other.post("/epk/delete")
    with appmod.app.app_context():
        assert store.get_epk(artist._uid) is not None

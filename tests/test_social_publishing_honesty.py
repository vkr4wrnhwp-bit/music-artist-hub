"""The socials page implied a capability that does not exist.

A platform whose environment variables happened to be present was
labelled "configured", which reads as connected and working. Nothing in
this product can publish to any platform: social_providers had no upload
code, for YouTube or anything else, and still does not.

That mattered because the owner read the page and reasonably concluded
YouTube was ready to post. A status word must not be able to say more
than the code behind it can do.
"""
import social_providers as sp


def test_nothing_can_publish_automatically_yet():
    assert not sp.any_automatic_publishing(), (
        "if this changed, the page's copy has to change with it")


def test_the_word_configured_is_gone(monkeypatch):
    """It was the word doing the lying."""
    for var in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"):
        monkeypatch.setenv(var, "present-but-useless")
    statuses = {key: status for key, _name, status in sp.provider_status()}
    assert statuses["youtube"] != "configured"
    assert statuses["youtube"] == "not connected", (
        "credentials on the deployment are not a connection")


def test_only_manual_reads_ready(monkeypatch):
    for var in ("META_APP_ID", "META_APP_SECRET", "X_API_KEY", "X_API_SECRET"):
        monkeypatch.setenv(var, "x")
    for key, _name, status in sp.provider_status():
        if key == "manual":
            assert status == "ready", "a person posting is a working route"
        else:
            assert status != "ready", (
                "%s has no upload path and must not read as ready" % key)


def test_can_publish_answers_for_each_route():
    assert sp.can_publish("manual")
    for key in ("youtube", "meta", "tiktok", "x", "threads", "linkedin", "snapchat"):
        assert not sp.can_publish(key)
    assert not sp.can_publish("something-invented")

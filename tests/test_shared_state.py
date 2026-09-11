"""One account's action must not change what another account reads.

Street Banker runs as a single process. A module-level dict, list or set
that a request handler writes is therefore shared by every signed-in
account on the deployment, and the page renders one person's state to
everybody. The audit of 2026-09-10 found the shape four times:

  discover_config._likes / ._follows   a like drew a filled heart on
                                       somebody else's page
  network_config._connections etc.     A's pending connection appeared
                                       on B's My Network tab
  royalty_data._split_overrides        alice's split was readable,
                                       editable and deletable by bob
  royalty_data._claim_status_overrides a second account could reject the
                                       first account's claim

The two reachable ones were moved into the session. The rest were
mutated only by endpoints nothing in the product linked to - no template,
no script, no url_for - so the endpoints were deleted rather than fixed:
a demo dict nobody can reach is harmless, and an address that answers is
not.

These tests hold both halves of that. They are deliberately blunt: the
cheapest way for this family to come back is somebody re-adding a
convenient route to a helper that is still sitting there.
"""
import uuid

import pytest

from app import create_app


@pytest.fixture
def app_obj():
    return create_app()


def _account(app_obj):
    """A signed-in client on its own fresh account.

    Not the demo login: that account is shared by every test in the suite
    and by anyone who asks /demo-access for the password, so two "demo"
    clients are not two accounts and would prove nothing here.
    """
    client = app_obj.test_client()
    client.post("/signup", data={
        "name": "Owner", "password": "sharedstate1",
        "email": "shared-%s@example.net" % uuid.uuid4().hex[:10]})
    return client


# The addresses removed on 2026-09-10. Each wrote a process-global dict in
# royalty_data with no user key and no ownership check.
DELETED = [
    ("POST", "/connections/spotify/connect"),
    ("POST", "/connections/spotify/disconnect"),
    ("GET", "/songs/midnight-drive"),
    ("POST", "/songs/midnight-drive/splits"),
    ("POST", "/songs/midnight-drive/splits/0/remove"),
    ("POST", "/songs/midnight-drive/splits/0/toggle"),
    ("POST", "/claims/youtube-music-uncollected/advance"),
    ("POST", "/claims/youtube-music-uncollected/reject"),
    ("POST", "/fixes/some-item/status"),
    ("POST", "/alerts/pending-negotiation/resolve"),
]


@pytest.mark.parametrize("method,path", DELETED)
def test_the_deleted_shared_state_endpoints_stay_deleted(app_obj, method, path):
    """Not a 403 or a redirect - nothing should be listening at all."""
    rules = {r.rule for r in app_obj.url_map.iter_rules()}
    generic = path.split("/")[1]
    live = {r for r in rules if r.split("/")[1:2] == [generic]}
    assert not any(
        "<" in r and r.count("/") == path.count("/") for r in live), (
        "%s is registered again: %s" % (path, sorted(live)))


def test_discover_likes_belong_to_one_browser(app_obj):
    mine, theirs = _account(app_obj), _account(app_obj)
    assert mine.post("/discover/like/tr-1").get_json()["count"] == 1
    assert theirs.post("/discover/like/tr-1").get_json()["count"] == 1, (
        "their first like is their first, not their second")
    assert theirs.post("/discover/like/tr-2").get_json()["count"] == 2
    assert mine.post("/discover/like/tr-1").get_json() == {
        "ok": True, "liked": False, "count": 0}, (
        "mine toggles off my own like, untouched by theirs")


def test_discover_follows_belong_to_one_browser(app_obj):
    """Read through the toggle, not the HTML.

    The rendered page carries the string "Following" either way - it is
    in the inline script that swaps the button label - so counting it
    proves nothing. The toggle does: if the two accounts shared a set,
    the second follow would turn the first one OFF and come back False.
    """
    mine, theirs = _account(app_obj), _account(app_obj)
    assert mine.post("/discover/follow/nova-reign").get_json() == {
        "ok": True, "following": True, "count": 1}
    assert theirs.post("/discover/follow/nova-reign").get_json() == {
        "ok": True, "following": True, "count": 1}, (
        "their follow is their first, not a toggle of mine")
    assert mine.post("/discover/follow/nova-reign").get_json()["following"] is False, (
        "and mine was still on file to be turned off")


def test_my_network_is_one_accounts_own(app_obj):
    """The tab that says "private to you".

    Account A connecting to a profile used to put that connection on
    account B's My Network tab, because network_config held one dict for
    the whole process.
    """
    mine, theirs = _account(app_obj), _account(app_obj)
    assert mine.post("/network/kilo-byte/connect").get_json()["status"] == "Pending"
    assert mine.post("/network/playlist/late-night-synth/submit",
                     json={"song": "Midnight Drive"}).get_json()["ok"]

    theirs_tab = theirs.get("/network?tab=my").get_data(as_text=True)
    assert "Kilo Byte" not in theirs_tab, "my connection is not their connection"
    assert "Midnight Drive" not in theirs_tab, "nor my submission their submission"

    mine_tab = mine.get("/network?tab=my").get_data(as_text=True)
    assert "Kilo Byte" in mine_tab and "Late Night Synth" in mine_tab


def test_a_claimed_moment_carries_one_owners_serial(app_obj):
    """The worst of the five: a serial number is a claim of ownership.

    Read it off the My Network tab, which lists only the moments this
    visitor claimed. The moment page itself prints the serial either way
    and its inline script contains the word "Owned" whatever the state,
    so neither is evidence.
    """
    mine, theirs = _account(app_obj), _account(app_obj)
    assert mine.post("/network/moment/mo-1/claim").get_json()["serial"] == "SB-1-0001"
    assert "SB-1-0001" not in theirs.get("/network?tab=my").get_data(as_text=True), (
        "my serial must not appear among their owned moments")
    assert "SB-1-0001" in mine.get("/network?tab=my").get_data(as_text=True)


def test_network_config_holds_no_state_of_its_own():
    import network_config

    bare = [n for n, v in vars(network_config).items()
            if isinstance(v, (set, dict, list)) and not n.isupper()
            and not n.startswith("__")]
    assert bare == [], (
        "network_config grew module-level mutable state again: %s" % bare)


def test_discover_config_holds_no_state_of_its_own():
    """The guard that matters: there is nothing left to share.

    Keyed-by-user state is fine and common here. What is not fine is a
    bare container at module level that a handler writes.
    """
    import discover_config

    bare = [n for n, v in vars(discover_config).items()
            if isinstance(v, (set, dict)) and not n.isupper()
            and not n.startswith("__")]
    assert bare == [], (
        "discover_config grew module-level mutable state again: %s" % bare)

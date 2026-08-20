"""Progressive disclosure — the rules, and the state behind them.

The invariant that matters most is the first test: a module whose own
trigger is locked can never be opened by the person it is hiding from.
That is a trap the config makes easy to walk into and impossible to see
by reading, so it is proved here rather than reviewed.
"""
import uuid

import pytest

import db as store
import unlock_rules
import unlock_store
from app import create_app


@pytest.fixture(scope="module")
def app_ready():
    """create_app seeds demo accounts, which is also what the one-time
    backfill runs against — so the fixture exercises the real order."""
    return create_app()


def _account(app_ready, label="Unlock Artist"):
    """A genuinely new account. conftest puts the rest of the suite in
    full mode so those tests can get at the features they are about; this
    file is the one that proves what a first day actually looks like, so
    it opts back into simple mode explicitly."""
    email = "unlock-%s@example.net" % uuid.uuid4().hex[:8]
    client = app_ready.test_client()
    client.post("/signup", data={"name": label, "email": email,
                                 "password": "unlock-secret-1"})
    client.post("/login", data={"email": email, "password": "unlock-secret-1"})
    user = store.get_user_by_email(email)
    unlock_store.set_mode(user["id"], unlock_store.SIMPLE)
    return client, user


# --- the config is coherent -------------------------------------------------

def test_no_module_is_locked_behind_its_own_trigger():
    """A circular lock: Royalty Sweep opens when you upload a statement,
    so if the statements page were itself inside the Sweep, a simple-mode
    account could never get out. Every trigger's route must stay open."""
    for milestone, needed_key in unlock_rules.TRIGGER_ROUTES.items():
        assert not unlock_rules.is_gated(needed_key), (
            "%s is the way to earn %s, and it is gated — nobody in simple "
            "mode could ever satisfy it" % (needed_key, milestone))


def test_everything_promised_as_always_visible_really_is():
    for key in unlock_rules.ALWAYS_VISIBLE:
        assert not unlock_rules.is_gated(key), key


def test_gated_keys_are_real_modules():
    """A rule pointing at a key the nav does not have is a rule that
    silently does nothing."""
    import hubs

    known = {k for _hk, _n, _t, items in hubs.HUBS for k, *_ in items}
    for group in (hubs.LABEL_GROUP, hubs.COMMUNITY_GROUP, hubs.ACCOUNT_GROUP):
        known |= {k for k, *_ in group[1]}
    for key in unlock_rules.gated_keys() | set(unlock_rules.ALWAYS_VISIBLE):
        assert key in known, "%s is not a module in hubs.py" % key


def test_every_gated_module_says_how_to_open_it():
    for key in unlock_rules.gated_keys():
        text = unlock_rules.hint(key)
        assert text.startswith("Unlocks"), key
        assert len(text) > 20, key


# --- rules evaluate ---------------------------------------------------------

def test_the_thresholds_are_the_only_numbers_that_decide():
    below = {"smart_link_visit_count": unlock_rules.FAN_INTELLIGENCE_VISITS - 1}
    at = {"smart_link_visit_count": unlock_rules.FAN_INTELLIGENCE_VISITS}
    assert "audience" not in unlock_rules.unlocked_keys({}, below)
    assert "audience" in unlock_rules.unlocked_keys({}, at)


def test_either_rule_opens_on_whichever_arrives_first():
    by_statement = unlock_rules.unlocked_keys({"statement_uploaded": "now"}, {})
    by_releases = unlock_rules.unlocked_keys(
        {}, {"releases_count": unlock_rules.SWEEP_RELEASES})
    assert "overview" in by_statement
    assert "overview" in by_releases
    assert "overview" not in unlock_rules.unlocked_keys(
        {}, {"releases_count": unlock_rules.SWEEP_RELEASES - 1})


def test_partnership_needs_more_than_the_sweep():
    counters = {"releases_count": unlock_rules.SWEEP_RELEASES}
    opened = unlock_rules.unlocked_keys({}, counters)
    assert "overview" in opened
    assert "deal-room" not in opened
    counters = {"releases_count": unlock_rules.PARTNERSHIP_RELEASES}
    assert "deal-room" in unlock_rules.unlocked_keys({}, counters)


# --- per-account state ------------------------------------------------------

def test_a_new_account_starts_simple_with_the_gated_set_closed(app_ready):
    _client, user = _account(app_ready)
    state = unlock_store.state(user["id"])
    assert state["mode"] == unlock_store.SIMPLE
    assert state["locked"] == unlock_rules.gated_keys()
    assert state["unlocked"] == set()


def test_accounts_that_existed_before_this_shipped_keep_everything(app_ready):
    """The promise in the brief. The demo accounts are seeded by
    create_app before init_unlocks runs, so they stand in for everybody
    who was already using the platform."""
    demo = store.get_user_by_email("demo@streetbanker.io")
    assert demo is not None
    state = unlock_store.state(demo["id"])
    assert state["mode"] == unlock_store.FULL
    assert state["locked"] == set()


def test_a_milestone_opens_its_module_and_only_its_module(app_ready):
    _client, user = _account(app_ready)
    opened = unlock_store.flag(user["id"], "second_contributor_added")
    assert set(opened) == {"conflicts", "disputes"}
    state = unlock_store.state(user["id"])
    assert "conflicts" in state["unlocked"]
    assert "overview" in state["locked"]


def test_an_unlock_latches_and_cannot_be_taken_away(app_ready):
    """Counts fall, dates pass. A module somebody has started using does
    not close behind them."""
    _client, user = _account(app_ready)
    unlock_store.bump(user["id"], "smart_link_visit_count",
                      unlock_rules.FAN_INTELLIGENCE_VISITS)
    assert "audience" in unlock_store.state(user["id"])["unlocked"]

    # Wipe the counter underneath it — the latch holds.
    import json
    with store.get_db() as db:
        db.execute("UPDATE user_unlocks SET counters = ? WHERE user_id = ?",
                   (json.dumps({"smart_link_visit_count": 0}), user["id"]))
    assert "audience" in unlock_store.state(user["id"])["unlocked"]


def test_flags_are_idempotent_and_announce_once(app_ready):
    _client, user = _account(app_ready)
    first = unlock_store.flag(user["id"], "release_scheduled_2wk_out")
    second = unlock_store.flag(user["id"], "release_scheduled_2wk_out")
    assert first == ["rollout"]
    assert second == []


def test_a_total_never_goes_backwards(app_ready):
    _client, user = _account(app_ready)
    unlock_store.set_count(user["id"], "releases_count", 5)
    unlock_store.set_count(user["id"], "releases_count", 1)
    assert unlock_store.state(user["id"])["counters"]["releases_count"] == 5


def test_unknown_milestones_are_refused_rather_than_stored(app_ready):
    _client, user = _account(app_ready)
    assert unlock_store.flag(user["id"], "not_a_milestone") == []
    assert unlock_store.bump(user["id"], "not_a_counter", 10) == []
    assert unlock_store.state(user["id"])["flags"] == {}


# --- the escape hatch -------------------------------------------------------

def test_full_mode_opens_everything_instantly_and_reverses(app_ready):
    _client, user = _account(app_ready)
    assert unlock_store.state(user["id"])["locked"] == unlock_rules.gated_keys()

    unlock_store.set_mode(user["id"], unlock_store.FULL)
    state = unlock_store.state(user["id"])
    assert state["locked"] == set()
    assert state["unlocked"] == unlock_rules.gated_keys()

    unlock_store.set_mode(user["id"], unlock_store.SIMPLE)
    assert unlock_store.state(user["id"])["locked"] == unlock_rules.gated_keys()


def test_full_mode_accounts_are_not_told_things_have_unlocked(app_ready):
    """Nothing was hidden from them, so nothing opened."""
    _client, user = _account(app_ready)
    unlock_store.set_mode(user["id"], unlock_store.FULL)
    assert unlock_store.flag(user["id"], "statement_uploaded") == []
    assert unlock_store.pending_notices(user["id"]) == []


# --- the unlock moment ------------------------------------------------------

def test_one_action_that_opens_five_modules_says_so_once(app_ready):
    """Uploading a statement opens the whole money hub. Five banners about
    one action is noise, and noise is what gets dismissed unread."""
    _client, user = _account(app_ready)
    opened = unlock_store.flag(user["id"], "statement_uploaded")
    assert len(opened) == 5
    assert unlock_store.pending_notices(user["id"]) == ["royalty-sweep"]


def test_a_notice_is_queued_once_and_never_returns(app_ready):
    _client, user = _account(app_ready)
    unlock_store.flag(user["id"], "statement_uploaded")
    assert "royalty-sweep" in unlock_store.pending_notices(user["id"])

    unlock_store.dismiss_notice(user["id"], "royalty-sweep")
    assert unlock_store.pending_notices(user["id"]) == []

    # Re-earning it does not bring the notice back.
    unlock_store.bump(user["id"], "releases_count", unlock_rules.SWEEP_RELEASES)
    assert unlock_store.pending_notices(user["id"]) == []



# --- what a first day actually looks like -----------------------------------

def test_a_locked_route_turns_you_around_and_says_why(app_ready):
    client, _user = _account(app_ready)
    response = client.get("/audience")
    assert response.status_code == 302
    assert response.headers["Location"] == "/command-center?locked=audience"

    body = client.get("/command-center?locked=audience").get_data(as_text=True)
    assert "Not open yet" in body
    assert unlock_rules.hint("audience") in body
    # And the way out is offered rather than hidden.
    assert "show everything now" in body


def test_the_workspace_a_new_account_needs_is_never_locked(app_ready):
    client, _user = _account(app_ready)
    for path in ("/releases", "/links", "/tracks", "/command-center",
                 "/settings"):
        assert client.get(path).status_code == 200, path


def test_the_sidebar_dims_a_locked_module_instead_of_hiding_it(app_ready):
    client, _user = _account(app_ready)
    body = client.get("/command-center").get_data(as_text=True)
    # Still present — this is disclosure, not removal.
    assert 'href="/audience"' in body
    assert 'data-unlock="locked"' in body
    assert "opacity-60" in body
    assert unlock_rules.hint("audience") in body


def test_earning_it_opens_the_route_and_announces_it_once(app_ready):
    client, user = _account(app_ready)
    assert client.get("/rollout-studio").status_code == 302

    unlock_store.flag(user["id"], "release_scheduled_2wk_out")
    assert client.get("/rollout-studio").status_code == 200

    body = client.get("/command-center").get_data(as_text=True)
    assert "Now open" in body
    assert unlock_rules.OPENED["rollout"] in body

    client.post("/unlocks/rollout/dismiss")
    body = client.get("/command-center").get_data(as_text=True)
    assert "Now open" not in body


def test_the_escape_hatch_works_from_the_settings_page(app_ready):
    client, user = _account(app_ready)
    assert client.get("/audience").status_code == 302

    page = client.get("/settings").get_data(as_text=True)
    assert "How much of the app you see" in page
    assert "Show me everything" in page

    client.post("/settings/disclosure", data={"mode": "full"})
    assert client.get("/audience").status_code == 200
    assert unlock_store.state(user["id"])["mode"] == unlock_store.FULL

    client.post("/settings/disclosure", data={"mode": "simple"})
    assert client.get("/audience").status_code == 302


def test_turning_everything_on_and_off_again_keeps_what_was_earned(app_ready):
    client, user = _account(app_ready)
    unlock_store.flag(user["id"], "release_scheduled_2wk_out")
    client.post("/settings/disclosure", data={"mode": "full"})
    client.post("/settings/disclosure", data={"mode": "simple"})
    assert "rollout" in unlock_store.state(user["id"])["unlocked"]
    assert client.get("/rollout-studio").status_code == 200


def test_a_module_the_plan_blocks_is_left_to_the_plan_to_explain(app_ready):
    """The two systems overlap. Where a higher plan is the real answer,
    promising "unlocks when you upload a statement" would be a promise the
    product cannot keep — so the plan gate answers instead."""
    client, _user = _account(app_ready)
    response = client.get("/overview")          # pro tier, gated by plan
    assert response.status_code == 402
    body = client.get("/command-center").get_data(as_text=True)
    assert unlock_rules.hint("overview") not in body


def test_every_group_has_something_to_say_when_it_opens():
    groups = {unlock_rules.group_of(k) for k in unlock_rules.gated_keys()}
    for group in groups:
        assert group in unlock_rules.OPENED, group
        assert len(unlock_rules.OPENED[group]) > 25, group

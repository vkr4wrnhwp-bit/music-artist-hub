"""The Audio Studio's off-state instructions have to be followable.

Every lane is off until a deployment switches it on, which is deliberate -
these calls cost money. So the page lists the environment variables each lane
needs. The failure this covers is subtler than a missing feature: the
instructions were incomplete. AUDIO_INTELLIGENCE_ENABLED gates every lane and
was named nowhere, so an operator could set all six flags the page listed,
reload, and find the Studio exactly as dead as before - with the page still
telling them to set the flags they had just set.
"""
import os

import pytest


@pytest.fixture
def env():
    """Flags are read from os.environ at call time, so they must be restored."""
    from audio_policy import FLAGS
    saved = {name: os.environ.get(name) for name in FLAGS}
    yield os.environ
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def _all_off(env):
    from audio_policy import FLAGS
    for name in FLAGS:
        env.pop(name, None)


def test_following_the_pages_instructions_switches_the_lane_on(env):
    """The property that matters: do what the page says, get what it offers.

    Red before the fix - the instructions omitted the master flag, so setting
    everything they named left every lane off.
    """
    import audio_studio

    _all_off(env)
    for lane in audio_studio._lanes_for_render():
        if lane["title"] == "Artist Voice Vault":
            continue          # deliberately off: the consent flow is not built
        _all_off(env)
        for name in lane["flag"].split(" and "):
            env[name.strip()] = "1"
        after = [x for x in audio_studio._lanes_for_render()
                 if x["title"] == lane["title"]][0]
        assert after["on"], "%s: set %s and it is still off" % (
            lane["title"], lane["flag"])


def test_the_master_flag_is_named_on_every_lane(env):
    """It gates all of them, so leaving it out of any one is a dead end."""
    import audio_studio

    _all_off(env)
    for lane in audio_studio._lanes_for_render():
        assert "AUDIO_INTELLIGENCE_ENABLED" in lane["flag"], lane["title"]


def test_the_voice_vault_stays_off_however_many_flags_are_set(env):
    """A voice can only be registered by its owner, through a verification
    step this app does not implement. No flag may switch that on."""
    import audio_studio
    from audio_policy import FLAGS

    for name in FLAGS:
        env[name] = "1"
    vault = [x for x in audio_studio._lanes_for_render()
             if x["title"] == "Artist Voice Vault"][0]
    assert not vault["on"]

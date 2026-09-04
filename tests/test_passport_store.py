"""Show Passport phase 2: the record, and the promise that it does not move.

The load-bearing requirement in the brief is immutability: "every published
passport must be immutable" and "later passport edits must not silently change
historical shows". Everything else here is bookkeeping; that one is the product.
So most of this file is about a published version refusing to change when the
draft underneath it does.
"""
import pytest

import db as store
import passport_store as ps
from db import get_db


@pytest.fixture(scope="module", autouse=True)
def schema():
    # The stage plot lives in db.py's schema now, not in a table of our own.
    store.init_db()
    ps.init_passports()


@pytest.fixture
def passport():
    pid = ps.create_passport("user-tests", artist_name="Prayers",
                             production_name="No Tengo Calma",
                             emergency_contact="Tour manager 555-0100")
    ps.add_row("personnel", pid, kind="performer", name="Leafar", role="Vocal",
               instruments="Voice", sort=1)
    ps.add_row("inputs", pid, channel="1", source="Kick", mic_di="Beta 91",
               phantom="1", required="1", sort=1)
    ps.add_row("outputs", pid, mix_name="Mix 1", performer="Leafar", kind="iem",
               safe_start="-20 dB, vocal only", sort=1)
    return pid


# --- the draft ---------------------------------------------------------------

def test_a_new_passport_has_no_version_in_force(passport):
    """Never published is a real state, not a missing one: there is nothing a
    show could be advanced against yet."""
    head = ps.get_passport(passport, "user-tests")
    assert head["current_version_id"] is None
    assert ps.current_version(passport, "user-tests") is None


def test_another_account_cannot_read_the_passport(passport):
    assert ps.get_passport(passport, "someone-else") is None


def test_sections_round_trip(passport):
    snap = ps.build_snapshot(passport, "user-tests")
    assert snap["identity"]["artist_name"] == "Prayers"
    assert [r["source"] for r in snap["inputs"]] == ["Kick"]
    assert snap["inputs"][0]["phantom"] == 1
    assert [r["mix_name"] for r in snap["outputs"]] == ["Mix 1"]
    for section in ps.SECTIONS:
        assert section in snap, section


def test_an_unknown_field_never_reaches_sql(passport):
    """The section column lists are the allowlist. A stray form key must be
    dropped, not interpolated."""
    ps.add_row("inputs", passport, channel="2", source="Snare",
               drop_table="; DROP TABLE passports;--")
    assert ps.get_passport(passport, "user-tests") is not None
    assert len(ps.rows("inputs", passport)) == 2


def test_playback_is_a_single_row(passport):
    ps.save_playback(passport, system="Ableton", sample_rate="48 kHz", tc_fps="30")
    ps.save_playback(passport, system="Ableton", sample_rate="96 kHz", tc_fps="30")
    pb = ps.get_playback(passport)
    assert pb["sample_rate"] == "96 kHz", "the second save updates, not inserts"


def test_the_stage_plot_is_read_from_the_editor_not_duplicated(passport):
    """There is no passport_stage_plot table. /stage-plot owns the drawing,
    derives the channel list and exports the PNG the advance email attaches;
    a second plot here would be a worse copy of a shipped feature."""
    assert not hasattr(ps, "save_stage_plot")
    store.save_stage_plot("user-tests", {"items": {"drums": 1, "bass": 1}})
    plot = ps.get_stage_plot(passport, "user-tests")
    assert plot["has_plot"] is True
    assert plot["channels"][0] == "Kick — Beta 52"
    assert len(plot["channels"]) == 8


def test_an_artist_with_no_plot_is_not_an_error(passport):
    store.save_stage_plot("user-tests", {})
    plot = ps.get_stage_plot(passport, "user-tests")
    assert plot["has_plot"] is False and plot["channels"] == []


def test_importing_seeds_the_input_list_without_duplicating(passport):
    """The editor already knows a drum kit is seven inputs. Typing that again
    is work the product can do - but a second import must not double it."""
    store.save_stage_plot("user-tests", {"items": {"drums": 1}})
    # The fixture already has a hand-typed "Kick", so a drum kit's seven
    # channels should bring in six - the dedup is the point, not a rounding.
    added = ps.import_inputs_from_plot(passport, "user-tests")
    assert added == 6, "Kick was already there and must not arrive twice"

    again = ps.import_inputs_from_plot(passport, "user-tests")
    assert again == 0, "re-importing must not duplicate"

    sources = [r["source"] for r in ps.rows("inputs", passport)]
    assert sources.count("Kick") == 1
    assert "Snare" in sources and "OH R" in sources


def test_the_import_leaves_what_the_drawing_cannot_know_blank(passport):
    store.save_stage_plot("user-tests", {"items": {"bass": 1}})
    ps.import_inputs_from_plot(passport, "user-tests", replace=True)
    row = [r for r in ps.rows("inputs", passport) if r["source"] == "Bass"][0]
    assert row["mic_di"] == "DI"
    assert row["patch"] == "" and row["stagebox"] == "" and row["performer"] == ""


def test_publishing_freezes_the_drawn_plot_too(passport):
    """This is what the consolidation buys: the drawn plot had no versioning
    of its own, and now a published passport carries the plot as it stood."""
    store.save_stage_plot("user-tests", {"items": {"drums": 1}})
    vid = ps.publish(passport, "user-tests")
    store.save_stage_plot("user-tests", {"items": {"drums": 1, "keys": 2}})
    frozen = ps.get_version(vid, "user-tests")["snapshot"]["stage_plot"]
    assert len(frozen["channels"]) == 7, "the version keeps the plot it froze"
    assert len(ps.get_stage_plot(passport, "user-tests")["channels"]) == 11


# --- immutability, the point of the phase ------------------------------------

def test_publishing_freezes_the_draft(passport):
    vid = ps.publish(passport, "user-tests", published_by="tm@example.net")
    frozen = ps.get_version(vid, "user-tests")["snapshot"]
    assert [r["source"] for r in frozen["inputs"]] == ["Kick"]

    ps.add_row("inputs", passport, channel="2", source="Snare", sort=2)
    ps.update_row("outputs", passport, ps.rows("outputs", passport)[0]["id"],
                  safe_start="CHANGED")

    again = ps.get_version(vid, "user-tests")["snapshot"]
    assert [r["source"] for r in again["inputs"]] == ["Kick"], \
        "a published version must not follow the draft"
    assert again["outputs"][0]["safe_start"] == "-20 dB, vocal only"


def test_publishing_supersedes_the_previous_version(passport):
    first = ps.publish(passport, "user-tests")
    second = ps.publish(passport, "user-tests")
    assert ps.get_version(first, "user-tests")["state"] == "superseded"
    assert ps.get_version(second, "user-tests")["state"] == "published"
    states = [v["state"] for v in ps.versions(passport)]
    assert states.count("published") == 1, "exactly one version is ever in force"


def test_version_numbers_increment_and_never_repeat(passport):
    ps.publish(passport, "user-tests")
    ps.publish(passport, "user-tests")
    ps.publish(passport, "user-tests")
    numbers = [v["number"] for v in ps.versions(passport)]
    assert numbers == [3, 2, 1]


def test_the_passport_points_at_the_newest_version(passport):
    ps.publish(passport, "user-tests")
    second = ps.publish(passport, "user-tests")
    assert ps.get_passport(passport, "user-tests")["current_version_id"] == second
    assert ps.current_version(passport, "user-tests")["number"] == 2


def test_publishing_stamps_last_verified(passport):
    assert ps.get_passport(passport, "user-tests")["last_verified"] == ""
    ps.publish(passport, "user-tests")
    assert ps.get_passport(passport, "user-tests")["last_verified"] != ""


def test_the_version_in_force_cannot_be_archived(passport):
    """Archiving the live version would leave the passport pointing at a
    document it is no longer offering."""
    vid = ps.publish(passport, "user-tests")
    assert ps.archive_version(vid, "user-tests") is False
    ps.publish(passport, "user-tests")
    assert ps.archive_version(vid, "user-tests") is True
    assert ps.get_version(vid, "user-tests")["state"] == "archived"


# --- comparison --------------------------------------------------------------

def test_compare_names_the_fields_that_moved(passport):
    first = ps.publish(passport, "user-tests")
    row = ps.rows("inputs", passport)[0]
    ps.update_row("inputs", passport, row["id"], mic_di="D112")
    second = ps.publish(passport, "user-tests")

    diff = ps.compare_versions(first, second, "user-tests")
    assert "inputs" in diff
    changed = diff["inputs"]["changed"]
    assert changed and "mic_di" in changed[0]["fields"]
    assert changed[0]["before"]["mic_di"] == "Beta 91"
    assert changed[0]["after"]["mic_di"] == "D112"


def test_compare_matches_rows_on_meaning_not_id(passport):
    """A row deleted and retyped is a new id but the same channel. The crew
    reads that as an edit, so the diff must too."""
    first = ps.publish(passport, "user-tests")
    row = ps.rows("inputs", passport)[0]
    ps.delete_row("inputs", passport, row["id"])
    ps.add_row("inputs", passport, channel="1", source="Kick", mic_di="D112", sort=1)
    second = ps.publish(passport, "user-tests")

    diff = ps.compare_versions(first, second, "user-tests")
    assert diff["inputs"]["added"] == []
    assert diff["inputs"]["removed"] == []
    assert "mic_di" in diff["inputs"]["changed"][0]["fields"]


def test_an_identical_republish_shows_no_difference(passport):
    first = ps.publish(passport, "user-tests")
    second = ps.publish(passport, "user-tests")
    assert ps.compare_versions(first, second, "user-tests") == {}


def test_the_publish_prompt_knows_when_there_is_nothing_to_publish(passport):
    assert ps.draft_differs_from_current(passport, "user-tests") is True
    ps.publish(passport, "user-tests")
    assert ps.draft_differs_from_current(passport, "user-tests") is False
    ps.add_row("cues", passport, song="Opener", cue_no="1", cue_type="Playback")
    assert ps.draft_differs_from_current(passport, "user-tests") is True


# --- readiness ---------------------------------------------------------------

def test_gaps_are_facts_not_a_score(passport):
    """A passport that is "80% complete" is not 80% useful - the missing part
    is exactly what the engineer needed."""
    empty = ps.create_passport("user-tests")
    found = ps.gaps(empty, "user-tests")
    assert any("input list" in g for g in found)
    assert any("monitor mixes" in g for g in found)
    assert all(isinstance(g, str) for g in found)
    assert not any("%" in g for g in found)


def test_a_filled_passport_reports_the_specific_hole(passport):
    found = ps.gaps(passport, "user-tests")
    assert not any("input list" in g for g in found)
    ps.add_row("outputs", passport, mix_name="Mix 2", kind="wedge", sort=2)
    found = ps.gaps(passport, "user-tests")
    assert any("not assigned to a performer" in g for g in found)
    assert any("safe starting state" in g for g in found)

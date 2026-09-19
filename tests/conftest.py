"""Point the persistence layer at a throwaway SQLite file for the whole
test session, before any test module imports the app."""

import os
import tempfile

os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="sb-tests-"), "test.db")


import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="module")
def _signal_provider_registry_per_module():
    """What a test file installs as the Signal provider registry stays in
    that file: the registry it found is put back when the file ends. A
    file-wide fixture (test_signal.py's mock universe) never restored it."""
    import signal_providers
    before = signal_providers._registry
    yield
    signal_providers.reset_registry(before)


@pytest.fixture(autouse=True)
def _signal_provider_registry_per_test():
    """A test that swaps the registry with signal_providers.reset_registry
    and does not put it back no longer hands its fake to the next test in
    the same worker. That is how the readiness page lost its Songstats row
    and five tests failed whenever the worker split placed them behind
    test_metrics_staleness.py or test_meter_dialects_folded.py (full run
    of 2026-09-19). The registry the test found, including one a file-wide
    fixture installed on purpose, is what it leaves."""
    import signal_providers
    before = signal_providers._registry
    yield
    signal_providers.reset_registry(before)

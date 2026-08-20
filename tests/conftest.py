"""Point the persistence layer at a throwaway SQLite file for the whole
test session, before any test module imports the app."""

import os
import tempfile

os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="sb-tests-"), "test.db")

# Accounts created by tests behave like established ones, not first-day
# ones. Progressive disclosure hides modules until an account has earned
# them, and almost every test here signs up and then immediately drives a
# deep feature — so without this they would all be testing the disclosure
# system instead of the thing they name. test_unlocks.py opts back into
# simple mode explicitly, and is where first-day behaviour is proved.
import unlock_store  # noqa: E402

unlock_store.DEFAULT_MODE = unlock_store.FULL

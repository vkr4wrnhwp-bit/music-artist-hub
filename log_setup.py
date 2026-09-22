"""Send the app's own log lines somewhere a person can read them.

Nothing in this app configured logging, so every `logging.getLogger(...)`
line went to the root logger with no handler. Python's last-resort handler
then prints WARNING and above and drops the rest, which meant every
`log.info` in the codebase was written and never seen - including
roex_client's "could not connect" and "timed out", and release_ready's
account of what a provider is answering while a job sits unfinished. A
forty-five-minute failure on staging showed nothing in Render's log but
the access lines, and that is why.

Called once from app.py at import, before anything logs. Idempotent: two
gunicorn workers each import the app, and a re-import must not stack a
second handler and double every line.
"""
import logging
import os
import sys

# Ours, so the level is ours to choose. Third-party loggers keep whatever
# they came with: turning urllib3 or botocore up to INFO would bury this.
# "app" is Flask's own app.logger: Flask names it after the application,
# and app.py does Flask(__name__) in a module called app. It is not
# "flask.app", which is a name nothing here ever logs to.
OURS = ("app", "release_ready", "roex_client", "blob_store", "audio")

MARK = "_sb_configured"


def setup(level=None):
    """Attach one stderr handler and put our loggers at LOG_LEVEL.

    stderr because gunicorn captures it and Render shows it. Returns the
    level applied, so a caller can say what it did."""
    want = (level or os.environ.get("LOG_LEVEL") or "INFO").strip().upper()
    if want not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        want = "INFO"
    number = getattr(logging, want)

    root = logging.getLogger()
    if not any(getattr(h, MARK, False) for h in root.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S"))
        setattr(handler, MARK, True)
        root.addHandler(handler)

    # The root stays at WARNING so a chatty dependency does not flood the
    # log; each of ours is turned up on its own.
    if root.level > logging.WARNING or root.level == logging.NOTSET:
        root.setLevel(logging.WARNING)
    for name in OURS:
        got = logging.getLogger(name)
        got.setLevel(number)
        # Flask attaches its own handler to flask.app. Left alone it would
        # print every line a second time through this one.
        got.propagate = True
        for h in list(got.handlers):
            if not getattr(h, MARK, False):
                got.removeHandler(h)
    return want

"""The app's own log lines have to reach the log.

Nothing configured logging, so every log.info in the codebase went to a
root logger with no handler and Python's last-resort handler dropped it.
A forty-five-minute Release-Ready failure on staging left nothing in
Render's log but the access lines, which is what these lock against.
"""
import logging
import sys

import log_setup


def _reset():
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, log_setup.MARK, False):
            root.removeHandler(h)
    for name in log_setup.OURS:
        got = logging.getLogger(name)
        got.setLevel(logging.NOTSET)


def test_an_info_line_from_one_of_our_modules_is_emitted(monkeypatch, capsys):
    _reset()
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert log_setup.setup() == "INFO"
    logging.getLogger("release_ready").info("preview %s not ready", "abc123")
    logging.getLogger("roex_client").info("could not connect")
    err = capsys.readouterr().err
    assert "preview abc123 not ready" in err
    assert "could not connect" in err
    # The name is in the line, so a reader can tell which module spoke.
    assert "release_ready" in err and "roex_client" in err


def test_it_goes_to_stderr_because_that_is_what_gunicorn_captures(monkeypatch, capsys):
    _reset()
    log_setup.setup("INFO")
    logging.getLogger("blob_store").info("bucket line")
    out, err = capsys.readouterr()
    assert "bucket line" in err
    assert "bucket line" not in out


def test_importing_twice_does_not_double_every_line(monkeypatch, capsys):
    """Two gunicorn workers each import the app."""
    _reset()
    log_setup.setup("INFO")
    log_setup.setup("INFO")
    log_setup.setup("INFO")
    logging.getLogger("app").info("once please")
    assert capsys.readouterr().err.count("once please") == 1


def test_a_chatty_dependency_is_not_turned_up_with_us(monkeypatch, capsys):
    """Putting the root at INFO would bury our lines under urllib3's."""
    _reset()
    log_setup.setup("INFO")
    logging.getLogger("urllib3.connectionpool").info("GET / 200")
    logging.getLogger("botocore.hooks").info("event hook")
    err = capsys.readouterr().err
    assert "GET / 200" not in err and "event hook" not in err
    # But a real problem from a dependency still gets through.
    logging.getLogger("urllib3.connectionpool").warning("retrying")
    assert "retrying" in capsys.readouterr().err


def test_the_level_can_be_turned_down_without_a_deploy(monkeypatch, capsys):
    _reset()
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    assert log_setup.setup() == "WARNING"
    logging.getLogger("release_ready").info("chatty")
    logging.getLogger("release_ready").warning("real")
    err = capsys.readouterr().err
    assert "chatty" not in err and "real" in err


def test_nonsense_in_the_variable_falls_back_rather_than_crashing(monkeypatch):
    _reset()
    monkeypatch.setenv("LOG_LEVEL", "loud")
    assert log_setup.setup() == "INFO"
    monkeypatch.setenv("LOG_LEVEL", "")
    assert log_setup.setup() == "INFO"


def test_the_apps_own_logger_is_covered_and_printed_once(monkeypatch, capsys):
    """app.logger is named after the Flask app, not "flask.app": app.py
    does Flask(__name__) in a module called app, so the name is "app".
    Getting this wrong is silent - the lines simply never appear - so the
    name is asserted rather than assumed. Flask attaches its own handler
    lazily, and left in place beside ours it would print each line twice."""
    _reset()
    import flask
    app = flask.Flask("app")
    app.logger.info("warm the handler")          # Flask attaches it lazily
    capsys.readouterr()
    log_setup.setup("INFO")
    app.logger.info("just once")
    assert capsys.readouterr().err.count("just once") == 1


def test_every_logger_the_app_actually_uses_is_in_the_list(monkeypatch):
    """A module that starts logging under a new name would be silent again.
    This walks what the code really asks for, so adding one without adding
    it here fails instead of quietly going unheard."""
    import pathlib
    import re

    wanted = set()
    pattern = re.compile(r"getLogger\(\s*[\"']([A-Za-z0-9_.]+)[\"']\s*\)")
    for path in pathlib.Path(".").glob("*.py"):
        for name in pattern.findall(path.read_text(encoding="utf-8")):
            wanted.add(name)
    # Flask's app.logger, which takes the app module's name.
    wanted.add("app")

    missing = sorted(n for n in wanted
                     if not any(n == o or n.startswith(o + ".") for o in log_setup.OURS))
    assert not missing, ("these loggers are used but never turned up, so their "
                         "lines are dropped: %s" % ", ".join(missing))

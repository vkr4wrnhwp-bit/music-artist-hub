"""Local V1 preview on the THROWAWAY preview database, already signed in.

Same scratch database as tools/dev_preview.py (never the real dev data),
plus a request hook that signs in one throwaway account so the browser
pane can screenshot signed-in pages. A tools/ script, not an app route.

    python tools/v1_preview_signed.py        # http://localhost:5059
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "sb-preview", "preview.db"))
os.makedirs(os.path.dirname(os.environ["DATABASE_PATH"]), exist_ok=True)

from flask import session  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

import app as appmod  # noqa: E402
import db as store  # noqa: E402

EMAIL = "preview@example.net"


def _user_id():
    row = store.get_user_by_email(EMAIL) if hasattr(store, "get_user_by_email") else None
    if row:
        return row["id"]
    uid = store.create_user(EMAIL, "Preview Owner", generate_password_hash(os.urandom(16).hex()))
    if uid is None:
        import sqlite3
        con = sqlite3.connect(os.environ["DATABASE_PATH"])
        uid = con.execute("SELECT id FROM users WHERE email = ?", (EMAIL,)).fetchone()[0]
        con.close()
    try:
        store.set_user_plan(uid, "label")
    except Exception:
        pass
    return uid


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5059"))
    uid = _user_id()

    def _signin():
        # Always set it, never setdefault: a browser holding a cookie
        # from an older preview database keeps a user_id that does not
        # exist here, and setdefault leaves that stale id in place -
        # which is a redirect to /login, not a signed-in page.
        if session.get("user_id") != uid:
            session["user_id"] = uid

    appmod.app.before_request_funcs.setdefault(None, []).insert(0, _signin)
    appmod.app.config["TEMPLATES_AUTO_RELOAD"] = True
    appmod.app.jinja_env.auto_reload = True
    appmod.app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    print("V1 signed preview on http://localhost:%d  (db: %s)" % (port, os.environ["DATABASE_PATH"]))
    appmod.app.run(port=port, debug=False, use_reloader=False, threaded=True)

"""REACH — standalone application entry point.

REACH is its own product. It shares no process, no database and no catalog with
anything else in this repository: this file builds a Flask app that mounts the
REACH blueprint and nothing else.

    pip install -r requirements.txt
    python app.py            # http://127.0.0.1:5000

REACH runs with no configuration. Without a search credential, discovery uses
the built-in fixture corpus and every screen says so. See
docs/INTEGRATION_SETUP.md to connect real providers.
"""

import os

from flask import Flask, redirect

from reach.web import bp as reach_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(reach_bp)

    @app.route("/")
    def index():
        return redirect("/reach")

    @app.route("/healthz")
    def healthz():
        # Deliberately does not touch the database: a health check that fails on
        # a slow query takes the service down for a problem it did not have.
        return {"ok": True, "service": "reach"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)

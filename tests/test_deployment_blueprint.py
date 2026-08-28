"""Guards on render.yaml, the one file that decides what actually deploys.

Every product in this repository is a separate application, but Render only
reads the blueprint at the repository root. These tests keep that file honest:
each product stays declared, and REACH's standalone copy — kept for a future
repository split — cannot silently drift away from the definition that really
deploys.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _blueprint(path):
    return yaml.safe_load((ROOT / path).read_text())


def test_every_product_has_a_service():
    services = {s["name"]: s for s in _blueprint("render.yaml")["services"]}
    assert set(services) == {
        "trace",
        "reach",
        "masterclip",
        "royalty-sweep",
        "holeshot-tuner",
    }
    # each service points at a directory that exists (or the repo root)
    for name, service in services.items():
        root_dir = service.get("rootDir")
        if root_dir:
            assert (ROOT / root_dir).is_dir(), f"{name} points at a missing {root_dir}"


def test_royalty_sweep_serves_the_root_flask_app():
    service = next(
        s for s in _blueprint("render.yaml")["services"] if s["name"] == "royalty-sweep"
    )
    assert "gunicorn app:app" in service["startCommand"]
    assert service["healthCheckPath"] == "/dashboard"
    assert (ROOT / "app.py").is_file()


def test_reach_standalone_copy_matches_the_deploying_definition():
    """reach-app/render.yaml is never what deploys; it must not drift from what is."""
    deploying = next(
        s for s in _blueprint("render.yaml")["services"] if s["name"] == "reach"
    )
    standalone = _blueprint("reach-app/render.yaml")["services"][0]
    assert standalone == deploying, (
        "reach-app/render.yaml has drifted from the root blueprint — "
        "the root file is the one Render reads"
    )

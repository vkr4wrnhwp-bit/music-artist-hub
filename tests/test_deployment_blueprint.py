"""Guards on render.yaml, the one file that decides what actually deploys.

Every product in this repository is a separate application, but Render only
reads the blueprint at the repository root. These tests keep that file honest:
each product stays declared, and REACH's standalone copy — kept for a future
repository split — cannot silently drift away from the definition that really
deploys.

They also keep MASTERCLIP OS *out*. It has its own repository and its own
blueprint; it was once vendored here as masterclip-os/ and deployed from this
file, which meant production ran whatever had last been hand-copied across.
That copy fell six days and seventeen packages behind before anyone noticed.
`test_masterclip_is_not_vendored_back` is what makes re-adding it fail loudly
rather than quietly restart the treadmill.
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


def test_masterclip_is_not_vendored_back():
    """MASTERCLIP OS is its own repository; a copy here is the bug, not the fix.

    Deploying it from this repo means every upstream commit reaches production
    only once a human remembers to copy it. That is how the directory came to
    be six days and seventeen whole packages behind the product (#55), and how
    a cost-control fix ended up in the copy while the live service shipped
    without it. If this fails, delete the directory rather than the test.
    """
    assert not (ROOT / "masterclip-os").exists(), (
        "masterclip-os/ is back. It belongs to "
        "github.com/vkr4wrnhwp-bit/masterclip-os, which deploys from its own "
        "render.yaml; a copy here can only drift from it."
    )
    names = {s["name"] for s in _blueprint("render.yaml")["services"]}
    assert "masterclip" not in names, (
        "the masterclip service is back in this blueprint — it is declared in "
        "the masterclip-os repository's own render.yaml"
    )

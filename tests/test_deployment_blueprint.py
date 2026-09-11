"""Guards on render.yaml, the one file that decides what actually deploys.

Every product in this repository is a separate application, but Render only
reads the blueprint at the repository root. These tests keep that file honest:
each product stays declared, and each points at a directory that exists.

There is deliberately only one copy of each service definition. `reach-app/`
used to carry its own `render.yaml` "for a future repository split", which
nothing deployed from and a test had to hold in step with the real one; it also
left three documents claiming the root blueprint deployed TRACE only. A config
that nothing reads is a config nobody notices going wrong, so it was deleted
rather than guarded.

They also keep MASTERCLIP OS *out*. It has its own repository and its own
blueprint; it was once vendored here as masterclip-os/ and deployed from this
file, which meant production ran whatever had last been hand-copied across.
That copy fell six days and seventeen packages behind before anyone noticed.
`test_masterclip_is_not_vendored_back` is what makes re-adding it fail loudly
rather than quietly restart the treadmill.

Holeshot Tuner is kept out for a different reason. It was not a separate
repository, it was a second implementation of a tool TRACE already had — the
same RPM x throttle grid, without the revisions, approval gates and per-bike
ECU axes TRACE wraps around it. Its editing tools were folded into TRACE and
the standalone worksheet retired, so a `fuel-map-tool/` directory reappearing
means the fork is back.
"""

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _blueprint(path):
    return yaml.safe_load((ROOT / path).read_text())


def _is_tracked(path):
    """Whether git tracks anything at `path`.

    The guards below ask this rather than `Path.exists()`, because the thing
    they forbid is a copy *committed to this repository* — not a directory
    lying around in someone's checkout. Those are not the same question, and
    the difference is not academic: deleting masterclip-os/ took its
    .gitignore with it, so every working copy that had ever built the vendored
    tree kept ~364 MB of node_modules, dist and a local .env at that path. An
    existence check calls that "masterclip-os/ is back" and fails a clean
    tree, which teaches people that a red suite is normal. This check passes,
    and still fails the moment a single file is actually committed there.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        # No git binary at all — a source zip, or a slim image that ships
        # none. `check=False` does not cover this: subprocess raises before
        # there is a returncode to inspect, so catching only the non-zero exit
        # missed half of the very case this fallback is here for.
        return (ROOT / path).exists()
    if result.returncode != 0:  # git present, but not a work tree
        return (ROOT / path).exists()
    return bool(result.stdout.strip())


def test_every_product_has_a_service():
    declared = [s["name"] for s in _blueprint("render.yaml")["services"]]
    # Before the set comparison, not after: keying services by name collapses a
    # duplicate definition into one entry, so a second `trace` block declared
    # halfway down the file would satisfy every assertion in this module while
    # Render read two conflicting definitions of the same service.
    assert len(declared) == len(set(declared)), (
        f"render.yaml declares a service twice: {sorted(declared)}"
    )
    services = {s["name"]: s for s in _blueprint("render.yaml")["services"]}
    assert set(services) == {
        "trace",
        "reach",
        "royalty-sweep",
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


def test_reach_has_no_second_service_definition():
    """One definition per service. A copy nothing deploys from only drifts.

    `reach-app/render.yaml` was kept "for a future repository split" and had to
    be held in step with the root blueprint by a test, because nothing deployed
    from it. It is the same shape as the masterclip directory above, one size
    down: a second copy of an active config, kept honest by hand.
    """
    assert not _is_tracked("reach-app/render.yaml"), (
        "reach-app/render.yaml is back. The root blueprint declares the `reach` "
        "service and is the only file Render reads; reach-app/README.md "
        "documents standing REACH up without a blueprint at all."
    )


def test_masterclip_is_not_vendored_back():
    """MASTERCLIP OS is its own repository; a copy here is the bug, not the fix.

    Deploying it from this repo means every upstream commit reaches production
    only once a human remembers to copy it. That is how the directory came to
    be six days and seventeen whole packages behind the product (#55), and how
    a cost-control fix ended up in the copy while the live service shipped
    without it. If this fails, delete the directory rather than the test.
    """
    assert not _is_tracked("masterclip-os"), (
        "masterclip-os/ is back. It belongs to "
        "github.com/vkr4wrnhwp-bit/masterclip-os, which deploys from its own "
        "render.yaml; a copy here can only drift from it."
    )
    names = {s["name"] for s in _blueprint("render.yaml")["services"]}
    assert "masterclip" not in names, (
        "the masterclip service is back in this blueprint — it is declared in "
        "the masterclip-os repository's own render.yaml"
    )


def test_holeshot_tuner_is_not_vendored_back():
    """The fuel-map worksheet was folded into TRACE; a copy here is the fork again.

    `fuel-map-tool/index.html` and the `trackside` repository were two
    implementations of the same tuner, drifting apart from each other and from
    TRACE's own map editor. TRACE now owns that grid — with heatmap editing,
    smooth, interpolate, undo/redo, air density and condition presets — so a
    standalone copy has nothing to add and everything to drift from.
    """
    assert not _is_tracked("fuel-map-tool"), (
        "fuel-map-tool/ is back. Fuel and ignition map editing lives in "
        "mx-lab/ (TRACE); see mx-lab/packages/domain/src/mapEditing.ts"
    )
    names = {s["name"] for s in _blueprint("render.yaml")["services"]}
    assert "holeshot-tuner" not in names, (
        "the holeshot-tuner service is back — the tuner is a screen inside "
        "TRACE now, not its own deployment"
    )

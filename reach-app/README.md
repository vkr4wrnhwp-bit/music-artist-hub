# REACH

Global music discovery, opportunity intelligence, outreach and submission
management. REACH finds the playlists, blogs, radio shows, labels and sync
outlets that plausibly fit a track, records the evidence behind every claim it
makes, and routes each opportunity either to an approved direct email or to a
structured human task.

**REACH is a standalone application.** It has its own entry point, its own
templates, its own database and its own recording catalog. It shares no process,
no data and no deployment with the other products in this repository.

## Run it

```bash
cd reach-app
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000` — `/` redirects to `/reach`.

REACH needs no internet connection to render: the stylesheet is built ahead of
time into `static/` and served by the app, so there is no CDN in the page and
nothing to load from a third party.

REACH runs with **no configuration at all**. Without a search credential,
discovery runs against a built-in fixture corpus of reserved `.example` domains,
and every screen labels the run as fixture mode rather than passing invented
results off as real ones. See [`docs/INTEGRATION_SETUP.md`](docs/INTEGRATION_SETUP.md)
to connect real providers.

## Your catalog

The **Catalog** screen is where tracks come from. REACH does not read another
application's songs: you add a track, and only a title and an artist name are
required. Anything you leave blank stays UNKNOWN — REACH shows the gap instead
of filling it in, because a missing ISRC blocks different routes than a missing
UPC does, and a stream count you never entered is not a stream count of zero.

REACH is not a royalty system and has no reporting feed. Any performance figure
a pitch quotes is one you entered yourself, and it is labelled as such in the
"source of every factual claim" panel on the review screen.

A first run seeds five **sample** tracks so the pipeline can be exercised before
you enter real ones. Every one carries a SAMPLE badge; their figures are
illustrative, not measured. Delete them from the Catalog screen once your own
tracks are in, or start empty with `REACH_SEED_SAMPLE_TRACKS=0`.

## Deploy

`render.yaml` in this directory is REACH's own Render blueprint — separate from
the TRACE blueprint at the repository root. Neither one deploys the other.
`Dockerfile` is the container equivalent. Both need one thing to be useful:
`REACH_DB_PATH` pointing at a mounted disk, so the store survives a restart.

## Develop

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest
```

Both run in CI as the `REACH tests & lint` job.

`static/tailwind.css` is committed so deploying stays a pure-Python operation.
Run `tools/build-css.sh` after adding a utility class a template has not used
before — that is the only step that needs node, and a test tells you when it is
needed.

**Pre-release schema note.** REACH has never been deployed, so the migration
that creates the catalog was edited in place rather than layered over with an
ALTER. If you have a `reach.db` from an earlier local run, delete it — it
predates the standalone catalog and will not migrate forward.

## Documentation

[Phase One](docs/PHASE_ONE.md) ·
[Architecture](docs/ARCHITECTURE.md) ·
[Data model](docs/DATA_MODEL.md) ·
[Provider policy matrix](docs/PROVIDER_POLICY_MATRIX.md) ·
[Security threat model](docs/SECURITY_THREAT_MODEL.md) ·
[Outreach compliance](docs/OUTREACH_COMPLIANCE.md) ·
[Integration setup](docs/INTEGRATION_SETUP.md) ·
[Test plan](docs/TEST_PLAN.md)

# music-artist-hub

Early scaffold for a music & artists app. This repo starts small: a couple of
shared utility functions that the rest of the app will build on.

## Utilities

`music_utils/duration.py`
- `format_duration(seconds)` — turns a track length in seconds into `mm:ss`
  (or `h:mm:ss` for tracks over an hour).
- `parse_artist_list(raw)` — splits a comma/`&`/`feat.`-separated credit
  string (e.g. `"Artist A, Artist B & Artist C"`) into a clean list of names.

## Dashboard

`app.py` serves an artist dashboard at `/dashboard` with royalty balances
(seeded mock data for now — no live platform integrations yet), key metrics,
an earnings trend chart, and recent payouts.

```
pip install -r requirements.txt
python app.py
```

Then visit `http://127.0.0.1:5000/dashboard`.

## REACH

`reach/` adds a native module for global music discovery, opportunity
intelligence and submission management, mounted at `/reach`. It builds campaigns
from tracks already in this catalog, researches permitted sources, records the
evidence behind every claim, and routes each opportunity either to an approved
direct email or to a structured human task.

REACH runs with no configuration: without a search credential, discovery uses a
built-in fixture corpus and every screen labels it as such. See
`docs/reach/INTEGRATION_SETUP.md` to connect real providers.

```
pip install -r requirements.txt
python app.py
```

Then visit `http://127.0.0.1:5000/reach`.

Documentation: [Phase One](docs/reach/PHASE_ONE.md) ·
[Architecture](docs/reach/ARCHITECTURE.md) ·
[Data model](docs/reach/DATA_MODEL.md) ·
[Provider policy matrix](docs/reach/PROVIDER_POLICY_MATRIX.md) ·
[Security threat model](docs/reach/SECURITY_THREAT_MODEL.md) ·
[Outreach compliance](docs/reach/OUTREACH_COMPLIANCE.md) ·
[Integration setup](docs/reach/INTEGRATION_SETUP.md) ·
[Test plan](docs/reach/TEST_PLAN.md)

## Development

```
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest
```

Both run in CI.

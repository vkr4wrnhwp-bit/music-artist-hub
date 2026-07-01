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

## Development

```
pip install -r requirements.txt
pytest
```
